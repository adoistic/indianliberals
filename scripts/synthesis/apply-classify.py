#!/usr/bin/env python3
"""
Step 5 of the classification pipeline: validate + merge subagent outputs
into musings/opinions frontmatter.

Per-field handling:
- themes outside vocab → proposed_themes[]
- places outside vocab → dropped, logged
- pull_quote → verbatim-substring check (smart-quote/em-dash/NFKC normalised);
  dropped on failure
- period_window → derived deterministically from resolved year
- kind/stance/scale → empty-when-uncertain; soft defaults never applied
- merge: first-run-wins by default; --overwrite=<field> opts in per-field

Run:
    .venv-extract/bin/python3 scripts/synthesis/apply-classify.py
    .venv-extract/bin/python3 scripts/synthesis/apply-classify.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/apply-classify.py --overwrite=stance
    .venv-extract/bin/python3 scripts/synthesis/apply-classify.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Local import — same dir
sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_schema import (
    validate_record,
    load_themes_vocab,
    load_places_vocab,
)

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
PW_DIR = CONTENT_ROOT / "primary-works"
OUTPUT_DIR = ROOT / "data/classify"
COVERAGE_REPORT_PARTIAL = ROOT / "data/classify/apply-log.txt"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)

# ─── Verbatim verifier (mirrors apply-ner.py, with NFKC + danda support) ─

_MARKDOWN_NOISE_RX = re.compile(r"[*_`>~]")
_SMART_QUOTES = {
    "“": '"', "”": '"',
    "‘": "'", "’": "'",
    "–": "-", "—": "-",
}


def _normalise(text: str) -> str:
    # NFKC normalises Indic glyph variants
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _SMART_QUOTES.items():
        text = text.replace(src, dst)
    text = _MARKDOWN_NOISE_RX.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def quote_substring_matches(body: str, quote: str) -> bool:
    if not quote or not body:
        return False
    nb = _normalise(body)
    nq = _normalise(quote).rstrip(".,;:।").strip("\"'")
    if not nq:
        return False
    return nq in nb


# ─── Period derivation ──────────────────────────────────────────────────

def year_to_period(year: int) -> str | None:
    if year is None:
        return None
    if year <= 1947:
        return "pre-independence"
    if year <= 1964:
        return "nehruvian-era"
    if year <= 1984:
        return "late-license-raj"
    if year <= 2004:
        return "reform-era"
    return "post-reform"


# ─── Year resolution for musings ────────────────────────────────────────

def resolve_musing_year(fm: str, source_year_inferred: int | None) -> tuple[int | None, str]:
    """Return (year, fallback_tag).

    fallback_tag is one of: 'excerpt-of', 'claude-inferred', 'pubdate', 'none'.
    """
    excerpt_of = re.search(r"^excerpt_of:\s*\"([^\"]+)\"", fm, re.M)
    if excerpt_of:
        pw_path = PW_DIR / f"{excerpt_of.group(1)}.md"
        if pw_path.exists():
            text = pw_path.read_text(encoding="utf-8")
            mm = _FRONTMATTER_RX.match(text)
            if mm:
                pub_block = re.search(r"^publication:\s*\n((?:[ \t]+.*\n)+)", mm.group(1), re.M)
                if pub_block:
                    y = re.search(r"^[ \t]+year:\s*(\d{4})", pub_block.group(1), re.M)
                    if y:
                        return int(y.group(1)), "excerpt-of"
    if source_year_inferred is not None and 1800 <= source_year_inferred <= 2026:
        return source_year_inferred, "claude-inferred"
    pd = re.search(r"^pubDate:\s*\"(\d{4})", fm, re.M)
    if pd:
        return int(pd.group(1)), "pubdate"
    return None, "none"


# ─── Frontmatter mutation ───────────────────────────────────────────────

def _yaml_str(s: str | None) -> str:
    if s is None:
        return '""'
    s = str(s)
    needs = any(c in s for c in ":#&*!|>'\"%@`{}[]\n\r\t") or (s and s[0] in "-?:") or s.endswith(" ")
    if needs:
        esc = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{esc}"'
    return s


def _emit_string_list(key: str, values: list[str]) -> str:
    if not values:
        return f"{key}: []"
    lines = [f"{key}:"]
    for v in values:
        lines.append(f'  - "{v}"')
    return "\n".join(lines)


def _emit_scope(scope: dict | None) -> str | None:
    # Parentheses are critical — without them, Python parses this as
    # `not scope or (("scale" not in scope) and (not scope.get("places")))`
    # which is wrong. We want: emit nothing only when scope is empty
    # *both* in scale AND in places.
    if not scope or ("scale" not in scope and not scope.get("places")):
        return None
    lines = ["geographic_scope:"]
    if "scale" in scope:
        lines.append(f'  scale: {scope["scale"]}')
    if scope.get("places"):
        lines.append("  places:")
        for p in scope["places"]:
            lines.append(f'    - "{p}"')
    else:
        lines.append("  places: []")
    return "\n".join(lines)


def _set_or_replace_line(fm: str, key: str, value_line: str) -> str:
    """Replace a single-line YAML key or append it. value_line is the full
    line to set (e.g. 'kind: profile' or 'stance: analyzes').
    """
    rx = re.compile(rf"^{re.escape(key)}:\s*.*$", re.M)
    if rx.search(fm):
        return rx.sub(value_line, fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + value_line + "\n"


def _set_or_replace_block(fm: str, key: str, block: str | None) -> str:
    """Replace a YAML block (multi-line, optionally an indented list/object).
    If block is None, leave existing content untouched. Block must start with
    `<key>:`.
    """
    if block is None:
        return fm
    rx = re.compile(
        rf"^{re.escape(key)}:\s*(\[\]|(?:\n[ \t]+.*)+)\n?",
        re.M,
    )
    if rx.search(fm):
        return rx.sub(block.rstrip() + "\n", fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + block.rstrip() + "\n"


def _existing_field(fm: str, key: str) -> str | None:
    """Return the raw value of a single-line YAML key, or None if absent."""
    m = re.search(rf"^{re.escape(key)}:\s*(.*)$", fm, re.M)
    return m.group(1).strip() if m else None


def _existing_array_block(fm: str, key: str) -> list[str] | None:
    """Parse a YAML array under `key`. Returns None if absent, [] if empty.

    Supports both quoted ("- \"foo\"") and unquoted ("- foo") list items —
    PyYAML permits both and our scripts emit quoted, but hand-edited frontmatter
    may use either form. Without this tolerance we'd silently overwrite
    unquoted lists on re-run, violating first-run-wins.
    """
    m = re.search(
        rf"^{re.escape(key)}:\s*(\[\]|(?:\n[ \t]+-\s*\S.*)+)",
        fm,
        re.M,
    )
    if not m:
        return None
    body = m.group(1).strip()
    if body == "[]":
        return []
    out = []
    for line in body.splitlines():
        # Try quoted first, then unquoted (no leading quote).
        sub = re.match(r"\s*-\s*\"([^\"]+)\"", line)
        if sub:
            out.append(sub.group(1))
            continue
        sub = re.match(r"\s*-\s*([^\"\s].*?)\s*$", line)
        if sub:
            out.append(sub.group(1))
    return out


# ─── Per-piece applier ──────────────────────────────────────────────────

def merge_into(fm: str, rec: dict, overwrite_fields: set[str], log: list[str]) -> tuple[str, dict]:
    """Apply rec to fm. Returns (new_fm, diff_summary).

    diff_summary maps field name → 'wrote' | 'preserved' | 'skipped'.
    """
    diff: dict[str, str] = {}

    def write_block(key: str, new_block: str | None, existing_is_empty: bool,
                    existing_matches_new: bool = False):
        nonlocal fm
        if new_block is None:
            diff[key] = "skipped"
            return
        if existing_is_empty or existing_matches_new or key in overwrite_fields:
            fm = _set_or_replace_block(fm, key, new_block)
            diff[key] = "wrote"
        else:
            diff[key] = "preserved"

    def write_line(key: str, value_line: str | None, existing_is_empty: bool,
                   existing_matches_new: bool = False):
        nonlocal fm
        if value_line is None:
            diff[key] = "skipped"
            return
        if existing_is_empty or existing_matches_new or key in overwrite_fields:
            fm = _set_or_replace_line(fm, key, value_line)
            diff[key] = "wrote"
        else:
            diff[key] = "preserved"

    # themes
    new_themes = rec.get("themes") or []
    existing_themes = _existing_array_block(fm, "themes") or []
    write_block(
        "themes", _emit_string_list("themes", new_themes),
        not existing_themes,
        existing_matches_new=(existing_themes == new_themes),
    )

    # proposed_themes
    new_proposed = rec.get("proposed_themes") or []
    existing_proposed = _existing_array_block(fm, "proposed_themes") or []
    write_block(
        "proposed_themes", _emit_string_list("proposed_themes", new_proposed),
        not existing_proposed,
        existing_matches_new=(existing_proposed == new_proposed),
    )

    # key_concepts
    new_kc = rec.get("key_concepts") or []
    existing_kc = _existing_array_block(fm, "key_concepts") or []
    write_block(
        "key_concepts", _emit_string_list("key_concepts", new_kc),
        not existing_kc,
        existing_matches_new=(existing_kc == new_kc),
    )

    # pull_quote
    pq = rec.get("pull_quote")
    existing_pq = _existing_field(fm, "pull_quote")
    if pq is not None:
        new_pq_line = f"pull_quote: {_yaml_str(pq)}"
        write_line(
            "pull_quote",
            new_pq_line,
            existing_pq is None or existing_pq == '""',
            existing_matches_new=(existing_pq is not None
                                  and existing_pq == _yaml_str(pq)),
        )

    # stance, kind, period_window
    for single_key in ("stance", "kind", "period_window"):
        val = rec.get(single_key)
        if val:
            existing = _existing_field(fm, single_key)
            write_line(
                single_key, f"{single_key}: {val}",
                existing is None,
                existing_matches_new=(existing == str(val)),
            )

    # geographic_scope
    scope_block = _emit_scope(rec.get("geographic_scope"))
    existing_scale = re.search(r"^geographic_scope:", fm, re.M)
    write_block("geographic_scope", scope_block, existing_scale is None)

    return fm, diff


def process_one(md: Path, rec: dict, themes_vocab, places_canon, places_alias,
                overwrite_fields: set[str], dry_run: bool, log: list[str]) -> str:
    text = md.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return "skip-no-frontmatter"
    fm, body = m.group(1), m.group(2)
    collection = md.parent.name  # 'musings' or 'opinions'

    sanitized, warnings = validate_record(rec, collection, themes_vocab, places_canon, places_alias)
    for w in warnings:
        log.append(w)
    if sanitized is None:
        return "rejected-record"

    # Pull-quote verbatim check
    pull_quote_failed = False
    pq = sanitized.get("pull_quote")
    if pq is not None and not quote_substring_matches(body, pq):
        log.append(f"[{sanitized['id']}] pull_quote not verbatim — dropped")
        sanitized.pop("pull_quote", None)
        pull_quote_failed = True

    # Period_window derivation
    musing_excerpt_of_present = bool(re.search(r"^excerpt_of:\s*\"[^\"]+\"", fm, re.M))
    if collection == "opinions":
        pd = re.search(r"^pubDate:\s*\"(\d{4})", fm, re.M)
        year = int(pd.group(1)) if pd else None
        fallback_tag = "pubdate"
    else:
        year, fallback_tag = resolve_musing_year(fm, sanitized.get("source_year_inferred"))
    period = year_to_period(year) if year else None
    if period:
        sanitized["period_window"] = period

    # source_year_inferred is a transient input field; never written to frontmatter
    sanitized.pop("source_year_inferred", None)

    # needs_review per spec §6 Step 5:
    #   (a) year-resolution fell back to pubDate for a musing WITHOUT excerpt_of
    #   (b) pull_quote failed verbatim verification
    #   (c) ≥1 *required* expected field is missing
    #
    # The spec's "expected fields" are the ones where empty-when-uncertain does
    # NOT apply (i.e. every piece SHOULD have these populated). The fields where
    # empty-when-uncertain DOES apply — kind, stance, scale, pull_quote — can be
    # legitimately null and don't trigger review when missing.
    REQUIRED_KEYS = {"themes", "key_concepts", "period_window"}
    missing_required = [k for k in REQUIRED_KEYS if not sanitized.get(k)]

    needs_review_flags: list[str] = []
    if collection == "musings" and fallback_tag == "pubdate" and not musing_excerpt_of_present:
        needs_review_flags.append("year-fallback-to-pubdate")
    if pull_quote_failed:
        needs_review_flags.append("pull-quote-verbatim-failed")
    if missing_required:
        needs_review_flags.append(f"missing-required-fields:{','.join(sorted(missing_required))}")

    new_fm, diff = merge_into(fm, sanitized, overwrite_fields, log)

    # needs_review handling
    if needs_review_flags:
        log.append(f"[{sanitized['id']}] needs_review set: {needs_review_flags}")
        new_fm = _set_or_replace_line(new_fm, "needs_review", "needs_review: true")

    if dry_run:
        return "would-update"
    new_text = f"---\n{new_fm}---\n{body}"
    md.write_text(new_text, encoding="utf-8")
    return "updated"


# ─── Driver ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--overwrite",
        action="append",
        default=[],
        help="Per-field overwrite. Repeatable AND comma-splittable: "
             "--overwrite=stance --overwrite=kind  OR  --overwrite=stance,kind",
    )
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        _run_tests()
        return 0

    themes_vocab = load_themes_vocab()
    places_canon, places_alias = load_places_vocab()
    # Allow comma-separated values too.
    overwrite: set[str] = set()
    for raw in args.overwrite:
        for field in raw.split(","):
            field = field.strip()
            if field:
                overwrite.add(field)

    # Aggregate all output JSONs
    records: dict[str, dict] = {}
    for out_path in sorted(OUTPUT_DIR.glob("output-*.json")):
        arr = json.loads(out_path.read_text())
        for r in arr:
            if "id" not in r:
                continue
            records[r["id"]] = r

    log: list[str] = []
    summary: dict[str, int] = {}
    for collection in ("musings", "opinions"):
        coll_dir = CONTENT_ROOT / collection
        for md in sorted(coll_dir.glob("*.md")):
            rec = records.get(md.stem)
            if rec is None:
                summary["skip-no-record"] = summary.get("skip-no-record", 0) + 1
                continue
            result = process_one(md, rec, themes_vocab, places_canon, places_alias,
                                 overwrite, args.dry_run, log)
            summary[result] = summary.get(result, 0) + 1
    for k in sorted(summary):
        print(f"  {summary[k]:4d}  {k}")
    print(f"  warnings: {len(log)}")
    COVERAGE_REPORT_PARTIAL.parent.mkdir(parents=True, exist_ok=True)
    COVERAGE_REPORT_PARTIAL.write_text("\n".join(log) + "\n" if log else "(no warnings)\n")
    print(f"  log written to {COVERAGE_REPORT_PARTIAL.relative_to(ROOT)}")
    return 0


def _run_tests():
    # Verbatim verifier
    body = "Hello world. The economy is broken. — A.D."
    assert quote_substring_matches(body, "The economy is broken")
    assert quote_substring_matches(body, "“The economy is broken”")  # smart quotes
    assert quote_substring_matches(body, "The economy is broken.")  # trailing punctuation
    assert not quote_substring_matches(body, "The economy is fine")
    assert not quote_substring_matches(body, "")

    # Indic danda support — trailing danda strip
    indic_body = "यह आर्थिक नीति है। एक स्पष्ट उदाहरण।"
    assert quote_substring_matches(indic_body, "यह आर्थिक नीति है")
    # Internal danda preserved verbatim in both body and quote
    indic_body2 = "पहला वाक्य। दूसरा वाक्य भी है।"
    assert quote_substring_matches(indic_body2, "पहला वाक्य। दूसरा वाक्य भी है"), "internal danda should match"

    # Year → period
    assert year_to_period(1945) == "pre-independence"
    assert year_to_period(1947) == "pre-independence"
    assert year_to_period(1948) == "nehruvian-era"
    assert year_to_period(1964) == "nehruvian-era"
    assert year_to_period(1965) == "late-license-raj"
    assert year_to_period(1984) == "late-license-raj"
    assert year_to_period(1985) == "reform-era"
    assert year_to_period(2004) == "reform-era"
    assert year_to_period(2005) == "post-reform"
    assert year_to_period(2024) == "post-reform"
    assert year_to_period(None) is None

    # Frontmatter line set
    fm = 'id: "x"\nkind: profile\ntitle: "y"\n'
    fm2 = _set_or_replace_line(fm, "kind", "kind: commentary")
    assert "kind: commentary" in fm2
    assert "kind: profile" not in fm2

    fm3 = _set_or_replace_line(fm, "stance", "stance: analyzes")
    assert "stance: analyzes" in fm3
    assert fm3.startswith('id: "x"')

    # Block set / replace
    fm4 = 'id: "x"\nthemes:\n  - "old"\nlanguage: "en"\n'
    new_block = _emit_string_list("themes", ["new1", "new2"])
    fm5 = _set_or_replace_block(fm4, "themes", new_block)
    assert '- "old"' not in fm5
    assert '- "new1"' in fm5
    assert '- "new2"' in fm5
    assert 'language: "en"' in fm5

    # Existing field
    assert _existing_field(fm, "kind") == "profile"
    assert _existing_field(fm, "stance") is None

    # Existing array block
    assert _existing_array_block(fm4, "themes") == ["old"]
    assert _existing_array_block(fm, "themes") is None

    # Merge behavior: empty existing → wrote
    rec = {
        "id": "x", "themes": ["democracy"], "proposed_themes": [],
        "key_concepts": ["liberty"], "stance": "analyzes", "kind": "profile",
    }
    new_fm, diff = merge_into(fm, rec, overwrite_fields=set(), log=[])
    assert diff["themes"] == "wrote", diff
    assert diff["kind"] == "wrote", diff

    # Merge behavior: populated existing without overwrite → preserved
    fm_pop = 'id: "x"\nkind: profile\nstance: argues-for\n'
    rec2 = {"id": "x", "kind": "commentary", "stance": "analyzes"}
    new_fm2, diff2 = merge_into(fm_pop, rec2, overwrite_fields=set(), log=[])
    assert diff2["kind"] == "preserved", diff2
    assert diff2["stance"] == "preserved", diff2
    assert "kind: profile" in new_fm2

    # Merge behavior: --overwrite=kind → wrote
    new_fm3, diff3 = merge_into(fm_pop, rec2, overwrite_fields={"kind"}, log=[])
    assert diff3["kind"] == "wrote", diff3
    assert diff3["stance"] == "preserved", diff3
    assert "kind: commentary" in new_fm3
    assert "stance: argues-for" in new_fm3

    # Merge behavior: --overwrite on a populated array block (themes)
    fm_themes_pop = 'id: "x"\nthemes:\n  - "old-theme"\nlanguage: "en"\n'
    rec_themes = {"id": "x", "themes": ["democracy", "free-enterprise"], "proposed_themes": []}
    new_fm_t, diff_t = merge_into(fm_themes_pop, rec_themes, overwrite_fields=set(), log=[])
    assert diff_t["themes"] == "preserved", diff_t
    assert "old-theme" in new_fm_t, "themes preserved"
    new_fm_t2, diff_t2 = merge_into(fm_themes_pop, rec_themes, overwrite_fields={"themes"}, log=[])
    assert diff_t2["themes"] == "wrote", diff_t2
    assert "old-theme" not in new_fm_t2
    assert "democracy" in new_fm_t2 and "free-enterprise" in new_fm_t2

    # Unquoted array survives _existing_array_block (regression guard)
    fm_unquoted = 'id: "x"\nthemes:\n  - democracy\n  - free-enterprise\n'
    parsed = _existing_array_block(fm_unquoted, "themes")
    assert parsed == ["democracy", "free-enterprise"], parsed

    # Integration: process_one drops bad pull_quote AND sets needs_review
    import tempfile
    sample_md = """---
