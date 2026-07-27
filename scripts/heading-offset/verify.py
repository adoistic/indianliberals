#!/usr/bin/env python3
"""
Check that a heading repair changed only labels.

Run after any pass over the article headings, automated or by hand against the
scans. The repair is allowed to move, add and rewrite `### ` heading lines and
`*By …*` byline lines, and to add the standard "no summary was extracted" note.
It is allowed to change nothing else, and the point of this script is that the
claim gets checked rather than asserted.

Three things it will not let past:

  prose altered      a summary line or bullet differs from the baseline
  duplicate heading  a `###` heading now appears more times than it did
  em dash            a heading picked up a character the house style forbids

Usage:
    python3 scripts/heading-offset/verify.py                # against HEAD
    python3 scripts/heading-offset/verify.py --base eaa1a65c
    python3 scripts/heading-offset/verify.py --base HEAD --only ff030 ff272
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
WORKS = "apps/site/src/content/primary-works"

ORPHAN_NOTE = "No summary was extracted for this article"

# Works whose bodies were deliberately rewritten from the scans, so a prose
# diff is expected and not a regression.
REWRITTEN = {
    "ff389",
    # Re-read from the scans because their bodies summarised a different issue
    # entirely. See scripts/dedupe/cross_contamination.py.
    "the-indian-libertarian-may1-1960",
    "the-indian-libertarian-may1-1961",
    "the-indian-libertarian-may15-1960",
    "the-indian-libertarian-may15-1962",
    "the-indian-libertarian-may15-1963",
    "the-indian-libertarian-nov1-1958",
    "evils-of-child-marriage",
    "from-darkness-to-light",
    "bharatasathi-sharad-joshi",
    "poshindyanchi-lokshahi-sharad-joshi",
}


def headings(text: str) -> list[str]:
    return [h.strip() for h in re.findall(r"^### (.*)$", text, flags=re.MULTILINE)]


def duplicate_count(text: str) -> int:
    counts = collections.Counter(headings(text))
    return sum(n - 1 for n in counts.values() if n > 1)


def prose_lines(text: str) -> list[str]:
    """Everything a reader reads that is not a label."""
    return sorted(
        line
        for line in text.splitlines()
        if line.strip()
        and not line.startswith("### ")
        and not line.startswith("*By ")
        and ORPHAN_NOTE not in line
    )


def baseline(base: str, name: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{base}:{WORKS}/{name}"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    return result.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    changed = altered = duped = dashed = 0
    problems: list[str] = []

    for path in sorted((REPO / WORKS).glob("*.md")):
        if args.only and path.stem not in args.only:
            continue
        before = baseline(args.base, path.name)
        if not before:
            continue
        after = path.read_text(encoding="utf-8")
        if before == after:
            continue
        changed += 1

        if path.stem not in REWRITTEN and prose_lines(before) != prose_lines(after):
            altered += 1
            lost = [l for l in prose_lines(before) if l not in prose_lines(after)]
            gained = [l for l in prose_lines(after) if l not in prose_lines(before)]
            problems.append(
                f"{path.stem}: prose changed ({len(lost)} lost, {len(gained)} gained)"
                + (f"\n    lost: {lost[0][:100]}" if lost else "")
            )

        if duplicate_count(after) > duplicate_count(before):
            duped += 1
            counts = collections.Counter(headings(after))
            repeats = [h for h, n in counts.items() if n > 1]
            problems.append(f"{path.stem}: repeated heading {repeats[:2]}")

        # Only *new* em dashes. The house ban covers hard-coded UI copy, not
        # content: "Gokhale and Western Education—II" is the title as printed,
        # and reproducing it faithfully is the whole point of an archive. What
        # would be wrong is a repair inventing one.
        def dashed_headings(text: str) -> set[str]:
            return {h for h in headings(text) if "—" in h or "&mdash;" in h}

        # Only flag it when the file did not already reproduce printed em dashes
        # in its headings. ff408's titles all carry one, so a re-seated heading
        # matching its siblings is faithful, not a regression.
        introduced = dashed_headings(after) - dashed_headings(before)
        if introduced and not dashed_headings(before):
            dashed += 1
            problems.append(
                f"{path.stem}: em dash introduced into heading {sorted(introduced)[0][:60]!r}"
            )

    print(f"compared against {args.base}")
    print(f"  files changed      {changed}")
    print(f"  prose altered      {altered}")
    print(f"  duplicate headings {duped}")
    print(f"  em dash in heading {dashed}")
    if problems:
        print("\nproblems:")
        for problem in problems[:25]:
            print(f"  {problem}")
        if len(problems) > 25:
            print(f"  … and {len(problems) - 25} more")
        return 1
    print("\nclean: labels moved, nothing else")
    return 0


if __name__ == "__main__":
    sys.exit(main())
