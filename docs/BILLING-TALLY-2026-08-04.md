# Indian Liberals — billing tally

What was promised, what was built, and what was built beyond the promise.
Written 4 August 2026 against the v3 rebuild proposal (May 2026,
`indian-liberals-rebuild-proposal.pdf`, 19 pages) and the repository at
`7bd3f4de`.

Every "delivered" claim below names the artefact in the repo or the live URL
that proves it.

---

## 1. What was promised

Four packages, one-time, ₹1,20,000 total. Proposal §8.

| | Package | Quoted |
|---|---|---|
| A | Discovery and metadata | ₹30,000 |
| B | Site and CMS foundation | ₹45,000 |
| C | AI and agent layer | ₹30,000 |
| D | Federation and launch | ₹15,000 |
| | **Total** | **₹1,20,000** |

Inclusive of all LLM API costs for the extraction pass, and of three months of
post-launch issue support.

The proposal also **excluded** three things by name (§2, §5, §6): layout
reconstruction of the primary-work PDFs via vision-language models,
paragraph-stable IDs on primary works with full-text search inside them, and
the LLM-synthesised wiki layer. Those were deferred to a future engagement and
are not counted as gaps anywhere below.

---

## 2. Line-by-line: promised against delivered

### Package A · Discovery and metadata · ₹30,000

| Promised | Status | Evidence |
|---|---|---|
| WordPress site audit and content inventory across the eight content kinds | Delivered | `scripts/db-extract/`, `data/corpus-inventory.json`, `data/prod-mirror/` |
| AI-driven structured-metadata extraction pipeline, Thothica designs, builds and runs | Delivered | `scripts/llm-extract/` — rasterize, prepare, dispatch, validate, collect, ledger, overnight runner |
| All LLM API costs for the extraction pass, absorbed | Delivered | Absorbed in full, corpus-wide |
| Author, organisation and year normalisation | Delivered | `scripts/synthesis/` byline resolution (deterministic → LLM → vision), classification passes, coverage audits |
| Master manifests: `works.json`, `thinkers.json`, `organisations.json` | Delivered | `/api/works.json`, `/api/thinkers.json`, `/api/organisations.json`, listed in `/api/meta.json` |

**Package A: complete.**

### Package B · Site and CMS foundation · ₹45,000

| Promised | Status | Evidence |
|---|---|---|
| Astro rebuild with eight content collections | Delivered, exceeded | Thirteen collections defined, eight populated beyond the original set |
| Sveltia CMS with GitHub OAuth, editors sign in once | Delivered, then superseded | Sveltia shipped at `/admin/` with the OAuth proxy (`apps/auth`); replaced by the purpose-built CMS — see §3 |
| Thothica-grade design system: typography, colour, dark mode, mobile, accessibility | Delivered | Source Serif/Sans + Noto Indic, dark mode, responsive, WAI-ARIA disclosure nav |
| Pagefind multilingual search with per-language analyzers | Delivered | Per-page tokenizer selection driven by `<html lang>`; English, Hindi, Gujarati, Marathi, Bengali |
| Migration of Tier A content to clean markdown | Delivered | Musings, profiles, organisation pages, opinions, interviews |
| Multilingual content support: per-language collections, Noto fonts | Delivered | `/<lang>/<collection>/<slug>/` routes, bidirectional hreflang, `x-default` |
| pdf.js viewer for primary-work PDFs | Delivered | Read-PDF tab on the work detail page |

**Package B: complete, with the CMS delivered twice over.**

### Package C · AI and agent layer · ₹30,000

| Promised | Status | Evidence |
|---|---|---|
| Markdown siblings on every page, tier declared in frontmatter | Delivered | `<col>/[slug].md.ts` on every Tier-A collection |
| `/llms.txt`, `/llms-full.txt`, per-thinker bulk-fetch endpoints | Delivered | All three serve |
| `/AGENTS.md` with schema, citation rules, tier documentation | Delivered | Build-generated |
| Paragraph-stable IDs across all Tier A content | Delivered | `p-` + six hex FNV-1a, remark plugin, identical in HTML and `.md` siblings |
| MCP server at `mcp.indianliberals.in` with the eight v1 tools | Delivered, exceeded | **Ten** tools; one registry generates MCP + REST + OpenAPI |
| `/SKILL.md` for Claude users without an MCP client | Delivered | Serves |

**Package C: complete, and larger than quoted.**

