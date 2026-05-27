#!/usr/bin/env python3
"""Phase A: deterministic migration of interview MDs into primary-works.

For each MD under apps/site/src/content/interviews/:
  - parse frontmatter
  - build a primary-work-shaped frontmatter (work_type='interview', authors,
    contributors, publication, youtube_url, transcript_status, description if any)
  - replace body with the cleaned transcript content (or a placeholder if missing)
  - write to apps/site/src/content/primary-works/<slug>.md
  - delete the source interview MD only AFTER successful write

Pure-logic helpers are unit-tested in scripts/synthesis/tests/test_migrate_interviews.py.
The main driver runs once over all 72 MDs.

Run:
    .venv-extract/bin/python3 scripts/synthesis/migrate-interviews-to-primary-works.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERVIEWS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "interviews"
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
TRANSCRIPT_DIR = REPO_ROOT / "data" / "interview-transcripts"
THINKERS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "thinkers"

# WP-garbage tail strip, per spec §5.2.
_WP_TAIL_RX = re.compile(
    r"\s*_?\s*type=content&[\s\S]*?Needs editorial review\._?\s*$",
    re.M,
)
# Leading "linked-source" boilerplate sometimes precedes the type=content tail,
# e.g., `[Read more](https://...]_.` from the prior WordPress export.
_WP_LINK_LEAD_RX = re.compile(r"^[\s\S]*?\]_\.\s*", re.M)

_FM_BLOCK_RX = re.compile(r"^---\n([\s\S]*?)\n---\n?([\s\S]*)$", re.M)


def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Empty dict if no frontmatter found."""
    m = _FM_BLOCK_RX.match(md_text)
    if not m:
        return {}, md_text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), m.group(2)


def extract_year_from_pubdate(pubdate: object) -> int | None:
    """Parse an ISO-like date string and return its year, or None on failure."""
    if not isinstance(pubdate, str) or not pubdate.strip():
        return None
    candidate = pubdate.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate).year
    except ValueError:
        pass
    m = re.match(r"^(\d{4})\b", pubdate)
    return int(m.group(1)) if m else None


def strip_wp_garbage_body(body: str) -> str | None:
    """Return cleaned body, or None if there's nothing meaningful left.

    Strips the trailing WordPress-migration boilerplate. Returns the cleaned
    text if it has >= 80 non-whitespace chars; else None.
    """
    if not body:
        return None
    cleaned = _WP_TAIL_RX.sub("", body).strip()
    if sum(1 for c in cleaned if not c.isspace()) < 80:
        return None
    return cleaned


def classify_transcript_status(slug: str, *, transcript_dir: Path = TRANSCRIPT_DIR) -> str:
    """Decide which transcript_status enum value applies for this slug.

    Returns one of: 'complete', 'none', 'unavailable'.
    """
    cleaned = transcript_dir / f"{slug}.cleaned.md"
    if not cleaned.exists():
        return "unavailable"
    body = cleaned.read_text(encoding="utf-8")
    if "(empty transcript)" in body or "skipped (transcript empty" in body:
        return "none"
    return "complete"


def build_new_frontmatter(
    old_fm: dict,
    *,
    slug: str,
    transcript_status: str,
    description: str | None,
) -> dict:
    """Build the primary-work-shaped frontmatter dict from an interview's old frontmatter."""
    subject = old_fm.get("subject")
    if isinstance(subject, str) and subject.strip():
        authors = [subject.strip()]
    else:
        authors = []

    year = extract_year_from_pubdate(old_fm.get("pubDate"))
    language = old_fm.get("language") or "en"
    publication: dict = {"language": language}
    if year is not None:
        publication["year"] = year

    new_fm: dict = {
        "id": old_fm.get("id") or slug,
        "title": {"main": old_fm.get("title", slug)},
        "work_type": "interview",
        "authors": authors,
        "editors": [],
        "contributors": [],
        "publication": publication,
        "themes": [],
        "needs_review": True,
        "draft": bool(old_fm.get("draft", False)),
        "transcript_status": transcript_status,
    }

    if isinstance(old_fm.get("youtube_url"), str) and old_fm["youtube_url"].strip():
        new_fm["youtube_url"] = old_fm["youtube_url"].strip()
    if description is not None:
        new_fm["description"] = description

    return new_fm


def serialize_new_md(new_fm: dict, body: str) -> str:
    """Render a primary-work MD: YAML frontmatter + body."""
    fm_yaml = yaml.safe_dump(new_fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{fm_yaml.rstrip()}\n---\n\n{body.rstrip()}\n"


def migrate_one(md_path: Path) -> dict:
    """Migrate one interview MD. Returns a status dict with keys:
        slug, status ('OK' | 'COLLISION' | 'NO_FRONTMATTER'), dest_path
    """
    slug = md_path.stem
    dest = PW_DIR / f"{slug}.md"
    if dest.exists():
        return {"slug": slug, "status": "COLLISION", "dest_path": str(dest)}

    text = md_path.read_text(encoding="utf-8")
    old_fm, old_body = parse_frontmatter(text)
    if not old_fm:
        return {"slug": slug, "status": "NO_FRONTMATTER", "dest_path": str(dest)}

    transcript_status = classify_transcript_status(slug)
    description = strip_wp_garbage_body(old_body)
    new_fm = build_new_frontmatter(
        old_fm, slug=slug,
        transcript_status=transcript_status,
        description=description,
    )

    if transcript_status == "complete":
        body = (TRANSCRIPT_DIR / f"{slug}.cleaned.md").read_text(encoding="utf-8")
    elif transcript_status == "none":
        body = (TRANSCRIPT_DIR / f"{slug}.cleaned.md").read_text(encoding="utf-8")
    else:  # 'unavailable'
        body = "Transcript not available.\n"

    new_md_text = serialize_new_md(new_fm, body)
    dest.write_text(new_md_text, encoding="utf-8")
    md_path.unlink()
    return {"slug": slug, "status": "OK", "dest_path": str(dest)}


def main() -> int:
    if not INTERVIEWS_DIR.exists():
        print(f"interviews dir missing — nothing to migrate: {INTERVIEWS_DIR}")
        return 0

    mds = sorted(INTERVIEWS_DIR.glob("*.md"))
    print(f"Migrating {len(mds)} interview MDs → primary-works/")

    ok = collisions = no_fm = 0
    for md in mds:
        r = migrate_one(md)
        status = r["status"]
        if status == "OK":
            ok += 1
            print(f"  ✓ {r['slug']}")
        elif status == "COLLISION":
            collisions += 1
            print(f"  ✗ COLLISION at {r['dest_path']} — left source in place")
        else:
            no_fm += 1
            print(f"  ✗ NO_FRONTMATTER: {r['slug']}")

    print()
    print(f"Migration summary: {ok} ok, {collisions} collisions, {no_fm} no-frontmatter, {len(mds)} total")
    return 0 if (collisions + no_fm) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
