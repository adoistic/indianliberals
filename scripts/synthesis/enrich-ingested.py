#!/usr/bin/env python3
"""Post-ingestion enrichment for primary-works MDs produced by the v1.5 pipeline.

Two passes, both idempotent and targeted (no YAML round-trip — edits only the
specific frontmatter keys so diffs stay minimal):

  1. THEMES — when `themes: []`, backfill from the work's summary.json
     (summary_structured.themes_confirmed + theme_proposed_new).
  2. AUTHORS / CONTRIBUTORS — re-resolve against the FULL authority file
     (canonical + also_known_as, incl. Devanagari aliases), which the
     extraction prompt's 60-thinker subset could not see. When `authors: []`
     but the work's metadata carries a byline that matches authority, fill
     `authors:`. For periodical contributors, resolve `thinker_unresolved:`
     to a `thinker:` id when it matches.

Unmatched bylines (genuinely not in authority) are written to
data/synthesis/unresolved-bylines.tsv for the stub-creation step.

Run: .venv-extract/bin/python3 scripts/synthesis/enrich-ingested.py [--themes-only|--authors-only]
"""
from __future__ import annotations
import csv, json, re, sys, pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
PW = ROOT / "apps/site/src/content/primary-works"
BAKE = ROOT / "data/bake-off-output"
AUTH = ROOT / "data/authority/thinkers.json"
BACKLOG = ROOT / "data/synthesis/ingestion-backlog.csv"

_HONOR = re.compile(r"\b(dr|prof|professor|mr|mrs|ms|miss|justice|sir|capt|captain|col|colonel|"
                    r"gen|general|admiral|shri|smt|smti|hon|honourable|acharya|swami|maj|major|lt|"
                    r"the late|late|rtd|retd|i\.?c\.?s|m\.?p|m\.?l\.?a)\b", re.I)
def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"^\s*by\s+", " ", s)          # strip leading "By "
    s = re.sub(r"\(.*?\)", " ", s)            # drop (Retd.) etc.
    s = _HONOR.sub(" ", s)
    s = re.sub(r"[^a-z0-9ऀ-ॿঀ-৿ ]+", " ", s)  # keep latin + devanagari + bengali
    return re.sub(r"\s+", " ", s).strip()

def _li_key(n: str):
    """(lastname, first-initial) for a latin normalized name; None if not usable."""
    toks = [t for t in n.split() if t]
    if len(toks) >= 2 and toks[0].isascii():
        return (toks[-1], toks[0][0])
    return None

