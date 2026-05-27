# Content readiness pass 1 — Streams A/B/C/D findings

**Date:** 2026-05-27
**Audit-time snapshot:** `ae76978`
**Pre-extension baseline:** `b6be9fe`
**Scope:** the **99** primary-work MDs added between `b6be9fe` and the audit-time snapshot, plus a corpus-wide thinker-quote sweep across all **480** thinker files.

## TL;DR

- **Stream A (PDF apply):** **64** high-confidence `pdf_url` rows applied via `data/pdf-link-manifest.tsv`. 2 candidates from the matcher were surgically reverted before commit because the title-fuzzy heuristic had picked the wrong PDFs (see Follow-ups #1). Commit `1ba7bb8`.
- **Stream B (slug resolution):** **51 / 51** thinker slugs referenced in the new MDs' `related_thinkers` resolve to existing thinker files. **Zero missing.** No new thinker stubs required.
- **Stream C (cross-ref drift):** **73 / 99** new MDs have at least one slug↔prose discrepancy. **98** slugs are listed in `related_thinkers` but their canonical name does not appear in the summary/key_points; **63** names appear in the prose without a corresponding slug. Editorial cleanup, not a blocker.
- **Stream D (inbound quotes):** **204 / 480** thinker files (~42%) have at least one inbound pull-quote attribution; **276** (~58%) have none. Strong positive: **all 28 `core` thinkers have quote coverage.** The headline 58% gap is largely an artifact of the NER pass not having run on the new batch — expect it to shrink sharply after the post-batch NER run.

---

## Stream A — PDF URL backfill

Source manifest: `data/pdf-link-manifest.tsv` (produced by `scripts/data-ingestion/match-pdfs.py`).

- High-confidence rows applied to MDs: **64**
- Surgically reverted before commit (matcher false-positives): **2**
  - `property-rights-k-subba-rao-dec10-1968` — matcher pointed at the wrong PDF on title-fuzzy alone.
  - `role-of-free-enterprises-by-sn-haji-october-2-1956` — same class of false-positive.
- `skip-existing` (already had a `pdf_url`): **232**
- Commit: `1ba7bb8` — `data(primary-works): apply 64 high-confidence pdf_urls from prod reconciliation`

Full apply log: `/tmp/v1.5-readiness-apply.log`.

---

## Stream B — slug resolution for new MDs

Live re-verification at snapshot `ae76978`:

- New primary-work MDs since `b6be9fe`: **99**
- Unique thinker slugs in their `related_thinkers`: **51**
- Resolved to an existing `apps/site/src/content/thinkers/<slug>.md`: **51**
- Missing: **0**

The previous brainstorming-time figure of "53 / 53" was stale; the current corpus has all 51 referenced slugs covered. **No new thinker stubs required.**

(Note: the plan's Step 4.1.1b shell loop has a word-splitting quirk under zsh that under-counts existence checks. The numbers above were produced via a `while IFS= read -r` re-run.)

---

## Stream C — cross-reference drift in new MDs

Audit: `scripts/data-ingestion/audit-cross-refs.py` against the 99 new MDs.

- New MDs scanned: **99**
- Thinker index size: **480**
- MDs with at least one discrepancy: **73**
- `slugs-not-in-prose` (slug listed in `related_thinkers`, canonical name not found in summary/key_points): **98** total across **58** MDs
- `names-not-in-slugs` (canonical name appears in prose but the slug is missing from `related_thinkers`): **63** total across **47** MDs

### Representative discrepancies

```
--- giving-is-receiving-mrs-meera-shenoy ---
Slugs in related_thinkers but not mentioned in prose:
  - b-r-shenoy (canonical name "B. R. Shenoy" not found in summary/key_points)
Names in prose but not in related_thinkers:
  - "Sunil S. Bhandare" appears in summary/key_points; slug missing from related_thinkers

--- golden-jubilee-1956-2006 ---
Slugs in related_thinkers but not mentioned in prose:
  - a-d-shroff, ma-sreenivasan, m-r-pai, milton-friedman, peter-bauer
Names in prose but not in related_thinkers:
  - "M.A. Master"

--- grave-dangers-of-state-trading-in-foodgrains-by-ajit-prasad-jain-november-2-1959 ---
Slugs in related_thinkers but not mentioned in prose:
  - jawaharlal-nehru, karl-marx
Names in prose but not in related_thinkers:
  - "Ajit Prasad Jain"

--- growthmanship-fact-or-fallacy-colin-clark-jul11-1965 ---
Slugs in related_thinkers but not mentioned in prose:
  - adam-smith
Names in prose but not in related_thinkers:
  - "A. D. Shroff", "Colin Clark"

--- on-socialism-and-bank-nationalisation-dr-r-c-cooper-... ---
Slugs in related_thinkers but not mentioned in prose:
  - warren-hastings
Names in prose but not in related_thinkers:
  - "B. R. Shenoy", "Indira Gandhi", "Mahatma Gandhi", "Dr. R. C. Cooper"
...
```

The dominant pattern is the extractor stuffing `related_thinkers` with canonical-name slugs (Nehru, Marx, Adam Smith, A. D. Shroff…) even when the prose doesn't explicitly name them, while real first-mention authors and quoted figures (e.g. "Ajit Prasad Jain", "Colin Clark") get dropped because they're not in the canonical-name dictionary. Editorial pass.

Full log: `/tmp/v1.5-readiness-stream-c.log` (421 lines).

---

## Stream D — thinkers without inbound pull-quote attribution

Audit: `scripts/data-ingestion/audit-thinkers-without-quotes.py` against all 480 thinker files, joined against `pullQuotes` collected from `data/synthesis/ner-mentions-batch-*.jsonl`.

- Total thinker files: **480**
- Thinkers with ≥1 inbound quote: **204**
- Thinkers with 0 inbound quotes: **276** (~**58%**)

### Breakdown by `canon_status`

| canon_status   | with quotes | without quotes |
| -------------- | ----------- | -------------- |
| `core`         | **28**      | **0**          |
| `referenced`   | 84          | 127            |
| `extended`     | 80          | 87             |
| `unclassified` | 12          | 62             |

**Strong positive: every `core` thinker has at least one inbound quote.** That's the floor we wanted.

The 127 `referenced` thinkers without quotes is the most actionable cohort — these are second-tier figures the editorial team has chosen to surface, and a missing quote is a real gap once the NER pass catches up.

### Top 20 of the 127 `referenced` thinkers without quotes

```
a-c-chhatrapati       (A. C. Chhatrapati)
a-n-agarwala          (A. N. Agarwala)
a-s-ganguly           (A. S. Ganguly)
abhay-pethe           (Abhay Pethe)
abhaya-prasad-hota    (Abhaya Prasad Hota)
adi-godrej            (Adi Godrej)
ajit-narde            (Ajit Narde)
ak-purwar             (AK Purwar)
amitabh-kant          (Amitabh Kant)
amul-desai            (Amul Desai)
anand-sinha           (Anand Sinha)
anant-umrikar         (Anant Umrikar)
anu-aga               (Anu Aga)
arvind-deshpande      (Arvind Deshpande)
arvind-lalbhai        (Arvind Lalbhai)
ashima-goyal          (Ashima Goyal)
azim-premji           (Azim Premji)
azizun-nisa           (Azizun Nisa)
b-s-mahajan           (B. S. Mahajan)
bhaskar-g-kakatkar    (Bhaskar G. Kakatkar)
...
```

(Full list of 127 in the log.)

**Caveat:** ~58% of the corpus lacks any `thinker_mentions` because the NER pipeline hasn't been run on the recent extraction-pipeline output. The headline gap will drop sharply after the post-batch NER run — see Follow-ups #3.

Full log: `/tmp/v1.5-readiness-stream-d.log` (147 lines).

---

## Follow-ups

1. **`match-pdfs.py` false-positives.** The title-fuzzy heuristic can return high-confidence rows that point at the wrong PDF (2 caught and skipped this pass — `property-rights-k-subba-rao-dec10-1968`, `role-of-free-enterprises-by-sn-haji-october-2-1956`). Tighten with a stricter author-token + date-token check before promoting any row to high-confidence.
2. **Pipeline silently drops `pdf_url` when overwriting `bio_source: filename-attested-stub` MDs.** The runner's committer uses `git ls-files --others` which only sees untracked files — modified-but-tracked stubs are skipped. 2 MDs were re-emitted manually this session (commit `c3e4af1`). At least 1 filename-attested stub remains in the corpus and will need another manual flush when the pipeline processes its PDF. Suggested fix: have the committer scan for modified tracked files in `primary-works/` whose `bio_source` was previously `filename-attested-stub`.
3. **NER pass on the new MDs to populate `thinker_mentions`.** The corpus-wide 58% thinker-quote gap will drop sharply once NER runs against the post-batch primary-works output. This is the single highest-leverage item.
4. **Editorial review of medium-confidence `pdf_url` candidates** in `data/pdf-link-manifest.tsv` (the rows below the high-confidence cutoff that were not auto-applied in Stream A).
5. **Editorial review of Stream C discrepancies** — particularly the `names-not-in-slugs` cohort (63 across 47 MDs), where the extractor missed first-mention authors and quoted figures.
6. **`audit-thinkers-without-quotes.py` taxonomy mismatch.** The script references `canon_status: canonical` per the original spec, but the live corpus uses `core / referenced / extended / unclassified`. The script's `Canonical thinkers with zero quotes` section therefore always prints `(none)` and is dead. Either patch the script's `CANON_PRIORITY` + section labels to match the real taxonomy, or remove the section and rely on the breakdown table.

---

## Index of artefacts

| Artefact                    | Location                                                                                   |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| Stream A apply log          | `/tmp/v1.5-readiness-apply.log`                                                            |
| Stream A apply script       | `scripts/data-ingestion/apply-pdf-urls.py`                                                 |
| Stream A manifest           | `data/pdf-link-manifest.tsv`                                                               |
| Stream C script             | `scripts/data-ingestion/audit-cross-refs.py`                                               |
| Stream C log                | `/tmp/v1.5-readiness-stream-c.log`                                                         |
| Stream D script             | `scripts/data-ingestion/audit-thinkers-without-quotes.py`                                  |
| Stream D log                | `/tmp/v1.5-readiness-stream-d.log`                                                         |
| Commit (Stream A)           | `1ba7bb8`                                                                                  |
| Commit (Stream A re-emit)   | `c3e4af1`                                                                                  |
| Commit (Stream C script)    | `73f2574`                                                                                  |
| Commit (Stream D script)    | `ae76978`                                                                                  |
