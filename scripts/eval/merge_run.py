#!/usr/bin/env python3
"""
Merge the per-part answer files from one run into a single run file.

The pool is split across several agents so no single answer gets truncated.
This puts the pieces back together, reports anything missing, and refuses to
silently produce a run that only covers part of the pool — a partial run graded
as if it were complete would flatter the score.

Usage:
    python3 scripts/eval/merge_run.py --label "claude-sonnet-5 via MCP, 2026-07-27"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import load_pool

HERE = Path(__file__).resolve().parent
PARTS = HERE / "runparts"
RUNS = HERE / "runs"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default=None, help="run file name; defaults from the label")
    args = ap.parse_args()

    pool = load_pool()
    expected = {q["id"] for q in pool["questions"]}

    answers: dict[str, dict] = {}
    malformed: list[str] = []
    for path in sorted(PARTS.glob("answers-*.json")):
        try:
            with path.open(encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            malformed.append(f"{path.name}: {exc}")
            continue
        rows = payload.get("answers") if isinstance(payload, dict) else payload
        for row in rows or []:
            qid = row.get("id")
            if not qid:
                continue
            if qid in answers:
                malformed.append(f"{path.name}: duplicate answer for {qid}")
                continue
            answers[qid] = {
                "id": qid,
                "answer": row.get("answer") or "",
                "tool_calls": row.get("tool_calls") or [],
            }

    missing = sorted(expected - set(answers))
    extra = sorted(set(answers) - expected)
    empty = sorted(qid for qid, a in answers.items() if not a["answer"].strip())

    RUNS.mkdir(exist_ok=True)
    name = args.out or "run.json"
    out = RUNS / name
    out.write_text(
        json.dumps(
            {
                "label": args.label,
                "pool_id": pool.get("pool_id"),
                "answers": [answers[qid] for qid in sorted(answers) if qid in expected],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    print(f"merged {len(answers)} answers from {len(list(PARTS.glob('answers-*.json')))} part file(s)")
    print(f"  pool size {len(expected)} · missing {len(missing)} · empty {len(empty)} · unknown ids {len(extra)}")
    if malformed:
        print("  problems:")
        for problem in malformed:
            print(f"    {problem}")
    if missing:
        print(f"  MISSING: {', '.join(missing[:20])}{' …' if len(missing) > 20 else ''}")
    if extra:
        print(f"  UNKNOWN: {', '.join(extra[:10])}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
