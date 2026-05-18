# Phase B scope confirmation + Phase B-2 audio pipeline plan

**Date written:** 2026-05-18
**For:** the session implementing Phase B in-prose NER, and the future session that picks up Phase B-2
**Parent doc:** [`2026-05-18-phase-b-ner-handoff.md`](./2026-05-18-phase-b-ner-handoff.md)

> **How to read this file:** the parent doc is the durable Phase B design. This
> file is the supplementary spec produced by the 2026-05-18 brainstorming
> pass that picked up the handoff. It records the deltas to the parent doc's
> scope, the locked smoke-batch composition, the prompt-anchoring strategy
> for the new system prompt, and the deferred Phase B-2 audio pipeline.
> When the parent doc and this file disagree, this file wins for sections
> covered here.

---

## 1. Locked scope for Phase B core

The parent doc lists four Tier-A collections in scope: musings, opinions,
interviews, theprint-mirror, plus a primary-works re-pass. The brainstorming
pass dropped interviews.

**In scope for Phase B core:**

| Collection | Source for NER | Notes |
|---|---|---|
| musings | full body markdown | English `language: "en"` only |
| opinions | full body markdown | English only |
| theprint-mirror | full body markdown | English only |
| primary-works | the `summary` prose in the entry body | NER reads the AI-generated summary, not the original PDF — see §1.1 |

**Out of scope for Phase B core (deferred):**

| Collection | Deferred to | Reason |
|---|---|---|
| interviews | Phase B-2 (see §5) | 72 of 72 entries are 21-22-line WP-import stubs with `transcript_status: "none"`; bodies are 1-2 sentences. Real content is in the linked YouTube videos. NER over the stub bodies is wasted call budget. |
| primary-works full PDF | Phase 2 | The v1.5 extraction already captured `cross_thinker_mentions` from the full PDFs. Phase B over the summary prose adds evidence quotes drawn from the summary. A future Phase 2 pass should re-run NER over the full PDF text to extract verbatim evidence quotes from the original work, not just the summary. |
| non-English entries (Marathi, Gujarati, Hindi, Bengali) | a future language-specific pass | The authority list is English-name-keyed. Honoured already by the parent doc's `.data.language === "en"` filter. |

### 1.1 Primary-works clarification

Primary-works MD bodies hold the AI-generated `summary` + `key_points`, not
the original work's prose. NER over a primary-work therefore surfaces
mentions from the summary text (e.g., "Germany and Japan are cited..." in
the Godrej entry) with evidence quotes pulled from the summary prose.

Why this is still valuable now: the resulting `thinker_mentions[]` entries
carry verifiable evidence (the quote is a substring of the rendered body),
which the existing `cross_thinker_mentions` lacked. Bio pages get inline
quotes under "Mentioned in" sections from this immediately.

Why Phase 2 should re-do it: the original PDF text contains many more
mentions than the summary, and the verbatim quotes from the original work
are more historically valuable than quotes from an AI-generated summary.
A Phase 2 re-pass should run the same prompt against the full extracted
text (when paragraph-stable IDs land) and replace `thinker_mentions[]`
atomically per primary-work.

---

## 2. Updated scale estimate

Recounted at brainstorming time (2026-05-18 08:24 IST):

| Collection | English entries | In Phase B core |
|---|---|---|
| musings | 224 | yes |
| opinions | 61 | yes |
| theprint-mirror | 48 | yes |
| primary-works | 287 (and growing — runner still extracting) | yes |
| interviews | 72 | no (Phase B-2) |
| **Total in core** | **~620** | |

Per-batch budget unchanged: 8 entries per `claude -p` call, ~80 total calls.

---

## 3. Smoke batch (locked, 7 entries)

The parent doc named 8 entries; this brainstorming pass dropped the
interview slot. The remaining 7 cover every code path Phase B core needs
to validate before scaling.

