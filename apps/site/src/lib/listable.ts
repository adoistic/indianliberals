// One predicate for "should this work appear in a listing".
//
// There are ten places that read the primary-works collection, and a work
// hidden from nine of them is not hidden. Kept here so adding a reason to
// withhold a work is one edit rather than ten.

type Listable = { data: { draft?: boolean; hide_from_index?: boolean } };

/**
 * True when a work belongs in an index, a count, or an agent-facing manifest.
 *
 * `hide_from_index` withholds a work whose record we do not trust: at present
 * the six whose source PDF was never digitised, three of them carrying a
 * summary written from a different document. Their pages still build and still
 * resolve; they are simply not offered anywhere. See
 * docs/missing-pdfs-and-bad-summaries.md.
 */
export function isListed(w: Listable): boolean {
  return !w.data.draft && !w.data.hide_from_index;
}
