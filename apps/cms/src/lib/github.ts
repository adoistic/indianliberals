/**
 * Committing on an editor's behalf.
 *
 * Editors sign in with Firebase and never touch GitHub. The CMS holds one
 * GitHub App installation, scoped to contents:write on a single repository,
 * and commits for them. The commit message names the person who made the
 * change, so the repository history stays a record of who did what even though
 * none of them has a GitHub account.
 *
 * Installation tokens last an hour; we cache one in the isolate and mint
 * another when it is close to expiring.
 */

export interface GitHubEnv {
  GITHUB_APP_ID: string;
  GITHUB_APP_INSTALLATION_ID: string;
  GITHUB_APP_PRIVATE_KEY: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
}

let tokenCache: { token: string; expires: number } | null = null;

/** DER length octets: short form below 128, long form above it. */
function derLength(length: number): number[] {
  if (length < 0x80) return [length];
  const bytes: number[] = [];
  let rest = length;
  while (rest > 0) {
    bytes.unshift(rest & 0xff);
    rest >>= 8;
  }
  return [0x80 | bytes.length, ...bytes];
}

/**
 * Wrap a PKCS#1 RSAPrivateKey in the PKCS#8 envelope.
 *
 * This is load-bearing. GitHub hands out App keys as PKCS#1, the format whose
 * header reads "BEGIN RSA PRIVATE KEY", and WebCrypto's importKey only accepts
 * PKCS#8. Node's crypto.sign takes either, which is why the setup scripts have
 * always worked and why this went unnoticed: nothing that ran outside a Worker
 * ever exercised it.
 *
 * The envelope is a SEQUENCE of three things: an INTEGER version of zero, the
 * algorithm identifier for rsaEncryption, and the original key as an OCTET
 * STRING.
 */
function pkcs1ToPkcs8(key: Uint8Array): Uint8Array<ArrayBuffer> {
  // SEQUENCE { OID 1.2.840.113549.1.1.1 (rsaEncryption), NULL }
  const algorithm = [
    0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00,
  ];
  const version = [0x02, 0x01, 0x00];
  const octet = [0x04, ...derLength(key.length)];
  const inner = version.length + algorithm.length + octet.length + key.length;
  const header = [0x30, ...derLength(inner)];

  const out = new Uint8Array(new ArrayBuffer(header.length + inner));
  out.set(header, 0);
  let at = header.length;
  out.set(version, at);
  at += version.length;
  out.set(algorithm, at);
  at += algorithm.length;
  out.set(octet, at);
  at += octet.length;
  out.set(key, at);
  return out;
}

/**
 * The private key as the bytes WebCrypto wants, whichever form it arrived in.
 *
 * Both are accepted because both are things a person can plausibly paste into
 * a secret: PKCS#1 is what GitHub gives you, PKCS#8 is what you get if you have
 * run the key through openssl at some point.
 */
function pemToPkcs8(pem: string): Uint8Array<ArrayBuffer> {
  const isPkcs1 = /BEGIN RSA PRIVATE KEY/.test(pem);
  const body = pem
    .replace(/-----(BEGIN|END) (RSA )?PRIVATE KEY-----/g, '')
    .replace(/\s+/g, '');
  const binary = atob(body);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return isPkcs1 ? pkcs1ToPkcs8(bytes) : bytes;
}

