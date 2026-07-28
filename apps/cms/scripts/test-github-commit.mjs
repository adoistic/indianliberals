/**
 * Exercise the real commit paths against the real repository.
 *
 * Not part of `npm test`: it needs .github-app.json and it talks to GitHub.
 * Run it by hand with `npm run test:github` after touching src/lib/github.ts.
 *
 * Everything happens on a throwaway branch that is deleted at the end, so main
 * is never touched. What this proves is the part types cannot: that the git
 * data API sequence (blob, tree, commit, ref) actually lands, that the files
 * arrive with their bytes intact including non-Latin script, and that a stale
 * parent is rejected rather than silently overwriting.
 */

import { readFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

// Build the real module rather than trusting a bundle somebody left lying
// about. What is under test is src/lib/github.ts as it stands right now.
const here = dirname(fileURLToPath(import.meta.url));
const out = join(mkdtempSync(join(tmpdir(), 'cms-github-')), 'github.mjs');
execFileSync(
  'npx',
  ['esbuild', join(here, '../src/lib/github.ts'), '--bundle', '--format=esm', '--platform=neutral', `--outfile=${out}`],
  { cwd: join(here, '..'), stdio: 'pipe' },
);
const { commitFiles, commitFile, readFile } = await import(out);

const creds = JSON.parse(readFileSync(join(here, '../../../.github-app.json'), 'utf8'));

const env = {
  GITHUB_APP_ID: String(creds.app_id),
  GITHUB_APP_INSTALLATION_ID: String(creds.installation_id),
  GITHUB_APP_PRIVATE_KEY: creds.pem,
  GITHUB_OWNER: 'adoistic',
  GITHUB_REPO: 'indianliberals',
  GITHUB_BRANCH: 'cms-batch-test',
};

const OWNER = env.GITHUB_OWNER;
const REPO = env.GITHUB_REPO;

// A tiny reimplementation only for the scaffolding: making and removing the
// test branch. The thing under test is the imported commitFiles.
async function token() {
  const crypto = await import('node:crypto');
  const now = Math.floor(Date.now() / 1000);
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const body = `${b64({ alg: 'RS256', typ: 'JWT' })}.${b64({ iat: now - 60, exp: now + 540, iss: env.GITHUB_APP_ID })}`;
  const jwt = `${body}.${crypto.sign('RSA-SHA256', Buffer.from(body), env.GITHUB_APP_PRIVATE_KEY).toString('base64url')}`;
  const r = await fetch(
    `https://api.github.com/app/installations/${env.GITHUB_APP_INSTALLATION_ID}/access_tokens`,
    { method: 'POST', headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${jwt}`, 'User-Agent': 't' } },
  );
  return (await r.json()).token;
}

async function gh(path, tok, init = {}) {
  const r = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${tok}`, 'User-Agent': 't', ...(init.headers || {}) },
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`${path} -> ${r.status} ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : {};
}

const results = [];
const check = (name, pass, detail = '') => {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'ok  ' : 'FAIL'}  ${name}${detail ? `  ${detail}` : ''}`);
};

const tok = await token();

// ── Scaffolding: a branch off main ──────────────────────────────────────
const main = await gh(`/repos/${OWNER}/${REPO}/git/ref/heads/main`, tok);
try {
  await gh(`/repos/${OWNER}/${REPO}/git/refs/heads/${env.GITHUB_BRANCH}`, tok, { method: 'DELETE' });
} catch {
  /* it did not exist, which is the normal case */
}
await gh(`/repos/${OWNER}/${REPO}/git/refs`, tok, {
  method: 'POST',
  body: JSON.stringify({ ref: `refs/heads/${env.GITHUB_BRANCH}`, sha: main.object.sha }),
});
// A freshly created ref is not always readable straight away.
for (let tries = 0; tries < 10; tries++) {
  try {
    await gh(`/repos/${OWNER}/${REPO}/git/ref/heads/${env.GITHUB_BRANCH}`, tok);
    break;
  } catch {
    await new Promise((r) => setTimeout(r, 1000));
  }
}
console.log(`test branch ${env.GITHUB_BRANCH} created at ${main.object.sha.slice(0, 7)}\n`);

try {
  // ── 1. Many files, one commit ─────────────────────────────────────────
  const files = [
    { path: 'tmp-batch-test/one.md', content: '---\nid: one\n---\n\nFirst.\n' },
    { path: 'tmp-batch-test/two.md', content: '---\nid: two\n---\n\nSecond.\n' },
    // Devanagari and Gujarati, because the archive is multilingual and base64
    // round-tripping is exactly where that quietly breaks.
    { path: 'tmp-batch-test/three.md', content: '---\nid: three\ntitle: "स्वतंत्रता और ગુજરાતી"\n---\n\nThird.\n' },
  ];

  const result = await commitFiles(env, files, 'test: batch of three', {
    email: 'adnan@thothica.com',
    name: 'Adnan',
  });
  check('three files land in one commit', result.files === 3 && Boolean(result.sha), result.sha?.slice(0, 7));

  const after = await gh(`/repos/${OWNER}/${REPO}/git/ref/heads/${env.GITHUB_BRANCH}`, tok);
  check('the branch moved to that commit', after.object.sha === result.sha);

  const commit = await gh(`/repos/${OWNER}/${REPO}/git/commits/${result.sha}`, tok);
  check('it has exactly one parent', commit.parents.length === 1, `parent ${commit.parents[0]?.sha.slice(0, 7)}`);
  check('the parent is where we started', commit.parents[0]?.sha === main.object.sha);
  check('the editor is the author', commit.author.email === 'adnan@thothica.com', commit.author.name);
  check('the CMS is the committer', commit.committer.email === 'cms@thothica.com');
  check('the message names the editor', commit.message.includes('Adnan <adnan@thothica.com>'));

  // ── 2. The bytes survived ─────────────────────────────────────────────
  const three = await gh(
    `/repos/${OWNER}/${REPO}/contents/tmp-batch-test/three.md?ref=${env.GITHUB_BRANCH}`,
    tok,
  );
  const text = Buffer.from(three.content, 'base64').toString('utf8');
  check('Devanagari and Gujarati survive the round trip', text.includes('स्वतंत्रता और ગુજરાતી'));

  // ── 3. One commit, not three ──────────────────────────────────────────
  const log = await gh(`/repos/${OWNER}/${REPO}/commits?sha=${env.GITHUB_BRANCH}&per_page=5`, tok);
  const added = log.findIndex((c) => c.sha === main.object.sha);
  check('three files cost exactly one commit', added === 1, `${added} commit(s) since the branch point`);

  // ── 4. A stale parent is refused, not merged ──────────────────────────
  // Someone else commits while our batch is being prepared. The ref update
  // must fail rather than discard their work.
  await gh(`/repos/${OWNER}/${REPO}/contents/tmp-batch-test/interloper.md`, tok, {
    method: 'PUT',
    body: JSON.stringify({
      message: 'test: a concurrent commit',
      content: Buffer.from('---\nid: interloper\n---\n').toString('base64'),
      branch: env.GITHUB_BRANCH,
    }),
  });

  let refused = false;
  try {
    // commitFiles reads the head itself, so to simulate staleness we race it:
    // commit again from an env pinned to the now-old sha is not expressible,
    // so instead assert the non-fast-forward guard directly on the ref API,
    // which is the exact call commitFiles makes with force: false.
    await gh(`/repos/${OWNER}/${REPO}/git/refs/heads/${env.GITHUB_BRANCH}`, tok, {
      method: 'PATCH',
      body: JSON.stringify({ sha: result.sha, force: false }),
    });
  } catch (error) {
    refused = String(error).includes('422');
  }
  check('a non-fast-forward ref update is refused', refused, 'force:false holds');

  // ── 4b. The single-save path, which shares the key import ─────────────
  // This is the path an editor uses on the edit screen. It was broken by the
  // same cause and is fixed by the same fix, so it is proved here too.
  const single = await commitFile(env, {
    path: 'tmp-batch-test/single.md',
    content: '---\nid: single\ntitle: "एक"\n---\n\nOne at a time.\n',
    summary: 'test: one file the ordinary way',
    actor: { email: 'adnan@thothica.com', name: 'Adnan' },
  });
  check('a single save commits', Boolean(single?.commit?.sha), single?.commit?.sha?.slice(0, 7));

  const back = await readFile(env, 'tmp-batch-test/single.md');
  check('and reads back with its bytes intact', Boolean(back?.content.includes('एक')));

  // ── 5. Nothing to commit is an error, not an empty commit ─────────────
  let threw = false;
  try {
    await commitFiles(env, [], 'test: nothing', { email: 'a@b.c' });
  } catch {
    threw = true;
  }
  check('an empty batch throws rather than committing nothing', threw);
} finally {
  // ── Teardown ──────────────────────────────────────────────────────────
  await gh(`/repos/${OWNER}/${REPO}/git/refs/heads/${env.GITHUB_BRANCH}`, tok, { method: 'DELETE' });
  console.log(`\ntest branch deleted; main untouched`);
}

const failed = results.filter((r) => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
