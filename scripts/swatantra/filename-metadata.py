#!/usr/bin/env python3
"""Derive metadata from Swatantra papers filenames, deterministically.

The archive's filenames encode real cataloguing: `<archive_id>-<Title>_<DD-MM-YYYY>.pdf`,
and for correspondence `Letter_to_<Person>` / `Letter_from_<Person>`. That is a
free, high-precision signal the extraction pipeline never sees, because
`byline-sweep` reads page 1 as an image.

This produces two outputs:

  data/swatantra-papers/filename-metadata.tsv
      One row per PDF: parsed date, direction, correspondent verbatim, the
      resolved thinker_id where the existing authority already covers it, and a
      genre guess.

  data/swatantra-papers/authority-candidates.tsv
      Unresolved correspondent strings, frequency-sorted, each with its closest
      existing authority entry and a similarity score. This is an editorial
      queue in the sense of `recommended_authority_additions[]` — it proposes,
      it does not write to the authority file.

Intended use is CROSS-CHECK, not replacement. `year` here should corroborate or
contradict the model's extracted year, not pre-empt it; disagreements are the
interesting output. Nothing here writes to the corpus or to authority files.

Usage:
    python3 scripts/swatantra/filename-metadata.py <corpus-dir> [out-dir]
"""
import csv
import difflib
import json
import os
import re
import sys
import unicodedata
from collections import Counter

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
AUTHORITY = os.path.join(REPO, "data", "authority", "thinkers.json")

# Plausibility window for a Swatantra-era date parsed out of a filename.
# The party was founded 1959; the papers run either side of that.
YEAR_MIN, YEAR_MAX = 1900, 2020

HONORIFICS = r"^(Mr|Mrs|Miss|Ms|Dr|Shri|Sri|Smt|Prof|Col|Maj|Capt|Sardar|Raja|Rajkumar|Seth|Pandit|Swami)\s+"

# Not people, however much they look like a name after `_to_`.
NON_PERSON = re.compile(
    r"^(the\s+)?(regional transport officer|editor|secretary|president|chairman|"
    r"registrar|collector|commissioner|manager|director|treasurer|principal|"
    r"press|all members|members|swatantra party|the times|the hindu|govt|government)",
    re.I,
)

MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

GENRES = [
    ("letter", r"letter"),
    ("telegram", r"telegram"),
    ("minutes", r"minutes"),
    ("circular", r"circular|notice"),
    ("resolution", r"resolution"),
    ("report", r"report"),
    ("manifesto", r"manifesto|principles|programme"),
    ("press_note", r"press|statement"),
    ("souvenir", r"souvenir|convention"),
    ("memo", r"memo"),
    ("speech", r"speech|address|lecture|talk"),
    ("agenda", r"agenda"),
    ("bulletin", r"bulletin|newsletter"),
]

