#!/usr/bin/env python3
"""Assemble final primary-works markdown for each new video from:
  - routing.final.json  (work_type, group/series, speaker, thinker, slug)
  - meta/<vid>.json     (YouTube title/description/upload_date/webpage_url)
  - transcripts/<vid>.raw.txt   (diarized transcript body)
  - transcripts/<vid>.lang      (detected language)
  - metadata/<vid>.json (LLM: description, summary, key_points, themes,
                          related_thinkers, thinker_mentions)  [optional]

Every thinker reference (authors, related_thinkers, thinker_mentions.thinker) is
validated against the real thinker slug set; unknown slugs are dropped or
downgraded to thinker_unresolved so `astro check` / build never breaks on a
dangling reference.

Writes apps/site/src/content/primary-works/<slug>.md. Idempotent: overwrites.
"""
import json
import os
import re
import sys

ROOT = os.getcwd()
DTX = os.path.join(ROOT, "data/interview-transcripts")
ROUTING = os.path.join(DTX, "routing.final.json")
META = os.path.join(DTX, "meta")
MDDIR = os.path.join(DTX, "metadata")
TRANS = os.path.join(ROOT, "data/transcripts")
OUTDIR = os.path.join(ROOT, "apps/site/src/content/primary-works")
THINKERS = set(x.strip() for x in open("/tmp/thinker_ids.txt") if x.strip())


def yaml_str(s: str) -> str:
    s = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def block_scalar(key: str, text: str, indent: int = 0) -> str:
    pad = " " * indent
    lines = [f"{pad}{key}: |-"]
    for ln in text.rstrip().split("\n"):
        lines.append(f"{pad}  {ln}" if ln else "")
    return "\n".join(lines)


def clean_slug(vid_slug: str, used: set) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", vid_slug.lower()).strip("-")[:90]
    base = slug
    n = 2
    while slug in used or os.path.exists(os.path.join(OUTDIR, f"{slug}.md")):
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def validate_mentions(mentions):
    out = []
    for m in mentions or []:
        rec = {"role": m.get("role", "mention"), "reasoning": (m.get("reasoning") or "").strip()}
        if not rec["reasoning"]:
            continue
        slug = m.get("thinker")
        if slug and slug in THINKERS:
            rec["thinker"] = slug
        else:
            name = m.get("thinker_unresolved") or m.get("name") or slug
            if not name:
                continue
            rec["thinker_unresolved"] = str(name)
        ev = [e for e in (m.get("evidence") or []) if e.get("quote")]
        kp = [e for e in (m.get("key_passages") or []) if e.get("quote") and e.get("what_it_shows")]
        if ev:
            rec["evidence"] = ev
        if kp:
            rec["key_passages"] = kp
        out.append(rec)
    return out


