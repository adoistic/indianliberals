# Extraction Pipeline Extension — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auto-commit/auto-push committer thread to `scripts/llm-extract/run_overnight.py` so the existing v1.5 extraction pipeline can autonomously process the remaining 610 unbaked PDFs on the external drive, landing batches of 20 MDs on `origin/main` as they complete.

**Architecture:** Three additive changes to one file (`run_overnight.py`). A new daemon `committer_thread` polls `git ls-files --others` every 60 seconds; when it finds ≥20 untracked `.md` files under `apps/site/src/content/primary-works/`, it stages + commits + pushes. The committer is wired into `main()` via `try/finally` to guarantee a final-flush commit on shutdown. Two helper functions (`_parse_untracked_mds`, `_build_commit_message`) are pure-logic and TDD-tested; the I/O portions are smoke-tested via a 3-PDF dry run before the full batch.

**Tech Stack:** Python 3 (existing `.venv-extract`), `subprocess` (stdlib), `threading` (stdlib), `git`, `claude` CLI (Max plan), the existing extraction pipeline (`driver.py`, `dispatcher.py`, `rasterize.py`, `validator.py`).

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `scripts/llm-extract/run_overnight.py` | MODIFY | Add committer thread + helpers + wire into main(). Currently 414 lines; final ~480. |
| `scripts/llm-extract/tests/test_committer_helpers.py` | CREATE | Unit tests for pure-logic helpers (`_parse_untracked_mds`, `_build_commit_message`). |
| `/tmp/v1.5-overnight-v2.log` | RUNTIME | Pipeline stdout/stderr (created by nohup; not in repo). |
| `/tmp/v1.5-overnight-progress.tsv` | RUNTIME | Per-PDF status log (existing; not in repo). |
| `/tmp/v1.5-overnight-commits.tsv` | RUNTIME | NEW per-batch commit log. |
| `apps/site/src/content/primary-works/*.md` | RUNTIME WRITE | ~610 new MDs emitted by `driver.py collect`. Committed in batches of 20. |
| `data/bake-off-output/<slug>/{metadata.a.a.json,metadata.b.b.json,summary.json}` | RUNTIME WRITE | Per-PDF bake artifacts. Already gitignored (we'll verify). |

**File-size budget:** Total new code ~80 lines (committer + 2 helpers + tests). `run_overnight.py` grows from 414 → ~480 lines. Test file ~100 lines. Well under any reasonable limit.

---

## Conventions to honour

- **Python venv:** all script runs use `.venv-extract/bin/python3 <script>`. Always.
- **Test runs:** `.venv-extract/bin/python3 -m pytest scripts/llm-extract/tests/test_committer_helpers.py -v`.
- **Commit messages:** `feat(pipeline):` for the committer additions; the runner's auto-commits use `data(primary-works):` (set inside `_build_commit_message`).
- **No `Co-Authored-By` trailer** unless Adnan explicitly asks.
- **Don't push to origin from this plan's commits.** The runner will push autonomously once launched; Adnan reviews the runner's commits live on GitHub as they land.
- **External drive must be mounted at `/Volumes/One Touch/`** throughout the smoke test + full run. The drive auto-mounts on connect; if it disconnects mid-run, expect `PREP_FAILED` rows in the progress log until reconnect.

---

## Pre-work baseline (run once before Chunk 1)

- [ ] **Step 0.1: Confirm external drive + venv + pipeline state**

```bash
cd "/Users/siraj/Indian Liberals Website"

# Drive mounted?
ls "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher" | head -3
# Expected: bengali / forum-of-free-enterprise / gujarati ... (12 publishers)

# Venv intact?
.venv-extract/bin/python3 --version

# Pipeline imports cleanly?
.venv-extract/bin/python3 -c "
import sys
sys.path.insert(0, 'scripts/llm-extract')
import run_overnight
from run_overnight import list_unbaked_pdfs, PDFS_ROOT, BAKE_DIR
print(f'PDFS_ROOT: {PDFS_ROOT}')
print(f'BAKE_DIR: {BAKE_DIR}')
print(f'unbaked: {len(list_unbaked_pdfs())}')
"
# Expected: 610 unbaked

# Baseline MD count + build sanity
ls apps/site/src/content/primary-works/*.md | wc -l
# Expected: 377

cd apps/site
find dist -name 'index.html' | wc -l 2>/dev/null
# Expected: 1283 (last known clean build)
```

- [ ] **Step 0.2: Confirm `.gitignore` covers the bake artifacts**

```bash
cd "/Users/siraj/Indian Liberals Website"
git check-ignore data/bake-off-output/test-slug/foo.json
# Expected: data/bake-off-output/test-slug/foo.json (ignored)
# If NOT ignored, the runner will pollute the diff. Need to add to .gitignore before Chunk 1.
```

- [ ] **Step 0.3: Capture pre-work SHA**

```bash
git rev-parse --short HEAD
# Record this for the final review diff range.
```

---

## Chunk 1: Pure-logic helpers (TDD)

Goal: TDD-build two pure functions that the committer thread will use. No I/O, no `git`, no threading. Fast unit tests.

### Task 1.1: Create test file + scaffolding

**Files:**
- Create: `scripts/llm-extract/tests/test_committer_helpers.py`

(No `__init__.py` needed — pytest is invoked with the test file path directly, bypassing package discovery.)

- [ ] **Step 1.1.1: Check tests/ dir exists**

```bash
cd "/Users/siraj/Indian Liberals Website"
ls scripts/llm-extract/tests/ 2>&1
# Expected: existing test_transliteration.py
# If the dir doesn't exist:
mkdir -p scripts/llm-extract/tests
```

- [ ] **Step 1.1.2: Create the test file skeleton**

Create `scripts/llm-extract/tests/test_committer_helpers.py` with:

```python
"""Tests for the committer-thread pure-logic helpers in run_overnight.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Load run_overnight.py as a module so we can access internal helpers.
spec = importlib.util.spec_from_file_location(
    "run_overnight",
    str(Path(__file__).resolve().parents[1] / "run_overnight.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
```

- [ ] **Step 1.1.3: Verify the import works**

```bash
.venv-extract/bin/python3 -m pytest scripts/llm-extract/tests/test_committer_helpers.py -v
# Expected: "no tests collected" (file exists but has no test functions yet)
# NOT expected: ImportError. If import fails, run_overnight.py has a top-level side effect blocking import.
# If that happens, STOP and report — the test approach needs adjusting.
```

### Task 1.2: `_parse_untracked_mds()` (TDD)

**Files:**
- Modify: `scripts/llm-extract/tests/test_committer_helpers.py`
- Modify: `scripts/llm-extract/run_overnight.py`

This helper parses the output of `git ls-files --others --exclude-standard -- <dir>` and returns only the `.md` files. Pure-logic so we can test it without invoking git.

- [ ] **Step 1.2.1: Write failing tests**

Append to `test_committer_helpers.py`:

```python
def test_parse_untracked_mds_empty_output():
    assert mod._parse_untracked_mds("") == []


def test_parse_untracked_mds_whitespace_only():
    assert mod._parse_untracked_mds("   \n\n  ") == []


def test_parse_untracked_mds_one_md():
    out = "apps/site/src/content/primary-works/foo.md\n"
    assert mod._parse_untracked_mds(out) == ["apps/site/src/content/primary-works/foo.md"]


def test_parse_untracked_mds_filters_non_md():
    out = (
        "apps/site/src/content/primary-works/foo.md\n"
        "apps/site/src/content/primary-works/.DS_Store\n"
        "apps/site/src/content/primary-works/bar.md\n"
        "apps/site/src/content/primary-works/draft.tmp\n"
    )
    assert mod._parse_untracked_mds(out) == [
        "apps/site/src/content/primary-works/foo.md",
        "apps/site/src/content/primary-works/bar.md",
    ]


def test_parse_untracked_mds_trailing_blank_lines():
    out = "apps/site/src/content/primary-works/foo.md\n\n"
    assert mod._parse_untracked_mds(out) == ["apps/site/src/content/primary-works/foo.md"]
```

- [ ] **Step 1.2.2: Run, expect 5 failures (function undefined)**

```bash
.venv-extract/bin/python3 -m pytest scripts/llm-extract/tests/test_committer_helpers.py -v
# Expected: 5 FAIL with AttributeError: module 'run_overnight' has no attribute '_parse_untracked_mds'
```

- [ ] **Step 1.2.3: Implement `_parse_untracked_mds`**

Open `scripts/llm-extract/run_overnight.py`. Near the existing module-level helpers (after `parse_reset_seconds`, around line 110), add:

```python
def _parse_untracked_mds(stdout: str) -> list[str]:
    """Parse the output of `git ls-files --others --exclude-standard`; return only .md files.

    Handles empty input, whitespace-only input, and trailing blank lines safely.
    Returns paths in the order they appear in the input.
    """
    if not stdout or not stdout.strip():
        return []
    return [line for line in stdout.split("\n") if line.endswith(".md")]
```

- [ ] **Step 1.2.4: Run, expect 5/5 PASS**

```bash
.venv-extract/bin/python3 -m pytest scripts/llm-extract/tests/test_committer_helpers.py -v
# Expected: 5 passed
```

- [ ] **Step 1.2.5: Commit**

```bash
git add scripts/llm-extract/tests/test_committer_helpers.py scripts/llm-extract/run_overnight.py
git commit -m "feat(pipeline): add _parse_untracked_mds helper"
```

### Task 1.3: `_build_commit_message()` (TDD)

**Files:**
- Modify: `scripts/llm-extract/tests/test_committer_helpers.py`
- Modify: `scripts/llm-extract/run_overnight.py`

This helper formats the commit message for each batch. Pure string formatting; trivial to test.

- [ ] **Step 1.3.1: Write failing tests**

Append to `test_committer_helpers.py`:

```python
def test_build_commit_message_first_batch():
    msg = mod._build_commit_message(batch_no=1, count=20, prior_total=0, last_batch=False)
    assert msg.startswith("data(primary-works): extraction batch 1 — 20 new MDs")
    assert "Running total this run: 20." in msg
    assert "run_overnight.py" in msg
    assert "(final flush)" not in msg


def test_build_commit_message_subsequent_batch():
    msg = mod._build_commit_message(batch_no=7, count=20, prior_total=120, last_batch=False)
    assert msg.startswith("data(primary-works): extraction batch 7 — 20 new MDs")
    assert "Running total this run: 140." in msg


def test_build_commit_message_final_flush():
    msg = mod._build_commit_message(batch_no=31, count=13, prior_total=600, last_batch=True)
    assert msg.startswith("data(primary-works): extraction batch 31 — 13 new MDs (final flush)")
    assert "Running total this run: 613." in msg


def test_build_commit_message_zero_count_still_produces_string():
    # Defensive — committer should never call with 0, but if it does, don't crash.
    msg = mod._build_commit_message(batch_no=1, count=0, prior_total=0, last_batch=False)
    assert isinstance(msg, str)
    assert "0 new MDs" in msg
```

- [ ] **Step 1.3.2: Run, expect 4 failures**

```bash
.venv-extract/bin/python3 -m pytest scripts/llm-extract/tests/test_committer_helpers.py -v
# Expected: 5 PASS (from 1.2) + 4 FAIL (AttributeError on _build_commit_message)
```

- [ ] **Step 1.3.3: Implement `_build_commit_message`**

Append to `run_overnight.py` (next to `_parse_untracked_mds`):

```python
def _build_commit_message(*, batch_no: int, count: int, prior_total: int, last_batch: bool) -> str:
    """Format the commit message for one committer batch."""
    suffix = " (final flush)" if last_batch else ""
    return (
        f"data(primary-works): extraction batch {batch_no} — {count} new MDs{suffix}\n"
        f"\n"
        f"Running total this run: {prior_total + count}.\n"
        f"Source: v1.5 extraction pipeline (run_overnight.py).\n"
    )
```

- [ ] **Step 1.3.4: Run, expect 9/9 PASS**

```bash
.venv-extract/bin/python3 -m pytest scripts/llm-extract/tests/test_committer_helpers.py -v
# Expected: 9 passed
```

- [ ] **Step 1.3.5: Commit**

```bash
git add scripts/llm-extract/tests/test_committer_helpers.py scripts/llm-extract/run_overnight.py
git commit -m "feat(pipeline): add _build_commit_message helper"
```

---

## Chunk 2: I/O committer + wiring (smoke-tested)

Goal: Add the `_commit_and_push` I/O helper and `committer_thread` daemon, then wire into `main()` via `try/finally`. These touch real git + subprocess + threads, so we smoke-test rather than unit-test.

### Task 2.1: Module-level constants

**Files:**
- Modify: `scripts/llm-extract/run_overnight.py`

- [ ] **Step 2.1.1: Add constants**

Near the existing module-level constants (around line 46-54, next to `PDFS_ROOT` and `PROGRESS_TSV`), add:

```python
# Committer-thread config (auto-commit + auto-push as MDs accumulate).
COMMIT_BATCH_SIZE = 20
COMMIT_POLL_INTERVAL_S = 60
PW_DIR_REL = "apps/site/src/content/primary-works"
COMMIT_LOG = Path("/tmp/v1.5-overnight-commits.tsv")
```

- [ ] **Step 2.1.2: Verify no import errors**

```bash
.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
import run_overnight
print(f'COMMIT_BATCH_SIZE: {run_overnight.COMMIT_BATCH_SIZE}')
print(f'COMMIT_LOG: {run_overnight.COMMIT_LOG}')
"
# Expected: COMMIT_BATCH_SIZE: 20 / COMMIT_LOG: /tmp/v1.5-overnight-commits.tsv
```

### Task 2.2: `_commit_and_push()` helper

**Files:**
- Modify: `scripts/llm-extract/run_overnight.py`

- [ ] **Step 2.2.1: Implement**

Append (after the two pure helpers):

```python
def _commit_and_push(untracked: list[str], *, batch_no: int, prior_total: int, last_batch: bool) -> None:
    """Stage the given files, commit with a generated message, and push to origin/main.

    Failure modes:
      - git add fails → CalledProcessError propagates (committer thread catches it).
      - git commit fails (e.g., pre-commit hook) → CalledProcessError propagates.
      - git push fails (network, auth, conflict) → logged; commit remains locally; pipeline continues.
    """
    subprocess.run(["git", "add", "--"] + untracked, cwd=ROOT, check=True)
    msg = _build_commit_message(
        batch_no=batch_no, count=len(untracked),
        prior_total=prior_total, last_batch=last_batch,
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    push = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    push_status = "pushed" if push.returncode == 0 else f"push-failed: {push.stderr[:100].strip()}"
    with COMMIT_LOG.open("a") as f:
        f.write(
            f"{int(time.time())}\t{batch_no}\t{len(untracked)}\t"
            f"{prior_total + len(untracked)}\t{push_status}\n"
        )
    print(f"[committer] batch {batch_no}: {len(untracked)} MDs → {push_status}", flush=True)
```

- [ ] **Step 2.2.2: Verify import**

```bash
.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
import run_overnight
print(run_overnight._commit_and_push)
"
# Expected: <function _commit_and_push at 0x...>
```

### Task 2.3: `committer_thread()` daemon

**Files:**
- Modify: `scripts/llm-extract/run_overnight.py`

- [ ] **Step 2.3.1: Implement**

Append:

```python
def committer_thread(stop_event: threading.Event) -> None:
    """Wake every COMMIT_POLL_INTERVAL_S; commit + push when ≥ COMMIT_BATCH_SIZE new MDs exist.

    Idempotent and crash-safe: each poll independently re-discovers untracked MDs via
    `git ls-files --others`. If the committer dies mid-iteration, the next launch picks
    up where it left off (untracked MDs persist; nothing is lost).

    On stop_event.set(), runs a final flush — any remaining untracked .md gets one
    last commit even if the batch threshold isn't reached.
    """
    total_committed = 0
    batch_number = 0
    while not stop_event.is_set():
        try:
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard", "--", PW_DIR_REL],
                capture_output=True, text=True, cwd=ROOT, check=True,
            )
            untracked = _parse_untracked_mds(result.stdout)
            if len(untracked) >= COMMIT_BATCH_SIZE:
                batch_number += 1
                _commit_and_push(
                    untracked, batch_no=batch_number,
                    prior_total=total_committed, last_batch=False,
                )
                total_committed += len(untracked)
        except subprocess.CalledProcessError as e:
            print(f"[committer] git error: {e}; will retry next poll", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[committer] unexpected: {e!r}", file=sys.stderr, flush=True)
        stop_event.wait(COMMIT_POLL_INTERVAL_S)

    # Final flush — commit any leftover < COMMIT_BATCH_SIZE MDs on shutdown.
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", PW_DIR_REL],
            capture_output=True, text=True, cwd=ROOT, check=True,
        )
        untracked = _parse_untracked_mds(result.stdout)
        if untracked:
            batch_number += 1
            _commit_and_push(
                untracked, batch_no=batch_number,
                prior_total=total_committed, last_batch=True,
            )
            total_committed += len(untracked)
    except Exception as e:
        print(f"[committer-final-flush] {e!r}", file=sys.stderr, flush=True)
    print(f"[committer] exiting; total MDs committed this run: {total_committed}", flush=True)
```

- [ ] **Step 2.3.2: Verify import**

```bash
.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
import run_overnight
print(run_overnight.committer_thread)
"
# Expected: <function committer_thread at 0x...>
```

### Task 2.4: Wire committer into `main()`

**Files:**
- Modify: `scripts/llm-extract/run_overnight.py`

- [ ] **Step 2.4.1: Locate `main()` and the ThreadPoolExecutor**

```bash
grep -nE "^def main|ThreadPoolExecutor" scripts/llm-extract/run_overnight.py
# Expected output should show `def main()` and the `ThreadPoolExecutor(...)` line nearby.
# Note the line numbers.
```

- [ ] **Step 2.4.2: Add stop_event + thread start + try/finally**

In `main()`, find the block that currently looks like:

```python
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        # ... existing dispatch/collect loop, references `ex.submit(...)` ...
```

(The actual loop variable in `run_overnight.py` is named `ex`, not `pool`. Body lines like `ex.submit(...)` and `futs = {ex.submit(...): ...}` use that name. Do NOT rename it — that would create stale references.)

Wrap with the committer setup + try/finally, keeping `as ex:` unchanged:

```python
    stop_event = threading.Event()
    committer = threading.Thread(target=committer_thread, args=(stop_event,), daemon=True)
    committer.start()
    print(f"[main] committer thread started (batch size {COMMIT_BATCH_SIZE}, "
          f"poll every {COMMIT_POLL_INTERVAL_S}s)", flush=True)

    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            # ... existing dispatch/collect loop, UNCHANGED — all references to `ex` stay `ex` ...
    finally:
        print("[main] signaling committer to flush + exit...", flush=True)
        stop_event.set()
        committer.join(timeout=120)
```

**Important:** preserve all existing logic inside the `with ThreadPoolExecutor` block. The only change is adding the wrapper. Specifically: do NOT rename `ex` to `pool` — every `ex.submit` / `ex` reference in the body must stay valid. If the existing code has `signal.signal(SIGTERM, ...)` or similar handlers, leave them; the `finally` clause covers normal exit + KeyboardInterrupt; SIGTERM and SIGKILL are documented as known abrupt-exit cases (see §4.3.3).

- [ ] **Step 2.4.3: Verify the file still parses**

```bash
.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
import run_overnight
print('imports OK')
print(f'committer_thread: {run_overnight.committer_thread.__name__}')
print(f'main: {run_overnight.main.__name__}')
"
# Expected: imports OK / committer_thread: committer_thread / main: main
```

- [ ] **Step 2.4.4: Commit**

```bash
git add scripts/llm-extract/run_overnight.py
git commit -m "feat(pipeline): wire committer thread into run_overnight main()

Adds a daemon thread that auto-commits + auto-pushes new MDs in
batches of 20 every 60s. Final flush on exit guarantees no
abandoned untracked files. SIGKILL still leaves untracked, but
the next launch picks them up on first poll."
```

---

## Chunk 3: Smoke test (3 PDFs)

Goal: Run the pipeline against 3 PDFs end-to-end to confirm the committer works, no regressions in prep/dispatch/collect, and the final-flush commit fires on graceful exit.

### Task 3.1: Confirm `--smoke` flag exists

- [ ] **Step 3.1.1: Verify the CLI**

```bash
.venv-extract/bin/python3 scripts/llm-extract/run_overnight.py --help 2>&1 | grep -A1 "smoke\|concurrency"
# Expected: --smoke N flag is documented; --concurrency N too.
```

### Task 3.2: Run the smoke

- [ ] **Step 3.2.1: Capture pre-smoke state**

```bash
cd "/Users/siraj/Indian Liberals Website"

PRE_MD_COUNT=$(ls apps/site/src/content/primary-works/*.md | wc -l | tr -d ' ')
PRE_HEAD=$(git rev-parse --short HEAD)
echo "pre: MDs=$PRE_MD_COUNT, HEAD=$PRE_HEAD"
# Expected: MDs=377, HEAD=<latest-after-Chunk-2>
```

- [ ] **Step 3.2.2: Launch the smoke**

```bash
cd "/Users/siraj/Indian Liberals Website"

# Foreground run (not nohup) so we can watch it. ~10-15 min for 3 PDFs.
.venv-extract/bin/python3 scripts/llm-extract/run_overnight.py \
  --concurrency 2 --smoke 3 \
  2>&1 | tee /tmp/v1.5-smoke.log
```

Expected:
- Three `[seed]` / processing lines
- Three `OK` rows in `/tmp/v1.5-overnight-progress.tsv`
- One `[committer]` flush line at the end (the final-flush batch with 3 MDs)
- One new commit on local main: `data(primary-works): extraction batch 1 — 3 new MDs (final flush)`
- The commit gets pushed (or `push-failed:` logged in `/tmp/v1.5-overnight-commits.tsv`)

- [ ] **Step 3.2.3: Verify post-smoke state**

```bash
cd "/Users/siraj/Indian Liberals Website"

POST_MD_COUNT=$(ls apps/site/src/content/primary-works/*.md | wc -l | tr -d ' ')
echo "post: MDs=$POST_MD_COUNT  (expected: 380)"

git log --oneline -3
# Expected: top commit is "data(primary-works): extraction batch 1 — 3 new MDs (final flush)"

cat /tmp/v1.5-overnight-commits.tsv
# Expected: one row with batch=1, count=3, total=3, status=pushed (or push-failed: ...)

cat /tmp/v1.5-overnight-progress.tsv | grep OK | wc -l
# Expected: 3 (or more if prior runs left rows)

# Spot-check ONE of the new MDs renders correctly
ls -t apps/site/src/content/primary-works/*.md | head -1 | xargs head -20
# Expected: well-formed frontmatter with title, authors, summary, etc.
```

- [ ] **Step 3.2.4: If smoke fails, STOP and diagnose**

Common failure modes:
- `ImportError`: a syntax error in run_overnight.py from Chunk 2.4. Inspect the diff, fix.
- `Drive not mounted`: re-attach the external drive.
- `claude -p` rate-limit: wait for the window, restart smoke.
- `[committer] git error: not a git repo`: shouldn't happen; check `cd`.
- `Push failed (auth)`: re-authenticate `gh auth login` and re-launch smoke.

If smoke succeeds → proceed to Chunk 4.

### Task 3.3: Verify build still works

- [ ] **Step 3.3.1: Build**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/v1.5-post-smoke-build.log | tail -6
[ -L public/pagefind ] || ln -s ../dist/pagefind public/pagefind

grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/v1.5-post-smoke-build.log
# Expected: 0

find dist -name 'index.html' | wc -l
# Expected: 1283 + 3 = 1286 (one page per new MD)
```

- [ ] **Step 3.3.2: Sanity-check a new MD page**

```bash
# Pick the most recently added MD
SLUG=$(ls -t apps/site/src/content/primary-works/*.md | head -1 | xargs basename | sed 's/.md$//')
echo "checking $SLUG"

PAGE=$(find apps/site/dist -path "*/primary-works/$SLUG/index.html" | head -1)
[ -n "$PAGE" ] && echo "✓ rendered at $PAGE" || echo "✗ no page found"

# The page should contain the title from the MD's frontmatter
grep -c "<h1" "$PAGE"
# Expected: ≥ 1
```

---

## Chunk 4: Full batch launch + monitoring

Goal: Launch the full 610-PDF run in the background. This step blocks until the run finishes (could be 2-5 days), but the launching session can close.

### Task 4.1: Pre-launch sanity

- [ ] **Step 4.1.1: Confirm drive + venv + auth one last time**

```bash
cd "/Users/siraj/Indian Liberals Website"
ls "/Volumes/One Touch/Indian Liberals/PDFs-by-publisher" >/dev/null && echo "✓ drive"
.venv-extract/bin/python3 --version >/dev/null && echo "✓ venv"
git remote -v | grep -q origin && echo "✓ remote"
git ls-remote origin HEAD >/dev/null 2>&1 && echo "✓ remote auth" || echo "✗ run gh auth login"
```

- [ ] **Step 4.1.2: Confirm unbaked count is what we expect**

```bash
.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
from run_overnight import list_unbaked_pdfs
print(f'unbaked: {len(list_unbaked_pdfs())}')
"
# Expected: 607 (was 610 minus the 3 from smoke)
```

- [ ] **Step 4.1.3: Confirm no other run is in flight**

```bash
pgrep -fl "run_overnight.py" || echo "(no existing process)"
# Expected: (no existing process). If a process is running, STOP — don't double-launch.
```

### Task 4.2: Launch

- [ ] **Step 4.2.1: Launch the full batch via nohup**

```bash
cd "/Users/siraj/Indian Liberals Website"

nohup .venv-extract/bin/python3 scripts/llm-extract/run_overnight.py \
  --concurrency 8 \
  > /tmp/v1.5-overnight-v2.log 2>&1 &
echo $! > /tmp/v1.5-overnight-v2.pid
disown

sleep 5
echo "PID: $(cat /tmp/v1.5-overnight-v2.pid)"
ps -p "$(cat /tmp/v1.5-overnight-v2.pid)" && echo "✓ running" || echo "✗ already exited (check log)"
head -20 /tmp/v1.5-overnight-v2.log
# Expected: "[main] committer thread started (batch size 20, poll every 60s)" near the top.
```

### Task 4.3: Live monitoring (optional, hands-off)

The pipeline runs autonomously for 2-5 days. Adnan can ignore it or watch via:

- [ ] **Step 4.3.1: Three logs to tail**

```bash
tail -f /tmp/v1.5-overnight-v2.log              # raw stdout/stderr
tail -f /tmp/v1.5-overnight-progress.tsv        # per-PDF status
tail -f /tmp/v1.5-overnight-commits.tsv         # per-batch commit + push results
```

- [ ] **Step 4.3.2: Periodic health check**

```bash
ps -p "$(cat /tmp/v1.5-overnight-v2.pid)" && echo "✓ alive" || echo "✗ exited"

# Untracked-but-emitted MDs (should oscillate 0..20)
git ls-files --others --exclude-standard -- apps/site/src/content/primary-works/ | grep '\.md$' | wc -l

# Commits since launch
git log --oneline origin/main..HEAD
# Expected: usually empty (auto-pushed). If non-empty, push-failed somewhere.

# Recent batches on GitHub
git log --oneline origin/main | head -10
```

- [ ] **Step 4.3.3: Stop early (if needed)**

```bash
# Graceful: SIGINT raises KeyboardInterrupt in the main thread, which propagates
# through the try/finally and triggers the committer's final flush.
kill -INT "$(cat /tmp/v1.5-overnight-v2.pid)"

# Confirm exit
sleep 10
ps -p "$(cat /tmp/v1.5-overnight-v2.pid)" || echo "✓ stopped"
tail -5 /tmp/v1.5-overnight-v2.log
# Expected: "[main] signaling committer..." + "[committer] exiting; total..."
```

**Note on SIGTERM:** Python's default `SIGTERM` handler is the OS default — immediate exit, the `try/finally` block does NOT run. If you accidentally `kill -TERM`, the daemon committer dies with the process and any < 20 untracked MDs persist. They're not lost: the next launch's committer picks them up on its first poll (60s in). For a true graceful stop, always use `kill -INT` (or `Ctrl-C` if running foreground).

### Task 4.4: Wait for completion

- [ ] **Step 4.4.1: Detect completion**

The pipeline exits when `list_unbaked_pdfs()` returns 0 (or only unrecoverable failures). Signal:

```bash
# Process gone + log shows summary line
ps -p "$(cat /tmp/v1.5-overnight-v2.pid)" || tail -30 /tmp/v1.5-overnight-v2.log
```

Expected final state:
- Final flush committed
- All untracked MDs committed (`git ls-files --others ...` returns empty for primary-works/)
- Commit log shows ~31 batches (or fewer if failures)

---

## Chunk 5: Post-batch verification + handoff

Goal: After the runner finishes, validate the results and surface to Adnan for the next step (pdf_url re-discovery, R2 migration, etc.).

### Task 5.1: Coverage check

- [ ] **Step 5.1.1: Unbaked count → 0 (or known-failing)**

```bash
cd "/Users/siraj/Indian Liberals Website"

.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
from run_overnight import list_unbaked_pdfs
unbaked = list_unbaked_pdfs()
print(f'unbaked remaining: {len(unbaked)}')
for u in unbaked[:20]:
    print(f'  {u}')
"
# Expected: 0 (success). If > 0, those are the failing PDFs — check progress.tsv to understand why.
```

- [ ] **Step 5.1.2: MD count**

```bash
ls apps/site/src/content/primary-works/*.md | wc -l
# Expected: ~987 (377 baseline + ~610 new — minus any failures)
```

- [ ] **Step 5.1.3: Build clean**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/v1.5-final-build.log | tail -6
[ -L public/pagefind ] || ln -s ../dist/pagefind public/pagefind

grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/v1.5-final-build.log
# Expected: 0

find dist -name 'index.html' | wc -l
# Expected: ~1893 (1283 + ~610 new — minus any failures)
```

### Task 5.2: Spot-check 10 new MDs

- [ ] **Step 5.2.1: Sample 10 random new MDs**

```bash
cd "/Users/siraj/Indian Liberals Website"

# Substitute PRE_EXT_SHA below with the SHA captured in Step 0.3
# (the value from `git rev-parse --short HEAD` BEFORE Chunk 1 ran).
PRE_EXT_SHA="${PRE_EXT_SHA:?Set this to the SHA recorded in Step 0.3}"

.venv-extract/bin/python3 << PYEOF
import json, random, re, yaml
from pathlib import Path

random.seed(0)
PW = Path("apps/site/src/content/primary-works")
import subprocess
result = subprocess.run(
    ["git", "diff", "--name-only", "--diff-filter=A", "$PRE_EXT_SHA..HEAD", "--", str(PW)],
    capture_output=True, text=True, cwd=".",
)
new_mds = [Path(p) for p in result.stdout.strip().split("\n") if p.endswith(".md")]
print(f"new MDs since pre-extension baseline: {len(new_mds)}")

sample = random.sample(new_mds, min(10, len(new_mds)))
for md in sample:
    text = md.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not fm_match: continue
    try:
        fm = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError:
        continue
    title = (fm.get("title") or {}).get("main") or ""
    summary = fm.get("summary") or ""
    needs_review = fm.get("needs_review", False)
    first = re.split(r"(?<=[.?!])\s+", summary.strip(), maxsplit=1)[0][:150]
    print(f"\n--- {md.stem}")
    print(f"    title:        {title}")
    print(f"    needs_review: {needs_review}")
    print(f"    summary[0]:   {first}")
PYEOF
```

(Note: the heredoc is unquoted (`PYEOF` not `'PYEOF'`) so that `$PRE_EXT_SHA` interpolates from the shell into the embedded Python source.)

Eyeball-check each:
- Title is non-empty and matches the file's slug roughly
- Summary's first sentence describes the same work the title names
- needs_review: true is acceptable (means the AI was uncertain); false is preferred

### Task 5.3: Re-run the inventory audit

- [ ] **Step 5.3.1: Run the slug-vs-URL + summary-content audit script from the prior session**

```bash
# This is the script from the May 26 verification work — it checks:
# - slug == url_basename (safe group)
# - summary describes the work the title claims (no Khoj-2009 → 2006-content silent mismatches)
.venv-extract/bin/python3 << 'PYEOF'
"""Re-audit content-vs-URL alignment on the post-extension corpus."""
import re, yaml
from pathlib import Path
from urllib.parse import urlparse, unquote

PW = Path("apps/site/src/content/primary-works")
_FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)

flagged = []
for md_path in sorted(PW.glob("*.md")):
    text = md_path.read_text(encoding="utf-8")
    m = _FM.match(text)
    if not m: continue
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        continue
    url = fm.get("pdf_url")
    summary = fm.get("summary") or ""
    if not url or not summary:
        continue
    # Flag if the summary contains explicit mismatch language.
    disclaimer = re.search(
        r"could not be located|is a different work|appears to be missing|"
        r"file at the recorded path|dispatch inventory tags",
        summary[:1500], re.I,
    )
    if disclaimer:
        flagged.append((md_path.stem, disclaimer.group(0)))

print(f"Post-extension audit: {len(flagged)} MDs with disclaimer language in summary")
for slug, match in flagged[:20]:
    print(f"  {slug}: '{match}'")
PYEOF
```

Expected: 0 flagged (the v1.5 pipeline doesn't produce the "PDF could not be located" disclaimer — that came from the WP-DB-rebuild commit, which is not used here). If > 0, surface to Adnan.

### Task 5.4: Optional follow-up: re-run `match-pdfs.py` for new MDs

- [ ] **Step 5.4.1: Re-run the matcher**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/match-pdfs.py
# Expected: a higher exact + high tier match count since many new MD slugs now exist
# that correspond to prod URLs we already crawled.
```

- [ ] **Step 5.4.2: Surface the new manifest to Adnan**

Use the same review workflow as the prior pdf_url batch — eyeball the new manifest, decide on `apply-pdf-urls.py` invocation.

### Task 5.5: Final commit + handoff

- [ ] **Step 5.5.1: Commit any pending audit artifacts (if any)**

```bash
# If you wrote anything new to data/ during audit, commit it.
git status --short data/
```

- [ ] **Step 5.5.2: Report to Adnan**

Summarise:
- Final MD count
- Number of successful bakes vs failures (from progress.tsv `OK` vs `*_FAILED` counts)
- New build's page count
- Audit results
- Whether `match-pdfs.py` re-run was done + how many new `pdf_url`s would be applied
- STOP — Adnan reviews + decides on the apply step

---

## Final acceptance

- [ ] **Acceptance #1:** `list_unbaked_pdfs()` returns 0 (or only documented unrecoverable failures).
- [ ] **Acceptance #2:** `pnpm build` exits clean.
- [ ] **Acceptance #3:** `find apps/site/dist -name 'index.html' | wc -l` ≈ 1893 (within 5% of 1283 + successful-bakes).
- [ ] **Acceptance #4:** 10 randomly-sampled new MDs each have a sensible title + summary that describes the same work.
- [ ] **Acceptance #5:** Post-extension audit shows 0 new disclaimer-language summaries (no silent mismatches).
- [ ] **Acceptance #6:** `git log --oneline origin/main..HEAD` is empty (all batches successfully pushed).
- [ ] **Acceptance #7:** Pipeline-extension committer code reviewed (Chunks 1 + 2 commits) and approved.
- [ ] **STOP** — surface to Adnan for the `match-pdfs.py` re-run + apply step.

---

## Out of scope (per spec §2)

- Re-baking the 335 already-baked PDFs.
- Schema changes to prompts, validator, or content collections.
- PDF acquisition / R2 migration.
- Editorial review of `needs_review: true` MDs.
- Anthology continuation loop for multi-essay works (existing `cmd_loop` handles this if invoked separately).
- Populating `pdf_url` for the new MDs (deferred to `match-pdfs.py` re-run; covered in §5.4 but execution is Adnan's call).
- Cleaning up the 6 honest-placeholder MDs flagged in prior audits.
- Running the extraction as a cloud routine (the external drive isn't reachable from cloud infra; local nohup is the confirmed venue).

---

## Plan complete

After all chunks pass:

1. The terminal state is:
   - ~610 new MDs under `apps/site/src/content/primary-works/`, batched into ~31 commits on `origin/main`.
   - ~610 new dirs under `data/bake-off-output/<slug>/` with metadata + summary JSONs.
   - 2 new pure-logic helpers + 1 daemon thread in `run_overnight.py`.
   - 1 new test file with 9 unit tests.
   - 3 log files under `/tmp/` (one rotates per run).
2. Adnan reviews the final summary, decides on `match-pdfs.py` re-run + apply, decides on editorial review of `needs_review: true` MDs.
