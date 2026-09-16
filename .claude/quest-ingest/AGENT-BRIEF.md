# Per-issue agent brief — Quest ingestion

ONE subagent = ONE complete issue. Substitute {QT} (e.g. QT029), {PP} (page
count from `pdfinfo`), {DIR} (the working dir printed by prep_work.sh), and the
example volume/number for that era. Send it as the Agent prompt verbatim; every
clause below exists because a real failure produced it.

---

You are cataloguing ONE COMPLETE ISSUE of *Quest* for the Indian Liberals
digital archive — a public-good research archive that scholars, journalists and
AI agents will cite. Accuracy matters more than speed. Take as long as you need.

*Quest* is a Bombay quarterly sponsored by the Indian Committee for Cultural
Freedom. By this point in the run it prints "A Quarterly of Inquiry, Criticism
and Ideas" on its contents page and "An Adventure of Ideas" on the cover — two
different genuine self-descriptions — is edited by Abu Sayeed Ayyub and Amlan
Datta with advisory editors, and numbers issues sequentially with no volume
number. DO NOT ASSUME ANY OF IT — the masthead CHANGES mid-run: the reviews
desk passed from Nissim Ezekiel to Indira Talyarkhan and back within QT028-031,
and an assistant reviews editor appears at QT031. read masthead, self-description, cadence,
editors and board off this issue and report what you actually find. (The cover
and contents page also sometimes give DIFFERENT dates — QT027 says "autumn 1960"
on the cover and "OCT./DEC. 1960" inside. Record both.)

YOUR ISSUE: {QT} — {PP} PDF pages.
WORKING DIRECTORY: {DIR}

=== WHAT IS THERE ===
- `system.txt` + `user.txt` — METADATA schema and rules. Authoritative.
- `summary_system.txt` + `summary_user.txt` — SUMMARY schema and rules.
- `page-001.jpg` … `page-014.jpg` — the first 14 PDF pages. Display type OCRs
  badly: TRUST THESE IMAGES over the text layer for cover, masthead, contents.
- `fulltext.txt` — the COMPLETE text layer of all {PP} pages, delimited
  `===== PDF PAGE n of {PP} =====`.
- `render_page.sh` — renders any page to a JPEG and prints its path:
  `./render_page.sh 57`. Use it freely.
- `offset_hint.txt` — a guess only; agents have correctly rejected it as OCR noise.

=== METHOD ===
1. Read `system.txt` and `user.txt`.
2. Read all 14 front-matter images; transcribe the cover exactly.
3. Read the printed contents page from the images — your spine, but NOT the
   whole issue.
4. Read `fulltext.txt` IN FULL. Do not stop early.
5. THE FOLIO OFFSET IS OFTEN NOT CONSTANT. Observed so far: constant -2; -2 then
   -4; -2 then -6; -2/-4/-6; -2/-4/-6/-8; -2/-4/-6/-10. Every shift is caused by
   unnumbered plates tipped in mid-issue, so a long issue may have several.
   Verify by rendering early, middle AND late; record each range and say how you
   checked. TWO look-alikes to distinguish: QT020's leaves are genuinely BOUND
   OUT OF SEQUENCE (printed pp.22-41 relocated), detected because a sentence
   continued across non-adjacent PDF pages; QT024's text layer INTERLEAVED two
   reviews sitting in adjacent columns on the SAME page, which is an OCR
   artefact, not a binding defect. Diagnose before reporting. A THIRD
   look-alike is a folio DIGIT MISREAD: QT029's text layer gave "100" where
   the page prints 103, and QT031's gave "86" and "88" for 36 and 83. Each
   would have broken an otherwise constant offset; each was settled by
   rendering the page header. Never revise an offset on the text layer alone.
