import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { renderMdSibling, mdResponse } from '~/lib/md-sibling';
import { isWithheld } from '~/lib/listable';

// .md sibling endpoint for /primary-works/<slug>/.
// Returns the raw markdown body of the entry so AI agents can read it
// without HTML / CSS / layout chrome. See AGENTS.md for the citation rules.

export async function getStaticPaths() {
  // No sibling for a withheld work: the address answers 404, which is what an
  // agent should hear for a record it may not read.
  const entries = await getCollection(
    'primary-works',
    (e) => !e.data.draft && e.data.language === 'en' && !isWithheld(e),
  );
  return entries.map((e) => ({ params: { slug: e.id }, props: { entry: e } }));
}

export const GET: APIRoute = async ({ props, site }) => {
  const entry = props.entry;
  const body = renderMdSibling(entry, 'primary-works', site!.origin);
  return mdResponse(body);
};
