#!/usr/bin/env python3
"""
Backfill structured thinker references on Tier-A content.

The WordPress import populated string fields (author_name on opinions /
theprint-mirror, subject_name on interviews) but left the structured
references empty. AND the same WordPress import dropped some article
titles into the thinkers collection as fake "imported" entries, which
poisons naive byline_lookup-based matching.

This resolver:
  1. Builds a LOOKUP of real-thinker names only — filters out WP-imported
     stubs whose "canonical" name looks like an article title (contains
     " - ", " on ", ":", or is unusually long).
  2. For each Tier-A entry, reads the name field; for interviews the
     subject_name is often an article title, so we ALSO try the prefix
     before any " - ", " on ", ":" separator.
  3. Writes the structured reference back:
       - interviews: `subject:` (single ref)
       - opinions:   `author:` and `related_thinkers:` (single + array)
       - theprint-mirror: `related_thinkers:` (theprint-mirror has no
         `author` reference field in the schema; the related-thinkers
         array is the canonical place for byline-resolved IDs)
  4. Idempotent: re-running is safe (existing refs are not overwritten).

Run from the repo root:
    python3 scripts/synthesis/resolve-bylines.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
AUTHORITY = ROOT / "data/authority/thinkers.json"

# A "real" thinker name shouldn't look like an article title. These markers
# are heuristics tuned to the WP-import garbage we observed.
ARTICLE_TITLE_MARKERS = [
    " - ",  # "A.D. Shroff - Champion of..."
    " on ",  # "D R Pendse on the 1991 Crisis"
    ": ",
    " and ",  # "Constitution and Charter..."
]

# Min/max plausible length for a real person's canonical name
MIN_NAME_LEN = 3
MAX_NAME_LEN = 60


def normalise(s: str) -> str:
    s = s.lower().replace(".", " ").replace(",", " ").replace("-", " ").replace("'", "").replace("’", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def looks_like_real_name(canonical: str) -> bool:
    """Heuristic filter to drop WP-imported article-title-as-thinker stubs."""
    if not canonical:
        return False
    if not (MIN_NAME_LEN <= len(canonical) <= MAX_NAME_LEN):
        return False
    lower = canonical.lower()
    for marker in ARTICLE_TITLE_MARKERS:
        if marker in lower:
            return False
    # Mixed-content giveaways
    if "?" in canonical or "!" in canonical:
        return False
    # Real names rarely have 5+ words
    if len(canonical.split()) > 5:
        return False
    return True


def build_lookup(authority: dict) -> dict[str, str]:
    """needle -> thinker_id, filtered to real names only."""
    real_thinker_ids: set[str] = set()
    lookup: dict[str, str] = {}
    for t in authority.get("thinkers", []):
        name = t.get("name", {})
        canonical = name.get("canonical", "")
        if not looks_like_real_name(canonical):
            continue
        tid = t["id"]
        real_thinker_ids.add(tid)
        cands: list[str] = [canonical]
        if name.get("full") and looks_like_real_name(name["full"]):
            cands.append(name["full"])
        if name.get("sort") and looks_like_real_name(name["sort"]):
            cands.append(name["sort"])
        for aka in name.get("also_known_as", []) or []:
            if looks_like_real_name(aka):
                cands.append(aka)
        for c in cands:
            n = normalise(c)
            if n and n not in lookup:
                lookup[n] = tid
            # without leading honorific
            stripped = re.sub(r"^(prof|dr|mr|mrs|ms|shri|sri)\.?\s+", "", c.lower())
            ns = normalise(stripped)
            if ns and ns not in lookup:
                lookup[ns] = tid
    # Also seed from the pre-built byline_lookup, but only if the target id
    # is a real-thinker id (drops the WP-imported article-title-as-thinker pollution).
    for k, v in authority.get("byline_lookup", {}).items():
        if v in real_thinker_ids and k not in lookup:
            lookup[k] = v
    return lookup


def split_subject_title(s: str) -> list[str]:
    """For interview subject_name shape 'Person Name - Article Title' or
    'Person Name on Topic', return candidate prefixes to try."""
    candidates = [s]
    for sep in (" - ", ": ", " – "):
        if sep in s:
            candidates.append(s.split(sep, 1)[0].strip())
    # "Person on Topic" — try the part before " on "
    m = re.search(r"^(.+?)\s+on\s+", s, re.I)
    if m:
        candidates.append(m.group(1).strip())
    # De-dup
    seen: set[str] = set()
    return [c for c in candidates if c and not (c in seen or seen.add(c))]


def parse_byline(s: str) -> list[str]:
    s = re.sub(r"\bby\s+", "", s, flags=re.I).strip()
    parts = re.split(r"\s*(?:,|;|\band\b|&)\s*", s, flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def resolve_via(name: str, lookup: dict[str, str]) -> list[str]:
    """Resolve one name candidate. Returns a list of thinker_ids."""
    out: list[str] = []
    for part in parse_byline(name):
        n = normalise(part)
        if not n:
            continue
        if n in lookup:
            out.append(lookup[n])
            continue
        # try stripping honorific
        n2 = re.sub(r"^(prof|dr|mr|mrs|ms|shri|sri)\s+", "", n)
        if n2 in lookup:
            out.append(lookup[n2])
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def quote(s: str) -> str:
    return f'"{s}"'


def patch_or_set(text: str, field: str, value: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return text
    fm = m.group(1)
    line_rx = re.compile(rf"^{re.escape(field)}:\s*.*$", re.M)
    new_line = f"{field}: {value}"
    if line_rx.search(fm):
        existing = line_rx.search(fm).group(0)  # type: ignore
        v = existing.split(":", 1)[1].strip()
        if v and v not in ("null", "[]", '""', "''"):
            return text  # already populated
        new_fm = line_rx.sub(new_line, fm)
    else:
        new_fm = fm + "\n" + new_line
    return text[: m.start()] + "---\n" + new_fm + "\n---" + text[m.end():]


def main() -> int:
    authority = json.loads(AUTHORITY.read_text())
    lookup = build_lookup(authority)
    print(f"[bylines] real-name lookup size: {len(lookup)} needles")

    summary: dict[str, dict[str, int]] = {}

    # Interviews: subject_name is usually an article title; also try the prefix.
    interviews_patched = unresolved = 0
    for p in sorted((CONTENT_ROOT / "interviews").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            continue
        fm = m.group(1)
        if re.search(r'^subject:\s*"[^"]+"', fm, re.M):
            continue
        sm = re.search(r'^subject_name:\s*"?([^"\n]+)"?\s*$', fm, re.M)
        if not sm:
            continue
        candidates = split_subject_title(sm.group(1).strip().strip('"').strip("'"))
        resolved: list[str] = []
        for c in candidates:
            resolved = resolve_via(c, lookup)
            if resolved:
                break
        if not resolved:
            unresolved += 1
            continue
        new_text = patch_or_set(text, "subject", quote(resolved[0]))
        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            interviews_patched += 1
    summary["interviews"] = {"patched": interviews_patched, "unresolved": unresolved}

    # Opinions: author_name (skip "Editorial Team" placeholders)
    op_patched = op_unresolved = op_skipped = 0
    for p in sorted((CONTENT_ROOT / "opinions").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            continue
        fm = m.group(1)
        if re.search(r'^author:\s*"[^"]+"', fm, re.M):
            continue
        am = re.search(r'^author_name:\s*"?([^"\n]+)"?\s*$', fm, re.M)
        if not am:
            continue
        byline = am.group(1).strip().strip('"').strip("'")
        if byline.lower() in ("unknown", "anonymous", "editorial team", "ccs editorial team"):
            op_skipped += 1
            continue
        resolved = resolve_via(byline, lookup)
        if not resolved:
            op_unresolved += 1
            continue
        new_text = patch_or_set(text, "author", quote(resolved[0]))
        if len(resolved) > 1:
            arr = "[" + ", ".join(quote(r) for r in resolved[1:]) + "]"
            new_text = patch_or_set(new_text, "related_thinkers", arr)
        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            op_patched += 1
    summary["opinions"] = {"patched": op_patched, "skipped_editorial": op_skipped, "unresolved": op_unresolved}

    # theprint-mirror: author_name → related_thinkers (schema has no author field)
    tp_patched = tp_unresolved = 0
    for p in sorted((CONTENT_ROOT / "theprint-mirror").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            continue
        fm = m.group(1)
        rt_match = re.search(r"^related_thinkers:\s*\[(.*?)\]\s*$", fm, re.M)
        if rt_match and rt_match.group(1).strip():
            continue  # already populated
        am = re.search(r'^author_name:\s*"?([^"\n]+)"?\s*$', fm, re.M)
        if not am:
            continue
        byline = am.group(1).strip().strip('"').strip("'")
        if byline.lower() in ("theprint", "theprint contributor", "unknown", "anonymous"):
            continue
        resolved = resolve_via(byline, lookup)
        if not resolved:
            tp_unresolved += 1
            continue
        arr = "[" + ", ".join(quote(r) for r in resolved) + "]"
        new_text = patch_or_set(text, "related_thinkers", arr)
        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            tp_patched += 1
    summary["theprint-mirror"] = {"patched": tp_patched, "unresolved": tp_unresolved}

    for k, v in summary.items():
        print(f"[bylines] {k}: {v}")
    print(f"[bylines] total patched: {sum(v.get('patched', 0) for v in summary.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
