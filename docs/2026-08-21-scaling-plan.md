# Scaling the archive past two Cloudflare ceilings

**Status:** plan, not yet executed.
**Written:** 2026-08-21, after the Swatantra Party papers took the corpus from
1,577 works to 7,932.

## 1. What is actually broken

Two independent Cloudflare Pages limits are exceeded. Both were measured, not
inferred, and the second was hidden behind the first.

| Limit | Ours | Evidence |
|---|---|---|
| Build time (~36 min observed) | 31.5 min local, >36 min on Pages | 5 consecutive builds terminated at 35.8–36.7 min |
| 20,000 files per deployment | **35,841** | `find dist -type f`, this build |
| 25 MiB per file | `llms-full.txt` at **29 MB** | `find dist -size +25M` |

The build-time failures masked the file cap: every build died before upload, so
the file count was never tested. Fixing build time alone would have produced a
second failure at the upload step.

### Where the 35,841 files come from

| Kind | Files |
|---|---:|
| HTML pages | 9,099 |
| Pagefind index fragments | 9,443 |
| `api/works/<id>.json` (per work) | 7,888 |
| per-page `.md` (all collections) | 8,947 |
| assets, fonts, images, `_astro` | ~460 |

Each work emits **three** files: an HTML page, a markdown sibling, and a JSON
record. The page count tripled quietly.

### Why concurrency did not save it

`build.concurrency: 4` was measured at **1.26x** (264 -> 332 pages/min). Four
workers buying 26% means the cost is mostly serial — content-store I/O and
markdown compilation, not page rendering. It moves the primary-works route from
30.0 to 23.9 minutes and leaves the total over the wall. Keep it (it is free)
but it is not a fix.

## 2. Constraint that shapes everything

`apps/mcp/wrangler.jsonc` says, deliberately:

> A thin, stateless Cloudflare Worker. It holds NO content: every tool reads
> the build-generated `/api/*.json` endpoints and `.md` siblings on
> indianliberals.in, so each site deploy flows into the MCP automatically.

So the per-work files are **not** redundant. `apps/mcp/src/tools.ts:226` and
`:457` fetch `/api/works/<id>.json`; `data.ts:78` fetches
`/api/search-index.json`. `public/SKILL.md` and `AGENTS.md.ts` publish both
families as a public contract to outside agents.

**Nothing may be deleted.** The URLs must keep resolving byte-identically. That
rules out "drop the duplicate surfaces", which was the first idea and the wrong
one.

## 3. Phase 1 — move per-work data to R2, keep every URL

R2 has no file-count limit, and `indianliberals-archive` already exists, bound
as `ARCHIVE` in `apps/archive-root/wrangler.jsonc`.

1. Build emits per-work `.md` and `api/works/<id>.json` to `build-artifacts/`
   instead of `dist/` (an Astro integration or a post-build move; the routes
   themselves do not change).
2. `scripts/deploy/upload-agent-surfaces.mjs` syncs that tree to R2 under
   `agent/` — same resumable shape as the existing PDF upload script.
3. Two Pages Functions at the **repository root** (see §6) proxy the public
   URLs to R2, preserving path, content-type and cache headers:
   - `functions/api/works/[id].json.js`
   - `functions/[collection]/[slug].md.js`

**Effect on the file cap:**

```
35,841 − 7,888 (api/works) − 8,947 (per-page .md) = 19,006   ✓ under 20,000
```

**Effect on consumers:** none. Same URLs, same bytes. The MCP worker needs no
change, and stays stateless in exactly the sense its config intends — it still
reads the site over HTTP.

`llms-full.txt` (29 MB) moves to R2 the same way and is proxied.

## 4. Phase 2 — on-demand rendering for archival items

Build time still exceeds the wall after Phase 1, because the page count is
unchanged. Phase 2 addresses that and is independent: Phase 1 alone makes the
site deployable by direct upload.

1. Enable `adapter: cloudflare()` — already scaffolded and commented out at
   `astro.config.mjs:80`.
2. `export const prerender = false` on `primary-works/[slug].astro` **for
   Swatantra archival items only**. The ~1,577 pre-existing published works stay
   prerendered: they carry the SEO weight and are what people browse.
3. Edge-cache the on-demand responses so each item renders once.

**The trap:** search is built from rendered HTML (`pagefind --site dist`, keyed
off `data-pagefind-body`). Un-rendered pages would silently vanish from search,
which is the archive's core value. So:

4. Build the Pagefind index from **content data** via Pagefind's Node API
   (`addCustomRecord`, present in pagefind 1.5.2 — verified). Records are
   derived from the collection, not from markup, so all 6,355 archival items
   stay searchable without being rendered.

This is the fiddly part and where the work will actually go: excerpts, filters
and language metadata currently fall out of the markup for free.

### Blocking discovery: the adapter turns the Functions directory off

`@astrojs/cloudflare` 12.6.13 emits `dist/_worker.js/` (advanced mode). On
Cloudflare Pages `_worker.js` and `functions/` are mutually exclusive: when the
worker is present, the Functions directory is **ignored entirely**.

That is not a detail. It would silently disable:

