// ThePrint ingest — GitHub Actions / local runner.
//
// Same job as the Cloudflare Worker (src/index.ts), but instead of writing via
// the GitHub Contents API it writes straight into the checked-out repo. A
// scheduled GitHub Actions workflow (.github/workflows/theprint-ingest.yml)
// runs this weekly and commits any new/updated mirror files. This is what makes
// ThePrint actually auto-ingest without a Cloudflare deploy.
//
// Reuses src/rss.ts + src/markdown.ts so the Worker and the Action stay in
// lockstep. Run with: `npx tsx scripts/ingest-to-repo.ts` from this package,
// or from repo root via the workflow.

import { readFile, writeFile, stat } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { join, resolve } from 'node:path';
import { parseRssFeed, slugFromUrl, type RssItem } from '../src/rss';
import { rssItemToMarkdown } from '../src/markdown';
import { fetchWpRestItems } from '../src/wp-rest';

// Repo root: two levels up from apps/theprint-ingest, resolved from cwd so the
// workflow can run this from the repo root or the package dir.
const REPO_ROOT = resolve(process.env.GITHUB_WORKSPACE || process.cwd());

const CONTENT_PATH = process.env.CONTENT_PATH || 'apps/site/src/content/theprint-mirror';
const BLOCKLIST_PATH = process.env.BLOCKLIST_PATH || 'data/theprint-blocklist.json';
const MAX_ITEMS = parseInt(process.env.MAX_ITEMS_PER_RUN || '25', 10) || 25;
const BOT_EMAIL = process.env.BOT_COMMIT_EMAIL || 'theprint-ingest@indianliberals.in';
const RSS_FEED_URL =
  process.env.RSS_FEED_URL || 'https://theprint.in/category/opinion/indian-liberals-matter/feed/';

// Ingestion sources. English comes from the WordPress RSS feed. Hindi has no
// working RSS (the category /feed/ 404s), so it is pulled from the WordPress
// REST API instead — a genuinely separate path. Hindi is opt-in via
// INGEST_HINDI=1 so an English-only run stays unchanged.
type Source =
  | { type: 'rss'; language: string; url: string }
  | { type: 'wp'; language: string; base: string; categoryId: number };

const sources: Source[] = [{ type: 'rss', language: 'en', url: RSS_FEED_URL }];
if (process.env.INGEST_HINDI === '1' || process.env.INGEST_HINDI === 'true') {
  sources.push({
    type: 'wp',
    language: 'hi',
    base: process.env.HINDI_WP_BASE || 'https://hindi.theprint.in',
    categoryId: parseInt(process.env.HINDI_WP_CATEGORY || '326160', 10),
  });
}

const summary = {
  created: [] as string[],
  updated: [] as string[],
  skippedBlocklist: [] as string[],
  skippedAdminEdit: [] as string[],
  skippedNoChange: [] as string[],
  errors: [] as { slug: string; reason: string }[],
};

async function fileExists(p: string): Promise<boolean> {
  try {
    await stat(p);
    return true;
  } catch {
    return false;
  }
}

// Last commit author email for a repo-relative path. Empty string when the file
// has no history yet (brand new). Requires full history (checkout fetch-depth: 0).
function lastCommitEmail(relPath: string): string {
  try {
    const out = execFileSync('git', ['log', '-1', '--format=%ae', '--', relPath], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    return out.trim();
  } catch {
    return '';
  }
}

async function loadBlocklist(): Promise<Set<string>> {
  try {
    const raw = await readFile(join(REPO_ROOT, BLOCKLIST_PATH), 'utf8');
    const parsed = JSON.parse(raw) as { urls?: string[] };
    return new Set((parsed.urls || []).map((u) => u.toLowerCase()));
  } catch {
    return new Set();
  }
}

async function run() {
  const blocklist = await loadBlocklist();
  const mirroredOnIso = new Date().toISOString().slice(0, 10);

  for (const src of sources) {
    let items: RssItem[];
    try {
      if (src.type === 'rss') {
        const resp = await fetch(src.url, {
          headers: {
            'User-Agent': 'indianliberals-theprint-ingest/0.1 (+https://indianliberals.in)',
            Accept: 'application/rss+xml, application/xml, text/xml',
          },
        });
        if (!resp.ok) throw new Error(`RSS fetch failed: ${resp.status} ${resp.statusText}`);
        items = parseRssFeed(await resp.text());
      } else {
        items = await fetchWpRestItems({ base: src.base, categoryId: src.categoryId, max: MAX_ITEMS });
      }
    } catch (e) {
      summary.errors.push({ slug: `__feed_${src.language}__`, reason: String(e) });
      continue;
    }

    for (const item of items.slice(0, MAX_ITEMS)) {
      const slug = slugFromUrl(item.link, item.title);
      const rel = `${CONTENT_PATH}/${slug}.md`;
      const abs = join(REPO_ROOT, rel);
      try {
        if (blocklist.has(item.link.toLowerCase())) {
          summary.skippedBlocklist.push(slug);
          continue;
        }
        // Admin-edit guard: never clobber a file a human last touched via the CMS.
        if (await fileExists(abs)) {
          const author = lastCommitEmail(rel);
          if (author && author !== BOT_EMAIL) {
            summary.skippedAdminEdit.push(slug);
            continue;
          }
        }
        const content = rssItemToMarkdown(item, { mirroredOnIso, slug, language: src.language });
        if (await fileExists(abs)) {
          const existing = await readFile(abs, 'utf8');
          if (existing === content) {
            summary.skippedNoChange.push(slug);
            continue;
          }
          await writeFile(abs, content, 'utf8');
          summary.updated.push(slug);
        } else {
          await writeFile(abs, content, 'utf8');
          summary.created.push(slug);
        }
      } catch (e) {
        summary.errors.push({ slug, reason: String(e) });
      }
    }
  }

  console.log(JSON.stringify(summary, null, 2));
  // Signal to the workflow whether anything changed (via output file).
  const changed = summary.created.length + summary.updated.length;
  if (process.env.GITHUB_OUTPUT) {
    await writeFile(process.env.GITHUB_OUTPUT, `changed=${changed}\n`, { flag: 'a' });
  }
}

run().catch((e) => {
  console.error('ingest failed:', e);
  process.exit(1);
});
