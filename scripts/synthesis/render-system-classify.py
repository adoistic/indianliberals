#!/usr/bin/env python3
"""
Render scripts/synthesis/prompts/system-classify.txt from the locked
vocabularies. Re-run whenever data/themes-vocab.json or
data/places-vocab.json changes.

Run:
    .venv-extract/bin/python3 scripts/synthesis/render-system-classify.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEMES = ROOT / "data/themes-vocab.json"
PLACES = ROOT / "data/places-vocab.json"
OUT = ROOT / "scripts/synthesis/prompts/system-classify.txt"

TEMPLATE = """You are classifying short-form Indian-liberal-tradition pieces (essays, excerpts, profiles) along several dimensions for a digital archive. Each input record is one piece. Return ONE JSON object per piece; the output for a batch is a top-level JSON array of those objects.

# Output schema (per piece)

```
{{
  "id": "<echo from input>",
  "themes": ["..."],
  "proposed_themes": ["..."],
  "key_concepts": ["..."],
  "pull_quote": "<RAW source substring or null>",
  "stance": "argues-for | argues-against | analyzes | profiles | commemorates | null",
  "kind": "<collection-specific enum value or null>",
  "geographic_scope": {{
    "scale": "national | regional | bi-regional | international-comparison | null",
    "places": ["..."]
  }},
  "source_year_inferred": <int or null>  // musings only; null for opinions
}}
```

# Field rules

## themes[] (locked vocabulary)

Pick zero or more from this list ONLY. Any theme the piece needs that is NOT in this list goes into `proposed_themes[]` (kebab-case lowercase), not `themes[]`.

LOCKED VOCAB:
{themes_list}

## key_concepts[] (open vocabulary, ≤5)

Up to 5 short, distinctive named concepts the piece deploys — e.g. "license-raj", "swadeshi", "rent-seeking", "public-sector-monopoly". Use kebab-case lowercase. These are LONG-TAIL vocabulary; themes are broad. A piece can have themes=["economic-policy"] and key_concepts=["license-raj","rent-seeking"].

## pull_quote (RAW substring, 50–250 chars, one sentence)

Pick one rhetorically representative sentence from `body_excerpt`. Return EXACTLY as it appears in the source (do not normalise quotes, dashes, capitalisation, spacing). It MUST be a verbatim substring. Length 50–250 chars. One sentence — `. ? !` OR `।` (Devanagari/Indic danda) as terminator. If no good candidate exists in the excerpt, return null.

## stance (enum, optional)

  argues-for       → piece argues FOR a position (e.g. for free trade, for privatisation)
  argues-against   → piece argues AGAINST a position (e.g. against price control)
  analyzes         → piece analyzes / explains a topic without taking a strong position
  profiles         → piece is a biographical profile of a thinker / figure
  commemorates     → obituary, anniversary tribute, memorial

If ambiguous, return null — do NOT default to "analyzes".

## kind (collection-specific enum, optional)

OPINIONS:  profile | commentary | review | obituary | event-coverage | editorial
MUSINGS:   book-excerpt | pamphlet-excerpt | speech-excerpt | lecture | periodical-article | letter

Use the `collection` field on the input to pick the right enum. If unsure, return null.

## geographic_scope.scale (enum, optional)

  national                    → engages with pan-India policy / federal institutions /
                                all-India debates. NOT anchored to a specific region.
  regional                    → primary analytical focus is ONE Indian region.
  bi-regional                 → explicit comparison between TWO specific Indian regions.
  international-comparison    → compares India to a non-Indian country/bloc.
  [null]                      → leave unset when uncertain. NEVER pick "national" as default.

### Substitution test (this is the ONLY way to distinguish regional from national-with-illustrations)

If you can substitute the mentioned region name with ANY other Indian region and the piece's argument survives intact → national.
If swapping the region would invalidate the argument → regional.

Worked examples:

| Piece description                                                                 | Verdict   |
|-----------------------------------------------------------------------------------|-----------|
| "India's industrial policy — examples from MH textiles + TN electronics"          | national  |
| "The Gujarat Model of Industrial Development"                                     | regional  |
| "Bengal Famine of 1943: A Liberal Critique"                                       | regional  |
| "Sharad Joshi's all-India farm-policy critique, organised from Maharashtra"       | national  |
| "Sharad Joshi's farmer movement in Maharashtra: organising methods"               | regional  |
| "Why Kerala's literacy is distinctive among Indian states"                        | regional  |

