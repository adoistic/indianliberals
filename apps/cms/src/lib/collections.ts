/**
 * Every kind of thing the archive holds, described in plain data.
 *
 * The site's real contract is `apps/site/src/content.config.ts`, which is Zod
 * and therefore only readable by a build. This file is the same 13 collections
 * said again as data the CMS can render: what the fields are called, what an
 * editor should type into them, which ones matter first, and which ones the
 * extraction pipeline fills in on its own.
 *
 * Two rules keep the two files honest with each other:
 *
 *   1. `required` here means the Zod field has no default and is not optional.
 *      A field with a default is not required, even when every existing file
 *      carries a value for it.
 *   2. Field names are the frontmatter keys. Nested keys use a dotted path,
 *      so `publication.year` is the `year` inside the `publication` object.
 *      Inside an `object-list` the names are relative to one row of the list,
 *      because a row has no fixed position to be dotted from.
 *
 * Where a field accepts entries from more than one collection the `collection`
 * value is pipe separated, for example `thinkers|organisations`. A picker
 * splits on the pipe and offers both.
 *
 * A note on themes. `themes`, `proposed_themes` and `related_themes` hold
 * lowercase hyphenated tags such as `economic-policy`. There is a `themes`
 * collection that will one day be the authority for them, but it has no
 * entries yet, so a picker built on it would offer an editor nothing. Until it
 * is populated these stay free tag lists.
 *
 * `id` is not a field an editor should ever invent twice: it is the file name
 * without its extension, and the site's slug-uniqueness check fails the build
 * if two files share one.
 */

export type FieldKind =
  | 'text' | 'textarea' | 'markdown' | 'number' | 'year' | 'boolean'
  | 'select' | 'multiselect' | 'date' | 'url' | 'slug'
  | 'reference'        // points at another collection
  | 'reference-list'   // many of them
  | 'string-list'      // free text tags
  | 'object' | 'object-list';

export interface Field {
  name: string;           // dotted path for nested fields, e.g. 'publication.year'
  label: string;          // sentence case, human words, not the field name
  kind: FieldKind;
  required: boolean;
  hint?: string;          // one plain sentence telling a non-technical editor what to put here
  options?: string[];     // for select / multiselect, taken from the Zod enum
  collection?: string;    // for reference / reference-list
  fields?: Field[];       // for object / object-list
  group: 'essential' | 'publication' | 'people' | 'classification' | 'files' | 'advanced';
  placeholder?: string;
}

export interface CollectionDef {
  id: string;             // 'primary-works'
  label: string;          // 'Primary works'
  singular: string;       // 'Primary work'
  description: string;    // one sentence an editor reads before choosing this type
  path: string;           // 'apps/site/src/content/primary-works'
  titleField: string;     // which field to show in lists
  slugFrom: string;       // which field to derive the filename from
  hasBody: boolean;       // does it carry markdown below the frontmatter
  bodyLabel?: string;
  fields: Field[];
}

// ─── Shared vocabulary ─────────────────────────────────────────────────

const LANGUAGES = ['en', 'hi', 'gu', 'mr', 'bn'];

const LANGUAGE_HINT =
  'The language this entry is written in. Leave it as en unless you are making a Hindi, Gujarati, Marathi or Bengali version of an existing page.';

// ─── Field builders reused across collections ──────────────────────────

/** The record identifier. Always the file name, always the web address. */
function idField(example: string, what: string): Field {
  return {
    name: 'id',
    label: 'Web address name',
    kind: 'slug',
    required: true,
    group: 'essential',
    placeholder: example,
    hint: `The short name that appears in the web address for ${what}. Lowercase words joined by hyphens, no spaces or punctuation. It must match the file name, and once the page is public it should not be changed, because old links would break.`,
  };
}

/** Translation plumbing. Present on most collections through i18nFields. */
function languageFields(self: string): Field[] {
  return [
    {
      name: 'language',
      label: 'Language of this page',
      kind: 'select',
      required: false,
      options: LANGUAGES,
      group: 'advanced',
      hint: LANGUAGE_HINT,
    },
    {
      name: 'translation_of',
      label: 'Translated from',
      kind: 'reference',
      required: false,
      collection: self,
      group: 'advanced',
      hint: 'If this page is a translation, pick the original entry it was translated from. Leave blank for an original.',
    },
    {
      name: 'translations',
      label: 'Other language versions',
      kind: 'object',
      required: false,
      group: 'advanced',
      hint: 'Every other language this same entry exists in. Both sides of a pair have to list each other, or the language links will point one way only.',
      fields: LANGUAGES.map((code) => ({
        name: `translations.${code}`,
        label: `Version in ${code}`,
        kind: 'reference' as FieldKind,
        required: false,
        collection: self,
        group: 'advanced' as const,
      })),
    },
    {
      name: 'translation_status',
      label: 'How this version was produced',
      kind: 'select',
      required: false,
      options: ['original', 'human_translation', 'ai_translation', 'needs_translation'],
      group: 'advanced',
      hint: 'Whether the author wrote it in this language, a person translated it, or a machine did. Machine translations stay hidden from search engines until someone checks them.',
    },
  ];
}

/** Audit trail written by the extraction scripts. Editors read, rarely write. */
function aiProvenanceFields(): Field[] {
  return [
    {
      name: 'ai',
      label: 'Machine extraction record',
      kind: 'object',
      required: false,
      group: 'advanced',
      hint: 'Filled in by the extraction scripts to record which model produced the summary and when. There is no reason to edit it by hand.',
      fields: [
        { name: 'ai.extracted_at', label: 'Extracted at', kind: 'text', required: false, group: 'advanced' },
        { name: 'ai.model', label: 'Model used', kind: 'text', required: false, group: 'advanced' },
        { name: 'ai.prompt_version', label: 'Prompt version', kind: 'text', required: false, group: 'advanced' },
      ],
    },
  ];
}

/** The two flags every collection ends with. */
function workflowFields(reviewHint: string): Field[] {
  return [
    {
      name: 'needs_review',
      label: 'Needs an editor to check it',
      kind: 'boolean',
      required: false,
      group: 'advanced',
      hint: reviewHint,
    },
    {
      name: 'draft',
      label: 'Keep as a draft',
      kind: 'boolean',
      required: false,
      group: 'advanced',
      hint: 'Tick this to keep the entry out of the public site. Untick it when the entry is ready for readers.',
    },
  ];
}

/** A verbatim quote lifted from a scanned page, with its provenance. */
function pullQuoteFields(): Field[] {
  return [
    { name: 'verbatim', label: 'The quote, word for word', kind: 'textarea', required: true, group: 'advanced', hint: 'Exactly what the page says, including any old spellings. Do not tidy it.' },
    { name: 'page', label: 'Page it appears on', kind: 'number', required: true, group: 'advanced' },
    { name: 'page_system', label: 'Which page numbering', kind: 'select', required: false, options: ['pdf', 'printed'], group: 'advanced', hint: 'Whether that page number is the one printed on the paper or the position of the sheet in the PDF.' },
    { name: 'why_notable', label: 'Why it is worth quoting', kind: 'select', required: true, options: ['framing', 'aphorism', 'data', 'counter_intuitive'], group: 'advanced' },
    { name: 'context', label: 'What is happening around it', kind: 'text', required: false, group: 'advanced' },
    { name: 'shareable', label: 'Good enough to share on its own', kind: 'boolean', required: false, group: 'advanced' },
    { name: 'translation', label: 'English rendering', kind: 'textarea', required: false, group: 'advanced', hint: 'An English version of the quote, when the original is in another language.' },
    {
      name: 'transcription_anomaly',
      label: 'Scanning error in the quote',
      kind: 'object',
      required: false,
      group: 'advanced',
      hint: 'Use this when the scan garbled a word and the quote had to keep the garble. Say what the page shows and what it was meant to say.',
      fields: [
        { name: 'observed', label: 'What the page shows', kind: 'text', required: true, group: 'advanced' },
        { name: 'likely_intended', label: 'What it probably meant', kind: 'text', required: true, group: 'advanced' },
        { name: 'note', label: 'Note', kind: 'text', required: false, group: 'advanced' },
      ],
    },
  ];
}

/** A person named in the body text, with the evidence that they are named. */
function crossThinkerMentionFields(): Field[] {
  return [
    { name: 'thinker_id', label: 'Thinker', kind: 'reference', required: false, collection: 'thinkers', group: 'advanced' },
    { name: 'thinker_id_unresolved', label: 'Name as printed', kind: 'text', required: false, group: 'advanced', hint: 'Use this when the person named on the page has no profile in the archive yet.' },
    { name: 'context', label: 'What is said about them', kind: 'text', required: false, group: 'advanced' },
    { name: 'page', label: 'Page', kind: 'number', required: false, group: 'advanced' },
    { name: 'page_system', label: 'Which page numbering', kind: 'select', required: false, options: ['pdf', 'printed'], group: 'advanced' },
  ];
}

