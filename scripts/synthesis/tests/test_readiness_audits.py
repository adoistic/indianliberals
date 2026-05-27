"""Unit tests for the content-readiness pass 1 audit scripts."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _load(stem: str):
    """Load a hyphenated script (e.g., 'audit-cross-refs') as a module."""
    mod_name = stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(
        mod_name,
        str(SCRIPTS_DIR / f"{stem}.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve cls.__module__ in Python 3.14.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


cross_refs = _load("audit-cross-refs")


# -------- audit-cross-refs.py tests --------

ThinkerInfo = cross_refs.ThinkerInfo


def _idx(*infos: ThinkerInfo) -> dict[str, ThinkerInfo]:
    return {i.slug: i for i in infos}


def test_slug_not_in_prose_simple(tmp_path):
    """A related_thinker whose canonical name is absent from prose → reported."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers:\n  - milton-friedman\n"
        "summary: This essay discusses economic policy in postwar India.\n"
        "---\n"
        "## Summary\n\nMore prose here.\n\n## Key points\n\n- a point\n"
    )
    idx = _idx(ThinkerInfo(slug="milton-friedman", canonical="Milton Friedman"))
    d = cross_refs._check_md(md, idx)
    assert d.slugs_not_in_prose == ["milton-friedman"]
    assert d.names_not_in_slugs == []


def test_slug_in_prose_via_aka(tmp_path):
    """A related_thinker whose canonical is absent but an also_known_as is present → not reported."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers:\n  - bhimrao-ambedkar\n"
        "summary: The work cites Dr Ambedkar's writings on caste.\n"
        "---\n"
        "## Summary\n\n"
    )
    idx = _idx(ThinkerInfo(
        slug="bhimrao-ambedkar",
        canonical="Bhimrao Ramji Ambedkar",
        also_known_as=["Dr Ambedkar", "B. R. Ambedkar"],
    ))
    d = cross_refs._check_md(md, idx)
    assert d.slugs_not_in_prose == []


def test_prose_name_not_in_slugs(tmp_path):
    """A thinker named in prose but absent from related_thinkers → reported."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers: []\n"
        "summary: Friedrich Hayek's Road to Serfdom is invoked.\n"
        "---\n"
    )
    idx = _idx(ThinkerInfo(slug="friedrich-hayek", canonical="Friedrich Hayek"))
    d = cross_refs._check_md(md, idx)
    assert "Friedrich Hayek" in d.names_not_in_slugs
    assert d.slugs_not_in_prose == []


def test_whole_word_match(tmp_path):
    """\"Smithson\" must NOT match \"Adam Smith\"."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers: []\n"
        "summary: The Smithsonian holds important documents.\n"
        "---\n"
    )
    idx = _idx(ThinkerInfo(slug="adam-smith", canonical="Adam Smith"))
    d = cross_refs._check_md(md, idx)
    assert d.names_not_in_slugs == []


def test_case_insensitive_match(tmp_path):
    """\"milton FRIEDMAN\" should match \"Milton Friedman\"."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers:\n  - milton-friedman\n"
        "summary: milton FRIEDMAN once wrote about monetary policy.\n"
        "---\n"
    )
    idx = _idx(ThinkerInfo(slug="milton-friedman", canonical="Milton Friedman"))
    d = cross_refs._check_md(md, idx)
    assert d.slugs_not_in_prose == []
