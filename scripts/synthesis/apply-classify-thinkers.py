#!/usr/bin/env python3
"""
Apply AI classification outputs to thinker MDs per the spec §7 confidence rule.

  high confidence on axis  → write the AI value to frontmatter
  medium                   → write + set needs_review: true on the record
  low                      → DO NOT write that axis; leave at default;
                             set needs_review: true on the record

Also append the AI's reasoning paragraph to
data/classify-thinkers/reasoning-log.md keyed by thinker id.

The applier touches ONLY canon_status, tradition, vocations, and
needs_review on the thinker MD. All other frontmatter fields are
left untouched.

Output-stable rather than purely idempotent: re-running with the same
outputs produces zero file changes IF no curator edit has happened in
between. But: if a curator cleared needs_review: false between runs
and the AI output still has any medium/low axis, the re-run re-sets
needs_review: true. This is intentional (spec §7.2).

Modes:
  --dry-run    Print what WOULD be modified; touch no files.
  --pilot      Apply data/classify-thinkers/pilot-output.json instead of
               the bulk outputs (uses pilot-batch.jsonl for id validation).
  (default)    Live run: write to MDs + append reasoning log.

Run from repo root:
    python3 scripts/synthesis/apply-classify-thinkers.py --dry-run
    python3 scripts/synthesis/apply-classify-thinkers.py
    python3 scripts/synthesis/apply-classify-thinkers.py --pilot
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Schema validation
sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_thinkers_schema import (
    CANON_STATUS_VALUES, TRADITION_VALUES, VOCATIONS_VALUES, CONFIDENCE_VALUES,
    validate_record,
)

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
DATA_DIR = ROOT / "data/classify-thinkers"
REASONING_LOG = DATA_DIR / "reasoning-log.md"

# Regexes for replacing or inserting the four touched fields.
_CANON_STATUS_LINE_RX = re.compile(r"^canon_status:.*$", re.MULTILINE)
_TRADITION_LINE_RX = re.compile(r"^tradition:.*$", re.MULTILINE)
# Flow-style vocations on one line
_VOCATIONS_LINE_RX = re.compile(r"^vocations:.*$", re.MULTILINE)
# Block-style: `vocations:\n  - foo\n  - bar\n` — match up to next top-level key
# (a line starting at column 0 with a non-space, non-dash character) or EOF.
_VOCATIONS_BLOCK_RX = re.compile(
    r"^vocations:[ \t]*\n(?:[ \t]+-[^\n]*\n?)+",
    re.MULTILINE,
)
_NEEDS_REVIEW_RX = re.compile(r"^needs_review:\s*(true|false)\s*$", re.MULTILINE)
_DRAFT_LINE_RX = re.compile(r"^draft:.*$", re.MULTILINE)


def replace_canon_status(text: str, new_value: str) -> str:
    """Replace the `canon_status:` frontmatter line with `canon_status: <new_value>`."""
    return _CANON_STATUS_LINE_RX.sub(f"canon_status: {new_value}", text, count=1)


def replace_tradition(text: str, new_value: str) -> str:
    """Replace the `tradition:` frontmatter line with `tradition: <new_value>`."""
    return _TRADITION_LINE_RX.sub(f"tradition: {new_value}", text, count=1)


def replace_vocations(text: str, new_list: list[str]) -> str:
    """Replace the `vocations:` frontmatter line with a flow-style list.

    Non-empty:  `vocations: [a, b, c]`  (space after comma, no trailing space)
    Empty:      `vocations: []`

    Handles both the standard flow-style single line AND a defensive block-style
    multi-line form (`vocations:\\n  - foo\\n  - bar\\n`) — every current MD is
    flow-style but the block form is matched first to avoid leaving orphan items
    if someone hand-edited.
    """
    if new_list:
        replacement = f"vocations: [{', '.join(new_list)}]"
    else:
        replacement = "vocations: []"

    # Try block-style first (greedier match); fall through to flow-style.
    new_text, n = _VOCATIONS_BLOCK_RX.subn(replacement + "\n", text, count=1)
    if n > 0:
        return new_text
    return _VOCATIONS_LINE_RX.sub(replacement, text, count=1)


def set_needs_review_true(text: str) -> str:
    """Set `needs_review: true`. If the line exists, replace it. Otherwise insert
    immediately before the `draft:` line."""
    if _NEEDS_REVIEW_RX.search(text):
        return _NEEDS_REVIEW_RX.sub("needs_review: true", text, count=1)

    # Insert before the draft: line (rare path; thinker schema requires both).
    m = _DRAFT_LINE_RX.search(text)
    if m:
        insertion = "needs_review: true\n"
        return text[:m.start()] + insertion + text[m.start():]

    # No draft line either — append at end of frontmatter (defensive fallback).
    # Find the closing `---` of frontmatter.
    fm_end = text.find("\n---", text.find("---") + 3)
    if fm_end != -1:
        return text[:fm_end] + "\nneeds_review: true" + text[fm_end:]
    return text  # give up; shouldn't happen on a real thinker MD


def apply_record_to_text(text: str, rec: dict) -> tuple[str, set[str], bool]:
    """Apply one validated output record to a thinker MD's text.

    Returns (new_text, written_axes, set_needs_review):
      - new_text: text after all confidence-rule replacements + needs_review flip
      - written_axes: set of axis names ('canon_status', 'tradition', 'vocations')
        whose values were written
      - set_needs_review: True iff any axis was medium or low (and so
        needs_review was set to true)
    """
    written: set[str] = set()
    any_below_high = False

    cs_conf = rec["confidence"]["canon_status"]
    if cs_conf == "high":
        text = replace_canon_status(text, rec["canon_status"])
        written.add("canon_status")
    elif cs_conf == "medium":
        text = replace_canon_status(text, rec["canon_status"])
        written.add("canon_status")
        any_below_high = True
    else:  # low
        any_below_high = True

    tr_conf = rec["confidence"]["tradition"]
    if tr_conf == "high":
        text = replace_tradition(text, rec["tradition"])
        written.add("tradition")
    elif tr_conf == "medium":
        text = replace_tradition(text, rec["tradition"])
        written.add("tradition")
        any_below_high = True
    else:
        any_below_high = True

    voc_conf = rec["confidence"]["vocations"]
    if voc_conf == "high":
        text = replace_vocations(text, rec["vocations"])
        written.add("vocations")
    elif voc_conf == "medium":
        text = replace_vocations(text, rec["vocations"])
        written.add("vocations")
        any_below_high = True
    else:
        any_below_high = True

    if any_below_high:
        text = set_needs_review_true(text)

    return text, written, any_below_high


def _format_log_chunk(rec, written, set_review):
    cs_conf = rec["confidence"]["canon_status"]
    tr_conf = rec["confidence"]["tradition"]
    voc_conf = rec["confidence"]["vocations"]
    result = f"{rec['canon_status']} / {rec['tradition']} / {rec['vocations']}"
    written_str = ", ".join(sorted(written)) if written else "none"
    review_str = "needs_review=true" if set_review else "needs_review unchanged"
    return (
        f"## {rec['id']}\n\n"
        f"**Confidence:** canon_status={cs_conf}, tradition={tr_conf}, vocations={voc_conf}\n"
        f"**Result:** {result} — written axes: {written_str}; {review_str}\n\n"
        f"> {rec['reasoning']}\n\n"
        f"---\n\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print would-be changes; touch no files")
    ap.add_argument("--pilot", action="store_true",
                    help="apply data/classify-thinkers/pilot-output.json instead of the 10 bulk outputs")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)  # ensure reasoning-log destination exists

    if args.pilot:
        output_files = [DATA_DIR / "pilot-output.json"]
        batch_files = [DATA_DIR / "pilot-batch.jsonl"]
    else:
        output_files = sorted(DATA_DIR.glob("output-*.json"))
        batch_files = sorted(DATA_DIR.glob("batch-*.jsonl"))

    if args.pilot and not output_files[0].exists():
        print(f"ERROR: pilot output missing: {output_files[0]}", file=sys.stderr)
        return 1
    if not args.pilot and not output_files:
        print(f"ERROR: no output-*.json files in {DATA_DIR}", file=sys.stderr)
        return 1

    missing_batches = [str(bf) for bf in batch_files if not bf.exists()]
    if missing_batches:
        print(
            f"ERROR: missing batch file(s) (required to validate output ids): {', '.join(missing_batches)}",
            file=sys.stderr,
        )
        return 1

    # Build the set of valid input IDs (union of all batch JSONLs) for schema validation
    input_ids: set[str] = set()
    for bf in batch_files:
        for line in bf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                input_ids.add(rec["id"])

    # Process each output file's records, applying to MDs per the confidence rule
    n_written = n_review_set = n_rejected = 0
    rejected_log_lines: list[str] = []
    log_chunks: list[str] = []

    for of in output_files:
        records = json.loads(of.read_text(encoding="utf-8"))
        for rec in records:
            ok, errs = validate_record(rec, input_ids)
            if not ok:
                n_rejected += 1
                rejected_log_lines.append(f"REJECT {rec.get('id', '?')}: {'; '.join(errs)}")
                continue

            md_path = THINKERS_DIR / f"{rec['id']}.md"
            if not md_path.exists():
                n_rejected += 1
                rejected_log_lines.append(f"REJECT {rec['id']}: thinker MD does not exist at {md_path}")
                continue

            original = md_path.read_text(encoding="utf-8")
            new_text, written, set_review = apply_record_to_text(original, rec)

            if new_text != original:
                n_written += 1
                if not args.dry_run:
                    md_path.write_text(new_text, encoding="utf-8")
            if set_review:
                n_review_set += 1

            log_chunks.append(_format_log_chunk(rec, written, set_review))

    # Emit rejected records to stderr
    for line in rejected_log_lines:
        print(line, file=sys.stderr)

    # Append the reasoning log (skip on dry-run)
    if not args.dry_run and log_chunks:
        with REASONING_LOG.open("a", encoding="utf-8") as f:
            for chunk in log_chunks:
                f.write(chunk)

    mode = "dry-run: would " if args.dry_run else ""
    print(f"{mode}modify {n_written} thinker MDs; needs_review set on {n_review_set}; rejected {n_rejected}")
    return 0 if n_rejected == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
