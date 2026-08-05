/**
 * The website's own words, as editable surfaces.
 *
 * Every static sentence on indianliberals.in (the homepage hero, the menu,
 * each section's introduction, the about page, the shelf blurbs, the little
 * headings on a work's page) lives in one markdown file per surface under
 * `apps/site/src/content/site/`. The site reads those files at build time
 * and falls back to its built-in wording when a field is empty, so nothing
 * an editor clears can ever blank a page.
 *
 * These definitions reuse the same Field/CollectionDef machinery as the
 * content collections, so the edit screen renders them with no new code.
 * They are deliberately NOT in COLLECTIONS: an editor reaches them through
 * the "Change the website's own words" screen, not through "Add something",
 * because you edit these surfaces, you never create or delete them.
 *
 * Placeholders such as {works} or {count} in a sentence are filled in by
 * the site with live numbers. The hints tell editors to leave them in.
 */

import type { CollectionDef, Field } from './collections';

const SITE_PATH = 'apps/site/src/content/site';

const TOKEN_HINT =
  'Anything in curly brackets, such as {works} or {count}, is replaced with a live number when the site is built. Keep those brackets exactly as they are.';

function text(name: string, label: string, hint?: string): Field {
  return { name, label, kind: 'text', required: false, group: 'essential', hint };
}

function long(name: string, label: string, hint?: string): Field {
  return { name, label, kind: 'textarea', required: false, group: 'essential', hint };
}

/** The id row every surface file carries. Editors never change it. */
function fixedId(): Field {
  return {
    name: 'id',
    label: 'File name (do not change)',
    kind: 'slug',
    required: true,
    group: 'advanced',
    hint: 'The internal name of this surface. Changing it would disconnect the words from the page they belong to.',
  };
}

export interface Surface extends CollectionDef {
  /** The one file this surface edits, under apps/site/src/content/site/. */
  slug: string;
  /** Where the words appear, in one sentence, shown on the site screen. */
  where: string;
}

function surface(
  slug: string,
  label: string,
  where: string,
  fields: Field[],
  body?: { label: string; hint?: string },
): Surface {
  return {
    id: 'site',
    slug,
    label,
    singular: label,
    where,
    description: where,
    path: SITE_PATH,
    titleField: 'id',
    slugFrom: 'id',
    hasBody: Boolean(body),
    bodyLabel: body?.label,
    fields: [...fields, fixedId()],
  };
}

// ─── The surfaces ──────────────────────────────────────────────────────

const identity = surface(
  'identity',
  'Name, description and credits',
  'The site title, the description search engines show, the footer credits and the copyright line.',
  [
    text('site_title', 'Title of the site', 'Appears in the browser tab and in search results for the homepage.'),
    long('site_description', 'Description of the site', 'The sentence search engines and social links show under the title. One or two sentences.'),
    long('footer_blurb', 'Footer description', 'The short paragraph at the bottom of every page.'),
    text('org_name', 'Maintained by', 'The organisation named in the footer and the copyright line.'),
    text('org_url', 'Their website', 'The address the organisation name links to.'),
    text('builder_name', 'Site rebuilt by', 'The name in the "rebuilt by" credit.'),
    text('builder_url', 'Their website', 'The address that credit links to.'),
    { name: 'copyright_start', label: 'Copyright starts from year', kind: 'number', required: false, group: 'essential', hint: 'The first year in the copyright line at the foot of every page.' },
    text('contact_email', 'Contact email', 'Shown on the contact page once filled in. Leave empty to show none.'),
  ],
);

const navigation = surface(
  'navigation',
  'Menus and footer links',
  'Every label and one-line description in the site menu, and the links in the footer.',
  [
    text('title', 'Wordmark', 'The site name written next to the crane in the header.'),
    {
      name: 'groups',
      label: 'Menu groups',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'The header menu, group by group. Change wording freely; only change a web address if you know where it should point.',
      fields: [
        { name: 'label', label: 'Group name', kind: 'text', required: true, group: 'essential' },
        {
          name: 'items',
          label: 'Entries',
          kind: 'object-list',
          required: false,
          group: 'essential',
          fields: [
            { name: 'label', label: 'Label', kind: 'text', required: true, group: 'essential' },
            { name: 'href', label: 'Web address', kind: 'text', required: true, group: 'essential' },
            { name: 'desc', label: 'One-line description', kind: 'text', required: false, group: 'essential' },
          ],
        },
      ],
    },
    {
      name: 'footer_links',
      label: 'Footer links',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'The small links at the bottom of every page.',
      fields: [
        { name: 'label', label: 'Label', kind: 'text', required: true, group: 'essential' },
        { name: 'href', label: 'Web address', kind: 'text', required: true, group: 'essential' },
      ],
    },
  ],
);

