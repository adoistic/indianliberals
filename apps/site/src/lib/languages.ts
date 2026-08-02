// Browse the archive by the language a work was published in.
//
// CCS asked for a Languages sub-section with Hindi, Bengali and Marathi
// (round-3 feedback, 3.5). Built from the content rather than that fixed list
// of three: there are more Gujarati works than Hindi and Bengali put together,
// and the counts move every ingestion round.
//
// Three things here are easy to get wrong, and the first version got all
// three.
//
// 1. Which language field. `publication.language` is what the work is written
//    in and decides its shelf. The entry's own `language` describes the page,
//    defaults to English, and decides the URL, because
//    /<lang>/primary-works/<slug>/ is only built for entries whose own
//    language is not English. Link by the shelf's language instead and 56 of
//    the 78 Marathi works 404.
//
// 2. Periodical runs. 53 of the 78 Marathi items are issues of Shetkari
//    Sanghatak carrying the same title, so listing every issue produced 53
//    near-identical cards. Issues are grouped into their run here, the same
//    way /periodicals/ does it, and the run links there.
//
// 3. The script. Only 24 of the 109 non-English works carry native script in
//    `title.main`, but 67 have it in `title.original_script`. On a page about
//    language, the work should appear in its own script where we have it.

import { getCollection } from "astro:content";
import { LANG_NAMES, pathForEntry, type LangCode } from "./i18n";
import { resolveAuthorEntries } from "./resolve-author-entries";
import { seriesFor, SERIES_META, issueYear } from "./periodicals";

export interface LanguageWork {
  id: string;
  /** Native script where the record has it, otherwise whatever the title is. */
  title: string;
  /** The romanised form, when it differs from the title shown. */
  romanised?: string;
  translation?: string;
  year?: number;
  workType: string;
  cover?: string;
  byline: string;
  href: string;
}

export interface LanguageRun {
  id: string;
  name: string;
  native?: string;
  issueCount: number;
  yearRange: string;
  cover?: string;
  href: string;
}

export interface LanguageColumn {
  id: string;
  title: string;
  author?: string;
  year: number;
  href: string;
}

export interface DecadeGroup {
  start: number;
  label: string;
  works: LanguageWork[];
}

export interface LanguageShelf {
  code: LangCode;
  native: string;
  english: string;
  runs: LanguageRun[];
  issueCount: number;
  decades: DecadeGroup[];
  workCount: number;
  columns: LanguageColumn[];
  total: number;
  yearRange: string;
  workTypes: { type: string; count: number }[];
}

const UNDATED = 0;
const NATIVE_SCRIPT = /[ऀ-ॿ઀-૿ঀ-৿]/;

function rangeOf(years: number[]): string {
  if (!years.length) return "";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? `${lo}` : `${lo} to ${hi}`;
}

