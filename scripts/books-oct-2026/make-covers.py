#!/usr/bin/env python3
"""Render page 1 of each book in the October 2026 tranche to a cover thumbnail.

Matches the archive's existing convention exactly: WebP at
`archive.indianliberals.in/covers/<slug>.webp`, same slug as the work id, and
the same 640px target width `scripts/swatantra/make-covers.py` uses, so the
listing tiles in /primary-works/ and the series pages stay visually uniform.

Reads the slug -> source-PDF mapping from data/books-oct-2026/manifest.tsv, so
cover names and R2 object keys cannot drift from the content entries.

    python3 scripts/books-oct-2026/make-covers.py [--width 640] [--out DIR]

Resumable: a slug whose .webp already exists on disk is skipped.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, "/Users/siraj/Library/Python/3.14/lib/python/site-packages")
import fitz  # noqa: E402
from PIL import Image  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "data/books-oct-2026/manifest.tsv"
PDF_ROOT = Path(os.environ.get("LLM_EXTRACT_PDF_ROOT",
                               "/Users/siraj/Downloads/BOOKS FINAL DATA"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--out", default=str(REPO / "build-artifacts/books-oct-2026/covers"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    with open(MANIFEST, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    for row in rows:
        dest = out / f"{row['slug']}.webp"
        if dest.exists():
            print(f"skip  {dest.name}")
            continue
        src = PDF_ROOT / row["source_pdf"]
        doc = fitz.open(src)
        page = doc[0]
        # Scale so the rendered bitmap is `width` px across, whatever the trim size.
        zoom = a.width / page.rect.width
        pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        # PyMuPDF has no WebP encoder, so hand the raw samples to PIL. Quality 82
        # is the archive's existing cover setting: visually clean at tile size,
        # and it keeps a 640px cover well under 100 KB.
        img = Image.frombytes("RGB" if pm.n >= 3 else "L",
                              (pm.width, pm.height), pm.samples)
        img.save(dest, "WEBP", quality=82, method=6)
        doc.close()
        print(f"wrote {dest.name}  {pm.width}x{pm.height}  {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
