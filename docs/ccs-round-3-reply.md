---
title: "Indian Liberals: round-3 feedback"
---

Dear Arjun,

Thank you for this. It is a good list, and most of it is straightforwardly
buildable. Before we meet I want to give you one finding that changes how three
of your items should be read, then what is already done and live, what I need
from you tomorrow, and what is left.

# Three of your items were one bug, and it is fixed

Your request to remove M. N. Roy, point 8 about backend changes not appearing,
and point 9 about ThePrint not updating are the same fault.

On 30 July a save from the CMS wrote one field on the M. N. Roy entry
incorrectly. The field `vocations` holds a list. It was written as a piece of
text that looks like a list. The site is built as static pages, so a single file
that fails validation fails the whole build and Cloudflare stops publishing. The
previously published site stays up and looks perfectly healthy, which is why
nobody saw it. Cloudflare's own record shows seven production builds in a row
failing, from 30 July until this afternoon.

What follows from that:

- **M. N. Roy had already been removed.** Aayushi made the change herself on 31
  July. It was correct and it is still in place. It simply could not reach the
  live site. He is off the Thinkers list now.
- **Point 8 is not caching.** Nothing published at all between 30 July and this
  afternoon. It was not slow, it was stopped.
- **Point 9 is not a broken integration.** The ThePrint import ran normally and
  on schedule, including on 1 August when it collected two new pieces. They were
  in the repository the whole time, unpublishable.

Three things have been done about it. The entry is repaired, and every editorial
change CCS made to it stands. The CMS itself is fixed, which matters more: 448
files in the archive were exposed to the same fault, and any one of them opened
and saved would have done the same thing. And a check now runs on every change
and fails loudly if a file breaks, so the site cannot freeze silently again.

That last part is the real lesson. The bug cost six days rather than ten minutes
because nothing was watching. I am sorry it took your email to surface it.

# The numbers are not wrong, and it is worth being exact about why

You asked us to correct figures that look inaccurate. We have been through every
one. **None of them is miscounted.** Nothing on the site is typed in by hand;
every figure is counted from the content each time the site builds.

Here is precisely what each counts, as of today:

| Shown as | What it counts | Value |
|---|---|---|
| Primary works | every primary work that is not a draft | 1,575 |
| Periodical issues | of those, the ones marked as a periodical issue | 740 |
| Interviews | of those, the ones marked as an interview | 92 |
| Thinkers profiled | every thinker classified as core or extended in the tradition | 194 |
| Excerpts and opinions | every musing plus every opinion | 254 |

The reason they feel wrong is real, though, and it is this: three of those tiles
are links, and they open a page showing a different number.

- **Thinkers profiled: 194** opens a page listing 23 people. Both are true. The
  tile counts everyone classified as part of the tradition; the page shows only
  the curated canon. The other 171 are real records, reachable by search and by
  their own pages, just not listed there.
- **Excerpts and opinions: 254** opens Opinions, which has 55.
- **Periodical issues: 740** opens a page that also counts the Forum of Free
  Enterprise booklets, which are not periodical issues.

So the question is not arithmetic. It is which number you want a reader to land
on. My recommendation is to point each tile at the page that holds what it
counts, rather than shrink the numbers, because 194 is the honest scale of the
archive and 23 is not.

**On the total page count you asked us to add:** the figure available today is
**22,715 pages across 1,423 works**. 110 works have no pages at all, being the
interviews and lectures, which are video. 42 paginated works have no count
recorded. So we can publish "over 22,000 pages", which is true today and stays
true, or spend a day counting the source PDFs exactly first.

One thing to settle, because it will come up. The old site's essay contest page
says the archive "presently hosts up to 50,000 digitized pages". That does not
match anything we can measure. If 50,000 is a number CCS has used publicly, I
would like to know where it came from before we print a different one.

# Two corrections worth making

**The featured images, point 7.2.** Your diagnosis is right: they display badly.
The stated cause is not, and it matters, because acting on it would have made
things worse.

