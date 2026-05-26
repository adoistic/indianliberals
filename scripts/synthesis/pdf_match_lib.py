# scripts/synthesis/pdf_match_lib.py
"""Pure-logic helpers for PDF link matching.

No I/O. No side effects. Shared by match-pdfs.py and tests.
"""
from __future__ import annotations

import re
import string
import unicodedata


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
