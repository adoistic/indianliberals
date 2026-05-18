"""Emit Astro content collection MD files from authority + bake-off outputs.

Targets:
- apps/site/src/content/thinkers/<id>.md       (from data/authority/thinkers.json)
- apps/site/src/content/organisations/<id>.md  (from data/authority/organisations.json)
- apps/site/src/content/primary-works/<slug>.md (from data/bake-off-output/<slug>/*.json)

Frontmatter follows the Zod schemas in apps/site/src/content.config.ts.

The body of each MD file is a "needs review" stub for now — the editorial
team will fill bio/intro content separately. The frontmatter is the
machine-tractable canonical record; the body is a placeholder that
preserves enough of the AI summary to be useful for the Sveltia editor.

Usage:
    python3 scripts/synthesis/emit-astro-md.py
    python3 scripts/synthesis/emit-astro-md.py --only-works   # skip authority
    python3 scripts/synthesis/emit-astro-md.py --slug <slug>  # one work
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUTH_DIR = ROOT / "data" / "authority"
BAKE_DIR = ROOT / "data" / "bake-off-output"
ASTRO_CONTENT = ROOT / "apps" / "site" / "src" / "content"

THINKERS_DIR = ASTRO_CONTENT / "thinkers"
ORGS_DIR = ASTRO_CONTENT / "organisations"
WORKS_DIR = ASTRO_CONTENT / "primary-works"

THINKER_TRADITIONS = {
    "classical_liberal", "reformer", "nationalist_liberal",
    "social_reformer", "contemporary_liberal", "international_influence",
}
ORG_TYPES = {
    "political_party", "think_tank", "publisher_org", "reform_society",
    "professional_body", "academic", "international_network",
}
WORK_TYPES = {
    "book", "pamphlet", "speech", "essay", "edited_volume",
    "occasional_paper", "letter", "correspondence",
    "periodical_issue", "reference",
}


def _load(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _str_val(v: Any, default: str = "") -> str:
    if isinstance(v, dict):
        return str(v.get("value") or v.get("verbatim") or default)
    return str(v if v is not None else default)


def _yaml_str(s: str) -> str:
    """Quote a string for YAML, escaping internal quotes and backslashes."""
    if s is None:
        return '""'
    s = str(s)
    if not s:
        return '""'
    # If string contains anything that needs quoting, use double quotes
    needs_quotes = any(c in s for c in ":#&*!|>'\"%@`{}[]\n\r\t") or s[0] in "-?:" or s.endswith(" ")
    if needs_quotes:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return s


def _yaml_list(items, indent: int = 0) -> str:
    """Render a YAML list. Returns inline `[]` when empty, block otherwise."""
    if not items:
        return "[]"
    out_lines = []
    pad = " " * indent
    for item in items:
        if isinstance(item, (str, int, float, bool)):
            out_lines.append(f"{pad}- {_yaml_str(str(item))}")
        elif isinstance(item, dict):
            inner = _yaml_dict(item, indent + 2)
            out_lines.append(f"{pad}- " + inner.lstrip(" ").rstrip("\n"))
        else:
            out_lines.append(f"{pad}- {_yaml_str(str(item))}")
    return "\n" + "\n".join(out_lines)


def _yaml_dict(d: dict, indent: int = 0) -> str:
    """Render a YAML dict at the given indent. Returns lines (newline-prefixed)."""
    out = []
    pad = " " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            out.append(f"{pad}{k}:")
            out.append(_yaml_dict(v, indent + 2).rstrip())
        elif isinstance(v, list):
            if not v:
                # Inline empty list must have a space after the colon, else
                # YAML parsers (js-yaml in Astro) reject it as malformed.
                out.append(f"{pad}{k}: []")
            else:
                out.append(f"{pad}{k}:{_yaml_list(v, indent + 2)}")
        elif v is None:
            out.append(f"{pad}{k}: null")
        elif isinstance(v, bool):
            out.append(f"{pad}{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            out.append(f"{pad}{k}: {v}")
        else:
            out.append(f"{pad}{k}: {_yaml_str(str(v))}")
    return "\n".join(out) + ("\n" if out else "")


def write_md(path: Path, frontmatter: dict, body: str, *, overwrite: bool = False):
    """Write an MD file with YAML frontmatter.

    By default, refuses to overwrite an existing file — hand-curated bios
    are precious and must not be clobbered. Pass overwrite=True only when
    the caller explicitly wants to replace the file (e.g., re-emitting
    a fresh extraction over a known-AI-generated placeholder).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    fm = _yaml_dict(frontmatter)
    path.write_text(f"---\n{fm}---\n\n{body}\n", encoding="utf-8")
    return True


