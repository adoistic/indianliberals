# Phase B — In-prose NER handoff

**For:** the next Claude Code session that picks up this work
**From:** the long Sunday 2026-05-18 session that built indianliberals.in's Phase A
**Date written:** 2026-05-18 08:03 IST
**Branch:** `main` (everything is committed and pushed to GitHub)

> **How to read this file:** if you (the fresh session) are reading this because
> Adnan pasted the path, START by running the commands in **§ Before you start —
> verify state** below. The PIDs and counts in this doc were point-in-time at
> 08:03 IST on 2026-05-18. Verify everything yourself before acting. The
> *decisions* in this doc are durable; the *numbers* are stale by definition.

---

## You are Adnan's engineering pair on this project

The macOS account is `siraj` but the human is **Adnan**, founder of Thothica. This is a Thothica engagement for the Centre for Civil Society (CCS), funded by the Friedrich Naumann Foundation for Freedom. CCS owns the editorial side. Thothica owns the build.

The site is **indianliberals.in** — a digital archive of the Indian liberal tradition. It launches in approximately 7 days.

Two CCS editorial owners post-handoff (per the project memory file): **Arjun** and **Kumar Anand** (Kumar is CCS Head of Research).

Adnan's persistent project memory (read it for any clarifying user-preference signals you might need) lives at:

```
/Users/siraj/.claude/projects/-Users-siraj-Indian-Liberals-Website/memory/MEMORY.md
```

There is no project-root `CLAUDE.md` — gstack memory is the source of truth for user-style preferences.

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

## Before you start — verify state

The PIDs and counts in this doc were captured at 2026-05-18 08:03 IST. They WILL be stale. Run all of these and reason from the current output, not from this doc's numbers:

```bash
cd "/Users/siraj/Indian Liberals Website"
date
git status              # should be clean; main branch
git log --oneline -10   # last commit should be docs/readme update from this session

# Runner state
pgrep -fl run_overnight                        # is any runner process alive?
pgrep -f "^claude" | wc -l                     # any active claude -p workers?
tail -20 /tmp/v1.5-overnight-progress.tsv      # recent activity / breaker trips
find data/bake-off-output -maxdepth 2 -name "summary.json" | wc -l   # PDFs fully baked

# External drive (the runner READS PDFs from here)
ls "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher" 2>/dev/null | head -3
# If this returns nothing, the drive is unmounted — the runner CAN'T extract more PDFs
# until Adnan plugs it back in. Phase B doesn't need the drive; only the runner does.

# Python venv for the extraction pipeline + synthesis scripts
ls .venv-extract/bin/python3 2>/dev/null
# If missing, recreate: python3 -m venv .venv-extract && source .venv-extract/bin/activate
# and install whatever the extraction scripts need. Phase B scripts only need stdlib,
# but emit-astro-md.py uses no external libs either, so the venv is mostly cosmetic.

# Astro preview
pgrep -f "astro preview" | head -1
# If empty, start it:
# cd apps/site && nohup npx --offline astro preview --host 127.0.0.1 --port 4321 > /tmp/astro-preview.log 2>&1 &

# Authority size (changes over time as the runner adds stubs)
python3 -c "import json; d=json.load(open('data/authority/thinkers.json')); print(f'thinkers: {len(d[\"thinkers\"])}, byline_lookup: {len(d.get(\"byline_lookup\",{}))}')"
```

### Decision tree based on output

