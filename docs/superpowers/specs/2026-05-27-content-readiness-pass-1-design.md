# Content-Readiness Pass 1 — Post-Extraction Audit & PDF-URL Apply — Design Spec

**Author:** Adnan
**Date:** 2026-05-27
**Status:** locked

## 1. Goal

Take the ~99 new primary-works MDs that have landed on `origin/main` during the still-running v1.5 extraction batch and bring them to publishable shape in one focused pass:

1. Populate `pdf_url` for every new MD that has a high-confidence match on the existing prod site, using the already-locked PDF reconciliation tooling.
2. Audit (read-only) the new MDs' cross-references for slug ↔ prose drift.
3. Audit (read-only) the entire corpus for thinkers who have no pull-quote attribution anywhere — the answer to "are there any people who do not have any [quotes] associated with them?"
4. Produce a single handoff document that summarises every finding so the next session has a clean picture of what's left to address (e.g., medium-confidence pdf_url candidates, mention-pipeline backlog).

**Terminal state:**

- ≥ 80 of the 99 new MDs gain `pdf_url` (high-confidence tier only). The actual number depends on prod coverage; the prior 381-MD reconciliation landed 369/381 ≈ 97% across all tiers, with ~85–90% at high-confidence tiers alone. We commit to applying ≥ 60 if the matcher returns that many high-confidence rows; if it returns fewer (e.g., 30), we apply all of them and surface the gap.
- Two TSV review surfaces (`data/pdf-link-manifest.tsv`, `data/pdf-link-misses.tsv`) regenerated and committed for Adnan's eyeball pass.
- One findings doc at `docs/handoffs/2026-05-27-content-readiness-pass-1.md` covering Streams B, C, D + Stream A's numeric summary.
- Two new audit scripts under `scripts/synthesis/` with TDD'd unit tests.

## 2. Non-goals

- **Running the NER / mention pipeline** on the 99 new MDs (`thinker_mentions` field stays empty for now). Deferred because (a) it requires Claude calls, (b) the extraction pipeline is rate-limit-paused and competing for the same Max-plan window, and (c) re-running NER once after the full batch completes is cheaper than running it twice. The findings doc will name this as the top follow-up.
- **Mutating the medium / page-only tier of pdf_url matches.** Only `exact` + `high` confidence tiers auto-apply. Medium and below sit in the manifest for Adnan's review.
- **Re-baking the existing 377 MDs** or making any change to MDs that already have `pdf_url`. Stream A's `apply-pdf-urls.py` invocation uses default `--force=false`, so existing pdf_urls are never overwritten.
- **Creating thinker stubs.** This session's audit (Stream B, pre-computed during brainstorming) confirmed 0 new thinker slugs from the 99 new MDs — every referenced slug already has a thinker file. Future batches may surface new ones, but this pass has nothing to create.
- **Modifying the rendering layer.** No Astro component, content schema, or styling changes. If the audit surfaces rendering issues, they're written up in findings, not patched.
- **Re-scraping prod.** The matcher uses the existing `data/prod-mirror/inventory.jsonl` (last refreshed for the May 26 reconciliation). If prod has gained new pages since, our matcher won't see them; that's the trade-off for keeping this pass scoped.
- **Touching the running extraction process.** The pipeline at PID 43187 is still mid-run; we do not pause, kill, or interfere with it. All our writes are to MDs that *already exist* (the pipeline writes new MDs); the sets are disjoint.

## 3. Scope

Three deliverables to land in this pass:

1. **Re-run of the locked PDF reconciliation tools** on the corpus, with apply restricted to high-confidence tiers. (Stream A.)
2. **Two new audit scripts** under `scripts/synthesis/`:
   - `audit-cross-refs.py` — for the new MDs, surface slug ↔ prose drift in two directions.
   - `audit-thinkers-without-quotes.py` — corpus-wide, surface thinkers with zero inbound `evidence.quote` attribution.
3. **One findings document** at `docs/handoffs/2026-05-27-content-readiness-pass-1.md`, hand-authored from the audit outputs, organised by stream.

**Out of scope (named explicitly so the spec stays small):** see §2.

**File budget:**
- 2 new scripts (~150 lines each).
- 1 new test file (`scripts/synthesis/tests/test_readiness_audits.py`, ~120 lines covering both scripts).
- 1 findings doc (~3–5 KB Markdown).
- Manifest TSVs regenerated in place.
- 1 modified-MDs commit from `apply-pdf-urls.py`.

## 4. Architecture

