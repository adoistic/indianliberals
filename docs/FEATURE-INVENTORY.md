# Indian Liberals — complete feature inventory

Written 4 August 2026, read out of the repository at `7bd3f4de` on `main`.
Every count below was computed from the content files, not carried forward from
an earlier document.

Three sections: **what is built and live**, **what is in flight**, and **what is
deferred**. The CMS gets its own part, because it is a second application with
its own roadmap.

---

# PART I — WHAT IS BUILT

## 1. Infrastructure and hosting

| Piece | What it is | Where |
|---|---|---|
| `indianliberals.in` | Astro 5 static site, git-integrated Cloudflare Pages build | `apps/site` |
| `cms.indianliberals.in` | Thothica CMS, Astro SSR on Pages | `apps/cms` |
| `mcp.indianliberals.in` | MCP + REST + OpenAPI server, stateless Worker | `apps/mcp` |
| `archive.indianliberals.in` | R2 bucket front (PDFs, covers, OG cards) + statistics landing page | `apps/archive-root` |
| `www.indianliberals.in` | Canonical-host redirect Worker | `apps/www-redirect` |
| ThePrint ingest | Weekly RSS + WP-REST mirror, runs on GitHub Actions | `.github/workflows/theprint-ingest.yml` |
| Content check | `astro sync` schema gate on every push and PR | `.github/workflows/content-check.yml` |

Repository is a monorepo: `apps/`, `scripts/`, `data/`, `docs/`, `content/`.
1,459 work records carry a `pdf_url` served from R2 (3.51 GB at the last audit).

**Operating characteristics worth knowing.** A full site build is roughly 25–30
minutes and Cloudflare builds one at a time. A single content file that fails
its Zod schema fails the whole build and Pages silently keeps serving the last
good deploy — which is why the content-check workflow exists. Never bind the
apex domain to the R2 bucket; doing so on 26 July took the entire site down.

## 2. Content model

Thirteen Astro content collections, Zod-validated in
`apps/site/src/content.config.ts`, with shared sub-schemas in `src/schemas/`
(`extraction`, `i18n`, `mentions`, `people`, `provenance`, `rights`,
`synthesis`). `SCHEMA.md` is the prose form of the same contract.

### Populated

| Collection | Entries | Tier | Notes |
|---|---|---|---|
| `primary-works` | 1,575 (6 hidden) | B (interviews A) | 12 work types; 34,200 measured pages across 1,418 works |
| `thinkers` | 725 | A | 27 core, 167 extended, 211 referenced, 320 unclassified |
| `musings` | 195 | A | Curated excerpts, paragraph-citable |
| `theprint-mirror` | 81 | A | Federated column, noindex by design |
| `opinions` | 59 | A | Includes event coverage, split out to `/events/` |
| `organisations` | 52 | A | Section currently hidden from nav; all pages resolve |
| `contributors` | 13 | A | Present-day opinion writers, distinct from thinkers |
| `series` | 10 | — | Named non-periodical runs |

Work-type breakdown of primary works: 740 periodical issues, 351 speeches, 149
pamphlets, 93 edited volumes, 92 interviews, 59 essays, 50 books, 18 lectures,
17 occasional papers, 3 reference, 2 correspondence, 1 letter.

### Defined but empty (schema exists, no entries)

`themes`, `period-windows`, `reading-paths`, `graph-edges`, `periodicals`.
The last is empty by design: periodical issues live inside `primary-works` with
`work_type: periodical_issue`. The other four are the synthesis layer — Phase 4
of the extraction plan, scoped but not run.

### Schema features worth naming individually

- **Two-tier model.** Tier A carries full markdown body and is paragraph-citable.
  Tier B is metadata + AI summary + key points + PDF link. Declared in
  frontmatter, enforced in the agent layer, tested by `/eval`.
- **Multilingual titles** — `main`, `subtitle`, `original_script`, `translit`,
  `translation`.
- **i18n fields on every collection** — `language`, `translation_of`,
  `translations{}`, `translation_status`. Machine translations are noindexed
  until reviewed.
- **AI provenance** (`ai.extracted_at`, `model`, `prompt_version`) on every
  AI-touched record, plus `needs_review` and `draft`.
- **Rights schema** — `public_domain` / `fair_use_educational` /
  `permission_granted` / `takedown_on_request` / `unknown`, with a PD year, an
  editorial review flag and notes.
