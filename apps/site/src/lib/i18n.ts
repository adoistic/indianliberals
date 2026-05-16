/**
 * i18n helpers — the single source of truth for how a content entry's
 * URL is computed and how hreflang alternates are emitted.
 *
 * Conventions (per Google's multilingual SEO guidelines):
 *
 * - English (the default locale) lives at the root: /<collection>/<slug>/
 *   No /en/ prefix because `prefixDefaultLocale: false` in astro.config.
 * - Non-English content lives at /<lang>/<collection>/<slug>/.
 * - Slugs are always transliterated Latin (per Adnan's call). The native-
 *   script title is preserved in frontmatter (`title.original_script`).
 * - Every page is single-language. No mixed-language content on one URL.
 * - hreflang is bidirectional and self-referential: every language version
 *   of the same intellectual content references every other version,
 *   including itself, plus an `x-default` (English).
 */

export type LangCode = 'en' | 'hi' | 'gu' | 'mr' | 'bn';

export const DEFAULT_LOCALE: LangCode = 'en';

export const LOCALES: readonly LangCode[] = ['en', 'hi', 'gu', 'mr', 'bn'] as const;

// BCP 47 region codes used in hreflang and og:locale. We're an India-
// focused archive so all locales are pinned to India.
export const BCP47: Record<LangCode, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
  gu: 'gu-IN',
  mr: 'mr-IN',
  bn: 'bn-IN',
};

// Open Graph locale codes (uses underscore, not hyphen).
export const OG_LOCALE: Record<LangCode, string> = {
  en: 'en_IN',
  hi: 'hi_IN',
  gu: 'gu_IN',
  mr: 'mr_IN',
  bn: 'bn_IN',
};

export const LANG_NAMES: Record<LangCode, { native: string; english: string }> = {
  en: { native: 'English', english: 'English' },
  hi: { native: 'हिन्दी', english: 'Hindi' },
  gu: { native: 'ગુજરાતી', english: 'Gujarati' },
  mr: { native: 'मराठी', english: 'Marathi' },
  bn: { native: 'বাংলা', english: 'Bengali' },
};

/**
 * Build the language-aware URL path for a content entry.
 *
 * @param collection - "musings" | "opinions" | "thinkers" | ...
 * @param slug - the entry id (kebab-case Latin)
 * @param language - the entry's language code
 * @returns absolute path including trailing slash, e.g. "/mr/musings/foo/"
 */
export function pathForEntry(
  collection: string,
  slug: string,
  language: LangCode = DEFAULT_LOCALE,
): string {
  const prefix = language === DEFAULT_LOCALE ? '' : `/${language}`;
  return `${prefix}/${collection}/${slug}/`;
}

/**
 * Build the language-aware URL path for a top-level collection index
 * (e.g. /musings/, /mr/musings/, /thinkers/, /bn/thinkers/).
 */
export function pathForCollection(
  collection: string,
  language: LangCode = DEFAULT_LOCALE,
): string {
  const prefix = language === DEFAULT_LOCALE ? '' : `/${language}`;
  return `${prefix}/${collection}/`;
}

/**
 * Given a content entry, build the list of hreflang alternates for its
 * <head>. Returns an array of { hreflang, href } records — every available
 * translation of the same intellectual content, including a self-
 * referential entry and an x-default pointing to the English version
 * (or the original-language version if no English exists).
 *
 * The caller passes both the entry itself and the resolution map of
 * other-language ids — so we can compute hrefs without needing to look up
 * other entries (which would create circular import problems at render time).
 *
 * @param collection - the entry's collection name
 * @param entryId - the entry's slug/id
 * @param entryLang - the entry's language
 * @param translations - frontmatter `translations` map, lang → slug. Should
 *                       NOT include the entry's own language (we add it
 *                       automatically as self).
 * @param siteOrigin - absolute origin, e.g. "https://indianliberals.in"
 */
export function hreflangAlternates(
  collection: string,
  entryId: string,
  entryLang: LangCode,
  translations: Partial<Record<LangCode, string>> | undefined,
  siteOrigin: string,
): { hreflang: string; href: string }[] {
  const map: Partial<Record<LangCode, string>> = {
    ...(translations || {}),
    [entryLang]: entryId, // self
  };

  const alternates: { hreflang: string; href: string }[] = [];

  for (const lang of LOCALES) {
    const slug = map[lang];
    if (!slug) continue;
    alternates.push({
      hreflang: BCP47[lang],
      href: siteOrigin + pathForEntry(collection, slug, lang),
    });
  }

  // x-default: prefer English, fall back to the entry's own language
  // if no English translation exists.
  const defaultSlug = map.en || map[entryLang];
  const defaultLang = map.en ? 'en' : entryLang;
  if (defaultSlug) {
    alternates.push({
      hreflang: 'x-default',
      href: siteOrigin + pathForEntry(collection, defaultSlug, defaultLang),
    });
  }

  return alternates;
}

/**
 * True if the page should be set to noindex based on its translation status.
 * AI-translated pages stay noindex until reviewed.
 */
export function shouldNoindex(translationStatus: string | undefined): boolean {
  return (
    translationStatus === 'ai_translation' ||
    translationStatus === 'needs_translation'
  );
}
