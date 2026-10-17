# The October 2026 book tranche: OCR and ingest

**Date:** 2026-10-16 · **Author:** Adnan · **Source:** `~/Downloads/BOOKS FINAL DATA`

Twelve scanned books arrived with no text layer. This records what they turned
out to be, how they were OCR'd and extracted, the two cataloguing decisions
taken, and the one step that is blocked.

## 1. What arrived

Ten distinct works in twelve files, 1,832 pages. Every one is a standalone
monograph; none is a numbered instalment of a run except the two National Book
Trust biographies, which print a series statement.

| Slug | Work, per its title page | By | Publisher, year | pp |
|---|---|---|---|---:|
| `minoo-masani-1905-1998` | Minoo Masani (1905-1998) | S. V. Raju | Freedom First, year not printed | 16 |
| `our-growing-human-family-ilg-2007` | Our Growing Human Family | Masani, illus. Moorhouse | Indian Liberal Group, 2007 | 143 |
| `minoo-masani-nbt-2007` | Minoo Masani | S. V. Raju | National Book Trust, 2007 | 124 |
| `our-india-oup-1975` | Our India | Masani, illus. Moorhouse | Oxford University Press, Calcutta, 1975 | 181 |
| `how-businessmen-can-enrich-public-life` | How Businessmen Can Enrich Public Life: D. N. Patodia - Reflections | S. V. Raju | Project for Economic Education, 2014 | 249 |
| `antidote-essays-against-the-socialist-indian-state` | Antidote: Essays Against the Socialist Indian State | Sauvik Chakraverti | Macmillan India, 2000 | 193 |
| `minoo-masani-nbt-hindi-2010` | मीनू मसानी | S. V. Raju, tr. सौमित्र मोहन | National Book Trust, 2010 | 132 |
| `terrorism-v-balachandran-2005` | Terrorism | V. Balachandran | Freedom First and ILG, 2005 | 47 |
| `we-indians-oup-1989` | We Indians | Masani, illus. R. K. Laxman | Oxford University Press, Bombay, 1989 | 118 |
| `the-growing-human-family-oup-1951` | The Growing Human Family | Masani, illus. Moorhouse | Oxford University Press, New York, 1951 | 127 |
| `freedom-and-dissent-essays-in-honour-of-minoo-masani` | Freedom and Dissent | ed. R. Srinivasan | Democratic Research Service, 1985 | 245 |
| `liberalism-and-less-developed-countries` | Liberalism and Less Developed Countries | ed. Bhatt and Trivedi | Gujarat University, 1982 | 257 |

### The groupings inside the batch

1. **Two language editions of one work.** `minoo-masani-nbt-2007` (English,
   ISBN 978-81-237-5079-8) and `minoo-masani-nbt-hindi-2010` (Hindi, ISBN
   978-81-237-5740-7) are the same biography in the National Book Trust's
   **National Biography** series, printed on the Hindi title page as
   राष्ट्रीय जीवनचरित. A `series/national-biography-nbt` entity was created for
   them; it is the only publisher's series in the batch.
2. **Two editions of one work, under two titles.**
   `the-growing-human-family-oup-1951` is the American edition, and its title
   page reads *The* Growing Human Family while its cover reads *Our* Growing
   Human Family. `our-growing-human-family-ilg-2007` is the Indian Liberal
   Group's third printing of the same 1950 book, with new matter.
3. **Masani's illustrated trilogy for young readers**: Our India (1940, revised
   1953), Our Growing Human Family (1950) and We Indians (1989). Not a
   publisher's series, but We Indians states in its preface that it was
   commissioned as a companion volume to Our India after Masani concluded Our
   India could not be revised.
4. **The Mumbai liberal-press cluster.** Four works come from the Freedom First
   / ICCF / ILG / Project for Economic Education address at 148 M. G. Road.
   `terrorism-v-balachandran-2005` was issued for the Masani birth centenary and
   `our-growing-human-family-ilg-2007` is the centenary reprint. Both carry
   `series_id: indian-liberal-group`.

