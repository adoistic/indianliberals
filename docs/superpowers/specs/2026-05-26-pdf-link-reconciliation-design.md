# PDF Link Reconciliation — Design Spec

**Author:** Adnan
**Date:** 2026-05-26
**Status:** locked

## 1. Goal

Populate the root-level `pdf_url` field on every primary-works MD that has a corresponding page on the existing production site `https://indianliberals.in`. Today, all 381 primary-works MDs have `pdf_url` empty; the schema and the `<PrimaryWorkDetail>` component already render a "Read PDF" button when the field is set. Filling it from the existing prod site closes a visible gap on the new site without waiting for the future R2-hosted PDF deployment.

The terminal state of this work:

1. A reusable, idempotent scrape of the existing prod site is cached under `data/prod-mirror/` so the matching pass can be re-run offline without re-fetching.
2. A review manifest at `data/pdf-link-manifest.tsv` lists every (MD slug → prod PDF URL) match with a confidence tier.
3. A companion `data/pdf-link-misses.tsv` lists unmatched MDs with their top-3 fuzzy candidates so manual rescues are cheap.
4. After Adnan signs off on the manifest, an applier writes `pdf_url` into the matched MDs in one (or two) commits.
5. The next `pnpm build` renders working "Read PDF" buttons on the populated primary-works pages.

## 2. Non-goals

- **Hosting the PDFs ourselves.** The schema's long-term intent is R2-hosted PDFs (`pdf_staging_path` and `pdf_size_mb` fields exist for this). This spec is the *transitional* state: link to prod for now; replace with R2 URLs in a future spec.
- **Populating the `manifestations[]` schema array** (multi-edition / reprint PDFs). Some prod pages link multiple PDFs; we record the first and surface the rest in the manifest, but writing back to `manifestations[]` is a separate task.
- **Reverse reconciliation** — "works on prod that we lack an MD for." The crawl will incidentally produce this data, but populating new MDs from it is out of scope.
- **Translating prod's PDFs.** Non-English primary-works MDs (e.g. gu Khoj) link to the same prod URL if a prod page exists; no separate translated PDFs exist on prod today.
- **Validating that each PDF URL is still live** at apply time. The applier writes URLs from the cached scrape; link-rot is a separate concern.

## 3. Scope

- **Three Python scripts** under `scripts/synthesis/`:
  - `scrape_prod.py` (one-time, idempotent crawl of indianliberals.in periodical categories)
  - `match_pdfs.py` (offline matcher over cached HTML + 381 MDs → manifest + misses)
  - `apply_pdf_urls.py` (writes `pdf_url` into MDs from the approved manifest, with `--dry-run` and `--force` flags)
- **Two artifact files** under `data/` (TSV review surfaces for Adnan).
- **Cache directory** `data/prod-mirror/` with per-page HTML + a JSONL inventory.
- **Unit tests** under `scripts/synthesis/tests/` (or wherever the existing pytest convention lands) for the title normalizer and matcher tiers.
- **One MD-touching commit** (probably 1–2 commits including a manual-overrides pass).

## 4. Architecture

```
                  https://indianliberals.in (HTTP)
                            │
                            ▼
            ┌──────────── scrape_prod.py ──────────────┐
            │  - Seed periodicals: forum-of-free-      │
            │    enterprise, freedom-first, the-       │
            │    indian-libertarian, swatantra-party,  │
            │    + regional bn/gu/hi/mr sections       │
            │  - 1 req/sec, retry 5xx, polite UA       │
            │  - Idempotent via on-disk cache          │
            └──────────────────────────────────────────┘
                            │
                            ▼
   data/prod-mirror/
     <periodical>/<slug>.html        ← cached page HTML
     inventory.jsonl                 ← {prod_slug, periodical,
                                        pdf_url, page_title,
                                        byline_text, year_string,
                                        source_url}
                            │
                            ▼
            ┌──────────── match_pdfs.py ───────────────┐
            │  Reads inventory.jsonl +                 │
            │  apps/site/src/content/primary-works/    │
            │   *.md (381)                             │
            │                                          │
            │  Tier 1 (exact):  md.slug == prod_slug   │
            │  Tier 2 (high):   title fuzzy ≥92 AND    │
            │                   year matches           │
            │  Tier 3 (medium): title fuzzy ≥80 AND    │
            │                   year AND author        │
            │                   lastname appears in    │
            │                   prod byline            │
            │  page-only:       slug matches but page  │
            │                   has no <a *.pdf>       │
            └──────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
   data/pdf-link-manifest.tsv  data/pdf-link-misses.tsv
   (matches, sorted by         (unmatched MDs + top-3
    confidence desc)            fuzzy candidates each)
                            │
                ── HUMAN REVIEW (Adnan eyeballs) ──
                            │
                            ▼
            ┌──────────── apply_pdf_urls.py ───────────┐
            │  Reads (post-review) manifest.tsv        │
            │  Writes pdf_url: <url> into each MD's    │
            │   root frontmatter (insert after         │
            │   provenance: block, preserve            │
            │   formatting via ruamel.yaml)            │
            │  --dry-run prints unified diff           │
            │  --only-confidence flag for tier         │
            │   selection                              │
            │  --force overrides existing pdf_url      │
            │   (defensive; not needed today)          │
            │  Stages and commits in one shot          │
            └──────────────────────────────────────────┘
                            │
                            ▼
     apps/site/src/content/primary-works/*.md  ← pdf_url populated
     git commit: "data(primary-works): populate pdf_url
                  from prod indianliberals.in (N=...)"
                            │
                            ▼
                pnpm build → "Read PDF" buttons render
                              on populated primary-works pages
```

