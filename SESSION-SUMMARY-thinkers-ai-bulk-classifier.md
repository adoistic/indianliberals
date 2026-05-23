# SESSION-SUMMARY — Thinkers AI Bulk Classifier (SP2)

**Date:** 2026-05-23
**Branch:** `main` (now 33 commits ahead of `origin/main`; not pushed — awaiting Adnan's review)
**Spec:** [docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md](docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md)
**Plan:** [docs/superpowers/plans/2026-05-23-thinkers-ai-bulk-classifier.md](docs/superpowers/plans/2026-05-23-thinkers-ai-bulk-classifier.md)

## Final state

- **Final implementation commit on `main`:** `b16d0c5` (bulk classifier applied to 506 thinker MDs)
- **Build:** clean, **1185 pages indexed** (unchanged from pre-bulk baseline)
- **Spec §10 acceptance criteria:** all 1-30 verified

## Commits landed across the SP2 chunks

| # | SHA | Chunk | Title |
|---|---|---|---|
| 1 | `f2cabed` | Chunk 1 | feat(classify-thinkers): schema validation + pilot CLI |
| 2 | `038ef9d` | Chunk 2 | feat(classify-thinkers): batch preparation + system prompt renderer |
| 3 | `5558492` | Chunk 2 fix | fix(classify-thinkers): correct two anchor slugs to match on-disk thinker MDs |
| 4 | `17e12dd` | Handoff | docs: session handoff for SP2 chunks 1-2 → 3-5 in new session |
| 5 | `673c45d` | **Chunk 3** | feat(classify-thinkers): applier + coverage audit |
| 6 | `a6749eb` | **Chunk 4** | chore(classify-thinkers): pilot calibration passed (90/86.7/86.7); ground truth committed |
| 7 | `b16d0c5` | **Chunk 5** | feat(data): AI bulk classifier populates canon_status / tradition / vocations on 506 thinkers |
| 8 | `f2804f7` | docs | docs: SESSION-SUMMARY for thinkers-AI-bulk-classifier run |
| 9 | `b4510d2` | post-review fix | fix(audit): dedupe reasoning-log entries by id (latest-wins) |

Chunks 1-2 landed in a prior session; Chunks 3-5 (and the post-review fix) in this session.

## Pilot calibration

**One iteration, terminated by ground-truth revision rather than prompt amendment.**

| Run | canon_status | tradition | vocations | Verdict |
|---|---|---|---|---|
| Initial | 21/30 = 70.0% | 24/30 = 80.0% | 26/30 = 86.7% | FAIL (canon_status below 80%) |
| Post-revision | 27/30 = 90.0% | 26/30 = 86.7% | 26/30 = 86.7% | **PASS — bulk authorized** |

**Iteration mechanic:** instead of editing the system prompt or anchors, the diff analysis (against actual corpus engagement: subject-essay counts, mention counts) showed that 6 of 9 canon_status disagreements and 2 of 6 tradition disagreements were cases where the AI's corpus-grounded reasoning was stronger than the controller's first-draft ground truth. Per spec §9.4's "ambiguous ground truth → adjust GT" escalation, the GT was revised on those 8 records (with Adnan's approval). No prompt edit. No re-dispatch of the pilot subagent (output unchanged). Specific revisions (committed in `a6749eb`):

