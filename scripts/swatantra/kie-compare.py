#!/usr/bin/env python3
"""Score kie.ai replay records against their baked Sonnet baselines.

Pure local — no network, no credential — so it can be re-run freely as more
replays land.

Two methodological points that decide whether the numbers mean anything:

  1. The baked records went through validate_metadata() before being written
     to disk. Comparing a raw kie response against a validated baseline would
     charge kie for corrections the validator would have made anyway, so the
     kie output is put through the same validator first. Like for like.

  2. Agreement is reported raw AND normalised. Raw catches "(M. R. MASANI)"
     vs "M. R. Masani" as a disagreement; normalised does not. A pipeline that
     feeds a slug-matching authority resolver cares about the normalised
     number; a diff of the archival record cares about the raw one.

    python3 scripts/swatantra/kie-compare.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/llm-extract"))
from validator import validate_metadata  # noqa: E402

BAKE = REPO / "data/bake-off-output"
REPLAY = REPO / "data/swatantra-papers/kie-replay"
FIELDS = ["work_type", "year", "title.main", "publisher_verbatim",
          "byline_verbatim", "thinker_ids"]


def dig(d, path, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def six(rec):
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


def norm(v):
    if v is None:
        return ""
    s = re.sub(r"[^a-z0-9 ]+", " ", str(v).lower())
    return re.sub(r"\s+", " ", s).strip()


def parse_json_loose(text):
    """Model output may be fenced or have prose around it."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(t[i:j + 1])
        except json.JSONDecodeError:
            return None
    return None


def main():
    if not REPLAY.exists():
        return print("no replay records yet")
    files = sorted(REPLAY.glob("*.metadata.a.*.json"))
    if not files:
        return print("no replay records yet")

    raw_dis, norm_dis = Counter(), Counter()
    rows, failed, unparsed, usage = [], [], [], []

    for f in files:
        r = json.loads(f.read_text(encoding="utf-8"))
        slug = r["slug"]
        if r.get("failed"):
            failed.append((slug, r["failed"]))
            continue
        usage.append(r)

        parsed = parse_json_loose(r.get("raw_text"))
        if parsed is None:
            unparsed.append(slug)
            continue

        kie = six(validate_metadata(parsed))
        base_path = BAKE / slug / "metadata.a.a.json"
        if not base_path.exists():
            continue
        base = six(json.loads(base_path.read_text(encoding="utf-8")))

        diffs_raw = [k for k in FIELDS if str(base[k] or "") != str(kie[k] or "")]
        diffs_norm = [k for k in FIELDS if norm(base[k]) != norm(kie[k])]
        for k in diffs_raw:
            raw_dis[k] += 1
        for k in diffs_norm:
            norm_dis[k] += 1
        rows.append((slug, base, kie, diffs_raw, diffs_norm))

    n = len(rows)
    print(f"replay records : {len(files)}")
    print(f"  hard failures: {len(failed)}")
    print(f"  unparseable  : {len(unparsed)}")
    print(f"  scored       : {n}\n")

    if failed:
        print("FAILURES")
        for s, e in failed:
            print(f"  {s[:55]:55} {str(e)[:50]}")
        print()

    if n:
        clean_raw = sum(1 for r in rows if not r[3])
        clean_norm = sum(1 for r in rows if not r[4])
        print(f"agree on all six (raw)       : {clean_raw}/{n} "
              f"({clean_raw/n*100:.0f}%)")
        print(f"agree on all six (normalised): {clean_norm}/{n} "
              f"({clean_norm/n*100:.0f}%)\n")
        print(f"{'field':22} {'raw':>8} {'norm':>8}")
        for k in FIELDS:
            print(f"{k:22} {raw_dis[k]:>4}/{n:<3} {norm_dis[k]:>4}/{n:<3}")
        print()
        for slug, base, kie, d_raw, d_norm in rows:
            if not d_raw:
                continue
            print(f"— {slug}")
            for k in d_raw:
                flag = "" if k in d_norm else "   (normalises away)"
                print(f"    {k}")
                print(f"      sonnet : {base[k]!r}")
                print(f"      kie    : {kie[k]!r}{flag}")
        print()

    if usage:
        print("TOKEN USAGE (kie)")
        tot = Counter()
        for r in usage:
            for k, v in (r.get("usage") or {}).items():
                if isinstance(v, int):
                    tot[k] += v
        served = Counter(r.get("served_model") for r in usage)
        cred = sum(r.get("credits_consumed") or 0 for r in usage)
        tries = Counter(r.get("attempts") for r in usage)
        for k, v in tot.items():
            print(f"  {k:32} {v:>9,}  (mean {v/len(usage):>8,.0f})")
        print(f"  credits consumed                 {cred:>9.2f}  "
              f"(= ${cred/200:.4f}, mean ${cred/200/len(usage):.4f}/doc)")
        print(f"  served model(s)                  {dict(served)}")
        print(f"  attempts to succeed              {dict(sorted(tries.items()))}")
        mean_wall = sum(r["wall_clock_s"] for r in usage) / len(usage)
        print(f"  mean wall clock                  {mean_wall:.1f}s")


if __name__ == "__main__":
    main()
