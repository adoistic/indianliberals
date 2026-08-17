#!/usr/bin/env python3
"""Emit primary-works content entries for the Swatantra papers.

These are PROVISIONAL. Everything here is deterministic — filename-derived date
and correspondent, measured scan condition — because the llm-extract run that
produces real titles, summaries and themes is ~25,700 dispatches and has not
been done. The point is to make 6,355 documents findable and readable on the
site now, with the extraction pass enriching them in place later.

Honesty markers, so nothing here can be mistaken for extracted metadata:
  needs_review: true
  authors_resolution.method: deterministic     (a schema enum that already exists)
  provenance.notes: filename-derived …
  no `summary`, and no `ai:` block — nothing was model-drafted

`scan_quality` is not a guess either: it maps the measured ink/background
separation band from inventory.tsv onto the schema's enum.

Idempotent. Refuses to touch any pre-existing entry it did not write itself.

    python3 scripts/swatantra/emit-content-entries.py [--limit N] [--dry-run]
                                                     [--only-ocrd]
"""
import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUTDIR = REPO / "apps/site/src/content/primary-works"
INVENTORY = REPO / "data/swatantra-papers/inventory.tsv"
FILEMETA = REPO / "data/swatantra-papers/filename-metadata.tsv"
OCR = REPO / "data/swatantra-papers/ocr/corpus.jsonl"
ARCHIVE = "https://archive.indianliberals.in"
PREFIX = "swatantra-party-papers"
MARKER = "filename-derived; awaiting llm-extract enrichment"

# Measured legibility band -> the schema's scan_quality enum.
SCAN_QUALITY = {"strong": "good", "adequate": "fair", "weak": "fair", "faint": "poor"}


def y(v):
    """YAML-safe scalar. JSON is a YAML subset, so this quotes correctly."""
    return json.dumps(v, ensure_ascii=False)


def build(row, meta, has_ocr):
    slug = Path(row["_slug"]).stem
    key = f"{PREFIX}/{slug}.pdf"
    year = meta.get("year", "")
    year_i = int(year) if year.isdigit() else None
    work_type = meta.get("work_type_suggest") or "letter"
    tid = meta.get("thinker_id") or ""
    band = row.get("legibility", "")

    L = ["---"]
    L.append(f"id: {slug}")
    L.append("title:")
    L.append(f"  main: {y(meta['_title'])}")
    L.append('  subtitle: ""')
    L.append(f"work_type: {work_type}")
    L.append("authors:")
    if tid:
        L.append(f"  - {tid}")
    else:
        L[-1] = "authors: []"
    L.append("editors: []")
    L.append("contributors: []")
    L.append("related_thinkers: []")
    L.append("publication:")
    L.append("  language: en")
    L.append("  issuer_id: swatantra-party")
    L.append('  publisher_name: "Swatantra Party"')
    if year_i:
        L.append(f"  year: {year_i}")
    L.append("provenance:")
    L.append("  source: ccs_archive")
    L.append(f"  scan_quality: {SCAN_QUALITY.get(band, 'unknown')}")
    L.append(f"  notes: {y(MARKER)}")
    L.append("physical:")
    L.append(f"  pages_total: {row['pages']}")
    L.append("  pages_total_source: pypdfium2")
    L.append(f"pdf_url: {ARCHIVE}/{key}")
    L.append("rights:")
    L.append("  status: takedown_on_request")
    L.append("  license: in-copyright")
    L.append("  license_url: null")
    L.append("  rights_statement: Rights held by original depositors / Centre for "
             "Civil Society; reproduced for archival access.")
    L.append("themes: []")
    L.append("authors_resolution:")
    L.append("  method: deterministic")
    L.append(f"  confidence: {'medium' if tid else 'low'}")
    L.append("  proposed_unknowns: []")
    if meta.get("correspondent_verbatim") and not tid:
        L.append(f"  # unresolved correspondent: {meta['correspondent_verbatim']}")
    L.append("needs_review: true")
    L.append("draft: false")
    L.append("---")
    L.append("")

    date = meta.get("date") or ""
    bits = [b for b in (
        f"Archive item {meta.get('archive_id','')}" if meta.get("archive_id") else "",
        f"dated {date}" if date else "",
        f"{row['pages']} page{'s' if row['pages'] != '1' else ''}",
    ) if b]
    L.append(f"{'; '.join(bits)}. Scanned document from the Swatantra Party papers.")
    L.append("")
    L.append("Catalogue metadata on this item is provisional and derived from the "
             "archival filename; it has not yet been read from the document itself. "
             + ("The full text is searchable." if has_ocr
                else "The page text is not yet indexed."))
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-ocrd", action="store_true",
                    help="Emit only for documents whose OCR has completed.")
    a = ap.parse_args()

    inv = {r["file"]: r for r in csv.DictReader(open(INVENTORY, encoding="utf-8"), delimiter="\t")}
    fm = {r["file"]: r for r in csv.DictReader(open(FILEMETA, encoding="utf-8"), delimiter="\t")}

    ocrd = set()
    if OCR.exists():
        for line in open(OCR, encoding="utf-8"):
            try:
                ocrd.add(json.loads(line)["file"])
            except (json.JSONDecodeError, KeyError):
                continue

    sys.path.insert(0, str(REPO / "scripts/swatantra"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("o", REPO / "scripts/swatantra/ocr-pages.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    names = sorted(inv)
    if a.only_ocrd:
        names = [n for n in names if n in ocrd]
    if a.limit:
        names = names[:a.limit]

    written = skipped = foreign = 0
    for name in names:
        row = dict(inv[name])
        row["_slug"] = m.slugify(name) + ".pdf"
        meta = dict(fm.get(name, {}))
        meta["_title"] = title_of(name)
        path = OUTDIR / f"{m.slugify(name)}.md"

        if path.exists() and MARKER not in path.read_text(encoding="utf-8"):
            print(f"  REFUSING to overwrite non-generated entry: {path.name}", file=sys.stderr)
            foreign += 1
            continue

        body = build(row, meta, name in ocrd)
        if a.dry_run:
            if written < 1:
                print(body)
            written += 1
            continue
        if path.exists() and path.read_text(encoding="utf-8") == body:
            skipped += 1
            continue
        path.write_text(body, encoding="utf-8")
        written += 1

    print(f"{'would write' if a.dry_run else 'wrote'} {written}, unchanged {skipped}, "
          f"refused {foreign}  (of {len(names)} considered)")
    return 0


def title_of(name):
    import re
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = re.sub(r"^\d+[A-Za-z]?-", "", stem)
    stem = re.sub(r"_(\d{2})-(\d{2})-(\d{4})$", "", stem)
    return stem.replace("_", " ").strip() or "Untitled document"


if __name__ == "__main__":
    sys.exit(main())
