import type { APIRoute } from 'astro';
import crossLinksJson from '../../../../../data/synthesis/cross-links.json';
import { jsonResponse } from '~/lib/agent-api';

// The precomputed TF-IDF related-entries map (same data the on-page
// "Related" sections render). Keys are "<collection>:<slug>". Backs the
// MCP find_related tool.

export const GET: APIRoute = async () => {
  return jsonResponse(crossLinksJson);
};
