"""
Extract content posts from the current WP database into our content
collections — replacing the live-HTML scrape with cleaner DB data.

Mapping:
  content_category.slug == 'so-musings'      → src/content/musings/<slug>.md
  content_category.slug == 'opinions-events' → src/content/opinions/<slug>.md
  content_category.slug == 'audio-videos'    → src/content/interviews/<slug>.md
  content_category.slug ∈ {PDF wrappers}     → SKIP (they wrap legacy PDFs)
  content_category.slug ∈ {encyclopedia tags}→ src/content/musings/<slug>.md
  no category                                 → SKIP, log

Language: Polylang stores per-post language in il_term_relationships against
the `language` taxonomy. Terms 'en', 'hi', 'gu', 'mr', 'bn' map to BCP-47
codes 1:1.

Author: il_users.user_login is one of {admin, ET, vikrant} for all rows, so
we extract author names from the title/content. The original site authored
everything under "Editorial Team" by default — we keep that as the fallback.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dump_parser import iter_rows  # noqa: E402
from util import html_to_markdown, slugify, write_md_with_frontmatter  # noqa: E402

DB_DIR = Path("/Volumes/One Touch/Indian Liberals/sql")
V3 = DB_DIR / "indianli_indianv3.sql"
REPO = Path("/Users/siraj/Indian Liberals Website")
CONTENT_ROOT = REPO / "apps/site/src/content"

# Categories that wrap legacy PDFs — they have no editorial body, just a
# PDF link. We're not scraping these (Adnan's instruction in earlier turns).
PDF_WRAPPER_CATS = {
    "forum-of-free-enterprise",
    "the-indian-libertarian",
    "shetkari-sanghatak",
    "swatantra-party",
    "indian-liberals",
    "indian-liberal-group",
    "periodicals",
    "other-publications",
    "bengali",  # bucket for Bengali PDFs
    "hindi",  # bucket for Hindi PDFs
    "marathi",
    "gujarati",
    "liberal-times",
    "freedom-first",
    "testimonials",
}

# Encyclopedia-drift categories that were imports of Wikipedia-style stubs.
# We drop them entirely; they were never real editorial content.
DROP_CATS = {
    "middle-ages",
    "new-france",
}

CAT_TO_COLLECTION = {
    "so-musings": "musings",
    "opinions-events": "opinions",
    "audio-videos": "interviews",
}

LANG_SLUG_TO_BCP47 = {
    "en": "en",
    "english": "en",
    "hi": "hi",
    "hindi": "hi",
    "gu": "gu",
    "gujarati": "gu",
    "mr": "mr",
    "marathi": "mr",
    "bn": "bn",
    "bengali": "bn",
}


def load_taxonomies():
    """Return (post_terms, taxonomies) — see recon.py for shapes."""
    terms = {r["term_id"]: r for r in iter_rows(V3, "il_terms")}
    taxonomies = {}
    for tt in iter_rows(V3, "il_term_taxonomy"):
        t = terms.get(tt["term_id"])
        if t:
            taxonomies[tt["term_taxonomy_id"]] = (tt["taxonomy"], t["name"], t["slug"])
    post_terms = defaultdict(list)
    for tr in iter_rows(V3, "il_term_relationships"):
        post_terms[tr["object_id"]].append(tr["term_taxonomy_id"])
    return post_terms, taxonomies


def post_facets(post_id, post_terms, taxonomies):
    """Bucket a post's term memberships by taxonomy."""
    facets = defaultdict(list)  # taxonomy -> list of slugs
    for tt_id in post_terms.get(post_id, []):
        tax_info = taxonomies.get(tt_id)
        if tax_info:
            facets[tax_info[0]].append(tax_info[2])
    return facets


def pick_collection(facets) -> str | None:
    """Decide which content collection this post belongs in.

    Priority order: real editorial categories first, PDF wrapper cats last.
    """
    cats = facets.get("content_category", [])
    # Drop encyclopedia drift outright
    if any(c in DROP_CATS for c in cats):
        return None
    # Map known editorial categories
    for c in cats:
        if c in CAT_TO_COLLECTION:
            return CAT_TO_COLLECTION[c]
    # All categories are PDF wrappers → skip
    if cats and all(c in PDF_WRAPPER_CATS for c in cats):
        return None
    # No category — treat as musing (catch-all editorial)
    if not cats:
        return "musings"
    return None


def language_from_facets(facets) -> str:
    """Resolve the BCP-47 language code from Polylang's `language` taxonomy."""
    langs = facets.get("language") or facets.get("term_language") or []
    for slug in langs:
        if slug in LANG_SLUG_TO_BCP47:
            return LANG_SLUG_TO_BCP47[slug]
    return "en"


