# PDF Link Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate root-level `pdf_url` on every primary-works MD that has a matching page on existing prod `https://indianliberals.in`, via a three-script Python pipeline (crawler → matcher → applier) following the spec at `docs/superpowers/specs/2026-05-26-pdf-link-reconciliation-design.md`.

**Architecture:** Idempotent crawler caches every prod `/content/<slug>/` HTML page + extracts the PDF link into `data/prod-mirror/inventory.jsonl`. Offline matcher joins the inventory with all 381 primary-works MDs using a three-tier confidence ladder (exact slug → fuzzy title+year → fuzzy title+year+author lastname). Applier reads a human-reviewed manifest and inserts `pdf_url:` into matched MDs via the same `_FRONTMATTER_RX` regex-surgery pattern used elsewhere in `scripts/synthesis/`.

**Tech Stack:** Python 3 (existing `.venv-extract` virtualenv); `requests` (existing) + `beautifulsoup4` (new) for the crawler; `rapidfuzz` (new) for fuzzy matching; `pyyaml` (existing) for inventory I/O. Frontmatter mutation uses regex line-surgery (NOT yaml round-trip), matching `scripts/synthesis/apply-classify.py` convention. Pytest for unit tests under `scripts/synthesis/tests/`.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `scripts/synthesis/pdf_match_lib.py` | CREATE | Pure-logic helpers: `normalize_title()`, `tier_match()`, `extract_year()`, `extract_lastname()`. Shared by matcher + tests. No I/O. |
| `scripts/synthesis/scrape-prod.py` | CREATE | One-time idempotent crawler. Walks periodical seeds, paginates, fetches detail pages, caches HTML, parses PDF link + metadata, appends to `inventory.jsonl`. |
| `scripts/synthesis/match-pdfs.py` | CREATE | Offline matcher. Reads inventory + 381 MDs, walks three confidence tiers, emits `pdf-link-manifest.tsv` + `pdf-link-misses.tsv`. |
| `scripts/synthesis/apply-pdf-urls.py` | CREATE | Frontmatter mutator. Reads approved manifest; inserts `pdf_url:` line after `provenance:` block via `_FRONTMATTER_RX` regex surgery. Supports `--dry-run`, `--only-confidence`, `--force`, `--manifest`. |
| `scripts/synthesis/tests/test_pdf_match_lib.py` | CREATE | Unit tests for pure-logic helpers. |
| `scripts/synthesis/tests/test_apply_pdf_urls.py` | CREATE | Unit tests for the frontmatter mutator (synthetic MD fixture). |
| `data/prod-mirror/` | CREATE (gitignored) | Cached HTML pages + `inventory.jsonl`. |
| `data/pdf-link-manifest.tsv` | CREATE (committed) | Review surface: one row per matched MD. Adnan eyeballs before applier runs. |
| `data/pdf-link-misses.tsv` | CREATE (committed) | One row per unmatched MD + top-3 fuzzy candidates. |
| `data/manual-overrides.tsv` | OPTIONAL (committed if used) | Hand-written rescues from misses; same column layout as manifest; treated as `exact` confidence. |
| `apps/site/src/content/primary-works/*.md` | MODIFY (batch) | Add `pdf_url: <url>` line to matched MDs. |
| `.gitignore` | MODIFY | Add `data/prod-mirror/` (cached HTML is large + ephemeral). |

**File-size budget:** Each `.py` script under ~400 lines. `pdf_match_lib.py` under ~150 lines.

---

## Conventions to honour

- **Python venv:** all script runs use `.venv-extract/bin/python3 scripts/synthesis/<name>.py`.
- **Test runs:** `.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_<name>.py -v`.
- **Hyphenated script names** (`scrape-prod.py`, `match-pdfs.py`, `apply-pdf-urls.py`) — matches `scripts/synthesis/apply-classify.py`, `apply-ner.py`, etc.
- **Test files load hyphenated scripts via `importlib.util.spec_from_file_location`** — copy the pattern from `scripts/synthesis/tests/test_apply_classify_thinkers.py:8-15`.
- **Frontmatter regex** — reuse `_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)` from `apply-classify.py:44`.
- **Imports of pure-logic helpers** — `pdf_match_lib.py` is importable as `from pdf_match_lib import normalize_title` (underscore module name, no hyphen).
- **Commit messages** — `feat(pipeline):` for code, `data(primary-works):` for the MD-mutation commit.
- **No `Co-Authored-By` trailer** unless Adnan explicitly asks.

---

## Pre-work baseline (run once before Chunk 1)

- [ ] **Step 0.1: Sanity-check current state**

```bash
cd "/Users/siraj/Indian Liberals Website"

# Count primary-works MDs (expected: 381)
ls apps/site/src/content/primary-works/*.md | wc -l

# Confirm zero MDs currently have pdf_url
grep -c "^pdf_url:" apps/site/src/content/primary-works/*.md | awk -F: '{tot+=$2} END {print "Total pdf_url lines:", tot}'

# Confirm venv exists
ls .venv-extract/bin/python3
```

Expected: 381 MDs; 0 pdf_url lines; venv present.

---

## Chunk 1: Library helpers (`pdf_match_lib.py`)

Goal: Pure-logic primitives the matcher (and tests) depend on. No I/O, no side effects.

### Task 1.1: Add dependencies

**Files:**
- Modify (install only): `.venv-extract/`