- `b-r-shenoy`: extended → core (subject essay "India's first neoliberal" + 10+ authored works)
- `mahadev-govind-ranade`: extended → core (3 subject essays)
- `benjamin-tucker`: core → referenced (1 mention)
- `a-p-j-abdul-kalam`: extended → referenced (1 mention)
- `mahatma-gandhi`: unclassified → referenced (43 mentions, unclassified implausible)
- `rabindranath-tagore`: unclassified → extended (13 mentions)
- `bhimrao-ambedkar`: constitutional_liberal → social_reformer (subject essay title)
- `ludwig-von-mises`: classical_liberal → libertarian (rubric's own eponym)

## Bulk run

**10 parallel Agent subagents over 10 batches of 50-51 thinkers, dispatched in a single message.**

| Batch | Records | Outcome |
|---|---|---|
| 00 | 51 | 51 ok, 0 rejected — schema-clean |
| 01 | 51 | 51 ok, 0 rejected |
| 02 | 51 | 51 ok, 0 rejected |
| 03 | 51 | 51 ok, 0 rejected |
| 04 | 51 | 51 ok, 0 rejected |
| 05 | 51 | 51 ok, 0 rejected |
| 06 | 50 | 50 ok, 0 rejected |
| 07 | 50 | 50 ok, 0 rejected |
| 08 | 50 | 50 ok, 0 rejected |
| 09 | 50 | 50 ok, 0 rejected |
| **Total** | **506** | **506 ok, 0 rejected, 0 re-dispatches needed** |

No subagent emitted the forbidden `tradition: international_influence` value. All 506 input IDs are echoed in the union of output records (verified via `jq | sort -u | wc -l`).

**Applier outcome:**
- 453 thinker MDs actually modified (53 already matched AI output and produced no diff)
- 373 records had at least one medium/low axis → `needs_review: true` (set or preserved)
- 506 reasoning paragraphs logged to `data/classify-thinkers/reasoning-log.md` (untracked, regenerable)
- 0 schema rejections
- Output-stable: re-running the applier with the same outputs produced 0 file changes (spec §7.2)

## Post-run coverage breakdown

(from [data/classify-thinkers/coverage-report.md](data/classify-thinkers/coverage-report.md), itself committed in `b16d0c5`)

### By canon_status (506 total)
- `core`: **29**
- `extended`: **170**
- `referenced`: **222**
- `unclassified`: **85**

### By tradition (506 total)
- `classical_liberal`: 154
- `contemporary_liberal`: 116
- `social_reformer`: 51
- `non_liberal`: 49
- `constitutional_liberal`: 46
- `practice`: 35
- `unclassified`: 22
- `libertarian`: 17
- `international_influence` (DEPRECATED, see Deferred Item 1): 16

### Top vocations
writer 210, economist 117, statesman 93, civil_servant 58, reformer 47, industrialist 46, professor 44, activist 44, editor 33, parliamentarian 31, journalist 27, philosopher 25, legal_scholar 20.

### `/thinkers` index sections after build
- Liberal canon: **29** cards (was 0 pre-bulk)
- Extended liberal tradition: **156** cards (was 0)
- Referenced thinkers: **180** cards (was 0)
- Awaiting classification: **37** cards (was 402)

The "Awaiting" section shrank from 402 (every visible thinker) to 37 (low-confidence canon_status), confirming spec §10.5 #23.

## Curator triage queue size (sub-project 3 seed)

**506 thinkers carry `needs_review: true` on disk** after the bulk run. This is because:
- All 506 thinkers were `needs_review: true` pre-bulk (a state set by the May 2026 thinker-classification migration before SP2 started).
- The applier sets `needs_review: true` on records where at least one axis was medium/low (373 records).
- The applier never downgrades `needs_review: true` to `false` (spec §7.1 — that's curator territory).

So the post-bulk `needs_review: true` count is unchanged at 506, but the **meaningful new triage signal** is the 373 records the applier flagged. Sub-project 3 will need a CLI or UI to triage those 373 (or to filter the 506-strong queue).

## Spec §10 acceptance verification

| § | # | Criterion | Status |
|---|---|---|---|
| 10.1 | 1 | Schema CLI exits 0 on well-formed array | ✅ |
| 10.1 | 2 | Malformed `canon_status` rejected with precise error | ✅ (Chunk 1 tests) |
| 10.1 | 3 | `tradition: international_influence` rejected as forbidden | ✅ (Chunk 1 tests) |
| 10.1 | 4 | Record missing any of 3 confidence axes rejected | ✅ (Chunk 1 tests) |
| 10.2 | 5 | `--bootstrap` emits 30-thinker template | ✅ |
| 10.2 | 6 | `--diff` emits `pilot-diff-report.md` with per-axis percentages | ✅ |
| 10.2 | 7 | Bulk-run gate triggers iteration if any axis <80% | ✅ (initial pilot triggered iteration; ground-truth revision per §9.4 → PASS) |
| 10.2 | 8 | Agreement computed per axis; Jaccard ≥0.6 for vocations | ✅ |
| 10.3 | 9 | Exactly 10 batch JSONLs in `data/classify-thinkers/batch-{00..09}.jsonl` | ✅ |
| 10.3 | 10 | Every batch record validates against §5 schema | ✅ |
| 10.3 | 11 | Union of batches = 506 unique IDs | ✅ |
| 10.3 | 12 | Mention contexts truncated (max 10/thinker, ~150-250 chars each) | ✅ |
| 10.4 | 13 | All 10 `output-NN.json` exist after dispatch | ✅ |
| 10.4 | 14 | Each output validates against §6 schema | ✅ (0 rejections × 10) |
| 10.4 | 15 | Union of all output IDs = 506 unique | ✅ |
| 10.4 | 16 | `--dry-run` reports would-modify count; touches no files | ✅ (`would modify 453`; `git status` confirmed 0 actual diffs) |
| 10.4 | 17 | Live applier modifies MDs per §7 confidence rule | ✅ (spot-checked all-high, mixed, any-low cases — see Spot-check Table below) |
| 10.4 | 18 | Applier output-stable: re-apply produces 0 file changes | ✅ (verified via second `apply-classify-thinkers.py` run + `git diff --stat`) |
| 10.4 | 19 | `reasoning-log.md` contains an entry per processed thinker | ✅ (506 `## <id>` sections) |
| 10.4 | 20 | `needs_review: true` on every record with ≥1 medium/low axis | ✅ (applier reported 373; all 373 verifiable via reasoning-log + on-disk MDs) |
| 10.5 | 21 | `pnpm build` exits clean, 1185 pages | ✅ |
| 10.5 | 22 | `/thinkers` renders non-empty `core` / `extended` / `referenced` sections | ✅ (29 / 156 / 180 cards respectively) |
| 10.5 | 23 | Awaiting section smaller than day-1 | ✅ (37 vs 402) |
| 10.5 | 24 | Spot-check rendered HTML for 4 thinker cards | ✅ |
| 10.6 | 25 | `coverage-report.md` has per-canon_status, per-tradition, per-vocations + needs_review queue | ✅ |
| 10.6 | 26 | Report makes curator-hours-of-review answerable at a glance | ✅ (373 medium/low flagged records itemised) |
| 10.7 | 27 | PUCL Gujarat saffron pill renders | ✅ (`grep -c "PUCL Gujarat" .../khoj.../index.html` matches) |
| 10.7 | 28 | `/organisations/pucl-gujarat/` renders | ✅ |
| 10.7 | 29 | `/thinkers/dadabhai-naoroji/` renders | ✅ |
| 10.7 | 30 | Page count unchanged at 1185 | ✅ |

### Spot-check table (§10.4 #17)

| Slug | Confidence | Result on disk |
|---|---|---|
| `begum-rokeya` | all-high | tradition=social_reformer, canon_status=extended, vocations=[reformer, writer, activist], needs_review=true (preserved from pre-bulk) |
| `abraham-lincoln` | medium tradition, high canon_status + vocations | tradition=non_liberal (written), canon_status=referenced (written), vocations=[statesman, writer] (written), needs_review=true (set by medium) |
| `a-c-chhatrapati` | medium tradition, high canon_status, low vocations | tradition=classical_liberal (written), canon_status=referenced (written), vocations=[] (preserved at default per low-confidence rule), needs_review=true |

## Review-loop iterations

| Chunk | Implementer | Spec review | Code review |
|---|---|---|---|
| 3 (applier + audit) | DONE (first pass) | ✅ Approved (first pass) | ✅ Approved-with-2-Important-cleanups (first pass) → fixed inline → re-approved by spec verification |
| 4 (pilot) | n/a (operational) | n/a | n/a (single iteration loop; ground-truth-revision path) |
| 5 (bulk) | 10 parallel implementers | n/a — schema validation served as automated spec review | n/a — operational batch processing |

Chunk 3's two Important code-quality items (I1: conflated `--pilot`/non-pilot guard; I3: cryptic precondition error if `pilot-batch.jsonl` missing) were both addressed inline before the commit landed.

## Deviations from the spec/plan (with rationale)

### Deviation 1 — Pilot iteration via GT revision, not prompt amendment

**What:** Spec §9.4 envisions iteration via prompt amendment (rubric tightening, anchor additions). The pilot's first run failed canon_status at 70%, and §9.4 explicitly allows "ambiguous ground truth → propose adjusting the ground truth" as an iteration path. After verifying against actual corpus engagement, 8 of the 15 disagreements (6 canon_status + 2 tradition) were judged to be GT errors rather than AI failures — and the GT was revised with Adnan's approval. No prompt edit; no pilot re-dispatch (AI output unchanged).

**Impact:** Pilot passed at 90/86.7/86.7. The bulk run used the unmodified prompt (rendered after Chunk 2, slug-fixed at `5558492`).

**Action:** Documented here. The committed `pilot-ground-truth.json` (`a6749eb`) preserves both the pre- and post-revision call as a `_note` field per entry, so future calibration loops have visibility into which calls were judgment-revised.

### Deviation 2 — Pilot subagent ran a 81/18/1 confidence distribution, hotter than the prompt's 60-70/20-30/5-15 target

**What:** The pilot subagent self-reported the distribution as "slightly hotter than the 60-70% high target but defensible given the batch contained many anchor-grade canonical figures." The pilot's batch was deliberately hand-curated to include 8 anchor examples + 22 well-known validation figures, so the high confidence rate is expected on this batch composition.

**Impact:** None on calibration — the pilot still passed the 80% per-axis agreement threshold. The bulk run's per-batch subagents reported more realistic distributions (50-65% high typical) on the random-sorted bulk batches.

**Action:** No action needed. The pilot's confidence calibration is meaningful only for the pilot's own batch composition (which is anchor-heavy).

## Deferred items

### Item 1 — `tradition: international_influence` retirement

**What:** 16 thinkers ended with `tradition: international_influence` on disk after the bulk run. The AI was forbidden from emitting this value (spec §6.1), and the schema validator would have rejected any record that did. The 16 residual entries are cases where the AI gave **low confidence on the `tradition` axis**, so the applier left the existing value untouched per the spec §7 confidence rule — and the pre-bulk value for those was `international_influence`.

**Status:** The schema in `apps/site/src/content.config.ts` still accepts the deprecated value (added back in Chunk 1 of the prior thinkers-classification work; spec amendment from Adnan kept it to avoid breaking pre-existing entries). The 16 records ARE flagged `needs_review: true` for curator triage.

**Action:** Sub-project 3's curator review can resolve the 16 manually. After resolution, the `international_influence` enum could be dropped from `content.config.ts` (~2-line cleanup commit) and the schema-validator's `TRADITION_FORBIDDEN` would still gate any AI re-runs.

### Item 2 — Spec / plan slug references to `f-a-hayek` / `h-r-khanna`

**What:** The spec doc and plan doc still reference the old anchor slugs `f-a-hayek` and `h-r-khanna`. Those were corrected on-disk by `5558492` (the slug fix) and the pipeline files all use the correct on-disk slugs (`friedrich-hayek`, `hans-raj-khanna`). The reference docs were left untouched per the handoff note's "post-Chunk-5 hygiene" deferral.

**Action:** Small spec-doc commit if Adnan wants alignment. Pipeline is source-of-truth; the docs' stale slugs are a reading artifact only.

### Item 3 — Pilot-mode test coverage

**What:** `apply-classify-thinkers.py:main()` has a `--pilot` flag (per plan §3.1.1) that was exercised only operationally (Chunk 4) and not by automated tests. The Task 3.1 code-quality reviewer flagged this as a "low-stakes future-proofing" gap.

**Action:** A small `test_apply_classify_thinkers_pilot_smoke.py` could exercise the flag with a tempdir-mock setup. Not blocking; the operational pilot did exercise the path end-to-end.

### Item 4 — Reasoning log format coupling

**What:** `audit-classify-thinkers-coverage.py:76` parses the reasoning-log entries with a regex that hard-codes the format emitted by `apply-classify-thinkers.py:_format_log_chunk`. A comment was added inline noting the coupling. If the format is ever changed, both must be updated together.

**Action:** Cosmetic only. The audit script's "By per-record confidence" section will silently report zeros if the formats diverge — caught by next-day curator review, not by automation.

### Item 5 — Reasoning log doubling on re-apply (RESOLVED at `b4510d2`)

**What:** The applier writes `data/classify-thinkers/reasoning-log.md` in append mode per spec §3.1.1 ("Re-runs append again — the log is intentionally append-only across runs so curators can diff between runs"). The §10.4 #18 output-stability acceptance check necessarily re-runs the applier, which doubled the log from 506 to 1012 sections. Without a defensive fix, anyone re-running `audit-classify-thinkers-coverage.py` after the SP2 push would see inflated "By per-record confidence" counts.

**Resolution:** The audit script (`b4510d2`) now dedupes by `## <id>` header keeping the latest occurrence, so the per-record confidence breakdown is robust to any number of re-applies. The committed `coverage-report.md` from `b16d0c5` was regenerated byte-identical against the deduped logic (133 all-high / 213 medium-mixed / 160 any-low). The append-only log itself is unchanged — curators can still diff across runs.

**Surfaced by:** Final SP2 code review (post-summary, pre-push).

## Notes for push

**Branch state:** `main` is **35 commits ahead** of `origin/main` (9 of those landed in this SP2 work; the rest were prior work — org-authorship, thinkers-classification, pre-existing migrations).

**What `git push origin main` will land:**
- All nine SP2 commits (`f2cabed`, `038ef9d`, `5558492`, `17e12dd`, `673c45d`, `a6749eb`, `b16d0c5`, `f2804f7`, `b4510d2`).
- The 26 prior commits already on local `main`.

**What `git push` will NOT land:**
- `data/classify-thinkers/batch-*.jsonl` (untracked per `.gitignore`)
- `data/classify-thinkers/output-*.json` (untracked)
- `data/classify-thinkers/reasoning-log.md` (untracked)
- `data/classify-thinkers/pilot-output.json` / `pilot-diff-report.md` / `pilot-batch.jsonl` (untracked)

These are regenerable from `scripts/synthesis/` + the committed `pilot-ground-truth.json`. Fresh-clone reproducibility: `python3 scripts/synthesis/prepare-classify-thinkers-batches.py && python3 scripts/synthesis/render-system-classify-thinkers.py` → ready to dispatch.

**Recommended push sequence (Adnan's call):**
1. `git log --oneline 5558492..HEAD` — visual confirmation.
2. `cd apps/site && pnpm build` — final sanity check.
3. `git push origin main` — assuming Adnan is satisfied with the bulk classifications and the 373-strong review queue.

## What this enables next

- **Sub-project 3 (curator review tooling):** the 373 medium/low-confidence triage queue is now a concrete, on-disk artifact. Whatever CLI or UI sub-project 3 builds has real data to work against.
- **Thinker detail-page redesign:** the new `canon_status` / `tradition` / `vocations` frontmatter is now populated; `/thinkers/<slug>/` page surfacing is a future spec with real fields to show.
- **Cross-axis filtering on `/thinkers`:** Pagefind `canon-status:` and `vocation:` filters now have real values across the corpus — implementing a facet UI is plausible.
- **`international_influence` cleanup:** sub-project 3 can resolve the 16 residual cases and the deprecated enum value can be dropped from the schema.
