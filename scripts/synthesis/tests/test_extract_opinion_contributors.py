#!/usr/bin/env python3
"""Tests for extract_opinion_contributors.py helpers."""
from __future__ import annotations
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "extract_opinion_contributors",
    str(Path(__file__).resolve().parents[1] / "extract_opinion_contributors.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_slugify_simple():
    assert mod.slugify("Sanjeet Kashyap") == "sanjeet-kashyap"

def test_slugify_with_initials():
    assert mod.slugify("A. D. Shroff") == "a-d-shroff"

def test_slugify_with_unicode():
    assert mod.slugify("Frédéric Bastiat") == "frederic-bastiat"

def test_slugify_strips_trailing_punct():
    assert mod.slugify("Naina Ojha ") == "naina-ojha"

def test_sort_name_two_part():
    assert mod.sort_name("Sanjeet Kashyap") == "Kashyap, Sanjeet"

def test_sort_name_single():
    assert mod.sort_name("Naina") == "Naina"

def test_sort_name_three_part():
    assert mod.sort_name("Shivani A. Tannu") == "Tannu, Shivani A."

def test_is_false_positive_section_heading():
    assert mod.is_false_positive("Introduction") is True
    assert mod.is_false_positive("References") is True
    assert mod.is_false_positive("Way forward") is True
    assert mod.is_false_positive("Sanjeet Kashyap") is False


SAMPLE_WITH_PHOTO = """\
…body paragraphs…

![](https://indianliberals.in/wp-content/uploads/2020/12/sanjeet.jpg)

**Sanjeet Kashyap**

A classic liberal by persuasion, Sanjeet has a BA in History from Hansraj College, University of Delhi…
"""

SAMPLE_NAME_ONLY = """\
…body paragraphs…

**Naina Ojha**
Naina is a writer from Ghaziabad, Uttar Pradesh. She is pursuing a Master's in Gender Studies from Ambedkar University, Delhi…
"""

SAMPLE_NO_BIO = """\
Just a body paragraph with no trailing bio block.

A second paragraph for good measure.
"""

SAMPLE_FALSE_POSITIVE = """\
**Introduction**
This is a section heading, not an author name.

**Way forward**
Same: section, not an author.
"""


def test_extract_bio_with_photo():
    out = mod.extract_bio_block(SAMPLE_WITH_PHOTO)
    assert out is not None
    assert out["name"] == "Sanjeet Kashyap"
    assert out["photo_url"] == "https://indianliberals.in/wp-content/uploads/2020/12/sanjeet.jpg"
    assert "classic liberal" in out["bio"]

def test_extract_bio_name_only():
    out = mod.extract_bio_block(SAMPLE_NAME_ONLY)
    assert out is not None
    assert out["name"] == "Naina Ojha"
    assert out["photo_url"] is None
    assert "Ghaziabad" in out["bio"]

def test_extract_no_bio_returns_none():
    assert mod.extract_bio_block(SAMPLE_NO_BIO) is None

def test_extract_filters_false_positives():
    # "Introduction" and "Way forward" should not be picked as a contributor.
    assert mod.extract_bio_block(SAMPLE_FALSE_POSITIVE) is None


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
