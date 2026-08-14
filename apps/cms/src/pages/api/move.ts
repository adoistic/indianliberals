import type { APIRoute } from 'astro';
import { requireRole, refuse, json, type Env } from '../../lib/guard';
import { readFile, readBlob, commitFiles, type GitHubEnv } from '../../lib/github';
import { collectionById } from '../../lib/collections';
import { entryPath, withRedirect } from '../../lib/move';
import { frontmatterProblems } from '../../lib/frontmatter';

/**
 * Move an entry to another section, or retire it.
 *
 * Both are one commit that removes a file, and either writes it elsewhere or
 * does not. Until this existed the CMS could only write: an editor who found a
 * piece in the wrong section could copy it across and then had no way to remove
 * the original, only to tick "Keep as a draft" and leave a ghost. CCS asked for
 * it in round 4, having found twelve opinion pieces filed under Musings.
 *
 * The finished file arrives from the browser, exactly as it does for a save.
 * The edit screen already holds the record as an object and knows how to render
 * it back to markdown; the Worker has no YAML parser and does not need one.
 *
 * Gated at sub_admin, the level that saving needs, because both change what the
 * public sees.
 */

interface MoveBody {
  action: 'move' | 'retire';
  collection: string;
  slug: string;
  toCollection?: string;
  /** The complete new file, frontmatter and body, as the editor will see it. */
  content?: string;
  /** Pictures that must follow the entry into its new folder. */
  images?: { from: string; to: string }[];
  summary?: string;
}

const NAME = /^[a-z-]+$/;
const SLUG = /^[a-z0-9-]+$/i;
const IMAGE_PATH = /^apps\/site\/public\/[a-z0-9/_-]+\.(jpg|jpeg|png|webp|svg)$/;

export const POST: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & GitHubEnv & { CONTENT_ROOT: string };
  try {
    const actor = await requireRole(request, env, 'sub_admin');
    const body = (await request.json()) as MoveBody;

    if (!NAME.test(body.collection || '') || !SLUG.test(body.slug || '')) {
      return json({ error: 'that is not an entry we can address' }, 400);
    }

    const from = collectionById(body.collection);
    if (!from) return json({ error: `there is no section called ${body.collection}` }, 400);

    const fromPath = `${env.CONTENT_ROOT}/${body.collection}/${body.slug}.md`;
    const current = await readFile(env, fromPath);
    if (!current) return json({ error: 'no such entry' }, 404);

    // ── Retire ───────────────────────────────────────────────────────────
    if (body.action === 'retire') {
      const result = await commitFiles(
        env,
        [{ path: fromPath, remove: true }],
        body.summary?.trim() || `content(${body.collection}): retire ${body.slug}`,
        actor,
      );
      return json({
        ok: true,
        retired: true,
        commit: result.url,
        note: 'It is off the site. The last version stays in the history, so nothing is lost for good.',
      });
    }

    // ── Move ─────────────────────────────────────────────────────────────
    if (!NAME.test(body.toCollection || '')) {
      return json({ error: 'that is not a section to move into' }, 400);
    }
    if (body.toCollection === body.collection) {
      return json({ error: 'it is already in that section' }, 400);
    }
    const to = collectionById(body.toCollection!);
    if (!to) return json({ error: `there is no section called ${body.toCollection}` }, 400);

    const problems = frontmatterProblems(body.content || '');
    if (problems.length) return json({ error: 'The moved entry is not valid yet', problems }, 422);

    const toPath = `${env.CONTENT_ROOT}/${body.toCollection}/${body.slug}.md`;
    if (await readFile(env, toPath)) {
      return json(
        { error: `A ${to.singular.toLowerCase()} called "${body.slug}" already exists. Rename one of them first.` },
        409,
      );
    }

    const files: { path: string; content?: string; base64?: string; remove?: boolean }[] = [
      { path: toPath, content: body.content },
      { path: fromPath, remove: true },
    ];

    // A hero picture lives in a folder named after its section, so it has to
    // travel too or the moved entry points at a file nobody serves.
    for (const image of (body.images ?? []).slice(0, 8)) {
      if (!IMAGE_PATH.test(image.from || '') || !IMAGE_PATH.test(image.to || '')) {
        return json({ error: `That is not a place a picture can go: ${image.to}` }, 400);
      }
      const held = await readBlob(env, image.from);
      if (!held) continue; // already moved, or never committed
      files.push({ path: image.to, base64: held.base64 });
      files.push({ path: image.from, remove: true });
    }

    // The old address keeps working. Anything already linked or indexed at
    // /musings/<slug>/ still resolves once the piece becomes an opinion.
    const redirectsPath = 'apps/site/public/_redirects';
    const redirects = await readFile(env, redirectsPath);
    if (redirects) {
      const updated = withRedirect(
        redirects.content,
        entryPath(body.collection, body.slug),
        entryPath(body.toCollection!, body.slug),
        `Moved from ${from.label} to ${to.label} in the CMS.`,
      );
      if (updated !== redirects.content) files.push({ path: redirectsPath, content: updated });
    }

    const result = await commitFiles(
      env,
      files,
      body.summary?.trim() ||
        `content(${body.toCollection}): move ${body.slug} from ${body.collection}`,
      actor,
    );

    return json({
      ok: true,
      moved: true,
      to: `/edit?collection=${body.toCollection}&slug=${body.slug}`,
      commit: result.url,
    });
  } catch (error) {
    return refuse(error);
  }
};
