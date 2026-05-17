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
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/Users/siraj/Indian Liberals Website")
VENV_PY = str(ROOT / ".venv-extract" / "bin" / "python3")
DRIVER = str(ROOT / "scripts" / "llm-extract" / "driver.py")
PDFS_ROOT = Path("/Volumes/One Touch/Indian Liberals/PDFs-by-publisher")
BAKE_DIR = ROOT / "data" / "bake-off-output"
PROGRESS_TSV = Path("/tmp/v1.5-overnight-progress.tsv")

# `claude -p` config
CLAUDE_TIMEOUT_S = 600  # 10 min per LLM call (generous; most should finish in 1-2 min)
CLAUDE_ALLOWED_TOOLS = "Read,Write"


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
    """
    resp_path = request_dir / "response.json"
    # If response already exists and is non-trivial, skip (idempotent re-runs).
    if resp_path.exists() and resp_path.stat().st_size > 100:
        return True

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
        subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False
    return resp_path.exists() and resp_path.stat().st_size > 100


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
    ap.add_argument("--concurrency", type=int, default=8, help="parallel PDFs to process")
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

    elapsed = int(time.time() - t0)
    log_progress("__END__", "DONE", f"ok={ok} fail={fail} elapsed_s={elapsed}")
    print(f"\n=== Overnight run complete ===")
    print(f"  Total: {ok + fail}, OK: {ok}, Failed: {fail}")
    print(f"  Failure modes: {fail_modes}")
    print(f"  Wall-clock: {elapsed//3600}h {(elapsed%3600)//60}m")


if __name__ == "__main__":
    main()
