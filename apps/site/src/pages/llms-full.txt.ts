import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

// /llms-full.txt — every Tier-A entry's full markdown body, plus every
// Tier-B entry's metadata + AI summary. Agents that want the whole corpus
// in one request hit this endpoint; agents that want a curated catalogue
// hit /llms.txt instead. See AGENTS.md for the schema + citation rules.
//
// File size: ~5–10 MB once the corpus is fully extracted. Served gzipped
// from the Cloudflare CDN — that drops it to ~1–2 MB on the wire.
//
// Build-time generation per engagement-plan decision A4. No runtime cost.

export const GET: APIRoute = async ({ site }) => {
  const origin = site!.origin;

  // Pull everything in parallel — Astro caches getCollection internally.
  const [thinkers, orgs, musings, opinions, interviews, works, theprint] = await Promise.all([
    getCollection('thinkers', (e) => !e.data.draft && e.data.language === 'en'),
    getCollection('organisations', (e) => !e.data.draft && e.data.language === 'en'),
    getCollection('musings', (e) => !e.data.draft && e.data.language === 'en'),
    getCollection('opinions', (e) => !e.data.draft && e.data.language === 'en'),
    getCollection('interviews', (e) => !e.data.draft && e.data.language === 'en'),
    getCollection('primary-works', (e) => !e.data.draft && e.data.language === 'en'),
    getCollection('theprint-mirror', (e) => !e.data.draft && e.data.language === 'en'),
  ]);

  const lines: string[] = [];
  lines.push('# Indian Liberals — full corpus dump');
  lines.push('');
  lines.push('> Every Tier-A entry in full, plus every Tier-B summary, one file.');
  lines.push('> See /AGENTS.md for the citation rules and tier system.');
  lines.push(`> Generated at ${new Date().toISOString()}.`);
  lines.push('');
  lines.push('---');
  lines.push('');

  function appendEntry(
    sectionLabel: string,
    entry: { id: string; body?: string; data: Record<string, unknown> },
    collectionPath: string,
  ) {
    const data = entry.data;
    let title = entry.id;
    if (data.title && typeof data.title === 'object' && 'main' in (data.title as object)) {
      title = (data.title as { main: string }).main;
    } else if (data.name && typeof data.name === 'object' && 'canonical' in (data.name as object)) {
      title = (data.name as { canonical: string }).canonical;
    } else if (typeof data.title === 'string') {
      title = data.title;
    }
    const url = `${origin}/${collectionPath}/${entry.id}/`;
    lines.push(`## [${sectionLabel}] ${title}`);
    lines.push(`URL: ${url}`);
    if (typeof data.summary === 'string' && data.summary.length > 0) {
      lines.push('');
      lines.push('### Summary');
      lines.push(data.summary);
    }
    if (typeof entry.body === 'string' && entry.body.trim().length > 0) {
      lines.push('');
      lines.push('### Body');
      lines.push(entry.body.trim());
    }
    lines.push('');
    lines.push('---');
    lines.push('');
  }

  // Thinkers (profiles)
  lines.push('# Thinkers');
  lines.push('');
  for (const t of thinkers) appendEntry('Thinker', t, 'thinkers');

  // Organisations
  lines.push('# Organisations');
  lines.push('');
  for (const o of orgs) appendEntry('Organisation', o, 'organisations');

  // Musings (excerpts)
  lines.push('# Musings');
  lines.push('');
  for (const m of musings) appendEntry('Musing', m, 'musings');

  // Opinions
  lines.push('# Opinions');
  lines.push('');
  for (const op of opinions) appendEntry('Opinion', op, 'opinions');

  // Interviews
  lines.push('# Interviews');
  lines.push('');
  for (const i of interviews) appendEntry('Interview', i, 'interviews');

  // ThePrint mirror — included for agent readability; canonical version is on theprint.in
  lines.push('# ThePrint mirror');
  lines.push('> Canonical version on theprint.in. Cite the theprint_url field, not this mirror.');
  lines.push('');
  for (const p of theprint) appendEntry('ThePrint', p, 'theprint-mirror');

  // Primary works (Tier B — summary only)
  lines.push('# Primary works (Tier B — summaries only)');
  lines.push('> Tier B: cite to the PDF, not as if the body text was read.');
  lines.push('');
  for (const w of works) appendEntry('Primary work', w, 'primary-works');

  return new Response(lines.join('\n'), {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=600, s-maxage=600',
    },
  });
};
