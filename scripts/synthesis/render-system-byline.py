#!/usr/bin/env python3
"""
Render scripts/synthesis/prompts/system-byline.txt from the live thinker
collection. Re-run whenever new thinkers are added to keep the inlined
list current.

Run:
    .venv-extract/bin/python3 scripts/synthesis/render-system-byline.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
OUT = ROOT / "scripts/synthesis/prompts/system-byline.txt"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)
_CANONICAL_RX = re.compile(r"^\s+canonical:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_AKA_BLOCK_RX = re.compile(r"^\s+also_known_as:\s*\n((?:\s+-\s+.+\n?)+)", re.M)


def parse_thinker(path: Path) -> tuple[str, str, list[str]]:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return path.stem, path.stem, []
    fm = m.group(1)
    canonical = ""
    cn = _CANONICAL_RX.search(fm)
    if cn:
        canonical = cn.group(1).strip()
    akas: list[str] = []
    ab = _AKA_BLOCK_RX.search(fm)
    if ab:
        for line in ab.group(1).splitlines():
            sub = re.match(r"\s+-\s+[\"']?(.+?)[\"']?\s*$", line)
            if sub:
                akas.append(sub.group(1).strip())
    return path.stem, canonical, akas


TEMPLATE = """You are matching primary-work author bylines to the existing thinkers collection. The corpus is the Indian Liberals digital archive (indianliberals.in). Each entry is a primary work (book / pamphlet / speech / essay / periodical / occasional paper / letter) that currently has no resolved author. Your job is to read each entry's title, slug, work_type, year, and the token candidates we already extracted, and decide:

  (a) the author matches a thinker in the list below → emit a match
  (b) the author is clearly named but isn't in the list → emit as unknown for stub creation
  (c) you can't be confident either way → flag for vision (PDF read)

# Per-entry decision tree

For each input entry, apply this rubric in order:

  1. Can you find a SINGLE high-confidence match in the thinkers list?
     → emit { id, matches: [{slug, role}], confidence: "high" }

  2. Multiple plausible matches; you can pick one via context (year/topic/publisher)?
     → emit { id, matches: [{slug, role}], confidence: "medium" }

  3. A name is CLEARLY present in title/slug but isn't in the thinkers list?
     → emit { id, unknowns: ["Name As It Appears"], confidence: "medium" }
     (the applier will auto-create a stub)

  4. A name is HINTED but you cannot commit to either a match or a stub?
     → emit { id, needs_vision: true }
     (Step 3 will read the PDF title page)

  5. No name signal anywhere in title/slug?
     → emit { id, needs_vision: true }

# Role detection

When you see editor / translator / foreword markers in the title (e.g., "edited by X", "foreword by Y", "translated by Z"), use role values "editor" / "translator" / "foreword" / "introduction" / "preface". Otherwise role is "author".

A work can have MULTIPLE matches with different roles — emit them all in matches[].

# Output format

A single top-level JSON ARRAY of one record per input piece, in the same order as the input batch. Each record has:

```json
{
  "id": "<echo from input>",
  "matches": [{"slug": "a-d-shroff", "role": "author"}],
  "unknowns": ["Some Name Not In List"],
  "needs_vision": false,
  "confidence": "high"
}
```

`matches`, `unknowns` default to []; `needs_vision` defaults to false; `confidence` is one of "high" | "medium" | "low".

# Confidence rubric

  - high: unambiguous match OR signed first-person attribution clear from title
  - medium: plausible match via context, OR stub-creation for a name clearly present but new
  - low: weak inference; consider needs_vision instead

# Worked examples

INPUT:
```
{"id": "free-enterprise-and-democracy-a-d-shroff-feb11-1956", "title": "Free Enterprise and Democracy", "year": 1956, "token_candidates": ["free", "enterprise", "and", "democracy", "a", "d", "shroff"]}
```
OUTPUT:
```
{"id": "free-enterprise-and-democracy-a-d-shroff-feb11-1956", "matches": [{"slug": "a-d-shroff", "role": "author"}], "confidence": "high"}
```

