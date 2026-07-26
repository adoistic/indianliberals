#!/usr/bin/env python3
"""Bind an original-language text and its English translation into one PDF.

Two works in the archive were digitised as a matched pair — the original and a
translation, scanned as separate files and catalogued as separate records:

  বাল্যবিবাহের দোষ / The Vice of Child Marriages   — Ishwar Chandra Vidyasagar
  सोव्हिएत साम्राज्याचा उदय आणि अस्त / The Rise and Fall of the Soviet Empire

Opening either record showed only half the document, and the original-language
half was effectively invisible: the Bengali scan carries no text layer, so it
does not surface in search either. Reading them apart also loses the point —
the translation exists to be read *against* the original.

This binds each pair into a single PDF, original first, with a printed divider
between the two halves so a reader knows where the translation begins. Both
records then point at the same combined file and cross-reference each other
through `publication.translations`, so either title is a valid way in.

Output goes to the bucket under `combined/`; the single-language originals stay
where they are and are not deleted.
"""

import io
import os
import sys

from pypdf import PdfReader, PdfWriter

SCRATCH = sys.argv[1] if len(sys.argv) > 1 else "."

PAIRS = [
    {
        "out": "balyo-bibaher-dosh-vidyasagar-bengali-and-english.pdf",
        "original": ("bn_orig.pdf", "বাল্যবিবাহের দোষ", "Bengali original"),
        "translation": ("bn_tr.pdf", "The Vice of Child Marriages", "English translation"),
        "author": "Ishwar Chandra Vidyasagar",
    },
    {
        "out": "soviet-samarajya-uday-ani-astha-marathi-and-english.pdf",
        "original": ("mr_orig.pdf", "सोव्हिएत साम्राज्याचा उदय आणि अस्त", "Marathi original"),
        "translation": ("mr_tr.pdf", "The Rise and Fall of the Soviet Empire", "English translation"),
        "author": "",
    },
]


def _esc(s: str) -> str:
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def divider(label: str, sub: str) -> io.BytesIO:
    """A plain title card marking the start of a section.

    Hand-built rather than pulled from a PDF library: this repo has no
    reportlab and the divider is one line of centred Helvetica, which the PDF
    base-14 fonts give for free. Deliberately ASCII — embedding a Bengali or
    Devanagari face for one caption would add megabytes; the original-language
    title is carried by the scan on the page that follows.
    """
    W, H = 595, 842  # A4 in points
    # Helvetica average advance is ~0.5em; good enough to centre a short line.
    def centred(text, size, y, font, grey):
        x = (W - len(text) * size * 0.5) / 2
        return (
            f"BT /{font} {size} Tf {grey} rg 1 0 0 1 {x:.1f} {y:.1f} Tm "
            f"({_esc(text)}) Tj ET\n"
        )

    stream = (
        centred(label, 19, H / 2 + 22, "F1", "0.09 0.075 0.06")
        + f"0.82 0.78 0.72 RG 0.8 w {W/2-90:.1f} {H/2-4:.1f} m {W/2+90:.1f} {H/2-4:.1f} l S\n"
        + centred(sub, 11, H / 2 - 34, "F2", "0.42 0.38 0.34")
    ).encode("latin-1", "replace")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] "
        f"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(buf.tell())
        buf.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    xref = buf.tell()
    buf.write(f"xref\n0 {len(objs)+1}\n".encode())
    buf.write(b"0000000000 65535 f \n")
    for off in offsets:
        buf.write(f"{off:010d} 00000 n \n".encode())
    buf.write(
        f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    buf.seek(0)
    return buf


def main():
    for p in PAIRS:
        w = PdfWriter()
        total = 0
        for key in ("original", "translation"):
            fname, title, label = p[key]
            src = os.path.join(SCRATCH, fname)
            sub = f"{p['author']} · {label}" if p["author"] else label
            for page in PdfReader(divider(label, sub)).pages:
                w.add_page(page)
            r = PdfReader(src)
            for page in r.pages:
                w.add_page(page)
            total += len(r.pages) + 1
            print(f"    + {label:20} {len(r.pages)} pp  ({title[:38]})")
        out = os.path.join(SCRATCH, p["out"])
        with open(out, "wb") as fh:
            w.write(fh)
        print(f"  -> {p['out']}  {total} pp, {os.path.getsize(out):,} bytes\n")


if __name__ == "__main__":
    main()
