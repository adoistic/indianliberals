// Minimal GitHub Contents-API client for the ThePrint ingest worker.
//
// Three operations are needed:
//   1. getFile(path) — returns { sha, content } or null if 404.
//   2. lastCommitAuthor(path) — returns the GitHub username/email of the
//      last person who touched the file. Used for admin-edit detection
//      (Critical Gap T20) — if the last commit was NOT the bot, we skip
//      the cron update so we don't trample editor work.
//   3. putFile(path, content, sha?, message) — creates or updates a file.
//      Pass sha=undefined for new files; pass the current sha for updates.
//
// All requests use a fine-grained PAT in the worker's GITHUB_TOKEN secret.
// The token is scoped to one repo with Contents: read+write.

export interface GhConfig {
  token: string;
  repo: string;        // "owner/repo"
  branch: string;
  botEmail: string;
  botName: string;
}

export interface GhFile {
  sha: string;
  content: string;     // decoded UTF-8 content
}

export class GitHubClient {
  private headers: Record<string, string>;
  private base: string;

  constructor(private cfg: GhConfig) {
    this.base = `https://api.github.com/repos/${cfg.repo}`;
    this.headers = {
      'Authorization': `Bearer ${cfg.token}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'indianliberals-theprint-ingest/0.1',
    };
  }

  /** Read a file. Returns null on 404 (file doesn't exist), throws on other errors. */
  async getFile(path: string): Promise<GhFile | null> {
    const url = `${this.base}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}?ref=${this.cfg.branch}`;
    const r = await fetch(url, { headers: this.headers });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(`GET ${path}: ${r.status} ${await r.text()}`);
    const j = (await r.json()) as { sha: string; content: string; encoding: string };
    if (j.encoding !== 'base64') throw new Error(`Unexpected encoding for ${path}: ${j.encoding}`);
    // atob is available in Workers runtime
    const decoded = decodeBase64Utf8(j.content);
    return { sha: j.sha, content: decoded };
  }

  /**
   * Inspect the most recent commit that touched `path`. Returns the author
   * identity (login / email) so the caller can compare against the bot
   * identity and decide whether the file is admin-edited.
   *
   * Returns null if the file has no commit history (i.e., it doesn't
   * exist yet — the caller should treat that as "safe to create").
   */
  async lastCommitAuthor(path: string): Promise<{
    login?: string;
    email?: string;
    name?: string;
    sha?: string;
  } | null> {
    const url = `${this.base}/commits?path=${encodeURIComponent(path)}&per_page=1&sha=${this.cfg.branch}`;
    const r = await fetch(url, { headers: this.headers });
    if (!r.ok) throw new Error(`GET commits ${path}: ${r.status} ${await r.text()}`);
    const commits = (await r.json()) as Array<{
      sha: string;
      author: { login: string } | null;
      commit: { author: { name: string; email: string } };
    }>;
    if (!commits.length) return null;
    const c = commits[0];
    return {
      sha: c.sha,
      login: c.author?.login,
      email: c.commit?.author?.email,
      name: c.commit?.author?.name,
    };
  }

  /** Create or update a file. Pass sha for updates, omit for creation. */
  async putFile(
    path: string,
    content: string,
    opts: { sha?: string; message: string },
  ): Promise<{ sha: string }> {
    const url = `${this.base}/contents/${encodeURIComponent(path).replace(/%2F/g, '/')}`;
    const body = {
      message: opts.message,
      content: encodeBase64Utf8(content),
      branch: this.cfg.branch,
      sha: opts.sha,
      committer: { name: this.cfg.botName, email: this.cfg.botEmail },
      author:    { name: this.cfg.botName, email: this.cfg.botEmail },
    };
    const r = await fetch(url, {
      method: 'PUT',
      headers: { ...this.headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`PUT ${path}: ${r.status} ${await r.text()}`);
    const j = (await r.json()) as { content: { sha: string } };
    return { sha: j.content.sha };
  }
}

/**
 * Decide whether a file was last edited by an admin (NOT the bot).
 * If so, the caller MUST skip writing to that path during the cron run
 * — this is the Critical Gap T20 fix: don't trample editor work.
 *
 * Decision rule:
 *   - No commit history → treat as "not admin-edited" (file is new).
 *   - Last commit author email matches bot email → not admin-edited.
 *   - Anything else → admin-edited; skip.
 *
 * We compare on email because the email is set on every commit, whereas
 * the GitHub `login` is only present when the author is a registered
 * GitHub user (cron commits via PAT may not always populate it).
 */
export function isAdminEdited(
  lastCommit: Awaited<ReturnType<GitHubClient['lastCommitAuthor']>>,
  botEmail: string,
): boolean {
  if (!lastCommit) return false;
  if (!lastCommit.email) return true; // unknown author — fail closed
  return lastCommit.email.toLowerCase() !== botEmail.toLowerCase();
}

// ─── base64 helpers (Workers runtime uses atob/btoa on ASCII; we need UTF-8) ───

function encodeBase64Utf8(s: string): string {
  const bytes = new TextEncoder().encode(s);
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

function decodeBase64Utf8(b64: string): string {
  const binary = atob(b64.replace(/\s+/g, ''));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}
