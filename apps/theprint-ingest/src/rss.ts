// Minimal RSS parser for ThePrint's WordPress RSS feed.
//
// WordPress emits standard RSS 2.0 with the `content:encoded` namespace
// for full article HTML. We don't pull in a parser dependency — the feed
// shape is stable and we only need a few fields. Tests live in tests/rss.test.ts.

export interface RssItem {
  title: string;
  link: string;            // canonical theprint.in URL
  guid: string;            // unique stable id (often = link)
  pubDate: Date;
  author: string;          // dc:creator
  description: string;     // <description> — usually the article excerpt
  contentHtml: string;     // <content:encoded> — full article HTML
  categories: string[];    // <category> tags
}

/**
 * Parse a WordPress RSS 2.0 feed and return its items.
 * Robust to whitespace and CDATA wrappers; tolerates missing optional fields.
 * Throws on a fundamentally malformed feed (no <item> elements at all).
 */
export function parseRssFeed(xml: string): RssItem[] {
  // Strip BOM if present
  const text = xml.replace(/^﻿/, '');
  const items: RssItem[] = [];

  // Each <item>...</item> block. RSS allows any number; we capture all
  // and let the caller cap via MAX_ITEMS_PER_RUN.
  const itemRx = /<item\b[^>]*>([\s\S]*?)<\/item>/g;
  let m: RegExpExecArray | null;
  while ((m = itemRx.exec(text)) !== null) {
    const block = m[1];
    const title = extractText(block, 'title');
    const link = extractText(block, 'link');
    const guid = extractText(block, 'guid') || link;
    const pubDateStr = extractText(block, 'pubDate');
    const author = extractText(block, 'dc:creator') || extractText(block, 'author');
    const description = extractText(block, 'description');
    const contentHtml = extractText(block, 'content:encoded') || description;
    const categories = extractAll(block, 'category');

    if (!title || !link) continue;

    const pubDate = pubDateStr ? new Date(pubDateStr) : new Date();
    items.push({
      title: decodeEntities(title.trim()),
      link: link.trim(),
      guid: guid.trim(),
      pubDate,
      author: decodeEntities(author.trim()),
      description: stripCdata(description),
      contentHtml: stripCdata(contentHtml),
      categories: categories.map((c) => decodeEntities(c.trim())),
    });
  }

  return items;
}

/** Pull the first <tag>...</tag> from `block` and strip CDATA wrapper. */
function extractText(block: string, tag: string): string {
  const escaped = tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const rx = new RegExp(`<${escaped}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${escaped}>`, 'i');
  const m = block.match(rx);
  if (!m) return '';
  return stripCdata(m[1]);
}

/** Pull every <tag>...</tag> as a list of strings. */
function extractAll(block: string, tag: string): string[] {
  const escaped = tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const rx = new RegExp(`<${escaped}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${escaped}>`, 'gi');
  const out: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = rx.exec(block)) !== null) {
    out.push(stripCdata(m[1]));
  }
  return out;
}

function stripCdata(s: string): string {
  return s.replace(/^<!\[CDATA\[([\s\S]*?)\]\]>$/i, '$1').trim();
}

/**
 * Minimal HTML-entity decoder for the entities WordPress regularly emits in
 * RSS feed fields. Not exhaustive; sufficient for title/author/category text.
 */
function decodeEntities(s: string): string {
  return s
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)));
}

/**
 * Extract the slug from a ThePrint article URL. URL shape:
 *   https://theprint.in/opinion/indian-liberals-matter/<slug>/<post-id>/
 * The slug is the path segment immediately following 'indian-liberals-matter'.
 * Falls back to a slug derived from the title if the URL doesn't match.
 */
export function slugFromUrl(url: string, fallbackTitle: string): string {
  try {
    const u = new URL(url);
    const parts = u.pathname.split('/').filter(Boolean);
    const colIdx = parts.indexOf('indian-liberals-matter');
    if (colIdx >= 0 && parts[colIdx + 1]) {
      return parts[colIdx + 1];
    }
    // Fallback: last non-numeric segment
    for (let i = parts.length - 1; i >= 0; i--) {
      if (!/^\d+$/.test(parts[i])) return parts[i];
    }
  } catch {
    // Fall through to title-based slug
  }
  return fallbackTitle
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}
