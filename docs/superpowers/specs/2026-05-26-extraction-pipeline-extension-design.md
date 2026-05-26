# Extraction Pipeline Extension — Bake the Remaining 610 PDFs — Design Spec

**Author:** Adnan
**Date:** 2026-05-26
**Status:** locked

## 1. Goal

Bake every unbaked PDF on the external drive (`/Volumes/One Touch/Indian Liberals/PDFs-by-publisher/`) into the corpus by running the existing v1.5 extraction pipeline (`scripts/llm-extract/run_overnight.py`) against the 610 PDFs that the prior v1.5 batch (May 17) did not reach. Auto-commit and auto-push results in batches of 20 MDs so progress is durable and visible on `origin/main` without manual intervention.

**Terminal state:** roughly 900–1000 primary-works MDs in `apps/site/src/content/primary-works/`, each carrying an AI summary, 3–5 verbatim pull quotes, cross-thinker mentions, and validated metadata. The current count is 377; the target is 377 + 610 ≈ 987, modulo failures and slug collisions.

## 2. Non-goals

- **Re-baking the 335 already-baked PDFs.** They're in `data/bake-off-output/` and have working MDs. `list_unbaked_pdfs()` skips them by checking for `metadata.a.a.json` or `final.json` in each bake-off-output subdir.
- **Schema changes** to prompts, validator, or content collections. We're running the existing pipeline as-is.
- **PDF acquisition.** The drive's contents are the input; nothing else gets crawled.
- **Cleaning up the 6 honest-placeholder MDs** (the slugs without a `pdf_url` after our earlier audits). Editorial follow-up; separate scope.
- **R2 migration.** The schema's `pdf_staging_path` field anticipates this but it's a separate spec.
- **Cloud routine.** Confirmed local nohup is the right venue — the PDFs live on the external drive which isn't reachable from cloud routines.
- **Populating `pdf_url` for the new MDs.** The pipeline doesn't set this field; a separate `match-pdfs.py` re-run after the batch will discover URLs from the existing prod-mirror inventory and local backup.

## 3. Scope

Three additive code changes to one file: `scripts/llm-extract/run_overnight.py`.

1. **`committer_thread()`** — a new daemon thread that wakes every 60 seconds, checks for ≥ 20 untracked MD files in `apps/site/src/content/primary-works/`, and if found: `git add` + `git commit` + `git push origin main`. Failures are logged but never crash the pipeline.
2. **Wire the committer into `main()`** — start before the worker pool; signal stop on exit with a final flush.
3. **Commit log** — append per-batch results to `/tmp/v1.5-overnight-commits.tsv` for visibility (`tail -f`).

Unchanged: `driver.py`, `dispatcher.py`, `rasterize.py`, `validator.py`, `ledger.py`, `transliteration.py`, all `prompts/*.md`, all content collection schemas, all Astro components.

**File-size budget:** the committer addition is ~60 lines added to `run_overnight.py` (currently 414 lines). Well within budget.

## 4. Architecture

```
                   /Volumes/One Touch/Indian Liberals/PDFs-by-publisher/
                                       │
                                       │  list_unbaked_pdfs()  →  610 paths
                                       ▼
                  ┌─────── run_overnight.py (nohup background) ──────┐
                  │                                                    │
                  │   ThreadPoolExecutor(max_workers=8)                │
                  │                                                    │
                  │   Per PDF (parallel × 8):                          │
                  │      ├─ prep metadata.a                            │
                  │      ├─ prep metadata.b                            │
                  │      ├─ prep summary                               │
                  │      ├─ claude -p × 2 (parallel A + B)             │
                  │      ├─ collect A, collect B                       │
                  │      ├─ claude -p × 1 (summary)                    │
                  │      └─ collect summary  →  emit MD                │
                  │                                                    │
                  │   ┌──── NEW: Committer thread ────────────────┐   │
                  │   │   every 60s:                                │   │
                  │   │   if `git ls-files --others` has ≥ 20      │   │
                  │   │      .md files in primary-works/:           │   │
                  │   │     git add + commit + push origin main     │   │
                  │   │     log batch in commits.tsv                │   │
                  │   └──────────────────────────────────────────────┘  │
                  │                                                    │
                  │   Circuit breaker (existing): pauses workers on    │
                  │   rate-limit, auto-resumes after window.           │
                  │                                                    │
                  └────────────────────────────────────────────────────┘
                                       │
                                       ▼
                  apps/site/src/content/primary-works/<slug>.md
                  data/bake-off-output/<slug>/{metadata.a.a.json,
                                               metadata.b.b.json,
                                               summary.json}
                                       │
                                       ▼  (every 20 untracked)
                              git commit + git push origin main
```

