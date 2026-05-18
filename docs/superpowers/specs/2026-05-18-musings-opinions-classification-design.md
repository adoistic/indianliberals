# Classification pass for musings & opinions — design spec

**Author:** Adnan
**Date:** 2026-05-18
**Status:** Draft (pre-review)
**Adjacent specs:**
- `2026-05-18-phase-b-ner-handoff.md` — Phase B in-prose NER (already shipped)
- `2026-05-18-phase-b-scope-and-b2-audio.md` — Phase B scope deltas + audio plan

---

## 1. Problem

The site has three content collections with parallel intent — `primary-works`, `musings`, `opinions` — but only `primary-works` has been through a classification pass. The other two collections carry "themes" that are CMS bucket labels, not subject taxonomy:

- **musings** (200 entries): 175 have themes; `so-musings` ×169, `forum-of-free-enterprise-periodicals` ×3, `indian-libertarian-periodicals` ×3, `marathi-articles` ×1, `lectures` ×1.
- **opinions** (61 entries): 60 have themes; all are `"opinions"` ×57 or `"events"` ×4.
- **primary-works** (378 entries): 173 have substantive themes — `economic-policy`, `free-enterprise`, `democracy`, `rule-of-law`, etc.

As a result, the theme filter on `/musings/` and `/opinions/` is dead — clicking a chip returns either 169 unhelpful results or a no-op. Users cannot answer questions like "show me musings about democracy" or "show me opinions on economic reform".

This spec defines a classification pass that brings musings and opinions to filter-parity with primary-works on subject taxonomy, plus adds six other dimensions chosen for cross-collection utility.

## 2. Goal

Run a single classification pass over all musings (200) and opinions (61) that:

1. Populates substantive `themes[]` using the locked primary-works vocabulary.
2. Adds six new classification dimensions: `kind`, `period_window`, `key_concepts[]`, `pull_quote`, `stance`, `geographic_scope` — plus a `proposed_themes[]` overflow bucket for curator review.
3. Migrates the existing bucket-label "themes" into a new `source_channel` field so provenance is preserved separately from subject.
4. Surfaces all of this as filter facets in the existing JSTOR-style sidebars on `/musings/` and `/opinions/`.
5. Uses parallel subagents inside the Max session — zero `claude -p` budget consumption.

## 3. Non-goals

- **No summary pass.** Musings are already curated excerpts; opinions are already short-form editorial. They don't need an `ai_summary` field.
- **No re-classification of primary-works themes.** Their themes are already populated; cleanup (name-strings like `Sharad Joshi`, possible vocab drift) is a separate downstream pass.
- **No `liberal_lineage` classification.** Considered and cut — it's a contested dimension that Indian scholars would disagree fiercely about. Revisit after curator review. Note that `stance` partly covers what `liberal_lineage` would have addressed (pro-market/anti-intervention is implicit in argues-for/argues-against patterns over time).
- **No reading-paths or themes-collection updates.** Downstream of new vocabulary; deferred.
- **No `source_channel` sidebar facet (v1).** The field gets populated but isn't surfaced yet. Curator can decide later whether it deserves a chip row.
- **No interview classification.** Interviews are a separate Phase B-2 (audio) effort.

## 4. Schema additions

Two collections get the same set of new fields, except `kind` (per-collection enum). All additions go into `apps/site/src/content.config.ts`.

**Reuse note:** the existing `themes: z.array(z.string()).default([])` field on both collections is **reused, not duplicated** — Step 0 strips bucket labels from it, and the classification pass repopulates it with substantive subject terms. The eight new fields below are added alongside.

### 4.1 Shared additions (both musings and opinions)

```ts
proposed_themes:  z.array(z.string()).default([])         // vocabulary Claude suggested that wasn't in canonical list
key_concepts:     z.array(z.string()).max(5).default([])  // long-tail named concepts (up to 5)
pull_quote:       z.string().optional()                   // RAW source substring (50–250 chars, one sentence).
                                                          // Stored verbatim from source markdown; not normalized.
                                                          // Verifier normalizes a transient copy for matching only.
stance:           z.enum([
                    'argues-for','argues-against','analyzes','profiles','commemorates'
                  ]).optional()
geographic_scope: z.object({
                    scale:  z.enum(['national','regional','bi-regional','international-comparison']).optional(),
                    places: z.array(z.string()).default([])
                  }).optional()
period_window:    z.enum([
                    'pre-independence','nehruvian-era','late-license-raj',
                    'reform-era','post-reform'
                  ]).optional()
source_channel:   z.string().optional()                   // migrated from old bucket-label themes
```

