#!/usr/bin/env python3
"""
Step 2 of the contributors-collection pipeline.

For every opinion MD whose trailing bio block matched a contributor we
extracted in step 1:
  1. Set frontmatter `author: <slug>` (insert or replace).
  2. Strip the trailing bio block from the body.

Preserves every other frontmatter field + the rest of the body.
Idempotent: re-runs with no new bios produce zero file changes.

Run from repo root (after extract_opinion_contributors.py):
    python3 scripts/synthesis/wire_opinion_contributors.py
    python3 scripts/synthesis/wire_opinion_contributors.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPINIONS_DIR = ROOT / "apps/site/src/content/opinions"
CONTRIBUTORS_DIR = ROOT / "apps/site/src/content/contributors"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)

# Bio-block OPENERS — match just enough to identify the start of a bio block.
# We anchor on the LAST surviving opener (after false-positive filtering),
# then strip from there to EOF. This avoids the previous bug where a section
# heading like "**References **" + bibliography matched as a bio block and
# caused the strip to start mid-article.
_BIO_PHOTO_OPENER_RX = re.compile(
    r"\n!\[\]\(https?://[^\)]+\.(?:jpg|jpeg|png|webp)\)\s*\n+\s*\*\*(?P<name>[^*\n]+?)\s*\*\*\s*\n",
    re.M,
)
_BIO_NAME_OPENER_RX = re.compile(
    r"\n\*\*(?P<name>[A-Z][A-Za-z. \-]{4,60}?)\s*\*\*\s*\n+[A-Z][^\n]{60,}",
    re.M,
)

# False-positive name allowlist — bold-text section headings that look like
# names but aren't. Keep in sync with extract_opinion_contributors._FALSE_POSITIVE_NAMES.
_FALSE_POSITIVE_NAMES = frozenset({
    "Introduction", "References", "Conclusion", "Background",
    "Way forward", "Summing Up", "The Witch-hunt", "Need for Two Fleets",
    "The Problem with the First-Past-the-Post System",
    "Defining the Role of the Indian Navy in the Bay of Bengal",
    "Importance of Collective Action", "The Indian Liberals Annual Lecture",
    "Palkhivala Stunned the Government",
})

# Also strip a stray empty link that some opinions have just before the bio.
_STRAY_BIO_LINK_RX = re.compile(
    r"\n\[\]\(https?://[^\)]*/attachment/bio/?\)\s*\n",
    re.M,
)


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def strip_bio_block(body: str) -> str:
    """Remove the trailing bio block (and any stray /attachment/bio/ link
    immediately preceding it). Returns body with the trailing block stripped.
    If no surviving bio opener is found, returns body with only the stray
    link removed (or unchanged if no stray link either).

    Anchor logic: among all opener matches, drop those whose bold-text name
    is in `_FALSE_POSITIVE_NAMES` (section headings, doc titles), then strip
    from the LAST surviving match's start to EOF. This matches the LAST-wins
    semantics of `find_contributor_for_body` and prevents over-stripping
    when a section heading like '**References **' appears earlier in the
    body."""
    # Strip the stray empty bio link first (cosmetic; some opinions have it).
    body = _STRAY_BIO_LINK_RX.sub("\n", body)
    # Photo openers first; fall through to name-only if no photo opener survives.
    for rx in (_BIO_PHOTO_OPENER_RX, _BIO_NAME_OPENER_RX):
        matches = [m for m in rx.finditer(body)
                   if m.group("name").strip() not in _FALSE_POSITIVE_NAMES]
        if matches:
            return body[: matches[-1].start()].rstrip() + "\n"
    return body


def set_frontmatter_author(fm: str, slug: str) -> str:
    """Insert `author: <slug>` into the frontmatter YAML string, or
    replace an existing `author:` line. Other fields untouched."""
    line = f"author: {slug}"
    if re.search(r"^author:", fm, re.M):
        return re.sub(r"^author:.*$", line, fm, count=1, flags=re.M)
    if re.search(r"^author_name:", fm, re.M):
        return re.sub(r"(^author_name:[^\n]+\n)", rf"\1{line}\n", fm, count=1, flags=re.M)
    return fm.rstrip() + "\n" + line + "\n"


def parse_md(text: str) -> tuple[str, str] | None:
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    return m.group(1), m.group(2)


def find_contributor_for_body(body: str) -> str | None:
    """Re-detect the trailing bio block's name and resolve it to an existing
    contributor slug. Returns None if no bio or no matching contributor MD."""
    name_with_photo = re.search(
        r"!\[\]\(https?://[^\)]+\.(?:jpg|jpeg|png|webp)\)\s*\n+\s*\*\*([^*\n]+?)\s*\*\*\s*\n",
        body,
    )
    if name_with_photo:
        slug = slugify(name_with_photo.group(1))
        if (CONTRIBUTORS_DIR / f"{slug}.md").exists():
            return slug
    name_only = list(re.finditer(
        r"\n\*\*([A-Z][A-Za-z. \-]{4,60}?)\s*\*\*\s*\n+([A-Z][^\n]{60,})",
        body, re.M,
    ))
    if name_only:
        m = name_only[-1]
        slug = slugify(m.group(1))
        if (CONTRIBUTORS_DIR / f"{slug}.md").exists():
            return slug
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    n_opinions = n_wired = n_stripped = n_already = n_no_match = 0

    for op_path in sorted(OPINIONS_DIR.glob("*.md")):
        n_opinions += 1
        text = op_path.read_text(encoding="utf-8")
        parsed = parse_md(text)
        if not parsed:
            continue
        fm, body = parsed
        slug = find_contributor_for_body(body)
        if not slug:
            n_no_match += 1
            continue
        author_match = re.search(r"^author:\s*(\S+)", fm, re.M)
        already_set = author_match and author_match.group(1) == slug
        new_body = strip_bio_block(body)
        body_changed = (new_body != body)
        if already_set and not body_changed:
            n_already += 1
            continue
        new_fm = set_frontmatter_author(fm, slug)
        new_text = f"---\n{new_fm.rstrip()}\n---\n{new_body}"
        if args.dry_run:
            if not already_set:
                n_wired += 1
            if body_changed:
                n_stripped += 1
            continue
        op_path.write_text(new_text, encoding="utf-8")
        if not already_set:
            n_wired += 1
        if body_changed:
            n_stripped += 1

    prefix = "dry-run: would " if args.dry_run else ""
    print(f"{prefix}scan {n_opinions} opinions: wire {n_wired} new author refs; "
          f"strip bio from {n_stripped} bodies; "
          f"{n_already} already wired (no change); "
          f"{n_no_match} no bio match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
