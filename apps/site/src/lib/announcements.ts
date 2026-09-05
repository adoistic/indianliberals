// The pop-up notice, chosen at build time and retired in the browser.
//
// An editor writes one entry per notice: a poster, a sentence, a link, and
// the moment the thing being announced is over. Two clocks decide whether a
// reader sees it, and they have to be different clocks:
//
//   The build clock picks the entry. Anything already finished, or switched
//   off, or not yet due, is left out of the HTML altogether, so an old
//   notice cannot come back through a stale page.
//
//   The reader's clock retires it. A static site is only as current as its
//   last build, and nobody is going to rebuild the archive at six on a
//   Friday evening because a lecture has started. The component carries the
//   start and end as epoch milliseconds and the browser hides the notice the
//   moment they have passed, whether or not anyone has touched the site.
//
// Editors type times the way they say them — 2026-09-18T18:00 — with no
// timezone, because asking a person to write +05:30 is asking for a mistake.
// A bare time is read as Indian Standard Time, which is where the readers
// and the events are. A time that carries its own offset is respected.

import { getCollection } from 'astro:content';

/** Indian Standard Time, in milliseconds ahead of UTC. */
const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;

export interface Announcement {
  id: string;
  headline: string;
  message: string;
  image?: string;
  linkUrl?: string;
  linkLabel: string;
  /** Epoch milliseconds. The browser shows nothing before this. */
  startsAt: number;
  /** Epoch milliseconds. The browser hides the notice after this. */
  endsAt: number;
}

/**
 * A date an editor typed, as epoch milliseconds.
 *
 * `2026-09-18T18:00` and `2026-09-18` are Indian Standard Time. Anything
 * ending in Z or carrying a +05:30-style offset is taken at its word. A
 * date alone means the end of that day, so "show it until the 18th" does
 * not blank the notice at one minute past midnight.
 */
export function parseWhen(value: string, endOfDayIfDateOnly = false): number {
  const text = value.trim();
  if (!text) return NaN;

  if (/(?:Z|[+-]\d{2}:?\d{2})$/i.test(text)) return Date.parse(text);

  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (dateOnly) {
    const naive = endOfDayIfDateOnly ? `${text}T23:59:59` : `${text}T00:00:00`;
    return Date.parse(`${naive}Z`) - IST_OFFSET_MS;
  }

  const naive = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(:\d{2})?$/.exec(text);
  if (naive) return Date.parse(`${text}${naive[3] ? '' : ':00'}Z`) - IST_OFFSET_MS;

  // Something we did not anticipate: let the platform try, rather than
  // silently dropping a notice an editor believes is scheduled.
  return Date.parse(text);
}

/**
 * The notice to put on every page, or nothing.
 *
 * When two notices overlap the one that ends soonest wins: it is the one
 * with the least time left to be seen in. Two pop-ups at once is never the
 * answer, so the rest simply wait their turn.
 */
export async function liveAnnouncement(now = Date.now()): Promise<Announcement | null> {
  const entries = await getCollection('announcements');

  const live = entries
    .filter((entry) => !entry.data.draft)
    .map((entry) => {
      const data = entry.data;
      const endsAt = parseWhen(data.ends, true);
      const startsAt = data.starts ? parseWhen(data.starts) : 0;
      return {
        id: entry.id,
        headline: data.headline,
        message: data.message,
        image: data.image,
        linkUrl: data.link_url?.trim() || undefined,
        linkLabel: data.link_label?.trim() || 'Read more',
        startsAt: Number.isFinite(startsAt) ? startsAt : 0,
        endsAt,
      } satisfies Announcement;
    })
    // A notice with an unreadable end date is a notice nobody can retire.
    .filter((notice) => Number.isFinite(notice.endsAt))
    .filter((notice) => notice.endsAt > now)
    .sort((a, b) => a.endsAt - b.endsAt);

  return live[0] ?? null;
}
