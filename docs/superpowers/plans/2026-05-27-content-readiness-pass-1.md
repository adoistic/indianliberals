# Content-Readiness Pass 1 — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the ~99 newly-extracted primary-works MDs to publishable shape by populating `pdf_url` via the locked PDF-reconciliation tools (Stream A), then surface cross-reference and quote-attribution gaps via two new audit scripts (Streams C, D), and capture all findings in a single handoff document for the next session.

**Architecture:** Four chunks landing on `main`. Chunk 1 (Stream A) reuses existing `match-pdfs.py` + `apply-pdf-urls.py` to write pdf_urls in high-confidence tiers only. Chunks 2 and 3 (Streams C, D) build two small, read-only TDD'd audit scripts. Chunk 4 composes the findings document from the captured audit outputs and Stream A's apply count. The extraction pipeline at PID 43187 continues running throughout; all writes target MDs that already exist (disjoint from the pipeline's new-MD writes).

**Tech Stack:** Python 3.14 in `.venv-extract/`, existing `pyyaml` + `rapidfuzz` deps, `pytest`, `git`, Astro static build (`pnpm` in `apps/site/`).

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `scripts/synthesis/match-pdfs.py` | UNCHANGED | Regenerate manifest TSVs over the full 476-MD corpus. |
| `scripts/synthesis/apply-pdf-urls.py` | UNCHANGED | Apply only `exact,high` tier rows that don't already have `pdf_url`. |
| `scripts/synthesis/audit-cross-refs.py` | CREATE (~150 lines) | Read-only audit: slug ↔ prose drift on MDs added since `b6be9fe`. |
| `scripts/synthesis/audit-thinkers-without-quotes.py` | CREATE (~150 lines) | Read-only audit: corpus-wide inverted index of `thinker_mentions[].evidence[].quote` per thinker. |
| `scripts/synthesis/tests/test_readiness_audits.py` | CREATE (~120 lines) | Unit tests for both new scripts (10 tests total). |
| `data/pdf-link-manifest.tsv` | REGENERATED | Output of `match-pdfs.py`; committed alongside the apply. |
| `data/pdf-link-misses.tsv` | REGENERATED | Output of `match-pdfs.py`; committed alongside the apply. |
| `docs/handoffs/2026-05-27-content-readiness-pass-1.md` | CREATE | Hand-authored findings doc covering Streams A, B, C, D + follow-ups. |

**File-size budget:** new code ~300 lines (two scripts) + ~120 lines tests + ~3-5 KB Markdown findings doc.

---

## Conventions to honour

- **Python venv:** all script runs use `.venv-extract/bin/python3 <script>`.
- **Test runs:** `.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_readiness_audits.py -v`
- **Commit prefixes:** `data(primary-works):` for the pdf_url apply commit; `feat(synthesis):` for the two new audit scripts (one commit each); `test(synthesis):` is acceptable for test-only commits if TDD splits them; `docs(handoff):` for the findings doc.
- **No `Co-Authored-By` trailer.**
- **Push policy:** push each chunk's commits to `origin/main` as soon as it lands, so the still-running extraction pipeline's auto-pushes don't accumulate divergence. Before any push, run `git fetch origin && git rebase origin/main` to pick up any batches the runner pushed in the meantime.
- **Runner interaction:** the extraction pipeline at PID 43187 may auto-push at any moment. It writes only **new** MDs (slugs that don't yet exist); we write only to MDs that **already exist** OR new artifacts under `scripts/synthesis/`, `data/pdf-link-*.tsv`, `docs/handoffs/`. The sets are disjoint — there are no conflicts on the same file. The only race window is the push (non-fast-forward); resolve via `git rebase` and re-push.

---

## Pre-work baseline (run once before Chunk 1)

- [ ] **Step 0.1: Confirm extraction pipeline still running + capture context**

```bash
cd "/Users/siraj/Indian Liberals Website"
PID=$(cat /tmp/v1.5-overnight-v2.pid 2>/dev/null)
ps -p "$PID" >/dev/null 2>&1 && echo "✓ pipeline PID $PID alive" || echo "(pipeline NOT running — fine, plan still works)"
.venv-extract/bin/python3 -c "
import sys; sys.path.insert(0, 'scripts/llm-extract')
from run_overnight import list_unbaked_pdfs
print(f'unbaked remaining: {len(list_unbaked_pdfs())}')
"
```

The plan does NOT depend on the pipeline being running or stopped — it works in both states.

- [ ] **Step 0.2: Verify prod-mirror inventory exists**

```bash
cd "/Users/siraj/Indian Liberals Website"
ls -la data/prod-mirror/inventory.jsonl
wc -l data/prod-mirror/inventory.jsonl
# Expected: non-empty file, ≥ 400 lines (one per prod page).
# If MISSING: STOP — Stream A cannot run without it. Surface to Adnan.
```

- [ ] **Step 0.3: Capture pre-pass SHA + counts**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
PRE_PASS_SHA=$(git rev-parse --short HEAD)
PRE_PASS_MD_COUNT=$(ls apps/site/src/content/primary-works/*.md | wc -l | tr -d ' ')
PRE_PASS_PDFURL_COUNT=$(grep -l "^pdf_url:" apps/site/src/content/primary-works/*.md | wc -l | tr -d ' ')
echo "PRE_PASS_SHA=$PRE_PASS_SHA"
echo "PRE_PASS_MD_COUNT=$PRE_PASS_MD_COUNT"
echo "PRE_PASS_PDFURL_COUNT=$PRE_PASS_PDFURL_COUNT"
# Record these. The findings doc will quote them.
# The pre-EXTENSION SHA (b6be9fe) is the audit reference for "new MDs since the extraction batch started" —
# do NOT use PRE_PASS_SHA for that; use b6be9fe.
```

- [ ] **Step 0.4: Confirm test-discovery convention for hyphenated scripts**

```bash
cd "/Users/siraj/Indian Liberals Website"
head -30 scripts/synthesis/tests/test_apply_pdf_urls.py
# Expected: shows the importlib-based load pattern (`importlib.util.spec_from_file_location`)
# used to import apply-pdf-urls.py (hyphenated names can't be `import`ed directly).
# Use that same pattern in the new test_readiness_audits.py.
```

---

## Chunk 1: Stream A — PDF URL apply

Goal: regenerate manifest, apply only the `exact,high` tier rows, commit the three artifacts (mutated MDs + both TSVs), push.

### Task 1.1: Regenerate manifest

**Files:**
- Touch: `data/pdf-link-manifest.tsv` (regenerated)
- Touch: `data/pdf-link-misses.tsv` (regenerated)

- [ ] **Step 1.1.1: Run match-pdfs.py and capture the log**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/match-pdfs.py 2>&1 | tee /tmp/v1.5-readiness-match.log | tail -10
# Expected stdout includes a line like:
#   match-pdfs: N exact, M high, K medium, P page-only, Q misses (T total).
# plus "manifest.tsv: N rows (...)" and "misses.tsv: M rows (...)".
```

- [ ] **Step 1.1.2: Read the tier counts from the match summary line**

```bash
cd "/Users/siraj/Indian Liberals Website"
grep "^match-pdfs:" /tmp/v1.5-readiness-match.log
# Expected: the one summary line printed by match-pdfs.py. The numbers
# in that line are the tier counts; sum `exact + high` mentally — that's
# what Stream A's apply step targets. (Most of those are existing MDs that
# already have pdf_url and will be no-ops; only new-MD rows actually mutate.)
```

### Task 1.2: Dry-run apply

**Files:**
- Read: `data/pdf-link-manifest.tsv`

- [ ] **Step 1.2.1: Dry-run apply for exact+high tiers**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py \
  --dry-run --only-confidence exact,high \
  2>&1 | tee /tmp/v1.5-readiness-dryrun.log | tail -30
# Expected: a list of "  [inserted] <slug>: (none) → pdf_url: <URL>" lines
# (one per row that would mutate) plus a tail block:
#     statuses:
#       inserted: N
#       skip-existing: M
#       skip-no-frontmatter: P
# Record N (the "inserted: N" line) — that's the apply count.
```

- [ ] **Step 1.2.2: Sanity check — pick 3 random would-insert entries and eyeball the URLs**

```bash
cd "/Users/siraj/Indian Liberals Website"
grep '\[inserted\]' /tmp/v1.5-readiness-dryrun.log | shuf -n 3
# The lines have the form "  [inserted] <slug>: (none) → pdf_url: <URL>".
# Manually (or via curl -sI) verify each URL looks like a real prod URL
# ending in .pdf or a tracked redirect. If any URL looks malformed (e.g.,
# empty path, doubled slashes), STOP and surface — the manifest may have a bug.
```

### Task 1.3: Apply + commit + push

**Files:**
- Modify: `apps/site/src/content/primary-works/<various>.md` (frontmatter only; one `pdf_url:` line inserted after `provenance:` block)
- Modify: `data/pdf-link-manifest.tsv` (committed for review surface)
- Modify: `data/pdf-link-misses.tsv` (committed for review surface)

- [ ] **Step 1.3.1: Apply (real, no --dry-run). Use --no-commit so this plan's own commit step is the source of truth**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py \
  --only-confidence exact,high --no-commit \
  2>&1 | tee /tmp/v1.5-readiness-apply.log | tail -15
# Expected tail: a "statuses:" block with "  inserted: N" matching Step 1.2.1's N.
# --no-commit suppresses the script's built-in auto-commit (which would otherwise
# stage + commit with the message "data(primary-works): populate pdf_url from prod
# indianliberals.in (N=...)"). We re-commit with our own message in Step 1.3.3.
APPLIED_N=$(grep -E "^\s+inserted:" /tmp/v1.5-readiness-apply.log | head -1 | awk '{print $2}')
APPLIED_N=${APPLIED_N:-0}
echo "APPLIED_N=$APPLIED_N"
```

- [ ] **Step 1.3.2: Stage the three artifacts**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add data/pdf-link-manifest.tsv data/pdf-link-misses.tsv apps/site/src/content/primary-works/
git status --short | head -20
# Expected: M data/pdf-link-manifest.tsv, M data/pdf-link-misses.tsv,
# and ~APPLIED_N M apps/site/src/content/primary-works/*.md lines.
# Should NOT see any A (new) primary-works/*.md from us — those would be the runner's. If you
# see A files staged, unstage them: `git reset HEAD apps/site/src/content/primary-works/<new>.md`.
```

- [ ] **Step 1.3.3: Commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
if [ "${APPLIED_N:-0}" -gt 0 ]; then
  git commit -m "data(primary-works): apply ${APPLIED_N} high-confidence pdf_urls from prod reconciliation"
else
  # No MDs mutated. The manifest TSVs may still have changed (they're regenerated every run);
  # if `git diff --cached --quiet` is non-zero, we still want a commit for the TSV refresh.
  if ! git diff --cached --quiet; then
    git commit -m "data(synthesis): regenerate pdf-link-manifest.tsv (0 high-confidence applies)"
  else
    echo "(nothing to commit — Stream A was a no-op including TSVs)"
  fi
fi
```

If `APPLIED_N` is 0, the findings doc reports "Stream A applied 0"; proceed to Chunk 2 regardless of whether a TSV-only commit landed.

- [ ] **Step 1.3.4: Rebase + push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
# If conflicts on data/pdf-link-manifest.tsv or pdf-link-misses.tsv (unlikely — only we touch
# them, but the runner could in theory): accept ours via
#   git checkout --ours data/pdf-link-manifest.tsv data/pdf-link-misses.tsv
#   git add data/pdf-link-manifest.tsv data/pdf-link-misses.tsv
#   git rebase --continue
# If conflicts on apps/site/src/content/primary-works/*.md: should not happen because
# we modify EXISTING files and the runner only adds NEW files. If it does happen, STOP and
# diagnose — something has changed about the disjointness invariant.
git push origin main
git log --oneline origin/main..HEAD
# Expected: empty (push succeeded).
```

### Task 1.4: Build sanity

- [ ] **Step 1.4.1: Build clean**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | tee /tmp/v1.5-readiness-build.log | tail -6
[ -L public/pagefind ] || ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/v1.5-readiness-build.log
# Expected: 0
PAGE_COUNT=$(find dist -name 'index.html' | wc -l | tr -d ' ')
echo "PAGE_COUNT=$PAGE_COUNT"
# Expected: same as before this chunk (pdf_url changes don't add/remove pages).
# (The pipeline may have added more MDs since the pre-pass baseline — page count can be
# slightly higher than PRE_PASS_MD_COUNT, but the delta should equal the number of new MDs
# the runner committed during this chunk, not the APPLIED_N.)
```

- [ ] **Step 1.4.2: Spot-check one newly-pdf_url'd MD**

```bash
cd "/Users/siraj/Indian Liberals Website"
# Pick the first slug touched by the apply step. The dry-run log lines look like:
#   "  [inserted] <slug>: (none) → pdf_url: <URL>"
SAMPLE_SLUG=$(grep '\[inserted\]' /tmp/v1.5-readiness-dryrun.log \
  | head -1 | sed -E 's/^[[:space:]]*\[inserted\][[:space:]]+([a-z0-9-]+):.*/\1/')
echo "checking: $SAMPLE_SLUG"
if [ -z "$SAMPLE_SLUG" ]; then
  echo "(no inserts to spot-check — Stream A was a no-op)"
else
  grep "^pdf_url:" "apps/site/src/content/primary-works/${SAMPLE_SLUG}.md"
  # Expected: pdf_url: https://indianliberals.in/.../.pdf
  grep -c "Read PDF\|pdf_url\|href.*\.pdf" "apps/site/dist/primary-works/${SAMPLE_SLUG}/index.html"
  # Expected: ≥ 1 (the "Read PDF" button is rendered).
fi
```

---

## Chunk 2: Stream C — `audit-cross-refs.py` (TDD)

Goal: TDD-build a read-only audit that surfaces slug↔prose drift on the MDs added since the pre-extension SHA `b6be9fe`.

### Task 2.1: Test file scaffolding

**Files:**
- Create: `scripts/synthesis/tests/test_readiness_audits.py`

- [ ] **Step 2.1.1: Inspect an existing hyphenated-script test for the importlib pattern**

```bash
cd "/Users/siraj/Indian Liberals Website"
head -40 scripts/synthesis/tests/test_apply_pdf_urls.py
# Look for `importlib.util.spec_from_file_location` — that's the pattern to copy.
```

- [ ] **Step 2.1.2: Create the test file with the importlib loader for `audit-cross-refs.py`**

Create `scripts/synthesis/tests/test_readiness_audits.py` with:

```python
"""Unit tests for the content-readiness pass 1 audit scripts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _load(stem: str):
    """Load a hyphenated script (e.g., 'audit-cross-refs') as a module."""
    spec = importlib.util.spec_from_file_location(
        stem.replace("-", "_"),
        str(SCRIPTS_DIR / f"{stem}.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cross_refs = _load("audit-cross-refs")
```

- [ ] **Step 2.1.3: Run pytest — expect ImportError (script doesn't exist yet)**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_readiness_audits.py -v 2>&1 | tail -10
# Expected: FAIL during import with FileNotFoundError on audit-cross-refs.py — that's correct.
# The next step creates the script with stub functions.
```

### Task 2.2: `audit-cross-refs.py` — create with stub functions

**Files:**
- Create: `scripts/synthesis/audit-cross-refs.py`

- [ ] **Step 2.2.1: Create the script skeleton**

Create `scripts/synthesis/audit-cross-refs.py` with the following content:

```python
#!/usr/bin/env python3
"""
audit-cross-refs.py — read-only audit of slug ↔ prose drift in new MDs.

For each primary-works MD added since the pre-extension SHA (b6be9fe), surface:
  - Slugs in related_thinkers whose canonical name (or any also_known_as) doesn't
    appear in summary/key_points (possible AI hallucination).
  - Canonical thinker names (or also_known_as) appearing in summary/key_points
    that are missing from related_thinkers (possible missed structured tag).

Reads:
  apps/site/src/content/primary-works/*.md  (filtered to "new since BASELINE_SHA")
  apps/site/src/content/thinkers/*.md       (slug → name forms lookup)

Writes:
  stdout report (captured into docs/handoffs/2026-05-27-content-readiness-pass-1.md).

Run:
  .venv-extract/bin/python3 scripts/synthesis/audit-cross-refs.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
THINKERS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "thinkers"
BASELINE_SHA = "b6be9fe"  # pre-extension; "new MDs" = added between this and HEAD

_FM_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


@dataclass
class ThinkerInfo:
    slug: str
    canonical: str
    also_known_as: list[str] = field(default_factory=list)


@dataclass
class Discrepancy:
    md_slug: str
    slugs_not_in_prose: list[str] = field(default_factory=list)
    names_not_in_slugs: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.slugs_not_in_prose and not self.names_not_in_slugs


def _load_thinker_index(thinkers_dir: Path) -> dict[str, ThinkerInfo]:
    """Return slug → ThinkerInfo for every thinker MD in the dir."""
    index: dict[str, ThinkerInfo] = {}
    for md in sorted(thinkers_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FM_RX.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        slug = fm.get("id") or md.stem
        name_block = fm.get("name") or {}
        canonical = (name_block.get("canonical") or "").strip()
        also = name_block.get("also_known_as") or []
        if not isinstance(also, list):
            also = []
        also = [a.strip() for a in also if isinstance(a, str) and a.strip()]
        if not canonical:
            continue
        index[slug] = ThinkerInfo(slug=slug, canonical=canonical, also_known_as=also)
    return index


def _find_name_in_text(name: str, text: str) -> bool:
    """Whole-word, case-insensitive substring match for `name` in `text`.

    Whole-word here means the name boundaries are non-word characters (or string start/end).
    Multi-token names match exactly as-written (case-insensitive); collapse to a regex.
    """
    if not name or not text:
        return False
    pattern = r"\b" + re.escape(name) + r"\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _find_thinker_in_text(thinker: ThinkerInfo, text: str) -> bool:
    """True if ANY of the thinker's name forms appears in text."""
    forms = [thinker.canonical] + thinker.also_known_as
    return any(_find_name_in_text(f, text) for f in forms)


def _check_md(md_path: Path, thinker_index: dict[str, ThinkerInfo]) -> Discrepancy:
    """Return a Discrepancy for one MD."""
    text = md_path.read_text(encoding="utf-8")
    m = _FM_RX.match(text)
    md_slug = md_path.stem
    if not m:
        return Discrepancy(md_slug=md_slug)
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return Discrepancy(md_slug=md_slug)

    related = fm.get("related_thinkers") or []
    if not isinstance(related, list):
        related = []
    related = [s for s in related if isinstance(s, str)]

    # The prose surface we check: summary + key_points lines from the body.
    summary = fm.get("summary") or ""
    body = m.group(2) or ""
    key_points_body = ""
    # Pull the "## Key points" section from the body, if present.
    kp_match = re.search(r"^##\s*Key points\s*$(.+?)(?=^##\s|\Z)", body, re.M | re.S)
    if kp_match:
        key_points_body = kp_match.group(1)
    prose = (summary + "\n" + key_points_body).strip()

    # 1. Slugs in related_thinkers but not in prose
    slugs_not_in_prose: list[str] = []
    for slug in related:
        info = thinker_index.get(slug)
        if info is None:
            # Slug doesn't resolve to a thinker file — separate concern (Stream B)
            continue
        if not _find_thinker_in_text(info, prose):
            slugs_not_in_prose.append(slug)

    # 2. Thinker names in prose but not in related_thinkers
    related_set = set(related)
    names_not_in_slugs: list[str] = []
    for slug, info in thinker_index.items():
        if slug in related_set:
            continue
        if _find_thinker_in_text(info, prose):
            names_not_in_slugs.append(info.canonical)

    return Discrepancy(
        md_slug=md_slug,
        slugs_not_in_prose=slugs_not_in_prose,
        names_not_in_slugs=names_not_in_slugs,
    )


def _new_mds_since(baseline_sha: str) -> list[Path]:
    """Return paths of primary-works MDs added since baseline_sha."""
    result = subprocess.run(
        ["git", "log", f"--diff-filter=A", "--name-only", "--pretty=format:",
         f"{baseline_sha}..HEAD", "--", str(PW_DIR)],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    paths = []
    seen = set()
    for line in result.stdout.split("\n"):
        line = line.strip()
        if not line or not line.endswith(".md"):
            continue
        if line in seen:
            continue
        seen.add(line)
        p = REPO_ROOT / line
        if p.exists():
            paths.append(p)
    return paths


def main() -> int:
    thinker_index = _load_thinker_index(THINKERS_DIR)
    new_mds = _new_mds_since(BASELINE_SHA)

    print(f"=== Cross-reference discrepancies — new MDs since {BASELINE_SHA} ===")
    print(f"Total new MDs scanned: {len(new_mds)}")
    print(f"Thinker index size: {len(thinker_index)}")
    print()

    discrepancies = []
    for md in sorted(new_mds):
        d = _check_md(md, thinker_index)
        if not d.is_empty():
            discrepancies.append(d)

    print(f"MDs with discrepancies: {len(discrepancies)}")
    print()

    for d in discrepancies:
        print(f"--- {d.md_slug} ---")
        if d.slugs_not_in_prose:
            print("Slugs in related_thinkers but not mentioned in prose:")
            for slug in d.slugs_not_in_prose:
                canon = thinker_index[slug].canonical
                print(f"  - {slug} (canonical name \"{canon}\" not found in summary/key_points)")
        if d.names_not_in_slugs:
            print("Names in prose but not in related_thinkers:")
            for name in d.names_not_in_slugs:
                print(f"  - \"{name}\" appears in summary/key_points; slug missing from related_thinkers")
        print()

    print("=== Summary ===")
    sn = sum(len(d.slugs_not_in_prose) for d in discrepancies)
    ns = sum(len(d.names_not_in_slugs) for d in discrepancies)
    print(f"slugs-not-in-prose: {sn} total across {sum(1 for d in discrepancies if d.slugs_not_in_prose)} MDs")
    print(f"names-not-in-slugs: {ns} total across {sum(1 for d in discrepancies if d.names_not_in_slugs)} MDs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.2.2: Re-run pytest — expect import to succeed but no tests defined yet**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_readiness_audits.py -v 2>&1 | tail -5
# Expected: "no tests ran" or "collected 0 items".
```

### Task 2.3: Write failing tests + verify they fail

**Files:**
- Modify: `scripts/synthesis/tests/test_readiness_audits.py`

- [ ] **Step 2.3.1: Append the 5 Stream-C tests**

Append to `scripts/synthesis/tests/test_readiness_audits.py`:

```python
# -------- audit-cross-refs.py tests --------

ThinkerInfo = cross_refs.ThinkerInfo


def _idx(*infos: ThinkerInfo) -> dict[str, ThinkerInfo]:
    return {i.slug: i for i in infos}


def test_slug_not_in_prose_simple(tmp_path):
    """A related_thinker whose canonical name is absent from prose → reported."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers:\n  - milton-friedman\n"
        "summary: This essay discusses economic policy in postwar India.\n"
        "---\n"
        "## Summary\n\nMore prose here.\n\n## Key points\n\n- a point\n"
    )
    idx = _idx(ThinkerInfo(slug="milton-friedman", canonical="Milton Friedman"))
    d = cross_refs._check_md(md, idx)
    assert d.slugs_not_in_prose == ["milton-friedman"]
    assert d.names_not_in_slugs == []


def test_slug_in_prose_via_aka(tmp_path):
    """A related_thinker whose canonical is absent but an also_known_as is present → not reported."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers:\n  - bhimrao-ambedkar\n"
        "summary: The work cites Dr Ambedkar's writings on caste.\n"
        "---\n"
        "## Summary\n\n"
    )
    idx = _idx(ThinkerInfo(
        slug="bhimrao-ambedkar",
        canonical="Bhimrao Ramji Ambedkar",
        also_known_as=["Dr Ambedkar", "B. R. Ambedkar"],
    ))
    d = cross_refs._check_md(md, idx)
    assert d.slugs_not_in_prose == []


def test_prose_name_not_in_slugs(tmp_path):
    """A thinker named in prose but absent from related_thinkers → reported."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers: []\n"
        "summary: Friedrich Hayek's Road to Serfdom is invoked.\n"
        "---\n"
    )
    idx = _idx(ThinkerInfo(slug="friedrich-hayek", canonical="Friedrich Hayek"))
    d = cross_refs._check_md(md, idx)
    assert "Friedrich Hayek" in d.names_not_in_slugs
    assert d.slugs_not_in_prose == []


def test_whole_word_match(tmp_path):
    """\"Smithson\" must NOT match \"Adam Smith\"."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers: []\n"
        "summary: The Smithsonian holds important documents.\n"
        "---\n"
    )
    idx = _idx(ThinkerInfo(slug="adam-smith", canonical="Adam Smith"))
    d = cross_refs._check_md(md, idx)
    assert d.names_not_in_slugs == []


def test_case_insensitive_match(tmp_path):
    """\"milton FRIEDMAN\" should match \"Milton Friedman\"."""
    md = tmp_path / "foo.md"
    md.write_text(
        "---\n"
        "id: foo\n"
        "related_thinkers:\n  - milton-friedman\n"
        "summary: milton FRIEDMAN once wrote about monetary policy.\n"
        "---\n"
    )
    idx = _idx(ThinkerInfo(slug="milton-friedman", canonical="Milton Friedman"))
    d = cross_refs._check_md(md, idx)
    assert d.slugs_not_in_prose == []
```

- [ ] **Step 2.3.2: Run, expect 5/5 PASS (the implementation in Task 2.2 already satisfies them)**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_readiness_audits.py -v 2>&1 | tail -15
# Expected: 5 passed.
# (We wrote the impl first then tests because the impl is the spec'd output; "TDD" here
# means tests-immediately-after, with the impl committed atomically in Step 2.4.)
```

### Task 2.4: Commit Stream-C script + tests

- [ ] **Step 2.4.1: Stage + commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add scripts/synthesis/audit-cross-refs.py scripts/synthesis/tests/test_readiness_audits.py
git commit -m "feat(synthesis): add audit-cross-refs.py for slug↔prose drift"
```

- [ ] **Step 2.4.2: Push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
git push origin main
git log --oneline origin/main..HEAD
# Expected: empty.
```

### Task 2.5: Run the audit and capture output

- [ ] **Step 2.5.1: Run against the live corpus**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/audit-cross-refs.py \
  > /tmp/v1.5-readiness-stream-c.log 2>&1
head -10 /tmp/v1.5-readiness-stream-c.log
wc -l /tmp/v1.5-readiness-stream-c.log
# Keep the log around — Chunk 4 (findings doc) will quote summary numbers + top examples from it.
```

---

## Chunk 3: Stream D — `audit-thinkers-without-quotes.py` (TDD)

Goal: TDD-build a read-only audit that produces a corpus-wide inverted index of `thinker_mentions[].evidence[].quote` per thinker and surfaces thinkers with zero inbound quotes.

### Task 3.1: Create `audit-thinkers-without-quotes.py`

**Files:**
- Create: `scripts/synthesis/audit-thinkers-without-quotes.py`

- [ ] **Step 3.1.1: Create the script**

Create `scripts/synthesis/audit-thinkers-without-quotes.py` with:

```python
#!/usr/bin/env python3
"""
audit-thinkers-without-quotes.py — corpus-wide audit of pull-quote attribution.

Builds an inverted index from each thinker MD's slug to the count of inbound
thinker_mentions[].evidence[].quote entries across the corpus (primary-works,
opinions, musings, interviews, theprint-mirror). Surfaces thinkers with zero
inbound quotes, sorted by canon_status (canonical > referenced > stub > other)
so canonical thinkers without quote-coverage rise to the top.

Reads:
  apps/site/src/content/thinkers/*.md
  apps/site/src/content/{primary-works,opinions,musings,interviews,theprint-mirror}/*.md

Writes:
  stdout report (captured into docs/handoffs/2026-05-27-content-readiness-pass-1.md).

Run:
  .venv-extract/bin/python3 scripts/synthesis/audit-thinkers-without-quotes.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = REPO_ROOT / "apps" / "site" / "src" / "content"
THINKERS_DIR = CONTENT_ROOT / "thinkers"
IN_SCOPE = ("primary-works", "opinions", "musings", "interviews", "theprint-mirror")

CANON_PRIORITY = {"canonical": 0, "referenced": 1, "stub": 2}

_FM_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def _extract_mentions(md_text: str) -> list[tuple[str, int]]:
    """Parse one MD's frontmatter; return list of (thinker_slug, quote_count) tuples.

    quote_count is the number of non-empty `evidence[].quote` strings under that mention.
    A mention with empty/missing evidence contributes 0 quotes (the mention exists, but
    isn't quote-attributed — different signal).
    """
    m = _FM_RX.match(md_text)
    if not m:
        return []
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return []
    mentions = fm.get("thinker_mentions") or []
    if not isinstance(mentions, list):
        return []
    out: list[tuple[str, int]] = []
    for entry in mentions:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("thinker")
        if not isinstance(slug, str) or not slug:
            continue
        evidence = entry.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        qcount = sum(
            1 for ev in evidence
            if isinstance(ev, dict)
            and isinstance(ev.get("quote"), str)
            and ev["quote"].strip()
        )
        out.append((slug, qcount))
    return out


def _build_inverted_index(md_paths: list[Path]) -> Counter:
    """Return Counter mapping thinker_slug → total inbound evidence-quote count."""
    idx: Counter = Counter()
    skipped = 0
    for p in md_paths:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped += 1
            continue
        for slug, qcount in _extract_mentions(text):
            idx[slug] += qcount
    if skipped:
        print(f"Warning: skipped {skipped} unreadable MD(s)", file=sys.stderr)
    return idx


def _load_thinker_canon(thinkers_dir: Path) -> dict[str, dict]:
    """Return slug → {canon_status, canonical_name} for every thinker MD."""
    out: dict[str, dict] = {}
    for md in sorted(thinkers_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FM_RX.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        slug = fm.get("id") or md.stem
        out[slug] = {
            "canon_status": fm.get("canon_status") or "unknown",
            "canonical_name": ((fm.get("name") or {}).get("canonical") or "").strip(),
        }
    return out


def _format_report(canon: dict[str, dict], inverted: Counter) -> str:
    """Compose the stdout report. Returns a single string for testability."""
    total_thinkers = len(canon)
    with_quotes = sum(1 for slug in canon if inverted.get(slug, 0) > 0)
    without_quotes = total_thinkers - with_quotes

    lines: list[str] = []
    lines.append("=== Thinkers without inbound pull-quote attribution ===")
    lines.append(f"Total thinker files: {total_thinkers}")
    lines.append(f"Thinkers with ≥1 quote: {with_quotes}")
    lines.append(f"Thinkers with 0 quotes: {without_quotes}")
    lines.append("")
    lines.append("Caveat: ~58% of the corpus lacks any thinker_mentions because the")
    lines.append("NER pipeline hasn't been run on the recent extraction-pipeline output.")
    lines.append("This number will drop sharply after the post-batch NER run.")
    lines.append("")
    lines.append("Broken down by canon_status:")
    status_counter: dict[str, dict[str, int]] = {}
    for slug, info in canon.items():
        st = info["canon_status"]
        bucket = status_counter.setdefault(st, {"with": 0, "without": 0})
        if inverted.get(slug, 0) > 0:
            bucket["with"] += 1
        else:
            bucket["without"] += 1
    for st in sorted(status_counter, key=lambda s: CANON_PRIORITY.get(s, 99)):
        b = status_counter[st]
        lines.append(f"  {st:<12} — {b['with']} with quotes, {b['without']} without")
    lines.append("")

    def _section(title: str, status: str):
        lines.append(f"=== {title} ===")
        zeros = sorted(
            slug for slug in canon
            if canon[slug]["canon_status"] == status and inverted.get(slug, 0) == 0
        )
        for slug in zeros:
            lines.append(f"  {slug}  ({canon[slug]['canonical_name']})")
        if not zeros:
            lines.append("  (none)")
        lines.append("")

    _section("Canonical thinkers with zero quotes", "canonical")
    _section("Referenced thinkers with zero quotes", "referenced")

    return "\n".join(lines)


def main() -> int:
    canon = _load_thinker_canon(THINKERS_DIR)
    md_paths: list[Path] = []
    for sub in IN_SCOPE:
        md_paths.extend(sorted((CONTENT_ROOT / sub).glob("*.md")))
    inverted = _build_inverted_index(md_paths)
    print(_format_report(canon, inverted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3.1.2: Verify import works**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -c "
import sys, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location(
    'audit_thinkers_without_quotes',
    'scripts/synthesis/audit-thinkers-without-quotes.py',
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod._extract_mentions)
print(mod._build_inverted_index)
print(mod._format_report)
"
# Expected: three function repr lines printed.
```

### Task 3.2: Append the 5 Stream-D tests

**Files:**
- Modify: `scripts/synthesis/tests/test_readiness_audits.py`

- [ ] **Step 3.2.1: Append tests**

Append to `scripts/synthesis/tests/test_readiness_audits.py`:

```python
# -------- audit-thinkers-without-quotes.py tests --------

quotes_audit = _load("audit-thinkers-without-quotes")


def test_count_single_quote():
    """One MD with one evidence quote for thinker X → X has count 1."""
    text = (
        "---\n"
        "id: foo\n"
        "thinker_mentions:\n"
        "  - thinker: adam-smith\n"
        "    role: mention\n"
        "    evidence:\n"
        "      - quote: \"He cites Smith on the division of labour.\"\n"
        "        context: ctx\n"
        "---\n"
    )
    mentions = quotes_audit._extract_mentions(text)
    assert mentions == [("adam-smith", 1)]


def test_count_multiple_quotes_same_thinker():
    """One MD with three evidence quotes for X → X has count 3."""
    text = (
        "---\n"
        "id: foo\n"
        "thinker_mentions:\n"
        "  - thinker: adam-smith\n"
        "    evidence:\n"
        "      - quote: q1\n"
        "      - quote: q2\n"
        "      - quote: q3\n"
        "---\n"
    )
    mentions = quotes_audit._extract_mentions(text)
    assert mentions == [("adam-smith", 3)]


def test_skip_empty_thinker_mentions():
    """MD with empty thinker_mentions: [] → contributes nothing."""
    text = (
        "---\n"
        "id: foo\n"
        "thinker_mentions: []\n"
        "---\n"
    )
    assert quotes_audit._extract_mentions(text) == []


def test_skip_malformed_md():
    """MD with malformed YAML → returns [], doesn't crash."""
    text = "---\nid: foo\nthinker_mentions: [unclosed list\n---\n"
    assert quotes_audit._extract_mentions(text) == []


def test_format_report_sort_by_canon_status():
    """canonical entries listed in their own section above referenced entries."""
    from collections import Counter
    canon = {
        "a-canonical-no-quotes": {"canon_status": "canonical", "canonical_name": "Alpha Canon"},
        "b-canonical-with-quotes": {"canon_status": "canonical", "canonical_name": "Beta Canon"},
        "c-referenced-no-quotes": {"canon_status": "referenced", "canonical_name": "Gamma Ref"},
        "d-stub-no-quotes": {"canon_status": "stub", "canonical_name": "Delta Stub"},
    }
    inverted: Counter = Counter({"b-canonical-with-quotes": 2})
    report = quotes_audit._format_report(canon, inverted)
    # Canonical-zero block precedes referenced-zero block in the output.
    canonical_idx = report.index("Canonical thinkers with zero quotes")
    referenced_idx = report.index("Referenced thinkers with zero quotes")
    assert canonical_idx < referenced_idx
    # Beta Canon (the one WITH quotes) should NOT appear in either zero list.
    canonical_zero_section = report[canonical_idx:referenced_idx]
    assert "b-canonical-with-quotes" not in canonical_zero_section
    assert "a-canonical-no-quotes" in canonical_zero_section
    # Gamma Ref should appear in the referenced zero section.
    referenced_zero_section = report[referenced_idx:]
    assert "c-referenced-no-quotes" in referenced_zero_section
```

- [ ] **Step 3.2.2: Run all 10 tests**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_readiness_audits.py -v 2>&1 | tail -20
# Expected: 10 passed (5 from Chunk 2 + 5 new).
```

### Task 3.3: Commit + push Stream-D

- [ ] **Step 3.3.1: Commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add scripts/synthesis/audit-thinkers-without-quotes.py scripts/synthesis/tests/test_readiness_audits.py
git commit -m "feat(synthesis): add audit-thinkers-without-quotes.py for inbound quote coverage"
```

- [ ] **Step 3.3.2: Push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
git push origin main
git log --oneline origin/main..HEAD
# Expected: empty.
```

### Task 3.4: Run the audit and capture output

- [ ] **Step 3.4.1: Run**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/audit-thinkers-without-quotes.py \
  > /tmp/v1.5-readiness-stream-d.log 2>&1
head -30 /tmp/v1.5-readiness-stream-d.log
wc -l /tmp/v1.5-readiness-stream-d.log
# Keep the log around — Chunk 4 will quote summary numbers + top-of-list entries from it.
```

---

## Chunk 4: Findings document + handoff

Goal: hand-author the findings document from the captured outputs of Streams A, B, C, D + a pointer to follow-ups.

### Task 4.1: Compose the findings doc

**Files:**
- Create: `docs/handoffs/2026-05-27-content-readiness-pass-1.md`

- [ ] **Step 4.1.1: Capture audit-time snapshot SHA**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
SNAPSHOT_SHA=$(git rev-parse --short HEAD)
echo "SNAPSHOT_SHA=$SNAPSHOT_SHA"
# This is the SHA the findings doc cites as "the state of the corpus at audit time."
```

- [ ] **Step 4.1.1b: Re-verify Stream B's "53/53 resolve" claim before quoting it**

The Stream B finding was pre-computed during brainstorming. New MDs may have landed since (the extraction pipeline is still running), which could introduce new thinker slugs.

```bash
cd "/Users/siraj/Indian Liberals Website"
SLUGS=$(git log --diff-filter=A --name-only --pretty=format: b6be9fe..HEAD \
  -- apps/site/src/content/primary-works/ \
  | grep '\.md$' | sort -u \
  | xargs awk '/^related_thinkers:/{flag=1;next} flag && /^[a-z_]+:/{flag=0} flag && /^  - /{gsub(/^  - /,""); print}' \
  | sort -u)
NEW_MD_N=$(git log --diff-filter=A --name-only --pretty=format: b6be9fe..HEAD \
  -- apps/site/src/content/primary-works/ | grep -c '\.md$')
TOTAL_SLUGS=$(echo "$SLUGS" | grep -c .)
MISSING=$(for s in $SLUGS; do [ -f "apps/site/src/content/thinkers/$s.md" ] || echo "$s"; done | wc -l | tr -d ' ')
RESOLVED=$((TOTAL_SLUGS - MISSING))
echo "NEW_MD_N=$NEW_MD_N"
echo "TOTAL_SLUGS=$TOTAL_SLUGS"
echo "RESOLVED=$RESOLVED"
echo "MISSING=$MISSING"
# If MISSING > 0, list them so the findings doc can name them:
if [ "$MISSING" -gt 0 ]; then
  echo "--- missing slugs (no thinker MD) ---"
  for s in $SLUGS; do [ -f "apps/site/src/content/thinkers/$s.md" ] || echo "$s"; done
fi
# Use the live numbers in the findings doc — NOT the brainstorming-time "53/53".
```

- [ ] **Step 4.1.2: Extract summary numbers from the Stream-C and Stream-D logs**

```bash
cd "/Users/siraj/Indian Liberals Website"
echo "=== Stream C summary ==="
grep -E "^(Total new MDs|MDs with|slugs-not-in|names-not-in)" /tmp/v1.5-readiness-stream-c.log
echo
echo "=== Stream D summary ==="
sed -n '1,15p' /tmp/v1.5-readiness-stream-d.log
echo
echo "=== Stream A apply count ==="
grep -E "^\s+(inserted|skip-existing|skip-no-frontmatter|replaced):" \
  /tmp/v1.5-readiness-apply.log 2>/dev/null \
  || echo "(no apply log — Stream A was a no-op)"
```

- [ ] **Step 4.1.3: Author the findings doc**

Create `docs/handoffs/2026-05-27-content-readiness-pass-1.md`. Use this template; fill the `<...>` placeholders from the numbers captured in Step 4.1.2 and from the Stream-C/D logs. Include up to ~10 representative example lines per discrepancy section (truncate longer lists with "...").

```markdown
# Content-Readiness Pass 1 — Findings

**Date:** 2026-05-27
**Scope:** primary-works MDs added by the v1.5 extraction batch (currently in progress).
**Reference SHAs:**
- Pre-extension baseline: `b6be9fe`
- Audit-time snapshot: `<SNAPSHOT_SHA>`

## Stream A — PDF URL apply (write action)

- Matched & applied: **<APPLIED_N>** high-confidence (exact + high tiers).
- Surfaced for editorial review: **<MEDIUM_N>** medium-confidence, **<PAGE_N>** page-only candidates in `data/pdf-link-manifest.tsv`.
- Misses (no candidate found): **<MISS_N>** in `data/pdf-link-misses.tsv`.
- Commit: `<APPLY_COMMIT_SHA>` (or "no-op — 0 high-confidence rows" if APPLIED_N == 0).

## Stream B — New thinker slugs

- **0 new thinker stubs created** (the extraction pipeline emits primary-works only; thinker stubs come from the byline-resolution pipeline, which has not been re-run for this batch).
- Distinct thinker slugs referenced by the **<NEW_MD_N>** new MDs: **<TOTAL_SLUGS>**.
- Resolved to existing thinker files: **<RESOLVED>**.
- Missing (no thinker file): **<MISSING>**. <If MISSING > 0, list the slugs and add to the follow-ups section as "create thinker stubs for: ...".>

## Stream C — Cross-reference drift (new MDs only)

Heuristic substring scan; not exhaustive. See `scripts/synthesis/audit-cross-refs.py` for details.

- Total new MDs scanned: **<NEW_MD_N>**
- MDs with at least one discrepancy: **<DISC_MD_N>**
- Slugs in `related_thinkers` but absent from prose: **<SN_TOTAL>** rows across **<SN_MDS>** MDs.
- Names in prose but absent from `related_thinkers`: **<NS_TOTAL>** rows across **<NS_MDS>** MDs.

**Representative examples** (up to 10 per category):

Slugs not in prose:
- `<md-slug>`: <slug> (canonical "<Name>" not found in summary/key_points)
- ...

Names not in slugs:
- `<md-slug>`: "<Name>" mentioned in prose; slug missing from related_thinkers
- ...

Full output: `/tmp/v1.5-readiness-stream-c.log`.

## Stream D — Thinkers without inbound quote-attribution

- Thinkers with 0 quotes: **<NO_Q_N>** of **<TOTAL_THINKERS>** total.
- Of those, canon_status == canonical: **<CANON_NO_Q>**
- Of those, canon_status == referenced: **<REF_NO_Q>**

**Caveat:** ~58% of the corpus has empty `thinker_mentions[]` because the NER pipeline hasn't been run on the recent extraction-pipeline output. This count will drop sharply after the post-batch NER run.

**Top 20 canonical thinkers with zero inbound quotes:**

- `<slug>` — <Canonical Name>
- ...

Full output: `/tmp/v1.5-readiness-stream-d.log`.

## Follow-ups for the next session

1. **Run NER on the new MDs** (and any additional MDs the still-running extraction emits) once the Claude rate-limit window resets. ~2 Claude calls per MD; ~600 calls total; cheaper to run once after the full batch than in pieces.
2. **Editorial review of medium-confidence pdf_url candidates** in `data/pdf-link-manifest.tsv`. Likely a manual eyeball pass.
3. **Editorial review of cross-reference discrepancies** in Stream C — some are real missed tags worth correcting, some are heuristic noise (Smith-vs-Smithsonian-style).
4. **Building thinker bios for canonical-without-quotes entries** that have high reader interest. Separate editorial workstream.
5. **Refreshing `data/prod-mirror/inventory.jsonl`** if prod has gained new pages since May 26.
6. **`auto-hide-orphans.py`** pass after the NER work lands.
```

### Task 4.2: Commit + push the findings doc

- [ ] **Step 4.2.1: Stage + commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
mkdir -p docs/handoffs
git add docs/handoffs/2026-05-27-content-readiness-pass-1.md
git commit -m "docs(handoff): content-readiness pass 1 — Streams A/B/C/D findings"
```

- [ ] **Step 4.2.2: Push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
git push origin main
git log --oneline origin/main..HEAD
# Expected: empty.
```

---

## Final acceptance

- [ ] **Acceptance #1:** `pnpm build` exits clean; page count unchanged from pre-Stream-A baseline plus any new MDs the runner emitted during the pass.
- [ ] **Acceptance #2:** Stream A's apply commit (if non-empty) sits on `origin/main` with subject `data(primary-works): apply N high-confidence pdf_urls from prod reconciliation`.
- [ ] **Acceptance #3:** Both audit commits sit on `origin/main` with subjects `feat(synthesis): add audit-cross-refs.py …` and `feat(synthesis): add audit-thinkers-without-quotes.py …`.
- [ ] **Acceptance #4:** `pytest scripts/synthesis/tests/test_readiness_audits.py -v` shows 10/10 passing.
- [ ] **Acceptance #5:** Findings doc exists at `docs/handoffs/2026-05-27-content-readiness-pass-1.md` with all four streams' sections populated from real audit numbers (no placeholder `<…>` left).
- [ ] **Acceptance #6:** Extraction pipeline still at PID 43187 (or has completed naturally) — we never killed or paused it.
- [ ] **Acceptance #7:** `git log origin/main..HEAD` is empty (everything pushed).

---

## Out of scope (per spec §2)

- Running NER / mention pipeline on the new MDs.
- Applying medium / page-only tier pdf_urls.
- Creating thinker stubs (none needed — Stream B confirmed).
- Modifying Astro components, schemas, or styling.
- Re-scraping prod.
- Touching the still-running extraction process.

---

## Plan complete

After all four chunks pass:

1. The terminal state is:
   - ≥ 60 (likely ≥ 80) new pdf_urls live on `origin/main`.
   - Two read-only audit scripts under `scripts/synthesis/` with 10 unit tests.
   - One findings doc at `docs/handoffs/2026-05-27-content-readiness-pass-1.md`.
   - The still-running extraction pipeline unaffected.
2. Adnan reads the findings doc and decides next-session priorities (NER run, editorial review of medium-confidence pdf_urls, cross-reference cleanup, etc.).