/** The richer in-prose mention record used by the readable collections. */
function thinkerMentionsField(): Field {
  return {
    name: 'thinker_mentions',
    label: 'People discussed in the text',
    kind: 'object-list',
    required: false,
    group: 'people',
    hint: 'Everyone the text talks about, with a line saying what they contribute and a quote proving it. This is what fills the "Mentioned in" section of a person\'s profile.',
    fields: [
      { name: 'thinker', label: 'Thinker', kind: 'reference', required: false, collection: 'thinkers', group: 'people', hint: 'Pick the profile this mention refers to.' },
      { name: 'thinker_unresolved', label: 'Name as printed', kind: 'text', required: false, group: 'people', hint: 'Use this instead when the person has no profile in the archive yet.' },
      { name: 'role', label: 'How they figure in it', kind: 'select', required: true, options: ['author', 'subject', 'mention'], group: 'people', hint: 'Author if they wrote it, subject if the piece is about them, mention if they are only referred to.' },
      { name: 'reasoning', label: 'Why they matter here', kind: 'textarea', required: true, group: 'people', hint: 'One or two sentences saying what this person contributes to the piece. Readers see this on the profile page, so write it for them.' },
      {
        name: 'evidence',
        label: 'Quotes that prove the mention',
        kind: 'object-list',
        required: false,
        group: 'people',
        hint: 'One to three short quotes, copied exactly from the text. The build drops any quote it cannot find in the body.',
        fields: [
          { name: 'quote', label: 'Quote', kind: 'textarea', required: true, group: 'people' },
          { name: 'context', label: 'One line of context', kind: 'text', required: false, group: 'people' },
        ],
      },
      {
        name: 'key_passages',
        label: 'Highlights, for pieces about this person',
        kind: 'object-list',
        required: false,
        group: 'people',
        hint: 'Two to four passages worth pulling out, used only when the piece is about the person rather than merely mentioning them.',
        fields: [
          { name: 'quote', label: 'Passage', kind: 'textarea', required: true, group: 'people' },
          { name: 'what_it_shows', label: 'What it shows', kind: 'text', required: true, group: 'people' },
        ],
      },
    ],
  };
}

/** Copyright position. Decides whether the full text can be hosted. */
function rightsFields(): Field[] {
  return [
    {
      name: 'rights',
      label: 'Copyright position',
      kind: 'object',
      required: false,
      group: 'files',
      hint: 'What the archive is allowed to do with this document. If you are unsure, choose unknown and leave a note rather than guessing.',
      fields: [
        { name: 'rights.status', label: 'Status', kind: 'select', required: true, options: ['public_domain', 'fair_use_educational', 'permission_granted', 'takedown_on_request', 'unknown'], group: 'files', hint: 'Public domain if copyright has expired, permission granted if the holder said yes in writing, takedown on request for anything hosted on sufferance.' },
        { name: 'rights.pd_year', label: 'Year it entered the public domain', kind: 'year', required: false, group: 'files' },
        { name: 'rights.editorial_review_flag', label: 'A person should look at this again', kind: 'boolean', required: false, group: 'files' },
        { name: 'rights.notes', label: 'Notes on rights', kind: 'textarea', required: false, group: 'files', hint: 'Where permission came from, who granted it, or why the status is uncertain.' },
      ],
    },
  ];
}

/** Extent of the scan. Shared by primary works and periodicals. */
function physicalFields(): Field[] {
  return [
    {
      name: 'physical',
      label: 'The physical item',
      kind: 'object',
      required: false,
      group: 'publication',
      hint: 'How long the document is and how much of it the scan actually covers.',
      fields: [
        { name: 'physical.page_count', label: 'Page count', kind: 'number', required: false, group: 'publication', hint: 'The older page count field. Prefer filling in total pages below.' },
        { name: 'physical.page_count_visible', label: 'Pages visible in the scan', kind: 'number', required: false, group: 'publication', hint: 'An older field, kept so existing records still load. Use pages read instead.' },
        { name: 'physical.pages_rendered', label: 'Pages read by the extraction', kind: 'number', required: false, group: 'publication', hint: 'How many pages the summarising model actually saw. Filled in by the scripts.' },
        { name: 'physical.pages_total', label: 'Total pages in the file', kind: 'number', required: false, group: 'publication' },
        { name: 'physical.pages_total_source', label: 'How the total was counted', kind: 'select', required: false, options: ['pypdfium2', 'pdfinfo', 'toc_max', 'unknown'], group: 'publication', hint: 'Which tool produced the page total, so a surprising number can be traced back.' },
        { name: 'physical.format', label: 'Size and format', kind: 'text', required: false, group: 'publication', hint: 'How the item was printed, for example octavo, quarto or A5 pamphlet.' },
      ],
    },
  ];
}

/** The PDF and its cover. */
function pdfFields(what: string): Field[] {
  return [
    {
      name: 'pdf_url',
      label: 'PDF file',
      kind: 'url',
      required: false,
      group: 'essential',
      placeholder: 'https://archive.indianliberals.in/...',
      hint: `The web address of the scanned ${what} on the archive server. Without this the page has nothing for a reader to open, so add it as soon as the file is uploaded.`,
    },
    {
      name: 'pdf_staging_path',
      label: 'Where the file sits before upload',
      kind: 'text',
      required: false,
      group: 'files',
      hint: 'The path to the file on the curator\'s own drive, kept so an unpublished scan can still be found.',
    },
    { name: 'pdf_size_mb', label: 'File size in MB', kind: 'number', required: false, group: 'files' },
  ];
}

/** Structured summary payload, written by the summarising pass. */
function summaryStructuredField(): Field {
  return {
    name: 'summary_structured',
    label: 'Structured summary',
    kind: 'object',
    required: false,
    group: 'advanced',
    hint: 'The machine-made breakdown that sits behind the written summary: key points, quotes, and how much of the item was read.',
    fields: [
      { name: 'summary_structured.key_points', label: 'Key points', kind: 'string-list', required: false, group: 'advanced' },
      { name: 'summary_structured.themes_confirmed', label: 'Themes found in the text', kind: 'string-list', required: false, group: 'advanced' },
      { name: 'summary_structured.pull_quotes', label: 'Pull quotes', kind: 'object-list', required: false, group: 'advanced', fields: pullQuoteFields() },
      { name: 'summary_structured.cross_thinker_mentions', label: 'People named in the text', kind: 'object-list', required: false, group: 'advanced', fields: crossThinkerMentionFields() },
      {
        name: 'summary_structured.summary_completeness',
        label: 'How much was read',
        kind: 'object',
        required: false,
        group: 'advanced',
        fields: [
          { name: 'based_on_pages', label: 'Pages the summary is based on', kind: 'string-list', required: true, group: 'advanced', hint: 'The first and last page the model read, as two numbers.' },
          { name: 'covers_full_work', label: 'Covers the whole item', kind: 'boolean', required: true, group: 'advanced' },
          { name: 'missing_content_note', label: 'What was missed', kind: 'textarea', required: false, group: 'advanced' },
        ],
      },
    ],
  };
}

/** Entities the extraction met but could not match to an existing record. */
function authorityAdditionsField(): Field {
  return {
    name: 'recommended_authority_additions',
    label: 'People and bodies worth adding',
    kind: 'object-list',
    required: false,
    group: 'advanced',
    hint: 'Names the extraction found in the text but could not match to anything in the archive. An editor decides whether each one deserves its own record.',
    fields: [
      { name: 'kind', label: 'What sort of name', kind: 'select', required: true, options: ['thinker', 'publisher', 'organisation'], group: 'advanced' },
      { name: 'verbatim', label: 'Name as printed', kind: 'text', required: true, group: 'advanced' },
      { name: 'language', label: 'Language of the name', kind: 'text', required: false, group: 'advanced' },
      { name: 'context', label: 'Where it came up', kind: 'text', required: false, group: 'advanced' },
      { name: 'page', label: 'Page', kind: 'number', required: false, group: 'advanced' },
      { name: 'page_system', label: 'Which page numbering', kind: 'select', required: false, options: ['pdf', 'printed'], group: 'advanced' },
    ],
  };
}

/** The two legacy summary fields kept for records imported from the old database. */
function legacySummaryFields(): Field[] {
  return [
    { name: 'ai_summary', label: 'Older machine summary', kind: 'markdown', required: false, group: 'advanced', hint: 'A summary written by an earlier version of the pipeline. New records use the written summary field instead.' },
    { name: 'ai_key_points', label: 'Older key points', kind: 'string-list', required: false, group: 'advanced', hint: 'Key points from the earlier pipeline, kept so imported records still show something.' },
  ];
}

/**
 * The classification dimensions musings and opinions share. Written by the
 * classifying pass and corrected by editors.
 */
