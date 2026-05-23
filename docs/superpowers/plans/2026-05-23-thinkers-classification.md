# Thinkers Classification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three orthogonal classification axes to thinkers (`canon_status`, revised `tradition`, multi-valued `vocations`), redesign the `/thinkers` index as four canon-status sections with vocation captions + works/references affordances, and migrate the existing 506 entries to the new schema with safe defaults.

**Architecture:** Three independently-buildable commits. Schema accepts new values + old values together during the transition; mechanical Python migration script populates new fields + renames two enum values; the schema then tightens to drop the now-unused old values. UI rewrites the index page to use a build-time `thinker-stats.ts` helper that derives works/references counts from existing collection refs (no new stored counters).

**Tech Stack:** Astro 5 content collections, Zod, Tailwind 4 (`text-(--color-...)` utility forms already in the codebase), Python 3 for the migration script (matches `scripts/synthesis/` convention).

**Spec reference (read before starting):**
- [`docs/superpowers/specs/2026-05-23-thinkers-classification-design.md`](../specs/2026-05-23-thinkers-classification-design.md) — design + acceptance criteria, locked

**Pre-flight reading (in order, before Chunk 1):**
- `apps/site/src/content.config.ts` lines 43-90 — current thinker schema (tradition enum currently has 7 values)
- `apps/site/src/content.config.ts` lines 175-235 — opinions + interviews collection field shapes (used by §5.1 mapping in spec)
- `apps/site/src/content.config.ts` lines 236-463 — primary-works + periodicals field shapes
- `apps/site/src/content.config.ts` lines 464-497 — theprint-mirror (note: author_name is a string, not a thinker ref)
- `apps/site/src/pages/thinkers/index.astro` lines 1-100 — current flat-grid index page (will be fully rewritten in Chunk 3)
- `scripts/synthesis/apply-thinker-cleanup.py` — convention for repo-root Python scripts that touch thinker MDs

**Working directory:** the repo root `/Users/siraj/Indian Liberals Website` on `main`. All git operations target `main` unless otherwise noted.

**Verification harness:**
- Schema/build: `cd apps/site && pnpm build` (currently emits 1185 pages; should stay at 1185 post-plan since no routes added).

**Spec deviations logged here:** none expected. The spec is locked at commit `30bfaaf`.

---

## File Structure

**Created (new files):**

```
apps/site/src/lib/thinker-stats.ts                              # Chunk 3: build-time helper computing per-thinker {worksAuthored, referencedIn}
scripts/synthesis/apply-thinker-classification-migration.py     # Chunk 2: one-time mechanical migration
```

**Modified:**

```
apps/site/src/content.config.ts                                 # Chunk 1 + Chunk 2: schema additions, then schema tightening
apps/site/src/pages/thinkers/index.astro                        # Chunk 3: full rewrite (4 sections, vocation captions, works chips)
apps/site/src/content/thinkers/*.md                             # Chunk 2: 506 files touched (53 renames + 10 merges + 506 field additions)
```

**Deleted:** none.

---

## Chunk 1: Schema delta (additive only — all old values still accepted)

Goal: extend the schema to accept the new fields and the new enum values, without breaking any existing data. End state: build clean; new fields default to safe values on every existing thinker (canon_status: unclassified, vocations: []); old tradition values continue to validate.

### Task 1.1: Extend the `tradition` enum

**Files:**
- Modify: `apps/site/src/content.config.ts` (the `thinkers = defineCollection({...})` block, currently at lines 43-90; locate by anchor `tradition: z.enum(`)

- [ ] **Step 1.1.1: Read the current schema block**

```bash
sed -n '43,90p' apps/site/src/content.config.ts
```

Confirm the tradition enum currently lists exactly: `classical_liberal, reformer, nationalist_liberal, social_reformer, contemporary_liberal, international_influence, unclassified` (7 values). If different, locate by the anchor `tradition: z.enum(` and proceed against what's actually there.

- [ ] **Step 1.1.2: Add the four new enum values**

Find the `tradition: z.enum([...])` block and add four new values in this exact position (sorted alphabetically within the new additions). Keep all 7 existing values. New enum becomes 11 values:

```ts
tradition: z.enum([
  'classical_liberal',
  'constitutional_liberal',  // NEW — will absorb nationalist_liberal entries in Chunk 2
  'contemporary_liberal',
  'international_influence', // DEPRECATED but still accepted (sub-project 2 reclassifies)
  'libertarian',             // NEW
  'nationalist_liberal',     // DEPRECATED but still accepted in Chunk 1 (data still uses it; gets renamed in Chunk 2)
  'non_liberal',             // NEW
  'practice',                // NEW — for non-political figures (industrialists, scientists, etc.)
  'reformer',                // DEPRECATED but still accepted in Chunk 1 (data still uses it; merged into social_reformer in Chunk 2)
  'social_reformer',
  'unclassified',
]),
```

Order is purely cosmetic to Zod — alphabetical for readability. The COMMENTS marking deprecated values are important: they're the trail Chunk 2 follows to drop the right ones.

### Task 1.2: Add the new fields

**Files:**
- Modify: `apps/site/src/content.config.ts` (same `thinkers` block)

- [ ] **Step 1.2.1: Add `canon_status` field**

Insert immediately after the closing `])` of the tradition enum:

```ts
canon_status: z.enum([
  'core',         // Central to the classical-liberal / libertarian canon
  'extended',     // Broader liberal tradition (constitutional, contemporary, reform-era, honored practitioners)
  'referenced',   // Mentioned in the corpus but outside the liberal tradition
  'unclassified', // Default
]).default('unclassified'),
```

- [ ] **Step 1.2.2: Add `vocations` array field**

Insert immediately after `canon_status`:

```ts
vocations: z.array(z.enum([
  // Academic / theoretical
  'philosopher', 'economist', 'historian', 'political_scientist',
  'sociologist', 'legal_scholar', 'scientist', 'engineer', 'professor',
  // Writing / editorial
  'writer', 'editor', 'journalist', 'poet',
  // Public office / governance
  'statesman', 'parliamentarian', 'civil_servant', 'diplomat', 'judge',
  // Business / enterprise
  'industrialist', 'entrepreneur',
  // Civil society
  'activist', 'reformer', 'religious_figure',
  // Other
  'military_officer', 'artist',
])).default([]),
```

### Task 1.3: Verify build + negative test + commit

