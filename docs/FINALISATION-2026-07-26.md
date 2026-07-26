# Corpus finalisation — 26 July 2026

End-state audit of the archive, run to answer one question: is every work
uploaded and catalogued exactly once, with nothing duplicated and nothing
skipped? Every figure below was measured against production, not inferred.

## Verdict

| Check | Result |
|---|---|
| Batch PDFs shipped by CCS | 993 |
| Distinct works they represent | 928 (65 works were shipped twice — see below) |
| Batch PDFs unaccounted for | **0** |
| Corpus works | 1,575 |
| Corpus PDFs live and fetchable | **1,457 / 1,457** (3.51 GB, zero empty) |
| Same PDF on more than one record | 2 — both intentional, see below |
| Duplicate record ids | **0** |
| Works on two ontology surfaces | **0** |
| `series_id` pointing at a missing entity | **0** |
| Unpublished drafts | **0** |

## Nothing uploaded or catalogued twice

**In CCS's folder:** 65 works arrived as more than one file. 60 of those are
byte-identical copies (the same PDF shipped twice, often as `foo.pdf` and
`foo (1).pdf`, or the same file in two folders). All 65 collapse to a single
record — that is deduplication working, not double-ingestion.

Of the 5 that differ in bytes, 4 are the same document at different scan
quality or with a 2-byte metadata difference, and in each case the fuller
version is the one live. The fifth was a genuine defect, now fixed:

- `liberal-budget-2006-07` — the live PDF was a **36-page truncation** of a
  43-page document, missing seven pages of appendices. The record already said
  `pages_total: 43`, so the metadata had been extracted from the complete
  document and the *upload* was wrong. The full 43-page file now serves at the
  same key; links are unaffected.

**In the corpus:** 11 duplicate record pairs were merged field-by-field rather
than deleted, because neither copy dominated — one usually held the richer
summary while the other held the better bibliography (native-script title, real
publication year, publisher imprint). 16 redirects (11 canonical + 5
language-prefixed) keep the retired slugs working, and 9 stale targets in the
legacy WP map were repointed.

**Two same-PDF pairs are deliberate** and must not be "fixed" by a future audit:

- `basic-documents-forum-of-free-enterprise-july-18-1956` and
  `forum-of-free-enterprise-speech-by-mr-ad-shroff-july-25-1956`
- `the-central-budget-2004-2005-vis-a-vis-the-liberal-budget-various-july-18-2004`
  and `liberal-budget-building-equitable-society`

Each pair is two genuinely different works that share one combined scan.
Deleting either side loses a real work.

## Nothing skipped

- **Summaries:** 1,558 of 1,575. The 17 without are 16 video works whose
  transcripts are empty or unavailable upstream, plus `ff389`.
- **Key points:** 1,554 of 1,575. The 21 without break down as 14 interviews and
  2 lectures with no transcript to digest, 4 image-only scans with no text
  layer, and `ff389`.
- **`ff389`** (Freedom First, April 1986) is the corpus's only true stub — empty
  summary and body, though `freedom-first-apr1-1986.pdf` exists in the bucket.
  It needs re-extraction, not re-ingestion.

Nothing in either list is an oversight; each is blocked on missing source
material and is recorded rather than quietly dropped.

## Known defect, not addressed here

In many multi-article issues the `###` heading and `*By …*` byline are offset
one position from the prose beneath them, so live pages can attribute an
article to the wrong author. A heuristic flags ~234 of 671 multi-article files;
confirmed by hand in `ff007`, `ff097`, `ff114`, `ff130`. The summaries
themselves are correct. This belongs in the v1.5 extraction pipeline. The
`## Key points` digests added on this date attribute from the prose rather than
the headings, so they are right despite the offset — do not "correct" them to
match the headings.

## Infrastructure notes

- Apex + www serve the Astro site from Cloudflare Pages. **Never bind the apex
  to the R2 bucket** — doing so on this date took the whole site offline.
- `archive.indianliberals.in` is served by the `indianliberals-archive-root`
  Worker (`apps/archive-root/`), which maps `/` to the landing page and passes
  every other path through to R2. A bare R2 custom domain cannot do this: R2 has
  no index-document resolution.
- Cloudflare's git-integrated build produced stale output for commit `6e3c689`
  while reporting it Active. If a deploy looks stale, verify with a marker
  string from the commit and, if needed, `wrangler pages deploy dist` the
  locally-verified artifact.
- The Astro content-layer cache that emits phantom `Duplicate id` warnings lives
  at `apps/site/node_modules/.astro`, not `apps/site/.astro`.