Three of the twelve are themselves collections: `freedom-and-dissent` and
`liberalism-and-less-developed-countries` are festschrift edited volumes, and
`minoo-masani-1905-1998` is a memorial booklet of three separately-bylined
pieces. All three are typed `edited_volume`.

### Filename traps

The incoming filenames are unreliable and the pipeline has a filename-metadata
step, so these are recorded deliberately: file 06 omits the actual title
*Antidote*; files 09 and 10 name the **illustrators** (Laxman, Moorhouse) where
an author is expected; file 10 carries the cover title rather than the title-page
title. None of these reached the content entries, which are extracted from the
page images.

## 2. OCR

`scripts/swatantra/ocr-pages.py` unchanged, at 300 dpi with Sauvola
binarisation, `--psm 6`. Before committing to the run, three preprocessing
variants were measured on sample pages from four books: plain greyscale at psm 6,
plain greyscale at psm 4, and the script's Sauvola path. They came out within
0.008 word-hit of each other, so the existing tool was used as-is rather than
tuned. These scans are 300 dpi clean print, which is strictly easier than the
128 dpi tanned archival paper that script was built for.

Result: 12 of 12 files, 1,832 pages, word-hit 0.80 to 0.87 on the English works.
The corpus is `data/books-oct-2026/corpus.jsonl`, one record per work with
per-page text, keyed by R2 object key. Per-book plain text is in
`data/books-oct-2026/text/` for reading.

Two faults found and fixed:

* **Two pages of Our India are physically upside down in the scan** (PDF 98 and
  108, `/Rotate=0` but inverted content). Tesseract's own orientation detection
  flagged them at only 28 to 30 percent confidence, so they were confirmed by
  re-OCR at each of four rotations. At 180 degrees word-hit goes from 0.248 to
  0.879 and from 0.222 to 0.819. Both pages were replaced and the record carries
  `rotated_pages: [98, 108]`.
