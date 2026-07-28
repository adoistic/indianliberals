import type { APIRoute } from 'astro';
import { requireRole, refuse, json, type Env } from '../../lib/guard';
import { commitFile, readFile, type GitHubEnv } from '../../lib/github';
import { frontmatterProblems } from '../../lib/frontmatter';

/**
 * Save an entry: validate it, then commit it.
 *
 * Publishing is the only action in this system that changes what the public
 * sees, so it is the one gated on a role rather than merely on being signed
 * in. Contributors get a 403 here and save drafts to Firestore instead.
 *
 * Two guards before anything is written. The frontmatter has to parse, because
 * a file that breaks the site build takes the whole archive offline until
 * someone notices. And the sha has to match what the editor loaded, so a save
 * cannot quietly discard a colleague's change made in the meantime.
 */

interface SaveBody {
  collection: string;
  slug: string;
  /** The complete file, frontmatter and body, exactly as it should land. */
  content: string;
  /** The sha the editor loaded, absent when creating something new. */
  sha?: string;
  summary?: string;
}

export const POST: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & GitHubEnv & { CONTENT_ROOT: string };
  try {
    const actor = await requireRole(request, env, 'sub_admin');
    const body = (await request.json()) as SaveBody;

    if (!/^[a-z-]+$/.test(body.collection || '')) {
      return json({ error: 'that is not a collection name' }, 400);
    }
    if (!/^[a-z0-9-]+$/i.test(body.slug || '')) {
      return json(
        { error: 'the file name may only use letters, numbers and hyphens' },
        400,
      );
    }

    const problems = frontmatterProblems(body.content || '');
    if (problems.length) return json({ error: 'The entry is not valid yet', problems }, 422);

    const path = `${env.CONTENT_ROOT}/${body.collection}/${body.slug}.md`;

    // Re-read rather than trust the sha we were handed: if the file moved on
    // since the editor opened it, say so instead of overwriting the change.
    const current = await readFile(env, path);
    if (current && !body.sha) {
      return json(
        { error: 'Something already exists with that name. Open it and edit it instead.' },
        409,
      );
    }
    if (current && body.sha && current.sha !== body.sha) {
      return json(
        {
          error:
            'Somebody else saved this while you were editing. Reload to see their version before saving yours.',
        },
        409,
      );
    }

    const verb = current ? 'Update' : 'Add';
    const summary =
      body.summary?.trim() ||
      `content(${body.collection}): ${verb.toLowerCase()} ${body.slug}`;

    const result = await commitFile(env, {
      path,
      content: body.content,
      summary,
      sha: current?.sha,
      actor: { email: actor.email, name: actor.name },
    });

    return json({
      ok: true,
      path,
      created: !current,
      commit: result?.commit?.sha ?? null,
      url: result?.commit?.html_url ?? null,
    });
  } catch (error) {
    return refuse(error);
  }
};
