# Interviews into Primary-Works — Design Spec

**Author:** Adnan
**Date:** 2026-05-27
**Status:** locked

## 1. Goal

Fold the 72 entries in the existing `interviews` content collection into the `primary-works` collection by adding `'interview'` to the `work_type` enum, migrating every interview MD onto the primary-works schema, and enriching each one with LLM-extracted structured metadata (cross-thinker mentions, summary, key points, key passages, themes, resolved interviewer) using the **already-produced cleaned + diarized transcripts** at `data/interview-transcripts/<slug>.cleaned.md`.

After this work, an interview is just another work in the corpus — same listing page, same filters, same `thinker_mentions[]` shape, same detail page (with a small UI extension covered in a follow-up spec). The `interviews` collection ceases to exist.

**Terminal state:**

- 72 MDs moved from `apps/site/src/content/interviews/` to `apps/site/src/content/primary-works/`, each with `work_type: 'interview'`.
- ~67 of those carry LLM-enriched frontmatter (summary, key_points, thinker_mentions with key_passages, themes, interviewer if resolvable).
- 3 special cases: 2 audio-only podcasts (`transcript_status: 'unavailable'`, no audio recoverable) + 1 with an empty Deepgram result (`transcript_status: 'none'`).
- The `interviews` collection definition, the `apps/site/src/content/interviews/` directory, and the "Interviews" nav-bar link are removed.
- `pnpm build` exits clean; page count grows by 72.

## 2. Non-goals

- **No UI changes to the primary-work detail page** in this spec. The video embed, transcript renderer, and any interview-specific filter UI are deferred to a follow-up spec ("interview-detail UI"). After this spec, an interview-as-primary-work renders with the existing primary-work detail layout, with the cleaned transcript appearing as the page body (markdown-rendered without special formatting for diarized turns).
- **No creation of thinker stubs** for `thinker_unresolved` mentions surfaced by the LLM. Editorial follow-up.
- **No re-running of NER / `audit-cross-refs.py`** on the newly-migrated MDs. Will happen later as part of the next content-readiness pass.
- **No editorial review of `needs_review: true` MDs.** Every enriched MD lands with `needs_review: true` so a human can sweep through later.
- **No second-pass speaker re-diarization.** The cleanup script already produced reasonable speaker labels via Claude; the extraction pass trusts those.
- **No new themes collection entries.** `themes:` stays as free-form string array until the themes collection is brainstormed separately.
- **No changes to the `interviews/`-era Sveltia CMS routes**, if any. The Sveltia config will be updated only if it explicitly references the `interviews` collection name; otherwise it picks up primary-works automatically.

## 3. Scope

Three Python scripts under `scripts/synthesis/`:

1. `migrate-interviews-to-primary-works.py` — deterministic, no LLM. Reads each interview MD, builds a primary-work-shaped MD, writes it to `apps/site/src/content/primary-works/`, deletes the old MD. ~150 lines including helpers.

2. `enrich-interview-mds.py` — LLM-driven. For each newly-migrated interview MD with a cleaned transcript, calls `claude -p` with the transcript + title + authority list of thinkers, parses the JSON response, validates the shape, merges into the MD frontmatter. ~200 lines.

3. `scripts/synthesis/tests/test_migrate_interviews.py` + `test_enrich_interviews.py` — TDD tests for pure-logic helpers in both scripts. ~150 lines combined.

Plus one config change:

4. `apps/site/src/content.config.ts` — extend the `work_type` enum with `'interview'`, add optional `youtube_url` and updated `transcript_status` fields to the primary-works schema, remove the `interviews` collection definition.

Plus one navigation cleanup:

5. The header / nav component (wherever the "Interviews" link lives — likely `apps/site/src/components/Header.astro` or `Layout.astro`) loses that link.

**File-size budget:** ~500 lines of new Python total. Schema delta to `content.config.ts` is ~5 lines added, ~20 lines removed (the `interviews` collection block).

## 4. Architecture

