#!/usr/bin/env python3
"""Deterministic publication year from the archivist's filename.

721 of the 6,355 Swatantra works carry no year: the model looked at the page
and found no date it trusted. For 258 of them the cataloguer had already typed
the date into the filename, exactly as with work_type.

    2933-The_Presidents_Report_on_Political_Developments_21-07-1970.pdf

That file's record says `year: null, confidence: low`. The date is right there
in the name.

ONE RULE, and it is the opposite of the work_type module's: the filename may
only FILL a missing year, never replace one the model supplied. A year read off
a title page is evidence about the document; a year in a filename is evidence
about the cataloguer. Where they disagree the model wins and the disagreement
is reported rather than resolved, because a mismatch usually means the filename
records when a letter was RECEIVED or filed, not when it was written.

    from filename_year import derive, apply
"""
import re

# The archive id leads every filename ("2933-The_Presidents..."). Those digits
# look exactly like a year for anything catalogued between 1900 and 2026, so
# they must come off before any year matching. Without this, 1971-Letter_to_X
# silently acquires the year 1971 from its accession number.
_ARCHIVE_ID = re.compile(r"^\d+[A-Za-z]?-")

# Most-specific first: a full d-m-Y beats a bare year in the same string.
_DMY = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})-((?:19|20)\d{2})(?!\d)")
_MY = re.compile(r"(?<!\d)(\d{1,2})-((?:19|20)\d{2})(?!\d)")
_Y = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

LO, HI = 1900, 2026


def derive(filename):
    """Return (year, cue) from a filename, or (None, None)."""
    stem = re.sub(r"\.pdf$", "", filename, flags=re.I)
    stem = _ARCHIVE_ID.sub("", stem)
    for cue, rx, grp in (("dmy", _DMY, 3), ("my", _MY, 2), ("year", _Y, 1)):
        m = rx.search(stem)
        if m:
            y = int(m.group(grp))
            if LO <= y <= HI:
                return y, cue
    return None, None


def apply(filename, model_year):
    """Resolve filename evidence against the model's answer.

    Returns (year, source) where source is one of:
        "model"     the model supplied a year, or there is nothing to add
        "filename"  the model had none and the filename supplied one
        "agree"     both said the same thing
        "conflict"  both spoke and disagreed — the MODEL's year is returned
    """
    y, _cue = derive(filename)
    if model_year is not None:
        if y is None:
            return model_year, "model"
        return (model_year, "agree" if y == model_year else "conflict")
    if y is None:
        return None, "model"
    return y, "filename"
