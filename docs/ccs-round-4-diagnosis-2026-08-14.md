# CCS round-4 feedback: what it means, and where we actually are

**Date of this report:** 14 August 2026
**Author:** Adnan (with Claude)
**Status:** Diagnosis only. Nothing in this document has been fixed. It exists so
that this session, a later session, or a colleague can pick up any of the five
items without re-doing the investigation.

Every claim below was checked against the live site at `indianliberals.in`, the
repository at `origin/main`, or both. Where a number appears, the command that
produced it is described so it can be re-run. Where CCS's description of a
symptom differs from what is actually happening, that is said plainly.

---

## 0. State of play before reading the five points

Three facts frame everything else.

**The local checkout is 118 commits behind `origin/main`.** All 118 are CMS
commits by Aayushi Tripathi at CCS, dated 6 to 14 August. Anyone working from
this repository must `git pull` first; the four broken records described in
section 2 do not exist locally.

**CCS editors are working daily and the pipeline is healthy.** Content check
and OG-card workflows pass on every push (`gh run list`), the Cloudflare Pages
deploy is current, and pages edited on 14 August are live the same day. The
six-day publishing outage of 30 July is not recurring. This matters because
three of CCS's five points read like "the website is broken" and none of them
is a deploy problem.

**Two of the five points are the direct consequence of one wrong click.** See
section 2. It is worth reading that section before section 1, because the
clutter CCS sees on the Periodicals page is partly the wreckage of the upload
attempt they describe separately.

---

## 1. Periodicals page and categorisation

### 1a. "The Periodicals page still feels quite cluttered"

The page is not one list. It is **two independent grouping systems stacked on
one URL**, and that is the structural cause of the clutter.

| | Upper half: "Booklet series, lectures & annual analyses" | Lower half: "Magazines & journals" |
|---|---|---|
| What decides membership | `publication.series_id` on each work, pointing at a record in the `series` content collection | `publication.publisher_id` / `issuer_id`, matched against a hard-coded table |
| Where the headings live | `apps/site/src/content/series/*.md` — **editable in the CMS** | `apps/site/src/lib/periodicals.ts` (`ORG_SERIES`, `SERIES_META`, `SERIES_ORDER`) — **code only** |
| Nesting | one level of `parent_series` | none |
| Currently | 599 works, 5 root runs, 9 sub-runs | 737 issues, 6 runs |

Headline figures on the live page: **1,336 works · 11 runs**. The archive holds
1,575 primary works, so **237 works appear under no heading on this page at
all** (they are neither periodical issues nor assigned to a series).

Two concrete symptoms of "not consistently placed under their respective
headings":

- **31 Forum of Free Enterprise / A. D. Shroff Memorial Trust works carry no
  `series_id`** and therefore appear nowhere on Periodicals. Nine of them
  literally print their run on the item — `publication.series` reads
  "A. D. Shroff Memorial Lecture, 1974", "A. D. Shroff Memorial Trust Lecture,
  1975", "A. D. Shroff Memorial Annual Public Lecture" — and still are not
  filed to the `ad-shroff-memorial-lecture` series. That field is descriptive
  text only; it groups nothing. The full list of 31 is reproducible with a scan
  of `apps/site/src/content/primary-works/` for works with no `series_id`, no
  `work_type: periodical_issue`, and a Forum/Shroff publisher.
- **176 works have no publisher recorded at all.** This is the same population
  flagged in the round-3 reply (then counted at 206 across a wider set). It is
  an editorial gap, not a display bug.

### 1b. "All Forum pieces should be consolidated under Forum of Free Enterprise only"

Confirmed and precisely located. The Forum currently renders as **one parent
card plus five sub-series cards**:

| Series record | Works | Years |
|---|---|---|
| `ffe-booklets` — Forum of Free Enterprise Booklets (parent) | 481 direct | 1956–2019 |
| `ad-shroff-memorial-lecture` | 49 | 1966–2016 |
| `ffe-union-budget` — The Union Budget | 45 | 1968–2018 |
| `bhogilal-leherchand-memorial-lecture` | 9 | 1998–2018 |
| `nani-palkhivala-memorial-lecture` | 2 | 2009–2011 |
| `builders-of-indian-economy` | 1 | 1990 |
| **Total shown on the card** | **587** | |

Plus the 31 unfiled Forum works from 1a, which is why the Forum's true footprint
is roughly 618 works, not 587.

