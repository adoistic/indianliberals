# Indian Liberals — handoff for the remaining work

Written 26 July 2026, at `fa1053de` on `main` (clean tree, everything pushed and
deployed). This is the context a fresh session needs to finish the engagement.

---

## 1. Background: the proposal, and what happened after it

CCS engaged Thothica in May 2026 on a **₹1,20,000 one-time rebuild** — the v3
proposal, `indian-liberals-rebuild-proposal.pdf` in the repo root. Four packages:

| | Package | Quoted |
|---|---|---|
| A | Discovery and metadata | ₹30,000 |
| B | Site and CMS foundation | ₹45,000 |
| C | AI and agent layer | ₹30,000 |
| D | Federation and launch | ₹15,000 |

All four are delivered and live. The site is Astro on Cloudflare Pages, Sveltia
CMS at `/admin/`, PDFs and covers on R2 behind `archive.indianliberals.in`, MCP
server at `mcp.indianliberals.in`.

### The single most important thing to understand

The proposal drew a hard line, and we crossed it.

§2 deferred body-text reconstruction of the primary works to a future
engagement. §5 said plainly: *"No body-text access to primary works in v1.
Stays a PDF link until layout reconstruction lands."* The contracted
deliverable for a primary work was a **PDF link plus metadata plus an AI
summary** — nothing more.

What actually shipped: **780 works carry extracted per-article body text** —
headings, bylines, per-article prose, per-article bullets. A single Freedom
First issue has ten structured article sections. That is the deferred future
scope, done inside v1, unbilled.

This matters for how you treat the bug in §3 below. It is a defect in work that
was never quoted. The contracted deliverable underneath it is sound.

### Everything else built beyond the quote

- **Series & Periodicals** — a content type and browse surface that was not
  among the proposal's eight kinds. 10 series entities, 598 works organised into
  runs. Merged into one surface at `/periodicals/` on 26 July.
- **Branded OG social cards** — a PIL compositor producing 1200×630 cards for
  every page, on R2 under `og/`. Never mentioned in the proposal.
- **Video pipeline** — local Whisper transcription plus speaker diarization for
  110 interviews and lectures. The proposal said "transcript where we have one";
  we generated them, and built `/interviews/` and `/lectures/`.
- **1,539-rule legacy WordPress redirect map** (`apps/site/functions/_legacy/`),
  preserving old URLs' SEO. Not scoped.
- **`archive.indianliberals.in`** — Worker (`apps/archive-root/`) serving the R2
  bucket, plus a statistics landing page with its own OG card.
- **`www` canonical-host redirect Worker** (`apps/www-redirect/`), fixing a
  pre-existing dead origin.
- **Duplicate detection and field-level merge** (`scripts/dedupe/`) — 13 PDFs
  had been ingested twice; 11 merged with full redirect coverage, 2 deliberately
  left because they are distinct works sharing one combined scan.
- **Two CCS review spreadsheets** — 725 thinkers, 52 organisations, round-trip
  ingestible.
- **Contributors collection** — 12 profiles, added on request.
- **MCP ships 10 tools, not the 8 quoted** — the eight committed plus
  `search`/`fetch` for ChatGPT compatibility.
- **Key points: proposal promised 3–5 per work; median shipped is 8** (11,099
  bullets across 1,460 works).
- **Eleven content collections against the eight specified.**

### Current corpus state

1,575 primary works · 1,558 summaries · 1,554 key-point digests · 725 thinkers ·
52 organisations · 196 musings · 59 opinions · 79 ThePrint · 10 series · 12
contributors. Clean build: exit 0, 0 duplicate-id warnings, 2,714 pages.

**Build note that costs an hour if you miss it:** the content-layer cache that
emits phantom `Duplicate id` warnings lives at `apps/site/node_modules/.astro`,
NOT `apps/site/.astro`. Clear all three:
`rm -rf apps/site/.astro apps/site/dist apps/site/node_modules/.astro`.

---

## 2. TASK ONE — `/eval`, the only unmet contractual commitment

**Package D, quoted and unbuilt.** `https://indianliberals.in/eval/` → 404.

The proposal (§6 Phase 3, and Package D) specifies:

- A question pool of **200 to 500 questions**, covering both tiers.
- **Deterministic** grading: substring plus structured-citation check, graded
  **0 / 0.5 / 1**. Explicitly "the Falsafa pattern".
- **Published at `/eval`** for transparency.

The reference implementation is live at `falsafa.ai/eval` (200 OK) — same
architectural template, same team. Look at it before designing anything.

Why it matters beyond the invoice: the proposal's §9 north star is that this
archive "earns serious citation" because it is honest about which claims are
paragraph-quotable (Tier A) and which are summary-only (Tier B). `/eval` is the
proof of that claim. Without it the two-tier model is an assertion.

**Design constraints that fall out of the proposal:**

- Questions must cover **both tiers**. Tier A answers can be graded on exact
  paragraph citation (`p-xxxxxx` anchors); Tier B answers must be graded on
  correct summary-attribution and a working `pdf_url` — an agent that quotes a
  primary work verbatim has failed, and the grader should catch that.
- Grading must be **deterministic** — no LLM judge. Substring match plus
  citation-shape validation.
- It should exercise the **live MCP surface** (`mcp.indianliberals.in`, 10
  tools) and/or the `/api/*.json` endpoints, since that is what the eval is
  actually testing.
