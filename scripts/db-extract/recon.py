"""
Reconnaissance: cross-tab content posts × categories/taxonomies to plan
the extraction. Reports what we'll get per collection.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dump_parser import iter_rows  # noqa: E402

DB_DIR = Path("/Volumes/One Touch/Indian Liberals/sql")
V3 = DB_DIR / "indianli_indianv3.sql"
LIB = DB_DIR / "indianli_liberals.sql"


def recon_v3() -> None:
    print("=" * 72)
    print("Current WP database (indianli_indianv3.sql)")
    print("=" * 72)

    # 1. Term taxonomies
    taxonomies: dict[int, tuple[str, str, str]] = {}  # tt_id -> (taxonomy, term_name, term_slug)
    terms = {r["term_id"]: r for r in iter_rows(V3, "il_terms")}
    for tt in iter_rows(V3, "il_term_taxonomy"):
        t = terms.get(tt["term_id"])
        if t:
            taxonomies[tt["term_taxonomy_id"]] = (tt["taxonomy"], t["name"], t["slug"])

    tax_groups: Counter = Counter()
    for tax, _, _ in taxonomies.values():
        tax_groups[tax] += 1
    print(f"\nTaxonomies ({len(tax_groups)}):")
    for tax, n in tax_groups.most_common():
        print(f"  {tax}: {n} terms")

    # 2. il_term_relationships: object_id (post) -> term_taxonomy_id
    post_terms: dict[int, list[int]] = defaultdict(list)
    for tr in iter_rows(V3, "il_term_relationships"):
        post_terms[tr["object_id"]].append(tr["term_taxonomy_id"])

    # 3. Load posts of interest
    interesting_types = {"content", "indian_liberals", "print", "page"}
    posts_by_type: dict[str, list[dict]] = defaultdict(list)
    for p in iter_rows(V3, "il_posts"):
        if p["post_status"] != "publish":
            continue
        if p["post_type"] in interesting_types:
            posts_by_type[p["post_type"]].append(p)

    print(f"\nPublished posts by type:")
    for t, rows in sorted(posts_by_type.items(), key=lambda x: -len(x[1])):
        print(f"  {t}: {len(rows)}")

    # 4. For each content row, count category memberships per taxonomy
    print(f"\n--- 'content' post-type x taxonomy histograms ---")
    by_tax: dict[str, Counter] = defaultdict(Counter)
    posts_with_no_tax: Counter = Counter()
    for p in posts_by_type.get("content", []):
        cats = post_terms.get(p["ID"], [])
        seen_tax: set[str] = set()
        for tt_id in cats:
            tax_info = taxonomies.get(tt_id)
            if tax_info and tax_info[0] in ("content_category", "content_tag", "content_letter", "language", "term_language"):
                by_tax[tax_info[0]][tax_info[2]] += 1
                seen_tax.add(tax_info[0])
        for missing in {"content_category", "content_letter", "language"} - seen_tax:
            posts_with_no_tax[missing] += 1
    for tax_name, ctr in by_tax.items():
        print(f"\n  --- {tax_name} ({len(ctr)} terms used) ---")
        for cat, n in ctr.most_common(20):
            print(f"    {cat}: {n}")
    print(f"\n  Posts missing taxonomies: {dict(posts_with_no_tax)}")

    # 5. Sample post_names per category to verify mapping
    print(f"\n--- Sample post_names per top category ---")
    samples_by_cat: dict[str, list[str]] = defaultdict(list)
    for p in posts_by_type.get("content", []):
        cats = post_terms.get(p["ID"], [])
        for tt_id in cats:
            tax_info = taxonomies.get(tt_id)
            if tax_info and tax_info[0] in ("content_category", "content_tag", "content_letter"):
                slug = tax_info[2]
                if len(samples_by_cat[slug]) < 3:
                    samples_by_cat[slug].append(p["post_name"])
    for cat in [c for c, _ in cat_counter.most_common(15)]:
        print(f"  {cat}: {samples_by_cat[cat]}")

    # 6. Attachment file paths via il_postmeta._wp_attached_file
    print(f"\n--- Attachments by extension ---")
    ext_counter: Counter = Counter()
    attachments_by_post: dict[int, str] = {}
    for pm in iter_rows(V3, "il_postmeta"):
        if pm["meta_key"] == "_wp_attached_file":
            path = pm["meta_value"]
            if isinstance(path, str) and "." in path:
                ext_counter[path.rsplit(".", 1)[-1].lower()] += 1
                attachments_by_post[pm["post_id"]] = path
    for ext, n in ext_counter.most_common():
        print(f"  .{ext}: {n}")

    # 7. Authors
    print(f"\n--- Authors ---")
    users = {r["ID"]: r for r in iter_rows(V3, "il_users")}
    author_counter: Counter = Counter()
    for p in posts_by_type.get("content", []):
        author_id = p["post_author"]
        u = users.get(author_id)
        author_counter[u["user_login"] if u else f"user_{author_id}"] += 1
    print(f"  Distinct authors: {len(author_counter)}")
    for u, n in author_counter.most_common(10):
        print(f"  {u}: {n}")


def recon_liberals() -> None:
    print("\n" + "=" * 72)
    print("Mid-era WP database (indianli_liberals.sql)")
    print("=" * 72)
    # tbl_languages_details count + total OCR pages
    details = list(iter_rows(LIB, "tbl_languages_details"))
    print(f"\ntbl_languages_details: {len(details)} books")
    page_counter: Counter = Counter()
    for r in iter_rows(LIB, "tbl_languages_content"):
        page_counter[r["langpdfid"]] += 1
    total_pages = sum(page_counter.values())
    print(f"OCR pages total: {total_pages}")
    print(f"  Books with OCR: {len(page_counter)}")
    print(f"  Pages per book (sample): {sorted(page_counter.values(), reverse=True)[:10]}")
    # Sample a few details
    print(f"\nSample tbl_languages_details:")
    for d in details[:5]:
        print(
            f"  id={d['id']} lang={d['languageid']} pdf={d['pdf_file']!r} title={d['title'][:50]!r} author={d['author'][:30]!r}"
        )
    # tbl_languages master
    print(f"\ntbl_languages (language master):")
    for r in iter_rows(LIB, "tbl_languages"):
        print(f"  id={r['id']} name={r['name']!r}")
    # wp_book
    print(f"\nwp_book rows:")
    books = list(iter_rows(LIB, "wp_book"))
    print(f"  Total: {len(books)}")
    for b in books[:5]:
        print(f"  id={b['id']} title={b['title'][:50]!r} pdf={b['pdf_file']!r}")


if __name__ == "__main__":
    recon_v3()
    recon_liberals()
