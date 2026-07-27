#!/usr/bin/env python3
"""
Build the abstention questions: things the archive genuinely does not hold.

Every other cell asks whether an agent can find what is here. This one asks
whether it will admit when something is not. That is the failure that actually
costs a researcher: a confident citation to an issue that was never scanned is
worse than no answer, because it looks exactly like a real one.

The questions are generated from the ontology rather than written, so there is
nothing to argue about. The archive profiles 695 thinkers but holds works by
only some of them: 321 are named, described, and cross-referenced without a
single work of their own on file. Asking what one of those people wrote is not a
trick, it is the most ordinary thing a reader does, and the archive's own
metadata settles the answer in one pass.

The presupposition is deliberate. "What works by X does the archive hold" takes
for granted that it holds some. An agent that pattern-matches on the profile it
does find, and dresses it up as a work, fails here and nowhere else.

Grading is in grade.py:

  1    the answer says the archive does not hold it, and cites nothing
  0.5  no clear statement either way, but nothing fabricated
  0    a work is cited, or the answer asserts the issue exists

Usage:
    python3 scripts/eval/build_abstention.py
    python3 scripts/eval/build_abstention.py --count 30
"""

from __future__ import annotations

import argparse
import json
import random
import re

import yaml
from collections import defaultdict
from pathlib import Path

from common import REPO, fold, load_corpus, title_string

HERE = Path(__file__).resolve().parent
OUT = HERE / "authored" / "abstention.json"

SEED = 20260727


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    corpus = load_corpus()
    rng = random.Random(args.seed)

    # Years the archive holds nothing from.
    #
    # This replaced an earlier design that asked which works the archive held by
    # a person it profiles but credits with nothing. That could not be made
    # safe. Credit is recorded four different ways, the search index leaves
    # `authors` empty for musings, video works never record their speaker as an
    # author, and once the check was tightened enough to be trustworthy it
    # excluded every profiled figure in the archive. Two questions shipped with
    # a wrong answer key before that became clear, and the agents were the ones
    # who caught it.
    #
    # A year is different. `publication.year` is a single field with a single
    # meaning, and a year with no works is a fact one pass over the metadata
    # settles. It is also how researchers actually ask: give me what you have
    # from 1947.
    years: dict[int, int] = {}
    for path in (REPO / "apps/site/dist/api/works").glob("*.json"):
        with path.open(encoding="utf-8") as fh:
            year = json.load(fh).get("year")
        if isinstance(year, int):
            years[year] = years.get(year, 0) + 1

    lo, hi = min(years), max(years)
    gaps = [y for y in range(lo, hi + 1) if y not in years]
    # Weight towards the decades the archive is actually about, where an empty
    # year is a real gap in the record rather than simply out of period.
    modern = [y for y in gaps if y >= 1920]
    rng.shuffle(modern)
    chosen_years = sorted(modern[: args.count])

    questions = []
    for n, year in enumerate(chosen_years, start=1):
        questions.append(
            {
                "id": f"il-abs-{n:03d}",
                "tier": "none",
                "retrieval": "named",
                "shape": "abstention",
                "question": (
                    f"What does the Indian Liberals archive hold that was published in "
                    f"{year}? Give me the works and what they argue."
                ),
                "expected": {
                    "docs": [],
                    "paragraph_ids": {},
                    "pdf_urls": {},
                    "answer_must_contain": [],
                    "must_abstain": True,
                    "absent": {"year": year},
                },
                "rationale": (
                    f"No work in the archive carries publication.year {year}, though the "
                    f"corpus spans {lo} to {hi}. The question presumes there is something "
                    f"from that year; the only correct answer says there is not."
                ),
            }
        )

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"batch": "abstention", "cell": {"tier": "none", "retrieval": "named",
                                             "shape": "abstention"},
             "questions": questions},
            ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(questions)} abstention questions -> {OUT.relative_to(REPO)}")
    print(f"  corpus spans {lo}-{hi}; {len(gaps)} years inside it hold nothing, "
          f"{len(modern)} of them from 1920 on")
    for q in questions[:6]:
        print(f"  {q['id']}: {q['expected']['absent']['year']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