The old site used a 3:4 portrait canvas. The images themselves are not portrait.
All 59 covers were recovered from the Wayback Machine, and they measure: 24
landscape, 20 wide, 8 square, 7 portrait. They run from 192 by 306 at one end to
1024 by 329 at the other. Putting that set behind a 3:4 box would have cropped
the 44 landscape and wide covers far harder than the boxes it replaced.

The fault was never which ratio. It was that one fixed ratio cannot serve a set
that varies five times over in shape. So no cover is forced into a box any more.
Each keeps its own proportions, with its true pixel size on the page so nothing
jumps as it loads. That is done and live, and I think it is what you were
actually asking for.

**Renaming to Periodicals, point 3.1.** Done. But most of what is on that page is
not a periodical: the roughly 600 Forum of Free Enterprise booklets, the annual
budget analyses and the memorial lectures all live there, which is what "Series
and Periodicals" was for. If a reader goes to Periodicals looking for the Forum
booklets, the name now works against them. Easy to revisit, and worth thirty
seconds tomorrow.

# What is done and live

- M. N. Roy removed from the Thinkers list.
- Thinkers listed alphabetically.
- Organisations hidden from the navigation. Nothing is deleted: all 106
  organisation pages still exist and still resolve.
- About: the contributors section renamed to "People who helped in building this
  Archive" and moved above "What You'll Find Here".
- "Series and Periodicals" renamed to "Periodicals", and "The runs" removed.
- Opinions page titled "Opinions".
- The repeated article in "Related across the archive" is fixed. It affected 76
  entries and 88 duplicate links.
- Count-up animation on the home page figures.
- The search bar is larger and reads as a search field rather than a menu item.
- **Featured images** now keep their own shape, as above.
- **Events** is a section of its own, with the annual lecture, the essay contest,
  its results, and the Vaad Vivad on decentralisation moved out of Opinions.
  Their pages keep their existing addresses so nothing already linked or indexed
  breaks; what changed is where they are listed.
- **Languages** is a new section. It covers Marathi (78 works), Gujarati (24),
  Hindi (5) and Bengali (2), each with its own page.
- **Mobile sort and filter.** Sort is new on both Opinions and Musings: newest to
  oldest, or oldest to newest. On a phone the filters are now behind a single
  "Filter" control that shows how many are active. On a desktop nothing changed.

Two notes on those last two. You asked for Hindi, Bengali and Marathi; I have
included **Gujarati** as well, because there is more Gujarati in the archive than
Hindi and Bengali put together and leaving it out would look odd. And you listed
Languages among the filters for Opinions and Musings: those two collections are
entirely in English, so a language filter there would have exactly one option. It
belongs on the works, which is where it now is.

# What I need from you tomorrow

Things I cannot start without you:

1. The revised copy for the Home page, About page and Thinkers description.
2. The black-and-white image of Raja Ram Mohan Roy.
3. Which numbers you felt were wrong, against the table above.
4. Whether the page count says "over 22,000" now or waits for an exact count, and
   where the 50,000 figure came from.
5. Which interview pages are filed under the person being discussed rather than
   the person speaking. I need you to name them; there are 92 and I cannot tell
   from the outside which are wrong.
6. Whether Periodicals keeps that name given what is actually on the page.

# What is left, and exactly where each one stands

## Grouping Collections by publication house (3.3)

**Where we are.** The data is better than I expected. Every work carries a
resolved publisher, and there are 23 publishing houses in the archive, not
hundreds. The shape is very top-heavy: Forum of Free Enterprise 577 works,
Freedom First 500, The Indian Libertarian 138, Shetkari Sanghatana 48. Those four
are 92% of everything attributed. Eight houses have ten or more works; eight have
exactly one.

**What needs a conversation.** Two things. **206 works have no publisher
recorded**, so we need to decide whether they sit in an "Other" shelf, stay in a
flat list alongside the houses, or get researched and attributed first. And the
eight houses with a single work: own section each, or folded into "Other"? A page
with four large sections and fifteen near-empty ones will read as broken.

**The idea.** Collections becomes a list of houses rather than a list of formats.
Freedom First opens onto everything Freedom First published, its magazine issues
and anything else, instead of those being scattered across "periodicals" and
"series" by cataloguing type. This is close to what you described and I think it
is right: the reader thinks in institutions, not in formats.

