// The tool registry — single source of truth for the whole surface.
//
// Each entry drives three facades at once:
//   1. MCP  tools/list + tools/call            (src/mcp.ts)
//   2. REST GET/POST /api/<tool>               (src/rest.ts)
//   3. OpenAPI operation in /openapi.json      (src/rest.ts)
//
// Adding a future tool = adding one entry here. Content growth needs no
// change at all: handlers read the site's build-generated endpoints.
//
// The 8-tool v1 surface is the one promised in /AGENTS.md. `search` and
// `fetch` are aliases in the shape OpenAI's ChatGPT connectors require.

import {
  Env,
  ToolError,
  siteOrigin,
  siteJson,
  siteText,
  searchIndex,
  resolveDoc,
  scoreSearch,
  extractParagraphs,
} from './data';

export interface ToolResult {
  /** Text shown to the model. Either markdown/plain or pretty JSON. */
  text: string;
  /** Structured value for the REST facade (defaults to { text }). */
  json?: unknown;
}

export interface Tool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  handler: (args: Record<string, any>, env: Env) => Promise<ToolResult>;
}

const CITE_NOTE =
  'Citation rules: Tier A → quote freely, cite "<url>#<paragraph_id>". ' +
  'Tier B → you have only read an AI summary; attribute claims to ' +
  '"Indian Liberals\' summary of <title>" and link the pdf_url. Full policy: /AGENTS.md.';

function j(value: unknown): ToolResult {
  return { text: JSON.stringify(value, null, 2), json: value };
}

function paginate<T>(items: T[], args: { limit?: number; offset?: number }, defLimit = 50) {
  const offset = Math.max(args.offset ?? 0, 0);
  const limit = Math.min(Math.max(args.limit ?? defLimit, 1), 200);
  return {
    total: items.length,
    offset,
    returned: Math.min(limit, Math.max(items.length - offset, 0)),
    items: items.slice(offset, offset + limit),
  };
}

