# Contributors Collection — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a new `/contributors/` collection on indianliberals.in for contemporary opinion-piece writers (CCS fellows, interns, guest writers) — distinct from the canonical `/thinkers/` collection. Extract the inline bio + photo each opinion piece ends with into structured per-writer pages.

**Architecture:** New `contributors` content collection registered in `apps/site/src/content.config.ts`, sibling to `thinkers`/`opinions`. Two synthesis scripts populate it from existing opinion bodies (one extracts MDs + photo URLs; one downloads photos + wires opinion `author:` refs + strips the trailing bio block from the body). Two new Astro page templates render the detail + index pages. Opinion template adds a "Written by" card. One in-place migration: `shivani-a-tannu` moves from `/thinkers/` to `/contributors/`.

**Tech Stack:** Astro v5 content collections (Zod schema), Python 3 (synthesis scripts; existing `scripts/synthesis/` convention), TypeScript/JSX (Astro templates), pnpm.

**Spec:** [`docs/superpowers/specs/2026-05-25-contributors-collection-design.md`](../specs/2026-05-25-contributors-collection-design.md)

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `apps/site/src/content.config.ts` | MODIFY | Add `contributors` collection definition + register; retype `opinions.author` from `thinkers` to `contributors` |
| `apps/site/src/content/contributors/` | CREATE | Directory holding ~11-14 contributor MDs (one file per writer) |
| `apps/site/src/content/contributors/.gitkeep` | CREATE | So the empty directory is committable before the script run |
| `apps/site/public/contributors/photos/` | CREATE | Directory holding ~13 downloaded photo files |
| `apps/site/src/pages/contributors/[slug].astro` | CREATE | Detail page: header + photo + bio body + "Pieces by X" |
| `apps/site/src/pages/contributors/index.astro` | CREATE | Listing page: card grid sorted alphabetical, with piece count |
| `apps/site/src/pages/opinions/[slug].astro` | MODIFY | Add a "Written by" card linked to `/contributors/<slug>/` when `author:` is set |
| `apps/site/src/components/ContributorCard.astro` | CREATE | Reusable photo + name + role/affiliation card; used by opinions and listing |
| `scripts/synthesis/extract_opinion_contributors.py` | CREATE | Bio-block detection + slugify + MD writer; produces `(slug, photo_url)` sidecar |
| `scripts/synthesis/tests/test_extract_opinion_contributors.py` | CREATE | Unit tests for slugify, bio-block regex, false-positive filter, idempotence |
| `scripts/synthesis/wire_opinion_contributors.py` | CREATE | Downloads photos to `public/contributors/photos/`; wires opinion `author:` refs; strips bio block from opinion body |
| `scripts/synthesis/tests/test_wire_opinion_contributors.py` | CREATE | Unit tests for the body-strip + frontmatter-merge helpers; idempotence |
| `apps/site/src/content/thinkers/shivani-a-tannu.md` | DELETE | Migration target (moves to `/contributors/`) |
| `apps/site/src/content/contributors/shivani-a-tannu.md` | CREATE | The migrated MD (handcrafted; bio empty, `bio_source: imported`, `needs_review: true`) |
| `data/authority/thinkers.json` | MODIFY | Remove `shivani-a-tannu` entry + her byline_lookup alias |

**File-size budget**: each new file should land under 250 lines (~scripts) or 200 lines (~templates). If a file grows beyond that, split before committing.

---

## Chunk 1: Schema + collection registration

Goal: register the new `contributors` collection in Astro's content config (with the field shape from spec §5), and retype `opinions.author` from `thinkers` to `contributors`. Build should still pass with an empty collection.

### Task 1.1: Add the `contributors` collection definition

**Files:**
- Modify: `apps/site/src/content.config.ts`
- Create: `apps/site/src/content/contributors/` (empty dir)
- Create: `apps/site/src/content/contributors/.gitkeep`

- [ ] **Step 1.1.1: Add the collection definition**

Insert after the `thinkers` collection block (around line 113, before `const organisations`):

```typescript
// ─── Contemporary contributors (opinion-piece writers) ───────────────
// Distinct from `thinkers` (which is the canonical Indian liberal canon).
// Contributors are CCS fellows / interns / guest writers whose bios
// were extracted from the trailing bio block of opinion pieces.
// See docs/superpowers/specs/2026-05-25-contributors-collection-design.md.

const contributors = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/contributors' }),
  schema: z.object({
    id: z.string(),
    name: z.object({
      canonical: z.string(),
      sort: z.string(),
      also_known_as: z.array(z.string()).default([]),
    }),
    // Local path under /public, e.g. "/contributors/photos/sanjeet-kashyap.jpg".
    // Optional — some imported bios had no photo.
    photo: z.string().optional(),
    // Optional structured fields. Bios mention these inconsistently;
    // extraction is best-effort. Curator fills the rest when triaging.
    affiliation: z.string().optional(),       // e.g. "Centre for Civil Society"
    role: z.string().optional(),              // e.g. "Indian Liberal Fellow"
    joined_at: z.number().int().optional(),   // year
    areas_of_interest: z.array(z.string()).default([]),
    bio_source: z
      .enum(['extracted_from_opinion_bio', 'curator', 'imported'])
      .default('extracted_from_opinion_bio'),
    needs_review: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});
```

- [ ] **Step 1.1.2: Register the collection in the `collections` export**

Modify the existing export block (around line 643). Insert `contributors` next to `thinkers`:

```typescript
export const collections = {
  thinkers,
  contributors,        // ← NEW
  organisations,
  musings,
  // …rest unchanged
};
```

- [ ] **Step 1.1.3: Create the empty content dir + .gitkeep**

```bash
cd "/Users/siraj/Indian Liberals Website"
mkdir -p apps/site/src/content/contributors
touch apps/site/src/content/contributors/.gitkeep
```

- [ ] **Step 1.1.4: Build — confirm Astro accepts the empty collection**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind          # dev-only symlink will block fresh build
pnpm build 2>&1 | grep -E "Indexed |error|Error|ELIFECYCLE"
ln -s ../dist/pagefind public/pagefind   # restore for dev
```

Expected: `Indexed N pages` line prints; no errors. Page count should match the pre-change count exactly (we haven't added any pages, just an empty collection).

### Task 1.2: Retype `opinions.author` from `thinkers` to `contributors`

**Files:**
- Modify: `apps/site/src/content.config.ts` (the `opinions` collection block, around line 198)

- [ ] **Step 1.2.1: Change the `author` ref target**

Find the line in the `opinions` collection schema (currently):
```typescript
author: reference('thinkers').optional(),
```

Change to:
```typescript
author: reference('contributors').optional(),
```

Leave the comment above explaining the field — update the wording to match:
```typescript
// `author_name` is the writer (often "Editorial Team" for CCS profile
// pieces); `author` is the structured ref to the writer's
// contributor entry when one exists. Most opinions are written by
// Editorial Team ABOUT a thinker — that thinker goes in `subject`.
```

- [ ] **Step 1.2.2: Pre-empt the migration: temporarily create a stub shivani-a-tannu in contributors**

The build will fail right now because two opinion files (`encoding-privacy-...`) reference `author: shivani-a-tannu`, which used to resolve into thinkers but now resolves into the empty contributors collection.

Create a minimal stub so the build passes. We'll flesh it out properly in Chunk 5.

```bash
cat > apps/site/src/content/contributors/shivani-a-tannu.md <<'EOF'
---
id: shivani-a-tannu
name:
  canonical: Shivani A. Tannu
  sort: Tannu, Shivani A.
