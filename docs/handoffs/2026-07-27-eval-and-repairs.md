# Indian Liberals — `/eval`, the heading repair, and what the work turned up

Written 27 July 2026. Supersedes the numbers in
`2026-07-26-remaining-work-handoff.md`, which were estimates; several were
wrong, and the corrections are the useful part of this document.

---

## 1. `/eval` is built

Package D's last unmet commitment. The proposal specified a 200 to 500 question
pool covering both tiers, deterministic grading on 0 / 0.5 / 1 by substring plus
structured-citation check, published at `/eval`. All of that now exists.

- **Pool**: 256 questions, frozen at `data/eval/pool.json`, served raw at
  `/eval/pool.json`.
- **Harness**: `scripts/eval/`. See its `README.md` for the full method.
- **Page**: `apps/site/src/pages/eval/index.astro`.
- **Grading**: `scripts/eval/grade.py`. No model judges anything.

### The first run

Claude Sonnet against the live `mcp.indianliberals.in`, all 256 questions,
27 July 2026. Published at `/eval` and in `data/eval/results.json`.

| | |
|---|---|
| loose (source merely named) | 87.3% |
| **graded (headline)** | **70.7%** |
| strict (citation proven by tool trace) | 58.0% |
| **answers that quoted text the archive does not publish** | **0** |

Distribution: 116 scored 1, 100 scored 0.5, 22 scored 0.

Four things in the per-cell numbers are worth carrying forward:

- **Zero invented quotations in 238 answers.** The two-tier claim is the thing
  this whole exercise exists to test, and it held.
- **Needles are the strongest cell on `graded` (94.1%) and among the weakest on
  `strict` (50.0%).** The agent reliably finds an obscure fact buried in one
  paragraph, then frequently cites the anchor without having fetched that
  paragraph through `get_passage`. Retrieval is good; citation hygiene is the
  gap, and that is precisely the "citation-discipline gap" Falsafa documents.
- **Mixed-tier questions are the weakest cell (50.0%).** Holding both rules in
  one answer, a paragraph anchor for the Tier A source and summary-attribution
  plus a PDF link for the Tier B one, is materially harder than either alone.
  If `AGENTS.md` is to be tightened anywhere, it is here.
- **Tier B `strict` equals `graded`** by construction, since only Tier A
  citations can be checked against a tool trace.

The reach split (see §4) costs about 6 points: 71.8% where the answer is
obtainable from what the tools return, 65.6% where it is not.

### The pool has three dimensions, not one

The proposal only asked for both tiers to be covered. Two more axes were added
because without them a score is not interpretable:

| Dimension | Values |
|---|---|
| `tier` | `A` quotable · `B` summary-only · `mixed` both in one answer |
| `retrieval` | `named` the question names the source · `blind` it does not |
| `shape` | `single` · `multi` two or more sources · `needle` one obscure fact |

**76% of the pool is blind.** A question that names its source measures citation
discipline only; a reader who does not know what is in the archive is the real
case, and the gap between the two numbers is where the retrieval surface is
actually judged. Needles are picked by term rarity, scoring each candidate
paragraph by how many of its words appear in two or fewer documents corpus-wide.

Sampling is seeded (`build_pool.py`, seed 20260727), so coverage is a property
of the corpus rather than of whoever wrote the questions.

### Three scores, published together

`loose` (source merely named), `graded` (the headline, per the proposal), and
`strict` (a paragraph citation counts only if the tool trace shows the agent
fetched it). Publishing only `graded` would hide the citation-discipline gap
that Falsafa documents, so all three are on the page with the caveats.

### The honesty check is the load-bearing part

An answer that presents twelve or more words as a source's own text, where no run
of eight consecutive words appears anywhere in the archive, scores a hard 0
regardless of how well it cites. That is the two-tier claim made falsifiable.

Calibrating it took four passes, and the intermediate versions are worth knowing
about because each false-positive class is a trap:

1. Quotes were checked only against the question's *expected* sources, so an
   answer legitimately quoting another archive document was marked invented. Now
   checked corpus-wide.
2. An eight-word floor caught quoted *titles*. Raised to twelve, plus an
   explicit title allowance.
3. `"([^"]+)"` matched the text *between* one quotation's closing mark and the
   next one's opening mark, flagging ordinary connective prose. Straight quotes
   are now paired per line by splitting on the delimiter.
4. Editorial marks (`accrue[s]`, ellipses) break any run of consecutive words, so
   an accurate quotation looked invented. Variants are now tested.

Net effect: 53 flagged of 120 real answers at the start, **0 false positives** at
the end, while `test_grade.py` still catches a synthetic invented quotation.

