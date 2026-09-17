// Shared gallery grouping, used by /gallery/ and by the homepage mosaic.
//
// A photograph is one entry in the `gallery` collection. Albums are not
// entities: a photograph carries an `album` string, and every photograph with
// the same string is shown under that heading. The album order and each
// album's blurb are part of the gallery page's own copy (site collection,
// `section-gallery`, `albums` list), so an editor arranges the page from the
// same screen they write its introduction on.

import { getCollection } from "astro:content";
import type { CollectionEntry } from "astro:content";
import { keyed, siteCopy } from "~/lib/site-copy";

export type Photo = CollectionEntry<"gallery">;

/** Photographs the site should show at all. */
export async function getPhotos(): Promise<Photo[]> {
  return getCollection("gallery", (p) => !p.data.draft);
}

const NO_ORDER = 999_999;

/**
 * Order inside an album: by date, then by `order` among photographs sharing a
 * date, then by id. Undated photographs come last, since a date an editor
 * has not supplied yet should not push a dated one down the page.
 */
export function byDateThenOrder(a: Photo, b: Photo): number {
  const da = a.data.date ?? "￿";
  const db = b.data.date ?? "￿";
  if (da !== db) return da < db ? -1 : 1;
  return (a.data.order ?? NO_ORDER) - (b.data.order ?? NO_ORDER) || a.id.localeCompare(b.id);
}

/** Homepage order: by `order`, then by date, then by id. */
export function byOrderThenDate(a: Photo, b: Photo): number {
  return (
    (a.data.order ?? NO_ORDER) - (b.data.order ?? NO_ORDER) ||
    (a.data.date ?? "￿").localeCompare(b.data.date ?? "￿") ||
    a.id.localeCompare(b.id)
  );
}

/** The featured photographs, at most `limit`, for the homepage mosaic. */
export async function getFeaturedPhotos(limit = 7): Promise<Photo[]> {
  return (await getPhotos())
    .filter((p) => p.data.featured)
    .sort(byOrderThenDate)
    .slice(0, limit);
}

export interface Album {
  /** The album string the photographs carry; also the heading. */
  name: string;
  /** From the section-gallery copy, when an editor has written one. */
  blurb: string;
  photos: Photo[];
  /** "1987", "2014–2015", or "" when nothing is dated. */
  span: string;
}

/** The heading for photographs with no album at all. */
export const UNFILED = "More photographs";

function yearOf(p: Photo): number | null {
  const y = p.data.date?.slice(0, 4);
  return y ? Number(y) : null;
}

function spanOf(photos: Photo[]): string {
  const years = photos.map(yearOf).filter((y): y is number => y !== null);
  if (years.length === 0) return "";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

/**
 * Every album with at least one listed photograph, in the order the page's
 * copy gives them. Albums the copy does not mention follow, alphabetically,
 * and photographs with no album close the page under UNFILED.
 */
export async function getAlbums(): Promise<Album[]> {
  const [photos, copy] = await Promise.all([getPhotos(), siteCopy("section-gallery")]);

  const byName = new Map<string, Photo[]>();
  for (const p of photos) {
    const name = p.data.album?.trim() || UNFILED;
    if (!byName.has(name)) byName.set(name, []);
    byName.get(name)!.push(p);
  }

  const listed = Array.isArray(copy.albums)
    ? (copy.albums as { key?: string }[]).map((row) => row.key ?? "").filter(Boolean)
    : [];
  const rest = [...byName.keys()]
    .filter((name) => !listed.includes(name) && name !== UNFILED)
    .sort((a, b) => a.localeCompare(b));
  const names = [...listed.filter((name) => byName.has(name)), ...rest];
  if (byName.has(UNFILED)) names.push(UNFILED);

  return names.map((name) => {
    const list = [...byName.get(name)!].sort(byDateThenOrder);
    const row = keyed(copy, "albums", name);
    return {
      name,
      blurb: typeof row.blurb === "string" ? row.blurb : "",
      photos: list,
      span: spanOf(list),
    };
  });
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** "12 December 1987", "November 2016", "2022", or "" for no date. */
export function formatDate(date: string | undefined): string {
  if (!date) return "";
  const [y, m, d] = date.split("-");
  if (!m) return y;
  const month = MONTHS[Number(m) - 1] ?? "";
  if (!d) return `${month} ${y}`.trim();
  return `${Number(d)} ${month} ${y}`;
}
