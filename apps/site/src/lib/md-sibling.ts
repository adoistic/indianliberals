// Markdown-sibling rendering helper.
//
// Every Tier-A detail page exposes a `<url>.md` sibling that returns the
// entry's raw markdown body + a frontmatter-derived header line. This is
// what AI agents fetch when they want the source-of-truth representation
// of a page without HTML, CSS, scripts, or layout chrome.
//
// Decision A4 in the engagement plan: build-time emission (static files
// on the Cloudflare CDN). Each per-collection route at
// `<col>/[slug].md.ts` calls `renderMdSibling()` to compose the response.

import type { CollectionEntry, CollectionKey } from 'astro:content';

const SITE_NAME = 'Indian Liberals';

interface ResolvedTitle {
  primary: string;
  subtitle?: string;
}

function resolveTitle(entry: CollectionEntry<CollectionKey>): ResolvedTitle {
  const data = entry.data as Record<string, unknown>;
  // multilingualTitle shape (primary-works, periodicals)
  if (data.title && typeof data.title === 'object' && 'main' in (data.title as object)) {
    const t = data.title as { main: string; subtitle?: string };
    return { primary: t.main, subtitle: t.subtitle };
  }
  // thinkerName / organisationName shape
  if (data.name && typeof data.name === 'object' && 'canonical' in (data.name as object)) {
    const n = data.name as { canonical: string };
    return { primary: n.canonical };
  }
  // Flat string title (musings, opinions, interviews, theprint-mirror)
  if (typeof data.title === 'string') {
    return { primary: data.title };
  }
  return { primary: entry.id };
}

/**
 * Compose the markdown response body. Includes:
 *   1. Title heading + subtitle
 *   2. Provenance footer (URL on the site + extracted_at if AI)
 *   3. The entry's raw markdown body
 *
 * Frontmatter is NOT included — agents can fetch the structured fields
 * from the MCP server or by parsing the HTML page. The .md sibling is
 * the body, not the metadata index.
 */
export function renderMdSibling(
  entry: CollectionEntry<CollectionKey>,
  collectionPath: string,
  siteOrigin: string,
): string {
  const title = resolveTitle(entry);
  const data = entry.data as Record<string, unknown>;
  const pageUrl = `${siteOrigin}/${collectionPath}/${entry.id}/`;
  const ai = data.ai as { extracted_at?: string; model?: string } | undefined;

  const lines: string[] = [];
  lines.push(`# ${title.primary}`);
  if (title.subtitle) lines.push(`*${title.subtitle}*`);
  lines.push('');
  lines.push(`<!-- Source: ${pageUrl} -->`);
  lines.push(`<!-- ${SITE_NAME} — ${collectionPath} -->`);
  if (ai?.extracted_at) {
    lines.push(`<!-- AI-extracted ${ai.extracted_at}${ai.model ? ` via ${ai.model}` : ''} -->`);
  }
  lines.push('');

  // Body — Astro's CollectionEntry exposes the raw markdown via `.body`.
  // For graph-edges (JSON loader), body is undefined; we serve frontmatter
  // as JSON-in-code-fence instead.
  if (typeof entry.body === 'string' && entry.body.length > 0) {
    lines.push(entry.body.trim());
  } else {
    // Fallback for entries whose body is empty (JSON loaders, stub MDs)
    lines.push('```json');
    lines.push(JSON.stringify(data, null, 2));
    lines.push('```');
  }
  lines.push('');

  return lines.join('\n');
}

/**
 * Build a Response object suitable for an Astro APIRoute.
 */
export function mdResponse(body: string): Response {
  return new Response(body, {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'Cache-Control': 'public, max-age=300, s-maxage=300',
    },
  });
}
