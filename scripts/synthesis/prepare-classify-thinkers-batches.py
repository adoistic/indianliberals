#!/usr/bin/env python3
"""
Prepare input batches for the thinkers AI-bulk-classifier pipeline.

Modes:
  (default)    Round-robin all 506 thinker MDs into 10 batches at
               data/classify-thinkers/batch-{00..09}.jsonl.
  --pilot      Read data/classify-thinkers/pilot-ground-truth.json,
               assemble a single batch at pilot-batch.jsonl containing
               only those 30 thinkers (used for the pilot dispatch).

Input record shape per spec §5:
  { id, name: {canonical, sort, also_known_as}, birth_year, death_year,
    nationality, current_fields: {tradition, canon_status, vocations,
    themes, affiliations, bio_source}, bio_excerpt (≤3000 chars),
    works_authored: [{id, title, year, work_type}, ...] (≤20),
    mention_contexts: [{source, excerpt (~150-250 chars), role}, ...] (≤10) }

Run from repo root:
    python3 scripts/synthesis/prepare-classify-thinkers-batches.py
    python3 scripts/synthesis/prepare-classify-thinkers-batches.py --pilot

Refs docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md §5
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
PRIMARY_WORKS_DIR = CONTENT_ROOT / "primary-works"
DATA_DIR = ROOT / "data/classify-thinkers"
GROUND_TRUTH = DATA_DIR / "pilot-ground-truth.json"

# Collections to scan for mention_contexts. Periodicals is currently empty on
# disk but listed for completeness — if any periodical MDs land later they'll
# be picked up automatically.
MENTION_COLLECTIONS = ("primary-works", "opinions", "musings", "theprint-mirror", "periodicals")

N_BATCHES = 10
MAX_BODY_CHARS = 3000
MAX_WORKS_AUTHORED = 20
MAX_MENTION_CONTEXTS = 10
MENTION_EXCERPT_CHARS = 250

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)

# Bare-string list item: e.g. "  - some-slug"
_BARE_REF_RX = re.compile(r"^\s*-\s*([a-z0-9][a-z0-9-]*)\s*$")
# Flow-style object item: e.g. "  - { collection: organisations, id: pucl-gujarat }"
_FLOW_OBJ_RX = re.compile(
    r"^\s*-\s*\{[^}]*?id:\s*([a-z0-9][a-z0-9-]*)[^}]*\}\s*$"
)
_FLOW_COLLECTION_RX = re.compile(r"collection:\s*([a-z_-]+)")
# Block-style object item start: "  - collection: thinkers"
_BLOCK_OBJ_START_RX = re.compile(r"^\s*-\s*collection:\s*(\S+)\s*$")
# Block-style object item id-line: "    id: some-slug"
_BLOCK_OBJ_ID_RX = re.compile(r"^\s*id:\s*([a-z0-9][a-z0-9-]*)\s*$")

# thinker_mentions entry: "  - thinker: <slug>" (inline form)
_TM_INLINE_RX = re.compile(r"^\s*-\s*thinker:\s*([a-z0-9][a-z0-9-]*)\s*$")
# thinker_mentions entry block-style id-line: "    thinker: <slug>"
_TM_ID_LINE_RX = re.compile(r"^\s*thinker:\s*([a-z0-9][a-z0-9-]*)\s*$")
# contributors entry: "  - thinker: <slug>" (inline)
_CONTRIB_INLINE_RX = _TM_INLINE_RX

# Top-level scalar key match — used to detect when a block ends.
_TOP_LEVEL_KEY_RX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:\s")

# Frontmatter helpers
_NAME_CANONICAL_RX = re.compile(r'^  canonical:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)
_NAME_SORT_RX = re.compile(r'^  sort:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)
_BIRTH_YEAR_RX = re.compile(r"^birth_year:\s*(-?\d+)\s*$", re.MULTILINE)
_DEATH_YEAR_RX = re.compile(r"^death_year:\s*(-?\d+)\s*$", re.MULTILINE)
_NATIONALITY_RX = re.compile(r"^nationality:\s*([a-z_]+)\s*$", re.MULTILINE)
_TRADITION_RX = re.compile(r"^tradition:\s*([a-z_]+)\s*$", re.MULTILINE)
_CANON_STATUS_RX = re.compile(r"^canon_status:\s*([a-z_]+)\s*$", re.MULTILINE)
_BIO_SOURCE_RX = re.compile(r"^bio_source:\s*([a-z_]+)\s*$", re.MULTILINE)
# Title (primary-works): nested "title:\n  main: ..." OR scalar 'title: "..."'
_PW_TITLE_MAIN_RX = re.compile(r'^  main:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)
_PW_TITLE_SCALAR_RX = re.compile(r'^title:\s*"([^"\n]+)"\s*$', re.MULTILINE)
_PW_WORK_TYPE_RX = re.compile(r'^work_type:\s*"?([a-z_]+)"?\s*$', re.MULTILINE)
_PW_PUB_YEAR_RX = re.compile(r"^[ \t]+year:\s*(\d{4})", re.MULTILINE)


def parse_frontmatter(text: str) -> tuple[dict, str] | None:
    """Return ({field: raw_str_value}, body) or None if no frontmatter.

    Top-level scalar fields only; the caller does any further parsing.
    """
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm_text, body = m.group(1), m.group(2)
    fields: dict[str, str] = {}
    for line in fm_text.split("\n"):
        if line and not line.startswith(" ") and not line.startswith("\t") and ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    return fields, body


def _read_list_block_collect_refs(
    lines: list[str],
    start_idx: int,
    *,
    accept_obj_collection: tuple[str, ...] | None = None,
    field: str = "list",
) -> tuple[list[str], int]:
    """Read an indented YAML list following a top-level key. Return collected
    slug refs and the index of the first line that is NOT inside the block.

    Accepts bare-string, flow-object, and block-object refs. For object refs,
    if `accept_obj_collection` is provided, only items with collection in that
    tuple (or no explicit collection at all) are collected. Bare-string refs
    default to "thinkers".
    """
    refs: list[str] = []
    i = start_idx
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        # Blank line — continues the block (YAML allows blank lines inside)
        if not stripped:
            i += 1
            continue
        # If we hit another top-level key (column-0 letter + colon), block is done.
        if line and not line.startswith(" ") and not line.startswith("\t") and ":" in line:
            return refs, i
        # bare-string
        m = _BARE_REF_RX.match(line)
        if m:
            slug = m.group(1)
            # bare-string defaults to "thinkers" collection
            if accept_obj_collection is None or "thinkers" in accept_obj_collection:
                refs.append(slug)
            i += 1
            continue
        # flow-object: "- { collection: X, id: Y }"
        m = _FLOW_OBJ_RX.match(line)
        if m:
            slug = m.group(1)
            coll_m = _FLOW_COLLECTION_RX.search(line)
            coll = coll_m.group(1) if coll_m else "thinkers"
            if accept_obj_collection is None or coll in accept_obj_collection:
                refs.append(slug)
            i += 1
            continue
        # block-object: "- collection: X" followed by "    id: Y"
        m = _BLOCK_OBJ_START_RX.match(line)
        if m:
            coll = m.group(1)
            # Look ahead for id line
            j = i + 1
            slug = None
            while j < n:
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                m2 = _BLOCK_OBJ_ID_RX.match(nxt)
                if m2:
                    slug = m2.group(1)
                    j += 1
                    break
                # Anything else: bail
                break
            if slug and (accept_obj_collection is None or coll in accept_obj_collection):
                refs.append(slug)
            i = j
            continue
        # Otherwise, indented sub-key under a list entry (e.g. role: ..., reasoning: ...).
        # If the line is indented, we're still inside the block — skip it.
        if line.startswith(" ") or line.startswith("\t"):
            i += 1
            continue
        # Unindented non-key line: shouldn't normally happen; bail.
        return refs, i
    return refs, i


def load_thinker(path: Path) -> dict:
    """Return the §5 input-record fields derived from one thinker MD."""
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        # Bare body without frontmatter is unexpected for thinkers; emit minimal record.
        return {
            "id": path.stem,
            "name": {"canonical": path.stem, "sort": path.stem, "also_known_as": []},
            "birth_year": None,
            "death_year": None,
            "nationality": None,
            "current_fields": {
                "tradition": "unclassified",
                "canon_status": "unclassified",
                "vocations": [],
                "themes": [],
                "affiliations": [],
                "bio_source": None,
            },
            "bio_excerpt": text[:MAX_BODY_CHARS],
        }
    fm_text, body = m.group(1), m.group(2)

    # Name block (nested)
    canonical_m = _NAME_CANONICAL_RX.search(fm_text)
    sort_m = _NAME_SORT_RX.search(fm_text)

    # also_known_as: list under name; parse via dedicated block scan
    also_known_as: list[str] = []
    fm_lines = fm_text.split("\n")
    for idx, line in enumerate(fm_lines):
        if line.startswith("  also_known_as:"):
            # may be flow-style "[]" inline, or block list following
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                if inner:
                    also_known_as = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
                break
            # block-list children indented further
            j = idx + 1
            while j < len(fm_lines):
                child = fm_lines[j]
                if child.startswith("    - "):
                    val = child[6:].strip().strip('"').strip("'")
                    also_known_as.append(val)
                    j += 1
                else:
                    break
            break

    # Top-level scalars
    birth_year = _BIRTH_YEAR_RX.search(fm_text)
    death_year = _DEATH_YEAR_RX.search(fm_text)
    nationality = _NATIONALITY_RX.search(fm_text)
    tradition = _TRADITION_RX.search(fm_text)
    canon_status = _CANON_STATUS_RX.search(fm_text)
    bio_source = _BIO_SOURCE_RX.search(fm_text)

    # vocations[] — collect under top-level vocations: key
    vocations: list[str] = []
    for idx, line in enumerate(fm_lines):
        if line.startswith("vocations:"):
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                if inner:
                    vocations = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
                break
            j = idx + 1
            while j < len(fm_lines):
                child = fm_lines[j]
                if child.startswith("  - "):
                    val = child[4:].strip().strip('"').strip("'")
                    vocations.append(val)
                    j += 1
                else:
                    break
            break

    # themes[] and affiliations[] (same pattern, top-level)
    def _collect_top_level_list(field_name: str) -> list[str]:
        out: list[str] = []
        prefix = f"{field_name}:"
        for idx, line in enumerate(fm_lines):
            if line.startswith(prefix):
                rest = line.split(":", 1)[1].strip()
                if rest.startswith("[") and rest.endswith("]"):
                    inner = rest[1:-1].strip()
                    if inner:
                        out = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
                    break
                j = idx + 1
                while j < len(fm_lines):
                    child = fm_lines[j]
                    if child.startswith("  - "):
                        val = child[4:].strip().strip('"').strip("'")
                        out.append(val)
                        j += 1
                    else:
                        break
                break
        return out

    themes = _collect_top_level_list("themes")
    affiliations = _collect_top_level_list("affiliations")

    return {
        "id": path.stem,
        "name": {
            "canonical": canonical_m.group(1) if canonical_m else path.stem,
            "sort": sort_m.group(1) if sort_m else path.stem,
            "also_known_as": also_known_as,
        },
        "birth_year": int(birth_year.group(1)) if birth_year else None,
        "death_year": int(death_year.group(1)) if death_year else None,
        "nationality": nationality.group(1) if nationality else None,
        "current_fields": {
            "tradition": tradition.group(1) if tradition else "unclassified",
            "canon_status": canon_status.group(1) if canon_status else "unclassified",
            "vocations": vocations,
            "themes": themes,
            "affiliations": affiliations,
            "bio_source": bio_source.group(1) if bio_source else None,
        },
        # bio_excerpt: body[:3000], no ellipsis suffix
        "bio_excerpt": body[:MAX_BODY_CHARS],
    }


def _pw_title(fm_text: str) -> str:
    """Extract a primary-work's title (handles nested title.main and scalar)."""
    m = _PW_TITLE_MAIN_RX.search(fm_text)
    if m:
        return m.group(1).strip()
    m = _PW_TITLE_SCALAR_RX.search(fm_text)
    if m:
        return m.group(1).strip()
    return ""


