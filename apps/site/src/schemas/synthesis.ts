// Sub-schemas populated by the synthesis layer (Phase 4 of the LLM
// extraction pipeline). These ride on the thinker and primary-works
// schemas but are populated by later synthesis passes (Pass 3, Pass 7).

import { z, reference } from 'astro:content';

// Per-work reading guide, populated by Phase 4 Pass 7 per-work enrichment.
// Surfaces "how to approach" + audience signals on each primary-works page.
export const readingGuide = z.object({
  how_to_approach: z.string().optional(),
  difficulty: z.enum(['introductory', 'intermediate', 'advanced']).optional(),
  estimated_minutes: z.number().int().optional(),
  prerequisites: z.array(z.string()).default([]),
  why_this_matters: z.string().optional(),
  best_read_alongside: z
    .array(z.object({ work_id: z.string(), relationship: z.string() }))
    .default([]),
});

// Per-thinker intellectual arc, populated by Phase 4 Pass 3 per-thinker
// genealogy pass.
export const intellectualArc = z.object({
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
