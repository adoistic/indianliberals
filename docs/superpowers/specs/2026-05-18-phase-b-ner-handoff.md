# Phase B — In-prose NER handoff

**For:** the next Claude Code session that picks up this work
**From:** the long Sunday 2026-05-18 session that built indianliberals.in's Phase A
**Date written:** 2026-05-18 08:03 IST
**Branch:** `main` (everything is committed and pushed to GitHub)

---

## You are Adnan's engineering pair on this project

The macOS account is `siraj` but the human is **Adnan**, founder of Thothica. This is a Thothica engagement for the Centre for Civil Society (CCS), funded by the Friedrich Naumann Foundation for Freedom. CCS owns the editorial side. Thothica owns the build.

The site is **indianliberals.in** — a digital archive of the Indian liberal tradition. It launches in approximately 7 days.

---

## Repo location

```
/Users/siraj/Indian Liberals Website
```

GitHub: <https://github.com/adoistic/indianliberals> (private). Branch: `main`.

`cd "/Users/siraj/Indian Liberals Website"` to start.

---

## What the project IS

A static-site, AI-readable digital archive built on Astro 5 + Pagefind. It holds:

| Tier | What | Where |
|---|---|---|
| **A — clean content** | Curated excerpts ("musings"), opinion pieces, interviews, ThePrint federated mirror, thinker profiles, organisation profiles | Markdown in `apps/site/src/content/{musings,opinions,interviews,theprint-mirror,thinkers,organisations}/` |
| **B — primary works + periodicals** | The historic Indian liberal corpus — books, pamphlets, speeches, essays. Surfaced as metadata + AI-extracted summary + key points + PDF link (no full-text reconstruction yet) | `apps/site/src/content/primary-works/` |

**Two scale axes everything is built around:**
- The AI extraction pipeline (Python + `claude -p` headless) chews through PDFs from `/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/` and emits primary-works MDs. ~944 PDFs total; ~220 baked so far.
- Every content collection has a Zod schema in `apps/site/src/content.config.ts` that imports from `apps/site/src/schemas/`. Schema-validated.

---

## What's running in the background

Check first:

```bash
date
ps -p 25812 -o pid,etime,stat,command 2>/dev/null
pgrep -fl run_overnight
pgrep -f "^claude" | wc -l
tail -10 /tmp/v1.5-overnight-progress.tsv
find data/bake-off-output -maxdepth 2 -name "summary.json" 2>/dev/null | wc -l
```

**At the moment of handoff (2026-05-18 08:03 IST):**

- **Overnight extraction runner:** PID **25812**, alive ~2h 52min, but currently idle (0 active claude procs). It's paused — the runner has a rate-limit-aware circuit breaker (`scripts/llm-extract/run_overnight.py`) that parses Anthropic's "resets at HH:MM" messages and sleeps until the reset. The last visible activity showed `SUMMARY_FAILED` entries around the rate-limit boundary; the breaker is waiting it out. It will resume on its own.
- **Astro preview server:** running on `http://127.0.0.1:4321/` (PID 53630). If it's gone when you start, restart with:
  ```bash
  cd "/Users/siraj/Indian Liberals Website/apps/site" && nohup npx --offline astro preview --host 127.0.0.1 --port 4321 > /tmp/astro-preview.log 2>&1 &
  ```

**Total PDFs baked so far: 220 of ~944.** The runner will fill in more over the coming days; no action needed from you on the runner.

---

## What's already built (do NOT rebuild)

Read this section carefully. Almost everything is in place.

### The extraction pipeline (v1.5)

- `scripts/llm-extract/driver.py` — per-PDF orchestration: metadata extraction (chunked TOC + bylines) + summarization pass + cross-thinker mention extraction
- `scripts/llm-extract/run_overnight.py` — parallel `claude -p` CLI driver. Has a `CircuitBreaker` class that parses rate-limit messages and pauses until the actual reset time. Concurrency default 12. Restart with:
  ```bash
  cd "/Users/siraj/Indian Liberals Website" && source .venv-extract/bin/activate && nohup python3 scripts/llm-extract/run_overnight.py --concurrency 12 > /tmp/v1.5-overnight.log 2>&1 &
  ```
