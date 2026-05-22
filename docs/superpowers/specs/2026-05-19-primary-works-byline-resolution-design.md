# Primary-works byline resolution — design spec

**Author:** Adnan
**Date:** 2026-05-19
**Status:** Draft (pre-review)
**Adjacent specs:**
- `2026-05-18-phase-b-ner-handoff.md` — Phase B NER (cross-link mentions)
- `2026-05-18-musings-opinions-classification-design.md` — classification pipeline (architectural precedent)

---

## 1. Problem

Of 378 primary-works in the corpus, **179 have neither `authors[]` nor `contributors[]` populated** — about half of every listing card on `/primary-works/` shows no "By X" line. The Forum-of-Free-Enterprise speeches from the 1956–80 era are the largest cohort. The author name is almost always visible in `title.main` or in the entry slug (e.g., `free-enterprise-and-democracy-a-d-shroff-feb11-1956`); Phase A's `resolve-bylines.py` covered opinions, interviews, and theprint-mirror but skipped primary-works.

This spec defines a four-pass pipeline that bylines the 179 unmatched primary-works, auto-creates minimal stub thinker entries for any author not already in the 453-thinker collection, and routes ambiguous cases through a PDF-vision fallback.

## 2. Goal

Land bylines on ≥95% of the 179 unbylined primary-works. Auto-create stub thinker entries for unmatched author names so the cross-collection link graph stays complete. Track resolution provenance so the curator can audit which entries were matched deterministically vs which needed LLM judgment vs vision.

## 3. Non-goals

- **No re-litigation of the 199 already-bylined entries.** They keep their existing `authors[]`. If Phase A made a wrong call, that's a separate cleanup pass.
- **No FRBR / manifestations work.** Out of scope.
- **No curator-driven bio expansion of auto-created stubs.** They ship with `needs_review: true`; expansion is a later pass.
- **No namesake disambiguation across stubs.** Slug-collision (two distinct unmatched "A.D. Shroff"-shape names landing on the same slug) is accepted as a rare edge case.
- **No vision pass on PDFs that don't exist.** Roughly all 378 PDFs are on the external drive at the staging paths in frontmatter; if a PDF is missing at apply-time, the entry stays unresolved and flagged.

## 4. Schema additions

The primary-works schema already has the target fields:
- `authors: z.array(reference('thinkers')).default([])`
- `contributors: z.array({thinker, thinker_unresolved, role, toc_index}).default([])`

No structural changes to those. **One new optional provenance object** captures how each entry was resolved:

```ts
// In primary-works defineCollection (apps/site/src/content.config.ts):
authors_resolution: z
  .object({
    confidence: z.enum(['high', 'medium', 'low']).optional(),
    method: z.enum(['deterministic', 'llm', 'vision']).optional(),
    proposed_unknowns: z.array(z.string()).default([]),
    stubs_created: z.array(z.string()).default([]),
  })
  .optional(),
```

This is a transparency field — the curator can later filter `authors_resolution.method == 'vision'` to find entries where the byline came from a low-signal source.

**Stub thinkers** — minimal frontmatter, no body:

```yaml
---
id: <kebab-slug>
name:
  canonical: "<Name as it appeared in title>"
  sort: "<Last, First>" if invertible, else canonical
  also_known_as: []
tradition: unclassified
nationality: india
themes: []
affiliations: []
bio_source: ai_drafted_stub
needs_review: true
draft: false
ai:
  drafted_by: claude-sonnet-4.6
  drafted_at: <today>
  model_version: byline-resolve-<date>
---
```

No body content. The frontmatter is enough for listing-card rendering and for the primary-work's `authors[]` ref to resolve. The thinker collection currently has 125 entries with `bio_source: ai_drafted_stub` — this expands that cohort.

## 5. Pipeline (Approach A: deterministic Python first, LLM cleanup, vision fallback)

Five steps. All scripts under `scripts/synthesis/`. Dispatch model: same as classification + extraction passes — Claude `Agent`-tool subagents inside the Max session (no `claude -p`, no API budget).

### Step 0 — Build candidate set (`prepare-byline-batches.py`)

Walks the 179 entries where `len(authors) == 0` AND `contributors` has no thinker refs. For each, emits a candidate JSONL record:

```json
{
  "id": "free-enterprise-and-democracy-a-d-shroff-feb11-1956",
  "title": "Free Enterprise and Democracy",
  "slug": "free-enterprise-and-democracy-a-d-shroff-feb11-1956",
  "work_type": "speech",
  "year": 1956,
  "pdf_staging_path": "PDFs-by-publisher/forum-of-free-enterprise/...",
  "token_candidates": ["a-d-shroff", "feb11", "1956"]
}
```

The `token_candidates[]` array is a heuristic split of `title` + `slug` on common separators (`by`, `—`, `·`, `:`, `,`), with honorifics stripped (`Dr.`, `Mr.`, `Prof.`, `Shri`, `Sir`) and dates / month names dropped via a small allow-list.

Output: `data/byline-resolve/candidates.jsonl` (179 records).

### Step 1 — Deterministic Python pass (`resolve-byline-deterministic.py`)

Loads the 453 thinkers into a normalized lookup:

```python
{
  "a-d-shroff": "a-d-shroff",
  "ardeshir-darabshaw-shroff": "a-d-shroff",  # also_known_as → canonical
  "milton-friedman": "milton-friedman",
  ...
}
```

For each candidate, attempts to match any token to any lookup key. Match rules:
1. **Exact slug match** → `confidence: high, method: deterministic`.
2. **Initialism normalization** — `a-d-shroff` matches `a-d-shroff`; `adshroff` does not (initialism dots and hyphens are normalized to single hyphens before lookup).
3. **Ambiguous** (≥2 matches across tokens) → defer to Step 2.
4. **No match** → defer to Step 2.

