"""
Stage non-PDF media (portraits, magazine covers, book covers, audio) and
emit a manifest. Small assets (images < 5MB total per kind) are copied into
apps/site/public/legacy-media/ for immediate use. Audio is huge (~261MB) so
we manifest it for later R2 upload.

We also try to enrich the manifest with names from the mid-era WP database:
  wp_author.image       → thinker portrait filename (e.g. 'coverimg__masani.jpg')
  wp_book.coverimage    → book cover filename
  wp_periodicals.coverimage → periodical cover filename
  wp_av.url             → audio URL (mostly YouTube — we still note any local files)

Whether those named files exist on disk is reported separately; on this drive
they are not present at the expected paths because the backup tar contains
them under wp-content/uploads/ which we never extracted. The DB metadata is
captured in the manifest so a future pass can wire them up.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dump_parser import iter_rows  # noqa: E402

REPO = Path("/Users/siraj/Indian Liberals Website")
DRIVE = Path("/Volumes/One Touch/Indian Liberals")
SQL = DRIVE / "sql"
TARGET = REPO / "apps/site/public/legacy-media"
DATA = REPO / "data"


def copy_tree(src: Path, dest: Path, exts: set[str]) -> list[dict]:
    """Copy non-temp media files from src to dest. Return manifest entries."""
    dest.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for f in sorted(src.iterdir()):
        if f.name.startswith("._") or f.name == ".DS_Store":
            continue
        if f.suffix.lower().lstrip(".") not in exts:
            continue
        shutil.copy2(f, dest / f.name)
        out.append(
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "source_path": str(f.relative_to(DRIVE)),
            }
        )
    return out


def manifest_only(src: Path, exts: set[str]) -> list[dict]:
    """Manifest entries without copying (for large media bound for R2)."""
    if not src.exists():
        return []
    out: list[dict] = []
    for f in sorted(src.iterdir()):
        if f.name.startswith("._") or f.name == ".DS_Store":
            continue
        if f.suffix.lower().lstrip(".") not in exts:
            continue
        out.append(
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "source_path": str(f.relative_to(DRIVE)),
                "needs_r2": True,
            }
        )
    return out


def main() -> None:
    if TARGET.exists():
        # Wipe and rebuild so this script is idempotent.
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True, exist_ok=True)

    portraits_p = copy_tree(DRIVE / "PDFs/person", TARGET / "portraits", {"jpg", "jpeg", "png"})
    portraits_p += copy_tree(DRIVE / "PDFs/profile", TARGET / "portraits", {"jpg", "jpeg", "png"})

    mag_covers = copy_tree(DRIVE / "PDFs/periodicals", TARGET / "periodicals", {"jpg", "jpeg", "png"})
    book_covers = copy_tree(DRIVE / "PDFs/language", TARGET / "book-covers", {"jpg", "jpeg", "png"})

    # Audio: manifest only (too big to commit; bound for R2)
    audio = manifest_only(DRIVE / "PDFs/audio", {"mp3", "mp4", "wma", "m4a", "ogg"})

    # Pull DB metadata that names these assets
    LIB = SQL / "indianli_liberals.sql"
    INL = SQL / "indianli_inliberdb.sql"

    db_authors = []
    for r in iter_rows(LIB, "wp_author"):
        db_authors.append(
            {
                "id": r["id"],
                "name": r["name"],
                "image_filename": r.get("image", ""),
                "brief": (r.get("briefinfo") or "")[:300],
            }
        )

    db_periodicals = []
    for r in iter_rows(LIB, "wp_periodicals"):
        db_periodicals.append(
            {
                "id": r["id"],
                "title": r["title"],
                "cover_filename": r.get("coverimage", ""),
                "brief": (r.get("briefinfo") or "")[:300],
            }
        )

    db_books = []
    for r in iter_rows(LIB, "wp_book"):
        db_books.append(
            {
                "id": r["id"],
                "title": r["title"],
                "pdf_filename": r.get("pdf_file", ""),
                "cover_filename": r.get("coverimage", ""),
            }
        )

    db_av = []
    for r in iter_rows(LIB, "wp_av"):
        db_av.append(
            {
                "id": r["id"],
                "title": r["title"],
                "author": r.get("author", ""),
                "description": (r.get("description") or "")[:300],
                "url": r.get("url", ""),
            }
        )

    # Legacy non-WP DB: testimonials, video, events, news
    db_testimonials = []
    for r in iter_rows(INL, "testimonials"):
        db_testimonials.append(
            {
                "id": r["id"],
                "name": r.get("name", ""),
                "image_filename": r.get("image", ""),
                "short": (r.get("short") or "")[:200],
            }
        )

    db_videos = []
    for r in iter_rows(INL, "video"):
        db_videos.append(
            {
                "id": r["id"],
                "heading": r.get("heading", ""),
                "video_data": r.get("video_data", ""),
                "video_type": r.get("video_type", ""),
                "description": (r.get("description") or "")[:300],
            }
        )

    manifest = {
        "_meta": {
            "generated_from": "extract_media.py",
            "note": (
                "Numeric-ID files (e.g. 1083724334.jpg) are uploaded media from "
                "the WordPress era — we don't have name metadata for them in the "
                "extracted DBs because their attachment records live in "
                "il_postmeta._wp_attached_file under different paths. "
                "Named files (coverimg__masani.jpg) are referenced by the mid-era "
                "wp_author/wp_book/wp_periodicals tables but are NOT present on "
                "this drive — they're inside the unextracted wp-content/uploads/ "
                "subtree of the tar.gz backup."
            ),
        },
        "on_disk": {
            "portraits": portraits_p,
            "magazine_covers": mag_covers,
            "book_covers": book_covers,
            "audio": audio,
        },
        "db_metadata": {
            "authors": db_authors,
            "periodicals": db_periodicals,
            "books": db_books,
            "av_youtube_links": db_av,
            "testimonials": db_testimonials,
            "videos": db_videos,
        },
    }

    DATA.mkdir(parents=True, exist_ok=True)
    manifest_path = DATA / "legacy-media.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Copied:")
    print(f"  portraits:       {len(portraits_p)} files")
    print(f"  magazine covers: {len(mag_covers)} files")
    print(f"  book covers:     {len(book_covers)} files")
    print(f"Manifested only (bound for R2):")
    print(f"  audio:           {len(audio)} files")
    print(f"DB metadata captured:")
    print(f"  authors:         {len(db_authors)} records")
    print(f"  periodicals:     {len(db_periodicals)} records")
    print(f"  books:           {len(db_books)} records")
    print(f"  av/youtube:      {len(db_av)} records")
    print(f"  testimonials:    {len(db_testimonials)} records")
    print(f"  videos:          {len(db_videos)} records")
    print(f"\nManifest: {manifest_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
