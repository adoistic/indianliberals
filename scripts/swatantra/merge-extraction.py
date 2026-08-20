#!/usr/bin/env python3
"""Merge extracted records into the provisional Swatantra content entries.

The entries written by emit-content-entries.py are filename-derived scaffolding.
This replaces that scaffolding with what the model actually read off the page,
in place — same slug, same R2 pdf_url, same file. Nothing is duplicated.

Why not `emit-astro-md.py`: it derives its slug from the raw PDF stem
(underscores kept) and sets no pdf_url, so it writes a SECOND entry per work
with the filename as the title. Extraction therefore runs with
LLM_EXTRACT_NO_EMIT=1 and merging happens here, where slug and pdf_url are
already correct.

Rules that matter:

  * metadata.a is canonical; metadata.b is used only to detect disagreement.
    Where the two differ on a self-consistency field, needs_review stays true —
    that is the tiebreak signal, and we are not running the Opus tiebreak pass.
  * `authors` are Zod *references*. A thinker_id with no entry in the thinkers
    collection fails the whole build, so every id is checked against the
    collection and dropped (with the verbatim byline preserved) if absent.
  * Themes are filtered to the controlled vocabulary; the rest go to
    `proposed_themes`, which is what that field is for.
  * Measured `scan_quality` is kept from inventory.tsv — the model cannot know
    the ink/background separation, we measured it.
  * Refuses to touch any entry that is not one of ours.

    python3 scripts/swatantra/merge-extraction.py            # dry run
    python3 scripts/swatantra/merge-extraction.py --apply
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BAKE = REPO / "data/bake-off-output"
CLOUD = REPO / "data/swatantra-papers/cloud-results"
CONTENT = REPO / "apps/site/src/content/primary-works"
THINKERS = REPO / "apps/site/src/content/thinkers"
INVENTORY = REPO / "data/swatantra-papers/inventory.tsv"
VOCAB = REPO / "data/themes-vocab.json"
ARCHIVE = "https://archive.indianliberals.in"
PREFIX = "swatantra-party-papers"
PROVISIONAL = "filename-derived; awaiting llm-extract enrichment"
MERGED = "llm-extract v1.5; metadata.a canonical, metadata.b cross-checked"

SCAN_QUALITY = {"strong": "good", "adequate": "fair", "weak": "fair", "faint": "poor"}
# The six fields driver.py escalates to Opus on disagreement.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from filename_worktype import apply as fw_apply  # noqa: E402

CONSISTENCY = ("work_type", "year", "title", "publisher", "byline", "thinker_ids")


def slugify(name):
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return re.sub(r"-{2,}", "-", stem)


def y(v):
    return json.dumps(v, ensure_ascii=False)


def dig(d, path, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def scalar(node):
    """Unwrap {value, confidence} wrappers the schema uses on high-stakes fields."""
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def fingerprint(rec):
    """The comparison tuple for A/B self-consistency."""
    authors = rec.get("authors") or []
    return {
        "work_type": rec.get("work_type"),
        "year": scalar(dig(rec, "publication.year")),
        "title": scalar(dig(rec, "title.main")),
        "publisher": dig(rec, "publication.publisher_verbatim"),
        "byline": " | ".join(sorted(str(a.get("byline_verbatim") or "") for a in authors)),
        "thinker_ids": ",".join(sorted(
            str(a.get("thinker_id")) for a in authors if a.get("thinker_id"))),
    }


def norm(v):
    if v is None:
        return ""
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def supplied_title(name):
    """Archival supplied title, in square brackets.

    D15 makes extraction return title.main: null for the office records that
    carry no printed title — correct, and the site schema still requires a
    string. Square brackets are the standard archival marker for a title
    supplied by the cataloguer rather than taken from the item, so the display
    stays honest: `[Letter to Mr Suresh Singh]` reads as "we named this", and
    `title_not_printed` remains in missing_metadata_flags.
    """
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = re.sub(r"^\d+[A-Za-z]?-", "", stem)
    stem = re.sub(r"_(\d{2})-(\d{2})-(\d{4})$", "", stem)
    stem = stem.replace("_", " ").strip()
    return f"[{stem}]" if stem else "[Untitled document]"


def build_entry(name, inv_row, meta, summ, disagree, known_thinkers, vocab):
    slug = slugify(name)
    pdf_url = f"{ARCHIVE}/{PREFIX}/{slug}.pdf"

    title = scalar(dig(meta, "title.main"))
    title_supplied = not title
    if title_supplied:
        title = supplied_title(name)
    subtitle = scalar(dig(meta, "title.subtitle")) or ""
    # work_type is the field the cheap extraction model gets worst (48% on a
    # stratified sample; minutes/circulars/press notes all collapse into
    # `occasional_paper`), and the only field with a model-free signal: the
    # cataloguer typed the form into the filename. The filename may only
    # REPLACE a less specific answer, never downgrade one — see
    # filename_worktype.SPECIFICITY. Measured: lifts the model from 48% to
    # 65%, and overrides the baked Sonnet records zero times.
    work_type, wt_source = fw_apply(name, meta.get("work_type") or "letter")
    purpose = meta.get("purpose")
    year = scalar(dig(meta, "publication.year"))
    # scalar() on every one of these, not just the ones the schema declares as
    # wrapped. Luna occasionally returns {value, confidence} for a field the
    # schema says is a plain string; without the unwrap that dict reaches the
    # frontmatter and fails the collection schema at build time.
    place = scalar(dig(meta, "publication.place"))
    publisher_name = scalar(dig(meta, "publication.publisher_verbatim"))
    issuer = scalar(dig(meta, "publication.issuer_id"))
    language = meta.get("language") or "en"

    # Reference integrity: an unknown thinker_id fails the Astro build.
    authors, dropped = [], []
    for a in (meta.get("authors") or []):
        tid = a.get("thinker_id")
        if not tid:
            continue
        if tid in known_thinkers:
            authors.append(tid)
        else:
            dropped.append(tid)

    raw_themes = meta.get("themes") or []
    conf = dig(summ, "summary_structured.themes_confirmed") or []
    raw_themes = list(dict.fromkeys(list(raw_themes) + list(conf)))
    themes = [t for t in raw_themes if t in vocab]
    proposed = [t for t in raw_themes if t not in vocab]
    proposed += list(dig(summ, "summary_structured.theme_proposed_new") or [])
    proposed = list(dict.fromkeys(proposed))

    summary_text = summ.get("summary") if isinstance(summ.get("summary"), str) else None
    flags = list(meta.get("missing_metadata_flags") or [])
    if title_supplied and "title_not_printed" not in flags:
        flags.append("title_not_printed")
    if disagree:
        flags.append("ab_disagreement:" + ",".join(disagree))
    needs_review = bool(meta.get("needs_human_review")) or bool(disagree) or bool(dropped)

    L = ["---", f"id: {slug}", "title:"]
    L.append(f"  main: {y(title)}")
    L.append(f"  subtitle: {y(subtitle)}")
    L.append(f"work_type: {work_type}")
    if wt_source == "filename":
        L.append("work_type_source: filename")
    if purpose:
        L.append(f"purpose: {purpose}")
    if authors:
        L.append("authors:")
        L += [f"  - {a}" for a in authors]
    else:
        L.append("authors: []")
    L += ["editors: []", "contributors: []", "related_thinkers: []", "publication:"]
    L.append(f"  language: {language}")
    if issuer:
        L.append(f"  issuer_id: {issuer}")
    if publisher_name:
        L.append(f"  publisher_name: {y(publisher_name)}")
    if place:
        L.append(f"  place: {y(place)}")
    if isinstance(year, int):
        L.append(f"  year: {year}")
    L += ["provenance:", "  source: ccs_archive",
          f"  scan_quality: {SCAN_QUALITY.get(inv_row.get('legibility',''), 'unknown')}",
          f"  notes: {y(MERGED)}",
          "physical:", f"  pages_total: {inv_row['pages']}",
          "  pages_total_source: pypdfium2",
          f"pdf_url: {pdf_url}",
          "rights:", "  status: takedown_on_request", "  license: in-copyright",
          "  license_url: null",
          "  rights_statement: Rights held by original depositors / Centre for "
          "Civil Society; reproduced for archival access."]
    if themes:
        L.append("themes:")
        L += [f"  - {t}" for t in themes]
    else:
        L.append("themes: []")
    if proposed:
        L.append("proposed_themes:")
        L += [f"  - {y(t)}" for t in proposed]
    if flags:
        L.append("missing_metadata_flags:")
        L += [f"  - {y(f)}" for f in flags]
    L += ["authors_resolution:", "  method: vision",
          f"  confidence: {'high' if authors and not disagree else 'medium'}",
          "  proposed_unknowns: []"]
    L.append(f"needs_review: {'true' if needs_review else 'false'}")
    L.append("draft: false")
    L.append("ai:")
    L.append("  drafted_by: claude-sonnet-4.5")
    L.append("  model_version: v1.5")
    if summary_text:
        L.append("summary: |-")
        for line in summary_text.strip().splitlines():
            L.append(f"  {line}")
    L.append("---")
    L.append("")

    kp = dig(summ, "summary_structured.key_points") or []
    if kp:
        L.append("## Key points")
        L.append("")
        for k in kp:
            if isinstance(k, str):
                L.append(f"- {k}")
        L.append("")
    if not summary_text and not kp:
        L.append(f"Archive item {inv_row.get('archive_id','')}. "
                 "Scanned document from the Swatantra Party papers.")
        L.append("")
    return "\n".join(L), dropped, needs_review


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    inv = {Path(r["file"]).stem: r for r in csv.DictReader(
        open(INVENTORY, encoding="utf-8"), delimiter="\t")}
    for r in inv.values():
        r["archive_id"] = (re.match(r"(\d+[A-Za-z]?)", r["file"]) or [""])[0]
    known = {p.stem for p in THINKERS.glob("*.md")}
    vocab = set(json.loads(VOCAB.read_text(encoding="utf-8"))) if VOCAB.exists() else set()

    merged = skipped = foreign = no_summary = 0
    all_dropped, review_count, disagreements = [], 0, 0

    # Two extraction roots: the original Sonnet bake, and the Luna cloud run.
    # BAKE is listed first so that on any slug present in both, the Sonnet
    # record wins — it is the more accurate model, and re-extraction should
    # never silently downgrade a work we already did well.
    found = {}
    for root in (BAKE, CLOUD):
        if not root.exists():
            continue
        for d in root.iterdir():
            if d.is_dir() and d.name in inv and d.name not in found:
                found[d.name] = d
    dirs = [found[k] for k in sorted(found)]
    if a.limit:
        dirs = dirs[:a.limit]

    for d in dirs:
        ma, mb = d / "metadata.a.a.json", d / "metadata.b.b.json"
        if not ma.exists():
            continue
        try:
            meta = json.loads(ma.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        summ = {}
        sp = d / "summary.json"
        if sp.exists():
            try:
                summ = json.loads(sp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        if not summ:
            no_summary += 1

        disagree = []
        if mb.exists():
            try:
                fb = fingerprint(json.loads(mb.read_text(encoding="utf-8")))
                fa = fingerprint(meta)
                disagree = [k for k in CONSISTENCY if norm(fa[k]) != norm(fb[k])]
            except json.JSONDecodeError:
                pass
        if disagree:
            disagreements += 1

        name = inv[d.name]["file"]
        path = CONTENT / f"{slugify(name)}.md"
        if path.exists():
            cur = path.read_text(encoding="utf-8")
            if PROVISIONAL not in cur and MERGED not in cur:
                print(f"  REFUSING (not ours): {path.name}", file=sys.stderr)
                foreign += 1
                continue

        body, dropped, needs = build_entry(
            name, inv[d.name], meta, summ, disagree, known, vocab)
        all_dropped += dropped
        review_count += bool(needs)

        if path.exists() and path.read_text(encoding="utf-8") == body:
            skipped += 1
            continue
        if a.apply:
            path.write_text(body, encoding="utf-8")
        merged += 1

    verb = "merged" if a.apply else "would merge"
    print(f"{verb} {merged}, unchanged {skipped}, refused {foreign} "
          f"(of {len(dirs)} extracted works)")
    print(f"  without a summary yet : {no_summary}")
    print(f"  A/B disagreement      : {disagreements} "
          f"({disagreements/max(len(dirs),1)*100:.0f}%) -> needs_review")
    print(f"  needs_review true     : {review_count}")
    if all_dropped:
        from collections import Counter
        c = Counter(all_dropped)
        print(f"  thinker_ids DROPPED (no entry in the thinkers collection): {len(c)}")
        for tid, n in c.most_common(8):
            print(f"      {n:4d}  {tid}")
        print("      byline_verbatim is preserved; these need authority entries.")
    if not a.apply:
        print("\n(dry run — pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
