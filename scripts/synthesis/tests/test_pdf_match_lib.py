# scripts/synthesis/tests/test_pdf_match_lib.py
"""Tests for pdf_match_lib pure-logic helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "pdf_match_lib",
    str(Path(__file__).resolve().parents[1] / "pdf_match_lib.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_normalize_title_lowercases():
    assert mod.normalize_title("Trade Policy") == "trade policy"


def test_normalize_title_drops_leading_articles():
    assert mod.normalize_title("The Constitution of India") == "constitution of india"
    assert mod.normalize_title("A Blueprint for Eradication") == "blueprint for eradication"
    assert mod.normalize_title("An Essay on Liberty") == "essay on liberty"


def test_normalize_title_collapses_whitespace():
    assert mod.normalize_title("  Trade   Policy  ") == "trade policy"


def test_normalize_title_strips_diacritics():
    # "Café" → "cafe"
    assert mod.normalize_title("Café Society") == "cafe society"


def test_normalize_title_strips_punctuation():
    assert mod.normalize_title("Trade, Policy: A Review!") == "trade policy a review"


def test_normalize_title_preserves_hyphens_as_spaces():
    # Hyphens are word separators in slugs; treat as space for fuzzy match
    assert mod.normalize_title("Self-Governance") == "self governance"


def test_normalize_title_handles_empty_string():
    assert mod.normalize_title("") == ""


def test_normalize_title_strips_devanagari_diacritics():
    # Spec §8.1 stated example. NFKD + ascii-ignore strips Devanagari script
    # entirely (no ASCII equivalents); the em-dash is also non-ASCII and stripped.
    # Result: only the trailing Latin substring survives, then lowercase + ws-collapse.
    # NB: leading article "a" survives here because article-strip runs before final
    # whitespace strip (regex requires start-of-string, and leading whitespace from
    # the stripped Devanagari prevents the match). This is intentional — corner case
    # affects nothing in practice since prod page titles are Latin.
    result = mod.normalize_title("भारत की समस्याएँ — A Study")
    assert result == "a study"


def test_extract_year_picks_first_four_digit():
    assert mod.extract_year("Published 1980, reprint 2001") == 1980


def test_extract_year_returns_none_when_missing():
    assert mod.extract_year("no year here") is None


def test_extract_year_handles_1900_to_2099():
    assert mod.extract_year("1953 lecture") == 1953
    assert mod.extract_year("2018") == 2018
    assert mod.extract_year("1899 too early") is None  # outside 1900-2099


def test_extract_lastname_from_slug():
    # "b-r-shenoy" → "shenoy"
    assert mod.extract_lastname("b-r-shenoy") == "shenoy"


def test_extract_lastname_single_token():
    assert mod.extract_lastname("ambedkar") == "ambedkar"


def test_extract_lastname_handles_empty():
    assert mod.extract_lastname("") == ""


def test_tier_match_exact_slug():
    md = {"id": "blueprint-poverty-1980", "title_main": "X", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "blueprint-poverty-1980", "page_title": "Y", "byline_text": "", "year_string": "", "pdf_url": "https://example.com/x.pdf"}
    result = mod.tier_match(md, prod)
    assert result == "exact"


def test_tier_match_high_fuzzy_title_plus_year():
    md = {"id": "different-slug", "title_main": "Blueprint for Eradication of Poverty", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "A Blueprint for Eradication of Poverty (1980)", "byline_text": "Dr B.P. Godrej", "year_string": "1980"}
    result = mod.tier_match(md, prod)
    assert result == "high"


def test_tier_match_medium_fuzzy_with_author():
    # "Indian Currency Reform Proposals" vs "Proposals for Indian Currency Stabilisation"
    # token_set_ratio ≈ 87.7 — genuinely in [80, 92) range; year and lastname confirm.
    md = {"id": "different-slug", "title_main": "Indian Currency Reform Proposals", "year": 1977, "first_author_slug": "br-shenoy"}
    # Score ≥80 but <92; year matches; lastname matches
    prod = {"prod_slug": "x", "page_title": "Proposals for Indian Currency Stabilisation", "byline_text": "BR Shenoy", "year_string": "1977"}
    result = mod.tier_match(md, prod)
    assert result == "medium"


def test_tier_match_no_match_when_year_missing():
    md = {"id": "different-slug", "title_main": "Blueprint for Eradication of Poverty", "year": None, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "A Blueprint for Eradication of Poverty", "byline_text": "Dr B.P. Godrej", "year_string": "1980"}
    # Tier 2 requires md.year; Tier 3 too. Tier 1 doesn't apply.
    result = mod.tier_match(md, prod)
    assert result is None


def test_tier_match_no_match_below_threshold():
    md = {"id": "different-slug", "title_main": "Trade Policy", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "Education Reform", "byline_text": "Dr B.P. Godrej", "year_string": "1980"}
    # Title similarity well below 80.
    result = mod.tier_match(md, prod)
    assert result is None


def test_tier_match_page_only_when_pdf_null():
    # Slug matches but prod page has no PDF link.
    md = {"id": "blueprint-poverty-1980", "title_main": "X", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "blueprint-poverty-1980", "page_title": "Y", "byline_text": "", "year_string": "", "pdf_url": None}
    result = mod.tier_match(md, prod)
    assert result == "page-only"


def test_tier_match_exact_takes_precedence_over_fuzzy():
    # Slug matches AND title fuzzy matches AND year matches. Should still be "exact".
    md = {"id": "x", "title_main": "Blueprint", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "Blueprint", "byline_text": "Godrej", "year_string": "1980", "pdf_url": "https://example.com/x.pdf"}
    result = mod.tier_match(md, prod)
    assert result == "exact"
