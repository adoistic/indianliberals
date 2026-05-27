# Interviews into Primary-Works — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold the 72 interview MDs into the primary-works collection (deterministic migration), then enrich each one with LLM-extracted thinker_mentions / summary / key_points / themes / interviewer from the already-produced cleaned diarized transcripts at `data/interview-transcripts/<slug>.cleaned.md`. After this plan, `interviews` is no longer a separate content collection.

**Architecture:** Five chunks landing on `main`. Chunk 1 = schema additions + repo-state setup. Chunk 2 = TDD'd migration script (pure-logic helpers + driver). Chunk 3 = run Phase A migration + remove the old collection + nav link. Chunk 4 = TDD'd enrichment script. Chunk 5 = run Phase B enrichment in batches of 10 commits, final acceptance.

**Tech Stack:** Python 3.14 in `.venv-extract/`, `pyyaml` for frontmatter, `claude -p` for LLM enrichment, `git` + `pnpm build` for verification, Astro 5 (existing).

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `apps/site/src/content.config.ts` | MODIFY | Add `'interview'` to `work_type` enum; add `youtube_url` + `'unavailable'` to `transcript_status`; remove the `interviews` collection block. |
| `apps/site/src/components/Header.astro` | MODIFY | Remove the "Interviews" nav-bar link. |
| `apps/site/src/content/interviews/` | DELETE | Whole dir removed after migration. |
| `apps/site/src/content/primary-works/<slug>.md` | CREATE × 72 | One new MD per migrated interview (with `work_type: 'interview'`). |
| `scripts/synthesis/migrate-interviews-to-primary-works.py` | CREATE (~200 lines) | Phase A deterministic migration. |
| `scripts/synthesis/enrich-interview-mds.py` | CREATE (~250 lines) | Phase B LLM enrichment. |
| `scripts/synthesis/tests/test_migrate_interviews.py` | CREATE (~120 lines) | 7 unit tests for Phase A helpers. |
| `scripts/synthesis/tests/test_enrich_interviews.py` | CREATE (~120 lines) | 5 unit tests for Phase B helpers. |
| `/tmp/interview-enrich-fails.tsv` | RUNTIME | Per-MD enrichment failures (not in repo). |
| `/tmp/interview-enrich-progress.tsv` | RUNTIME | Per-MD enrichment status (not in repo). |

**File-size budget:** ~700 lines of new Python + ~5 lines added / ~20 lines removed in `content.config.ts` + 1 line removed in `Header.astro`.

---

## Conventions to honour

- **venv:** `.venv-extract/bin/python3` for all script + pytest runs.
- **Test command:** `.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_migrate_interviews.py scripts/synthesis/tests/test_enrich_interviews.py -v`
- **Commit prefixes:**
  - `feat(content):` for schema / migration commits
  - `feat(synthesis):` for the new scripts + tests
  - `data(primary-works):` for the actual MD writes in Phase B batches
- **No `Co-Authored-By` trailer.**
- **Push policy:** push after every chunk. Before pushing, run `git fetch origin && git rebase origin/main` to pick up any concurrent commits.
- **v1.5 extraction:** assumed paused at plan-start time (the brainstorm session killed PID 77356 earlier). Pre-work Step 0.1 verifies no v1.5 process is alive. **Do not relaunch v1.5 until Phase B completes** — it would compete with the enrichment for Claude rate-limit headroom.

---

## Pre-work baseline (run once before Chunk 1)

- [ ] **Step 0.1: Confirm no v1.5 extraction is running + cleanup is done**

```bash
cd "/Users/siraj/Indian Liberals Website"
PID=$(cat /tmp/v1.5-overnight-v2.pid 2>/dev/null)
ps -p "$PID" >/dev/null 2>&1 && echo "✗ v1.5 still alive — STOP and pause it" || echo "✓ v1.5 not running"

# Cleanup state — should be 70 .txt files matched 1:1 with .cleaned.md (modulo a-d-shroff SKIP_EMPTY)
TXT=$(ls data/interview-transcripts/*.txt 2>/dev/null | wc -l | tr -d ' ')
CLEAN=$(ls data/interview-transcripts/*.cleaned.md 2>/dev/null | wc -l | tr -d ' ')
echo "txt: $TXT  cleaned: $CLEAN  (expected 70 each, modulo small drift)"
[ "$CLEAN" -lt 65 ] && echo "✗ cleanup not done — wait for it to finish" || echo "✓ cleanup essentially done"
```

If v1.5 is alive or cleanup is < 65 .cleaned.md: STOP and surface to controller.

- [ ] **Step 0.2: Flush any pending v1.5 writes** (manual flush, same as content-readiness-pass-1)

```bash
cd "/Users/siraj/Indian Liberals Website"
PENDING_NEW=$(git ls-files --others --exclude-standard -- apps/site/src/content/primary-works/ | grep -c '\.md$' || true)
PENDING_MOD=$(git diff --name-only -- apps/site/src/content/primary-works/ | wc -l | tr -d ' ')
echo "pending new MDs: $PENDING_NEW"
echo "pending modified MDs: $PENDING_MOD"

if [ "$PENDING_NEW" -gt 0 ]; then
  # Stage and commit them as a manual flush (the v1.5 committer thread couldn't because the process died)
  git ls-files --others --exclude-standard -- apps/site/src/content/primary-works/ | grep '\.md$' | xargs git add
  git commit -m "data(primary-works): flush N pending v1.5 MDs before interviews migration"
fi

# Also commit modified data/extraction-log.jsonl if present
git diff --name-only data/extraction-log.jsonl | grep -q . && \
  git add data/extraction-log.jsonl && \
  git commit -m "data(extraction-log): flush before interviews migration"
```

