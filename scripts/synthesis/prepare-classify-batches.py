#!/usr/bin/env python3
"""
Step 2: prepare batch inputs for the classification pass.

Writes data/classify/batch-NN.jsonl files, one JSON record per line. Each
record carries one piece's metadata + body excerpt for a single Agent
subagent to classify.

Resolves musings' source years via excerpt_of → primary-works lookup
when available.

Run:
    .venv-extract/bin/python3 scripts/synthesis/prepare-classify-batches.py
    .venv-extract/bin/python3 scripts/synthesis/prepare-classify-batches.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
PW_DIR = CONTENT_ROOT / "primary-works"
OUT_DIR = ROOT / "data/classify"
N_BATCHES = 10
MAX_BODY_CHARS = 3000

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_TITLE_RX = re.compile(r"^title:\s*\"([^\"]+)\"", re.M)
_PUBDATE_RX = re.compile(r"^pubDate:\s*\"(\d{4})", re.M)
_DRAFT_RX = re.compile(r"^draft:\s*(true|false)", re.M)
_AUTHOR_RX = re.compile(r"^author:\s*\"([^\"]+)\"", re.M)
_SUBJECT_RX = re.compile(r"^subject:\s*\"([^\"]+)\"", re.M)
_EXCERPT_OF_RX = re.compile(r"^excerpt_of:\s*\"([^\"]+)\"", re.M)


def parse_frontmatter(path: Path) -> tuple[dict, str] | None:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm, body = m.group(1), m.group(2)
    out: dict = {}
    title = _TITLE_RX.search(fm)
    out["title"] = title.group(1) if title else ""
    pubdate = _PUBDATE_RX.search(fm)
    out["pub_year"] = int(pubdate.group(1)) if pubdate else None
    draft = _DRAFT_RX.search(fm)
    out["draft"] = draft.group(1) == "true" if draft else False
    author = _AUTHOR_RX.search(fm)
    out["author"] = author.group(1) if author else None
    subject = _SUBJECT_RX.search(fm)
    out["subject"] = subject.group(1) if subject else None
    excerpt_of = _EXCERPT_OF_RX.search(fm)
    out["excerpt_of"] = excerpt_of.group(1) if excerpt_of else None
    return out, body.strip()


def primary_work_year(pw_id: str) -> int | None:
    """Resolve a primary-work id to its publication.year via frontmatter scan."""
    path = PW_DIR / f"{pw_id}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm = m.group(1)
    # publication block is nested; capture the year line under it.
    pub_block = re.search(r"^publication:\s*\n((?:[ \t]+.*\n)+)", fm, re.M)
    if not pub_block:
        return None
    yr = re.search(r"^[ \t]+year:\s*(\d{4})", pub_block.group(1), re.M)
    return int(yr.group(1)) if yr else None


def truncate_body(body: str, n: int) -> str:
    """Truncate at the nearest paragraph boundary at or before n chars."""
    if len(body) <= n:
        return body
    cut = body.rfind("\n\n", 0, n)
    if cut < 0:
        cut = body.rfind("\n", 0, n)
    if cut < 0:
        cut = n
    return body[:cut].rstrip()


def build_record(md: Path, collection: str) -> dict | None:
    parsed = parse_frontmatter(md)
    if not parsed:
        return None
    fm, body = parsed
    if fm["draft"]:
        return None
    rec: dict = {
        "id": md.stem,
        "collection": collection,
        "title": fm["title"],
    }
    pub_year = fm["pub_year"]
    if collection == "musings" and fm.get("excerpt_of"):
        src_year = primary_work_year(fm["excerpt_of"])
        rec["year_hint"] = src_year or pub_year
    else:
        rec["year_hint"] = pub_year
    rec["body_excerpt"] = truncate_body(body, MAX_BODY_CHARS)
    ctx = {}
    if fm.get("author"):
        ctx["author"] = fm["author"]
    if fm.get("subject"):
        ctx["subject"] = fm["subject"]
    if fm.get("excerpt_of"):
        ctx["excerpt_of"] = fm["excerpt_of"]
    rec["context"] = ctx
    return rec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    records: list[dict] = []
    for collection in ("musings", "opinions"):
        coll_dir = CONTENT_ROOT / collection
        for md in sorted(coll_dir.glob("*.md")):
            rec = build_record(md, collection)
            if rec is not None:
                records.append(rec)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Existing batch files: wipe before regenerate (re-runs should be reproducible)
    for stale in OUT_DIR.glob("batch-*.jsonl"):
        stale.unlink()

    per_batch = (len(records) + N_BATCHES - 1) // N_BATCHES
    for i in range(N_BATCHES):
        chunk = records[i * per_batch : (i + 1) * per_batch]
        if not chunk:
            continue
        out_path = OUT_DIR / f"batch-{i:02d}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for r in chunk:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"wrote {out_path.relative_to(ROOT)}  ({len(chunk)} records)")

    print(f"total {len(records)} records across {N_BATCHES} batches")
    return 0


def _run_tests():
    # Body truncation
    assert truncate_body("aaa\n\nbbb\n\nccc", 100) == "aaa\n\nbbb\n\nccc"
    assert truncate_body("aaa\n\nbbb\n\nccc", 5) == "aaa"
    long = "para1\n\n" + ("x" * 5000) + "\n\npara3"
    out = truncate_body(long, 3000)
    assert len(out) <= 3000
    assert out.endswith("x") or out == "para1"  # paragraph boundary respected

    print("prepare-classify-batches tests passed.")


if __name__ == "__main__":
    sys.exit(main())
