# scripts/synthesis/tests/test_apply_pdf_urls.py
"""Tests for apply-pdf-urls frontmatter mutator."""
from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "apply_pdf_urls",
    str(Path(__file__).resolve().parents[1] / "apply-pdf-urls.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


SAMPLE_MD = """---
id: sample
title:
  main: Sample Work
work_type: speech
publication:
  language: en
  year: 1980
provenance:
  source: ccs_archive
  scan_quality: unknown
rights:
  status: takedown_on_request
themes: []
---

# Body
"""


def test_insert_pdf_url_after_provenance():
    out, status = mod.insert_pdf_url(SAMPLE_MD, "https://example.com/x.pdf", force=False)
    assert status == "inserted"
    # The new line lives after the provenance block, before rights:
    lines = out.split("\n")
    prov_idx = lines.index("provenance:")
    rights_idx = lines.index("rights:")
    inserted_idx = next(i for i, l in enumerate(lines) if l.startswith("pdf_url:"))
    assert prov_idx < inserted_idx < rights_idx


def test_insert_preserves_body_byte_for_byte():
    out, _ = mod.insert_pdf_url(SAMPLE_MD, "https://example.com/x.pdf", force=False)
    # Body after second --- must equal the original body.
    assert out.split("---\n", 2)[2] == SAMPLE_MD.split("---\n", 2)[2]


def test_skips_when_pdf_url_already_present():
    md_with_pdf = SAMPLE_MD.replace(
        "themes: []\n",
        "themes: []\npdf_url: https://old.example.com/old.pdf\n",
    )
    out, status = mod.insert_pdf_url(md_with_pdf, "https://new.example.com/new.pdf", force=False)
    assert status == "skip-existing"
    assert "old.example.com/old.pdf" in out
    assert "new.example.com/new.pdf" not in out


def test_force_overwrites_existing():
    md_with_pdf = SAMPLE_MD.replace(
        "themes: []\n",
        "themes: []\npdf_url: https://old.example.com/old.pdf\n",
    )
    out, status = mod.insert_pdf_url(md_with_pdf, "https://new.example.com/new.pdf", force=True)
    assert status == "replaced"
    assert "new.example.com/new.pdf" in out
    assert "old.example.com/old.pdf" not in out


def test_no_frontmatter_returns_skip():
    out, status = mod.insert_pdf_url("no frontmatter here\n", "https://x/y.pdf", force=False)
    assert status == "skip-no-frontmatter"
    assert out == "no frontmatter here\n"


SAMPLE_MD_NO_PROVENANCE = """---
id: sample
title:
  main: Sample Work
work_type: speech
publication:
  language: en
  year: 1980
rights:
  status: takedown_on_request
themes: []
---

# Body
"""


def test_fallback_appends_when_no_provenance_block():
    out, status = mod.insert_pdf_url(SAMPLE_MD_NO_PROVENANCE, "https://example.com/x.pdf", force=False)
    assert status == "inserted"
    # pdf_url must be INSIDE the frontmatter (before the closing ---)
    fm_part = out.split("---\n", 2)[1]
    assert "pdf_url: https://example.com/x.pdf" in fm_part
    # And at column 0 (root level, not indented)
    lines = out.split("\n")
    inserted = next(l for l in lines if l.startswith("pdf_url:"))
    assert inserted == "pdf_url: https://example.com/x.pdf"
    # Body still byte-equal to original
    assert out.split("---\n", 2)[2] == SAMPLE_MD_NO_PROVENANCE.split("---\n", 2)[2]
