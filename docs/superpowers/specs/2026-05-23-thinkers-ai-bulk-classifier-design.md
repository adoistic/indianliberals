# Thinkers AI Bulk Classifier — Design Spec

**Author:** Adnan
**Date:** 2026-05-23
**Status:** locked

## 1. Goal

Populate `canon_status` / `tradition` / `vocations` across all 506 thinker MDs via a parallel-subagent classification pipeline, reusing the May 18 musings/opinions classification pipeline shape with one addition: a **pilot calibration phase** before the bulk run.

Ideological classification has higher subjective stakes than the topical classification the May 18 pipeline did. The pilot calibrates the system prompt against 30 hand-picked ground-truth thinkers before committing 506 entries to whatever the AI says.

The terminal state of this work: every thinker MD ends in one of three states —

1. **All three axes classified at `high` confidence** — auto-written to frontmatter, `needs_review` unchanged.
2. **Some axes `high`, some `medium`** — high-confidence axes written; medium-confidence axes written but `needs_review: true` set on the record.
3. **At least one axis `low`** — that axis stays at its default (canon_status: `unclassified`, tradition: `unclassified`, vocations: `[]`), record gets `needs_review: true`. The AI's reasoning paragraph for that axis is logged to a side artifact (`data/classify-thinkers/reasoning-log.md`) so the curator has the AI's thinking even when the field wasn't written.

The `/thinkers` index page populates its four canon-status sections automatically as a side effect of the new frontmatter.

## 2. Non-goals

- **Curator review tooling** (sub-project 3 — separate spec). The `needs_review: true` flag + the reasoning log + the coverage report are the v1 review surface; no curator-review UI is built.
- **Re-running musings/opinions classification.** That pipeline (May 18) is already shipped; not in scope here. We reuse its scripts as templates, not its data.
- **Thinker detail-page redesign.** The new fields exist in frontmatter; surfacing them on `/thinkers/<slug>/` is a future spec.
- **The AI editing any other thinker frontmatter field.** The applier touches only `canon_status`, `tradition`, `vocations`, and `needs_review`. `bio_source`, `themes`, `affiliations`, `birth_year`, `death_year`, `nationality`, `portrait`, etc. stay untouched.
- **Sweeping organisations.** Only thinkers in this pipeline; organisations' classification is unaddressed.

## 3. Scope

- **Pilot stage:** 30 hand-picked thinkers spanning all canon_status / tradition cells. Curator writes ground truth; script diffs AI output against it; iterate the system prompt until ≥80% per-axis agreement.
- **Bulk stage:** all 506 thinkers in 10 parallel batches (~50 each).
- **Six new scripts + one schema module** in `scripts/synthesis/` mirroring the May 18 shape, with a new `pilot-classify-thinkers.py` step the May 18 pipeline doesn't have.
- **New data directory** `data/classify-thinkers/` for batches, outputs, reasoning log, coverage report, and pilot artifacts.
- **No new content collections.** The pipeline writes to existing `apps/site/src/content/thinkers/*.md` frontmatter only.

## 4. Pipeline architecture

Seven steps in choreography, mapped to six scripts + one schema module. Dispatch happens inside the Max session via parallel Agent subagents — zero `claude -p` budget consumption, same as May 18.

