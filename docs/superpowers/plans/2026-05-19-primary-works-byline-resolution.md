# Primary-works Byline Resolution Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve `authors[]` (and `contributors[]` when role-tagged) on the 179 of 378 primary-works that currently have no byline, auto-creating minimal stub thinker entries for author names not yet in the 453-thinker collection.

**Architecture:** Four-pass pipeline. Step 0 prepares a candidate set from each unbylined entry's title+slug. Step 1 is a Python-only deterministic exact-slug/initialism match against the existing thinker lookup. Step 2 batches the deferred entries to parallel Claude `Agent` subagents that match against the full thinkers list and emit a decision (known match / new-stub / needs-vision). Step 3 reads PDFs page 1–3 via Claude vision for entries that need it. Step 4 applies all three output sources to MD frontmatter, creating stub thinkers for unknowns and logging silent slug-collisions for curator review. Step 5 audits and writes a `curator-queue.md` file listing every entry needing human eyes.

**Tech Stack:** Astro 5 + Zod for the content layer; Python 3 stdlib for the pipeline (no new deps); Claude `Agent` subagents inside the Max session for LLM passes; hand-rolled YAML/regex frontmatter mutation matching the existing apply-ner.py / apply-classify.py / apply-extract.py convention.

**Spec reference (read this before starting):**
- [`docs/superpowers/specs/2026-05-19-primary-works-byline-resolution-design.md`](../specs/2026-05-19-primary-works-byline-resolution-design.md) — design + acceptance criteria, locked

**Pre-flight reading (in order, before Task 1):**
- `scripts/synthesis/apply-classify.py` — closest architectural sibling: frontmatter mutation via regex, --test mode, --dry-run flag, log emission
- `scripts/synthesis/apply-extract.py` — the most recent applier we shipped (the 49-PDF extraction); same patterns this plan mirrors
- `scripts/synthesis/prepare-classify-batches.py` — batch-emission shape Step 0 mirrors
- `scripts/synthesis/prompts/system-classify.txt` — system-prompt shape Step 3's prompt mirrors
- `apps/site/src/content.config.ts` lines 41–88 — `thinkers` defineCollection (where the `tradition` enum lives) and lines 187–325 — `primaryWorks` defineCollection (where `authors_resolution` goes)
- Sample stub thinker: `apps/site/src/content/thinkers/charan-singh.md` — current `bio_source: imported` shape; the v1 stub shape is similar but uses `bio_source: ai_drafted_stub`

**Working directory:** the active worktree (currently `.claude/worktrees/festive-kepler-096509` on `main`). All git operations target `main` unless otherwise noted.

**Verification harness:**
- Python: `.venv-extract/bin/python3 <script> --test` (plain-Python assert-style tests, no pytest). Phase B convention.
- Schema/build: `cd apps/site && pnpm build` (1,131 pages should still emit cleanly).

**Spec deviations logged here:** none expected. The spec is locked at commit `267cdeb`.

---

## File Structure

**Created (new files):**

```
data/byline-resolve/
├── candidates.jsonl                       # Step 0 output: per-entry candidate record
├── deterministic-resolved.jsonl           # Step 1 output: confident Python-pass hits
├── deferred.jsonl                         # Step 1 output: entries needing LLM judgment
├── llm-batch-NN.jsonl                     # Step 2 input batches (one per dispatch)
├── llm-output-NN.json                     # Step 2 output (per batch)
├── vision-output-<id>.json                # Step 3 output (per ambiguous entry)
├── dispatch.log                           # subagent failure log
├── collisions.log                         # Step 4: silent stub→existing-thinker collisions
├── apply-log.txt                          # Step 4 applier log
├── coverage-report.md                     # Step 5 audit output
└── curator-queue.md                       # Step 5: flat list of entries needing human review

scripts/synthesis/
├── prepare-byline-batches.py              # Step 0
├── resolve-byline-deterministic.py        # Step 1
├── prepare-byline-llm-batches.py          # Step 2 input prep
├── apply-byline.py                        # Step 4
├── audit-byline-coverage.py               # Step 5
└── prompts/
    └── system-byline.txt                  # Step 2 system prompt
```

**Modified:**

```
apps/site/src/content.config.ts            # two changes:
                                           #   - add 'unclassified' to tradition enum
                                           #   - add authors_resolution to primaryWorks
```

**Touched at runtime (committed when stable):**

```
apps/site/src/content/primary-works/*.md   # up to 179 bylined, ≤80 stubs referenced
apps/site/src/content/thinkers/*.md        # up to ~80 new stub MDs
```

---

## Chunk 1: Schema + scaffolding

Adds the two schema changes (tradition enum, authors_resolution object) and the data directory. End state: build still passes; primary-works can carry `authors_resolution` and stub thinkers can carry `tradition: unclassified` once the pipeline starts writing those.

### Task 1.1: Extend the tradition enum + add authors_resolution

**Files:**
- Modify: `apps/site/src/content.config.ts`

- [ ] **Step 1.1.1: Read the current schemas to confirm insertion points**

```bash
grep -n "const thinkers = defineCollection\|const primaryWorks = defineCollection" apps/site/src/content.config.ts
```

Use those line numbers to view each block (typically `sed -n '<L>,<L+40>p'` for thinkers and `sed -n '<L>,<L+90>p'` for primaryWorks). Locate (a) the `tradition: z.enum([...])` block in the thinkers schema and (b) a clean insertion point for `authors_resolution` in the primaryWorks schema — anywhere alongside other optional provenance-style fields. Good anchors: after `thinker_mentions:`, after `related_works:`, or after `contributors:`.

- [ ] **Step 1.1.2: Add `'unclassified'` to the tradition enum**

Find:

```ts
tradition: z.enum([
  'classical_liberal',
  'reformer',
  'nationalist_liberal',
  'social_reformer',
  'contemporary_liberal',
  'international_influence',
]),
```

Replace with:

```ts
tradition: z.enum([
  'classical_liberal',
  'reformer',
  'nationalist_liberal',
  'social_reformer',
  'contemporary_liberal',
  'international_influence',
  'unclassified',
]),
```

- [ ] **Step 1.1.3: Add `authors_resolution` to primaryWorks**

Insert at any clean point inside the primaryWorks schema, alongside other optional provenance-style fields (after `thinker_mentions:` is a good anchor):

```ts
    // Authors resolution provenance — populated by scripts/synthesis/apply-byline.py.
    // Lets the curator audit which entries were matched deterministically vs LLM vs
    // vision, which had to fall back to auto-stubbing new thinkers, and which had
    // silent slug-collisions with existing thinkers. See
    // docs/superpowers/specs/2026-05-19-primary-works-byline-resolution-design.md
    authors_resolution: z
      .object({
        confidence: z.enum(['high', 'medium', 'low']).optional(),
        method: z.enum(['deterministic', 'llm', 'vision']).optional(),
        proposed_unknowns: z.array(z.string()).default([]),
        stubs_created: z.array(z.string()).default([]),
        stubs_referenced: z.array(z.string()).default([]),
        collisions_logged: z.array(z.string()).default([]),
      })
      .optional(),
```

- [ ] **Step 1.1.4: Build to verify both changes parse**

Run:

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: build completes; "1,131 pages built"; no Zod errors.

- [ ] **Step 1.1.5: Commit**

```bash
git add apps/site/src/content.config.ts
git commit -m "$(cat <<'EOF'
feat(schema): authors_resolution on primary-works + 'unclassified' tradition

Two schema additions needed by the upcoming byline-resolution pipeline:

1. authors_resolution (optional object) on primaryWorks: tracks the
   confidence, method (deterministic/llm/vision), unknown names that
   were stubbed, slugs of new stubs created in this run, slugs of
   stubs referenced from same-run earlier creates, and slugs of silent
   collisions where the stub name slug-collided with a pre-existing
   thinker (curator must verify identity).

2. 'unclassified' added to the tradition enum on thinkers (was 6 values,
   now 7). The byline pipeline auto-creates stub thinkers for author
   names not in the existing 453-thinker collection; defaulting their
   tradition to 'unclassified' is more honest than guessing
   'contemporary_liberal' (the previous fallback pattern).

Refs docs/superpowers/specs/2026-05-19-primary-works-byline-resolution-design.md
EOF
)"
```

### Task 1.2: Scaffold the data directory

**Files:**
- Create: `data/byline-resolve/.gitkeep`

- [ ] **Step 1.2.1: Create the directory + gitkeep**

```bash
mkdir -p data/byline-resolve
touch data/byline-resolve/.gitkeep
```

- [ ] **Step 1.2.2: Commit**

```bash
git add data/byline-resolve/.gitkeep
git commit -m "data: scaffold byline-resolve directory"
```

---

**End of Chunk 1.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 2: Step 0 + Step 1 (candidate prep + deterministic resolver)

Two pure-Python scripts. The first emits a candidate JSONL with tokenized author-name candidates from each unbylined entry's title+slug. The second loads the thinker collection and matches deterministically; ambiguous and no-match cases get deferred to Step 2.

### Task 2.1: `scripts/synthesis/prepare-byline-batches.py`

**Files:**
- Create: `scripts/synthesis/prepare-byline-batches.py`

