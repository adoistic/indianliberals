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
                    r"torn|damaged|cropped|cut off|"
                    # QT035's four tipped-in Kanchanjangha plates include two
                    # leaves scanned sideways: the images and their captions
                    # read vertically. Nothing is lost, but a reader meets two
                    # pages turned 90 degrees, so it belongs in provenance.
                    r"rotat(ed|ion)|sideways|upside[- ]down|90 ?(degrees|\u00b0)", re.I)
# Rotation is the one defect word that also describes a PERFECTLY GOOD original:
# QT036's Konarak plate is a landscape sheet, "four drawings printed sideways",
# which is how Quest printed it. So a rotation hit only counts when the sentence
# also talks about the ARTEFACT - the scan, the PDF, the leaf, the binding - and
# never when "printed" or "original" is what is being described.
ROT = re.compile(r"rotat(ed|ion)|sideways|upside[- ]down|90 ?(degrees|\u00b0)", re.I)
ARTEFACT = re.compile(r"\b(scan|scans|scanned|pdf|leaf|leaves|bound|binding|capture[d]?)\b", re.I)
AS_PRINTED = re.compile(r"\b(printed|prints|as printed|in the original|original layout|"
                        r"landscape plate|laid out)\b", re.I)
# Grade by what the defect does to a READER, so scan_quality is a usable
# rescan list instead of one undifferentiated bucket. Everything used to land
# on "fair", which put QT040's single damaged digit on the contents page at the
# same grade as QT020's twenty relocated pages.
SEVERE = re.compile(r"out of sequence|out of order|mis-?bound|misbind|scanned out|"
                    r"missing page|missing lea|duplicate(d)? (page|lea)|"
                    r"illegible|unreadable", re.I)
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
        # a rotation claim needs artefact context and must not be about the print
        if ROT.search(s) and not DEFECT.sub("", ROT.sub("", s)).strip(" .,;:"):
            pass
        if ROT.search(s) and not ARTEFACT.search(s):
            continue
        if ROT.search(s) and AS_PRINTED.search(s) and not re.search(
                r"\b(scan|scanned|pdf)\b", s, re.I):
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
    grade = "poor" if any(SEVERE.search(h) for h in hits) else "fair"
    if any(re.match(r"\s*scan_quality:", l) for l in block):
        block = [re.sub(r"^(\s*scan_quality:).*$", rf"\1 {grade}", l) for l in block]
    else:
        block.append(f"  scan_quality: {grade}")
    md.write_text("\n".join(lines[:i+1] + block + lines[j:]), encoding="utf-8")
    print(f"{qt}: carried [{grade}] -> {note[:100]}")