- [ ] **Step 0.3: Capture pre-work snapshot SHA + counts**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
PRE_PLAN_SHA=$(git rev-parse --short HEAD)
PRE_PW_COUNT=$(ls apps/site/src/content/primary-works/*.md | wc -l | tr -d ' ')
INT_COUNT=$(ls apps/site/src/content/interviews/*.md | wc -l | tr -d ' ')
echo "PRE_PLAN_SHA=$PRE_PLAN_SHA"
echo "PRE_PW_COUNT=$PRE_PW_COUNT  (primary-works MDs before this plan)"
echo "INT_COUNT=$INT_COUNT  (interview MDs to migrate; expected 72)"
```

If `INT_COUNT != 72`, surface to controller — the migration count assumption is wrong.

- [ ] **Step 0.4: Confirm build is clean before any edits**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build > /tmp/interviews-plan-pre-build.log 2>&1 && tail -3 /tmp/interviews-plan-pre-build.log
[ -L public/pagefind ] || ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/interviews-plan-pre-build.log
# Expected: 0 (clean baseline)
```

If non-zero, STOP — fix upstream before proceeding.

---

## Chunk 1: Schema additions

Goal: extend the `primaryWorks` Zod schema to accept `'interview'` as a `work_type`, add the optional `youtube_url` field, and add `'unavailable'` to `transcript_status`. Build must still pass — no schema validations should break.

### Task 1.1: Inspect current schema + nav file

- [ ] **Step 1.1.1: Read the relevant section of `content.config.ts`**

```bash
cd "/Users/siraj/Indian Liberals Website"
grep -n "work_type\|transcript_status\|^const interviews\|^const primaryWorks" apps/site/src/content.config.ts
```

Note the line numbers for: the `work_type` enum (in the `primaryWorks` collection), the `interviews` collection definition (to be removed in Chunk 3), the collections map at the bottom.

- [ ] **Step 1.1.2: Find the "Interviews" nav link in Header.astro**

```bash
grep -n "Interview\|interview" apps/site/src/components/Header.astro
```

Note the line number — Chunk 3 deletes that line.

### Task 1.2: Extend the primary-works schema

**Files:**
- Modify: `apps/site/src/content.config.ts`

- [ ] **Step 1.2.1: Add `'interview'` to the `work_type` enum**

In the `primaryWorks` collection's `work_type: z.enum([...])` array, add `'interview'` as the final entry (preserving existing order):

Before:
```ts
work_type: z.enum([
  'book',
  'pamphlet',
  'speech',
  'essay',
  'edited_volume',
  'occasional_paper',
  'letter',
  'correspondence',
  'periodical_issue',
  'reference',
]),
```

After:
```ts
work_type: z.enum([
  'book',
  'pamphlet',
  'speech',
  'essay',
  'edited_volume',
  'occasional_paper',
  'letter',
  'correspondence',
  'periodical_issue',
  'reference',
  'interview',
]),
```

- [ ] **Step 1.2.2: Add `youtube_url` + `transcript_status` fields to primary-works**

Find an appropriate insertion point near the other optional metadata fields in the `primaryWorks` schema (after `provenance` block, before `rights` block — read the file to confirm the convention). Add:

```ts
    youtube_url: z.string().url().optional(),
    transcript_status: z.enum(['none', 'partial', 'complete', 'unavailable']).default('none'),
```

The placement is cosmetic — Zod doesn't care about field order. Use the closest "metadata about the work itself" group.

- [ ] **Step 1.2.3: Verify the schema edit by re-grepping**

```bash
cd "/Users/siraj/Indian Liberals Website"
grep -A 12 "work_type: z.enum" apps/site/src/content.config.ts
grep "youtube_url\|transcript_status" apps/site/src/content.config.ts | head -5
```

Expected: `'interview'` appears in the enum; `youtube_url` and `transcript_status` appear in the primary-works schema (plus the existing duplicates in the `interviews` schema block, which will be removed in Chunk 3).

### Task 1.3: Build sanity

- [ ] **Step 1.3.1: Build must still pass (the schema change is additive)**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build > /tmp/interviews-chunk1-build.log 2>&1 && tail -3 /tmp/interviews-chunk1-build.log
[ -L public/pagefind ] || ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/interviews-chunk1-build.log
# Expected: 0 — the additions are backward-compatible (new enum value + optional fields).
```

### Task 1.4: Commit + push

- [ ] **Step 1.4.1: Commit the schema additions**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/content.config.ts
git commit -m "feat(content): extend primary-works schema for interviews

Adds 'interview' to the work_type enum, plus optional youtube_url and
transcript_status fields. Sets up the schema for the interviews→primary-works
migration in subsequent chunks. The interviews collection itself stays
in place for now; removal happens in Chunk 3 after MDs are migrated."
```

- [ ] **Step 1.4.2: Push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
git push origin main
git log --oneline origin/main..HEAD
# Expected: empty.
```

---

## Chunk 2: `migrate-interviews-to-primary-works.py` (TDD)

Goal: TDD-build the Phase A migration script's pure-logic helpers, then write the driver. Driver is smoke-tested in Chunk 3 (not unit-tested directly).

### Task 2.1: Test file scaffolding

**Files:**
- Create: `scripts/synthesis/tests/test_migrate_interviews.py`
- Create: `scripts/synthesis/migrate-interviews-to-primary-works.py`

- [ ] **Step 2.1.1: Create the test file with the importlib loader pattern**

The existing convention is at `scripts/synthesis/tests/test_apply_pdf_urls.py` and `test_readiness_audits.py`. Use the same pattern with the Python 3.14 sys.modules adaptation:

```python
"""Unit tests for migrate-interviews-to-primary-works.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _load(stem: str):
    mod_name = stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(
        mod_name,
        str(SCRIPTS_DIR / f"{stem}.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve cls.__module__ in Python 3.14
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


migrate = _load("migrate-interviews-to-primary-works")
```

- [ ] **Step 2.1.2: Create the migration script's skeleton (will fail import — that's correct)**

```bash
cd "/Users/siraj/Indian Liberals Website"
touch scripts/synthesis/migrate-interviews-to-primary-works.py
```

The file is empty for now. Pytest will fail import — expected at this step.

- [ ] **Step 2.1.3: Run pytest — expect import to fail**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_migrate_interviews.py -v 2>&1 | tail -5
# Expected: collection error (empty module has no `parse_frontmatter` etc.).
```

### Task 2.2: Skeleton + first helper — `parse_frontmatter` (TDD)

**Files:**
- Modify: `scripts/synthesis/migrate-interviews-to-primary-works.py`
- Modify: `scripts/synthesis/tests/test_migrate_interviews.py`

- [ ] **Step 2.2.1: Add the script's imports + constants + first helper stub**

Write to `scripts/synthesis/migrate-interviews-to-primary-works.py`:

```python
#!/usr/bin/env python3
"""Phase A: deterministic migration of interview MDs into primary-works.

For each MD under apps/site/src/content/interviews/:
  - parse frontmatter
  - build a primary-work-shaped frontmatter (work_type='interview', authors,
    contributors, publication, youtube_url, transcript_status, description if any)
  - replace body with the cleaned transcript content (or a placeholder if missing)
  - write to apps/site/src/content/primary-works/<slug>.md
  - delete the source interview MD only AFTER successful write

Pure-logic helpers are unit-tested in scripts/synthesis/tests/test_migrate_interviews.py.
The main driver runs once over all 72 MDs.

Run:
    .venv-extract/bin/python3 scripts/synthesis/migrate-interviews-to-primary-works.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERVIEWS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "interviews"
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
TRANSCRIPT_DIR = REPO_ROOT / "data" / "interview-transcripts"
THINKERS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "thinkers"

# WP-garbage tail strip, per spec §5.2.
_WP_TAIL_RX = re.compile(
    r"\s*_?\s*type=content&[\s\S]*?Needs editorial review\._?\s*$",
    re.M,
)
# Leading "linked-source" boilerplate sometimes precedes the type=content tail,
# e.g., `[Read more](https://...]_.` from the prior WordPress export.
_WP_LINK_LEAD_RX = re.compile(r"^[\s\S]*?\]_\.\s*", re.M)

_FM_BLOCK_RX = re.compile(r"^---\n([\s\S]*?)\n---\n?([\s\S]*)$", re.M)


def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Empty dict if no frontmatter found."""
    m = _FM_BLOCK_RX.match(md_text)
    if not m:
        return {}, md_text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), m.group(2)
```

- [ ] **Step 2.2.2: Add the first test (parse_frontmatter basic)**

Append to `scripts/synthesis/tests/test_migrate_interviews.py`:

```python
# -------- parse_frontmatter tests --------


def test_parse_frontmatter_extracts_dict_and_body():
    md = "---\nid: foo\ntitle: Bar\n---\nbody text here\n"
    fm, body = migrate.parse_frontmatter(md)
    assert fm == {"id": "foo", "title": "Bar"}
    assert body == "body text here\n"


def test_parse_frontmatter_returns_empty_on_no_frontmatter():
    md = "no frontmatter here, just body"
    fm, body = migrate.parse_frontmatter(md)
    assert fm == {}
    assert body == md
```

- [ ] **Step 2.2.3: Run, expect 2 PASS**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_migrate_interviews.py -v 2>&1 | tail -8
# Expected: 2 passed.
```

### Task 2.3: `extract_year_from_pubdate` (TDD)

- [ ] **Step 2.3.1: Add the test**

Append to `test_migrate_interviews.py`:

```python
# -------- extract_year_from_pubdate tests --------


def test_pubdate_year_extraction():
    assert migrate.extract_year_from_pubdate("2020-11-05T04:29:04Z") == 2020


def test_pubdate_year_extraction_returns_none_on_garbage():
    assert migrate.extract_year_from_pubdate("not-a-date") is None
    assert migrate.extract_year_from_pubdate(None) is None
    assert migrate.extract_year_from_pubdate("") is None
```

- [ ] **Step 2.3.2: Run — expect 2 failures (function undefined)**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_migrate_interviews.py::test_pubdate_year_extraction -v 2>&1 | tail -5
# Expected: AttributeError or similar
```

- [ ] **Step 2.3.3: Implement `extract_year_from_pubdate`**

Append to `migrate-interviews-to-primary-works.py`:

```python
def extract_year_from_pubdate(pubdate: object) -> int | None:
    """Parse an ISO-like date string and return its year, or None on failure."""
    if not isinstance(pubdate, str) or not pubdate.strip():
        return None
    # Strip trailing Z which datetime.fromisoformat doesn't accept on older Pythons
    candidate = pubdate.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate).year
    except ValueError:
        pass
    # Fall back to a regex pull
    m = re.match(r"^(\d{4})\b", pubdate)
    return int(m.group(1)) if m else None
```

- [ ] **Step 2.3.4: Run — expect 4/4 PASS**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_migrate_interviews.py -v 2>&1 | tail -8
```

### Task 2.4: `strip_wp_garbage_body` (TDD)

- [ ] **Step 2.4.1: Add the test**

Append to `test_migrate_interviews.py`:

```python
# -------- strip_wp_garbage_body tests --------


def test_wp_garbage_body_returns_none():
    """A body matching only the WP migration tail returns None (no description)."""
    body = "\n\ntype=content&#038;p=1773). Needs editorial review._"
    assert migrate.strip_wp_garbage_body(body) is None


def test_editorial_paragraph_preserved():
    """A real editorial paragraph survives the strip."""
    body = "Begum Rokeya was a major Bengali liberal figure. " * 4
    cleaned = migrate.strip_wp_garbage_body(body)
    assert cleaned is not None
    assert "Begum Rokeya" in cleaned


def test_editorial_paragraph_with_wp_tail():
    """Real paragraph plus WP tail → paragraph survives, tail stripped."""
    body = (
        "Begum Rokeya was a major Bengali liberal figure. "
        "She wrote Sultana's Dream. " * 3
        + "\ntype=content&#038;p=1773). Needs editorial review._"
    )
    cleaned = migrate.strip_wp_garbage_body(body)
    assert cleaned is not None
    assert "Begum Rokeya" in cleaned
    assert "type=content" not in cleaned
    assert "Needs editorial review" not in cleaned
```

- [ ] **Step 2.4.2: Run — expect failures**

- [ ] **Step 2.4.3: Implement `strip_wp_garbage_body`**

Append to `migrate-interviews-to-primary-works.py`:

```python
def strip_wp_garbage_body(body: str) -> str | None:
    """Return cleaned body, or None if there's nothing meaningful left.

    Strips the trailing WordPress-migration boilerplate matching:
      ...type=content&[stuff]Needs editorial review._
    Then returns the cleaned text if it has >= 80 non-whitespace chars; else None.
    """
    if not body:
        return None
    cleaned = _WP_TAIL_RX.sub("", body).strip()
    # Count non-whitespace chars
    if sum(1 for c in cleaned if not c.isspace()) < 80:
        return None
    return cleaned
```

- [ ] **Step 2.4.4: Run — expect 3/3 new tests PASS (7/7 cumulative)**

### Task 2.5: `classify_transcript_status` (TDD)

- [ ] **Step 2.5.1: Add the test**

Append to `test_migrate_interviews.py`:

```python
# -------- classify_transcript_status tests --------


def test_classify_transcript_status_complete(tmp_path):
    """A real cleaned transcript → 'complete'."""
    txt = tmp_path / "foo.txt"
    txt.write_text("# Foo\n\nSpeaker 0: hello\n" * 20)  # plenty of content
    cleaned = tmp_path / "foo.cleaned.md"
    cleaned.write_text("# Foo\n\n**Speaker** (00:00): hello world\n" * 20)
    assert migrate.classify_transcript_status("foo", transcript_dir=tmp_path) == "complete"


def test_classify_transcript_status_none_when_skip_empty(tmp_path):
    """A SKIP_EMPTY stub cleaned.md → 'none'."""
    cleaned = tmp_path / "foo.cleaned.md"
    cleaned.write_text("# Foo\n\n(empty transcript)\n\n_Cleaned: skipped (transcript empty or too short)._\n")
    txt = tmp_path / "foo.txt"
    txt.write_text("(empty transcript)\n")
    assert migrate.classify_transcript_status("foo", transcript_dir=tmp_path) == "none"


def test_classify_transcript_status_unavailable_when_no_files(tmp_path):
    """No cleaned.md and no .txt → 'unavailable'."""
    assert migrate.classify_transcript_status("foo", transcript_dir=tmp_path) == "unavailable"
```

- [ ] **Step 2.5.2: Run — expect failures**

- [ ] **Step 2.5.3: Implement `classify_transcript_status`**

Append to `migrate-interviews-to-primary-works.py`:

```python
def classify_transcript_status(slug: str, *, transcript_dir: Path = TRANSCRIPT_DIR) -> str:
    """Decide which transcript_status enum value applies for this slug.

    Returns one of: 'complete', 'none', 'unavailable'.
    """
    cleaned = transcript_dir / f"{slug}.cleaned.md"
    if not cleaned.exists():
        return "unavailable"
    body = cleaned.read_text(encoding="utf-8")
    # SKIP_EMPTY stubs always carry the marker line emitted by the cleanup script.
    if "(empty transcript)" in body or "skipped (transcript empty" in body:
        return "none"
    return "complete"
```

- [ ] **Step 2.5.4: Run — expect 3/3 new tests PASS (10/10 cumulative)**

### Task 2.6: `build_new_frontmatter` (TDD)

- [ ] **Step 2.6.1: Add the test**

Append to `test_migrate_interviews.py`:

```python
# -------- build_new_frontmatter tests --------


def test_subject_ref_becomes_authors_list():
    """An interview with subject: 'd-r-pendse' produces authors: ['d-r-pendse']."""
    old_fm = {
        "id": "d-r-pendse-on-doing-business",
        "title": "D R Pendse on Doing Business",
        "subject": "d-r-pendse",
        "subject_name": "D R Pendse",
        "youtube_url": "https://www.youtube.com/watch?v=abc",
        "pubDate": "2020-11-05T04:29:04Z",
        "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="d-r-pendse-on-doing-business",
        transcript_status="complete", description=None,
    )
    assert new_fm["work_type"] == "interview"
    assert new_fm["authors"] == ["d-r-pendse"]
    assert new_fm["youtube_url"] == "https://www.youtube.com/watch?v=abc"
    assert new_fm["transcript_status"] == "complete"
    assert new_fm["publication"]["year"] == 2020
    assert new_fm["publication"]["language"] == "en"
    # Defensive: subject_name dropped (covered by title + resolved authors[0])
    assert "subject_name" not in new_fm


def test_missing_subject_yields_empty_authors():
    """No subject ref → authors: []."""
    old_fm = {
        "id": "il-explainer-ep-1",
        "title": "IL Explainer Ep 1",
        "subject_name": "Some Title",
        "pubDate": "2022-01-01T00:00:00Z",
        "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="il-explainer-ep-1",
        transcript_status="complete", description=None,
    )
    assert new_fm["authors"] == []
    assert "contributors" not in new_fm or new_fm["contributors"] == []


def test_description_when_present():
    """A non-empty description is included in the new frontmatter."""
    old_fm = {
        "id": "foo", "title": "Foo", "pubDate": "2020-01-01T00:00:00Z", "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="foo",
        transcript_status="complete",
        description="A real editorial paragraph.",
    )
    assert new_fm["description"] == "A real editorial paragraph."


def test_description_omitted_when_none():
    """A None description is NOT added as a key."""
    old_fm = {
        "id": "foo", "title": "Foo", "pubDate": "2020-01-01T00:00:00Z", "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="foo",
        transcript_status="complete", description=None,
    )
    assert "description" not in new_fm
```

- [ ] **Step 2.6.2: Run — expect failures**

- [ ] **Step 2.6.3: Implement `build_new_frontmatter`**

Append to `migrate-interviews-to-primary-works.py`:

```python
def build_new_frontmatter(
    old_fm: dict,
    *,
    slug: str,
    transcript_status: str,
    description: str | None,
) -> dict:
    """Build the primary-work-shaped frontmatter dict from an interview's old frontmatter."""
    # Authors
    subject = old_fm.get("subject")
    if isinstance(subject, str) and subject.strip():
        authors = [subject.strip()]
    else:
        authors = []

    # Year + language → publication block
    year = extract_year_from_pubdate(old_fm.get("pubDate"))
    language = old_fm.get("language") or "en"
    publication: dict = {"language": language}
    if year is not None:
        publication["year"] = year

    new_fm: dict = {
        "id": old_fm.get("id") or slug,
        "title": {"main": old_fm.get("title", slug)},
        "work_type": "interview",
        "authors": authors,
        "editors": [],
        "contributors": [],
        "publication": publication,
        "themes": [],
        "needs_review": True,
        "draft": bool(old_fm.get("draft", False)),
        "transcript_status": transcript_status,
    }

    # Optional fields
    if isinstance(old_fm.get("youtube_url"), str) and old_fm["youtube_url"].strip():
        new_fm["youtube_url"] = old_fm["youtube_url"].strip()
    if description is not None:
        new_fm["description"] = description

    return new_fm
```

- [ ] **Step 2.6.4: Run — expect 4/4 new tests PASS (14/14 cumulative)**

### Task 2.7: `serialize_new_md` (utility — no test; covered by integration)

- [ ] **Step 2.7.1: Implement the serializer + driver tail**

Append to `migrate-interviews-to-primary-works.py`:

```python
def serialize_new_md(new_fm: dict, body: str) -> str:
    """Render a primary-work MD: YAML frontmatter + body."""
    fm_yaml = yaml.safe_dump(new_fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{fm_yaml.rstrip()}\n---\n\n{body.rstrip()}\n"


def migrate_one(md_path: Path) -> dict:
    """Migrate one interview MD. Returns a status dict with keys:
        slug, status ('OK' | 'COLLISION' | 'NO_FRONTMATTER'), dest_path
    """
    slug = md_path.stem
    dest = PW_DIR / f"{slug}.md"
    if dest.exists():
        return {"slug": slug, "status": "COLLISION", "dest_path": str(dest)}

    text = md_path.read_text(encoding="utf-8")
    old_fm, old_body = parse_frontmatter(text)
    if not old_fm:
        return {"slug": slug, "status": "NO_FRONTMATTER", "dest_path": str(dest)}

    transcript_status = classify_transcript_status(slug)
    description = strip_wp_garbage_body(old_body)
    new_fm = build_new_frontmatter(
        old_fm, slug=slug,
        transcript_status=transcript_status,
        description=description,
    )

    # Body content
    if transcript_status == "complete":
        body = (TRANSCRIPT_DIR / f"{slug}.cleaned.md").read_text(encoding="utf-8")
    elif transcript_status == "none":
        # The SKIP_EMPTY stub the cleanup script wrote IS the body.
        body = (TRANSCRIPT_DIR / f"{slug}.cleaned.md").read_text(encoding="utf-8")
    else:  # 'unavailable'
        body = "Transcript not available.\n"

    new_md_text = serialize_new_md(new_fm, body)
    dest.write_text(new_md_text, encoding="utf-8")
    md_path.unlink()  # delete source only after successful write
    return {"slug": slug, "status": "OK", "dest_path": str(dest)}


def main() -> int:
    if not INTERVIEWS_DIR.exists():
        print(f"interviews dir missing — nothing to migrate: {INTERVIEWS_DIR}")
        return 0

    mds = sorted(INTERVIEWS_DIR.glob("*.md"))
    print(f"Migrating {len(mds)} interview MDs → primary-works/")

    ok = collisions = no_fm = 0
    for md in mds:
        r = migrate_one(md)
        status = r["status"]
        if status == "OK":
            ok += 1
            print(f"  ✓ {r['slug']}")
        elif status == "COLLISION":
            collisions += 1
            print(f"  ✗ COLLISION at {r['dest_path']} — left source in place")
        else:
            no_fm += 1
            print(f"  ✗ NO_FRONTMATTER: {r['slug']}")

    print()
    print(f"Migration summary: {ok} ok, {collisions} collisions, {no_fm} no-frontmatter, {len(mds)} total")
    return 0 if (collisions + no_fm) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.7.2: Add `test_slug_collision_aborts`**

Append to `test_migrate_interviews.py`:

```python
# -------- slug collision test --------


def test_slug_collision_aborts(tmp_path, monkeypatch):
    """If the destination MD already exists, migrate_one returns COLLISION and does NOT delete the source."""
    src_dir = tmp_path / "interviews"
    dst_dir = tmp_path / "primary-works"
    src_dir.mkdir()
    dst_dir.mkdir()

    src = src_dir / "foo.md"
    src.write_text("---\nid: foo\ntitle: Foo\npubDate: 2020-01-01T00:00:00Z\n---\nbody\n")
    dst = dst_dir / "foo.md"
    dst.write_text("# Already exists\n")

    monkeypatch.setattr(migrate, "PW_DIR", dst_dir)
    monkeypatch.setattr(migrate, "TRANSCRIPT_DIR", tmp_path)  # no cleaned.md → unavailable

    r = migrate.migrate_one(src)
    assert r["status"] == "COLLISION"
    assert src.exists(), "source was deleted despite collision"
    assert dst.read_text() == "# Already exists\n", "destination was overwritten"
```

- [ ] **Step 2.7.3: Run — expect 15/15 PASS**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_migrate_interviews.py -v 2>&1 | tail -20
```

### Task 2.8: Commit + push Chunk 2

- [ ] **Step 2.8.1: Stage + commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add scripts/synthesis/migrate-interviews-to-primary-works.py scripts/synthesis/tests/test_migrate_interviews.py
git commit -m "feat(synthesis): add migrate-interviews-to-primary-works.py (Phase A) with TDD helpers

Pure-logic helpers: parse_frontmatter, extract_year_from_pubdate,
strip_wp_garbage_body, classify_transcript_status, build_new_frontmatter,
serialize_new_md. Plus the migrate_one driver and main() loop.

15 unit tests covering each helper's success + edge-case paths.
Migration itself runs in Chunk 3."
```

- [ ] **Step 2.8.2: Push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
git push origin main
```

---

## Chunk 3: Run Phase A — migration + collection removal

Goal: execute the migration on all 72 interview MDs, remove the now-empty `interviews/` directory + the `interviews` collection definition from `content.config.ts` + the nav-bar link, build clean, commit + push.

### Task 3.1: Dry-run check (manual)

- [ ] **Step 3.1.1: Confirm exact MD counts before running**

```bash
cd "/Users/siraj/Indian Liberals Website"
ls apps/site/src/content/interviews/*.md | wc -l | tr -d ' '
# Expected: 72
ls apps/site/src/content/primary-works/*.md | wc -l | tr -d ' '
# Record: PRE_PW_COUNT (e.g., ~520)
```

### Task 3.2: Run the migration

- [ ] **Step 3.2.1: Execute migrate-interviews-to-primary-works.py**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 scripts/synthesis/migrate-interviews-to-primary-works.py 2>&1 | tee /tmp/interviews-migrate.log | tail -10
```

Expected tail:
```
Migration summary: 72 ok, 0 collisions, 0 no-frontmatter, 72 total
```

If collisions > 0 or no-frontmatter > 0: STOP, inspect the log, decide.

- [ ] **Step 3.2.2: Verify counts post-migration**

```bash
cd "/Users/siraj/Indian Liberals Website"
ls apps/site/src/content/interviews/ 2>/dev/null | wc -l | tr -d ' '
# Expected: 0 (or just any non-.md files like .DS_Store)
ls apps/site/src/content/primary-works/*.md | wc -l | tr -d ' '
# Expected: PRE_PW_COUNT + 72
```

### Task 3.3: Remove the now-empty `interviews/` directory

- [ ] **Step 3.3.1: Remove the dir**

```bash
cd "/Users/siraj/Indian Liberals Website"
rm -rf apps/site/src/content/interviews/
```

### Task 3.4: Remove the `interviews` collection definition

- [ ] **Step 3.4.1: Edit `content.config.ts`**

Open `apps/site/src/content.config.ts`. Find the `interviews` collection block. It looks like:

```ts
const interviews = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/interviews' }),
  schema: z.object({
    id: z.string(),
    title: z.string(),
    // ... ~13 lines of schema ...
  }),
});
```

Delete the entire `const interviews = defineCollection({ ... });` block.

Then find the exported `collections` map at the bottom and delete the `interviews,` entry from it.

- [ ] **Step 3.4.2: Verify the edit**

```bash
cd "/Users/siraj/Indian Liberals Website"
grep -n "^const interviews\b\|interviews," apps/site/src/content.config.ts
# Expected: empty (no matches).
```

### Task 3.5: Remove the "Interviews" nav-bar link

- [ ] **Step 3.5.1: Edit `apps/site/src/components/Header.astro`**

Find the line with the "Interviews" link (around line 10 per the spec; verify with `grep -n "Interview" apps/site/src/components/Header.astro`). Delete that line and any surrounding whitespace artifacts.

- [ ] **Step 3.5.2: Verify the edit**

```bash
cd "/Users/siraj/Indian Liberals Website"
grep -n "Interview" apps/site/src/components/Header.astro
# Expected: empty (no matches in the nav block; matches in unrelated context are fine).
```

### Task 3.6: Build sanity

- [ ] **Step 3.6.1: Full build**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build > /tmp/interviews-chunk3-build.log 2>&1 && tail -5 /tmp/interviews-chunk3-build.log
[ -L public/pagefind ] || ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/interviews-chunk3-build.log
# Expected: 0 — schema accepts work_type='interview'; no MDs reference the removed
# interviews collection.
PAGES=$(find dist -name 'index.html' | wc -l | tr -d ' ')
echo "PAGES=$PAGES"
# Expected: pre-chunk page count + 72.
```

If errors appear, common causes:
- `apps/site/src/components/ThinkerDetail.astro` still references `getCollection('interviews')` — fix to filter primary-works by `work_type: 'interview'`. Document in commit but don't deep-dive; UI is the follow-up spec. If the build fails, do a minimal stub: replace the `getCollection('interviews')` call with `getCollection('primary-works')` filtered by `data.work_type === 'interview'`.
- `apps/site/src/components/Search.astro` may have a hardcoded `'interviews'` filter; same minimal fix.

- [ ] **Step 3.6.2: Spot-check 3 migrated interviews render**

```bash
cd "/Users/siraj/Indian Liberals Website"
for slug in d-r-pendse-on-doing-business-in-india-before-1991-reforms \
            bollywood-and-cultural-change-in-attitude \
            il-explainer-ep-2-begum-rokeya; do
  PAGE=$(find apps/site/dist -path "*/primary-works/$slug/index.html" | head -1)
  [ -n "$PAGE" ] && echo "✓ rendered: $slug" || echo "✗ MISSING: $slug"
done
```

### Task 3.7: Commit + push Chunk 3

- [ ] **Step 3.7.1: Stage everything**

```bash
cd "/Users/siraj/Indian Liberals Website"
# The 72 new primary-works MDs + the 72 deleted interview MDs + the schema + Header.
git add apps/site/src/content/primary-works/ apps/site/src/content/interviews/ \
        apps/site/src/content.config.ts apps/site/src/components/Header.astro
# If any UI files were minimally patched (ThinkerDetail.astro, Search.astro), add those too:
git add apps/site/src/components/ThinkerDetail.astro apps/site/src/components/Search.astro 2>/dev/null || true
git status --short | head -20
```

- [ ] **Step 3.7.2: Commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git commit -m "feat(content): fold interviews into primary-works (72 MDs migrated)

Phase A of the interviews-into-primary-works spec.

- Migrate 72 interview MDs into apps/site/src/content/primary-works/ with
  work_type='interview'.
- Remove the interviews collection definition from content.config.ts.
- Remove the 'Interviews' nav-bar link.
- Minimal patches to ThinkerDetail.astro / Search.astro to keep the build
  green (proper UI overhaul deferred to the interview-detail-UI spec).

Of the 72 migrated MDs:
- ~67 have transcript_status: complete (cleaned diarized transcript as body).
- 2 have transcript_status: unavailable (audio MP3s 404'd):
    in-conversation-with-ronald-meinardus-regional-director-fnf-south-asia
    indian-liberal-tradition-gp-manish
- 1 has transcript_status: none (empty Deepgram result):
    a-d-shroff-champion-of-free-enterprise

LLM enrichment (summary, key_points, thinker_mentions, themes, interviewer)
follows in the next chunk."
```

- [ ] **Step 3.7.3: Push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
git push origin main
```

---

## Chunk 4: `enrich-interview-mds.py` (TDD)

Goal: TDD-build the Phase B enrichment script's pure-logic helpers, then write the driver. Driver smoke-tested in Chunk 5.

### Task 4.1: Test file scaffolding

**Files:**
- Create: `scripts/synthesis/tests/test_enrich_interviews.py`
- Create: `scripts/synthesis/enrich-interview-mds.py`

- [ ] **Step 4.1.1: Create the test file with importlib loader**

Same pattern as Chunk 2:

```python
"""Unit tests for enrich-interview-mds.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _load(stem: str):
    mod_name = stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(
        mod_name, str(SCRIPTS_DIR / f"{stem}.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


enrich = _load("enrich-interview-mds")
```

- [ ] **Step 4.1.2: Create the enrichment script skeleton**

```python
#!/usr/bin/env python3
"""Phase B: LLM enrichment of migrated interview MDs.

For each MD under apps/site/src/content/primary-works/ with work_type='interview'
and transcript_status='complete':
  - load the MD's body (cleaned transcript) + frontmatter (title, description,
    authors[0]=subject) + thinker-collection authority list
  - call claude -p with a structured-output prompt
  - parse + validate the JSON
  - merge summary, key_points, themes, thinker_mentions, related_thinkers,
    contributors[] into the MD frontmatter
  - write back; commit in batches of 10