bio_source: imported
needs_review: true
draft: false
---

(Bio pending curator review; this stub exists so the two opinion pieces
referencing her resolve correctly. See migration plan §5.)
EOF
```

- [ ] **Step 1.2.3: Build — confirm opinion `author:` refs still resolve**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | grep -E "Indexed |error|Error|ELIFECYCLE"
ln -s ../dist/pagefind public/pagefind
```

Expected: clean build. Page count is `+1` from baseline (the new `/contributors/shivani-a-tannu/`-ish… wait — no page template yet; Astro builds collection entries but doesn't render pages until we add `pages/contributors/[slug].astro` in Chunk 4). So page count is **unchanged** from baseline.

- [ ] **Step 1.2.4: Commit Chunk 1**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/content.config.ts \
        apps/site/src/content/contributors/.gitkeep \
        apps/site/src/content/contributors/shivani-a-tannu.md
git commit -m "$(cat <<'EOF'
feat(schema): add contributors collection; retype opinions.author

New content collection at apps/site/src/content/contributors/ for
contemporary opinion-piece writers (CCS fellows, interns, guest
writers). Distinct from /thinkers/ (canonical Indian liberal canon).

Schema is minimal: name, optional photo (local path), optional
structured fields (affiliation, role, joined_at, areas_of_interest),
bio_source enum + needs_review/draft. Body of the MD = bio prose.

opinions.author ref retyped from thinkers → contributors. Two
opinions currently reference shivani-a-tannu; a stub contributor
MD is added so the build resolves. Full migration (move from
/thinkers/, populate bio, scrub authority) lands in Chunk 5.

Build clean; page count unchanged (no detail/index page template
yet — comes in Chunk 4).

Refs docs/superpowers/specs/2026-05-25-contributors-collection-design.md §5-6
EOF
)"
```

---

**End of Chunk 1.** Dispatch plan-document-reviewer before proceeding.

---

## Chunk 2: Extraction script + tests

Goal: ship `scripts/synthesis/extract_opinion_contributors.py` which walks every opinion MD, finds the trailing bio block, and writes one contributor MD per unique name. Idempotent — re-running with no new bios produces zero changes.

### Task 2.1: Slugify + name helpers

**Files:**
- Create: `scripts/synthesis/extract_opinion_contributors.py` (skeleton)
- Create: `scripts/synthesis/tests/test_extract_opinion_contributors.py`

- [ ] **Step 2.1.1: Write failing tests for slugify + name-shape helpers**

```python
#!/usr/bin/env python3
"""Tests for extract_opinion_contributors.py helpers."""
from __future__ import annotations
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "extract_opinion_contributors",
    str(Path(__file__).resolve().parents[1] / "extract_opinion_contributors.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_slugify_simple():
    assert mod.slugify("Sanjeet Kashyap") == "sanjeet-kashyap"

def test_slugify_with_initials():
    assert mod.slugify("A. D. Shroff") == "a-d-shroff"

def test_slugify_with_unicode():
    assert mod.slugify("Frédéric Bastiat") == "frederic-bastiat"

def test_slugify_strips_trailing_punct():
    assert mod.slugify("Naina Ojha ") == "naina-ojha"

def test_sort_name_two_part():
    assert mod.sort_name("Sanjeet Kashyap") == "Kashyap, Sanjeet"

def test_sort_name_single():
    assert mod.sort_name("Naina") == "Naina"

def test_sort_name_three_part():
    assert mod.sort_name("Shivani A. Tannu") == "Tannu, Shivani A."

def test_is_false_positive_section_heading():
    assert mod.is_false_positive("Introduction") is True
    assert mod.is_false_positive("References") is True
    assert mod.is_false_positive("Way forward") is True
    assert mod.is_false_positive("Sanjeet Kashyap") is False

if __name__ == "__main__":
    import sys as _sys
    n_pass = n_fail = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                n_pass += 1
                print(f"PASS {name}")
            except AssertionError as e:
                n_fail += 1
                print(f"FAIL {name}: {e}", file=_sys.stderr)
    _sys.exit(0 if n_fail == 0 else 1)
```

- [ ] **Step 2.1.2: Create the script skeleton (helpers only)**

```python
#!/usr/bin/env python3
"""
Step 1 of the contributors-collection pipeline.

Walks every opinion MD under apps/site/src/content/opinions/, finds
the trailing author-bio block (photo URL + bold name + paragraph),
and writes one contributor MD per unique name to
apps/site/src/content/contributors/.

Idempotent: re-runs do NOT overwrite existing contributor MDs.

Emits data/synthesis/contributor-photo-urls.jsonl mapping each
extracted contributor slug to its source photo URL (input for the
wire/download step that runs next).

Run from repo root:
    python3 scripts/synthesis/extract_opinion_contributors.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPINIONS_DIR = ROOT / "apps/site/src/content/opinions"
CONTRIBUTORS_DIR = ROOT / "apps/site/src/content/contributors"
PHOTO_URLS_OUT = ROOT / "data/synthesis/contributor-photo-urls.jsonl"

# Section headings + doc-title patterns that look like names but are not.
_FALSE_POSITIVE_NAMES = frozenset({
    "Introduction", "References", "Conclusion", "Background",
    "Way forward", "Summing Up", "The Witch-hunt", "Need for Two Fleets",
    "The Problem with the First-Past-the-Post System",
    "Defining the Role of the Indian Navy in the Bay of Bengal",
    "Importance of Collective Action", "The Indian Liberals Annual Lecture",
})


def slugify(name: str) -> str:
    """'Sanjeet Kashyap' → 'sanjeet-kashyap'. Strips diacritics, lowercases,
    collapses whitespace + punctuation to single hyphens, strips trailing."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def sort_name(name: str) -> str:
    """'Sanjeet Kashyap' → 'Kashyap, Sanjeet'. Single-word names pass through."""
    parts = name.strip().split()
    if len(parts) < 2:
        return name.strip()
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def is_false_positive(name: str) -> bool:
    """True if the bold-text 'name' is actually a section heading or doc title."""
    return name.strip() in _FALSE_POSITIVE_NAMES


def main() -> int:
    raise NotImplementedError  # filled in Task 2.2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.1.3: Run the tests — expect PASS**

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 scripts/synthesis/tests/test_extract_opinion_contributors.py
```

Expected: 7 PASS, exit 0.

### Task 2.2: Bio-block detection + MD writing

**Files:**
- Modify: `scripts/synthesis/extract_opinion_contributors.py` (add bio-block regex + main loop)
- Modify: `scripts/synthesis/tests/test_extract_opinion_contributors.py` (add bio-block tests)

- [ ] **Step 2.2.1: Append bio-block tests**

Add to the bottom of `test_extract_opinion_contributors.py` (before the `__main__` block):

```python
SAMPLE_WITH_PHOTO = """\
…body paragraphs…

![](https://indianliberals.in/wp-content/uploads/2020/12/sanjeet.jpg)

**Sanjeet Kashyap**

A classic liberal by persuasion, Sanjeet has a BA in History from Hansraj College, University of Delhi…
"""

SAMPLE_NAME_ONLY = """\
…body paragraphs…

**Naina Ojha**
Naina is a writer from Ghaziabad, Uttar Pradesh. She is pursuing a Master's in Gender Studies from Ambedkar University, Delhi…
"""

SAMPLE_NO_BIO = """\
Just a body paragraph with no trailing bio block.

A second paragraph for good measure.
"""

SAMPLE_FALSE_POSITIVE = """\
**Introduction**
This is a section heading, not an author name.

**Way forward**
Same: section, not an author.
"""


def test_extract_bio_with_photo():
    out = mod.extract_bio_block(SAMPLE_WITH_PHOTO)
    assert out is not None
    assert out["name"] == "Sanjeet Kashyap"
    assert out["photo_url"] == "https://indianliberals.in/wp-content/uploads/2020/12/sanjeet.jpg"
    assert "classic liberal" in out["bio"]

def test_extract_bio_name_only():
    out = mod.extract_bio_block(SAMPLE_NAME_ONLY)
    assert out is not None
    assert out["name"] == "Naina Ojha"
    assert out["photo_url"] is None
    assert "Ghaziabad" in out["bio"]

def test_extract_no_bio_returns_none():
    assert mod.extract_bio_block(SAMPLE_NO_BIO) is None

def test_extract_filters_false_positives():
    # "Introduction" and "Way forward" should not be picked as a contributor.
    assert mod.extract_bio_block(SAMPLE_FALSE_POSITIVE) is None
```

- [ ] **Step 2.2.2: Implement `extract_bio_block`**

Add to `extract_opinion_contributors.py` before `def main`:

```python
# Pattern A: photo URL + bold name + bio paragraph (1+ lines).
_BIO_WITH_PHOTO_RX = re.compile(
    r"!\[\]\((?P<photo>https?://[^\)]+\.(?:jpg|jpeg|png|webp))\)\s*\n+"
    r"\s*\*\*(?P<name>[^*\n]+?)\s*\*\*\s*\n+"
    r"(?P<bio>(?:[^\n]+\n?){1,15})",
    re.M,
)

# Pattern B: bold name + bio paragraph (no photo), bio at least 80 chars.
_BIO_NAME_ONLY_RX = re.compile(
    r"\n\*\*(?P<name>[A-Z][A-Za-z. \-]{4,60}?)\s*\*\*\s*\n+"
    r"(?P<bio>[A-Z][^\n]{60,}(?:\n[^\n]+)*)",
    re.M,
)


def extract_bio_block(body: str) -> dict | None:
    """Find the trailing bio block in an opinion body. Returns
    {name, photo_url, bio} or None if no real bio block is present.

    Walks both patterns; takes the LAST match (the trailing block, not
    any inline mid-body image). Filters false-positive 'names' that are
    actually section headings."""
    last = None
    for rx in (_BIO_WITH_PHOTO_RX, _BIO_NAME_ONLY_RX):
        for m in rx.finditer(body):
            name = m.group("name").strip()
            if is_false_positive(name):
                continue
            bio = m.group("bio").strip()
            if len(bio) < 80:
                continue
            try:
                photo = m.group("photo")
            except IndexError:
                photo = None
            last = {"name": name, "photo_url": photo, "bio": bio}
    return last
```

- [ ] **Step 2.2.3: Run tests — expect all 11 PASS**

```bash
python3 scripts/synthesis/tests/test_extract_opinion_contributors.py
```

- [ ] **Step 2.2.4: Implement `write_contributor_md` + `main()`**

Add to `extract_opinion_contributors.py`:

```python
_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


def parse_md(text: str) -> tuple[str, str]:
    """Returns (frontmatter_yaml, body). Raises on malformed."""
    m = _FRONTMATTER_RX.match(text)
    if not m:
        raise ValueError("not a frontmatter MD")
    return m.group(1), m.group(2)


def write_contributor_md(slug: str, name: str, bio: str, photo_url: str | None) -> bool:
    """Create apps/site/src/content/contributors/<slug>.md if not present.
    Returns True if a new file was written, False if it already existed.
    Re-runs MUST NOT overwrite — preserves idempotence + curator edits."""
    path = CONTRIBUTORS_DIR / f"{slug}.md"
    if path.exists():
        return False
    # Best-effort affiliation + role from the bio prose.
    affiliation = None
    if "Centre for Civil Society" in bio or "CCS" in bio:
        affiliation = "Centre for Civil Society"
    role = None
    for pat in ("Indian Liberal Fellow", "Indian Liberals Fellow",
                "Indian Liberals Project intern", "research scholar",
                "intern", "Editorial Team", "Editor"):
        if re.search(rf"\b{re.escape(pat)}\b", bio, re.I):
            role = pat
            break
    # Build YAML
    lines = ["---"]
    lines.append(f"id: {slug}")
    lines.append("name:")
    lines.append(f'  canonical: "{name}"')
    lines.append(f'  sort: "{sort_name(name)}"')
    if affiliation:
        lines.append(f'affiliation: "{affiliation}"')
    if role:
        lines.append(f'role: "{role}"')
    lines.append("bio_source: extracted_from_opinion_bio")
    lines.append("needs_review: true")
    lines.append("draft: false")
    lines.append("---")
    lines.append("")
    lines.append(bio)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report what would be written; touch no files")
    args = ap.parse_args()

    CONTRIBUTORS_DIR.mkdir(parents=True, exist_ok=True)
    PHOTO_URLS_OUT.parent.mkdir(parents=True, exist_ok=True)

    seen: dict[str, str | None] = {}
    n_opinions_scanned = n_bio_found = n_new = n_skipped_existing = 0

    for op_path in sorted(OPINIONS_DIR.glob("*.md")):
        n_opinions_scanned += 1
        text = op_path.read_text(encoding="utf-8")
        try:
            _, body = parse_md(text)
        except ValueError:
            continue
        bio = extract_bio_block(body)
        if not bio:
            continue
        n_bio_found += 1
        slug = slugify(bio["name"])
        # First photo URL wins per slug (preserves the photo from the first occurrence).
        if slug not in seen:
            seen[slug] = bio["photo_url"]
        if args.dry_run:
            continue
        wrote = write_contributor_md(slug, bio["name"], bio["bio"], bio["photo_url"])
        if wrote:
            n_new += 1
        else:
            n_skipped_existing += 1

    # Emit photo-URL sidecar (always rebuilt fresh on every run).
    if not args.dry_run:
        with PHOTO_URLS_OUT.open("w", encoding="utf-8") as f:
            for slug, url in sorted(seen.items()):
                if url:
                    f.write(json.dumps({"slug": slug, "photo_url": url}) + "\n")

    prefix = "dry-run: would " if args.dry_run else ""
    print(f"{prefix}scanned {n_opinions_scanned} opinions; "
          f"found {n_bio_found} bio blocks → {len(seen)} unique contributors; "
          f"new MDs: {n_new}; skipped (already existed): {n_skipped_existing}")
    print(f"photo URL sidecar: {PHOTO_URLS_OUT.relative_to(ROOT)}")
    return 0
```

- [ ] **Step 2.2.5: Run the extraction (dry-run) — sanity-check the counts**

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 scripts/synthesis/extract_opinion_contributors.py --dry-run
```

Expected: `scanned 61 opinions; found ~45 bio blocks → ~12 unique contributors; new MDs: 0; skipped (already existed): 0` (existing is the shivani stub from Chunk 1, but she's a different slug name; should still be ~12 net new candidates).

- [ ] **Step 2.2.6: Run the extraction (live) — produce contributor MDs**

```bash
python3 scripts/synthesis/extract_opinion_contributors.py
```

Expected: `new MDs: ~11-12; skipped: 0 or 1 (shivani-a-tannu if her name appears in a bio block — which it doesn't, so 0)`.

Verify:
```bash
ls apps/site/src/content/contributors/*.md | wc -l   # expect ~12-13 (+1 for shivani stub)
head -10 apps/site/src/content/contributors/sanjeet-kashyap.md
```

- [ ] **Step 2.2.7: Run the script AGAIN — verify idempotence**

```bash
python3 scripts/synthesis/extract_opinion_contributors.py
```

Expected: `new MDs: 0; skipped (already existed): ~12`. No file mutations.

```bash
git status apps/site/src/content/contributors/   # expect only newly-created MDs from the first live run; no further mods
```

- [ ] **Step 2.2.8: Re-build the site — confirm contributor MDs validate against the schema**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | grep -E "Indexed |error|Error|ELIFECYCLE"
ln -s ../dist/pagefind public/pagefind
```

Expected: clean build. Page count still unchanged (no detail-page template yet).

- [ ] **Step 2.2.9: Commit Chunk 2**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add scripts/synthesis/extract_opinion_contributors.py \
        scripts/synthesis/tests/test_extract_opinion_contributors.py \
        apps/site/src/content/contributors/ \
        data/synthesis/contributor-photo-urls.jsonl
git commit -m "$(cat <<'EOF'
feat(synthesis): extract opinion contributors into the new collection

scripts/synthesis/extract_opinion_contributors.py walks every opinion
MD, finds the trailing bio block (photo URL + bold name + paragraph),
and writes one contributor MD per unique name to
apps/site/src/content/contributors/.

Idempotent — re-runs skip existing MDs without overwrite, preserving
curator edits.

Bio-block detection handles two patterns:
  pattern A: photo URL + **Name** + paragraph
  pattern B: **Name** + paragraph (no photo; bio >= 80 chars)
False positives ("Introduction", "References", "Way forward", etc.)
are filtered by name allowlist.

Best-effort frontmatter extraction:
  affiliation: matches "Centre for Civil Society" / "CCS"
  role:        matches "Indian Liberal Fellow", "intern", etc.
needs_review: true is set on every new MD; curator triages.

Emits data/synthesis/contributor-photo-urls.jsonl with the source
photo URL per contributor slug (consumed by the wire step in Chunk 3).

11 helper unit tests passing (slugify, sort_name, false-positive
filter, bio-block detection across all four cases).

Refs docs/superpowers/specs/2026-05-25-contributors-collection-design.md §7.1, §7.3
EOF
)"
```

---

**End of Chunk 2.** Dispatch plan-document-reviewer before proceeding.

---

## Chunk 3: Photo download + wire-opinion script

Goal: download the ~13 source photos to `apps/site/public/contributors/photos/`, update each contributor MD's `photo:` field to the local path, then wire each opinion's `author:` ref to its contributor and strip the bio block from the opinion body.

### Task 3.1: Photo download

**Files:**
- Create: `apps/site/public/contributors/photos/` (directory)

- [ ] **Step 3.1.1: Create the photos directory**

```bash
cd "/Users/siraj/Indian Liberals Website"
mkdir -p apps/site/public/contributors/photos
```

- [ ] **Step 3.1.2: Run the photo downloader (inline shell script — small one-shot)**

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 <<'PY'
import json, urllib.request, os, sys, re
from pathlib import Path

sidecar = Path("data/synthesis/contributor-photo-urls.jsonl")
out_dir = Path("apps/site/public/contributors/photos")
out_dir.mkdir(parents=True, exist_ok=True)

n_ok = n_fail = 0
results = []
for line in sidecar.read_text().splitlines():
    if not line.strip(): continue
    rec = json.loads(line)
    slug, url = rec["slug"], rec["photo_url"]
    ext = os.path.splitext(url.split("?")[0])[1].lower() or ".jpg"
    dest = out_dir / f"{slug}{ext}"
    if dest.exists():
        results.append((slug, ext, "exists"))
        continue
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "indianliberals-archive/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        results.append((slug, ext, "downloaded"))
        n_ok += 1
    except Exception as e:
        results.append((slug, ext, f"FAILED: {e}"))
        n_fail += 1

for slug, ext, status in results:
    print(f"  {slug:30} {ext:5} {status}")
print(f"\ntotal: {n_ok} downloaded, {n_fail} failed")
PY
```

Expected: ~13 lines printed, each `downloaded` or `exists`. If any line says `FAILED:`, log it for follow-up (the contributor MD will keep `photo:` unset).

- [ ] **Step 3.1.3: Update each contributor MD's `photo:` field**

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 <<'PY'
import json, re, yaml
from pathlib import Path

sidecar = Path("data/synthesis/contributor-photo-urls.jsonl")
contrib_dir = Path("apps/site/src/content/contributors")
photos_dir = Path("apps/site/public/contributors/photos")

n_updated = 0
for line in sidecar.read_text().splitlines():
    if not line.strip(): continue
    rec = json.loads(line)
    slug = rec["slug"]
    md = contrib_dir / f"{slug}.md"
    if not md.exists():
        print(f"  WARN: no MD for {slug}")
        continue
    # Find local photo (any extension)
    candidates = list(photos_dir.glob(f"{slug}.*"))
    if not candidates:
        print(f"  WARN: no local photo for {slug}")
        continue
    photo_path = f"/contributors/photos/{candidates[0].name}"
    text = md.read_text(encoding="utf-8")
    # Insert / replace photo: line. The MD has frontmatter form already.
    if re.search(r"^photo:", text, re.M):
        new_text = re.sub(r"^photo:.*$", f'photo: "{photo_path}"', text, count=1, flags=re.M)
    else:
        # Insert after the name: block (after `sort:` line)
        new_text = re.sub(r"(^  sort: [^\n]+\n)", rf'\1photo: "{photo_path}"\n', text, count=1, flags=re.M)
    if new_text != text:
        md.write_text(new_text, encoding="utf-8")
        n_updated += 1
        print(f"  set photo on {slug}")
print(f"\nupdated {n_updated} contributor MDs")
PY
```

Expected: ~13 lines `set photo on <slug>`. Verify one:

```bash
head -10 apps/site/src/content/contributors/sanjeet-kashyap.md
# Expected: a `photo: "/contributors/photos/sanjeet-kashyap.jpg"` line is present
```

- [ ] **Step 3.1.4: Rebuild — verify photo paths are valid**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | grep -E "Indexed |error|Error|ELIFECYCLE"
ln -s ../dist/pagefind public/pagefind
```

Expected: clean build.

### Task 3.2: `wire_opinion_contributors.py`

**Files:**
- Create: `scripts/synthesis/wire_opinion_contributors.py`
- Create: `scripts/synthesis/tests/test_wire_opinion_contributors.py`

- [ ] **Step 3.2.1: Write failing tests for the body-strip + author-merge helpers**

```python
#!/usr/bin/env python3
"""Tests for wire_opinion_contributors.py helpers."""
from __future__ import annotations
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "wire_opinion_contributors",
    str(Path(__file__).resolve().parents[1] / "wire_opinion_contributors.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


BODY_WITH_PHOTO_BIO = """\
Some body text.

Another paragraph.

![](https://indianliberals.in/wp-content/uploads/2020/12/sanjeet.jpg)

**Sanjeet Kashyap**

A classic liberal by persuasion, Sanjeet has a BA in History from Hansraj College…
"""

BODY_NAME_ONLY_BIO = """\
Some body text.

**Naina Ojha**
Naina is a writer from Ghaziabad, Uttar Pradesh…
"""

BODY_NO_BIO = """\
Just body text. No bio block at the end.
"""


def test_strip_bio_with_photo():
    out = mod.strip_bio_block(BODY_WITH_PHOTO_BIO)
    assert "A classic liberal" not in out
    assert "Sanjeet Kashyap" not in out
    assert "indianliberals.in" not in out
    assert "Some body text." in out
    assert "Another paragraph." in out

def test_strip_bio_name_only():
    out = mod.strip_bio_block(BODY_NAME_ONLY_BIO)
    assert "Naina is a writer" not in out
    assert "Naina Ojha" not in out
    assert "Some body text." in out

def test_strip_bio_no_bio_passthrough():
    out = mod.strip_bio_block(BODY_NO_BIO)
    assert out == BODY_NO_BIO

def test_set_frontmatter_author_inserts():
    fm = "id: foo\ntitle: bar\nauthor_name: Editorial Team\n"
    out = mod.set_frontmatter_author(fm, "sanjeet-kashyap")
    assert "author: sanjeet-kashyap" in out
    assert "author_name: Editorial Team" in out   # other fields preserved

def test_set_frontmatter_author_replaces():
    fm = "id: foo\nauthor: old-author\nauthor_name: X\n"
    out = mod.set_frontmatter_author(fm, "new-author")
    assert "author: new-author" in out
    assert "author: old-author" not in out

if __name__ == "__main__":
    n_pass = n_fail = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                n_pass += 1
                print(f"PASS {name}")
            except AssertionError as e:
                n_fail += 1
                print(f"FAIL {name}: {e}", file=sys.stderr)
    sys.exit(0 if n_fail == 0 else 1)
```

- [ ] **Step 3.2.2: Implement the helpers + main loop**

```python
#!/usr/bin/env python3
"""
Step 2 of the contributors-collection pipeline.

For every opinion MD whose trailing bio block matched a contributor we
extracted in step 1:
  1. Set frontmatter `author: <slug>` (insert or replace).
  2. Strip the trailing bio block from the body.

Preserves every other frontmatter field + the rest of the body.
Idempotent: re-runs with no new bios produce zero file changes.

Run from repo root (after extract_opinion_contributors.py):
    python3 scripts/synthesis/wire_opinion_contributors.py
    python3 scripts/synthesis/wire_opinion_contributors.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPINIONS_DIR = ROOT / "apps/site/src/content/opinions"
CONTRIBUTORS_DIR = ROOT / "apps/site/src/content/contributors"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)

# Bio block: starts at either the photo image or the bold name marker
# (whichever comes first in the trailing region), continues to EOF.
_BIO_PHOTO_RX = re.compile(
    r"\n!\[\]\(https?://[^\)]+\.(?:jpg|jpeg|png|webp)\)\s*\n+\s*\*\*[^*]+\*\*[\s\S]*$",
    re.M,
)
_BIO_NAME_RX = re.compile(
    r"\n\*\*[A-Z][A-Za-z. \-]{4,60}?\s*\*\*\s*\n+[A-Z][^\n]{60,}[\s\S]*$",
    re.M,
)

# Also strip a stray empty link that some opinions have just before the bio.
_STRAY_BIO_LINK_RX = re.compile(
    r"\n\[\]\(https?://[^\)]*/attachment/bio/?\)\s*\n",
    re.M,
)


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def strip_bio_block(body: str) -> str:
    """Remove the trailing bio block (and any stray /attachment/bio/ link
    immediately preceding it). Returns body with the block stripped. If no
    bio block is present, returns body unchanged."""
    # Strip the stray empty bio link first (cosmetic; some opinions have it).
    body = _STRAY_BIO_LINK_RX.sub("\n", body)
    # Then strip the actual block.
    for rx in (_BIO_PHOTO_RX, _BIO_NAME_RX):
        m = rx.search(body)
        if m:
            return body[: m.start()].rstrip() + "\n"
    return body


def set_frontmatter_author(fm: str, slug: str) -> str:
    """Insert `author: <slug>` into the frontmatter YAML string, or
    replace an existing `author:` line. Other fields untouched."""
    line = f"author: {slug}"
    if re.search(r"^author:\s*\S+", fm, re.M):
        return re.sub(r"^author:.*$", line, fm, count=1, flags=re.M)
    # Insert just after `author_name:` line if present, else append.
    if re.search(r"^author_name:", fm, re.M):
        return re.sub(r"(^author_name:[^\n]+\n)", rf"\1{line}\n", fm, count=1, flags=re.M)
    return fm.rstrip() + "\n" + line + "\n"


def parse_md(text: str) -> tuple[str, str] | None:
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return None
    return m.group(1), m.group(2)


def find_contributor_for_body(body: str) -> str | None:
    """Re-detect the trailing bio block's name and resolve it to an existing
    contributor slug. Returns None if no bio or no matching contributor MD."""
    # Reuse the patterns from extract_opinion_contributors via independent regex.
    name_with_photo = re.search(
        r"!\[\]\(https?://[^\)]+\.(?:jpg|jpeg|png|webp)\)\s*\n+\s*\*\*([^*\n]+?)\s*\*\*\s*\n",
        body,
    )
    if name_with_photo:
        slug = slugify(name_with_photo.group(1))
        if (CONTRIBUTORS_DIR / f"{slug}.md").exists():
            return slug
    # Fall back to name-only pattern
    name_only = list(re.finditer(
        r"\n\*\*([A-Z][A-Za-z. \-]{4,60}?)\s*\*\*\s*\n+([A-Z][^\n]{60,})",
        body, re.M,
    ))
    if name_only:
        m = name_only[-1]
        slug = slugify(m.group(1))
        if (CONTRIBUTORS_DIR / f"{slug}.md").exists():
            return slug
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    n_opinions = n_wired = n_stripped = n_already = n_no_match = 0

    for op_path in sorted(OPINIONS_DIR.glob("*.md")):
        n_opinions += 1
        text = op_path.read_text(encoding="utf-8")
        parsed = parse_md(text)
        if not parsed:
            continue
        fm, body = parsed
        slug = find_contributor_for_body(body)
        if not slug:
            n_no_match += 1
            continue
        # Check if already wired
        author_match = re.search(r"^author:\s*(\S+)", fm, re.M)
        already_set = author_match and author_match.group(1) == slug
        new_body = strip_bio_block(body)
        body_changed = (new_body != body)
        if already_set and not body_changed:
            n_already += 1
            continue
        new_fm = set_frontmatter_author(fm, slug)
        new_text = f"---\n{new_fm.rstrip()}\n---\n{new_body}"
        if args.dry_run:
            if not already_set:
                n_wired += 1
            if body_changed:
                n_stripped += 1
            continue
        op_path.write_text(new_text, encoding="utf-8")
        if not already_set:
            n_wired += 1
        if body_changed:
            n_stripped += 1

    prefix = "dry-run: would " if args.dry_run else ""
    print(f"{prefix}scan {n_opinions} opinions: wire {n_wired} new author refs; "
          f"strip bio from {n_stripped} bodies; "
          f"{n_already} already wired (no change); "
          f"{n_no_match} no bio match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3.2.3: Run tests — expect 5 PASS**

```bash
python3 scripts/synthesis/tests/test_wire_opinion_contributors.py
```

- [ ] **Step 3.2.4: Dry-run on the live corpus**

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 scripts/synthesis/wire_opinion_contributors.py --dry-run
```

Expected: `would wire ~45 new author refs; strip bio from ~45 bodies; 0 already wired; ~16 no bio match`.

- [ ] **Step 3.2.5: Live run**

```bash
python3 scripts/synthesis/wire_opinion_contributors.py
git diff --stat apps/site/src/content/opinions/ | tail -3
```

Expected: ~45 opinion MDs modified.

- [ ] **Step 3.2.6: Verify idempotence**

```bash
python3 scripts/synthesis/wire_opinion_contributors.py
```

Expected: `wire 0 new author refs; strip bio from 0 bodies; ~45 already wired; ~16 no bio match`. No file changes from this second run:

```bash
git status apps/site/src/content/opinions/ | grep -c "^	modified:"
# Expected: same count as after Step 3.2.5 (no further mods from this run alone)
```

- [ ] **Step 3.2.7: Build the site**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | grep -E "Indexed |error|Error|ELIFECYCLE"
ln -s ../dist/pagefind public/pagefind
```

Expected: clean build.

- [ ] **Step 3.2.8: Commit Chunk 3**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add scripts/synthesis/wire_opinion_contributors.py \
        scripts/synthesis/tests/test_wire_opinion_contributors.py \
        apps/site/public/contributors/ \
        apps/site/src/content/contributors/ \
        apps/site/src/content/opinions/
git commit -m "$(cat <<'EOF'
feat(synthesis): download contributor photos + wire opinions

Two-step landing:

1. Photo download — fetched the ~13 source photos referenced in the
   extract step's sidecar (data/synthesis/contributor-photo-urls.jsonl)
   from the live indianliberals.in WP host to
   apps/site/public/contributors/photos/<slug>.<ext>. Each contributor
   MD's `photo:` field updated to the local path. Photos are committed
   to git (small files, < 200 KB each).

2. wire_opinion_contributors.py — for every opinion with a trailing
   bio block:
     - Inserts/replaces frontmatter `author: <slug>` ref.
     - Strips the trailing bio block from the body (now lives on the
       contributor's page + the "Written by" card lands in Chunk 4).
   Idempotent: re-runs produce zero file changes. 5 helper unit tests
   passing (strip_bio_block × 3 cases, set_frontmatter_author × 2).

~45 opinions wired + stripped; ~16 opinions had no bio block and
keep their unset `author:` field.

Refs docs/superpowers/specs/2026-05-25-contributors-collection-design.md §7.2, §7.4
EOF
)"
```

---

**End of Chunk 3.** Dispatch plan-document-reviewer before proceeding.

---

## Chunk 4: Page templates

Goal: render the contributor detail page, the contributor index page, and add a "Written by" card to the opinion page.

### Task 4.1: `ContributorCard` shared component

**Files:**
- Create: `apps/site/src/components/ContributorCard.astro`

- [ ] **Step 4.1.1: Write the component**

```astro
---
// Reusable small card for a contributor — photo thumb + name + role/affiliation.
// Used on opinion pages ("Written by …") and on /contributors/ index cards.

interface Props {
  contributor: {
    id: string;
    data: {
      name: { canonical: string };
      photo?: string;
      role?: string;
      affiliation?: string;
    };
  };
  variant?: "inline" | "card";
}

const { contributor, variant = "inline" } = Astro.props;
const d = contributor.data;
const subtitle = [d.role, d.affiliation].filter(Boolean).join(" · ");
---

{variant === "inline" ? (
  <aside class="mt-10 pt-8 border-t border-(--color-border) flex items-start gap-4 font-(family-name:--font-ui)">
    {d.photo && (
      <img src={d.photo} alt="" class="w-16 h-16 rounded-full object-cover flex-shrink-0" />
    )}
    <div>
      <p class="text-xs uppercase tracking-widest text-(--color-fg-muted) mb-1">Written by</p>
      <p class="text-(--color-fg) font-semibold">
        <a href={`/contributors/${contributor.id}/`} class="text-(--color-forest-700) no-underline hover:underline">
          {d.name.canonical}
        </a>
      </p>
      {subtitle && (
        <p class="text-sm text-(--color-fg-muted) mt-0.5">{subtitle}</p>
      )}
    </div>
  </aside>
) : (
  <a href={`/contributors/${contributor.id}/`} class="block group no-underline">
    <div class="aspect-square bg-(--color-bg-muted) border border-(--color-border) rounded-sm overflow-hidden flex items-end justify-center">
      {d.photo ? (
        <img src={d.photo} alt="" class="w-full h-full object-cover" />
      ) : (
        <span class="text-(--color-fg-muted) text-4xl font-(family-name:--font-display) opacity-30">
          {d.name.canonical[0]}
        </span>
      )}
    </div>
    <p class="mt-3 text-(--color-fg) font-(family-name:--font-ui) text-sm font-semibold leading-tight">
      {d.name.canonical}
    </p>
    {subtitle && (
      <p class="mt-1 text-xs text-(--color-fg-muted) font-(family-name:--font-ui)">{subtitle}</p>
    )}
  </a>
)}
```

### Task 4.2: `/contributors/[slug].astro` detail page

**Files:**
- Create: `apps/site/src/pages/contributors/[slug].astro`

- [ ] **Step 4.2.1: Write the detail page template**

```astro
---
import BaseLayout from "~/layouts/BaseLayout.astro";
import { getCollection, render } from "astro:content";

export async function getStaticPaths() {
  const contributors = await getCollection("contributors", (c) => !c.data.draft);
  return contributors.map((c) => ({ params: { slug: c.id }, props: { c } }));
}

const { c } = Astro.props;
const { Content } = await render(c);

// Pieces written by this contributor.
const opinions = await getCollection("opinions");
const byThisContributor = opinions
  .filter((o) => o.data.author?.id === c.id)
  .sort((a, b) => +new Date(b.data.pubDate) - +new Date(a.data.pubDate));

const subtitle = [c.data.role, c.data.affiliation].filter(Boolean).join(" · ");
---

<BaseLayout title={`${c.data.name.canonical} — Indian Liberals`}>
  <article class="mx-auto max-w-3xl px-6 py-12 md:py-16">
    <header class="grid grid-cols-[auto,1fr] gap-6 items-start border-b border-(--color-border) pb-10 mb-10">
      {c.data.photo ? (
        <img src={c.data.photo} alt="" class="w-32 h-32 rounded-sm object-cover" />
      ) : (
        <div class="w-32 h-32 bg-(--color-bg-muted) border border-(--color-border) rounded-sm flex items-center justify-center">
          <span class="text-5xl font-(family-name:--font-display) text-(--color-fg-muted) opacity-30">
            {c.data.name.canonical[0]}
          </span>
        </div>
      )}
      <div>
        <h1 class="text-(--color-fg) leading-tight">{c.data.name.canonical}</h1>
        {subtitle && (
          <p class="mt-2 text-(--color-fg-muted) font-(family-name:--font-ui)">{subtitle}</p>
        )}
      </div>
    </header>

    {/* Bio prose (body of the MD) */}
    <div class="prose-container text-(--color-fg) leading-relaxed">
      <Content />
    </div>

    {byThisContributor.length > 0 && (
      <section class="mt-12 pt-8 border-t border-(--color-border) font-(family-name:--font-ui)">
        <h2 class="text-xs uppercase tracking-widest text-(--color-fg-muted) mb-4">
          Pieces by {c.data.name.canonical.split(" ")[0]} ({byThisContributor.length})
        </h2>
        <ul class="space-y-2">
          {byThisContributor.map((o) => (
            <li>
              <a href={`/opinions/${o.id}/`} class="text-sm text-(--color-forest-700) no-underline hover:underline">
                {o.data.title}
              </a>
              <span class="text-(--color-fg-muted) text-xs ml-2">· {new Date(o.data.pubDate).getFullYear()}</span>
            </li>
          ))}
        </ul>
      </section>
    )}
  </article>
</BaseLayout>
```

### Task 4.3: `/contributors/index.astro` listing page

**Files:**
- Create: `apps/site/src/pages/contributors/index.astro`

- [ ] **Step 4.3.1: Write the index page template**

```astro
---
import BaseLayout from "~/layouts/BaseLayout.astro";
import { getCollection } from "astro:content";
import ContributorCard from "~/components/ContributorCard.astro";

const contributors = (await getCollection("contributors", (c) => !c.data.draft))
  .sort((a, b) => a.data.name.sort.localeCompare(b.data.name.sort));

const opinions = await getCollection("opinions");
const pieceCount = (slug: string) =>
  opinions.filter((o) => o.data.author?.id === slug).length;
---

<BaseLayout title="Contributors — Indian Liberals">
  <article class="mx-auto max-w-6xl px-6 py-12 md:py-16">
    <header class="border-b border-(--color-border) pb-10 mb-10">
      <h1 class="text-(--color-fg)">Contributors</h1>
      <p class="mt-4 text-(--color-fg-muted) font-(family-name:--font-ui) max-w-prose">
        Writers, fellows, and interns who have contributed opinion pieces
        to indianliberals.in. Distinct from the Indian liberal canon
        catalogued under <a href="/thinkers/" class="text-(--color-forest-700)">thinkers</a>.
      </p>
      <p class="mt-4 text-sm text-(--color-fg-muted) font-(family-name:--font-ui)">
        {contributors.length} contributors
      </p>
    </header>

    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-10">
      {contributors.map((c) => (
        <ContributorCard contributor={c} variant="card" />
      ))}
    </div>
  </article>
</BaseLayout>
```

### Task 4.4: Wire the "Written by" card into the opinion page

**Files:**
- Modify: `apps/site/src/pages/opinions/[slug].astro`

- [ ] **Step 4.4.1: Resolve the contributor from the opinion's `author:` ref**

In the frontmatter section of `apps/site/src/pages/opinions/[slug].astro` (top of file), add (next to existing imports):

```typescript
import { getEntry } from "astro:content";
import ContributorCard from "~/components/ContributorCard.astro";
```

And after the existing destructuring of `o` / `Content` / etc., add:

```typescript
const contributor = o.data.author ? await getEntry(o.data.author) : null;
```

- [ ] **Step 4.4.2: Render the card after the body**

Find the `<Content />` render block. Immediately after it (before any closing section or footer markup), add:

```jsx
{contributor && (
  <ContributorCard contributor={contributor} variant="inline" />
)}
```

- [ ] **Step 4.4.3: Build the site**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | grep -E "Indexed |error|Error|ELIFECYCLE"
ln -s ../dist/pagefind public/pagefind
```

Expected: page count is +N from baseline where `N = (contributor detail pages) + 1 (contributor index page)`. If there are 12 contributors, expect `+13`.

- [ ] **Step 4.4.4: Smoke-test the rendered pages**

```bash
cd "/Users/siraj/Indian Liberals Website"

# Detail page
ls apps/site/dist/contributors/sanjeet-kashyap/index.html
grep -c "Sanjeet Kashyap" apps/site/dist/contributors/sanjeet-kashyap/index.html
# Expected: file exists; name appears >= 2 times (header + page title)

grep -c "Pieces by Sanjeet" apps/site/dist/contributors/sanjeet-kashyap/index.html
# Expected: 1 — the "Pieces by Sanjeet" section heading

# Index page
ls apps/site/dist/contributors/index.html
grep -c 'href="/contributors/sanjeet-kashyap/"' apps/site/dist/contributors/index.html
# Expected: 1 (Sanjeet's card on the index)

# Opinion page with the new "Written by" card
grep -c "Written by" apps/site/dist/opinions/b-r-ambedkar-social-reform-failure-of-indian-liberalism/index.html
grep -c 'href="/contributors/sanjeet-kashyap/"' apps/site/dist/opinions/b-r-ambedkar-social-reform-failure-of-indian-liberalism/index.html
# Expected: both 1

# Opinion page WITHOUT an author — no card
grep -c "Written by" apps/site/dist/opinions/decentralisation-and-panchayati-raj-system-in-india/index.html
# Expected: 0 (this opinion has author_name "Editorial Team" but no author ref)
```

- [ ] **Step 4.4.5: Commit Chunk 4**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/components/ContributorCard.astro \
        apps/site/src/pages/contributors/ \
        apps/site/src/pages/opinions/\[slug\].astro
git commit -m "$(cat <<'EOF'
feat(ui): contributor pages + 'Written by' card on opinions

Three new render surfaces:

1. /contributors/<slug>/ detail page — photo + name + role/affiliation
   chip, bio prose rendered from the MD body, "Pieces by X" list of
   opinions where author=<slug>.

2. /contributors/ index page — alphabetical card grid (photo + name +
   role/affiliation) using a shared ContributorCard component.

3. Opinion pages — "Written by" inline card at the bottom resolves
   the opinion's author ref into the contributors collection.
   ContributorCard supports both variants (inline + card) so the
   same component renders both places.

ContributorCard is intentionally a presentation-only component —
no data fetching, takes a pre-resolved contributor entry as a prop.

Build clean. Page count +N (N = number of contributors + 1 index).

Refs docs/superpowers/specs/2026-05-25-contributors-collection-design.md §8
EOF
)"
```

---

**End of Chunk 4.** Dispatch plan-document-reviewer before proceeding.

---

## Chunk 5: shivani-a-tannu migration + final acceptance

Goal: properly migrate `shivani-a-tannu` from the placeholder stub to a real contributor entry; scrub the authority file; verify every §10 acceptance criterion from the spec.

### Task 5.1: Migrate `shivani-a-tannu` properly

**Files:**
- Delete: `apps/site/src/content/thinkers/shivani-a-tannu.md`
- Modify: `apps/site/src/content/contributors/shivani-a-tannu.md` (the Chunk 1 stub)
- Modify: `data/authority/thinkers.json` (remove entry + byline_lookup alias)

- [ ] **Step 5.1.1: Inspect the existing `/thinkers/` entry for any bio text to migrate**

```bash
cd "/Users/siraj/Indian Liberals Website"
cat apps/site/src/content/thinkers/shivani-a-tannu.md
```

If there's body content (likely empty), copy it into the existing
`apps/site/src/content/contributors/shivani-a-tannu.md` stub by hand.

- [ ] **Step 5.1.2: Delete the thinkers entry**

```bash
git rm apps/site/src/content/thinkers/shivani-a-tannu.md
```

- [ ] **Step 5.1.3: Scrub authority file**

```bash
cd "/Users/siraj/Indian Liberals Website"
python3 <<'PY'
import json
from pathlib import Path
p = Path("data/authority/thinkers.json")
a = json.load(p.open())
before_t = len(a["thinkers"])
a["thinkers"] = [t for t in a["thinkers"] if t.get("id") != "shivani-a-tannu"]
removed_t = before_t - len(a["thinkers"])
before_bl = len(a.get("byline_lookup", {}))
a["byline_lookup"] = {k: v for k, v in a.get("byline_lookup", {}).items() if v != "shivani-a-tannu"}
removed_bl = before_bl - len(a["byline_lookup"])
counts = a.get("_meta", {}).get("counts", {})
counts["total"] = len(a["thinkers"])
from collections import Counter
cc = Counter(t.get("confidence", "medium") for t in a["thinkers"])
counts["canonical"] = cc.get("canonical", 0)
counts["high"] = cc.get("high", 0)
counts["medium"] = cc.get("medium", 0)
p.write_text(json.dumps(a, ensure_ascii=False, indent=2))
print(f"removed {removed_t} thinker entry + {removed_bl} byline_lookup aliases")
print(f"_meta.counts: {counts}")
PY
```

- [ ] **Step 5.1.4: Build — verify everything still resolves**

```bash
cd "/Users/siraj/Indian Liberals Website/apps/site"
rm -f public/pagefind
pnpm build 2>&1 | grep -E "Indexed |error|Error|ELIFECYCLE"
ln -s ../dist/pagefind public/pagefind
```

Expected: clean build; page count drops by 1 (no more thinker detail page for her), gains 0 (her contributor detail page already exists from Chunk 4).

### Task 5.2: Acceptance verification (spec §10)

- [ ] **Step 5.2.1: Schema + collection (§10.1 #1-#3)**

Already verified in Chunk 1.

- [ ] **Step 5.2.2: Extraction (§10.2 #4-#8)**

```bash
cd "/Users/siraj/Indian Liberals Website"
ls apps/site/src/content/contributors/*.md | wc -l
# Expected: ~12-13 (~11 extracted + shivani migrated)

# Bodies are non-empty for the extracted ones
for f in apps/site/src/content/contributors/sanjeet-kashyap.md apps/site/src/content/contributors/naina-ojha.md; do
  bytes=$(awk '/^---$/{n++; next} n==2{print}' "$f" | wc -c | tr -d ' ')
  echo "  $f: body=$bytes chars"
done
# Expected: bodies > 50 chars each
```

- [ ] **Step 5.2.3: Photo download (§10.3 #9-#11)**

```bash
ls apps/site/public/contributors/photos/ | wc -l
# Expected: number of contributors that had a photo URL in their bio block (~10-13)

# Photos are committed to git
git ls-files apps/site/public/contributors/photos/ | wc -l
# Expected: same as above

# Sample MD has the local path
grep "^photo:" apps/site/src/content/contributors/sanjeet-kashyap.md
# Expected: photo: "/contributors/photos/sanjeet-kashyap.jpg" (or similar ext)
```

- [ ] **Step 5.2.4: Wire + strip (§10.4 #12-#15)**

```bash
# Every wired opinion has author: in frontmatter
grep -c "^author: " apps/site/src/content/opinions/b-r-ambedkar-social-reform-failure-of-indian-liberalism.md
# Expected: 1

# Bio block is stripped from the body
grep -c "A classic liberal by persuasion" apps/site/src/content/opinions/b-r-ambedkar-social-reform-failure-of-indian-liberalism.md
# Expected: 0 (the bio paragraph is gone)

# Idempotence
python3 scripts/synthesis/wire_opinion_contributors.py
git status apps/site/src/content/opinions/
# Expected: no further mods from this re-run
```

- [ ] **Step 5.2.5: Page rendering (§10.5 #16-#19)**

Already verified in Chunk 4. Repeat the smoke tests against the freshly-built dist.

- [ ] **Step 5.2.6: Migration (§10.6 #20-#22)**

```bash
# Contributor MD exists; thinker MD does not
ls apps/site/src/content/contributors/shivani-a-tannu.md
ls apps/site/src/content/thinkers/shivani-a-tannu.md 2>&1
# Expected: contributor exists; thinker raises "No such file or directory"

# Authority no longer references her
python3 -c "
import json
a = json.load(open('data/authority/thinkers.json'))
ids = [t['id'] for t in a['thinkers']]
print('in thinkers list:', 'shivani-a-tannu' in ids)
print('in byline_lookup:', 'shivani-a-tannu' in a.get('byline_lookup', {}).values())
"
# Expected: both False

# Her opinion still resolves the author ref (to /contributors/)
grep -c 'href="/contributors/shivani-a-tannu/"' apps/site/dist/opinions/encoding-privacy-in-a-digital-world-by-shivani-a-tannu/index.html
# Expected: 1 (the "Written by" card links to her contributor page)
```

- [ ] **Step 5.2.7: Regression (§10.7 #23-#26)**

```bash
cd "/Users/siraj/Indian Liberals Website"
find apps/site/dist -name 'index.html' | wc -l
# Compare to the pre-work baseline. Delta should equal:
#   +N (contributor detail pages) + 1 (contributor index) - 1 (deleted shivani thinker)
# For 12 contributors: delta = +12 + 1 - 1 = +12

# /thinkers/ index still renders the canon sections
grep -c "Liberal canon\|Extended liberal tradition\|Referenced thinkers" apps/site/dist/thinkers/index.html
# Expected: 3
```

### Task 5.3: Commit + final ship

- [ ] **Step 5.3.1: Commit Chunk 5**

```bash
cd "/Users/siraj/Indian Liberals Website"
git add apps/site/src/content/thinkers/shivani-a-tannu.md \
        apps/site/src/content/contributors/shivani-a-tannu.md \
        data/authority/thinkers.json
git commit -m "$(cat <<'EOF'
chore(data): migrate shivani-a-tannu thinker → contributor

Final piece of the contributors-collection landing. The
shivani-a-tannu MD was a placeholder in /thinkers/ — semantically
she's a CCS contributor (Editorial Team author of two privacy-
encoding opinions), not an Indian liberal canon figure.

Migration:
- Delete apps/site/src/content/thinkers/shivani-a-tannu.md.
- The Chunk-1 stub at apps/site/src/content/contributors/
  shivani-a-tannu.md becomes the canonical entry (bio: pending
  curator review; needs_review: true).
- Scrub the authority file: removed her thinker entry + 1
  byline_lookup alias (canonical/high/medium counts recomputed).
- The two opinions referencing author: shivani-a-tannu now resolve
  to /contributors/ (via the schema rebind from Chunk 1).

Build clean. Net page count delta from the whole contributors
landing: +N where N = (contributor detail pages) + 1 (contributor
index page) - 1 (shivani thinker deletion).

Refs docs/superpowers/specs/2026-05-25-contributors-collection-design.md §9, §10.6
EOF
)"
```

- [ ] **Step 5.3.2: Push when ready**

```bash
git log --oneline 2f98422..HEAD   # spec sha → review what landed
git push origin main              # Adnan's call when to push
```

---

**End of Chunk 5.** Dispatch plan-document-reviewer; once approved, the plan is complete.

---

## Reviewer dispatch template

For each chunk above, dispatch the plan-document-reviewer with:

```
You are a plan document reviewer. Verify this chunk is complete and ready to execute.

**Chunk to review:** [paste chunk content]

**Spec reference:** /Users/siraj/Indian Liberals Website/docs/superpowers/specs/2026-05-25-contributors-collection-design.md

## What to check

| Category | What to look for |
|---|---|
| Granularity | Each step is one 2-5 minute action |
| Completeness | No TODOs; no "implement X here" without concrete code |
| Testability | Acceptance commands have real grep/ls/jq patterns with expected output |
| Exactness | File paths absolute; commit messages drafted |
| Spec fidelity | Plan matches spec §X for the chunk's scope |
| Idempotence | Scripts assert idempotence is verifiable |

Return: Status (Approved | Issues Found), per-task verification, new issues introduced, recommendations.
```

Fix issues in-place; re-dispatch until approved.

---

## Plan complete

After all 5 chunks pass review:

1. Hand off to **superpowers:subagent-driven-development** for execution.
2. The terminal state of this plan is:
   - `apps/site/src/content/contributors/` populated with ~12-13 contributor MDs (one per unique opinion-piece bio writer + migrated shivani).
   - `apps/site/public/contributors/photos/` populated with ~10-13 photo files.
   - `/contributors/<slug>/` detail page + `/contributors/` index page rendered.
   - Every opinion with a bio block has `author: <slug>` + the bio block stripped from the body.
   - The opinion detail page shows a "Written by" card for opinions whose `author:` resolves.
   - `shivani-a-tannu` is in `/contributors/`, not `/thinkers/`, and the authority file is scrubbed.