- [ ] **Step 2.1.1: Write the script**

```python
#!/usr/bin/env python3
"""
Step 0 of the byline-resolution pipeline.

Walks apps/site/src/content/primary-works/*.md, finds entries where
authors[] is empty AND contributors[] has no thinker refs, and emits
a candidate JSONL record per entry. Each record carries title, slug,
work_type, year, pdf_staging_path, and a list of token_candidates
heuristically extracted from title+slug.

Token-candidate extraction:
  1. Take title.main + slug (id) as input.
  2. Replace common separators (by, —, ·, :, ,, em-dash, en-dash, /, " - ")
     with spaces. Split on whitespace.
  3. For each token: lowercase, kebab-case (collapse punctuation+ws to '-'),
     trim trailing/leading '-'.
  4. Drop tokens matching any of:
     - Honorifics (whole-token): dr, dr., mr, mr., mrs, mrs., ms, ms.,
       prof, prof., shri, sir, sri, smt, lady, lord
     - Year regex: \\b(19|20)\\d{2}\\b anywhere in token
     - Month names + abbreviations: january..december + jan..dec
     - Day ordinals/numerals: ^[0-9]+(st|nd|rd|th)?$
     - Roman ordinals (conference labels): ^[ivxlcdm]+$
     - The literal token 'by'

Run:
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-batches.py
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-batches.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW_DIR = ROOT / "apps/site/src/content/primary-works"
OUT = ROOT / "data/byline-resolve/candidates.jsonl"

# Module-level constants so reviewer and implementer can audit the drop-list.
HONORIFICS = {
    "dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.",
    "prof", "prof.", "shri", "sir", "sri", "smt", "lady", "lord",
}
MONTHS = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
}
_YEAR_RX = re.compile(r"\b(19|20)\d{2}\b")
_DAY_RX = re.compile(r"^[0-9]+(st|nd|rd|th)?$")
# Roman numeral pattern targeting conference labels like III, IV, XVIII. Tightened
# to start with a roman-numeral lead (i/v/x) so 3-char Indic surname tokens that
# happen to consist only of [cdlm] characters (e.g. 'mil', 'mid', 'lid') are NOT
# false-dropped. A token like 'iii' / 'iv' / 'xviii' still drops; 'mil' / 'vid' /
# 'lid' survive.
_ROMAN_RX = re.compile(r"^[ivx][ivxlcdm]*$")
_SLUG_RX = re.compile(r"^[a-z][a-z0-9-]*$")

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def parse_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm = m.group(1)

    # Title.main (handle quoted + bare YAML scalar)
    tm = re.search(r"^\s+main:\s*[\"']?(.+?)[\"']?\s*$", fm, re.M)
    title = tm.group(1).strip() if tm else ""

    wt = re.search(r"^work_type:\s*[\"']?([a-z_]+)[\"']?", fm, re.M)
    work_type = wt.group(1) if wt else None

    yr = re.search(r"^\s+year:\s*(\d{4})", fm, re.M)
    year = int(yr.group(1)) if yr else None

    pdf = re.search(r'^pdf_staging_path:\s*"?([^"\n]+?)"?\s*$', fm, re.M)
    pdf_path = pdf.group(1).strip() if pdf else None

    # Detect existing bylines: authors[] non-empty OR contributors[] with thinker:
    has_authors = bool(re.search(r"^authors:\s*\n\s+-\s+", fm, re.M))
    has_contribs = bool(re.search(r"^contributors:\s*\n\s+-\s+thinker:", fm, re.M))

    return {
        "title": title,
        "work_type": work_type,
        "year": year,
        "pdf_staging_path": pdf_path,
        "has_byline": has_authors or has_contribs,
    }


def tokenize(title: str, slug: str) -> list[str]:
    """Return the de-duplicated, drop-list-filtered token candidates."""
    raw = f"{title} {slug}"
    # Normalize separators
    raw = re.sub(r"[—–\-–—·:,/]", " ", raw)
    raw = re.sub(r"\bby\b", " ", raw, flags=re.IGNORECASE)
    tokens: list[str] = []
    for piece in raw.split():
        # kebab the piece: lowercase, punctuation→hyphen, collapse, strip
        kebab = piece.lower()
        kebab = re.sub(r"[^a-z0-9]+", "-", kebab)
        kebab = re.sub(r"-+", "-", kebab).strip("-")
        if not kebab:
            continue
        # Drop-list checks
        if kebab in HONORIFICS:
            continue
        if kebab in MONTHS:
            continue
        if _YEAR_RX.search(kebab):
            continue
        if _DAY_RX.match(kebab):
            continue
        if _ROMAN_RX.match(kebab) and len(kebab) <= 6:
            # Tightened pattern starts with i/v/x so 'mil' / 'vid' / 'lid' (potential
            # Indic surname tokens consisting only of [cdlm]) survive; only true
            # roman-led conference labels (iii, iv, xviii) drop.
            continue
        tokens.append(kebab)
    # Deduplicate, preserve order
    return list(dict.fromkeys(tokens))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_total = n_bylined = n_unbylined = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for md in sorted(PW_DIR.glob("*.md")):
            n_total += 1
            parsed = parse_frontmatter(md)
            if not parsed:
                continue
            if parsed["has_byline"]:
                n_bylined += 1
                continue
            n_unbylined += 1
            rec = {
                "id": md.stem,
                "title": parsed["title"],
                "slug": md.stem,
                "work_type": parsed["work_type"],
                "year": parsed["year"],
                "pdf_staging_path": parsed["pdf_staging_path"],
                "token_candidates": tokenize(parsed["title"], md.stem),
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  total primary-works: {n_total}")
    print(f"  with byline already: {n_bylined}")
    print(f"  unbylined → emitted: {n_unbylined}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


def _run_tests():
    # tokenize() — happy path
    assert tokenize("Free Enterprise and Democracy", "free-enterprise-and-democracy-a-d-shroff-feb11-1956") == [
        "free", "enterprise", "and", "democracy", "a", "d", "shroff",
    ], tokenize("Free Enterprise and Democracy", "free-enterprise-and-democracy-a-d-shroff-feb11-1956")

    # Honorifics drop
    assert "dr" not in tokenize("Dr. B. P. Godrej", "")
    assert "mr" not in tokenize("Mr. R. Mody", "")
    assert "prof" not in tokenize("Prof. Gangadhar", "")

    # Year drop
    assert "1956" not in tokenize("", "speech-1956-shroff")
    assert "feb11" not in tokenize("", "feb11-1956")  # year regex catches the embedded year

    # Month drop
    assert "january" not in tokenize("January Lecture", "")
    assert "feb" not in tokenize("Feb Lecture", "")

    # Day-ordinal drop
    assert "1st" not in tokenize("1st", "")
    assert "25" not in tokenize("25", "")

    # Roman-numeral drop (short conference labels)
    assert "iii" not in tokenize("III Conference", "")
    assert "xviii" not in tokenize("XVIII Lecture", "")
    assert "iv" not in tokenize("IV Symposium", "")
    # Indic surname tokens that look superficially roman are KEPT:
    assert "mil" in tokenize("S. K. Mil Lecture", "S-K-Mil-1972"), "mil should survive (no roman lead)"
    assert "vid" in tokenize("R. K. Vid", "r-k-vid"), "vid should survive (no roman lead)"
    assert "lid" in tokenize("P. Lid Speech", "p-lid"), "lid should survive (no roman lead)"

    # 'by' drop
    assert "by" not in tokenize("Free Markets by Friedman", "")

    # Slug already kebab-cased survives
    assert "a-d-shroff" in tokenize("", "free-enterprise-a-d-shroff-1956") or \
           ("a" in tokenize("", "free-enterprise-a-d-shroff-1956") and
            "d" in tokenize("", "free-enterprise-a-d-shroff-1956"))

    # Deduplication
    out = tokenize("Free Enterprise", "free-enterprise-speech")
    assert out.count("free") == 1
    assert out.count("enterprise") == 1

    print("prepare-byline-batches tests passed.")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.1.2: Run inline tests**

```bash
.venv-extract/bin/python3 scripts/synthesis/prepare-byline-batches.py --test
```

Expected: `prepare-byline-batches tests passed.`

- [ ] **Step 2.1.3: Run for real**

```bash
.venv-extract/bin/python3 scripts/synthesis/prepare-byline-batches.py
```

Expected output approximately:

```
  total primary-works: 378
  with byline already: 199
  unbylined → emitted: 179
  wrote data/byline-resolve/candidates.jsonl
```

If the unbylined count is wildly different (>200 or <150), STOP and report — the byline detection regex is probably wrong.

- [ ] **Step 2.1.4: Spot-check one candidate record**

```bash
head -1 data/byline-resolve/candidates.jsonl | python3 -m json.tool
```

Expected: a well-formed JSON record with `id`, `title`, `slug`, `work_type`, `year`, `pdf_staging_path`, and a `token_candidates` list of 4–10 lowercase kebab tokens.

- [ ] **Step 2.1.5: Commit**

```bash
git add scripts/synthesis/prepare-byline-batches.py data/byline-resolve/candidates.jsonl
git commit -m "feat(synthesis): prepare-byline-batches.py emits Step 0 candidates