- `data/bake-off-output/<slug>/{metadata.a.a.json, summary.json, metadata.b.b.json}` — extraction outputs per PDF

### The authority files

- `data/authority/thinkers.json` — **462 thinkers**, **678 byline_lookup keys**. Includes 125 `ai_drafted_stub` entries from Phase A cross-link audit (these need real bios eventually — Phase 1.5).
- `data/authority/organisations.json` — 50 organisations, byline_lookup similar.

### The Astro site

- `apps/site/` — Astro 5 with Pagefind, Cloudflare Pages adapter ready (not yet deployed)
- `apps/site/src/content.config.ts` — 7 collection schemas
- `apps/site/src/schemas/` — shared sub-schemas (i18n, rights, provenance, people, extraction, synthesis) — extracted from a monolithic config during Day 7
- `apps/site/src/pages/` — all page templates including the three-section thinker bio (By / About / Mentioned in)
- `apps/site/src/lib/cross-links.ts` — TF-IDF related-link reader (1,958 cross-links computed by `scripts/synthesis/tfidf.py`)

### The agent layer

- `apps/site/src/pages/llms.txt.ts` — curated index for AI agents
- `apps/site/src/pages/llms-full.txt.ts` — full corpus dump (4 MB)
- `apps/site/src/pages/AGENTS.md.ts` — citation rules + tier policy + schema
- `apps/site/src/pages/*/[slug].md.ts` — `.md` sibling for every Tier-A detail page (so any URL has a `<url>.md` companion AI agents can fetch)

### The Cloudflare Workers

- `apps/theprint-ingest/` — daily cron worker that mirrors ThePrint's "Indian Liberals Matter" RSS into the theprint-mirror collection. Tested (16/16 vitest passing). NOT YET DEPLOYED — pending Cloudflare account setup.
- `apps/auth/` — Sveltia CMS OAuth proxy. NOT YET DEPLOYED.

### Phase A cross-link audit (the immediately previous work)

- Spec: `docs/superpowers/specs/2026-05-18-cross-link-audit-design.md`
- Prompts: `scripts/synthesis/prompts/system-resolver.txt` + `scripts/synthesis/prompts/README.md`
- Scripts:
  - `scripts/synthesis/prepare-unlinked.py` — finds entries without structured thinker refs
  - `scripts/synthesis/resolve-unlinked.py` — headless `claude -p` dispatcher (same circuit-breaker pattern as the extraction runner)
  - `scripts/synthesis/apply-resolutions.py` — applies resolution decisions, creates stub thinkers
  - `scripts/synthesis/audit-thinkers.py` + `apply-thinker-cleanup.py` — the duplicate-and-fake cleanup from earlier in the day
  - `scripts/synthesis/heuristic-resolve.py` — slug-tail / title-prefix heuristic
  - `scripts/synthesis/resolve-bylines.py` — initial byline backfill (mostly superseded by apply-resolutions.py)
- Outputs:
  - `data/synthesis/unlinked.jsonl` — raw input
  - `data/synthesis/resolutions.jsonl` — 516 resolution records (every decision recorded)
  - `data/synthesis/audit-residual.txt` — 190 skip entries (truly thematic content)
  - `data/synthesis/cleanup-plan.json` — the earlier thinker cleanup audit

**Phase A result:** coverage went from 31% → 65% linked (456 of 692 Tier-A entries have a structured thinker reference). The 35% residual is mostly thematic editorials + WP-import junk that has no single primary thinker — correctly skipped.

### One late-breaking fix that matters for Phase B planning

