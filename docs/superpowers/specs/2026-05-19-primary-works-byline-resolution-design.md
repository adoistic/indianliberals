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
    stubs_referenced: z.array(z.string()).default([]),  // stubs created earlier in this run
    collisions_logged: z.array(z.string()).default([]),  // existing-thinker slug-collisions hit silently
  })
  .optional(),
```

This is a transparency field — the curator can later filter `authors_resolution.method == 'vision'` to find entries where the byline came from a low-signal source. The `stubs_referenced[]` field distinguishes "stub created by THIS work" (in `stubs_created[]`) from "stub created earlier this run, referenced here" so the curator can trace stub origin from any one work. The `collisions_logged[]` field captures cases where a generated stub slug already existed in the thinker collection — see §6 for the safety net.

**Confidence semantics (locked rubric the prompt + applier both honor):**

| Level | Meaning | Examples |
|---|---|---|
| `high` | Exact slug match OR initialism-normalized match against an existing thinker, AND unambiguous (single match across all token candidates). Or LLM/vision sees an unambiguous signed byline on the title page. | Title `... by A. D. Shroff ...` → exact-matches thinker slug `a-d-shroff` |
| `medium` | LLM/vision identifies a plausible match but with hedging — initials ambiguous, or token matches multiple thinkers and LLM picks one via context. Stub auto-creation also defaults to `medium` (we believe the name is right but the person is new). | Title `... by R. Cooper ...` matches both `r-c-cooper` and `r-d-cooper`; LLM picks one based on year/topic context |
| `low` | LLM/vision returns a name but signals weak evidence — name not on title page, only inferred from elsewhere in body or from the publisher's house-style attribution. Vision-source default is `low` unless the title page carried a strong signature. | "Implications of Bank Nationalisation, Misc 1964" — no title-page byline; LLM proposes via house-style heuristic |

**Stub thinkers** — minimal frontmatter, no body. The `tradition` enum in `apps/site/src/content.config.ts` currently has six values (`classical_liberal`, `reformer`, `nationalist_liberal`, `social_reformer`, `contemporary_liberal`, `international_influence`); a seventh value `unclassified` must be added in this pass so auto-created stubs can honestly defer that classification to curator review rather than soft-defaulting to `contemporary_liberal`.

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

**Schema delta required:** add `'unclassified'` to the `tradition` enum at `apps/site/src/content.config.ts:49-56`. One-line change. Existing 453 thinkers continue to validate since the enum is widened, not narrowed.

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

The `token_candidates[]` array is a heuristic split of `title` + `slug` on common separators (`by`, `—`, `·`, `:`, `,`, em-dash, en-dash, slash). Each resulting token is then:

1. Lowercased and re-kebab-cased (whitespace + punctuation → single hyphen).
2. Filtered against an explicit drop-list:
   - **Honorifics** (whole tokens): `dr`, `dr.`, `mr`, `mr.`, `mrs`, `mrs.`, `ms`, `ms.`, `prof`, `prof.`, `shri`, `sir`, `sri`, `smt`, `lady`, `lord`.
   - **Years**: regex `\b(19|20)\d{2}\b` matched anywhere in the token (catches `1956`, `feb11-1956`, `1972a`).
   - **Month names + abbreviations**: `january`, `february`, …, `december`, `jan`, `feb`, `mar`, …, `dec`, `jan2`, `feb11`-style date+digit hybrids (the year regex catches the trailing-digits form; bare month names handled by the allow-list).
   - **Day ordinals + numerals**: regex `^[0-9]+(st|nd|rd|th)?$` (catches `1st`, `25`, `25th`).
   - **Roman ordinals** for conference labels: `^[ivxlcdm]+$` (catches `iii`, `xviii`).
   - **The literal token `by`** that survives split-on-em-dash (e.g., title fragment `... — by Sharad Joshi`).
3. Empty tokens after filtering are discarded. Tokens with internal hyphens (e.g., `a-d-shroff`) are preserved as-is — they are the canonical thinker-slug shape.

The full filter list lives in `scripts/synthesis/prepare-byline-batches.py` as a module-level constant so both implementer and reviewer can audit it.

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

**Per-entry decision tree the subagent applies** (this rubric lives in the system prompt):

```
For each input entry, look at title + slug + thinkers list. Then:

1. Can you find a high-confidence single match? → emit { matches: [...], confidence: "high" }
2. Multiple plausible matches via context (year/topic/publisher)? → pick one,
   emit { matches: [...], confidence: "medium" }
