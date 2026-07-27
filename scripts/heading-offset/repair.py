#!/usr/bin/env python3
"""
Re-pair article headings and bylines with the prose they belong to.

`measure.py` establishes what is wrong. This fixes it.

The failure mode is not a constant shift. The v1.5 extraction produced a list of
headings and a list of per-article summaries and zipped them together; wherever
the two lists diverge, because a heading was captured with no summary or a
summary with no heading, everything after the divergence is misaligned. Files
with two divergences show two different offsets, and the offsets run in both
directions. So a rotation is the wrong tool. This is a sequence alignment.

Both lists are in page order, which is the property that makes alignment sound:
we need a monotonic match that permits gaps on either side. The score comes from
the prose naming its own article, exactly as in measure.py, so a pairing is only
credited when the prose says so.

    headings:  A  B  C  D  E   -
    prose:     a  -  c  d  e   f
               |     |  |  |   |
    result:   A/a   C/c D/d E/e  f keeps a title derived from its own prose

Nothing is invented. Where a prose block aligns to no heading, its title is
taken from the title the prose itself quotes; if it quotes none, the section is
left alone and reported. Where a heading aligns to no prose, the heading is kept
as a section with no body rather than dropped, because the article did appear in
the issue and losing it would be a second error on top of the first.

Usage:
    python3 scripts/heading-offset/repair.py --dry-run
    python3 scripts/heading-offset/repair.py --dry-run --detail ff130
    python3 scripts/heading-offset/repair.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from measure import (
    BYLINE_RE,
    identify,
    GENERIC_TITLES,
    POSSESSIVE_RE,
    QUOTED_RE,
    REPO,
    WORKS,
    content_words,
    fold,
    same_title,
    strip_frontmatter,
    surname,
)

HERE = Path(__file__).resolve().parent
REPORT = HERE / "repair-report.json"

ORPHAN_NOTE = "*No summary was extracted for this article. Listed for completeness.*"

MATCH = 3.0        # the prose names this heading
GAP_OPEN = -1.2    # begin skipping: one dropped heading, or one unlabelled block
GAP_EXTEND = -0.2  # continue skipping
PAIR_NO_EVIDENCE = -0.15  # pair two things the prose never connected
PAIR_CONTRADICTED = -4.0  # pair two things the prose says do NOT belong together
GAP = GAP_OPEN     # kept for the row/column initialisation

# The penalties above were rebalanced after a hand audit of twelve files the
# first version left untouched: all twelve were genuinely misjoined, and the
# aligner had priced the correct answer out of reach.
#
# Two bugs, one cause. A contradicted pairing scored the same as an unevidenced
# one, so the aligner treated "the prose explicitly names a different heading"
# as no information at all. And shifting a tail by one costs two gap openings,
# which at -2.5 each meant a shift needed two or more confirmed pairings to pay
# for itself. Most broken files have exactly one, so most broken files stayed
# broken.
#
# Now contradiction is expensive and gaps are cheap, which is the right shape:
# the prose is the evidence, and a dropped heading is an ordinary event in this
# corpus rather than an extraordinary one.

# Affine gaps, deliberately. The true structure is runs of constant offset broken
# by the occasional dropped heading or unlabelled summary, so opening a gap must
# cost much more than continuing one. With a flat penalty the aligner scattered
# single gaps through the middle of a run to chase stray evidence, which moved
# labels that were already correct.


def sections_with_spans(body: str) -> list[dict]:
    """
    Parse `###` sections, keeping the exact source spans so a rewrite can
    replace only the heading and byline lines and leave the prose byte-identical.
    """
    out: list[dict] = []
    matches = list(re.finditer(r"^### (.*)$", body, flags=re.MULTILINE))
    for n, match in enumerate(matches):
        start = match.start()
        end = matches[n + 1].start() if n + 1 < len(matches) else len(body)
        chunk = body[start:end]
        lines = chunk.splitlines(keepends=True)
        heading = match.group(1).strip()

        byline = None
        byline_line = None
        consumed = 1
        for offset in range(1, min(5, len(lines))):
            bm = BYLINE_RE.match(lines[offset].strip())
            if bm:
                byline = bm.group(1).strip()
                byline_line = offset
                consumed = offset + 1
                break
            if lines[offset].strip():
                break

        prose = "".join(lines[consumed:])
        # A heading this tool previously found no prose for. It must not be
        # re-read as a prose block: doing so let the note itself get re-orphaned
        # on the next run, which grew the file by a section every pass and left
        # two files oscillating between headings forever.
        stripped = prose.replace(ORPHAN_NOTE, "").strip()
        out.append(
            {
                "index": n,
                "heading": heading,
                "byline": byline,
                "placeholder": not stripped,
                "byline_line": byline_line,
                "prose": prose,
                "prose_text": " ".join(prose.split()),
                "span": (start, end),
                "lines": lines,
                "consumed": consumed,
            }
        )
    return out


def claimed_index(sec: dict, headings: list[dict]) -> int | None:
    """The single heading this section's prose claims as its own, if any."""
    if "_claimed" not in sec:
        sec["_claimed"] = identify(sec["prose_text"], [h["heading"] for h in headings])
    return sec["_claimed"]


