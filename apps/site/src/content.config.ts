// Astro content collections for the eight Indian Liberals content kinds.
// This file is the runtime contract that SCHEMA.md is the prose-form of.
//
// Tier A = clean content (musings, opinions, thinker-profiles,
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

import './lib/check-slug-uniqueness';

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
      'constitutional_liberal',
      'contemporary_liberal',
      'international_influence', // DEPRECATED but still accepted (sub-project 2 reclassifies)
      'libertarian',
      'non_liberal',
      'practice',
      'social_reformer',
      'unclassified',
    ]),
    canon_status: z.enum([
      'core',         // Central to the classical-liberal / libertarian canon
      'extended',     // Broader liberal tradition (constitutional, contemporary, reform-era, honored practitioners)
      'referenced',   // Mentioned in the corpus but outside the liberal tradition
      'unclassified', // Default
    ]).default('unclassified'),
    // Curated canon page membership. The /thinkers/ landing page shows ONLY
    // featured entries (legacy-site 13 + select core additions, per CCS
    // editorial direction 2026-06); everyone else stays reachable via
    // /thinkers/directory/. Presentation-only — no thinker is ever removed.
    featured: z.boolean().default(false),
    vocations: z.array(z.enum([
      // Academic / theoretical
      'philosopher', 'economist', 'historian', 'political_scientist',
      'sociologist', 'legal_scholar', 'scientist', 'engineer', 'professor',
      // Writing / editorial
      'writer', 'editor', 'journalist', 'poet',
      // Public office / governance
      'statesman', 'parliamentarian', 'civil_servant', 'diplomat', 'judge',
      // Business / enterprise
      'industrialist', 'entrepreneur',
      // Civil society
      'activist', 'reformer', 'religious_figure',
      // Other
      'military_officer', 'artist',
    ])).default([]),
    themes: z.array(z.string()).default([]),
    affiliations: z.array(z.string()).default([]),
    portrait: z
      .object({
        photo: z.string().optional(),
        caricature: z.string().optional(),
        ring_portrait: z.string().optional(),
        // Uniform archival duotone derived from photo/caricature by
        // scripts/synthesis/make-duotone-portraits.py. The curated canon
        // page renders this for visual consistency (CCS feedback 2.2);
        // detail pages keep the original photo/caricature.
        duotone: z.string().optional(),
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

// ─── Contemporary contributors (opinion-piece writers) ───────────────
// Distinct from `thinkers` (which is the canonical Indian liberal canon).
// Contributors are CCS fellows / interns / guest writers whose bios
// were extracted from the trailing bio block of opinion pieces.
// See docs/superpowers/specs/2026-05-25-contributors-collection-design.md.

const contributors = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/contributors' }),
  schema: z.object({
    id: z.string(),
    name: z.object({
      canonical: z.string(),
      sort: z.string(),
      also_known_as: z.array(z.string()).default([]),
    }),
    // Local path under /public, e.g. "/contributors/photos/sanjeet-kashyap.jpg".
    // Optional — some imported bios had no photo.
    photo: z.string().optional(),
    // Optional structured fields. Bios mention these inconsistently;
    // extraction is best-effort. Curator fills the rest when triaging.
    affiliation: z.string().optional(),       // e.g. "Centre for Civil Society"
    role: z.string().optional(),              // e.g. "Indian Liberal Fellow"
    joined_at: z.number().int().optional(),   // year
    areas_of_interest: z.array(z.string()).default([]),
    bio_source: z
      .enum(['extracted_from_opinion_bio', 'curator', 'imported'])
      .default('extracted_from_opinion_bio'),
    needs_review: z.boolean().default(true),
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
    // 1–2 sentence editorial description shown on the index cards and as
    // the detail-page lede. AI-drafted 2026-06 (CCS feedback item 3);
    // editorial refines via Sveltia.
    description: z.string().optional(),
    // Path under /public, e.g. "/organisations/logos/ccs.svg". Cards and
    // detail headers render a monogram tile when absent — most defunct
    // organisations have no surviving mark.
    logo: z.string().optional(),
    ...i18nFields,
    needs_review: z.boolean().default(false),
    draft: z.boolean().default(false),
    // Keep the record (its detail page still builds and stays linkable from
    // thinker affiliations) but exclude it from the /organisations/ index
    // listing. Used for entities that appear only because thinkers operated
    // within them (e.g. the Indian National Congress) and are not part of
    // "our" liberal organisations. CCS round-2 feedback #13/#14 — hide, not
    // delete.
    hide_from_index: z.boolean().default(false),
    /** Why it is hidden, so the next person does not have to guess. */
    hide_reason: z.string().optional(),
  }),
});

