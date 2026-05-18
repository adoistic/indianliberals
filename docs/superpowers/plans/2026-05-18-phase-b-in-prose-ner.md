# Phase B In-Prose NER Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a pure-LLM in-prose named-entity-recognition pass across musings + opinions + theprint-mirror + primary-works (summary prose), producing per-entry `thinker_mentions[]` records with verbatim evidence quotes that drive a new "How {Thinker} is discussed in this archive" surface on every bio page.

**Architecture:** Mirror Phase A's `prepare → resolve → apply` pipeline using the same `claude -p` headless driver, the same circuit-breaker pattern, and the same prompt-as-source-of-truth dual-path (manual chat AND headless). New shared Zod sub-schema `thinkerMention` wired into 5 content collections via `apps/site/src/schemas/`. A new pure-function verbatim-substring validator in `apply-ner.py` drops mentions whose quotes don't substring-match the body under normalisation rules.

**Tech Stack:** Astro 5 + Zod for the content layer; Python 3 stdlib for the pipeline (no new dependencies); `claude -p` CLI for LLM dispatch; existing `scripts/synthesis/` patterns from Phase A.

**Spec references (read these before starting):**
- Parent design (durable): [`docs/superpowers/specs/2026-05-18-phase-b-ner-handoff.md`](../specs/2026-05-18-phase-b-ner-handoff.md)
- Supplementary spec (brainstorming output, scope-locked): [`docs/superpowers/specs/2026-05-18-phase-b-scope-and-b2-audio.md`](../specs/2026-05-18-phase-b-scope-and-b2-audio.md)

**Pre-flight reading (in order, before Task 1):**
- `scripts/synthesis/prompts/system-resolver.txt` — Phase A's canonical prompt; Phase B's prompt mirrors its shape exactly
- `scripts/synthesis/resolve-unlinked.py` — the headless driver Phase B's `resolve-ner.py` is a near-mirror of
- `scripts/synthesis/apply-resolutions.py` — the frontmatter-mutation patterns Phase B's `apply-ner.py` reuses
- `scripts/synthesis/emit-astro-md.py` lines 1-140 — the `_yaml_str`, `_yaml_list`, `_yaml_dict`, `write_md` helpers `apply-ner.py` will reuse to emit the nested `thinker_mentions[]` block
- `apps/site/src/content.config.ts` + `apps/site/src/schemas/` — the schema composition pattern

**Working directory:** `/Users/siraj/Indian Liberals Website/.claude/worktrees/festive-kepler-096509` (this worktree). Branch: `claude/festive-kepler-096509` (will merge to `main` post-completion).

**Verification harness:** This project uses plain-Python assert-style test scripts run via `.venv-extract/bin/python3` (see `scripts/llm-extract/test_transliteration.py` for the established pattern). No pytest. For schema changes, `npx --offline astro check` is the verification command. The baseline `astro check` error count to track delta against is captured in Task 4.

---

## Chunk 1: Schema foundation

This chunk wires Phase B's data model into the Astro content layer without touching any pipeline code. After this chunk lands, `astro check` and `npm run build` must still succeed with no new errors — the schemas accept Phase B data but no Phase B data exists yet.

### Task 1: Create the `thinkerMention` shared sub-schema

**Files:**
- Create: `apps/site/src/schemas/mentions.ts`

**Per supplementary spec §1 and parent doc § Data model.** This module is the single source of truth for the in-prose mention record. The shape is shared across the 5 collections that will carry `thinker_mentions[]`.

- [ ] **Step 1: Create the file**

Create `apps/site/src/schemas/mentions.ts` with this content (verbatim from parent doc § Data model, with comments tightened):

```typescript
import { z, reference } from 'astro:content';

// In-prose thinker mention — populated by the Phase B NER pass.
// One record per (entry, thinker) pair where the thinker appears in the body.
//
// role:
//   - 'author'  — the entry was authored by this thinker. Rarely populated
//                 here; Phase A handled byline-based author detection via
//                 `author` / `authors[]` / `contributors[]` fields.
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
//            editorial review.
//
// Every quote MUST be a verbatim substring of the entry's rendered body
// text (under the normalisation rules in apply-ner.py). The apply step
// validates this and drops mentions whose quotes don't substring-match.

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

- [ ] **Step 2: Verify the file parses with Astro's TypeScript checker**

Run from repo root:
```bash
cd apps/site && npx --offline tsc --noEmit src/schemas/mentions.ts 2>&1 | head -5
```

Expected output: nothing (clean compile), OR a `Cannot find module 'astro:content'` error if running tsc bare. The second is acceptable because `astro:content` is virtualised — the real check happens in Task 4 via `astro check`.

- [ ] **Step 3: Commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/schemas/mentions.ts
git -c commit.gpgsign=false commit -m "feat(schema): add thinkerMention shared sub-schema for Phase B"
```

---

### Task 2: Re-export `thinkerMention` from the schemas barrel

**Files:**
- Modify: `apps/site/src/schemas/index.ts` (add one export line)

- [ ] **Step 1: Read current state of the file**

Read `apps/site/src/schemas/index.ts`. The end of the file (after `synthesis.ts`) is the insertion point.

- [ ] **Step 2: Add the re-export**

Append one line and update the leading comment block:

```typescript
// Barrel re-export for all shared schema primitives. Import these into
// content.config.ts (and from future scripts that need the same Zod shapes,
// e.g., the synthesis validators in scripts/synthesis/).
//
// Organisation:
//   i18n.ts         — LANG_CODES, i18nFields, multilingualTitle
//   rights.ts       — rightsSchema
//   provenance.ts   — aiProvenance, confidenceFlag
//   people.ts       — thinkerName, organisationName
//   extraction.ts   — LLM extraction shapes (pageSystem, pullQuote, tocEntry, …)
//   synthesis.ts    — readingGuide, intellectualArc
//   mentions.ts     — thinkerMention (Phase B in-prose NER)

export * from './i18n';
export * from './rights';
export * from './provenance';
export * from './people';
export * from './extraction';
export * from './synthesis';
export * from './mentions';
```

- [ ] **Step 3: Commit**

```bash
git add apps/site/src/schemas/index.ts
git -c commit.gpgsign=false commit -m "feat(schema): re-export thinkerMention from schemas barrel"
```

---

### Task 3: Add `thinker_mentions[]` to five content collections

**Files:**
- Modify: `apps/site/src/content.config.ts` (5 collection schemas + 1 import line)

**Per supplementary spec §1 (in-scope: musings, opinions, theprint-mirror, primary-works, periodicals).** Do NOT touch interviews — interviews are deferred to Phase B-2.

The supplementary spec §7 step 4 also flags that `periodicals` is missing `related_thinkers` (the parent doc was wrong about it being present); add that here too for future-proofing.

- [ ] **Step 1: Import `thinkerMention` at the top of `content.config.ts`**

In the existing import block (lines 18-36, the `import { ... } from './schemas';` block), add `thinkerMention` to the alphabetical list:

```typescript
import {
  aiProvenance,
  confidenceFlag,
  crossThinkerMention,
  essaySummarized,
  i18nFields,
  intellectualArc,
  multilingualTitle,
  organisationName,
  pageSystem,
  pullQuote,
  purposeEnum,
  readingGuide,
  recommendedAuthorityAddition,
  rightsSchema,
  summaryStructured,
  thinkerMention,
  thinkerName,
  tocEntry,
} from './schemas';
```

- [ ] **Step 2: Add `thinker_mentions: z.array(thinkerMention).default([])` to the `musings` schema**

Locate the `musings` `defineCollection` block (around line 112). Find the `related_thinkers` line. Add `thinker_mentions` immediately after it. The change region (existing two lines + one new line):

```typescript
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    themes: z.array(z.string()).default([]),
```

- [ ] **Step 3: Add the same field to `opinions`**

Locate `opinions` (around line 135). After `related_thinkers`:

```typescript
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    ...i18nFields,
```

- [ ] **Step 4: Add to `primaryWorks`**

Locate `primaryWorks` (around line 184). After `related_thinkers`:

```typescript
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    related_works: z.array(z.string()).default([]),
```

- [ ] **Step 5: Add to `theprintMirror`**

Locate `theprintMirror` (around line 394). After `related_thinkers`:

```typescript
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    related_works: z.array(z.string()).default([]),
```

- [ ] **Step 6: Add BOTH `related_thinkers` and `thinker_mentions` to `periodicals`**

Locate `periodicals` (around line 323). The schema doesn't currently have `related_thinkers`. Add both fields together near the top, right after `themes`:

```typescript
    themes: z.array(z.string()).default([]),
    related_thinkers: z.array(reference('thinkers')).default([]),
    thinker_mentions: z.array(thinkerMention).default([]),
    // Editorial-ready prose summary of the issue ...
```

- [ ] **Step 7: Verify the import line and all 5 collections compile**

```bash
cd apps/site && npx --offline astro check 2>&1 | tail -20
```

Expected: the error count and category should be unchanged from the pre-Task-3 baseline. The known-acceptable errors (per supplementary spec § Heads-up on pre-existing issues / parent doc § Heads-up on pre-existing issues) are: 1 type error in `astro.config.mjs:32` (Tailwind/Vite mismatch) + 9 warnings/hints. **If a new error appears**, it points to a typo in the schema additions — fix before committing.

- [ ] **Step 8: Commit**

```bash
git add apps/site/src/content.config.ts
git -c commit.gpgsign=false commit -m "feat(schema): wire thinker_mentions into 5 content collections"
```

---

### Task 4: Capture the baseline `astro check` error count

**Files:** none modified — this is a verification + documentation step.

This number is the delta target for every subsequent task: no Phase B change should add a new error.

- [ ] **Step 1: Run astro check and capture the summary line**

```bash
cd apps/site && npx --offline astro check 2>&1 | grep -E "^Result\b|errors?\b|warnings?\b|hints?\b" | tail -5
```

Expected: one summary block reporting N errors / M warnings / K hints. Per the parent doc § Heads-up, this should be `1 error, 9 warnings, ...` or close — `astro.config.mjs:32` Tailwind/Vite mismatch + Search.astro nullability + ThinkerCard unused import + `/pagefind/pagefind.js` typing.

- [ ] **Step 2: Verify `npm run build` succeeds**

```bash
cd apps/site && npm run build 2>&1 | tail -10
```

Expected: build completes, reports `1,225+ pages` generated, exit code 0. This is the load-bearing verification — `astro check` is type-only and tolerates these errors; the real build must succeed.

- [ ] **Step 3: Record the baseline in the plan execution log**

After running, append the captured numbers (error/warning/hint counts) into the chunk-completion checklist below. No file commit — this is run-time tracking only.

**Chunk 1 completion checklist:**

- [ ] `astro check` baseline recorded: ___ errors / ___ warnings / ___ hints
- [ ] `npm run build` succeeds, ___ pages generated
- [ ] All 5 Tasks 1-3 commits land cleanly on the branch (verify via `git log --oneline -5`)

---

## Chunk 2: Prompt and batch-input preparation

This chunk produces the two artifacts the resolver needs: the system prompt (`system-ner.txt`) and the input JSONL (`ner-input.jsonl`). After this chunk lands, the inputs to `claude -p` exist but no LLM calls have been made yet.

### Task 5: Write the canonical Phase B system prompt

**Files:**
- Create: `scripts/synthesis/prompts/system-ner.txt`
- Modify: `scripts/synthesis/prompts/README.md` (add Phase B paths)

