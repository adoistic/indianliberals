import type { APIRoute } from 'astro';
import { requireRole, refuse, json, type Env } from '../../lib/guard';

/**
 * What readers send in, and where it lands.
 *
 * CCS, round 4: "we would like to have a dialogue box/feedback box on the
 * website where users can submit their responses or feedback."
 *
 * The site is static, so a form needs somewhere to post. It posts here rather
 * than to the site's own Pages Functions for one practical reason: this Worker
 * already has the archive bucket bound and already knows who the editors are,
 * so a submission can be stored and read without a new credential, a new
 * service, or a mailbox nobody remembers to check. Submissions land in R2 under
 * feedback/, and editors read them on the Feedback screen, in the same place
 * they already sign in to.
 *
 * On spam, the honest position: this is a public endpoint on a public archive,
 * and nothing short of a challenge widget stops a determined bot. What is here
 * stops the casual kind, costs a reader nothing, and asks nobody to identify
 * himself to leave a correction:
 *
 *   - a honeypot field a human never sees and never fills in;
 *   - a minimum time on the form, because a script posts instantly;
 *   - one submission per address per minute, held as a short-lived marker;
 *   - hard length caps, so nobody can post a novel into the bucket.
 *
 * If it is ever abused past that, the next step is Turnstile, which is a
 * setting rather than a rewrite.
 */

const SITE_ORIGINS = ['https://indianliberals.in', 'https://www.indianliberals.in'];

const LIMITS = { name: 120, email: 200, subject: 200, message: 5000, page: 300 };

interface Bucket {
  get(key: string): Promise<{ text(): Promise<string> } | null>;
  put(key: string, value: string, options?: unknown): Promise<unknown>;
  list(options?: { prefix?: string; limit?: number; cursor?: string }): Promise<{
    objects: { key: string; uploaded: string }[];
    truncated: boolean;
    cursor?: string;
  }>;
  delete(key: string): Promise<void>;
}

function corsHeaders(origin: string | null): Record<string, string> {
  const allowed = origin && SITE_ORIGINS.includes(origin) ? origin : SITE_ORIGINS[0];
  return {
    'access-control-allow-origin': allowed,
    'access-control-allow-methods': 'POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
    'access-control-max-age': '86400',
    vary: 'Origin',
  };
}

export const OPTIONS: APIRoute = ({ request }) =>
  new Response(null, { status: 204, headers: corsHeaders(request.headers.get('Origin')) });

