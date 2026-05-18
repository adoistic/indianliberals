#!/usr/bin/env python3
"""
Step 1: build the canonical themes vocabulary from primary-works
frontmatter.

Two outputs:
  data/themes-vocab-candidates.json — auto-filtered, sorted by frequency
  data/themes-vocab.json            — manually curated lock file
                                       (this script writes only candidates;
                                        the lock file is hand-trimmed)

Filters applied to candidates:
  1. Slug-shape: ^[a-z][a-z0-9-]+$
  2. Thinker-slug filter: drop tokens that match a thinker id

Run:
    .venv-extract/bin/python3 scripts/synthesis/build-themes-vocab.py
    .venv-extract/bin/python3 scripts/synthesis/build-themes-vocab.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW_DIR = ROOT / "apps/site/src/content/primary-works"
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
CANDIDATES_OUT = ROOT / "data/themes-vocab-candidates.json"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)
_THEMES_BLOCK_RX = re.compile(
    # NOTE: inner pattern matches whole lines (`-[^\n]+`) rather than the
    # narrower `-\s*"..."` form, because the latter combined with trailing
    # `\s*` inside the repeat group consumed the newline the next iteration
    # needed, capturing only the first list item. The per-line parser below
    # extracts the quoted value from each captured line.
    r"^themes:\s*(\[\]|(?:\n[ \t]+-[^\n]+)+)",
    re.M,
)
_SLUG_RX = re.compile(r"^[a-z][a-z0-9-]+$")


def extract_themes(md_path: Path) -> list[str]:
    text = md_path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return []
    fm = m.group(1)
    block = _THEMES_BLOCK_RX.search(fm)
    if not block:
        return []
    body = block.group(1).strip()
    if body == "[]":
        return []
    out: list[str] = []
    for line in body.splitlines():
        # Accept both quoted ("- \"foo\"") and bare ("- foo") YAML list items.
        # The corpus uses bare slugs for most themes and quoted strings only
        # for stray thinker-name themes that the shape filter drops later.
        sub = re.match(r"\s*-\s*\"([^\"]+)\"\s*$", line)
        if sub:
            out.append(sub.group(1))
            continue
        sub = re.match(r"\s*-\s*(\S.*?)\s*(?:#.*)?$", line)
        if sub:
            out.append(sub.group(1))
    return out


def thinker_slugs() -> set[str]:
    if not THINKERS_DIR.exists():
        return set()
    return {p.stem for p in THINKERS_DIR.glob("*.md")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    counter: Counter[str] = Counter()
    for md in sorted(PW_DIR.glob("*.md")):
        for t in extract_themes(md):
            counter[t] += 1

    thinkers = thinker_slugs()
    dropped_thinker = []
    dropped_shape = []
    accepted: list[tuple[str, int]] = []

    for theme, n in counter.most_common():
        if not _SLUG_RX.match(theme):
            dropped_shape.append((theme, n))
            continue
        if theme in thinkers:
            dropped_thinker.append((theme, n))
            continue
        accepted.append((theme, n))

    payload = {
        "accepted_candidates": [{"theme": t, "count": n} for t, n in accepted],
        "dropped_shape": [{"theme": t, "count": n} for t, n in dropped_shape],
        "dropped_thinker_slug": [{"theme": t, "count": n} for t, n in dropped_thinker],
        "note": "Manually curate accepted_candidates → data/themes-vocab.json; the latter is the lock file.",
    }
    CANDIDATES_OUT.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_OUT.write_text(json.dumps(payload, indent=2))
    print(f"wrote {CANDIDATES_OUT.relative_to(ROOT)}")
    print(f"  accepted={len(accepted)}  dropped_shape={len(dropped_shape)}  dropped_thinker={len(dropped_thinker)}")
    return 0


def _run_tests():
    # Inline test for slug-shape filter
    assert _SLUG_RX.match("economic-policy")
    assert _SLUG_RX.match("free-enterprise")
    assert not _SLUG_RX.match("Sharad Joshi")
    assert not _SLUG_RX.match("Free Enterprise")
    assert not _SLUG_RX.match("UPPERCASE")
    assert not _SLUG_RX.match("a"), "single-char slug should fail (min 2 chars)"
    print("build-themes-vocab tests passed.")


if __name__ == "__main__":
    sys.exit(main())
