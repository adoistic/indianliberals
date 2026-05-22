#!/usr/bin/env python3
"""
Step 1 of the byline-resolution pipeline.

Loads the 453 thinkers into a normalised lookup (canonical kebab → canonical
slug; each also_known_as kebab → canonical slug). For each candidate record
in data/byline-resolve/candidates.jsonl, tries to match any token_candidate
against the lookup.

Match outcomes:
  - Unambiguous single match → emit to deterministic-resolved.jsonl with
    confidence: high, method: deterministic.
  - Multiple tokens match multiple different thinkers → defer to Step 2.
  - No match → defer to Step 2.

Note: empty also_known_as: [] is treated as "no aliases" — the loader must
not fail on the empty list case.

Run:
    .venv-extract/bin/python3 scripts/synthesis/resolve-byline-deterministic.py
    .venv-extract/bin/python3 scripts/synthesis/resolve-byline-deterministic.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
CANDIDATES = ROOT / "data/byline-resolve/candidates.jsonl"
RESOLVED = ROOT / "data/byline-resolve/deterministic-resolved.jsonl"
DEFERRED = ROOT / "data/byline-resolve/deferred.jsonl"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)
_CANONICAL_RX = re.compile(r"^\s+canonical:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_AKA_BLOCK_RX = re.compile(r"^\s+also_known_as:\s*\n((?:\s+-\s+.+\n?)+)", re.M)
_EMPTY_AKA_RX = re.compile(r"^\s+also_known_as:\s*\[\]", re.M)

# Honorific prefixes that may appear at the start of a thinker slug or
# canonical name but are stripped from title-derived token_candidates by
# prepare-byline-batches.py.  When a slug starts with one of these prefixes,
# we also index the de-prefixed form so that, e.g., 'prof-cn-vakil' can be
# found by the token key 'cn-vakil'.
_HONORIFIC_SLUG_PREFIXES = re.compile(
    r"^(dr|dr\b|prof|mr|mrs|ms|shri|sir|sri|smt|lady|lord)-"
)


def kebab(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


_COMPACTED_INITIALS_RX = re.compile(r"\b([a-z]{1,3})([a-z]{1,3})\b")

def _expand_compacted_initials(key: str) -> list[str]:
    """Yield hyphen-expanded forms for keys that contain compacted initials.

    E.g. 'bp-godrej' → 'b-p-godrej'; 'cn-vakil' → 'c-n-vakil'.
    Only expands 2- or 3-letter runs at the start of the key (the initials
    segment) followed by a longer surname part.
    """
    parts = key.split("-")
    results: list[str] = []
    for k, part in enumerate(parts):
        # Only expand prefix segments that look like compacted initials:
        # 2-3 lower-case letters that are immediately before a longer surname.
        if 1 < len(part) <= 3 and k < len(parts) - 1 and len(parts[k + 1]) > 3:
            expanded_part = "-".join(list(part))
            new_key = "-".join(parts[:k] + [expanded_part] + parts[k + 1:])
            if new_key != key:
                results.append(new_key)
    return results


def _register(lookup: dict[str, str], key: str, slug: str) -> None:
    """Add key → slug to lookup; also add derived variants.

    Derived variants:
    1. Honorific-prefix-stripped form (e.g. 'prof-cn-vakil' → 'cn-vakil').
    2. Compacted-initials-expanded form (e.g. 'bp-godrej' → 'b-p-godrej',
       'cn-vakil' → 'c-n-vakil') so that token sequences like ['b','p','godrej']
       produce the initialism key 'b-p-godrej' which lands in the lookup.
    """
    if not key:
        return
    lookup[key] = slug
    stripped = _HONORIFIC_SLUG_PREFIXES.sub("", key)
    if stripped and stripped != key:
        lookup.setdefault(stripped, slug)
        # Also expand compacted initials in the stripped form
        for expanded in _expand_compacted_initials(stripped):
            lookup.setdefault(expanded, slug)
    # Expand compacted initials in the original key too
    for expanded in _expand_compacted_initials(key):
        lookup.setdefault(expanded, slug)


def build_thinker_lookup() -> dict[str, str]:
    """Return mapping kebab-key → canonical-slug (the thinker file stem).

    For each thinker we register:
      - The slug itself (e.g. 'prof-cn-vakil').
      - The kebab of the canonical name (e.g. 'prof-cn-vakil' → same).
      - Each also_known_as entry, kebab-cased.
      - Honorific-prefix-stripped variants of all of the above (e.g.
        'prof-cn-vakil' → also 'cn-vakil') so that token sequences produced
        by prepare-byline-batches.py (which drops honorific tokens) can still
        land a match.
    """
    lookup: dict[str, str] = {}
    for md in sorted(THINKERS_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FRONTMATTER_RX.match(text)
        if not m:
            continue
        fm = m.group(1)
        slug = md.stem
        # Canonical → slug
        cn = _CANONICAL_RX.search(fm)
        if cn:
            _register(lookup, kebab(cn.group(1)), slug)
        # The slug itself is always a key
        _register(lookup, slug, slug)
        # also_known_as
        if _EMPTY_AKA_RX.search(fm):
            continue
        ab = _AKA_BLOCK_RX.search(fm)
        if not ab:
            continue
        for line in ab.group(1).splitlines():
            sub = re.match(r"\s+-\s+[\"']?(.+?)[\"']?\s*$", line)
            if sub:
                _register(lookup, kebab(sub.group(1)), slug)
    return lookup


def match_candidates(tokens: list[str], lookup: dict[str, str]) -> list[str]:
    """Return list of unique canonical slugs that any token matched.

    Strategy (applied in order):
    1. Direct token match (each token as a standalone lookup key).
    2. Initialism recombination: consecutive single-letter tokens followed
       by a multi-letter token — e.g. ['a', 'd', 'shroff'] → 'a-d-shroff'.
    3. Sliding-window join: all contiguous 2-to-MAX_WIN token windows joined
       with hyphens, tried against the lookup. This catches split two-part
       names like ['colin', 'clark'] → 'colin-clark'.

    MAX_WIN is capped at 6 to avoid combinatorial blowup on long token lists.
    """
    MAX_WIN = 6
    hits: list[str] = []

    # 1. Direct token matches — only accepted when the token itself is a
    #    multi-part key (contains a hyphen), e.g. 'a-d-shroff', 'colin-clark'.
    #    Bare single-word tokens (e.g. 'patel', 'shroff') are too ambiguous
    #    to match confidently on their own; they will be picked up by the
    #    window join (strategy 3) when combined with adjacent tokens.
    for t in tokens:
        if "-" in t and t in lookup:
            hits.append(lookup[t])

    # 2. Initialism recombination: walk runs of single-letter tokens followed
    #    by a multi-letter token, build joined keys.
    for i in range(len(tokens)):
        # Collect run of single chars starting at i
        if len(tokens[i]) != 1:
            continue
        j = i
        while j < len(tokens) and len(tokens[j]) == 1:
            j += 1
        if j >= len(tokens):
            continue
        # tokens[i:j] are single chars, tokens[j] is a multi-char name
        joined = "-".join(tokens[i : j + 1])
        if joined in lookup:
            hits.append(lookup[joined])

    # 3. Sliding-window join for multi-word names (2..MAX_WIN tokens)
    n = len(tokens)
    for win in range(2, min(MAX_WIN + 1, n + 1)):
        for i in range(n - win + 1):
            joined = "-".join(tokens[i : i + win])
            if joined in lookup:
                hits.append(lookup[joined])

    # 4. Middle-initial stripping: for each 3+-token window, also try the
    #    version with interior single-letter tokens removed.  This handles
    #    patterns like ['murarji', 'j', 'vaidya'] → 'murarji-vaidya' and
    #    ['adi', 'a', 'godrej'] → 'adi-godrej' where the middle initial is
    #    present in the slug but absent from the thinker slug.
    for win in range(3, min(MAX_WIN + 1, n + 1)):
        for i in range(n - win + 1):
            window = tokens[i : i + win]
            # Remove each single-letter token that is NOT at position 0 or -1
            for j in range(1, len(window) - 1):
                if len(window[j]) == 1:
                    stripped = window[:j] + window[j + 1 :]
                    joined = "-".join(stripped)
                    if joined in lookup:
                        hits.append(lookup[joined])

    return list(dict.fromkeys(hits))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    if not CANDIDATES.exists():
        print(f"ERROR: {CANDIDATES} not found. Run prepare-byline-batches.py first.", file=sys.stderr)
        return 1

    lookup = build_thinker_lookup()
    print(f"thinker lookup size: {len(lookup)} keys → {len(set(lookup.values()))} unique slugs")

    n_resolved = n_deferred = n_ambiguous = 0
    with RESOLVED.open("w", encoding="utf-8") as f_res, \
         DEFERRED.open("w", encoding="utf-8") as f_def, \
         CANDIDATES.open("r", encoding="utf-8") as f_in:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            hits = match_candidates(rec.get("token_candidates", []), lookup)
            if len(hits) == 1:
                # Unambiguous single match
                out = {
                    "id": rec["id"],
                    "matches": [{"slug": hits[0], "role": "author"}],
                    "confidence": "high",
                    "method": "deterministic",
                }
                f_res.write(json.dumps(out, ensure_ascii=False) + "\n")
                n_resolved += 1
            elif len(hits) > 1:
                # Multiple distinct matches — defer
                rec["deterministic_hits"] = hits
                f_def.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_ambiguous += 1
            else:
                # No match — defer
                f_def.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_deferred += 1
    print(f"  resolved deterministically: {n_resolved}")
    print(f"  deferred (no match): {n_deferred}")
    print(f"  deferred (ambiguous, ≥2 matches): {n_ambiguous}")
    print(f"  wrote {RESOLVED.relative_to(ROOT)} + {DEFERRED.relative_to(ROOT)}")
    return 0


def _run_tests():
    # kebab
    assert kebab("A. D. Shroff") == "a-d-shroff"
    assert kebab("  N.A. Palkhivala ") == "n-a-palkhivala"
    assert kebab("R.C. Cooper") == "r-c-cooper"

    # match_candidates: direct match
    lookup = {
        "a-d-shroff": "a-d-shroff",
        "ardeshir-darabshaw-shroff": "a-d-shroff",
        "nani-palkhivala": "nani-palkhivala",
        "milton-friedman": "milton-friedman",
    }
    assert match_candidates(["a-d-shroff", "1956"], lookup) == ["a-d-shroff"]
    assert match_candidates(["nani-palkhivala"], lookup) == ["nani-palkhivala"]

    # match_candidates: initialism recombination
    # tokens ['a', 'd', 'shroff'] should match 'a-d-shroff'
    assert match_candidates(["a", "d", "shroff"], lookup) == ["a-d-shroff"]
    assert match_candidates(["free", "enterprise", "a", "d", "shroff"], lookup) == ["a-d-shroff"]

    # match_candidates: no match
    assert match_candidates(["random", "tokens"], lookup) == []

    # match_candidates: trailing multi-letter token after initialism run
    # j stops at the first multi-letter token; subsequent multi-letter tokens
    # like 'lecture' are NOT consumed into the initialism key.
    assert match_candidates(["a", "d", "shroff", "lecture"], lookup) == ["a-d-shroff"]
    assert match_candidates(["free", "a", "d", "shroff", "lecture"], lookup) == ["a-d-shroff"]

    # match_candidates: multi-hit ambiguity
    lookup2 = {**lookup, "a-d-iyer": "a-d-iyer"}
    # Single 'a' wouldn't match anything (single-letter alone), but
    # an aka collision could; not exercising that path in tests.

    # match_candidates: sliding-window join (two-word names split into tokens)
    lookup_cw = {"colin-clark": "colin-clark", "nani-palkhivala": "nani-palkhivala"}
    assert match_candidates(["agriculture", "colin", "clark", "1971"], lookup_cw) == ["colin-clark"]
    assert match_candidates(["free", "markets", "nani", "palkhivala"], lookup_cw) == ["nani-palkhivala"]

    # match_candidates: middle-initial stripping (['murarji', 'j', 'vaidya'] → 'murarji-vaidya')
    lookup_mv = {"murarji-vaidya": "murarji-vaidya"}
    assert match_candidates(["crisis", "murarji", "j", "vaidya"], lookup_mv) == ["murarji-vaidya"]
    assert match_candidates(["minoo", "r", "shroff"], {"minoo-shroff": "minoo-shroff"}) == ["minoo-shroff"]

    # match_candidates: bare single-word tokens WITHOUT hyphens do NOT fire direct match
    # (prevents surname-only false positives like 'patel' → 'sardar-patel')
    lookup_bare = {"patel": "sardar-patel", "shroff": "a-d-shroff"}
    assert match_candidates(["equity", "global", "patel"], lookup_bare) == []

    # Empty token list
    assert match_candidates([], lookup) == []

    # build_thinker_lookup: empty also_known_as: [] must not crash.
    # We exercise this against an actual temp-dir of two thinker files,
    # one with populated AKAs and one with the empty-list form.
    import tempfile
    sample_populated = '''---
id: foo-bar
name:
  canonical: "Foo Bar"
  also_known_as:
    - "F. Bar"
    - "Foo B."
---
'''
    sample_empty = '''---
id: baz-qux
name:
  canonical: "Baz Qux"
  also_known_as: []
---
'''
    # build_thinker_lookup: honorific-stripped variant + compacted-initial expansion
    sample_prof = '''---
id: prof-cn-vakil
name:
  canonical: "Prof CN Vakil"
  also_known_as: []
---
'''
    sample_bp = '''---
id: bp-godrej
name:
  canonical: "BP Godrej"
  also_known_as: []
---
'''
    global THINKERS_DIR
    orig_th = THINKERS_DIR
    try:
        with tempfile.TemporaryDirectory() as td:
            THINKERS_DIR = Path(td)
            (THINKERS_DIR / "foo-bar.md").write_text(sample_populated)
            (THINKERS_DIR / "baz-qux.md").write_text(sample_empty)
            (THINKERS_DIR / "prof-cn-vakil.md").write_text(sample_prof)
            (THINKERS_DIR / "bp-godrej.md").write_text(sample_bp)
            lookup3 = build_thinker_lookup()
            # Both canonical names + the aka aliases land in the lookup;
            # empty-aka thinker still gets its canonical + slug entries.
            assert lookup3.get("foo-bar") == "foo-bar"
            assert lookup3.get("f-bar") == "foo-bar"
            assert lookup3.get("foo-b") == "foo-bar"
            assert lookup3.get("baz-qux") == "baz-qux"
            # Honorific-stripped: 'prof-cn-vakil' → also 'cn-vakil'
            assert lookup3.get("prof-cn-vakil") == "prof-cn-vakil"
            assert lookup3.get("cn-vakil") == "prof-cn-vakil", f"expected cn-vakil, got {lookup3.get('cn-vakil')}"
            # Compacted-initials expansion: 'cn-vakil' → also 'c-n-vakil'
            assert lookup3.get("c-n-vakil") == "prof-cn-vakil", f"expected c-n-vakil, got {lookup3.get('c-n-vakil')}"
            # 'bp-godrej' → also 'b-p-godrej'
            assert lookup3.get("bp-godrej") == "bp-godrej"
            assert lookup3.get("b-p-godrej") == "bp-godrej", f"expected b-p-godrej, got {lookup3.get('b-p-godrej')}"
    finally:
        THINKERS_DIR = orig_th

    print("resolve-byline-deterministic tests passed.")


if __name__ == "__main__":
    sys.exit(main())
