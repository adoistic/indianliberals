#!/usr/bin/env python3
"""Phase B: LLM enrichment of migrated interview MDs.

For each MD under apps/site/src/content/primary-works/ with work_type='interview'
and transcript_status='complete':
  - load the MD's body (cleaned transcript) + frontmatter (title, description,
    authors[0]=subject) + thinker-collection authority list
  - call claude -p with a structured-output prompt
  - parse + validate the JSON
  - merge summary, key_points, themes, thinker_mentions, related_thinkers,
    contributors[] into the MD frontmatter
  - write back; commit in batches of 10

Skips MDs whose transcript_status is 'unavailable' or 'none'.

Run:
    .venv-extract/bin/python3 scripts/synthesis/enrich-interview-mds.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
THINKERS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "thinkers"
LOG = Path("/tmp/interview-enrich-progress.tsv")
FAILS = Path("/tmp/interview-enrich-fails.tsv")
COMMIT_BATCH_SIZE = 10
MAX_TRANSCRIPT_BYTES = 80_000

_FM_BLOCK_RX = re.compile(r"^---\n([\s\S]*?)\n---\n?([\s\S]*)$", re.M)


def build_authority_manifest(thinkers_dir: Path) -> list[dict]:
    """Return [{slug, canonical_name, also_known_as, canon_status}, ...] sorted by slug."""
    out: list[dict] = []
    for md in sorted(thinkers_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FM_BLOCK_RX.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        slug = fm.get("id") or md.stem
        name_block = fm.get("name") or {}
        canonical = (name_block.get("canonical") or "").strip()
        if not canonical:
            continue
        also = name_block.get("also_known_as") or []
        if not isinstance(also, list):
            also = []
        also = [a.strip() for a in also if isinstance(a, str) and a.strip()]
        out.append({
            "slug": slug,
            "canonical_name": canonical,
            "also_known_as": also,
            "canon_status": fm.get("canon_status") or "unknown",
        })
    return out


def validate_and_clamp(payload: dict, *, authority_slugs: set[str]) -> dict:
    """Normalise LLM output: demote unknown slugs to thinker_unresolved, clamp count caps.

    Caps:
      - key_points: <= 7
      - themes: <= 7
      - thinker_mentions: <= 5
      - thinker_mentions[].evidence: <= 5
      - thinker_mentions[].key_passages: <= 5
    """
    out: dict = {
        "summary": payload.get("summary") or "",
        "key_points": list(payload.get("key_points") or [])[:7],
        "themes": list(payload.get("themes") or [])[:7],
        "interviewer_name": payload.get("interviewer_name") or None,
        "interviewer_slug": payload.get("interviewer_slug") or None,
        "thinker_mentions": [],
    }
    raw_mentions = list(payload.get("thinker_mentions") or [])[:5]
    for entry in raw_mentions:
        if not isinstance(entry, dict):
            continue
        mention: dict = {}
        slug = entry.get("thinker")
        display = entry.get("display_name") or ""
        if isinstance(slug, str) and slug in authority_slugs:
            mention["thinker"] = slug
        else:
            unresolved = entry.get("thinker_unresolved") or display or slug or ""
            mention["thinker_unresolved"] = unresolved.strip() if isinstance(unresolved, str) else ""
        mention["role"] = entry.get("role") or "mention"
        mention["reasoning"] = entry.get("reasoning") or ""
        evidence = list(entry.get("evidence") or [])[:5]
        mention["evidence"] = [
            {"quote": e.get("quote", ""), "context": e.get("context", "")}
            for e in evidence if isinstance(e, dict)
        ]
        passages = list(entry.get("key_passages") or [])[:5]
        mention["key_passages"] = [
            {"quote": p.get("quote", ""), "what_it_shows": p.get("what_it_shows", "")}
            for p in passages if isinstance(p, dict)
        ]
        out["thinker_mentions"].append(mention)
    return out


def truncate_transcript(text: str, *, max_bytes: int = MAX_TRANSCRIPT_BYTES) -> str:
    """Truncate the middle of a long transcript; preserve first half and last half."""
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    half = max_bytes // 2
    head = data[:half].decode("utf-8", errors="ignore")
    tail = data[-half:].decode("utf-8", errors="ignore")
    return (
        head
        + "\n\n... (transcript truncated for analysis — full text preserved in MD body) ...\n\n"
        + tail
    )


def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    m = _FM_BLOCK_RX.match(md_text)
    if not m:
        return {}, md_text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), m.group(2)


def lookup_thinker_name(slug: str) -> str | None:
    p = THINKERS_DIR / f"{slug}.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(text)
    return ((fm.get("name") or {}).get("canonical") or "").strip() or None


def compose_prompt(*, title: str, year: int | None, subject_name: str | None,
                    description: str | None, authority: list[dict],
                    transcript: str) -> str:
    """Build the Phase B prompt per spec section 5.3."""
    desc_line = description.strip() if description else "(no editorial description on file)"
    year_line = str(year) if year else "(unknown)"
    subj_line = subject_name if subject_name else "(no resolved subject — use transcript to determine the main speaker)"

    auth_rows = []
    for a in authority:
        aka = ", ".join(a["also_known_as"]) if a["also_known_as"] else ""
        auth_rows.append(f"{a['slug']}\t{a['canonical_name']}\t[{aka}]\t{a['canon_status']}")
    auth_table = "\n".join(auth_rows)

    transcript = truncate_transcript(transcript)

    return f"""You are an analyst preparing structured metadata for an interview transcript that is being filed alongside books, pamphlets, and speeches in the Indian Liberals archive.

