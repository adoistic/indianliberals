# Per-subagent extraction spec

Each subagent is dispatched with one entry from `data/extract/inventory.json` and reads that PDF directly via Claude's vision (the Read tool can read PDFs natively, including non-Roman scripts — Devanagari, Gujarati, etc.).

## What you do, in order

1. **Read the PDF** at the absolute path `pdf_full_path`. For large PDFs (>10 pages) you MUST use the `pages` parameter. Recommended approach:
   - First call: `pages: "1-10"` to read the front matter (title page, copyright, TOC, preface, first chapter opening).
   - If you need more context to write a good summary, do a second read with a later range like `pages: "20-30"` or whatever looks substantive based on what you saw in the front matter.
   - Don't try to read the whole PDF — front matter + a representative chapter is enough for a 200–400 word summary.

2. **Understand the work.** It will be in Marathi, Gujarati, or Hindi (Devanagari/Gujarati script). Claude can read these directly from the rendered PDF pages.

3. **Produce ENGLISH output.** Site readers are English-speaking; don't write the summary in the source language.

4. **Write a single JSON file** at `/Users/siraj/Indian Liberals Website/data/extract/output-<id>.json` with this exact shape:

```json
{
  "id": "<entry-id-echoed-from-input>",
  "summary": "<200-400 word English prose, 2-4 paragraphs, describing what the work argues / contains / is about>",
  "ai_key_points": [
    "Short single-sentence bullet 1.",
    "Bullet 2.",
    "...5-8 bullets total. Each captures a distinct claim, theme, or noteworthy passage."
  ],
  "themes": ["..."],
  "source_year_inferred": 1992,
  "needs_review": false
}
```

5. **Reply** with exactly `wrote output-<id>.json` and nothing else.

## Field rules

### themes (locked vocabulary)

Pick zero or more from this list ONLY. Anything else gets dropped silently — do not invent themes.

```
agriculture
banking
civil-liberties
civil-society
democracy
economic-development
economic-freedom
economic-growth
economic-planning
economic-policy
economic-reform
fiscal-policy
free-enterprise
free-markets
globalisation
governance
industrial-policy
inflation
liberalism
mixed-economy
monetary-policy
nationalisation
political-economy
private-enterprise
public-finance
public-sector
rule-of-law
social-reform
socialism
taxation
```

### summary

- 200–400 words, 2–4 paragraphs.
- ENGLISH. Even when the source is Marathi/Gujarati/Hindi.
- Describe: what kind of work it is (book / collected essays / periodical issue / pamphlet / etc.), who the author/editor is, the central argument or contents, where it sits in the Indian liberal tradition. Concrete details — names, places, dates, specific arguments — from the actual PDF.
- Do NOT pad with generic praise. Do NOT speculate about content you didn't read.
- Mention the source language ("This Marathi-language book…") when it adds context.

### ai_key_points

- 5–8 bullets, each a single English sentence.
- Each captures a distinct claim, theme, or noteworthy passage you actually saw in the rendered pages.
- Use exact names (people, places, organisations) when they appear.

### source_year_inferred

- Year the work was first published. Find it on the title page, copyright page, or preface.
- Integer between 1800 and 2027.

### needs_review

- Set to `true` only if the PDF was unreadable, the rendered pages were too sparse to assess content, or you had to guess substantially.
- Otherwise `false`.

## Hard rules

- **Do not hallucinate content.** If you can't make sense of the PDF, set `needs_review: true` and write a brief summary describing what you COULD see (e.g., "Title page indicates X; rendered pages were too damaged to extract substantive content").
- **Do not write the summary in the source language.** Always English.
- **Do not modify any file other than your output JSON.** Don't touch the source MD, don't touch the PDF, don't run scripts.
- **Output is plain JSON.** No markdown code fences around it. No commentary before or after.
- **Echo the `id` exactly** as given to you in the input.

## Reference: existing already-extracted entries

The 326 already-extracted entries (e.g., `apps/site/src/content/primary-works/aandolan-anant-umrikar.md` which has `needs_extraction: true` but was partially summarized) show the expected shape. The applier will use your JSON to fill in the same fields.
