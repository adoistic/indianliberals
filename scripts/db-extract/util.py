"""Shared helpers: slugify, HTML→Markdown, frontmatter writer."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any


# --- slugify --------------------------------------------------------------


def slugify(s: str) -> str:
    """Slug compatible with our content collection IDs: ascii lowercase with hyphens."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "untitled"


# --- HTML → Markdown -----------------------------------------------------

# Order matters: shortcode patterns first, then tags.

_SHORTCODE_RE = re.compile(r"\[/?vc_[^\]]*\]|\[/?cs_[^\]]*\]|\[/?stm_[^\]]*\]")
_SHORTCODE_GENERIC_RE = re.compile(r"\[/?(?:row|column|column_text|empty_space|caption|audio|video|gallery|embed)[^\]]*\]", re.IGNORECASE)


def strip_shortcodes(html: str) -> str:
    html = _SHORTCODE_RE.sub("", html)
    html = _SHORTCODE_GENERIC_RE.sub("", html)
    return html


# Convert basic HTML to markdown. Not a full parser — handles the WordPress
# output patterns we see in this dump.
def html_to_markdown(html: str) -> str:
    if not html:
        return ""

    text = strip_shortcodes(html)

    # <br>, <br/> → newline
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # <strong>/<b>
    text = re.sub(r"</?(strong|b)\b[^>]*>", "**", text, flags=re.IGNORECASE)
    # <em>/<i>
    text = re.sub(r"</?(em|i)\b[^>]*>", "_", text, flags=re.IGNORECASE)

    # Links: <a href="...">text</a> → [text](href)
    text = re.sub(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(2)).strip()}]({m.group(1)})",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Images: <img src="..."> → ![](src)
    text = re.sub(
        r"<img\b[^>]*src=[\"']([^\"']+)[\"'][^>]*alt=[\"']([^\"']*)[\"'][^>]*/?>",
        r"![\2](\1)",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<img\b[^>]*src=[\"']([^\"']+)[\"'][^>]*/?>",
        r"![](\1)",
        text,
        flags=re.IGNORECASE,
    )

    # Headings
    for level in range(6, 0, -1):
        text = re.sub(
            rf"<h{level}\b[^>]*>(.*?)</h{level}>",
            lambda m, lvl=level: f"\n\n{'#' * lvl} {re.sub(r'<[^>]+>', '', m.group(1)).strip()}\n\n",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Lists
    text = re.sub(r"<li\b[^>]*>(.*?)</li>", lambda m: f"- {re.sub(r'<[^>]+>', '', m.group(1)).strip()}\n", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</?(ul|ol)\b[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Paragraphs: <p>...</p> → ...\n\n
    text = re.sub(r"<p\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)

    # Block-level wrappers we don't care about
    text = re.sub(r"</?(div|span|section|article|figure|figcaption|blockquote)\b[^>]*>", "", text, flags=re.IGNORECASE)

    # Remaining unknown tags → strip
    text = re.sub(r"<[^>]+>", "", text)

    # HTML entities
    entities = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&apos;": "'",
        "&#39;": "'",
        "&rsquo;": "’",
        "&lsquo;": "‘",
        "&rdquo;": "”",
        "&ldquo;": "“",
        "&hellip;": "…",
        "&mdash;": "—",
        "&ndash;": "–",
    }
    for k, v in entities.items():
        text = text.replace(k, v)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)

    # Collapse 3+ newlines, trim trailing whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


# --- Frontmatter writer ---------------------------------------------------


def _yaml_value(v: Any) -> str:
    """Render a Python value as a YAML scalar/sequence."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        if not v:
            return "[]"
        return "\n" + "\n".join(f"  - {_yaml_inline(x)}" for x in v)
    if isinstance(v, dict):
        # Drop keys whose value is None so we don't emit `key: null` for optional fields.
        pruned = {k: val for k, val in v.items() if val is not None}
        if not pruned:
            return "{}"
        return "\n" + "\n".join(f"  {k}: {_yaml_inline(val)}" for k, val in pruned.items())
    return _yaml_inline(v)


def _yaml_inline(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # Always quote — safer than trying to predict YAML edge cases.
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def write_md_with_frontmatter(path: Path, frontmatter: dict, body: str) -> None:
    """Atomic-ish write: frontmatter then body. Skips keys whose value is None."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if v is None:
            continue
        fm_lines.append(f"{k}: {_yaml_value(v)}")
    fm_lines.append("---")
    fm = "\n".join(fm_lines)
    path.write_text(f"{fm}\n\n{body.strip()}\n", encoding="utf-8")
