#!/usr/bin/env python3
"""Build a works_meta.json for the Swatantra papers from deterministic data only.

`scripts/fulltext/build-index.mjs` joins `fulltext.jsonl` to a metas map keyed by
R2 object key. For the existing archive that map comes from primary-works
frontmatter via export-works-meta.py. The Swatantra papers have no frontmatter
yet — the extraction run that produces it is ~25,700 dispatches — so this builds
the same shape from what IS known without any model call:

    inventory.tsv          pages, legibility
    filename-metadata.tsv  date/year, correspondent -> thinker_id, genre -> work_type

Everything here is derived or measured. Nothing is inferred by a model, and
fields that cannot be known are left empty rather than guessed — `title` falls
back to the archival ID, which is a true statement about an untitled office
record (see prompt rule D15).

`--path-mode` picks what a search hit links to:
    pdf   — the R2 PDF directly. Correct while these have no site pages.
    site  — /primary-works/<slug>/, for after ingestion creates entries.

    python3 scripts/swatantra/build-works-meta.py <out.json> [--path-mode pdf]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INVENTORY = REPO / "data/swatantra-papers/inventory.tsv"
FILEMETA = REPO / "data/swatantra-papers/filename-metadata.tsv"
PREFIX = "swatantra-party-papers"
ARCHIVE = "https://archive.indianliberals.in"
COLLECTION = "Swatantra Party papers"


def slugify(name):
    import unicodedata
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return re.sub(r"-{2,}", "-", stem)


def title_from(name):
    """Human-readable title from the filename, ID stripped and separators eased.

    This is a FINDING-AID title, not a transcribed one — the documents are
    largely untitled office records. It exists so a search result is legible,
    and it is superseded the moment extraction writes a real title.
    """
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = re.sub(r"^\d+[A-Za-z]?-", "", stem)
    stem = re.sub(r"_(\d{2})-(\d{2})-(\d{4})$", "", stem)
    stem = stem.replace("_", " ").strip()
    return stem or "Untitled"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--path-mode", choices=("pdf", "site"), default="pdf")
    a = ap.parse_args()

    inv = {r["file"]: r for r in csv.DictReader(open(INVENTORY, encoding="utf-8"), delimiter="\t")}
    fm = {r["file"]: r for r in csv.DictReader(open(FILEMETA, encoding="utf-8"), delimiter="\t")}

    metas, no_year, no_type, no_byline = {}, 0, 0, 0
    for name, row in inv.items():
        f = fm.get(name, {})
        slug = slugify(name)
        key = f"{PREFIX}/{slug}.pdf"
        pdf_url = f"{ARCHIVE}/{key}"

        year = f.get("year") or ""
        year_i = int(year) if year.isdigit() else None
        if year_i is None:
            no_year += 1
        work_type = f.get("work_type_suggest") or ""
        if not work_type:
            no_type += 1
        byline = f.get("thinker_id") or f.get("correspondent_verbatim") or ""
        if not byline:
            no_byline += 1

        metas[key] = {
            "path": pdf_url if a.path_mode == "pdf" else f"/primary-works/{slug}/",
            "title": title_from(name),
            "subtitle": "",
            "byline": byline,
            "year": year_i,
            "decade": (year_i // 10 * 10) if year_i else None,
            "work_type": work_type or "letter",
            "language": "en",
            "collection": COLLECTION,
            "themes": [],
            "cover_image": "",
            "pdf_url": pdf_url,
            "archive_id": f.get("archive_id", ""),
            "provenance": "filename-derived; not model-extracted",
        }

    Path(a.out).write_text(json.dumps(metas, indent=1, ensure_ascii=False), encoding="utf-8")
    n = len(metas)
    print(f"wrote {a.out}: {n} records, path-mode={a.path_mode}")
    print(f"  year known      : {n - no_year} ({(n-no_year)/n*100:.1f}%)")
    print(f"  work_type known : {n - no_type} ({(n-no_type)/n*100:.1f}%)  "
          f"[{no_type} defaulted to 'letter']")
    print(f"  byline present  : {n - no_byline} ({(n-no_byline)/n*100:.1f}%)")
    print("\nNOTE: titles are finding-aid labels derived from filenames, and the")
    print("pilot showed the filename loses to the page on document type 3 times")
    print("out of 3. This layer makes the corpus findable; it does not describe it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