| # | Entry | What it exercises |
|---|---|---|
| 1 | `opinions/anandibai-joshee` | `subject` role — full profile, 2-4 `key_passages` expected |
| 2 | `opinions/homi-modys-liberalism-pro-business-to-pro-market` | `subject` role — consistency check against #1 |
| 3 | `opinions/gg-agarkar-revisiting-a-misunderstood-legacy` | `subject` role — edge cases (older era, less internet-visible figure) |
| 4 | `musings/economic-reforms-in-india` | `mention`-rich body — Shroff, Nehru, Gladwell, Bombay Plan |
| 5 | `musings/1991-liberal-reforms-why-no-one-celebrated-them-ashok-desai-1995` | known `author` + body mentions — co-validates Phase A author detection alongside Phase B mention detection |
| 6 | `theprint-mirror/ad-shroff-socialism-free-enterprise-lessons` | ThePrint piece — publisher-formatted prose, mention-rich |
| 7 | `primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980` | primary-work over summary — entry already has `cross_thinker_mentions`; validates the evidence-quote layer overlays cleanly on existing structured mentions |

After running the smoke batch through `resolve-ner.py`, read the resulting
JSON by hand. Show Adnan. Iterate the prompt until all 7 produce
sensible, verbatim-correct mentions before running the full batch.

---

## 4. Worked-example anchoring in `system-ner.txt`

The parent doc says to mirror `system-resolver.txt` in shape and tone.
That prompt uses **synthetic, short examples**. Phase B introduces a new
constraint Phase A didn't have: every `evidence[].quote` and
`key_passages[].quote` must be a verbatim substring of the body. The
validator in `apply-ner.py` will drop quotes that fail the substring
check, so weak prompt anchoring directly translates to dropped mentions.

**Strategy: anchor with real verbatim excerpts** — for each of the three
roles (`subject`, `mention`, `author`+`mention`), embed in the prompt:

1. A real ~2-line passage copied verbatim from an actual corpus entry
2. The gold-standard JSON output for that role, with quotes that are
   strict substrings of the passage above

Concrete picks (use the same entries as the smoke batch where possible —
avoids drift between examples and validation):

- **`subject` example**: passage from `opinions/anandibai-joshee` (the
  intro paragraph). Gold output shows 2 `key_passages` with `what_it_shows`
  framing.
- **`mention` example**: passage from `musings/economic-reforms-in-india`
  — the "I am deeply honoured to have been invited to deliver this A. D.
  Shroff Memorial Lecture" paragraph. Gold output shows 1 `mention`
  record for Shroff with one evidence quote that is an exact substring.
- **`author`+`mention` example**: passage from `musings/1991-liberal-reforms-…-ashok-desai-1995`. Show that the byline-author (Desai) is **omitted** from `thinker_mentions[]` (it lives in `author` from Phase A), and only the in-prose mentions are emitted.

Token budget: parent doc estimates `system-resolver.txt` at ~3K tokens.
Adding three real-excerpt examples adds ~1.5K tokens. Total `system-ner.txt`
≈ 4.5K tokens, well within budget.

Also include in the prompt body, immediately above the examples:

> "Every quote in `evidence[].quote` and `key_passages[].quote` must be a
> verbatim substring of the entry's body markdown. Match on the visible
> text — strip markdown emphasis (`*`, `_`, backticks, `>`) and normalise
> smart quotes to straight quotes mentally before deciding whether a
> candidate quote substring-matches. Apply-step validation does the same
> normalisation. Quotes that don't substring-match are dropped silently."

---

## 5. Phase B-2 — Interview audio pipeline (deferred plan)

This section captures the architecture for the next session that picks up
interview processing. **Do not implement during Phase B core.** Phase B-2
runs after Phase B core lands and is operating cleanly in production.

### 5.1 Goal

Turn the 72 YouTube interview videos into clean transcripts → run them
through the same Phase B mention-extraction pipeline as everything else.
End state: interviews join the unified "How {Thinker} is discussed in this
archive" surface with linked thinkers, evidence quotes, and reasoning.

### 5.2 Coverage

- 72 interviews total, all `language: "en"`, all English titles
- 70 of 72 have a `youtube_url` field; the remaining 2 need manual review
- All 72 currently carry `transcript_status: "none"`; this field will
  flip to `"complete"` (or `"partial"` on errors) as Phase B-2 lands
- ~50 of 72 are named-subject interviews; ~20 are thematic

### 5.3 Pipeline