- **Extraction honesty fields** — `pages_rendered` vs `pages_total` with a
  `pages_total_source` provenance enum, `extent_caveat`, `toc_drift_detected`,
  `missing_metadata_flags`, `dispatch_count`.
- **Byline resolution provenance** — `authors_resolution.method`
  (deterministic / llm / vision), confidence, stubs created, collisions logged.
- **Structured mentions** — `thinker_mentions[]` with role, reasoning, evidence
  quotes and key passages; `related_thinkers[]`; `cross_thinker_mentions[]`.
- **FRBR-lite manifestation chain** for reprints.
- **Hide, never delete.** `hide_from_index` on works and organisations, with a
  `hide_reason`. Six works with no digitised source are hidden this way; their
  pages still resolve so nothing already linked breaks.
- **Build-time slug uniqueness check** (`lib/check-slug-uniqueness.ts`) — a
  duplicate id fails the build.

## 3. Public site — every surface

### Landing page (`/`)

- Drifting mosaic hero built from the collection's own portraits and periodical
  covers; CSS-only motion, IntersectionObserver stagger, fully disabled under
  `prefers-reduced-motion`.
- "Archive at a glance" stats band, every figure computed at build time: pages,
  primary works, periodical issues, oral history, thinkers profiled, excerpts &
  opinions. Count-up animation. Each tile is a doorway into the section.
- Works-per-decade histogram, 1820s onward, with a caption stating how many
  works carry a date. Bars deep-link into `/primary-works/?decade=…`.
- Canon rail of Indian thinkers, ordered by birth year, duotone portraits.
- Latest six ThePrint pieces, linking out to theprint.in.

### Collections

| Route | What it does |
|---|---|
| `/primary-works/` | Chronological list, faceted client-side filters on Type / Language / Decade / Theme, cover-image grid, deep-linkable decade param |
| `/primary-works/<slug>/` | Tabbed detail: summary + read-PDF; pull quotes, themes, people in the piece, related across the archive, Tier-B disclaimer |
| `/periodicals/` | Openable series cards for dated runs plus booklet series |
| `/periodicals/<series>/` | One run's issues |
| `/series/<series>/` | Named non-periodical runs (booklet series, memorial lectures, occasional papers, annual analyses, multi-part works) |
| `/interviews/` | Oral history, four doorways: by figure, historic talks, explainers, conversations |
| `/interviews/<shelf>/` and `/interviews/people/` | One figure's sittings, or the index of interviewees |
| `/lectures/` and `/lectures/<series>/` | Annual, memorial and historic addresses |
| `/musings/` | Image-led card grid; sort newest/oldest; facets on Decade / Kind / Place / Key concept / Theme; on mobile the facets collapse behind one control showing the active count |
| `/musings/<slug>/` | Excerpt with hero image, source-work link, paragraph anchors |
| `/opinions/` and `/opinions/<slug>/` | Present-day commentary, same sort/filter treatment |
| `/events/` | Annual lecture, essay contests, results, public debates — split out of Opinions, existing URLs preserved |
| `/languages/` and `/languages/<lang>/` | Browse by the language the work was published in: Marathi 78, Gujarati 24, Hindi 5, Bengali 2. Periodical runs grouped rather than listed issue by issue |
| `/thinkers/` | Curated canon, alphabetical by displayed name, duotone portraits |
| `/thinkers/directory/` | All 725, sectioned by canon status, live name filter, works-only toggle, expand/collapse per section |
| `/thinkers/<slug>/` | Bio, portrait chain (caricature → ring → photo), themes, affiliations, "By X" / "About X" / "Mentioned in" sections with real counts, "How X is discussed in this archive" evidence aggregation |
| `/organisations/` and `/organisations/<slug>/` | Org pages with logo or generated monogram tile; index hidden from nav at CCS request, pages all resolve |
| `/contributors/` and `/contributors/<slug>/` | Present-day writers |
| `/theprint-mirror/` and `/theprint-mirror/<slug>/` | Federated column; body stripped for humans, preserved in the `.md` sibling for agents, outbound CTA to theprint.in |
| `/about/` | What the archive is, who built it, "People who helped in building this Archive" |
| `/eval/` and `/eval/paper/` | Score page and the method written up in full |
| `/gallery/`, `/testimonials/`, `/contact/` | Real placeholder pages, noindex, excluded from sitemap |
| `/404` | Custom |

