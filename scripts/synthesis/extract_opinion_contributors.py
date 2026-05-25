#!/usr/bin/env python3
"""
Step 1 of the contributors-collection pipeline.

Walks every opinion MD under apps/site/src/content/opinions/, finds
the trailing author-bio block (photo URL + bold name + paragraph),
and writes one contributor MD per unique name to
apps/site/src/content/contributors/.

Idempotent: re-runs do NOT overwrite existing contributor MDs.

Emits data/synthesis/contributor-photo-urls.jsonl mapping each
extracted contributor slug to its source photo URL (input for the
wire/download step that runs next).

Run from repo root:
    python3 scripts/synthesis/extract_opinion_contributors.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPINIONS_DIR = ROOT / "apps/site/src/content/opinions"
CONTRIBUTORS_DIR = ROOT / "apps/site/src/content/contributors"
PHOTO_URLS_OUT = ROOT / "data/synthesis/contributor-photo-urls.jsonl"

# Section headings + doc-title patterns that look like names but are not.
_FALSE_POSITIVE_NAMES = frozenset({
    "Introduction", "References", "Conclusion", "Background",
    "Way forward", "Summing Up", "The Witch-hunt", "Need for Two Fleets",
    "The Problem with the First-Past-the-Post System",
    "Defining the Role of the Indian Navy in the Bay of Bengal",
    "Importance of Collective Action", "The Indian Liberals Annual Lecture",
    "Palkhivala Stunned the Government",
})


def slugify(name: str) -> str:
    """'Sanjeet Kashyap' → 'sanjeet-kashyap'. Strips diacritics, lowercases,
    collapses whitespace + punctuation to single hyphens, strips trailing."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def sort_name(name: str) -> str:
    """'Sanjeet Kashyap' → 'Kashyap, Sanjeet'. Single-word names pass through."""
    parts = name.strip().split()
    if len(parts) < 2:
        return name.strip()
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def is_false_positive(name: str) -> bool:
    """True if the bold-text 'name' is actually a section heading or doc title."""
    return name.strip() in _FALSE_POSITIVE_NAMES


# Pattern A: photo URL + bold name + bio paragraph (1+ lines).
_BIO_WITH_PHOTO_RX = re.compile(
    r"!\[\]\((?P<photo>https?://[^\)]+\.(?:jpg|jpeg|png|webp))\)\s*\n+"
    r"\s*\*\*(?P<name>[^*\n]+?)\s*\*\*\s*\n+"
    r"(?P<bio>(?:[^\n]+\n?){1,15})",
    re.M,
)

# Pattern B: bold name + bio paragraph (no photo), bio at least 80 chars.
_BIO_NAME_ONLY_RX = re.compile(
    r"\n\*\*(?P<name>[A-Z][A-Za-z. \-]{4,60}?)\s*\*\*\s*\n+"
    r"(?P<bio>[A-Z][^\n]{60,}(?:\n[^\n]+)*)",
    re.M,
)


def extract_bio_block(body: str) -> dict | None:
    """Find the trailing bio block in an opinion body. Returns
    {name, photo_url, bio} or None if no real bio block is present.

    Precedence: pattern A (photo + name + bio) is tried first. If at least
    one A match survives the false-positive + bio-length filters, the LAST
    A match wins. Only if NO A match survives do we fall through to pattern
    B (name + bio without photo).

    This matters because pattern B's name-only regex is broader and can
    match bold subheadings mid-body — pattern A's image anchor is the
    strong signal that a real trailing bio block is present."""
    def _candidates(rx, has_photo: bool):
        out = []
        for m in rx.finditer(body):
            name = m.group("name").strip()
            if is_false_positive(name):
                continue
            bio = m.group("bio").strip()
            if len(bio) < 80:
                continue
            photo = m.group("photo") if has_photo else None
            out.append({"name": name, "photo_url": photo, "bio": bio})
        return out
    a = _candidates(_BIO_WITH_PHOTO_RX, has_photo=True)
    if a:
        return a[-1]
    b = _candidates(_BIO_NAME_ONLY_RX, has_photo=False)
    return b[-1] if b else None


_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


def parse_md(text: str) -> tuple[str, str]:
    """Returns (frontmatter_yaml, body). Raises on malformed."""
    m = _FRONTMATTER_RX.match(text)
    if not m:
        raise ValueError("not a frontmatter MD")
    return m.group(1), m.group(2)


def write_contributor_md(slug: str, name: str, bio: str, photo_url: str | None) -> bool:
    """Create apps/site/src/content/contributors/<slug>.md if not present.
    Returns True if a new file was written, False if it already existed.
    Re-runs MUST NOT overwrite — preserves idempotence + curator edits."""
    path = CONTRIBUTORS_DIR / f"{slug}.md"
    if path.exists():
        return False
    # Best-effort affiliation + role from the bio prose.
    affiliation = None
    if "Centre for Civil Society" in bio or "CCS" in bio:
        affiliation = "Centre for Civil Society"
    role = None
    for pat in ("Indian Liberal Fellow", "Indian Liberals Fellow",
                "Indian Liberals Project intern", "research scholar",
                "intern", "Editorial Team", "Editor"):
        if re.search(rf"\b{re.escape(pat)}\b", bio, re.I):
            role = pat
            break
    # Build YAML
    lines = ["---"]
    lines.append(f"id: {slug}")
    lines.append("name:")
    lines.append(f"  canonical: {json.dumps(name)}")
    lines.append(f"  sort: {json.dumps(sort_name(name))}")
    if affiliation:
        lines.append(f"affiliation: {json.dumps(affiliation)}")
    if role:
        lines.append(f"role: {json.dumps(role)}")
    lines.append("bio_source: extracted_from_opinion_bio")
    lines.append("needs_review: true")
    lines.append("draft: false")
    lines.append("---")
    lines.append("")
    lines.append(bio)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report what would be written; touch no files")
    args = ap.parse_args()

    CONTRIBUTORS_DIR.mkdir(parents=True, exist_ok=True)
    PHOTO_URLS_OUT.parent.mkdir(parents=True, exist_ok=True)

    seen: dict[str, str | None] = {}
    n_opinions_scanned = n_bio_found = n_new = n_skipped_existing = 0

    for op_path in sorted(OPINIONS_DIR.glob("*.md")):
        n_opinions_scanned += 1
        text = op_path.read_text(encoding="utf-8")
        try:
            _, body = parse_md(text)
        except ValueError:
            continue
        bio = extract_bio_block(body)
        if not bio:
            continue
        n_bio_found += 1
        slug = slugify(bio["name"])
        # First photo URL wins per slug (preserves the photo from the first occurrence).
        if slug not in seen:
            seen[slug] = bio["photo_url"]
        if args.dry_run:
            continue
        wrote = write_contributor_md(slug, bio["name"], bio["bio"], bio["photo_url"])
        if wrote:
            n_new += 1
        else:
            n_skipped_existing += 1

    # Emit photo-URL sidecar (always rebuilt fresh on every run).
    if not args.dry_run:
        with PHOTO_URLS_OUT.open("w", encoding="utf-8") as f:
            for slug, url in sorted(seen.items()):
                if url:
                    f.write(json.dumps({"slug": slug, "photo_url": url}) + "\n")

    prefix = "dry-run: would " if args.dry_run else ""
    print(f"{prefix}scanned {n_opinions_scanned} opinions; "
          f"found {n_bio_found} bio blocks → {len(seen)} unique contributors; "
          f"new MDs: {n_new}; skipped (already existed): {n_skipped_existing}")
    print(f"photo URL sidecar: {PHOTO_URLS_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