## 5. Components in detail

### 5.1 `run_overnight.py` — new `committer_thread()` function

Add the following constants near the existing module-level constants:

```python
COMMIT_BATCH_SIZE = 20
COMMIT_POLL_INTERVAL_S = 60
PW_DIR_REL = "apps/site/src/content/primary-works"
COMMIT_LOG = Path("/tmp/v1.5-overnight-commits.tsv")
```

Add the function (after `process_pdf` and before `main`):

```python
def committer_thread(stop_event: threading.Event) -> None:
    """Wake every 60 seconds; commit + push when ≥ COMMIT_BATCH_SIZE new MDs are untracked.

    Idempotent and crash-safe: each poll independently re-discovers untracked MDs via
    `git ls-files --others`. If the committer dies mid-iteration, the next launch picks
    up where it left off.
    """
    total_committed = 0
    batch_number = 0
    while not stop_event.is_set():
        try:
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "--", PW_DIR_REL],
                capture_output=True, text=True, cwd=ROOT, check=True,
            )
            untracked = [u for u in result.stdout.strip().split("\n") if u.endswith(".md")]
            if len(untracked) >= COMMIT_BATCH_SIZE:
                batch_number += 1
                _commit_and_push(untracked, batch_number, total_committed, last_batch=False)
                total_committed += len(untracked)
        except subprocess.CalledProcessError as e:
            print(f"[committer] git error: {e}; will retry next poll", file=sys.stderr)
        except Exception as e:
            print(f"[committer] unexpected: {e}", file=sys.stderr)
        stop_event.wait(COMMIT_POLL_INTERVAL_S)

    # Final flush — commit any leftover < COMMIT_BATCH_SIZE MDs on shutdown.
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", PW_DIR_REL],
            capture_output=True, text=True, cwd=ROOT, check=True,
        )
        untracked = [u for u in result.stdout.strip().split("\n") if u.endswith(".md")]
        if untracked:
            batch_number += 1
            _commit_and_push(untracked, batch_number, total_committed, last_batch=True)
            total_committed += len(untracked)
    except Exception as e:
        print(f"[committer-final-flush] {e}", file=sys.stderr)
    print(f"[committer] exiting; total MDs committed this run: {total_committed}")


def _commit_and_push(untracked: list[str], batch_no: int, prior_total: int, *, last_batch: bool) -> None:
    subprocess.run(["git", "add", "--"] + untracked, cwd=ROOT, check=True)
    suffix = " (final flush)" if last_batch else ""
    msg = (
        f"data(primary-works): extraction batch {batch_no} — {len(untracked)} new MDs{suffix}\n\n"
        f"Running total this run: {prior_total + len(untracked)}.\n"
        f"Source: v1.5 extraction pipeline (run_overnight.py).\n"
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    push = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    push_status = "pushed" if push.returncode == 0 else f"push-failed: {push.stderr[:100].strip()}"
    with COMMIT_LOG.open("a") as f:
        f.write(f"{int(time.time())}\t{batch_no}\t{len(untracked)}\t{prior_total + len(untracked)}\t{push_status}\n")
    print(f"[committer] batch {batch_no}: {len(untracked)} MDs → {push_status}")
```