### Reader-facing features

- **Search.** Pagefind, static index built after `astro build`. `/` keyboard
  shortcut, keyboard-trappable dialog, type and language filter pills.
  Per-page tokenizer selection driven by `<html lang>`, so Devanagari, Gujarati
  and Bengali index correctly rather than silently returning nothing.
- **Grouped disclosure navigation.** Three clusters (Collections / People /
  Commentary) plus About and Search. Every nav item carries a one-line
  description and a live build-time count. WAI-ARIA disclosure pattern: real
  buttons, `aria-expanded`/`aria-controls`, Escape closes and restores focus,
  focus-out and click-outside close, hover is a convenience layered on top.
- **Pop-up notices.** One editable notice, poster and sentence and button, on
  every page until the moment it is over. Not a modal: a complementary landmark
  first in the document, nothing aria-modal, no focus stolen and no focus trap,
  so a screen reader meets it as a piece of the page. Close it with the button,
  Escape, a click off the card, or by tabbing past it; the browser remembers
  for 48 hours, so a dismissal holds without losing the notice.
  With no JavaScript the same markup is a banner at the top of the page. The
  build drops a finished notice and the reader's own clock retires one that
  finishes between builds (`apps/site/src/lib/announcements.ts`).
- **Dark mode**, responsive layout, mobile filter and sort affordances.
- **Typography.** Source Serif 4 and Source Sans 3, with Noto Serif Devanagari
  and Noto Serif Gujarati for Indic scripts.
- **Multilingual routing.** `en` at root, `/<lang>/<collection>/<slug>/` for
  hi / gu / mr / bn, bidirectional hreflang graph with `x-default`,
  self-referential canonicals.
- **Related across the archive** on every detail page, from a precomputed
  TF-IDF cross-link map.
- **Paragraph-stable anchors** (`p-` + six hex, FNV-1a) on every rendered
  paragraph of Tier A content, computed at build by a remark plugin.

## 4. AI and agent layer

- **`.md` siblings** on every Tier-A detail page — raw markdown plus a
  frontmatter-derived header, with `<!-- #p-xxxxxx -->` annotations matching the
  rendered anchors exactly, so an agent can cite `<page-url>#p-xxxxxx` and the
  link resolves.
- **`/llms.txt`** — curated index of the archive.
- **`/llms-full.txt`** — single-file corpus dump, plus per-thinker variants.
- **`/AGENTS.md`** — the citation policy and schema, generated at build.
- **`/SKILL.md`** — a skill file for clients with no MCP connection.
- **Build-time JSON API**: `/api/meta.json` (live counts and endpoint
  directory), `/api/works.json`, `/api/works/<id>.json`, `/api/thinkers.json`,
  `/api/organisations.json`, `/api/cross-links.json`, `/api/search-index.json`.
  These are what the MCP server reads, which is why content growth needs no MCP
  change.
- **`/eval/pool.json`** and **`/eval/results.json`** published alongside the
  page.

## 5. MCP server

One tool registry in `apps/mcp/src/tools.ts` generates three surfaces — MCP
Streamable HTTP, REST, and an OpenAPI 3.1 document — so they cannot drift.
Stateless Worker, zero runtime dependencies, with its own landing page carrying
setup instructions.

Ten tools: `read_index`, `list_thinkers`, `list_works`, `get_work_metadata`,
`read_clean_content`, `get_passage`, `search_corpus`, `find_related`, plus
`search` and `fetch` — the pair OpenAI's deep-research clients require, so the
corpus is reachable from ChatGPT as well as Claude and Cursor.

## 6. Eval framework

Live at `/eval/`, with the method written up at `/eval/paper/`, bylined Adnan
Abbasi.

- **255 questions** in a frozen pool (`data/eval/pool.json`), covering both
  tiers, versioned with the corpus snapshot they were built from.
- **Deterministic grading** — substring match plus citation-shape validation,
  scored 0 / 0.5 / 1. No model judges anything.
- Last run: `claude-sonnet-5` driven through the live MCP surface, 27 July.
  **Graded 70.8%**, loose 87.5%, strict 58.0%, 25 content failures, 0
  unanswered, and **0 answers quoting text the archive does not publish**. That
  last zero is the point: the two-tier promise held across 255 questions with no
  fabricated quotation.