After Adnan pointed out that "every author should have works", I found the bug: the extraction pipeline captures `cross_thinker_mentions` in `summary.json.summary_structured.cross_thinker_mentions` (and per-essay for multi-author volumes) — **196 baked works carry 1,347 mentions across 53 distinct thinkers**. The emitter never projected these into the primary-work frontmatter's `related_thinkers[]`. Fixed in commit `846bccb`. Re-emitted all 238 primary-works. Touchstones like Adam Smith, Hayek, Marx, Lincoln, Bernard Shaw, McNamara now show "Mentioned in" sections on their bio pages.

**So primary-works are already partially Phase-B-enabled** — they have structured mentions because the extraction did them. What's missing is the same for Tier-A bodies (musings, opinions, interviews, theprint-mirror), which were imported from WordPress and never AI-processed for cross-thinker references.

---

## What you are building — Phase B (in-prose NER)

### The goal

For every Tier-A entry (musings, opinions, interviews, theprint-mirror) AND a richer re-do of primary-works:

1. Send the body to `claude -p` along with the authority listing
2. The LLM identifies every named-thinker mention with role classification + verbatim evidence + reasoning
3. Apply to frontmatter so the thinker bio pages can surface these mentions with their evidence

### Adnan's key requirements (these are non-negotiable)

1. **Pure LLM. No regex.** Adnan explicitly rejected hybrid regex+LLM. The LLM has the full body and the full authority list; that's enough.

2. **Evidence + reasoning are public, not gated behind editorial review.** Adnan said "do not have evidence as review or anything. Just let it go. I mean, you are over-doubting an LLM." The LLM's outputs go straight to the bio page. No `needs_review` flag on the evidence quotes or reasoning.

3. **Role-aware evidence handling.** For entries where one thinker is the SUBJECT (the whole article is about them), don't quote the whole article. The LLM picks **2-4 cool key passages** — curated highlights. For mention-role thinkers, **1-3 verbatim evidence excerpts** per location.

4. **"How [Thinker] is discussed across the corpus" UI.** The bio page surfaces the evidence quotes contextually, not as a flat list. This is the user-facing payoff — it turns the catalogue into a contextual map.

### Data model

Extend the schemas in `apps/site/src/content.config.ts`. For each entry, add:

```typescript
const thinkerMention = z.object({
  thinker: reference('thinkers'),
  role: z.enum(['author', 'subject', 'mention']),
  reasoning: z.string(),                                      // 1-2 sentences
  evidence: z.array(z.object({
    quote: z.string(),                                         // verbatim from body
    context: z.string().optional(),                            // one-line context for `mention` role
  })).default([]),
  key_passages: z.array(z.object({
    quote: z.string(),                                         // verbatim from body
    what_it_shows: z.string(),                                 // for `subject` role only — what this passage demonstrates
  })).default([]),
});
```

Then add `thinker_mentions: z.array(thinkerMention).default([])` to:
- musings, opinions, interviews, theprint-mirror schemas
- primary-works + periodicals schemas (this REPLACES the current cross_thinker_mentions handling — richer, with evidence)

The existing `related_thinkers: z.array(reference('thinkers'))` field stays as a flat slug list for fast bio-page filtering. Populate it automatically from `thinker_mentions[].thinker` slugs during the apply step.

### Architecture (mirror Phase A exactly)

```
scripts/synthesis/
├── prompts/
│   ├── system-resolver.txt           (Phase A — already exists)
│   ├── system-ner.txt                (NEW — Phase B canonical prompt)
│   └── README.md                     (update with Phase B paths)
├── prepare-ner-batches.py            (NEW — emits data/synthesis/ner-input.jsonl)
├── resolve-ner.py                    (NEW — headless claude -p driver,
│                                            mirror of resolve-unlinked.py)
└── apply-ner.py                      (NEW — reads mentions.jsonl,
                                              writes thinker_mentions[] to frontmatter)
```

Reuse the exact patterns from Phase A:
- Same circuit-breaker copied from `resolve-unlinked.py` (parses reset times)
- Resumable: skip entries already resolved
- Both manual chat-path AND `claude -p` headless work from the same prompt file

