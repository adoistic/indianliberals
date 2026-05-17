"""
Append-only JSONL ledger for all LLM dispatch calls in the extraction pipeline.

The pipeline runs 100% on Claude Code subagents (Max plan, flat-rate), so the
ledger does NOT track $-cost per call — there is none from our side. What it
tracks:

  - Which prompts and prompt versions ran when, on which PDFs
  - Wall-clock per dispatch (throughput tracking + slow-call diagnosis)
  - Pass/fail outcome and error text (for retry decisions)
  - Token counts WHEN the subagent reports them (often null)
  - Model used (sonnet / opus) and self-consistency run label (a / b / tiebreak)

Each line is a JSON object (LedgerEntry).  Writes are atomic for small writes
on POSIX (`open(..., "a")`).

Usage:
    from ledger import LedgerEntry, append, summarize
    entry = LedgerEntry(timestamp=..., pdf_path=..., ...)
    append(entry)
    stats = summarize()

CLI:
    python3 ledger.py summary
    python3 ledger.py append-test   # appends 3 fake entries for verification
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO / "data/extraction-log.jsonl"


@dataclass
class LedgerEntry:
    timestamp: str          # ISO 8601 UTC, e.g. "2026-05-17T14:23:01Z"
    pdf_path: str
    job: str                # "byline-sweep" | "metadata" | "summary" | "tiebreak" | "synthesis"
    chunk_idx: int | None
    model: str              # "sonnet" | "opus"
    prompt_version: str     # e.g. "v1.0"
    self_consistency_run: str | None   # "a" | "b" | "tiebreak" | None
    input_tokens: int | None           # often None — subagent rarely reports
    output_tokens: int | None
    wall_clock_s: float
    ok: bool
    error: str | None
    work_slug: str | None = None       # canonical slug for the work this call relates to


def _now_utc() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append(
    entry: LedgerEntry,
    ledger_path: Path = DEFAULT_LEDGER,
) -> None:
    """
    Append one LedgerEntry to the JSONL file.

    Atomic for small writes on POSIX (open in "a" mode).
    Creates parent directories if they do not exist.
    """
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(entry), ensure_ascii=False)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def summarize(
    ledger_path: Path = DEFAULT_LEDGER,
) -> dict[str, Any]:
    """
    Read the ledger and return aggregate statistics.

    Returns:
        {
            total_calls, ok_calls, error_calls,
            total_wall_clock_s, mean_wall_clock_s,
            by_job:   {job:   {calls, ok, errors, total_s, mean_s}},
            by_model: {model: {calls, ok, errors, total_s, mean_s}},
            by_prompt_version: {version: calls},
        }
    """
    ledger_path = Path(ledger_path)
    entries: list[LedgerEntry] = []

    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append(LedgerEntry(**data))
            except Exception:
                pass  # skip corrupt lines silently

    total_wall = sum(e.wall_clock_s for e in entries)
    ok_calls = sum(1 for e in entries if e.ok)
    error_calls = sum(1 for e in entries if not e.ok)
    n = len(entries)

    by_job: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_prompt_version: dict[str, int] = {}

    for e in entries:
        for bucket, key in ((by_job, e.job), (by_model, e.model)):
            if key not in bucket:
                bucket[key] = {"calls": 0, "ok": 0, "errors": 0, "total_s": 0.0}
            bucket[key]["calls"] += 1
            bucket[key]["ok" if e.ok else "errors"] += 1
            bucket[key]["total_s"] += e.wall_clock_s

        by_prompt_version[e.prompt_version] = by_prompt_version.get(e.prompt_version, 0) + 1

    # Add mean_s to each bucket
    for bucket in (by_job, by_model):
        for k, v in bucket.items():
            v["mean_s"] = round(v["total_s"] / max(v["calls"], 1), 3)
            v["total_s"] = round(v["total_s"], 3)

    return {
        "total_calls": n,
        "ok_calls": ok_calls,
        "error_calls": error_calls,
        "total_wall_clock_s": round(total_wall, 3),
        "mean_wall_clock_s": round(total_wall / max(n, 1), 3),
        "by_job": by_job,
        "by_model": by_model,
        "by_prompt_version": by_prompt_version,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_summary(ledger_path: Path) -> None:
    stats = summarize(ledger_path)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


def _cmd_append_test(ledger_path: Path) -> None:
    """Append 3 fake entries for verification purposes."""
    fakes = [
        LedgerEntry(
            timestamp=_now_utc(),
            pdf_path="forum-of-free-enterprise/Some-Light-On-Coal-Discoveries.pdf",
            job="byline-sweep",
            chunk_idx=None,
            model="sonnet",
            prompt_version="v1.0",
            self_consistency_run=None,
            input_tokens=None,
            output_tokens=None,
            wall_clock_s=4.2,
            ok=True,
            error=None,
            work_slug="some-light-on-coal-discoveries",
        ),
        LedgerEntry(
            timestamp=_now_utc(),
            pdf_path="liberals/satyamev-jayate-volume-1.pdf",
            job="metadata",
            chunk_idx=0,
            model="sonnet",
            prompt_version="v1.0",
            self_consistency_run="a",
            input_tokens=None,
            output_tokens=None,
            wall_clock_s=18.5,
            ok=True,
            error=None,
            work_slug="satyamev-jayate-volume-1",
        ),
        LedgerEntry(
            timestamp=_now_utc(),
            pdf_path="bengali/balyo-bibaher-dosh-Ishwar-chandra-vidyasagar.pdf",
            job="summary",
            chunk_idx=0,
            model="sonnet",
            prompt_version="v1.0",
            self_consistency_run=None,
            input_tokens=None,
            output_tokens=None,
            wall_clock_s=12.7,
            ok=True,
            error=None,
            work_slug="balyo-bibaher-dosh",
        ),
    ]

    for entry in fakes:
        append(entry, ledger_path)
        print(f"  appended: {entry.job} / {Path(entry.pdf_path).name}")

    print(f"\nAppended {len(fakes)} entries.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM call ledger for extraction pipeline")
    parser.add_argument(
        "command",
        choices=["summary", "append-test"],
        help="summary: print aggregate stats; append-test: add 3 fake entries",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_LEDGER,
        help=f"Path to JSONL ledger file (default: {DEFAULT_LEDGER})",
    )
    args = parser.parse_args()

    if args.command == "summary":
        _cmd_summary(args.ledger)
    elif args.command == "append-test":
        _cmd_append_test(args.ledger)
