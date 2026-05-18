# Indian Liberals

A modern home for the Indian liberal tradition. This is the in-progress rebuild of [indianliberals.in](https://indianliberals.in) — a digital archive of primary works by historically significant Indian liberal thinkers, alongside thinker profiles, organisation pages, curated excerpts, opinion pieces, interviews, and a federated feed from ThePrint's "Indian Liberals Matter" column.

Built for the [Centre for Civil Society](https://ccs.in) by [Thothica](https://thothica.com), in partnership with the Friedrich Naumann Foundation for Freedom.

## What this rebuild changes

The legacy site runs on WordPress. Indexing is shallow, metadata is inconsistent, and nothing is machine-readable in the way researchers — human or AI — increasingly work. This rebuild ships:

- A fast, static Astro site on Cloudflare, with a Git-based CMS so editors never see a database.
- A rich AI-extracted metadata layer over the primary-works PDFs — author normalisation, year, themes, publisher provenance, AI summaries, key points, cross-thinker mentions with verbatim evidence — language-agnostic at the schema level.
- An AI/agent layer: `.md` siblings on every page, `/llms.txt` and `/llms-full.txt`, an `/AGENTS.md` schema, and (post-launch) an MCP server at `mcp.indianliberals.in` for frontier LLMs to query the corpus directly.
- Multilingual search via Pagefind with per-language analyzers — English alongside Hindi, Gujarati, Marathi, Bengali. 4 languages currently indexed; 1,225 pages, ~28,000 words.
- An honest two-tier model: clean content (musings, opinions, interviews, profiles, organisation pages, the ThePrint mirror) is fully searchable and paragraph-citable; primary-work PDFs surface as rich metadata + AI summary + link, with paragraph-level citation deferred to a future engagement once vision-language layout reconstruction matures.

## Where we are

The site **builds locally and renders production-quality output**. End-to-end content pipeline runs cleanly. Not yet deployed to a public URL — that's Day 10-13 work.

### Snapshot (2026-05-18)

| Surface | State |
|---|---|
| Astro site | Builds clean. 1,225 pages, 28,000 indexed words across 4 languages. |
| Content collections | 7 wired: thinkers, organisations, musings, opinions, interviews, primary-works, theprint-mirror. Periodicals empty (deferred). |
| AI extraction pipeline | Production. 220 of ~944 PDFs baked. Rate-limit-aware overnight runner crunches the rest over the coming days. |
| Authority files | 462 thinkers + 50 organisations. byline_lookup at 678 keys. 125 entries flagged `bio_source: ai_drafted_stub` awaiting real bios (Phase 1.5). |
| Cross-link audit | Phase A applied. 65% of Tier-A entries carry a structured thinker reference (up from 31% at baseline). Bio pages render "By X / About X / Mentioned in" sections with real counts. |
| Cross-thinker mentions | 1,347 mentions across 196 works projected from extraction summaries into primary-work `related_thinkers[]`. Touchstones like Shroff (72 mentions), Nehru (42), Gandhi (26), Marx (15), Hayek (9), Adam Smith (11) now surface on their bio pages with the works that quote them. |
| TF-IDF related-links | 1,958 cross-collection links computed; rendered as "Related across the archive" on every detail page. |
| Search | Pagefind wired; `/` keyboard shortcut; type-filter pills; per-language tokenization (Devanagari, Gujarati, etc.). |
| Agent layer | `.md` siblings on every Tier-A detail page (~580 files). `/llms.txt` (curated index) and `/llms-full.txt` (4 MB single-file corpus dump) emit at build time. `/AGENTS.md` documents the citation rules + tier system. |
| ThePrint federation | RSS-ingest Cloudflare Worker scaffolded + 16/16 vitest passing. List page and homepage feed link **out** to theprint.in for humans; per-article mirror pages strip the body and keep only metadata + outbound CTA. The body is preserved in the `.md` sibling for AI agents. NOT yet deployed. |
| Sveltia CMS auth proxy | Worker scaffolded (`apps/auth/`). NOT yet deployed. |

### What remains before launch

These are tracked in `docs/superpowers/specs/` and the engagement plan at `~/.gstack/projects/IndianLiberalsWebsite/`.

1. **Phase B — in-prose NER pass** (`docs/superpowers/specs/2026-05-18-phase-b-ner-handoff.md`).
   For every Tier-A entry (musings, opinions, interviews, theprint-mirror), an LLM reads the body and emits structured `thinker_mentions[]` records — each with the named thinker, a verbatim evidence quote, and a one-line reasoning. Subject-role entries get 2-4 curated key passages instead of a single quote. The bio page renders a "How X is discussed in this archive" section that aggregates the evidence across the corpus. Pure LLM; no regex.

2. **Phase 1.5 — real bios for 125 stub thinkers**. The Phase A cross-link audit auto-created minimal `ai_drafted_stub` entries for every byline that wasn't already in the authority. They render today as placeholder pages. A later pass uses `claude -p` to draft 2-4-paragraph bios from the works each thinker authored / pieces about them already in the corpus.

3. **Day 10-13 deployment work**:
   - R2 upload of all ~944 PDFs with resumable batch script (PDFs are still on a curator's external drive)
   - Cloudflare Pages staging deploy
   - Sveltia CMS config + GitHub OAuth app wiring
   - ThePrint cron worker deploy + secrets
   - DNS cutover prep

4. **Day 14 — DNS cutover and launch**.

5. **3-month support window items** captured in `TODOS.md` and the spec docs.

### Current limitations (honest)

This is a deliberate list of what is NOT yet good enough. Each is either deferred to a known later pass or scoped out of the engagement.

- **Visual / UI design pass.** The UI today uses the project's baseline design system (Source Serif, Source Sans, Indic Noto-Serif fallbacks, a saffron + forest accent palette) but no professional design polish. A proper visual pass — typography rhythm, density tuning, image treatment, hero treatments per content kind, mobile interaction details, dark mode — is its own workstream and has not happened yet. The site is functional and readable; it is not yet *crafted*.
- **In-prose Wikipedia-style mention linking.** Today the bio pages list works/mentions but the prose inside an article doesn't hyperlink every mentioned thinker's name. Phase B above adds that surface.
- **Layout reconstruction of primary works.** PDFs are linked but not full-text-indexed. Paragraph-level citation inside the original works is explicitly deferred — it requires reliable vision-language layout reconstruction that clears editorial review, which is a separate engagement.
- **Karpathy-style synthesised wiki layer.** The "LLM-as-wiki-author" enrichment on top of Tier B is roadmapped post-launch.
- **125 stub thinker bios** are minimal one-liners marked `bio_source: ai_drafted_stub`. Real bios are a Phase 1.5 task.
- **The full corpus is not yet extracted.** ~220 of ~944 PDFs are baked; the rest are still queued in the overnight runner. Bio pages will grow more works/mentions as the queue drains over the coming days.
- **Periodicals collection is empty.** The Khoj Gujarati issues are filed under primary-works instead. No action planned for launch.
- **Editorial review of AI-extracted content is sparse.** `needs_review: true` is set on AI-emitted entries to flag this; CCS editorial works through them over time via Sveltia.
- **MCP server is deferred.** The agent layer today is `.md` siblings + `/llms.txt` + `/AGENTS.md`. The MCP server with 8 tools (`get_work_metadata`, `read_clean_content`, `find_related`, etc.) lands post-engagement.
- **No live deployment.** The site builds and previews locally on `:4321`; it is not yet served at `indianliberals.in`.

## Stack

Every choice below is already in production on either [Falsafa](https://falsafa.ai) (Thothica) or [Liberty Lighthouse](https://libertylighthouse.ccs.in) (CCS + Thothica). No experimental components.

| Layer | Choice |
|---|---|
| Site generator | Astro 5 with Cloudflare adapter |
| CMS | Sveltia CMS (Decap rewrite, Git-based) |
| Hosting | Cloudflare Pages + Workers + R2 |
| Search | Pagefind with per-language analyzers |
| Metadata extraction | Frontier LLM via headless `claude -p` CLI, parallelised, rate-limit-aware |
| PDF serving | Direct R2 links (pdf.js viewer not in scope for v1) |
| MCP server | Cloudflare Workers, deferred to post-engagement |
| Repo layout | Monorepo (`apps/`, `scripts/`, `data/`) |

## Repository layout

```
apps/
  site/             Astro site
    src/
      content/      Content collections (7 kinds; 1,200+ entries)
      content.config.ts  Zod schemas (with shared sub-schemas in src/schemas/)
      pages/        Routes incl. per-language /<lang>/<collection>/<slug>
      components/   Cards, Search dialog, Related sections, Header, Footer
      layouts/      BaseLayout with hreflang + Pagefind body marker
  theprint-ingest/  Cloudflare Worker — daily RSS cron mirror with admin-edit guard
  auth/             Cloudflare Worker — Sveltia OAuth proxy (scaffolded)

scripts/
  llm-extract/      v1.5 extraction pipeline (driver.py, run_overnight.py)
  synthesis/        Authority cleanup, TF-IDF, cross-link audit, byline resolution
    prompts/        Canonical prompts (system-resolver.txt, README.md);
                    Phase B will add system-ner.txt here.

data/
  authority/        thinkers.json (462), organisations.json (50)
  bake-off-output/  Per-PDF extraction outputs (metadata.a.a.json, summary.json)
  synthesis/        Aggregations, cross-links, audit residuals, resolution logs

docs/
  superpowers/specs/
    2026-05-18-cross-link-audit-design.md   Phase A spec (applied)
    2026-05-18-phase-b-ner-handoff.md       Phase B spec (next session)

SCHEMA.md           Cataloging schema — the librarian-grade input to extraction +
                    the editor handbook
ARCHITECTURE.md     Top-level design doc
TODOS.md            Post-engagement / support-window backlog
```

## Reference projects

- **[Falsafa](https://falsafa.ai)** — Thothica's reading platform for philosophical and classical texts. 37 works, 818 logical chapters, 2,053 variant entries across 6 languages, 3.1M words. Eight-tool MCP surface, paragraph-stable IDs, deterministic eval at `/eval`. The methodological precedent for the no-embeddings, LLM-navigates-markdown approach this site extends.
- **[Liberty Lighthouse](https://libertylighthouse.ccs.in)** — CCS's classical-liberal resource on Indian policy, built with Thothica. Astro plus Decap CMS today; Sveltia is the natural next step. Indian Liberals is the third application of the same architectural template.
- **[Karpathy's LLM-as-Wiki gist](https://gist.github.com/karpathy/9b7dbe0f57c8edf25f3c4b07f04fb33b)** — The methodological source. Humans curate sources, the LLM does the bookkeeping that makes the knowledge base usable, and the wiki is a persistent compounding artifact rather than a chunk index rebuilt on every query.

## License

MIT. See [LICENSE](LICENSE).

The intellectual content of the archive (primary works, summaries, curated excerpts) is owned by the Centre for Civil Society and the original authors; this repository covers the build infrastructure only.
