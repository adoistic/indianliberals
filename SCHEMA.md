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

*To be drafted in Phase 0 week 1. Seed list: ~30 thinkers, ~15 organisations, ~10 publishers.*

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
