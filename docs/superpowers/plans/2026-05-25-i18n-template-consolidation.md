# i18n Template Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the duplicated-template architecture that causes the English and lang-prefixed routes to silently drift apart over time. After this work, each content type has ONE source of truth for rendering (a shared component), used by both routes. Today's gap (e.g. the gu Khoj missing Themes, Pull quotes, Related; the gu thinker pages missing canon tabs and Pieces-by-X) closes. Future feature additions land in one place and show up on both en + i18n routes automatically.

**Architecture:**
- Per-collection shared component at `apps/site/src/components/<Collection>Detail.astro` — owns the full UI (header, body, all sections, disclaimer).
- Two thin route shells per collection:
  - `apps/site/src/pages/<ct>/[slug].astro` — filters `language === DEFAULT_LOCALE`, hands the entry to `<CollectionDetail entry={…} />`.
  - `apps/site/src/pages/[lang]/<ct>/[slug].astro` — filters `language !== DEFAULT_LOCALE` AND `LOCALES.includes(...)`, hands the entry to the same component.
- Language-specific behavior (`noindex` on AI translations, `lang=` attribute on body, `data-pagefind-filter:lang:<code>`) is read inside the shared component from `entry.data.language` and `entry.data.translation_status`. The two routes don't carry conditionals; the component does.

**Tech Stack:** Astro v5 content collections (existing); shared components as `.astro` files (existing pattern). No new dependencies.

**Spec:** None — this is a refactor with no new behavior. Source of truth is the existing English templates' current rendering. Each chunk's acceptance is "English page bytes-identical (modulo whitespace), i18n page now includes the previously-missing sections, build clean, page count unchanged."

