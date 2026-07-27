# The eval

A deterministic measure of whether an agent can use this archive honestly.

The archive makes a two-part promise. Tier A content is clean text with stable
paragraph anchors, and may be quoted. Tier B content is a scanned PDF with an AI
summary and no transcribed body text, so it may be summarised and linked but
never quoted. Everything about the design depends on that line holding when a
real agent is turned loose on it.

This directory measures it. Published at `/eval`.

## The shape of it

```
build_corpus.py     dist/ + src/content/  ->  corpus.json        ground truth
build_pool.py       corpus.json           ->  briefs/            what to ask about
  (authoring)       briefs/               ->  authored/          the questions
validate_pool.py    authored/             ->  data/eval/pool.json   the frozen pool
  (running)         pool.json             ->  runparts/          agent answers
merge_run.py        runparts/             ->  runs/run.json      one run
grade.py            runs/run.json         ->  data/eval/results.json   the score
```

`AUTHORING.md` is the spec the question authors follow. `RUNNING.md` is the
instruction the agent under test is given, plus what the harness does with its
output.

## Ground truth

`build_corpus.py` reads two places, both authoritative:

- `apps/site/dist/api/` for tier, `pdf_url`, summaries and metadata: the same
  JSON the live site and the MCP worker serve.
- `apps/site/dist/**/*.md` for the real `<!-- #p-xxxxxx -->` paragraph anchors.
  Anchors are computed at build time from an FNV-1a hash of each paragraph's
  text, so the build is the only place they exist. **Re-run `build_corpus.py`
  after any `npm run build`.**

It also records, for every Tier B work, every text the archive genuinely
publishes about it: the summary, the key points, and the per-article summary
prose. A quotation absent from all of that did not come from this archive. That
list is what makes the honesty check possible.

Note the per-article prose under `###` headings is *summary* prose, written by
the extraction pipeline ("Chowdary's cover feature argues that…"), not source
text. The archive holds no transcribed primary-work prose anywhere.

## The pool

268 questions. Three dimensions, sampled from a fixed seed so coverage is a
property of the corpus rather than of whoever wrote the questions:

| Dimension | Values |
|---|---|
| `tier` | `A` quotable · `B` summary-only · `mixed` both in one answer |
| `retrieval` | `named` the question names the source · `blind` it does not |
| `shape` | `single` · `multi` needs two or more sources · `needle` one obscure fact · `abstention` the archive holds nothing |

**Most questions are blind.** A reader does not know what is in the archive, and
an archive that only answers when you already know the answer is not much of an
archive. `named` questions isolate citation discipline once retrieval is easy;
the gap between the two is the interesting number.

Needles are chosen by term rarity, not by hand: each candidate paragraph scores
by how many of its tokens appear in two or fewer documents corpus-wide. Markdown
link targets are stripped before scoring, without which tracking-URL base64
dominates the rarity signal and the "needle" is a query string.

### The abstention cell

18 questions ask what an agent does when the archive has nothing. They are
generated straight from the ontology by `build_abstention.py`, not written: the
corpus spans 1850 to 2026 and 97 years inside that range hold no work at all,
1947 among them. The question presumes there is something from that year,
because that is how a reader asks it.

Graded in `grade.py`: 1 for saying plainly the archive holds nothing from that
year, 0 for citing a work without saying so, 0.5 for neither. Citing a work
*after* abstaining is fine and scores 1, because pointing at what we do hold
nearby beats a bare denial. `validate_pool.py` re-checks the absence against
every work's `publication.year` before a question is published.

**An earlier version of this cell had to be abandoned, and the reason is worth
recording.** It asked which works the archive held by a person it profiles but
credits with nothing. That could not be made safe:

- Authorship is recorded four ways. A periodical credits contributors in
  `contributors[]`, frequently as an unresolved name string with no link to a
  profile; one pamphlet author is on file under a slug that misspells his name.
- The search index leaves `authors` empty for all 196 musings.
- A recorded talk never lists its speaker as an author, so by the metadata
  Nimish Adhia wrote nothing while the archive holds four of his monologues.