/** A stable, non-identifying handle for one sender, for rate limiting only. */
async function senderKey(request: Request): Promise<string> {
  const ip = request.headers.get('CF-Connecting-IP') ?? 'unknown';
  const bytes = new TextEncoder().encode(`indianliberals-feedback:${ip}`);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest).slice(0, 8))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export const POST: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & { ARCHIVE: Bucket };
  const cors = corsHeaders(request.headers.get('Origin'));
  const reply = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json; charset=utf-8', ...cors },
    });

  try {
    const origin = request.headers.get('Origin');
    if (origin && !SITE_ORIGINS.includes(origin)) {
      return reply({ error: 'This form only works from the archive.' }, 403);
    }

    const raw = await request.text();
    if (raw.length > 20000) return reply({ error: 'That message is too long to send.' }, 413);

    let body: Record<string, unknown>;
    try {
      body = JSON.parse(raw);
    } catch {
      return reply({ error: 'We could not read that.' }, 400);
    }

    // The honeypot. A real person never sees this field, so anything in it is
    // a machine filling every input it finds. Answer as though it worked.
    if (typeof body.website === 'string' && body.website.trim() !== '') {
      return reply({ ok: true });
    }

    // Time on the form. A person takes seconds to write even a short note.
    const started = Number(body.startedAt);
    if (Number.isFinite(started) && Date.now() - started < 3000) {
      return reply({ error: 'That went through faster than we expected. Please try again.' }, 429);
    }

    const text = (value: unknown, cap: number) =>
      typeof value === 'string' ? value.trim().slice(0, cap) : '';

    const message = text(body.message, LIMITS.message);
    if (message.length < 10) {
      return reply({ error: 'Please write a little more, so we can act on it.' }, 422);
    }

    const email = text(body.email, LIMITS.email);
    if (email && !/^[^@\s]+@[^@\s.]+\.[^@\s]+$/.test(email)) {
      return reply({ error: 'That email address does not look right.' }, 422);
    }

    // One a minute per sender.
    //
    // R2 has no expiry, so the marker carries its own: the timestamp it was
    // written at, checked here. Without that the first message anyone sent
    // would be their last, which is a worse failure than the spam it prevents.
    const sender = await senderKey(request);
    const gate = `feedback/.recent/${sender}`;
    const held = await env.ARCHIVE.get(gate);
    if (held) {
      const at = Date.parse(await held.text());
      if (Number.isFinite(at) && Date.now() - at < 60000) {
        return reply(
          { error: 'You have just sent one. Give it a minute before sending another.' },
          429,
        );
      }
    }

    const now = new Date().toISOString();
    const id = `${now.replace(/[:.]/g, '-')}-${crypto.randomUUID().slice(0, 8)}`;
    const record = {
      id,
      received_at: now,
      name: text(body.name, LIMITS.name),
      email,
      subject: text(body.subject, LIMITS.subject),
      message,
      // Which page they were reading. This is what turns "the date is wrong"
      // into something an editor can act on without writing back to ask.
      page: text(body.page, LIMITS.page),
      kind: ['correction', 'contribution', 'rights', 'general'].includes(String(body.kind))
        ? String(body.kind)
        : 'general',
      country: request.headers.get('CF-IPCountry') ?? '',
      handled: false,
    };

    await env.ARCHIVE.put(`feedback/${id}.json`, JSON.stringify(record, null, 2), {
      httpMetadata: { contentType: 'application/json' },
    });
    await env.ARCHIVE.put(gate, now);

    return reply({ ok: true });
  } catch (error) {
    return reply({ error: `Could not send that: ${(error as Error).message}` }, 500);
  }
};

/** The inbox, for editors. Newest first. */
export const GET: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & { ARCHIVE: Bucket };
  try {
    await requireRole(request, env, 'sub_admin');
    const listing = await env.ARCHIVE.list({ prefix: 'feedback/', limit: 400 });
    const keys = listing.objects
      .map((o) => o.key)
      .filter((key) => key.endsWith('.json') && !key.startsWith('feedback/.recent/'))
      .sort()
      .reverse()
      .slice(0, 100);

    const items = [];
    for (const key of keys) {
      const held = await env.ARCHIVE.get(key);
      if (!held) continue;
      try {
        items.push(JSON.parse(await held.text()));
      } catch {
        /* a half-written object is not worth failing the whole inbox for */
      }
    }
    return json({ items, total: keys.length });
  } catch (error) {
    return refuse(error);
  }
};

/**
 * Mark one dealt with, so an inbox two people share does not get answered
 * twice. Who marked it is recorded, because that is the question anyone asks
 * next.
 */
export const PUT: APIRoute = async ({ request, locals }) => {
  const env = (locals as any).runtime.env as Env & { ARCHIVE: Bucket };
  try {
    const actor = await requireRole(request, env, 'sub_admin');
    const { id, handled } = (await request.json()) as { id?: string; handled?: boolean };
    if (!id || !/^[0-9TZa-z-]+$/.test(id)) return json({ error: 'that is not a message id' }, 400);

    const key = `feedback/${id}.json`;
    const held = await env.ARCHIVE.get(key);
    if (!held) return json({ error: 'no such message' }, 404);

    const record = JSON.parse(await held.text()) as Record<string, unknown>;
    record.handled = handled !== false;
    record.handled_by = record.handled ? actor.email : '';
    record.handled_at = record.handled ? new Date().toISOString() : '';

    await env.ARCHIVE.put(key, JSON.stringify(record, null, 2), {
      httpMetadata: { contentType: 'application/json' },
    });
    return json({ ok: true, handled: record.handled });
  } catch (error) {
    return refuse(error);
  }
};
