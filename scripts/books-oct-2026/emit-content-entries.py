#!/usr/bin/env python3
"""Emit primary-works content entries for the October 2026 book tranche.

Unlike `scripts/swatantra/emit-content-entries.py`, these entries are NOT
provisional: both pipeline passes ran on every one of the twelve works, so the
titles, publishers, years, themes, summaries, pull quotes and cross-thinker
mentions here are extracted rather than filename-derived.

Two things this script does that the Swatantra emitter did not have to:

1. **It validates every schema `reference()` before writing it.** `authors`,
   `editors`, `contributors[].thinker`, `related_thinkers`, `series_id`,
   `essays_summarized[].author_resolved` and — the one that actually bit —
   `summary_structured.cross_thinker_mentions[].thinker_id` are all Astro
   references, so an id that is not a file in the target collection fails the
   whole build. The summarisation subagents resolved against the authority
   *file*, which is not the same set as the `thinkers/` *collection*, and they
   also resolved organisations (`swatantra-party`, `tata-sons`) into a field
   typed as a thinkers reference. Anything that does not resolve is demoted to
   the matching `*_unresolved` string field rather than dropped, so the
   evidence survives for a later resolution pass.

2. **It records the edition chain.** Four of these works are a second
   manifestation of something the archive already holds or of another work in
   the same batch. The schema's FRBR-lite `manifestations[]` plus
   `related_works[]` carry that, so /primary-works/our-india/ and
   /primary-works/our-india-oup-1975/ can both exist honestly instead of one
   silently overwriting the other.

Idempotent, and it refuses to touch an entry it did not write itself.

    python3 scripts/books-oct-2026/emit-content-entries.py [--dry-run]
"""
import argparse
import csv
import glob
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTENT = REPO / "apps/site/src/content"
OUTDIR = CONTENT / "primary-works"
MANIFEST = REPO / "data/books-oct-2026/manifest.tsv"
BAKEOUT = REPO / "data/bake-off-output"
SUMMARY_REQ = Path("/tmp/llm-extract-requests/summary")
PDF_ROOT = Path(os.environ.get("LLM_EXTRACT_PDF_ROOT", "/Users/siraj/Downloads/BOOKS FINAL DATA"))
ARCHIVE = "https://archive.indianliberals.in"
MARKER = "books-oct-2026"

# Series membership. Editorial, not extracted: the books print a series
# statement but nothing tells the pipeline which `series/` entity it maps to.
SERIES = {
    "our-growing-human-family-ilg-2007": "indian-liberal-group",
    "terrorism-v-balachandran-2005": "indian-liberal-group",
    "minoo-masani-nbt-2007": "national-biography-nbt",
    "minoo-masani-nbt-hindi-2010": "national-biography-nbt",
}

# Cross-links between manifestations of the same work, and to the records the
# archive already holds. Editorial decision (Adnan, 2026-10-16): add the better
# scans as separate edition records and cross-link them, rather than
# overwriting the thinner records already published at their own URLs.
RELATED = {
    "our-india-oup-1975": ["our-india", "hamara-hindustan"],
    "we-indians-oup-1989": ["we-indians-minoo-masani-1989"],
    "our-growing-human-family-ilg-2007": ["the-growing-human-family-oup-1951"],
    "the-growing-human-family-oup-1951": ["our-growing-human-family-ilg-2007"],
    "minoo-masani-nbt-2007": ["minoo-masani-nbt-hindi-2010"],
    "minoo-masani-nbt-hindi-2010": ["minoo-masani-nbt-2007"],
}

# Printing histories transcribed from the copyright pages. Only where the page
# actually prints a chain — an invented chain is worse than none.
MANIFESTATIONS = {
    "our-india-oup-1975": [
        {"year": 1940, "publisher_name": "Oxford University Press", "place": "Calcutta",
         "edition": "Our India, first published October 1940"},
        {"year": 1953, "publisher_name": "Oxford University Press", "place": "Calcutta",
         "edition": "Our India-1953, first published September 1953"},
        {"year": 1954, "publisher_name": "Oxford University Press", "place": "Calcutta",
         "edition": "First cheap edition, June 1954"},
        {"year": 1975, "publisher_name": "Oxford University Press", "place": "Calcutta",
         "edition": "Eighth impression 1975"},
    ],
    "our-growing-human-family-ilg-2007": [
        {"year": 1950, "publisher_name": "Oxford University Press", "edition": "First Printing"},
        {"year": 1953, "publisher_name": "Oxford University Press", "edition": "Second Printing"},
        {"year": 2007, "publisher_name": "Indian Liberal Group", "place": "Mumbai",
         "edition": "Third Printing, 2007"},
    ],
    "the-growing-human-family-oup-1951": [
        {"year": 1951, "publisher_name": "Oxford University Press Inc.", "place": "New York",
         "edition": "Copyright 1951"},
        {"year": 1953, "publisher_name": "Oxford University Press Inc.", "place": "New York",
         "edition": "Second Printing, 1953"},
    ],
}