# ─── Thinkers ────────────────────────────────────────────────────────────

def emit_thinker(entry: dict) -> Path | None:
    """Emit one thinkers/<id>.md from an authority entry."""
    tid = entry.get("id")
    if not tid:
        return None
    name_obj = entry.get("name") or {}
    tradition = entry.get("tradition") or "contemporary_liberal"
    if tradition not in THINKER_TRADITIONS:
        tradition = "contemporary_liberal"
    # Drop {value, confidence} wrappers from birth/death
    birth = entry.get("birth_year")
    death = entry.get("death_year")
    if isinstance(birth, dict): birth = birth.get("value")
    if isinstance(death, dict): death = death.get("value")
    fm = {
        "id": tid,
        "name": {
            "canonical": _str_val(name_obj.get("canonical"), tid),
            "sort": _str_val(name_obj.get("sort"), _str_val(name_obj.get("canonical"), tid)),
        },
        "tradition": tradition,
        "nationality": entry.get("nationality") or "india",
        "themes": entry.get("themes") or [],
        "affiliations": entry.get("affiliations") or [],
        "bio_source": entry.get("bio_source") or "imported",
        "needs_review": True,  # always true for AI-drafted entries
        "draft": True,
        "ai": {
            "drafted_by": "claude-sonnet-4.5",
            "drafted_at": "2026-05-17",
            "model_version": entry.get("sources", ["unknown"])[0] if entry.get("sources") else "imported",
        },
    }
    if name_obj.get("full"):
        fm["name"]["full"] = name_obj["full"]
    if name_obj.get("also_known_as"):
        fm["name"]["also_known_as"] = name_obj["also_known_as"]
    if birth is not None and isinstance(birth, int):
        fm["birth_year"] = birth
    if death is not None and isinstance(death, int):
        fm["death_year"] = death

    body = f"# {fm['name']['canonical']}\n\n*Entry pending editorial review. The AI extraction pipeline identified this person as a recurring figure in the Indian liberal corpus.*\n"
    if entry.get("sources"):
        body += f"\n**Provenance:** {', '.join(entry['sources'][:3])}\n"
    path = THINKERS_DIR / f"{tid}.md"
    wrote = write_md(path, fm, body)
    return path if wrote else None


def emit_all_thinkers():
    doc = _load(AUTH_DIR / "thinkers.json")
    if not doc:
        return 0
    n = 0
    for entry in doc.get("thinkers", []):
        if emit_thinker(entry):
            n += 1
    return n


# ─── Organisations ───────────────────────────────────────────────────────

def emit_organisation(entry: dict) -> Path | None:
    oid = entry.get("id")
    if not oid:
        return None
    name_obj = entry.get("name") or {}
    otype = entry.get("type") or "think_tank"
    if otype not in ORG_TYPES:
        otype = "think_tank"
    fm = {
        "id": oid,
        "name": {
            "canonical": _str_val(name_obj.get("canonical"), oid),
            "sort": _str_val(name_obj.get("sort"), _str_val(name_obj.get("canonical"), oid)),
        },
        "type": otype,
        "ideology": entry.get("ideology") or [],
        "needs_review": True,
        "draft": True,
    }
    if name_obj.get("full"):
        fm["name"]["full"] = name_obj["full"]
    if name_obj.get("also_known_as"):
        fm["name"]["also_known_as"] = name_obj["also_known_as"]
    founded = entry.get("founded_year")
    if isinstance(founded, dict): founded = founded.get("value")
    if isinstance(founded, int):
        fm["founded_year"] = founded
    dissolved = entry.get("dissolved_year")
    if isinstance(dissolved, dict): dissolved = dissolved.get("value")
    if isinstance(dissolved, int):
        fm["dissolved_year"] = dissolved

    body = f"# {fm['name']['canonical']}\n\n*Entry pending editorial review.*\n"
    path = ORGS_DIR / f"{oid}.md"
    wrote = write_md(path, fm, body)
    return path if wrote else None


