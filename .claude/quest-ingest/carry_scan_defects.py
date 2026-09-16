#!/usr/bin/env python3
"""Carry physical-artefact defects from the extraction into provenance.notes.

emit-astro-md.py does not copy the extraction's `notes`, so a defect an agent
found in the SCAN rather than the text never reached the published record.
QT020's leaves for printed pp.22-41 are bound or scanned out of sequence —
proved by a sentence splitting across non-adjacent PDF pages — and every page
citation in that range depends on knowing it.

Only physical defects are carried, not editorial asides about cover taglines:
the note must mention sequence, binding, legibility, missing or duplicated
leaves, or damage. provenance.notes is the schema's own home for this.

Usage: carry_scan_defects.py <QT0NN> [...]
"""
import json, re, sys
from pathlib import Path
REPO = Path("/Users/siraj/Indian Liberals Website")
WORKS = REPO / "apps/site/src/content/primary-works"
BAKE = REPO / "data/bake-off-output"
DEFECT = re.compile(r"out of sequence|out of order|mis-?bound|misbind|scanned out|"
                    r"illegible|unreadable|missing page|missing lea|duplicate(d)? (page|lea)|"
                    r"torn|damaged|cropped|cut off", re.I)
for qt in sys.argv[1:]:
    qt = qt.upper(); md = WORKS / f"{qt.lower()}.md"; mj = BAKE / qt / "metadata.a.json"
    if not (md.exists() and mj.exists()): print(f"SKIP {qt}"); continue
    notes = json.loads(mj.read_text(encoding="utf-8")).get("notes") or ""
    if isinstance(notes, dict): notes = json.dumps(notes, ensure_ascii=False)
    # A negated sentence reports the ABSENCE of a defect and must not be carried:
    # QT021's agent wrote "No leaves appear bound out of sequence", which the
    # bare keyword match turned into a "scan defect" note saying there isn't one,
    # and marked the scan fair.
    NEG = re.compile(r"\b(no|not|none|nothing|never|without|free of|did not|does not|"
                     r"weren't|wasn't|isn't|aren't)\b", re.I)
    hits = []
    for s in re.split(r"(?<=\.)\s+", notes):
        s = s.strip()
        if not DEFECT.search(s):
            continue
        head = s[:max(0, DEFECT.search(s).start())]
        if NEG.search(head):
            continue
        hits.append(s)
    if not hits: print(f"{qt}: no physical defect noted"); continue
    text = md.read_text(encoding="utf-8")
    if "scan defect:" in text: print(f"{qt}: already carried"); continue
    note = ("scan defect: " + " ".join(hits)).replace('"', "'").replace("\n", " ")
    lines = text.split("\n")
    i = next((k for k, l in enumerate(lines) if l == "provenance:"), None)
    if i is None: print(f"{qt}: no provenance block"); continue
    j = i + 1
    while j < len(lines) and (lines[j].startswith("  ") or lines[j] == ""): j += 1
    block = [l for l in lines[i+1:j] if not re.match(r"\s*notes:", l)]
    block.append(f'  notes: "{note}"')
    if any(re.match(r"\s*scan_quality:", l) for l in block):
        block = [re.sub(r"^(\s*scan_quality:).*$", r"\1 fair", l) for l in block]
    else:
        block.append("  scan_quality: fair")
    md.write_text("\n".join(lines[:i+1] + block + lines[j:]), encoding="utf-8")
    print(f"{qt}: carried -> {note[:110]}")