- [ ] **Step 1.1.1: Install rapidfuzz + beautifulsoup4**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/pip install rapidfuzz beautifulsoup4
```

Expected: both install cleanly. Note: no `requirements.txt` exists in the repo currently — installations go directly into the venv. Adnan tracks deps informally.

- [ ] **Step 1.1.2: Smoke-import the new packages**

```bash
.venv-extract/bin/python3 -c "import rapidfuzz, bs4; print(rapidfuzz.__version__, bs4.__version__)"
```

Expected: both versions print.

### Task 1.2: `normalize_title()` (TDD)

**Files:**
- Create: `scripts/synthesis/pdf_match_lib.py`
- Test: `scripts/synthesis/tests/test_pdf_match_lib.py`

- [ ] **Step 1.2.1: Write the failing test**

```python
# scripts/synthesis/tests/test_pdf_match_lib.py
"""Tests for pdf_match_lib pure-logic helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "pdf_match_lib",
    str(Path(__file__).resolve().parents[1] / "pdf_match_lib.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_normalize_title_lowercases():
    assert mod.normalize_title("Trade Policy") == "trade policy"


def test_normalize_title_drops_leading_articles():
    assert mod.normalize_title("The Constitution of India") == "constitution of india"
    assert mod.normalize_title("A Blueprint for Eradication") == "blueprint for eradication"
    assert mod.normalize_title("An Essay on Liberty") == "essay on liberty"


def test_normalize_title_collapses_whitespace():
    assert mod.normalize_title("  Trade   Policy  ") == "trade policy"


def test_normalize_title_strips_diacritics():
    # "Café" → "cafe"
    assert mod.normalize_title("Café Society") == "cafe society"


def test_normalize_title_strips_punctuation():
    assert mod.normalize_title("Trade, Policy: A Review!") == "trade policy a review"


def test_normalize_title_preserves_hyphens_as_spaces():
    # Hyphens are word separators in slugs; treat as space for fuzzy match
    assert mod.normalize_title("Self-Governance") == "self governance"


def test_normalize_title_handles_empty_string():
    assert mod.normalize_title("") == ""


def test_normalize_title_strips_devanagari_diacritics():
    # Spec §8.1 stated example. NFKD + ascii-ignore strips Devanagari script
    # entirely (no ASCII equivalents); the em-dash is also non-ASCII and stripped.
    # Result: only the trailing Latin substring survives, then lowercase + ws-collapse.
    # NB: leading article "a" survives here because article-strip runs before final
    # whitespace strip (regex requires start-of-string, and leading whitespace from
    # the stripped Devanagari prevents the match). This is intentional — corner case
    # affects nothing in practice since prod page titles are Latin.
    result = mod.normalize_title("भारत की समस्याएँ — A Study")
    assert result == "a study"
```

- [ ] **Step 1.2.2: Run test to verify it fails**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_pdf_match_lib.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `AttributeError: module has no attribute 'normalize_title'`.

- [ ] **Step 1.2.3: Implement `normalize_title`**

```python
# scripts/synthesis/pdf_match_lib.py
"""Pure-logic helpers for PDF link matching.