### 5.2 Wire the committer into `main()`

In `main()`, immediately before the `ThreadPoolExecutor` line:

```python
stop_event = threading.Event()
committer = threading.Thread(target=committer_thread, args=(stop_event,), daemon=True)
committer.start()
```

Wrap the existing pool loop in `try/finally`:

```python
try:
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        # ... existing dispatch + collect loop ...
finally:
    stop_event.set()
    committer.join(timeout=120)
```

This guarantees the final flush runs before the process exits, even on KeyboardInterrupt or exceptions.

### 5.3 Launch + monitoring

The existing `run_overnight.py` has `--concurrency` default = **12** (not 8 as a stray context line in this spec earlier implied). We explicitly pass `--concurrency 8` for the extension run because the v1.5 batch was tuned at 8 and we want consistent rate-limit behavior; raising to 12 only made sense in earlier debugging passes.

```bash
cd "/Users/siraj/Indian Liberals Website"
nohup .venv-extract/bin/python3 scripts/llm-extract/run_overnight.py \
  --concurrency 8 \
  > /tmp/v1.5-overnight-v2.log 2>&1 &
echo $! > /tmp/v1.5-overnight-v2.pid
```

Monitor:
```bash
tail -f /tmp/v1.5-overnight-v2.log              # overall stderr/stdout
tail -f /tmp/v1.5-overnight-progress.tsv        # per-PDF status (existing)
tail -f /tmp/v1.5-overnight-commits.tsv         # commit/push log (new)
git log --oneline origin/main..HEAD             # committed-not-pushed
```

Stop early (if needed):
```bash
kill -TERM "$(cat /tmp/v1.5-overnight-v2.pid)"  # graceful — triggers final flush
```

## 6. Data flow

```
PDF (on drive)
    │
    │  prep: rasterize first 20 non-blank pages → JPEGs
    │        + load prompts + authority subset + theme vocab
    ▼
/tmp/llm-extract-requests/<slug>-chunk0-<hash>/
    ├─ system.txt
    ├─ user.txt
    └─ page-001.jpg .. page-N.jpg
    │
    │  claude -p (3 calls: metadata.a, metadata.b, summary)
    ▼
.../response.json (in each request_dir)
    │
    │  collect: parse + validate + write canonical output
    ▼
data/bake-off-output/<slug>/
    ├─ metadata.a.a.json
    ├─ metadata.b.b.json
    └─ summary.json
    │
    │  collect (summary phase) auto-emits MD via emit-astro-md.py
    ▼
apps/site/src/content/primary-works/<slug>.md
    │
    │  every 60s: committer_thread sees ≥ 20 untracked .md
    ▼
git add + commit + push origin main
    │
    ▼
GitHub origin/main reflects progress in near-real-time
```

## 7. Failure modes & edge cases

