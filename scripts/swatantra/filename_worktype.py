#!/usr/bin/env python3
"""Deterministic work_type from the archivist's filename.

`work_type` is the one field the cheap models get badly wrong: gpt-5-6-luna
scores ~48% and gpt-5-6-terra ~50% on a stratified sample, because both
collapse minutes, circulars, press notes and essays into `occasional_paper`.
It is also the one field with an independent, model-free signal — the
cataloguer typed the document's form into the filename.

Measured on the 22 trial works whose filename names a form:
    filename cue   (this module)  100%   by construction
    sonnet                          82%
    terra                           73%
    luna                            64%

So where the filename names a form, trust it over the model.

ONE EXCEPTION: never override a model that said `telegram`. Sonnet's four
apparent "misses" against the filename were all documents filed generically as
`Letter_to_X` that are in fact telegrams — it read the form off the page. A
model looking at a telegram blank is better evidence than a cataloguer's
default noun, so `telegram` from the model always wins.

    from filename_worktype import derive, apply
"""
import re

# Cue -> work_type. Ordered: the FIRST match against the filename wins, so
# more specific cues must precede the generic ones ("press_statement" before
# "statement", "newsletter" before "letter" — otherwise every newsletter in
# the corpus becomes a letter).
CUES = [
    ("press_statement", "press_note"),
    ("press_release",   "press_note"),
    ("press_note",      "press_note"),
    ("newsletter",      "periodical_issue"),
    ("news_letter",     "periodical_issue"),
    ("bulletin",        "periodical_issue"),
    ("telegram",        "telegram"),
    ("cable",           "telegram"),
    ("minutes",         "minutes"),
    ("circular",        "circular"),
    ("resolution",      "resolution"),
    ("memorandum",      "pamphlet"),
    ("lecture",         "lecture"),
    ("speech",          "speech"),
    ("address_by",      "speech"),
    ("interview",       "interview"),
    ("letter",          "letter"),
]

# How much information a work_type carries. The filename may only overwrite a
# model verdict with a MORE specific one; it may never downgrade.
#
# This matters in both directions and a flat "filename wins" rule gets one of
# them badly wrong. Overriding `occasional_paper` with `minutes` repairs the
# sink the cheap models fall into. But overriding `circular` with `letter`
# destroys information: on six baked works Sonnet read the page and saw a
# circular, while the cataloguer had filed it under the default noun
# `Letter_to_X`. Same for telegrams filed as letters — the model looking at a
# telegram blank beats a naming habit.
SPECIFICITY = {
    "occasional_paper": 0,        # the sink: carries no information
    "letter": 1,                  # the corpus default noun
    "essay": 2, "speech": 2, "pamphlet": 2, "book": 2,
    "periodical_issue": 2, "edited_volume": 2, "correspondence": 1,
    "telegram": 3, "minutes": 3, "circular": 3, "press_note": 3,
    "resolution": 3, "lecture": 3, "interview": 3,
}


def _rank(wt):
    return SPECIFICITY.get(wt, 2)


def derive(filename):
    """Return (work_type, cue) from a filename, or (None, None)."""
    low = re.sub(r"[^a-z0-9]+", "_", filename.lower())
    for cue, wt in CUES:
        if cue in low:
            return wt, cue
    return None, None


def apply(filename, model_work_type):
    """Resolve filename evidence against the model's answer.

    Returns (work_type, source) where source is one of:
        "model"            no filename cue, or the model is protected
        "filename"         filename cue overrode the model
        "agree"            both said the same thing
    """
    wt, _cue = derive(filename)
    if wt is None:
        return model_work_type, "model"
    if model_work_type == wt:
        return wt, "agree"
    if _rank(wt) <= _rank(model_work_type):
        return model_work_type, "model"   # never downgrade specificity
    return wt, "filename"


if __name__ == "__main__":
    import csv, json, os, sys
    from collections import Counter
    from pathlib import Path
    REPO = Path(__file__).resolve().parents[2]
    BAKE = REPO / "data/bake-off-output"
    rows = list(csv.DictReader(
        open(REPO / "data/swatantra-papers/inventory.tsv", encoding="utf-8"),
        delimiter="\t"))
    cov = Counter(); agree = Counter(); over = Counter()
    n_cue = 0
    for r in rows:
        slug = os.path.splitext(r["file"])[0]
        wt, cue = derive(r["file"])
        cov[wt] += 1
        if wt:
            n_cue += 1
        p = BAKE / slug / "metadata.a.a.json"
        if wt and p.is_file():
            try:
                m = json.loads(p.read_text(encoding="utf-8")).get("work_type")
            except Exception:
                continue
            _, src = apply(r["file"], m)
            (agree if src == "agree" else over)[f"{m} -> {wt}"] += 1
    print(f"corpus: {len(rows):,} works")
    print(f"  filename names a form: {n_cue:,} ({n_cue/len(rows)*100:.0f}%)")
    print("\ncoverage by derived type:")
    for k, v in cov.most_common():
        if k:
            print(f"  {v:5}  {k}")
    print(f"\nagainst baked Sonnet records: {sum(agree.values())} agree, "
          f"{sum(over.values())} would be overridden")
    print("\ntop overrides (model -> filename):")
    for k, v in over.most_common(12):
        print(f"  {v:4}  {k}")