```
┌─────────────────────────────── PILOT ────────────────────────────────┐
│ Step 0  curator hand-writes data/classify-thinkers/pilot-ground-     │
│         truth.json — 30 thinkers × {canon_status, tradition,         │
│         vocations}                                                   │
│ Step 1  dispatch 1 Agent subagent against the 30-thinker batch       │
│         → output stored, diffed against ground truth                 │
│ Step 2  pilot-classify-thinkers.py --diff → per-axis agreement       │
│         report. If <80% on any axis, iterate the system prompt and   │
│         re-run Step 1. Loop until >80% (or surface to human).        │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────── BULK ─────────────────────────────────┐
│ Step 3  prepare-classify-thinkers-batches.py                         │
│         → data/classify-thinkers/batch-{00..09}.jsonl                │
│           (10 batches × ~50 thinkers, plus mention-context           │
│           assembly from primary-works/opinions/musings/…)            │
│ Step 4  dispatch 10 parallel Agent subagents (one per batch);        │
│         each gets the rendered system prompt + the batch JSONL       │
│         → data/classify-thinkers/output-{00..09}.json                │
│ Step 5  apply-classify-thinkers.py                                   │
│         → updates apps/site/src/content/thinkers/*.md per the        │
│           confidence rule from §7; logs reasoning paragraphs to      │
│           data/classify-thinkers/reasoning-log.md                    │
│ Step 6  audit-classify-thinkers-coverage.py                          │
│         → data/classify-thinkers/coverage-report.md                  │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.1 Scripts

| File | Role |
|---|---|
| `scripts/synthesis/classify_thinkers_schema.py` | Validates output JSON against §6 schema; reusable from both pilot and bulk paths |
| `scripts/synthesis/pilot-classify-thinkers.py` | `--bootstrap` emits a `pilot-ground-truth.json` template with 30 IDs; `--diff` diffs AI output against ground truth |
| `scripts/synthesis/prepare-classify-thinkers-batches.py` | Step 3: emit 10 batch JSONLs with per-thinker input records per §5 |
| `scripts/synthesis/render-system-classify-thinkers.py` | Renders `scripts/synthesis/prompts/system-classify-thinkers.txt` from rubric + 8 anchor examples |
| `scripts/synthesis/apply-classify-thinkers.py` | Step 5: merge outputs into frontmatter per confidence rules; `--dry-run` supported |
| `scripts/synthesis/audit-classify-thinkers-coverage.py` | Step 6: coverage breakdown by canon_status / tradition / vocation + needs_review queue |

### 4.2 Data directory

```
data/classify-thinkers/
  pilot-ground-truth.json       # hand-written by curator (30 entries)
  pilot-output.json             # AI output for the 30 pilot thinkers
  pilot-diff-report.md          # per-axis agreement breakdown; gates bulk run
  batch-00.jsonl … batch-09.jsonl
  output-00.json … output-09.json
  reasoning-log.md              # per-thinker AI reasoning + confidence vectors
  coverage-report.md            # post-bulk coverage breakdown
