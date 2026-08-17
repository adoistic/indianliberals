# Swatantra Party papers — condition of the corpus before ingestion

Written 17 August 2026. This describes the **incoming** Swatantra Party papers
scan set as it exists today, measured rather than estimated, so that both
tracks that will touch it — the `llm-extract` ingestion pipeline and the
separate OCR-for-search pass — know what they are handling in advance.

Sections 1–7 are the corpus itself: what it is, and what physical condition it
is in. Section 8 reads those measurements against the pipeline as it currently
stands. Section 9 covers the OCR track, which serves search only.

Nothing here has been ingested yet. No file in the corpus has been modified,
and none needs to be — the measurements are all read-only.

**Corpus location** (Google Drive shared target, read-only to us):

```
/Users/siraj/Library/CloudStorage/GoogleDrive-adnan@thothica.com/.shortcut-targets-by-id/1vDrOqgdnQHTfL5vqJtx-ZRy4e2jf-Bcq/Swatantra Party papers
```

One flat directory. No subfolders. 6,355 PDFs, 22,757 pages, 4.32 GB.

---

## 1. The one thing to know

**99.4% of the corpus has no text layer at all.** These are not badly-OCR'd
PDFs. They are bare JPEG scans in a PDF wrapper, with zero embedded fonts and
zero glyphs.

| | Files | % of files | Pages | % of pages |
|---|---|---|---|---|
| Has a text layer | 40 | 0.63% | 1,420 | 6.2% |
| **Image only, no text** | **6,315** | **99.37%** | **21,337** | **93.8%** |

Every one of the 6,355 files reports `Producer: ABBYY FineReader 8.0
Professional Edition`. So an OCR-capable tool produced them, but the searchable
text layer was exported for only 40 of them. The other 6,315 went through
ABBYY as a scanning-and-assembly step only.

**What this does and does not block.** The `llm-extract` pipeline has no OCR
step by design — `rasterize.py` renders page images and the vision model reads
them directly, so extraction, metadata, summaries and classification are
*unaffected* by the missing text layer. The thing that genuinely breaks is the
Pagefind full-text index in `scripts/fulltext/`, which reads
`page.get_text("text")` and would ingest 21,337 empty strings.

So OCR is a **parallel track for search**, not a precondition for ingestion.
The two can run independently and in either order. §8 works through the
consequences.

## 2. How this was measured

`scripts/swatantra/scan-corpus.py` sweeps the corpus and writes one row per
PDF to `data/swatantra-papers/inventory.tsv`. It takes about 70 seconds on the
M-series laptop and is safe to re-run — it only reads. **Re-run it after OCR**
to confirm the text layer actually landed; the columns are designed to make
before/after directly comparable.

```sh
python3 scripts/swatantra/scan-corpus.py "<corpus-dir>" data/swatantra-papers/inventory.tsv
```

The "no text layer" finding was confirmed three independent ways rather than
trusted from one extractor:

- PyMuPDF returns 0 characters on the sampled pages.
- `pdffonts` lists **no embedded fonts whatsoever** — there is nothing there to
  extract, which is stronger evidence than an empty extraction.
- `pdftotext` run over the **complete** document on a random 300-file sample of
  the no-text group found text in **0 of 300**.

All 6,355 files opened cleanly. **Zero corrupt or unreadable files.**

## 3. What the documents are

Page counts, across all 6,355 files:

| Metric | Value |
|---|---|
| Total pages | 22,757 |
| Min | 1 |
| Max | 437 |
| Mean | 3.58 |
| Median | 1 |
| Std dev | 9.75 |

**Quartiles: p25 = 1, p50 = 1, p75 = 3.** Then p90 = 8, p95 = 12, p99 = 30.

| Length | Files | % of files | Pages | % of pages |
|---|---|---|---|---|
| 1 page | 3,234 | 50.9% | 3,234 | 14.2% |
| 2 pages | 1,350 | 21.2% | 2,700 | 11.9% |
| 3–5 | 883 | 13.9% | 3,241 | 14.2% |
| 6–10 | 481 | 7.6% | 3,691 | 16.2% |
| 11–20 | 283 | 4.5% | 4,126 | 18.1% |
| 21–50 | 100 | 1.6% | 3,039 | 13.4% |
| 51–100 | 15 | 0.2% | 1,016 | 4.5% |
| 101–437 | 9 | 0.1% | 1,710 | 7.5% |

The shape matters for job scheduling: half the corpus is single-page letters,
but the ~124 documents over 20 pages carry a quarter of all pages. A naive
per-file work queue will have terrible tail latency. Queue by page, not by file.

