#!/usr/bin/env python3
"""Set provenance.notes + scan_quality on a work, without breaking the build.

Hand-writing this note broke qt041.md: the defect description quoted the cover
line 'THE "PRINCE" OF THE INDIAN RENAISSANCE', and unescaped double quotes
inside a double-quoted YAML scalar make the frontmatter unparseable. A single
bad frontmatter save stops EVERY Cloudflare deploy for the whole site, so the
note is now written through yaml.safe_dump and read back before the file is
saved. carry_scan_defects.py sidestepped this by replacing every double quote
with a single one; that silently altered quoted matter, which is worse for an
archive that promises verbatim transcription.

Severity follows the same rule as carry_scan_defects.py: a defect that breaks
reading order is "poor", a localised one is "fair".

Usage: set_provenance_note.py <slug> "<note text>"
       set_provenance_note.py --verify              # parse every Quest work
"""
import re, sys
from pathlib import Path

import yaml

WORKS = Path("/Users/siraj/Indian Liberals Website/apps/site/src/content/primary-works")
FM = re.compile(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$")
SEVERE = re.compile(r"out of sequence|out of order|mis-?bound|misbind|scanned out|"
                    r"missing page|missing lea|duplicate(d)? (page|lea)|"
                    r"relocat(ed|ion)|reading order is wrong|"
                    r"illegible|unreadable", re.I)
# A severity word inside a NEGATED clause means the opposite. This grader had
# no such guard and read "Nothing in the issue is illegible" as grounds for
# grading QT047 "poor" - the same mistake carry_scan_defects.py made once with
# "No leaves appear bound out of sequence".
NEG = re.compile(r"\b(no|not|none|nothing|never|without|free of|did not|does not|"
                 r"weren't|wasn't|isn't|aren't)\b", re.I)


def severity(note: str) -> str:
    """poor when the defect breaks reading order, fair when it is localised."""
    for sentence in re.split(r"(?<=[.;])\s+", note):
        m = SEVERE.search(sentence)
        if m and not NEG.search(sentence[:m.start()]):
            return "poor"
    return "fair"


def frontmatter(p: Path):
    m = FM.match(p.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"{p.name}: no frontmatter")
    return m.group(1), m.group(2)


def verify() -> int:
    bad = 0
    for p in sorted(WORKS.glob("qt[0-9][0-9][0-9].md")):
        try:
            fm, _ = frontmatter(p)
            yaml.safe_load(fm)
        except Exception as e:                       # noqa: BLE001
            print(f"BROKEN {p.name}: {type(e).__name__}: {str(e).splitlines()[0]}")
            bad += 1
    print(f"checked {len(list(WORKS.glob('qt[0-9][0-9][0-9].md')))} Quest works, {bad} broken")
    return 1 if bad else 0


def main() -> int:
    if "--verify" in sys.argv:
        return verify()
    if len(sys.argv) != 3:
        print(__doc__); return 2
    slug, note = sys.argv[1].lower(), sys.argv[2]
    p = WORKS / f"{slug}.md"
    raw, body = frontmatter(p)
    doc = yaml.safe_load(raw)
    prov = doc.setdefault("provenance", {})
    prov["notes"] = note
    prov["scan_quality"] = severity(note)
    out = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False,
                         default_flow_style=False, width=100000)
    text = f"---\n{out}---\n{body}"
    yaml.safe_load(FM.match(text).group(1))          # parse before writing
    p.write_text(text, encoding="utf-8")
    print(f"{slug}: scan_quality={prov['scan_quality']}, note set and re-parsed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
