# Organisational Authorship Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let primary-works' `authors[]` and `editors[]` reference either thinkers or organisations, render org entries with a saffron "organisation" pill in the byline, and migrate `pucl-gujarat` from a thinker stub to a proper organisation.

**Architecture:** Zod `z.union` of two `reference()` arms on the existing array fields; build-time slug-uniqueness check across the two collections enforces the invariant that the union depends on; UI discriminates by `ref.collection` and routes to the right detail-page URL.

**Tech Stack:** Astro 5 content collections, Zod, Tailwind 4 (the `text-(--color-...)` utility forms already used in the codebase).

**Spec reference (read this before starting):**
- [`docs/superpowers/specs/2026-05-23-organisational-authorship-design.md`](../specs/2026-05-23-organisational-authorship-design.md) — design + acceptance criteria, locked

**Pre-flight reading (in order, before Chunk 1):**
- `apps/site/src/content.config.ts` lines 41-110 — thinkers + organisations defineCollection
- `apps/site/src/content.config.ts` lines 234-330 — primaryWorks defineCollection (the `authors:` and `editors:` lines are what change)
- `apps/site/src/pages/primary-works/[slug].astro` lines 39-43, 80, 127-133 — the byline rendering you'll modify
- `apps/site/src/content/organisations/centre-for-civil-society.md` — sample organisation frontmatter shape

**Working directory:** the repo root `/Users/siraj/Indian Liberals Website` on `main`. All git operations target `main` unless otherwise noted.

**Verification harness:**
- Schema/build: `cd apps/site && pnpm build` (1185 pages should still emit cleanly post-migration: 1131 + 55 stubs - 1 thinker + 1 org = 1186; the migration is a swap so net change is zero against the pre-Chunk-3 number).

**Spec deviations logged here:** none expected. The spec is locked at commit `4357e89`.

---

## File Structure

**Created (new files):**

```
apps/site/src/lib/check-slug-uniqueness.ts          # Chunk 1: cross-collection slug invariant
apps/site/src/content/organisations/pucl-gujarat.md # Chunk 3: the migrated org
```

**Modified:**

```
apps/site/src/content.config.ts                                   # Chunk 1: union the schemas + side-effect import
apps/site/src/pages/primary-works/[slug].astro                    # Chunk 2: discriminated byline render
apps/site/src/content/primary-works/khoj-march-april-2005.md      # Chunk 3: trim stubs_referenced[]
```

**Deleted:**

```
apps/site/src/content/thinkers/pucl-gujarat.md                    # Chunk 3: stub retired
```

---

## Chunk 1: Schema union + slug-uniqueness check

Two coupled changes: extend the schema to accept org refs, add a build-time guard against duplicate slugs across the two collections. End state: build still passes; nothing visible yet, but the schema can now accept an org slug in `authors[]` or `editors[]` once one exists on disk.

### Task 1.1: Add the slug-uniqueness check

**Files:**
- Create: `apps/site/src/lib/check-slug-uniqueness.ts`

- [ ] **Step 1.1.1: Write the check**

Create `apps/site/src/lib/check-slug-uniqueness.ts` with exactly this content:

```ts
// Enforces the invariant that a slug is unique across the union of the
// thinkers/ and organisations/ collections. The primaryWorks.authors[] schema
// is a Zod union over reference('thinkers') | reference('organisations');
// the union resolves by trying each arm in order, so a slug that exists in
// BOTH collections would silently route to thinkers and never to organisations.
// See docs/superpowers/specs/2026-05-23-organisational-authorship-design.md §6.
import { readdirSync } from "node:fs";
import { resolve } from "node:path";

const CONTENT = resolve(import.meta.dirname, "../content");

const slugsOf = (dir: string) =>
  new Set(
    readdirSync(resolve(CONTENT, dir))
      .filter((f) => f.endsWith(".md"))
      .map((f) => f.replace(/\.md$/, "")),
  );

const thinkers = slugsOf("thinkers");
const orgs = slugsOf("organisations");
const overlap = [...thinkers].filter((s) => orgs.has(s));

if (overlap.length) {
  throw new Error(
    `Slug overlap between thinkers/ and organisations/: ${overlap.join(", ")}. ` +
      `A slug must be unique across the union of these collections (see ` +
      `docs/superpowers/specs/2026-05-23-organisational-authorship-design.md §6).`,
  );
}
```

