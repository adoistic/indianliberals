# Addendum for lower-capability models

Appended to the metadata system prompt ONLY when the extraction runs on a
small/cheap model (kie `--route codex`, gpt-5-6-luna, etc). It is deliberately
NOT part of metadata.a.md / metadata.b.md: the baked Sonnet corpus was produced
without it, and changing the shared prompt would make the two halves of the
corpus incomparable.

Every rule below is written against an observed failure on this corpus, not a
hypothetical one. Measured on 8 baked Swatantra letters replayed through
gpt-5-6-luna (2026-08-18): raw agreement with the Sonnet baseline was 5/8, and
all three misses were one of the four cases named here.

---

## Reading the page: what you are looking at

These are 1960s–70s Indian political office papers — carbon copies, typescript,
mimeograph, and telegram forms — scanned at moderate resolution. The text is
often faint, skewed, or broken. Read the IMAGE. Do not infer content from the
filename; the filename is a cataloguing convenience and is sometimes wrong.

## The four things that get missed. Work through each one explicitly.

**1. Signatures — attempt them before declaring them illegible.**
A typed name and a handwritten signature are different evidence and both count.
Before writing `[illegible signature]`, do all of these:
  - look for a TYPED name beneath or beside the signature — office letters
    almost always type the signer's name under the manuscript squiggle;
  - look at the letterhead, the reference line, and the typist's initials
    (e.g. `mrm/rb`) — these frequently identify the sender;
  - compare the shape against the `canonical` and `also_known_as` names in the
    authority subset you were given. A short signature such as `Ranga` is a
    surname you can confirm against that list.
Only after all four fail should you emit `[illegible signature]`.
Observed failure: a signature reading `Ranga` was returned as
`[illegible signature]` although the name appears in the authority subset.

**2. Initials — do not guess a letter you cannot see.**
Indian bylines in this corpus are initial-heavy (`I.C. Thakkar`, `M. R.
MASANI`, `N. G. Ranga`). A single wrong initial produces a different person and
silently corrupts the archive. If a specific initial is genuinely ambiguous on
the scan, transcribe the part you CAN read and set that author's `confidence`
to `"low"` rather than inventing a plausible letter.
Observed failure: `(I.C. Thakkar)` was returned as `(P.C. Thakkar)`.

**3. `byline_verbatim` means verbatim.**
Copy the byline exactly as printed, INCLUDING surrounding punctuation and
capitalisation: if the page reads `( M. R. MASANI )`, that is the value —
not `M. R. Masani`, not `M. R. MASANI`. Do not normalise, expand, or tidy.
The separate `thinker_id` field is where normalisation happens.

**4. `work_type` — a telegram is not a letter.**
Classify from the physical form on the page, not from the prose. Mark
`telegram` when you see any of: a printed telegram/cable form or grid; the
words TELEGRAM, CABLE, EXPRESS, or a post-office frank; an addressee and
sender block with no salutation and no complimentary close; block-capital
running text with omitted articles (`ARRIVING DELHI TUESDAY REGARDS`).
A `letter` has a salutation (`Dear …`), a complimentary close (`Yours
sincerely`), or both.
Observed failure: a telegram was classified as `letter`.

## Authority resolution — run this as a procedure, not an impression

For every byline you extract:
  1. Normalise your extracted byline for comparison only: lowercase it, drop
     punctuation and extra spaces (`( M. R. MASANI )` → `m r masani`).
  2. Scan the authority subset in the user message. For each entry, compare
     against its `canonical` AND every string in `also_known_as`, normalised
     the same way.
  3. A match that differs ONLY in case, punctuation, spacing, or the presence
     or absence of full stops between initials IS a match. Emit that entry's
     `id`.
  4. Only if no entry matches under that comparison, emit `thinker_id: null`
     and set `needs_human_review: true`.

Step 3 is the one that gets skipped. The binary rule in the main prompt exists
to stop you INVENTING ids for people who are absent from the list — it is not
a reason to return `null` for someone who IS in the list but is printed with
different punctuation.

Observed failure: a byline whose person was present in the authority subset was
returned as `thinker_id: null`.

## Before you return

Check each of these and fix it if wrong:
  - every author has a `byline_verbatim` copied exactly as printed;
  - every author has been run through the four resolution steps above;
  - `work_type` was chosen from the physical form of the document;
  - anything you genuinely could not read is marked `confidence: "low"` and
    flagged, rather than guessed.
Return the JSON object only. No prose before or after it, no code fences.
