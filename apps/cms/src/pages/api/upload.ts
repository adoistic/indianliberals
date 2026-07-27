import type { APIRoute } from 'astro';
import { requireRole, refuse, json, type Env } from '../../lib/guard';

/**
 * Put a document in the archive bucket.
 *
 * The site already serves PDFs and covers from R2 behind
 * archive.indianliberals.in, so an upload here lands beside everything that is
 * already there and the returned URL is the one that goes in the entry's
 * pdf_url. The bucket is bound to this Worker directly, so no key changes
 * hands to make it work.
 */

/**
 * Just the slice of R2 this route touches. Pulling the full Workers type
 * package into the global scope would shadow the DOM's Element with
 * HTMLRewriter's, and every client script that calls append() stops compiling.
 */
interface Bucket {
  head(key: string): Promise<unknown | null>;
  put(key: string, value: ReadableStream | ArrayBuffer, options?: {
    httpMetadata?: { contentType?: string; cacheControl?: string };
  }): Promise<unknown>;
}

const PREFIXES: Record<string, string> = {
  pdf: 'liberals',
  cover: 'covers',
  marathi: 'marathi',
  'freedom-first': 'freedom-first',
  other: 'other-publications',
};

const ALLOWED = new Set(['application/pdf', 'image/jpeg', 'image/png', 'image/webp']);
const MAX_BYTES = 120 * 1024 * 1024;

/** Filenames become URLs, so they get the same treatment as slugs. */
function tidyName(name: string): string {
  const dot = name.lastIndexOf('.');
  const stem = (dot > 0 ? name.slice(0, dot) : name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 90);
  const ext = dot > 0 ? name.slice(dot).toLowerCase().replace(/[^a-z.]/g, '') : '';
  return `${stem || 'document'}${ext}`;
}

export const POST: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & {
    ARCHIVE: Bucket;
    ARCHIVE_ORIGIN: string;
  };
  try {
    await requireRole(request, env, 'contributor');

    const form = await request.formData();
    const file = form.get('file');
    const kind = String(form.get('kind') || 'pdf');

    if (!(file instanceof File)) return json({ error: 'no file came through' }, 400);
    if (!ALLOWED.has(file.type)) {
      return json(
        { error: `${file.type || 'that file type'} is not one we accept. PDFs and images only.` },
        415,
      );
    }
    if (file.size > MAX_BYTES) {
      return json(
        { error: `That file is ${(file.size / 1e6).toFixed(0)} MB. The limit is 120 MB.` },
        413,
      );
    }

    const prefix = PREFIXES[kind] ?? PREFIXES.other;
    const key = `${prefix}/${tidyName(file.name)}`;

    const existing = await env.ARCHIVE.head(key);
    if (existing && form.get('overwrite') !== 'yes') {
      return json(
        {
          error: `A file called ${key} is already in the archive. Rename yours, or confirm you mean to replace it.`,
          existing: `${env.ARCHIVE_ORIGIN}/${key}`,
          needsConfirmation: true,
        },
        409,
      );
    }

    await env.ARCHIVE.put(key, file.stream(), {
      httpMetadata: { contentType: file.type, cacheControl: 'public, max-age=31536000' },
    });

    return json({ ok: true, key, url: `${env.ARCHIVE_ORIGIN}/${key}`, bytes: file.size });
  } catch (error) {
    return refuse(error);
  }
};
