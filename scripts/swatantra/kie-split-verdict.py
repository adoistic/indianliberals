#!/usr/bin/env python3
"""Does a cross-model split CATCH the cheap model's systematic errors?

The pipeline's quality mechanism is disagreement: metadata.a vs metadata.b,
escalating to a tiebreak when they differ. Running both passes on the SAME
model cannot catch a systematic bias — the model makes the same mistake twice,
the passes agree, nothing escalates. Running them on DIFFERENT models can.

So the question is not "is Luna accurate" but "when Luna is wrong, does the
second model disagree loudly enough to trigger arbitration". That is a recall
measure on a bias detector, and it is what decides whether the split
configuration is worth its price over all-Luna.

  ground truth : the two baked Sonnet passes, used only where they AGREE
                 (where Sonnet contradicts itself there is no truth to score)
  caught       : luna wrong AND terra disagrees with luna  -> escalates
  silent       : luna wrong AND terra agrees with luna     -> ships wrong
"""
import json, re, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/llm-extract"))
from validator import validate_metadata  # noqa: E402

BAKE = REPO / "data/bake-off-output"
REPLAY = REPO / "data/swatantra-papers/kie-replay"
WORKS = REPO / "data/swatantra-papers/split-trial-works.json"
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


def load(slug, job, tag):
    p = REPLAY / f"{slug}.{job}.{tag}.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text(encoding="utf-8"))
    if r.get("failed"):
        return None
    pj = parse(r.get("raw_text"))
    return validate_metadata(pj) if pj else None


def main():
    slugs = [Path(f).stem for f in json.loads(WORKS.read_text(encoding="utf-8"))]
    caught = Counter(); silent = Counter(); correct = Counter(); scored = Counter()
    esc_split = esc_sonnet = 0
    n = 0
    detail = []

    for slug in slugs:
        pa, pb = BAKE / slug / "metadata.a.a.json", BAKE / slug / "metadata.b.b.json"
        if not (pa.exists() and pb.exists()):
            continue
        L = load(slug, "metadata.a", "gpt-5-6-luna-add")
        T = load(slug, "metadata.b", "gpt-5-6-terra-add")
        if not L or not T:
            continue
        A = six(json.loads(pa.read_text(encoding="utf-8")))
        B = six(json.loads(pb.read_text(encoding="utf-8")))
        Ls, Ts = six(L), six(T)
        n += 1
        esc_split += any(norm(Ls[k]) != norm(Ts[k]) for k in F)
        esc_sonnet += any(norm(A[k]) != norm(B[k]) for k in F)

        for k in F:
            if norm(A[k]) != norm(B[k]):
                continue                     # no ground truth on this field
            scored[k] += 1
            truth = A[k]
            luna_ok = norm(Ls[k]) == norm(truth)
            if luna_ok:
                correct[k] += 1
            elif norm(Ts[k]) != norm(Ls[k]):
                caught[k] += 1
                detail.append((slug, k, truth, Ls[k], Ts[k], "CAUGHT"))
            else:
                silent[k] += 1
                detail.append((slug, k, truth, Ls[k], Ts[k], "SILENT"))

    if not n:
        return print("no complete split records yet")

    print(f"works with all three passes: {n}\n")
    print(f"{'field':22}{'scoreable':>10}{'luna ok':>9}{'caught':>8}{'SILENT':>8}")
    tc = ts = tk = 0
    for k in F:
        print(f"{k:22}{scored[k]:>10}{correct[k]:>9}{caught[k]:>8}{silent[k]:>8}")
        tc += correct[k]; tk += caught[k]; ts += silent[k]
    tot = tc + tk + ts
    print(f"{'TOTAL':22}{tot:>10}{tc:>9}{tk:>8}{ts:>8}")
    if tk + ts:
        print(f"\nbias-detector recall: {tk}/{tk+ts} = {tk/(tk+ts)*100:.0f}% "
              f"of Luna's errors escalate instead of shipping")
    print(f"field-level accuracy shipped without arbitration: "
          f"{(tc)/tot*100:.1f}%  (silent error rate {ts/tot*100:.2f}%)")
    print(f"\nescalation rate  split(luna/terra): {esc_split}/{n} "
          f"({esc_split/n*100:.0f}%)   sonnet(a/b): {esc_sonnet}/{n} "
          f"({esc_sonnet/n*100:.0f}%)")
    print("  -> tiebreak calls needed is the driver of the real bill")

    print("\n--- every Luna error, and whether the split caught it ---")
    for slug, k, truth, l, t, verdict in detail:
        print(f"  [{verdict}] {slug[:44]:44} {k}")
        print(f"      sonnet={truth!r}  luna={l!r}  terra={t!r}")


if __name__ == "__main__":
    main()
