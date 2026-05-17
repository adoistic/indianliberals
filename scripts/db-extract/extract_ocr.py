"""
Extract OCR text + book metadata from the mid-era WP database
(indianli_liberals.sql) and write primary-works entries.

Source tables:
  tbl_languages_details — 51 books with title, author, language, PDF filename
  tbl_languages_content — 3,684 OCR'd pages (langpdfid, content, pageno)
  tbl_languages         — language master (Hindi=2, Gujarati=3, Marathi=4)
  wp_author             — author master (some books have author IDs vs names)

Each book becomes one primary-works entry with:
  - the book metadata in frontmatter
  - the full OCR text in the body (with page markers)
  - a pdf_staging_path that we'll later wire to R2
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dump_parser import iter_rows  # noqa: E402
from util import slugify, write_md_with_frontmatter  # noqa: E402

DB_DIR = Path("/Volumes/One Touch/Indian Liberals/sql")
LIB = DB_DIR / "indianli_liberals.sql"
REPO = Path("/Users/siraj/Indian Liberals Website")
CONTENT_ROOT = REPO / "apps/site/src/content"
DRIVE_PDFS = Path("/Volumes/One Touch/Indian Liberals/PDFs-by-publisher")

# tbl_languages.id → BCP-47 code
LANG_MAP = {2: "hi", 3: "gu", 4: "mr"}

# tbl_work_categories.id → work_type (we'll need to load this from DB)
# But for simplicity, infer from title pattern. Periodicals = serial issues.

PERIODICAL_TITLE_RE = re.compile(r"\b(khoj|liberal[\s-]?times|libertarian)\b", re.IGNORECASE)


def infer_work_type(title: str) -> str:
    if PERIODICAL_TITLE_RE.search(title):
        return "periodical_issue"
    return "book"


def find_disk_pdf(db_filename: str, db_title: str, language_code: str) -> str | None:
    """Best-effort match of DB filename → file on the curator's drive.

    The DB filenames look like 'PDF_2_c2i4vobook-udarwad.pdf'.
    The disk filenames are clean slugs like 'udarwad-raj-samaj-aur-bazaar.pdf'.
    We try slug overlap to find a likely match.
    """
    folder = DRIVE_PDFS / {"hi": "hindi", "gu": "gujarati", "mr": "marathi"}.get(language_code, "")
    if not folder.exists():
        return None
    # Pull the "meaningful" part of the DB filename
    db_slug = re.sub(r"^PDF_\d+_[a-z0-9]+", "", Path(db_filename).stem).strip("_-").lower()
    title_slug = slugify(db_title)
    best = None
    best_score = 0
    for p in folder.glob("*.pdf"):
        if p.name.startswith("._"):
            continue
        disk_slug = p.stem.lower()
        # Score by longest common substring length
        score = max(
            _overlap(db_slug, disk_slug),
            _overlap(title_slug, disk_slug),
        )
        if score > best_score:
            best_score = score
            best = p
    if best and best_score >= 5:
        return str(best.relative_to(DRIVE_PDFS.parent))
    return None


def _overlap(a: str, b: str) -> int:
    """Length of the longest common contiguous run between a and b."""
    if not a or not b:
        return 0
    # Quick: longest run of common alpha tokens
    tokens_a = set(re.findall(r"[a-z]{4,}", a))
    tokens_b = set(re.findall(r"[a-z]{4,}", b))
    return sum(len(t) for t in tokens_a & tokens_b)


def main() -> None:
    # Load OCR pages, grouped by langpdfid
    pages_by_book: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for r in iter_rows(LIB, "tbl_languages_content"):
        pages_by_book[r["langpdfid"]].append((r["pageno"], r["content"] or ""))

    # Load language master
    lang_master = {r["id"]: r["name"] for r in iter_rows(LIB, "tbl_languages")}

    # Clear any existing primary-works (we're regenerating canonically from DB)
    target = CONTENT_ROOT / "primary-works"
    target.mkdir(parents=True, exist_ok=True)
    for f in target.iterdir():
        if f.is_file() and f.suffix in {".md", ".mdx"}:
            f.unlink()

    written = 0
    pdf_matched = 0
    for d in iter_rows(LIB, "tbl_languages_details"):
        lang_code = LANG_MAP.get(d["languageid"], "en")
        lang_name = lang_master.get(d["languageid"], "Unknown")
        title = (d["title"] or "").strip()
        if not title:
            continue
        slug = slugify(title)
        if not slug:
            continue

        # Gather OCR pages, sorted by pageno. Decode HTML entities, strip
        # control characters (the OCR data has embedded \x00 nulls), normalize whitespace.
        def _decode(s: str) -> str:
            s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            s = s.replace("&quot;", '"').replace("&apos;", "'")
            s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
            s = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), s)
            # Strip ASCII control characters (keep \n, \t for now — collapsed below)
            s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
            return re.sub(r"\s+", " ", s).strip()

        pages = sorted(pages_by_book.get(d["id"], []), key=lambda x: x[0])
        decoded_pages = [(pn, _decode(c)) for pn, c in pages]
        ocr_body_parts: list[str] = []
        latin_chars = 0
        total_chars = 0
        for pageno, content in decoded_pages:
            if content:
                ocr_body_parts.append(f"### Page {pageno}\n\n{content}\n")
                latin_chars += sum(1 for ch in content if ch.isascii() and ch.isalnum())
                total_chars += sum(1 for ch in content if not ch.isspace())
        ocr_body = "\n".join(ocr_body_parts).strip()
        if not ocr_body:
            ocr_body = "_No OCR text in source database for this work._"

        # Heuristic: if a non-Latin-script book has >80% ASCII alphanumeric in
        # OCR, the original scan was font-encoded and the OCR is junk — warn.
        ocr_quality = "unknown"
        if total_chars > 100 and lang_code in {"hi", "gu", "mr", "bn"}:
            ratio = latin_chars / total_chars
            ocr_quality = "corrupted" if ratio > 0.7 else "partial"

        # Body shell
        excerpt = (d["excerpt"] or "").strip()
        body = []
        if excerpt:
            body.append(excerpt)
            body.append("")
        body.append("---")
        body.append("")
        body.append(f"## Original text ({lang_name})")
        body.append("")
        quality_note = {
            "corrupted": (
                f"**Warning:** the OCR text below was extracted from a font-encoded "
                f"{lang_name} PDF scan with an English-only OCR pipeline. The text "
                f"is largely corrupted and should not be used for citation or "
                f"reading. Refer to the original PDF for the authoritative scan. "
                f"A future engagement will re-run OCR with a script-aware pipeline."
            ),
            "partial": (
                f"The text below was extracted by OCR from the original {lang_name} "
                f"PDF scan. Quality is mixed — refer to the PDF for the authoritative scan."
            ),
            "unknown": (
                f"The text below was extracted by OCR from the original {lang_name} "
                f"PDF scan. Errors may remain — refer to the PDF for the authoritative scan."
            ),
        }[ocr_quality]
        body.append(quality_note)
        body.append("")
        body.append(ocr_body)
        body_text = "\n".join(body)

        pdf_staging = find_disk_pdf(d["pdf_file"], title, lang_code)
        if pdf_staging:
            pdf_matched += 1

        # Pub year from `date` field
        year = None
        if d.get("date"):
            m = re.match(r"(\d{4})", str(d["date"]))
            if m:
                year = int(m.group(1))

        # Map our internal OCR quality flag to the schema's enum.
        scan_quality = {"corrupted": "poor", "partial": "fair", "unknown": "unknown"}[ocr_quality]

        fm = {
            "id": slug,
            "title": {
                "main": title,
            },
            "work_type": infer_work_type(title),
            "authors": [],
            "publication": {
                "publisher_name": "Centre for Civil Society / Indian Liberals archive",
                "year": year,
                "language": lang_code,
            },
            "physical": {"page_count": d.get("pages") or len(pages) or None},
            "provenance": {
                "source": "ccs_archive",
                "scan_quality": scan_quality,
                "notes": f"Imported from indianli_liberals DB (id={d['id']}, lang={lang_name}). "
                + f"Original PDF filename: {d['pdf_file']}. "
                + f"OCR pages in DB: {len(pages)}. OCR quality flag: {ocr_quality}.",
            },
            "themes": [t.strip() for t in (d.get("tag") or "").split(",") if t.strip()],
            "ai_summary": (d.get("excerpt") or "").strip()[:600] or None,
            "ai_key_points": [],
            "paragraph_ids": [],
            "manifestations": [],
            "language": lang_code,
            "translation_status": "original",
            "needs_review": True,
            "draft": False,
        }
        if pdf_staging:
            fm["pdf_staging_path"] = pdf_staging

        # Author string → put in contributors note for now (we don't have a
        # matching thinker entry yet; that's a manual reconciliation step)
        author_str = (d.get("author") or "").strip()
        if author_str:
            fm["provenance"]["notes"] += f" Author (per DB): {author_str}."

        write_md_with_frontmatter(target / f"{slug}.md", fm, body_text)
        written += 1

    print(f"Wrote {written} primary-works entries; PDF matched on disk: {pdf_matched}/{written}")


if __name__ == "__main__":
    main()