The sub-series exist because each is a genuinely distinct run with its own
identity, and the nesting was deliberate (`parent_series` in
`apps/site/src/lib/series.ts`). CCS is asking us to collapse that distinction on
the index page.

**Decision required.** "Consolidated under Forum of Free Enterprise only" has
two readings, and they are not the same amount of work:

1. *Presentation only* — one card on the Periodicals index; the five runs
   survive as sections inside `/series/ffe-booklets/`, and their own URLs keep
   resolving. Low risk, nothing is lost, no content edits.
2. *Structural* — re-point all 106 sub-series works at `ffe-booklets` and
   retire the five records. This throws away the ability to browse the Shroff
   lectures as a run, and 49 Shroff lectures are the archive's single most
   coherent lecture series.

Recommendation to put to CCS: option 1, plus filing the 31 orphans, which is
what actually makes the Forum look consistent.

### 1c. "Two separate sections: Swatantra Party and Indian Liberal Group"

Neither exists on the Periodicals page today.

**Swatantra Party** — `/periodicals/swatantra-party/` returns 404 and no series
record exists. The material does: an organisation page at
`/organisations/swatantra-party/` (live, 200) and roughly a dozen party
publications in the archive, including the Election Manifesto 1967, the
Statement of Principles (Aug 1959), *Why Swatantra*, *What the Swatantra Party
Stands For*, *Real Land Reforms*, *The Budget versus the People*, *Devaluation:
the Guilty Men*, *Garibi Hatao the Swatantra Way*, *Swatantra Alternative to the
Third Plan*, *National Priorities for 1970*, *Lawless Legislation*, *From
Darkness to Light*, and the Sixth National Convention souvenir. Only **two** of
these carry `publisher_id: swatantra-party`; none carries a `series_id`.

**Indian Liberal Group** — 13 works, currently split across three places:
- 4 under the `ilg-liberal-budget` series ("The Liberal Budget", upper half);
- 2 as periodical issues under "The Liberal Position" newsletter (lower half,
  at `/periodicals/indian-liberal-group/`, which does resolve);
- 7 filed nowhere (Basic Principles 2000, Constitution 2000, Manifesto 1985,
  the Second National Convention report 2005, Trends in Government Expenditure
  2007, Union Budget 2002-03, *We Indians*).

Worth knowing where the request probably comes from: the legacy WordPress
redirect map (`apps/site/functions/_legacy/map.json`) has `swatantra-party` and
`indian-liberal-group` as top-level slugs, both now pointing at
`/organisations/…`. On the old site these were browsable category pages. **The
Organisations section was removed from the site navigation at CCS's own request
in round 3** — the pages still resolve, but nothing links to them. So CCS has
lost the doorway they used to have, and are asking for it back under a different
heading. That is worth saying to them explicitly, because reinstating
Organisations in the nav may be a cleaner answer than inventing two more
"series".

### 1d. "CCS Viewpoints should be renamed to CCS Publications"

The record is `apps/site/src/content/series/ccs-viewpoint.md`, `name: CCS
Viewpoint` (singular, as printed on the pamphlets). It holds 3 works.

Renaming is a **one-field CMS edit** that CCS can do themselves — Edit → Series
→ CCS Viewpoint → Name. Two things it will not change, and one caution:

- the URL stays `/series/ccs-viewpoint/`, which is correct: changing the file
  name breaks every existing link and the legacy redirect map;
- the phrase "CCS Viewpoint" also appears inside two work summaries and in the
  Sauvik Chakraverti biography, as the run's printed name on those items. Those
  are quotations of the imprint and should probably stay;
- **the blurb is now wrong for the new name.** It describes "a numbered run of
  short argumentative pamphlets". "CCS Publications" implies something wider.
  CCS should supply replacement wording, or the rename produces a heading that
  contradicts its own description.

---

## 2. Uploading books — what went wrong, exactly

This is the most important section. CCS's four sub-complaints are symptoms of a
single mistaken step, plus two real defects on our side.

### 2a. What actually happened

On 13 August, five book PDFs were uploaded through the CMS. All five reached
Cloudflare R2 successfully (all return HTTP 200 at
`archive.indianliberals.in/liberals/<slug>.pdf`). What was written into the site
differs:

| PDF | What was created | Result |
|---|---|---|
| `friedman-on-india` | a **Series** record named "Ccs Viewpoint " | empty box, 0 works |
| `book-after-the-welfare-state` | a **Series** record named "CCS Viewpoint " | empty box, 0 works |
| `indian-legacy-of-freedom-web-version-0` | a **Series** record named "CCS Viewpoint " | empty box, 0 works |
| `what-does-it-mean-to-be-a-liberal-in-india` | a **Series** record named "CCS Publication" | empty box, 0 works |
| `liberalism-in-india-2` | a **Primary work** | live, but wrong (2c, 2d) |

The four series records are commits `6c451130`, `087914e3`, `fb96d217`,
`7a6c906c`. Each carries `parent_series: ccs-viewpoint`, an identical
machine-written blurb, and a `pdf_url` field that the `series` schema does not
have (Zod silently discards it, which is why nothing failed loudly).

**Consequence: four of the five books are not in the archive.** Their PDFs sit
on R2 unreferenced. There is no work page, no summary, no cover, no search
entry. What CCS sees instead is four empty headings on the Periodicals page,
live and already in `sitemap-0.xml`:

> CCS Publication — 0 works · Ccs Viewpoint — 0 works · CCS Viewpoint — 0 works · CCS Viewpoint — 0 works

That is precisely their sentence: *"the system created separate boxes/categories
under CCS Viewpoints, which is not what we intended."*

### 2b. Why it happened — the correct workflow, and the trap

Step 1 of **Add many documents at once** (`/batch`) asks "What are these" and
offers all seven collections as equal-looking buttons, including **Series**. The
last one reads:

> **Series** — A named run of printed items that is not a magazine: a
> publisher's booklet run, an annual memorial lecture, or a numbered set of
> papers.

For someone uploading a folder of CCS booklets, that description reads like a
plausible answer. It is not: **Series describes a shelf, not a book.** Every
file in the batch then became one shelf. The AI pass, handed a CCS PDF and asked
to describe a *series*, dutifully answered "CCS Viewpoint" with a CCS blurb —
four times, which is why all four are near-identical.

The correct workflow, to send back to CCS:

1. **Books and pamphlets are always "Primary work."** Never "Series". Series is
   only for creating a new *run heading*, and only once per run.
2. Batch upload shelves everything as a draft at `/drafts`; nothing is public
   until it is published from there. This is the checkpoint where four empty
   shelves should have been caught.
3. To put a book inside an existing run, edit the work and set **Publication
   details → Part of the series**.

Two defects on our side that this exposed, both worth fixing regardless of what
CCS does:

- `batch.astro` stamps `data.pdf_url = item.pdfUrl` onto **every** collection,
  including ones with no such field. A batch of "Series" should refuse the file
  outright rather than write a record it cannot describe.
- Nothing warns that a batch of N files is about to create N series records. A
  batch of Series is almost always a mistake.

### 2c. "I could not find an option to select the featured image/cover image"

Confirmed, and the cause is a defensible design decision that has become a trap.

`cover_image` (primary works) and `hero_image` (opinions, musings) are real,
working, drag-and-drop image fields. But they are assigned to the field group
`files`, and `apps/cms/src/lib/groups.ts` renders every group except
`essential` as a **collapsed `<details>` drawer** — this one labelled *"Files,
pictures and rights"*. So on the Add form an editor sees Title, Kind of work,
Authors, Year, Language, PDF file and Summary, and no cover field at all unless
they open the fourth drawer.

On the **batch** screen there is no form at all — steps 1 to 4 are file
selection and progress. There is nowhere to choose a cover by design.

The intended behaviour is that the cover captures itself: on PDF upload the CMS
renders page 1 in the browser and writes it to `cover_image`. That did not
happen for `liberalism-in-india-2` — the record has no `cover_image` and
the live page shows no picture. The capture is fire-and-forget after the upload
completes (`add.astro` ~line 1214), so it is lost if it fails or if the editor
moves on before it lands.

**Answer to their question "can images be changed or uploaded directly through
the backend": yes.** Any entry can be opened in the CMS and a picture dropped
onto its image field. The field is simply buried. Promoting cover/hero to the
`essential` group would resolve the complaint on its own.

### 2d. "The author's name is also not displaying correctly"

Confirmed, with a precise and slightly embarrassing cause.

`/primary-works/liberalism-in-india-2/` displays **"By Jayaprakash Narayan"**.
The book is *Liberalism in India: Past, Present and Future*, the S. V. Raju
festschrift, **edited by Parth J Shah**, with seventeen contributors. Jayaprakash
Narayan wrote one essay.