function classificationFields(): Field[] {
  return [
    { name: 'proposed_themes', label: 'Themes suggested by the machine', kind: 'string-list', required: false, group: 'classification', hint: 'Themes the classifier proposed but nobody has confirmed. Move the good ones up into the themes field and delete the rest.' },
    { name: 'key_concepts', label: 'Key ideas', kind: 'string-list', required: false, group: 'classification', hint: 'Up to five ideas the piece turns on, as lowercase hyphenated tags, for example industrial-licensing.' },
    { name: 'pull_quote', label: 'Quote to feature', kind: 'textarea', required: false, group: 'classification', hint: 'One sentence from the piece, copied exactly, that could stand alone on a card.' },
    { name: 'stance', label: 'What the piece does', kind: 'select', required: false, options: ['argues-for', 'argues-against', 'analyzes', 'profiles', 'commemorates'], group: 'classification', hint: 'Whether the piece takes a side, examines something, portrays a person, or marks an occasion.' },
    {
      name: 'geographic_scope',
      label: 'Where it is about',
      kind: 'object',
      required: false,
      group: 'classification',
      fields: [
        { name: 'geographic_scope.scale', label: 'Scale', kind: 'select', required: false, options: ['national', 'regional', 'bi-regional', 'international-comparison'], group: 'classification', hint: 'Whether it treats India as a whole, one part of it, two places together, or India against another country.' },
        { name: 'geographic_scope.places', label: 'Places named', kind: 'string-list', required: false, group: 'classification' },
      ],
    },
    { name: 'period_window', label: 'Period it belongs to', kind: 'select', required: false, options: ['pre-independence', 'nehruvian-era', 'late-license-raj', 'reform-era', 'post-reform'], group: 'classification', hint: 'The era the piece speaks from or about. Judge it by the argument, not only by the date it was published.' },
    { name: 'source_channel', label: 'Where it first appeared', kind: 'text', required: false, group: 'advanced', hint: 'The newspaper, magazine or platform that carried it first, when that is known.' },
  ];
}

const THEMES_FIELD: Field = {
  name: 'themes',
  label: 'Themes',
  kind: 'string-list',
  required: false,
  group: 'classification',
  hint: 'The subjects this belongs under, as lowercase hyphenated tags such as economic-policy or free-speech. Reuse tags that already exist rather than inventing near-duplicates.',
};

// ─── The collections ───────────────────────────────────────────────────

const thinkers: CollectionDef = {
  id: 'thinkers',
  label: 'Thinkers',
  singular: 'Thinker',
  description: 'A person in the Indian liberal canon, with a biography and links to everything they wrote.',
  path: 'apps/site/src/content/thinkers',
  titleField: 'name.canonical',
  slugFrom: 'name.canonical',
  hasBody: true,
  bodyLabel: 'Biography',
  fields: [
    idField('gopal-krishna-gokhale', 'this person'),
    { name: 'name.canonical', label: 'Name', kind: 'text', required: true, group: 'essential', hint: 'The name as it should appear at the top of the page, in the form the person is best known by.' },
    { name: 'name.sort', label: 'Name for alphabetical lists', kind: 'text', required: true, group: 'essential', placeholder: 'Gokhale, Gopal Krishna', hint: 'The same name rearranged so lists sort correctly, family name first, then a comma.' },
    { name: 'birth_year', label: 'Year of birth', kind: 'year', required: false, group: 'essential', hint: 'Leave blank if no source gives it. Do not estimate.' },
    { name: 'death_year', label: 'Year of death', kind: 'year', required: false, group: 'essential', hint: 'Leave blank if the person is living, or if no source gives it.' },
    {
      name: 'tradition',
      label: 'Strand of thought',
      kind: 'select',
      required: true,
      options: ['classical_liberal', 'constitutional_liberal', 'contemporary_liberal', 'international_influence', 'libertarian', 'non_liberal', 'practice', 'social_reformer', 'unclassified'],
      group: 'essential',
      hint: 'Which strand of liberal thinking this person belongs to. Choose unclassified if you are not sure and someone will settle it later. Do not choose international influence for new records: it is being retired.',
    },

    { name: 'name.full', label: 'Full name', kind: 'text', required: false, group: 'people', hint: 'The complete name with middle names and titles spelled out, when it differs from the name above.' },
    { name: 'name.also_known_as', label: 'Other names', kind: 'string-list', required: false, group: 'people', hint: 'Spellings and forms found in the sources, so a search for any of them finds this person.' },
    { name: 'name.honorifics', label: 'Titles and honorifics', kind: 'string-list', required: false, group: 'people', hint: 'Forms such as Sir, Dr or Rao Bahadur that appear before the name in printed sources.' },
    { name: 'nationality', label: 'Nationality', kind: 'text', required: false, group: 'people', placeholder: 'india', hint: 'Lowercase country name. Leave it as india unless the person was not Indian.' },
    { name: 'affiliations', label: 'Organisations they belonged to', kind: 'reference-list', required: false, collection: 'organisations', group: 'people', hint: 'The parties, societies and institutes this person worked in or led.' },

    { name: 'canon_status', label: 'Place in the canon', kind: 'select', required: false, options: ['core', 'extended', 'referenced', 'unclassified'], group: 'classification', hint: 'Core for the central classical liberal figures, extended for the wider liberal tradition, referenced for people who appear in the corpus but sit outside it.' },
    { name: 'featured', label: 'Show on the main thinkers page', kind: 'boolean', required: false, group: 'classification', hint: 'Only a small curated set appears on the front thinkers page. Everyone else stays findable through the full directory, so leaving this unticked hides nobody.' },
    {
      name: 'vocations',
      label: 'What they did',
      kind: 'multiselect',
      required: false,
      options: ['philosopher', 'economist', 'historian', 'political_scientist', 'sociologist', 'legal_scholar', 'scientist', 'engineer', 'professor', 'writer', 'editor', 'journalist', 'poet', 'statesman', 'parliamentarian', 'civil_servant', 'diplomat', 'judge', 'industrialist', 'entrepreneur', 'activist', 'reformer', 'religious_figure', 'military_officer', 'artist'],
      group: 'classification',
      hint: 'Pick every occupation that genuinely applies, not just the best known one.',
    },
    THEMES_FIELD,

    { name: 'portrait.photo', label: 'Photograph', kind: 'text', required: false, group: 'files', placeholder: '/thinkers/photos/gopal-krishna-gokhale.jpg', hint: 'The path to a photograph already uploaded to the site.' },
    { name: 'portrait.caricature', label: 'Drawing or caricature', kind: 'text', required: false, group: 'files', hint: 'Use this when no photograph survives but a drawing does.' },
    { name: 'portrait.ring_portrait', label: 'Circular portrait', kind: 'text', required: false, group: 'files', hint: 'A version cropped to a circle, used in small round frames.' },
    { name: 'portrait.duotone', label: 'Two-tone portrait', kind: 'text', required: false, group: 'files', hint: 'The uniform two-colour version used on the main thinkers page. It is generated from the photograph by a script.' },

    { name: 'bio_source', label: 'Where the biography came from', kind: 'select', required: false, options: ['canonical', 'feature_article', 'ai_drafted', 'ai_drafted_stub', 'imported'], group: 'advanced', hint: 'Canonical means a person at CCS wrote it. Change this to canonical once you have rewritten a machine-drafted biography.' },
    {
      name: 'intellectual_arc',
      label: 'How their thinking developed',
      kind: 'object',
      required: false,
      group: 'advanced',
      hint: 'A longer account of how this person\'s ideas changed over a lifetime. Produced by a later stage of the pipeline, so it is empty for most people.',
      fields: [
        { name: 'intellectual_arc.summary', label: 'Summary of the arc', kind: 'textarea', required: true, group: 'advanced' },
        {
          name: 'intellectual_arc.phases',
          label: 'Phases',
          kind: 'object-list',
          required: false,
          group: 'advanced',
          fields: [
            { name: 'label', label: 'Name of the phase', kind: 'text', required: true, group: 'advanced' },
            { name: 'key_works', label: 'Works from this phase', kind: 'reference-list', required: false, collection: 'primary-works', group: 'advanced' },
          ],
        },
        { name: 'intellectual_arc.influences.on_them', label: 'Who shaped them', kind: 'reference-list', required: false, collection: 'thinkers', group: 'advanced' },
        { name: 'intellectual_arc.influences.from_them', label: 'Who they shaped', kind: 'reference-list', required: false, collection: 'thinkers', group: 'advanced' },
        { name: 'intellectual_arc.core_questions', label: 'Questions they kept returning to', kind: 'string-list', required: false, group: 'advanced' },
      ],
    },
    ...languageFields('thinkers'),
    ...aiProvenanceFields(),
    ...workflowFields('Tick this when something about the person looks wrong or thin and another editor should look before readers do.'),
  ],
};