`941-Letter_to_Raju_30-06-1974.pdf` is **437 pages** and is the largest item in
the archive. It is near-certainly a mis-titled bundle rather than a letter, and
should be looked at by a human before it is ingested as a single work.

## 4. The 40 files that do have text

They are almost exactly the contiguous ID block **1605–1642** — the printed
pamphlets, manifestos and convention reports — plus two stray letters
(`24-A-Letter_to_Mr_Minoo_Masani_15-03-1971`, `24-Letter_to_Sardar_Gian_Singh_Rarewala_24-03-1971`).
The bulk correspondence, which is the archival substance of the collection, has
none.

Quality of what is there, scored by dictionary hit rate on extracted tokens:

- **37 are good** (hit rate 0.78–0.89, junk characters under 1%). Errors are the
  classic ABBYY-on-letterpress kind — `otiier` for "other", `willi` for "with",
  `tliat` for "that", `II` read as `11`. Usable as-is; cheap to clean.
- **2 are degraded** — `1641-Swatantra_Party_Constitution...` (0.68) and
  `24-Letter_to_Sardar_Gian_Singh_Rarewala...` (0.65). Sample: *"iiro not less
  dim 250 members"* for "are not less than 250 members".
- **1 is unusable** — `1640-Swatantra_Party_Manifesto.pdf` (0.16). It is a
  **Tamil-language** document that was run through an English-only engine, so
  the output is meaningless. Not degraded OCR; wrong-script OCR. It needs
  `-l tam`, and it is a warning that the corpus is not uniformly English.

Three of these 40 carry a text layer on only *some* pages (`text_layer =
partial` in the inventory), so a blanket skip-if-any-text rule would leave holes.

## 5. Physical condition of the scans

This is the part that governs OCR accuracy, and it is the weakest link.

**Resolution is low.** Page images run about 1,000 × 1,300 px — roughly
**128 DPI** (5,919 files; another 337 sit at 200 DPI). Tesseract's own guidance
asks for 300 DPI. Nothing in the corpus reaches it.

**Contrast is worse than the resolution.** Measuring Otsu ink/background
separation on sampled pages (0–255, higher is more legible):

| Legibility | Files | % of files | Pages | % of pages |
|---|---|---|---|---|
| Faint (sep < 60) | 1,279 | 20.1% | 3,824 | 16.8% |
| Weak (60–90) | 2,261 | 35.6% | 7,562 | 33.2% |
| Adequate (90–130) | 2,357 | 37.1% | 8,978 | 39.5% |
| Strong (≥ 130) | 458 | 7.2% | 2,393 | 10.5% |

Median separation is 86. **Half the corpus by page count sits below the
"adequate" band** — faded carbon copies and mimeographs, mostly.

**Other physical facts:**

- 5,323 files store pages as 8-bit **DeviceRGB JPEG**, 959 as DeviceGray JPEG,
  49 as RGB Flate, 24 as bitonal CCITT. Most pages are scanned in colour even
  though the content is monochrome — 2,545 files (40%) carry genuine colour,
  the rest is just tanned paper recorded in RGB. Grayscale conversion before
  binarisation is a real win here, not a formality.
- 12.4% of sampled pages have over 35% ink coverage — dark scanner-bed borders,
  show-through from the reverse side, punch holes, and halftone photographs in
  the newspaper clippings. These will generate spurious glyphs unless cropped
  and cleaned.
- Skew is visible and common. Deskew is not optional.

## 6. What is actually on the pages

I rendered and inspected a random sample. This is good news, and it is the
single most important input to the "will Tesseract work" question:

**The corpus is machine-produced text, not manuscript.** Typewritten letters
and carbon copies, typeset pamphlets and book pages, mimeographed circulars,
and newspaper clippings. Handwriting is confined to the margins — signatures,
the archivist's pen-circled ID number, and occasional annotations over the
typescript. There is very little handwritten *body* text.

That is the difference between "Tesseract is a reasonable tool here" and
"Tesseract is the wrong tool entirely." It is the former.

The hard sub-populations are the newspaper clippings (multi-column layout,
small dense type, halftone photographs adjacent to text) and the faint
mimeographs.

**Correction, from the completed OCR run.** "Handwriting is confined to the
margins" is true of the bulk but not of everything. Seven files came back with
under 40 characters, and inspecting them shows the cause is not faintness —
they are **holograph documents**: a handwritten list of books, a handwritten
cover note, and a manuscript note from C. Rajagopalachari on his own
letterhead. Tesseract cannot read cursive and never will.

