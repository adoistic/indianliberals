// Builders for the /api/*.json agent endpoints — the machine-readable
// data plane behind mcp.indianliberals.in.
//
// Everything here is derived from the content collections at build time,
// so the MCP server (apps/mcp — a thin stateless Worker that fetches
// these endpoints) automatically reflects every content addition on the
// next deploy. Adding a work, thinker, or musing requires NO change to
// the MCP: these endpoints regenerate, the Worker re-reads them.
//
// Coverage matches the .md siblings: English-canonical entries only
// (translations are discoverable via each entry's `translations` map).

import { getCollection, type CollectionEntry } from 'astro:content';
import { resolveAuthorEntries } from './resolve-author-entries';
import { pathForEntry, type LangCode } from './i18n';

// ─── Shared helpers ────────────────────────────────────────────────────

type AnyData = Record<string, any>;

const notDraftEn = (e: { data: AnyData }) =>
  !e.data.draft && (e.data.language ?? 'en') === 'en';

/** Tier assignment. Interviews carry full transcripts → Tier A. */
export function tierForWorkType(workType: string): 'A' | 'B' {
  return workType === 'interview' ? 'A' : 'B';
}

/** Cheap markdown → plain text for snippets and the search index. */
export function stripMarkdown(md: string): string {
  return md
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/[*_`~]/g, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function snippet(text: string | undefined, max = 1200): string {
  if (!text) return '';
  const plain = stripMarkdown(text);
  return plain.length <= max ? plain : plain.slice(0, max).replace(/\s\S*$/, '') + '…';
}

function urlFor(collection: string, id: string, language: LangCode = 'en') {
  return pathForEntry(collection, id, language);
}

function mdUrlFor(collection: string, id: string) {
  return `/${collection}/${id}.md`;
}

export function jsonResponse(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=300, s-maxage=300',
      'Access-Control-Allow-Origin': '*',
    },
  });
}

// ─── Works catalogue ───────────────────────────────────────────────────

export async function getEnWorks() {
  return getCollection('primary-works', notDraftEn);
}

export async function buildWorkCard(w: CollectionEntry<'primary-works'>) {
  const d = w.data as AnyData;
  const authors = await resolveAuthorEntries(d.authors, w.id);
  return {
    id: w.id,
    title: {
      main: d.title.main,
      ...(d.title.subtitle ? { subtitle: d.title.subtitle } : {}),
      ...(d.title.original_script ? { original_script: d.title.original_script } : {}),
      ...(d.title.translit ? { translit: d.title.translit } : {}),
      ...(d.title.translation ? { translation: d.title.translation } : {}),
    },
    work_type: d.work_type,
    tier: tierForWorkType(d.work_type),
    authors: authors.map((a) => ({ kind: a.kind, id: a.id, name: a.name })),
    year: d.publication?.year ?? null,
    language: d.publication?.language ?? 'en',
    ...(d.publication?.series ? { series: d.publication.series } : {}),
    themes: d.themes ?? [],
    ...(d.pdf_url ? { pdf_url: d.pdf_url } : {}),
    ...(d.cover_image ? { cover_image: d.cover_image } : {}),
    url: urlFor('primary-works', w.id),
    md_url: mdUrlFor('primary-works', w.id),
    has_summary: Boolean(d.summary || d.ai_summary),
    has_transcript: d.work_type === 'interview' && (w.body ?? '').trim().length > 0,
    ...(d.youtube_url ? { youtube_url: d.youtube_url } : {}),
  };
}

export async function buildWorkDetail(w: CollectionEntry<'primary-works'>) {
  const d = w.data as AnyData;
  const card = await buildWorkCard(w);
  const keyPoints: string[] =
    (d.ai_key_points?.length ? d.ai_key_points : d.key_points) ?? [];
  return {
    ...card,
    summary: d.summary || d.ai_summary || null,
    key_points: keyPoints,
    ...(d.description ? { description: d.description } : {}),
    publication: d.publication ?? {},
    ...(d.physical?.pages_total ? { pages_total: d.physical.pages_total } : {}),
    provenance: d.provenance ?? {},
    rights: d.rights ?? null,
    ...(d.identifiers ? { identifiers: d.identifiers } : {}),
    contributors: (d.contributors ?? []).map((c: AnyData) => ({
      ...(c.thinker ? { thinker_id: c.thinker.id } : {}),
      ...(c.thinker_unresolved ? { name_unresolved: c.thinker_unresolved } : {}),
      role: c.role,
      ...(typeof c.toc_index === 'number' ? { toc_index: c.toc_index } : {}),
    })),
    ...(d.toc?.entries?.length ? { toc: d.toc.entries } : {}),
    ...(d.essays_summarized?.length ? { essays_summarized: d.essays_summarized } : {}),
    related_thinkers: (d.related_thinkers ?? []).map((r: AnyData) => r.id ?? r),
    related_works: d.related_works ?? [],
    ...(d.translations ? { translations: d.translations } : {}),
    paragraph_ids: d.paragraph_ids ?? [],
    ...(d.clean_markdown_url ? { clean_markdown_url: d.clean_markdown_url } : {}),
    needs_review: d.needs_review ?? false,
  };
}

// ─── Thinkers ──────────────────────────────────────────────────────────

export async function buildThinkers() {
  const thinkers = await getCollection('thinkers', notDraftEn);
  return thinkers
    .map((t) => {
      const d = t.data as AnyData;
      return {
        id: t.id,
        name: {
          canonical: d.name.canonical,
          ...(d.name.sort ? { sort: d.name.sort } : {}),
          ...(d.name.also_known_as?.length ? { also_known_as: d.name.also_known_as } : {}),
        },
        birth_year: d.birth_year ?? null,
        death_year: d.death_year ?? null,
        tradition: d.tradition,
        canon_status: d.canon_status,
        featured: d.featured ?? false,
        vocations: d.vocations ?? [],
        themes: d.themes ?? [],
        affiliations: d.affiliations ?? [],
        url: urlFor('thinkers', t.id),
        md_url: mdUrlFor('thinkers', t.id),
        bio_snippet: snippet(t.body, 300),
      };
    })
    .sort((a, b) => (a.name.sort ?? a.name.canonical).localeCompare(b.name.sort ?? b.name.canonical));
}

// ─── Search index (all content kinds, tier-flagged) ────────────────────

export interface SearchDoc {
  key: string; // "<collection>:<id>" — the stable document handle
  collection: string;
  id: string;
  tier: 'A' | 'B';
  kind: string;
  title: string;
  url: string;
  md_url: string | null;
  authors: string[];
  themes: string[];
  year: number | null;
  text: string;
}

export async function buildSearchIndex(): Promise<SearchDoc[]> {
  const docs: SearchDoc[] = [];

  const thinkers = await getCollection('thinkers', notDraftEn);
  for (const t of thinkers) {
    const d = t.data as AnyData;
    docs.push({
      key: `thinkers:${t.id}`,
      collection: 'thinkers',
      id: t.id,
      tier: 'A',
      kind: 'thinker_profile',
      title: d.name.canonical,
      url: urlFor('thinkers', t.id),
      md_url: mdUrlFor('thinkers', t.id),
      authors: [],
      themes: d.themes ?? [],
      year: d.birth_year ?? null,
      text: snippet(t.body),
    });
  }

  const orgs = await getCollection('organisations', notDraftEn);
  for (const o of orgs) {
    const d = o.data as AnyData;
    docs.push({
      key: `organisations:${o.id}`,
      collection: 'organisations',
      id: o.id,
      tier: 'A',
      kind: `organisation_${d.type}`,
      title: d.name.canonical ?? d.name.main ?? o.id,
      url: urlFor('organisations', o.id),
      md_url: mdUrlFor('organisations', o.id),
      authors: [],
      themes: d.ideology ?? [],
      year: d.founded_year ?? null,
      text: snippet([d.description ?? '', o.body ?? ''].join(' ')),
    });
  }

  const musings = await getCollection('musings', notDraftEn);
  for (const m of musings) {
    const d = m.data as AnyData;
    docs.push({
      key: `musings:${m.id}`,
      collection: 'musings',
      id: m.id,
      tier: 'A',
      kind: d.kind ?? 'excerpt',
      title: d.title,
      url: urlFor('musings', m.id),
      md_url: mdUrlFor('musings', m.id),
      authors: d.author ? [d.author.id] : [],
      themes: d.themes ?? [],
      year: d.pubDate ? new Date(d.pubDate).getFullYear() : null,
      text: snippet(m.body),
    });
  }

  const opinions = await getCollection('opinions', notDraftEn);
  for (const o of opinions) {
    const d = o.data as AnyData;
    docs.push({
      key: `opinions:${o.id}`,
      collection: 'opinions',
      id: o.id,
      tier: 'A',
      kind: d.kind ?? 'opinion',
      title: d.title,
      url: urlFor('opinions', o.id),
      md_url: mdUrlFor('opinions', o.id),
      authors: [d.author_name].filter(Boolean),
      themes: d.themes ?? [],
      year: d.pubDate ? new Date(d.pubDate).getFullYear() : null,
      text: snippet(o.body),
    });
  }

  const works = await getEnWorks();
  for (const w of works) {
    const d = w.data as AnyData;
    const authors = await resolveAuthorEntries(d.authors, w.id);
    const tier = tierForWorkType(d.work_type);
    docs.push({
      key: `primary-works:${w.id}`,
      collection: 'primary-works',
      id: w.id,
      tier,
      kind: d.work_type,
      title: d.title.main,
      url: urlFor('primary-works', w.id),
      md_url: mdUrlFor('primary-works', w.id),
      authors: authors.map((a) => a.name),
      themes: d.themes ?? [],
      year: d.publication?.year ?? null,
      text:
        tier === 'A'
          ? snippet([d.description ?? '', w.body ?? ''].join(' '))
          : snippet(d.summary || d.ai_summary || d.description),
    });
  }

  const theprint = await getCollection('theprint-mirror', notDraftEn);
  for (const p of theprint) {
    const d = p.data as AnyData;
    docs.push({
      key: `theprint-mirror:${p.id}`,
      collection: 'theprint-mirror',
      id: p.id,
      tier: 'A',
      kind: 'theprint_column',
      title: d.title,
      url: urlFor('theprint-mirror', p.id),
      md_url: mdUrlFor('theprint-mirror', p.id),
      authors: [d.author_name].filter(Boolean),
      themes: d.themes ?? [],
      year: d.pubDate ? new Date(d.pubDate).getFullYear() : null,
      text: snippet(d.ai_summary || p.body),
    });
  }

  return docs;
}

// ─── Meta ──────────────────────────────────────────────────────────────

export async function buildMeta(siteOrigin: string) {
  const [works, thinkers, orgs, musings, opinions, theprint] = await Promise.all([
    getEnWorks(),
    getCollection('thinkers', notDraftEn),
    getCollection('organisations', notDraftEn),
    getCollection('musings', notDraftEn),
    getCollection('opinions', notDraftEn),
    getCollection('theprint-mirror', notDraftEn),
  ]);
  const interviews = works.filter((w) => w.data.work_type === 'interview');
  const periodicalIssues = works.filter((w) => w.data.work_type === 'periodical_issue');
  return {
    name: 'Indian Liberals — agent data plane',
    site: siteOrigin,
    generated_at: new Date().toISOString(),
    schema_version: 1,
    counts: {
      primary_works: works.length,
      interviews: interviews.length,
      periodical_issues: periodicalIssues.length,
      thinkers: thinkers.length,
      organisations: orgs.length,
      musings: musings.length,
      opinions: opinions.length,
      theprint_mirror: theprint.length,
    },
    endpoints: [
      '/api/meta.json',
      '/api/works.json',
      '/api/works/<id>.json',
      '/api/thinkers.json',
      '/api/search-index.json',
      '/api/cross-links.json',
    ],
    docs: ['/AGENTS.md', '/llms.txt', '/llms-full.txt'],
    mcp: 'https://mcp.indianliberals.in/mcp',
  };
}
