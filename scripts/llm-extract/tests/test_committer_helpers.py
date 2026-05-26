"""Tests for the committer-thread pure-logic helpers in run_overnight.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Load run_overnight.py as a module so we can access internal helpers.
spec = importlib.util.spec_from_file_location(
    "run_overnight",
    str(Path(__file__).resolve().parents[1] / "run_overnight.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_parse_untracked_mds_empty_output():
    assert mod._parse_untracked_mds("") == []


def test_parse_untracked_mds_whitespace_only():
    assert mod._parse_untracked_mds("   \n\n  ") == []


def test_parse_untracked_mds_one_md():
    out = "apps/site/src/content/primary-works/foo.md\n"
    assert mod._parse_untracked_mds(out) == ["apps/site/src/content/primary-works/foo.md"]


def test_parse_untracked_mds_filters_non_md():
    out = (
        "apps/site/src/content/primary-works/foo.md\n"
        "apps/site/src/content/primary-works/.DS_Store\n"
        "apps/site/src/content/primary-works/bar.md\n"
        "apps/site/src/content/primary-works/draft.tmp\n"
    )
    assert mod._parse_untracked_mds(out) == [
        "apps/site/src/content/primary-works/foo.md",
        "apps/site/src/content/primary-works/bar.md",
    ]


def test_parse_untracked_mds_trailing_blank_lines():
    out = "apps/site/src/content/primary-works/foo.md\n\n"
    assert mod._parse_untracked_mds(out) == ["apps/site/src/content/primary-works/foo.md"]