const home = surface(
  'home',
  'Homepage',
  'Everything written on the front page: the opening lines, the section headings and their blurbs.',
  [
    text('hero_eyebrow', 'Small line above the headline'),
    text('hero_heading', 'The headline'),
    long('hero_lede', 'The paragraph under it', TOKEN_HINT),
    text('cta_primary', 'First button'),
    text('cta_secondary', 'Second button'),
    text('glance_heading', 'Heading over the numbers'),
    text('glance_span', 'Line under that heading', TOKEN_HINT),
    long('histogram_caption', 'Caption under the decade chart', TOKEN_HINT),
    {
      name: 'tiles',
      label: 'The stat tiles',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'The label under each number. The numbers themselves are counted automatically. Do not change the short name in the key box.',
      fields: [
        { name: 'key', label: 'Key (do not change)', kind: 'text', required: true, group: 'essential' },
        { name: 'label', label: 'Label', kind: 'text', required: true, group: 'essential' },
      ],
    },
    text('browse_heading', 'Heading over the section cards'),
    long('browse_lede', 'The line under it'),
    {
      name: 'cards',
      label: 'The section cards',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'One card per section of the archive. ' + TOKEN_HINT,
      fields: [
        { name: 'key', label: 'Key (do not change)', kind: 'text', required: true, group: 'essential' },
        { name: 'heading', label: 'Heading', kind: 'text', required: false, group: 'essential' },
        { name: 'blurb', label: 'Blurb', kind: 'textarea', required: false, group: 'essential' },
      ],
    },
    text('canon_heading', 'Heading over the thinkers strip'),
    long('canon_blurb', 'The line under it'),
    text('canon_cta', 'The thinkers strip link'),
    text('theprint_eyebrow', 'Small line above the ThePrint column'),
    text('theprint_heading', 'ThePrint heading'),
    long('theprint_blurb', 'ThePrint blurb'),
    text('theprint_cta', 'ThePrint link text'),
    text('researchers_eyebrow', 'Small line above the researchers section'),
    text('researchers_heading', 'Researchers heading'),
    long('researchers_body', 'Researchers paragraph'),
    text('tier_eyebrow', 'Small line above the two-tier section'),
    text('tier_heading', 'Two-tier heading'),
    long('tier_para_a', 'Two-tier first paragraph'),
    long('tier_para_b', 'Two-tier second paragraph'),
  ],
);

const about = surface(
  'about',
  'About page',
  'The about page: its headline, introduction and the acknowledgements list.',
  [
    text('heading', 'The headline'),
    text('tier_heading', 'Heading over the content-kinds grid'),
    text('tier_sub', 'The line under it'),
    text('gratitude_heading', 'Gratitude heading'),
    text('gratitude_sub', 'The line under it'),
    long('gratitude_note', 'Gratitude paragraph'),
    {
      name: 'acknowledgements',
      label: 'People thanked',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'The acknowledgements list, one row per person.',
      fields: [
        { name: 'name', label: 'Name', kind: 'text', required: true, group: 'essential' },
        { name: 'org', label: 'Organisation', kind: 'text', required: false, group: 'essential' },
      ],
    },
  ],
  { label: 'The introduction', hint: 'The paragraphs at the top of the about page, in markdown.' },
);

const comingSoon = surface(
  'coming-soon',
  'Placeholder pages',
  'The Contact, Gallery and Testimonials pages while they wait to be built.',
  [
    text('contact_title', 'Contact page title'),
    long('contact_blurb', 'Contact page blurb'),
    text('gallery_title', 'Gallery page title'),
    long('gallery_blurb', 'Gallery page blurb'),
    text('testimonials_title', 'Testimonials page title'),
    long('testimonials_blurb', 'Testimonials page blurb'),
    long('note', 'The "coming soon" sentence', 'Shown on all three pages under the blurb.'),
  ],
);

const shelves = surface(
  'shelves',
  'Shelf blurbs',
  'The descriptions of each magazine run, lecture series and interview shelf.',
  [
    {
      name: 'periodical_shelves',
      label: 'Magazine runs',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'One row per run on the periodicals page. Do not change the key.',
      fields: [
        { name: 'key', label: 'Key (do not change)', kind: 'text', required: true, group: 'essential' },
        { name: 'name', label: 'Name', kind: 'text', required: false, group: 'essential' },
        { name: 'native', label: 'Name in its own script', kind: 'text', required: false, group: 'essential' },
        { name: 'blurb', label: 'Blurb', kind: 'textarea', required: false, group: 'essential' },
      ],
    },
    {
      name: 'lecture_shelves',
      label: 'Lecture series',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'One row per series on the lectures page. Do not change the key.',
      fields: [
        { name: 'key', label: 'Key (do not change)', kind: 'text', required: true, group: 'essential' },
        { name: 'name', label: 'Name', kind: 'text', required: false, group: 'essential' },
        { name: 'blurb', label: 'Blurb', kind: 'textarea', required: false, group: 'essential' },
      ],
    },
    {
      name: 'interview_shelves',
      label: 'Interview shelves',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'One row per shelf on the oral history page. Do not change the key.',
      fields: [
        { name: 'key', label: 'Key (do not change)', kind: 'text', required: true, group: 'essential' },
        { name: 'name', label: 'Name', kind: 'text', required: false, group: 'essential' },
        { name: 'blurb', label: 'Blurb', kind: 'textarea', required: false, group: 'essential' },
      ],
    },
  ],
);

