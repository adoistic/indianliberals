#!/usr/bin/env python3
"""Rebuild the contributor-note harvest for already-ingested Quest issues.

Why this exists: the harvest for QT001-020 lived in the session scratchpad and a
disk-full event wiped it. It is recoverable without re-reading the issues,
because it splits in two and only one half was lost:
  bylines / roles / toc_index -> survive in data/bake-off-output/<QT>/metadata.a.json
  the biographies             -> come from one "Contributors to this issue" (or
                                 "Our Reviewers") page per issue, and every scan
                                 is on R2.

Notes are NOT paragraph-separated in this OCR: each begins at a LINE whose first
few words are the person's name and runs on until the next such line. Boundaries
are therefore found by line-anchored surname matches, which also avoids matching
a surname appearing mid-sentence inside someone else's note ("joint author with
A. S. Ray" sits inside Lila Ray's own note).

A note is attached to a byline ONLY on a surname match at a line start. An
unmatched note is reported and left out rather than guessed onto the nearest
person: attaching the wrong biography to a real author is worse than a blank.

nationality_evidence / vocation_evidence stay null — the agents derived those by
judgement, and build_profiles.py reads the note text itself for country and
vocation signals, so nothing downstream depends on them.

Usage: recover_contributors.py QT001 [...]
"""
import json, re, subprocess, sys, unicodedata
from pathlib import Path

REPO = Path("/Users/siraj/Indian Liberals Website")
BAKE = REPO / "data/bake-off-output"
OUT = REPO / "data/quest-contributors"
STAGE = Path("/tmp/quest-scans/quest")
SRC = Path("/Users/siraj/Downloads/drive-download-20260915T160627Z-1-001")
HEAD = re.compile(r"contribut|our reviewers", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"^(mrs|mr|dr|prof|professor|shri|sri|smt|miss|ms|swami|sir)\.?\s+", "", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def surname(s: str) -> str:
    w = norm(s).split()
    return w[-1] if w else ""


def get_pdf(qt: str):
    STAGE.mkdir(parents=True, exist_ok=True)
    p = STAGE / f"{qt}.pdf"
    if p.exists():
        return p
    if (SRC / f"{qt}.pdf").exists():
        p.write_bytes((SRC / f"{qt}.pdf").read_bytes())
        return p
    subprocess.run(["curl", "-sS", "-o", str(p),
                    f"https://archive.indianliberals.in/quest/{qt.lower()}.pdf"],
                   capture_output=True)
    return p if p.exists() and p.stat().st_size > 10000 else None


OUT.mkdir(parents=True, exist_ok=True)
for qt in sys.argv[1:]:
    qt = qt.upper()
    mj = BAKE / qt / "metadata.a.json"
    if not mj.exists():
        print(f"SKIP {qt}: no surviving metadata")
        continue
    meta = json.loads(mj.read_text(encoding="utf-8"))
    contribs = [c for c in (meta.get("contributors") or []) if isinstance(c, dict)]
    pdf = get_pdf(qt)
    if not pdf:
        print(f"FAIL {qt}: could not obtain the scan")
        continue
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    pp = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))

    sur_to_byline = {}
    for c in contribs:
        by = (c.get("byline_verbatim") or "").strip()
        s = surname(by)
        if s and len(s) > 2:
            sur_to_byline.setdefault(s, by)

    # A heading is NOT a reliable signal: QT003's notes page carries none at all,
    # running straight from the folio into "Edward Shils is professor of
    # Sociology at Chicago University...". Detect instead by the structure we
    # actually exploit — a page in the back half where several LINES each begin
    # with a different contributor's name. That is what a notes page is.
    def line_starts(txt):
        hits = []
        for i, line in enumerate(txt.split("\n")):
            for tok in norm(" ".join(line.split()[:5])).split():
                if tok in sur_to_byline:
                    hits.append((i, sur_to_byline[tok]))
                    break
        return hits

    note_pages = []
    for p in range(max(1, pp // 2), pp + 1):
        txt = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"],
                             capture_output=True, text=True).stdout
        if len(txt) < 300:
            continue
        hits = line_starts(txt)
        distinct = {b for _, b in hits}
        if len(distinct) >= 3 or (HEAD.search("\n".join(txt.strip().split("\n")[:4]))
                                  and len(distinct) >= 1):
            note_pages.append((p, txt))

    notes = []
    for page, txt in note_pages:
        lines = txt.split("\n")
        starts = line_starts(txt)
        for k, (i, by) in enumerate(starts):
            j = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
            body = " ".join(" ".join(lines[i:j]).split())
            if len(body) > 30:
                notes.append((page, by, body))

    note_for, used = {}, set()
    for idx, (page, by, body) in enumerate(notes):
        note_for.setdefault(norm(by), (idx, page, body))

    merged = {}
    for c in contribs:
        by = (c.get("byline_verbatim") or "").strip()
        if not by:
            continue
        hit = note_for.get(norm(by))
        if hit:
            used.add(hit[0])
        row = {
            "byline_verbatim": by,
            "name_as_in_contributor_note": None,
            "name_variants": [],
            "roles": [c.get("role") or "author"],
            "toc_indexes": [c["toc_index"]] if c.get("toc_index") is not None else [],
            "note_verbatim": hit[2] if hit else None,
            "note_printed_page": hit[1] if hit else None,
            "nationality_evidence": None,
            "vocation_evidence": None,
            "is_editor_of_issue": (c.get("role") == "editor"),
            "_provenance": "recovered_by_extraction",
        }
        k = norm(by)
        if k in merged:
            m = merged[k]
            m["roles"] = sorted(set(m["roles"]) | set(row["roles"]))
            m["toc_indexes"] = sorted(set(m["toc_indexes"]) | set(row["toc_indexes"]))
            m["note_verbatim"] = m["note_verbatim"] or row["note_verbatim"]
            m["note_printed_page"] = m["note_printed_page"] or row["note_printed_page"]
            m["is_editor_of_issue"] = m["is_editor_of_issue"] or row["is_editor_of_issue"]
        else:
            merged[k] = row

    final = list(merged.values())
    (OUT / f"{qt}.json").write_text(
        json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    withnote = sum(1 for r in final if r["note_verbatim"])
    orphan = [b for i, (p, b, t) in enumerate(notes) if i not in used]
    print(f"{qt}: {len(final)} people, {withnote} with a recovered note "
          f"(pages {[p for p, _ in note_pages] or 'none found'}"
          + (f", {len(orphan)} unmatched left out" if orphan else "") + ")")
