#!/usr/bin/env python3
"""Catch bylines that an alias resolved to the wrong person.

THE PROBLEM
emit-astro-md.py resolves `byline_verbatim` against each authority entry's
canonical name AND its `also_known_as` aliases. 58 of those aliases are single
tokens ("Nehru", "Marx", "Rajaji", "Indira", "Gandhi"). That is correct and
wanted for CROSS-THINKER MENTIONS — it is how the corpus's prose names people —
but a BYLINE carries far less context than a sentence, so the same alias can
attribute authorship to the wrong person.

It already happened: Quest QT011 carries a Marathi poem bylined simply
"Indira". The authority file lists "Indira" as an alias of Indira Gandhi, so she
was credited as the SOLE AUTHOR of Quest's Marathi Literature special issue.
The issue's own contributor note names no one, calling the poet only "an
unmatched lyricist, writing with subdued melancholy".

THE RULE
A single-token byline is demoted to `thinker_unresolved` when that token is the
person's GIVEN name (the first word of their canonical name). It is KEPT when
the token is their surname or a distinct byname, because those genuinely
identify one person in this corpus:
    "Masani"  -> minoo-masani          surname            KEEP
    "Rajaji"  -> c-rajagopalachari     byname             KEEP
    "Nehru"   -> jawaharlal-nehru      surname            KEEP
    "S.V.Raju"-> s-v-raju              full name, no gaps KEEP
    "Indira"  -> indira-gandhi         GIVEN NAME         DEMOTE
Initials are expanded before counting tokens, so "S.V.Raju" is not mistaken for
a mononym. Multi-word bylines are never touched.

Removing the aliases themselves would be the wrong fix: it would break mention
resolution corpus-wide, where they are doing their job.

Usage:
    guard-byline-aliases.py --audit              # whole corpus, report only
    guard-byline-aliases.py --fix <slug> [...]   # rewrite those works
"""
import json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKS = REPO / "apps/site/src/content/primary-works"
BAKE = REPO / "data/bake-off-output"

auth = json.loads((REPO / "data/authority/thinkers.json").read_text(encoding="utf-8"))
PEOPLE = {t["id"]: t["name"]["canonical"] for t in auth["thinkers"]}


def byline_tokens(byline: str) -> list[str]:
    """Words in a byline, with run-together initials split out.

    "S.V.Raju" -> ["S", "V", "Raju"], so a full name written without spaces is
    not mistaken for a bare mononym.
    """
    s = re.sub(r"([A-Z])\.", r"\1 ", byline or "")
    return [w for w in re.split(r"[\s.]+", s) if w]


def should_demote(byline: str, tid: str) -> bool:
    toks = byline_tokens(byline)
    if len(toks) != 1:
        return False
    canon = PEOPLE.get(tid)
    if not canon:
        return False
    ctoks = canon.split()
    if len(ctoks) < 2:
        return False                      # genuinely mononymous authority entry
    return toks[0].lower() == ctoks[0].lower().strip(".")


def source_bylines(slug: str) -> list[str] | None:
    d = BAKE / slug
    for c in ("metadata.a.json", "metadata.b.json", "metadata.a.a.json"):
        if (d / c).exists():
            try:
                meta = json.loads((d / c).read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
            return [(x.get("byline_verbatim") or "") for x in (meta.get("contributors") or [])
                    if isinstance(x, dict)]
    return None


def scan(slug: str, fix: bool) -> list[tuple[str, str]]:
    md = WORKS / f"{slug.lower()}.md"
    bylines = source_bylines(slug)
    if not md.exists() or bylines is None:
        return []
    lines = md.read_text(encoding="utf-8").split("\n")
    start = next((i for i, l in enumerate(lines) if l == "contributors:"), None)
    if start is None:
        return []
    end = start + 1
    while end < len(lines) and (lines[end].startswith("  ") or lines[end] == ""):
        end += 1

    found, n = [], -1
    for i in range(start + 1, end):
        if re.match(r"^  - role:", lines[i]):
            n += 1
        m = re.match(r"^(\s+)thinker: (\S+)\s*$", lines[i])
        if m and 0 <= n < len(bylines):
            by = bylines[n].strip()
            if should_demote(by, m.group(2)):
                found.append((by, m.group(2)))
                if fix:
                    lines[i] = f"{m.group(1)}thinker_unresolved: {by}"
    if fix and found:
        text = "\n".join(lines)
        for _, tid in found:
            if f"thinker: {tid}" not in text:
                text = re.sub(rf"^  - {re.escape(tid)}\s*$\n", "", text, flags=re.M)
        text = re.sub(r"^(authors|editors|related_thinkers):\s*$(?!\n\s+-)", r"\1: []",
                      text, flags=re.M)
        md.write_text(text, encoding="utf-8")
    return found


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args[0] == "--audit":
        slugs = sorted(p.name for p in BAKE.iterdir() if p.is_dir())
        total = 0
        for s in slugs:
            for by, tid in scan(s, fix=False):
                print(f'  {s}: byline "{by}" -> {tid} ({PEOPLE[tid]})')
                total += 1
        print(f"\naudited {len(slugs)} works with source metadata; "
              f"{total} given-name byline match(es) to demote")
    elif args[0] == "--fix":
        for s in args[1:]:
            got = scan(s, fix=True)
            print(f"{s}: " + (", ".join(f'demoted "{b}" (was {t})' for b, t in got)
                              if got else "nothing to demote"))
