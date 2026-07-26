#!/usr/bin/env python3
"""Merge Sonnet shard outputs into one applier input, dropping unusable bullets.

Why this exists
---------------
The shard agents were told to derive bullets only from each record's existing
body. For a handful of works the body is a metadata-only stub (image-only scan,
no text layer), and the agents honestly said so — but they said so *in the
bullets*, e.g. "The scan is an image with no usable text layer, pending OCR and
editorial review." That is a pipeline note, not a reader-facing key point, and
must never reach a public page.

This script:
  1. merges every out-*.json (including the partB/partC fragment files a few
     agents produced by sub-delegating),
  2. drops bullets that talk about the scan/OCR/record rather than the work,
  3. drops any work left with too few real bullets, so a thin record keeps no
     digest at all rather than a misleading one,
  4. restricts to the intended target ids and de-duplicates.

Output is the JSON that scripts/kp-backfill/apply.py consumes.
"""

import argparse
import glob
import json
import os
import re
import sys

# Bullets ABOUT the digitisation/record rather than about the work's content.
META = re.compile(
    r"\b("
    r"no (?:reliable |usable |extractable )?text layer"
    r"|image[- ]only"
    r"|pending ocr"
    r"|awaiting ocr"
    r"|ocr and editorial review"
    r"|editorial review"
    r"|bibliographic record"
    r"|remains bibliographic"
    r"|could not be extracted"
    r"|no substantive summary"
    r"|this record"
    r"|the record remains"
    r"|catalogued within"
    r"|scan is"
    r"|source scan"
    r"|corrupted ocr"
    r"|no legible"
    r")\b",
    re.I,
)

MIN_BULLETS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard-dir", default="scripts/kp-backfill/shards2")
    ap.add_argument("--out", default="scripts/kp-backfill/merged.json")
    ap.add_argument("--content-dir", default="apps/site/src/content/primary-works")
    args = ap.parse_args()

    target = set()
    for f in glob.glob(os.path.join(args.shard_dir, "ids-*.json")):
        target |= set(json.load(open(f, encoding="utf-8")))

    merged, seen_bad = {}, []
    for f in sorted(glob.glob(os.path.join(args.shard_dir, "out-*.json"))):
        try:
            recs = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"UNPARSEABLE {f}: {e}", file=sys.stderr)
            continue
        for r in recs:
            rid, bullets = r.get("id"), r.get("key_points") or []
            if rid not in target:
                continue
            kept = [b.strip() for b in bullets if b and not META.search(b)]
            dropped = len(bullets) - len(kept)
            if dropped:
                seen_bad.append((rid, dropped))
            # keep the richest version if an id appears in several fragments
            if rid not in merged or len(kept) > len(merged[rid]):
                merged[rid] = kept

    ok, thin, already = {}, [], []
    for rid, bullets in merged.items():
        path = os.path.join(args.content_dir, rid + ".md")
        if os.path.exists(path):
            body = open(path, encoding="utf-8").read()
            if re.search(r"^##\s+Key points\s*$", body, re.M):
                already.append(rid)
                continue
        if len(bullets) < MIN_BULLETS:
            thin.append((rid, len(bullets)))
            continue
        ok[rid] = bullets

    out = [{"id": k, "key_points": v} for k, v in sorted(ok.items())]
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"target ids            : {len(target)}")
    print(f"merged from shards    : {len(merged)}")
    print(f"meta-bullets stripped : {sum(n for _, n in seen_bad)} across {len(seen_bad)} works")
    print(f"skipped, already had  : {len(already)}")
    print(f"skipped, too thin(<{MIN_BULLETS}): {len(thin)}  {[t[0] for t in thin]}")
    print(f"WRITABLE              : {len(out)} -> {args.out}")
    missing = target - set(merged)
    if missing:
        print(f"NOT YET COVERED       : {len(missing)}")


if __name__ == "__main__":
    main()