Output: `data/byline-resolve/deterministic-resolved.jsonl` (the confident hits) + `data/byline-resolve/deferred.jsonl` (the rest).

Expected: ≥40% of the 179 (~75 entries) resolved here at zero LLM cost.

### Step 2 — Subagent batched LLM matching

`prepare-byline-llm-batches.py` chunks `deferred.jsonl` into batches of ~20 entries. Each batch file is `data/byline-resolve/llm-batch-NN.jsonl`. The system prompt at `scripts/synthesis/prompts/system-byline.txt` inlines:
- The full thinkers list: 453 entries × `(canonical, also_known_as[])` ≈ 6KB.
- The matching rubric with worked examples (initialism / role detection / unknown-author flagging).
- The output schema (one record per entry: `{id, matches[], unknowns[], needs_vision, confidence, role?}`).

Dispatch waves of 8–10 parallel `Agent` subagents (matches the classification / extraction precedent). Each subagent emits `data/byline-resolve/llm-output-NN.json`.

Expected: ≥80% of deferred entries resolve here. Remainder flagged `needs_vision: true`.

### Step 3 — Vision fallback (per-entry subagents)

For entries flagged `needs_vision`, dispatch one Claude vision subagent per entry. Each reads the PDF at `pdf_staging_path` with `pages: "1-3"` (title page + copyright + opening) and emits a match record. Output: `data/byline-resolve/vision-output-<id>.json`.

Expected count: ~20 entries. If a PDF doesn't exist at the staging path, the subagent emits `unresolved: true` and the applier leaves that entry unbylined.

### Step 4 — Apply (`apply-byline.py`)

Walks all three output sources (deterministic, LLM, vision) and merges per entry:

1. **Matched authors** → write to `authors[]` (single-author works) or `contributors[]` with role when role is `editor` / `translator` / `foreword`. Default role = `author` → `authors[]`.
2. **For each `unknowns[]` name**: synthesize a slug (`kebab(name.lower())`), check if a thinker MD already exists at that slug. If not, create the stub with the frontmatter shape in §4. Track in `stubs_created[]`.
3. **Write `authors_resolution`** with `confidence`, `method`, `proposed_unknowns`, `stubs_created`.
4. **Set `needs_review: true`** when confidence is medium/low OR stubs_created is non-empty.

Idempotent — re-running with the same outputs is a no-op (existing matches preserved).

### Step 5 — Audit (`audit-byline-coverage.py`)

Generates `data/byline-resolve/coverage-report.md` with:
- Total primary-works with `authors[]` populated (target ≥99%).
- Of the 179 originally unbylined: count by method (deterministic / llm / vision / unresolved).
- Confidence breakdown.
- Number of stub thinkers created; list of slugs.
- Top `proposed_unknowns` frequencies (sanity check — should be empty after auto-stubbing).

## 6. Error handling

- **PDF missing at staging path** (Step 3) — entry stays unresolved; logged; not a pipeline failure.
- **LLM batch JSON malformed** — log to `data/byline-resolve/dispatch.log`, re-dispatch the single batch.
- **Stub slug collides with an existing thinker entry** — applier checks existence first; if exists, the primary-work just references that existing thinker. Collision is silent on the assumption it's the same person (rare namesake collisions accepted per §3).
- **Multiple stubs created for the same person** (e.g., subagent emits both "A.D. Shroff" and "Ardeshir Shroff") — accepted as v1 limitation; later dedup pass can merge by `also_known_as` expansion.
- **Deterministic ambiguous match** (token matches multiple thinkers) — never auto-resolved; always deferred to Step 2 for LLM judgment.

## 7. Acceptance metrics

| Dimension | Target |
|---|---|
| primary-works with `authors[]` populated (out of 378) | ≥99% |
| Of 179 originally unbylined: deterministic hits | ≥40% (~75 entries) |
| Of 179: total resolved by any method | ≥95% (~170 entries) |
| Stub thinkers auto-created | ≤80 (rough budget) |
| Build clean post-merge | yes |
| `needs_review: true` flag on entries with low-confidence or stub-created bylines | yes |

## 8. Out of scope (recap)

- Re-litigating the 199 already-bylined entries
- FRBR / manifestations
- Curator bio expansion of auto-stubs
- Slug-collision dedup
- The 49 non-English primary-works whose `authors[]` was already populated in earlier passes — they're already handled

## 9. Dependencies

- `apps/site/src/content.config.ts` — schema addition for `authors_resolution` (one optional object).
- `scripts/synthesis/prepare-byline-batches.py` — new.
- `scripts/synthesis/resolve-byline-deterministic.py` — new.
- `scripts/synthesis/prepare-byline-llm-batches.py` — new.
- `scripts/synthesis/prompts/system-byline.txt` — new (thinkers list + matching rubric + worked examples).
- `scripts/synthesis/apply-byline.py` — new.
- `scripts/synthesis/audit-byline-coverage.py` — new.
- `data/byline-resolve/` — new directory for batch + output artefacts.

## 10. Execution model

Same Max session as the classification + extraction passes. Multiple Claude Agent subagent dispatches per wave (visible as chips in the monitoring UI). Total dispatches expected:

- Step 2: ~5 batches × ~20 entries = ~5 dispatches
- Step 3: ~20 vision dispatches
- Total: ~25 subagent dispatches across the whole pipeline

Estimated total token consumption: ~300K–500K (see brainstorm conversation log, 2026-05-19).

## 11. Open questions

None at design-lock time. Anything that surfaces during implementation rolls into a v1.1 follow-up.
