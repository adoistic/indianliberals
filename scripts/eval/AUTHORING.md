# Authoring a question for the Indian Liberals eval

You are writing questions for a **deterministic** eval. No LLM judges the
answers. A grader matches strings and validates citation shapes. So a question
is only useful if its correct answer is mechanically checkable.

You will be given a batch file: a cell (`tier` / `retrieval` / `shape`) and a
list of briefs. Each brief carries the real source material for one question.
Write exactly one question per brief, keeping the brief's `id`.

## What the grader checks

For every question, the grader takes the agent's answer text plus its tool-call
trace and awards **1, 0.5, or 0**:

- **Tier A** — 1 when every expected doc is cited as `<page-url>#p-xxxxxx` with
  an anchor that genuinely belongs to that doc. 0.5 when the doc is named but
  the anchor is missing, malformed, or invented. 0 when the doc never appears.
- **Tier B** — 1 when every expected work is named, attributed as *Indian
  Liberals' summary of …*, and accompanied by its working `pdf_url`. 0.5 when
  named but the attribution or the PDF link is missing. 0 when never named.
  **Hard 0** if the answer presents a verbatim quotation as the primary work's
  own words — the archive holds no primary-work body text, so any such quote is
  ungrounded. This check is the point of the whole exercise.
- **`answer_must_contain`** — every string must appear in the answer, matched
  case-insensitively with punctuation and diacritics folded. This is what
  proves the agent actually read the source rather than pattern-matching a
  title.

## Writing the question

**The question must be answerable from the brief's material alone.** Do not ask
for anything the source does not state. Do not ask for a judgement, a ranking,
or an opinion — there is no correct string for those.

**Sound like a reader, not a database query.** "Which Indian liberal argued
that the 1991 reforms arrived by stealth and went uncelebrated?" — not
"Retrieve the musing whose author is Ashok Desai."

### If `retrieval` is `named`

Name the work, its author, or its publication in the question. You are testing
citation discipline once retrieval is trivial.

### If `retrieval` is `blind`

**The question must not name the source.** Specifically it must not contain:

- the document title, or any four consecutive words of it
- the author's or subject's name, or their surname
- the publication or series name

Describe the *idea* or the *fact* and let the agent find the source. If you
cannot pose the question without naming the source, set `"skip": true` with a
one-line reason rather than writing a leaky question.

### If `shape` is `needle`

The brief gives you one paragraph, chosen because it contains terms that occur
almost nowhere else in the corpus. Ask about the specific, obscure fact in that
paragraph — a figure, a place, an institution, a title of a work. The answer
should be findable only by someone who really searched. Put the distinctive
tokens in `answer_must_contain`, and set `paragraph_ids` to that one anchor.

### If `shape` is `multi`

The question must genuinely require **all** the briefed sources — a question
answerable from one of them is a single-source question. Ask something
comparative or cumulative: how two thinkers differed on a point, what several
issues of one periodical show about a change over time, what a profile and a
pamphlet together establish. List every source in `expected.docs`.

### If `tier` is `mixed`

You get one Tier A doc and one Tier B work. Write a question needing both. This
is the sharpest test in the pool: a correct answer quotes the Tier A source
with a paragraph anchor **and** summary-attributes the Tier B work with its PDF
link, in the same answer, without quoting the Tier B work.

## Choosing `answer_must_contain`

One to three strings. Each must be:

- **distinctive** — a proper noun, an institution, a number, a date, a title.
  Never a common word, and never a word already in the question.
- **verbatim from the source**, so a correct answer will reproduce it.
- **short** — a name or figure, not a clause. Long strings fail on trivial
  rewording and make the eval measure phrasing instead of retrieval.
- **absent from your own question.** A string the question already supplies
  proves nothing — the agent can echo it without retrieving anything. Write the
  question first, then pick strings it does not contain.

Prefer a person's surname, a year, a place, or a quantity. Skip anything the
agent could guess without reading the source.

## Output

Write one JSON file, `authored/<batch-file-name>`, shaped:

```json
{
  "batch": 4,
  "cell": { "tier": "A", "retrieval": "blind", "shape": "needle" },
  "questions": [
    {
      "id": "il-0071",
      "tier": "A",
      "retrieval": "blind",
      "shape": "needle",
      "question": "Which Carnatic composer is described as rooting his love of free self-expression in an older devotional lineage?",
      "expected": {
        "docs": ["musings:freedom-of-self-expression"],
        "paragraph_ids": { "musings:freedom-of-self-expression": ["p-09bb7b"] },
        "pdf_urls": {},
        "answer_must_contain": ["Tyagaraja", "Purvacharyas"]
      },
      "rationale": "The paragraph is the only place in the corpus linking Tyagaraja to the Purvacharyas."
    }
  ]
}
```

Rules for the object:

- Keep `id`, `tier`, `retrieval`, `shape` exactly as the brief gives them.
- `docs` uses the brief's `key` values verbatim (`collection:slug`).
- `paragraph_ids` — required for Tier A and mixed docs, keyed by doc key. Use
  only anchors present in the brief. Empty `{}` for Tier B works.
- `pdf_urls` — required for every Tier B work, keyed by work key, copied
  verbatim from the brief. Empty `{}` for Tier A docs.
- `rationale` — one line, why this is answerable and unambiguous.
- If a brief will not yield a sound question, emit
  `{"id": "...", "skip": true, "reason": "..."}` and move on. A skipped brief
  costs nothing; a leaky or unanswerable question corrupts the score.

A validator will reject leaked titles, unknown doc keys, anchors that do not
exist, missing PDF URLs, and `answer_must_contain` strings absent from the
source. Expect it to check your work.
