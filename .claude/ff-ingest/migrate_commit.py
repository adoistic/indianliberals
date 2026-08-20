#!/usr/bin/env python3
"""Commits the migrated non-FF works in reasonable batches by category
(splitting the largest category into chunks), one git commit per batch."""
import subprocess
import sys

ROOT = "/Users/siraj/Indian Liberals Website"

# Load manifest: local, key, mdfile, old_url, new_url
rows = []
with open("/tmp/other_works_manifest.tsv") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        rows.append(parts)

by_cat = {}
for r in rows:
    cat = r[1].split("/")[0]
    by_cat.setdefault(cat, []).append(r[2])  # mdfile paths

CHUNK = 200
batches = []
for cat, files in sorted(by_cat.items(), key=lambda x: -len(x[1])):
    for i in range(0, len(files), CHUNK):
        batches.append((cat, i // CHUNK + 1, files[i:i+CHUNK]))

print(f"total batches: {len(batches)}")
for cat, part, files in batches:
    label = f"{cat} (part {part})" if len([b for b in batches if b[0]==cat]) > 1 else cat
    print(f"--- committing {label}: {len(files)} files ---")
    subprocess.run(["git", "add"] + files, cwd=ROOT, check=True)
    msg = (
        f"data(primary-works): host {label} PDFs on R2 (migrated from WordPress)\n\n"
        f"Uploaded {len(files)} existing local source PDFs to the Cloudflare R2\n"
        f"bucket 'indianliberals-archive', keyed identically to their existing\n"
        f"indianliberals.in/{cat}/<slug>.pdf paths so the migration is\n"
        f"domain-portable (attaching the custom domain later serves the same\n"
        f"paths, no link changes needed). Updated pdf_url on each entry.\n\n"
        f"Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
    )
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if result.returncode == 0:
        print(f"  (nothing staged for {label}, skipping)")
        continue
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=ROOT, check=True)
    print(f"  committed.")

print("=== pulling + pushing ===")
subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=ROOT)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT)
