# Quest contributor harvest — items needing a human eye

These are the cases the recovery could not settle from the evidence available.
Each is recorded rather than guessed, because a wrong biography attached to a
real author is worse than a blank field.

## Cross-attached captions, pages not rendered (QT011)
QT011 is the Marathi Literature special issue; its biographies sit in a
recurring "Some of our contributors" photo-and-caption feature rather than one
back-matter block.
- A caption under **P. S. Rege** appears to describe **Sadanand Rege** and
  **Indira** instead — a name-adjacency mixup in the printed layout.
- A caption under **W. L. Kulkarni** appears to include **Kusumavati
  Deshpande's** caption as well.
Both sit on printed pp.48-49, which were outside the rendered set, so they were
left untouched. Re-render those two pages to settle it.

## Truncated or garbled, not visually re-verified (QT016)
- **Chetan Karnani** — note is truncated.
- **Uma Anand** — note has a word-order garble, probably simple OCR, but was not
  re-checked against the image.

## Printed biography with no matching byline record (QT020)
- **A. M. Ghose** has a printed biography in QT020, found nested inside C. L.
  Nahal's merged note, but he is not a tracked byline in that issue's record.
  Reported rather than force-inserted: adding a contributor the extraction never
  saw would put a person on an issue on the strength of a nested note alone.

## Uncredited name, no byline match (QT011)
- **Somnath Samel** appears in the photo credits but matches no tracked byline.
  Probably the feature's photographer. Not added as a record.

## Notes that are not biographies
Five items were transcribed accurately but are the person's own prose, not
biography, so they sit in `self_authored_excerpt` and do NOT feed author
profiles: four correspondence letters (S. Ookerjee, David Mark, P. K. Saha,
Nissim Ezekiel) and one Einstein quotation. See
.claude/quest-ingest/check_note_shape.py.