# Interview
- Title: {title}
- Year: {year_line}
- Subject (interviewee): {subj_line}
- Editorial description (verbatim, if any):
{desc_line}

# Authority list of thinkers in the archive
(tab-separated: slug | canonical_name | [also_known_as] | canon_status)
{auth_table}

# Cleaned diarized transcript

{transcript}

# Your task

Produce a SINGLE JSON object with these fields (and NOTHING else — no preamble, no code fence):

{{
  "summary": "1-3 paragraph synopsis...",
  "key_points": ["...", "..."],
  "themes": ["lowercase-hyphenated-tag", "..."],
  "interviewer_name": "Resolved canonical name" OR null,
  "interviewer_slug": "slug-from-authority-list" OR null,
  "thinker_mentions": [
    {{
      "display_name": "Person's name as commonly rendered",
      "thinker": "slug-from-authority-list",
      "role": "subject" | "mention",
      "reasoning": "one-sentence explanation",
      "evidence": [{{"quote": "verbatim from transcript", "context": "short"}}],
      "key_passages": [{{"quote": "verbatim", "what_it_shows": "short"}}]
    }}
  ]
}}

Hard rules:
- thinker_mentions[].thinker MUST be a slug from the authority list above. If a person has no plausible match, use {{"display_name": "Their name", "thinker_unresolved": "Their name", ...}} instead. Never invent a slug.
- Always include a display_name field in each mention.
- evidence[].quote and key_passages[].quote MUST be verbatim from the transcript.
- Max 5 mentions, <=5 evidence + <=5 key_passages per mention, <=7 key_points, <=7 themes.
- Output ONLY the JSON object. No preamble, no commentary, no code fence.
"""


def log(msg: str) -> None:
    line = f"{int(time.time())}\t{msg}\n"
    with LOG.open("a") as f:
        f.write(line)
    print(line.rstrip(), flush=True)


def log_fail(slug: str, reason: str) -> None:
    with FAILS.open("a") as f:
        f.write(f"{int(time.time())}\t{slug}\t{reason}\n")


def parse_reset_seconds(text: str) -> float | None:
    m = re.search(r"reset.*?in\s+(\d+(?:\.\d+)?)\s*min", text or "", re.I)
    return (float(m.group(1)) * 60 + 30) if m else None


def call_claude(prompt: str, slug: str, *, max_retries: int = 3) -> dict | None:
    """Call claude -p; parse JSON; handle rate-limit retries."""
    for attempt in range(1, max_retries + 1):
        try:
            r = subprocess.run(
                ["claude", "-p", "--dangerously-skip-permissions"],
                input=prompt, capture_output=True, text=True, timeout=600,
            )
        except subprocess.TimeoutExpired:
            log(f"{slug}\tTIMEOUT_attempt={attempt}")
            continue
        if r.returncode != 0:
            combined = (r.stderr or "") + " " + (r.stdout or "")
            if re.search(r"rate.?limit|out.?of.?extra.?usage|usage.?limit|quota", combined, re.I):
                reset = parse_reset_seconds(combined) or 600
                log(f"{slug}\tRATE_LIMITED_attempt={attempt}_sleep={reset:.0f}s")
                time.sleep(reset)
                continue
            log(f"{slug}\tFAIL_rc={r.returncode}\t{combined[:200]!r}")
            return None
        raw = r.stdout.strip()
        raw = re.sub(r"^```(?:json)?\s*\n", "", raw)
        raw = re.sub(r"\n```\s*$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log(f"{slug}\tJSON_PARSE_FAIL_attempt={attempt}\t{e!s}")
            continue
    return None


def write_back_frontmatter(md_path: Path, new_fields: dict) -> None:
    """Merge new_fields into the MD's frontmatter; preserve body."""
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    fm.update(new_fields)
    related = set()
    for a in fm.get("authors") or []:
        if isinstance(a, str):
            related.add(a)
    for mention in fm.get("thinker_mentions") or []:
        s = mention.get("thinker")
        if isinstance(s, str):
            related.add(s)
    fm["related_thinkers"] = sorted(related)
    fm["needs_review"] = True

    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    md_path.write_text(f"---\n{fm_yaml.rstrip()}\n---\n\n{body.lstrip()}", encoding="utf-8")


