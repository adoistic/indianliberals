#!/usr/bin/env python3
"""
Shared primitives for the eval: text folding, citation shapes, corpus access.

Both the pool validator and the grader import from here, so a string that
validates is graded by exactly the same comparison. Anything that decides
whether two pieces of text "match" belongs in this file and nowhere else.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CORPUS_PATH = HERE / "corpus.json"
POOL_PATH = REPO / "data" / "eval" / "pool.json"

SITE_ORIGIN = "https://indianliberals.in"

# A paragraph anchor as the site emits it, and as an agent should cite it.
ANCHOR_RE = re.compile(r"p-[0-9a-f]{6}(?:-\d+)?")

# A structured Tier A citation: something addressable carrying an anchor
# fragment. The scheme and host are optional because the API reports page URLs
# site-relative (`/musings/slug/`) while an agent following AGENTS.md writes them
# absolute (`https://indianliberals.in/musings/slug/#p-abc123`). Both are the
# same citation, so the target is captured loosely here and compared by path.
CITATION_RE = re.compile(r"([^\s\)\]<>\"'`]*)#(p-[0-9a-f]{6}(?:-\d+)?)")

# Tier B attribution. The archive's own instruction to agents (AGENTS.md) is to
# write "According to Indian Liberals' summary of <work> (<year>), …", so the
# grader accepts that and the near neighbours a careful writer would produce —
# but it always requires both the attributing phrase and the word "summary",
# because "According to Indian Liberals, X" asserts the claim as fact.
ATTRIBUTION_RE = re.compile(
    r"(?:"
    r"indian\s+liberals[^.]{0,40}?summar"      # Indian Liberals' summary of …
    r"|summar\w*\s+(?:by|from|on)\s+indian\s+liberals"
    r"|indian\s+liberals[^.]{0,40}?(?:ai[- ]generated|ai)\s+summar"
    r")",
    re.IGNORECASE,
)

# Curly quotes are directional, so they pair unambiguously. Excluding the
# opening character from the class stops one span swallowing the next.
CURLY_QUOTE_RE = re.compile(r"“([^“”\n]{40,})”")
BLOCKQUOTE_RE = re.compile(r"^>\s?(.{40,})$", re.MULTILINE)

# A quoted span this long, presented as a source's own words, must be traceable
# to text the archive actually publishes. Set well above a title's length: an
# article title in quotation marks is a reference, not a quotation, and at eight
# words the check was failing answers for naming their source.
MIN_QUOTE_WORDS = 12

# A real quotation is rarely reproduced character-perfect. Writers insert "[else]",
# elide with an ellipsis, normalise punctuation, and trim. So a span counts as
# traceable when any run of this many consecutive words appears in the archive.
# An invented quotation shares no such run with anything we publish.
SHINGLE = 8


def fold(text: str) -> str:
    """
    Normalise text for comparison: strip diacritics, lowercase, and reduce
    every run of non-alphanumeric characters to a single space.

    This is the only matching rule in the eval. It makes "Manusmṛti" match
    "manusmrti" and "A. D. Shroff" match "A D Shroff", without letting a
    grader decide anything on the basis of judgement.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped.lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def folded_contains(haystack: str, needle: str) -> bool:
    """Substring test under folding. Empty needles never match."""
    n = fold(needle)
    if not n:
        return False
    return n in fold(haystack)


def word_count(text: str) -> int:
    return len(fold(text).split())


def ngrams(text: str, n: int) -> set[str]:
    words = fold(text).split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def shares_ngram(a: str, b: str, n: int = 4) -> str | None:
    """Return a shared n-gram between two strings, or None. Used for leak checks."""
    overlap = ngrams(a, n) & ngrams(b, n)
    return sorted(overlap)[0] if overlap else None