**Per parent doc § The prompt design and supplementary spec §4.** Mirror `system-resolver.txt`'s shape and tone. The new constraint is the verbatim-substring rule — anchor it with real worked examples from real entries.

- [ ] **Step 1: Read the Phase A prompt for shape**

Re-read `scripts/synthesis/prompts/system-resolver.txt` end-to-end. Note the structure: role intro → task → output format → rules → authority list reference → examples. Phase B mirrors this structure exactly.

- [ ] **Step 2: Read the source passages for the three worked examples**

Read the body text of these three entries (skip frontmatter — start after the closing `---`):
- `apps/site/src/content/opinions/anandibai-joshee.md` — pick a 2-line passage from the opening that names her. For the `subject` example, also draft a 1-line `what_it_shows` framing for each chosen passage (e.g., "establishes her as the first Indian woman to qualify in Western medicine"). The framing strings live alongside the verbatim quotes in the gold JSON output.
- `apps/site/src/content/musings/economic-reforms-in-india.md` — the paragraph starting "I am deeply honoured to have been invited to deliver this A. D. Shroff Memorial Lecture"
- `apps/site/src/content/musings/1991-liberal-reforms-why-no-one-celebrated-them-ashok-desai-1995.md` — search the body for Manmohan Singh, Narasimha Rao, or A. D. Shroff; copy a ≤2-line passage that names one of them; the corresponding authority slug is what goes into `thinker_id` of the gold JSON.

For each, copy the chosen passage verbatim into your scratch buffer. **No editorial elisions** (`[...]`, `...`) in the copied text — the quotes you embed in the prompt examples MUST be contiguous substrings of the actual body markdown. If a passage you want is split by an aside, pick a shorter contiguous span instead.

- [ ] **Step 3: Create `scripts/synthesis/prompts/system-ner.txt`**

Write the prompt following this structure:

```
You are the in-prose mention extractor for the Indian Liberals digital
archive (indianliberals.in). For each input entry, identify every
authority-listed thinker who is invoked, quoted, profiled, or referenced
inside the entry's body — and emit one JSON line per (entry, thinker)
pair with the LLM's reasoning and verbatim evidence quotes.

This is the Phase B in-prose NER pass. Phase A already captured the
author + subject of each entry; do NOT re-emit author or subject roles
that Phase A would have caught (the byline-author of the entry is in
the entry's `author` or `authors[]` frontmatter and is excluded from
this pass).

TASK
====

For each input entry, walk the body markdown. For every authority-listed
thinker who actually appears in the body, emit ONE JSON line. Skip
thinkers who don't structurally appear — no speculation, no "this is
the kind of essay where X would be relevant."

ROLES
=====

- "author"  — the entry was authored by this thinker. Rarely populated
              here; Phase A handled byline detection. Only emit if the
              author is also discussed in the body as a subject of
              their own piece (unusual case).
- "subject" — the entry is primarily ABOUT this thinker (profile pieces,
              obituaries, "X: a misunderstood legacy"). The title
              typically names them. For this role, emit 2-4 `key_passages`
              with `what_it_shows` framing — curated highlights from the
              body. Do NOT populate `evidence` for subject role.
- "mention" — the thinker is invoked / quoted / cited / referenced
              inside an entry whose primary subject is something else.
              For this role, emit 1-3 `evidence` records with verbatim
              quotes. Do NOT populate `key_passages` for mention role.

VERBATIM SUBSTRING RULE
=======================

Every quote in `evidence[].quote` and `key_passages[].quote` MUST be a
verbatim substring of the entry's body markdown.

When choosing a quote, match it against the visible text — strip
markdown emphasis (`*`, `_`, backticks, `>`) and normalise smart quotes
to straight quotes mentally before deciding whether your candidate
quote will substring-match. The apply step does the same normalisation
when validating; quotes that don't substring-match are dropped silently.

Quote the SMALLEST verbatim span that captures the point — typically
one sentence, occasionally two. Never quote a whole paragraph. Never
paraphrase. If you can't find a verbatim quote that proves the
mention, omit the mention entirely.

OUTPUT FORMAT
=============

For each (entry, thinker) pair where the thinker appears, emit EXACTLY
ONE JSON object on a single line. No prose, no markdown fences, no
commentary — just the JSON line.

Required fields per record:

  entry_id    : string. Echo the input id verbatim.
  collection  : string. Echo the input collection verbatim.
  thinker_id  : string. MUST be a slug from the AUTHORITY list provided
                in the user message. Do not invent slugs.
  role        : "subject" | "mention" | "author" (rare)
  reasoning   : string. 1-2 sentences explaining what this thinker
                contributes to the entry. Rendered publicly on the
                thinker's bio page.

If role == "subject":
  key_passages : array of 2-4 objects, each with:
                   quote : string. Verbatim substring of the body.
                   what_it_shows : string. 1-line framing of the passage.
  evidence    : OMIT (empty default).

If role == "mention" or "author":
  evidence    : array of 1-3 objects, each with:
                  quote   : string. Verbatim substring of the body.
                  context : string (optional). One-line framing of where
                            in the argument this quote sits.
  key_passages : OMIT (empty default).

RULES
=====

1. Only emit thinker_ids that appear in the authority list. If a person
   appears in the body but is NOT in the authority list, skip them
   entirely. Do not invent slugs. Do not invent thinkers.

2. Skip the entry's own author (the byline thinker). Phase A captured
   that via `author` / `authors[]` / `contributors[]`. This pass is
   about IN-PROSE mentions, not bylines.

3. Skip thinkers whose presence is purely thematic. If the body says
   "free-market economics" and Adam Smith is in the authority list,
   that is NOT a mention of Adam Smith unless his name actually appears
   in the body. Be strict: structural evidence only.

4. For an entry that is a PROFILE PIECE of one thinker (subject role),
   pick the most striking 2-4 passages — not the first 2-4. The
   `key_passages` block becomes the "highlight reel" on the bio page.

5. For mention-role entries, ordering of evidence records is by order
   of appearance in the body (so the bio page shows them in narrative
   order).

6. NEVER hallucinate quotes. If a quote you want to emit isn't an exact
   substring of the body, either find a different verbatim quote that
   captures the same idea, or omit the mention.

7. Multiple-author works (primary-works with `essays_summarized`) get
   ONE record per (work, thinker) pair across the whole summary; do not
   try to attribute quotes to specific essays at this stage.

AUTHORITY LIST
==============

The user message includes a section "## Authority" listing every
currently-known thinker as "<slug>  ::  <Canonical Name>". Match
against this list verbatim. Slugs not in this list cannot be emitted.

WORKED EXAMPLES
===============

Example 1 — subject role (a profile-piece opinion):

Input entry:
  collection: opinions
  id: anandibai-joshee
  title: Anandibai Joshee: First Indian Woman Doctor
  body (excerpt): "[PASTE THE 2-LINE PASSAGE FROM anandibai-joshee.md HERE]"

Authority includes: anandibai-joshee :: Anandibai Joshee

Output (one line):
{"entry_id":"anandibai-joshee","collection":"opinions","thinker_id":"anandibai-joshee","role":"subject","reasoning":"The piece is a full-length profile of Joshee, framing her as the first Indian woman doctor and tracing her formation against the social constraints of the late 19th century.","key_passages":[{"quote":"[VERBATIM SUBSTRING FROM THE PASSAGE]","what_it_shows":"[FRAMING]"},{"quote":"[ANOTHER VERBATIM SUBSTRING]","what_it_shows":"[FRAMING]"}]}


Example 2 — mention role (a body mention inside a thematic musing):

Input entry:
  collection: musings
  id: economic-reforms-in-india
  title: Economic Reforms In India: Where Are We And Where Do We Go?
  body (excerpt): "I am deeply honoured to have been invited to deliver this A. D. Shroff Memorial Lecture. [...] He was among the eight authors of the Bombay Plan and an unofficial delegate at the Bretton Woods Conference [...]"

Authority includes: a-d-shroff :: A. D. Shroff

Output (one line):
{"entry_id":"economic-reforms-in-india","collection":"musings","thinker_id":"a-d-shroff","role":"mention","reasoning":"The author opens by framing the lecture as a Shroff Memorial address and credits Shroff with foundational work on the Bombay Plan and Bretton Woods.","evidence":[{"quote":"I am deeply honoured to have been invited to deliver this A. D. Shroff Memorial Lecture.","context":"opening of the lecture; positions Shroff as the namesake-anchor of the entire address"},{"quote":"He was among the eight authors of the Bombay Plan and an unofficial delegate at the Bretton Woods Conference","context":"biographical aside establishing Shroff's institutional weight"}]}


Example 3 — author with in-prose mentions (author lives in Phase A; only mentions here):

Input entry:
  collection: musings
  id: 1991-liberal-reforms-why-no-one-celebrated-them-ashok-desai-1995
  title: 1991 Liberal Reforms: Why No One Celebrated Them
  author: ashok-desai          (from Phase A — DO NOT re-emit)
  body (excerpt): "[PASTE A PASSAGE FROM THE BODY THAT MENTIONS ANOTHER AUTHORITY THINKER — IDEALLY Manmohan Singh, Narasimha Rao, or A. D. Shroff]"

Authority includes: manmohan-singh :: Manmohan Singh    (and similar)

Output (one line per OTHER thinker mentioned — Desai is omitted):
{"entry_id":"1991-liberal-reforms-why-no-one-celebrated-them-ashok-desai-1995","collection":"musings","thinker_id":"[OTHER-SLUG]","role":"mention","reasoning":"[1-2 SENTENCES]","evidence":[{"quote":"[VERBATIM SUBSTRING]","context":"[FRAMING]"}]}
```

**Replace every `[PASTE …]`, `[VERBATIM SUBSTRING …]`, `[FRAMING]`, and `[OTHER-SLUG]` placeholder with the real passages you copied in Step 2.** The prompt is shipped with those concrete examples — they are the anchors.

- [ ] **Step 4: Update `scripts/synthesis/prompts/README.md` with Phase B paths**

Append a new section at the end:

```markdown
## Phase B (in-prose NER) prompts

- `system-ner.txt` — system message for the Phase B in-prose mention
  extractor. Same dual-path (manual + headless) as the resolver. Read
  by `scripts/synthesis/resolve-ner.py` and by humans who paste it into
  an interactive Claude session.

To re-run via the automated path:

    python3 scripts/synthesis/prepare-ner-batches.py
    python3 scripts/synthesis/resolve-ner.py \
        --batch-size 8 --concurrency 2
    python3 scripts/synthesis/apply-ner.py

Phase B is independent of Phase A — Phase B reads structured refs
written by Phase A (to skip the byline-author) but otherwise the two
pipelines don't share state.
```

- [ ] **Step 5: Eyeball-check the prompt for the verbatim rule**

Re-open `system-ner.txt`. Confirm that:
- The three example entries you embedded are real entries that exist on disk
- Every `quote` field in the example outputs is a literal substring of the example body passages
- No placeholder `[…]` markers remain
- Token estimate: copy the file, paste into Claude's count-tokens tool OR estimate at ~3.7 chars/token. Target ≤ 5K tokens.

- [ ] **Step 6: Commit**

```bash
git add scripts/synthesis/prompts/system-ner.txt scripts/synthesis/prompts/README.md
git -c commit.gpgsign=false commit -m "feat(prompt): Phase B system-ner.txt with real-excerpt worked examples"
```

---

### Task 6: Write `prepare-ner-batches.py`