Why: the record has **no `authors` field**. When `authors` is empty,
`PrimaryWorkDetail.astro` falls back to contributors whose role is `author` —
and the test is `c.role === "author"`, **case-sensitive**. The AI wrote:

```yaml
- thinker: hindol-sengupta     role: Author
- thinker: gurcharan-das       role: Author
- thinker: ashok-desai         role: Author
- thinker: jayaprakash-narayan role: author   ← the only lowercase one
- thinker: ms-seetha           role: Author
- thinker: nadir-godrej        role: Author
```

One lowercase "a" out of six decides the byline of the book. Fixing the
comparison is a one-line change; the record also needs `authors` or `editors`
promoted properly.

**A second, different author bug** (CCS raise it under Musings in 2e, but it is
the same complaint): the `author` field on **musings** is a reference to the
**thinkers** collection only. Present-day writers live in **contributors**. The
CMS renders references as a free-text input with a `<datalist>` suggestion list,
so anything can be typed. Someone typed `Avanti lele` into
`lokmanya-tilak-a-conservative-liberal.md`. There is no thinker with that id —
Avanti Lele is a *contributor* — so `getEntry()` returns nothing and **the
byline silently disappears**. No error, no warning, no build failure. The
correct name was entered and the page shows no author at all.

### 2e. "Several pieces under Musings are actually Opinion Pieces"

Confirmed, and the population is identifiable and small.

**Twelve musings**, published weekly between 23 August and 15 November 2023,
each ending in a legacy author photograph and a present-day biography note, are
modern essays by two CCS writers — **Ch Prashanth** and **Avanti Lele**. Each is
credited in the `author` field to **the dead person the essay is about**:

| Piece | Credited to | Actually written by |
|---|---|---|
| Dr Muthulakshmi Reddi: Beacon of Women's Liberty | muthulakshmi-reddi | Ch Prashanth |
| Gurcharan Das: Champion of Liberal Ideals | gurcharan-das | Ch Prashanth |
| Fighting for Freedom: The Tumultuous Legacy of Raghunath Karve | raghunath-karve | Avanti Lele |
| Gurajada Apparao: Liberal and Feminist Insights in Kanyasulkam | gurajada-apparao | Ch Prashanth |
| The Forgotten Legacy of Yashodabai Agarkar | yashodabai-agarkar | Avanti Lele |
| Gopal Ganesh Agarkar and the Vindication of Women's Education | gopal-ganesh-agarkar | Avanti Lele |
| Lokmanya Tilak: A Conservative Liberal? | *(already corrected)* | Avanti Lele |
| भारतातील उदारमतवादाचे पुरस्कर्ते गोपाळ कृष्ण गोखले | gopal-krishna-gokhale | Avanti Lele |
| Two Strands of Liberal Expression: Anandibai Joshi and Lakshmibai Tilak | lakshmibai-tilak | Avanti Lele |
| Kandukuri Veeresalingam: Icon of Andhra's Renaissance | kandukuri-veeresalingam | Ch Prashanth |
| Tanguturi Prakasam Panthulu: A Visionary Leader and Pioneer of Press Freedom | tanguturi-prakasam | Ch Prashanth |
| Acharya N G Ranga: The Farmer's Friend and Swatantra Party Stalwart | n-g-ranga | Ch Prashanth |

These are Opinion pieces by every test the schema applies: a named present-day
writer with a contributor record, a subject who is someone else, a bio note, and
a reference list. Their titles are indistinguishable in style from live Opinions
("The Resolute Abala Bose", "Forgotten Feminist, Educator: Fatima Sheikh"). One
subject, Rukhmabai, appears **twice** — once as a musing and once as an opinion.

CCS is already fixing these by hand: Aayushi created the `avanti-lele`
contributor record on 30 July and has been editing exactly these files on 12–14
August. She has hit the wall described next.

**Answer to "can content be moved from one section to another": not today.**
The CMS API writes files; it has **no delete, no rename and no move**
(`apps/cms/src/pages/api/save.ts`). Moving a musing to Opinions by hand means
creating a new opinion, leaving the musing behind, and being unable to remove
it — only to tick "Keep as a draft". The same limitation is why the four empty
series boxes cannot be deleted from the CMS either.

This is a real gap and probably the single highest-value CMS change: a "move to
another section" action, plus the ability to retire a record.