```
youtube_url
  → yt-dlp (install: `brew install yt-dlp`)
  → ffmpeg: mono, 16 kHz, mp3 32 kbps  (keeps files small; Gemini-or-
                                          Deepgram down-samples anyway)
  → Deepgram Nova-3 STT  (speaker diarization on for interview format;
                          smart-formatting on; punctuation on)
  → raw transcript (`data/transcripts/<slug>.raw.txt`)
  → `claude -p` correction pass  (prompt: see §5.5)
  → cleaned transcript written into the interview MD body
  → standard Phase B `resolve-ner.py` → `apply-ner.py` pipeline runs
    over the interview, identical to musings/opinions
```

### 5.4 Why Deepgram + Claude over multimodal audio LLM

Researched on OpenRouter 2026-05-18:

| Option | Estimated cost for 72 interviews | Reusable artifact? |
|---|---|---|
| Gemini 2.5 Flash audio-in, summary-out | ~$1.70 | no — only the summary survives |
| Deepgram Nova-3 + `claude -p` correction + standard NER | **~$10** | **yes — clean reusable transcripts** |
| Whisper-1 (OpenRouter) + correction + NER | ~$30 | yes |
| GPT-Audio direct | ~$150 | no |

Deepgram wins on:
1. **Clean transcripts as a byproduct** — searchable, citable, future-proof
2. **Speaker diarization** — interview format ("Q:" / "A:") for free
3. **Cost** — ~$0.004/min vs Gemini's reasoning-on-audio rate
4. **Decoupling** — STT failure modes (mishearings, name spellings) are
   isolated to one stage; the correction pass is purely text-over-text
   and reuses the same Claude tooling as the rest of the project

The Claude correction pass is what makes the architecture work: Deepgram
gets ~95% of words right but mangles proper nouns ("Palki-vala" not
"Palkhivala", "Mas-ani" not "Masani"). A `claude -p` pass given the
authority list and the raw transcript fixes these in context.

### 5.5 Correction-pass prompt (`scripts/synthesis/prompts/system-transcript-correction.txt`)

Sketch — to be detailed in the Phase B-2 implementation plan:

- Role: "you are correcting a Deepgram transcript of an English-language
  interview from the Indian Liberals archive"
- Inputs in user message:
  - The full authority list (slug :: canonical) — same listing the resolver and NER prompts use
  - The raw transcript with diarization tags (e.g., `[Speaker 0]`, `[Speaker 1]`)
  - The interview's frontmatter (subject_name, themes, youtube_url) for context
- Output: cleaned transcript with proper-noun corrections applied, light grammar smoothing, paragraph breaks, and `[Q:]` / `[A:]` speaker labels if the interview is two-speaker (skip labels for monologues / IL Explainer episodes)
- Forbid: changing factual content, hallucinating names not in the authority list, inventing context, summarising

### 5.6 Storage

```
data/transcripts/
├── <slug>.raw.json     (Deepgram response — diarization, timestamps, confidence)
├── <slug>.raw.txt      (flat text projection from .raw.json)
└── <slug>.cleaned.txt  (claude -p correction output)

apps/site/src/content/interviews/<slug>.md
  → body becomes the cleaned transcript
  → transcript_status: "complete"
  → ai.drafted_by: "deepgram-nova-3+claude-sonnet-4.x"
```

### 5.7 Acceptance for Phase B-2

- 70+ of 72 interviews have transcripts in `data/transcripts/`
- Each interview MD has a non-trivial body (≥10 paragraphs typical)
- Standard Phase B NER pipeline runs over interview bodies and the same
  ≥80% mention-coverage criterion holds
- Spot-check 10 transcript samples by listening to a minute of source
  audio and reading the corresponding cleaned transcript — proper-noun
  accuracy ≥95% for thinker names in the authority list

### 5.8 Open questions to resolve at Phase B-2 start