# Genre -> work_type from the content.config.ts enum, which was extended on
# 2026-08-17 with the archival office-record types this corpus needs.
# This is a HINT for cross-checking the model, not an authority: a filename
# saying "Notice" cannot tell you whether the document is the notice or the
# minutes. `None` means "no enum value fits; do not guess".
WORK_TYPE = {
    "letter": "letter", "telegram": "telegram", "minutes": "minutes",
    "circular": "circular", "resolution": "resolution",
    "report": "occasional_paper", "manifesto": "occasional_paper",
    "press_note": "press_note", "souvenir": "edited_volume",
    "memo": "circular", "speech": "speech", "agenda": "circular",
    "bulletin": "periodical_issue",
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", s.lower())).strip()


def load_authority():
    """Return (match_keys -> thinker_id, id -> display name)."""
    data = json.load(open(AUTHORITY, encoding="utf-8"))
    keys, display = {}, {}
    for raw, tid in data.get("byline_lookup", {}).items():
        keys.setdefault(norm(raw), tid)
        display.setdefault(tid, raw)
    for t in data.get("thinkers", []):
        tid = t.get("id")
        if not tid:
            continue
        for field in ("canonical", "name", "canonical_name"):
            if t.get(field):
                keys.setdefault(norm(t[field]), tid)
                display.setdefault(tid, t[field])
        for alias in (t.get("also_known_as") or []) + (t.get("aliases") or []):
            if isinstance(alias, str):
                keys.setdefault(norm(alias), tid)
    return keys, display


def parse_date(stem):
    """Return (iso_date, year, flag). Flag is set when the date is implausible."""
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", stem)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (YEAR_MIN <= y <= YEAR_MAX):
            return "", y, "year_out_of_range"
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return "", y, "bad_day_month"
        return f"{y:04d}-{mo:02d}-{d:02d}", y, ""
    m = re.search(r"([A-Za-z]{3,9})[-_](\d{4})$", stem)
    if m and m.group(1)[:3].lower() in MONTHS:
        y = int(m.group(2))
        if not (YEAR_MIN <= y <= YEAR_MAX):
            return "", y, "year_out_of_range"
        return f"{y:04d}-{MONTHS[m.group(1)[:3].lower()]:02d}", y, ""
    m = re.search(r"[-_](\d{4})$", stem)
    if m:
        y = int(m.group(1))
        if YEAR_MIN <= y <= YEAR_MAX:
            return f"{y:04d}", y, ""
        return "", y, "year_out_of_range"
    return "", None, ""


# `_to_` / `_from_` only means correspondence when a correspondence noun
# precedes it. Without this guard, "Notice_of_Amendments_to_Bills" yields a
# correspondent named "Bills", and "Where_do_we_go_from_here-The_Onlooker"
# yields "here-The Onlooker".
CORRESPONDENCE = re.compile(
    r"(?:letter|telegram|telegramme|cable|wire|note|memo|message|reply|"
    r"postcard|card|correspondence)[a-z]*_(to|from)_(.+?)"
    r"(?:_\d{2}-\d{2}-\d{4})?$", re.I)


def parse_correspondent(stem):
    """Return (direction, verbatim name) or ('', '')."""
    m = CORRESPONDENCE.search(stem)
    if not m:
        return "", ""
    name = re.sub(HONORIFICS, "", m.group(2).replace("_", " "), flags=re.I).strip()
    name = re.sub(r"\s+\d{2}-\d{2}-\d{4}$", "", name).strip()
    return m.group(1).lower(), name


def alias_verdict(who, nearest_key, score):
    """Triage a fuzzy match. Conservative: initials and surnames must agree.

    Pure edit distance produces dangerous matches in a political archive —
    "Mohan Singh"/"Manmohan Singh" scores 0.88, "India"/"Indira Gandhi" 0.91.
    Both are different people. Requiring the surname to be close AND the
    leading token to be close kills those without losing genuine misspellings
    like "Dandeker"/"Dandekar".
    """
    a, b = norm(who).split(), nearest_key.split()
    if not a or not b:
        return "no"
    ratio = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio()
    if ratio(a[-1], b[-1]) < 0.85:          # surnames must agree
        return "review"
    if ratio(a[0], b[0]) >= 0.8 or score >= 0.93:
        return "yes"
    return "review"


def genre_of(stem):
    for label, pattern in GENRES:
        if re.search(pattern, stem, re.I):
            return label
    return ""


def main(corpus_dir, out_dir):
    keys, display = load_authority()
    files = sorted(f for f in os.listdir(corpus_dir) if f.lower().endswith(".pdf"))
    os.makedirs(out_dir, exist_ok=True)

    rows, unresolved = [], Counter()
    for name in files:
        stem = name[:-4]
        aid = (re.match(r"(\d+[A-Za-z]?)", stem) or [""])[0]
        iso, year, flag = parse_date(stem)
        direction, who = parse_correspondent(stem)
        tid, status = "", ""
        if who:
            if NON_PERSON.match(who):
                status = "not_a_person"
            elif norm(who) in keys:
                tid, status = keys[norm(who)], "resolved"
            else:
                status = "unresolved"
                unresolved[who] += 1
        genre = genre_of(stem)
        rows.append({
            "file": name, "archive_id": aid, "date": iso, "year": year or "",
            "date_flag": flag, "direction": direction, "correspondent_verbatim": who,
            "thinker_id": tid, "resolution": status, "genre": genre,
            "work_type_suggest": WORK_TYPE.get(genre) or "",
        })

    cols = ["file", "archive_id", "date", "year", "date_flag", "direction",
            "correspondent_verbatim", "thinker_id", "resolution", "genre",
            "work_type_suggest"]
    meta_path = os.path.join(out_dir, "filename-metadata.tsv")
    with open(meta_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # Editorial queue: unresolved names + nearest existing authority entry.
    known = list(keys)
    cand_path = os.path.join(out_dir, "authority-candidates.tsv")
    with open(cand_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["correspondent_verbatim", "files", "nearest_authority_id",
                    "nearest_authority_name", "similarity", "likely_alias_of_existing"])
        for who, n in unresolved.most_common():
            close = difflib.get_close_matches(norm(who), known, n=1, cutoff=0.6)
            if close:
                tid = keys[close[0]]
                score = difflib.SequenceMatcher(None, norm(who), close[0]).ratio()
                w.writerow([who, n, tid, display.get(tid, ""), f"{score:.2f}",
                            alias_verdict(who, close[0], score)])
            else:
                w.writerow([who, n, "", "", "0.00", "no"])

    # Report
    named = [r for r in rows if r["correspondent_verbatim"]]
    res = sum(1 for r in rows if r["resolution"] == "resolved")
    dated = sum(1 for r in rows if r["date"])
    flagged = sum(1 for r in rows if r["date_flag"])
    no_wt = sum(1 for r in rows if r["genre"] and not r["work_type_suggest"])
    print(f"files                       : {len(rows)}")
    print(f"  with a valid parsed date  : {dated} ({dated/len(rows)*100:.1f}%)")
    print(f"  date rejected as implausible: {flagged}")
    print(f"  naming a correspondent    : {len(named)}")
    print(f"    resolved to a thinker_id: {res} ({res/max(1,len(named))*100:.1f}%)")
    print(f"    flagged not-a-person    : {sum(1 for r in rows if r['resolution']=='not_a_person')}")
    print(f"    unresolved (distinct)   : {len(unresolved)}")
    print(f"  genre with no work_type   : {no_wt}")
    likely = sum(1 for line in open(cand_path, encoding="utf-8").readlines()[1:]
                 if line.rstrip("\n").endswith("\tyes"))
    print(f"  candidates that look like aliases of existing entries: {likely}")
    print(f"\nwrote {meta_path}\nwrote {cand_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO, "data", "swatantra-papers")
    main(sys.argv[1], out)
