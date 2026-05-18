#!/usr/bin/env python3
"""
Apply data/synthesis/ner-mentions.jsonl to live entry frontmatter.

For each entry that has mention records, validate every quote substring-
matches the body under normalisation rules, drop validation failures to
data/synthesis/ner-rejected.txt, write thinker_mentions[] + populate
related_thinkers[] in the entry's frontmatter.

Idempotent: re-running replaces thinker_mentions[] atomically per entry.

Run from repo root (after resolve-ner.py emits ner-mentions.jsonl):

    python3 scripts/synthesis/apply-ner.py
    python3 scripts/synthesis/apply-ner.py --test    # run the validator's
                                                       built-in unit tests
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
NER_MENTIONS = ROOT / "data/synthesis/ner-mentions.jsonl"
REJECTED_LOG = ROOT / "data/synthesis/ner-rejected.txt"
AUTHORITY = ROOT / "data/authority/thinkers.json"


# ─── Verbatim-substring validator ──────────────────────────────────────

_MARKDOWN_NOISE_RX = re.compile(r"[*_`>~]")
_SMART_QUOTES = {
    "“": '"', "”": '"',   # curly double quotes → straight
    "‘": "'", "’": "'",   # curly single quotes → straight
    "–": "-", "—": "-",   # en/em dashes → hyphen
}


def _normalise(text: str) -> str:
    """Normalise body or candidate quote for substring matching.

    Steps (in order):
      1. Replace smart quotes / dashes with their straight ASCII equivalents.
      2. Remove markdown emphasis markers (*, _, backtick, >, ~).
      3. Collapse all whitespace runs to a single space.
      4. Strip leading and trailing whitespace.

    Case is preserved. Trailing punctuation on the candidate quote is
    handled in `quote_substring_matches`, not here."""
    for src, dst in _SMART_QUOTES.items():
        text = text.replace(src, dst)
    text = _MARKDOWN_NOISE_RX.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def quote_substring_matches(body: str, quote: str) -> bool:
    """Return True if `quote` appears (case-sensitive) as a substring of
    `body` under our normalisation rules.

    The LLM is allowed minor formatting drift versus the body: smart-quote
    vs straight-quote, markdown emphasis around words, whitespace
    variation, and trailing punctuation. Anything beyond that — different
    words, paraphrase, hallucination — fails."""
    if not quote or not body:
        return False
    norm_body = _normalise(body)
    norm_quote = _normalise(quote)
    # Allow the candidate quote to drop a final period/comma/semicolon/colon
    # that is present in the body but not in the LLM's output.
    norm_quote = norm_quote.rstrip(".,;:")
    if not norm_quote:
        return False
    return norm_quote in norm_body


# ─── Built-in tests ────────────────────────────────────────────────────

def _run_tests() -> int:
    """Plain-Python assertion-style tests. Exits 0 on pass, 1 on fail."""
    cases = [
        # (label, body, quote, expected)
        ("exact match", "Hayek argued for spontaneous order.", "Hayek argued for spontaneous order.", True),
        ("substring", "Hayek argued for spontaneous order in 1944.", "Hayek argued for spontaneous order", True),
        ("markdown emphasis in body", "*Hayek* argued for spontaneous order.", "Hayek argued for spontaneous order", True),
        ("smart quotes in body", "Hayek’s argument was clear: “spontaneous order”.", "Hayek's argument was clear: \"spontaneous order\"", True),
        ("smart quotes in quote", "Hayek's argument was clear: \"spontaneous order\".", "Hayek’s argument was clear: “spontaneous order”", True),
        ("whitespace variation", "Hayek argued for\n\nspontaneous order.", "Hayek argued for spontaneous order", True),
        ("trailing period drop", "Hayek argued for spontaneous order.", "Hayek argued for spontaneous order.", True),
        ("trailing comma drop", "Hayek, an Austrian economist, argued.", "Hayek, an Austrian economist", True),
        ("paraphrase (must fail)", "Hayek argued for spontaneous order.", "Hayek defended unplanned market coordination.", False),
        ("hallucinated quote (must fail)", "Hayek argued for spontaneous order.", "Hayek opposed all forms of central planning.", False),
        ("empty quote (must fail)", "Hayek argued for spontaneous order.", "", False),
        ("empty body (must fail)", "", "Hayek argued for spontaneous order.", False),
        ("case-sensitive (must fail)", "Hayek argued for spontaneous order.", "hayek argued for spontaneous order", False),
        ("markdown link", "See [Hayek's Road to Serfdom](https://example.com) for more.", "Road to Serfdom", True),
        ("blockquote prefix", "> Hayek wrote: spontaneous order matters.", "Hayek wrote: spontaneous order matters.", True),
        ("underscore emphasis", "_Hayek_ argued for spontaneous order.", "Hayek argued for spontaneous order", True),
        ("backtick code span", "The term `spontaneous order` is Hayek's.", "The term spontaneous order is Hayek's.", True),
        ("em-dash normalisation", "Hayek—an Austrian economist—argued for spontaneous order.", "Hayek-an Austrian economist-argued for spontaneous order", True),
        ("en-dash normalisation", "Hayek (1899–1992) argued for spontaneous order.", "Hayek (1899-1992) argued for spontaneous order", True),
        ("mixed emphasis + apostrophe", "*Hayek*’s _Road to Serfdom_ is foundational.", "Hayek's Road to Serfdom is foundational", True),
    ]
    failed = 0
    for label, body, quote, expected in cases:
        actual = quote_substring_matches(body, quote)
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            failed += 1
        print(f"[{status}] {label}: expected={expected} got={actual}")
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    return 0 if failed == 0 else 1


# ─── Main (stub for now; full apply logic in Task 9) ───────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Run validator unit tests and exit")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.test:
        return _run_tests()

    print("apply-ner.py full apply logic lands in Task 9", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
