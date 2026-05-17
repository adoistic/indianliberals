"""
Transliteration module for the Indian Liberals LLM extraction pipeline — v1.2.

Converts Indic-script name forms (Devanagari, Bengali, Gujarati) to a
normalised Latin string suitable for binary matching against the authority
file's byline_lookup map.

Library used: indic-transliteration (pip install indic-transliteration).
Note: aksharamukha-python was the design doc's first choice but it uses
ast.Str which was removed in Python 3.14. indic-transliteration covers
Devanagari, Bengali, and Gujarati at the same quality level and works on
Python 3.14.

Output scheme: IAST (International Alphabet of Sanskrit Transliteration).
This matches the diacritic style already used in the authority file's
`translit` fields (e.g. v1.1 records produced "Samasyāẽ Bhārat Kī" for
the Sharad Joshi book title).

Matching strategy (D3):
  1. Try direct case-folded + whitespace-collapsed + punctuation-stripped
     match against authority byline_lookup. This wins without transliteration
     when the Indic alias is directly in also_known_as[].
  2. If no direct match, transliterate Indic text to IAST, then also strip
     diacritics to plain ASCII (so "kṛṣṇamācārī" → "krsnamacari") and try
     the normalised ASCII form. This handles the common case where authority
     canonical/alias uses an ASCII rendering (e.g. "Krishnamachari") that
     doesn't survive round-trip through diacritics.
  3. Surface failures in recommended_authority_additions[].

Diacritic stripping rationale:
  aksharamukha / indic-transliteration emit full IAST with diacritics.
  Authority file canonical names typically use simplified ASCII or approximate
  Latin (e.g. "Nehru" not "Neharū", "Ambedkar" not "Āmbeḍakara"). Stripping
  diacritics in the comparison path dramatically improves match rate while
  retaining the diacriticised form for display/archival.
"""

from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# Unicode range constants for script detection
# ---------------------------------------------------------------------------

_DEVANAGARI_RANGE = (0x0900, 0x097F)
_BENGALI_RANGE = (0x0980, 0x09FF)
_GUJARATI_RANGE = (0x0A80, 0x0AFF)


def detect_script(text: str) -> str:
    """
    Detect the dominant Indic script in text.

    Returns one of: 'devanagari', 'bengali', 'gujarati', 'latin', 'mixed'.
    Decision is majority-character based — the script of most non-space
    characters wins. Latin wins by default when no Indic script is detected.
    """
    counts = {"devanagari": 0, "bengali": 0, "gujarati": 0, "latin": 0}
    for ch in text:
        cp = ord(ch)
        if _DEVANAGARI_RANGE[0] <= cp <= _DEVANAGARI_RANGE[1]:
            counts["devanagari"] += 1
        elif _BENGALI_RANGE[0] <= cp <= _BENGALI_RANGE[1]:
            counts["bengali"] += 1
        elif _GUJARATI_RANGE[0] <= cp <= _GUJARATI_RANGE[1]:
            counts["gujarati"] += 1
        elif ch.isalpha():
            counts["latin"] += 1

    total_indic = counts["devanagari"] + counts["bengali"] + counts["gujarati"]
    if total_indic == 0:
        return "latin"

    indic_scripts = {k: v for k, v in counts.items() if k != "latin"}
    dominant = max(indic_scripts, key=lambda k: indic_scripts[k])

    # "mixed" when Latin is also substantial
    if counts["latin"] > 0 and counts["latin"] >= total_indic * 0.5:
        return "mixed"

    return dominant


# ---------------------------------------------------------------------------
# IAST transliteration
# ---------------------------------------------------------------------------

_SCRIPT_MAP = {
    "devanagari": "Devanagari",
    "bengali": "Bengali",
    "gujarati": "Gujarati",
}


def _transliterate_to_iast(text: str, script: str) -> str:
    """
    Transliterate Indic text to IAST using indic-transliteration.

    script must be one of 'devanagari', 'bengali', 'gujarati'.
    Raises ImportError if indic-transliteration is not installed.
    """
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate as _trans
    except ImportError as exc:
        raise ImportError(
            "indic-transliteration is required: "
            "pip install indic-transliteration"
        ) from exc

    src_scheme_name = _SCRIPT_MAP.get(script)
    if src_scheme_name is None:
        raise ValueError(f"Unsupported source script: {script!r}")

    src_scheme = getattr(sanscript, src_scheme_name.upper(), None)
    if src_scheme is None:
        raise ValueError(f"indic-transliteration has no scheme for: {src_scheme_name!r}")

    return _trans(text, src_scheme, sanscript.IAST)


# ---------------------------------------------------------------------------
# Normalisation helpers (mirror byline_lookup convention in thinkers.json)
# ---------------------------------------------------------------------------

