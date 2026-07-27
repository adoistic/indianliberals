#!/usr/bin/env python3
"""
Measure the heading/byline misjoin in multi-article primary works.

`detect.py` flags files by token overlap between a heading and the prose below
it, and returned 234 suspects on a threshold that was never validated. This
script measures the thing itself instead of estimating it.

The lever is that the extraction pipeline wrote each article's prose as a
third-person summary that names its own subject: "S. Sharangpani's 'Double-cross
At Moshi' recounts how the Indian delegation…". So the prose carries its own
label, and we can ask, per section, whether the `###` heading and `*By …*` byline
sitting above it agree with what the prose says about itself.

Three outcomes per section:

  agrees        the prose names the heading above it, or its byline author
  disagrees     the prose names a *different* heading from the same file
  undetermined  the prose names nothing we can match, so no claim either way

A file is only called broken on `disagrees`. `undetermined` is not evidence.

The important finding is in what the disagreements look like. In ff130 they are
not a uniform shift: some headings have no prose at all ("Innocent By
Definition"), and some prose has no heading (the 'Six Years Under Communism'
review). So a blanket "rotate every heading by one" would repair the middle of
the file and corrupt both ends. The repair has to re-pair section by section.

Usage:
    python3 scripts/heading-offset/measure.py
    python3 scripts/heading-offset/measure.py --detail ff130
    python3 scripts/heading-offset/measure.py --only-suspected
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKS = REPO / "apps" / "site" / "src" / "content" / "primary-works"
HERE = Path(__file__).resolve().parent
SUSPECTED = HERE / "suspected.json"
OUT = HERE / "measured.json"

# Titles the prose quotes about itself. Straight and curly, single and double.
QUOTED_RE = re.compile(r"['\"‘’“”]([^'\"‘’“”]{4,90})['\"‘’“”]")
# "Raman Desai's opening piece argues…" / "M. A. Venkata Rao's 'De-Militarisation…'"
POSSESSIVE_RE = re.compile(r"^([A-Z][A-Za-z.’' -]{2,40}?)[’']s\s")
BYLINE_RE = re.compile(r"^\*By\s+(?:by\s+)?(.+?)\*\s*$")

# How much of a heading's words must appear in a candidate title to call it the
# same article. Titles get transcribed with '[sic]', punctuation drift, and
# subtitle truncation, so this is deliberately loose on wording and strict on
# length.
MATCH_RATIO = 0.7


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


STOP = {"the", "a", "an", "of", "and", "in", "to", "for", "on", "at", "by", "is", "it"}


def content_words(text: str) -> set[str]:
    return {w for w in fold(text).split() if w not in STOP and len(w) > 2}


# Quoted strings too generic to identify an article. Left in, a prose block that
# merely says the word "Review" matches every heading beginning "Review:", which
# manufactured both false agreements and false disagreements.
GENERIC_TITLES = {
    "review", "reviews", "notes", "note", "editorial", "editorials", "letters",
    "letter", "obituary", "books", "book", "correspondence", "comment",
    "comments", "sic", "the", "contents", "cover", "article", "articles",
    "quotes", "quotations", "extracts", "excerpt", "excerpts", "summary",
}


def same_title(heading: str, candidate: str) -> bool:
    """
    Is `candidate`, quoted inside prose, the article titled `heading`?

    Both sides must carry at least two distinctive words, and the overlap has to
    be substantial from the heading's side as well as the candidate's. A
    one-word candidate is rejected outright: it cannot distinguish one article
    from another, and accepting it was the largest source of error in the first
    version of this script.
    """
    h, c = content_words(heading), content_words(candidate)
    if not h or not c:
        return False
    if c <= GENERIC_TITLES or h <= GENERIC_TITLES:
        return False
    # An exact quotation of the whole heading is unambiguous however short it is.
    # Without this, a real title like "The Peacock" carries one distinctive word
    # and fails the two-word floor below, which cost a correct pairing in ff130.
    if fold(heading) == fold(candidate) or h == c:
        return True
    if len(c) < 2:
        return False
    c = c - GENERIC_TITLES
    if len(c) < 2:
        return False
    overlap = len(h & c)
    if overlap < 2:
        return False
    return overlap / len(h) >= MATCH_RATIO and overlap / len(c) >= 0.5


def surname(name: str) -> str:
    parts = [p for p in fold(name).split() if len(p) > 2]
    return parts[-1] if parts else ""


def identify(prose: str, headings: list[str]) -> int | None:
    """
    Which heading does this prose block claim as its own?

    Only the *first* quoted title that matches any heading counts. A summary
    routinely mentions the article after it ("It is followed by James McAuley's
    poem 'Innocent by Definition'"), and crediting every quotation made prose
    blocks appear to claim two headings at once, which is what misled the first
    version of the aligner. The self-identification comes first; everything after
    it is a cross-reference.
    """
    opening = prose[:400]
    for candidate in QUOTED_RE.findall(opening):
        for index, heading in enumerate(headings):
            if same_title(heading, candidate):
                return index
    return None


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    return text[end + 4 :] if end != -1 else text


def sections(body: str) -> list[dict]:
    out: list[dict] = []
    for chunk in re.split(r"^### ", body, flags=re.MULTILINE)[1:]:
        lines = chunk.splitlines()
        heading = lines[0].strip()
        byline = None
        rest = 1
        for offset, line in enumerate(lines[1:5], start=1):
            match = BYLINE_RE.match(line.strip())
            if match:
                byline = match.group(1).strip()
                rest = offset + 1
                break
        prose_lines = [l for l in lines[rest:] if not l.strip().startswith("- ")]
        prose = " ".join(" ".join(prose_lines).split())
        out.append({"heading": heading, "byline": byline, "prose": prose})
    return out


def analyse(slug: str, body: str) -> dict | None:
    secs = sections(body)
    if len(secs) < 2:
        return None

    headings = [s["heading"] for s in secs]
    verdicts: list[dict] = []

    for index, sec in enumerate(secs):
        prose = sec["prose"]
        # The opening sentence carries the self-identification; later sentences
        # quote other things and would produce false matches.
        opening = prose[:400]
        candidates = QUOTED_RE.findall(opening)
        possessive = POSSESSIVE_RE.match(opening)
        claimed_author = possessive.group(1) if possessive else None

        # Which heading in this file does the prose claim as its own? Exactly
        # one, or none: see identify().
        claimed_index = identify(prose, headings)

        verdict = "undetermined"
        points_to = None
        if claimed_index == index:
            verdict = "agrees"
        elif claimed_index is not None:
            verdict = "disagrees"
            points_to = claimed_index
        elif claimed_author and sec["byline"]:
            # No quoted title, but the prose opens with an author's name. If it
            # is this section's byline the label holds; if it is a *different*
            # section's byline the label is misjoined.
            own = surname(sec["byline"])
            claimed = surname(claimed_author)
            if own and claimed and own == claimed:
                verdict = "agrees"
            elif claimed:
                for other, s in enumerate(secs):
                    if other != index and s["byline"] and surname(s["byline"]) == claimed:
                        verdict = "disagrees"
                        points_to = other
                        break

        verdicts.append(
            {
                "index": index,
                "heading": sec["heading"],
                "byline": sec["byline"],
                "verdict": verdict,
                "points_to": points_to,
                "offset": (points_to - index) if points_to is not None else None,
                "prose_opening": prose[:120],
            }
        )

    counts = Counter(v["verdict"] for v in verdicts)
    offsets = Counter(v["offset"] for v in verdicts if v["offset"] is not None)
    decided = counts["agrees"] + counts["disagrees"]

    return {
        "id": slug,
        "sections": len(secs),
        "agrees": counts["agrees"],
        "disagrees": counts["disagrees"],
        "undetermined": counts["undetermined"],
        "decided": decided,
        "broken": counts["disagrees"] > 0,
        # A single dominant offset means a rotation would fix most of the file;
        # a spread means headings and prose are missing on both sides and a
        # rotation would do damage.
        "offsets": dict(sorted(offsets.items())),
        "uniform_offset": (
            list(offsets)[0] if len(offsets) == 1 and counts["disagrees"] > 0 else None
        ),
        "verdicts": verdicts,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", help="print every section verdict for one work id")
    ap.add_argument("--only-suspected", action="store_true", help="limit to suspected.json")
    args = ap.parse_args()

    suspected = set()
    if SUSPECTED.exists():
        with SUSPECTED.open(encoding="utf-8") as fh:
            suspected = set(json.load(fh))

    results: list[dict] = []
    for path in sorted(WORKS.glob("*.md")):
        slug = path.stem
        if args.detail and slug != args.detail:
            continue
        if args.only_suspected and slug not in suspected:
            continue
        body = strip_frontmatter(path.read_text(encoding="utf-8"))
        if "### " not in body:
            continue
        row = analyse(slug, body)
        if row:
            results.append(row)

    if args.detail:
        if not results:
            print(f"no multi-article body found for {args.detail}")
            return 1
        row = results[0]
        print(f"{row['id']}: {row['sections']} sections · "
              f"{row['agrees']} agree, {row['disagrees']} disagree, "
              f"{row['undetermined']} undetermined")
        print(f"  offsets seen: {row['offsets']}  uniform: {row['uniform_offset']}")
        for v in row["verdicts"]:
            arrow = "" if v["points_to"] is None else f"  -> section {v['points_to']} (offset {v['offset']:+d})"
            print(f"  [{v['index']:2}] {v['verdict']:13}{arrow}")
            print(f"       H: {v['heading'][:66]}")
            print(f"       B: {v['byline']}")
            print(f"       P: {v['prose_opening']}")
        return 0

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    broken = [r for r in results if r["broken"]]
    clean = [r for r in results if not r["broken"] and r["decided"] > 0]
    silent = [r for r in results if r["decided"] == 0]
    uniform = [r for r in broken if r["uniform_offset"] is not None]

    print(f"multi-article works examined: {len(results)}")
    print(f"  misjoined (>=1 section disagrees) : {len(broken)}")
    print(f"  consistent, with evidence        : {len(clean)}")
    print(f"  no evidence either way           : {len(silent)}")
    print()
    print(f"  of the misjoined, a single uniform offset: {len(uniform)}")
    print(f"  mixed or multiple offsets               : {len(broken) - len(uniform)}")
    print()
    total_sections = sum(r["sections"] for r in results)
    bad_sections = sum(r["disagrees"] for r in results)
    print(f"  sections total {total_sections} · misjoined {bad_sections} "
          f"({bad_sections / total_sections * 100:.1f}%)")
    print()
    if suspected:
        flagged_and_broken = sum(1 for r in broken if r["id"] in suspected)
        flagged = sum(1 for r in results if r["id"] in suspected)
        missed = len(broken) - flagged_and_broken
        print(f"  against detect.py's {len(suspected)} suspects:")
        print(f"    suspects examined here          : {flagged}")
        print(f"    suspects confirmed misjoined    : {flagged_and_broken}"
              f"  (precision {flagged_and_broken / flagged * 100:.0f}% of examined)" if flagged else "")
        print(f"    misjoined files it never flagged: {missed}")
    print(f"\nwrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
