// One predicate for "is this thinker part of the canon the site presents".
//
// This exists because the number and the list drifted apart. The nav counted
// every `featured` thinker (28) while /thinkers/ rendered only the Indian ones
// (23), so the navigation advertised five people the page then withheld: the
// international influences (Mill, Hayek, Mises, Friedman, Bauer), which are
// featured in the data but deliberately not shown on the canon page. Same
// reasoning as `isListed` in ./listable.ts: a rule applied in one of two
// places is not a rule, so both now read it from here.

type CanonThinker = {
  data: {
    draft?: boolean;
    language?: string;
    featured?: boolean;
    nationality?: string;
  };
};

/**
 * True when a thinker belongs on /thinkers/ and in the count that advertises it.
 *
 * `featured` is the editorial flag (Sveltia-editable, presentation-only) and
 * `nationality === "india"` is the this-is-the-*Indian*-liberals-archive rule
 * (Adnan, 2026-07): the international influences stay in the archive, in search
 * and on their own detail pages, but the canon page presents Indians.
 *
 * The draft/language guards are usually already applied by the caller's
 * getCollection filter; repeating them here is deliberate, so this is safe to
 * call on an unfiltered collection and cannot quietly count a draft.
 */
export function isCanonThinker(t: CanonThinker): boolean {
  return (
    !t.data.draft &&
    (t.data.language ?? "en") === "en" &&
    !!t.data.featured &&
    t.data.nationality === "india"
  );
}