def frontmatter(row, meta, llm, lang, body_present):
    slug = row["_slug"]
    fm = []
    fm.append(f"id: {slug}")
    fm.append("title:")
    fm.append(f"  main: {yaml_str(row['title'])}")
    fm.append(f"work_type: {row['work_type']}")

    thinker = row.get("thinker")
    author_ref = thinker if thinker in THINKERS else None
    fm.append("authors:" + ("" if author_ref else " []"))
    if author_ref:
        fm.append(f"- {author_ref}")
    fm.append("editors: []")
    fm.append("contributors: []")

    year = row.get("year") or (meta.get("upload_date") or "")[:4]
    fm.append("publication:")
    fm.append(f"  language: {lang}")
    if str(year).isdigit():
        fm.append(f"  year: {int(year)}")

    # Explicit routing fields (interviews only; lectures group by id prefix).
    if row["work_type"] == "interview" and row.get("group"):
        fm.append(f"video_group: {row['group']}")
    speaker = row.get("speaker")
    if speaker and not author_ref:
        fm.append(f"speaker_name: {yaml_str(speaker)}")

    themes = [t for t in (llm.get("themes") or []) if isinstance(t, str)]
    fm.append("themes:" + ("" if themes else " []"))
    for t in themes:
        fm.append(f"- {re.sub(r'[^a-z0-9-]+','-', t.lower()).strip('-')}")

    needs_review = row.get("_needs_review", False)
    fm.append(f"needs_review: {'true' if needs_review else 'false'}")
    fm.append("draft: false")
    fm.append(f"transcript_status: {row.get('_transcript_status','complete')}")
    if meta.get("webpage_url"):
        fm.append(f"youtube_url: {meta['webpage_url']}")

    desc = (llm.get("description") or meta.get("description") or "").strip()
    if desc:
        desc = " ".join(desc.split())[:600]
        fm.append(f"description: {yaml_str(desc)}")

    fm.append("provenance:")
    fm.append("  source: ccs_archive")
    fm.append("  scan_quality: unknown")

    summary = (llm.get("summary") or "").strip()
    if summary:
        fm.append(block_scalar("summary", summary))
    kps = [k for k in (llm.get("key_points") or []) if isinstance(k, str) and k.strip()]
    fm.append("key_points:" + ("" if kps else " []"))
    for k in kps:
        fm.append(f"- {yaml_str(k.strip())}")

    related = [s for s in (llm.get("related_thinkers") or []) if s in THINKERS]
    if author_ref and author_ref not in related:
        related.insert(0, author_ref)
    # dedupe, keep order
    seen, rel2 = set(), []
    for s in related:
        if s not in seen:
            seen.add(s); rel2.append(s)
    fm.append("related_thinkers:" + ("" if rel2 else " []"))
    for s in rel2:
        fm.append(f"- {s}")

    mentions = validate_mentions(llm.get("thinker_mentions"))
    if mentions:
        fm.append("thinker_mentions:")
        for m in mentions:
            fm.append(f"- role: {m['role']}")
            if "thinker" in m:
                fm.append(f"  thinker: {m['thinker']}")
            else:
                fm.append(f"  thinker_unresolved: {yaml_str(m['thinker_unresolved'])}")
            fm.append(f"  reasoning: {yaml_str(m['reasoning'])}")
            if m.get("evidence"):
                fm.append("  evidence:")
                for e in m["evidence"]:
                    fm.append(f"  - quote: {yaml_str(e['quote'])}")
                    if e.get("context"):
                        fm.append(f"    context: {yaml_str(e['context'])}")
            if m.get("key_passages"):
                fm.append("  key_passages:")
                for e in m["key_passages"]:
                    fm.append(f"  - quote: {yaml_str(e['quote'])}")
                    fm.append(f"    what_it_shows: {yaml_str(e['what_it_shows'])}")
    else:
        fm.append("thinker_mentions: []")

    return "\n".join(fm)


def main():
    rows = json.load(open(ROUTING))
    kept = [r for r in rows if not r.get("skip")]
    used = set()
    written, missing_tx = 0, []
    for r in kept:
        vid = r["id"]
        tx = os.path.join(TRANS, f"{vid}.raw.txt")
        if not os.path.exists(tx):
            missing_tx.append(vid)
            continue
        meta = json.load(open(os.path.join(META, f"{vid}.json"))) if os.path.exists(os.path.join(META, f"{vid}.json")) else {}
        mdpath = os.path.join(MDDIR, f"{vid}.json")
        llm = json.load(open(mdpath)) if os.path.exists(mdpath) else {}
        lang = "en"
        lp = os.path.join(TRANS, f"{vid}.lang")
        if os.path.exists(lp):
            lang = open(lp).read().strip() or "en"

        r["_slug"] = clean_slug(r["slug"], used)
        # Non-English or flagged transcripts get review + partial status.
        body = open(tx).read()
        # crude repetition-loop detector: a paragraph with <15% unique tokens
        loop = False
        for para in re.split(r"\n\*\*Speaker", body):
            toks = re.findall(r"\S+", para)
            if len(toks) > 40 and len(set(toks)) / len(toks) < 0.15:
                loop = True
                break
        r["_needs_review"] = (lang != "en") or loop or not llm
        r["_transcript_status"] = "partial" if loop else "complete"

        fm = frontmatter(r, meta, llm, lang, True)
        # Body: transcript already carries "# title / Source / Duration / paras".
        out = f"---\n{fm}\n---\n\n{body.strip()}\n"
        open(os.path.join(OUTDIR, f"{r['_slug']}.md"), "w").write(out)
        written += 1
        tag = "LLM" if llm else "no-LLM"
        print(f"  wrote {r['_slug']}.md  ({r['work_type']}, lang={lang}, {tag})")
    print(f"\nwrote {written}; missing transcript: {len(missing_tx)} {missing_tx}")


if __name__ == "__main__":
    main()
