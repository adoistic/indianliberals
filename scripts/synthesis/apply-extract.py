#!/usr/bin/env python3
"""
Apply Claude-vision extraction outputs to primary-work MD files.

For each `data/extract/output-<id>.json`:
  - Validate shape + themes vocab membership
  - Replace placeholder body with proper `## Summary` + `## Key points` sections
  - Write `summary` (literal-strip YAML scalar) + `ai_key_points[]` + `themes[]`
    into frontmatter
  - Set `needs_extraction: false` (was `true` on these entries)
  - Set `needs_review` per the subagent's flag

Run:
    .venv-extract/bin/python3 scripts/synthesis/apply-extract.py
    .venv-extract/bin/python3 scripts/synthesis/apply-extract.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/apply-extract.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "apps/site/src/content/primary-works"
EXTRACT_DIR = ROOT / "data/extract"
THEMES_VOCAB = ROOT / "data/themes-vocab.json"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def load_themes_vocab() -> set[str]:
    return set(json.loads(THEMES_VOCAB.read_text()))


def validate(rec: dict, vocab: set[str]) -> tuple[bool, list[str]]:
    errs: list[str] = []
    rid = rec.get("id")
    if not isinstance(rid, str) or not rid:
        errs.append("missing id")
    summary = rec.get("summary", "")
    if not isinstance(summary, str) or len(summary) < 100:
        errs.append(f"summary too short ({len(summary) if isinstance(summary, str) else 'n/a'} chars; need ≥100)")
    pts = rec.get("ai_key_points", [])
    if not isinstance(pts, list) or len(pts) < 3:
        errs.append(f"ai_key_points should have ≥3 entries, got {len(pts) if isinstance(pts, list) else 'n/a'}")
    themes_in = rec.get("themes", [])
    if not isinstance(themes_in, list):
        errs.append("themes must be a list")
    yr = rec.get("source_year_inferred")
    if yr is not None and (not isinstance(yr, int) or yr < 1800 or yr > 2027):
        errs.append(f"source_year_inferred out of range: {yr}")
    return (not errs, errs)


def _yaml_quote(s: str) -> str:
    """Quote a single-line scalar for YAML."""
    if not s:
        return '""'
    needs = any(c in s for c in ":#&*!|>'\"%@`{}[]\n\r\t") or s[0] in "-?:" or s.endswith(" ")
    if needs:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return s


def emit_summary_block(summary: str, indent: int = 0) -> str:
    """Emit a `summary: |-` literal-strip block. Two-space indent for content."""
    pad = " " * indent
    body_indent = " " * (indent + 2)
    lines = summary.rstrip().split("\n")
    out = [f"{pad}summary: |-"]
    for line in lines:
        if line:
            out.append(f"{body_indent}{line}")
        else:
            out.append("")
    return "\n".join(out)


def emit_string_list(key: str, values: list[str], indent: int = 0) -> str:
    pad = " " * indent
    if not values:
        return f"{pad}{key}: []"
    lines = [f"{pad}{key}:"]
    for v in values:
        lines.append(f'{pad}  - {_yaml_quote(v)}')
    return "\n".join(lines)


# Frontmatter mutation primitives ────────────────────────────────────────

def replace_or_append_block(fm: str, key: str, new_block: str, *, top_level: bool = True) -> str:
    """Replace an existing `<key>: ...` block (multi-line) or append.

    The existing block is whatever starts at `^<key>:` and runs until either
    EOF or the next top-level (zero-indent) `^[a-z_]+:` line.
    """
    rx = re.compile(
        rf"^{re.escape(key)}:(?:[ \t]*\n(?:[ \t]+.*\n?)*|[ \t]+.*\n?(?:[ \t]+.*\n?)*)",
        re.M,
    )
    if rx.search(fm):
        return rx.sub(new_block.rstrip() + "\n", fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + new_block.rstrip() + "\n"


def replace_or_append_line(fm: str, key: str, value_line: str) -> str:
    """Replace an existing single-line `<key>: <value>` or append."""
    rx = re.compile(rf"^{re.escape(key)}:[ \t]*\S.*$", re.M)
    if rx.search(fm):
        return rx.sub(value_line, fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + value_line + "\n"


# Body construction ─────────────────────────────────────────────────────

def build_body(summary: str, key_points: list[str]) -> str:
    parts = ["## Summary", "", summary.strip(), "", "## Key points", ""]
    for pt in key_points:
        parts.append(f"- {pt.strip()}")
    parts.append("")
    return "\n".join(parts) + "\n"


def process_one(md: Path, rec: dict, vocab: set[str], dry_run: bool, log: list[str]) -> str:
    ok, errs = validate(rec, vocab)
    if not ok:
        log.append(f"[{rec.get('id', md.stem)}] validation failed: {'; '.join(errs)}")
        return "rejected"

    text = md.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return "skip-no-frontmatter"
    fm = m.group(1)

    summary = rec["summary"].strip()
    key_points = [p.strip() for p in rec.get("ai_key_points", []) if isinstance(p, str)]
    themes_clean = sorted({t for t in rec.get("themes", []) if isinstance(t, str) and t in vocab})
    dropped = [t for t in rec.get("themes", []) if isinstance(t, str) and t not in vocab]
    if dropped:
        log.append(f"[{rec['id']}] dropped out-of-vocab themes: {dropped}")
    needs_review = bool(rec.get("needs_review", False))

    # Mutate frontmatter
    fm = replace_or_append_block(fm, "summary", emit_summary_block(summary))
    fm = replace_or_append_block(fm, "ai_key_points", emit_string_list("ai_key_points", key_points))
    fm = replace_or_append_block(fm, "themes", emit_string_list("themes", themes_clean))
    fm = replace_or_append_line(fm, "needs_extraction", "needs_extraction: false")
    fm = replace_or_append_line(fm, "needs_review", f"needs_review: {'true' if needs_review else 'false'}")

    new_body = build_body(summary, key_points)
    new_text = f"---\n{fm.rstrip()}\n---\n\n{new_body}"

    if dry_run:
        return "would-apply"
    md.write_text(new_text, encoding="utf-8")
    return "applied"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    vocab = load_themes_vocab()
    summary: dict[str, int] = {}
    log: list[str] = []

    for out_path in sorted(EXTRACT_DIR.glob("output-*.json")):
        try:
            rec = json.loads(out_path.read_text())
        except json.JSONDecodeError as e:
            log.append(f"{out_path.name}: invalid JSON — {e}")
            summary["json-error"] = summary.get("json-error", 0) + 1
            continue
        rid = rec.get("id")
        if not rid:
            log.append(f"{out_path.name}: missing id")
            summary["missing-id"] = summary.get("missing-id", 0) + 1
            continue
        md = CONTENT_DIR / f"{rid}.md"
        if not md.exists():
            log.append(f"{rid}: MD file not found at {md}")
            summary["md-not-found"] = summary.get("md-not-found", 0) + 1
            continue
        result = process_one(md, rec, vocab, args.dry_run, log)
        summary[result] = summary.get(result, 0) + 1

    for k in sorted(summary):
        print(f"  {summary[k]:5d}  {k}")
    print(f"  warnings: {len(log)}")
    (EXTRACT_DIR / "apply-log.txt").write_text("\n".join(log) + "\n" if log else "(no warnings)\n")
    print(f"  log: {(EXTRACT_DIR / 'apply-log.txt').relative_to(ROOT)}")
    return 0


def _run_tests():
    import tempfile

    vocab = {"agriculture", "economic-policy", "free-enterprise"}

    # Happy path
    rec = {
        "id": "test",
        "summary": "First paragraph of a test summary that is reasonably substantive in length and clearly describes the contents of the work in plain English prose.\n\nSecond paragraph offering more detail about the work's argument and structure.",
        "ai_key_points": ["Point one.", "Point two.", "Point three."],
        "themes": ["agriculture", "not-in-vocab"],
        "source_year_inferred": 1992,
        "needs_review": False,
    }
    ok, errs = validate(rec, vocab)
    assert ok, errs

    sample_md = """---