- [ ] **Step 1.1.2: Verify it runs in isolation (before wiring it up)**

Run with `tsx` or `node --experimental-strip-types`. From the repo root:

```bash
cd apps/site && pnpm exec tsx src/lib/check-slug-uniqueness.ts && echo "OK"
```

Expected: `OK` (no overlap exists yet). If `tsx` isn't available, skip this step — Step 1.2.3's build will exercise the check.

### Task 1.2: Wire the schema union + side-effect import

**Files:**
- Modify: `apps/site/src/content.config.ts`

- [ ] **Step 1.2.1: Add the side-effect import at the top of the file**

Find the import block at the top of `apps/site/src/content.config.ts`. After the existing imports (Zod, glob, helpers), add this line on its own:

```ts
import "./lib/check-slug-uniqueness";
```

The import has no exports — its sole purpose is to run the invariant check at config-load time.

- [ ] **Step 1.2.2: Union the two ref fields in `primaryWorks`**

Find the two lines in the `primaryWorks = defineCollection({ ... })` block (around lines 253-254):

```ts
authors: z.array(reference('thinkers')).default([]),
editors: z.array(reference('thinkers')).default([]),
```

Replace with:

```ts
authors: z.array(z.union([reference('thinkers'), reference('organisations')])).default([]),
editors: z.array(z.union([reference('thinkers'), reference('organisations')])).default([]),
```

No other changes to this file.

- [ ] **Step 1.2.3: Build to verify**

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: build completes; page count unchanged from before (~1186); no Zod errors; no "slug overlap" error. The slug-uniqueness check fires silently because no overlap exists.

- [ ] **Step 1.2.4: Quick negative test of the invariant**

Verify the invariant check actually fires when violated. Temporarily create a duplicate slug:

```bash
touch apps/site/src/content/organisations/charan-singh.md
cd apps/site && pnpm build 2>&1 | grep -E "Slug overlap|overlap"
```

Expected: an error message mentioning `Slug overlap` and `charan-singh`. Then remove the test file:

```bash
rm apps/site/src/content/organisations/charan-singh.md
cd apps/site && pnpm build 2>&1 | tail -3
```