### The prompt design (`scripts/synthesis/prompts/system-ner.txt`)

Reference the existing `scripts/synthesis/prompts/system-resolver.txt` for shape and tone — same conventions, same role section, same authority-list handling, same `## Authority` and `## Entries to resolve` user-message structure.

Key instructions to include:

1. **Input shape**: each entry has `id, collection, title, body (full markdown)`. The user message also includes the `## Authority` block (slug `::` canonical pairs).

2. **For each authority thinker who actually appears in the body**, emit one JSON line:

   ```json
   {
     "entry_id": "...",
     "thinker_id": "friedrich-hayek",
     "role": "mention",
     "reasoning": "Hayek is invoked twice as the theoretical anchor for the author's anti-planning argument.",
     "evidence": [
       {"quote": "verbatim from body", "context": "one-line framing of where in the argument"}
     ]
   }
   ```

   For `subject` role, replace `evidence` with `key_passages` (2-4 entries, each with `quote` + `what_it_shows`).

3. **Forbid invention**: only emit thinker_ids that appear in the authority list. Only emit quotes that are verbatim substring-matches of the body.

4. **Skip thinkers who don't actually appear**: no speculation, no "this is the kind of essay where X would be relevant." Only structural evidence.

5. **Role decision tree**:
   - `author`: the entry's byline IS this thinker (already captured by Phase A; rarely needed here)
   - `subject`: the entire entry is a profile of this thinker (the title is "X: …" or "X — …" pattern, body discusses them throughout)
   - `mention`: this thinker is invoked / quoted / referenced inside an entry whose primary subject is something else

6. **Output format**: one JSON object per line. No prose. No fences. The apply step parses line-by-line.

Worked examples should be in the prompt — pick one for each role from real entries (e.g., the Anandibai Joshee opinion for `subject`, the Godrej blueprint summary for `mention`).

### Scale estimate

- 405 Tier-A entries + 238 primary-works re-do = ~643 entries
- Batch size 8-15 entries per `claude -p` call (each entry has 500-3000 words of body)
- ~50-80 calls total
- Bodies + authority listing fit in the prompt budget per call
- Rate-limited; expect to need at least one pause cycle

### Apply step specifics

`apply-ner.py` should:

1. Read `data/synthesis/mentions.jsonl` (the resolver output)
2. Group by `entry_id`
3. For each entry:
   - Validate every `evidence[].quote` is a substring of the body (verbatim check). Drop mentions that fail. Log.
   - Validate every `thinker_id` is in the current authority. Drop unknowns. Log.
   - Write `thinker_mentions[]` to the entry's frontmatter
   - Also populate `related_thinkers[]` with the slug-only list (de-duped, excluding the author/subject of the entry)
4. Idempotent — re-running should be safe; existing `thinker_mentions[]` is replaced atomically per-entry

### Bio page changes

`apps/site/src/pages/thinkers/[slug].astro`:

1. Read every entry that has this thinker in `thinker_mentions[]`
2. Add a new top-level section **"How [Thinker] is discussed in this archive"** that aggregates the LLM's `reasoning` strings from all entries — maybe just the first sentence of each, joined with paragraph breaks.
3. Under the existing "Mentioned in" sub-sections, render the evidence quotes inline (collapsible blockquote, one per entry).
4. For entries where role is `subject` AND this thinker is the subject, surface the `key_passages` in a "Highlight" treatment under the entry title.

### Acceptance criterion

For a touchstone like A. D. Shroff:

- Bio page shows "How A. D. Shroff is discussed in this archive" with 2-3 paragraphs of aggregated context
- Under each Mentioned-in work, the evidence quote renders inline
- For the few opinions that are profile pieces about Shroff, the key_passages section shows the curated highlights

The bio page becomes the canonical "what does this archive say about X?" surface.

---

## How to start the new session

Do this exactly:

```bash
cd "/Users/siraj/Indian Liberals Website"
git status
git log --oneline -5
date
```

