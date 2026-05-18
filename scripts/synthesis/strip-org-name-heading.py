#!/usr/bin/env python3
"""
Strip the leading `# <Name>` heading from organisation bodies, when it
duplicates the canonical name already rendered in the page header.

Mirror of strip-thinker-name-heading.py — same shape, different
frontmatter layout. Organisations have `name: { canonical, sort,
also_known_as? }`.

Run:
    .venv-extract/bin/python3 scripts/synthesis/strip-org-name-heading.py
    .venv-extract/bin/python3 scripts/synthesis/strip-org-name-heading.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/strip-org-name-heading.py --test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "apps/site/src/content/organisations"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_CANONICAL_RX = re.compile(r"^\s+canonical:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_SORT_RX = re.compile(r"^\s+sort:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_AKA_BLOCK_RX = re.compile(r"^\s+also_known_as:\s*\n((?:\s+-\s+.+\n?)+)", re.M)


def parse_name_aliases(fm: str) -> set[str]:
    names: set[str] = set()
    m = _CANONICAL_RX.search(fm)
    if m:
        names.add(m.group(1).strip().strip('"').strip("'"))
    m = _SORT_RX.search(fm)
    if m:
        names.add(m.group(1).strip().strip('"').strip("'"))
    m = _AKA_BLOCK_RX.search(fm)
    if m:
        for line in m.group(1).splitlines():
            sub = re.match(r"\s+-\s+(.+?)\s*$", line)
            if sub:
                names.add(sub.group(1).strip().strip('"').strip("'"))
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

    if candidate.lower() not in {n.lower() for n in names}:
        return "skip-h1-not-name"

    new_lines = lines[:idx] + lines[idx + 1 :]
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

    # Happy path: canonical matches
    sample = """---
id: org
name:
  canonical: "Bharathan Publications"
  sort: "Bharathan Publications"
type: publisher_org
---

# Bharathan Publications
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample)
        assert process_one(p, False) == "stripped"
        out = p.read_text()
        assert "# Bharathan Publications" not in out
        # Idempotent
        assert process_one(p, False) == "skip-no-h1" or process_one(p, False) == "skip-empty-body"

    # H1 doesn't match canonical → leave alone
    sample2 = """---
name:
  canonical: "ABC Press"
---

# Other Heading

body
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample2)
        assert process_one(p, False) == "skip-h1-not-name"
        assert "# Other Heading" in p.read_text()

    # Match via also_known_as alias
    sample3 = """---
name:
  canonical: "CCS"
  also_known_as:
    - "Centre for Civil Society"
---

# Centre for Civil Society

mission
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.md"
        p.write_text(sample3)
        assert process_one(p, False) == "stripped"
        out = p.read_text()
        assert "# Centre for Civil Society" not in out
        assert "mission" in out

    print("strip-org-name-heading tests passed.")


if __name__ == "__main__":
    sys.exit(main())