### 4.2 Opinion-only kind enum

```ts
kind: z.enum([
  'profile','commentary','review','obituary','event-coverage','editorial'
]).optional()
```

### 4.3 Musing-only kind enum

```ts
kind: z.enum([
  'book-excerpt','pamphlet-excerpt','speech-excerpt','lecture','periodical-article','letter'
]).optional()
```

### 4.4 Period boundaries (deterministic — applier computes from year)

| Enum value | Year range | Description |
|---|---|---|
| `pre-independence` | ≤1947 | Colonial era through Independence |
| `nehruvian-era` | 1948–1964 | First three Plans; Nehru's death in 1964 |
| `late-license-raj` | 1965–1984 | Indo-Pak '65, Emergency, Janata, return of Indira |
| `reform-era` | 1985–2004 | Rajiv → Manmohan '91 reforms → Vajpayee NDA |
| `post-reform` | 2005+ | Post-WTO India |

Boundaries are deliberately coarse and event-anchored so they remain stable; they are standard in Indian political-economic historiography (cf. Joshi, Panagariya, Bhagwati).

**Note on naming collision:** the existing `apps/site/src/content/period-windows/` reference collection (loaded via `content.config.ts:456`) has its own ID scheme used by `graph-edges` and reading-paths. The `period_window` z.enum here is a **separate, lightweight per-piece filter facet** — not a `reference('period-windows')`. We chose z.enum over a reference because filtering is the only consumer of this field today; revisit if the synthesis collection's per-window attributes (e.g. summaries, anchor events) become useful on the listing.

### 4.5 Geographic_scope — substitution-test rubric

`scale` is **mutually exclusive** (single value, not multi). The classification rubric below goes verbatim into the system prompt.

```
national             → engages with pan-India policy / federal institutions /
                       all-India debates. NOT anchored to a specific region even
                       when examples are drawn from one (see substitution test).
regional             → primary analytical focus is ONE Indian region. National
                       context may be mentioned but is backdrop, not subject.
bi-regional          → explicit comparison between TWO specific Indian regions.
                       Not "uses examples from two states" — must be a structured
                       comparison where regional specificity drives the analysis.
international-       → compares India to a non-Indian country/bloc as a primary
  comparison           analytical move.
```

**Empty-when-uncertain rule.** When the substitution test is ambiguous, leave the field **unset** (null in JSON, absent in frontmatter). The enum has only the four values above — "unset" is the absence of a value, not a fifth option. Never pick `national` as a soft default — that pollutes the filter.

**Substitution test (embedded as worked examples in the prompt):**

> Can you substitute the region name with any other Indian region and have the piece's argument survive intact? If yes → **national**. If no → **regional**.

| Piece description | Mentions | Substitution test | Verdict |
|---|---|---|---|
| "India's industrial policy needs reform — compare MH textiles to TN electronics" | MH, TN | Swap to Gujarat/Karnataka — argument identical | **national** |
| "The Gujarat Model of Industrial Development" | Gujarat | Swap Gujarat→Punjab — argument collapses | **regional** |
| "Bengal Famine of 1943: A Liberal Critique" | Bengal | Famine specific to Bengal — substitution incoherent | **regional** |
| "Sharad Joshi's all-India farm-policy critique, organised from Maharashtra" | MH | Joshi's arguments are national; MH is staging ground only | **national** |
| "Sharad Joshi's farmer movement in Maharashtra: organising methods" | MH | Movement itself is the subject; swap to Punjab — different movement | **regional** |
| "Why Kerala's literacy is distinctive among Indian states" | Kerala | Argument is specifically about Kerala | **regional** |

Pieces published from one state's editorial team but with pan-India arguments → **national** (publishing geography ≠ subject geography).

### 4.6 Geographic_scope — `places[]` modeling

`places[]` populates **whenever a place is substantively engaged with**, independent of `scale`. National-with-illustration pieces still list the illustrated states.

Vocabulary is **closed** — 28 states + 8 UTs + a handful of pre-1956 historical units (Bombay-Presidency, Madras-Presidency, Bengal-Presidency) + ISO-style country slugs for international-comparison. Sub-state and multi-state cultural regions get **collapsed to the modern state(s) they overlap with**:

```
Awadh                  → ["uttar-pradesh"]
Konkan                 → ["maharashtra","goa","karnataka"]
Vidarbha               → ["maharashtra"]
Cow Belt               → ["uttar-pradesh","bihar","madhya-pradesh","rajasthan","haryana"]
"the South" / Dravida  → ["tamil-nadu","kerala","karnataka","andhra-pradesh","telangana"]
"the Northeast"        → ["assam","meghalaya","manipur","tripura","mizoram",
                          "arunachal-pradesh","nagaland","sikkim"]
"West UP and Haryana"  → ["uttar-pradesh","haryana"]
Bombay Presidency      → ["maharashtra","gujarat","karnataka"]  (pre-1956 pieces)
Madras Presidency      → ["tamil-nadu","kerala","karnataka","andhra-pradesh","odisha"]
```

The full canonical vocabulary file lives at `data/places-vocab.json` (states + UTs + historical-units + countries).

### 4.7 Two filter facets in the sidebar

Scale and Places remain independent in the UI:
- **Scale chips** — 4 values (national, regional, bi-regional, international-comparison).
- **Places chips** — top N states by frequency across visible entries.

A user can combine "scale=regional AND place=Tamil Nadu" to get pieces specifically about TN, or "place=Tamil Nadu" alone to also see national pieces that engaged with TN.

## 5. Year resolution for `period_window`

Deterministic (no Claude call for the era itself). Per-collection rule:

- **Opinions:** use `pubDate.year` directly. The Editorial Team wrote them at that date — pub year IS source year.
- **Musings:** prefer **source year**, not the website upload date.
  1. If `excerpt_of` is set → resolve `primary-works[excerpt_of].publication.year`.
  2. Else → Claude returns `source_year_inferred: int | null` in its JSON output (see §6 Step 3 contract); applier uses it if non-null and within the plausible range 1800–2026.
  3. Else → fall back to `pubDate.year` (will be the upload date — occasionally wrong; sets `needs_review: true` for curator).

The applier maps the resolved year to a `period_window` value via the year-range table above. `source_year_inferred` is a **transient Claude output**, not a stored frontmatter field — the applier consumes it and discards it.

## 6. Pipeline (parallel-subagent execution)

Six steps. Scripts live in `scripts/synthesis/`. No `claude -p`. Subagents are dispatched in parallel from the Max session.

**Step ordering / dependency graph:**

```
Step 0 (bucket cleanup)      ──┐
Step 1 (build themes vocab)  ──┼─→ Step 2 (prepare batches) → Step 3 (write prompt) → Step 4 (dispatch) → Step 5 (apply) → Step 6 (audit)
```

Steps 0 and 1 are independent (Step 0 touches musings/opinions; Step 1 reads primary-works only) and can run in parallel. Step 2 needs Step 0's outputs (so cleaned `themes[]` doesn't leak into the prompt) and Step 1's vocab. Step 3 inlines the vocab from Step 1. Steps 4–6 are strictly sequential.

### Step 0 — Bucket cleanup pre-pass (`cleanup-bucket-themes.py`)

For each musing/opinion, scan `themes[]` for known bucket labels and migrate them into `source_channel`:

```
so-musings                          → "so-musings"
forum-of-free-enterprise-periodicals → "forum-of-free-enterprise"
indian-libertarian-periodicals       → "indian-libertarian"
indian-liberal-group-periodicals     → "indian-liberal-group"
marathi-articles                     → "marathi-articles"
lectures                             → "lectures"
opinions / events (on opinions only) → "editorial-opinions" / "editorial-events"
```

`source_channel` is a single string (first-match wins by the order above). Migrated labels are then stripped from `themes[]`. Idempotent — skip pieces whose `themes[]` already contains no known bucket labels.

### Step 1 — Canonical themes vocabulary (`build-themes-vocab.py`)

Walk `apps/site/src/content/primary-works/*.md`, extract distinct `themes[]` values, then filter the candidate list through two automated heuristics:

1. **Slug-shape filter** — keep only kebab-case lowercase tokens (`^[a-z][a-z0-9-]*$`). Anything with capital letters, spaces, or punctuation gets dropped (catches "Sharad Joshi", "Sharad Anantrao Joshi", title-case strings).
2. **Thinker-slug filter** — drop tokens that also appear as an `id` in `apps/site/src/content/thinkers/*.md` (catches thinker names that snuck in via the synthesis pipeline as kebab-case).

