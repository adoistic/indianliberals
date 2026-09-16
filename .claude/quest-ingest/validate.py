#!/usr/bin/env python3
"""Verify an ingested Quest issue against what the run promises.

Checks the things a wrong answer would hide: ontology ids, whether the issue
really was read cover to cover, and whether every printed contents entry got a
summary. Exits non-zero if anything fails.

Usage: validate.py QT001 [...]
"""
import json, re, sys
from pathlib import Path
REPO = Path("/Users/siraj/Indian Liberals Website")
WORKS = REPO / "apps/site/src/content/primary-works"
BAKE = REPO / "data/bake-off-output"
fail = 0
for qt in sys.argv[1:]:
    qt = qt.upper(); md = WORKS / f"{qt.lower()}.md"
    probs, notes = [], []
    if not md.exists():
        print(f"FAIL {qt}: no markdown"); fail += 1; continue
    t = md.read_text(encoding="utf-8"); fm = t.split("---", 2)[1]
    for want, label in (("publisher_id: quest", "publisher_id"),
                        ("issuer_id: quest", "issuer_id"),
                        ("work_type: periodical_issue", "work_type")):
        if want not in fm: probs.append(f"{label} wrong")
    if not re.search(r"^pdf_url:", fm, re.M): notes.append("no pdf_url yet")
    if not re.search(r"^cover_image:", fm, re.M): notes.append("no cover yet")

    meta = json.loads((BAKE / qt / "metadata.a.json").read_text(encoding="utf-8"))
    sp = BAKE / qt / "summary.json"
    summ = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    toc = [e for e in ((meta.get("toc") or {}).get("entries") or []) if e.get("toc_index") is not None]
    essays = summ.get("essays_summarized") or []
    t_idx = {e["toc_index"] for e in toc}
    e_idx = {e.get("toc_index") for e in essays if e.get("toc_index") is not None}
    pages_total = (meta.get("physical") or {}).get("pages_total")
    sc = summ.get("summary_completeness") or {}

    if summ.get("extent_caveat") is True: probs.append("extent_caveat true — not fully read")
    unseen = (sc.get("essays_not_yet_seen") or []) + (sc.get("essays_partial") or [])
    if sc.get("covers_full_work") is not True and unseen:
        probs.append(f"not full coverage: {len(unseen)} partial/unseen")
    br = sc.get("based_on_pages")
    if isinstance(br, list) and len(br) == 2 and pages_total and br[1] < pages_total:
        probs.append(f"based_on_pages ends at {br[1]} of {pages_total}")
    missing = sorted(t_idx - e_idx)
    if missing: probs.append(f"{len(missing)} TOC entries with no summary: {missing[:8]}")
    extra = sorted(e_idx - t_idx)
    if extra: notes.append(f"{len(extra)} items not on the contents page (expected: plates/ads)")
    done = set(sc.get("essays_complete") or [])
    short = sorted(i for i in (e_idx & t_idx) if i not in done)
    if short: notes.append(f"{len(short)} not in essays_complete: {short[:6]}")
    body = t.split("---", 2)[2]
    if len(body) < 8000: probs.append(f"body only {len(body)} chars")
    # the harvest must be durable, not left in ephemeral scratch
    if not (REPO / "data/quest-contributors" / f"{qt}.json").exists():
        notes.append("contributor harvest NOT archived in repo")

    if probs: fail += 1
    print(f"{'OK  ' if not probs else 'FAIL'} {qt}: {len(toc)} TOC / {len(essays)} essays / "
          f"{pages_total}pp / body {len(body)}c"
          + ("  | " + "; ".join(probs) if probs else "")
          + ("  (" + "; ".join(notes) + ")" if notes else ""))
sys.exit(1 if fail else 0)
