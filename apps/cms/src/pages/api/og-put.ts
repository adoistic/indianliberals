import type { APIRoute } from 'astro';
import { json, type Env } from '../../lib/guard';

/**
 * Where the OG-card workflow puts its renders.
 *
 * The cards are drawn by scripts/og/og_cards.py, which GitHub Actions runs
 * whenever content changes. Actions holds no Cloudflare credential; this
 * Worker already holds the bucket. So the workflow proves itself with one
 * shared secret and hands the bytes over, and the only things this route
 * will write are JPEGs and the manifest, under og/, full stop.
 */

interface Bucket {
  put(
    key: string,
    value: ReadableStream | ArrayBuffer | null,
    options?: { httpMetadata?: { contentType?: string; cacheControl?: string } },
  ): Promise<unknown>;
}

const KEY_SHAPE = /^og\/[a-z0-9/._-]+\.(jpg|json)$/;
const MAX_BYTES = 2 * 1024 * 1024;

export const PUT: APIRoute = async ({ request, url, locals }) => {
  const env = (locals as any).runtime.env as Env & {
    ARCHIVE: Bucket;
    OG_PUSH_TOKEN?: string;
  };

  const expected = env.OG_PUSH_TOKEN;
  if (!expected) return json({ error: 'og uploads are not configured' }, 503);
  if (request.headers.get('X-Og-Token') !== expected) {
    return json({ error: 'that is not the token' }, 403);
  }

  const key = url.searchParams.get('key') ?? '';
  if (!KEY_SHAPE.test(key)) {
    return json({ error: 'og uploads may only write og/ cards and the manifest' }, 400);
  }

  const body = await request.arrayBuffer();
  if (!body.byteLength) return json({ error: 'the upload carried no bytes' }, 400);
  if (body.byteLength > MAX_BYTES) return json({ error: 'that is too big for a card' }, 413);

  await env.ARCHIVE.put(key, body, {
    httpMetadata: {
      contentType: key.endsWith('.json') ? 'application/json' : 'image/jpeg',
      cacheControl: 'public, max-age=86400',
    },
  });

  return json({ ok: true, key });
};
