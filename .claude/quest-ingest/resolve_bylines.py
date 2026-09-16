#!/usr/bin/env python3
"""Resolve `thinker_unresolved` bylines in the Quest works, in place.

WHY NOT RE-EMIT. The handoff said to re-run emit-astro-md.py so bylines resolve
against the new profiles. emit_primary_work writes with overwrite=True, and
everything added to these files AFTER emit would be destroyed: the pdf_url and
cover_image that publish.py writes, the provenance.notes and scan_quality for
the seven issues with recorded scan defects (four of which I wrote by hand from
an agent's report, so they exist in no extraction), and the quoted
publication.series that unblocked the site's deploys. Re-emitting would also
restore series as an integer and break Content check again.

So this edits in place: for each contributor carrying `thinker_unresolved`, look
the byline up in the authority file exactly as emit-astro-md.py does, and on a
genuine match replace it with `thinker: <id>`, promoting author-role matches
into `authors[]` the way the emitter does. Nothing else in the file is touched,
and the frontmatter is re-parsed before it is saved.

Both guards from build_profiles.py apply, because the authority file now holds
930 more byline keys than it did and the ambiguity is worse, not better:
  - a lone GIVEN name never resolves (Quest QT011's "Indira");
  - a lone SURNAME never resolves to someone whose given name the byline
    contradicts (Michael Polanyi is not Karl).

Usage: resolve_bylines.py --audit | --fix [slug ...]
"""
from __future__ import annotations

import importlib.util, json, re, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKS = REPO / "apps/site/src/content/primary-works"
AUTHORITY = REPO / "data/authority/thinkers.json"
FM = re.compile(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$")

_spec = importlib.util.spec_from_file_location("bp", Path(__file__).with_name("build_profiles.py"))
bp = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bp)


def emit_normalise(s: str) -> str:
    """Exactly emit-astro-md.py's _normalise_byline, so we hit the same keys."""
    s = s.lower().replace(".", " ").replace(",", " ").replace("-", " ")
    s = s.replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", s).strip()


HON = r"(prof|dr|mr|mrs|ms|shri|sri|sir|justice|lord|lady|pandit|acharya|miss|swami|the late)"


def candidates(byline: str) -> list[str]:
    bv = re.sub(r"\s*\([^)]+\)\s*$", "", byline)
    bv = re.sub(r",?\s*(I\.?A\.?S\.?|I\.?C\.?S\.?|M\.?P\.?|Esq\.?|Ph\.?\s*D\.?)\s*$", "", bv, flags=re.I)
    bv = bv.strip(" ,.").strip()
    out = [emit_normalise(bv)]
    out.append(re.sub(rf"^{HON}\s+", "", out[0]))
    out.append(re.sub(rf"\b{HON}\b\.?\s*", " ", out[0]).strip())
    out.append(bp.norm(bv))
    out.append(emit_normalise(bp.display_name(byline)))   # strips role prefixes
    out.append(bp.norm(bp.display_name(byline)))
    seen, uniq = set(), []
    for c in out:
        c = re.sub(r"\s+", " ", c).strip()
        if c and c not in seen:
            seen.add(c); uniq.append(c)
    return uniq


def main() -> int:
    argv = sys.argv[1:]
    fix = "--fix" in argv
    if not fix and "--audit" not in argv:
        print(__doc__); return 2
    slugs = [a.lower() for a in argv if not a.startswith("--")]

    doc = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    lookup = {emit_normalise(k): v for k, v in (doc.get("byline_lookup") or {}).items()}
    canon = {t["id"]: (t.get("name") or {}).get("canonical", "")
             for t in doc.get("thinkers", []) if t.get("id")}

    files = sorted(WORKS.glob("qt[0-9][0-9][0-9].md"))
    if slugs:
        files = [p for p in files if p.stem in slugs]
    tot_res = tot_left = tot_refused = 0
    for p in files:
        m = FM.match(p.read_text(encoding="utf-8"))
        fm = yaml.safe_load(m.group(1)); body = m.group(2)
        authors = list(fm.get("authors") or [])
        resolved = left = refused = 0
        for c in fm.get("contributors") or []:
            bl = c.get("thinker_unresolved")
            if not bl:
                continue
            tid = next((lookup[k] for k in candidates(bl) if k in lookup), None)
            if tid:
                # A byline that is a leading run of the canonical name is the
                # same person: "Swami Agehananda" against "Swami Agehananda
                # Bharati". Without this the given-name guard refused all five
                # of his bylines, because stripping the honorific leaves one
                # token that IS the entry's first name.
                ctoks, ktoks = bp.tokens(bl), bp.tokens(canon.get(tid, ""))
                prefix_of_entry = bool(ctoks) and ktoks[:len(ctoks)] == ctoks
                if not prefix_of_entry and (bp.given_name_clash(bl, tid, canon) or (
                        len(bp.tokens(bl)) == 1 and bp.alias_conflict(bl, tid, canon))):
                    refused += 1; left += 1; continue
                c.pop("thinker_unresolved")
                c["thinker"] = tid
                if (c.get("role") or "author") == "author" and tid not in authors:
                    authors.append(tid)
                resolved += 1
            else:
                left += 1
        if resolved and fix:
            fm["authors"] = authors
            out = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                                 default_flow_style=False, width=100000)
            text = f"---\n{out}---\n{body}"
            yaml.safe_load(FM.match(text).group(1))      # parse before saving
            p.write_text(text, encoding="utf-8")
        print(f"{p.stem}: {resolved} resolved, {left} still unresolved"
              + (f", {refused} refused by a guard" if refused else ""))
        tot_res += resolved; tot_left += left; tot_refused += refused
    verb = "resolved" if fix else "resolvable"
    print(f"\n{tot_res} bylines {verb} across {len(files)} works; "
          f"{tot_left} remain unresolved; {tot_refused} refused by a guard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
