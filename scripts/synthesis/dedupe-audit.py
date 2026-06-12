#!/usr/bin/env python3
"""Find duplicate entries across Tier-A content collections.

WordPress import produced double-imports (same piece under two slugs,
sometimes with a `-2` suffix or a slightly different title). This script
groups entries by normalised title AND by body similarity, then reports
pairs above a similarity threshold so a human (or the calling agent) can
pick the canonical slug.

Usage:
    python3 scripts/synthesis/dedupe-audit.py [--threshold 0.85]

Output: one block per suspected duplicate pair with title, slugs,
pubDates, body lengths, and similarity ratio. Exit code 0 always —
this is a report, not a gate.
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

SITE_CONTENT = Path(__file__).resolve().parents[2] / "apps/site/src/content"
COLLECTIONS = ["opinions", "musings", "primary-works", "theprint-mirror"]


def split_frontmatter(text: str) -> tuple[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return "", text
    return m.group(1), m.group(2)


def field(fm: str, name: str) -> str:
    m = re.search(rf"^{name}:\s*(.+)$", fm, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[’'\"“”:;,.!?()–—-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def norm_body(b: str) -> str:
    b = re.sub(r"\s+", " ", b).strip().lower()
    return b


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.85)
    args = ap.parse_args()

    found_any = False
    for coll in COLLECTIONS:
        cdir = SITE_CONTENT / coll
        if not cdir.is_dir():
            continue
        entries = []
        for f in sorted(cdir.glob("*.md")):
            fm, body = split_frontmatter(f.read_text(encoding="utf-8"))
            entries.append(
                {
                    "file": f.name,
                    "title": field(fm, "title") or field(fm, "  main"),
                    "pubDate": field(fm, "pubDate"),
                    "draft": field(fm, "draft"),
                    "body": norm_body(body),
                }
            )

        # Candidate pairs: same normalised title, or one slug is the other
        # plus a -2/-3 suffix, or very close slugs.
        pairs = set()
        by_title: dict[str, list[int]] = {}
        for i, e in enumerate(entries):
            if e["title"]:
                by_title.setdefault(norm_title(e["title"]), []).append(i)
        for idxs in by_title.values():
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    pairs.add((idxs[a], idxs[b]))
        slugs = [e["file"].removesuffix(".md") for e in entries]
        for i, s in enumerate(slugs):
            m = re.match(r"^(.*)-\d$", s)
            if m and m.group(1) in slugs:
                pairs.add(tuple(sorted((slugs.index(m.group(1)), i))))
        # Near-identical slugs (e.g. freedom-first vs freedom-firsts)
        for i in range(len(slugs)):
            for j in range(i + 1, len(slugs)):
                if difflib.SequenceMatcher(None, slugs[i], slugs[j]).ratio() > 0.93:
                    pairs.add((i, j))

        for i, j in sorted(pairs):
            a, b = entries[i], entries[j]
            if not a["body"] or not b["body"]:
                ratio = 0.0
            else:
                ratio = difflib.SequenceMatcher(None, a["body"], b["body"]).ratio()
            if ratio >= args.threshold:
                found_any = True
                print(f"[{coll}] similarity={ratio:.3f}")
                for e in (a, b):
                    print(
                        f"    {e['file']}  pubDate={e['pubDate'] or '-'}  "
                        f"draft={e['draft'] or 'false'}  body={len(e['body'])} chars  "
                        f"title={e['title'][:70]!r}"
                    )
                print()

    if not found_any:
        print("No duplicate pairs above threshold.")


if __name__ == "__main__":
    main()
