// WordPress REST API adapter for the Hindi ThePrint column.
//
// The Hindi "Indian Liberals Matter" category (hindi.theprint.in) does NOT
// expose a working RSS feed — /category/indianliberalsmatter/feed/ returns a
// 404 HTML page. The WP REST API does work, so Hindi is ingested from there
// instead and mapped onto the same RssItem shape the rest of the pipeline
// (rssItemToMarkdown) already understands.
//
//   GET {base}/wp-json/wp/v2/posts?categories={id}&per_page={n}&_embed
//
// Returns posts with rendered title/content/excerpt (Devanagari), an ASCII
// slug in the article URL, date_gmt, and — via _embed — the author name and
// category terms.

import type { RssItem } from './rss';

interface WpPost {
  link: string;
  date_gmt?: string;
  title?: { rendered?: string };
  excerpt?: { rendered?: string };
  content?: { rendered?: string };
  _embedded?: {
    author?: { name?: string }[];
    'wp:term'?: { taxonomy?: string; name?: string }[][];
  };
}

const UA = 'indianliberals-theprint-ingest/0.1 (+https://indianliberals.in)';

function decodeEntities(s: string): string {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;/g, "'")
    .replace(/&#8217;/g, '’')
    .replace(/&#8216;/g, '‘')
    .replace(/&#8220;/g, '“')
    .replace(/&#8221;/g, '”')
    .replace(/&#8211;/g, '–')
    .replace(/&#8230;/g, '…')
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)));
}

/**
 * Fetch a WordPress category's posts and map them to RssItem[].
 * `base` is the site origin (e.g. https://hindi.theprint.in), `categoryId` the
 * numeric WP category id (Hindi "Indian Liberals Matter" = 326160).
 */
export async function fetchWpRestItems(opts: {
  base: string;
  categoryId: number;
  max: number;
}): Promise<RssItem[]> {
  const perPage = Math.min(Math.max(opts.max, 1), 100);
  const url = `${opts.base.replace(/\/$/, '')}/wp-json/wp/v2/posts?categories=${opts.categoryId}&per_page=${perPage}&orderby=date&order=desc&_embed=1`;
  const resp = await fetch(url, {
    headers: { 'User-Agent': UA, Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new Error(`WP REST fetch failed: ${resp.status} ${resp.statusText}`);
  }
  const posts = (await resp.json()) as WpPost[];
  if (!Array.isArray(posts)) throw new Error('WP REST returned a non-array payload');

  return posts.map((p) => {
    const author = p._embedded?.author?.[0]?.name ?? '';
    const terms = (p._embedded?.['wp:term'] ?? []).flat();
    const categories = terms
      .filter((t) => t?.taxonomy === 'category' && t.name)
      .map((t) => decodeEntities(t.name as string));
    const contentHtml = p.content?.rendered ?? '';
    const description = p.excerpt?.rendered ?? '';
    return {
      title: decodeEntities(p.title?.rendered ?? ''),
      link: p.link,
      guid: p.link,
      // date_gmt has no timezone suffix; it is UTC, so append Z.
      pubDate: p.date_gmt ? new Date(`${p.date_gmt}Z`) : new Date(),
      author: decodeEntities(author),
      description,
      contentHtml: contentHtml || description,
      categories,
    } satisfies RssItem;
  });
}
