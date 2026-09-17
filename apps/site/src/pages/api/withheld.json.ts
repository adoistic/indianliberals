import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { isWithheld } from '~/lib/listable';
import { jsonResponse } from '~/lib/agent-api';

// The works currently withheld, so the CMS can list them for an editor who
// wants to release one. Browse reads the live catalogue, and a withheld work
// is by design not in it; without this it could be found only by typing its
// address into the edit screen. Ids and titles only, nothing of the records.

export const GET: APIRoute = async () => {
  const works = (await getCollection('primary-works', (w) => !w.data.draft && isWithheld(w)))
    .map((w) => ({
      id: w.id,
      title: w.data.title.main,
      language: w.data.language ?? 'en',
      work_type: w.data.work_type,
      year: w.data.publication?.year ?? null,
    }))
    .sort((a, b) => a.title.localeCompare(b.title));
  return jsonResponse({ count: works.length, works });
};