Expected: clean build again. (If the build is fast enough that this is annoying, skip — Step 1.2.3 is the primary gate. But running it once confirms acceptance criterion #2 from the spec.)

- [ ] **Step 1.2.5: Commit**

```bash
git add apps/site/src/lib/check-slug-uniqueness.ts apps/site/src/content.config.ts
git commit -m "$(cat <<'EOF'
feat(schema): allow organisations as primary-work authors/editors

primaryWorks.authors[] and primaryWorks.editors[] now accept slugs that
resolve to EITHER the thinkers or organisations collection, via a Zod
union of two reference() arms. The union picks the first arm that
resolves the slug; the new lib/check-slug-uniqueness.ts side-effect
import enforces the invariant that no slug exists in both collections
at once (which would make the second arm silently unreachable).

Frontmatter shape is unchanged — a bare slug like `- pucl-gujarat`
keeps working; Astro resolves it to {id, collection} at runtime so
consumers can discriminate.

Build still clean; no data references an organisation in authors[]
yet, but the schema accepts the case.

Refs docs/superpowers/specs/2026-05-23-organisational-authorship-design.md
EOF
)"
```

---

**End of Chunk 1.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 2: UI byline rendering

Discriminated lookup in the primary-work detail page, with a saffron pill next to organisational authors. No data changes — this chunk just teaches the renderer to handle both arms of the union the schema now allows.

### Task 2.1: Update the byline renderer in `[slug].astro`

**Files:**
- Modify: `apps/site/src/pages/primary-works/[slug].astro` (~lines 39-43, 80, 127-133)

- [ ] **Step 2.1.1: Locate the lines**

```bash
grep -n "allThinkers\|thinkersById\|authorEntries\|authorSlugs" apps/site/src/pages/primary-works/\[slug\].astro
```

Confirm the structure matches the spec: `allThinkers`/`thinkersById` at ~39-40, `authorEntries` at ~41-43, `authorSlugs` at ~80, the byline JSX at ~127-133. If line numbers have shifted, locate by anchor strings, not by absolute line.

- [ ] **Step 2.1.2: Replace the lookup block (~lines 39-43)**

Find:

```ts
const allThinkers = await getCollection("thinkers");
const thinkersById = new Map(allThinkers.map((t) => [t.id, t]));
const authorEntries = (fm.authors ?? [])
  .map((ref) => thinkersById.get(ref.id ?? (ref as unknown as string)))
  .filter((t): t is NonNullable<typeof t> => !!t);
```

Replace with:

```ts
const allThinkers = await getCollection("thinkers");
const allOrgs = await getCollection("organisations");
const thinkersById = new Map(allThinkers.map((t) => [t.id, t]));
const orgsById = new Map(allOrgs.map((o) => [o.id, o]));

type AuthorEntry =
  | { kind: "thinker"; id: string; name: string }
  | { kind: "organisation"; id: string; name: string };

const authorEntries: AuthorEntry[] = (fm.authors ?? [])
  .map((ref): AuthorEntry | null => {
    const id = ref.id;
    if (ref.collection === "organisations") {
      const o = orgsById.get(id);
      return o ? { kind: "organisation", id, name: o.data.name.canonical } : null;
    }
    const t = thinkersById.get(id);
    return t ? { kind: "thinker", id, name: t.data.name.canonical } : null;
  })
  .filter((e): e is AuthorEntry => !!e);
```

Note: the `(ref as unknown as string)` cast from the prior code is gone. The union schema guarantees `ref.id` is a string and `ref.collection` is one of the two collection names; the cast is no longer needed.

- [ ] **Step 2.1.3: Update the `authorSlugs` derivation (~line 80)**

Find:

```ts
const authorSlugs = authorEntries.map((t) => t.id);
```

Replace with:

```ts
const authorSlugs = authorEntries
  .filter((e): e is Extract<AuthorEntry, { kind: "thinker" }> => e.kind === "thinker")
  .map((e) => e.id);
```

This keeps the "People in this piece" chip section (which consumes `authorSlugs`) thinker-only — organisations shouldn't appear in that block.

- [ ] **Step 2.1.4: Update the byline JSX (~lines 127-133)**

Find:

```astro
{authorEntries.length > 0
  ? authorEntries.map((t, i) => (
      <>
        <a href={`/thinkers/${t.id}/`} class="text-(--color-forest-700)">{t.data.name.canonical}</a>
        {i < authorEntries.length - 1 ? ", " : ""}
      </>
    ))
  : bylineFallback}
```

Replace with:

```astro
{authorEntries.length > 0
  ? authorEntries.map((e, i) => (
      <>
        {e.kind === "organisation" ? (
          <>
            <a href={`/organisations/${e.id}/`} class="text-(--color-saffron-700)">{e.name}</a>
            <span class="ml-1 inline-block align-middle px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-(family-name:--font-ui) font-semibold bg-(--color-saffron-100) text-(--color-saffron-700)">organisation</span>
          </>
        ) : (
          <a href={`/thinkers/${e.id}/`} class="text-(--color-forest-700)">{e.name}</a>
        )}
        {i < authorEntries.length - 1 ? ", " : ""}
      </>
    ))
  : bylineFallback}
```

Note: the iteration variable is now `e` (an `AuthorEntry`), so `t.data.name.canonical` becomes `e.name`. Don't miss this rename.

- [ ] **Step 2.1.5: Build to verify**

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: clean build. The byline rendering is exercised but no entry currently has an org in `authors[]` — visual effect lands in Chunk 3.

- [ ] **Step 2.1.6: Spot-check a person-only primary-work renders unchanged**

```bash
grep -A2 "class=\"text-(--color-forest-700)\"" apps/site/dist/primary-works/free-enterprise-and-democracy-a-d-shroff-feb11-1956/index.html | head -5
```

Expected: A. D. Shroff renders as a forest-green link, byline structure intact. (Use any primary-work id that has known thinker authors if this one isn't built — `grep -l "authors:" apps/site/src/content/primary-works/*.md | shuf -n 1` picks one.)

- [ ] **Step 2.1.7: Commit**

```bash
git add apps/site/src/pages/primary-works/\[slug\].astro
git commit -m "$(cat <<'EOF'
feat(ui): byline distinguishes organisational authors with saffron pill

The primary-work detail page now resolves authors[] refs against BOTH
the thinkers and organisations collections, discriminating on the
ref.collection field. Person-author links continue to render with
forest-green text and route to /thinkers/<slug>/. Organisational
authors get a saffron-700 link and an inline saffron-100 pill labelled
"organisation" so readers can tell at a glance which authors are
institutions rather than individuals, and click through to
/organisations/<slug>/.

The authorSlugs derivation that feeds the "People in this piece" chip
block is now filtered to thinker entries only — organisations don't
belong in that section.

Defensive `(ref as unknown as string)` cast removed: the Zod union
guarantees ref.id is a string and ref.collection is set, so the
fallback is no longer needed (and would silently drop org references
if left in).

No change to primary-works/index.astro per spec §5.3: the card-list
byline reads from contributors[].role==='author', not authors[], so
organisational authorship doesn't surface there.

Refs docs/superpowers/specs/2026-05-23-organisational-authorship-design.md
EOF
)"
```

---

**End of Chunk 2.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 3: Migrate pucl-gujarat + final verification

The data move that activates the visual treatment from Chunk 2. End state: build clean, byline on Khoj 2005 shows the pill, `/organisations/pucl-gujarat/` renders, `/thinkers/pucl-gujarat/` 404s.

### Task 3.1: Create the organisation, retire the thinker, trim provenance

**Files:**
- Create: `apps/site/src/content/organisations/pucl-gujarat.md`
- Delete: `apps/site/src/content/thinkers/pucl-gujarat.md`
- Modify: `apps/site/src/content/primary-works/khoj-march-april-2005.md`

- [ ] **Step 3.1.1: Create the organisation frontmatter**

```bash
cat > apps/site/src/content/organisations/pucl-gujarat.md <<'EOF'
---
id: pucl-gujarat
name:
  canonical: "PUCL Gujarat"
  sort: "Gujarat, PUCL"
type: reform_society
ideology:
  - civil_libertarian
needs_review: true
draft: false
---
EOF
```

(The body is empty by design — this is a stub the curator can flesh out. `needs_review: true` signals that the `type` + `ideology` are AI-chosen and worth verification.)

- [ ] **Step 3.1.2: Delete the thinker stub**

```bash
rm apps/site/src/content/thinkers/pucl-gujarat.md
```

After this step, the slug `pucl-gujarat` exists only in the organisations collection. The Zod union on `authors[]` will now resolve `- pucl-gujarat` to the organisations arm.

- [ ] **Step 3.1.3: Trim `stubs_referenced[]` on the Khoj 2005 entry**

Open `apps/site/src/content/primary-works/khoj-march-april-2005.md`. Find the `authors_resolution:` block. The `stubs_referenced:` array should currently list several slugs including `pucl-gujarat`. Remove the `- pucl-gujarat` line (just that one entry). If after removal the array becomes empty, change the block to `stubs_referenced: []` (inline empty form, matching the pattern other empty arrays use elsewhere in the frontmatter).

Verify with:

```bash
grep -A8 "authors_resolution:" apps/site/src/content/primary-works/khoj-march-april-2005.md
```

Confirm `pucl-gujarat` does not appear in the `stubs_referenced:` block. The other stub entries in that block (revatbha-rayjada, yogendra-mankad, manjula-dabhi, asghar-ali-engineer, etc.) stay.

- [ ] **Step 3.1.4: Build to verify**

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: clean build. The slug-uniqueness check finds zero overlaps (we deleted the thinker stub before adding the org, so they were never both present). The schema resolves `pucl-gujarat` in `authors[]` via the union's organisations arm. The byline JSX from Chunk 2 picks up the visual treatment.

### Task 3.2: Final acceptance verification

- [ ] **Step 3.2.1: Confirm the Khoj 2005 detail page renders the pill**

```bash
grep -B1 -A3 "PUCL Gujarat" apps/site/dist/primary-works/khoj-march-april-2005/index.html | head -10
```

Expected: An `<a href="/organisations/pucl-gujarat/">PUCL Gujarat</a>` followed by a `<span ...>organisation</span>`. The link's class list includes `text-(--color-saffron-700)`.

- [ ] **Step 3.2.2: Confirm `/organisations/pucl-gujarat/` was emitted**

```bash
ls apps/site/dist/organisations/pucl-gujarat/index.html
```

Expected: the file exists.

- [ ] **Step 3.2.3: Confirm `/thinkers/pucl-gujarat/` is gone**

```bash
ls apps/site/dist/thinkers/pucl-gujarat/ 2>&1
```

Expected: `No such file or directory`. (The thinker stub was deleted, so no `/thinkers/pucl-gujarat/` route should be generated.)

- [ ] **Step 3.2.4: Regression — Rayjada renders across all 4 Khoj-March-April issues**

```bash
for slug in khoj-march-april-2005 khoj-march-april-2006 khoj-march-april-2007 khoj-march-april-2008; do
  echo "=== $slug ==="
  grep -o "revatbha-rayjada[^\"]*\"[^>]*>Revatbha Rayjada</a>" apps/site/dist/primary-works/$slug/index.html | head -1
done
```

Expected: each issue prints one line showing the forest-green link to `/thinkers/revatbha-rayjada/`. If any issue prints nothing or shows a different colour class, the merge from yesterday's commit `7dc3434` regressed somehow — investigate before committing.

- [ ] **Step 3.2.5: Commit**

```bash
git add apps/site/src/content/organisations/pucl-gujarat.md apps/site/src/content/primary-works/khoj-march-april-2005.md
git rm apps/site/src/content/thinkers/pucl-gujarat.md
git commit -m "$(cat <<'EOF'
data: migrate pucl-gujarat from thinkers to organisations

PUCL Gujarat (People's Union for Civil Liberties — Gujarat chapter)
was created as a thinker stub by the 2026-05-22 byline-resolution
pipeline run. The pipeline's applier has no concept of organisational
authorship, so any name surfaced in unknowns[] became an ai_drafted_stub
thinker MD. PUCL Gujarat is in fact a civil-liberties advocacy NGO,
not a person.

This commit completes the migration in three filesystem operations:

1. Delete apps/site/src/content/thinkers/pucl-gujarat.md (the wrongly-
   classified stub).
2. Create apps/site/src/content/organisations/pucl-gujarat.md with
   type: reform_society, ideology: [civil_libertarian], needs_review:
   true. The type and ideology are provisional curator-flagged
   choices; founded_year is intentionally absent (no confidently
   sourced date for the Gujarat chapter).
3. Drop pucl-gujarat from the authors_resolution.stubs_referenced[]
   array of apps/site/src/content/primary-works/khoj-march-april-2005.md
   (the only primary-work that linked to it).

The schema union from feat(schema) now resolves the slug to the
organisations arm; the UI from feat(ui) renders PUCL Gujarat with the
saffron pill on /primary-works/khoj-march-april-2005/. /thinkers/pucl-
gujarat/ now 404s; /organisations/pucl-gujarat/ renders.

Refs docs/superpowers/specs/2026-05-23-organisational-authorship-design.md
EOF
)"
```

- [ ] **Step 3.2.6: Plan complete — no further commits**

Mark all tasks complete. The pipeline is shipped.

---

**End of Chunk 3.** Dispatch the plan-document-reviewer subagent for this chunk; once approved, the plan is complete and ready for human push to origin.

---

## Reviewer dispatch template

For each chunk above, dispatch the plan-document-reviewer subagent with:

```
You are a plan document reviewer. Verify this chunk is complete and ready to execute.

**Chunk to review:** [paste chunk content]

**Spec reference:** /Users/siraj/Indian Liberals Website/docs/superpowers/specs/2026-05-23-organisational-authorship-design.md

## What to check
| Category | What to look for |
|---|---|
| Granularity | Each step is one 2-5 minute action |
| Completeness | No TODOs, no placeholders, no "implement X here" |
| Testability | Manual spot-checks use real grep/ls commands with expected output |
| Exactness | File paths absolute; commit messages drafted |
| Spec fidelity | Plan matches spec §X for the chunk's scope |

Return: Status (Approved | Issues Found), per-task verification, new issues introduced, recommendations.
```

Fix issues in-place; re-dispatch until approved.

---

## Plan complete

After all 3 chunks pass review:

1. Mark this todo item complete.
2. Hand off to **superpowers:subagent-driven-development** for execution. Fresh subagent per task, two-stage review (spec compliance + code quality).

The terminal state of this plan is a primary-works detail page where org-authored entries render with a saffron "organisation" pill linking to `/organisations/<slug>/`, with `pucl-gujarat` as the first migrated case and the schema + invariant in place for future migrations.
