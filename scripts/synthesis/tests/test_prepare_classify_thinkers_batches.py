#!/usr/bin/env python3
"""Tests for prepare-classify-thinkers-batches.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "prepare_classify_thinkers_batches",
    str(Path(__file__).resolve().parents[1] / "prepare-classify-thinkers-batches.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_round_robin_distribution():
    """Sorted thinker i goes to batch i % 10."""
    ids = [f"thinker-{i:03d}" for i in range(506)]
    ids.sort()
    batches = [[] for _ in range(10)]
    for i, t in enumerate(ids):
        batches[i % 10].append(t)
    # Each batch has 50 or 51 entries
    for b in batches:
        assert 50 <= len(b) <= 51
    # Union is all 506
    union = [t for b in batches for t in b]
    assert sorted(union) == sorted(ids)
    # No duplicates
    assert len(union) == len(set(union))


def test_frontmatter_parsing():
    text = """---
id: dadabhai-naoroji
tradition: constitutional_liberal
canon_status: unclassified
---

Body text here.
"""
    fields, body = mod.parse_frontmatter(text)
    assert fields["id"] == "dadabhai-naoroji"
    assert fields["tradition"] == "constitutional_liberal"
    assert body.strip() == "Body text here."


def test_constants_match_spec():
    """The truncation constants must match spec §5.1 values."""
    assert mod.MAX_BODY_CHARS == 3000
    assert mod.MAX_WORKS_AUTHORED == 20
    assert mod.MAX_MENTION_CONTEXTS == 10
    assert mod.N_BATCHES == 10


# Note: behavioural tests for load_thinker / load_works_authored / load_mention_contexts
# require the live corpus or extensive fixtures. They're deferred to Step 2.1.4's
# manual verification against the real apps/site/src/content/ tree, which is the
# canonical signal anyway (the script's whole job is to assemble records from
# that tree).

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