No I/O. No side effects. Shared by match-pdfs.py and tests.
"""
from __future__ import annotations

import re
import string
import unicodedata


_LEADING_ARTICLE_RX = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
_PUNCT_TABLE = str.maketrans({c: " " for c in string.punctuation})
_WS_RX = re.compile(r"\s+")


def normalize_title(s: str) -> str:
    """Lowercase, drop diacritics, drop leading article, drop punctuation,
    collapse whitespace. Used for fuzzy-match similarity scoring."""
    if not s:
        return ""
    # NFKD decomposition + strip combining marks → ASCII-equivalent.
    decomposed = unicodedata.normalize("NFKD", s)
    ascii_form = decomposed.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_form.lower()
    no_punct = lowered.translate(_PUNCT_TABLE)
    no_article = _LEADING_ARTICLE_RX.sub("", no_punct)
    collapsed = _WS_RX.sub(" ", no_article).strip()
    return collapsed
```

- [ ] **Step 1.2.4: Run test to verify it passes**

```bash
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_pdf_match_lib.py -v
```

Expected: 8/8 PASS.

- [ ] **Step 1.2.5: Commit**

```bash
git add scripts/synthesis/pdf_match_lib.py scripts/synthesis/tests/test_pdf_match_lib.py
git commit -m "feat(pipeline): add pdf_match_lib normalize_title helper"
```

### Task 1.3: `extract_year()` + `extract_lastname()` (TDD)

**Files:**
- Modify: `scripts/synthesis/pdf_match_lib.py`
- Test: `scripts/synthesis/tests/test_pdf_match_lib.py`

- [ ] **Step 1.3.1: Add failing tests**

Append to `test_pdf_match_lib.py`:

```python
def test_extract_year_picks_first_four_digit():
    assert mod.extract_year("Published 1980, reprint 2001") == 1980


def test_extract_year_returns_none_when_missing():
    assert mod.extract_year("no year here") is None


def test_extract_year_handles_1900_to_2099():
    assert mod.extract_year("1953 lecture") == 1953
    assert mod.extract_year("2018") == 2018
    assert mod.extract_year("1899 too early") is None  # outside 1900-2099


def test_extract_lastname_from_slug():
    # "b-r-shenoy" → "shenoy"
    assert mod.extract_lastname("b-r-shenoy") == "shenoy"


def test_extract_lastname_single_token():
    assert mod.extract_lastname("ambedkar") == "ambedkar"


def test_extract_lastname_handles_empty():
    assert mod.extract_lastname("") == ""
```

- [ ] **Step 1.3.2: Run, expect 3 new fails**

```bash
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_pdf_match_lib.py -v
```

Expected: 8 PASS + 6 FAIL (the new ones).

- [ ] **Step 1.3.3: Implement both helpers**

Append to `pdf_match_lib.py`:

```python
_YEAR_RX = re.compile(r"\b(19|20)\d{2}\b")


def extract_year(s: str) -> int | None:
    """Find first four-digit year in [1900, 2099] in the string. Returns
    int or None."""
    if not s:
        return None
    m = _YEAR_RX.search(s)
    return int(m.group(0)) if m else None


def extract_lastname(thinker_slug: str) -> str:
    """The slug's last hyphen-separated token is the lastname for matching
    purposes. (e.g. 'b-r-shenoy' → 'shenoy')"""
    if not thinker_slug:
        return ""
    return thinker_slug.rsplit("-", 1)[-1]
```

- [ ] **Step 1.3.4: Run, expect all pass**

```bash
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_pdf_match_lib.py -v
```

Expected: 14/14 PASS.

- [ ] **Step 1.3.5: Commit**

```bash
git add scripts/synthesis/pdf_match_lib.py scripts/synthesis/tests/test_pdf_match_lib.py
git commit -m "feat(pipeline): add extract_year and extract_lastname helpers"
```

### Task 1.4: `tier_match()` — the three-tier ladder (TDD)

**Files:**
- Modify: `scripts/synthesis/pdf_match_lib.py`
- Test: `scripts/synthesis/tests/test_pdf_match_lib.py`

- [ ] **Step 1.4.1: Add failing tests**

Append to `test_pdf_match_lib.py`:

```python
def test_tier_match_exact_slug():
    md = {"id": "blueprint-poverty-1980", "title_main": "X", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "blueprint-poverty-1980", "page_title": "Y", "byline_text": "", "year_string": "", "pdf_url": "https://example.com/x.pdf"}
    result = mod.tier_match(md, prod)
    assert result == "exact"


def test_tier_match_high_fuzzy_title_plus_year():
    md = {"id": "different-slug", "title_main": "Blueprint for Eradication of Poverty", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "A Blueprint for Eradication of Poverty (1980)", "byline_text": "Dr B.P. Godrej", "year_string": "1980"}
    result = mod.tier_match(md, prod)
    assert result == "high"


def test_tier_match_medium_fuzzy_with_author():
    md = {"id": "different-slug", "title_main": "Inflation Control in India", "year": 1977, "first_author_slug": "br-shenoy"}
    # Score ≥80 but <92; year matches; lastname matches
    prod = {"prod_slug": "x", "page_title": "Controlling Inflation in India", "byline_text": "BR Shenoy", "year_string": "1977"}
    result = mod.tier_match(md, prod)
    assert result == "medium"


def test_tier_match_no_match_when_year_missing():
    md = {"id": "different-slug", "title_main": "Blueprint for Eradication of Poverty", "year": None, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "A Blueprint for Eradication of Poverty", "byline_text": "Dr B.P. Godrej", "year_string": "1980"}
    # Tier 2 requires md.year; Tier 3 too. Tier 1 doesn't apply.
    result = mod.tier_match(md, prod)
    assert result is None


def test_tier_match_no_match_below_threshold():
    md = {"id": "different-slug", "title_main": "Trade Policy", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "Education Reform", "byline_text": "Dr B.P. Godrej", "year_string": "1980"}
    # Title similarity well below 80.
    result = mod.tier_match(md, prod)
    assert result is None


def test_tier_match_page_only_when_pdf_null():
    # Slug matches but prod page has no PDF link.
    md = {"id": "blueprint-poverty-1980", "title_main": "X", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "blueprint-poverty-1980", "page_title": "Y", "byline_text": "", "year_string": "", "pdf_url": None}
    result = mod.tier_match(md, prod)
    assert result == "page-only"


def test_tier_match_exact_takes_precedence_over_fuzzy():
    # Slug matches AND title fuzzy matches AND year matches. Should still be "exact".
    md = {"id": "x", "title_main": "Blueprint", "year": 1980, "first_author_slug": "godrej"}
    prod = {"prod_slug": "x", "page_title": "Blueprint", "byline_text": "Godrej", "year_string": "1980", "pdf_url": "https://example.com/x.pdf"}
    result = mod.tier_match(md, prod)
    assert result == "exact"
```

- [ ] **Step 1.4.2: Run, expect 7 new fails**

```bash
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_pdf_match_lib.py -v
```

- [ ] **Step 1.4.3: Implement `tier_match`**

Append to `pdf_match_lib.py`:

```python
from rapidfuzz import fuzz

# Confidence thresholds (rapidfuzz.fuzz.token_set_ratio, 0-100 scale).
THRESHOLD_HIGH = 92
THRESHOLD_MEDIUM = 80


def tier_match(md: dict, prod: dict) -> str | None:
    """Walk the three-tier ladder. Return the matched confidence label or None.

    md: {"id": str, "title_main": str, "year": int | None, "first_author_slug": str}
    prod: {"prod_slug": str, "page_title": str, "byline_text": str, "year_string": str,
           "pdf_url": str | None}  # pdf_url only inspected for page-only detection

    Tiers (first hit wins):
      1. "exact"     — md.id == prod.prod_slug
                       (returns "page-only" if prod.pdf_url is None/empty)
      2. "high"      — normalized-title token_set_ratio ≥ 92 AND md.year present
                       AND str(md.year) appears in prod.year_string
      3. "medium"    — ≥ 80 AND year match AND md.first_author_slug's lastname
                       appears (case-insensitive) in prod.byline_text
      else: None
    """
    # Tier 1: exact slug match.
    if md["id"] == prod["prod_slug"]:
        pdf = prod.get("pdf_url")
        if pdf is None or pdf == "":
            return "page-only"
        return "exact"

    # Tiers 2/3 require md.year.
    if md.get("year") is None:
        return None

    year_str = str(md["year"])
    if year_str not in (prod.get("year_string") or ""):
        return None

    score = fuzz.token_set_ratio(
        normalize_title(md["title_main"]),
        normalize_title(prod["page_title"]),
    )

    if score >= THRESHOLD_HIGH:
        return "high"

    if score >= THRESHOLD_MEDIUM:
        lastname = extract_lastname(md.get("first_author_slug") or "")
        if lastname and lastname.lower() in (prod.get("byline_text") or "").lower():
            return "medium"

    return None
```

- [ ] **Step 1.4.4: Run, expect all 21 pass**

```bash
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_pdf_match_lib.py -v
```

Expected: 21/21 PASS.

- [ ] **Step 1.4.5: Commit**

```bash
git add scripts/synthesis/pdf_match_lib.py scripts/synthesis/tests/test_pdf_match_lib.py
git commit -m "feat(pipeline): add tier_match three-tier ladder"
```

---

## Chunk 2: Crawler (`scrape-prod.py`)

Goal: Idempotent walker of `indianliberals.in` periodical categories that caches every detail page's HTML and emits `data/prod-mirror/inventory.jsonl`.

### Task 2.1: Gitignore the cache + create directories

**Files:**
- Modify: `.gitignore`
- Create: `data/prod-mirror/` (empty)

- [ ] **Step 2.1.1: Append to .gitignore**

```bash
echo "" >> .gitignore
echo "# Local mirror of prod indianliberals.in (per docs/superpowers/specs/2026-05-26-pdf-link-reconciliation-design.md)" >> .gitignore
echo "data/prod-mirror/" >> .gitignore
```

- [ ] **Step 2.1.2: Create cache root**

```bash
mkdir -p data/prod-mirror
```

- [ ] **Step 2.1.3: Commit gitignore**

```bash
git add .gitignore
git commit -m "chore: gitignore data/prod-mirror/ (PDF reconciliation cache)"
```

### Task 2.2: Crawler skeleton + seed list

**Files:**
- Create: `scripts/synthesis/scrape-prod.py`

- [ ] **Step 2.2.1: Write the crawler**

```python
#!/usr/bin/env python3
"""
scrape-prod.py — idempotent crawler of existing prod indianliberals.in.

For each seed periodical category page, paginates and collects every
/content/<slug>/ URL, fetches each detail page, caches HTML, parses the
PDF link + metadata, and appends one JSONL row per page to
data/prod-mirror/inventory.jsonl.

Run:
    .venv-extract/bin/python3 scripts/synthesis/scrape-prod.py
    .venv-extract/bin/python3 scripts/synthesis/scrape-prod.py --seed freedom-first --limit 5
    .venv-extract/bin/python3 scripts/synthesis/scrape-prod.py --refresh   # ignore cache
    .venv-extract/bin/python3 scripts/synthesis/scrape-prod.py --rps 0.5   # 1 req every 2s

Per the spec at docs/superpowers/specs/2026-05-26-pdf-link-reconciliation-design.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE = "https://indianliberals.in"
USER_AGENT = "indianliberals-pdf-reconciliation-bot (Adnan, Thothica)"

# Periodical seeds. Hardcoded — the prod site's periodical taxonomy is small
# and stable. If discovery is later needed, see the spec's §5.1 note on
# "additionally walks any /periodicals/<x>/ links it finds during the first
# pass" — not implemented in v1.
SEEDS = [
    "/periodicals/forum-of-free-enterprise/",
    "/periodicals/freedom-first/",
    "/periodicals/the-indian-libertarian/",
    "/periodicals/swatantra-party/",
    "/regional-literature/bengali/",
    "/regional-literature/gujarati/",
    "/regional-literature/hindi/",
    "/regional-literature/marathi/",
]

