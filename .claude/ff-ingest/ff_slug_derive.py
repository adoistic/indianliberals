#!/usr/bin/env python3
"""
Derive the date-slug R2 key (freedom-first-<mon>1-<year>.pdf) for every ingested
FF issue from its markdown (year: field + month parsed from the summary), then:
  - VALIDATE: for the 153 issues that already have a pdf_url, check the derived
    slug matches the real one exactly. Any mismatch => derivation not trustworthy.
  - PROPOSE: for the issues with no pdf_url, print the proposed slug and whether
    the drive scan FFxxx.pdf exists.
Read-only. No uploads, no file writes to the repo.
"""
import glob, os, re

WORKS = "/Users/siraj/Indian Liberals Website/apps/site/src/content/primary-works"
DRIVE = "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/freedom-first"
MONTHS = {m: a for a, m in zip(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"],
    ["january","february","march","april","may","june","july","august",
     "september","october","november","december"])}
MON_RX = "|".join(MONTHS)

def frontmatter(text):
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""

def derive(mdfile):
    text = open(mdfile, encoding="utf-8", errors="ignore").read()
    fm = frontmatter(text)
    ym = re.search(r"^\s*year:\s*(\d{4})", fm, re.M)
    year = ym.group(1) if ym else None
    # month: look in the summary line first, then anywhere in the doc
    sm = re.search(r"summary:.*?\b(%s)\b" % MON_RX, text, re.I | re.S)
    if not sm:
        sm = re.search(r"\b(%s)\b\s+\d{4}" % MON_RX, text, re.I)
    month = MONTHS[sm.group(1).lower()] if sm else None
    # also grab year from the "(Month YYYY)" pair if frontmatter year missing
    if not year:
        pm = re.search(r"\b(?:%s)\b\s+(\d{4})" % MON_RX, text, re.I)
        year = pm.group(1) if pm else None
    slug = f"freedom-first-{month}1-{year}.pdf" if (month and year) else None
    return year, month, slug

def real_pdf_slug(text):
    m = re.search(r"^pdf_url:\s*\S+/([^/\s]+\.pdf)\s*$", text, re.M)
    return m.group(1) if m else None

ok = mism = 0
mismatches = []
proposed = []
unparsed = []
for f in sorted(glob.glob(f"{WORKS}/ff*.md")):
    ffid = os.path.basename(f)[:-3]          # ff300
    num = ffid[2:].upper()                    # 300
    text = open(f, encoding="utf-8", errors="ignore").read()
    year, month, slug = derive(f)
    real = real_pdf_slug(text)
    drive = os.path.exists(f"{DRIVE}/FF{num}.pdf")
    if real:  # validation set
        if slug == real:
            ok += 1
        else:
            mism += 1
            mismatches.append((ffid, real, slug))
    else:     # proposal set
        if slug:
            proposed.append((ffid, num, slug, drive))
        else:
            unparsed.append((ffid, year, month))

print(f"VALIDATION (issues with existing pdf_url): {ok} match, {mism} MISMATCH")
for ffid, real, slug in mismatches[:40]:
    print(f"  MISMATCH {ffid}: real={real}  derived={slug}")
print()
print(f"PROPOSED (unlinked issues): {len(proposed)} derived a slug, {len(unparsed)} could NOT parse month/year")
miss_drive = [p for p in proposed if not p[3]]
print(f"  of the {len(proposed)} proposed, {len(miss_drive)} have NO drive scan FFxxx.pdf")
# collision check among proposed
from collections import Counter
c = Counter(s for _, _, s, _ in proposed)
dupes = {k: v for k, v in c.items() if v > 1}
print(f"  slug collisions among proposed: {len(dupes)}")
for k, v in list(dupes.items())[:20]:
    print(f"    {k} x{v}")
print()
print("  sample proposed:")
for ffid, num, slug, drive in proposed[:8]:
    print(f"    {ffid} -> {slug}  (drive scan: {'yes' if drive else 'NO'})")
if unparsed:
    print("  UNPARSED:")
    for ffid, y, m in unparsed[:20]:
        print(f"    {ffid}: year={y} month={m}")
