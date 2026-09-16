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

## Two pseudonyms one letter apart (QT023, QT028, QT029)
- **'Sanjoy'** signs the Koestler review in QT029 (signature verified against the
  rendered page).
- **'Sanjaya'** is a different spelling belonging to the QT028 writer whom Vinod
  Sena answers in QT029's correspondence.
They are recorded as two people and must not be merged without editorial
evidence. Both are held back from profile-building anyway — a single-token name
with no printed biography gets no page — so a decision is not yet blocking.

## A USIS officer among the contributors (QT034)
Robert Gilkey's printed note says he "has just terminated his post as Cultural
Affairs Officer, USIS, Calcutta". Recorded verbatim in his vocation evidence,
with nationality left null (a posting is not an origin). Flagged because the
Congress for Cultural Freedom's funding history makes the affiliation of a
Quest contributor something a reader of the archive should be able to see, not
something for the archive to decide quietly either way.

## Reported speakers who are not bylines (QT034)
The ICCF meeting reportage quotes P. Lal, Kazi Abdul Wadud, Hirankumar Sanyal
and chairman Jayantanuja Bandopadhyaya, but the contents line covers them with
"and others". They are recorded as mentions, not bylines, so they get no author
profile. An editorial call is available either way: the record is a revised
account drafted by K. K. Sinha, not a verbatim transcript, which is the reason
for leaving it as it stands.

## A contributor note for a non-contributor (QT039)
QT039's "OUR CONTRIBUTORS" page prints: "CHETAN KARNANI, who contributed to our
Arts Section in the Monsoon issue, teaches English in the University of
Rajasthan." Karnani has NO byline anywhere in QT039 — the agent grepped the
whole text layer and his name occurs only in that note. It is almost certainly a
standing entry left set from the previous issue.

He is therefore not in QT039's contributor records, which is the correct
ontology: a note alone does not make someone a contributor to an issue. But the
sentence does supply the vocation that QT016's truncated note for him is missing
(see above). It is recorded here rather than copied into his QT016 record,
because compose_body cites the issue that a record belongs to, and pasting
QT039's sentence under a QT016 page reference would cite the wrong page.
An editor completing his profile can take it from here.
