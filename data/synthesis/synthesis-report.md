# Day 6 Synthesis Report
**Date:** 2026-05-17  
**Source:** 40 baked PDFs (Wave 1 + 9-PDF benchmark + Wave 2)

## Aggregations emitted
- `thinker-occurrences.json`: **50 thinkers** with at least one corpus occurrence
- `theme-occurrences.json`: **202 themes** engaged across the corpus
- `graph-edges/cites.json`: **120 edges** (work → thinker body-text citations)
- `graph-edges/engages.json`: **372 edges** (work → theme)
- `graph-edges/contributor.json`: **34 edges** (work → author/editor/contributor)

## Top 25 thinkers by corpus occurrence

| Rank | thinker_id | Canonical name | Occurrences | Role distribution |
|---:|---|---|---:|---|
| 1 | `jawaharlal-nehru` | Jawaharlal Nehru | 31 | body_text_mention:31 |
| 2 | `mahatma-gandhi` | Mahatma Gandhi | 12 | body_text_mention:12 |
| 3 | `karl-marx` | Karl Marx | 8 | body_text_mention:8 |
| 4 | `sharad-joshi` | Sharad Joshi | 7 | author:6, body_text_mention:1 |
| 5 | `c-rajagopalachari` | C. Rajagopalachari | 7 | body_text_mention:5, foreword:1, author:1 |
| 6 | `s-v-raju` | S. V. Raju | 7 | other:2, author:2, body_text_mention:1, editor:1, introduction:1 |
| 7 | `indira-gandhi` | Indira Gandhi | 6 | body_text_mention:6 |
| 8 | `minoo-masani` | Minoo Masani | 6 | body_text_mention:5, author:1 |
| 9 | `a-d-shroff` | A. D. Shroff | 5 | body_text_mention:5 |
| 10 | `jayaprakash-narayan` | Jayaprakash Narayan | 5 | body_text_mention:5 |
| 11 | `bhimrao-ambedkar` | B. R. Ambedkar | 4 | body_text_mention:4 |
| 12 | `m-n-roy` | M. N. Roy | 4 | body_text_mention:4 |
| 13 | `gopal-krishna-gokhale` | Gopal Krishna Gokhale | 4 | body_text_mention:4 |
| 14 | `ma-venkata-rao` | MA Venkata Rao | 4 | author:4 |
| 15 | `nani-palkhivala` | Nani Palkhivala | 3 | body_text_mention:2, author:1 |
| 16 | `b-r-shenoy` | B. R. Shenoy | 3 | body_text_mention:2, author:1 |
| 17 | `ishwar-chandra-vidyasagar` | Ishwar Chandra Vidyasagar | 2 | author:1, body_text_mention:1 |
| 18 | `friedrich-hayek` | Friedrich Hayek | 2 | body_text_mention:2 |
| 19 | `s-p-sathe` | S. P. Sathe | 2 | author:1, body_text_mention:1 |
| 20 | `a-ranganathan` | A Ranganathan | 2 | body_text_mention:2 |
| 21 | `russi-mody` | Russi Mody | 1 | author:1 |
| 22 | `thomas-robert-malthus` | Thomas Robert Malthus | 1 | body_text_mention:1 |
| 23 | `ma-sreenivasan` | MA Sreenivasan | 1 | author:1 |
| 24 | `hp-ranina` | HP Ranina | 1 | author:1 |
| 25 | `peter-bauer` | Peter Bauer | 1 | body_text_mention:1 |

## Top 25 themes by corpus engagement

