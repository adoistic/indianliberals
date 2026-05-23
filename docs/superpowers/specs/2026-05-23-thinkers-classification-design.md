# Thinkers Classification — Design Spec

**Author:** Adnan
**Date:** 2026-05-23
**Status:** amended (2026-05-23 — post-impl hygiene)
**Amended:** Corrected the visible-entry count in §1 and §9.3 #13 (was wrongly stated as 328 — conflated `bio_source: ai_drafted_stub` count with `draft: true` count; actual visible count is 402 = 506 total minus 104 drafts). Reworded §9.6 #27 to acknowledge that the pagefind `vocation:` filter key only surfaces after data is populated.

## 1. Goal

The `/thinkers` page currently renders a flat alphabetical photo-grid of every published thinker — 402 visible entries (out of 506 on disk, with 104 hidden as drafts). It treats Hayek, Mukesh Ambani, Nehru, and an obscure liberal commentator as visually identical, with no editorial signal about their position in the liberal canon, their mode of contribution, or their relationship to the site's story.

This spec introduces three independent classification axes on every thinker, redesigns the `/thinkers` index to surface them, and lays the foundation for a future AI-assisted reclassification pass (out of scope for this spec — see §11). End state: the page reads as a coherent editorial map — central canon figures, broader liberal tradition, referenced thinkers from outside it, and an explicit "awaiting classification" tier — with each card carrying specific vocation labels (`Philosopher · Economist · Professor` rather than a generic "thinker") and counts of works/references on the site.

## 2. Non-goals

- **The AI bulk classifier pipeline** that will fill in the new fields across all 506 entries. Will be a separate spec ("sub-project 2"). This spec ships the schema, the page, and the migration, with all entries initially `canon_status: unclassified`. The "Awaiting classification" section is the day-1 home for everyone.
- **Curator review tooling / queue UI** ("sub-project 3"). Out of scope; the existing pattern of `needs_review: true` + git-based review is good enough for v1.
- **Thinker detail-page redesign** (`/thinkers/<slug>/`). The new fields exist in frontmatter but aren't surfaced on the detail page yet. Adding them there is a future spec.
- **Reclassification of any thinker.** This spec touches only schema + page + a mechanical migration that renames two enum values. No editorial classification decisions land here.
- **Changes to `/organisations`, `/primary-works`, or other pages.** Only `/thinkers` index is rewritten.
- **`auto_hide_orphans.py` behaviour.** The existing `draft: true` machinery for hiding orphans is unchanged; drafts continue to be omitted from all sections.

## 3. Scope

Three commits, in order:

1. **Schema:** add `canon_status`, `vocations`, and the new `tradition: practice` value. Deprecate but accept `tradition: international_influence` until sub-project 2 reclassifies it.
2. **Data:** one-time migration script that adds `canon_status: unclassified` + `vocations: []` to all 506 thinker MDs, renames `tradition: nationalist_liberal` → `constitutional_liberal` (53 entries), merges `tradition: reformer` → `social_reformer` (10 entries).
3. **UI:** rewrite `apps/site/src/pages/thinkers/index.astro` with four canon-status sections + a `thinker-stats.ts` build-time helper that computes per-thinker work/reference counts.

## 4. Schema delta

The thinker schema lives in `apps/site/src/content.config.ts` (verified — the `thinkers = defineCollection({…})` block starts at line 43; `apps/site/src/schemas/people.ts` only defines name shapes, not the frontmatter schema). All edits in this section target `content.config.ts`.