Skips MDs whose transcript_status is 'unavailable' or 'none'.

Run:
    .venv-extract/bin/python3 scripts/synthesis/enrich-interview-mds.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
THINKERS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "thinkers"
LOG = Path("/tmp/interview-enrich-progress.tsv")
FAILS = Path("/tmp/interview-enrich-fails.tsv")
COMMIT_BATCH_SIZE = 10
MAX_TRANSCRIPT_BYTES = 80_000

_FM_BLOCK_RX = re.compile(r"^---\n([\s\S]*?)\n---\n?([\s\S]*)$", re.M)
```

- [ ] **Step 4.1.3: Run pytest — expect import to succeed but no tests run**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_enrich_interviews.py -v 2>&1 | tail -5
# Expected: "no tests ran" or similar.
```

### Task 4.2: `build_authority_manifest` (TDD)

- [ ] **Step 4.2.1: Add the test**

Append to `test_enrich_interviews.py`:

```python
# -------- build_authority_manifest tests --------


def test_authority_manifest_format(tmp_path):
    """Returns a deterministic, sorted list with {slug, canonical_name, also_known_as, canon_status}."""
    t1 = tmp_path / "peter-bauer.md"
    t1.write_text(
        "---\nid: peter-bauer\n"
        "name:\n  canonical: Peter Bauer\n  also_known_as: [Lord Bauer, P. T. Bauer]\n"
        "canon_status: core\n---\n"
    )
    t2 = tmp_path / "milton-friedman.md"
    t2.write_text(
        "---\nid: milton-friedman\n"
        "name:\n  canonical: Milton Friedman\n  also_known_as: []\n"
        "canon_status: core\n---\n"
    )
    manifest = enrich.build_authority_manifest(tmp_path)
    assert len(manifest) == 2
    # Sorted by slug
    assert [m["slug"] for m in manifest] == ["milton-friedman", "peter-bauer"]
    # Shape
    assert manifest[0] == {
        "slug": "milton-friedman",
        "canonical_name": "Milton Friedman",
        "also_known_as": [],
        "canon_status": "core",
    }
    assert manifest[1]["also_known_as"] == ["Lord Bauer", "P. T. Bauer"]
```