- The page at `/eval` should publish the pool, the method, and the current
  score. Transparency is the point.

Suggested home: `scripts/eval/` for the harness and pool, `apps/site/src/pages/eval/`
for the published page.

---

## 3. TASK TWO — the heading/byline offset (~234 files)

**A live citation-integrity bug.** In many multi-article works, the `###`
article heading and its `*By …*` byline sit **one position out of step** with
the prose beneath them. The prose is right; the label above it belongs to a
different article. So pages attribute articles to the wrong authors.

Confirmed by hand in **`ff007`, `ff097`, `ff114`, `ff130`**. Worked example from
`ff130`:

| Heading and byline shown | What the prose beneath actually describes |
|---|---|
| `Double-cross At Moshi` — *S. Sharangpani* | the "As Others See Us: Indian Dilemma" reprint |
| `As Others See Us: Indian Dilemma` | Adam Adil's "Dr. Sukarno And Malaysia" |
| `De-Militarisation Of Tibet` — *M. A. Venkata Rao* | Dr. L. M. Singhvi on the Defence of India Act |

Typically the first section aligns and drift begins after it.

**Already prepared for you:**

- `scripts/heading-offset/detect.py` — the heuristic detector. For each `###`
  section it compares heading tokens against the first 60 words of the prose
  beneath, flagging files where under 40% of headings match. Skips single-token
  headings like "Notes" to stay conservative.
- `scripts/heading-offset/suspected.json` — the 234 flagged ids.

**Treat 234 as an estimate, not a verified count.** 4 of 4 sampled were true
positives, but the detector has not been validated at scale. Four independent
Sonnet subagents surfaced this while writing digests, naming these ranges:
`ff068/79/81/84/89/94-96`, `ff128–147`, `ff293–300`, `ff358–387`,
`ff097/113/114`.

**Two cautions:**

1. **The `## Key points` digests are already correct.** The subagents who wrote
   them deliberately took attribution from each paragraph's own self-identifying
   text rather than the mismatched heading. Do not "fix" the digests to match
   the headings — that would break correct data.
2. The repair belongs in the **v1.5 extraction pipeline** (`scripts/llm-extract/`)
   or a one-off re-pairing script, not in the digest layer.

Also here, small and cosmetic: **46 files carry a doubled byline** `*By by
<name>*` (145 occurrences). A regex sweep, separate from the offset work.

---

## 4. TASK THREE — the small source-blocked items

Genuinely blocked on missing or unusable source, not oversight:

- **`ff389`** (Freedom First, April 1986) — the corpus's **only** true empty
  stub. Empty summary, empty body, "Awaiting editorial review" placeholder,
  though `freedom-first-apr1-1986.pdf` exists on R2. Needs re-extraction.
- **4 image-only scans**, no text layer: `bharatasathi-sharad-joshi`,
  `evils-of-child-marriage`, `from-darkness-to-light`,
  `poshindyanchi-lokshahi-sharad-joshi`. Need OCR before they can be digested.
  Note the precedent set on 26 July: the Vidyasagar Bengali scan was four
  sideways two-page spreads and was fixed losslessly by
  `scripts/combine-translations/deskew_split.py` — rotate, detect the gutter per
  page, split by narrowing the mediabox. Reuse it.
- **16 video works** with `transcript_status: none` or `unavailable` — the
  transcript is empty upstream. Do not generate key points for these; there is
  nothing to derive them from and the result would be invented.

### Still outstanding from CCS (chase, don't build)

Six works exist as records with no source PDF:

- *Khoj* — July–August 2007, November–December 2008, May–August 2010
- *Doan Pavlant Bali Patalat* — Anant Umrikar
- *Shetakanyachi Raje Shivaji* — Sharad Joshi
- *Yodha Shetkari* — Vijay Prulkar

Plus the Bengali original of *Ramtanu Lahiri o Tatkalin Bangosamaj* — we hold
only an English translation of Chapter V.

---

## 5. Explicitly NOT gaps

Correctly deferred by the proposal. Do not treat these as unfinished:

- VLM layout reconstruction of primary-work PDFs
- Paragraph-stable IDs on primary works, and full-text search inside them
- MCP tools that read primary-work bodies (`read_primary_work`,
  `get_primary_work_passage`)
- The LLM-synthesised wiki layer
- Per-article structured fields (`essays_summarized`, `articles[]`) — §3 puts
  per-article extraction in future scope. They are empty corpus-wide by design.

---

## 6. Working notes

- Deploy: `npm run build` in `apps/site`, then
  `npx wrangler pages deploy dist --project-name indianliberals --branch main`.
  Pushing to `main` also triggers a git-integrated build.
- Cloudflare's edge can serve a stale page for a few minutes after deploy. Add
  `?cb=$RANDOM` when verifying, or you will chase a phantom.
- The Cloudflare API rate-limits hard (error code 971). Wrap `wrangler` calls in
  a retry loop rather than assuming failure.
- **Never bind the apex `indianliberals.in` to the R2 bucket.** Doing so on
  26 July took the entire site offline — a hostname belongs to one thing, and
  attaching it to R2 detached it from Pages. The archive lives on the
  `archive.` subdomain for exactly this reason.
- The AI-written per-work summaries are generated at scale and are out of scope
  for copy edits. Hand-written section copy was humanised on 26 July; most of it
  was already good and was deliberately left alone.
