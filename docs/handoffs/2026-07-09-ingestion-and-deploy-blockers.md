# Batch D/E — ingestion & infra blockers (round-2 feedback #7, #16, #18a)

Date: 2026-07-09. These items are wholly or partly blocked on things outside this repo
(source scans, a Hindi feed URL, a worker deploy, or a pending CCS list). Recording the exact
state so they can be picked up the moment the dependency clears.

## #7 — Freedom First (upload all 552 pieces) — BLOCKED (source not mounted)

- The source scans/PDFs live on the curator's **"One Touch" external drive**, which is **not
  mounted** on this machine (`/Volumes` shows only `Macintosh HD`). Ingestion cannot start
  without the scans.
- The **series is ready**: `Freedom First` now exists as a run on `/periodicals/`
  (`issuer_id: freedom-first`), currently with the 1 issue already in the corpus. Bulk
  ingestion will land straight into it.
- **To proceed:** mount "One Touch", confirm the Freedom First scans are present, then run the
  established primary-works pipeline (extraction → bake → enrich → emit `.md` with
  `work_type: periodical_issue`, `publication.issuer_id: freedom-first`). Per project practice,
  drive this with **in-session Agent subagents**, in batches, pushing periodically — NOT
  `claude -p` / overnight runners (unreliable: rate stalls, SUMMARY_FAILED).

## #16 — ThePrint Hindi + Saturday auto-update

- **#16b cron → done in config.** `apps/theprint-ingest/wrangler.toml` cron changed from daily
  to **weekly Saturday** (`30 4 * * 6`, 10:00 IST).
- **#16a Hindi — code ready, needs the feed URL.** The worker now mirrors multiple
  language-tagged column feeds; set `RSS_FEED_URL_HI` to the Hindi "Indian Liberals Matter"
  column's RSS URL and its items ingest with `language: "hi"` (Pagefind already indexes Hindi).
  English output is unchanged (16/16 worker tests still pass). **Blocked on** the exact Hindi
  column URL from ThePrint — the placeholder is commented in `wrangler.toml`.
- **Deployment — BLOCKED.** The worker is scaffolded but **not deployed** (needs a Cloudflare
  account, `GITHUB_TOKEN` secret via `wrangler secret put`, then `npm run deploy`). Until it is
  deployed, neither the Saturday cron nor Hindi ingestion runs. This is the real gate on #16.

## #18a — final Home/Canon author list — BLOCKED (pending CCS)

- Kumar Anand & Arjun are to send the specific list of people to feature. **Not guessed.**
- The mechanism is in place: set `featured: true` on the chosen thinker MDs and the Home rail
  (`index.astro`) and Canon rail (`thinkers/index.astro`) pick them up. #18b (uniform B&W
  duotone treatment) is already done and applies to whatever set is featured.

## Summary of what IS done in this batch

- #16b cron set to Saturday; worker made Hindi-capable (multi-feed, language-tagged).
- #18b duotone/B&W treatment standardised; grayscale safety net added so no colour photo can
  reach the home/canon rails.
- #12 People-section options written for CCS (`2026-07-09-people-section-proposal.md`).
