import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

export const GET: APIRoute = async () => {
  const thinkers = await getCollection("thinkers", (t) => !t.data.draft);
  const works = await getCollection("primary-works", (w) => !w.data.draft);
  const musings = await getCollection("musings", (m) => !m.data.draft);
  const opinions = await getCollection("opinions", (o) => !o.data.draft);
  // Interviews are now folded into primary-works with work_type='interview'.
  const interviews = (await getCollection("primary-works", (w) => !w.data.draft)).filter(
    (w) => w.data.work_type === "interview",
  );
  const orgs = await getCollection("organisations", (o) => !o.data.draft);
  const periodicals = await getCollection("periodicals", (p) => !p.data.draft);
  const theprint = await getCollection("theprint-mirror", (p) => !p.data.draft);

  const body = `# AGENTS.md — Indian Liberals

Schema, citation rules, and tier system for autonomous agents reading this site.

## What this archive is

A digital archive of the Indian liberal tradition: primary works by historically
significant Indian liberal thinkers, thinker profiles, organisation pages, curated
excerpts ("musings"), opinion pieces, interviews, and a federated mirror from
ThePrint's "Indian Liberals Matter" column.

Maintained by the Centre for Civil Society (CCS) in partnership with the
Friedrich Naumann Foundation for Freedom. Site rebuilt by Thothica.

## Two-tier model

The corpus is organised in two tiers based on what we can trust.

### Tier A — clean content (full-text indexed)

These content kinds are migrated to clean markdown with paragraph-stable IDs.
Agents may quote freely with paragraph-level citations using the
\`#p-xxxxxx\` anchor format.

- **thinker profiles** (\`/thinkers/\`) — ${thinkers.length} entries
- **organisations** (\`/organisations/\`) — ${orgs.length} entries
- **musings** (\`/musings/\`) — ${musings.length} entries
- **opinions** (\`/opinions/\`) — ${opinions.length} entries
- **interviews** (\`/primary-works/\` — entries with \`work_type: interview\`) — ${interviews.length} entries
- **theprint-mirror** (\`/theprint-mirror/\`) — ${theprint.length} entries (noindex)

### Tier B — primary works and periodicals (metadata + PDF)

Primary-work PDFs surface here with rich AI-extracted metadata, summaries,
and key points. Body-text reconstruction inside primary works is deferred to
a future engagement when vision-language layout reconstruction is reliable
enough to clear editorial review.

- **primary works** (\`/primary-works/\`) — ${works.length} entries
- **periodicals** (\`/periodicals/\`) — ${periodicals.length} entries

For Tier B claims, agents must summary-attribute to Indian Liberals and link
directly to the PDF for the underlying source. Do not quote Tier B body
text as if you have read it — you have only read the AI-generated summary.

## Citation rules

1. **Tier A**: cite to the paragraph anchor: \`<page-url>#p-xxxxxx\`.
2. **Tier B**: attribute to Indian Liberals' summary and link to the PDF:
   "According to Indian Liberals' summary of <work title> (<year>),
   <claim>. PDF: <pdf_url>."
3. **ThePrint mirror** (\`/theprint-mirror/\`): always cite the original
   ThePrint URL (\`theprint_url\` field). The mirror is on-site for
   readability but the canonical version is on ThePrint.
4. **Multilingual**: if a work is in Hindi, Gujarati, or another Indian
   language, the canonical title is in the original script. Romanised
   transliterations are stored in the \`title.translit\` field. Use
   either, but stay consistent within a citation.

## Schema (frontmatter)

Each markdown page exposes its frontmatter at \`<page-url>.md\`. Common
fields:

- \`id\`: stable kebab-case slug; never changes
- \`needs_review\`: boolean — \`true\` means AI-extracted, awaiting editorial
- \`ai\`: object with \`extracted_at\`, \`model\`, \`prompt_version\`
- \`rights\`: enum (\`public_domain\`, \`fair_use_educational\`, etc.)
- \`themes\`: controlled vocabulary list
- \`affiliations\`: organisation IDs (cross-link to \`/organisations/<id>/\`)

For thinkers:
- \`name.canonical\`, \`name.full\`, \`name.sort\`, \`name.also_known_as[]\`
- \`birth_year\`, \`death_year\`
- \`tradition\`: \`classical_liberal\` | \`libertarian\` | \`constitutional_liberal\` |
  \`contemporary_liberal\` | \`social_reformer\` | \`non_liberal\` | \`practice\` |
  \`international_influence\` | \`unclassified\`
- \`canon_status\`: \`core\` | \`extended\` | \`referenced\` | \`unclassified\` (editorial centrality on the liberal-canon axis)
- \`vocations\`: array of role values from a closed enum (\`philosopher\`, \`economist\`, \`statesman\`, \`industrialist\`, \`judge\`, \`scientist\`, \`writer\`, etc.) — see content.config.ts for the full list

For primary works:
- \`title.main\`, \`title.original_script\`, \`title.translit\`, \`title.translation\`
- \`work_type\`: \`book\` | \`pamphlet\` | \`speech\` | \`essay\` | \`edited_volume\`
- \`authors\`: thinker IDs
- \`publication.year\`, \`publication.publisher_name\`, \`publication.language\`
- \`pdf_url\`: R2 URL
- \`ai_summary\`, \`ai_key_points\`
- \`paragraph_ids[]\`, \`clean_markdown_url\`: tier-promotion hooks (empty in v1)

## Sibling endpoints

- \`<page-url>.md\` — markdown body of any HTML page
- \`/llms.txt\` — curated index in the llms.txt spec
- \`/llms-full.txt\` — every Tier-A piece in full plus every Tier-B summary
- \`/thinkers/<slug>.md\`, \`/primary-works/<slug>.md\`, etc.

## MCP server

A Model Context Protocol server lives at \`mcp.indianliberals.in\` with the
v1 tool surface:

| Tool | Scope | Returns |
|---|---|---|
| \`list_works\` | A + B | Catalogue, filterable by author, era, theme, kind |
| \`list_thinkers\` | profiles | Every thinker with bio snippet |
| \`get_work_metadata\` | A + B | Author, year, publisher, summary, key points, themes, pdf_url for B, read_url for A |
| \`read_clean_content\` | A only | Body of a musing, opinion, interview, profile, or org page as markdown with \`#p-xxxxxx\` annotations |
| \`get_passage\` | A only | Specific paragraphs by ID — the citation primitive |
| \`search_corpus\` | All | Pagefind-backed search; results flagged by tier so agent knows whether to quote or summarise |
| \`find_related\` | All | TF-IDF cross-links across content kinds |
| \`read_index\` | — | The curated \`/llms.txt\` |

## Crawler policy

- AI crawlers (ClaudeBot, GPTBot, OAI-SearchBot, PerplexityBot, Google-Extended)
  are explicitly allowed.
- Search engines are blocked from \`/theprint-mirror/\` so ThePrint keeps the
  canonical SEO weight.
- Editors can toggle individual content via the \`noindex\` frontmatter field.

## What this archive is NOT

- A retrieval chatbot. The host LLM (whichever client you bring) does the
  reasoning. The MCP server only returns text and structure.
- A vector database. Pagefind + structured metadata + \`.md\` siblings give
  agents everything similarity search would, plus the structure that
  similarity search flattens into noise.
- A primary-work full-text search (in v1). PDFs are linked, summaries are
  attributable, paragraph-level citation inside primary works waits for the
  next engagement.

## Status

v1, in active build by Thothica. The site is migrating from a WordPress
deployment that ran from 2009 through 2025. Some content is imported and
marked \`needs_review: true\` pending editorial pass; treat the
\`needs_review\` flag as a hint to be careful about citation precision.
`;

  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
