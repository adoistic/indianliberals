#!/usr/bin/env python3
"""
Pilot calibration tool for the thinkers AI-bulk-classifier pipeline.

Two modes:

  --bootstrap   Emit data/classify-thinkers/pilot-ground-truth.json with 30
                pre-selected thinker IDs (8 anchors + 22 curator-picked
                placeholders). Curator must edit the file to fill in
                canon_status / tradition / vocations per entry.

  --diff        Read pilot-ground-truth.json (curator-filled) and
                pilot-output.json (AI-produced), emit pilot-diff-report.md
                with per-axis agreement and a list of disagreements. Gates
                the bulk run on ≥80% per-axis agreement.

See spec §9.

Run from repo root:
    python3 scripts/synthesis/pilot-classify-thinkers.py --bootstrap
    python3 scripts/synthesis/pilot-classify-thinkers.py --diff
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/classify-thinkers"
GROUND_TRUTH = DATA_DIR / "pilot-ground-truth.json"
PILOT_OUTPUT = DATA_DIR / "pilot-output.json"
DIFF_REPORT = DATA_DIR / "pilot-diff-report.md"

# The 8 anchor example IDs from spec §8.1 item 6 + §9.1.
# These also appear as worked examples in the system prompt.
# MUST stay in sync with scripts/synthesis/prompts/classify-thinkers-anchors.json
# (same 8 slugs, same order). If you change one, change the other.
ANCHOR_IDS = [
    "f-a-hayek",
    "c-rajagopalachari",
    "dadabhai-naoroji",
    "raja-ram-mohan-roy",
    "jrd-tata",
    "h-r-khanna",
    "mukesh-ambani",
    "jawaharlal-nehru",
]

# 22 additional curator-picked IDs (placeholders — curator edits to actual slugs).
# Spec §9.1 says these should cover 5+ core, 5+ extended, 5+ referenced, a few
# unclassified, including at least one libertarian + one contemporary_liberal.
PLACEHOLDER_PICKS = [
    "PLACEHOLDER-core-classical-liberal-foreign-2",   # e.g., milton-friedman
    "PLACEHOLDER-core-libertarian",                   # e.g., a-mises or rothbard
    "PLACEHOLDER-core-contemporary-liberal",          # e.g., a contemporary Indian liberal commentator
    "PLACEHOLDER-core-constitutional-liberal-2",      # e.g., gopal-krishna-gokhale
    "PLACEHOLDER-core-social-reformer-2",             # e.g., b-r-ambedkar
    "PLACEHOLDER-extended-classical-liberal",
    "PLACEHOLDER-extended-constitutional-liberal-2",
    "PLACEHOLDER-extended-contemporary-liberal",
    "PLACEHOLDER-extended-social-reformer",
    "PLACEHOLDER-extended-practice-scientist",        # e.g., apj-abdul-kalam (if present)
    "PLACEHOLDER-referenced-non-liberal-marxist",
    "PLACEHOLDER-referenced-non-liberal-hindutva",
    "PLACEHOLDER-referenced-non-liberal-2",
    "PLACEHOLDER-referenced-practice-industrialist",  # e.g., ratan-tata
    "PLACEHOLDER-referenced-practice-2",
    "PLACEHOLDER-unclassified-cross-cutting-1",
    "PLACEHOLDER-unclassified-cross-cutting-2",
    "PLACEHOLDER-misc-1",
    "PLACEHOLDER-misc-2",
    "PLACEHOLDER-misc-3",
    "PLACEHOLDER-misc-4",
    "PLACEHOLDER-misc-5",
]


def _bootstrap() -> int:
    """Emit a template pilot-ground-truth.json file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if GROUND_TRUTH.exists():
        print(f"ERROR: {GROUND_TRUTH} already exists — refusing to overwrite. Move it aside if you want to regenerate.", file=sys.stderr)
        return 1

    entries = []
    for i, slug in enumerate(ANCHOR_IDS + PLACEHOLDER_PICKS):
        entries.append({
            "id": slug,
            "_note": "anchor (in prompt)" if i < len(ANCHOR_IDS) else "validation-only (NOT in prompt)",
            "canon_status": "FILL_IN",       # one of core / extended / referenced / unclassified
            "tradition": "FILL_IN",          # one of the 8 allowed values (NOT international_influence)
            "vocations": ["FILL_IN"],        # array of values from the 25-value enum
        })

    GROUND_TRUTH.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {GROUND_TRUTH}")
    print(f"  - {len(ANCHOR_IDS)} anchor IDs (already in prompt)")
    print(f"  - {len(PLACEHOLDER_PICKS)} placeholder IDs (curator should replace with actual slugs)")
    print("Next: edit the file to (a) replace PLACEHOLDER- slugs with real thinker IDs from")
    print("apps/site/src/content/thinkers/ and (b) fill in FILL_IN values per spec §9.1.")
    return 0


def _jaccard(a: list[str], b: list[str]) -> float:
    """Set-Jaccard similarity. Empty/empty returns 1.0; empty/non-empty returns 0.0."""
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)