def quoted_spans(text: str) -> list[str]:
    """
    Every quotation in an answer long enough to count as a quotation.

    Straight double quotes are not directional, so they are paired by counting
    from the start of the line: split on the delimiter and keep the odd
    segments. A regex of the form `"([^"]+)"` instead matches the text *between*
    one quotation's closing mark and the next one's opening mark, which made the
    grader flag ordinary connective prose as an invented quotation.
    """
    out: list[str] = []

    for pattern in (CURLY_QUOTE_RE, BLOCKQUOTE_RE):
        for match in pattern.finditer(text):
            span = match.group(1).strip()
            if word_count(span) >= MIN_QUOTE_WORDS:
                out.append(span)

    # Pair straight quotes per line, so an unbalanced mark cannot bleed a span
    # across the rest of the answer.
    for line in text.splitlines():
        segments = line.split('"')
        if len(segments) < 3:
            continue
        for span in segments[1::2]:
            span = span.strip()
            if word_count(span) >= MIN_QUOTE_WORDS:
                out.append(span)

    return out


def url_path(target: str) -> str:
    """
    Reduce a citation target to a comparable path.

    Drops the scheme and host, the `.md` suffix of a sibling URL, any trailing
    slash, and case. So all of these name the same page:

        https://indianliberals.in/musings/slug/
        /musings/slug
        indianliberals.in/musings/slug.md
    """
    if not target:
        return ""
    cleaned = re.sub(r"^[a-z]+://", "", target.strip(), flags=re.IGNORECASE)
    # Drop a bare host prefix, with or without a scheme having been present.
    cleaned = re.sub(r"^(?:www\.)?indianliberals\.in", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\.md$", "", cleaned, flags=re.IGNORECASE)
    return "/" + cleaned.strip("/").lower() if cleaned.strip("/") else ""


def citation_targets(text: str) -> list[tuple[str, str]]:
    """Every `<target>#p-xxxxxx` pair in the text, as (path, anchor)."""
    return [(url_path(target), anchor) for target, anchor in CITATION_RE.findall(text)]


def shingles(text: str, n: int = SHINGLE) -> list[str]:
    """Every run of `n` consecutive words in the folded text."""
    words = fold(text).split()
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


_HAYSTACK: str | None = None
_TITLES: set[str] | None = None


def corpus_haystack(corpus: dict) -> str:
    """
    Every text the archive publishes, folded and concatenated.

    Corpus-wide on purpose. An answer may legitimately quote a document the
    question did not ask for, and judging a quotation only against the expected
    sources marked those as invented. What matters is whether the archive
    publishes the words anywhere, not whether we predicted which page.
    """
    global _HAYSTACK
    if _HAYSTACK is None:
        parts: list[str] = []
        for doc in corpus["tier_a"].values():
            parts.extend(p["text"] for p in doc["paragraphs"])
        for work in corpus["tier_b"].values():
            parts.extend(work.get("grounded_text") or [])
        _HAYSTACK = " ␟ ".join(fold(p) for p in parts if p)
    return _HAYSTACK


def corpus_titles(corpus: dict) -> set[str]:
    """Folded titles and article headings, so a quoted title is not a quotation."""
    global _TITLES
    if _TITLES is None:
        out: set[str] = set()
        for doc in corpus["tier_a"].values():
            out.add(fold(title_string(doc)))
        for work in corpus["tier_b"].values():
            out.add(fold(title_string(work)))
            for article in work.get("articles") or []:
                out.add(fold(article.get("heading") or ""))
        _TITLES = {t for t in out if t}
    return _TITLES


def quote_variants(span: str) -> list[str]:
    """
    The span as written, plus the forms it would take without the standard
    editorial marks.

    A writer quoting accurately still writes "accrue[s]" to fix agreement and
    elides with an ellipsis. Both interrupt every run of consecutive words, so
    without these variants an honest quotation looks invented.
    """
    out = [span]
    without_brackets = re.sub(r"\[[^\]]*\]", " ", span)
    out.append(without_brackets)          # drop the insertion entirely
    out.append(re.sub(r"[\[\]]", "", span))  # keep it, drop the brackets
    # Each side of an elision should match on its own.
    for variant in list(out):
        for piece in re.split(r"\.\.\.|…", variant):
            if word_count(piece) >= SHINGLE:
                out.append(piece)
    return out


def is_ungrounded(span: str, corpus: dict) -> bool:
    """
    Does this quoted span correspond to nothing the archive publishes?

    Cleared if it is short enough to be a reference rather than a quotation, if
    it is a title, or if any run of eight consecutive words, in any of its
    editorial variants, appears anywhere in the archive.
    """
    if word_count(span) < MIN_QUOTE_WORDS:
        return False
    folded = fold(span)
    titles = corpus_titles(corpus)
    if folded in titles or any(folded in t or t in folded for t in titles if len(t) > 20):
        return False
    haystack = corpus_haystack(corpus)
    for variant in quote_variants(span):
        if any(shingle in haystack for shingle in shingles(variant)):
            return False
    return True


def load_corpus() -> dict:
    if not CORPUS_PATH.exists():
        raise SystemExit("Missing scripts/eval/corpus.json — run build_corpus.py.")
    with CORPUS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_pool(path: Path | None = None) -> dict:
    target = path or POOL_PATH
    if not target.exists():
        raise SystemExit(f"Missing {target} — run validate_pool.py.")
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)


