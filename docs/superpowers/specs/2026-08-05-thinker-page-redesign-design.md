# Thinker page redesign: works explorer, collapsible bio, in-author search

**Date:** 2026-08-05
**Author:** Adnan
**Status:** Implemented same-day (autonomous /goal session)

## Problem

The thinker detail page (`ThinkerDetail.astro`) is far below the bar set by
`/primary-works/`:

- Works render as plain text link lists, truncated at 10–15 items with a dead
  "…and N more" line. M. A. Venkata Rao has 179 authored works; the page shows
  15 and hides 164 with no way to see them.
- No cover images anywhere below the portrait, no filters, no per-author
  search. `/primary-works/` has a cover-led grid, a sticky facet rail, decade
  grouping and live counts; the thinker page has none of it.
- Long bios (Sharad Joshi: 1,871 words) push all works below several screens
  of prose with no collapse.
- The layout below the bio is six stacked list-sections with identical
  styling, hard to scan and visually monotonous.

## Data facts that shaped the design

- 1,575 listed primary works; heaviest author 179 works, several over 60.
- 725 thinker entries; most bios are short (median ~0 words — many stubs),
  only ~7 exceed 600 words. Bio collapse must not fire on short bios.
- Site search = Pagefind over the built pages, filters `type` + `lang`.
  A second full-text bundle (inside-the-PDFs) lives on R2; its build inputs
  (`works_meta.json`, `fulltext.jsonl` ~100 MB) are not in git, so that bundle
  cannot gain an author facet in this change (follow-up below).
- Works carry `cover_image`, `publication.year`, `work_type`, `themes`,
  `publication.language`; opinions/musings carry `pubDate`, `themes`,
  `hero_image`.

## Design

### 1. Header + stat strip