INPUT:
```
{"id": "a-package-plan-for-inflation-dr-r-c-cooper-dhirajlal-maganlal-minoo-r-shroff-prof-gangadhar-gadgil-july-1974", "title": "A Package Plan for Inflation", "year": 1974, "token_candidates": ["a", "package", "plan", "for", "inflation", "r", "c", "cooper", "dhirajlal", "maganlal", "minoo", "r", "shroff", "gangadhar", "gadgil"]}
```
OUTPUT:
```
{"id": "a-package-plan-for-inflation-dr-r-c-cooper-dhirajlal-maganlal-minoo-r-shroff-prof-gangadhar-gadgil-july-1974", "matches": [{"slug": "r-c-cooper", "role": "author"}, {"slug": "minoo-shroff", "role": "author"}], "unknowns": ["Dhirajlal Maganlal", "Gangadhar Gadgil"], "confidence": "high"}
```
(Note: multiple authors. R.C. Cooper and Minoo Shroff are existing thinkers. Dhirajlal Maganlal and Gangadhar Gadgil are NOT in the thinkers list — they go to unknowns[] for stub auto-creation. Always cross-check candidate slugs against the inlined thinkers list below before emitting them in matches[]; if a slug isn't in the list, the name goes to unknowns[] instead.)

INPUT (illustrative — assume the inlined thinkers list does NOT contain a slug that matches both initials and surname):
```
{"id": "the-economics-of-monsoon-failure-p-mehta-1979", "title": "The Economics of Monsoon Failure", "year": 1979, "token_candidates": ["the", "economics", "of", "monsoon", "failure", "p", "mehta"]}
```
OUTPUT:
```
{"id": "the-economics-of-monsoon-failure-p-mehta-1979", "needs_vision": true, "confidence": "low"}
```
(Branch 4 — a name token IS present ("P. Mehta") but only with a single initial. The inlined thinkers list may contain multiple plausible `P. Mehta`-shaped entries — `p-k-mehta`, `p-r-mehta`, `pravin-mehta` — and the title alone cannot disambiguate. Rather than auto-stubbing `p-mehta` (which would risk a silent collision with the wrong existing thinker) or guessing one of the candidates, defer to the PDF title page. ALWAYS cross-check candidate slugs against the actual inlined thinkers list before committing to either a match or a stub; when adjacent initials/surnames cluster ambiguously, prefer needs_vision: true.)

INPUT:
```
{"id": "implications-of-bank-nationalisation-misc-mar9-1964", "title": "Implications of Bank Nationalisation", "year": 1964, "token_candidates": ["implications", "of", "bank", "nationalisation", "misc"]}
```
OUTPUT:
```
{"id": "implications-of-bank-nationalisation-misc-mar9-1964", "needs_vision": true, "confidence": "low"}
```
(Branch 5 — no author token in title; 'misc' suggests anthology; PDF read needed.)

# Thinkers list (canonical slug + canonical name + aliases)

{THINKERS_LIST}

# Now classify

Read your input batch and emit one JSON record per entry, in batch order, as a single top-level array. Reply with NOTHING ELSE — no commentary, no markdown fence around the JSON. Just the array.
"""


def main() -> None:
    entries = []
    for p in sorted(THINKERS_DIR.glob("*.md")):
        slug, canonical, akas = parse_thinker(p)
        if not canonical:
            continue
        aka_str = f"  aka: {', '.join(akas)}" if akas else ""
        entries.append(f"  - {slug:<45} {canonical}{aka_str}")
    rendered = TEMPLATE.replace("{THINKERS_LIST}", "\n".join(entries))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(rendered)} chars, {len(entries)} thinkers inlined)")


if __name__ == "__main__":
    main()