```

### 4.3 Dispatch mechanics

Per May 18 §6, dispatch happens via parallel Agent subagent invocations inside the Max session — zero `claude -p` cost. Each subagent receives:
- The rendered system prompt (`scripts/synthesis/prompts/system-classify-thinkers.txt`) as its system-instruction
- One batch JSONL as user-message input (passed as a file path the subagent reads, or inlined into the prompt body — implementation choice)
- The target output path it MUST write its result to (`data/classify-thinkers/output-NN.json` where NN matches the batch number)
- Instructions to write a JSON array of classification objects to that path AND return a one-line confirmation in its final message

The pilot stage uses 1 subagent; bulk uses 10 in parallel. The controller (this session, when execution lands) is responsible for batch→subagent assignment, passing the right output path per dispatch, and post-dispatch verification: confirming each `output-NN.json` exists and validates against the §6 schema before proceeding to the applier. If a subagent fails to write its output (file missing or schema-invalid), the controller re-dispatches just that batch.

## 5. Input record schema (one per thinker in a batch JSONL)

```json
{
  "id": "dadabhai-naoroji",
  "name": {
    "canonical": "Dadabhai Naoroji",
    "sort": "Naoroji, Dadabhai",
    "also_known_as": []
  },
  "birth_year": 1825,
  "death_year": 1917,
  "nationality": "india",
  "current_fields": {
    "tradition": "nationalist_liberal",
    "canon_status": "unclassified",
    "vocations": [],
    "themes": ["economic-policy", "free-enterprise"],
    "affiliations": ["indian-national-congress"],
    "bio_source": "ai_drafted_stub"
  },
  "bio_excerpt": "<first ~3000 chars of the MD body, verbatim>",
  "works_authored": [
    {"id": "poverty-and-un-british-rule-in-india", "title": "Poverty and Un-British Rule in India", "year": 1901, "work_type": "book"}
  ],
  "mention_contexts": [
    {"source": "opinions/gg-agarkar-revisiting-a-misunderstood-legacy", "excerpt": "…Naoroji's drain theory anticipated…", "role": "thinker_mention"},
    {"source": "primary-works/some-slug", "excerpt": "…the constitutional moderates including Naoroji and Gokhale…", "role": "related_thinker"}
  ]
}
```

### 5.1 Field rules

- `current_fields` exists so the AI can use existing classification as a prior, but the system prompt explicitly instructs "re-classify from first principles, not by deferring to current_fields." Reclassification is the whole point.
- `bio_excerpt` truncated to **MAX_BODY_CHARS = 3000** (matches May 18). For sub-3000-char bios (most `ai_drafted_stub` entries), full body is sent.
- `works_authored` lists primary-works where this thinker appears in `authors[]`. Truncated to 20 most-recent entries if longer.
- `mention_contexts` lists up to 10 most-relevant excerpts where this thinker appears in `thinker_mentions[].thinker` / `related_thinkers[]` / `subject` across the corpus. Relevance ordering: (1) opinions where they're the `subject`; (2) primary-works where they appear in `thinker_mentions[]` more than once; (3) other mentions. Each excerpt is the sentence around the mention (~150-250 chars).
- For super-popular thinkers (Rajaji, Naoroji), the 10-mention cap prevents single-record bloat.
- Estimated record size: 3-8 KB per thinker. Batch of 50 thinkers ≈ 150-400 KB JSONL.

### 5.2 Notes on the existing `tradition` value

The deprecated value `international_influence` (86 entries on disk) still appears in `current_fields.tradition` for those entries. The AI is told (in §8 system prompt) that this is a deprecated value and must NEVER be in its output — the AI must pick a replacement value from the 9 allowed enum values, with foreignness handled by the existing `nationality` field which the AI does not modify.

## 6. Output record schema (one per thinker, returned by subagent)

```json
{
  "id": "dadabhai-naoroji",
  "canon_status": "core",
  "tradition": "constitutional_liberal",
  "vocations": ["statesman", "economist", "writer"],
  "confidence": {
    "canon_status": "high",
    "tradition": "high",
    "vocations": "high"
  },
  "reasoning": "Naoroji is foundational to the Indian constitutional-liberal tradition — first Indian MP in the British Parliament, Congress president three times, author of *Poverty and Un-British Rule in India* which established the 'drain theory'. His vocations span statesman, economist, and writer. The corpus references him heavily as a constitutional-moderate counterweight to revolutionary nationalism."
}
```

### 6.1 Field rules

- `id` MUST echo the input id so the applier can match output→input. A record missing `id` or with an unknown `id` is rejected.
- `canon_status` MUST be one of: `core` | `extended` | `referenced` | `unclassified`. Validated against the §6.3 schema.
- `tradition` MUST be one of the **8 allowed values**: `classical_liberal`, `libertarian`, `constitutional_liberal`, `contemporary_liberal`, `social_reformer`, `non_liberal`, `practice`, `unclassified`. The post-Chunk-2 thinker schema accepts a 9th value, `international_influence`, but that value is DEPRECATED and **FORBIDDEN in AI output**. The applier-side schema rejects records emitting it; this is the only enum the AI must explicitly avoid. Foreignness is captured by the existing `nationality` field (which the AI does not modify).
- `vocations` MUST be a (possibly empty) array of values from the 25-value vocation enum. Order matters editorially — "most central first" (Hayek = `[philosopher, economist, professor]` reads better than `[professor, economist, philosopher]`). The applier preserves the AI's order.
- `confidence` is an object with one `high|medium|low` per axis. All three keys MUST be present.
- `reasoning` is a single string, ~50-200 words, one paragraph. The applier writes this to `data/classify-thinkers/reasoning-log.md` keyed by thinker id.

### 6.2 Validation rejections

The `classify_thinkers_schema.py validate` step rejects a record if any of:
- `id` missing, or not in the input batch.
- `canon_status` not in the 4-value enum.
- `tradition` not in the 8 allowed values, OR `tradition == international_influence` (explicit forbidden value per §6.1).
- `vocations` contains a value not in the 25-value enum.
- `confidence` missing or doesn't have all three required keys.
- `reasoning` missing or empty.

Rejected records are logged and SKIPPED by the applier (the thinker MD stays untouched). The coverage report counts rejected records; the curator triages them manually.

### 6.3 Schema module (`classify_thinkers_schema.py`)

Lives at `scripts/synthesis/classify_thinkers_schema.py`. Mirror of May 18's `classify_schema.py` shape; exports:

```python
CANON_STATUS_VALUES = ("core", "extended", "referenced", "unclassified")
TRADITION_VALUES = (
    "classical_liberal", "libertarian", "constitutional_liberal",
    "contemporary_liberal", "social_reformer", "non_liberal",
    "practice", "unclassified",
)
TRADITION_FORBIDDEN = ("international_influence",)  # explicit reject
VOCATIONS_VALUES = (
    "philosopher", "economist", "historian", "political_scientist",
    "sociologist", "legal_scholar", "scientist", "engineer", "professor",
    "writer", "editor", "journalist", "poet",
    "statesman", "parliamentarian", "civil_servant", "diplomat", "judge",
    "industrialist", "entrepreneur",
    "activist", "reformer", "religious_figure",
    "military_officer", "artist",
)
CONFIDENCE_VALUES = ("high", "medium", "low")

