#!/usr/bin/env python3
"""Prepare a stratified extraction pilot over the Swatantra Party papers.

Answers four questions before ~25,700 dispatches are committed:

  1. Can the vision model read 128 DPI scans, and how does that degrade across
     the legibility bands measured in inventory.tsv?
  2. How often do `metadata.a` and `metadata.b` disagree on the six
     self-consistency fields? That rate is what drives Opus tiebreak volume.
  3. Do prompts written for published works behave on office correspondence?
  4. Does the model use the archival work_type values added on 2026-08-17?

Reuses the real pipeline: driver.py's prompt loader, authority subset and
taxonomy blocks, rasterize.py, and dispatcher.prepare_request. The only thing
it changes is the PDF root, since driver.PDF_ROOT points at an external drive.

    python3 scripts/swatantra/pilot-prepare.py <corpus-dir> [n_docs]

Writes request dirs under /tmp/llm-extract-requests/ and a manifest at
data/swatantra-papers/pilot/manifest.json. Dispatching the agents and
collecting results is the orchestrating session's job — see pilot-report.py.
"""
import csv
import json
from collections import Counter
import os
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "llm-extract"))

import driver  # noqa: E402
from dispatcher import DispatchRequest, prepare_request  # noqa: E402
from rasterize import rasterize_chunk  # noqa: E402

OUT = REPO / "data" / "swatantra-papers" / "pilot"

# Stratify across the two axes that plausibly predict failure: how legible the
# scan is, and whether the genre resembles anything the prompts were written
# for. One cell per row; `genre` empty means "any".
CELLS = [
    ("faint", "letter"), ("faint", "minutes"), ("faint", ""),
    ("weak", "letter"), ("weak", "circular"), ("weak", "telegram"),
    ("adequate", "letter"), ("adequate", "minutes"), ("adequate", "press_note"),
    ("strong", "letter"), ("strong", ""), ("strong", "souvenir"),
]


def load_rows():
    inv = {r["file"]: r for r in csv.DictReader(
        open(REPO / "data/swatantra-papers/inventory.tsv", encoding="utf-8"), delimiter="\t")}
    meta = {r["file"]: r for r in csv.DictReader(
        open(REPO / "data/swatantra-papers/filename-metadata.tsv", encoding="utf-8"), delimiter="\t")}
    for f, r in inv.items():
        r.update({k: v for k, v in meta.get(f, {}).items() if k != "file"})
    return inv


def select(rows, n):
    """One document per stratification cell, deterministic."""
    rng = random.Random(17)
    picked, seen = [], set()
    for band, genre in CELLS:
        if len(picked) >= n:
            break
        pool = [r for f, r in rows.items()
                if r["legibility"] == band
                and (not genre or r.get("genre") == genre)
                and f not in seen
                # keep the pilot cheap: single-chunk docs except the souvenir cell
                and (genre == "souvenir" or int(r["pages"]) <= 20)
                and int(r["pages"]) >= 1]
        if not pool:
            print(f"  (no candidate for {band}/{genre or 'any'})", file=sys.stderr)
            continue
        pick = rng.choice(sorted(pool, key=lambda r: r["file"]))
        seen.add(pick["file"])
        picked.append(pick)
    return picked


def top_corpus_thinkers(limit=40):
    """Thinker IDs most frequent in this corpus, for authority-subset pinning.

    The default 60-of-454 subset is an alphabetical cut that omits Minoo Masani,
    who is the correspondent in 1,171 files. Pinning the corpus's own frequent
    bylines is what stops every Masani document emitting thinker_id: null.
    """
    counts = Counter()
    with open(REPO / "data/swatantra-papers/filename-metadata.tsv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r["thinker_id"]:
                counts[r["thinker_id"]] += 1
    return [tid for tid, _ in counts.most_common(limit)]


def main(corpus_dir, n_docs):
    rows = load_rows()
    picked = select(rows, n_docs)
    OUT.mkdir(parents=True, exist_ok=True)

    pinned = top_corpus_thinkers()
    print(f"pinning {len(pinned)} corpus-frequent thinkers into the authority subset "
          f"(top: {', '.join(pinned[:5])})", file=sys.stderr)
    authority_subset = driver._load_authority_subset(include_ids=pinned)
    manifest = []

    for row in picked:
        pdf = Path(corpus_dir) / row["file"]
        chunk = rasterize_chunk(pdf_path=pdf, start_page=1, pages_wanted=20)
        pages = [p.page_num for p in chunk.pages]
        entry = {
            "file": row["file"],
            "archive_id": row["archive_id"],
            "legibility": row["legibility"],
            "separation": row["separation"],
            "pages_total": chunk.total_pages_in_pdf,
            "pages_rendered": pages,
            "filename_hint": {
                "date": row.get("date", ""), "year": row.get("year", ""),
                "correspondent": row.get("correspondent_verbatim", ""),
                "thinker_id": row.get("thinker_id", ""),
                "genre": row.get("genre", ""),
                "work_type_suggest": row.get("work_type_suggest", ""),
            },
            "requests": {},
        }

        for job in ("metadata.a", "metadata.b"):
            system, user_template, version = driver._load_prompt(job)
            subs = dict(
                PDF_NAME=pdf.name,
                PUBLISHER_FOLDER="swatantra-party-papers",
                TOTAL_PDF_PAGES=chunk.total_pages_in_pdf,
                N_PAGES=len(chunk.pages),
                PAGE_NUMBERS=str(pages),
                AUTHORITY_SUBSET=authority_subset,
                WORK_TYPE_TAXONOMY=driver.WORK_TYPE_TAXONOMY,
                THEME_VOCABULARY=driver.THEME_VOCABULARY,
                METADATA_JSON="{}", MODE="default",
                TOC_INDEX="", PREV_SUBCHUNK_CONTEXT="",
            )
            # See the note in driver.cmd_prep: the taxonomy and theme-vocabulary
            # placeholders live in the SYSTEM block, so both need substituting.
            system = driver._substitute(system, **subs)
            user_text = driver._substitute(user_template, **subs)
            prepared = prepare_request(DispatchRequest(
                system_prompt=system, user_text=user_text,
                images=[p.jpeg_bytes for p in chunk.pages],
                image_page_numbers=pages,
                model="sonnet", job=job,
                work_slug=pdf.stem, chunk_idx=0, prompt_version=version,
            ))
            out_path = prepared.request_dir / "response.json"
            agent_prompt = (
                prepared.suggested_agent_prompt.rstrip()
                + f"\n\nIMPORTANT — output handling:\n"
                  f"Write your JSON object to {out_path} using the Write tool.\n"
                  f"Then reply with ONE line only, no JSON, no prose:\n"
                  f"  OK <work_type> | year=<year or ?> | authors=<thinker_id or null> | "
                  f"themes=<count> | proposed=<count> | review=<true|false>\n"
                  f"If you cannot produce valid JSON, write nothing and reply: FAIL <one-line reason>"
            )
            entry["requests"][job] = {
                "request_dir": str(prepared.request_dir),
                "response_path": str(out_path),
                "agent_prompt": agent_prompt,
                "prompt_version": version,
            }
        manifest.append(entry)
        print(f"  prepared {row['legibility']:8s} {row.get('genre','') or '-':10s} "
              f"{len(pages):2d}p  {row['file'][:52]}")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{len(manifest)} documents, {len(manifest)*2} dispatches prepared")
    print(f"manifest: {OUT / 'manifest.json'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 12)
