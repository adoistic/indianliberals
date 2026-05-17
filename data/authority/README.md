# Authority files

Canonical IDs + aliases for the entities that appear as authors, editors,
contributors, publishers, and issuers across the Indian Liberals corpus.

The LLM extraction pipeline reads these files at every metadata call and
resolves bylines against them. Anything that doesn't match with high
confidence surfaces as `needs_human_review: true`. See the design doc
for the full mechanism:

  ~/.gstack/projects/IndianLiberalsWebsite/siraj-main-design-20260517-133733.md

## Files

| File | What it is | Who produces it |
|---|---|---|
| `thinkers.json` | Canonical thinker entries + byline_lookup map | Phase 0.1 seed (this commit); refined by Phase 0.3 clustering |
| `thinkers.raw.json` | Raw aggregated candidates with provenance | Phase 0.1 mining script (`scripts/authority/mine_sources.py`) |
| `organisations.json` | Canonical organisation entries | Hand-curated from proposal + corpus context |
| `publishers.json` | Canonical publisher entries | Hand-curated from publisher folders + commercial-publisher list |

## v1 seed counts (2026-05-17)

- **Thinkers: 199** (target ≥ 80 met)
  - `canonical` confidence: 43 — multi-source verified + proposal + WP DB + thinkers collection
  - `high` confidence: 92 — single-source extracted from content bylines (musings, opinions, interviews, ThePrint mirror)
  - `medium` confidence: 64 — single-source extracted from PDF filename patterns; some duplicates of canonical entries that Phase 0.3 will collapse
- **Organisations: 21** (target ≥ 20 met)
- **Publishers: 17** (target ≥ 15 met)

## Confidence levels — what they mean for resolution

When the metadata extraction pass resolves a byline against this file:

- **canonical**: high-trust match. If the LLM's byline normalisation hits one of these, ship without flag.
- **high**: trusted match. Same treatment — these come from real bylines in already-extracted content.
- **medium**: candidate match. Phase 0.3 Opus clustering may collapse these into existing `canonical` entries (e.g., `medium: "MR Masani"` collapses into `canonical: "Minoo Masani"`). Until then, the metadata pass should EITHER pick the canonical alias if the candidate is a known alias, OR flag `needs_human_review: true` with the candidate listed.

## Known issues that Phase 0.3 will resolve

The v1 seed has expected duplicates that the LLM clustering will collapse:

- `a-d-shroff` (canonical) and `ad-shroff` (high) — same person, will merge
- `b-r-shenoy` (canonical) and `br-shenoy` (high) — same person, will merge
- `m-r-pai` (canonical) and `mr-pai` (high) — same person, will merge
- Similar split patterns for several others where initials are written with vs without periods

The byline lookup map already handles many of these via the `also_known_as[]`
arrays seeded from the proposal. Phase 0.3 produces the final canonical
collapse.

## How the lookup works

The metadata extraction prompt receives `thinkers.json` (or a slimmer
projection of it) in its system prompt. It also receives the `byline_lookup`
map — a flat `{ normalized_byline_string: thinker_id }` lookup.

When the LLM extracts a byline like "Minoo Masani" from the title page:
1. Normalise (lowercase, strip periods + commas + extra whitespace): `"minoo masani"`
2. Look up in `byline_lookup`: → `"minoo-masani"`
3. Emit `{ thinker_id: "minoo-masani", byline_verbatim: "Minoo Masani", confidence: "high" }`

When a byline doesn't resolve (e.g., the LLM extracts "P. K. Sharma" which isn't in the file):
1. Lookup miss
2. Emit `{ thinker_id: null, byline_verbatim: "P. K. Sharma", needs_human_review: true }`
3. Editorial workflow either adds the new thinker to the authority file or merges into an existing alias

## Regenerating

```bash
python3 scripts/authority/mine_sources.py
python3 scripts/authority/build_seed.py
```

The mining script reads:
- `apps/site/src/content/thinkers/*.md` (existing thinker collection)
- `/Volumes/One Touch/Indian Liberals/sql/indianli_liberals.sql` (wp_author table)
- `apps/site/src/content/{musings,opinions,interviews,theprint-mirror}/*.md` (extracted content bylines)
- `/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/**/*.pdf` (filename heuristics)

Plus the hand-curated proposal-figures list inside the script.