- [ ] **Step 4.2.2: Run — expect failure**

- [ ] **Step 4.2.3: Implement `build_authority_manifest`**

Append to `enrich-interview-mds.py`:

```python
def build_authority_manifest(thinkers_dir: Path) -> list[dict]:
    """Return [{slug, canonical_name, also_known_as, canon_status}, ...] sorted by slug."""
    out: list[dict] = []
    for md in sorted(thinkers_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FM_BLOCK_RX.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        slug = fm.get("id") or md.stem
        name_block = fm.get("name") or {}
        canonical = (name_block.get("canonical") or "").strip()
        if not canonical:
            continue
        also = name_block.get("also_known_as") or []
        if not isinstance(also, list):
            also = []
        also = [a.strip() for a in also if isinstance(a, str) and a.strip()]
        out.append({
            "slug": slug,
            "canonical_name": canonical,
            "also_known_as": also,
            "canon_status": fm.get("canon_status") or "unknown",
        })
    return out
```

- [ ] **Step 4.2.4: Run — expect PASS**

### Task 4.3: `validate_and_clamp` (TDD)

- [ ] **Step 4.3.1: Add the tests**

Append to `test_enrich_interviews.py`:

```python
# -------- validate_and_clamp tests --------


def test_validate_passes_known_slugs():
    """All slugs in authority → returned unchanged (minus display_name)."""
    payload = {
        "summary": "s", "key_points": ["a"], "themes": ["x"],
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "display_name": "Peter Bauer", "thinker": "peter-bauer",
                "role": "mention", "reasoning": "r",
                "evidence": [{"quote": "q", "context": "c"}],
                "key_passages": [],
            }
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    assert out["thinker_mentions"][0]["thinker"] == "peter-bauer"
    assert "display_name" not in out["thinker_mentions"][0]


def test_validate_demotes_unknown_slug_via_display_name():
    """Unknown slug + display_name present → demoted to thinker_unresolved using display_name."""
    payload = {
        "summary": "s", "key_points": [], "themes": [],
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "display_name": "Friedrich Hayek", "thinker": "friedrich-hayek",
                "role": "mention", "reasoning": "r",
                "evidence": [], "key_passages": [],
            }
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    mention = out["thinker_mentions"][0]
    assert "thinker" not in mention
    assert mention["thinker_unresolved"] == "Friedrich Hayek"


def test_validate_demotes_unknown_slug_via_literal_fallback():
    """Unknown slug + missing display_name → fall back to the slug-shaped string."""
    payload = {
        "summary": "s", "key_points": [], "themes": [],
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "thinker": "friedrich-hayek",
                "role": "mention", "reasoning": "r",
                "evidence": [], "key_passages": [],
            }
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    assert out["thinker_mentions"][0]["thinker_unresolved"] == "friedrich-hayek"


def test_validate_clamps_counts():
    """Counts exceeding caps are trimmed."""
    payload = {
        "summary": "s",
        "key_points": [f"point-{i}" for i in range(15)],   # > 7
        "themes": [f"theme-{i}" for i in range(15)],        # > 7
        "interviewer_name": None, "interviewer_slug": None,
        "thinker_mentions": [
            {
                "display_name": f"Person {i}", "thinker": "peter-bauer",
                "role": "mention", "reasoning": "r",
                "evidence": [{"quote": f"q{j}", "context": ""} for j in range(15)],
                "key_passages": [{"quote": f"k{j}", "what_it_shows": ""} for j in range(15)],
            }
            for i in range(15)  # > 5 mentions
        ],
    }
    out = enrich.validate_and_clamp(payload, authority_slugs={"peter-bauer"})
    assert len(out["key_points"]) == 7
    assert len(out["themes"]) == 7
    assert len(out["thinker_mentions"]) == 5
    assert len(out["thinker_mentions"][0]["evidence"]) == 5
    assert len(out["thinker_mentions"][0]["key_passages"]) == 5
```

