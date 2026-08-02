---
title: "Indian Liberals: round-3 feedback"
---

Dear Arjun,

Thanks for the list. Most of it is straightforward. Ahead of tomorrow, here is
one finding that affects three of your points, then what is done, what I need
from you, and what is outstanding.

# Three of your points were the same bug

Removing M. N. Roy, point 8 about backend changes not appearing, and point 9
about ThePrint not updating all come from one fault.

On 30 July a CMS save wrote the `vocations` field on the M. N. Roy entry as text
where the site expects a list. The site builds as static pages, so one invalid
file fails the whole build and Cloudflare stops publishing. The previous version
stays up and looks fine. Cloudflare's log shows seven production builds failing
in a row, 30 July to this afternoon.

So:

- Aayushi had already removed M. N. Roy, on 31 July. The change was correct and
  never reached the site. He is off the list now.
- Point 8 is not caching. Nothing published at all for six days.
- Point 9 is not the integration. The ThePrint import ran on schedule and picked
  up two pieces on 1 August, which sat in the repository unpublished.

The entry is repaired and your edits to it are intact. The CMS is fixed as well,
which matters more, since 448 files could have hit the same fault on any save.
There is now a check on every change that fails visibly, so a broken file cannot
stop publishing quietly.

# The numbers

We went through all of them. None is miscounted. Every figure is counted from
the content at build time.

| Shown as | What it counts | Value |
|---|---|---|
| Primary works | every primary work that is not a draft | 1,575 |
| Periodical issues | of those, the ones marked as a periodical issue | 740 |
| Interviews | of those, the ones marked as an interview | 92 |
| Thinkers profiled | every thinker classified as core or extended in the tradition | 194 |
| Excerpts and opinions | every musing plus every opinion | 254 |

What is off is that three of the tiles link to a page counting something else:

- Thinkers profiled, 194, opens a page listing 23. The tile counts everyone
  classified as part of the tradition; the page shows only the curated canon.
  The other 171 are in the archive and reachable, just not on that page.
- Excerpts and opinions, 254, opens Opinions, which has 55.
- Periodical issues, 740, opens a page that also counts the Forum booklets.

Worth deciding which number you want a reader to land on. I would point each
tile at the page holding what it counts, but tell me.

Total pages: 22,715 across 1,423 works. 110 works have no pages, being video. 42
paginated works have no count recorded. We can say "over 22,000", or spend a day
counting the PDFs exactly.

Separately, the old essay contest page says the archive "presently hosts up to
50,000 digitized pages". I cannot reconcile that with anything measurable. If
that figure has been used publicly I would like to know where it came from.

# Two corrections

**Featured images, 7.2.** You are right that they display badly. The cause is not
the ratio. The 59 covers recovered from the Wayback Machine measure 24
landscape, 20 wide, 8 square and 7 portrait, ranging from 192 by 306 to 1024 by
329. A 3:4 box would have cropped the 44 landscape and wide ones harder than
what was there. The problem is a single fixed ratio applied to a set that varies
that much, so covers now keep their own proportions. Done and live.

**Periodicals, 3.1.** Renamed. Most of that page is not periodicals though: the
roughly 600 Forum booklets, the budget analyses and the memorial lectures are
all there, which is what the old name covered. Flagging it, and easy to change
back.

# Live now

- M. N. Roy removed from the Thinkers list.
- Thinkers listed alphabetically.
- Organisations hidden from the navigation. Nothing deleted, and all 106
  organisation pages still resolve.
- About: contributors section renamed to "People who helped in building this
  Archive" and moved above "What You'll Find Here".
- "Series and Periodicals" renamed to "Periodicals", and "The runs" removed.
- Opinions page titled "Opinions".
- The repeated article in "Related across the archive" is fixed, across 76
  entries and 88 duplicate links.
- Count-up animation on the home page figures.
- A larger search bar.
- Featured images keeping their own shape, as above.
- Events as its own section, with the annual lecture, the essay contest, its
  results and the Vaad Vivad on decentralisation moved out of Opinions. Their
  pages keep their existing addresses, so nothing already linked or indexed
  breaks.
- Languages, covering Marathi (78 works), Gujarati (24), Hindi (5) and Bengali
  (2), each with its own page.
- Sort and filter on mobile. Sort is new on both Opinions and Musings, newest or
  oldest first. On a phone the filters sit behind one control showing how many
  are active. Desktop is unchanged.

Two notes. I added Gujarati to Languages alongside the three you named, since
there is more Gujarati in the archive than Hindi and Bengali combined. And
Languages as a filter on Opinions and Musings would have had one option, both
being entirely English, so it sits on the works instead.

# What I need from you

1. The revised copy for the Home page, About page and Thinkers description.
2. The black and white image of Raja Ram Mohan Roy.
3. Which numbers you thought were wrong, against the table above.
4. Whether the page count says "over 22,000" now or waits for an exact count,
   and where 50,000 came from.
5. Which interview pages are filed under the person being discussed rather than
   the person speaking. There are 92 and I cannot tell from outside which are
   wrong.
6. Whether Periodicals keeps that name.

# Outstanding

**Collections by publication house (3.3).** 23 publishers, not hundreds. Forum of
Free Enterprise 577 works, Freedom First 500, The Indian Libertarian 138,
Shetkari Sanghatana 48, which is 92% of everything attributed. Two open
questions: 206 works have no publisher recorded, and eight publishers have a
single work each. Both need a decision on where they sit.

**Oral Histories (3.7).** Most of the structure exists. The section already groups
by figure and has shelves for talks, explainers and conversations. The problem is
underneath: of 92 interviews only 27 carry an explicit group, and the other 65
are sorted by reading the filename. Four browsable sub-sections need that fixed
first. I would propose a group for each of the 65 and send you the list to
correct. The same pass covers the misfiled interviews once you send them.

**Interviews on thinker pages (5.1).** The mention data exists. The question is
the threshold: Zareen Masani on Minoo Masani belongs there, a passing mention
does not. I will draft a rule and show you what it catches before it goes live.

**Musings authors (6.2).** 98 of the 195 have no author, and none has a link back
to a source work, so there is no field to derive it from. 74 of the 98 name the
source in their own text. I would extract those and send them for approval
rather than publish them unchecked. The other 24 need the original WordPress
posts or someone at CCS who remembers.

**Home page separation (2.2).** Not started. Easier to show than to describe, so I
will bring a few versions.

**Contact, feedback form, Gallery, Testimonials (10).** Nothing built yet. Contact
and the form are small. For the Gallery I need to know what the photographs are
and roughly how many. For Testimonials, how many you have and what form they
take.

**Section 12.** Agreed, and it is the part I would most like to get right. The
descriptive standfirsts exist so search engines and AI agents can parse the
archive; they have leaked into the reading. Better as one pass than scattered
edits. Tell me which pages matter most and I will start there. Your new copy for
Home, About and Thinkers is the obvious beginning.

See you tomorrow.

Best,
Adnan
