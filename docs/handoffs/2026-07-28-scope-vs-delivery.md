# Indian Liberals — what was promised, what was built, what was added

Written 28 July 2026, against the v3 rebuild proposal of May 2026.

> **Superseded by `../2026-07-28-final-report.md`**, written later the same day.
> That document covers everything here and adds the draft shelf, the batch
> intake, and the defects found while building them, including one that had
> stopped the CMS committing anything at all since it went up.

Three questions, in order: what the proposal committed us to, what actually
exists today, and what we built that nobody asked for. Every figure below was
read out of production or out of the repository on the day of writing, not
carried forward from an earlier document.

The engagement ran from 16 May to 28 July 2026 — 571 commits.

---

## 1. What was intended

The proposal broke the work into four packages totalling ₹1,20,000, and set
out five phases. Scope was defined as much by exclusion as inclusion: layout
reconstruction of the scanned PDFs, paragraph IDs on primary works, and the
wiki layer were all **explicitly deferred to a future engagement**. Those are
not gaps, and they are not counted as such here.

### Package A · Discovery and metadata · ₹30,000
WordPress audit and content inventory across the eight content kinds; an
AI-driven structured-metadata extraction pipeline built and run by us with the
LLM costs absorbed; author, organisation and year normalisation; and three
master manifests — `works.json`, `thinkers.json`, `organisations.json`.

### Package B · Site and CMS foundation · ₹45,000
Astro rebuild with eight content collections; **Sveltia CMS** with GitHub
OAuth; a design system with dark mode and mobile; Pagefind multilingual search
with per-language analyzers; migration of all Tier A content to clean markdown;
multilingual support with Noto fonts for Indian scripts; a pdf.js viewer.

### Package C · AI and agent layer · ₹30,000
Markdown siblings on every page with the tier declared in frontmatter;
`/llms.txt`, `/llms-full.txt` and per-thinker bulk-fetch endpoints;
`/AGENTS.md`; paragraph-stable IDs across all Tier A content; an MCP server at
`mcp.indianliberals.in` with **eight** v1 tools; `/SKILL.md`.

### Package D · Federation and launch · ₹15,000
ThePrint RSS ingest with summaries and topics at ingest; Cloudflare deployment
across Pages, Workers, R2 and DNS; a **200-question eval framework published at
`/eval`**; editor onboarding and handoff documentation; three months of
post-launch support.

---

## 2. What we ended up creating

### The corpus

| Collection | Records |
|---|---|
| Primary works (markdown files) | 1,575 |
| — of which periodical issues | 740 |
| — of which interviews | 92 |
| — of which lectures | 18 |
| Thinkers | 725 |
| Musings (curated excerpts) | 195 |
| ThePrint mirror | 79 |
| Opinions | 59 |
| Organisations | 52 |
| Contributors | 12 |
| Series | 10 |

1,457 PDFs serve from R2, 3.51 GB, zero empty. Zero duplicate record ids, zero
unpublished drafts, zero works appearing on two ontology surfaces. Every one of
the 993 PDFs CCS shipped is accounted for.

### Package A — delivered

The extraction pipeline is `scripts/llm-extract/`. Author, organisation and
year normalisation ran across the whole corpus. `works.json` and
`thinkers.json` have been live since launch; **`organisations.json` had not
been — this file run is what caught it, and it shipped today.** All three are
now listed in the endpoint directory that `/api/meta.json` advertises.

### Package B — delivered, with one deliberate substitution

Everything shipped as specified except the CMS, and that changed for a reason
covered in §3. Astro rebuild, Pagefind search across English, Hindi, Gujarati
and Marathi, Noto fonts, pdf.js viewer, dark mode, mobile — all live.

The proposal modelled eight content kinds. The site ships **eleven**: the
original eight plus contributors, series, and lectures as a distinct surface.

### Package C — delivered, and larger than specified

`mcp.indianliberals.in` exposes **ten** endpoints, not eight. The two extra are
`search` and `fetch`, the pair OpenAI's deep-research clients require, so the
corpus is reachable from ChatGPT as well as Claude and Cursor. One tool
registry generates the MCP surface, the REST surface and the OpenAPI document,
so they cannot drift apart.

Paragraph-stable IDs (`p-` plus six hex, FNV-1a, computed at build) are live
across all Tier A content. `/llms.txt`, `/llms-full.txt`, per-thinker
`/llms-full.txt`, `/AGENTS.md` and `/SKILL.md` all serve.

### Package D — delivered, and the eval is bigger than quoted

ThePrint ingest runs on GitHub Actions. Cloudflare hosts Pages, Workers, R2 and
DNS. Handoff documentation is in `docs/`.