**Also found while checking these:** `bhartaateel-udaarmatavadache-puraskrute-gopal-krishna-gokhale.md`
still carries a leftover WPML marker `{:en}` at the start of its title, which
renders literally. It is the only file in the archive that does.

### 2f. One more defect in the same record

`liberalism-in-india-2`'s `summary` field begins:

```
Liberalism](https://archive.indianliberals.in/liberals/liberalism-in-india-2.pdf%22,%22summary%22:%22Liberalism) in India Past, Present and Future is …
```

A fragment of the model's own JSON leaked into the field. That string is the
page's `<meta name="description">` and `og:description` — it is what Google and
every social preview show. The visible summary on the page is fine; only the
metadata is corrupted. Also: the title is stored in block capitals, and the
publisher reads "centre for civil society" in lower case.

---

## 3. Featured images cropped on the individual article page (their point 7.2)

CCS's description is accurate and their diagnosis is close but not quite right.

**What they see.** Listing cards look right; opening a piece crops the picture.

**What is actually happening.** Both surfaces use `object-cover` with a maximum
height. The difference is column width, and it is decisive.

Measured live on `/opinions/forgotten-feminist-fatima-sheikh/`:

| | Listing card | Article page |
|---|---|---|
| Column width | 408 px | 720 px |
| Height cap | `max-h-[30rem]` = 480 px | `max-h-[30rem]` = 480 px |
| Image natural size | 192 × 306 | 192 × 306 |
| Height it wants | 650 px | 1,147 px |
| Visible | **74 %** | **42 %** |

The image is scaled to fill the wider column, so a portrait overflows the same
480 px cap almost three times over. On the article page the subject's head is
cut off at the chin.

Two contributing faults in `OpinionDetail.astro` (lines 164–176) and
`MusingDetail.astro` (lines 144–157):

1. `object-cover` combined with `max-h-[30rem]` / `max-h-[28rem]` — the crop
   itself;
2. hard-coded `width="1024" height="576"` regardless of the real file. The
   listing pages call `imageSize()` (`apps/site/src/lib/image-size.ts`) to read
   each file's true dimensions; the detail components do not. This does not
   cause the crop — the intrinsic ratio wins once the image loads — but it makes
   the page jump as it loads, and it is why the two surfaces behave differently
   for no stated reason.

**Scale of the problem, measured across every cover file:**

- **30 of 59 opinion covers are cropped on the article page**; 27 lose more than
  5 % of their height; the worst loses 58 %.
- **14 of 68 musing hero images** lose more than 5 % on the musing page.
- Nothing wider than 3:2 is affected at all, which is why it looks fine on the
  pieces CCS happened to check first.

This is a small, contained change: use the real dimensions and stop cropping.
Worth confirming with CCS that a very tall portrait may then occupy most of the
first screen, since the height cap was there for a reason.

---

## 4. A feedback box for users

Nothing exists. `/contact/` is live and in the navigation but renders the
"Coming Soon" placeholder (`ComingSoon.astro`); so do `/gallery/` and
`/testimonials/`. There is no form anywhere on the site apart from search. This
was already listed as outstanding in the round-3 reply (item 10) and has not
been started.

CCS asked what options are possible. The relevant constraints, so that
conversation starts from facts:

- the site is **static** on Cloudflare Pages, so a form needs a server endpoint;
- one already exists in the right place — `apps/site/functions/` runs Pages
  Functions on the same domain, which is how the legacy redirects work;
- the CMS already authenticates against **Firestore**, so submissions could land
  in the same database the editors already sign in to, and be read inside the
  CMS rather than by email;
- spam is the only hard part on a public archive, and it is the thing to decide
  before building: an emailed inbox, a moderated queue in the CMS, or a
  third-party form service are three genuinely different products.

Two questions to put back to CCS before any of this is built: **where should
submissions go** (an inbox, or a screen in the CMS), and **is this "contact us"
or "comment on this page"** — they wrote "submit their responses or feedback",
which could mean either, and they are not the same feature.

---

## 5. Filters on Thinker pages

Confirmed exactly as described, and the component is shared, so the fix has a
wider reach than CCS realises.

The block is `apps/site/src/components/WorksExplorer.astro`, used by **both**
`ThinkerDetail.astro` and `OrganisationDetail.astro`. It renders four rows of
filter chips — Type, Decade, Language, Theme (up to 12) — **always expanded, at
every viewport, with no toggle of any kind**. It appears whenever a person has
more than six works.