3. A name is clearly present but isn't in the thinkers list? → emit
   { unknowns: ["Name as it appears"], confidence: "medium" }  (applier will stub)
4. A name is hinted but you cannot be confident enough to commit a stub? → emit
   { needs_vision: true }  (Step 3 reads the PDF)
5. No name signal anywhere in title/slug? → emit
   { needs_vision: true }
```

Crucially: branches (3) and (4) are distinct. (3) means "I see the name, but it's a new person" — auto-stub. (4) means "I'm not sure there even IS a name to extract" — defer to vision. The system prompt's worked examples must demonstrate both paths so the subagent doesn't conflate them.

Expected: ≥80% of deferred entries resolve here. Remainder flagged `needs_vision: true`.

### Step 3 — Vision fallback (per-entry subagents)

For entries flagged `needs_vision`, dispatch one Claude vision subagent per entry. Each reads the PDF at `pdf_staging_path` with `pages: "1-3"` (title page + copyright + opening) and emits a match record. Output: `data/byline-resolve/vision-output-<id>.json`.

Expected count: ~20 entries. If a PDF doesn't exist at the staging path, the subagent emits `unresolved: true` and the applier leaves that entry unbylined.

### Step 4 — Apply (`apply-byline.py`)

Walks all three output sources (deterministic, LLM, vision) and merges per entry. **Process order matters**: deterministic outputs apply first (most confident), then LLM, then vision — so a deterministic hit can't be overwritten by a lower-confidence vision pass.

**Author routing rule** (one place; resolves the multi-author edge case):
- Every matched name with `role` ∈ {`author`, unspecified, missing} → `authors[]`.
- Every matched name with `role` ∈ {`editor`, `translator`, `foreword`, `introduction`, `preface`} → `contributors[]` with that role.
- Multiple authors all → `authors[]` (preserves array semantics).
- No `work_type` change is made based on author count.

**Stub creation algorithm** (the heart of the safety net):

```
For each unknowns[] name N in the entry's resolution record:
  slug = kebab(N.lower())
  if thinker MD already exists at apps/site/src/content/thinkers/<slug>.md:
    # could be (a) a stub we created earlier in THIS run, or
    # (b) a pre-existing real thinker who happens to share the slug
    if slug is in this run's `run_stubs_created_set` (in-memory):
      # case (a): silent dedup, expected
      add slug to authors_resolution.stubs_referenced
    else:
      # case (b): potential mis-attribution — could be the right person OR a namesake
      add slug to authors_resolution.collisions_logged
      log a line to data/byline-resolve/collisions.log with: entry id, name N,
        existing slug, existing thinker canonical name
      DO link the primary-work to this thinker (per §3 the spec accepts namesake collisions
      as rare, prioritising coverage over a tiny risk of mis-attribution)
  else:
    write stub MD per §4 shape
    add slug to authors_resolution.stubs_created AND to run_stubs_created_set