const contributors: CollectionDef = {
  id: 'contributors',
  label: 'Contributors',
  singular: 'Contributor',
  description: 'A present-day writer of opinion pieces, such as a CCS fellow or a guest author. Not the same as a thinker in the canon.',
  path: 'apps/site/src/content/contributors',
  titleField: 'name.canonical',
  slugFrom: 'name.canonical',
  hasBody: true,
  bodyLabel: 'Short biography',
  fields: [
    idField('sanjeet-kashyap', 'this writer'),
    { name: 'name.canonical', label: 'Name', kind: 'text', required: true, group: 'essential', hint: 'The name as it should appear in the byline of their pieces.' },
    { name: 'name.sort', label: 'Name for alphabetical lists', kind: 'text', required: true, group: 'essential', placeholder: 'Kashyap, Sanjeet', hint: 'The same name with the family name first, so lists sort correctly.' },
    { name: 'affiliation', label: 'Where they work', kind: 'text', required: false, group: 'essential', placeholder: 'Centre for Civil Society', hint: 'The organisation named in their biography note. Leave blank if the note does not say.' },
    { name: 'role', label: 'Their title', kind: 'text', required: false, group: 'essential', placeholder: 'Indian Liberal Fellow', hint: 'The title given in their biography note, such as Research Associate or Indian Liberal Fellow.' },

    { name: 'name.also_known_as', label: 'Other names', kind: 'string-list', required: false, group: 'people', hint: 'Other spellings that appear on their bylines, so the same person is not split across two records.' },
    { name: 'joined_at', label: 'Year they joined', kind: 'year', required: false, group: 'people', hint: 'The year they started at the organisation above. Leave blank if it is not stated anywhere.' },
    { name: 'areas_of_interest', label: 'What they write about', kind: 'string-list', required: false, group: 'classification', hint: 'Two or three subjects, taken from their own biography note rather than guessed from their pieces.' },
    { name: 'photo', label: 'Photograph', kind: 'text', required: false, group: 'files', placeholder: '/contributors/photos/sanjeet-kashyap.jpg', hint: 'The path to a photograph already uploaded to the site. Many imported biographies have none.' },

    { name: 'bio_source', label: 'Where the biography came from', kind: 'select', required: false, options: ['extracted_from_opinion_bio', 'curator', 'imported'], group: 'advanced', hint: 'Most were lifted automatically from the note at the foot of an opinion piece. Change it to curator once you have written the biography yourself.' },
    ...workflowFields('These records were pulled out of opinion pieces automatically, so most start needing a check. Untick it once you have confirmed the name, the title and the photograph.'),
  ],
};

const organisations: CollectionDef = {
  id: 'organisations',
  label: 'Organisations',
  singular: 'Organisation',
  description: 'A party, think tank, publisher or society that Indian liberals founded, led or wrote for.',
  path: 'apps/site/src/content/organisations',
  titleField: 'name.canonical',
  slugFrom: 'name.canonical',
  hasBody: true,
  bodyLabel: 'History and description',
  fields: [
    idField('forum-of-free-enterprise', 'this organisation'),
    { name: 'name.canonical', label: 'Name', kind: 'text', required: true, group: 'essential', hint: 'The name as it should appear on the page, in the form the organisation used itself.' },
    { name: 'name.sort', label: 'Name for alphabetical lists', kind: 'text', required: true, group: 'essential', hint: 'The name with any leading The removed, so lists sort on the first real word.' },
    {
      name: 'type',
      label: 'Kind of organisation',
      kind: 'select',
      required: true,
      options: ['political_party', 'think_tank', 'publisher_org', 'reform_society', 'professional_body', 'academic', 'international_network'],
      group: 'essential',
      hint: 'What sort of body it was. If it did several things, choose the one it is remembered for.',
    },
    { name: 'founded_year', label: 'Year founded', kind: 'year', required: false, group: 'essential', hint: 'Leave blank if the sources do not agree or do not say.' },
    { name: 'dissolved_year', label: 'Year it closed', kind: 'year', required: false, group: 'essential', hint: 'Leave blank if the organisation still exists.' },
    { name: 'description', label: 'Short description', kind: 'textarea', required: false, group: 'essential', hint: 'One or two sentences saying what the organisation was and why it belongs in this archive. This is what readers see on the listing cards.' },

    { name: 'name.full', label: 'Full name', kind: 'text', required: false, group: 'people', hint: 'The complete registered name, when the organisation is usually known by a shorter one.' },
    { name: 'name.also_known_as', label: 'Other names', kind: 'string-list', required: false, group: 'people', hint: 'Abbreviations and former names, so a search for any of them finds this record.' },
    { name: 'ideology', label: 'What it stood for', kind: 'string-list', required: false, group: 'classification', hint: 'A few lowercase hyphenated tags describing its politics, for example free-markets or constitutional-reform.' },
    { name: 'logo', label: 'Logo', kind: 'text', required: false, group: 'files', placeholder: '/organisations/logos/ccs.svg', hint: 'The path to a logo already uploaded to the site. Most defunct organisations have none, and the page draws a lettered tile instead.' },

    { name: 'hide_from_index', label: 'Keep off the organisations list', kind: 'boolean', required: false, group: 'advanced', hint: 'Tick this for bodies that are in the archive only because thinkers worked inside them, such as a large national party. The page still exists and still links from profiles: it just does not appear in the main list.' },
    ...languageFields('organisations'),
    ...workflowFields('Tick this when the dates, the type or the description need a second pair of eyes.'),
  ],
};

const musings: CollectionDef = {
  id: 'musings',
  label: 'Musings',
  singular: 'Musing',
  description: 'A readable extract from a longer work: a chapter, a speech or a passage worth reading on its own.',
  path: 'apps/site/src/content/musings',
  titleField: 'title',
  slugFrom: 'title',
  hasBody: true,
  bodyLabel: 'The extract',
  fields: [
    idField('1991-liberal-reforms-ashok-desai-1995', 'this extract'),
    { name: 'title', label: 'Title', kind: 'text', required: true, group: 'essential', hint: 'What the extract should be called. If the passage has no title of its own, write one that says what it is about, then the author and year.' },
    { name: 'pubDate', label: 'Date published', kind: 'date', required: true, group: 'essential', hint: 'When the original piece appeared. If only the year is known, use the first of January of that year.' },
    { name: 'author', label: 'Author', kind: 'reference', required: false, collection: 'thinkers', group: 'essential', hint: 'The person who wrote it. If they have no profile in the archive yet, create one first.' },
    { name: 'excerpt_of', label: 'Taken from', kind: 'reference', required: false, collection: 'primary-works', group: 'essential', hint: 'The full work this passage comes from, so readers can go from the extract to the whole document.' },
    {
      name: 'kind',
      label: 'Kind of extract',
      kind: 'select',
      required: false,
      options: ['book-excerpt', 'pamphlet-excerpt', 'speech-excerpt', 'lecture', 'periodical-article', 'letter'],
      group: 'essential',
      hint: 'What sort of thing the passage was taken out of.',
    },

    { name: 'hero_image', label: 'Picture at the top', kind: 'text', required: false, group: 'files', placeholder: '/musings/covers/some-slug.webp', hint: 'The path to an image already uploaded to the site. It appears on the listing card and across the top of the page.' },

    { name: 'related_thinkers', label: 'Other people it concerns', kind: 'reference-list', required: false, collection: 'thinkers', group: 'people', hint: 'People named in the passage who are neither its author nor its subject.' },
    thinkerMentionsField(),

    THEMES_FIELD,
    ...classificationFields(),
    ...languageFields('musings'),
    ...aiProvenanceFields(),
    ...workflowFields('Tick this when the transcription or the attribution needs checking against the original.'),
  ],
};

const opinions: CollectionDef = {
  id: 'opinions',
  label: 'Opinion pieces',
  singular: 'Opinion piece',
  description: 'A present-day article written for this site: commentary, a profile of a liberal figure, a review or an event report.',
  path: 'apps/site/src/content/opinions',
  titleField: 'title',
  slugFrom: 'title',
  hasBody: true,
  bodyLabel: 'The article',
  fields: [
    idField('anandibai-joshee-first-indian-woman-doctor', 'this article'),
    { name: 'title', label: 'Title', kind: 'text', required: true, group: 'essential', hint: 'The headline as readers should see it.' },
    { name: 'pubDate', label: 'Date published', kind: 'date', required: true, group: 'essential', hint: 'The day the piece went out. For older imported pieces, use the date on the original.' },
    { name: 'author_name', label: 'Byline', kind: 'text', required: true, group: 'essential', hint: 'The name to print under the headline. Write Editorial Team for pieces the office wrote collectively.' },
    { name: 'author', label: 'Writer', kind: 'reference', required: false, collection: 'contributors', group: 'essential', hint: 'The contributor record for the writer, when there is one. Leave blank for Editorial Team pieces.' },
    { name: 'subject', label: 'Person the piece is about', kind: 'reference', required: false, collection: 'thinkers', group: 'essential', hint: 'For a profile or an obituary, the person it portrays. This is what puts the piece on their profile page.' },
    {
      name: 'kind',
      label: 'Kind of piece',
      kind: 'select',
      required: false,
      options: ['profile', 'commentary', 'review', 'obituary', 'event-coverage', 'editorial'],
      group: 'essential',
      hint: 'What the article is: a portrait of a person, an argument, a book review, an obituary, a report on an event, or an unsigned editorial.',
    },

    { name: 'hero_image', label: 'Picture at the top', kind: 'text', required: false, group: 'files', placeholder: '/opinions/covers/some-slug.webp', hint: 'The path to an image already uploaded to the site. It appears on the listing card and across the top of the page.' },

    { name: 'related_thinkers', label: 'Other people it concerns', kind: 'reference-list', required: false, collection: 'thinkers', group: 'people', hint: 'People discussed in the piece besides its subject.' },
    thinkerMentionsField(),
    { name: 'related_works', label: 'Works it discusses', kind: 'reference-list', required: false, collection: 'primary-works', group: 'classification', hint: 'Documents in the archive that the article talks about, so a reader can go and read them.' },

    THEMES_FIELD,
    ...classificationFields(),
    ...languageFields('opinions'),
    ...aiProvenanceFields(),
    ...workflowFields('Tick this when the piece needs a second read before it goes out.'),
  ],
};