def collection_ids(name):
    return {Path(p).stem for p in glob.glob(str(CONTENT / name / "*.md"))}


THINKERS = collection_ids("thinkers")
ORGS = collection_ids("organisations")
SERIES_IDS = collection_ids("series")


def y(v):
    """YAML-safe scalar. JSON is a YAML subset, so this quotes correctly."""
    return json.dumps(v, ensure_ascii=False)


def unwrap(v):
    """Metadata fields are {value, confidence} dicts; summary fields are bare."""
    if isinstance(v, dict) and "value" in v:
        return v["value"]
    return v


def load(slug_row):
    stem = slug_row["source_pdf"][:-4]
    meta = json.loads((BAKEOUT / stem / "metadata.a.a.json").read_text(encoding="utf-8"))
    # Prefer the collected record under data/bake-off-output/ — /tmp request
    # dirs are transient, and the collected copy is what the ledger points at.
    summ = None
    for cand in ("summary.none.json", "summary.json"):
        f = BAKEOUT / stem / cand
        if f.exists():
            summ = json.loads(f.read_text(encoding="utf-8"))
            break
    if summ is None:
        hits = glob.glob(str(SUMMARY_REQ / f"{stem}-chunk0-*" / "response.json"))
        if hits:
            summ = json.loads(Path(hits[0]).read_text(encoding="utf-8"))
    return meta, summ


