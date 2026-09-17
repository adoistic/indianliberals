# Testimonials, Gallery, and the periodicals card unification

Design record, 17 September 2026. Written by Claude for Adnan, who asked for
the work to be done end to end without a review gate; the decisions below are
the ones a reviewer would otherwise have been asked to approve.

## What is being built

Three things, one commit series:

1. **Testimonials.** A real `/testimonials/` page in the About cluster,
   replacing the coming-soon placeholder, fed by a new `testimonials` content
   collection (seven entries from the supplied document, with portraits). The
   four from renowned figures are `featured` and appear on the homepage.
2. **Gallery.** A real `/gallery/` page, fed by a new `gallery` collection
   (33 photographs from the supplied folder, captioned and grouped into
   albums, with a lightbox). Seven are `featured` and appear on the homepage
   as a photo mosaic.
3. **Periodicals index consistency.** The "Booklets, papers and lectures" and
   "Magazines & journals" sections of `/periodicals/` now use one shared card
   (`RunCard.astro`) in one grid, so the page reads as one surface.

Both new collections are editable in the CMS: an editor can add a testimonial
or a photograph from the home screen, list and open existing ones, and edit
the pages' own wording under "The site's words".

## Data model

### `testimonials` (one file per testimonial, body = the quotation)

| field | type | notes |
|---|---|---|
| `id` | slug | file name |
| `name` | string | as it should appear under the quote |
| `role` | string, optional | one line: title, institution |
| `photo` | site path, optional | `/testimonials/photos/<id>.jpg` |
| `pull_quote` | string, optional | one sentence for the homepage; falls back to the opening of the body |
| `featured` | bool | on the homepage |
| `order` | int, optional | lower first; unordered entries follow, by name |
| `needs_review`, `draft` | bool | the archive's usual flags |

### `gallery` (one file per photograph, no body)

| field | type | notes |
|---|---|---|
| `id` | slug | file name |
| `caption` | string | shown under the photograph and in the lightbox; doubles as alt text |
| `image` | site path | `/gallery/photos/<id>.jpg` |
| `album` | string, optional | photographs sharing an album string are grouped under that heading |
| `date` | `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, optional | printed in the lightbox; orders photographs inside an album |
| `credit` | string, optional | photographer or source |
| `featured` | bool | on the homepage mosaic (first seven by `order`) |
| `order` | int, optional | |
| `related_thinkers` | thinker ids | "People in this photograph" links in the lightbox |
| `notes` | string, optional | editor-only; never rendered |
| `needs_review`, `draft` | bool | |

One entry per photograph rather than album entries holding photo lists, because
the CMS image widget is built for one picture per field and the existing
collections all work this way. Album order and album blurbs live in the
`section-gallery` site surface (`albums` list), which is the page's own copy.

### Site copy

New surfaces `section-gallery` and `section-testimonials`; new homepage keys
(`gallery_*`, `testimonials_*`). The `coming-soon` entry keeps only the contact
page's title and blurb, since nothing is coming soon any more, and the
`ComingSoon` component is deleted.

## Pages

- `/testimonials/`: hero band (heading, lede, count); the featured four as
  large editorial quotations with portraits in a two-column grid; the rest as a
  three-column grid of quote cards under a second heading. Quotations render
  from markdown.
- `/gallery/`: hero band; one section per album (heading, blurb, span of
  dates, count) with a CSS-columns masonry that keeps every photograph's own
  shape; captions under each; a `<dialog>` lightbox with previous/next, keyboard
  arrows, caption, date, credit and thinker links. Without JavaScript each
  photograph links to its file.
- Homepage: a "From the gallery" mosaic (one large, four small, two wide
  tiles) after the thinkers rail, and a "What readers say" band (lead quote plus
  three compact quotes) after the ThePrint column.
- About page: a two-card row pointing at Testimonials and Gallery.
- Header: live counts beside Gallery and Testimonials in the About menu.

## Images

Photographs are committed under `apps/site/public/gallery/photos/`, EXIF
orientation applied, metadata stripped, longest edge 1600 px, JPEG quality 80
(the CMS commits editor-added pictures to the same directory). Portraits go
under `apps/site/public/testimonials/photos/`. Cache rules are added for both
directories, scoped to the photo directories so the HTML pages keep the short
default TTL.

## Out of scope

Per-photograph pages, album entities, image size variants, and translations.