// ─── Classification dimensions shared by musings + opinions ────────────
// Populated by the classification pass (scripts/synthesis/apply-classify.py).
// See docs/superpowers/specs/2026-05-18-musings-opinions-classification-design.md
const classificationFields = {
  proposed_themes: z.array(z.string()).default([]),
  key_concepts: z.array(z.string()).max(5).default([]),
  pull_quote: z.string().optional(),
  stance: z
    .enum(['argues-for', 'argues-against', 'analyzes', 'profiles', 'commemorates'])
    .optional(),
  geographic_scope: z
    .object({
      scale: z
        .enum(['national', 'regional', 'bi-regional', 'international-comparison'])
        .optional(),
      places: z.array(z.string()).default([]),
    })
    .optional(),
  period_window: z
    .enum(['pre-independence', 'nehruvian-era', 'late-license-raj', 'reform-era', 'post-reform'])
    .optional(),
  source_channel: z.string().optional(),
};

// ─── Tier A: musings (excerpts from primary works) ─────────────────────

const musings = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/musings' }),
  schema: z.object({
    id: z.string(),
    title: z.string(),
    pubDate: z.coerce.date(),
    excerpt_of: z.string().optional(), // primary-works ID
    author: reference('thinkers').optional(),
    // Featured image, e.g. "/musings/covers/<slug>.webp". Recovered from the
    // legacy WordPress musings cards (topical imagery), with a fallback to the
    // source work's cover for musings the archive didn't preserve. Drives the
    // image-led card grid on /musings/ and the hero on the detail page.
    hero_image: z.string().optional(),
    // `related_thinkers` carries thinkers mentioned inside the body of
    // the excerpt but who are neither the author nor the subject. Drives
    // the "Mentioned in" section on bio pages. Empty in Phase A; populated
    // by the Phase B in-prose NER pass.
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    themes: z.array(z.string()).default([]),
    ...classificationFields,
    kind: z
      .enum([
        'book-excerpt',
        'pamphlet-excerpt',
        'speech-excerpt',
        'lecture',
        'periodical-article',
        'letter',
      ])
      .optional(),
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
    // pieces); `author` is the structured ref to the writer's
    // contributor entry when one exists. Most opinions are written by
    // Editorial Team ABOUT a thinker — that thinker goes in `subject`.
    author_name: z.string(),
    author: reference('contributors').optional(),
    // Featured image recovered from the legacy WordPress site (the old
    // opinions-and-events cards), e.g. "/opinions/covers/<slug>.webp".
    // Drives the card grid on /opinions/ and the hero on the detail page.
    hero_image: z.string().optional(),
    // `subject` is the thinker the piece profiles, populated for profile-
    // style opinions ("Anandibai Joshee: First Indian Woman Doctor"). Drives
    // the "Profile pieces and interviews about <X>" section on the bio page.
    subject: reference('thinkers').optional(),
    themes: z.array(z.string()).default([]),
    related_works: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    ...classificationFields,
    kind: z
      .enum([
        'profile',
        'commentary',
        'review',
        'obituary',
        'event-coverage',
        'editorial',
      ])
      .optional(),
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
      'interview',
      'lecture', // NEW — formal named lecture (annual/memorial series, addresses); rendered under /lectures/
    ]),
    // Optional sub-type qualifier. See `purposeEnum` definition in schemas/extraction.ts.
    purpose: purposeEnum.optional(),
    authors: z.array(z.union([reference('thinkers'), reference('organisations')])).default([]),
    editors: z.array(z.union([reference('thinkers'), reference('organisations')])).default([]),
    // Static metadata roster (who's in the book + their role), produced by
    // the metadata pass. Joins to `essays_summarized[]` via `toc_index`.
    contributors: z
      .array(
        z.object({
          thinker: reference('thinkers').optional(),
          thinker_unresolved: z.string().nullable().optional(),
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
      // Free-text label exactly as printed on the item ("Sixth A. D. Shroff
      // Memorial Lecture"). Descriptive only — it does not group anything.
      series: z.string().optional(),
      // Membership in a named non-periodical run. This is what /series/ groups
      // on. A work carries its MOST SPECIFIC series: an A. D. Shroff lecture
      // gets `ad-shroff-memorial-lecture`, not the parent `ffe-booklets`.
      series_id: reference('series').optional(),
      // This item's own number within the run, when it is numbered. Null for
      // date-ordered runs, and for items whose number was never recorded.
      series_ordinal: z.number().int().positive().optional(),
      language: z.string().default('en'),
    }),
    physical: z
      .object({
        page_count: z.number().int().optional(),  // legacy field — kept for backward compat
        page_count_visible: z.number().int().optional(),  // legacy v1.0 field — superseded by pages_rendered/total
        pages_rendered: z.number().int().optional(),  // v1.2 D1 — pages the model actually saw across all chunks
        pages_total: z.number().int().optional(),  // v1.2 D1 — total page count of the source PDF
        pages_total_source: z.enum(['pypdfium2', 'pdfinfo', 'pypdf', 'toc_max', 'unknown']).optional(),  // v1.2 D1 provenance
        // 'pdfinfo' added 2026-07-27: the re-extraction of the contaminated
        // Indian Libertarian issues counted pages with pdfinfo, and recording
        // which tool produced the count is the point of this field.
        // 'pypdf' added 2026-08-03: the two Forum of Free Enterprise pamphlets
        // that never carried a count were measured off the R2 copy with pypdf,
        // so the archive-wide page total covers every PDF we serve.
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
    youtube_url: z.string().url().optional(),
    transcript_status: z.enum(['none', 'partial', 'complete', 'unavailable']).default('none'),
    // Explicit editorial routing for video works (interview/lecture), preferred
    // over the id-pattern heuristics in lib/interviews.ts. `video_group` places
    // an interview on an /interviews/ shelf; `speaker_name` names the figure
    // when the speaker has no thinker profile (so it can't live in `authors`).
    video_group: z.enum(['oral', 'talks', 'explainers', 'conversations']).optional(),
    speaker_name: z.string().optional(),
    // Editorial description (preserved verbatim from a migrated interview MD's body, if non-garbage).
    // Distinct from `summary` (the AI-generated synopsis emitted by Phase B enrichment).
    description: z.string().optional(),
    // Phase B enrichment output for interview MDs. The pre-existing
    // `ai_key_points` field is reserved for the v1.5 PDF-extractor; interviews
    // use this field instead. Both render the same way at the UI layer.
    key_points: z.array(z.string()).default([]),
    rights: rightsSchema,
    themes: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    // Authors resolution provenance — populated by scripts/synthesis/apply-byline.py.
    // Lets the curator audit which entries were matched deterministically vs LLM vs
    // vision, which had to fall back to auto-stubbing new thinkers, and which had
    // silent slug-collisions with existing thinkers. See
    // docs/superpowers/specs/2026-05-19-primary-works-byline-resolution-design.md
    authors_resolution: z
      .object({
        confidence: z.enum(['high', 'medium', 'low']).optional(),
        method: z.enum(['deterministic', 'llm', 'vision']).optional(),
        proposed_unknowns: z.array(z.string()).default([]),
        stubs_created: z.array(z.string()).default([]),
        stubs_referenced: z.array(z.string()).default([]),
        collisions_logged: z.array(z.string()).default([]),
      })
      .optional(),
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
    // v1.2 D5 — true when pages_rendered/pages_total < 0.3. May instead carry a
    // one-line string spelling out exactly what the summary was based on, for
    // hand-read image-only scans where the bare boolean loses useful detail.
    extent_caveat: z.union([z.boolean(), z.string()]).default(false),
    toc_drift_detected: z.boolean().default(false),  // v1.2 D14 — true when chunk 1's TOC disagreed with chunk 2's rendered position
    recommended_authority_additions: z.array(recommendedAuthorityAddition).default([]),  // v1.2 D10
    dispatch_count: z.number().int().optional(),    // v1.2 — total subagent dispatches consumed during extraction
    // PDF is hosted on R2 in production. May be null pre-R2-deployment;
    // the staging_pdf_path points to the file on the curator's external drive.
    pdf_url: z.string().url().optional(),
    pdf_staging_path: z.string().optional(),
    pdf_size_mb: z.number().optional(),
    // First-page raster of the source PDF, hosted on R2 alongside the PDFs,
    // e.g. "https://pub-<hash>.r2.dev/covers/<slug>.webp" (Adnan, 2026-07 —
    // moved off the repo to R2 to match the PDF hosting). Gives listing pages a
    // visual shelf instead of text-only cards.
    cover_image: z.string().optional(),
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
    // Keep the work in the archive and its page resolving, but take it out of
    // every listing and every count. Same principle as `hide_from_index` on
    // organisations: hide, not delete.
    //
    // Set on the six works whose source PDF was never digitised, three of
    // which carry a summary written from a different document. The page stays
    // reachable so nothing already linked breaks, but it withholds the body
    // and is noindexed while the flag is set. See
    // docs/missing-pdfs-and-bad-summaries.md. Clear the flag once CCS supplies
    // the scan and the entry has been re-extracted from it.
    hide_from_index: z.boolean().default(false),
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
        pages_total_source: z.enum(['pypdfium2', 'pdfinfo', 'pypdf', 'toc_max', 'unknown']).optional(),  // v1.2 D1
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
    // Featured image on ThePrint's CDN (hotlinked, not mirrored — their
    // photos are agency-licensed). Joined in by the ingest from the WP REST
    // API; the RSS feed itself carries no images.
    hero_image: z.string().url().optional(),
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

// SERIES — named non-periodical runs: publisher booklet series, annual memorial
// lectures, numbered occasional-paper runs, recurring annual analyses.
//
// This is the third series surface, alongside /periodicals/ (dated issues of a
// serial, keyed off work_type: "periodical_issue") and /lectures/ (video
// recordings, keyed off work_type: "lecture"). A print series is none of those:
// each item is a standalone document that happens to be the Nth in a run. Works
// join a series through `publication.series_id`; `publication.series` stays as
// the free-text label printed on the item itself.

const series = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/series' }),
  schema: z.object({
    id: z.string(),
    name: z.string(),
    // Shown under the name; the run's own subtitle or alternate designation.
    native: z.string().optional(),
    blurb: z.string(),
    // What kind of run this is — drives grouping on the /series/ index.
    kind: z.enum([
      'booklet_series', // a publisher's numbered/unnumbered booklet run
      'lecture_series', // an annual or memorial named lecture
      'occasional_papers', // a numbered occasional-paper run
      'annual_analysis', // a recurring yearly commentary (e.g. the union budget)
      'multi_part_work', // a work issued in parts/volumes
    ]),
    publisher_id: z.string().optional(),
    issuer_id: z.string().optional(),
    // Nesting: the A. D. Shroff Memorial Lecture booklets are themselves part of
    // the wider Forum of Free Enterprise run.
    parent_series: z.string().optional(),
    // True when items carry their own printed number (so we can render "No. 12"
    // and flag gaps). False for date-ordered runs like the FFE booklets, whose
    // colophon carries a date rather than a serial number.
    numbered: z.boolean().default(false),
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
  contributors,
  organisations,
  musings,
  opinions,
  'primary-works': primaryWorks,
  periodicals,
  series,
  'theprint-mirror': theprintMirror,
  // Synthesis layer outputs (populated by Phase 4):
  themes,
  'period-windows': periodWindows,
  'reading-paths': readingPaths,
  'graph-edges': graphEdges,
};
