# Indian Liberals: the whole engagement, against what was promised

Thothica for the Centre for Civil Society, in partnership with the Friedrich
Naumann Foundation for Freedom.
Written 28 July 2026. Supersedes `handoffs/2026-07-28-scope-vs-delivery.md`,
which this expands and, in two places, corrects.

The work ran from 16 May to 28 July 2026: **576 commits** across a static site,
an agent data plane, an MCP server, a purpose-built CMS, an evaluation
framework, and the extraction and repair pipelines that produced the corpus.

Every number below was read out of production or out of the repository on the
day of writing. Where a claim in an earlier document turned out to be wrong, it
is corrected here rather than quietly restated.

---

## Part one: what was promised

The v3 proposal of May 2026 divided the work into four packages totalling
₹1,20,000 and five phases. It was unusually specific about what it excluded,
and those exclusions are not counted as gaps anywhere in this report.

| Package | Promised | Price |
|---|---|---|
| **A** · Discovery and metadata | WordPress audit and inventory across eight content kinds; an AI extraction pipeline built and run by us with LLM costs absorbed; author, organisation and year normalisation; three master manifests | ₹30,000 |
| **B** · Site and CMS foundation | Astro rebuild with eight collections; Sveltia CMS with GitHub OAuth; design system with dark mode and mobile; Pagefind multilingual search; Tier A content migrated to clean markdown; Noto fonts for Indian scripts; pdf.js viewer | ₹45,000 |
| **C** · AI and agent layer | Markdown siblings with tier in frontmatter; `/llms.txt`, `/llms-full.txt`, per-thinker endpoints; `/AGENTS.md`; paragraph-stable IDs across Tier A; an MCP server with eight tools; `/SKILL.md` | ₹30,000 |
| **D** · Federation and launch | ThePrint RSS ingest with summaries at ingest; Cloudflare deployment; a 200-question eval published at `/eval`; onboarding and handoff docs; three months of support | ₹15,000 |

**Explicitly deferred to a future engagement**, and still deferred: layout
reconstruction of the primary-work PDFs by vision-language model,
paragraph-stable IDs *on primary works*, MCP tools that read primary-work
bodies, and the LLM-synthesised wiki layer. All four wait on the same thing:
models good enough at page layout that the work will not need doing twice.

The proposal's own north star was a researcher asking *"What did BR Shenoy
actually argue about inflation, who else around him made similar arguments, and
where can I read the original?"* — answerable in one call, with every claim
honestly attributed.

---

## Part two: what exists

### The corpus

| Collection | Records |
|---|---|
| Primary works | 1,575 |
| — periodical issues among them | 740 |
| — interviews among them | 92 |
| — lectures among them | 18 |
| Thinkers | 725 |
| Musings (curated excerpts) | 195 |
| ThePrint mirror | 79 |
| Opinions | 59 |
| Organisations | 52 |
| Contributors | 12 |
| Series | 10 |

1,457 PDFs serve from R2 at 3.51 GB, none empty or truncated. Zero duplicate
record ids, zero unpublished drafts, zero works on two ontology surfaces. All
993 PDFs CCS supplied are accounted for; 65 arrived more than once and collapse
to one record each.

### The software, ground up

**`apps/site`** — 93 source files. Astro 5, statically built, on Cloudflare
Pages. Eleven content collections, Pagefind search with per-language analyzers
for English, Hindi, Gujarati and Marathi, a pdf.js viewer, dark mode, and a
legacy-redirect layer so no URL the WordPress site ever had returns a 404.

**The agent data plane** — `/api/meta.json`, `works.json`, `works/<id>.json`,
`thinkers.json`, `organisations.json`, `search-index.json`, `cross-links.json`,
plus `/llms.txt`, `/llms-full.txt`, per-thinker `/llms-full.txt`, `/AGENTS.md`
and `/SKILL.md`. Every page has a markdown sibling declaring its tier.

**`apps/mcp`** — a stateless Worker at `mcp.indianliberals.in`. One tool
registry generates the MCP surface, the REST surface and the OpenAPI document,
so the three cannot drift apart.