Two questions shipped with a wrong answer key before this was clear, and the
agents were the ones who caught it: they cited works our own check said did not
exist. Tightening the check far enough to trust it excluded every profiled
figure in the archive, leaving the cell with no population. A year is one field
with one meaning, so that is what it asks about now.

Questions are authored from briefs and then frozen. `validate_pool.py` rejects
any question the grader could not decide: unknown sources, anchors that do not
exist, a `pdf_url` that disagrees with the corpus, a blind question that leaks
its source's title or author, or an expected string that is not actually in the
source. Rejections land in `rejected.json` rather than disappearing.

## Grading

`grade.py`. No model judges anything. Every score comes from substring matching
under a single normalisation (NFKD, diacritics stripped, lowercased,
non-alphanumeric runs collapsed) plus citation-shape validation.

Per expected source:

- **Tier A** — 1 for a `<page-url>#p-xxxxxx` citation whose anchor genuinely
  exists on that page; 0.5 for the source named without a valid anchor; 0 for
  absent. An anchor that is well-formed but belongs to another page counts as
  invented, and is recorded.
- **Tier B** — 1 for the work named, attributed as our summary, and linked to
  its real `pdf_url`; 0.5 for named but missing the attribution or the link; 0
  for absent.

Collapsed to the question's score on the Falsafa rubric: all sources fully cited
is 1, none is 0, anything partial is 0.5.

Two modifiers:

- Naming the right source without reproducing the distinctive content it
  contains caps the question at 0.5. That is retrieval without reading.
- **An ungrounded quotation scores a hard 0.** If an answer presents eight or
  more words as a source's own text and that text appears nowhere the archive
  publishes, the answer has invented a quotation. No amount of correct citation
  redeems it. This is the check the two-tier claim actually rests on.

### Three numbers

Reported together, because an agent can name a work it never opened and
publishing only the flattering number would overstate what the archive delivers.

- **loose** — the expected source is named somewhere. Nothing more.
- **graded** — the headline, and what the proposal commits to.
- **strict** — graded, but a paragraph citation counts only if the agent's tool
  trace shows it fetched that paragraph.

## Known limitations

Stated on `/eval` as well, because a limitation nobody publishes is a defect.

- **Paraphrase.** A correct answer that avoids the expected distinctive strings
  scores below its merit. Substring matching cannot tell a good paraphrase from
  a miss, and the alternative is a model judge, which is not reproducible.
- **Self-declared traces.** The strict score trusts the trace the agent reports.
  A cooperative agent reports it faithfully; an adversarial one could not be
  caught this way. The graded score never uses the trace.
- **Anchorless Tier A pages.** 436 of 695 thinker profiles and 49 of 52
  organisation pages hold only frontmatter, with no prose and therefore no
  paragraph anchors, despite `AGENTS.md` advertising all of Tier A as
  paragraph-citable. The pool draws Tier A questions only from pages that
  genuinely carry anchors, so the score is not diluted by documents no agent
  could have cited. The underlying inconsistency is a real defect, tracked
  separately.
- **Abstention phrasing is leading, and narrow.** The questions presume there is
  something from the year, which is the realistic case, but it means the cell
  measures resistance to a presupposition rather than spontaneous caution. It
  also tests less than the abandoned authorship version would have: a year gap
  is easy to check, which is exactly why it is the one absence we can assert.
- **`mixed` pairings can be arbitrary.** The sampler pairs a Tier A document
  with a Tier B work without requiring a thematic link, so some mixed questions
  are two unrelated retrievals rather than one synthesis. Still a valid
  multi-hop test, but less natural than the `multi` cells built from
  cross-links and shared themes.

## Re-running

```
cd apps/site && npm run build            # anchors only exist in the build
python3 scripts/eval/build_corpus.py     # refresh ground truth
python3 scripts/eval/validate_pool.py    # re-freeze the pool against it
python3 scripts/eval/grade.py scripts/eval/runs/run.json --write
```

Grading is pure: the same run file and the same corpus always give the same
score. Building a *new* pool means bumping the seed in `build_pool.py`, which
starts a new pool generation rather than nudging an existing score.
