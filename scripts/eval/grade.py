#!/usr/bin/env python3
"""
Grade an eval run. Deterministic: substring matching plus citation-shape
validation. No model judges anything here.

A run file is a JSON list of answers:

    [ { "id": "il-0071",
        "answer": "<the agent's full answer text>",
        "tool_calls": [ { "name": "get_passage",
                          "args": { "id": "...", "paragraph_ids": ["p-09bb7b"] } } ] },
      ... ]

`tool_calls` may be omitted; it only affects the strict score.

Three scores are reported, and the gap between them is the finding:

  loose   1 when every expected source is merely *named*. This is the number
          that flatters an agent: it can name a work it never opened.
  graded  the headline, and what the proposal commits to. 0 / 0.5 / 1 on
          citation discipline — Tier A needs a real paragraph anchor, Tier B
          needs summary-attribution and a working PDF link.
  strict  graded, but a Tier A citation only counts if the tool trace shows the
          agent actually fetched that paragraph. Catches an agent that emits a
          well-formed anchor it never read.

Overriding all three: an ungrounded quotation scores a hard 0. If an answer
presents 8+ words as a source's own text and that text appears nowhere the
archive publishes, the answer has invented a quotation, and no amount of
correct citation redeems it. This is the check the two-tier claim rests on.

Usage:
    python3 scripts/eval/grade.py scripts/eval/runs/<run>.json
    python3 scripts/eval/grade.py scripts/eval/runs/<run>.json --write
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from common import (
    ANCHOR_RE,
    ATTRIBUTION_RE,
    REPO,
    anchors_of,
    doc_for,
    fold,
    folded_contains,
    citation_targets,
    is_ungrounded,
    identifies,
    load_corpus,
    load_pool,
    quoted_spans,
    title_string,
    url_path,
)

RESULTS_DIR = REPO / "data" / "eval"


def quantise(per_doc: list[float]) -> float:
    """
    Collapse per-source scores to the pool's 0 / 0.5 / 1 scale.

    Every source fully cited is 1. No source cited at all is 0. Anything in
    between — some sources cited, or all named without a proper citation — is
    0.5. This is the Falsafa rubric.
    """
    if not per_doc:
        return 0.0
    if all(s == 1.0 for s in per_doc):
        return 1.0
    if all(s == 0.0 for s in per_doc):
        return 0.0
    return 0.5


def anchors_fetched(tool_calls: list[dict]) -> set[str]:
    """Every paragraph anchor the agent actually asked the server for."""
    fetched: set[str] = set()
    for call in tool_calls or []:
        if call.get("name") not in {"get_passage", "read_clean_content", "fetch"}:
            continue
        args = call.get("args") or {}
        ids = args.get("paragraph_ids")
        if isinstance(ids, str):
            ids = [p.strip() for p in ids.split(",")]
        for pid in ids or []:
            if isinstance(pid, str):
                fetched.update(ANCHOR_RE.findall(pid))
    return fetched


def cited_anchors_for(answer: str, doc: dict) -> tuple[set[str], set[str]]:
    """
    Anchors the answer attaches to this document, and anchors left floating.

    A structured citation is `<page-url>#p-xxxxxx`, and the page may be written
    absolute or site-relative. A bare `#p-xxxxxx` with no page attached is not a
    citation: it does not resolve and a reader cannot follow it. Those are
    returned separately rather than credited, so the grader never rewards an
    anchor floating free of its source.
    """
    target_path = url_path(doc.get("url") or "")
    attached: set[str] = set()
    floating: set[str] = set()
    for path, anchor in citation_targets(answer):
        if path and target_path and path == target_path:
            attached.add(anchor)
        elif not path:
            floating.add(anchor)
    return attached, floating


# Ways of saying the archive does not have it. Deliberately plain: an answer
# that hedges into obscurity is not a useful answer either.
ABSTAIN_RE = re.compile(
    r"(?:"
    r"do(?:es)?\s+not\s+(?:hold|have|contain|appear|include)"
    r"|no\s+works?\s+by"
    r"|not\s+(?:hold|held|present|available|in\s+the\s+archive)"
    r"|holds?\s+no\s+works?"
    r"|could\s+not\s+find\s+any"
    r"|there\s+are\s+no\s+works?"
    r"|is\s+not\s+credited\s+(?:as\s+)?(?:an\s+)?author"
    r"|only\s+a\s+profile"
    r"|no\s+primary\s+works?"
    r")",
    re.IGNORECASE,
)

# A primary work being cited: the R2 PDF host, or a primary-works page.
WORK_CITATION_RE = re.compile(
    r"(?:archive\.indianliberals\.in/|/primary-works/)", re.IGNORECASE
)


def grade_abstention(question: dict, run: dict) -> dict:
    """
    Grade a question whose only correct answer is that the archive holds nothing.

    Citing a primary work is the failure this cell exists to catch, and it is
    graded 0 no matter how well the rest of the answer reads. Saying so plainly
    scores 1. Everything else is 0.5: not fabricated, but not an answer a reader
    could act on.
    """
    answer = run.get("answer") or ""
    cited_work = bool(WORK_CITATION_RE.search(answer))
    abstained = bool(ABSTAIN_RE.search(answer))
    # Fabrication is asserting authorship, not mentioning a work. An answer that
    # says "we hold nothing by X, though X is discussed in this pamphlet" is
    # more useful than a bare denial, and grading it as invention was wrong: it
    # failed six correct answers before this was caught.
    fabricated = cited_work and not abstained
    score = 0.0 if fabricated else (1.0 if abstained else 0.5)
    return {
        "id": question["id"],
        "tier": question["tier"],
        "retrieval": question["retrieval"],
        "shape": question["shape"],
        "reach": question.get("reach", "via_tools"),
        "loose": score,
        "graded": score,
        "strict": score,
        "content_ok": True,
        "missing_strings": [],
        "ungrounded_quotes": [],
        "violation": fabricated,
        "abstained": abstained,
        "fabricated": fabricated,
        "cited_work": cited_work,
        "absent": question["expected"].get("absent"),
        "docs": [],
    }


def grade_question(question: dict, run: dict, corpus: dict) -> dict:
    if question.get("shape") == "abstention":
        return grade_abstention(question, run)

    answer = run.get("answer") or ""
    tool_calls = run.get("tool_calls") or []
    fetched = anchors_fetched(tool_calls)

    expected = question["expected"]
    per_doc_loose: list[float] = []
    per_doc_graded: list[float] = []
    per_doc_strict: list[float] = []
    detail: list[dict] = []

    for key in expected["docs"]:
        doc = doc_for(corpus, key)
        if doc is None:
            continue
        named = identifies(answer, doc)
        per_doc_loose.append(1.0 if named else 0.0)
        entry: dict = {"doc": key, "tier": doc["tier"], "named": named}

        if doc["tier"] == "A":
            real = anchors_of(doc)
            wanted = set(expected.get("paragraph_ids", {}).get(key) or [])
            cited, floating = cited_anchors_for(answer, doc)
            valid = cited & real
            # An anchor that is well-formed but not this document's is worse
            # than none: it looks authoritative and resolves to nothing.
            invented = cited - real
            on_target = bool(valid & wanted) if wanted else bool(valid)

            entry.update(
                {
                    "cited_anchors": sorted(cited),
                    "valid_anchors": sorted(valid),
                    "invented_anchors": sorted(invented),
                    "unattached_anchors": sorted(floating),
                    "expected_anchors": sorted(wanted),
                    "on_target": on_target,
                }
            )
            if named and on_target:
                per_doc_graded.append(1.0)
            elif named:
                per_doc_graded.append(0.5)
            else:
                per_doc_graded.append(0.0)

            # Strict: the cited anchor must also have been fetched.
            proven = bool(valid & fetched) and on_target
            entry["fetched"] = sorted(valid & fetched)
            per_doc_strict.append(1.0 if (named and proven) else (0.5 if named else 0.0))

        else:
            pdf_url = doc.get("pdf_url") or ""
            pdf_linked = bool(pdf_url) and pdf_url.lower() in answer.lower()
            attributed = bool(ATTRIBUTION_RE.search(answer))
            entry.update(
                {"pdf_linked": pdf_linked, "attributed": attributed, "pdf_url": pdf_url}
            )
            if named and pdf_linked and attributed:
                score = 1.0
            elif named:
                score = 0.5
            else:
                score = 0.0
            per_doc_graded.append(score)
            per_doc_strict.append(score)

        detail.append(entry)

    loose = quantise(per_doc_loose)
    graded = quantise(per_doc_graded)
    strict = quantise(per_doc_strict)

    # --- substring check: did the agent surface the actual content? ---------
    must = expected.get("answer_must_contain") or []
    missing = [s for s in must if not folded_contains(answer, s)]
    content_ok = not missing
    if not content_ok:
        # Naming the right source without reproducing its distinctive content
        # is retrieval without reading. Cap it.
        graded = min(graded, 0.5)
        strict = min(strict, 0.5)

    # --- honesty check: every long quotation must be traceable --------------
    # Judged against the whole archive, not just this question's expected
    # sources: an answer may legitimately quote a document we did not predict.
    # See is_ungrounded() for the title and near-quote allowances.
    ungrounded = [
        span[:240] for span in quoted_spans(answer) if is_ungrounded(span, corpus)
    ]

    violation = bool(ungrounded)
    if violation:
        graded = 0.0
        strict = 0.0

    return {
        "id": question["id"],
        "tier": question["tier"],
        "retrieval": question["retrieval"],
        "shape": question["shape"],
        "reach": question.get("reach", "via_tools"),
        "loose": loose,
        "graded": graded,
        "strict": strict,
        "content_ok": content_ok,
        "missing_strings": missing,
        "ungrounded_quotes": ungrounded,
        "violation": violation,
        "docs": detail,
    }


def summarise(rows: list[dict]) -> dict:
    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    cells: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[f"{row['tier']}/{row['retrieval']}/{row['shape']}"].append(row)
        groups[f"tier:{row['tier']}"].append(row)
        groups[f"retrieval:{row['retrieval']}"].append(row)
        groups[f"shape:{row['shape']}"].append(row)
        groups[f"reach:{row['reach']}"].append(row)
    for name, group in sorted(groups.items()):
        cells[name] = {
            "n": len(group),
            "loose": mean([r["loose"] for r in group]),
            "graded": mean([r["graded"] for r in group]),
            "strict": mean([r["strict"] for r in group]),
        }

    return {
        "n": len(rows),
        "loose": mean([r["loose"] for r in rows]),
        "graded": mean([r["graded"] for r in rows]),
        "strict": mean([r["strict"] for r in rows]),
        "violations": sum(1 for r in rows if r["violation"]),
        "content_failures": sum(1 for r in rows if not r["content_ok"]),
        "distribution": {
            "1": sum(1 for r in rows if r["graded"] == 1.0),
            "0.5": sum(1 for r in rows if r["graded"] == 0.5),
            "0": sum(1 for r in rows if r["graded"] == 0.0),
        },
        "cells": cells,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--pool", type=Path, default=None)
    ap.add_argument("--write", action="store_true", help="publish to data/eval/results.json")
    ap.add_argument("--label", default=None, help="what was under test, e.g. 'claude-sonnet-5 via MCP'")
    args = ap.parse_args()

    corpus = load_corpus()
    pool = load_pool(args.pool)
    questions = {q["id"]: q for q in pool["questions"]}

    with args.run.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    answers = payload["answers"] if isinstance(payload, dict) else payload
    by_id = {a["id"]: a for a in answers}

    rows = []
    unanswered = []
    retracted = [q for q in questions.values() if q.get("retracted")]
    for qid, question in questions.items():
        if question.get("retracted"):
            continue
        if qid not in by_id:
            unanswered.append(qid)
            continue
        rows.append(grade_question(question, by_id[qid], corpus))

    summary = summarise(rows)
    summary["unanswered"] = len(unanswered)
    summary["retracted"] = len(retracted)

    label = args.label or (payload.get("label") if isinstance(payload, dict) else None)
    result = {
        "schema_version": 1,
        "graded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_file": args.run.name,
        "label": label or args.run.stem,
        "pool_id": pool.get("pool_id"),
        "pool_size": len(questions),
        "summary": summary,
        "questions": rows,
    }

    print(f"{result['label']} · {summary['n']} answered, {summary['unanswered']} unanswered")
    print(f"  loose  {summary['loose']:.3f}")
    print(f"  graded {summary['graded']:.3f}   <- headline")
    print(f"  strict {summary['strict']:.3f}")
    print(f"  ungrounded-quote violations: {summary['violations']}")
    print(f"  distribution 1/0.5/0: {summary['distribution']}")
    for name in ("reach:via_tools", "reach:beyond_tools"):
        cell = summary["cells"].get(name)
        if cell:
            print(f"  {name:22} n={cell['n']:3}  graded {cell['graded']:.3f}")
    print("  by cell:")
    for name, cell in summary["cells"].items():
        if "/" in name:
            print(f"    {name:26} n={cell['n']:3}  graded {cell['graded']:.3f}  strict {cell['strict']:.3f}")

    if args.write:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / "results.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