```
                ┌────────────────── repo state today ──────────────────┐
                │ 476 primary-works MDs (377 prior + 99 new this run)  │
                │ 480 thinker MDs                                       │
                │ data/prod-mirror/inventory.jsonl (cached scrape)      │
                │ Extraction pipeline still running at PID 43187        │
                └───────────────────────────────────────────────────────┘
                                       │
   ┌─── STREAM A: PDF URL apply (writes) ────────────────────────────┐
   │                                                                  │
   │   match-pdfs.py                                                  │
   │     → data/pdf-link-manifest.tsv  (regenerated, all tiers)       │
   │     → data/pdf-link-misses.tsv                                   │
   │                                                                  │
   │   apply-pdf-urls.py --only-confidence exact,high                 │
   │     → mutates apps/site/src/content/primary-works/<slug>.md      │
   │       for matched MDs that don't already have pdf_url            │
   │                                                                  │
   │   commit: "data(primary-works): apply N high-confidence pdf_urls │
   │           from prod reconciliation"                              │
   └──────────────────────────────────────────────────────────────────┘
                                       │
   ┌─── STREAM C: Cross-reference audit (read-only) ──────────────────┐
   │                                                                   │
   │   audit-cross-refs.py                                             │
   │     reads:  the 99 new MDs + the 480 thinker MDs                  │
   │     writes: stdout report → captured into findings doc            │
   │     surfaces:                                                     │
   │       - slugs in related_thinkers whose canonical name doesn't    │
   │         appear in summary/key_points (possible AI hallucination)  │
   │       - canonical thinker names appearing in summary/key_points   │
   │         that aren't in related_thinkers (possible missed tag)     │
   └───────────────────────────────────────────────────────────────────┘
                                       │
   ┌─── STREAM D: Thinkers-without-quotes audit (read-only) ──────────┐
   │                                                                   │
   │   audit-thinkers-without-quotes.py                                │
   │     reads:  480 thinker MDs                                       │
   │             + all primary-works/opinions/musings/interviews/      │
   │               theprint-mirror MDs                                 │
   │     writes: stdout report → captured into findings doc            │
   │     surfaces:                                                     │
   │       - per-thinker count of inbound thinker_mentions.evidence.   │
   │         quote entries across the corpus                           │
   │       - list of thinkers with count == 0, sorted by canon_status  │
   │         (canonical > referenced > stub) so canonical thinkers     │
   │         without quote-coverage rise to the top                    │
   └───────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                    docs/handoffs/2026-05-27-content-readiness-pass-1.md
                            │
                            │ Findings sections:
                            │   - Stream A summary (apply count by tier)
                            │   - Stream B summary (pre-computed: 0 new
                            │     thinker slugs; 53/53 resolve)
                            │   - Stream C results (cross-ref discrepancies)
                            │   - Stream D results (thinkers without quotes)
                            │   - Follow-ups (NER run after full batch, etc.)
                            ▼
                    commit: "docs(handoff): content-readiness pass 1"
```

The three streams are independent. Stream A is the only one that writes content files; C and D are read-only. There are no ordering constraints between them — they can be implemented and reviewed in any order. Stream A is run first only because its output (apply count by tier) is one of the numbers the findings doc reports.

## 5. Components in detail

### 5.1 Stream A: PDF URL apply (re-uses existing tools)

**Components:**
- `scripts/synthesis/match-pdfs.py` (existing, locked, no changes)
- `scripts/synthesis/apply-pdf-urls.py` (existing, locked, no changes)

**Invocation:**
```bash
.venv-extract/bin/python3 scripts/synthesis/match-pdfs.py
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --dry-run --only-confidence exact,high
# Eyeball the diff in dry-run output. If sane:
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --only-confidence exact,high
git add apps/site/src/content/primary-works/ data/pdf-link-manifest.tsv data/pdf-link-misses.tsv
git commit -m "data(primary-works): apply N high-confidence pdf_urls from prod reconciliation"
```

**Filter behaviour:** the matcher always operates on the full 476-MD set. Most of the 377 prior MDs already have `pdf_url` populated, so the applier's default no-overwrite policy (`--force=false`) means those rows are no-ops. New-MD rows (the 99) are the ones that actually mutate.

**Tier policy:** `exact` + `high` apply automatically. `medium` and `page-only` stay in the manifest as candidates for Adnan's editorial review. The manifest is committed alongside the apply so Adnan can browse it later without re-running the matcher.

**Numeric expectation:** based on the prior 381-MD reconciliation (369 matches total, ~340 at exact+high), we expect ≥ 60–80 of the 99 new MDs to land a high-confidence pdf_url. The exact number is reported in the findings doc and the commit message.

