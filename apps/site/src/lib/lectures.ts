// Lectures index used by /lectures/ (the wall of series cards) and
// /lectures/[series]/ (one lecture series' recordings).
//
// Formal named lectures live inside the primary-works collection with
// work_type: "lecture" — the annual/memorial series (marquee economists and
// public figures delivering one address a year) plus the historic addresses
// recovered from the archive (Palkhivala's 1992 Union Budget address, Sudha
// Shenoy's Mises lectures). These are a genre apart from the sit-down
// interviews at /interviews/, so they get their own home (Adnan, 2026-07).
//
// A lecture is assigned to a series by its id prefix; anything unprefixed falls
// into the "historic" bucket of standalone addresses.

import { getCollection } from "astro:content";
import {
  type Entry,
  yearRangeOf,
  thumbOf,
} from "~/lib/video";

export interface LectureSeries {
  slug: string; // URL slug under /lectures/<slug>/
  title: string;
  blurb: string;
  items: Entry[];
  yearRange: string;
  thumb: string;
  order: number;
}

const SERIES_META: Record<
  string,
  { title: string; blurb: string; order: number; prefix?: string }
> = {
  "br-shenoy-memorial-lecture": {
    title: "B.R. Shenoy Memorial Lecture",
    blurb:
      "The annual lecture instituted in memory of B.R. Shenoy — the economist who dissented against the Second Five-Year Plan — delivered by leading economists and policymakers including Bibek Debroy, Montek Singh Ahluwalia, Duvvuri Subbarao, Surjit Bhalla, Arvind Panagariya, and Arvind Subramanian.",
    order: 1,
    prefix: "br-shenoy-memorial-lecture",
  },
  "indian-liberals-annual-lecture": {
    title: "Indian Liberals Annual Lecture",
    blurb:
      "The flagship annual address on the state and future of the liberal idea in India — delivered by Sagarika Ghose, J.P. Narayan, Gurcharan Das, and Praveen Chakravarty.",
    order: 2,
    prefix: "indian-liberals-annual-lecture",
  },
  historic: {
    title: "Historic lectures & addresses",
    blurb:
      "Recordings of addresses delivered decades before they reached the archive, from Nani Palkhivala's 1992 Union Budget address to Sudha Shenoy's lectures at the Mises Institute.",
    order: 3,
  },
};

function seriesFor(w: Entry): string {
  for (const [slug, meta] of Object.entries(SERIES_META)) {
    if (meta.prefix && w.id.startsWith(meta.prefix)) return slug;
  }
  return "historic";
}

export interface LectureShelves {
  series: LectureSeries[];
  total: number;
  yearSpan: string;
}

export async function getLectureSeries(): Promise<LectureShelves> {
  const lectures = await getCollection(
    "primary-works",
    (w) => !w.data.draft && w.data.work_type === "lecture",
  );

  const byslug = new Map<string, Entry[]>();
  for (const w of lectures) {
    const slug = seriesFor(w);
    (byslug.get(slug) ?? byslug.set(slug, []).get(slug)!).push(w);
  }

  const series = [...byslug.entries()]
    .map(([slug, items]) => {
      // Newest first for the annual series; historic addresses read oldest-first.
      items.sort((a, b) =>
        slug === "historic"
          ? (a.data.publication?.year ?? 9999) - (b.data.publication?.year ?? 9999)
          : (b.data.publication?.year ?? 0) - (a.data.publication?.year ?? 0),
      );
      return {
        slug,
        title: SERIES_META[slug].title,
        blurb: SERIES_META[slug].blurb,
        items,
        yearRange: yearRangeOf(items),
        thumb: thumbOf(items),
        order: SERIES_META[slug].order,
      };
    })
    .sort((a, b) => a.order - b.order);

  const total = lectures.length;
  const yearSpan = yearRangeOf(lectures);
  return { series, total, yearSpan };
}
