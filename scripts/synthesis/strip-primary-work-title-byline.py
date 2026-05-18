#!/usr/bin/env python3
"""
Strip duplicate `# <Title>` and `*By <Author>*` lines from the head of
primary-work bodies.

The legacy ingestion pass wrote each markdown body with a heading +
byline that the page template ALSO renders from frontmatter. Result:
duplicate title + duplicate byline visible on every detail page.

This script removes those leading body lines:
  - the first non-blank `# <something>` line (a single H1)
  - the next non-blank `*By <something>*` line that follows it

It does NOT touch the `## Summary` heading or anything below — only the
top-of-body title/byline pair. Idempotent.

Run:
    .venv-extract/bin/python3 scripts/synthesis/strip-primary-work-title-byline.py
    .venv-extract/bin/python3 scripts/synthesis/strip-primary-work-title-byline.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/strip-primary-work-title-byline.py --test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "apps/site/src/content/primary-works"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_H1_RX = re.compile(r"^#\s+\S.*$")
_BYLINE_RX = re.compile(r"^\*By\s+.+\*\s*$")


def process_one(path: Path, dry_run: bool) -> str:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return "skip-no-frontmatter"
    fm, body = m.group(1), m.group(2)
    lines = body.split("\n")

    # Walk to first non-blank
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines):
        return "skip-empty-body"

    # Is first non-blank line an H1?
    if not _H1_RX.match(lines[i]):
        return "skip-no-h1"
    h1_idx = i

    # Find next non-blank line — is it a byline?
    j = h1_idx + 1
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    has_byline = j < len(lines) and _BYLINE_RX.match(lines[j].strip())
    byline_idx = j if has_byline else None

    # Build the new body: drop the H1 line and (if present) the byline line.
    # Collapse the now-orphan blank rows above and between.
    drop = {h1_idx}
    if byline_idx is not None:
        drop.add(byline_idx)
    new_lines = [l for k, l in enumerate(lines) if k not in drop]

    # Trim leading blank lines
    while new_lines and new_lines[0].strip() == "":
        new_lines.pop(0)
    # Collapse 3+ consecutive blanks to 2
    out_lines: list[str] = []
    blank_run = 0
    for l in new_lines:
        if l.strip() == "":
            blank_run += 1
            if blank_run > 2:
                continue
        else:
            blank_run = 0
        out_lines.append(l)

    new_body = "\n".join(out_lines).rstrip() + "\n"
    new_text = f"---\n{fm}\n---\n{new_body}"
    if new_text == text:
        return "skip-no-change"
    if dry_run:
        return "would-strip-byline" if has_byline else "would-strip-h1-only"
    path.write_text(new_text, encoding="utf-8")
    return "stripped-byline" if has_byline else "stripped-h1-only"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0
    summary: dict[str, int] = {}
    for md in sorted(CONTENT_DIR.glob("*.md")):
        r = process_one(md, args.dry_run)
        summary[r] = summary.get(r, 0) + 1
    for k in sorted(summary):
        print(f"  {summary[k]:5d}  {k}")
    return 0


def _run_tests():
    import tempfile

    # Happy path: H1 + byline
    sample = """---
title:
  main: "Test Book"
---

# Test Book

*By Author Name*

## Summary

Body content here.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample)
        assert process_one(p, False) == "stripped-byline"
        out = p.read_text()
        assert "# Test Book" not in out
        assert "*By Author Name*" not in out
        assert "## Summary" in out
        assert "Body content here." in out
        # Idempotent
        assert process_one(p, False) == "skip-no-h1"

    # H1 only (no byline)
    sample2 = """---
title: x
---

# Just A Title

Body
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample2)
        assert process_one(p, False) == "stripped-h1-only"
        assert "# Just A Title" not in p.read_text()

    # No H1 — leave alone
    sample3 = """---
title: x
---

Body without heading.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample3)
        assert process_one(p, False) == "skip-no-h1"

    # H1 then non-byline content — strip H1 only
    sample4 = """---
title: x
---

# Title

This is regular prose, not a byline.

## Summary

stuff
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample4)
        assert process_one(p, False) == "stripped-h1-only"
        out = p.read_text()
        assert "This is regular prose" in out
        assert "## Summary" in out

    # H1 with Indic script
    sample5 = """---
title:
  main: बळीचे राज्य येणार आहे
---

# बळीचे राज्य येणार आहे

*By Sharad Joshi*

## Summary
content
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample5)
        assert process_one(p, False) == "stripped-byline"
        out = p.read_text()
        assert "# बळीचे" not in out
        assert "*By Sharad Joshi*" not in out

    print("strip-primary-work-title-byline tests passed.")


if __name__ == "__main__":
    sys.exit(main())
