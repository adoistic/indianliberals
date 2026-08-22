// Shared periodicals grouping used by /periodicals/ (series index) and
// /periodicals/[series]/ (one run's issues).
//
// Periodical issues live inside the primary-works collection with
// work_type: "periodical_issue" (the dedicated `periodicals` collection is
// reserved for a future migration). We group them into named runs (series).
//
// Series detection is keyed FIRST on the explicit publication.issuer_id /
// publisher_id fields (robust, editor-controllable via the CMS) and only
// falls back to title/slug heuristics for older issues that predate those
// fields (CCS round-2 feedback #8: prefer an explicit field over slug regex).

import { getCollection } from "astro:content";
import { isListed } from "./listable";
import type { CollectionEntry } from "astro:content";
import { DEFAULT_LOCALE } from "~/lib/i18n";
import { siteCopy, keyed, t } from "~/lib/site-copy";

export type Issue = CollectionEntry<"primary-works">;

// Organisation id (issuer or publisher) → series id. Multiple orgs can map to
// the same run (e.g. the Indian Libertarian was issued under several imprints).
const ORG_SERIES: Record<string, string> = {
  "the-indian-libertarian": "indian-libertarian",
  "libertarian-social-institute": "indian-libertarian",
  "libertarian-publishers": "indian-libertarian",
  "shetkari-sanghatana": "shetkari-sanghatak",
  "initiative-for-open-society": "khoj",
  khoj: "khoj",
  "liberal-times": "liberal-times",
  "indian-liberal-group": "indian-liberal-group",
  "freedom-first": "freedom-first",
  // The party's own newsletter — 167 issues, run monthly through the 1960s.
  // Without this they fall to "other", which is where genuine one-off press
  // clippings live, so the site's largest periodical run after Freedom First
  // was showing as an unnamed miscellany.
  "swatantra-party": "swatantra-newsletter",
};

export function seriesFor(w: Issue): string {
  const iss = w.data.publication?.issuer_id;
  const pub = w.data.publication?.publisher_id;
  if (iss && ORG_SERIES[iss]) return ORG_SERIES[iss];
  if (pub && ORG_SERIES[pub]) return ORG_SERIES[pub];
  // Fallbacks for issues without explicit issuer/publisher ids.
  const t = w.data.title.main;
  if (w.id.startsWith("khoj-") || /^khoj\b/i.test(t) || t.startsWith("ખોજ")) return "khoj";
  if (/indian libert/i.test(t)) return "indian-libertarian";
  if (/^swatantra\s+news\s*letter/i.test(t)) return "swatantra-newsletter";
  if (t === "Liberal Times" || (w.data.publication?.series ?? "").startsWith("Liberal Times")) return "liberal-times";
  if (w.id.startsWith("shetkari-sanghatak") || t.startsWith("शेतकरी संघटक")) return "shetkari-sanghatak";
  return "other";
}

export interface SeriesMeta {
  name: string;
  native?: string;
  blurb: string;
}

export const SERIES_META: Record<string, SeriesMeta> = {
  khoj: {
    name: "Khoj",
    native: "ખોજ",
    blurb:
      "A bi-monthly Gujarati liberal periodical published from Vadodara under the 'Pahel: Initiative for Open Society', explicitly anchored in the thought of Karl Popper and Friedrich Hayek. The first sustained attempt to debate free markets, poverty, and open-society ideas in Gujarati print.",
  },
  "swatantra-newsletter": {
    name: "Swatantra Newsletter",
    blurb:
      "The Swatantra Party's own newsletter, issued from its Bombay central office through the 1960s and into the 1970s: party circulars, conference reports, state-unit news and the leadership's running commentary on national politics, written for members rather than for the public.",
  },
  "indian-libertarian": {
    name: "The Indian Libertarian",
    blurb:
      "The Bombay fortnightly of the Libertarian Social Institute, published on the 1st and 15th of each month: classical-liberal and libertarian commentary on Indian politics and economics through the Nehruvian decades.",
  },
  "liberal-times": {
    name: "Liberal Times",
    blurb:
      "A South Asian liberal-affairs magazine published from New Delhi in the 1990s, carrying essays on liberal politics and policy across the region.",
  },
  "shetkari-sanghatak": {
    name: "Shetkari Sanghatak",
    native: "शेतकरी संघटक",
    blurb:
      "The Marathi organ of Sharad Joshi's Shetkari Sanghatana, the farmers' movement that argued the case for market freedom from the fields rather than the seminar room.",
  },
  "freedom-first": {
    name: "Freedom First",
    blurb:
      "The English-language liberal monthly founded in 1952 by Minoo Masani and the Democratic Research Service, one of India's longest-running liberal journals, making the case for individual liberty and the market economy through and beyond the licence-permit raj.",
  },
  "indian-liberal-group": {
    name: "The Liberal Position",
    blurb:
      "The newsletter of the Indian Liberal Group, the Mumbai-based network that carried the organised liberal tradition forward, circulating classical-liberal commentary to members and fellow travellers.",
  },
  other: {
    name: "Other periodicals",
    blurb: "Periodical issues in the archive that are not yet part of a named run.",
  },
};

