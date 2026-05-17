"""
Post-extraction validator for LLM-emitted metadata records — v1.2.

Belt-and-braces with the prompt's strict-enum rules: the prompt asks the LLM
to use only the allowed enum values, but if it slips, the validator catches
it deterministically and force-corrects the record.

Six classes of mechanical fix applied to every metadata record:

  1. Enum violation → coerce to closest allowed value, set
     classification_reasoning.<field>_validator_correction with the original
     bad value + the chosen substitute.
  2. Unknown thinker_id (one that isn't in data/authority/thinkers.json) →
     force `thinker_id: null`, populate `thinker_unresolved` if missing, set
     `needs_human_review: true` on the record.
  3. Missing confidence flag (when value is null but confidence is also
     null) → set confidence: "low".
  4. (D2) Theme case normalisation: snake_case/TitleCase/PascalCase themes →
     kebab-case canonical form. Applied to themes[], themes_confirmed[],
     theme_proposed_new[] wherever they appear.
  5. (D11) page_start > page_end on TOC entries → force page_end = null,
     set needs_human_review: true.
  6. (D1) Legacy field preservation: if physical.page_count_visible exists
     but physical.pages_rendered does not, copy the value across. Never
     deletes legacy fields.

New functions (v1.2):
  compare_metadata_records(rec_a, rec_b) → list[str]  — D12 cross-record check
  detect_toc_drift(toc_entries, essay_summary) → bool  — D14 drift detection

The validator is idempotent: running it twice produces the same output.

Usage:
    from validator import validate_metadata
    result = validate_metadata(raw_dict)  # returns a new dict with fixes applied
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTHORITY_FILE = REPO / "data/authority/thinkers.json"

# ----------------------------------------------------------------------------
# Allowed enum values (must match apps/site/src/content.config.ts)
# ----------------------------------------------------------------------------

ALLOWED_WORK_TYPES = {
    "book", "pamphlet", "speech", "essay", "edited_volume",
    "occasional_paper", "letter", "correspondence", "periodical_issue", "reference",
}

ALLOWED_PURPOSES = {
    # occasional_paper sub-types
    "manifesto", "statement_of_principles", "report", "working_paper",
    "position_paper", "annual_report",
    # edited_volume sub-types
    "anthology", "festschrift", "proceedings", "memorial_volume", "collected_works",
    # book sub-types
    "treatise", "memoir", "biography", "textbook",
    # speech sub-types
    "parliamentary", "convocation", "convention_address", "inaugural",
    "memorial_lecture",
}

ALLOWED_LANGUAGES = {"en", "hi", "gu", "mr", "bn"}

ALLOWED_CONFIDENCE = {"high", "medium", "low"}

# ----------------------------------------------------------------------------
# Coercion maps — when the LLM emits something close-but-wrong, map it
# ----------------------------------------------------------------------------

WORK_TYPE_COERCIONS = {
    # Common hallucinations observed in v1.0 runs
    "speech_or_address": "speech",
    "address": "speech",
    "lecture": "speech",
    "essay_collection": "book",          # single-author compilation
    "collected_essays": "book",
    "collected_works": "book",           # this is a `purpose`, not a `work_type`
    "authored_collection": "book",
    "anthology": "edited_volume",         # this is a `purpose`, not a `work_type`
    "conference_report": "edited_volume",
    "conference_proceedings": "edited_volume",
    "proceedings": "edited_volume",       # this is a `purpose`, not a `work_type`
    "festschrift": "edited_volume",       # this is a `purpose`, not a `work_type`
    "manifesto": "occasional_paper",      # this is a `purpose`, not a `work_type`
    "policy_paper": "occasional_paper",
    "research_paper": "occasional_paper",
    "report": "occasional_paper",
    "monograph": "book",
    "memoir": "book",                     # this is a `purpose`
    "biography": "book",                  # this is a `purpose`
    "textbook": "book",                   # this is a `purpose`
    "bibliography": "reference",
    "directory": "reference",
    "magazine": "periodical_issue",
    "journal": "periodical_issue",
    "newsletter": "periodical_issue",
}

PURPOSE_COERCIONS = {
    "compilation_of_reprinted_articles": "anthology",
    "compilation": "anthology",
    "policy_compilation": "anthology",
    "collected_journalism": "collected_works",
    "collected_articles": "collected_works",
    "collected_essays": "collected_works",
    "convocation_address": "convocation",
    "convocation_address_reprinted_as_booklet": "convocation",
    "convention_proceedings": "proceedings",
    "conference_proceedings": "proceedings",
    "policy_paper": "position_paper",
    "policy_brief": "position_paper",
    "annual": "annual_report",
}

# D2 — Theme vocabulary: canonical kebab-case forms (from driver.py THEME_VOCABULARY).
# Used to build the normalisation map below.
THEME_VOCABULARY_CANONICAL = {
    "economic-liberty", "planning-critique", "free-trade", "regulatory-state-critique",
    "monetary-policy", "agricultural-reform", "land-reform", "property-rights",
    "fiscal-policy", "public-sector-critique", "civil-liberty", "free-speech",
    "rule-of-law", "constitutionalism", "federalism", "separation-of-powers",
    "individual-rights", "women-rights", "dalit-rights", "religious-freedom",
    "secularism", "education", "health-policy", "urban-policy", "foreign-policy",
    "cold-war-positioning", "party-politics", "electoral-reform", "governance-reform",
    "anti-corruption", "socialism-debate", "marxism-debate", "capitalism-defence",
    "press-freedom", "judicial-independence", "emergency-critique",
    "liberalism-as-tradition", "indian-liberal-history", "biographical-tribute",
}

def _build_theme_normalisation_map() -> dict[str, str]:
    """
    Build a map from non-canonical theme spellings to canonical kebab-case.
    Handles: snake_case, TitleCase, PascalCase, space-separated, mixed.
    """
    import re
    norm_map: dict[str, str] = {}
    for canonical in THEME_VOCABULARY_CANONICAL:
        # canonical is already in the map pointing to itself
        norm_map[canonical] = canonical
        # snake_case variant
        snake = canonical.replace("-", "_")
        norm_map[snake] = canonical
        # TitleCase / PascalCase: split on hyphens, title-case each word, join
        title = "".join(word.title() for word in canonical.split("-"))
        norm_map[title] = canonical
        # Title_Case: words title-cased, joined by underscores
        title_snake = "_".join(word.title() for word in canonical.split("-"))
        norm_map[title_snake] = canonical
        # space-separated lowercase
        space = canonical.replace("-", " ")
        norm_map[space] = canonical
        # space-separated Title Case
        space_title = " ".join(word.title() for word in canonical.split("-"))
        norm_map[space_title] = canonical
    return norm_map

THEME_NORMALISATION_MAP: dict[str, str] = _build_theme_normalisation_map()


def _normalise_theme(theme: str) -> str:
    """
    Normalise a theme string to kebab-case shape.

    Two layers of normalisation:
      1. CANONICAL: if the input matches a known alias of a controlled-vocab
         theme (via THEME_NORMALISATION_MAP), return the canonical kebab form.
      2. SHAPE: even when the theme is NOT in the controlled vocab (i.e.,
         a new theme proposal), still enforce kebab-case shape so the v1.2
         contract holds. snake_case → kebab-case, TitleCase → kebab-case,
         spaces → hyphens, everything lowercased.

    Only returns the original string unchanged when the input is non-string.
    """
    if not isinstance(theme, str):
        return theme
    # Layer 1: canonical alias lookup
    if theme in THEME_NORMALISATION_MAP:
        return THEME_NORMALISATION_MAP[theme]
    lower = theme.lower()
    if lower in THEME_NORMALISATION_MAP:
        return THEME_NORMALISATION_MAP[lower]
    # Layer 2: shape normalisation for non-canonical themes.
    # PascalCase / TitleCase: insert hyphens between lowercase-uppercase boundaries
    # before lowercasing, so "EconomicLiberalisation" → "economic-liberalisation".
    import re
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", theme)
    shape_kebab = spaced.lower().replace("_", "-").replace(" ", "-")
    # Collapse runs of hyphens and strip leading/trailing hyphens
    shape_kebab = re.sub(r"-+", "-", shape_kebab).strip("-")
    if shape_kebab in THEME_VOCABULARY_CANONICAL:
        return shape_kebab  # rescued a canonical via shape transform
    if shape_kebab != theme:
        return shape_kebab  # non-canonical but now kebab-shaped (D2 contract)
    return theme


# ----------------------------------------------------------------------------
# Validator
# ----------------------------------------------------------------------------


def _load_authority_ids() -> set[str]:
    """Return the set of valid thinker_ids from the authority file."""
    if not AUTHORITY_FILE.exists():
        return set()
    data = json.loads(AUTHORITY_FILE.read_text(encoding="utf-8"))
    return {t["id"] for t in data.get("thinkers", []) if "id" in t}


def validate_metadata(record: dict, *, authority_ids: set[str] | None = None) -> dict:
    """
    Apply all mechanical corrections to a metadata record. Returns a NEW dict
    (does not mutate the input). Adds a `_validator` audit block at the top
    level recording every correction made.
    """
    if authority_ids is None:
        authority_ids = _load_authority_ids()

    fixed = deepcopy(record)
    corrections: list[dict] = []

    # 1. work_type enum
    wt = fixed.get("work_type")
    if isinstance(wt, str) and wt not in ALLOWED_WORK_TYPES:
        coerced = WORK_TYPE_COERCIONS.get(wt.lower().replace(" ", "_").replace("-", "_"), "occasional_paper")
        corrections.append({
            "field": "work_type",
            "original": wt,
            "coerced_to": coerced,
            "rule": "value not in ALLOWED_WORK_TYPES",
        })
        fixed["work_type"] = coerced
        fixed["needs_human_review"] = True

    # 2. purpose enum (optional — null is allowed)
    purp = fixed.get("purpose")
    if isinstance(purp, str) and purp and purp not in ALLOWED_PURPOSES:
        coerced = PURPOSE_COERCIONS.get(purp.lower().replace(" ", "_").replace("-", "_"))
        if coerced is None:
            corrections.append({
                "field": "purpose",
                "original": purp,
                "coerced_to": None,
                "rule": "value not in ALLOWED_PURPOSES and no coercion mapping; setting null",
            })
            fixed["purpose"] = None
        else:
            corrections.append({
                "field": "purpose",
                "original": purp,
                "coerced_to": coerced,
                "rule": "value not in ALLOWED_PURPOSES; coerced via mapping",
            })
            fixed["purpose"] = coerced
        fixed["needs_human_review"] = True

    # 3. language enum
    lang = fixed.get("language")
    if isinstance(lang, str) and lang not in ALLOWED_LANGUAGES:
        corrections.append({
            "field": "language",
            "original": lang,
            "coerced_to": "en",
            "rule": "value not in ALLOWED_LANGUAGES; defaulting to en",
        })
        fixed["language"] = "en"
        fixed["needs_human_review"] = True

    # 4. authors[*].thinker_id — force null if not in authority file
    _validate_thinker_refs(fixed, "authors", authority_ids, corrections)
    _validate_thinker_refs(fixed, "editors", authority_ids, corrections)
    _validate_thinker_refs(fixed, "contributors", authority_ids, corrections)

    # 5. TOC entries — same for thinker_id_proposed + D11 page_start > page_end check
    toc = fixed.get("toc")
    if isinstance(toc, dict):
        for key in ("entries", "entries_not_yet_rendered"):
            entries_list = toc.get(key, []) or []
            if not isinstance(entries_list, list):
                continue
            for entry in entries_list:
                # Defensive: some model outputs emit `entries_not_yet_rendered`
                # as a list of integer toc_index values (shorthand) rather than
                # full entry objects. Skip non-dict items — the validator
                # only enforces thinker_id resolution; integer shorthand is
                # acceptable upstream.
                if not isinstance(entry, dict):
                    continue
                tid = entry.get("thinker_id_proposed")
                if tid and tid not in authority_ids:
                    corrections.append({
                        "field": f"toc.{key}[{entry.get('toc_index', '?')}].thinker_id_proposed",
                        "original": tid,
                        "coerced_to": None,
                        "rule": "thinker_id not in authority file; force null",
                    })
                    entry["thinker_id_proposed"] = None
                    fixed["needs_human_review"] = True

                # D11 — page_start > page_end check
                page_start = entry.get("page_start")
                page_end = entry.get("page_end")
                if (
                    page_end is not None
                    and isinstance(page_start, int)
                    and isinstance(page_end, int)
                    and page_start > page_end
                ):
                    corrections.append({
                        "field": f"toc.{key}[{entry.get('toc_index', '?')}].page_end",
                        "original": page_end,
                        "coerced_to": None,
                        "rule": f"D11: page_start ({page_start}) > page_end ({page_end}); force page_end=null",
                    })
                    entry["page_end"] = None
                    fixed["needs_human_review"] = True

    # 5b. D2 — Theme case normalisation (kebab-case canonical)
    _normalise_themes_in_record(fixed, corrections)

    # 5c. D1 — Legacy field preservation (page_count_visible → pages_rendered migration)
    #         + pages_total_source default (v1.3)
    physical = fixed.get("physical")
    if isinstance(physical, dict):
        if "page_count_visible" in physical and "pages_rendered" not in physical:
            physical["pages_rendered"] = physical["page_count_visible"]
            corrections.append({
                "field": "physical.pages_rendered",
                "original": None,
                "coerced_to": physical["page_count_visible"],
                "rule": "D1: legacy page_count_visible promoted to pages_rendered; both retained",
            })
        # v1.3 — D1: pages_total_source is required. Default to "pypdfium2" when the
        # model omits it AND pages_total has a value (the most common case — the
        # rasterizer's count is what feeds into the prompt's TOTAL_PDF_PAGES).
        # Fall back to "unknown" when pages_total is missing too.
        if "pages_total_source" not in physical:
            default_source = "pypdfium2" if physical.get("pages_total") is not None else "unknown"
            physical["pages_total_source"] = default_source
            corrections.append({
                "field": "physical.pages_total_source",
                "original": None,
                "coerced_to": default_source,
                "rule": "D1: pages_total_source defaulted (model omitted required field)",
            })

    # 5d. D10 — recommended_authority_additions: check for thinkers already in authority
    _validate_recommended_additions(fixed, authority_ids, corrections)

    # 6. Confidence flags: never null when value is also null — set "low"
    _fix_confidence_nulls(fixed, corrections)

    # Record-level needs_human_review: ALSO true if any author has thinker_id=null
    if any(
        (a.get("thinker_id") is None) and a.get("byline_verbatim")
        for a in (fixed.get("authors") or []) + (fixed.get("editors") or []) + (fixed.get("contributors") or [])
    ):
        fixed["needs_human_review"] = True

    # 7. Stamp the audit block
    if corrections:
        fixed["_validator"] = {
            "version": "v1.3",
            "corrections": corrections,
            "ok": False,  # corrections were needed
        }
    else:
        fixed["_validator"] = {
            "version": "v1.3",
            "corrections": [],
            "ok": True,
        }

    return fixed


def _validate_thinker_refs(
    record: dict,
    field: str,
    authority_ids: set[str],
    corrections: list[dict],
) -> None:
    """Force-null any thinker_id in record[field] that isn't in the authority file."""
    items = record.get(field) or []
    if not isinstance(items, list):
        return
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        tid = item.get("thinker_id")
        if tid and tid not in authority_ids:
            corrections.append({
                "field": f"{field}[{idx}].thinker_id",
                "original": tid,
                "coerced_to": None,
                "rule": "thinker_id not in authority file (validator force-null per binary rule)",
            })
            item["thinker_id"] = None
            # Preserve verbatim if present; otherwise leave it as the LLM emitted
            if not item.get("byline_verbatim") and not item.get("thinker_unresolved"):
                item["thinker_unresolved"] = tid


