import type { APIRoute } from 'astro';
import { actorFrom, refuse, json, type Env } from '../../lib/guard';
import { listCollection, type GitHubEnv } from '../../lib/github';

// Everything in one collection, so a list page can show what already exists
// and the entity pickers can offer real slugs rather than free text.
export const GET: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & GitHubEnv & { CONTENT_ROOT: string };
  try {
    await actorFrom(request, env);
    const collection = new URL(request.url).searchParams.get('collection');
    if (!collection) return json({ error: 'which collection' }, 400);
    if (!/^[a-z-]+$/.test(collection)) return json({ error: 'that is not a collection name' }, 400);
    return json({ entries: await listCollection(env, collection, env.CONTENT_ROOT) });
  } catch (error) {
    return refuse(error);
  }
};
