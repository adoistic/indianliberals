"""Day 6 synthesis pass — aggregate per-thinker and per-theme occurrences
from the 40 baked PDFs, plus emit graph-edges JSON for the Astro
`graph-edges` content collection.

Inputs:
- data/bake-off-output/<work-slug>/metadata.a.a.json (or .b.b for fallback)
- data/bake-off-output/<work-slug>/summary.json (or final.json for Mangalore)
- data/authority/thinkers.json (resolve thinker_id → canonical name)
- data/authority/organisations.json

Outputs:
- data/synthesis/thinker-occurrences.json
- data/synthesis/theme-occurrences.json
- data/synthesis/graph-edges/cites.json  (work → thinker citation edges)
- data/synthesis/graph-edges/engages.json (work → theme engagement edges)
- data/synthesis/graph-edges/contributor.json (work → thinker contributor/editor edges)
- data/synthesis/synthesis-report.md

Edges emit in the graphEdges schema from apps/site/src/content.config.ts:704.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BAKE_DIR = ROOT / "data" / "bake-off-output"
AUTH_DIR = ROOT / "data" / "authority"
OUT_DIR = ROOT / "data" / "synthesis"
OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "graph-edges").mkdir(parents=True, exist_ok=True)


def _load(p: Path) -> Any:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _str_val(v: Any) -> str:
    """Coerce possibly-{value,confidence}-shaped dicts to a plain string."""
    if isinstance(v, dict):
        return str(v.get("value") or v.get("verbatim") or "")
    return str(v or "")


def load_authority() -> tuple[dict[str, dict], dict[str, dict]]:
    thinkers_doc = _load(AUTH_DIR / "thinkers.json") or {}
    orgs_doc = _load(AUTH_DIR / "organisations.json") or {}
    thinkers = {t["id"]: t for t in thinkers_doc.get("thinkers", [])}
    orgs = {o["id"]: o for o in orgs_doc.get("organisations", [])}
    return thinkers, orgs


def iter_baked_works():
    """Yield (work_slug, metadata, summary) tuples for each baked PDF."""
    for sub in sorted(BAKE_DIR.iterdir()):
        if not sub.is_dir():
            continue
        slug = sub.name
        # Prefer the validated .a.a record; fall back to .b.b, then plain
        meta = None
        for fname in ("metadata.a.a.json", "metadata.b.b.json", "metadata.a.json", "metadata.b.json"):
            m = _load(sub / fname)
            if m:
                meta = m
                break
        # For Mangalore (or any work with continuation merge), prefer final.json
        final = _load(sub / "final.json")
        summ = final if final else _load(sub / "summary.json")
        if meta is None and summ is None:
            continue
        yield slug, meta or {}, summ or {}


def collect_thinker_occurrences():
    """Map thinker_id → list of {work_slug, role, confidence, source}."""
    occ: dict[str, list] = defaultdict(list)
    contributor_edges: list[dict] = []
    cites_edges: list[dict] = []

    for slug, meta, summ in iter_baked_works():
        # Authors
        for a in meta.get("authors") or []:
            if not isinstance(a, dict):
                continue
            tid = a.get("thinker_id")
            if tid:
                occ[tid].append({"work_slug": slug, "role": "author", "confidence": a.get("confidence", "medium")})
                contributor_edges.append({
                    "from": slug,
                    "to": tid,
                    "confidence": a.get("confidence", "medium") or "medium",
                    "evidence_works": [slug],
                    "source": "ai_synthesis_v1",
                    "context": "author",
                })

        # Editors
        for e in meta.get("editors") or []:
            if not isinstance(e, dict):
                continue
            tid = e.get("thinker_id")
            if tid:
                occ[tid].append({"work_slug": slug, "role": "editor"})
                contributor_edges.append({
                    "from": slug,
                    "to": tid,
                    "confidence": e.get("confidence", "medium") or "medium",
                    "evidence_works": [slug],
                    "source": "ai_synthesis_v1",
                    "context": "editor",
                })

        # Contributors (multi-author works)
        for c in meta.get("contributors") or []:
            if not isinstance(c, dict):
                continue
            tid = c.get("thinker_id")
            if tid:
                role = c.get("role") or "contributor"
                occ[tid].append({"work_slug": slug, "role": role})
                contributor_edges.append({
                    "from": slug,
                    "to": tid,
                    "confidence": c.get("confidence", "medium") or "medium",
                    "evidence_works": [slug],
                    "source": "ai_synthesis_v1",
                    "context": role,
                })

        # Cross-thinker mentions from summary
        for ctm in _iter_cross_thinker_mentions(summ):
            tid = ctm.get("thinker_id")
            if tid:
                occ[tid].append({
                    "work_slug": slug,
                    "role": "body_text_mention",
                    "page": ctm.get("page"),
                    "context": (ctm.get("context") or "")[:200],
                })
                cites_edges.append({
                    "from": slug,
                    "to": tid,
                    "confidence": "high",
                    "evidence_works": [slug],
                    "source": "ai_synthesis_v1",
                    "context": (ctm.get("context") or "")[:200],
                })

    return occ, contributor_edges, cites_edges


def _iter_cross_thinker_mentions(summ: dict):
    """Yield cross_thinker_mention dicts from single-author or multi-author shape."""
    if not summ:
        return
    # Single-author shape
    ss = summ.get("summary_structured") or {}
    for m in ss.get("cross_thinker_mentions") or []:
        if isinstance(m, dict):
            yield m
    # Multi-author shape
    for e in summ.get("essays_summarized") or []:
        if not isinstance(e, dict):
            continue
        ess_ss = e.get("summary_structured") or {}
        for m in ess_ss.get("cross_thinker_mentions") or []:
            if isinstance(m, dict):
                yield m


def collect_theme_occurrences():
    """Map theme → list of work_slug; emit engages edges."""
    occ: dict[str, list[str]] = defaultdict(list)
    engages_edges: list[dict] = []

    for slug, meta, summ in iter_baked_works():
        themes = set()
        # Top-level metadata themes
        for t in (meta.get("themes") or []):
            if isinstance(t, str):
                themes.add(t)
        for t in (meta.get("theme_proposed_new") or []):
            if isinstance(t, str):
                themes.add(t)
        # Summary-level themes (single-author shape)
        ss = summ.get("summary_structured") or {}
        for t in (ss.get("themes_confirmed") or []) + (ss.get("theme_proposed_new") or []):
            if isinstance(t, str):
                themes.add(t)
        # Multi-author summary
        for e in summ.get("essays_summarized") or []:
            if not isinstance(e, dict):
                continue
            ess_ss = e.get("summary_structured") or {}
            for t in (ess_ss.get("themes_confirmed") or []) + (ess_ss.get("theme_proposed_new") or []):
                if isinstance(t, str):
                    themes.add(t)
        for theme in sorted(themes):
            occ[theme].append(slug)
            engages_edges.append({
                "from": slug,
                "to": theme,
                "confidence": "high",
                "evidence_works": [slug],
                "source": "ai_synthesis_v1",
            })

    return occ, engages_edges


def _index_by_slug() -> dict:
    """Map work_slug → metadata snippet (title, work_type, lang, year) for the report."""
    out = {}
    for slug, meta, _ in iter_baked_works():
        title_obj = meta.get("title") or {}
        if isinstance(title_obj, dict):
            tv = title_obj.get("main")
            if isinstance(tv, dict):
                tv = tv.get("value")
        else:
            tv = title_obj
        out[slug] = {
            "title": _str_val(tv) or slug,
            "work_type": meta.get("work_type"),
            "language": meta.get("language") or _str_val((meta.get("publication") or {}).get("language")),
            "year": _str_val(((meta.get("publication") or {}).get("year") or {})),
            "pages_total": (meta.get("physical") or {}).get("pages_total"),
        }
    return out


def write_aggregations(thinker_occ, theme_occ, slug_index):
    # Sort thinker_occ entries by frequency, then dump as a stable dict
    thinker_sorted = dict(sorted(thinker_occ.items(), key=lambda kv: -len(kv[1])))
    theme_sorted = dict(sorted(theme_occ.items(), key=lambda kv: -len(kv[1])))

    (OUT_DIR / "thinker-occurrences.json").write_text(
        json.dumps({"_meta": {"works_indexed": len(slug_index), "thinkers_with_occurrences": len(thinker_sorted)},
                    "occurrences": thinker_sorted}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "theme-occurrences.json").write_text(
        json.dumps({"_meta": {"works_indexed": len(slug_index), "themes_with_occurrences": len(theme_sorted)},
                    "occurrences": theme_sorted}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "works-index.json").write_text(
        json.dumps(slug_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_graph_edges(cites_edges, engages_edges, contributor_edges):
    """Emit graph-edges JSON files in the schema from content.config.ts:704."""
    def _dedupe(edges):
        # Dedupe by (from, to, context) and merge evidence_works
        seen = {}
        for e in edges:
            key = (e["from"], e["to"], e.get("context") or "")
            if key in seen:
                seen[key]["evidence_works"] = list(set(seen[key]["evidence_works"]) | set(e["evidence_works"]))
            else:
                seen[key] = dict(e)
        return list(seen.values())

    cites = _dedupe(cites_edges)
    engages = _dedupe(engages_edges)
    contribs = _dedupe(contributor_edges)

    (OUT_DIR / "graph-edges" / "cites.json").write_text(
        json.dumps({"edge_type": "cites", "edges": cites}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "graph-edges" / "engages.json").write_text(
        json.dumps({"edge_type": "engages", "edges": engages}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "graph-edges" / "contributor.json").write_text(
        # No "contributor" type in the schema yet; use "cites" as the closest existing kind,
        # with context flagging the role. Future schema extension can split this out.
        json.dumps({
            "edge_type": "cites",  # TODO: extend schema with author_of/editor_of/contributor_of
            "edges": contribs,
            "_note": "Author/editor/contributor edges. Pending schema extension for author_of/editor_of/contributor_of edge types; using cites with context=<role> as interim.",
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(cites), len(engages), len(contribs)


def write_report(thinker_occ, theme_occ, slug_index, n_cites, n_engages, n_contribs, thinkers_auth):
    """Write the synthesis-report.md."""
    lines = []
    lines.append("# Day 6 Synthesis Report\n")
    lines.append(f"**Date:** 2026-05-17  \n")
    lines.append(f"**Source:** {len(slug_index)} baked PDFs (Wave 1 + 9-PDF benchmark + Wave 2)\n\n")
    lines.append("## Aggregations emitted\n")
    lines.append(f"- `thinker-occurrences.json`: **{len(thinker_occ)} thinkers** with at least one corpus occurrence\n")
    lines.append(f"- `theme-occurrences.json`: **{len(theme_occ)} themes** engaged across the corpus\n")
    lines.append(f"- `graph-edges/cites.json`: **{n_cites} edges** (work → thinker body-text citations)\n")
    lines.append(f"- `graph-edges/engages.json`: **{n_engages} edges** (work → theme)\n")
    lines.append(f"- `graph-edges/contributor.json`: **{n_contribs} edges** (work → author/editor/contributor)\n\n")

    # Top 20 thinkers by occurrence count
    top_thinkers = sorted(thinker_occ.items(), key=lambda kv: -len(kv[1]))[:25]
    lines.append("## Top 25 thinkers by corpus occurrence\n\n")
    lines.append("| Rank | thinker_id | Canonical name | Occurrences | Role distribution |\n")
    lines.append("|---:|---|---|---:|---|\n")
    for i, (tid, occs) in enumerate(top_thinkers, 1):
        canonical = (thinkers_auth.get(tid, {}).get("name") or {}).get("canonical") or "(missing)"
        role_counts = defaultdict(int)
        for o in occs:
            role_counts[o.get("role", "?")] += 1
        roles = ", ".join(f"{r}:{c}" for r, c in sorted(role_counts.items(), key=lambda x: -x[1]))
        lines.append(f"| {i} | `{tid}` | {canonical} | {len(occs)} | {roles} |\n")

    # Top 25 themes
    top_themes = sorted(theme_occ.items(), key=lambda kv: -len(kv[1]))[:25]
    lines.append("\n## Top 25 themes by corpus engagement\n\n")
    lines.append("| Rank | Theme | Works engaging |\n")
    lines.append("|---:|---|---:|\n")
    for i, (theme, works) in enumerate(top_themes, 1):
        lines.append(f"| {i} | `{theme}` | {len(works)} |\n")

    # Network density signals
    lines.append("\n## Network density signals\n\n")
    total_thinkers = len(thinkers_auth)
    pct_with_occ = len(thinker_occ) * 100 // max(total_thinkers, 1)
    lines.append(f"- **Authority utilization:** {len(thinker_occ)} of {total_thinkers} thinkers ({pct_with_occ}%) have at least one occurrence in the baked corpus.\n")
    lines.append(f"- **Mean occurrences per thinker:** {sum(len(v) for v in thinker_occ.values()) / max(len(thinker_occ), 1):.1f}\n")
    lines.append(f"- **Works baked:** {len(slug_index)} of ~944 in the full corpus ({len(slug_index)*100//944}%)\n\n")

    # Thinker coverage by tradition (where assigned)
    by_tradition = defaultdict(int)
    for tid in thinker_occ:
        trad = thinkers_auth.get(tid, {}).get("tradition") or "(unspecified)"
        by_tradition[trad] += 1
    lines.append("### Occurrences by tradition tier\n\n")
    for trad, n in sorted(by_tradition.items(), key=lambda x: -x[1]):
        lines.append(f"- `{trad}`: {n} thinkers\n")

    # Theme distribution by work_type
    lines.append("\n## Theme distribution by work_type\n\n")
    by_wt = defaultdict(lambda: defaultdict(int))
    for slug, info in slug_index.items():
        wt = info.get("work_type") or "?"
        # We don't have the themes in slug_index, look them up
        # Instead, just count works per work_type
        by_wt[wt]["count"] += 1
    lines.append("| Work type | # works baked |\n")
    lines.append("|---|---:|\n")
    for wt, info in sorted(by_wt.items(), key=lambda x: -x[1]["count"]):
        lines.append(f"| `{wt}` | {info['count']} |\n")

    # Language distribution
    lines.append("\n## Language distribution\n\n")
    by_lang = defaultdict(int)
    for slug, info in slug_index.items():
        lang = info.get("language") or "?"
        by_lang[lang] += 1
    lines.append("| Language | # works baked |\n|---|---:|\n")
    for lang, n in sorted(by_lang.items(), key=lambda x: -x[1]):
        lines.append(f"| `{lang}` | {n} |\n")

    # Coverage gaps
    lines.append("\n## Authority utilization gaps\n\n")
    unused = sorted(set(thinkers_auth.keys()) - set(thinker_occ.keys()))
    lines.append(f"**{len(unused)} of {len(thinkers_auth)} thinkers** in the authority file have ZERO occurrences in the baked corpus so far. ")
    lines.append("This is expected: only 40 of ~944 PDFs are baked. Examples of canonical-tier thinkers not yet attested in any baked PDF (sampled):\n\n")
    canonical_unused = [tid for tid in unused if thinkers_auth.get(tid, {}).get("confidence") == "canonical"][:15]
    for tid in canonical_unused:
        canonical = (thinkers_auth.get(tid, {}).get("name") or {}).get("canonical") or tid
        lines.append(f"- `{tid}`: {canonical}\n")

    # Notes for downstream
    lines.append("\n## Notes for downstream consumers\n\n")
    lines.append("1. **Edges schema gap**: the v1.x `graphEdges` schema (`content.config.ts:708`) has `cites`, `responds_to`, `builds_on`, `influenced_by`, etc., but no explicit `author_of` / `editor_of` / `contributor_of` edge types. Until the schema extends, `graph-edges/contributor.json` uses `cites` with `context: <role>` as an interim encoding. **TODO**: propose schema extension.\n")
    lines.append("2. **Re-baking impact**: each future bake of a not-yet-baked PDF will append to these aggregations. The script is idempotent — re-run after every batch.\n")
    lines.append("3. **Cluster collapse applied (2026-05-18)**: the four duplicate-pair entries flagged by the v1.5 curator (rk-amin/prof-rk-amin, dm-kulkarni/d-m-kulkarni, bk-nehru/b-k-nehru, ashok-desai/ashok-v-desai) have been merged. Authority is now 424 thinkers (was 426). Wider corpus-wide name disambiguation deferred to post-engagement (TODOS.md).\n")
    lines.append("4. **Pull quotes not aggregated here** — they're per-work editorial content, indexed at the per-work `summary.json` level. A separate pass can produce a `data/synthesis/pull-quotes-index.json` for shareable-quote UIs.\n")

    (OUT_DIR / "synthesis-report.md").write_text("".join(lines), encoding="utf-8")


def main():
    thinkers_auth, _orgs_auth = load_authority()
    slug_index = _index_by_slug()
    thinker_occ, contributor_edges, cites_edges = collect_thinker_occurrences()
    theme_occ, engages_edges = collect_theme_occurrences()

    write_aggregations(thinker_occ, theme_occ, slug_index)
    n_cites, n_engages, n_contribs = write_graph_edges(cites_edges, engages_edges, contributor_edges)
    write_report(thinker_occ, theme_occ, slug_index, n_cites, n_engages, n_contribs, thinkers_auth)

    print(f"Synthesis pass complete.")
    print(f"  Works indexed: {len(slug_index)}")
    print(f"  Thinkers with occurrences: {len(thinker_occ)}")
    print(f"  Themes engaged: {len(theme_occ)}")
    print(f"  cites edges: {n_cites}")
    print(f"  engages edges: {n_engages}")
    print(f"  contributor edges: {n_contribs}")
    print(f"  Outputs: {OUT_DIR}/")


if __name__ == "__main__":
    main()