**Safety:** the runner pipeline writes NEW MDs (slugs that don't exist yet). Stream A writes to MDs that already exist. The two sets are disjoint by construction; no git conflicts possible. If a brand-new MD gets emitted by the runner between our match step and our apply step, it's simply absent from our manifest — the next readiness pass picks it up.

### 5.2 Stream C: `audit-cross-refs.py`

**Responsibility:** for each new MD (selected by file mtime > pre-extension SHA), surface two categories of slug/prose drift.

**Input:**
- `apps/site/src/content/primary-works/*.md` — filtered to "new since last batch" via `git log --diff-filter=A --name-only b6be9fe..HEAD -- apps/site/src/content/primary-works/`. (`b6be9fe` is the pre-extension SHA captured in the extraction-pipeline plan §0.3.)
- `apps/site/src/content/thinkers/*.md` — used to build a slug → {canonical name, also_known_as[]} lookup table.

**Output:** plain-text report to stdout, format:
```
=== Cross-reference discrepancies — new MDs since b6be9fe ===
Total new MDs scanned: 99
MDs with discrepancies: 14

--- <md-slug-1> ---
Slugs in related_thinkers but not mentioned in prose:
  - milton-friedman (canonical name "Milton Friedman" not found in summary/key_points)
Names in prose but not in related_thinkers:
  - "Friedrich Hayek" appears in summary; no `friedrich-hayek` in related_thinkers

--- <md-slug-2> ---
...

=== Summary ===
slugs-not-in-prose: 23 total across 12 MDs
names-not-in-slugs: 18 total across 10 MDs
```

**Matching rule:**
- **Slug → prose:** look up the thinker's `name.canonical` and `name.also_known_as[]`; consider a slug "mentioned" if any of those forms appears as a substring of `summary` or any `key_points[*]` (case-insensitive, word-boundary aware).
- **Prose → slug:** for every thinker file, check if `name.canonical` or any `also_known_as` appears as a word-boundary substring in the prose; if so, that thinker is "named in prose". Compare against `related_thinkers[]`.

**Heuristic limits:** acknowledge in the report header that this is a string-match heuristic; partial-name collisions (e.g., "Smith" without first name) and metonyms ("Forum" for an organisation) are out of scope. The report's purpose is to surface high-signal discrepancies, not to be exhaustive.

**Interface:** zero CLI args. Reads from the repo's canonical paths. Single function `main()`; helpers are pure and TDD-tested.

### 5.3 Stream D: `audit-thinkers-without-quotes.py`

**Responsibility:** corpus-wide inverted index from thinker_id → count of inbound evidence.quote entries; surface thinkers with count == 0.

**Input:**
- `apps/site/src/content/thinkers/*.md` — the universe of thinker IDs.
- `apps/site/src/content/primary-works/*.md`
- `apps/site/src/content/opinions/*.md`
- `apps/site/src/content/musings/*.md`
- `apps/site/src/content/interviews/*.md`
- `apps/site/src/content/theprint-mirror/*.md`

For each content MD, parse the `thinker_mentions[]` frontmatter array; for each mention with non-empty `evidence[].quote` strings, increment the count for that mention's `thinker:` slug.

**Output:** plain-text report to stdout, format:
```
=== Thinkers without inbound pull-quote attribution ===
Total thinker files: 480
Thinkers with ≥1 quote: 152
Thinkers with 0 quotes: 328

Broken down by canon_status:
  canonical    — N with quotes, M without
  referenced   — N with quotes, M without
  stub         — N with quotes, M without
  (other)      — N with quotes, M without

=== Canonical thinkers with zero quotes (top of follow-up list) ===
  <slug>  (canonical name)
  ...

=== Referenced thinkers with zero quotes ===
  <slug>  (canonical name)
  ...
```

**Sorting:** by `canon_status` priority (canonical > referenced > stub > unknown), then alphabetically by slug. The point is to make canonical thinkers without coverage visible first — they're the highest-value gaps.

**Note:** ~58% of the corpus has empty `thinker_mentions[]` (the 99 new + the 235 prior that haven't been NER'd). This audit's "0 quotes" count is therefore inflated by extraction-pipeline backlog, not by genuine thinker isolation. The report header states this explicitly so Adnan reads the numbers in context.

**Interface:** zero CLI args. Single `main()`; helpers (frontmatter parser, inverted-index builder) are pure and unit-tested.

### 5.4 Findings document

**Path:** `docs/handoffs/2026-05-27-content-readiness-pass-1.md`

**Structure:**
```markdown
# Content-Readiness Pass 1 — Findings

**Date:** 2026-05-27
**Scope:** the 99 new primary-works MDs added by the v1.5 extraction batch.
**Reference SHA:** b6be9fe (pre-extension baseline)

## Stream A — PDF URL apply
- Matched & applied: <N> high-confidence (exact + high)
- Surfaced for review: <M> medium / page-only candidates in `data/pdf-link-manifest.tsv`
- Misses: <P> in `data/pdf-link-misses.tsv`
- Commit: <SHA>

## Stream B — New thinker slugs
- 0 new thinker stubs created.
- 53 distinct slugs referenced by the new MDs; 53/53 resolve to existing thinker files.

## Stream C — Cross-reference drift (new MDs only)
- MDs with at least one discrepancy: <N>
- Slugs in related_thinkers but absent from prose: <K> rows
- Names in prose but absent from related_thinkers: <L> rows
- Top examples:
  - <md-slug>: <one-line description>
  - ...

## Stream D — Thinkers without inbound quotes
- Thinkers with 0 quotes: <T>
- Of those, canonical: <C>
- Of those, referenced: <R>
- Caveat: ~58% of the corpus lacks any thinker_mentions because the NER pipeline hasn't been run on the extraction-pipeline output. This number will drop sharply after the post-batch NER run.
- Top 20 canonical-without-quotes:
  - <slug> — <canonical-name>
  - ...

## Follow-ups for next session
1. Run NER on the 99 new MDs (and any additional MDs the full batch produces) once Claude rate-limit window resets.
2. Editorial review of medium-confidence pdf_url candidates in `data/pdf-link-manifest.tsv`.
3. Editorial review of the cross-reference discrepancies surfaced in Stream C.
4. Consider building thinker bios for any canonical-without-quotes entries with strong inbound interest.
```

**Authoring:** the doc is generated by a tiny shell script (or by hand) that captures stdout from each audit, fills the placeholders, and commits. Not a separate Python module — too small to warrant one.

## 6. Data flow

```
data/prod-mirror/inventory.jsonl
       │
       │ + apps/site/src/content/primary-works/*.md
       ▼
match-pdfs.py
       │
       ▼
data/pdf-link-manifest.tsv (regenerated, all tiers)
data/pdf-link-misses.tsv   (regenerated)
       │
       ▼  --only-confidence exact,high
apply-pdf-urls.py
       │
       ▼
mutated MDs (only those whose pdf_url was empty)
       │
       ▼
commit 1: data(primary-works): apply N pdf_urls

apps/site/src/content/primary-works/*.md (new since b6be9fe)
apps/site/src/content/thinkers/*.md
       │
       ▼
audit-cross-refs.py → stdout report
       │
       │ (captured into findings doc)
       ▼
all content collections + thinkers
       │
       ▼
audit-thinkers-without-quotes.py → stdout report
       │
       │ (captured into findings doc)
       ▼
docs/handoffs/2026-05-27-content-readiness-pass-1.md
       │
       ▼
commit 2: docs(handoff): content-readiness pass 1
```

## 7. Failure modes & edge cases

| Case | Behavior |
|---|---|
| Matcher finds 0 high-confidence rows for the 99 new MDs (e.g., prod-mirror inventory is stale) | Stream A apply is a no-op; commit step skipped; findings doc reports "0 applied" and surfaces this as a follow-up item. The next readiness pass would refresh the prod-mirror cache. |
| Matcher's regenerated TSV diff is large (existing rows resorted, etc.) but no semantic change | Commit it anyway — the TSV is a regenerable artifact and re-committing it locks the state cleanly. The commit message reflects the apply count, not the TSV diff size. |
| `apply-pdf-urls.py` fails on a malformed MD (e.g., truncated frontmatter) | Existing script's behaviour: skip that row, exit non-zero, surface in stderr. We commit whatever did apply, surface the failed slug in findings doc, do not retry mid-run. |
| Cross-ref audit encounters a thinker MD with malformed YAML | Skip that thinker in the lookup table; the audit's stdout reports `Warning: skipped <slug>` and continues. Treated the same way the existing `audit-thinkers.py` does. |
| Cross-ref audit case sensitivity / partial-match collisions (e.g., "Smith" matches both Adam Smith and a stray modern Smith) | Acknowledged as a heuristic limitation in the report header. We do whole-word case-insensitive substring matching only; multi-token names (≥ 2 words) reduce false positives substantially. Single-word ambiguous names are accepted as noise. |
| Quotes audit double-counts when the same evidence quote appears in multiple MDs | Acceptable — we count *occurrences*, not unique quotes. A thinker quoted in 5 MDs by 5 different works has a count of 5+, which is the signal we want. |
| Quotes audit reads an MD whose `thinker_mentions[]` is malformed (e.g., a string where a list is expected) | Existing pattern: log + skip + continue. Per-MD failures don't crash the audit. |
| Extraction pipeline emits new MDs between `match-pdfs.py` and `apply-pdf-urls.py` | New MD lacks `pdf_url`; matcher missed it because it ran earlier. Not applied this pass. Next readiness pass catches it. Documented as expected behaviour. |
| Extraction pipeline emits a new MD whose slug matches a slug already in our manifest | Conflict impossible at the apply layer — `apply-pdf-urls.py` uses `--force=false` and skips any MD that already has `pdf_url`. The new MD won't have `pdf_url` (just emitted), so it would naturally apply — which is the right outcome. The only race window is sub-second; functionally benign. |
| Quotes audit's "0 quotes" count is misleadingly high because NER hasn't been run on the 99 new MDs | Findings doc explicitly states this caveat in the Stream D section. Numbers are reported with context, not in isolation. |

## 8. Testing & validation

**Unit tests** in `scripts/synthesis/tests/test_readiness_audits.py`:

For `audit-cross-refs.py`:
- `test_slug_not_in_prose_simple` — single related_thinker, canonical name absent from prose → reported.
- `test_slug_in_prose_via_aka` — canonical name absent but `also_known_as` present → not reported.
- `test_prose_name_not_in_slugs` — canonical name present in prose, slug absent → reported.
- `test_whole_word_match` — "Smithson" does NOT match thinker "Adam Smith".
- `test_case_insensitive_match` — "milton FRIEDMAN" matches "Milton Friedman".

For `audit-thinkers-without-quotes.py`:
- `test_count_single_quote` — one MD with one evidence quote for thinker X → X has count 1.
- `test_count_multiple_quotes_same_thinker` — one MD with three evidence quotes for X → X has count 3.
- `test_skip_empty_thinker_mentions` — MD with empty `thinker_mentions: []` → contributes nothing.
- `test_skip_malformed_md` — MD with bad YAML → audit continues, logs warning.
- `test_sort_by_canon_status` — canonical > referenced > stub in the output ordering.

**Integration sanity:**
- After Stream A's apply commit, `pnpm build` exits clean and `find dist -name 'index.html' | wc -l` returns the same number as before (PDF URL changes don't add/remove pages).
- Spot-check 3 random newly-pdf_url'd MDs and confirm the "Read PDF" button renders by hitting the rendered HTML.

