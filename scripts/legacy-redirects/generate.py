#!/usr/bin/env python3
"""Regenerate apps/site/functions/_legacy/map.json — the legacy-WordPress
redirect map.

Sources joined, in priority order:
  1. data/prod-mirror/inventory.jsonl  — old /content/<slug>/ pages with their
     PDF URLs (pdf path == R2 key, so this join is exact).
  2. data/pdf-link-manifest*.tsv       — hand-verified md_slug <-> prod_slug.
  3. Slug/normalised/fuzzy matching against every content collection
     (primary-works, thinkers, musings, opinions, interviews, organisations).
  4. HEAD-check on R2 for orphan PDFs (old page whose PDF exists but was
     never ingested as a work → redirect straight to the PDF).
  5. data/legacy/wayback-cdx-urls.txt  — the Wayback CDX snapshot of every
     crawled legacy URL (adds slugs missing from the inventory).

Anything still unmatched falls back per-periodical (see FALLBACK_LANDING) and
known WP spam/demo slugs get a 410 via the "gone" list.

Run after ingesting new works so old URLs upgrade from section fallbacks to
exact redirects:

    python3 scripts/legacy-redirects/generate.py

The existing map.json's manual entries (fallback/gone) are preserved unless
a better exact match is found.
"""
import json
import os
import re
import sys
import difflib
import concurrent.futures as cf
import urllib.request
from urllib.parse import urlparse, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTENT = os.path.join(ROOT, "apps/site/src/content")
MAP_PATH = os.path.join(ROOT, "apps/site/functions/_legacy/map.json")
R2 = "https://pub-f1430c20cc1c400da542453c56d614c8.r2.dev/"

FALLBACK_LANDING = {
    "forum-of-free-enterprise": "/organisations/forum-of-free-enterprise/",
    "freedom-first": "/periodicals/freedom-first/",
    "the-indian-libertarian": "/periodicals/indian-libertarian/",
    "khoj": "/periodicals/khoj/",
    "liberal-times": "/periodicals/liberal-times/",
    "shetkari-sanghatak": "/periodicals/shetkari-sanghatak/",
    "indian-liberal-group": "/periodicals/indian-liberal-group/",
    "swatantra-party": "/primary-works/",
    "other-publications": "/primary-works/",
}

COLLECTIONS = {
    "primary-works": "/primary-works/",
    "thinkers": "/thinkers/",
    "musings": "/musings/",
    "opinions": "/opinions/",
    "interviews": "/interviews/",
    "organisations": "/organisations/",
}


