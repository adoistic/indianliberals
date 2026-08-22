#!/usr/bin/env python3
"""Render page 1 of each Swatantra PDF to a cover thumbnail.

Every listing on the site — /primary-works/, the series pages, the periodical
runs, the "Related" strips — leads with a cover image. 1,463 of the 1,580
pre-existing works have one; none of the 6,355 Swatantra works did, so the
archive's largest collection showed as a wall of blank tiles.

Matches the existing convention exactly: WebP at
`archive.indianliberals.in/covers/<slug>.webp`, same slug as the work id.

    python3 scripts/swatantra/make-covers.py [--jobs 8] [--limit N] [--width 640]

Resumable: a slug whose .webp already exists on disk is skipped, so a killed
run continues rather than re-rendering thousands of pages.
"""
import argparse
import concurrent.futures as futures
import csv
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INVENTORY = REPO / "data/swatantra-papers/inventory.tsv"
OUT = REPO / "build-artifacts/covers"
R2_BASE = "https://archive.indianliberals.in/swatantra-party-papers"
CORPUS = os.environ.get("LLM_EXTRACT_PDF_ROOT", "")
UA = "indianliberals-covers/1.0 (+https://indianliberals.in)"

_lock = threading.Lock()
_done = {"ok": 0, "skip": 0, "fail": 0}


def slugify(name):
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()


def source_bytes(fname):
    """Local Drive mount if present, else the public R2 copy.

    The R2 path retries and checks what it got. At ten concurrent readers the
    bucket returns short bodies often enough to matter — 2,186 of one run's
    downloads came back truncated, and PDFium reports those as "Data format
    error", which reads like a corrupt archive rather than a bad fetch. A PDF
    always starts %PDF and ends %%EOF, so a truncated body is detectable
    rather than something to hand downstream.
    """
    if CORPUS:
        p = Path(CORPUS) / fname
        if p.is_file():
            return p.read_bytes()
    # R2 keys are the slug, not the archivist's filename — upload-pdfs.py
    # slugified on the way in so the OCR corpus and the bucket could join.
    key = slugify(fname) + ".pdf"
    url = f"{R2_BASE}/{urllib.parse.quote(key)}"
    last = None
    for attempt in range(4):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                declared = r.headers.get("content-length")
                data = r.read()
            if declared and len(data) != int(declared):
                last = f"short body {len(data)}/{declared}"
                continue
            if not data.startswith(b"%PDF") or b"%%EOF" not in data[-2048:]:
                last = "not a complete PDF"
                continue
            return data
        except Exception as e:                                # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
    raise RuntimeError(last or "fetch failed")


def render(fname, width):
    import io
    import pypdfium2 as pdfium
    from PIL import Image
    slug = slugify(fname)
    out = OUT / f"{slug}.webp"
    if out.exists():
        with _lock:
            _done["skip"] += 1
        return
    try:
        data = source_bytes(fname)
        doc = pdfium.PdfDocument(io.BytesIO(data))
        page = doc[0]
        # Scale so the long edge lands near `width`; these scans are mostly
        # foolscap, and a fixed scale would make portrait and landscape
        # thumbnails wildly different sizes in the same grid.
        w, h = page.get_size()
        scale = width / max(w, h)
        img = page.render(scale=scale).to_pil().convert("RGB")
        img.thumbnail((width, width), Image.LANCZOS)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, "WEBP", quality=78, method=4)
        page.close()
        doc.close()
        with _lock:
            _done["ok"] += 1
    except Exception as e:                                    # noqa: BLE001
        with _lock:
            _done["fail"] += 1
            if _done["fail"] <= 5:
                print(f"  FAIL {fname[:60]}: {type(e).__name__}: {str(e)[:70]}",
                      file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(INVENTORY, encoding="utf-8"), delimiter="\t"))
    names = [r["file"] for r in rows]
    if a.limit:
        names = names[: a.limit]
    print(f"rendering {len(names):,} covers -> {OUT.relative_to(REPO)}")
    with futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for i, _ in enumerate(ex.map(lambda n: render(n, a.width), names), 1):
            if i % 250 == 0:
                print(f"  {i}/{len(names)}  ok={_done['ok']} "
                      f"skip={_done['skip']} fail={_done['fail']}", flush=True)
    print(f"done: ok={_done['ok']} skip={_done['skip']} fail={_done['fail']}")
    return 1 if _done["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