`scripts/eval/test_grade.py` asserts every rubric branch against the real corpus.
It caught a bug that would have capped **every** Tier A question at 0.5: the
grader required an absolute `https://` citation, but the API reports page URLs
site-relative, so no Tier A citation ever matched. Run it after touching
anything in `scripts/eval/`.

### Re-running

```
cd apps/site && npm run build          # paragraph anchors only exist in the build
python3 scripts/eval/build_corpus.py   # refresh ground truth
python3 scripts/eval/validate_pool.py  # re-freeze the pool against it
python3 scripts/eval/test_grade.py     # prove the rubric still holds
python3 scripts/eval/grade.py scripts/eval/runs/run.json --write
```

---

## 2. The heading/byline misjoin: measured, then repaired

### The 234 estimate was about half wrong

`detect.py`'s suspect list was never validated at scale. It is now:

| | |
|---|---|
| `detect.py` suspects | 234 |
| Of those, genuinely misjoined | **127** (54% precision) |
| Misjoined files it never flagged | **37** |
| True scope | **164 files · 369 sections** (7.0% of 5,289 sections in 765 multi-article works) |

Mass-editing the 234 list would have corrupted about 107 correctly-labelled
files and still missed 37 broken ones. The handoff was right to insist on
verification first.

### It is not an offset

The handoff describes headings sitting "one position out of step". The real
structure is worse and more tractable at once. The v1.5 extraction produced a
list of headings and a list of per-article summaries and **zipped them
together**. Wherever the lists diverge, because a heading was captured with no
summary or a summary with no heading, everything after the divergence slips.
Files with two divergences show two different offsets, and offsets run from
**-10 to +8 in both directions**.

So a rotation is the wrong tool: it would repair the middle of a file and
corrupt both ends. `ff130` is the worked example. Sections 0 and 1 are correct,
2 through 7 slip by +1, and the last two sections have no heading at all,
because "Reviews: Six Years Under Communism" and "With Many Voices" were never
captured while "Innocent By Definition" was captured with no summary.

### What fixed it

The extraction wrote each article's prose as a third-person summary that names
its own subject: *"S. Sharangpani's 'Double-cross At Moshi' recounts how the
Indian delegation…"*. So the prose carries its own label, and the repair is a
**monotonic sequence alignment** of prose blocks against headings, with affine
gaps, scored only where the prose positively identifies an article.

- `scripts/heading-offset/measure.py` — measures the misjoin, per section
- `scripts/heading-offset/repair.py` — aligns and rewrites

Applied: **55 files rewritten, 371 section labels corrected, 0 prose lines
altered** (verified by comparing prose lines as a multiset before and after, on
all 55). Orphaned headings are kept in page order with a note rather than
dropped, because the article was in the issue.

**109 misjoined files were deliberately not touched** and are listed in
`scripts/heading-offset/repair-report.json`: 78 where the global alignment
agrees with the current labels anyway, 27 with too little evidence, 4 where the
prose contradicts the alignment. `ff097` is among them despite being
hand-confirmed, because its prose quotes no matchable titles. These need a human
or a vision pass over the PDFs.

Three subtleties that cost time and would cost it again:

- **Only the first quoted title in a prose block counts.** A summary routinely
  mentions the next article ("It is followed by James McAuley's poem 'Innocent by
  Definition'"), and crediting every quotation made blocks appear to claim two
  headings at once.
- **One-word candidate titles must be rejected** unless they equal the heading
  exactly. Accepting the bare word "Review" matched every heading beginning
  "Review:".
- **Affine gaps, and a state-aware traceback.** With a flat gap penalty the
  aligner scattered single gaps to chase stray evidence; with a cell-based
  traceback it did not reproduce its own optimum.

The `## Key points` digests were left alone, as instructed. They were written
from each paragraph's self-identifying text and were already right.

### Doubled bylines: 79 files, not 46

The handoff counted `*By by ` (145 occurrences, 46 files) and missed
`*By By ` (91 occurrences, 33 more files). All **236 occurrences across 79
files** are fixed. No triples exist, and no other collection is affected.

---

## 3. `ff389`

The handoff gives its PDF as `freedom-first-apr1-1986.pdf` on R2. That path
404s. The file is at
`https://archive.indianliberals.in/freedom-first/freedom-first-apr1-1986.pdf`
(the `/freedom-first/` prefix, not `/liberals/`), 5.9 MB, 60 pages, and the
recorded `pdf_url` in the frontmatter is correct.

**Re-extracted from all 60 pages.** It now carries a 2,509-character summary and
a body in house format: `## Summary`, `## Key points` (8 bullets), and
`## Essays` with 16 sections covering the 13 TOC items plus "With Many Voices",
"Of Cabbages and Kings" and the book reviews. The placeholder is gone. Nothing
contradicted the existing 13-entry TOC. `physical.pages_rendered` was a stale
20 and is now 60.

Three things from the source that CCS should know, none of them errors:

- **The cover essay is a disagreement, not a position.** Masani argues *for* a
  uniform civil code, citing his Constituent Assembly Minute of Dissent with
  Ambedkar, Amrit Kaur and Hansa Mehta; Seervai argues explicitly *against* one
  while agreeing the government's Bill must be opposed. Downstream copy must not
  present Tyabji, Masani and Seervai as one voice.
- The `toc_index: 7` entry packs three people into a single
  `thinker_unresolved` string. A data-shape wart worth normalising.
- "Of Cabbages and Kings" records the masthead change that explains the two
  `role: editor` entries: K. S. Venkateswaran resigned and R. Srinivasan joined
  with this issue.

Scan quality degrades at the foot of pages 34, 35, 38, 42, 45, 54 and 56. Those
lines were summarised only where legible and no claims rest on them. One date on
printed p32 appears to read "21st April 1986", which cannot be right for an April
1986 issue and conflicts with a 25 February date nearby; both were left out
rather than guessed.

### The four image-only scans are less blocked than described

`bharatasathi-sharad-joshi`, `evils-of-child-marriage`, `from-darkness-to-light`
and `poshindyanchi-lokshahi-sharad-joshi` all already carry substantial
summaries, written from cover and metadata rather than from a text layer. What
they lack is a `## Key points` digest. So the blocker is narrower than "cannot be
digested": they need OCR only for the bullet-level digest, and
`scripts/combine-translations/deskew_split.py` remains the tool if any of them
turn out to be sideways spreads.

The 16 video works with empty upstream transcripts were left alone.

---

## 4. Defects found along the way, none of them fixed

These came out of building the eval. Each is filed as its own piece of work.

### 485 Tier A pages have nothing to cite

436 of 695 thinker profiles and 49 of 52 organisation pages carry **no paragraph
anchors at all**. Their content is entirely frontmatter (`bio_source:
ai_drafted_stub`), so the `.md` sibling is a fenced JSON block with no prose.
`AGENTS.md` tells agents that all of Tier A is paragraph-citable and to quote it
with `#p-xxxxxx` anchors. For these 485 documents there is nothing to anchor.

Same family as the heading misjoin: the agent-facing contract promises more than
the data supports. Either emit prose for stub profiles, or mark them ineligible
for paragraph citation in the search index and in `AGENTS.md`.

The eval draws Tier A questions only from pages that genuinely carry anchors, so
the published score is not diluted by documents no agent could have cited.

### The tool layer denies body text the site serves

`read_clean_content` on a Tier B work returns *"is Tier B — no trusted body text
exists"*, and `get_work_metadata` returns only the summary and key points. But
the per-article prose for 780 works **is** served at
`https://indianliberals.in/primary-works/<slug>.md`, and `buildWorkCard` puts
that exact `md_url` in every Tier B API response. An agent is told the text does
not exist while being handed its address.

Measured on the pool: 80 of 238 questions (34%), and 64 of 85 Tier B questions,
need detail reachable only that way. `/eval` reports those separately so a thin
retrieval surface is not read as poor citation discipline.

Nothing here breaks the two-tier promise: the per-article text is summary prose
written by our pipeline, not transcribed source. This is a discoverability and
error-message-truthfulness defect. Either stop emitting `md_url` for Tier B and
say what the refusal actually means, or expose the per-article summaries
properly, clearly labelled as summaries.

### The em-dash guard has been failing on `main`

`apps/site/scripts/lint-no-emdash.mjs` exits 1 today, so it protects nothing.
Two causes: it scans comment lines its own docstring puts out of scope, and
about 15 genuine em dashes have since returned to user-visible copy and page
descriptions. CCS raised em dashes in round-2 feedback as reading
"AI-generated", so this is live. Fix the linter to skip comments, clear the real
hits, then wire it into the build or a pre-push hook so it cannot rot again. The
file list is in the task description.

---

## 5. Operational notes that still hold

- The phantom `Duplicate id` cache is `apps/site/node_modules/.astro`, **not**
  `apps/site/.astro`. Clear all three.
- **Never bind the apex to the R2 bucket.** The archive lives on `archive.`
  for exactly this reason.
- Cloudflare's edge serves stale pages for a few minutes after a deploy; add
  `?cb=$RANDOM` when verifying.
- Regenerate the legacy redirect map after any ingestion.

### New ones

- **A user interrupt kills in-flight background agents.** Twelve eval-run agents
  and the heading-offset investigation were lost mid-work this session, having
  done the research but not yet written output. Any agent doing expensive work
  should be told to write its output file incrementally. The one that was told to
  do so salvaged 8 of 10 answers through an API stall.
- `scripts/eval/corpus.json` is 31 MB and gitignored. Rebuild it from
  `apps/site/dist` after every build; the paragraph anchors exist nowhere else.
