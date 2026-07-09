# Periodicals status — CCS round-2 feedback #8, #9, #10

Date: 2026-07-09.

## What changed

- **Series-first layout (#10).** `/periodicals/` no longer dumps every issue flat.
  It now shows one **card per run** (cover + name + issue count + span + blurb), each
  linking to a dedicated `/periodicals/<series>/` page that lists that run's issues.
  Grouping + metadata moved to `apps/site/src/lib/periodicals.ts` (shared by both pages).
- **Robust grouping (#8).** Series detection is now keyed first on the explicit
  `publication.issuer_id` / `publisher_id` fields, with the old title/slug regex as a
  fallback. The Indian Libertarian "only 4 showing" symptom is gone: **all 160 issues**
  now group under one run. (The bulk were ingested after CCS's review; the grouping was
  the remaining risk, now hardened against title variance.)

## Series now live

| Run | Issues | Span |
|---|---|---|
| The Indian Libertarian | 160 | 1957–1973 |
| Khoj | 24 | 2005–2010 |
| Shetkari Sanghatak | 53 | 1991–1995 |
| Liberal Times | 2 | 1995 |
| **Freedom First** (new) | 1 | 1995 |
| **The Liberal Position** / Indian Liberal Group (new) | 2 | 2001–2002 |

Total: 242 issues, 6 runs. The "Other" bucket is now empty.

## #9 — the three requested runs

- **Indian Liberal Group** → **added.** Its newsletter *The Liberal Position* (2 issues,
  `issuer_id: indian-liberal-group`) now has its own run.
- **Freedom First** → **added** as a run (1 issue in the corpus so far,
  `issuer_id: freedom-first`). This is the same run targeted by feedback **#7** (upload all
  552 pieces); the series now exists so that bulk ingestion lands straight into it.
- **Forum for Free Enterprise** → **GAP.** No `periodical_issue` in the corpus has Forum
  for Free Enterprise as issuer/publisher. FoFE's output in the archive is *booklets /
  pamphlets* (other work types), not a periodical run. If CCS wants a FoFE run, the scanned
  booklet series needs ingesting from the source drive.
- **Swatantra Party** → **GAP.** Likewise no Swatantra `periodical_issue` exists. The
  Swatantra-aligned journal *Swarajya* appears only as a couple of collected-writings
  volumes, not an issue run. Needs source scans to stand up as a periodical run.

## To finish #9

Mount the source drive and confirm whether scanned runs exist for **Forum for Free
Enterprise** and **Swatantra Party / Swarajya**. If they do, ingest as `periodical_issue`
primary-works with `publication.issuer_id` set to the org id and the series will register
automatically (add a blurb to `SERIES_META` in `lib/periodicals.ts`). If they don't, these
two remain organisation pages only.