**`apps/cms`** — 28 source files, 8,192 lines, at `cms.indianliberals.in`.
Firebase sign-in, four roles, schema-driven forms, R2 uploads, GitHub commits
credited to the editor, a draft shelf and a batch intake.

**The CMS security model** — there is no Firebase service account anywhere in
this project, deliberately. `firestore.rules` is the root of trust: the super
admin is pinned by email, nobody can grant themselves a role, and the API
routes read a caller's role over REST using that caller's own token, so a rule
that would refuse them in the browser refuses them on the server too. Nineteen
cases now run against the real rules file in the emulator.

**Test suites** — `npm test` runs on every CMS build and covers YAML quoting
against all 2,707 real content files and the private-key conversion at two key
sizes. `npm run test:rules` runs the nineteen security-rule cases in the
Firestore emulator. `npm run test:github` exercises the real commit paths
against the real repository on a throwaway branch, thirteen cases including a
Devanagari and Gujarati round trip. `scripts/eval/test_grade.py` holds
twenty-five cases for the grader.

**`scripts/`** — 14 pipelines: extraction, deduplication, heading repair,
authority control, translation combination, video transcription, series
handling, legacy redirects, SEO, key-point backfill, the eval harness.

### The two-tier promise, measured

`/eval` publishes 255 questions (200 were quoted), graded by arithmetic with no
model judging anything. The pool and the grader are public and re-runnable.

| | |
|---|---|
| Graded (headline) | **70.8%** |
| Loose (source merely named) | 87.5% |
| Strict (citation proven by tool trace) | 58.0% |
| **Answers quoting text the archive does not publish** | **0** |

The zero is the whole point. The archive's design rests on one line — an agent
may quote the clean content down to the paragraph, and must summarise and link
the scanned PDFs rather than pretend to have read them. Across 255 questions
that line held without a single fabricated quotation. The method, including the
failure the eval did not catch, is written up at `/eval/paper`, bylined Adnan
Abbasi.

---

## Part three: promise against delivery

| Promised | Status | Note |
|---|---|---|
| WordPress audit and inventory | **Delivered** | |
| AI extraction pipeline, costs absorbed | **Delivered** | `scripts/llm-extract/` |
| Author, organisation, year normalisation | **Delivered** | |
| `works.json`, `thinkers.json` | **Delivered** | |
| `organisations.json` | **Delivered late** | Never shipped at launch; caught by the 28 July file run and published the same day |
| Astro rebuild, eight collections | **Exceeded** | Eleven collections |
| Sveltia CMS with GitHub OAuth | **Substituted** | Replaced by a purpose-built CMS at no change in price; see Part four |
| Design system, dark mode, mobile | **Delivered** | |
| Pagefind multilingual search | **Delivered** | Four languages with correct analyzers |
| Tier A migrated to clean markdown | **Delivered** | |
| Noto fonts for Indian scripts | **Delivered** | |
| pdf.js viewer | **Delivered** | |
| Markdown siblings with tier | **Delivered** | |
| `/llms.txt`, `/llms-full.txt`, per-thinker | **Delivered** | |
| `/AGENTS.md`, `/SKILL.md` | **Delivered** | |
| Paragraph-stable IDs across Tier A | **Delivered** | FNV-1a, computed at build |
| MCP server, eight tools | **Exceeded** | Ten endpoints; `search` and `fetch` added so ChatGPT deep research reaches the corpus |
| ThePrint RSS ingest | **Delivered** | On GitHub Actions |
| Cloudflare deployment | **Delivered** | Pages, Workers, R2, DNS |
| 200-question eval at `/eval` | **Exceeded** | 255 questions |
| Onboarding and handoff documentation | **Delivered** | `docs/` |
| Three months of support | **Runs from today** | |

Nothing promised is outstanding.

---

## Part four: what was built that nobody asked for

Roughly in order of the work each represents.

