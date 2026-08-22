#!/usr/bin/env python3
"""Infer work_type from the model's own summary prose.

949 Swatantra works carry work_type `occasional_paper`. That value is not a
description, it is the model's shrug: the schema's least specific print type,
chosen when nothing on the page said what the document was. It is 15% of the
corpus and the largest single quality gap in the extraction.

But the summary usually says outright what the model was looking at:

    "This one-page English telegram, issued under the Swatantra Party
     president's identification, requests ..."
    "This four-page Swatantra Party note by Dr. R. C. Cooper challenges ..."

That sentence is evidence the work_type field threw away. This reads it back.

Only the OPENING of the summary counts. A letter that discusses a resolution
mentions "resolution" in its body; a letter that IS a resolution says so in its
first clause. The window is the first 200 characters, which in practice is the
"This <n>-page <form> ..." opening the prompt asks for.

    from summary_worktype import classify
"""
import re

# Ordered: the first match wins, so compounds precede their parts.
#
# The archival forms come FIRST. An affidavit that mentions a letter it
# encloses is an affidavit; a receipt for a telegram is a receipt. The
# publication-oriented patterns below assume the document is a piece of
# writing, and would happily call either of those a letter.
PATTERNS = [
    (r"\bconstitution\b|\brules and regulations\b|\bbye-?laws\b", "constitution"),
    (r"\bagreement\b|\bcoalition arrangement\b|\bmemorandum of understanding\b", "agreement"),
    (r"\baffidavit\b|\bplaint\b|\bpetition(?:ers)?\b|\bwrit\b|\bjudg?ment\b|\binjunction\b|\bcourt\b", "legal_filing"),
    (r"\breceipt\b|\bvoucher\b|\bsubscription\b|\bstatement of accounts\b|\bfinancial (?:calculation|statement)\b|\baccounts\b", "financial_record"),
    (r"\bblank form\b|\bproforma\b|\b(?:application|membership|nomination|pledge|enrol?ment) form\b", "form"),
    (r"\bprogramme\b|\binvitation\b|\bagenda\b|\bitinerary\b|\breception committee\b", "programme"),
    (r"\bnotice\b|\bintimation\b|\bannounces\b|\bannouncing\b", "notice"),
    (r"\broster\b|\blist of\b|\bregister of\b|\bdirectory\b|\bnames and addresses\b", "roster"),
    (r"\bclipping\b|\bcutting\b|\bpress copy\b|\btimes of india\b|\bindian express\b|\bthe hindu\b|\bhindustan times\b|\bthe statesman\b", "press_clipping"),
    (r"\bsynopsis\b|\bproceedings\b|\bdossier\b|\breport\b", "report"),
    (r"\baide-?memoire\b|\bchecklist\b|\boffice[- ](?:paper|record|note)\b|\binternal record\b|\badministrative (?:record|sheet|note)\b|\bworking paper\b|\bmemo\b", "office_record"),
    (r"\bpress (?:note|statement|release)\b", "press_note"),
    (r"\bminutes\b", "minutes"),
    (r"\bcircular\b", "circular"),
    (r"\btelegram\b|\bcablegram\b", "telegram"),
    (r"\bresolution\b", "resolution"),
    (r"\bmemorandum\b", "pamphlet"),
    (r"\binterview\b", "interview"),
    (r"\blecture\b", "lecture"),
    (r"\b(?:speech|address delivered|presidential address)\b", "speech"),
    (r"\bnewspaper (?:report|article|clipping)\b|\bnews (?:report|clipping)\b", "essay"),
    (r"\b(?:letter|note to|covering note)\b", "letter"),
    (r"\bpamphlet\b|\bbooklet\b", "pamphlet"),
    (r"\breport\b|\bstatement\b|\bnote\b|\barticle\b", "essay"),
]

WINDOW = 200

# The archival forms get a much tighter window than the publication ones.
#
# "report", "notice", "programme" and the like are ordinary words: an essay
# ABOUT a report mentions one in its second sentence. Matching them anywhere in
# 200 characters dropped agreement with the model from 90.8% to 69.7% on works
# it had already typed. The document's own form is named in its opening clause
# -- "This one-page notice ...", "This two-page roster ..." -- so the archival
# patterns only look there.
# The opening CLAUSE, not a character count: "This two-page English roster,
# titled ..." names the form before its first comma. A character window either
# clips a long one or admits the sentence after it.
ARCHIVAL = {
    "constitution", "agreement", "legal_filing", "financial_record", "form",
    "programme", "notice", "roster", "press_clipping", "report", "office_record",
}


def classify(summary):
    """Return (work_type, cue) inferred from a summary, or (None, None)."""
    if not summary:
        return None, None
    flat = " ".join(summary.split()).lower()
    head, opening = flat[:WINDOW], flat.split(",")[0][:WINDOW]
    for rx, wt in PATTERNS:
        if re.search(rx, opening if wt in ARCHIVAL else head):
            return wt, rx
    return None, None