const primaryWorks: CollectionDef = {
  id: 'primary-works',
  label: 'Primary works',
  singular: 'Primary work',
  description: 'A scanned document from the archive: a book, pamphlet, speech, lecture, interview or paper, with its details and a link to the PDF.',
  path: 'apps/site/src/content/primary-works',
  titleField: 'title.main',
  slugFrom: 'title.main',
  hasBody: true,
  bodyLabel: 'Summary and key points',
  fields: [
    idField('planning-for-scarcity-b-r-shenoy-1965', 'this work'),
    { name: 'title.main', label: 'Title', kind: 'text', required: true, group: 'essential', hint: 'The title exactly as printed on the title page, including its capitalisation. Do not shorten it.' },
    {
      name: 'work_type',
      label: 'Kind of work',
      kind: 'select',
      required: true,
      options: ['book', 'pamphlet', 'speech', 'essay', 'edited_volume', 'occasional_paper', 'letter', 'correspondence', 'periodical_issue', 'reference', 'interview', 'lecture'],
      group: 'essential',
      hint: 'What sort of document this is. Choose edited volume when several authors contributed chapters, and lecture for a named annual or memorial lecture.',
    },
    {
      name: 'authors',
      label: 'Authors',
      kind: 'reference-list',
      required: false,
      collection: 'thinkers|organisations',
      group: 'essential',
      hint: 'Whoever wrote it, in the order printed on the title page. An author can be a person or a body such as a party or an institute.',
    },
    { name: 'publication.year', label: 'Year of publication', kind: 'year', required: false, group: 'essential', hint: 'The year the work was first published. Leave blank if the source does not say. Do not guess from the subject matter.' },
    { name: 'publication.language', label: 'Language of the work', kind: 'text', required: false, group: 'essential', placeholder: 'en', hint: 'The language the document itself is written in, as a two-letter code: en, hi, gu, mr or bn.' },
    ...pdfFields('document'),
    { name: 'summary', label: 'What this work argues', kind: 'markdown', required: false, group: 'essential', hint: 'Two to four paragraphs on what the work says and why it matters. This is the main thing a reader has to go on before opening the PDF.' },

    { name: 'title.subtitle', label: 'Subtitle', kind: 'text', required: false, group: 'publication', hint: 'The second half of the title, when the title page carries one.' },
    { name: 'title.original_script', label: 'Title in its own script', kind: 'text', required: false, group: 'publication', hint: 'The title in Devanagari, Gujarati, Bengali or whichever script it was printed in.' },
    { name: 'title.translit', label: 'Title spelled in English letters', kind: 'text', required: false, group: 'publication', hint: 'The sound of the original title written in the English alphabet.' },
    { name: 'title.translation', label: 'Title translated into English', kind: 'text', required: false, group: 'publication', hint: 'What the title means, for works not published in English.' },
    { name: 'purpose', label: 'More precisely, it is a', kind: 'select', required: false, options: ['manifesto', 'statement_of_principles', 'report', 'working_paper', 'position_paper', 'annual_report', 'anthology', 'festschrift', 'proceedings', 'memorial_volume', 'collected_works', 'treatise', 'memoir', 'biography', 'textbook', 'parliamentary', 'convocation', 'convention_address', 'inaugural', 'memorial_lecture'], group: 'publication', hint: 'An optional finer label under the kind of work above. Leave it blank if none of them fits.' },
    { name: 'publication.publisher_name', label: 'Publisher', kind: 'text', required: false, group: 'publication', hint: 'The publisher exactly as printed, usually on the title page or the last page.' },
    { name: 'publication.publisher_id', label: 'Publisher record', kind: 'reference', required: false, collection: 'organisations', group: 'publication', hint: 'The organisation record for that publisher, when the archive has one.' },
    { name: 'publication.issuer_id', label: 'Issuing body', kind: 'reference', required: false, collection: 'organisations', group: 'publication', hint: 'Use this only when the body that issued the document is not the one that printed it, as when a party issues a statement that a commercial press prints.' },
    { name: 'publication.place', label: 'Place of publication', kind: 'text', required: false, group: 'publication', placeholder: 'Bombay', hint: 'The city on the title page. Keep the name as printed, so Bombay stays Bombay.' },
    { name: 'publication.edition', label: 'Edition', kind: 'text', required: false, group: 'publication', hint: 'Only when the item says so, for example Second edition or Revised edition.' },
    { name: 'publication.series', label: 'Series line as printed', kind: 'text', required: false, group: 'publication', placeholder: 'Sixth A. D. Shroff Memorial Lecture', hint: 'The series wording exactly as it appears on the item. This is descriptive text only: it does not group anything.' },
    { name: 'publication.series_id', label: 'Part of the series', kind: 'reference', required: false, collection: 'series', group: 'publication', hint: 'The series this item actually belongs to, which is what groups it on the series pages. Choose the most specific one: a Shroff lecture belongs to the Shroff series, not to the wider booklet run.' },
    { name: 'publication.series_ordinal', label: 'Number within the series', kind: 'number', required: false, group: 'publication', hint: 'The number printed on the item. Leave blank for runs ordered by date rather than number.' },
    ...physicalFields(),
    {
      name: 'identifiers',
      label: 'Catalogue numbers',
      kind: 'object',
      required: false,
      group: 'publication',
      hint: 'Library reference numbers, when the item or a catalogue record carries them.',
      fields: [
        { name: 'identifiers.isbn', label: 'ISBN', kind: 'text', required: false, group: 'publication' },
        { name: 'identifiers.oclc', label: 'OCLC number', kind: 'text', required: false, group: 'publication' },
        { name: 'identifiers.lccn', label: 'Library of Congress number', kind: 'text', required: false, group: 'publication' },
      ],
    },
    {
      name: 'manifestations',
      label: 'Other printings',
      kind: 'object-list',
      required: false,
      group: 'publication',
      hint: 'Later reprints and new editions of this same work. Leave empty unless the work was reissued.',
      fields: [
        { name: 'year', label: 'Year', kind: 'year', required: true, group: 'publication' },
        { name: 'publisher_name', label: 'Publisher', kind: 'text', required: true, group: 'publication' },
        { name: 'place', label: 'Place', kind: 'text', required: false, group: 'publication' },
        { name: 'edition', label: 'Edition', kind: 'text', required: false, group: 'publication' },
        { name: 'pdf_url', label: 'PDF of this printing', kind: 'url', required: false, group: 'publication' },
      ],
    },

    { name: 'editors', label: 'Editors', kind: 'reference-list', required: false, collection: 'thinkers|organisations', group: 'people', hint: 'Whoever put the volume together, when that is someone other than the authors.' },
    {
      name: 'contributors',
      label: 'Everyone else involved',
      kind: 'object-list',
      required: false,
      group: 'people',
      hint: 'The full roster for a volume with several hands in it: chapter authors, translators, whoever wrote the foreword. Leave empty for a work by one author.',
      fields: [
        { name: 'thinker', label: 'Person', kind: 'reference', required: false, collection: 'thinkers', group: 'people' },
        { name: 'thinker_unresolved', label: 'Name as printed', kind: 'text', required: false, group: 'people', hint: 'Use this when the person has no profile in the archive yet.' },
        { name: 'role', label: 'What they did', kind: 'text', required: true, group: 'people', placeholder: 'translator', hint: 'One word: author, editor, translator, foreword, introduction, or whatever the item says.' },
        { name: 'toc_index', label: 'Their entry in the contents', kind: 'number', required: false, group: 'people', hint: 'The position of their chapter in the table of contents, counting from the top.' },
      ],
    },
    { name: 'speaker_name', label: 'Speaker', kind: 'text', required: false, group: 'people', hint: 'For a recorded talk or interview, the name of the person speaking when they have no profile in the archive and so cannot be listed as an author.' },
    { name: 'related_thinkers', label: 'People the work concerns', kind: 'reference-list', required: false, collection: 'thinkers', group: 'people', hint: 'People the work is about or argues with, other than its authors.' },
    thinkerMentionsField(),

    THEMES_FIELD,
    { name: 'related_works', label: 'Related works', kind: 'reference-list', required: false, collection: 'primary-works', group: 'classification', hint: 'Other documents in the archive a reader of this one should know about.' },
    { name: 'key_points', label: 'Key points', kind: 'string-list', required: false, group: 'classification', hint: 'A handful of one-line takeaways. Used for recorded talks and interviews.' },
    { name: 'description', label: 'Editorial note', kind: 'textarea', required: false, group: 'classification', hint: 'A short description written by a person, as opposed to the machine-written summary above.' },

    { name: 'youtube_url', label: 'YouTube video', kind: 'url', required: false, group: 'files', hint: 'For a recorded lecture or interview, the address of the video on YouTube.' },
    { name: 'transcript_status', label: 'State of the transcript', kind: 'select', required: false, options: ['none', 'partial', 'complete', 'unavailable'], group: 'files', hint: 'How much of the recording has been written out. Choose unavailable when no transcript can be made.' },
    { name: 'video_group', label: 'Which video shelf', kind: 'select', required: false, options: ['oral', 'talks', 'explainers', 'conversations'], group: 'files', hint: 'Where a recorded interview belongs on the interviews page: an oral history, a talk, an explainer or a conversation.' },
    { name: 'cover_image', label: 'Cover picture', kind: 'url', required: false, group: 'files', hint: 'A picture of the first page, used so listing pages look like a shelf rather than a list of titles. It is generated from the PDF.' },
    { name: 'clean_markdown_url', label: 'Full text file', kind: 'url', required: false, group: 'files', hint: 'The address of a cleaned-up text version of the work, once one exists.' },
    ...rightsFields(),

    { name: 'provenance.source', label: 'Where the scan came from', kind: 'select', required: true, options: ['ccs_archive', 'private_scan', 'source_library', 'unknown'], group: 'files', hint: 'Whether the file came from the CCS archive, a private scan, a library, or somewhere nobody recorded.' },
    { name: 'provenance.scan_quality', label: 'Quality of the scan', kind: 'select', required: false, options: ['good', 'fair', 'poor', 'unknown'], group: 'files', hint: 'How readable the pages are. Mark it poor when whole passages cannot be made out, so nobody trusts the summary too far.' },
    { name: 'provenance.notes', label: 'Notes on the scan', kind: 'textarea', required: false, group: 'files', hint: 'Missing pages, a broken spine, anything a reader should know before opening the file.' },

    summaryStructuredField(),
    {
      name: 'essays_summarized',
      label: 'Summaries of each chapter',
      kind: 'object-list',
      required: false,
      group: 'advanced',
      hint: 'For a volume with several authors, one summary per chapter. Written by the extraction, matched to the contents list by position.',
      fields: [
        { name: 'toc_index', label: 'Position in the contents', kind: 'number', required: true, group: 'advanced' },
        { name: 'author_resolved', label: 'Author', kind: 'reference', required: false, collection: 'thinkers', group: 'advanced' },
        { name: 'author_unresolved', label: 'Author name as printed', kind: 'text', required: false, group: 'advanced' },
        { name: 'summary', label: 'Summary', kind: 'markdown', required: true, group: 'advanced' },
        { name: 'partial_essay', label: 'Only part of it was read', kind: 'boolean', required: false, group: 'advanced' },
        { name: 'summary_structured.key_points', label: 'Key points', kind: 'string-list', required: false, group: 'advanced' },
        { name: 'summary_structured.pull_quotes', label: 'Pull quotes', kind: 'object-list', required: false, group: 'advanced', fields: pullQuoteFields() },
        { name: 'summary_structured.cross_thinker_mentions', label: 'People named', kind: 'object-list', required: false, group: 'advanced', fields: crossThinkerMentionFields() },
        { name: 'summary_structured.complete', label: 'The whole chapter was read', kind: 'boolean', required: true, group: 'advanced' },
        { name: 'summary_structured.seen_through_page', label: 'Read as far as page', kind: 'number', required: false, group: 'advanced' },
      ],
    },
    {
      name: 'toc',
      label: 'Table of contents',
      kind: 'object',
      required: false,
      group: 'advanced',
      hint: 'The contents list copied out and matched against the scanned pages. Empty for works by a single author.',
      fields: [
        { name: 'toc.extracted_from_pages', label: 'Pages the contents were read from', kind: 'string-list', required: false, group: 'advanced' },
        { name: 'toc.entries', label: 'Entries', kind: 'object-list', required: false, group: 'advanced', fields: tocEntryFields() },
        { name: 'toc.entries_not_yet_rendered', label: 'Entries not yet reached in the scan', kind: 'object-list', required: false, group: 'advanced', fields: tocEntryFields() },
      ],
    },
    {
      name: 'reading_guide',
      label: 'How to read it',
      kind: 'object',
      required: false,
      group: 'advanced',
      hint: 'Guidance for a reader coming to the work cold. Produced by a later stage of the pipeline, so it is empty for most works.',
      fields: [
        { name: 'reading_guide.how_to_approach', label: 'How to approach it', kind: 'textarea', required: false, group: 'advanced' },
        { name: 'reading_guide.difficulty', label: 'How hard it is', kind: 'select', required: false, options: ['introductory', 'intermediate', 'advanced'], group: 'advanced' },
        { name: 'reading_guide.estimated_minutes', label: 'Minutes to read', kind: 'number', required: false, group: 'advanced' },
        { name: 'reading_guide.prerequisites', label: 'Read these first', kind: 'reference-list', required: false, collection: 'primary-works', group: 'advanced' },
        { name: 'reading_guide.why_this_matters', label: 'Why it matters', kind: 'textarea', required: false, group: 'advanced' },
        {
          name: 'reading_guide.best_read_alongside',
          label: 'Read alongside',
          kind: 'object-list',
          required: false,
          group: 'advanced',
          fields: [
            { name: 'work_id', label: 'Work', kind: 'reference', required: true, collection: 'primary-works', group: 'advanced' },
            { name: 'relationship', label: 'How the two relate', kind: 'text', required: true, group: 'advanced' },
          ],
        },
      ],
    },
    {
      name: 'authors_resolution',
      label: 'How the authors were worked out',
      kind: 'object',
      required: false,
      group: 'advanced',
      hint: 'A record of how the byline was matched to profiles, so a wrong attribution can be traced back to whatever produced it.',
      fields: [
        { name: 'authors_resolution.confidence', label: 'How sure the match is', kind: 'select', required: false, options: ['high', 'medium', 'low'], group: 'advanced' },
        { name: 'authors_resolution.method', label: 'How it was matched', kind: 'select', required: false, options: ['deterministic', 'llm', 'vision'], group: 'advanced' },
        { name: 'authors_resolution.proposed_unknowns', label: 'Names it could not place', kind: 'string-list', required: false, group: 'advanced' },
        { name: 'authors_resolution.stubs_created', label: 'Placeholder profiles it created', kind: 'string-list', required: false, group: 'advanced' },
        { name: 'authors_resolution.stubs_referenced', label: 'Placeholder profiles it reused', kind: 'string-list', required: false, group: 'advanced' },
        { name: 'authors_resolution.collisions_logged', label: 'Names that clashed with existing profiles', kind: 'string-list', required: false, group: 'advanced' },
      ],
    },
    authorityAdditionsField(),
    { name: 'missing_metadata_flags', label: 'Details the extraction could not find', kind: 'string-list', required: false, group: 'advanced', hint: 'Short notes the extraction leaves for itself, such as title page not found. Each one is a gap for an editor to fill by hand.' },
    { name: 'extent_caveat', label: 'Warning about how little was read', kind: 'text', required: false, group: 'advanced', hint: 'Set when the summary rests on only a small part of the document. Leave blank when the whole thing was read, or write one line saying what the summary is actually based on.' },
    { name: 'toc_drift_detected', label: 'Contents list did not match the pages', kind: 'boolean', required: false, group: 'advanced', hint: 'Set by the extraction when the printed contents disagreed with where chapters actually start. Treat the page numbers as unreliable until someone checks.' },
    { name: 'needs_extraction', label: 'Still waiting to be read by the machine', kind: 'boolean', required: false, group: 'advanced', hint: 'Set on records that came from the old database with no text attached, so the summarising pass knows to pick them up.' },
    { name: 'dispatch_count', label: 'Extraction runs used', kind: 'number', required: false, group: 'advanced' },
    { name: 'paragraph_ids', label: 'Paragraph identifiers', kind: 'string-list', required: false, group: 'advanced', hint: 'Stable labels for individual paragraphs, so a citation can point at one. Empty until the full text is prepared.' },
    ...legacySummaryFields(),
    ...languageFields('primary-works'),
    ...aiProvenanceFields(),
    ...workflowFields('New works start needing a check, because the details are read off a scan by a machine. Untick it once you have compared the title, the author and the year against the title page.'),
  ],
};