def prose_names(sec: dict, heading: str, headings: list[dict] | None = None) -> bool:
    """Does this section's prose identify the given heading as its own article?"""
    if headings is None:
        opening = sec["prose_text"][:400]
        return any(same_title(heading, cand) for cand in QUOTED_RE.findall(opening))
    index = claimed_index(sec, headings)
    return index is not None and headings[index]["heading"] == heading


def self_title(sec: dict) -> str | None:
    """
    The article title the prose quotes about itself, if any is usable.

    Used only when a prose block aligns to no heading at all, so it must be
    conservative: a candidate needs two distinctive words to be trusted as a
    title rather than a stray quotation.
    """
    opening = sec["prose_text"][:400]
    for cand in QUOTED_RE.findall(opening):
        words = content_words(cand) - GENERIC_TITLES
        if len(words) >= 2 and len(cand) < 90:
            return cand.strip()
    return None


def self_author(sec: dict) -> str | None:
    match = POSSESSIVE_RE.match(sec["prose_text"][:400])
    return match.group(1).strip() if match else None


def align(secs: list[dict], headings: list[dict]) -> list[int | None]:
    """
    Monotonic alignment of prose blocks to headings, gaps allowed on both sides.

    Needleman-Wunsch over a sparse evidence matrix. Returns, for each prose
    block, the heading index it pairs with, or None for a gap.
    """
    n, m = len(secs), len(headings)
    NEG = float("-inf")
    # Three states, so a gap knows whether it is being opened or continued. The
    # traceback has to follow states rather than cells: when a gap is extended,
    # the predecessor is that same gap state, not whatever scored best there.
    S = {"diag": [[NEG] * (m + 1) for _ in range(n + 1)],
         "up": [[NEG] * (m + 1) for _ in range(n + 1)],
         "left": [[NEG] * (m + 1) for _ in range(n + 1)]}
    B = {"diag": [[None] * (m + 1) for _ in range(n + 1)],
         "up": [[None] * (m + 1) for _ in range(n + 1)],
         "left": [[None] * (m + 1) for _ in range(n + 1)]}

    S["diag"][0][0] = 0.0
    for i in range(1, n + 1):
        S["up"][i][0] = GAP_OPEN + GAP_EXTEND * (i - 1)
        B["up"][i][0] = "diag" if i == 1 else "up"
    for j in range(1, m + 1):
        S["left"][0][j] = GAP_OPEN + GAP_EXTEND * (j - 1)
        B["left"][0][j] = "diag" if j == 1 else "left"

    def best_state(i: int, j: int) -> tuple[float, str]:
        return max(((S[k][i][j], k) for k in S), key=lambda t: t[0])

    def evidence_for(i: int, j: int) -> float:
        claim = claimed_index(secs[i], headings)
        if claim == j:
            return MATCH
        # Byline agreement is weaker evidence than a quoted title, but it is the
        # only signal for sections whose prose names no title.
        claimed = self_author(secs[i])
        own = headings[j]["byline"]
        if claimed and own and surname(claimed) and surname(claimed) == surname(own):
            return MATCH * 0.8
        if claim is not None:
            # The prose names a different heading. That is evidence against this
            # pairing, not an absence of evidence, and scoring it as neutral is
            # what let whole files stay misjoined.
            return PAIR_CONTRADICTED
        return PAIR_NO_EVIDENCE

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            prev_score, prev_state = best_state(i - 1, j - 1)
            if prev_score > NEG:
                S["diag"][i][j] = prev_score + evidence_for(i - 1, j - 1)
                B["diag"][i][j] = prev_state

            open_score, open_state = best_state(i - 1, j)
            open_score += GAP_OPEN
            extend_score = S["up"][i - 1][j] + GAP_EXTEND
            if extend_score > open_score:
                S["up"][i][j], B["up"][i][j] = extend_score, "up"
            else:
                S["up"][i][j], B["up"][i][j] = open_score, open_state

            open_score, open_state = best_state(i, j - 1)
            open_score += GAP_OPEN
            extend_score = S["left"][i][j - 1] + GAP_EXTEND
            if extend_score > open_score:
                S["left"][i][j], B["left"][i][j] = extend_score, "left"
            else:
                S["left"][i][j], B["left"][i][j] = open_score, open_state

    pairing: list[int | None] = [None] * n
    i, j = n, m
    _, state = best_state(i, j)
    while i > 0 or j > 0:
        nxt = B[state][i][j]
        if state == "diag":
            pairing[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif state == "up":
            i -= 1
        else:
            j -= 1
        if i == 0 and j == 0:
            break
        state = nxt or ("up" if j == 0 else "left")
    return pairing


def evidence_count(secs: list[dict], headings: list[dict], pairing: list[int | None]) -> tuple[int, int]:
    """How many pairings the prose positively confirms, and how many it contradicts."""
    confirmed = contradicted = 0
    for i, j in enumerate(pairing):
        claim = claimed_index(secs[i], headings)
        if claim is None:
            continue
        if j == claim:
            confirmed += 1
        else:
            contradicted += 1
    return confirmed, contradicted


def rebuild(body: str, secs: list[dict], headings: list[dict], pairing: list[int | None]) -> tuple[str, list[dict]]:
    """Rewrite the body with each prose block under its aligned heading."""
    changes: list[dict] = []
    pieces: list[str] = [body[: secs[0]["span"][0]]]

    used = {j for j in pairing if j is not None}
    emitted: set[int] = set()
    emitted_headings: list[str] = []

    def emit_orphan(k: int) -> None:
        """A heading no prose claimed. The article was in the issue, so keep it."""
        pieces.append(f"### {headings[k]['heading']}\n")
        emitted_headings.append(headings[k]["heading"])
        if headings[k]["byline"]:
            pieces.append(f"*By {headings[k]['byline']}*\n")
        pieces.append(f"\n{ORPHAN_NOTE}\n\n")
        emitted.add(k)

    for i, sec in enumerate(secs):
        j = pairing[i]
        # Keep orphans in page order rather than sweeping them to the end: an
        # article listed out of sequence reads as an editorial afterthought
        # instead of the item that actually sat there in the issue.
        if j is not None:
            for k in range(j):
                if k not in used and k not in emitted:
                    emit_orphan(k)
        if j is not None:
            new_heading = headings[j]["heading"]
            new_byline = headings[j]["byline"]
            source = "aligned"
        else:
            derived = self_title(sec)
            previous = emitted_headings[-1] if emitted_headings else None
            author = self_author(sec)

            if derived is not None and fold(derived) == fold(previous or ""):
                # A column continued across pages: the second block names the
                # same piece as the one above it. The archive has several of
                # these ("Point Counter Point" runs on, "Of Cabbages and Kings"
                # carries two batches). Emit the prose under the heading already
                # standing rather than repeating it.
                pieces.append(sec["prose"] if sec["prose"].startswith("\n") else "\n" + sec["prose"])
                changes.append({
                    "index": i,
                    "from": {"heading": sec["heading"], "byline": sec["byline"]},
                    "to": {"heading": previous, "byline": None},
                    "source": "continuation of the preceding section",
                })
                continue

            if derived is not None and fold(derived) not in {fold(h) for h in emitted_headings}:
                new_heading = derived
                new_byline = author
                source = "derived from prose"
            else:
                # Either the prose names no title, or the title it names is
                # already standing elsewhere in the issue and this is not a
                # continuation of it. Inventing a heading would be a guess and
                # repeating one would be a lie, so use the pipeline's own
                # neutral placeholder, which claims nothing, and keep whatever
                # author the prose does name.
                new_heading = f"Essay {i + 1}"
                new_byline = author
                source = "unlabelled: neutral placeholder"

        if new_heading != sec["heading"] or new_byline != sec["byline"]:
            changes.append(
                {
                    "index": i,
                    "from": {"heading": sec["heading"], "byline": sec["byline"]},
                    "to": {"heading": new_heading, "byline": new_byline},
                    "source": source,
                }
            )

        pieces.append(f"### {new_heading}\n")
        emitted_headings.append(new_heading)
        if new_byline:
            pieces.append(f"*By {new_byline}*\n")
        # Preserve the blank line that separated the label block from the prose.
        prose = sec["prose"]
        if not prose.startswith("\n"):
            pieces.append("\n")
        pieces.append(prose)

    # Any orphan headings after the last paired one.
    for k in range(len(headings)):
        if k not in used and k not in emitted:
            emit_orphan(k)

    return "".join(pieces), changes


def main() -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    ap.add_argument("--detail", help="show the full plan for one work id")
    ap.add_argument("--min-confirmed", type=int, default=2,
                    help="minimum positively confirmed pairings before a file is rewritten")
    args = ap.parse_args()

    measured = json.loads((HERE / "measured.json").read_text(encoding="utf-8"))
    broken = {r["id"] for r in measured if r["broken"]}

    report: list[dict] = []
    rewritten = skipped = 0

    for slug in sorted(broken):
        if args.detail and slug != args.detail:
            continue
        path = WORKS / f"{slug}.md"
        text = path.read_text(encoding="utf-8")
        split = text.find("\n---", 3)
        head, body = text[: split + 4], text[split + 4 :]

        all_secs = sections_with_spans(body)
        if len(all_secs) < 2:
            continue
        headings = [{"heading": s["heading"], "byline": s["byline"]} for s in all_secs]
        # Placeholder sections carry a heading but no prose, so they belong in
        # the heading sequence and must stay out of the prose sequence.
        secs = [s for s in all_secs if not s["placeholder"]]
        if not secs:
            continue

        pairing = align(secs, headings)
        confirmed, contradicted = evidence_count(secs, headings, pairing)

        identity = [all_secs.index(s) for s in secs]
        unchanged_plan = pairing == identity

        new_body, changes = rebuild(body, secs, headings, pairing)

        entry = {
            "id": slug,
            "sections": len(secs),
            "confirmed": confirmed,
            "contradicted": contradicted,
            "changes": len(changes),
            "pairing": pairing,
            "detail": changes,
        }

        # Never leave a file with a heading it did not have twice before. A
        # gapped prose block takes its title from the title its own prose
        # quotes, and that title can collide with a heading already used
        # elsewhere in the issue. Rather than reason about every way two
        # articles can share a name, refuse the rewrite and report it: 71
        # duplicated headings across 54 files got in before this existed.
        def repeats(text: str) -> int:
            found = [h.strip() for h in re.findall(r"^### (.*)$", text, flags=re.MULTILINE)]
            return len(found) - len(set(found))

        introduces_duplicate = repeats(new_body) > repeats(body)

        safe = (
            not unchanged_plan
            and confirmed >= args.min_confirmed
            and contradicted == 0
            and changes
            and not introduces_duplicate
        )
        entry["action"] = "rewrite" if safe else "skip"
        if not safe:
            entry["reason"] = (
                "would repeat a heading" if introduces_duplicate
                else f"{contradicted} pairing(s) contradicted by the prose" if contradicted
                else "alignment matches current labels" if unchanged_plan
                else f"only {confirmed} confirmed pairing(s)" if confirmed < args.min_confirmed
                else "no label changes"
            )
        report.append(entry)

        if args.detail:
            print(f"{slug}: {len(secs)} sections · confirmed {confirmed} · contradicted {contradicted}")
            print(f"  action: {entry['action']}" + (f" ({entry.get('reason')})" if entry.get("reason") else ""))
            print(f"  pairing: {pairing}")
            for change in changes:
                print(f"  [{change['index']:2}] {change['source']}")
                print(f"       was: {change['from']['heading'][:60]}  /  {change['from']['byline']}")
                print(f"       now: {change['to']['heading'][:60]}  /  {change['to']['byline']}")
            return 0

        if safe and args.apply:
            path.write_text(head + new_body, encoding="utf-8")
            rewritten += 1
        elif safe:
            rewritten += 1
        else:
            skipped += 1

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    verb = "rewrote" if args.apply else "would rewrite"
    print(f"misjoined files considered: {len(report)}")
    print(f"  {verb}: {rewritten}")
    print(f"  skipped: {skipped}")
    total_changes = sum(r["changes"] for r in report if r["action"] == "rewrite")
    print(f"  section labels corrected: {total_changes}")
    reasons: dict[str, int] = {}
    for r in report:
        if r["action"] == "skip":
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    if reasons:
        print("  skip reasons:")
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"    {count:4}  {reason}")
    print(f"wrote {REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