## 5. Components in detail

### 5.1 `scripts/synthesis/scrape_prod.py`

**Purpose:** Build a complete, cached mirror of every `/content/<slug>/` detail page on `indianliberals.in`, along with each page's PDF link if present.

**Seed periodicals** (hardcoded; small and stable):

```
/periodicals/forum-of-free-enterprise/
/periodicals/freedom-first/
/periodicals/the-indian-libertarian/
/periodicals/swatantra-party/
/regional-literature/bengali/
/regional-literature/gujarati/
/regional-literature/hindi/
/regional-literature/marathi/
```

The crawler additionally walks any `/periodicals/<x>/` links it finds during the first pass and adds new seeds incrementally (in case the list above is incomplete).

**Per category:** fetch the category page, paginate via `?page=N` (or whatever WP convention prod uses — discovered during smoke test), collect every `/content/<slug>/` URL into a per-category set.

**Per detail page:**
- Skip if `data/prod-mirror/<periodical>/<slug>.html` already exists (cache hit) — unless `--refresh` is passed.
- Fetch with `User-Agent: indianliberals-pdf-reconciliation-bot (Adnan, Thothica)`.
- Save raw HTML to cache.
- Parse with `beautifulsoup4`:
  - PDF link: first `<a href>` whose href ends in `.pdf` (case-insensitive). Normalize via `urljoin` to absolute. Strip session/tracking query params; preserve content-addressing ones.
  - Page title: `<h1>` or `<title>` content.
  - Byline text: visible text near the byline (best-effort; used downstream by the matcher's Tier-3 author check).
  - Year string: regex `\b(19|20)\d{2}\b` against page title + byline (first match).
- Append one JSONL row to `data/prod-mirror/inventory.jsonl`:
  ```json
  {"prod_slug": "...", "periodical": "...", "pdf_url": "https://...", "page_title": "...", "byline_text": "...", "year_string": "1980", "source_url": "https://indianliberals.in/content/..."}
  ```
- If no PDF link found: same row but `"pdf_url": null`.

**Rate limit + retries:** 1 req/sec default (overridable via `--rps`). 3 retries with 1s/2s/4s backoff on HTTP 5xx. Hard fail (log + skip) on 4xx other than 404. 404 is recorded as a "stub" inventory row.

**robots.txt:** fetched once at start. If the bot's UA is disallowed, halt with a clear error message — Adnan decides whether to override (`--ignore-robots`).

**Output summary line** at end:
```
scrape_prod: 487 pages cached, 412 with PDFs, 73 without, 2 errors.
inventory.jsonl: 485 rows.
```

### 5.2 `scripts/synthesis/match_pdfs.py`

**Purpose:** Join the prod inventory with the local primary-works MDs and assign each MD a confidence tier.

**Input:**
- `data/prod-mirror/inventory.jsonl` (N rows)
- `apps/site/src/content/primary-works/*.md` (381 MDs)

**Per MD, walk three tiers and stop at first hit:**

| Tier | Confidence | Rule |
|---|---|---|
| 1 | `exact` | `md.id == prod_slug` |
| 2 | `high` | `rapidfuzz.token_set_ratio(normalize(md.title.main), normalize(prod.page_title)) ≥ 92` AND `md.publication.year` appears in `prod.year_string` |
| 3 | `medium` | `≥ 80` title similarity AND year match AND lastname of `md.authors[0]` appears in `prod.byline_text` (case-insensitive) |
| — | `page-only` | Tier 1 slug matches but `prod.pdf_url is null` |
| — | (no row) | None of the above; MD goes to `misses.tsv` |

**Title normalization** (`normalize()`):
- Lowercase.
- Strip diacritics via `unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")`.
- Drop leading articles `the |a |an `.
- Strip punctuation (`string.punctuation` minus hyphens).
- Collapse internal whitespace to a single space.

**Output `data/pdf-link-manifest.tsv`:**
```
md_slug	confidence	prod_slug	pdf_url	md_title	prod_title	notes
```
Sorted by (confidence desc using priority `exact > high > medium > page-only`, then md_slug asc).

**Output `data/pdf-link-misses.tsv`:**
```
md_slug	md_title	md_year	md_first_author	top1_prod_slug	top1_score	top2_prod_slug	top2_score	top3_prod_slug	top3_score
```
One row per unmatched MD. The `top1..top3` columns help Adnan paste an override URL by hand if a candidate is obviously right but the tier-2/3 rules didn't fire.

**Edge cases handled inline:**
- Multiple MDs targeting one `prod_slug` → emit a `DUPLICATE` row instead of any match; flag both MDs in the manifest's `notes`.
- Multiple `<a *.pdf>` on a single prod page → first wins; the rest land in the `notes` column for manual review (and a follow-up task to populate `manifestations[]`).

**Output summary line:**
```
match_pdfs: 312 exact, 18 high, 7 medium, 9 page-only, 35 misses (381 total).
manifest.tsv: 346 rows. misses.tsv: 35 rows.
```

### 5.3 `scripts/synthesis/apply_pdf_urls.py`

**Purpose:** Mutate frontmatter of matched MDs to add `pdf_url: <url>`.

**Input:** `data/pdf-link-manifest.tsv` (post-review). Optionally `data/manual-overrides.tsv` in a second pass (same columns; treated as `exact` confidence regardless of what's written).

**Per matched row:**
- Open `apps/site/src/content/primary-works/<md_slug>.md`.
- Parse frontmatter with `ruamel.yaml` round-tripper (so quote styles and key order are preserved).
- If `pdf_url` is already set and non-empty: skip with warning unless `--force`.
- Otherwise: insert `pdf_url: <url>` immediately after the `provenance:` block (or after `physical:` if `provenance:` is absent — survey first).
- Write back the file.

**Flags:**
- `--dry-run` — print a unified diff per MD, no writes.
- `--only-confidence exact,high` — apply only the listed tiers (default: `exact,high,medium`; `page-only` and `none` never auto-applied).
- `--force` — overwrite existing non-empty `pdf_url`.
- `--manifest <path>` — alternate manifest (default `data/pdf-link-manifest.tsv`).

**Final action:** stages the touched MDs and commits with a message naming the count:
```
data(primary-works): populate pdf_url from prod indianliberals.in (N=312)

Tier breakdown: 290 exact, 16 high, 6 medium.
Source: data/prod-mirror (scraped 2026-05-26).
9 page-only matches (slug found but no PDF on page) and 35 misses
left for manual review via data/pdf-link-misses.tsv.

Transitional; will be replaced by R2-hosted URLs in a future spec
per the pdf_staging_path / pdf_size_mb schema fields.
```

## 6. Data flow

```
prod indianliberals.in           data/prod-mirror/             review surfaces
─────────────────────            ──────────────────             ──────────────────
   GET category pages      ───►  *.html (cached)
   GET detail pages        ───►  *.html (cached)        ───►   inventory.jsonl
                                                                   │
                                                                   ▼
   apps/site/src/content/primary-works/*.md  ◄──────  match_pdfs.py
                                                                   │
                                              ┌────────────────────┴──┐
                                              ▼                       ▼
                                  pdf-link-manifest.tsv      pdf-link-misses.tsv
                                              │                       │
                                              │              (manual rescues
                                              │               → manual-overrides.tsv)
                                              │                       │
                                              ▼                       ▼
                                  apply_pdf_urls.py  ◄────────────────┘
                                              │
                                              ▼
                                  apps/site/src/content/primary-works/*.md
                                  (pdf_url populated)
                                              │
                                              ▼
                                       git commit
```

## 7. Failure modes & edge cases

| Case | Behavior |
|---|---|
| Network 5xx / timeout | Retry 3x with exponential backoff (1s/2s/4s). Persistent fail → log and continue; cache means re-running picks up. |
| Detail page exists, no `<a *.pdf>` | Record with `pdf_url: null`. Matcher emits `confidence: page-only` so the "page found, no PDF" case is distinct from "no match at all". |
| Multiple PDF links per page (translations, multi-volume) | First wins as the primary `pdf_url`; remainder land in `notes` column of manifest. Out of scope to populate `manifestations[]` automatically. |
| Relative PDF URLs (`/forum-of-free-enterprise/x.pdf`) | Normalized via `urljoin(base, href)` to absolute. Strip tracking query params. |
| MD has no `publication.year` | Tier 2/3 skip (require year). Tier 1 still works. Logged into misses regardless. |
| Two MDs map to same `prod_slug` | Matcher refuses to emit; logs `DUPLICATE` row with both MD slugs. Manual resolution. |
| MD already has `pdf_url` (defensive — not the case for any of 381 today) | Applier skips with warning. `--force` overrides. |
| `rights.status: takedown_on_request` | Don't filter. Populate the URL. If prod takes it down, prod 404s and the link breaks visibly. |
| `robots.txt` disallows scraping | Crawler halts at start with clear error. Override with `--ignore-robots`. |
| Slug matches but cached page has no PDF | The `page-only` tier above. Manual review may yield a URL by hand; otherwise accept the gap. |
| Prod paginated category page format unknown until smoke | Smoke test (Section 8.2.1) resolves before full crawl. |

## 8. Testing & validation

### 8.1 Unit tests (`pytest`)

- `test_normalize_title.py` — title normalization:
  - `"The Constitution of India"` → `"constitution of india"`
  - `"भारत की समस्याएँ — A Study"` → `"bhrt ki smsye  a study"` (diacritics stripped, hyphens preserved as separators)
  - `"  Trade   Policy  "` → `"trade policy"` (whitespace collapsed)
- `test_match_tiers.py` — 6 synthetic (md, prod_inventory) fixtures, one per tier hit + one per relevant tier miss; asserts the right confidence label.
- `test_apply_yaml.py` — round-trip a sample frontmatter through the applier; assert `pdf_url:` is inserted in the expected position and other fields are byte-preserved (no spurious quote-style or key-order changes from the YAML library).

### 8.2 Smoke tests (manual)

1. **Crawler partial run:** `scrape_prod.py --seed freedom-first --limit 5` — fetch 5 detail pages, eyeball `inventory.jsonl` rows, confirm cache dir populated.
2. **Matcher dry run:** `match_pdfs.py` against the 5-page inventory + all 381 MDs — should find 0-3 tier-1 hits in the freedom-first sample; eyeball that they look right.
3. **Applier dry run:** `apply_pdf_urls.py --dry-run --only-confidence exact` — review the diff for 3 random MDs; confirm one-line `pdf_url:` addition and no other frontmatter mutation.

### 8.3 Integration check (after full apply)

- `cd apps/site && pnpm build` — Zod schema validates every `pdf_url` (`.url()` enforcement); a malformed URL would fail the build.
- Spot-check 5 rendered primary-work pages — confirm the "Read PDF" button appears and points to the populated URL.
- Visit 3 of those URLs in a browser to verify the PDFs still load on prod.

### 8.4 Coverage target

≥ 80 % of 381 MDs matched at `exact` or `high` confidence in the first run. Below that → iterate on title normalization before manual triage on `medium` / misses.

## 9. Stopping criteria

- All `exact` and `high` rows applied via `apply_pdf_urls.py` (single commit).
- `medium` rows manually reviewed; applied selectively (in the same commit or a follow-up).
- `misses.tsv` reviewed; obvious manual matches pasted into `data/manual-overrides.tsv` and applied in a second pass.
- Final commit count: 1–2.
- `pnpm build` clean, page count unchanged from current baseline (1287).

## 10. Open items / follow-ups (separate specs)

- **Populate `manifestations[]`** for primary-works with multi-edition PDFs (the manifest's `notes` column flags candidates).
- **Migrate PDFs to R2** per the schema's stated long-term intent (`pdf_staging_path` → R2 → replace `pdf_url`).
- **Reverse reconciliation** — surface prod pages we lack an MD for.
- **Link-rot monitoring** — periodic check that populated `pdf_url`s still resolve.
- **Per-language PDFs** — translated primary-works MDs (gu/hi/mr/bn) currently share the English prod URL; a future spec may add language-keyed PDF hosting.
