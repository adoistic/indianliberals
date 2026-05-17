"""
Mine all available sources for thinker / organisation / publisher names.
Output: raw aggregated lists with provenance, before any LLM clustering.

Sources:
  1. Existing thinkers/ collection — canonical IDs we've committed to
  2. WP DB wp_author table (indianli_liberals.sql) — 11 named authors with brief bios
  3. Content bylines from extracted entries (musings, opinions, interviews,
     theprint-mirror) — author_name + subject_name + author_resolved strings
  4. Publisher folder names — direct organisation + publisher identities
  5. Filename heuristics on 944 PDFs — "by X", "by X. Y. Surname", honorifics
  6. Proposal's named figures (manually listed)

This script does NOT cluster aliases (that's Phase 0.3 with Opus). It produces
the RAW union of every name seen, with provenance. Phase 0.3 collapses
"M.R. Masani" / "Minoo Masani" / "Mr. Masani" into one canonical entry.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db-extract"))
from dump_parser import iter_rows  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DRIVE = Path("/Volumes/One Touch/Indian Liberals")
SQL_DIR = DRIVE / "sql"
PDF_ROOT = DRIVE / "PDFs-by-publisher"
CONTENT_ROOT = REPO / "apps/site/src/content"
OUT_DIR = REPO / "data/authority"

# Names from the proposal + design docs that anchor the corpus.
PROPOSAL_THINKERS = [
    # Founding-era and major figures named explicitly in the proposal + design docs
    {"canonical": "Minoo Masani", "full": "Minocher Rustom Masani", "tradition": "classical_liberal", "birth_year": 1905, "death_year": 1998},
    {"canonical": "B. R. Shenoy", "full": "Bellikoth Raghunath Shenoy", "tradition": "classical_liberal", "birth_year": 1905, "death_year": 1978, "also_known_as": ["BR Shenoy", "B.R. Shenoy"]},
    {"canonical": "C. Rajagopalachari", "full": "Chakravarti Rajagopalachari", "tradition": "nationalist_liberal", "birth_year": 1878, "death_year": 1972, "also_known_as": ["Rajaji", "C.R."]},
    {"canonical": "A. D. Shroff", "full": "Ardeshir Darabshaw Shroff", "tradition": "classical_liberal", "birth_year": 1899, "death_year": 1965, "also_known_as": ["AD Shroff", "A.D. Shroff"]},
    {"canonical": "Nani Palkhivala", "full": "Nanabhoy Ardeshir Palkhivala", "tradition": "classical_liberal", "birth_year": 1920, "death_year": 2002, "also_known_as": ["Nani A. Palkhivala", "N. A. Palkhivala"]},
    {"canonical": "M. R. Pai", "full": "Madhav Ramachandra Pai", "tradition": "classical_liberal", "birth_year": 1930, "death_year": 2003, "also_known_as": ["MR Pai", "M.R. Pai"]},
    {"canonical": "D. R. Pendse", "full": "Datta R. Pendse", "tradition": "classical_liberal", "also_known_as": ["DR Pendse", "D.R. Pendse"]},
    {"canonical": "S. V. Raju", "full": "Sundaram Venkateswaran Raju", "tradition": "classical_liberal", "birth_year": 1933, "death_year": 2015, "also_known_as": ["SV Raju", "S.V. Raju"]},
    {"canonical": "Sudha R. Shenoy", "full": "Sudha Rabindranath Shenoy", "tradition": "classical_liberal", "birth_year": 1943, "death_year": 2008},
    {"canonical": "Sauvik Chakraverti", "full": "Sauvik Chakraverti", "tradition": "classical_liberal", "death_year": 2017},
    {"canonical": "Sharad Joshi", "full": "Sharad Anantrao Joshi", "tradition": "classical_liberal", "birth_year": 1935, "death_year": 2015, "also_known_as": ["Sharad Anantrao Joshi"]},
    {"canonical": "Mithan Tata Lam", "full": "Mithan Jamshed Lam", "tradition": "social_reformer", "birth_year": 1898, "death_year": 1981, "also_known_as": ["Mithan Lam", "Mithan Tata"]},
    {"canonical": "Lady Abala Bose", "full": "Abala Bose", "tradition": "social_reformer", "birth_year": 1864, "death_year": 1951, "also_known_as": ["Abala Bose"]},
    {"canonical": "Begum Rokeya", "full": "Rokeya Sakhawat Hossain", "tradition": "social_reformer", "birth_year": 1880, "death_year": 1932, "also_known_as": ["Begum Rokeya Sakhawat Hossain", "Rokeya"]},
    {"canonical": "Rabindranath Tagore", "full": "Rabindranath Thakur", "tradition": "reformer", "birth_year": 1861, "death_year": 1941, "also_known_as": ["Tagore"]},
    {"canonical": "Ishwar Chandra Vidyasagar", "full": "Ishwar Chandra Bandyopadhyay", "tradition": "social_reformer", "birth_year": 1820, "death_year": 1891, "also_known_as": ["Vidyasagar", "Ishwarchandra Vidyasagar"]},
    {"canonical": "Janaki Ammal", "full": "Edavalath Kakkat Janaki Ammal", "tradition": "reformer", "birth_year": 1897, "death_year": 1984, "also_known_as": ["E.K. Janaki Ammal"]},
    {"canonical": "Muthulakshmi Reddi", "full": "Muthulakshmi Reddi", "tradition": "social_reformer", "birth_year": 1886, "death_year": 1968, "also_known_as": ["S. Muthulakshmi Reddy"]},
    {"canonical": "Pandita Ramabai", "full": "Pandita Ramabai Sarasvati", "tradition": "social_reformer", "birth_year": 1858, "death_year": 1922, "also_known_as": ["Ramabai"]},
    {"canonical": "Gopal Krishna Gokhale", "full": "Gopal Krishna Gokhale", "tradition": "nationalist_liberal", "birth_year": 1866, "death_year": 1915, "also_known_as": ["Gokhale"]},
    {"canonical": "Raja Ram Mohan Roy", "full": "Rammohun Roy", "tradition": "reformer", "birth_year": 1772, "death_year": 1833, "also_known_as": ["Ram Mohan Roy", "Rammohun Roy"]},
    {"canonical": "Arun Shourie", "full": "Arun Shourie", "tradition": "contemporary_liberal", "birth_year": 1941},
    {"canonical": "Christopher Lingle", "full": "Christopher Lingle", "tradition": "international_influence"},
    {"canonical": "Tom G. Palmer", "full": "Tom Gordon Palmer", "tradition": "international_influence"},
    {"canonical": "Friedrich Hayek", "full": "Friedrich August von Hayek", "tradition": "international_influence", "birth_year": 1899, "death_year": 1992},
    {"canonical": "Peter Bauer", "full": "Peter Thomas Bauer", "tradition": "international_influence", "birth_year": 1915, "death_year": 2002},
    {"canonical": "Frédéric Bastiat", "full": "Claude-Frédéric Bastiat", "tradition": "international_influence", "birth_year": 1801, "death_year": 1850, "also_known_as": ["Frederic Bastiat"]},
]

PROPOSAL_ORGS = [
    # Indian liberal movement orgs
    {"id": "forum-of-free-enterprise", "canonical": "Forum of Free Enterprise", "also_known_as": ["FFE", "the Forum"], "founded_year": 1956, "type": "think_tank"},
    {"id": "swatantra-party", "canonical": "Swatantra Party", "also_known_as": ["Swatantra"], "founded_year": 1959, "dissolved_year": 1974, "type": "political_party"},
    {"id": "indian-liberal-group", "canonical": "Indian Liberal Group", "also_known_as": ["ILG", "IL Group"], "founded_year": 2000, "type": "think_tank"},
    {"id": "shetkari-sanghatana", "canonical": "Shetkari Sanghatana", "also_known_as": ["Shetkari Sanghatak"], "founded_year": 1979, "type": "reform_society"},
    {"id": "centre-for-civil-society", "canonical": "Centre for Civil Society", "also_known_as": ["CCS"], "founded_year": 1997, "type": "think_tank"},
    {"id": "liberty-institute", "canonical": "Liberty Institute", "founded_year": 1996, "type": "think_tank"},
    {"id": "all-india-liberal-federation", "canonical": "All India Liberal Federation", "also_known_as": ["AILF"], "type": "political_party"},
    # International liberal network
    {"id": "friedrich-naumann-foundation", "canonical": "Friedrich Naumann Foundation", "also_known_as": ["FNF", "Friedrich Naumann Foundation for Freedom"], "type": "international_network"},
    {"id": "liberal-international", "canonical": "Liberal International", "founded_year": 1947, "type": "international_network"},
    {"id": "atlas-network", "canonical": "Atlas Network", "also_known_as": ["Atlas Economic Research Foundation"], "type": "international_network"},
    {"id": "mont-pelerin-society", "canonical": "Mont Pelerin Society", "founded_year": 1947, "type": "international_network"},
    {"id": "hoover-institution", "canonical": "Hoover Institution", "founded_year": 1919, "type": "academic"},
    # Counter-context (statist counterparts, frequently engaged with in corpus)
    {"id": "indian-national-congress", "canonical": "Indian National Congress", "also_known_as": ["Congress", "INC"], "founded_year": 1885, "type": "political_party"},
    {"id": "congress-socialist-party", "canonical": "Congress Socialist Party", "also_known_as": ["CSP"], "founded_year": 1934, "dissolved_year": 1948, "type": "political_party"},
    {"id": "planning-commission-india", "canonical": "Planning Commission of India", "founded_year": 1950, "dissolved_year": 2014, "type": "academic"},
    # Business orgs (FFE-adjacent ecosystem)
    {"id": "indian-merchants-chamber", "canonical": "Indian Merchants' Chamber", "also_known_as": ["IMC"], "founded_year": 1907, "type": "professional_body"},
    {"id": "federation-of-indian-chambers-of-commerce", "canonical": "Federation of Indian Chambers of Commerce and Industry", "also_known_as": ["FICCI"], "founded_year": 1927, "type": "professional_body"},
    {"id": "bombay-stock-exchange", "canonical": "Bombay Stock Exchange", "also_known_as": ["BSE"], "founded_year": 1875, "type": "professional_body"},
    {"id": "ncaer", "canonical": "National Council of Applied Economic Research", "also_known_as": ["NCAER"], "founded_year": 1956, "type": "academic"},
    {"id": "tata-sons", "canonical": "Tata Sons", "founded_year": 1917, "type": "publisher_org"},
    {"id": "bharatiya-vidya-bhavan", "canonical": "Bharatiya Vidya Bhavan", "founded_year": 1938, "type": "academic"},
]

PROPOSAL_PUBLISHERS = [
    # Self-publishing orgs (also in organisations list)
    {"id": "forum-of-free-enterprise", "name": "Forum of Free Enterprise", "place": "Bombay", "linked_organisation": "forum-of-free-enterprise"},
    {"id": "swatantra-party", "name": "Swatantra Party", "linked_organisation": "swatantra-party"},
    {"id": "shetkari-sanghatana", "name": "Shetkari Sanghatana", "linked_organisation": "shetkari-sanghatana"},
    {"id": "indian-liberal-group", "name": "Indian Liberal Group", "linked_organisation": "indian-liberal-group"},
    {"id": "centre-for-civil-society", "name": "Centre for Civil Society", "place": "New Delhi", "linked_organisation": "centre-for-civil-society"},
    # Periodical mastheads (frequently referenced as their own publishers)
    {"id": "the-indian-libertarian", "name": "The Indian Libertarian", "place": "Bombay", "publication_type": "periodical"},
    {"id": "liberal-times", "name": "Liberal Times", "publication_type": "periodical"},
    {"id": "freedom-first", "name": "Freedom First", "place": "Bombay", "publication_type": "periodical"},
    {"id": "khoj", "name": "Khoj", "publication_type": "periodical"},
    {"id": "swarajya", "name": "Swarajya", "place": "Madras", "publication_type": "periodical"},
    # Commercial publishers active in the Indian liberal corpus
    {"id": "asia-publishing-house", "name": "Asia Publishing House", "place": "Bombay"},
    {"id": "vakils-feffer-simons", "name": "Vakils, Feffer and Simons", "place": "Bombay"},
    {"id": "popular-prakashan", "name": "Popular Prakashan", "place": "Bombay"},
    {"id": "macmillan-india", "name": "Macmillan India"},
    {"id": "oxford-university-press-india", "name": "Oxford University Press India"},
    {"id": "penguin-india", "name": "Penguin India"},
    {"id": "rupa-publications", "name": "Rupa Publications", "place": "Delhi"},
]


# --- Source 1: existing thinkers/ collection ------------------------------

def mine_thinkers_collection() -> list[dict]:
    out = []
    for f in sorted((CONTENT_ROOT / "thinkers").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        fm_end = text.find("\n---\n", 4)
        fm = text[4:fm_end]
        slug = f.stem
        # Extract canonical name
        m = re.search(r"canonical:\s*\"([^\"]+)\"", fm)
        canonical = m.group(1) if m else slug.replace("-", " ").title()
        out.append({"id": slug, "canonical": canonical, "source": "thinkers_collection"})
    return out


# --- Source 2: WP DB wp_author ---------------------------------------------

def mine_wp_author() -> list[dict]:
    out = []
    sql = SQL_DIR / "indianli_liberals.sql"
    for r in iter_rows(sql, "wp_author"):
        if not r.get("name"):
            continue
        out.append({
            "canonical": r["name"].strip(),
            "brief_bio": (r.get("briefinfo") or "").strip()[:400],
            "image_filename": r.get("image", ""),
            "source": "wp_author",
        })
    return out


# --- Source 3: content bylines --------------------------------------------

BYLINE_FIELDS = {
    "opinions": "author_name",
    "interviews": "subject_name",
    "theprint-mirror": "author_name",
    "musings": None,  # no consistent byline field after our extraction
}


def mine_content_bylines() -> list[dict]:
    out = []
    for coll, field in BYLINE_FIELDS.items():
        if field is None:
            continue
        coll_dir = CONTENT_ROOT / coll
        if not coll_dir.exists():
            continue
        for f in sorted(coll_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            m = re.search(rf'^{re.escape(field)}:\s*"([^"]+)"', text, re.MULTILINE)
            if not m:
                continue
            byline = m.group(1).strip()
            # Skip placeholder values and obvious junk
            if byline in {"Editorial Team", "Editorial Team — Indian Liberals", ""}:
                continue
            if "EditorialTeam" in byline.replace(" ", ""):
                continue
            out.append({"byline": byline, "source": f"content/{coll}/{f.name}"})
    return out


# --- Source 4: PDF filenames ----------------------------------------------

# Pattern: capture text after "-by-" up to either a month word, a 4-digit year,
# a date numeral pattern, or end of filename. This strips trailing date noise
# like "by-bk-nehru-april-15-1986" → "bk nehru" instead of "bk nehru april".

_MONTH_WORDS = (
    "january|february|march|april|may|june|july|august|september|"
    "october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)

_BY_AUTHOR_FILENAME_RE = re.compile(
    rf"-by-([a-z][a-z'\.\-]+?)(?=-(?:{_MONTH_WORDS})\b|-\d{{4}}\b|-on-\b|-and-the-\b|\.pdf$|-$)",
    re.IGNORECASE,
)


# Words that should never appear as part of an extracted byline (typically
# title fragments that snuck through). Drop entries containing only these.
_BYLINE_NOISE_WORDS = {
    "and", "or", "the", "a", "of", "for", "to", "in", "on", "at",
    "foreign", "economists", "edited", "memorial", "honour", "honor",
    "indian", "national", "march", "april", "june", "july", "august",
}


def mine_pdf_filenames() -> list[dict]:
    out = []
    if not PDF_ROOT.exists():
        return out
    for f in sorted(PDF_ROOT.rglob("*.pdf")):
        if f.name.startswith("._"):
            continue
        stem = f.stem.lower()
        for m in _BY_AUTHOR_FILENAME_RE.finditer(stem):
            raw = m.group(1).replace("-", " ").strip(". ")
            if len(raw) < 5 or len(raw) > 60:
                continue
            # Drop pure-noise extractions (titles that mention "by foreign economists" etc.)
            tokens = [t for t in raw.split() if len(t) > 1]
            if not tokens:
                continue
            real_tokens = [t for t in tokens if t.lower() not in _BYLINE_NOISE_WORDS]
            if not real_tokens or len(real_tokens) < 2:
                continue
            # Title-case for canonical display, preserving initials
            canonical = " ".join(
                t.upper() if len(t) <= 3 and t.replace(".", "").isalpha() and len(t) <= 2 else t.capitalize()
                for t in tokens
            )
            out.append({"canonical": canonical, "source": f"pdf-filename/{f.parent.name}/{f.name}"})
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    thinkers_coll = mine_thinkers_collection()
    wp_authors = mine_wp_author()
    bylines = mine_content_bylines()
    filenames = mine_pdf_filenames()

    # Combine all thinker-name evidence
    seen_by_normalized: dict[str, dict] = {}

    def normalize(s: str) -> str:
        s = re.sub(r"[\.\,]", "", s).lower()
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def add(canonical: str, **kwargs) -> None:
        key = normalize(canonical)
        if not key or len(key) < 5:
            return
        if key in seen_by_normalized:
            entry = seen_by_normalized[key]
            entry["sources"].append(kwargs.get("source", "unknown"))
        else:
            seen_by_normalized[key] = {
                "canonical": canonical,
                "sources": [kwargs.get("source", "unknown")],
                **{k: v for k, v in kwargs.items() if k not in {"source", "canonical"}},
            }

    # Order matters: proposal seeds first (richest metadata), then existing,
    # then WP DB, then bylines, then filenames.
    for t in PROPOSAL_THINKERS:
        add(t["canonical"], source="proposal", **{k: v for k, v in t.items() if k != "canonical"})
    for t in thinkers_coll:
        add(t["canonical"], source=t["source"], existing_id=t["id"])
    for t in wp_authors:
        add(t["canonical"], source=t["source"], brief_bio=t.get("brief_bio"), image_filename=t.get("image_filename"))
    for t in bylines:
        add(t["byline"], source=t["source"])
    for t in filenames:
        add(t["canonical"], source=t["source"])

    # Convert to list for output
    thinkers_list = list(seen_by_normalized.values())
    # Sort by number of sources (more sources = more confidence)
    thinkers_list.sort(key=lambda x: (-len(x["sources"]), x["canonical"]))

    # Write outputs
    thinkers_file = OUT_DIR / "thinkers.raw.json"
    thinkers_file.write_text(
        json.dumps({"_meta": {"count": len(thinkers_list), "purpose": "raw pre-clustering aggregated thinker names with provenance — Phase 0.1 seed"}, "thinkers": thinkers_list}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    orgs_file = OUT_DIR / "organisations.json"
    orgs_file.write_text(
        json.dumps({"_meta": {"count": len(PROPOSAL_ORGS), "purpose": "seed organisation list for authority file"}, "organisations": PROPOSAL_ORGS}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    publishers_file = OUT_DIR / "publishers.json"
    publishers_file.write_text(
        json.dumps({"_meta": {"count": len(PROPOSAL_PUBLISHERS), "purpose": "seed publisher list for authority file"}, "publishers": PROPOSAL_PUBLISHERS}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Raw thinker candidates: {len(thinkers_list)}")
    print(f"  with multiple sources: {sum(1 for t in thinkers_list if len(t['sources']) >= 2)}")
    print(f"  single-source: {sum(1 for t in thinkers_list if len(t['sources']) == 1)}")
    print(f"\nOrganisations: {len(PROPOSAL_ORGS)}")
    print(f"Publishers: {len(PROPOSAL_PUBLISHERS)}")
    print(f"\nWritten:")
    print(f"  {thinkers_file.relative_to(REPO)}  (raw — needs Phase 0.3 clustering)")
    print(f"  {orgs_file.relative_to(REPO)}")
    print(f"  {publishers_file.relative_to(REPO)}")


if __name__ == "__main__":
    main()
