import type { APIRoute } from 'astro';
import { buildThinkers, jsonResponse } from '~/lib/agent-api';

// Every thinker profile with bio snippet. Backs the MCP list_thinkers tool.

export const GET: APIRoute = async () => {
  const thinkers = await buildThinkers();
  return jsonResponse({ count: thinkers.length, thinkers });
};
