#!/usr/bin/env python3
"""Measure the condition of the Swatantra Party papers scan corpus.

Emits one TSV row per PDF describing what the ingestion and OCR stages are
dealing with: page count, whether a text layer exists at all, how good that
text is where it exists, the scan resolution, and how legible the page image
is (ink/background separation after Otsu).

Nothing here writes to the corpus. It is safe to re-run, and it is meant to be
re-run after OCR to confirm the text layer landed:

    python3 scripts/swatantra/scan-corpus.py <corpus-dir> data/swatantra-papers/inventory.tsv

Columns
  file            basename of the PDF
  archive_id      leading numeric ID (matches the pen-circled number on the scan)
  pages           page count
  bytes           file size
  text_layer      none | partial | full   (over the sampled pages)
  ocr_quality     none | garbled | degraded | good
  chars_per_page  extracted characters per sampled page
  word_hit        fraction of alphabetic tokens found in the system wordlist
  junk_ratio      fraction of non-alphanumeric, non-punctuation characters
  dpi             effective resolution of the page image
  colour          y if the scan carries real colour, n if it is monochrome content
  separation      Otsu ink/background separation, 0-255 (higher is more legible)
  legibility      faint | weak | adequate | strong
  ink_pct         share of pixels below the Otsu threshold
"""
import json
import os
import re
import sys
from multiprocessing import Pool

import fitz
import numpy as np
from PIL import Image

TOKEN_RE = re.compile(r"[A-Za-z]{2,}")
TEXT_SAMPLE = 12          # pages sampled for text extraction
IMAGE_SAMPLE = 3          # pages sampled for legibility (first, middle, last)

# Tokens that are legitimate here but absent from /usr/share/dict/words.
EXTRA_WORDS = {
    "a", "i", "to", "of", "in", "is", "it", "on", "at", "by", "we", "he", "be",
    "as", "an", "or", "do", "so", "if", "no", "up", "my", "me", "us", "the",
    "and", "for", "you", "are", "was", "not", "but", "that", "this", "with",
    "have", "from", "they", "will", "would", "shall", "yours", "sincerely",
    "dear", "sir", "mr", "mrs", "dr", "shri", "india", "indian", "delhi",
    "bombay", "madras", "calcutta", "swatantra", "masani", "rajaji", "ranga",
    "congress", "party", "government", "president", "secretary", "committee",
    "national", "convention", "parliament", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october",
    "november", "december",
}


def load_words():
    words = set(EXTRA_WORDS)
    path = "/usr/share/dict/words"
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            words |= {w.strip().lower() for w in fh if len(w.strip()) > 1}
    return words


WORDS = load_words()


def score_text(text):
    """Quality metrics for an extracted text blob."""
    n = len(text)
    if n == 0:
        return 0.0, 0.0, 0.0
    space = sum(c.isspace() for c in text)
    junk = sum(
        1 for c in text
        if not (c.isalnum() or c.isspace() or c in ".,;:'\"!?()-–—/&$%#*[]{}+=@_`~<>|\\")
    )
    toks = TOKEN_RE.findall(text)
    hit = sum(1 for t in toks if t.lower() in WORDS)
    denom = max(1, n - space)
    return (hit / len(toks)) if toks else 0.0, junk / denom, float(n)