This matters more than seven files suggests, because it is the visible tail of
the 561 files (9%) scoring below 0.50 — some unknown share of those are
part-handwritten too. **These are recoverable, just not by OCR**: the
`llm-extract` vision model reads page images and handles manuscript, so a
handwritten Rajagopalachari note is legible to the extraction pass even though
it is invisible to the search index. Worth flagging the handwritten tail for
that pass rather than treating it as OCR failure.

One narrower miss: `5378-Compliments_of_N_Dandekar` is *printed*, but sparse
centred text on a mostly-empty slip, which `--psm 6` (uniform block) reads as
nothing. `--psm 11` (sparse text) recovers 109 characters. Not worth
re-running the corpus, but if a second pass is ever made, route short
low-yield pages through `--psm 11` before giving up on them.

## 7. Identity and duplication

- The **numeric filename prefix is the physical archive ID** — it matches the
  number circled in pen on the scan itself. It is the stable identifier and
  should carry through to the slug. 6,353 distinct IDs across 6,355 files; two
  IDs (`24`, `167`) are shared by a pair of files each, via an `-A-` suffix.
- **Zero byte-identical duplicate files.**
- But **617 groups of files share a normalised title, covering 1,551 files
  (24% of the corpus).** Titles like `Letter_to_Mr_Minoo_Masani.pdf` recur 27
  times with different IDs. **Slug generation must include the archive ID** or
  a quarter of the corpus will collide.
- A spot check of consecutive-ID same-title groups (e.g. 5102–5105
  `Letter_to_N_Dandeker_04-04-1968`) found first-page images that are visually
  near-identical at thumbnail scale. That is consistent with *either* carbon
  copies of one letter filed separately *or* the same document scanned more
  than once — and those two cases warrant opposite treatment. **This cannot be
  settled from the images**; it needs text-level comparison, so dedupe has to
  run after either OCR or the extraction pass, not before ingestion.

## 8. How this corpus meets the extraction pipeline

Measured against the pipeline as it stands, not as a general observation. The
short version: **this corpus is the opposite shape from the one the pipeline
was built for**, and the mismatch is mostly in our favour.

### 8.1 Rasterization

`rasterize.py` renders at `scale=2.0` (~144 DPI). The source images are 128
DPI, so the renderer is already slightly upsampling and **raising `scale`
buys nothing** — there is no detail behind it. What the model sees is capped
by §5, not by the render setting.

**The blank-page detector is inert on this corpus — but harmlessly so.**
`is_pdf_blank_page` calls a page blank when fewer than 0.1% of pixels are
darker than 240. This paper is tanned and scanned in colour, so the
*background itself* sits below 240. Measured over 180 pages sampled across all
four legibility bands:

| Band | Median non-white ratio | Would trip "blank" |
|---|---|---|
| Faint | 0.996 | 0 / 45 |
| Weak | 0.996 | 0 / 45 |
| Adequate | 0.989 | 0 / 45 |
| Strong | 0.238 | 0 / 45 |

Overall median 0.992 — 55% of sampled pages have essentially *every* pixel
registering as non-white. **Not one page in 180 would be detected as blank.**

The obvious inference is that blank versos will be rendered and dispatched as
if they were content. **That inference is wrong, and it was worth testing
before changing anything.** Re-profiling 681 pages from 120 multi-page
documents with a *relative* detector (ink ratio against the page's own 95th
-percentile background, which is immune to tanning) flags **zero blank pages
too**. The minimum adaptive ink ratio observed is 0.020 — twenty times above
the 0.001 threshold. Even a page that looks blank to the eye
(`1856-Swatantra_Party-Preparatory_Convention`, p4) scores 0.054, because
punch holes and scanner-bed edges put real ink on it.

The reason is simply that **this archive scanned content pages only.** There
are almost no blank versos to catch.

So: `is_pdf_blank_page` is non-functional on this corpus, but it has nothing to
do, and **`rasterize.py` should be left alone.** Changing production code that
the existing corpus also depends on, to fix a problem that does not occur, on a
laptop where the existing corpus is not even mounted for regression testing,
would be a bad trade. Revisit only if a later batch turns out to include
versos.

### 8.2 The anthology machinery barely fires

The continuation loop, `_build_virtual_toc`, `_sub_chunk_essay`,
`essay-synthesis.md`, D4/D14 — the single biggest source of complexity in the
pipeline — is nearly irrelevant here.

| | Files | % |
|---|---|---|
| Fits one 20-page chunk | 6,231 | 98.0% |
| Needs the continuation loop | 124 | 2.0% |
| Over 60 pages → `_build_virtual_toc` | 18 | 0.3% |

