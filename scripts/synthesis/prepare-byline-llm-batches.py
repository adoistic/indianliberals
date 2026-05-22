#!/usr/bin/env python3
"""
Step 2 input prep: chunk deferred.jsonl into LLM batches of ~20 entries each.

Each batch carries: a list of deferred-entry candidate records (with their
token_candidates, year, work_type, title, and any deterministic_hits that
were ambiguous in Step 1). The full thinkers list is NOT inlined into each
batch JSONL — it's inlined into the system prompt by render-system-byline.py
to keep batch files small and the prompt versioned.

Run:
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-llm-batches.py
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-llm-batches.py --test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFERRED = ROOT / "data/byline-resolve/deferred.jsonl"
OUT_DIR = ROOT / "data/byline-resolve"
BATCH_SIZE = 20


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        print("prepare-byline-llm-batches: no inline unit tests (pure I/O batching)")
        return 0

    if not DEFERRED.exists():
        print(f"ERROR: {DEFERRED} not found. Run resolve-byline-deterministic.py first.", file=sys.stderr)
        return 1

    # Wipe stale batches for reproducibility
    for stale in OUT_DIR.glob("llm-batch-*.jsonl"):
        stale.unlink()

    records = [json.loads(l) for l in DEFERRED.read_text().splitlines() if l.strip()]
    n_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(n_batches):
        chunk = records[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        out_path = OUT_DIR / f"llm-batch-{i:02d}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for rec in chunk:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"wrote {out_path.relative_to(ROOT)}  ({len(chunk)} records)")
    print(f"total: {len(records)} records across {n_batches} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
