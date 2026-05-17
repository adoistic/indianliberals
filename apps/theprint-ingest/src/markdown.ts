// Generate a theprint-mirror markdown file from a parsed RSS item.
//
// The output MUST match the existing format (see any file under
// apps/site/src/content/theprint-mirror/ for a sample) so that the Astro
// content collection schema validates it without complaint.
//
// We do NOT attempt sophisticated HTML→markdown conversion — ThePrint's
// WordPress HTML uses well-formed <p>, <blockquote>, <em>, <strong>, <a>,
// <h2>/<h3> tags which round-trip well to markdown via the limited set of
// rules below. Edge cases (custom shortcodes, embeds) fall through as
// text and are flagged for editorial review via needs_review: true.

import type { RssItem } from './rss';

export interface MdEmitOpts {
  /** Today's date for the "mirrored on" footer line. */
  mirroredOnIso: string; // YYYY-MM-DD
  /** Article slug — used as the entry id. */
  slug: string;
}

export function rssItemToMarkdown(item: RssItem, opts: MdEmitOpts): string {
  const frontmatter = emitFrontmatter(item, opts);
  const body = emitBody(item, opts);
  return `${frontmatter}\n${body}\n`;
}

function emitFrontmatter(item: RssItem, opts: MdEmitOpts): string {
  // Themes derive from RSS <category> tags, slugged. The Indian Liberals
  // Matter column emits topical tags ("socialism", "free-markets", etc.)
  // that we map directly. Editorial can refine later via Sveltia.
  const themes = item.categories
    .map((c) => slugifyTheme(c))
    .filter((c, i, arr) => c && arr.indexOf(c) === i);

  const lines: string[] = ['---'];
  lines.push(`id: ${yamlString(opts.slug)}`);
  lines.push(`title: ${yamlString(item.title)}`);
  lines.push(`pubDate: ${item.pubDate.toISOString()}`);
  lines.push(`author_name: ${yamlString(item.author || 'ThePrint contributor')}`);
  lines.push(`theprint_url: ${yamlString(item.link)}`);
  lines.push(`themes: ${themes.length ? `[${themes.map(yamlString).join(', ')}]` : '[]'}`);
  lines.push(`related_thinkers: []`);
  lines.push(`related_works: []`);
  // Mirror stays noindex so theprint.in keeps SEO weight; the page is
  // still readable on-site and crawler-accessible to AI bots via the
  // .md sibling.
  lines.push(`noindex: true`);
  lines.push(`needs_review: true`);
  lines.push(`draft: false`);
  lines.push('---');
  return lines.join('\n');
}

function emitBody(item: RssItem, opts: MdEmitOpts): string {
  const attribution = `_Mirrored from [ThePrint](${item.link}) on ${opts.mirroredOnIso}. Originally published ${item.pubDate.toISOString().slice(0, 10)}. Author retains all rights; the canonical version on ThePrint should be cited. This mirror exists for AI-agent readability — search engines are asked not to index it (canonical SEO weight stays with ThePrint)._`;

  const heading = `# ${item.title}`;
  const body = htmlToMarkdown(item.contentHtml || item.description);

  return `${attribution}\n\n${heading}\n\n${body}`;
}

/**
 * Lightweight HTML→Markdown for the WordPress block subset ThePrint emits.
 * Not exhaustive — by design. Anything we don't translate is stripped to
 * text, which preserves the article content but loses some formatting.
 * needs_review: true in frontmatter signals "human should glance at this".
 */
function htmlToMarkdown(html: string): string {
  if (!html) return '';
  let s = html;

  // Block-level transforms first
  s = s.replace(/<h2\b[^>]*>([\s\S]*?)<\/h2>/gi, (_, x) => `\n\n## ${stripTags(x).trim()}\n\n`);
  s = s.replace(/<h3\b[^>]*>([\s\S]*?)<\/h3>/gi, (_, x) => `\n\n### ${stripTags(x).trim()}\n\n`);
  s = s.replace(/<blockquote\b[^>]*>([\s\S]*?)<\/blockquote>/gi, (_, x) => {
    const inner = stripTags(x).trim();
    return `\n\n${inner.split(/\n/).map((line) => `> ${line}`).join('\n')}\n\n`;
  });
  s = s.replace(/<p\b[^>]*>([\s\S]*?)<\/p>/gi, (_, x) => `\n\n${inlineHtmlToMarkdown(x).trim()}\n\n`);
  s = s.replace(/<br\s*\/?>/gi, '  \n');

  // Lists
  s = s.replace(/<ul\b[^>]*>([\s\S]*?)<\/ul>/gi, (_, list) => {
    const items = list.match(/<li\b[^>]*>([\s\S]*?)<\/li>/gi) || [];
    return '\n\n' + items.map((li: string) => `- ${inlineHtmlToMarkdown(li.replace(/<\/?li[^>]*>/gi, '')).trim()}`).join('\n') + '\n\n';
  });
  s = s.replace(/<ol\b[^>]*>([\s\S]*?)<\/ol>/gi, (_, list) => {
    const items = list.match(/<li\b[^>]*>([\s\S]*?)<\/li>/gi) || [];
    return '\n\n' + items.map((li: string, i: number) => `${i + 1}. ${inlineHtmlToMarkdown(li.replace(/<\/?li[^>]*>/gi, '')).trim()}`).join('\n') + '\n\n';
  });

  // Inline pass for anything outside the block tags above
  s = inlineHtmlToMarkdown(s);

  // Normalise whitespace
  s = s.replace(/\n{3,}/g, '\n\n').trim();
  return s;
}

function inlineHtmlToMarkdown(s: string): string {
  return s
    .replace(/<strong\b[^>]*>([\s\S]*?)<\/strong>/gi, '**$1**')
    .replace(/<b\b[^>]*>([\s\S]*?)<\/b>/gi, '**$1**')
    .replace(/<em\b[^>]*>([\s\S]*?)<\/em>/gi, '*$1*')
    .replace(/<i\b[^>]*>([\s\S]*?)<\/i>/gi, '*$1*')
    .replace(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, '[$2]($1)')
    .replace(/<code\b[^>]*>([\s\S]*?)<\/code>/gi, '`$1`')
    // Strip remaining tags — anything we didn't translate
    .replace(/<\/?[a-z][^>]*>/gi, '')
    // Decode core entities
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&hellip;/g, '…')
    .replace(/&mdash;/g, '—')
    .replace(/&ndash;/g, '–')
    .replace(/&rsquo;/g, '’')
    .replace(/&lsquo;/g, '‘')
    .replace(/&rdquo;/g, '”')
    .replace(/&ldquo;/g, '“')
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)));
}

function stripTags(s: string): string {
  return s.replace(/<\/?[a-z][^>]*>/gi, '');
}

/** Single-quote-wrapped YAML string, with internal quotes escaped. */
function yamlString(s: string): string {
  // Prefer double-quote wrapping (matches existing files) and escape \ and ".
  const escaped = s.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  return `"${escaped}"`;
}

function slugifyTheme(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}
