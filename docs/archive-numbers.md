# Every number on the site, and exactly how it is worked out

CCS asked us to "review and correct some of the existing numbers, as a few
appear to be inaccurate" (round-3 feedback, 2.1b).

Nothing on the site is typed in by hand. Every figure is counted from the
content at build time, so no number can drift from what the archive holds. We
have gone through all of them. **None of them is miscounted.** What is wrong is
something else, and it is worth naming precisely, because it is the thing that
makes them look wrong.

Values below are as of 2 August 2026.

## The "Archive at a glance" band

| Shown as | The exact rule | Value |
|---|---|---|
| Primary works | every `primary-works` entry with `draft: false` | **1,575** |
| Periodical issues | the same set, where `work_type == "periodical_issue"` | **740** |
| Interviews | the same set, where `work_type == "interview"` | **92** |
| Thinkers profiled | every `thinkers` entry with `draft: false` whose `canon_status` is `core` or `extended` | **194** |
| Excerpts & opinions | every `musings` entry plus every `opinions` entry, both with `draft: false` | **195 + 59 = 254** |

The Organisations tile (52) has been removed while that section is hidden.

## The real problem: three tiles lead somewhere that counts something else

Each tile is a link. Three of them land on a page showing a different number,
and neither number is wrong. That is what makes the band feel unreliable.

| Tile | Says | The page it opens shows | Why they differ |
|---|---|---|---|
| Thinkers profiled | **194** | **23** | The tile counts every thinker classified as part of the tradition. The page shows only the curated canon: `featured: true` and Indian. The other 171 are real records, reachable by search and by their own pages, just not listed on that page. |
| Excerpts & opinions | **254** | **59** | The tile adds musings to opinions. The link goes to Opinions alone. |
| Periodical issues | **740** | 740 issues, but the page header counts issues **plus** the booklet series works | The tile counts dated issues. The page covers every named run, including the roughly 600 Forum of Free Enterprise booklets, which are not periodical issues. |

Three ways to settle this, for CCS to choose:

1. **Point each tile at what it counts.** Thinkers profiled goes to the full
   directory rather than the canon page; Excerpts & opinions splits into two
   tiles, or links to musings.
2. **Count what the destination shows.** "Thinkers profiled" becomes 23. This
   makes the archive look far smaller than it is.
3. **Say what is being counted** in the label, so 194 and 23 are visibly two
   different true statements.

Our recommendation is (1). The numbers are the honest scale of the archive, and
the fix is to send the reader to the page that holds them.

## Total pages, the number CCS asked us to add (2.1a)

There is a real number available, with one caveat worth stating before it goes
on the home page.

- **22,715 pages**, across **1,423 works**.
- **110 works have no pages at all**: 92 interviews and 18 lectures, which are
  video and audio.
- **42 paginated works have no page count recorded**: 21 periodical issues,
  20 books, 1 pamphlet. Their pages exist; the figure was never captured.

So "22,715" is an undercount by roughly the size of those 42 works, likely a few
hundred pages. Two options: publish "over 22,000 pages", which is true today and
stays true; or run a pass over the PDFs on the archive server to get an exact
count first. The second takes a day and gives a number that can be stated flatly.

The field being summed is `physical.pages_rendered`, which records the pages
processed when each work was ingested. For a scanned PDF that is the whole
document. It is not a hand-checked page count, and we would rather say that now
than be asked later.

## Where the numbers are counted

- The band itself: `apps/site/src/pages/index.astro`, the `stats` array.
- Thinkers page population: `apps/site/src/pages/thinkers/index.astro`.
- Navigation counts: `apps/site/src/components/Header.astro`.

All three read the content collections directly. Changing a rule means changing
one line in one of those files; the number then follows the content forever
after.
