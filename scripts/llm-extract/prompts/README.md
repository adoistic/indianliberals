# Extraction prompts

Versioned prompt files that the dispatcher loads at runtime. Each file is
a single Markdown document with three sections delimited by HR rules:

```
# SYSTEM
...the system message...

---

# USER_TEMPLATE
...the user message with {{ }} substitutions for runtime values...

---

# SCHEMA_EXAMPLE
...one worked example showing the exact JSON output expected.
   The dispatcher does NOT include this in the request; it lives here so
   developers can read what "good output" looks like.
```

## Files

| File | Used by | Purpose |
|---|---|---|
| `byline-sweep.md` | Phase 0.2 (Sonnet) | Minimal byline + title + year extraction from page 1 of every PDF. Feeds the authority-file clustering pass. |
| `metadata.a.md` | Phase 1 (Sonnet, self-consistency run A) | Full metadata extraction from chunk 1. Framed as "archival cataloguer". |
| `metadata.b.md` | Phase 1 (Sonnet, self-consistency run B) | Same field set as `.a`. Framed as "library curator", examples reordered. Used for self-consistency comparison. |
| `metadata-tiebreak.md` | Phase 1 (Opus) | Tie-breaker when A and B disagree on high-stakes fields. |
| `summary.md` | Phase 2 (Sonnet) | Summary + pull quotes + cross-thinker mentions per chunk. |
| `synthesis-*.md` | Phase 4 (Opus) | Various synthesis-layer passes. Added after bake-off. |

## Self-consistency comparison (M3 in the design doc)

Both metadata variants must produce the EXACT SAME JSON SCHEMA. Phase 1
runs both, compares the high-stakes fields:

- `title.main` — case-folded + whitespace-collapsed string match
- `publisher_verbatim` — same
- `byline_verbatim` for each author/editor — same
- `year` — integer match
- `authors[].thinker_id` — set equality (order-independent)
- `work_type` — enum match

Disagreement on any high-stakes field → `metadata-tiebreak.md` is called with
both A and B outputs in the context. Opus's output is canonical for the
disagreeing field.

## Versioning

The `prompt_version` field in the `ai` provenance object on every extracted
entry records which prompt version was used. When a prompt file is changed,
bump its version in the front-matter (line 1 of each file: `<!-- v1.0 -->`).
The dispatcher passes the version to the ledger so we can diff outputs
across prompt revisions later.

## Substitutions

The dispatcher resolves these placeholders in `USER_TEMPLATE` at runtime:

- `{{ PDF_NAME }}` — basename of the PDF
- `{{ PUBLISHER_FOLDER }}` — the publisher folder it came from (a weak signal — don't rely on it for ground truth)
- `{{ N_PAGES }}` — how many images are attached
- `{{ PAGE_NUMBERS }}` — the 1-indexed PDF page numbers of those images (e.g., "[1, 2, 3, 4, 5, 6, 8, 9, 10]" — non-contiguous when blanks were skipped)
- `{{ TOTAL_PDF_PAGES }}` — total page count of the PDF
- `{{ AUTHORITY_SUBSET }}` — a JSON blob of relevant thinkers/orgs/publishers (the dispatcher selects a subset by language + publisher folder hint to keep the prompt small)
- `{{ WORK_TYPE_TAXONOMY }}` — the 10-value enum + the `purpose` qualifier list with one-line definitions
- `{{ THEME_VOCABULARY }}` — the controlled theme list

Images are attached separately (not in the template).