def _diff() -> int:
    """Compute per-axis agreement between ground truth and AI output."""
    if not GROUND_TRUTH.exists():
        print(f"ERROR: {GROUND_TRUTH} missing. Run --bootstrap first.", file=sys.stderr)
        return 1
    if not PILOT_OUTPUT.exists():
        print(f"ERROR: {PILOT_OUTPUT} missing. Dispatch the pilot subagent first.", file=sys.stderr)
        return 1

    gt_list = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    ai_list = json.loads(PILOT_OUTPUT.read_text(encoding="utf-8"))

    gt_by_id = {r["id"]: r for r in gt_list}
    ai_by_id = {r["id"]: r for r in ai_list}

    # Restrict to IDs that exist in BOTH (the curator may have left placeholders empty)
    common_ids = sorted(set(gt_by_id) & set(ai_by_id))
    if not common_ids:
        print("ERROR: no common IDs between ground truth and AI output", file=sys.stderr)
        return 1

    # Reject ground-truth entries that still have FILL_IN values
    invalid_gt = [i for i in common_ids
                  if gt_by_id[i].get("canon_status") == "FILL_IN"
                  or gt_by_id[i].get("tradition") == "FILL_IN"
                  or "FILL_IN" in (gt_by_id[i].get("vocations") or [])]
    if invalid_gt:
        print(f"ERROR: ground-truth entries still have FILL_IN values: {invalid_gt}", file=sys.stderr)
        return 1

    n_total = len(common_ids)
    cs_match = sum(1 for i in common_ids if gt_by_id[i]["canon_status"] == ai_by_id[i]["canon_status"])
    tr_match = sum(1 for i in common_ids if gt_by_id[i]["tradition"] == ai_by_id[i]["tradition"])
    voc_match = sum(1 for i in common_ids
                    if _jaccard(gt_by_id[i]["vocations"], ai_by_id[i]["vocations"]) >= 0.6)

    cs_pct = 100.0 * cs_match / n_total
    tr_pct = 100.0 * tr_match / n_total
    voc_pct = 100.0 * voc_match / n_total

    threshold = 80.0
    passed = cs_pct >= threshold and tr_pct >= threshold and voc_pct >= threshold

    # Disagreement detail
    disagreements = []
    for i in common_ids:
        gt = gt_by_id[i]
        ai = ai_by_id[i]
        deltas = []
        if gt["canon_status"] != ai["canon_status"]:
            deltas.append(f"canon_status ({ai['canon_status']} vs gt {gt['canon_status']})")
        if gt["tradition"] != ai["tradition"]:
            deltas.append(f"tradition ({ai['tradition']} vs gt {gt['tradition']})")
        voc_j = _jaccard(gt["vocations"], ai["vocations"])
        if voc_j < 0.6:
            deltas.append(f"vocations Jaccard {voc_j:.2f}: ai={ai['vocations']} gt={gt['vocations']}")
        if deltas:
            disagreements.append({
                "id": i,
                "is_anchor": i in ANCHOR_IDS,
                "deltas": deltas,
                "ai_reasoning": ai.get("reasoning", ""),
            })

    lines = []
    lines.append("# Pilot diff report")
    lines.append("")
    lines.append(f"Ground truth: `{GROUND_TRUTH.relative_to(ROOT)}`")
    lines.append(f"AI output:    `{PILOT_OUTPUT.relative_to(ROOT)}`")
    lines.append(f"Compared:     {n_total} thinkers")
    lines.append("")
    lines.append("## Per-axis agreement")
    lines.append("")
    lines.append("| Axis | Agreement | Threshold | Pass? |")
    lines.append("|---|---|---|---|")
    lines.append(f"| canon_status | {cs_match}/{n_total} = {cs_pct:.1f}% | {threshold:.0f}% | {'PASS' if cs_pct >= threshold else 'FAIL'} |")
    lines.append(f"| tradition | {tr_match}/{n_total} = {tr_pct:.1f}% | {threshold:.0f}% | {'PASS' if tr_pct >= threshold else 'FAIL'} |")
    lines.append(f"| vocations (Jaccard ≥ 0.6) | {voc_match}/{n_total} = {voc_pct:.1f}% | {threshold:.0f}% | {'PASS' if voc_pct >= threshold else 'FAIL'} |")
    lines.append("")
    lines.append(f"**Overall: {'PASS — bulk dispatch authorized.' if passed else 'FAIL — iterate prompt and re-run pilot (spec §9.4).'}**")
    lines.append("")

    if disagreements:
        anchor_disagreements = [d for d in disagreements if d["is_anchor"]]
        nonanchor_disagreements = [d for d in disagreements if not d["is_anchor"]]
        if anchor_disagreements:
            lines.append("## Disagreements on anchor examples (RED FLAG — prompt may be broken)")
            lines.append("")
            for d in anchor_disagreements:
                lines.append(f"### {d['id']} (anchor)")
                for delta in d["deltas"]:
                    lines.append(f"- {delta}")
                lines.append(f"- ai_reasoning: {d['ai_reasoning']}")
                lines.append("")
        if nonanchor_disagreements:
            lines.append("## Disagreements on validation-only thinkers")
            lines.append("")
            for d in nonanchor_disagreements:
                lines.append(f"### {d['id']}")
                for delta in d["deltas"]:
                    lines.append(f"- {delta}")
                lines.append(f"- ai_reasoning: {d['ai_reasoning']}")
                lines.append("")
    else:
        lines.append("No disagreements.")

    DIFF_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {DIFF_REPORT}")
    print(f"canon_status: {cs_pct:.1f}% | tradition: {tr_pct:.1f}% | vocations: {voc_pct:.1f}%")
    return 0 if passed else 2  # 2 = fail-the-gate (distinguish from 1 = error)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bootstrap", action="store_true")
    g.add_argument("--diff", action="store_true")
    args = ap.parse_args(argv[1:])
    if args.bootstrap:
        return _bootstrap()
    return _diff()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
