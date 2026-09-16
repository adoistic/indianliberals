# Full-text search index

The `/search/` page runs client-side [Pagefind](https://pagefind.app) against a
static index of the **full text of every archive PDF**, hosted on R2 under the
`search/` prefix and served from `https://archive.indianliberals.in/search/`.
This is a second, independent index; the site-build Pagefind index that powers
the header quick search is untouched.

Costs nothing to run: static files, R2 egress is free, and a query fetches only
the few-KB fragments it needs.

## Rebuild (after ingesting new works, or re-OCR'ing old ones)

```sh
# 1. Frontmatter of every listed work with a pdf_url -> works_meta.json
python3 scripts/fulltext/export-works-meta.py works_meta.json

# 2. Per-page text of every PDF -> fulltext.jsonl (~100 MB, keep out of git).
#    A gzipped copy of the current corpus lives at
#    https://archive.indianliberals.in/search/corpus.jsonl.gz - download and
#    gunzip it, then extract text for NEW works only and append lines
#    ({"key": "<r2 key>", "pages": ["page text", ...]}, one JSON per line;
#    PyMuPDF page.get_text("text") per page). Re-upload the refreshed
#    corpus.jsonl.gz alongside the rebuilt bundle.

# 3. Build the Pagefind bundle
node scripts/fulltext/build-index.mjs works_meta.json fulltext.jsonl search_bundle

# 4. Upload to R2. Shards first, entrypoints only if every shard landed;
#    resumable via uploaded_search.tsv in the working directory.
scripts/fulltext/upload_search.sh search_bundle
```

Notes that matter:

- `upload_search.sh` uploads in TWO PHASES and that is not cosmetic. The
  `/search/` page was degraded for about thirty minutes once because an ad-hoc
  uploader went in directory order: a `pkill` killed the xargs doing the shards,
  the parent script carried on, and the entrypoints went up while 1,436
  fragment and index shards were missing. A fresh entrypoint naming absent
  shards is worse than a stale one naming the old bundle, because the old
  bundle still serves. If any shard fails the script exits 2 and never touches
  the entrypoints. It lives in the repo now; the previous version was lost with
  a wiped scratchpad.

- `build-index.mjs` forces a single language shard (`forceLanguage: "en"`).
  Without it Pagefind shards per language and the client only searches the
  shard matching the page's `<html lang>`, so Devanagari/Bengali/Gujarati
  queries silently return nothing. Indic text is whitespace-tokenized either
  way; do not remove this.
- The archive-root Worker (apps/archive-root) adds `access-control-allow-origin: *`
  (the site imports the bundle cross-origin) and keeps `search/` entrypoints at
  `max-age=300` while the content-hashed `search/fragment/` and `search/index/`
  files stay immutable. Stale entrypoints resolve within 5 minutes of a rebuild.
- Records carry meta (title, cover, byline, year, type, pdf, pages) and filters
  (type, language, decade, collection, theme) so the /search/ page needs no
  build-time knowledge of the corpus.
