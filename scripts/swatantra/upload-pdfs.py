#!/usr/bin/env python3
"""Upload the Swatantra Party PDFs to R2, resumably.

Mirrors the pattern scripts/fulltext/README.md describes for the search bundle:
parallel wrangler puts, with a ledger so a killed run resumes instead of
re-uploading 4.3 GB.

Object keys are `<prefix>/<slug>.pdf`, slug derived by ocr-pages.slugify — the
same function the OCR layer uses, so `corpus.jsonl` keys and R2 object keys are
guaranteed identical. That join is the whole point; if they drift, the search
index points at objects that do not exist.

    python3 scripts/swatantra/upload-pdfs.py <corpus-dir> [--prefix ...]
                                             [--jobs 8] [--limit N] [--dry-run]

Ledger: data/swatantra-papers/uploaded-pdfs.tsv  (key<TAB>bytes<TAB>status)
"""
import argparse
import concurrent.futures as futures
import importlib.util
import os
import subprocess
import sys
import time
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "data/swatantra-papers/uploaded-pdfs.tsv"
BUCKET = "indianliberals-archive"

# Reuse the OCR module's slugify so keys cannot diverge between the two layers.
_spec = importlib.util.spec_from_file_location("ocrmod", Path(__file__).parent / "ocr-pages.py")
_ocr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ocr)
slugify = _ocr.slugify

_lock = threading.Lock()


def load_ledger():
    done = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[2] == "ok":
                done.add(parts[0])
    return done


def record(key, size, status):
    with _lock:
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(f"{key}\t{size}\t{status}\n")


def put(path, key, attempts=3):
    """Upload with retries.

    R2 returns a transient 500 ("We encountered an internal error. Please try
    again.") often enough to matter at 6,355 objects — one showed up in the
    first 1,500. A plain retry clears it. Puts are idempotent, so retrying is
    always safe.
    """
    last = ""
    for attempt in range(attempts):
        if attempt:
            time.sleep(2 ** attempt)
        ok, last = _put_once(path, key)
        if ok:
            record(key, path.stat().st_size, "ok")
            return key, True, None
    record(key, path.stat().st_size, "fail")
    return key, False, [last]


def _put_once(path, key):
    try:
        proc = subprocess.run(
            ["npx", "wrangler", "r2", "object", "put", f"{BUCKET}/{key}",
             "--file", str(path), "--content-type", "application/pdf", "--remote"],
            capture_output=True, text=True, timeout=300, cwd=str(REPO),
        )
        ok = proc.returncode == 0 and "Upload complete" in (proc.stdout + proc.stderr)
        tail = (proc.stderr or proc.stdout).strip().splitlines()
        return ok, (tail[-1] if tail else "")
    except subprocess.TimeoutExpired:
        return False, "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_dir")
    ap.add_argument("--prefix", default="swatantra-party-papers")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    done = load_ledger()
    names = sorted(f for f in os.listdir(a.corpus_dir) if f.lower().endswith(".pdf"))
    if a.limit:
        names = names[:a.limit]

    jobs = []
    collisions = {}
    for n in names:
        key = f"{a.prefix}/{slugify(n)}.pdf"
        if key in collisions:
            print(f"KEY COLLISION: {n!r} and {collisions[key]!r} -> {key}", file=sys.stderr)
        collisions[key] = n
        if key not in done:
            jobs.append((Path(a.corpus_dir) / n, key))

    total_bytes = sum(p.stat().st_size for p, _ in jobs)
    print(f"{len(names)} PDFs, {len(done)} already uploaded, {len(jobs)} to go "
          f"({total_bytes/1e9:.2f} GB)", file=sys.stderr)
    if a.dry_run:
        for p, k in jobs[:10]:
            print(f"  would put {k}")
        print("(dry run)")
        return 0
    if not jobs:
        print("nothing to do")
        return 0

    ok = fail = 0
    with futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(put, p, k) for p, k in jobs]
        for i, fut in enumerate(futures.as_completed(futs), 1):
            key, good, err = fut.result()
            ok += good
            fail += (not good)
            if not good:
                print(f"  FAIL {key}: {err[0] if err else ''}", file=sys.stderr)
            if i % 50 == 0:
                print(f"  {i}/{len(jobs)}  ok={ok} fail={fail}", file=sys.stderr, flush=True)
    print(f"done: {ok} uploaded, {fail} failed. ledger: {LEDGER}", file=sys.stderr)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
