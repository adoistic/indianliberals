# Cloudflare Pages deployment

This is the deployment guide for indianliberals.in on **Cloudflare Pages**. The site is fully static (Astro 5 + Pagefind), so deployment is "ship the `dist/` folder" — no SSR runtime, no adapter, no workers.

There are two paths:

- **One-shot manual deploy** via `wrangler pages deploy` — fastest way to get a preview URL to share with CCS editorial.
- **GitHub-integrated continuous deploy** — set up once in the Cloudflare dashboard; every push to `main` auto-deploys to production.

Use the one-shot path for the first preview. Switch to GitHub integration before launch.

---

## Prerequisites (one-time)

1. **Cloudflare account.** Adnan has this — the production zone for `indianliberals.in` lives there.
2. **wrangler CLI authenticated locally:**
   ```bash
   npx wrangler login
   ```
   Opens a browser tab; approve the OAuth and you're done. `wrangler` is bundled with Astro via `@astrojs/cloudflare`, currently at v4.59.

3. **The repo's local build works:**
   ```bash
   cd "/Users/siraj/Indian Liberals Website/apps/site"
   npm install
   npm run build
   ```
   Output goes to `apps/site/dist/` (~97 MB across ~1,280 pages including i18n).

---

## Path A — One-shot preview deploy

Fastest way to get a shareable URL for CCS.

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
npm run build
npx wrangler pages deploy dist \
  --project-name=indianliberals \
  --branch=phase-b-preview \
  --commit-message="Phase B preview for CCS review"
```

First run creates the Pages project (`indianliberals.pages.dev`) under Adnan's Cloudflare account. wrangler prints the deployed URL on completion — looks like:

```
https://phase-b-preview.indianliberals.pages.dev
```

Share that with Arjun and Kumar Anand for review.

The `--branch` flag controls the subdomain prefix. Each branch gets its own preview URL, so you can have multiple previews live at once (e.g., `phase-b-preview`, `audio-pipeline-preview`).

To re-deploy a new build to the same preview URL: just re-run the command above. wrangler picks up the existing project and overwrites the preview.

---

## Path B — GitHub-integrated continuous deploy

Set this up once when you're ready to land on production. Every push to `main` auto-deploys.

1. **Cloudflare dashboard** → Pages → "Create a project" → "Connect to Git"
2. Select the GitHub repo: `adoistic/indianliberals`
3. **Production branch:** `main`
4. **Build settings:**
   - Framework preset: **None** (we have a custom monorepo layout)
   - Build command:
     ```
     cd apps/site && npm install && npm run build
     ```
   - Build output directory: `apps/site/dist`
   - Root directory: `/` (the repo root)
   - Node version: 20 (set via `NODE_VERSION=20` env var)
5. **Environment variables:** none required for the current build. If/when secrets are added (Sveltia OAuth, etc.), set them here as Plain text or Secret.
6. **Deploy.** First build takes 3-5 min; subsequent builds ~2 min.

Preview deploys auto-fire on PRs against `main`; they get a URL like `<commit-sha>.indianliberals.pages.dev`.

---

## Custom domain (production cutover)

Once `*.pages.dev` looks good and you're ready to flip:

1. **Cloudflare dashboard** → the `indianliberals` Pages project → Custom domains → Set up custom domain → `indianliberals.in`
2. Cloudflare automatically configures the CNAME record (since the zone is in the same Cloudflare account). DNS propagation is near-instant.
3. SSL certificate is issued automatically via Cloudflare's edge certs.
4. Update Astro's `site:` field in `astro.config.mjs` if the canonical changes (it already says `https://indianliberals.in`, so no change needed).

If you also want `www.indianliberals.in` redirecting to apex, add that as a second custom domain.

---

## What's in the repo for deployment

| File | Purpose |
|---|---|
| `apps/site/public/_headers` | Cloudflare Pages cache & security headers. Aggressive caching for `_astro/*` content-hashed assets; short TTL for HTML. |
| `apps/site/public/_redirects` | Empty for now. Add WP→Astro URL redirects here at cutover time. |
| `apps/site/astro.config.mjs` | `site: 'https://indianliberals.in'`. Cloudflare SSR adapter import is present but commented (we want static output). |
| `apps/site/package.json` | `build` script: `astro build && pagefind --site dist`. |

---

## Routing notes

- **i18n:** English at root (`/musings/...`), other languages at `/hi/`, `/gu/`, `/mr/`, `/bn/`. Cloudflare Pages serves the static prerender — no rewrites needed.
- **Pagefind search:** loads `/pagefind/pagefind.js` at runtime; the search index lives in `/pagefind/*.pf_*`. All static.
- **AI agent surfaces:** `/llms.txt`, `/llms-full.txt`, `/AGENTS.md`, and per-page `<url>.md` siblings are all static-built. Served with `Content-Type: text/markdown` via `_headers`.

---

## Smoke checks after deploy

After `wrangler pages deploy` returns the URL:

```bash
PAGES_URL="https://phase-b-preview.indianliberals.pages.dev"

# Homepage
curl -sI "$PAGES_URL/" | head -3

# A touchstone bio page (Phase B surface)
curl -s "$PAGES_URL/thinkers/a-d-shroff/" | grep -c "How A. D. Shroff is discussed in this archive"
# expect: 1

# A primary-work
curl -sI "$PAGES_URL/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/" | head -3

# Pagefind index
curl -sI "$PAGES_URL/pagefind/pagefind.js" | head -3

# Agent index
curl -s "$PAGES_URL/llms.txt" | head -3
curl -sI "$PAGES_URL/AGENTS.md" | grep -i content-type
```

Each should return a 200 (or appropriate response) within ~200ms thanks to Cloudflare's edge cache.

---

## What's NOT deployed yet

- `apps/theprint-ingest/` — daily cron worker mirroring ThePrint's RSS. Separate `wrangler deploy` from inside that directory; tests pass (16/16) but the worker is not yet pushed.
- `apps/auth/` — Sveltia CMS OAuth proxy. Not yet deployed; not blocking the static-site preview.

These are tracked as separate deployment units; both can wait for the static-site preview to land first.