def _pw_year(fm_text: str) -> int | None:
    """Extract publication.year from a primary-work frontmatter."""
    m = re.search(r"^publication:\s*\n((?:[ \t]+.*\n)+)", fm_text, re.MULTILINE)
    if not m:
        return None
    yr = _PW_PUB_YEAR_RX.search(m.group(1))
    return int(yr.group(1)) if yr else None


def load_works_authored(thinker_id: str) -> list[dict]:
    """Scan primary-works for entries where this thinker appears in authors[].

    Returns up to MAX_WORKS_AUTHORED entries, sorted by year DESC (missing
    year sorts to bottom), then by id ASC as a stable secondary key.
    """
    out: list[dict] = []
    for path in sorted(PRIMARY_WORKS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RX.match(text)
        if not m:
            continue
        fm_text = m.group(1)
        fm_lines = fm_text.split("\n")

        # Find authors: key and read its list block
        authors_refs: list[str] = []
        for idx, line in enumerate(fm_lines):
            if line.startswith("authors:"):
                rest = line.split(":", 1)[1].strip()
                if rest.startswith("[") and rest.endswith("]"):
                    # flow-list — extract bare slugs
                    inner = rest[1:-1].strip()
                    if inner:
                        for tok in inner.split(","):
                            tok = tok.strip().strip('"').strip("'")
                            if tok and re.match(r"^[a-z0-9][a-z0-9-]*$", tok):
                                authors_refs.append(tok)
                    break
                # block-list — collect bare/object refs, filter to thinkers-collection only
                refs, _ = _read_list_block_collect_refs(
                    fm_lines,
                    idx + 1,
                    accept_obj_collection=("thinkers",),
                    field="authors",
                )
                authors_refs = refs
                break

        if thinker_id not in authors_refs:
            continue

        work_type_m = _PW_WORK_TYPE_RX.search(fm_text)
        out.append({
            "id": path.stem,
            "title": _pw_title(fm_text),
            "year": _pw_year(fm_text),
            "work_type": work_type_m.group(1) if work_type_m else None,
        })

    # Sort: year DESC (missing = bottom), id ASC
    def sort_key(rec: dict):
        y = rec["year"] if rec["year"] is not None else float("-inf")
        return (-y if isinstance(y, int) else float("inf"), rec["id"])

    out.sort(key=sort_key)
    return out[:MAX_WORKS_AUTHORED]


# Role priority for mention_contexts ordering
_ROLE_PRIORITY = {
    "subject": 3,
    "thinker_mention": 2,
    "related_thinker": 1,
    "contributor": 1,
}


def _build_excerpt(lines: list[str], start_idx: int, limit: int = MENTION_EXCERPT_CHARS) -> str:
    """Take the key line + next 1-2 indented lines (where they exist) as the
    excerpt. Truncate to limit chars."""
    parts: list[str] = [lines[start_idx].rstrip()]
    j = start_idx + 1
    added = 0
    while j < len(lines) and added < 2:
        nxt = lines[j]
        # Only follow-on indented lines (children of this list entry)
        if (nxt.startswith("    ") or nxt.startswith("      ")) and nxt.strip():
            parts.append(nxt.rstrip())
            added += 1
            j += 1
        else:
            break
    excerpt = " ".join(p.strip() for p in parts)
    if len(excerpt) > limit:
        excerpt = excerpt[:limit].rstrip()
    return excerpt


def _scan_one_md_for_mentions(
    path: Path,
    thinker_id: str,
    collection: str,
) -> list[dict]:
    """Return mention_context records for one source MD where thinker_id
    appears in any of: thinker_mentions[].thinker, related_thinkers[],
    subject (scalar), and (for primary-works only) contributors[].thinker.

    authors[] is EXCLUDED (those count toward works_authored).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return []
    fm_text = m.group(1)
    fm_lines = fm_text.split("\n")
    source_key = f"{collection}/{path.stem}"
    found: list[dict] = []

    # Track block state line-by-line
    block_state: str | None = None  # one of: thinker_mentions, related_thinkers, contributors
    i = 0
    n = len(fm_lines)
    while i < n:
        line = fm_lines[i]
        stripped_lhs = line.split("#", 1)[0].rstrip()

        # Detect entering a top-level block
        if line.startswith("thinker_mentions:"):
            block_state = "thinker_mentions"
            i += 1
            continue
        if line.startswith("related_thinkers:"):
            block_state = "related_thinkers"
            i += 1
            continue
        if line.startswith("contributors:") and collection == "primary-works":
            block_state = "contributors"
            i += 1
            continue
        # subject is a top-level scalar key
        if line.startswith("subject:"):
            rest = line.split(":", 1)[1].strip().strip('"').strip("'")
            if rest == thinker_id:
                found.append({
                    "source": source_key,
                    "excerpt": _build_excerpt(fm_lines, i),
                    "role": "subject",
                })
            block_state = None
            i += 1
            continue

        # Detect leaving a block: hit another top-level key
        if (
            stripped_lhs
            and not line.startswith(" ")
            and not line.startswith("\t")
            and ":" in line
            and _TOP_LEVEL_KEY_RX.match(line)
        ):
            block_state = None
            # don't 'continue' — re-process this line below
            # (but at this branch we know it's a top-level key that isn't one of the watched ones)
            i += 1
            continue

        # Inside a watched block: scan for the thinker
        if block_state == "thinker_mentions":
            # Inline form: "  - thinker: <slug>"
            m_tm = _TM_INLINE_RX.match(line)
            if m_tm and m_tm.group(1) == thinker_id:
                found.append({
                    "source": source_key,
                    "excerpt": _build_excerpt(fm_lines, i),
                    "role": "thinker_mention",
                })
            # Block-style sub-key form: "    thinker: <slug>" (no leading "-")
            elif not line.lstrip().startswith("-"):
                m_id = _TM_ID_LINE_RX.match(line)
                if m_id and m_id.group(1) == thinker_id:
                    found.append({
                        "source": source_key,
                        "excerpt": _build_excerpt(fm_lines, i),
                        "role": "thinker_mention",
                    })
            i += 1
            continue

        if block_state == "related_thinkers":
            # Bare-string
            m_b = _BARE_REF_RX.match(line)
            if m_b and m_b.group(1) == thinker_id:
                found.append({
                    "source": source_key,
                    "excerpt": _build_excerpt(fm_lines, i),
                    "role": "related_thinker",
                })
                i += 1
                continue
            # Flow-object
            m_f = _FLOW_OBJ_RX.match(line)
            if m_f and m_f.group(1) == thinker_id:
                coll_m = _FLOW_COLLECTION_RX.search(line)
                coll = coll_m.group(1) if coll_m else "thinkers"
                if coll == "thinkers":
                    found.append({
                        "source": source_key,
                        "excerpt": _build_excerpt(fm_lines, i),
                        "role": "related_thinker",
                    })
                i += 1
                continue
            # Block-object: "- collection: thinkers" followed by "  id: <slug>"
            m_bs = _BLOCK_OBJ_START_RX.match(line)
            if m_bs:
                coll = m_bs.group(1)
                j = i + 1
                while j < n and not fm_lines[j].strip():
                    j += 1
                if j < n:
                    m_bid = _BLOCK_OBJ_ID_RX.match(fm_lines[j])
                    if m_bid and m_bid.group(1) == thinker_id and coll == "thinkers":
                        found.append({
                            "source": source_key,
                            "excerpt": _build_excerpt(fm_lines, i),
                            "role": "related_thinker",
                        })
                i += 1
                continue
            i += 1
            continue

        if block_state == "contributors":
            # Inline: "  - thinker: <slug>"
            m_c = _CONTRIB_INLINE_RX.match(line)
            if m_c and m_c.group(1) == thinker_id:
                found.append({
                    "source": source_key,
                    "excerpt": _build_excerpt(fm_lines, i),
                    "role": "contributor",
                })
            # Block style: "    thinker: <slug>" inside a "- " entry
            elif not line.lstrip().startswith("-"):
                m_cid = _TM_ID_LINE_RX.match(line)
                if m_cid and m_cid.group(1) == thinker_id:
                    found.append({
                        "source": source_key,
                        "excerpt": _build_excerpt(fm_lines, i),
                        "role": "contributor",
                    })
            i += 1
            continue

        i += 1

    return found


def load_mention_contexts(thinker_id: str) -> list[dict]:
    """Return up to MAX_MENTION_CONTEXTS mention contexts across all
    mention-bearing collections. Sorted by role priority (subject > mention
    > related/contributor) then by source slug ASC."""
    all_found: list[dict] = []
    for collection in MENTION_COLLECTIONS:
        coll_dir = CONTENT_ROOT / collection
        if not coll_dir.exists():
            continue
        for md in sorted(coll_dir.glob("*.md")):
            all_found.extend(_scan_one_md_for_mentions(md, thinker_id, collection))

    def sort_key(rec: dict) -> tuple:
        return (-_ROLE_PRIORITY.get(rec["role"], 0), rec["source"])

    all_found.sort(key=sort_key)
    return all_found[:MAX_MENTION_CONTEXTS]


def assemble_record(thinker_path: Path) -> dict:
    """Combine load_thinker + load_works_authored + load_mention_contexts."""
    rec = load_thinker(thinker_path)
    rec["works_authored"] = load_works_authored(rec["id"])
    rec["mention_contexts"] = load_mention_contexts(rec["id"])
    return rec


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _pilot_ids() -> list[str]:
    if not GROUND_TRUTH.exists():
        raise SystemExit(
            f"ERROR: {GROUND_TRUTH} missing. Run pilot-classify-thinkers.py --bootstrap first."
        )
    entries = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    return [e["id"] for e in entries]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="emit one batch from pilot-ground-truth.json")
    args = ap.parse_args(argv[1:])

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.pilot:
        wanted = set(_pilot_ids())
        records: list[dict] = []
        for path in sorted(THINKERS_DIR.glob("*.md")):
            if path.stem in wanted:
                records.append(assemble_record(path))
        out_path = DATA_DIR / "pilot-batch.jsonl"
        _write_jsonl(out_path, records)
        print(f"wrote pilot-batch.jsonl with {len(records)} records")
        return 0

    # Default: round-robin all 506 thinkers into 10 batches
    paths = sorted(THINKERS_DIR.glob("*.md"))
    # Wipe stale batch files so re-runs are reproducible
    for stale in DATA_DIR.glob("batch-*.jsonl"):
        stale.unlink()

    batches: list[list[dict]] = [[] for _ in range(N_BATCHES)]
    for i, path in enumerate(paths):
        rec = assemble_record(path)
        batches[i % N_BATCHES].append(rec)

    total = 0
    for i, batch_records in enumerate(batches):
        out_path = DATA_DIR / f"batch-{i:02d}.jsonl"
        _write_jsonl(out_path, batch_records)
        total += len(batch_records)

    print(f"wrote {N_BATCHES} batches; total {total} records")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