def enrich_one(md_path: Path, *, authority: list[dict], authority_slugs: set[str]) -> str:
    """Run Phase B on one MD. Returns one of: 'OK', 'SKIPPED', 'FAILED'."""
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    slug = md_path.stem
    if fm.get("work_type") != "interview":
        return "SKIPPED"
    if fm.get("transcript_status") != "complete":
        return "SKIPPED"
    if fm.get("thinker_mentions"):
        return "SKIPPED"
    title = (fm.get("title") or {}).get("main") or slug
    year = (fm.get("publication") or {}).get("year")
    subject_slug = (fm.get("authors") or [None])[0]
    subject_name = lookup_thinker_name(subject_slug) if isinstance(subject_slug, str) else None
    description = fm.get("description")

    prompt = compose_prompt(
        title=title, year=year, subject_name=subject_name,
        description=description, authority=authority, transcript=body,
    )
    payload = call_claude(prompt, slug)
    if payload is None:
        log_fail(slug, "claude_p_returned_none_or_unparseable")
        return "FAILED"

    cleaned = validate_and_clamp(payload, authority_slugs=authority_slugs)

    contributors = list(fm.get("contributors") or [])
    iv_slug = cleaned["interviewer_slug"]
    iv_name = cleaned["interviewer_name"]
    if isinstance(iv_slug, str) and iv_slug in authority_slugs:
        contributors.append({"role": "interviewer", "thinker": iv_slug})
    elif isinstance(iv_name, str) and iv_name.strip() and iv_name.strip().lower() not in ("interviewer", "host"):
        contributors.append({"role": "interviewer", "thinker_unresolved": iv_name.strip()})

    new_fields = {
        "summary": cleaned["summary"],
        "key_points": cleaned["key_points"],
        "themes": cleaned["themes"],
        "thinker_mentions": cleaned["thinker_mentions"],
        "contributors": contributors,
    }
    write_back_frontmatter(md_path, new_fields)
    return "OK"


def commit_batch(batch_no: int, count: int) -> None:
    msg = f"data(primary-works): enrich {count} interview MD(s) (batch {batch_no})"
    subprocess.run(["git", "commit", "-m", msg], check=True, cwd=str(REPO_ROOT))
    subprocess.run(["git", "fetch", "origin"], check=True, cwd=str(REPO_ROOT))
    subprocess.run(["git", "rebase", "origin/main"], check=True, cwd=str(REPO_ROOT))
    subprocess.run(["git", "push", "origin", "main"], check=True, cwd=str(REPO_ROOT))


def main() -> int:
    LOG.touch()
    FAILS.touch()

    authority = build_authority_manifest(THINKERS_DIR)
    authority_slugs = {a["slug"] for a in authority}
    log(f"__START__\tauthority_size={len(authority)}")

    candidates: list[Path] = []
    for md in sorted(PW_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if fm.get("work_type") == "interview":
            candidates.append(md)
    log(f"__CANDIDATES__\tcount={len(candidates)}")

    ok = skipped = failed = 0
    batch_no = 0
    in_batch = 0
    for md in candidates:
        status = enrich_one(md, authority=authority, authority_slugs=authority_slugs)
        if status == "OK":
            ok += 1
            in_batch += 1
            log(f"{md.stem}\tOK")
            subprocess.run(["git", "add", str(md)], check=True, cwd=str(REPO_ROOT))
            if in_batch >= COMMIT_BATCH_SIZE:
                batch_no += 1
                commit_batch(batch_no, in_batch)
                in_batch = 0
        elif status == "SKIPPED":
            skipped += 1
            log(f"{md.stem}\tSKIP")
        else:
            failed += 1
    if in_batch > 0:
        batch_no += 1
        commit_batch(batch_no, in_batch)

    log(f"__END__\tok={ok} skipped={skipped} failed={failed} batches={batch_no}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
