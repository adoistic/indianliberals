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
import tarfile
import time
from collections import defaultdict
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
    "/periodicals/indian-liberal-group/",
    "/periodicals/liberal-times/",
    "/periodicals/other-publications/",
    "/periodicals/shetkari-sanghatak/",
    "/periodicals/khoj/",
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


# ── Backup-tarball fallback ────────────────────────────────────────────────
# Some sections (notably /regional-literature/*) render their listings via
# JavaScript, so a plain requests crawl of the category page yields zero
# /content/ links. The PDFs themselves are static files served straight from
# the server filesystem, which is captured verbatim in the cPanel backup
# tarball. When a seed yields nothing live AND --backup is supplied, we
# enumerate that section's PDFs from the tarball instead, so the mirror still
# covers them. Server static-PDF folders are the URL path component, e.g.
# /gujarati/<f>.pdf, /marathi/<f>.pdf, /forum-of-free-enterprise/<f>.pdf.

def backup_section_for_seed(seed_path: str) -> str:
    """Map a seed to the server's static-PDF folder name.
    '/regional-literature/marathi/' -> 'marathi'; else the last path part."""
    parts = [p for p in seed_path.split("/") if p]
    return parts[1] if parts[0] == "regional-literature" else parts[-1]


def backup_pdf_index(tarball: Path) -> dict[str, list[str]]:
    """Scan the backup tarball once; return {section: [pdf_basename, ...]} for
    every PDF directly under a canonical public_html/<section>/ folder
    (ignoring -old / _bk snapshot copies)."""
    idx: dict[str, set] = defaultdict(set)
    rx = re.compile(r"/public_html/([^/]+)/([^/]+\.pdf)$", re.I)
    with tarfile.open(tarball, "r:*") as tf:
        for name in tf.getnames():
            m = rx.search(name)
            if m:
                idx[m.group(1)].add(m.group(2))
    return {k: sorted(v) for k, v in idx.items()}


def backup_rows_for_section(section: str, periodical: str, files: list[str]) -> list[dict]:
    """Build inventory rows from a section's backup PDF filenames."""
    rows = []
    for fname in files:
        stem = re.sub(r"\.pdf$", "", fname, flags=re.I)
        slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
        ym = _YEAR_RX.search(stem)
        rows.append({
            "prod_slug": slug,
            "periodical": periodical,
            "pdf_url": f"{BASE}/{section}/{fname}",
            "page_title": stem.replace("-", " ").strip(),
            "byline_text": "",
            "year_string": ym.group(0) if ym else "",
            "source_url": "",
            "source": "backup-fallback",
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="append", help="Seed path (e.g. /periodicals/freedom-first/). Repeatable. Default: all known seeds.")
    ap.add_argument("--limit", type=int, default=None, help="Max detail pages to fetch per seed (smoke testing).")
    ap.add_argument("--refresh", action="store_true", help="Ignore cache; re-fetch every page.")
    ap.add_argument("--rps", type=float, default=1.0, help="Max requests per second (default: 1.0).")
    ap.add_argument("--ignore-robots", action="store_true", help="Skip robots.txt check.")
    ap.add_argument("--backup", type=Path, default=None, help="Path to the cPanel backup tarball; used as a fallback to enumerate a section's static PDFs when its live listing is JS-rendered and yields no links.")
    args = ap.parse_args()

    seeds = args.seed or SEEDS
    interval = 1.0 / args.rps if args.rps > 0 else 0

    backup_index: dict[str, list[str]] | None = None
    if args.backup:
        if not args.backup.exists():
            print(f"--backup path not found: {args.backup}", file=sys.stderr)
            return 2
        print(f"[backup] indexing {args.backup} ...")
        backup_index = backup_pdf_index(args.backup)
        print(f"[backup] indexed {sum(len(v) for v in backup_index.values())} PDFs across {len(backup_index)} sections")

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

            # JS-rendered listing yielded nothing live → fall back to the
            # backup tarball's static PDFs for this section, if available.
            if not detail_urls and backup_index is not None:
                section = backup_section_for_seed(seed)
                files = backup_index.get(section, [])
                rows = backup_rows_for_section(section, periodical, files)
                for row in rows:
                    inventory_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                total_pages += len(rows)
                total_with_pdf += len(rows)
                print(f"  [backup-fallback] {len(rows)} PDFs from public_html/{section}/")
                continue

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
