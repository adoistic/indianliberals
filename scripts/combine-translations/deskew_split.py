#!/usr/bin/env python3
"""Turn a scanned book into single pages: fix the rotation, split the spreads.

The Vidyasagar Bengali scan (বাল্যবিবাহের দোষ) was photographed as four
two-page spreads lying on their side. Every page carried `/Rotate 90` on a
landscape mediabox, so viewers showed it as a tall portrait page with the text
running sideways and two book pages crammed into one. Readable only by tilting
your head, and impossible to page through like a book.

This does two things, both losslessly — no re-rasterising, so the scan keeps
its original resolution:

  1. Sets `/Rotate 0`. The landscape mediabox was already the upright
     orientation; the 90 was what put it on its side.
  2. Splits each spread down the gutter into two pages by narrowing the
     mediabox, left half then right (Bengali reads left to right).

The gutter is found per page rather than assumed to be the centre — it lands
between 0.497 and 0.508 of the width across these four spreads. It is the
darkest column in the middle third, the shadow where the binding dips away
from the camera.

Halves under `--blank-threshold` ink coverage are dropped: on this scan that
removes exactly one, the blank inside cover facing the title page.
"""

import argparse
import glob
import os
import subprocess
import tempfile

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject


def analyse(pdf_path, dpi=100):
    """Per page: gutter position as a fraction of width, and ink either side."""
    out = []
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), pdf_path, os.path.join(td, "p")],
            check=True,
        )
        for f in sorted(glob.glob(os.path.join(td, "p-*.png"))):
            im = Image.open(f).convert("L")
            W, H = im.size
            px = im.load()
            rows = range(0, H, 7)
            lo, hi = int(W * 0.33), int(W * 0.67)
            gx = min(
                ((sum(px[x, y] for y in rows) / len(rows)), x) for x in range(lo, hi)
            )[1]

            def ink(x0, x1):
                n = d = 0
                for x in range(x0, x1, 3):
                    for y in rows:
                        n += 1
                        if px[x, y] < 160:
                            d += 1
                return d / max(n, 1)

            out.append((gx / W, ink(0, gx), ink(gx, W)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--blank-threshold", type=float, default=0.05)
    args = ap.parse_args()

    # Rotation has to be normalised before measuring, or the gutter runs
    # horizontally and the middle-third scan finds nothing.
    reader = PdfReader(args.src)
    tmp = PdfWriter()
    for p in reader.pages:
        p[NameObject("/Rotate")] = NumberObject(0)
        tmp.add_page(p)
    upright = args.dst + ".upright.tmp.pdf"
    with open(upright, "wb") as fh:
        tmp.write(fh)

    metrics = analyse(upright)

    writer = PdfWriter()
    kept = dropped = 0
    for i, (frac, ink_l, ink_r) in enumerate(metrics):
        for side, inked in (("L", ink_l), ("R", ink_r)):
            if inked < args.blank_threshold:
                print(f"  spread {i+1} {side}: blank ({inked:.3f}) — dropped")
                dropped += 1
                continue
            src = PdfReader(upright).pages[i]
            x0 = float(src.mediabox.left)
            x1 = float(src.mediabox.right)
            cut = x0 + (x1 - x0) * frac
            if side == "L":
                src.mediabox.upper_right = (cut, float(src.mediabox.top))
            else:
                src.mediabox.lower_left = (cut, float(src.mediabox.bottom))
            writer.add_page(src)
            kept += 1
            print(f"  spread {i+1} {side}: kept (ink {inked:.3f}, cut at {frac:.3f})")

    with open(args.dst, "wb") as fh:
        writer.write(fh)
    os.remove(upright)
    print(f"\n{len(metrics)} spreads -> {kept} pages ({dropped} blank dropped): {args.dst}")


if __name__ == "__main__":
    main()
