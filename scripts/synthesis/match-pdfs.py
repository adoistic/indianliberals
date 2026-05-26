#!/usr/bin/env python3
"""
match-pdfs.py — offline matcher joining prod inventory with primary-works MDs.

Reads:
    data/prod-mirror/inventory.jsonl
    apps/site/src/content/primary-works/*.md (381 MDs)

Writes:
    data/pdf-link-manifest.tsv     — matches sorted by confidence desc
    data/pdf-link-misses.tsv       — unmatched MDs with top-3 fuzzy candidates

Run:
    .venv-extract/bin/python3 scripts/synthesis/match-pdfs.py

Per the spec at docs/superpowers/specs/2026-05-26-pdf-link-reconciliation-design.md.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from rapidfuzz import fuzz, process

# Local sibling import.
_LIB = Path(__file__).resolve().parent / "pdf_match_lib.py"
spec = importlib.util.spec_from_file_location("pdf_match_lib", str(_LIB))
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)

REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
INVENTORY = REPO_ROOT / "data" / "prod-mirror" / "inventory.jsonl"
MANIFEST = REPO_ROOT / "data" / "pdf-link-manifest.tsv"
MISSES = REPO_ROOT / "data" / "pdf-link-misses.tsv"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)

CONFIDENCE_ORDER = {"exact": 0, "high": 1, "medium": 2, "page-only": 3}


def load_md(md_path: Path) -> dict | None:
    """Parse a primary-works MD; return {id, title_main, year, first_author_slug} or None."""
    text = md_path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm = yaml.safe_load(m.group(1)) or {}
    title_block = fm.get("title", {})
    title_main = title_block.get("main") if isinstance(title_block, dict) else ""
    pub = fm.get("publication", {}) or {}
    year = pub.get("year") if isinstance(pub.get("year"), int) else None
    authors = fm.get("authors") or []
    # Authors entries may be plain strings (slugs) or {id: ..., collection: ...} refs.
    first = ""
    if authors:
        a0 = authors[0]
        first = a0 if isinstance(a0, str) else (a0.get("id") if isinstance(a0, dict) else "")
    return {
        "id": fm.get("id") or md_path.stem,
        "title_main": title_main or "",
        "year": year,
        "first_author_slug": first or "",
    }


def load_inventory() -> list[dict]:
    out = []
    if not INVENTORY.exists():
        return out
    with INVENTORY.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def match_one(md: dict, prod_index_by_slug: dict, all_prod: list[dict]) -> tuple[str | None, dict | None]:
    """Return (confidence_label, prod_row) or (None, None) for no match."""
    # Tier 1: exact slug.
    if md["id"] in prod_index_by_slug:
        prod = prod_index_by_slug[md["id"]]
        return (lib.tier_match(md, prod), prod)

    # Tiers 2/3 via fuzzy candidate ranking (only top-5 candidates inspected for speed).
    if md.get("year") is None:
        return (None, None)

    md_norm = lib.normalize_title(md["title_main"])
    if not md_norm:
        return (None, None)

    # Candidate set: prod rows whose year_string contains md.year (cheap pre-filter).
    yr = str(md["year"])
    candidates = [p for p in all_prod if yr in (p.get("year_string") or "")]
    if not candidates:
        return (None, None)

    # Rank by token_set_ratio, top 5.
    scored = process.extract(
        md_norm,
        {i: lib.normalize_title(p["page_title"]) for i, p in enumerate(candidates)},
        scorer=fuzz.token_set_ratio,
        limit=5,
    )

    for normalized_title, score, idx in scored:
        prod = candidates[idx]
        label = lib.tier_match(md, prod)
        if label in ("high", "medium"):
            return (label, prod)

    return (None, None)


def find_misses_candidates(md: dict, all_prod: list[dict], top_k: int = 3) -> list[tuple[str, int]]:
    """Return [(prod_slug, score), …] top_k by raw title similarity (no year filter)."""
    md_norm = lib.normalize_title(md["title_main"])
    if not md_norm or not all_prod:
        return []
    titles = {p["prod_slug"]: lib.normalize_title(p["page_title"]) for p in all_prod}
    scored = process.extract(md_norm, titles, scorer=fuzz.token_set_ratio, limit=top_k)
    # scored entries are (matched_string, score, key)
    return [(key, int(score)) for (_str, score, key) in scored]


def main() -> int:
    if not INVENTORY.exists():
        print(f"missing {INVENTORY}; run scrape-prod.py first", file=sys.stderr)
        return 2

    inv = load_inventory()
    print(f"inventory: {len(inv)} rows")

    # Build prod_slug -> row index (last write wins for accidental dupes).
    prod_index = {row["prod_slug"]: row for row in inv}

    # Reverse-collision check.
    rev = defaultdict(list)
    for row in inv:
        rev[row["prod_slug"]].append(row)
    for slug, rows in rev.items():
        if len(rows) > 1:
            print(f"  [warn] {len(rows)} inventory rows share prod_slug={slug}", file=sys.stderr)

    md_files = sorted(PW_DIR.glob("*.md"))
    print(f"primary-works: {len(md_files)} MDs")

    counts = defaultdict(int)
    manifest_rows: list[dict] = []
    miss_rows: list[dict] = []
    used_prod_slugs: dict[str, str] = {}  # detect MDs colliding on same prod page

    for md_path in md_files:
        md = load_md(md_path)
        if md is None:
            print(f"  [skip-no-frontmatter] {md_path.name}", file=sys.stderr)
            continue

        label, prod = match_one(md, prod_index, inv)
        if label is None:
            counts["miss"] += 1
            candidates = find_misses_candidates(md, inv)
            miss_rows.append({
                "md_slug": md["id"],
                "md_title": md["title_main"],
                "md_year": md["year"] or "",
                "md_first_author": md["first_author_slug"],
                "candidates": candidates,
            })
            continue

        counts[label] += 1
        # Reverse-collision: same prod slug claimed by another MD.
        prev_md = used_prod_slugs.get(prod["prod_slug"])
        notes = ""
        if prev_md and prev_md != md["id"]:
            notes = f"DUPLICATE: also matched by {prev_md}"
        else:
            used_prod_slugs[prod["prod_slug"]] = md["id"]
        manifest_rows.append({
            "md_slug": md["id"],
            "confidence": label,
            "prod_slug": prod["prod_slug"],
            "pdf_url": prod.get("pdf_url") or "",
            "md_title": md["title_main"],
            "prod_title": prod.get("page_title") or "",
            "notes": notes,
        })

    # Sort manifest by (confidence priority, md_slug).
    manifest_rows.sort(key=lambda r: (CONFIDENCE_ORDER.get(r["confidence"], 9), r["md_slug"]))
    miss_rows.sort(key=lambda r: r["md_slug"])

    # Write manifest.
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8") as fh:
        fh.write("md_slug\tconfidence\tprod_slug\tpdf_url\tmd_title\tprod_title\tnotes\n")
        for r in manifest_rows:
            fh.write("\t".join([
                r["md_slug"], r["confidence"], r["prod_slug"], r["pdf_url"],
                r["md_title"].replace("\t", " "), r["prod_title"].replace("\t", " "),
                r["notes"],
            ]) + "\n")

    # Write misses.
    with MISSES.open("w", encoding="utf-8") as fh:
        fh.write("md_slug\tmd_title\tmd_year\tmd_first_author\ttop1_prod_slug\ttop1_score\ttop2_prod_slug\ttop2_score\ttop3_prod_slug\ttop3_score\n")
        for r in miss_rows:
            cands = r["candidates"]
            cells = [
                r["md_slug"], r["md_title"].replace("\t", " "), str(r["md_year"]), r["md_first_author"],
            ]
            for i in range(3):
                if i < len(cands):
                    cells.extend([cands[i][0], str(cands[i][1])])
                else:
                    cells.extend(["", ""])
            fh.write("\t".join(cells) + "\n")

    print()
    print(f"match-pdfs: {counts['exact']} exact, {counts['high']} high, {counts['medium']} medium, {counts['page-only']} page-only, {counts['miss']} misses ({len(md_files)} total).")
    print(f"manifest.tsv: {len(manifest_rows)} rows ({MANIFEST})")
    print(f"misses.tsv: {len(miss_rows)} rows ({MISSES})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
