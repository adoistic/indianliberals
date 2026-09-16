# Quest ingestion — handoff

Paste the "RESUME PROMPT" section below into a fresh Claude Code session in this
repo. Everything else here is reference for whoever picks it up.

---

## RESUME PROMPT

Continue the Quest ingestion for the Indian Liberals archive. Read
`.claude/quest-ingest/HANDOFF-PROMPT.md` first, then
`.claude/quest-ingest/AGENT-BRIEF.md`, and carry on from where it says.

21 issues remain: QT029-QT048 and QT051. Work in batches of four, one subagent
per issue, using the brief verbatim with the per-issue values substituted. After
each batch: finalize, archive, check note shape, publish, reap, validate, commit,
push. Do not leave commits unpushed and do not keep derived data outside the
repo — both bit this project already.

When all 49 are in, do the end-of-run steps in this file: build the author
profiles, re-emit so bylines resolve, rebuild the full-text search index, and
regenerate the legacy redirect map.

---

## WHERE IT STANDS

Quest is a Bombay journal of arts and ideas sponsored by the Indian Committee for
Cultural Freedom, launched August 1955 under Nissim Ezekiel, bi-monthly at first
and quarterly from QT017 (April/June 1958) under Abu Sayeed Ayyub and Amlan
Datta. The supplied Drive folder holds 49 issues, QT001-QT051; **QT049 and QT050
are absent from it**. Quest ran until the Emergency closed it in 1975, so this is
the first two-thirds of the run.

- **28 of 49 published**: QT001-QT028. All committed and pushed.
- **21 remaining**: QT029-QT048, QT051. Source scans are in
  `~/Downloads/drive-download-20260915T160627Z-1-001` (21 files left; earlier
  ones were reaped after verification and live on R2).
- **Harvest**: `data/quest-contributors/` holds 28 issue files, 793 people, 417
  biographies. Committed — this is what the author profiles are built from.
- Run `python3 .claude/quest-ingest/validate.py QT001 ... ` any time for state.

Totals so far: 692 printed contents entries, 782 pieces summarised, 2,738 pages
read with nothing partial or unseen, 82 pieces recovered that appear on no
contents page.

## THE PIPELINE

Per batch of four (all paths from the repo root):

    .claude/quest-ingest/prep_work.sh QT029      # prints DIR=...; stages the scan
    # dispatch one Agent per issue with AGENT-BRIEF.md, values substituted
    .claude/quest-ingest/finalize.sh QT029 <DIR> # collect, emit, normalise, guard
    .claude/quest-ingest/archive.sh QT029        # harvest -> data/quest-contributors/
    python3 .claude/quest-ingest/check_note_shape.py --fix QT029
    .venv-extract/bin/python .claude/quest-ingest/publish.py 029   # R2 pdf + cover
    python3 .claude/quest-ingest/reap.py 029     # delete local scans, verified first
    python3 .claude/quest-ingest/validate.py QT029

`finalize.sh` already runs `scripts/synthesis/guard-byline-aliases.py --fix` and
`carry_scan_defects.py`. `archive.sh` refuses to delete a working directory until
all three deliverables are safely copied into the repo.

## WHAT THE SITE NEEDS (all already done, do not redo)

- `quest` publisher entry in `data/authority/publishers.json`.
- `/periodicals/quest/` shelf: registering a run takes THREE edits to
  `apps/site/src/lib/periodicals.ts` — ORG_SERIES, SERIES_META **and
  SERIES_ORDER**. The file warns that a run missing from SERIES_ORDER renders
  nowhere at all; the shelf 404'd until it was listed there.
- R2 keys: `quest/qtNNN.pdf` and `covers/qtNNN.webp`. Issue-numbered, not
  date-slugged like Freedom First, because Quest was never on the old WordPress
  domain and its cadence changes mid-run.

## END-OF-RUN STEPS