def validate_record(rec: dict, input_ids: set[str]) -> tuple[bool, list[str]]:
    """Returns (ok, errors). errors is a list of human-readable validation failures."""
    ...
```

## 7. Applier semantics (confidence rule)

Per `apply-classify-thinkers.py` for each validated output record:

| Axis confidence | Action on the thinker's MD |
|---|---|
| `high` | Write the AI value to frontmatter |
| `medium` | Write the AI value to frontmatter AND set `needs_review: true` on the record |
| `low` | Do NOT write the AI value; leave that axis at its existing/default value AND set `needs_review: true` |

### 7.1 Always-applied actions per record

- Append the AI's `reasoning` paragraph (with id + confidence vector) to `data/classify-thinkers/reasoning-log.md`.
- If any axis was `medium` or `low`: set `needs_review: true`.
- If all three axes were `high`: leave `needs_review` at its current value (typically `false` for prior curator-reviewed entries; `true` for `ai_drafted_stub` entries — the applier doesn't downgrade `needs_review` from `true` to `false`).

### 7.2 Overwrite semantics

- The applier OVERWRITES `canon_status`, `tradition`, `vocations` per the confidence rule. This is intentional — Adnan's "from first principles, reclassify all" directive.
- The applier does NOT touch any other frontmatter field (except `needs_review` per §7.1).
- **Applier-output-stability rather than pure idempotency.** Re-running the applier on the same output JSONs produces zero additional changes IF no curator edit has happened in between. But: if a curator clears `needs_review: false` between runs and the AI output for that thinker still has any medium/low axis, the re-run re-sets `needs_review: true`. This is intentional — the AI's stated confidence hasn't changed, so the review need hasn't either. The curator's clearing of `needs_review` is meaningful only if the AI's confidence vector also changes (which requires a new classification run with a refined prompt). Stable; not pure idempotency.

### 7.3 Side log shape (`reasoning-log.md`)

```markdown
## dadabhai-naoroji

**Confidence:** canon_status=high, tradition=high, vocations=high
**Result:** core / constitutional_liberal / [statesman, economist, writer] — all auto-written

> Naoroji is foundational to the Indian constitutional-liberal tradition…

---

## mukesh-ambani

**Confidence:** canon_status=medium, tradition=high, vocations=high
**Result:** referenced / practice / [industrialist] — canon_status written but needs_review=true

> Mukesh Ambani is referenced in the corpus through interviews on Indian economic reform; he's not an ideological figure himself…

---

## obscure-thinker-x

**Confidence:** canon_status=low, tradition=low, vocations=medium
**Result:** vocations=[writer] written; canon_status + tradition left at default; needs_review=true