| Case | Behavior |
|---|---|
| External drive unmounts mid-run | `prep_one()` returns `None` for affected PDFs → `process_pdf()` returns `PREP_FAILED` → logged, pipeline continues with other PDFs that were already prepped. On drive reconnect, re-launch picks up where it left off (failed PDFs are still in the unbaked set). |
| Single `claude -p` call times out (> 10 min) | Worker returns `False` → `process_pdf` returns `META_FAILED` or `SUMMARY_FAILED` → logged. The circuit breaker may trip if multiple consecutive timeouts. |
| Max plan rate-limit hits | Existing circuit breaker (`_BREAKER`) detects the pattern in stderr/stdout, pauses ALL workers via `wait_if_open()`, waits for the reset window (or backs off 1/2/4/8 minutes), resumes. |
| `git push` fails (network, auth, conflict on main) | Committer logs `push-failed: <reason>` in commits.tsv. Local commit succeeded; the next batch's push will include the prior batch's commits. If push keeps failing, local work is still safe and can be pushed manually. |
| `git commit` fails (pre-commit hook fail) | `subprocess.run(check=True)` raises `CalledProcessError`. Committer catches it, logs, retries next poll. Untracked MDs persist until commit succeeds. |
| Concurrent manual `git commit` during a run | The committer's `git add` only adds the specific MD files it discovered via `git ls-files --others`. Manual commits in parallel are safe. The 60s polling window keeps races rare. |
| Pipeline crashes (Python exception in worker) | The exception propagates to `ThreadPoolExecutor` → the future records it. The `finally` clause around the pool fires, signaling the committer to flush. Already-committed MDs are safe. Un-committed-but-emitted MDs persist as untracked → manual commit or re-launch will pick them up. |
| `kill -KILL` (no chance to flush) | Committer thread is a daemon → dies with process. Untracked MDs persist; next launch's committer picks them up on its first poll. |
| Duplicate slug — PDF stem matches existing MD | `emit-astro-md.py` overwrites silently. The emitter's own comment documents this as the intended policy ("Primary-works are 100% machine-emitted ... overwriting is the correct policy"). For this extension run, no slug collisions are expected because `list_unbaked_pdfs()` skips already-baked PDFs by stem, and the 377 existing MDs have stems derived from those same PDF filenames. If a collision happens anyway, the existing MD is overwritten in place. |
| Empty / corrupted PDF | `rasterize_chunk` returns 0 usable pages → prep aborts → `PREP_FAILED`, skip. |
| Validator rejects metadata.a/.b output (e.g., disagreement triggers tiebreak; tiebreak also fails) | `collect_one` returns `False` → `COLLECT_FAILED` → MD not emitted → no commit. |
| Subagent writes malformed JSON to response.json | Dispatcher's `parse_response` raises → recorded as failure → no MD emitted. |
| Two MDs whose slugs differ only by case (e.g., `Foo.pdf` and `foo.pdf` on macOS) | macOS HFS+/APFS is case-insensitive by default. `rglob("*.pdf")` would return both but they resolve to the same file. Confirm in smoke test. |
| Anthology / long-essay needs continuation chunks | The existing `cmd_loop` in `driver.py` handles this when invoked. `run_overnight.py` currently does chunk 0 only. **In scope to verify** — see open items. |
| `pdf_url` discovery for new MDs | Not handled by this pipeline. After the batch, re-run `match-pdfs.py` against the new MDs using the existing prod-mirror inventory + local-backup logic. |
| Build fails after a batch lands on `origin/main` | Each new MD is Zod-validated by Astro on build. A schema violation would fail CI (if configured) but not the extraction pipeline itself. Build verification is post-batch. |

## 8. Testing & validation

### 8.1 Pre-launch (smoke + checks)

**Duplicate-slug behavior is already confirmed** as silent overwrite (see §7 row "Duplicate slug" and `emit-astro-md.py` line 483 comment). No pre-launch investigation needed.

**Smoke run on 3 PDFs:**
```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/llm-extract/run_overnight.py \
  --concurrency 2 --smoke 3 \
  2>&1 | tee /tmp/v1.5-smoke.log
```
(The actual flag is `--smoke N`, not `--limit N` — `run_overnight.py` line 372.)
Expected:
- 3 PDFs run end-to-end
- 3 new MDs emitted to `apps/site/src/content/primary-works/`
- 3 dirs created in `data/bake-off-output/`
- 0 commits (below batch threshold)
- Committer thread starts, polls a few times, logs no-op
- Final flush on exit commits the 3 MDs in one batch

If smoke clean → proceed.

### 8.2 Mid-run monitoring (during the batch)

Three logs to watch:
- `/tmp/v1.5-overnight-v2.log` — overall stderr/stdout (errors, rate-limit pauses)
- `/tmp/v1.5-overnight-progress.tsv` — per-PDF: `<ts>\t<slug>\t<status>\t<note>`
- `/tmp/v1.5-overnight-commits.tsv` — per-batch: `<ts>\t<batch_no>\t<count>\t<total>\t<push_status>`