- Harness in `scripts/eval/`: pool builder, corpus builder, abstention builder,
  grader with its own unit tests, run merger, pool validator.

## 7. SEO and legacy preservation

- **1,539-rule legacy WordPress redirect map** as Cloudflare Pages Functions
  (`apps/site/functions/_legacy/`), covering `/content/`, `/author/`,
  `/content_tag/`, `/content_category/`, `/content_letter/`,
  `/all-categories/`, `/travel/` and the per-language `hi/`, `mr/`, `bn/`,
  `gj/` variants. Regenerate with `scripts/legacy-redirects/generate.py` after
  every ingestion.
- **JSON-LD** on every page: sitewide Organization + WebSite graph, plus
  per-page Book/Article/Person/Organization/BreadcrumbList/CollectionPage nodes.
- **Branded OG cards**, 1200×630, pre-rendered on R2 under `og/` — a per-work
  card compositing the cover, per-thinker cards from portraits, per-musing and
  per-opinion cards from hero images, section mosaics, and a home card. Falls
  back cleanly when no source image exists.
- **Sitemap** with hreflang alternates, excluding noindex mirror pages and the
  unbuilt placeholder sections.
- **robots.txt**, `_headers`, `_redirects`, IndexNow submission script.

## 8. Pipelines and tooling

| Directory | What it does |
|---|---|
| `scripts/llm-extract/` | v1.5 extraction pipeline: rasterize → prepare pages → dispatch → validate → collect, with a ledger, a rate-limit-aware overnight runner, transliteration handling and tests |
| `scripts/synthesis/` | ~50 scripts: authority cleanup, byline resolution (deterministic → LLM → vision), thinker and work classification, NER mention resolution, TF-IDF cross-links, theme vocabulary, duotone portrait generation, periodical cover generation, orphan auto-hiding, coverage audits for every pass |
| `scripts/interviews/` | Local Whisper (mlx large-v3-turbo) transcription plus sherpa-onnx speaker diarization, classification and routing, for 110 video works |
| `scripts/heading-offset/` | Sequence alignment with affine gaps that repaired the article-misjoin bug: 164 files / 369 sections down to 3 files / 4 sections, zero prose lines altered |
| `scripts/kp-backfill/` | Key-points digest backfill; 11,099 bullets across 1,460 works |
| `scripts/dedupe/` | Duplicate detection and field-level merge, with redirect generation |
| `scripts/series/` | Series detection and assignment |
| `scripts/db-extract/` | WordPress SQL dump parsing, content/media/OCR extraction |
| `scripts/combine-translations/` | Deskew, gutter detection and lossless page splitting for sideways two-page spreads |
| `scripts/authority/`, `scripts/eval/`, `scripts/seo/`, `scripts/legacy-redirects/`, `scripts/archive-landing/` | Authority seeding, eval harness, IndexNow, redirect map, archive landing page |

Two CCS review spreadsheets are round-trip ingestible: 725 thinkers
(`Indian-Liberals-Thinkers-Classification-2026-07-17.xlsx`) and 52
organisations (`…-Organisations-…-2026-07-24.xlsx`).

---

# PART II — THE CMS

`cms.indianliberals.in`. A purpose-built Astro application, not the
off-the-shelf Sveltia the proposal specified. The reason for the substitution:
Sveltia would have put a schema in front of an archivist. This puts a job in
front of them.

## What it does today

### Identity and access

- **Firebase Auth** — Google sign-in or an emailed magic link. No GitHub
  account, no password.
- **Four roles**, defined once in `src/lib/roles.ts` and explained to editors on
  the People page in the same words the code enforces:

| Role | Content | People |
|---|---|---|
| Super admin | everything | everyone, including admins |
| Admin | everything | sub-admins and contributors |
| Sub-admin | create, edit, publish | nobody |
| Contributor | drafts only | nobody |

- Super admin is pinned by email in `firestore.rules`, so nobody can grant it to
  themselves. An admin cannot mint another admin, which keeps the blast radius
  of one compromised account small.
- **No Firebase service account exists.** The Worker verifies each sign-in
  against Google's public certificates and reads roles from Firestore *as the
  user*, so the security rules do the enforcing. One fewer key to leak. The
  rules are under test (`scripts/test-rules.mjs`).
