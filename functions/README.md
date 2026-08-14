# Why this directory exists

Cloudflare Pages looks for Functions at `<root directory>/functions`. This
project's root directory is the repository root, while the site and its
functions live under `apps/site/`. So `apps/site/functions/` was never
deployed: every legacy WordPress URL 404'd in production, while working
perfectly under `wrangler pages dev` run from `apps/site`, which is why it
went unnoticed. Roughly 1,400 inbound addresses were dead.

Each file here is one line. It re-exports the real handler, which stays next to
the site it belongs to. Adding a legacy route means adding it in both places;
`scripts/legacy-redirects/` regenerates the map, not these.

The alternative was to change the project's root directory in the Cloudflare
dashboard, which also moves the build command and the output directory and
cannot be reviewed in a pull request. This can.
