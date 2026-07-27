#!/usr/bin/env python3
"""
Validate the authored questions and freeze them into the published pool.

Every check here is mechanical. The point is that no question reaches the
published pool unless the grader can actually decide it — and unless a blind
question is really blind. A leaked title turns a retrieval test into a
copy-paste test, and it would inflate the score silently.

Checks, in order of how badly each would corrupt a result:

  1. shape/tier agreement — a `multi` question needs 2+ sources, a `needle`
     exactly one anchor, a `mixed` question one source from each tier
  2. resolvable sources — every doc key exists in the corpus snapshot
  3. real anchors — every Tier A paragraph id exists on the doc it is claimed for
  4. real PDFs — every Tier B work carries the exact pdf_url the corpus has
  5. blind means blind — the question leaks no title, author, or series name
  6. gradeable content — every `answer_must_contain` string is present in the
     source material, and absent from the question itself

Rejections are reported, not silently dropped, and written to
scripts/eval/rejected.json so they can be fixed and re-validated.

Usage:
    python3 scripts/eval/validate_pool.py
    python3 scripts/eval/validate_pool.py --strict   # exit non-zero on any rejection
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from common import (
    REPO,
    anchors_of,
    author_names,
    doc_for,
    fold,
    folded_contains,
    grounded_texts,
    load_corpus,
    shares_ngram,
    title_string,
    tool_reachable_texts,
)

HERE = Path(__file__).resolve().parent
AUTHORED = HERE / "authored"
BRIEFS = HERE / "briefs"
OUT = REPO / "data" / "eval" / "pool.json"
REJECTED = HERE / "rejected.json"

POOL_ID = "il-eval-v1"


def check(question: dict, corpus: dict, brief: dict | None) -> list[str]:
    """Return a list of reasons this question cannot be published. Empty = fine."""
    problems: list[str] = []
    qid = question.get("id", "<no id>")
    text = question.get("question") or ""
    expected = question.get("expected") or {}
    docs = expected.get("docs") or []
    tier = question.get("tier")
    shape = question.get("shape")
    retrieval = question.get("retrieval")

    if not text.strip():
        problems.append("empty question text")

    # Abstention questions name no source on purpose: the correct answer is that
    # the archive holds none. Their one check is that the absence is real.
    if shape == "abstention":
        question["reach"] = "via_tools"
        absent = expected.get("absent") or {}
        if not expected.get("must_abstain"):
            problems.append("abstention question without must_abstain")
        if docs:
            problems.append("abstention question lists expected docs")
        year = absent.get("year")
        if not isinstance(year, int):
            problems.append("abstention question names no absent year")
        else:
            # Works only. `year` on a thinker profile is a birth year and on a
            # musing a posting date, neither of which is a work published then.
            for key, doc in {**corpus["tier_a"], **corpus["tier_b"]}.items():
                if doc.get("collection") == "primary-works" and doc.get("year") == year:
                    problems.append(
                        f"{key} is dated {year}; the absence is not real"
                    )
                    break
        return problems

    if not docs:
        problems.append("no expected docs")
        return problems

    # 1. shape and tier agreement
    if shape == "multi" and len(docs) < 2:
        problems.append(f"shape=multi but only {len(docs)} source(s)")
    if shape in {"single", "needle"} and len(docs) != 1:
        problems.append(f"shape={shape} but {len(docs)} sources")

    resolved = {}
    for key in docs:
        doc = doc_for(corpus, key)
        if doc is None:
            problems.append(f"unknown doc key: {key}")
            continue
        resolved[key] = doc

    if not resolved:
        return problems

    tiers = {d["tier"] for d in resolved.values()}
    if tier == "mixed" and tiers != {"A", "B"}:
        problems.append(f"tier=mixed but sources are all tier {sorted(tiers)}")
    if tier in {"A", "B"} and tiers != {tier}:
        problems.append(f"tier={tier} but sources are tier {sorted(tiers)}")

    # 2/3. anchors must exist on the doc they are claimed for
    anchor_map = expected.get("paragraph_ids") or {}
    for key, doc in resolved.items():
        if doc["tier"] != "A":
            if key in anchor_map and anchor_map[key]:
                problems.append(f"{key} is Tier B but carries paragraph_ids")
            continue
        claimed = anchor_map.get(key) or []
        if not claimed:
            problems.append(f"{key} is Tier A but has no paragraph_ids")
            continue
        real = anchors_of(doc)
        for pid in claimed:
            if pid not in real:
                problems.append(f"{key}: anchor {pid} does not exist on that page")
        if shape == "needle" and len(claimed) != 1:
            problems.append(f"shape=needle but {len(claimed)} anchors for {key}")

    # 4. Tier B works need their real PDF
    pdf_map = expected.get("pdf_urls") or {}
    for key, doc in resolved.items():
        if doc["tier"] != "B":
            continue
        given = pdf_map.get(key)
        actual = doc.get("pdf_url")
        if not actual:
            problems.append(f"{key} has no pdf_url in the corpus — not eligible")
        elif given != actual:
            problems.append(f"{key}: pdf_url mismatch (expected the corpus value)")

    # 5. blind means blind
    if retrieval == "blind":
        for key, doc in resolved.items():
            title = title_string(doc)
            folded_title = fold(title)
            if folded_title and len(folded_title.split()) <= 4:
                if folded_title in fold(text):
                    problems.append(f"blind question contains the full title of {key}")
            else:
                leak = shares_ngram(text, title, 4)
                if leak:
                    problems.append(f"blind question leaks title of {key}: '{leak}'")
            for name in author_names(doc):
                parts = [p for p in fold(name).split() if len(p) > 2]
                surname = parts[-1] if parts else ""
                if surname and f" {surname} " in f" {fold(text)} ":
                    problems.append(f"blind question names the author of {key}: '{name}'")
            series = doc.get("series")
            if series and folded_contains(text, series):
                problems.append(f"blind question names the series of {key}: '{series}'")

    # 6. the substring check must be decidable
    must = expected.get("answer_must_contain") or []
    if not must:
        problems.append("no answer_must_contain strings")
    source_text = " \n ".join(t for key in resolved for t in grounded_texts(corpus, key))

    # A string the question already supplies proves nothing — the agent can echo
    # it without retrieving anything — so it is dropped rather than counted.
    # That is a safe repair while at least one gating string survives; if all of
    # them were give-aways the question has no substring check at all and is
    # rejected. Repairs are recorded on the question so the pool shows its work.
    kept: list[str] = []
    dropped: list[str] = []
    for needle in must:
        if not needle or len(needle.strip()) < 2:
            problems.append(f"answer_must_contain entry too short: {needle!r}")
            continue
        if not folded_contains(source_text, needle):
            problems.append(f"answer_must_contain {needle!r} is not in the source material")
            continue
        if folded_contains(text, needle):
            dropped.append(needle)
            continue
        kept.append(needle)

    # Record whether the surviving strings are obtainable through the documented
    # MCP tools, or only from text the tool layer denies exists. See
    # tool_reachable_texts() for why that distinction is a finding in itself.
    reachable = " \n ".join(t for key in resolved for t in tool_reachable_texts(corpus, key))
    beyond = [n for n in (kept or must) if not folded_contains(reachable, n)]
    question["reach"] = "beyond_tools" if beyond else "via_tools"
    if beyond:
        question["reach_detail"] = beyond

    if dropped and kept:
        expected["answer_must_contain"] = kept
        question.setdefault("repairs", []).append(
            f"dropped {len(dropped)} answer_must_contain string(s) already present in the question: "
            + ", ".join(repr(d) for d in dropped)
        )
    elif dropped and not kept:
        problems.append(
            "every answer_must_contain string is already given away in the question"
        )

    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    corpus = load_corpus()

    briefs_by_id: dict[str, dict] = {}
    for path in sorted(BRIEFS.glob("batch-*.json")):
        with path.open(encoding="utf-8") as fh:
            for brief in json.load(fh)["briefs"]:
                briefs_by_id[brief["id"]] = brief

    authored: list[dict] = []
    skipped: list[dict] = []
    missing_files: list[str] = []

    # Question files with no brief behind them, generated straight from the
    # ontology rather than authored (currently the abstention cell).
    for path in sorted(AUTHORED.glob("*.json")):
        if path.name.startswith("batch-"):
            continue
        with path.open(encoding="utf-8") as fh:
            for question in json.load(fh).get("questions", []):
                if question.get("skip"):
                    skipped.append({"id": question.get("id"), "reason": question.get("reason")})
                else:
                    authored.append(question)

    for path in sorted(BRIEFS.glob("batch-*.json")):
        target = AUTHORED / path.name
        if not target.exists():
            missing_files.append(path.name)
            continue
        with target.open(encoding="utf-8") as fh:
            payload = json.load(fh)
        for question in payload.get("questions", []):
            if question.get("skip"):
                skipped.append({"id": question.get("id"), "reason": question.get("reason")})
            else:
                authored.append(question)

    accepted: list[dict] = []
    rejected: list[dict] = []
    seen: set[str] = set()

    for question in authored:
        qid = question.get("id")
        if qid in seen:
            rejected.append({"id": qid, "problems": ["duplicate id"]})
            continue
        seen.add(qid)
        problems = check(question, corpus, briefs_by_id.get(qid))
        if problems:
            rejected.append({"id": qid, "question": question.get("question"), "problems": problems})
        else:
            accepted.append(question)

    accepted.sort(key=lambda q: q["id"])

    cells = Counter(f"{q['tier']}/{q['retrieval']}/{q['shape']}" for q in accepted)
    pool = {
        "schema_version": 1,
        "pool_id": POOL_ID,
        "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus_built_from": corpus["built_from"],
        "counts": {
            "questions": len(accepted),
            "by_cell": dict(sorted(cells.items())),
            "by_tier": dict(Counter(q["tier"] for q in accepted)),
            "by_retrieval": dict(Counter(q["retrieval"] for q in accepted)),
            "by_shape": dict(Counter(q["shape"] for q in accepted)),
            "by_reach": dict(Counter(q.get("reach", "via_tools") for q in accepted)),
        },
        "questions": accepted,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
    REJECTED.write_text(
        json.dumps({"rejected": rejected, "skipped": skipped, "missing_batch_files": missing_files},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print(f"authored {len(authored)} · accepted {len(accepted)} · rejected {len(rejected)} · skipped {len(skipped)}")
    if missing_files:
        print(f"  MISSING authored files: {', '.join(missing_files)}")
    print(f"  by cell: {json.dumps(dict(sorted(cells.items())), indent=None)}")
    if rejected:
        reasons = Counter()
        for entry in rejected:
            for problem in entry["problems"]:
                reasons[problem.split(":")[0]] += 1
        print("  rejection reasons:")
        for reason, count in reasons.most_common():
            print(f"    {count:4}  {reason}")
    print(f"wrote {OUT.relative_to(REPO)} and {REJECTED.relative_to(REPO)}")

    if args.strict and (rejected or missing_files):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
