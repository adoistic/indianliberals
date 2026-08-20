#!/usr/bin/env python3
"""Emit /tmp/ff_pdf_manifest.tsv for FF issues that are ingested but have no
pdf_url: columns = local_pdf \t r2_key \t mdfile \t new_pdf_url.
Uses the validated date-slug derivation (see ff_slug_derive.py: 153/153 match)."""
import glob, os, re

WORKS = "/Users/siraj/Indian Liberals Website/apps/site/src/content/primary-works"
DRIVE = "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/freedom-first"
R2_HOST = "https://pub-f1430c20cc1c400da542453c56d614c8.r2.dev"
OUT = "/tmp/ff_pdf_manifest.tsv"
MONTHS = dict(zip(
    ["january","february","march","april","may","june","july","august",
     "september","october","november","december"],
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]))
MON_RX = "|".join(MONTHS)

rows = []
unparseable = []
for f in sorted(glob.glob(f"{WORKS}/ff*.md")):
    text = open(f, encoding="utf-8", errors="ignore").read()
    if re.search(r"^pdf_url:", text, re.M):
        continue  # already linked
    num = os.path.basename(f)[2:-3].upper()   # 195
    fm = text.split("---", 2)[1]
    ym = re.search(r"^\s*year:\s*(\d{4})", fm, re.M)
    ym2 = re.search(r"\b(?:%s)\b\s+(\d{4})" % MON_RX, text, re.I)
    year = ym.group(1) if ym else (ym2.group(1) if ym2 else None)
    fm_month = re.search(
        r"^\s*(?:edition|series):.*?\b(%s)\b" % MON_RX,
        fm,
        re.I | re.M,
    )
    mm = fm_month or re.search(r"summary:.*?\b(%s)\b" % MON_RX, text, re.I | re.S)
    mon = MONTHS[mm.group(1).lower()] if mm else None
    if not (year and mon):
        # extraction dropped the month/year somewhere the regex can't find it
        # (seen once: ff329, summary text had no "(Month Year)" phrasing at all).
        # Skip here — handle as a manual one-off, don't block the rest of the batch.
        unparseable.append(f)
        continue
    key = f"freedom-first/freedom-first-{mon}1-{year}.pdf"
    local = f"{DRIVE}/FF{num}.pdf"
    rows.append((local, key, f, f"{R2_HOST}/{key}"))

with open(OUT, "w") as fh:
    for r in rows:
        fh.write("\t".join(r) + "\n")
print(f"wrote {len(rows)} rows -> {OUT}")
print("all local scans present:", all(os.path.exists(r[0]) for r in rows))
if unparseable:
    print(f"SKIPPED (no month/year parseable, needs manual slug): {len(unparseable)}")
    for f in unparseable:
        print(f"  {f}")
