#!/usr/bin/env python3
"""Tests for pilot-classify-thinkers Jaccard agreement metric."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import the module dynamically because its filename has a hyphen
import importlib.util
spec = importlib.util.spec_from_file_location(
    "pilot_classify_thinkers",
    str(Path(__file__).resolve().parents[1] / "pilot-classify-thinkers.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
jaccard = mod._jaccard


def test_jaccard_identical():
    assert jaccard(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_jaccard_two_of_three():
    # Hayek case: gt=[philosopher, economist, professor], ai=[philosopher, economist]
    # |intersection|=2, |union|=3, Jaccard=2/3 ≈ 0.6667 → passes 0.6 threshold
    j = jaccard(["philosopher", "economist", "professor"], ["philosopher", "economist"])
    assert abs(j - 2 / 3) < 0.001
    assert j >= 0.6


def test_jaccard_one_of_four():
    # |intersection|=1, |union|=4, Jaccard=0.25 → fails threshold
    j = jaccard(["philosopher", "economist", "professor"], ["philosopher", "statesman"])
    # gt has 3, ai has 2, intersection={philosopher}=1, union=4
    assert abs(j - 0.25) < 0.001
    assert j < 0.6


def test_jaccard_disjoint():
    j = jaccard(["a", "b"], ["c", "d"])
    assert j == 0.0


def test_jaccard_both_empty():
    assert jaccard([], []) == 1.0


def test_jaccard_empty_vs_nonempty():
    assert jaccard([], ["a"]) == 0.0


def test_jaccard_set_semantics():
    # Duplicates in input should not affect (sets dedupe)
    assert jaccard(["a", "a", "b"], ["a", "b"]) == 1.0


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
