---
name: indian-liberals-archive
description: Query the Indian Liberals digital archive (indianliberals.in) — thinkers, primary works, periodicals, musings, opinions, interviews — with correct two-tier citations. Use when researching the Indian liberal tradition, its thinkers, organisations, or publications.
---

# Indian Liberals archive — manual access skill

This is the fallback for clients without an MCP connection. If your client
supports MCP, prefer the server: `https://mcp.indianliberals.in/mcp`
(setup instructions at https://mcp.indianliberals.in/).

## The two-tier rule (read this first)

- **Tier A — clean full text** (thinker profiles, organisation pages,
  musings/excerpts, opinions, interview transcripts, ThePrint mirror):
  quote freely; cite `<page-url>#p-xxxxxx` using the paragraph anchors.
- **Tier B — primary-work PDFs** (books, pamphlets, speeches, periodical
  issues): you can only read an AI-generated summary, never the body.
  Attribute claims as "Indian Liberals' summary of <work> (<year>)" and
  link the `pdf_url`. Never quote Tier B as if you read the original.

Full policy: https://indianliberals.in/AGENTS.md

## Endpoints (all public, no auth)

Orientation:
- `https://indianliberals.in/llms.txt` — curated index of everything
- `https://indianliberals.in/api/meta.json` — live counts + endpoint list

Structured data (build-generated, always current):
- `/api/works.json` — full works catalogue (id, title, type, authors, year, themes, tier, pdf_url)
- `/api/works/<id>.json` — one work: summary, key points, TOC, provenance
- `/api/thinkers.json` — every thinker with bio snippet
- `/api/search-index.json` — compact tier-flagged index of all content
- `/api/cross-links.json` — TF-IDF related-entries map, keys `<collection>:<slug>`

Full text (Tier A):
- Any page URL + `.md` — e.g. `/thinkers/minoo-masani.md` — returns clean
  markdown; paragraphs end with `<!-- #p-xxxxxx -->` anchors for citation.
- `/llms-full.txt` — the whole Tier-A corpus + every Tier-B summary in one file.

REST mirror of the MCP tools (JSON in/out, good for function-calling):
- `https://mcp.indianliberals.in/api/search_corpus?query=...`
- `https://mcp.indianliberals.in/api/list_works?author=...&work_type=...&year_from=...`
- `https://mcp.indianliberals.in/api/list_thinkers?tradition=...`
- `https://mcp.indianliberals.in/api/get_work_metadata?id=<slug>`
- `https://mcp.indianliberals.in/api/read_clean_content?id=<collection>:<slug>`
- `https://mcp.indianliberals.in/api/get_passage?id=<collection>:<slug>&paragraph_ids=p-xxxxxx`
- `https://mcp.indianliberals.in/api/find_related?id=<collection>:<slug>`
- OpenAPI 3.1 spec: `https://mcp.indianliberals.in/openapi.json`

## Typical research flow

1. Fetch `/llms.txt` for orientation, or `/api/search_corpus?query=...`.
2. For a thinker: `/api/list_thinkers?q=<name>` → read `/thinkers/<id>.md`.
3. For works: `/api/list_works?author=<id>` → `/api/works/<id>.json` for
   the summary → link the `pdf_url` for the source.
4. Cite Tier A paragraphs by anchor; attribute Tier B to the archive's summary.

Maintained by the Centre for Civil Society; rebuilt by Thothica.
