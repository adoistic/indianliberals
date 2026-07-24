#!/usr/bin/env python3
"""Propose editorial routing for each new video: work_type, series/group, a
url-safe slug/id, the speaker, and (if matched) their thinker slug.

Reads the manifest + per-video metadata + the thinker id list; writes a
reviewable data/interview-transcripts/routing.json. Heuristic only — meant to
be eyeballed and hand-corrected before files are written.
"""
import json
import os
import re

ROOT = os.getcwd()
MANIFEST = os.path.join(ROOT, "data/interview-transcripts/manifest.json")
META = os.path.join(ROOT, "data/interview-transcripts/meta")
THINKER_IDS = "/tmp/thinker_ids.txt"
OUT = os.path.join(ROOT, "data/interview-transcripts/routing.json")

thinker_ids = set(x.strip() for x in open(THINKER_IDS) if x.strip())


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"['’]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"^-+|-+$", "", s)[:90]


def match_thinker(name: str):
    """Return a thinker slug if the person clearly matches one."""
    s = slugify(name)
    if s in thinker_ids:
        return s
    # try last-name / common variants
    toks = [t for t in s.split("-") if t not in ("dr", "prof", "professor", "mr", "ms", "shri")]
    cand = "-".join(toks)
    if cand in thinker_ids:
        return cand
    # substring against known ids (surname match)
    for tid in thinker_ids:
        if cand and (cand == tid or (len(toks) >= 2 and toks[-1] == tid.split("-")[-1] and toks[0] == tid.split("-")[0])):
            return tid
    return None


ORDINAL = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7}


def year_from(meta):
    ud = (meta.get("upload_date") or "")[:4]
    return int(ud) if ud.isdigit() else None


def route(v, meta):
    title = meta.get("title") or v["title"]
    pls = v["playlists"]
    y = year_from(meta)
    r = {
        "id": v["id"],
        "title": title,
        "playlists": pls,
        "year": y,
        "work_type": "interview",
        "group": None,       # oral | talks | explainers | conversations (interviews)
        "series": None,      # lecture series slug (lectures)
        "speaker": None,
        "thinker": None,
        "slug": None,
    }

    # ── Lectures ────────────────────────────────────────────────────────────
    if "shenoy-memorial" in pls:
        r["work_type"] = "lecture"
        r["series"] = "br-shenoy-memorial-lecture"
        ym = re.search(r"(20\d\d)", title)
        yr = int(ym.group(1)) if ym else y
        r["year"] = yr
        sm = re.search(r"\|\|?\s*(?:Dr\.?|Professor|Prof\.?)?\s*([A-Z][A-Za-z.\s]+?)(?:\s*#|$)", title)
        sp = sm.group(1).strip() if sm else None
        r["speaker"] = sp
        r["thinker"] = match_thinker(sp) if sp else None
        r["slug"] = f"br-shenoy-memorial-lecture-{yr}-{slugify(sp) if sp else v['id']}"
        return r
    if "il-annual-lecture" in pls:
        r["work_type"] = "lecture"
        r["series"] = "indian-liberals-annual-lecture"
        om = re.search(r"(\d(?:st|nd|rd|th))", title)
        n = ORDINAL.get(om.group(1).lower(), None) if om else None
        sm = re.search(r"by\s+(?:Dr\.?|Ms\.?|Mr\.?)?\s*([A-Z][A-Za-z.\s]+)$", title)
        sp = sm.group(1).strip() if sm else None
        r["speaker"] = sp
        r["thinker"] = match_thinker(sp) if sp else None
        base = f"indian-liberals-annual-lecture-{n}" if n else "indian-liberals-annual-lecture"
        r["slug"] = f"{base}-{slugify(sp) if sp else v['id']}"
        return r

    # ── Interviews ──────────────────────────────────────────────────────────
    # "X on Y" oral-history pattern
    m = re.match(r"^([A-Z][A-Za-z.\s]+?)\s+on\s+(.+)$", title)
    conv = re.search(r"in conversation with", title, re.I)
    women = re.search(r"women liberals|indian women liberals", title, re.I)
    profile = re.search(
        r"rukhmabai|tarabai shinde|iqbalunnisa|babytai kamble|unwavering|resolute|stalwart",
        title, re.I,
    )
    if profile or women:
        r["group"] = "explainers"
        r["slug"] = slugify(title)
    elif conv:
        r["group"] = "conversations"
        r["slug"] = slugify(title)
    elif m:
        sp = m.group(1).strip()
        r["group"] = "oral"
        r["speaker"] = sp
        r["thinker"] = match_thinker(sp)
        r["slug"] = slugify(title)
    else:
        r["group"] = "talks"
        r["slug"] = slugify(title)
    return r


def main():
    manifest = json.load(open(MANIFEST))
    rows = []
    for v in manifest:
        if v.get("unavailable"):
            continue
        mpath = os.path.join(META, f"{v['id']}.json")
        meta = json.load(open(mpath)) if os.path.exists(mpath) else {}
        rows.append(route(v, meta))
    json.dump(rows, open(OUT, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {len(rows)} routing rows -> {OUT}\n")
    for r in rows:
        wt = r["work_type"]
        grp = r["series"] or r["group"]
        th = f" -> {r['thinker']}" if r["thinker"] else (f" (speaker={r['speaker']}, UNMATCHED)" if r["speaker"] else "")
        print(f"  [{wt:9}/{grp or '-':10}] {r['id']}  {r['title'][:55]}{th}")


if __name__ == "__main__":
    main()
