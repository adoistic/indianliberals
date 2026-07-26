#!/usr/bin/env python3
"""Merge duplicate primary-work records that point at the same source PDF.

Why a merge and not a delete
----------------------------
13 PDFs were ingested twice under different slugs. Two of those pairs turned
out to be *distinct works* that share one combined scan, so they are excluded
by name below — deleting either would lose a real work.

For the remaining 11, neither record dominates. Typically one has the richer
AI summary while the other has the better bibliography: native-script title,
the real publication year, the publisher's imprint. e.g. `angarmala`:

  angarmala-by-sharad-joshi : summary 2483 chars, title "Angarmala by Sharad
                              Joshi", year 2016 (the scan year), no publisher
  angarmala-sharad-joshi    : summary 1121 chars, title "अंगारमळा" with
                              original_script + translit, year 2008, full
                              Marathi publisher imprint

Dropping either loses something. So we merge field by field, then keep ONE
slug and redirect the other.

Survivor slug = the one matching the PDF basename. That is the canonical name,
and it is the slug the CCS source-batch reconciliation already maps to, so
that verification stays valid.
"""

import json
import os
import re
import sys

import yaml

# Same PDF, but genuinely two different works (a combined scan). Never merge.
EXCLUDE_PDFS = {
    "basic-documents-forum-of-free-enterprise-july-18-1956.pdf",
    "the-central-budget-2004-2005-vis-a-vis-the-liberal-budget-various-july-18-2004.pdf",
}

FM = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


def load(path):
    text = open(path, encoding="utf-8").read()
    m = FM.match(text)
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def richer_title(a, b):
    """Prefer a title carrying original_script (proper native cataloguing)."""
    for t in (a, b):
        if isinstance(t, dict) and t.get("original_script"):
            return t
    return a if len(str(a)) >= len(str(b)) else b


def pick_year(a_fm, b_fm):
    """Prefer the year from whichever record is better catalogued.

    A record with original_script or a publisher imprint was catalogued from
    the title page, so its year is the real publication year rather than the
    scan/upload year.
    """
    def catalogued(fm):
        t = fm.get("title") or {}
        pub = fm.get("publication") or {}
        return bool((isinstance(t, dict) and t.get("original_script")) or pub.get("publisher_name"))

    ay = (a_fm.get("publication") or {}).get("year")
    by = (b_fm.get("publication") or {}).get("year")
    if ay is None:
        return by
    if by is None:
        return ay
    if ay == by:
        return ay
    if catalogued(a_fm) and not catalogued(b_fm):
        return ay
    if catalogued(b_fm) and not catalogued(a_fm):
        return by
    return min(ay, by)  # both catalogued: the earlier is the original edition


def key_points(body):
    m = re.search(r"^## Key points\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    return len(re.findall(r"^- ", m.group(1), re.M)) if m else 0


def merge(sur_fm, sur_body, oth_fm, oth_body):
    out = dict(sur_fm)

    out["title"] = richer_title(sur_fm.get("title"), oth_fm.get("title"))

    pub = dict(sur_fm.get("publication") or {})
    opub = oth_fm.get("publication") or {}
    for f in ("publisher_id", "publisher_name", "issuer_id", "place", "edition", "series", "series_id"):
        if not pub.get(f) and opub.get(f):
            pub[f] = opub[f]
    y = pick_year(sur_fm, oth_fm)
    if y is not None:
        pub["year"] = y
    out["publication"] = pub

    # union of themes, order-stable
    seen, themes = set(), []
    for t in (sur_fm.get("themes") or []) + (oth_fm.get("themes") or []):
        if t not in seen:
            seen.add(t)
            themes.append(t)
    if themes:
        out["themes"] = themes

    for f in ("authors", "editors", "contributors", "related_thinkers", "thinker_mentions"):
        if len(oth_fm.get(f) or []) > len(sur_fm.get(f) or []):
            out[f] = oth_fm[f]

    for f in ("language", "cover_image", "youtube_url", "purpose", "physical", "identifiers"):
        if not out.get(f) and oth_fm.get(f):
            out[f] = oth_fm[f]

    if len((oth_fm.get("summary") or "")) > len((sur_fm.get("summary") or "")):
        out["summary"] = oth_fm["summary"]

    # body: keep whichever is more complete (key-point count first, then length)
    body = sur_body
    if (key_points(oth_body), len(oth_body)) > (key_points(sur_body), len(sur_body)):
        body = oth_body

    return out, body


def main():
    ap_dir = "apps/site/src/content/primary-works"
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    apply = "--apply" in sys.argv

    redirects, merged = [], 0
    for p in plan:
        if p["pdf"] in EXCLUDE_PDFS:
            continue
        ids = [p["keep"]] + p["drop"]
        base = re.sub(r"\.pdf$", "", p["pdf"])
        survivor = next((i for i in ids if i == base), None) or p["keep"]
        others = [i for i in ids if i != survivor]

        s_path = os.path.join(ap_dir, survivor + ".md")
        s_fm, s_body = load(s_path)
        for o in others:
            o_fm, o_body = load(os.path.join(ap_dir, o + ".md"))
            s_fm, s_body = merge(s_fm, s_body, o_fm, o_body)
            redirects.append((o, survivor))

        print(f"{survivor}")
        print(f"    title  -> {s_fm.get('title')}")
        print(f"    year   -> {(s_fm.get('publication') or {}).get('year')}"
              f" | publisher -> {str((s_fm.get('publication') or {}).get('publisher_name'))[:44]}")
        print(f"    themes -> {len(s_fm.get('themes') or [])} | kp -> {key_points(s_body)}"
              f" | absorbs -> {others}")
        merged += 1

        if apply:
            with open(s_path, "w", encoding="utf-8") as fh:
                fh.write("---\n" + yaml.safe_dump(s_fm, allow_unicode=True, sort_keys=False).rstrip()
                         + "\n---\n" + s_body)
            for o in others:
                os.remove(os.path.join(ap_dir, o + ".md"))

    print(f"\n{'merged' if apply else 'would merge'}: {merged} pairs | "
          f"{'removed' if apply else 'would remove'}: {len(redirects)} duplicate records")
    if apply:
        json.dump([{"from": a, "to": b} for a, b in redirects],
                  open("scripts/dedupe/redirects.json", "w"), indent=1)
        print("wrote scripts/dedupe/redirects.json")


if __name__ == "__main__":
    main()
