"""
Calibration test for the transliteration module — v1.2.

For every thinker in data/authority/thinkers.json that has at least one
Indic-script alias (Devanagari, Bengali, or Gujarati), transliterate the
alias through latin_match_form() and verify the result resolves back to the
correct thinker_id via byline_lookup.

This is the contract for D3 part 1 (design doc): if this script exits non-zero,
the cross-script resolver in summary.md §6 is untrustworthy.

Exit codes:
  0 — 100% of Indic aliases round-trip cleanly.
  1 — One or more aliases failed to round-trip; details printed to stdout.

Run:
  .venv-extract/bin/python3 scripts/llm-extract/test_transliteration.py
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

# Ensure scripts/llm-extract is on the path
sys.path.insert(0, str(Path(__file__).parent))

from transliteration import detect_script, latin_match_form, resolve_indic_name

REPO = Path(__file__).resolve().parents[2]
AUTHORITY_FILE = REPO / "data/authority/thinkers.json"

# Unicode range checks (same as transliteration.py)
_DEVANAGARI_RANGE = (0x0900, 0x097F)
_BENGALI_RANGE = (0x0980, 0x09FF)
_GUJARATI_RANGE = (0x0A80, 0x0AFF)


def _is_indic(text: str) -> bool:
    """Return True if text contains any Devanagari, Bengali, or Gujarati characters."""
    for ch in text:
        cp = ord(ch)
        if (
            _DEVANAGARI_RANGE[0] <= cp <= _DEVANAGARI_RANGE[1]
            or _BENGALI_RANGE[0] <= cp <= _BENGALI_RANGE[1]
            or _GUJARATI_RANGE[0] <= cp <= _GUJARATI_RANGE[1]
        ):
            return True
    return False


def main() -> int:
    if not AUTHORITY_FILE.exists():
        print(f"ERROR: Authority file not found: {AUTHORITY_FILE}")
        return 1

    data = json.loads(AUTHORITY_FILE.read_text(encoding="utf-8"))
    thinkers = data.get("thinkers", [])
    byline_lookup = data.get("byline_lookup", {})

    print(f"Authority file: {len(thinkers)} thinkers, {len(byline_lookup)} lookup keys")
    print()

    passes = []
    failures = []

    for thinker in thinkers:
        thinker_id = thinker.get("id", "?")
        also_known_as = thinker.get("name", {}).get("also_known_as", []) or []

        indic_aliases = [alias for alias in also_known_as if _is_indic(alias)]
        if not indic_aliases:
            continue  # no Indic aliases to test

        for alias in indic_aliases:
            script = detect_script(alias)
            if script in ("latin", "mixed"):
                # Shouldn't happen — _is_indic already filtered — but be safe
                continue

            resolved = resolve_indic_name(alias, byline_lookup, source_script=script)
            latin_form = latin_match_form(alias, source_script=script)

            if resolved == thinker_id:
                passes.append((thinker_id, alias, script, latin_form, resolved))
            else:
                failures.append((thinker_id, alias, script, latin_form, resolved))

    # Report
    total = len(passes) + len(failures)

    print(f"=== Results: {len(passes)}/{total} Indic aliases round-trip cleanly ===")
    print()

    if passes:
        print("PASSED:")
        for thinker_id, alias, script, latin_form, resolved in passes:
            print(f"  [PASS] {thinker_id}")
            print(f"         alias={alias!r}  script={script}")
            print(f"         → latin_form={latin_form!r} → resolved={resolved!r}")
        print()

    if failures:
        print("FAILED:")
        for thinker_id, alias, script, latin_form, resolved in failures:
            print(f"  [FAIL] {thinker_id}")
            print(f"         alias={alias!r}  script={script}")
            print(f"         → latin_form={latin_form!r} → resolved={resolved!r} (expected: {thinker_id!r})")
        print()
        print(
            "Diagnosis: run the following to see what key the transliterator produces"
            " and check if a matching entry is in byline_lookup:"
        )
        for thinker_id, alias, script, latin_form, resolved in failures:
            print(f"  {alias!r} → {latin_form!r}")
        print()

    if total == 0:
        print("WARNING: No thinkers with Indic aliases found in authority file.")
        print("  Run Step 2 (authority file expansion) before calibrating.")
        return 1

    if failures:
        print(f"CALIBRATION FAILED: {len(failures)}/{total} aliases don't round-trip.")
        print("Fix: add the normalised form of the failed aliases to byline_lookup,")
        print("     or adjust the alias text in also_known_as[] to a form that")
        print("     round-trips through latin_match_form() to a key already in byline_lookup.")
        return 1

    print(f"CALIBRATION PASSED: {len(passes)}/{total} Indic aliases round-trip correctly.")
    print("D3 contract satisfied — the cross-script resolver is trustworthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
