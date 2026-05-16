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
      'periodical_issue',
    ]),
    authors: z.array(reference('thinkers')).default([]),
    contributors: z
      .array(z.object({ thinker: reference('thinkers'), role: z.string() }))
      .default([]),
    publication: z.object({
      publisher_id: z.string().optional(),
      publisher_name: z.string().optional(),
      place: z.string().optional(),
      year: z.number().int().nullable().optional(),
      edition: z.string().optional(),
      series: z.string().optional(),
      language: z.string().default('en'),
    }),
    physical: z
      .object({
        page_count: z.number().int().optional(),
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
    // AI-extracted (Tier B surface)
    ai_summary: z.string().optional(),
    ai_key_points: z.array(z.string()).default([]),
    ai: aiProvenance,
    pdf_url: z.string().url(),
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
    language: z.string().default('en'),
    themes: z.array(z.string()).default([]),
    ai_summary: z.string().optional(),
    ai_key_points: z.array(z.string()).default([]),
    ai: aiProvenance,
    pdf_url: z.string().url(),
    pdf_size_mb: z.number().optional(),
    rights: rightsSchema,
    // Future scope: per-article extraction
    articles: z
      .array(
        z.object({
          title: z.string(),
          author: z.string().optional(),
          page_start: z.number().int().optional(),
          page_end: z.number().int().optional(),
          abstract: z.string().optional(),
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

export const collections = {
  thinkers,
  organisations,
  musings,
  opinions,
  interviews,
  'primary-works': primaryWorks,
  periodicals,
  'theprint-mirror': theprintMirror,
};
