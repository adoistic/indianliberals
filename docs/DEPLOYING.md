# Deploying indianliberals.in

## The short version

```bash
cd "<repo root>"                       # NOT apps/site — see "Functions" below
npm --prefix apps/site run build       # lint gates + astro build + pagefind
node scripts/deploy/pack-agent-surfaces.mjs
node scripts/deploy/upload-agent-surfaces.mjs
node scripts/deploy/publish-llms-full.mjs
npx wrangler pages deploy apps/site/dist --project-name indianliberals --branch main
```

## Why not just push to main

`indianliberals` is a git-integrated Pages project, so pushing to `main`
*should* build and deploy. It cannot, and has not since the Swatantra Party
papers landed: five consecutive builds were terminated at 35.8–36.7 minutes for
exceeding the build time limit. A failed build does not deploy, so production
keeps serving the last good version and **nothing surfaces the failure**.

Treat a green `main` as meaning nothing until the SSR work in
`docs/2026-08-21-scaling-plan.md` lands. Every content change needs a direct
upload.

## Functions: run from the repository root

Cloudflare Pages looks for Functions at `<root directory>/functions`, and this
project's root directory is the **repository root**. The handlers live in
`apps/site/functions/` and are re-exported from `functions/` at the root.

Deploy from `apps/site` and you ship the site with its 1,539-rule legacy
WordPress redirect map missing. That exact mistake went unnoticed for months —
see `docs/ccs-round-4-fixes-2026-08-14.md`.

## The packing step

Pages allows 20,000 files per deployment. A full build emits 35,841, because
every work also emits a `.md` sibling and an `api/works/<id>.json` record.

`pack-agent-surfaces.mjs` moves those 16,833 files into two blobs plus an
offset index, leaving **19,012** files in `dist`. `upload-agent-surfaces.mjs`
puts the four objects on R2. Two Pages Functions serve the original URLs from
byte ranges of those blobs, so `/api/works/<id>.json` and `<page-url>.md`
respond exactly as before.

Skipping the pack step means the upload is rejected. Skipping the upload step
means those URLs return 503 while every page still works.

## The one file too big to ship

`/llms-full.txt` is the whole corpus in one file. It was 29 MB when it was
first moved to R2 and is over 35 MB now, and Pages refuses any single file
above 25 MiB. The refusal comes at the end of the upload, so the minute spent
sending 19,000 files is spent before anything says why.

`publish-llms-full.mjs` puts it on R2 at `agent/llms-full.txt` and deletes it
from `dist`; `functions/llms-full.txt.js` serves that object at the original
URL and forwards range requests. The script refuses to publish a file under
10 MB, because a truncated build would otherwise replace a good copy of a URL
that SKILL.md advertises.

Every build writes the file again, so this runs on every deploy.

## Verifying before you deploy

```bash
npx wrangler pages dev apps/site/dist --port 8788      # from the repo root
node scripts/parity/compare-manifest.mjs               # gate 1: nothing else changed
node scripts/parity/check-moved-surfaces.mjs           # gate 3: moved bytes identical
```

`compare-manifest.mjs` must report `changed 0 / missing 0 / added 0`, with the
only difference being the moved paths. Its reference is
`data/parity/golden-manifest.txt`, taken from the last all-static build.

Also check by hand, because these have broken silently before:

| URL | Expected |
|---|---|
| `/content/<legacy-slug>/` | 301 to the work |
| `/content/<gone-slug>/` | 410 |
| `/content/<unknown>/` | 404, never a guess |
| `/all-categories/` | 301 to `/primary-works/` |
| `/AGENTS.md`, `/SKILL.md` | 200, served statically |

## Rollback

Deployments stay addressable. Roll back by promoting the previous deployment id
in the dashboard rather than rebuilding:

```bash
npx wrangler pages deployment list --project-name indianliberals
```