**Out of scope for this plan:**
- Translating new content (no MD edits — only template edits).
- Per-language thinker bio pages (e.g. `/gu/thinkers/<slug>/` for a translated bio). The current schema is one MD per thinker; adding per-(person, language) MDs is a separate scope.
- New features on either template (port faithfully; don't add).
- The `/contributors/` collection — see Chunk 7 for the explicit decision.
- The `extract_opinion_contributors.py` Pattern-B regression flagged in the prior contributors-collection final review (separate follow-up).

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `apps/site/src/components/PrimaryWorkDetail.astro` | CREATE | Owns the full primary-work article UI (header, body, pull quotes, themes, related, disclaimer, PeopleInPiece). |
| `apps/site/src/components/ThinkerDetail.astro` | CREATE | Owns the full thinker page UI (canon banner, classification chips, bio body, Pieces-by-X, Profile-pieces-about-X, Works-by-X, related). |
| `apps/site/src/components/OrganisationDetail.astro` | CREATE | Owns the organisation page UI. |
| `apps/site/src/components/OpinionDetail.astro` | CREATE | Owns the opinion page UI (header, body, "Written by" card, PeopleInPiece, Related). |
| `apps/site/src/components/MusingDetail.astro` | CREATE | Owns the musing page UI. |
| `apps/site/src/components/InterviewDetail.astro` | CREATE | Owns the interview page UI. |
| `apps/site/src/pages/{primary-works,thinkers,organisations,opinions,musings,interviews}/[slug].astro` | REWRITE | Shrink each to a ~25-line shell: getStaticPaths + render `<XxxDetail entry={...} />`. |
| `apps/site/src/pages/[lang]/{primary-works,thinkers,organisations,opinions,musings,interviews}/[slug].astro` | REWRITE | Same pattern for the lang-prefixed route. |

**File-size budget:** Each shared component should land under ~600 lines (thinkers is the largest — currently 534 lines in the English template alone). Each route shell should land at ~30 lines or less.

---

## Pre-work baseline (run once before Chunk 1)

Capture once at the very top so every chunk can reference the same numbers.

- [ ] **Step 0.1: Capture baseline page count + sample HTML snapshots**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/i18n-baseline-build.log
ln -s ../dist/pagefind public/pagefind
find dist -name 'index.html' | wc -l > /tmp/i18n-baseline-pages
echo "baseline pages: $(cat /tmp/i18n-baseline-pages)"  # expect 1287

# Capture HTML snapshots of representative pages for diffing post-refactor.
# These are the "shouldn't change" pages for English; on i18n they SHOULD
# gain content but no English content should disappear.
mkdir -p /tmp/i18n-baseline-html
for path in \
  "primary-works/khoj-january-february-2007/index.html" \
  "thinkers/b-r-ambedkar/index.html" \
  "organisations/centre-for-civil-society/index.html" \
  "opinions/b-r-ambedkar-social-reform-failure-of-indian-liberalism/index.html" \
  "musings/index.html" \
  "interviews/index.html" \
  "gu/primary-works/khoj-january-february-2008/index.html"
do
  src="dist/$path"
  dest="/tmp/i18n-baseline-html/$(echo $path | tr '/' '_')"
  test -f "$src" && cp "$src" "$dest" && echo "snapshot: $dest"
done
ls /tmp/i18n-baseline-html | wc -l   # expect 7
```

Expected: clean build; baseline-pages = 1287; 7 HTML snapshots captured.

---

## Chunk 1: Pilot on primary-works

Goal: Extract `PrimaryWorkDetail.astro` and convert both routes to thin shells. Kills the dup-Summary at the root (the Option-1 band-aid will become a no-op once the new architecture lands). Validates the pattern.

### Task 1.1: Inventory both templates side-by-side

- [ ] **Step 1.1.1: Read both templates and tabulate differences**

```bash
cd "/Users/siraj/Indian Liberals Website"
diff -u apps/site/src/pages/primary-works/\[slug\].astro \
        apps/site/src/pages/\[lang\]/primary-works/\[slug\].astro | head -200
```

Produce a written inventory of:
1. Sections only in English (e.g. Pull quotes, Themes, disclaimer, PeopleInPiece, RelatedSection).
2. Sections only in i18n (e.g. `data-pagefind-meta="work_type:..."` markup — does English have an equivalent?).
3. Lang-conditional rendering needs (`noindex` on AI translations, `lang=` attribute, pagefind language filter).

Document the inventory in a comment block at the top of the new `PrimaryWorkDetail.astro` so a future reader knows which decisions came from which side.

### Task 1.2: Extract `PrimaryWorkDetail.astro`

- [ ] **Step 1.2.1: Create the shared component**

Create `apps/site/src/components/PrimaryWorkDetail.astro`. It should:

1. Take a single prop: `{ entry }` where entry is a primary-works collection entry.
2. Internally compute everything currently computed in the English template's frontmatter section (pullQuotes, themesPretty, hreflang, authorEntries, bylineFallback, descriptionForMeta).
3. Render the full English UI: header (with byline, year, publisher, PDF link), body via `<Content />` with the prose-styling class block, Pull quotes section, Themes chips section, Tier-B disclaimer, PeopleInPiece, RelatedSection.
4. Apply lang-conditional behavior:
   - `BaseLayout` `noindex={shouldNoindex(entry.data.translation_status)}` regardless of route.
   - `lang={entry.data.language}` on body content.
   - `data-pagefind-filter={`type:primary-work,lang:${entry.data.language}`}` on the article element.

Reference the inventory comment for which behaviors are conditional.

- [ ] **Step 1.2.2: Convert English route to a thin shell**

Rewrite `apps/site/src/pages/primary-works/[slug].astro` to:

```astro
---
import { getCollection } from "astro:content";
import { DEFAULT_LOCALE } from "~/lib/i18n";
import PrimaryWorkDetail from "~/components/PrimaryWorkDetail.astro";

export async function getStaticPaths() {
  const works = await getCollection(
    "primary-works",
    (w) => !w.data.draft && w.data.language === DEFAULT_LOCALE,
  );
  return works.map((w) => ({ params: { slug: w.id }, props: { w } }));
}

const { w } = Astro.props;
---

<PrimaryWorkDetail entry={w} />
```

- [ ] **Step 1.2.3: Convert i18n route to a thin shell**

Rewrite `apps/site/src/pages/[lang]/primary-works/[slug].astro` to the same shell, with the filter inverted:

```astro
---
import { getCollection } from "astro:content";
import { DEFAULT_LOCALE, LOCALES, type LangCode } from "~/lib/i18n";
import PrimaryWorkDetail from "~/components/PrimaryWorkDetail.astro";

export async function getStaticPaths() {
  const works = await getCollection(
    "primary-works",
    (w) => !w.data.draft && w.data.language !== DEFAULT_LOCALE,
  );
  return works
    .filter((w) => LOCALES.includes(w.data.language as LangCode))
    .map((w) => ({ params: { lang: w.data.language, slug: w.id }, props: { w } }));
}

const { w } = Astro.props;
---

<PrimaryWorkDetail entry={w} />
```

### Task 1.3: Verify Chunk 1

- [ ] **Step 1.3.1: Build clean + page count unchanged**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/i18n-c1-build.log
ln -s ../dist/pagefind public/pagefind
! grep -qE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/i18n-c1-build.log || { echo "BUILD FAILED"; exit 1; }
test "$(find dist -name 'index.html' | wc -l)" = "$(cat /tmp/i18n-baseline-pages)" \
  || { echo "PAGE COUNT DRIFTED"; exit 1; }
echo "build clean + page count matches baseline"
```

- [ ] **Step 1.3.2: English primary-work page is bytes-identical (modulo whitespace)**

```bash
diff <(cat /tmp/i18n-baseline-html/primary-works_khoj-january-february-2007_index.html | tr -s '[:space:]' ' ') \
     <(cat apps/site/dist/primary-works/khoj-january-february-2007/index.html | tr -s '[:space:]' ' ') > /tmp/c1-en-diff.txt
# Acceptable: only data-astro-source-loc changes (line numbers shifted from extraction).
# UNACCEPTABLE: any visible-content differences (missing sections, changed text, dropped links).
wc -l /tmp/c1-en-diff.txt
# Inspect the diff manually to confirm it's all source-loc noise.
```

Note: `data-astro-source-loc` attribute changes are expected because the rendering moved files. Filter them out for a cleaner diff:

```bash
diff <(sed 's/data-astro-source-[a-z]*="[^"]*"//g' /tmp/i18n-baseline-html/primary-works_khoj-january-february-2007_index.html) \
     <(sed 's/data-astro-source-[a-z]*="[^"]*"//g' apps/site/dist/primary-works/khoj-january-february-2007/index.html) \
  | head -40
# Expected: empty (or close to it — only whitespace formatting differences).
```

- [ ] **Step 1.3.3: i18n primary-work page GAINS the previously-missing sections**

```bash
# The gu Khoj should now have the sections English has.
for marker in "Notable passages" "Themes" "Metadata and summary are AI-extracted"; do
  count=$(grep -c "$marker" apps/site/dist/gu/primary-works/khoj-january-february-2008/index.html)
  echo "  '$marker' on gu Khoj: $count"
done
# Each marker should be >= 1 (was 0 pre-refactor).
```

- [ ] **Step 1.3.4: i18n page still suppresses indexing of AI translations**

```bash
# Find an opinion or primary-work with translation_status: ai_translation
# and confirm its rendered page has <meta name="robots" content="noindex">.
ai_md=$(grep -l "translation_status:.*ai_translation" apps/site/src/content/primary-works/*.md 2>/dev/null | head -1)
if [ -n "$ai_md" ]; then
  slug=$(basename "$ai_md" .md)
  lang=$(grep "^language:" "$ai_md" | sed 's/language: //;s/"//g')
  url="apps/site/dist/${lang}/primary-works/${slug}/index.html"
  grep -c 'name="robots" content="noindex"' "$url"
fi
# Expected: 1 (the AI translation correctly gets noindex)
# If no ai_translation entries exist yet, skip this check.
```

### Task 1.4: Commit Chunk 1

- [ ] **Step 1.4.1: Commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/components/PrimaryWorkDetail.astro \
        apps/site/src/pages/primary-works/\[slug\].astro \
        apps/site/src/pages/\[lang\]/primary-works/\[slug\].astro
git commit -m "$(cat <<'EOF'
refactor(ui): collapse primary-work template into a shared component

Extract the full primary-work article UI into
apps/site/src/components/PrimaryWorkDetail.astro. Both routes —
/primary-works/<slug>/ (English) and /<lang>/primary-works/<slug>/
(i18n) — become thin shells that hand the entry to the shared
component.

Net effect:
- gu / hi / mr / bn primary-work pages (e.g. every Khoj issue) now
  render the same sections the English ones do: pull quotes,
  themes chips, Tier-B disclaimer, PeopleInPiece, RelatedSection,
  prose-styled body.
- English pages are bytes-identical (modulo data-astro-source-loc).
- The Option-1 band-aid for the duplicate Summary block becomes
  a no-op — the new architecture renders <Content /> as the single
  summary source by construction.

Language-specific behavior (noindex on AI translations, lang= on
body content, data-pagefind-filter:lang:X) lives inside the shared
component, read from entry.data.language / translation_status.

Pilot of docs/superpowers/plans/2026-05-25-i18n-template-consolidation.md.
Five more collections to follow.
EOF
)"
```

---

## Chunk 2: Thinkers (the biggest payoff)

Goal: Extract `ThinkerDetail.astro` from the 534-line English template. After this, gu / hi / mr / bn thinker pages gain the canon banner, classification chips, Pieces-by-X / Profile-pieces-about-X / Works-by-X sections, related contributors — currently they show only the bio.

Pattern is identical to Chunk 1: inventory differences, extract component, two thin shells, verify.

### Task 2.1: Inventory + extract

- [ ] **Step 2.1.1**: Side-by-side diff of `apps/site/src/pages/thinkers/[slug].astro` (534 lines) vs `[lang]/thinkers/[slug].astro` (85 lines). Tabulate which sections exist where.
- [ ] **Step 2.1.2**: Create `apps/site/src/components/ThinkerDetail.astro` carrying the union of the English UI. Particularly watch for:
  - `getCollection("opinions")` / `getCollection("primary-works")` calls for the cross-link sections — these run per page-build, so the component does them; consider memoization if build-time degrades.
  - Canon-tab logic and classification banner (read from `entry.data.canon_status`, `entry.data.tradition`).
  - Lang-conditional: `lang={entry.data.language}` on bio body; otherwise behavior is the same for en + i18n.
- [ ] **Step 2.1.3**: Rewrite both route shells to use the component.

### Task 2.2: Verify

Same four checks as Chunk 1: build clean, page count unchanged, English thinker page bytes-identical, i18n thinker page gains the missing sections.

⚠️ **Watch for:** the English thinker template currently iterates the full opinions + primary-works collections per thinker page. If this gets expensive (build time > 2× baseline), lift the cross-link queries into a build-time helper that runs once.

### Task 2.3: Commit Chunk 2

Commit message body: same shape as Chunk 1, naming the specific sections that now appear on i18n thinker pages.

---

## Chunk 3: Organisations

Pattern identical to Chunk 1. 170 → 65 line gap.

- [ ] Inventory en vs i18n organisation template.
- [ ] Extract `OrganisationDetail.astro`.
- [ ] Both routes → thin shells.
- [ ] Verify (build clean, English bytes-identical, i18n gains missing sections).
- [ ] Commit.

---

## Chunk 4: Opinions

Pattern identical. 99 → 72 line gap. Smaller delta — most of the English template just landed (the Chunk 4 contributors-collection landing added the "Written by" card and the byline-link update). The i18n opinion template doesn't yet render the "Written by" card.

Decision point: should i18n opinions render the "Written by" card? **Yes** — contributors are language-neutral (their bios are at `/contributors/<slug>/`, English-only for now, but the byline references resolve the same way). Port the inline ContributorCard render.

- [ ] Extract `OpinionDetail.astro`, including the "Written by" card.
- [ ] Both routes → thin shells.
- [ ] Verify; specifically: a gu / hi opinion (if any exist with `author:` set) renders the "Written by" card pointing at `/contributors/<slug>/`.
- [ ] Commit.

---

## Chunk 5: Musings

Pattern identical. 83 → 71 line gap — small. Mostly mechanical.

- [ ] Extract `MusingDetail.astro`.
- [ ] Both routes → thin shells.
- [ ] Verify.
- [ ] Commit.

---

## Chunk 6: Interviews

Pattern identical. 72 → 72 line gap — already near parity, mostly an exercise in consistency. Validate that English page is bytes-identical and i18n behavior doesn't regress.

- [ ] Extract `InterviewDetail.astro`.
- [ ] Both routes → thin shells.
- [ ] Verify.
- [ ] Commit.

---

## Chunk 7: Decision on /contributors/

The `/contributors/` collection landed English-only on 2026-05-25. No `[lang]/contributors/` route exists. Two paths:

**Option A (recommended for v1): Leave English-only.** Contributors are CCS fellows / interns; their bios are short English-language stubs. Until translated bios exist, there's nothing to render at `/gu/contributors/<slug>/`. The byline references on gu opinion pages already resolve to the English contributor page (cross-language link) — that's acceptable for v1.

**Option B (defer): Stub i18n contributor route.** Add `[lang]/contributors/[slug].astro` that filters `language !== "en"`, finds zero entries (because no contributor MD has `language` set), and emits no pages. Costs nothing today; ready for future translated bios.

- [ ] **Step 7.1**: Confirm Option A with Adnan before closing the plan. If Option B is preferred, add a tiny route shell as the seventh component-extraction. If Option A, mark this chunk as "no code change; design decision documented."

---

## Final acceptance

After all 6 (or 7) chunks land:

- [ ] **Acceptance #1**: `pnpm build` exits clean.
- [ ] **Acceptance #2**: `find apps/site/dist -name 'index.html' | wc -l` equals the baseline (1287). No page added; no page lost.
- [ ] **Acceptance #3**: For each of the 7 captured baseline snapshots in `/tmp/i18n-baseline-html/`, the corresponding post-refactor English page is bytes-identical modulo `data-astro-source-*` attributes. Use the `sed 's/data-astro-source-[a-z]*="[^"]*"//g'` diff.
- [ ] **Acceptance #4**: For at least one i18n page per content type (gu Khoj, gu/hi/mr/bn thinker if any exists, etc.), the rendered HTML now contains every section the English page renders — verified by grep for representative section markers.
- [ ] **Acceptance #5**: `<meta name="robots" content="noindex">` still appears on AI-translated entries (if any exist), and is absent on canonical entries.
- [ ] **Acceptance #6**: `<link rel="canonical">` and `<link rel="alternate" hreflang="X">` tags still emit correctly per the existing `BaseLayout` + `lib/i18n.ts` infrastructure (no changes expected — but verify).
- [ ] **Acceptance #7**: Pagefind index still contains the same number of indexed pages as baseline; lang filter still works (i.e. `data-pagefind-filter:lang:gu` appears on gu primary-works in the dist HTML).
- [ ] **Acceptance #8**: Final cross-chunk code reviewer reads the full diff from pre-Chunk-1 to final HEAD and signs off.

---

## Sequencing notes

- **Lower-risk ordering:** primary-works → musings → interviews → opinions → organisations → thinkers. The simplest collections get the pattern shaken out first; thinkers (the biggest, most complex) lands last when the pattern is well-tested.
- **Higher-impact ordering:** primary-works → thinkers → organisations → opinions → musings → interviews. Pays off the visible bugs (Khoj, gu thinkers) earliest.
- **Recommended:** higher-impact, with extra care on thinkers (Chunk 2). The Khoj fix and the thinker-page parity fix are what Adnan actually noticed.

## Stopping criteria

The work is "done" when:
- All chunks pass spec-compliance + code-quality review.
- `pnpm build` exits clean.
- Each acceptance check above passes.
- Adnan signs off on the visible result for a sampled gu page (Khoj) AND a sampled hi/mr/bn page (if any exist with non-English content).

## Reviewer dispatch template

For each chunk above, dispatch the spec-compliance reviewer and then the code-quality reviewer after the implementer reports DONE. Spec-compliance for this refactor means: "the English page is bytes-identical and the i18n page gained the previously-missing sections." Code-quality is the standard pass.

---

## Plan complete

After all 6 chunks pass review:

1. The terminal state is:
   - 6 new shared components under `apps/site/src/components/<Collection>Detail.astro`.
   - 12 route shells (one en + one i18n per collection), each ~25-30 lines.
   - i18n routes render the same UI as English routes for every content type.
   - Future feature additions land in one place per collection and propagate to both routes automatically.
2. Hand the diff to Adnan for review + push.