`/eval` was the last unmet commitment and is now live. Against the quoted
**200 questions, it ships 255**, graded by arithmetic with no model judging
anything:

| | |
|---|---|
| Graded (headline) | **70.8%** |
| Loose (source merely named) | 87.5% |
| Strict (citation proven by tool trace) | 58.0% |
| **Answers quoting text the archive does not publish** | **0** |

128 scored 1, 105 scored 0.5, 22 scored 0. The zero in that table is the point
of the whole exercise: the two-tier promise — quote Tier A, summarise and link
Tier B — held across 255 questions without a single fabricated quotation.

---

## 3. What we built that was not in the proposal

Roughly in order of how much work each represents.

**Thothica CMS — `cms.indianliberals.in`.** The proposal specified Sveltia CMS,
an off-the-shelf editor. What shipped is a purpose-built Astro application:
Firebase sign-in with Google or a magic link, four documented roles with the
permissions written out in the interface, entry forms generated from the same
schema the site validates against, uploads straight to R2, and saves that land
as GitHub commits credited to the editor who made them. It offers three routes
into the archive — a copyable prompt for a cloud model, the editor's own API
key used entirely in their browser, or plain manual entry. Substantially more
work than the line item it replaced, and the reason is that Sveltia would have
put a schema in front of an archivist; this puts a job in front of them.

**The eval paper** at `/eval/paper/`, bylined Adnan Abbasi. The proposal
promised a score page. This is the method written up in full, including the
failure the eval did not catch.

**The heading and byline repair.** A misjoin in the v1.5 extraction pipeline
had zipped two divergent lists together, putting the wrong headings against the
wrong articles across the periodical corpus. Sequence alignment with affine
gaps repaired **164 files / 369 sections down to 3 files / 4 sections** — 7.0%
to 0.1% — across 209+ content files, with zero prose lines altered and zero
duplicate headings introduced.

**A cross-contamination sweep** of all six prose collections (1,799 documents),
which found and fixed six periodicals carrying another issue's content.

**`archive.indianliberals.in`** — a Worker in front of R2 so the PDFs have a
stable public home independent of the site build.

**Branded social cards** — 1,200×630 images generated for every page and
served from R2, so a link to any work renders properly in Slack, WhatsApp,
Twitter and Google.

**SEO infrastructure** the proposal did not mention: a redirect map covering
the legacy WordPress URLs so nothing that was ever linked is now a 404,
JSON-LD structured data, IndexNow submission, and a www-redirect worker.

**A video ingestion pipeline** — local Whisper transcription plus speaker
diarization — which is what made the 18 lectures and the interview transcripts
possible.

**The key-points convention and backfill**, 299 works.

**Two classification exports for CCS** as Excel workbooks — 725 thinkers and 52
organisations — with round-trip ID columns so editorial decisions come back
into the corpus without re-keying.

**Corpus finalisation audit**, documented in
`docs/FINALISATION-2026-07-26.md`, which is where the 993-PDF reconciliation
and the truncated `liberal-budget-2006-07` upload were caught.

---

## 4. Open, and honest about it

**The agent data plane is English-only.** `/api/*` and therefore every MCP tool
filter on `language === 'en'`. Forty-four non-English primary works (22 Marathi,
21 Gujarati, 1 Hindi) and 23 Hindi ThePrint posts are live and readable on the
site under `/mr/`, `/gu/` and `/hi/` — but an agent calling `list_works` cannot
see them. Search covers them; the catalogue does not. The proposal promised the
extraction schema would be language-agnostic, which it is, and that search would
work across languages from launch, which it does. It did not explicitly promise
the manifests would carry them. Removing the filter is a small change; deciding
whether the tier and citation rules should read differently per language is not,
which is why it is flagged here rather than quietly changed.

**Public counts differ between two surfaces** for the same reason: the site
navigation counts all languages (1,575 primary works, 79 ThePrint) while
`/api/meta.json` counts English only (1,531 and 56). Both are correct; neither
says which it is.

**A save takes about half an hour to appear.** A full site build runs roughly
twenty-five minutes — 2,700-odd pages plus the Pagefind index — and Cloudflare
runs them one at a time, so three saves in quick succession queue behind each
other. Nothing is lost and no editor needs to wait at the screen, but the CMS
used to promise "a few minutes", which would have read as a failure. The copy
now says half an hour. If that ever becomes a real irritation, incremental
builds are the fix, and they are not a small change.

**Deferred by agreement, not left undone:** layout reconstruction of the
primary-work PDFs, paragraph IDs on primary works, MCP tools that read
primary-work bodies, and the wiki layer. All four wait on vision-language
models good enough at layout that the work will not need redoing.