**Files:**
- Create: `scripts/synthesis/prepare-ner-batches.py`

**Per supplementary spec §6 (the operational filter for primary-works) and parent doc § Apply step specifics.** Emits `data/synthesis/ner-input.jsonl` — one JSON object per English entry in the 4 in-scope collections.

- [ ] **Step 1: Create the script with shebang, docstring, and constants**

Create `scripts/synthesis/prepare-ner-batches.py`:

```python
#!/usr/bin/env python3
"""
Emit data/synthesis/ner-input.jsonl — one entry per line for the
Phase B in-prose NER pass. Reads English entries from the four
in-scope collections (musings, opinions, theprint-mirror,
primary-works) and writes id + collection + title + body for each.

Filters applied:
  - language == "en" (the authority is English-name-keyed; non-English
    bodies don't resolve cleanly)
  - primary-works only: body has ≥200 chars of prose (excluding
    frontmatter and the structured key_points list). Per supplementary
    spec §6, this is the operational definition of "non-trivial summary".
  - primary-works only: needs_extraction != true

Run from repo root:
    python3 scripts/synthesis/prepare-ner-batches.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
OUT = ROOT / "data/synthesis/ner-input.jsonl"

IN_SCOPE = ("musings", "opinions", "theprint-mirror", "primary-works")
MIN_BODY_CHARS = 200
```

- [ ] **Step 2: Add the frontmatter parser**

