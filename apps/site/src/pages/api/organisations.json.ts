import type { APIRoute } from 'astro';
import { buildOrganisations, jsonResponse } from '~/lib/agent-api';

// Every organisation page: the parties, forums, institutes and presses the
// thinkers wrote for. The third of the three master manifests, alongside
// works.json and thinkers.json.

export const GET: APIRoute = async () => {
  const organisations = await buildOrganisations();
  return jsonResponse({ count: organisations.length, organisations });
};
