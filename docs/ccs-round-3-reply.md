# Reply to CCS, round-3 feedback (2 August 2026)

Draft for Adnan to send. Plain text, no em dashes, per house style.

---

Dear Arjun,

Thank you for this. It is a good, specific list, and most of it is
straightforwardly buildable. Before the meeting I want to give you one finding
that changes how three of your items should be read, then set out what is
already done, what I need from you tomorrow, and what remains.

## First: three of your items were one bug, and it is fixed

Your request to remove M. N. Roy, your point 8 about backend changes not
appearing, and your point 9 about ThePrint not updating are the same fault.

On 30 July a save from the CMS wrote one field on the M. N. Roy entry
incorrectly. The field `vocations` should hold a list. It was written as a piece
of text that looked like a list. The site is built as static pages, so a single
file that fails validation fails the entire build, and Cloudflare stops
publishing. The previously published site stays up and looks perfectly healthy,
which is why nobody saw it.

What follows from that:

- **M. N. Roy had already been removed.** Aayushi made the change herself on
  31 July. It was correct and it is still in place. It simply could not reach
  the live site. He is now gone from the Thinkers list.
- **Point 8 is not caching.** Nothing published between 30 July and today. It
  was not slow, it was stopped.
- **Point 9 is not a broken integration.** The ThePrint import ran normally and
  on schedule, including on 1 August, when it collected two new pieces. They
  were sitting in the repository, unpublishable.

Three things have been done about it:

1. The entry is repaired. Every editorial change CCS made to it stands.
2. The CMS itself is fixed, which matters more. 448 files in the archive were
   exposed to the same fault, and any one of them opened and saved would have
   done the same thing. It is now covered by a test that runs on every build.
3. A check now runs on every change and fails loudly if any file breaks. The
   site can no longer freeze silently. This is the part that was genuinely
   missing, and it is the reason a bad save cost six days instead of ten
   minutes.

I am sorry it took your email to surface it.

## Second: the numbers are not wrong, and it is worth being precise about why

You asked us to correct the figures in "Archive at a Glance" because some look
inaccurate. We have gone through every one. None of them is miscounted. Nothing
on the site is typed in by hand; every figure is counted from the content each
time the site is built.

Here is exactly what each one counts, as of today:

| Shown as | What it counts | Value |
|---|---|---|
| Primary works | every primary work that is not a draft | 1,575 |
| Periodical issues | of those, the ones marked as a periodical issue | 740 |
| Interviews | of those, the ones marked as an interview | 92 |
| Thinkers profiled | every thinker classified as core or extended in the tradition | 194 |
| Excerpts & opinions | every musing plus every opinion | 254 |

The reason they feel wrong is real, though, and it is this: three of those tiles
are links, and they open a page that shows a different number.

- "Thinkers profiled: 194" opens a page listing 23 people. Both are true. The
  tile counts everyone classified as part of the tradition; the page shows only
  the curated canon. The other 171 are real records and are reachable, just not
  listed there.
- "Excerpts & opinions: 254" opens Opinions, which has 59.
- "Periodical issues: 740" opens a page that also counts the Forum of Free
  Enterprise booklets, which are not periodical issues.

So the question for tomorrow is not arithmetic, it is which number you want a
reader to land on. My recommendation is to point each tile at the page that
holds what it counts, rather than shrink the numbers, because 194 is the honest
scale of the archive and 23 is not.

On the total page count you asked us to add: the figure available today is
**22,715 pages across 1,423 works**. 110 works have no pages at all, being the
interviews and lectures, which are video. 42 paginated works have no count
recorded. So the honest options are to publish "over 22,000 pages", or to let us
spend a day counting the source PDFs exactly first. I would rather ask than put
a number on the home page we cannot stand behind.

## Two smaller corrections

**On the featured images (7.2).** Your diagnosis is right: the old site used a
portrait canvas and the new one crops those images badly. The measurement is
slightly off, though. The new site is not using 3:2. It uses 21:10 for the lead
image and 16:10 for the cards. That matters because moving to a portrait shape
changes the whole grid rather than one number, so I would like five minutes with
you on how the listing should look rather than guess.

**On renaming to "Periodicals" (3.1).** Happy to do it, and it is done. But it
is worth knowing that most of what is on that page is not a periodical. The
roughly 600 Forum of Free Enterprise booklets, the annual budget analyses and
the memorial lectures all live there, which is why it was called "Series and
Periodicals". If a reader goes to Periodicals looking for the Forum booklets,
the name now works against them. Easy to revisit.

## What is already done and will be live today

- M. N. Roy removed from the Thinkers list.
- Thinkers listed alphabetically.
- Organisations hidden from the navigation. Nothing is deleted; every
  organisation page still exists and still resolves.
- About page: the contributors section is renamed "People who helped in
  building this Archive" and moved above "What You'll Find Here".
- "Series and Periodicals" renamed to "Periodicals", and "The runs" removed.
- Opinions page titled "Opinions".
- The repeated article in "Related across the archive" is fixed. It affected 76
  entries and 88 duplicate links in total.
- Count-up animation on the home page figures.
- The search bar is larger and now reads as a search field rather than a menu
  item.

## What I would like to settle tomorrow

Things I cannot start without you:

- The revised copy for the Home page, About page and Thinkers description.
- The black-and-white image of Raja Ram Mohan Roy.
- Which numbers you felt were wrong, against the table above.
- Whether total pages should say "over 22,000" now or wait for an exact count.
- Which interview pages are filed under the wrong person. I need you to name
  them.
- The image shape for Opinions, and the grid that follows from it.
- What belongs in the new Events section, beyond the annual lecture and the
  essay competition.

## What remains, in order of size

Straightforward, next:

- Events section, and moving the lecture and essay competition posts into it.
- Languages sub-section for Hindi, Bengali and Marathi.
- Mobile sort and filter as a dropdown.

Larger, and worth their own conversation:

- Grouping Collections by publication house.
- Oral Histories, with the four sub-sections. Much of this structure already
  exists, so it is less work than it looks.
- Surfacing interviews and talks about a thinker on that thinker's page.
- Author information on musings. 98 of the 195 have no author recorded at all,
  so this is a research task rather than a data-entry one, and I would like to
  scope it with you.
- Visual separation between home page sections.
- Contact details, feedback form, Gallery, Testimonials.
- The wider point in your section 12, that the site explains itself to search
  engines before it speaks to people. I agree with it, and it deserves a proper
  pass rather than being folded into this round.

Two of these last items overlap with what your users told you, and I would
rather treat them as one piece of work than as scattered fixes.

See you tomorrow.

Best,
Adnan
