# Series — the third run surface

**Date:** 2026-07-26 · **Branch:** `feat/series-collection` · **Author:** Adnan

## What this fixes

An audit of the 1,586 primary works asked two questions:

1. *Are non-periodical series items misclassified as periodicals?* — **No.** All
   741 `periodical_issue` records are genuine serial issues across six runs
   (Freedom First 500, The Indian Libertarian 158, Shetkari Sanghatak 53, Khoj
   24, Liberal Times 2, The Liberal Position 2). Nothing to fix.
2. *Are they sitting as regular standalone works?* — **Yes, ~600 of them.** The
   Forum of Free Enterprise booklets, the A. D. Shroff Memorial Lecture, the
   annual union-budget analyses and the numbered occasional-paper runs all
   rendered as loose individual works.

The reason was structural, not just missing metadata: `publication.series` was
free text read by nothing except the agent API. Grouping on the site was done
by hardcoded heuristics in `lib/periodicals.ts` (gated to
`work_type: periodical_issue`) and `lib/lectures.ts` (gated to
`work_type: lecture`). A print series is neither, so it had no surface.

## What changed

**New `series` collection** (`apps/site/src/content/series/`, 10 entries) —
booklet runs, memorial lectures, occasional papers, annual analyses. One level
of nesting via `parent_series`.

**New fields on `publication`:**
- `series_id` — `reference('series')`, the thing `/series/` groups on. A work
  carries its **most specific** series.
- `series_ordinal` — the item's own printed number, when it states one.
- `series` — unchanged, still the free-text label as printed.

**New routes:** `/series/` (index of runs) and `/series/<id>/` (one run,
ordered by number where numbered, by date otherwise). Registered in the header
under Collections. Work detail pages now show "No. N in <series>".

**Wired through:** `lib/series.ts`, `agent-api.ts` (so MCP sees series_id and
ordinal), Sveltia `config.yml` (series collection + a relation widget on
primary works), `SCHEMA.md` Q2b.

## Two corrections to the data

**1. Twenty colophon dates were masquerading as series names.** The v1.4
extractor read the printer's line on the back page (`9/August/1962`,
`2.5/Aug./2014`, `7/Je/59`) as a series designation. Every one matches its own
record's date. These are cleared from `publication.series` and the
transcription preserved in `provenance.notes`.

Consequence: **the FFE booklets are not a numbered run.** They are ordered by
date. `numbered: false` on that series entity.

**2. Ordinals are only set where they are unambiguous.** Two traps:
- Records cite *other* lectures ("invoking Chagla's Ninth A. D. Shroff Memorial
  Lecture") — a cited ordinal is not this work's ordinal.
- The Forum's regional centres numbered their own runs. Mukharji's 1973 booklet
  is "the first ... under the auspices of the **Calcutta Centre**", not the
  first of the series.

Of 33 Shroff ordinals initially detected, 24 survived as unambiguous. Nine were
withheld where two works claim one number and neither can be shown to hold it —
the series page reports the gaps rather than guessing.

## How the data was produced

Three passes, deliberately cheap:

| Pass | Method | Resolved |
|---|---|---|
| 0 | `scripts/series/detect.py` — regex over the existing records (the evidence was already in the `summary` prose and `physical.format`) | 576 free |
| 1 | 3 × Haiku subagents over 30 ambiguous snippets | 27 members, 3 rejected |
| 2 | 1 × Haiku subagent over 7 ordinal-collision groups | 15 works adjudicated |

No PDFs were read and no Opus was spent: once the colophon-date finding ruled
out booklet numbering, everything needed was already in the markdown.
Total subagent cost ~265k Haiku tokens.

Artifacts kept as an audit trail: `scripts/series/detected.json`,
`assignments.json`, `shards/verdict-*.json`, `shards/conflict-verdict.json`.

## Open editorial items for CCS

1. **Two confirmed duplicate record pairs**, now cross-linked via
   `related_works` but not merged — someone should pick a survivor:
   - `corporate-governance-in-india-by-k-b-dadiseth-1997` ↔ `corporate-governance-in-india-k-b-dadiseth` (both the 32nd Shroff lecture, 1997)
   - `the-role-of-the-judiciary-in-parliamentary-democracy-m-c-chagla-28-october-1974` ↔ `the-role-of-judiciary-in-parliamentary-democracy-m-c-chagla-january-4-2011` (the 2011 item is a reprint of the 1974 ninth lecture)
2. **9 withheld Shroff ordinals** — resolvable only from the booklet covers.
   Listed as gaps on `/series/ad-shroff-memorial-lecture/`.
3. **Is per-centre numbering real?** If the Bombay, Calcutta, Delhi, Bangalore
   and Poona centres each ran their own numbered Shroff lecture, the series may
   need splitting or a `centre` qualifier. Worth one question to Kumar.
4. `minoo-masani-at-90-freedom-first-1995` is tagged `periodical_issue` but
   reads like a tribute compilation.
5. `regional-literature/` in the source batch is empty.

## Verification

`astro build` clean — 2,726 pages, no new errors or warnings (the
`periodicals collection is empty` notice and the 11 `astro check` errors in
`astro.config.mjs` / `Search.astro` / `ThinkerDetail.astro` are pre-existing).
`/series/`, all 10 run pages, and the work-detail series line checked in the
browser.
