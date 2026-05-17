"""
Rasterizer for the LLM extraction pipeline.

Converts a range of PDF pages to JPEG bytes, skipping blank pages, with an
optional cap on how many extra pages are rendered when blanks are encountered.

Public surface:
    rasterize_chunk(pdf_path, *, start_page, pages_wanted, ...) -> RasterizedChunk
    is_pdf_blank_page(img, threshold) -> bool

Design notes:
- Uses pypdfium2 for rendering (same as rasterize_smoke_test.py).
- Blank detection: grayscale, count pixels < 240, ratio over total pixels.
- JPEG encoding at jpeg_quality via Pillow.
- All PDF/page objects are closed in a finally block.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PDF_ROOT = Path("/Volumes/One Touch/Indian Liberals/PDFs-by-publisher")

# Filesystem artefacts to skip on any directory walk
GHOST_NAMES = {".DS_Store", "desktop.ini", "Thumbs.db"}


def _is_ghost(p: Path) -> bool:
    """Return True for macOS/Windows filesystem artefact files."""
    name = p.name
    return name.startswith("._") or name in GHOST_NAMES


@dataclass
class RasterizedPage:
    page_num: int       # 1-indexed PDF page number
    is_blank: bool
    jpeg_bytes: bytes
    width_px: int
    height_px: int


@dataclass
class RasterizedChunk:
    pdf_path: Path
    requested_start: int       # 1-indexed
    requested_count: int
    pages: list[RasterizedPage]         # non-blank pages only, in order
    blank_pages_skipped: list[int]      # 1-indexed page numbers that were blank
    total_pages_in_pdf: int
    truncated: bool     # True if hit max_extra_factor cap before getting pages_wanted
    ended_at_eof: bool  # True if reached end of PDF before getting pages_wanted


def is_pdf_blank_page(img: Image.Image, threshold: float = 0.001) -> bool:
    """
    Return True when the image looks blank (all-white or near-all-white).

    Heuristic: convert to grayscale, count pixels darker than 240 (non-white),
    compute ratio over total pixels.  Blank if ratio < threshold.

    Uses get_flattened_data() on Pillow >= 11 to avoid the getdata() deprecation
    warning; falls back to getdata() for older Pillow installs.
    """
    gray = img.convert("L")
    try:
        # Pillow >= 11: get_flattened_data() returns a flat list of pixel values
        pixels = list(gray.get_flattened_data())
    except AttributeError:
        pixels = list(gray.getdata())
    non_white = sum(1 for p in pixels if p < 240)
    ratio = non_white / max(len(pixels), 1)
    return ratio < threshold


def rasterize_chunk(
    pdf_path: Path,
    *,
    start_page: int = 1,           # 1-indexed
    pages_wanted: int = 20,
    scale: float = 2.0,            # ~150 DPI (72 DPI base × 2)
    jpeg_quality: int = 85,
    blank_threshold: float = 0.001,
    max_extra_factor: float = 1.5,
) -> RasterizedChunk:
    """
    Render up to `pages_wanted` non-blank pages starting from `start_page`.

    Pages are rendered one-at-a-time.  Blank pages (per `blank_threshold`) are
    skipped and recorded in `blank_pages_skipped`.  Rendering stops when:
      - `len(pages) == pages_wanted`, OR
      - total pages rendered >= pages_wanted * max_extra_factor, OR
      - end of PDF is reached.

    Returns a RasterizedChunk with all state (including truncated / ended_at_eof
    flags) populated.
    """
    pdf_path = Path(pdf_path)
    doc: pdfium.PdfDocument | None = None
    rendered_pages: list[RasterizedPage] = []
    blank_pages: list[int] = []

    try:
        doc = pdfium.PdfDocument(str(pdf_path))
        total_pages = len(doc)

        # Convert 1-indexed start_page to 0-indexed
        start_idx = max(0, start_page - 1)
        max_render = int(pages_wanted * max_extra_factor)

        pages_rendered = 0   # how many pages we have rendered (blank + non-blank)
        truncated = False
        ended_at_eof = False

        current_idx = start_idx
        while len(rendered_pages) < pages_wanted:
            # Hit end of document?
            if current_idx >= total_pages:
                ended_at_eof = True
                break

            # Hit render cap?
            if pages_rendered >= max_render:
                truncated = True
                break

            page_1indexed = current_idx + 1
            page_obj = doc[current_idx]
            try:
                bitmap = page_obj.render(scale=scale)
                img = bitmap.to_pil()

                blank = is_pdf_blank_page(img, threshold=blank_threshold)

                # Encode to JPEG
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality)
                jpeg_bytes = buf.getvalue()

                width_px, height_px = img.size

                if blank:
                    blank_pages.append(page_1indexed)
                else:
                    rendered_pages.append(
                        RasterizedPage(
                            page_num=page_1indexed,
                            is_blank=False,
                            jpeg_bytes=jpeg_bytes,
                            width_px=width_px,
                            height_px=height_px,
                        )
                    )
            finally:
                page_obj.close()

            pages_rendered += 1
            current_idx += 1

        # If we exited the while because pages_wanted was satisfied, check eof edge
        if not truncated and not ended_at_eof:
            # We got exactly pages_wanted non-blank pages; that's a clean stop
            pass

        return RasterizedChunk(
            pdf_path=pdf_path,
            requested_start=start_page,
            requested_count=pages_wanted,
            pages=rendered_pages,
            blank_pages_skipped=blank_pages,
            total_pages_in_pdf=total_pages,
            truncated=truncated,
            ended_at_eof=ended_at_eof,
        )
    finally:
        if doc is not None:
            doc.close()


# ---------------------------------------------------------------------------
# Unit-test / smoke test
# ---------------------------------------------------------------------------

def _run_tests() -> None:
    import json

    manifest_path = REPO / "data/bakeoff-sample.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pdfs_by_id = {e["id"]: e for e in manifest["pdfs"]}

    test_cases = [
        (1,  "2-page coal — expect 2 non-blank",    {"pages_wanted": 20}),
        (41, "570-page Satyamev — expect 20 non-blank (p1 blank cover)", {"pages_wanted": 20}),
        (39, "4-page Bengali Vidyasagar — expect 4 non-blank", {"pages_wanted": 20}),
    ]

    print("=" * 60)
    print("rasterize.py unit tests")
    print("=" * 60)

    all_ok = True
    for entry_id, label, kwargs in test_cases:
        entry = pdfs_by_id[entry_id]
        pdf_path = PDF_ROOT / entry["path"]

        if not pdf_path.exists():
            print(f"\n[SKIP] #{entry_id} {label}")
            print(f"       File not found: {pdf_path}")
            continue

        print(f"\n[TEST] #{entry_id} {label}")
        print(f"       {pdf_path.name}")

        try:
            chunk = rasterize_chunk(pdf_path, **kwargs)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            all_ok = False
            continue

        non_blank = len(chunk.pages)
        blank = len(chunk.blank_pages_skipped)
        total_pdf = chunk.total_pages_in_pdf
        avg_kb = (
            sum(len(p.jpeg_bytes) for p in chunk.pages) / max(non_blank, 1) / 1024
        )

        print(f"  total_pages_in_pdf : {total_pdf}")
        print(f"  non-blank pages    : {non_blank}")
        print(f"  blank pages skipped: {blank}  {chunk.blank_pages_skipped}")
        print(f"  truncated          : {chunk.truncated}")
        print(f"  ended_at_eof       : {chunk.ended_at_eof}")
        print(f"  avg JPEG size      : {avg_kb:.1f} KB")
        if chunk.pages:
            first = chunk.pages[0]
            print(f"  first page dims    : {first.width_px}×{first.height_px} px")

        # Spot-check assertions
        if entry_id == 1:
            assert non_blank == 2, f"Expected 2 non-blank pages, got {non_blank}"
            print("  [PASS] 2 non-blank pages confirmed")
        elif entry_id == 39:
            assert non_blank == 4, f"Expected 4 non-blank pages, got {non_blank}"
            print("  [PASS] 4 non-blank pages confirmed")
        elif entry_id == 41:
            assert non_blank == 20, f"Expected 20 non-blank pages, got {non_blank}"
            print("  [PASS] 20 non-blank pages confirmed")

    print("\n" + "=" * 60)
    if all_ok:
        print("All tests completed (see assertions above for pass/fail).")
    else:
        print("Some tests encountered errors.")


if __name__ == "__main__":
    _run_tests()