6. Render any page whose text is garbled, empty or visual. A near-empty text
   block usually means a plate, photograph or advertisement. Quest often carries
   visual material with NO contents entry — found so far: M. F. Husain drawings,
   a Laxman Pai painting, a Richard Lannoy photograph, a Jehangir Sabavala still
   life, a Francis Newton Souza etching, two A. M. Davierwalla sculptures, an
   S. H. Raza painting, Jean Herman street photography, Khajuraho sculpture, a
   Jaisalmer Fort photo-essay by Dhruva N. Chaudhuri, Indrani Rahman dancing
   Orissi, Sombhu Mitra and Alkazi theatre stills, Olivier and Leigh in Titus
   Andronicus, a four-page Chandigarh essay (Le Corbusier, Fry, Drew,
   Jeanneret), Quest Seminar photographs of Arthur Koestler and Jayaprakash
   Narayan, a Camus memorial portrait, and a Sudhindranath Datta memorial plate
   by Sunil Janah. SEVERAL ISSUES HAD NONE AND SAID SO — a genuine absence is a
   finding, so state it.

=== DELIVERABLE 1: metadata → {DIR}/response_metadata.json ===
Raw JSON, no fence, no preamble.
- `work_type`: "periodical_issue". `title.main`: masthead name as printed.
  `title.subtitle`: the contents-page self-description.
- `publication.publisher_id`: "quest". `publication.issuer_id`: "quest".
  Literally those strings.
- `publication.place`, `publication.year` (integer), `publication.series`
  (number as printed), `publication.edition` (printed designation incl. date).
- **`toc.entries` = ONLY the printed contents page.** Every line separately:
  articles, stories, poems, each review, each correspondence letter. Where one
  contents line groups several items under one page number, split into one entry
  each matched to actual pages (QT011 grouped 14 poems under a single line). Each
  gets `toc_index`, verbatim title, verbatim byline, `page_start`/`page_end` in
  PRINTED FOLIOS. A line with no printed title keeps a null title plus a note.
  Unlisted material does NOT go here — QT006 merged the two and made "what did
  the contents page list?" unanswerable; it had to be re-filed.
- `contributors`: one per byline with `role`
  (author/translator/editor/reviewer/illustrator), `byline_verbatim` exactly as
  printed, and its `toc_index`. Include editors and masthead staff.
- `thinker_id`: ONLY on a genuine match against the authority subset in your
  prompt, and only when the byline identifies one person. The subset is capped
  at 60 of 454 and sorted alphabetically, so most contributors will be absent —
  expected and correct; use null and list them in
  `recommended_authority_additions`. You CANNOT conclude a name is absent from
  the authority file, only from your subset; emit-astro-md.py re-resolves every
  byline against all 454 at emit time. NEVER force a match. Worked examples:
  Rabindranath Tagore was kept out of the unrelated Dwarkanath Tagore entry;
  "Michael Polanyi" was not resolved to his brother Karl; "Ellen Roy" was not
  conflated with M. N. Roy; James Mill was not conflated with John Stuart Mill;
  "N.E." and "A.H.D." were left unresolved rather than guessed at Nissim Ezekiel
  and Ashok Desai. CRITICAL: never resolve a SINGLE-WORD byline to a multi-word
  person — a poem bylined merely "Indira" was credited to Indira Gandhi and had
  to be corrected.

=== DELIVERABLE 2: summary → {DIR}/response_summary.json ===
Read `summary_system.txt` and `summary_user.txt` first. Their `METADATA_JSON`
placeholder is EMPTY — use YOUR OWN Deliverable 1 as the phase-1 metadata;
`essays_summarized[]` toc_index values MUST match the `toc.entries` you assigned.
- MULTI-AUTHOR shape: `volume_summary` plus `essays_summarized[]`. Do NOT emit
  the single-essay shape (bare top-level `toc_index` + `summary`) — that silently
  lost five articles on an earlier issue.
- ONE ENTRY PER `toc.entries` entry, PLUS one for every substantive unlisted
  item, each with `"in_toc": false` and a toc_index continuing after the printed
  ones. Commercial advertisements are NOT substantive — exclude them.
- Each entry: a real summary of the argument or narrative, `key_points`, 1-2
  VERBATIM pull quotes with the PRINTED page and `page_system: "printed"`, and
  `cross_thinker_mentions`.