def _normalise_lookup(s: str) -> str:
    """
    Normalise a string the same way the authority file's byline_lookup is built:
    lowercase, strip punctuation, collapse whitespace.
    """
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)   # strip punctuation (keeps word chars + spaces)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_diacritics(s: str) -> str:
    """
    Strip Unicode diacritics / combining marks from an IAST string,
    yielding plain ASCII (approximately).

    e.g. "kṛṣṇamācārī" → "krsnamacari",
         "javāharalāla neharū" → "javāharalāla neharu" → "javaharalala neharu"
    """
    # NFD decomposes precomposed characters into base + combining marks
    nfd = unicodedata.normalize("NFD", s)
    # Drop every character in the "Mn" (Mark, Nonspacing) category
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    # Also drop any remaining non-ASCII characters that weren't decomposable
    stripped = stripped.encode("ascii", errors="ignore").decode("ascii")
    return stripped


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def latin_match_form(indic_text: str, source_script: str = "auto") -> str:
    """
    Transliterate Indic-script text to a normalised Latin form for
    authority-file matching (IAST → diacritics stripped → lowercased).

    Parameters
    ----------
    indic_text:
        The name as it appears in the source PDF, in Devanagari, Bengali,
        or Gujarati script.
    source_script:
        'devanagari', 'bengali', 'gujarati', or 'auto' (detect from text).

    Returns
    -------
    A lowercase, punctuation-stripped, diacritic-free ASCII string suitable
    for binary comparison against keys in byline_lookup (which are built the
    same way from the canonical / alias Latin forms).

    Raises ValueError if auto-detection finds no Indic characters (pass a
    Latin-script string directly to _normalise_lookup instead).
    """
    if source_script == "auto":
        source_script = detect_script(indic_text)
        if source_script in ("latin", "mixed"):
            # Already Latin — just normalise
            return _normalise_lookup(indic_text)

    iast = _transliterate_to_iast(indic_text, source_script)
    ascii_form = _strip_diacritics(iast)
    return _normalise_lookup(ascii_form)


def resolve_indic_name(
    indic_text: str,
    byline_lookup: dict[str, str],
    source_script: str = "auto",
) -> str | None:
    """
    Try to resolve an Indic-script name to an authority-file thinker_id.

    Strategy:
    1. Direct normalised match (works when the Indic form is in also_known_as[]).
    2. IAST-with-diacritics match (rarely needed but included for robustness).
    3. Diacritics-stripped ASCII match (the main workhorse for names like
       "Krishnamachari", "Nehru", "Gandhi" that are ASCII in the authority file).

    Returns thinker_id string or None if no match.
    """
    # Step 1: direct normalised match (Indic key in byline_lookup)
    direct_key = _normalise_lookup(indic_text)
    if direct_key in byline_lookup:
        return byline_lookup[direct_key]

    # Steps 2 + 3: transliterate then match
    if source_script == "auto":
        detected = detect_script(indic_text)
        if detected in ("latin", "mixed"):
            return None  # can't transliterate Latin
        source_script = detected

    try:
        iast = _transliterate_to_iast(indic_text, source_script)
    except (ImportError, ValueError):
        return None

    # Step 2: IAST with diacritics (normalised)
    iast_key = _normalise_lookup(iast)
    if iast_key in byline_lookup:
        return byline_lookup[iast_key]

    # Step 3: strip diacritics → plain ASCII
    ascii_key = _normalise_lookup(_strip_diacritics(iast))
    if ascii_key in byline_lookup:
        return byline_lookup[ascii_key]

    return None


# ---------------------------------------------------------------------------
# __main__ — quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from pathlib import Path

    REPO = Path(__file__).resolve().parents[2]
    auth_file = REPO / "data/authority/thinkers.json"

    if not auth_file.exists():
        print("Authority file not found; skipping smoke test.")
    else:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
        byline_lookup = data.get("byline_lookup", {})

        test_cases = [
            ("जवाहरलाल नेहरू", "devanagari", "jawaharlal-nehru"),
            ("महात्मा गांधी", "devanagari", "mahatma-gandhi"),
            ("मीनू मसानी", "devanagari", "minoo-masani"),
            ("रवीन्द्रनाथ टैगोर", "devanagari", "rabindranath-tagore"),
            ("রবীন্দ্রনাথ ঠাকুর", "bengali", "rabindranath-tagore"),
            ("भीमराव आंबेडकर", "devanagari", "bhimrao-ambedkar"),
            ("सरदार पटेल", "devanagari", "sardar-patel"),
        ]

        print("Smoke test — transliteration + resolve_indic_name:")
        all_pass = True
        for indic, script, expected_id in test_cases:
            resolved = resolve_indic_name(indic, byline_lookup, source_script=script)
            status = "PASS" if resolved == expected_id else "FAIL"
            if status == "FAIL":
                all_pass = False
            latin = latin_match_form(indic, source_script=script)
            print(f"  [{status}] {indic!r} → {latin!r} → {resolved!r} (expected: {expected_id!r})")

        print()
        if all_pass:
            print("All smoke tests passed.")
        else:
            print("Some smoke tests failed — check authority file and aliases.")
            raise SystemExit(1)
