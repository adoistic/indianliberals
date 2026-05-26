"""Overnight extraction runner — processes the 903 unbaked PDFs via headless `claude -p`.

Architecture:
- Runs as a single Python background process (Bash run_in_background).
- For each PDF, runs the three-job pipeline (metadata.a, metadata.b, summary)
  via headless `claude -p` invocations.
- Each `claude -p` is a fresh Claude Code session with Read+Write access to
  the request_dir. Output: response.json in the request_dir.
- ThreadPool runs N PDFs concurrently. Within a PDF, metadata.a + metadata.b
  run in parallel, then summary serially.
- driver.py collect auto-emits Astro MD on summary success.

Race-condition prevention:
- Each driver.py prep generates a unique chunk0-<hash> request_dir.
- Thread pool dispatches each PDF to exactly one worker thread.
- claude -p invocations write to the request_dir's response.json explicitly.

Run:
    cd "/Users/siraj/Indian Liberals Website"
    source .venv-extract/bin/activate
    nohup python3 scripts/llm-extract/run_overnight.py \\
        --concurrency 8 \\
        > /tmp/v1.5-overnight.log 2>&1 &

Monitor:
    tail -f /tmp/v1.5-overnight.log
    tail -f /tmp/v1.5-overnight-progress.tsv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/Users/siraj/Indian Liberals Website")
VENV_PY = str(ROOT / ".venv-extract" / "bin" / "python3")
DRIVER = str(ROOT / "scripts" / "llm-extract" / "driver.py")
PDFS_ROOT = Path("/Volumes/One Touch/Indian Liberals/PDFs-by-publisher")
BAKE_DIR = ROOT / "data" / "bake-off-output"
PROGRESS_TSV = Path("/tmp/v1.5-overnight-progress.tsv")

# Committer-thread config (auto-commit + auto-push as MDs accumulate).
COMMIT_BATCH_SIZE = 20
COMMIT_POLL_INTERVAL_S = 60
PW_DIR_REL = "apps/site/src/content/primary-works"
COMMIT_LOG = Path("/tmp/v1.5-overnight-commits.tsv")

# `claude -p` config
CLAUDE_TIMEOUT_S = 600  # 10 min per LLM call (generous; most should finish in 1-2 min)
CLAUDE_ALLOWED_TOOLS = "Read,Write"

# Rate-limit detection patterns. Match anywhere in stderr/stdout (case-insensitive).
RATE_LIMIT_PATTERNS = re.compile(
    r"(rate.?limit|usage.?limit|quota.?exceeded|too.?many.?requests"
    r"|5-?hour|weekly.?limit|limit.?reached|429|please.?try.?again|"
    r"capacity|throttle|out.?of.?extra.?usage)",
    re.I,
)

# Anthropic's CLI error format: "resets 4:10am (Asia/Calcutta)" or "resets 04:10 (UTC)".
# We capture HH(:MM)? and an optional am/pm and an optional timezone name in parens.
RESET_TIME_PATTERN = re.compile(
    r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:\(([^)]+)\))?",
    re.I,
)


def parse_reset_seconds(text: str) -> float | None:
    """Parse 'resets 4:10am (Asia/Calcutta)' style strings from claude CLI errors.
    Returns seconds-until-reset (with a 30s safety buffer), or None if not parseable.
    """
    m = RESET_TIME_PATTERN.search(text or "")
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = (m.group(3) or "").lower()
    tzname = m.group(4) or "Asia/Calcutta"  # default to IST since that's our user's TZ
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    try:
        import zoneinfo  # py3.9+
        tz = zoneinfo.ZoneInfo(tzname)
    except Exception:
        # Fallback: assume IST
        try:
            tz = zoneinfo.ZoneInfo("Asia/Calcutta")
        except Exception:
            return None
    now = time.time()
    from datetime import datetime, timedelta
    now_dt = datetime.fromtimestamp(now, tz=tz)
    target = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_dt:
        target += timedelta(days=1)  # reset is tomorrow at HH:MM
    secs = (target.timestamp() - now) + 30  # 30s buffer past the reset
    if secs < 0 or secs > 25 * 3600:  # sanity
        return None
    return secs


def _parse_untracked_mds(stdout: str) -> list[str]:
    """Parse the output of `git ls-files --others --exclude-standard`; return only .md files.

    Handles empty input, whitespace-only input, and trailing blank lines safely.
    Returns paths in the order they appear in the input.
    """
    if not stdout or not stdout.strip():
        return []
    return [line for line in stdout.split("\n") if line.endswith(".md")]


def _build_commit_message(*, batch_no: int, count: int, prior_total: int, last_batch: bool) -> str:
    """Format the commit message for one committer batch."""
    suffix = " (final flush)" if last_batch else ""
    return (
        f"data(primary-works): extraction batch {batch_no} — {count} new MDs{suffix}\n"
        f"\n"
        f"Running total this run: {prior_total + count}.\n"
        f"Source: v1.5 extraction pipeline (run_overnight.py).\n"
    )


def _commit_and_push(untracked: list[str], *, batch_no: int, prior_total: int, last_batch: bool) -> None:
    """Stage the given files, commit with a generated message, and push to origin/main.

    Failure modes:
      - git add fails → CalledProcessError propagates (committer thread catches it).
      - git commit fails (e.g., pre-commit hook) → CalledProcessError propagates.
      - git push fails (network, auth, conflict) → logged; commit remains locally; pipeline continues.
    """
    subprocess.run(["git", "add", "--"] + untracked, cwd=ROOT, check=True)
    msg = _build_commit_message(
        batch_no=batch_no, count=len(untracked),
        prior_total=prior_total, last_batch=last_batch,
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    push = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    push_status = "pushed" if push.returncode == 0 else f"push-failed: {push.stderr[:100].strip()}"
    with COMMIT_LOG.open("a") as f:
        f.write(
            f"{int(time.time())}\t{batch_no}\t{len(untracked)}\t"
            f"{prior_total + len(untracked)}\t{push_status}\n"
        )
    print(f"[committer] batch {batch_no}: {len(untracked)} MDs → {push_status}", flush=True)


def committer_thread(stop_event: threading.Event) -> None:
    """Wake every COMMIT_POLL_INTERVAL_S; commit + push when ≥ COMMIT_BATCH_SIZE new MDs exist.

    Idempotent and crash-safe: each poll independently re-discovers untracked MDs via
    `git ls-files --others`. If the committer dies mid-iteration, the next launch picks
    up where it left off (untracked MDs persist; nothing is lost).

    On stop_event.set(), runs a final flush — any remaining untracked .md gets one
    last commit even if the batch threshold isn't reached.
    """
    total_committed = 0
    batch_number = 0
    while not stop_event.is_set():
        try:
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "--", PW_DIR_REL],
                capture_output=True, text=True, cwd=ROOT, check=True,
            )
            untracked = _parse_untracked_mds(result.stdout)
            if len(untracked) >= COMMIT_BATCH_SIZE:
                batch_number += 1
                _commit_and_push(
                    untracked, batch_no=batch_number,
                    prior_total=total_committed, last_batch=False,
                )
                total_committed += len(untracked)
        except subprocess.CalledProcessError as e:
            print(f"[committer] git error: {e}; will retry next poll", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[committer] unexpected: {e!r}", file=sys.stderr, flush=True)
        stop_event.wait(COMMIT_POLL_INTERVAL_S)

    # Final flush — commit any leftover < COMMIT_BATCH_SIZE MDs on shutdown.
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", PW_DIR_REL],
            capture_output=True, text=True, cwd=ROOT, check=True,
        )
        untracked = _parse_untracked_mds(result.stdout)
        if untracked:
            batch_number += 1
            _commit_and_push(
                untracked, batch_no=batch_number,
                prior_total=total_committed, last_batch=True,
            )
            total_committed += len(untracked)
    except Exception as e:
        print(f"[committer-final-flush] {e!r}", file=sys.stderr, flush=True)
    print(f"[committer] exiting; total MDs committed this run: {total_committed}", flush=True)


# Circuit breaker — pauses ALL workers if we suspect a rate-limit storm.
class CircuitBreaker:
    """Thread-safe gate. Workers block on `.wait_if_open()` until `.close()` is called.

    Trip condition: 5+ consecutive failures in <60s OR an explicit rate-limit signal.
    On trip: pause for `pause_minutes` (default 30 min), then probe; if probe succeeds,
    close the breaker and resume.
    """

    def __init__(self, pause_minutes: float = 30.0, fail_threshold: int = 5, fail_window_s: float = 60.0):
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._event.set()  # initially closed (gate open, workers proceed)
        self._recent_failures: list[float] = []
        self._pause_minutes = pause_minutes
        self._fail_threshold = fail_threshold
        self._fail_window_s = fail_window_s
        self._tripped_count = 0

    def record_success(self) -> None:
        with self._lock:
            self._recent_failures.clear()

    def record_failure(self, reason: str = "") -> None:
        """Returns True if the failure tripped the breaker."""
        with self._lock:
            now = time.time()
            self._recent_failures = [t for t in self._recent_failures if now - t < self._fail_window_s]
            self._recent_failures.append(now)
            if len(self._recent_failures) >= self._fail_threshold and self._event.is_set():
                self._trip(reason or f"{len(self._recent_failures)} consecutive failures in {self._fail_window_s}s")

    def record_rate_limit(self, reason: str = "", reset_seconds: float | None = None) -> None:
        """Explicit rate-limit signal — trip immediately.
        If `reset_seconds` is provided (parsed from the CLI error), sleep exactly that long
        instead of the default pause_minutes.
        """
        with self._lock:
            if self._event.is_set():
                self._trip(f"rate-limit signal detected: {reason}", sleep_seconds=reset_seconds)

    def _trip(self, reason: str, sleep_seconds: float | None = None) -> None:
        """Caller must hold _lock."""
        self._event.clear()
        self._tripped_count += 1
        secs = sleep_seconds if sleep_seconds is not None else self._pause_minutes * 60
        mins = secs / 60.0
        log_progress("__BREAKER_TRIP__", "PAUSED", f"#{self._tripped_count}: {reason}; sleeping {mins:.1f}min")
        # Schedule a background thread to wait + probe + resume
        t = threading.Thread(target=self._wait_and_probe, args=(secs,), daemon=True)
        t.start()

    def _wait_and_probe(self, sleep_seconds: float) -> None:
        time.sleep(sleep_seconds)
        log_progress("__BREAKER_RESUME__", "RESUMING", f"after {sleep_seconds/60.0:.1f}min pause")
        with self._lock:
            self._recent_failures.clear()
            self._event.set()

    def wait_if_open(self) -> None:
        """Block until the gate is open (closed = not tripped)."""
        self._event.wait()


_BREAKER = CircuitBreaker()


def list_unbaked_pdfs() -> list[str]:
    """Return relative PDF paths (from PDFS_ROOT) that haven't been baked yet."""
    baked = set()
    if BAKE_DIR.exists():
        for sub in BAKE_DIR.iterdir():
            if sub.is_dir() and (
                (sub / "metadata.a.a.json").exists() or (sub / "final.json").exists()
            ):
                baked.add(sub.name)
    pdfs = []
    for p in sorted(PDFS_ROOT.rglob("*.pdf")):
        if p.name.startswith("._"):
            continue
        slug = p.stem
        if slug in baked:
            continue
        pdfs.append(str(p.relative_to(PDFS_ROOT)))
    return pdfs


