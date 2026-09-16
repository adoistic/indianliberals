#!/usr/bin/env python3
"""Build author profiles for every BYLINED Quest contributor.

INPUT is the committed harvest in `data/quest-contributors/QTNNN.json` — one
file per issue, one record per bylined person, each carrying the byline as
printed, the contributor note copied word for word, and the printed evidence
for nationality and vocation. Nothing here reads a PDF: the reading was done
once, by the per-issue agents, and committed.

WHAT IT DOES
  1. Clusters records into PEOPLE across the whole run, using the
     `name_variants` the agents recorded ("Monika Verma"/"Monika Varma",
     "Sachin K. Roy"/"S. K. Ray"). Surnames are NOT required to agree — several
     real Quest contributors published under two different surnames.
  2. Matches each cluster against the people the archive already has (the 454
     authority entries and the 727 thinker pages). An existing person keeps
     their existing page; we only propose adding their Quest name variants as
     aliases so future emits resolve them.
  3. Writes a thinker profile for each genuinely new person, grounded ONLY in
     what Quest printed: the note is quoted, with the issue cited.

WHAT IT DELIBERATELY DOES NOT DO
  - It does not classify `tradition` or `canon_status`. Quest published poets,
    musicologists and French art critics; CCS has a thinker-classification
    round-trip for exactly this, so both stay "unclassified".
  - It does not set `nationality` without printed words to rest it on. The
    schema defaults to india and 30+ Quest contributors are evidenced as
    non-Indian; a name is NOT evidence.
  - It does not create a page for an initials-only byline ("N.E.", "A.H.D.").
    Those would be junk pages, and "L.F." would split Laeeq Futehally, who has
    a profile from her named bylines.
  - It never marks anyone `featured`: the curated canon page is CCS's.

Usage:
    build_profiles.py --audit            # report only; writes nothing
    build_profiles.py --write            # write thinker MDs
    build_profiles.py --write --authority  # also update data/authority/thinkers.json
"""
from __future__ import annotations

import json, re, sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
HARVEST = REPO / "data/quest-contributors"
THINKERS = REPO / "apps/site/src/content/thinkers"
WORKS = REPO / "apps/site/src/content/primary-works"
AUTHORITY = REPO / "data/authority/thinkers.json"
REPORT = HARVEST / "PROFILE-BUILD-REPORT.md"

FM_RX = re.compile(r"^---\n([\s\S]*?)\n---\n?([\s\S]*)$")
HONORIFIC = r"(?:prof|dr|mr|mrs|ms|smt|shri|sri|sir|justice|lord|lady|pandit|acharya|miss|swami|rev|late)"
HON_RX = re.compile(rf"^{HONORIFIC}\.?\s+", re.I)
NON_SLUG_RX = re.compile(r"[^a-z0-9]+")


# ── name handling ────────────────────────────────────────────────────────────

DISPLAY_HONORIFIC = r"(?:prof(?:essor)?|dr|mr|mrs|ms|smt|miss|shri|sri|sir|the hon|rev)"
DISP_HON_RX = re.compile(rf"^{DISPLAY_HONORIFIC}\.?\s+", re.I)
QUOTES = "\"'\u2018\u2019\u201c\u201d"

# Bylines that name no person. Quest signed real things this way.
STOP_NAMES = {
    "anonymous", "anon", "a correspondent", "our correspondent",
    "special correspondent", "from our correspondent", "the editor",
    "the editors", "editor", "editors", "the publishers", "staff",
    "a reader", "a contributor", "contributors", "unsigned", "various",
    "a consumer", "a student", "a friend", "observer",
}
ROLE_TITLE_RX = re.compile(
    r"\b(chairman|president|secretary|director|principal|vice-chancellor|"
    r"professor|lecturer|reader|editor|manager|member of|fellow of|"
    r"i\.?c\.?s\.?|i\.?a\.?s\.?|ph\.?\s*d|m\.?\s*a\.?|b\.?\s*a\.?|"
    r"m\.?\s*p\.?|esq)\b", re.I)
PARTICLES = {"de", "del", "della", "van", "von", "der", "den", "da", "di", "du",
             "la", "le", "bin", "ibn", "al", "e"}


def strip_honorifics(name: str) -> str:
    s = (name or "").strip()
    for _ in range(3):
        new = HON_RX.sub("", s).strip()
        if new == s:
            break
        s = new
    return s


def titlecase_name(s: str) -> str:
    """Quest sets contributor names in caps; the archive displays title case.

    Initials, Mc/Mac, O', hyphens and nobiliary particles all have to survive:
    "A. H. SOMJEE" -> "A. H. Somjee", "R. DE LOYOLA FURTADO" -> "R. de Loyola
    Furtado", "DATTA-RAY" -> "Datta-Ray".
    """
    def one(w: str) -> str:
        if re.fullmatch(r"(?:[A-Za-z]\.){1,4}|[A-Za-z]", w):
            return w.upper()                       # "S.D.", "A.H.D.", "A"
        low = w.lower()
        if low.strip(".") in PARTICLES:
            return low
        if low.startswith("mc") and len(low) > 2:
            return "Mc" + low[2:].capitalize()
        if low.startswith("mac") and len(low) > 4:
            return "Mac" + low[3:].capitalize()
        if low.startswith("o'") and len(low) > 2:
            return "O'" + low[2:].capitalize()
        return "-".join(part.capitalize() for part in low.split("-"))
    out = " ".join(one(w) for w in s.split())
    return out[0].upper() + out[1:] if out else out