def norm(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    s = re.sub(r"-by-[a-z-]+$", "", s)
    s = re.sub(
        r"-(january|february|march|april|may|june|july|august|september|october"
        r"|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)[-0-9]*$",
        "", s)
    s = re.sub(r"-\d{1,2}-\d{4}$", "", s)
    s = re.sub(r"-\d{4}(-\d)?$", "", s)
    return s


def pdf_path(u):
    if not u:
        return None
    return unquote(urlparse(u).path).lstrip("/").lower() or None


def load_collections():
    """slug/norm-slug → new path, plus primary-work pdf paths and basenames."""
    slug_map, md_by_pdf, md_base = {}, {}, {}
    for coll, prefix in COLLECTIONS.items():
        d = os.path.join(CONTENT, coll)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not re.search(r"\.mdx?$", fn):
                continue
            slug = re.sub(r"\.mdx?$", "", fn)
            path = prefix + slug + "/"
            slug_map.setdefault(slug, path)
            slug_map.setdefault(norm(slug), path)
            if coll == "primary-works":
                head = open(os.path.join(d, fn), encoding="utf-8").read(4000)
                m = re.search(r"^pdf_url:\s*(\S+)", head, re.M)
                if m:
                    pp = pdf_path(m.group(1))
                    md_by_pdf[pp] = path
                    md_base[path] = re.sub(r"\.pdf$", "", pp.rsplit("/", 1)[-1])
    return slug_map, md_by_pdf, md_base


def main():
    slug_map, md_by_pdf, md_base = load_collections()
    keys = list(slug_map.keys())

    prev = {"exact": {}, "fallback": {}, "gone": [], "translated": []}
    if os.path.exists(MAP_PATH):
        prev = json.load(open(MAP_PATH))

    inv = [json.loads(l) for l in open(os.path.join(ROOT, "data/prod-mirror/inventory.jsonl"))]
    inv_by_slug = {d["prod_slug"]: d for d in inv}

    # legacy slug universe = inventory + CDX /content/ slugs (any language)
    legacy = set(inv_by_slug)
    cdx_file = os.path.join(ROOT, "data/legacy/wayback-cdx-urls.txt")
    if os.path.exists(cdx_file):
        for line in open(cdx_file):
            m = re.match(
                r"https?://(?:www\.)?indianliberals\.in(?:/(?:bn|gj|hi|mr))?/content/([^/?#]+)/?\s",
                line + " ")
            if m:
                legacy.add(unquote(m.group(1)).lower())

    exact, fallback = {}, dict(prev.get("fallback", {}))
    gone = set(prev.get("gone", []))
    unmatched_with_pdf = {}

    for ps in sorted(legacy):
        if ps in gone:
            continue
        d = inv_by_slug.get(ps, {})
        pp = pdf_path(d.get("pdf_url"))
        n = norm(ps)
        target = (
            md_by_pdf.get(pp)
            or slug_map.get(ps)
            or slug_map.get(n)
        )
        if not target:
            hits = difflib.get_close_matches(n, keys, n=1, cutoff=0.87)
            if hits:
                target = slug_map[hits[0]]
        if not target and pp:
            base = re.sub(r"\.pdf$", "", pp.rsplit("/", 1)[-1])
            hits = difflib.get_close_matches(base, list(md_base.values()), n=1, cutoff=0.85)
            if hits:
                target = next(p for p, b in md_base.items() if b == hits[0])
        if target:
            exact[ps] = target
        elif pp:
            unmatched_with_pdf[ps] = pp
        elif d.get("periodical") in FALLBACK_LANDING:
            fallback.setdefault(ps, FALLBACK_LANDING[d["periodical"]])

    # orphan PDFs that exist on R2 → link old page straight to the PDF
    def head(item):
        ps, pp = item
        req = urllib.request.Request(
            R2 + pp.replace(" ", "%20"), method="HEAD",
            headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return ps, pp, r.status
        except Exception as e:
            return ps, pp, getattr(e, "code", 0)

    with cf.ThreadPoolExecutor(12) as ex:
        for ps, pp, st in ex.map(head, unmatched_with_pdf.items()):
            if st == 200:
                exact[ps] = R2 + pp.replace(" ", "%20")
            else:
                d = inv_by_slug.get(ps, {})
                if d.get("periodical") in FALLBACK_LANDING:
                    fallback.setdefault(ps, FALLBACK_LANDING[d["periodical"]])

    # keep prior exact entries (manual fixes) that this run didn't reproduce
    for k, v in prev.get("exact", {}).items():
        exact.setdefault(k, v)
    # an exact match beats a stale fallback
    for k in list(fallback):
        if k in exact:
            del fallback[k]

    # translated-page set for the language hop, from the live sitemap
    translated = prev.get("translated", [])
    try:
        req = urllib.request.Request(
            "https://indianliberals.in/sitemap-0.xml",
            headers={"User-Agent": "Mozilla/5.0"})
        sm = urllib.request.urlopen(req, timeout=30).read().decode()
        translated = sorted(set(
            re.findall(r"<loc>https://indianliberals\.in(/(?:mr|gu|hi)/[^<]+)</loc>", sm)))
    except Exception as e:
        print(f"warn: sitemap fetch failed ({e}); keeping previous translated set",
              file=sys.stderr)

    out = {"exact": exact, "fallback": fallback, "gone": sorted(gone),
           "translated": translated}
    json.dump(out, open(MAP_PATH, "w"), indent=0, sort_keys=True)
    print(f"map.json: {len(exact)} exact, {len(fallback)} fallback, "
          f"{len(gone)} gone, {len(translated)} translated")


if __name__ == "__main__":
    main()
