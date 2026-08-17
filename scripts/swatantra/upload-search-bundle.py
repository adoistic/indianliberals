#!/usr/bin/env python3
"""Upload a built Pagefind bundle to R2 under `search/`, resumably.

This is the step scripts/fulltext/README.md refers to as "upload_search.sh in
the scratchpad" — parallel wrangler puts with a ledger so an interrupted run
resumes instead of re-uploading ~170 MB across ~9,000 small files.

Content types matter here: the site imports the bundle cross-origin, and a
wrong type on the JS/CSS entrypoints makes the browser refuse them. Pagefind's
own binary shards (.pf_fragment / .pf_index / .pf_meta) are served as
octet-stream, which is what Pagefind's fetch expects.

    python3 scripts/swatantra/upload-search-bundle.py <bundle-dir> [--jobs 6]

Ledger: data/swatantra-papers/uploaded-search.tsv
"""
import argparse
import concurrent.futures as futures
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "data/swatantra-papers/uploaded-search.tsv"
BUCKET = "indianliberals-archive"

CTYPE = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".wasm": "application/wasm",
    ".html": "text/html; charset=utf-8",
}
DEFAULT_CTYPE = "application/octet-stream"

_lock = threading.Lock()


def load_ledger():
    done = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            p = line.split("\t")
            if len(p) >= 2 and p[1] == "ok":
                done.add(p[0])
    return done


def record(key, status):
    with _lock:
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(f"{key}\t{status}\n")


def put(path, key, attempts=3):
    ctype = CTYPE.get(path.suffix.lower(), DEFAULT_CTYPE)
    last = ""
    for attempt in range(attempts):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            proc = subprocess.run(
                ["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{key}",
                 "--file", str(path), "--content-type", ctype, "--remote"],
                capture_output=True, text=True, timeout=300, cwd=str(REPO),
            )
            if proc.returncode == 0 and "Upload complete" in (proc.stdout + proc.stderr):
                record(key, "ok")
                return key, True, None
            tail = (proc.stderr or proc.stdout).strip().splitlines()
            last = tail[-1] if tail else ""
        except subprocess.TimeoutExpired:
            last = "timeout"
    record(key, "fail")
    return key, False, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle_dir")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--prefix", default="search")
    a = ap.parse_args()

    root = Path(a.bundle_dir)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    done = load_ledger()

    jobs = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            key = f"{a.prefix}/{p.relative_to(root).as_posix()}"
            if key not in done:
                jobs.append((p, key))

    total = sum(p.stat().st_size for p, _ in jobs)
    print(f"{len(jobs)} files to upload ({total/1e6:.0f} MB), {len(done)} already done",
          file=sys.stderr)
    if not jobs:
        print("nothing to do", file=sys.stderr)
        return 0

    ok = fail = 0
    with futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(put, p, k) for p, k in jobs]
        for i, f in enumerate(futures.as_completed(futs), 1):
            key, good, err = f.result()
            ok += good
            fail += (not good)
            if not good:
                print(f"  FAIL {key}: {err}", file=sys.stderr)
            if i % 250 == 0:
                print(f"  {i}/{len(jobs)}  ok={ok} fail={fail}", file=sys.stderr, flush=True)
    print(f"done: {ok} uploaded, {fail} failed", file=sys.stderr)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
