#!/usr/bin/env python3
"""
Apply data/synthesis/cleanup-plan.json:
  1. Delete fake-thinker MDs + remove their authority entries
  2. Merge each duplicate cluster:
       - Absorb losers' aliases / aka into winner
       - Redirect every byline_lookup value pointing to a loser → winner
       - Delete loser MDs from apps/site/src/content/thinkers/
       - Sweep all content + synthesis JSON for word-boundary loser-slug
         references and rewrite to winner slug
  3. Rebuild byline_lookup so deleted-fake slugs aren't lingering keys
  4. Bump authority._meta and write back

Idempotent — safe to re-run.

Run from the repo root:
    python3 scripts/synthesis/apply-thinker-cleanup.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "data/synthesis/cleanup-plan.json"
AUTHORITY = ROOT / "data/authority/thinkers.json"
THINKERS_MD = ROOT / "apps/site/src/content/thinkers"
SWEEP_ROOTS = [
    ROOT / "apps/site/src/content",
    ROOT / "data/synthesis",
    ROOT / "data/authority",
]

# Files the sweep MUST skip. These are audit / planning outputs that
# legitimately mention deleted slugs inside string values (as evidence
# of what was deleted) — rewriting them would corrupt the audit trail.
SWEEP_SKIP = {
    ROOT / "data/synthesis/cleanup-plan.json",
}


def main() -> int:
    if not PLAN.exists():
        print(f"ERROR: run audit-thinkers.py first ({PLAN} missing)")
        return 1
    plan = json.loads(PLAN.read_text())
    auth = json.loads(AUTHORITY.read_text())

    # Build id → record map for quick mutation
    thinkers = auth.get("thinkers", [])
    by_id = {t["id"]: t for t in thinkers}

    deletions: set[str] = set()
    redirects: dict[str, str] = {}  # loser_id → winner_id

    # ─── Pass 1: deletions ──────────────────────────────────────────────
    for d in plan.get("delete", []):
        deletions.add(d["id"])

    # ─── Pass 2: merges ─────────────────────────────────────────────────
    for m in plan.get("merge", []):
        winner = m["winner"]
        for loser in m["losers"]:
            redirects[loser] = winner
        if winner in by_id:
            w = by_id[winner]
            # Override canonical name if the plan specified a cleaner one
            if m.get("winner_canonical"):
                w.setdefault("name", {})["canonical"] = m["winner_canonical"]
            # Absorb loser aliases
            aka = set(w.get("name", {}).get("also_known_as") or [])
            for loser in m["losers"]:
                lr = by_id.get(loser)
                if not lr:
                    continue
                aka.add(lr.get("name", {}).get("canonical", "").strip())
                aka.update(lr.get("name", {}).get("also_known_as") or [])
            # Drop the winner's own canonical from its aka list to avoid self-reference
            wcanon = w.get("name", {}).get("canonical", "")
            aka = {a for a in aka if a and a != wcanon}
            w.setdefault("name", {})["also_known_as"] = sorted(aka)

    # ─── Pass 3: remove deletion + loser entries from thinkers list ─────
    remove_ids = deletions | set(redirects.keys())
    new_thinkers = [t for t in thinkers if t["id"] not in remove_ids]
    auth["thinkers"] = new_thinkers

    # ─── Pass 4: rebuild byline_lookup ──────────────────────────────────
    # Redirect any entry pointing to a loser to its winner. Drop entries
    # pointing to deletions (those people don't exist as real thinkers).
    bl = auth.get("byline_lookup", {})
    new_bl: dict[str, str] = {}
    for needle, tid in bl.items():
        if tid in deletions:
            continue
        if tid in redirects:
            new_bl[needle] = redirects[tid]
        else:
            new_bl[needle] = tid
    # Add the loser's canonical name as a new alias for the winner,
    # so future byline strings matching the loser name still resolve.
    for loser, winner in redirects.items():
        loser_record = by_id.get(loser)
        if not loser_record:
            continue
        for src in [
            loser_record.get("name", {}).get("canonical"),
            *(loser_record.get("name", {}).get("also_known_as") or []),
        ]:
            if not src:
                continue
            needle = _normalise_byline_key(src)
            if needle and needle not in new_bl:
                new_bl[needle] = winner
    auth["byline_lookup"] = dict(sorted(new_bl.items()))

    # ─── Pass 5: write authority ────────────────────────────────────────
    auth.setdefault("_meta", {})
    auth["_meta"]["last_cleanup"] = plan.get("generated_at", "2026-05-18")
    auth["_meta"]["cleanup_summary"] = {
        "deleted": len(deletions),
        "merged_clusters": len(plan.get("merge", [])),
        "final_thinker_count": len(new_thinkers),
        "byline_lookup_size": len(new_bl),
    }
    AUTHORITY.write_text(json.dumps(auth, indent=2, ensure_ascii=False) + "\n")
    print(f"[apply] authority rewritten: {len(new_thinkers)} thinkers, {len(new_bl)} byline keys")

    # ─── Pass 6: delete MD files for deletions + losers ─────────────────
    md_deleted = 0
    for tid in remove_ids:
        p = THINKERS_MD / f"{tid}.md"
        if p.exists():
            p.unlink()
            md_deleted += 1
    print(f"[apply] deleted {md_deleted} thinker MD files")

    # ─── Pass 7: sweep content for slug references ──────────────────────
    # The sweep must NEVER touch a frontmatter `id:` line — that line is the
    # entry's own canonical slug, not a reference to another entry. Same
    # for `theprint_url:`, `youtube_url:`, anything URL-shaped. We restrict
    # rewrites to the *value* of recognised reference fields, and to plain
    # body-text mentions outside frontmatter.
    REF_FIELDS = {
        "author", "subject", "thinker", "thinker_id", "thinker_unresolved",
        "subject_name",  # only for sweep awareness; we don't rewrite the string
    }
    REF_ARRAY_FIELDS = {
        "authors", "editors", "related_thinkers", "related_works", "affiliations",
    }

    files_rewritten = 0
    refs_rewritten = 0
    refs_dropped = 0
    for root in SWEEP_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in {".md", ".mdx", ".json"}:
                continue
            if p == AUTHORITY or p in SWEEP_SKIP:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            if not any(tid in text for tid in remove_ids):
                continue

            new_text = text

            # Split MD into frontmatter + body. Rewrites in body are
            # bare-slug only (e.g., links like `/thinkers/<slug>/`). Rewrites
            # in frontmatter happen only when the line is one of REF_FIELDS
            # or appears inside a REF_ARRAY_FIELDS array. The `id:` line is
            # never touched.
            fm_match = re.match(r"^(---\n)(.*?)(\n---)", new_text, re.S)
            if p.suffix in {".md", ".mdx"} and fm_match:
                fm_head, fm_body, fm_tail = fm_match.group(1), fm_match.group(2), fm_match.group(3)
                rest = new_text[fm_match.end():]

                new_fm_lines: list[str] = []
                in_array = None  # name of array field we're inside, if any
                array_indent = ""
                for line in fm_body.split("\n"):
                    stripped = line.lstrip()
                    leading_ws = line[: len(line) - len(stripped)]

                    # Detect entering / leaving an array block
                    arr_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*):\s*$", stripped)
                    if arr_match and arr_match.group(1) in REF_ARRAY_FIELDS:
                        in_array = arr_match.group(1)
                        array_indent = leading_ws
                        new_fm_lines.append(line)
                        continue
                    if in_array and stripped.startswith("- "):
                        # Inside ref array — safe to rewrite
                        new_line = _rewrite_ref(line, redirects, deletions)
                        if new_line != line:
                            if new_line.strip().endswith('""') or new_line.strip() == '-':
                                refs_dropped += 1
                            else:
                                refs_rewritten += 1
                        new_fm_lines.append(new_line)
                        continue
                    if in_array and leading_ws <= array_indent and stripped and not stripped.startswith("- "):
                        in_array = None

                    # Detect inline array on one line:  field: [..., "x", ...]
                    inline_arr = re.match(r"([A-Za-z_][A-Za-z0-9_]*):\s*\[(.*)\]\s*$", stripped)
                    if inline_arr and inline_arr.group(1) in REF_ARRAY_FIELDS:
                        items = inline_arr.group(2)
                        new_items, drops, rewrites = _rewrite_inline_array(items, redirects, deletions)
                        refs_rewritten += rewrites
                        refs_dropped += drops
                        new_fm_lines.append(f"{leading_ws}{inline_arr.group(1)}: [{new_items}]")
                        continue

                    # Single-value ref field:  field: "value" or field: value
                    sv_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.+?)\s*$", stripped)
                    if sv_match and sv_match.group(1) in REF_FIELDS:
                        val = sv_match.group(2).strip().strip('"').strip("'")
                        if val in deletions:
                            new_fm_lines.append(f"{leading_ws}{sv_match.group(1)}: \"\"")
                            refs_dropped += 1
                            continue
                        if val in redirects:
                            new_fm_lines.append(f"{leading_ws}{sv_match.group(1)}: \"{redirects[val]}\"")
                            refs_rewritten += 1
                            continue

                    new_fm_lines.append(line)

                new_fm = "\n".join(new_fm_lines)
                new_text = fm_head + new_fm + fm_tail + rest

            # Body / non-MD: rewrite known-good link patterns only. Specifically
            # `/thinkers/<slug>/` and `/organisations/<slug>/`. Bare slugs in
            # free text are NOT touched (too risky — could be a substring of an
            # interview slug etc.).
            def _rewrite_link(m: re.Match) -> str:
                col, slug, trail = m.group(1), m.group(2), m.group(3)
                if slug in deletions:
                    return f"/{col}/{slug}{trail}"  # leave as-is; broken link is better than wrong link
                if slug in redirects:
                    return f"/{col}/{redirects[slug]}{trail}"
                return m.group(0)

            new_text = re.sub(
                r"/(thinkers|organisations)/([a-z0-9-]+)(/|\b)",
                _rewrite_link,
                new_text,
            )

            # JSON files: rewrite quoted slug values that match known ref keys.
            # data/synthesis/*.json has structures like {"thinker_id": "<slug>"}.
            if p.suffix == ".json":
                for loser, winner in redirects.items():
                    pat = re.compile(rf'"({"|".join(map(re.escape, [loser]))})"')
                    new_text, n = pat.subn(f'"{winner}"', new_text)
                    refs_rewritten += n

            if new_text != text:
                p.write_text(new_text, encoding="utf-8")
                files_rewritten += 1
    print(f"[apply] swept content: {files_rewritten} files, {refs_rewritten} refs redirected, {refs_dropped} refs dropped")
    return 0


def _rewrite_ref(line: str, redirects: dict[str, str], deletions: set[str]) -> str:
    """Rewrite a `- "<slug>"` ref-array line. Returns the unchanged line if
    the slug isn't in the rewrite tables, an empty-quoted line if it points
    to a deletion, or a redirected line if it points to a merge loser."""
    m = re.match(r'(\s*-\s*)"([^"]+)"(.*)', line)
    if not m:
        return line
    prefix, val, suffix = m.group(1), m.group(2), m.group(3)
    if val in deletions:
        return f'{prefix}""{suffix}'
    if val in redirects:
        return f'{prefix}"{redirects[val]}"{suffix}'
    return line


def _rewrite_inline_array(
    items: str, redirects: dict[str, str], deletions: set[str]
) -> tuple[str, int, int]:
    """Rewrite an inline YAML array body like `"a", "b", "c"`. Returns
    (new_items_str, drops, rewrites)."""
    parts = [p.strip() for p in items.split(",")]
    new_parts: list[str] = []
    drops = rewrites = 0
    for part in parts:
        val = part.strip().strip('"').strip("'")
        if val in deletions:
            drops += 1
            continue  # silently drop deletions
        if val in redirects:
            new_parts.append(f'"{redirects[val]}"')
            rewrites += 1
            continue
        new_parts.append(part)
    return ", ".join(new_parts), drops, rewrites


def _normalise_byline_key(s: str) -> str:
    """Match the byline_lookup normalisation: lowercase, drop punct, collapse ws."""
    s = s.lower().replace(".", " ").replace(",", " ").replace("-", " ").replace("'", "").replace("’", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


if __name__ == "__main__":
    sys.exit(main())