id: "test"
title:
  main: "Test"
themes:
  - "old-theme"
needs_extraction: true
needs_review: true
draft: false
---

 Metadata is
preserved; body text is pending the AI-extraction pipeline.
"""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.md"
        p.write_text(sample_md)
        log: list[str] = []
        # Patch CONTENT_DIR for this test
        global CONTENT_DIR
        orig = CONTENT_DIR
        CONTENT_DIR = Path(td)
        try:
            result = process_one(p, rec, vocab, dry_run=False, log=log)
            assert result == "applied", result
            out = p.read_text()
            assert "## Summary" in out
            assert "## Key points" in out
            assert "- Point one." in out
            assert "needs_extraction: false" in out
            assert "needs_review: false" in out
            assert "agriculture" in out
            assert "not-in-vocab" not in out  # dropped
            assert "old-theme" not in out  # overwritten
            assert "Metadata is" not in out  # placeholder gone
            assert any("dropped out-of-vocab" in m for m in log)
        finally:
            CONTENT_DIR = orig

    # Bad input: short summary
    bad = {"id": "x", "summary": "too short", "ai_key_points": [], "themes": []}
    ok, errs = validate(bad, vocab)
    assert not ok
    assert any("too short" in e for e in errs)

    # needs_review propagation
    rec2 = {**rec, "needs_review": True}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.md"
        p.write_text(sample_md)
        CONTENT_DIR = Path(td)
        try:
            process_one(p, rec2, vocab, dry_run=False, log=[])
            assert "needs_review: true" in p.read_text()
        finally:
            CONTENT_DIR = orig

    print("apply-extract tests passed.")


if __name__ == "__main__":
    sys.exit(main())
