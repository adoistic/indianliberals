import type { APIRoute } from 'astro';
import { requireRole, refuse, json, type Env } from '../../lib/guard';
import { commitFiles, readFile, type GitHubEnv } from '../../lib/github';
import { frontmatterProblems } from '../../lib/frontmatter';

/**
 * Publish many drafts at once, as a single commit.
 *
 * This exists because of one number: a full site build takes about twenty-five
 * minutes and Cloudflare runs them one after another. Approving fifty scanned
 * pamphlets one at a time would queue builds into the middle of next week. One
 * commit means one build, whether it carries one entry or fifty.
 *
 * Everything is checked before anything is written. A batch that would break
 * the site build, or would quietly overwrite an entry somebody else already
 * published, is refused whole, with the reasons named per entry, so the
 * editor can fix the two that are wrong rather than being told "invalid".
 */

interface BatchEntry {
  collection: string;
  slug: string;
  /** The complete file, frontmatter and body, exactly as it should land. */
  content: string;
  /** Carried through untouched so the browser can mark the right draft done. */
  draftId?: string;
  /** Pictures staged in the bucket, committed beside the entry. */
  images?: { path: string; stagingKey: string }[];
}

/** The slice of R2 this route reads staged pictures from. */
interface Bucket {
  get(key: string): Promise<{ arrayBuffer(): Promise<ArrayBuffer> } | null>;
  delete(key: string): Promise<void>;
}

const IMAGE_PATH = /^apps\/site\/public\/[a-z0-9/_-]+\.(jpg|jpeg|png|webp|svg)$/;
const STAGING_KEY = /^staging\/[a-z0-9./-]+$/;

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

interface BatchBody {
  entries: BatchEntry[];
  summary?: string;
}

/**
 * One commit's worth. Above this the request spends long enough talking to
 * GitHub that it is kinder to split it, and an editor approving more than a
 * hundred entries in one gesture has probably not read them.
 */
const MAX_ENTRIES = 100;

export const POST: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & GitHubEnv & { CONTENT_ROOT: string };
  try {
    const actor = await requireRole(request, env, 'sub_admin');
    const body = (await request.json()) as BatchBody;
    const entries = Array.isArray(body.entries) ? body.entries : [];

    if (!entries.length) return json({ error: 'There was nothing to publish.' }, 400);
    if (entries.length > MAX_ENTRIES) {
      return json(
        {
          error: `That is ${entries.length} entries in one go. The limit is ${MAX_ENTRIES}; publish them in two batches.`,
        },
        413,
      );
    }

    // ── Check everything first ──────────────────────────────────────────
    //
    // Each rejection is tied to its slug. A batch of fifty with two bad
    // entries should tell you which two.
    const rejected: { slug: string; problems: string[] }[] = [];
    const seen = new Map<string, string>();
    const planned: {
      path: string;
      content: string;
      slug: string;
      draftId?: string;
      images: { path: string; stagingKey: string }[];
    }[] = [];

    for (const entry of entries) {
      const slug = String(entry.slug || '');
      const problems: string[] = [];

      if (!/^[a-z-]+$/.test(entry.collection || '')) {
        problems.push('That is not a kind of entry this archive holds.');
      }
      if (!/^[a-z0-9-]+$/i.test(slug)) {
        problems.push('The file name may only use letters, numbers and hyphens.');
      }
      problems.push(...frontmatterProblems(entry.content || ''));

      const images = Array.isArray(entry.images) ? entry.images.slice(0, 12) : [];
      for (const image of images) {
        if (!IMAGE_PATH.test(image.path || '') || !STAGING_KEY.test(image.stagingKey || '')) {
          problems.push('A picture attached to this entry is not one we staged.');
        }
      }

      const path = `${env.CONTENT_ROOT}/${entry.collection}/${slug}.md`;

      // Two drafts in the same batch claiming one filename would silently
      // become whichever landed last.
      const twin = seen.get(path);
      if (twin) {
        problems.push(`Another entry in this batch is also called ${slug}. Rename one of them.`);
      } else {
        seen.set(path, slug);
      }

      if (problems.length) {
        rejected.push({ slug: slug || '(no name)', problems });
        continue;
      }
      planned.push({ path, content: entry.content, slug, draftId: entry.draftId, images });
    }

    // Anything already in the archive is somebody else's work. Publishing a
    // batch is for new entries; replacing an existing one is a deliberate act
    // that belongs on the edit screen where the change is shown first.
    const existing = await Promise.all(
      planned.map(async (item) => ((await readFile(env, item.path)) ? item.slug : null)),
    );
    for (const slug of existing.filter(Boolean) as string[]) {
      rejected.push({
        slug,
        problems: ['Something with this name is already in the archive. Open it and edit it instead.'],
      });
    }

    if (rejected.length) {
      return json(
        {
          error:
            rejected.length === entries.length
              ? 'None of these could be published yet.'
              : `${rejected.length} of ${entries.length} could not be published, so nothing was. Fix them and try again.`,
          rejected,
        },
        422,
      );
    }

    // ── Write ───────────────────────────────────────────────────────────
    const summary =
      body.summary?.trim() ||
      `content: add ${planned.length} ${planned.length === 1 ? 'entry' : 'entries'}`;

    // Staged pictures ride in the same commit as the entries that use them.
    const bucket = (env as unknown as { ARCHIVE: Bucket }).ARCHIVE;
    const files: { path: string; content?: string; base64?: string }[] = planned.map((item) => ({
      path: item.path,
      content: item.content,
    }));
    const stagedKeys: string[] = [];
    for (const item of planned) {
      for (const image of item.images) {
        const held = await bucket.get(image.stagingKey);
        if (!held) {
          return json(
            {
              error: `A picture for ${item.slug} has gone missing from staging. Open the draft and drop it again.`,
            },
            409,
          );
        }
        files.push({ path: image.path, base64: toBase64(await held.arrayBuffer()) });
        stagedKeys.push(image.stagingKey);
      }
    }

    const result = await commitFiles(env, files, summary, {
      email: actor.email,
      name: actor.name,
    });

    for (const key of stagedKeys) {
      try {
        await bucket.delete(key);
      } catch {
        /* crumbs in staging are harmless */
      }
    }

    return json({
      ok: true,
      published: planned.length,
      commit: result.sha,
      url: result.url,
      slugs: planned.map((item) => item.slug),
      draftIds: planned.map((item) => item.draftId).filter(Boolean),
    });
  } catch (error) {
    return refuse(error);
  }
};