def display_name(raw: str) -> str:
    """Turn a printed byline into the person's name.

    Quest's bylines carry role prefixes ("EDITOR: NISSIM EZEKIEL", "Paintings
    by RASIK RAVAL", "Translated from the Marathi by M. D. HATKANANGALEKAR"),
    trailing qualifications ("Professor M. K. Haldar, Ph. D. (London)") and
    appointments ("Jayaprakash Narayan, Chairman of the Indian Committee...").
    None of that is the name.
    """
    s = (raw or "").strip().strip(QUOTES).strip()
    s = re.sub(r"\s*\([^)]*\)", " ", s)                 # (the Author), (London)
    if ":" in s:
        s = s.split(":", 1)[1]                            # role prefix
    s = re.sub(r"^.*?\bby\s+", "", s, flags=re.I) if re.search(r"\bby\s+\S", s, re.I) else s
    if "," in s:
        head, tail = s.split(",", 1)
        # a trailing appointment or degree is not part of the name
        if len(head.split()) >= 2 or ROLE_TITLE_RX.search(tail):
            s = head
    s = re.sub(r",?\s*(I\.?A\.?S\.?|I\.?C\.?S\.?|Esq\.?|Jr\.?|Sr\.?|Ph\.?\s*D\.?|M\.?A\.?|M\.?P\.?)\s*$",
               "", s, flags=re.I)
    s = s.strip(" ,.;:" + QUOTES).strip()
    for _ in range(3):
        new = DISP_HON_RX.sub("", s).strip()
        if new == s:
            break
        s = new
    if s and not re.search(r"[a-z]", s):                  # SHOUTED
        s = titlecase_name(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(name: str) -> str:
    """Matching form: honorific-stripped, lowercase, alphanumerics only.

    Everything that is not a letter or digit becomes a space, so a pen name
    printed as "\u2018Andal\u2019" and one printed as "Andal" are one person rather
    than two profiles.
    """
    s = strip_honorifics(name or "")
    s = re.sub(r"[^0-9a-z\u0080-\uffff]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def tokens(name: str) -> list[str]:
    return [t for t in norm(name).split() if t]


def is_initials_only(name: str) -> bool:
    """True when every token is a single letter: "N.E.", "A. H. D.", "L.F.".

    These are real Quest bylines but they do not identify a person well enough
    for a page, and they merge everyone who shares the initials.
    """
    toks = tokens(name)
    return bool(toks) and all(len(t) == 1 for t in toks)


def is_multi_person(raw: str) -> bool:
    """"Advisory Editors: Nirad C. Chaudhuri, Sudhin Datta, D. G. Nadkarni"
    is three people on one masthead line, not a person."""
    s = re.sub(r"\s*\([^)]*\)", " ", (raw or ""))
    if ":" in s:
        s = s.split(":", 1)[1]
    return s.count(",") >= 2 or bool(re.search(r"\S\s+and\s+\S", s, re.I))


def slugify(name: str, max_len: int = 60) -> str:
    s = NON_SLUG_RX.sub("-", strip_honorifics(name).lower()).strip("-")
    return re.sub(r"-+", "-", s)[:max_len]


def sort_key(canonical: str) -> str:
    """"A. B. Shah" -> "Shah, A. B."; a mononym stays as it is."""
    parts = strip_honorifics(canonical).split()
    if len(parts) < 2:
        return strip_honorifics(canonical)
    surname = parts[-1]
    rest = parts[:-1]
    if len(parts) > 2 and parts[-2].lower().strip(".") in PARTICLES:
        surname = f"{parts[-2]} {parts[-1]}"
        rest = parts[:-2]
    return f"{surname}, {' '.join(rest)}"


def name_quality(name: str) -> tuple:
    """Rank name forms for choosing a cluster's display name: a form with real
    given names beats initials, more tokens beats fewer.
    "Nissim Ezekiel" > "N. Ezekiel" > "N.E.".
    """
    toks = tokens(name)
    spelled = sum(1 for t in toks if len(t) > 1)
    return (spelled, len(toks), len(name))


# ── harvest ──────────────────────────────────────────────────────────────────

def load_harvest() -> list[tuple[str, dict]]:
    rows = []
    for f in sorted(HARVEST.glob("QT*.json")):
        qt = f.stem
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, dict):                     # tolerate a wrapped array
            data = data.get("contributors") or data.get("records") or []
        for r in data:
            if isinstance(r, dict) and (r.get("byline_verbatim") or r.get("name_as_in_contributor_note")):
                rows.append((qt, r))
    return rows


def record_forms(r: dict) -> list[str]:
    """Every name form on one harvest record, as printed."""
    forms = [r.get("byline_verbatim"), r.get("name_as_in_contributor_note")]
    forms += [v for v in (r.get("name_variants") or []) if isinstance(v, str)]
    seen, out = set(), []
    for f in forms:
        if isinstance(f, str) and f.strip() and norm(f) and norm(f) not in seen:
            seen.add(norm(f))
            out.append(f.strip())
    return out


def clean_forms(r: dict) -> list[str]:
    """The same forms reduced to names, which is what identity is keyed on.

    Clustering on the raw byline split people in two: Quest's masthead prints
    "EDITOR: NISSIM EZEKIEL" and its contents page prints "Nissim Ezekiel", and
    the first version of this script proposed two Nissim Ezekiel pages and then
    reported the second as a slug clash. A byline naming SEVERAL people
    ("Advisory Editors: Nirad C. Chaudhuri, Sudhin Datta, D. G. Nadkarni") is
    dropped here rather than cleaned, because cleaning it would silently file
    three people's masthead line under the first of them.
    """
    out = []
    for f in record_forms(r):
        if is_multi_person(f):
            continue
        d = display_name(f)
        if d and norm(d) not in {norm(x) for x in out}:
            out.append(d)
    return out


class Union:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.p[rb] = ra


def cluster(rows: list[tuple[str, dict]]) -> tuple[dict, dict]:
    """Group records into people, and count how often each name form is printed.

    Any two name forms on the SAME record are the same person — that is what
    `name_variants` means. Frequency matters for picking the display form:
    Quest printed "David McCutchion" nine times and "David McChutchion" once,
    and the nine-times spelling is the right one.
    """
    u = Union()
    freq: dict[str, int] = defaultdict(int)
    unnamed: list[tuple[str, dict]] = []
    for _, r in rows:
        forms = [norm(f) for f in clean_forms(r)]
        for f in forms[1:]:
            u.join(forms[0], f)
    for _, r in rows:
        for k in ("byline_verbatim", "name_as_in_contributor_note"):
            v = r.get(k)
            if isinstance(v, str) and not is_multi_person(v):
                d = norm(display_name(v))
                if d:
                    freq[d] += 1
    groups = defaultdict(list)
    for qt, r in rows:
        forms = clean_forms(r)
        if not forms:
            unnamed.append((qt, r)); continue
        groups[u.find(norm(forms[0]))].append((qt, r))
    return groups, freq, unnamed


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def is_extension(a: str, b: str) -> bool:
    """True when one name is the other plus a middle initial or middle name:
    "Feroze Moos" / "Feroze F. Moos". First and last token must be identical,
    and the shorter must be a subsequence of the longer. "K. B. Rao" is NOT an
    extension of "K. Raghavendra Rao" — those are two people.
    """
    x, y = tokens(a), tokens(b)
    if len(x) == len(y) or not x or not y:
        return False
    short, long = (x, y) if len(x) < len(y) else (y, x)
    if short[0] != long[0] or short[-1] != long[-1]:
        return False
    it = iter(long)
    return all(any(t == l for l in it) for t in short)


def near_duplicates(canonicals: list[str]) -> list[tuple[str, str]]:
    """Clusters that may be one person under two spellings — for REVIEW only.

    "ARUN KOLHATKAR" and "Arun Kolatkar" are the poet Arun Kolatkar, but no
    single harvest record listed both forms, so the variant-based clustering
    cannot see it. Merging on similarity alone would be worse than reporting:
    the first version of this check bucketed every Roy and Ray in the run
    together and proposed that Sachin K. Roy, Samaren Roy, Satyajit Roy,
    Sibnarayan Ray and Sunanda K. Datta-Ray might be one man. So BOTH halves
    have to be close: the surnames within an edit or two, AND the given names
    matching, initial-compatible, or within an edit or two.
    """
    out = []
    for i in range(len(canonicals)):
        for j in range(i + 1, len(canonicals)):
            a, b = canonicals[i], canonicals[j]
            ta, tb = tokens(a), tokens(b)
            if not ta or not tb or norm(a) == norm(b):
                continue
            sa, sb = ta[-1], tb[-1]
            # a three-letter surname has no room for two edits: "Rao" and
            # "Raza" are not each other, and "K. B. Rao" is not "S. Balu Rao"
            limit = 1 if min(len(sa), len(sb)) <= 4 else 2
            if sa[0] != sb[0] or edit_distance(sa, sb) > limit:
                continue
            ga, gb = ta[0], tb[0]
            if len(ga) == 1 and len(gb) == 1:
                close = ga == gb              # two different initials are two people
            elif len(ga) == 1 or len(gb) == 1:
                close = gb.startswith(ga) if len(ga) == 1 else ga.startswith(gb)
            else:
                close = ga == gb or (min(len(ga), len(gb)) >= 4
                                     and edit_distance(ga, gb) <= 2)
            # "A. H. Somjee" / "H. Somjee": same surname, and every token of
            # the shorter form appears in the longer one.
            if not close and sa == sb:
                short, long = sorted((ta, tb), key=len)
                close = all(t in long for t in short)
            if close:
                out.append(tuple(sorted((a, b))))
    return sorted(set(out))


# ── the archive's existing people ────────────────────────────────────────────

def existing_people() -> tuple[dict[str, str], dict[str, str], set[str], dict[str, str]]:
    """(normalised name -> slug) from the authority file and the thinker pages,
    the set of slugs already taken, and each slug's canonical name (which the
    given-name guard needs)."""
    auth, files, slugs, canon = {}, {}, set(), {}
    doc = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    for key, tid in (doc.get("byline_lookup") or {}).items():
        auth.setdefault(norm(key), tid)
    for t in doc.get("thinkers") or []:
        nm = t.get("name") or {}
        tid = t.get("id")
        if not tid:
            continue
        slugs.add(tid)
        if nm.get("canonical"):
            canon.setdefault(tid, nm["canonical"])
        for form in [nm.get("canonical"), nm.get("full"), *(nm.get("also_known_as") or [])]:
            if form:
                auth.setdefault(norm(form), tid)
    for p in sorted(THINKERS.glob("*.md")):
        slugs.add(p.stem)
        m = FM_RX.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        nm = fm.get("name") or {}
        if isinstance(nm, str):
            nm = {"canonical": nm}
        if nm.get("canonical"):
            canon.setdefault(p.stem, nm["canonical"])
        for form in [nm.get("canonical"), nm.get("full"), *(nm.get("also_known_as") or [])]:
            if form:
                files.setdefault(norm(form), p.stem)
    return auth, files, slugs, canon


# ── evidence → fields ────────────────────────────────────────────────────────

# Word-anchored, because an unbounded /editor/ once matched "Cr-EDITED" and made
# the sculptor A. M. Davierwalla an editor.
VOCATION_RX = [
    ("poet",               r"\bpoet(ry|s)?\b|\bpoems?\b"),
    ("philosopher",        r"\bphilosoph(y|er|ical)\b|\bmetaphysic"),
    # "a doctorate from the London School of Economics" is an institution, not
    # a vocation: it made the political scientist A. H. Somjee an economist.
    ("economist",          r"\beconomist\b|(?<!school of )\beconomics\b"),
    ("historian",          r"\bhistorian\b|\bhistory\b"),
    ("political_scientist",r"\bpolitical scien|\bpolitics\b.{0,20}\b(professor|lecturer|reader)\b"),
    ("sociologist",        r"\bsociolog(y|ist|ical)\b|\banthropolog(y|ist)\b"),
    ("legal_scholar",      r"\bbarrister\b|\badvocate\b|\bjuris|\blaw\b|\blawyer\b|\bsolicitor\b"),
    ("scientist",          r"\bphysicist\b|\bchemist\b|\bbiolog(y|ist)\b|\bmathematic|\bscientist\b|\bbotan(y|ist)\b"),
    ("engineer",           r"\bengineer(ing)?\b"),
    ("professor",          r"\bprofessor\b|\blecturer\b|\breader in\b|\bteaches\b|\btaught\b|\bfaculty\b"),
    ("writer",             r"\bnovelist\b|\bnovels?\b|\bshort stor(y|ies)\b|\bwriter\b|\bauthor of\b|\bessayist\b|\bplaywright\b|\bdramatist\b"),
    ("editor",             r"\beditor\b|\beditorial\b|\bedits\b|\bedited\b(?!\s*by\s*the)"),
    ("journalist",         r"\bjournalist\b|\bcorrespondent\b|\breporter\b|\bnewspaper\b"),
    ("statesman",          r"\bminister\b|\bcabinet\b|\bchief minister\b|\bgovernor\b"),
    ("parliamentarian",    r"\bmember of parliament\b|\bm\.?p\.?\b|\blok sabha\b|\brajya sabha\b|\blegislative assembly\b"),
    ("civil_servant",      r"\bcivil service\b|\bi\.?c\.?s\.?\b|\bi\.?a\.?s\.?\b|\bsecretary to the government\b|\bdeputy commissioner\b"),
    ("diplomat",           r"\bambassador\b|\bdiplomat(ic)?\b|\bhigh commissioner\b|\bconsul\b"),
    ("judge",              r"\bjudge\b|\bjustice of\b|\bhigh court\b.{0,15}\bbench\b"),
    ("industrialist",      r"\bindustrialist\b|\bmanaging director\b|\bmills\b"),
    ("entrepreneur",       r"\bbusinessman\b|\bentrepreneur\b|\bfounded the firm\b"),
    ("activist",           r"\btrade union\b|\bactivist\b|\bsatyagraha\b|\bmovement\b.{0,20}\bleader\b"),
    ("reformer",           r"\breformer\b|\bsocial work(er)?\b"),
    ("religious_figure",   r"\bswami\b|\bmonk\b|\bpriest\b|\bjesuit\b|\btheolog(y|ian)\b|\bsannyasi\b"),
    # "major" alone made Aron Tamasi — "one of the major figures in Hungarian
    # short story and drama" — a military officer. Ranks only, anchored.
    ("military_officer",   r"\b(army|navy|naval|air force|colonel|brigadier|lieutenant|"
                           r"major[- ]general|squadron leader|regiment)\b"),
    ("artist",             r"\bpainter\b|\bsculptor\b|\bartist\b|\bphotographer\b|\bmusician\b|\bdancer\b|\bfilm\b|\bmusicolog"),
]

# An adjectival nationality, or a place in an explicit ORIGIN construction.
# Nothing else counts. The first version of this script read Nissim Ezekiel's
# note — he studied in London — and labelled India's foremost English-language
# poet British.
ADJECTIVAL = {
    "indian": "india", "english": "uk", "british": "uk", "scottish": "uk",
    "welsh": "uk", "irish": "ireland", "american": "usa", "french": "france",
    "german": "germany", "austrian": "austria", "hungarian": "hungary",
    "italian": "italy", "swiss": "switzerland", "israeli": "israel",
    "japanese": "japan", "chinese": "china", "polish": "poland",
    "russian": "russia", "soviet": "russia", "yugoslav": "yugoslavia",
    "dutch": "netherlands", "belgian": "belgium", "spanish": "spain",
    "portuguese": "portugal", "swedish": "sweden", "norwegian": "norway",
    "danish": "denmark", "czech": "czechoslovakia", "romanian": "romania",
    "greek": "greece", "turkish": "turkey", "pakistani": "pakistan",
    "ceylonese": "ceylon", "burmese": "burma", "nepalese": "nepal",
    "canadian": "canada", "australian": "australia", "brazilian": "brazil",
    "mexican": "mexico", "egyptian": "egypt", "nigerian": "nigeria",
    "iranian": "iran", "persian": "iran", "iraqi": "iraq", "afghan": "afghanistan",
    "bengali": "india", "marathi": "india", "gujarati": "india", "tamil": "india",
    "englishman": "uk", "englishwoman": "uk", "anglo-indian": "india",
}
# Contexts in which an adjectival nationality is about a LANGUAGE or a
# literature, not a person. "an eminent Indo-English poet" is Nissim Ezekiel,
# who was Indian; "writes exclusively in English" is a Bengali writer.
LANG_CONTEXT = re.compile(
    r"(?:\bin(?:to)?\s+|\bfrom\s+the\s+|\bwrit(?:es|ten|ing)\s+|\btranslat\w+\s+"
    r"|\blanguage\s+of\s+|\bindo[- ]|\banglo[- ])$", re.I)
LANG_SUFFIX = re.compile(r"^(?:[- ](?:speaking|language|literature|translation|version|edition))", re.I)
PLACE_COUNTRY = {
    "india": "india", "bombay": "india", "calcutta": "india", "delhi": "india",
    "new delhi": "india", "madras": "india", "poona": "india", "bengal": "india",
    "punjab": "india", "mysore": "india", "kerala": "india", "hyderabad": "india",
    "ahmedabad": "india", "baroda": "india", "banaras": "india", "varanasi": "india",
    "allahabad": "india", "lucknow": "india", "nagpur": "india", "patna": "india",
    "shantiniketan": "india", "kashmir": "india", "assam": "india", "goa": "india",
    "england": "uk", "britain": "uk", "london": "uk", "scotland": "uk", "wales": "uk",
    "united states": "usa", "u s a": "usa", "usa": "usa", "america": "usa",
    "new york": "usa",
    "france": "france", "paris": "france", "germany": "germany", "berlin": "germany",
    "austria": "austria", "vienna": "austria", "hungary": "hungary",
    "budapest": "hungary", "italy": "italy", "rome": "italy",
    "switzerland": "switzerland", "geneva": "switzerland", "zurich": "switzerland",
    "israel": "israel", "jerusalem": "israel", "tel aviv": "israel",
    "japan": "japan", "tokyo": "japan", "poland": "poland", "warsaw": "poland",
    "russia": "russia", "moscow": "russia", "yugoslavia": "yugoslavia",
    "belgrade": "yugoslavia", "holland": "netherlands", "netherlands": "netherlands",
    "pakistan": "pakistan", "lahore": "pakistan", "karachi": "pakistan",
    "ceylon": "ceylon", "colombo": "ceylon", "burma": "burma", "china": "china",
    "spain": "spain", "sweden": "sweden", "norway": "norway", "denmark": "denmark",
    "czechoslovakia": "czechoslovakia", "prague": "czechoslovakia",
    "greece": "greece", "turkey": "turkey", "canada": "canada", "egypt": "egypt",
    "travancore": "india", "cochin": "india", "malabar": "india", "sind": "india",
    "gujarat": "india", "maharashtra": "india", "karnataka": "india",
    "andhra": "india", "orissa": "india", "bihar": "india", "rajasthan": "india",
    "dacca": "bangladesh", "east bengal": "bangladesh", "burma": "burma",
    "kolhapur": "india", "madura": "india", "madurai": "india", "karwar": "india",
    "mylapore": "india", "saurashtra": "india", "rajkot": "india",
    "south africa": "south-africa", "johannesburg": "south-africa",
    "australia": "australia", "sydney": "australia", "melbourne": "australia",
    "ireland": "ireland", "dublin": "ireland", "mauritius": "mauritius",
    "vietnam": "vietnam", "saigon": "vietnam", "new zealand": "new-zealand",
    "lyon": "france", "louvain": "belgium", "brussels": "belgium",
}
# A bare place, with no origin verb, is an ADDRESS. The schema defaults
# nationality to india, so an Indian address is already handled by the default
# and is left alone; a FOREIGN address is acted on, because the error it
# prevents (filing Martin S. Dworkin of New York as Indian) is the worse one.
# An institution is not a homeland, so "graduated ... from Cambridge" and
# "a graduate of Sydney University" are refused.
INSTITUTION_RX = re.compile(
    r"\b(universit\w+|college|school|institute|graduat\w+|studi\w+|degree|"
    r"professor|lecturer|fellow|read\s+(?:for|at))\b", re.I)
# Origin constructions. "studied at", "read at", "visited", "lectured in" are
# NOT here on purpose — they say where someone went, not where they are from.
ORIGIN_RX = re.compile(
    r"\b(?:was\s+)?born\s+(?:in|at)\s+([A-Za-z.\u2019' ]{3,30})"
    r"|\bnative\s+of\s+([A-Za-z.\u2019' ]{3,30})"
    r"|\bcomes?\s+from\s+([A-Za-z.\u2019' ]{3,30})"
    r"|\bcitizen\s+of\s+([A-Za-z.\u2019' ]{3,30})"
    r"|\bhails?\s+from\s+(?:the\s+)?([A-Za-z.\u2019' ]{3,30})"
    r"|\bis\s+from\s+([A-Za-z.\u2019' ]{3,30})"
    r"|\ban?\s+([A-Za-z]{4,20})\s+by\s+birth", re.I)


def vocations_from(evidence: list[str]) -> list[str]:
    """Only `vocation_evidence` is passed in — never the whole contributor note.

    Reading the note wholesale made A. H. Somjee ("Reader in Political Science
    at M. S. University of Baroda") an economist, because somewhere across ten
    notes he reviewed something economic.
    """
    blob = " ".join(e for e in evidence if e).lower()
    if not blob.strip():
        return []
    out = []
    for voc, rx in VOCATION_RX:
        if re.search(rx, blob, re.I) and voc not in out:
            out.append(voc)
    return out[:4]                       # four is plenty; the rest is noise


def nationality_from(evidence: list[str]) -> tuple[str | None, str | None]:
    """Return (country slug, the printed phrase it rests on) — or (None, None).

    Two things count, and nothing else: an adjectival nationality ("an Austrian
    by birth", "is one of the major figures in Hungarian short story"), or a
    place inside an explicit origin construction ("born in Russia 1902, has
    lived in Israel since 1920"). A place someone merely studied, lectured or
    published in does not count, and a NAME never counts — that is the field
    where guessing would label Ignazio Silone and Denis de Rougemont Indian.
    """
    for e in evidence:
        if not e:
            continue
        low = " " + re.sub(r"\s+", " ", e.lower()) + " "
        for adj, country in ADJECTIVAL.items():
            for m in re.finditer(rf"\b{re.escape(adj)}\b", low):
                if LANG_CONTEXT.search(low[:m.start()]) or LANG_SUFFIX.match(low[m.end():]):
                    continue
                return country, e.strip()
        m = ORIGIN_RX.search(low)
        if m:
            place = next((g for g in m.groups() if g), "").strip(" .'\u2019")
            place = re.sub(r"\.", " ", place)      # "U.S.A." -> "U S A "
            for key in sorted(PLACE_COUNTRY, key=len, reverse=True):
                if re.search(rf"\b{re.escape(key)}\b", place):
                    return PLACE_COUNTRY[key], e.strip()
    for e in evidence:                          # bare foreign address, last
        if not e:
            continue
        low = " " + re.sub(r"\s+", " ", e.lower()) + " "
        if INSTITUTION_RX.search(low):
            continue
        for key in sorted(PLACE_COUNTRY, key=len, reverse=True):
            if PLACE_COUNTRY[key] == "india":
                continue
            if re.search(rf"\b{re.escape(key)}\b", low):
                return PLACE_COUNTRY[key], e.strip()
    return None, None


# ── issue citation ───────────────────────────────────────────────────────────

def issue_labels() -> dict[str, str]:
    """QT029 -> "No. 29 (Jan./Mar. 1961)", read off the published work so the
    citation is the designation Quest itself printed."""
    out = {}
    for p in sorted(WORKS.glob("qt[0-9][0-9][0-9].md")):
        m = FM_RX.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        pub = fm.get("publication") or {}
        num = str(pub.get("series") or "").strip()
        ed = str(pub.get("edition") or "").strip()
        # Quest numbered itself two ways: "Vol. I No. 1" early, a bare issue
        # number from 1958. The edition usually REPEATS the number and adds the
        # date, so quoting both gave "No. Vol. I No. 1 (Vol. I No. 1, August
        # 1955)". Take the number as printed and keep only what the edition
        # adds to it.
        label = num if re.match(r"(?i)^(vol|no)\b", num) else (f"No. {num}" if num else p.stem.upper())
        extra = ed
        if num:
            extra = re.sub(re.escape(num), "", extra, flags=re.I)
        extra = extra.strip(" ,;:()-\u2014").strip()
        if extra and norm(extra) != norm(label):
            label += f" ({extra})"
        out[p.stem.upper()] = label
    return out


ROLE_WORD = {
    "author": "wrote for", "translator": "translated for",
    "editor": "edited", "reviewer": "reviewed for",
    "illustrator": "illustrated", "photographer": "illustrated",
}


def compose_body(canonical: str, recs: list[tuple[str, dict]], labels: dict[str, str]) -> str:
    """A profile body that says only what Quest printed, and cites it.

    It does NOT enumerate the issues: ThinkerDetail.astro already builds
    "Works in the archive" from the resolved `authors[]`/`contributors[]`, so
    listing eighteen issue designations in prose only duplicated it badly.
    """
    roles, issues = set(), []
    for qt, r in recs:
        for role in (r.get("roles") or ["author"]):
            roles.add(str(role).lower())
        if qt not in issues:
            issues.append(qt)
    verbs = sorted({ROLE_WORD.get(x, "contributed to") for x in roles})
    verb = verbs[0] if len(verbs) == 1 else "contributed to"
    n = len(issues)
    where = "one issue" if n == 1 else f"{n} issues"
    lead = (f"{canonical} {verb} *Quest*, the journal of ideas sponsored by the "
            f"Indian Committee for Cultural Freedom, appearing in {where} of "
            f"the archive's run ({labels.get(issues[0], issues[0])}"
            + (f" to {labels.get(issues[-1], issues[-1])}" if n > 1 else "") + ").")

    quotes = []
    for qt, r in recs:
        # One issue can print the same person twice — QT033 gives Satish
        # Saberwal a biography in BOTH the contributors and the reviewers
        # block, and the harvest keeps the second as additional_note_verbatim.
        for key, pkey in (("note_verbatim", "note_printed_page"),
                          ("additional_note_verbatim", "additional_note_printed_page")):
            note = (r.get(key) or "").strip()
            if not note:
                continue
            page = r.get(pkey)
            cite = labels.get(qt, qt) + (f", p. {page}" if page else "")
            block = "\n".join("> " + ln.strip() for ln in note.splitlines() if ln.strip())
            quotes.append(f"*Quest*'s contributor note in {cite} reads:\n\n{block}")
        if len(quotes) >= 2:                   # two printed notes are enough
            break

    parts = [lead]
    if quotes:
        parts.append("\n\n".join(quotes))
    else:
        parts.append("*Quest* printed no contributor note for them; this page "
                     "records the bylines themselves, pending further research.")
    return "\n\n".join(parts) + "\n"


# ── frontmatter ──────────────────────────────────────────────────────────────

def compose_frontmatter(slug: str, canonical: str, forms: list[str],
                        recs: list[tuple[str, dict]]) -> tuple[dict, dict]:
    ev_voc = [r.get("vocation_evidence") for _, r in recs]
    ev_nat = [r.get("nationality_evidence") for _, r in recs]
    notes = [r.get("note_verbatim") for _, r in recs]
    notes += [r.get("additional_note_verbatim") for _, r in recs]
    has_note = any(n for n in notes)

    aka = [f for f in forms if norm(f) != norm(canonical)]
    vocs = vocations_from(ev_voc)
    country, phrase = nationality_from(ev_nat)

    fm = {
        "id": slug,
        "name": {"canonical": canonical, "sort": sort_key(canonical),
                 "also_known_as": aka},
        "tradition": "unclassified",          # CCS's call, not ours
        "canon_status": "unclassified",
        "nationality": country,               # dropped below when unevidenced
        "vocations": vocs,
        "themes": [],
        "affiliations": [],
        "bio_source": "ai_drafted" if has_note else "ai_drafted_stub",
        "needs_review": True,
        "draft": False,
        "ai": {"drafted_by": "claude-opus-5",
               "drafted_at": date.today().isoformat(),
               "model_version": "quest-contributor-harvest-2026-09"},
    }
    if country is None:
        del fm["nationality"]                 # schema default; see docstring
    unclassified = None
    if country is None:
        unclassified = next((e for e in ev_nat if e), None)
    return fm, {"nationality_phrase": phrase, "has_note": has_note,
                "nationality_unclassified": unclassified}


def dump_md(fm: dict, body: str) -> str:
    y = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=100000)
    return f"---\n{y}---\n\n{body}"


