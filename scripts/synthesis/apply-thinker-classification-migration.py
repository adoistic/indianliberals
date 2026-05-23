#!/usr/bin/env python3
"""
Apply the thinker-classification migration:
  1. Add `canon_status: unclassified` to every thinker MD that doesn't have it
  2. Add `vocations: []` to every thinker MD that doesn't have it
  3. Rename `tradition: nationalist_liberal` → `tradition: constitutional_liberal`
  4. Merge `tradition: reformer` → `tradition: social_reformer`

Strict per-spec YAML serialization:
  - canon_status: unclassified   (no quoting, no comments, no trailing whitespace)
  - vocations: []                (flow-style empty array, NOT block-style)
These exact forms are what the §9.2 acceptance grep checks rely on.

Idempotent. Safe to re-run.

Run from the repo root:
    python3 scripts/synthesis/apply-thinker-classification-migration.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"

# Compiled regexes once
TRADITION_LINE = re.compile(r'^(tradition:\s*)([a-z_]+)\s*$', re.MULTILINE)
CANON_STATUS_PRESENT = re.compile(r'^canon_status:\s*\S+', re.MULTILINE)
VOCATIONS_PRESENT = re.compile(r'^vocations:\s*', re.MULTILINE)


def migrate_one(text: str) -> tuple[str, dict]:
    """Apply the four migration steps to one file's content.
    Returns (new_text, stats_dict).
    """
    stats = {
        'added_canon_status': False,
        'added_vocations': False,
        'renamed_nationalist_liberal': False,
        'merged_reformer': False,
    }

    # Find the tradition line — anchor for inserting new fields right after it
    m = TRADITION_LINE.search(text)
    if not m:
        # No tradition line at all (unexpected for a real thinker MD); skip mutation
        return text, stats

    tradition_value = m.group(2)
    tradition_line_end = m.end()

    # Step 3 + 4: rewrite the tradition value if it matches
    if tradition_value == 'nationalist_liberal':
        text = text[:m.start(2)] + 'constitutional_liberal' + text[m.end(2):]
        stats['renamed_nationalist_liberal'] = True
        # Recompute the line end after substitution (different length)
        m = TRADITION_LINE.search(text)
        tradition_line_end = m.end()
    elif tradition_value == 'reformer':
        text = text[:m.start(2)] + 'social_reformer' + text[m.end(2):]
        stats['merged_reformer'] = True
        m = TRADITION_LINE.search(text)
        tradition_line_end = m.end()

    # Step 1: insert canon_status if absent (immediately after the tradition line)
    if not CANON_STATUS_PRESENT.search(text):
        # tradition_line_end points to the \n at the end of the tradition line
        # or to the position right after the value. We want to insert AFTER the \n.
        # The regex's group(0) ends just before \n; advance to include the \n.
        insertion_point = tradition_line_end
        if insertion_point < len(text) and text[insertion_point] == '\n':
            insertion_point += 1
        text = text[:insertion_point] + 'canon_status: unclassified\n' + text[insertion_point:]
        stats['added_canon_status'] = True

    # Step 2: insert vocations if absent (immediately after canon_status line)
    if not VOCATIONS_PRESENT.search(text):
        canon_m = CANON_STATUS_PRESENT.search(text)
        # canon_m must exist now since we either inserted it or it was already present
        if canon_m:
            # Find the end of the canon_status line
            line_end = text.find('\n', canon_m.end())
            if line_end == -1:
                line_end = len(text)
            else:
                line_end += 1  # include the \n
            text = text[:line_end] + 'vocations: []\n' + text[line_end:]
            stats['added_vocations'] = True

    return text, stats


def main() -> int:
    if not THINKERS_DIR.exists():
        print(f"ERROR: {THINKERS_DIR} does not exist; run from repo root.", file=sys.stderr)
        return 1

    files = sorted(THINKERS_DIR.glob('*.md'))
    if not files:
        print(f"ERROR: no MD files in {THINKERS_DIR}", file=sys.stderr)
        return 1

    totals = {
        'files_processed': 0,
        'files_modified': 0,
        'added_canon_status': 0,
        'added_vocations': 0,
        'renamed_nationalist_liberal': 0,
        'merged_reformer': 0,
    }

    for f in files:
        original = f.read_text(encoding='utf-8')
        new_text, stats = migrate_one(original)
        totals['files_processed'] += 1
        if new_text != original:
            f.write_text(new_text, encoding='utf-8')
            totals['files_modified'] += 1
        for k in ('added_canon_status', 'added_vocations',
                  'renamed_nationalist_liberal', 'merged_reformer'):
            if stats[k]:
                totals[k] += 1

    print(f"files_processed:           {totals['files_processed']}")
    print(f"files_modified:            {totals['files_modified']}")
    print(f"added_canon_status:        {totals['added_canon_status']}")
    print(f"added_vocations:           {totals['added_vocations']}")
    print(f"renamed_nationalist_liberal: {totals['renamed_nationalist_liberal']}")
    print(f"merged_reformer:           {totals['merged_reformer']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