def emit_all_organisations():
    doc = _load(AUTH_DIR / "organisations.json")
    if not doc:
        return 0
    n = 0
    for entry in doc.get("organisations", []):
        if emit_organisation(entry):
            n += 1
    return n


# ─── Primary works ───────────────────────────────────────────────────────

def slug_to_work_id(slug: str) -> str:
    """Convert filesystem slug to a content collection ID."""
    # Drop any extension; collapse spaces/non-alnum to hyphens.
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug).strip("-").lower()
    return s


def emit_primary_work(slug: str) -> Path | None:
    """Emit primary-works/<slug>.md from bake-off-output/<slug>/{metadata,summary}.json."""
    sub = BAKE_DIR / slug
    if not sub.is_dir():
        return None
    # Prefer the most-validated metadata
    meta = None
    for fname in ("metadata.a.a.json", "metadata.b.b.json", "metadata.a.json", "metadata.b.json"):
        m = _load(sub / fname)
        if m:
            meta = m
            break
    if meta is None:
        return None
    # Prefer final.json (continuation-merged) over plain summary
    summ = _load(sub / "final.json") or _load(sub / "summary.json") or {}

    work_id = slug_to_work_id(slug)
    title_obj = meta.get("title") or {}
    title_main = _str_val(title_obj.get("main"), slug)
    title_fm = {"main": title_main}
    if title_obj.get("subtitle"):
        title_fm["subtitle"] = _str_val(title_obj.get("subtitle"))
    if title_obj.get("original_script"):
        title_fm["original_script"] = title_obj["original_script"]
    if title_obj.get("translit"):
        title_fm["translit"] = title_obj["translit"]

    wt = meta.get("work_type")
    if wt not in WORK_TYPES:
        wt = "book"  # fallback for unrecognised work_types

    pub = meta.get("publication") or {}
    pub_fm = {
        "language": pub.get("language") or meta.get("language") or "en",
    }
    if pub.get("publisher_id"): pub_fm["publisher_id"] = pub["publisher_id"]
    if pub.get("publisher_verbatim"): pub_fm["publisher_name"] = pub["publisher_verbatim"]
    if pub.get("issuer_id"): pub_fm["issuer_id"] = pub["issuer_id"]
    if pub.get("place"): pub_fm["place"] = pub["place"]
    year = pub.get("year")
    if isinstance(year, dict): year = year.get("value")
    if isinstance(year, int): pub_fm["year"] = year
    if pub.get("edition"): pub_fm["edition"] = _str_val(pub["edition"])
    if pub.get("series"): pub_fm["series"] = _str_val(pub["series"])

    # Authors / contributors: resolve byline_verbatim → thinker_id against
    # the cleaned authority byline_lookup at emit time. Without this the
    # `authors[]` array stays empty for any work whose extraction-time
    # resolver didn't catch the byline (most of the corpus). The thinker
    # bio page's "Works in the archive" section depends on this.
    bl = _byline_lookup()

    def _resolve(byline_verbatim: str | None) -> str | None:
        if not byline_verbatim:
            return None
        # Strip trailing honorific / qualification suffixes BEFORE
        # normalising. The metadata routinely carries strings like
        # "N. Vittal IAS (Retd.)", "C. S. Seshadri, I.A.S. (Retd.)",
        # "M. R. Pai, Esq.", "Dr. Y. V. Reddy, M.P.". These won't match
        # the clean canonical "N. Vittal" in byline_lookup unless we
        # strip the suffix first.
        bv = byline_verbatim
        bv = re.sub(r"\s*\([^)]+\)\s*$", "", bv)         # drop trailing (Retd.) etc.
        bv = re.sub(r",?\s*(I\.?A\.?S\.?|I\.?C\.?S\.?|I\.?F\.?S\.?|I\.?P\.?S\.?|I\.?R\.?S\.?|M\.?P\.?|M\.?L\.?A\.?|Esq\.?|Jr\.?|Sr\.?|Ph\.?\s*D\.?)\s*$", "", bv, flags=re.I)
        bv = bv.strip(" ,.").strip()
        n = _normalise_byline(bv)
        if not n:
            return None
        if n in bl:
            return bl[n]
        n2 = re.sub(r"^(prof|dr|mr|mrs|ms|shri|sri|sir|justice|lord|lady|pandit|acharya)\s+", "", n)
        if n2 in bl:
            return bl[n2]
        # Final attempt: try the byline_verbatim WITH common honorifics stripped
        # from anywhere
        n3 = re.sub(r"\b(prof|dr|mr|mrs|ms|sir|justice|lord|lady|sri|shri|pandit|acharya|the late)\b\.?\s*", " ", n).strip()
        n3 = re.sub(r"\s+", " ", n3)
        return bl.get(n3)

    authors: list[str] = []
    for a in (meta.get("authors") or []):
        if not isinstance(a, dict):
            continue
        tid = a.get("thinker_id") or _resolve(a.get("byline_verbatim"))
        if tid and tid not in authors:
            authors.append(tid)

    editors: list[str] = []
    for e in (meta.get("editors") or []):
        if not isinstance(e, dict):
            continue
        tid = e.get("thinker_id") or _resolve(e.get("byline_verbatim"))
        if tid and tid not in editors:
            editors.append(tid)

    contribs: list[dict] = []
    for c in (meta.get("contributors") or []):
        if not isinstance(c, dict):
            continue
        item: dict = {"role": c.get("role") or "author"}
        tid = c.get("thinker_id") or _resolve(c.get("byline_verbatim"))
        if tid:
            item["thinker"] = tid
            # Promote 'author' contributors into the top-level authors[] too,
            # so the thinker bio page's "Works in the archive" cross-list
            # populates without depending on the extraction's authors[] field
            # (which is often empty even when contributors[] is rich).
            if item["role"] == "author" and tid not in authors:
                authors.append(tid)
        elif c.get("byline_verbatim"):
            item["thinker_unresolved"] = c["byline_verbatim"]
        if c.get("toc_index") is not None:
            item["toc_index"] = c["toc_index"]
        contribs.append(item)

    fm = {
        "id": work_id,
        "title": title_fm,
        "work_type": wt,
        "authors": authors,
        "editors": editors,
        "contributors": contribs,
        "publication": pub_fm,
        "provenance": {
            "source": "ccs_archive",
            "scan_quality": "unknown",
        },
        "rights": {
            # Schema requires `status` (enum); the legacy `license`/`license_url`/
            # `rights_statement` keys are preserved for backwards compat but the
            # Zod gate is on `status`. takedown_on_request is the conservative
            # default for in-copyright works hosted under archival access;
            # editorial can re-classify per-work in Sveltia later.
            "status": "takedown_on_request",
            "license": "in-copyright",
            "license_url": None,
            "rights_statement": "Rights held by original publishers / Centre for Civil Society; reproduced for archival access.",
        },
        "themes": meta.get("themes") or [],
        "summary": _short_summary(summ),
        # needs_review remains true: this is the editorial signal that an
        # entry is AI-extracted and hasn't had a human-reviewed pass yet.
        # Sveltia surfaces "needs_review: true" entries to editors first.
        "needs_review": True,
        # draft stays FALSE: Tier B primary works ship publicly with the
        # "metadata is AI-extracted, under editorial review" disclaimer
        # rendered on the detail page. Hiding 900+ entries behind a
        # manual review gate would make the corpus invisible at launch.
        "draft": False,
        "ai": {
            "drafted_by": "claude-sonnet-4.5",
            "drafted_at": "2026-05-17",
            "model_version": (meta.get("_validator") or {}).get("version", "v1.4"),
        },
    }
    if meta.get("purpose"):
        fm["purpose"] = meta["purpose"]
    phys = meta.get("physical") or {}
    if phys:
        phys_fm = {}
        for k in ("page_count", "page_count_visible", "pages_rendered", "pages_total", "pages_total_source", "format"):
            v = phys.get(k)
            if v is not None and not isinstance(v, dict):
                phys_fm[k] = v
        if phys_fm:
            fm["physical"] = phys_fm
    if meta.get("missing_metadata_flags"):
        fm["missing_metadata_flags"] = meta["missing_metadata_flags"]

    body = _work_body_md(meta, summ)
    path = WORKS_DIR / f"{work_id}.md"
    # Primary-works are 100% machine-emitted from bake-off-output. They have
    # no hand-curated bodies to protect — overwriting is the correct policy
    # so re-running this script after a metadata/body fix actually updates
    # the rendered file. (Hand-curated thinkers + organisations stay
    # protected because their emit fns use the default overwrite=False.)
    wrote = write_md(path, fm, body, overwrite=True)
    return path if wrote else None


