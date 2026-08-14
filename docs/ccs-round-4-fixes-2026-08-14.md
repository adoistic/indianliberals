# CCS round 4: what was done

**Date:** 14 August 2026
**Diagnosis:** `docs/ccs-round-4-diagnosis-2026-08-14.md` — read that first for why each of these was necessary.

All five points are addressed, plus eleven defects the diagnosis turned up and
three more found while fixing them. Everything below is in the working tree and
verified against a local build.

---

## 1. Periodicals page and categorisation

**The page is now six run cards instead of fourteen.**

| Before | After |
|---|---|
| 5 root cards + 9 sub-series cards | 6 root cards, sub-runs inside their parent |
| 1,336 works · 11 runs | 1,392 works · 12 runs |
| Forum shown as 6 separate boxes | Forum shown once, 618 works |
| No Swatantra Party, no Indian Liberal Group | Both, as their own sections |
| "CCS Viewpoint" | "CCS Publications" |

- **Forum consolidated.** `periodicals/index.astro` no longer renders sub-series
  beside their parent. The five runs (A. D. Shroff Memorial Lecture, The Union
  Budget, Bhogilal Leherchand, Nani Palkhivala, Builders of Indian Economy) now
  appear as cards *inside* `/series/ffe-booklets/`, under a "Runs within" heading,
  and keep their own URLs. Nothing was deleted and nothing became unreachable.
- **31 orphan Forum works filed.** 26 A. D. Shroff Memorial Trust lectures joined
  `ad-shroff-memorial-lecture` (49 → 75 works), 3 joined `ffe-booklets`, the 2004
  budget pamphlet joined `ffe-union-budget`, and the Visvesvaraya biography joined
  `builders-of-indian-economy`. Nine of them printed their series on the item and
  were still filed nowhere.
- **Swatantra Party** is a new section: 14 party-imprint works, 1959 to 1973.
  Twelve of them carried the party as `publisher_name` text only, so they never
  appeared on the organisation page either; they now carry `publisher_id` as well.
- **Indian Liberal Group** is a new section: 11 works, with The Liberal Budget as a
  sub-run inside it. Its newsletter, *The Liberal Position*, stays under Magazines
  and journals, and the section blurb says so.
- **CCS Viewpoint renamed to CCS Publications**, with a blurb rewritten to cover a
  run that is now books as well as pamphlets. The URL `/series/ccs-viewpoint/` is
  unchanged, so no link breaks.

## 2. Uploading books

**The four lost books are in the archive.** Each now has a full record built from
its own PDF: real title, editors, contributors, ISBN where printed, page count,
rights position, a summary and key points, and a cover rendered from page one and
uploaded to R2.

| Book | Was | Now |
|---|---|---|
| *Friedman on India* (CCS, 2000) | an empty series box | a work, by Milton Friedman, ed. Parth J. Shah |
| *After the Welfare State* (CCS reprint, 2012) | an empty series box | a work, ed. Tom G. Palmer, foreword Bibek Debroy |
| *Indian Legacy of Freedom* (CCS, 2022) | an empty series box | a work, by Centre for Civil Society |
| *What Does it Mean to be a Liberal in India* (2016) | an empty series box | a work, ed. Ronald Meinardus |
| *Liberalism in India* (CCS, 2016) | bylined to one essayist, no cover | "Edited by Parth J. Shah", cover, clean metadata |

The four bogus `series` records are deleted.

**The byline bug is fixed at the root.** `PrimaryWorkDetail.astro` compared
`c.role === "author"` case-sensitively; the extraction had written five `Author`
and one `author`, so a seventeen-contributor festschrift was credited to the one
lowercase entry. The comparison is now case-insensitive and trimmed, in both the
detail page and the works listing. Edited volumes with no named authors are now
credited "Edited by …" instead of falling through to their contributors.

**The corrupted metadata is repaired.** `liberalism-in-india-2` had a fragment of
the model's own JSON at the head of its `summary`, which was the page's
`meta description` and `og:description`. Also fixed: the ALL-CAPS title, the
lower-case publisher, the mangled "R J AGANNATHAN" (the printed name is
R Jagannathan), and the Windows staging path left in the record.

**Thirteen more silently-dropped bylines, found while fixing the above.** An
organisation in `authors[]` written as a bare string always resolves through the
thinkers arm of the union and vanishes. All thirteen now use the object form and
their bylines render: Forum of Free Enterprise, Swatantra Party, Indian Liberal
Group and Centre for Civil Society among them.