# ── main ─────────────────────────────────────────────────────────────────────

def given_name_clash(form: str, tid: str, canon_by_id: dict[str, str]) -> bool:
    """The rule the byline guard enforces on works, applied to profiles too.

    A single-token name matches an existing person ONLY when the token is their
    surname or a distinct byname — never when it is their GIVEN name. Quest
    QT011 carries a Marathi poem bylined simply "Indira"; the authority lists
    "Indira" as an alias of Indira Gandhi, and the first pass of this script
    duly proposed filing Quest's poet under her. Surnames still resolve:
    "Kolakowski" -> l-kolakowski is right.
    See scripts/synthesis/guard-byline-aliases.py.
    """
    toks = tokens(form)
    if len(toks) != 1:
        return False
    canon = canon_by_id.get(tid)
    if not canon:
        return False
    ctoks = tokens(canon)
    return len(ctoks) >= 2 and toks[0] == ctoks[0]


def main() -> int:
    argv = sys.argv[1:]
    write = "--write" in argv
    do_auth = "--authority" in argv
    if not write and "--audit" not in argv:
        print(__doc__); return 2

    rows = load_harvest()
    groups, freq, unnamed = cluster(rows)
    auth, files, taken, canon_by_id = existing_people()
    labels = issue_labels()

    new, existing, held, collisions, merged = [], [], [], [], []
    canonicals: list[str] = []

    # One person printed with and without a middle initial is one person.
    # Their records sit in different clusters because no single record carried
    # both forms, so join them here before anything is written.
    best: dict[str, str] = {}
    for key, recs in groups.items():
        forms = [d for _, r in recs for d in clean_forms(r)]
        if forms:
            best[key] = max(forms, key=lambda f: (freq.get(norm(f), 0), *name_quality(f)))
    ext_merges = []
    keys = sorted(best)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            if a in groups and b in groups and is_extension(best[a], best[b]):
                groups[a].extend(groups.pop(b))
                ext_merges.append((best[a], best[b]))

    for qt, r in unnamed:
        held.append((record_forms(r)[0], [qt], "one byline names several people"))

    for key, recs in sorted(groups.items()):
        raw_forms, forms = [], []
        for _, r in recs:
            for f in record_forms(r):
                if norm(f) not in {norm(x) for x in raw_forms}:
                    raw_forms.append(f)
            for d in clean_forms(r):
                if norm(d) not in {norm(x) for x in forms}:
                    forms.append(d)
        issues = sorted({q for q, _ in recs})
        has_note = any((r.get("note_verbatim") or "").strip() for _, r in recs)
        # best display form: the one Quest printed most often, then the fullest
        canonical = max(forms, key=lambda f: (freq.get(norm(f), 0), *name_quality(f)))

        reason = None
        if norm(canonical) in STOP_NAMES:
            reason = "names no person"
        elif all(is_initials_only(f) for f in forms):
            reason = "initials only"
        elif len(tokens(canonical)) > 5:
            reason = "phrase, not a name"
        elif len(tokens(canonical)) == 1 and not has_note:
            reason = "single-token name with no printed biography"
        if reason:
            held.append((canonical, issues, reason)); continue

        canonicals.append(canonical)
        if len(forms) > 1:
            merged.append((canonical, raw_forms, issues))

        hit = None
        for f in forms + raw_forms:
            cand = files.get(norm(f)) or auth.get(norm(f))
            if cand and not given_name_clash(f, cand, canon_by_id):
                hit = cand; break
        if hit:
            existing.append((canonical, hit, forms, issues)); continue

        slug = slugify(canonical)
        if not slug:
            held.append((canonical, issues, "unsluggable")); continue
        if slug in taken:
            collisions.append((canonical, slug, issues)); continue
        taken.add(slug)
        fm, meta = compose_frontmatter(slug, canonical, forms, recs)
        body = compose_body(canonical, recs, labels)
        new.append((slug, canonical, fm, body, meta, recs))

    dupes = [d for d in near_duplicates(canonicals)
             if d not in {tuple(sorted(m)) for m in ext_merges}]

    print(f"harvest        {len(rows)} records across {len({q for q, _ in rows})} issues")
    print(f"people         {len(groups)} clusters ({len(merged)} merged from variants)")
    print(f"already known  {len(existing)}")
    print(f"new profiles   {len(new)}")
    print(f"held back      {len(held)}")
    print(f"slug clashes   {len(collisions)}")
    print(f"merged on initials {len(ext_merges)} (e.g. \"Feroze Moos\" into \"Feroze F. Moos\")")
    print(f"look-alikes    {len(dupes)} pairs flagged for review")
    nat = sum(1 for *_x, m, _r in new if m["nationality_phrase"])
    bio = sum(1 for *_x, m, _r in new if m["has_note"])
    print(f"               {bio} of the new have a printed biography; "
          f"{nat} have printed nationality evidence")

    if write:
        for slug, _c, fm, body, _m, _r in new:
            (THINKERS / f"{slug}.md").write_text(dump_md(fm, body), encoding="utf-8")
        print(f"wrote {len(new)} profiles to {THINKERS}")
        if do_auth:
            update_authority(new, existing)

    write_report(rows, groups, new, existing, held, collisions,
                 merged + [(a, [a, b], ["same person, one form carries a middle initial"])
                           for a, b in ext_merges], dupes)
    print(f"report -> {REPORT.relative_to(REPO)}")
    return 0


