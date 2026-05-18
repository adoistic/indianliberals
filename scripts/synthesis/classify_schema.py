#!/usr/bin/env python3
"""
Validation functions for the per-piece classification record emitted by
the classification subagents (see system-classify.txt).

Mirrors apps/site/src/content.config.ts:classificationFields and the per-
collection kind enums. Returns (sanitized_dict, list_of_warnings). Never
raises on per-field problems — out-of-vocab themes/places are MOVED, not
rejected; only structural errors (wrong type, missing required key) are
rejected.

Run tests:
    .venv-extract/bin/python3 scripts/synthesis/classify_schema.py --test
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
PLACES_VOCAB_PATH = ROOT / "data/places-vocab.json"
THEMES_VOCAB_PATH = ROOT / "data/themes-vocab.json"

STANCE_ENUM = {"argues-for", "argues-against", "analyzes", "profiles", "commemorates"}
SCALE_ENUM = {"national", "regional", "bi-regional", "international-comparison"}
PERIOD_ENUM = {"pre-independence", "nehruvian-era", "late-license-raj", "reform-era", "post-reform"}
KIND_OPINIONS = {"profile", "commentary", "review", "obituary", "event-coverage", "editorial"}
KIND_MUSINGS = {"book-excerpt", "pamphlet-excerpt", "speech-excerpt", "lecture", "periodical-article", "letter"}

_SLUG_RX = re.compile(r"^[a-z][a-z0-9-]*$")


def load_places_vocab() -> tuple[set[str], dict[str, list[str]]]:
    doc = json.loads(PLACES_VOCAB_PATH.read_text())
    canonical: set[str] = set()
    canonical.update(doc["states_and_uts"])
    canonical.update(doc["historical_units"])
    canonical.update(doc["countries"])
    aliases = doc["regional_aliases"]
    return canonical, aliases


def load_themes_vocab() -> set[str]:
    if not THEMES_VOCAB_PATH.exists():
        return set()
    doc = json.loads(THEMES_VOCAB_PATH.read_text())
    if isinstance(doc, list):
        return set(doc)
    return set(doc.get("themes", []))


def kebab(s: str) -> str:
    """Lowercase + normalize whitespace/underscores to single hyphens."""
    s = s.strip().lower().replace("_", "-")
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s


def validate_record(
    rec: dict,
    collection: str,
    themes_vocab: set[str],
    places_canonical: set[str],
    places_aliases: dict[str, list[str]],
) -> tuple[Optional[dict], list[str]]:
    """Validate one classification record. Returns (sanitized, warnings).

    Returns (None, [...]) on hard structural errors. Soft errors (out-of-
    vocab themes/places, stance/scale unset) yield warnings but a usable
    record is returned with those values redirected/dropped per the spec.

    The `id` field is required. The rest are optional under the empty-
    when-uncertain rule.
    """
    warnings: list[str] = []
    if not isinstance(rec, dict):
        return None, [f"record is not a dict: {type(rec).__name__}"]
    rid = rec.get("id")
    if not isinstance(rid, str) or not rid:
        return None, ["missing or non-string `id`"]

    out: dict = {"id": rid}

    # themes / proposed_themes
    in_themes = rec.get("themes") or []
    in_proposed = rec.get("proposed_themes") or []
    if not isinstance(in_themes, list) or not isinstance(in_proposed, list):
        return None, [f"[{rid}] themes/proposed_themes must be lists"]
    accepted = []
    moved = list(in_proposed)
    for t in in_themes:
        if not isinstance(t, str):
            warnings.append(f"[{rid}] non-string theme dropped: {t!r}")
            continue
        slug = kebab(t)
        if not _SLUG_RX.match(slug):
            warnings.append(f"[{rid}] theme malformed, dropped: {t!r}")
            continue
        if slug in themes_vocab:
            accepted.append(slug)
        else:
            moved.append(slug)
            warnings.append(f"[{rid}] theme '{slug}' not in vocab → proposed_themes")
    out["themes"] = sorted(set(accepted))
    out["proposed_themes"] = sorted(set(moved))

    # key_concepts: kebab, max 5
    in_kc = rec.get("key_concepts") or []
    if not isinstance(in_kc, list):
        return None, [f"[{rid}] key_concepts must be a list"]
    kc_clean = []
    for c in in_kc:
        if not isinstance(c, str):
            continue
        s = kebab(c)
        if _SLUG_RX.match(s):
            kc_clean.append(s)
    out["key_concepts"] = list(dict.fromkeys(kc_clean))[:5]

    # pull_quote: just length-checked here; verbatim-check is in apply step
    pq = rec.get("pull_quote")
    if pq is not None and isinstance(pq, str):
        if 50 <= len(pq) <= 250:
            out["pull_quote"] = pq
        else:
            warnings.append(f"[{rid}] pull_quote length {len(pq)} out of 50..250 — dropped")

    # stance
    st = rec.get("stance")
    if st in STANCE_ENUM:
        out["stance"] = st
    elif st is not None:
        warnings.append(f"[{rid}] stance '{st}' not in enum — left unset")

    # kind
    kn = rec.get("kind")
    valid_kinds = KIND_OPINIONS if collection == "opinions" else KIND_MUSINGS
    if kn in valid_kinds:
        out["kind"] = kn
    elif kn is not None:
        warnings.append(f"[{rid}] kind '{kn}' not in {collection} enum — left unset")

    # geographic_scope
    gs = rec.get("geographic_scope")
    if isinstance(gs, dict):
        scope_out: dict = {}
        scale = gs.get("scale")
        if scale in SCALE_ENUM:
            scope_out["scale"] = scale
        elif scale is not None:
            warnings.append(f"[{rid}] scale '{scale}' not in enum — left unset")
        # places: expand aliases, then validate against canonical vocab
        raw_places = gs.get("places") or []
        if isinstance(raw_places, list):
            expanded: list[str] = []
            for p in raw_places:
                if not isinstance(p, str):
                    continue
                slug = kebab(p)
                if slug in places_aliases:
                    expanded.extend(places_aliases[slug])
                else:
                    expanded.append(slug)
            cleaned = []
            for p in expanded:
                if p in places_canonical:
                    cleaned.append(p)
                else:
                    warnings.append(f"[{rid}] place '{p}' not in vocab — dropped")
            scope_out["places"] = sorted(set(cleaned))
        if scope_out:
            out["geographic_scope"] = scope_out

    # source_year_inferred (musings only) — transient, used by applier
    syi = rec.get("source_year_inferred")
    if isinstance(syi, int) and 1800 <= syi <= 2026:
        out["source_year_inferred"] = syi

    return out, warnings


# ─── Built-in tests ────────────────────────────────────────────────────

def _run_tests():
    themes_vocab = {"economic-policy", "free-enterprise", "democracy"}
    places_canonical = {"maharashtra", "tamil-nadu", "uttar-pradesh", "haryana", "united-states"}
    aliases = {"awadh": ["uttar-pradesh"], "west-up-and-haryana": ["uttar-pradesh", "haryana"]}

    # Happy path
    rec = {
        "id": "test-1",
        "themes": ["democracy", "free-enterprise"],
        "proposed_themes": [],
        "key_concepts": ["License-Raj", "swadeshi"],
        "pull_quote": "a" * 60,
        "stance": "analyzes",
        "kind": "profile",
        "geographic_scope": {"scale": "national", "places": ["awadh", "maharashtra"]},
        "source_year_inferred": 1995,
    }
    out, warns = validate_record(rec, "opinions", themes_vocab, places_canonical, aliases)
    assert out is not None, "happy path should return record"
    assert out["themes"] == ["democracy", "free-enterprise"], out["themes"]
    assert out["proposed_themes"] == [], out["proposed_themes"]
    assert out["key_concepts"] == ["license-raj", "swadeshi"], out["key_concepts"]
    assert out["pull_quote"] == "a" * 60
    assert out["stance"] == "analyzes"
    assert out["kind"] == "profile"
    assert out["geographic_scope"]["scale"] == "national"
    assert out["geographic_scope"]["places"] == ["maharashtra", "uttar-pradesh"], out["geographic_scope"]["places"]
    assert out["source_year_inferred"] == 1995

    # Out-of-vocab theme → proposed_themes
    rec2 = {"id": "test-2", "themes": ["zoning"], "proposed_themes": []}
    out2, warns2 = validate_record(rec2, "musings", themes_vocab, places_canonical, aliases)
    assert out2 is not None
    assert out2["themes"] == []
    assert out2["proposed_themes"] == ["zoning"]
    assert any("not in vocab" in w for w in warns2)

    # Bad kind for opinions
    rec3 = {"id": "test-3", "kind": "book-excerpt"}
    out3, warns3 = validate_record(rec3, "opinions", themes_vocab, places_canonical, aliases)
    assert out3 is not None
    assert "kind" not in out3
    assert any("not in opinions enum" in w for w in warns3)

    # Pull-quote too short
    rec4 = {"id": "test-4", "pull_quote": "short"}
    out4, warns4 = validate_record(rec4, "musings", themes_vocab, places_canonical, aliases)
    assert out4 is not None
    assert "pull_quote" not in out4
    assert any("out of 50..250" in w for w in warns4)

    # Missing id
    rec5 = {"themes": []}
    out5, warns5 = validate_record(rec5, "musings", themes_vocab, places_canonical, aliases)
    assert out5 is None
    assert any("missing or non-string `id`" in w for w in warns5)

    # Place alias expansion + canonical-vocab filtering
    rec6 = {"id": "test-6", "geographic_scope": {"scale": "regional", "places": ["west-up-and-haryana"]}}
    out6, _ = validate_record(rec6, "musings", themes_vocab, places_canonical, aliases)
    assert out6["geographic_scope"]["places"] == ["haryana", "uttar-pradesh"]

    print("all classify_schema tests passed.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_tests()
    else:
        print("usage: classify_schema.py --test", file=sys.stderr)
        sys.exit(2)