const b64url = (bytes: Uint8Array | string) => {
  const binary =
    typeof bytes === 'string' ? bytes : String.fromCharCode(...bytes);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

async function appJwt(env: GitHubEnv): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  // Backdated a minute so a fast clock does not get the token rejected.
  const payload = b64url(
    JSON.stringify({ iat: now - 60, exp: now + 540, iss: env.GITHUB_APP_ID }),
  );
  const key = await crypto.subtle.importKey(
    'pkcs8',
    pemToPkcs8(env.GITHUB_APP_PRIVATE_KEY),
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const signature = new Uint8Array(
    await crypto.subtle.sign(
      'RSASSA-PKCS1-v1_5',
      key,
      new TextEncoder().encode(`${header}.${payload}`),
    ),
  );
  return `${header}.${payload}.${b64url(signature)}`;
}

async function installationToken(env: GitHubEnv): Promise<string> {
  if (tokenCache && tokenCache.expires - Date.now() > 120_000) return tokenCache.token;
  const jwt = await appJwt(env);
  const response = await fetch(
    `https://api.github.com/app/installations/${env.GITHUB_APP_INSTALLATION_ID}/access_tokens`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${jwt}`,
        'User-Agent': 'thothica-cms',
      },
    },
  );
  if (!response.ok) {
    throw new Error(`GitHub refused an installation token: ${response.status} ${await response.text()}`);
  }
  const data = (await response.json()) as { token: string; expires_at: string };
  tokenCache = { token: data.token, expires: Date.parse(data.expires_at) };
  return data.token;
}

async function api(env: GitHubEnv, path: string, init: RequestInit = {}) {
  const token = await installationToken(env);
  const response = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'User-Agent': 'thothica-cms',
      ...(init.headers || {}),
    },
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`${path}: ${response.status} ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : {};
}

const repoPath = (env: GitHubEnv, p: string) =>
  `/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/${p}`;

export interface ExistingFile {
  content: string;
  sha: string;
}

/** Read a file, or null when it does not exist yet. */
export async function readFile(env: GitHubEnv, path: string): Promise<ExistingFile | null> {
  try {
    const data = await api(
      env,
      repoPath(env, `contents/${encodeURI(path)}?ref=${env.GITHUB_BRANCH}`),
    );
    const binary = atob(String(data.content).replace(/\n/g, ''));
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
    return { content: new TextDecoder().decode(bytes), sha: data.sha };
  } catch (error) {
    if (String(error).includes('404')) return null;
    throw error;
  }
}

export interface CommitRequest {
  path: string;
  content: string;
  /** What changed, in one line, without the actor's name. */
  summary: string;
  actor: { email: string; name?: string };
  /** Passing the sha we read guards against overwriting a concurrent edit. */
  sha?: string;
}

/**
 * Write one file and commit it.
 *
 * The message credits the editor by name and address. The App is the author of
 * record because it holds the key, so without this the history would say
 * "Thothica CMS" for every change anyone ever made.
 */
export async function commitFile(env: GitHubEnv, request: CommitRequest) {
  const who = request.actor.name
    ? `${request.actor.name} <${request.actor.email}>`
    : request.actor.email;

  const message = `${request.summary}\n\nEdited in Thothica CMS by ${who}.`;

  const bytes = new TextEncoder().encode(request.content);
  const base64 = btoa(String.fromCharCode(...bytes));

  return api(env, repoPath(env, `contents/${encodeURI(request.path)}`), {
    method: 'PUT',
    body: JSON.stringify({
      message,
      content: base64,
      branch: env.GITHUB_BRANCH,
      ...(request.sha ? { sha: request.sha } : {}),
      committer: { name: 'Thothica CMS', email: 'cms@thothica.com' },
      author: { name: request.actor.name || request.actor.email, email: request.actor.email },
    }),
  });
}

export interface BatchFile {
  path: string;
  /** Text content. Give exactly one of content or base64. */
  content?: string;
  /** Binary content, already base64-encoded: pictures ride along this way. */
  base64?: string;
}

/**
 * Write many files as a single commit.
 *
 * The contents API used above writes one file per commit, which is right for a
 * person correcting a publisher and wrong for someone approving fifty scanned
 * pamphlets at once: fifty commits means fifty site builds, and the site takes
 * about twenty-five minutes to build. This goes through the git data API
 * instead: a blob per file, one tree, one commit, one move of the branch ref,
 * so a batch of any size costs exactly one rebuild.
 *
 * It is also atomic in the way that matters. Everything is staged against the
 * branch head we read at the start, and the only mutating step is the final ref
 * update. If anything fails before then, nothing has moved; if the ref update
 * itself fails because somebody committed while we worked, it fails cleanly
 * rather than half-writing the batch.
 */
export async function commitFiles(
  env: GitHubEnv,
  files: BatchFile[],
  summary: string,
  actor: { email: string; name?: string },
) {
  if (!files.length) throw new Error('commitFiles was given nothing to commit');

  const who = actor.name ? `${actor.name} <${actor.email}>` : actor.email;
  const message = `${summary}\n\nEdited in Thothica CMS by ${who}.`;

  // Where the branch is now. Everything below is built on this exact commit,
  // so a concurrent push makes the final step fail instead of silently
  // clobbering their work.
  const ref = await api(
    env,
    repoPath(env, `git/ref/heads/${encodeURIComponent(env.GITHUB_BRANCH)}`),
  );
  const headSha = ref.object.sha as string;
  const headCommit = await api(env, repoPath(env, `git/commits/${headSha}`));

  // A blob per file, sent as base64 so a Marathi title survives the trip.
  // Eight at a time: enough to be quick over fifty files, few enough that
  // GitHub's secondary rate limit never sees a burst worth throttling.
  const blobs: { path: string; sha: string }[] = [];
  for (let i = 0; i < files.length; i += 8) {
    const slice = await Promise.all(
      files.slice(i, i + 8).map(async (file) => {
        let encoded = file.base64;
        if (encoded === undefined) {
          const bytes = new TextEncoder().encode(file.content ?? '');
          let binary = '';
          for (const byte of bytes) binary += String.fromCharCode(byte);
          encoded = btoa(binary);
        }
        const blob = await api(env, repoPath(env, 'git/blobs'), {
          method: 'POST',
          body: JSON.stringify({ content: encoded, encoding: 'base64' }),
        });
        return { path: file.path, sha: blob.sha as string };
      }),
    );
    blobs.push(...slice);
  }

  const tree = await api(env, repoPath(env, 'git/trees'), {
    method: 'POST',
    body: JSON.stringify({
      base_tree: headCommit.tree.sha,
      tree: blobs.map((blob) => ({
        path: blob.path,
        mode: '100644',
        type: 'blob',
        sha: blob.sha,
      })),
    }),
  });

  const commit = await api(env, repoPath(env, 'git/commits'), {
    method: 'POST',
    body: JSON.stringify({
      message,
      tree: tree.sha,
      parents: [headSha],
      committer: { name: 'Thothica CMS', email: 'cms@thothica.com' },
      author: { name: actor.name || actor.email, email: actor.email },
    }),
  });

  await api(env, repoPath(env, `git/refs/heads/${encodeURIComponent(env.GITHUB_BRANCH)}`), {
    method: 'PATCH',
    body: JSON.stringify({ sha: commit.sha, force: false }),
  });

  return {
    sha: commit.sha as string,
    url: `https://github.com/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/commit/${commit.sha}`,
    files: files.length,
  };
}

export async function deleteFile(
  env: GitHubEnv,
  path: string,
  sha: string,
  summary: string,
  actor: { email: string; name?: string },
) {
  const who = actor.name ? `${actor.name} <${actor.email}>` : actor.email;
  return api(env, repoPath(env, `contents/${encodeURI(path)}`), {
    method: 'DELETE',
    body: JSON.stringify({
      message: `${summary}\n\nRemoved in Thothica CMS by ${who}.`,
      sha,
      branch: env.GITHUB_BRANCH,
      committer: { name: 'Thothica CMS', email: 'cms@thothica.com' },
    }),
  });
}

/** Every slug in a collection, for the entity pickers. */
export async function listCollection(env: GitHubEnv, collection: string, root: string) {
  const data = await api(
    env,
    repoPath(env, `contents/${encodeURI(`${root}/${collection}`)}?ref=${env.GITHUB_BRANCH}`),
  );
  if (!Array.isArray(data)) return [];
  return data
    .filter((f: any) => f.type === 'file' && f.name.endsWith('.md'))
    .map((f: any) => ({ slug: f.name.replace(/\.mdx?$/, ''), sha: f.sha, path: f.path }));
}
