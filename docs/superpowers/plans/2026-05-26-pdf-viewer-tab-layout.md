# Primary-Work Detail — Summary + PDF Tab Layout Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing primary-work detail page (`PrimaryWorkDetail.astro`) into a tabbed reading-mode layout: a **Summary** tab (today's content) plus a **Read full PDF** tab that lazy-loads an `<iframe>` of the work's PDF. Pages without `pdf_url` render unchanged.

**Architecture:** Single-file change to `apps/site/src/components/PrimaryWorkDetail.astro`. Restructure JSX to wrap existing summary content in a `role="tabpanel"` div, add a second `role="tabpanel"` for the PDF iframe (lazy-mounted), and add an inline `<script>` block (~40 LOC vanilla JS) that handles tab activation, lazy iframe injection on first activation, URL fragment sync (`#summary` / `#read`), and ARIA keyboard navigation. No new components, no new dependencies, no schema changes.

**Tech Stack:** Astro 5 (existing); Tailwind 4 with `aria-selected:` variant (built-in); vanilla JS (no framework). Per the spec at `docs/superpowers/specs/2026-05-26-pdf-viewer-tab-layout-design.md`.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `apps/site/src/components/PrimaryWorkDetail.astro` | MODIFY | Add `pageCount` derived variable. Remove inline "Read PDF" header button (its function moves to the second tab). Insert conditional tab nav + two tabpanel divs when `fm.pdf_url` is set. Rewrap existing summary body + pull quotes inside the Summary tabpanel. Update Tier-B disclaimer wording. Add inline `<script>` block for tab interactivity. |

