// ThePrint ingest worker — scheduled (cron) handler.
//
// Daily flow:
//   1. Fetch the "Indian Liberals Matter" RSS feed.
//   2. Load the blocklist from the repo (data/theprint-blocklist.json).
//   3. For each feed item, in order, up to MAX_ITEMS_PER_RUN:
//        a. Skip if theprint_url is in the blocklist.
//        b. Compute the target file path: apps/site/src/content/theprint-mirror/<slug>.md
//        c. Read the existing file's last-commit author. If it was NOT
//           the bot (= admin edit), skip — Critical Gap T20 fix.
//        d. Generate the markdown body from the RSS item.
//        e. If the existing content is byte-identical, skip (no-op).
//        f. PUT the file via the GitHub Contents API.
//   4. Emit a structured log for the wrangler tail observability.
//
// Manual override: the worker also exposes a fetch handler so admins can
// hit the Worker URL with a shared HEADER secret to trigger a fresh
// ingest outside the cron schedule (A3 in the engagement plan).

import { GitHubClient, isAdminEdited } from './github';
import { parseRssFeed, slugFromUrl } from './rss';
import { rssItemToMarkdown } from './markdown';

interface Env {
  GITHUB_TOKEN: string;
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
  BOT_COMMIT_AUTHOR: string;
  BOT_COMMIT_EMAIL: string;
  RSS_FEED_URL: string;
  CONTENT_PATH: string;
  BLOCKLIST_PATH: string;
  MAX_ITEMS_PER_RUN: string;
  // Optional manual-trigger secret. If set, a fetch with header
  // `X-Ingest-Token: <value>` triggers an ad-hoc run.
  MANUAL_TRIGGER_TOKEN?: string;
}

interface IngestSummary {
  startedAt: string;
  finishedAt: string;
  itemsFetched: number;
  itemsConsidered: number;
  created: string[];
  updated: string[];
  skippedBlocklist: string[];
  skippedAdminEdit: string[];
  skippedNoChange: string[];
  errors: { slug: string; reason: string }[];
}

export default {
  async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runIngest(env, 'cron'));
  },
  async fetch(req: Request, env: Env): Promise<Response> {
    // Manual trigger via shared-secret header. Useful for admin-initiated
    // ingestion outside the cron window (A3).
    if (req.method === 'POST' && env.MANUAL_TRIGGER_TOKEN) {
      const provided = req.headers.get('X-Ingest-Token');
      if (provided !== env.MANUAL_TRIGGER_TOKEN) {
        return new Response('Forbidden', { status: 403 });
      }
      const summary = await runIngest(env, 'manual');
      return Response.json(summary);
    }
    return new Response(
      'indianliberals-theprint-ingest worker. Cron-scheduled daily; POST with X-Ingest-Token to trigger manually.',
      { headers: { 'Content-Type': 'text/plain' } },
    );
  },
};

async function runIngest(env: Env, mode: 'cron' | 'manual'): Promise<IngestSummary> {
  const summary: IngestSummary = {
    startedAt: new Date().toISOString(),
    finishedAt: '',
    itemsFetched: 0,
    itemsConsidered: 0,
    created: [],
    updated: [],
    skippedBlocklist: [],
    skippedAdminEdit: [],
    skippedNoChange: [],
    errors: [],
  };

  const log = (msg: string, extra?: object) => {
    console.log(JSON.stringify({ ts: new Date().toISOString(), worker: 'theprint-ingest', mode, msg, ...(extra || {}) }));
  };

  try {
    // 1. Fetch the RSS feed
    log('fetching_feed', { url: env.RSS_FEED_URL });
    const feedResp = await fetch(env.RSS_FEED_URL, {
      headers: {
        // Identify ourselves so ThePrint can rate-limit / contact us if needed.
        'User-Agent': 'indianliberals-theprint-ingest/0.1 (+https://indianliberals.in)',
        'Accept': 'application/rss+xml, application/xml, text/xml',
      },
    });
    if (!feedResp.ok) {
      throw new Error(`RSS fetch failed: ${feedResp.status} ${feedResp.statusText}`);
    }
    const feedXml = await feedResp.text();
    const items = parseRssFeed(feedXml);
    summary.itemsFetched = items.length;
    log('feed_parsed', { items: items.length });

    // 2. Load the blocklist (best-effort — empty if file missing)
    const gh = new GitHubClient({
      token: env.GITHUB_TOKEN,
      repo: env.GITHUB_REPO,
      branch: env.GITHUB_BRANCH,
      botEmail: env.BOT_COMMIT_EMAIL,
      botName: env.BOT_COMMIT_AUTHOR,
    });
    let blocklist: Set<string> = new Set();
    try {
      const blocklistFile = await gh.getFile(env.BLOCKLIST_PATH);
      if (blocklistFile) {
        const parsed = JSON.parse(blocklistFile.content) as { urls?: string[] };
        blocklist = new Set((parsed.urls || []).map((u) => u.toLowerCase()));
        log('blocklist_loaded', { count: blocklist.size });
      }
    } catch (e) {
      log('blocklist_load_failed', { error: String(e) });
      // Continue — empty blocklist is safe (ingest may overwrite an
      // intentionally-removed file, but the admin-edit guard catches that).
    }

    // 3. Iterate items
    const maxItems = parseInt(env.MAX_ITEMS_PER_RUN, 10) || 10;
    const mirroredOnIso = new Date().toISOString().slice(0, 10);

    for (const item of items.slice(0, maxItems)) {
      summary.itemsConsidered += 1;
      const slug = slugFromUrl(item.link, item.title);
      const path = `${env.CONTENT_PATH}/${slug}.md`;

      try {
        // (a) Blocklist
        if (blocklist.has(item.link.toLowerCase())) {
          summary.skippedBlocklist.push(slug);
          continue;
        }

        // (b) Admin-edit guard — Critical Gap T20 fix
        const lastCommit = await gh.lastCommitAuthor(path);
        if (isAdminEdited(lastCommit, env.BOT_COMMIT_EMAIL)) {
          summary.skippedAdminEdit.push(slug);
          log('skip_admin_edited', { slug, lastCommit });
          continue;
        }

        // (c) Generate target content
        const targetContent = rssItemToMarkdown(item, { mirroredOnIso, slug });

        // (d) Read existing for no-op detection
        const existing = await gh.getFile(path);
        if (existing && existing.content === targetContent) {
          summary.skippedNoChange.push(slug);
          continue;
        }

        // (e) Write
        const message = existing
          ? `chore(theprint-ingest): refresh ${slug}`
          : `feat(theprint-ingest): mirror ${slug}`;
        await gh.putFile(path, targetContent, { sha: existing?.sha, message });

        if (existing) summary.updated.push(slug);
        else summary.created.push(slug);
        log(existing ? 'updated' : 'created', { slug, url: item.link });
      } catch (e) {
        summary.errors.push({ slug, reason: String(e) });
        log('item_error', { slug, error: String(e) });
      }
    }
  } catch (e) {
    summary.errors.push({ slug: '__run__', reason: String(e) });
    log('run_error', { error: String(e) });
  }

  summary.finishedAt = new Date().toISOString();
  log('summary', summary as unknown as Record<string, unknown>);
  return summary;
}