> The bio is a 1-line stub; no mention contexts exist…
```

The log is append-only across runs; reruns add new sections (the curator can diff between runs if they want).

## 8. System prompt structure

Rendered by `render-system-classify-thinkers.py` into `scripts/synthesis/prompts/system-classify-thinkers.txt`. Estimated 3500-4500 chars after rendering.

### 8.1 Sections (in render order)

1. **Preamble** — one paragraph; "classify Indian liberal-tradition figures along three independent dimensions."
2. **`canon_status` rubric** — definition of each tier, with the "would removing this figure leave a hole?" heuristic.
3. **`tradition` rubric** — definition of each value; **explicit prohibition on `international_influence`**; foreignness goes via the existing `nationality` field which the AI must not modify.
4. **`vocations` rubric** — the 6 categories, semantics of `writer` vs `professor` vs `industrialist` vs `entrepreneur`, ordering convention (most central first).
5. **Confidence calibration** — definitions of high/medium/low + calibration check ("60-70% high, 20-30% medium, 5-15% low across a batch").
6. **8 anchor examples** — Hayek (foreign, core, classical_liberal, multi-vocation), Rajaji (core, classical_liberal, multi-vocation), Naoroji (core, constitutional_liberal, multi-vocation), Raja Ram Mohan Roy (core, social_reformer, multi-vocation), J.R.D. Tata (extended, practice, single-vocation, **deliberately borderline — explains why not `core`**), Justice H.R. Khanna (extended, constitutional_liberal, single-vocation judge), Mukesh Ambani (referenced, practice, non-political), Nehru (referenced, non_liberal, **explicit framing: not editorial endorsement**).
7. **Output format spec** — the exact JSON shape the AI must return; "Output the array AS THE ENTIRE RESPONSE, no preamble or postamble text."

### 8.2 What the prompt does NOT contain

- No reference to `needs_review` — applier's job.
- No reference to side-log artifacts — applier territory.
- No reference to the other 22 pilot ground-truth thinkers — the 8 anchor examples are the prompt's pedagogical surface; the other 22 are validation-only.
- No file-edit instructions — the AI's only job is to return JSON.

## 9. Pilot calibration loop

The pilot is the gate between "we wrote a prompt" and "we trust the prompt enough to run all 506."

### 9.1 Pilot ground-truth bootstrap

`pilot-classify-thinkers.py --bootstrap` emits `data/classify-thinkers/pilot-ground-truth.json` with a pre-selected list of 30 thinker IDs:

- 8 anchor-example IDs (the same ones in the system prompt): hayek, rajagopalachari, naoroji, raja-ram-mohan-roy, jrd-tata, hr-khanna, mukesh-ambani, jawaharlal-nehru.
- 22 additional IDs spanning the canon_status / tradition cells, hand-picked by Adnan during pilot prep. The bootstrap script emits a stub list (just IDs); Adnan fills in the expected `canon_status`, `tradition`, `vocations` for each.

The 22 IDs should cover:
- 5+ `core` (including at least one libertarian — Mises if in corpus — and one contemporary_liberal),
- 5+ `extended` (mix of constitutional_liberal, contemporary_liberal, social_reformer, practice),
- 5+ `referenced` (a Marxist, a Hindu-nationalist, a non-political figure, etc.),
- A few `unclassified` (genuinely cross-cutting figures where Adnan thinks the AI should mark low-confidence on at least one axis — e.g., a figure who straddles social_reformer and non_liberal).

**Anchor↔pilot overlap:** the 8 anchor-example IDs above double as anchor examples in the rendered system prompt (§8.1 item 6). Their AI output is a sanity check on prompt fidelity — if the AI gets even its own anchor examples wrong, the prompt rendering is broken. The other 22 IDs are validation-only — they never appear in the prompt, so AI agreement on them is the clean signal of generalization. Per-axis agreement metrics in the diff report are computed across all 30, but the controller should also eyeball the 22-only subset to confirm the AI isn't just memorising the prompt.

### 9.2 Pilot dispatch

Step 1 dispatches ONE Agent subagent against a single batch containing all 30 pilot thinkers (input records prepared by `prepare-classify-thinkers-batches.py --pilot`). Returns `pilot-output.json`.

### 9.3 Pilot diff

`pilot-classify-thinkers.py --diff` produces `pilot-diff-report.md`:

```markdown
# Pilot diff report — 2026-MM-DD HH:MM

## Per-axis agreement

| Axis | Agreement | Threshold | Pass? |
|---|---|---|---|
| canon_status | 27/30 = 90% | 80% | ✅ |
| tradition | 25/30 = 83% | 80% | ✅ |
| vocations (Jaccard ≥ 0.6) | 28/30 = 93% | 80% | ✅ |

