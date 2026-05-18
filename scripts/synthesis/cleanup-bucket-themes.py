#!/usr/bin/env python3
"""
Step 0 of the classification pipeline: migrate bucket-label themes on
musings + opinions into a new `source_channel` field, then strip them
from themes[].

Idempotent: skip pieces whose themes[] contains no known bucket labels.

Run:
    .venv-extract/bin/python3 scripts/synthesis/cleanup-bucket-themes.py
    .venv-extract/bin/python3 scripts/synthesis/cleanup-bucket-themes.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/cleanup-bucket-themes.py --test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"

# Mapping: bucket-label theme → source_channel value. First-match wins
# (in declaration order) when a piece carries multiple bucket labels.
BUCKET_MAP: list[tuple[str, str]] = [
    ("so-musings", "so-musings"),
    ("forum-of-free-enterprise-periodicals", "forum-of-free-enterprise"),
    ("indian-libertarian-periodicals", "indian-libertarian"),
    ("indian-liberal-group-periodicals", "indian-liberal-group"),
    ("marathi-articles", "marathi-articles"),
    ("lectures", "lectures"),
    ("events", "editorial-events"),
    ("opinions", "editorial-opinions"),
]
BUCKET_LABELS = {b for b, _ in BUCKET_MAP}

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_THEMES_BLOCK_RX = re.compile(
    # NOTE: inner pattern matches whole lines (`-[^\n]+`) rather than the
    # narrower `-\s*"..."` form, because the latter combined with trailing
    # `\s*` inside the repeat group consumed the newline the next iteration
    # needed, capturing only the first list item. The per-line parser below
    # extracts the quoted value from each captured line.
    r"^themes:\s*(\[\]|(?:\n[ \t]+-[^\n]+)+)\n?",
    re.M,
)


def parse_themes(fm: str) -> list[str]:
    m = _THEMES_BLOCK_RX.search(fm)
    if not m:
        return []
    body = m.group(1).strip()
    if body == "[]":
        return []
    out: list[str] = []
    for line in body.splitlines():
        sub = re.match(r"\s*-\s*\"([^\"]+)\"", line)
        if sub:
            out.append(sub.group(1))
    return out


def emit_themes_block(themes: list[str]) -> str:
    if not themes:
        return "themes: []"
    lines = ["themes:"]
    for t in themes:
        lines.append(f'  - "{t}"')
    return "\n".join(lines)


def process_one(path: Path, dry_run: bool) -> str:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return "skip-no-frontmatter"
    fm, body = m.group(1), m.group(2)
    themes = parse_themes(fm)
    if not themes:
        return "skip-empty-themes"

    has_bucket = any(t in BUCKET_LABELS for t in themes)
    if not has_bucket:
        return "skip-no-bucket"

    new_themes: list[str] = []
    source_channel: str | None = None
    for t in themes:
        if t in BUCKET_LABELS:
            if source_channel is None:
                # first-match wins in BUCKET_MAP declaration order
                for bucket, sc in BUCKET_MAP:
                    if bucket == t:
                        source_channel = sc
                        break
        else:
            new_themes.append(t)

    # Replace the themes block
    new_themes_block = emit_themes_block(new_themes)
    new_fm = _THEMES_BLOCK_RX.sub(new_themes_block + "\n", fm)

    # Insert/replace source_channel line: keep idempotent
    if re.search(r"^source_channel:\s*\".*\"\s*$", new_fm, re.M):
        new_fm = re.sub(
            r"^source_channel:\s*\".*\"\s*$",
            f'source_channel: "{source_channel}"',
            new_fm,
            count=1,
            flags=re.M,
        )
    else:
        if not new_fm.endswith("\n"):
            new_fm += "\n"
        new_fm += f'source_channel: "{source_channel}"\n'

    new_text = f"---\n{new_fm}---\n{body}"
    if dry_run:
        return "would-update"
    path.write_text(new_text, encoding="utf-8")
    return "updated"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        _run_tests()
        return 0

    summary: dict[str, int] = {}
    for collection in ("musings", "opinions"):
        coll_dir = CONTENT_ROOT / collection
        for md in sorted(coll_dir.glob("*.md")):
            result = process_one(md, args.dry_run)
            summary[result] = summary.get(result, 0) + 1
    for k in sorted(summary):
        print(f"  {summary[k]:4d}  {k}")
    return 0


def _run_tests():
    import tempfile

    sample = """---
id: "test"
title: "Test Piece"
pubDate: "2024-06-10T14:38:49Z"
themes:
  - "so-musings"
  - "economic-policy"
language: "en"
needs_review: true
draft: false
---

Body text here.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample)
        result = process_one(p, dry_run=False)
        assert result == "updated", result
        new = p.read_text()
        assert 'source_channel: "so-musings"' in new
        assert '"so-musings"' not in new.split("themes:")[1].split("language:")[0]
        assert '"economic-policy"' in new

        # Re-run should be idempotent
        result2 = process_one(p, dry_run=False)
        assert result2 == "skip-no-bucket", result2

    # All-bucket → empty themes[]
    sample2 = """---
id: "test-2"
title: "Test"
themes:
  - "opinions"
language: "en"
draft: false
---

Body.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample2)
        result = process_one(p, dry_run=False)
        assert result == "updated"
        new = p.read_text()
        assert "themes: []" in new
        assert 'source_channel: "editorial-opinions"' in new

    # No themes at all → skip
    sample3 = """---
id: "test-3"
themes: []
---

Body.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample3)
        result = process_one(p, dry_run=False)
        assert result == "skip-empty-themes", result

    print("cleanup-bucket-themes tests passed.")


if __name__ == "__main__":
    sys.exit(main())
