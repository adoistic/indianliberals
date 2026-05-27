#!/usr/bin/env python3
"""Local fallback for the indianliberals-theprint-ingest Cloudflare Worker cron.

Ports the worker's TS logic (apps/theprint-ingest/src/rss.ts + markdown.ts) to
Python so the daily ingest can be re-run from a local terminal when the worker
is unreachable, mis-deployed, silently failing, or when you simply don't have
Cloudflare credentials handy.

Behaviour, mirroring the worker:
  - Fetches the Indian Liberals Matter RSS feed.
  - For each item, in feed order, up to MAX_ITEMS:
      - Skips if the article URL or slug is in data/theprint-blocklist.json.
      - Skips if the target MD already exists AND was last touched by someone
        other than theprint-ingest-bot (admin-edit detection, Critical Gap T20).
      - Otherwise emits a markdown file with the same frontmatter shape the
        worker produces, writes it, stages it.
  - Commits the batch with --author=theprint-ingest-bot so the next worker run
    correctly identifies these MDs as bot-emitted and not admin-edited.

Differences from the worker:
  - Writes files via the local working tree, not the GitHub Contents API.
  - Caller is responsible for `git push` after this script commits.
  - No structured-log output — prints a human-readable summary instead.

Run:
    .venv-extract/bin/python3 apps/theprint-ingest/scripts/cron-rerun.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# Repo root = three levels up from this file (apps/theprint-ingest/scripts/<this>.py).
REPO_ROOT = Path(__file__).resolve().parents[3]
MIRROR_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "theprint-mirror"
BLOCKLIST_PATH = REPO_ROOT / "data" / "theprint-blocklist.json"
RSS_URL = "https://theprint.in/category/opinion/indian-liberals-matter/feed/"
MAX_ITEMS = 10
BOT_NAME = "theprint-ingest-bot"
BOT_EMAIL = "theprint-ingest@indianliberals.in"


# ─── RSS parse (port of rss.ts) ─────────────────────────────────────────

_CDATA = re.compile(r"^<!\[CDATA\[([\s\S]*?)\]\]>$", re.I)


def _strip_cdata(s: str) -> str:
    s = s.strip()
    m = _CDATA.match(s)
    return m.group(1) if m else s


def _decode_entities(s: str) -> str:
    s = (
        s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#039;", "'")
        .replace("&apos;", "'")
    )
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    s = re.sub(r"&#x([0-9a-f]+);", lambda m: chr(int(m.group(1), 16)), s, flags=re.I)
    return s


def _extract_text(block: str, tag: str) -> str:
    rx = re.compile(
        r"<" + re.escape(tag) + r"(?:\s[^>]*)?>([\s\S]*?)</" + re.escape(tag) + r">",
        re.I,
    )
    m = rx.search(block)
    return _strip_cdata(m.group(1)) if m else ""


def _extract_all(block: str, tag: str) -> list[str]:
    rx = re.compile(
        r"<" + re.escape(tag) + r"(?:\s[^>]*)?>([\s\S]*?)</" + re.escape(tag) + r">",
        re.I,
    )
    return [_strip_cdata(m.group(1)) for m in rx.finditer(block)]


def parse_rss(xml: str) -> list[dict]:
    xml = xml.lstrip("﻿")
    items = []
    for m in re.finditer(r"<item\b[^>]*>([\s\S]*?)</item>", xml):
        block = m.group(1)
        title = _extract_text(block, "title")
        link = _extract_text(block, "link")
        guid = _extract_text(block, "guid") or link
        pub_date_str = _extract_text(block, "pubDate")
        author = _extract_text(block, "dc:creator") or _extract_text(block, "author")
        description = _extract_text(block, "description")
        content_html = _extract_text(block, "content:encoded") or description
        cats = _extract_all(block, "category")
        if not title or not link:
            continue
        try:
            # RFC 822: "Sat, 23 May 2026 05:27:28 +0000"
            pub = dt.datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
        except (ValueError, TypeError):
            pub = dt.datetime.now(dt.timezone.utc)
        items.append({
            "title": _decode_entities(title.strip()),
            "link": link.strip(),
            "guid": guid.strip(),
            "pubDate": pub,
            "author": _decode_entities(author.strip()),
            "description": description,
            "contentHtml": content_html,
            "categories": [_decode_entities(c.strip()) for c in cats],
        })
    return items


def slug_from_url(url: str, fallback_title: str) -> str:
    try:
        path = urlparse(url).path
        parts = [p for p in path.split("/") if p]
        if "indian-liberals-matter" in parts:
            i = parts.index("indian-liberals-matter")
            if i + 1 < len(parts):
                return parts[i + 1]
        for p in reversed(parts):
            if not p.isdigit():
                return p
    except Exception:
        pass
    return re.sub(r"[^a-z0-9]+", "-", fallback_title.lower()).strip("-")[:80]


# ─── HTML → Markdown (port of markdown.ts) ──────────────────────────────


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _inline_html_to_md(s: str) -> str:
    # Strong / em / links
    s = re.sub(r"<(?:strong|b)\b[^>]*>([\s\S]*?)</(?:strong|b)>", r"**\1**", s, flags=re.I)
    s = re.sub(r"<(?:em|i)\b[^>]*>([\s\S]*?)</(?:em|i)>", r"*\1*", s, flags=re.I)
    s = re.sub(
        r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
        lambda m: f"[{_strip_tags(m.group(2))}]({m.group(1)})",
        s,
        flags=re.I,
    )
    # Drop remaining tags
    s = re.sub(r"<[^>]+>", "", s)
    return _decode_entities(s)


def html_to_markdown(html: str) -> str:
    if not html:
        return ""
    s = html
    # Block-level transforms first
    s = re.sub(r"<h2\b[^>]*>([\s\S]*?)</h2>", lambda m: f"\n\n## {_strip_tags(m.group(1)).strip()}\n\n", s, flags=re.I)
    s = re.sub(r"<h3\b[^>]*>([\s\S]*?)</h3>", lambda m: f"\n\n### {_strip_tags(m.group(1)).strip()}\n\n", s, flags=re.I)

    def _bq(m):
        inner = _strip_tags(m.group(1)).strip()
        return "\n\n" + "\n".join(f"> {line}" for line in inner.split("\n")) + "\n\n"

    s = re.sub(r"<blockquote\b[^>]*>([\s\S]*?)</blockquote>", _bq, s, flags=re.I)
    s = re.sub(r"<p\b[^>]*>([\s\S]*?)</p>", lambda m: f"\n\n{_inline_html_to_md(m.group(1)).strip()}\n\n", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "  \n", s, flags=re.I)

    def _ul(m):
        items = re.findall(r"<li\b[^>]*>([\s\S]*?)</li>", m.group(1), flags=re.I)
        return "\n\n" + "\n".join(f"- {_inline_html_to_md(li).strip()}" for li in items) + "\n\n"

    def _ol(m):
        items = re.findall(r"<li\b[^>]*>([\s\S]*?)</li>", m.group(1), flags=re.I)
        return "\n\n" + "\n".join(f"{i+1}. {_inline_html_to_md(li).strip()}" for i, li in enumerate(items)) + "\n\n"

    s = re.sub(r"<ul\b[^>]*>([\s\S]*?)</ul>", _ul, s, flags=re.I)
    s = re.sub(r"<ol\b[^>]*>([\s\S]*?)</ol>", _ol, s, flags=re.I)

    # Inline pass for anything outside the block tags
    s = _inline_html_to_md(s)

    # Normalise whitespace
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def slugify_theme(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def yaml_string(s: str) -> str:
    # Worker uses JSON.stringify, which escapes " and \. Mirror that.
    return json.dumps(s, ensure_ascii=False)


def emit_md(item: dict, slug: str, mirrored_on_iso: str) -> str:
    themes = []
    for c in item["categories"]:
        sl = slugify_theme(c)
        if sl and sl not in themes:
            themes.append(sl)

    lines = ["---"]
    lines.append(f"id: {yaml_string(slug)}")
    lines.append(f"title: {yaml_string(item['title'])}")
    lines.append(f"pubDate: {item['pubDate'].astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')}")
    lines.append(f"author_name: {yaml_string(item['author'] or 'ThePrint contributor')}")
    lines.append(f"theprint_url: {yaml_string(item['link'])}")
    if themes:
        lines.append(f"themes: [{', '.join(yaml_string(t) for t in themes)}]")
    else:
        lines.append("themes: []")
    lines.append("related_thinkers: []")
    lines.append("related_works: []")
    lines.append("noindex: true")
    lines.append("needs_review: true")
    lines.append("draft: false")
    lines.append("---")
    frontmatter = "\n".join(lines)

    attribution = (
        f"_Mirrored from [ThePrint]({item['link']}) on {mirrored_on_iso}. "
        f"Originally published {item['pubDate'].astimezone(dt.timezone.utc).strftime('%Y-%m-%d')}. "
        f"Author retains all rights; the canonical version on ThePrint should be cited. "
        f"This mirror exists for AI-agent readability — search engines are asked not to index it "
        f"(canonical SEO weight stays with ThePrint)._"
    )
    heading = f"# {item['title']}"
    body = html_to_markdown(item["contentHtml"] or item["description"])
    return f"{frontmatter}\n\n{attribution}\n\n{heading}\n\n{body}\n"


# ─── Main ──────────────────────────────────────────────────────────────


def load_blocklist() -> set[str]:
    if not BLOCKLIST_PATH.exists():
        return set()
    try:
        data = json.loads(BLOCKLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return {str(u) for u in data}
    if isinstance(data, dict):
        # Allow {"blocked": [...]} or similar
        return {str(u) for u in data.get("blocked", [])}
    return set()


def last_commit_author_email(path: Path) -> str | None:
    """Return the email of the last commit author for path, or None if file has no history."""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ae", "--", str(path.relative_to(REPO_ROOT))],
            capture_output=True, text=True, cwd=str(REPO_ROOT), check=True,
        )
    except subprocess.CalledProcessError:
        return None
    out = r.stdout.strip()
    return out or None


def main() -> int:
    print(f"Fetching RSS: {RSS_URL}")
    req = urllib.request.Request(
        RSS_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; indianliberals-rerun/0.1)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        xml = r.read().decode("utf-8", errors="replace")

    items = parse_rss(xml)
    print(f"feed: {len(items)} items")

    blocklist = load_blocklist()
    if blocklist:
        print(f"blocklist: {len(blocklist)} URLs")

    mirrored_on_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    created: list[str] = []
    updated: list[str] = []
    skipped_blocklist: list[str] = []
    skipped_admin: list[str] = []
    skipped_no_change: list[str] = []

    for item in items[:MAX_ITEMS]:
        slug = slug_from_url(item["link"], item["title"])
        if item["link"] in blocklist or slug in blocklist:
            skipped_blocklist.append(slug)
            continue
        target = MIRROR_DIR / f"{slug}.md"
        new_text = emit_md(item, slug, mirrored_on_iso)

        if target.exists():
            existing_author = last_commit_author_email(target)
            if existing_author and existing_author != BOT_EMAIL:
                skipped_admin.append(slug)
                continue
            existing_text = target.read_text(encoding="utf-8")
            if existing_text == new_text:
                skipped_no_change.append(slug)
                continue
            target.write_text(new_text, encoding="utf-8")
            updated.append(slug)
        else:
            target.write_text(new_text, encoding="utf-8")
            created.append(slug)

    print()
    print(f"created: {len(created)}")
    for s in created: print(f"  + {s}")
    print(f"updated: {len(updated)}")
    for s in updated: print(f"  ~ {s}")
    print(f"skipped (blocklist): {len(skipped_blocklist)}")
    print(f"skipped (admin-edited): {len(skipped_admin)}")
    for s in skipped_admin: print(f"  ! {s}")
    print(f"skipped (no change): {len(skipped_no_change)}")

    if not (created or updated):
        print("\nNothing to commit.")
        return 0

    # Stage all touched files
    touched = [MIRROR_DIR / f"{s}.md" for s in created + updated]
    rels = [str(p.relative_to(REPO_ROOT)) for p in touched]
    subprocess.run(["git", "add", "--"] + rels, check=True, cwd=str(REPO_ROOT))

    # Commit with the bot author so future cron runs preserve admin-edit semantics.
    n = len(created) + len(updated)
    msg = (
        f"data(theprint-mirror): manual cron-rerun — {n} article(s) "
        f"({len(created)} new, {len(updated)} updated)\n\n"
        f"Ran apps/theprint-ingest/scripts/cron-rerun.py — the local Python fallback "
        f"for the Cloudflare Worker cron. Authored as theprint-ingest-bot so the next "
        f"actual worker run treats these MDs as bot-emitted via the admin-edit "
        f"detection in src/github.ts.\n\n"
        f"New: {', '.join(created) if created else '(none)'}\n"
        f"Updated: {', '.join(updated) if updated else '(none)'}"
    )
    subprocess.run(
        ["git", "commit",
         f"--author={BOT_NAME} <{BOT_EMAIL}>",
         "-m", msg],
        check=True, cwd=str(REPO_ROOT),
    )
    print(f"\ncommitted {len(touched)} files as {BOT_NAME} <{BOT_EMAIL}>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