Then read **this file** (`docs/superpowers/specs/2026-05-18-phase-b-ner-handoff.md`) — that's the spec.

Then read the Phase A files for the patterns you'll mirror:
- `scripts/synthesis/prompts/system-resolver.txt` — prompt structure
- `scripts/synthesis/prompts/README.md` — manual vs automated path framing
- `scripts/synthesis/resolve-unlinked.py` — circuit breaker + claude -p invocation
- `scripts/synthesis/apply-resolutions.py` — frontmatter mutation patterns

Then **before writing any code**, run the brainstorming skill ONLY to confirm scope with Adnan (he is in the chat). The design above is approved. The question is sequencing — does Adnan want you to run the whole batch via headless `claude -p`, or process some interactively, or split.

After confirmation, build in this order:

1. `scripts/synthesis/prompts/system-ner.txt` (write the prompt; iterate with Adnan on 2-3 worked examples)
2. Schema patch in `apps/site/src/content.config.ts` (add `thinkerMention` shape + `thinker_mentions[]` field across the 6 collections)
3. `prepare-ner-batches.py` → emits the input JSONL
4. `resolve-ner.py` → mirror of resolve-unlinked.py
5. **Run a smoke batch** of 5-10 entries to validate the prompt; show Adnan the output JSON; tune
6. `apply-ner.py` → frontmatter mutation
7. Run the full batch (will need to pause across rate-limit windows)
8. Bio page updates
9. Build, verify, commit, push

---

## Decisions already locked in (don't relitigate)

- Pure LLM. No regex. Adnan's explicit choice.
- Evidence + reasoning public, no editorial gate. Adnan's explicit choice.
- Subject role gets 2-4 curated key passages, not full quote. Adnan's explicit framing.
- Stub thinkers from Phase A stay (`bio_source: ai_drafted_stub`). Phase 1.5 drafts real bios later.
- ThePrint mirror pages are AI-only (humans go out to theprint.in). Already in production code.
- Footer year auto-updates on every page load via inline JS.

---

## Files you should NOT touch unless you know why

- `apps/site/src/content/thinkers/*.md` for any thinker with `bio_source: canonical` or `feature_article` — those are hand-curated by CCS.
- `apps/site/src/content/musings/*.md`, `apps/site/src/content/opinions/*.md`, `apps/site/src/content/interviews/*.md` — the body content is from the legacy WordPress site. You are only adding frontmatter fields.
- Anything under `data/raw/` or `/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/` — these are read-only source artifacts.

---

## When you finish Phase B

Run the same coverage recount Phase A used:

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 scripts/synthesis/prepare-unlinked.py
```

The unlinked count should drop further (from 236 today). The acceptance is not 0 — some entries are genuinely thematic. But every touchstone thinker should now have rich mentions.

Then proceed to Day 10 deployment work:
- R2 upload script for PDFs
- Sveltia CMS config
- Cloudflare Pages deploy
- DNS cutover prep
- Launch on Day 14

The plan doc for Days 10-14 lives at:
```
~/.gstack/projects/IndianLiberalsWebsite/siraj-main-engagement-finale-plan-20260518.md
```

---

## Loose threads worth knowing

- **Sudha R. Shenoy** has very few works in the archive because her published output is mostly post-1991 essays that aren't in the priority queue. Phase B might add mentions from other works.
- **Periodicals** collection is empty (`apps/site/src/content/periodicals/` has no files). The 25 Khoj Gujarati issues are filed under primary-works instead. Leave it.
- **The runner** (PID 25812 right now) will eventually finish ~944 PDFs over the next 1-2 days. As each new primary-work emerges, you may want to re-run Phase B's NER step on the new ones — or just trigger a full re-run after the runner finishes.

---

**End of handoff.** The new session has everything it needs. Adnan, paste this file's path into the new chat:

```
/Users/siraj/Indian Liberals Website/docs/superpowers/specs/2026-05-18-phase-b-ner-handoff.md
```
