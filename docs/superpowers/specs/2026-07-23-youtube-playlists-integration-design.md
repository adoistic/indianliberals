# YouTube playlists → Interviews + new /lectures/ page

**Date:** 2026-07-23
**Author:** Adnan
**Status:** approved-to-implement (IA decision confirmed; transcription + work_type recommended defaults)

## Goal

Integrate four CCS YouTube playlists into the site's video archive, downloading
and transcribing every video that is not already on the site. No duplication.

Playlists:

| Key | Playlist ID | Destination |
|---|---|---|
| interviews | `PLysF1qZYkiGHeL136ATCo7AN2beAQaJav` | /interviews/ (figures / talks / conversations) |
| collections | `PLysF1qZYkiGFX04FNPTvzZOcZfJnc-a0q` | /interviews/ Collections shelves |
| shenoy-memorial | `PLysF1qZYkiGFRGgvHhZuZYhrzkP2fbq-6` | /lectures/ (B.R. Shenoy Memorial Lecture) |
| il-annual-lecture | `PLysF1qZYkiGGk7nGkXYKe37_7TBaD34jK` | /lectures/ (Indian Liberals Annual Lecture) |

## Scope (deduped 2026-07-23)

- 119 videos across the four playlists.
- 68 unique video IDs already on the site (matched by `youtube_url`).
- After dedup against the site **and** across playlists: **44 unique new videos.**
- A handful of Collections entries are `NA` (private/deleted) → skipped.

Per-playlist NEW: interviews 23, collections 14, shenoy-memorial 7,
il-annual-lecture 4 (with 4 videos shared interviews↔collections and the
Gurcharan Das lecture shared interviews↔il-annual, resolved to 44 unique).

The authoritative id list lives in the scratchpad `yt/union.new.ids` during the
run and is re-derivable at any time from the playlists.

## Content model

Every video is a `primary-works` markdown entry (unchanged from today):

- `youtube_url`, timestamped transcript body with a `Duration: <sec>s` header
  (the format `lib/interviews.ts` already parses for thumbnails + duration).
- LLM metadata to match the existing bar: `summary`, `key_points`, `themes`,
  `thinker_mentions`, `related_thinkers`, `description`.

### New `work_type: "lecture"`

Added to the `work_type` enum in `content.config.ts`. Applied to:

1. The 11 formal annual-lecture videos (Shenoy Memorial + IL Annual).
2. **Migration:** the 7 existing historic lectures currently mis-typed as
   `interview` and hardcoded in `interviews.ts` `LECTURE_IDS`
   (union-budget-1992 Palkhivala, the four Sudha Shenoy lectures,
   the-case-against-neo-protectionism, indian-liberal-tradition-gp-manish,
   an-auxiliary-for-historians-...).

This replaces the hardcoded `LECTURE_IDS` set with a real type, so the two
pages separate by query, not by maintained ID lists.

## Pages

- **`/lectures/` (new)** — reuses the shelf/card UI. Shelves: *B.R. Shenoy
  Memorial Lecture* (by year, desc), *Indian Liberals Annual Lecture* (by
  edition), *Historic lectures & addresses* (the migrated 7). Selects
  `work_type === "lecture"`.
- **`/interviews/` (refactored)** — selects `work_type === "interview"` (lectures
  drop out automatically). `LECTURE_IDS` deleted. New interview/collection
  videos slot into the existing figure / collection / explainer / talk grouping.
- Shared video helpers (`videoIdFor`, `thumbFor`, `durationFor`, `workHref`)
  extract to `lib/video.ts`; `interviews.ts` and the new `lectures.ts` both import.
- Nav gains a "Lectures" entry; the two pages cross-link.

## Ingestion pipeline (idempotent, ledger-backed)

```
union new video IDs (44)
  → yt-dlp: metadata JSON (title, description, upload_date→year, duration)
            + bestaudio → 16 kHz mono mp3  (data/audio/<id>.mp3)
  → Whisper large-v3 (GPU)  → timestamped transcript  (data/transcripts/<id>.raw.txt)
       primary: runpod GPU MCP; captions fallback only if a video blocks whisper
  → claude -p correction pass (authority list) → proper-noun fixes
  → claude -p metadata pass (reuse scripts/llm-extract prompts)
       → summary / key_points / themes / thinker_mentions
  → editorial routing (playlist + title heuristics, human-reviewed 44-row map)
  → write apps/site/src/content/primary-works/<slug>.md
       work_type: interview | lecture ; group assigned
```

A JSON ledger (`data/interview-transcripts/ledger.json`) tracks per-video
status (`audio | transcribed | corrected | metadata | written`) so re-runs skip
completed stages — the Freedom-First ingestion pattern.

### Transcription engine choice

No STT API keys are provisioned (only Claude via `ANTHROPIC_BASE_URL`).
YouTube auto-captions are unreliable for this corpus: some videos have none
(e.g. the 2026 Arvind Subramanian lecture), and auto-captions lack punctuation
and mangle the proper nouns these transcripts exist to make searchable and to
feed thinker-mention NER. → **Whisper large-v3 on runpod GPU** for
archive-quality, timestamped, reusable transcripts. Consistent with the prior
Phase B-2 decision to favour quality + reusable artifacts over the cheapest
option.

## Verify & ship

- `astro check` clean; `npm run build` succeeds (page count grows by the new
  entries + the /lectures/ shelves).
- Browser-preview spot-check of `/lectures/` and `/interviews/`.
- Regenerate sitemap / legacy-redirect artifacts if the generators require it.
- Commit in logical batches (schema+pages, then content batches); push per the
  established cadence.

## Non-goals

- Re-transcribing the existing 72 interviews.
- Full-PDF NER (separate Phase 2 workstream).
- Non-English metadata beyond what the existing pipeline handles (the Hindi
  "Public Choice" primer gets a transcript + basic metadata; deep NER deferred).
