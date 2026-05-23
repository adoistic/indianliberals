#!/usr/bin/env python3
"""Unit tests for classify_thinkers_schema.validate_record()."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the parent dir importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classify_thinkers_schema import validate_record


INPUT_IDS = {"dadabhai-naoroji", "f-a-hayek", "mukesh-ambani"}


def _valid_record() -> dict:
    return {
        "id": "dadabhai-naoroji",
        "canon_status": "core",
        "tradition": "constitutional_liberal",
        "vocations": ["statesman", "economist", "writer"],
        "confidence": {"canon_status": "high", "tradition": "high", "vocations": "high"},
        "reasoning": "Foundational figure in the Indian constitutional-liberal tradition.",
    }


def test_valid_record_accepts():
    ok, errs = validate_record(_valid_record(), INPUT_IDS)
    assert ok, f"expected accept, got errors: {errs}"
    assert errs == []


def test_id_not_in_batch_rejects():
    rec = _valid_record()
    rec["id"] = "unknown-slug"
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("not in input batch" in e for e in errs)


def test_canon_status_invalid_rejects():
    rec = _valid_record()
    rec["canon_status"] = "bogus"
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("canon_status" in e and "bogus" in e for e in errs)


def test_tradition_international_influence_rejects():
    """The deprecated value international_influence is explicitly forbidden in AI output."""
    rec = _valid_record()
    rec["tradition"] = "international_influence"
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("FORBIDDEN" in e for e in errs)


def test_tradition_unknown_value_rejects():
    rec = _valid_record()
    rec["tradition"] = "neo_marxist"
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("tradition" in e and "neo_marxist" in e for e in errs)


def test_vocations_unknown_value_rejects():
    rec = _valid_record()
    rec["vocations"] = ["philosopher", "wizard"]
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("wizard" in e for e in errs)


def test_vocations_empty_list_accepts():
    """vocations: [] is valid (rare but allowed for genuinely-unknown roles)."""
    rec = _valid_record()
    rec["vocations"] = []
    ok, errs = validate_record(rec, INPUT_IDS)
    assert ok, f"expected accept, got: {errs}"


def test_confidence_missing_axis_rejects():
    rec = _valid_record()
    del rec["confidence"]["tradition"]
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("confidence.tradition" in e for e in errs)


def test_confidence_invalid_value_rejects():
    rec = _valid_record()
    rec["confidence"]["vocations"] = "very-high"
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("confidence.vocations" in e for e in errs)


def test_reasoning_empty_rejects():
    rec = _valid_record()
    rec["reasoning"] = "   "  # whitespace only
    ok, errs = validate_record(rec, INPUT_IDS)
    assert not ok
    assert any("reasoning" in e for e in errs)


if __name__ == "__main__":
    # Allow `python3 test_classify_thinkers_schema.py` invocation for quick checks
    import sys as _sys
    n_pass = n_fail = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                n_pass += 1
                print(f"PASS {name}")
            except AssertionError as e:
                n_fail += 1
                print(f"FAIL {name}: {e}", file=_sys.stderr)
    _sys.exit(0 if n_fail == 0 else 1)