```
                ┌─── repo state today ────────────────────────────────────┐
                │  apps/site/src/content/interviews/         (72 MDs)     │
                │  apps/site/src/content/primary-works/      (~520 MDs)   │
                │  apps/site/src/content/thinkers/           (~480 MDs)   │
                │  data/interview-transcripts/<slug>.cleaned.md (~67)     │
                └─────────────────────────────────────────────────────────┘
                                       │
   ┌─── PHASE A: deterministic migration (one-shot, no LLM) ──────────────┐
   │                                                                       │
   │  scripts/synthesis/migrate-interviews-to-primary-works.py             │
   │     For each interview MD:                                            │
   │       - parse frontmatter                                             │
   │       - build new primary-work frontmatter:                           │
   │           work_type: 'interview'                                      │
   │           authors: [subject] (if subject ref present)                 │
   │           contributors: []                                            │
   │           publication: { year, language }                             │
   │           youtube_url, transcript_status                              │
   │           description: <preserved editorial body, if non-garbage>     │
   │           needs_review: true, draft: false                            │
   │       - body: cleaned transcript content (or placeholder)             │
   │       - write to primary-works/<slug>.md                              │
   │       - delete old interviews/<slug>.md                               │
   │                                                                       │
   │  schema change in content.config.ts:                                  │
   │     - add 'interview' to work_type enum                               │
   │     - add youtube_url + transcript_status to primary-works            │
   │     - remove interviews collection definition + dir                   │
   │                                                                       │
   │  nav-bar cleanup: drop "Interviews" link                              │
   │                                                                       │
   │  commit: "feat(content): fold interviews into primary-works           │
   │           (72 MDs migrated, interviews collection removed)"           │
   └───────────────────────────────────────────────────────────────────────┘
                                       │
   ┌─── PHASE B: LLM enrichment (one MD at a time) ───────────────────────┐
   │                                                                       │
   │  scripts/synthesis/enrich-interview-mds.py                            │
   │     Build authority manifest from thinkers/ (~480 rows)               │
   │     For each migrated interview MD where transcript_status=='complete'│
   │       - compose prompt: title, description, subject, authority list,  │
   │         cleaned transcript body                                       │
   │       - claude -p --dangerously-skip-permissions, parse JSON          │
   │       - validate: known slugs only; demote unknowns to                │
   │         thinker_unresolved; clamp count caps                          │
   │       - merge JSON into MD frontmatter:                               │
   │           summary, key_points, themes,                                │
   │           thinker_mentions[], related_thinkers[],                     │
   │           contributors[] (interviewer entry if resolvable)            │
   │       - write back                                                    │
   │                                                                       │
   │     Commit in batches of 10:                                          │
   │       "data(primary-works): enrich N interview MDs (batch K)"         │
   │                                                                       │
   │     Skip rules:                                                       │
   │       - transcript_status == 'unavailable': skip                      │
   │       - transcript_status == 'none': skip                             │
   │       - claude -p fails after 3 retries: log, skip                    │
   │                                                                       │
   │  Final flush + summary log.                                           │
   └───────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                ┌─── repo state after this spec ──────────────────────────┐
                │  apps/site/src/content/primary-works/  (~592 MDs)       │
                │     - ~520 books + pamphlets + speeches + ...           │
                │     - 72 interviews with work_type='interview'          │
                │       - ~67 fully enriched (mentions, summary, etc.)    │
                │       - 3 transcript-unavailable or transcript-empty    │
                │  apps/site/src/content/interviews/  (gone)              │
                │  data/interview-transcripts/  (preserved; source-of-truth│
                │    transcripts kept for re-runs / future passes)        │
                └─────────────────────────────────────────────────────────┘
```

Phase A and Phase B ship independently. Phase A can land first; the site builds clean with un-enriched interview MDs. Phase B layers enrichment on top, committing in 10-MD batches so partial progress is durable.

## 5. Components in detail

### 5.1 Schema additions (`apps/site/src/content.config.ts`)

Three concrete edits to the existing `primaryWorks` schema:

