# Architecture

The build follows the Falsafa / Liberty Lighthouse template — a static site over content collections with an AI/agent layer on top — adapted for a heterogeneous Indian liberal corpus whose primary works are PDFs of variable OCR quality.

## High-level diagram

```
                          ┌──────────────────────────────┐
                          │      indianliberals.in       │
                          │   (Astro, Cloudflare Pages)  │
                          └──────────────┬───────────────┘
                                         │
                ┌────────────────────────┼────────────────────────┐
                │                        │                        │
        ┌───────▼────────┐      ┌────────▼────────┐      ┌────────▼─────────┐
        │   Tier A       │      │    Tier B        │      │  External feed   │
        │   (clean)      │      │  (primary works) │      │  (ThePrint)      │
        │  Markdown,     │      │  Metadata +      │      │  RSS → markdown  │
        │  Pagefind,     │      │  AI summary +    │      │  mirror at       │
        │  paragraph IDs │      │  pdf.js viewer   │      │  /external/      │
        └────────────────┘      └────────┬─────────┘      └──────────────────┘
                                         │
                          ┌──────────────▼───────────────┐
                          │   PDFs in Cloudflare R2      │
                          │   (zero-egress storage)      │
                          └──────────────────────────────┘

                          ┌──────────────────────────────┐
                          │   mcp.indianliberals.in      │
                          │   (Node service on Workers)  │
                          │   8 tools: list_works,       │
                          │   list_thinkers,             │
                          │   get_work_metadata,         │
                          │   read_clean_content,        │
                          │   get_passage, search_corpus,│
                          │   find_related, read_index   │
                          └──────────────┬───────────────┘
                                         │ reads
                          ┌──────────────▼───────────────┐
                          │   /content collections +     │
                          │   manifests + .md siblings   │
                          └──────────────────────────────┘
```

## Two-tier model

The defining architectural decision. Bad OCR plus LLM retrieval produces confidently garbled citations — worse than no retrieval at all. The honest path is to expose what we trust now and link out to the PDF for the rest.

- **Tier A — clean content.** Musings, opinion pieces, interviews, thinker profiles, organisation pages, and the ThePrint mirror. Already-clean markdown. Full-text searchable via Pagefind, paragraph-stable IDs (`#p-xxxxxx`), deep-link citable. Agents may quote freely with citation.
- **Tier B — primary works and periodicals.** PDF in R2, metadata + AI summary + AI key points + themes + classification + author normalisation in `works.json`. Agents must summary-attribute and link out to the PDF for the underlying claim. Paragraph IDs and full-text search inside primary works are deferred to a future engagement, when vision-language layout reconstruction matures enough to clear editorial review.

Promotion hooks for Tier B → Tier A are designed into the schema now (nullable `paragraph_ids[]` and `clean_markdown_url` fields), so promotion in 18 months is a data update, not a schema migration.

## AI/agent layer

Every HTML URL has a `.md` sibling. `/llms.txt` is the curated index (llms.txt spec). `/llms-full.txt` holds every Tier-A content kind in full plus every Tier-B summary, in one file. `/AGENTS.md` documents the schema, citation rules, and tier system for autonomous agents. `/SKILL.md` is the manual fallback for Claude users without an MCP client.

The MCP server is a thin Node service on Cloudflare Workers. It exposes eight tools that return text and structure — no LLM inside. The host model (whichever the user runs in Claude Desktop, Cursor, Codex, or a browser) does the reasoning. Tools are scoped to what v1 can answer well; `read_primary_work` and `get_primary_work_passage` arrive in the future engagement when paragraph IDs land on primary works.

## Why no vector database

The corpus fits in a build artifact. Pagefind + structured metadata + the `.md` siblings give agents everything similarity search would, plus the structure (work → chapter → paragraph, plus authored metadata) that similarity search would flatten into noise. And citations need to resolve to paragraphs, not chunks, so a reader can follow the trail back. Every model improvement upstream lifts the site at no cost.

See [Karpathy's LLM-as-Wiki gist](https://gist.github.com/karpathy/9b7dbe0f57c8edf25f3c4b07f04fb33b) and the [Falsafa thesis page](https://falsafa.ai/thesis) for the methodological precedent.

## Phased delivery

1. **Phase 0 — Audit and extraction.** WordPress URL inventory, librarian schema (`SCHEMA.md`), AI extraction pipeline (`scripts/`), manifests (`works.json`, `thinkers.json`, `organisations.json`).
2. **Phase 1 — Site skeleton + clean content.** Astro scaffold, Sveltia CMS, base design system, Tier A migration, multilingual support, deploy to Cloudflare.
3. **Phase 2a — Tier B ingest + agent layer.** Per-work pages, per-thinker aggregation, `.md` siblings, `/llms.txt`, `/AGENTS.md`, MCP server.
4. **Phase 2b — ThePrint federation.** RSS ingest, markdown mirror, TF-IDF cross-links.
5. **Phase 3 — Evaluation and launch.** 200-question eval pool, deterministic substring + structured-citation check, published at `/eval`, editor onboarding, DNS cutover, three-month support window.

## Deferred to a future engagement

- Layout reconstruction of primary-work PDFs via vision-language models (heading hierarchy, paragraph structure, footnotes, multi-column handling).
- Paragraph-stable IDs on primary works, full-text search inside them, and the corresponding MCP tools.
- LLM-synthesised wiki layer built on the reconstructed primary-work text (the Karpathy pattern, applied to a historical Indian corpus).