* the 18 legacy redirect handlers carrying the 1,539-rule WordPress map, and
* the three agent-surface functions added in Phase 1.

Both would return 404 while every page still rendered — the exact failure shape
that went unnoticed for months in `docs/ccs-round-4-fixes-2026-08-14.md`, and
one that no page-level parity check would catch.

So Phase 2 is not "switch on the adapter". It is:

1. port all 21 handlers into `src/middleware.ts`, preserving 301/410/404
   semantics per rule,
2. re-verify the full legacy map, not a sample — every one of the 1,539 rules,
3. then the SSR and Pagefind work described above.

Attempting it without step 2 would ship a site whose pages all look right and
whose entire legacy URL surface is gone.

### Build-time attribution (measured 2026-08-21)

| Route | Minutes | Share |
|---|---:|---:|
| `primary-works/[slug]` | 24.7 | 78.9% |
| `thinkers/[slug]` | 4.6 | 14.8% |
| everything else | 2.0 | 6.3% |

SSR targets the right route. Nothing else is worth optimising first.

## 5. Parity: the website must look exactly as it does today

A complete, known-good build exists as of 2026-08-21 and is the reference.

`data/parity/golden-manifest.txt` — 26,402 paths with SHA-256, produced from
that build (pagefind excluded; its fragment names are content-addressed and
change on any content edit).

### Gates, in order of strength

1. **Byte parity on static output.** After Phase 1, re-run the build and diff
   the new manifest against the golden one. The ONLY permitted differences are
   the deliberately-removed `.md` and `api/works/*.json` paths. Any other
   changed hash is a regression. `scripts/parity/compare-manifest.mjs`.
2. **URL resolution parity.** Every URL in the golden sitemap must return the
   same HTTP status and content-type from the deployed site, including the
   moved surfaces now served from R2. Run against a preview deployment before
   production.
3. **Byte parity on moved surfaces.** For a stratified sample (300 works across
   every `work_type`), `GET /api/works/<id>.json` and `GET /<c>/<slug>.md` must
   equal the golden file byte-for-byte.
4. **Legacy redirect parity.** The 1,539-rule WordPress map is served by
   root `functions/`. Re-verify the cases named in
   `docs/ccs-round-4-fixes-2026-08-14.md`: `/content/<slug>/`,
   `/hi/content/<slug>/`, `/all-categories/`, and an unknown slug still 404ing.
   This has silently broken before — for months.
5. **Search parity.** Pagefind record count within 1% of golden, and a fixed
   query set (20 queries spanning English and the four Indic languages) must
   return the same top-5 result ids.
6. **MCP parity.** Exercise every MCP tool against the preview origin and diff
   responses against the same tools run on production.
7. **Rendered-HTML parity for SSR pages (Phase 2 only).** For 200 sampled
   works, the SSR response body must equal the prerendered golden HTML after
   normalising nothing. If they differ, SSR is not a drop-in and the difference
   must be explained before shipping.
8. **Visual check.** Screenshots of 10 representative pages (work detail,
   thinker, series, periodical, listing, search, home) at desktop and mobile,
   compared against the same pages on production.

Gates 1–4 are Phase 1. Gates 5–8 are Phase 2. All are scripted under
`scripts/parity/` and runnable as one command.

## 6. Documentation that must change

Each of these states something that will stop being true:

- `apps/mcp/wrangler.jsonc` — the "holds NO content" comment stays accurate,
  but should note the surfaces are proxied from R2.
- `public/SKILL.md` (lines 32, 38, 55–56) and `src/pages/AGENTS.md.ts`
  (lines 94, 128, 133–138) — URLs are unchanged, so the contract text stands;
  add a note that these are served from object storage.
- `docs/ARCHITECTURE.md`, `docs/FEATURE-INVENTORY.md` — the hosting table calls
  the site a static Pages build. After Phase 2 it is hybrid.
- `docs/ccs-round-4-fixes-2026-08-14.md` — the Functions-location lesson gains
  two more functions that must live at the repository root, not `apps/site/`.
- `README.md` — deploy instructions, including that Pages git builds cannot
  complete until Phase 2 lands.
- A new `docs/DEPLOYING.md` — direct-upload procedure, run from the repository
  root so root `functions/` is bundled.

## 7. Sequencing and rollback

Phase 1 is independently valuable and low-risk: no page changes, no adapter, no
SSR. It makes the site deployable today by direct upload and can ship alone.

Phase 2 is the architectural change and should not be attempted until Phase 1's
parity gates pass green.

Rollback for both: production is served by whatever the last successful
deployment was, and Cloudflare keeps prior deployments addressable. A bad
direct upload is reverted by redeploying the previous deployment id, not by
rebuilding.

## 8. Known cleanup

- `dist/.wrangler/` (4 files, 144 KB) is local `wrangler dev` state landing in
  the build output. It should never be uploaded. Add to the build's ignore.
- Git-integrated Pages builds fail until Phase 2. Every content edit pushed to
  `main` therefore needs a direct upload, and nothing surfaces the failure.
  Until then, treat a green `main` as meaning nothing.
