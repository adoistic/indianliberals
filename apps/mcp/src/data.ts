// Data plane: cached fetchers against the site's build-generated agent
// endpoints, plus the document-reference resolver and search scoring.
//
// The Worker holds no content. Everything comes from indianliberals.in
// at request time (edge-cached ~5 min), so new content appears here on
// the next site deploy with no Worker change.

export interface Env {
  SITE_ORIGIN?: string;
}

export class ToolError extends Error {
  status: number;
  constructor(message: string, status = 400) {
    super(message);
    this.status = status;
  }
}

export function siteOrigin(env: Env): string {
  return (env.SITE_ORIGIN || 'https://indianliberals.in').replace(/\/$/, '');
}

// In-isolate memory cache. Cloudflare may evict isolates at any time;
// this is just a hot-path accelerator on top of the edge fetch cache.
const MEM = new Map<string, { exp: number; val: unknown }>();
const TTL_MS = 5 * 60 * 1000;

async function siteFetch(env: Env, path: string): Promise<Response> {
  const url = siteOrigin(env) + path;
  const res = await fetch(url, {
    headers: { 'User-Agent': 'indianliberals-mcp/1.0' },
    cf: { cacheTtl: 300, cacheEverything: true },
  } as RequestInit);
  if (!res.ok) {
    throw new ToolError(`Upstream ${path} returned ${res.status}`, res.status === 404 ? 404 : 502);
  }
  return res;
}

export async function siteJson<T = any>(env: Env, path: string): Promise<T> {
  const hit = MEM.get(path);
  if (hit && hit.exp > Date.now()) return hit.val as T;
  const res = await siteFetch(env, path);
  const val = (await res.json()) as T;
  MEM.set(path, { exp: Date.now() + TTL_MS, val });
  return val;
}

export async function siteText(env: Env, path: string): Promise<string> {
  const key = `text:${path}`;
  const hit = MEM.get(key);
  if (hit && hit.exp > Date.now()) return hit.val as string;
  const res = await siteFetch(env, path);
  const val = await res.text();
  MEM.set(key, { exp: Date.now() + TTL_MS, val });
  return val;
}

// ─── Search index & document resolution ────────────────────────────────

export interface SearchDoc {
  key: string;
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

export async function searchIndex(env: Env): Promise<SearchDoc[]> {
  const data = await siteJson<{ docs: SearchDoc[] }>(env, '/api/search-index.json');
  return data.docs;
}

/**
 * Resolve a user-supplied document reference to a search-index doc.
 * Accepts "collection:slug", "/collection/slug/", a full site URL,
 * or a bare slug (unique across collections).
 */
export async function resolveDoc(env: Env, ref: string): Promise<SearchDoc> {
  if (!ref || typeof ref !== 'string') throw new ToolError('Missing document id.');
  const docs = await searchIndex(env);
  let cleaned = ref.trim();
  cleaned = cleaned.replace(/^https?:\/\/[^/]+/, ''); // full URL → path
  cleaned = cleaned.replace(/\.md$/, '').replace(/^\/+|\/+$/g, ''); // path → col/slug
  const asKey = cleaned.includes(':') ? cleaned : cleaned.replace('/', ':');

  const byKey = docs.find((d) => d.key === asKey);
  if (byKey) return byKey;

  const bySlug = docs.filter((d) => d.id === cleaned);
  if (bySlug.length === 1) return bySlug[0];
  if (bySlug.length > 1) {
    throw new ToolError(
      `Ambiguous id "${ref}" — matches ${bySlug.map((d) => d.key).join(', ')}. Use the "<collection>:<slug>" form.`,
    );
  }

  const close = docs
    .filter((d) => d.id.includes(cleaned.split(':').pop() ?? cleaned) || d.title.toLowerCase().includes(cleaned.toLowerCase()))
    .slice(0, 5)
    .map((d) => d.key);
  throw new ToolError(
    `No document "${ref}". ${close.length ? `Close matches: ${close.join(', ')}.` : 'Try search_corpus first.'}`,
    404,
  );
}

// ─── Search scoring ────────────────────────────────────────────────────

function tokenize(q: string): string[] {
  return q
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((t) => t.length >= 2);
}

export interface SearchHit extends Omit<SearchDoc, 'text'> {
  score: number;
  snippet: string;
}

export function scoreSearch(
  docs: SearchDoc[],
  query: string,
  opts: { tier?: string; collection?: string; kind?: string; limit?: number } = {},
): SearchHit[] {
  const tokens = tokenize(query);
  const phrase = query.trim().toLowerCase();
  const limit = Math.min(Math.max(opts.limit ?? 10, 1), 50);
  const hits: SearchHit[] = [];

  for (const d of docs) {
    if (opts.tier && d.tier !== opts.tier.toUpperCase()) continue;
    if (opts.collection && d.collection !== opts.collection) continue;
    if (opts.kind && d.kind !== opts.kind) continue;

    const title = d.title.toLowerCase();
    const authors = d.authors.join(' ').toLowerCase();
    const themes = d.themes.join(' ').toLowerCase();
    const text = d.text.toLowerCase();

    let score = 0;
    if (phrase.length > 3) {
      if (title.includes(phrase)) score += 10;
      if (text.includes(phrase)) score += 5;
    }
    for (const t of tokens) {
      if (title.includes(t)) score += 4;
      if (authors.includes(t)) score += 3;
      if (themes.includes(t)) score += 2;
      if (text.includes(t)) {
        // occurrence count, capped so one long doc doesn't drown the rest
        let n = 0;
        let i = text.indexOf(t);
        while (i !== -1 && n < 5) {
          n++;
          i = text.indexOf(t, i + t.length);
        }
        score += n;
      }
    }
    if (score === 0) continue;

    // snippet centered on the first token hit in the body text
    let snippet = d.text.slice(0, 200);
    for (const t of tokens) {
      const i = text.indexOf(t);
      if (i !== -1) {
        const start = Math.max(0, i - 80);
        snippet = (start > 0 ? '…' : '') + d.text.slice(start, i + 140) + '…';
        break;
      }
    }
    const { text: _omit, ...rest } = d;
    hits.push({ ...rest, score, snippet });
  }

  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, limit);
}

// ─── Paragraph extraction from annotated .md siblings ──────────────────

const ANNOT_RE = /<!--\s*#(p-[0-9a-f]{6}(?:-\d+)?)\s*-->/g;

/** Map of paragraph-id → clean paragraph text for an annotated .md body. */
export function extractParagraphs(markdown: string): Map<string, string> {
  const out = new Map<string, string>();
  const blocks = markdown.split(/\n{2,}/);
  for (const block of blocks) {
    const m = [...block.matchAll(ANNOT_RE)];
    if (m.length === 0) continue;
    const id = m[m.length - 1][1];
    const text = block.replace(ANNOT_RE, '').replace(/\s+$/g, '').trim();
    if (text) out.set(id, text);
  }
  return out;
}
