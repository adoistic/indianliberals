import { z, reference } from 'astro:content';

// In-prose thinker mention — populated by the Phase B NER pass.
// One record per (entry, thinker) pair where the thinker appears in the body.
//
// role:
//   - 'author'  — the entry was authored by this thinker. Rarely populated
//                 here; Phase A handled byline-based author detection via
//                 `author` / `authors[]` / `contributors[]` fields.
//   - 'subject' — the entry is primarily ABOUT this thinker (profile pieces,
//                 obituaries). For this role, `key_passages` is populated
//                 with 2-4 curated highlights from the body and `evidence`
//                 stays empty.
//   - 'mention' — the thinker is invoked / quoted / referenced inside an
//                 entry whose primary subject is something else. For this
//                 role, `evidence` carries 1-3 verbatim excerpts with
//                 one-line context strings.
//
// reasoning: 1-2 sentences explaining what this thinker contributes to the
//            entry. Rendered publicly on the bio page; NOT gated behind
//            editorial review.
//
// Every quote MUST be a verbatim substring of the entry's rendered body
// text (under the normalisation rules in apply-ner.py). The apply step
// validates this and drops mentions whose quotes don't substring-match.

export const thinkerMention = z.object({
  // Either a resolved thinker reference OR an unresolved name string.
  // Mirrors the `contributors[]` shape: `thinker` is the canonical-slug
  // reference; `thinker_unresolved` is the literal name when an LLM (or
  // editorial) couldn't match the mention to a thinker MD on disk.
  // The enrichment pipelines emit exactly one of the two per entry.
  thinker: reference('thinkers').optional(),
  thinker_unresolved: z.string().optional(),
  role: z.enum(['author', 'subject', 'mention']),
  reasoning: z.string(),
  evidence: z.array(z.object({
    quote: z.string(),
    context: z.string().optional(),
  })).default([]),
  key_passages: z.array(z.object({
    quote: z.string(),
    what_it_shows: z.string(),
  })).default([]),
});
