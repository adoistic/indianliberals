#!/usr/bin/env python3
"""
Step 5: emit data/byline-resolve/coverage-report.md and curator-queue.md.

coverage-report.md: aggregate counts (total bylined, method breakdown,
confidence breakdown, stub counts, collision counts).

curator-queue.md: flat actionable list of primary-works whose post-apply
state satisfies any of:
  - authors_resolution.method == 'vision'
  - confidence != 'high'
  - stubs_created non-empty
  - collisions_logged non-empty
  - no authors resolved (genuinely unresolved)

Run:
    .venv-extract/bin/python3 scripts/synthesis/audit-byline-coverage.py
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW_DIR = ROOT / "apps/site/src/content/primary-works"
OUT_REPORT = ROOT / "data/byline-resolve/coverage-report.md"
OUT_QUEUE = ROOT / "data/byline-resolve/curator-queue.md"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)


def parse(md: Path) -> dict:
    text = md.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return {}
    fm = m.group(1)
    out: dict = {"id": md.stem}
    authors_m = re.search(r"^authors:\s*(\[\]|(?:\n\s+-\s+.+)+)", fm, re.M)
    out["has_authors"] = bool(authors_m and authors_m.group(1).strip() != "[]")
    res_m = re.search(r"^authors_resolution:\s*\n((?:\s+.+\n?)+)", fm, re.M)
    res_block = res_m.group(1) if res_m else ""
    out["confidence"] = (
        re.search(r"^\s+confidence:\s*(\S+)", res_block, re.M).group(1)
        if re.search(r"^\s+confidence:", res_block, re.M)
        else None
    )
    out["method"] = (
        re.search(r"^\s+method:\s*(\S+)", res_block, re.M).group(1)
        if re.search(r"^\s+method:", res_block, re.M)
        else None
    )
    out["stubs_created"] = bool(
        re.search(r"^\s+stubs_created:\s*\n\s+-", res_block, re.M)
    )
    out["collisions_logged"] = bool(
        re.search(r"^\s+collisions_logged:\s*\n\s+-", res_block, re.M)
    )
    out["needs_review"] = bool(re.search(r"^needs_review:\s*true", fm, re.M))
    return out


def main() -> int:
    entries = [parse(md) for md in sorted(PW_DIR.glob("*.md"))]
    total = len(entries)
    bylined = sum(1 for e in entries if e.get("has_authors"))
    by_method = Counter(e["method"] for e in entries if e.get("method"))
    by_confidence = Counter(e["confidence"] for e in entries if e.get("confidence"))
    stubs = sum(1 for e in entries if e.get("stubs_created"))
    collisions = sum(1 for e in entries if e.get("collisions_logged"))

    lines = [
        "# Byline Resolution Coverage Report",
        "",
        f"Total primary-works: {total}",
        f"With `authors[]` populated: {bylined}/{total} ({bylined*100//total}%)",
        "",
        "## Method breakdown (entries where a resolution ran)",
        "",
    ]
    for m, n in by_method.most_common():
        lines.append(f"- {m}: {n}")
    lines.extend(["", "## Confidence breakdown", ""])
    for c, n in by_confidence.most_common():
        lines.append(f"- {c}: {n}")
    lines.extend([
        "",
        f"## Stubs created (entries with new stub thinkers): {stubs}",
        f"## Collisions logged (silent existing-thinker hits): {collisions}",
        "",
    ])
    OUT_REPORT.write_text("\n".join(lines))
    print(f"wrote {OUT_REPORT.relative_to(ROOT)}")

    # Curator queue
    queue = [
        e for e in entries
        if e.get("method") == "vision"
        or (e.get("confidence") and e["confidence"] != "high")
        or e.get("stubs_created")
        or e.get("collisions_logged")
        or (e.get("method") and not e.get("has_authors"))
    ]
    q_lines = [
        "# Curator Review Queue (post-byline-resolution)",
        "",
        f"Total entries needing review: {len(queue)}",
        "",
        "| id | method | confidence | stubs | collisions |",
        "|---|---|---|---|---|",
    ]
    for e in queue:
        q_lines.append(
            f"| `{e['id']}` | {e.get('method') or ''} | {e.get('confidence') or ''} | "
            f"{'✓' if e.get('stubs_created') else ''} | "
            f"{'✓' if e.get('collisions_logged') else ''} |"
        )
    OUT_QUEUE.write_text("\n".join(q_lines) + "\n")
    print(f"wrote {OUT_QUEUE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
