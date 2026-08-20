#!/usr/bin/env python3
"""Recover summaries from responses the parser rejected.

gpt-5-6-luna's one systematic JSON failure is a runaway summary paragraph
emitted as a bare string in object position (see the note above parse_json in
kie-ingest.py). The response is otherwise complete and correct, so these are
not failed extractions — they are successful ones a stricter parser threw
away, and every one of them was already paid for.

This re-parses the captured text with the repaired parser and writes the
summaries that come back. No API calls, no cost.

    python3 scripts/swatantra/salvage-unparseable.py            # dry run
    python3 scripts/swatantra/salvage-unparseable.py --apply
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DUMPS = REPO / "data/swatantra-papers/kie-unparseable"

# kie-ingest.py is not importable by name (the hyphen), and it is the single
# source of truth for both the repair and the validator wiring.
_spec = importlib.util.spec_from_file_location(
    "kie_ingest", REPO / "scripts/swatantra/kie-ingest.py")
_ki = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ki)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--bake-root", default=str(_ki.BAKE),
                    help="extraction tree the summaries belong to")
    a = ap.parse_args()
    bake = Path(a.bake_root)

    if not DUMPS.is_dir():
        print(f"no dumps at {DUMPS}")
        return 0

    wrote = skipped = present = unrecoverable = no_dir = 0
    for f in sorted(DUMPS.glob("*.txt")):
        # "<slug>.<job>.txt"
        stem = f.name[:-len(".txt")]
        slug, _, job = stem.rpartition(".")
        if job != "summary":
            skipped += 1
            continue
        d = bake / slug
        if not d.is_dir():
            no_dir += 1
            continue
        out = d / "summary.json"
        if out.exists():
            present += 1          # the retry already got it; leave it alone
            continue
        parsed = _ki.parse_json(f.read_text(encoding="utf-8"))
        if parsed is None:
            unrecoverable += 1
            print(f"  UNRECOVERABLE {slug}")
            continue
        if a.apply:
            out.write_text(json.dumps(parsed, indent=2, ensure_ascii=False),
                           encoding="utf-8")
        wrote += 1

    verb = "wrote" if a.apply else "would write"
    print(f"{verb} {wrote} summaries")
    print(f"  already had one (retry got it) : {present}")
    print(f"  still unrecoverable            : {unrecoverable}")
    print(f"  no extraction dir              : {no_dir}")
    print(f"  not a summary job              : {skipped}")
    if not a.apply:
        print("\n(dry run — pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
