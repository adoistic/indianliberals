#!/usr/bin/env python3
"""
Step 4 of the byline-resolution pipeline.

Walks data/byline-resolve/{deterministic-resolved.jsonl, llm-output-*.json,
vision-output-*.json}, merging per-entry. Process order: deterministic
first (most confident), then LLM, then vision — a higher-confidence pass
already locks in `authors[]` so later passes can't overwrite.

For each entry:
  - Matched authors → authors[] (or contributors[] with role for non-author roles)
  - Unknown names → auto-create stub thinker MD at apps/site/src/content/thinkers/<slug>.md
                   (or log collision if slug already exists)
  - Write authors_resolution object (confidence, method, proposed_unknowns,
    stubs_created, stubs_referenced, collisions_logged)
  - Set needs_review: true when confidence != high OR stubs/collisions occurred

Run:
    .venv-extract/bin/python3 scripts/synthesis/apply-byline.py
    .venv-extract/bin/python3 scripts/synthesis/apply-byline.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/apply-byline.py --test
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW_DIR = ROOT / "apps/site/src/content/primary-works"
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
OUT_DIR = ROOT / "data/byline-resolve"
COLLISIONS_LOG = OUT_DIR / "collisions.log"
APPLY_LOG = OUT_DIR / "apply-log.txt"

VALID_ROLES = {"author", "editor", "translator", "foreword", "introduction", "preface"}
NON_AUTHOR_ROLES = {"editor", "translator", "foreword", "introduction", "preface"}
NEW_STUB_TRADITION = "unclassified"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def kebab(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


# YAML emit helpers ──────────────────────────────────────────────────────

def _yaml_str(s: str) -> str:
    if s is None:
        return '""'
    s = str(s)
    needs = any(c in s for c in ":#&*!|>'\"%@`{}[]\n\r\t") or (s and s[0] in "-?:") or s.endswith(" ")
    if needs:
        esc = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{esc}"'
    return s


def _emit_authors_block(slugs: list[str]) -> str:
    if not slugs:
        return "authors: []"
    lines = ["authors:"]
    for s in slugs:
        lines.append(f'  - {_yaml_str(s)}')
    return "\n".join(lines)


def _emit_contributors_block(items: list[dict]) -> str:
    if not items:
        return "contributors: []"
    lines = ["contributors:"]
    for it in items:
        lines.append(f'  - thinker: {_yaml_str(it["thinker"])}')
        lines.append(f'    role: {it["role"]}')
    return "\n".join(lines)


def _emit_resolution_block(res: dict) -> str:
    """Emit the authors_resolution block."""
    lines = ["authors_resolution:"]
    if res.get("confidence"):
        lines.append(f'  confidence: {res["confidence"]}')
    if res.get("method"):
        lines.append(f'  method: {res["method"]}')
    for key in ("proposed_unknowns", "stubs_created", "stubs_referenced", "collisions_logged"):
        vals = res.get(key) or []
        if not vals:
            lines.append(f"  {key}: []")
        else:
            lines.append(f"  {key}:")
            for v in vals:
                lines.append(f'    - {_yaml_str(v)}')
    return "\n".join(lines)


# Frontmatter mutation ─────────────────────────────────────────────────

def _replace_or_append_line(fm: str, key: str, value_line: str) -> str:
    rx = re.compile(rf"^{re.escape(key)}:[ \t]*\S.*$", re.M)
    if rx.search(fm):
        return rx.sub(value_line, fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + value_line + "\n"


def _replace_or_append_block(fm: str, key: str, new_block: str) -> str:
    rx = re.compile(
        rf"^{re.escape(key)}:(?:[ \t]*\n(?:[ \t]+.*\n?)*|[ \t]+.*\n?(?:[ \t]+.*\n?)*)",
        re.M,
    )
    if rx.search(fm):
        return rx.sub(new_block.rstrip() + "\n", fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + new_block.rstrip() + "\n"


# Stub creation ─────────────────────────────────────────────────────────

def stub_thinker_md(slug: str, canonical: str) -> str:
    today = datetime.date.today().isoformat()
    # Build a sort key: "Last, First" if invertible, else canonical
    parts = canonical.split()
    if len(parts) >= 2:
        sort = f"{parts[-1]}, {' '.join(parts[:-1])}"
    else:
        sort = canonical
    return f"""---
id: {slug}
name:
  canonical: {_yaml_str(canonical)}
  sort: {_yaml_str(sort)}
  also_known_as: []
tradition: {NEW_STUB_TRADITION}
nationality: india
themes: []
affiliations: []
bio_source: ai_drafted_stub
needs_review: true
draft: false
ai:
  drafted_by: claude-sonnet-4.6
  drafted_at: {today}
  model_version: byline-resolve-{today}