def update_authority(new, existing) -> None:
    """Add the new people to the authority file so emit-astro-md.py resolves
    their bylines, and add Quest's name variants for people already there."""
    doc = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in doc["thinkers"] if t.get("id")}
    lookup = doc.setdefault("byline_lookup", {})
    added_people = added_keys = 0
    for slug, canonical, fm, _b, _m, _r in new:
        if slug not in by_id:
            entry = {"id": slug,
                     "name": {"canonical": canonical, "sort": fm["name"]["sort"]},
                     "confidence": "high",
                     "sources": ["data/quest-contributors/ (printed Quest bylines)"]}
            aka = fm["name"].get("also_known_as") or []
            if aka:
                entry["name"]["also_known_as"] = aka
            doc["thinkers"].append(entry); by_id[slug] = entry; added_people += 1
        for form in [canonical, *(fm["name"].get("also_known_as") or [])]:
            k = norm(form)
            if k and k not in lookup:
                lookup[k] = slug; added_keys += 1
    for canonical, tid, forms, _issues in existing:
        for form in forms:
            k = norm(form)
            if k and k not in lookup:
                lookup[k] = tid; added_keys += 1
    doc["thinkers"].sort(key=lambda t: t.get("id") or "")
    doc["byline_lookup"] = dict(sorted(lookup.items()))
    doc["_meta"]["counts"]["total"] = len(doc["thinkers"])
    doc["_meta"]["quest_harvest_applied"] = date.today().isoformat()
    AUTHORITY.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"authority: +{added_people} people, +{added_keys} byline keys "
          f"(total {len(doc['thinkers'])})")