### Package D · Federation and launch · ₹15,000

| Promised | Status | Evidence |
|---|---|---|
| ThePrint RSS ingest, AI summaries and topic tags at ingest | Delivered, exceeded | `apps/theprint-ingest` + GitHub Actions weekly; **also** the Hindi column via the WP REST API, which has no working feed |
| Cloudflare deployment: Pages, Workers, R2, DNS, OAuth proxy | Delivered | Pages, four Workers, R2 at 3.51 GB, DNS |
| 200-question eval framework published at `/eval` | Delivered, exceeded | **255** questions, deterministic grading, live at `/eval/` |
| Editor onboarding session and technical handoff documentation | Delivered | `docs/` — CMS workflow, deployment, SEO operations, handoffs |
| Three months of post-launch issue support | In progress | Runs to late October 2026 |

**Package D: complete; support window still open.**

### Verdict on the contract

**All four packages delivered.** Every quoted line item exists and is live. Three
of them shipped materially larger than quoted (MCP tools 10 vs 8, eval questions
255 vs 200, key points a median of 8 per work vs the 3–5 promised).

---

## 3. What was built that was never quoted

Roughly in order of effort.

**1. The Thothica CMS.** The proposal specified Sveltia, an off-the-shelf editor.
That was built and deployed. It was then replaced with a purpose-built Astro
application at `cms.indianliberals.in`: Firebase sign-in with Google or a magic
link, four documented roles enforced by Firestore rules with no service account
anywhere in the system, entry forms generated from the same schema the site
validates against, uploads straight to R2, a Firestore draft shelf that avoids
burning the archive's build capacity, batch folder intake, and saves that land
as GitHub commits credited to the editor who made them. Three routes into the
archive: a copyable prompt, the editor's own API key used entirely in their
browser, or manual entry. Substantially more work than the line item it
replaced.

**2. Per-article body text on 780 works.** The proposal deferred body-text
reconstruction to a future engagement and said so twice. 780 works nonetheless
carry extracted per-article headings, bylines, prose and bullets — a single
Freedom First issue has ten structured article sections. This is deferred future
scope, built inside v1, unbilled.

**3. Video pipeline.** Local Whisper (mlx large-v3-turbo) transcription plus
sherpa-onnx speaker diarization for 110 interviews and lectures. The proposal
said "transcript where we have one"; we generated them. Plus two browse surfaces
that did not exist in the inventory: `/interviews/` (oral history, four
doorways) and `/lectures/`.

**4. Series and Periodicals.** A content type and two browse surfaces that were
not among the proposal's eight kinds. 10 series entities, roughly 600 works
organised into named runs.

**5. Legacy URL preservation.** A 1,539-rule WordPress redirect map as Cloudflare
Pages Functions, covering every old content, author, tag, category, letter and
per-language path. Not scoped, and the reason the rebuild did not cost CCS its
search rankings.

**6. `archive.indianliberals.in`.** A Worker serving the R2 bucket, with its own
statistics landing page and OG card.

**7. `www` canonical-host redirect Worker**, fixing a pre-existing dead origin.

**8. Branded OG social cards.** A PIL compositor producing 1200×630 cards for
every page — per work, per thinker, per musing, per opinion, per section, plus
a home mosaic — hosted on R2. Never mentioned in the proposal.

**9. SEO layer beyond scope.** JSON-LD builders for Organization, WebSite, Book,
Article, Person, BreadcrumbList and CollectionPage; sitemap with hreflang
alternates; IndexNow submission; robots and headers.

**10. Duplicate detection and field-level merge.** 13 PDFs had been ingested
twice; 11 merged with full redirect coverage, 2 deliberately left as distinct
works sharing one scan.

**11. The heading and byline repair.** A misjoin in the extraction pipeline had
zipped two divergent lists together, putting the wrong headings against the
wrong articles across the periodical corpus. Sequence alignment with affine gaps
took it from 164 files / 369 sections to 3 files / 4 sections, with zero prose
lines altered.

**12. Two CCS review spreadsheets**, round-trip ingestible: 725 thinkers and 52
organisations, with the label-to-enum mapping and ID column preserved.

**13. Contributors collection** — 13 profiles, added on request.

**14. The eval paper** at `/eval/paper/`. The proposal promised a score page;
this is the method written up in full, including the failure the eval did not
catch.

**15. Content-check CI.** A schema gate on every push, added after a bad CMS save
silently stopped all publishing for six days. The gap it closes is structural,
not cosmetic.

