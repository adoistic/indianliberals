#!/usr/bin/env python3
"""
Headless `claude -p` driver for the Phase B in-prose NER pass.

Reads `data/synthesis/ner-input.jsonl` (produced by `prepare-ner-batches.py`)
and the cleaned `data/authority/thinkers.json`, chunks the entries into
batches, and dispatches each batch through `claude -p` with the prompt
from `scripts/synthesis/prompts/system-ner.txt`.

Appends one JSON mention record per line to `data/synthesis/ner-mentions.jsonl`.
One entry may produce zero, one, or many lines (one per authority-listed
thinker who appears in the body).

Idempotent: entries already resolved (any prior line for that entry_id)
are skipped on re-run. Restart-safe after a rate-limit pause.

Mirror of `resolve-unlinked.py`. See that file for the chat-vs-headless
dual-path design rationale.

Run from repo root:

    python3 scripts/synthesis/resolve-ner.py \
        --batch-size 8 \
        --concurrency 2 \
        --max-batches 1     # smoke-batch run; remove for full pass

Optional flags:
    --dry-run               # print the prompt + first batch and exit
    --only musings,opinions # restrict to a subset of collections
    --redo                  # force re-resolve everything
    --input-file PATH       # override the default ner-input.jsonl path
    --output-file PATH      # override the default ner-mentions.jsonl path
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NER_INPUT = ROOT / "data/synthesis/ner-input.jsonl"
NER_MENTIONS = ROOT / "data/synthesis/ner-mentions.jsonl"
AUTHORITY = ROOT / "data/authority/thinkers.json"
SYSTEM_PROMPT = ROOT / "scripts/synthesis/prompts/system-ner.txt"

# Same rate-limit-aware circuit-breaker pattern as the overnight extraction
# runner uses (scripts/llm-extract/run_overnight.py). Trips on explicit
# rate-limit signals from claude -p stderr/stdout; parses reset times like
# "resets 4:10am (Asia/Calcutta)" and sleeps exactly that long.

RATE_LIMIT_PATTERNS = re.compile(
    r"(rate.?limit|usage.?limit|quota.?exceeded|too.?many.?requests"
    r"|5-?hour|weekly.?limit|limit.?reached|429|please.?try.?again|"
    r"capacity|throttle|out.?of.?extra.?usage)",
    re.I,
)
RESET_TIME_PATTERN = re.compile(
    r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:\(([^)]+)\))?",
    re.I,
)


def parse_reset_seconds(text: str) -> float | None:
    m = RESET_TIME_PATTERN.search(text or "")
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    tzname = m.group(4) or "Asia/Calcutta"
    if ampm == "pm" and hour < 12: hour += 12
    if ampm == "am" and hour == 12: hour = 0
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tzname)
    except Exception:
        return None
    from datetime import datetime, timedelta
    now_dt = datetime.now(tz)
    target = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_dt:
        target += timedelta(days=1)
    secs = (target.timestamp() - now_dt.timestamp()) + 30
    if 0 < secs < 25 * 3600:
        return secs
    return None


class Breaker:
    def __init__(self, default_pause_min: float = 30.0):
        self._lock = threading.Lock()
        self._gate = threading.Event()
        self._gate.set()
        self._default_pause_s = default_pause_min * 60

    def wait(self):
        self._gate.wait()

    def trip(self, reason: str, sleep_s: float | None):
        with self._lock:
            if not self._gate.is_set():
                return
            self._gate.clear()
            sleep_s = sleep_s or self._default_pause_s
            print(f"[breaker] TRIPPED — {reason}; sleeping {sleep_s/60:.1f}min", flush=True)
            t = threading.Thread(target=self._wait_and_resume, args=(sleep_s,), daemon=True)
            t.start()

    def _wait_and_resume(self, sleep_s: float):
        time.sleep(sleep_s)
        with self._lock:
            print(f"[breaker] RESUMING after {sleep_s/60:.1f}min pause", flush=True)
            self._gate.set()


BREAKER = Breaker()


def build_authority_listing() -> str:
    """Render the authority list as a `<slug>  ::  <Canonical>` block.

    The list is part of every user message — the resolver matches input
    bylines against it. The list is ~350 entries × ~60 chars = ~20 KB,
    well within claude -p prompt budget."""
    doc = json.loads(AUTHORITY.read_text())
    lines = []
    for t in doc.get("thinkers", []):
        canonical = (t.get("name") or {}).get("canonical") or ""
        lines.append(f"{t['id']}  ::  {canonical}")
    return "\n".join(sorted(lines))


def build_user_message(batch: list[dict], authority_listing: str) -> str:
    lines = ["## Authority", "", authority_listing, "", "## Entries to scan", ""]
    for rec in batch:
        lines.append(json.dumps(rec, ensure_ascii=False))
    lines.append("")
    lines.append(
        "For each entry above, emit one JSON object per (entry, thinker) "
        "pair where the thinker appears in the body. Multiple lines per "
        "entry are allowed. Entries with no authority-listed thinkers "
        "should produce zero lines. No prose, no fences — JSON only."
    )
    return "\n".join(lines)


def claude_dispatch(system: str, user: str, timeout_s: int = 600) -> list[dict]:
    """Run claude -p with the system + user message; parse out JSON lines."""
    BREAKER.wait()

    # System message goes via --append-system-prompt (no shell-escape issues);
    # user payload goes via stdin to keep prompts off the command line.
    cmd = [
        "claude", "-p",
        "--dangerously-skip-permissions",
        "--allowed-tools", "Read,Write",
        "--append-system-prompt", system,
    ]
    try:
        result = subprocess.run(
            cmd, input=user, capture_output=True, text=True, timeout=timeout_s
        )
    except subprocess.TimeoutExpired:
        BREAKER.trip("claude -p timeout", None)
        return []

    if result.returncode != 0:
        combined = (result.stderr or "") + " " + (result.stdout or "")
        if RATE_LIMIT_PATTERNS.search(combined):
            BREAKER.trip(f"rate limit: {combined[:120]!r}", parse_reset_seconds(combined))
        else:
            print(f"[claude] exit {result.returncode}: {combined[:200]}", flush=True)
        return []

    # Parse one JSON object per line — skip prose noise the LLM might emit.
    mentions: list[dict] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            mentions.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return mentions


def already_resolved_entry_ids(path: Path) -> set[str]:
    """Read existing ner-mentions.jsonl to support resume-by-default behaviour.
    Returns the set of entry_ids that have at least one line emitted."""
    if not path.exists():
        return set()
    ids: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("entry_id"):
                    ids.add(r["entry_id"])
            except json.JSONDecodeError:
                continue
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--input-file", default="", help="Override the default NER_INPUT path (used by smoke-batch runs)")
    ap.add_argument("--output-file", default="", help="Override the default NER_MENTIONS path (used by smoke-batch runs)")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--max-batches", type=int, default=0, help="0 = no cap")
    ap.add_argument("--only", default="", help="Comma-separated collection allowlist")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()

    input_path = Path(args.input_file).resolve() if args.input_file else NER_INPUT
    output_path = Path(args.output_file).resolve() if args.output_file else NER_MENTIONS

    if not input_path.exists():
        print(f"ERROR: run prepare-ner-batches.py first ({input_path} missing)")
        return 1
    if not SYSTEM_PROMPT.exists():
        print(f"ERROR: system prompt missing at {SYSTEM_PROMPT}")
        return 1

    system_msg = SYSTEM_PROMPT.read_text()
    authority = build_authority_listing()

    with input_path.open(encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    only = set(args.only.split(",")) if args.only else None
    if only:
        entries = [e for e in entries if e["collection"] in only]

    done = set() if args.redo else already_resolved_entry_ids(output_path)
    if not args.redo and output_path.exists():
        print(f"[resume] {len(done)} entries already resolved; will skip those")
    # Resume key: input `id` == output `entry_id` (per system-ner.txt
    # contract — the model echoes the input id verbatim into entry_id).
    # So we filter the input list by `id` against the set of output `entry_id`s.
    pending = [e for e in entries if e["id"] not in done]
    print(f"[plan] pending: {len(pending)}, batches: {(len(pending) + args.batch_size - 1) // args.batch_size}")

    if args.dry_run:
        print("\n--- SYSTEM PROMPT ---\n")
        print(system_msg[:1500] + ("...\n[truncated]" if len(system_msg) > 1500 else ""))
        print("\n--- USER MESSAGE (batch 1, 3 sample entries) ---\n")
        print(build_user_message(pending[:3], authority[:1000] + "\n...[truncated]"))
        return 0

    # Chunk into batches
    batches: list[list[dict]] = [
        pending[i:i + args.batch_size] for i in range(0, len(pending), args.batch_size)
    ]
    if args.max_batches:
        batches = batches[:args.max_batches]

    # Open mentions file for append. Mode 'w' if redo, else 'a'.
    mode = "w" if args.redo else "a"
    out_f = output_path.open(mode, encoding="utf-8")
    write_lock = threading.Lock()

    def run_batch(idx: int, batch: list[dict]) -> tuple[int, int]:
        user_msg = build_user_message(batch, authority)
        resolutions = claude_dispatch(system_msg, user_msg)
        if not resolutions:
            return idx, 0
        with write_lock:
            for r in resolutions:
                out_f.write(json.dumps(r, ensure_ascii=False) + "\n")
            out_f.flush()
        return idx, len(resolutions)

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = [ex.submit(run_batch, i, b) for i, b in enumerate(batches)]
        for fut in as_completed(futs):
            idx, n = fut.result()
            print(f"[batch {idx+1}/{len(batches)}] {n} mentions", flush=True)

    out_f.close()
    print(f"[done] mentions written to {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
