# Eleven work types for an office archive

## Why

The `work_type` enum was built for a publisher's list: book, pamphlet, essay,
speech, edited volume, periodical issue. The Swatantra Party papers are not a
publisher's list. They are the working paper of a political party — and 949
works, 15% of the corpus, came back as `occasional_paper`, which is the
schema's least specific print type and carries no information at all.

`occasional_paper` was doing two different jobs, and separating them is the
whole point:

* **481 works** where the form WAS knowable and the field discarded it. The
  model's own summary opened by naming it — "This one-page English telegram
  …" — and reading that back resolved them into values the enum already had.
* **468 works** where the form had no home in the enum. A petition is not a
  pamphlet. A receipt is not an essay. The model shrugged because the schema
  left it nowhere to go.

This is the second archival tranche. The first — `telegram`, `minutes`,
`circular`, `resolution`, `press_note` — was added on 2026-08-17 for the same
reason, and is recorded in `docs/handoffs/2026-08-17-swatantra-papers-corpus-condition.md` §8.3.

## The values, counted from the corpus rather than imagined

| Value | Works | What it is |
|---|---:|---|
| `press_clipping` | 107 | a cutting from a newspaper or magazine |
| `report` | 79 | a report, synopsis, or written proceedings |
| `office_record` | 61 | internal working paper: memo, checklist, aide-memoire |
| `notice` | 49 | a posted or circulated announcement |
| `legal_filing` | 45 | affidavit, plaint, petition, writ, judgment |
| `programme` | 37 | event programme, invitation, agenda, itinerary |
| `roster` | 24 | list, register or directory of people or units |
| `financial_record` | 20 | receipt, bill, accounts, subscription record |
| `constitution` | 17 | a party or society constitution, rules, bye-laws |
| `agreement` | 5 | coalition arrangement, memorandum of understanding |
| `form` | 0 | a blank form awaiting completion |

`form` is in the enum and unused: blank forms are in the corpus, but no summary
opens by naming one, so nothing has been assigned automatically. It is there so
the value exists when a human catalogues one.

## How assignment works

`scripts/swatantra/summary_worktype.py`, applied ONLY where `work_type` is
already `occasional_paper`. It can never downgrade an answer the model gave.

The archival patterns match against the summary's **opening clause** — the text
before its first comma — while the older publication patterns get 200
characters. That distinction matters: "report", "notice" and "programme" are
ordinary words, and an essay ABOUT a report mentions one in its second
sentence. Matching anywhere in 200 characters dropped agreement with the model
from 90.8% to 69.7% on works it had already typed.

Agreement with the model's own labels now sits at ~78%, below the 90.8% the
first tranche measured, and that number should be read carefully rather than as
a regression. Most of the remaining disagreement is the new vocabulary doing
its job: the model called a newspaper article an `essay` because
`press_clipping` did not exist, and called an internal minute a `circular`
because `office_record` did not. Agreement with a vocabulary the model could
not choose from is the wrong yardstick. The safety property that matters is
structural — nothing but `occasional_paper` is ever overwritten.

## What is left

231 works remain `occasional_paper`, down from 949. Their summaries do not name
a form in the opening clause: an illustrated argument, an untitled draft, a
document reproducing the Universal Declaration of Human Rights. Some are
genuinely miscellaneous; others would need a human to look at the page. They
are honestly labelled as unresolved rather than forced into a category.

## Downstream

* `apps/site/src/content.config.ts` — the enum.
* `apps/site/src/lib/schema.ts` — schema.org mapping for each new value.
* `prettyType()` in `apps/site/src/lib/languages.ts` needs no change: it turns
  `press_clipping` into "press clipping" already.
* Search facets and the `/primary-works/` filters read the work_type values
  directly, so the new types become filterable without further work.
