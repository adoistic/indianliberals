# CCS Feedback — Round 2 Fix Brief (2026-07-09)

Source: feedback email from CCS (aayushi@ccs.in), thread "IndianLiberals.in – Follow-up
Feedback & Fixes", 2026-06-30, reviewing the current rebuild.

This document is the **complete working spec** for one Claude Code session (or a series of
them) to fix the site. It expands each feedback item with: the issue, what the reviewer's
screenshot showed, the exact file(s) and line(s) involved, what to change, and how to know
it's done. Every meeting-scheduling ask from the email has been stripped — only the fixable
work remains.

The site is an **Astro** static site under `apps/site/`. Content lives in git-based content
collections (`apps/site/src/content/*`) plus authority YAML files (`content/authority/*.yaml`).

---

## How to work this brief

1. **Run the site and look before you touch anything.** Reproduce each issue in the browser
   preview so you're fixing the real thing, not a guess. Use the preview tools
   (`preview_start` → the site dev server; `preview_snapshot` / `preview_inspect` /
   `preview_screenshot`). Several items below (esp. #11, #19) need you to *see* the current
   state to locate the exact surface.
2. **Work top-to-bottom by priority** (see the priority table at the end). The quick,
   unambiguous fixes (#1, #2, #4, #5, #6, #15, #17, #19) can land first as one batch. The
   data/ingestion items (#7, #8, #9, #16) and the design rethinks (#12, #18) are larger and
   should be separate commits.
3. **Verify each fix in the preview before claiming it done.** Screenshot the before/after
   for the visual ones.
4. **Commit in coherent batches** with `data(...)` / `fix(site): ...` messages, and push to
   `origin/main` after a batch or two (don't push per-file).

### Two standing constraints from the client — do NOT violate

- **Never delete an entity CCS asks to "remove."** For #13 and #14, "remove INC / clean up the
  Political Party & Organisation sections" means **exclude it from that listing / reclassify /
  hide it from that surface — NOT delete the underlying record.** INC (and orgs like it) are
  referenced by thinker affiliations (Gokhale, Rajaji operated within Congress) and must remain
  as linkable entities. The redesign is about *presentation*, not deletion.
- **The final Home-page / Liberal-Canon author list is still pending from CCS** (Kumar Anand &
  Arjun are to send it). For #18, do the *photo-style standardisation* now; do **not** guess the
  membership list — leave the `featured: true` flag mechanism in place and wait for the list.

### Screenshots

The email included 6 inline PNG screenshots. They could not be extracted programmatically from
Gmail, so each is described in prose under its item below, marked **[Reviewer's screenshot]**.
Where a screenshot matters, reproduce it live in the preview to confirm you're looking at the
same thing.

---

## 1. Tagline styling — remove the logo, enlarge the line

**[Reviewer's screenshot]** The hero eyebrow line "A digital archive of the Indian liberal
tradition" rendered in small saffron all-caps with a tiny crane brand-mark icon crammed
immediately to its left.

- **File:** `apps/site/src/pages/index.astro:129-132`
- **Current markup:**
  ```html
  <p class="flex items-center gap-2.5 text-xs uppercase tracking-widest text-(--color-saffron-700) font-(family-name:--font-ui) font-semibold mb-5" data-reveal>
    <img src="/brand/brand-mark-crane.png" alt="" class="h-6 w-6" width="24" height="24" />
    A digital archive of the Indian liberal tradition
  </p>
  ```
- **Change:** Delete the `<img>`. Increase the line's font size (drop `text-xs uppercase
  tracking-widest`; use something substantially larger, e.g. `text-lg md:text-xl` — treat it as a
  readable subtitle, not a micro-eyebrow). Keep the saffron colour if it still reads well at the
  larger size; adjust `mb-5` spacing so the hero still balances.
- **Done when:** No logo beside the tagline; the tagline is visibly larger and reads as a proper
  standfirst under/over the H1.

## 2. Nav label — "The collection" → "Collections"

- **File:** `apps/site/src/components/Header.astro:40`
- The nav group is `{ id: "collection", label: "The collection", ... }`. (Note: the email said
  "The Collections"; the actual current string is **"The collection"**.)
- **Change:** Set `label: "Collections"`. Verify it updates both the desktop disclosure trigger
  and the mobile menu (the same `label` renders in both — Header.astro ~145 and ~237).
- **Done when:** Top nav reads "Collections".

## 3. Home bar graphs — make each bar a link to the work/decade

**[No screenshot]** The homepage decade histogram bars are plain, non-interactive `<div>`s.

- **File:** `apps/site/src/pages/index.astro:227-244` (the `<figure>` / `.histogram` block; bars
  are the per-decade `<div>`s at ~230-234). Data comes from the `decades` array computed at
  `index.astro:61-81`.
- **Change:** Wrap each bar in an `<a>`. Each bar represents a decade → link it to the
  primary-works listing filtered/anchored to that decade (e.g. `/primary-works/?decade=1950s`
  or an anchor the primary-works index understands). If the primary-works index has no decade
  filter yet, the smallest correct fix is to link the bar to `/primary-works/` with the decade
  pre-selected; confirm the index page can receive that. Keep the existing hover styling and the
  `title` tooltip; add an `aria-label` per bar ("45 works from the 1950s").
- **Done when:** Hovering a bar shows a pointer cursor and clicking navigates to that decade's
  works.
- **Note:** The reviewer literally said "hyperlink to the work" — but each bar is a *decade*
  (many works), not a single work. Linking to the decade-filtered listing is the correct
  interpretation; flag this back to CCS if they meant something else.

## 4. Content review — fix AI-flavoured / awkward copy (fixable portion)

The email flags editorial copy that reads as machine-written, with the homepage as the named
example. The meeting to review the *rest* of the site's copy is out of scope here; fix the
concrete named instances and do a pass over the hard-coded editorial strings.

- **Named instance — homepage:** `apps/site/src/pages/index.astro:251-256`
  - `<h2>Begin in the stacks</h2>` and the paragraph
    *"Four ways into the collection — by work, by run, by voice, by thinker."*
  - Rewrite in plain, human, archival English. Avoid the "N ways into…" listicle cadence and the
    "Begin in the stacks" conceit if it reads as strained. (This overlaps with #5 — the em dash
    in that sentence must go regardless.)
- **Do a sweep** of hard-coded editorial copy in these page/component files (these are the
  files with the most prose): `index.astro`, `about.astro`, and the `*Detail.astro` components.
  Look for: over-clever metaphors ("stacks", "doorways", "voices"), the rule-of-three listicle
  pattern, and promotional filler. Rewrite to be direct and concrete.
- **Done when:** The homepage intro copy is plain and human; no "Four ways into the collection"
  listicle phrasing remains.
- **Caveat:** This is inherently a judgement call and CCS wants to review the full site's copy in
  a call. Fix the obvious homepage instances; leave a short list in your commit message of other
  spots you rewrote so CCS can spot-check.

## 5. Em dashes — remove throughout

Em dashes (—) read as AI-generated to the client. Remove them site-wide, replacing with a
comma, a colon, parenthesis, or a full stop / sentence break as the grammar requires (do **not**
mechanically swap `—` → ` - ` everywhere; read each sentence).

- **Hard-coded editorial copy (~103 em dashes across 12 files):** these are the priority because
  they're on every page. Per-file counts:

  | File | count |
  |---|---|
  | `components/ThinkerDetail.astro` | 23 |
  | `pages/index.astro` | 22 |
  | `components/PrimaryWorkDetail.astro` | 15 |
  | `components/MusingDetail.astro` | 10 |
  | `components/OrganisationDetail.astro` | 10 |
  | `components/OpinionDetail.astro` | 8 |
  | `pages/about.astro` | 5 |
  | `components/Header.astro` | 3 |
  | `components/OrgMark.astro` | 2 |
  | `layouts/BaseLayout.astro` | 2 |
  | `ContributorCard / PeopleInPiece / RelatedSection / Search` | 1 each |

- **Content markdown (`apps/site/src/content/**/*.md`):** thousands more em dashes live in
  frontmatter (bio_note, description, blurbs) and body prose. Handle these carefully — an em dash
  inside a *quoted primary-source passage* is legitimate and must be preserved; only rewrite the
  *our-voice* editorial fields (descriptions, bios, blurbs, summaries). A blind find-replace over
  all `.md` files WILL corrupt quoted historical text — do a field-scoped pass (frontmatter
  editorial fields + AI-summary fields), not a global replace.
- **Done when:** No em dashes in the hard-coded UI copy; editorial (our-voice) content fields
  de-dashed; quoted source text untouched. Suggest adding a lint/CI check that flags new `—` in
  UI files so they don't creep back.

## 6. Birth/death dates — Sauvik Chakraverti & D. R. Pendse

- **Schema:** `apps/site/src/content.config.ts:48-49` — `birth_year` / `death_year`
  (`z.number().int().nullable().optional()`). Same fields exist in the authority YAML.
- **Authority records:** `content/authority/thinkers.yaml`
  - **Sauvik Chakraverti** (`id: sauvik-chakraverti`, ~line 325): `birth_year: 1957  # [NEEDS
    REVIEW]`, `death_year: 2018`. Death is set; birth is flagged uncertain. Confirm the real
    birth year and remove the NEEDS REVIEW flag. (Reviewer spelled it "Chakravarti"; canonical
    data spelling is **Chakraverti**.)
  - **D. R. Pendse** (`id: d-r-pendse`, ~line 292): `birth_year: null`, `death_year: null` — both
    missing. Fill both. Economist associated with Tata and the Forum of Free Enterprise. His
    thinker markdown (`apps/site/src/content/thinkers/d-r-pendse.md`) has a garbled bio line
    ("born on 6 September 1930/ 7 September 1969") that looks like an OCR/data error — resolve it
    to the correct dates.
- **Also update** the corresponding `apps/site/src/content/thinkers/{sauvik-chakraverti,d-r-pendse}.md`
  frontmatter if dates are duplicated there (the thinker markdown carries its own `birth_year` /
  `death_year:7`).
- **Research required:** You need the real dates. Verify from a reliable source and cite it in the
  commit message. Do not invent dates; if a date genuinely can't be confirmed, say so rather than
  guessing.
- **Done when:** Both thinkers render birth–death dates on their profile pages and in the
  featured rail, with no NEEDS REVIEW flags.

## 7. Freedom First — upload all 552 pieces  *(large ingestion task)*

Freedom First (the Indian liberal monthly) is **not yet in the corpus at all**. CCS wants all
**552** pieces uploaded.

- This is an **ingestion job**, not a code fix. Source scans/PDFs are on the curator's external
  drive ("One Touch"), not in the repo. It follows the established primary-works ingestion
  pipeline (extraction → bake → enrich → `.md` in `apps/site/src/content/primary-works/` with
  `work_type: "periodical_issue"` and a `series`/slug that groups them as "Freedom First").
- **Drive per the project's ingestion workflow: in-session Agent subagents**, not
  `claude -p` / overnight runners (those have been unreliable — rate stalls, SUMMARY_FAILED).
- **Blocked-on:** confirmation that the Freedom First source files are present on the drive and
  accessible from this machine. If they aren't mounted, surface that — this item can't proceed
  without the scans.
- **Done when:** Freedom First appears as its own series in `/periodicals/` with its issues
  ingested (target 552), each linking to a primary-work detail page. Given the volume, land it in
  batches and push periodically.

## 8. Indian Libertarian — finish the transfer

Only ~4 Indian Libertarian pieces currently surface in Periodicals, but the collection actually
holds **~100+** `the-indian-libertarian-*.md` issue files (they exist under
`apps/site/src/content/primary-works/`). So this is likely a **grouping/surfacing bug**, not
missing data — the periodicals page isn't collecting them all under the "Indian Libertarian"
series (see #10 for the grouping heuristic).

- **Investigate first:** count how many `the-indian-libertarian-*` primary-works exist vs how many
  the periodicals page groups under that series. The series-detection heuristic is at
  `apps/site/src/pages/periodicals/index.astro:26-33` (slug-prefix / title-regex). If issues are
  slipping into "Other" or not matching, fix the heuristic (ideally add an explicit
  `series: "indian-libertarian"` field to the frontmatter rather than relying on slug regex).
- If some issues genuinely aren't ingested yet, treat the remainder like #7 (ingestion from the
  drive).
- **Done when:** All Indian Libertarian issues in the corpus appear under one "The Indian
  Libertarian" series on `/periodicals/`, and the "only 4 showing" symptom is gone.

## 9. Missing periodicals — add Forum for Free Enterprise, Swatantra Party, Indian Liberal Group

The Periodicals section is missing three runs. Note these three are also **organisations**
(they exist in `content/authority/organisations.yaml`), so this is about adding their
*periodical/publication output* as a periodical series.

- **Depends on source material:** if the scanned issues/pamphlets exist on the drive, ingest them
  as `periodical_issue` primary-works with the appropriate `series` and register the series in the
  `SERIES` metadata block at `apps/site/src/pages/periodicals/index.astro:35-62` (add entries like
  `forum-for-free-enterprise`, `swatantra-party`, `indian-liberal-group` with blurbs, alongside
  the existing `khoj` / `indian-libertarian` / `liberal-times` / `shetkari-sanghatak`).
- **Done when:** Each of the three appears as a clickable series on `/periodicals/` with its
  issues. If source scans for any of them aren't available, ingest what exists and report the gap.

## 10. Periodicals page layout — series-first, each clickable

**[No screenshot]** Currently opening `/periodicals/` dumps all **Khoj** issues first and you must
scroll to reach the other runs — it reads as a flat wall of one series.

- **File:** `apps/site/src/pages/periodicals/index.astro` (series grouped and rendered at
  ~150-204; issue cards ~173-183; order array at ~109).
- **Change:** Redesign so the **landing view shows the set of periodical *series* up front** — one
  card/tile per run (Khoj, The Indian Libertarian, Liberal Times, Shetkari Sanghatak, plus the
  new ones from #9), each with cover + name + issue count. Clicking a series reveals/opens that
  run's individual issues (either an in-page expand, or a dedicated
  `/periodicals/<series>/` page). Do **not** render every issue of every series flat on load.
- **Done when:** `/periodicals/` opens to a clean grid of periodical titles; no single series'
  issues dominate the top; each title is clickable through to its issues.

## 11. Thinker work-count mismatch — align home vs People to *authored-only*

**[Reviewer's screenshot ×2]** Two screenshots of the same thinker showing **different work
counts** on two surfaces. The reviewer's diagnosis: the higher count is pulling in ThePrint
pieces that merely *mention* the thinker, not pieces they *authored*.

- **Root cause (confirmed):** `apps/site/src/components/ThinkerDetail.astro:102-104,137-139`
  counts ThePrint-mirror pieces via `related_thinkers[]` (i.e. *mentions*), and folds them into
  the same `authorshipCount` as authored works. ThePrint entries have no author ref, only
  `related_thinkers[]` (see `apps/site/src/lib/thinker-stats.ts:130-166`).
- **Good news:** `apps/site/src/lib/thinker-stats.ts` **already separates** `worksAuthored` from
  `referenced` (see `applyEntry`, lines ~59-62: "authored wins", then `bump(id, "worksAuthored")`).
  So the counting primitives exist — the surfaces just need to display the same field.
- **Change:**
  1. Reproduce both surfaces live to identify exactly which two are disagreeing (the homepage
     featured rail shows *dates only* — the "home" count in the screenshot is likely the Thinkers
     landing page `pages/thinkers/index.astro` search-index count, or a card count; confirm by
     looking). 
  2. Make **both** surfaces read the **same** number from `thinker-stats.ts` — the
     *authored* count (`worksAuthored`), excluding mere ThePrint mentions. If a "mentioned in N
     pieces" figure is still wanted, show it as a **separate, labelled** stat, never merged into
     the headline work count.
- **Done when:** The same thinker shows an identical, authored-only work count on both surfaces;
  ThePrint "mention" pieces no longer inflate it.

## 12. People section — broader rethink  *(design task; scope carefully)*

CCS wants to "rethink the entire People section and its sub-sections." This is a design item, not
a defined fix. Current structure to work from:

- `apps/site/src/pages/thinkers/index.astro` — "The Indian liberal canon" landing: a people
  search over all thinkers (~361), plus two curated rails — **Canon** (`featured: true` &
  `nationality: "india"`) and **International Influences** (`featured: true` & non-India),
  chronological by `birth_year`; and a link to the **Full directory**
  (`pages/thinkers/directory/index.astro`).
- `components/ThinkerCard.astro`, `components/ThinkerDetail.astro`.
- Featured membership is driven purely by the `featured: true` frontmatter flag (Sveltia-editable).
- **How to proceed:** This overlaps with #18 and with the pending author list from CCS. Do **not**
  do a speculative redesign now. Instead: (a) make the concrete sub-fixes (#11 count, #18 photo
  style), (b) write a short proposal of options for restructuring the People section /
  sub-sections and leave it for CCS review. Treat the full rethink as blocked on CCS direction.

## 13. Political Party section — INC should not appear as a party

**[No screenshot]** The Organisations "Political Party" grouping currently lists the **Indian
National Congress**, which CCS says shouldn't be there.

- **Confirmed present:** `content/authority/organisations.yaml:169` (`id: indian-national-congress`,
  `type: political_party`) and the rendered org `apps/site/src/content/organisations/indian-national-congress.md`.
- Orgs are grouped by `type` on `apps/site/src/pages/organisations/index.astro` (TYPE_ORDER at
  ~14-43). Current `political_party` orgs: swatantra-party, all-india-liberal-federation,
  congress-socialist-party, liberal-party-of-sri-lanka, **indian-national-congress**.
- **Change (respecting the no-delete rule):** Remove INC **from the Political Party listing** —
  do NOT delete the record. Options: exclude non-liberal parties from the org index grouping (e.g.
  a `hide_from_index: true` flag, or filter the political_party group to liberal parties only), so
  INC still exists as a linkable entity referenced by thinker affiliations, but isn't presented as
  one of "our" political parties. Audit the other four party entries too and confirm each belongs
  (congress-socialist-party is borderline — flag for CCS).
- **Done when:** The Political Party section on `/organisations/` no longer shows INC (or other
  non-liberal parties), but INC's page/links from affiliations still resolve.

## 14. Organisation category — same cleanup

Apply the same audit to the whole Organisations listing: remove/hide entities that don't belong
under "our" organisations while **keeping the records** (same no-delete rule as #13). Review each
`type` group on `apps/site/src/pages/organisations/index.astro` for entries that are referenced-only
(mentioned via affiliations) versus genuinely part of the liberal ecosystem, and present only the
latter. Report the list of hidden/reclassified orgs for CCS sign-off.

## 15. Category filters — remove "Stance", "Scale", "Period"

**[Reviewer's screenshot]** A filter chip bar with facet groups labelled **Period**, **Stance**,
and **Scale**.

- **Location (corrected):** these facets are **not** on the organisations page. They're the filter
  UI on the **musings** and **opinions** index pages:
  - `apps/site/src/pages/musings/index.astro` — `Period` (~129), `Stance` (~148), `Scale` (~167);
    filter wiring at ~382, ~414-416.
  - `apps/site/src/pages/opinions/index.astro` — same headings at ~129/148/167; wiring ~383,
    ~415-416.
  - (The email said "first party section under the Category section" — this maps to the first
    filter block on these listing pages.)
- **Change:** Remove the Period, Stance, and Scale filter groups (the `<h3>` + their chips) and the
  associated JS filter handlers (`filterPeriod` / `filterStance` / `filterScale`, the `toggle`
  branches, and any `period`/`stance`/`scale` state). Leave whatever other filter(s) CCS wants
  (e.g. a theme/topic or year filter) intact and working. Confirm the client-side filtering JS
  still runs with those branches removed.
- **Done when:** Those three facet groups are gone from both listing pages and the remaining
  filters still work.

## 16. ThePrint — Hindi pieces + automatic Saturday updates

Two parts:

- **(a) Upload the Hindi ThePrint pieces.** The ThePrint mirror (`apps/site/src/content/theprint-mirror/`,
  ~49 files) doesn't include the Hindi-language column pieces yet. The ingest worker
  (`apps/theprint-ingest/src/index.ts`) has no language filtering visible — determine why Hindi
  pieces are absent (feed source? a filter upstream? they were never backfilled) and ingest them.
  The site already supports Hindi indexing (Pagefind per-language analyzers), so Hindi mirror
  entries should render + search fine.
- **(b) Auto-update every Saturday.** The ingest worker is a Cloudflare Worker that PUTs new RSS
  items via the GitHub Contents API; it supports a cron trigger via `apps/theprint-ingest/wrangler.toml`
  and a manual `X-Ingest-Token` POST override. Set/confirm the cron to run **weekly on Saturday**
  (e.g. `cron = ["0 6 * * 6"]`) and confirm it's actually deployed (the worker was scaffolded but
  "NOT yet deployed" per the repo README — deployment may be the real blocker here).
- **Done when:** Hindi ThePrint pieces are in the mirror and searchable; the ingest worker's cron
  is set to Saturday and deployed (or the deployment dependency is clearly surfaced).

## 17. About section — give "What you'll find here" a visual layout

**[Reviewer's screenshot]** The "What you'll find here" section is a flat wall of paragraph text;
CCS wants a proper visual structure.

- **File:** `apps/site/src/pages/about.astro:23-26` — an `<h2>What you&rsquo;ll find here</h2>`
  followed by two `<p>` paragraphs describing Tier A (musings, opinions, interviews, thinker
  profiles, org pages, ThePrint mirror) and Tier B (primary works + periodical PDFs).
- **Change:** Replace the prose with a designed layout — e.g. a card/grid of the **eight content
  kinds** grouped into the **two tiers**, each with a short label + one-line description (and
  optionally an icon and a link to that section's index). Keep it on-brand with the rest of the
  site (existing Tailwind + CSS-variable design tokens). This is a self-contained design
  improvement — make it genuinely structured, not just bolded text.
- **Done when:** The section renders as a clear visual grouping of content types across the two
  tiers, not a paragraph block.

## 18. Home / Liberal-Canon authors — standardise photos to B&W  *(list pending)*

Two parts; only one is actionable now:

- **(a) Final author list — BLOCKED.** CCS will send the specific list of people to feature on the
  Home page and in the Liberal Canon. **Do not guess it.** The mechanism already exists: the
  `featured: true` frontmatter flag selects the rails (`pages/thinkers/index.astro`, homepage rail
  at `index.astro:360-392`). When the list arrives, set flags accordingly.
- **(b) Standardised black-and-white photo style — DO NOW.** The homepage featured rail already
  uses a pre-generated **duotone** portrait (`t.data.portrait.duotone`, `index.astro:370`),
  produced by `scripts/synthesis/make-duotone-portraits.py`. Make the treatment **consistent
  black-and-white across every featured portrait** — run/extend that script so every featured
  thinker has a duotone/B&W asset in the same style (uniform contrast, framing, background), and
  ensure the fallback chain (`portrait.duotone → caricature → ring_portrait → photo`) doesn't let
  a stray colour photo through on the home/canon rails. Any thinker missing a duotone should get
  one, not fall back to a colour photo.
- **Done when:** Every portrait on the home + canon rails is the same B&W/duotone treatment; no
  colour photos slip through. (Membership left to the pending list.)

## 19. Odd white space at top on load

**[Reviewer's screenshot]** On first load the homepage shows a large empty white band at the very
top, above the visible content.

- **Reproduce first** in the preview (hard reload) — this one you must *see* to diagnose. Capture a
  screenshot at desktop and mobile widths.
- **Suspects to check:**
  - Hero top padding: `apps/site/src/pages/index.astro:127` — `py-16 md:py-24` (96px top on
    desktop). Combined with the sticky header this may read as a big gap.
  - Sticky header + `scroll-padding-top: 5.5rem` on `<html>` (`layouts/BaseLayout.astro:84`) and
    header height ~88px (`components/Header.astro:118-122`).
  - **Reveal animation:** hero content has `data-reveal` with staggered `--reveal-delay`
    (`index.astro:129+`). If the reveal animation starts from an offset/opacity:0 state and the JS
    is slow or fails, the content sits invisible → perceived white gap on load. Check the reveal
    CSS/JS init and whether there's a no-JS / pre-hydration flash.
- **Change:** Fix whichever it is — most likely reduce the hero top padding and/or ensure the
  reveal animation's initial state doesn't leave a tall empty region before content paints (e.g.
  reserve no extra vertical offset, or render content visible-by-default and animate in without
  reserving blank space).
- **Done when:** The homepage paints with content near the top on load; no large empty band above
  the hero at any width.

---

## Priority / batching

| Batch | Items | Nature | Blockers |
|---|---|---|---|
| **A — quick UI fixes** | 1, 2, 4 (homepage copy), 5 (UI files), 15, 17, 19 | Small, unambiguous edits | none |
| **B — data/logic fixes** | 3, 6, 11, 13, 14 | Code + small data edits | #6 needs verified dates; #11 needs live repro |
| **C — periodicals** | 8, 10, 9 | Grouping redesign + some ingestion | #9 needs source scans |
| **D — ingestion (large)** | 7, 16(a) | Bulk content ingestion | source PDFs on external drive must be mounted; use in-session Agent subagents |
| **E — infra/design (needs CCS)** | 12, 16(b), 18 | Design rethink / deploy / pending list | #12 & #18(a) blocked on CCS; #16(b) blocked on worker deploy |

Start with Batch A (fast wins, all landable today), then B. C/D/E depend on source material,
deployment, and CCS's pending inputs — surface those blockers early rather than guessing.

## Reference

- Site root: `apps/site/` · Content: `apps/site/src/content/` · Authority YAML:
  `content/authority/{thinkers,organisations,publishers}.yaml`
- Shared thinker counting: `apps/site/src/lib/thinker-stats.ts`
- ThePrint ingest worker: `apps/theprint-ingest/`
- Duotone portraits: `scripts/synthesis/make-duotone-portraits.py`
- Build quirk to watch: Pagefind has a symlink build step — see prior handoffs if the search
  index fails to build.