Where it *does* fire it fires hard, and on exactly the documents the taxonomy
already anticipates. 74 files match souvenir/convention by filename, and the
**17 of them over 20 pages (1,110 pages)** are textbook `edited_volume` /
`purpose: proceedings` — multi-contributor volumes with real TOCs. The
`metadata.a` prompt already names "Swatantra National Convention Souvenirs" as
its worked example for exactly this case, so the prompt is pre-aimed at this
corpus. Those files deserve a supervised first run; the other ~6,330 are
single-dispatch work.

### 8.3 Genre versus the `work_type` enum

`letter` and `correspondence` are both already in the Zod enum
(`content.config.ts:311`), so the bulk of the corpus has a valid home. But the
enum was built for published works, and this is an office archive:

Genre here is inferred from filenames, first match wins — so a letter that
mentions a convention counts as a letter, and the 26.4% unmatched tail is real
uncertainty, not a rounding error. Treat it as a shape, not a census:

| Filename genre | Files | Maps cleanly? |
|---|---|---|
| Letter | 3,469 (54.6%) | ✅ `letter` |
| Minutes of meeting | 359 (5.6%) | ❌ no enum value |
| Circular / notice | 208 (3.3%) | ❌ |
| Press note / statement | 143 (2.3%) | ❌ |
| Telegram | 126 (2.0%) | ❌ |
| Resolution | 75 (1.2%) | ❌ |
| Souvenir / convention | 54 (0.8%) | ✅ `edited_volume` |
| Manifesto / principles | 43 (0.7%) | ✅ `occasional_paper` |
| Unmatched by filename | 1,680 (26.4%) | — |

Roughly **900 files have no honest `work_type`** and will flatten into
`letter` or `occasional_paper`, losing the distinction between a telegram, a
set of minutes and a party circular. Note also that `correspondence` is
defined as *collected* letters between named individuals — these are loose
single items, so `letter` is the correct value and `correspondence` should be
reserved for any bound compilations found in the set. Worth an enum decision
before 6,355 works are written, because changing it afterwards means a
migration.

### 8.4 The filenames are a free metadata channel

The archive's filenames encode real cataloguing, and the pipeline never sees
it — `byline-sweep` reads page 1 as an image. **This is built and run**:
`scripts/swatantra/filename-metadata.py`, output in §10.

| Signal | Files | % |
|---|---|---|
| Valid parsed date (`DD-MM-YYYY`, `Mon-YYYY`, or bare year) | 5,498 | 86.5% |
| Names a correspondent | 3,299 | 51.9% |
| …of which resolve to an existing `thinker_id` | 1,816 | **55.0% of named** |

`period_window` is derived deterministically from the resolved year, so an 86.5%
free-year rate is a direct win — though the right use is **cross-check on the
model's `year`, not replacement**. 13 filename dates were rejected as
implausible and are flagged rather than dropped.

Top resolved correspondents are who you would expect: `minoo-masani`,
`s-v-raju`, `c-rajagopalachari`, `n-g-ranga`, `piloo-mody`.

**Two traps found and handled, both worth knowing about:**

*Parser noise.* A naive `_to_`/`_from_` match yields a correspondent named
"Bills" (from `Notice_of_Amendments_to_Bills`) and "here-The Onlooker" (from
`Where_do_we_go_from_here-The_Onlooker`). Requiring a correspondence noun
before the preposition removed 270 phantom correspondents — and *raised*
resolution from 51.2% to 55.0%, because the noise was all unresolvable. 75
further strings are flagged `not_a_person` (`Regional Transport Officer`
appears repeatedly and is an office, not a thinker).

*Fuzzy-match false positives.* Edit distance alone proposes `Mohan Singh` →
`manmohan-singh` (0.88), `India` → `indira-gandhi` (0.91) and `HP Mody` →
`mh-mody` (0.86). Those are **different people**, and in a political archive
that class of error is worse than leaving the name unresolved. `alias_verdict`
now requires the surname to match at ≥0.85 *and* the leading token at ≥0.8,
which demotes all of those to `review` while keeping genuine misspellings
(`Dandeker`→`dandekar`, `Naryan`→`narayan`, `Rajagopalchari`→`c-rajagopalachari`).

That leaves **25 high-confidence alias candidates covering 183 files**, and 585
distinct unresolved names. **Nothing is written to the authority file** — the
candidates are staged for editorial, in the sense of
`recommended_authority_additions[]`. Applying the 25 is a human decision, and
two of them (`B N Rao`→`b-g-rao`, `R J Amin`→`r-k-amin`) differ on a middle
initial and should probably be rejected.

### 8.5 Scale

This is a 9× corpus expansion, and three things scale badly.