/** One line of a table of contents. Used twice inside the primary work TOC. */
function tocEntryFields(): Field[] {
  return [
    { name: 'toc_index', label: 'Position in the contents', kind: 'number', required: true, group: 'advanced' },
    { name: 'title', label: 'Title as printed', kind: 'text', required: true, group: 'advanced' },
    { name: 'byline_verbatim', label: 'Byline as printed', kind: 'text', required: false, group: 'advanced' },
    { name: 'thinker_id_proposed', label: 'Suggested author profile', kind: 'reference', required: false, collection: 'thinkers', group: 'advanced' },
    { name: 'page_start', label: 'Starts on page', kind: 'number', required: true, group: 'advanced' },
    { name: 'page_end', label: 'Ends on page', kind: 'number', required: false, group: 'advanced' },
    { name: 'page_system', label: 'Which page numbering', kind: 'select', required: false, options: ['pdf', 'printed'], group: 'advanced' },
    { name: 'complete_in_chunk', label: 'Read from start to finish', kind: 'boolean', required: false, group: 'advanced' },
    { name: 'seen_through_page', label: 'Read as far as page', kind: 'number', required: false, group: 'advanced' },
    { name: 'virtual', label: 'Invented page window', kind: 'boolean', required: false, group: 'advanced', hint: 'Set when there was no real contents list and the extraction split a long work into page ranges of its own making.' },
  ];
}