**16. Key-points digests at scale.** 11,099 bullets across 1,460 works, against a
promise of 3–5 per work.

**17. Round-3 feedback work** (August): Languages browse surface, Events split
into its own section, featured images keeping their own aspect ratios, sort and
mobile filter affordances on Opinions and Musings, count-up statistics,
enlarged search, related-links deduplication across 76 entries, measured page
totals across the whole archive.

**18. Thirteen content collections against the eight specified.**

---

## 4. What remains open

Not billed here. Listed so the invoices are not read as a claim that nothing is
outstanding.

- Three months of post-launch support, running to late October 2026.
- Round-3 items awaiting a decision or material from CCS: revised Home / About /
  Thinkers copy, the Ram Mohan Roy image, where three statistics tiles should
  link, whether "Periodicals" keeps its name, which interviews are misfiled,
  and the Gallery and Testimonials source material.
- Scoped and startable: publisher collections, oral-history group routing for 65
  of 92 interviews, the thinker-page interview threshold, 98 authorless musings,
  home-page separation, the standfirst pass, the contact form.
- Content repair blocked on source: `ff389`, four image-only scans needing OCR,
  16 video works with no upstream transcript, six works whose PDF CCS has not
  supplied.

---

## 5. Billing structure

Three documents. The ₹1,20,000 contract figure is the **fee, exclusive of GST**
(Adnan, 4 August), so tax is charged on top of it.

| # | Description | Taxable value | GST 18% | Payable |
|---|---|---|---|---|
| 1 | Indian Liberals rebuild — part 1 of 2 | ₹50,847.46 | ₹9,152.54 | **₹60,000.00** |
| 2 | Indian Liberals rebuild — part 2 of 2 | ₹69,152.54 | ₹12,447.46 | **₹81,600.00** |
| 3 | Additional work beyond the May 2026 scope | ₹20,000.00 | ₹3,600.00 | **₹23,600.00** |
| | **Total** | **₹1,40,000.00** | **₹25,200.00** | **₹1,65,200.00** |

Invoices 1 and 2 carry taxable values summing to ₹1,20,000.00 exactly — the
contracted engagement — and ₹1,41,600.00 payable with tax.

**Why invoice 1 is ₹50,847.46 and not a round number.** CCS has already paid
₹60,000, and that receipt is GST-inclusive. The taxable value is therefore
₹60,000 ÷ 1.18 = ₹50,847.46, leaving GST of ₹9,152.54. Invoice 1 documents money
already received, so it is written backwards from the amount paid rather than
forwards from a quoted figure.

**Invoice 2 carries the balance of the fee**: ₹1,20,000.00 − ₹50,847.46 =
₹69,152.54, plus GST of ₹12,447.46, payable ₹81,600.00.

**Note on the split.** Neither taxable value falls on a package boundary — the
packages are ₹30,000 / ₹45,000 / ₹30,000 / ₹15,000. The two invoices are
therefore written as **two tranches against one engagement**, each naming the
whole scope, rather than claiming a package boundary that is not there.

**Note on the extras.** ₹20,000 does not attempt to price the work in §3 at
anything like its cost. The CMS alone exceeds it. It is a goodwill figure
against a schedule of out-of-scope work, and the invoice says so.

**GST split.** Thothica is registered in Delhi. A Delhi-registered client takes
CGST 9% + SGST 9%; any other state takes IGST 18%. The rate and the payable
total are identical either way — only the split shown on the face of the
invoice changes.

| # | CGST 9% | SGST 9% | or IGST 18% |
|---|---|---|---|
| 1 | ₹4,576.27 | ₹4,576.27 | ₹9,152.54 |
| 2 | ₹6,223.73 | ₹6,223.73 | ₹12,447.46 |
| 3 | ₹1,800.00 | ₹1,800.00 | ₹3,600.00 |

HSN/SAC for all three: **9983**.

---

## 6. Source documents

- `indian-liberals-rebuild-proposal.pdf` — the contract. **Untracked**: it is
  caught by `.gitignore:52` (`*.pdf`) and has never been committed.
- `docs/2026-07-28-final-report.md` — the full engagement report.
- `docs/handoffs/2026-07-28-scope-vs-delivery.md` — the earlier file run.
- `docs/FEATURE-INVENTORY.md` — the complete feature inventory, 4 August.
- `docs/archive-numbers.md` — how every published figure is counted.
