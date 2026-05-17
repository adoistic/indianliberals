// Astro content collections for the eight Indian Liberals content kinds.
// This file is the runtime contract that SCHEMA.md is the prose-form of.
//
// Tier A = clean content (musings, opinions, interviews, thinker-profiles,
// organisations, ThePrint mirror). Full markdown body, full-text indexed
// in Pagefind, paragraph-citable.
//
// Tier B = primary works and periodicals. Metadata + AI summary + key
// points + PDF link only. Body-text reconstruction deferred to a future
// engagement.

import { defineCollection, reference, z } from 'astro:content';
import { glob } from 'astro/loaders';

// ─── shared sub-schemas ────────────────────────────────────────────────

const aiProvenance = z
  .object({
    extracted_at: z.string().datetime().optional(),
    model: z.string().optional(),
    prompt_version: z.string().optional(),
  })
  .optional();

// Multilingual support. Every content entry knows its own language,
// optionally points to the original-language version (translation_of),
// and exposes a map of all other-language versions (translations).
// BaseLayout reads these and emits bidirectional hreflang alternates
// per Google's multilingual SEO guidelines.
const LANG_CODES = ['en', 'hi', 'gu', 'mr', 'bn'] as const;

const i18nFields = {
  language: z.enum(LANG_CODES).default('en'),
  // For non-English content: ID of the original-language entry (if known)
  translation_of: z.string().optional(),
  // Map of <lang-code, entry-id> for every other-language version
  // of the same intellectual content. Used to emit hreflang alternates.
  // Must be kept consistent on BOTH sides of a translation pair.
  translations: z.record(z.enum(LANG_CODES), z.string()).optional(),
  // Translation provenance — controls whether the page is indexed.
  // "original" = primary author wrote it in this language
  // "human_translation" = trusted human translator, OK to index
  // "ai_translation" = AI-generated, set noindex until reviewed
  // "needs_translation" = placeholder, do not show on site
  translation_status: z
    .enum(['original', 'human_translation', 'ai_translation', 'needs_translation'])
    .default('original'),
};

const rightsSchema = z
  .object({
    status: z.enum([
      'public_domain',
      'fair_use_educational',
      'permission_granted',
      'takedown_on_request',
      'unknown',
    ]),
    pd_year: z.number().int().optional(),
    editorial_review_flag: z.boolean().default(false),
    notes: z.string().optional(),
  })
  .optional();

const multilingualTitle = z.object({
  main: z.string(),
  subtitle: z.string().optional(),
  original_script: z.string().optional(),
  translit: z.string().optional(),
  translation: z.string().optional(),
});

const thinkerName = z.object({
  canonical: z.string(),
  full: z.string().optional(),
  sort: z.string(),
  also_known_as: z.array(z.string()).default([]),
  honorifics: z.array(z.string()).default([]),
});

// ─── Shared sub-schemas for LLM extraction pipeline ────────────────────
// See design doc: ~/.gstack/projects/IndianLiberalsWebsite/siraj-main-design-20260517-133733.md
// These shapes are filled by the extraction (metadata + summary) and
// synthesis (themes/genealogies/reading-guides) passes.

// Per-field confidence flag — applied to high-stakes fields (title, author,
// year, publisher, language) by the metadata pass. See M3 in the design doc.
const confidenceFlag = z.enum(['high', 'medium', 'low']);

// One of two page-numbering systems. Required disambiguation in v1.2 (D8):
// a record can mix PDF page numbers and printed/book page numbers; downstream
// citation generators need to know which.
const pageSystem = z.enum(['pdf', 'printed']);

// Transcription anomaly side-channel (v1.2 D9). When the verbatim contains an
// OCR garble or source typo that the translation/context silently corrects,
// surface it here so editorial reviewers can decide what to publish.
const transcriptionAnomaly = z.object({
  observed: z.string(),         // what's literally on the page (preserved in verbatim)
  likely_intended: z.string(),  // what the model believes was meant
  note: z.string().optional(),  // 1-line reason ('OCR substitution; translation reflects intended reading')
});

