#!/usr/bin/env python3
"""Classify the works whose form no pattern could name, by asking a model.

summary_worktype.py resolves a work when its summary opens by naming the form.
231 works do not: they open "This untitled, undated draft argues ...", "These
typewritten notes record a meeting ...", "In the rendered pages, the
petitioners challenge ...". A person reads those instantly. The regexes cannot,
and the honest answer is not that the documents resist classification -- it is
that pattern matching was the wrong instrument for the last mile.

Text only, no page images: the summary already describes the document, and this
costs a fraction of the extraction pass.

    python3 scripts/swatantra/classify-worktype.py --validate   # measure first
    python3 scripts/swatantra/classify-worktype.py --apply

Writes data/swatantra-papers/worktype-llm.json  (slug -> {work_type, why}).
"""
import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.request
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTENT = REPO / "apps/site/src/content/primary-works"
INVENTORY = REPO / "data/swatantra-papers/inventory.tsv"
OUT = REPO / "data/swatantra-papers/worktype-llm.json"
ENDPOINT = "https://api.kie.ai/codex/v1/responses"
MODEL = "gpt-5-6-luna"

VOCAB = [
    "letter", "telegram", "correspondence", "circular", "notice", "minutes",
    "resolution", "press_note", "press_clipping", "report", "office_record",
    "roster", "programme", "constitution", "agreement", "legal_filing",
    "financial_record", "form", "essay", "speech", "lecture", "interview",
    "pamphlet", "book", "edited_volume", "periodical_issue", "reference",
    "occasional_paper",
]

SYSTEM = """You are cataloguing an Indian political party's office archive.

You will be given a description of one document, written by someone who read
it. Decide which single term best names the document's FORM -- what kind of
object it is -- not what it is about.

Reply with JSON only: {"work_type": "<term>", "why": "<up to 12 words>"}

Allowed terms, and what each means:

  letter            a letter from one person to another
  telegram          a telegram or cable
  correspondence    a bundle or exchange of letters, not a single letter
  circular          a notice sent to members or units of the party
  notice            a posted or public announcement
  minutes           the record of a meeting, including draft minutes and
                    transcripts of committee proceedings
  resolution        a resolution as adopted, issued as its own document
  press_note        a statement issued by the party TO the press
  press_clipping    a cutting FROM a newspaper or magazine
  report            a report, synopsis, or survey
  office_record     an internal working paper: notes, talking points,
                    checklists, itineraries, drafts of administrative matter
  roster            a list, register or directory of people or units
  programme         an event programme, invitation, agenda or timetable
  constitution      a constitution, rules or bye-laws
  agreement         an agreement or arrangement between parties
  legal_filing      an affidavit, plaint, petition, writ or judgment
  financial_record  a receipt, bill, account or subscription record
  form              a blank form awaiting completion
  essay             an argued piece of writing: article, position paper,
                    memorandum arguing a case
  speech            a speech or address
  lecture           a named or formal lecture
  interview         an interview
  pamphlet          a pamphlet, manifesto or booklet meant for distribution
  book              a book
  edited_volume     a collection with an editor
  periodical_issue  one issue of a magazine or newsletter
  reference         a bibliography, catalogue, or a reproduced standing text
  occasional_paper  use ONLY if genuinely none of the above fits

Prefer a specific term over occasional_paper. Judge the form, not the subject:
a letter that discusses a resolution is a letter."""


def slugify(name):
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()


def api_key():
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("KIE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("KIE_API_KEY not in .env")


def ask(summary, key, attempts=4):
    body = json.dumps({
        "model": MODEL, "stream": False, "instructions": SYSTEM,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": summary[:2500]}]}],
        "reasoning": {"effort": "low"},
    }).encode()
    for a in range(attempts):
        if a:
            time.sleep(min(4 * 2 ** a, 60))
        try:
            req = urllib.request.Request(
                ENDPOINT, data=body,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                payload = json.loads(r.read())
            text = ""
            for item in payload.get("output", []):
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        text += c.get("text", "")
            t = text.strip()
            if t.startswith("```"):
                t = re.sub(r"^```(?:json)?\s*", "", t)
                t = re.sub(r"\s*```$", "", t)
            i, j = t.find("{"), t.rfind("}")
            d = json.loads(t[i:j + 1]) if i >= 0 else None
            if d and d.get("work_type") in VOCAB:
                return d
        except Exception:                                     # noqa: BLE001
            pass
    return None


def summaries():
    inv = {slugify(r["file"]) for r in csv.DictReader(
        open(INVENTORY, encoding="utf-8"), delimiter="\t")}
    out = {}
    for p in CONTENT.glob("*.md"):
        if p.stem not in inv:
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        w = re.search(r"^work_type:\s*(\S+)", t, re.M)
        b = re.search(r"^## Summary\n\n(.+?)\n\n", t, re.S | re.M)
        if w and b:
            out[p.stem] = (w.group(1), " ".join(b.group(1).split()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true",
                    help="score against works the model already typed")
    ap.add_argument("--sample", type=int, default=150)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    key = api_key()
    data = summaries()

    if a.validate:
        typed = [(s, wt, sm) for s, (wt, sm) in data.items()
                 if wt not in ("occasional_paper", "periodical_issue")]
        random.seed(11)
        pick = random.sample(typed, min(a.sample, len(typed)))
        agree = 0
        rows = []
        with ThreadPoolExecutor(max_workers=a.jobs) as ex:
            futs = {ex.submit(ask, sm, key): (s, wt) for s, wt, sm in pick}
            for f in as_completed(futs):
                s, wt = futs[f]
                d = f.result()
                got = (d or {}).get("work_type")
                agree += got == wt
                rows.append((wt, got))
        print(f"validation on {len(pick)} already-typed works")
        print(f"  agreement: {agree}/{len(pick)} = {agree/len(pick)*100:.1f}%")
        from collections import Counter
        c = Counter((w, g) for w, g in rows if w != g)
        print("  top disagreements (model -> llm):")
        for (w, g), n in c.most_common(8):
            print(f"    {n:3}  {w} -> {g}")
        return 0

    todo = {s: sm for s, (wt, sm) in data.items() if wt == "occasional_paper"}
    print(f"classifying {len(todo)} unresolved works")
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = {s: sm for s, sm in todo.items() if s not in res}
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(ask, sm, key): s for s, sm in todo.items()}
        for i, f in enumerate(as_completed(futs), 1):
            s = futs[f]
            d = f.result()
            if d:
                res[s] = d
            if i % 25 == 0:
                print(f"  {i}/{len(todo)}  resolved={len(res)}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    c = Counter(v["work_type"] for v in res.values())
    print(f"\nwrote {OUT.relative_to(REPO)}  ({len(res)} classified)")
    for k, v in c.most_common():
        print(f"  {v:4}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
