"""
Strip the stale OCR text body from the 51 primary-works entries imported
from the legacy DB and replace with a needs_extraction flag.

Why:
- The OCR text was extracted by an English-only OCR pipeline run on
  font-encoded Marathi/Hindi/Gujarati scans, so it's mostly garbage
  (font-glyph mojibake rendered as ASCII).
- The new LLM extraction pipeline (per design doc 2026-05-17) replaces
  body text with AI-generated summary + key_points + pull_quotes from
  rendered page images.
- These 51 entries already have valid metadata (title, language, year,
  pdf_staging_path, etc.) — we preserve that and just replace the body.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET_DIR = REPO / "apps/site/src/content/primary-works"

PLACEHOLDER_BODY = """_Awaiting LLM extraction._

This entry was imported from the legacy WordPress database. Metadata is
preserved; body text is pending the AI-extraction pipeline (rasterize + Sonnet
metadata pass + summarization pass + synthesis layer). See the
[Indian Liberals Website project design doc](../../../../../.gstack/projects/IndianLiberalsWebsite/siraj-main-design-20260517-133733.md)
for the extraction architecture.

Until extraction runs, please refer to the staging PDF
(`pdf_staging_path` in the frontmatter)."""


def strip_one(path: Path) -> bool:
    """Return True if the file was modified."""
    text = path.read_text(encoding="utf-8")

    # Frontmatter parsing: file starts with --- and has a closing --- on its own line
    if not text.startswith("---\n"):
        return False
    end = text.find("\n---\n", 4)
    if end == -1:
        return False
    fm_block = text[4:end]
    body = text[end + 5:]

    # Skip files that don't carry the OCR body marker — leave them untouched.
    if "## Original text" not in body and "OCR" not in body and "## Page " not in body:
        return False

    # Add needs_extraction: true into the frontmatter if not already present.
    if "needs_extraction:" not in fm_block:
        # Insert after the last frontmatter line, before the closing ---
        fm_block = fm_block.rstrip() + '\nneeds_extraction: true'

    new_text = f"---\n{fm_block}\n---\n\n{PLACEHOLDER_BODY}\n"
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    modified = 0
    skipped = 0
    for f in sorted(TARGET_DIR.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        if strip_one(f):
            modified += 1
        else:
            skipped += 1
    print(f"Stripped {modified} entries; skipped {skipped} (no OCR body to remove).")


if __name__ == "__main__":
    main()