// A verbatim quote pulled by the summarization pass. The model is asked to
// extract verbatim; pdftotext verification was rejected (noisier than the
// model on scanned corpora). See S2 in the design doc.
const pullQuote = z.object({
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
const crossThinkerMention = z.object({
  thinker_id: reference('thinkers').optional(),
  thinker_id_unresolved: z.string().optional(), // verbatim string if not in authority file
  context: z.string().optional(),
  page: z.number().int().optional(),
  page_system: pageSystem.optional(),   // v1.2 D8
});

// v1.2 D10 — recommended authority additions. Entities surfaced from extraction
// that didn't resolve against the authority file and that the model believes
// SHOULD be added. Editorial reviews these; pipeline does not silently fail.
const recommendedAuthorityAddition = z.object({
  kind: z.enum(['thinker', 'publisher', 'organisation']),
  verbatim: z.string(),
  language: z.string().optional(),
  context: z.string().optional(),
  page: z.number().int().optional(),
  page_system: pageSystem.optional(),
});

// What the summarization pass actually saw (or didn't) of the work.
const summaryCompleteness = z.object({
  based_on_pages: z.tuple([z.number().int(), z.number().int()]),
  covers_full_work: z.boolean(),
  missing_content_note: z.string().nullable().optional(),
});

// Single-author summary structured payload — sits alongside the prose
// `summary` field on primary-works.
const summaryStructured = z.object({
  key_points: z.array(z.string()).default([]),
  themes_confirmed: z.array(z.string()).default([]),
  pull_quotes: z.array(pullQuote).default([]),
  cross_thinker_mentions: z.array(crossThinkerMention).default([]),
  summary_completeness: summaryCompleteness.optional(),
});

// One entry in the reconciled table of contents for a multi-author work.
// Verbatim TOC transcription + rendered-position reconciliation (see M5).
const tocEntry = z.object({
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
const essaySummarized = z.object({
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
const purposeEnum = z.enum([
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

// Per-work reading guide, populated by the synthesis layer's per-work
// enrichment pass (Phase 4 Pass 7). Surfaces "how to approach" + audience
// signals on each primary-works page.
const readingGuide = z.object({
  how_to_approach: z.string().optional(),
  difficulty: z.enum(['introductory', 'intermediate', 'advanced']).optional(),
  estimated_minutes: z.number().int().optional(),
  prerequisites: z.array(z.string()).default([]),
  why_this_matters: z.string().optional(),
  best_read_alongside: z
    .array(z.object({ work_id: z.string(), relationship: z.string() }))
    .default([]),
});

// Per-thinker intellectual arc, populated by the synthesis layer's
// per-thinker genealogy pass (Phase 4 Pass 3).
const intellectualArc = z.object({
  summary: z.string(),
  phases: z
    .array(z.object({ label: z.string(), key_works: z.array(z.string()).default([]) }))
    .default([]),
  influences: z
    .object({
      on_them: z.array(reference('thinkers')).default([]),
      from_them: z.array(reference('thinkers')).default([]),
    })
    .optional(),
  core_questions: z.array(z.string()).default([]),
});

// ─── Tier A: thinker profiles ──────────────────────────────────────────

const thinkers = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/thinkers' }),
  schema: z.object({
    id: z.string(),
    name: thinkerName,
    birth_year: z.number().int().nullable().optional(),
    death_year: z.number().int().nullable().optional(),
    nationality: z.string().default('india'),
    tradition: z.enum([
      'classical_liberal',
      'reformer',
      'nationalist_liberal',
      'social_reformer',
      'contemporary_liberal',
      'international_influence',
    ]),
    themes: z.array(z.string()).default([]),
    affiliations: z.array(z.string()).default([]),
    portrait: z
      .object({
        photo: z.string().optional(),
        caricature: z.string().optional(),
        ring_portrait: z.string().optional(),
      })
      .optional(),
    bio_source: z
      .enum(['canonical', 'feature_article', 'ai_drafted', 'imported'])
      .default('canonical'),
    // Synthesis-populated. Empty until Phase 4 Pass 3 runs over the
    // extracted corpus.
    intellectual_arc: intellectualArc.optional(),
    ...i18nFields,
    needs_review: z.boolean().default(false),
    ai: aiProvenance,
    // For Sveltia editorial workflow
    draft: z.boolean().default(false),
  }),
});

// ─── Tier A: organisations ─────────────────────────────────────────────

const organisations = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/organisations' }),
  schema: z.object({
    id: z.string(),
    name: z.object({
      canonical: z.string(),
      full: z.string().optional(),
      sort: z.string(),
      also_known_as: z.array(z.string()).default([]),
    }),
    founded_year: z.number().int().nullable().optional(),
    dissolved_year: z.number().int().nullable().optional(),
    type: z.enum([
      'political_party',
      'think_tank',
      'publisher_org',
      'reform_society',
      'professional_body',
      'academic',
      'international_network',
    ]),
    ideology: z.array(z.string()).default([]),
    ...i18nFields,
    needs_review: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// ─── Tier A: musings (excerpts from primary works) ─────────────────────

const musings = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/musings' }),
  schema: z.object({
    id: z.string(),
    title: z.string(),
    pubDate: z.coerce.date(),
    excerpt_of: z.string().optional(), // primary-works ID
    author: reference('thinkers').optional(),
    themes: z.array(z.string()).default([]),
    ...i18nFields,
    ai: aiProvenance,
    needs_review: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// ─── Tier A: opinion pieces ────────────────────────────────────────────

const opinions = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/opinions' }),
  schema: z.object({
    id: z.string(),
    title: z.string(),
    pubDate: z.coerce.date(),
    author_name: z.string(),
    author: reference('thinkers').optional(),
    themes: z.array(z.string()).default([]),
    related_works: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    ...i18nFields,
    ai: aiProvenance,
    needs_review: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// ─── Tier A: interviews ────────────────────────────────────────────────

const interviews = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/interviews' }),
  schema: z.object({
    id: z.string(),
    title: z.string(),
    pubDate: z.coerce.date(),
    subject: reference('thinkers').optional(),
    subject_name: z.string(),
    interviewer: z.string().optional(),
    youtube_url: z.string().url().optional(),
    transcript_status: z.enum(['none', 'partial', 'complete']).default('none'),
    themes: z.array(z.string()).default([]),
    ...i18nFields,
    ai: aiProvenance,
    needs_review: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// ─── Tier B: primary works (PDFs) ──────────────────────────────────────

const primaryWorks = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/primary-works' }),
  schema: z.object({
    id: z.string(),
    title: multilingualTitle,
    work_type: z.enum([
      'book',
      'pamphlet',
      'speech',
      'essay',
      'edited_volume',
      'occasional_paper',
      'letter',
      'correspondence', // NEW — collected letters between named individuals
      'periodical_issue',
      'reference', // NEW — bibliography / dictionary / catalogue / index
    ]),
    // Optional sub-type qualifier. See `purposeEnum` definition above.
    purpose: purposeEnum.optional(),
    authors: z.array(reference('thinkers')).default([]),
    editors: z.array(reference('thinkers')).default([]),
    // Static metadata roster (who's in the book + their role), produced by
    // the metadata pass. Joins to `essays_summarized[]` via `toc_index`.
    contributors: z
      .array(
        z.object({
          thinker: reference('thinkers').optional(),
          thinker_unresolved: z.string().optional(),
          role: z.string(), // "author" | "editor" | "translator" | "foreword" | "introduction" | other
          toc_index: z.number().int().optional(),
        }),
      )
      .default([]),
    publication: z.object({
      publisher_id: z.string().optional(),
      publisher_name: z.string().optional(),
      // NEW — issuing organisation when distinct from publisher. E.g., the
      // Swatantra Party "Statement of Principles" was issued by the party
      // (issuer) and printed elsewhere (publisher). Often equal to publisher.
      issuer_id: z.string().optional(),
      place: z.string().optional(),
      year: z.number().int().nullable().optional(),
      edition: z.string().optional(),
      series: z.string().optional(),
      language: z.string().default('en'),
    }),
    physical: z
      .object({
        page_count: z.number().int().optional(),  // legacy field — kept for backward compat
        page_count_visible: z.number().int().optional(),  // legacy v1.0 field — superseded by pages_rendered/total
        pages_rendered: z.number().int().optional(),  // v1.2 D1 — pages the model actually saw across all chunks
        pages_total: z.number().int().optional(),  // v1.2 D1 — total page count of the source PDF
        pages_total_source: z.enum(['pypdfium2', 'toc_max', 'unknown']).optional(),  // v1.2 D1 provenance
        format: z.string().optional(),
      })
      .optional(),
    identifiers: z
      .object({
        isbn: z.string().optional(),
        oclc: z.string().optional(),
        lccn: z.string().optional(),
      })
      .optional(),
    provenance: z.object({
      source: z.enum(['ccs_archive', 'private_scan', 'source_library', 'unknown']),
      scan_quality: z.enum(['good', 'fair', 'poor', 'unknown']).default('unknown'),
      notes: z.string().optional(),
    }),
    rights: rightsSchema,
    themes: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    related_works: z.array(z.string()).default([]),
    // Reconciled TOC for multi-author works. Populated by the metadata pass
    // (transcribed verbatim from the TOC page + cross-referenced against
    // rendered-page positions). Empty for single-author works. Drives the
    // continuation loop in the summarization pass.
    toc: z
      .object({
        extracted_from_pages: z.array(z.number().int()).optional(),
        entries: z.array(tocEntry).default([]),
        entries_not_yet_rendered: z.array(tocEntry).default([]),
      })
      .optional(),
    // Editorial-ready prose summary. ~2-4 paragraphs of "what this work argues"
    // for single-author works, or a brief volume_summary for multi-author works.
    summary: z.string().optional(),
    // Structured summary payload — key points, themes, pull quotes, body-text
    // mentions, completeness. Sits alongside the prose `summary` field.
    summary_structured: summaryStructured.optional(),
    // Per-essay summarization payloads for multi-author works. Joins to
    // `contributors[].toc_index` (static metadata) and to `toc.entries[].toc_index`.
    essays_summarized: z.array(essaySummarized).default([]),
    // Self-reported by the metadata pass when fields couldn't be confidently
    // resolved (e.g., "no_publisher_address_found", "title_page_not_found").
    missing_metadata_flags: z.array(z.string()).default([]),
    // Synthesis-populated reading guide. Empty until Phase 4 Pass 7 runs.
    reading_guide: readingGuide.optional(),
    // Legacy fields (kept for backwards compat with pre-extraction stubs).
    // The DB-imported primary-works carried these; the new pipeline writes
    // `summary` + `summary_structured` instead.
    ai_summary: z.string().optional(),
    ai_key_points: z.array(z.string()).default([]),
    ai: aiProvenance,
    // True when the entry is awaiting LLM extraction (e.g., the 51 entries
    // imported from the legacy DB whose OCR text was stripped).
    needs_extraction: z.boolean().default(false),
    // v1.2 fields — extent caveat, TOC drift, recommended authority additions, dispatch observability.
    extent_caveat: z.boolean().default(false),     // v1.2 D5 — true when pages_rendered/pages_total < 0.3
    toc_drift_detected: z.boolean().default(false),  // v1.2 D14 — true when chunk 1's TOC disagreed with chunk 2's rendered position
    recommended_authority_additions: z.array(recommendedAuthorityAddition).default([]),  // v1.2 D10
    dispatch_count: z.number().int().optional(),    // v1.2 — total subagent dispatches consumed during extraction
    // PDF is hosted on R2 in production. May be null pre-R2-deployment;
    // the staging_pdf_path points to the file on the curator's external drive.
    pdf_url: z.string().url().optional(),
    pdf_staging_path: z.string().optional(),
    pdf_size_mb: z.number().optional(),
    // Tier promotion hooks (empty in v1, populated when paragraph-stable IDs land)
    paragraph_ids: z.array(z.string()).default([]),
    clean_markdown_url: z.string().url().optional(),
    // FRBR-lite manifestation chain (empty unless reprint)
    manifestations: z
      .array(
        z.object({
          year: z.number().int(),
          publisher_name: z.string(),
          place: z.string().optional(),
          edition: z.string().optional(),
          pdf_url: z.string().url().optional(),
        }),
      )
      .default([]),
    ...i18nFields,
    needs_review: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});

// ─── Tier B: periodicals (issues of magazines/journals) ────────────────

const periodicals = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/periodicals' }),
  schema: z.object({
    id: z.string(),
    publication_name: z.string(),
    publication_slug: z.string(),
    publisher_id: z.string().optional(),
    issue: z.object({
      volume: z.string().optional(),
      number: z.string().optional(),
      date: z.coerce.date().optional(),
      label: z.string().optional(),
    }),
    themes: z.array(z.string()).default([]),
    // Editorial-ready prose summary of the issue (what it covers, the
    // editorial frame, notable contributions). Populated by Phase 2.
    summary: z.string().optional(),
    // Structured summary payload (same shape as primary-works).
    summary_structured: summaryStructured.optional(),
    // Legacy fields kept for backwards compat with pre-extraction stubs.
    ai_summary: z.string().optional(),
    ai_key_points: z.array(z.string()).default([]),
    ai: aiProvenance,
    needs_extraction: z.boolean().default(false),
    // v1.2 fields — same shape as primary-works (periodicals can be partially-rendered too).
    extent_caveat: z.boolean().default(false),     // v1.2 D5
    toc_drift_detected: z.boolean().default(false),  // v1.2 D14
    recommended_authority_additions: z.array(recommendedAuthorityAddition).default([]),  // v1.2 D10
    dispatch_count: z.number().int().optional(),    // v1.2 — total subagent dispatches consumed
    physical: z
      .object({
        page_count: z.number().int().optional(),
        page_count_visible: z.number().int().optional(),  // legacy v1.0 field
        pages_rendered: z.number().int().optional(),  // v1.2 D1
        pages_total: z.number().int().optional(),  // v1.2 D1
        pages_total_source: z.enum(['pypdfium2', 'toc_max', 'unknown']).optional(),  // v1.2 D1
        format: z.string().optional(),
      })
      .optional(),
    pdf_url: z.string().url().optional(),
    pdf_staging_path: z.string().optional(),
    pdf_size_mb: z.number().optional(),
    rights: rightsSchema,
    // Per-article extraction — populated by Phase 2 for multi-article issues.
    // Each article gets a short LLM-generated abstract (the `abstract` field
    // is the generated 50-word version, not pulled from a real abstract).
    articles: z
      .array(
        z.object({
          toc_index: z.number().int().optional(),
          title: z.string(),
          author_resolved: reference('thinkers').optional(),
          author_unresolved: z.string().optional(),
          page_start: z.number().int().optional(),
          page_end: z.number().int().optional(),
          page_system: pageSystem.optional(),   // v1.2 D8
          abstract: z.string().optional(),
          partial_essay: z.boolean().default(false),  // v1.2 — sub-chunk failure flag
          pull_quotes: z.array(pullQuote).default([]),
          cross_thinker_mentions: z.array(crossThinkerMention).default([]),
        }),
      )
      .default([]),
    ...i18nFields,
    needs_review: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});

// ─── Tier A: ThePrint federated mirror ─────────────────────────────────

const theprintMirror = defineCollection({
  loader: glob({
    pattern: '**/*.{md,mdx}',
    base: './src/content/theprint-mirror',
  }),
  schema: z.object({
    id: z.string(),
    title: z.string(),
    pubDate: z.coerce.date(),
    author_name: z.string(),
    theprint_url: z.string().url(),
    themes: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    related_works: z.array(z.string()).default([]),
    ai_summary: z.string().optional(),
    ai_key_points: z.array(z.string()).default([]),
    ai: aiProvenance,
    // The mirror is HTML-blocked from search engines (so theprint.in keeps SEO weight)
    // but readable on-site and crawler-accessible to AI bots.
    noindex: z.boolean().default(true),
    ...i18nFields,
    needs_review: z.boolean().default(false),
    draft: z.boolean().default(false),
  }),
});

// ─── Synthesis layer outputs ───────────────────────────────────────────
// Four collections produced by Phase 4 of the LLM extraction pipeline.
// See design doc Phase 3 "Synthesis Layer" table for what each pass emits.

// THEMES — emergent theme taxonomy across the corpus (Pass 1 + Pass 2).
// One entry per theme with editorial-style intro + evolution + open questions.

const themes = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/themes' }),
  schema: z.object({
    id: z.string(),
    label: z.string(),
    blurb: z.string().optional(),
    evolution: z.string().optional(),
    key_works: z.array(z.string()).default([]),
    key_thinkers: z.array(reference('thinkers')).default([]),
    open_questions: z.array(z.string()).default([]),
    parent_theme: z.string().optional(),
    child_themes: z.array(z.string()).default([]),
    intersects_with: z.array(z.string()).default([]),
    ai: aiProvenance,
    needs_review: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});

// PERIOD-WINDOWS — works grouped by decade or named era (Pass 4).
// Editorial context + key debates + key works for each period.

const periodWindows = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/period-windows' }),
  schema: z.object({
    id: z.string(),
    label: z.string(),
    year_start: z.number().int(),
    year_end: z.number().int(),
    context: z.string().optional(),
    key_works: z.array(z.string()).default([]),
    key_thinkers: z.array(reference('thinkers')).default([]),
    key_debates: z
      .array(
        z.object({
          label: z.string(),
          sides: z.array(z.string()).default([]),
          works: z.array(z.string()).default([]),
        }),
      )
      .default([]),
    ai: aiProvenance,
    needs_review: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});

// READING-PATHS — curated sequences (newcomer / scholar / specific-thinker) (Pass 5).
// These are CCS-shaped editorial product surfaces; generated by synthesis as
// proposals, validated with CCS editorial owners before commit (see design doc).

const readingPaths = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/reading-paths' }),
  schema: z.object({
    id: z.string(),
    title: z.string(),
    audience: z.enum(['newcomer', 'scholar', 'specialist', 'specific_thinker', 'specific_theme', 'specific_period']),
    blurb: z.string().optional(),
    sequence: z
      .array(
        z.object({
          work_id: z.string(),
          why_read_now: z.string().optional(),
          estimated_minutes: z.number().int().optional(),
        }),
      )
      .default([]),
    related_themes: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    ai: aiProvenance,
    needs_review: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});

// GRAPH-EDGES — relationship edges between nodes (works, thinkers, themes,
// periods, organisations) (Pass 6). One file per edge type. Designed for a
// future graph-explorer UI; emitted now to avoid retrofit cost (see P11).

const graphEdges = defineCollection({
  // Edge files are JSON, not markdown — synthesis writes them programmatically.
  loader: glob({ pattern: '**/*.json', base: './src/content/graph-edges' }),
  schema: z.object({
    edge_type: z.enum([
      // work → work
      'responds_to',
      'builds_on',
      'cites',
      'reprints',
      'translates',
      // thinker → thinker
      'influenced_by',
      'debated_with',
      'collaborated_with',
      // thinker → organisation
      'member_of',
      'founded',
      'presided',
      // theme → theme
      'parent_of',
      'intersects_with',
      // work → theme / period
      'engages',
      'situated_in',
    ]),
    edges: z
      .array(
        z.object({
          from: z.string(),
          to: z.string(),
          confidence: confidenceFlag.default('medium'),
          evidence_works: z.array(z.string()).default([]),
          source: z
            .enum(['ai_synthesis_v1', 'human_curated', 'ai_synthesis_v2'])
            .default('ai_synthesis_v1'),
          context: z.string().optional(),
        }),
      )
      .default([]),
  }),
});

export const collections = {
  thinkers,
  organisations,
  musings,
  opinions,
  interviews,
  'primary-works': primaryWorks,
  periodicals,
  'theprint-mirror': theprintMirror,
  // Synthesis layer outputs (populated by Phase 4):
  themes,
  'period-windows': periodWindows,
  'reading-paths': readingPaths,
  'graph-edges': graphEdges,
};