- **Dispatch volume.** Lower bound of **~25,700 dispatches** (6,593 summary
  chunks + 6,355 × 3 for byline-sweep, `metadata.a`, `metadata.b`), before any
  Opus tiebreaks. Today's corpus is ~500 works. The self-consistency design —
  two Sonnet passes plus conditional Opus — is what makes this expensive, and
  it may be worth asking whether a one-page letter with a legible letterhead
  needs A/B adjudication at all, or whether self-consistency should be gated on
  page count or on `metadata.a` confidence.
- **`tfidf.py`.** It is not naive all-pairs — it uses an inverted index — but
  postings lists grow with the corpus, so total work still scales roughly
  quadratically. 780 → ~7,135 docs is ~9× the documents and therefore ~84× the
  work. The header comment's "~500 docs makes it a sub-5-second job" stops
  being true; expect minutes. Measure it before assuming it still fits the
  build.
- **Cross-link *quality*, which matters more than its runtime.** 3,469 letters
  sharing "Dear", "Swatantra", "Masani", "yours sincerely" will be mutually
  similar and mostly *uninteresting*. The real risk is that they swamp
  `cross-links.json` and degrade "Related across the archive" for the existing
  780 works. The `MIN_DOC_FREQ` / `n_docs * 0.7` pruning and the
  three-per-collection diversity cap will help, but this needs checking against
  real output rather than assumed. Similarly, `auto-hide-orphans.py` will find
  thousands of single-page letters with zero inbound references and draft them
  en masse — correct by its own logic, but probably not the intent.

### 8.6 Tier

These are primary archival sources, so they are **Tier B** under
`ARCHITECTURE.md`: summary-attributed, linking out to the PDF, not quotable to
the paragraph. That is the safe default and it also sidesteps the OCR question
entirely for the site — Tier B never needed a text layer.

## 9. The OCR track — for search, not for ingestion

Everything in this section serves the Pagefind full-text index and nothing
else. It is independent of §8 and can run before, after, or alongside it.

Local tooling, as verified on this laptop today:

| Tool | State |
|---|---|
| `tesseract` | **5.5.2 installed**, at `/opt/homebrew/bin/tesseract` |
| tessdata | **163 languages**, including `tam`, `hin`, `mar`, `guj`, `ben`, `tel`, `kan`, `mal`, `pan`, `urd`, `san`, and `osd` |
| `ocrmypdf` | not installed (`brew install ocrmypdf`) |
| `unpaper` | not installed — needed for `--clean` (`brew install unpaper`) |

The realistic tool is `ocrmypdf` wrapping Tesseract: it does rasterise →
deskew → clean → OCR → embed-text-layer and writes a searchable PDF while
preserving the original page image. The flags that matter given the conditions
above are `--oversample 300` (the corpus is 128 DPI and this is exactly the
low-input-resolution remedy), `--deskew`, `--clean`, `--skip-text` so the 40
existing text layers are not clobbered, and `--sidecar` to emit plain text
alongside — which feeds the index directly. `-l tam` is needed for at least
`1640`. On 10 cores, 22,757 pages is a few hours, not days. All of it is free
and runs offline.

### OCR was run and measured, not estimated

`scripts/swatantra/ocr-pages.py` — PyMuPDF renders at 300 DPI, Sauvola local
adaptive binarisation, then Tesseract. No `ocrmypdf` needed for the index, since
Pagefind wants per-page text rather than an embedded PDF text layer; the output
is already in `fulltext.jsonl` shape. `ocrmypdf` is still the tool if you also
want the PDFs themselves searchable.

**Against ground truth.** The 40 files that already carry ABBYY text are a real
benchmark. On 8 of them:

| | Dictionary hit rate |
|---|---|
| ABBYY FineReader 8.0 (2017) | 0.833 |
| **Tesseract 5.5.2 (this script)** | **0.829** |
| Token-level similarity between the two | **0.986** |

**Tesseract reproduces ABBYY quality on this corpus.** The free local path is
not a compromise on the printed material.

**But printed pamphlets are the easy 6%.** On 24 image-only office records,
stratified across the legibility bands:

| Band | n | Mean hit rate |
|---|---|---|
| Faint | 6 | 0.559 |
| Weak | 6 | 0.689 |
| Adequate | 6 | 0.696 |
| Strong | 6 | 0.717 |
| **All** | **24** | **0.665** |

So expect roughly **0.83 on the printed pamphlets and 0.55–0.72 on the
typescript bulk.** That is "searchable but not quotable": good enough to find a
document by keyword, not good enough to quote from without checking the scan.
Given the corpus is Tier B (§8.6) and quotation is not on offer anyway, that is
an acceptable trade. 2 of 24 fell below 0.50.

