# Cross-link audit — design spec

**Date:** 2026-05-18
**Author:** Adnan (collaborative session, this conversation)
**Status:** Approved for Phase A implementation

## Problem

Of 643 English Tier-A entries on the site, only 201 (31 %) have a structured thinker reference. The remaining **442 entries are unlinked** — their byline reads as plain text instead of a clickable link to the author's bio page, and the author's bio page does not list those entries as their work.

Distribution of the gap:

| Collection | Linked | Total | % | Unlinked | Root cause |
|---|---|---|---|---|---|
| musings | 0 | 224 | 0 % | 224 | No `author_name` field in frontmatter; author is in slug / body only |
| opinions | 0 | 61 | 0 % | 61 | `author_name: "Editorial Team"`; the real signal is *who the piece is about*, not who wrote it |
| interviews | 27 | 72 | 38 % | 45 | `subject_name` is the article title, not a person name |
| theprint-mirror | 48 | 48 | 100 % | 0 | (Already resolved in earlier pass.) |
| primary-works | 126 | 238 | 53 % | 112 | `byline_verbatim` set but not in `byline_lookup`; author either missing from authority or has a name variant not aliased |
| **Total** | **201** | **643** | **31 %** | **442** | — |

Adnan's goal stated in this conversation: *"there should not even be a single article which is not linked."*

## Three-role data model

The current schema and UI conflate two distinct relationships. Phase A formalises a three-role model:

| Role | Meaning | Bio-page section |
|---|---|---|
| **author** | The thinker wrote this piece. | "Works by [X]" |
| **subject** | This piece is a profile / interview *about* the thinker (someone else wrote it). | "Profile pieces and interviews about [X]" |
| **mention** | The thinker's name appears in the body but they are neither author nor subject. | "Mentioned in" |

The current schema supports the first two cleanly only for some collections. Phase A patches the gaps:

- **musings** — `author` (✅ exists) is the writer of the excerpt
- **opinions** — `subject` (🆕 add to schema) is the thinker the piece profiles; `author` stays as the writer (typically Editorial Team)
- **interviews** — `subject` (✅ exists) is the interviewee
- **primary-works** — `authors[]` (✅ exists) is the work's byline
- **theprint-mirror** — `related_thinkers[]` (✅ exists) carries the byline ref

The `mention` role is **not extracted in Phase A**. It is the explicit deliverable of Phase B (see "Future work" below).

## Phase A — scope (this spec)

### In scope

1. Resolve the **author** (musings, primary-works, theprint-mirror) or **subject** (opinions, interviews) for all 442 unlinked entries.
2. Add `subject: reference('thinkers').optional()` to the opinions schema.
3. Auto-create *minimal* stub thinker entries for any byline that looks like a real name but isn't in the authority. Stubs carry `bio_source: "ai_drafted_stub"` so Phase 1.5 can find them.
4. Split the thinker bio page into three labelled sections: Works by · Profile pieces about · Mentioned in.
5. Re-emit primary-works after authority expansion so the new `byline_lookup` resolves Mody, Narayan, et al.
6. Run-once cleanup: site builds clean, recount shows ≥ 95 % of entries linked.

### Explicitly out of scope (Phase A only)