- [ ] **Step 1.3.1: Build to verify clean**

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: build completes; `Finished in <N> seconds`; no Zod errors. Page count should stay 1185.

- [ ] **Step 1.3.2: Negative test — invalid canon_status fails build**

Pick any thinker file and temporarily add a bogus canon_status. Don't pick a stub or a draft; use a non-draft real entry to maximise visibility. Use a **content-anchored** sed (NOT a line-number sed) so the injection lands at the top level of the frontmatter regardless of where the `tradition:` line happens to sit — line-number sed risks injecting inside the `name:` mapping which would break YAML parsing before Zod ever sees `canon_status`:

```bash
THINKER=apps/site/src/content/thinkers/dadabhai-naoroji.md
cp "$THINKER" "$THINKER.bak"
# Insert canon_status: bogus_value BEFORE the existing tradition: line.
# Both keys are top-level scalars in the frontmatter, so the injection
# is syntactically valid YAML — the failure surface is the Zod enum, not
# YAML structure.
sed -i '' 's/^tradition: /canon_status: bogus_value\
tradition: /' "$THINKER"
cd apps/site && pnpm build 2>&1 | grep -E "canon_status|bogus_value" | head -3
```

Expected: a Zod error referencing the file, the field `canon_status`, the value `bogus_value`, and the allowed enum values. Then revert from the .bak:

```bash
cd "/Users/siraj/Indian Liberals Website"
mv "$THINKER.bak" "$THINKER"
git status apps/site/src/content/thinkers/dadabhai-naoroji.md
# Expected: the file is not listed in git status output (unmodified).
cd apps/site && pnpm build 2>&1 | tail -3
```

Expected: clean build, `Finished in <N> seconds`. If `git status` shows the file as modified, the revert failed — investigate before continuing.

- [ ] **Step 1.3.3: Commit**

```bash
git add apps/site/src/content.config.ts
git commit -m "$(cat <<'EOF'
feat(schema): add canon_status + vocations + tradition.practice/libertarian/constitutional_liberal/non_liberal to thinker schema

primaryWorks-side schema already accepts both thinker and organisation
refs via the union from the org-authorship work. This commit extends
the thinker-side schema to support the three-axis classification model
specced in docs/superpowers/specs/2026-05-23-thinkers-classification-
design.md:

1. tradition enum gains four new values — libertarian,
   constitutional_liberal, non_liberal, practice. Existing 7 values
   stay accepted (including reformer + nationalist_liberal, which
   Chunk 2's data migration will retire after rewriting the 63 data
   files that use them; and international_influence, deprecated but
   accepted indefinitely until sub-project 2 reclassifies the 86
   entries).
2. canon_status enum (core / extended / referenced / unclassified),
   defaults to unclassified.
3. vocations multi-valued enum array (philosopher / economist /
   industrialist / judge / scientist / statesman / etc.), defaults [].

No data changes. Build is clean — every existing thinker has the new
fields populated via the .default() expressions. The actual data
migration (rename two enum values across 63 files; add the new
default fields to all 506) lands in Chunk 2.

Refs docs/superpowers/specs/2026-05-23-thinkers-classification-design.md §4
EOF
)"
```

---

**End of Chunk 1.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 2: Data migration + schema tightening

Goal: populate `canon_status: unclassified` + `vocations: []` on all 506 thinker MDs; rename `tradition: nationalist_liberal` → `constitutional_liberal` (53 entries) and `tradition: reformer` → `social_reformer` (10 entries); then tighten the schema to drop the two now-unused values. Single commit at the end (script + 506 data files + schema delta). End state: schema cleaner, no data uses the removed enum values, build clean.

### Task 2.1: Write the migration script

**Files:**
- Create: `scripts/synthesis/apply-thinker-classification-migration.py`

- [ ] **Step 2.1.1: Write the script with exact YAML serialization**

Create `scripts/synthesis/apply-thinker-classification-migration.py` with this content:

```python
#!/usr/bin/env python3
"""
Apply the thinker-classification migration:
  1. Add `canon_status: unclassified` to every thinker MD that doesn't have it
  2. Add `vocations: []` to every thinker MD that doesn't have it
  3. Rename `tradition: nationalist_liberal` → `tradition: constitutional_liberal`
  4. Merge `tradition: reformer` → `tradition: social_reformer`

Strict per-spec YAML serialization:
  - canon_status: unclassified   (no quoting, no comments, no trailing whitespace)
  - vocations: []                (flow-style empty array, NOT block-style)
These exact forms are what the §9.2 acceptance grep checks rely on.

Idempotent. Safe to re-run.

Run from the repo root:
    python3 scripts/synthesis/apply-thinker-classification-migration.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THINKERS_DIR = ROOT / "apps/site/src/content/thinkers"

# Compiled regexes once
TRADITION_LINE = re.compile(r'^(tradition:\s*)([a-z_]+)\s*$', re.MULTILINE)
CANON_STATUS_PRESENT = re.compile(r'^canon_status:\s*\S+', re.MULTILINE)
VOCATIONS_PRESENT = re.compile(r'^vocations:\s*', re.MULTILINE)


def migrate_one(text: str) -> tuple[str, dict]:
    """Apply the four migration steps to one file's content.
    Returns (new_text, stats_dict).
    """
    stats = {
        'added_canon_status': False,
        'added_vocations': False,
        'renamed_nationalist_liberal': False,
        'merged_reformer': False,
    }

    # Find the tradition line — anchor for inserting new fields right after it
    m = TRADITION_LINE.search(text)
    if not m:
        # No tradition line at all (unexpected for a real thinker MD); skip mutation
        return text, stats

    tradition_value = m.group(2)
    tradition_line_end = m.end()

    # Step 3 + 4: rewrite the tradition value if it matches
    if tradition_value == 'nationalist_liberal':
        text = text[:m.start(2)] + 'constitutional_liberal' + text[m.end(2):]
        stats['renamed_nationalist_liberal'] = True
        # Recompute the line end after substitution (different length)
        m = TRADITION_LINE.search(text)
        tradition_line_end = m.end()
    elif tradition_value == 'reformer':
        text = text[:m.start(2)] + 'social_reformer' + text[m.end(2):]
        stats['merged_reformer'] = True
        m = TRADITION_LINE.search(text)
        tradition_line_end = m.end()

    # Step 1: insert canon_status if absent (immediately after the tradition line)
    if not CANON_STATUS_PRESENT.search(text):
        # tradition_line_end points to the \n at the end of the tradition line
        # or to the position right after the value. We want to insert AFTER the \n.
        # The regex's group(0) ends just before \n; advance to include the \n.
        insertion_point = tradition_line_end
        if insertion_point < len(text) and text[insertion_point] == '\n':
            insertion_point += 1
        text = text[:insertion_point] + 'canon_status: unclassified\n' + text[insertion_point:]
        stats['added_canon_status'] = True

    # Step 2: insert vocations if absent (immediately after canon_status line)
    if not VOCATIONS_PRESENT.search(text):
        canon_m = CANON_STATUS_PRESENT.search(text)
        # canon_m must exist now since we either inserted it or it was already present
        if canon_m:
            # Find the end of the canon_status line
            line_end = text.find('\n', canon_m.end())
            if line_end == -1:
                line_end = len(text)
            else:
                line_end += 1  # include the \n
            text = text[:line_end] + 'vocations: []\n' + text[line_end:]
            stats['added_vocations'] = True

    return text, stats


def main() -> int:
    if not THINKERS_DIR.exists():
        print(f"ERROR: {THINKERS_DIR} does not exist; run from repo root.", file=sys.stderr)
        return 1

    files = sorted(THINKERS_DIR.glob('*.md'))
    if not files:
        print(f"ERROR: no MD files in {THINKERS_DIR}", file=sys.stderr)
        return 1

    totals = {
        'files_processed': 0,
        'files_modified': 0,
        'added_canon_status': 0,
        'added_vocations': 0,
        'renamed_nationalist_liberal': 0,
        'merged_reformer': 0,
    }

    for f in files:
        original = f.read_text(encoding='utf-8')
        new_text, stats = migrate_one(original)
        totals['files_processed'] += 1
        if new_text != original:
            f.write_text(new_text, encoding='utf-8')
            totals['files_modified'] += 1
        for k in ('added_canon_status', 'added_vocations',
                  'renamed_nationalist_liberal', 'merged_reformer'):
            if stats[k]:
                totals[k] += 1

    print(f"files_processed:           {totals['files_processed']}")
    print(f"files_modified:            {totals['files_modified']}")
    print(f"added_canon_status:        {totals['added_canon_status']}")
    print(f"added_vocations:           {totals['added_vocations']}")
    print(f"renamed_nationalist_liberal: {totals['renamed_nationalist_liberal']}")
    print(f"merged_reformer:           {totals['merged_reformer']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2.1.2: Make the script executable**

```bash
chmod +x scripts/synthesis/apply-thinker-classification-migration.py
```

### Task 2.2: Run the migration

- [ ] **Step 2.2.1: First run + single-file spot-check**

The script has no dry-run flag; this step runs the migration on the full corpus, then diffs ONE file against its pre-migration copy as a spot-check. (Full per-criterion verification follows in Step 2.2.2.) Pick one MD file that uses `nationalist_liberal` so the diff shows both the rename and the field insertions:

```bash
TEST_THINKER=$(grep -l "^tradition: nationalist_liberal$" apps/site/src/content/thinkers/*.md | head -1)
echo "Test target: $TEST_THINKER"
cp "$TEST_THINKER" /tmp/test-thinker-before.md
```

Run the script:

```bash
python3 scripts/synthesis/apply-thinker-classification-migration.py
```

Diff the one file to confirm shape:

```bash
diff /tmp/test-thinker-before.md "$TEST_THINKER"
```

Expected diff: `tradition: nationalist_liberal` → `tradition: constitutional_liberal`; two new lines `canon_status: unclassified` and `vocations: []` inserted immediately after the tradition line. Nothing else changed.

- [ ] **Step 2.2.2: Verify the script output matches §9.2 acceptance criteria**

```bash
echo "AC §9.2 #5: all 506 have canon_status: unclassified"
grep -c "^canon_status: unclassified$" apps/site/src/content/thinkers/*.md | awk -F: '{s+=$2} END {print s}'
# Expected: 506

echo "AC §9.2 #6: all 506 have vocations: []"
grep -c "^vocations: \[\]$" apps/site/src/content/thinkers/*.md | awk -F: '{s+=$2} END {print s}'
# Expected: 506

echo "AC §9.2 #7: zero remaining nationalist_liberal"
grep -c "^tradition: nationalist_liberal$" apps/site/src/content/thinkers/*.md | awk -F: '{s+=$2} END {print s}'
# Expected: 0

echo "AC §9.2 #8: zero remaining reformer"
grep -c "^tradition: reformer$" apps/site/src/content/thinkers/*.md | awk -F: '{s+=$2} END {print s}'
# Expected: 0

echo "AC §9.2 #9: international_influence count unchanged (~86)"
grep -c "^tradition: international_influence$" apps/site/src/content/thinkers/*.md | awk -F: '{s+=$2} END {print s}'
# Expected: 86 (same as pre-migration)

echo "Sanity: constitutional_liberal now contains old nationalist_liberal + any preexisting (should be 53)"
grep -c "^tradition: constitutional_liberal$" apps/site/src/content/thinkers/*.md | awk -F: '{s+=$2} END {print s}'
# Expected: 53

echo "Sanity: social_reformer absorbed old reformer (was 44 + 10 reformer = 54)"
grep -c "^tradition: social_reformer$" apps/site/src/content/thinkers/*.md | awk -F: '{s+=$2} END {print s}'
# Expected: 54
```

If any expected number is wrong, STOP and investigate. Do NOT proceed to schema tightening until all six checks pass.

- [ ] **Step 2.2.3: Idempotency check (script must be safe to re-run)**

```bash
python3 scripts/synthesis/apply-thinker-classification-migration.py
```

Expected output:
```
files_processed:           506
files_modified:            0   ← key invariant: re-run modifies zero files
added_canon_status:        0
added_vocations:           0
renamed_nationalist_liberal: 0
merged_reformer:           0
```

If `files_modified` is non-zero on a re-run, the script is not idempotent — STOP, fix, then redo Step 2.2.2.

### Task 2.3: Tighten the schema (drop the now-unused enum values)

- [ ] **Step 2.3.1: Edit content.config.ts**

In `apps/site/src/content.config.ts`, find the tradition enum (now 11 values after Chunk 1). Remove these two:

```ts
  'nationalist_liberal',     // DEPRECATED but still accepted in Chunk 1 (data still uses it; gets renamed in Chunk 2)
  'reformer',                // DEPRECATED but still accepted in Chunk 1 (data still uses it; merged into social_reformer in Chunk 2)
```

(Including their trailing comments.) Leave `international_influence` in place — it remains deprecated-but-accepted (sub-project 2 will retire it).

Final enum after this step (9 values):

```ts
tradition: z.enum([
  'classical_liberal',
  'constitutional_liberal',
  'contemporary_liberal',
  'international_influence', // DEPRECATED but still accepted (sub-project 2 reclassifies)
  'libertarian',
  'non_liberal',
  'practice',
  'social_reformer',
  'unclassified',
]),
```

- [ ] **Step 2.3.2: Verify the enum-shape change**

Before building, confirm the schema's `tradition` enum no longer contains the two retired values:

```bash
grep -E "'(nationalist_liberal|reformer)'" apps/site/src/content.config.ts
# Expected: empty (no matches)

grep -E "'(libertarian|constitutional_liberal|non_liberal|practice)'" apps/site/src/content.config.ts | wc -l | tr -d ' '
# Expected: 4 (each of the new values present exactly once)
```

If `nationalist_liberal` or `reformer` still appear, undo the wrong deletion and retry. If any of the 4 new values is missing, Chunk 1 wasn't completed correctly — STOP and re-investigate.

- [ ] **Step 2.3.3: Build to verify**

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: clean build, 1185 pages, no Zod errors. If a thinker still references `nationalist_liberal` or `reformer`, the script under Task 2.2 missed something — STOP and re-investigate; do not "fix forward" by re-adding the enum values.

### Task 2.4: Commit

- [ ] **Step 2.4.1: Inspect the diff scope**

```bash
git diff --stat | tail -15
```

Expected: 506 thinker MDs in `apps/site/src/content/thinkers/` (plus the new script + the schema change in `content.config.ts`). Many files have +2 / -0 (added canon_status + vocations); 63 files (53+10) also show a `tradition:` line change.

- [ ] **Step 2.4.2: Commit**

```bash
git add scripts/synthesis/apply-thinker-classification-migration.py \
        apps/site/src/content.config.ts \
        apps/site/src/content/thinkers/
git commit -m "$(cat <<'EOF'
feat(data): populate canon_status + vocations on all thinkers, retire two tradition values

One-time mechanical migration via scripts/synthesis/apply-thinker-
classification-migration.py:

1. Added `canon_status: unclassified` + `vocations: []` to all 506
   thinker MDs (exact YAML serialization per spec §7 — literal lines
   with no quoting, flow-style empty array). Default values; the
   actual classification work happens in sub-project 2 (AI bulk
   classifier) + curator review.

2. Renamed `tradition: nationalist_liberal` → `constitutional_liberal`
   (53 files). The original name conflated nationalism with
   constitutional liberalism; constitutional_liberal is the editorial
   contract for the Indian constitutional-liberal tradition (Naoroji,
   Gokhale, Sastri, Sapru, etc.).

3. Merged `tradition: reformer` → `social_reformer` (10 files). The
   two were near-duplicates; social_reformer is the kept name.

4. Tightened the schema in content.config.ts to drop the two retired
   values from the enum. international_influence stays as a deprecated
   accepted value — sub-project 2 will retire it after reclassifying
   the 86 entries that still use it.

Build clean; page count unchanged (1185). Migration script is
idempotent — re-running produces zero file modifications.

Refs docs/superpowers/specs/2026-05-23-thinkers-classification-design.md §7
EOF
)"
```

---

**End of Chunk 2.** Dispatch the plan-document-reviewer subagent for this chunk before proceeding.

---

## Chunk 3: UI rewrite — helper + redesigned thinkers index

Goal: add the build-time `thinker-stats.ts` helper that computes per-thinker work/reference counts from the live corpus, and rewrite `apps/site/src/pages/thinkers/index.astro` to render the four canon-status sections with vocation captions and works/references affordances. Day-1 state: only the "Awaiting classification" section renders (everyone is unclassified). Verify day-N rendering by temporarily seeding 4 classifications, building, spot-checking, and reverting. Single commit.

### Task 3.1: Write the `thinker-stats.ts` helper

**Files:**
- Create: `apps/site/src/lib/thinker-stats.ts`

- [ ] **Step 3.1.1: Confirm interview collection's available thinker-ref fields**

The spec §5.1 table lists `interviews` row's `referencedIn` source as `subject + (any other thinker-ref fields on the schema)`. From the actual schema at `apps/site/src/content.config.ts:215-235`, the only thinker-ref field on interviews is `subject` (singular optional ref); there is no `related_thinkers` or `thinker_mentions` on interviews. Pin this when writing the helper.

```bash
sed -n '215,235p' apps/site/src/content.config.ts
```

Confirm: only `subject: reference('thinkers').optional()` and `subject_name: z.string()`. The `interviewer` field is a plain string.

- [ ] **Step 3.1.2: Write the helper**

Create `apps/site/src/lib/thinker-stats.ts` with exactly this content:

```ts
// Build-time helper: computes per-thinker {worksAuthored, referencedIn}
// counts by iterating the relevant content collections.
//
// Per spec §5.1 mapping table:
//   primary-works:  worksAuthored ← authors[] (thinker-refs only; org-refs excluded)
//                   referencedIn  ← contributors[].thinker + thinker_mentions[].thinker
//                                   + related_thinkers[]
//   opinions:       worksAuthored ← author
//                   referencedIn  ← subject + thinker_mentions[].thinker
//                                   + related_thinkers[]
//   interviews:     worksAuthored ← (none — interviewee is not author)
//                   referencedIn  ← subject (the only thinker-ref field on schema)
//   musings:        worksAuthored ← author
//                   referencedIn  ← thinker_mentions[].thinker + related_thinkers[]
//   theprint-mirror: worksAuthored ← (none — author_name is a free-text string)
//                   referencedIn  ← thinker_mentions[].thinker + related_thinkers[]
//   periodicals:    worksAuthored ← toc[].author_resolved (one count per TOC entry)
//                   referencedIn  ← related_thinkers[] + thinker_mentions[].thinker
//                                   + toc[].cross_thinker_mentions[].thinker_resolved
//
// Within-entry dedup: if a thinker appears in both authored AND referenced
// fields of the same entry, count as worksAuthored only.
//
// Contract: returned Map contains an entry iff the thinker has at least
// one non-zero count. Page-render code must use:
//   stats.get(id) ?? { worksAuthored: 0, referencedIn: 0 }
//
// See docs/superpowers/specs/2026-05-23-thinkers-classification-design.md §5.

import { getCollection } from "astro:content";

export interface ThinkerStat {
  worksAuthored: number;
  referencedIn: number;
}

type RefLike = { id: string; collection?: string } | string | undefined | null;

function refToId(ref: RefLike): string | null {
  if (!ref) return null;
  if (typeof ref === "string") return ref;
  // Filter to thinker refs only (org-refs from the primary-works authors[]
  // union are excluded).
  if (ref.collection && ref.collection !== "thinkers") return null;
  return ref.id ?? null;
}

export async function getThinkerStats(): Promise<Map<string, ThinkerStat>> {
  const stats = new Map<string, ThinkerStat>();

  const bump = (id: string, key: keyof ThinkerStat) => {
    const cur = stats.get(id) ?? { worksAuthored: 0, referencedIn: 0 };
    cur[key] += 1;
    stats.set(id, cur);
  };

  const applyEntry = (authored: Set<string>, referenced: Set<string>) => {
    // Within-entry dedup: authored wins
    for (const id of authored) referenced.delete(id);
    for (const id of authored) bump(id, "worksAuthored");
    for (const id of referenced) bump(id, "referencedIn");
  };

  // primary-works
  const primaryWorks = await getCollection("primary-works");
  for (const w of primaryWorks) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    for (const a of w.data.authors ?? []) {
      const id = refToId(a as RefLike);
      if (id) authored.add(id);
    }
    for (const c of w.data.contributors ?? []) {
      const id = refToId(c.thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const m of w.data.thinker_mentions ?? []) {
      const id = refToId((m as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of w.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(authored, referenced);
  }

  // opinions
  const opinions = await getCollection("opinions");
  for (const o of opinions) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    const authorId = refToId(o.data.author as RefLike);
    if (authorId) authored.add(authorId);
    const subjectId = refToId(o.data.subject as RefLike);
    if (subjectId) referenced.add(subjectId);
    for (const m of o.data.thinker_mentions ?? []) {
      const id = refToId((m as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of o.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(authored, referenced);
  }

  // interviews — only `subject` is a thinker ref
  const interviews = await getCollection("interviews");
  for (const v of interviews) {
    const referenced = new Set<string>();
    const subjectId = refToId(v.data.subject as RefLike);
    if (subjectId) referenced.add(subjectId);
    applyEntry(new Set(), referenced);
  }

  // musings
  const musings = await getCollection("musings");
  for (const m of musings) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    const authorId = refToId(m.data.author as RefLike);
    if (authorId) authored.add(authorId);
    for (const mn of m.data.thinker_mentions ?? []) {
      const id = refToId((mn as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of m.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(authored, referenced);
  }

  // theprint-mirror — no author ref, only mentions
  const tpm = await getCollection("theprint-mirror");
  for (const p of tpm) {
    const referenced = new Set<string>();
    for (const mn of p.data.thinker_mentions ?? []) {
      const id = refToId((mn as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of p.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(new Set(), referenced);
  }

  // periodicals — may be empty today; helper still iterates
  const periodicals = await getCollection("periodicals");
  for (const p of periodicals) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    for (const r of p.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    for (const mn of p.data.thinker_mentions ?? []) {
      const id = refToId((mn as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const tocEntry of (p.data as any).toc ?? []) {
      const aid = refToId(tocEntry.author_resolved as RefLike);
      if (aid) authored.add(aid);
      for (const ctm of tocEntry.cross_thinker_mentions ?? []) {
        const id = refToId(ctm.thinker_resolved as RefLike);
        if (id) referenced.add(id);
      }
    }
    applyEntry(authored, referenced);
  }

  return stats;
}
```

- [ ] **Step 3.1.3: Spot-check the helper against a known thinker (inline)**

The cleanest spot-check is to add a temporary `console.log` inside the rewritten index page (Task 3.2) and inspect the build output. Defer to Step 3.3.1 below.

### Task 3.2: Rewrite `apps/site/src/pages/thinkers/index.astro`

**Files:**
- Modify: `apps/site/src/pages/thinkers/index.astro` (full rewrite)

- [ ] **Step 3.2.1: Read the current file end-to-end**

```bash
cat apps/site/src/pages/thinkers/index.astro
```

Note the existing `treatmentFor` helper (portrait fallback logic) and the BaseLayout import. Both stay; only the body's filter + grid logic changes.

- [ ] **Step 3.2.2: Write the new index page**

Replace the entire file content with:

```astro
---
import BaseLayout from "~/layouts/BaseLayout.astro";
import { getCollection } from "astro:content";
import { getThinkerStats, type ThinkerStat } from "~/lib/thinker-stats";

// Hide thinkers with zero inbound reference material (`draft: true` is set
// by /tmp/auto_hide_orphans.py when nothing in the corpus references the
// slug). Re-run that script after content changes to update visibility.
const allThinkers = (await getCollection("thinkers", (t) => !t.data.draft && t.data.language === "en")).sort(
  (a, b) => a.data.name.sort.localeCompare(b.data.name.sort),
);

const stats = await getThinkerStats();

const treatmentFor = (t: typeof allThinkers[number]) => {
  if (t.data.portrait?.caricature) return { src: t.data.portrait.caricature, kind: "caricature" } as const;
  if (t.data.portrait?.ring_portrait) return { src: t.data.portrait.ring_portrait, kind: "ring" } as const;
  if (t.data.portrait?.photo) return { src: t.data.portrait.photo, kind: "photo" } as const;
  return null;
};

// Sentence-case a vocation enum value: "legal_scholar" → "Legal scholar"
const prettifyVocation = (v: string): string => {
  const spaced = v.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

type CanonStatus = "core" | "extended" | "referenced" | "unclassified";

const sections: { id: CanonStatus; title: string; blurb: string; isAwaiting: boolean }[] = [
  {
    id: "core",
    title: "Liberal canon",
    blurb:
      "Central figures in the story this site tells: thinkers whose ideas, governance, scholarship, or enterprise form the foundation of the case for individual liberty, free enterprise, and constitutional governance in modern India.",
    isAwaiting: false,
  },
  {
    id: "extended",
    title: "Extended liberal tradition",
    blurb:
      "The broader cast in the liberal story: thinkers, statesmen, scholars, and figures of practice whose work belongs here without being at the very centre. Includes constitutional liberals, contemporary commentators, reform-era thinkers, and practitioners whom the liberal tradition honors — scientists, jurists, industrialists whose work has shaped the Indian liberal imagination.",
    isAwaiting: false,
  },
  {
    id: "referenced",
    title: "Referenced thinkers",
    blurb:
      "Thinkers and figures from outside the liberal tradition whose work appears in the corpus — through citation, critique, or admiration. Their presence reflects their role in liberal writing, not editorial endorsement.",
    isAwaiting: false,
  },
  {
    id: "unclassified",
    title: "Awaiting classification",
    blurb:
      "Classification pass in progress — these thinkers will move into the sections above as curator review completes.",
    isAwaiting: true,
  },
];

// Stat line (computed from all-thinkers + stats)
const totalCount = allThinkers.length;
const withWorksCount = allThinkers.filter((t) => (stats.get(t.id)?.worksAuthored ?? 0) > 0).length;
const referencedCount = allThinkers.filter((t) => (stats.get(t.id)?.referencedIn ?? 0) > 0).length;
const statLine = `${totalCount} thinkers · ${withWorksCount} with works in the archive · ${referencedCount} referenced in other works`;
---

<BaseLayout
  title="Thinkers — Indian Liberals"
  description="Biographical profiles of figures in the Indian liberal tradition, from Raja Ram Mohan Roy through the Swatantra-era classical liberals to contemporary commentators."
>
  <section class="border-b border-(--color-border)">
    <div class="mx-auto max-w-6xl px-6 py-12 md:py-16">
      <p class="text-xs uppercase tracking-widest text-(--color-saffron-700) font-(family-name:--font-ui) font-semibold mb-3">
        Thinkers
      </p>
      <h1 class="text-(--color-fg) mb-4">Figures in the Indian liberal tradition</h1>
      <p class="text-(--color-fg-muted) leading-relaxed max-w-prose">
        Biographies, bibliographies, and cross-links between the people who shaped the case for individual liberty, free enterprise, and constitutional governance in modern India.
      </p>
      <p class="text-(--color-fg-muted) text-sm mt-4 font-(family-name:--font-ui)">
        {statLine}
      </p>
    </div>
  </section>

  {sections.map((section) => {
    const sectionThinkers = allThinkers.filter((t) => t.data.canon_status === section.id);
    if (sectionThinkers.length === 0) return null;
    const headingId = `${section.id}-heading`;

    return (
      <section aria-labelledby={headingId} class="border-b border-(--color-border) last:border-b-0">
        <div class="mx-auto max-w-6xl px-6 py-12">
          <h2 id={headingId} class="text-(--color-fg) text-2xl md:text-3xl font-(family-name:--font-display) mb-3">
            {section.title}
          </h2>
          <p class={section.isAwaiting
            ? "text-(--color-fg-muted) text-sm mb-8 font-(family-name:--font-ui) italic max-w-prose"
            : "text-(--color-fg-muted) leading-relaxed mb-8 max-w-prose"
          }>
            {section.blurb}
          </p>
          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-10">
            {sectionThinkers.map((t) => {
              const treatment = treatmentFor(t);
              const tStat: ThinkerStat = stats.get(t.id) ?? { worksAuthored: 0, referencedIn: 0 };
              const vocationCaption = (t.data.vocations ?? []).map(prettifyVocation).join(" · ");
              const worksText = tStat.worksAuthored === 1 ? "1 work on this site" : `${tStat.worksAuthored} works on this site`;
              const referencedText = tStat.referencedIn === 1 ? "Referenced in 1 piece" : `Referenced in ${tStat.referencedIn} pieces`;
              const pagefindVocations = (t.data.vocations ?? []).map((v) => `vocation:${v}`).join(",");

              return (
                <a
                  href={`/thinkers/${t.id}/`}
                  class="group block no-underline"
                  data-pagefind-filter={`canon-status:${t.data.canon_status}${pagefindVocations ? "," + pagefindVocations : ""}`}
                >
                  <div class="aspect-[3/4] bg-(--color-bg-muted) border border-(--color-border) rounded-sm overflow-hidden flex items-end justify-center transition-shadow group-hover:shadow-md">
                    {treatment ? (
                      <img
                        src={treatment.src}
                        alt=""
                        width="240"
                        height="320"
                        loading="lazy"
                        class={treatment.kind === "ring"
                          ? "w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
                          : "w-full h-full object-contain object-bottom group-hover:scale-[1.02] transition-transform duration-300"
                        }
                      />
                    ) : (
                      <span class="text-(--color-fg-muted) text-4xl font-(family-name:--font-display) opacity-30">
                        {t.data.name.canonical.charAt(0)}
                      </span>
                    )}
                  </div>
                  <p class="mt-3 text-(--color-fg) font-(family-name:--font-ui) text-sm font-semibold leading-tight">
                    {t.data.name.canonical}
                  </p>
                  {vocationCaption && (
                    <p class="mt-1 text-xs text-(--color-fg-muted) font-(family-name:--font-ui)">
                      {vocationCaption}
                    </p>
                  )}
                  {(tStat.worksAuthored > 0 || tStat.referencedIn > 0) && (
                    <p class="mt-1.5 flex items-center gap-1.5 flex-wrap">
                      {tStat.worksAuthored > 0 && (
                        <span class="inline-block px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-(family-name:--font-ui) font-semibold bg-(--color-forest-100) text-(--color-forest-700)">
                          {worksText}
                        </span>
                      )}
                      {tStat.referencedIn > 0 && (
                        <span class="text-xs text-(--color-fg-muted) font-(family-name:--font-ui)">
                          {tStat.worksAuthored > 0 ? "· " : ""}{referencedText}
                        </span>
                      )}
                    </p>
                  )}
                </a>
              );
            })}
          </div>
        </div>
      </section>
    );
  })}
</BaseLayout>
```

Notes on the rewrite:
- The pre-existing `treatmentFor` portrait helper logic is preserved verbatim.
- The pre-existing initial-letter fallback (when no portrait exists) is preserved.
- The new `prettifyVocation` helper does the `legal_scholar` → `Legal scholar` mapping per spec §6.3.
- Empty-section rule: `if (sectionThinkers.length === 0) return null;` — header / blurb / grid all omitted from rendered HTML.
- The separator-rule between works chip and referenced label: when both render, the referenced label prefixes itself with `· `; when only referenced renders, no `· ` prefix (per spec §6.3 trailing rule).
- Pagefind filter attributes carry both `canon-status:<value>` and `vocation:<value>` per spec §6.6.

### Task 3.3: Build + day-1 acceptance

- [ ] **Step 3.3.1: Build**

```bash
cd apps/site && pnpm build 2>&1 | tail -5
```

Expected: clean build, page count line `Indexed 1185 pages` (per spec §9.6 #26).

- [ ] **Step 3.3.2: Verify §9.3 #12 — only Awaiting section renders on day 1**

```bash
grep -c "Liberal canon" apps/site/dist/thinkers/index.html
# Expected: 0

grep -c "Extended liberal tradition" apps/site/dist/thinkers/index.html
# Expected: 0

grep -c "Referenced thinkers" apps/site/dist/thinkers/index.html
# Expected: 0

grep -c "Awaiting classification" apps/site/dist/thinkers/index.html
# Expected: 1
```

If any expected number is wrong, STOP — empty-section rule is broken.

- [ ] **Step 3.3.3: Verify §9.3 #13 — same set of thinkers as pre-change**

```bash
grep -oE 'href="/thinkers/[^"]+/"' apps/site/dist/thinkers/index.html | sort -u | wc -l
# Expected: 328 (the count of non-draft, language=en thinkers)
```

- [ ] **Step 3.3.4: Verify §9.3 #14 — no vocation captions on day 1**

```bash
grep -c "Philosopher · Economist" apps/site/dist/thinkers/index.html
# Expected: 0
```

- [ ] **Step 3.3.5: Verify §9.3 #15 — works chip renders for thinkers with works**

`dadabhai-naoroji` is known to have authored primary-works content (he's referenced as the subject of a profile). Pick a thinker the helper marks as having `worksAuthored > 0`:

```bash
# Find a thinker with works (worksAuthored count surfaces as the "N work(s) on this site" pill)
grep -B5 "works on this site" apps/site/dist/thinkers/index.html | grep -oE 'href="/thinkers/[^"]+/"' | head -5
```

Expected: a non-empty list. Spot-check any one — e.g., open the card markup for that thinker:

```bash
SLUG=$(grep -B5 "works on this site" apps/site/dist/thinkers/index.html | grep -oE 'href="/thinkers/[^"]+/"' | head -1 | sed 's|href="/thinkers/\(.*\)/"|\1|')
grep -B2 -A4 "href=\"/thinkers/$SLUG/\"" apps/site/dist/thinkers/index.html | head -10
```

Confirm the card markup contains `bg-(--color-forest-100) text-(--color-forest-700)` (the forest-tint chip class) and the chip text matches `N work(s) on this site`.

- [ ] **Step 3.3.6: Verify §9.3 #16 — referenced label renders for thinkers with mentions**

```bash
grep -c "Referenced in" apps/site/dist/thinkers/index.html
# Expected: > 0 (any positive number; many thinkers will have mention counts)
```

### Task 3.4: Day-N simulation (temporary, reverted before commit)

The simulation proves the section structure works when classifications exist. Per spec §9.4, we seed 4 thinkers, rebuild, verify, then revert.

- [ ] **Step 3.4.1: Pick 4 representative thinkers (verify slugs exist)**

```bash
ls apps/site/src/content/thinkers/ | grep -iE "hayek|naoroji|tata|nehru" | head -10
```

If `f-a-hayek.md` doesn't exist, pick any classical_liberal-tagged thinker as the substitute. Similarly for the other three. Record the actual slugs you choose:

| Role | Expected slug | If missing, substitute |
|---|---|---|
| Core, classical liberal | `f-a-hayek` | any thinker with `tradition: classical_liberal` |
| Core, constitutional liberal | `dadabhai-naoroji` | any with `tradition: constitutional_liberal` |
| Extended, practice (industrialist) | `j-r-d-tata` or `jrd-tata` | any non-political figure (search by tradition or name) |
| Referenced, non_liberal | `jawaharlal-nehru` | any thinker not in the liberal canon |

- [ ] **Step 3.4.2: Apply the temporary classifications (sed edits)**

For each of the 4 picked thinkers, edit `canon_status` + `tradition` + `vocations` in their MD. Use sed or your editor of choice; the values to seed are:

| Slug | canon_status | tradition | vocations |
|---|---|---|---|
| (Hayek-like) | `core` | `classical_liberal` | `[philosopher, economist, professor]` |
| (Naoroji-like) | `core` | `constitutional_liberal` | `[statesman, economist, writer]` |
| (Tata-like) | `extended` | `practice` | `[industrialist]` |
| (Nehru-like) | `referenced` | `non_liberal` | `[statesman, writer]` |

For multi-valued vocations, the YAML can be flow-form on a single line: `vocations: [philosopher, economist, professor]`. The schema accepts both flow and block forms.

Capture which 4 slugs you edited as a bash array — required for the revert in Step 3.4.5:

```bash
# Replace the four slugs with the actual ones you picked in Step 3.4.1
SEED_FILES=(
  apps/site/src/content/thinkers/<hayek-like-slug>.md
  apps/site/src/content/thinkers/<naoroji-like-slug>.md
  apps/site/src/content/thinkers/<tata-like-slug>.md
  apps/site/src/content/thinkers/<nehru-like-slug>.md
)
# Sanity-check the array was populated
echo "${SEED_FILES[@]}"
ls "${SEED_FILES[@]}" >/dev/null  # exits non-zero if any path is missing
```

- [ ] **Step 3.4.3: Rebuild + verify §9.4 #19 sections render**

```bash
cd apps/site && pnpm build 2>&1 | tail -3

# Liberal canon section now renders
grep "Liberal canon" apps/site/dist/thinkers/index.html | head -1
# Expected: non-empty match

# Extended section renders
grep "Extended liberal tradition" apps/site/dist/thinkers/index.html | head -1
# Expected: non-empty match

# Referenced section renders
grep "Referenced thinkers" apps/site/dist/thinkers/index.html | head -1
# Expected: non-empty match

# Awaiting section still renders (most thinkers still unclassified)
grep "Awaiting classification" apps/site/dist/thinkers/index.html | head -1
# Expected: non-empty match
```

- [ ] **Step 3.4.4: Verify §9.4 #20 — vocation captions render**

```bash
# Hayek-like in Liberal canon section should show Philosopher · Economist · Professor
grep -A2 "Liberal canon" apps/site/dist/thinkers/index.html | grep -oE "Philosopher · Economist · Professor" | head -1
# Expected: a match (or substitute equivalent if Hayek slug isn't real)
```

- [ ] **Step 3.4.5: Revert the seed edits**

```bash
# git restore the 4 edited files
git checkout -- "${SEED_FILES[@]}"

# Confirm clean
git status
# Expected: only the new files from Chunks 2 + 3 should be modified — none of the 4 seed files
```

- [ ] **Step 3.4.6: Rebuild to confirm return to day-1 state**

```bash
cd apps/site && pnpm build 2>&1 | tail -3

grep -c "Awaiting classification" apps/site/dist/thinkers/index.html
# Expected: 1 (just the Awaiting section)

grep -c "Liberal canon" apps/site/dist/thinkers/index.html
# Expected: 0 (empty-section rule kicks in again)
```

### Task 3.5: Regression checks (per spec §9.6)

- [ ] **Step 3.5.1: PUCL Gujarat saffron pill still renders (org-authorship regression)**

```bash
grep -o "PUCL Gujarat</a><span[^>]*organisation</span>" apps/site/dist/gu/primary-works/khoj-march-april-2005/index.html | head -1
```

Expected: a match (the closing `</a>` of the link immediately followed by the `<span>` of the pill). If this returns empty, Chunk 3's helper changes have inadvertently broken something — investigate.

- [ ] **Step 3.5.2: PUCL Gujarat detail page renders**

```bash
ls apps/site/dist/organisations/pucl-gujarat/index.html
```

Expected: exists.

- [ ] **Step 3.5.3: Thinker detail pages render unchanged**

```bash
# Pick any classified thinker and confirm their detail page renders
ls apps/site/dist/thinkers/dadabhai-naoroji/index.html
```

Expected: exists. (Spec §9.6 #25 — the new fields are in frontmatter but not surfaced on the detail page; this is intentional.)

- [ ] **Step 3.5.4: Page count unchanged**

```bash
cd apps/site && pnpm build 2>&1 | grep -E "Indexed.*pages"
```

Expected: `Indexed 1185 pages`. If the count drifts, the new sections might be unexpectedly emitting extra pages — investigate.

### Task 3.6: Commit

- [ ] **Step 3.6.1: Inspect the diff**

```bash
git diff --stat
```

Expected: exactly two files modified:
- `apps/site/src/lib/thinker-stats.ts` — new file (~150 lines)
- `apps/site/src/pages/thinkers/index.astro` — fully rewritten (~150 lines)

- [ ] **Step 3.6.2: Commit**

```bash
git add apps/site/src/lib/thinker-stats.ts apps/site/src/pages/thinkers/index.astro
git commit -m "$(cat <<'EOF'
feat(ui): redesign /thinkers with canon-status sections + vocation captions + works/refs chips

Rewrites the flat alphabetical photo grid into four canon-status sections
(Liberal canon / Extended liberal tradition / Referenced thinkers /
Awaiting classification), with empty-section omission so the day-1
state — everyone is unclassified — only renders the Awaiting section.

Cards now carry three additions below the name:
1. Vocation caption (Philosopher · Economist · Professor), rendered
   when the thinker has any vocations set. Sentence-cased from enum
   value via simple underscore→space + capitalize.
2. Forest-tint "N works on this site" chip when worksAuthored > 0.
3. Muted "Referenced in N pieces" label when referencedIn > 0. When
   both render, the referenced label prefixes with "· " as separator.

The new apps/site/src/lib/thinker-stats.ts helper derives both counts
from existing collection refs per spec §5.1 mapping — no new stored
fields. Within-entry dedup: if a thinker appears in both authored AND
referenced fields of the same entry, count as worksAuthored only.

Pagefind facet attributes added — `canon-status:` and `vocation:` are
now queryable in the search index for future UI work.

The pre-existing portrait fallback logic (treatmentFor + initial-letter
placeholder) is preserved verbatim. auto_hide_orphans.py's draft:true
machinery is unchanged.

Refs docs/superpowers/specs/2026-05-23-thinkers-classification-design.md §5, §6
EOF
)"
```

- [ ] **Step 3.6.3: Confirm clean working tree**

```bash
git status
```

Expected: only `.claude/` untracked. No modified files.

---

**End of Chunk 3.** Dispatch the plan-document-reviewer subagent for this chunk; once approved, the plan is complete and ready for human push to origin.

---

## Reviewer dispatch template

For each chunk above, dispatch the plan-document-reviewer subagent with:

```
You are a plan document reviewer. Verify this chunk is complete and ready to execute.

**Chunk to review:** [paste chunk content]

**Spec reference:** /Users/siraj/Indian Liberals Website/docs/superpowers/specs/2026-05-23-thinkers-classification-design.md

## What to check
| Category | What to look for |
|---|---|
| Granularity | Each step is one 2-5 minute action |
| Completeness | No TODOs, no placeholders, no "implement X here" |
| Testability | Acceptance commands have real grep/ls patterns with expected output |
| Exactness | File paths absolute; commit messages drafted |
| Spec fidelity | Plan matches spec §X for the chunk's scope |

Return: Status (Approved | Issues Found), per-task verification, new issues introduced, recommendations.
```

Fix issues in-place; re-dispatch until approved.

---

## Plan complete

After all 3 chunks pass review:

1. Mark this todo item complete.
2. Hand off to **superpowers:subagent-driven-development** for execution. Fresh subagent per task, two-stage review (spec compliance + code quality).

The terminal state of this plan is:
- Schema with three orthogonal classification axes, accepting `tradition: practice` and the three other new values.
- 506 thinker MDs migrated to the new shape (canon_status + vocations populated with safe defaults; two old tradition values retired in favour of their replacements).
- `/thinkers` index redesigned into four canon-status sections with vocation captions + works/references affordances on each card.
- Day-1 visual state: only the "Awaiting classification" section renders (same set of thinkers as today's flat grid, just in a labeled container).
- Day-N visual state (once sub-project 2's AI classifier or curators populate classifications): the page progressively gains structure as thinkers move out of "Awaiting" into their proper sections. No code change needed.

Sub-projects 2 (AI bulk classifier pipeline) and 3 (curator review tooling) are explicitly out of this spec and plan — they ship in later sessions against the schema this plan lands.
