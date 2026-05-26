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


def test_build_commit_message_first_batch():
    msg = mod._build_commit_message(batch_no=1, count=20, prior_total=0, last_batch=False)
    assert msg.startswith("data(primary-works): extraction batch 1 — 20 new MDs")
    assert "Running total this run: 20." in msg
    assert "run_overnight.py" in msg
    assert "(final flush)" not in msg


def test_build_commit_message_subsequent_batch():
    msg = mod._build_commit_message(batch_no=7, count=20, prior_total=120, last_batch=False)
    assert msg.startswith("data(primary-works): extraction batch 7 — 20 new MDs")
    assert "Running total this run: 140." in msg


def test_build_commit_message_final_flush():
    msg = mod._build_commit_message(batch_no=31, count=13, prior_total=600, last_batch=True)
    assert msg.startswith("data(primary-works): extraction batch 31 — 13 new MDs (final flush)")
    assert "Running total this run: 613." in msg


def test_build_commit_message_zero_count_still_produces_string():
    # Defensive — committer should never call with 0, but if it does, don't crash.
    msg = mod._build_commit_message(batch_no=1, count=0, prior_total=0, last_batch=False)
    assert isinstance(msg, str)
    assert "0 new MDs" in msg