**Thothica CMS.** The proposal specified Sveltia, an off-the-shelf git-backed
editor. What shipped is a purpose-built application, and the reason is the
difference between a schema and a job: Sveltia would have shown an archivist a
list of content types and a form of field names. This one asks what they came
to do — put a document online, fix something wrong, add a person, get through a
folder of scans — and works backwards. Firebase sign-in with Google or a magic
link. Four roles with what each can and cannot do written on the page rather
than in a manual. Forms generated from the same schema the site validates
against. Uploads straight to R2. Saves that become GitHub commits credited to
the editor who made them. Three routes to metadata: a copyable prompt for a
cloud model, the editor's own API key used entirely in their browser, or plain
manual entry.

**The draft shelf and batch intake** (28 July). Work started and not finished
now has somewhere to live, in Firestore, invisible to readers and triggering no
build. `/batch` takes a folder: every file goes to R2 before anything else, so
a failure later never loses a document; the queue then reads them one at a time
with the editor's own key; each entry lands on the shelf the moment it is
ready, so closing the tab costs the one in flight and nothing more. A document
the model cannot read is shelved anyway, carrying its file and the reason.
Publishing several drafts is a **single commit** via the git data API, which
matters because a full site build takes about twenty-five minutes and
Cloudflare runs them one at a time: fifty entries approved individually would
occupy the archive until the next day.

**The eval paper** at `/eval/paper`. The proposal promised a score page; this
is the method in full.

**The heading and byline repair.** A misjoin in the v1.5 extraction pipeline
had zipped two divergent lists together, attaching the wrong headings to the
wrong articles across the periodical corpus. Sequence alignment with affine
gaps took it from **164 files / 369 sections (7.0%) to 3 files / 4 sections
(0.1%)** across 209+ files, with zero prose lines altered and zero duplicate
headings introduced.

**A cross-contamination sweep** of all six prose collections, 1,799 documents,
which found six periodicals carrying another issue's content.

**`archive.indianliberals.in`** — a Worker in front of R2 giving the PDFs a
stable public home independent of the site build.

**Branded social cards** — 1,200×630 images for every page, served from R2.

**SEO infrastructure** the proposal never mentioned: a legacy WordPress
redirect map, JSON-LD structured data, IndexNow submission, a www-redirect
worker.

**A video ingestion pipeline** — local Whisper transcription with speaker
diarization, which is where the 18 lectures and the interview transcripts came
from.

**The key-points convention and a 299-work backfill.**

**Two classification exports for CCS** as Excel workbooks, 725 thinkers and 52
organisations, with round-trip ID columns so editorial decisions return to the
corpus without re-keying.

**The corpus finalisation audit** (`FINALISATION-2026-07-26.md`), which is
where the 993-PDF reconciliation happened and where a budget PDF was found to
have uploaded as a 36-page truncation of a 43-page document.

---

## Part five: defects found in our own work

Listed because a report that only describes successes is not a report.

**The CMS could not commit anything, and had never been able to.** GitHub
issues App private keys as PKCS#1 (`BEGIN RSA PRIVATE KEY`); WebCrypto's
`importKey` accepts only PKCS#8. Every attempt to mint an installation token
threw before reaching GitHub, so every save would have failed. It went
unnoticed because Node's `crypto.sign` accepts both formats: the setup scripts
that verified the App's permissions all passed, and nothing that ran outside a
Worker ever exercised the path. Found on 28 July while testing the batch
commit, fixed the same day, and now covered by a test that generates throwaway
keys at two sizes and fails against the old code. **Anything an earlier
document said about saves reaching the archive was true of the design and false
of the running system until 28 July.**

**Five defects on the add and edit screens** (28 July): the add form's entire
runtime-built markup was unstyled because its rules sat in a scoped `<style>`,
which Astro applies only to build-time elements — the same trap the browse
screen had fallen into; the home page's archive-count tiles were unstyled for
the same reason; the six field groups had two different sets of names depending
on which screen you were on; neither form asked before discarding unsaved work;
and the edit screen could not tell whether anything had changed, so Save was
always live and would write an empty commit.

