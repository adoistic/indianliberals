// Shared series grouping used by /series/ (the index of runs) and
// /series/[series]/ (one run's items).
//
// A "series" here means a named NON-periodical run: a publisher's booklet
// series, an annual memorial lecture, a numbered occasional-paper run, a
// recurring yearly analysis. The two neighbouring surfaces cover the other
// shapes — /periodicals/ owns work_type "periodical_issue" (dated issues of a
// serial) and /lectures/ owns work_type "lecture" (video recordings). Nothing
// appears on two of the three.
//
// Membership is explicit: publication.series_id references the `series`
// collection, so editors control it from Sveltia rather than by slug regex.
// publication.series stays as the free-text label printed on the item.

import { getCollection, getEntry } from "astro:content";
import type { CollectionEntry } from "astro:content";
import { DEFAULT_LOCALE } from "~/lib/i18n";

export type SeriesEntry = CollectionEntry<"series">;
export type Item = CollectionEntry<"primary-works">;

export const KIND_LABEL: Record<string, string> = {
  booklet_series: "Booklet series",
  lecture_series: "Lecture series",
  occasional_papers: "Occasional papers",
  annual_analysis: "Annual analysis",
  multi_part_work: "Issued in parts",
};

// Display order on the index: the big runs first, then the lecture series,
// then the smaller numbered runs.
const KIND_ORDER = [
  "booklet_series",
  "lecture_series",
  "annual_analysis",
  "occasional_papers",
  "multi_part_work",
];

export function seriesIdOf(w: Item): string | null {
  const s = w.data.publication?.series_id;
  if (!s) return null;
  // A reference() resolves to { collection, id } at build time.
  return typeof s === "string" ? s : ((s as { id: string }).id ?? null);
}

export function ordinalOf(w: Item): number | null {
  return w.data.publication?.series_ordinal ?? null;
}

// Unlike a periodical issue — whose slug ends in its cover date — a print
// work's slug often carries a year that belongs to the TITLE, not the
// imprint ("indian-economic-development-1950-1980-..."). So trust the
// metadata pass's publication.year first, and only fall back to a year in the
// slug, taking the LAST one (a trailing date) rather than the first.
export function itemYear(w: Item): number | null {
  const y = w.data.publication?.year;
  if (y != null) return y;
  const all = w.id.match(/(18|19|20)\d{2}/g);
  return all ? Number(all[all.length - 1]) : null;
}

export function workHref(w: Item): string {
  return w.data.language && w.data.language !== DEFAULT_LOCALE
    ? `/${w.data.language}/primary-works/${w.id}/`
    : `/primary-works/${w.id}/`;
}

export interface SeriesGroup {
  entry: SeriesEntry;
  items: Item[];
  yearRange: string;
  cover: string | null;
  /** Ordinals actually present, ascending — only for numbered runs. */
  ordinals: number[];
  /** Missing numbers below the highest known ordinal. Editorial to-do list. */
  gaps: number[];
  children: SeriesGroup[];
}

function yearRangeOf(items: Item[]): string {
  const years = items.map(itemYear).filter((y): y is number => y !== null);
  if (years.length === 0) return "";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

function coverOf(items: Item[]): string | null {
  const withCover = items.find((w) => w.data.cover_image);
  return (withCover?.data.cover_image as string) ?? null;
}

/**
 * Sort a run for reading: by printed number when the run is numbered and the
 * number is known, otherwise chronologically. Items whose ordinal was withheld
 * (ambiguous) fall in with the date-ordered tail rather than pretending to a
 * position they can't be shown to hold.
 */
export function sortItems(items: Item[], numbered: boolean): Item[] {
  return [...items].sort((a, b) => {
    if (numbered) {
      const oa = ordinalOf(a);
      const ob = ordinalOf(b);
      if (oa !== null && ob !== null && oa !== ob) return oa - ob;
      if (oa !== null && ob === null) return -1;
      if (oa === null && ob !== null) return 1;
    }
    return (itemYear(a) ?? 9999) - (itemYear(b) ?? 9999) || a.id.localeCompare(b.id);
  });
}

function gapsIn(ordinals: number[]): number[] {
  if (ordinals.length === 0) return [];
  const have = new Set(ordinals);
  const hi = Math.max(...ordinals);
  const out: number[] = [];
  for (let i = 1; i < hi; i++) if (!have.has(i)) out.push(i);
  return out;
}

async function buildGroup(entry: SeriesEntry, byseries: Map<string, Item[]>): Promise<SeriesGroup> {
  const items = sortItems(byseries.get(entry.id) ?? [], entry.data.numbered);
  const ordinals = entry.data.numbered
    ? [...new Set(items.map(ordinalOf).filter((n): n is number => n !== null))].sort((a, b) => a - b)
    : [];
  return {
    entry,
    items,
    yearRange: yearRangeOf(items),
    cover: coverOf(items),
    ordinals,
    gaps: gapsIn(ordinals),
    children: [],
  };
}

/**
 * All series, nested one level (a memorial lecture sits under the booklet run
 * that printed it) and ordered by kind then size.
 */
export async function getSeries(): Promise<SeriesGroup[]> {
  const [entries, works] = await Promise.all([
    getCollection("series", (s) => !s.data.draft),
    getCollection("primary-works", (w) => !w.data.draft),
  ]);

  const byseries = new Map<string, Item[]>();
  for (const w of works) {
    const sid = seriesIdOf(w);
    if (!sid) continue;
    if (!byseries.has(sid)) byseries.set(sid, []);
    byseries.get(sid)!.push(w);
  }

  const groups = new Map<string, SeriesGroup>();
  for (const e of entries) groups.set(e.id, await buildGroup(e, byseries));

  const roots: SeriesGroup[] = [];
  for (const g of groups.values()) {
    const parent = g.entry.data.parent_series;
    if (parent && groups.has(parent)) groups.get(parent)!.children.push(g);
    else roots.push(g);
  }

  const bySize = (a: SeriesGroup, b: SeriesGroup) =>
    b.items.length - a.items.length || a.entry.data.name.localeCompare(b.entry.data.name);
  for (const g of groups.values()) g.children.sort(bySize);
  roots.sort(
    (a, b) =>
      KIND_ORDER.indexOf(a.entry.data.kind) - KIND_ORDER.indexOf(b.entry.data.kind) || bySize(a, b),
  );
  return roots;
}

/** Flattened list (roots + children), for getStaticPaths. */
export async function getAllSeriesGroups(): Promise<SeriesGroup[]> {
  const roots = await getSeries();
  const out: SeriesGroup[] = [];
  const walk = (g: SeriesGroup) => {
    out.push(g);
    g.children.forEach(walk);
  };
  roots.forEach(walk);
  return out;
}

/** The series a single work belongs to — used on the work detail page. */
export async function seriesOf(w: Item): Promise<SeriesEntry | null> {
  const sid = seriesIdOf(w);
  if (!sid) return null;
  try {
    return (await getEntry("series", sid)) ?? null;
  } catch {
    return null;
  }
}
