#!/usr/bin/env python3
"""
audit-cross-refs.py — read-only audit of slug ↔ prose drift in new MDs.

For each primary-works MD added since the pre-extension SHA (b6be9fe), surface:
  - Slugs in related_thinkers whose canonical name (or any also_known_as) doesn't
    appear in summary/key_points (possible AI hallucination).
  - Canonical thinker names (or also_known_as) appearing in summary/key_points
    that are missing from related_thinkers (possible missed structured tag).

Reads:
  apps/site/src/content/primary-works/*.md  (filtered to "new since BASELINE_SHA")
  apps/site/src/content/thinkers/*.md       (slug → name forms lookup)

Writes:
  stdout report (captured into docs/handoffs/2026-05-27-content-readiness-pass-1.md).

Run:
  .venv-extract/bin/python3 scripts/synthesis/audit-cross-refs.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PW_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "primary-works"
THINKERS_DIR = REPO_ROOT / "apps" / "site" / "src" / "content" / "thinkers"
BASELINE_SHA = "b6be9fe"  # pre-extension; "new MDs" = added between this and HEAD

_FM_RX = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


@dataclass
class ThinkerInfo:
    slug: str
    canonical: str
    also_known_as: list[str] = field(default_factory=list)


@dataclass
class Discrepancy:
    md_slug: str
    slugs_not_in_prose: list[str] = field(default_factory=list)
    names_not_in_slugs: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.slugs_not_in_prose and not self.names_not_in_slugs


def _load_thinker_index(thinkers_dir: Path) -> dict[str, ThinkerInfo]:
    """Return slug → ThinkerInfo for every thinker MD in the dir."""
    index: dict[str, ThinkerInfo] = {}
    for md in sorted(thinkers_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        m = _FM_RX.match(text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        slug = fm.get("id") or md.stem
        name_block = fm.get("name") or {}
        canonical = (name_block.get("canonical") or "").strip()
        also = name_block.get("also_known_as") or []
        if not isinstance(also, list):
            also = []
        also = [a.strip() for a in also if isinstance(a, str) and a.strip()]
        if not canonical:
            continue
        index[slug] = ThinkerInfo(slug=slug, canonical=canonical, also_known_as=also)
    return index


def _find_name_in_text(name: str, text: str) -> bool:
    """Whole-word, case-insensitive substring match for `name` in `text`.

    Whole-word here means the name boundaries are non-word characters (or string start/end).
    Multi-token names match exactly as-written (case-insensitive); collapse to a regex.
    """
    if not name or not text:
        return False
    pattern = r"\b" + re.escape(name) + r"\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _find_thinker_in_text(thinker: ThinkerInfo, text: str) -> bool:
    """True if ANY of the thinker's name forms appears in text."""
    forms = [thinker.canonical] + thinker.also_known_as
    return any(_find_name_in_text(f, text) for f in forms)


def _check_md(md_path: Path, thinker_index: dict[str, ThinkerInfo]) -> Discrepancy:
    """Return a Discrepancy for one MD."""
    text = md_path.read_text(encoding="utf-8")
    m = _FM_RX.match(text)
    md_slug = md_path.stem
    if not m:
        return Discrepancy(md_slug=md_slug)
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return Discrepancy(md_slug=md_slug)

    related = fm.get("related_thinkers") or []
    if not isinstance(related, list):
        related = []
    related = [s for s in related if isinstance(s, str)]

    # The prose surface we check: summary + key_points lines from the body.
    summary = fm.get("summary") or ""
    body = m.group(2) or ""
    key_points_body = ""
    # Pull the "## Key points" section from the body, if present.
    kp_match = re.search(r"^##\s*Key points\s*$(.+?)(?=^##\s|\Z)", body, re.M | re.S)
    if kp_match:
        key_points_body = kp_match.group(1)
    prose = (summary + "\n" + key_points_body).strip()

    # 1. Slugs in related_thinkers but not in prose
    slugs_not_in_prose: list[str] = []
    for slug in related:
        info = thinker_index.get(slug)
        if info is None:
            # Slug doesn't resolve to a thinker file — separate concern (Stream B)
            continue
        if not _find_thinker_in_text(info, prose):
            slugs_not_in_prose.append(slug)

    # 2. Thinker names in prose but not in related_thinkers
    related_set = set(related)
    names_not_in_slugs: list[str] = []
    for slug, info in thinker_index.items():
        if slug in related_set:
            continue
        if _find_thinker_in_text(info, prose):
            names_not_in_slugs.append(info.canonical)

    return Discrepancy(
        md_slug=md_slug,
        slugs_not_in_prose=slugs_not_in_prose,
        names_not_in_slugs=names_not_in_slugs,
    )


def _new_mds_since(baseline_sha: str) -> list[Path]:
    """Return paths of primary-works MDs added since baseline_sha."""
    result = subprocess.run(
        ["git", "log", f"--diff-filter=A", "--name-only", "--pretty=format:",
         f"{baseline_sha}..HEAD", "--", str(PW_DIR)],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    paths = []
    seen = set()
    for line in result.stdout.split("\n"):
        line = line.strip()
        if not line or not line.endswith(".md"):
            continue
        if line in seen:
            continue
        seen.add(line)
        p = REPO_ROOT / line
        if p.exists():
            paths.append(p)
    return paths


def main() -> int:
    thinker_index = _load_thinker_index(THINKERS_DIR)
    new_mds = _new_mds_since(BASELINE_SHA)

    print(f"=== Cross-reference discrepancies — new MDs since {BASELINE_SHA} ===")
    print(f"Total new MDs scanned: {len(new_mds)}")
    print(f"Thinker index size: {len(thinker_index)}")
    print()

    discrepancies = []
    for md in sorted(new_mds):
        d = _check_md(md, thinker_index)
        if not d.is_empty():
            discrepancies.append(d)

    print(f"MDs with discrepancies: {len(discrepancies)}")
    print()

    for d in discrepancies:
        print(f"--- {d.md_slug} ---")
        if d.slugs_not_in_prose:
            print("Slugs in related_thinkers but not mentioned in prose:")
            for slug in d.slugs_not_in_prose:
                canon = thinker_index[slug].canonical
                print(f"  - {slug} (canonical name \"{canon}\" not found in summary/key_points)")
        if d.names_not_in_slugs:
            print("Names in prose but not in related_thinkers:")
            for name in d.names_not_in_slugs:
                print(f"  - \"{name}\" appears in summary/key_points; slug missing from related_thinkers")
        print()

    print("=== Summary ===")
    sn = sum(len(d.slugs_not_in_prose) for d in discrepancies)
    ns = sum(len(d.names_not_in_slugs) for d in discrepancies)
    print(f"slugs-not-in-prose: {sn} total across {sum(1 for d in discrepancies if d.slugs_not_in_prose)} MDs")
    print(f"names-not-in-slugs: {ns} total across {sum(1 for d in discrepancies if d.names_not_in_slugs)} MDs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
