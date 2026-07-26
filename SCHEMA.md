# SCHEMA.md

The cataloging schema for the Indian Liberals corpus.

This document is the source of truth for two things at once:
1. **The librarian-grade input** to the AI metadata extraction prompts in `scripts/extract.ts`.
2. **The editor handbook** for CCS staff adding new records through Sveltia CMS.

It is written in this order deliberately: extraction reads first, editors read second. If a question is unclear to either audience, the answer in this document is wrong.

## Status

**Phase 0 work in progress.** This file currently contains the empty headings for the eight schema decisions (Q1-Q8) that need first-call positions before the Phase 0 spike runs. Each section will be filled in by Adnan acting as librarian-archivist-historian for the Indian liberal corpus.

## Q1. Work vs manifestation modelling

*To be drafted in Phase 0 week 1. See design doc for decision criteria.*

## Q2. Periodical depth

*To be drafted in Phase 0 week 1.*

### Q2b. Series vs periodicals vs lectures (2026-07-26)

Three surfaces group works into runs, and they must not overlap:

| Surface | Keyed on | Covers |
|---|---|---|
| `/periodicals/` | `work_type: periodical_issue` | dated issues of a serial — Freedom First, The Indian Libertarian, Khoj, Shetkari Sanghatak |
| `/lectures/` | `work_type: lecture` | video recordings of annual/memorial lectures |
| `/series/` | `publication.series_id` → `series` collection | named **non-periodical print runs** — publisher booklet series, printed memorial lectures, numbered occasional papers, recurring annual analyses |

**Why a third surface.** ~600 works in the archive were published as part of a
run but are not periodical issues: the Forum of Free Enterprise booklets, the
A. D. Shroff Memorial Lecture, the annual union-budget analyses. Before this
they rendered as loose standalone works, because `publication.series` was
free-text consumed by nothing but the agent API. `series_id` is a real
`reference('series')`, so grouping is editor-controllable from Sveltia rather
than by slug regex.

**Field split on `publication`:**
- `series` — free text exactly as printed on the item ("Sixth A. D. Shroff Memorial Lecture"). Descriptive; groups nothing.
- `series_id` — reference into the `series` collection. A work carries its **most specific** series (an A. D. Shroff lecture gets `ad-shroff-memorial-lecture`, not the parent `ffe-booklets`); nesting is expressed by `parent_series` on the series entity.
- `series_ordinal` — this item's own printed number, when it states one.

**Two rules learned the hard way:**

1. *The FFE booklets are not numbered.* The colophon on the back page carries
   the printing date (`9/August/1962`), not a booklet number. The v1.4
   extractor read 20 of these as series designations; they have been cleared
   into `provenance.notes`. Set `numbered: false` for date-ordered runs.
2. *A cited ordinal is not this work's ordinal.* Records frequently reference
   another lecture in the run ("invoking Chagla's Ninth A. D. Shroff Memorial
   Lecture"). And the Forum's regional centres numbered their own local runs —
   Mukharji's 1973 booklet is "the first ... under the auspices of the Calcutta
   Centre", not the first of the series. Where two works claim one number and
   neither can be shown to hold it, `series_ordinal` is left unset rather than
   guessed; the series page reports the gaps.

## Q3. Authority files (authors, publishers, organisations)

**First-call position (2026-05-16):** pre-populate. Library practice — draft the authority file first (even if incomplete), have the LLM map extracted names against it, flag unmatched for human review. The alternative (let extraction propose free text, normalise later) is faster on day one and dramatically worse after the first 50 records.

**Data lives in three YAML files:**
- `content/authority/thinkers.yaml` — people (authors, profile subjects, contributors)
- `content/authority/organisations.yaml` — institutions (parties, think tanks, movements)
- `content/authority/publishers.yaml` — imprints (overlapping with organisations where an org also publishes — captured via `org_ref`)

**ID rules:**
- IDs are kebab-case slugs, immutable once committed (renaming is a migration)
- IDs use the canonical-name form, not the formal-name form (`rajaji` not `chakravarti-rajagopalachari`)
- For figures with strong initials-based names (`b-r-shenoy`, `m-r-pai`, `s-v-raju`) the initials form is the slug
- Cross-references between files use the ID (e.g., a thinker's `affiliations` is a list of organisation IDs)

**Coverage check (post-spike):** seeded authority files must cover ≥75% of corpus mentions in the spike — per the per-mention definition in the design doc's Phase 0 acceptance criterion (b). If the bar misses, the remediation is to expand the seed, not to lower the bar.

**Status (2026-05-16):** first cut written. ~20 thinkers, ~14 organisations, ~10 publishers. Substantial NEEDS REVIEW gaps remain — see the candidates lists at the bottom of each YAML file. Adnan's pass to expand to the design-doc target (~30 thinkers, ~15 organisations, ~10 publishers) happens against the WordPress URL inventory once it's in hand.

## Q4. Theme controlled vocabulary

*To be drafted in Phase 0 week 1. Target: 20-30 controlled themes.*

## Q5. Provenance and rights

*To be drafted in Phase 0 week 1.*

Suggested `rights` shape (to confirm):
```yaml
rights:
  status: public_domain | fair_use_educational | permission_granted | takedown_on_request | unknown
  pd_year: int  # nullable
  editorial_review_flag: bool
  rights_notes: string  # nullable
```

## Q6. Multilingual title and name handling

*To be drafted in Phase 0 week 1.*

## Q7. Tier promotion hooks

*To be drafted in Phase 0 week 1. Schema accommodates `paragraph_ids[]` and `clean_markdown_url` as nullable fields now, empty in v1.*

## Q8. AI provenance and editorial-review fields

*To be drafted in Phase 0 week 1.*

Suggested per-record fields:
- `ai_extracted_at` — ISO timestamp
- `ai_model` — e.g., `claude-opus-4-7`
- `ai_prompt_version` — short hash or semver of the extraction prompt
- `needs_review` — bool, defaults true on first extraction, false after librarian sign-off

## Eval-plan section

*To be drafted in Phase 0 week 1.* This captures the decision on who authors the eval questions (Adnan default, per the design doc's Hidden Premise C).
