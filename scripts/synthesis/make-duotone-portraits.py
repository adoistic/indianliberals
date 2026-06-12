#!/usr/bin/env python3
"""Generate uniform archival duotone portraits for featured thinkers.

CCS feedback 2.2 asks for visually consistent portraits across the
Thinkers page. Source photos are a mix of studio photographs, scans, and
engravings; caricatures are stylised webp. This script normalises all of
them into one treatment: a 3:4 crop mapped onto a two-tone archival
palette (deep ink shadows, warm paper highlights) matching the site's
saffron-and-forest scheme.

Reads `featured: true` thinker MDs, picks the best source
(photo > caricature), writes /public/thinkers/duotone/<slug>.webp and
sets `portrait.duotone` in the frontmatter. Idempotent — re-run after
adding new featured thinkers or replacing source photos.

Usage:
    .venv-extract/bin/python3 scripts/synthesis/make-duotone-portraits.py
"""

import re
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
THINKERS = ROOT / "apps/site/src/content/thinkers"
PUBLIC = ROOT / "apps/site/public"
OUT = PUBLIC / "thinkers/duotone"

# Site palette: ink ≈ deep forest-slate, paper ≈ warm cream.
INK = (39, 52, 59)
PAPER = (245, 239, 226)
SIZE = (480, 640)  # 3:4, 2x the 240x320 card


def duotone_lut() -> list[int]:
    """Per-channel LUT mapping grayscale 0..255 onto INK→PAPER."""
    lut = []
    for ch in range(3):
        lo, hi = INK[ch], PAPER[ch]
        lut.extend(round(lo + (hi - lo) * (i / 255)) for i in range(256))
    return lut


LUT = duotone_lut()


def treat(src: Path, dest: Path) -> None:
    im = Image.open(src)
    # Flatten transparency (caricatures) onto paper.
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, PAPER + (255,))
        im = Image.alpha_composite(bg, im)
    im = im.convert("L")
    im = ImageOps.autocontrast(im, cutoff=1)
    # 3:4 crop, biased toward the top of the frame where faces sit.
    w, h = im.size
    target = 3 / 4
    if w / h > target:
        nw = int(h * target)
        x = (w - nw) // 2
        im = im.crop((x, 0, x + nw, h))
    else:
        nh = int(w / target)
        y = int((h - nh) * 0.25)  # top-weighted
        im = im.crop((0, y, w, y + nh))
    im = im.resize(SIZE, Image.LANCZOS)
    im = im.convert("RGB").point(LUT * 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=82)


def main() -> None:
    done, skipped = 0, []
    for f in sorted(THINKERS.glob("*.md")):
        t = f.read_text()
        if not re.search(r"^featured: true$", t, re.M):
            continue
        m = re.search(r'^\s+photo: "([^"]+)"', t, re.M) or re.search(
            r'^\s+caricature: "([^"]+)"', t, re.M
        )
        if not m:
            skipped.append(f.stem)
            continue
        src = PUBLIC / m.group(1).lstrip("/")
        if not src.exists():
            skipped.append(f"{f.stem} (missing {m.group(1)})")
            continue
        dest = OUT / f"{f.stem}.webp"
        treat(src, dest)
        rel = f"/thinkers/duotone/{f.stem}.webp"
        if "duotone:" in t:
            t = re.sub(r'^(\s+duotone: ").*(")$', rf"\g<1>{rel}\g<2>", t, flags=re.M)
        else:
            t = re.sub(
                r"^(portrait:\n)", rf'\g<1>  duotone: "{rel}"\n', t, count=1, flags=re.M
            )
        f.write_text(t)
        done += 1
    print(f"duotone portraits written: {done}")
    if skipped:
        print("skipped (no source):", ", ".join(skipped))


if __name__ == "__main__":
    main()