**Nothing else touched.** No new files. No edits to `[slug].astro` routes (they're thin wrappers). No edits to global CSS — the design uses existing tokens.

**File-size budget:** the file currently has 249 lines; this change adds ~80 lines (variable + tab markup + script + disclaimer tweak) and removes ~10 lines (old PDF button block + simplification). Net: ~320 lines. Comfortable.

---

## Conventions to honour

- **Single-file diff.** No new components or files. If you find yourself wanting to extract a `PrimaryWorkTabs.astro`, stop and report — the spec explicitly chose inline.
- **Tailwind 4 with the `@import "tailwindcss"` setup.** The `aria-selected:` variant is built-in; no config edits.
- **Astro conditional attribute pattern.** When an attribute should be present only in tab mode, use `attr={fm.pdf_url ? "value" : undefined}`. Astro omits `undefined`-valued attributes.
- **No `Co-Authored-By` trailer** unless Adnan explicitly asks.
- **Commit messages:** `feat(ui):` for the component change. Verification commits are not needed (we don't commit grep output).
- **Per Adnan's autonomy preference:** don't push to origin; Adnan reviews + pushes manually.

---

## Pre-work baseline (run once before Chunk 1)

- [ ] **Step 0.1: Confirm clean tree and capture pre-work baseline SHA**

```bash
cd "/Users/siraj/Indian Liberals Website"
git status --short
# Expected: only the .claude/ + data/synthesis/*.jsonl untracked files
# (pre-existing per the user briefing). Tree clean otherwise.

# Capture the pre-work HEAD SHA — used later in §4.5.1 to verify exactly
# three new commits land for this plan. Save the SHA somewhere (note it
# in your task tracker or set an env var that survives across chunks).
PREWORK_SHA=$(git rev-parse --short HEAD)
echo "Pre-work baseline SHA: $PREWORK_SHA"
# Expected: most recent docs(spec): ... commit (currently 33cbfe2 at the
# time this plan was written; whatever the actual HEAD is when you start
# is the right baseline).
```

- [ ] **Step 0.2: Smoke-build the site to capture baseline**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/tabs-build-baseline.log | tail -5
ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/tabs-build-baseline.log
# Expected: 0
find dist -name 'index.html' | wc -l
# Expected: 1287
```

- [ ] **Step 0.3: Confirm sample slugs are still valid**

```bash
cd "/Users/siraj/Indian Liberals Website"
# Slug WITH pdf_url:
grep "^pdf_url:" apps/site/src/content/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980.md
# Expected: prints `pdf_url: https://indianliberals.in/.../...pdf`

# Slug WITHOUT pdf_url:
grep "^pdf_url:" apps/site/src/content/primary-works/khoj-november-december-2009.md
# Expected: empty (exit code 1 is fine — no match)
```

---

## Chunk 1: Component prep — TypeScript variables + header cleanup

Goal: Add the `pageCount` derived variable, remove the old inline "Read PDF" header button (it becomes the second tab in Chunk 2), and update the Tier-B disclaimer wording. The page is briefly in an in-between state at end of Chunk 1 — no tab nav yet, no header PDF button either — but the build is clean.

### Task 1.1: Add `pageCount` variable

**Files:**
- Modify: `apps/site/src/components/PrimaryWorkDetail.astro` (TypeScript block, around line 73 alongside `pagesNote`)

- [ ] **Step 1.1.1: Locate the `pagesNote` block**

Open the file. Find:

```ts
// Page count for the public-facing badge. ...
const pagesNote = (() => {
  const t = fm.physical?.pages_total ?? fm.physical?.page_count;
  return t ? `${t} pages` : "";
})();
```

This is around line 70–73 in the current file.

- [ ] **Step 1.1.2: Add `pageCount` immediately after `pagesNote`**

Insert this block right after the `pagesNote` IIFE (still in the TypeScript frontmatter section):

```ts
// Bare integer for the "Read full PDF · N pages" tab label suffix.
// Distinct from `pagesNote` (a formatted string used by the header badge).
// `null` when the page count is unknown — tab label then degrades to
// "Read full PDF" (no suffix).
const pageCount: number | null = fm.physical?.pages_total ?? fm.physical?.page_count ?? null;
```

- [ ] **Step 1.1.3: Run a typecheck-via-build to confirm no errors**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
pnpm build 2>&1 | tail -3
# Expected: build completes; no TS errors about pageCount.
```

### Task 1.2: Remove the old inline "Read PDF" header button

**Files:**
- Modify: `apps/site/src/components/PrimaryWorkDetail.astro` (around lines 176–186)

- [ ] **Step 1.2.1: Delete the PDF link block**

Find this JSX block (around lines 176–186):

```astro
{/* PDF link */}
{fm.pdf_url && (
  <div class="mt-6 flex flex-wrap gap-3 font-(family-name:--font-ui)">
    <a
      href={fm.pdf_url}
      class="inline-flex items-center gap-2 px-5 py-2.5 bg-(--color-fg) text-(--color-bg) rounded-full text-sm font-semibold no-underline hover:bg-(--color-forest-700) transition-colors"
    >
      Read PDF <span aria-hidden>↗</span>
    </a>
  </div>
)}
```

Delete it entirely — including the `{/* PDF link */}` comment and the surrounding blank line. The button's role moves to the tab nav added in Chunk 2.

- [ ] **Step 1.2.2: Confirm the header still closes cleanly**

The header block should now end with the `pagesNote` paragraph (~line 173 originally). The `</header>` closing tag follows (originally around line 187). Verify no stray braces or orphaned JSX.

### Task 1.3: Update Tier-B disclaimer wording

**Files:**
- Modify: `apps/site/src/components/PrimaryWorkDetail.astro` (Tier-B disclaimer block, originally lines 234–239)

- [ ] **Step 1.3.1: Update the disclaimer text**

Find:

```astro
{/* Tier-B disclaimer */}
<p class="mt-12 pt-6 border-t border-(--color-border) text-xs text-(--color-fg-muted) font-(family-name:--font-ui) italic">
  Metadata and summary are AI-extracted from the source PDF and reviewed for
  editorial accuracy. The original work is available via the PDF link above;
  paragraph-level citation inside the PDF is deferred to a future engagement.
</p>
```

Replace the inner text with:

```astro
{/* Tier-B disclaimer */}
<p class="mt-12 pt-6 border-t border-(--color-border) text-xs text-(--color-fg-muted) font-(family-name:--font-ui) italic">
  Metadata and summary are AI-extracted from the source PDF and reviewed for
  editorial accuracy. The original work is available via the Read PDF tab above
  (where present); paragraph-level citation inside the PDF is deferred to a
  future engagement.
</p>
```

The wording change is "PDF link above" → "Read PDF tab above (where present)". The "(where present)" hedge covers the no-`pdf_url` case acceptably. (Per spec §10, a broader fix for the no-PDF case is a separate follow-up.)

### Task 1.4: Build clean, commit

- [ ] **Step 1.4.1: Build**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
pnpm build 2>&1 | tee /tmp/tabs-build-chunk1.log | tail -5
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/tabs-build-chunk1.log
# Expected: 0
find dist -name 'index.html' | wc -l
# Expected: 1287
```

- [ ] **Step 1.4.2: Spot-check the in-progress state**

```bash
# A PDF-having work should NOT have any "Read PDF" affordance right now (we deleted it; tab nav lands in Chunk 2):
grep -c "Read PDF\|role=\"tab\"" dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html
# Expected: 0 (no Read PDF text yet, no tab nav yet — this is the in-between state)

# Disclaimer wording updated:
grep "Read PDF tab above" dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html
# Expected: prints the line (disclaimer has the new wording)
```

- [ ] **Step 1.4.3: Commit Chunk 1**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/components/PrimaryWorkDetail.astro
git commit -m "feat(ui): prep primary-work detail for tab layout

- Add pageCount integer variable (separate from pagesNote string)
- Remove inline 'Read PDF' header button (becomes second tab in
  follow-up commit)
- Update Tier-B disclaimer wording from 'PDF link above' to
  'Read PDF tab above (where present)'

This commit alone leaves PDF-having works without any PDF affordance.
The tab nav lands in the next commit."
```

---

## Chunk 2: Tab nav + tabpanel structure

Goal: Add the WAI-ARIA tab control. Wrap the existing summary content (prose-container + pull quotes) in `role="tabpanel"` div. Add a second tabpanel for the PDF iframe (lazy mount, no iframe in DOM yet). Build clean; tabs visible but non-interactive (JS lands in Chunk 3).

### Task 2.1: Insert tab nav

**Files:**
- Modify: `apps/site/src/components/PrimaryWorkDetail.astro` (immediately after the closing `</header>` tag, around line 187)

- [ ] **Step 2.1.1: Locate the end of `<header>`**

The `<header>` block now ends with:

```astro
      {pagesNote && (
        <p class="mt-1 text-xs text-(--color-fg-muted) font-(family-name:--font-ui)">{pagesNote}</p>
      )}
    </header>
```

- [ ] **Step 2.1.2: Add the tab nav immediately after `</header>`**

Insert this block on the line directly after `</header>` (and before the `{/* Body markdown */}` comment):

```astro
    {/* Tab nav — only when this work has a downloadable PDF.
        Both buttons share identical Tailwind classes; aria-selected: drives the active style. */}
    {fm.pdf_url && (
      <div
        role="tablist"
        aria-label="Reading modes"
        class="border-b border-(--color-border) mb-8 flex font-(family-name:--font-ui)"
      >
        <button
          role="tab"
          id="tab-summary"
          aria-controls="panel-summary"
          aria-selected="true"
          tabindex="0"
          class="px-4 py-3 text-sm font-semibold border-b-2 border-transparent
                 aria-selected:border-(--color-saffron-700) aria-selected:text-(--color-fg)
                 text-(--color-fg-muted) hover:text-(--color-fg) cursor-pointer
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-(--color-saffron-500)
                 -mb-px transition-colors"
        >
          Summary
        </button>
        <button
          role="tab"
          id="tab-read"
          aria-controls="panel-read"
          aria-selected="false"
          tabindex="-1"
          class="px-4 py-3 text-sm font-semibold border-b-2 border-transparent
                 aria-selected:border-(--color-saffron-700) aria-selected:text-(--color-fg)
                 text-(--color-fg-muted) hover:text-(--color-fg) cursor-pointer
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-(--color-saffron-500)
                 -mb-px transition-colors"
        >
          {pageCount ? `Read full PDF · ${pageCount} pages` : "Read full PDF"}
        </button>
      </div>
    )}
```

### Task 2.2: Wrap Summary content in a tabpanel div

**Files:**
- Modify: `apps/site/src/components/PrimaryWorkDetail.astro` (around lines 189–220 — the prose-container + pull quotes block)

- [ ] **Step 2.2.1: Locate the current body block**

The existing structure (post-Chunk-1):

```astro
    {/* Body markdown — ... */}
    <div class="prose-container mb-10">
      <div class="text-(--color-fg) leading-relaxed [&_>_h1]:hidden ...">
        <Content />
      </div>
    </div>

    {/* Pull quotes */}
    {pullQuotes.length > 0 && (
      <section class="mb-10">
        <h2 class="text-xs uppercase tracking-widest text-(--color-fg-muted) font-(family-name:--font-ui) mb-4">
          Notable passages
        </h2>
        <div class="space-y-6">
          {pullQuotes.map((q) => (
            <figure ...>...</figure>
          ))}
        </div>
      </section>
    )}
```

- [ ] **Step 2.2.2: Wrap both blocks in a single Summary tabpanel div**

Wrap the body markdown div + the pull quotes section together in a single `<div>` that gets `role="tabpanel"` only when `fm.pdf_url` is set. Replace the existing markup with:

```astro
    {/* Summary tabpanel (in tab mode) or just the body section (no-PDF mode).
        When fm.pdf_url is unset, role/id/aria-labelledby are all undefined and
        Astro omits them — the div renders as a plain wrapper. */}
    <div
      role={fm.pdf_url ? "tabpanel" : undefined}
      id={fm.pdf_url ? "panel-summary" : undefined}
      aria-labelledby={fm.pdf_url ? "tab-summary" : undefined}
    >
      {/* Body markdown — contains the full Summary, Key points, and any
          additional sections the emitter wrote. The frontmatter `summary` and
          `ai_key_points` fields are intentionally truncated for the search
          index / og:description; the body is the canonical text shown to
          readers. The `[&_>_h1]:hidden` rule suppresses the body's duplicate
          H1 (the page header above already shows the title). */}
      <div class="prose-container mb-10">
        <div class="text-(--color-fg) leading-relaxed [&_>_h1]:hidden [&_p]:my-4 [&_p]:text-[1.0625rem] [&_h2]:text-xs [&_h2]:uppercase [&_h2]:tracking-widest [&_h2]:text-(--color-fg-muted) [&_h2]:font-(family-name:--font-ui) [&_h2]:font-semibold [&_h2]:mt-10 [&_h2]:mb-4 [&_h3]:mt-8 [&_h3]:mb-3 [&_a]:text-(--color-forest-700) [&_ul]:my-5 [&_ul]:list-disc [&_ul]:pl-6 [&_ul_li]:my-2 [&_ul_li]:text-[1.0625rem] [&_blockquote]:border-l-2 [&_blockquote]:border-(--color-saffron-500) [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-(--color-fg-muted) [&_em]:italic">
          <Content />
        </div>
      </div>

      {/* Pull quotes */}
      {pullQuotes.length > 0 && (
        <section class="mb-10">
          <h2 class="text-xs uppercase tracking-widest text-(--color-fg-muted) font-(family-name:--font-ui) mb-4">
            Notable passages
          </h2>
          <div class="space-y-6">
            {pullQuotes.map((q) => (
              <figure class="border-l-2 border-(--color-saffron-500) pl-5 py-1">
                <blockquote class="text-lg leading-relaxed text-(--color-fg) italic font-(family-name:--font-display)">
                  "{q.verbatim}"
                </blockquote>
                <figcaption class="mt-2 text-xs uppercase tracking-widest text-(--color-fg-muted) font-(family-name:--font-ui)">
                  {q.why_notable ? q.why_notable.replace(/_/g, " ") : ""}{q.page ? ` · p. ${q.page}` : ""}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}
    </div>
```

The contents of `prose-container` and the pull quotes section are unchanged — only the outer wrapping div is new, and its `role`/`id`/`aria-labelledby` attributes are conditionally set.

### Task 2.3: Add the Read PDF tabpanel

**Files:**
- Modify: `apps/site/src/components/PrimaryWorkDetail.astro` (immediately after the Summary tabpanel wrapper closes, before the Themes block)

- [ ] **Step 2.3.1: Insert the Read PDF tabpanel block**

Immediately after the closing `</div>` of the Summary wrapper added in Step 2.2.2 (and before the `{themesPretty.length > 0 && ...}` Themes block), insert:

```astro
    {/* Read PDF tabpanel — only when this work has a downloadable PDF.
        Iframe is NOT rendered server-side; the inline script at the bottom
        injects it lazily on first tab activation. */}
    {fm.pdf_url && (
      <div
        role="tabpanel"
        id="panel-read"
        aria-labelledby="tab-read"
        hidden
        class="mb-10"
      >
        <div data-pdf-mount data-pdf-url={fm.pdf_url}></div>
        <p class="mt-3 text-sm font-(family-name:--font-ui)">
          <a
            href={fm.pdf_url}
            target="_blank"
            rel="noopener"
            class="text-(--color-forest-700) hover:underline"
          >
            Open in new tab ↗
          </a>
        </p>
      </div>
    )}
```

The `hidden` attribute starts the panel collapsed (semantic hidden = `display:none`). The empty `<div data-pdf-mount>` is the mount point the inline script targets.

### Task 2.4: Build clean, commit

- [ ] **Step 2.4.1: Build**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
pnpm build 2>&1 | tee /tmp/tabs-build-chunk2.log | tail -5
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/tabs-build-chunk2.log
# Expected: 0
find dist -name 'index.html' | wc -l
# Expected: 1287
```

- [ ] **Step 2.4.2: Spot-check both branches**

```bash
# A PDF-having work should now have a tab nav + 2 tabpanels:
grep -c 'role="tab"' dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html
# Expected: 2 (two <button role="tab"> elements)

grep -c 'role="tabpanel"' dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html
# Expected: 2 (Summary + Read PDF panels)

grep -c 'data-pdf-mount' dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html
# Expected: 1

grep -c 'Open in new tab' dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html
# Expected: 1

# A no-PDF work should have NO tab nav and NO tabpanel role attributes:
grep -c 'role="tab"' dist/primary-works/khoj-november-december-2009/index.html
# Expected: 0

grep -c 'role="tabpanel"' dist/primary-works/khoj-november-december-2009/index.html
# Expected: 0

grep -c 'data-pdf-mount' dist/primary-works/khoj-november-december-2009/index.html
# Expected: 0
```

- [ ] **Step 2.4.3: Commit Chunk 2**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/components/PrimaryWorkDetail.astro
git commit -m "feat(ui): add tab nav + tabpanels for primary-work detail

WAI-ARIA tabs structure for works that carry pdf_url:
  - role='tablist' with two role='tab' buttons (Summary / Read full PDF)
  - role='tabpanel' wrapper around the existing summary body + pull
    quotes
  - role='tabpanel' for the PDF with an empty data-pdf-mount div
    (iframe is lazy-injected by a JS script in the next commit)

Pages without pdf_url get no tab nav and no role attributes — the
summary wrapper div renders as a plain container. Build clean; tabs
are visible but non-interactive without the JS."
```

---

## Chunk 3: Inline tab activation + lazy iframe injection script

Goal: Add a single `<script>` block at the bottom of the component (just before `</BaseLayout>` close, or at the very end of `<article>`). The script wires tab activation, lazy iframe injection on first Read PDF tab open, URL fragment sync, and ARIA keyboard navigation.

### Task 3.1: Insert the script

**Files:**
- Modify: `apps/site/src/components/PrimaryWorkDetail.astro` (immediately before the closing `</article>` tag, near the end of the component)

- [ ] **Step 3.1.1: Locate the closing `</article>`**

The component currently ends with:

```astro
    <PeopleInPiece ... />
    <RelatedSection ... />
  </article>
</BaseLayout>
```

- [ ] **Step 3.1.2: Insert the script block immediately before `</article>`**

Add this on a new line, after `<RelatedSection />` and before `</article>`:

```astro
    <script is:inline>
      (() => {
        const tablist = document.querySelector('[role="tablist"]');
        if (!tablist) return; // No-op for pages without pdf_url.

        const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
        const panels = tabs.map((t) => document.getElementById(t.getAttribute('aria-controls')));

        function activate(idx, { syncHash = true, focusTab = true } = {}) {
          tabs.forEach((t, i) => {
            const selected = i === idx;
            t.setAttribute('aria-selected', selected);
            t.tabIndex = selected ? 0 : -1;
            panels[i].hidden = !selected;
          });

          // Lazy-inject iframe on first activation of the Read PDF panel.
          if (idx === 1) {
            const mount = panels[1].querySelector('[data-pdf-mount]');
            if (mount && !mount.dataset.loaded) {
              const url = mount.dataset.pdfUrl;
              const iframe = document.createElement('iframe');
              iframe.src = url;
              iframe.title = document.title;
              iframe.style.width = '100%';
              iframe.style.height = window.matchMedia('(max-width: 768px)').matches ? '70vh' : '80vh';
              iframe.style.border = '0';
              // No loading="lazy" — the iframe is only constructed on click,
              // so it's already lazy in the meaningful sense.
              mount.appendChild(iframe);
              mount.dataset.loaded = 'true';
            }
          }

          if (syncHash) {
            const fragment = idx === 1 ? '#read' : '#summary';
            history.replaceState(null, '', fragment);
          }
          if (focusTab) tabs[idx].focus({ preventScroll: true });
        }

        tabs.forEach((tab, i) => {
          tab.addEventListener('click', () => activate(i));
          tab.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight') activate((i + 1) % tabs.length);
            if (e.key === 'ArrowLeft') activate((i - 1 + tabs.length) % tabs.length);
          });
        });

        // Honor initial URL hash. #read → PDF tab. Anything else → Summary.
        // Do NOT focus the tab on hash-init — a deep-linked visitor expects
        // to start reading, not to have a tab control under their cursor.
        const initial = window.location.hash === '#read' ? 1 : 0;
        if (initial !== 0) {
          activate(initial, { syncHash: false, focusTab: false });
        }
      })();
    </script>
```

The `is:inline` directive is Astro's way of saying "ship this script verbatim, don't bundle, don't process." That's what we want — the script is self-contained, runs once, no module imports.

### Task 3.2: Build + spot-check that script is emitted

- [ ] **Step 3.2.1: Build**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
pnpm build 2>&1 | tee /tmp/tabs-build-chunk3.log | tail -5
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/tabs-build-chunk3.log
# Expected: 0
find dist -name 'index.html' | wc -l
# Expected: 1287
```

- [ ] **Step 3.2.2: Confirm the script is present in PDF-having pages and present-but-inert in no-PDF pages**

```bash
# PDF-having work: mount div + the script's querySelector call both present.
page=apps/site/dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html
grep -c 'data-pdf-mount' "$page"
# Expected: 1
grep -c 'querySelector' "$page"
# Expected: ≥ 1 (the script's tablist query is present)

# Astro emits the same script on every primary-work page (since the
# component contains it), even for no-PDF works. That's fine — the
# script's outer `if (!tablist) return;` guard makes it a no-op there.
# Find a no-PDF page in whichever language route it lives:
no_pdf_page=$(find apps/site/dist -path '*/primary-works/khoj-november-december-2009/index.html' | head -1)
grep -c 'querySelector' "$no_pdf_page"
# Expected: ≥ 1 (script present but inert because no tablist exists)
```

- [ ] **Step 3.2.3: Commit Chunk 3**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/components/PrimaryWorkDetail.astro
git commit -m "feat(ui): inline tab JS — activation, lazy iframe, hash sync

Vanilla JS (~40 LOC) added as an Astro is:inline script:
  - On click / arrow key: swap aria-selected, hidden, tabindex; sync
    URL fragment (#summary or #read)
  - First time Read PDF tab activates: inject <iframe src={pdf_url}>
    into data-pdf-mount with ~80vh / 70vh-mobile height
  - On page load: honor #read hash to deep-link to PDF tab, but do
    NOT focus the tab button (preserves reading flow for deep links)
  - Pages without tablist (no-PDF works): script is a no-op via the
    initial 'if (!tablist) return;' guard"
```

---

## Chunk 4: Verification — rendered HTML, accessibility, smoke

Goal: Validate the implementation against the spec's §8 checks. No code edits expected (if something fails, return to the relevant Chunk to fix).

### Task 4.1: Rendered-HTML spot checks (spec §8.2)

- [ ] **Step 4.1.1: PDF-having sample (3 slugs)**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site/dist"
for slug in \
  "a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980" \
  "an-infationary-budget-a-d-shroff-jun7-1959" \
  "challenges-of-transforming-india-amitabh-kant" ; do
  echo "=== $slug ==="
  page="primary-works/$slug/index.html"
  [ -f "$page" ] || { echo "  NOT FOUND"; continue; }
  echo "  role=tab count: $(grep -c 'role="tab"' "$page")"           # Expect 2
  echo "  role=tabpanel count: $(grep -c 'role="tabpanel"' "$page")" # Expect 2
  echo "  data-pdf-mount count: $(grep -c 'data-pdf-mount' "$page")" # Expect 1
  echo "  Open in new tab: $(grep -c 'Open in new tab' "$page")"     # Expect 1
  echo "  aria-selected=true count: $(grep -c 'aria-selected="true"' "$page")"   # Expect 1
  echo "  aria-selected=false count: $(grep -c 'aria-selected="false"' "$page")" # Expect 1
done
```

Expected: all three slugs report `2 / 2 / 1 / 1 / 1 / 1`.

- [ ] **Step 4.1.2: No-PDF sample (3 slugs)**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site/dist"
for slug in \
  "khoj-november-december-2009" \
  "aandolan" \
  "anavyartha-1" ; do
  echo "=== $slug ==="
  page="primary-works/$slug/index.html"
  [ -f "$page" ] || page="hi/primary-works/$slug/index.html"
  [ -f "$page" ] || page="mr/primary-works/$slug/index.html"
  [ -f "$page" ] || page="gu/primary-works/$slug/index.html"
  [ -f "$page" ] || { echo "  NOT FOUND in any lang"; continue; }
  echo "  page: $page"
  echo "  role=tab count: $(grep -c 'role="tab"' "$page")"           # Expect 0
  echo "  role=tabpanel count: $(grep -c 'role="tabpanel"' "$page")" # Expect 0
  echo "  data-pdf-mount count: $(grep -c 'data-pdf-mount' "$page")" # Expect 0
done
```

Expected: all three report `0 / 0 / 0`.

- [ ] **Step 4.1.3: Disclaimer wording present on every primary-work page**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site/dist"
# Sample a handful of slugs from both branches:
for slug in \
  "a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980" \
  "khoj-november-december-2009" \
  "an-infationary-budget-a-d-shroff-jun7-1959" ; do
  page=$(find . -path "*/primary-works/$slug/index.html" 2>/dev/null | head -1)
  [ -z "$page" ] && continue
  echo "=== $slug ==="
  grep -c "Read PDF tab above" "$page"   # Expect 1 (new wording)
  grep -c "PDF link above" "$page"       # Expect 0 (old wording gone)
done
```

### Task 4.2: Page-count sanity (spec §8.1)

- [ ] **Step 4.2.1: Total pages unchanged**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
find dist -name 'index.html' | wc -l
# Expected: 1287 (baseline from pre-work)
```

- [ ] **Step 4.2.2: Build log free of errors**

```bash
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/tabs-build-chunk3.log
# Expected: 0
```

### Task 4.3: Browser smoke (manual or via `browse` MCP)

Spec §8.3 — these checks require a running browser. The `gstack` / `browse` MCP can script the clicks; otherwise start the dev server and click manually.

- [ ] **Step 4.3.1: Start preview server**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
pnpm preview &
# Note the URL printed (typically http://localhost:4321/).
# Wait ~3s for it to come up.
sleep 3
```

- [ ] **Step 4.3.2: PDF-having page — manual checks**

Open `http://localhost:4321/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/`. Confirm:

- [ ] Tab nav visible with "Summary" highlighted, "Read full PDF · {N} pages" inactive.
- [ ] Summary content (AI summary body, pull quotes) visible below tabs.
- [ ] Click "Read full PDF" tab → Summary content hides, PDF embed loads inline. URL fragment becomes `#read`.
- [ ] In DevTools Network panel: first PDF request fires NOW (not on initial page load).
- [ ] Click "Summary" → PDF panel hides, Summary content reappears. URL fragment becomes `#summary`.
- [ ] Switch back to "Read full PDF" → PDF panel reappears instantly (iframe persists in DOM).
- [ ] "Open in new tab ↗" link below the iframe opens the PDF in a new browser tab.

- [ ] **Step 4.3.3: Deep-link `#read`**

Open `http://localhost:4321/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/#read` directly.

- [ ] Read PDF tab is active on initial render; iframe present in DOM.
- [ ] Focus is NOT on the tab control (no visible focus ring on tab buttons).

- [ ] **Step 4.3.4: No-PDF page**

Open `http://localhost:4321/gu/primary-works/khoj-november-december-2009/` (or whichever language route resolves).

- [ ] No tab nav visible.
- [ ] Page reads as a single column: header, AI summary, themes, disclaimer, people, related.
- [ ] DevTools: no console errors. The inline script is present but is a no-op.

- [ ] **Step 4.3.5: Keyboard navigation**

Back on the PDF-having page:
- [ ] Press Tab until the Summary tab button has focus (visible focus ring).
- [ ] Press → arrow key — focus and active state move to "Read full PDF". Iframe injects.
- [ ] Press ← arrow key — focus and active state return to "Summary".
- [ ] Press Tab again — focus moves past the tab control into the content.

- [ ] **Step 4.3.6: Stop preview server**

```bash
# Find and kill the preview server (substitute PID from pnpm preview output, or):
pkill -f "astro preview" || true
```

### Task 4.4: Accessibility audit (spec §8.4)

- [ ] **Step 4.4.1: Static ARIA grep**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site/dist"
page="primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html"

# Expected ARIA attributes present:
for attr in 'role="tablist"' 'aria-label="Reading modes"' 'role="tab"' 'aria-controls="panel-summary"' 'aria-controls="panel-read"' 'role="tabpanel"' 'aria-labelledby="tab-summary"' 'aria-labelledby="tab-read"'; do
  count=$(grep -c "$attr" "$page")
  echo "  '$attr': $count"
done
```

Expected: all attributes present at least once. `role="tab"` and `role="tabpanel"` count 2 each; others count 1.

- [ ] **Step 4.4.2: Contrast check via accesslint:contrast-checker**

The active tab uses `aria-selected:text-(--color-fg)` against the page background; inactive uses `text-(--color-fg-muted)`. The active underline is `aria-selected:border-(--color-saffron-700)`. Use the contrast-checker skill on these color-pair combos:

- `--color-fg` on `--color-bg` — active tab label vs page background (should pass WCAG AA already; this is the body text combo).
- `--color-fg-muted` on `--color-bg` — inactive tab label vs page background.
- `--color-saffron-700` on `--color-bg` — active tab underline accent.

Run the accesslint:contrast-checker skill against these pairs. Document any failing pair in the task report.

### Task 4.5: Final acceptance + handoff

- [ ] **Step 4.5.1: Confirm git log**

```bash
cd "/Users/siraj/Indian Liberals Website"
# Use the $PREWORK_SHA captured in Step 0.1. If you lost it, the three
# commits below are the new feat(ui): commits; everything before them
# is pre-work.
git log --oneline "${PREWORK_SHA}..HEAD"
# Expected: 3 commits (one per chunk):
#   <sha>  feat(ui): inline tab JS — activation, lazy iframe, hash sync
#   <sha>  feat(ui): add tab nav + tabpanels for primary-work detail
#   <sha>  feat(ui): prep primary-work detail for tab layout
```

- [ ] **Step 4.5.2: Final build sanity**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/tabs-build-final.log | tail -5
ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/tabs-build-final.log
# Expected: 0
find dist -name 'index.html' | wc -l
# Expected: 1287
```

- [ ] **Step 4.5.3: Hand off to Adnan**

Surface to Adnan:
- All three commits landed locally on `main`.
- Build clean, page count 1287.
- Three PDF-having samples render tab nav + 2 tabpanels + iframe mount.
- Three no-PDF samples render unchanged (no tabs).
- Browser smoke checks (4.3.x) passed.
- Accessibility audit (4.4) passed.
- **DO NOT push.** Adnan reviews + pushes manually.

---

## Final acceptance

- [ ] **Acceptance #1:** `pnpm build` exits clean. (§8.1)
- [ ] **Acceptance #2:** `find apps/site/dist -name 'index.html' \| wc -l` equals 1287. (§8.1)
- [ ] **Acceptance #3:** Three randomly-picked PDF-having primary-work pages each grep to 2× `role="tab"`, 2× `role="tabpanel"`, 1× `data-pdf-mount`, 1× `Open in new tab`. (§8.2)
- [ ] **Acceptance #4:** Three randomly-picked no-PDF primary-work pages each grep to 0× `role="tab"`, 0× `role="tabpanel"`, 0× `data-pdf-mount`. (§8.2)
- [ ] **Acceptance #5:** Browser smoke (Task 4.3): tab switching works, lazy load fires only on click, deep-link `#read` activates the PDF tab without trapping focus. (§8.3)
- [ ] **Acceptance #6:** ARIA attributes all emitted (Task 4.4.1). (§8.4)
- [ ] **Acceptance #7:** Contrast check passes on the three tab color pairs (Task 4.4.2). (§8.4)
- [ ] **Acceptance #8:** Performance check (DevTools Network): PDF iframe fires zero requests until the user clicks the Read PDF tab. (§8.5)
- [ ] **STOP** — do NOT push. Surface to Adnan for the push call.

---

## Sequencing notes

- Chunks 1–3 each produce ONE commit. Chunk 4 produces no commits (verification only).
- The in-between state at end of Chunk 1 (PDF-having pages lose the "Read PDF" button before the tab nav lands) is intentional but should not be exposed to users. Don't push between chunks; complete all three before pushing.
- If the spec-reviewer or code-reviewer flags a real defect in any chunk, fix in place (small follow-up commit) before proceeding.

## Stopping criteria

The work is "done" when:
- All 3 code chunks have approved spec + code reviews.
- All 8 final acceptance checks pass.
- A final code-reviewer pass signs off.
- Adnan signs off on the visible result (3 sampled PDF-having pages + 3 no-PDF pages).

## Out of scope (per spec §2 and §10)

- Custom PDF.js / flipbook renderer (blocked by CORS until R2 migration).
- Pre-rendered PDF page images (build step out of scope this iteration).
- Hiding the browser PDF chrome.
- UI string translation infrastructure (tab labels stay English).
- Server-side PDF proxy.
- The Tier-B disclaimer / no-pdf_url bug — only partially addressed; full fix is a separate task.
- Reading-progress state, bookmarks, "where I left off".
- PDF text search highlighting / cross-tab search integration.

---

## Plan complete

After all chunks pass:

1. The terminal state is:
   - 1 file modified (`apps/site/src/components/PrimaryWorkDetail.astro`), 3 commits.
   - Every primary-work page with `pdf_url` renders a tabbed reading-mode UI.
   - Every primary-work page without `pdf_url` renders unchanged.
   - Build clean, page count 1287, contrast passes.
2. Hand the diff to Adnan for review + push.
