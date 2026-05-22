#!/usr/bin/env python3
"""
Step 0 of the byline-resolution pipeline.

Walks apps/site/src/content/primary-works/*.md, finds entries where
authors[] is empty AND contributors[] has no thinker refs, and emits
a candidate JSONL record per entry. Each record carries title, slug,
work_type, year, pdf_staging_path, and a list of token_candidates
heuristically extracted from title+slug.

Token-candidate extraction:
  1. Take title.main + slug (id) as input.
  2. Replace common separators (by, —, ·, :, ,, em-dash, en-dash, /, " - ")
     with spaces. Split on whitespace.
  3. For each token: lowercase, kebab-case (collapse punctuation+ws to '-'),
     trim trailing/leading '-'.
  4. Drop tokens matching any of:
     - Honorifics (whole-token): dr, dr., mr, mr., mrs, mrs., ms, ms.,
       prof, prof., shri, sir, sri, smt, lady, lord
     - Year regex: \\b(19|20)\\d{2}\\b anywhere in token
     - Month names + abbreviations: january..december + jan..dec
     - Day ordinals/numerals: ^[0-9]+(st|nd|rd|th)?$
     - Roman ordinals (conference labels): valid Roman numerals of length >= 2
     - The literal token 'by'

Run:
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-batches.py
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-batches.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW_DIR = ROOT / "apps/site/src/content/primary-works"
OUT = ROOT / "data/byline-resolve/candidates.jsonl"

# Module-level constants so reviewer and implementer can audit the drop-list.
HONORIFICS = {
    "dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.",
    "prof", "prof.", "shri", "sir", "sri", "smt", "lady", "lord",
}
MONTHS = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
}
_YEAR_RX = re.compile(r"\b(19|20)\d{2}\b")
_DAY_RX = re.compile(r"^[0-9]+(st|nd|rd|th)?$")
# Month-prefix tokens like "feb11", "jan3", "dec25" — date fragments in slugs
_MONTH_PREFIX_RX = re.compile(
    r"^(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\d+$"
)
# Valid Roman numeral pattern targeting conference labels like III, IV, XVIII.
# Uses a proper Roman numeral grammar so 'mil', 'vid', 'lid' (Indic surname tokens
# that are NOT valid Roman numerals) survive. Requires length >= 2 to preserve
# single-char initials like 'i', 'v', 'x' that may appear in name abbreviations.
_ROMAN_RX = re.compile(
    r"^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$",
    re.IGNORECASE,
)
_SLUG_RX = re.compile(r"^[a-z][a-z0-9-]*$")

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def parse_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm = m.group(1)

    # Title.main (handle quoted + bare YAML scalar)
    tm = re.search(r"^\s+main:\s*[\"']?(.+?)[\"']?\s*$", fm, re.M)
    title = tm.group(1).strip() if tm else ""

    wt = re.search(r"^work_type:\s*[\"']?([a-z_]+)[\"']?", fm, re.M)
    work_type = wt.group(1) if wt else None

    yr = re.search(r"^\s+year:\s*(\d{4})", fm, re.M)
    year = int(yr.group(1)) if yr else None

    pdf = re.search(r'^pdf_staging_path:\s*"?([^"\n]+?)"?\s*$', fm, re.M)
    pdf_path = pdf.group(1).strip() if pdf else None

    # Detect existing bylines: authors[] non-empty OR contributors[] with thinker:
    has_authors = bool(re.search(r"^authors:\s*\n\s+-\s+", fm, re.M))
    has_contribs = bool(re.search(r"^contributors:\s*\n\s+-\s+thinker:", fm, re.M))

    return {
        "title": title,
        "work_type": work_type,
        "year": year,
        "pdf_staging_path": pdf_path,
        "has_byline": has_authors or has_contribs,
    }


def tokenize(title: str, slug: str) -> list[str]:
    """Return the de-duplicated, drop-list-filtered token candidates."""
    raw = f"{title} {slug}"
    # Normalize separators
    raw = re.sub(r"[—–\-–—·:,/]", " ", raw)
    raw = re.sub(r"\bby\b", " ", raw, flags=re.IGNORECASE)
    tokens: list[str] = []
    for piece in raw.split():
        # kebab the piece: lowercase, punctuation→hyphen, collapse, strip
        kebab = piece.lower()
        kebab = re.sub(r"[^a-z0-9]+", "-", kebab)
        kebab = re.sub(r"-+", "-", kebab).strip("-")
        if not kebab:
            continue
        # Drop-list checks
        if kebab in HONORIFICS:
            continue
        if kebab in MONTHS:
            continue
        if _YEAR_RX.search(kebab):
            continue
        if _MONTH_PREFIX_RX.match(kebab):
            continue
        if _DAY_RX.match(kebab):
            continue
        if _ROMAN_RX.match(kebab) and len(kebab) >= 2:
            # Proper Roman numeral grammar: 'mil', 'vid', 'lid' are invalid Roman
            # numerals and survive. Single-char initials (i/v/x) are preserved via
            # the len >= 2 guard.
            continue
        tokens.append(kebab)
    # Deduplicate, preserve order
    return list(dict.fromkeys(tokens))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_total = n_bylined = n_unbylined = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for md in sorted(PW_DIR.glob("*.md")):
            n_total += 1
            parsed = parse_frontmatter(md)
            if not parsed:
                continue
            if parsed["has_byline"]:
                n_bylined += 1
                continue
            n_unbylined += 1
            rec = {
                "id": md.stem,
                "title": parsed["title"],
                "slug": md.stem,
                "work_type": parsed["work_type"],
                "year": parsed["year"],
                "pdf_staging_path": parsed["pdf_staging_path"],
                "token_candidates": tokenize(parsed["title"], md.stem),
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  total primary-works: {n_total}")
    print(f"  with byline already: {n_bylined}")
    print(f"  unbylined → emitted: {n_unbylined}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


def _run_tests():
    # tokenize() — happy path
    assert tokenize("Free Enterprise and Democracy", "free-enterprise-and-democracy-a-d-shroff-feb11-1956") == [
        "free", "enterprise", "and", "democracy", "a", "d", "shroff",
    ], tokenize("Free Enterprise and Democracy", "free-enterprise-and-democracy-a-d-shroff-feb11-1956")

    # Honorifics drop
    assert "dr" not in tokenize("Dr. B. P. Godrej", "")
    assert "mr" not in tokenize("Mr. R. Mody", "")
    assert "prof" not in tokenize("Prof. Gangadhar", "")

    # Year drop
    assert "1956" not in tokenize("", "speech-1956-shroff")
    assert "feb11" not in tokenize("", "feb11-1956")  # year regex catches the embedded year

    # Month drop
    assert "january" not in tokenize("January Lecture", "")
    assert "feb" not in tokenize("Feb Lecture", "")

    # Day-ordinal drop
    assert "1st" not in tokenize("1st", "")
    assert "25" not in tokenize("25", "")

    # Roman-numeral drop (short conference labels)
    assert "iii" not in tokenize("III Conference", "")
    assert "xviii" not in tokenize("XVIII Lecture", "")
    assert "iv" not in tokenize("IV Symposium", "")
    # Indic surname tokens that look superficially roman are KEPT:
    assert "mil" in tokenize("S. K. Mil Lecture", "S-K-Mil-1972"), "mil should survive (no roman lead)"
    assert "vid" in tokenize("R. K. Vid", "r-k-vid"), "vid should survive (no roman lead)"
    assert "lid" in tokenize("P. Lid Speech", "p-lid"), "lid should survive (no roman lead)"

    # 'by' drop
    assert "by" not in tokenize("Free Markets by Friedman", "")

    # Slug already kebab-cased survives
    assert "a-d-shroff" in tokenize("", "free-enterprise-a-d-shroff-1956") or \
           ("a" in tokenize("", "free-enterprise-a-d-shroff-1956") and
            "d" in tokenize("", "free-enterprise-a-d-shroff-1956"))

    # Deduplication
    out = tokenize("Free Enterprise", "free-enterprise-speech")
    assert out.count("free") == 1
    assert out.count("enterprise") == 1

    print("prepare-byline-batches tests passed.")


if __name__ == "__main__":
    sys.exit(main())
