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

/** Same title, ignoring case, punctuation and spacing. */
function titleKey(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
}

/**
 * Look up the top-N TF-IDF-similar entries for a (collection, slug) pair.
 * Returns an empty array if the entry has no related-list (rare; only true
 * for entries with very thin body content the TF-IDF script discards).
 *
 * Entries repeating a title are collapsed to the first, which is the
 * highest-scoring since the source is emitted in descending score. CCS
 * reported the same article appearing twice in "Related across the archive"
 * (round-3 feedback, 6.1); it affects 76 of the 851 entries and removes 88
 * repeated links in all. Two causes sit underneath, and only one of them is a
 * display problem:
 *
 *   - The same work really is in the corpus twice under two slugs, as
 *     `...m-a-rangoonwaala-june-15-1982` and `...by-ma-rangoonwala-1982`.
 *     Two musings are duplicates of each other the same way.
 *   - Two different works carry the same title, because one of them has the
 *     wrong title: `the-challenge-of-rural-development...` is recorded as
 *     "The Basic Truth About Inflation".
 *
 * Collapsing here stops a reader being offered the same link twice whichever
 * cause applies. It does not clean the records, which is a separate data pass
 * and is on the list for CCS.
 */
export function getCrossLinks(collection: string, slug: string): CrossLink[] {
  const links = RAW[`${collection}:${slug}`] ?? [];
  const best = new Map<string, CrossLink>();
  for (const link of links) {
    const key = titleKey(link.title);
    const held = best.get(key);
    if (!held || link.score > held.score) best.set(key, link);
  }
  // TF-IDF emits in descending score and the map preserves insertion order,
  // so the surviving links stay in the order they were ranked.
  return [...best.values()];
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
