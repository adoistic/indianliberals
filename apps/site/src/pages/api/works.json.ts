import type { APIRoute } from 'astro';
import { getEnWorks, buildWorkCard, jsonResponse } from '~/lib/agent-api';

// The full works catalogue (books, pamphlets, speeches, periodical
// issues, interviews …) as light cards. Backs the MCP list_works tool.

export const GET: APIRoute = async () => {
  const works = await getEnWorks();
  const cards = await Promise.all(works.map(buildWorkCard));
  cards.sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.id.localeCompare(b.id));
  return jsonResponse({ count: cards.length, works: cards });
};