```ts
work_type: z.enum([
  'book', 'pamphlet', 'speech', 'essay',
  'edited_volume', 'occasional_paper', 'letter',
  'correspondence', 'periodical_issue', 'reference',
  'interview',                                       // NEW
]),
// ... existing fields unchanged ...
youtube_url: z.string().url().optional(),            // NEW
transcript_status: z.enum(
  ['none', 'partial', 'complete', 'unavailable']     // 'unavailable' is NEW
).default('none'),                                   // NEW
```

The existing `interviews` collection block (the whole `defineCollection({ ... })` for interviews and its entry in the exported collections map) is removed.

### 5.2 Migration mapping (`migrate-interviews-to-primary-works.py`)

Per-interview, the field mapping from old MD to new MD:

| Old field (interviews schema) | New field (primary-works schema) |
|---|---|
| `id` | `id` (unchanged) |
| `title` | `title.main` |
| `pubDate` | `publication.year` (year extracted from ISO date) |
| `subject` (thinker ref) | `authors: [<subject_ref>]` if present; else `authors: []` |
| `subject_name` | `title.main` (already from title, redundant; subject_name dropped) |
| `interviewer` (string, empty in all MDs) | `contributors: [{ role: 'interviewer', thinker_unresolved: <value> }]` if non-empty; else `contributors: []` |
| `youtube_url` | `youtube_url` (unchanged) |
| `transcript_status` | `transcript_status`, recomputed from disk:<br>• `complete` if `data/interview-transcripts/<slug>.cleaned.md` exists and is non-stub<br>• `none` if it's a SKIP_EMPTY stub<br>• `unavailable` for the 2 podcasts whose audio 404'd |
| `themes: ['interviews']` | `themes: []` (the `interviews` tag is redundant — `work_type` says it) |
| `language` | `publication.language` |
| `needs_review`, `draft` | preserved |
| `ai` | dropped (will be repopulated in Phase B) |
| (no field) | `work_type: 'interview'` (NEW, fixed value) |
| (old body content) | preserved as `description` frontmatter field IF non-garbage (filter: not matching `^type=content&` AND > 80 chars of real content after stripping `Needs editorial review` tail) |
| (new body content) | = contents of `data/interview-transcripts/<slug>.cleaned.md` if present, else a one-line "Transcript not available." placeholder |

The script runs once, processes all 72 MDs in slug-sorted order, deletes the source MD only AFTER successfully writing the destination. Idempotent re-run is safe (skips if destination exists with matching shape).

### 5.3 Enrichment pipeline (`enrich-interview-mds.py`)

**Authority manifest build (once per run):**

```python
def build_authority_manifest(thinkers_dir: Path) -> list[dict]:
    """Return [{slug, canonical_name, also_known_as, canon_status}, ...] for every thinker MD."""
```

Loaded into the prompt template as a structured table the LLM can reference.

**Per-MD prompt (Phase B core):**

```
You are an analyst preparing structured metadata for an interview transcript
that is being filed alongside books, pamphlets, and speeches in the Indian
Liberals archive.

# Interview
- Title: <title.main>
- Year: <publication.year>
- Subject (interviewee): <subject canonical name from authors[0]>
- Editorial description (from the archive's original notes, if any):
  <description field, verbatim>

# Authority list of thinkers in the archive
(slug | canonical_name | also_known_as[] | canon_status)
peter-bauer      | Peter Bauer     | [Lord Bauer, P. T. Bauer, Prof. Bauer]  | core
b-r-shenoy       | B. R. Shenoy    | [Bellikoth R. Shenoy, ...]              | core
... (~480 rows)

# Cleaned diarized transcript
<full body of the migrated primary-work MD>

# Your task
Produce a SINGLE JSON object with these fields (and nothing else):

{
  "summary": "1-3 paragraph synopsis of what the interview covers...",
  "key_points": ["...", "...", ...],          // 3-7 items
  "themes": ["...", "..."],                    // 3-7 free-form lowercase-hyphenated tags
  "interviewer_name": "..." | null,            // resolved canonical name if you can identify the interviewer, else null
  "interviewer_slug": "..." | null,            // slug from the authority list if interviewer matches one; else null
  "thinker_mentions": [
    {
      "thinker": "<slug from authority list>" OR
      "thinker_unresolved": "<name as spoken>",
      "role": "subject" | "mention",
      "reasoning": "<one-sentence explanation>",
      "evidence": [
        { "quote": "<verbatim from transcript>", "context": "<short>" },
        ...
      ],
      "key_passages": [
        { "quote": "<verbatim>", "what_it_shows": "<short>" },
        ...
      ]
    },
    ...                                        // max 5 thinker_mentions
  ]
}

Hard rules:
- thinker_mentions[].thinker MUST be a slug from the authority list. If a
  person discussed has no plausible match, use thinker_unresolved instead.
- Do NOT invent or approximate-spell slugs.
- evidence[].quote and key_passages[].quote MUST be verbatim from the transcript.
- Max 5 thinker_mentions, max 5 evidence + 5 key_passages per mention,
  max 7 key_points, max 7 themes.
- Output ONLY the JSON object. No preamble. No code fence.
```

