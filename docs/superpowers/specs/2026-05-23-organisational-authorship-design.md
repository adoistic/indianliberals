# Organisational Authorship — Design Spec

**Author:** Adnan
**Date:** 2026-05-23
**Status:** locked

## 1. Goal

A primary-work's `authors[]` (and `editors[]`) can refer to either a thinker or an organisation. The UI distinguishes organisational entries from person entries with a small inline saffron "organisation" pill, and the org link routes to `/organisations/<slug>/` instead of `/thinkers/<slug>/`.

The byline-resolution pipeline that ran on 2026-05-22 surfaced one entry — `pucl-gujarat`, currently a thinker stub — that is in fact a civil-liberties NGO, not a person. The byline pipeline auto-created it as a thinker stub because its applier has no concept of organisational authorship. This spec adds first-class support for the case so future pipelines, manual edits, and curator decisions all have somewhere correct to put org-authored entries.

## 2. Non-goals

- **Updating the byline-resolution LLM/vision pipeline** to detect and route organisational author names natively. The pipeline will continue to create thinker stubs by default; manual curator action is required to re-classify a stub as an organisation. Updating the pipeline's prompts and applier routing is a separate body of work.
- **Sweeping the existing 179 pipeline-owned thinker stubs** for other org candidates. Only `pucl-gujarat` is migrated this round.
- **Re-attributing the 48 still-unresolved primary-works.** Some may have organisational authorship; that pass needs the pipeline update above.
- **Changes to `contributors[]`.** That field already accepts a `thinker_unresolved` string fallback and is structurally distinct (it captures multi-author TOCs for collected volumes, not the primary author of a work).
- **A new organisation type / enum value.** PUCL Gujarat fits the existing `reform_society` value adequately; curator can refine.

## 3. Scope

Three commits:

1. **Schema:** `authors[]` and `editors[]` on `primaryWorks` become `z.union` of thinker-or-organisation refs. Includes a build-time slug-uniqueness check across the two collections.
2. **UI rendering:** `apps/site/src/pages/primary-works/[slug].astro` (detail page) and, if relevant, `apps/site/src/pages/primary-works/index.astro` (card list) discriminate on the ref's `.collection` field and render organisational authors with a saffron pill labelled "organisation". Person authors render unchanged.
3. **Data migration (pucl-gujarat):** delete `apps/site/src/content/thinkers/pucl-gujarat.md`, create `apps/site/src/content/organisations/pucl-gujarat.md`, drop `pucl-gujarat` from the `authors_resolution.stubs_referenced[]` array of `apps/site/src/content/primary-works/khoj-march-april-2005.md`.

## 4. Schema delta

In `apps/site/src/content.config.ts`, the `primaryWorks` collection schema changes two fields:

```ts
// Before
authors: z.array(reference('thinkers')).default([]),
editors: z.array(reference('thinkers')).default([]),

// After
authors: z.array(z.union([reference('thinkers'), reference('organisations')])).default([]),
editors: z.array(z.union([reference('thinkers'), reference('organisations')])).default([]),
```

Frontmatter shape does not change. A bare string slug (`- pucl-gujarat`) still works. Astro's `reference()` resolves the slug to `{ id, collection }` at runtime; the union picks the first collection that contains the slug.

**Invariant introduced:** a slug must be unique across the union of the `thinkers` and `organisations` collections. The Zod union picks the first arm that resolves, so if a slug exists in both, the second arm (organisations) is unreachable. This invariant is enforced by a small build-time check (§6).

