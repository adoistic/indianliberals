# OG social cards

Every detail page with a picture advertises itself with a branded 1200x630
card on R2 under `og/`, addressed by convention (`og/w/<work>.jpg`,
`og/t/<thinker>.jpg`, `og/m/<musing>.jpg`, `og/o/<opinion>.jpg`); the section
mosaics and the home card live beside them. `apps/site/src/lib/og.ts` builds
the URLs; nothing per-entry is stored in frontmatter.

`og_cards.py` is the whole per-entry pipeline: it reads the content
collections, decides what each card should say (title, eyebrow, byline) and
show (cover / portrait / hero image), and re-renders only cards whose inputs
changed, tracked through `og/manifest.json` on R2.

**Nobody runs this by hand for routine edits.** The GitHub workflow
`og-cards.yml` runs it on every push that touches works, thinkers, musings or
opinions, uploading through the CMS Worker's `/api/og-put` (shared secret
`OG_PUSH_TOKEN`, set on both the workflow and the Worker). A new work gets its
card within minutes of the content landing; a changed title or replaced cover
regenerates it the same way.

Local use (bulk rebuilds, testing):

```sh
# render whatever changed and upload with the wrangler OAuth session
python3 scripts/og/og_cards.py sync --out /tmp/og_out --wrangler

# force a full re-render; preview without uploading
python3 scripts/og/og_cards.py sync --all --out /tmp/og_out --no-upload --limit 20
```

Needs `pillow` (the wheels bundle libraqm, which Devanagari/Bengali/Gujarati
titles require for correct shaping) and `pyyaml`. The fonts in `fonts/` are
TTF conversions of the site's own fontsource packages plus Noto Serif Bengali;
the crane comes from `apps/site/public/brand/`. The palette and geometry are
sampled from the original cards, so a re-render sits beside a 2026-07 card
without a visible seam.

Section mosaics (`og/home.jpg`, `og/<section>.jpg`) are not re-rendered here;
they change only when the shelf as a whole changes character.
