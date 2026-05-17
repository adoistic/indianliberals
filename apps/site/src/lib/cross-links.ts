// Cross-link helper. Reads the precomputed TF-IDF related-entries map
// emitted by scripts/synthesis/tfidf.py at build time.
//
// Astro evaluates this module once per build; the JSON import is statically
// inlined into the bundle, so detail pages get the related list with zero
// runtime cost.
//
// Run `python3 scripts/synthesis/tfidf.py` from the repo root to refresh
// the underlying data after content changes (the build script in package.json
// can be extended to call this when we wire it into CI).

import crossLinksJson from '../../../../data/synthesis/cross-links.json';
import { pathForEntry, type LangCode } from './i18n';

export interface CrossLink {
  collection: string;
  slug: string;
  title: string;
  score: number;
}

const RAW: Record<string, CrossLink[]> = crossLinksJson as Record<string, CrossLink[]>;

/**
 * Look up the top-N TF-IDF-similar entries for a (collection, slug) pair.
 * Returns an empty array if the entry has no related-list (rare; only true
 * for entries with very thin body content the TF-IDF script discards).
 */
export function getCrossLinks(collection: string, slug: string): CrossLink[] {
  return RAW[`${collection}:${slug}`] ?? [];
}

/**
 * Resolve a cross-link to the language-aware URL path for the linked entry.
 * Cross-links are emitted from the English corpus only; the URL uses the
 * caller's language so the user stays inside their language context where
 * a translation exists (best-effort — translations may not exist yet).
 */
export function urlForCrossLink(link: CrossLink, viewerLang: LangCode = 'en'): string {
  return pathForEntry(link.collection, link.slug, viewerLang);
}

/**
 * Friendly label for the collection name shown in the "Related" UI.
 */
export const COLLECTION_LABEL: Record<string, string> = {
  'primary-works': 'Primary work',
  'musings': 'Excerpt',
  'opinions': 'Opinion',
  'interviews': 'Interview',
  'thinkers': 'Thinker',
  'organisations': 'Organisation',
  'theprint-mirror': 'ThePrint',
};
