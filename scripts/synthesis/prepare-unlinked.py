#!/usr/bin/env python3
"""
Compile every Tier-A entry that lacks a structured thinker reference into
`data/synthesis/unlinked.jsonl` — one JSON object per line, ready to be
fed into the cross-link resolver (manual or `claude -p` automated).

See `docs/superpowers/specs/2026-05-18-cross-link-audit-design.md` for
the surrounding design.

Run from the repo root:

    python3 scripts/synthesis/prepare-unlinked.py [--limit N] [--collections musings,opinions,...]

Output: `data/synthesis/unlinked.jsonl`

Per-entry record schema:

    {
      "id":          "<slug>",
      "collection":  "musings | opinions | interviews | primary-works",
      "slug":        "<slug>",
      "title":       "<entry title or fallback>",
      "body_excerpt": "<first 500 chars of body text, markdown-stripped>",
      "current_author_hint":  "<author_name or subject_name string from FM, or null>",
      "byline_verbatim":      "<for primary-works only: the raw byline string from contributors[0]>",
      "expected_role":        "author | subject"
    }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
BAKE_DIR = ROOT / "data/bake-off-output"
OUT_PATH = ROOT / "data/synthesis/unlinked.jsonl"


# (collection, ref_fields_that_indicate_linked, expected_role_for_resolver)
SPECS = [
    ("musings",         ["author"],                     "author"),
    ("opinions",        ["author", "subject"],          "subject"),
    ("interviews",      ["subject"],                    "subject"),
    ("theprint-mirror", ["author", "related_thinkers"], "author"),
    ("primary-works",   ["authors"],                    "author"),
]


def has_nonempty_ref(fm: str, fields: list[str]) -> bool:
    for f in fields:
        m = re.search(rf'^{f}:\s*"([^"]+)"\s*$', fm, re.M)
        if m and m.group(1).strip():
            return True
        m = re.search(rf'^{f}:\s*\n((?:\s+-\s+.+\n)+)', fm, re.M)
        if m:
            return True
        m = re.search(rf'^{f}:\s*\[(.+?)\]', fm, re.M)
        if m and m.group(1).strip() not in ("", '""'):
            return True
    return False


def extract_fm_field(fm: str, field: str) -> str:
    """Return the bare value of `<field>: "..."` or `<field>: ...`, or empty."""
    m = re.search(rf'^{field}:\s*"?([^"\n]+)"?\s*$', fm, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def author_or_subject_hint(fm: str) -> str:
    for f in ("subject_name", "author_name"):
        v = extract_fm_field(fm, f)
        if v:
            return v
    return ""


def md_body_excerpt(text: str, n: int = 500) -> str:
    """Return the first n chars of the body (post-frontmatter), with
    markdown syntax stripped down to readable prose."""
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.S)
    body = (m.group(1) if m else text).strip()
    # Strip code fences, links, images, html, headings
    body = re.sub(r"```.*?```", " ", body, flags=re.S)
    body = re.sub(r"`[^`]*`", " ", body)
    body = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"^#+\s+", "", body, flags=re.M)
    body = re.sub(r"[*_~|]+", "", body)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:n]


def title_of(fm: str, slug: str) -> str:
    # multilingualTitle (primary-works): title.main
    m = re.search(r"^title:\s*\n\s+main:\s*\"?([^\"\n]+)\"?", fm, re.M)
    if m:
        return m.group(1).strip().strip('"')
    # name.canonical (thinkers — shouldn't appear here but defensive)
    m = re.search(r"^name:\s*\n\s+canonical:\s*\"?([^\"\n]+)\"?", fm, re.M)
    if m:
        return m.group(1).strip().strip('"')
    v = extract_fm_field(fm, "title")
    return v or slug


def collect_primary_works_byline(slug: str) -> str | None:
    """For primary-works, the canonical byline lives in the extraction
    metadata (data/bake-off-output/<slug>/metadata.a.a.json), not in
    the emitted frontmatter. Pull the first contributor with role=author
    or just the first contributor."""
    meta_path = BAKE_DIR / slug / "metadata.a.a.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        return None
    contributors = meta.get("contributors") or []
    for c in contributors:
        if not isinstance(c, dict):
            continue
        if c.get("role") == "author" and c.get("byline_verbatim"):
            return c["byline_verbatim"]
    # Fallback: any contributor
    for c in contributors:
        if isinstance(c, dict) and c.get("byline_verbatim"):
            return c["byline_verbatim"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Cap total entries emitted (debug)")
    ap.add_argument(
        "--collections", default="",
        help="Comma-separated subset of collections to process (default: all)"
    )
    args = ap.parse_args()
    only = set(args.collections.split(",")) if args.collections else None

    records: list[dict] = []
    per_col: dict[str, int] = {}

    for col, ref_fields, expected_role in SPECS:
        if only and col not in only:
            continue
        coldir = CONTENT_ROOT / col
        if not coldir.is_dir():
            continue
        n = 0
        for p in sorted(coldir.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---", text, re.S)
            if not m:
                continue
            fm = m.group(1)
            # English entries only — Phase A is English-corpus first
            lang = extract_fm_field(fm, "language") or "en"
            if lang != "en":
                continue
            if has_nonempty_ref(fm, ref_fields):
                continue
            slug = p.stem
            rec = {
                "id": slug,
                "collection": col,
                "slug": slug,
                "title": title_of(fm, slug),
                "body_excerpt": md_body_excerpt(text),
                "current_author_hint": author_or_subject_hint(fm) or None,
                "expected_role": expected_role,
            }
            if col == "primary-works":
                bv = collect_primary_works_byline(slug)
                if bv:
                    rec["byline_verbatim"] = bv
            records.append(rec)
            n += 1
            if args.limit and len(records) >= args.limit:
                break
        per_col[col] = n
        if args.limit and len(records) >= args.limit:
            break

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[prepare] wrote {OUT_PATH.relative_to(ROOT)} — {len(records)} entries")
    for col, n in per_col.items():
        print(f"  {col:18}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
