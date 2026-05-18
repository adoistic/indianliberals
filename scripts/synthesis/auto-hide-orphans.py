#!/usr/bin/env python3
"""Hide thinkers and organisations with zero inbound reference material.
Mechanism: set `draft: true` in the entry's frontmatter.

A thinker has reference material if ANY of:
  - any work's authors[] or contributors[].thinker matches their slug
  - any musing/opinion/theprint/interview has them as author or subject
  - any entry has them in related_thinkers[] or thinker_mentions[]

An organisation has reference material if ANY of:
  - any primary-work has publisher_id/issuer_id matching the org slug
  - any thinker has affiliations[] containing the org slug

If draft was previously true but the entity now has refs (e.g., Phase B
backfill), this script FLIPS it back to false. Idempotent.
"""
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path('/Users/siraj/Indian Liberals Website')
CONTENT = ROOT / 'apps/site/src/content'

THINKERS_DIR = CONTENT / 'thinkers'
ORGS_DIR = CONTENT / 'organisations'

# Build reference indexes
thinker_refs = defaultdict(int)  # slug → ref count
org_refs = defaultdict(int)

# Walk all content collections to count thinker refs
for collection in ['musings', 'opinions', 'theprint-mirror', 'primary-works', 'interviews']:
    cdir = CONTENT / collection
    if not cdir.exists(): continue
    for p in cdir.glob('*.md'):
        text = p.read_text()
        # author / subject / thinker: "slug"
        for m in re.finditer(r'(?:^|\s)(?:author|subject|thinker)\s*:\s*"?([a-z][a-z0-9-]*)"?(?:\s|$)', text):
            thinker_refs[m.group(1)] += 1
        # authors[], contributors[].thinker, related_thinkers[]
        for sec_m in re.finditer(
            r'^(authors|contributors|related_thinkers|editors):\s*\n((?:\s+-\s.*\n)+)',
            text, re.M
        ):
            for slug_m in re.finditer(r'-\s+(?:thinker\s*:\s*)?"?([a-z][a-z0-9-]+)"?', sec_m.group(2)):
                slug = slug_m.group(1)
                if slug not in ('author', 'editor', 'translator', 'foreword', 'introduction'):
                    thinker_refs[slug] += 1
        # thinker_mentions[].thinker
        for m in re.finditer(r'^\s+-\s+thinker:\s*"?([a-z][a-z0-9-]+)"?', text, re.M):
            thinker_refs[m.group(1)] += 1

# Org refs: publisher_id / issuer_id in primary-works
for p in (CONTENT / 'primary-works').glob('*.md'):
    text = p.read_text()
    for m in re.finditer(r'(?:publisher_id|issuer_id):\s*([a-z][a-z0-9-]*)', text):
        org_refs[m.group(1)] += 1

# Org refs: affiliations[] in thinkers
for p in THINKERS_DIR.glob('*.md'):
    text = p.read_text()
    # inline: affiliations: ["slug"]
    for m in re.finditer(r'affiliations:\s*\[([^\]]+)\]', text):
        for slug_m in re.finditer(r'"([a-z][a-z0-9-]+)"', m.group(1)):
            org_refs[slug_m.group(1)] += 1
    # list form: affiliations:\n  - slug
    for m in re.finditer(r'^affiliations:\s*\n((?:\s+-\s.*\n)+)', text, re.M):
        for slug_m in re.finditer(r'-\s+"?([a-z][a-z0-9-]+)"?', m.group(1)):
            org_refs[slug_m.group(1)] += 1


def set_draft_flag(p: Path, should_be_draft: bool) -> str | None:
    """Update the `draft:` field in the frontmatter. Returns 'hid', 'unhid',
    or None if no change."""
    text = p.read_text()
    m = re.search(r'^(draft:\s*)(true|false)$', text, re.M)
    if not m:
        return None
    current = m.group(2) == 'true'
    if current == should_be_draft:
        return None
    new_value = 'true' if should_be_draft else 'false'
    new_text = re.sub(r'^draft:\s*(true|false)$', f'draft: {new_value}', text, count=1, flags=re.M)
    p.write_text(new_text, encoding='utf-8')
    return 'hid' if should_be_draft else 'unhid'


# Process thinkers
hidden_thinkers = []
unhidden_thinkers = []
for p in sorted(THINKERS_DIR.glob('*.md')):
    slug = p.stem
    has_refs = thinker_refs.get(slug, 0) > 0
    result = set_draft_flag(p, should_be_draft=not has_refs)
    if result == 'hid':
        hidden_thinkers.append(slug)
    elif result == 'unhid':
        unhidden_thinkers.append(slug)

# Process orgs
hidden_orgs = []
unhidden_orgs = []
for p in sorted(ORGS_DIR.glob('*.md')):
    slug = p.stem
    has_refs = org_refs.get(slug, 0) > 0
    result = set_draft_flag(p, should_be_draft=not has_refs)
    if result == 'hid':
        hidden_orgs.append(slug)
    elif result == 'unhid':
        unhidden_orgs.append(slug)

print(f'=== Thinkers ===')
print(f'  Total: {len(list(THINKERS_DIR.glob("*.md")))}')
print(f'  Now hidden (no refs): {len(hidden_thinkers)}')
print(f'  Newly un-hidden:       {len(unhidden_thinkers)}')
print()
print(f'=== Organisations ===')
print(f'  Total: {len(list(ORGS_DIR.glob("*.md")))}')
print(f'  Now hidden (no refs): {len(hidden_orgs)}')
print(f'  Newly un-hidden:       {len(unhidden_orgs)}')
print()
if hidden_thinkers:
    print(f'Hidden thinkers (sample 10): {hidden_thinkers[:10]}')
if hidden_orgs:
    print(f'Hidden orgs (sample 10): {hidden_orgs[:10]}')
if unhidden_orgs:
    print(f'Un-hidden orgs: {unhidden_orgs}')
