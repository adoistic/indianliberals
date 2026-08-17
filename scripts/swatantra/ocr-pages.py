#!/usr/bin/env python3
"""OCR the Swatantra Party papers with Tesseract, for the full-text search layer.

This feeds `scripts/fulltext/` — the Pagefind index reads per-page plain text.
It is NOT needed for `llm-extract`, which reads page images directly.

Preprocessing is driven by what the corpus measurement found (see
docs/handoffs/2026-08-17-swatantra-papers-corpus-condition.md §5):

  * Source scans are ~128 DPI. Tesseract wants 300. We upsample on render via
    PyMuPDF rather than post-hoc, so the interpolation happens once.
  * Pages are mostly stored as 8-bit RGB even though the content is monochrome,
    and the paper is tanned — the *background* sits below 240. So a fixed
    threshold is wrong here; Otsu picks the split per page.
  * Median ink/background separation is 86 of 255, and half the corpus is below
    the "adequate" band, so contrast is stretched before thresholding.

Emits JSON Lines, one record per PDF:
    {"file": ..., "key": ..., "pages": ["page 1 text", ...], "word_hit": 0.83}

`pages` matches the shape `scripts/fulltext/README.md` expects for
fulltext.jsonl, so the output can be joined straight into the index.

    python3 scripts/swatantra/ocr-pages.py <corpus-dir> <out.jsonl> [--limit N]
                                           [--files a.pdf,b.pdf] [--lang eng]
"""
import argparse
import json
import unicodedata
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool

import fitz
import numpy as np
from PIL import Image

RENDER_DPI = 300          # Tesseract's documented sweet spot
TOKEN_RE = re.compile(r"[A-Za-z]{2,}")


def load_words():
    words = {"a", "i", "to", "of", "in", "is", "it", "on", "at", "by", "we",
             "he", "be", "as", "an", "or", "the", "and", "for", "you", "are",
             "was", "not", "but", "that", "this", "with", "have", "from",
             "swatantra", "masani", "rajaji", "ranga", "india", "indian",
             "bombay", "delhi", "madras", "party", "congress", "sincerely"}
    p = "/usr/share/dict/words"
    if os.path.exists(p):
        with open(p, encoding="utf-8", errors="ignore") as fh:
            words |= {w.strip().lower() for w in fh if len(w.strip()) > 1}
    return words


WORDS = load_words()


def word_hit(text):
    toks = TOKEN_RE.findall(text)
    if not toks:
        return 0.0
    return sum(1 for t in toks if t.lower() in WORDS) / len(toks)


def _boxsum(arr, r):
    """Sum over a (2r+1) square window, via an integral image."""
    pad = np.pad(arr, r + 1, mode="edge")
    integral = pad.cumsum(0).cumsum(1)
    h, w = arr.shape
    d = 2 * r + 1
    return (integral[d:d + h, d:d + w] - integral[0:h, d:d + w]
            - integral[d:d + h, 0:w] + integral[0:h, 0:w])


