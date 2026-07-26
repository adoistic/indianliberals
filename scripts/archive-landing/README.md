# archive.indianliberals.in landing page

The bucket's front door. `archive.indianliberals.in` is an R2 custom domain, so
it serves objects by key — a visitor hitting the root previously got a bare 404.
These two objects fix that:

| local file   | bucket key       | content-type              |
|--------------|------------------|---------------------------|
| `index.html` | `index.html`     | `text/html; charset=utf-8`|
| `archive.jpg`| `og/archive.jpg` | `image/jpeg`              |

Upload:

```sh
npx wrangler r2 object put indianliberals-archive/index.html \
  --file scripts/archive-landing/index.html \
  --content-type "text/html; charset=utf-8" --remote

npx wrangler r2 object put indianliberals-archive/og/archive.jpg \
  --file scripts/archive-landing/archive.jpg \
  --content-type "image/jpeg" --remote
```

## Caveat: R2 custom domains and the root path

R2 has no index-document resolution. `GET /` maps to the empty key, so uploading
`index.html` makes `https://archive.indianliberals.in/index.html` work but may
leave `/` returning 404. If it does, the fix is a small Worker routed on the
hostname that rewrites `/` to `index.html` and passes everything else through to
the bucket. Verify after upload before assuming the root works.

## The numbers

Every figure is measured, not estimated — regenerate rather than hand-edit:

- 1,575 works, 36,650 pages: counted from `primary-works` frontmatter
  (`physical.pages_total`, 1,462 records carry it; median 16).
- 3.5 GB / 1,457 PDFs: summed from live `content-length` headers on every
  distinct `pdf_url`. Covers add 57.6 MB across 1,456 files.
- Decade histogram, languages, top authors, largest runs: counted from
  `publication.year`, `language`, `authors[]`, `publication.publisher_id`.

The page is a single self-contained file — fonts are system stacks (Georgia /
system-ui / ui-monospace) and the crane mark is an inlined data URI, so it has
no external requests and cannot break from a CDN or font host going away.