- [ ] **Step 4.3.2: Run — expect failures**

- [ ] **Step 4.3.3: Implement `validate_and_clamp`**

Append to `enrich-interview-mds.py`:

```python
def validate_and_clamp(payload: dict, *, authority_slugs: set[str]) -> dict:
    """Normalise LLM output: demote unknown slugs to thinker_unresolved, clamp count caps.

    Caps:
      - key_points: ≤ 7
      - themes: ≤ 7
      - thinker_mentions: ≤ 5
      - thinker_mentions[].evidence: ≤ 5
      - thinker_mentions[].key_passages: ≤ 5
    """
    out: dict = {
        "summary": payload.get("summary") or "",
        "key_points": list(payload.get("key_points") or [])[:7],
        "themes": list(payload.get("themes") or [])[:7],
        "interviewer_name": payload.get("interviewer_name") or None,
        "interviewer_slug": payload.get("interviewer_slug") or None,
        "thinker_mentions": [],
    }
    raw_mentions = list(payload.get("thinker_mentions") or [])[:5]
    for entry in raw_mentions:
        if not isinstance(entry, dict):
            continue
        mention: dict = {}
        slug = entry.get("thinker")
        display = entry.get("display_name") or ""
        if isinstance(slug, str) and slug in authority_slugs:
            mention["thinker"] = slug
        else:
            # Demote to thinker_unresolved
            unresolved = entry.get("thinker_unresolved") or display or slug or ""
            mention["thinker_unresolved"] = unresolved.strip() if isinstance(unresolved, str) else ""
        # role + reasoning + evidence + key_passages
        mention["role"] = entry.get("role") or "mention"
        mention["reasoning"] = entry.get("reasoning") or ""
        evidence = list(entry.get("evidence") or [])[:5]
        mention["evidence"] = [
            {"quote": e.get("quote", ""), "context": e.get("context", "")}
            for e in evidence if isinstance(e, dict)
        ]
        passages = list(entry.get("key_passages") or [])[:5]
        mention["key_passages"] = [
            {"quote": p.get("quote", ""), "what_it_shows": p.get("what_it_shows", "")}
            for p in passages if isinstance(p, dict)
        ]
        out["thinker_mentions"].append(mention)
    return out
```