// Display order for series. "other" always last.
export const SERIES_ORDER = [
  "indian-libertarian",
  "khoj",
  "shetkari-sanghatak",
  "liberal-times",
  "freedom-first",
  "swatantra-newsletter",
  "indian-liberal-group",
  // "other" is the sink and must stay last. A run missing from this list is
  // not merely unordered — getPeriodicalSeries filters by it, so its issues
  // render nowhere at all.
  "other",
];

// Issue year: publication.year is unreliable for digitised runs (it often
// records the scan/upload year). Prefer a 4-digit year embedded in the slug,
// which encodes the cover date.
export function issueYear(w: Issue): number | null {
  const m = w.id.match(/(18|19|20)\d{2}/);
  if (m) return Number(m[0]);
  return w.data.publication?.year ?? null;
}

// Human label for an issue inside its series: strip the series-name prefix from
// the title; fall back to a humanised slug remainder for masthead-only titles.
export function issueLabel(w: Issue, seriesId: string): string {
  const t = w.data.title.main;
  const meta = SERIES_META[seriesId];
  const stripped = t.replace(new RegExp(`^${meta.name}\\s*[:—-]\\s*`, "i"), "").trim();
  if (stripped && stripped !== t) return stripped;
  if (stripped === t && !["ખોજ", meta.name, meta.native].includes(t)) return t;
  const rest = w.id
    .replace(/^[a-z]+(-[a-z]+)*?-(?=(january|february|march|april|may|june|july|august|september|october|november|december|apr1))/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return rest || t;
}

export function workHref(w: Issue): string {
  return w.data.language && w.data.language !== DEFAULT_LOCALE
    ? `/${w.data.language}/primary-works/${w.id}/`
    : `/primary-works/${w.id}/`;
}

export interface SeriesGroup {
  id: string;
  meta: SeriesMeta;
  items: Issue[];
  yearRange: string;
  cover: string | null;
}

function yearRangeOf(items: Issue[]): string {
  const years = items.map(issueYear).filter((y): y is number => y !== null);
  if (years.length === 0) return "";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

// Pick a representative cover for a series card: the first issue (chronological)
// that has a cover image.
function coverOf(items: Issue[]): string | null {
  const withCover = items.find((w) => w.data.cover_image);
  return (withCover?.data.cover_image as string) ?? null;
}

// The CMS "shelves" entry can restate a run's name, native masthead or blurb
// (seed wins per key+field); the built-in SERIES_META stays the fallback.
function overlaidMeta(id: string, copy: Record<string, unknown>): SeriesMeta {
  const row = keyed(copy, "periodical_shelves", id);
  const base = SERIES_META[id];
  const native =
    typeof row.native === "string" && row.native.trim() ? (row.native as string) : base.native;
  return { name: t(row, "name", base.name), native, blurb: t(row, "blurb", base.blurb) };
}

// Group all periodical issues into ordered series. Each series' issues are
// sorted chronologically.
export async function getPeriodicalSeries(): Promise<SeriesGroup[]> {
  const copy = await siteCopy("shelves");
  const issues = await getCollection(
    "primary-works",
    (w) => isListed(w) && w.data.work_type === "periodical_issue",
  );
  const bySeries = new Map<string, Issue[]>();
  for (const w of issues) {
    const s = seriesFor(w);
    if (!bySeries.has(s)) bySeries.set(s, []);
    bySeries.get(s)!.push(w);
  }
  for (const [, list] of bySeries) {
    list.sort((a, b) => (issueYear(a) ?? 9999) - (issueYear(b) ?? 9999) || a.id.localeCompare(b.id));
  }
  return SERIES_ORDER.filter((s) => bySeries.has(s)).map((s) => {
    const items = bySeries.get(s)!;
    return { id: s, meta: overlaidMeta(s, copy), items, yearRange: yearRangeOf(items), cover: coverOf(items) };
  });
}
