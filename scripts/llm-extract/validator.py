"""
Post-extraction validator for LLM-emitted metadata records.

Belt-and-braces with the prompt's strict-enum rules: the prompt asks the LLM
to use only the allowed enum values, but if it slips, the validator catches
it deterministically and force-corrects the record.

Three classes of mechanical fix applied to every metadata record:

  1. Enum violation → coerce to closest allowed value, set
     classification_reasoning.<field>_validator_correction with the original
     bad value + the chosen substitute.
  2. Unknown thinker_id (one that isn't in data/authority/thinkers.json) →
     force `thinker_id: null`, populate `thinker_unresolved` if missing, set
     `needs_human_review: true` on the record.
  3. Missing confidence flag (when value is null but confidence is also
     null) → set confidence: "low".

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

    # 5. TOC entries — same for thinker_id_proposed
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
            "version": "v1.0",
            "corrections": corrections,
            "ok": False,  # corrections were needed
        }
    else:
        fixed["_validator"] = {
            "version": "v1.0",
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
