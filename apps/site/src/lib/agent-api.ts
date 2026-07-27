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
    ...(d.publication?.series_id
      ? {
          series_id:
            typeof d.publication.series_id === 'string'
              ? d.publication.series_id
              : d.publication.series_id.id,
        }
      : {}),
    ...(d.publication?.series_ordinal != null
      ? { series_ordinal: d.publication.series_ordinal }
      : {}),
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

/** Pull the bullets out of a `## <name>` section of a work's markdown body. */
function bodyBullets(body: string, name: string): string[] {
  // `$(?![\s\S])` for end-of-input, not `$`. Under the `m` flag `$` matches the
  // end of the *first* line, so the lazy capture stopped immediately and every
  // section came back empty.
  const section = new RegExp(
    `^##\\s+${name}\\s*$([\\s\\S]*?)(?=^##\\s|$(?![\\s\\S]))`,
    'm',
  ).exec(body ?? '');
  if (!section) return [];
  return section[1]
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => line.slice(2).trim())
    .filter(Boolean);
}

/**
 * The per-article summaries under a multi-article work's `## Essays` region.
 *
 * These exist for 780 works and were, until now, unreachable through any
 * documented tool: `read_clean_content` refuses Tier B and `get_work_metadata`
 * never carried them, while the site served them all along at the `md_url` this
 * same response hands out. So an agent was told the text did not exist and
 * given its address in the same breath. Surfacing them here closes that, and
 * the field name says plainly what they are, because they are summary prose
 * written by our extraction pipeline and not transcribed source text.
 */
function articleSummaries(body: string): { heading: string; byline: string | null; summary: string }[] {
  const out: { heading: string; byline: string | null; summary: string }[] = [];
  const chunks = (body ?? '').split(/^### /m).slice(1);
  for (const chunk of chunks) {
    const lines = chunk.split('\n');
    const heading = (lines[0] ?? '').trim();
    if (!heading) continue;
    let byline: string | null = null;
    let start = 1;
    for (let i = 1; i < Math.min(4, lines.length); i += 1) {
      const match = /^\*By\s+(.+?)\*\s*$/.exec(lines[i].trim());
      if (match) {
        byline = match[1].trim();
        start = i + 1;
        break;
      }
      if (lines[i].trim()) break;
    }
    const summary = lines
      .slice(start)
      .filter((line) => !line.trim().startsWith('- '))
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
    out.push({ heading, byline, summary });
  }
  return out;
}

export async function buildWorkDetail(w: CollectionEntry<'primary-works'>) {
  const d = w.data as AnyData;
  const card = await buildWorkCard(w);
  const body = w.body ?? '';
  // The digests live in the markdown body rather than frontmatter for most
  // works, which left `key_points` empty in all but 121 of 1,531 API responses.
  const keyPoints: string[] =
    (d.ai_key_points?.length ? d.ai_key_points : d.key_points)?.length
      ? (d.ai_key_points?.length ? d.ai_key_points : d.key_points)
      : bodyBullets(body, 'Key points');
  const articles = articleSummaries(body);
  return {
    ...card,
    summary: d.summary || d.ai_summary || null,
    key_points: keyPoints,
    ...(articles.length ? { article_summaries: articles } : {}),
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
  /**
   * Whether this document actually carries quotable prose.
   *
   * Tier A promises paragraph-stable citations, but 436 of 695 thinker profiles
   * and 49 of 52 organisation pages are frontmatter only: the rendered page is a
   * block of JSON with no paragraphs, so there is no `#p-xxxxxx` anchor to cite
   * and never was. Tier is about what an agent MAY do with a document; this is
   * about whether the document gives it anything to do it with. An agent should
   * not promise a paragraph citation for a document where `citable` is false.
   */
  citable: boolean;
}

/** A document is citable when it has body prose for the anchor plugin to id. */
function hasProse(body: string | undefined): boolean {
  return (body ?? '').replace(/```[\s\S]*?```/g, '').trim().length > 0;
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
      citable: hasProse(t.body),
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
      citable: hasProse(o.body),
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
      citable: hasProse(m.body),
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
      citable: hasProse(o.body),
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
      // Only the interview transcripts are Tier A here, and only those carry
      // quotable prose. A Tier B work's body holds our summaries, not source
      // text, so it is never paragraph-citable however much of it there is.
      citable: tier === 'A' && hasProse(w.body),
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
      citable: hasProse(p.body),
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