**Validator (Python, post-LLM):**

```python
def validate_and_clamp(llm_output: dict, authority_slugs: set[str]) -> dict:
    """
    - Parse the JSON (with one retry on malformed JSON via a re-prompt).
    - For each thinker_mentions entry:
        - If `thinker` is present but not in authority_slugs:
          rewrite as `thinker_unresolved: <last-known canonical>` and drop `thinker`.
    - Clamp count caps: ≤5 mentions, ≤5 evidence per, ≤5 key_passages per, ≤7 key_points, ≤7 themes.
    - Return the cleaned dict.
    """
```

**Merge into MD frontmatter:**

The validated dict's fields overwrite the corresponding frontmatter fields. `related_thinkers` is recomputed as the unique union of `authors[0]` (the subject) + all resolved `thinker_mentions[].thinker` slugs.

If `interviewer_slug` is non-null, append to `contributors[]` as `{ role: 'interviewer', thinker: <slug> }`. If only `interviewer_name` is non-null, append `{ role: 'interviewer', thinker_unresolved: <name> }`. If both null, leave `contributors[]` alone.

`needs_review: true` is set unconditionally (editorial review of all AI output).

### 5.4 Skip rules + special cases

- `transcript_status == 'unavailable'` (the 2 podcasts: `ronald-meinardus`, `gp-manish`): skip Phase B. MD stays migrated-but-not-enriched.
- `transcript_status == 'none'` (a-d-shroff with empty Deepgram result): skip Phase B. MD stays migrated; body is the SKIP_EMPTY stub.
- Transcript length > 80 KB: truncate middle, preserving first 40 KB + last 40 KB + a `(transcript truncated for analysis — full text preserved in MD body)` marker. The MD body itself stays un-truncated; only the LLM input is shortened.
- LLM rate-limit on `claude -p`: parse `reset in N min`, sleep, retry. Max 3 retries; then skip + log to `/tmp/interview-enrich-fails.tsv`.

## 6. Data flow

```
Phase A:
  interviews/<slug>.md ──────────────────────┐
                                              │  migrate-interviews-to-primary-works.py
                                              │  (deterministic field mapping + body swap)
                                              ▼
                                       primary-works/<slug>.md
                                       (work_type='interview',
                                        body=cleaned transcript,
                                        un-enriched frontmatter)
                                              │
                                              │  + delete interviews/<slug>.md
                                              │  + edit content.config.ts (schema)
                                              │  + edit Header.astro (nav link removal)
                                              ▼
                                       commit + push:
                                       "feat(content): fold interviews
                                        into primary-works (72 MDs)"

Phase B (after Phase A):
  thinkers/*.md ─────────► authority manifest (one-time build) ──┐
                                                                  │
  primary-works/<slug>.md (work_type='interview') ────────────────┤
                                                                  ▼
                                              compose Phase B prompt
                                                       │
                                                       ▼
                                              claude -p (--dangerously-skip-permissions)
                                                       │
                                                       │  JSON output
                                                       ▼
                                              validate_and_clamp()
                                                       │
                                                       ▼
                                              merge into MD frontmatter
                                                       │
                                                       ▼
                                       primary-works/<slug>.md
                                       (now with summary, key_points,
                                        thinker_mentions, themes,
                                        possibly interviewer)
                                                       │
                                       every 10 MDs:
                                                       ▼
                                       commit + push:
                                       "data(primary-works): enrich N
                                        interview MDs (batch K)"
```

