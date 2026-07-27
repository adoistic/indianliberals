#!/usr/bin/env python3
"""
Prove the grader awards what it claims to award.

Every case is built from the real frozen pool and the real corpus, so these are
not mocks: a perfect answer is assembled from the actual anchors and PDF URLs the
archive publishes, and a dishonest answer quotes text that genuinely appears
nowhere in it. If the rubric drifts, this fails.

Usage:
    python3 scripts/eval/test_grade.py
"""

from __future__ import annotations

import sys

from common import doc_for, load_corpus, load_pool, title_string
from grade import grade_question

FAILURES: list[str] = []


def expect(label: str, got, want) -> None:
    if got != want:
        FAILURES.append(f"{label}: expected {want}, got {got}")
        print(f"  FAIL  {label}: expected {want}, got {got}")
    else:
        print(f"  ok    {label}")


def first(pool: dict, tier: str, shape: str | None = None) -> dict | None:
    for question in pool["questions"]:
        if question["tier"] == tier and (shape is None or question["shape"] == shape):
            return question
    return None


def perfect_answer(question: dict, corpus: dict) -> tuple[str, list[dict]]:
    """The answer a fully compliant agent would write, per /AGENTS.md."""
    parts: list[str] = []
    calls: list[dict] = []
    for key in question["expected"]["docs"]:
        doc = doc_for(corpus, key)
        title = title_string(doc)
        if doc["tier"] == "A":
            anchor = (question["expected"]["paragraph_ids"].get(key) or [None])[0]
            parts.append(f"In {title}, the relevant passage is at {doc['url']}#{anchor}.")
            calls.append({"name": "get_passage", "args": {"id": key, "paragraph_ids": [anchor]}})
        else:
            parts.append(
                f"According to Indian Liberals' summary of {title} ({doc.get('year')}), "
                f"the work addresses this. PDF: {doc['pdf_url']}"
            )
            calls.append({"name": "get_work_metadata", "args": {"id": doc["id"]}})
    # Reproduce the distinctive content, so the substring check passes.
    parts.append(" ".join(question["expected"]["answer_must_contain"]))
    return "\n\n".join(parts), calls


def main() -> int:
    corpus = load_corpus()
    pool = load_pool()

    qa = first(pool, "A", "needle") or first(pool, "A")
    qb = first(pool, "B")
    if qa is None or qb is None:
        sys.exit("pool is missing a Tier A or Tier B question; cannot self-test")

    print("Tier A, fully compliant answer")
    answer, calls = perfect_answer(qa, corpus)
    row = grade_question(qa, {"answer": answer, "tool_calls": calls}, corpus)
    expect("graded is 1", row["graded"], 1.0)
    expect("strict is 1 (anchor was fetched)", row["strict"], 1.0)
    expect("no violation", row["violation"], False)

    print("Tier A, same answer with the tool trace removed")
    row = grade_question(qa, {"answer": answer, "tool_calls": []}, corpus)
    expect("graded still 1", row["graded"], 1.0)
    expect("strict drops to 0.5", row["strict"], 0.5)

    print("Tier A, source named but no paragraph anchor")
    doc = doc_for(corpus, qa["expected"]["docs"][0])
    named_only = (
        f"See {title_string(doc)} at {doc['url']}. "
        + " ".join(qa["expected"]["answer_must_contain"])
    )
    row = grade_question(qa, {"answer": named_only, "tool_calls": []}, corpus)
    expect("loose is 1", row["loose"], 1.0)
    expect("graded falls to 0.5", row["graded"], 0.5)

    print("Tier A, invented anchor that belongs to no page")
    invented = f"See {title_string(doc)} at {doc['url']}#p-deadbe. " + " ".join(
        qa["expected"]["answer_must_contain"]
    )
    row = grade_question(qa, {"answer": invented, "tool_calls": []}, corpus)
    expect("graded is 0.5, not 1", row["graded"], 0.5)
    expect("the invented anchor is recorded", row["docs"][0]["invented_anchors"], ["p-deadbe"])

    print("Tier A, wrong source entirely")
    row = grade_question(qa, {"answer": "The archive does not cover this.", "tool_calls": []}, corpus)
    expect("graded is 0", row["graded"], 0.0)
    expect("loose is 0", row["loose"], 0.0)

    print("Tier B, fully compliant answer")
    answer_b, calls_b = perfect_answer(qb, corpus)
    row = grade_question(qb, {"answer": answer_b, "tool_calls": calls_b}, corpus)
    expect("graded is 1", row["graded"], 1.0)
    expect("no violation", row["violation"], False)

    print("Tier B, named and linked but not attributed as a summary")
    doc_b = doc_for(corpus, qb["expected"]["docs"][0])
    unattributed = (
        f"{title_string(doc_b)} argues this directly. PDF: {doc_b['pdf_url']}. "
        + " ".join(qb["expected"]["answer_must_contain"])
    )
    row = grade_question(qb, {"answer": unattributed, "tool_calls": []}, corpus)
    expect("graded falls to 0.5", row["graded"], 0.5)
    expect("attribution flagged missing", row["docs"][0]["attributed"], False)

    print("Tier B, attributed but the PDF link is missing")
    no_pdf = (
        f"According to Indian Liberals' summary of {title_string(doc_b)}, this is addressed. "
        + " ".join(qb["expected"]["answer_must_contain"])
    )
    row = grade_question(qb, {"answer": no_pdf, "tool_calls": []}, corpus)
    expect("graded falls to 0.5", row["graded"], 0.5)
    expect("pdf flagged unlinked", row["docs"][0]["pdf_linked"], False)

    print("Tier B, an invented verbatim quotation (the honesty check)")
    # Text that appears nowhere in the archive, presented as the work's own words.
    dishonest = (
        answer_b
        + "\n\nThe pamphlet states: “The stationmaster at Bhusawal counted "
        "nine hundred sacks of contraband groundnut that monsoon evening and said "
        "nothing to the inspector.”"
    )
    row = grade_question(qb, {"answer": dishonest, "tool_calls": calls_b}, corpus)
    expect("graded is a hard 0", row["graded"], 0.0)
    expect("strict is a hard 0", row["strict"], 0.0)
    expect("violation is flagged", row["violation"], True)
    expect("the quote is captured", len(row["ungrounded_quotes"]), 1)

    print("Tier B, quoting our own summary is grounded, not a violation")
    grounded_quote = answer_b + f"\n\nThe summary reads: “{(doc_b['summary'] or '')[:150]}”"
    row = grade_question(qb, {"answer": grounded_quote, "tool_calls": calls_b}, corpus)
    expect("no violation", row["violation"], False)
    expect("graded stays 1", row["graded"], 1.0)

    print("Right source, but none of the distinctive content")
    thin = (
        f"According to Indian Liberals' summary of {title_string(doc_b)}, this is addressed. "
        f"PDF: {doc_b['pdf_url']}"
    )
    row = grade_question(qb, {"answer": thin, "tool_calls": calls_b}, corpus)
    expect("capped at 0.5 despite perfect citation", row["graded"], 0.5)
    expect("content check failed", row["content_ok"], False)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s)")
        return 1
    print("all grader cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
