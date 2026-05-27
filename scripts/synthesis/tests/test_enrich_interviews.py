"""Unit tests for enrich-interview-mds.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _load(stem: str):
    mod_name = stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(
        mod_name, str(SCRIPTS_DIR / f"{stem}.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


enrich = _load("enrich-interview-mds")


# -------- build_authority_manifest tests --------


def test_authority_manifest_format(tmp_path):
    """Returns a deterministic, sorted list with {slug, canonical_name, also_known_as, canon_status}."""
    t1 = tmp_path / "peter-bauer.md"
    t1.write_text(
        "---\nid: peter-bauer\n"
        "name:\n  canonical: Peter Bauer\n  also_known_as: [Lord Bauer, P. T. Bauer]\n"
        "canon_status: core\n---\n"
    )
    t2 = tmp_path / "milton-friedman.md"
    t2.write_text(
        "---\nid: milton-friedman\n"
        "name:\n  canonical: Milton Friedman\n  also_known_as: []\n"
        "canon_status: core\n---\n"
    )
    manifest = enrich.build_authority_manifest(tmp_path)
    assert len(manifest) == 2
    assert [m["slug"] for m in manifest] == ["milton-friedman", "peter-bauer"]
    assert manifest[0] == {
        "slug": "milton-friedman",
        "canonical_name": "Milton Friedman",
        "also_known_as": [],
        "canon_status": "core",
    }
    assert manifest[1]["also_known_as"] == ["Lord Bauer", "P. T. Bauer"]


# -------- validate_and_clamp tests --------


def test_validate_passes_known_slugs():
    payload = {
        "summary": "s", "key_points": ["a"], "themes": ["x"],
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "display_name": "Peter Bauer", "thinker": "peter-bauer",
                "role": "mention", "reasoning": "r",
                "evidence": [{"quote": "q", "context": "c"}],
                "key_passages": [],
            }
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    assert out["thinker_mentions"][0]["thinker"] == "peter-bauer"
    assert "display_name" not in out["thinker_mentions"][0]


def test_validate_demotes_unknown_slug_via_display_name():
    payload = {
        "summary": "s", "key_points": [], "themes": [],
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "display_name": "Friedrich Hayek", "thinker": "friedrich-hayek",
                "role": "mention", "reasoning": "r",
                "evidence": [], "key_passages": [],
            }
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    mention = out["thinker_mentions"][0]
    assert "thinker" not in mention
    assert mention["thinker_unresolved"] == "Friedrich Hayek"


def test_validate_demotes_unknown_slug_via_literal_fallback():
    payload = {
        "summary": "s", "key_points": [], "themes": [],
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "thinker": "friedrich-hayek",
                "role": "mention", "reasoning": "r",
                "evidence": [], "key_passages": [],
            }
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    assert out["thinker_mentions"][0]["thinker_unresolved"] == "friedrich-hayek"


def test_validate_clamps_counts():
    payload = {
        "summary": "s",
        "key_points": [f"point-{i}" for i in range(15)],
        "themes": [f"theme-{i}" for i in range(15)],
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "display_name": f"Person {i}", "thinker": "peter-bauer",
                "role": "mention", "reasoning": "r",
                "evidence": [{"quote": f"q{j}", "context": ""} for j in range(15)],
                "key_passages": [{"quote": f"k{j}", "what_it_shows": ""} for j in range(15)],
            }
            for i in range(15)
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    assert len(out["key_points"]) == 7
    assert len(out["themes"]) == 7
    assert len(out["thinker_mentions"]) == 5
    assert len(out["thinker_mentions"][0]["evidence"]) == 5
    assert len(out["thinker_mentions"][0]["key_passages"]) == 5


# -------- truncate_transcript test --------


def test_truncate_long_transcript_preserves_endpoints():
    big = ("first-segment " * 5000) + ("MIDDLE_SHOULD_BE_DROPPED " * 5000) + ("last-segment " * 5000)
    assert len(big.encode("utf-8")) > 80_000
    truncated = enrich.truncate_transcript(big, max_bytes=80_000)
    assert "first-segment" in truncated
    assert "last-segment" in truncated
    assert "MIDDLE_SHOULD_BE_DROPPED" not in truncated
    assert "transcript truncated" in truncated.lower()


def test_truncate_short_transcript_unchanged():
    small = "short transcript content."
    assert enrich.truncate_transcript(small, max_bytes=80_000) == small