- **Runner is alive (pgrep finds it) AND 0 claude procs**: it's paused on the circuit breaker. Check `tail -20 /tmp/v1.5-overnight-progress.tsv` — the last `__BREAKER_TRIP__` line tells you when it's expected to resume. Leave it. Don't restart.
- **Runner is alive AND N>0 claude procs**: it's actively working. Leave it.
- **Runner is NOT alive AND last log line is `__END__`**: the queue drained or it exited. Restart only if the bake-off-output count is < ~944 (i.e., the corpus isn't fully extracted yet):
  ```bash
  source .venv-extract/bin/activate && nohup python3 scripts/llm-extract/run_overnight.py --concurrency 12 > /tmp/v1.5-overnight.log 2>&1 &
  ```
  Phase B does NOT need the runner running. They're independent.
- **External drive is unmounted**: don't restart the runner; tell Adnan. Phase B is unaffected.

**Snapshot at handoff (will be stale by the time you read this):**

- Overnight extraction runner: PID **25812**, alive ~2h 52min, idle (rate-limited).
- Astro preview server: PID **53630**.
- 220 of ~944 PDFs baked. 462 thinkers in authority.

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

The schemas live in `apps/site/src/content.config.ts`. Shared sub-schemas are factored out into `apps/site/src/schemas/{i18n,rights,provenance,people,extraction,synthesis}.ts` and re-exported from `apps/site/src/schemas/index.ts`. For Phase B, create a NEW shared module:

**File to CREATE:** `apps/site/src/schemas/mentions.ts`

```typescript
import { z, reference } from 'astro:content';

// In-prose thinker mention — populated by the Phase B NER pass.
// One record per (entry, thinker) pair where the thinker appears in the body.
//
// role:
//   - 'author'  — the entry was authored by this thinker. Rarely populated
//                 here; Phase A handled the byline-based author detection
//                 via `author` / `authors[]` / `contributors[]` fields.
//   - 'subject' — the entry is primarily ABOUT this thinker (profile pieces,
//                 obituaries). For this role, `key_passages` is populated
//                 with 2-4 curated highlights from the body and `evidence`
//                 stays empty.
//   - 'mention' — the thinker is invoked / quoted / referenced inside an
//                 entry whose primary subject is something else. For this
//                 role, `evidence` carries 1-3 verbatim excerpts with
//                 one-line context strings.
//
// reasoning: 1-2 sentences explaining what this thinker contributes to the
//            entry. Rendered publicly on the bio page; NOT gated behind
//            editorial review (Adnan's explicit call — trust the LLM).
//
// Every quote MUST be a verbatim substring of the entry's rendered body
// text. The apply step (apply-ner.py) validates this and drops mentions
// whose quotes don't substring-match.

export const thinkerMention = z.object({
  thinker: reference('thinkers'),
  role: z.enum(['author', 'subject', 'mention']),
  reasoning: z.string(),
  evidence: z.array(z.object({
    quote: z.string(),
    context: z.string().optional(),
  })).default([]),
  key_passages: z.array(z.object({
    quote: z.string(),
    what_it_shows: z.string(),
  })).default([]),
});
```

Then re-export from `apps/site/src/schemas/index.ts`:

```typescript
export * from './mentions';
```

Then add `thinker_mentions: z.array(thinkerMention).default([])` to each of these 6 collection schemas in `content.config.ts`. The simplest way: grep for `related_thinkers: z.array(reference('thinkers'))` — it appears in opinions, theprint-mirror, primary-works, periodicals (and you'll add it to musings + interviews too if not present). Drop `thinker_mentions` right after `related_thinkers` in each. Collections to update:

| Collection | Already has `related_thinkers`? | Action |
|---|---|---|
| musings | yes (added during Phase A) | add `thinker_mentions` |
| opinions | yes | add `thinker_mentions` |
| interviews | NO (only has `related_thinkers` if I missed it — verify) | add both |
| theprint-mirror | yes | add `thinker_mentions` |
| primary-works | yes | add `thinker_mentions` |
| periodicals | yes (via shared schema) | add `thinker_mentions` (collection is empty today but schema should be future-proof) |

Don't forget to add the import: `import { thinkerMention } from './schemas';` at the top of `content.config.ts`. The existing schemas import similarly.

The existing `related_thinkers: z.array(reference('thinkers'))` field stays as a flat slug list for fast bio-page filtering. `apply-ner.py` populates it from `thinker_mentions[].thinker` slugs at apply time.

### Verbatim substring check — be precise about this

The "quote must be a verbatim substring of the body" rule sounds simple but has gotchas:

1. **Markdown formatting** — if the body has `*Hayek* argued...` and the LLM emits the quote `"Hayek argued"`, that's NOT a substring match (the asterisks aren't there in the LLM's output). Strip markdown formatting from BOTH sides before comparing:
   - Remove `*`, `_`, `~`, backticks, `>`
   - Collapse multiple whitespace to single space
   - Then check substring match
2. **Smart quotes vs straight quotes** — bodies may have `"…"` curly while LLM emits `"…"` straight. Normalise both: replace `"` `"` `'` `'` with `"` and `'`.
3. **Case sensitivity** — keep case-sensitive matching. False positives from case-insensitive matching are worse than false negatives here.
4. **Trailing punctuation** — allow the LLM's quote to end without a final period that's in the body. Trim trailing `.`, `,`, `;`, `:` before comparing.

The validator is a small pure function. Put it in `scripts/synthesis/apply-ner.py` as a top-level helper.

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

### Scope, scale, and budget

**Language scope:** English entries only for the v1 NER pass. The corpus has `language: hi | gu | mr | bn` entries (mostly Marathi musings under Sharad Joshi and Gujarati Khoj issues) that we leave for a later language-specific pass. Adnan's authority is English-name-keyed so non-English bodies won't resolve cleanly anyway. The Phase A scripts use the same filter — `.data.language === "en"` — adopt that pattern.

**Output filename:** `data/synthesis/ner-mentions.jsonl` (consistent with the Phase A pattern of `<phase>-<role>.jsonl`). One JSON object per line; one line per `(entry, thinker)` pair (so a musing that mentions Hayek and Smith produces two lines).

**Scale:**
- ~405 Tier-A English entries (musings 224 + opinions 61 + interviews 72 + theprint 48; exact counts will differ at the moment you start — recount).
- ~238 primary-works to re-do (still growing as the runner extracts more).
- Total ~640 entries.

**Per-batch budget:** `claude -p` accepts ~200K tokens of context, so theoretically you could send the whole authority + many entries at once. In practice, the authority listing is ~13KB (~3K tokens) and each entry's body is up to ~3,000 words (~4K tokens). Conservative batch size: **8 entries per call** (~35K tokens input). If a batch returns nothing or errors, halve the batch and retry. The `resolve-ner.py` driver should handle this.

**Expected call volume:** ~80 calls. With the 5h rate limit on the headless lane and concurrency 2, expect 2-3 pause cycles. Phase B doesn't have a hard deadline; it can run over a couple of days.

**One important separation:** Phase B is independent of the extraction runner. You can run both at the same time (they share the `claude -p` rate-limit pool, so they'll throttle each other, but that's fine — both have circuit breakers).

### Apply step specifics

`apply-ner.py` should:

1. Read `data/synthesis/ner-mentions.jsonl` (the resolver output).
2. Group by `entry_id`.
3. For each entry:
   - Validate every `evidence[].quote` and `key_passages[].quote` is a substring of the body's plain-text projection (see "Verbatim substring check" above for normalisation rules). Drop mentions that fail validation; log them to `data/synthesis/ner-rejected.txt`.
   - Validate every `thinker_id` is in the current authority. Drop unknowns; log.
   - Write `thinker_mentions[]` to the entry's frontmatter as a YAML block.
   - Also populate `related_thinkers[]` with the slug-only list (de-dup; exclude the entry's own author/subject IDs so a thinker doesn't get cross-referenced from a work they wrote).
4. Idempotent — re-running replaces the entire `thinker_mentions[]` block atomically per entry. The Phase A apply script had a frontmatter-writer pattern (`set_frontmatter_field` and the block-handling for arrays); read `scripts/synthesis/apply-resolutions.py` and reuse the YAML-emit helpers.

### Smoke batch — validate the prompt before scaling

Before running the full batch, send 8 carefully-picked entries through `resolve-ner.py` and read the output JSON by hand. Pick entries that exercise every code path:

```
1. opinions/anandibai-joshee                                   # subject role (whole article)
2. opinions/homi-modys-liberalism-pro-business-to-pro-market   # subject role
3. opinions/gg-agarkar-revisiting-a-misunderstood-legacy       # subject role
4. musings/economic-reforms-in-india                           # mention role — Manmohan Singh, Narasimha Rao, Shroff
5. musings/1991-liberal-reforms-why-no-one-celebrated-them-ashok-desai-1995  # author + mentions
6. interviews/a-d-shroff-champion-of-free-enterprise           # interview about a thinker
7. theprint-mirror/ad-shroff-socialism-free-enterprise-lessons # ThePrint piece, author known
8. primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980  # primary-work mention-heavy; already has cross_thinker_mentions, Phase B should add evidence quotes
```

Show Adnan the JSON output. Iterate on the prompt until those 8 produce sensible, verbatim-correct mentions. Then run the full batch.

### Bio page changes

The file is `apps/site/src/pages/thinkers/[slug].astro`. Today it has three sections in this order:

1. Header (portrait + canonical name + dates + tradition + body markdown of the bio)
2. **By {Thinker}** — works/excerpts/opinions/theprint articles authored by this thinker
3. **About {Thinker}** — interviews + opinions where they are the subject
4. **Mentioned in** — entries in `related_thinkers[]` but not author/subject
5. `<RelatedSection>` — TF-IDF related links

Phase B adds two new affordances:

**(a)** A new section **between the header and "By {Thinker}"** titled `How {Thinker} is discussed in this archive`. Compute it by walking every entry that has this thinker in `thinker_mentions[]` and concatenating the `reasoning` strings (first sentence of each) into 2-3 paragraphs. Group by role: "Authored 22 works including…", "Subject of 1 profile piece (…)", "Referenced in N other works including…". Keep prose readable, not a list dump.

**(b)** Under the existing **Mentioned in** subsections, when listing each work, render the matching evidence quote(s) inline as a small blockquote under the work title (max 2 quotes per entry to avoid bloat). On `subject` role entries (rare — they belong in the "About" section, not "Mentioned in"), surface 1-2 `key_passages` as the highlight reel under the "About" subsection.

Both sections share data — both walk every entry's `thinker_mentions[]` looking for this thinker. The Phase A counting block (`worksByThisThinker`, `interviewMentions`, etc.) stays as-is — Phase B adds new walks alongside it.

### Acceptance criterion

For a touchstone like A. D. Shroff:

- Bio page shows "How A. D. Shroff is discussed in this archive" with 2-3 paragraphs of aggregated context
- Under each Mentioned-in work, the evidence quote renders inline
- For the few opinions that are profile pieces about Shroff, the key_passages section shows the curated highlights

The bio page becomes the canonical "what does this archive say about X?" surface.

---

## How to start the new session

You (the new session) will see Adnan paste the path to this file into chat. Wait for that — don't proceed on imagined context. Then:

1. Run every command in **§ Before you start — verify state** above and reason from the output. Brief Adnan on what's running / what the current counts are.

2. Read these files (in order — they're all needed for Phase B):
   - `docs/superpowers/specs/2026-05-18-cross-link-audit-design.md` — Phase A spec, full context
   - `scripts/synthesis/prompts/system-resolver.txt` — the canonical Phase A prompt; Phase B's prompt mirrors this exactly in shape
   - `scripts/synthesis/prompts/README.md` — the manual-vs-automated dual-path framing
   - `scripts/synthesis/resolve-unlinked.py` — the headless `claude -p` driver with circuit breaker (~280 lines; read it carefully — Phase B's `resolve-ner.py` is a near-mirror)
   - `scripts/synthesis/apply-resolutions.py` — frontmatter mutation patterns; the helpers `set_frontmatter_field` and the byline-alias logic are what `apply-ner.py` should imitate
   - `scripts/synthesis/emit-astro-md.py` (just the YAML emit helpers at the top, `_yaml_dict` and `_yaml_list` — `apply-ner.py` will emit a nested `thinker_mentions[]` block and these are the easiest reusable utilities)
   - `apps/site/src/content.config.ts` — see how the existing schemas are composed; understand the shared-schema pattern in `apps/site/src/schemas/`

3. **Invoke `superpowers:brainstorming` ONLY to confirm sequencing**, not to redesign. The design is locked. The brainstorming skill helps you scope the smoke batch, decide whether to process Tier-A in parallel with primary-works re-emit, and pick worked examples for the prompt. Do not relitigate any of the locked-in decisions (see § Decisions already locked in).

4. **Heads-up on pre-existing issues** (so you don't blame Phase B for them):
   - `astro check` returns **1 error** today: a Tailwind/Vite plugin type mismatch in `astro.config.mjs:32` and 9 warnings/hints (Search.astro nullability, ThinkerCard unused import, `/pagefind/pagefind.js` missing type). None of these are Phase B's fault. Total before any Phase B change: **10 errors**. Track the delta.
   - The actual ASTRO BUILD is clean — `npm run build` succeeds and produces 1,225+ pages. Only `astro check` (type-only) flags these.
   - 4 files have `id: "<filename-stem>"` that was repaired from a sweep bug earlier in the session: `apps/site/src/content/interviews/{liberalism-and-the-challenge-of-polarisation,the-future-of-liberalism-in-a-post-pandemic-world,bollywood-and-cultural-change-in-attitude,...}.md`. These IDs are correct as-is — they match the filename stems and the slug routing depends on them. Don't "fix" them.
   - The 1 known-good error log from the apply-resolutions.py run: a single entry with `match_to_unknown_thinker:...` — also fine, it's just one corrupted resolution that got rejected.

5. Build in this order:

   ```
   1. scripts/synthesis/prompts/system-ner.txt    (write prompt; iterate with Adnan on
                                                   the 8 smoke-batch examples)
   2. apps/site/src/schemas/mentions.ts           (NEW module; export thinkerMention)
   3. apps/site/src/schemas/index.ts              (add: export * from './mentions';)
   4. apps/site/src/content.config.ts             (import + add thinker_mentions field
                                                   to all 6 collections; bare-grep each one)
   5. Run `npx --offline astro check` — confirm error count is the same 10 (no new ones)
   6. scripts/synthesis/prepare-ner-batches.py    (read English entries; emit
                                                   data/synthesis/ner-input.jsonl)
   7. scripts/synthesis/resolve-ner.py            (mirror of resolve-unlinked.py)
   8. Run smoke batch of 8 entries (see § Smoke batch); show Adnan the JSON;
      iterate the prompt until correct
   9. scripts/synthesis/apply-ner.py              (read ner-mentions.jsonl;
                                                   validate; mutate frontmatter)
  10. Run full batch via resolve-ner.py
  11. Run apply-ner.py
  12. Update apps/site/src/pages/thinkers/[slug].astro per § Bio page changes
  13. npm run build → verify 1,225+ pages, no new errors
  14. python3 scripts/synthesis/audit-ner-coverage.py (write this small audit;
      reports % of Tier-A entries with non-empty thinker_mentions[])
  15. Commit + push each step as a separate commit. Reference the Phase A
      commits as templates for the messages.
   ```

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

## Phase B success metric

Phase B's success is NOT the Phase A unlinked count (Phase A is about author/subject; Phase B is about in-prose mentions). Write a small `scripts/synthesis/audit-ner-coverage.py` that reports:

```
Tier-A entries with at least one thinker_mentions[] record:  N / total
Average thinker_mentions count per English entry:             X
Touchstone coverage (top 20 thinkers by expected mention):    A.D. Shroff (live: M; expected: ≥50),
                                                              Nehru (live: M; expected: ≥40),
                                                              Adam Smith (live: M; expected: ≥5),
                                                              Hayek (live: M; expected: ≥5),
                                                              ...
Entries with zero matches (likely truly-thematic editorials): K
```

**Acceptance criteria:**
- ≥80% of Tier-A English entries have at least one `thinker_mentions[]` record.
- Every "touchstone" thinker (A.D. Shroff, Nehru, Gandhi, Hayek, Smith, Marx, Palkhivala, Masani, Shenoy, Bhagwati, plus a few more) has visible mentions across multiple works on their bio page.
- The "How {Thinker} is discussed in this archive" section renders sensible 2-3-paragraph synthesis for at least 30 thinkers.
- `npm run build` clean. `astro check` error count unchanged.
- Spot-check 10 random evidence quotes: every one substring-matches the body when normalised per § Verbatim substring check.

If any of these fail, iterate on the prompt + re-run resolve-ner.py + apply-ner.py. The pipeline is fully idempotent and resumable.

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
