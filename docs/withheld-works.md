# Withheld works

How a work is kept from readers and agents for a while without being removed
from the archive. Added 17 September 2026 for the 171 Swatantra-era records
CCS asked to hide temporarily (the list is in the commit that introduced this).

## The flag

`withheld: true` in a primary-work's frontmatter. Set it in the file, or in the
CMS ("Withhold from readers for now", on the work's edit screen). Unset it the
same way and the work is back on the next build. Nothing is deleted at any
point: the record stays in the repository, the PDF stays on R2, the OG card
stays where it is.

It sits beside two older flags with different meanings (`apps/site/src/lib/listable.ts`):

| flag | built | listed | counted | why |
|---|---|---|---|---|
| `draft` | no | no | no | not ready |
| `hide_from_index` | yes, normally | no | no | record not trusted (see missing-pdfs-and-bad-summaries.md) |
| `withheld` | yes, as a notice | no | **yes** | kept from readers for now, at CCS's request |

## What a withheld work looks like from outside

- **Its address still answers**, with a notice: "This document is temporarily
  unavailable." No title, no metadata, no summary, no PDF link. The notice is
  `noindex`, carries no search body (so the site's Pagefind index skips it),
  and is filtered out of the sitemap. Translations of a withheld work show the
  same notice.
- **It is in no list**: not on /primary-works/, not in its run on /periodicals/
  or /series/, not on a thinker's or organisation's page, not on the languages
  page, not in "Related across the archive".
- **Agents cannot read it**: no `.md` sibling (404), no `/api/works/<id>.json`
  (404), absent from `/api/works.json`, `/api/search-index.json`,
  `/api/cross-links.json` (as key and as target), `/llms.txt` and
  `/llms-full.txt`. The MCP server reads those endpoints, so it follows.
- **It still counts.** The homepage tiles, the menu counts, the periodicals
  page totals, a run's card ("171 issues"), `/api/meta.json` and `/AGENTS.md`
  all include withheld works. A run page whose items include withheld ones says
  so in one line ("3 issues are temporarily unavailable and not listed below").

## Finding them again

`/api/withheld.json` lists the ids and titles of everything currently withheld
(nothing else of the records). The CMS browse screen has a "Withheld for now"
tab built on it; open a work there and untick the box.

## Two things a rebuild does not do

- **The full-text `/search/` bundle.** `scripts/fulltext/export-works-meta.py`
  now excludes withheld works, but the bundle on R2 is only refreshed when the
  index is rebuilt and uploaded (`scripts/fulltext/README.md`). Until then a
  withheld work's page text can still match a query there; the result links to
  the notice.
- **Search engines.** The notice is `noindex`; Google drops the old listing
  when it next crawls the address.
