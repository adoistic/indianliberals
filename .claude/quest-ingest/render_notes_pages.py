#!/usr/bin/env python3
"""Render each issue's contributor-notes page(s) for a targeted re-read.

The text-layer recovery got about 72% of the biographies; the rest are lost to
OCR mangling the name at a line start, which is exactly where the match is made.
Reading the page as an IMAGE fixes that, and is cheap: one or two pages per
issue rather than the whole issue.

Candidate pages are the byline-dense ones — a page where several lines each
begin with a different contributor's name IS the notes page, headed or not
(QT003's carries no heading at all). The whole issue is scanned, not just the
back matter, because QT008 and QT011 print notes mid-issue too.

Usage: render_notes_pages.py <outdir> QT001 [...]
"""
import json, re, subprocess, sys, unicodedata
from pathlib import Path
import pypdfium2 as pdfium

REPO = Path("/Users/siraj/Indian Liberals Website")
BAKE = REPO / "data/bake-off-output"
HARVEST = REPO / "data/quest-contributors"
STAGE = Path("/tmp/quest-scans/quest")

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"^(mrs|mr|dr|prof|professor|shri|sri|smt|miss|ms|swami|sir)\.?\s+", "", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())

def surname(s):
    w = norm(s).split()
    return w[-1] if w else ""

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
manifest = {}
for qt in sys.argv[2:]:
    qt = qt.upper()
    pdf = STAGE / f"{qt}.pdf"
    if not pdf.exists():
        subprocess.run(["curl","-sS","-o",str(pdf),
                        f"https://archive.indianliberals.in/quest/{qt.lower()}.pdf"],
                       capture_output=True)
    if not pdf.exists():
        print(f"FAIL {qt}: no scan"); continue
    meta = json.loads((BAKE / qt / "metadata.a.json").read_text(encoding="utf-8"))
    surs = {surname(c.get("byline_verbatim") or "") for c in (meta.get("contributors") or [])
            if isinstance(c, dict) and len(surname(c.get("byline_verbatim") or "")) > 2}
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    pp = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    scored = []
    for p in range(1, pp + 1):
        txt = subprocess.run(["pdftotext","-f",str(p),"-l",str(p),str(pdf),"-"],
                             capture_output=True, text=True).stdout
        if len(txt) < 250: continue
        hits = set()
        for line in txt.split("\n"):
            for tok in norm(" ".join(line.split()[:5])).split():
                if tok in surs: hits.add(tok); break
        if len(hits) >= 2: scored.append((len(hits), p))
    scored.sort(reverse=True)
    pages = sorted(p for _, p in scored[:3])
    if not pages:
        print(f"{qt}: no byline-dense page found"); manifest[qt] = []; continue
    doc = pdfium.PdfDocument(str(pdf))
    for p in pages:
        dest = out / f"{qt}-p{p:03d}.jpg"
        doc[p-1].render(scale=2.2).to_pil().convert("RGB").save(dest, "JPEG", quality=88)
    doc.close()
    have = json.loads((HARVEST / f"{qt}.json").read_text(encoding="utf-8"))
    missing = [r["byline_verbatim"] for r in have if not r.get("note_verbatim")]
    manifest[qt] = {"pages": pages, "people_without_a_note": missing}
    print(f"{qt}: rendered pages {pages}; {len(missing)} people still lack a note")
(out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nmanifest -> {out}/manifest.json")