const periodicals: CollectionDef = {
  id: 'periodicals',
  label: 'Periodicals',
  singular: 'Periodical issue',
  description: 'A single dated issue of a magazine or journal, with a summary of the articles inside it. Nothing has been filed under this type yet: issues currently live as primary works of the periodical issue kind.',
  path: 'apps/site/src/content/periodicals',
  titleField: 'publication_name',
  slugFrom: 'publication_slug',
  hasBody: true,
  bodyLabel: 'Summary of the issue',
  fields: [
    idField('the-indian-libertarian-1958-06-15', 'this issue'),
    { name: 'publication_name', label: 'Name of the magazine', kind: 'text', required: true, group: 'essential', placeholder: 'The Indian Libertarian', hint: 'The title of the magazine or journal, as printed on its masthead. Type it the same way on every issue.' },
    { name: 'publication_slug', label: 'Short name of the magazine', kind: 'slug', required: true, group: 'essential', placeholder: 'the-indian-libertarian', hint: 'The lowercase hyphenated form of the magazine name. Every issue of the same magazine must use exactly the same one, because that is what groups them together.' },
    { name: 'issue.date', label: 'Date of the issue', kind: 'date', required: false, group: 'essential', hint: 'The date printed on the cover. If it gives only a month, use the first of that month.' },
    { name: 'issue.volume', label: 'Volume', kind: 'text', required: false, group: 'essential', hint: 'The volume number on the cover, if there is one.' },
    { name: 'issue.number', label: 'Issue number', kind: 'text', required: false, group: 'essential', hint: 'The number of this issue within the volume, if there is one.' },
    { name: 'issue.label', label: 'How to name this issue', kind: 'text', required: false, group: 'essential', placeholder: 'Vol. VI, No. 12', hint: 'How the issue should be labelled on the page when volume and number alone would read awkwardly.' },
    ...pdfFields('issue'),
    { name: 'summary', label: 'What this issue covers', kind: 'markdown', required: false, group: 'essential', hint: 'A few paragraphs on what is in the issue, what its editorial line is, and which contributions stand out.' },

    { name: 'publisher_id', label: 'Publisher', kind: 'reference', required: false, collection: 'organisations', group: 'publication', hint: 'The organisation that published the magazine.' },
    ...physicalFields(),
    ...rightsFields(),

    { name: 'related_thinkers', label: 'People in this issue', kind: 'reference-list', required: false, collection: 'thinkers', group: 'people', hint: 'People who wrote in the issue or are written about in it.' },
    thinkerMentionsField(),
    {
      name: 'articles',
      label: 'Articles in this issue',
      kind: 'object-list',
      required: false,
      group: 'people',
      hint: 'One row per article, each with a short summary. This is what makes a single issue searchable piece by piece.',
      fields: [
        { name: 'toc_index', label: 'Position in the contents', kind: 'number', required: false, group: 'people' },
        { name: 'title', label: 'Title of the article', kind: 'text', required: true, group: 'people' },
        { name: 'author_resolved', label: 'Author', kind: 'reference', required: false, collection: 'thinkers', group: 'people' },
        { name: 'author_unresolved', label: 'Author name as printed', kind: 'text', required: false, group: 'people', hint: 'Use this when the author has no profile in the archive yet.' },
        { name: 'page_start', label: 'Starts on page', kind: 'number', required: false, group: 'people' },
        { name: 'page_end', label: 'Ends on page', kind: 'number', required: false, group: 'people' },
        { name: 'page_system', label: 'Which page numbering', kind: 'select', required: false, options: ['pdf', 'printed'], group: 'people' },
        { name: 'abstract', label: 'Short summary', kind: 'textarea', required: false, group: 'people', hint: 'About fifty words on what the article says. It is written from the article, not copied from one.' },
        { name: 'partial_essay', label: 'Only part of it was read', kind: 'boolean', required: false, group: 'people' },
        { name: 'pull_quotes', label: 'Pull quotes', kind: 'object-list', required: false, group: 'people', fields: pullQuoteFields() },
        { name: 'cross_thinker_mentions', label: 'People named in it', kind: 'object-list', required: false, group: 'people', fields: crossThinkerMentionFields() },
      ],
    },

    THEMES_FIELD,
    summaryStructuredField(),
    authorityAdditionsField(),
    { name: 'extent_caveat', label: 'Warning about how little was read', kind: 'boolean', required: false, group: 'advanced', hint: 'Set when the summary rests on only a small part of the issue.' },
    { name: 'toc_drift_detected', label: 'Contents list did not match the pages', kind: 'boolean', required: false, group: 'advanced', hint: 'Set when the printed contents disagreed with where articles actually start.' },
    { name: 'needs_extraction', label: 'Still waiting to be read by the machine', kind: 'boolean', required: false, group: 'advanced' },
    { name: 'dispatch_count', label: 'Extraction runs used', kind: 'number', required: false, group: 'advanced' },
    ...legacySummaryFields(),
    ...languageFields('periodicals'),
    ...aiProvenanceFields(),
    ...workflowFields('New issues start needing a check, because the masthead details are read off a scan by a machine.'),
  ],
};

const series: CollectionDef = {
  id: 'series',
  label: 'Series',
  singular: 'Series',
  description: 'A named run of printed items that is not a magazine: a publisher\'s booklet run, an annual memorial lecture, or a numbered set of papers.',
  path: 'apps/site/src/content/series',
  titleField: 'name',
  slugFrom: 'name',
  hasBody: true,
  bodyLabel: 'About the series',
  fields: [
    idField('ad-shroff-memorial-lecture', 'this series'),
    { name: 'name', label: 'Name of the series', kind: 'text', required: true, group: 'essential', placeholder: 'A. D. Shroff Memorial Lecture', hint: 'The name of the run as printed on its items.' },
    { name: 'blurb', label: 'What the series is', kind: 'textarea', required: true, group: 'essential', hint: 'A short paragraph saying who ran the series, when, and what it was for. Readers see this at the top of the series page.' },
    {
      name: 'kind',
      label: 'Kind of series',
      kind: 'select',
      required: true,
      options: ['booklet_series', 'lecture_series', 'occasional_papers', 'annual_analysis', 'multi_part_work'],
      group: 'essential',
      hint: 'What sort of run it is. This decides where it appears on the series page.',
    },
    { name: 'numbered', label: 'Items carry printed numbers', kind: 'boolean', required: false, group: 'essential', hint: 'Tick this only when the items themselves print a number, so the site can show No. 12 and notice which numbers are missing. Leave it unticked for runs ordered by date.' },
    { name: 'native', label: 'Subtitle or second name', kind: 'text', required: false, group: 'essential', hint: 'The run\'s own subtitle or the other name it went by, shown under the name.' },

    { name: 'publisher_id', label: 'Publisher', kind: 'reference', required: false, collection: 'organisations', group: 'publication', hint: 'The organisation that printed the items in the run.' },
    { name: 'issuer_id', label: 'Issuing body', kind: 'reference', required: false, collection: 'organisations', group: 'publication', hint: 'The body behind the series, when it is not the printer.' },
    { name: 'parent_series', label: 'Part of a wider series', kind: 'reference', required: false, collection: 'series', group: 'publication', hint: 'Use this when this run sits inside a bigger one, as the Shroff lectures sit inside the wider booklet run.' },

    ...aiProvenanceFields(),
    ...workflowFields('New series records start needing a check, because the shape of a run is easy to get wrong from a handful of items.'),
  ],
};

const themes: CollectionDef = {
  id: 'themes',
  label: 'Themes',
  singular: 'Theme',
  description: 'A subject that runs across the archive, written up with the works and people that carry it. Nothing has been filed under this type yet: theme tags on other records are still plain text.',
  path: 'apps/site/src/content/themes',
  titleField: 'label',
  slugFrom: 'label',
  hasBody: true,
  bodyLabel: 'Essay on the theme',
  fields: [
    idField('economic-policy', 'this theme'),
    { name: 'label', label: 'Name of the theme', kind: 'text', required: true, group: 'essential', placeholder: 'Economic policy', hint: 'The theme in ordinary words, as a heading. This is the name readers see.' },
    { name: 'blurb', label: 'Short description', kind: 'textarea', required: false, group: 'essential', hint: 'Two or three sentences saying what the theme covers and where its edges are.' },
    { name: 'evolution', label: 'How the argument changed', kind: 'markdown', required: false, group: 'essential', hint: 'How thinking on this subject moved over the decades the archive covers.' },
    { name: 'open_questions', label: 'Questions still open', kind: 'string-list', required: false, group: 'essential', hint: 'Arguments the archive does not settle, written as questions.' },

    { name: 'key_works', label: 'Works that matter most', kind: 'reference-list', required: false, collection: 'primary-works', group: 'classification', hint: 'The documents someone should read to understand this theme.' },
    { name: 'key_thinkers', label: 'People who shaped it', kind: 'reference-list', required: false, collection: 'thinkers', group: 'classification' },
    { name: 'parent_theme', label: 'Sits under', kind: 'reference', required: false, collection: 'themes', group: 'classification', hint: 'The broader theme this one belongs to, if it belongs to one.' },
    { name: 'child_themes', label: 'Narrower themes under it', kind: 'reference-list', required: false, collection: 'themes', group: 'classification' },
    { name: 'intersects_with', label: 'Overlaps with', kind: 'reference-list', required: false, collection: 'themes', group: 'classification', hint: 'Themes that keep coming up alongside this one without being part of it.' },

    ...aiProvenanceFields(),
    ...workflowFields('These are drafted by machine before anyone reads them, so they start needing a check.'),
  ],
};