def otsu_stats(gray):
    """Return (ink/background separation, ink coverage) for a grayscale array."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    hist = hist.astype(float)
    total = hist.sum()
    weight = np.cumsum(hist)
    mean = np.cumsum(hist * np.arange(256))
    with np.errstate(invalid="ignore", divide="ignore"):
        between = (mean[-1] * weight / total - mean) ** 2 / (weight * (total - weight))
    thresh = int(np.nanargmax(between))
    fg, bg = gray[gray <= thresh], gray[gray > thresh]
    sep = (bg.mean() - fg.mean()) if fg.size and bg.size else 0.0
    return float(sep), float(fg.size / gray.size)


def spread(count, k):
    """Up to k evenly spread page indices out of count pages."""
    if count <= k:
        return list(range(count))
    return sorted({round(i * (count - 1) / (k - 1)) for i in range(k)})


def classify_quality(has_text, word_hit):
    if not has_text:
        return "none"
    if word_hit < 0.35:
        return "garbled"
    if word_hit < 0.75:
        return "degraded"
    return "good"


def classify_legibility(sep):
    if sep < 60:
        return "faint"
    if sep < 90:
        return "weak"
    if sep < 130:
        return "adequate"
    return "strong"


def scan(path):
    name = os.path.basename(path)
    m = re.match(r"(\d+)", name)
    row = {
        "file": name,
        "archive_id": m.group(1) if m else "",
        "pages": 0, "bytes": os.path.getsize(path),
        "text_layer": "none", "ocr_quality": "none",
        "chars_per_page": 0.0, "word_hit": 0.0, "junk_ratio": 0.0,
        "dpi": 0, "colour": "n", "separation": 0.0,
        "legibility": "", "ink_pct": 0.0,
    }
    doc = fitz.open(path)
    try:
        count = doc.page_count
        row["pages"] = count

        # --- text layer -------------------------------------------------
        idxs = spread(count, TEXT_SAMPLE)
        chunks, with_text, dpis = [], 0, []
        for i in idxs:
            page = doc[i]
            text = page.get_text("text")
            if len(text.strip()) >= 20:
                with_text += 1
            chunks.append(text)
            images = page.get_images(full=True)
            if images:
                _, _, w, h = images[0][:4]
                pw, ph = page.rect.width, page.rect.height
                if pw > 0 and ph > 0:
                    dpis.append(max(w / pw, h / ph) * 72)
        body = "".join(chunks)
        word_hit, junk, chars = score_text(body)
        row["text_layer"] = (
            "none" if with_text == 0 else "full" if with_text == len(idxs) else "partial"
        )
        row["ocr_quality"] = classify_quality(with_text > 0, word_hit)
        row["chars_per_page"] = round(chars / max(1, len(idxs)), 1)
        row["word_hit"] = round(word_hit, 3)
        row["junk_ratio"] = round(junk, 4)
        row["dpi"] = round(sum(dpis) / len(dpis)) if dpis else 0

        # --- legibility of the page image -------------------------------
        seps, inks, colour = [], [], False
        for i in spread(count, IMAGE_SAMPLE):
            pm = doc[i].get_pixmap(dpi=72)
            img = Image.frombytes(
                "RGB" if pm.n >= 3 else "L", (pm.width, pm.height), pm.samples
            )
            arr = np.asarray(img)
            if arr.ndim == 3:
                r, g, b = (arr[:, :, c].astype(int) for c in range(3))
                if np.abs(r - g).mean() > 6 or np.abs(g - b).mean() > 6:
                    colour = True
                arr = np.asarray(img.convert("L"))
            sep, ink = otsu_stats(arr)
            seps.append(sep)
            inks.append(ink)
        if seps:
            row["separation"] = round(sum(seps) / len(seps), 1)
            row["ink_pct"] = round(sum(inks) / len(inks) * 100, 1)
            row["legibility"] = classify_legibility(row["separation"])
        row["colour"] = "y" if colour else "n"
    finally:
        doc.close()
    return row


COLUMNS = [
    "file", "archive_id", "pages", "bytes", "text_layer", "ocr_quality",
    "chars_per_page", "word_hit", "junk_ratio", "dpi", "colour",
    "separation", "legibility", "ink_pct",
]


def main(corpus_dir, out_path):
    files = sorted(
        os.path.join(corpus_dir, f)
        for f in os.listdir(corpus_dir)
        if f.lower().endswith(".pdf")
    )
    print(f"scanning {len(files)} PDFs in {corpus_dir}", file=sys.stderr)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    failures = []
    with Pool(8) as pool, open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(COLUMNS) + "\n")
        for i, row in enumerate(pool.imap(scan_safe, files, chunksize=8), 1):
            if isinstance(row, str):
                failures.append(row)
                continue
            fh.write("\t".join(str(row[c]) for c in COLUMNS) + "\n")
            if i % 500 == 0:
                print(f"  {i}/{len(files)}", file=sys.stderr, flush=True)
    for f in failures:
        print(f"UNREADABLE: {f}", file=sys.stderr)
    print(f"wrote {out_path} ({len(files) - len(failures)} rows, "
          f"{len(failures)} unreadable)", file=sys.stderr)


def scan_safe(path):
    try:
        return scan(path)
    except Exception as exc:  # a corrupt PDF must not abort the sweep
        return f"{os.path.basename(path)}\t{type(exc).__name__}: {exc}"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
