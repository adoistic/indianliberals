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