const labels = surface(
  'labels',
  'Interface labels',
  'The small recurring headings and search-box wording used across the site.',
  [
    {
      name: 'pairs',
      label: 'The labels',
      kind: 'object-list',
      required: false,
      group: 'essential',
      hint: 'Each row is one piece of interface wording. The first box says where it appears; change only the words in the last box. ' + TOKEN_HINT,
      fields: [
        { name: 'key', label: 'Key (do not change)', kind: 'text', required: true, group: 'essential' },
        { name: 'about', label: 'Where it appears', kind: 'text', required: false, group: 'essential' },
        { name: 'value', label: 'The words', kind: 'text', required: true, group: 'essential' },
      ],
    },
  ],
);

/** The shared shape of a section landing page's words. */
function sectionSurface(slug: string, label: string, where: string, extras: Field[] = []): Surface {
  return surface(slug, label, where, [
    text('heading', 'The headline'),
    long('lede', 'The introduction under it', TOKEN_HINT),
    text('eyebrow', 'Small line above the headline'),
    text('title', 'Browser-tab title', 'What the browser tab and search results call this page.'),
    long('description', 'Search-result description', 'The sentence search engines show for this page. ' + TOKEN_HINT),
    long('empty_state', 'When nothing matches', 'Shown when a filter or search on this page finds nothing.'),
    ...extras,
  ]);
}

const doorwaysField = (hint: string): Field => ({
  name: 'doorways',
  label: 'The doorway cards',
  kind: 'object-list',
  required: false,
  group: 'essential',
  hint,
  fields: [
    { name: 'key', label: 'Key (do not change)', kind: 'text', required: true, group: 'essential' },
    { name: 'label', label: 'Label', kind: 'text', required: false, group: 'essential' },
    { name: 'title', label: 'Title', kind: 'text', required: false, group: 'essential' },
    { name: 'blurb', label: 'Blurb', kind: 'textarea', required: false, group: 'essential' },
  ],
});

export const SURFACES: Surface[] = [
  home,
  identity,
  navigation,
  about,
  sectionSurface('section-primary-works', 'Primary works page', 'The introduction to the primary works listing.'),
  sectionSurface('section-thinkers', 'Thinkers page', 'The introduction to the curated canon page.'),
  sectionSurface(
    'section-thinkers-directory',
    'Thinkers directory page',
    'The introduction to the full directory, and the blurb over each of its four groups.',
    [doorwaysField('One row per group of the directory: the canon, the extended tradition, referenced figures, and the unclassified.')],
  ),
  sectionSurface('section-organisations', 'Organisations page', 'The introduction to the organisations listing.'),
  sectionSurface('section-opinions', 'Opinions page', 'The introduction to the opinions listing.'),
  sectionSurface('section-musings', 'Musings page', 'The introduction to the curated excerpts listing.'),
  sectionSurface('section-periodicals', 'Periodicals page', 'The introduction to the periodicals and series page.'),
  sectionSurface(
    'section-interviews',
    'Oral history page',
    'The introduction to the oral history page and its four doorway cards.',
    [doorwaysField('One row per doorway: interviews, talks, explainers, conversations.')],
  ),
  sectionSurface('section-interviews-people', 'Interviews by person page', 'The introduction to the interviews-by-person listing.'),
  sectionSurface('section-lectures', 'Lectures page', 'The introduction to the lectures and addresses page.'),
  sectionSurface('section-languages', 'Languages page', 'The introduction to the writing-in-other-languages page.'),
  sectionSurface('section-theprint', 'ThePrint mirror page', 'The introduction to the federated ThePrint column page.'),
  sectionSurface('section-events', 'Events page', 'The introduction to the events listing.'),
  sectionSurface('section-contributors', 'Contributors page', 'The introduction to the contributors listing.'),
  sectionSurface('section-search', 'Full-text search page', 'The introduction to the full-text search page.'),
  shelves,
  comingSoon,
  labels,
];

export function surfaceFor(slug: string): Surface | undefined {
  return SURFACES.find((s) => s.slug === slug);
}
