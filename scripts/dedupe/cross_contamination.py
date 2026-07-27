#!/usr/bin/env python3
"""
Find works whose summaries were written from a different work.

This is not the duplicate-PDF problem `scripts/dedupe/` was built for, where the
same scan was ingested twice. This is worse and quieter: two *different* works,
each with its own PDF and its own correct metadata, where one of them carries
the other's summaries. The record looks complete, the citation resolves, and the
content is about a different issue entirely.

Five works had it, all *The Indian Libertarian*, and every one of them has a
"may" slug:

    may1-1960   carried jun15-1960
    may1-1961   carried jun15-1961
    may15-1960  carried may1-1967
    may15-1962  carried may15-1957
    may15-1963  carried may15-1958

The clustering on one publication and one month is why this is worth keeping as
a standing check rather than a one-off script: it looks like a slug collision in
an ingest pass, and a pipeline that did it once to five works can do it again.

Nothing here is heuristic about *whether* two works share text. It compares the
exact prose lines. Judgement only enters in reading the report: a high overlap
between two records of genuinely the same work, published under two slugs, is
expected and fine.

Usage:
    python3 scripts/dedupe/cross_contamination.py
    python3 scripts/dedupe/cross_contamination.py --threshold 0.35
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
CONTENT = REPO / "apps" / "site" / "src" / "content"
WORKS = CONTENT / "primary-works"

# Every collection whose entries carry prose worth comparing. Contamination is
# not a periodicals problem in principle: any pipeline that writes a summary
# from the wrong source can do it to a thinker profile too.
COLLECTIONS = [
    "primary-works",
    "musings",
    "opinions",
    "thinkers",
    "organisations",
    "theprint-mirror",
]

# Short lines collide by chance (bullets like "- Reviews the budget"), so only
# substantial ones count towards an overlap.
MIN_LINE = 60
# Below this many comparable lines a work cannot be judged either way.
MIN_LINES = 6
# A line shared by more than this many works is boilerplate, not evidence.
MAX_SHARERS = 6


def body(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    return text[end + 4 :] if end != -1 else text


def prose_signature(text: str) -> set[str]:
    return {
        hashlib.md5(line.strip().encode()).hexdigest()[:12]
        for line in text.splitlines()
        if len(line.strip()) >= MIN_LINE and not line.startswith(("#", "*By"))
    }


def stated_issue(path: pathlib.Path) -> str | None:
    """The issue a work's own summary claims to describe, if it says so."""
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"^summary:\s*\"?(?:This is )?[Tt]he ([A-Z][a-z]+ \d{1,2},? \d{4}|\d{1,2} [A-Z][a-z]+ \d{4})",
        text,
        flags=re.MULTILINE,
    )
    return match.group(1) if match else None


MONTHS = {m: n for n, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}

SLUG_DATE_RE = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(\d{1,2})?-(\d{4})$")


def slug_date(slug: str) -> tuple[int, int] | None:
    """The (year, month) a periodical slug claims, e.g. …-may15-1960 -> (1960, 5)."""
    match = SLUG_DATE_RE.search(slug)
    if not match:
        return None
    month = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
             "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}[match.group(1)]
    return int(match.group(3)), month


def summary_date(path: pathlib.Path) -> tuple[int, int] | None:
    """The (year, month) the summary text itself names, if any."""
    stated = stated_issue(path)
    if not stated:
        return None
    parts = stated.replace(",", "").split()
    for part in parts:
        if part.lower() in MONTHS:
            month = MONTHS[part.lower()]
            years = [int(p) for p in parts if p.isdigit() and len(p) == 4]
            if years:
                return years[0], month
    return None


def self_inconsistent() -> list[tuple[str, tuple[int, int], tuple[int, int]]]:
    """
    Works whose summary names a different issue from the one their slug claims.

    This catches contamination the pairwise check cannot: if the issue a summary
    was really written from is not itself in the corpus, there is no partner to
    overlap with, and the only evidence is the record contradicting itself.
    """
    out = []
    for path in sorted(WORKS.glob("*.md")):
        claimed = slug_date(path.stem)
        stated = summary_date(path)
        if claimed and stated and claimed != stated:
            out.append((path.stem, claimed, stated))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--collections", nargs="*", default=COLLECTIONS,
                    help="which content collections to compare (default: all with prose)")
    args = ap.parse_args()

    signatures: dict[str, set[str]] = {}
    where: dict[str, str] = {}
    for collection in args.collections:
        folder = CONTENT / collection
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            signature = prose_signature(body(path))
            if len(signature) >= MIN_LINES:
                key = f"{collection}:{path.stem}"
                signatures[key] = signature
                where[key] = collection

    index: dict[str, list[str]] = collections.defaultdict(list)
    for slug, signature in signatures.items():
        for line in signature:
            index[line].append(slug)

    shared: collections.Counter = collections.Counter()
    for line, slugs in index.items():
        if 1 < len(slugs) <= MAX_SHARERS:
            for i in range(len(slugs)):
                for j in range(i + 1, len(slugs)):
                    shared[tuple(sorted((slugs[i], slugs[j])))] += 1

    flagged = []
    for (left, right), count in shared.items():
        ratio = count / min(len(signatures[left]), len(signatures[right]))
        if ratio >= args.threshold:
            flagged.append((ratio, count, left, right))
    flagged.sort(reverse=True)

    print(f"works with a comparable body: {len(signatures)}")
    print(f"pairs sharing >= {args.threshold:.0%} of their prose: {len(flagged)}\n")

    for ratio, count, left, right in flagged:
        lp = CONTENT / where[left] / f"{left.split(':', 1)[1]}.md"
        rp = CONTENT / where[right] / f"{right.split(':', 1)[1]}.md"
        left_says = stated_issue(lp)
        right_says = stated_issue(rp)
        verdict = ""
        if left_says and left_says == right_says:
            verdict = f"  <<< both summaries claim to be the {left_says} issue"
        cross = "  [cross-collection]" if where[left] != where[right] else ""
        print(f"{ratio*100:5.1f}%  {count:3} lines  {left}  ~  {right}{verdict}{cross}")

    if flagged:
        print(
            "\nA pair is only a defect when the two works are genuinely different\n"
            "items. Same work under two slugs is expected to overlap."
        )

    mismatched = self_inconsistent()
    print(f"\nworks whose summary names a different issue from their slug: {len(mismatched)}")
    for slug, claimed, stated in mismatched:
        print(f"  {slug}: slug says {claimed[1]:02d}/{claimed[0]}, "
              f"summary says {stated[1]:02d}/{stated[0]}")
    if mismatched:
        print(
            "\nThese need no partner in the corpus to be wrong: the record\n"
            "contradicts itself, so one of the two dates is false."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
