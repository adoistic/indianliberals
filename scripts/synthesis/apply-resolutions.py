#!/usr/bin/env python3
"""
Apply `data/synthesis/resolutions.jsonl` to the live archive.

Reads one JSON resolution per line (output of the cross-link resolver,
either the manual chat session OR `resolve-unlinked.py` headless driver),
validates it, and applies the four mutations:

  1. Stub thinker creation
     - For action="create_stub": writes a new minimal MD to
       `apps/site/src/content/thinkers/<slug>.md`, appends the entry
       to `data/authority/thinkers.json`, and adds normalised
       byline_lookup keys.

  2. byline_lookup expansion
     - For action="match": adds the entry's byline / title hint as a
       new alias pointing to the matched thinker, so future emissions
       resolve consistently.

  3. Frontmatter ref backfill
     - For action="match" or "create_stub": writes the structured
       reference (`author:`, `subject:`, or `authors:`) into the
       entry's frontmatter. Idempotent — entries with existing refs
       are not overwritten.

  4. Residual logging
     - For action="skip": appends a one-line note to
       `data/synthesis/audit-residual.txt` for editorial review.

After this step, run:

    python3 scripts/synthesis/emit-astro-md.py            # re-emit primary-works
    cd apps/site && npm run build                         # verify references

This script is idempotent — running it twice is a no-op on the second
pass (every mutation guards against existing state).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
THINKERS_DIR = CONTENT_ROOT / "thinkers"
RESOLUTIONS = ROOT / "data/synthesis/resolutions.jsonl"
AUTHORITY = ROOT / "data/authority/thinkers.json"
RESIDUAL_LOG = ROOT / "data/synthesis/audit-residual.txt"


VALID_TRADITIONS = {
    "classical_liberal", "reformer", "nationalist_liberal",
    "social_reformer", "contemporary_liberal", "international_influence",
}

# Per-collection ref-field mapping. For each (collection, role) tuple, the
# corresponding entry frontmatter field is the structured reference.
REF_FIELD = {
    ("musings",         "author"):  "author",
    ("opinions",        "author"):  "author",
    ("opinions",        "subject"): "subject",
    ("interviews",      "author"):  "subject",   # interviews never have a writer; subject is the canonical signal
    ("interviews",      "subject"): "subject",
    ("theprint-mirror", "author"):  None,  # theprint uses related_thinkers; populated by resolve-bylines.py
    ("primary-works",   "author"):  None,  # primary-works refs go into authors[] via emit-astro-md.py
}


def normalise_byline(s: str) -> str:
    s = s.lower().replace(".", " ").replace(",", " ").replace("-", " ").replace("'", "").replace("’", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def slug_safe(s: str) -> str:
    """Sanity-check a proposed stub slug — lowercase ASCII, hyphens, no
    punctuation. Returns the cleaned slug."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def load_authority() -> dict:
    return json.loads(AUTHORITY.read_text())


def save_authority(doc: dict):
    AUTHORITY.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create_stub_thinker(slug: str, new_thinker: dict, doc: dict, *, source_marker: str) -> bool:
    """Write the stub MD + append to authority. Returns True if created,
    False if a thinker with the same id already exists (caller should
    treat the resolution as 'match' instead)."""
    if any(t["id"] == slug for t in doc.get("thinkers", [])):
        return False

    canonical = new_thinker.get("canonical", "").strip()
    if not canonical:
        return False
    sort = new_thinker.get("sort") or canonical
    tradition = new_thinker.get("tradition", "contemporary_liberal")
    if tradition not in VALID_TRADITIONS:
        tradition = "contemporary_liberal"
    birth_year = new_thinker.get("birth_year")
    death_year = new_thinker.get("death_year")

    # Authority record
    rec = {
        "id": slug,
        "name": {
            "canonical": canonical,
            "sort": sort,
            "also_known_as": [],
        },
        "tradition": tradition,
        "nationality": "india",
        "themes": [],
        "affiliations": [],
        "bio_source": "ai_drafted_stub",
        "needs_review": True,
    }
    if birth_year: rec["birth_year"] = birth_year
    if death_year: rec["death_year"] = death_year
    doc.setdefault("thinkers", []).append(rec)

    # MD file
    fm_lines = [
        "---",
        f'id: {slug}',
        "name:",
        f'  canonical: "{canonical}"',
        f'  sort: "{sort}"',
        f"  also_known_as: []",
        f"tradition: {tradition}",
        f"nationality: india",
        f"themes: []",
        f"affiliations: []",
    ]
    if birth_year: fm_lines.append(f"birth_year: {birth_year}")
    if death_year: fm_lines.append(f"death_year: {death_year}")
    fm_lines.extend([
        'bio_source: ai_drafted_stub',
        'needs_review: true',
        'draft: false',
        "ai:",
        f'  drafted_by: "{source_marker}"',
        f'  drafted_at: "2026-05-18"',
        f'  model_version: "cross-link-audit-phase-a"',
        "---",
        "",
        f"# {canonical}",
        "",
        "*Entry created during the Phase A cross-link audit. The full bio is queued for a Phase 1.5 AI-drafted pass.*",
        "",
        "This thinker appeared as an author or subject in the corpus. Until a real bio lands, see the works and pieces linked below.",
        "",
    ])
    md_path = THINKERS_DIR / f"{slug}.md"
    md_path.write_text("\n".join(fm_lines), encoding="utf-8")

    # byline_lookup seed
    bl = doc.setdefault("byline_lookup", {})
    bl[normalise_byline(canonical)] = slug
    return True