**One preprocessing trap worth knowing.** Global thresholding — fixed *or*
Otsu — fails on the pasted-clipping layout, which is common here: a small
newspaper cutting mounted on a large tanned backing sheet. The backing
dominates the histogram, so Otsu splits backing-versus-clipping and discards
the text. `2058-Emergency_Must_Stay_Says_Munshi` came back **0 characters at
every `--psm` setting**, and page-segmentation mode was not the problem.
Sauvola local thresholding recovered it to 543 characters. It also lifted the
`adequate` band from 0.594 to 0.696 overall. If you re-implement this with
`ocrmypdf`, make sure its binarisation is local, or these pages silently
vanish from the index.

**The one hard gate.** `scripts/fulltext/README.md` builds `fulltext.jsonl`
from per-page PyMuPDF text, keyed by R2 object key. Today this corpus would
contribute **21,337 empty page records**. It must not enter that index before
OCR — not because it would break, but because it would silently register 6,315
works as present-and-empty, which is worse than absent. After OCR, `--sidecar`
output populates it directly with no second extraction pass.

Note the ordering freedom this buys: works can be ingested, classified and
published as Tier B *now*, and become searchable later when OCR lands, without
re-running any part of §8.

## 10. Artifacts in this repo

Every script is read-only against the corpus and safe to re-run; the two
long-running ones are resumable.

| Path | Rows | What it is |
|---|---|---|
| `data/swatantra-papers/inventory.tsv` | 6,355 | Physical condition per PDF: `pages`, `bytes`, `text_layer`, `ocr_quality`, `chars_per_page`, `word_hit`, `junk_ratio`, `dpi`, `colour`, `separation`, `legibility`, `ink_pct` |
| `data/swatantra-papers/filename-metadata.tsv` | 6,355 | Derived metadata per PDF: `date`, `year`, `date_flag`, `direction`, `correspondent_verbatim`, `thinker_id`, `resolution`, `genre`, `work_type_suggest` |
| `data/swatantra-papers/authority-candidates.tsv` | 585 | Unresolved correspondents with nearest authority entry, similarity, and a `yes`/`review`/`no` triage verdict |
| `data/swatantra-papers/works-meta.json` | 6,355 | `build-index.mjs`-shaped metas, filename-derived. Each carries `provenance: "filename-derived; not model-extracted"` |
| `data/swatantra-papers/ocr/corpus.jsonl` | growing | `{key, pages[]}` per PDF — the shape `fulltext.jsonl` expects |
| `data/swatantra-papers/uploaded-pdfs.tsv` | growing | R2 upload ledger, `key`/`bytes`/`ok`\|`fail` |
| `scripts/swatantra/scan-corpus.py` | — | Produces `inventory.tsv`. ~70s |
| `scripts/swatantra/filename-metadata.py` | — | Produces the metadata and candidate tables. ~2s |
| `scripts/swatantra/ocr-pages.py` | — | Tesseract + Sauvola OCR. Resumable |
| `scripts/swatantra/upload-pdfs.py` | — | Parallel R2 puts, ledger-resumable, retries transient 500s |
| `scripts/swatantra/build-works-meta.py` | — | Builds the metas map without any model call |
| `scripts/swatantra/pilot-prepare.py` / `pilot-report.py` | — | Stratified extraction pilot and its A/B scorer |
| `scripts/authority/sync_yaml_aliases.py` | — | Syncs curator-declared name forms into the extraction seed |

### R2 layout

Objects land at `swatantra-party-papers/<slug>.pdf`, served publicly by
`apps/archive-root` at `archive.indianliberals.in/<key>`. The slug keeps the
leading archive ID deliberately — 617 title groups covering 1,551 files share a
normalised title, so an ID-less slug collides on about a quarter of the corpus.
Verified: **zero key collisions across all 6,355.**

`upload-pdfs.py` imports `slugify` from `ocr-pages.py` rather than
reimplementing it, so the R2 object key and the `corpus.jsonl` key are the same
function's output and cannot drift. If they ever did, the search index would
point at objects that do not exist.

The condition report itself is published (redacted of local paths) at
`archive.indianliberals.in/docs/swatantra-papers-corpus-condition-2026-08-17.md`.

### Scheduling note

Do not run the OCR and the upload concurrently. Each `npx wrangler` put spawns
a full Node runtime; six of those against eight OCR workers on a 10-core
machine measured **OCR at 0.16 pages/sec against 2.8 uncontended — a 17x
penalty**. Serialised, the two together take about three hours; run together
they take considerably longer. `scratchpad/chain-ocr.sh` sequences them.