- One secret in the whole system: the GitHub App (id, installation id, PEM),
  scoped to `contents:write` on a single repository.

### Task-shaped home screen

The home page asks what you want to do, not which entity you would like to
author: put a document online · put a whole folder online · fix something that
is wrong · add a person or organisation · add an excerpt or opinion piece ·
finish something you started.

### Screens

| Screen | What it does |
|---|---|
| `/add` | Single-entry creation: pick the kind, upload the document, choose how to fill it in, check and save |
| `/batch` | Folder intake: every file goes to R2 first, then each is read in turn and lands on the draft shelf. Closing the tab costs the one in flight and nothing more |
| `/browse` | The catalogue as a reader sees it — titles, authors, covers — searchable per collection, click through to edit |
| `/edit` | Full field editor, grouped, with hints |
| `/drafts` | The shelf: anything begun and put down, plus everything a batch has read. Nothing here is public and nothing here triggers a build |
| `/popups` | Pop-up notices: which one readers are meeting now, which are waiting, which are over, and a button to make another |
| `/people` | Role management, with each role's powers spelled out |
| `/signin`, `/finish-signin`, `/no-access` | Auth flow |

### Forms

- Generated from `src/lib/collections.ts`, which restates all thirteen
  collections as plain data: field name, human label, kind, whether it is
  required, and one plain sentence telling a non-technical editor what belongs
  there. Two written rules keep it honest with the site's Zod schema.
- **Six field groups**, named once in `src/lib/groups.ts` so both the add and
  edit screens call the same drawer the same thing: *The details that matter ·
  Publication details · People and contents · Subjects and filing · Files,
  pictures and rights · Machine records and settings*.
- Sixteen field kinds including reference and reference-list pickers (which
  split on a pipe to offer more than one collection), object and object-list
  editors for nested structures like pull quotes and thinker mentions,
  string-lists, slugs, years and dates.
- **Seven collections are offered**, not thirteen: primary works, thinkers,
  opinions, musings, organisations, contributors, series. The other six are
  deliberately withheld — five have zero entries or no directory, so a form
  would produce a file nothing renders; ThePrint mirror is refilled weekly by
  the ingest and an entry typed here would be overwritten. All thirteen stay in
  `ALL_COLLECTIONS` so tooling can still describe a record it encounters.

### Three ways to add something

All three produce the same validated file. The AI paths are a convenience, not
a separate class of record.

1. **Copy a prompt.** The CMS writes a complete prompt from the schema —
   including the archive's conventions and the slugs already in use, so the
   model reuses ids rather than inventing them — the editor pastes it into
   whatever AI they already use and pastes the reply back. Costs nothing.
2. **Bring your own key.** Anthropic or OpenRouter. The key stays in the
   editor's browser and the request goes straight to the provider, so the bill
   and the document are both theirs. Never sent to us.
3. **Type it in.** Every field, with a hint.

### Storage and commits

- **Uploads go to R2 first**, before anything is read or catalogued, so a
  failure downstream never loses a document. XHR with a real progress bar,
  clash detection, explicit overwrite. Up to 120 MB per file.
- **Drafts live in Firestore, not git.** Deliberate: the site takes ~25 minutes
  to build and Cloudflare builds one at a time, so a draft that committed on
  every save would spend the archive's whole build capacity on work nobody can
  read. The commit happens once, at the end, when a person says it is ready.
- **Publishing commits through a GitHub App**, with the commit message naming
  the editor, so repository history stays a record of who did what even though
  no editor has a GitHub account. Installation tokens are cached per isolate and
  re-minted near expiry. The PKCS#1 → PKCS#8 key conversion is hand-rolled
  because WebCrypto will not accept GitHub's format.
- **`publish-batch`** endpoint for promoting a whole shelf at once.
- **YAML scalar quoting** (`src/lib/yaml-scalar.ts`) with flow-style reading —
  this is the module that, when it got quoting wrong, wrote `vocations` as a
  string and stopped every deploy for six days. It now has its own tests.
- **Em-dash lint** runs before every CMS build.

### Setup tooling