def binarize(arr, k=0.25, R=128.0):
    """Sauvola local adaptive thresholding.

    A *global* threshold — fixed or Otsu — fails on this corpus in two ways.
    A fixed cutoff marks the whole sheet as ink, because tanned paper puts the
    background below 240. Global Otsu then fails on the very common case of a
    small newspaper clipping pasted onto a large backing sheet: the dominant
    pixel population is the backing, so Otsu splits backing-vs-clipping and
    throws away the text inside the clipping entirely. On
    `2058-Emergency_Must_Stay_Says_Munshi` that produced a 92%-black page and
    zero characters at every --psm setting.

    Sauvola thresholds each pixel against its own neighbourhood, so backing
    sheet, clipping and typescript are each judged on local contrast:
        T = mean * (1 + k * (std / R - 1))
    Window is sized to the page so it spans several text lines.
    """
    h, w = arr.shape
    r = max(8, min(h, w) // 40)
    n = float((2 * r + 1) ** 2)
    mean = _boxsum(arr, r) / n
    sq = _boxsum(arr * arr, r) / n
    std = np.sqrt(np.maximum(sq - mean * mean, 0))
    thresh = mean * (1.0 + k * (std / R - 1.0))
    return np.where(arr <= thresh, 0, 255).astype(np.uint8)


def ocr_page(page, lang, psm):
    pm = page.get_pixmap(dpi=RENDER_DPI)
    img = Image.frombytes("RGB" if pm.n >= 3 else "L", (pm.width, pm.height), pm.samples)
    arr = np.asarray(img.convert("L")).astype(float)
    binary = Image.fromarray(binarize(arr))

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        binary.save(tf.name)
        tmp = tf.name
    try:
        proc = subprocess.run(
            ["tesseract", tmp, "stdout", "-l", lang, "--psm", str(psm),
             "--dpi", str(RENDER_DPI)],
            capture_output=True, text=True, timeout=180,
        )
        return proc.stdout
    except subprocess.TimeoutExpired:
        return ""
    finally:
        os.unlink(tmp)


def slugify(name):
    """`1008-Letter_to_NG_Ranga_03-08-1964.pdf` -> `1008-letter-to-ng-ranga-03-08-1964`.

    The leading archive ID is kept deliberately: 617 title groups covering 1,551
    files share a normalised title, so a slug without the ID collides on ~24% of
    the corpus.
    """
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return re.sub(r"-{2,}", "-", stem)


def ocr_file(args):
    path, lang, psm, prefix = args
    base = os.path.basename(path)
    key = f"{prefix.rstrip('/')}/{slugify(base)}.pdf" if prefix else base
    rec = {"file": base, "key": key, "pages": []}
    try:
        doc = fitz.open(path)
        for page in doc:
            rec["pages"].append(ocr_page(page, lang, psm).strip())
        doc.close()
        blob = "\n".join(rec["pages"])
        rec["chars"] = len(blob)
        rec["word_hit"] = round(word_hit(blob), 3)
        rec["ok"] = True
    except Exception as exc:
        rec["ok"] = False
        rec["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_dir")
    ap.add_argument("out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--files", default="")
    ap.add_argument("--lang", default="eng")
    ap.add_argument("--psm", type=int, default=6)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--resume", action="store_true",
                    help="Skip files already present in <out>, and append.")
    ap.add_argument("--key-prefix", default="",
                    help="R2 collection prefix, e.g. swatantra-party-papers. "
                         "Makes `key` match the object key so the OCR text joins "
                         "the Pagefind corpus directly.")
    a = ap.parse_args()

    if a.files:
        names = [f.strip() for f in a.files.split(",") if f.strip()]
    else:
        names = sorted(f for f in os.listdir(a.corpus_dir) if f.lower().endswith(".pdf"))
        if a.limit:
            names = names[:a.limit]
    # Resume: a full-corpus pass is ~2 hours, so never redo completed files.
    already = set()
    if a.resume and os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            for line in fh:
                try:
                    already.add(json.loads(line)["file"])
                except (json.JSONDecodeError, KeyError):
                    continue   # tolerate a torn last line from a killed run
        names = [n for n in names if n not in already]
        print(f"resuming: {len(already)} already done, {len(names)} remaining",
              file=sys.stderr)

    paths = [(os.path.join(a.corpus_dir, n), a.lang, a.psm, a.key_prefix) for n in names]
    print(f"OCR: {len(paths)} files, lang={a.lang}, psm={a.psm}, "
          f"render={RENDER_DPI}dpi, jobs={a.jobs}", file=sys.stderr)

    done = 0
    mode = "a" if (a.resume and already) else "w"
    with Pool(a.jobs) as pool, open(a.out, mode, encoding="utf-8") as fh:
        for rec in pool.imap_unordered(ocr_file, paths, chunksize=1):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()          # a killed run must leave a resumable file
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(paths)}", file=sys.stderr, flush=True)
    print(f"wrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
