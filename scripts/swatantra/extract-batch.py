#!/usr/bin/env python3
"""Batch extraction over the Swatantra papers, dispatched by the orchestrating session.

`run_overnight.py` needs a working `claude -p`; this path uses in-session
subagents instead, so it needs no CLI auth. The tradeoff is that dispatch only
happens while a turn is running, so work proceeds in batches rather than
unattended.

Disk is the binding constraint: rasterising all 22,757 pages at once would be
~5-6 GB of JPEGs against ~10 GB free. So each request directory is deleted as
soon as its response is collected — peak usage stays at one batch, a few tens
of MB, no matter how many batches run.

    prepare  — rasterise the next N unfinished works, emit dispatch lines
    collect  — validate responses, write records, DELETE the image dirs
    status   — how far along the corpus is

    python3 scripts/swatantra/extract-batch.py prepare --n 12
    python3 scripts/swatantra/extract-batch.py collect
    python3 scripts/swatantra/extract-batch.py status
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = Path(os.environ.get(
    "LLM_EXTRACT_PDF_ROOT",
    "/Users/siraj/Library/CloudStorage/GoogleDrive-adnan@thothica.com/"
    ".shortcut-targets-by-id/1vDrOqgdnQHTfL5vqJtx-ZRy4e2jf-Bcq/Swatantra Party papers"))
OUT = REPO / "data/swatantra-papers/extraction"
STATE = REPO / "data/swatantra-papers/extraction-state.json"  # NOT inside OUT:
# records are globbed from OUT, so state must not live among them.
VENV = REPO / ".venv-extract/bin/python3"
DRIVER = REPO / "scripts/llm-extract/driver.py"
INVENTORY = REPO / "data/swatantra-papers/inventory.tsv"
JOBS = ("metadata.a", "metadata.b")


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"done": {}, "failed": {}, "pending": {}}


def save_state(st):
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")


def all_files():
    return [r["file"] for r in csv.DictReader(
        open(INVENTORY, encoding="utf-8"), delimiter="\t")]


def prep(pdf_name, job):
    """Run driver.py prep; return the request dir it created."""
    env = dict(os.environ, LLM_EXTRACT_PDF_ROOT=str(CORPUS))
    r = subprocess.run(
        [str(VENV), str(DRIVER), "prep", pdf_name, "--job", job, "--pages-wanted", "20"],
        capture_output=True, text=True, cwd=str(REPO), env=env, timeout=180)
    for line in r.stdout.splitlines():
        if "Request dir:" in line:
            return line.split("Request dir:")[1].strip()
    return None


def cmd_prepare(a):
    st = load_state()
    todo = [f for f in all_files()
            if f not in st["done"] and f not in st["pending"]][:a.n]
    if not todo:
        print("nothing left to prepare")
        return 0
    for name in todo:
        dirs = {}
        for job in JOBS:
            d = prep(name, job)
            if d:
                dirs[job] = d
        if len(dirs) == len(JOBS):
            st["pending"][name] = dirs
            for job, d in dirs.items():
                n_img = len(list(Path(d).glob("page-*.jpg")))
                print(f"{name}\t{job}\t{d}\t{n_img}")
        else:
            st["failed"][name] = "prep_failed"
            print(f"PREP FAILED\t{name}", file=sys.stderr)
    save_state(st)
    print(f"# prepared {len(st['pending'])} works, {len(JOBS)} dispatches each",
          file=sys.stderr)
    return 0


def cmd_collect(a):
    """Validate any response.json, store the record, then delete the images."""
    st = load_state()
    OUT.mkdir(parents=True, exist_ok=True)
    collected = freed = 0
    still_pending = {}

    for name, dirs in st["pending"].items():
        records = {}
        for job, d in dirs.items():
            rp = Path(d) / "response.json"
            if not rp.exists():
                continue
            try:
                records[job] = json.loads(rp.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                st["failed"][name] = f"{job}: bad json: {e}"

        if len(records) == len(JOBS):
            (OUT / f"{Path(name).stem}.json").write_text(
                json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")
            st["done"][name] = {"jobs": list(records)}
            collected += 1
            # Delete the rasterised pages now — this is what keeps peak disk
            # at one batch instead of the whole corpus.
            for d in dirs.values():
                p = Path(d)
                if p.exists():
                    freed += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                    shutil.rmtree(p, ignore_errors=True)
        else:
            still_pending[name] = dirs

    st["pending"] = still_pending
    save_state(st)
    print(f"collected {collected} works, freed {freed/1e6:.1f} MB of page images, "
          f"{len(still_pending)} still awaiting responses")
    return 0


def cmd_status(a):
    st = load_state()
    total = len(all_files())
    done, pend, fail = len(st["done"]), len(st["pending"]), len(st["failed"])
    print(f"corpus   : {total}")
    print(f"  done   : {done} ({done/total*100:.1f}%)")
    print(f"  pending: {pend}")
    print(f"  failed : {fail}")
    req = Path("/tmp/llm-extract-requests")
    if req.exists():
        sz = sum(f.stat().st_size for f in req.rglob("*") if f.is_file())
        print(f"  request dirs on disk: {sz/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--n", type=int, default=12)
    sub.add_parser("collect")
    sub.add_parser("status")
    args = ap.parse_args()
    sys.exit({"prepare": cmd_prepare, "collect": cmd_collect,
              "status": cmd_status}[args.cmd](args))
