# SP2 Handoff — Chunks 1-2 done; resume in new session

**Date:** 2026-05-23
**Branch:** `main` (28 commits ahead of `origin/main`; not pushed)
**Spec:** [docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md](docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md)
**Plan:** [docs/superpowers/plans/2026-05-23-thinkers-ai-bulk-classifier.md](docs/superpowers/plans/2026-05-23-thinkers-ai-bulk-classifier.md)

## What's done

| Chunk | SHA | Status |
|---|---|---|
| 1 — Schema + pilot CLI | `f2cabed` | ✅ Spec compliance approved, code quality approved |
| 2 — Batch prep + system prompt renderer | `038ef9d` + `5558492` (slug fix) | ✅ Both approved |

**Tests passing:** 10 schema + 7 pilot + 3 batch-prep = 20/20.

**Live corpus verification:**
- `prepare-classify-thinkers-batches.py` produces 10 batches × ~50 thinkers, 506 unique IDs.
- `render-system-classify-thinkers.py` produces a 12,386-char system prompt with all 8 anchor examples + the `international_influence` prohibition.
- All 8 anchor slugs intersect the on-disk thinkers dir (post-slug-fix at `5558492`).

## What's remaining (Chunks 3, 4, 5)

| Chunk | Description | Autonomy |
|---|---|---|
| 3 — Applier + audit | Ship `apply-classify-thinkers.py` (confidence-rule merger) + `audit-classify-thinkers-coverage.py` + tests. ~400 lines new code. | Full autonomy |
| 4 — Pilot execution | Bootstrap → curator hand-fills `pilot-ground-truth.json` → dispatch 1 pilot subagent → diff → iterate on FAIL up to 5x (human-gated) | Curator-fill requires Adnan's input (10-15 min); rest autonomous |
| 5 — Bulk execution | 10 parallel subagents over 506 thinkers → apply → audit → verify → commit + SESSION-SUMMARY | Full autonomy after pilot passes |

## Decisions already pinned (from the brainstorm + plan-review pass)

- **Confidence rule:** high → auto-write; medium → write + needs_review; low → leave axis at default + needs_review.
- **Reasoning paragraph:** always logged to `data/classify-thinkers/reasoning-log.md`, even when the field isn't written.
- **AI must NEVER emit `tradition: international_influence`** — schema rejects it; spec §6.1.
- **`pilot-ground-truth.json` and `coverage-report.md` are committed**; per-run pipeline artifacts (batches, outputs, reasoning log, diff report) stay untracked via `data/classify-thinkers/.gitignore` (created in Chunk 4).
- **Bulk dispatch:** 10 parallel Agent subagents via the harness's Agent tool, each given the system prompt + one batch JSONL + an output-path target.
- **Pilot threshold:** ≥80% per-axis agreement on all three axes (Jaccard ≥ 0.6 for vocations).
- **Iteration loop is HUMAN-GATED:** each iteration on FAIL surfaces a proposed prompt amendment to Adnan via AskUserQuestion before editing the rubric/anchor files.

## Anchor-slug fix (already landed at `5558492`)

The plan originally referenced `f-a-hayek` and `h-r-khanna`. Actual on-disk slugs are `friedrich-hayek` and `hans-raj-khanna`. The pipeline files (anchors JSON, ANCHOR_IDS in pilot script, rendered prompt) all use the correct on-disk slugs now. **Spec and plan reference docs still carry the old slugs** — they're read-only reference text; the pipeline is source-of-truth.

## Critical pre-flight reading for the new session

In order:
1. The spec (§§ 5-10): `docs/superpowers/specs/2026-05-23-thinkers-ai-bulk-classifier-design.md`.
2. The plan, Chunks 3-5: `docs/superpowers/plans/2026-05-23-thinkers-ai-bulk-classifier.md`.
3. This handoff file.
4. The existing pipeline scripts under `scripts/synthesis/`.

## Pilot bootstrap status

- `data/classify-thinkers/` is currently EMPTY (cleaned up after Chunk 2 verification).
- Running `python3 scripts/synthesis/pilot-classify-thinkers.py --bootstrap` will emit `pilot-ground-truth.json` with 8 anchors + 22 `PLACEHOLDER-*` slugs.
- The 22 PLACEHOLDER slugs do NOT resolve to on-disk thinkers; the new session should replace them with real slugs from `apps/site/src/content/thinkers/` AND propose first-guess classifications for Adnan to review.

## Reviewer-flagged deferred items (not blocking; address opportunistically)

- (Chunk 1) Anchor-ID source-of-truth duplication between `pilot-classify-thinkers.py:ANCHOR_IDS` and `classify-thinkers-anchors.json`. Cross-sync comment exists in both; consider importing from the JSON instead.
- (Chunk 2) Pilot-mode silent-skip on missing on-disk IDs. Could add a `WARN` stderr line in `prepare-classify-thinkers-batches.py`.
- (Chunk 2) Inline `subject:` regex matches loosely. Tightening to require trailing space/tab is a 1-line code change.
- Spec + plan still reference the old slugs `f-a-hayek` and `h-r-khanna`. Could be aligned in a post-Chunk-5 hygiene commit.

None of these block Chunks 3-5.
