#!/usr/bin/env python3
"""
Render scripts/synthesis/prompts/system-classify-thinkers.txt from
the rubric prose and 8 anchor examples.

Re-run whenever the rubric or anchor file changes.

Run from repo root:
    python3 scripts/synthesis/render-system-classify-thinkers.py

Refs docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md §8
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "scripts/synthesis/prompts"
RUBRICS = PROMPTS_DIR / "classify-thinkers-rubrics.txt"
ANCHORS = PROMPTS_DIR / "classify-thinkers-anchors.json"
OUT = PROMPTS_DIR / "system-classify-thinkers.txt"

PREAMBLE = """You are classifying figures in the Indian liberal-tradition archive at indianliberals.in along three independent dimensions. Each input record is one thinker (person or institution-as-figure). Return ONE JSON object per thinker; the output for a batch is a top-level JSON array of those objects.

The three dimensions are independent — any combination is editorially valid. Classify each dimension on its own merits. Do not infer one from another."""

OUTPUT_FORMAT_SPEC = """# Output format

Return a JSON array. Each element is one classification object with this exact shape:

{
  "id": string (echo input id),
  "canon_status": "core" | "extended" | "referenced" | "unclassified",
  "tradition": one of [classical_liberal, libertarian, constitutional_liberal,
    contemporary_liberal, social_reformer, non_liberal, practice, unclassified],
  "vocations": array of strings from the closed enum (see vocations rubric),
  "confidence": {"canon_status": "high|medium|low", "tradition": "...", "vocations": "..."},
  "reasoning": string (50-200 words, one paragraph)
}

DO NOT output `tradition: international_influence` — deprecated value; forbidden.

Output the array AS THE ENTIRE RESPONSE, no preamble or postamble text. The
applier will JSON-parse your response directly."""


def main() -> int:
    rubrics_text = RUBRICS.read_text(encoding="utf-8")
    anchors = json.loads(ANCHORS.read_text(encoding="utf-8"))

    parts: list[str] = [PREAMBLE, "", rubrics_text, "", "# Worked examples", ""]

    for i, a in enumerate(anchors, start=1):
        parts.append(f"## Example {i} — {a['id']}")
        parts.append("")
        parts.append("Expected output (note the per-axis confidence):")
        parts.append("```json")
        out = {
            "id": a["id"],
            "canon_status": a["expected"]["canon_status"],
            "tradition": a["expected"]["tradition"],
            "vocations": a["expected"]["vocations"],
            "confidence": a["expected"]["confidence"],
            "reasoning": a["reasoning"],
        }
        parts.append(json.dumps(out, indent=2))
        parts.append("```")
        parts.append("")

    parts.append(OUTPUT_FORMAT_SPEC)

    rendered = "\n".join(parts)
    OUT.write_text(rendered + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rendered)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