def doc_for(corpus: dict, key: str) -> dict | None:
    return corpus["tier_a"].get(key) or corpus["tier_b"].get(key)


def anchors_of(doc: dict) -> set[str]:
    return {p["paragraph_id"] for p in doc.get("paragraphs", [])}


def grounded_texts(corpus: dict, key: str) -> list[str]:
    """
    Every text the archive genuinely publishes for a document.

    For Tier A that is the anchored paragraphs. For Tier B it is the summary,
    the key points, and the per-article summary prose — but never source prose,
    because the archive holds none. A quotation absent from all of this did not
    come from the archive.
    """
    doc = doc_for(corpus, key)
    if not doc:
        return []
    if doc["tier"] == "A":
        return [p["text"] for p in doc["paragraphs"]]
    return doc.get("grounded_text", [])


def tool_reachable_texts(corpus: dict, key: str) -> list[str]:
    """
    The text an agent can obtain through the documented MCP tools.

    Narrower than `grounded_texts` for Tier B, and the difference is a real
    finding: `read_clean_content` refuses Tier B with "no trusted body text
    exists", and `get_work_metadata` returns only the summary and key points.
    Yet the per-article prose for 780 works is served at the `md_url` that same
    API response hands out. So some Tier B detail is published but denied by the
    tool layer, and a question needing it tests discoverability rather than
    citation discipline. Tagging which is which keeps the two apart.
    """
    doc = doc_for(corpus, key)
    if not doc:
        return []
    if doc["tier"] == "A":
        return [p["text"] for p in doc["paragraphs"]]
    # `api_key_points`, not `key_points`: the merged list includes the digests
    # that live in the markdown body, which get_work_metadata does not return.
    return [t for t in [doc.get("summary") or "", *(doc.get("api_key_points") or [])] if t]


def identifies(answer: str, doc: dict) -> bool:
    """
    Did the answer identify this document at all?

    Accepts the page URL, the slug, or the title. Titles are matched whole for
    short ones and by four-word span for long ones, so "Freedom First, April
    1986" counts as naming a work whose full title runs much longer.
    """
    url = doc.get("url") or ""
    if url and fold(url.rstrip("/")) in fold(answer):
        return True
    slug = doc.get("id") or ""
    if slug and slug.lower() in answer.lower():
        return True
    title = title_string(doc)
    folded_title = fold(title)
    if not folded_title:
        return False
    if len(folded_title.split()) <= 4:
        return folded_title in fold(answer)
    return shares_ngram(answer, title, 4) is not None


def title_string(doc: dict) -> str:
    """Flatten the multilingual title object down to its main string."""
    title = doc.get("title")
    if isinstance(title, str):
        return title
    if isinstance(title, dict):
        parts = [title.get("main") or "", title.get("subtitle") or ""]
        return " ".join(p for p in parts if p).strip()
    return ""


def author_names(doc: dict) -> list[str]:
    out: list[str] = []
    for author in doc.get("authors") or []:
        if isinstance(author, str):
            out.append(author)
        elif isinstance(author, dict) and author.get("name"):
            out.append(author["name"])
    return out