Walks primary-works, finds the 179 unbylined entries (authors[] empty AND
no thinker refs in contributors[]), emits one candidate JSONL record per
entry with tokenized author-name candidates extracted from title+slug.
Drop-list filters honorifics, years, month names, day-ordinals, short
Roman numerals, and the literal token 'by'.

Step 0 of the byline-resolution pipeline."
```

### Task 2.2: `scripts/synthesis/resolve-byline-deterministic.py`

**Files:**
- Create: `scripts/synthesis/resolve-byline-deterministic.py`

- [ ] **Step 2.2.1: Write the script**

```python
#!/usr/bin/env python3
"""
Step 1 of the byline-resolution pipeline.

Loads the 453 thinkers into a normalised lookup (canonical kebab → canonical
slug; each also_known_as kebab → canonical slug). For each candidate record
in data/byline-resolve/candidates.jsonl, tries to match any token_candidate
against the lookup.

Match outcomes:
  - Unambiguous single match → emit to deterministic-resolved.jsonl with
    confidence: high, method: deterministic.
  - Multiple tokens match multiple different thinkers → defer to Step 2.
  - No match → defer to Step 2.

Note: empty also_known_as: [] is treated as "no aliases" — the loader must
not fail on the empty list case.

Run:
    .venv-extract/bin/python3 scripts/synthesis/resolve-byline-deterministic.py
    .venv-extract/bin/python3 scripts/synthesis/resolve-byline-deterministic.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
CANDIDATES = ROOT / "data/byline-resolve/candidates.jsonl"
RESOLVED = ROOT / "data/byline-resolve/deterministic-resolved.jsonl"
DEFERRED = ROOT / "data/byline-resolve/deferred.jsonl"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)
_CANONICAL_RX = re.compile(r"^\s+canonical:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_AKA_BLOCK_RX = re.compile(r"^\s+also_known_as:\s*\n((?:\s+-\s+.+\n?)+)", re.M)
_EMPTY_AKA_RX = re.compile(r"^\s+also_known_as:\s*\[\]", re.M)


def kebab(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def build_thinker_lookup() -> dict[str, str]:
    """Return mapping kebab-key → canonical-slug (the thinker file stem)."""
    lookup: dict[str, str] = {}
    for md in sorted(THINKERS_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FRONTMATTER_RX.match(text)
        if not m:
            continue
        fm = m.group(1)
        slug = md.stem
        # Canonical → slug
        cn = _CANONICAL_RX.search(fm)
        if cn:
            lookup[kebab(cn.group(1))] = slug
        # The slug itself is always a key
        lookup[slug] = slug
        # also_known_as
        if _EMPTY_AKA_RX.search(fm):
            continue
        ab = _AKA_BLOCK_RX.search(fm)
        if not ab:
            continue
        for line in ab.group(1).splitlines():
            sub = re.match(r"\s+-\s+[\"']?(.+?)[\"']?\s*$", line)
            if sub:
                lookup[kebab(sub.group(1))] = slug
    return lookup


def match_candidates(tokens: list[str], lookup: dict[str, str]) -> list[str]:
    """Return list of unique canonical slugs that any token matched.

    Also attempts to recombine consecutive single-letter tokens that look
    like initials (e.g., ['a', 'd', 'shroff'] → also try 'a-d-shroff').
    """
    hits: list[str] = []

    # Direct token matches
    for t in tokens:
        if t in lookup:
            hits.append(lookup[t])

    # Initialism recombination: walk runs of single-letter tokens followed
    # by a multi-letter token, build joined keys.
    for i in range(len(tokens)):
        # Collect run of single chars starting at i
        if len(tokens[i]) != 1:
            continue
        j = i
        while j < len(tokens) and len(tokens[j]) == 1:
            j += 1
        if j >= len(tokens):
            continue
        # tokens[i:j] are single chars, tokens[j] is a multi-char name
        joined = "-".join(tokens[i : j + 1])
        if joined in lookup:
            hits.append(lookup[joined])

    return list(dict.fromkeys(hits))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    if not CANDIDATES.exists():
        print(f"ERROR: {CANDIDATES} not found. Run prepare-byline-batches.py first.", file=sys.stderr)
        return 1

    lookup = build_thinker_lookup()
    print(f"thinker lookup size: {len(lookup)} keys → {len(set(lookup.values()))} unique slugs")

    n_resolved = n_deferred = n_ambiguous = 0
    with RESOLVED.open("w", encoding="utf-8") as f_res, \
         DEFERRED.open("w", encoding="utf-8") as f_def, \
         CANDIDATES.open("r", encoding="utf-8") as f_in:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            hits = match_candidates(rec.get("token_candidates", []), lookup)
            if len(hits) == 1:
                # Unambiguous single match
                out = {
                    "id": rec["id"],
                    "matches": [{"slug": hits[0], "role": "author"}],
                    "confidence": "high",
                    "method": "deterministic",
                }
                f_res.write(json.dumps(out, ensure_ascii=False) + "\n")
                n_resolved += 1
            elif len(hits) > 1:
                # Multiple distinct matches — defer
                rec["deterministic_hits"] = hits
                f_def.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_ambiguous += 1
            else:
                # No match — defer
                f_def.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_deferred += 1
    print(f"  resolved deterministically: {n_resolved}")
    print(f"  deferred (no match): {n_deferred}")
    print(f"  deferred (ambiguous, ≥2 matches): {n_ambiguous}")
    print(f"  wrote {RESOLVED.relative_to(ROOT)} + {DEFERRED.relative_to(ROOT)}")
    return 0


def _run_tests():
    # kebab
    assert kebab("A. D. Shroff") == "a-d-shroff"
    assert kebab("  N.A. Palkhivala ") == "n-a-palkhivala"
    assert kebab("R.C. Cooper") == "r-c-cooper"

    # match_candidates: direct match
    lookup = {
        "a-d-shroff": "a-d-shroff",
        "ardeshir-darabshaw-shroff": "a-d-shroff",
        "nani-palkhivala": "nani-palkhivala",
        "milton-friedman": "milton-friedman",
    }
    assert match_candidates(["a-d-shroff", "1956"], lookup) == ["a-d-shroff"]
    assert match_candidates(["nani-palkhivala"], lookup) == ["nani-palkhivala"]

    # match_candidates: initialism recombination
    # tokens ['a', 'd', 'shroff'] should match 'a-d-shroff'
    assert match_candidates(["a", "d", "shroff"], lookup) == ["a-d-shroff"]
    assert match_candidates(["free", "enterprise", "a", "d", "shroff"], lookup) == ["a-d-shroff"]

    # match_candidates: no match
    assert match_candidates(["random", "tokens"], lookup) == []

    # match_candidates: trailing multi-letter token after initialism run
    # j stops at the first multi-letter token; subsequent multi-letter tokens
    # like 'lecture' are NOT consumed into the initialism key.
    assert match_candidates(["a", "d", "shroff", "lecture"], lookup) == ["a-d-shroff"]
    assert match_candidates(["free", "a", "d", "shroff", "lecture"], lookup) == ["a-d-shroff"]

    # match_candidates: multi-hit ambiguity
    lookup2 = {**lookup, "a-d-iyer": "a-d-iyer"}
    # Single 'a' wouldn't match anything (single-letter alone), but
    # an aka collision could; not exercising that path in tests.

    # Empty token list
    assert match_candidates([], lookup) == []

    # build_thinker_lookup: empty also_known_as: [] must not crash.
    # We exercise this against an actual temp-dir of two thinker files,
    # one with populated AKAs and one with the empty-list form.
    import tempfile
    sample_populated = '''---
id: foo-bar
name:
  canonical: "Foo Bar"
  also_known_as:
    - "F. Bar"
    - "Foo B."
---
'''
    sample_empty = '''---
id: baz-qux
name:
  canonical: "Baz Qux"
  also_known_as: []
---
'''
    global THINKERS_DIR
    orig_th = THINKERS_DIR
    try:
        with tempfile.TemporaryDirectory() as td:
            THINKERS_DIR = Path(td)
            (THINKERS_DIR / "foo-bar.md").write_text(sample_populated)
            (THINKERS_DIR / "baz-qux.md").write_text(sample_empty)
            lookup3 = build_thinker_lookup()
            # Both canonical names + the aka aliases land in the lookup;
            # empty-aka thinker still gets its canonical + slug entries.
            assert lookup3.get("foo-bar") == "foo-bar"
            assert lookup3.get("f-bar") == "foo-bar"
            assert lookup3.get("foo-b") == "foo-bar"
            assert lookup3.get("baz-qux") == "baz-qux"
    finally:
        THINKERS_DIR = orig_th

    print("resolve-byline-deterministic tests passed.")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.2.2: Run inline tests**

```bash
.venv-extract/bin/python3 scripts/synthesis/resolve-byline-deterministic.py --test
```

Expected: `resolve-byline-deterministic tests passed.`

- [ ] **Step 2.2.3: Run for real**

```bash
.venv-extract/bin/python3 scripts/synthesis/resolve-byline-deterministic.py
```

Expected approximately:

```
thinker lookup size: 1200-1500 keys → 453 unique slugs
  resolved deterministically: 70-90
  deferred (no match): 60-80
  deferred (ambiguous, ≥2 matches): 20-40
  wrote data/byline-resolve/deterministic-resolved.jsonl + ...deferred.jsonl
```

The deterministic-resolved count should be ≥40% of 179 (≥72). If it's much lower, the lookup builder or token matching has a bug.

- [ ] **Step 2.2.4: Spot-check 5 resolutions for sanity**

```bash
python3 -c "
import json, random
lines = open('data/byline-resolve/deterministic-resolved.jsonl').read().splitlines()
for line in random.sample(lines, min(5, len(lines))):
    r = json.loads(line)
    print(f'  {r[\"id\"]:<70} → {r[\"matches\"][0][\"slug\"]}')
"
```

(Uses `random.sample` rather than `shuf` since `shuf` isn't in stock macOS coreutils.)

Expected: each resolved entry's slug should plausibly match the title. Spot-check 2–3 manually by reading the primary-work title; the matched thinker slug should match the surname/initials.

- [ ] **Step 2.2.5: Commit**

```bash
git add scripts/synthesis/resolve-byline-deterministic.py data/byline-resolve/deterministic-resolved.jsonl data/byline-resolve/deferred.jsonl
git commit -m "feat(synthesis): resolve-byline-deterministic.py (Step 1)

Loads the 453 thinkers into a normalised lookup (canonical + every
also_known_as, both kebab-cased), then matches each candidate's
token_candidates against it. Single-letter token runs are recombined
into initialism keys (a, d, shroff → a-d-shroff). Empty also_known_as: []
is handled gracefully.

Unambiguous single match → deterministic-resolved.jsonl with
confidence: high. Multiple matches or no match → deferred.jsonl.
Expected ≥40% deterministic-hit rate on the 179 unbylined entries."
```

---

**End of Chunk 2.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 3: Step 2 (LLM batched matching)

Per-batch JSONL prep, system-prompt with the locked decision tree + worked examples, and a documented dispatch protocol. The orchestrator is the Max session itself (Claude in interactive mode emits parallel `Agent` calls), matching the classification + extraction execution model — there is no `dispatch-byline.py` script.

### Task 3.1: `scripts/synthesis/prepare-byline-llm-batches.py`

**Files:**
- Create: `scripts/synthesis/prepare-byline-llm-batches.py`

- [ ] **Step 3.1.1: Write the script**

```python
#!/usr/bin/env python3
"""
Step 2 input prep: chunk deferred.jsonl into LLM batches of ~20 entries each.

