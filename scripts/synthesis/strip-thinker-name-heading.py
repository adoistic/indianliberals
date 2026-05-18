#!/usr/bin/env python3
"""
Strip the leading `# <Name>` heading from thinker bio bodies.

Many imported thinker MD files have a body that consists of just one
heading line — the thinker's name. The bio page already renders the
canonical name in the page header, so this duplicates the name on
screen (visible as "Charan Singh" appearing twice on /thinkers/charan-singh/).

Heuristic:
  - Locate the frontmatter close (`^---$` line #2).
  - Walk the first non-blank body line. If it is `# <text>` AND the text
    case-insensitively matches the canonical name (or full name, or any
    also_known_as alias), strip it.
  - Idempotent: re-running is a no-op if no leading H1 remains.

Run:
    .venv-extract/bin/python3 scripts/synthesis/strip-thinker-name-heading.py
    .venv-extract/bin/python3 scripts/synthesis/strip-thinker-name-heading.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/strip-thinker-name-heading.py --test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "apps/site/src/content/thinkers"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_CANONICAL_RX = re.compile(r"^\s+canonical:\s*(.+?)\s*$", re.M)
_FULL_RX = re.compile(r"^\s+full:\s*(.+?)\s*$", re.M)
_AKA_BLOCK_RX = re.compile(r"^\s+also_known_as:\s*\n((?:\s+-\s+.+\n?)+)", re.M)


def parse_name_aliases(fm: str) -> set[str]:
    """Collect every name string under `name:` for matching."""
    names: set[str] = set()
    m = _CANONICAL_RX.search(fm)
    if m:
        names.add(m.group(1).strip().strip('"'))
    m = _FULL_RX.search(fm)
    if m:
        names.add(m.group(1).strip().strip('"'))
    m = _AKA_BLOCK_RX.search(fm)
    if m:
        for line in m.group(1).splitlines():
            sub = re.match(r"\s+-\s+(.+?)\s*$", line)
            if sub:
                names.add(sub.group(1).strip().strip('"'))
    return {n for n in names if n}


def process_one(path: Path, dry_run: bool) -> str:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return "skip-no-frontmatter"
    fm, body = m.group(1), m.group(2)
    names = parse_name_aliases(fm)
    if not names:
        return "skip-no-names"

    # Find the first non-blank line of the body
    lines = body.split("\n")
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx >= len(lines):
        return "skip-empty-body"

    first = lines[idx].rstrip()
    h1 = re.match(r"^#\s+(.+?)\s*$", first)
    if not h1:
        return "skip-no-h1"
    candidate = h1.group(1)

    # Match against any name (case-insensitive, also tolerant to leading/trailing whitespace)
    if candidate.lower() not in {n.lower() for n in names}:
        return "skip-h1-not-name"

    # Strip the line + the blank line(s) immediately above and below it
    new_lines = lines[:idx] + lines[idx + 1 :]
    # Trim leading blank lines so the body doesn't start with a wall of whitespace
    while new_lines and new_lines[0].strip() == "":
        new_lines.pop(0)
    new_body = "\n".join(new_lines)
    if not new_body.endswith("\n"):
        new_body += "\n"
    new_text = f"---\n{fm}\n---\n{new_body}"
    if dry_run:
        return "would-strip"
    path.write_text(new_text, encoding="utf-8")
    return "stripped"


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
        print(f"  {summary[k]:4d}  {k}")
    return 0


def _run_tests():
    import tempfile

    sample = """---
id: "test"
name:
  canonical: Test Person
  full: Test Full Person
  also_known_as:
    - Testy P.
---

# Test Person

Some other content here.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample)
        assert process_one(p, dry_run=False) == "stripped"
        out = p.read_text()
        assert "# Test Person" not in out
        assert "Some other content here." in out
        # idempotent
        assert process_one(p, dry_run=False) == "skip-no-h1"

    # H1 doesn't match name → leave alone
    sample2 = """---
name:
  canonical: Alice
---

# Bob

text
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample2)
        assert process_one(p, dry_run=False) == "skip-h1-not-name"
        assert "# Bob" in p.read_text()

    # No H1 at all → leave alone
    sample3 = """---
name:
  canonical: Carol
---

Just a paragraph.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample3)
        assert process_one(p, dry_run=False) == "skip-no-h1"
        assert "Just a paragraph." in p.read_text()

    # Empty body — body has only the heading, nothing else
    sample4 = """---
name:
  canonical: Dan
---

# Dan
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample4)
        assert process_one(p, dry_run=False) == "stripped"
        out = p.read_text()
        assert "# Dan" not in out

    # Also_known_as alias matches
    sample5 = """---
name:
  canonical: Eric
  also_known_as:
    - Eric the Great
---

# Eric the Great

body
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample5)
        assert process_one(p, dry_run=False) == "stripped"
        assert "# Eric the Great" not in p.read_text()

    print("strip-thinker-name-heading tests passed.")


if __name__ == "__main__":
    sys.exit(main())