Then **emit two files**:
- `data/themes-vocab-candidates.json` — full filtered candidate list.
- `data/themes-vocab.json` — **manually curated** locked vocabulary (Adnan reviews and trims). The applier and prompt only read the locked file.

Sort by frequency in both. Expected locked size ≈ 30 canonical terms.

If Adnan trims a candidate term that's already populated on some primary-works entries, that's fine — the classification pass only writes to musings/opinions; existing primary-works frontmatter is untouched. The trimmed term continues to render on primary-works listing chips until a separate primary-works cleanup pass (out of v1 scope).

### Step 2 — Prepare batch inputs (`prepare-classify-batches.py`)

For each non-draft musing/opinion, emit one JSON record per line into `data/classify/batch-NN.jsonl`:

```json
{
  "id": "1991-liberal-reforms-...",
  "collection": "musings",
  "title": "1991 Liberal Reforms: Why No One Celebrated Them - Ashok Desai, 1995",
  "year_hint": 1995,
  "body_excerpt": "<first ~3000 chars, truncated at paragraph boundary>",
  "context": {
    "author": "ashok-desai",
    "subject": null,
    "excerpt_of": null
  }
}
```

Group into 10 batches of ~26 pieces each (200 musings + 61 opinions = 261 pieces; 261 / 10 ≈ 26). `year_hint` already resolves `excerpt_of` for musings where the source year is known.

**Body excerpt handling.** Most musings are <3000 chars total; for those, `body_excerpt` is the full body. For longer pieces, truncate at the nearest paragraph boundary at or before 3000 chars. The trade-off: a pull_quote candidate that only appears in chars 3000+ of a long piece will not be verifiable and will be dropped — acceptable, since most rhetorical highlights appear in the first ~2 pages of a short piece.

### Step 3 — System prompt (`prompts/system-classify.txt`)

Single prompt file that embeds:
- The locked themes vocabulary (~30 terms) inline.
- The locked places vocabulary (states/UTs/historical units/countries) inline.
- Each output field with constraints and the substitution-test rubric for `scale`.
- Two worked examples (one opinion, one musing) showing complete correct output.
- Hard rules:
  - `themes[]` must be a subset of the vocabulary; new terms go into `proposed_themes[]`.
  - `places[]` must be a subset of the places vocabulary; outside-vocab places are dropped (logged).
  - `pull_quote` must be a verbatim substring of `body_excerpt`, 50–250 chars, single sentence. Indic-language pieces use `।` (danda) as sentence terminator in addition to `. ? !`; the prompt instruction names the danda explicitly.
  - `kind` must match the supplied collection's enum.
  - When uncertain about `scale`, `stance`, or `kind`, leave the field **unset** (`null`) — never pick a soft default.
  - For musings, return `source_year_inferred: int | null` — the year the source work was published (NOT when CCS posted the excerpt). Set null if not confidently inferable from the body.

**Full per-piece output contract** (Claude returns one such object per input piece, all in a single top-level array per batch):

```json
{
  "id": "<echo from input>",
  "themes": ["..."],
  "proposed_themes": ["..."],
  "key_concepts": ["..."],
  "pull_quote": "<raw substring or null>",
  "stance": "argues-for | argues-against | analyzes | profiles | commemorates | null",
  "kind": "<collection-specific enum value or null>",
  "geographic_scope": {
    "scale": "national | regional | bi-regional | international-comparison | null",
    "places": ["..."]
  },
  "source_year_inferred": 1995  // musings only; null for opinions
}
```

### Step 4 — Dispatch parallel subagents (orchestrator inside Max session)

**Orchestrator = the Max session itself, not a script.** Claude (interactive) reads the dispatch plan and emits 10 parallel `Agent` tool calls in a single message. No `dispatch-classify.py`. This matches the Phase B NER execution model.

Each subagent receives:
- The system prompt (`prompts/system-classify.txt`).
- Its batch file path (`data/classify/batch-NN.jsonl`).
- Its output path (`data/classify/output-NN.json`).

Each subagent emits one classification object per piece (the §6 Step 3 contract).

**Failure definition.** A batch is considered failed if any of:
- Subagent timeout (>10 min per batch).
- Output file missing, empty, or not valid JSON.
- Output array length does not match input batch length.
- Output is missing the `id` echo or `id` doesn't match an input piece.

Failures get **logged to `data/classify/dispatch.log`** (one line per failure: batch number, failure type, timestamp, agent ID). The orchestrator re-dispatches failed batches individually after the first wave completes. Per-piece validation errors (e.g. an out-of-vocab theme on one entry) are NOT batch failures — they're handled by the applier in Step 5.

