#!/usr/bin/env python3
"""
scrape-prod.py — idempotent crawler of existing prod indianliberals.in.

For each seed periodical category page, paginates and collects every
/content/<slug>/ URL, fetches each detail page, caches HTML, parses the
PDF link + metadata, and appends one JSONL row per page to
data/prod-mirror/inventory.jsonl.

Run:
    .venv-extract/bin/python3 scripts/synthesis/scrape-prod.py
    .venv-extract/bin/python3 scripts/synthesis/scrape-prod.py --seed /periodicals/freedom-first/ --limit 5
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
        if not href.lower().endswith(".pdf"):
            continue
        # Reject placeholder hrefs like ".pdf" or "#.pdf" that satisfy the substring
        # check but resolve to an empty/fragment-only URL with no actual filename.
        candidate = urljoin(source_url, href)
        basename = urlparse(candidate).path.rsplit("/", 1)[-1]
        if basename in ("", ".pdf"):
            continue
        pdf_url = candidate
        break

    # Page title — <h1> preferred, fallback <title>.
    h1 = soup.find("h1")
    page_title = h1.get_text(strip=True) if h1 else (soup.title.string.strip() if soup.title and soup.title.string else "")

    # Byline + year — extract from a reasonable region of the page.
    # The site doesn't have a structured byline tag; scan the first ~2000 chars
    # of visible content text below the H1.
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
        r = fetch(session, urljoin(BASE, "/robots.txt"))
        if r and r.status_code == 200 and "disallow: /content/" in r.text.lower():
            print("robots.txt disallows /content/. Use --ignore-robots to override.", file=sys.stderr)
            return 2

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    total_pages = 0
    total_with_pdf = 0
    total_skipped_cached = 0
    seen_detail_urls: set[str] = set()

    with INVENTORY.open("a", encoding="utf-8") as inventory_fh:
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

    print(f"\nscrape-prod: {total_pages} pages cached, {total_with_pdf} with PDFs, {total_skipped_cached} from cache.")
    print(f"inventory.jsonl: {INVENTORY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
