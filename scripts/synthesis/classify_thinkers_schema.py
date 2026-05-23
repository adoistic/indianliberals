#!/usr/bin/env python3
"""
Validation schema for the thinkers AI-bulk-classifier output records.

See docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md §6.

Exports:
  CANON_STATUS_VALUES   — 4-tuple
  TRADITION_VALUES      — 8-tuple (the AI-allowed values)
  TRADITION_FORBIDDEN   — 1-tuple ('international_influence' — deprecated, schema-rejected)
  VOCATIONS_VALUES      — 25-tuple
  CONFIDENCE_VALUES     — 3-tuple
  validate_record(rec, input_ids) → (ok: bool, errors: list[str])

CLI:
  python3 scripts/synthesis/classify_thinkers_schema.py validate <output.json>
      Exits 0 if every record in the array validates; non-zero if any rejected.
      Prints per-record errors to stderr.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CANON_STATUS_VALUES = ("core", "extended", "referenced", "unclassified")

TRADITION_VALUES = (
    "classical_liberal",
    "libertarian",
    "constitutional_liberal",
    "contemporary_liberal",
    "social_reformer",
    "non_liberal",
    "practice",
    "unclassified",
)

# Deprecated; the post-Chunk-2 thinker schema still ACCEPTS this value (the 86
# existing entries that use it) but the AI MUST NEVER emit it. Spec §6.1.
TRADITION_FORBIDDEN = ("international_influence",)

VOCATIONS_VALUES = (
    # Academic / theoretical
    "philosopher", "economist", "historian", "political_scientist",
    "sociologist", "legal_scholar", "scientist", "engineer", "professor",
    # Writing / editorial
    "writer", "editor", "journalist", "poet",
    # Public office / governance
    "statesman", "parliamentarian", "civil_servant", "diplomat", "judge",
    # Business / enterprise
    "industrialist", "entrepreneur",
    # Civil society
    "activist", "reformer", "religious_figure",
    # Other
    "military_officer", "artist",
)

CONFIDENCE_VALUES = ("high", "medium", "low")


def validate_record(rec: dict, input_ids: set[str]) -> tuple[bool, list[str]]:
    """Validate one classification output record per spec §6.

    Args:
        rec: a dict (parsed from JSON).
        input_ids: the set of thinker IDs that were in the corresponding input batch;
                   used to validate `rec["id"]` is one of them.

    Returns:
        (ok, errors): ok is True iff errors is empty.
    """
    errors: list[str] = []

    rec_id = rec.get("id")
    if not isinstance(rec_id, str) or not rec_id:
        errors.append("missing or non-string `id`")
    elif rec_id not in input_ids:
        errors.append(f"`id` {rec_id!r} not in input batch")

    cs = rec.get("canon_status")
    if cs not in CANON_STATUS_VALUES:
        errors.append(f"`canon_status` {cs!r} not in {CANON_STATUS_VALUES}")

    tr = rec.get("tradition")
    if tr in TRADITION_FORBIDDEN:
        errors.append(f"`tradition` {tr!r} is FORBIDDEN in AI output (deprecated value; spec §6.1)")
    elif tr not in TRADITION_VALUES:
        errors.append(f"`tradition` {tr!r} not in {TRADITION_VALUES}")

    vocs = rec.get("vocations")
    if not isinstance(vocs, list):
        errors.append(f"`vocations` not a list (got {type(vocs).__name__})")
    else:
        for v in vocs:
            if v not in VOCATIONS_VALUES:
                errors.append(f"`vocations` value {v!r} not in the 25-value enum")

    conf = rec.get("confidence")
    if not isinstance(conf, dict):
        errors.append(f"`confidence` not a dict (got {type(conf).__name__})")
    else:
        for axis in ("canon_status", "tradition", "vocations"):
            if axis not in conf:
                errors.append(f"`confidence.{axis}` missing")
            elif conf[axis] not in CONFIDENCE_VALUES:
                errors.append(f"`confidence.{axis}` {conf[axis]!r} not in {CONFIDENCE_VALUES}")

    reasoning = rec.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        errors.append("`reasoning` missing or empty")

    return (len(errors) == 0, errors)


def _cli_validate(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print(f"ERROR: {path}: top-level value is not a JSON array", file=sys.stderr)
        return 1

    # For CLI use, accept any id (no input batch to cross-reference). The
    # bulk applier will pass the real input_ids set in process.
    all_ids = {r.get("id") for r in data if isinstance(r, dict)}
    n_ok, n_bad = 0, 0
    for i, rec in enumerate(data):
        if not isinstance(rec, dict):
            print(f"ERROR: {path}: record {i} not an object", file=sys.stderr)
            n_bad += 1
            continue
        ok, errs = validate_record(rec, all_ids)
        if ok:
            n_ok += 1
        else:
            n_bad += 1
            print(f"REJECT {rec.get('id', '?')}: {'; '.join(errs)}", file=sys.stderr)

    print(f"validated: {n_ok} ok, {n_bad} rejected (of {len(data)})")
    return 0 if n_bad == 0 else 1


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "validate":
        return _cli_validate(Path(argv[2]))
    print(f"usage: python3 {Path(__file__).name} validate <output.json>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