- `summary_completeness`: `based_on_pages` [1, {PP}], every PRINTED toc_index in
  `essays_complete`, `essays_partial`/`essays_not_yet_seen` empty,
  `extent_caveat` false. Only claim this if true.
- `themes`: the controlled vocabulary in the prompt, kebab-case; new ones in
  `theme_proposed_new`.

=== DELIVERABLE 3: contributor notes → {DIR}/response_contributors.json ===
We build an author profile page for every person with a BYLINE in Quest — not
for people merely discussed. Quest prints "Contributors to this issue" and often
a separate "Our Reviewers" block; some issues print NO heading at all (QT003's
runs straight from the folio into the first biography). A JSON array, one object
per bylined person:
{
  "byline_verbatim": "exactly as printed, preserving case",
  "name_as_in_contributor_note": "the form on the notes page, if different",
  "name_variants": ["every other spelling seen anywhere in the issue"],
  "roles": ["author"],
  "toc_indexes": [1],
  "note_verbatim": "the biography copied WORD FOR WORD, or null",
  "note_printed_page": 103,
  "nationality_evidence": "printed words indicating where they are from, or null",
  "vocation_evidence": "printed words stating their occupation, or null",
  "is_editor_of_issue": false
}
CRITICAL, learned from a failed mechanical recovery:
- `note_verbatim` must be the person's BIOGRAPHY — third person, normally
  opening with their own name. NOT their article text, NOT a letter they wrote,
  NOT a quotation, and NOT the biography of whoever is printed next to them.
  Name adjacency in these layouts caused real damage: Amaresh Datta's bio was
  filed under "Sudhin Datta", Gurbachan Singh Talib's under "Miss Sheela
  Singh", an advertisement contaminated H. H. Price's note, and one Ookerjee
  letter was split across four unrelated people.
- No printed biography means `null`. Editors, masthead staff, reviewers and
  correspondents frequently have none, and null is the correct answer.
- `nationality_evidence` must rest on printed words, NEVER inferred from a name.
  This matters: 30+ Quest contributors are evidenced as non-Indian — Silone, de
  Rougemont, Brecht, Luthy, H. H. Price, Paul Tabori, Eliezer Livneh ("born in
  Russia 1902, has lived in Israel since 1920"), Joseph Roggendorf, Aron Tamasi,
  Swami Agehananda ("an Austrian by birth"), Philip Spratt ("as an envoy of the
  British Communist Party") — and the schema defaults `nationality` to india.
- NAME VARIANTS MATTER; they merge one person across the run. Seen: "Monika
  Verma"/"Monika Varma", "S. Ookerjee"/"S. Ookerji", "David
  McChutchion"/"McCutchion", "Sachin K. Roy"/"S. K. Ray", "Ashapurna
  Devi"/"Ashapurna Gupta", "Annada Shankar"/"Sankar Ray". But do NOT record an
  OCR artefact as a variant: "A.M. Chose" was the text layer mangling "A. M.
  Ghose" — check the image before deciding.

=== ACCURACY RULES ===
- NEVER summarise from a contents page, editor's introduction or blurb. Only
  from text you actually read.
- Pull quotes word-for-word; no paraphrase, no spelling fixes. Preserve real
  typos and OCR garbles with `transcription_anomaly`. If a defect makes a
  sentence ambiguous, choose a different quote rather than guessing.
- If something is illegible after rendering, say so plainly.
- Do not sanitise the historical record. Transcribe dated or offensive language
  as printed and flag it in your report, noting whether it is the author's own
  view or something they report in order to criticise.

Also report anything an editor should know about the issue as an artefact:
QT031 reviews a book by its own co-editor (S. Natarajan on Amlan Datta) with no
printed note of the relationship, which is the kind of thing a reader of the
archive should be told.

Finally report: masthead self-description and cadence AS PRINTED, issue number,
cover date(s), editors and board, the offset range(s) and how verified, printed
toc.entries count, essays_summarized total and how many carry in_toc false, what
the contents page omits, contributor count and how many had printed biographies,
and anything unreadable.
