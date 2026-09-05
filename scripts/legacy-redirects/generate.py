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

Re-running is safe. An entry already in map.json is only rewritten when the
legacy slug is itself a work's slug, which is a one-to-one match; a PDF-path
join or a fuzzy match may fill a slug that has no entry yet, but neither
overrules one that has. That
rule is what keeps a re-run from churning decided redirects every time the
archive grows, since difflib compares against every work in it. The summary
line at the end says how many entries were added, corrected and declined.
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
R2 = "https://archive.indianliberals.in/"

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
    """slug/norm-slug → new path, plus primary-work pdf paths and basenames.

    `real_slugs` is kept apart from `slug_map`: it holds only the slugs works
    actually have, each with every collection it occurs in, and it is the one
    structure here whose matches are one to one. `slug_map` mixes those with
    normalised forms, where a whole run of a periodical shares one key.
    """
    slug_map, md_by_pdf, md_base = {}, {}, {}
    real_slugs = {}
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
            real_slugs.setdefault(slug, []).append(path)
            if coll == "primary-works":
                head = open(os.path.join(d, fn), encoding="utf-8").read(4000)
                m = re.search(r"^pdf_url:\s*(\S+)", head, re.M)
                if m:
                    pp = pdf_path(m.group(1))
                    md_by_pdf[pp] = path
                    md_base[path] = re.sub(r"\.pdf$", "", pp.rsplit("/", 1)[-1])
    return slug_map, md_by_pdf, md_base, real_slugs


def main():
    slug_map, md_by_pdf, md_base, real_slugs = load_collections()
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
    # Slugs whose target this run guessed with difflib rather than joined on
    # a PDF path or a slug. A guess is good enough to fill an empty space and
    # never good enough to overrule a decision already in the map: see the
    # merge below, and the note at the top of this file.
    guessed = set()
    # Slugs matched to a work because the legacy slug is the work's slug.
    # That join is the only one here that is one to one, and it is therefore
    # the only one allowed to correct an entry already in the map.
    #
    # The other two collapse. A PDF-path join maps several old pages onto one
    # work whenever they carried the same PDF link. And norm() strips the
    # trailing month and year, so every issue of a run normalises to the same
    # key: `shetkari-sanghatak-dec-6-1993` and `-june-6-1993` both become
    # `shetkari-sanghatak`, and the lookup returns whichever issue happens to
    # hold that key. That is how twelve Shetkari Sanghatak slugs and three
    # Indian Libertarian slugs came to point at one unrelated issue each.
    # Both joins still fill a slug that has nothing, where any issue of the
    # right run beats a 404.
    joined_by_slug = set()

    for ps in sorted(legacy):
        if ps in gone:
            continue
        d = inv_by_slug.get(ps, {})
        pp = pdf_path(d.get("pdf_url"))
        n = norm(ps)
        # One to one only when the legacy slug is a slug some work really
        # has, and only one work has it. Two collections holding the same
        # slug is a tie this script cannot break, so it leaves the standing
        # entry alone rather than picking by directory order.
        hits = real_slugs.get(ps, [])
        by_slug = hits[0] if len(hits) == 1 else None
        target = md_by_pdf.get(pp) or slug_map.get(ps) or slug_map.get(n)
        if by_slug and target == by_slug:
            joined_by_slug.add(ps)
        if not target:
            hits = difflib.get_close_matches(n, keys, n=1, cutoff=0.87)
            if hits:
                target = slug_map[hits[0]]
                guessed.add(ps)
        if not target and pp:
            base = re.sub(r"\.pdf$", "", pp.rsplit("/", 1)[-1])
            hits = difflib.get_close_matches(base, list(md_base.values()), n=1, cutoff=0.85)
            if hits:
                target = next(p for p, b in md_base.items() if b == hits[0])
                guessed.add(ps)
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

    # ── Merge with what is already in the map ────────────────────────
    #
    # Every entry in the map is a decision that somebody has, at minimum,
    # lived with. Re-running this script must therefore add and correct, and
    # must not reshuffle. The difference that matters is how a target was
    # arrived at:
    #
    #   by slug  the legacy slug is the work's slug. One to one, so it is
    #            good enough to correct an entry that is already there.
    #   collapsed a PDF-path or normalised-slug join. Both map many legacy
    #            slugs onto one work, so they fill an empty slot and must not
    #            overrule a standing entry.
    #   guessed  difflib found something within its cutoff. Good enough for
    #            a slug with nothing at all, never good enough to overrule.
    #
    # Without this distinction a re-run rewrites decided entries with fresh
    # guesses, and because difflib compares against every work in the
    # archive, the guesses move every time content is ingested. One run in
    # September 2026 changed sixty entries this way, several for the worse:
    # a Freedom First issue was re-pointed at the Forum of Free Enterprise,
    # and three Shetkari Sanghatak issues to a fourth issue's page.
    prev_exact = prev.get("exact", {})
    prev_fallback = prev.get("fallback", {})
    decided = set(prev_exact) | set(prev_fallback)

    added, upgraded, kept_guess = 0, 0, 0
    merged = dict(prev_exact)
    for k, v in exact.items():
        if k not in decided:
            merged[k] = v
            added += 1
        elif k not in joined_by_slug:
            kept_guess += 1                      # leave the standing entry alone
        elif prev_exact.get(k) != v:
            merged[k] = v
            upgraded += 1
    exact = merged

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
    print(f"  this run: {added} newly matched, {upgraded} corrected by a slug join, "
          f"{kept_guess} weaker matches declined in favour of the standing entry")


if __name__ == "__main__":
    main()
