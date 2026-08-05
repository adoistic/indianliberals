// The website's own words, read from the `site` content collection.
//
// Every editable surface (homepage, navigation, section standfirsts, the
// about page, shelf blurbs, interface labels) has one entry under
// src/content/site/, edited from the CMS. Pages read fields through these
// helpers and pass their original hardcoded string as the fallback, so a
// missing entry or a half-saved field can never blank a page: the built-in
// wording simply comes back.

import { getCollection } from 'astro:content';

type Copy = Record<string, unknown>;

let loaded: Map<string, Copy> | null = null;

async function load(): Promise<Map<string, Copy>> {
  if (loaded) return loaded;
  const entries = await getCollection('site');
  loaded = new Map(entries.map((entry) => [entry.id, entry.data as Copy]));
  return loaded;
}

/** The whole entry for one surface, or an empty object when it is missing. */
export async function siteCopy(id: string): Promise<Copy> {
  return (await load()).get(id) ?? {};
}

/** The markdown body of a surface entry (the about page uses one). */
export async function siteBody(id: string): Promise<string | undefined> {
  const entries = await getCollection('site');
  const found = entries.find((entry) => entry.id === id);
  const body = (found as { body?: string } | undefined)?.body;
  return body && body.trim() ? body : undefined;
}

/** A string field, falling back to the built-in wording. */
export function t(copy: Copy, field: string, fallback: string): string {
  const value = copy[field];
  return typeof value === 'string' && value.trim() ? value : fallback;
}

/** A numeric field with a fallback. */
export function n(copy: Copy, field: string, fallback: number): number {
  const value = copy[field];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

/**
 * Fill `{token}` placeholders in an edited sentence, so copy like
 * "{works} works, from the Bengal Renaissance…" can carry live counts.
 * Unknown tokens are left as they are, which makes a typo visible rather
 * than silently swallowed.
 */
export function fmt(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{([a-z_]+)\}/g, (whole, name: string) =>
    name in vars ? String(vars[name]) : whole,
  );
}

/** One row of a keyed list (cards, shelves, doorways), by its key. */
export function keyed(copy: Copy, field: string, key: string): Copy {
  const list = copy[field];
  if (!Array.isArray(list)) return {};
  const row = list.find((item) => (item as Copy)?.key === key);
  return (row as Copy) ?? {};
}

/** An interface label from the `labels` entry's key/value pairs. */
export function label(labels: Copy, key: string, fallback: string): string {
  const list = labels.pairs;
  if (!Array.isArray(list)) return fallback;
  const row = list.find((item) => (item as Copy)?.key === key) as Copy | undefined;
  const value = row?.value;
  return typeof value === 'string' && value.trim() ? value : fallback;
}