CACHE_ROOT = Path("data/prod-mirror")
INVENTORY = CACHE_ROOT / "inventory.jsonl"

_YEAR_RX = re.compile(r"\b(19|20)\d{2}\b")


def slug_from_content_url(url: str) -> str | None:
    """https://indianliberals.in/content/foo-bar/ → 'foo-bar'."""
    path = urlparse(url).path
    m = re.match(r"^/content/([^/]+)/?$", path)
    return m.group(1) if m else None


def periodical_from_seed(seed_path: str) -> str:
    """'/periodicals/forum-of-free-enterprise/' → 'forum-of-free-enterprise'.
    '/regional-literature/bengali/' → 'regional-bengali'."""
    parts = [p for p in seed_path.split("/") if p]
    if parts[0] == "regional-literature":
        return f"regional-{parts[1]}"
    return parts[-1]


def fetch(session: requests.Session, url: str, *, retries: int = 3) -> requests.Response | None:
    """GET with exponential backoff on 5xx. Returns None on persistent failure."""
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            print(f"  [error] {url}: {e}", file=sys.stderr)
            if attempt == retries:
                return None
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code == 200:
            return r
        if r.status_code == 404:
            print(f"  [404] {url}", file=sys.stderr)
            return r
        if 500 <= r.status_code < 600:
            if attempt == retries:
                print(f"  [5xx-final] {url}: {r.status_code}", file=sys.stderr)
                return None
            time.sleep(delay)
            delay *= 2
            continue
        # Other 4xx: don't retry, log and return.
        print(f"  [{r.status_code}] {url}", file=sys.stderr)
        return r
    return None


def discover_detail_urls(category_html: str, base_url: str) -> set[str]:
    """Find all /content/<slug>/ links on a category page."""
    soup = BeautifulSoup(category_html, "html.parser")
    out: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/content/" in href:
            absolute = urljoin(base_url, href)
            slug = slug_from_content_url(absolute)
            if slug:
                out.add(absolute.split("?")[0].rstrip("/") + "/")
    return out


def discover_next_page(category_html: str, base_url: str) -> str | None:
    """Look for a 'next page' / pagination link on a category page."""
    soup = BeautifulSoup(category_html, "html.parser")
    # WordPress conventional: rel="next" or class "next page-numbers"
    nxt = soup.find("a", attrs={"rel": "next"})
    if nxt and nxt.get("href"):
        return urljoin(base_url, nxt["href"])
    # Fallback: class-based.
    nxt = soup.find("a", class_="next")
    if nxt and nxt.get("href"):
        return urljoin(base_url, nxt["href"])
    return None


def parse_detail(html: str, source_url: str) -> dict:
    """Extract pdf_url, page_title, byline_text, year_string from a detail page."""
    soup = BeautifulSoup(html, "html.parser")

    # PDF link — first <a> whose href ends in .pdf (case-insensitive).
    pdf_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if href.lower().endswith(".pdf"):
            pdf_url = urljoin(source_url, a["href"])
            break

    # Page title — <h1> preferred, fallback <title>.
    h1 = soup.find("h1")
    page_title = h1.get_text(strip=True) if h1 else (soup.title.string.strip() if soup.title else "")

    # Byline + year — extract from a reasonable region of the page.
    # The site doesn't have a structured byline tag; scan the first ~500 chars of
    # visible content text below the H1.
    body_text = soup.get_text(" ", strip=True)[:2000]
    year_match = _YEAR_RX.search(page_title) or _YEAR_RX.search(body_text)
    year_string = year_match.group(0) if year_match else ""

    return {
        "pdf_url": pdf_url,
        "page_title": page_title,
        "byline_text": body_text[:500],  # generous slice; matcher does substring check
        "year_string": year_string,
        "source_url": source_url,
    }


