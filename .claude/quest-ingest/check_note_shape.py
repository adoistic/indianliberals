#!/usr/bin/env python3
"""Keep only biography-shaped text in note_verbatim.

A contributor note is third-person biography and opens with the person's own
name: "S. Ookerjee lectures in philosophy at Wilson College". A letter or
article by the same person is neither, and Quest prints plenty of both on
byline-dense pages. Four such letters were transcribed into note_verbatim
during the QT001-010 recovery, e.g. S. Ookerjee's "When he can give unambiguous
answers to the arguments he will find there..." — which the profile builder
would have quoted as sourced biography on his author page.

The text is accurate, just not biography, so it is MOVED to
`self_authored_excerpt` rather than discarded. Only note_verbatim feeds
build_profiles.py.

Test: does the note open with the person's surname within its first ~8 words?

Usage: check_note_shape.py [--fix] <QT0NN> [...]
"""
import json, re, sys, unicodedata
from pathlib import Path

HARVEST = Path("/Users/siraj/Indian Liberals Website/data/quest-contributors")
FIX = "--fix" in sys.argv

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"^(mrs|mr|dr|prof|professor|shri|sri|smt|miss|ms|swami|sir)\.?\s+", "", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())

total = moved = 0
for qt in [a for a in sys.argv[1:] if not a.startswith("--")]:
    p = HARVEST / f"{qt.upper()}.json"
    if not p.exists():
        print(f"SKIP {qt}"); continue
    rows = json.loads(p.read_text(encoding="utf-8"))
    hits = []
    for r in rows:
        n = r.get("note_verbatim")
        if not n: continue
        total += 1
        # Check EVERY name form we hold for this person, not just the byline.
        # Quest routinely prints a contributor under one name and bios them
        # under another: "Ashapurna Devi" is bioed as "ASHAPURNA GUPTA is a
        # leading short story writer in Bengali", "A. H. Somjee" as "A. H.
        # SOMJI, Reader in Political Science". Matching the byline alone
        # discarded both as non-biography.
        forms = [r.get("byline_verbatim") or "", r.get("name_as_in_contributor_note") or ""]
        forms += [v for v in (r.get("name_variants") or []) if isinstance(v, str)]
        surs = {norm(f).split()[-1] for f in forms if norm(f)}
        lead = set(norm(" ".join(n.split()[:8])).split())
        if surs and not (surs & lead):
            hits.append(r)
    for r in hits:
        moved += 1
        if FIX:
            r["self_authored_excerpt"] = r["note_verbatim"]
            r["note_verbatim"] = None
            r["note_printed_page"] = None
    if hits:
        print(f"{qt}: {len(hits)} non-biography note(s) "
              + ("moved to self_authored_excerpt" if FIX else "found"))
        for r in hits:
            print(f"    {r['byline_verbatim']}: {(r.get('self_authored_excerpt') or r.get('note_verbatim'))[:80]}")
    if FIX and hits:
        p.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\n{total} notes checked, {moved} not biography-shaped")
