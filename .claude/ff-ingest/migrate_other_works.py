#!/usr/bin/env python3
"""
Migrates the non-Freedom-First primary-works corpus from WordPress hosting
to the same R2 bucket used for Freedom First (indianliberals-archive),
preserving the exact existing URL path (<category>/<slug>.pdf) so the
migration is domain-portable: attaching indianliberals.in to the bucket
later serves the identical paths, no link changes needed.

Only migrates entries whose local source PDF is confirmed present (via
pdf_url -> PDFs-by-publisher/<category>/<slug>.pdf, URL-decoded). Entries
whose local file is missing are left untouched and reported, not guessed.

Usage:
    .venv-extract/bin/python3 .claude/ff-ingest/migrate_other_works.py --manifest-only
        # just (re)generates /tmp/other_works_manifest.tsv and reports counts
    .venv-extract/bin/python3 .claude/ff-ingest/migrate_other_works.py --set-urls
        # after uploads are done (see migrate_other_works_upload.sh), rewrites
        # pdf_url in each .md from the manifest and reports how many changed
"""
import argparse
import glob
import os
import re
import urllib.parse

ROOT = "/Users/siraj/Indian Liberals Website"
WORKS = os.path.join(ROOT, "apps/site/src/content/primary-works")
SRC = "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher"
R2_HOST = "https://pub-f1430c20cc1c400da542453c56d614c8.r2.dev"
MANIFEST = "/tmp/other_works_manifest.tsv"


def build_manifest():
    rows = []
    missing = []
    for f in sorted(glob.glob(f"{WORKS}/*.md")):
        t = open(f, encoding="utf-8", errors="ignore").read()
        m = re.search(r"^pdf_url:\s*(\S+)", t, re.M)
        if not m or "indianliberals.in" not in m.group(1):
            continue
        old_url = m.group(1)
        path = re.sub(r"^https?://indianliberals\.in/", "", urllib.parse.unquote(old_url))
        local = os.path.join(SRC, path)
        if not os.path.exists(local):
            missing.append((f, path))
            continue
        new_url = f"{R2_HOST}/{path}"
        rows.append((local, path, f, old_url, new_url))
    with open(MANIFEST, "w") as out:
        for r in rows:
            out.write("\t".join(r) + "\n")
    return rows, missing


def set_urls():
    changed = 0
    with open(MANIFEST) as fh:
        for line in fh:
            local, key, mdfile, old_url, new_url = line.rstrip("\n").split("\t")
            t = open(mdfile, encoding="utf-8").read()
            new_t = t.replace(f"pdf_url: {old_url}", f"pdf_url: {new_url}", 1)
            if new_t != t:
                open(mdfile, "w", encoding="utf-8").write(new_t)
                changed += 1
    print(f"pdf_url updated in {changed} files")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--set-urls", action="store_true")
    args = ap.parse_args()

    if args.set_urls:
        set_urls()
    else:
        rows, missing = build_manifest()
        print(f"manifest: {len(rows)} entries ready -> {MANIFEST}")
        print(f"missing local PDF (skipped, needs manual fix): {len(missing)}")
        for f, p in missing:
            print(f"  MISSING: {p}  <- {f}")
