# Primary-Work Detail — Summary + PDF Tab Layout — Design Spec

**Author:** Adnan
**Date:** 2026-05-26
**Status:** locked

## 1. Goal

Restructure the primary-work detail page (`PrimaryWorkDetail.astro`) so that, when a work has a `pdf_url`, the page exposes both the AI-extracted Summary **and** the full original PDF as first-class, equally-prominent reading modalities — switchable via a tab control. The current page only shows the summary; the PDF lives behind a small "Read PDF ↗" header button that takes the user off-site. With 275 of 381 primary-works now carrying a `pdf_url` (per the prior PDF reconciliation work), inline access to the original text is a visible gap.

The terminal state:

1. Every primary-work page that has `pdf_url` renders a tab control: **Summary** | **Read full PDF · N pages**.
2. The Summary tab content matches what the page shows today (AI summary body + pull quotes).
3. The Read PDF tab embeds the PDF in a browser-native `<iframe>` at ~80vh, with a small "Open in new tab ↗" fallback link below.
4. Tab state is reflected in the URL fragment (`#read` activates the PDF tab; bare URL or `#summary` activates Summary). Tab switching does not scroll.
5. The PDF iframe is **lazy** — not inserted into DOM until the user activates the Read PDF tab the first time. Once inserted, it persists.
6. Pages without `pdf_url` render the existing single-column layout unchanged — no tab nav, no empty placeholder.
7. The build remains clean (page count 1287, Zod validates all `pdf_url`s).

## 2. Non-goals

- **Custom PDF rendering** (PDF.js, flipbook, page-turn animations). Prod PDFs at `indianliberals.in` do not send CORS headers, so JS-based renderers cannot fetch them client-side. Iframe is the only path until R2 migration (separate spec).
- **Pre-rendered page images** for an "Internet Archive book reader" experience. Out of scope; would require a build-step that's not justified for this iteration.
- **Hiding the browser's PDF chrome.** `#toolbar=0&navpanes=0` is Chrome-only. Trying to enforce it creates inconsistent cross-browser behaviour and removes useful affordances (download, print, find, zoom, page nav). Keep browser-native chrome.
- **UI string translation infrastructure.** The project doesn't have one today; "Summary" / "Read full PDF" labels are hardcoded English, consistent with the existing "Read PDF" button. A site-wide UI-translation pass is a separate task.
- **Server-side PDF proxy.** Would solve CORS but adds infrastructure; not justified for this iteration. R2 migration achieves the same outcome better.
- **Fixing the "Tier-B disclaimer / no-pdf_url" bug** flagged in the i18n consolidation review. Separate follow-up.
- **Reading-progress state**, "where I left off", bookmarks. Out of scope.
- **PDF text search highlighting** across summary ↔ PDF. The browser's PDF viewer has its own find; we don't try to integrate it with Pagefind.

## 3. Scope

- **One Astro component edit:** `apps/site/src/components/PrimaryWorkDetail.astro` (the shared component used by both `/primary-works/[slug].astro` and `/[lang]/primary-works/[slug].astro`).
- **One new self-contained UI primitive:** an inline tabs implementation. Either:
  - Inline `<script>` block at the bottom of `PrimaryWorkDetail.astro` (preferred — keeps the page self-contained), OR
  - A new `apps/site/src/components/PrimaryWorkTabs.astro` if the code grows beyond ~60 lines.
- **No new dependencies.** Vanilla JS for tab state + lazy iframe injection + URL fragment sync. No Alpine, no React, no Astro client islands beyond a `<script>` block.
- **No content-collection schema changes.** `pdf_url` is already in the schema and already validated by Zod's `.url()`.

## 4. Architecture

