// Paragraph-stable ID derivation — the single source of truth.
//
// Both the HTML pipeline (src/plugins/remark-paragraph-ids.mjs adds
// id="p-xxxxxx" anchors to rendered <p> elements) and the .md siblings
// (src/lib/md-sibling.ts appends <!-- #p-xxxxxx --> annotations) derive
// IDs through this function, so a citation minted from either surface
// resolves on the other.
//
// The hash input is the paragraph's *plain text* (mdast-util-to-string
// output: markdown syntax, link URLs, and emphasis markers stripped,
// whitespace collapsed). That makes IDs stable across formatting-only
// edits — fixing a link target or bolding a phrase keeps the anchor;
// rewording the sentence changes it, which is what "paragraph-stable"
// promises: the ID follows the content, not the position.
//
// Plain .mjs (not .ts) so astro.config.mjs can import it for the remark
// plugin without a TS loader in the config path.

/**
 * Derive the stable ID for one paragraph.
 * @param {string} text - plain text of the paragraph
 * @returns {string} e.g. "p-3fa2c1" (6 hex chars of FNV-1a over the
 *   whitespace-normalized text)
 */
export function paragraphIdFor(text) {
  const normalized = text.replace(/\s+/g, ' ').trim();
  let h = 0x811c9dc5; // FNV-1a 32-bit offset basis
  for (let i = 0; i < normalized.length; i++) {
    h ^= normalized.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0; // FNV prime
  }
  return 'p-' + h.toString(16).padStart(8, '0').slice(0, 6);
}

/**
 * Assign IDs to an ordered list of paragraph texts, disambiguating
 * repeats (identical paragraphs on one page get -2, -3… suffixes so
 * anchors stay unique). Both pipelines iterate top-level paragraphs in
 * document order, so the suffixes agree.
 * @param {string[]} texts
 * @returns {string[]}
 */
export function paragraphIdsFor(texts) {
  const seen = new Map();
  return texts.map((text) => {
    const base = paragraphIdFor(text);
    const n = (seen.get(base) ?? 0) + 1;
    seen.set(base, n);
    return n === 1 ? base : `${base}-${n}`;
  });
}