## 7. Failure modes & edge cases

### Phase A

| Case | Behaviour |
|---|---|
| Original MD has no `subject:` ref | `authors: []`. Editorial follow-up via `audit-thinkers.py`. |
| Original MD's `subject:` slug doesn't resolve to a thinker file | Migration writes `authors: []` + `contributors: [{role: 'subject', thinker_unresolved: <subject_name>}]`. |
| Original MD body is WP garbage (matches `^type=content&` or `<` 80 chars after tail strip) | `description` field omitted from output. |
| Original MD body is a genuine editorial paragraph (e.g., Begum Rokeya, ~1 KB) | Preserved verbatim in `description` frontmatter field. |
| Cleaned transcript file missing for a slug (the 2 audio-404 podcasts) | `transcript_status: 'unavailable'`; body = "Transcript not available." placeholder. |
| Cleaned transcript exists but the source was empty (a-d-shroff) | `transcript_status: 'none'`; body = the SKIP_EMPTY stub; no further enrichment. |
| Slug collision with an existing primary-work MD | Abort with a clear error, do not overwrite. Manual disambiguation. (None expected — interview slugs are distinctive.) |
| Year extraction from `pubDate` fails | `publication.year` omitted; schema allows it optional. |
| Sveltia / CMS config references the `interviews` collection by name | Outside this spec's purview — surface in commit message and let editorial follow up. |

### Phase B

| Case | Behaviour |
|---|---|
| `claude -p` returns non-JSON or malformed JSON | Retry once with a stricter prompt suffix ("output ONLY the JSON object — no preamble, no code fence"). If still bad, log to fails TSV, skip the MD. |
| `claude -p` hits rate-limit | Parse `reset in N min`, sleep, retry. Max 3 attempts per MD. |
| LLM returns a thinker slug not in the authority list | Validator rewrites as `thinker_unresolved: <name>`. The original slug-shaped string becomes the unresolved-name string. |
| LLM returns more than the count caps | Validator trims to first N. |
| LLM returns `interviewer_name: "Interviewer"` or other non-resolution | Skip the `contributors[]` entry; leave it empty. |
| LLM returns an evidence `quote` that's not actually in the transcript (hallucination) | NOT validated programmatically in this spec (too costly, false-positive-prone). The `needs_review: true` flag is the editorial backstop. |
| Authority manifest is too large to fit in context with a long transcript | Hard cap on transcript length is 80 KB (per spec §5.4); authority manifest is ~40 KB; combined fits comfortably in a Claude context window. |
| Phase B run is interrupted mid-batch | Last full 10-MD batch is committed; un-enriched MDs remain migrated-but-not-enriched. Re-run picks up where left off (script skips MDs whose frontmatter already has non-empty `thinker_mentions`). |
| Concurrent v1.5 extraction pipeline is also running | Skip the concern: this spec's execution should pause the v1.5 extraction first (same Option-D pattern used in earlier sessions). Documented in the implementation plan. |

## 8. Testing & validation

### Phase A unit tests (`scripts/synthesis/tests/test_migrate_interviews.py`)

1. `test_subject_ref_becomes_authors_list` — subject "d-r-pendse" → `authors: [d-r-pendse]`.
2. `test_missing_subject_yields_empty_authors` — no `subject:` → `authors: []`, no contributor.
3. `test_pubdate_year_extraction` — `pubDate: "2020-11-05T04:29:04Z"` → `publication.year: 2020`.
4. `test_wp_garbage_body_is_dropped` — body matching `^type=content&` filter → `description` omitted.
5. `test_editorial_paragraph_preserved` — body > 80 chars of real text → preserved as `description`.
6. `test_transcript_status_resolved_from_disk` — `'complete'` / `'unavailable'` / `'none'` mapped correctly from disk state.
7. `test_slug_collision_aborts` — destination MD already exists → script raises, doesn't overwrite.

