// Sub-schemas filled by the LLM extraction pipeline.
//
// Two passes feed these shapes:
//   1. Metadata pass — produces TOC entries, contributor rosters, page-system
//      disambiguation, transcription anomalies, recommended authority additions.
//   2. Summarization pass — produces pull quotes, cross-thinker mentions,
//      per-essay summaries, summary completeness flags.
//
// Design provenance: ~/.gstack/projects/IndianLiberalsWebsite/siraj-main-design-20260517-133733.md
// (look for M-numbers / S-numbers below for the relevant design decisions).

import { z, reference } from 'astro:content';

// One of two page-numbering systems. v1.2 D8 disambiguation: a record can mix
// PDF page numbers and printed/book page numbers; downstream citation generators
// need to know which.
export const pageSystem = z.enum(['pdf', 'printed']);

// Transcription anomaly side-channel (v1.2 D9). When the verbatim contains an
// OCR garble or source typo that the translation/context silently corrects,
// surface it here so editorial reviewers can decide what to publish.
export const transcriptionAnomaly = z.object({
  observed: z.string(),         // what's literally on the page (preserved in verbatim)
  likely_intended: z.string(),  // what the model believes was meant
  note: z.string().optional(),  // 1-line reason ('OCR substitution; translation reflects intended reading')
});

// A verbatim quote pulled by the summarization pass. The model is asked to
// extract verbatim; pdftotext verification was rejected (noisier than the
// model on scanned corpora). See S2 in the design doc.
export const pullQuote = z.object({
  verbatim: z.string(),
  page: z.number().int(),
  page_system: pageSystem.optional(),   // v1.2 D8 — defaults to 'printed' when book page numbers are visible
  why_notable: z.enum(['framing', 'aphorism', 'data', 'counter_intuitive']),
  context: z.string().optional(),
  shareable: z.boolean().default(false),
  translation: z.string().optional(),    // English rendering for non-English verbatims
  transcription_anomaly: transcriptionAnomaly.optional(),  // v1.2 D9
});

// A named-person mention surfaced from body text (not the byline) and
// resolved against the authority file. Synthesis prunes mentions into the
// meaningful edge types (responds_to / builds_on / cites). See S4 in the doc.
export const crossThinkerMention = z.object({
  thinker_id: reference('thinkers').optional(),
  thinker_id_unresolved: z.string().optional(), // verbatim string if not in authority file
  context: z.string().optional(),
  page: z.number().int().optional(),
  page_system: pageSystem.optional(),   // v1.2 D8
});

// v1.2 D10 — recommended authority additions. Entities surfaced from extraction
// that didn't resolve against the authority file and that the model believes
// SHOULD be added. Editorial reviews these; pipeline does not silently fail.
export const recommendedAuthorityAddition = z.object({
  kind: z.enum(['thinker', 'publisher', 'organisation']),
  verbatim: z.string(),
  language: z.string().optional(),
  context: z.string().optional(),
  page: z.number().int().optional(),
  page_system: pageSystem.optional(),
});

// What the summarization pass actually saw (or didn't) of the work.
export const summaryCompleteness = z.object({
  based_on_pages: z.tuple([z.number().int(), z.number().int()]),
  covers_full_work: z.boolean(),
  missing_content_note: z.string().nullable().optional(),
});

// Single-author summary structured payload — sits alongside the prose
// `summary` field on primary-works.
export const summaryStructured = z.object({
  key_points: z.array(z.string()).default([]),
  themes_confirmed: z.array(z.string()).default([]),
  pull_quotes: z.array(pullQuote).default([]),
  cross_thinker_mentions: z.array(crossThinkerMention).default([]),
  summary_completeness: summaryCompleteness.optional(),
});

// One entry in the reconciled table of contents for a multi-author work.
// Verbatim TOC transcription + rendered-position reconciliation (see M5).
export const tocEntry = z.object({
  toc_index: z.number().int(),
  title: z.string(),
  byline_verbatim: z.string().optional(),
  thinker_id_proposed: z.string().optional(),
  page_start: z.number().int(),
  page_end: z.number().int().nullable().optional(),
  page_system: pageSystem.optional(),   // v1.2 D8
  complete_in_chunk: z.boolean().default(false),
  seen_through_page: z.number().int().optional(),
  virtual: z.boolean().default(false),  // v1.2 D13 — true for synthetic page-window entries on thick single-author no-TOC works
});

// Per-essay summarization payload for multi-author works. Joins to
// `contributors[].toc_index` for the static metadata roster.
export const essaySummarized = z.object({
  toc_index: z.number().int(),
  author_resolved: reference('thinkers').optional(),
  author_unresolved: z.string().optional(),
  summary: z.string(),
  partial_essay: z.boolean().default(false),  // v1.2 — true when sub-chunk failures meant the essay wasn't fully summarized
  summary_structured: z.object({
    key_points: z.array(z.string()).default([]),
    pull_quotes: z.array(pullQuote).default([]),
    cross_thinker_mentions: z.array(crossThinkerMention).default([]),
    complete: z.boolean(),
    seen_through_page: z.number().int().optional(),
  }),
});

// Optional `purpose` qualifier that sits next to `work_type` to capture
// finer granularity without polluting the primary enum. See "10 work_types"
// in the design doc.
export const purposeEnum = z.enum([
  // for occasional_paper
  'manifesto',
  'statement_of_principles',
  'report',
  'working_paper',
  'position_paper',
  'annual_report',
  // for edited_volume
  'anthology',
  'festschrift',
  'proceedings',
  'memorial_volume',
  'collected_works',
  // for book
  'treatise',
  'memoir',
  'biography',
  'textbook',
  // for speech
  'parliamentary',
  'convocation',
  'convention_address',
  'inaugural',
  'memorial_lecture',
]);
