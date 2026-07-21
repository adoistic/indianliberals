import type { APIRoute } from 'astro';
import { buildSearchIndex, jsonResponse } from '~/lib/agent-api';

// Compact tier-flagged search index over every content kind. The MCP
// server's search_corpus tool scores against this at request time.

export const GET: APIRoute = async () => {
  const docs = await buildSearchIndex();
  return jsonResponse({ count: docs.length, docs });
};
