#!/usr/bin/env python3
"""
Apply data/synthesis/ner-mentions.jsonl to live entry frontmatter.

For each entry that has mention records, validate every quote substring-
matches the body under normalisation rules, drop validation failures to
data/synthesis/ner-rejected.txt, write thinker_mentions[] + populate
related_thinkers[] in the entry's frontmatter.

Idempotent: re-running replaces thinker_mentions[] atomically per entry.

Run from repo root (after resolve-ner.py emits ner-mentions.jsonl):

    python3 scripts/synthesis/apply-ner.py
    python3 scripts/synthesis/apply-ner.py --test    # run the validator's
                                                       built-in unit tests
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
NER_MENTIONS = ROOT / "data/synthesis/ner-mentions.jsonl"
REJECTED_LOG = ROOT / "data/synthesis/ner-rejected.txt"
AUTHORITY = ROOT / "data/authority/thinkers.json"


# ─── Verbatim-substring validator ──────────────────────────────────────

_MARKDOWN_NOISE_RX = re.compile(r"[*_`>~]")
_SMART_QUOTES = {
    "“": '"', "”": '"',   # curly double quotes → straight
    "‘": "'", "’": "'",   # curly single quotes → straight
    "–": "-", "—": "-",   # en/em dashes → hyphen
}


def _normalise(text: str) -> str:
    """Normalise body or candidate quote for substring matching.

    Steps (in order):
      1. Replace smart quotes / dashes with their straight ASCII equivalents.
      2. Remove markdown emphasis markers (*, _, backtick, >, ~).
      3. Collapse all whitespace runs to a single space.
      4. Strip leading and trailing whitespace.

    Case is preserved. Trailing punctuation on the candidate quote is
    handled in `quote_substring_matches`, not here."""
    for src, dst in _SMART_QUOTES.items():
        text = text.replace(src, dst)
    text = _MARKDOWN_NOISE_RX.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def quote_substring_matches(body: str, quote: str) -> bool:
    """Return True if `quote` appears (case-sensitive) as a substring of
    `body` under our normalisation rules.

    The LLM is allowed minor formatting drift versus the body: smart-quote
    vs straight-quote, markdown emphasis around words, whitespace
    variation, and trailing punctuation. Anything beyond that — different
    words, paraphrase, hallucination — fails."""
    if not quote or not body:
        return False
    norm_body = _normalise(body)
    norm_quote = _normalise(quote)
    # Allow the candidate quote to drop a final period/comma/semicolon/colon
    # that is present in the body but not in the LLM's output.
    norm_quote = norm_quote.rstrip(".,;:")
    if not norm_quote:
        return False
    return norm_quote in norm_body


# ─── YAML emit helpers (parallel to scripts/synthesis/emit-astro-md.py) ──

def _yaml_str(s: str) -> str:
    if s is None:
        return '""'
    s = str(s)
    if not s:
        return '""'
    needs_quotes = any(c in s for c in ":#&*!|>'\"%@`{}[]\n\r\t") or (s and s[0] in "-?:") or s.endswith(" ")
    if needs_quotes:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return s


def _yaml_thinker_mentions_block(mentions: list[dict], indent: int = 0) -> str:
    """Emit a YAML block for the thinker_mentions[] array. Each mention
    becomes a list item; nested arrays (evidence, key_passages) emit as
    sub-lists. Returns the block including its leading 'thinker_mentions:'
    key line."""
    pad = " " * indent
    if not mentions:
        return f"{pad}thinker_mentions: []"
    lines = [f"{pad}thinker_mentions:"]
    item_pad = " " * (indent + 2)
    inner_pad = " " * (indent + 4)
    for m in mentions:
        lines.append(f"{item_pad}- thinker: {_yaml_str(m['thinker'])}")
        lines.append(f"{inner_pad}role: {m['role']}")
        lines.append(f"{inner_pad}reasoning: {_yaml_str(m['reasoning'])}")
        evidence = m.get("evidence") or []
        if evidence:
            lines.append(f"{inner_pad}evidence:")
            for ev in evidence:
                lines.append(f"{inner_pad}  - quote: {_yaml_str(ev['quote'])}")
                if ev.get("context"):
                    lines.append(f"{inner_pad}    context: {_yaml_str(ev['context'])}")
        else:
            lines.append(f"{inner_pad}evidence: []")
        key_passages = m.get("key_passages") or []
        if key_passages:
            lines.append(f"{inner_pad}key_passages:")
            for kp in key_passages:
                lines.append(f"{inner_pad}  - quote: {_yaml_str(kp['quote'])}")
                lines.append(f"{inner_pad}    what_it_shows: {_yaml_str(kp['what_it_shows'])}")
        else:
            lines.append(f"{inner_pad}key_passages: []")
    return "\n".join(lines)


# ─── Frontmatter helpers ───────────────────────────────────────────────

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_TM_BLOCK_RX = re.compile(
    r"^thinker_mentions:\s*(?:\[\]|(?:\n[ \t]+.*)+)\n?",
    re.M,
)
_RT_LINE_RX = re.compile(r"^related_thinkers:\s*.*$(?:\n[ \t]+.*)*", re.M)


def _replace_or_append_block(fm: str, key: str, new_block: str) -> str:
    """Replace `<key>:` block in frontmatter with `new_block`. If the key
    isn't present, append new_block to the end of `fm`. `new_block`
    must start with `<key>:`."""
    if key == "thinker_mentions":
        rx = _TM_BLOCK_RX
    elif key == "related_thinkers":
        rx = _RT_LINE_RX
    else:
        raise ValueError(f"unknown frontmatter key: {key}")
    if rx.search(fm):
        return rx.sub(new_block.rstrip() + "\n", fm)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + new_block.rstrip() + "\n"


# ─── Authority / body loaders ──────────────────────────────────────────

def load_body(collection: str, entry_id: str) -> str | None:
    p = CONTENT_ROOT / collection / f"{entry_id}.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    return m.group(2)


def load_authority_slugs() -> set[str]:
    doc = json.loads(AUTHORITY.read_text())
    return {t["id"] for t in doc.get("thinkers", [])}


def load_existing_author_slugs(collection: str, entry_id: str) -> set[str]:
    """Return the set of slugs already attached to this entry as author
    or subject (from Phase A). These slugs are excluded from
    related_thinkers[] to avoid the entry cross-referencing its own
    author/subject."""
    p = CONTENT_ROOT / collection / f"{entry_id}.md"
    if not p.exists():
        return set()
    text = p.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return set()
    fm = m.group(1)
    slugs: set[str] = set()
    for field in ("author", "subject"):
        mm = re.search(rf"^{field}:\s*\"([^\"]+)\"", fm, re.M)
        if mm:
            slugs.add(mm.group(1))
    # authors[] (primary-works)
    mm = re.search(r"^authors:\s*\n((?:[ \t]+-\s*\"[^\"]+\"\s*\n)+)", fm, re.M)
    if mm:
        for line in mm.group(1).splitlines():
            sub = re.match(r"\s*-\s*\"([^\"]+)\"", line)
            if sub:
                slugs.add(sub.group(1))
    return slugs


# ─── Built-in tests ────────────────────────────────────────────────────

def _run_tests() -> int:
    """Plain-Python assertion-style tests. Exits 0 on pass, 1 on fail."""
    cases = [
        # (label, body, quote, expected)
        ("exact match", "Hayek argued for spontaneous order.", "Hayek argued for spontaneous order.", True),
        ("substring", "Hayek argued for spontaneous order in 1944.", "Hayek argued for spontaneous order", True),
        ("markdown emphasis in body", "*Hayek* argued for spontaneous order.", "Hayek argued for spontaneous order", True),
        ("smart quotes in body", "Hayek’s argument was clear: “spontaneous order”.", "Hayek's argument was clear: \"spontaneous order\"", True),
        ("smart quotes in quote", "Hayek's argument was clear: \"spontaneous order\".", "Hayek’s argument was clear: “spontaneous order”", True),
        ("whitespace variation", "Hayek argued for\n\nspontaneous order.", "Hayek argued for spontaneous order", True),
        ("trailing period drop", "Hayek argued for spontaneous order.", "Hayek argued for spontaneous order.", True),
        ("trailing comma drop", "Hayek, an Austrian economist, argued.", "Hayek, an Austrian economist", True),
        ("paraphrase (must fail)", "Hayek argued for spontaneous order.", "Hayek defended unplanned market coordination.", False),
        ("hallucinated quote (must fail)", "Hayek argued for spontaneous order.", "Hayek opposed all forms of central planning.", False),
        ("empty quote (must fail)", "Hayek argued for spontaneous order.", "", False),
        ("empty body (must fail)", "", "Hayek argued for spontaneous order.", False),
        ("case-sensitive (must fail)", "Hayek argued for spontaneous order.", "hayek argued for spontaneous order", False),
        ("markdown link", "See [Hayek's Road to Serfdom](https://example.com) for more.", "Road to Serfdom", True),
        ("blockquote prefix", "> Hayek wrote: spontaneous order matters.", "Hayek wrote: spontaneous order matters.", True),
        ("underscore emphasis", "_Hayek_ argued for spontaneous order.", "Hayek argued for spontaneous order", True),
        ("backtick code span", "The term `spontaneous order` is Hayek's.", "The term spontaneous order is Hayek's.", True),
        ("em-dash normalisation", "Hayek—an Austrian economist—argued for spontaneous order.", "Hayek-an Austrian economist-argued for spontaneous order", True),
        ("en-dash normalisation", "Hayek (1899–1992) argued for spontaneous order.", "Hayek (1899-1992) argued for spontaneous order", True),
        ("mixed emphasis + apostrophe", "*Hayek*’s _Road to Serfdom_ is foundational.", "Hayek's Road to Serfdom is foundational", True),
    ]
    failed = 0
    for label, body, quote, expected in cases:
        actual = quote_substring_matches(body, quote)
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            failed += 1
        print(f"[{status}] {label}: expected={expected} got={actual}")
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    return 0 if failed == 0 else 1


# ─── Main ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Run validator unit tests and exit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-entry", default="", help="Restrict apply to a single entry_id (debugging)")
    args = ap.parse_args()

    if args.test:
        return _run_tests()

    if not NER_MENTIONS.exists():
        print(f"ERROR: {NER_MENTIONS} missing — run resolve-ner.py first", file=sys.stderr)
        return 1

    authority = load_authority_slugs()

    # Read mentions, group by entry_id
    by_entry: dict[str, list[dict]] = {}
    for raw in NER_MENTIONS.read_text().splitlines():
        raw = raw.strip()
        if not raw or not raw.startswith("{"):
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        eid = rec.get("entry_id")
        if not eid:
            continue
        if args.only_entry and eid != args.only_entry:
            continue
        by_entry.setdefault(eid, []).append(rec)

    counts = {
        "entries_processed": 0,
        "mentions_written": 0,
        "mentions_rejected_quote": 0,
        "mentions_rejected_thinker": 0,
        "mentions_rejected_self": 0,
        "files_updated": 0,
    }
    rejected_lines: list[str] = []

    for eid, mentions in by_entry.items():
        collection = mentions[0].get("collection")
        if not collection:
            continue
        body = load_body(collection, eid)
        if body is None:
            rejected_lines.append(f"{collection}\t{eid}\tBODY_MISSING")
            continue
        existing_author_slugs = load_existing_author_slugs(collection, eid)

        valid_mentions: list[dict] = []
        for m in mentions:
            slug = m.get("thinker_id")
            if not slug or slug not in authority:
                counts["mentions_rejected_thinker"] += 1
                rejected_lines.append(f"{collection}\t{eid}\tunknown_thinker={slug}")
                continue
            # Skip the entry's own author/subject (Phase A owns those)
            if slug in existing_author_slugs:
                counts["mentions_rejected_self"] += 1
                continue
            # Validate every quote
            evidence = m.get("evidence") or []
            key_passages = m.get("key_passages") or []
            kept_evidence: list[dict] = []
            for ev in evidence:
                q = ev.get("quote", "")
                if quote_substring_matches(body, q):
                    kept_evidence.append({"quote": q, **({"context": ev["context"]} if ev.get("context") else {})})
                else:
                    counts["mentions_rejected_quote"] += 1
                    rejected_lines.append(f"{collection}\t{eid}\t{slug}\tevidence_quote_no_substring\t{q[:80]}")
            kept_key_passages: list[dict] = []
            for kp in key_passages:
                q = kp.get("quote", "")
                if quote_substring_matches(body, q):
                    kept_key_passages.append({"quote": q, "what_it_shows": kp.get("what_it_shows", "")})
                else:
                    counts["mentions_rejected_quote"] += 1
                    rejected_lines.append(f"{collection}\t{eid}\t{slug}\tkey_passage_quote_no_substring\t{q[:80]}")
            # If a role expects evidence/key_passages and BOTH lists are empty after validation, drop the mention
            role = m.get("role", "mention")
            if role == "subject" and not kept_key_passages:
                continue
            if role in ("mention", "author") and not kept_evidence:
                continue
            valid_mentions.append({
                "thinker": slug,
                "role": role,
                "reasoning": m.get("reasoning", ""),
                "evidence": kept_evidence,
                "key_passages": kept_key_passages,
            })

        # related_thinkers = de-duped union of (kept mentions' thinkers) minus the entry's own author/subject
        related_slugs = sorted({m["thinker"] for m in valid_mentions} - existing_author_slugs)

        # Render the frontmatter blocks
        tm_block = _yaml_thinker_mentions_block(valid_mentions, indent=0)
        rt_block = "related_thinkers: " + (
            "[]" if not related_slugs else "\n" + "\n".join(f"  - {_yaml_str(s)}" for s in related_slugs)
        )

        # Apply to the file
        p = CONTENT_ROOT / collection / f"{eid}.md"
        text = p.read_text(encoding="utf-8")
        fm_match = _FRONTMATTER_RX.match(text)
        if not fm_match:
            rejected_lines.append(f"{collection}\t{eid}\tNO_FRONTMATTER")
            continue
        fm = fm_match.group(1)
        body_part = fm_match.group(2)
        fm = _replace_or_append_block(fm, "thinker_mentions", tm_block)
        fm = _replace_or_append_block(fm, "related_thinkers", rt_block)
        new_text = f"---\n{fm}\n---\n{body_part}"
        if not args.dry_run:
            p.write_text(new_text, encoding="utf-8")
        counts["files_updated"] += 1
        counts["entries_processed"] += 1
        counts["mentions_written"] += len(valid_mentions)

    if rejected_lines and not args.dry_run:
        REJECTED_LOG.write_text("\n".join(rejected_lines) + "\n", encoding="utf-8")
        counts["rejected_log"] = str(REJECTED_LOG.relative_to(ROOT))

    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