id: "test-pq"
title: "Test"
pubDate: "2024-01-01T00:00:00Z"
themes: []
draft: false
needs_review: false
language: "en"
---

The economy is broken.
"""
    bad_rec = {
        "id": "test-pq",
        "themes": ["democracy"],
        "proposed_themes": [],
        "key_concepts": ["liberty"],
        "pull_quote": "THIS PHRASE DOES NOT APPEAR IN THE BODY OF THE PIECE AT ALL",
        "stance": "analyzes",
        "kind": "editorial",
        "geographic_scope": {"scale": "national", "places": []},
    }
    log_buf: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        # We need the file under a "musings" or "opinions" parent dir so the
        # collection inference (md.parent.name) works.
        coll_dir = Path(td) / "opinions"
        coll_dir.mkdir()
        p = coll_dir / "test-pq.md"
        p.write_text(sample_md)
        themes_vocab = {"democracy"}
        places_canon, places_alias = ({"maharashtra"}, {})
        result = process_one(p, bad_rec, themes_vocab, places_canon, places_alias,
                             overwrite_fields=set(), dry_run=False, log=log_buf)
        assert result == "updated", result
        new = p.read_text()
        assert "pull_quote:" not in new or 'pull_quote: ""' in new, "bad quote should be dropped"
        assert "needs_review: true" in new, "needs_review should be set after pull_quote drop"
        assert any("pull_quote not verbatim" in line for line in log_buf), log_buf

    # Happy path: a complete record should NOT trip any needs_review flag.
    good_sample = """---
id: "test-happy"
title: "Test"
pubDate: "2010-01-01T00:00:00Z"
themes: []
draft: false
needs_review: false
language: "en"
---

The economy is broken in surprising ways.
"""
    good_rec = {
        "id": "test-happy",
        "themes": ["democracy"],
        "proposed_themes": [],
        "key_concepts": ["liberty"],
        "pull_quote": "The economy is broken in surprising ways.",
        "stance": "analyzes",
        "kind": "editorial",
        "geographic_scope": {"scale": "national", "places": []},
    }
    log_buf2: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        coll_dir = Path(td) / "opinions"
        coll_dir.mkdir()
        p = coll_dir / "test-happy.md"
        p.write_text(good_sample)
        themes_vocab = {"democracy"}
        places_canon, places_alias = ({"maharashtra"}, {})
        result = process_one(p, good_rec, themes_vocab, places_canon, places_alias,
                             overwrite_fields=set(), dry_run=False, log=log_buf2)
        assert result == "updated", result
        new = p.read_text()
        # needs_review should stay false (or be absent — the initial line stays false)
        assert "needs_review: true" not in new, "happy path should not flag review"

    print("apply-classify tests passed.")


if __name__ == "__main__":
    sys.exit(main())