`scripts/create-github-app.mjs` uses GitHub's app-manifest flow so every setting
is pre-filled and the private key comes back over the API rather than being
copied out of a browser; `finish-github-app.mjs --set` writes the secrets. Plus
standalone tests for the private key, commits, YAML flow and quoting, and the
Firestore rules.

### The previous generation, removed

The Sveltia CMS (`/admin/`), its never-deployed OAuth proxy (`apps/auth`),
its allowlist (`data/admins.json`) and its guide (`docs/CMS-WORKFLOW.md`)
were removed on 2026-08-05. The only editing surface is
`cms.indianliberals.in`; git history keeps the old code if it is ever
wanted for reference.

## Built since this list was first drawn (2026-08-05)

1. **Static page content is editable.** A `site` content collection
   (`apps/site/src/content/site/`, one markdown file per surface) now holds the
   homepage copy, the site title/description/credits, the whole nav tree, every
   section standfirst, the About page, the shelf blurbs, the placeholder pages
   and the recurring interface labels. The `.astro` pages read it through
   `src/lib/site-copy.ts` and keep their original wording as inline fallbacks,
   so an emptied field can never blank a page. The CMS edits it at `/site`
   ("Change the website's own words"), one form per surface, through the same
   field machinery as everything else (`apps/cms/src/lib/site-surfaces.ts`).

2. **Pictures are dropped, not typed.** Every image field (work covers, thinker
   portraits, organisation logos, contributor photos, musing/opinion heroes) is
   a drag-and-drop widget with a preview. Covers go straight to R2; repository
   images are staged in the bucket and committed *beside the entry in the same
   commit* at save time (so one save is still one build). Drafts remember their
   staged pictures across sessions.

3. **Covers capture themselves.** Uploading a PDF (single add or batch) renders
   its first page in the browser (pdf.js) and files it as the cover
   automatically; the edit screen has "Capture the first page of the PDF" for
   older entries, and any capture can be replaced by dropping a picture.

4. **OG cards regenerate themselves.** `scripts/og/og_cards.py` +
   `.github/workflows/og-cards.yml`: every content push re-renders exactly the
   cards whose title, byline or picture changed (manifest on R2), uploading
   through the CMS Worker's `/api/og-put`. New works get their card minutes
   after landing.

## What the CMS does not do yet

This is the list to build against.

2. **Gallery has no content type.** Building the section means a collection with
   image, caption, credit, date and event grouping. (The image picker now
   exists.)

3. **Testimonials has no content type.** Quote, attribution, role, organisation,
   optional photo, ordering.

4. **Contact has no form.** A contact and corrections form, and somewhere for
   submissions to land. (The contact page's copy, and a contact email that
   shows once filled in, are now editable from `/site`.)

6. **No editorial workflow beyond draft/publish.** No review queue, no
   assignment, no comment thread on an entry. `needs_review` exists in the data
   as a flag but has no screen driving through it — and there are hundreds of
   AI-emitted records carrying it.

7. **No preview.** An editor cannot see the rendered page before publishing, and
   given the 25-minute build they cannot see it quickly afterwards either.

8. **No bulk edit.** Reclassifying 300 thinkers means 300 saves or a script.

9. **No delete or unpublish.** Hiding a record means setting `hide_from_index`
   by hand if the form exposes it.

10. **No build status.** After publishing, nothing tells the editor whether the
    deploy succeeded — which is exactly the failure mode of 30 July. The
    content-check workflow now catches a bad file, but the CMS itself does not
    surface it.

11. **No revision history in the interface.** Git holds every version; the CMS
    offers no way to see or restore one.

---

# PART III — IN FLIGHT

Open items from the CCS round-3 review (`docs/ccs-round-3-reply.md`, 2 August),
plus the standing backlog.

## Committed, awaiting a decision from CCS

- **Revised copy** for Home, About and Thinkers — requested, not yet received.
- **The black-and-white Raja Ram Mohan Roy image.**
- **Which stat tiles should link where.** Three tiles count one thing and open a
  page showing another. Recommendation is to point each tile at the page holding
  what it counts.
- **Whether "Periodicals" keeps that name** — most of that page is Forum
  booklets, budget analyses and memorial lectures rather than periodicals.
- **Which interview pages are filed under the person discussed rather than the
  person speaking** — 92 interviews, and it cannot be told from outside which
  are wrong.
- **Gallery and Testimonials source material** — what the photographs are, how
  many, and what form the testimonials take.