# Author extraction from title: heuristics for the patterns we see in this
# dump. Examples:
#   "Growthmanship Fact or Fallacy by Colin Clark (July 11, 1965)"
#   "Mass Education by M. R. Pai"
#   "Sultana's Dream"
_BY_AUTHOR_RE = re.compile(r"\bby\s+([A-Z][A-Za-z.\-' ]{2,80}?)(?:\s*\(|\s*\||\s*[-–—]|\s*$)", re.IGNORECASE)


def author_from_title(title: str) -> str | None:
    m = _BY_AUTHOR_RE.search(title)
    if not m:
        return None
    name = m.group(1).strip().rstrip(",")
    # Drop obviously-noise endings
    name = re.sub(r"\s+the\s+(?:rt\.?\s+hon|hon|mr|mrs|dr|prof)\s.*$", "", name, flags=re.IGNORECASE)
    if len(name) < 3 or len(name) > 80:
        return None
    return name


def youtube_from_content(content: str) -> str | None:
    """Find the first YouTube URL embedded in the post body."""
    m = re.search(r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})", content)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return None


def subject_from_title(title: str) -> str:
    """Strip episode labels and 'by ...' tails for interview subject lines."""
    s = re.sub(r"^IL\s*Explainer[^|]*\|\s*", "", title, flags=re.IGNORECASE)
    s = re.sub(r"\s+by\s+.+$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+\(.*?\)\s*$", "", s)
    return s.strip() or title


def main() -> None:
    post_terms, taxonomies = load_taxonomies()

    # Clear existing scrape-sourced content so the DB extraction is canonical.
    # Keep thinkers/organisations/theprint-mirror (sourced elsewhere).
    for coll in ("musings", "opinions", "interviews"):
        target = CONTENT_ROOT / coll
        if target.exists():
            for f in target.iterdir():
                if f.is_file() and f.suffix in {".md", ".mdx"}:
                    f.unlink()

    counts: dict[str, int] = defaultdict(int)
    seen_slugs: dict[str, set] = defaultdict(set)
    skipped: dict[str, int] = defaultdict(int)

    for p in iter_rows(V3, "il_posts"):
        if p["post_status"] != "publish":
            continue
        if p["post_type"] != "content":
            continue
        facets = post_facets(p["ID"], post_terms, taxonomies)
        collection = pick_collection(facets)
        if collection is None:
            skipped["wrapper_or_drift"] += 1
            continue

        slug = p["post_name"]
        if not slug:
            slug = slugify(p["post_title"])
        # de-dupe within collection
        if slug in seen_slugs[collection]:
            slug = f"{slug}-{p['ID']}"
        seen_slugs[collection].add(slug)

        title = p["post_title"]
        # Strip trailing parenthesised dates from the title for the frontmatter
        title_clean = re.sub(r"\s+\([^)]+\)\s*$", "", title).strip() or title

        body_md = html_to_markdown(p["post_content"])
        pub_date = p["post_date"]  # already 'YYYY-MM-DD HH:MM:SS'
        if isinstance(pub_date, str):
            # Convert to ISO 8601 with timezone
            pub_iso = pub_date.replace(" ", "T") + "Z"
        else:
            pub_iso = str(pub_date)

        lang = language_from_facets(facets)
        tags = facets.get("content_tag", [])

        # Build frontmatter per-collection
        fm = {
            "id": slug,
            "title": title_clean,
            "pubDate": pub_iso,
            "themes": [t for t in tags if t not in PDF_WRAPPER_CATS and t not in DROP_CATS],
            "language": lang,
            "needs_review": True,
            "draft": False,
        }

        if collection == "opinions":
            author_name = author_from_title(title) or "Editorial Team"
            fm["author_name"] = author_name
        elif collection == "interviews":
            fm["subject_name"] = subject_from_title(title)
            yt = youtube_from_content(p["post_content"])
            if yt:
                fm["youtube_url"] = yt
            fm["transcript_status"] = "none"

        # Provenance footer
        guid = p.get("guid", "")
        body_md = (
            body_md
            + f"\n\n---\n\n_Sourced from the WordPress database export (post ID {p['ID']}, "
            + f"{guid}). Needs editorial review._"
        )

        path = CONTENT_ROOT / collection / f"{slug}.md"
        write_md_with_frontmatter(path, fm, body_md)
        counts[collection] += 1

    print("\n=== Extraction complete ===")
    for c, n in sorted(counts.items()):
        print(f"  {c}: {n} entries")
    print(f"\nSkipped (PDF-wrapper or drift): {skipped['wrapper_or_drift']}")


if __name__ == "__main__":
    main()
