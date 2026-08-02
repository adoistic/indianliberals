# Works with no PDF, and the summaries that go with them

Audit run 2 August 2026 against 1,575 live primary works.

## The short version

Six works are missing a PDF that should have one. All six are vernacular, which
is why they surfaced on the new Languages shelves. **None of the six can be
recovered from anything we hold**: they were never on the curator's drive.

Their summaries are the more serious half. Three describe a different document
altogether, one is inferred from the title, and two say plainly that extraction
failed. The three that describe a different document read as confident,
sourced descriptions, and are live on the site now.

## 1. Which works have no PDF

116 live works carry no `pdf_url`. 110 of those are correct: 92 interviews and
18 lectures, which are video and audio and have no document to link.

That leaves six.

| Work | Type | Lang | Year | Cover |
|---|---|---|---|---|
| `khoj-july-august-2007` | periodical issue | gu | 2007 | none |
| `khoj-november-december-2008` | periodical issue | gu | 2008 | none |
| `khoj-may-august-2010` | periodical issue | gu | 2010 | none |
| `doan-pavlant-bali-patalat-by-anant-umrikar` | book | mr | 2016 | none |
| `shetakanyachi-raje-shivaji-by-sharad-joshi` | book | mr | 2016 | none |
| `yodha-shetkari-by-vijay-prulkar` | book | mr | 2016 | none |

All six also lack a cover image, which follows: the cover is rendered from the
first page of the PDF.

All six are live and reachable, at their language-prefixed addresses:
`/gu/primary-works/<slug>/` and `/mr/primary-works/<slug>/`.

## 2. Can the PDFs be found?

No, not from anything on our side. Four checks, all negative.

**The curator's drive never had them.** `data/corpus-inventory.json` records the
drive at `/Volumes/One Touch/Indian Liberals/PDFs-by-publisher` as holding 944
PDFs, of which **21 are Gujarati and 21 are Marathi**. The site links 21
Gujarati and 21 Marathi PDFs, exactly matching. The drive is fully accounted
for; there is no unlinked remainder for these six to be hiding in.

**They are already on record as unmatched.** All six appear in
`data/pdf-link-misses.tsv`, the list of markdown entries that could not be
matched to a file during the linking pass.

**The candidate matches are all the wrong work.** `data/local-backup-candidates.tsv`
proposes a nearest file for each, and every one is a different document:

| Record | Proposed file | Why it is wrong |
|---|---|---|
| `khoj-november-december-2008` | `khoj-november-december-2009` | a different year's issue |
| `khoj-july-august-2007` | `khoj-july-august-2006` | a different year's issue |
| `khoj-may-august-2010` | `khoj-july-august-2006` | a different year's issue |
| `doan-pavlant-bali-patalat` | `vedepir-anant-umrikar` | a different book, same author |
| `shetakanyachi-raje-shivaji` | `angarmala-sharad-joshi` | a different book |
| `yodha-shetkari` | `shetkari-sanghatak-april-6-1992` | a magazine issue, not the book |

Whoever ran that pass was right to decline all six.

**The archive has nothing under any plausible key.** Direct requests to
`archive.indianliberals.in` under the exact slug and the run's naming
convention return 404 for all six.

The external drive is not currently mounted, so the inventory file is the
authority on what it held. If CCS believes these were scanned, the drive is the
place to look; otherwise they need scanning.

## 3. What the summaries actually say

This is the part worth acting on.

### Written from a different document (3)

**`khoj-july-august-2007`** opens: *"This is the July-August 2006 issue of Khoj
(Year 2, Issue 3; serial number 9)"*. The record is the 2007 issue. The 2006
issue exists separately as `khoj-july-august-2006`, and it has a PDF.

**`khoj-may-august-2010`** opens by claiming the document was rendered, then
identifies it as *"Year 2, Issue 3 (Consecutive No. 9), dated July-August 2006"*.
The same 2006 issue again.

**`shetakanyachi-raje-shivaji-by-sharad-joshi`** describes *"one of four pieces
collected in Indrajit Bhalerao's 2010 volume Madhyatil Angar"*. That volume is
its own record, `madhyatil-angar-by-sharad-joshi`, and it has a PDF.

In each case the summary was written from a neighbouring file, presumably the
nearest match the pipeline could render. None of the three says so.

### Inferred from the title (1)

**`doan-pavlant-bali-patalat-by-anant-umrikar`** says the PDF *"could not be
located at extraction time"* and then reasons from the title: *"Based on the
title, which reads roughly as 'In two steps, Bali is crushed underfoot', and on
Umrikar's other titles in the same collection, the work appears to belong to..."*
followed by what works in that tradition *"typically"* argue.

It is careful prose about a book nobody opened. It is also marked
`needs_review: false`, so nothing flags it.

### Honest about the failure (2)

**`yodha-shetkari-by-vijay-prulkar`** records that the inventory path pointed at
a file which does not contain the work.

**`khoj-november-december-2008`** records that the source could not be read.

These two are fine as they stand. They say what happened.

## 4. Is this wider than the six?

Two scans across all 1,553 works that carry a substantial summary.

**Summaries sharing text with another work's summary:** 4 pairs above 35%
overlap.

- `balyo-bibaher-dosh` and `the-vice-of-child-marriages`: legitimate. Both point
  at the same bilingual PDF, one record per language.
- Two pairs of interview segments with the same speaker: legitimate overlap.
- `the-new-class-in-a-state-dominated-economy-by-mh-moody-1980` and
  `the-new-class-in-state-dominated-economy-m-h-mody-october-15-1981`: same
  title, same author, two records, two different PDFs. A likely duplicate
  record, and worth a look alongside the other duplicates found in the
  "Related across the archive" pass.

**Summaries that self-identify as a different document:** 2 hits. One is
`khoj-july-august-2007`, above. The other, `khoj-november-february-2006`, is a
false positive: it is genuinely a combined November 2005 to February 2006 issue.

So the summary problem is confined to the PDF-less works, plus one duplicate
record. By these tests the other 1,547 are clean.

## 5. Status: all six are hidden as of 2 August 2026

Hidden rather than rewritten, so the record on file is preserved exactly as it
is for whoever reviews it, and nothing was invented to replace it.

Each of the six carries `hide_from_index: true`, `needs_review: true`, and a
`hide_reason` naming this document. That means:

- gone from every listing and every count: the language shelves, primary works,
  the periodical runs, the home page figures, the navigation, thinker and
  organisation pages, and the agent-facing manifests
- gone from site search, and marked `noindex`
- the page still resolves, so nothing already linked or indexed breaks
- the page shows a short "not yet digitised" note instead of the summary, and
  the untrusted text is not in the HTML at all, including the meta description,
  the social cards and the structured-data abstract

Counts moved by exactly six: 1,575 works to 1,569, Marathi 78 to 75, Gujarati
24 to 21.

**To restore one:** delete its `hide_from_index` and `hide_reason` lines. That
is the whole operation.

## 6. Still open

1. **Ask CCS for the six scans.** Nothing else recovers them, and the entries
   stay hidden until the source exists.
2. **Re-extract each summary from its scan** when it arrives. Three of the six
   currently hold a description of a different document; that text should not
   be trusted even as a starting point.
3. Check the `"The New Class"` pair for duplication.
