/**
 * Sveltia CMS OAuth proxy for indianliberals.in.
 *
 * Wraps the GitHub OAuth flow with an email allowlist check. Sveltia is
 * configured to point at this Worker as its `base_url`. The Worker:
 *   1. Forwards the user to GitHub's OAuth authorize endpoint
 *   2. Receives the authorization code on /callback
 *   3. Exchanges the code for an access token (server-side, using the secret)
 *   4. Fetches the user's primary GitHub email
 *   5. Checks the email against (super-admins ∪ sub-admins)
 *   6. If allowed: returns the token via Sveltia's postMessage protocol
 *      If denied:  returns a 403 with a clear message
 *
 * This is the ONLY enforcement point for "who can log in to the CMS."
 * The repo being public means we can't rely on GitHub repo visibility
 * for auth — this proxy is the gate.
 *
 * Sub-admins are also subject to GitHub repo permissions on commit.
 * They can only commit to data/admins.json if branch protection allows
 * (it doesn't — that file requires super-admin approval via CODEOWNERS).
 */

import { isSuperAdmin } from "./super-admins";

interface Env {
  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  GITHUB_REPO: string;
  ADMINS_PATH: string;
  ADMINS_CACHE_TTL_SECONDS: string;
  ALLOWED_REDIRECT_ORIGINS: string;
}

const GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize";
const GITHUB_OAUTH_TOKEN = "https://github.com/login/oauth/access_token";
const GITHUB_USER_EMAILS = "https://api.github.com/user/emails";

// In-memory cache for sub-admin list (per isolate). Short TTL so changes
// propagate quickly while avoiding rate limits.
let subAdminCache: { fetchedAt: number; emails: string[] } | null = null;

async function fetchSubAdmins(env: Env): Promise<string[]> {
  const ttlMs = parseInt(env.ADMINS_CACHE_TTL_SECONDS, 10) * 1000;
  const now = Date.now();
  if (subAdminCache && now - subAdminCache.fetchedAt < ttlMs) {
    return subAdminCache.emails;
  }

  // Always fetch from the protected branch (main).
  // This is the canonical sub-admin list. Any unauthorized edit would
  // require a merge to main, which is gated by CODEOWNERS.
  const url = `https://raw.githubusercontent.com/${env.GITHUB_REPO}/main/${env.ADMINS_PATH}`;
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "indianliberals-auth-proxy" },
      // Trust Cloudflare's HTTPS verification; no extra options needed.
    });
    if (!res.ok) {
      console.warn(`Sub-admin fetch failed: ${res.status} ${url}`);
      return subAdminCache?.emails ?? [];
    }
    const data = (await res.json()) as { admins?: string[] };
    const emails = Array.isArray(data.admins)
      ? data.admins.filter((e) => typeof e === "string")
      : [];
    subAdminCache = { fetchedAt: now, emails };
    return emails;
  } catch (err) {
    console.warn("Sub-admin fetch error:", err);
    return subAdminCache?.emails ?? [];
  }
}

async function isAuthorized(
  email: string | null,
  env: Env,
): Promise<{ allowed: boolean; tier: "super" | "sub" | "none" }> {
  if (!email) return { allowed: false, tier: "none" };
  if (isSuperAdmin(email)) return { allowed: true, tier: "super" };

  const subs = await fetchSubAdmins(env);
  const needle = email.trim().toLowerCase();
  const isSub = subs.some((e) => e.trim().toLowerCase() === needle);
  return isSub
    ? { allowed: true, tier: "sub" }
    : { allowed: false, tier: "none" };
}

function isAllowedOrigin(origin: string, env: Env): boolean {
  if (!origin) return false;
  const allowed = env.ALLOWED_REDIRECT_ORIGINS.split(",").map((s) =>
    s.trim().toLowerCase(),
  );
  return allowed.includes(origin.toLowerCase());
}

function html(body: string, status = 200): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

