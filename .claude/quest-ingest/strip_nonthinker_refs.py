#!/usr/bin/env python3
"""Drop `related_thinkers` entries that are not thinker pages.

`related_thinkers` is `z.array(reference('thinkers'))`, and the emitter's
cross-mention resolution can land an ORGANISATION id in it: QT051 resolved
"Indian National Congress" there, which is a real organisation page and not a
thinker. `npm run build` runs check-references.mjs BEFORE astro build, that
script calls a dangling reference an error, and one error blocks the deploy for
the entire site — which is exactly what QT051 did.

There is no related_organisations field on primary-works, so the mention stays
in the prose and the structured link is dropped rather than moved.

Usage: strip_nonthinker_refs.py <slug> [...]        # default: every Quest work
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2] / "apps/site/src/content"
WORKS = ROOT / "primary-works"
FM = re.compile(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$")


def main() -> int:
    thinkers = {p.stem for p in (ROOT / "thinkers").glob("*.md")}
    orgs = {p.stem for p in (ROOT / "organisations").glob("*.md")}
    slugs = [a.lower() for a in sys.argv[1:] if not a.startswith("--")]
    files = ([WORKS / f"{s}.md" for s in slugs] if slugs
             else sorted(WORKS.glob("qt[0-9][0-9][0-9].md")))
    changed = 0
    for p in files:
        m = FM.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = yaml.safe_load(m.group(1))
        rt = fm.get("related_thinkers") or []
        drop = [r for r in rt if r not in thinkers]
        if not drop:
            continue
        kind = ", ".join(f"{d} ({'organisation' if d in orgs else 'unknown id'})" for d in drop)
        fm["related_thinkers"] = [r for r in rt if r in thinkers]
        out = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                             default_flow_style=False, width=100000)
        text = f"---\n{out}---\n{m.group(2)}"
        yaml.safe_load(FM.match(text).group(1))      # parse before writing
        p.write_text(text, encoding="utf-8")
        print(f"{p.stem}: dropped {kind}")
        changed += 1
    print(f"{changed} work(s) corrected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
