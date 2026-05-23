#!/usr/bin/env python3
"""Tests for apply-classify-thinkers.py confidence-rule application."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "apply_classify_thinkers",
    str(Path(__file__).resolve().parents[1] / "apply-classify-thinkers.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


SAMPLE_MD = """---
id: test-thinker
name:
  canonical: Test Thinker
  sort: Thinker, Test
tradition: unclassified
canon_status: unclassified
vocations: []
needs_review: true
draft: false
---

Body content here.
"""


def test_replace_canon_status_high():
    new_text = mod.replace_canon_status(SAMPLE_MD, "core")
    assert "canon_status: core" in new_text
    assert "canon_status: unclassified" not in new_text


def test_replace_tradition():
    new_text = mod.replace_tradition(SAMPLE_MD, "classical_liberal")
    assert "tradition: classical_liberal" in new_text
    assert "tradition: unclassified" not in new_text


def test_replace_vocations_nonempty():
    new_text = mod.replace_vocations(SAMPLE_MD, ["philosopher", "economist", "professor"])
    assert "vocations: [philosopher, economist, professor]" in new_text


def test_replace_vocations_empty():
    new_text = mod.replace_vocations(SAMPLE_MD, [])
    assert "vocations: []" in new_text


def test_apply_all_high():
    """All-high record overwrites the three axes; needs_review unchanged."""
    rec = {
        "id": "test-thinker",
        "canon_status": "core",
        "tradition": "classical_liberal",
        "vocations": ["philosopher"],
        "confidence": {"canon_status": "high", "tradition": "high", "vocations": "high"},
        "reasoning": "test",
    }
    out, changed_axes, set_review = mod.apply_record_to_text(SAMPLE_MD, rec)
    assert "canon_status: core" in out
    assert "tradition: classical_liberal" in out
    assert "vocations: [philosopher]" in out
    assert set_review is False  # all-high → no flip


def test_apply_medium_axis_flags_review():
    """One medium axis → write all written values + set needs_review."""
    rec = {
        "id": "test-thinker",
        "canon_status": "extended",
        "tradition": "classical_liberal",
        "vocations": ["philosopher"],
        "confidence": {"canon_status": "medium", "tradition": "high", "vocations": "high"},
        "reasoning": "test",
    }
    out, changed_axes, set_review = mod.apply_record_to_text(SAMPLE_MD, rec)
    assert "canon_status: extended" in out
    assert set_review is True


def test_apply_low_axis_skips_field():
    """One low axis → that axis NOT written; needs_review set."""
    md_with_existing_canon = SAMPLE_MD.replace("canon_status: unclassified", "canon_status: extended")
    rec = {
        "id": "test-thinker",
        "canon_status": "core",  # AI's guess
        "tradition": "classical_liberal",
        "vocations": ["philosopher"],
        "confidence": {"canon_status": "low", "tradition": "high", "vocations": "high"},
        "reasoning": "test",
    }
    out, changed_axes, set_review = mod.apply_record_to_text(md_with_existing_canon, rec)
    # canon_status NOT overwritten (low confidence)
    assert "canon_status: extended" in out
    assert "canon_status: core" not in out
    # tradition WAS overwritten
    assert "tradition: classical_liberal" in out
    assert set_review is True


def test_other_fields_untouched():
    """The applier MUST NOT modify any field other than canon_status / tradition /
    vocations / needs_review. Spec §7.1 / §10.4 #20 invariant."""
    rec = {
        "id": "test-thinker",
        "canon_status": "core",
        "tradition": "classical_liberal",
        "vocations": ["philosopher"],
        "confidence": {"canon_status": "high", "tradition": "high", "vocations": "high"},
        "reasoning": "test",
    }
    out, _, _ = mod.apply_record_to_text(SAMPLE_MD, rec)
    # The name: block must be preserved verbatim — sub-keys and indentation intact
    assert "name:" in out
    assert "  canonical: Test Thinker" in out
    assert "  sort: Thinker, Test" in out
    # The draft: line is preserved
    assert "draft: false" in out
    # The id: line is preserved
    assert "id: test-thinker" in out
    # The body content is preserved
    assert "Body content here." in out
    # And the document still has both --- delimiters
    assert out.count("---\n") >= 2


def test_idempotent_no_curator_edit():
    """Applying the same record twice produces the same text (spec §7.2
    output-stability, no-curator-edit branch)."""
    rec = {
        "id": "test-thinker",
        "canon_status": "core",
        "tradition": "classical_liberal",
        "vocations": ["philosopher"],
        "confidence": {"canon_status": "high", "tradition": "high", "vocations": "high"},
        "reasoning": "test",
    }
    once, _, _ = mod.apply_record_to_text(SAMPLE_MD, rec)
    twice, _, _ = mod.apply_record_to_text(once, rec)
    assert once == twice, "applier is not output-stable: second apply changed text"


if __name__ == "__main__":
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
