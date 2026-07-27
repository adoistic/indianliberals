#!/usr/bin/env python3
"""
Fetch a work's PDF and render its pages to JPEGs an agent can read.

The extraction pipeline runs on Claude Code subagents rather than an HTTP API,
so the way to get a scanned page in front of a model is to put it on disk as an
image and hand over the path. This does that, for the handful of works whose
text never made it into the corpus: the one empty stub, and the image-only scans
with no text layer at all.

Reuses rasterize_chunk() from the v1.5 pipeline, so blank-page skipping and the
render scale match what every other work went through.

Usage:
    python3 scripts/llm-extract/prepare_pages.py ff389
    python3 scripts/llm-extract/prepare_pages.py evils-of-child-marriage --pages 30
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rasterize import rasterize_chunk  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WORKS = REPO / "apps" / "site" / "src" / "content" / "primary-works"
OUT_ROOT = Path("/private/tmp/claude-501/-Users-siraj-Indian-Liberals-Website/scratchpad/pages")


def pdf_url_for(slug: str) -> str:
    text = (WORKS / f"{slug}.md").read_text(encoding="utf-8")
    match = re.search(r"^pdf_url:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    if not match:
        raise SystemExit(f"{slug}: no pdf_url in frontmatter")
    return match.group(1).strip().strip('"')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--pages", type=int, default=24)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--scale", type=float, default=2.4)
    args = ap.parse_args()

    url = pdf_url_for(args.slug)
    out = OUT_ROOT / args.slug
    out.mkdir(parents=True, exist_ok=True)

    pdf_path = out / "source.pdf"
    if not pdf_path.exists():
        print(f"fetching {url}")
        # The archive worker rejects urllib's default user-agent with a 403.
        request = urllib.request.Request(
            url, headers={"User-Agent": "indianliberals-extract/1.0 (+https://indianliberals.in)"}
        )
        with urllib.request.urlopen(request) as response, pdf_path.open("wb") as fh:
            fh.write(response.read())
    print(f"pdf: {pdf_path} ({pdf_path.stat().st_size / 1e6:.1f} MB)")

    chunk = rasterize_chunk(
        pdf_path,
        start_page=args.start,
        pages_wanted=args.pages,
        scale=args.scale,
    )

    written = []
    for page in chunk.pages:
        target = out / f"page-{page.page_num:03d}.jpg"
        target.write_bytes(page.jpeg_bytes)
        written.append(target)

    print(f"rendered {len(written)} page(s) into {out}")
    print(f"  blank pages skipped: {chunk.blank_pages_skipped}")
    print(f"  ended at EOF: {chunk.ended_at_eof} · total pages in pdf: {chunk.total_pages_in_pdf}")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
