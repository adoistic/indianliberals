// One place for "should this work appear", in its three shades.
//
// There are a dozen places that read the primary-works collection, and a
// work hidden from eleven of them is not hidden. Kept here so adding a reason
// to withhold a work is one edit rather than twelve.
//
// Three flags, three meanings:
//
//   draft            not ready: not built, not listed, not counted.
//   hide_from_index  not trusted: the six works whose source PDF was never
//                    digitised (three carrying a summary of a different
//                    document). Their pages build and resolve; they are not
//                    listed and not counted. See docs/missing-pdfs-and-bad-summaries.md.
//   withheld         not for now: temporarily kept from readers and agents at
//                    CCS's request, but STILL COUNTED in the archive's totals.
//                    The page stays at its address as a notice with no
//                    content; the work is in no list, search index, feed or
//                    sitemap; the record and its PDF are untouched. Flip the
//                    flag (in the file or in the CMS) and it is back on the
//                    next build. See docs/withheld-works.md.

type Listable = {
  data: { draft?: boolean; hide_from_index?: boolean; withheld?: boolean };
};

/** True when a work counts towards the archive's totals. */
export function isCounted(w: Listable): boolean {
  return !w.data.draft && !w.data.hide_from_index;
}

/** True when a work is temporarily withheld from readers and agents. */
export function isWithheld(w: Listable): boolean {
  return Boolean(w.data.withheld);
}

/**
 * True when a work belongs in an index, a search result, a feed, or an
 * agent-facing manifest. Everything that offers a work to a reader or an
 * agent goes through this; the totals go through isCounted.
 */
export function isListed(w: Listable): boolean {
  return isCounted(w) && !isWithheld(w);
}