# Cached byline lookup: normalised byline → thinker_id. Lazy-loaded from the
# authority file on first use. Used by emit_primary_work to resolve any
# contributor whose extraction-time resolver came up empty.
_BYLINE_LOOKUP_CACHE: dict[str, str] | None = None


def _byline_lookup() -> dict[str, str]:
    global _BYLINE_LOOKUP_CACHE
    if _BYLINE_LOOKUP_CACHE is None:
        doc = _load(AUTH_DIR / "thinkers.json") or {}
        _BYLINE_LOOKUP_CACHE = dict(doc.get("byline_lookup", {}))
    return _BYLINE_LOOKUP_CACHE


def _normalise_byline(s: str) -> str:
    """Match the byline_lookup normalisation: lowercase, drop punct/honorifics
    that the authority strips during lookup-key generation."""
    s = s.lower().replace(".", " ").replace(",", " ").replace("-", " ").replace("'", "").replace("’", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Cached thinker name lookup: slug → canonical name. Lazy-loaded on first use.
_THINKER_NAME_CACHE: dict[str, str] | None = None


def _thinker_name(slug: str | None) -> str | None:
    """Resolve a thinker slug to its canonical display name. Returns None if
    the slug isn't in the authority file (caller should fall back to the
    verbatim byline string)."""
    global _THINKER_NAME_CACHE
    if not slug:
        return None
    if _THINKER_NAME_CACHE is None:
        doc = _load(AUTH_DIR / "thinkers.json") or {}
        _THINKER_NAME_CACHE = {}
        for t in doc.get("thinkers", []):
            name = t.get("name", {})
            canonical = name.get("canonical") or name.get("full") or t.get("id")
            if t.get("id") and canonical:
                _THINKER_NAME_CACHE[t["id"]] = canonical
    return _THINKER_NAME_CACHE.get(slug)


def _short_summary(summ: dict) -> str:
    """Extract a prose summary (volume_summary or summary) for the frontmatter
    `summary` field. Used for og:description previews + Pagefind index entry;
    NOT shown to humans on the detail page (that renders the full body). A
    1200-char soft cap keeps the og:description reasonable; longer summaries
    are truncated at a sentence boundary with an ellipsis."""
    if not summ:
        return ""
    text = summ.get("volume_summary") or summ.get("summary") or ""
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    if len(text) > 1200:
        # Snap to the last sentence end before 1200 to avoid mid-word cuts
        cut = text.rfind(". ", 0, 1200)
        if cut < 600:
            cut = 1197
        text = text[: cut + 1] + "…"
    return text


def _work_body_md(meta: dict, summ: dict) -> str:
    """Generate the MD body — prose summary, key points, per-essay summaries.

    The body is what's rendered to humans on the detail page (the page's
    frontmatter `summary` is for og:description / Pagefind only). So we
    emit FULL summaries here, not truncated previews."""
    title = _str_val((meta.get("title") or {}).get("main"), "Untitled")
    lines = [f"# {title}\n"]

    # Authors line — resolve slugs to canonical names where possible.
    authors = meta.get("authors") or []
    if authors:
        names = []
        for a in authors:
            if not isinstance(a, dict):
                continue
            tid = a.get("thinker_id") or a.get("id")
            byline = a.get("byline_verbatim")
            label = _thinker_name(tid) or byline or tid or "?"
            names.append(label)
        if names:
            lines.append(f"*By {', '.join(names)}*\n")

    # Summary prose — full text, not truncated.
    text = summ.get("volume_summary") or summ.get("summary") or ""
    if isinstance(text, str) and text.strip():
        lines.append("## Summary\n")
        lines.append(text.strip() + "\n")

    # Key points (single-author shape)
    ss = summ.get("summary_structured") or {}
    kps = ss.get("key_points") or []
    if kps:
        lines.append("## Key points\n")
        for kp in kps:
            text = kp if isinstance(kp, str) else (kp.get("text") or "")
            if text:
                lines.append(f"- {text}\n")
        lines.append("")

    # Per-essay summaries (multi-author shape) — join essay summaries to TOC
    # entries by `toc_index` to get the real essay title + byline. Without
    # the join the body shows "Essay (toc 1)" + the author slug ("b-r-shenoy")
    # instead of "Whither Indian Planning?" + "Sir H. P. Mody".
    essays = summ.get("essays_summarized") or []
    toc_entries = (meta.get("toc") or {}).get("entries") or []
    toc_by_index = {te.get("toc_index"): te for te in toc_entries if isinstance(te, dict)}

    if essays:
        lines.append("## Essays\n")
        for e in essays:
            if not isinstance(e, dict):
                continue
            ti = e.get("toc_index")
            ess_ss = e.get("summary_structured") or {}
            te = toc_by_index.get(ti) or {}

            # Title: prefer essay payload's own title, then TOC title, then a
            # last-resort label noting which TOC entry this is.
            etitle = e.get("title") or te.get("title") or f"Essay {ti}" if ti is not None else "Essay"

            # Byline: try essay's author_resolved (a slug), then resolve via
            # authority for the canonical display name. Fall back to the TOC
            # entry's byline_verbatim (the as-printed name).
            author_slug = e.get("author_resolved")
            if isinstance(author_slug, dict):
                author_slug = author_slug.get("thinker_id") or author_slug.get("id")
            author_label = (
                _thinker_name(author_slug)
                or te.get("byline_verbatim")
                or e.get("author_unresolved")
                or ""
            )

            lines.append(f"### {etitle}")
            if author_label:
                lines.append(f"*By {author_label}*\n")

            # FULL essay summary — no mid-essay truncation.
            ess_summary = e.get("summary") or ""
            if ess_summary:
                lines.append(ess_summary.strip() + "\n")

            # All key points, not just 3.
            for kp in (ess_ss.get("key_points") or []):
                text = kp if isinstance(kp, str) else (kp.get("text") or "")
                if text:
                    lines.append(f"- {text}")
            lines.append("")

    lines.append("\n---\n\n*Generated by the v1.5 extraction pipeline. Awaiting editorial review.*\n")
    return "\n".join(lines)


# ─── Driver ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-works", action="store_true", help="Skip authority refresh; only re-emit primary-works")
    ap.add_argument("--only-authority", action="store_true", help="Only emit thinkers + organisations")
    ap.add_argument("--slug", help="Emit one specific work_slug (use full directory name from bake-off-output/)")
    args = ap.parse_args()

    if args.slug:
        path = emit_primary_work(args.slug)
        print(f"Wrote: {path}" if path else f"No data found for slug: {args.slug}")
        return

    if not args.only_works:
        n_thinkers = emit_all_thinkers()
        n_orgs = emit_all_organisations()
        print(f"Authority: {n_thinkers} thinkers, {n_orgs} organisations emitted")

    if not args.only_authority:
        n_works = 0
        for sub in sorted(BAKE_DIR.iterdir()):
            if sub.is_dir():
                p = emit_primary_work(sub.name)
                if p:
                    n_works += 1
        print(f"Primary works: {n_works} emitted")


if __name__ == "__main__":
    main()
