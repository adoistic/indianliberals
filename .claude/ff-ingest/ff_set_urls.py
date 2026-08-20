#!/usr/bin/env python3
"""Insert a top-level `pdf_url:` line into each FF md in /tmp/ff_pdf_manifest.tsv,
placed immediately before the top-level `provenance:` line (matching the existing
153 linked files). Skips any file that already has a pdf_url. Idempotent."""
import re

MANIFEST = "/tmp/ff_pdf_manifest.tsv"
inserted = skipped = nofm = 0
problems = []
with open(MANIFEST) as fh:
    for line in fh:
        local, key, mdfile, url = line.rstrip("\n").split("\t")
        text = open(mdfile, encoding="utf-8").read()
        if re.search(r"^pdf_url:", text, re.M):
            skipped += 1
            continue
        new_line = f"pdf_url: {url}\n"
        # insert before the first top-level `provenance:` line
        m = re.search(r"^provenance:", text, re.M)
        if m:
            text = text[:m.start()] + new_line + text[m.start():]
        else:
            problems.append((mdfile, "no top-level provenance:"))
            continue
        open(mdfile, "w", encoding="utf-8").write(text)
        inserted += 1
print(f"inserted={inserted}  skipped(already had)={skipped}  problems={len(problems)}")
for p in problems:
    print("  PROBLEM:", p)