---
"""


def existing_thinker_canonical(slug: str) -> str | None:
    path = THINKERS_DIR / f"{slug}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm = m.group(1)
    cn = re.search(r"^\s+canonical:\s*[\"']?(.+?)[\"']?\s*$", fm, re.M)
    return cn.group(1).strip() if cn else None


# Per-entry applier ─────────────────────────────────────────────────────

def process_entry(
    entry_id: str,
    record: dict,
    run_stubs_created: set[str],
    dry_run: bool,
    log: list[str],
) -> str:
    md = PW_DIR / f"{entry_id}.md"
    if not md.exists():
        log.append(f"[{entry_id}] MD file missing — skipped")
        return "skip-no-md"
    text = md.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        log.append(f"[{entry_id}] no frontmatter — skipped")
        return "skip-no-fm"
    fm, body = m.group(1), m.group(2)

    # Authors / contributors routing
    authors: list[str] = []
    contributors: list[dict] = []
    for match in record.get("matches", []):
        slug = match.get("slug")
        role = match.get("role", "author")
        if not slug:
            continue
        if role in NON_AUTHOR_ROLES:
            contributors.append({"thinker": slug, "role": role})
        else:
            authors.append(slug)

    # Stub creation for unknowns
    stubs_created: list[str] = []
    stubs_referenced: list[str] = []
    collisions_logged: list[str] = []
    proposed_unknowns: list[str] = list(record.get("unknowns") or [])

    for name in proposed_unknowns:
        slug = kebab(name)
        if not slug:
            continue
        if slug in run_stubs_created:
            # Same-run earlier creation — silent reference
            authors.append(slug)
            stubs_referenced.append(slug)
            continue
        existing_canonical = existing_thinker_canonical(slug)
        if existing_canonical is not None:
            # Pre-existing thinker collision — link but log
            authors.append(slug)
            collisions_logged.append(slug)
            log.append(
                f"[{entry_id}] COLLISION: proposed unknown '{name}' → slug '{slug}' "
                f"already exists as '{existing_canonical}' (linking anyway per spec §3)"
            )
            if not dry_run:
                COLLISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
                with COLLISIONS_LOG.open("a", encoding="utf-8") as cl:
                    cl.write(
                        f"{datetime.datetime.utcnow().isoformat()}Z\t{entry_id}\t"
                        f"{name}\t{slug}\t{existing_canonical}\n"
                    )
            continue
        # Genuine new stub
        if not dry_run:
            stub_path = THINKERS_DIR / f"{slug}.md"
            stub_path.write_text(stub_thinker_md(slug, name), encoding="utf-8")
        authors.append(slug)
        run_stubs_created.add(slug)
        stubs_created.append(slug)

    # Deduplicate authors[] while preserving order
    authors = list(dict.fromkeys(authors))

    # Compose mutations
    if authors:
        fm = _replace_or_append_block(fm, "authors", _emit_authors_block(authors))
    if contributors:
        # Read existing contributors and append (don't overwrite TOC-driven contribs)
        # For v1: just write our additions; this is acceptable for unbylined entries
        # which by definition started with empty contributors.
        fm = _replace_or_append_block(fm, "contributors", _emit_contributors_block(contributors))

    confidence = record.get("confidence")
    method = record.get("method")
    resolution = {
        "confidence": confidence,
        "method": method,
        "proposed_unknowns": proposed_unknowns,
        "stubs_created": stubs_created,
        "stubs_referenced": stubs_referenced,
        "collisions_logged": collisions_logged,
    }
    fm = _replace_or_append_block(fm, "authors_resolution", _emit_resolution_block(resolution))

    # needs_review flag
    flag_review = (
        confidence != "high"
        or stubs_created
        or collisions_logged
        or not authors  # genuinely unresolved
    )
    fm = _replace_or_append_line(
        fm,
        "needs_review",
        f"needs_review: {'true' if flag_review else 'false'}",
    )

    new_text = f"---\n{fm.rstrip()}\n---\n{body if body.startswith(chr(10)) else chr(10) + body}"
    if dry_run:
        return "would-apply"
    md.write_text(new_text, encoding="utf-8")
    return "applied"


# Driver ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    # Aggregate records by id, in process order
    records: dict[str, dict] = {}
    # Deterministic first
    det_path = OUT_DIR / "deterministic-resolved.jsonl"
    if det_path.exists():
        for line in det_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            records[rec["id"]] = {**rec}

    # LLM outputs (don't overwrite deterministic)
    # Skip LLM records that flagged needs_vision: they're pass-through markers,
    # not resolutions, and would otherwise block the corresponding vision record.
    for fp in sorted(OUT_DIR.glob("llm-output-*.json")):
        arr = json.loads(fp.read_text())
        for rec in arr:
            rid = rec.get("id")
            if not rid or rid in records:
                continue
            if rec.get("needs_vision"):
                continue
            rec.setdefault("method", "llm")
            records[rid] = rec

    # Vision outputs (don't overwrite anything earlier)
    for fp in sorted(OUT_DIR.glob("vision-output-*.json")):
        rec = json.loads(fp.read_text())
        rid = rec.get("id")
        if not rid or rid in records:
            continue
        rec.setdefault("method", "vision")
        records[rid] = rec

    print(f"records to apply: {len(records)}")

    run_stubs: set[str] = set()
    log: list[str] = []
    summary: dict[str, int] = {}
    for entry_id, rec in records.items():
        result = process_entry(entry_id, rec, run_stubs, args.dry_run, log)
        summary[result] = summary.get(result, 0) + 1
    for k in sorted(summary):
        print(f"  {summary[k]:5d}  {k}")
    print(f"  stubs newly created: {len(run_stubs)}")
    APPLY_LOG.write_text("\n".join(log) + "\n" if log else "(no warnings)\n")
    print(f"  log: {APPLY_LOG.relative_to(ROOT)}")
    return 0


def _run_tests():
    import tempfile

    # kebab
    assert kebab("R. C. Cooper") == "r-c-cooper"
    assert kebab("Dhirajlal Maganlal") == "dhirajlal-maganlal"

    # stub_thinker_md shape
    stub = stub_thinker_md("dhirajlal-maganlal", "Dhirajlal Maganlal")
    assert 'id: dhirajlal-maganlal' in stub
    assert 'canonical: Dhirajlal Maganlal' in stub
    assert 'tradition: unclassified' in stub
    assert 'bio_source: ai_drafted_stub' in stub
    assert 'needs_review: true' in stub

    # YAML emit
    assert _emit_authors_block([]) == "authors: []"
    assert "  - a-d-shroff" in _emit_authors_block(["a-d-shroff"])
    assert "  - thinker: a-d-shroff" in _emit_contributors_block([{"thinker": "a-d-shroff", "role": "editor"}])
    assert "  - role: editor" not in _emit_contributors_block([{"thinker": "x", "role": "editor"}])  # role uses 4-space indent
    assert "    role: editor" in _emit_contributors_block([{"thinker": "x", "role": "editor"}])

    # process_entry happy path: matches + unknowns + needs_review flag
    sample_md = """---