Key health checks while running:
- `git log --oneline origin/main..HEAD` — should be empty (or transient) if pushes are succeeding
- `git ls-files --others --exclude-standard -- apps/site/src/content/primary-works/ | grep '\.md$' | wc -l` — should oscillate between 0 and 20 (committer flushes when it crosses 20). Use this exact command — it matches what the committer itself queries, so the count is authoritative.
- `tail -30 /tmp/v1.5-overnight-v2.log` — look for stack traces or repeated rate-limit pauses

### 8.3 Final validation (after the run completes)

**Coverage check:**
```bash
.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
from run_overnight import list_unbaked_pdfs
print(f'unbaked remaining: {len(list_unbaked_pdfs())}')
"
```
Expected: 0 (or only PDFs that hit unrecoverable PREP/META/SUMMARY failures).

**Build check:**
```bash
cd apps/site && rm -f public/pagefind && pnpm build 2>&1 | tail -5
ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" build.log  # 0 expected
find dist -name 'index.html' | wc -l  # ~1893 expected (1283 + ~610)
```

**Spot-check 10 random new MDs:**
- Title in frontmatter matches first sentence of summary
- `needs_review` is reasonable (true for short/cut-off works, false for clean extractions)
- Pull quotes' `page` fields point to pages in the rendered set
- No "PDF could not be located" disclaimer language (that pattern was specific to the WP-DB-rebuild commit, not the AI extraction pipeline)

**Re-run earlier audit:**
```bash
# Use the inventory-cross-check + slug-vs-URL audit logic from the prior audit conversation
# (described in the spec brainstorming session, not re-implemented here)
```
Expected: no new content-vs-URL mismatches beyond what was already flagged.

**Optional follow-up:** Run `match-pdfs.py` against the new MDs to populate `pdf_url` where possible.

## 9. Stopping criteria

1. `list_unbaked_pdfs()` returns 0 (or only stuck-failing PDFs documented as known-unrecoverable).
2. Smoke test passed before the full launch.
3. Committer's final-flush ran and pushed any tail batch.
4. Build clean, page count ≈ 1893 — i.e., 1283 (current `find apps/site/dist -name 'index.html' | wc -l` baseline from the most recent clean build, pre-extension) plus the number of successful new MDs, within ~5% tolerance. If the baseline shifts before launch, recompute it.
5. Spot-check confirms 10 random new MDs are sensible.
6. Commit log shows ≤ ⌈successes/20⌉ + 1 batched commits — at full success that's ~31 ((610 / 20) ≈ 30 + 1 final flush), but realistically lower since some PDFs will hit PREP/META/SUMMARY failures.

## 10. Open items / follow-ups (separate specs)

- **(none for slug handling — already confirmed as intentional silent overwrite).**
- **`pdf_url` discovery for the new ~610 MDs** — re-run `match-pdfs.py` after the batch using the existing prod-mirror inventory + local backup. Likely lands another ~500+ URLs (most prod pages will exist for these slugs).
- **R2 migration** — long-term plan to host PDFs ourselves and replace prod URLs.
- **Editorial review of `needs_review: true` MDs** — expected to be a meaningful fraction (10–25%). Out of scope for this run.
- **Anthology continuation loop** — if any new PDF is a multi-essay anthology where chunk 0 only covered the first essay or two, the existing `cmd_loop` in `driver.py` would need to be invoked separately to summarize the rest. Verify how many such PDFs exist post-run and decide whether to extend the pipeline or accept partial coverage.
- **Tier-B disclaimer wording** in `PrimaryWorkDetail.astro` — the current "where present" hedge still works but may want polishing once the corpus stabilizes.
- **Pipeline observability** — the existing progress.tsv + commits.tsv are good for `tail -f` but lack aggregation. A small dashboard (or `gh actions`-driven summary) would help for future runs.