```
                  /primary-works/<slug>/
                  /<lang>/primary-works/<slug>/
                            │
                            ▼
            ┌───────── BaseLayout.astro ───────────┐
            │                                       │
            │  ┌──── PrimaryWorkDetail.astro ────┐ │
            │  │                                  │ │
            │  │   ALWAYS-VISIBLE HEADER          │ │
            │  │   ──────────────────────         │ │
            │  │   work_type · year label         │ │
            │  │   <h1> title                     │ │
            │  │   subtitle · original_script     │ │
            │  │   · translit                     │ │
            │  │   byline (author chips)          │ │
            │  │   publisher · place · year       │ │
            │  │   pages note                     │ │
            │  │                                  │ │
            │  │   ┌──── if fm.pdf_url ────────┐ │ │
            │  │   │  TAB NAV                   │ │ │
            │  │   │  [Summary] [Read PDF · N] │ │ │
            │  │   ├────────────────────────────┤ │ │
            │  │   │  Tab panel #summary        │ │ │
            │  │   │    • <Content/> (md body) │ │ │
            │  │   │    • Pull quotes           │ │ │
            │  │   │                            │ │ │
            │  │   │  Tab panel #read           │ │ │
            │  │   │    • <iframe src={pdf}>   │ │ │
            │  │   │      (lazy-injected)       │ │ │
            │  │   │    • "Open in new tab ↗"  │ │ │
            │  │   └────────────────────────────┘ │ │
            │  │                                  │ │
            │  │   └──── else (no pdf_url) ─┐    │ │
            │  │     <Content/> (md body)   │    │ │
            │  │     Pull quotes            │    │ │
            │  │   ────────────────────────┘    │ │
            │  │                                  │ │
            │  │   ALWAYS-VISIBLE FOOTER          │ │
            │  │   ──────────────────────         │ │
            │  │   Themes chips                   │ │
            │  │   Tier-B disclaimer              │ │
            │  │   <PeopleInPiece/>               │ │
            │  │   <RelatedSection/>              │ │
            │  └──────────────────────────────────┘ │
            └───────────────────────────────────────┘
                            │
                            ▼
            <script> (vanilla JS, bottom of component)
              • Read window.location.hash on load
              • Activate matching tab
              • Wire tab click + keyboard (← →) handlers
              • Lazy-inject iframe on first Read PDF activation
              • Sync hash to URL on switch (history.replaceState)
```

## 5. Components in detail

### 5.1 `PrimaryWorkDetail.astro` — restructure

**Above the tabs (always visible):** unchanged from today. The existing `<header>` block stays as-is *except* the inline "Read PDF" button is removed — its function is now the second tab. The work_type label, title, subtitle, original-script title, translit title, byline, publisher/place/year line, and pages note all remain.

**New frontmatter-derived variable** to add to the component's TypeScript block (top of file, alongside `pagesNote`):

```ts
// Bare integer for the tab label suffix. Distinct from `pagesNote` (a
// formatted "N pages" string used by the existing badge under the header).
const pageCount: number | null = fm.physical?.pages_total ?? fm.physical?.page_count ?? null;
```

**Tab control:** rendered only when `fm.pdf_url` is set. Markup follows the WAI-ARIA tabs pattern:

```html
<div class="tab-nav" role="tablist" aria-label="Reading modes">
  <button role="tab" id="tab-summary" aria-controls="panel-summary" aria-selected="true" tabindex="0">
    Summary
  </button>
  <button role="tab" id="tab-read" aria-controls="panel-read" aria-selected="false" tabindex="-1">
    {pageCount ? `Read full PDF · ${pageCount} pages` : "Read full PDF"}
  </button>
</div>

<div role="tabpanel" id="panel-summary" aria-labelledby="tab-summary">
  <!-- AI summary body + pull quotes -->
</div>

<div role="tabpanel" id="panel-read" aria-labelledby="tab-read" hidden>
  <!-- iframe injected lazily on first activation -->
  <div data-pdf-mount data-pdf-url={fm.pdf_url}></div>
  <p class="mt-3 text-sm">
    <a href={fm.pdf_url} target="_blank" rel="noopener">Open in new tab ↗</a>
  </p>
</div>
```

When `pageCount` is `null`, the tab label degrades to "Read full PDF" (no suffix).

**Tab content — Summary panel:**
- `<Content />` (the rendered MDX body — same as today)
- Pull quotes section (same as today)
- Existing prose-container Tailwind class block reused verbatim

**Tab content — Read PDF panel:**
- `<div data-pdf-mount data-pdf-url={fm.pdf_url}>` placeholder. The JS injects `<iframe src={pdf_url} title="{title}" style="width:100%; height:80vh; border:0">` into this div on first tab activation. Once injected, the iframe stays in the DOM.
- "Open in new tab ↗" link below, always rendered (even before lazy injection).

**Below the tabs (always visible):** Themes chips, Tier-B disclaimer, `<PeopleInPiece />`, `<RelatedSection />` — identical structure to today, with one wording tweak in the disclaimer:

> Old: "The original work is available via the **PDF link above**…"
> New: "The original work is available via the **Read PDF tab above** (where present)…"

The "(where present)" hedge covers the no-`pdf_url` case (current language is already inaccurate when `pdf_url` is unset — a known bug listed in §10 follow-ups). The Tier-B disclaimer follow-up will revisit the wording for the no-PDF case more thoroughly.

**When `fm.pdf_url` is unset:** the existing single-column layout renders as today — no tab nav, no panel divs, no JS island. The component's `if (fm.pdf_url)` branch is the only gate.

### 5.2 Tab-control JavaScript (inline `<script>` block)

```javascript
const tablist = document.querySelector('[role="tablist"]');
if (tablist) {
  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  const panels = tabs.map(t => document.getElementById(t.getAttribute('aria-controls')));

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
        iframe.setAttribute('loading', 'lazy');
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
  // Do NOT focus the tab on hash-init — a deep-linked visitor expects to
  // start reading, not to have a tab control under their cursor.
  const initial = window.location.hash === '#read' ? 1 : 0;
  if (initial !== 0) {
    activate(initial, { syncHash: false, focusTab: false });
  }
}
```

