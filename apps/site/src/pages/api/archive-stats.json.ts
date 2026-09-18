import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { isCounted } from '~/lib/listable';
import { getPeriodicalSeries } from '~/lib/periodicals';
import { getSeries, countAll } from '~/lib/series';
import { jsonResponse } from '~/lib/agent-api';
import { workYear } from '~/lib/work-year';
import { workYear } from '~/lib/work-year';

// Every figure the archive's front door (archive.indianliberals.in, served by
// apps/archive-root) shows, measured from the content at build time. The
// Worker fetches this and renders the page from it, so the numbers follow
// every deploy and nobody regenerates a static page by hand again. Withheld
// works count here as they do everywhere (lib/listable.ts); drafts and
// untrusted records do not.

type Work = Awaited<ReturnType<typeof getCollection<'primary-works'>>>[number];

export const GET: APIRoute = async () => {
  const works = await getCollection('primary-works', isCounted);
  const thinkers = await getCollection('thinkers', (t) => !t.data.draft);
  const orgs = await getCollection('organisations', (o) => !o.data.draft);
  const musings = await getCollection('musings', (m) => !m.data.draft);
  const opinions = await getCollection('opinions', (o) => !o.data.draft);

  // Pages: the measured extent of the scans.
  const pageCounts = works
    .map((w) => w.data.physical?.pages_total ?? w.data.physical?.page_count ?? 0)
    .filter((n) => n > 0)
    .sort((a, b) => a - b);
  const pages = pageCounts.reduce((s, n) => s + n, 0);
  const medianPages = pageCounts.length ? pageCounts[Math.floor(pageCounts.length / 2)] : 0;

  const pdfs = new Set(works.map((w) => w.data.pdf_url).filter(Boolean)).size;
  const covers = works.filter((w) => w.data.cover_image).length;

  // Years and the decade histogram.
  const dated = works
    .map((w) => ({ w, y: workYear(w) }))
    .filter((x): x is { w: Work; y: number } => x.y !== null);
  const years = dated.map((x) => x.y);
  const earliest = years.length ? Math.min(...years) : null;
  const latest = years.length ? Math.max(...years) : null;
  const earliestWork = dated.find((x) => x.y === earliest)?.w;
  const byDecade = new Map<number, number>();
  for (const { y } of dated) {
    const d = Math.floor(y / 10) * 10;
    byDecade.set(d, (byDecade.get(d) ?? 0) + 1);
  }
  const decades = [...byDecade.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([decade, count]) => ({ decade, count }));

  // The longest single work.
  const longest = works
    .filter((w) => (w.data.physical?.pages_total ?? 0) > 0)
    .sort((a, b) => (b.data.physical!.pages_total ?? 0) - (a.data.physical!.pages_total ?? 0))[0];

  // Most-published voices: works per thinker, by the bare-string author form.
  const nameOf = new Map(thinkers.map((t) => [t.id, t.data.name.canonical]));
  const perAuthor = new Map<string, number>();
  for (const w of works) {
    for (const a of w.data.authors ?? []) {
      const id = typeof a === 'string' ? a : (a as { collection?: string; id: string }).collection === 'thinkers' ? (a as { id: string }).id : null;
      if (!id || !nameOf.has(id)) continue;
      perAuthor.set(id, (perAuthor.get(id) ?? 0) + 1);
    }
  }
  const voices = [...perAuthor.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([id, count]) => ({ id, name: nameOf.get(id)!, count }));

  // Languages of the documents themselves.
  const LANG_NAMES: Record<string, string> = { en: 'English', hi: 'Hindi', gu: 'Gujarati', mr: 'Marathi', bn: 'Bengali' };
  const perLang = new Map<string, number>();
  for (const w of works) {
    const l = w.data.publication?.language ?? w.data.language ?? 'en';
    perLang.set(l, (perLang.get(l) ?? 0) + 1);
  }
  const languages = [...perLang.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([code, count]) => ({ code, name: LANG_NAMES[code] ?? code, count }));

  // The largest runs, magazines and print series together.
  const periodicals = (await getPeriodicalSeries()).filter((g) => g.id !== 'other');
  const series = await getSeries();
  const runs = [
    ...periodicals.map((g) => ({ name: g.meta.name, count: g.total, href: `/periodicals/${g.id}/` })),
    ...series.map((g) => ({ name: g.entry.data.name, count: countAll(g), href: `/series/${g.entry.id}/` })),
  ]
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  return jsonResponse({
    generated_at: new Date().toISOString(),
    works: works.length,
    pages,
    median_pages: medianPages,
    pdfs,
    covers,
    earliest,
    latest,
    earliest_work: earliestWork
      ? { id: earliestWork.id, title: earliestWork.data.title.main, translation: earliestWork.data.title.translation ?? null }
      : null,
    decades,
    longest: longest ? { id: longest.id, title: longest.data.title.main, pages: longest.data.physical!.pages_total } : null,
    voices,
    languages,
    runs,
    thinkers: thinkers.filter((t) => ['core', 'extended'].includes(t.data.canon_status)).length,
    organisations: orgs.length,
    musings: musings.length,
    opinions: opinions.length,
  });
};