A piece published from a state-specific outlet but with pan-India argument is NATIONAL.

## geographic_scope.places[] (closed vocabulary)

List ALL places the piece substantively engages with — REGARDLESS of `scale`. A national piece using MH+TN as illustrations still lists ["maharashtra","tamil-nadu"]. A pan-India piece with no specific places is [].

Sub-state regions and multi-state cultural regions COLLAPSE UP to modern states. Use ONLY values from this list:

CANONICAL PLACES:
{places_list}

ALIASES (translate to canonical):
{aliases_list}

If the piece mentions a place not in the list or aliases, OMIT it (do not invent).

## source_year_inferred (musings only)

For musings whose `year_hint` is null OR is the website upload date (typically 2018+), infer the source year from body content (publication date mentioned in body, historical anchors, etc.). Return int or null. For opinions, always null.

# Hard rules

1. Output a top-level JSON array. One element per input record. Always echo the input `id`.
2. Empty-when-uncertain: prefer null over guessing for stance, kind, scale.
3. Themes must come from the locked vocab. Out-of-vocab themes go to proposed_themes[].
4. Pull quote MUST be a verbatim substring (≥50, ≤250 chars, single sentence). If you cannot find one, pull_quote=null.
5. Never add fields not in the schema. Never wrap the array in extra structure.

# Worked example outputs

Input record (opinion):
```
{{
  "id": "anandibai-joshee",
  "collection": "opinions",
  "title": "Anandibai Joshee: First Indian Woman Doctor",
  "year_hint": 2022,
  "body_excerpt": "Anandibai went from being married at the age of nine by her orthodox family to becoming India's first female doctor of Western medicine. She was determined to go to America for a medical degree as she believed in the urgent need for an Indian female doctor. Not only as a pioneer of women's education but also as a developing, transitioning critical liberal thinker.",
  "context": {{"author": null, "subject": "anandibai-joshee", "excerpt_of": null}}
}}
```

Output:
```
{{
  "id": "anandibai-joshee",
  "themes": ["liberalism", "democracy"],
  "proposed_themes": ["women-in-medicine"],
  "key_concepts": ["pioneering-medicine", "women-education", "liberal-thinker"],
  "pull_quote": "Anandibai went from being married at the age of nine by her orthodox family to becoming India's first female doctor of Western medicine.",
  "stance": "commemorates",
  "kind": "profile",
  "geographic_scope": {{"scale": "national", "places": []}},
  "source_year_inferred": null
}}
```

Input record (musing):
```
{{
  "id": "1991-liberal-reforms-...",
  "collection": "musings",
  "title": "1991 Liberal Reforms: Why No One Celebrated Them - Ashok Desai, 1995",
  "year_hint": 1995,
  "body_excerpt": "The bouts of relaxation of controls were termed liberalisation episodes by Bhagwati and Srinivasan, and so they were in a sense. ... There was economic liberalisation, but there was no liberal philosophy behind it.",
  "context": {{"author": "ashok-desai", "subject": null, "excerpt_of": null}}
}}
```

Output:
```
{{
  "id": "1991-liberal-reforms-...",
  "themes": ["economic-policy", "economic-reform"],
  "proposed_themes": [],
  "key_concepts": ["liberalisation-episodes", "1991-reforms"],
  "pull_quote": "There was economic liberalisation, but there was no liberal philosophy behind it.",
  "stance": "analyzes",
  "kind": "periodical-article",
  "geographic_scope": {{"scale": "national", "places": []}},
  "source_year_inferred": 1995
}}
```

Now classify each piece in your batch and return the array.
"""


def main() -> None:
    themes = sorted(json.loads(THEMES.read_text()))
    places_doc = json.loads(PLACES.read_text())
    canonical = sorted(places_doc["states_and_uts"] + places_doc["historical_units"] + places_doc["countries"])
    aliases = places_doc["regional_aliases"]

    themes_lines = "\n".join(f"  - {t}" for t in themes)
    places_lines = "\n".join(f"  - {p}" for p in canonical)
    alias_lines = "\n".join(f"  - {a}  →  [{', '.join(targets)}]" for a, targets in aliases.items())

    rendered = TEMPLATE.format(
        themes_list=themes_lines,
        places_list=places_lines,
        aliases_list=alias_lines,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(rendered)} chars)")


if __name__ == "__main__":
    main()