```ts
// Before — relevant fields (indicative; verify exact enum vs current source at implementation time)
tradition: z.enum([
  'classical_liberal',
  'contemporary_liberal',
  'nationalist_liberal',
  'social_reformer',
  'reformer',
  'international_influence',
  'unclassified',
]),

// After
tradition: z.enum([
  'classical_liberal',
  'libertarian',                  // NEW
  'constitutional_liberal',       // RENAMED from nationalist_liberal
  'contemporary_liberal',
  'social_reformer',              // absorbs reformer
  'non_liberal',                  // NEW
  'practice',                     // NEW — for non-political figures (industrialists, scientists, etc.)
  'international_influence',      // DEPRECATED but accepted (sub-project 2 reclassifies)
  'unclassified',
]),

canon_status: z.enum([
  'core',                         // Central to the classical-liberal / libertarian canon
  'extended',                     // Broader liberal tradition (constitutional, contemporary, reform-era, honored practitioners)
  'referenced',                   // Mentioned in the corpus but outside the liberal tradition
  'unclassified',                 // Default
]).default('unclassified'),

vocations: z.array(z.enum([
  // Academic / theoretical
  'philosopher', 'economist', 'historian', 'political_scientist',
  'sociologist', 'legal_scholar', 'scientist', 'engineer', 'professor',
  // Writing / editorial
  'writer', 'editor', 'journalist', 'poet',
  // Public office / governance
  'statesman', 'parliamentarian', 'civil_servant', 'diplomat', 'judge',
  // Business / enterprise
  'industrialist', 'entrepreneur',
  // Civil society
  'activist', 'reformer', 'religious_figure',
  // Other
  'military_officer', 'artist',
])).default([]),
```

**Why three orthogonal axes?**

The three answer three different questions:

| Axis | Question | Cardinality |
|---|---|---|
| `tradition` | What tradition of thought does the figure belong to? | single |
| `canon_status` | How central are they to the editorial story this site tells? | single |
| `vocations` | What forms does their thinking take? | multi (1+ specific roles) |

Any combination is possible. Examples:

| Figure | tradition | canon_status | vocations |
|---|---|---|---|
| F. A. Hayek | classical_liberal | core | [philosopher, economist, professor] |
| Milton Friedman | classical_liberal | core | [economist, professor, writer] |
| C. Rajagopalachari | classical_liberal | core | [statesman, writer, editor] |
| Dadabhai Naoroji | constitutional_liberal | core | [statesman, economist, writer] |
| Justice H. R. Khanna | constitutional_liberal | extended | [judge] |
| A.P.J. Abdul Kalam | practice | extended | [scientist, engineer, statesman] |
| J.R.D. Tata | practice | extended | [industrialist] |
| Ratan Tata | practice | extended | [industrialist] |
| Mukesh Ambani | practice | referenced | [industrialist] |
| Jawaharlal Nehru | non_liberal | referenced | [statesman, writer] |
| Raja Ram Mohan Roy | social_reformer | core | [reformer, writer, religious_figure] |

**Why `tradition: practice` specifically?**

The original tradition enum implicitly assumed every figure has an ideological position. Industrialists, technocrats, and apolitical scientists don't fit — calling Mukesh Ambani `classical_liberal` overclaims; calling him `non_liberal` is editorially harsh; `unclassified` falsely implies the curator hasn't decided yet. `practice` is the honest answer: this figure's contribution is doing, not ideological argument.

**No formal cross-axis constraint.** The schema doesn't enforce e.g. "core ⇒ tradition ∈ {classical_liberal, libertarian, constitutional_liberal, contemporary_liberal}". The AI classifier may follow such heuristics, but the schema stays loose to handle edge cases (a `practice + core` industrialist whose enterprise is integral to the liberal story; a `social_reformer + extended` reform-era figure).

## 5. Build-time helper: `thinker-stats.ts`

New file at `apps/site/src/lib/thinker-stats.ts`. Pure function, no side effects, computed once per build.

**Exports:**

```ts
export interface ThinkerStat {
  worksAuthored: number;  // Sum over all collections of entries where this thinker is an "author" per §5.1
  referencedIn: number;   // Sum over all collections of entries where this thinker appears in a "reference" field per §5.1, excluding entries already counted in worksAuthored for the same (collection, entryId) pair
}

export async function getThinkerStats(): Promise<Map<string, ThinkerStat>>;
```

**Contract:**

- The returned Map contains an entry for every thinker that has at least one non-zero count. Thinkers with both counts zero are **omitted** from the Map. Page-render code must use `stats.get(id) ?? { worksAuthored: 0, referencedIn: 0 }`.
- The Map keys are thinker `id` strings (slugs). Organisation refs are excluded.

### 5.1 Per-collection field mapping

