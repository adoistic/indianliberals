# SESSION-SUMMARY — Organisational Authorship

**Date:** 2026-05-23
**Branch:** `main` (8 commits ahead of `origin/main`; not pushed — awaiting Adnan's review)
**Plan:** [docs/superpowers/plans/2026-05-23-organisational-authorship.md](docs/superpowers/plans/2026-05-23-organisational-authorship.md)
**Spec (amended):** [docs/superpowers/specs/2026-05-23-organisational-authorship-design.md](docs/superpowers/specs/2026-05-23-organisational-authorship-design.md)

## Final state

- **Final commit on `main`:** `96aed0d86e2d43415354462189ca2b3d7d4bff26`
- **Build:** clean, 1185 pages indexed.
- **All 7 acceptance criteria from spec §10 verified** against rendered HTML in `apps/site/dist/`.

## Commits landed (5, not the planned 3)

| # | SHA | Title |
|---|---|---|
| 1 | `f173663` | feat(schema): allow organisations as primary-work authors/editors |
| 2 | `15425ed` | feat(ui): byline distinguishes organisational authors with saffron pill |
| 3 | `1f99d79` | data: migrate pucl-gujarat from thinkers to organisations |
| 4 | `4826e66` | feat(ui): byline rendering on lang-prefixed template + object-form data fix |
| 5 | `96aed0d` | fix(ui): byline whitespace + widen slug-uniqueness to .mdx |

Commits 1-3 are the originally-planned chunks. Commits 4-5 are deviations explained below.

## Acceptance verification (spec §10)

| # | Criterion | Status |
|---|---|---|
| 1 | `pnpm build` exits clean | ✅ 1185 pages, 1.2s |
| 2 | Slug-uniqueness check fires on overlap | ✅ verified in Chunk 1 negative test (charan-singh dupe → `Slug overlap between thinkers/ and organisations/: charan-singh`) |
| 3 | `/gu/primary-works/khoj-march-april-2005/` byline renders PUCL Gujarat with saffron pill linking to `/organisations/pucl-gujarat/` | ✅ HTML: `PUCL Gujarat</a><span class="ml-1 ...bg-(--color-saffron-100) text-(--color-saffron-700)">organisation</span>` |
| 4 | `/thinkers/pucl-gujarat/` returns 404 | ✅ `dist/thinkers/pucl-gujarat/` does not exist |
| 5 | `/organisations/pucl-gujarat/` renders | ✅ `dist/organisations/pucl-gujarat/index.html` present |
| 6 | All 4 Khoj-March-April issues render `revatbha-rayjada` forest-green | ✅ verified across 2005-2008, all show `class="text-(--color-forest-700)"` |
| 7 | `pucl-gujarat` no longer in Khoj 2005 `stubs_referenced[]` | ✅ removed in Chunk 3 |

(Acceptance URL for criteria 3 and 6 was updated `locked → amended` from `/primary-works/...` to `/gu/primary-works/...` — see Deviation 1 below.)

## Review-loop iterations

| Chunk | Implementer reports | Spec review | Code review |
|---|---|---|---|
| 1 | DONE (first pass) | ✅ Approved (first pass) | ✅ Approved (first pass) |
| 2 | DONE (first pass) | ✅ Approved (first pass) | ✅ Approved (first pass) |
| 3 | DONE_WITH_CONCERNS (first pass) — see below | n/a (paused for human input) | n/a |
| 4 | BLOCKED then DONE | ✅ Approved (first pass) | ✅ Approved-with-comments (first pass) |
| 5 (polish) | DONE — implementer's second attempt caught a residual whitespace artifact I hadn't flagged | n/a (final branch-level review covered it) | covered by branch-level review |

No chunk needed >1 review-loop iteration. Branch-level review (run once at the end) caught a Critical issue that per-chunk reviewers missed (the byline whitespace defect — see Deviation 2).

## Deviations from the plan

### Deviation 1 — Spec premise about `z.union` resolution was wrong (caused Commit 4)

**What:** The locked spec §4 stated *"Astro's `reference()` resolves the slug to `{ id, collection }` at runtime; the union picks the first collection that contains the slug."* This is empirically false. Zod's `z.union` accepts a bare-string input via the FIRST arm unconditionally (because `reference('thinkers')` is a permissive transform that doesn't validate file existence at parse time). The bare-string `- pucl-gujarat` in `authors[]` therefore resolves to `{ collection: 'thinkers', id: 'pucl-gujarat' }`, the lookup finds no thinker (we deleted the stub in Chunk 3), and the entry silently drops from the byline.

**Compounding gap:** The spec's acceptance criterion URL `/primary-works/khoj-march-april-2005/` is a 404 because the English template filters `language === "en"`. Khoj 2005 is `language: "gu"` and routes through `apps/site/src/pages/[lang]/primary-works/[slug].astro`, which was a deliberately minimal template with NO byline rendering at all. So the saffron-pill UI from Chunk 2 had no surface in production.

