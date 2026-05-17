// Multilingual primitives shared across every content kind.
//
// Every entry exposes a `language`, an optional pointer to the original-language
// version (`translation_of`), and a map of all other-language siblings
// (`translations`). BaseLayout reads these and emits bidirectional hreflang
// alternates per Google's multilingual SEO guidelines.
//
// `multilingualTitle` carries the surface forms used by primary-works:
// the original script (Devanagari / Gujarati / Bengali / etc.), an English
// transliteration, and an English translation when applicable.

import { z } from 'astro:content';

export const LANG_CODES = ['en', 'hi', 'gu', 'mr', 'bn'] as const;

export const i18nFields = {
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

export const multilingualTitle = z.object({
  main: z.string(),
  subtitle: z.string().optional(),
  original_script: z.string().optional(),
  translit: z.string().optional(),
  translation: z.string().optional(),
});
