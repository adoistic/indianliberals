// Browse the archive by the language a work was published in.
//
// CCS asked for a Languages sub-section with Hindi, Bengali and Marathi
// (round-3 feedback, 3.5). This is built from the content instead of that
// fixed list of three, for two reasons.
//
// First, Gujarati. There are more Gujarati works in the archive than Hindi and
// Bengali put together, so a Languages section that named Hindi and Bengali
// and left Gujarati out would be odd in a way a reader would notice.
//
// Second, the counts move. Every ingestion round adds works, and a hard-coded
// list of languages goes stale silently. Reading the corpus means the section
// is right today and stays right.
//
// The field is `publication.language`, which records the language the work
// itself is in. The entry's own top-level `language` is about the page, and
// defaults to English: the Vidyasagar essay has a Bengali title and an English
// summary, and belongs under Bengali. Using the wrong one of these two puts 56
// Marathi works in the English pile.

import { getCollection } from "astro:content";
import { LANG_NAMES, type LangCode } from "./i18n";

type Work = Awaited<ReturnType<typeof getCollection<"primary-works">>>[number];

export interface LanguageShelf {
  code: LangCode;
  native: string;
  english: string;
  items: Work[];
  yearRange: string;
}

function yearRangeOf(items: Work[]): string {
  const years = items
    .map((w) => w.data.publication?.year)
    .filter((y): y is number => typeof y === "number" && y > 1700);
  if (!years.length) return "";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? `${lo}` : `${lo} to ${hi}`;
}

/**
 * Every non-English language present in the archive, largest shelf first.
 * English is excluded: it is the bulk of the collection and has its own
 * doorways everywhere else on the site, so listing it here would say nothing.
 */
export async function getLanguageShelves(): Promise<LanguageShelf[]> {
  const works = await getCollection("primary-works", (w) => !w.data.draft);

  const byLang = new Map<LangCode, Work[]>();
  for (const w of works) {
    const code = w.data.publication?.language as LangCode | undefined;
    if (!code || code === "en") continue;
    if (!LANG_NAMES[code]) continue;
    const held = byLang.get(code);
    if (held) held.push(w);
    else byLang.set(code, [w]);
  }

  return [...byLang.entries()]
    .map(([code, items]) => {
      items.sort(
        (a, b) =>
          (a.data.publication?.year ?? 9999) - (b.data.publication?.year ?? 9999) ||
          a.data.title.main.localeCompare(b.data.title.main),
      );
      return {
        code,
        native: LANG_NAMES[code].native,
        english: LANG_NAMES[code].english,
        items,
        yearRange: yearRangeOf(items),
      };
    })
    .sort((a, b) => b.items.length - a.items.length || a.english.localeCompare(b.english));
}
