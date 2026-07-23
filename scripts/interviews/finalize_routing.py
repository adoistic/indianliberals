#!/usr/bin/env python3
"""Apply hand-reviewed editorial decisions on top of the classifier draft and
write the final data/interview-transcripts/routing.final.json.

Decisions (Adnan review, 2026-07-23):
- Drop content-duplicates that ID-dedup missed (same talk re-uploaded / already
  on site under a different YouTube URL).
- Promote multi-sitting subjects to oral-history figures; single one-offs stay
  as talks. Masani/Zareer conversations that name Minoo Masani → oral figure.
- Attach thinker slugs where a profile exists; otherwise carry speaker_name.
"""
import json
import os

ROOT = os.getcwd()
DRAFT = os.path.join(ROOT, "data/interview-transcripts/routing.json")
OUT = os.path.join(ROOT, "data/interview-transcripts/routing.final.json")

# Same content already present (drop entirely).
SKIP = {
    "yg4wKOrHEFg": "duplicate upload of DEM00CG7EeY (3rd IL Annual Lecture, Gurcharan Das)",
    "6WqXWM28bII": "already on site: d-r-pendse-on-think-tanks-and-the-power-of-ideas",
    "Pv-J6tiIDQs": "already on site: sunil-bhandare-on-private-enterprise-post-1991-reforms",
}

# Per-id overrides: group/work_type/speaker_name/thinker corrections.
OVERRIDES = {
    # Jagdish Bhagwati — all three are him; the "discussing his book" one didn't
    # match the "X on Y" pattern. Group as oral figure.
    "X9kOaBxFlxM": {"group": "oral", "speaker": "Jagdish Bhagwati", "thinker": "jagdish-bhagwati"},
    "F3m_kH6CM0I": {"thinker": "jagdish-bhagwati"},
    "Zokl5XHy-NI": {"thinker": "jagdish-bhagwati"},
    # Deepak Lal — six-part oral history, no thinker profile → speaker_name only.
    "HanUaEZDh1g": {"group": "oral", "speaker": "Deepak Lal"},
    "VbXX0sdTqEk": {"group": "oral", "speaker": "Deepak Lal"},
    "hAexZJvm8Jk": {"group": "oral", "speaker": "Deepak Lal"},
    "bpEgEIBlkUI": {"group": "oral", "speaker": "Deepak Lal"},
    "keShsYqNXGc": {"group": "oral", "speaker": "Deepak Lal"},
    "bbij8FY0ILw": {"group": "oral", "speaker": "Deepak Lal"},
    # Minoo Masani conversation that names him → oral figure (matches how the
    # existing Masani/Zareer conversations are grouped).
    "oUEbGZE8ABE": {"group": "oral", "speaker": "Minoo Masani", "thinker": "minoo-masani"},
    # Single one-offs → talks (a one-video "figure" shelf reads oddly).
    "WINVXoHVl_4": {"group": "talks", "speaker": None, "thinker": None},   # Subodh Shenoy
    "0jk86OCfXmY": {"group": "talks", "speaker": None, "thinker": None},   # Shekhar Gupta
    # Sharad Joshi oral (thinker exists).
    "EZiIUdsLSb8": {"group": "oral", "speaker": "Sharad Joshi", "thinker": "sharad-joshi"},
    # Lecture speaker → thinker where a profile exists.
    "XFRUZ3L82v8": {"thinker": "d-subbarao"},          # Duvvuri Subbarao
    "vWyLdJoqDrs": {"thinker": "jayaprakash-narayan"}, # JP Narayan
}


def main():
    rows = json.load(open(DRAFT))
    final = []
    for r in rows:
        vid = r["id"]
        if vid in SKIP:
            r["skip"] = SKIP[vid]
            final.append(r)
            continue
        ov = OVERRIDES.get(vid, {})
        for k, v in ov.items():
            r[k] = v
        r["skip"] = None
        # Regenerate slug for oral overrides whose group changed to keep the
        # descriptive title slug (classifier already set a title slug).
        final.append(r)
    json.dump(final, open(OUT, "w"), indent=2, ensure_ascii=False)

    kept = [r for r in final if not r["skip"]]
    print(f"{len(kept)} to ingest, {len(final)-len(kept)} skipped -> {OUT}\n")
    from collections import Counter
    c = Counter()
    for r in kept:
        key = ("lecture:" + r["series"]) if r["work_type"] == "lecture" else ("interview:" + (r["group"] or "?"))
        c[key] += 1
    for k, n in sorted(c.items()):
        print(f"  {k}: {n}")
    print("\nFigures (oral, by speaker):")
    figs = Counter(r["speaker"] for r in kept if r["group"] == "oral" and r["speaker"])
    for name, n in figs.most_common():
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()