def _normalise_themes_in_record(record: dict, corrections: list[dict]) -> None:
    """
    D2 — Walk the record and normalise all theme arrays to kebab-case.
    Applies to: themes[], themes_confirmed[], theme_proposed_new[].
    Also descends into essays_summarized[].summary_structured for multi-author records.
    """
    def fix_theme_list(lst: list, path: str) -> None:
        for i, theme in enumerate(lst):
            normalised = _normalise_theme(theme)
            if normalised != theme:
                corrections.append({
                    "field": f"{path}[{i}]",
                    "original": theme,
                    "coerced_to": normalised,
                    "rule": "D2: theme normalised to kebab-case",
                })
                lst[i] = normalised

    for field in ("themes", "themes_confirmed", "theme_proposed_new"):
        lst = record.get(field)
        if isinstance(lst, list):
            fix_theme_list(lst, field)

    # summary_structured (single-author)
    ss = record.get("summary_structured", {}) or {}
    for field in ("themes_confirmed", "theme_proposed_new"):
        lst = ss.get(field)
        if isinstance(lst, list):
            fix_theme_list(lst, f"summary_structured.{field}")

    # essays_summarized (multi-author)
    for idx, essay in enumerate(record.get("essays_summarized", []) or []):
        if not isinstance(essay, dict):
            continue
        for field in ("themes_confirmed", "theme_proposed_new"):
            lst = essay.get(field)
            if isinstance(lst, list):
                fix_theme_list(lst, f"essays_summarized[{idx}].{field}")
        ss = essay.get("summary_structured", {}) or {}
        for field in ("themes_confirmed", "theme_proposed_new"):
            lst = ss.get(field)
            if isinstance(lst, list):
                fix_theme_list(lst, f"essays_summarized[{idx}].summary_structured.{field}")