The existing project parses YAML frontmatter via simple regex (see `apply-resolutions.py`'s pattern). Add this helper:

```python
def split_frontmatter(text: str) -> tuple[dict, str, str]:
    """Return (frontmatter_dict, frontmatter_text, body) for an MD file.

    The dict is a SHALLOW parse — only flat top-level string/bool/null
    keys. Nested keys (e.g., primary-works' `publication.language:`) are
    NOT recovered into the dict; callers that need nested values should
    grep the `frontmatter_text` field directly with a targeted regex.
    Two-pass design avoids reimplementing a full YAML parser."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, "", text
    fm_text, body = m.group(1), m.group(2)
    fm: dict = {}
    for line in fm_text.splitlines():
        # Skip indented lines (they belong to nested blocks)
        if line.startswith((" ", "\t")):
            continue
        km = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$", line)
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        if val == "true":
            fm[key] = True
        elif val == "false":
            fm[key] = False
        elif val in ("null", ""):
            fm[key] = None
        else:
            fm[key] = val
    return fm, fm_text, body


_NESTED_PUBLICATION_LANG_RX = re.compile(
    r"^publication:\s*\n(?:[ \t]+\w+:.*\n)*?[ \t]+language:\s*[\"']?([a-z]{2})[\"']?",
    re.M,
)


def language_for_entry(collection: str, fm_dict: dict, fm_text: str) -> str:
    """Return the language code for an entry. Primary-works store the
    language under `publication.language`; everything else uses the
    top-level `language:` field. Default 'en' if absent."""
    if collection == "primary-works":
        m = _NESTED_PUBLICATION_LANG_RX.search(fm_text)
        if m:
            return m.group(1)
        return "en"
    return fm_dict.get("language") or "en"
```

- [ ] **Step 3: Add the primary-works body filter**

```python
def primary_work_body_qualifies(body: str) -> bool:
    """For primary-works, the rendered body holds the AI-generated summary
    + a structured Key points block. We want NER to read the summary prose
    only — not the bullet list. Strip the '## Key points' section and
    trailing AI-provenance footer, then check we have ≥MIN_BODY_CHARS of
    prose."""
    # Strip the Key points list (everything from '## Key points' onwards)
    stripped = re.split(r"\n##\s+Key\s+points\b", body, maxsplit=1, flags=re.I)[0]
    # Strip the trailing 'Generated by the v1.5 extraction pipeline' footer
    stripped = re.split(r"\n\*Generated by", stripped, maxsplit=1)[0]
    # Collapse whitespace and count visible chars (drop markdown emphasis)
    plain = re.sub(r"[*_`>#]+", "", stripped)
    plain = re.sub(r"\s+", " ", plain).strip()
    return len(plain) >= MIN_BODY_CHARS
```

- [ ] **Step 4: Add the main emit loop**

```python
def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_total = 0
    n_skipped_lang = 0
    n_skipped_thin = 0
    n_skipped_extract = 0
    n_emitted = 0
    with OUT.open("w", encoding="utf-8") as out_f:
        for collection in IN_SCOPE:
            cdir = CONTENT_ROOT / collection
            if not cdir.is_dir():
                print(f"[skip] {collection}: directory missing", file=sys.stderr)
                continue
            for md_path in sorted(cdir.glob("*.md")):
                n_total += 1
                text = md_path.read_text(encoding="utf-8")
                fm, fm_text, body = split_frontmatter(text)
                # Language filter — primary-works keep language nested
                # under publication.language; everything else uses
                # top-level language. Default 'en' if absent.
                lang = language_for_entry(collection, fm, fm_text)
                if lang != "en":
                    n_skipped_lang += 1
                    continue
                # Primary-works extra filters
                if collection == "primary-works":
                    if fm.get("needs_extraction") is True:
                        n_skipped_extract += 1
                        continue
                    if not primary_work_body_qualifies(body):
                        n_skipped_thin += 1
                        continue
                # Title
                title = fm.get("title") or md_path.stem
                # Emit
                rec = {
                    "id": md_path.stem,
                    "collection": collection,
                    "title": title,
                    "body": body.strip(),
                }
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_emitted += 1

    print(json.dumps({
        "total_scanned": n_total,
        "emitted": n_emitted,
        "skipped_non_english": n_skipped_lang,
        "skipped_needs_extraction": n_skipped_extract,
        "skipped_thin_summary": n_skipped_thin,
        "output_path": str(OUT.relative_to(ROOT)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run it and verify the counts**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/prepare-ner-batches.py
```

Expected output: JSON summary. The `emitted` count should be roughly:
- musings ~220 (English filter drops a handful — Sharad Joshi Marathi musings)
- opinions ~61
- theprint-mirror ~48
- primary-works ~200-240 (filtered by needs_extraction + thin-summary gate + nested language)

Total emitted ≈ 530-590. If `emitted` is dramatically lower than expected, inspect a few skipped entries to confirm the filter is correct (especially the nested-language lookup for primary-works).

Verify the output file exists and the first 3 lines look sane:

```bash
head -3 data/synthesis/ner-input.jsonl | python3 -c "import json, sys; [print(json.dumps({**json.loads(l), 'body': json.loads(l)['body'][:80] + '...'})) for l in sys.stdin]"
```

Expected: 3 JSON lines, each with `id`, `collection`, `title`, and a `body` field. The truncated body should be the actual entry text (not boilerplate).

- [ ] **Step 6: Add `data/synthesis/ner-input.jsonl` to gitignore**

`ner-input.jsonl` is a derived artifact (regenerated from content on demand) and must not be committed. Check `.gitignore`:

```bash
grep -n "data/synthesis" .gitignore 2>/dev/null && echo "---" && git ls-files data/synthesis/ 2>/dev/null
```

If there is no existing `data/synthesis/*` glob pattern in `.gitignore` (and `unlinked.jsonl` / `resolutions.jsonl` show up as tracked files in `git ls-files`), add a new explicit line to `.gitignore`:

```
data/synthesis/ner-input.jsonl
data/synthesis/ner-mentions.jsonl
data/synthesis/ner-rejected.txt
data/synthesis/ner-smoke-input.jsonl
```

These four files are all Phase B derived artifacts. The other Phase A artifacts (`unlinked.jsonl`, `resolutions.jsonl`) were committed in Phase A for archival; Phase B's outputs are regenerable and not worth committing.

- [ ] **Step 7: Commit**

```bash
git add scripts/synthesis/prepare-ner-batches.py .gitignore
git -c commit.gpgsign=false commit -m "feat(synth): prepare-ner-batches.py emits Phase B input JSONL"
```

---

**Chunk 2 completion checklist:**
- [ ] `system-ner.txt` created with three real-excerpt worked examples; no `[…]` placeholders remain
- [ ] `README.md` updated with Phase B paths
- [ ] `prepare-ner-batches.py` runs cleanly and emits `data/synthesis/ner-input.jsonl`
- [ ] Emit count is plausible (530-590 range)
- [ ] Three Tasks 5-6 commits land cleanly

---

## Chunk 3: Pipeline driver + applier + smoke batch

This chunk produces the two scripts that move data through the `claude -p` lane and validates them with the locked 7-entry smoke batch. After this chunk lands, Phase B has been proven on real data and the prompt is locked.

### Task 7: Write `resolve-ner.py` (the headless driver)

**Files:**
- Create: `scripts/synthesis/resolve-ner.py`

**Per parent doc § Architecture and supplementary spec §7 step 7.** This is a near-mirror of `resolve-unlinked.py`. The differences:
- Reads `data/synthesis/ner-input.jsonl` (not `unlinked.jsonl`)
- Writes `data/synthesis/ner-mentions.jsonl` (not `resolutions.jsonl`)
- Loads the prompt from `system-ner.txt` (not `system-resolver.txt`)
- Default batch size 8 (not 40) — entries are heavier (full bodies)
- The output line shape is different (a JSONL of mentions, not a JSONL of resolutions) — but the resume logic still keys off `entry_id`, with the additional caveat that one entry may produce multiple JSONL lines (one per thinker mentioned). So the resume key is `(entry_id seen in any prior line)`.

- [ ] **Step 1: Copy `resolve-unlinked.py` as the starting point**

```bash
cp scripts/synthesis/resolve-unlinked.py scripts/synthesis/resolve-ner.py
```

- [ ] **Step 2: Apply the path changes**

Edit `scripts/synthesis/resolve-ner.py`. Update the top constants block:

```python
ROOT = Path(__file__).resolve().parents[2]
NER_INPUT = ROOT / "data/synthesis/ner-input.jsonl"
NER_MENTIONS = ROOT / "data/synthesis/ner-mentions.jsonl"
AUTHORITY = ROOT / "data/authority/thinkers.json"
SYSTEM_PROMPT = ROOT / "scripts/synthesis/prompts/system-ner.txt"
```

Replace every reference to `UNLINKED` with `NER_INPUT` and every reference to `RESOLUTIONS` with `NER_MENTIONS`.

- [ ] **Step 3: Update the docstring**

Replace the existing module docstring with:

```python
"""
Headless `claude -p` driver for the Phase B in-prose NER pass.

Reads `data/synthesis/ner-input.jsonl` (produced by `prepare-ner-batches.py`)
and the cleaned `data/authority/thinkers.json`, chunks the entries into
batches, and dispatches each batch through `claude -p` with the prompt
from `scripts/synthesis/prompts/system-ner.txt`.

Appends one JSON mention record per line to `data/synthesis/ner-mentions.jsonl`.
One entry may produce zero, one, or many lines (one per authority-listed
thinker who appears in the body).

Idempotent: entries already resolved (any prior line for that entry_id)
are skipped on re-run. Restart-safe after a rate-limit pause.

Mirror of `resolve-unlinked.py`. See that file for the chat-vs-headless
dual-path design rationale.

Run from repo root:

    python3 scripts/synthesis/resolve-ner.py \
        --batch-size 8 \
        --concurrency 2 \
        --max-batches 1     # smoke-batch run; remove for full pass

Optional flags:
    --dry-run               # print the prompt + first batch and exit
    --only musings,opinions # restrict to a subset of collections
    --redo                  # force re-resolve everything
"""
```

- [ ] **Step 4: Adjust the default batch size AND add file-override flags**

In `main()`, find:
```python
ap.add_argument("--batch-size", type=int, default=40)
```
Replace with:
```python
ap.add_argument("--batch-size", type=int, default=8)
ap.add_argument("--input-file", default="", help="Override the default NER_INPUT path (used by smoke-batch runs)")
ap.add_argument("--output-file", default="", help="Override the default NER_MENTIONS path (used by smoke-batch runs)")
```

Then immediately after the `args = ap.parse_args()` line, add:
```python
    input_path = Path(args.input_file).resolve() if args.input_file else NER_INPUT
    output_path = Path(args.output_file).resolve() if args.output_file else NER_MENTIONS
```

Update every subsequent reference to `NER_INPUT` in `main()` to use `input_path`, and every subsequent reference to `NER_MENTIONS` in `main()` (including in the `already_resolved_entry_ids` call) to use `output_path`. Easiest path: update `already_resolved_entry_ids()` to take an explicit path argument:

```python
def already_resolved_entry_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("entry_id"):
                    ids.add(r["entry_id"])
            except json.JSONDecodeError:
                continue
    return ids
```

And the open-for-append in `main()`:
```python
    mode = "w" if args.redo else "a"
    out_f = output_path.open(mode, encoding="utf-8")
```

Verify no remaining bare `NER_INPUT` / `NER_MENTIONS` references in `main()` (the module-level constants stay as defaults; only the runtime code uses `input_path` / `output_path`):
```bash
grep -nE "\b(NER_INPUT|NER_MENTIONS)\b" scripts/synthesis/resolve-ner.py | grep -v "^scripts/synthesis/resolve-ner.py:[0-9]*:\s*\(NER_INPUT\s*=\|NER_MENTIONS\s*=\|input_path =\|output_path =\)"
```
Expected: no output (every other use is in main() and references `input_path` / `output_path`).

- [ ] **Step 5: (Resume logic now folded into Step 4 — confirm the rename)**

Step 4 above renamed `already_resolved_ids()` → `already_resolved_entry_ids(path)`. Verify the rename is complete and the call site in `main()` was updated:

```bash
grep -nE "already_resolved_(ids|entry_ids)" scripts/synthesis/resolve-ner.py
```

Expected: two hits — one `def` and one call site, both using `already_resolved_entry_ids(output_path)`.

- [ ] **Step 6: Adjust the `--only` filter for the new entry shape**

The Phase A entries are `{id, collection, byline_hint, ...}`. Phase B entries are `{id, collection, title, body}`. The `--only` filter checks `e["collection"]` — that works unchanged. No edit needed for the filter, but verify by reading the affected lines of the copied file.

- [ ] **Step 7: Update the user-message builder**

In `resolve-unlinked.py`, `build_user_message(batch, authority_listing)` formats the entries as JSON lines under "## Entries to resolve". Phase B uses the SAME structure but the section header is "## Entries to scan". Update:

```python
def build_user_message(batch: list[dict], authority_listing: str) -> str:
    lines = ["## Authority", "", authority_listing, "", "## Entries to scan", ""]
    for rec in batch:
        lines.append(json.dumps(rec, ensure_ascii=False))
    lines.append("")
    lines.append(
        "For each entry above, emit one JSON object per (entry, thinker) "
        "pair where the thinker appears in the body. Multiple lines per "
        "entry are allowed. Entries with no authority-listed thinkers "
        "should produce zero lines. No prose, no fences — JSON only."
    )
    return "\n".join(lines)
```

- [ ] **Step 8: Smoke-test with `--dry-run`**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/resolve-ner.py --dry-run | head -80
```

Expected: the system prompt prints (first 1500 chars), then the user message for batch 1 prints with the authority list and 3 sample entries. Confirm the structure is right — no JSON parse errors, the authority list is well-formed.

- [ ] **Step 9: Commit**

```bash
git add scripts/synthesis/resolve-ner.py
git -c commit.gpgsign=false commit -m "feat(synth): resolve-ner.py — Phase B claude -p driver"
```

---

### Task 8: Write the verbatim-substring validator with unit tests

**Files:**
- Create: `scripts/synthesis/apply-ner.py` (initial — just the validator + its tests)

**Per parent doc § Verbatim substring check and supplementary spec §6.** This is the only piece of Phase B with traditional unit tests — it's a pure function (body + quote → bool) and its correctness is load-bearing for the whole bio-page experience.

Tests run via the established project pattern: assertion-style `if __name__ == "__main__"` test block, exit 0 on pass, 1 on fail. Same shape as `scripts/llm-extract/test_transliteration.py`.

- [ ] **Step 1: Create the skeleton of `apply-ner.py` with the validator**

```python
#!/usr/bin/env python3
"""
Apply data/synthesis/ner-mentions.jsonl to live entry frontmatter.

For each entry that has mention records, validate every quote substring-
matches the body under normalisation rules, drop validation failures to
data/synthesis/ner-rejected.txt, write thinker_mentions[] + populate
related_thinkers[] in the entry's frontmatter.

Idempotent: re-running replaces thinker_mentions[] atomically per entry.

Run from repo root (after resolve-ner.py emits ner-mentions.jsonl):

    python3 scripts/synthesis/apply-ner.py
    python3 scripts/synthesis/apply-ner.py --test    # run the validator's
                                                       built-in unit tests
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
NER_MENTIONS = ROOT / "data/synthesis/ner-mentions.jsonl"
REJECTED_LOG = ROOT / "data/synthesis/ner-rejected.txt"
AUTHORITY = ROOT / "data/authority/thinkers.json"


# ─── Verbatim-substring validator ──────────────────────────────────────

_MARKDOWN_NOISE_RX = re.compile(r"[*_`>~]")
_SMART_QUOTES = {
    "“": '"', "”": '"',   # curly double quotes → straight
    "‘": "'", "’": "'",   # curly single quotes → straight
    "–": "-", "—": "-",   # en/em dashes → hyphen
}


def _normalise(text: str) -> str:
    """Normalise body or candidate quote for substring matching.

    Steps (in order):
      1. Replace smart quotes / dashes with their straight ASCII equivalents.
      2. Remove markdown emphasis markers (*, _, backtick, >, ~).
      3. Collapse all whitespace runs to a single space.
      4. Strip leading and trailing whitespace.

    Case is preserved. Trailing punctuation on the candidate quote is
    handled in `quote_substring_matches`, not here."""
    for src, dst in _SMART_QUOTES.items():
        text = text.replace(src, dst)
    text = _MARKDOWN_NOISE_RX.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def quote_substring_matches(body: str, quote: str) -> bool:
    """Return True if `quote` appears (case-sensitive) as a substring of
    `body` under our normalisation rules.

    The LLM is allowed minor formatting drift versus the body: smart-quote
    vs straight-quote, markdown emphasis around words, whitespace
    variation, and trailing punctuation. Anything beyond that — different
    words, paraphrase, hallucination — fails."""
    if not quote or not body:
        return False
    norm_body = _normalise(body)
    norm_quote = _normalise(quote)
    # Allow the candidate quote to drop a final period/comma/semicolon/colon
    # that is present in the body but not in the LLM's output.
    norm_quote = norm_quote.rstrip(".,;:")
    if not norm_quote:
        return False
    return norm_quote in norm_body


# ─── Built-in tests ────────────────────────────────────────────────────

def _run_tests() -> int:
    """Plain-Python assertion-style tests. Exits 0 on pass, 1 on fail."""
    cases = [
        # (label, body, quote, expected)
        ("exact match", "Hayek argued for spontaneous order.", "Hayek argued for spontaneous order.", True),
        ("substring", "Hayek argued for spontaneous order in 1944.", "Hayek argued for spontaneous order", True),
        ("markdown emphasis in body", "*Hayek* argued for spontaneous order.", "Hayek argued for spontaneous order", True),
        ("smart quotes in body", "Hayek’s argument was clear: “spontaneous order”.", 'Hayek\'s argument was clear: "spontaneous order"', True),
        ("smart quotes in quote", "Hayek's argument was clear: \"spontaneous order\".", "Hayek’s argument was clear: “spontaneous order”", True),
        ("whitespace variation", "Hayek argued for\n\nspontaneous order.", "Hayek argued for spontaneous order", True),
        ("trailing period drop", "Hayek argued for spontaneous order.", "Hayek argued for spontaneous order.", True),
        ("trailing comma drop", "Hayek, an Austrian economist, argued.", "Hayek, an Austrian economist", True),
        ("paraphrase (must fail)", "Hayek argued for spontaneous order.", "Hayek defended unplanned market coordination.", False),
        ("hallucinated quote (must fail)", "Hayek argued for spontaneous order.", "Hayek opposed all forms of central planning.", False),
        ("empty quote (must fail)", "Hayek argued for spontaneous order.", "", False),
        ("empty body (must fail)", "", "Hayek argued for spontaneous order.", False),
        ("case-sensitive (must fail)", "Hayek argued for spontaneous order.", "hayek argued for spontaneous order", False),
        ("markdown link", "See [Hayek's Road to Serfdom](https://example.com) for more.", "Road to Serfdom", True),
        ("blockquote prefix", "> Hayek wrote: spontaneous order matters.", "Hayek wrote: spontaneous order matters.", True),
        ("underscore emphasis", "_Hayek_ argued for spontaneous order.", "Hayek argued for spontaneous order", True),
        ("backtick code span", "The term `spontaneous order` is Hayek's.", "The term spontaneous order is Hayek's.", True),
        ("em-dash normalisation", "Hayek—an Austrian economist—argued for spontaneous order.", "Hayek-an Austrian economist-argued for spontaneous order", True),
        ("en-dash normalisation", "Hayek (1899–1992) argued for spontaneous order.", "Hayek (1899-1992) argued for spontaneous order", True),
        ("mixed emphasis + apostrophe", "*Hayek*'s _Road to Serfdom_ is foundational.", "Hayek's Road to Serfdom is foundational", True),
    ]
    failed = 0
    for label, body, quote, expected in cases:
        actual = quote_substring_matches(body, quote)
        status = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            failed += 1
        print(f"[{status}] {label}: expected={expected} got={actual}")
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    return 0 if failed == 0 else 1


# ─── Main (stub for now; full apply logic in Task 9) ───────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Run validator unit tests and exit")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.test:
        return _run_tests()

    print("apply-ner.py full apply logic lands in Task 9", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the validator tests**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/apply-ner.py --test
```

Expected: `20/20 passed`, exit code 0. If any case fails, the normalisation logic needs revision — fix and re-run.

- [ ] **Step 3: Commit**

```bash
git add scripts/synthesis/apply-ner.py
git -c commit.gpgsign=false commit -m "feat(synth): apply-ner.py validator + unit tests (Task 8)"
```

---

### Task 9: Complete `apply-ner.py` with the frontmatter mutator

**Files:**
- Modify: `scripts/synthesis/apply-ner.py` (replace the stub `main` with the full applier)

**Per parent doc § Apply step specifics.** The applier:
1. Reads `ner-mentions.jsonl`, groups by `entry_id`
2. For each entry: validates quotes, looks up the body, drops bad mentions
3. Writes `thinker_mentions[]` block to frontmatter (replacing any existing block atomically)
4. Populates `related_thinkers[]` with the deduped slug list (excluding the entry's own author/subject)
5. Logs rejected mentions to `ner-rejected.txt`

- [ ] **Step 1: Add YAML emit helpers (reuse the pattern from `emit-astro-md.py`)**

Add to `apply-ner.py` above `_run_tests`:

```python
# ─── YAML emit helpers (parallel to scripts/synthesis/emit-astro-md.py) ──

def _yaml_str(s: str) -> str:
    if s is None:
        return '""'
    s = str(s)
    if not s:
        return '""'
    needs_quotes = any(c in s for c in ":#&*!|>'\"%@`{}[]\n\r\t") or (s and s[0] in "-?:") or s.endswith(" ")
    if needs_quotes:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return s


def _yaml_thinker_mentions_block(mentions: list[dict], indent: int = 0) -> str:
    """Emit a YAML block for the thinker_mentions[] array. Each mention
    becomes a list item; nested arrays (evidence, key_passages) emit as
    sub-lists. Returns the block including its leading 'thinker_mentions:'
    key line."""
    pad = " " * indent
    if not mentions:
        return f"{pad}thinker_mentions: []"
    lines = [f"{pad}thinker_mentions:"]
    item_pad = " " * (indent + 2)
    inner_pad = " " * (indent + 4)
    for m in mentions:
        lines.append(f"{item_pad}- thinker: {_yaml_str(m['thinker'])}")
        lines.append(f"{inner_pad}role: {m['role']}")
        lines.append(f"{inner_pad}reasoning: {_yaml_str(m['reasoning'])}")
        evidence = m.get("evidence") or []
        if evidence:
            lines.append(f"{inner_pad}evidence:")
            for ev in evidence:
                lines.append(f"{inner_pad}  - quote: {_yaml_str(ev['quote'])}")
                if ev.get("context"):
                    lines.append(f"{inner_pad}    context: {_yaml_str(ev['context'])}")
        else:
            lines.append(f"{inner_pad}evidence: []")
        key_passages = m.get("key_passages") or []
        if key_passages:
            lines.append(f"{inner_pad}key_passages:")
            for kp in key_passages:
                lines.append(f"{inner_pad}  - quote: {_yaml_str(kp['quote'])}")
                lines.append(f"{inner_pad}    what_it_shows: {_yaml_str(kp['what_it_shows'])}")
        else:
            lines.append(f"{inner_pad}key_passages: []")
    return "\n".join(lines)
```

- [ ] **Step 2: Add the frontmatter splitter and block-replacer**

```python
_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_TM_BLOCK_RX = re.compile(
    r"^thinker_mentions:\s*(?:\[\]|(?:\n[ \t]+.*)+)\n?",
    re.M,
)
_RT_LINE_RX = re.compile(r"^related_thinkers:\s*.*$(?:\n[ \t]+.*)*", re.M)


def _replace_or_append_block(fm: str, key: str, new_block: str) -> str:
    """Replace `<key>:` block in frontmatter with `new_block`. If the key
    isn't present, append new_block to the end of `fm`. `new_block`
    must start with `<key>:`."""
    if key == "thinker_mentions":
        rx = _TM_BLOCK_RX
    elif key == "related_thinkers":
        rx = _RT_LINE_RX
    else:
        raise ValueError(f"unknown frontmatter key: {key}")
    if rx.search(fm):
        return rx.sub(new_block.rstrip() + "\n", fm)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + new_block.rstrip() + "\n"
```

- [ ] **Step 3: Add the body lookup and authority loader**

```python
def load_body(collection: str, entry_id: str) -> str | None:
    p = CONTENT_ROOT / collection / f"{entry_id}.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    return m.group(2)


def load_authority_slugs() -> set[str]:
    doc = json.loads(AUTHORITY.read_text())
    return {t["id"] for t in doc.get("thinkers", [])}


def load_existing_author_slugs(collection: str, entry_id: str) -> set[str]:
    """Return the set of slugs already attached to this entry as author
    or subject (from Phase A). These slugs are excluded from
    related_thinkers[] to avoid the entry cross-referencing its own
    author/subject."""
    p = CONTENT_ROOT / collection / f"{entry_id}.md"
    if not p.exists():
        return set()
    text = p.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return set()
    fm = m.group(1)
    slugs: set[str] = set()
    for field in ("author", "subject"):
        mm = re.search(rf"^{field}:\s*\"([^\"]+)\"", fm, re.M)
        if mm:
            slugs.add(mm.group(1))
    # authors[] (primary-works)
    mm = re.search(r"^authors:\s*\n((?:[ \t]+-\s*\"[^\"]+\"\s*\n)+)", fm, re.M)
    if mm:
        for line in mm.group(1).splitlines():
            sub = re.match(r"\s*-\s*\"([^\"]+)\"", line)
            if sub:
                slugs.add(sub.group(1))
    return slugs
```

- [ ] **Step 4: Add the main apply function (replace the stub `main`)**

Replace the existing `main` function entirely with:

```python
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Run validator unit tests and exit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-entry", default="", help="Restrict apply to a single entry_id (debugging)")
    args = ap.parse_args()

    if args.test:
        return _run_tests()

    if not NER_MENTIONS.exists():
        print(f"ERROR: {NER_MENTIONS} missing — run resolve-ner.py first", file=sys.stderr)
        return 1

    authority = load_authority_slugs()

    # Read mentions, group by entry_id
    by_entry: dict[str, list[dict]] = {}
    for raw in NER_MENTIONS.read_text().splitlines():
        raw = raw.strip()
        if not raw or not raw.startswith("{"):
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        eid = rec.get("entry_id")
        if not eid:
            continue
        if args.only_entry and eid != args.only_entry:
            continue
        by_entry.setdefault(eid, []).append(rec)

    counts = {
        "entries_processed": 0,
        "mentions_written": 0,
        "mentions_rejected_quote": 0,
        "mentions_rejected_thinker": 0,
        "mentions_rejected_self": 0,
        "files_updated": 0,
    }
    rejected_lines: list[str] = []

    for eid, mentions in by_entry.items():
        collection = mentions[0].get("collection")
        if not collection:
            continue
        body = load_body(collection, eid)
        if body is None:
            rejected_lines.append(f"{collection}\t{eid}\tBODY_MISSING")
            continue
        existing_author_slugs = load_existing_author_slugs(collection, eid)

        valid_mentions: list[dict] = []
        for m in mentions:
            slug = m.get("thinker_id")
            if not slug or slug not in authority:
                counts["mentions_rejected_thinker"] += 1
                rejected_lines.append(f"{collection}\t{eid}\tunknown_thinker={slug}")
                continue
            # Skip the entry's own author/subject (Phase A owns those)
            if slug in existing_author_slugs:
                counts["mentions_rejected_self"] += 1
                continue
            # Validate every quote
            evidence = m.get("evidence") or []
            key_passages = m.get("key_passages") or []
            kept_evidence: list[dict] = []
            for ev in evidence:
                q = ev.get("quote", "")
                if quote_substring_matches(body, q):
                    kept_evidence.append({"quote": q, **({"context": ev["context"]} if ev.get("context") else {})})
                else:
                    counts["mentions_rejected_quote"] += 1
                    rejected_lines.append(f"{collection}\t{eid}\t{slug}\tevidence_quote_no_substring\t{q[:80]}")
            kept_key_passages: list[dict] = []
            for kp in key_passages:
                q = kp.get("quote", "")
                if quote_substring_matches(body, q):
                    kept_key_passages.append({"quote": q, "what_it_shows": kp.get("what_it_shows", "")})
                else:
                    counts["mentions_rejected_quote"] += 1
                    rejected_lines.append(f"{collection}\t{eid}\t{slug}\tkey_passage_quote_no_substring\t{q[:80]}")
            # If a role expects evidence/key_passages and BOTH lists are empty after validation, drop the mention
            role = m.get("role", "mention")
            if role == "subject" and not kept_key_passages:
                continue
            if role in ("mention", "author") and not kept_evidence:
                continue
            valid_mentions.append({
                "thinker": slug,
                "role": role,
                "reasoning": m.get("reasoning", ""),
                "evidence": kept_evidence,
                "key_passages": kept_key_passages,
            })

        # related_thinkers = de-duped union of (kept mentions' thinkers) minus the entry's own author/subject
        related_slugs = sorted({m["thinker"] for m in valid_mentions} - existing_author_slugs)

        # Render the frontmatter blocks
        tm_block = _yaml_thinker_mentions_block(valid_mentions, indent=0)
        rt_block = "related_thinkers: " + (
            "[]" if not related_slugs else "\n" + "\n".join(f"  - {_yaml_str(s)}" for s in related_slugs)
        )

        # Apply to the file
        p = CONTENT_ROOT / collection / f"{eid}.md"
        text = p.read_text(encoding="utf-8")
        fm_match = _FRONTMATTER_RX.match(text)
        if not fm_match:
            rejected_lines.append(f"{collection}\t{eid}\tNO_FRONTMATTER")
            continue
        fm = fm_match.group(1)
        body_part = fm_match.group(2)
        fm = _replace_or_append_block(fm, "thinker_mentions", tm_block)
        fm = _replace_or_append_block(fm, "related_thinkers", rt_block)
        new_text = f"---\n{fm}\n---\n{body_part}"
        if not args.dry_run:
            p.write_text(new_text, encoding="utf-8")
        counts["files_updated"] += 1
        counts["entries_processed"] += 1
        counts["mentions_written"] += len(valid_mentions)

    if rejected_lines and not args.dry_run:
        REJECTED_LOG.write_text("\n".join(rejected_lines) + "\n", encoding="utf-8")
        counts["rejected_log"] = str(REJECTED_LOG.relative_to(ROOT))

    print(json.dumps(counts, indent=2))
    return 0
```

- [ ] **Step 5: Re-run the validator tests to confirm no regression**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-ner.py --test
```

Expected: `20/20 passed`, exit code 0.

- [ ] **Step 6: Run apply in `--dry-run` mode against an empty mentions file (if it exists)**

```bash
test -f data/synthesis/ner-mentions.jsonl && \
  .venv-extract/bin/python3 scripts/synthesis/apply-ner.py --dry-run || \
  echo "no mentions file yet — expected at this stage"
```

Expected: either prints the counts JSON (if the file exists from a smoke run) or prints "no mentions file yet". No traceback.

- [ ] **Step 7: Commit**

```bash
git add scripts/synthesis/apply-ner.py
git -c commit.gpgsign=false commit -m "feat(synth): apply-ner.py full applier with frontmatter mutation"
```

---

### Task 10: Run the smoke batch and iterate the prompt

**Files:** none modified in this task — Task 10 is a runtime + prompt-iteration cycle. The `system-ner.txt` prompt MAY be modified during this task; any changes are committed at the end of the cycle.

**Per supplementary spec §3 and §4.** Run resolve-ner.py on the 7 smoke-batch entries, read the JSON output by hand, show Adnan, iterate prompt until the 4 non-example entries (#2, #3, #6, #7) produce sensible verbatim-correct mentions. The 3 example entries (#1, #4, #5) should produce ~exact gold-standard outputs since they anchor the prompt; if they DON'T, the prompt has a bug.

- [ ] **Step 1 (pre-flight): Verify all 7 smoke slugs exist in `ner-input.jsonl`**

A silent partial-batch (e.g., 6 of 7 entries because one was filtered) burns `claude -p` budget without exercising the full code path. Hard-fail if any slug is missing:

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 -c "
import json, sys
SMOKE = [
    'anandibai-joshee',
    'homi-modys-liberalism-pro-business-to-pro-market',
    'gg-agarkar-revisiting-a-misunderstood-legacy',
    'economic-reforms-in-india',
    '1991-liberal-reforms-why-no-one-celebrated-them-ashok-desai-1995',
    'ad-shroff-socialism-free-enterprise-lessons',
    'a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980',
]
ids = set()
with open('data/synthesis/ner-input.jsonl') as f:
    for line in f:
        ids.add(json.loads(line)['id'])
missing = [s for s in SMOKE if s not in ids]
if missing:
    print(f'smoke slugs missing from ner-input.jsonl: {missing}', file=sys.stderr)
    sys.exit(1)
print(f'all 7 smoke slugs present in ner-input.jsonl ({len(ids)} total entries)')
"
```

Expected: `all 7 smoke slugs present in ner-input.jsonl (N total entries)`, exit 0. If any slug is missing, inspect `prepare-ner-batches.py`'s filter against that slug's MD file — most likely cause is the primary-works thin-summary gate or a typo in the smoke list. Fix and re-run Task 6 Step 5.

- [ ] **Step 2: Construct the smoke-batch input file**

```bash
python3 -c "
import json
SMOKE = [
    'anandibai-joshee',
    'homi-modys-liberalism-pro-business-to-pro-market',
    'gg-agarkar-revisiting-a-misunderstood-legacy',
    'economic-reforms-in-india',
    '1991-liberal-reforms-why-no-one-celebrated-them-ashok-desai-1995',
    'ad-shroff-socialism-free-enterprise-lessons',
    'a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980',
]
with open('data/synthesis/ner-input.jsonl') as f, open('data/synthesis/ner-smoke-input.jsonl','w') as out:
    for line in f:
        if json.loads(line)['id'] in SMOKE:
            out.write(line)
"
wc -l data/synthesis/ner-smoke-input.jsonl
```

Expected: `7`.

- [ ] **Step 3: Run the resolver on the smoke batch using the flags from Task 7**

```bash
.venv-extract/bin/python3 scripts/synthesis/resolve-ner.py \
    --input-file data/synthesis/ner-smoke-input.jsonl \
    --output-file data/synthesis/ner-mentions-smoke.jsonl \
    --batch-size 8 --concurrency 1 --max-batches 1 \
    2>&1 | tee /tmp/ner-smoke.log
```

Using a separate `ner-mentions-smoke.jsonl` keeps smoke output OUT of the eventual full-run output file — important because Step 6 may iterate the prompt several times, and we don't want stale smoke outputs polluting `ner-mentions.jsonl` and being skipped via resume-logic during the full Task 11 run.

If `claude -p` is rate-limited, the breaker trips and the script sleeps. Read the breaker output; if it's a long sleep (>30 min), drop into a manual chat session: paste `system-ner.txt` as the system prompt + paste one entry at a time as user messages, collect outputs, append them to `data/synthesis/ner-mentions-smoke.jsonl`.

- [ ] **Step 4: Inspect the smoke output**

```bash
wc -l data/synthesis/ner-mentions-smoke.jsonl
cat data/synthesis/ner-mentions-smoke.jsonl | python3 -m json.tool --no-ensure-ascii | less
```

For each of the 7 entries, verify:
- The 3 `subject`-role opinions each produced 1 record with role=subject and 2-4 key_passages
- The 2 `mention`-rich musings each produced multiple records, all role=mention, with 1-3 evidence quotes each
- The ThePrint piece produced multiple `mention` records
- The Godrej primary-work produced mention records over the SUMMARY prose (Germany/Japan/etc.)
- Every quote in every record appears LITERALLY in the source body (eyeball-check 3-5 random quotes per entry)

Special attention to the 4 *non-example* smoke entries (supplementary spec §4 prompt-example circularity note): #2, #3 (subject-role opinions NOT in the prompt examples), #6 (ThePrint), #7 (primary-work). These four must produce sensible verbatim-correct mentions before the prompt is locked.

- [ ] **Step 5: Run the applier in `--dry-run` against the smoke output**

apply-ner.py reads from the default `NER_MENTIONS` path. For this smoke check, temporarily point it at the smoke output by adding the same `--input-file` flag to apply-ner.py (mirror the pattern from Task 7). Alternatively, just copy: `cp data/synthesis/ner-mentions-smoke.jsonl data/synthesis/ner-mentions.jsonl`, run dry-run, then `rm data/synthesis/ner-mentions.jsonl` before the full run.

Simplest path:
```bash
cp data/synthesis/ner-mentions-smoke.jsonl data/synthesis/ner-mentions.jsonl
.venv-extract/bin/python3 scripts/synthesis/apply-ner.py --dry-run
rm data/synthesis/ner-mentions.jsonl
```

Expected: counts JSON shows `entries_processed: 7`, `mentions_rejected_quote: 0` or low. If `mentions_rejected_quote` is high (≥10% of `mentions_written`), the LLM is emitting non-substring quotes — the prompt's verbatim rule isn't anchoring well enough. Strengthen the prompt's worked examples and re-run from Step 3.

- [ ] **Step 6: Show Adnan the smoke output and the rejection log**

Print the smoke output and the rejection log inline in your response:

```bash
echo "=== smoke output ===" && cat data/synthesis/ner-mentions-smoke.jsonl
echo "=== rejection log (if any) ===" && cat data/synthesis/ner-rejected.txt 2>/dev/null || echo "(no rejections)"
```

Ask: "OK to lock the prompt and run the full batch?" Wait for sign-off.

- [ ] **Step 7: If Adnan asks for prompt edits, iterate**

Edit `scripts/synthesis/prompts/system-ner.txt`. Re-run Step 3-6. Repeat until Adnan signs off. Each iteration overwrites `ner-mentions-smoke.jsonl` (use `--redo` if the resolver's resume logic skips already-resolved entry_ids; deleting the smoke output file first is cleaner).

- [ ] **Step 8: Apply the smoke output to the 7 entry MD files**

```bash
cp data/synthesis/ner-mentions-smoke.jsonl data/synthesis/ner-mentions.jsonl
.venv-extract/bin/python3 scripts/synthesis/apply-ner.py
rm data/synthesis/ner-mentions.jsonl  # keep the full-run output file empty until Task 11
```

Verify a sample frontmatter was updated correctly:

```bash
grep -A 30 "^thinker_mentions:" apps/site/src/content/musings/economic-reforms-in-india.md | head -40
```

Expected: a YAML block with the kept mentions, properly indented, parseable by Astro.

- [ ] **Step 9: Run `npx --offline astro check` to confirm no schema regression**

```bash
cd apps/site && npx --offline astro check 2>&1 | tail -5
```

Expected: same error/warning/hint count as the Task 4 baseline.

- [ ] **Step 10: Commit the prompt iterations and the smoke artifacts**

```bash
cd "/Users/siraj/Indian Liberals Website"

# If the prompt was edited in Step 7, commit it
git add scripts/synthesis/prompts/system-ner.txt
git -c commit.gpgsign=false commit -m "feat(prompt): tune system-ner.txt after smoke-batch sign-off" \
    --allow-empty

# Commit the 7 modified frontmatter files
git add apps/site/src/content/
git -c commit.gpgsign=false commit -m "feat(content): apply Phase B mentions from 7-entry smoke batch"

# Discard the smoke-input artifact (derived; gitignored per Task 6 Step 6)
rm -f data/synthesis/ner-smoke-input.jsonl data/synthesis/ner-mentions-smoke.jsonl
```

---

**Chunk 3 completion checklist:**
- [ ] `resolve-ner.py` smoke-tested via `--dry-run` and a real 7-entry batch
- [ ] `apply-ner.py --test` reports 20/20 passing
- [ ] Adnan has signed off on the smoke output and any prompt edits are locked in
- [ ] 7 entry frontmatter files updated and committed
- [ ] `astro check` delta is still 0

---

## Chunk 4: Full batch + UI + audit

This chunk runs the locked pipeline at scale, surfaces the data on bio pages, and runs the acceptance audit. After this chunk lands, Phase B core is done.

### Task 11: Run the full Phase B batch via `resolve-ner.py`

**Files:** none modified — runtime task. Output goes to `data/synthesis/ner-mentions.jsonl` (appends; entries from the smoke batch are already there and will be skipped via resume logic).

- [ ] **Step 1: Kick off the full run**

If the extraction runner is still alive and competing for the `claude -p` rate-limit pool, that's fine — both pipelines have circuit breakers. Phase B will throttle gracefully.

```bash
cd "/Users/siraj/Indian Liberals Website"
nohup .venv-extract/bin/python3 scripts/synthesis/resolve-ner.py \
    --batch-size 8 --concurrency 2 \
    > /tmp/ner-full-run.log 2>&1 &
echo "started PID $!"
```

- [ ] **Step 2: Monitor**

```bash
tail -f /tmp/ner-full-run.log
```

Expected pattern: `[batch N/M] K mentions` lines as batches complete, occasional `[breaker] TRIPPED` lines on rate-limit hits, then `[breaker] RESUMING` after the reset window. The run takes 4-12 hours of wallclock depending on rate-limit pressure.

If a wakeup is needed mid-run, this is a good place to use `ScheduleWakeup` with `delaySeconds=1200` (20 min) and a reason like "checking Phase B batch progress".

- [ ] **Step 3: Confirm completion**

When the run completes:

```bash
wc -l data/synthesis/ner-mentions.jsonl
tail -1 /tmp/ner-full-run.log
```

Expected: `[done] resolutions written to data/synthesis/ner-mentions.jsonl` in the log. Line count should be in the thousands (every entry can produce multiple lines; expect ~3-5K total).

- [ ] **Step 4: No commit needed at this step — the JSONL is a derived artifact and not committed**

Verify `.gitignore` covers it:

```bash
git status data/synthesis/ner-mentions.jsonl
```

Expected: file is ignored or untracked. Move on.

---

### Task 12: Run `apply-ner.py` against the full mentions file

**Files:** This task mutates frontmatter in 4 content directories (musings, opinions, theprint-mirror, primary-works) — potentially hundreds of files. The commit at the end is a single bulk commit.

- [ ] **Step 1: Dry-run first to check the rejection rate**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-ner.py --dry-run 2>&1 | tee /tmp/ner-apply-dryrun.log
```

Read the counts JSON. Key checks:
- `mentions_rejected_quote` ÷ `mentions_written` should be ≤ 0.05 (≤5%). If higher, the prompt has drifted; inspect a few `ner-rejected.txt` lines and decide whether to re-tune the prompt or accept the rejection rate.
- `mentions_rejected_thinker` should be 0 or very low — the LLM should only emit slugs from the authority list.
- `mentions_rejected_self` is fine; it's a routine drop of byline-authors.

- [ ] **Step 2: Run for real**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-ner.py 2>&1 | tee /tmp/ner-apply.log
```

- [ ] **Step 3: Verify `astro check` still clean**

```bash
cd apps/site && npx --offline astro check 2>&1 | tail -5
```

Expected: same error/warning/hint count as the Task 4 baseline. If a new error appears, it points to a malformed YAML block — find the failing file, inspect the `thinker_mentions:` block, fix the YAML emitter, re-run apply.

- [ ] **Step 4: Verify `npm run build` succeeds**

```bash
cd apps/site && npm run build 2>&1 | tail -10
```

Expected: build completes, ≥1,225 pages generated, exit code 0.

- [ ] **Step 5: Commit the bulk frontmatter mutations**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/content/musings apps/site/src/content/opinions apps/site/src/content/theprint-mirror apps/site/src/content/primary-works
git -c commit.gpgsign=false commit -m "feat(content): apply Phase B thinker_mentions across Tier-A + primary-works"
```

---

### Task 13: Update the thinker bio page

**Files:**
- Modify: `apps/site/src/pages/thinkers/[slug].astro`

**Per parent doc § Bio page changes.** Two new affordances:
1. New section "How {Thinker} is discussed in this archive" between the existing themes/affiliations `<aside>` (line 199) and Section 1 "By {Thinker}" (line 202). Renders 2-3 paragraphs grouped by role with inline work-title links.
2. Inside the existing Section 3 "Mentioned in" subsections (workMentions, opinionMentions, musingMentions render loops, lines 325-369), augment each `<li>` with an inline blockquote rendering the matching evidence quote(s).
3. Inside the existing Section 2 "About {Thinker}" → `opinionsAbout` render loop (lines 300-313), surface 1-2 `key_passages` as a highlight strip under the entry title.

**Read the file once before starting** — see `apps/site/src/pages/thinkers/[slug].astro` (currently 383 lines). The existing aggregation variables we will reuse:

- Author role: `worksByThisThinker`, `musingsByThisThinker`, `opinionsByThisThinker`, `theprintByThisThinker` (lines 44-54)
- Subject role: `interviewsAbout`, `opinionsAbout` (lines 57-58)
- Mention role: `opinionMentions`, `musingMentions`, `workMentions` (lines 61-82)

The file already does `await Promise.all([getCollection('interviews'), getCollection('theprint-mirror'), ...])` at lines 29-35 — Task 13 reuses those arrays, no new `getCollection` calls.

- [ ] **Step 1: Add a helper at the top of the frontmatter script (after line 41, just before the existing aggregations)**

Insert this helper to look up a thinker's mention record from any entry's `thinker_mentions[]`:

```typescript
// Phase B — given any entry and the thinker we're rendering, find the
// matching thinker_mentions[] row (or undefined). Used by every section
// that wants to render evidence/key_passages alongside the entry link.
function mentionFor(entry: { data: { thinker_mentions?: Array<any> } }, id: string) {
  return (entry.data.thinker_mentions ?? []).find((m: any) => refMatches(m.thinker, id));
}
```

- [ ] **Step 2: After the existing aggregations (after line 89, before `const hreflang = ...`), build the "How … discussed" synthesis data**

```typescript
// Phase B — collect every (entry, mention) pair across the three
// mention-bearing role buckets for the synthesis section. Grouped by
// role so we can render role-bucketed prose like the parent spec calls
// for: "Authored N works including X, Y, Z. Referenced in M others
// including A, B, C."
type MentionRow = { entry: { collection: string; id: string; data: any }; mention: any };

const subjectMentions: MentionRow[] = opinionsAbout
  .map((e) => {
    const m = mentionFor(e, t.id);
    return m && m.role === 'subject' ? { entry: e, mention: m } : null;
  })
  .filter((x): x is MentionRow => x !== null);

const allMentionRows: MentionRow[] = [
  ...workMentions.map((e) => ({ entry: e, mention: mentionFor(e, t.id) })),
  ...opinionMentions.map((e) => ({ entry: e, mention: mentionFor(e, t.id) })),
  ...musingMentions.map((e) => ({ entry: e, mention: mentionFor(e, t.id) })),
].filter((r): r is MentionRow => r.mention !== undefined && r.mention.role === 'mention');

const hasPhaseBData = subjectMentions.length > 0 || allMentionRows.length > 0;

// For the inline "...including X, Y, Z" lists — pick up to 3 representative
// works by title, preferring the most-quoted (longest evidence list).
function topByEvidence(rows: MentionRow[], limit = 3): MentionRow[] {
  return [...rows]
    .sort((a, b) => (b.mention.evidence?.length ?? 0) - (a.mention.evidence?.length ?? 0))
    .slice(0, limit);
}
const topMentions = topByEvidence(allMentionRows, 3);
```

- [ ] **Step 3: Render the "How … discussed" section between the themes aside and Section 1**

Find the closing `</aside>` of the themes/affiliations block (currently line 199, immediately before the `{/* ── Section 1: Works BY this thinker ────────── */}` comment). Insert this section AFTER `</aside>` and BEFORE that comment:

```astro
    {/* ── Phase B: How this thinker is discussed in this archive ───── */}
    {hasPhaseBData && (
      <section class="mt-12 pt-8 border-t border-(--color-border) font-(family-name:--font-ui)">
        <h2 class="text-xs uppercase tracking-widest text-(--color-fg-muted) mb-4">
          How {t.data.name.canonical} is discussed in this archive
        </h2>
        <div class="text-(--color-fg) text-base leading-relaxed space-y-3">
          {authorshipCount > 0 && (
            <p>
              Authored {authorshipCount} {authorshipCount === 1 ? "work" : "works"} in the archive.
            </p>
          )}
          {subjectMentions.length > 0 && (
            <p>
              Subject of {subjectMentions.length} profile {subjectMentions.length === 1 ? "piece" : "pieces"}
              {" — including "}
              {subjectMentions.slice(0, 3).map((row, i) => (
                <Fragment>
                  {i > 0 && (i === Math.min(subjectMentions.length, 3) - 1 ? ", and " : ", ")}
                  <a href={`/opinions/${row.entry.id}/`} class="text-(--color-forest-700) no-underline hover:underline">
                    {row.entry.data.title}
                  </a>
                </Fragment>
              ))}
              .
            </p>
          )}
          {allMentionRows.length > 0 && (
            <p>
              Referenced in {allMentionRows.length} other {allMentionRows.length === 1 ? "work" : "works"}
              {topMentions.length > 0 && (
                <Fragment>
                  {" — including "}
                  {topMentions.map((row, i) => (
                    <Fragment>
                      {i > 0 && (i === topMentions.length - 1 ? ", and " : ", ")}
                      <a href={`/${row.entry.collection}/${row.entry.id}/`} class="text-(--color-forest-700) no-underline hover:underline">
                        {row.entry.collection === "primary-works"
                          ? row.entry.data.title.main
                          : row.entry.data.title}
                      </a>
                    </Fragment>
                  ))}
                </Fragment>
              )}
              .
            </p>
          )}
          {allMentionRows.slice(0, 5).map((row) => (
            <p class="text-sm text-(--color-fg-muted) italic pl-3 border-l-2 border-(--color-saffron-200)">
              <span class="not-italic text-(--color-fg)">In <a href={`/${row.entry.collection}/${row.entry.id}/`} class="text-(--color-forest-700) no-underline hover:underline">
                {row.entry.collection === "primary-works" ? row.entry.data.title.main : row.entry.data.title}
              </a>:</span>{" "}
              {(row.mention.reasoning || "").split(/(?<=\.)\s+/)[0]}
            </p>
          ))}
        </div>
      </section>
    )}
```

Note on Astro idioms: `<Fragment>` is the Astro equivalent of React's `<>`. The file already imports component patterns from `astro:content`; `Fragment` is globally available in Astro components (no import needed). The existing file does NOT use `<>` fragments — confirmed by inspection at lines 134-145, 280-316.

- [ ] **Step 4: Augment the three "Mentioned in" subsections with inline evidence quotes**

In `apps/site/src/pages/thinkers/[slug].astro`, the existing Section 3 has three render loops (workMentions at lines 329-341, opinionMentions at 347-356, musingMentions at 361-369). Each renders `<li><a>…</a></li>`. Modify each `<li>` to render the first 1-2 evidence quotes underneath the link.

**For `workMentions.slice(0, 15).map((w) => (...))`** — replace the existing `<li>` with:

```astro
                {workMentions.slice(0, 15).map((w) => {
                  const tm = mentionFor(w, t.id);
                  const quotes = (tm?.evidence ?? []).slice(0, 2);
                  return (
                    <li>
                      <a href={`/primary-works/${w.id}/`} class="text-sm text-(--color-forest-700) no-underline hover:underline">
                        {w.data.title.main}
                        <span class="text-(--color-fg-muted) ml-1">· {w.data.publication?.year ?? "n.d."}</span>
                      </a>
                      {quotes.length > 0 && (
                        <ul class="mt-1 space-y-1 ml-2">
                          {quotes.map((ev: any) => (
                            <li class="text-xs italic text-(--color-fg-muted) pl-2 border-l border-(--color-saffron-200)">
                              "{ev.quote}"
                              {ev.context && <span class="not-italic text-(--color-fg-muted) ml-1">— {ev.context}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
```

**For `opinionMentions.slice(0, 10).map((o) => (...))`** — same pattern, just swap `w.data.title.main` for `o.data.title` and `primary-works` for `opinions`:

```astro
                {opinionMentions.slice(0, 10).map((o) => {
                  const tm = mentionFor(o, t.id);
                  const quotes = (tm?.evidence ?? []).slice(0, 2);
                  return (
                    <li>
                      <a href={`/opinions/${o.id}/`} class="text-sm text-(--color-forest-700) no-underline hover:underline">
                        {o.data.title}
                      </a>
                      {quotes.length > 0 && (
                        <ul class="mt-1 space-y-1 ml-2">
                          {quotes.map((ev: any) => (
                            <li class="text-xs italic text-(--color-fg-muted) pl-2 border-l border-(--color-saffron-200)">
                              "{ev.quote}"
                              {ev.context && <span class="not-italic text-(--color-fg-muted) ml-1">— {ev.context}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
```

**For `musingMentions.slice(0, 10).map((m) => (...))`** — same pattern:

```astro
                {musingMentions.slice(0, 10).map((m) => {
                  const tm = mentionFor(m, t.id);
                  const quotes = (tm?.evidence ?? []).slice(0, 2);
                  return (
                    <li>
                      <a href={`/musings/${m.id}/`} class="text-sm text-(--color-forest-700) no-underline hover:underline">
                        {m.data.title}
                      </a>
                      {quotes.length > 0 && (
                        <ul class="mt-1 space-y-1 ml-2">
                          {quotes.map((ev: any) => (
                            <li class="text-xs italic text-(--color-fg-muted) pl-2 border-l border-(--color-saffron-200)">
                              "{ev.quote}"
                              {ev.context && <span class="not-italic text-(--color-fg-muted) ml-1">— {ev.context}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
```

Also remove the trailing footer paragraph at lines 372-376 (the one that says "In-prose mentions inside opinions, musings, interviews, and ThePrint articles are queued for the Phase B body-NER pass") — it's stale once Phase B lands.

- [ ] **Step 5: Augment the "About {Thinker}" → `opinionsAbout` subsection with subject-role `key_passages`**

In Section 2 (lines 300-313), modify the `opinionsAbout.map((o) => (...))` render to surface 1-2 `key_passages` per subject-role entry. Replace the existing `<li>` block with:

```astro
                {opinionsAbout.map((o) => {
                  const tm = mentionFor(o, t.id);
                  const passages = (tm?.role === 'subject' ? tm.key_passages ?? [] : []).slice(0, 2);
                  return (
                    <li>
                      <a href={`/opinions/${o.id}/`} class="text-sm text-(--color-forest-700) no-underline hover:underline">
                        {o.data.title}
                      </a>
                      {passages.length > 0 && (
                        <ul class="mt-1 space-y-1 ml-2">
                          {passages.map((kp: any) => (
                            <li class="text-xs italic text-(--color-fg-muted) pl-2 border-l border-(--color-saffron-200)">
                              "{kp.quote}"
                              {kp.what_it_shows && <span class="not-italic text-(--color-fg-muted) ml-1">— {kp.what_it_shows}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
```

Interviews are out of Phase B scope (no `thinker_mentions[]`), so the `interviewsAbout` render at lines 286-298 stays unchanged.

- [ ] **Step 6: Verify in the browser**

The astro preview server should still be running on 127.0.0.1:4321 (PID 53647 per the initial state check). If it's not, start it:

```bash
cd apps/site && pgrep -f "astro preview" >/dev/null || nohup npx --offline astro preview --host 127.0.0.1 --port 4321 > /tmp/astro-preview.log 2>&1 &
```

Astro preview serves the LAST build's output; trigger a fresh build first:

```bash
cd apps/site && npm run build 2>&1 | tail -5
```

Expected: build succeeds, ≥1,225 pages. Then check a touchstone bio page renders the new section:

```bash
curl -s "http://127.0.0.1:4321/thinkers/a-d-shroff/" | grep -o "How A. D. Shroff is discussed in this archive" | head -1
```

Expected: the matched string prints once. Also visit the URL in a browser to eyeball the rendering — the new "How … discussed" section should sit between the themes aside and the "By A. D. Shroff" section, with prose paragraphs and italicised quote-strip paragraphs.

Verify evidence quotes render under at least one Section 3 entry:

```bash
curl -s "http://127.0.0.1:4321/thinkers/a-d-shroff/" | grep -E "border-\(--color-saffron-200\)" | head -3
```

Expected: ≥1 line — the `border-l border-(--color-saffron-200)` class only appears on the new italic blockquote `<li>`s.

- [ ] **Step 7: Commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/pages/thinkers/\[slug\].astro
git -c commit.gpgsign=false commit -m "feat(ui): bio page surfaces Phase B mentions + evidence quotes"
```

---

### Task 14: Write `audit-ner-coverage.py` and run the acceptance audit

**Files:**
- Create: `scripts/synthesis/audit-ner-coverage.py`

**Per supplementary spec §6 and parent doc § Phase B success metric.** Reports the coverage percentages and the touchstone-coverage table.

- [ ] **Step 1: Create the script**

```python
#!/usr/bin/env python3
"""
Phase B coverage audit. Reports:
  - % of in-scope English entries with ≥1 thinker_mentions[] record
  - average mentions per entry
  - touchstone thinker coverage (live mentions vs expected baseline)
  - count of entries with zero matches

Per supplementary spec §6. Run after apply-ner.py lands.

Run:
    python3 scripts/synthesis/audit-ner-coverage.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = ROOT / "apps/site/src/content"
IN_SCOPE = ("musings", "opinions", "theprint-mirror", "primary-works")
TOUCHSTONES = [
    ("a-d-shroff", 50),
    ("jawaharlal-nehru", 40),
    ("mahatma-gandhi", 20),
    ("friedrich-hayek", 5),
    ("adam-smith", 5),
    ("karl-marx", 5),
    ("nani-palkhivala", 15),
    ("minoo-masani", 15),
    ("b-r-shenoy", 10),
    ("jagdish-bhagwati", 10),
]

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)
_THINKER_RX = re.compile(r"-\s+thinker:\s*(?:\"([^\"]+)\"|(\S+))", re.M)


def count_mentions(text: str) -> tuple[int, list[str]]:
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return 0, []
    fm = m.group(1)
    # Find the thinker_mentions: block
    tm_block_match = re.search(
        r"^thinker_mentions:\s*(?:\[\]|((?:\n[ \t]+.*)+))", fm, re.M,
    )
    if not tm_block_match or not tm_block_match.group(1):
        return 0, []
    block = tm_block_match.group(1)
    slugs = [m[0] or m[1] for m in _THINKER_RX.findall(block)]
    return len(slugs), slugs


def main() -> int:
    per_collection: dict[str, dict] = {c: {"total": 0, "with_mentions": 0, "total_mentions": 0} for c in IN_SCOPE}
    touchstone_counts: Counter = Counter()
    zero_match_examples: list[str] = []

    for collection in IN_SCOPE:
        cdir = CONTENT_ROOT / collection
        for p in sorted(cdir.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            # Language filter (mirror prepare-ner-batches.py)
            fm_match = _FRONTMATTER_RX.match(text)
            if not fm_match:
                continue
            fm = fm_match.group(1)
            lang_match = re.search(r"^language:\s*\"?([a-z]+)\"?", fm, re.M)
            if lang_match and lang_match.group(1) != "en":
                continue
            per_collection[collection]["total"] += 1
            n, slugs = count_mentions(text)
            if n > 0:
                per_collection[collection]["with_mentions"] += 1
                per_collection[collection]["total_mentions"] += n
                for s in slugs:
                    touchstone_counts[s] += 1
            else:
                if len(zero_match_examples) < 20:
                    zero_match_examples.append(f"{collection}/{p.stem}")

    print("\n=== Phase B coverage audit ===\n")
    for c in IN_SCOPE:
        d = per_collection[c]
        if d["total"]:
            pct = 100.0 * d["with_mentions"] / d["total"]
            avg = d["total_mentions"] / max(d["with_mentions"], 1)
            print(f"  {c:<18s} {d['with_mentions']:4d} / {d['total']:4d}  ({pct:5.1f}%)  avg mentions/entry: {avg:.1f}")

    print(f"\n=== Touchstone coverage ===\n")
    for slug, expected in TOUCHSTONES:
        live = touchstone_counts.get(slug, 0)
        flag = "OK " if live >= expected else "LO "
        print(f"  [{flag}] {slug:<25s} live: {live:3d}  expected: ≥{expected}")

    print(f"\n=== Sample zero-match entries (first 20) ===\n")
    for e in zero_match_examples:
        print(f"  {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the audit**

```bash
.venv-extract/bin/python3 scripts/synthesis/audit-ner-coverage.py | tee /tmp/ner-audit.txt
```

Expected:
- musings ≥ 80%
- opinions ≥ 80%
- theprint-mirror ≥ 80%
- primary-works ≥ 60%

**Touchstone counts are advisory, not blocking.** `LO` flags surface where the corpus contains fewer mentions of a thinker than expected — usually because that thinker isn't actually written about often in this archive (niche figures like Sudha Shenoy). A `LO` flag does NOT require prompt iteration; only investigate if a touchstone returns 0 mentions when ≥5 was expected (suggests a real extraction gap). The blocking acceptance gates are §6's percentage thresholds and the spot-check in Step 3 — not the touchstone table.

- [ ] **Step 3: Spot-check 10 random evidence quotes by hand**

```bash
.venv-extract/bin/python3 -c "
import re, random
from pathlib import Path
content = Path('apps/site/src/content')
files = list(content.glob('*/*.md'))
random.seed(42)
random.shuffle(files)
shown = 0
for p in files:
    text = p.read_text()
    m = re.search(r'thinker_mentions:\s*\n((?:\s+.*\n)+?)(?=^\w)', text, re.M)
    if not m: continue
    quotes = re.findall(r'^\s+quote:\s+\"([^\"]+)\"', m.group(1), re.M)
    if not quotes: continue
    q = random.choice(quotes)
    body_match = re.search(r'^---\n.*?\n---\n(.*)$', text, re.S)
    body = body_match.group(1) if body_match else ''
    norm_body = re.sub(r'[*_\`>~]', '', body)
    norm_body = re.sub(r'\s+', ' ', norm_body)
    norm_q = re.sub(r'[*_\`>~]', '', q)
    norm_q = re.sub(r'\s+', ' ', norm_q).rstrip('.,;:').strip()
    hit = norm_q in norm_body
    print(f'{\"✓\" if hit else \"✗\"} {p.parent.name}/{p.stem}: {q[:80]}...')
    shown += 1
    if shown >= 10: break
"
```

Expected: 10/10 lines start with ✓. Any ✗ is a validator-vs-applier inconsistency to fix.

- [ ] **Step 4: Commit the audit script**

```bash
git add scripts/synthesis/audit-ner-coverage.py
git -c commit.gpgsign=false commit -m "feat(synth): audit-ner-coverage.py — Phase B acceptance metric"
```

---

### Task 15: Final build verification and push

**Files:** none modified — verification + push.

- [ ] **Step 1: Run `astro check` and `npm run build`**

```bash
cd apps/site && npx --offline astro check 2>&1 | tail -5 && npm run build 2>&1 | tail -10
```

Expected:
- `astro check`: error/warning/hint count matches the Task 4 baseline (no new errors)
- `npm run build`: ≥1,225 pages, exit 0

- [ ] **Step 2: Visit a few bio pages in the local preview**

```bash
for slug in a-d-shroff jawaharlal-nehru friedrich-hayek adam-smith minoo-masani; do
    echo "=== $slug ==="
    curl -s "http://127.0.0.1:4321/thinkers/$slug" | grep -c "How.*is discussed"
done
```

Expected: each line prints `1` — every touchstone bio page has the new section.

- [ ] **Step 3: Push the branch**

```bash
cd "/Users/siraj/Indian Liberals Website"
git push -u origin claude/festive-kepler-096509
```

- [ ] **Step 4: Open a PR (optional — Adnan may prefer to land on main directly)**

If a PR is wanted:

```bash
gh pr create --title "feat: Phase B in-prose NER + bio-page mention surfacing" --body "$(cat <<'EOF'
## Summary
- Adds thinker_mentions[] across 5 content schemas
- Adds Phase B pipeline scripts: prepare-ner-batches.py, resolve-ner.py, apply-ner.py
- Adds system-ner.txt prompt with real-excerpt worked examples
- Adds audit-ner-coverage.py for acceptance metric
- Updates thinker bio page with "How … discussed" section and inline evidence quotes

## Spec references
- Parent: docs/superpowers/specs/2026-05-18-phase-b-ner-handoff.md
- Supplementary: docs/superpowers/specs/2026-05-18-phase-b-scope-and-b2-audio.md

## Test plan
- [x] apply-ner.py --test (15/15 validator unit tests passing)
- [x] astro check delta = 0
- [x] npm run build succeeds (≥1,225 pages)
- [x] audit-ner-coverage.py reports ≥80% Tier-A coverage, ≥60% primary-works coverage
- [x] 10 random evidence-quote spot-checks substring-match the body

Phase B-2 (interview audio pipeline) is documented in the supplementary spec but NOT implemented in this PR.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Mark Phase B core complete**

In this conversation:
- Update the project memory if any new editorial-team facts surfaced during the run
- Note the Phase B coverage numbers from the audit for the project record

---

**Chunk 4 completion checklist (= Phase B core acceptance):**
- [ ] ≥80% of musings + opinions + theprint-mirror have thinker_mentions[]
- [ ] ≥60% of primary-works (non-trivial summary) have thinker_mentions[]
- [ ] Every touchstone thinker has visible mentions on their bio page
- [ ] "How {Thinker} is discussed in this archive" renders for ≥30 thinkers
- [ ] `npm run build` clean; astro check delta = 0
- [ ] 10/10 random evidence quotes substring-match the body
- [ ] Branch pushed; PR opened (if Adnan wants one)

---

**End of Phase B core implementation plan.** Phase B-2 (interview audio pipeline via Deepgram + Claude correction + reuse of this NER pipeline) is a separate work stream documented in supplementary spec §5; its own plan will be written when Adnan is ready to start that work.