**Why `editors[]` too?** Collected volumes can have organisational editorship (party manifestos edited by the party's editorial board, periodicals issued by an institutional editorial committee, etc.). Keeping the two fields' shape symmetric is cheap and obvious.

## 5. UI rendering

### 5.1 Visual treatment

A primary-work's byline currently renders as:

> By **[person name](/thinkers/foo/)**, **[person name](/thinkers/bar/)**

Post-change, with an organisational author mixed in:

> By **[person name](/thinkers/foo/)**, **[PUCL Gujarat](/organisations/pucl-gujarat/)** `[organisation]`, **[person name](/thinkers/baz/)**

The pill is a small inline `<span>` next to the org name. Visual specifics:

- Background: `var(--color-saffron-100)` (light tint).
- Foreground text: `var(--color-saffron-700)` (matches the saffron eyebrow used on `/organisations/<slug>/` detail pages, so the visual language is consistent).
- Typography: `font-(family-name:--font-ui) font-semibold` at `text-[10px] uppercase tracking-wider`, matching other meta-tag pills used elsewhere on the site.
- Spacing: `ml-1 px-1.5 py-0.5 rounded`, `inline-block` with `align-middle` so it sits on the baseline of the linked org name.
- Content: the literal text `organisation` (lowercase, no abbreviation).

Person author links continue to use `text-(--color-forest-700)` (the existing convention). Org author links use `text-(--color-saffron-700)` for the link colour itself, reinforcing the colour story.

### 5.2 Code change (`primary-works/[slug].astro`)

Current logic (line ~39-43) loads thinkers only:

```ts
const allThinkers = await getCollection("thinkers");
const thinkersById = new Map(allThinkers.map((t) => [t.id, t]));
const authorEntries = (fm.authors ?? [])
  .map((ref) => thinkersById.get(ref.id ?? (ref as unknown as string)))
  .filter((t): t is NonNullable<typeof t> => !!t);
```

Note the `(ref as unknown as string)` fallback — this is a defensive cast from before Astro's `reference()` had a stable `.id` shape. After the schema change to `z.union([reference('thinkers'), reference('organisations')])`, the resolved type carries both `.id` and `.collection` reliably. **The implementer must remove the `(ref as unknown as string)` fallback** as part of this change — leaving it in would silently swallow org references that the union resolves but the thinker-only fallback can't handle.

Replace with a discriminated lookup:

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

And the byline JSX (line ~127-133):

```astro
{authorEntries.map((e, i) => (
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
))}
```

The `authorSlugs` derivation (line ~80) used downstream for the "People in this piece" chip section should continue to feed off thinker entries only — organisations don't belong in that chip block. Update:

```ts
const authorSlugs = authorEntries
  .filter((e): e is Extract<AuthorEntry, { kind: "thinker" }> => e.kind === "thinker")
  .map((e) => e.id);
```

### 5.3 No change to `primary-works/index.astro`

The card-list page does render a byline, but it reads from `contributors[].role === 'author'` (with `thinker_unresolved` fallback), not from `authors[]`:

```ts
const byline = (w.data.contributors ?? [])
  .filter((c) => c.role === "author")
  .map((c) => c.thinker_unresolved || (c.thinker as { id?: string } | undefined)?.id || "")
  .filter(Boolean)
  .join(", ");
```

Since organisational authorship lives in `authors[]`, not `contributors[]`, the card list will not surface org authors regardless. No change to this file. (A future spec that brings the card byline in line with the detail-page byline would extend the discriminated-lookup pattern here too, but that is not in scope.)

### 5.4 Accessibility

The pill is decorative metadata adjacent to the link's accessible name. The link's text is the org's canonical name; screen readers will announce "PUCL Gujarat, organisation" (the pill's `<span>` content is read in document order). No `aria-label`, no `role="img"`, no separate hidden text needed.

## 6. Slug-uniqueness invariant

The Zod union picks the first arm that resolves. If `pucl-gujarat` existed in *both* the thinkers and organisations collections, the union's first arm (`reference('thinkers')`) would always win and the org reference would be unreachable. Astro itself does not enforce uniqueness across collections.

A tiny build-time check fails the build when an overlap exists:

```ts
// apps/site/src/lib/check-slug-uniqueness.ts
import { readdirSync } from "node:fs";
import { resolve } from "node:path";

const CONTENT = resolve(import.meta.dirname, "../content");
const thinkers = new Set(
  readdirSync(resolve(CONTENT, "thinkers"))
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.replace(/\.md$/, "")),
);
const orgs = new Set(
  readdirSync(resolve(CONTENT, "organisations"))
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.replace(/\.md$/, "")),
);
const overlap = [...thinkers].filter((s) => orgs.has(s));
if (overlap.length) {
  throw new Error(
    `Slug overlap between thinkers/ and organisations/: ${overlap.join(", ")}. ` +
    `A slug must be unique across the union of these collections (see ` +
    `docs/superpowers/specs/2026-05-23-organisational-authorship-design.md §6).`,
  );
}
```

The check is invoked from the top of `apps/site/src/content.config.ts` via a side-effect import:

```ts
import "./lib/check-slug-uniqueness";
```

This runs on every Astro build and dev-server start, before the schema validates any entry. Cost: a single `readdirSync` pair, no JSON parsing.

## 7. Data migration (pucl-gujarat)

Three file operations:

**Delete** `apps/site/src/content/thinkers/pucl-gujarat.md`.

**Create** `apps/site/src/content/organisations/pucl-gujarat.md`:

```yaml
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
```

Rationale for each field:

| Field | Value | Rationale |
|---|---|---|
| `type` | `reform_society` | PUCL is a civil-liberties advocacy NGO; of the existing enum values, `reform_society` is the closest fit. Curator may refine. |
| `ideology` | `[civil_libertarian]` | Provisional. The full PUCL Gujarat ideological profile is curator-determined. |
| `founded_year` | absent | No confidently sourced founding date for the Gujarat chapter. Better to leave unset than guess. |
| `needs_review: true` | flagged | Curator should verify the `type` + `ideology` classification before this entry is considered canonical. |

**Modify** `apps/site/src/content/primary-works/khoj-march-april-2005.md`:

- `authors[]` already contains `- pucl-gujarat`. No change to that line.
- `authors_resolution.stubs_referenced[]` currently includes `pucl-gujarat`. Remove that one entry (the migration retired the thinker stub).

No other primary-works reference `pucl-gujarat`, so no further file edits are required for the migration.

## 8. Testing & verification

The verification surface is small and entirely runtime.

**Build (the schema gate):**

```bash
cd apps/site && pnpm build
```