- **In-prose name detection.** Body-text mentions inside musings, opinions, ThePrint articles, and especially the prose summaries of primary works (which routinely name multiple thinkers — e.g., Mody's volume summary names Shenoy and Narayan) are NOT extracted in Phase A. Phase B handles this.
- **AI-drafted full bios** for stub thinkers — content stays as a one-line placeholder noting "real bio drafting queued for Phase 1.5".
- **Cross-author relationship graph** ("Thinker A discussed Thinker B in this work") — Phase B.
- **Mention-of-mention** chains and the Wikipedia-style inline link treatment — Phase B.

## Future work — Phase B and beyond (explicit roadmap)

These items are deferred but **will happen**. Capturing them here so Phase A's design decisions don't paint Phase B into a corner.

### Phase 1.5 — AI-drafted bios for stub thinkers

After Phase A creates ~100–150 stub thinkers with `bio_source: "ai_drafted_stub"`, a follow-up pass uses `claude -p` to draft a 2–4-paragraph bio for each, drawing on the works they authored / pieces about them that are already in the corpus. Output replaces the stub body; `bio_source` flips to `"ai_drafted"` and `needs_review: true` for editorial.

### Phase B — In-prose mention linking (Wikipedia-style)

For every named-person reference inside the body of any article — including the prose summaries of primary-work pages — populate `related_thinkers[]` so the name renders as a hyperlink to that thinker's bio. Required because:

- A musing by Ashok Desai mentioning Manmohan Singh, Narasimha Rao, and B.R. Shenoy should let readers click straight from any of those names to the relevant bio.
- A primary-work summary noting "Prof. B. R. Shenoy diagnoses the food crisis…" should similarly link inline.
- An interview where one thinker discusses another should surface in *both* thinkers' "Mentioned in" lists.

Implementation outline (for the next engagement, not now):

- NER pass on every Tier-A body + every primary-work summary
- Resolve candidate spans against the (Phase-A-cleaned) `byline_lookup`
- Render inline `<a href="/thinkers/<slug>/">` in the body markdown via an Astro remark/rehype plugin
- Populate `related_thinkers[]` in frontmatter as the structured record

### Phase B.1 — Discussant graph

Beyond "X is mentioned in Y", surface "X discussed Y" as a directed edge in `data/synthesis/graph-edges/`. Drives a future "intellectual conversations" UI surface.

### Phase B.2 — Theme + work cross-linking

Same treatment for primary-work titles mentioned inside other works' summaries — the body of a musing mentioning *Indian Federalism by Granville Austin* should link to that primary-work page if it exists.

## Architecture (Phase A)

```
[content/ frontmatter on disk]
        │
        ▼
prepare-unlinked.py  →  data/synthesis/unlinked.jsonl
        │                  (one compact record per entry: title, slug,
        │                   body excerpt, current author/subject hint)
        ▼
[Interactive Claude session reads JSONL in batches of 30–50]
   For each entry, emits a resolution:
     { id, collection, primary_role, primary_thinker_id, create_stub?, new_thinker? }
        │
        ▼
data/synthesis/resolutions.jsonl
        │
        ▼
apply-resolutions.py
   • Validates: each match has a real thinker; each create_stub doesn't collide
   • Mutations: authority + byline_lookup append, stub thinker MDs created,
                content frontmatter refs written, residual logged
   • Idempotent: re-running is a no-op if data unchanged
        │
        ▼
emit-astro-md.py (re-emit primary-works)  ←  picks up expanded byline_lookup
        │
        ▼
astro build                                ←  verifies references validate
        │
        ▼
audit-coverage.py                          ←  confirms <5% residual
```

## Per-collection resolution rules

| Collection | Where the author/subject lives | LLM signal payload |
|---|---|---|
| **musings** | End of slug (`...-ashok-desai-1995`), or "Authored by X" in body opener, or inherit from `excerpt_of` primary-work | slug, title, first 300 chars of body |
| **opinions** | Title prefix before `:` or `-` is the subject (most pieces are profiles) | title, first 300 chars of body |
| **interviews** | Title prefix before ` - ` or ` on ` is the subject | title only (body is usually a transcript stub) |
| **primary-works** | `byline_verbatim` from `metadata.contributors[]` — already a parsed name string | DETERMINISTIC, no LLM needed |

For primary-works the resolver pass is purely a byline_lookup expansion + stub-creation script. No LLM call.

## Stub thinker shape

```yaml
---
id: "p-s-narayan"
name:
  canonical: "P. S. Narayan"
  sort: "Narayan, P. S."
  also_known_as: []
tradition: classical_liberal     # best heuristic; default if uncertain
nationality: india               # default
themes: []
affiliations: []
bio_source: "ai_drafted_stub"    # NEW enum value vs existing canonical/feature/ai_drafted/imported
needs_review: true
draft: false                     # visible — consistent with the earlier visibility decision
ai:
  drafted_by: "interactive-claude-session"
  drafted_at: "2026-05-18"
  model_version: "linking-audit-v1"
---

# P. S. Narayan

*Entry created during the cross-link audit. A real biographical pass is queued for Phase 1.5.*
```

The body is intentionally minimal. Phase 1.5 grep-targets `bio_source: ai_drafted_stub` to find every stub needing a real bio.

## Error handling

- **Compound bylines** like "Sir Homi Mody, S.L. Kirloskar, and M.R. Ramnivas Ruia" split into three separate authors at apply time.
- **Collision check before create_stub** — if `anandibai-joshee` already exists in the authority, downgrade the action to `match` and re-use the existing record.
- **Idempotence** — entry with `author: "..."` already set is left untouched. Apply step re-runs safely.
- **Schema patch ordering** — opinions schema gets the `subject` field before any opinion entry is written with it.
- **Residual logging** — any entry the resolver leaves unresolved (truly ambiguous, no name extractable) is appended to `data/synthesis/audit-residual.txt` for editorial review. Not blocking.

## Success criteria

| Metric | Target |
|---|---|
| Unlinked entries after Phase A | ≤ 22 (≥ 95 % coverage) |
| Stub thinkers created | ~100–150 |
| Astro build | Clean (no broken references) |
| Pagefind reindex | Succeeds; ≥ same word count as before |
| Bio page split visible | A.D. Shroff page renders three distinct sections |
| Editorial residual file | Created and committed |

## Migration / rollout

This is a one-shot historical migration. Once Phase A applies, the resolutions are baked into frontmatter and the new content collections, and forward-going work (new musings, new ThePrint ingest, new primary-work extractions) writes the resolved refs directly via the updated `emit-astro-md.py` + the ThePrint worker.

No rollback plan beyond `git revert` — the changes are confined to:
- `apps/site/src/content/` (frontmatter edits)
- `apps/site/src/content/thinkers/` (new stub MDs)
- `data/authority/thinkers.json` (new entries + new byline_lookup keys)
- `apps/site/src/content.config.ts` (one-field schema addition)
- `apps/site/src/pages/thinkers/[slug].astro` (three-section split)
- `scripts/synthesis/{prepare-unlinked,apply-resolutions}.py` (new files)

## Open questions

None outstanding. Phase B is explicitly deferred per Adnan's call. Phase 1.5 (AI-drafted bios) is queued for after the runner's claude-p budget recovers.