## Scoped, in progress or ready to start

- **Collections by publication house.** 23 publishers, of which Forum of Free
  Enterprise (577), Freedom First (500), The Indian Libertarian (138) and
  Shetkari Sanghatana (48) are 92% of everything attributed. Two open questions:
  206 works have no publisher recorded, and eight publishers hold a single work.
- **Oral histories, the data underneath.** Of 92 interviews only 27 carry an
  explicit `video_group`; the other 65 are sorted by reading the filename. The
  four-doorway UI shipped 3 August; the routing data behind it still needs a
  proposed group per work, sent to CCS to correct.
- **Interviews on thinker pages.** The mention data exists; the threshold rule
  does not. Zareen Masani on Minoo Masani belongs on his page, a passing mention
  does not. A rule will be drafted and its catch shown before it goes live.
- **Musings authorship.** 98 of 195 have no author and none links back to a
  source work. 74 of those name their source in their own text and can be
  extracted for approval; the remaining 24 need the original WordPress posts or
  institutional memory.
- **Home-page separation** — not started; to be shown as options rather than
  described.
- **The standfirst pass.** Descriptive section blurbs were written so search
  engines and agents could parse the archive, and they have leaked into the
  reading experience. Better as one deliberate pass than scattered edits.
- **Contact page and feedback form** — small, unbuilt.
- **Exact page count.** 34,200 pages are now measured across 1,418 works; the
  remaining gap is works whose count was never captured. The old essay-contest
  page claims "up to 50,000 digitized pages", which cannot be reconciled with
  anything measurable.

## Content repair backlog

- **`ff389`** (Freedom First, April 1986) — the corpus's only true empty stub.
  The PDF exists on R2; it needs re-extraction.
- **Four image-only scans** with no text layer, needing OCR:
  `bharatasathi-sharad-joshi`, `evils-of-child-marriage`,
  `from-darkness-to-light`, `poshindyanchi-lokshahi-sharad-joshi`.
- **16 video works** with no transcript upstream. Do not generate key points for
  these; there is nothing to derive them from.
- **Six works with no source PDF at all**, hidden rather than deleted, awaiting
  scans from CCS: three *Khoj* issues, *Doan Pavlant Bali Patalat*,
  *Shetakanyachi Raje Shivaji*, *Yodha Shetkari*. Plus the Bengali original of
  *Ramtanu Lahiri o Tatkalin Bangosamaj*, of which only an English translation
  of Chapter V is held.
- **125 stub thinker bios** marked `ai_drafted_stub`, awaiting real bios.
- **46 files with a doubled `*By by <name>*` byline** — a regex sweep.

## Not started, roadmapped

- **The synthesis layer.** Four collections are defined and empty: `themes`
  (emergent taxonomy with editorial intros and evolution), `period-windows`
  (era context and key debates), `reading-paths` (curated sequences by
  audience), `graph-edges` (fifteen typed relationships between works, thinkers,
  themes, periods and organisations, designed for a future graph explorer).
  Every schema is written; no pass has been run.
- **Per-article structured fields** — `essays_summarized[]` and `articles[]` are
  empty corpus-wide by design.

---

# PART IV — DEFERRED BY AGREEMENT

Not gaps. The proposal put these in a future engagement and they should not be
counted as unfinished.

- **Vision-language layout reconstruction** of the primary-work PDFs.
- **Paragraph-stable IDs on primary works**, and full-text search inside them.
- **MCP tools that read primary-work bodies** (`read_primary_work`,
  `get_primary_work_passage`).
- **The Karpathy-style LLM-synthesised wiki layer** over Tier B.

One caveat worth restating: 780 works already carry extracted per-article body
text — headings, bylines, per-article prose and bullets. That is deferred future
scope, built inside v1 and unbilled. The contracted deliverable underneath it
(PDF link + metadata + AI summary) is sound independently.

---

## Where the numbers in this document come from

Content counts: `grep` over `apps/site/src/content/`. Page totals: sum of
`physical.pages_total` over non-hidden works. Eval figures:
`data/eval/results.json`. Corpus and delivery history:
`docs/2026-07-28-final-report.md`, `docs/handoffs/2026-07-26-remaining-work-handoff.md`,
`docs/archive-numbers.md`, `docs/ccs-round-3-reply.md`.
