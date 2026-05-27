#!/usr/bin/env python3
"""Resolve every `thinker_unresolved` entry to a real thinker slug.

For each primary-works MD:
  - For each `thinker_mentions[]` entry with `thinker_unresolved` (and no
    `thinker`), try to match the literal name against an existing thinker's
    canonical name or `also_known_as`. If matched, replace `thinker_unresolved`
    with `thinker: <existing-slug>`.
  - Else, create a stub thinker MD at `apps/site/src/content/thinkers/<new-slug>.md`
    (matching the existing `ai_drafted_stub` convention), then replace
    `thinker_unresolved` with `thinker: <new-slug>`.
  - Same logic for `contributors[]` entries with `thinker_unresolved`.

Matching is intentionally permissive: strips honorifics ("Prof.", "Dr.", "Sir",
"Smt.", "Shri", "Mr.", "Mrs."), collapses whitespace, and compares
case-insensitively. False-positive risk is low because we only match against
the existing 480 thinkers' canonical + AKA strings, not against the entire
corpus.

After this script, no primary-works MD should have any `thinker_unresolved` field.

Run:
    .venv-extract/bin/python3 scripts/synthesis/resolve-all-thinker-mentions.py
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
THINKERS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "thinkers"

_FM_RX = re.compile(r"^---\n([\s\S]*?)\n---\n?([\s\S]*)$", re.M)
_HONORIFIC_RX = re.compile(
    r"^(?:prof\.?|dr\.?|sir|mr\.?|mrs\.?|ms\.?|smt\.?|shri|the hon\.?|lord|justice)\s+",
    re.I,
)
_NON_SLUG_RX = re.compile(r"[^a-z0-9]+")


def normalize_for_match(name: str) -> str:
    """Lowercased, honorific-stripped, whitespace-collapsed form for matching."""
    s = name.strip()
    # Strip leading honorifics (possibly multiple, e.g. "The Hon. Sir ...")
    for _ in range(3):
        new = _HONORIFIC_RX.sub("", s).strip()
        if new == s:
            break
        s = new
    # Collapse internal whitespace, lowercase.
    s = re.sub(r"\s+", " ", s).lower()
    # Drop trailing periods on initials (P. T. → P T)
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def slugify(name: str, *, max_len: int = 60) -> str:
    """Produce a Kebab-case slug for a new thinker MD."""
    s = name.strip()
    # Strip honorifics for the slug too
    for _ in range(3):
        new = _HONORIFIC_RX.sub("", s).strip()
        if new == s:
            break
        s = new
    s = s.lower()
    s = _NON_SLUG_RX.sub("-", s).strip("-")
    s = re.sub(r"-+", "-", s)
    return s[:max_len]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FM_RX.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), m.group(2)


def build_match_index(thinkers_dir: Path) -> tuple[dict[str, str], set[str]]:
    """Return (normalized_name → slug, set_of_existing_slugs).

    Each thinker contributes its canonical name and every also_known_as.
    """
    idx: dict[str, str] = {}
    slugs: set[str] = set()
    for md in sorted(thinkers_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        slug = fm.get("id") or md.stem
        slugs.add(slug)
        name_block = fm.get("name") or {}
        canonical = (name_block.get("canonical") or "").strip()
        also = name_block.get("also_known_as") or []
        if not isinstance(also, list):
            also = []
        candidates = [canonical] + [a for a in also if isinstance(a, str)]
        for c in candidates:
            if not c.strip():
                continue
            norm = normalize_for_match(c)
            if norm:
                # First write wins (canonical preferred over AKAs because canonical iterates first).
                idx.setdefault(norm, slug)
    return idx, slugs


def write_stub_thinker(slug: str, original_name: str, thinkers_dir: Path) -> None:
    """Create a minimal stub thinker MD."""
    canonical = original_name.strip()
    # Build a sort form: last name first if it looks like Western "First Last", else as-is.
    parts = re.split(r"\s+", canonical)
    if len(parts) >= 2 and not any("." in p for p in parts):
        sort_form = f"{parts[-1]}, {' '.join(parts[:-1])}"
    else:
        sort_form = canonical
    body_fm = {
        "id": slug,
        "name": {
            "canonical": canonical,
            "sort": sort_form,
            "also_known_as": [],
        },
        "tradition": "unclassified",
        "canon_status": "unclassified",
        "vocations": [],
        "nationality": "india",
        "themes": [],
        "affiliations": [],
        "bio_source": "ai_drafted_stub",
        "needs_review": True,
        "draft": False,
        "ai": {
            "drafted_by": "resolve-all-thinker-mentions",
            "drafted_at": date.today().isoformat(),
            "model_version": "resolve-all-v1",
        },
    }
    fm_yaml = yaml.safe_dump(body_fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    path = thinkers_dir / f"{slug}.md"
    path.write_text(
        f"---\n{fm_yaml.rstrip()}\n---\n\n"
        f"_Auto-created stub for `{canonical}` — surfaced by an interview or work that mentioned "
        f"this figure. Editorial review pending._\n",
        encoding="utf-8",
    )


def resolve_one_unresolved(
    name: str,
    *,
    match_index: dict[str, str],
    existing_slugs: set[str],
    created_stubs: dict[str, str],
) -> str:
    """Return the resolved slug for a literal unresolved name. Side-effect: may create a stub."""
    norm = normalize_for_match(name)
    # Try exact match against known canonical/AKA names
    if norm in match_index:
        return match_index[norm]
    # Try the slug we'd generate — if a thinker with that slug already exists, use it
    candidate = slugify(name)
    if not candidate:
        # Fall back to a generic slug if name is nothing but punctuation
        candidate = "unnamed-figure"
    if candidate in existing_slugs:
        # Slug collision = same person under a slightly different rendering
        match_index[norm] = candidate  # cache for future calls
        return candidate
    if candidate in created_stubs:
        match_index[norm] = candidate
        return candidate
    # Create a fresh stub
    write_stub_thinker(candidate, name, THINKERS_DIR)
    created_stubs[candidate] = name
    existing_slugs.add(candidate)
    match_index[norm] = candidate
    return candidate


def resolve_md_inplace(
    md_path: Path,
    *,
    match_index: dict[str, str],
    existing_slugs: set[str],
    created_stubs: dict[str, str],
) -> tuple[int, int]:
    """Walk a single MD's frontmatter; resolve every thinker_unresolved.

    Returns (mentions_resolved, contributors_resolved).
    """
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if not fm:
        return 0, 0
    mutated = False
    mentions_resolved = 0
    contributors_resolved = 0

    # thinker_mentions[]
    for tm in fm.get("thinker_mentions") or []:
        if not isinstance(tm, dict):
            continue
        unresolved = tm.get("thinker_unresolved")
        if isinstance(unresolved, str) and unresolved.strip() and not tm.get("thinker"):
            slug = resolve_one_unresolved(
                unresolved,
                match_index=match_index,
                existing_slugs=existing_slugs,
                created_stubs=created_stubs,
            )
            tm["thinker"] = slug
            tm.pop("thinker_unresolved", None)
            mutated = True
            mentions_resolved += 1

    # contributors[]
    for c in fm.get("contributors") or []:
        if not isinstance(c, dict):
            continue
        unresolved = c.get("thinker_unresolved")
        if isinstance(unresolved, str) and unresolved.strip() and not c.get("thinker"):
            slug = resolve_one_unresolved(
                unresolved,
                match_index=match_index,
                existing_slugs=existing_slugs,
                created_stubs=created_stubs,
            )
            c["thinker"] = slug
            c.pop("thinker_unresolved", None)
            mutated = True
            contributors_resolved += 1

    # Recompute related_thinkers as union of authors[] + thinker_mentions[].thinker
    if mutated:
        related = set()
        for a in fm.get("authors") or []:
            if isinstance(a, str):
                related.add(a)
        for tm in fm.get("thinker_mentions") or []:
            if isinstance(tm, dict):
                s = tm.get("thinker")
                if isinstance(s, str):
                    related.add(s)
        fm["related_thinkers"] = sorted(related)
        fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
        md_path.write_text(f"---\n{fm_yaml.rstrip()}\n---\n\n{body.lstrip()}", encoding="utf-8")

    return mentions_resolved, contributors_resolved


def main() -> int:
    match_index, existing_slugs = build_match_index(THINKERS_DIR)
    print(f"Authority manifest: {len(existing_slugs)} thinkers, "
          f"{len(match_index)} normalized name forms.")

    created_stubs: dict[str, str] = {}
    total_mentions = 0
    total_contribs = 0
    mds_touched = 0

    for md in sorted(PW_DIR.glob("*.md")):
        m, c = resolve_md_inplace(
            md,
            match_index=match_index,
            existing_slugs=existing_slugs,
            created_stubs=created_stubs,
        )
        if m or c:
            mds_touched += 1
            total_mentions += m
            total_contribs += c

    print()
    print(f"MDs touched:           {mds_touched}")
    print(f"thinker_mentions[] resolved: {total_mentions}")
    print(f"contributors[]    resolved: {total_contribs}")
    print(f"New stub thinkers created:  {len(created_stubs)}")
    if created_stubs:
        print()
        print("First 20 stub names:")
        for slug, name in sorted(created_stubs.items())[:20]:
            print(f"  {slug:<40}  ← {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
