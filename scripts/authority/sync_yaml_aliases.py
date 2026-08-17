#!/usr/bin/env python3
"""Sync curator-declared name forms from thinkers.yaml into the extraction lookup.

`content/authority/thinkers.yaml` (curated, small, hand-annotated) and
`data/authority/thinkers.json` (machine-built seed from build_seed.py, 454
entries) are two INDEPENDENT sources. Nothing has ever derived one from the
other, so they have drifted: name forms the curators declared in the YAML are
absent from the `byline_lookup` map that `metadata.a` / `metadata.b` resolve
bylines against.

The concrete cost, found by the Swatantra pilot on 2026-08-17: the YAML declares
`M. R. Masani` as an alias of `minoo-masani`, but `byline_lookup` had only
`mr masani` and `m r masani mp`. Party circulars are signed exactly
"(M. R. Masani)", so they resolved to `thinker_id: null` and were flagged for
human review. Masani is the correspondent in 1,171 of the 6,355 Swatantra files.

This script only ADDS lookup keys, and only from forms a curator wrote down. It
never renames, merges, deletes, or invents. Re-runnable and idempotent.

    python3 scripts/authority/sync_yaml_aliases.py [--apply]

Without --apply it prints what would change and writes nothing.
"""
import argparse
import json
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
YAML_PATH = REPO / "content/authority/thinkers.yaml"
JSON_PATH = REPO / "data/authority/thinkers.json"

# Fields on a YAML entry that hold a usable human name form. `sort_name` is
# excluded: "Masani, Minoo" is a filing form, not a byline anyone prints.
NAME_FIELDS = ("canonical_name", "full_name")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", s.lower())).strip()


def main(apply_changes):
    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    entries = data["thinkers"] if isinstance(data, dict) and "thinkers" in data else data
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    lookup = doc["byline_lookup"]
    by_id = {t.get("id"): t for t in doc["thinkers"]}
    known_ids = set(by_id)
    existing = {norm(k) for k in lookup}

    additions, skipped_unknown_id, alias_additions = [], [], []
    for entry in entries:
        tid = entry.get("id")
        if not tid:
            continue
        if tid not in known_ids:
            # The YAML knows a thinker the extraction seed does not. Adding a
            # lookup key pointing at an id with no entry would resolve bylines
            # to a dangling reference, so flag rather than write.
            skipped_unknown_id.append(tid)
            continue
        forms = [entry.get(f) for f in NAME_FIELDS]
        forms += list(entry.get("also_known_as") or [])
        # `name.also_known_as` is what the EXTRACTION PROMPT actually sees:
        # _load_authority_subset ships {id, canonical, aliases} built from this
        # field. `byline_lookup` is only read by downstream Python. Patching
        # the lookup alone therefore changes nothing the model can use — the
        # first attempt at this fix did exactly that and the re-test still
        # returned thinker_id: null. Both structures need the forms.
        entry_json = by_id[tid]
        seen_aliases = {norm(a) for a in (entry_json["name"].get("also_known_as") or [])}
        seen_aliases.add(norm(entry_json["name"].get("canonical", "")))

        for form in forms:
            if not form or not isinstance(form, str):
                continue
            key = norm(form)
            if key and key not in seen_aliases:
                entry_json["name"].setdefault("also_known_as", []).append(form)
                seen_aliases.add(key)
                alias_additions.append((tid, form))
            # Skip non-Latin forms: byline_lookup is normalised to ASCII, so a
            # Devanagari alias normalises to empty. Cross-script matching is
            # enrich-ingested.py's job, not this map's.
            if not key or key in existing:
                continue
            additions.append((key, tid, form))
            existing.add(key)

    print(f"YAML entries: {len(entries)}   byline_lookup keys: {len(lookup)}")
    print(f"forms missing from byline_lookup (downstream Python): {len(additions)}")
    print(f"forms missing from name.also_known_as (what the PROMPT sees): "
          f"{len(alias_additions)}\n")
    for key, tid, form in additions:
        print(f"  + {key:32s} -> {tid:26s}  (YAML: {form!r})")
    if skipped_unknown_id:
        print(f"\nSKIPPED — in YAML but no entry in the extraction seed "
              f"({len(skipped_unknown_id)}): {', '.join(sorted(skipped_unknown_id))}")
        print("  Adding lookup keys for these would resolve bylines to a dangling")
        print("  thinker_id. They need entries in data/authority/thinkers.json first.")

    if not apply_changes:
        print("\n(dry run — pass --apply to write)")
        return 0
    if not additions and not alias_additions:
        print("\nnothing to do")
        return 0

    backup = JSON_PATH.with_suffix(".json.bak")
    shutil.copy2(JSON_PATH, backup)
    for key, tid, _ in additions:
        lookup[key] = tid
    doc["_meta"]["alias_sync"] = {
        "date": date.today().isoformat(),
        "source": "content/authority/thinkers.yaml",
        "keys_added": len(additions),
        "prompt_aliases_added": len(alias_additions),
        "script": "scripts/authority/sync_yaml_aliases.py",
        "note": ("Curator-declared name forms only. Found because Swatantra "
                 "circulars signed '(M. R. Masani)' failed to resolve while the "
                 "YAML declared that exact alias."),
    }
    JSON_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"\napplied {len(additions)} lookup keys + {len(alias_additions)} "
          f"prompt-visible aliases. backup at {backup.name}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    raise SystemExit(main(ap.parse_args().apply))