These are meant to be *driven from*, not just read. `legibility` selects pages
needing aggressive preprocessing; `text_layer` selects what to skip; `pages`
balances a work queue by page rather than by file; `thinker_id` and `date` give
extraction a free cross-check; `work_type_suggest` is deliberately **blank**
for the 949 files whose genre has no honest enum value, rather than guessing.

Re-running `scan-corpus.py` after OCR turns `text_layer` and `ocr_quality` into
a verification report.

## 11. Pilot results — 12 documents, 39 dispatches

Run 17 August 2026 via `scripts/swatantra/pilot-prepare.py`, which reuses the
real prompts, authority subset, taxonomy and `dispatcher.prepare_request`. **All
12 documents were dispatched through both metadata passes**, stratified across
the four legibility bands and six genres, plus 7 re-runs to verify fixes — 39
subagent dispatches in total. Subagents write their JSON to `response.json` and
return a one-line summary, which is what makes a run of this size orchestrable
at all; `pilot-report.py` scores the files afterwards.

**128 DPI is not a barrier for the vision model.** This was the open question
and the answer is clear. On a *faint*-band 7-page cyclostyled minute the model
recovered the full heading, the letterhead down to "PHONE: 28887 GRAMS:
SURAJYAM", the attendance list, the adjourned-session date and the separately
paginated appendix. On a telegram it read the pasted teleprinter tape (`O 2115
AP 2470 NEW DELHI 1 11 / M R MASANI SWATANTRA PARTY RAJKOT`) and the form's
printer imprint. No OCR involved. §5's legibility worry applies to the OCR
track, not to extraction.

One real accuracy caveat: two runs over the same minute read the letterhead
address as "143" and "148 Mahatma Gandhi Road". **Digits in faint carbon are
where errors land**, which matters because dates and page numbers are digits.

### Three defects found, all fixed

**1. The SYSTEM prompt was never substituted — pre-existing, affects all 780
existing works.** `{{ WORK_TYPE_TAXONOMY }}` and `{{ THEME_VOCABULARY }}` live
in the SYSTEM section of `metadata.a.md`, `metadata.b.md` and
`metadata-tiebreak.md`, but `cmd_prep` applied `_substitute` only to
`user_template`. The model received the literal placeholder text under the
headings "## Work-type taxonomy" and "Theme vocabulary (pick from this list…)",
and fell back to the schema example's "one of the 10 enum values". Six
subagents flagged it unprompted (`work_type_taxonomy_not_supplied`,
"the taxonomy placeholder in the system prompt was not populated").

The effect on themes is the striking part. Same circular, before and after:

| | Before | After |
|---|---|---|
| `themes` | `[]` | `["party-politics", "press-freedom", "marxism-debate", "socialism-debate"]` |
| `theme_proposed_new` | 4 invented snake_case values | `[]` |

**The controlled theme vocabulary has never reached the model.** Every theme in
the archive was freely invented, which is worth re-reading §4's "emergent
first, frozen second" design against — `build-themes-vocab.py` has been
harvesting a vocabulary out of output that was never constrained by one.
Fixed in `driver.cmd_prep`; both blocks now substitute.

**2. The authority subset excluded Minoo Masani.** `_load_authority_subset`
takes 60 of 454 thinkers by confidence then id — an alphabetical guillotine
that ran "A. D. Shroff through Margaret Thatcher". Masani is the correspondent
in **1,171 of 6,355 files**, and every one would have emitted `thinker_id:
null` + `needs_human_review: true`. The binary rule behaved correctly; the
subset was wrong. `_load_authority_subset` now takes an optional `include_ids`
to pin a corpus's frequent bylines, defaulting to None so existing behaviour is
unchanged.

**3. Stale schema hint.** `"work_type": "<one of the 10 enum values>"`
contradicted the newly extended taxonomy; two agents flagged the conflict
explicitly. Now points at the taxonomy block. Prompts bumped to v1.5.

### The enum extension works

With the taxonomy actually reaching the model, all three re-runs reclassified:

| Document | Before | After |
|---|---|---|
| Telegram form | `letter` | `telegram` |
| Central Office Circular no. 36 | `letter` | `circular` |
| Draft minutes, Madras 1962 | `occasional_paper` | `minutes` |

The minutes agent cited both disambiguation rules from §8.3 back verbatim —
meeting record versus notice, and a resolution quoted inside minutes staying
`minutes`. Before the fix, two agents had independently invented
`purpose: "minutes"` and `purpose: "circular"` to express what `work_type`
could not.

### A/B self-consistency, scored across all 12

`scripts/swatantra/pilot-report.py` compares the six fields `driver.py`
escalates to Opus, both as raw strings and case/punctuation normalised:

| Field | Raw | Normalised |
|---|---|---|
| `work_type` | 0 | **0** |
| `authors[].thinker_id` | 0 | **0** |
| `year` | 1 | 1 |
| `byline_verbatim` | 1 | 1 |
| `publisher_verbatim` | 3 | 1 |
| **`title.main`** | **6** | **5** |
| Documents clean on all six | 4/12 (33%) | 6/12 (50%) |

**`work_type` and `thinker_id` agreed on every document.** The two fields whose
errors do the most downstream damage — wrong type, wrong person — are the two
the A/B mechanism never disputed.

**My earlier "normalise punctuation" recommendation was half wrong.** It saves
only 2 of 8 tiebreaks. The real driver is `title.main`, and reading the six
disagreements showed **4 were one pass supplying a descriptive title while the
other correctly emitted `null`** — because these documents carry no printed
title and the prompt had no rule for that case. Case folding cannot reconcile
`null` against an invented string.

So the fix is a prompt rule, not a comparison tweak. **D15, now in both
prompts:** when no title is printed, emit `null` at low confidence with
`title_not_printed` in `missing_metadata_flags`; never invent a descriptive
title, lift the body's opening words, or rebuild one from the filename. Same
principle as the rest of the pipeline — uncertainty is a value, not an absence.

**D15 was re-run, not assumed.** Both previously-disagreeing documents now
return `null` from both passes and agree:

| Document | Before (a / b) | After (a / b) |
|---|---|---|
| `1151-Letter_to_Girish_Munshi` | `"Letter to Girish Munshi, 4 April 1977"` / `null` | `null` / `null` ✅ |
| `6149-Letter_to_Mr_Minoo_Masani` | `"YOURS THIRD APPROVE COVERING LETTER"` / `null` | `null` / `null` ✅ |

If D15 clears all four, the tiebreak rate falls from 50% to roughly 17%. Two of
four are confirmed; the rest is projection from 12 documents. Re-run
`pilot-report.py` on a larger sample before trusting the number.

### The filename hint is a cross-check, and it loses

`work_type` matched the filename-derived hint on 8 of 11, `year` on 10 of 11.
**In all three `work_type` divergences the model was right and the filename
wrong**: `6149-Letter_to_...` is a cable, `846-..._Convention_...` is a
one-page press note *about* a convention, and `2264-Who_Owns_The_Air-Express_
Magazine` is a periodical issue. That is exactly why §8.4 says cross-check
rather than input.

### One caveat on §8.4's filename channel

The filename direction is **not reliable**. `6149-Letter_to_Mr_Minoo_Masani`
is in fact a cable *from* Masani — one pass caught it explicitly ("filename
calls it a letter TO Masani, but the page shows Masani as sender — filename not
trusted"). Filename `date` and `correspondent` are good cross-checks;
`direction` should be treated as a hint only.

## 12. Open questions for a human

Ordered by how much rework the wrong answer causes.

1. **Does `work_type` grow?** ~900 files are minutes, circulars, telegrams,
   press notes and resolutions with no honest enum value (§8.3). Deciding after
   6,355 works are written means a content migration. This is the only question
   here that is cheaper to answer now than later.
2. **Does self-consistency apply to one-page letters?** A/B plus conditional
   Opus over 6,355 mostly-single-page items is the bulk of the ~25,700
   dispatches. Gating it on page count or on `metadata.a` confidence is a
   defensible saving, but it is a deliberate weakening of the quality mechanism
   and should be an explicit decision, not a silent one.
3. **Should filename-derived date and correspondent feed extraction?** 82.2%
   free dates and 53.8% free byline resolution is a large amount of signal the
   pipeline currently discards (§8.4). The conservative use is cross-check
   rather than input — but even that needs somewhere to record a disagreement.
4. `941-Letter_to_Raju_30-06-1974.pdf` (437 pages) — almost certainly
   mis-titled. What is it?
5. **How much of the corpus is non-English?** One Tamil document surfaced by
   accident in the 40 OCR'd files; nobody has surveyed the other 6,315. This is
   answerable cheaply and before either track: Tesseract's `osd` model does
   orientation-and-script detection without transcribing, so `tesseract <page>
   - --psm 0` swept over the corpus yields a script census in minutes. It
   decides the `-l` set for OCR, tells extraction which documents need
   `original_script` handling, and reports page rotation for the deskew stage.
6. Are the same-title consecutive-ID groups distinct carbon copies or repeat
   scans? (§7 — answerable only from text.)
7. Is a re-scan of the faint band feasible at source, or is 128 DPI permanently
   what we have? It bounds the accuracy ceiling for the 11,386 pages (50.0%)
   below the adequate-legibility band — for OCR, and for how much the vision
   model can read too.