def apply_byline_lookup_alias(slug: str, byline_text: str, doc: dict) -> bool:
    """Add `normalise_byline(byline_text) -> slug` to the authority lookup
    if not already present. Returns True if added."""
    if not byline_text:
        return False
    bl = doc.setdefault("byline_lookup", {})
    key = normalise_byline(byline_text)
    if not key or key in bl:
        return False
    bl[key] = slug
    return True


def set_frontmatter_field(path: Path, field: str, value: str) -> bool:
    """Write `field: "<value>"` into the frontmatter of an MD file.
    Idempotent: refuses to overwrite an existing non-empty value of
    the same field. Returns True if the file was modified."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return False
    fm = m.group(1)
    line_rx = re.compile(rf"^{re.escape(field)}:\s*(.*)$", re.M)
    new_line = f'{field}: "{value}"'
    existing = line_rx.search(fm)
    if existing:
        ev = existing.group(1).strip()
        if ev and ev not in ('""', "''", "null", "[]"):
            return False  # already populated; idempotent skip
        new_fm = line_rx.sub(new_line, fm)
    else:
        new_fm = fm + "\n" + new_line
    out = text[: m.start()] + "---\n" + new_fm + "\n---" + text[m.end():]
    path.write_text(out, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source-marker",
        default="interactive-claude-session",
        help="ai.drafted_by value on new stub thinkers",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not RESOLUTIONS.exists():
        print(f"ERROR: {RESOLUTIONS} missing — generate it via the resolver first")
        return 1

    doc = load_authority()
    existing_ids = {t["id"] for t in doc.get("thinkers", [])}

    counts = {
        "match": 0, "create_stub": 0, "skip": 0,
        "collisions_downgraded": 0,
        "fm_written": 0, "fm_skipped_existing": 0,
        "byline_aliased": 0, "errors": 0,
    }
    residual_lines: list[str] = []

    with RESOLUTIONS.open(encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                r = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"[parse:{line_no}] {e}")
                counts["errors"] += 1
                continue

            action = r.get("action")
            collection = r.get("collection")
            entry_id = r.get("id")
            role = r.get("primary_role")
            slug = r.get("primary_thinker_id")
            entry_path = CONTENT_ROOT / collection / f"{entry_id}.md"

            if action == "skip":
                counts["skip"] += 1
                residual_lines.append(
                    f"{collection}\t{entry_id}\t{r.get('reason', 'unspecified')}\t{r.get('confidence', 'unknown')}"
                )
                continue

            if action == "create_stub":
                stub = r.get("new_thinker") or {}
                # Sanity-check the slug
                slug = slug_safe(slug or "")
                if not slug or not stub.get("canonical"):
                    counts["errors"] += 1
                    residual_lines.append(f"{collection}\t{entry_id}\tinvalid_stub_payload\tlow")
                    continue
                if slug in existing_ids:
                    counts["collisions_downgraded"] += 1
                    action = "match"  # fall through
                else:
                    if not args.dry_run:
                        create_stub_thinker(slug, stub, doc, source_marker=args.source_marker)
                    existing_ids.add(slug)
                    counts["create_stub"] += 1

            if action == "match":
                if slug not in existing_ids:
                    counts["errors"] += 1
                    residual_lines.append(f"{collection}\t{entry_id}\tmatch_to_unknown_thinker:{slug}\tlow")
                    continue
                counts["match"] += 1
                # Add byline alias from the entry's hint/title for future resolutions
                byline_text = r.get("byline_alias") or ""
                if byline_text and not args.dry_run:
                    if apply_byline_lookup_alias(slug, byline_text, doc):
                        counts["byline_aliased"] += 1

            # Write the structured ref into the entry's frontmatter
            field = REF_FIELD.get((collection, role))
            if field is None:
                # primary-works + theprint-mirror handle authors via separate emit paths
                continue
            if args.dry_run:
                counts["fm_written"] += 1
                continue
            if set_frontmatter_field(entry_path, field, slug):
                counts["fm_written"] += 1
            else:
                counts["fm_skipped_existing"] += 1

    if not args.dry_run:
        save_authority(doc)
        if residual_lines:
            RESIDUAL_LOG.write_text("\n".join(residual_lines) + "\n", encoding="utf-8")
            counts["residual_log"] = str(RESIDUAL_LOG.relative_to(ROOT))

    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