**Fix (Commit 4 `4826e66`):**
1. Switched line 13 of `khoj-march-april-2005.md` from `- pucl-gujarat` to YAML object form `- { collection: organisations, id: pucl-gujarat }` so the union resolves to the organisations arm. (Other authors[] entries stay bare-string — they're all thinkers, where first-arm resolution is correct.)
2. Ported the byline rendering (discriminated lookup, `bylineFallback`, byline JSX) from the English template into the `[lang]` template. Scope is byline-only — PeopleInPiece / RelatedSection / Themes / Pull quotes / Tier-B disclaimer NOT ported (those belong to a future template-unification spec).
3. Amended the spec: status bumped `locked` → `amended`, §4 corrected, §5.5 added describing the `[lang]`-template port, §7 / §9 / §10 updated.

**User authorisation:** Adnan was asked mid-session "How should I proceed?" with three options. He chose "Extend [lang] template with byline."

### Deviation 2 — Byline whitespace defect missed by per-chunk reviews (caused Commit 5)

**What:** The final branch-level reviewer flagged a visible typography defect on the Khoj 2005 demo URL — the JSX byline emitted `organisation</span> , <a...>` (space before comma) and `Rayjada</a>,  <a...>` (double space before the org pill's link). Both were classic JSX-whitespace-between-siblings-on-different-lines artifacts. Per-chunk reviewers didn't catch them because each reviewed the pill in isolation, not in context with its neighbouring authors.

**Fix (Commit 5 `96aed0d`):** Restructured the `.map` in both templates to inline the separator immediately adjacent to the element with no intervening newline. Also widened the slug-uniqueness filter from `.md` only to `.(md|mdx)` (latent gap — neither collection has `.mdx` files today but the loader glob accepts them).

### Deviation 3 — Total commit count: 5, not 3

The original plan was a "small, focused 3-commit change." Two extra commits (4 and 5) were unavoidable: Commit 4 fixed a spec premise error that blocked Acceptance Criterion 3; Commit 5 fixed a typography defect on the demo URL itself. Both are documented above. No other deviations.

## Deferred items (Adnan's call before push)

The final branch-level reviewer flagged three Important / Minor items not addressed in this session:

1. **(Important) Resolver duplication.** ~25 lines of TS resolver + ~22 lines of byline JSX are now duplicated between `apps/site/src/pages/primary-works/[slug].astro` and `apps/site/src/pages/[lang]/primary-works/[slug].astro`. The reviewer recommended extracting `resolveAuthorEntries()` to `apps/site/src/lib/resolve-author-entries.ts`. ~15 minutes of work; easier to do now (two callsites) than later (when someone adds a third). Skipped to stay within session scope.

2. **(Minor) Silent-drop on unresolved refs.** The discriminated lookup `.filter`s out null refs. If a curator typos a slug, the entry vanishes from the byline silently. Pre-existing behaviour, doubled in surface area by Commit 4. Reviewer recommended a build-time `console.warn` or an extension to `check-slug-uniqueness.ts` that probes every `authors[]` ref against its collection. Filed.

3. **(Minor) Hybrid YAML form in `khoj-march-april-2005.md` is undocumented.** Line 13 has `- { collection: organisations, id: pucl-gujarat }` mixed with bare-string entries. The convention is documented in the amended spec §4 but not in the data file or in `apps/site/src/content/AGENTS.md`. A one-line comment would close the gap. Filed.

4. **(Cosmetic) Pre-existing `By  <a` double-space.** The implementer noted that the byline opening `By <link>` has two spaces (from `By{" "}` + JSX newline-collapse). Out of scope for the polish commit; pre-existing, not introduced by this work.

None of the above block the push. They're follow-ups Adnan may want to land before or shortly after the push.

## Files changed (cumulative, across all 5 commits)

```
apps/site/src/content.config.ts                                       | (~6 lines)
apps/site/src/content/organisations/pucl-gujarat.md                   | (new, 11 lines)
apps/site/src/content/primary-works/khoj-march-april-2005.md          | (~2 lines)
apps/site/src/content/thinkers/pucl-gujarat.md                        | (deleted, 18 lines)
apps/site/src/lib/check-slug-uniqueness.ts                            | (new, 31 lines)
apps/site/src/pages/[lang]/primary-works/[slug].astro                 | (~50 lines)
apps/site/src/pages/primary-works/[slug].astro                        | (~50 lines)
docs/superpowers/specs/2026-05-23-organisational-authorship-design.md | (~33 lines, amended)
```

Plus this session-summary file at the repo root.

## Notes for push

- Branch is 8 commits ahead of `origin/main`: 5 from this work plus 3 already-ahead prior commits — `df29707 docs(plan)`, `4357e89 docs(spec)`, `a1f8349 docs(spec)`. Adnan should review the full set before push.
- No force-push needed. `git push origin main` (after Adnan's review) will land cleanly.
- `.claude/` directory is untracked and stays untracked — same as session start.
