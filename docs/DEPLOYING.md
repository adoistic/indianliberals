# Deploying indianliberals.in

## The short version

Push to `main`. `.github/workflows/deploy.yml` builds the site and uploads it
as a production deployment, taking about an hour end to end. A CMS save is a
push, so editors need nobody. Progress is on the Actions tab, and the CMS home
page reports whether the newest save is live yet.

If a deploy fails, the workflow opens a GitHub issue labelled `deploy-failed`
assigned to Adnan, and closes it when a later deploy succeeds. Production keeps
serving the previous build in between.

## Why it is a workflow and not the Pages git build

`indianliberals` is a git-integrated Pages project, so pushing to `main`
*should* build and deploy on Cloudflare's side. It cannot, and has not since the
Swatantra Party papers landed on 22 August 2026: every build is terminated
around 36 minutes in for exceeding the build time limit, and a failed build
does not deploy. Every push since then shows `Failure` in the Pages deployment
list, including every CMS save. Production kept serving the last direct upload
from Adnan's laptop, and nothing surfaced the failure to anyone.

The build cannot be made short enough, so it runs where the ceiling is six
hours instead: GitHub Actions, on every push to `main`, following exactly the
recipe below. Runs are serialised and coalesced (`concurrency`), so a burst of
CMS saves costs at most two builds, and a running deploy is never cancelled.

The Pages git build still fires on every push and still fails. That is
harmless but noisy, and would become a race if it ever succeeded. Turn it off
in the dashboard: the `indianliberals` project, Settings, Builds & deployments,
Production branch control, disable automatic deployments. Direct uploads keep
working with it off.

### One-time setup

The workflow needs one repository secret, `CLOUDFLARE_API_TOKEN`: a token on
the appsadoistic@gmail.com account with **Account → Cloudflare Pages → Edit**
and **Account → Workers R2 Storage → Edit** (R2 for the pack and llms-full
steps, Pages for the upload). Create it at dash.cloudflare.com → My Profile →
API Tokens → Create Token → Custom token, then:

```bash
gh secret set CLOUDFLARE_API_TOKEN
```

The workflow refuses in its first step, before building anything, while that
secret is missing. Re-run it from the Actions tab (`Run workflow`) once the
secret is set. The account id is not a secret and is in the workflow.

### Pushes that do not trigger it

GitHub does not start a workflow from a push made with another workflow's
token. The weekly ThePrint ingest pushes that way, so `theprint-ingest.yml`
dispatches the deploy itself after it commits. CMS pushes come from a GitHub
App and do trigger it; so do Adnan's.

## Deploying by hand

The same steps, for when Actions is down or a deploy must go out from a laptop.

```bash
cd "<repo root>"                       # NOT apps/site — see "Functions" below
npm --prefix apps/site run build       # lint gates + astro build + pagefind
node scripts/deploy/pack-agent-surfaces.mjs
node scripts/deploy/upload-agent-surfaces.mjs
node scripts/deploy/publish-llms-full.mjs
npx wrangler pages deploy apps/site/dist --project-name indianliberals --branch main
```

A hand build has no `GITHUB_SHA`, so `/api/meta.json` reports `commit: null`
and the CMS home page says the site was built by hand. Set
`GITHUB_SHA=$(git rev-parse HEAD)` before `npm run build` if that matters.

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
in the dashboard rather than rebuilding. Note that the next push to `main`
deploys again, so also revert the commit that needed rolling back:

```bash
npx wrangler pages deployment list --project-name indianliberals
```