def write_report(rows, groups, new, existing, held, collisions, merged, dupes) -> None:
    L = ["# Quest author profiles — build report", "",
         f"Generated {date.today().isoformat()} from "
         f"`data/quest-contributors/` ({len(rows)} records, {len(groups)} people).", "",
         "`tradition` and `canon_status` are left **unclassified** on every new "
         "profile: Quest published poets, musicologists and French art critics, "
         "and CCS has a thinker-classification round-trip for this.", ""]

    by_reason = defaultdict(list)
    for c, iss, reason in held:
        by_reason[reason].append((c, iss))
    L += [f"## Held back — {len(held)} bylines, no page written", ""]
    for reason in sorted(by_reason):
        L += [f"**{reason}** ({len(by_reason[reason])})", ""]
        for c, iss in sorted(by_reason[reason]):
            L.append(f"- `{c}` — {', '.join(iss)}")
        L.append("")
    L += ["An initials-only page would be junk and would merge everyone sharing "
          "the initials; \"L.F.\" would also split Laeeq Futehally, who has a "
          "profile from her named bylines. A single-token name with no printed "
          "biography is too thin to attach to a person.", ""]

    L += [f"## Look-alike clusters — {len(dupes)} pairs, for review", "",
          "These may be one person under two spellings, but no single harvest "
          "record listed both forms, so they were NOT merged. Merging on "
          "similarity alone would be worse: \"S. P. Aiyar\"/\"S. P. Aiyer\" is one "
          "person, \"K. Mukerji\"/\"Arati Mukerji\" is two.", ""]
    for a, b in dupes:
        L.append(f"- `{a}` / `{b}`")

    L += ["", f"## Merged from name variants — {len(merged)} people", "",
          "Merged because a single harvest record listed both forms. Surnames "
          "are not required to agree; several Quest contributors published "
          "under two.", ""]
    for c, forms, iss in sorted(merged):
        L.append(f"- **{c}** ← {', '.join(f'`{f}`' for f in forms)} ({', '.join(iss)})")

    L += ["", f"## Already in the archive — {len(existing)} people", "",
          "These keep their existing page. Their Quest name variants are added "
          "to the authority file as aliases so future emits resolve them.", ""]
    for c, tid, _f, iss in sorted(existing):
        L.append(f"- {c} → `{tid}` ({', '.join(iss)})")

    if collisions:
        L += ["", f"## Slug clashes — {len(collisions)}, NOT written", "",
              "The slug is taken by someone whose name did not match, so these "
              "are two different people spelling to one slug. Needs a human.", ""]
        for c, s, iss in sorted(collisions):
            L.append(f"- {c} → `{s}` (taken) — {', '.join(iss)}")

    with_note = sum(1 for *_x, m, _r in new if m["has_note"])
    nonat = [c for _s, c, fm, _b, m, _r in new if not m["nationality_phrase"]]
    unclass = [(c, m["nationality_unclassified"]) for _s, c, _f, _b, m, _r in new
               if m.get("nationality_unclassified")]
    L += ["", f"## New profiles — {len(new)}", "",
          f"{with_note} carry a biography Quest printed, quoted verbatim with "
          f"the issue cited. {len(new) - with_note} have no printed note and "
          "are marked `ai_drafted_stub`.", "",
          f"{len(nonat)} have no printed nationality evidence, so the "
          "`nationality` key is omitted and the schema's `india` default "
          "applies. That default is the archive's existing behaviour for all "
          "718 earlier thinkers; it is recorded here rather than asserted.", ""]
    if unclass:
        L += ["", f"### Nationality evidence printed but not classified — {len(unclass)}", "",
              "A phrase was printed but it does not state an origin in a form "
              "this script will act on, so no `nationality` was set and the "
              "schema default applies. Worth a human eye: Robert Antoine is "
              "here, whose note says only that he studied at Louvain and came "
              "to India in 1939.", ""]
        for c, phrase in sorted(unclass):
            L.append(f"- **{c}** — \"{phrase[:160]}\"")
        L.append("")
    for slug, c, fm, _b, m, recs in sorted(new, key=lambda x: x[1]):
        bits = [f"`{slug}`"]
        if fm.get("nationality"):
            bits.append(f"nationality **{fm['nationality']}** ← \"{m['nationality_phrase']}\"")
        if fm["vocations"]:
            bits.append("vocations " + ", ".join(fm["vocations"]))
        bits.append(f"{len({q for q, _ in recs})} issue(s)")
        L.append(f"- **{c}** — " + "; ".join(bits))
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
