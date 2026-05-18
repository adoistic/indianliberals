#!/usr/bin/env python3
"""
Heuristic pre-resolver: tries to match each unlinked entry's author/subject
against the authority's byline_lookup, using slug tails and body openers.

Writes high-confidence resolutions directly to resolutions.jsonl and emits
the remaining ambiguous entries to data/synthesis/unlinked-residual.jsonl
for hand resolution.

Heuristics, in order of confidence:

  1. Slug tail of the form `...-<token>-<token>-<year>` or `...-<token>-<token>`
     where the joined tokens match a byline_lookup key.
  2. Slug tail tokens match a byline_lookup key directly (any n-gram).
  3. Body opener phrases: "By X", "Authored by X", "by Dr X", followed by
     a name that resolves via byline_lookup.

Anything that doesn't match goes to the residual file.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNLINKED = ROOT / "data/synthesis/unlinked.jsonl"
RESOLUTIONS = ROOT / "data/synthesis/resolutions.jsonl"
RESIDUAL = ROOT / "data/synthesis/unlinked-residual.jsonl"
AUTHORITY = ROOT / "data/authority/thinkers.json"

REF_FIELD_ROLE = {
    "musings": "author",
    "opinions": "subject",   # opinions ABOUT a thinker
    "interviews": "subject",
    "theprint-mirror": "author",
    "primary-works": "author",
}

YEAR_RX = re.compile(r"^\d{4}$|^[a-z]+-?\d{4}$")  # 1990, may-1990, etc.


def normalise(s: str) -> str:
    s = s.lower().replace(".", " ").replace(",", " ").replace("-", " ").replace("'", "").replace("’", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


MONTH_WORDS = {"january","february","march","april","may","june","july","august","september","october","november","december","jan","feb","mar","apr","jun","jul","aug","sep","sept","oct","nov","dec"}


def slug_tail_candidates(slug: str) -> list[str]:
    """Generate trailing-token n-grams from a slug.

    Aggressively strips trailing year + month tokens, then returns 2/3/4/5-
    token tail candidates AND every interior token pair-triple-quad that
    LOOKS like a name (lowercased run of alphabetic tokens). The byline
    is sometimes in the middle of the slug (e.g., '...-ashok-desai-1995'
    after stripping year, or '...-by-jm-lobo-prabhu' interior)."""
    parts = [p for p in slug.split("-") if p]
    # Drop trailing year + month tokens
    while parts and (YEAR_RX.match(parts[-1]) or parts[-1].lower() in MONTH_WORDS or (parts[-1].isdigit() and len(parts[-1]) <= 2)):
        parts.pop()
    candidates: list[str] = []
    for n in (5, 4, 3, 2):
        if len(parts) >= n:
            tail = " ".join(parts[-n:])
            candidates.append(tail)
            # Also strip a leading "by" / "dr" / "prof" prefix
            stripped = re.sub(r"^(by|dr|mr|mrs|ms|sir|prof|professor|justice|lord|lady|pandit|acharya|the late)\s+", "", tail)
            if stripped != tail and stripped:
                candidates.append(stripped)
    # Interior n-grams — useful when the slug ends with a topic descriptor
    # rather than the author. Generate every 2-3-token window.
    for n in (3, 2):
        for i in range(len(parts) - n + 1):
            window = " ".join(parts[i:i + n])
            if window not in candidates:
                candidates.append(window)
    return candidates


def title_prefix_candidates(title: str) -> list[str]:
    """For opinions/interviews, the subject lives at the start of the title:
        "Anandibai Joshee: First Indian Woman Doctor" → "Anandibai Joshee"
        "BR Shenoy - A Prophet Without Honour?"      → "BR Shenoy"
        "D R Pendse on the 1991 Crisis"              → "D R Pendse"
    """
    candidates: list[str] = []
    for sep in (":", " - ", " – ", " — "):
        if sep in title:
            candidates.append(title.split(sep, 1)[0].strip())
    # "<Name> on <topic>"
    m = re.search(r"^([A-Z][A-Za-z'’\-\. ]+?)\s+on\s+", title)
    if m:
        candidates.append(m.group(1).strip())
    # The whole title as a last resort (in case it's just a name)
    if 3 < len(title) < 50 and len(title.split()) <= 5:
        candidates.append(title)
    return candidates


def body_author_candidates(body: str) -> list[str]:
    """Extract possible byline strings from the body opener."""
    candidates: list[str] = []
    # "Authored by X" / "written by X"
    for pat in (
        r"(?:authored by|written by)\s+(?:Dr|Mr|Mrs|Ms|Sir|Prof|Professor|Justice|Lord|Lady|Pandit|Acharya)?\.?\s*([A-Z][A-Za-z'’\-\. ]{2,40}?)(?:\s+(?:in|for|is|at|on|argues|writes|delivers|wrote|published)\b|\s*[,.;])",
        r"\bBy\s+(?:Dr|Mr|Mrs|Ms|Sir|Prof|Professor|Justice|Lord|Lady|Pandit|Acharya)?\.?\s*([A-Z][A-Z'’\-\. ]+[A-Z])(?:\s|\b)",
        r"\bBy\s+(?:Dr|Mr|Mrs|Ms|Sir|Prof|Professor|Justice|Lord|Lady|Pandit|Acharya)?\.?\s*([A-Z][A-Za-z'’\-\. ]{2,40}?)\s*(?:Summary|\b---\b|$)",
    ):
        for m in re.finditer(pat, body, flags=re.I):
            cand = m.group(1).strip(" .,").strip()
            if 3 < len(cand) < 60:
                candidates.append(cand)
    return candidates


def main() -> int:
    auth = json.loads(AUTHORITY.read_text())
    byline_lookup: dict[str, str] = auth.get("byline_lookup", {})

    # Add normalised aliases for every thinker's canonical + sort + full
    canonical_by_id = {}
    for t in auth.get("thinkers", []):
        tid = t["id"]
        name = t.get("name", {})
        canonical_by_id[tid] = name.get("canonical", tid)
        for src in [name.get("canonical"), name.get("full"), name.get("sort"), *(name.get("also_known_as") or [])]:
            if not src:
                continue
            n = normalise(src)
            if n and n not in byline_lookup:
                byline_lookup[n] = tid
            # honorific-stripped
            n2 = re.sub(r"^(prof|dr|mr|mrs|ms|shri|sri|sir|lord|lady|pandit|acharya)\s+", "", n)
            if n2 and n2 not in byline_lookup:
                byline_lookup[n2] = tid

    # Load already-resolved IDs from existing resolutions.jsonl
    already = set()
    if RESOLUTIONS.exists():
        with RESOLUTIONS.open() as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("id"):
                        already.add(r["id"])
                except json.JSONDecodeError:
                    continue

    new_resolutions: list[dict] = []
    residual: list[dict] = []

    with UNLINKED.open() as f:
        entries = [json.loads(l) for l in f if l.strip()]

    for entry in entries:
        if entry["id"] in already:
            continue
        slug = entry["slug"]
        body = entry.get("body_excerpt", "")
        title = entry.get("title", "")
        role = REF_FIELD_ROLE.get(entry["collection"], "author")
        # Try slug-tail candidates
        match_id = None
        match_source = None
        for cand in slug_tail_candidates(slug):
            if normalise(cand) in byline_lookup:
                match_id = byline_lookup[normalise(cand)]
                match_source = f"slug_tail:{cand}"
                break
        # For opinions / interviews, the subject is often the title prefix
        if not match_id and entry["collection"] in ("opinions", "interviews"):
            for cand in title_prefix_candidates(title):
                if normalise(cand) in byline_lookup:
                    match_id = byline_lookup[normalise(cand)]
                    match_source = f"title_prefix:{cand}"
                    break
        if not match_id:
            for cand in body_author_candidates(body):
                if normalise(cand) in byline_lookup:
                    match_id = byline_lookup[normalise(cand)]
                    match_source = f"body_byline:{cand}"
                    break
        if match_id:
            new_resolutions.append({
                "id": entry["id"],
                "collection": entry["collection"],
                "primary_role": role,
                "action": "match",
                "primary_thinker_id": match_id,
                "confidence": "high",
                "_via": match_source,
            })
        else:
            residual.append(entry)

    # Append matches to resolutions.jsonl
    with RESOLUTIONS.open("a") as f:
        for r in new_resolutions:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # Write residual
    with RESIDUAL.open("w") as f:
        for e in residual:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"[heuristic] matched: {len(new_resolutions)}")
    print(f"[heuristic] residual: {len(residual)} (written to {RESIDUAL.relative_to(ROOT)})")
    # Break down residual by collection
    from collections import Counter
    c = Counter(e["collection"] for e in residual)
    for k, v in c.most_common():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