| Collection | Counts toward `worksAuthored` | Counts toward `referencedIn` |
|---|---|---|
| `primary-works` | `authors[]` (filter to thinker-refs only; org-refs excluded) | `contributors[].thinker` (any role) + `thinker_mentions[].thinker` + `related_thinkers[]` |
| `opinions` | `author` (singular ref) | `subject` + `thinker_mentions[].thinker` + `related_thinkers[]` |
| `interviews` | *(none — interviewee is not an "author" in the writing sense)* | `subject` + (any other thinker-ref fields on the schema) |
| `musings` | `author` (singular ref) | `thinker_mentions[].thinker` + `related_thinkers[]` |
| `theprint-mirror` | *(none — `author_name` is a free-text string, not a thinker ref)* | `thinker_mentions[].thinker` + `related_thinkers[]` |
| `periodicals` | TOC entries' `author_resolved` ref (one count per TOC entry the thinker authored) | `related_thinkers[]` + `thinker_mentions[].thinker` + TOC entries' `cross_thinker_mentions[].thinker_resolved` |

**Within-entry dedup:** if a thinker appears in both an "authored" field AND a "referenced" field of the SAME entry, count them as `worksAuthored` only — not in `referencedIn`. (Example: a primary-work where the thinker is in both `authors[]` and `thinker_mentions[]` — the mention doesn't double-count.)

**Across-entry counting:** each distinct entry contributes its own count to each bucket — so a thinker with 3 primary-works in `authors[]` has `worksAuthored: 3`, and one of those same primary-works also referencing them in `thinker_mentions[]` does NOT bump `referencedIn` (per the within-entry dedup above).

**Implementation sketch:**

1. Initialise an empty `Map<string, { worksAuthored: number; referencedIn: number }>`.
2. For each collection in the table above, iterate `await getCollection(name)`.
3. For each entry, compute two sets per the table: `authoredThinkers` and `referencedThinkers`. Subtract `authoredThinkers` from `referencedThinkers` (within-entry dedup).
4. For each thinker id in the resulting `authoredThinkers`, increment its `worksAuthored` in the Map (creating the entry if absent).
5. For each thinker id in the resulting `referencedThinkers`, increment its `referencedIn`.
6. After all collections processed, drop any Map entries where both counts are zero (none should be — they wouldn't have been added — but a defensive sweep is cheap).
7. Return the Map.

**Why a build-time helper, not stored frontmatter?**

`worksAuthored` and `referencedIn` are *derived* from the corpus — every time a new primary-work lands, every thinker's counts may change. Storing them in frontmatter would require keeping them in sync on every content edit. A build-time computation is free, always correct, and adds no maintenance burden.

## 6. UI rewrite — `apps/site/src/pages/thinkers/index.astro`

### 6.1 Header

- Eyebrow `Thinkers` (unchanged).
- H1 `Figures in the Indian liberal tradition` (unchanged).
- Lede paragraph (unchanged).
- **New one-line stat** below the lede, computed from canon-status counts + `thinker-stats` helper:
  > `N thinkers · M with works in the archive · K referenced in other works`

### 6.2 Four sections, stacked

| # | Title | Filter | Editorial blurb |
|---|---|---|---|
| 1 | **Liberal canon** | `canon_status === 'core'` | "Central figures in the story this site tells: thinkers whose ideas, governance, scholarship, or enterprise form the foundation of the case for individual liberty, free enterprise, and constitutional governance in modern India." |
| 2 | **Extended liberal tradition** | `canon_status === 'extended'` | "The broader cast in the liberal story: thinkers, statesmen, scholars, and figures of practice whose work belongs here without being at the very centre. Includes constitutional liberals, contemporary commentators, reform-era thinkers, and practitioners whom the liberal tradition honors — scientists, jurists, industrialists whose work has shaped the Indian liberal imagination." |
| 3 | **Referenced thinkers** | `canon_status === 'referenced'` | "Thinkers and figures from outside the liberal tradition whose work appears in the corpus — through citation, critique, or admiration. Their presence reflects their role in liberal writing, not editorial endorsement." |
| 4 | **Awaiting classification** | `canon_status === 'unclassified'` | *Italic single line:* "Classification pass in progress — these thinkers will move into the sections above as curator review completes." |

**Empty-section rule:** if a section's filtered set is empty, header / blurb / grid are all omitted from the rendered HTML. On day 1 post-merge, sections 1-3 are empty; only section 4 renders. As classifications come in, sections populate and appear automatically.

**Sort within each section:** alphabetical by `name.sort` (current behaviour for the flat list).

**Section markup pattern:**

```astro
<section aria-labelledby="liberal-canon-heading">
  <h2 id="liberal-canon-heading" class="...">Liberal canon</h2>
  <p class="...">{blurb}</p>
  <div class="grid ..."> {/* card grid */} </div>
</section>
```

### 6.3 Card design

The existing portrait + name treatment is preserved (same dimensions, same hover/focus, same orphan-placeholder for portrait-less entries). **Three additions** sit below the name in an inline-flex stack:

1. **Vocations caption** (rendered whenever `vocations.length > 0`):
   - `·`-separated, sentence-case from the enum value: `Philosopher · Economist · Professor`.
   - Enum value `legal_scholar` → display `Legal scholar`. `political_scientist` → `Political scientist`. `religious_figure` → `Religious figure`. Convert via `value.replace(/_/g, ' ').replace(/^(.)/, c => c.toUpperCase())` or equivalent.
   - Style: `text-xs text-(--color-fg-muted) font-(family-name:--font-ui)`.
   - Empty array → caption omitted.

2. **Works chip** (rendered when `worksAuthored > 0`):
   - Text: `${n} work${n === 1 ? '' : 's'} on this site` — `1 work on this site` / `3 works on this site`.
   - Style: `inline-block px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-(family-name:--font-ui) font-semibold bg-(--color-forest-100) text-(--color-forest-700)` (forest tint to match the byline-link colour story from the org-authorship work).
   - Not clickable in v1; the card's outer `<a>` already routes to the detail page.

3. **Referenced label** (rendered when `referencedIn > 0`):
   - Text: `· Referenced in ${n} piece${n === 1 ? '' : 's'}` — `· Referenced in 1 piece` / `· Referenced in 12 pieces`.
   - Style: muted plain text (`text-xs text-(--color-fg-muted)`), no background. Subordinate to the works chip.
   - When both works-chip and referenced-label are present, they sit on the same line separated by their natural inline whitespace (the leading `·` on the referenced label is the visual separator).
   - When only referenced-label is present, the leading `·` is dropped (it becomes a standalone label, not a separator).

**No tradition on the card.** Tradition is editorially implied by which section the thinker sits in. Re-rendering it on each card would be visually redundant.

### 6.4 Card examples (intended rendered shape)

**Hayek in "Liberal canon" section:**
```
[portrait]
F. A. Hayek
Philosopher · Economist · Professor
[3 works on this site]  · Referenced in 12 pieces
```

**Ratan Tata in "Extended liberal tradition" section:**
```
[portrait]
Ratan Tata
Industrialist
Referenced in 4 pieces
```

**Mukesh Ambani in "Referenced thinkers" section:**
```
[portrait]
Mukesh Ambani
Industrialist
[1 work on this site]
```

**Unclassified day-1 card:**
```
[portrait]
A. N. Agarwala
(no caption — vocations is [])
(no chip — worksAuthored is 0)
(no label — referencedIn is 0)
```

### 6.5 Accessibility

- Each section is a `<section>` with an `<h2>` heading + `<p>` blurb + grid. Page becomes properly hierarchical for screen readers (currently a flat list).
- Vocations caption uses a `<p>` (or `<span>` in a stack) — read in document order after the name, before the chips.
- Works chip is a `<span>` with no separate link; the outer card `<a>` is the link target. No new tab-stops introduced.
- Empty-section rule means crawlers/screen readers don't encounter misleading empty headings.

### 6.6 Pagefind facets

The Pagefind search index already exists for the site. Adding `data-pagefind-filter="vocation:economist"` (etc.) on cards makes vocation a queryable facet — future work to add a UI for it, but the index is populated automatically by this spec. Use a multi-value approach: emit one `data-pagefind-filter` attribute per vocation on the card.

Also emit `data-pagefind-filter="canon-status:core"` (etc.) so canon status itself is filterable.

## 7. Data migration

`scripts/migrate-thinker-classification.ts` (or `.py`; match existing repo conventions — `apps/site/src/lib/byline-resolution/` previously used Python, but content-touching scripts elsewhere may be TS. Verify during implementation.). Runs once, idempotent.

**Per-file behaviour:**

For every `apps/site/src/content/thinkers/*.md`:

1. If `canon_status:` is absent, insert a literal line `canon_status: unclassified\n` immediately after the `tradition:` line. Exact serialization — no quoting, no comments, no trailing whitespace.
2. If `vocations:` is absent, insert a literal line `vocations: []\n` immediately after the `canon_status:` line. The flow-style empty-array form `[]` (not block-style `vocations:\n  []` or `vocations:\n`). Exact serialization.
3. If `tradition: nationalist_liberal`, rewrite to `tradition: constitutional_liberal`.
4. If `tradition: reformer`, rewrite to `tradition: social_reformer`.
5. **Leave everything else untouched.** No changes to `tradition: international_influence` (kept as deprecated-but-valid), `draft`, `needs_review`, `bio_source`, or any other field.

The exact YAML shapes in (1) and (2) are what the §9.2 grep checks rely on. Deviating from them (e.g., emitting `canon_status: "unclassified"` with quotes) would silently fail the acceptance grep without breaking the build.

**What the script does NOT do:**

- No classification decisions — every entry ends as `canon_status: unclassified`, `vocations: []`.
- No file deletions, renames, or moves.
- No body-content edits.
- No commits — emits a single batched diff that a human commits as one atomic change.

**Verification after script run:**

```bash
# All 506 entries have the new fields
grep -c "^canon_status: unclassified$" apps/site/src/content/thinkers/*.md  # → 506
grep -c "^vocations: \[\]$" apps/site/src/content/thinkers/*.md             # → 506

# Renames complete
grep -c "^tradition: nationalist_liberal$" apps/site/src/content/thinkers/*.md  # → 0
grep -c "^tradition: reformer$" apps/site/src/content/thinkers/*.md             # → 0

# Renamed targets gained the right count
grep -c "^tradition: constitutional_liberal$" apps/site/src/content/thinkers/*.md  # → 53 (was 53 nationalist_liberal)
grep -c "^tradition: social_reformer$" apps/site/src/content/thinkers/*.md         # → 54 (was 44 social_reformer + 10 reformer)

# Deprecated value untouched
grep -c "^tradition: international_influence$" apps/site/src/content/thinkers/*.md # → 86

# Build clean
cd apps/site && pnpm build
```

## 8. Commit plan

Three commits, each independently buildable. The build is green at every commit boundary.

1. **`feat(schema): add canon_status + vocations + tradition.practice to thinker schema`**
   - `apps/site/src/schemas/people.ts` (or wherever the thinker schema lives) — add the three enum changes from §4.
   - No data files touched.
   - Build clean: existing thinkers don't reference the new fields yet, defaults apply.

2. **`feat(data): migrate thinker tradition values + populate new fields`**
   - `scripts/migrate-thinker-classification.ts` (new file) + 506 thinker MDs touched (53 renames + 10 merges + 506 field-additions).
   - Big diff but mechanical — every change traceable to the script.
   - Build clean: the schema from commit 1 accepts all post-migration values.

3. **`feat(ui): redesign /thinkers index with canon-status sections + vocation captions`**
   - `apps/site/src/pages/thinkers/index.astro` — rewritten per §6.
   - `apps/site/src/lib/thinker-stats.ts` — new helper per §5.
   - First commit where the page visibly changes.
   - On day 1: only "Awaiting classification" section renders (all 506 are unclassified). Visually different from today (section header + blurb + italic note), substantively the same (same alphabetical photo grid of same entries).

**Rollback story:** each commit is revertable independently. Commit 3 reverts to the flat-grid layout with data intact; commit 2 reverts to pre-migration values with schema permissive (still passes); commit 1 reverts the new fields entirely.

## 9. Validation criteria

These are the acceptance checks the implementation plan must reference. Each numbered criterion is independently verifiable.

### 9.1 Schema acceptance

1. `pnpm build` exits clean after all three commits land.
2. A deliberately-malformed thinker (`canon_status: invalid_value`) fails the build with a precise file:line + invalid-value + allowed-enum error message. Verified by one-minute negative test during implementation, then reverted.
3. `tradition: international_influence` continues to validate (86 entries still parse) — confirms the deprecated value stays accepted until sub-project 2.
4. `tradition: practice` validates — verified by setting it on one entry during implementation, then reverting (or leaving the seed in place if a curator wants to start the migration manually).

### 9.2 Migration acceptance

5. All thinker MDs have `canon_status: unclassified` after commit 2: `grep -c "^canon_status: unclassified$" apps/site/src/content/thinkers/*.md` → 506.
6. All thinker MDs have `vocations: []` after commit 2: `grep -c "^vocations: \[\]$" apps/site/src/content/thinkers/*.md` → 506.
7. Zero remaining `tradition: nationalist_liberal`: `grep -c "^tradition: nationalist_liberal$" ...` → 0.
8. Zero remaining `tradition: reformer`: `grep -c "^tradition: reformer$" ...` → 0.
9. `tradition: international_influence` count unchanged: `grep -c "^tradition: international_influence$" ...` → 86.
10. `git show --stat <commit-2-sha>` lists only thinker MDs + the migration script file. No other paths touched.

### 9.3 Page rendering acceptance (day-1 state)

11. `apps/site/dist/thinkers/index.html` exists and is well-formed.
12. Section headers render correctly per the empty-section rule:
    - `grep -c "Liberal canon" apps/site/dist/thinkers/index.html` → 0
    - `grep -c "Extended liberal tradition" apps/site/dist/thinkers/index.html` → 0
    - `grep -c "Referenced thinkers" apps/site/dist/thinkers/index.html` → 0
    - `grep -c "Awaiting classification" apps/site/dist/thinkers/index.html` → 1
13. The Awaiting section's grid contains the same set of thinkers the pre-change flat grid did. Exact assertion: `grep -oE 'href="/thinkers/[^"]+/"' apps/site/dist/thinkers/index.html | sort -u | wc -l` produces the same count post-migration as the equivalent grep on the pre-migration build (expected to be 402 — count of non-draft, language=en thinkers; verifiable by re-running the pre-build before commit 3).
14. No card shows a vocations caption (all `vocations: []` on day 1).
15. Cards for thinkers with `worksAuthored > 0` show the forest-tint works chip. Spot-check on `dadabhai-naoroji` (known to have authored primary-works).
16. Cards for thinkers with `referencedIn > 0` show the muted "Referenced in N pieces" label.
17. Cards with neither show no chip or label — only portrait + name.

### 9.4 Page rendering acceptance (day-N simulated state)

To prove the section structure works *when classifications exist*, temporarily seed 4 representative classifications, build, verify, then revert (sub-project 2 owns the real classification work):

18. Seed:
    | Thinker (slug) | canon_status | tradition | vocations |
    |---|---|---|---|
    | `f-a-hayek` (or equivalent — pick one that exists) | core | classical_liberal | [philosopher, economist, professor] |
    | `dadabhai-naoroji` | core | constitutional_liberal | [statesman, economist, writer] |
    | (a Tata entry if it exists, else any non-political figure) | extended | practice | [industrialist] |
    | (a Nehru entry if it exists, else any non-liberal) | referenced | non_liberal | [statesman, writer] |
19. After rebuild:
    - "Liberal canon" section renders with Hayek + Naoroji in it.
    - "Extended liberal tradition" section renders with the Tata entry.
    - "Referenced thinkers" section renders with the Nehru entry.
    - "Awaiting classification" renders with everyone else.
    - Vocation captions show `Philosopher · Economist · Professor` for Hayek, `Industrialist` for the Tata entry, etc.
20. After revert, the page returns to the §9.3 day-1 state.

### 9.5 Helper acceptance

21. `getThinkerStats()` returns a `Map` populated per the §5 contract — entries present iff the thinker has at least one non-zero count. Verifiable inline during implementation via a temporary `console.log` of a known case (e.g., `dadabhai-naoroji`). Expected: `{ worksAuthored: <n>, referencedIn: <m> }` with both positive. Numbers should reconcile to a hand-count from `grep -l "dadabhai-naoroji" apps/site/src/content/{primary-works,opinions,interviews,musings,theprint-mirror,periodicals}/*.md`.
22. Map.get(id) returns `undefined` for thinkers with both counts zero (per the §5 contract — entries are omitted, not zeroed). The page-rendering logic uses `stats.get(id) ?? { worksAuthored: 0, referencedIn: 0 }` to coalesce. No defensive zero-padding inside the helper.

### 9.6 Regression acceptance

23. `/gu/primary-works/khoj-march-april-2005/` still renders the saffron pill for PUCL Gujarat (the latest org-authorship test case).
24. `/organisations/pucl-gujarat/` still renders.
25. `/thinkers/<some-classified-thinker>/` detail page renders unchanged (new fields exist in frontmatter but aren't surfaced on the detail page — that's a future spec).
26. Total page count stays at 1185 (no routes added; thinkers index stays one route). Verifiable: `pnpm build` tail line `Indexed N pages` reads 1185 (same as pre-change).
27. Pagefind index emits `data-pagefind-filter="canon-status:<value>"` on every card and `vocation:<value>` on cards with vocations populated. The `canon-status:` filter key surfaces in the index immediately (every card has it). The `vocation:` filter key only surfaces after at least one thinker has a non-empty `vocations` array — which only happens after sub-project 2 (AI bulk classifier) or a curator manually populates entries. Day-1, expect `canon-status:` indexed and `vocation:` absent.

### 9.7 Stopping criteria

For the plan that follows this spec, "done" is:

- `pnpm build` clean
- §9.2 grep checks all match
- §9.4 simulated-state test passes (then reverted)
- §9.6 regression checks pass
- Three commits landed in order, each independently buildable

## 10. Data shape examples

Worked YAML frontmatter for the four canon-status tiers, to anchor what the migration produces and what curators (eventually, in sub-project 2) will fill in.

**A `core` figure (post-classification):**

```yaml
---
id: f-a-hayek
name:
  canonical: "F. A. Hayek"
  sort: "Hayek, F. A."
tradition: classical_liberal
canon_status: core
vocations:
  - philosopher
  - economist
  - professor
nationality: foreign
birth_year: 1899
death_year: 1992
needs_review: false
draft: false
---
```

**An `extended + practice` figure (post-classification):**

```yaml
---
id: j-r-d-tata
name:
  canonical: "J. R. D. Tata"
  sort: "Tata, J. R. D."
tradition: practice
canon_status: extended
vocations:
  - industrialist
nationality: india
birth_year: 1904
death_year: 1993
needs_review: false
draft: false
---
```

**A `referenced + non_liberal` figure (post-classification):**

```yaml
---
id: jawaharlal-nehru
name:
  canonical: "Jawaharlal Nehru"
  sort: "Nehru, Jawaharlal"
tradition: non_liberal
canon_status: referenced
vocations:
  - statesman
  - writer
nationality: india
birth_year: 1889
death_year: 1964
needs_review: false
draft: false
---
```

**A day-1 unclassified entry (immediately after commit 2):**

```yaml
---
id: a-n-agarwala
name:
  canonical: "A. N. Agarwala"
  sort: "Agarwala, A. N."
tradition: unclassified
canon_status: unclassified
vocations: []
nationality: india
bio_source: ai_drafted_stub
needs_review: true
draft: false
---
```

The day-1 entry is what every thinker looks like after commit 2 — the AI classifier and curator review (sub-projects 2 and 3) progressively populate the new fields.

## 11. Future work (out of this spec, but worth noting)

- **Sub-project 2: AI bulk classifier pipeline.** A cloud routine (claude -p batch via /schedule, same pattern as the 2026-05-22 byline-resolution pipeline) that reads each thinker's bio + the works referencing them + existing fields, proposes `{canon_status, tradition, vocations, confidence, reasoning}`, and writes outputs to a branch for curator review. Will clear the 86 `international_influence` entries and the day-1 backlog of unclassified.
- **Sub-project 3: Curator review tooling.** Whatever workflow makes reviewing AI proposals fast. Could be a CLI, a tracking issue, a `needs_review` filter on /thinkers, or a dedicated review UI. Decision deferred.
- **Thinker detail-page redesign.** Surface `canon_status`, `vocations`, and the works-on-site / referenced-in counts on `/thinkers/<slug>/`. Future spec.
- **Card filter UI.** A row of chips above the grid (`All / Liberal canon / Extended / Referenced` and/or `All vocations / Philosophers / Economists / Statesmen / Industrialists / etc.`) to collapse the page to one tier or one role. Pagefind already indexes these as facets per §6.6; the UI layer is the deferred bit.
- **Cross-axis statistics.** A small "by tradition" or "by vocation" breakdown panel on the thinkers index — e.g., "27 classical_liberals, 12 industrialists, 5 jurists." Deferred until the corpus is classified.
- **Apply the same three-axis scheme to organisations.** PUCL Gujarat (the recent org-authorship case) currently has `type: reform_society` + `ideology: [civil_libertarian]` — different axis names from thinkers, but conceptually similar. Harmonising the two would unify the editorial vocabulary; deferred until both sides settle.
