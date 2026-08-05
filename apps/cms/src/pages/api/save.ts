import type { APIRoute } from 'astro';
import { requireRole, refuse, json, type Env } from '../../lib/guard';
import { commitFile, commitFiles, readFile, type GitHubEnv } from '../../lib/github';
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
  /**
   * Pictures dropped on the form, waiting in the bucket's staging area.
   * Each one is read out of staging and committed beside the entry, in the
   * same commit, at the repository path its field already points to.
   */
  images?: { path: string; stagingKey: string }[];
}

/** The slice of R2 this route reads staged pictures from. */
interface Bucket {
  get(key: string): Promise<{ arrayBuffer(): Promise<ArrayBuffer> } | null>;
  delete(key: string): Promise<void>;
}

/** Where in the repository a dropped picture is allowed to land. */
const IMAGE_PATH = /^apps\/site\/public\/[a-z0-9/_-]+\.(jpg|jpeg|png|webp|svg)$/;

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
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

    const images = Array.isArray(body.images) ? body.images.slice(0, 12) : [];
    if (images.length) {
      // Entry and pictures land as one commit, so one save is one build and
      // a page never appears pointing at a picture that is not there yet.
      const bucket = (env as unknown as { ARCHIVE: Bucket }).ARCHIVE;
      const files: { path: string; content?: string; base64?: string }[] = [
        { path, content: body.content },
      ];
      for (const image of images) {
        if (!IMAGE_PATH.test(image.path || '')) {
          return json({ error: `That is not a place a picture can go: ${image.path}` }, 400);
        }
        if (!/^staging\/[a-z0-9./-]+$/.test(image.stagingKey || '')) {
          return json({ error: 'That staged picture reference is not one we wrote.' }, 400);
        }
        const held = await bucket.get(image.stagingKey);
        if (!held) {
          return json(
            { error: 'A dropped picture has gone missing from staging. Drop it on the form again.' },
            409,
          );
        }
        files.push({ path: image.path, base64: toBase64(await held.arrayBuffer()) });
      }
      const result = await commitFiles(env, files, summary, {
        email: actor.email,
        name: actor.name,
      });
      // The staging copies have done their job. Losing this cleanup would
      // only leave crumbs, so it is not allowed to fail the save.
      for (const image of images) {
        try {
          await bucket.delete(image.stagingKey);
        } catch {
          /* harmless */
        }
      }
      return json({
        ok: true,
        path,
        created: !current,
        commit: result.sha,
        url: result.url,
      });
    }

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