**Read-only audits don't need integration tests** — their output is the findings doc, which is hand-reviewed.

## 9. Stopping criteria

1. `match-pdfs.py` ran; `data/pdf-link-manifest.tsv` and `data/pdf-link-misses.tsv` regenerated.
2. `apply-pdf-urls.py --only-confidence exact,high` applied N rows; N ≥ 0 (0 is acceptable but a finding).
3. Build clean after apply; page count unchanged.
4. `audit-cross-refs.py` ran on the 99 new MDs; output captured.
5. `audit-thinkers-without-quotes.py` ran corpus-wide; output captured.
6. Findings doc at `docs/handoffs/2026-05-27-content-readiness-pass-1.md` exists, covers all four streams, names the follow-ups.
7. Both audit scripts have passing unit tests in `scripts/synthesis/tests/test_readiness_audits.py`.
8. Two commits land on `main`:
   - `data(primary-works): apply N high-confidence pdf_urls from prod reconciliation` (only if N > 0)
   - `docs(handoff): content-readiness pass 1`
9. Both pushed to `origin/main`.

## 10. Open items / follow-ups (separate specs / future sessions)

- **NER / mention-pipeline run** for the 99 new MDs (and the residual 235 prior MDs without mentions). Cost: ~2 Claude calls per MD; ~600 calls total; must happen in a fresh Max-plan window after the extraction pipeline finishes.
- **Editorial review of medium-confidence pdf_url candidates** in the regenerated manifest. Likely a manual eyeball pass; could be aided by a tiny UI but probably not worth building.
- **Editorial review of cross-reference discrepancies** in Stream C output — some will be genuine misses (worth editing into MDs), some heuristic noise.
- **Building thinker bios for canonical-without-quotes entries** with high reader interest. Out of scope here; separate editorial workstream.
- **Refreshing `data/prod-mirror/inventory.jsonl`** if prod has gained new pages since May 26. Defer until we have evidence the cache is stale.
- **Auto-hide-orphans pass** after the NER work lands (the existing `auto-hide-orphans.py` mechanism hides thinker pages with no inbound references). Run later, with fresh mention data.
