# People section — restructuring options for CCS (round-2 feedback #12)

Date: 2026-07-09. CCS asked to "rethink the entire People section and its sub-sections."
This is a design decision, not a defined fix, and it overlaps with the still-pending
Home/Canon author list (#18a). Per the brief we have **not** done a speculative redesign;
this note lays out options for CCS to choose from, plus the concrete sub-fixes already made.

## What exists today

- `/thinkers/` — "The Indian liberal canon" landing: a people search over all ~361 people,
  plus two curated rails driven by the `featured: true` flag:
  - **The canon** — `featured && nationality: india`, chronological.
  - **International influences** — `featured && non-india`.
- `/thinkers/directory/` — the full directory, split into **canon / extended / referenced /
  unclassified** by `canon_status`, with per-person work + reference counts.
- Membership of the curated rails is purely the `featured` frontmatter flag (Sveltia-editable).

## Sub-fixes already landed (this round)

- **#11 work counts** now agree across the landing, directory, and detail pages
  (authored-only; ThePrint mentions and contributor/interview roles no longer inflate them).
- **#18b photo style** — every featured portrait is the uniform B&W duotone; a grayscale
  safety net keeps any future non-duotone fallback from showing a colour photo on the rails.

## Options for the rethink (pick one, or mix)

**A. Keep the two-rail canon, tighten membership (lowest effort).**
Keep `/thinkers/` as canon + international influences, but curate `featured` down to the
final Home/Canon list once CCS sends it (#18a). Directory stays as the "everyone" catch-all.
Best if CCS mainly wants the *right people* featured, not a new structure.

**B. Three tiers, explicit and labelled.**
Restructure around `canon_status`: **Canon** (the core tradition), **Extended** (the wider
liberal cast), **Referenced** (non-liberals the corpus cites). Give each its own page/section
with a one-line definition at the top so the distinction is legible to a first-time visitor.
Removes the "why is X here?" confusion. Moderate effort; needs CCS to ratify who is canon vs
extended.

**C. Thematic / role-based entry.**
Group people by vocation or era (reformers, economists, jurists, editors, farmer-movement,
international influences) instead of one long canon. Good for browsing, weaker for "who is the
canon"; risks fragmenting a small set. Higher effort.

**D. Canon as an edited narrative.**
Turn `/thinkers/` into a short curated essay ("the arc of Indian liberal thought") with the
featured people threaded chronologically, and push the searchable/faceted list entirely to the
directory. Highest editorial effort; strongest as a *statement* of the tradition.

## Recommendation

**Start with A**, then layer **B** once the #18a list arrives — i.e. lock the featured set,
then make the canon/extended/referenced split explicit and labelled. That resolves the two
concrete complaints (right people, legible tiers) without a speculative rebuild. C and D are
larger bets worth a separate design conversation if CCS wants the People section to become a
showcase rather than an index.

**Blocked on:** CCS direction on which option, and the pending #18a Home/Canon author list.
