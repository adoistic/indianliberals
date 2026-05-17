"""
Read the 4 `indian_liberals` + 3 `print` post-type entries from the WP DB
that the earlier extraction (extract_content.py) filtered out, and decide
whether to absorb them into existing collections.

Output: data/corpus-inventory.json gets a section for these so we have a
single canonical record of what's there + what we're going to do with each.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dump_parser import iter_rows  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
V3 = Path("/Volumes/One Touch/Indian Liberals/sql/indianli_indianv3.sql")


def main() -> None:
    interesting = []
    for p in iter_rows(V3, "il_posts"):
        if p["post_status"] != "publish":
            continue
        if p["post_type"] not in {"indian_liberals", "print"}:
            continue
        interesting.append(
            {
                "ID": p["ID"],
                "post_type": p["post_type"],
                "post_name": p["post_name"],
                "post_title": p["post_title"],
                "post_date": str(p["post_date"]),
                "content_length": len(p.get("post_content") or ""),
                "content_preview": re.sub(r"\s+", " ", (p.get("post_content") or ""))[:500],
                "guid": p["guid"],
            }
        )

    print(f"Found {len(interesting)} entries across indian_liberals + print post types\n")
    for e in interesting:
        print(f"--- {e['post_type']} / ID={e['ID']} / slug={e['post_name']} ---")
        print(f"   Title:   {e['post_title']}")
        print(f"   Date:    {e['post_date']}")
        print(f"   Length:  {e['content_length']} chars")
        print(f"   Preview: {e['content_preview'][:300]}...")
        print()

    out = REPO / "data/corpus-inventory" / "custom_post_types.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "_meta": {
                    "purpose": (
                        "WP DB custom post types that the initial extract_content.py "
                        "filter (post_type='content') skipped. Read here, decide whether "
                        "to absorb into existing collections, fold into a new collection, "
                        "or drop."
                    ),
                    "count": len(interesting),
                },
                "entries": interesting,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