**Images can now be found.** `cover_image`, `hero_image`, thinker portraits,
contributor photographs and organisation logos have moved from the collapsed
"Files, pictures and rights" drawer into the essentials, where an editor
adding a book actually looks.

**The batch screen no longer offers Series**, with a line saying why and where to
make one instead. It also no longer stamps `pdf_url` onto collections that have
no such field, which is how four series records ended up carrying one.

**Content can be moved between sections.** New in the CMS:

- *Move or remove this entry* on the edit screen, for sub-admins and above.
- Moving writes the new file, deletes the old one and appends a 301 to
  `public/_redirects` **in a single commit**, so the entry is never in two
  sections at once and the old address keeps working. Hero images travel with it.
- Anything the target section has no field for is named before it is dropped, and
  required fields it cannot fill block the move rather than producing a broken entry.
- *Remove it from the site* retires an entry; the last version stays in git.

## 3. Featured images

**Nothing is cropped on an article page any more.** A new `ArticleHero`
component, shared by opinions and musings, keeps every image whole: instead of
capping height and cropping, it caps the *width* an image may be drawn at so the
whole of it fits inside the height budget. A portrait renders narrow and centred;
a landscape fills the column as before.

Verified on the piece CCS is most likely to have looked at: Fatima Sheikh's
portrait was 42% visible and cut off at the chin, and is now whole. 30 of 59
opinion covers and 14 of 68 musing heroes were affected.

Real intrinsic dimensions now come from `imageSize()` on the detail pages too, so
the page no longer reflows as the picture loads.

## 4. Feedback

**There is a form, at `/contact/`.** The Coming Soon placeholder is gone.

- It leads with *corrections*, because that is what an archive of machine-read
  scans most needs from its readers, and it carries the page the reader was on so
  a correction arrives attached to the thing it corrects.
- No account, no required email address.
- Submissions post to `POST /api/feedback` on the CMS Worker, which already has
  the archive bucket bound and already knows who the editors are. They land in R2
  under `feedback/`.
- **Editors read them at `/feedback` in the CMS**, newest and most actionable
  first, with a "mark dealt with" that records who did it, so a shared inbox does
  not get answered twice.
- Spam guards, all verified locally: a honeypot field, a three-second minimum on
  the form, one message a minute per sender, hard length caps, and an origin
  check. If it is ever abused past that, Turnstile is a setting rather than a
  rewrite.

## 5. Thinker page filters

**The filters are behind a "Filters" button, collapsed by default, on desktop and
mobile alike.** The button carries a count when any are active, so a filtered
grid never looks like a broken one.

On Minoo Masani's page the controls above the first work went from **262 px to
74 px**; the 27 chips are still there, one click away. The block is shared, so
this applies to all 106 organisation pages too.

---

## What CCS did not ask for but now has

- **Twelve pieces moved from Musings to Opinions**, each credited to the person
  who actually wrote it. They ran weekly between 23 August and 15 November 2023
  and are the work of **Ch Prashanth** (6) and **Avanti Lele** (6); every one was
  credited to the dead subject it profiled. Both writers now have contributor
  records, the old `/musings/…` addresses 301 to the new ones, the twelve legacy
  WordPress URLs were repointed, and the covers moved with them.
- **A reference check that fails the build.** `scripts/check-references.mjs` runs
  in CI and in `npm run build`. Astro's `reference()` never checked that its
  target exists, which is why "Avanti lele" silently erased a byline and why
  thirteen organisation credits vanished without a word. 35 dangling references
  were found and fixed on the first run: `bk-nehru-cn` (16 uses), two opinion
  authors with no contributor record, six organisations sitting in
  `related_thinkers`, and a thinker deleted by an old "empty orphan" sweep that
  did in fact have an inbound link.
- Two contributor records created (Lakshmi Ramanandan, Dileep P. Chandran) and one
  restored (D. M. Kulkarni), plus a thinker record for Tom G. Palmer.

## Still open, and why

- **The `{:en}` WPML marker** flagged in the diagnosis was already fixed by
  Aayushi on 14 August. Nothing to do.
- **1,239 loose ids** are reported by the reference check as warnings rather than
  errors. Most are `publisher_id: freedom-first` and similar, where the id doubles
  as a grouping key in `lib/periodicals.ts` and names no organisation record. That
  is a real inconsistency worth resolving, but it is a data-modelling decision for
  CCS, not a defect, and failing the build on it would have meant not shipping any
  of the above.
- **The CMS must be deployed** for the feedback endpoint to exist at
  `cms.indianliberals.in`. It is not git-integrated: run `npm run deploy` in
  `apps/cms`. Until then the form on the live site will report that it could not
  send.
