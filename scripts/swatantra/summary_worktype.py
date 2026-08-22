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
PATTERNS = [
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


def classify(summary):
    """Return (work_type, cue) inferred from a summary, or (None, None)."""
    if not summary:
        return None, None
    head = " ".join(summary.split())[:WINDOW].lower()
    for rx, wt in PATTERNS:
        if re.search(rx, head):
            return wt, rx
    return None, None
