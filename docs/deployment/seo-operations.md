# SEO / GEO / AEO operations

Shipped 2026-07-21. This is the ops contract that keeps the site "ever-ready"
for search engines, generative engines, and answer engines as content grows.

## The standing pieces (no maintenance needed)

- **robots.txt** (`apps/site/public/robots.txt`) — welcomes all crawlers,
  names the AI bots explicitly, declares the sitemap, and points agents at
  `/llms.txt`, `/AGENTS.md`, and the MCP server.
- **JSON-LD** — `apps/site/src/lib/schema.ts` builders; BaseLayout emits an
  Organization + WebSite `@graph` on every page, detail components append
  Book/CreativeWork, Person + ProfilePage, Article, Organization,
  CollectionPage, and BreadcrumbList nodes. New content gets structured data
  automatically — nothing to do per-work.
- **Legacy WordPress redirects** — `apps/site/functions/` (Cloudflare Pages
  Functions). Old `/content/<slug>/`, the `/bn|gj|hi|mr/` subsites, taxonomy
  archives, and author/letter pages all 301 to their new homes;
  WP spam slugs return 410. `public/_redirects` blanket-301s all ten legacy
  PDF directories to R2 (keys mirror the old WP paths).
- **www host** — `apps/www-redirect` worker on the `www.indianliberals.in/*`
  zone route 301s the (dead-origin) www host to the apex. Deployed with
  `npx wrangler deploy` from `apps/www-redirect/`. Do not convert it to a
  custom domain: the wrangler OAuth grant has no `dns:write`, and the stale
  proxied www record can't be replaced — the route intercepts in front of it.
- **Sitemap** — `@astrojs/sitemap` with hreflang alternates; noindexed
  ThePrint-mirror detail pages are filtered out (astro.config.mjs).
- **Body headings** — `remark-demote-h1` keeps markdown bodies from emitting
  a second `<h1>`; the layout owns the page H1.

## After ingesting new works

1. **Regenerate the legacy-redirect map** so old URLs that previously fell
   back to a section landing upgrade to exact 301s:

   ```bash
   python3 scripts/legacy-redirects/generate.py
   ```

   Commit the changed `apps/site/functions/_legacy/map.json` with the batch.

## After each deploy

2. **Ping IndexNow** (Bing / Copilot / Seznam / Naver — Google does not use
   IndexNow; it discovers via sitemap):

   ```bash
   # whole sitemap (fine for occasional use)
   python3 scripts/seo/indexnow-submit.py
   # or just the pages that changed
   python3 scripts/seo/indexnow-submit.py https://indianliberals.in/primary-works/<slug>/ ...
   ```

   The key file lives at `apps/site/public/8857e84b5745431fb0913015ce306fe6.txt`.

## Pending (needs Adnan's accounts, one-time)

- **Google Search Console**: add the `indianliberals.in` domain property
  (DNS TXT verification), submit `https://indianliberals.in/sitemap-index.xml`.
  Until then Google discovers via crawl only, and we can't see impressions,
  coverage, or rich-result reports.
- **Bing Webmaster Tools**: import from GSC (one click) or verify the same
  way. Gives index coverage + the crawl data behind Copilot.

## Verification snapshot (2026-07-21)

- Lighthouse SEO **100/100** (home + work pages), performance 94–100,
  CLS ≈ 0, LCP 0.5–1.2 s.
- Google Rich Results Test: ProfilePage ✓, Article ✓, Breadcrumbs ✓ on the
  tested pages; no critical issues.
- IndexNow initial submission: 2,592 URLs accepted (HTTP 200).
- Legacy redirects: `/content/the-indian-libertarian-october-1-1957/` →
  `/primary-works/the-indian-libertarian-oct1-1957/` → 200, and equivalents
  across all namespaces; spam slugs 410.
