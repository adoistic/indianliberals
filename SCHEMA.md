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
