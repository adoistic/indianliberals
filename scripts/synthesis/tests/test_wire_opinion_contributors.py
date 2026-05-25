#!/usr/bin/env python3
"""Tests for wire_opinion_contributors.py helpers."""
from __future__ import annotations
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "wire_opinion_contributors",
    str(Path(__file__).resolve().parents[1] / "wire_opinion_contributors.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


BODY_WITH_PHOTO_BIO = """\
Some body text.

Another paragraph.

![](https://indianliberals.in/wp-content/uploads/2020/12/sanjeet.jpg)

**Sanjeet Kashyap**

A classic liberal by persuasion, Sanjeet has a BA in History from Hansraj College…
"""

BODY_NAME_ONLY_BIO = """\
Some body text.

**Naina Ojha**
Naina is a writer from Ghaziabad, Uttar Pradesh, currently pursuing a Master's in Gender Studies from Ambedkar University, Delhi.
"""

BODY_NO_BIO = """\
Just body text. No bio block at the end.
"""


def test_strip_bio_with_photo():
    out = mod.strip_bio_block(BODY_WITH_PHOTO_BIO)
    assert "A classic liberal" not in out
    assert "Sanjeet Kashyap" not in out
    assert "indianliberals.in" not in out
    assert "Some body text." in out
    assert "Another paragraph." in out

def test_strip_bio_name_only():
    out = mod.strip_bio_block(BODY_NAME_ONLY_BIO)
    assert "Naina is a writer" not in out
    assert "Naina Ojha" not in out
    assert "Some body text." in out

def test_strip_bio_no_bio_passthrough():
    out = mod.strip_bio_block(BODY_NO_BIO)
    assert out == BODY_NO_BIO

def test_set_frontmatter_author_inserts():
    fm = "id: foo\ntitle: bar\nauthor_name: Editorial Team\n"
    out = mod.set_frontmatter_author(fm, "sanjeet-kashyap")
    assert "author: sanjeet-kashyap" in out
    assert "author_name: Editorial Team" in out   # other fields preserved

def test_set_frontmatter_author_replaces():
    fm = "id: foo\nauthor: old-author\nauthor_name: X\n"
    out = mod.set_frontmatter_author(fm, "new-author")
    assert "author: new-author" in out
    assert "author: old-author" not in out

BODY_WITH_REFERENCES_THEN_BIO = """\
Some article body about Anandibai.

Even amidst societal distress, Joshee was hell-bent on sending Anandi.

**References **

Dall, Caroline Healey. The Life of Dr. Anandabai Joshee. Boston: Roberts Brothers, 1888.

Joshi, Through a Changing Feminist Lens. EPW Vol. 49, No. 33 (2014): 37-40.

Kosambi, Meera. Retrieving a Fragmented Feminist Image. EPW Vol. 31, No. 49 (1996).

**Naina Ojha **
Naina is a writer from Ghaziabad, Uttar Pradesh. She is pursuing a Master's in Gender Studies from Ambedkar University, Delhi.
"""

BODY_WITH_NON_ALLOWLIST_HEADING_THEN_BIO = """\
Some article body.

**Bose as an Educationist**
Abala Bose's reforms in girls' education spanned three decades from her institution-building in Bengal to the founding of Nari Shiksha Samiti.

**Kavya Sharma **
Kavya is an Indian Liberal Fellow at CCS who writes on women's history and educational reform across nineteenth-century India.
"""

BODY_STRAY_LINK_NO_BIO = """\
Article body paragraph.

[](https://indianliberals.in/content/foo/attachment/bio/)
"""

FRONTMATTER_AUTHOR_EMPTY = "id: foo\nauthor_name: Editorial Team\nauthor: \nsubject: bar\n"


def test_strip_bio_with_references_section_above():
    """Regression: an opinion with a '**References **' section + bibliography
    before the trailing bio block must NOT strip the references."""
    out = mod.strip_bio_block(BODY_WITH_REFERENCES_THEN_BIO)
    # References and bibliography survive.
    assert "**References **" in out, "References heading should survive"
    assert "Dall, Caroline Healey" in out, "first bibliography entry should survive"
    assert "Kosambi" in out, "last bibliography entry should survive"
    # Trailing bio block is gone.
    assert "Naina Ojha" not in out
    assert "Naina is a writer" not in out

def test_strip_bio_picks_last_match_over_section_heading():
    """Regression: a non-allowlist section heading like '**Bose as an Educationist**'
    earlier in the body must not anchor the strip — the LAST opener wins."""
    out = mod.strip_bio_block(BODY_WITH_NON_ALLOWLIST_HEADING_THEN_BIO)
    assert "Bose as an Educationist" in out, "section heading should survive"
    assert "Abala Bose's reforms" in out, "section body should survive"
    assert "Kavya Sharma" not in out, "trailing bio should be stripped"

def test_strip_bio_stray_link_only():
    """Body with only a stray /attachment/bio/ link and no real bio block:
    stray link is scrubbed, rest is preserved."""
    out = mod.strip_bio_block(BODY_STRAY_LINK_NO_BIO)
    assert "/attachment/bio/" not in out
    assert "Article body paragraph." in out

def test_set_frontmatter_author_replaces_empty_value():
    """Regression: an empty `author: ` line must be replaced in-place, not
    appended (which would create two `author:` keys)."""
    out = mod.set_frontmatter_author(FRONTMATTER_AUTHOR_EMPTY, "sanjeet-kashyap")
    # exactly one `author:` line
    assert out.count("\nauthor:") + (1 if out.startswith("author:") else 0) == 1, \
        f"expected exactly one author: line, got: {out!r}"
    assert "author: sanjeet-kashyap" in out
    assert "author_name: Editorial Team" in out

if __name__ == "__main__":
    n_pass = n_fail = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                n_pass += 1
                print(f"PASS {name}")
            except AssertionError as e:
                n_fail += 1
                print(f"FAIL {name}: {e}", file=sys.stderr)
    sys.exit(0 if n_fail == 0 else 1)