Header (portrait, tradition chip, name, dates) stays. Below it, a compact
stat strip of anchor chips: "N works · N excerpts · N about · N mentioned
in" — each an in-page link to its section. Counts reuse the existing
role-partition variables (authored-count semantics unchanged; CCS round-2
feedback #11 consistency is preserved).

### 2. Collapsible bio

The bio container collapses to ~26rem max-height with a bottom gradient fade
and a "Read the full biography" button; expanded state gets a "Show less".
A tiny inline script measures `scrollHeight` after load and only activates
collapse when the content meaningfully exceeds the threshold (>1.25× the
cap), so short bios never show the button. No-JS fallback: fully expanded
(script adds the collapsed class, never removes content).

### 3. Works explorer (the centerpiece)

`"By <name>"` becomes **ThinkerWorksExplorer.astro**: every authored primary
work as a cover-led card (same 3:4 grammar as `/primary-works/`: cover image
or initial+type spine tile, title, year · type, non-en language badge),
**no truncation ever**, newest first, with a toolbar:

- **Search box** ("Search within <name>'s works…"). Instant metadata match:
  each card carries a lowercased haystack (title, subtitle, translit,
  translation, year, type, themes); every typed word must match
  (AND-of-substrings). Also, debounced ≥3-char queries run an
  **author-scoped Pagefind search** (`filters: { author: <thinker-id> }`)
  against the site index and render a "Matches inside works and pages"
  panel beneath the grid — excerpts from summaries, key points, transcripts
  and page prose. Pagefind loads lazily on first keystroke; in dev (no
  index) the panel degrades to a hint, the metadata filter still works.
- **Facet chips**, same visual grammar as `/primary-works/`: Type, Decade,
  Language (only when >1 among this author's works), Theme (top 12 by
  count, only when the author has ≥2 themed works). Chips AND across
  facets, OR within one. Reset button + "Showing X of Y" counter.
- Authored **opinion pieces** join the same grid as cards (hero_image
  cropped 3:4, type "opinion piece") so "everything they wrote" is one
  surface with one search/filter state.

Empty-state line when filters+query match nothing.

### 4. Excerpts and About sections

- **Excerpts** (kept separate from "By" per Adnan 2026-07 decision, prose
  note retained): upgraded to an image-led card row using `hero_image` where
  present, text rows otherwise. All shown (musings per author are few).
- **About <name>** (interviews + profile pieces): profile pieces become
  hero-image cards with their key passages beneath; interviews listed with
  cover thumbnails. All shown.

### 5. "Mentioned in" — expanders instead of dead ends

Evidence-bearing text lists stay (the quotes are the value), but every
`.slice(0, N)` + "…and N more" is replaced by a no-JS-safe `<details>`
expander: first 8 rows visible, the rest inside `<details>` with summary
"Show all N". Nothing is unreachable anymore.

### 6. Pagefind author facet — and a production bug found on the way

The author facet is emitted on work/opinion/musing detail pages:
- `PrimaryWorkDetail.astro` — one per thinker in `authors[]`;
- `OpinionDetail.astro` — the `author` contributor ref id when present;
- `MusingDetail.astro` — the `author` thinker ref id when present.

IDs (slugs), not display names: stable, no escaping issues.
The explorer queries this facet. Cost: a few bytes per page in the index.

**Discovered while wiring this up (verified against Pagefind 1.5.2 with a
minimal reproduction, and against production):** Pagefind does NOT split
`data-pagefind-filter` on commas. `data-pagefind-filter="type:primary-work,
lang:en"` indexes ONE filter named `type` with the garbage value
`"primary-work,lang:en"` — so every filtered search on the live site
(including the header search dialog's type pills) has been silently
returning zero results. `data-pagefind-meta` mis-parses the same way.

Fix: `PagefindFilters.astro`, which renders one empty
`<span data-pagefind-filter="key:value">` per pair (the only syntax the
indexer parses) plus the same treatment for meta pairs. All six former
comma-syntax sites now go through it (thinker, organisation, musing,
opinion, primary-work, theprint-mirror detail pages). The thinkers
directory's per-row filters were removed outright: row filters merge into
one meaningless multi-valued facet on the listing page record, and no UI
consumes them.

## Alternatives considered

- **Author facet in the R2 full-text bundle** (search inside the PDFs scoped
  to an author): the right long-term addition, but its build inputs aren't
  reproducible in this repo checkout. Follow-up: add `filters.author` in
  `scripts/fulltext/export-works-meta.py` + `build-index.mjs`, rebuild,
  re-upload; then the explorer's matches panel can offer a "search inside
  the PDFs" scope toggle.
- **Paginating the works grid**: rejected. Filters + search + lazy-loaded
  images handle 179 cards fine on a static page; pagination reintroduces
  the "you can't see everything" feeling this redesign exists to kill.
- **One mixed grid including excerpts/about/mentions**: rejected; the
  role partition (by / excerpts / about / mentioned-in) is editorially
  meaningful and already understood by CCS.

## Round 2 (same day, on Adnan's feedback)

- **Organisation pages get the same treatment** (Adnan: "The same thing can
  be done for organizations"). `ThinkerWorksExplorer` generalised into
  `WorksExplorer` with a `scope` prop (`author:<id>` on thinker pages,
  `org:<id>` on organisation pages); `PrimaryWorkDetail` emits the `org`
  facet for publisher / issuer / org-author / org-editor. OrganisationDetail
  gains the stat strip, `CollapsibleBio` ("Read the full history"), the full
  works explorer (old cap of 30 removed), portrait chips for affiliated
  thinkers, and thumbnail rows + `<details>` expander for prose mentions
  (`org-mentions.ts` now carries each mention's image).
- **De-foldering the list sections** (Adnan, with screenshots: "these two
  sections... still use the folder style of UI"). `EvidenceLink` rows now
  lead with a cover/hero/portrait thumbnail (initial-tile fallback keeps
  columns aligned) and support a kind badge; `RelatedSection` renders
  image-led cards with a collection chip instead of text-only boxed rows.
- The bio collapse moved into a shared `CollapsibleBio.astro` used by both
  thinker and organisation pages.

## Out of scope (follow-ups)

- R2 full-text author/org facets (above).
- i18n copy keys for the new labels default to English via the existing
  `label()` fallback mechanism, as elsewhere on the site.