The script is small (~40 LOC), inline at the bottom of `PrimaryWorkDetail.astro`, and runs once per page. It is a no-op when no tab control is present (single-column layout for no-PDF works).

### 5.3 Styling

Tab nav uses the existing design tokens (`--color-saffron-700` for active accent, `--color-border` for the underline, `--font-ui` for tab labels). **Both tab buttons share identical Tailwind classes** — the active state is driven entirely by the `aria-selected:` variant. Full sketch:

```html
<div class="border-b border-(--color-border) mb-8 flex font-(family-name:--font-ui)">
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
```

Match the existing site rhythm: same baseline grid, same spacing scale. No new design tokens.

## 6. Data flow

```
Astro build (cold)
─────────────────
  CollectionEntry<"primary-works">
       │
       ▼
  PrimaryWorkDetail.astro renders:
       │
       ├─ if fm.pdf_url → tab nav + panel-summary (with content) + panel-read (with empty mount div)
       │     └─ inline <script> attached
       │
       └─ else → single-column layout (today's structure)


Browser runtime (warm)
──────────────────────
  Page loads
       │
       ▼
  <script> runs:
       │
       ├─ window.location.hash === '#read'?
       │     ├─ yes → activate(1) → inject iframe immediately
       │     └─ no  → leave Summary tab active; iframe NOT in DOM
       │
       ▼
  User clicks "Read full PDF · N" tab
       │
       ▼
  activate(1):
       ├─ swap aria-selected, hidden, tabindex on both tabs/panels
       ├─ first time? → inject <iframe src={pdf_url}> into mount div
       ├─ history.replaceState → URL becomes /primary-works/<slug>/#read
       └─ focus the active tab button (no scroll)
       │
       ▼
  Browser begins fetching the PDF; native PDF viewer renders it inline.


Subsequent tab switches
──────────────────────
  User clicks "Summary":
       └─ activate(0) → hides PDF panel; iframe stays in DOM; URL → /#summary
  User clicks "Read full PDF" again:
       └─ activate(1) → shows PDF panel; iframe already loaded; URL → /#read
```

## 7. Failure modes & edge cases