### Step 5 — Apply (`apply-classify.py`)

Walks `data/classify/output-*.json` and merges into each entry's MD frontmatter.

**Python-side validation schema** lives at `scripts/synthesis/classify_schema.py` — hand-rolled Pydantic models mirroring the Zod additions in §4. (Same convention as the existing Phase B NER applier: hand-rolled Pydantic, no Zod-to-Python codegen.) The applier instantiates these models per piece; ValidationError on a single piece is logged and the piece keeps `needs_review: true` rather than aborting the batch.

**Per-field handling:**
- `themes[]` not in canonical vocab → moved to `proposed_themes[]` (don't drop — curator may approve).
- `places[]` not in canonical vocab → dropped silently, logged at INFO.
- `pull_quote`: smart-quote/em-dash/Unicode-NFKC normalization on a transient copy for matching; if the normalized form appears as a substring of the normalized body, the **raw** quote (un-normalized, exactly as Claude returned it from the source) is stored. Dropped on failure, logged.
- `period_window` derived from resolved year (see §5).
- `key_concepts[]` lowercased + kebab-cased for storage (e.g. "License-Raj" → "license-raj"); deduped against vocab post-hoc by audit.

**Merge semantics on re-run.** For each piece, per field:
- If existing frontmatter field is **empty/unset** → write Claude's value.
- If existing field is **populated** → preserve existing UNLESS the script is invoked with `--overwrite=<field-name>` (per-field override). Default behavior is "first run wins" — protects manual curator edits.

**Frontmatter writer** uses PyYAML round-trip with key-order preservation (same as existing `apply-ner.py`). Untouched keys never get reformatted.

`needs_review: true` is set when ≥1 expected field is missing (kind/stance/scale unset is fine — that's the empty-when-uncertain rule), or `pull_quote` failed verification, or year-resolution fell back to `pubDate.year` for a musing without `excerpt_of`.

Idempotent under the merge rule above.

### Step 6 — Audit (`audit-classify-coverage.py`)

Generates `data/classify/coverage-report.md` with:
- Per-collection coverage % per dimension.
- Top 30 `proposed_themes[]` by frequency (curator review batch).
- Pieces with empty `key_concepts[]` (re-run candidates).
- Pieces where `pull_quote` failed verification (re-run candidates).
- Year-resolution fallbacks count for musings (manual review queue).

## 7. Frontend changes

### 7.1 Filter sidebar (`pages/musings/index.astro`, `pages/opinions/index.astro`)

Add chip rows for the new facets, alongside the existing Decade/Theme chips:

- **Kind** — collection-specific enum chips
- **Period** — 5 chips (era)
- **Stance** — 5 chips
- **Scale** — 4 chips
- **Place** — top-N chip cloud
- **Themes** — now populates with substantive vocabulary (chip cloud, top 30)

Existing dead theme chips (`so-musings`, `opinions`, `events`) disappear naturally because they've been migrated out of `themes[]` in Step 0.

The client-side filter JS extends the existing `state` Set-of-Sets pattern with one Set per new facet. No new dependencies.

### 7.2 Listing cards

Below the title and above the date line, show `pull_quote` if present:

```astro
{m.data.pull_quote && (
  <p class="text-sm text-(--color-fg-muted) italic mt-1 line-clamp-2">
    "{m.data.pull_quote}"
  </p>
)}
```

### 7.3 Detail pages (`pages/[lang]?/musings/[slug].astro`, opinions equivalent)

Render `key_concepts[]` as small badge chips near the top of the article, under the byline. Each chip links to a filtered listing (`/musings/?key_concept=<slug>`) — the listing's existing JS filter is enhanced to read URL params on load and pre-select matching chips.

**URL param namespace** (per facet, all kebab-case lowercase values):

| Param | Maps to | Multi-value? |
|---|---|---|
| `theme=...` | `themes[]` | comma-separated list (`?theme=democracy,free-enterprise`) |
| `kind=...` | `kind` | single value |
| `period=...` | `period_window` | comma-separated |
| `stance=...` | `stance` | comma-separated |
| `scale=...` | `geographic_scope.scale` | comma-separated |
| `place=...` | `geographic_scope.places[]` | comma-separated |
| `key_concept=...` | `key_concepts[]` | comma-separated |
| `decade=...` | derived from `pubDate.year` (existing) | comma-separated |

No collision risk because the existing chip handler does not read URL params today. The enhancement adds a single `parseInitialParamsFromURL()` call at load time, plus a `pushState` per chip toggle so the URL stays in sync (back-button restores prior filter state). The `decade=` param maps to the pre-existing decade chip row (which predates this spec); it's brought into the URL namespace by `parseInitialParamsFromURL()` for consistency.

### 7.4 Cards on bio pages

No changes required — the "Mentioned in" / "Profile pieces about <X>" sections already pull from `subject` and `thinker_mentions`; they don't depend on this classification.

## 8. Acceptance metrics

Run after Step 6 audit. Target thresholds:

| Dimension | Target coverage |
|---|---|
| `themes[]` populated (≥1) | ≥95% |
| `kind` populated | ≥90% |
| `stance` populated | ≥85% |
| `period_window` populated | ≥85% |
| `key_concepts[]` (≥1) | ≥80% |
| `pull_quote` (verbatim-verified) | ≥80% |
| `geographic_scope.scale` populated | ≥75% |
| `geographic_scope.places[]` populated when scale ∈ {regional, bi-regional} | ≥90% (of that subset) |
| `proposed_themes[]` unique-term count | ≤30 |

The deliberately-permissive scale target reflects the "leave-empty-when-uncertain" rule from §4.5 — a clean 25% unset is acceptable; a 100% rate would indicate Claude is defaulting to "national".

## 9. Risks & mitigations

- **Theme vocabulary drift.** Mitigated by hard-locking to primary-works vocabulary + capping `proposed_themes[]` at 30 unique terms reviewed by curator.
- **Pull-quote hallucination.** Mitigated by verbatim-substring validator with smart-quote/em-dash normalization. Failures are dropped, not silently accepted.
- **Place over-extraction.** Mitigated by the substitution-test rubric in the prompt + closed places vocabulary. National-with-illustration pieces are explicit pattern in the worked examples.
- **Source-year ambiguity (musings).** Mitigated by the three-step fallback in §5; `needs_review: true` flag set when fallback hits `pubDate.year`.
- **Subagent silent failure.** Mitigated by per-batch dispatch — one batch failing leaves the other nine intact. Re-dispatch is per-batch.
- **Indic-language musings.** Pipeline handles them: the prompt stays in English, Claude reads the body in source language. The single-sentence rule in §6 Step 3 explicitly names the danda (`।`) as a sentence terminator alongside `. ? !`. Pull-quote verbatim check uses Unicode NFKC normalization (so visually-identical but binary-different Devanagari/Gujarati glyphs still match). Expect slightly lower pull_quote coverage on Indic pieces — acceptable.

## 10. Out of scope (recap)

- `liberal_lineage` dimension (cut by Adnan).
- Re-classification or theme cleanup of primary-works (separate pass).
- Reading-paths and themes-collection downstream updates.
- `source_channel` sidebar facet (data populated; surfacing deferred).
- Interviews classification (Phase B-2 audio path).
- Cross-collection unified search / faceting beyond per-collection sidebars.

## 11. Dependencies

- `apps/site/src/content.config.ts` — schema additions for both collections.
- `data/classify/` — new directory holding batch inputs, agent outputs, dispatch log, and coverage report.
- `data/themes-vocab.json` — locked vocabulary (manually curated from Step 1 candidates).
- `data/themes-vocab-candidates.json` — Step 1 auto-filtered candidates (intermediate).
- `data/places-vocab.json` — written by hand: 28 Indian states + 8 UTs + ~5 pre-1956 historical units (Bombay-Presidency, Madras-Presidency, Bengal-Presidency, etc.) + ~20 country slugs (united-kingdom, united-states, china, japan, soviet-union, etc.). All kebab-case lowercase.
- `scripts/synthesis/prompts/system-classify.txt` — new prompt file.
- `scripts/synthesis/classify_schema.py` — new Pydantic schema mirroring §4 Zod additions.
- New scripts in `scripts/synthesis/`: `cleanup-bucket-themes.py`, `build-themes-vocab.py`, `prepare-classify-batches.py`, `apply-classify.py`, `audit-classify-coverage.py`.
- Frontend: `apps/site/src/pages/musings/index.astro` and `apps/site/src/pages/opinions/index.astro` get new chip rows + URL-param parsing JS.

## 12. Open questions

None at design-lock time. Anything that surfaces during implementation rolls into a v1.1 follow-up.