const periodWindows: CollectionDef = {
  id: 'period-windows',
  label: 'Periods',
  singular: 'Period',
  description: 'A named stretch of years, written up with the debates and works that define it. Nothing has been filed under this type yet.',
  path: 'apps/site/src/content/period-windows',
  titleField: 'label',
  slugFrom: 'label',
  hasBody: true,
  bodyLabel: 'Essay on the period',
  fields: [
    idField('reform-era', 'this period'),
    { name: 'label', label: 'Name of the period', kind: 'text', required: true, group: 'essential', placeholder: 'The reform era', hint: 'What this stretch of years is called, in the form a reader would recognise.' },
    { name: 'year_start', label: 'First year', kind: 'year', required: true, group: 'essential', hint: 'The year the period begins. Pick a defensible year and explain the choice in the context below.' },
    { name: 'year_end', label: 'Last year', kind: 'year', required: true, group: 'essential', hint: 'The year the period ends. For a period still running, use the current year.' },
    { name: 'context', label: 'What was happening', kind: 'markdown', required: false, group: 'essential', hint: 'What was going on in India in these years, and what liberals were arguing about.' },

    { name: 'key_works', label: 'Works from this period', kind: 'reference-list', required: false, collection: 'primary-works', group: 'classification' },
    { name: 'key_thinkers', label: 'People who defined it', kind: 'reference-list', required: false, collection: 'thinkers', group: 'classification' },
    {
      name: 'key_debates',
      label: 'Arguments of the period',
      kind: 'object-list',
      required: false,
      group: 'classification',
      hint: 'The disputes that mattered, each with the positions taken and the works that took them.',
      fields: [
        { name: 'label', label: 'What the argument was about', kind: 'text', required: true, group: 'classification' },
        { name: 'sides', label: 'Positions taken', kind: 'string-list', required: false, group: 'classification', hint: 'A line for each side, put fairly.' },
        { name: 'works', label: 'Works that argued it', kind: 'reference-list', required: false, collection: 'primary-works', group: 'classification' },
      ],
    },

    ...aiProvenanceFields(),
    ...workflowFields('These are drafted by machine before anyone reads them, so they start needing a check.'),
  ],
};

const readingPaths: CollectionDef = {
  id: 'reading-paths',
  label: 'Reading paths',
  singular: 'Reading path',
  description: 'An ordered set of works put together for a particular reader, with a note on why each one comes where it does. Nothing has been filed under this type yet.',
  path: 'apps/site/src/content/reading-paths',
  titleField: 'title',
  slugFrom: 'title',
  hasBody: true,
  bodyLabel: 'Introduction to the path',
  fields: [
    idField('start-here-indian-liberalism', 'this reading path'),
    { name: 'title', label: 'Title', kind: 'text', required: true, group: 'essential', hint: 'What the path is called, written as an invitation rather than a label.' },
    {
      name: 'audience',
      label: 'Who it is for',
      kind: 'select',
      required: true,
      options: ['newcomer', 'scholar', 'specialist', 'specific_thinker', 'specific_theme', 'specific_period'],
      group: 'essential',
      hint: 'The reader you had in mind: someone new to the subject, an academic, or someone following one person, one theme or one period.',
    },
    { name: 'blurb', label: 'Short description', kind: 'textarea', required: false, group: 'essential', hint: 'Two or three sentences on what the reader will come away with, and roughly how long it takes.' },
    {
      name: 'sequence',
      label: 'The works, in order',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'The reading list itself. The order is the point, so put each work where it makes sense to read it.',
      fields: [
        { name: 'work_id', label: 'Work', kind: 'reference', required: true, collection: 'primary-works', group: 'essential' },
        { name: 'why_read_now', label: 'Why read it at this point', kind: 'textarea', required: false, group: 'essential', hint: 'One or two sentences saying what the earlier works have set up for this one.' },
        { name: 'estimated_minutes', label: 'Minutes to read', kind: 'number', required: false, group: 'essential' },
      ],
    },

    { name: 'related_themes', label: 'Themes it covers', kind: 'string-list', required: false, group: 'classification', hint: 'The same lowercase hyphenated theme tags used elsewhere in the archive.' },
    { name: 'related_thinkers', label: 'People it covers', kind: 'reference-list', required: false, collection: 'thinkers', group: 'classification' },

    ...aiProvenanceFields(),
    ...workflowFields('Paths are proposed by machine and agreed with the editorial owners before they go out, so they start needing a check.'),
  ],
};

const graphEdges: CollectionDef = {
  id: 'graph-edges',
  label: 'Connections',
  singular: 'Connection set',
  description: 'Recorded links between records, such as one work answering another or one thinker influencing another. Nothing has been filed under this type yet, and the files are written by scripts rather than typed by hand.',
  path: 'apps/site/src/content/graph-edges',
  titleField: 'edge_type',
  slugFrom: 'edge_type',
  hasBody: false,
  fields: [
    {
      name: 'edge_type',
      label: 'Kind of connection',
      kind: 'select',
      required: true,
      options: ['responds_to', 'builds_on', 'cites', 'reprints', 'translates', 'influenced_by', 'debated_with', 'collaborated_with', 'member_of', 'founded', 'presided', 'parent_of', 'intersects_with', 'engages', 'situated_in'],
      group: 'essential',
      hint: 'What sort of link this file holds. One file holds one kind, and every row in it is that kind of link.',
    },
    {
      name: 'edges',
      label: 'The connections',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'One row per link, each running from one record to another.',
      fields: [
        { name: 'from', label: 'From', kind: 'text', required: true, group: 'essential', hint: 'The web address name of the record the link starts at.' },
        { name: 'to', label: 'To', kind: 'text', required: true, group: 'essential', hint: 'The web address name of the record the link points to.' },
        { name: 'confidence', label: 'How sure it is', kind: 'select', required: false, options: ['high', 'medium', 'low'], group: 'essential', hint: 'How firm the link is. Choose low when it rests on a single passing remark.' },
        { name: 'evidence_works', label: 'Works that show it', kind: 'reference-list', required: false, collection: 'primary-works', group: 'essential', hint: 'The documents that support the link, so a reader can check it.' },
        { name: 'source', label: 'Who established it', kind: 'select', required: false, options: ['ai_synthesis_v1', 'human_curated', 'ai_synthesis_v2'], group: 'essential', hint: 'Whether a machine proposed the link or a person established it. Set it to human curated once someone has confirmed it.' },
        { name: 'context', label: 'What the link amounts to', kind: 'text', required: false, group: 'essential', hint: 'One line saying what the connection actually is.' },
      ],
    },
  ],
};

// ThePrint mirror is deliberately not editable here.
//
// It is a federated mirror of an external column, refilled every Saturday by
// .github/workflows/theprint-ingest.yml. An entry typed in the CMS would be
// overwritten by the next run, and the text is not ours to change in any case:
// the canonical article lives at ThePrint and every record cites back to it.
// Maintaining those pages is a job for the ingest, not for an editor.

// What the CMS offers, and why it is seven things rather than thirteen.
//
// A first screen listing every collection in the schema reads as a quiz. Worse,
// five of those choices could not be completed:
//
//   periodicals     has no directory at all. The 719 periodical issues in the
//                   archive are primary works with work_type: periodical_issue,
//                   so choosing "periodical issue" here would write a file the
//                   site never reads.
//   themes          zero entries
//   period-windows  zero entries
//   reading-paths   zero entries
//   graph-edges     zero entries
//
// The last four are future scope from the proposal, not editorial surfaces.
// Offering them invites someone to spend an afternoon filling in a form whose
// output nothing renders. They stay in ALL_COLLECTIONS below so tooling can
// still describe them, and out of COLLECTIONS so nobody is asked to choose one.
//
// ThePrint mirror is absent for a different reason: see the note above.

export const COLLECTIONS: CollectionDef[] = [
  primaryWorks,
  thinkers,
  opinions,
  musings,
  organisations,
  contributors,
  series,
];

/**
 * Everything the archive can hold, including the parts no editor should be
 * offered. Kept so tooling can still describe a record it encounters.
 */
export const ALL_COLLECTIONS: CollectionDef[] = [
  ...COLLECTIONS,
  periodicals,
  themes,
  periodWindows,
  readingPaths,
  graphEdges,
];

export function collectionById(id: string): CollectionDef | undefined {
  return ALL_COLLECTIONS.find((collection) => collection.id === id);
}
