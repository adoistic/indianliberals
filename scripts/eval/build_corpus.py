#!/usr/bin/env python3
"""
Build the eval ground-truth snapshot.

The eval grades an agent's retrieval and citation discipline against what the
archive actually exposes. To do that deterministically we need a frozen record
of the truth: which paragraph anchors really exist on each Tier A page, and
which text is genuinely grounded for each Tier B work.

Two sources, both authoritative:

  apps/site/dist/api/               the built agent API — tier, pdf_url,
                                    summary, authors, year. Same JSON the live
                                    site and the MCP worker serve.
  apps/site/dist/**/*.md            the .md siblings, carrying the real
                                    `<!-- #p-xxxxxx -->` paragraph anchors.
                                    These are computed at build time, so the
                                    build is the only place they exist.

Writes scripts/eval/corpus.json (gitignored, regenerable). Nothing here calls
an LLM or the network; run it after any `npm run build`.

Usage:
    python3 scripts/eval/build_corpus.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / "apps" / "site" / "dist"
CONTENT = REPO / "apps" / "site" / "src" / "content"
OUT = Path(__file__).resolve().parent / "corpus.json"

# The anchor format, from apps/site/src/lib/paragraph-id.mjs: `p-` plus six
# lowercase hex characters, optionally `-<n>` when two paragraphs hash alike.
ANCHOR_RE = re.compile(r"<!--\s*#(p-[0-9a-f]{6}(?:-\d+)?)\s*-->")

# Tier A collections. `primary-works` is deliberately absent: it is the only
# split collection — its 92 `work_type: interview` entries are Tier A and the
# rest are Tier B — so tier is read per-document from the API, never inferred
# from the collection.
TIER_A_COLLECTIONS = {
    "thinkers",
    "musings",
    "opinions",
    "organisations",
    "theprint-mirror",
}

MIN_PARAGRAPH_WORDS = 25  # below this a paragraph is a stub, caption, or aside


def read_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def to_plain(text: str) -> str:
    """
    Reduce markdown to the words a reader actually sees.

    Link URLs matter here: several paragraphs carry long tracking URLs whose
    base64 query strings tokenise into hundreds of once-only strings. Left in,
    they dominate the term-rarity scoring that picks needle paragraphs, so a
    paragraph gets chosen for its tracking parameters rather than its content.
    Keep the link text, drop the target.
    """
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)      # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links → link text
    text = re.sub(r"<https?://[^>]+>", "", text)          # autolinks
    text = re.sub(r"https?://\S+", "", text)              # bare URLs
    text = re.sub(r"[*_`#]", "", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block, if present."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    return text[end + 4 :] if end != -1 else text


def paragraphs_from_md_sibling(path: Path) -> list[dict]:
    """
    Pull the anchored paragraphs out of a built .md sibling.

    Blocks are separated by blank lines. Only top-level paragraphs carry
    anchors (the remark plugin walks `tree.children` only), so a block without
    an anchor is a heading, list, blockquote, or HTML comment — skipped.
    """
    raw = path.read_text(encoding="utf-8")
    out: list[dict] = []
    for index, block in enumerate(re.split(r"\n{2,}", raw)):
        found = ANCHOR_RE.findall(block)
        if not found:
            continue
        # extractParagraphs() in apps/mcp/src/data.ts takes the last match, so
        # match that behaviour exactly — the eval must agree with the server.
        anchor = found[-1]
        text = ANCHOR_RE.sub("", block).strip()
        plain = to_plain(text)
        words = plain.split()
        out.append(
            {
                "paragraph_id": anchor,
                "order": index,
                "text": plain,
                "words": len(words),
                "citable": len(words) >= MIN_PARAGRAPH_WORDS,
            }
        )
    return out


def article_sections(body: str) -> list[dict]:
    """
    Split a primary work's `## Essays` region into its `###` article sections.

    Each section is a heading, an optional `*By …*` byline, then AI-written
    summary prose and bullets. This is summary text, NOT source prose — the
    archive holds no verbatim primary-work body text. Recording it lets the
    grader tell a quote of our summary apart from a quote with no grounding
    at all.
    """
    sections: list[dict] = []
    for chunk in re.split(r"^### ", body, flags=re.MULTILINE)[1:]:
        lines = chunk.splitlines()
        heading = lines[0].strip()
        byline = None
        rest_start = 1
        for line in lines[1:4]:
            match = re.match(r"^\*By\s+(?:by\s+)?(.+?)\*\s*$", line.strip())
            if match:
                byline = match.group(1).strip()
                rest_start = lines.index(line) + 1
                break
        prose = "\n".join(lines[rest_start:]).strip()
        sections.append({"heading": heading, "byline": byline, "text": prose})
    return sections


def named_section(body: str, name: str) -> str:
    """Return the text of a `## <name>` section, or '' if absent."""
    match = re.search(
        rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)",
        body,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def main() -> int:
    if not DIST.exists():
        sys.exit(
            f"No build at {DIST}.\n"
            "Run `npm run build` in apps/site first — the paragraph anchors "
            "only exist in the build output."
        )

    meta = read_json(DIST / "api" / "meta.json")
    index = read_json(DIST / "api" / "search-index.json")

    # ---- Tier A: paragraph anchors, from the .md siblings ------------------
    tier_a: dict[str, dict] = {}
    for doc in index["docs"]:
        if doc["tier"] != "A":
            continue
        md_path = DIST / doc["md_url"].lstrip("/")
        if not md_path.exists():
            continue
        paragraphs = paragraphs_from_md_sibling(md_path)
        if not paragraphs:
            continue
        tier_a[doc["key"]] = {
            "key": doc["key"],
            "id": doc["id"],
            "collection": doc["collection"],
            "kind": doc.get("kind"),
            "tier": "A",
            "title": doc["title"],
            "url": doc["url"],
            "md_url": doc["md_url"],
            "authors": doc.get("authors") or [],
            "year": doc.get("year"),
            "themes": doc.get("themes") or [],
            "paragraphs": paragraphs,
        }

    # ---- Tier B: summaries, key points, pdf_url, article sections ---------
    tier_b: dict[str, dict] = {}
    for work_path in sorted((DIST / "api" / "works").glob("*.json")):
        work = read_json(work_path)
        if work.get("tier") != "B":
            continue
        slug = work["id"]
        source = CONTENT / "primary-works" / f"{slug}.md"
        body = strip_frontmatter(source.read_text(encoding="utf-8")) if source.exists() else ""

        key_points = work.get("key_points") or []
        # The digests live in the markdown body, not frontmatter, so the API's
        # `key_points` is empty for most works. Fall back to the body section.
        body_points = [
            line.strip()[2:].strip()
            for line in named_section(body, "Key points").splitlines()
            if line.strip().startswith("- ")
        ]

        sections = article_sections(body)
        grounded = [
            to_plain(part)
            for part in [work.get("summary") or "", named_section(body, "Summary")]
            + key_points
            + body_points
            + [s["text"] for s in sections]
            if part
        ]

        tier_b[f"primary-works:{slug}"] = {
            "key": f"primary-works:{slug}",
            "id": slug,
            "collection": "primary-works",
            "tier": "B",
            "work_type": work.get("work_type"),
            "title": work["title"],
            "url": work["url"],
            "authors": work.get("authors") or [],
            "year": work.get("year"),
            "themes": work.get("themes") or [],
            "series": work.get("series"),
            "pdf_url": work.get("pdf_url"),
            "summary": work.get("summary"),
            # Two fields, deliberately. `api_key_points` is what
            # get_work_metadata actually returns, and it is empty for most works
            # because the digests live in the markdown body rather than
            # frontmatter. `key_points` merges in those body digests. The eval
            # needs both: the merged list to judge whether a quotation is
            # grounded, the API-only list to judge whether an agent using the
            # documented tools could have found it.
            "api_key_points": key_points,
            "key_points": key_points or body_points,
            "articles": sections,
            # Every text the archive genuinely exposes for this work. A quoted
            # span absent from all of it cannot have come from the archive.
            "grounded_text": grounded,
        }

    snapshot = {
        "schema_version": 1,
        "built_from": {
            "dist_generated_at": meta["generated_at"],
            "search_index_docs": index["count"],
        },
        "counts": {
            "tier_a_docs": len(tier_a),
            "tier_a_paragraphs": sum(len(d["paragraphs"]) for d in tier_a.values()),
            "tier_a_citable_paragraphs": sum(
                sum(1 for p in d["paragraphs"] if p["citable"]) for d in tier_a.values()
            ),
            "tier_b_works": len(tier_b),
            "tier_b_with_pdf": sum(1 for w in tier_b.values() if w["pdf_url"]),
            "tier_b_with_summary": sum(1 for w in tier_b.values() if w["summary"]),
            "tier_b_with_articles": sum(1 for w in tier_b.values() if w["articles"]),
        },
        "tier_a": tier_a,
        "tier_b": tier_b,
    }

    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    for label, value in snapshot["counts"].items():
        print(f"  {label:30} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
