#!/usr/bin/env python3
"""
Audit the thinker authority + content files; generate a cleanup plan.

Two classes of garbage to surface:

1. ARTICLE-TITLE FAKES
   The WordPress export dropped article titles into the thinkers
   collection as fake "imported" entries. Telltales: the canonical name
   contains " - " (em-dash with spaces), " on ", ":", "?", "!", or is
   >5 words. These are not people; they should be deleted outright. Body
   excerpts on these are always the templated "Entry pending editorial
   review" stub.

2. DUPLICATE CLUSTERS
   Same person, multiple thinker IDs from naming variants. E.g.,
     - "AD Shroff" / "A.D. Shroff" / "Mr. AD Shroff"           → ad-shroff
     - "BR Shenoy" / "B.R. Shenoy" / "Prof. BR Shenoy"         → b-r-shenoy
     - "Sudha R. Shenoy" / "Sudha Shenoy"                      → sudha-r-shenoy
   Detection: aggressive normalisation (drop dots, hyphens, honorifics,
   collapse consecutive single-letter initials into one token, lowercase).
   Pick the winner by: (a) bio_source priority (canonical > feature_article
   > ai_drafted > imported), (b) longest body, (c) shortest slug.

Output: data/synthesis/cleanup-plan.json with `delete` and `merge` arrays.
A separate apply-thinker-cleanup.py reads this plan and executes it
idempotently with full content cross-reference rewriting.

We use heuristic rules only — high confidence, deterministic. Anything
ambiguous goes into a `review` array for human attention.

Run from the repo root:
    python3 scripts/synthesis/audit-thinkers.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "apps/site/src/content/thinkers"
AUTHORITY = ROOT / "data/authority/thinkers.json"
OUT_PATH = ROOT / "data/synthesis/cleanup-plan.json"

# Heuristic markers that indicate an article-title-as-thinker fake.
ARTICLE_TITLE_PATTERNS = [
    r" - ",        # "A.D. Shroff - Champion of..."
    r" on ",       # "D R Pendse on the 1991 Crisis"
    r": ",
    r" – ",        # en-dash variant
    r"\?",
    r"!",
]
ARTICLE_TITLE_PHRASE_STARTS = (
    "how i ", "the new ", "the hayek", "did bollywood", "an auxiliary",
    "indian liberal", "centre for civil",
)


def is_article_title_fake(name: str, body_excerpt: str) -> tuple[bool, str]:
    """Return (is_fake, reason). Conservative — only flag with high confidence."""
    if not name:
        return False, ""
    lower = name.lower().strip()

    # Length-based: real names rarely exceed 5 tokens
    word_count = len(name.split())
    if word_count > 5:
        return True, f"name is {word_count} words"

    # Punctuation patterns that indicate article titles
    for pat in ARTICLE_TITLE_PATTERNS:
        if re.search(pat, name):
            return True, f"matches title pattern '{pat.strip()}'"

    # Common article-style prefixes
    for phrase in ARTICLE_TITLE_PHRASE_STARTS:
        if lower.startswith(phrase):
            return True, f"starts with article phrase '{phrase}'"

    # Length cap (a person's full name is rarely > 50 chars)
    if len(name) > 60:
        return True, f"name is {len(name)} chars long"

    return False, ""


def aggressive_normalise(s: str) -> str:
    """Normalise a name for duplicate detection.

    Steps (in order):
      1. Lowercase, strip
      2. Remove honorifics (prof, dr, mr, mrs, ms, shri, sri, sir)
      3. Remove dots, commas, apostrophes, hyphens
      4. Collapse any run of single-character tokens (initials) into one token
         so 'a d shroff' and 'ad shroff' both produce 'ad shroff'
      5. Collapse whitespace
    """
    s = s.lower().strip()
    s = re.sub(r"\b(prof|dr|mr|mrs|ms|shri|sri|sir|lord|lady|the late)\b\.?", "", s)
    s = re.sub(r"[.,'’\-–—/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Collapse runs of single letters: "a d shroff" → "ad shroff"
    tokens = s.split()
    out: list[str] = []
    buffer = ""
    for t in tokens:
        if len(t) == 1 and t.isalpha():
            buffer += t
        else:
            if buffer:
                out.append(buffer)
                buffer = ""
            out.append(t)
    if buffer:
        out.append(buffer)
    return " ".join(out).strip()


def body_excerpt(p: Path) -> str:
    """Return the body (post-frontmatter) trimmed to 200 chars."""
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return ""
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.S)
    body = m.group(1) if m else text
    return body.strip()[:200]


def body_length(p: Path) -> int:
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return 0
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.S)
    return len((m.group(1) if m else text).strip())


def bio_source_priority(src: str | None) -> int:
    return {
        "canonical": 4,
        "feature_article": 3,
        "ai_drafted": 2,
        "imported": 1,
    }.get(src or "", 0)


def main() -> int:
    if not AUTHORITY.exists():
        print(f"ERROR: {AUTHORITY} not found")
        return 1
    auth = json.loads(AUTHORITY.read_text())

    # Build a working set: id → record
    records: dict[str, dict] = {}
    for t in auth.get("thinkers", []):
        tid = t["id"]
        md_path = CONTENT_DIR / f"{tid}.md"
        records[tid] = {
            "id": tid,
            "canonical": (t.get("name") or {}).get("canonical") or "",
            "full": (t.get("name") or {}).get("full") or "",
            "sort": (t.get("name") or {}).get("sort") or "",
            "also_known_as": (t.get("name") or {}).get("also_known_as") or [],
            "bio_source": t.get("bio_source", "imported"),
            "body_len": body_length(md_path) if md_path.exists() else 0,
            "body_head": body_excerpt(md_path) if md_path.exists() else "",
            "md_exists": md_path.exists(),
        }

    # ─── Pass 1: article-title fakes ────────────────────────────────────
    delete: list[dict] = []
    for tid, r in records.items():
        fake, reason = is_article_title_fake(r["canonical"], r["body_head"])
        if fake:
            delete.append({"id": tid, "canonical": r["canonical"], "reason": reason})

    fake_ids = {d["id"] for d in delete}

    # ─── Pass 2: duplicate clusters ─────────────────────────────────────
    # Group remaining records by normalised name.
    groups: dict[str, list[str]] = defaultdict(list)
    for tid, r in records.items():
        if tid in fake_ids:
            continue
        if not r["canonical"]:
            continue
        groups[aggressive_normalise(r["canonical"])].append(tid)

    merges: list[dict] = []
    for nk, ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        # Pick the winner: highest bio_source priority, then longest body,
        # then shortest slug, then alphabetic.
        ids.sort(
            key=lambda i: (
                -bio_source_priority(records[i]["bio_source"]),
                -records[i]["body_len"],
                len(i),
                i,
            )
        )
        winner = ids[0]
        losers = ids[1:]
        # Compose a best-canonical: use the winner's canonical unless it lacks
        # dots and a loser's canonical has the proper dotted form for the same
        # initials. Prefer "A.D. Shroff" over "AD Shroff" when both exist.
        canonical = records[winner]["canonical"]
        # Heuristic: if the canonical lacks any "." but a loser has the
        # exact same letters with dots, prefer the dotted version.
        for lid in losers:
            lc = records[lid]["canonical"]
            if "." in lc and "." not in canonical:
                # Check it's the same person — normalised should match (it does, since they're in this group)
                # AND the alphabet-only form should match too
                a = re.sub(r"[^a-z]", "", canonical.lower())
                b = re.sub(r"[^a-z]", "", lc.lower())
                if a == b:
                    canonical = lc
                    break
        merges.append({
            "winner": winner,
            "winner_canonical": canonical,
            "losers": losers,
            "loser_canonicals": [records[l]["canonical"] for l in losers],
            "normalised_key": nk,
        })

    # ─── Review list: probably-real but suspicious entries ──────────────
    review: list[dict] = []
    for tid, r in records.items():
        if tid in fake_ids:
            continue
        if tid in {m["winner"] for m in merges} or tid in {l for m in merges for l in m["losers"]}:
            continue
        # Flag entries that are very short (body < 100 chars) AND imported
        # source — these are stubs, real but content-less. We don't delete
        # them; they're still valid people, just await editorial.
        if r["body_len"] < 100 and r["bio_source"] == "imported":
            review.append({"id": tid, "canonical": r["canonical"], "reason": "stub body, imported"})

    plan = {
        "generated_at": "2026-05-18",
        "summary": {
            "total_thinkers": len(records),
            "to_delete": len(delete),
            "merge_clusters": len(merges),
            "review": len(review),
            "after_cleanup": len(records) - len(delete) - sum(len(m["losers"]) for m in merges),
        },
        "delete": delete,
        "merge": merges,
        "review": review,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(f"[audit] wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"[audit] summary: {plan['summary']}")
    print()
    if delete:
        print("Top deletions (first 5):")
        for d in delete[:5]:
            print(f"  - {d['id']:50}  {d['canonical']!r}  ({d['reason']})")
    print()
    if merges:
        print("Top merges (first 10):")
        for m in merges[:10]:
            losers_str = ", ".join(m["losers"])
            print(f"  - keep '{m['winner']}' as '{m['winner_canonical']}' (drop: {losers_str})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
