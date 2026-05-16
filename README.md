# Indian Liberals

A modern home for the Indian liberal tradition. This is the in-progress rebuild of [indianliberals.in](https://indianliberals.in) — a digital archive of primary works by historically significant Indian liberal thinkers, alongside thinker profiles, organisation pages, curated excerpts, opinion pieces, interviews, and a federated feed from ThePrint's "Indian Liberals Matter" column.

Built for the [Centre for Civil Society](https://ccs.in) by [Thothica](https://thothica.com), in partnership with the Friedrich Naumann Foundation for Freedom.

## What this rebuild changes

The current site runs on WordPress. Indexing is shallow, metadata is inconsistent, and nothing is machine-readable in the way researchers — human or AI — increasingly work. This rebuild ships:

- A fast, static Astro site on Cloudflare, with a Git-based CMS so editors never see a database.
- A rich AI-extracted metadata layer over the primary-works PDFs — author normalisation, year, themes, publisher provenance, AI summaries, key points — language-agnostic at the schema level.
- An AI/agent layer: `.md` siblings on every page, `/llms.txt` and `/llms-full.txt`, an `/AGENTS.md` schema, and an MCP server at `mcp.indianliberals.in` for frontier LLMs to query the corpus directly.
- Multilingual search with per-language analyzers, covering English alongside Hindi, Gujarati, and other Indian-language primary works.
- An honest two-tier model: clean content (musings, opinions, interviews, profiles, organisation pages, the ThePrint mirror) is fully searchable and paragraph-citable; primary-work PDFs surface as rich metadata + AI summary + link, with paragraph-level citation deferred to a future engagement once vision-language layout reconstruction matures.

## Stack

Every choice below is already in production on either [Falsafa](https://falsafa.ai) (Thothica) or [Liberty Lighthouse](https://libertylighthouse.ccs.in) (CCS + Thothica). No experimental components.

| Layer | Choice |
|---|---|
| Site generator | Astro |
| CMS | Sveltia CMS (Decap rewrite, Git-based) |
| Hosting | Cloudflare Pages + Workers + R2 |
| Search | Pagefind with per-language analyzers |
| Metadata extraction | Frontier LLM with structured JSON output |
| PDF serving | pdf.js viewer |
| MCP server | Node service on Cloudflare Workers |
| Repo layout | Monorepo |

## Repository layout

```
apps/
  site/     Astro site (Phase 1)
  mcp/      MCP server, Cloudflare Workers (Phase 2a)
content/    Markdown corpus + manifests (works.json, thinkers.json, organisations.json)
scripts/    AI metadata extraction pipeline + utility scripts
assets/     Brand identity + thinker portraits scraped from the current site
docs/       Architecture + handoff documentation
SCHEMA.md   Cataloging schema (the librarian-grade input to extraction + the editor handbook)
```

## Status

Pre-Phase 0. The monorepo skeleton, baseline documentation, and scraped visual assets from the current site are in place. The cataloging schema (`SCHEMA.md`), extraction pipeline (`scripts/`), and Astro scaffold (`apps/site/`) land in Phase 0 and Phase 1 respectively.

## Reference projects

- **[Falsafa](https://falsafa.ai)** — Thothica's reading platform for philosophical and classical texts. 37 works, 818 logical chapters, 2,053 variant entries across 6 languages, 3.1M words. Eight-tool MCP surface, paragraph-stable IDs, deterministic eval published at `/eval`. The methodological precedent for the no-embeddings, LLM-navigates-markdown approach this site extends.
- **[Liberty Lighthouse](https://libertylighthouse.ccs.in)** — CCS's classical-liberal resource on Indian policy, built with Thothica. Astro plus Decap CMS today; Sveltia is the natural next step. Indian Liberals is the third application of the same architectural template.
- **[Karpathy's LLM-as-Wiki gist](https://gist.github.com/karpathy/9b7dbe0f57c8edf25f3c4b07f04fb33b)** — The methodological source. Humans curate sources, the LLM does the bookkeeping that makes the knowledge base usable, and the wiki is a persistent compounding artifact rather than a chunk index rebuilt on every query.

## License

MIT. See [LICENSE](LICENSE).

The intellectual content of the archive (primary works, summaries, curated excerpts) is owned by the Centre for Civil Society and the original authors; this repository covers the build infrastructure only.
