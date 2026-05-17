"""
Pre-flight rasterization smoke test for the LLM extraction pipeline.

Renders page 1 of every PDF in PDFs-by-publisher/ at 150 DPI, detects
failures + blank-page renders (heuristic for JBIG2 decode bugs in pypdfium2),
and writes data/rasterization-blocklist.json with the PDFs that need manual
triage.

Per design doc: expected hit rate is 1-2% of corpus (9-19 PDFs).
"""

from __future__ import annotations

import io
import json
import sys
import traceback
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PDF_ROOT = Path("/Volumes/One Touch/Indian Liberals/PDFs-by-publisher")
OUT = REPO / "data/rasterization-blocklist.json"
RENDER_OUT = Path("/tmp/render-smoke-test")
RENDER_OUT.mkdir(parents=True, exist_ok=True)


def is_blank(img: Image.Image, threshold: float = 0.001) -> bool:
    """Heuristic: >99.9% non-text pixels suggests a JBIG2-decode blank."""
    gray = img.convert("L")
    # Count non-white-ish pixels (anything darker than 240)
    pixels = list(gray.getdata())
    non_white = sum(1 for p in pixels if p < 240)
    ratio = non_white / max(len(pixels), 1)
    return ratio < threshold


def render_page_one(pdf_path: Path, save_jpeg: bool = False) -> dict:
    """Return {status, page_count, blank, jpeg_size_bytes, error}."""
    try:
        doc = pdfium.PdfDocument(str(pdf_path))
        page_count = len(doc)
        if page_count == 0:
            doc.close()
            return {"status": "no_pages", "page_count": 0}
        page = doc[0]
        # Render at scale=2.0 → roughly 150 DPI for standard PDF DPI of 72
        bitmap = page.render(scale=2.0)
        img = bitmap.to_pil()
        blank = is_blank(img)
        # Encode to JPEG for size measurement (q85, the production setting)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85)
        jpeg_size = buf.tell()
        if save_jpeg:
            rel = pdf_path.relative_to(PDF_ROOT)
            target = RENDER_OUT / rel.with_suffix(".jpg")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(buf.getvalue())
        page.close()
        doc.close()
        return {
            "status": "ok",
            "page_count": page_count,
            "blank": blank,
            "jpeg_size_bytes": jpeg_size,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }


def main() -> None:
    if not PDF_ROOT.exists():
        print(f"PDF_ROOT does not exist: {PDF_ROOT}")
        sys.exit(1)

    results: list[dict] = []
    blocklist: list[dict] = []
    total = 0
    ok = 0
    blank = 0
    error = 0
    no_pages = 0

    pdfs = [p for p in PDF_ROOT.rglob("*.pdf") if not p.name.startswith("._")]
    pdfs.sort()
    print(f"Smoke-testing {len(pdfs)} PDFs...")

    for i, p in enumerate(pdfs):
        rel = p.relative_to(PDF_ROOT)
        if i % 50 == 0:
            print(f"  [{i:>4d}/{len(pdfs)}]  {rel.parent}/...")
        r = render_page_one(p)
        total += 1
        entry = {"path": str(rel), **r}
        results.append(entry)
        if r["status"] == "ok":
            ok += 1
            if r.get("blank"):
                blank += 1
                blocklist.append({"path": str(rel), "reason": "blank_render", "page_count": r["page_count"]})
        elif r["status"] == "no_pages":
            no_pages += 1
            blocklist.append({"path": str(rel), "reason": "no_pages"})
        else:
            error += 1
            blocklist.append({"path": str(rel), "reason": "render_error", "error": r.get("error")})

    summary = {
        "total": total,
        "ok": ok,
        "blank_render": blank,
        "no_pages": no_pages,
        "render_error": error,
        "blocked": len(blocklist),
        "blocked_pct": round(100 * len(blocklist) / max(total, 1), 2),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"summary": summary, "blocklist": blocklist}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("")
    print("=== Summary ===")
    for k, v in summary.items():
        print(f"  {k:<20}: {v}")
    print(f"\nWritten: {OUT.relative_to(REPO)}")
    if blocklist:
        print(f"\nBlocklist preview (first 10):")
        for b in blocklist[:10]:
            print(f"  {b['reason']:<15}  {b['path']}")


if __name__ == "__main__":
    main()
