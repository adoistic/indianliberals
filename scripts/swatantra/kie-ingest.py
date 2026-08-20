#!/usr/bin/env python3
"""Production extraction of the Swatantra papers via kie.ai / gpt-5-6-luna.

One metadata pass, not two. The second self-consistency pass was dropped after
measurement: the Opus tiebreak it feeds has never once been dispatched (zero
tiebreak records across 1,177 works, and merge-extraction.py says so in its own
docstring), and the disagreement flag it produces fires on 45% of works — half
of those on `publisher_verbatim` alone, where the two passes differ over
whether to keep a street address. A flag that fires on half the corpus and
routes nowhere is not worth a third of the budget.

Writes straight into data/bake-off-output/<slug>/ in the same shape the baked
Sonnet corpus uses, so merge-extraction.py consumes it unchanged.

Disk is the binding constraint, as it was for OCR: 22,757 pages of JPEG is
5-6 GB against ~10 GB free, so each work's rasterised pages are deleted the
moment its records are written. Peak usage is one batch, not the corpus.

    python3 scripts/swatantra/kie-ingest.py --jobs 8
    python3 scripts/swatantra/kie-ingest.py --jobs 8 --limit 50   # trial slice
    python3 scripts/swatantra/kie-ingest.py --status
"""
import argparse
import base64
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/llm-extract"))
from validator import validate_metadata  # noqa: E402

# Two ways to reach the PDFs. Local is the Google Drive mount; r2 is the copy
# already published at archive.indianliberals.in, which is served publicly and
# needs no credentials — that is what makes running this off the laptop
# possible at all. Every one of the 6,355 inventory rows resolves to a key
# that exists on R2 (verified), so the two sources are interchangeable.
CORPUS = os.environ.get("LLM_EXTRACT_PDF_ROOT",
    "/Users/siraj/Library/CloudStorage/GoogleDrive-adnan@thothica.com/"
    ".shortcut-targets-by-id/1vDrOqgdnQHTfL5vqJtx-ZRy4e2jf-Bcq/"
    "Swatantra Party papers")
R2_BASE = os.environ.get("SWATANTRA_R2_BASE",
                         "https://archive.indianliberals.in/swatantra-party-papers")
# Where extraction records land. The cloud run wrote into its own tree and
# that tree is what got rsynced back, so a retry has to be pointed at it
# rather than at the laptop's original bake directory.
BAKE = Path(os.environ.get("KIE_BAKE_ROOT", REPO / "data/bake-off-output"))
# The work list. Overridable so the same retry machinery can be pointed at a
# neighbouring corpus (the Forum booklets live under a different R2 prefix
# and have no row in the Swatantra inventory).
INVENTORY = Path(os.environ.get(
    "KIE_INVENTORY", REPO / "data/swatantra-papers/inventory.tsv"))
PIN_THINKERS = REPO / "data/swatantra-papers/pin-thinkers.json"
ADDENDUM = REPO / "scripts/llm-extract/prompts/metadata-weak-model-addendum.md"
# On the laptop this is the extraction venv; on a cloud box there is no venv
# and the interpreter is just `python3`. driver.py is invoked as a subprocess,
# so it must be told which interpreter to use.
VENV = os.environ.get("LLM_EXTRACT_PYTHON", str(REPO / ".venv-extract/bin/python3"))
DRIVER = REPO / "scripts/llm-extract/driver.py"
PROGRESS = REPO / "data/swatantra-papers/kie-ingest-progress.tsv"
UNPARSEABLE = REPO / "data/swatantra-papers/kie-unparseable"
FETCH_DIR = Path(os.environ.get("SWATANTRA_FETCH_DIR", "/tmp/swatantra-pdfs"))
ENDPOINT = "https://api.kie.ai/codex/v1/responses"
MODEL = "gpt-5-6-luna"

_lock = threading.Lock()
_stats = {"ok": 0, "fail": 0, "credits": 0.0, "t0": time.time()}


class Breaker:
    """kie can fail wholesale, not just per-request — the Claude route went
    down for every request including ones that had just succeeded. Retrying
    into a dead endpoint burns hours, so consecutive failures across workers
    pause everyone rather than each worker discovering it alone."""

    def __init__(self, trip=12, pause=300):
        self.trip, self.pause = trip, pause
        self.consecutive = 0
        self.gate = threading.Event()
        self.gate.set()
        self.lk = threading.Lock()

    def ok(self):
        with self.lk:
            self.consecutive = 0

    def fail(self):
        with self.lk:
            self.consecutive += 1
            if self.consecutive >= self.trip and self.gate.is_set():
                self.gate.clear()
                log(f"!! {self.consecutive} consecutive failures — pausing "
                    f"{self.pause}s (endpoint likely down)")
                threading.Timer(self.pause, self._resume).start()

    def _resume(self):
        with self.lk:
            self.consecutive = 0
        self.gate.set()
        log("!! resuming after pause")

    def wait(self):
        self.gate.wait()


BREAKER = Breaker()


