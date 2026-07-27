#!/usr/bin/env node
/**
 * Register the "Thothica CMS" GitHub App and capture its credentials.
 *
 * GitHub will not mint an app from an API call: a human has to approve the
 * creation under their account. But it will accept a manifest, which means we
 * can pre-fill every field and reduce the job to one click. GitHub then hands
 * back the app id and the private key directly, so nobody has to copy a PEM out
 * of a browser and paste it somewhere.
 *
 * The flow, from the GitHub docs:
 *   1. POST a manifest to github.com/settings/apps/new
 *   2. the user confirms, GitHub redirects back with a temporary code
 *   3. POST /app-manifests/<code>/conversions returns { id, pem, ... }
 * The code is valid for one hour.
 *
 * Usage:
 *   node apps/cms/scripts/create-github-app.mjs
 *
 * Writes .github-app.json next to this repo's root. That file holds a private
 * key: it is gitignored, and the next step is to push it into Cloudflare with
 *   npx wrangler secret put GITHUB_APP_PRIVATE_KEY < the pem
 */

import http from "node:http";
import { exec } from "node:child_process";
import { writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "../../..");
const PORT = 8899;
const REDIRECT = `http://localhost:${PORT}/callback`;
const OWNER = "adoistic";
const REPO = "indianliberals";

const state = crypto.randomBytes(16).toString("hex");

// Only what the CMS actually does. `contents: write` is the whole job: read a
// file, write a file, commit. No webhooks, no issues, no org access, nothing
// that would let this token do something surprising if it ever leaked.
const manifest = {
  name: "Thothica CMS",
  url: "https://cms.indianliberals.in",
  description:
    "Editorial interface for the Indian Liberals archive. Commits content on behalf of signed-in editors.",
  public: false,
  redirect_url: REDIRECT,
  hook_attributes: { url: "https://cms.indianliberals.in/api/webhook", active: false },
  default_permissions: { contents: "write", metadata: "read" },
  default_events: [],
};

const page = `<!doctype html>
<html><head><meta charset="utf-8"><title>Create the Thothica CMS GitHub App</title>
<style>
 body{font-family:-apple-system,system-ui,sans-serif;background:#FCFCFA;color:#4F3419;
      display:grid;place-items:center;min-height:100vh;margin:0}
 .card{max-width:34rem;background:#fff;border:1px solid #E3DDD5;border-radius:16px;padding:2.5rem}
 h1{font-family:Georgia,serif;font-weight:500;margin:0 0 .25rem}
 .rule{width:44px;height:1px;background:#B8956A;margin:1rem 0 1.25rem}
 p{color:#6F665E;line-height:1.6}
 ul{color:#6F665E;line-height:1.7}
 button{background:#624120;color:#FCF7F1;border:0;border-radius:10px;padding:.8rem 1.4rem;
        font-size:1rem;cursor:pointer;margin-top:1rem}
</style></head>
<body><div class="card">
<h1>Create the Thothica CMS app</h1><div class="rule"></div>
<p>This registers a GitHub App called <strong>Thothica CMS</strong> on your account,
pre-configured. You will see GitHub's confirmation page next.</p>
<p>What it will be allowed to do:</p>
<ul>
  <li>Read and write files in <strong>${OWNER}/${REPO}</strong>, and nothing else</li>
  <li>No webhooks, no issues, no access to other repositories</li>
</ul>
<form action="https://github.com/settings/apps/new?state=${state}" method="post">
  <input type="hidden" name="manifest" value='${JSON.stringify(manifest).replace(/'/g, "&apos;")}'>
  <button type="submit">Create the app on GitHub</button>
</form>
</div></body></html>`;

const done = (body) =>
  `<!doctype html><html><head><meta charset="utf-8"><title>Done</title>
<style>body{font-family:-apple-system,system-ui,sans-serif;background:#FCFCFA;color:#4F3419;
display:grid;place-items:center;min-height:100vh;margin:0}
.card{max-width:34rem;background:#fff;border:1px solid #E3DDD5;border-radius:16px;padding:2.5rem}
h1{font-family:Georgia,serif;font-weight:500}p{color:#6F665E;line-height:1.6}
code{background:#F4EFE8;padding:.15rem .4rem;border-radius:4px}</style></head>
<body><div class="card">${body}</div></body></html>`;

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === "/") {
    res.writeHead(200, { "Content-Type": "text/html" });
    return res.end(page);
  }

  if (url.pathname !== "/callback") {
    res.writeHead(404);
    return res.end();
  }

  if (url.searchParams.get("state") !== state) {
    res.writeHead(400, { "Content-Type": "text/html" });
    return res.end(done("<h1>State mismatch</h1><p>Start again.</p>"));
  }

  const code = url.searchParams.get("code");
  if (!code) {
    res.writeHead(400, { "Content-Type": "text/html" });
    return res.end(done("<h1>No code returned</h1><p>Start again.</p>"));
  }

  const response = await fetch(`https://api.github.com/app-manifests/${code}/conversions`, {
    method: "POST",
    headers: { Accept: "application/vnd.github+json", "User-Agent": "thothica-cms-setup" },
  });

  if (!response.ok) {
    const text = await response.text();
    res.writeHead(500, { "Content-Type": "text/html" });
    res.end(done(`<h1>GitHub refused the exchange</h1><pre>${text.slice(0, 500)}</pre>`));
    console.error(`\nexchange failed: ${response.status}\n${text}`);
    server.close();
    return;
  }

  const app = await response.json();
  const out = resolve(REPO_ROOT, ".github-app.json");
  writeFileSync(
    out,
    JSON.stringify(
      { app_id: app.id, slug: app.slug, name: app.name, html_url: app.html_url, pem: app.pem },
      null,
      2,
    ),
    { mode: 0o600 },
  );

  const installUrl = `${app.html_url}/installations/new`;
  res.writeHead(200, { "Content-Type": "text/html" });
  res.end(
    done(
      `<h1>App created</h1>
       <p><strong>${app.name}</strong>, app id <code>${app.id}</code>.
       The private key is saved locally and is gitignored.</p>
       <p>One click left: install it on the repository.</p>
       <p><a href="${installUrl}">${installUrl}</a></p>`,
    ),
  );

  console.log(`\ncreated: ${app.name} (app id ${app.id})`);
  console.log(`credentials: ${out}  (gitignored, mode 600)`);
  console.log(`\nnow install it on the repo:\n  ${installUrl}`);
  console.log(`\nthen finish setup:\n  node apps/cms/scripts/finish-github-app.mjs\n`);
  server.close();
});

server.listen(PORT, () => {
  const url = `http://localhost:${PORT}/`;
  console.log(`Opening ${url}`);
  console.log("If the browser does not open, paste that into it.\n");
  exec(`open "${url}"`);
});