* **Two concurrent writers tore a line of the output.** A broken process check
  (`pgrep -fc` is not valid on macOS, so it returned nothing and read as "no
  processes") led to a second resumable run being started while the first was
  still working. Both appended to one JSONL file and interleaved. No data was
  lost, because the torn line was a duplicate, but the recovery is worth
  recording: parse tolerantly, keep the record with the most pages per file,
  rewrite. If a future tranche runs two passes, give them separate output files.

The Hindi volume was OCR'd with `-l hin+eng`. Its word-hit figure of 0.578 is
**not** a quality signal: the metric matches `[A-Za-z]{2,}` against an English
dictionary, so it only ever sees the Latin-script tokens on a Devanagari page.
Spot-checked by reading, the Devanagari is clean.

## 3. Extraction

Both passes of `scripts/llm-extract/` ran on all twelve works: `metadata.a`
then `summary`, 24 subagent dispatches, Sonnet, prompts v1.5 and v1.2. Unlike
the Swatantra tranche, nothing here is filename-derived.

`LLM_EXTRACT_PIN_THINKERS_FILE` was set to
`data/books-oct-2026/pin-thinkers.json` for every dispatch. Without it the
60-thinker authority cap excludes Masani, who is the subject or author of eight
of these twelve works.

**One deliberate deviation from the validated pipeline.** The summary prompt
assumes it sees 20 page images and tells the model to summarise only what it
saw, which is why existing corpus summaries cover chapter one and say so. Full
OCR text now exists, so each summary agent was given both: the page images, and
the whole book as text. Pull quotes were restricted to the page images, because
they publish as verbatim and OCR introduces garbles; the summaries draw on the
full text. Every record states this in `summary_completeness`, and
`covers_full_work` is true for eleven of the twelve. This is why these entries
describe whole books rather than opening chapters.

Yield: 12 metadata records, 12 summary records, 61 pull quotes, and cross-thinker
mentions in the hundreds (Our India 12, the Hindi biography 72, the English
biography 82, the Patodia volume 112, Freedom and Dissent 88).

## 4. Decisions taken

**Edition records, not replacement** (Adnan, 2026-10-16). Two of these works
collide with records already published:

* `our-india` is an 86-page partial scan flagged `no_publisher`,
  `year_not_printed`, `title_page_not_found`. The new `our-india-oup-1975` is the
  complete 181-page eighth impression of the revised 1953 text.
* `we-indians-minoo-masani-1989` is slugged 1989 but the record describes the
  **Indian Liberal Group 2001 reprint** (63 pages). The new
  `we-indians-oup-1989` is the Oxford University Press first edition.

Both existing records keep their URLs and their summaries. The new scans went in
as separate records, cross-linked through `related_works`, with the printing
history in the schema's FRBR-lite `manifestations[]`. A comment in each existing
record explains which edition it actually holds, so the next person does not
have to rediscover the 1989-versus-2001 discrepancy.

**Full-text indexing** (Adnan, 2026-10-16). These twelve break the archive's
metadata-only tier for primary works, as a measured exception rather than a
model change: the scans are 300 dpi print and score 0.80 to 0.87, against
roughly 0.70 for the Swatantra scans. `data/books-oct-2026/fulltext-append.jsonl`
is merge-ready in the exact `{key, pages}` shape `build-index.mjs` reads, and
all twelve keys join `works_meta.json` cleanly.

## 5. For editorial attention

These came out of the extraction and a curator should see them.

1. **`liberalism-and-less-developed-countries` is more significant than its
   cover suggests.** The 1982 Gujarat University volume for B. R. Shenoy carries
   essays by **Milton Friedman, Henry Hazlitt, Gottfried Haberler, Antony
   Fisher, C. Lowell Harriss, George C. Roche III, Leonard E. Read and David D.
   Friedman**, alongside Subramanian Swamy, Gautam Mathur and M. H. Gopal. On
   contributor weight this is one of the strongest items in the archive.
2. **That volume's printed contents is wrong, and the body is right.** Leonard
   Read's essay "Problems Miracles Pose" is in the book at printed pp. 220-224
   but absent from the contents. Roche's essay starts at printed p. 212, not the
   220 the contents gives; Harriss's runs to p. 211, not 219. The contents also
   misprints "Ragunath" for Raghunath, "C. Lawell Harris" for C. Lowell Harriss,
   and "i-ivx" for i-xiv.
3. **The 2007 epilogue to Our Growing Human Family is not Masani's words.** It is
   written in an imagined voice: the Indian Liberal Group pictures him alive at
   102 and composes what he "might have said". For an archive that supports
   citation this needs to be visible on the page, not buried in an
   acknowledgement. The record notes it; a human should decide how it displays.
4. **`minoo-masani-1905-1998` has no printed year** and no title page. It is
   post-1998 on internal evidence. `year: null`, flagged.
5. **Our India carries dated racial and anthropological language** ("Negro",
   "dull savages"). Worth an editorial note on the page rather than a silent
   republication.
6. **Authority additions.** Four thinker stubs were created because the schema
   requires `authors`, `editors` and `subject` to be real references:
   `v-balachandran`, `mahesh-p-bhatt`, `mukund-s-trivedi`, `d-n-patodia`. Every
   other unresolved name stayed as a `thinker_unresolved` string and is listed in
   each record's `recommended_authority_additions`. The notable ones recur across
   several works: C. H. G. Moorhouse, N. A. Palkhivala, Soli Sorabjee, P. T.
   Bauer, B. S. Yamey, Nissim Ezekiel, V. B. Karnik, Firoze Hirjikaka, Saumitra
   Mohan, and the publishers National Book Trust, Oxford University Press and
   Gujarat University.
7. **Organisation mentions are lost by schema design.** The summary pass
   resolved `swatantra-party`, `congress-socialist-party`, `tata-sons`,
   `project-for-economic-education` and `liberal-international` for the memorial
   booklet, but `cross_thinker_mentions[].thinker_id` is typed
   `reference('thinkers')` and those live in `organisations/`. The emitter demotes
   them to `thinker_id_unresolved` so the verbatim survives. If
   organisation-level mentions are wanted, that field needs a companion.

## 6. Blocked: R2 credentials

**The PDFs and the search bundle cannot be uploaded from this machine.** The
wrangler OAuth token has no R2 scope: `wrangler r2 bucket list` fails with
`Authentication error [code: 10000]`, and `wrangler whoami` lists 23 permissions
with no R2 among them. It is also reaching for a different account id than the
one `whoami` reports. This is consistent with the credential rotation left
outstanding in `docs/handoffs/2026-08-20-session-handoff.md` section 4.

Until that is fixed, every `pdf_url` and `cover_image` on the twelve new entries
is a 404, and the full-text index does not include them.

### What remains, in order

```sh
# 1. Re-authenticate wrangler with an R2-scoped token, then confirm:
npx wrangler r2 bucket list        # must list indianliberals-archive

# 2. Upload the twelve PDFs to the keys the entries already point at.
#    Keys are in data/books-oct-2026/manifest.tsv (11 under liberals/, 1 under hindi/).
#    scripts/swatantra/upload-pdfs.py derives keys by slugifying filenames, which
#    does NOT match these slugs, so upload from the manifest rather than reusing it.

# 3. Upload the twelve covers from build-artifacts/books-oct-2026/covers/
#    to covers/<slug>.webp.

# 4. Rebuild the full-text index. Do NOT build it from the 12 new works alone:
#    that would replace the whole-corpus bundle with a 12-work one.
curl -o corpus.jsonl.gz https://archive.indianliberals.in/search/corpus.jsonl.gz
gunzip corpus.jsonl.gz
cat data/books-oct-2026/fulltext-append.jsonl >> corpus.jsonl
python3 scripts/fulltext/export-works-meta.py works_meta.json
node scripts/fulltext/build-index.mjs works_meta.json corpus.jsonl search_bundle
scripts/fulltext/upload_search.sh search_bundle     # shards first, then entrypoints
# re-upload the refreshed corpus.jsonl.gz alongside the bundle

# 5. TF-IDF related-links pass, so the new works appear in "Related across the archive":
python3 scripts/analysis/tfidf.py                   # or scripts/synthesis/tfidf.py
```

## 7. Verification

`npm run build:astro-only` exits 0: **9,792 pages built**. The only warning is
the pre-existing "collection periodicals does not exist or is empty" notice,
recorded as pre-existing in `docs/handoffs/2026-07-26-series-collection.md`.

All twelve work pages render, along with `/series/national-biography-nbt/`, the
four new thinker pages, and the agent-layer `.md` siblings. `check-references.mjs`
reports "every reference resolves, across 9681 entries" and `lint-no-emdash.mjs`
passes. The twelve entries were also checked independently against every enum
the schema constrains (`work_type`, `purpose`, `provenance.source`,
`scan_quality`, `rights.status`, `why_notable`, `page_system`,
`pages_total_source`, authority-addition `kind`) plus required field types.

**The build now takes 2.5 hours** (9,029s) at this corpus size. Worth knowing
before anyone starts one casually, and worth a look if CI is on a timeout.

## 8. Artefacts

| Path | What |
|---|---|
| `data/books-oct-2026/corpus.jsonl` | full OCR, per page, keyed by R2 object key |
| `data/books-oct-2026/fulltext-append.jsonl` | merge-ready `{key, pages}` for the search index |
| `data/books-oct-2026/text/` | per-book plain text, page-delimited |
| `data/books-oct-2026/manifest.tsv` | slug, R2 key and source filename per work |
| `data/books-oct-2026/pin-thinkers.json` | authority ids pinned into every dispatch |
| `data/bake-off-output/<pdf stem>/` | `metadata.a.a.json` and `summary.json` per work |
| `build-artifacts/books-oct-2026/covers/` | twelve 640px WebP covers, awaiting upload |
| `scripts/books-oct-2026/make-covers.py` | cover renderer, manifest-driven |
| `scripts/books-oct-2026/emit-content-entries.py` | emitter, validates every reference before writing |

The emitter is worth reusing. It checks `authors`, `editors`,
`contributors[].thinker`, `related_thinkers`, `series_id`,
`essays_summarized[].author_resolved` and
`summary_structured.cross_thinker_mentions[].thinker_id` against the actual
content collections before writing, and demotes anything that does not resolve
to the matching `*_unresolved` string. The subagents resolve against the
authority *file*, which is not the same set as the `thinkers/` *collection*, and
that mismatch is a build failure rather than a warning.