Each batch carries: a list of deferred-entry candidate records (with their
token_candidates, year, work_type, title, and any deterministic_hits that
were ambiguous in Step 1). The full thinkers list is NOT inlined into each
batch JSONL — it's inlined into the system prompt by render-system-byline.py
to keep batch files small and the prompt versioned.

Run:
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-llm-batches.py
    .venv-extract/bin/python3 scripts/synthesis/prepare-byline-llm-batches.py --test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFERRED = ROOT / "data/byline-resolve/deferred.jsonl"
OUT_DIR = ROOT / "data/byline-resolve"
BATCH_SIZE = 20


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        print("prepare-byline-llm-batches: no inline unit tests (pure I/O batching)")
        return 0

    if not DEFERRED.exists():
        print(f"ERROR: {DEFERRED} not found. Run resolve-byline-deterministic.py first.", file=sys.stderr)
        return 1

    # Wipe stale batches for reproducibility
    for stale in OUT_DIR.glob("llm-batch-*.jsonl"):
        stale.unlink()

    records = [json.loads(l) for l in DEFERRED.read_text().splitlines() if l.strip()]
    n_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(n_batches):
        chunk = records[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        out_path = OUT_DIR / f"llm-batch-{i:02d}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for rec in chunk:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"wrote {out_path.relative_to(ROOT)}  ({len(chunk)} records)")
    print(f"total: {len(records)} records across {n_batches} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3.1.2: Run inline tests + real prep**

```bash
.venv-extract/bin/python3 scripts/synthesis/prepare-byline-llm-batches.py --test
.venv-extract/bin/python3 scripts/synthesis/prepare-byline-llm-batches.py
```

Expected: ~5–6 batch files, ~80–110 records total.

- [ ] **Step 3.1.3: Commit**

```bash
git add scripts/synthesis/prepare-byline-llm-batches.py data/byline-resolve/llm-batch-*.jsonl
git commit -m "feat(synthesis): prepare-byline-llm-batches.py + Step 2 input batches"
```

### Task 3.2: `scripts/synthesis/prompts/system-byline.txt` (via render script)

**Files:**
- Create: `scripts/synthesis/render-system-byline.py`
- Generated: `scripts/synthesis/prompts/system-byline.txt`

- [ ] **Step 3.2.1: Write the render helper script**

```python
#!/usr/bin/env python3
"""
Render scripts/synthesis/prompts/system-byline.txt from the live thinker
collection. Re-run whenever new thinkers are added to keep the inlined
list current.

Run:
    .venv-extract/bin/python3 scripts/synthesis/render-system-byline.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
OUT = ROOT / "scripts/synthesis/prompts/system-byline.txt"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)
_CANONICAL_RX = re.compile(r"^\s+canonical:\s*[\"']?(.+?)[\"']?\s*$", re.M)
_AKA_BLOCK_RX = re.compile(r"^\s+also_known_as:\s*\n((?:\s+-\s+.+\n?)+)", re.M)


def parse_thinker(path: Path) -> tuple[str, str, list[str]]:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return path.stem, path.stem, []
    fm = m.group(1)
    canonical = ""
    cn = _CANONICAL_RX.search(fm)
    if cn:
        canonical = cn.group(1).strip()
    akas: list[str] = []
    ab = _AKA_BLOCK_RX.search(fm)
    if ab:
        for line in ab.group(1).splitlines():
            sub = re.match(r"\s+-\s+[\"']?(.+?)[\"']?\s*$", line)
            if sub:
                akas.append(sub.group(1).strip())
    return path.stem, canonical, akas


TEMPLATE = """You are matching primary-work author bylines to the existing thinkers collection. The corpus is the Indian Liberals digital archive (indianliberals.in). Each entry is a primary work (book / pamphlet / speech / essay / periodical / occasional paper / letter) that currently has no resolved author. Your job is to read each entry's title, slug, work_type, year, and the token candidates we already extracted, and decide:

  (a) the author matches a thinker in the list below → emit a match
  (b) the author is clearly named but isn't in the list → emit as unknown for stub creation
  (c) you can't be confident either way → flag for vision (PDF read)

# Per-entry decision tree

For each input entry, apply this rubric in order:

  1. Can you find a SINGLE high-confidence match in the thinkers list?
     → emit { id, matches: [{slug, role}], confidence: "high" }

  2. Multiple plausible matches; you can pick one via context (year/topic/publisher)?
     → emit { id, matches: [{slug, role}], confidence: "medium" }

  3. A name is CLEARLY present in title/slug but isn't in the thinkers list?
     → emit { id, unknowns: ["Name As It Appears"], confidence: "medium" }
     (the applier will auto-create a stub)

  4. A name is HINTED but you cannot commit to either a match or a stub?
     → emit { id, needs_vision: true }
     (Step 3 will read the PDF title page)

  5. No name signal anywhere in title/slug?
     → emit { id, needs_vision: true }

# Role detection

When you see editor / translator / foreword markers in the title (e.g., "edited by X", "foreword by Y", "translated by Z"), use role values "editor" / "translator" / "foreword" / "introduction" / "preface". Otherwise role is "author".

A work can have MULTIPLE matches with different roles — emit them all in matches[].

# Output format

A single top-level JSON ARRAY of one record per input piece, in the same order as the input batch. Each record has:

```json
{
  "id": "<echo from input>",
  "matches": [{"slug": "a-d-shroff", "role": "author"}],
  "unknowns": ["Some Name Not In List"],
  "needs_vision": false,
  "confidence": "high"
}
```

`matches`, `unknowns` default to []; `needs_vision` defaults to false; `confidence` is one of "high" | "medium" | "low".

# Confidence rubric

  - high: unambiguous match OR signed first-person attribution clear from title
  - medium: plausible match via context, OR stub-creation for a name clearly present but new
  - low: weak inference; consider needs_vision instead

# Worked examples

INPUT:
```
{"id": "free-enterprise-and-democracy-a-d-shroff-feb11-1956", "title": "Free Enterprise and Democracy", "year": 1956, "token_candidates": ["free", "enterprise", "and", "democracy", "a", "d", "shroff"]}
```
OUTPUT:
```
{"id": "free-enterprise-and-democracy-a-d-shroff-feb11-1956", "matches": [{"slug": "a-d-shroff", "role": "author"}], "confidence": "high"}
```

INPUT:
```
{"id": "a-package-plan-for-inflation-dr-r-c-cooper-dhirajlal-maganlal-minoo-r-shroff-prof-gangadhar-gadgil-july-1974", "title": "A Package Plan for Inflation", "year": 1974, "token_candidates": ["a", "package", "plan", "for", "inflation", "r", "c", "cooper", "dhirajlal", "maganlal", "minoo", "r", "shroff", "gangadhar", "gadgil"]}
```
OUTPUT:
```
{"id": "a-package-plan-for-inflation-dr-r-c-cooper-dhirajlal-maganlal-minoo-r-shroff-prof-gangadhar-gadgil-july-1974", "matches": [{"slug": "r-c-cooper", "role": "author"}, {"slug": "minoo-shroff", "role": "author"}], "unknowns": ["Dhirajlal Maganlal", "Gangadhar Gadgil"], "confidence": "high"}
```
(Note: multiple authors. R.C. Cooper and Minoo Shroff are existing thinkers. Dhirajlal Maganlal and Gangadhar Gadgil are NOT in the thinkers list — they go to unknowns[] for stub auto-creation. Always cross-check candidate slugs against the inlined thinkers list below before emitting them in matches[]; if a slug isn't in the list, the name goes to unknowns[] instead.)

INPUT (illustrative — assume the inlined thinkers list does NOT contain a slug that matches both initials and surname):
```
{"id": "the-economics-of-monsoon-failure-p-mehta-1979", "title": "The Economics of Monsoon Failure", "year": 1979, "token_candidates": ["the", "economics", "of", "monsoon", "failure", "p", "mehta"]}
```
OUTPUT:
```
{"id": "the-economics-of-monsoon-failure-p-mehta-1979", "needs_vision": true, "confidence": "low"}
```
(Branch 4 — a name token IS present ("P. Mehta") but only with a single initial. The inlined thinkers list may contain multiple plausible `P. Mehta`-shaped entries — `p-k-mehta`, `p-r-mehta`, `pravin-mehta` — and the title alone cannot disambiguate. Rather than auto-stubbing `p-mehta` (which would risk a silent collision with the wrong existing thinker) or guessing one of the candidates, defer to the PDF title page. ALWAYS cross-check candidate slugs against the actual inlined thinkers list before committing to either a match or a stub; when adjacent initials/surnames cluster ambiguously, prefer needs_vision: true.)

INPUT:
```
{"id": "implications-of-bank-nationalisation-misc-mar9-1964", "title": "Implications of Bank Nationalisation", "year": 1964, "token_candidates": ["implications", "of", "bank", "nationalisation", "misc"]}
```
OUTPUT:
```
{"id": "implications-of-bank-nationalisation-misc-mar9-1964", "needs_vision": true, "confidence": "low"}
```
(Branch 5 — no author token in title; 'misc' suggests anthology; PDF read needed.)

# Thinkers list (canonical slug + canonical name + aliases)

{THINKERS_LIST}

# Now classify

Read your input batch and emit one JSON record per entry, in batch order, as a single top-level array. Reply with NOTHING ELSE — no commentary, no markdown fence around the JSON. Just the array.
"""


def main() -> None:
    entries = []
    for p in sorted(THINKERS_DIR.glob("*.md")):
        slug, canonical, akas = parse_thinker(p)
        if not canonical:
            continue
        aka_str = f"  aka: {', '.join(akas)}" if akas else ""
        entries.append(f"  - {slug:<45} {canonical}{aka_str}")
    rendered = TEMPLATE.replace("{THINKERS_LIST}", "\n".join(entries))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(rendered)} chars, {len(entries)} thinkers inlined)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3.2.2: Render the prompt**

```bash
.venv-extract/bin/python3 scripts/synthesis/render-system-byline.py
```

Expected: `wrote scripts/synthesis/prompts/system-byline.txt (~25000-35000 chars, ~453 thinkers inlined)`

- [ ] **Step 3.2.3: Spot-check the prompt**

```bash
head -30 scripts/synthesis/prompts/system-byline.txt
grep -c "^  - " scripts/synthesis/prompts/system-byline.txt
```

Expected: header + decision tree visible; ~453 lines beginning `  - ` (one per thinker).

- [ ] **Step 3.2.4: Commit**

```bash
git add scripts/synthesis/render-system-byline.py scripts/synthesis/prompts/system-byline.txt
git commit -m "feat(synthesis): byline-resolution system prompt + render helper

system-byline.txt inlines all 453 thinkers (canonical slug + canonical
name + aliases) plus the 5-branch decision tree for the LLM matching
pass. Three worked examples demonstrate single-match-high-confidence,
multi-author-with-unknowns, and no-byline-needs-vision paths.

Re-render via render-system-byline.py whenever the thinker collection
grows."
```

### Task 3.3: Dispatch protocol (operator action — no script)

**Files:** none. Documents the protocol the operator (Claude in the Max session) follows at runtime.

- [ ] **Step 3.3.1: Read the dispatch protocol below**

For each batch `llm-batch-NN.jsonl`, dispatch one Claude `Agent`-tool subagent with this prompt template:

```
You are a byline-resolution subagent. Read the system prompt and the
input batch, then emit a JSON array of matches.

System prompt:
  /Users/siraj/Indian Liberals Website/scripts/synthesis/prompts/system-byline.txt

Input batch:
  /Users/siraj/Indian Liberals Website/data/byline-resolve/llm-batch-NN.jsonl  ← REPLACE NN

For each record in the batch, decide per the system prompt's 5-branch
decision tree. Echo the `id` from each input record exactly.

Write the output as a single top-level JSON array to:
  /Users/siraj/Indian Liberals Website/data/byline-resolve/llm-output-NN.json  ← REPLACE NN

When done, reply with: "wrote N records to data/byline-resolve/llm-output-NN.json" — nothing else.
```

- [ ] **Step 3.3.2: Dispatch all batches in a single message (parallel waves)**

Dispatch up to 8 `Agent` calls in one message. For 5–6 batches that's one wave; if more, a second wave. Wait for all to report back before continuing.

- [ ] **Step 3.3.3: Verify outputs**

```bash
ls data/byline-resolve/llm-output-*.json | wc -l
.venv-extract/bin/python3 -c "
import json, glob
for f in sorted(glob.glob('data/byline-resolve/llm-output-*.json')):
    arr = json.loads(open(f).read())
    print(f'  {f}: {len(arr)} records')
"
```

Expected: file count matches batch count; record counts add up to the deferred total.

- [ ] **Step 3.3.4: Re-dispatch any failed batch**

If a batch is missing, has 0 records, or has malformed JSON, log to `data/byline-resolve/dispatch.log`:

```bash
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  llm-batch-NN  <failure-type>" >> data/byline-resolve/dispatch.log
```

Then re-dispatch that single batch using the same template.

- [ ] **Step 3.3.5: Commit the outputs**

```bash
git add data/byline-resolve/llm-output-*.json data/byline-resolve/dispatch.log 2>/dev/null || true
git commit -m "data: Step 2 LLM-pass outputs (~80 deferred entries resolved)"
```

---

**End of Chunk 3.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 4: Step 3 (vision fallback)

For entries flagged `needs_vision: true` in Step 2, dispatch one Claude vision subagent per entry. Each reads the PDF's first 1–3 pages and emits a per-entry vision-output JSON. No new scripts — pure dispatch.

### Task 4.1: Identify needs-vision entries

- [ ] **Step 4.1.1: Extract the needs-vision list**

```bash
cd "/Users/siraj/Indian Liberals Website"
.venv-extract/bin/python3 <<'PY'
import json, glob
needs_vision = []
for f in sorted(glob.glob('data/byline-resolve/llm-output-*.json')):
    for rec in json.loads(open(f).read()):
        if rec.get('needs_vision'):
            needs_vision.append(rec['id'])
print(f"Entries needing vision: {len(needs_vision)}")
for n in needs_vision:
    print(f"  {n}")
# Save for the next step
import pathlib
pathlib.Path('data/byline-resolve/needs-vision.txt').write_text("\n".join(needs_vision) + "\n")
PY
```

Expected: ~10–25 IDs printed.

### Task 4.2: Dispatch vision subagents (operator action)

- [ ] **Step 4.2.1: For each needs-vision id, dispatch one vision subagent**

Subagent prompt template (per entry):

```
You are a byline-resolution vision subagent. Use Claude's vision to read
the PDF title page and decide on the author.

Step 1: read the system prompt at:
  /Users/siraj/Indian Liberals Website/scripts/synthesis/prompts/system-byline.txt
That file contains the locked thinkers list (453 entries with canonical
slugs + AKAs) and the decision rubric — load it first so you can match
PDF-found names against existing thinker slugs.

Step 2: look up your entry context. The inventory file is at
  /Users/siraj/Indian Liberals Website/data/byline-resolve/candidates.jsonl
Find the record whose `id` matches <id>; pull its `title`, `year`,
`token_candidates`, and `pdf_staging_path`.

Step 3: read the PDF. Compute the absolute PDF path by prepending
"/Volumes/One Touch/Indian Liberals/" to the staging path. Use the
Read tool with `pages: "1-3"` — title page + copyright page + first
content page usually carry the byline.

Step 4: decide per the system prompt's decision tree — branches 1
(high-confidence match), 2 (medium match via context), or 3 (clearly
named but not in list → stub via unknowns[]). Do NOT flag
needs_vision: true again; you ARE the vision pass.

Step 5: write a single JSON object (NOT an array; one record only) to:
  /Users/siraj/Indian Liberals Website/data/byline-resolve/vision-output-<id>.json
Use this schema:
  {
    "id": "<echo>",
    "matches": [{"slug": "...", "role": "author"}],     // optional
    "unknowns": ["Name as appears on title page"],       // optional
    "confidence": "high" | "medium" | "low",
    "method": "vision"
  }

If the PDF file doesn't exist at the expected path, emit:
  { "id": "<id>", "unresolved": true, "reason": "pdf-missing",
    "confidence": "low", "method": "vision" }

Reply with exactly: "wrote vision-output-<id>.json"
```

Dispatch in waves of 8 parallel subagents (the same dispatch pattern used for the 49-PDF extraction).

- [ ] **Step 4.2.2: Verify all vision outputs exist**

```bash
ls data/byline-resolve/vision-output-*.json | wc -l
wc -l data/byline-resolve/needs-vision.txt
```

Both counts should match.

- [ ] **Step 4.2.3: Commit**

```bash
git add data/byline-resolve/vision-output-*.json data/byline-resolve/needs-vision.txt
git commit -m "data: Step 3 vision-pass outputs (~20 ambiguous PDFs read)"
```

---

**End of Chunk 4.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 5: Step 4 + Step 5 (applier + audit)

The applier merges all three output sources, creates stub thinkers, logs silent collisions, writes provenance. The audit emits two reports — an aggregate `coverage-report.md` and a flat actionable `curator-queue.md`.

### Task 5.1: `scripts/synthesis/apply-byline.py`

**Files:**
- Create: `scripts/synthesis/apply-byline.py`

- [ ] **Step 5.1.1: Write the script**

```python
#!/usr/bin/env python3
"""
Step 4 of the byline-resolution pipeline.

Walks data/byline-resolve/{deterministic-resolved.jsonl, llm-output-*.json,
vision-output-*.json}, merging per-entry. Process order: deterministic
first (most confident), then LLM, then vision — a higher-confidence pass
already locks in `authors[]` so later passes can't overwrite.

For each entry:
  - Matched authors → authors[] (or contributors[] with role for non-author roles)
  - Unknown names → auto-create stub thinker MD at apps/site/src/content/thinkers/<slug>.md
                   (or log collision if slug already exists)
  - Write authors_resolution object (confidence, method, proposed_unknowns,
    stubs_created, stubs_referenced, collisions_logged)
  - Set needs_review: true when confidence != high OR stubs/collisions occurred

Run:
    .venv-extract/bin/python3 scripts/synthesis/apply-byline.py
    .venv-extract/bin/python3 scripts/synthesis/apply-byline.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/apply-byline.py --test
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW_DIR = ROOT / "apps/site/src/content/primary-works"
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"
OUT_DIR = ROOT / "data/byline-resolve"
COLLISIONS_LOG = OUT_DIR / "collisions.log"
APPLY_LOG = OUT_DIR / "apply-log.txt"

VALID_ROLES = {"author", "editor", "translator", "foreword", "introduction", "preface"}
NON_AUTHOR_ROLES = {"editor", "translator", "foreword", "introduction", "preface"}
NEW_STUB_TRADITION = "unclassified"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def kebab(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


# YAML emit helpers ──────────────────────────────────────────────────────

def _yaml_str(s: str) -> str:
    if s is None:
        return '""'
    s = str(s)
    needs = any(c in s for c in ":#&*!|>'\"%@`{}[]\n\r\t") or (s and s[0] in "-?:") or s.endswith(" ")
    if needs:
        esc = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{esc}"'
    return s


def _emit_authors_block(slugs: list[str]) -> str:
    if not slugs:
        return "authors: []"
    lines = ["authors:"]
    for s in slugs:
        lines.append(f'  - {_yaml_str(s)}')
    return "\n".join(lines)


def _emit_contributors_block(items: list[dict]) -> str:
    if not items:
        return "contributors: []"
    lines = ["contributors:"]
    for it in items:
        lines.append(f'  - thinker: {_yaml_str(it["thinker"])}')
        lines.append(f'    role: {it["role"]}')
    return "\n".join(lines)


def _emit_resolution_block(res: dict) -> str:
    """Emit the authors_resolution block."""
    lines = ["authors_resolution:"]
    if res.get("confidence"):
        lines.append(f'  confidence: {res["confidence"]}')
    if res.get("method"):
        lines.append(f'  method: {res["method"]}')
    for key in ("proposed_unknowns", "stubs_created", "stubs_referenced", "collisions_logged"):
        vals = res.get(key) or []
        if not vals:
            lines.append(f"  {key}: []")
        else:
            lines.append(f"  {key}:")
            for v in vals:
                lines.append(f'    - {_yaml_str(v)}')
    return "\n".join(lines)


# Frontmatter mutation ─────────────────────────────────────────────────

def _replace_or_append_line(fm: str, key: str, value_line: str) -> str:
    rx = re.compile(rf"^{re.escape(key)}:[ \t]*\S.*$", re.M)
    if rx.search(fm):
        return rx.sub(value_line, fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + value_line + "\n"


def _replace_or_append_block(fm: str, key: str, new_block: str) -> str:
    rx = re.compile(
        rf"^{re.escape(key)}:(?:[ \t]*\n(?:[ \t]+.*\n?)*|[ \t]+.*\n?(?:[ \t]+.*\n?)*)",
        re.M,
    )
    if rx.search(fm):
        return rx.sub(new_block.rstrip() + "\n", fm, count=1)
    if not fm.endswith("\n"):
        fm += "\n"
    return fm + new_block.rstrip() + "\n"


# Stub creation ─────────────────────────────────────────────────────────

def stub_thinker_md(slug: str, canonical: str) -> str:
    today = datetime.date.today().isoformat()
    # Build a sort key: "Last, First" if invertible, else canonical
    parts = canonical.split()
    if len(parts) >= 2:
        sort = f"{parts[-1]}, {' '.join(parts[:-1])}"
    else:
        sort = canonical
    return f"""---
id: {slug}
name:
  canonical: {_yaml_str(canonical)}
  sort: {_yaml_str(sort)}
  also_known_as: []
tradition: {NEW_STUB_TRADITION}
nationality: india
themes: []
affiliations: []
bio_source: ai_drafted_stub
needs_review: true
draft: false
ai:
  drafted_by: claude-sonnet-4.6
  drafted_at: {today}
  model_version: byline-resolve-{today}
---
"""


def existing_thinker_canonical(slug: str) -> str | None:
    path = THINKERS_DIR / f"{slug}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    fm = m.group(1)
    cn = re.search(r"^\s+canonical:\s*[\"']?(.+?)[\"']?\s*$", fm, re.M)
    return cn.group(1).strip() if cn else None


# Per-entry applier ─────────────────────────────────────────────────────

def process_entry(
    entry_id: str,
    record: dict,
    run_stubs_created: set[str],
    dry_run: bool,
    log: list[str],
) -> str:
    md = PW_DIR / f"{entry_id}.md"
    if not md.exists():
        log.append(f"[{entry_id}] MD file missing — skipped")
        return "skip-no-md"
    text = md.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        log.append(f"[{entry_id}] no frontmatter — skipped")
        return "skip-no-fm"
    fm, body = m.group(1), m.group(2)

    # Authors / contributors routing
    authors: list[str] = []
    contributors: list[dict] = []
    for match in record.get("matches", []):
        slug = match.get("slug")
        role = match.get("role", "author")
        if not slug:
            continue
        if role in NON_AUTHOR_ROLES:
            contributors.append({"thinker": slug, "role": role})
        else:
            authors.append(slug)

    # Stub creation for unknowns
    stubs_created: list[str] = []
    stubs_referenced: list[str] = []
    collisions_logged: list[str] = []
    proposed_unknowns: list[str] = list(record.get("unknowns") or [])

    for name in proposed_unknowns:
        slug = kebab(name)
        if not slug:
            continue
        if slug in run_stubs_created:
            # Same-run earlier creation — silent reference
            authors.append(slug)
            stubs_referenced.append(slug)
            continue
        existing_canonical = existing_thinker_canonical(slug)
        if existing_canonical is not None:
            # Pre-existing thinker collision — link but log
            authors.append(slug)
            collisions_logged.append(slug)
            log.append(
                f"[{entry_id}] COLLISION: proposed unknown '{name}' → slug '{slug}' "
                f"already exists as '{existing_canonical}' (linking anyway per spec §3)"
            )
            if not dry_run:
                COLLISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
                with COLLISIONS_LOG.open("a", encoding="utf-8") as cl:
                    cl.write(
                        f"{datetime.datetime.utcnow().isoformat()}Z\t{entry_id}\t"
                        f"{name}\t{slug}\t{existing_canonical}\n"
                    )
            continue
        # Genuine new stub
        if not dry_run:
            stub_path = THINKERS_DIR / f"{slug}.md"
            stub_path.write_text(stub_thinker_md(slug, name), encoding="utf-8")
        authors.append(slug)
        run_stubs_created.add(slug)
        stubs_created.append(slug)

    # Deduplicate authors[] while preserving order
    authors = list(dict.fromkeys(authors))

    # Compose mutations
    if authors:
        fm = _replace_or_append_block(fm, "authors", _emit_authors_block(authors))
    if contributors:
        # Read existing contributors and append (don't overwrite TOC-driven contribs)
        # For v1: just write our additions; this is acceptable for unbylined entries
        # which by definition started with empty contributors.
        fm = _replace_or_append_block(fm, "contributors", _emit_contributors_block(contributors))

    confidence = record.get("confidence")
    method = record.get("method")
    resolution = {
        "confidence": confidence,
        "method": method,
        "proposed_unknowns": proposed_unknowns,
        "stubs_created": stubs_created,
        "stubs_referenced": stubs_referenced,
        "collisions_logged": collisions_logged,
    }
    fm = _replace_or_append_block(fm, "authors_resolution", _emit_resolution_block(resolution))

    # needs_review flag
    flag_review = (
        confidence != "high"
        or stubs_created
        or collisions_logged
        or not authors  # genuinely unresolved
    )
    fm = _replace_or_append_line(
        fm,
        "needs_review",
        f"needs_review: {'true' if flag_review else 'false'}",
    )

    new_text = f"---\n{fm.rstrip()}\n---\n{body if body.startswith(chr(10)) else chr(10) + body}"
    if dry_run:
        return "would-apply"
    md.write_text(new_text, encoding="utf-8")
    return "applied"


# Driver ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        _run_tests()
        return 0

    # Aggregate records by id, in process order
    records: dict[str, dict] = {}
    # Deterministic first
    det_path = OUT_DIR / "deterministic-resolved.jsonl"
    if det_path.exists():
        for line in det_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            records[rec["id"]] = {**rec}

    # LLM outputs (don't overwrite deterministic)
    for fp in sorted(OUT_DIR.glob("llm-output-*.json")):
        arr = json.loads(fp.read_text())
        for rec in arr:
            rid = rec.get("id")
            if not rid or rid in records:
                continue
            rec.setdefault("method", "llm")
            records[rid] = rec

    # Vision outputs (don't overwrite anything earlier)
    for fp in sorted(OUT_DIR.glob("vision-output-*.json")):
        rec = json.loads(fp.read_text())
        rid = rec.get("id")
        if not rid or rid in records:
            continue
        rec.setdefault("method", "vision")
        records[rid] = rec

    print(f"records to apply: {len(records)}")

    run_stubs: set[str] = set()
    log: list[str] = []
    summary: dict[str, int] = {}
    for entry_id, rec in records.items():
        result = process_entry(entry_id, rec, run_stubs, args.dry_run, log)
        summary[result] = summary.get(result, 0) + 1
    for k in sorted(summary):
        print(f"  {summary[k]:5d}  {k}")
    print(f"  stubs newly created: {len(run_stubs)}")
    APPLY_LOG.write_text("\n".join(log) + "\n" if log else "(no warnings)\n")
    print(f"  log: {APPLY_LOG.relative_to(ROOT)}")
    return 0


def _run_tests():
    import tempfile

    # kebab
    assert kebab("R. C. Cooper") == "r-c-cooper"
    assert kebab("Dhirajlal Maganlal") == "dhirajlal-maganlal"

    # stub_thinker_md shape
    stub = stub_thinker_md("dhirajlal-maganlal", "Dhirajlal Maganlal")
    assert 'id: dhirajlal-maganlal' in stub
    assert 'canonical: Dhirajlal Maganlal' in stub
    assert 'tradition: unclassified' in stub
    assert 'bio_source: ai_drafted_stub' in stub
    assert 'needs_review: true' in stub

    # YAML emit
    assert _emit_authors_block([]) == "authors: []"
    assert "  - a-d-shroff" in _emit_authors_block(["a-d-shroff"])
    assert "  - thinker: a-d-shroff" in _emit_contributors_block([{"thinker": "a-d-shroff", "role": "editor"}])
    assert "  - role: editor" not in _emit_contributors_block([{"thinker": "x", "role": "editor"}])  # role uses 4-space indent
    assert "    role: editor" in _emit_contributors_block([{"thinker": "x", "role": "editor"}])

    # process_entry happy path: matches + unknowns + needs_review flag
    sample_md = """---
id: "test-entry"
title:
  main: "Test Speech"
authors: []
contributors: []
needs_review: true
draft: false
---

Body content here.
"""
    rec = {
        "id": "test-entry",
        "matches": [{"slug": "a-d-shroff", "role": "author"}],
        "unknowns": ["New Unknown Person"],
        "confidence": "medium",
        "method": "llm",
    }
    log: list[str] = []
    global PW_DIR, THINKERS_DIR
    orig_pw, orig_th = PW_DIR, THINKERS_DIR
    with tempfile.TemporaryDirectory() as td:
        PW_DIR = Path(td) / "primary-works"
        THINKERS_DIR = Path(td) / "thinkers"
        PW_DIR.mkdir()
        THINKERS_DIR.mkdir()
        (PW_DIR / "test-entry.md").write_text(sample_md)
        try:
            result = process_entry("test-entry", rec, set(), False, log)
            assert result == "applied", result
            new = (PW_DIR / "test-entry.md").read_text()
            assert "- a-d-shroff" in new
            assert "- new-unknown-person" in new
            assert "authors_resolution:" in new
            assert "confidence: medium" in new
            assert "method: llm" in new
            assert "needs_review: true" in new  # stub_created or non-high → true
            # Stub thinker MD was created
            stub_path = THINKERS_DIR / "new-unknown-person.md"
            assert stub_path.exists()
            stub_text = stub_path.read_text()
            assert 'canonical: "New Unknown Person"' in stub_text or 'canonical: New Unknown Person' in stub_text
        finally:
            PW_DIR, THINKERS_DIR = orig_pw, orig_th

    # Editor / non-author role path: matches with role='editor' should land in
    # contributors[], not authors[]
    sample_md_b = """---
id: "edited-work"
title:
  main: "Test Edited Volume"
authors: []
contributors: []
needs_review: true
draft: false
---

Body.
"""
    rec_b = {
        "id": "edited-work",
        "matches": [
            {"slug": "a-d-shroff", "role": "editor"},
            {"slug": "minoo-shroff", "role": "translator"},
        ],
        "confidence": "high",
        "method": "llm",
    }
    log_b: list[str] = []
    orig_pw, orig_th = PW_DIR, THINKERS_DIR
    with tempfile.TemporaryDirectory() as td:
        PW_DIR = Path(td) / "primary-works"
        THINKERS_DIR = Path(td) / "thinkers"
        PW_DIR.mkdir()
        THINKERS_DIR.mkdir()
        (PW_DIR / "edited-work.md").write_text(sample_md_b)
        try:
            result_b = process_entry("edited-work", rec_b, set(), False, log_b)
            assert result_b == "applied", result_b
            new_b = (PW_DIR / "edited-work.md").read_text()
            # No authors[] populated (both matches were non-author roles)
            assert "authors: []" in new_b, "authors[] should be empty when only non-author roles match"
            # Both contributors present with correct roles
            assert "thinker: a-d-shroff" in new_b
            assert "role: editor" in new_b
            assert "thinker: minoo-shroff" in new_b
            assert "role: translator" in new_b
            # High confidence + no stubs + no collisions + no resolved authors → needs_review STILL true (no authors)
            assert "needs_review: true" in new_b
        finally:
            PW_DIR, THINKERS_DIR = orig_pw, orig_th

    print("apply-byline tests passed.")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5.1.2: Run inline tests**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-byline.py --test
```

Expected: `apply-byline tests passed.`

- [ ] **Step 5.1.3: Dry-run + inspect**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-byline.py --dry-run
head -30 data/byline-resolve/apply-log.txt
```

Look for surprising messages — large collision counts, missing MDs, etc. Stop and investigate before the real run if anything is wrong.

- [ ] **Step 5.1.4: Real run**

```bash
.venv-extract/bin/python3 scripts/synthesis/apply-byline.py
```

Expected: `applied: ~170-179`; `stubs newly created: ≤80`.

- [ ] **Step 5.1.5: Build verification**

Capture the pre-applier page count for the dynamic delta check:

```bash
cd apps/site && pnpm build 2>&1 | grep -oE "Indexed [0-9]+ pages" | head -1
```

Note the number. Then after the applier ran (which it did in 5.1.4), re-build:

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: build passes; total page count = pre-applier count + (stubs created in 5.1.4); no Zod errors. If errors mention `tradition`, the enum change in Chunk 1 didn't land — investigate.

- [ ] **Step 5.1.6: Spot-check 3 results**

```bash
for slug in $(shuf -n 3 -e $(ls apps/site/src/content/primary-works | head -200)); do
  echo "=== $slug ==="
  awk '/^---$/{f++} f<2' "apps/site/src/content/primary-works/$slug" | grep -E "^authors:|^  - |authors_resolution|needs_review" | head -10
  echo
done
```

Expected: each entry has `authors: [<slug>]`, an `authors_resolution` block with sensible fields, and `needs_review` set appropriately.

- [ ] **Step 5.1.7: Sanity-check gitignore coverage, then commit**

Before staging, verify none of the artefacts we're about to commit are silently dropped by a parent `.gitignore`:

```bash
git check-ignore -v data/byline-resolve/apply-log.txt data/byline-resolve/collisions.log 2>&1 | tail -5
```

Expected: no output (means not ignored). If anything IS ignored, decide whether to add `!data/byline-resolve/...` exceptions or accept the artefact loss.

```bash
git add scripts/synthesis/apply-byline.py apps/site/src/content/primary-works/*.md apps/site/src/content/thinkers/*.md data/byline-resolve/apply-log.txt data/byline-resolve/collisions.log 2>/dev/null || true
git commit -m "$(cat <<'EOF'
feat(synthesis): apply-byline.py + ~170 newly bylined primary-works + ≤80 stub thinkers

Step 4 of the byline-resolution pipeline. Merges deterministic / LLM /
vision outputs into primary-work frontmatter in confidence order so
later passes can't downgrade an earlier confident match. Creates stub
thinker MDs at apps/site/src/content/thinkers/<slug>.md for unknown
names, with bio_source: ai_drafted_stub and tradition: unclassified.

Same-run stub re-references are silent. Collisions with pre-existing
thinker slugs are linked (per spec §3 namesake-acceptance) but logged
to data/byline-resolve/collisions.log for curator audit.

authors_resolution provenance object written on every newly bylined
entry. needs_review: true when confidence != high OR a stub was
created OR a collision was logged OR no authors resolved at all.
EOF
)"
```

### Task 5.2: `scripts/synthesis/audit-byline-coverage.py`

**Files:**
- Create: `scripts/synthesis/audit-byline-coverage.py`

- [ ] **Step 5.2.1: Write the script**

```python
#!/usr/bin/env python3
"""
Step 5: emit data/byline-resolve/coverage-report.md and curator-queue.md.

coverage-report.md: aggregate counts (total bylined, method breakdown,
confidence breakdown, stub counts, collision counts).

curator-queue.md: flat actionable list of primary-works whose post-apply
state satisfies any of:
  - authors_resolution.method == 'vision'
  - confidence != 'high'
  - stubs_created non-empty
  - collisions_logged non-empty
  - no authors resolved (genuinely unresolved)

Run:
    .venv-extract/bin/python3 scripts/synthesis/audit-byline-coverage.py
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW_DIR = ROOT / "apps/site/src/content/primary-works"
OUT_REPORT = ROOT / "data/byline-resolve/coverage-report.md"
OUT_QUEUE = ROOT / "data/byline-resolve/curator-queue.md"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---", re.S)


def parse(md: Path) -> dict:
    text = md.read_text(encoding="utf-8")
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return {}
    fm = m.group(1)
    out: dict = {"id": md.stem}
    authors_m = re.search(r"^authors:\s*(\[\]|(?:\n\s+-\s+.+)+)", fm, re.M)
    out["has_authors"] = bool(authors_m and authors_m.group(1).strip() != "[]")
    res_m = re.search(r"^authors_resolution:\s*\n((?:\s+.+\n?)+)", fm, re.M)
    res_block = res_m.group(1) if res_m else ""
    out["confidence"] = (
        re.search(r"^\s+confidence:\s*(\S+)", res_block, re.M).group(1)
        if re.search(r"^\s+confidence:", res_block, re.M)
        else None
    )
    out["method"] = (
        re.search(r"^\s+method:\s*(\S+)", res_block, re.M).group(1)
        if re.search(r"^\s+method:", res_block, re.M)
        else None
    )
    out["stubs_created"] = bool(
        re.search(r"^\s+stubs_created:\s*\n\s+-", res_block, re.M)
    )
    out["collisions_logged"] = bool(
        re.search(r"^\s+collisions_logged:\s*\n\s+-", res_block, re.M)
    )
    out["needs_review"] = bool(re.search(r"^needs_review:\s*true", fm, re.M))
    return out


def main() -> int:
    entries = [parse(md) for md in sorted(PW_DIR.glob("*.md"))]
    total = len(entries)
    bylined = sum(1 for e in entries if e.get("has_authors"))
    by_method = Counter(e["method"] for e in entries if e.get("method"))
    by_confidence = Counter(e["confidence"] for e in entries if e.get("confidence"))
    stubs = sum(1 for e in entries if e.get("stubs_created"))
    collisions = sum(1 for e in entries if e.get("collisions_logged"))

    lines = [
        "# Byline Resolution Coverage Report",
        "",
        f"Total primary-works: {total}",
        f"With `authors[]` populated: {bylined}/{total} ({bylined*100//total}%)",
        "",
        "## Method breakdown (entries where a resolution ran)",
        "",
    ]
    for m, n in by_method.most_common():
        lines.append(f"- {m}: {n}")
    lines.extend(["", "## Confidence breakdown", ""])
    for c, n in by_confidence.most_common():
        lines.append(f"- {c}: {n}")
    lines.extend([
        "",
        f"## Stubs created (entries with new stub thinkers): {stubs}",
        f"## Collisions logged (silent existing-thinker hits): {collisions}",
        "",
    ])
    OUT_REPORT.write_text("\n".join(lines))
    print(f"wrote {OUT_REPORT.relative_to(ROOT)}")

    # Curator queue
    queue = [
        e for e in entries
        if e.get("method") == "vision"
        or (e.get("confidence") and e["confidence"] != "high")
        or e.get("stubs_created")
        or e.get("collisions_logged")
        or (e.get("method") and not e.get("has_authors"))
    ]
    q_lines = [
        "# Curator Review Queue (post-byline-resolution)",
        "",
        f"Total entries needing review: {len(queue)}",
        "",
        "| id | method | confidence | stubs | collisions |",
        "|---|---|---|---|---|",
    ]
    for e in queue:
        q_lines.append(
            f"| `{e['id']}` | {e.get('method') or ''} | {e.get('confidence') or ''} | "
            f"{'✓' if e.get('stubs_created') else ''} | "
            f"{'✓' if e.get('collisions_logged') else ''} |"
        )
    OUT_QUEUE.write_text("\n".join(q_lines) + "\n")
    print(f"wrote {OUT_QUEUE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5.2.2: Run + inspect**

```bash
.venv-extract/bin/python3 scripts/synthesis/audit-byline-coverage.py
cat data/byline-resolve/coverage-report.md
head -30 data/byline-resolve/curator-queue.md
```

Verify the coverage report matches the §7 acceptance metrics:
- Total bylined ≥97% (≥367 of 378)
- Stubs ≤80
- Collisions ≤5

If any metric is off, surface to the user before proceeding (a real outlier might mean a regex or matching bug upstream).

- [ ] **Step 5.2.3: Commit**

```bash
git add scripts/synthesis/audit-byline-coverage.py data/byline-resolve/coverage-report.md data/byline-resolve/curator-queue.md
git commit -m "feat(synthesis): audit-byline-coverage.py + initial reports

Aggregate coverage-report.md plus an actionable flat curator-queue.md
listing every entry where the curator should eyeball the result —
vision-source, medium/low confidence, stub-created, collision-logged,
or genuinely unresolved. Step 5 of the pipeline."
```

### Task 5.3: Final verification

- [ ] **Step 5.3.1: Final build + page-count sanity check**

```bash
cd apps/site && pnpm build 2>&1 | tail -3
```

Expected: build clean. Page count = 1,131 + (newly created stubs) — confirm by comparing to pre-Chunk-5 build.

- [ ] **Step 5.3.2: Sanity-check listing UI**

Open one or two primary-work pages that were previously unbylined, e.g.:

```bash
grep -oE '<p class="mt-1 text[^"]*">[^<]*</p>' apps/site/dist/primary-works/a-blueprint-for-eradication-of-poverty-dr-b-p-godrej-december-15-1980/index.html | head -2
```

Look for a byline rendered in the card / detail page. If the card still says "no author", the listing template doesn't read `authors[]` correctly (existing bug surfaced by this work, fix as follow-up).

- [ ] **Step 5.3.3: Plan complete — chunk 5 close**

No further commits. Mark plan complete.

---

**End of Chunk 5.** Dispatch the plan-document-reviewer subagent; once approved, the plan is complete and ready for execution.

---

## Reviewer dispatch template

For each chunk above, dispatch the plan-document-reviewer subagent with:

```
You are a plan document reviewer. Verify this chunk is complete and ready to execute.

**Chunk to review:** [paste chunk content]

**Spec reference:** /Users/siraj/Indian Liberals Website/docs/superpowers/specs/2026-05-19-primary-works-byline-resolution-design.md

## What to check
| Category | What to look for |
|---|---|
| Granularity | Each step is one 2-5 minute action |
| Completeness | No TODOs, no placeholders, no "implement X here" |
| Testability | Tests are real code, not pseudocode |
| Exactness | File paths absolute; commit messages drafted |
| Spec fidelity | Plan matches spec §X for the chunk's scope |

Return: Status (Approved | Issues Found), per-task verification, new issues introduced, recommendations.
```

Fix issues in-place; re-dispatch until approved.

---

## Plan complete

After all 5 chunks pass review:

1. Mark this todo item complete.
2. Hand off to **superpowers:subagent-driven-development** for execution. Fresh subagent per task, two-stage review.

The terminal state of this plan is a primary-works listing where ≥97% of cards carry a "By X" line, ~80 new stub thinker pages exist (with `needs_review: true`), and a `curator-queue.md` lists every entry needing human eyes for further bio expansion.
