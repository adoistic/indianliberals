// Shared helpers for video-backed primary-works entries (work_type "interview"
// and "lecture"). Both /interviews/ and /lectures/ render the same card shape —
// a YouTube thumbnail, duration, and speaker byline lifted from the transcript
// body — so the extraction lives here and both grouping libs import it.

import type { CollectionEntry } from "astro:content";
import { DEFAULT_LOCALE } from "~/lib/i18n";

export type Entry = CollectionEntry<"primary-works">;

export function videoIdFor(w: Entry): string {
  const u = w.data.youtube_url ?? "";
  const m =
    u.match(/[?&]v=([a-zA-Z0-9_-]{6,15})/) ??
    u.match(/youtu\.be\/([a-zA-Z0-9_-]{6,15})/) ??
    u.match(/youtube\.com\/embed\/([a-zA-Z0-9_-]{6,15})/);
  return m ? m[1] : "";
}

export function thumbFor(w: Entry): string {
  const id = videoIdFor(w);
  return id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : "";
}

// Duration is baked into the transcript body header ("Duration: 1536.4s").
export function durationFor(w: Entry): string {
  const m = (w.body ?? "").match(/^Duration: (\d+)/m);
  if (!m) return "";
  const mins = Math.round(Number(m[1]) / 60);
  return mins < 1 ? "1 min" : `${mins} min`;
}

export function workHref(w: Entry): string {
  return w.data.language && w.data.language !== DEFAULT_LOCALE
    ? `/${w.data.language}/primary-works/${w.id}/`
    : `/primary-works/${w.id}/`;
}

export function speakerFor(
  w: Entry,
  thinkerById: Map<string, CollectionEntry<"thinkers">>,
): { name: string; thinkerId?: string } | null {
  const a = w.data.authors?.[0];
  if (a && "id" in a && thinkerById.has(a.id)) {
    return { name: thinkerById.get(a.id)!.data.name.canonical, thinkerId: a.id };
  }
  // Explicit figure name for speakers with no thinker profile.
  if (w.data.speaker_name) return { name: w.data.speaker_name };
  // Body byline: "**Name** (00:05):" — but not the generic diarization labels
  // "**Speaker**", "**Speaker 2**", or "**Narrator**".
  const m = (w.body ?? "").match(/^\*\*(?!Speaker\b|Narrator\b)([^*]+?)\*\* \(/m);
  return m ? { name: m[1].trim() } : null;
}

export function yearRangeOf(items: Entry[]): string {
  const years = items
    .map((w) => w.data.publication?.year)
    .filter((y): y is number => y != null);
  if (years.length === 0) return "";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

export function thumbOf(items: Entry[]): string {
  return items.map(thumbFor).find(Boolean) ?? "";
}

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
