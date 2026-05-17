"""
Consume thinkers.raw.json and produce the canonical authority-file seed at
data/authority/thinkers.json + byline lookup.

Confidence tiers:
  canonical = multi-source verified (proposal+WP DB+content) OR proposal-only OR wp_author-only
  high      = single-source content byline (extracted from existing content entries)
  medium    = single-source filename derivation

Phase 0.2 byline sweep + Phase 0.3 Opus clustering will refine. This is the
hand-curated v1 seed.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTHORITY = REPO / "data/authority"


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def normalize_byline(s: str) -> str:
    """Match-key for byline lookup. Case + punctuation insensitive."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[\.\,]", "", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def classify_confidence(sources: list[str]) -> str:
    if len(sources) >= 2:
        return "canonical"
    src = sources[0]
    if src in {"proposal", "wp_author"} or src == "thinkers_collection":
        return "canonical"
    if src.startswith("content/"):
        return "high"
    if src.startswith("pdf-filename"):
        return "medium"
    return "low"


def main() -> None:
    raw_path = AUTHORITY / "thinkers.raw.json"
    raw = json.load(raw_path.open(encoding="utf-8"))

    thinkers: list[dict] = []
    byline_lookup: dict[str, str] = {}
    used_ids: set[str] = set()

    for entry in raw["thinkers"]:
        canonical = entry["canonical"]
        # Assign an ID. Prefer existing thinker-collection slug if available.
        if entry.get("existing_id"):
            tid = entry["existing_id"]
        else:
            tid = slugify(canonical)
        # Ensure uniqueness
        base = tid
        counter = 2
        while tid in used_ids:
            tid = f"{base}-{counter}"
            counter += 1
        used_ids.add(tid)

        # Build aliases. Start with the seeded `also_known_as` if any.
        aliases = list(entry.get("also_known_as", []) or [])
        # Always include the canonical form as an alias (case-insensitive lookup)
        if canonical not in aliases:
            aliases.insert(0, canonical)

        confidence = classify_confidence(entry["sources"])

        out_entry = {
            "id": tid,
            "name": {
                "canonical": canonical,
                "full": entry.get("full"),
                "sort": entry.get("sort") or canonical_sort(canonical),
                "also_known_as": [a for a in aliases if a != canonical],
                "honorifics": entry.get("honorifics", []),
            },
            "birth_year": entry.get("birth_year"),
            "death_year": entry.get("death_year"),
            "tradition": entry.get("tradition"),
            "brief_bio": entry.get("brief_bio"),
            "image_filename_hint": entry.get("image_filename"),
            "confidence": confidence,
            "sources": entry["sources"],
        }
        # Strip nulls for cleanliness
        out_entry = {k: v for k, v in out_entry.items() if v not in (None, [], "")}
        # Strip nulls in name sub-object too
        out_entry["name"] = {k: v for k, v in out_entry["name"].items() if v not in (None, [], "")}
        thinkers.append(out_entry)

        # Add to byline lookup
        for alias in [canonical] + aliases:
            byline_lookup[normalize_byline(alias)] = tid

    # Sort by confidence then by canonical name
    confidence_order = {"canonical": 0, "high": 1, "medium": 2, "low": 3}
    thinkers.sort(key=lambda t: (confidence_order.get(t["confidence"], 9), t["name"]["canonical"]))

    counts = {
        "total": len(thinkers),
        "canonical": sum(1 for t in thinkers if t["confidence"] == "canonical"),
        "high": sum(1 for t in thinkers if t["confidence"] == "high"),
        "medium": sum(1 for t in thinkers if t["confidence"] == "medium"),
    }

    final = {
        "_meta": {
            "version": "v1-seed-2026-05-17",
            "purpose": (
                "Authority file seed for thinker resolution. Phase 0.2 byline sweep + "
                "Phase 0.3 Opus clustering refine this. Metadata extraction prompts "
                "resolve bylines against the byline_lookup map. Entries with "
                "confidence: canonical are trusted; medium-confidence entries are "
                "candidate names that need cluster-collapse (e.g., 'MR Masani' will "
                "collapse into 'minoo-masani' after Phase 0.3)."
            ),
            "counts": counts,
            "schema_note": "Each entry follows the thinkerName shape from apps/site/src/content.config.ts.",
        },
        "thinkers": thinkers,
        "byline_lookup": byline_lookup,
    }

    out_file = AUTHORITY / "thinkers.json"
    out_file.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_file.relative_to(REPO)}")
    print(f"  Total thinkers: {counts['total']}")
    print(f"    canonical:  {counts['canonical']}")
    print(f"    high:       {counts['high']}")
    print(f"    medium:     {counts['medium']}")
    print(f"  Byline lookup keys: {len(byline_lookup)}")


def canonical_sort(name: str) -> str:
    """Derive a 'Surname, Given' sort form from 'Given Surname'."""
    parts = name.split()
    if len(parts) < 2:
        return name
    # Heuristic: last token is surname unless it's a suffix
    suffix = {"Jr.", "Sr.", "II", "III", "PhD", "MD"}
    last_idx = len(parts) - 1
    while last_idx > 0 and parts[last_idx] in suffix:
        last_idx -= 1
    surname = parts[last_idx]
    given = " ".join(parts[:last_idx])
    if last_idx < len(parts) - 1:
        given = given + " " + " ".join(parts[last_idx + 1:])
    return f"{surname}, {given}"


if __name__ == "__main__":
    main()