export async function getLanguageShelves(): Promise<LanguageShelf[]> {
  const works = await getCollection("primary-works", (w) => !w.data.draft);
  const columns = await getCollection("theprint-mirror", (p) => !p.data.draft);

  const worksByLang = new Map<LangCode, typeof works>();
  for (const w of works) {
    const code = w.data.publication?.language as LangCode | undefined;
    if (!code || code === "en" || !LANG_NAMES[code]) continue;
    const held = worksByLang.get(code);
    if (held) held.push(w);
    else worksByLang.set(code, [w]);
  }

  const columnsByLang = new Map<LangCode, typeof columns>();
  for (const c of columns) {
    const code = c.data.language as LangCode | undefined;
    if (!code || code === "en" || !LANG_NAMES[code]) continue;
    const held = columnsByLang.get(code);
    if (held) held.push(c);
    else columnsByLang.set(code, [c]);
  }

  const codes = new Set<LangCode>([...worksByLang.keys(), ...columnsByLang.keys()]);
  const shelves: LanguageShelf[] = [];

  for (const code of codes) {
    const all = worksByLang.get(code) ?? [];
    const issues = all.filter((w) => w.data.work_type === "periodical_issue");
    const standalone = all.filter((w) => w.data.work_type !== "periodical_issue");

    // ── Runs ────────────────────────────────────────────────────────────
    const runBuckets = new Map<string, typeof issues>();
    for (const w of issues) {
      const id = seriesFor(w);
      const held = runBuckets.get(id);
      if (held) held.push(w);
      else runBuckets.set(id, [w]);
    }
    const runs: LanguageRun[] = [...runBuckets.entries()]
      .map(([id, items]) => {
        const meta = SERIES_META[id];
        const years = items.map((w) => issueYear(w)).filter((y): y is number => !!y);
        return {
          id,
          name: meta?.name ?? id.replace(/-/g, " "),
          native: meta?.native,
          issueCount: items.length,
          yearRange: rangeOf(years),
          cover: items.find((w) => w.data.cover_image)?.data.cover_image,
          href: `/periodicals/${id}/`,
        };
      })
      .sort((a, b) => b.issueCount - a.issueCount);

    // ── Standalone works ────────────────────────────────────────────────
    const rendered: LanguageWork[] = [];
    for (const w of standalone) {
      const authors = await resolveAuthorEntries(w.data.authors, w.id);
      const main = w.data.title.main;
      const original = w.data.title.original_script;
      const showNative = original && NATIVE_SCRIPT.test(original);
      const title = showNative ? original : main;
      rendered.push({
        id: w.id,
        title,
        romanised: showNative && main !== original ? main : undefined,
        translation: w.data.title.translation,
        year: w.data.publication?.year ?? undefined,
        workType: w.data.work_type,
        cover: w.data.cover_image,
        byline: authors.map((a) => a.name).join(", "),
        // The work's OWN language, never the shelf's. See note 1 above.
        href: pathForEntry("primary-works", w.id, (w.data.language ?? "en") as LangCode),
      });
    }

    const byDecade = new Map<number, LanguageWork[]>();
    for (const w of rendered) {
      const bucket = w.year ? Math.floor(w.year / 10) * 10 : UNDATED;
      const held = byDecade.get(bucket);
      if (held) held.push(w);
      else byDecade.set(bucket, [w]);
    }
    const decades: DecadeGroup[] = [...byDecade.entries()]
      .sort((a, b) => (b[0] || -1) - (a[0] || -1))
      .map(([start, items]) => ({
        start,
        label: start === UNDATED ? "Undated" : `${start}s`,
        works: items.sort(
          (a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.title.localeCompare(b.title),
        ),
      }));

    const shelfColumns: LanguageColumn[] = (columnsByLang.get(code) ?? [])
      .sort((a, b) => +new Date(b.data.pubDate) - +new Date(a.data.pubDate))
      .map((c) => ({
        id: c.id,
        title: c.data.title,
        author: c.data.author_name,
        year: new Date(c.data.pubDate).getFullYear(),
        href: `/theprint-mirror/${c.id}/`,
      }));

    const typeCounts = new Map<string, number>();
    for (const w of rendered) typeCounts.set(w.workType, (typeCounts.get(w.workType) ?? 0) + 1);

    const years = [
      ...rendered.map((w) => w.year).filter((y): y is number => !!y),
      ...issues.map((w) => issueYear(w)).filter((y): y is number => !!y),
      ...shelfColumns.map((c) => c.year),
    ];

    shelves.push({
      code,
      native: LANG_NAMES[code].native,
      english: LANG_NAMES[code].english,
      runs,
      issueCount: issues.length,
      decades,
      workCount: rendered.length,
      columns: shelfColumns,
      total: all.length + shelfColumns.length,
      yearRange: rangeOf(years),
      workTypes: [...typeCounts.entries()]
        .map(([type, count]) => ({ type, count }))
        .sort((a, b) => b.count - a.count),
    });
  }

  return shelves.sort((a, b) => b.total - a.total || a.english.localeCompare(b.english));
}

/** "periodical_issue" reads as "periodical issue" in a card. */
export function prettyType(t: string): string {
  return t.replace(/_/g, " ");
}
