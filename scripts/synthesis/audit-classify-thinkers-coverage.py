#!/usr/bin/env python3
"""
Step 6: post-run coverage report for the thinkers AI-bulk-classifier.

Reads all thinker MDs + the reasoning log, emits
data/classify-thinkers/coverage-report.md with:

- Per-canon_status count (core / extended / referenced / unclassified)
- Per-tradition count (8 allowed values + flagged international_influence remainder)
- Per-vocation count (top 30 most-used)
- Per-confidence breakdown (read from reasoning-log.md)
- List of needs_review: true thinker IDs (the curator triage queue)

Run from repo root:
    python3 scripts/synthesis/audit-classify-thinkers-coverage.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
DATA_DIR = ROOT / "data/classify-thinkers"
REASONING_LOG = DATA_DIR / "reasoning-log.md"
OUT = DATA_DIR / "coverage-report.md"

_CANON_STATUS_RX = re.compile(r"^canon_status:\s*(\S+)\s*$", re.MULTILINE)
_TRADITION_RX = re.compile(r"^tradition:\s*(\S+)\s*$", re.MULTILINE)
_VOCATIONS_RX = re.compile(r"^vocations:\s*\[([^\]]*)\]\s*$", re.MULTILINE)
_NEEDS_REVIEW_RX = re.compile(r"^needs_review:\s*(true|false)\s*$", re.MULTILINE)
_DRAFT_RX = re.compile(r"^draft:\s*(true|false)\s*$", re.MULTILINE)


def main() -> int:
    files = sorted(THINKERS_DIR.glob("*.md"))
    cs_counter: Counter = Counter()
    tr_counter: Counter = Counter()
    voc_counter: Counter = Counter()
    needs_review_ids: list[str] = []
    n_total = 0
    n_draft = 0

    for f in files:
        text = f.read_text(encoding="utf-8")
        n_total += 1

        cs_m = _CANON_STATUS_RX.search(text)
        cs_counter[cs_m.group(1) if cs_m else "(missing)"] += 1

        tr_m = _TRADITION_RX.search(text)
        tr_counter[tr_m.group(1) if tr_m else "(missing)"] += 1

        voc_m = _VOCATIONS_RX.search(text)
        if voc_m:
            inner = voc_m.group(1).strip()
            if inner:
                for v in [x.strip() for x in inner.split(",")]:
                    if v:
                        voc_counter[v] += 1

        nr_m = _NEEDS_REVIEW_RX.search(text)
        if nr_m and nr_m.group(1) == "true":
            needs_review_ids.append(f.stem)

        d_m = _DRAFT_RX.search(text)
        if d_m and d_m.group(1) == "true":
            n_draft += 1

    # Confidence breakdown — parse reasoning-log.md if present.
    # The applier writes the log in APPEND mode (spec-prescribed: curators may
    # diff across runs), so re-applies accumulate duplicate `## <id>` sections.
    # Dedupe by thinker id, keeping the LATEST occurrence (most-recent confidence
    # call wins). Without this, the per-record confidence breakdown inflates
    # linearly with re-run count.
    conf_per_id: dict[str, tuple[str, str, str]] = {}
    if REASONING_LOG.exists():
        for chunk in REASONING_LOG.read_text(encoding="utf-8").split("\n---\n"):
            id_m = re.search(r"^## (\S+)", chunk, re.MULTILINE)
            # Format-coupled to apply-classify-thinkers.py:_format_log_chunk.
            # If that emitter changes its "**Confidence:**" line format, update here.
            conf_m = re.search(r"\*\*Confidence:\*\* canon_status=(\S+), tradition=(\S+), vocations=(\S+)", chunk)
            if id_m and conf_m:
                conf_per_id[id_m.group(1)] = (
                    conf_m.group(1).rstrip(","),
                    conf_m.group(2).rstrip(","),
                    conf_m.group(3).rstrip(","),
                )

    conf_counter: Counter = Counter()
    for vals in conf_per_id.values():
        if all(v == "high" for v in vals):
            conf_counter["all-high"] += 1
        elif any(v == "low" for v in vals):
            conf_counter["any-low"] += 1
        else:
            conf_counter["medium-mixed"] += 1

    lines = []
    lines.append("# Thinkers classification — coverage report")
    lines.append("")
    lines.append(f"Total thinker MDs: {n_total}")
    lines.append(f"  - draft (hidden): {n_draft}")
    lines.append(f"  - visible:        {n_total - n_draft}")
    lines.append("")
    lines.append("## By canon_status")
    lines.append("")
    for k in ("core", "extended", "referenced", "unclassified"):
        lines.append(f"- `{k}`: {cs_counter.get(k, 0)}")
    other_cs = sorted(k for k in cs_counter if k not in ("core", "extended", "referenced", "unclassified"))
    for k in other_cs:
        lines.append(f"- `{k}` (unexpected): {cs_counter[k]}")
    lines.append("")
    lines.append("## By tradition")
    lines.append("")
    expected_tr = (
        "classical_liberal", "libertarian", "constitutional_liberal", "contemporary_liberal",
        "social_reformer", "non_liberal", "practice", "unclassified",
    )
    for k in expected_tr:
        lines.append(f"- `{k}`: {tr_counter.get(k, 0)}")
    other_tr = sorted(k for k in tr_counter if k not in expected_tr)
    for k in other_tr:
        marker = " (DEPRECATED — sub-project 2's job to retire)" if k == "international_influence" else ""
        lines.append(f"- `{k}`{marker}: {tr_counter[k]}")
    lines.append("")
    lines.append("## By vocation (top entries)")
    lines.append("")
    for v, n in voc_counter.most_common(30):
        lines.append(f"- `{v}`: {n}")
    lines.append("")
    if conf_counter:
        lines.append("## By per-record confidence")
        lines.append("")
        for k in ("all-high", "medium-mixed", "any-low"):
            lines.append(f"- {k}: {conf_counter.get(k, 0)}")
        lines.append("")
    lines.append(f"## Curator triage queue ({len(needs_review_ids)} thinkers with needs_review: true)")
    lines.append("")
    for tid in needs_review_ids:
        lines.append(f"- {tid}")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  total: {n_total}, needs_review: {len(needs_review_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