**Overall:** PASS — bulk dispatch authorized.

## Disagreements (3 thinkers)

### mukesh-ambani
- ground_truth: { canon_status: referenced, tradition: practice, vocations: [industrialist] }
- ai_output:    { canon_status: extended,   tradition: practice, vocations: [industrialist] }
- delta: canon_status (extended vs referenced)
- ai_reasoning: "…appears in corpus more than once as an interviewee on Indian economic reform…"

…
```

### 9.4 Bulk-run gate

If per-axis agreement is **≥80% on ALL three axes**, the pilot passes and the bulk run is authorized.

If any axis is below 80%:
- **Iteration mechanics:** the controller (the controlling Claude session that orchestrates this pipeline) reads the diff report, proposes specific prompt amendments to Adnan (e.g., "add an anchor example for the missing canon_status=extended case", "tighten the rubric language for tradition=practice"), and on approval edits the rubric source / anchor-example file feeding `render-system-classify-thinkers.py`. The curator does NOT edit raw prompt text directly; all changes go through the renderer so re-renders are reproducible.
- Re-renders the system prompt via `render-system-classify-thinkers.py`.
- Re-runs Step 1 with the updated prompt.
- Re-runs the diff.
- Max 5 iterations before surfacing to Adnan for an explicit "ship as-is or escalate" decision (matches the spec-review-loop convention).

### 9.5 Vocations agreement metric

Vocations is multi-valued, so equality is set-similarity (Jaccard index):
- For thinker T, ground_truth set GT and AI output set AI, similarity = |GT ∩ AI| / |GT ∪ AI|.
- A thinker counts as "agreement" if Jaccard ≥ 0.6. (Hayek truth=[philosopher, economist, professor], AI=[philosopher, economist] → Jaccard 2/3 ≈ 0.67 → agreement. Truth=[philosopher, economist, professor], AI=[philosopher, statesman] → Jaccard 1/4 = 0.25 → disagreement.)

The 0.6 threshold is a first-pass estimate, not an empirically-validated cutoff. It sits between "Hayek's 2-of-3 vocations match" (Jaccard 0.67 → agreement) and "1-of-4 vocations match" (Jaccard 0.25 → disagreement). Tunable during pilot: if the diff report flags too many false positives (cases where Adnan judges the AI's set substantively correct but Jaccard < 0.6), lower the threshold. If too many false negatives, raise.

## 10. Validation criteria

Each numbered criterion is independently verifiable.

### 10.1 Schema validation

1. `classify_thinkers_schema.py validate <output.json>` exits 0 for a well-formed array; non-zero for malformed.
2. A malformed test record (`canon_status: bogus`) is rejected with file + record id + field + allowed-enum error.
3. A record with `tradition: international_influence` is rejected (explicit forbidden value per §6.1).
4. A record missing any of the three confidence axes is rejected.

### 10.2 Pilot acceptance

5. `pilot-classify-thinkers.py --bootstrap` emits a template `pilot-ground-truth.json` with 30 thinker IDs (8 anchors + 22 curator-picked; curator fills the three axes per entry).
6. After Step 1 produces `pilot-output.json`, `pilot-classify-thinkers.py --diff` emits `pilot-diff-report.md` with per-axis agreement percentages.
7. **Bulk-run gate:** if per-axis agreement is <80% on ANY axis, do NOT proceed to bulk. Iterate prompt; re-run pilot. Loop up to 5 iterations.
8. Agreement per axis is computed as `(records where AI value == ground truth) / 30`. For vocations, Jaccard ≥ 0.6 counts as agreement.

### 10.3 Bulk batch preparation

9. `prepare-classify-thinkers-batches.py` emits exactly 10 batch JSONLs at `data/classify-thinkers/batch-{00..09}.jsonl`. Distribution is round-robin by sorted thinker ID — i.e., sorted thinker `i` goes to batch `i % 10`, producing a slug-stratified slice per batch (not topically/canonically representative; just deterministic).
10. Every record in every batch validates against the §5 input schema.
11. Union of all batches' records is exactly the 506 thinker IDs from `apps/site/src/content/thinkers/*.md` — no thinker missed, no thinker duplicated. Verified by `cat data/classify-thinkers/batch-*.jsonl | jq -r .id | sort -u | wc -l` → 506.
12. Mention contexts are truncated (max 10 per thinker; each ~150-250 chars). Spot-check on Rajaji and Naoroji.

### 10.4 Bulk dispatch + apply

13. After 10 parallel subagents return, `data/classify-thinkers/output-{00..09}.json` exist — each is a JSON array of ~50 records.
14. Each output record validates against the §6 output schema.
15. Union of all output IDs covers all 506 input thinkers. Verified by `cat data/classify-thinkers/output-*.json | jq -r '.[].id' | sort -u | wc -l` → 506.
16. `apply-classify-thinkers.py --dry-run` reports which files would be modified and which axes would be written; no files touched.
17. `apply-classify-thinkers.py` (live) modifies thinker MDs per the §7 confidence rule. Spot-check 3 thinkers: one all-high, one mixed, one with low-confidence axis.
18. Applier is output-stable — re-running with same outputs AND no intervening curator edits produces zero file changes. (Per §7.2, a curator-cleared `needs_review: false` re-set to `true` on re-apply is INTENDED behaviour, not a violation.)
19. `data/classify-thinkers/reasoning-log.md` is created/updated; contains an entry per processed thinker.
20. `needs_review: true` is set on every record where at least one axis was medium-or-low.

### 10.5 Site build

21. After applier runs, `cd apps/site && pnpm build` exits clean. Page count stays at 1185.
22. `/thinkers` index now renders non-empty sections for `core`, `extended`, `referenced` (assuming the AI distributed across all three).
23. The "Awaiting classification" section is now smaller — contains only thinkers where canon_status was left at default `unclassified`.
24. Spot-check 4 representative thinker cards in the rendered HTML: Hayek in "Liberal canon" with vocations caption; Tata in "Extended liberal tradition"; Ambani in "Referenced thinkers"; a low-confidence entry in "Awaiting classification".

### 10.6 Audit / coverage

25. `audit-classify-thinkers-coverage.py` emits `data/classify-thinkers/coverage-report.md` containing per-canon_status, per-tradition, per-vocations breakdowns + per-confidence breakdown + list of `needs_review: true` thinker IDs.
26. The report makes "how many curator hours of review does this run produce?" answerable at a glance.

### 10.7 Regression

27. `/gu/primary-works/khoj-march-april-2005/` still shows the PUCL Gujarat saffron pill.
28. `/organisations/pucl-gujarat/` still renders.
29. `/thinkers/<some-thinker>/` detail page still renders.
30. Page count stays at 1185.

### 10.8 Stopping criteria

The bulk run is "done" when:
- §10.4 #15 (all 506 output records exist) passes
- §10.4 #18 (applier idempotent) passes
- §10.5 #21 (build clean) passes
- §10.6 #25 (coverage report generated) passes
- §10.7 regression checks pass

Curator review queue triage from §10.6 #25's `needs_review` list is the START of sub-project 3, not part of this spec's done-ness.

## 11. Future work (out of scope but worth noting)

- **Sub-project 3: Curator review tooling.** Whatever workflow makes reviewing the `needs_review: true` queue fast. CLI, dedicated page, or just a `/thinkers/?needs_review` filter. Deferred until we know what this pipeline's review-queue size and shape actually look like.
- **Thinker detail-page redesign.** Surface `canon_status`, `tradition`, `vocations`, works-count chips on `/thinkers/<slug>/`. Future spec.
- **Re-running classification after content edits.** Today's pipeline is one-shot. A future pipeline could detect "this thinker was edited since classification" and re-classify only the deltas. Out of scope.
- **Cross-axis statistics / facet UI.** A "by tradition" or "by vocation" filter row above the `/thinkers` grid. Deferred until the corpus is classified.
- **Reclassification of organisations** along similar axes. Organisations currently have `type` + `ideology`; aligning the two schemas (thinkers vs organisations) is a future spec.
- **Vocation enum extensions.** If pilot or bulk surfaces a vocation we missed (e.g., `architect`, `cinematographer`), add via spec amendment.
