"""Unit tests for migrate-interviews-to-primary-works.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _load(stem: str):
    mod_name = stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(
        mod_name,
        str(SCRIPTS_DIR / f"{stem}.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve cls.__module__ in Python 3.14
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


migrate = _load("migrate-interviews-to-primary-works")


# -------- parse_frontmatter tests --------


def test_parse_frontmatter_extracts_dict_and_body():
    md = "---\nid: foo\ntitle: Bar\n---\nbody text here\n"
    fm, body = migrate.parse_frontmatter(md)
    assert fm == {"id": "foo", "title": "Bar"}
    assert body == "body text here\n"


def test_parse_frontmatter_returns_empty_on_no_frontmatter():
    md = "no frontmatter here, just body"
    fm, body = migrate.parse_frontmatter(md)
    assert fm == {}
    assert body == md


# -------- extract_year_from_pubdate tests --------


def test_pubdate_year_extraction():
    assert migrate.extract_year_from_pubdate("2020-11-05T04:29:04Z") == 2020


def test_pubdate_year_extraction_returns_none_on_garbage():
    assert migrate.extract_year_from_pubdate("not-a-date") is None
    assert migrate.extract_year_from_pubdate(None) is None
    assert migrate.extract_year_from_pubdate("") is None


# -------- strip_wp_garbage_body tests --------


def test_wp_garbage_body_returns_none():
    """A body matching only the WP migration tail returns None (no description)."""
    body = "\n\ntype=content&#038;p=1773). Needs editorial review._"
    assert migrate.strip_wp_garbage_body(body) is None


def test_editorial_paragraph_preserved():
    """A real editorial paragraph survives the strip."""
    body = "Begum Rokeya was a major Bengali liberal figure. " * 4
    cleaned = migrate.strip_wp_garbage_body(body)
    assert cleaned is not None
    assert "Begum Rokeya" in cleaned


def test_editorial_paragraph_with_wp_tail():
    """Real paragraph plus WP tail → paragraph survives, tail stripped."""
    body = (
        "Begum Rokeya was a major Bengali liberal figure. "
        "She wrote Sultana's Dream. " * 3
        + "\ntype=content&#038;p=1773). Needs editorial review._"
    )
    cleaned = migrate.strip_wp_garbage_body(body)
    assert cleaned is not None
    assert "Begum Rokeya" in cleaned
    assert "type=content" not in cleaned
    assert "Needs editorial review" not in cleaned


# -------- classify_transcript_status tests --------


def test_classify_transcript_status_complete(tmp_path):
    """A real cleaned transcript → 'complete'."""
    txt = tmp_path / "foo.txt"
    txt.write_text("# Foo\n\nSpeaker 0: hello\n" * 20)
    cleaned = tmp_path / "foo.cleaned.md"
    cleaned.write_text("# Foo\n\n**Speaker** (00:00): hello world\n" * 20)
    assert migrate.classify_transcript_status("foo", transcript_dir=tmp_path) == "complete"


def test_classify_transcript_status_none_when_skip_empty(tmp_path):
    """A SKIP_EMPTY stub cleaned.md → 'none'."""
    cleaned = tmp_path / "foo.cleaned.md"
    cleaned.write_text("# Foo\n\n(empty transcript)\n\n_Cleaned: skipped (transcript empty or too short)._\n")
    txt = tmp_path / "foo.txt"
    txt.write_text("(empty transcript)\n")
    assert migrate.classify_transcript_status("foo", transcript_dir=tmp_path) == "none"


def test_classify_transcript_status_unavailable_when_no_files(tmp_path):
    """No cleaned.md and no .txt → 'unavailable'."""
    assert migrate.classify_transcript_status("foo", transcript_dir=tmp_path) == "unavailable"


# -------- build_new_frontmatter tests --------


def test_subject_ref_becomes_authors_list():
    """An interview with subject: 'd-r-pendse' produces authors: ['d-r-pendse']."""
    old_fm = {
        "id": "d-r-pendse-on-doing-business",
        "title": "D R Pendse on Doing Business",
        "subject": "d-r-pendse",
        "subject_name": "D R Pendse",
        "youtube_url": "https://www.youtube.com/watch?v=abc",
        "pubDate": "2020-11-05T04:29:04Z",
        "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="d-r-pendse-on-doing-business",
        transcript_status="complete", description=None,
    )
    assert new_fm["work_type"] == "interview"
    assert new_fm["authors"] == ["d-r-pendse"]
    assert new_fm["youtube_url"] == "https://www.youtube.com/watch?v=abc"
    assert new_fm["transcript_status"] == "complete"
    assert new_fm["publication"]["year"] == 2020
    assert new_fm["publication"]["language"] == "en"
    assert "subject_name" not in new_fm


def test_missing_subject_yields_empty_authors():
    """No subject ref → authors: []."""
    old_fm = {
        "id": "il-explainer-ep-1",
        "title": "IL Explainer Ep 1",
        "subject_name": "Some Title",
        "pubDate": "2022-01-01T00:00:00Z",
        "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="il-explainer-ep-1",
        transcript_status="complete", description=None,
    )
    assert new_fm["authors"] == []
    assert "contributors" not in new_fm or new_fm["contributors"] == []


def test_description_when_present():
    """A non-empty description is included in the new frontmatter."""
    old_fm = {
        "id": "foo", "title": "Foo", "pubDate": "2020-01-01T00:00:00Z", "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="foo",
        transcript_status="complete",
        description="A real editorial paragraph.",
    )
    assert new_fm["description"] == "A real editorial paragraph."


def test_description_omitted_when_none():
    """A None description is NOT added as a key."""
    old_fm = {
        "id": "foo", "title": "Foo", "pubDate": "2020-01-01T00:00:00Z", "language": "en",
    }
    new_fm = migrate.build_new_frontmatter(
        old_fm, slug="foo",
        transcript_status="complete", description=None,
    )
    assert "description" not in new_fm


# -------- slug collision test --------


def test_slug_collision_aborts(tmp_path, monkeypatch):
    """If the destination MD already exists, migrate_one returns COLLISION and does NOT delete the source."""
    src_dir = tmp_path / "interviews"
    dst_dir = tmp_path / "primary-works"
    src_dir.mkdir()
    dst_dir.mkdir()

    src = src_dir / "foo.md"
    src.write_text("---\nid: foo\ntitle: Foo\npubDate: 2020-01-01T00:00:00Z\n---\nbody\n")
    dst = dst_dir / "foo.md"
    dst.write_text("# Already exists\n")

    monkeypatch.setattr(migrate, "PW_DIR", dst_dir)
    monkeypatch.setattr(migrate, "TRANSCRIPT_DIR", tmp_path)

    r = migrate.migrate_one(src)
    assert r["status"] == "COLLISION"
    assert src.exists(), "source was deleted despite collision"
    assert dst.read_text() == "# Already exists\n", "destination was overwritten"