Measured live:

| Page | Works | Chips | Height before the first work |
|---|---|---|---|
| `/thinkers/minoo-masani/` | 65 | **27** | 262 px |
| `/thinkers/nani-palkhivala/` | 49 | 23 | 224 px |

Worst cases across the archive are around 29 chips. On a phone those four rows
wrap into a full screen of controls before any work is visible.

**The pattern CCS wants already exists elsewhere** — `opinions/index.astro`
lines 129–141 have a "Filter" button showing the count of active filters, with
the panel collapsed by default. But it is `md:hidden`: **phone only**. On desktop
those filters are a permanently visible sidebar.

So there are two gaps, and one needs a decision:

1. `WorksExplorer` has no toggle at all. Adding one is straightforward and can
   reuse the Opinions script almost verbatim.
2. CCS asked for hidden-by-default **"consistently on both desktop and mobile"**,
   which the existing Opinions/Musings pattern does *not* do. Their point 5 names
   Thinker pages only. **Ask them whether Opinions and Musings should change to
   match**, or whether thinker pages are deliberately different.

Note that the fix automatically applies to all 106 organisation pages too, since
they share the component. That is desirable, but it should be said rather than
discovered.

---

## Summary of what needs a decision from CCS

| # | Question | Blocks |
|---|---|---|
| 1 | Consolidate the Forum *on the index only*, or dissolve the five sub-series entirely? | 1b |
| 2 | Should Swatantra Party and Indian Liberal Group be new run headings, or should the Organisations section simply return to the navigation? | 1c |
| 3 | New blurb wording for "CCS Publications" — the current one describes a pamphlet run | 1d |
| 4 | Confirm the four uploaded books should be re-created as Primary works, and the four empty series boxes retired | 2a |
| 5 | Is the feedback box "contact us" or "comment on this page", and where should submissions land? | 4 |
| 6 | Should Opinions and Musings also hide their filters by default on desktop, or only Thinker pages? | 5 |

## Summary of what needs no decision — defects to fix

| # | Fix | Where |
|---|---|---|
| A | Case-insensitive author-role match; `liberalism-in-india-2` byline | `PrimaryWorkDetail.astro`, and the record |
| B | Corrupted `summary` / meta description on `liberalism-in-india-2` | the record |
| C | Stop cropping hero images on article pages; use real dimensions | `OpinionDetail.astro`, `MusingDetail.astro` |
| D | Collapse the thinker/organisation filters behind a "Filters" control | `WorksExplorer.astro` |
| E | Move cover/hero image fields out of the collapsed drawer into the essentials | `apps/cms/src/lib/collections.ts` |
| F | Warn or refuse when a *batch* is filed as "Series"; stop stamping `pdf_url` on collections that have no such field | `apps/cms/src/pages/batch.astro` |
| G | Give the CMS a "move to another section" action and a way to retire a record | `apps/cms/src/pages/api/save.ts` and the edit screen |
| H | File the 31 orphan Forum / Shroff works to their series | content |
| I | Re-file the 12 mis-classified musings as opinions, crediting Ch Prashanth and Avanti Lele | content (blocked on G) |
| J | Reject an author reference that matches no record, instead of dropping the byline silently | `MusingDetail.astro` / content check |
| K | Strip the `{:en}` WPML marker from the Gokhale musing title | content |

---

## Evidence appendix — how each figure was obtained

- **Live page text and measurements** — browser at `indianliberals.in`;
  `getBoundingClientRect()` and `getComputedStyle()` for the image and filter
  measurements quoted in sections 3 and 5.
- **Commit provenance** — `git log --format='%h %ad %an %s' HEAD..origin/main`;
  the four series records are `6c451130`, `087914e3`, `fb96d217`, `7a6c906c`.
- **Record contents** — read from `origin/main` with `git show`, not from the
  local checkout, which is 118 commits behind.
- **Counts of works, publishers, series membership** — Python scans over the
  frontmatter of `apps/site/src/content/primary-works/*.md` (1,575 files).
- **Image dimensions** — PNG/JPEG/WebP headers parsed directly from
  `apps/site/public/opinions/covers/` (59 files) and
  `apps/site/public/musings/` (68 files), then compared against the measured
  720 px column and the 480 px / 448 px caps.
- **CI health** — `gh run list`.
- **URL status codes** — `curl -o /dev/null -w '%{http_code}'`.
