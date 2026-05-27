#!/usr/bin/env python3
"""
audit-thinkers-without-quotes.py — corpus-wide audit of pull-quote attribution.

Builds an inverted index from each thinker MD's slug to the count of inbound
thinker_mentions[].evidence[].quote entries across the corpus (primary-works,
opinions, musings, interviews, theprint-mirror). Surfaces thinkers with zero
inbound quotes, sorted by canon_status (canonical > referenced > stub > other)
so canonical thinkers without quote-coverage rise to the top.

Reads:
  apps/site/src/content/thinkers/*.md
  apps/site/src/content/{primary-works,opinions,musings,interviews,theprint-mirror}/*.md

Writes:
  stdout report (captured into docs/handoffs/2026-05-27-content-readiness-pass-1.md).

Run:
  .venv-extract/bin/python3 scripts/synthesis/audit-thinkers-without-quotes.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = REPO_ROOT / "apps" / "site" / "src" / "content"
THINKERS_DIR = CONTENT_ROOT / "thinkers"
IN_SCOPE = ("primary-works", "opinions", "musings", "interviews", "theprint-mirror")

CANON_PRIORITY = {"canonical": 0, "referenced": 1, "stub": 2}

_FM_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def _extract_mentions(md_text: str) -> list[tuple[str, int]]:
    """Parse one MD's frontmatter; return list of (thinker_slug, quote_count) tuples.

    quote_count is the number of non-empty `evidence[].quote` strings under that mention.
    A mention with empty/missing evidence contributes 0 quotes (the mention exists, but
    isn't quote-attributed — different signal).
    """
    m = _FM_RX.match(md_text)
    if not m:
        return []
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return []
    mentions = fm.get("thinker_mentions") or []
    if not isinstance(mentions, list):
        return []
    out: list[tuple[str, int]] = []
    for entry in mentions:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("thinker")
        if not isinstance(slug, str) or not slug:
            continue
        evidence = entry.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        qcount = sum(
            1 for ev in evidence
            if isinstance(ev, dict)
            and isinstance(ev.get("quote"), str)
            and ev["quote"].strip()
        )
        out.append((slug, qcount))
    return out


def _build_inverted_index(md_paths: list[Path]) -> Counter:
    """Return Counter mapping thinker_slug → total inbound evidence-quote count."""
    idx: Counter = Counter()
    skipped = 0
    for p in md_paths:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped += 1
            continue
        for slug, qcount in _extract_mentions(text):
            idx[slug] += qcount
    if skipped:
        print(f"Warning: skipped {skipped} unreadable MD(s)", file=sys.stderr)
    return idx


def _load_thinker_canon(thinkers_dir: Path) -> dict[str, dict]:
    """Return slug → {canon_status, canonical_name} for every thinker MD."""
    out: dict[str, dict] = {}
    for md in sorted(thinkers_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FM_RX.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        slug = fm.get("id") or md.stem
        out[slug] = {
            "canon_status": fm.get("canon_status") or "unknown",
            "canonical_name": ((fm.get("name") or {}).get("canonical") or "").strip(),
        }
    return out


def _format_report(canon: dict[str, dict], inverted: Counter) -> str:
    """Compose the stdout report. Returns a single string for testability."""
    total_thinkers = len(canon)
    with_quotes = sum(1 for slug in canon if inverted.get(slug, 0) > 0)
    without_quotes = total_thinkers - with_quotes

    lines: list[str] = []
    lines.append("=== Thinkers without inbound pull-quote attribution ===")
    lines.append(f"Total thinker files: {total_thinkers}")
    lines.append(f"Thinkers with ≥1 quote: {with_quotes}")
    lines.append(f"Thinkers with 0 quotes: {without_quotes}")
    lines.append("")
    lines.append("Caveat: ~58% of the corpus lacks any thinker_mentions because the")
    lines.append("NER pipeline hasn't been run on the recent extraction-pipeline output.")
    lines.append("This number will drop sharply after the post-batch NER run.")
    lines.append("")
    lines.append("Broken down by canon_status:")
    status_counter: dict[str, dict[str, int]] = {}
    for slug, info in canon.items():
        st = info["canon_status"]
        bucket = status_counter.setdefault(st, {"with": 0, "without": 0})
        if inverted.get(slug, 0) > 0:
            bucket["with"] += 1
        else:
            bucket["without"] += 1
    for st in sorted(status_counter, key=lambda s: CANON_PRIORITY.get(s, 99)):
        b = status_counter[st]
        lines.append(f"  {st:<12} — {b['with']} with quotes, {b['without']} without")
    lines.append("")

    def _section(title: str, status: str):
        lines.append(f"=== {title} ===")
        zeros = sorted(
            slug for slug in canon
            if canon[slug]["canon_status"] == status and inverted.get(slug, 0) == 0
        )
        for slug in zeros:
            lines.append(f"  {slug}  ({canon[slug]['canonical_name']})")
        if not zeros:
            lines.append("  (none)")
        lines.append("")

    _section("Canonical thinkers with zero quotes", "canonical")
    _section("Referenced thinkers with zero quotes", "referenced")

    return "\n".join(lines)


def main() -> int:
    canon = _load_thinker_canon(THINKERS_DIR)
    md_paths: list[Path] = []
    for sub in IN_SCOPE:
        md_paths.extend(sorted((CONTENT_ROOT / sub).glob("*.md")))
    inverted = _build_inverted_index(md_paths)
    print(_format_report(canon, inverted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