def log_progress(slug: str, status: str, note: str = "") -> None:
    ts = int(time.time())
    line = f"{ts}\t{slug}\t{status}\t{note}\n"
    with open(PROGRESS_TSV, "a") as f:
        f.write(line)
    print(line.rstrip(), flush=True)


def prep_one(pdf_rel: str, job: str, sc_run: str | None) -> Path | None:
    """Call driver.py prep, return the request_dir as a Path."""
    args = [
        VENV_PY, DRIVER, "prep", pdf_rel,
        "--job", job,
        "--pages-wanted", "20",
    ]
    if sc_run:
        args += ["--self-consistency-run", sc_run]
    if job == "summary":
        args += ["--chunk-idx", "0"]
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    except subprocess.TimeoutExpired:
        return None
    for line in r.stdout.splitlines():
        if "Request dir:" in line:
            return Path(line.split("Request dir:")[1].strip())
    return None


def claude_dispatch(request_dir: Path, job_label: str) -> bool:
    """Run a headless `claude -p` against the request_dir. Returns True if response.json was written.

    `job_label` is a short string (metadata.a / metadata.b / summary) used in the prompt
    for the agent's self-context.

    Side effects: records success/failure with the global circuit breaker. Workers block
    on `_BREAKER.wait_if_open()` before issuing the claude -p call, so a tripped breaker
    pauses all in-flight dispatches until the breaker auto-closes after its pause window.
    """
    resp_path = request_dir / "response.json"
    # If response already exists and is non-trivial, skip (idempotent re-runs).
    if resp_path.exists() and resp_path.stat().st_size > 100:
        return True

    # Block here if the circuit breaker is tripped (rate-limit storm).
    _BREAKER.wait_if_open()

    prompt = (
        f"You are an extraction worker for the v1.5 Indian Liberals corpus pipeline.\n"
        f"\n"
        f"TASK: Read the prompt files and page images in {request_dir}/, then write the JSON output.\n"
        f"\n"
        f"STEPS:\n"
        f"1. Read {request_dir}/system.txt (the SYSTEM block of the {job_label} prompt — schema + rules).\n"
        f"2. Read {request_dir}/user.txt (the USER block with metadata, authority subset, theme vocab, etc.).\n"
        f"3. Read all page images: {request_dir}/page-001.jpg, page-002.jpg, ... (whatever exists in that directory).\n"
        f"4. Produce JSON exactly matching the schema in system.txt. Follow every rule literally.\n"
        f"5. Write the JSON to EXACTLY this path: {request_dir}/response.json\n"
        f"\n"
        f"OUTPUT: JSON only. No preamble. No markdown fence. No explanation.\n"
        f"\n"
        f"After writing the file, reply with a single line: 'DONE' (or 'FAILED: <reason>' if you couldn't produce valid JSON).\n"
    )
    cmd = [
        "claude", "-p",
        "--dangerously-skip-permissions",
        "--add-dir", str(request_dir),
        "--allowed-tools", CLAUDE_ALLOWED_TOOLS,
    ]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        _BREAKER.record_failure("timeout")
        return False
    except Exception as e:
        _BREAKER.record_failure(f"exception: {e!s:50}")
        return False

    # Rate-limit detection: scan stderr + stdout for known patterns.
    if result.returncode != 0:
        combined = (result.stderr or "") + " " + (result.stdout or "")
        m = RATE_LIMIT_PATTERNS.search(combined)
        if m:
            reset_secs = parse_reset_seconds(combined)
            reason = f"matched '{m.group(0)}' in claude -p output"
            if reset_secs is not None:
                reason += f"; reset in {reset_secs/60.0:.1f}min"
            _BREAKER.record_rate_limit(reason, reset_seconds=reset_secs)
        else:
            _BREAKER.record_failure(f"exit {result.returncode}: {combined[:120]!r}")
        return False

    # Check response file actually got written
    ok = resp_path.exists() and resp_path.stat().st_size > 100
    if ok:
        _BREAKER.record_success()
    else:
        _BREAKER.record_failure("no response.json written")
    return ok


