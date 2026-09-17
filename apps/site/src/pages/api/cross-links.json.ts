import type { APIRoute } from 'astro';
import { crossLinksForAgents } from '~/lib/cross-links';
import { jsonResponse } from '~/lib/agent-api';

// The precomputed TF-IDF related-entries map (same data the on-page
// "Related" sections render), with withheld works removed as keys and as
// targets. Keys are "<collection>:<slug>". Backs the MCP find_related tool.

export const GET: APIRoute = async () => {
  return jsonResponse(crossLinksForAgents());
};