def emit(row, stats):
    slug = row["slug"]
    meta, summ = load(row)
    pub = meta.get("publication") or {}
    phys = meta.get("physical") or {}
    ident = meta.get("identifiers") or {}
    ss = (summ or {}).get("summary_structured") or {}

    L = ["---", f"id: {slug}"]

    # ── title ────────────────────────────────────────────────────────────
    t = meta.get("title") or {}
    L.append("title:")
    L.append(f"  main: {y(unwrap(t.get('main')) or slug)}")
    sub = unwrap(t.get("subtitle"))
    L.append(f"  subtitle: {y(sub or '')}")
    if t.get("original_script"):
        L.append(f"  original_script: {y(t['original_script'])}")
    if t.get("translit"):
        L.append(f"  translit: {y(t['translit'])}")

    L.append(f"work_type: {meta.get('work_type') or 'book'}")
    if meta.get("purpose"):
        L.append(f"purpose: {meta['purpose']}")

    # ── authors / editors: must resolve to thinkers OR organisations ─────
    def people(key):
        out, unresolved = [], []
        for a in meta.get(key) or []:
            tid = a.get("thinker_id")
            if tid and (tid in THINKERS or tid in ORGS):
                out.append(tid)
            else:
                v = a.get("byline_verbatim")
                if v:
                    unresolved.append(v)
                if tid:
                    stats["demoted_refs"].append(f"{slug}:{key}:{tid}")
        return out, unresolved

    authors, authors_unres = people("authors")
    editors, editors_unres = people("editors")
    for key, vals in (("authors", authors), ("editors", editors)):
        if vals:
            L.append(f"{key}:")
            L += [f"  - {v}" for v in vals]
        else:
            L.append(f"{key}: []")

    # ── contributors: thinker is a reference, thinker_unresolved is free ─
    contribs = meta.get("contributors") or []
    if contribs:
        L.append("contributors:")
        for c in contribs:
            tid = c.get("thinker_id") or c.get("thinker")
            L.append(f"  - role: {y(c.get('role') or 'other')}")
            if tid and tid in THINKERS:
                L.append(f"    thinker: {tid}")
            else:
                if tid and tid not in THINKERS:
                    stats["demoted_refs"].append(f"{slug}:contributor:{tid}")
                name = c.get("byline_verbatim") or c.get("thinker_unresolved") or tid
                L.append(f"    thinker_unresolved: {y(name)}" if name
                         else "    thinker_unresolved: null")
            if isinstance(c.get("toc_index"), int):
                L.append(f"    toc_index: {c['toc_index']}")
    else:
        L.append("contributors: []")

    # ── publication ──────────────────────────────────────────────────────
    L.append("publication:")
    if pub.get("publisher_id"):
        L.append(f"  publisher_id: {y(pub['publisher_id'])}")
    pname = pub.get("publisher_verbatim") or pub.get("publisher_name")
    if pname:
        L.append(f"  publisher_name: {y(pname)}")
    if pub.get("issuer_id"):
        L.append(f"  issuer_id: {y(pub['issuer_id'])}")
    if pub.get("place"):
        L.append(f"  place: {y(pub['place'])}")
    yr = unwrap(pub.get("year"))
    L.append(f"  year: {yr if isinstance(yr, int) else 'null'}")
    if pub.get("edition"):
        L.append(f"  edition: {y(pub['edition'])}")
    if pub.get("series"):
        L.append(f"  series: {y(pub['series'])}")
    sid = SERIES.get(slug)
    if sid:
        if sid in SERIES_IDS:
            L.append(f"  series_id: {sid}")
        else:
            stats["demoted_refs"].append(f"{slug}:series_id:{sid}")
    L.append(f"  language: {y(pub.get('language') or meta.get('language') or 'en')}")

    # ── physical / identifiers / provenance ──────────────────────────────
    L.append("physical:")
    for k in ("pages_rendered", "pages_total"):
        if isinstance(phys.get(k), int):
            L.append(f"  {k}: {phys[k]}")
    if phys.get("pages_total_source"):
        L.append(f"  pages_total_source: {phys['pages_total_source']}")
    if phys.get("format"):
        L.append(f"  format: {y(phys['format'])}")

    isbn = ident.get("isbn")
    if isbn:
        L.append("identifiers:")
        L.append(f"  isbn: {y(isbn)}")

    L.append("provenance:")
    L.append("  source: ccs_archive")
    L.append("  scan_quality: good")
    L.append(f"  notes: {y('Scanned at 300 dpi with no text layer; full-text OCR added 2026-10-16 (Tesseract 5.5.2, Sauvola binarisation). See data/books-oct-2026/.')}")

    L.append("rights:")
    L.append("  status: takedown_on_request")
    L.append("  editorial_review_flag: true")
    L.append(f"  notes: {y('In copyright. Rights held by the original publishers and authors; reproduced for archival access.')}")

    # ── themes ───────────────────────────────────────────────────────────
    themes = []
    for t_ in (meta.get("themes") or []) + (ss.get("themes_confirmed") or []):
        if isinstance(t_, str) and t_ not in themes:
            themes.append(t_)
    if themes:
        L.append("themes:")
        L += [f"  - {t_}" for t_ in themes]
    else:
        L.append("themes: []")

    # ── summary + structured payload ─────────────────────────────────────
    if summ and summ.get("summary"):
        L.append(f"summary: {y(summ['summary'])}")

    def quote_lines(lst, indent):
        """Render pullQuote[] at a given indent. Shared by the work-level
        payload and the per-essay payloads, which have identical shape."""
        out = []
        for q in lst or []:
            if not isinstance(q, dict) or not q.get("verbatim"):
                continue
            out.append(f"{indent}  - verbatim: {y(q['verbatim'])}")
            if isinstance(q.get("page"), int):
                out.append(f"{indent}    page: {q['page']}")
            if q.get("page_system"):
                out.append(f"{indent}    page_system: {q['page_system']}")
            wn = q.get("why_notable")
            out.append(f"{indent}    why_notable: {wn if wn in ('framing','aphorism','data','counter_intuitive') else 'framing'}")
            if q.get("context"):
                out.append(f"{indent}    context: {y(q['context'])}")
            if q.get("translation"):
                out.append(f"{indent}    translation: {y(q['translation'])}")
        return out

    def mentions(lst):
        rows, resolved = [], []
        for mm in lst or []:
            tid = mm.get("thinker_id")
            row = {}
            if tid and tid in THINKERS:
                row["thinker_id"] = tid
                resolved.append(tid)
            else:
                if tid:
                    stats["demoted_refs"].append(f"{slug}:mention:{tid}")
                v = mm.get("thinker_id_unresolved") or tid
                if v:
                    row["thinker_id_unresolved"] = v
            for k in ("context", "page", "page_system"):
                if mm.get(k) is not None:
                    row[k] = mm[k]
            if row:
                rows.append(row)
        return rows, resolved

    def mention_lines(rows, indent):
        out = []
        for r in rows:
            first = True
            for k, v in r.items():
                pre = f"{indent}  - " if first else f"{indent}    "
                if isinstance(v, int):
                    out.append(f"{pre}{k}: {v}")
                elif k in ("thinker_id", "page_system"):
                    out.append(f"{pre}{k}: {v}")
                else:
                    out.append(f"{pre}{k}: {y(v)}")
                first = False
        return out

    mrows, resolved_ids = mentions(ss.get("cross_thinker_mentions"))

    # Per-essay payloads are built here, ahead of `related_thinkers`, because
    # for an edited volume ALL the pull quotes and cross-thinker mentions live
    # nested inside essays_summarized[] rather than at the top level — books 01,
    # 11 and 12 carry 37, and 54 nested mentions respectively and nothing at the
    # work level. Rolling the resolved ids up into related_thinkers is what puts
    # these works on the contributors' bio pages.
    essay_lines = []
    for e in (summ or {}).get("essays_summarized") or []:
        if not isinstance(e, dict) or not isinstance(e.get("toc_index"), int) or not e.get("summary"):
            continue
        essay_lines.append(f"  - toc_index: {e['toc_index']}")
        ar = e.get("author_resolved")
        if ar and ar in THINKERS:
            essay_lines.append(f"    author_resolved: {ar}")
        else:
            if ar:
                stats["demoted_refs"].append(f"{slug}:essay_author:{ar}")
            au = e.get("author_unresolved") or ar
            if au:
                essay_lines.append(f"    author_unresolved: {y(au)}")
        essay_lines.append(f"    summary: {y(e['summary'])}")
        if e.get("partial_essay"):
            essay_lines.append("    partial_essay: true")
        es = e.get("summary_structured") or {}
        essay_lines.append("    summary_structured:")
        essay_lines.append(f"      complete: {str(bool(es.get('complete'))).lower()}")
        if isinstance(es.get("seen_through_page"), int):
            essay_lines.append(f"      seen_through_page: {es['seen_through_page']}")
        ekp = es.get("key_points") or []
        if ekp:
            essay_lines.append("      key_points:")
            essay_lines += [f"        - {y(k)}" for k in ekp]
        eq = quote_lines(es.get("pull_quotes"), "      ")
        if eq:
            essay_lines.append("      pull_quotes:")
            essay_lines += eq
        erows, eres = mentions(es.get("cross_thinker_mentions"))
        resolved_ids.extend(eres)
        if erows:
            essay_lines.append("      cross_thinker_mentions:")
            essay_lines += mention_lines(erows, "      ")
    if ss:
        L.append("summary_structured:")
        kp = ss.get("key_points") or []
        if kp:
            L.append("  key_points:")
            L += [f"    - {y(k)}" for k in kp]
        tc = ss.get("themes_confirmed") or []
        if tc:
            L.append("  themes_confirmed:")
            L += [f"    - {t_}" for t_ in tc]
        pq = quote_lines(ss.get("pull_quotes"), "  ")
        if pq:
            L.append("  pull_quotes:")
            L += pq
        if mrows:
            L.append("  cross_thinker_mentions:")
            L += mention_lines(mrows, "  ")
        sc = ss.get("summary_completeness")
        if isinstance(sc, dict) and isinstance(sc.get("based_on_pages"), list) and len(sc["based_on_pages"]) == 2:
            L.append("  summary_completeness:")
            L.append(f"    based_on_pages: [{sc['based_on_pages'][0]}, {sc['based_on_pages'][1]}]")
            L.append(f"    covers_full_work: {str(bool(sc.get('covers_full_work'))).lower()}")
            if sc.get("missing_content_note"):
                L.append(f"    missing_content_note: {y(sc['missing_content_note'])}")

    # related_thinkers drives the "works that mention X" section on bio pages.
    rt = sorted(set(resolved_ids))
    if rt:
        L.append("related_thinkers:")
        L += [f"  - {r}" for r in rt]

    # ── TOC (multi-author works) ─────────────────────────────────────────
    toc = meta.get("toc") or {}
    def toc_block(key):
        out = []
        for e in toc.get(key) or []:
            # Some passes emitted entries_not_yet_rendered as bare title strings
            # rather than tocEntry objects. The schema wants objects, and a bare
            # title carries no page anchor, so those are dropped here rather
            # than guessed at — the full TOC survives in `entries`.
            if not isinstance(e, dict):
                stats["dropped_toc_strings"] += 1
                continue
            if not isinstance(e.get("toc_index"), int) or not isinstance(e.get("page_start"), int):
                continue
            out.append(f"    - toc_index: {e['toc_index']}")
            out.append(f"      title: {y(e.get('title') or '')}")
            if e.get("byline_verbatim"):
                out.append(f"      byline_verbatim: {y(e['byline_verbatim'])}")
            out.append(f"      page_start: {e['page_start']}")
            if isinstance(e.get("page_end"), int):
                out.append(f"      page_end: {e['page_end']}")
            if e.get("page_system"):
                out.append(f"      page_system: {e['page_system']}")
        return out
    ent, notyet = toc_block("entries"), toc_block("entries_not_yet_rendered")
    if ent or notyet:
        L.append("toc:")
        if toc.get("extracted_from_pages"):
            L.append(f"  extracted_from_pages: {json.dumps(toc['extracted_from_pages'])}")
        if ent:
            L.append("  entries:")
            L += ent
        if notyet:
            L.append("  entries_not_yet_rendered:")
            L += notyet

    # ── per-essay summaries (edited volumes) ─────────────────────────────
    if essay_lines:
        L.append("essays_summarized:")
        L += essay_lines

    # ── edition chain + cross-links ──────────────────────────────────────
    man = MANIFESTATIONS.get(slug)
    if man:
        L.append("manifestations:")
        for m_ in man:
            L.append(f"  - year: {m_['year']}")
            L.append(f"    publisher_name: {y(m_['publisher_name'])}")
            if m_.get("place"):
                L.append(f"    place: {y(m_['place'])}")
            if m_.get("edition"):
                L.append(f"    edition: {y(m_['edition'])}")
    rel = RELATED.get(slug)
    if rel:
        L.append("related_works:")
        L += [f"  - {r}" for r in rel]

    # ── flags, provenance of the AI passes, assets ───────────────────────
    flags = meta.get("missing_metadata_flags") or []
    if flags:
        L.append("missing_metadata_flags:")
        L += [f"  - {y(f)}" for f in flags]

    raa = (meta.get("recommended_authority_additions") or []) + \
          ((summ or {}).get("recommended_authority_additions") or [])
    seen, dedup = set(), []
    for r in raa:
        k = (r.get("kind"), (r.get("verbatim") or "").strip().lower())
        if k in seen or not k[1]:
            continue
        seen.add(k)
        dedup.append(r)
    if dedup:
        L.append("recommended_authority_additions:")
        for r in dedup:
            kind = r.get("kind")
            L.append(f"  - kind: {kind if kind in ('thinker','publisher','organisation') else 'thinker'}")
            L.append(f"    verbatim: {y(r.get('verbatim'))}")
            if r.get("context"):
                L.append(f"    context: {y(r['context'])}")
            if isinstance(r.get("page"), int):
                L.append(f"    page: {r['page']}")
            if r.get("page_system"):
                L.append(f"    page_system: {r['page_system']}")

    ec = (summ or {}).get("extent_caveat")
    L.append(f"extent_caveat: {str(bool(ec)).lower() if not isinstance(ec, str) else y(ec)}")

    src = PDF_ROOT / row["source_pdf"]
    L.append(f"pdf_url: {ARCHIVE}/{row['r2_key']}")
    if src.exists():
        L.append(f"pdf_size_mb: {round(src.stat().st_size / 1_048_576, 2)}")
    L.append(f"cover_image: {y(f'{ARCHIVE}/covers/{slug}.webp')}")

    L.append("needs_review: true")
    L.append("draft: false")
    L.append("ai:")
    L.append("  drafted_by: claude-sonnet-4.5")
    L.append("  drafted_at: 2026-10-16")
    L.append("  model_version: v1.5")
    L.append("---")
    L.append("")
    L.append(f"# {unwrap(t.get('main')) or slug}")
    L.append("")
    if summ and summ.get("summary"):
        L.append("## Summary")
        L.append("")
        L.append(summ["summary"])
        L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    with open(MANIFEST, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    stats = {"demoted_refs": [], "written": 0, "skipped": 0, "missing_summary": [],
             "dropped_toc_strings": 0}
    for row in rows:
        dest = OUTDIR / f"{row['slug']}.md"
        if dest.exists() and MARKER not in dest.read_text(encoding="utf-8"):
            print(f"REFUSE (not ours): {dest.name}")
            stats["skipped"] += 1
            continue
        _, summ = load(row)
        if summ is None:
            stats["missing_summary"].append(row["slug"])
        body = emit(row, stats)
        if not a.dry_run:
            dest.write_text(body, encoding="utf-8")
        stats["written"] += 1
        print(f"{'would write' if a.dry_run else 'wrote'} {dest.name}  ({len(body)//1024} KB)")

    print(f"\nwritten={stats['written']} skipped={stats['skipped']}")
    if stats["missing_summary"]:
        print(f"NO SUMMARY YET: {stats['missing_summary']}")
    d = stats["demoted_refs"]
    print(f"dropped TOC entries that were bare strings: {stats['dropped_toc_strings']}")
    print(f"demoted references (id not in its target collection): {len(d)}")
    for x in d[:25]:
        print("  ", x)
    if len(d) > 25:
        print(f"   ... and {len(d)-25} more")


if __name__ == "__main__":
    main()
