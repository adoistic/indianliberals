#!/usr/bin/env python3
"""Is the challenger model's disagreement bigger than the baseline's own noise?

Comparing a challenger against ONE baked Sonnet pass overstates the gap: the
two Sonnet passes (metadata.a / metadata.b) disagree with each other on 42% of
one-page works, which is why the pipeline escalates to an Opus tiebreak at all.
A challenger that lands inside that envelope is not measurably worse; the
pipeline was already going to arbitrate.

So three numbers per field, on the SAME set of works:

  noise floor   sonnet-a vs sonnet-b        irreducible extraction variance
  challenger    luna vs sonnet-a            the naive comparison
  envelope      luna agrees with a OR b     inside the model's own spread?

`envelope` is the decision number. A challenger at or above the noise floor is
at parity for practical purposes.
"""
import csv, json, os, re, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/llm-extract"))
from validator import validate_metadata  # noqa: E402

BAKE = REPO / "data/bake-off-output"
REPLAY = REPO / "data/swatantra-papers/kie-replay"
INV = REPO / "data/swatantra-papers/inventory.tsv"
F = ["work_type", "year", "title.main", "publisher_verbatim",
     "byline_verbatim", "thinker_ids"]


def dig(d, p):
    c = d
    for k in p.split("."):
        if not isinstance(c, dict):
            return None
        c = c.get(k)
        if c is None:
            return None
    return c


def six(r):
    a = r.get("authors") or []
    return {"work_type": r.get("work_type"),
            "year": dig(r, "publication.year.value"),
            "title.main": dig(r, "title.main.value"),
            "publisher_verbatim": dig(r, "publication.publisher_verbatim"),
            "byline_verbatim": " | ".join(
                sorted(str(x.get("byline_verbatim") or "") for x in a)),
            "thinker_ids": ",".join(sorted(
                str(x.get("thinker_id")) for x in a if x.get("thinker_id")))}


def norm(v):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(v or "").lower())).strip()


def parse(t):
    t = (t or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        i, j = t.find("{"), t.rfind("}")
        try:
            return json.loads(t[i:j + 1])
        except Exception:
            return None


def arm(suffix, label, normalised):
    eq = (lambda x, y: norm(x) == norm(y)) if normalised else \
         (lambda x, y: str(x or "") == str(y or ""))
    floor = Counter(); naive = Counter(); env = Counter()
    n = 0; f_all = c_all = e_all = 0
    losses = []

    for fp in sorted(REPLAY.glob(f"*.metadata.a.{suffix}.json")):
        r = json.loads(fp.read_text(encoding="utf-8"))
        if r.get("failed"):
            continue
        pj = parse(r.get("raw_text"))
        if pj is None:
            continue
        slug = r["slug"]
        pa, pb = BAKE / slug / "metadata.a.a.json", BAKE / slug / "metadata.b.b.json"
        if not (pa.exists() and pb.exists()):
            continue
        A = six(json.loads(pa.read_text(encoding="utf-8")))
        B = six(json.loads(pb.read_text(encoding="utf-8")))
        G = six(validate_metadata(pj))
        n += 1
        f_ok = c_ok = e_ok = True
        for k in F:
            if eq(A[k], B[k]):
                floor[k] += 1
            else:
                f_ok = False
            if eq(G[k], A[k]):
                naive[k] += 1
            else:
                c_ok = False
            if eq(G[k], A[k]) or eq(G[k], B[k]):
                env[k] += 1
            else:
                e_ok = False
                # a real loss: outside the range the baseline itself spans
                losses.append((slug, k, A[k], B[k], G[k]))
        f_all += f_ok; c_all += c_ok; e_all += e_ok

    if not n:
        return None
    tag = "normalised" if normalised else "raw"
    print(f"\n=== {label}  ({n} works, {tag}) ===")
    print(f"{'field':22}{'noise floor':>13}{'vs sonnet-a':>13}{'in envelope':>13}")
    for k in F:
        print(f"{k:22}{floor[k]/n*100:12.1f}%{naive[k]/n*100:12.1f}%{env[k]/n*100:12.1f}%")
    print(f"{'ALL SIX':22}{f_all/n*100:12.1f}%{c_all/n*100:12.1f}%{e_all/n*100:12.1f}%")
    return n, losses


def main():
    for normalised in (False, True):
        for suffix, label in (("gpt-5-6-luna", "luna, baseline prompt"),
                              ("gpt-5-6-luna-add", "luna + weak-model addendum")):
            arm(suffix, label, normalised)

    print("\n\n=== LOSSES OUTSIDE THE ENVELOPE (normalised, addendum arm) ===")
    res = arm("gpt-5-6-luna-add", "_", True)
    if res:
        _, losses = res
        by_field = Counter(k for _, k, *_ in losses)
        print("\nby field:", dict(by_field))
        for slug, k, a, b, g in losses[:25]:
            print(f"\n  {slug[:56]}  [{k}]")
            print(f"    sonnet-a : {a!r}")
            print(f"    sonnet-b : {b!r}")
            print(f"    luna     : {g!r}")


if __name__ == "__main__":
    main()