function deniedPage(email: string | null): Response {
  const safeEmail = email
    ? email.replace(/[<>&"']/g, (c) =>
        ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" })[c]!,
      )
    : "(unknown)";
  return html(
    `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>Access denied — Indian Liberals CMS</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 480px; margin: 6rem auto; padding: 0 1.5rem; line-height: 1.6; color: #2d2820; }
  h1 { font-weight: 600; }
  code { background: #f5f1ea; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
</style>
</head><body>
<h1>Access denied</h1>
<p>The email <code>${safeEmail}</code> is not authorised to use the Indian Liberals CMS.</p>
<p>If you should have access, ask a super-admin to add your GitHub primary email to the editor list.</p>
<p style="margin-top:2rem;color:#7a6f5e;font-size:0.9em">Indian Liberals · Centre for Civil Society</p>
</body></html>`,
    403,
  );
}

/**
 * Sveltia's auth flow (decap-style): the popup window is opened pointing
 * at our /auth endpoint. We redirect to GitHub. After GitHub redirects
 * back to /callback with a code, we exchange for a token, check the
 * email, then post the result back to the opener window via postMessage,
 * which Sveltia is listening for.
 */
function postMessageHTML(payload: object, targetOrigin: string): Response {
  const json = JSON.stringify(payload).replace(/</g, "\\u003c");
  return html(`<!doctype html>
<html><head><meta charset="utf-8"><title>Authorising…</title></head><body>
<script>
(function() {
  var msg = ${json};
  // Sveltia listens for a specific message format. We emit both
  // the modern (Sveltia-style) and legacy (Decap-style) formats.
  function send() {
    if (window.opener) {
      window.opener.postMessage('authorization:github:success:' + JSON.stringify({ token: msg.token, provider: 'github' }), '${targetOrigin}');
      window.opener.postMessage(msg, '${targetOrigin}');
    }
  }
  send();
  // Sveltia may re-emit the message after handshake — emit on receive too
  window.addEventListener('message', function(e) {
    if (e.data === 'authorizing:github') send();
  });
  // Close after a tick so the parent has time to receive
  setTimeout(function() { window.close(); }, 1000);
})();
</script>
<p>Authorising… you can close this window.</p>
</body></html>`);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // ─── /auth — entry point ────────────────────────────────────────
    // Sveltia opens this URL. We redirect to GitHub OAuth authorize.
    if (url.pathname === "/auth" || url.pathname === "/auth/") {
      const callerOrigin = url.searchParams.get("site_id") || url.searchParams.get("origin") || "";
      const state = crypto.randomUUID();
      // We need to remember the caller origin so we know where to postMessage
      // back. Encode it into the state parameter (signed in production —
      // here just opaque, since we verify against allowlist on callback).
      const stateWithOrigin = `${state}::${callerOrigin}`;
      const params = new URLSearchParams({
        client_id: env.GITHUB_CLIENT_ID,
        redirect_uri: `${url.origin}/callback`,
        scope: "repo,user:email",
        state: stateWithOrigin,
      });
      return Response.redirect(`${GITHUB_OAUTH_AUTHORIZE}?${params}`, 302);
    }

    // ─── /callback — GitHub returns here after OAuth ────────────────
    if (url.pathname === "/callback" || url.pathname === "/callback/") {
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state") || "";
      const [, callerOrigin] = state.split("::");
      const targetOrigin = isAllowedOrigin(callerOrigin, env) ? callerOrigin : "https://indianliberals.in";

      if (!code) {
        return html("<h1>Missing OAuth code</h1>", 400);
      }

      // Exchange code → access token
      const tokenRes = await fetch(GITHUB_OAUTH_TOKEN, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "User-Agent": "indianliberals-auth-proxy",
        },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code,
          redirect_uri: `${url.origin}/callback`,
        }),
      });
      if (!tokenRes.ok) {
        return html(`<h1>Token exchange failed</h1><p>${tokenRes.status}</p>`, 500);
      }
      const tokenData = (await tokenRes.json()) as { access_token?: string; error?: string };
      if (!tokenData.access_token) {
        return html(`<h1>No access token</h1><p>${tokenData.error || "Unknown error"}</p>`, 500);
      }
      const token = tokenData.access_token;

      // Fetch user emails
      const emailsRes = await fetch(GITHUB_USER_EMAILS, {
        headers: {
          "Authorization": `Bearer ${token}`,
          "User-Agent": "indianliberals-auth-proxy",
          "Accept": "application/vnd.github+json",
        },
      });
      if (!emailsRes.ok) {
        return html(`<h1>Email fetch failed</h1>`, 500);
      }
      type GhEmail = { email: string; primary: boolean; verified: boolean };
      const emails = (await emailsRes.json()) as GhEmail[];
      const primary = emails.find((e) => e.primary && e.verified);
      const email = primary?.email || emails.find((e) => e.verified)?.email || null;

      // Authorise
      const auth = await isAuthorized(email, env);
      if (!auth.allowed) {
        return deniedPage(email);
      }

      // Authorised — post the token back to the opener window
      return postMessageHTML(
        {
          token,
          provider: "github",
          email,
          tier: auth.tier,
        },
        targetOrigin,
      );
    }

    // ─── /me — debug endpoint, useful during setup ─────────────────
    if (url.pathname === "/me") {
      const auth_header = request.headers.get("Authorization");
      if (!auth_header) return html("<h1>No auth header</h1>", 401);
      const token = auth_header.replace(/^Bearer\s+/i, "");
      const r = await fetch(GITHUB_USER_EMAILS, {
        headers: {
          "Authorization": `Bearer ${token}`,
          "User-Agent": "indianliberals-auth-proxy",
          "Accept": "application/vnd.github+json",
        },
      });
      if (!r.ok) return html(`<h1>GitHub error ${r.status}</h1>`, r.status);
      const emails = (await r.json()) as Array<{ email: string; primary: boolean }>;
      const primary = emails.find((e) => e.primary)?.email || null;
      const auth = await isAuthorized(primary, env);
      return new Response(
        JSON.stringify({ email: primary, ...auth }, null, 2),
        { headers: { "Content-Type": "application/json" } },
      );
    }

    // ─── / — health check ──────────────────────────────────────────
    if (url.pathname === "/" || url.pathname === "/health") {
      return new Response(
        JSON.stringify({ ok: true, service: "indianliberals-auth" }, null, 2),
        { headers: { "Content-Type": "application/json" } },
      );
    }

    return new Response("Not found", { status: 404 });
  },
};
