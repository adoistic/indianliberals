#!/usr/bin/env python3
"""
TF-IDF cross-link generator (Day 8, Step 6).

Reads every Tier-A content MD (musings, opinions, interviews, thinker bios,
ThePrint mirror) plus the prose `summary` / body of every primary-works MD,
tokenises against an English stopword list, computes per-document TF-IDF
vectors, and writes the top-N most similar OTHER documents for each entry to:

    data/synthesis/cross-links.json

Shape:
    {
      "<collection>:<slug>": [
        {"collection": "primary-works", "slug": "...", "score": 0.43, "title": "..."},
        ...
      ]
    }

The Astro detail pages read this file at build time and render "Related" sections.

Why pure Python (no scikit-learn / numpy):
  - Corpus is small (~500 docs × ~500 words avg).
  - Avoiding heavy deps keeps the synthesis venv minimal.
  - Cosine similarity on sparse dicts is fast enough (<5s for the full corpus).

Run from the repo root:
    python3 scripts/synthesis/tfidf.py
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
OUT_PATH = ROOT / "data/synthesis/cross-links.json"

# Collections that get cross-linked. graph-edges is JSON, not MD; period-windows,
# reading-paths, themes carry their own synthesis content that doesn't benefit
# from TF-IDF similarity. Organisations get cross-linked too — short pages but
# their text mentions are useful for "see also" navigation.
COLLECTIONS = [
    "primary-works",
    "musings",
    "opinions",
    "interviews",
    "thinkers",
    "organisations",
    "theprint-mirror",
]

TOP_N = 5
MIN_SCORE = 0.05  # below this cosine similarity, "related" is just noise
MIN_DOC_FREQ = 2  # vocab terms must appear in ≥2 docs to count

# Compact English stopword list. Indic-script tokens get tokenised
# differently in Pagefind but for TF-IDF we operate on word boundaries
# AFTER lowercasing, so non-Latin characters survive as their own tokens.
# We don't filter them; rare Devanagari/Gujarati words become high-IDF
# signal automatically.
STOPWORDS = set(
    """
    a about above after again against all am an and any are as at be because been before
    being below between both but by can cannot could did do does doing don down during each
    few for from further had has have having he her here hers herself him himself his how
    i if in into is it its itself just me more most my myself no nor not now of off on once
    only or other our ours ourselves out over own same she should so some such than that
    the their theirs them themselves then there these they this those through to too under
    until up very was we were what when where which while who whom why will with would you
    your yours yourself yourselves
    """.split()
)


def parse_md(p: Path) -> tuple[dict, str]:
    """Split frontmatter (YAML-ish) from body. Returns (frontmatter_dict, body)."""
    text = p.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    raw_fm, body = m.group(1), m.group(2)
    fm: dict = {}
    # Naive YAML parse — only fields we need: id, title, summary.
    # Multi-line title.main shape:
    #   title:
    #     main: "...."
    title_main_match = re.search(r"^title:\s*\n\s+main:\s*(.+)$", raw_fm, re.M)
    if title_main_match:
        fm["title"] = title_main_match.group(1).strip().strip('"').strip("'")
    else:
        flat_title = re.search(r'^title:\s*"?([^"\n]+)"?\s*$', raw_fm, re.M)
        if flat_title:
            fm["title"] = flat_title.group(1).strip().strip('"').strip("'")
    id_match = re.search(r'^id:\s*"?([^"\n]+)"?\s*$', raw_fm, re.M)
    if id_match:
        fm["id"] = id_match.group(1).strip().strip('"').strip("'")
    # Multi-line summary: "summary: \"\\n  text\\n  more\\n\""
    # Or scalar summary on one line. The emitter uses scalar; the
    # primary-works extraction uses scalar too. Either way, this captures the
    # content for body augmentation.
    sum_match = re.search(r'^summary:\s*"((?:[^"\\]|\\.)*)"\s*$', raw_fm, re.M)
    if sum_match:
        fm["summary"] = sum_match.group(1).replace("\\n", "\n").replace('\\"', '"')
    fm["draft"] = bool(re.search(r"^draft:\s*true\s*$", raw_fm, re.M))
    fm["language"] = "en"
    lang_match = re.search(r'^language:\s*"?([a-z]{2})"?\s*$', raw_fm, re.M)
    if lang_match:
        fm["language"] = lang_match.group(1)
    return fm, body


WORD_RX = re.compile(r"[A-Za-zऀ-ॿ઀-૿ঀ-৿ऀ-ॿ]{3,}")


def tokenise(text: str) -> list[str]:
    """Tokenise to lowercase word tokens ≥3 chars, dropping markdown / HTML
    syntax characters but preserving Devanagari/Gujarati/Bengali ranges."""
    # Strip code fences, links, HTML tags
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_~|]+", " ", text)
    tokens = [t.lower() for t in WORD_RX.findall(text)]
    return [t for t in tokens if t not in STOPWORDS]


def main() -> int:
    docs: list[dict] = []  # {key, collection, slug, title, tokens}
    for col in COLLECTIONS:
        coldir = CONTENT_ROOT / col
        if not coldir.is_dir():
            continue
        for p in sorted(coldir.glob("*.md")):
            fm, body = parse_md(p)
            if fm.get("draft"):
                continue
            if fm.get("language", "en") != "en":
                continue
            slug = fm.get("id") or p.stem
            title = fm.get("title", slug)
            text = body
            if fm.get("summary"):
                text = fm["summary"] + "\n\n" + text
            tokens = tokenise(text)
            if len(tokens) < 20:
                continue  # too thin to bother — would produce noise
            docs.append({
                "key": f"{col}:{slug}",
                "collection": col,
                "slug": slug,
                "title": title,
                "tokens": tokens,
            })

    n_docs = len(docs)
    if n_docs < 2:
        print(f"[tfidf] Only {n_docs} eligible docs; emitting empty cross-links.")
        OUT_PATH.write_text(json.dumps({}) + "\n")
        return 0

    print(f"[tfidf] {n_docs} docs across {len({d['collection'] for d in docs})} collections")

    # Compute document frequency per term
    df: Counter[str] = Counter()
    for d in docs:
        for term in set(d["tokens"]):
            df[term] += 1

    # Vocabulary: terms with df >= MIN_DOC_FREQ and df < n_docs (drop ubiquitous)
    vocab = {term for term, freq in df.items() if MIN_DOC_FREQ <= freq < n_docs * 0.7}
    print(f"[tfidf] vocab size: {len(vocab)} (raw: {len(df)})")

    # Pre-compute IDF
    idf = {term: math.log(n_docs / df[term]) for term in vocab}

    # Build TF-IDF sparse vectors per doc + their L2 norms
    vectors: list[dict[str, float]] = []
    norms: list[float] = []
    for d in docs:
        tf = Counter(t for t in d["tokens"] if t in vocab)
        if not tf:
            vectors.append({})
            norms.append(0.0)
            continue
        # log-normalised tf
        vec = {t: (1 + math.log(tf[t])) * idf[t] for t in tf}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        # Normalise so cosine is just dot product
        vec = {t: v / norm for t, v in vec.items()}
        vectors.append(vec)
        norms.append(norm)

    # Inverted index for fast similarity: term → list of (doc_idx, weight)
    inv: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for i, vec in enumerate(vectors):
        for term, w in vec.items():
            inv[term].append((i, w))

    # For each doc, compute scores against all others via the inverted index.
    out: dict[str, list[dict]] = {}
    for i, d in enumerate(docs):
        if not vectors[i]:
            continue
        scores: dict[int, float] = defaultdict(float)
        for term, w_i in vectors[i].items():
            for j, w_j in inv[term]:
                if j == i:
                    continue
                scores[j] += w_i * w_j
        # Top-N per cross-collection preference: don't return 5 items from the
        # same collection. We want a mix — for each related doc, prefer
        # diverse collections by penalising same-collection slightly.
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        related: list[dict] = []
        seen_collections: Counter[str] = Counter()
        for j, score in ranked:
            if score < MIN_SCORE:
                break
            if len(related) >= TOP_N:
                break
            # Soft diversity cap: max 3 from the same collection
            if seen_collections[docs[j]["collection"]] >= 3:
                continue
            related.append({
                "collection": docs[j]["collection"],
                "slug": docs[j]["slug"],
                "title": docs[j]["title"],
                "score": round(score, 4),
            })
            seen_collections[docs[j]["collection"]] += 1
        if related:
            out[d["key"]] = related

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    edges = sum(len(v) for v in out.values())
    print(f"[tfidf] wrote {OUT_PATH.relative_to(ROOT)} — {len(out)} docs with related, {edges} edges")
    # Print a tiny sample for sanity
    sample_key = next(iter(out.keys()))
    print(f"[tfidf] sample: {sample_key}")
    for r in out[sample_key][:3]:
        print(f"        → {r['collection']:18}  {r['slug']:40}  score={r['score']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