## Oral Histories with four sub-sections (3.7)

**Where we are.** Most of the structure exists. The section already groups
interviews by figure, and already has separate shelves for talks, explainers and
conversations, which maps almost exactly onto the four you listed. Renaming and
regrouping is a day.

**What needs a conversation.** The classification underneath is thin. Of the 92
interviews, only 27 carry an explicit group; **the other 65 are sorted by a rule
that reads their filename.** That works well enough for the current three
shelves, and it will not hold up under four named sub-sections that a reader is
invited to browse.

**The idea.** We propose a group for each of the 65 and send you the list to
correct, rather than either of us classifying 92 items from scratch. This is also
the natural moment to fix the interviews filed under the wrong person, since that
is the same pass over the same 92 records.

## Interviews and talks on a thinker's page (5.1)

**Where we are.** The archive already knows which thinkers a work mentions, and
the thinker pages already have a "mentioned in" area, so the plumbing exists.

**What needs a conversation.** What counts. Zareen Masani's interview about Minoo
Masani clearly belongs on Minoo Masani's page. A talk that mentions him once in
passing does not. That is an editorial threshold, not a technical one, and if we
set it too low every page fills with noise.

**The idea.** A section on the thinker page for recorded material about them,
above the ordinary mentions, with a deliberately conservative rule: the thinker
is the subject, not merely named. We will show you what it catches before it
goes live.

## Author information on Musings (6.2)

**Where we are.** 98 of the 195 musings have no author recorded, and none of them
has a link back to the primary work it was excerpted from either, so there is no
field to derive it from. The good news: **74 of those 98 name the source in the
text itself**, in sentences like "In a 1986 article published in Freedom First,
the prolific Marathi editor Govind Talwalkar".

**What needs a conversation.** The remaining 24 have nothing to go on. Those need
either the original WordPress posts or somebody at CCS who remembers.

**The idea.** Extract a proposed author for the 74 from their own text, and send
them to you as a list to approve rather than publishing them unchecked. An
attribution that is wrong is worse than one that is missing, in an archive.

## Visual separation on the Home page (2.2)

**Where we are.** Not started. The point is fair: the page is one continuous
cream field and the sections run together.

**What needs a conversation.** This is a design direction, not a fix, and it is
the one thing on your list I would rather show you than describe. You mentioned
the 1947 Partition Archive as a reference.

**The idea.** Alternating section backgrounds and firmer rules between them, using
the palette already on the site rather than introducing new colour. I will bring
two or three versions to look at.

## Contact details, feedback form, Gallery, Testimonials (10.1 to 10.4)

**Where we are.** None of these exist yet. The first two are small. The Gallery
and Testimonials are the ones worth planning, because they change what the home
page is for.

**What needs a conversation.** For the Gallery: what the photographs actually
are, how many, and whether they are of the physical archive, the digitisation
work, or the events. For Testimonials: how many you have, and whether they carry
names and photographs, because three named testimonials read as credibility and
ten anonymous ones read as marketing.

**The idea.** Contact details and a feedback form on their own page, linked in the
footer, not on the home page. Testimonials as a single quiet band on the home
page, three at a time. Gallery as its own section. I would rather not add all
four to the landing page at once.

## The wider point in section 12

**Where we are.** I agree with your users, and it is the most useful thing in
your email. The site does explain itself before it speaks. That is a consequence
of how it was built: the descriptive standfirsts and the section labels exist so
that search engines and AI agents can parse the archive, and it worked, but it
has leaked into the reading experience.

**What needs a conversation.** Which pages matter most to you. A copy pass across
the whole site is a large job and I do not want to spend it on pages nobody
reads.

**The idea.** Treat this as one piece of work rather than scattered fixes. Start
with the Home page, About and the four section landing pages, cut the standfirsts
that restate the heading, and keep the machine-readable description in the page
metadata where it belongs and no reader sees it. Your new copy for Home, About
and Thinkers is the natural start.

See you tomorrow.

Best,
Adnan
