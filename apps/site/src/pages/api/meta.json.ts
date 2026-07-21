import type { APIRoute } from 'astro';
import { buildMeta, jsonResponse } from '~/lib/agent-api';

// Counts, endpoint directory, and build stamp for the agent data plane.
// The MCP server reads this to describe itself with live numbers.

export const GET: APIRoute = async ({ site }) => {
  return jsonResponse(await buildMeta(site!.origin));
};
