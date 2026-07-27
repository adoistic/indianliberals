#!/usr/bin/env node
/**
 * Second half of GitHub App setup: find the installation, then hand the
 * credentials to Cloudflare.
 *
 * Run after installing the app on the repository. It mints a short-lived app
 * JWT from the private key, asks GitHub which installation covers
 * adoistic/indianliberals, verifies the app can actually write there, and
 * prints the two `wrangler secret put` commands with the values ready on stdin.
 *
 * Usage:
 *   node apps/cms/scripts/finish-github-app.mjs
 *   node apps/cms/scripts/finish-github-app.mjs --set   (pipes the secrets in for you)
 */

import { readFileSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "../../..");
const CREDS = resolve(REPO_ROOT, ".github-app.json");
const OWNER = "adoistic";
const REPO = "indianliberals";

function appJwt({ app_id, pem }) {
  // GitHub wants an RS256 JWT signed with the app's private key, valid for at
  // most ten minutes. Backdate by a minute so a slightly fast clock does not
  // get the token rejected.
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "RS256", typ: "JWT" };
  const payload = { iat: now - 60, exp: now + 540, iss: String(app_id) };
  const b64 = (o) =>
    Buffer.from(JSON.stringify(o)).toString("base64url");
  const body = `${b64(header)}.${b64(payload)}`;
  const signature = crypto.sign("RSA-SHA256", Buffer.from(body), pem).toString("base64url");
  return `${body}.${signature}`;
}

async function gh(path, token, init = {}) {
  const response = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "User-Agent": "thothica-cms-setup",
      ...(init.headers || {}),
    },
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`${path} -> ${response.status}\n${text.slice(0, 400)}`);
  return text ? JSON.parse(text) : {};
}

const creds = JSON.parse(readFileSync(CREDS, "utf8"));
const jwt = appJwt(creds);

const installations = await gh("/app/installations", jwt);
const installation = installations.find(
  (i) => i.account?.login?.toLowerCase() === OWNER.toLowerCase(),
);

if (!installation) {
  console.error(
    `\nThe app is not installed on ${OWNER} yet.\n` +
      `Install it here, then run this again:\n  ${creds.html_url}/installations/new\n`,
  );
  process.exit(1);
}

// Prove it can actually write before declaring success. An app installed with
// the wrong repository selected fails here rather than at the first save.
const token = await gh(
  `/app/installations/${installation.id}/access_tokens`,
  jwt,
  { method: "POST" },
);
const repos = await gh("/installation/repositories", token.token);
const target = repos.repositories.find((r) => r.name === REPO);

if (!target) {
  console.error(
    `\nInstalled, but ${OWNER}/${REPO} is not in its repository list.\n` +
      `Open ${creds.html_url}/installations and add it.\n`,
  );
  process.exit(1);
}

const permissions = token.permissions || {};
if (permissions.contents !== "write") {
  console.error(`\nThe installation lacks contents:write. It has: ${JSON.stringify(permissions)}\n`);
  process.exit(1);
}

creds.installation_id = installation.id;
writeFileSync(CREDS, JSON.stringify(creds, null, 2), { mode: 0o600 });

console.log(`\napp id          ${creds.app_id}`);
console.log(`installation    ${installation.id}`);
console.log(`repository      ${target.full_name}`);
console.log(`permissions     ${JSON.stringify(permissions)}`);
console.log(`\nVerified: the app can write to ${target.full_name}.`);

if (process.argv.includes("--set")) {
  const cms = resolve(REPO_ROOT, "apps/cms");
  const put = (name, value) => {
    execSync(`npx wrangler secret put ${name}`, { cwd: cms, input: value, stdio: ["pipe", "inherit", "inherit"] });
  };
  put("GITHUB_APP_ID", String(creds.app_id));
  put("GITHUB_APP_INSTALLATION_ID", String(installation.id));
  put("GITHUB_APP_PRIVATE_KEY", creds.pem);
  console.log("\nSecrets set on the Cloudflare Worker.");
} else {
  console.log(`\nTo push these into Cloudflare:\n  node apps/cms/scripts/finish-github-app.mjs --set\n`);
}