| Case | Behaviour |
|---|---|
| `fm.pdf_url` unset | No tab nav rendered. Single-column layout displays exactly as today. JS is no-op (no tablist → script's outer guard returns). |
| JS disabled in browser | Both panels are present in initial DOM; both render. `hidden` attribute on panel-read causes it to be invisible (semantic hidden = `display:none`). Result: only Summary visible, PDF tab inert (clicking does nothing). The "Open in new tab ↗" link still works as a regular `<a>`. Acceptable graceful degradation. |
| Browser doesn't support iframe-embedded PDFs (rare) | The browser shows its own "PDF not supported" message inside the iframe area. The "Open in new tab ↗" link below is the escape hatch. |
| iOS Safari renders only first page of PDF | Known platform quirk. The "Open in new tab ↗" link is the documented workaround — it opens the PDF in Safari's full-screen PDF viewer. |
| `pdf_url` returns 404 | Browser-native PDF viewer shows its error UI. We do not try to detect this (would require a `fetch` + CORS, which is blocked). The "Open in new tab ↗" link will also 404; user sees a clear browser error. |
| Page count unknown (`physical.pages_total` / `page_count` both null) | Tab label degrades to "Read full PDF" without the "· N pages" suffix. |
| `pdf_url` is set but page count is known via the manifest (not the MD frontmatter) | Out of scope — the matcher's `notes` column was the only place this could be sourced, and it's not in the schema. Spec follow-up: surface scraped page count back into MDs (separate task). |
| Deep-linked `#read` on a no-PDF page | The URL fragment is harmless. No tab control exists, JS short-circuits, the hash is meaningless. |
| User navigates back/forward through tab switches | We use `history.replaceState`, not `pushState`, so browser back/forward jumps to previous **pages**, not previous **tabs**. This is intentional — tab state is incidental UI, not a navigation event. |
| Tab nav on a very narrow viewport (<360px) | Tabs wrap. The `flex` row simply pushes the second tab to a new line if it doesn't fit. Acceptable. |
| `pdf_url` has unusual characters (`&`, `%20`, etc.) | Astro's JSX-style attribute interpolation handles escaping. The browser hands the URL to its PDF viewer; the viewer handles fetch. Already validated in the prior reconciliation work. |
| Pagefind index pollution | The Read PDF panel contains only an `<iframe>` (lazy) and a link. Pagefind indexes the rendered HTML, which initially shows only the empty `<div data-pdf-mount>`. The iframe content (the PDF) is never seen by Pagefind — same as today's "Read PDF" external link. No regressions. |
| RTL languages (none today, but bn/hi/mr/gu use Devanagari/Bengali/Marathi/Gujarati scripts which are LTR) | All current locales are LTR. Tab order is left-to-right. No change. |

## 8. Testing & validation

### 8.1 Build sanity
- `cd apps/site && pnpm build` exits clean.
- `find apps/site/dist -name 'index.html' \| wc -l` equals **1287** (unchanged from current baseline).
- `grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/tabs-build.log` returns **0**.

### 8.2 Rendered-HTML spot checks (against `apps/site/dist/`)
For at least 3 randomly-picked primary-works **with** `pdf_url`:
- `grep -c 'role="tab"' dist/primary-works/<slug>/index.html` == **2** (two tab buttons rendered).
- `grep -c 'role="tabpanel"' dist/primary-works/<slug>/index.html` == **2**.
- `grep -c 'data-pdf-mount' dist/primary-works/<slug>/index.html` == **1**.
- The "Open in new tab ↗" link is present with the correct `pdf_url`.
- The header section (title, byline, publisher line, pages note) renders above the tab nav.
- Themes chips, PeopleInPiece, RelatedSection render below the tab nav.

For at least 3 primary-works **without** `pdf_url`:
- `grep -c 'role="tab"' dist/primary-works/<slug>/index.html` == **0** (no tab nav).
- `grep -c 'role="tabpanel"' dist/primary-works/<slug>/index.html` == **0**.
- Page renders identical structure to a pre-change build (single column).

### 8.3 Browser smoke tests (manual; can be scripted via the `browse` MCP)
- Open `a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980` (verified to have `pdf_url` in the reconciliation manifest).
  - Confirm Summary tab is active by default.
  - Click "Read full PDF" tab → PDF embeds inline.
  - Click "Summary" → PDF panel hides; iframe stays in DOM (verify via DevTools).
  - URL shows `#read` and `#summary` as tabs are switched.
- Open the same slug with `#read` in the URL → PDF tab is active on initial render; iframe is in DOM; focus is NOT trapped in the tab control (deep-linked visitors land in reading flow).
- Open `khoj-november-december-2009` (verified to have no `pdf_url`) → no tab nav; layout matches the current production page.
- Keyboard: focus the first tab via Tab key; press → to move to "Read full PDF"; press ↵ → tab activates.

### 8.4 Accessibility audit
- Use the `accesslint:contrast-checker` skill against the new tab nav. Active vs inactive tab labels must meet WCAG AA contrast against the page background.
- Verify ARIA roles: `tablist`, `tab`, `tabpanel`, `aria-selected`, `aria-controls`, `aria-labelledby` all wired correctly.
- Inactive panels carry the `hidden` attribute (not just CSS `display:none`) so screen readers ignore them.
- Tab keyboard model matches the WAI-ARIA Authoring Practices "Tabs with Automatic Activation" pattern.

### 8.5 Performance check
- Before the user clicks the Read PDF tab, no network request for the PDF should fire. Verify via DevTools Network panel: page load → 0 PDF requests.
- After clicking the tab: exactly 1 PDF request to `indianliberals.in`.
- Lighthouse / Pagespeed: the primary-work detail page's TTI/LCP should not regress (PDF lazy-load is the main perf safeguard).

## 9. Stopping criteria

1. `PrimaryWorkDetail.astro` modified per §5.1.
2. Inline `<script>` block added per §5.2.
3. Tab styling per §5.3 (no new design tokens).
4. All §8.1 / §8.2 / §8.3 checks pass.
5. Build clean, page count 1287, no Zod errors.
6. Three sampled primary-work pages render the tab UI; three sampled no-PDF pages render unchanged.
7. Accessibility audit passes (§8.4).
8. PDF lazy-load verified (§8.5).
9. Pre-push code review signs off.

## 10. Open items / follow-ups (separate specs)

- **UI string translations** — hardcoded English "Summary" / "Read full PDF" labels. Once a site-wide UI-translation pass lands, replace with translated strings.
- **R2-hosted PDFs** — once PDFs migrate to R2 with proper CORS, a follow-up spec can replace the iframe with a custom PDF.js viewer (page-by-page, search, annotation hooks).
- **Page count from scraped inventory** — the matcher knows the scraped PDF size but not its page count; a follow-up could parse the PDF at scrape time and backfill `physical.pages_total` so all tabs show "· N pages".
- **Cross-tab persistence** — remembering "user prefers PDF tab" across sessions. Not justified without usage data.
- **Tier-B disclaimer / no-pdf_url bug** flagged in i18n consolidation review — independent of this work.
- **Inline citation linking** — eventually, summary bullet points could deep-link into specific pages of the PDF. Requires page-level anchors which the prod PDFs don't have. Future R2 + PDF.js work.