Required: clean build, ~1185 pages (no net change in page count from this work — minus one thinker page, plus one organisation page, net zero). Zod surfaces any unresolved `authors[]` reference as a precise file:line error. Build clean = schema, the union resolution, and the migration are all wired.

**Slug-uniqueness check (the §6 gate):** verified implicitly by build success — the side-effect import runs at config load.

**Manual UI spot-checks (post-build):**

1. `/primary-works/khoj-march-april-2005/` — byline reads "By Rajesh Mishra, Trupti Parekh, …, PUCL Gujarat *[organisation pill]*, Yogendra Mankad, …". Click "PUCL Gujarat" → `/organisations/pucl-gujarat/` renders.
2. `/organisations/pucl-gujarat/` — page renders, eyebrow / title display correctly.
3. `/thinkers/pucl-gujarat/` — 404 (the thinker MD is gone).
4. Regression set: visit all 4 Khoj-March-April pages — `/primary-works/khoj-march-april-2005/`, `/primary-works/khoj-march-april-2006/`, `/primary-works/khoj-march-april-2007/`, `/primary-works/khoj-march-april-2008/`. Each must render `revatbha-rayjada` as a forest-green person link (this is yesterday's merged-duplicate entry; it must keep working across all four issues).

**No unit tests.** The schema change is declarative; the UI change is visual; the migration is a one-time move. The build + 4 spot-checks are the full verification surface.

## 9. Commit plan

Three independently-buildable commits, in this order:

1. `feat(schema): allow organisations as primary-work authors/editors`
   - `apps/site/src/content.config.ts` — union the two ref schemas.
   - `apps/site/src/lib/check-slug-uniqueness.ts` — new file, side-effect imported by `content.config.ts`.
   - Build still passes (no data references an organisation in `authors[]` yet, but the schema accepts the case).

2. `feat(ui): byline distinguishes organisational authors with saffron pill`
   - `apps/site/src/pages/primary-works/[slug].astro` — dual-lookup + discriminated render; remove the `(ref as unknown as string)` defensive cast.
   - No change to `apps/site/src/pages/primary-works/index.astro` per §5.3 (card byline reads from `contributors[]`, not `authors[]`).

3. `data: migrate pucl-gujarat from thinkers to organisations`
   - Delete `apps/site/src/content/thinkers/pucl-gujarat.md`.
   - Create `apps/site/src/content/organisations/pucl-gujarat.md`.
   - Update `apps/site/src/content/primary-works/khoj-march-april-2005.md` to drop `pucl-gujarat` from `authors_resolution.stubs_referenced[]`.
   - Build passes (the schema from commit 1 now resolves the bare slug to the organisations collection); the §5.1 visual treatment from commit 2 takes effect on the Khoj 2005 page.

If any commit fails its build, fix or revert before proceeding to the next.

**Commit-ordering note:** commits 1 and 2 are safe to land without commit 3 — the build will pass because the schema accepts both arms and the UI's org-arm lookup will gracefully drop unresolved org refs (same filter pattern as the existing thinker lookup). But during that interval, `pucl-gujarat` is still a thinker on disk while `authors[]` resolves the slug via the union — the union's first arm (thinkers) wins, so the byline renders PUCL Gujarat as a person link with the forest-green colour, not as an org with the saffron pill. The visual treatment only takes effect after commit 3 retires the thinker stub. This is intentional and not a regression; the merged commit set produces the final state.

## 10. Acceptance criteria

1. `pnpm build` exits clean.
2. The slug-uniqueness check fires on a deliberately-introduced overlap (one-line manual test during implementation: temporarily create a duplicate, confirm the build errors out with the spec-referenced message, then remove the duplicate).
3. `/primary-works/khoj-march-april-2005/` byline renders PUCL Gujarat with the saffron pill, linking to `/organisations/pucl-gujarat/`.
4. `/thinkers/pucl-gujarat/` returns 404.
5. `/organisations/pucl-gujarat/` renders.
6. The 4 Khoj-March-April issues using `revatbha-rayjada` (regression set) still render the byline correctly.
7. `authors_resolution.stubs_referenced[]` on the Khoj 2005 entry no longer lists `pucl-gujarat`.

## 11. Future work (out of this spec, but worth noting)

- **Byline-resolution pipeline update:** teach the LLM/vision prompt to flag organisational author candidates separately (`{matches: [], orgs: ["PUCL Gujarat"], ...}`) and route the applier's stub-creation logic accordingly. Closes the loop for future pipeline runs so curators don't have to retroactively re-classify.
- **Heuristic sweep of existing stubs:** scan the 179 ai_drafted_stub thinkers for org-shaped canonical names (substring matches on "Forum", "Society", "Foundation", "Council", "Association", "Committee", "Initiative", "PUCL", etc.) plus a one-shot LLM classifier pass. Expected yield: 5-15 more migrations.
- **Coverage acceptance criterion re-calibration:** the byline-resolution spec's 97% target should reflect the corpus's institutional-document share. Either lower the bar to ~92% or extend authorship to also count institutional-only entries (this spec is a step in the latter direction).
