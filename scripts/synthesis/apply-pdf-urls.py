#!/usr/bin/env python3
"""
apply-pdf-urls.py — write pdf_url into primary-works MDs from approved manifest.

Reads:
    data/pdf-link-manifest.tsv (or --manifest <path>)

Writes:
    apps/site/src/content/primary-works/<md_slug>.md (mutated frontmatter)

Run:
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --dry-run
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --only-confidence exact,high
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py            # apply all by default
    .venv-extract/bin/python3 scripts/synthesis/apply-pdf-urls.py --force    # overwrite existing pdf_url

Per the spec at docs/superpowers/specs/2026-05-26-pdf-link-reconciliation-design.md.
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"

_FRONTMATTER_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
_PDF_URL_LINE_RX = re.compile(r"^pdf_url:\s*.*$", re.M)
_PROVENANCE_BLOCK_END_RX = re.compile(
    r"^(provenance:\n(?:[ \t]+.*\n)+)",  # provenance: followed by 1+ indented lines
    re.M,
)


def insert_pdf_url(text: str, pdf_url: str, *, force: bool) -> tuple[str, str]:
    """Return (new_text, status).

    Status values:
      "inserted"           — new pdf_url line added.
      "replaced"           — existing pdf_url line overwritten (force=True only).
      "skip-existing"      — pdf_url already present; force=False.
      "skip-no-frontmatter"— no frontmatter regex match.
    """
    m = _FRONTMATTER_RX.match(text)
    if not m:
        return text, "skip-no-frontmatter"

    fm, body = m.group(1), m.group(2)
    has_pdf = _PDF_URL_LINE_RX.search(fm) is not None

    if has_pdf and not force:
        return text, "skip-existing"

    new_line = f"pdf_url: {pdf_url}"

    if has_pdf:
        # Replace existing line.
        new_fm = _PDF_URL_LINE_RX.sub(new_line, fm, count=1)
        return f"---\n{new_fm}\n---\n{body}", "replaced"

    # Insert after the provenance: block. If the provenance block isn't found
    # (defensive fallback), append at end of frontmatter.
    pm = _PROVENANCE_BLOCK_END_RX.search(fm)
    if pm:
        insert_at = pm.end()  # position right after the provenance block
        new_fm = fm[:insert_at] + new_line + "\n" + fm[insert_at:]
    else:
        # Fallback: append at end of frontmatter (before the closing ---).
        new_fm = fm.rstrip("\n") + "\n" + new_line

    return f"---\n{new_fm}\n---\n{body}", "inserted"


def load_manifest(path: Path, accepted: set[str]) -> list[dict]:
    """Read a TSV manifest. accepted = set of confidence labels to apply."""
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if row.get("confidence") not in accepted:
                continue
            if not row.get("pdf_url"):
                continue  # don't apply rows with no URL
            if "DUPLICATE" in (row.get("notes") or ""):
                continue
            rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(REPO_ROOT / "data" / "pdf-link-manifest.tsv"))
    ap.add_argument(
        "--only-confidence",
        default="exact,high,medium",
        help="Comma-separated confidence labels to apply (default: exact,high,medium).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print diff per MD; don't write.")
    ap.add_argument("--force", action="store_true", help="Overwrite existing pdf_url.")
    ap.add_argument("--no-commit", action="store_true", help="Don't auto-commit after writes.")
    args = ap.parse_args()

    accepted = {s.strip() for s in args.only_confidence.split(",") if s.strip()}
    rows = load_manifest(Path(args.manifest), accepted)
    print(f"applying {len(rows)} rows ({sorted(accepted)})")

    statuses: dict[str, int] = {}
    touched: list[Path] = []

    for row in rows:
        slug = row["md_slug"]
        pdf_url = row["pdf_url"]
        md_path = PW_DIR / f"{slug}.md"
        if not md_path.exists():
            print(f"  [missing] {md_path}", file=sys.stderr)
            statuses["missing"] = statuses.get("missing", 0) + 1
            continue

        text = md_path.read_text(encoding="utf-8")
        new_text, status = insert_pdf_url(text, pdf_url, force=args.force)
        statuses[status] = statuses.get(status, 0) + 1

        if status in ("inserted", "replaced"):
            if args.dry_run:
                # Tiny visible diff:
                old_line = next((l for l in text.split("\n") if l.startswith("pdf_url:")), "(none)")
                new_line = next((l for l in new_text.split("\n") if l.startswith("pdf_url:")), "(none)")
                print(f"  [{status}] {slug}: {old_line} → {new_line}")
            else:
                md_path.write_text(new_text, encoding="utf-8")
                touched.append(md_path)

    print()
    print("statuses:")
    for k, v in sorted(statuses.items()):
        print(f"  {k}: {v}")

    if not args.dry_run and touched and not args.no_commit:
        # Stage + commit.
        subprocess.run(["git", "add", "--"] + [str(p) for p in touched], check=True, cwd=REPO_ROOT)
        n = len(touched)
        breakdown = ", ".join(f"{statuses.get(k, 0)} {k}" for k in ("inserted", "replaced") if statuses.get(k))
        commit_msg = (
            f"data(primary-works): populate pdf_url from prod indianliberals.in (N={n})\n\n"
            f"Tier breakdown: {breakdown}.\n"
            f"Source: data/prod-mirror (cached scrape).\n\n"
            f"Transitional; will be replaced by R2-hosted URLs in a future spec\n"
            f"per the pdf_staging_path / pdf_size_mb schema fields."
        )
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=REPO_ROOT)
        print(f"committed {n} MDs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
