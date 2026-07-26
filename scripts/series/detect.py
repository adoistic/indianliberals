#!/usr/bin/env python3
"""Pass 0 — deterministic series detection over primary-works records.

Series membership is almost always already stated inside the record we
generated at ingestion time (the summary prose says "Delivered as the 36th
A. D. Shroff Memorial Lecture", `physical.format` says "FFE booklet"). This
pass lifts that evidence into a structured assignment so the LLM pass only has
to adjudicate the residue.

Emits scripts/series/detected.json:
  {assigned: [{file, id, series_id, ordinal, evidence, confidence}],
   residue:  [{file, id, candidates, snippet}]}

Nothing here writes to the content tree; see apply.py.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PW = os.path.join(ROOT, "apps", "site", "src", "content", "primary-works")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "detected.json")

WORDS = ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
         "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth "
         "twenty-first twenty-second twenty-third twenty-fourth twenty-fifth").split()
ORDINAL_WORDS = {w: i + 1 for i, w in enumerate(WORDS)}

# A named lecture: the ordinal must sit adjacent to the series name, and the
# sentence must assert that THIS work is the lecture (not merely cite one).
LECTURES = {
    "ad-shroff-memorial-lecture": r"a\.?\s*d\.?\s*shroff\s+memorial\s+lecture",
    "bhogilal-leherchand-memorial-lecture": r"bhogilal\s+leherchand\s+memorial\s+lecture",
    "nani-palkhivala-memorial-lecture": r"(?:nani\s+a\.?\s*)?palkhivala\s+memorial\s+lecture",
}
# "Delivered as the Nth X", "is the text of the Nth X", "Nth X delivered by"
ASSERTS = (r"delivered\s+as\s+(?:the\s+)?", r"is\s+the\s+text\s+of\s+(?:the\s+)?",
           r"text\s+of\s+(?:the\s+)?", r"published\s+version\s+of\s+(?:the\s+)?",
           r"delivering\s+(?:the\s+)?")
ORD_RX = r"(?:(\d{1,2})(?:st|nd|rd|th)?|(" + "|".join(ORDINAL_WORDS) + r"))?\s*"

OTHER_SERIES = {
    # id: (regex asserting membership, human note)
    "ccs-viewpoint": r"\bviewpoint\s*(?:no\.?\s*)?(\d+)\b|\bccs\s+viewpoint\b",
    "liberty-institute-occasional-paper": r"liberty\s+institute\s+occasional\s+paper|occasional\s+paper\s*(?:no\.?\s*)?(\d+)",
    "builders-of-indian-economy": r"builders\s+of\s+indian\s+economy",
    "selections-from-the-indian-libertarian": r"selections\s+from\s+['‘\"]?the\s+indian\s+libertarian",
    "ilg-liberal-budget": r"\bthe\s+liberal\s+budget\b",
}

# The Union Budget annual run — FFE's yearly budget analysis. Title-anchored so
# we don't sweep in every work that merely discusses a budget.
UNION_BUDGET = re.compile(r"^\s*(?:the\s+)?union\s+budget\b|^\s*(?:the\s+)?central\s+budget\b", re.I)

FM_RX = re.compile(r"^---\n(.*?)\n---\n", re.S)


def frontmatter(text: str):
    import yaml
    m = FM_RX.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
    except Exception:
        return None
    return fm if isinstance(fm, dict) else None


def title_of(fm) -> str:
    t = fm.get("title")
    if isinstance(t, dict):
        return t.get("main") or ""
    return t or ""


def ordinal_from(m: re.Match):
    for g in m.groups():
        if not g:
            continue
        if g.isdigit():
            return int(g)
        if g.lower() in ORDINAL_WORDS:
            return ORDINAL_WORDS[g.lower()]
    return None


def is_ffe(fm) -> bool:
    pub = fm.get("publication") or {}
    name = (pub.get("publisher_name") or "").lower()
    return (pub.get("publisher_id") == "forum-of-free-enterprise"
            or pub.get("issuer_id") == "forum-of-free-enterprise"
            or "forum of free enterprise" in name)


def main() -> int:
    assigned, residue = [], []
    for fn in sorted(os.listdir(PW)):
        if not fn.endswith((".md", ".mdx")):
            continue
        path = os.path.join(PW, fn)
        text = open(path, encoding="utf-8").read()
        fm = frontmatter(text)
        if not fm:
            continue
        wt = fm.get("work_type")
        # /periodicals/ and /lectures/ already own these two.
        if wt in ("periodical_issue", "lecture", "interview"):
            continue
        title = title_of(fm)
        low = text.lower()
        hit = None

        for sid, name_rx in LECTURES.items():
            strong = re.compile("(?:" + "|".join(ASSERTS) + ")" + ORD_RX + name_rx, re.I)
            numbered = re.compile(r"\b" + ORD_RX.strip() + name_rx, re.I)
            m = strong.search(low)
            if m:
                hit = (sid, ordinal_from(m), "assertion", "high")
                break
            m = numbered.search(low)
            if m and ordinal_from(m) is not None:
                hit = (sid, ordinal_from(m), "ordinal+name", "medium")
                break

        if not hit:
            for sid, rx in OTHER_SERIES.items():
                m = re.search(rx, low, re.I)
                if m:
                    n = next((int(g) for g in (m.groups() or ()) if g and g.isdigit()), None)
                    hit = (sid, n, "name-match", "medium")
                    break

        if not hit and UNION_BUDGET.match(title) and is_ffe(fm):
            hit = ("ffe-union-budget", None, "title-anchored", "high")

        if not hit and is_ffe(fm):
            hit = ("ffe-booklets", None, "publisher", "high")

        if hit:
            sid, ordinal, evidence, conf = hit
            rec = dict(file=fn, id=fm.get("id") or fn[:-3], series_id=sid,
                       ordinal=ordinal, evidence=evidence, confidence=conf,
                       title=title, year=(fm.get("publication") or {}).get("year"),
                       work_type=wt)
            # Medium-confidence lecture/other hits go to the LLM for adjudication.
            if conf == "medium":
                snippet = ""
                for _, rx in list(LECTURES.items()) + list(OTHER_SERIES.items()):
                    m = re.search(rx, low, re.I)
                    if m:
                        snippet = " ".join(text[max(0, m.start() - 400):m.end() + 250].split())
                        break
                rec["snippet"] = snippet
                residue.append(rec)
            else:
                assigned.append(rec)

    json.dump({"assigned": assigned, "residue": residue}, open(OUT, "w"), indent=1)
    from collections import Counter
    print(f"assigned (high confidence): {len(assigned)}")
    for sid, n in Counter(a["series_id"] for a in assigned).most_common():
        print(f"   {n:5}  {sid}")
    print(f"residue (needs adjudication): {len(residue)}")
    for sid, n in Counter(r["series_id"] for r in residue).most_common():
        print(f"   {n:5}  {sid}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