### Phase B unit tests (`scripts/synthesis/tests/test_enrich_interviews.py`)

1. `test_authority_manifest_format` — deterministic sort, expected columns, ~480 rows.
2. `test_validate_thinker_mentions_passes_known_slugs` — all-valid slugs → returned unchanged.
3. `test_validate_thinker_mentions_demotes_unknown_slug` — unknown slug → rewritten as `thinker_unresolved`.
4. `test_truncate_long_transcript_preserves_endpoints` — > 80 KB input → middle elided with marker, endpoints preserved.
5. `test_clamp_counts_to_caps` — 15 mentions → 5; 20 key_passages → 5; 12 key_points → 7.

### Integration smoke (Phase B)

Pick `d-r-pendse-on-doing-business-in-india-before-1991-reforms` (long, rich, name-dense). Run Phase B on this single MD. Confirm the output:
- contains ≥ 3 thinker_mentions, including `d-r-pendse` (subject), `jrd-tata`, and `manmohan-singh` (mentioned heavily for the 1991 reforms).
- each mention has ≥ 1 key_passage.
- summary names the Licence-Permit Raj, the MRTP Act, the 1991 reforms.
- `interviewer_name` is either resolved or null (this transcript has no introduction, so likely null).

If the smoke output looks sane, launch the full Phase B batch.

### Build sanity (both phases)

After Phase A:
- `pnpm build` exits clean.
- `find apps/site/dist -name 'index.html' | wc -l` = pre-migration page count + 72 (one new primary-works detail page per migrated interview).
- Spot-check 3 detail pages render with the default primary-work layout (no video / transcript UI yet — that's the follow-up spec).

After Phase B:
- `pnpm build` still clean (no schema violations from the enriched frontmatter).
- Spot-check 3 enriched detail pages render the new summary + key_points + thinker_mentions data using the existing primary-work components.

## 9. Stopping criteria

1. `apps/site/src/content/interviews/` directory removed; the `interviews` collection definition removed from `content.config.ts`; "Interviews" nav-bar link removed.
2. 72 new MDs exist under `apps/site/src/content/primary-works/` with `work_type: 'interview'`.
3. Of those 72: ~67 have non-empty `thinker_mentions`, `summary`, `key_points`; 2 have `transcript_status: 'unavailable'`; 1 has `transcript_status: 'none'`.
4. `pnpm build` exits clean.
5. Phase A unit tests pass (7 tests).
6. Phase B unit tests pass (5 tests).
7. Phase B smoke test on `d-r-pendse-on-doing-business-in-india-before-1991-reforms` produces a sane output.
8. All commits pushed to `origin/main`; `git log origin/main..HEAD` is empty.

## 10. Open items / follow-ups (separate specs)

- **Interview-detail UI spec** — render the YouTube video embed below the title + above the summary; render the diarized transcript with proper speaker-turn formatting and a "jump to time" affordance; ensure Pagefind indexes the transcript body for full-text search; ensure the existing primary-works listing-page filter UI gets a `work_type: interview` option.
- **Themes collection** — currently empty; the `themes:` strings from this enrichment will need to settle before a canonical themes collection is brainstormed.
- **Editorial review** of all `needs_review: true` interview MDs (every one of them).
- **Thinker-stub creation** for any `thinker_unresolved` mentions surfaced by the LLM.
- **Audit re-run** — once enriched, the existing `audit-cross-refs.py` and `audit-thinkers-without-quotes.py` should be re-run on the expanded primary-works corpus.
- **Sveltia CMS config** — confirm whether the CMS still references the `interviews` collection name; if so, update separately.
- **NER / Phase B re-pass** for the rest of the primary-works corpus that still lacks `thinker_mentions` (the ~99 from the May 27 extraction batch + the 235 from prior batches).