def log(msg):
    with _lock:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def api_key():
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("KIE_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("KIE_API_KEY not found in .env")


def remaining(skip_file=None):
    """Works with no metadata record yet. Smallest first: the cheap, fast,
    high-yield end of the corpus lands before anything can go wrong.

    `skip_file` carries the slugs already extracted elsewhere. A cloud runner
    starts with an empty output dir, so without it the box would happily
    re-extract and re-pay for every work the laptop already finished.
    """
    done = set()
    if skip_file and Path(skip_file).is_file():
        done = set(json.loads(Path(skip_file).read_text(encoding="utf-8")))
    rows = list(csv.DictReader(open(INVENTORY, encoding="utf-8"), delimiter="\t"))
    todo = []
    for r in rows:
        slug = os.path.splitext(r["file"])[0]
        if slug in done or (BAKE / slug / "metadata.a.a.json").exists():
            continue
        todo.append((int(r["pages"]), r["file"]))
    todo.sort()
    return [f for _, f in todo]


def missing_summaries():
    """Works whose metadata landed but whose summary did not.

    These are not failed works — the record exists and is usable. Only the
    summary job returned something unparseable, so a retry re-runs that one
    job (do_work skips whatever is already on disk) at about a third of the
    cost of a full re-extraction.
    """
    rows = list(csv.DictReader(open(INVENTORY, encoding="utf-8"), delimiter="\t"))
    todo = []
    for r in rows:
        slug = os.path.splitext(r["file"])[0]
        d = BAKE / slug
        if (d / "metadata.a.a.json").exists() and not (d / "summary.json").exists():
            todo.append((int(r["pages"]), r["file"]))
    todo.sort()
    return [f for _, f in todo]


def _slugify(name):
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return re.sub(r"-{2,}", "-", stem)


def fetch_pdf(pdf_name):
    """Pull one PDF from public R2 into a per-work dir named for the original
    file, so driver.py can be pointed at it unchanged. Returns that dir."""
    d = FETCH_DIR / _slugify(pdf_name)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / pdf_name
    if dest.exists() and dest.stat().st_size > 0:
        return d
    url = f"{R2_BASE}/{_slugify(pdf_name)}.pdf"
    # Cloudflare in front of the archive worker 403s the default
    # `Python-urllib/3.x` agent. An identifying UA is accepted, so declare
    # what we are rather than impersonating a browser.
    req = urllib.request.Request(
        url, headers={"User-Agent": "indianliberals-ingest/1.0 "
                                    "(+https://indianliberals.in)"})
    for attempt in range(4):
        if attempt:
            time.sleep(3 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
            if body[:4] == b"%PDF":
                dest.write_bytes(body)
                return d
        except Exception:                                   # noqa: BLE001
            continue
    return None


def prep(pdf_name, job, pdf_root=None):
    env = dict(os.environ, LLM_EXTRACT_PDF_ROOT=str(pdf_root or CORPUS),
               LLM_EXTRACT_PIN_THINKERS_FILE=str(PIN_THINKERS),
               LLM_EXTRACT_NO_EMIT="1")
    r = subprocess.run(
        [str(VENV), str(DRIVER), "prep", pdf_name, "--job", job,
         "--pages-wanted", "20"],
        capture_output=True, text=True, cwd=str(REPO), env=env, timeout=600)
    for line in r.stdout.splitlines():
        if "Request dir:" in line:
            return Path(line.split("Request dir:")[1].strip())
    return None


def post(system_text, user_text, images, key, attempts=4):
    content = [{"type": "input_image",
                "image_url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}
               for b in images]
    content.append({"type": "input_text", "text": user_text})
    body = json.dumps({
        "model": MODEL, "stream": False,
        "instructions": system_text,      # replaces kie's default Codex prompt
        "input": [{"role": "user", "content": content}],
        "reasoning": {"effort": "low"},
    }).encode()

    last = None
    for attempt in range(attempts):
        BREAKER.wait()
        if attempt:
            time.sleep(min(6 * 2 ** attempt, 120))
        req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                p = json.loads(r.read().decode())
            text = "".join(c.get("text", "")
                           for o in p.get("output", []) if o.get("type") == "message"
                           for c in o.get("content", []))
            if text:
                BREAKER.ok()
                return text, p.get("credits_consumed") or 0.0, None
            last = p.get("msg") or "empty response"
        except Exception as e:              # noqa: BLE001 - any failure retries
            last = f"{type(e).__name__}: {str(e)[:80]}"
        BREAKER.fail()
    return None, 0.0, last


# gpt-5-6-luna has one systematic JSON failure, and it accounts for 58 of the
# 59 unparseable responses captured from the first full run. Asked for a
# multi-paragraph summary, it opens the second paragraph as a fresh object
# ENTRY rather than continuing the string:
#
#     {
#       "summary": "First paragraph ...",
#       "The letter also asks Raju to ...",     <- bare string, no key
#       "extent_caveat": false,
#
# That is a string literal sitting where a key/value pair belongs, so the
# whole object is invalid. The content is intact; only the punctuation between
# paragraphs is wrong. Splice such a string onto the preceding value instead of
# discarding the response — re-asking costs a call and loses the paragraph
# anyway, since the model makes the same mistake on the retry about 10% of the
# time. The lookahead is what keeps this safe: a real key is followed by ':',
# so only strings followed by ',' or '}' are treated as runaway paragraphs.
_BARE_STRING = re.compile(r'"\s*,\s*\n\s*"((?:[^"\\]|\\.)*)"(?=\s*[,}])')


def _splice_bare_strings(t):
    prev = None
    while prev != t:
        prev = t
        t = _BARE_STRING.sub(lambda m: " " + m.group(1) + '"', t, count=1)
    return t


def parse_json(t):
    t = (t or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    for candidate in (t, _splice_bare_strings(t)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        i, j = candidate.find("{"), candidate.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(candidate[i:j + 1])
            except json.JSONDecodeError:
                pass
    return None


def record(slug, job, note):
    with _lock:
        with open(PROGRESS, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\t{slug}\t{job}\t{note}\n")


def do_work(pdf_name, key, addendum_text, source="local"):
    slug = Path(pdf_name).stem
    out = BAKE / slug
    credits = 0.0
    fetched = None
    try:
        if source == "r2":
            fetched = fetch_pdf(pdf_name)
            if fetched is None:
                record(slug, "-", "FETCH_FAILED")
                return slug, False, credits
        for job, fname in (("metadata.a", "metadata.a.a.json"),
                           ("summary", "summary.json")):
            if (out / fname).exists():
                continue
            d = prep(pdf_name, job, fetched)
            if not d:
                record(slug, job, "PREP_FAILED")
                return slug, False, credits
            try:
                imgs = [p.read_bytes() for p in sorted(d.glob("page-*.jpg"))]
                sys_t = (d / "system.txt").read_text(encoding="utf-8")
                if job == "metadata.a":
                    sys_t += "\n\n---\n\n" + addendum_text
                usr_t = (d / "user.txt").read_text(encoding="utf-8")
                text, cred, err = post(sys_t, usr_t, imgs, key)
                credits += cred
                if not text:
                    record(slug, job, f"API_FAILED {err}")
                    return slug, False, credits
                parsed = parse_json(text)
                if parsed is None:
                    # Keep the raw response. Without it a retry pass is blind:
                    # prose, a truncated object and a mis-fenced block all look
                    # identical here, and they need different fixes.
                    UNPARSEABLE.mkdir(parents=True, exist_ok=True)
                    (UNPARSEABLE / f"{slug}.{job}.txt").write_text(
                        text, encoding="utf-8")
                    record(slug, job, f"UNPARSEABLE chars={len(text)}")
                    return slug, False, credits
                out.mkdir(parents=True, exist_ok=True)
                (out / fname).write_text(
                    json.dumps(validate_metadata(parsed), indent=2, ensure_ascii=False),
                    encoding="utf-8")
                record(slug, job, f"ok cred={cred}")
            finally:
                shutil.rmtree(d, ignore_errors=True)   # reap pages immediately
        return slug, True, credits
    except Exception as e:                              # noqa: BLE001
        record(slug, "-", f"EXCEPTION {type(e).__name__}: {str(e)[:80]}")
        return slug, False, credits
    finally:
        if fetched is not None:
            shutil.rmtree(fetched, ignore_errors=True)      # reap the PDF too


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--skip-file", help="JSON array of slugs already extracted")
    ap.add_argument("--source", default="local", choices=["local", "r2"],
                    help="local Drive mount, or fetch PDFs from public R2")
    ap.add_argument("--retry-summaries", action="store_true",
                    help="re-run only the summary job for works that have "
                         "metadata but no summary")
    a = ap.parse_args()

    todo = missing_summaries() if a.retry_summaries else remaining(a.skip_file)
    if a.status:
        total = sum(1 for _ in csv.DictReader(open(INVENTORY, encoding="utf-8"),
                                              delimiter="\t"))
        print(f"corpus {total:,} | done {total-len(remaining(a.skip_file)):,} | "
              f"remaining {len(remaining(a.skip_file)):,} | "
              f"missing summaries {len(missing_summaries()):,}")
        return 0
    if a.limit:
        todo = todo[:a.limit]
    if not todo:
        print("nothing to do")
        return 0

    key = api_key()
    addendum_text = ADDENDUM.read_text(encoding="utf-8")
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    log(f"extracting {len(todo):,} works, {a.jobs} workers, model {MODEL}, "
        f"source={a.source}")

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(do_work, f, key, addendum_text, a.source): f for f in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            slug, ok, cred = fut.result()
            with _lock:
                _stats["ok" if ok else "fail"] += 1
                _stats["credits"] += cred
            if i % 25 == 0 or not ok:
                el = time.time() - _stats["t0"]
                rate = i / el * 3600
                left = (len(todo) - i) / max(rate, 1e-9)
                log(f"{i}/{len(todo)}  ok={_stats['ok']} fail={_stats['fail']}  "
                    f"${_stats['credits']/200:.2f}  {rate:.0f}/h  eta {left:.1f}h"
                    + ("" if ok else f"  <- FAILED {slug[:40]}"))
    log(f"DONE ok={_stats['ok']} fail={_stats['fail']} "
        f"spend=${_stats['credits']/200:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
