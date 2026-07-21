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
  slug?: string;
  date_gmt?: string;
  title?: { rendered?: string };
  excerpt?: { rendered?: string };
  content?: { rendered?: string };
  _embedded?: {
    author?: { name?: string }[];
    'wp:term'?: { taxonomy?: string; name?: string }[][];
    'wp:featuredmedia'?: { source_url?: string }[];
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
      heroImage: p._embedded?.['wp:featuredmedia']?.[0]?.source_url || undefined,
    } satisfies RssItem;
  });
}

/**
 * Featured-image lookup for the RSS-sourced (English) column. The RSS feed
 * carries no images, but the same posts are exposed through the WP REST API
 * with `_embed`-ed featured media. Returns a slug → source_url map covering
 * the category's most recent posts; the ingest runner joins it onto RSS items
 * by slug. Failures should be non-fatal upstream — images are an enhancement,
 * not a requirement, so callers catch and continue without them.
 */
export async function fetchFeaturedImageMap(opts: {
  base: string;
  categoryId: number;
  max?: number;
}): Promise<Map<string, string>> {
  const perPage = Math.min(Math.max(opts.max ?? 100, 1), 100);
  const url =
    `${opts.base.replace(/\/$/, '')}/wp-json/wp/v2/posts` +
    `?categories=${opts.categoryId}&per_page=${perPage}&orderby=date&order=desc` +
    `&_fields=slug,link,_links,_embedded&_embed=wp:featuredmedia`;
  const resp = await fetch(url, {
    headers: { 'User-Agent': UA, Accept: 'application/json' },
  });
  if (!resp.ok) {
    throw new Error(`WP REST featured-media fetch failed: ${resp.status} ${resp.statusText}`);
  }
  const posts = (await resp.json()) as WpPost[];
  if (!Array.isArray(posts)) throw new Error('WP REST returned a non-array payload');

  const map = new Map<string, string>();
  for (const p of posts) {
    const src = p._embedded?.['wp:featuredmedia']?.[0]?.source_url;
    // Slug from the API field, falling back to the last URL segment.
    const slug = p.slug || (p.link ?? '').replace(/\/+$/, '').split('/').pop() || '';
    if (slug && src) map.set(slug, src);
  }
  return map;
}

/**
 * Last-resort image lookup: the article page's og:image meta tag. Some posts
 * have no WP featured media attached (seen on the Hindi column) but every
 * ThePrint article page still carries og:image for social cards. One fetch
 * per article — callers should only reach for this when the REST map came
 * up empty for a slug, and treat failures as "no image".
 */
export async function fetchOgImage(articleUrl: string): Promise<string | undefined> {
  const resp = await fetch(articleUrl, {
    headers: { 'User-Agent': UA, Accept: 'text/html' },
  });
  if (!resp.ok) return undefined;
  const html = await resp.text();
  const m =
    html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i) ??
    html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);
  return m?.[1] || undefined;
}
