# scripts/synthesis/pdf_match_lib.py
"""Pure-logic helpers for PDF link matching.

No I/O. No side effects. Shared by match-pdfs.py and tests.
"""
from __future__ import annotations

import re
import string
import unicodedata

from rapidfuzz import fuzz


_LEADING_ARTICLE_RX = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
_PUNCT_TABLE = str.maketrans({c: " " for c in string.punctuation})
_WS_RX = re.compile(r"\s+")


def normalize_title(s: str) -> str:
    """Lowercase, drop diacritics, drop leading article, drop punctuation,
    collapse whitespace. Used for fuzzy-match similarity scoring."""
    if not s:
        return ""
    # NFKD decomposition + strip combining marks → ASCII-equivalent.
    decomposed = unicodedata.normalize("NFKD", s)
    ascii_form = decomposed.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_form.lower()
    no_punct = lowered.translate(_PUNCT_TABLE)
    no_article = _LEADING_ARTICLE_RX.sub("", no_punct)
    collapsed = _WS_RX.sub(" ", no_article).strip()
    return collapsed


_YEAR_RX = re.compile(r"\b(19|20)\d{2}\b")


def extract_year(s: str) -> int | None:
    """Find first four-digit year in [1900, 2099] in the string. Returns
    int or None."""
    if not s:
        return None
    m = _YEAR_RX.search(s)
    return int(m.group(0)) if m else None


def extract_lastname(thinker_slug: str) -> str:
    """The slug's last hyphen-separated token is the lastname for matching
    purposes. (e.g. 'b-r-shenoy' → 'shenoy')"""
    if not thinker_slug:
        return ""
    return thinker_slug.rsplit("-", 1)[-1]


# Confidence thresholds (rapidfuzz.fuzz.token_set_ratio, 0-100 scale).
THRESHOLD_HIGH = 92
THRESHOLD_MEDIUM = 80


def tier_match(md: dict, prod: dict) -> str | None:
    """Walk the three-tier ladder. Return the matched confidence label or None.

    md: {"id": str, "title_main": str, "year": int | None, "first_author_slug": str}
    prod: {"prod_slug": str, "page_title": str, "byline_text": str, "year_string": str,
           "pdf_url": str | None}  # pdf_url only inspected for page-only detection

    Tiers (first hit wins):
      1. "exact"     — md.id == prod.prod_slug
                       (returns "page-only" if prod.pdf_url is None/empty)
      2. "high"      — normalized-title token_set_ratio ≥ 92 AND md.year present
                       AND str(md.year) appears in prod.year_string
      3. "medium"    — ≥ 80 AND year match AND md.first_author_slug's lastname
                       appears (case-insensitive) in prod.byline_text
      else: None
    """
    # Tier 1: exact slug match.
    if md["id"] == prod["prod_slug"]:
        pdf = prod.get("pdf_url")
        if pdf is None or pdf == "":
            return "page-only"
        return "exact"

    # Tiers 2/3 require md.year.
    if md.get("year") is None:
        return None

    year_str = str(md["year"])
    if year_str not in (prod.get("year_string") or ""):
        return None

    score = fuzz.token_set_ratio(
        normalize_title(md["title_main"]),
        normalize_title(prod["page_title"]),
    )

    if score >= THRESHOLD_HIGH:
        return "high"

    if score >= THRESHOLD_MEDIUM:
        lastname = extract_lastname(md.get("first_author_slug") or "")
        if lastname and lastname.lower() in (prod.get("byline_text") or "").lower():
            return "medium"

    return None