| Rank | Theme | Works engaging |
|---:|---|---:|
| 1 | `economic-policy` | 10 |
| 2 | `free-markets` | 9 |
| 3 | `civil-liberties` | 9 |
| 4 | `democracy` | 9 |
| 5 | `agriculture` | 8 |
| 6 | `fiscal-policy` | 8 |
| 7 | `taxation` | 8 |
| 8 | `civil-society` | 8 |
| 9 | `political-economy` | 8 |
| 10 | `planning-critique` | 7 |
| 11 | `public-finance` | 6 |
| 12 | `public-sector-critique` | 6 |
| 13 | `rule-of-law` | 6 |
| 14 | `liberalism` | 6 |
| 15 | `regulatory-state-critique` | 5 |
| 16 | `social-reform` | 5 |
| 17 | `foreign-policy` | 5 |
| 18 | `federalism` | 4 |
| 19 | `public-sector` | 4 |
| 20 | `economic-freedom` | 4 |
| 21 | `farmers-rights` | 4 |
| 22 | `governance` | 4 |
| 23 | `economic-reform` | 4 |
| 24 | `socialism-debate` | 3 |
| 25 | `press-freedom` | 3 |

## Network density signals

- **Authority utilization:** 50 of 426 thinkers (11%) have at least one occurrence in the baked corpus.
- **Mean occurrences per thinker:** 3.1
- **Works baked:** 40 of ~944 in the full corpus (4%)

### Occurrences by tradition tier

- `international_influence`: 11 thinkers
- `classical_liberal`: 10 thinkers
- `nationalist_liberal`: 10 thinkers
- `(unspecified)`: 7 thinkers
- `reformer`: 5 thinkers
- `contemporary_liberal`: 5 thinkers
- `social_reformer`: 2 thinkers

## Theme distribution by work_type

| Work type | # works baked |
|---|---:|
| `book` | 11 |
| `periodical_issue` | 9 |
| `edited_volume` | 5 |
| `occasional_paper` | 5 |
| `speech` | 4 |
| `essay` | 3 |
| `pamphlet` | 3 |

## Language distribution

| Language | # works baked |
|---|---:|
| `en` | 28 |
| `mr` | 5 |
| `hi` | 3 |
| `bn` | 2 |
| `gu` | 2 |

## Authority utilization gaps

**377 of 426 thinkers** in the authority file have ZERO occurrences in the baked corpus so far. This is expected: only 40 of ~944 PDFs are baked. Examples of canonical-tier thinkers not yet attested in any baked PDF (sampled):

- `abraham-lincoln`: Abraham Lincoln
- `achyut-patwardhan`: Achyut Patwardhan
- `a-d-shroff`: AD Shroff
- `adam-smith`: Adam Smith
- `alexis-de-tocqueville`: Alexis de Tocqueville
- `amartya-sen`: Amartya Sen
- `arun-shourie`: Arun Shourie
- `ashok-desai`: Ashok V. Desai
- `bk-nehru`: B. K. Nehru
- `bal-gangadhar-tilak`: Bal Gangadhar Tilak
- `begum-rokeya`: Begum Rokeya
- `bibek-debroy`: Bibek Debroy
- `b-r-shenoy`: BR Shenoy
- `c-rangarajan`: C. Rangarajan
- `chintaman-deshmukh`: C. D. Deshmukh

## Notes for downstream consumers

1. **Edges schema gap**: the v1.x `graphEdges` schema (`content.config.ts:708`) has `cites`, `responds_to`, `builds_on`, `influenced_by`, etc., but no explicit `author_of` / `editor_of` / `contributor_of` edge types. Until the schema extends, `graph-edges/contributor.json` uses `cites` with `context: <role>` as an interim encoding. **TODO**: propose schema extension.
2. **Re-baking impact**: each future bake of a not-yet-baked PDF will append to these aggregations. The script is idempotent — re-run after every batch.
3. **Cluster collapse pending**: the v1.5 authority has a few duplicate-pair entries flagged by the curator (rk-amin / r-k-amin, dm-kulkarni / d-m-kulkarni, bk-nehru / bk-nehru, ashok-desai / ashok-desai). Editorial pass needed before downstream UI shows split occurrence counts.
4. **Pull quotes not aggregated here** — they're per-work editorial content, indexed at the per-work `summary.json` level. A separate pass can produce a `data/synthesis/pull-quotes-index.json` for shareable-quote UIs.
