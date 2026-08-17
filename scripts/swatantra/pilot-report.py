#!/usr/bin/env python3
"""Score a prepared pilot: metadata.a vs metadata.b self-consistency.

Reads the response.json each subagent wrote into its request dir and compares
the six fields driver.py escalates to Opus on disagreement:

    title.main, publisher_verbatim, byline_verbatim, year,
    authors[].thinker_id (set equality), work_type

Reports both a RAW rate and a NORMALISED rate. The difference is the point:
if most disagreements vanish under case/punctuation folding, the tiebreak tier
is being paid for formatting noise rather than for genuine ambiguity.

    python3 scripts/swatantra/pilot-report.py [manifest.json]
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT = REPO / "data/swatantra-papers/pilot/manifest.json"

FIELDS = ["work_type", "year", "title.main", "publisher_verbatim",
          "byline_verbatim", "thinker_ids"]


def norm(v):
    """Case/punctuation/whitespace folding, so 'Mr.' == 'Mr'."""
    if v is None:
        return ""
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def dig(d, path, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def extract(rec):
    """Pull the six comparison fields out of one record."""
    if not rec:
        return None
    authors = rec.get("authors") or []
    return {
        "work_type": rec.get("work_type"),
        "year": dig(rec, "publication.year.value") or dig(rec, "publication.year"),
        "title.main": dig(rec, "title.main.value") or dig(rec, "title.main"),
        "publisher_verbatim": dig(rec, "publication.publisher_verbatim"),
        "byline_verbatim": " | ".join(
            sorted(str(a.get("byline_verbatim") or "") for a in authors)),
        "thinker_ids": ",".join(sorted(
            str(a.get("thinker_id")) for a in authors if a.get("thinker_id"))),
    }


def load(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    raw_dis = Counter()
    norm_dis = Counter()
    rows, missing, wt_counts = [], 0, Counter()

    for entry in manifest:
        a = extract(load(entry["requests"]["metadata.a"]["response_path"]))
        b = extract(load(entry["requests"]["metadata.b"]["response_path"]))
        if a is None or b is None:
            missing += 1
            continue
        wt_counts[a["work_type"]] += 1
        raw_fields, norm_fields = [], []
        for f in FIELDS:
            if str(a[f]) != str(b[f]):
                raw_fields.append(f)
                raw_dis[f] += 1
            if norm(a[f]) != norm(b[f]):
                norm_fields.append(f)
                norm_dis[f] += 1
        rows.append({
            "file": entry["file"], "legibility": entry["legibility"],
            "work_type": a["work_type"],
            "hint": entry["filename_hint"].get("work_type_suggest", ""),
            "year_a": a["year"], "year_b": b["year"],
            "hint_year": entry["filename_hint"].get("year", ""),
            "raw": raw_fields, "norm": norm_fields,
        })

    n = len(rows)
    if not n:
        print("no scored documents — did the agents write response.json?")
        return 1

    print(f"scored {n} documents ({missing} missing a response)\n")
    print(f"{'file':40s} {'legib':>9s} {'work_type':>12s} {'hint':>12s}  tiebreak fields (normalised)")
    print("-" * 108)
    for r in rows:
        flag = "MATCH" if not r["norm"] else ",".join(r["norm"])
        star = " *" if r["work_type"] != r["hint"] and r["hint"] else ""
        print(f"{r['file'][:40]:40s} {r['legibility']:>9s} {r['work_type'] or '-':>12s} "
              f"{r['hint'] or '-':>12s}{star}  {flag}")

    raw_clean = sum(1 for r in rows if not r["raw"])
    norm_clean = sum(1 for r in rows if not r["norm"])
    print("\n" + "=" * 60)
    print(f"documents agreeing on all six fields:")
    print(f"  raw string comparison : {raw_clean}/{n} ({raw_clean/n*100:.0f}%)"
          f"  -> {n-raw_clean} Opus tiebreaks")
    print(f"  normalised comparison : {norm_clean}/{n} ({norm_clean/n*100:.0f}%)"
          f"  -> {n-norm_clean} Opus tiebreaks")
    saved = (n - raw_clean) - (n - norm_clean)
    if n - raw_clean:
        print(f"  normalising avoids {saved} of {n-raw_clean} tiebreaks "
              f"({saved/(n-raw_clean)*100:.0f}% of them)")
    print("\nper-field disagreement (raw -> normalised):")
    for f in FIELDS:
        print(f"  {f:22s} {raw_dis[f]:2d} -> {norm_dis[f]:2d}")
    print("\nwork_type distribution (metadata.a):")
    for k, v in wt_counts.most_common():
        print(f"  {v:2d}  {k}")
    agree_hint = sum(1 for r in rows if r["hint"] and r["work_type"] == r["hint"])
    hinted = sum(1 for r in rows if r["hint"])
    if hinted:
        print(f"\nmodel work_type == filename hint: {agree_hint}/{hinted} "
              f"({agree_hint/hinted*100:.0f}%)  [* marks divergence above]")
    yr = [r for r in rows if r["hint_year"]]
    yr_ok = sum(1 for r in yr if str(r["year_a"]) == str(r["hint_year"]))
    if yr:
        print(f"model year == filename year:      {yr_ok}/{len(yr)} "
              f"({yr_ok/len(yr)*100:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