**Four more found while building the batch screen**: an upload helper received
a bare token from one caller and a `Bearer` header from the other, failing as
"sign in first"; drafts recorded the author's address in whatever case Firebase
returned, which the security rules would have refused; duplicate files within a
single selection were queued twice, which matters because CCS's deliveries
contain duplicates; and the CMS told editors the site would update "in a few
minutes" when the real figure is about half an hour.

**The shelf was readable and writable by any stranger who could sign in**
(28 July). Read and write on the drafts collection were gated on `signedIn()`,
and anybody at all can sign in with a Google account. The interface would have
bounced them to `/no-access`, but the rules would still have accepted a direct
write to Firestore, so an outsider could have filled the shelf with rubbish or
read unpublished work. Both are now gated on holding a role, which only an
admin can grant. Found by writing the rules tests, which had never existed;
the rules had been deployed and trusted for weeks without one.

Writing those tests also caught two faults in the tests themselves, worth
naming because they are the kind that make a suite worse than useless:
asserting that a delete fails against a document that was already deleted
passes for entirely the wrong reason, and two cases were checking the wrong
owner.

**Earlier in the engagement**: a grader bug that would have understated the
eval headline badly; 53 false ungrounded-quote violations from too short a
quote threshold; an abstention cell that scored 28% and looked like a finding
until it turned out to be three of my own bugs; 71 duplicate headings
introduced by the first repair pass and reverted wholesale; and a YAML quoting
bug that silently stripped quotation marks from titles.

---

## Part six: what is open

**The agent data plane is English-only.** `/api/*` and every MCP tool filter on
`language === 'en'`. Forty-four non-English primary works (22 Marathi, 21
Gujarati, 1 Hindi) and 23 Hindi ThePrint posts are live and readable under
`/mr/`, `/gu/` and `/hi/`, and search finds them, but an agent asking for a
catalogue will not see them listed. Removing the filter is small. Deciding
whether the tier and citation rules should read differently per language is
not, which is why it is flagged rather than quietly changed.

**Two public counts disagree** for the same reason: the site navigation counts
all languages (1,575 primary works, 79 ThePrint), `/api/meta.json` counts
English only (1,531 and 56). Both are correct; neither says which it is.

**A save takes about half an hour to appear.** A full build is roughly
twenty-five minutes and Cloudflare runs them serially. Nothing is lost and
nobody need wait at the screen. Incremental builds are the fix if it ever
becomes a real irritation, and they are not a small change.

**Deferred by agreement**, unchanged: layout reconstruction, paragraph IDs on
primary works, MCP tools reading primary-work bodies, the wiki layer.

---

## Part seven: how to check any of this

```bash
# Every live surface
for u in / /eval/ /eval/paper/ /api/meta.json /api/works.json \
         /api/thinkers.json /api/organisations.json /llms.txt \
         /AGENTS.md /SKILL.md; do
  printf "%-28s %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' https://indianliberals.in$u)"
done
```

```bash
# Regrade the published run and get the published numbers back
python3 scripts/eval/grade.py scripts/eval/runs/run.json --pool data/eval/pool.json
```

That prints loose 0.875, graded 0.708, strict 0.580, which are the figures on
`/eval` to the digit. `scripts/eval/runs/` also holds an earlier run from the
same day that scored 0.698; the published one is `run.json`. Grading is pure
arithmetic over a saved run, so it gives the same answer every time. Producing
a *new* run means putting a model back through the live MCP surface, which
costs whatever that model costs.

```bash
# The CMS commit paths, against the real repository on a throwaway branch
cd apps/cms && npm run test:github
```

```bash
# The security rules, against the real rules file in the emulator
cd apps/cms && npm run test:rules
```

```bash
# YAML quoting and the private-key conversion, no network needed
cd apps/cms && npm test
```

The eval pool is at `/eval/pool.json`, the answers that were graded at
`scripts/eval/runs/run.json`, the results at `data/eval/results.json`, and the
grader at `scripts/eval/grade.py`. The corpus reconciliation is in
`docs/FINALISATION-2026-07-26.md`.