- [ ] **Step 4.3.4: Run — expect 4 new PASS (5/5 cumulative)**

### Task 4.4: `truncate_transcript` (TDD)

- [ ] **Step 4.4.1: Add the test**

Append to `test_enrich_interviews.py`:

```python
# -------- truncate_transcript test --------


def test_truncate_long_transcript_preserves_endpoints():
    """A transcript > MAX bytes gets middle elided; first + last segments preserved."""
    big = ("first-segment " * 5000) + ("MIDDLE_SHOULD_BE_DROPPED " * 5000) + ("last-segment " * 5000)
    assert len(big.encode("utf-8")) > 80_000
    truncated = enrich.truncate_transcript(big, max_bytes=80_000)
    assert "first-segment" in truncated
    assert "last-segment" in truncated
    assert "MIDDLE_SHOULD_BE_DROPPED" not in truncated
    assert "transcript truncated" in truncated.lower()


def test_truncate_short_transcript_unchanged():
    """A transcript <= MAX bytes is returned unchanged."""
    small = "short transcript content."
    assert enrich.truncate_transcript(small, max_bytes=80_000) == small
```

- [ ] **Step 4.4.2: Run — expect failures**

- [ ] **Step 4.4.3: Implement `truncate_transcript`**

Append to `enrich-interview-mds.py`:

```python
def truncate_transcript(text: str, *, max_bytes: int = MAX_TRANSCRIPT_BYTES) -> str:
    """Truncate the middle of a long transcript; preserve first half and last half.

    The marker '(transcript truncated for analysis — full text preserved in MD body)'
    is inserted at the elision point.
    """
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    half = max_bytes // 2
    head = data[:half].decode("utf-8", errors="ignore")
    tail = data[-half:].decode("utf-8", errors="ignore")
    return (
        head
        + "\n\n... (transcript truncated for analysis — full text preserved in MD body) ...\n\n"
        + tail
    )
```

- [ ] **Step 4.4.4: Run — expect 2 new PASS (7/7 cumulative)**

### Task 4.5: Driver tail — `compose_prompt`, `call_claude`, `enrich_one`, `main`

These are integration-style — not unit-tested. The smoke test in Chunk 5 covers them.

- [ ] **Step 4.5.1: Append driver code**

Append to `enrich-interview-mds.py`:

```python
def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    m = _FM_BLOCK_RX.match(md_text)
    if not m:
        return {}, md_text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), m.group(2)


def lookup_thinker_name(slug: str) -> str | None:
    p = THINKERS_DIR / f"{slug}.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(text)
    return ((fm.get("name") or {}).get("canonical") or "").strip() or None


def compose_prompt(*, title: str, year: int | None, subject_name: str | None,
                    description: str | None, authority: list[dict],
                    transcript: str) -> str:
    """Build the Phase B prompt per spec §5.3."""
    desc_line = description.strip() if description else "(no editorial description on file)"
    year_line = str(year) if year else "(unknown)"
    subj_line = subject_name if subject_name else "(no resolved subject — use transcript to determine the main speaker)"

    # Render authority as one row per line
    auth_rows = []
    for a in authority:
        aka = ", ".join(a["also_known_as"]) if a["also_known_as"] else ""
        auth_rows.append(f"{a['slug']}\t{a['canonical_name']}\t[{aka}]\t{a['canon_status']}")
    auth_table = "\n".join(auth_rows)

    transcript = truncate_transcript(transcript)

    return f"""You are an analyst preparing structured metadata for an interview transcript that is being filed alongside books, pamphlets, and speeches in the Indian Liberals archive.

# Interview
- Title: {title}
- Year: {year_line}
- Subject (interviewee): {subj_line}
- Editorial description (verbatim, if any):
{desc_line}

# Authority list of thinkers in the archive
(tab-separated: slug | canonical_name | [also_known_as] | canon_status)
{auth_table}

# Cleaned diarized transcript

{transcript}

# Your task

Produce a SINGLE JSON object with these fields (and NOTHING else — no preamble, no code fence):

{{
  "summary": "1-3 paragraph synopsis...",
  "key_points": ["...", "..."],
  "themes": ["lowercase-hyphenated-tag", "..."],
  "interviewer_name": "Resolved canonical name" OR null,
  "interviewer_slug": "slug-from-authority-list" OR null,
  "thinker_mentions": [
    {{
      "display_name": "Person's name as commonly rendered",
      "thinker": "slug-from-authority-list",
      "role": "subject" | "mention",
      "reasoning": "one-sentence explanation",
      "evidence": [{{"quote": "verbatim from transcript", "context": "short"}}],
      "key_passages": [{{"quote": "verbatim", "what_it_shows": "short"}}]
    }}
  ]
}}

Hard rules:
- thinker_mentions[].thinker MUST be a slug from the authority list above. If a person has no plausible match, use {{"display_name": "Their name", "thinker_unresolved": "Their name", ...}} instead. Never invent a slug.
- Always include a display_name field in each mention.
- evidence[].quote and key_passages[].quote MUST be verbatim from the transcript.
- Max 5 mentions, ≤5 evidence + ≤5 key_passages per mention, ≤7 key_points, ≤7 themes.
- Output ONLY the JSON object. No preamble, no commentary, no code fence.
"""


def log(msg: str) -> None:
    line = f"{int(time.time())}\t{msg}\n"
    with LOG.open("a") as f:
        f.write(line)
    print(line.rstrip(), flush=True)


def log_fail(slug: str, reason: str) -> None:
    with FAILS.open("a") as f:
        f.write(f"{int(time.time())}\t{slug}\t{reason}\n")


def parse_reset_seconds(text: str) -> float | None:
    m = re.search(r"reset.*?in\s+(\d+(?:\.\d+)?)\s*min", text or "", re.I)
    return (float(m.group(1)) * 60 + 30) if m else None


def call_claude(prompt: str, slug: str, *, max_retries: int = 3) -> dict | None:
    """Call claude -p; parse JSON; handle rate-limit retries."""
    for attempt in range(1, max_retries + 1):
        try:
            r = subprocess.run(
                ["claude", "-p", "--dangerously-skip-permissions"],
                input=prompt, capture_output=True, text=True, timeout=600,
            )
        except subprocess.TimeoutExpired:
            log(f"{slug}\tTIMEOUT_attempt={attempt}")
            continue
        if r.returncode != 0:
            combined = (r.stderr or "") + " " + (r.stdout or "")
            if re.search(r"rate.?limit|out.?of.?extra.?usage|usage.?limit|quota", combined, re.I):
                reset = parse_reset_seconds(combined) or 600
                log(f"{slug}\tRATE_LIMITED_attempt={attempt}_sleep={reset:.0f}s")
                time.sleep(reset)
                continue
            log(f"{slug}\tFAIL_rc={r.returncode}\t{combined[:200]!r}")
            return None
        raw = r.stdout.strip()
        # The model sometimes wraps in ```json ... ```; strip that defensively.
        raw = re.sub(r"^```(?:json)?\s*\n", "", raw)
        raw = re.sub(r"\n```\s*$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log(f"{slug}\tJSON_PARSE_FAIL_attempt={attempt}\t{e!s}")
            continue
    return None


def write_back_frontmatter(md_path: Path, new_fields: dict) -> None:
    """Merge new_fields into the MD's frontmatter; preserve body."""
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    fm.update(new_fields)
    # Recompute related_thinkers as union of authors + thinker_mentions[].thinker
    related = set()
    for a in fm.get("authors") or []:
        if isinstance(a, str):
            related.add(a)
    for mention in fm.get("thinker_mentions") or []:
        s = mention.get("thinker")
        if isinstance(s, str):
            related.add(s)
    fm["related_thinkers"] = sorted(related)
    fm["needs_review"] = True

    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    md_path.write_text(f"---\n{fm_yaml.rstrip()}\n---\n\n{body.lstrip()}", encoding="utf-8")


def enrich_one(md_path: Path, *, authority: list[dict], authority_slugs: set[str]) -> str:
    """Run Phase B on one MD. Returns one of: 'OK', 'SKIPPED', 'FAILED'."""
    text = md_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    slug = md_path.stem
    if fm.get("work_type") != "interview":
        return "SKIPPED"
    if fm.get("transcript_status") != "complete":
        return "SKIPPED"
    if fm.get("thinker_mentions"):
        # Already enriched — idempotent skip
        return "SKIPPED"
    title = (fm.get("title") or {}).get("main") or slug
    year = (fm.get("publication") or {}).get("year")
    subject_slug = (fm.get("authors") or [None])[0]
    subject_name = lookup_thinker_name(subject_slug) if isinstance(subject_slug, str) else None
    description = fm.get("description")

    prompt = compose_prompt(
        title=title, year=year, subject_name=subject_name,
        description=description, authority=authority, transcript=body,
    )
    payload = call_claude(prompt, slug)
    if payload is None:
        log_fail(slug, "claude_p_returned_none_or_unparseable")
        return "FAILED"

    cleaned = validate_and_clamp(payload, authority_slugs=authority_slugs)

    # Merge interviewer into contributors
    contributors = list(fm.get("contributors") or [])
    iv_slug = cleaned["interviewer_slug"]
    iv_name = cleaned["interviewer_name"]
    if isinstance(iv_slug, str) and iv_slug in authority_slugs:
        contributors.append({"role": "interviewer", "thinker": iv_slug})
    elif isinstance(iv_name, str) and iv_name.strip() and iv_name.strip().lower() not in ("interviewer", "host"):
        contributors.append({"role": "interviewer", "thinker_unresolved": iv_name.strip()})

    new_fields = {
        "summary": cleaned["summary"],
        "key_points": cleaned["key_points"],
        "themes": cleaned["themes"],
        "thinker_mentions": cleaned["thinker_mentions"],
        "contributors": contributors,
    }
    write_back_frontmatter(md_path, new_fields)
    return "OK"


def _staged_paths_count() -> int:
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), check=True,
    )
    return sum(1 for line in r.stdout.splitlines() if line.strip())


def commit_batch(batch_no: int, count: int) -> None:
    msg = f"data(primary-works): enrich {count} interview MD(s) (batch {batch_no})"
    subprocess.run(["git", "commit", "-m", msg], check=True, cwd=str(REPO_ROOT))
    subprocess.run(["git", "fetch", "origin"], check=True, cwd=str(REPO_ROOT))
    subprocess.run(["git", "rebase", "origin/main"], check=True, cwd=str(REPO_ROOT))
    subprocess.run(["git", "push", "origin", "main"], check=True, cwd=str(REPO_ROOT))