```

The applier therefore produces three audit signals per entry: `stubs_created[]` (newly minted), `stubs_referenced[]` (created earlier in this run), `collisions_logged[]` (pre-existing thinker hit — curator must verify identity).

**Provenance writeback**: write `authors_resolution` with `confidence`, `method`, `proposed_unknowns`, `stubs_created`, `stubs_referenced`, `collisions_logged`.

**Needs-review flag**: set `needs_review: true` when ANY of: confidence is medium/low, `stubs_created` non-empty, `collisions_logged` non-empty, or no authors were resolved at all (genuinely unresolved entries — vision PDF missing, all signals exhausted).

Idempotent — re-running with the same outputs is a no-op (existing matches preserved).

### Step 5 — Audit (`audit-byline-coverage.py`)

Generates `data/byline-resolve/coverage-report.md` with:
- Total primary-works with `authors[]` populated (out of 378).
- Of the 179 originally unbylined: count by method (deterministic / llm / vision / unresolved).
- Confidence breakdown across all resolved.
- Number of stub thinkers created in this run; list of slugs.
- Number of `stubs_referenced[]` events (stub already-created-this-run reuse).
- Number of `collisions_logged[]` events; full list of (primary-work id, name, existing-thinker slug) tuples for curator inspection.
- Top `proposed_unknowns` frequencies (sanity — should be ~empty after auto-stubbing).

**Also writes an explicit review queue** at `data/byline-resolve/curator-queue.md` — a flat list of every primary-work whose post-apply state satisfies any of: `authors_resolution.method == 'vision'`, `confidence != 'high'`, `stubs_created` non-empty, `collisions_logged` non-empty, or unresolved. This is the curator's single actionable file after the apply pass — they don't need to read the aggregate report to know which entries need eyeballs.

## 6. Error handling

- **PDF missing at staging path** (Step 3) — entry stays unresolved; logged; not a pipeline failure.
- **LLM batch JSON malformed** — log to `data/byline-resolve/dispatch.log`, re-dispatch the single batch.
- **Stub slug collides with an existing thinker entry** — applier checks existence first; if exists, the primary-work just references that existing thinker. Collision is silent on the assumption it's the same person (rare namesake collisions accepted per §3).
- **Multiple stubs created for the same person** (e.g., subagent emits both "A.D. Shroff" and "Ardeshir Shroff") — accepted as v1 limitation; later dedup pass can merge by `also_known_as` expansion.
- **Deterministic ambiguous match** (token matches multiple thinkers) — never auto-resolved; always deferred to Step 2 for LLM judgment.

## 7. Acceptance metrics

| Dimension | Target |
|---|---|
| Of the 179 originally unbylined: total resolved by any method | ≥95% (~170 entries) |
| Of those resolved: deterministic-hit share | ≥40% (~70 of ~170) |
| primary-works with `authors[]` populated post-run (out of 378) | ≥97% (= 199 already + ~170 newly = ~369 of 378) |
| Stub thinkers auto-created | ≤80 (rough budget; if exceeded, surface for curator review before commit) |
| `collisions_logged` events | ≤5 (more than this suggests an over-eager stub-naming heuristic — pause and audit) |
| Build clean post-merge | yes |
| `needs_review: true` flag on entries with low-confidence, stub-created, or collision-logged bylines | yes |

(The 9 unresolved entries — ~5% of 179 — stay unbylined and flagged. Out of scope to chase the long tail past 95%.)

## 8. Out of scope (recap)

- Re-litigating the 199 already-bylined entries
- FRBR / manifestations
- Curator bio expansion of auto-stubs
- Slug-collision dedup
- The 49 non-English primary-works whose `authors[]` was already populated in earlier passes — they're already handled

## 9. Dependencies

- `apps/site/src/content.config.ts` — two changes: (a) add `authors_resolution` optional object to primary-works schema; (b) add `'unclassified'` to the `tradition` enum (six → seven values).
- `scripts/synthesis/prepare-byline-batches.py` — new.
- `scripts/synthesis/resolve-byline-deterministic.py` — new.
- `scripts/synthesis/prepare-byline-llm-batches.py` — new.
- `scripts/synthesis/prompts/system-byline.txt` — new (thinkers list + matching rubric + worked examples covering branches 1–5 in §5 Step 2).
- `scripts/synthesis/apply-byline.py` — new.
- `scripts/synthesis/audit-byline-coverage.py` — new.
- `data/byline-resolve/` — new directory for batch + output artefacts. Contains: `candidates.jsonl`, `deterministic-resolved.jsonl`, `deferred.jsonl`, `llm-batch-NN.jsonl`, `llm-output-NN.json`, `vision-output-<id>.json`, `dispatch.log` (per-subagent failure log, matching the convention used in `data/classify/`), `collisions.log` (Step 4 stub-collision events), `coverage-report.md`, `curator-queue.md`.

**Loader robustness note:** the deterministic pass (§5 Step 1) builds its thinker lookup by reading `apps/site/src/content/thinkers/*.md` frontmatter. Thinkers with `also_known_as: []` (empty list) are common — the loader must treat empty lists as "no aliases" and continue, not fail on the empty-array case.

## 10. Execution model

Same Max session as the classification + extraction passes. Multiple Claude Agent subagent dispatches per wave (visible as chips in the monitoring UI). Total dispatches expected:

- Step 2: ~5 batches × ~20 entries = ~5 dispatches
- Step 3: ~20 vision dispatches
- Total: ~25 subagent dispatches across the whole pipeline

Estimated total token consumption (see brainstorm conversation log, 2026-05-19):

| Step | Per-dispatch | Dispatches | Subtotal |
|---|---|---|---|
| Step 1 deterministic Python | 0 | n/a | 0 |
| Step 2 LLM batch | ~15K–25K | ~5 | ~75K–125K |
| Step 3 vision per-entry | ~10K–15K | ~20 | ~200K–300K |
| **Total** | | | **~275K–425K** |

## 11. Open questions

None at design-lock time. Anything that surfaces during implementation rolls into a v1.1 follow-up.
