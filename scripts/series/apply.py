#!/usr/bin/env python3
"""Backfill publication.series_id / series_ordinal onto primary-works records,
and repair the colophon dates that the v1.4 extractor mistook for series names.

Line-surgical rather than a YAML round-trip: rewriting the frontmatter through
yaml.dump would reflow all 1,586 records and bury the real change in noise.

Usage:  apply.py            # dry run, prints a diff summary
        apply.py --write    # apply
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PW = os.path.join(ROOT, "apps", "site", "src", "content", "primary-works")
HERE = os.path.dirname(os.path.abspath(__file__))

# The extractor read the printer's colophon line ("9/August/1962") as a series
# designation. It is a date, not a series: the run is unnumbered. Clear the
# field but keep the transcription in provenance.notes so nothing is lost.
COLOPHON_RX = re.compile(r"^\s*(ffe\s+booklet\s*)?[\d.]+\s*/|/\d{4}/\d+\s*$", re.I)


def split_frontmatter(text: str):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    return text[4:end + 1], text[end + 5:]


def block_bounds(lines: list[str], key: str):
    """Return (start, end) line indices of a top-level mapping's child block."""
    for i, ln in enumerate(lines):
        if ln.rstrip() == f"{key}:" or ln.startswith(f"{key}: "):
            j = i + 1
            while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
                j += 1
            return i, j
    return None


def main() -> int:
    write = "--write" in sys.argv
    assignments = {a["file"]: a for a in json.load(open(os.path.join(HERE, "assignments.json")))["final"]}
    stats = {"series_id": 0, "ordinal": 0, "colophon_cleared": 0, "skipped_no_publication": 0}
    touched = []

    for fn in sorted(os.listdir(PW)):
        if not fn.endswith((".md", ".mdx")):
            continue
        path = os.path.join(PW, fn)
        text = open(path, encoding="utf-8").read()
        parts = split_frontmatter(text)
        if not parts:
            continue
        fmtext, body = parts
        lines = fmtext.splitlines(keepends=True)
        changed = False

        pub = block_bounds(lines, "publication")
        if pub is None:
            if fn in assignments:
                stats["skipped_no_publication"] += 1
            continue
        pstart, pend = pub

        # 1. Repair a colophon date sitting in publication.series.
        colophon = None
        for i in range(pstart + 1, pend):
            m = re.match(r"^  series:\s*(.+?)\s*$", lines[i])
            if m:
                val = m.group(1).strip().strip("\"'")
                if COLOPHON_RX.search(val):
                    colophon = val
                    del lines[i]
                    pend -= 1
                    changed = True
                    stats["colophon_cleared"] += 1
                break

        # 2. Attach series membership.
        a = assignments.get(fn)
        if a:
            have = {re.match(r"^  ([A-Za-z_]+):", ln).group(1)
                    for ln in lines[pstart + 1:pend] if re.match(r"^  ([A-Za-z_]+):", ln)}
            ins = []
            if "series_id" not in have:
                ins.append(f"  series_id: {a['series_id']}\n")
                stats["series_id"] += 1
            if a.get("ordinal") and "series_ordinal" not in have:
                ins.append(f"  series_ordinal: {int(a['ordinal'])}\n")
                stats["ordinal"] += 1
            if ins:
                # Place after `series:` when present, else at the end of the block.
                at = pend
                for i in range(pstart + 1, pend):
                    if lines[i].startswith("  series:"):
                        at = i + 1
                        break
                lines[at:at] = ins
                pend += len(ins)
                changed = True

        # 3. Park the colophon transcription in provenance.notes.
        if colophon:
            prov = block_bounds(lines, "provenance")
            note = (f'  notes: "Colophon date as printed: {colophon}. '
                    f'(Recorded as publication.series by the v1.4 extractor; '
                    f'it is a printing date, not a series designation.)"\n')
            if prov:
                s, e = prov
                if not any(ln.startswith("  notes:") for ln in lines[s + 1:e]):
                    lines[e:e] = [note]
            else:
                lines.append("provenance:\n")
                lines.append(note)

        if changed:
            open(path, "w", encoding="utf-8").write("---\n" + "".join(lines) + "---\n" + body) if write else None
            touched.append(fn)

    print(("APPLIED" if write else "DRY RUN") + f" — records touched: {len(touched)}")
    for k, v in stats.items():
        print(f"   {k:26} {v}")
    unmatched = set(assignments) - set(touched)
    if unmatched:
        print(f"   assignments not applied: {len(unmatched)} (already had series_id?)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