1. **Author profiles.** Build from the committed harvest. A profile goes to
   everyone with a BYLINE (author, translator, editor, reviewer, illustrator);
   people merely discussed in articles stay as cross-thinker mentions. Adnan
   approved creating these. Grounding is Quest's own contributor notes, quoted
   with the issue cited, `bio_source: ai_drafted`, `needs_review: true`.
   - Leave `tradition` and `canon_status` as "unclassified" — Quest published
     poets, musicologists and French art critics, and CCS has a
     thinker-classification round-trip for exactly this.
   - Set `nationality` ONLY from printed evidence. The schema defaults to
     `india`, and 30+ contributors are evidenced as non-Indian.
   - HOLD BACK initials-only bylines ("N.E.", "L.F.", "A.H.D.") — they would be
     junk pages, and "L.F." would split Laeeq Futehally, who already has a
     profile from her named bylines.
   - Merge variant spellings onto one person; the harvest records them.
   - The old builder was lost in a wipe and needs rewriting; its logic is
     described above and its failure modes are in the git log.
2. **Re-emit** the Quest works so bylines resolve to the new profiles
   (`scripts/synthesis/emit-astro-md.py --slug QTNNN`), then re-run the byline
   guard.
3. **Rebuild the full-text search index** — `scripts/fulltext/README.md`.
   Ingesting a work does NOT make it searchable; the corpus silently lags. Diff
   every `pdf_url` against the corpus keys rather than assuming only new works
   are missing.
4. **Regenerate the legacy redirect map** — `scripts/legacy-redirects/generate.py`.
   Expect zero changes: Quest was never on the old domain.

## OPEN QUESTIONS FOR ADNAN / CCS

- **`tradition` and `canon_status`** for ~600 new profiles: left unclassified
  deliberately. CCS's call.
- **The bare "Polanyi" alias** on `karl-polanyi`. Michael Polanyi is in this
  corpus in his own right — he has a printed biography in QT019 ("was born in
  Budapest") and signed the Congress for Cultural Freedom's 1956 cable to Nehru
  in QT009. A bare "Polanyi" MENTION still resolves to Karl. The byline guard
  does not cover mentions by design. Documented in
  `scripts/synthesis/guard-byline-aliases.py`.
- **QT020's scan is defective** — leaves for printed pp.22-41 bound or scanned
  out of sequence. Recorded in that work's `provenance.notes` with
  `scan_quality: fair`. The text was fully recovered, but the artefact is wrong
  and CCS may want to rescan.
- **`data/quest-contributors/FOLLOW-UPS.md`** lists what could not be settled
  from the evidence: QT011's cross-attached P. S. Rege / W. L. Kulkarni
  captions, QT016's truncated Chetan Karnani and garbled Uma Anand, and a
  printed A. M. Ghose biography in QT020 belonging to no tracked byline.
- **QT049 and QT050** are missing from the supplied folder.

## HARD-WON LESSONS — DO NOT RELEARN THESE

- **Read the whole issue.** The contents page is a spine, not the contents. 82
  pieces so far appear on no contents page, including a Milovan Djilas excerpt, a
  Camus memorial portrait, JP Narayan's 1956 Hungary statement, and a cable
  signed by Madariaga, de Rougemont, Spender and Nabokov.
- **The folio offset is per-range, not per-issue**, and the computed hint has
  been wrong. Verify by rendering across the issue.
- **Agents see only 60 of 454 authority names.** They cannot report a name
  ABSENT from the authority file. The emitter resolves against all 454 — that is
  how Salvador de Madariaga was credited after an agent reported him missing.
- **A byline needs more evidence than a mention.** `scripts/synthesis/guard-byline-aliases.py`
  demotes a lone GIVEN name; surnames, bynames and initialisms still resolve. Its
  --audit mode covers the whole corpus.
- **Commit derived data to the repo and push often.** The entire QT001-020
  harvest and every helper script were lost to a disk-full wipe of the session
  scratchpad, with 8 commits unpushed at the time.
- **Check your own tooling's output, not just that it ran.** Four of my scripts
  were wrong on first contact with the material: the recovery misattributed
  biographies by matching surnames in article prose; the note-shape check
  discarded real biographies printed under variant names, then again when a
  biography began inside someone else's note; the defect carrier reported a
  defect from the sentence "No leaves appear bound out of sequence". All fixed,
  each with the reasoning in the commit.
