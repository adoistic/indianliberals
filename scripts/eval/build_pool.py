#!/usr/bin/env python3
"""
Sample the source material for the eval question pool, and emit authoring
briefs.

This script does not write questions. It decides *what each question must be
about* — deterministically, from a fixed seed — so the pool's coverage is a
property of the corpus rather than of whoever happened to be writing that day.
Questions themselves are authored from these briefs and then frozen; the
grader that consumes the frozen pool is fully deterministic.

Three dimensions define a question:

  tier        A      expected sources are paragraph-citable
              B      expected sources are summary-only, PDF-linked
              mixed  spans both — the sharpest test of the two-tier rule,
                     since one answer must quote Tier A with anchors AND
                     summary-attribute Tier B without quoting it

  retrieval   named  the question names the work, author, or publication.
                     Tests citation discipline once retrieval is easy.
              blind  the question names only a concept. The agent must find
                     the source itself. This is the realistic case — a reader
                     does not know what is in the archive — and the blind
                     score is the honest measure of whether discovery works.

  shape       single  one source suffices
              multi   needs two or more sources brought together
              needle  one obscure fact in one paragraph of one document

Needles are selected by term rarity, not by hand: a paragraph scores by how
many of its tokens appear in two or fewer documents corpus-wide. That surfaces
the rare proper nouns, place names, and figures that a keyword search will
only find if the agent actually searches well.

Usage:
    python3 scripts/eval/build_pool.py
    python3 scripts/eval/build_pool.py --seed 20260727 --total 250
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CORPUS = HERE / "corpus.json"
CROSS_LINKS = REPO / "data" / "synthesis" / "cross-links.json"
BRIEF_DIR = HERE / "briefs"

# Fixed so a re-run reproduces the same pool. Bump only to build a new pool
# generation, never to nudge a score.
DEFAULT_SEED = 20260727

# The eight cells, and each one's share of the pool. Blind questions are the
# clear majority: they are what a real reader's query looks like.
CELLS = [
    # (tier,   retrieval, shape,   weight)
    ("A",     "named",   "single", 30),
    ("A",     "blind",   "single", 40),
    ("A",     "blind",   "needle", 35),
    ("A",     "blind",   "multi",  25),
    ("B",     "named",   "single", 30),
    ("B",     "blind",   "single", 35),
    ("B",     "blind",   "multi",  20),
    ("mixed", "blind",   "multi",  35),
]

TOKEN_RE = re.compile(r"[a-z][a-z'-]{3,}")
STOP = {
    "that", "this", "with", "from", "have", "were", "been", "they", "their",
    "which", "would", "there", "these", "when", "what", "than", "then", "them",
    "some", "such", "into", "more", "most", "other", "only", "also", "over",
    "after", "before", "under", "about", "against", "between", "through",
    "during", "because", "while", "where", "both", "each", "very", "much",
    "many", "must", "should", "could", "will", "shall", "upon", "does", "made",
    "make", "said", "says", "being", "here", "even", "same", "well", "just",
    "like", "part", "time", "year", "years", "india", "indian",
}


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP]


def load_cross_links() -> dict[str, list[dict]]:
    if not CROSS_LINKS.exists():
        return {}
    with CROSS_LINKS.open(encoding="utf-8") as fh:
        return json.load(fh)


def document_frequency(corpus: dict) -> Counter:
    """How many documents each token appears in, across the whole corpus."""
    df: Counter = Counter()
    for doc in corpus["tier_a"].values():
        seen = set()
        for para in doc["paragraphs"]:
            seen.update(tokens(para["text"]))
        df.update(seen)
    for work in corpus["tier_b"].values():
        seen = set()
        for part in work["grounded_text"]:
            seen.update(tokens(part))
        df.update(seen)
    return df


def rarity(text: str, df: Counter) -> float:
    """
    Needle score: reward tokens that barely occur anywhere else.

    Summed inverse-log document frequency over the paragraph's distinct
    tokens, so a paragraph carrying three hapax proper nouns outranks a long
    paragraph of common policy vocabulary.
    """
    distinct = set(tokens(text))
    if not distinct:
        return 0.0
    return sum(1.0 / math.log(2 + df.get(t, 1)) for t in distinct if df.get(t, 1) <= 2)


def citable(doc: dict) -> list[dict]:
    return [p for p in doc["paragraphs"] if p["citable"]]


def brief_tier_a_doc(doc: dict, paragraphs: list[dict] | None = None) -> dict:
    """The material an author needs to write a Tier A question about one doc."""
    chosen = paragraphs if paragraphs is not None else citable(doc)
    return {
        "key": doc["key"],
        "tier": "A",
        "collection": doc["collection"],
        "title": doc["title"],
        "url": doc["url"],
        "authors": doc["authors"],
        "year": doc["year"],
        "themes": doc["themes"][:6],
        "citable_paragraphs": [
            {"paragraph_id": p["paragraph_id"], "words": p["words"], "text": p["text"]}
            for p in chosen
        ],
    }


def brief_tier_b_work(work: dict) -> dict:
    """The material an author needs to write a Tier B question about one work."""
    return {
        "key": work["key"],
        "tier": "B",
        "collection": "primary-works",
        "work_type": work["work_type"],
        "title": work["title"],
        "url": work["url"],
        "pdf_url": work["pdf_url"],
        "authors": work["authors"],
        "year": work["year"],
        "themes": work["themes"][:6],
        "series": work["series"],
        "summary": work["summary"],
        "key_points": work["key_points"][:10],
        "articles": [
            {"heading": a["heading"], "byline": a["byline"], "text": a["text"][:900]}
            for a in work["articles"][:6]
        ],
    }


def theme_groups(items: dict, min_size: int = 2) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for key, entry in items.items():
        for theme in entry.get("themes") or []:
            groups[theme].append(key)
    return {t: keys for t, keys in groups.items() if len(keys) >= min_size}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--total", type=int, default=250)
    ap.add_argument("--per-batch", type=int, default=10)
    args = ap.parse_args()

    if not CORPUS.exists():
        raise SystemExit("Run scripts/eval/build_corpus.py first.")
    with CORPUS.open(encoding="utf-8") as fh:
        corpus = json.load(fh)

    rng = random.Random(args.seed)
    df = document_frequency(corpus)
    links = load_cross_links()

    tier_a = corpus["tier_a"]
    tier_b = corpus["tier_b"]

    # Eligible sources. A Tier A doc needs at least one substantial anchored
    # paragraph or there is nothing to cite; a Tier B work needs both a
    # summary to attribute and a PDF to link, since the grader checks both.
    a_keys = sorted(k for k, d in tier_a.items() if citable(d))
    b_keys = sorted(k for k, w in tier_b.items() if w["summary"] and w["pdf_url"])

    # Needle candidates: the single rarest paragraph of each eligible doc,
    # ranked corpus-wide. Long enough to contain a real fact, short enough
    # that one anchor is unambiguously the answer.
    needles: list[tuple[float, str, dict]] = []
    for key in a_keys:
        doc = tier_a[key]
        best = max(
            (p for p in citable(doc) if 30 <= p["words"] <= 220),
            key=lambda p: rarity(p["text"], df),
            default=None,
        )
        if best is not None:
            score = rarity(best["text"], df)
            if score > 0:
                needles.append((score, key, best))
    needles.sort(key=lambda t: (-t[0], t[1]))

    scale = args.total / sum(w for *_, w in CELLS)
    used_a: set[str] = set()
    used_b: set[str] = set()
    briefs: list[dict] = []
    counter = 0

    a_pool = a_keys[:]
    b_pool = b_keys[:]
    rng.shuffle(a_pool)
    rng.shuffle(b_pool)
    a_iter = iter(a_pool)
    b_iter = iter(b_pool)

    def next_a() -> str | None:
        for key in a_iter:
            if key not in used_a:
                used_a.add(key)
                return key
        return None

    def next_b() -> str | None:
        for key in b_iter:
            if key not in used_b:
                used_b.add(key)
                return key
        return None

    a_themes = theme_groups(tier_a)
    b_themes = theme_groups(tier_b)

    def related_a(key: str) -> list[str]:
        """Cross-linked Tier A partners for a doc, falling back to shared theme."""
        out = [
            f"{l['collection']}:{l['slug']}"
            for l in links.get(key, [])
            if f"{l['collection']}:{l['slug']}" in tier_a
        ]
        out = [k for k in out if k in a_keys and k != key]
        if out:
            return out
        for theme in tier_a[key]["themes"]:
            peers = [k for k in a_themes.get(theme, []) if k != key and k in a_keys]
            if peers:
                return peers
        return []

    def related_b(key: str) -> list[str]:
        out = [
            f"primary-works:{l['slug']}"
            for l in links.get(key, [])
            if l["collection"] == "primary-works"
        ]
        out = [k for k in out if k in b_keys and k != key]
        if out:
            return out
        for theme in tier_b[key]["themes"]:
            peers = [k for k in b_themes.get(theme, []) if k != key and k in b_keys]
            if peers:
                return peers
        return []

    needle_cursor = 0

    for tier, retrieval, shape, weight in CELLS:
        want = max(1, round(weight * scale))
        made = 0
        guard = 0
        while made < want and guard < want * 40:
            guard += 1
            counter += 1
            qid = f"il-{counter:04d}"
            sources: list[dict] = []

            if shape == "needle":
                if needle_cursor >= len(needles):
                    break
                _, key, para = needles[needle_cursor]
                needle_cursor += 1
                if key in used_a:
                    counter -= 1
                    continue
                used_a.add(key)
                sources = [brief_tier_a_doc(tier_a[key], [para])]

            elif tier == "A" and shape == "single":
                key = next_a()
                if key is None:
                    break
                sources = [brief_tier_a_doc(tier_a[key])]

            elif tier == "A" and shape == "multi":
                key = next_a()
                if key is None:
                    break
                peers = [k for k in related_a(key) if k not in used_a]
                if not peers:
                    counter -= 1
                    continue
                partner = peers[0]
                used_a.add(partner)
                sources = [brief_tier_a_doc(tier_a[key]), brief_tier_a_doc(tier_a[partner])]

            elif tier == "B" and shape == "single":
                key = next_b()
                if key is None:
                    break
                sources = [brief_tier_b_work(tier_b[key])]

            elif tier == "B" and shape == "multi":
                key = next_b()
                if key is None:
                    break
                peers = [k for k in related_b(key) if k not in used_b]
                if not peers:
                    counter -= 1
                    continue
                partner = peers[0]
                used_b.add(partner)
                sources = [brief_tier_b_work(tier_b[key]), brief_tier_b_work(tier_b[partner])]

            elif tier == "mixed":
                a_key = next_a()
                b_key = next_b()
                if a_key is None or b_key is None:
                    break
                sources = [brief_tier_a_doc(tier_a[a_key]), brief_tier_b_work(tier_b[b_key])]

            if not sources:
                counter -= 1
                continue

            briefs.append(
                {
                    "id": qid,
                    "tier": tier,
                    "retrieval": retrieval,
                    "shape": shape,
                    "sources": sources,
                }
            )
            made += 1

    # Group into homogeneous batches so each authoring pass gets one clear
    # instruction set rather than a mixture.
    BRIEF_DIR.mkdir(exist_ok=True)
    for stale in BRIEF_DIR.glob("*.json"):
        stale.unlink()

    by_cell: dict[tuple, list[dict]] = defaultdict(list)
    for brief in briefs:
        by_cell[(brief["tier"], brief["retrieval"], brief["shape"])].append(brief)

    manifest = []
    batch_no = 0
    for (tier, retrieval, shape), group in sorted(by_cell.items()):
        for start in range(0, len(group), args.per_batch):
            batch_no += 1
            chunk = group[start : start + args.per_batch]
            name = f"batch-{batch_no:02d}-{tier}-{retrieval}-{shape}.json"
            payload = {
                "batch": batch_no,
                "cell": {"tier": tier, "retrieval": retrieval, "shape": shape},
                "count": len(chunk),
                "briefs": chunk,
            }
            (BRIEF_DIR / name).write_text(
                json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            manifest.append({"file": name, "cell": f"{tier}/{retrieval}/{shape}", "count": len(chunk)})

    (BRIEF_DIR / "manifest.json").write_text(
        json.dumps(
            {"seed": args.seed, "total": len(briefs), "batches": manifest},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    print(f"seed {args.seed} · {len(briefs)} briefs in {batch_no} batches → {BRIEF_DIR.relative_to(REPO)}")
    for tier, retrieval, shape, _ in CELLS:
        n = len(by_cell[(tier, retrieval, shape)])
        print(f"  {tier:5} {retrieval:5} {shape:6} {n:4}")
    print(f"  distinct Tier A docs used: {len(used_a)} · Tier B works used: {len(used_b)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
