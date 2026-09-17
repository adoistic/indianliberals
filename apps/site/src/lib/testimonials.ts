// Shared testimonial ordering, used by /testimonials/ and the homepage.
//
// `order` is explicit and editor-controlled; entries without one follow, by
// name, so a testimonial added from the CMS without a number still appears
// rather than vanishing to the bottom of nowhere.

import { getCollection } from "astro:content";
import type { CollectionEntry } from "astro:content";
import { metaExcerpt } from "~/lib/excerpt";

export type Testimonial = CollectionEntry<"testimonials">;

const NO_ORDER = 999_999;

export function byOrder(a: Testimonial, b: Testimonial): number {
  return (
    (a.data.order ?? NO_ORDER) - (b.data.order ?? NO_ORDER) ||
    a.data.name.localeCompare(b.data.name)
  );
}

/** Every listed testimonial, featured first, each group in `order`. */
export async function getTestimonials(): Promise<Testimonial[]> {
  const all = await getCollection("testimonials", (t) => !t.data.draft);
  return all.sort(
    (a, b) => Number(b.data.featured) - Number(a.data.featured) || byOrder(a, b),
  );
}

/** The featured ones alone, in `order`, for the homepage. */
export async function getFeaturedTestimonials(limit = 4): Promise<Testimonial[]> {
  return (await getTestimonials()).filter((t) => t.data.featured).slice(0, limit);
}

/**
 * The one-sentence version: the editor's pull quote, else the opening of the
 * quotation cut at a word. The body is plain prose, so the meta-excerpt
 * stripper is exactly the right tool.
 */
export function pullQuote(t: Testimonial, max = 180): string {
  const own = t.data.pull_quote?.trim();
  if (own) return own;
  return metaExcerpt(t.body ?? "", max);
}
