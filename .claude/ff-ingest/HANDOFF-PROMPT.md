# Freedom First ingestion — session handoff prompt

You are continuing an in-progress data-ingestion job on the **Indian Liberals website** (Astro site at `/Users/siraj/Indian Liberals Website`). Read this whole prompt, then VERIFY current state before acting — overnight automation may have advanced things since it was written.

## GOAL
Ingest every downloaded **Freedom First** periodical issue (`FFxxx.pdf`) into the `primary-works` content collection as `work_type: periodical_issue`, grouped under the existing `freedom-first` series, validated and pushed to `origin/main`. Then help close the gap to the full ~500-issue run (which requires downloading the rest).

## FIRST: verify where things stand
```
cd "/Users/siraj/Indian Liberals Website"
git log --oneline -3
ls apps/site/src/content/primary-works/ff*.md | wc -l          # issues already ingested
ls "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/freedom-first/"FF*.pdf | wc -l   # downloaded on disk
# remaining to ingest:
ls "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/freedom-first/"FF*.pdf | sed 's#.*/##;s#\.pdf$##' | sort -u > /tmp/od.txt
ls apps/site/src/content/primary-works/ff*.md | sed 's#.*/ff#FF#;s#\.md$##' | tr a-z A-Z | sort -u > /tmp/dn.txt
comm -23 /tmp/od.txt /tmp/dn.txt        # the un-ingested list; work through these ascending
```
As of writing: **97 issues live (FF001–FF102, minus gaps), 153 downloaded, 56 on-disk left to ingest starting at FF103.** Trust the live `comm` output over these numbers.

## BACKGROUND (how we got here)
- Also read memory `freedom_first_ingestion.md` (has the same facts, keep its state line updated).
- The pipeline is `scripts/llm-extract/` (driver.py prep/collect + prompts) → `scripts/synthesis/emit-astro-md.py` → normalize. It is driven by **in-session Agent subagents**, NOT `claude -p`/`run_overnight` (those stall).
- Helper scripts already written and persisted in `.claude/ff-ingest/`: `ff_prep.sh`, `ff_finalize.sh`, `extract_agent_json.py`. Use them.

## INFRA GOTCHAS — do not relearn these the hard way
1. **Internal disk is chronically ~95% full.** Rasterized page images go to `/tmp/llm-extract-requests`, which is a **symlink to the external drive** `/Volumes/One Touch/ff-rasterize`. Before starting, ensure it exists: `ls -ld /tmp/llm-extract-requests`; if missing: `ln -s "/Volumes/One Touch/ff-rasterize" /tmp/llm-extract-requests`. The external "One Touch" drive MUST be mounted (holds both source PDFs and rasterize scratch).
2. **Rate limits: 6 docs (= 12 subagents) per batch, max.** 24-at-once trips Anthropic's server-side limit.
3. **Extractor often leaves `publisher_id`/`issuer_id` null.** `ff_finalize.sh` force-sets BOTH to `freedom-first` on every `ff*.md` — required for periodicals series grouping. Don't skip it.
4. **Transient failures** (`API Error: Overloaded`, silent agent death, ~1–2 per few batches): just re-dispatch that one `(doc,job)`. The response-file poll makes this reliable.
5. **Purge `/tmp/llm-extract-requests/*` each batch** (ff_finalize does it) to reclaim external-drive space.
6. **Do NOT run `make-periodical-covers.py`** — it's global (rewrites every periodical `.md`) and belongs to a single deliberate end-of-run pass.

## THE LOOP (repeat until the on-disk backlog is empty)
For the next 6 un-ingested docs (call them FF0aa … FF0ff, ascending):
1. **Prep:** `zsh ".claude/ff-ingest/ff_prep.sh" /tmp/ff_batchN.tsv FF0aa FF0bb FF0cc FF0dd FF0ee FF0ff` — rasterizes metadata + summary, writes the manifest, prints the 12 request dirs.
2. **Dispatch 12 subagents** (Agent tool, `subagent_type: general-purpose`, `model: sonnet`), one per request dir. Each subagent prompt: *"Read that dir's system.txt + user.txt + every page-*.jpg image; apply the SYSTEM prompt to the images per the USER prompt; write ONLY the raw JSON result to that dir's `response.json` via the Write tool; reply 'done'."*
3. **Wait** for all 12 `response.json` to exist (background bash poll loop over the manifest; sleep 20s).
4. **Finalize:** `zsh ".claude/ff-ingest/ff_finalize.sh" /tmp/ff_batchN.tsv "batch NN (FF0aa–FF0ff)"` — collects (auto-emits `.md`), normalizes ids, `astro sync` validates, commits, `git pull --rebase`, pushes `origin/main`, purges `/tmp`.
5. Recompute the remaining list; continue. Push every batch. It's fine to run many batches per usage window.

## SUCCESS CRITERIA
- Every downloaded FF PDF has a validated `ff*.md` with `work_type: periodical_issue` + `issuer_id: freedom-first`, `astro sync` clean, pushed to `origin/main`. `comm -23 /tmp/od.txt /tmp/dn.txt` returns empty.

## AFTER the on-disk backlog is done — remaining project work
1. **Downloads are the real bottleneck to reach ~500.** Only 153/500 are on the drive. The rest (~347) were blocked by Google throttling the anonymous path and rclone's shared-quota client. The fast fix is a **personal Google OAuth client** (own quota) → pull all remaining in minutes. There's a partial rclone config at `~/.config/rclone/rclone.conf` (token expired). Ask Adnan before doing this — it needs ~5 min of his Google Cloud setup. Downloads land in `/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/freedom-first/`; then ingest them with the same loop.
2. **Periodical covers:** one deliberate `make-periodical-covers.py` pass at the very end (it touches all periodicals; review the diff, commit as its own change).
3. **Editorial review notes** (all entries are `needs_review: true`): the *M. R. Masani* byline may be mis-resolved to `m-r-pai` in some issues (FF100 flagged) — Masani recurs across the run, so a targeted resolver check is worthwhile. IDs are issue-numbered (`ff0xx`) which is fine for a periodical run.

## OWNERS / GUARDRAILS
- Editorial owners are CCS: Arjun and Kumar Anand. Never hard-delete entities CCS asks to "remove" (that's a presentation change). This ingestion is content prep for their review.
- Address the user as **Adnan**.