def main() -> int:
    LOG.touch()
    FAILS.touch()

    authority = build_authority_manifest(THINKERS_DIR)
    authority_slugs = {a["slug"] for a in authority}
    log(f"__START__\tauthority_size={len(authority)}")

    # Iterate only over MDs with work_type='interview'
    candidates: list[Path] = []
    for md in sorted(PW_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if fm.get("work_type") == "interview":
            candidates.append(md)
    log(f"__CANDIDATES__\tcount={len(candidates)}")

    ok = skipped = failed = 0
    batch_no = 0
    in_batch = 0
    for md in candidates:
        status = enrich_one(md, authority=authority, authority_slugs=authority_slugs)
        if status == "OK":
            ok += 1
            in_batch += 1
            log(f"{md.stem}\tOK")
            subprocess.run(["git", "add", str(md)], check=True, cwd=str(REPO_ROOT))
            if in_batch >= COMMIT_BATCH_SIZE:
                batch_no += 1
                commit_batch(batch_no, in_batch)
                in_batch = 0
        elif status == "SKIPPED":
            skipped += 1
            log(f"{md.stem}\tSKIP")
        else:
            failed += 1
    # Final flush
    if in_batch > 0:
        batch_no += 1
        commit_batch(batch_no, in_batch)

    log(f"__END__\tok={ok} skipped={skipped} failed={failed} batches={batch_no}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4.5.2: Verify the file parses + all helpers importable**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -c "
import sys, importlib.util
spec = importlib.util.spec_from_file_location('enrich', 'scripts/synthesis/enrich-interview-mds.py')
m = importlib.util.module_from_spec(spec)
sys.modules['enrich'] = m
spec.loader.exec_module(m)
print('OK')
for fn in ('build_authority_manifest', 'validate_and_clamp', 'truncate_transcript',
           'compose_prompt', 'call_claude', 'enrich_one', 'main'):
    print(f'{fn}: {getattr(m, fn).__name__}')
"
```

- [ ] **Step 4.5.3: Final pytest run — 7/7 enrich tests + 15/15 migrate tests = 22 passed**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 -m pytest scripts/synthesis/tests/test_migrate_interviews.py scripts/synthesis/tests/test_enrich_interviews.py -v 2>&1 | tail -20
```

### Task 4.6: Commit + push Chunk 4

- [ ] **Step 4.6.1: Stage + commit**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add scripts/synthesis/enrich-interview-mds.py scripts/synthesis/tests/test_enrich_interviews.py
git commit -m "feat(synthesis): add enrich-interview-mds.py (Phase B) with TDD helpers

Pure-logic helpers: build_authority_manifest, validate_and_clamp,
truncate_transcript. Plus the driver: parse_frontmatter, lookup_thinker_name,
compose_prompt (per spec §5.3), call_claude (with rate-limit retry),
write_back_frontmatter (recomputes related_thinkers), enrich_one,
commit_batch, main loop.

7 unit tests covering each helper's success + edge cases (known slug pass-through,
unknown slug demotion via display_name, fallback to literal slug-string when
display_name missing, count clamping, transcript truncation)."
```

- [ ] **Step 4.6.2: Push**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git rebase origin/main
git push origin main
```

---

## Chunk 5: Run Phase B + final acceptance

Goal: execute Phase B enrichment in batches of 10 commits. Confirm acceptance criteria. Surface to Adnan.

### Task 5.1: Smoke on two MDs first

- [ ] **Step 5.1.1: Smoke MD 1 — Pendse (long, name-dense, has subject)**

```bash
cd "/Users/siraj/Indian Liberals Website"
cat > /tmp/enrich-smoke.py << 'EOF'
import sys, importlib.util
spec = importlib.util.spec_from_file_location("enrich", "scripts/synthesis/enrich-interview-mds.py")
m = importlib.util.module_from_spec(spec); sys.modules["enrich"] = m; spec.loader.exec_module(m)
from pathlib import Path
authority = m.build_authority_manifest(m.THINKERS_DIR)
authority_slugs = {a["slug"] for a in authority}
for slug in ["d-r-pendse-on-doing-business-in-india-before-1991-reforms",
             "bollywood-and-cultural-change-in-attitude"]:
    md = m.PW_DIR / f"{slug}.md"
    if not md.exists():
        print(f"NOT FOUND: {md}"); continue
    print(f"--- ENRICHING: {slug} ---")
    import time; t0 = time.time()
    status = m.enrich_one(md, authority=authority, authority_slugs=authority_slugs)
    print(f"  status: {status}  elapsed: {time.time()-t0:.1f}s")
    if status == "OK":
        # Show what landed
        from yaml import safe_load
        text = md.read_text()
        fm_block = text.split("---", 2)[1]
        fm = safe_load(fm_block)
        print(f"  summary: {fm.get('summary', '')[:160]}...")
        print(f"  key_points: {len(fm.get('key_points', []))} items")
        print(f"  themes: {fm.get('themes')}")
        print(f"  thinker_mentions: {len(fm.get('thinker_mentions', []))} items")
        for tm in fm.get("thinker_mentions", [])[:3]:
            who = tm.get("thinker") or tm.get("thinker_unresolved")
            print(f"    - {who} (role={tm.get('role')}, evidence={len(tm.get('evidence',[]))}, passages={len(tm.get('key_passages',[]))})")
        print(f"  contributors: {fm.get('contributors')}")
EOF
.venv-extract/bin/python3 /tmp/enrich-smoke.py 2>&1 | tail -40
```

Expected: both MDs status OK; Pendse has ≥ 3 thinker_mentions including jrd-tata and a manmohan-singh entry (resolved or thinker_unresolved); Bollywood has ≥ 2 thinker_mentions.

- [ ] **Step 5.1.2: Decide based on smoke**

If smoke looks sane: commit the 2 smoke MDs ourselves as a manual batch-0:

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/content/primary-works/d-r-pendse-on-doing-business-in-india-before-1991-reforms.md \
        apps/site/src/content/primary-works/bollywood-and-cultural-change-in-attitude.md
git commit -m "data(primary-works): enrich 2 interview MDs (smoke batch)"
git fetch origin && git rebase origin/main && git push origin main
```

If smoke looks bad: STOP and surface — Phase B prompt or validator needs tuning before running the full batch.

### Task 5.2: Full Phase B run

- [ ] **Step 5.2.1: Launch the enrichment**

```bash
cd "/Users/siraj/Indian Liberals Website"
nohup .venv-extract/bin/python3 scripts/synthesis/enrich-interview-mds.py \
  > /tmp/enrich-stdout.log 2>&1 &
echo $! > /tmp/enrich.pid
disown
sleep 5
PID=$(cat /tmp/enrich.pid)
ps -p "$PID" -o pid,etime,command | head -2
head -10 /tmp/enrich-stdout.log
```

The enrichment runs sequentially (one MD at a time). At ~30 sec/MD × ~65 MDs (72 - 2 unavailable - 1 none - 2 smoke-already-done) = ~30-35 min.

- [ ] **Step 5.2.2: Monitor periodically**

```bash
cd "/Users/siraj/Indian Liberals Website"
PID=$(cat /tmp/enrich.pid)
ps -p "$PID" >/dev/null 2>&1 && echo "alive" || echo "exited"
echo "---"
tail -5 /tmp/interview-enrich-progress.tsv
echo "---"
echo "Failures so far:"
wc -l /tmp/interview-enrich-fails.tsv | tr -d ' '
```

Wait until the process exits (or kill via `kill $(cat /tmp/enrich.pid)` if surfaced as stuck).

### Task 5.3: Acceptance verification

- [ ] **Step 5.3.1: Count check**

```bash
cd "/Users/siraj/Indian Liberals Website"
# Total interviews in primary-works
TOTAL_INT=$(grep -l "^work_type: interview" apps/site/src/content/primary-works/*.md | wc -l | tr -d ' ')
echo "interview MDs total: $TOTAL_INT  (expected 72)"

# How many are enriched (have thinker_mentions populated)
ENRICHED=$(for f in apps/site/src/content/primary-works/*.md; do
  if grep -q "^work_type: interview" "$f" && grep -q "^thinker_mentions:" "$f"; then
    # Check that thinker_mentions isn't just an empty array
    if ! grep -q "^thinker_mentions: \[\]" "$f"; then echo x; fi
  fi
done | wc -l | tr -d ' ')
echo "enriched: $ENRICHED  (expected ~67)"

# transcript_status breakdown
for status in complete none unavailable; do
  N=$(grep -l "^transcript_status: $status" apps/site/src/content/primary-works/*.md | wc -l | tr -d ' ')
  echo "transcript_status=$status: $N"
done
```

- [ ] **Step 5.3.2: Build clean**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build > /tmp/interviews-chunk5-build.log 2>&1 && tail -5 /tmp/interviews-chunk5-build.log
[ -L public/pagefind ] || ln -s ../dist/pagefind public/pagefind
grep -cE "ELIFECYCLE|✘|✖|\[ERROR\]" /tmp/interviews-chunk5-build.log
# Expected: 0
```

- [ ] **Step 5.3.3: Spot-check 3 enriched MDs render**

```bash
cd "/Users/siraj/Indian Liberals Website"
for slug in d-r-pendse-on-doing-business-in-india-before-1991-reforms \
            il-explainer-ep-2-begum-rokeya \
            br-shenoy-a-prophet-without-honour; do
  PAGE=$(find apps/site/dist -path "*/primary-works/$slug/index.html" | head -1)
  if [ -n "$PAGE" ]; then
    echo "✓ $slug — $(grep -oE '<h1[^>]*>[^<]+' "$PAGE" | head -1)"
  else
    echo "✗ missing: $slug"
  fi
done
```

- [ ] **Step 5.3.4: Verify all pushed**

```bash
cd "/Users/siraj/Indian Liberals Website"
git fetch origin
git log --oneline origin/main..HEAD
# Expected: empty (every batch was auto-pushed).
```

- [ ] **Step 5.3.5: Final failures TSV check**

```bash
cd "/Users/siraj/Indian Liberals Website"
[ -s /tmp/interview-enrich-fails.tsv ] && echo "=== Failures ===" && cat /tmp/interview-enrich-fails.tsv \
  || echo "✓ no failures"
```

### Task 5.4: Surface to Adnan

- [ ] **Step 5.4.1: Compose summary message**

Report to the controller:
- Total interview MDs migrated: 72
- Enriched: ~67 (with summary + thinker_mentions + key_points + themes)
- transcript_status: complete=~67, none=1, unavailable=2
- All commits pushed to origin/main
- Build clean
- Any failures from /tmp/interview-enrich-fails.tsv surfaced explicitly with slugs + reason
- v1.5 extraction is still paused; controller decides when to relaunch

The follow-up UI spec (interview-detail UI) is the next thing in the queue.

---

## Final acceptance

- [ ] **Acceptance #1:** `apps/site/src/content/interviews/` directory removed.
- [ ] **Acceptance #2:** `apps/site/src/content.config.ts` no longer defines `interviews` collection.
- [ ] **Acceptance #3:** "Interviews" nav-bar link removed from `Header.astro`.
- [ ] **Acceptance #4:** 72 new MDs in `apps/site/src/content/primary-works/` with `work_type: 'interview'`.
- [ ] **Acceptance #5:** ≥ 65 of those 72 have non-empty `thinker_mentions`, `summary`, `key_points`.
- [ ] **Acceptance #6:** 2 MDs have `transcript_status: 'unavailable'`; 1 has `transcript_status: 'none'`.
- [ ] **Acceptance #7:** `pnpm build` exits clean; page count grew by 72.
- [ ] **Acceptance #8:** `pytest scripts/synthesis/tests/test_migrate_interviews.py scripts/synthesis/tests/test_enrich_interviews.py -v` shows 22/22 passing.
- [ ] **Acceptance #9:** `git log origin/main..HEAD` is empty.

---

## Out of scope (per spec §2)

- UI changes (video embed, transcript renderer, listing-page filter UI) — follow-up spec.
- Editorial review of `needs_review: true` MDs.
- Thinker-stub creation for `thinker_unresolved` entries.
- NER / cross-ref audit re-run on the new interview-as-primary-work MDs.
- Sveltia CMS config updates (if any).
- Relaunching the v1.5 extraction pipeline (controller decision).

---

## Plan complete

After all chunks pass, the terminal state is:

1. 72 interview MDs migrated into `primary-works/` with `work_type: 'interview'`.
2. ~67 enriched with summary + key_points + thinker_mentions + key_passages + themes + (where resolvable) interviewer.
3. The `interviews` collection definition, directory, and nav-bar link removed.
4. ~67 new commits on `origin/main` (1 schema, 1 migration script, 1 migration run, 1 enrichment script, ~63 enrichment data commits in batches of 10 + 1 smoke + 1 final flush).
5. Adnan reviews the result, decides on the follow-up UI spec, optionally relaunches v1.5 extraction.