def collect_one(pdf_rel: str, request_dir: Path, job: str, sc_run: str | None) -> bool:
    """Call driver.py collect. Returns True if collect succeeded."""
    args = [
        VENV_PY, DRIVER, "collect",
        "--request-dir", str(request_dir),
        "--pdf", pdf_rel,
        "--job", job,
        "--prompt-version", "v1.5",
        "--response-file", str(request_dir / "response.json"),
    ]
    if sc_run:
        args += ["--self-consistency-run", sc_run]
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0


def process_pdf(pdf_rel: str) -> dict:
    """Full prep → dispatch → collect cycle for one PDF.

    Returns {slug, status, note} with status one of: OK | PREP_FAILED | META_FAILED |
    SUMMARY_FAILED | COLLECT_FAILED.
    """
    slug = Path(pdf_rel).stem
    t0 = time.time()

    # 1. Prep three jobs
    rdirs = {}
    for job, sc in [("metadata.a", "a"), ("metadata.b", "b"), ("summary", None)]:
        rd = prep_one(pdf_rel, job, sc)
        if not rd:
            log_progress(slug, "PREP_FAILED", job)
            return {"slug": slug, "status": "PREP_FAILED", "note": job}
        rdirs[job] = rd

    # 2. Dispatch meta.a + meta.b in parallel
    with ThreadPoolExecutor(max_workers=2) as inner:
        futs = {
            inner.submit(claude_dispatch, rdirs["metadata.a"], "metadata.a"): "metadata.a",
            inner.submit(claude_dispatch, rdirs["metadata.b"], "metadata.b"): "metadata.b",
        }
        meta_results = {futs[f]: f.result() for f in as_completed(futs)}
    for job, ok in meta_results.items():
        if not ok:
            log_progress(slug, "META_FAILED", job)
            return {"slug": slug, "status": "META_FAILED", "note": job}

    # 3. Collect both metadata
    for job, sc in [("metadata.a", "a"), ("metadata.b", "b")]:
        if not collect_one(pdf_rel, rdirs[job], job, sc):
            log_progress(slug, "COLLECT_FAILED", job)
            return {"slug": slug, "status": "COLLECT_FAILED", "note": job}

    # 4. Dispatch summary
    if not claude_dispatch(rdirs["summary"], "summary"):
        log_progress(slug, "SUMMARY_FAILED")
        return {"slug": slug, "status": "SUMMARY_FAILED"}

    # 5. Collect summary (auto-emits Astro MD via the v1.5 patch in driver.py)
    if not collect_one(pdf_rel, rdirs["summary"], "summary", None):
        log_progress(slug, "COLLECT_FAILED", "summary")
        return {"slug": slug, "status": "COLLECT_FAILED", "note": "summary"}

    elapsed = int(time.time() - t0)
    log_progress(slug, "OK", f"{elapsed}s")
    return {"slug": slug, "status": "OK", "note": f"{elapsed}s"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=12, help="parallel PDFs to process")
    ap.add_argument("--smoke", type=int, default=0, help="process only first N PDFs (smoke test)")
    ap.add_argument("--shard-file", help="optional /tmp/v1.5-shards/shard-NN.json path; defaults to all unbaked")
    args = ap.parse_args()

    if args.shard_file:
        pdfs = json.load(open(args.shard_file))["pdfs"]
    else:
        pdfs = list_unbaked_pdfs()

    if args.smoke > 0:
        pdfs = pdfs[: args.smoke]
        print(f"SMOKE MODE: processing first {len(pdfs)} PDFs only.")

    print(f"Starting overnight extraction. PDFs in queue: {len(pdfs)}. Concurrency: {args.concurrency}.")
    print(f"Progress: {PROGRESS_TSV}")
    log_progress("__START__", "BEGIN", f"queue={len(pdfs)} concurrency={args.concurrency}")

    t0 = time.time()
    ok = fail = 0
    fail_modes: dict[str, int] = {}

    stop_event = threading.Event()
    committer = threading.Thread(target=committer_thread, args=(stop_event,), daemon=True)
    committer.start()
    print(f"[main] committer thread started (batch size {COMMIT_BATCH_SIZE}, "
          f"poll every {COMMIT_POLL_INTERVAL_S}s)", flush=True)

    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(process_pdf, p): p for p in pdfs}
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                except Exception as e:
                    r = {"slug": futs[fut], "status": "EXCEPTION", "note": str(e)[:100]}
                if r["status"] == "OK":
                    ok += 1
                else:
                    fail += 1
                    fail_modes[r["status"]] = fail_modes.get(r["status"], 0) + 1
    finally:
        print("[main] signaling committer to flush + exit...", flush=True)
        stop_event.set()
        committer.join(timeout=120)

    elapsed = int(time.time() - t0)
    log_progress("__END__", "DONE", f"ok={ok} fail={fail} elapsed_s={elapsed}")
    print(f"\n=== Overnight run complete ===")
    print(f"  Total: {ok + fail}, OK: {ok}, Failed: {fail}")
    print(f"  Failure modes: {fail_modes}")
    print(f"  Wall-clock: {elapsed//3600}h {(elapsed%3600)//60}m")


if __name__ == "__main__":
    main()