id: "test-entry"
title:
  main: "Test Speech"
authors: []
contributors: []
needs_review: true
draft: false
---

Body content here.
"""
    rec = {
        "id": "test-entry",
        "matches": [{"slug": "a-d-shroff", "role": "author"}],
        "unknowns": ["New Unknown Person"],
        "confidence": "medium",
        "method": "llm",
    }
    log: list[str] = []
    global PW_DIR, THINKERS_DIR
    orig_pw, orig_th = PW_DIR, THINKERS_DIR
    with tempfile.TemporaryDirectory() as td:
        PW_DIR = Path(td) / "primary-works"
        THINKERS_DIR = Path(td) / "thinkers"
        PW_DIR.mkdir()
        THINKERS_DIR.mkdir()
        (PW_DIR / "test-entry.md").write_text(sample_md)
        try:
            result = process_entry("test-entry", rec, set(), False, log)
            assert result == "applied", result
            new = (PW_DIR / "test-entry.md").read_text()
            assert "- a-d-shroff" in new
            assert "- new-unknown-person" in new
            assert "authors_resolution:" in new
            assert "confidence: medium" in new
            assert "method: llm" in new
            assert "needs_review: true" in new  # stub_created or non-high → true
            # Stub thinker MD was created
            stub_path = THINKERS_DIR / "new-unknown-person.md"
            assert stub_path.exists()
            stub_text = stub_path.read_text()
            assert 'canonical: "New Unknown Person"' in stub_text or 'canonical: New Unknown Person' in stub_text
        finally:
            PW_DIR, THINKERS_DIR = orig_pw, orig_th

    # Editor / non-author role path: matches with role='editor' should land in
    # contributors[], not authors[]
    sample_md_b = """---
id: "edited-work"
title:
  main: "Test Edited Volume"
authors: []
contributors: []
needs_review: true
draft: false
---

Body.
"""
    rec_b = {
        "id": "edited-work",
        "matches": [
            {"slug": "a-d-shroff", "role": "editor"},
            {"slug": "minoo-shroff", "role": "translator"},
        ],
        "confidence": "high",
        "method": "llm",
    }
    log_b: list[str] = []
    orig_pw, orig_th = PW_DIR, THINKERS_DIR
    with tempfile.TemporaryDirectory() as td:
        PW_DIR = Path(td) / "primary-works"
        THINKERS_DIR = Path(td) / "thinkers"
        PW_DIR.mkdir()
        THINKERS_DIR.mkdir()
        (PW_DIR / "edited-work.md").write_text(sample_md_b)
        try:
            result_b = process_entry("edited-work", rec_b, set(), False, log_b)
            assert result_b == "applied", result_b
            new_b = (PW_DIR / "edited-work.md").read_text()
            # No authors[] populated (both matches were non-author roles)
            assert "authors: []" in new_b, "authors[] should be empty when only non-author roles match"
            # Both contributors present with correct roles
            assert "thinker: a-d-shroff" in new_b
            assert "role: editor" in new_b
            assert "thinker: minoo-shroff" in new_b
            assert "role: translator" in new_b
            # High confidence + no stubs + no collisions + no resolved authors → needs_review STILL true (no authors)
            assert "needs_review: true" in new_b
        finally:
            PW_DIR, THINKERS_DIR = orig_pw, orig_th

    print("apply-byline tests passed.")


if __name__ == "__main__":
    sys.exit(main())
