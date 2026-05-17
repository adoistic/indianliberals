import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { renderMdSibling, mdResponse } from '~/lib/md-sibling';

// .md sibling endpoint for /primary-works/<slug>/.
// Returns the raw markdown body of the entry so AI agents can read it
// without HTML / CSS / layout chrome. See AGENTS.md for the citation rules.

export async function getStaticPaths() {
  const entries = await getCollection(
    'primary-works',
    (e) => !e.data.draft && e.data.language === 'en',
  );
  return entries.map((e) => ({ params: { slug: e.id }, props: { entry: e } }));
}

export const GET: APIRoute = async ({ props, site }) => {
  const entry = props.entry;
  const body = renderMdSibling(entry, 'primary-works', site!.origin);
  return mdResponse(body);
};
