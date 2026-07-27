import type { APIRoute } from 'astro';
import { actorFrom, refuse, json, type Env } from '../../lib/guard';
import { readFile, type GitHubEnv } from '../../lib/github';

// One entry, exactly as it sits in the repository, plus the sha we read it at.
// Sending that sha back with a save is what stops two editors silently
// overwriting each other.
export const GET: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & GitHubEnv & { CONTENT_ROOT: string };
  try {
    await actorFrom(request, env);
    const params = new URL(request.url).searchParams;
    const collection = params.get('collection');
    const slug = params.get('slug');
    if (!collection || !slug) return json({ error: 'need a collection and a slug' }, 400);
    if (!/^[a-z-]+$/.test(collection) || !/^[a-z0-9-]+$/i.test(slug)) {
      return json({ error: 'that name has characters we do not allow' }, 400);
    }
    const file = await readFile(env, `${env.CONTENT_ROOT}/${collection}/${slug}.md`);
    if (!file) return json({ error: 'no such entry' }, 404);
    return json(file);
  } catch (error) {
    return refuse(error);
  }
};
