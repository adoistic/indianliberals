#!/usr/bin/env python3
"""Export primary-works frontmatter as works_meta.json for the full-text index.

One record per work that has a pdf_url, keyed by its R2 object key
(the pdf_url path). Mirrors the /primary-works/ listing rules:
  - draft / hide_from_index works are excluded (lib/listable.ts),
  - the facet language is publication.language ?? language ?? "en",
  - the page path is pathForEntry: /<lang>/primary-works/<slug>/ for non-en.

Usage: python3 scripts/fulltext/export-works-meta.py <out.json>
"""
import json
import os
import sys

import yaml

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
CONTENT = os.path.join(ROOT, "apps", "site", "src", "content", "primary-works")


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    return yaml.safe_load(text[3:end])


def main(out_path):
    metas = {}
    skipped = 0
    for name in sorted(os.listdir(CONTENT)):
        if not name.endswith(".md"):
            continue
        fm = frontmatter(os.path.join(CONTENT, name))
        if not fm:
            continue
        if fm.get("draft") or fm.get("hide_from_index"):
            skipped += 1
            continue
        pdf_url = fm.get("pdf_url")
        if not pdf_url or "archive.indianliberals.in/" not in pdf_url:
            skipped += 1
            continue
        key = pdf_url.split("archive.indianliberals.in/")[1]
        slug = fm.get("id") or name[:-3]
        route_lang = fm.get("language") or "en"
        pub = fm.get("publication") or {}
        facet_lang = pub.get("language") or route_lang
        prefix = "" if route_lang == "en" else f"/{route_lang}"
        contributors = fm.get("contributors") or []
        byline = ", ".join(
            (c.get("thinker") or c.get("thinker_unresolved") or "").replace("-", " ")
            for c in contributors
            if isinstance(c, dict) and c.get("role") == "author"
            and (c.get("thinker") or c.get("thinker_unresolved"))
        )
        title = fm.get("title") or {}
        year = pub.get("year")
        metas[key] = {
            "slug": slug,
            "path": f"{prefix}/primary-works/{slug}/",
            "title": title.get("main") or slug,
            "subtitle": title.get("subtitle") or "",
            "byline": byline,
            "year": year,
            "decade": (year // 10 * 10) if isinstance(year, int) else None,
            "work_type": fm.get("work_type") or "other",
            "themes": fm.get("themes") or [],
            "language": facet_lang,
            "cover_image": fm.get("cover_image") or "",
            "collection": key.split("/")[0],
            "pdf_url": pdf_url,
        }
    json.dump(metas, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(metas)} works exported, {skipped} skipped")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "works_meta.json")