def es(stem: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-").lower()

import yaml
THINKERS = ROOT / "apps/site/src/content/thinkers"
def load_authority():
    """Build the lookup from the CONTENT thinker files (richer aliases than the
    authority JSON, incl. Latin + Devanagari forms)."""
    lut = {}; li = {}
    for p in THINKERS.glob("*.md"):
        m = FR.match(p.read_text(errors="ignore"))
        if not m: continue
        try: fm = yaml.safe_load(m.group(2)) or {}
        except Exception: continue
        tid = fm.get("id") or p.stem
        nm = fm.get("name") or {}
        akas = nm.get("also_known_as") or []
        for form in [nm.get("canonical"), nm.get("full")] + akas:
            if form:
                k = norm(str(form))
                if k and k not in lut:
                    lut[k] = tid
        # lastname+initial index from canonical/full only (not aka — less noise)
        for form in [nm.get("canonical"), nm.get("full")]:
            key = _li_key(norm(str(form))) if form else None
            if key:
                li.setdefault(key, set()).add(tid)
    return lut, li

def resolve(byline, lut, li):
    n = norm(byline)
    if n in lut: return lut[n]
    key = _li_key(n)
    if key and len(li.get(key, ())) == 1:
        return next(iter(li[key]))
    return None

FR = re.compile(r"^(---\n)(.*?)(\n---\n?)(.*)$", re.S)

def split_fm(text):
    m = FR.match(text)
    return (m.group(2), m.group(4), m) if m else (None, None, None)

def bake_dir_map():
    return {es(d.name): d for d in BAKE.iterdir() if d.is_dir()}

def read_meta(bd: pathlib.Path):
    for c in ("tiebreak.json","metadata.a.a.json","metadata.b.b.json","metadata.a.json","metadata.b.json"):
        p = bd / c
        if p.exists():
            try: return json.loads(p.read_text())
            except json.JSONDecodeError: pass
    return {}

def read_summary(bd: pathlib.Path):
    p = bd / "summary.json"
    if p.exists():
        try: return json.loads(p.read_text())
        except json.JSONDecodeError: pass
    return {}

def main():
    mode = next((a for a in sys.argv[1:] if a in ("--themes-only","--authors-only")), "")
    lut, li = load_authority()
    bdmap = bake_dir_map()
    if "--all-bake" in sys.argv:
        # Every MD that has a matching bake-off dir (covers earlier batches the
        # backlog CSV never listed), keyed by emit-slug.
        mds = [PW / (slug + ".md") for slug in bdmap]
        mds = [p for p in dict.fromkeys(mds) if p.exists()]
    else:
        backlog = list(csv.DictReader(open(BACKLOG)))
        mds = [PW / (es(r["filename"][:-4]) + ".md") for r in backlog]
        mds = [p for p in dict.fromkeys(mds) if p.exists()]

    stat = Counter(); unmatched = Counter()
    for p in mds:
        text = p.read_text(); fm, body, m = split_fm(text)
        if fm is None: continue
        bd = bdmap.get(p.stem)
        changed = False

        # ---- THEMES ----
        if mode in ("", "--themes-only") and re.search(r"^themes:\s*\[\]\s*$", fm, re.M) and bd:
            s = read_summary(bd); ss = s.get("summary_structured") or {}
            themes = list(dict.fromkeys((ss.get("themes_confirmed") or []) + (ss.get("theme_proposed_new") or [])))
            themes = [re.sub(r"[^a-z0-9-]+","-",t.lower()).strip("-") for t in themes if t]
            themes = [t for t in themes if t][:10]
            if themes:
                block = "themes:\n" + "\n".join(f"  - {t}" for t in themes)
                fm = re.sub(r"^themes:\s*\[\]\s*$", block, fm, count=1, flags=re.M)
                changed = True; stat["themes_filled"] += 1

        # ---- AUTHORS (authors: []) ----
        if mode in ("", "--authors-only") and re.search(r"^authors:\s*\[\]\s*$", fm, re.M) and bd:
            meta = read_meta(bd)
            ids = []
            for a in (meta.get("authors") or []):
                bv = a.get("byline_verbatim") or ""
                hit = resolve(bv, lut, li)
                if hit and hit not in ids: ids.append(hit)
                elif bv and not hit: unmatched[bv.strip()] += 1
            if ids:
                block = "authors:\n" + "\n".join(f"  - {i}" for i in ids)
                fm = re.sub(r"^authors:\s*\[\]\s*$", block, fm, count=1, flags=re.M)
                changed = True; stat["authors_resolved"] += 1

        # ---- CONTRIBUTORS thinker_unresolved -> thinker ----
        if mode in ("", "--authors-only") and "thinker_unresolved:" in fm:
            def repl(mo):
                indent, name = mo.group(1), mo.group(2).strip().strip('"\'')
                hit = resolve(name, lut, li)
                if hit:
                    repl.n += 1
                    return f"{indent}thinker: {hit}\n{indent}thinker_unresolved: null"
                return mo.group(0)
            repl.n = 0
            fm2 = re.sub(r"^(\s+)thinker_unresolved:\s*(.+)$", repl, fm, flags=re.M)
            if repl.n:
                fm = fm2; changed = True; stat["contributors_resolved"] += repl.n

        if changed:
            p.write_text(m.group(1) + fm + m.group(3) + body)

    print(f"MDs scanned: {len(mds)}")
    for k, v in stat.items(): print(f"  {k}: {v}")
    if unmatched:
        out = ROOT / "data/synthesis/unresolved-bylines.tsv"
        with out.open("w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t"); w.writerow(["byline","count"])
            for b, c in unmatched.most_common(): w.writerow([b, c])
        print(f"  unmatched unique bylines: {len(unmatched)} -> {out.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