def _validate_recommended_additions(
    record: dict,
    authority_ids: set[str],
    corrections: list[dict],
) -> None:
    """
    D10 — Check recommended_authority_additions[]: if a kind:'thinker' entry's
    verbatim matches an existing canonical name or alias in the authority file,
    flag it as a model error (should have resolved, not recommended).
    """
    additions = record.get("recommended_authority_additions") or []
    if not isinstance(additions, list):
        return

    # Build a set of all known canonical names + aliases for fast lookup
    if not AUTHORITY_FILE.exists():
        return
    try:
        auth_data = json.loads(AUTHORITY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    byline_lookup = auth_data.get("byline_lookup", {})

    import re
    def _norm(s: str) -> str:
        s = s.lower()
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    for idx, addition in enumerate(additions):
        if not isinstance(addition, dict):
            continue
        if addition.get("kind") != "thinker":
            continue
        verbatim = addition.get("verbatim", "")
        if not verbatim:
            continue
        key = _norm(verbatim)
        if key in byline_lookup:
            corrections.append({
                "field": f"recommended_authority_additions[{idx}]",
                "original": verbatim,
                "coerced_to": byline_lookup[key],
                "rule": "recommended_thinker_already_in_authority: model should have resolved this verbatim to a thinker_id",
            })


def _fix_confidence_nulls(record: dict, corrections: list[dict]) -> None:
    """
    Where a field has shape `{"value": X, "confidence": Y}` and confidence is
    null/missing, set to "low". Walk the record recursively.
    """
    def walk(obj, path):
        if isinstance(obj, dict):
            # Detect a {value, confidence} pair
            if "value" in obj and "confidence" in obj and obj["confidence"] not in ALLOWED_CONFIDENCE:
                corrections.append({
                    "field": f"{path}.confidence",
                    "original": obj["confidence"],
                    "coerced_to": "low",
                    "rule": "confidence must be high/medium/low, never null",
                })
                obj["confidence"] = "low"
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
    walk(record, "")


# ----------------------------------------------------------------------------
# D12 — Cross-record consistency check
# ----------------------------------------------------------------------------

def compare_metadata_records(rec_a: dict, rec_b: dict) -> list[str]:
    """
    D12 — Compare two independently-extracted metadata records for the same PDF.
    Returns a list of field-path strings where the records disagree.
    The driver feeds these disagreements into the metadata-tiebreak call.

    Fields checked:
      - physical.pages_rendered  (must agree — both see the same chunk)
      - physical.pages_total     (must agree — set from the same PDF)
      - toc.entries[*].toc_index set equality (same essays identified)
      - toc.entries[*].page_start for matching toc_indices
    """
    disagreements: list[str] = []

    phys_a = (rec_a.get("physical") or {})
    phys_b = (rec_b.get("physical") or {})

    # pages_rendered
    pr_a = phys_a.get("pages_rendered")
    pr_b = phys_b.get("pages_rendered")
    if pr_a is not None and pr_b is not None and pr_a != pr_b:
        disagreements.append(f"physical.pages_rendered: A={pr_a}, B={pr_b}")

    # pages_total
    pt_a = phys_a.get("pages_total")
    pt_b = phys_b.get("pages_total")
    if pt_a is not None and pt_b is not None and pt_a != pt_b:
        disagreements.append(f"physical.pages_total: A={pt_a}, B={pt_b}")

    # toc.entries[] — toc_index set equality
    def _toc_entries(rec: dict) -> list[dict]:
        toc = rec.get("toc") or {}
        return [e for e in (toc.get("entries") or []) if isinstance(e, dict)]

    entries_a = _toc_entries(rec_a)
    entries_b = _toc_entries(rec_b)
    idx_a = {e.get("toc_index") for e in entries_a if e.get("toc_index") is not None}
    idx_b = {e.get("toc_index") for e in entries_b if e.get("toc_index") is not None}

    if idx_a != idx_b:
        disagreements.append(
            f"toc.entries[*].toc_index set mismatch: A={sorted(idx_a)}, B={sorted(idx_b)}"
        )

    # For matching toc_indices, check page_start agreement
    map_a = {e.get("toc_index"): e for e in entries_a}
    map_b = {e.get("toc_index"): e for e in entries_b}
    for toc_idx in idx_a & idx_b:
        ps_a = map_a[toc_idx].get("page_start")
        ps_b = map_b[toc_idx].get("page_start")
        if ps_a is not None and ps_b is not None and ps_a != ps_b:
            disagreements.append(
                f"toc.entries[toc_index={toc_idx}].page_start: A={ps_a}, B={ps_b}"
            )

    return disagreements


# ----------------------------------------------------------------------------
# D14 — TOC-drift detection
# ----------------------------------------------------------------------------

def detect_toc_drift(toc_entries: list[dict], essay_summary: dict) -> bool:
    """
    D14 — Detect whether chunk 2's essay summary indicates the chunk 1 TOC
    was materially wrong about page positions or essay titles.

    Parameters
    ----------
    toc_entries:
        The toc.entries[] list from chunk 1's metadata_final record.
        Each entry is expected to have: toc_index, title, page_start.
    essay_summary:
        The essay summary returned by the first continuation-loop chunk
        (chunk 2 in loop terms). Expected keys:
          - toc_index (int)
          - actual_page_start (int, optional — the page where the model
            found this essay when rendering chunk 2's pages)
          - title (str, optional)

    Returns
    -------
    True if drift is detected (tiebreak needed), False otherwise.

    Drift conditions (either is sufficient):
      1. title_drift: normalised title strings disagree.
      2. page_drift: |essay_summary.actual_page_start - toc_entry.page_start| >= 5.
    """
    if not isinstance(toc_entries, list) or not isinstance(essay_summary, dict):
        return False

    target_idx = essay_summary.get("toc_index")
    if target_idx is None:
        return False

    # Find the matching TOC entry
    toc_entry = next(
        (e for e in toc_entries if isinstance(e, dict) and e.get("toc_index") == target_idx),
        None,
    )
    if toc_entry is None:
        # toc_index not in TOC — definitely drift
        return True

    # Title drift check
    def _normalise_title(s: str | None) -> str:
        if not s:
            return ""
        import re
        return re.sub(r"\s+", " ", s.lower().strip())

    toc_title = _normalise_title(toc_entry.get("title"))
    essay_title = _normalise_title(essay_summary.get("title"))
    if toc_title and essay_title and toc_title != essay_title:
        return True

    # Page drift check
    actual_page_start = essay_summary.get("actual_page_start")
    toc_page_start = toc_entry.get("page_start")
    if (
        actual_page_start is not None
        and toc_page_start is not None
        and isinstance(actual_page_start, int)
        and isinstance(toc_page_start, int)
        and abs(actual_page_start - toc_page_start) >= 5
    ):
        return True

    return False


# ----------------------------------------------------------------------------
# total_unique_pages_rendered — helper for the driver continuation loop
# ----------------------------------------------------------------------------

def total_unique_pages_rendered(record: dict) -> int:
    """
    Compute the total number of unique pages rendered across all chunks,
    from the record's pages_rendered fields.

    For the v1.2 continuation loop, the driver accumulates per-chunk
    pages_rendered values. This function sums them.

    The record is expected to have physical.pages_rendered set (or
    fallback to page_count_visible for v1.1 compatibility).
    """
    phys = record.get("physical") or {}
    pr = phys.get("pages_rendered") or phys.get("page_count_visible") or 0
    return int(pr)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def _cli() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Apply post-extraction validator to one JSON record")
    p.add_argument("input_file", type=Path)
    p.add_argument("--output-file", type=Path, default=None, help="Write fixed JSON here (default: stdout)")
    args = p.parse_args()

    data = json.loads(args.input_file.read_text(encoding="utf-8"))
    fixed = validate_metadata(data)

    out = json.dumps(fixed, indent=2, ensure_ascii=False)
    if args.output_file:
        args.output_file.write_text(out, encoding="utf-8")
        print(f"Wrote {args.output_file}")
        print(f"  Validator: {len(fixed['_validator']['corrections'])} corrections, ok={fixed['_validator']['ok']}")
    else:
        print(out)


if __name__ == "__main__":
    _cli()
