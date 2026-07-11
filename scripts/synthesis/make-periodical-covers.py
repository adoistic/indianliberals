#!/usr/bin/env python3
"""Rasterise page 1 of periodical-issue PDFs into cover thumbnails.

Downloads each periodical_issue work's pdf_url (the prod-hosted scan),
renders the first page with pypdfium2, and writes a webp cover to
apps/site/public/periodicals/covers/<slug>.webp, recording the path in
the entry's `cover_image` frontmatter field.

Idempotent: entries whose cover file already exists are skipped (pass
--force to regenerate). Download failures are reported and skipped —
re-run after the R2 migration if any URL was down.

Usage:
    .venv-extract/bin/python3 scripts/synthesis/make-periodical-covers.py [--force]
"""

import argparse
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORKS = ROOT / "apps/site/src/content/primary-works"
OUT = ROOT / "apps/site/public/periodicals/covers"
UA = {"User-Agent": "IndianLiberalsArchive/1.0 (cover thumbnails)"}
WIDTH = 480


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--glob", default="*.md",
                    help="filename glob to scope the run (default: all *.md; "
                         "e.g. 'ff*.md' for just Freedom First)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    ok, failed = 0, []
    for f in sorted(WORKS.glob(args.glob)):
        t = f.read_text()
        if not re.search(r'^work_type: "?periodical_issue"?$', t, re.M):
            continue
        m = re.search(r'^pdf_url: "?(https?://\S+?)"?$', t, re.M)
        if not m:
            failed.append(f"{f.stem}: no pdf_url")
            continue
        dest = OUT / f"{f.stem}.webp"
        rel = f"/periodicals/covers/{f.stem}.webp"
        if dest.exists() and not args.force:
            ok += 1
        else:
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                    req = urllib.request.Request(m.group(1), headers=UA)
                    tmp.write(urllib.request.urlopen(req, timeout=120).read())
                    tmp.flush()
                    pdf = pdfium.PdfDocument(tmp.name)
                    page = pdf[0]
                    scale = WIDTH / page.get_size()[0]
                    bitmap = page.render(scale=scale)
                    img: Image.Image = bitmap.to_pil().convert("RGB")
                    img.save(dest, "WEBP", quality=80)
                    pdf.close()
                ok += 1
            except Exception as e:  # noqa: BLE001 — report and continue
                failed.append(f"{f.stem}: {e}")
                continue
        if f'cover_image: "{rel}"' not in t:
            if re.search(r"^cover_image:", t, re.M):
                t = re.sub(r'^cover_image: .*$', f'cover_image: "{rel}"', t, count=1, flags=re.M)
            else:
                t = re.sub(r'^(pdf_url: .*)$', rf'\1\ncover_image: "{rel}"', t, count=1, flags=re.M)
            f.write_text(t)

    print(f"covers: {ok} ok, {len(failed)} failed")
    for line in failed:
        print("  FAIL", line)
    sys.exit(0)


if __name__ == "__main__":
    main()