- **Deepgram model tier**: Nova-3 (current top, $0.0043/min) vs Nova-2-general ($0.0036/min). Nova-3 if proper-noun accuracy matters; Nova-2 is fine because the correction pass cleans them anyway. Probably Nova-2.
- **Diarization on/off**: on for interview / Q&A format; off for monologue (IL Explainer single-speaker episodes). Decide per-entry via `subject_name` heuristic or just leave on for all.
- **Audio caching**: keep the downloaded mp3s on disk under `data/audio/` for re-runs, or stream through the pipeline and discard. Audio files are small (~14 MB/h at 32 kbps mp3) so caching is fine; ~5 GB total for 36h of interviews. Decide based on disk pressure at the time.

---

## 6. Updated acceptance criteria for Phase B core

The parent doc's acceptance criteria spoke of "Tier-A entries". With
interviews deferred, the denominator changes:

- ≥80% of English entries in musings + opinions + theprint-mirror have at least one `thinker_mentions[]` record. (Primary-works are evaluated separately — see below.)
- ≥60% of primary-works (where the summary prose runs ≥1 paragraph) have at least one `thinker_mentions[]` record. (Lower bar because summary prose is shorter and less mention-dense than original musings.)
- Every "touchstone" thinker — A.D. Shroff, Nehru, Gandhi, Hayek, Smith, Marx, Palkhivala, Masani, Shenoy, Bhagwati — has visible mentions across multiple works on their bio page.
- The "How {Thinker} is discussed in this archive" section renders sensible 2-3-paragraph synthesis for at least 30 thinkers.
- `npm run build` clean. `astro check` error count delta = 0.
- Spot-check 10 random evidence quotes: every one substring-matches the body under the parent doc's normalisation rules.

Interview-coverage criteria move to §5.7 and are evaluated only after
Phase B-2 lands.

---

## 7. Updated build order for Phase B core

The parent doc's step list (steps 1-15) is adjusted as follows:

```
1. scripts/synthesis/prompts/system-ner.txt
   - write prompt with §4 strategy (real verbatim worked examples)
   - iterate with Adnan on the 7 smoke-batch outputs

2. apps/site/src/schemas/mentions.ts                 (NEW)
3. apps/site/src/schemas/index.ts                    (re-export)
4. apps/site/src/content.config.ts
   - add thinker_mentions to musings, opinions, theprint-mirror,
     primary-works, periodicals (5 collections — NOT interviews)
   - add related_thinkers to periodicals too (parent doc said it had
     one; verified missing; future-proof)
   - do NOT modify the interviews schema (Phase B-2 will)

5. Run npx --offline astro check — error count unchanged from baseline

6. scripts/synthesis/prepare-ner-batches.py
   - read English entries from the 4 in-scope collections
   - emit data/synthesis/ner-input.jsonl

7. scripts/synthesis/resolve-ner.py                  (mirror of resolve-unlinked.py)

8. Run smoke batch of 7 entries; iterate prompt until all 7 produce
   sensible, verbatim-correct mentions

9. scripts/synthesis/apply-ner.py                    (read mentions.jsonl, validate, mutate frontmatter)

10. Run full batch via resolve-ner.py

11. Run apply-ner.py

12. Update apps/site/src/pages/thinkers/[slug].astro per parent doc § Bio page changes

13. npm run build → 1,225+ pages, no new errors

14. python3 scripts/synthesis/audit-ner-coverage.py (per §6)

15. Commit + push each step as a separate commit
```

After Phase B core lands, Phase B-2 (interviews) is a separate work
stream — its own spec + plan + implementation cycle. The two are fully
decoupled.

---

## 8. Decisions added in this brainstorming pass (don't relitigate)

- **Interviews are out of Phase B core**; they live in Phase B-2 with their own pipeline.
- **Primary-works NER reads summary prose now**; full-PDF re-NER is a Phase 2 task.
- **Smoke batch is 7 entries** as listed in §3.
- **System prompt uses real verbatim worked examples**, not synthetic ones, to anchor the substring rule.
- **Phase B-2 architecture is Deepgram + Claude correction + reuse Phase B NER pipeline**. Not Gemini-audio direct.
- **All other locked-in decisions from the parent doc still hold** (pure LLM no regex; evidence + reasoning public not gated; subject role gets 2-4 key passages; stub thinkers stay; ThePrint mirror is AI-only).

---

**End of supplementary spec.** Implementation plan to follow via the
`writing-plans` skill.
