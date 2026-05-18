#!/usr/bin/env python3
"""
Phase B coverage audit. Reports:
  - % of in-scope English entries with ≥1 thinker_mentions[] record
  - average mentions per entry
  - touchstone thinker coverage (live mentions vs expected baseline)
  - count of entries with zero matches

Per supplementary spec §6. Run after apply-ner.py lands.

Touchstone counts are advisory, not blocking — LO flags surface where the
corpus contains fewer mentions of a thinker than expected, usually because
that thinker is genuinely less written about in this archive. Only
investigate if a touchstone returns 0 mentions when ≥5 was expected.

Run:
    python3 scripts/synthesis/audit-ner-coverage.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
IN_SCOPE = ("musings", "opinions", "theprint-mirror", "primary-works")
TOUCHSTONES = [
    ("a-d-shroff", 50),
    ("jawaharlal-nehru", 40),
    ("mahatma-gandhi", 20),
    ("friedrich-hayek", 5),
    ("adam-smith", 5),
    ("karl-marx", 5),
    ("nani-palkhivala", 15),
    ("minoo-masani", 15),
    ("b-r-shenoy", 10),
    ("jagdish-bhagwati", 10),
]

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)
_THINKER_RX = re.compile(r"-\s+thinker:\s*(?:\"([^\"]+)\"|(\S+))", re.M)


def count_mentions(text: str) -> tuple[int, list[str]]:
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return 0, []
    fm = m.group(1)
    # Find the thinker_mentions: block
    tm_block_match = re.search(
        r"^thinker_mentions:\s*(?:\[\]|((?:\n[ \t]+.*)+))", fm, re.M,
    )
    if not tm_block_match or not tm_block_match.group(1):
        return 0, []
    block = tm_block_match.group(1)
    slugs = [m[0] or m[1] for m in _THINKER_RX.findall(block)]
    return len(slugs), slugs


def main() -> int:
    per_collection: dict[str, dict] = {c: {"total": 0, "with_mentions": 0, "total_mentions": 0} for c in IN_SCOPE}
    touchstone_counts: Counter = Counter()
    zero_match_examples: list[str] = []

    for collection in IN_SCOPE:
        cdir = CONTENT_ROOT / collection
        for p in sorted(cdir.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            # Language filter (mirror prepare-ner-batches.py)
            fm_match = _FRONTMATTER_RX.match(text)
            if not fm_match:
                continue
            fm = fm_match.group(1)
            lang_match = re.search(r"^language:\s*\"?([a-z]+)\"?", fm, re.M)
            if lang_match and lang_match.group(1) != "en":
                continue
            per_collection[collection]["total"] += 1
            n, slugs = count_mentions(text)
            if n > 0:
                per_collection[collection]["with_mentions"] += 1
                per_collection[collection]["total_mentions"] += n
                for s in slugs:
                    touchstone_counts[s] += 1
            else:
                if len(zero_match_examples) < 20:
                    zero_match_examples.append(f"{collection}/{p.stem}")

    print("\n=== Phase B coverage audit ===\n")
    for c in IN_SCOPE:
        d = per_collection[c]
        if d["total"]:
            pct = 100.0 * d["with_mentions"] / d["total"]
            avg = d["total_mentions"] / max(d["with_mentions"], 1)
            print(f"  {c:<18s} {d['with_mentions']:4d} / {d['total']:4d}  ({pct:5.1f}%)  avg mentions/entry: {avg:.1f}")

    print(f"\n=== Touchstone coverage ===\n")
    for slug, expected in TOUCHSTONES:
        live = touchstone_counts.get(slug, 0)
        flag = "OK " if live >= expected else "LO "
        print(f"  [{flag}] {slug:<25s} live: {live:3d}  expected: ≥{expected}")

    print(f"\n=== Sample zero-match entries (first 20) ===\n")
    for e in zero_match_examples:
        print(f"  {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
