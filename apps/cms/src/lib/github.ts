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

function pemToPkcs8(pem: string): Uint8Array<ArrayBuffer> {
  const body = pem
    .replace(/-----(BEGIN|END) (RSA )?PRIVATE KEY-----/g, '')
    .replace(/\s+/g, '');
  const binary = atob(body);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
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