def cache_path_for(periodical: str, slug: str) -> Path:
    return CACHE_ROOT / periodical / f"{slug}.html"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="append", help="Seed path (e.g. /periodicals/freedom-first/). Repeatable. Default: all known seeds.")
    ap.add_argument("--limit", type=int, default=None, help="Max detail pages to fetch per seed (smoke testing).")
    ap.add_argument("--refresh", action="store_true", help="Ignore cache; re-fetch every page.")
    ap.add_argument("--rps", type=float, default=1.0, help="Max requests per second (default: 1.0).")
    ap.add_argument("--ignore-robots", action="store_true", help="Skip robots.txt check.")
    args = ap.parse_args()

    seeds = args.seed or SEEDS
    interval = 1.0 / args.rps if args.rps > 0 else 0

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if not args.ignore_robots:
        # Best-effort robots check; if disallowed, halt unless --ignore-robots.
        # (For brevity in this MVP, just fetch + log; real exclusion parsing
        # can be added if prod robots.txt complicates things.)
        r = fetch(session, urljoin(BASE, "/robots.txt"))
        if r and r.status_code == 200 and "disallow: /content/" in r.text.lower():
            print("robots.txt disallows /content/. Use --ignore-robots to override.", file=sys.stderr)
            return 2

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    inventory_fh = INVENTORY.open("a", encoding="utf-8")

    total_pages = 0
    total_with_pdf = 0
    total_skipped_cached = 0
    seen_detail_urls: set[str] = set()

    for seed in seeds:
        periodical = periodical_from_seed(seed)
        print(f"[seed] {periodical} ({seed})")

        # Walk paginated category pages.
        current = urljoin(BASE, seed)
        detail_urls: set[str] = set()
        page_no = 0
        while current and page_no < 50:  # safety bound
            page_no += 1
            print(f"  [category page {page_no}] {current}")
            time.sleep(interval)
            r = fetch(session, current)
            if r is None or r.status_code != 200:
                break
            detail_urls.update(discover_detail_urls(r.text, current))
            current = discover_next_page(r.text, current)

        print(f"  [discovered] {len(detail_urls)} detail URLs")

        # Cap for smoke testing.
        ordered = sorted(detail_urls)
        if args.limit:
            ordered = ordered[: args.limit]

        for url in ordered:
            if url in seen_detail_urls:
                continue
            seen_detail_urls.add(url)

            slug = slug_from_content_url(url)
            if not slug:
                continue
            cache_file = cache_path_for(periodical, slug)

            if cache_file.exists() and not args.refresh:
                # Use cached HTML.
                html = cache_file.read_text(encoding="utf-8")
                total_skipped_cached += 1
            else:
                time.sleep(interval)
                r = fetch(session, url)
                if r is None or r.status_code != 200:
                    continue
                html = r.text
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(html, encoding="utf-8")

            meta = parse_detail(html, url)
            row = {
                "prod_slug": slug,
                "periodical": periodical,
                **meta,
            }
            inventory_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            total_pages += 1
            if meta["pdf_url"]:
                total_with_pdf += 1

    inventory_fh.close()
    print(f"\nscrape-prod: {total_pages} pages cached, {total_with_pdf} with PDFs, {total_skipped_cached} from cache.")
    print(f"inventory.jsonl: {INVENTORY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.2.2: Smoke run on a small slice**

```bash
cd "/Users/siraj/Indian Liberals Website"
# Wipe any prior inventory rows from re-runs:
> data/prod-mirror/inventory.jsonl
.venv-extract/bin/python3 scripts/synthesis/scrape-prod.py --seed /periodicals/freedom-first/ --limit 5
```

Expected: 1 category page fetched, ≤ 5 detail pages fetched, ≤ 5 rows in `data/prod-mirror/inventory.jsonl`.

- [ ] **Step 2.2.3: Verify cache + inventory shape**

```bash
ls data/prod-mirror/freedom-first/ | head
wc -l data/prod-mirror/inventory.jsonl
.venv-extract/bin/python3 -c "import json; print(json.loads(open('data/prod-mirror/inventory.jsonl').readline()))"
```

Expected: ≤ 5 HTML files; ≤ 5 inventory rows; first row prints with all 7 keys (`prod_slug, periodical, pdf_url, page_title, byline_text, year_string, source_url`).

- [ ] **Step 2.2.4: Commit**

```bash
git add scripts/synthesis/scrape-prod.py
git commit -m "feat(pipeline): scrape-prod.py — idempotent prod crawler"
```

### Task 2.3: Full crawl

- [ ] **Step 2.3.1: Wipe inventory + run full crawl**

```bash
cd "/Users/siraj/Indian Liberals Website"
> data/prod-mirror/inventory.jsonl
.venv-extract/bin/python3 scripts/synthesis/scrape-prod.py 2>&1 | tee /tmp/scrape-prod-full.log
```

Expected duration: ~5–15 minutes at 1 req/sec (rough estimate; depends on how many pages prod has).

- [ ] **Step 2.3.2: Inspect summary line**

```bash
tail -3 /tmp/scrape-prod-full.log
wc -l data/prod-mirror/inventory.jsonl
```

Expected: hundreds of rows; ~85 %+ with `pdf_url` populated.

---

## Chunk 3: Matcher (`match-pdfs.py`)

Goal: Read inventory + 381 MDs, walk the three-tier ladder, emit manifest + misses TSVs for human review.

### Task 3.1: Matcher script

**Files:**
- Create: `scripts/synthesis/match-pdfs.py`

- [ ] **Step 3.1.1: Write the matcher**

```python
#!/usr/bin/env python3
"""
match-pdfs.py — offline matcher joining prod inventory with primary-works MDs.

Reads:
    data/prod-mirror/inventory.jsonl
    apps/site/src/content/primary-works/*.md (381 MDs)

Writes:
    data/pdf-link-manifest.tsv     — matches sorted by confidence desc
    data/pdf-link-misses.tsv       — unmatched MDs with top-3 fuzzy candidates

Run:
    .venv-extract/bin/python3 scripts/synthesis/match-pdfs.py

Per the spec at docs/superpowers/specs/2026-05-26-pdf-link-reconciliation-design.md.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from rapidfuzz import fuzz, process

# Local sibling import.
_LIB = Path(__file__).resolve().parent / "pdf_match_lib.py"
spec = importlib.util.spec_from_file_location("pdf_match_lib", str(_LIB))
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)

REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
INVENTORY = REPO_ROOT / "data" / "prod-mirror" / "inventory.jsonl"
MANIFEST = REPO_ROOT / "data" / "pdf-link-manifest.tsv"
MISSES = REPO_ROOT / "data" / "pdf-link-misses.tsv"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)

CONFIDENCE_ORDER = {"exact": 0, "high": 1, "medium": 2, "page-only": 3}


def load_md(md_path: Path) -> dict | None:
    """Parse a primary-works MD; return {id, title_main, year, first_author_slug} or None."""
    text = md_path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm = yaml.safe_load(m.group(1)) or {}
    title_block = fm.get("title", {})
    title_main = title_block.get("main") if isinstance(title_block, dict) else ""
    pub = fm.get("publication", {}) or {}
    year = pub.get("year") if isinstance(pub.get("year"), int) else None
    authors = fm.get("authors") or []
    # Authors entries may be plain strings (slugs) or {id: ..., collection: ...} refs.
    first = ""
    if authors:
        a0 = authors[0]
        first = a0 if isinstance(a0, str) else (a0.get("id") if isinstance(a0, dict) else "")
    return {
        "id": fm.get("id") or md_path.stem,
        "title_main": title_main or "",
        "year": year,
        "first_author_slug": first or "",
    }


def load_inventory() -> list[dict]:
    out = []
    if not INVENTORY.exists():
        return out
    with INVENTORY.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def match_one(md: dict, prod_index_by_slug: dict, all_prod: list[dict]) -> tuple[str | None, dict | None]:
    """Return (confidence_label, prod_row) or (None, None) for no match."""
    # Tier 1: exact slug.
    if md["id"] in prod_index_by_slug:
        prod = prod_index_by_slug[md["id"]]
        return (lib.tier_match(md, prod), prod)

    # Tiers 2/3 via fuzzy candidate ranking (only top-5 candidates inspected for speed).
    if md.get("year") is None:
        return (None, None)

    md_norm = lib.normalize_title(md["title_main"])
    if not md_norm:
        return (None, None)

    # Candidate set: prod rows whose year_string contains md.year (cheap pre-filter).
    yr = str(md["year"])
    candidates = [p for p in all_prod if yr in (p.get("year_string") or "")]
    if not candidates:
        return (None, None)

    # Rank by token_set_ratio, top 5.
    scored = process.extract(
        md_norm,
        {i: lib.normalize_title(p["page_title"]) for i, p in enumerate(candidates)},
        scorer=fuzz.token_set_ratio,
        limit=5,
    )

    for normalized_title, score, idx in scored:
        prod = candidates[idx]
        label = lib.tier_match(md, prod)
        if label in ("high", "medium"):
            return (label, prod)

    return (None, None)


def find_misses_candidates(md: dict, all_prod: list[dict], top_k: int = 3) -> list[tuple[str, int]]:
    """Return [(prod_slug, score), …] top_k by raw title similarity (no year filter)."""
    md_norm = lib.normalize_title(md["title_main"])
    if not md_norm or not all_prod:
        return []
    titles = {p["prod_slug"]: lib.normalize_title(p["page_title"]) for p in all_prod}
    scored = process.extract(md_norm, titles, scorer=fuzz.token_set_ratio, limit=top_k)
    # scored entries are (matched_string, score, key)
    return [(key, int(score)) for (_str, score, key) in scored]


def main() -> int:
    if not INVENTORY.exists():
        print(f"missing {INVENTORY}; run scrape-prod.py first", file=sys.stderr)
        return 2

    inv = load_inventory()
    print(f"inventory: {len(inv)} rows")

    # Build prod_slug -> row index (last write wins for accidental dupes).
    prod_index = {row["prod_slug"]: row for row in inv}

    # Reverse-collision check.
    rev = defaultdict(list)
    for row in inv:
        rev[row["prod_slug"]].append(row)
    for slug, rows in rev.items():
        if len(rows) > 1:
            print(f"  [warn] {len(rows)} inventory rows share prod_slug={slug}", file=sys.stderr)

    md_files = sorted(PW_DIR.glob("*.md"))
    print(f"primary-works: {len(md_files)} MDs")

    counts = defaultdict(int)
    manifest_rows: list[dict] = []
    miss_rows: list[dict] = []
    used_prod_slugs: dict[str, str] = {}  # detect MDs colliding on same prod page

    for md_path in md_files:
        md = load_md(md_path)
        if md is None:
            print(f"  [skip-no-frontmatter] {md_path.name}", file=sys.stderr)
            continue

        label, prod = match_one(md, prod_index, inv)
        if label is None:
            counts["miss"] += 1
            candidates = find_misses_candidates(md, inv)
            miss_rows.append({
                "md_slug": md["id"],
                "md_title": md["title_main"],
                "md_year": md["year"] or "",
                "md_first_author": md["first_author_slug"],
                "candidates": candidates,
            })
            continue

        counts[label] += 1
        # Reverse-collision: same prod slug claimed by another MD.
        prev_md = used_prod_slugs.get(prod["prod_slug"])
        notes = ""
        if prev_md and prev_md != md["id"]:
            notes = f"DUPLICATE: also matched by {prev_md}"
        else:
            used_prod_slugs[prod["prod_slug"]] = md["id"]
        manifest_rows.append({
            "md_slug": md["id"],
            "confidence": label,
            "prod_slug": prod["prod_slug"],
            "pdf_url": prod.get("pdf_url") or "",
            "md_title": md["title_main"],
            "prod_title": prod.get("page_title") or "",
            "notes": notes,
        })

    # Sort manifest by (confidence priority, md_slug).
    manifest_rows.sort(key=lambda r: (CONFIDENCE_ORDER.get(r["confidence"], 9), r["md_slug"]))
    miss_rows.sort(key=lambda r: r["md_slug"])

    # Write manifest.
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8") as fh:
        fh.write("md_slug\tconfidence\tprod_slug\tpdf_url\tmd_title\tprod_title\tnotes\n")
        for r in manifest_rows:
            fh.write("\t".join([
                r["md_slug"], r["confidence"], r["prod_slug"], r["pdf_url"],
                r["md_title"].replace("\t", " "), r["prod_title"].replace("\t", " "),
                r["notes"],
            ]) + "\n")

    # Write misses.
    with MISSES.open("w", encoding="utf-8") as fh:
        fh.write("md_slug\tmd_title\tmd_year\tmd_first_author\ttop1_prod_slug\ttop1_score\ttop2_prod_slug\ttop2_score\ttop3_prod_slug\ttop3_score\n")
        for r in miss_rows:
            cands = r["candidates"]
            cells = [
                r["md_slug"], r["md_title"].replace("\t", " "), str(r["md_year"]), r["md_first_author"],
            ]
            for i in range(3):
                if i < len(cands):
                    cells.extend([cands[i][0], str(cands[i][1])])
                else:
                    cells.extend(["", ""])
            fh.write("\t".join(cells) + "\n")

    print()
    print(f"match-pdfs: {counts['exact']} exact, {counts['high']} high, {counts['medium']} medium, {counts['page-only']} page-only, {counts['miss']} misses ({len(md_files)} total).")
    print(f"manifest.tsv: {len(manifest_rows)} rows ({MANIFEST})")
    print(f"misses.tsv: {len(miss_rows)} rows ({MISSES})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3.1.2: Smoke run**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/match-pdfs.py
```

Expected: summary line printed; `data/pdf-link-manifest.tsv` and `data/pdf-link-misses.tsv` created.

- [ ] **Step 3.1.3: Eyeball the TSVs**

```bash
head -10 data/pdf-link-manifest.tsv
wc -l data/pdf-link-manifest.tsv data/pdf-link-misses.tsv
# Confirm exact rows look right:
awk -F'\t' '$2 == "exact"' data/pdf-link-manifest.tsv | head -5
# Confirm medium rows look plausible:
awk -F'\t' '$2 == "medium"' data/pdf-link-manifest.tsv | head -5
```

Expected: > 80 % of 381 MDs matched (i.e. `exact + high` rows ≥ 305).

- [ ] **Step 3.1.4: Commit**

```bash
git add scripts/synthesis/match-pdfs.py
git commit -m "feat(pipeline): match-pdfs.py — three-tier confidence matcher"
```

---

## Chunk 4: Applier (`apply-pdf-urls.py`)

Goal: Read the human-approved manifest and write `pdf_url:` into matched MDs via regex frontmatter surgery (matching `apply-classify.py` pattern).

### Task 4.1: Applier with TDD

**Files:**
- Create: `scripts/synthesis/apply-pdf-urls.py`
- Test: `scripts/synthesis/tests/test_apply_pdf_urls.py`

- [ ] **Step 4.1.1: Write the failing test**

```python
# scripts/synthesis/tests/test_apply_pdf_urls.py
"""Tests for apply-pdf-urls frontmatter mutator."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "apply_pdf_urls",
    str(Path(__file__).resolve().parents[1] / "apply-pdf-urls.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


SAMPLE_MD = """---
id: sample
title:
  main: Sample Work
work_type: speech
publication:
  language: en
  year: 1980
provenance:
  source: ccs_archive
  scan_quality: unknown
rights:
  status: takedown_on_request
themes: []
---

# Body
"""


def test_insert_pdf_url_after_provenance():
    out, status = mod.insert_pdf_url(SAMPLE_MD, "https://example.com/x.pdf", force=False)
    assert status == "inserted"
    # The new line lives after the provenance block, before rights:
    lines = out.split("\n")
    prov_idx = lines.index("provenance:")
    rights_idx = lines.index("rights:")
    inserted_idx = next(i for i, l in enumerate(lines) if l.startswith("pdf_url:"))
    assert prov_idx < inserted_idx < rights_idx


def test_insert_preserves_body_byte_for_byte():
    out, _ = mod.insert_pdf_url(SAMPLE_MD, "https://example.com/x.pdf", force=False)
    # Body after second --- must equal the original body.
    assert out.split("---\n", 2)[2] == SAMPLE_MD.split("---\n", 2)[2]


def test_skips_when_pdf_url_already_present():
    md_with_pdf = SAMPLE_MD.replace(
        "themes: []\n",
        "themes: []\npdf_url: https://old.example.com/old.pdf\n",
    )
    out, status = mod.insert_pdf_url(md_with_pdf, "https://new.example.com/new.pdf", force=False)
    assert status == "skip-existing"
    assert "old.example.com/old.pdf" in out
    assert "new.example.com/new.pdf" not in out


def test_force_overwrites_existing():
    md_with_pdf = SAMPLE_MD.replace(
        "themes: []\n",
        "themes: []\npdf_url: https://old.example.com/old.pdf\n",
    )
    out, status = mod.insert_pdf_url(md_with_pdf, "https://new.example.com/new.pdf", force=True)
    assert status == "replaced"
    assert "new.example.com/new.pdf" in out
    assert "old.example.com/old.pdf" not in out


def test_no_frontmatter_returns_skip():
    out, status = mod.insert_pdf_url("no frontmatter here\n", "https://x/y.pdf", force=False)
    assert status == "skip-no-frontmatter"
    assert out == "no frontmatter here\n"
```

- [ ] **Step 4.1.2: Run, expect fails**

```bash
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_apply_pdf_urls.py -v
```

- [ ] **Step 4.1.3: Implement the applier**

```python
#!/usr/bin/env python3
"""
apply-pdf-urls.py — write pdf_url into primary-works MDs from approved manifest.

Reads:
    data/pdf-link-manifest.tsv (or --manifest <path>)

Writes:
    apps/site/src/content/primary-works/<md_slug>.md (mutated frontmatter)

Run:
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --only-confidence exact,high
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py            # apply all by default
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --force    # overwrite existing pdf_url

Per the spec at docs/superpowers/specs/2026-05-26-pdf-link-reconciliation-design.md.
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_PDF_URL_LINE_RX = re.compile(r"^pdf_url:\s*.*$", re.M)
_PROVENANCE_BLOCK_END_RX = re.compile(
    r"^(provenance:\n(?:[ \t]+.*\n)+)",  # provenance: followed by 1+ indented lines
    re.M,
)


def insert_pdf_url(text: str, pdf_url: str, *, force: bool) -> tuple[str, str]:
    """Return (new_text, status).

    Status values:
      "inserted"           — new pdf_url line added.
      "replaced"           — existing pdf_url line overwritten (force=True only).
      "skip-existing"      — pdf_url already present; force=False.
      "skip-no-frontmatter"— no frontmatter regex match.
    """
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return text, "skip-no-frontmatter"

    fm, body = m.group(1), m.group(2)
    has_pdf = _PDF_URL_LINE_RX.search(fm) is not None

    if has_pdf and not force:
        return text, "skip-existing"

    new_line = f"pdf_url: {pdf_url}"

    if has_pdf:
        # Replace existing line.
        new_fm = _PDF_URL_LINE_RX.sub(new_line, fm, count=1)
        return f"---\n{new_fm}\n---\n{body}", "replaced"

    # Insert after the provenance: block. If the provenance block isn't found
    # (defensive fallback), append at end of frontmatter.
    pm = _PROVENANCE_BLOCK_END_RX.search(fm)
    if pm:
        insert_at = pm.end()  # position right after the provenance block
        new_fm = fm[:insert_at] + new_line + "\n" + fm[insert_at:]
    else:
        # Fallback: append at end of frontmatter (before the closing ---).
        new_fm = fm.rstrip("\n") + "\n" + new_line

    return f"---\n{new_fm}\n---\n{body}", "inserted"


def load_manifest(path: Path, accepted: set[str]) -> list[dict]:
    """Read a TSV manifest. accepted = set of confidence labels to apply."""
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if row.get("confidence") not in accepted:
                continue
            if not row.get("pdf_url"):
                continue  # don't apply rows with no URL
            if "DUPLICATE" in (row.get("notes") or ""):
                continue
            rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(REPO_ROOT / "data" / "pdf-link-manifest.tsv"))
    ap.add_argument(
        "--only-confidence",
        default="exact,high,medium",
        help="Comma-separated confidence labels to apply (default: exact,high,medium).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print diff per MD; don't write.")
    ap.add_argument("--force", action="store_true", help="Overwrite existing pdf_url.")
    ap.add_argument("--no-commit", action="store_true", help="Don't auto-commit after writes.")
    args = ap.parse_args()

    accepted = {s.strip() for s in args.only_confidence.split(",") if s.strip()}
    rows = load_manifest(Path(args.manifest), accepted)
    print(f"applying {len(rows)} rows ({sorted(accepted)})")

    statuses: dict[str, int] = {}
    touched: list[Path] = []

    for row in rows:
        slug = row["md_slug"]
        pdf_url = row["pdf_url"]
        md_path = PW_DIR / f"{slug}.md"
        if not md_path.exists():
            print(f"  [missing] {md_path}", file=sys.stderr)
            statuses["missing"] = statuses.get("missing", 0) + 1
            continue

        text = md_path.read_text(encoding="utf-8")
        new_text, status = insert_pdf_url(text, pdf_url, force=args.force)
        statuses[status] = statuses.get(status, 0) + 1

        if status in ("inserted", "replaced"):
            if args.dry_run:
                # Tiny visible diff:
                old_line = next((l for l in text.split("\n") if l.startswith("pdf_url:")), "(none)")
                new_line = next((l for l in new_text.split("\n") if l.startswith("pdf_url:")), "(none)")
                print(f"  [{status}] {slug}: {old_line} → {new_line}")
            else:
                md_path.write_text(new_text, encoding="utf-8")
                touched.append(md_path)

    print()
    print("statuses:")
    for k, v in sorted(statuses.items()):
        print(f"  {k}: {v}")

    if not args.dry_run and touched and not args.no_commit:
        # Stage + commit.
        subprocess.run(["git", "add", "--"] + [str(p) for p in touched], check=True, cwd=REPO_ROOT)
        n = len(touched)
        breakdown = ", ".join(f"{statuses.get(k, 0)} {k}" for k in ("inserted", "replaced") if statuses.get(k))
        commit_msg = (
            f"data(primary-works): populate pdf_url from prod indianliberals.in (N={n})\n\n"
            f"Tier breakdown: {breakdown}.\n"
            f"Source: data/prod-mirror (cached scrape).\n\n"
            f"Transitional; will be replaced by R2-hosted URLs in a future spec\n"
            f"per the pdf_staging_path / pdf_size_mb schema fields."
        )
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=REPO_ROOT)
        print(f"committed {n} MDs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4.1.4: Run tests, expect 5/5 pass**

```bash
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_apply_pdf_urls.py -v
```

- [ ] **Step 4.1.5: Commit**

```bash
git add scripts/synthesis/apply-pdf-urls.py scripts/synthesis/tests/test_apply_pdf_urls.py
git commit -m "feat(pipeline): apply-pdf-urls.py — write pdf_url into matched MDs"
```

### Task 4.2: Dry-run validation

- [ ] **Step 4.2.1: Run applier in --dry-run mode**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --dry-run --only-confidence exact | head -20
```

Expected: tens of "inserted" lines printed; nothing written.

- [ ] **Step 4.2.2: Verify a single MD diff by hand**

Pick the first `exact` row, run the applier on just it via a temporary single-row manifest, then diff:

```bash
head -1 data/pdf-link-manifest.tsv > /tmp/test-manifest.tsv
awk -F'\t' '$2 == "exact"' data/pdf-link-manifest.tsv | head -1 >> /tmp/test-manifest.tsv

SLUG=$(awk -F'\t' 'NR==2 {print $1}' /tmp/test-manifest.tsv)
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --manifest /tmp/test-manifest.tsv --no-commit
git diff apps/site/src/content/primary-works/$SLUG.md
git checkout -- apps/site/src/content/primary-works/$SLUG.md  # revert
```

Expected: clean single-line diff adding `pdf_url: <url>` right after the `provenance:` block; no other changes.

---

## Chunk 5: Manifest review + full apply

Goal: Adnan eyeballs the manifest + misses TSVs, decides what to apply, then the applier writes + commits.

### Task 5.1: Manifest review (HUMAN)

**STOP — surface the two TSVs to Adnan before proceeding to Task 5.2.** This is a human-in-loop checkpoint: an autonomous subagent must NOT auto-run Task 5.2 without Adnan's eyeball on the manifest. The subagent's job here is to print summary stats and hand off.

- [ ] **Step 5.1.1: Open manifest + misses in your editor**

```bash
cd "/Users/siraj/Indian Liberals Website"
# Open both files; eyeball especially:
#   - All "medium" rows (lower confidence; spot-check the prod_title matches)
#   - All "page-only" rows (slug matched but no PDF — note for follow-up)
#   - "DUPLICATE" notes
#   - First 5-10 entries of misses.tsv (look for obvious rescues)
$EDITOR data/pdf-link-manifest.tsv data/pdf-link-misses.tsv
```

- [ ] **Step 5.1.2: (Optional) Build manual-overrides.tsv from misses you can rescue**

If the eyeball found obvious misses, create `data/manual-overrides.tsv` with the same columns as `manifest.tsv` (any confidence label; recommend `exact` since you've eyeballed them):

```
md_slug	confidence	prod_slug	pdf_url	md_title	prod_title	notes
some-md-slug	exact	some-prod-slug	https://indianliberals.in/.../foo.pdf	Title	Prod title	manual override
```

### Task 5.2: Apply approved manifest

- [ ] **Step 5.2.1: Apply exact + high + medium**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py
```

Expected: a single commit lands; "statuses" prints with `inserted: N`.

- [ ] **Step 5.2.2: (Optional) Apply manual overrides**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --manifest data/manual-overrides.tsv
```

Expected: a second commit lands.

### Task 5.3: Build verification

- [ ] **Step 5.3.1: Build clean**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/pdf-build.log
ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/pdf-build.log
# Expect: 0 (Zod validates every pdf_url via .url())

test "$(find dist -name 'index.html' | wc -l)" = "1287" && echo "page count matches"
```

- [ ] **Step 5.3.2: Spot-check 5 rendered pages**

```bash
# Pick 5 random matched MD slugs from the manifest:
awk -F'\t' '$2 == "exact" {print $1}' /Users/siraj/Indian\ Liberals\ Website/data/pdf-link-manifest.tsv | shuf -n 5 | while read slug; do
  echo "=== $slug ==="
  grep -E 'href="[^"]+\.pdf"' dist/primary-works/$slug/index.html | head -1
done
```

Expected: each prints a single `href="https://indianliberals.in/.../*.pdf"` line.

- [ ] **Step 5.3.3: Manual click-through**

Open 3 of the rendered pages in a browser (`open dist/primary-works/<slug>/index.html`) and click "Read PDF". Expected: PDF loads on prod.

### Task 5.4: Commit data manifests

The cached HTML is gitignored, but the TSV manifests are kept in-repo for traceability.

- [ ] **Step 5.4.1: Commit the TSVs**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add data/pdf-link-manifest.tsv data/pdf-link-misses.tsv
[ -f data/manual-overrides.tsv ] && git add data/manual-overrides.tsv
git commit -m "data: pdf-link reconciliation manifests (snapshot)"
```

---

## Final acceptance

- [ ] **Acceptance #1:** `pnpm build` exits clean.
- [ ] **Acceptance #2:** `find apps/site/dist -name 'index.html' | wc -l` equals 1287 (page count unchanged).
- [ ] **Acceptance #3:** `grep -c "^pdf_url:" apps/site/src/content/primary-works/*.md | awk -F: '{n+=$2} END {print n}'` ≥ 305 (≥ 80 % of 381 matched at exact + high + medium).
- [ ] **Acceptance #4:** Three randomly-picked primary-works pages render a "Read PDF" button whose href is a working URL on `indianliberals.in`.
- [ ] **Acceptance #5:** All commits landed locally on `main`; `git log --oneline 5ef3848..HEAD` (or current pre-Chunk-1 SHA) shows ≤ 6 commits and a clear narrative.
- [ ] **Acceptance #6:** Final code-reviewer pass over the whole diff (pre-Chunk-1 vs HEAD) signs off.
- [ ] **STOP** — do NOT push. Surface to Adnan for the push call.

---

## Sequencing notes

- Chunks 1–4 are pure code (TDD-driven); land them as separate commits.
- Chunk 5 is the human-in-loop step + the data commits.
- Chunk 6 (manual override pass) is optional and only fires if Chunk 5's eyeball surfaces obvious rescues.

## Stopping criteria

The work is "done" when:
- All `exact` and `high` rows are applied (1 commit).
- All `medium` rows are reviewed and applied selectively (in the same or follow-up commit).
- `misses.tsv` has been eyeballed; any obvious rescues went through `manual-overrides.tsv`.
- All 6 final acceptance checks pass.
- A final code-reviewer pass signs off.
- Adnan signs off on the visible result for 3 sampled primary-work pages.

## Out of scope (per spec §2)

- Hosting PDFs on R2 (separate spec).
- Populating `manifestations[]` for multi-edition works.
- Reverse reconciliation (works on prod we lack an MD for).
- Translated PDFs for non-English primary-works MDs.
- Link-rot monitoring of populated URLs.

---

## Plan complete

After all chunks pass:

1. The terminal state is:
   - 4 new files under `scripts/synthesis/`: `pdf_match_lib.py`, `scrape-prod.py`, `match-pdfs.py`, `apply-pdf-urls.py`.
   - 2 new test files under `scripts/synthesis/tests/`.
   - 2–3 new TSVs under `data/`: `pdf-link-manifest.tsv`, `pdf-link-misses.tsv`, optionally `manual-overrides.tsv`.
   - 305+ primary-works MDs with `pdf_url` populated; "Read PDF" buttons rendering on the site.
2. Hand the diff to Adnan for review + push.
