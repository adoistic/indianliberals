# Contributors Collection — Design Spec

**Author:** Adnan
**Date:** 2026-05-25
**Status:** locked

## 1. Goal

Give every contemporary opinion-piece writer their own page on indianliberals.in, distinct from the canonical "Indian liberal thinker" pages. Extract the inline bio block + photo currently appended to each opinion piece's body into a structured collection with its own URL space, schema, and listing surface.

The terminal state of this work:
1. A new `apps/site/src/content/contributors/` content collection exists with a contributor MD for every unique opinion-piece bio author (~11-14 real people).
2. Every opinion piece references its contributor via `author: <slug>` in frontmatter.
3. The trailing bio block has been stripped from the opinion's body (it now renders on the contributor's page + as a "Written by" card on the opinion page).
4. A new `/contributors/<slug>/` detail page renders the contributor's photo, bio, structured affiliation/role, and the list of opinion pieces they've written.
5. A new `/contributors/` index page lists every contributor with photo + role + piece count.
6. The misplaced `shivani-a-tannu` stub in `/thinkers/` is migrated to `/contributors/`.

## 2. Non-goals

- **Re-running classification on existing opinions.** Themes / canon_status / tradition extraction stays as-is.
- **A "contributors" facet on the existing `/thinkers/` index.** Contributors and thinkers stay in different URL spaces, different schemas, different pages.
- **Bios for musings or theprint-mirror.** Those collections don't have the same trailing-bio pattern (musings are anonymous CCS editorial; theprint pieces use `author_name` free text). A future spec may extend this work; not in scope here.
- **Generating bios for opinion-piece writers who don't have one inline.** If the bio block is missing from the source MD, no contributor MD is created. (~16 of 61 opinions have no bio block; those opinions just won't have an `author:` ref.)
- **Editing opinion-piece bodies beyond stripping the trailing bio block.** No rephrasing, no summary rewriting.

## 3. Scope

- **One new content collection** (`contributors`) with a schema fitted to contemporary writers (bio prose as MD body + optional structured fields).
- **Two new page templates** (`/contributors/[slug].astro` detail + `/contributors/index.astro` listing).
- **One opinion-schema change** (`author` ref retypes from `thinkers` to `contributors`).
- **One opinion-template change** (add a "Written by" card at the bottom).
- **Two synthesis scripts** (extract bios from opinion bodies into contributor MDs; wire opinion frontmatter + strip body bio block).
- **One one-time photo-fetch step** (download ~13 WP-hosted photos to local `public/contributors/photos/`).
- **One thinker→contributor migration** (`shivani-a-tannu` moves; 2 opinions update their `author:` ref).

## 4. Architecture

```
apps/site/src/content/
  contributors/             ← NEW collection
    sanjeet-kashyap.md
    naina-ojha.md
    vikrant-pande.md
    …~13 entries
  thinkers/                 ← unchanged
  opinions/                 ← schema change (author ref) + body strip
  …

apps/site/src/pages/
  contributors/
    [slug].astro            ← NEW
    index.astro             ← NEW
  opinions/
    [slug].astro            ← MODIFIED (add "Written by" card)
  …

apps/site/public/
  contributors/
    photos/                 ← NEW; ~13 .jpg files
      sanjeet-kashyap.jpg
      …

scripts/synthesis/
  extract-opinion-contributors.py   ← NEW
  wire-opinion-authors.py           ← NEW
```

URL space:
- `/contributors/` — listing page (alphabetical, with optional sort by piece count)
- `/contributors/<slug>/` — detail page (photo, bio, "Pieces by <X>" list)
- `/thinkers/` and `/thinkers/<slug>/` — unchanged

## 5. Contributors collection schema

`apps/site/src/content.config.ts`:

```typescript
const contributors = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/contributors' }),
  schema: z.object({
    id: z.string(),
    name: z.object({
      canonical: z.string(),
      sort: z.string(),
      also_known_as: z.array(z.string()).default([]),
    }),
    // Local path under /public, e.g. "/contributors/photos/sanjeet-kashyap.jpg".
    // Optional because some bios were imported without a photo.
    photo: z.string().optional(),
    // Optional structured fields — extractable from the bio prose or
    // curator-filled. Not required because not every bio mentions all of them.
    affiliation: z.string().optional(),         // "Centre for Civil Society"
    role: z.string().optional(),                // "Indian Liberal Fellow" | "Intern" | …
    joined_at: z.number().int().optional(),     // year
    areas_of_interest: z.array(z.string()).default([]),
    bio_source: z.enum([
      'extracted_from_opinion_bio',
      'curator',
      'imported',
    ]).default('extracted_from_opinion_bio'),
    needs_review: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});
```

**Body of the MD = the bio prose verbatim** (1-2 paragraphs as extracted from the opinion's trailing bio block).

### 5.1 Why this shape

- **Bio in body, not frontmatter**: bios are 50-400 words of free prose. Storing them as the MD body lets Astro render them as the page's main copy (via `<Content />`) with markdown formatting preserved. Frontmatter would force YAML escaping of every paragraph break.
- **Structured fields are optional**: the audit of 11 unique bios showed inconsistent presence of role/affiliation/education/interests. Required fields would force fake values; optional fields let the schema be honest about what's known.
- **`bio_source` enum**: matches the convention in the thinker schema; tracks whether a bio is curator-vetted vs auto-extracted.

## 6. Opinion schema change

Current:
```typescript
author_name: z.string(),                            // free text, often "Editorial Team"
author: reference('thinkers').optional(),           // structured ref WHEN one exists
subject: reference('thinkers').optional(),          // the thinker the piece profiles
```

New:
```typescript
author_name: z.string(),                            // unchanged
author: reference('contributors').optional(),       // CHANGED: now points to contributors
subject: reference('thinkers').optional(),          // unchanged
```

### 6.1 Migration impact

- Two opinions currently have `author: shivani-a-tannu` (pointing at `thinkers/shivani-a-tannu`). The `shivani-a-tannu` MD migrates from `/thinkers/` to `/contributors/`. The two opinion `author:` refs continue to resolve, just to the contributors collection now.
- No data migration script required beyond the move + the MD authoring. The rename is a schema rebind, not a value change.

## 7. Extraction strategy

Two scripts in `scripts/synthesis/`:

### 7.1 `extract-opinion-contributors.py`

For each opinion MD:
1. Find the trailing bio block. Two patterns to match (in order):
   - **photo + name + bio**: `![](https://indianliberals.in/...jpg)\n\n**<Name>**\n<bio paragraph>`
   - **name + bio (no photo)**: `\n**<Name>**\n<bio paragraph>` (where bio ≥ 80 chars)
2. Filter out false positives by name pattern (section headings like "Introduction", "References", "Conclusion", "Way forward", "Summing Up", "Background", and known doc-title patterns).
3. Slugify the name (`Sanjeet Kashyap` → `sanjeet-kashyap`).
4. If `apps/site/src/content/contributors/<slug>.md` already exists, skip without writing (dedupes Sanjeet's 20 occurrences into one MD). Re-runs MUST NOT overwrite an existing MD even when the freshly-extracted bio is longer — that preserves idempotence (§10.2 #7) and prevents accidental clobber of curator edits. If a curator wants to refresh from a longer source bio, they delete the MD first and re-run.
5. Else create the MD with:
   - `id: <slug>`
   - `name.canonical: <extracted name>`, `name.sort: <Surname, Given>`
   - `photo:` if present in the extracted block → set after the photo-download step writes the local file
   - `affiliation`, `role` — best-effort regex extraction (see §7.3)
   - `bio_source: extracted_from_opinion_bio`
   - `needs_review: true`
   - Body: the extracted bio paragraph
6. Emit a list of (slug, photo_url) pairs for the photo-download step.

### 7.2 Photo download (one-shot, idempotent)

For each unique (slug, photo_url) pair:
1. `curl -fsSL <photo_url> -o apps/site/public/contributors/photos/<slug>.<ext>`
2. Update the contributor MD's `photo:` to `/contributors/photos/<slug>.<ext>`.
3. If the download fails (404, network), log a warning, leave `photo:` unset.

Photos are committed to git (small files, ~50-150 KB each; ~13 photos total).

### 7.3 Best-effort `affiliation` / `role` extraction

Regex over the bio paragraph:
- **affiliation**: if bio contains "Centre for Civil Society" or "CCS" → `affiliation: "Centre for Civil Society"`. Else leave unset.
- **role**: scan for "Indian Liberal Fellow", "Indian Liberals Fellow", "Indian Liberals Project intern", "research scholar", "Editorial Team", "Editor" in order; first match wins. Else leave unset.
- **joined_at**: leave unset for now; bios rarely state a start year.
- **areas_of_interest**: leave unset for now; bios state interests in inconsistent prose form.

These are heuristics, not authoritative. `needs_review: true` flags the entry for curator triage.

### 7.4 `wire-opinion-authors.py`

For each opinion MD with an extracted bio:
1. Add `author: <contributor-slug>` to frontmatter (replace if present, preserve `author_name`).
2. Strip the trailing bio block from the body (everything from the image/name marker to EOF).
3. Write back; preserve every other frontmatter field verbatim.

Idempotent: re-running with no new bios produces zero changes.

## 8. Page templates

### 8.1 `/contributors/[slug].astro`

Section layout:
1. **Header**: name (large), optional `role` + `affiliation` chip strip below
2. **Photo**: square or 3:4 aspect, ~200px, right-aligned on desktop / above-header on mobile
3. **Bio**: rendered as the page's main copy via `<Content />`
4. **"Pieces by <X>"**: list of opinions where `author: <slug>`, with title + pubDate

### 8.2 `/contributors/index.astro`

Simple grid (matches the `/thinkers/` cards-with-portrait pattern):
- Card per contributor: photo thumb, name, role/affiliation caption, piece count
- Default sort: alphabetical by `name.sort`
- Optional Pagefind filter chip strip (by role, by affiliation) — out of scope for v1

### 8.3 `/opinions/[slug].astro` — modification

After the existing body content, before the footer:
```jsx
---
import { getEntry } from 'astro:content';
// `o.data.author` is the Astro reference to the contributors collection.
const contributor = o.data.author ? await getEntry(o.data.author) : null;
---
{contributor && (
  <ContributorCard contributor={contributor} />
)}
```

`ContributorCard` component renders: small photo + name (linked to `/contributors/<slug>/`) + 1-2 sentence affiliation/role line. Reads from the opinion's resolved contributor entry.

When `author` is unset, no card renders (graceful fallback for the 16 opinions without a bio block).

## 9. Migration of `shivani-a-tannu`

The current `apps/site/src/content/thinkers/shivani-a-tannu.md` is a stub (no body, `tradition: contemporary_liberal`, `canon_status: unclassified`, `bio_source: ai_drafted_stub`) that semantically belongs in `/contributors/`.

Migration:
1. Create `apps/site/src/content/contributors/shivani-a-tannu.md` with whatever bio text exists (likely empty — needs_review: true) and `bio_source: imported`.
2. Delete `apps/site/src/content/thinkers/shivani-a-tannu.md`.
3. The two opinions that reference her (`encoding-privacy-in-a-digital-world-by-shivani-a-tannu.md` + the duplicate `encoding-privacy-in-a-digital-world.md`) continue to have `author: shivani-a-tannu` — the schema rebind in §6 means the ref now resolves to the contributors collection.
4. Remove `shivani-a-tannu` from `data/authority/thinkers.json` (thinker authority is for canonical Indian liberal thinkers, not contributors).

## 10. Validation criteria

Each numbered criterion is independently verifiable.

### 10.1 Collection + schema

1. `cd apps/site && pnpm build` exits clean after the collection is added.
2. The new schema rejects MDs missing `id`, `name.canonical`, or `name.sort` (Zod validation error in `pnpm check`).
3. The schema accepts MDs with only the required fields + body (all structured fields optional).

### 10.2 Extraction script

4. `python3 scripts/synthesis/extract-opinion-contributors.py` produces N ≥ 11 contributor MDs (the 11 unique real bio-block authors counted in the audit).
5. Each contributor MD has a non-empty body (the bio prose).
6. Each contributor MD's frontmatter contains `name.canonical` matching the extracted bold-text name.
7. Re-running the script with the same input produces zero new files (idempotent).
8. No contributor MD is created for filtered-out false-positive names (Introduction, References, etc.).

### 10.3 Photo download

9. Each contributor whose bio block contained a photo URL has a corresponding file under `apps/site/public/contributors/photos/<slug>.<ext>`.
10. Each such contributor's `photo:` field references the local path.
11. Photos are committed to git (verified via `git ls-files apps/site/public/contributors/photos/`).

### 10.4 Wire + strip

12. After `wire-opinion-authors.py` runs, every opinion that had a bio block now has `author: <contributor-slug>` in frontmatter.
13. The trailing bio block has been stripped from each such opinion's body.
14. Every other frontmatter field on every opinion is preserved verbatim (verified by diff: only `author:` line added/changed, body shortened).
15. Re-running `wire-opinion-authors.py` produces zero changes (idempotent).

### 10.5 Page rendering

16. After `pnpm build`, `/contributors/sanjeet-kashyap/index.html` exists, well-formed, contains his bio text + photo + "Pieces by Sanjeet" list.
17. `/contributors/index.html` exists and renders cards for all N contributors.
18. `/opinions/b-r-ambedkar-social-reform-failure-of-indian-liberalism/index.html` renders the "Written by Sanjeet Kashyap" card after the body, with a link to `/contributors/sanjeet-kashyap/`.
19. Opinions without an extracted bio (no `author:` ref) render with no "Written by" card.

### 10.6 Migration

20. `apps/site/src/content/contributors/shivani-a-tannu.md` exists; `apps/site/src/content/thinkers/shivani-a-tannu.md` does not.
21. The two opinions referencing her resolve to the contributors collection and render her contributor card.
22. `shivani-a-tannu` is absent from `data/authority/thinkers.json` post-migration.

### 10.7 Regression

23. Page count delta after the work lands is exactly `+N` from current, where `N = (contributor detail pages) + 1 (contributor index page) − 1 (deleted shivani-a-tannu thinker page)`. Verified via `find apps/site/dist -name 'index.html' | wc -l` before vs after.
24. `/thinkers/index.html` still renders all canon sections unchanged.
25. `/thinkers/` page counts (Liberal canon, Extended, Referenced, Awaiting) are unchanged from pre-work counts.
26. `pnpm build` exits clean.

### 10.8 Stopping criteria

The work is "done" when:
- §10.2 #4-#8 pass (extraction produced clean MDs)
- §10.4 #12-#15 pass (wiring is idempotent + complete)
- §10.5 #16-#19 pass (pages render correctly)
- §10.6 #20-#22 pass (shivani migration clean)
- §10.7 #23-#26 pass (no regression)

## 11. Future work (out of scope but worth noting)

- **Bios for musings + theprint-mirror.** Musings are currently anonymous CCS editorial; theprint pieces use `author_name` free text. A future spec could extend the contributors collection to cover those.
- **Curator-fill of `joined_at` / `areas_of_interest` / `social` links.** Schema supports them as optional; bulk-fill from a separate CCS-internal contributor sheet is a future ingest.
- **Contributor cross-link from thinker pages.** When an opinion references a thinker via `subject:` AND has an `author:` contributor, the thinker's "Profile pieces about X" section could optionally show the contributor's name + photo. Out of scope; cosmetic.
- **Pagefind facet filters on `/contributors/` index** (filter by role, affiliation). Out of scope for v1.
- **`author: union(thinkers | contributors)`** — if a canonical thinker ever writes an opinion piece on the site, the discriminated-union approach (Zod supports it) would let `author:` point at either collection. Not needed today (zero such opinions); revisit if/when it happens.
