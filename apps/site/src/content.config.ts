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
//
// Shared sub-schemas live in `./schemas/` — this file imports them so each
// `defineCollection` stays focused on its own contract.

import { defineCollection, reference, z } from 'astro:content';
import { glob } from 'astro/loaders';

import {
  aiProvenance,
  confidenceFlag,
  crossThinkerMention,
  essaySummarized,
  i18nFields,
  intellectualArc,
  multilingualTitle,
  organisationName,
  pageSystem,
  pullQuote,
  purposeEnum,
  readingGuide,
  recommendedAuthorityAddition,
  rightsSchema,
  summaryStructured,
  thinkerMention,
  thinkerName,
  tocEntry,
} from './schemas';

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
      .enum([
        'canonical',         // hand-curated CCS bio
        'feature_article',   // adapted from a longer published profile
        'ai_drafted',        // full AI-drafted bio reviewed by editorial
        'ai_drafted_stub',   // minimal stub from the Phase A cross-link audit; Phase 1.5 will expand
        'imported',          // imported from the WordPress export, often a placeholder
      ])
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
    name: organisationName,
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
    // `related_thinkers` carries thinkers mentioned inside the body of
    // the excerpt but who are neither the author nor the subject. Drives
    // the "Mentioned in" section on bio pages. Empty in Phase A; populated
    // by the Phase B in-prose NER pass.
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
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
    // `author_name` is the writer (often "Editorial Team" for CCS profile
    // pieces); `author` is the structured ref to the writer's thinker
    // entry when one exists. Most opinions are written by Editorial Team
    // ABOUT a thinker — that thinker goes in `subject`.
    author_name: z.string(),
    author: reference('thinkers').optional(),
    // `subject` is the thinker the piece profiles, populated for profile-
    // style opinions ("Anandibai Joshee: First Indian Woman Doctor"). Drives
    // the "Profile pieces and interviews about <X>" section on the bio page.
    subject: reference('thinkers').optional(),
    themes: z.array(z.string()).default([]),
    related_works: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
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
    // Optional sub-type qualifier. See `purposeEnum` definition in schemas/extraction.ts.
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
    thinker_mentions: z.array(thinkerMention).default([]),
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
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
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
    thinker_mentions: z.array(thinkerMention).default([]),
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