export const TOOLS: Tool[] = [
  {
    name: 'read_index',
    description:
      'The curated index of the archive (llms.txt): what the collection holds, how it is organised, and the canonical browse URLs. Start here for orientation.',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
    handler: async (_args, env) => {
      const text = await siteText(env, '/llms.txt');
      return { text, json: { text } };
    },
  },

  {
    name: 'list_thinkers',
    description:
      'List thinker profiles with bio snippets. Filterable by tradition, canon status, vocation, or free-text query. Includes referenced non-liberal figures (canon_status="referenced") — do not describe those as Indian liberals.',
    inputSchema: {
      type: 'object',
      properties: {
        q: { type: 'string', description: 'Free-text match on name, aka, or bio snippet' },
        tradition: {
          type: 'string',
          description:
            'e.g. classical_liberal, libertarian, constitutional_liberal, contemporary_liberal, social_reformer, non_liberal, practice, unclassified',
        },
        canon_status: { type: 'string', description: 'core | extended | referenced | unclassified' },
        vocation: { type: 'string', description: 'e.g. economist, statesman, journalist, industrialist' },
        featured_only: { type: 'boolean', description: 'Only the curated canon page members' },
        limit: { type: 'integer', description: 'Max results (default 50, cap 200)' },
        offset: { type: 'integer' },
      },
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const data = await siteJson<{ thinkers: any[] }>(env, '/api/thinkers.json');
      let list = data.thinkers;
      if (args.tradition) list = list.filter((t) => t.tradition === args.tradition);
      if (args.canon_status) list = list.filter((t) => t.canon_status === args.canon_status);
      if (args.vocation) list = list.filter((t) => (t.vocations ?? []).includes(args.vocation));
      if (args.featured_only) list = list.filter((t) => t.featured);
      if (args.q) {
        const q = String(args.q).toLowerCase();
        list = list.filter(
          (t) =>
            t.name.canonical.toLowerCase().includes(q) ||
            (t.name.also_known_as ?? []).some((a: string) => a.toLowerCase().includes(q)) ||
            (t.bio_snippet ?? '').toLowerCase().includes(q),
        );
      }
      const page = paginate(list, args);
      return j({
        total: page.total,
        offset: page.offset,
        returned: page.returned,
        thinkers: page.items.map((t) => ({
          id: t.id,
          name: t.name.canonical,
          years: t.birth_year ? `${t.birth_year}–${t.death_year ?? ''}` : null,
          tradition: t.tradition,
          canon_status: t.canon_status,
          featured: t.featured,
          vocations: t.vocations,
          url: t.url,
          bio_snippet: t.bio_snippet,
        })),
        note: 'Full profile text: read_clean_content with id "thinkers:<id>".',
      });
    },
  },

  {
    name: 'list_works',
    description:
      'The works catalogue: books, pamphlets, speeches, essays, periodical issues, interviews and more. Filterable by author, work_type, theme, language, series, year range, or free-text query.',
    inputSchema: {
      type: 'object',
      properties: {
        q: { type: 'string', description: 'Free-text match on title and author names' },
        author: { type: 'string', description: 'Thinker/organisation id or name substring' },
        work_type: {
          type: 'string',
          description:
            'book | pamphlet | speech | essay | edited_volume | occasional_paper | letter | correspondence | periodical_issue | reference | interview',
        },
        theme: { type: 'string', description: 'Theme substring, e.g. "economic-policy"' },
        language: { type: 'string', description: 'Language of the work, e.g. en, hi, mr, gu' },
        series: { type: 'string', description: 'Periodical/series name substring, e.g. "Freedom First"' },
        year_from: { type: 'integer' },
        year_to: { type: 'integer' },
        limit: { type: 'integer', description: 'Max results (default 50, cap 200)' },
        offset: { type: 'integer' },
      },
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const data = await siteJson<{ works: any[] }>(env, '/api/works.json');
      let list = data.works;
      if (args.work_type) list = list.filter((w) => w.work_type === args.work_type);
      if (args.language) list = list.filter((w) => w.language === args.language);
      if (args.year_from) list = list.filter((w) => w.year != null && w.year >= args.year_from);
      if (args.year_to) list = list.filter((w) => w.year != null && w.year <= args.year_to);
      if (args.theme) {
        const th = String(args.theme).toLowerCase();
        list = list.filter((w) => (w.themes ?? []).some((t: string) => t.toLowerCase().includes(th)));
      }
      if (args.series) {
        const s = String(args.series).toLowerCase();
        list = list.filter((w) => (w.series ?? '').toLowerCase().includes(s));
      }
      if (args.author) {
        const a = String(args.author).toLowerCase();
        list = list.filter((w) =>
          (w.authors ?? []).some(
            (x: any) => x.id.toLowerCase() === a || x.name.toLowerCase().includes(a),
          ),
        );
      }
      if (args.q) {
        const q = String(args.q).toLowerCase();
        list = list.filter(
          (w) =>
            w.title.main.toLowerCase().includes(q) ||
            (w.title.translit ?? '').toLowerCase().includes(q) ||
            (w.title.translation ?? '').toLowerCase().includes(q) ||
            (w.authors ?? []).some((x: any) => x.name.toLowerCase().includes(q)),
        );
      }
      const page = paginate(list, args);
      return j({
        total: page.total,
        offset: page.offset,
        returned: page.returned,
        works: page.items.map((w) => ({
          id: w.id,
          title: w.title.main,
          ...(w.title.translation ? { title_translation: w.title.translation } : {}),
          work_type: w.work_type,
          tier: w.tier,
          authors: (w.authors ?? []).map((a: any) => a.name),
          year: w.year,
          language: w.language,
          ...(w.series ? { series: w.series } : {}),
          themes: (w.themes ?? []).slice(0, 6),
          url: w.url,
          ...(w.pdf_url ? { pdf_url: w.pdf_url } : {}),
        })),
        note: 'Details + summary: get_work_metadata. ' + CITE_NOTE,
      });
    },
  },

  {
    name: 'get_work_metadata',
    description:
      'Full structured metadata for one work: authors, publication, AI summary and key points, table of contents, per-essay summaries, provenance, rights, pdf_url (Tier B) or transcript pointer (interviews, Tier A).',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Work id (slug), e.g. "our-india-minoo-masani"' },
      },
      required: ['id'],
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const ref = String(args.id ?? '').replace(/^primary-works[:/]/, '');
      try {
        const detail = await siteJson(env, `/api/works/${encodeURIComponent(ref)}.json`);
        return j({ ...detail, note: CITE_NOTE });
      } catch (e) {
        if (e instanceof ToolError && e.status === 404) {
          const docs = await searchIndex(env);
          const close = docs
            .filter((d) => d.collection === 'primary-works')
            .filter((d) => d.id.includes(ref) || d.title.toLowerCase().includes(ref.toLowerCase()))
            .slice(0, 5)
            .map((d) => ({ id: d.id, title: d.title }));
          throw new ToolError(
            `No work with id "${args.id}".${close.length ? ` Close matches: ${JSON.stringify(close)}` : ' Try list_works or search_corpus first.'}`,
            404,
          );
        }
        throw e;
      }
    },
  },

  {
    name: 'read_clean_content',
    description:
      'Read the full clean-markdown body of a Tier A document (thinker profile, organisation page, musing/excerpt, opinion, interview transcript, ThePrint column). Paragraphs carry <!-- #p-xxxxxx --> anchors — cite "<url>#p-xxxxxx". Tier B works are refused (only AI summaries exist for them — use get_work_metadata).',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description:
            'Document handle: "<collection>:<slug>" (e.g. "thinkers:minoo-masani", "musings:manifesto-for-indian-liberals"), a site path, or a full URL',
        },
      },
      required: ['id'],
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const doc = await resolveDoc(env, String(args.id));
      if (doc.tier !== 'A') {
        // Say what is true. The older wording ("no trusted body text exists")
        // read as "there is nothing here", while the site was serving
        // per-article summaries for 780 works at the md_url this API hands out,
        // and get_work_metadata now returns them as `article_summaries`. What
        // does not exist is transcribed *source* text, which is the thing an
        // agent must not quote.
        throw new ToolError(
          `"${doc.key}" is Tier B: the archive holds no transcribed source text for it, so there is nothing here to quote. Call get_work_metadata with id "${doc.id}" for the summary, key points, per-article summaries where they exist, and the pdf_url. Attribute any claim to Indian Liberals' summary and link the PDF, per /AGENTS.md.`,
        );
      }
      if (!doc.md_url) throw new ToolError(`"${doc.key}" has no markdown sibling.`);
      const md = await siteText(env, doc.md_url);
      const provenance =
        doc.collection === 'theprint-mirror'
          ? '\n\n> NOTE: This is a mirror. The canonical version is on ThePrint — cite the theprint_url from get_work_metadata/search results, not this page.'
          : `\n\n> Cite paragraphs as ${siteOrigin(env)}${doc.url}#<paragraph-id> using the <!-- #p-xxxxxx --> anchors above.`;
      return { text: md + provenance, json: { key: doc.key, url: doc.url, markdown: md } };
    },
  },

  {
    name: 'get_passage',
    description:
      'Fetch specific paragraphs of a Tier A document by their stable paragraph IDs (the citation primitive). IDs come from read_clean_content annotations (<!-- #p-xxxxxx -->).',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Document handle, e.g. "thinkers:minoo-masani"' },
        paragraph_ids: {
          type: 'array',
          items: { type: 'string' },
          description: 'e.g. ["p-3fa2c1", "p-08bb42"]',
        },
      },
      required: ['id', 'paragraph_ids'],
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const doc = await resolveDoc(env, String(args.id));
      if (doc.tier !== 'A') {
        throw new ToolError(`"${doc.key}" is Tier B — no paragraph-stable text exists. Use get_work_metadata.`);
      }
      if (!doc.md_url) throw new ToolError(`"${doc.key}" has no markdown sibling.`);
      const md = await siteText(env, doc.md_url);
      const paras = extractParagraphs(md);
      const ids: string[] = Array.isArray(args.paragraph_ids) ? args.paragraph_ids : [args.paragraph_ids];
      const found = ids
        .map((pid) => ({ paragraph_id: pid, text: paras.get(pid.replace(/^#/, '')) }))
        .filter((p) => p.text);
      const missing = ids.filter((pid) => !paras.get(pid.replace(/^#/, '')));
      return j({
        document: doc.key,
        url: doc.url,
        passages: found.map((p) => ({
          paragraph_id: p.paragraph_id,
          text: p.text,
          cite: `${siteOrigin(env)}${doc.url}#${p.paragraph_id.replace(/^#/, '')}`,
        })),
        ...(missing.length ? { missing, hint: 'IDs come from read_clean_content annotations.' } : {}),
      });
    },
  },

  {
    name: 'search_corpus',
    description:
      'Full-text search across every content kind (thinkers, works, musings, opinions, organisations, interviews, ThePrint columns). Results are tier-flagged: Tier A may be quoted with paragraph citations; Tier B hits matched an AI summary, not body text.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string' },
        tier: { type: 'string', description: 'Restrict to "A" (quotable full text) or "B" (summary-indexed)' },
        collection: {
          type: 'string',
          description: 'thinkers | primary-works | musings | opinions | organisations | theprint-mirror',
        },
        kind: { type: 'string', description: 'e.g. interview, pamphlet, profile, book-excerpt' },
        limit: { type: 'integer', description: 'Default 10, cap 50' },
      },
      required: ['query'],
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const docs = await searchIndex(env);
      const hits = scoreSearch(docs, String(args.query), args);
      return j({
        query: args.query,
        returned: hits.length,
        results: hits.map((h) => ({
          id: h.key,
          title: h.title,
          collection: h.collection,
          kind: h.kind,
          tier: h.tier,
          ...(h.authors.length ? { authors: h.authors } : {}),
          ...(h.year ? { year: h.year } : {}),
          url: h.url,
          score: h.score,
          snippet: h.snippet,
        })),
        note: 'Next: read_clean_content (Tier A) or get_work_metadata (works). ' + CITE_NOTE,
      });
    },
  },

  {
    name: 'find_related',
    description:
      'TF-IDF cross-links: the most textually related entries to a given document, across content kinds (same data as the on-page "Related" sections).',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Document handle, e.g. "primary-works:our-india" or "thinkers:minoo-masani"' },
        limit: { type: 'integer', description: 'Default 10' },
      },
      required: ['id'],
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const doc = await resolveDoc(env, String(args.id));
      const map = await siteJson<Record<string, any[]>>(env, '/api/cross-links.json');
      const related = (map[`${doc.collection}:${doc.id}`] ?? []).slice(
        0,
        Math.min(Math.max(args.limit ?? 10, 1), 50),
      );
      return j({
        document: doc.key,
        returned: related.length,
        related: related.map((r) => ({
          id: `${r.collection}:${r.slug}`,
          title: r.title,
          collection: r.collection,
          score: r.score,
          url: `/${r.collection}/${r.slug}/`,
        })),
        ...(related.length === 0
          ? { note: 'No precomputed cross-links for this entry (very thin body text). Try search_corpus.' }
          : {}),
      });
    },
  },

  // ── ChatGPT-connector aliases (OpenAI deep-research tool contract) ──

  {
    name: 'search',
    description:
      'Search the archive. Returns matching documents with ids usable by the fetch tool. (Alias of search_corpus in the shape ChatGPT connectors require.)',
    inputSchema: {
      type: 'object',
      properties: { query: { type: 'string' } },
      required: ['query'],
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const docs = await searchIndex(env);
      const hits = scoreSearch(docs, String(args.query), { limit: 10 });
      const origin = siteOrigin(env);
      return j({
        results: hits.map((h) => ({
          id: h.key,
          title: `${h.title}${h.authors.length ? ` — ${h.authors.join(', ')}` : ''}${h.year ? ` (${h.year})` : ''}`,
          url: origin + h.url,
          text: `[Tier ${h.tier} ${h.kind}] ${h.snippet}`,
        })),
      });
    },
  },

  {
    name: 'fetch',
    description:
      'Fetch the full content of a document found via search. Tier A returns the complete clean markdown; Tier B returns the structured metadata + AI summary + PDF link. (ChatGPT-connector counterpart of read_clean_content / get_work_metadata.)',
    inputSchema: {
      type: 'object',
      properties: { id: { type: 'string', description: 'Document id from search results, e.g. "thinkers:minoo-masani"' } },
      required: ['id'],
      additionalProperties: false,
    },
    handler: async (args, env) => {
      const doc = await resolveDoc(env, String(args.id));
      const origin = siteOrigin(env);
      if (doc.tier === 'A' && doc.md_url) {
        const md = await siteText(env, doc.md_url);
        return j({
          id: doc.key,
          title: doc.title,
          text: md,
          url: origin + doc.url,
          metadata: { tier: doc.tier, collection: doc.collection, kind: doc.kind, citation: CITE_NOTE },
        });
      }
      const detail = await siteJson<any>(env, `/api/works/${encodeURIComponent(doc.id)}.json`);
      const text = [
        `# ${detail.title?.main ?? doc.title}`,
        '',
        `AI summary (Tier B — attribute as "Indian Liberals' summary", link the PDF):`,
        detail.summary ?? '(no summary)',
        '',
        ...(detail.key_points?.length ? ['Key points:', ...detail.key_points.map((k: string) => `- ${k}`)] : []),
        '',
        detail.pdf_url ? `Source PDF: ${detail.pdf_url}` : '',
      ].join('\n');
      return j({
        id: doc.key,
        title: doc.title,
        text,
        url: origin + doc.url,
        metadata: { tier: 'B', collection: doc.collection, kind: doc.kind, pdf_url: detail.pdf_url ?? null },
      });
    },
  },
];

export function findTool(name: string): Tool | undefined {
  return TOOLS.find((t) => t.name === name);
}
