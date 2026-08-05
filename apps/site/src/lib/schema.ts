// JSON-LD (Schema.org) node builders.
//
// BaseLayout emits a single <script type="application/ld+json"> per page:
// an @graph of [Organization, WebSite, ...page-specific nodes]. Detail
// components build their nodes with these helpers and pass them via the
// layout's `schema` prop. Nodes reference each other by stable @id, so the
// org/site pair is emitted once per page and never duplicated.
//
// Field mapping follows Google's structured-data guidance: Book for
// book-like works, PublicationIssue for periodical issues, Article for
// editorial prose, ProfilePage+Person for bios, BreadcrumbList everywhere.

import type { CollectionEntry } from "astro:content";
import type { AuthorEntry } from "~/lib/resolve-author-entries";

export const SITE_URL = "https://indianliberals.in";
export const ORG_ID = `${SITE_URL}/#organization`;
export const WEBSITE_ID = `${SITE_URL}/#website`;

const SITE_DESCRIPTION =
  "A digital archive of the Indian liberal tradition. Primary works, thinker profiles, organisations, opinions, and curated excerpts from the figures who built the case for liberty in modern India.";

type Node = Record<string, unknown>;

const compact = (o: Node): Node =>
  Object.fromEntries(
    Object.entries(o).filter(
      ([, v]) =>
        v !== undefined &&
        v !== null &&
        v !== "" &&
        !(Array.isArray(v) && v.length === 0),
    ),
  );

const abs = (path: string): string =>
  path.startsWith("http") ? path : `${SITE_URL}${path}`;

/** Sitewide publisher node, same @id on every page.
 *  `description` lets BaseLayout pass the CMS-edited site description
 *  (site content collection, `identity` entry) so this node and the meta
 *  description can never drift; the built-in wording stays the default. */
export function organizationNode(description: string = SITE_DESCRIPTION): Node {
  return {
    "@type": "Organization",
    "@id": ORG_ID,
    name: "Indian Liberals",
    url: `${SITE_URL}/`,
    logo: {
      "@type": "ImageObject",
      url: `${SITE_URL}/brand/favicon-512.png`,
    },
    description,
    parentOrganization: {
      "@type": "NGO",
      name: "Centre for Civil Society",
      url: "https://ccs.in/",
    },
  };
}

/** Sitewide WebSite node, same @id on every page. Takes the same optional
 *  CMS-edited description as organizationNode. */
export function webSiteNode(description: string = SITE_DESCRIPTION): Node {
  return {
    "@type": "WebSite",
    "@id": WEBSITE_ID,
    url: `${SITE_URL}/`,
    name: "Indian Liberals",
    alternateName: "Indian Liberals: An Online Archive of Indian Liberal Works",
    description,
    publisher: { "@id": ORG_ID },
    inLanguage: ["en-IN", "hi-IN", "mr-IN", "gu-IN"],
  };
}

/** items: [label, site-relative-or-absolute URL] pairs, root-first. */
export function breadcrumbNode(items: [string, string][]): Node {
  return {
    "@type": "BreadcrumbList",
    itemListElement: items.map(([name, url], i) => ({
      "@type": "ListItem",
      position: i + 1,
      name,
      item: abs(url),
    })),
  };
}

const WORK_TYPE_TO_SCHEMA: Record<string, string> = {
  book: "Book",
  edited_volume: "Book",
  reference: "Book",
  periodical_issue: "PublicationIssue",
  essay: "Article",
  pamphlet: "CreativeWork",
  speech: "CreativeWork",
  occasional_paper: "Article",
  letter: "Message",
  correspondence: "CreativeWork",
  interview: "CreativeWork",
};

const clip = (s: string | undefined, n = 600): string | undefined => {
  if (!s) return undefined;
  const t = s.trim().replace(/\s+/g, " ");
  return t.length > n ? `${t.slice(0, n - 1).trimEnd()}…` : t;
};

/** Primary work (or interview) detail page. */
export function workNode(
  entry: CollectionEntry<"primary-works">,
  authorEntries: AuthorEntry[],
  pagePath: string,
): Node {
  const fm = entry.data;
  const type = WORK_TYPE_TO_SCHEMA[fm.work_type] ?? "CreativeWork";
  const pageCount = fm.physical?.pages_total ?? fm.physical?.page_count;
  const node: Node = {
    "@type": type,
    "@id": abs(pagePath),
    name: fm.title.main,
    alternateName: fm.title.original_script,
    author: authorEntries.map((a) =>
      compact({
        "@type": a.kind === "organisation" ? "Organization" : "Person",
        name: a.name,
        url: abs(
          a.kind === "organisation"
            ? `/organisations/${a.id}/`
            : `/thinkers/${a.id}/`,
        ),
      }),
    ),
    datePublished:
      fm.publication?.year != null ? String(fm.publication.year) : undefined,
    inLanguage: fm.publication?.language ?? "en",
    publisher: fm.publication?.publisher_name
      ? { "@type": "Organization", name: fm.publication.publisher_name }
      : undefined,
    image: fm.cover_image,
    thumbnailUrl: fm.cover_image,
    abstract: clip(fm.summary ?? fm.ai_summary),
    keywords: (fm.themes ?? []).map((t) => t.replace(/-/g, " ")).join(", "),
    url: abs(pagePath),
    mainEntityOfPage: abs(pagePath),
    isAccessibleForFree: true,
    encoding: fm.pdf_url
      ? {
          "@type": "MediaObject",
          contentUrl: fm.pdf_url,
          encodingFormat: "application/pdf",
        }
      : undefined,
    isPartOf: { "@id": WEBSITE_ID },
  };
  if (type === "Book") {
    node.numberOfPages = pageCount;
    node.isbn = fm.identifiers?.isbn;
    node.bookEdition = fm.publication?.edition;
  }
  if (type === "Article" || type === "PublicationIssue") {
    node.headline = fm.title.main;
  }
  return compact(node);
}

const pretty = (s: string): string =>
  s.replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/** Thinker bio page: ProfilePage wrapping a Person mainEntity. */
export function thinkerNodes(
  entry: CollectionEntry<"thinkers">,
  pagePath: string,
): Node[] {
  const fm = entry.data;
  const personId = `${abs(pagePath)}#person`;
  const portrait =
    fm.portrait?.photo ?? fm.portrait?.caricature ?? fm.portrait?.duotone;
  const person = compact({
    "@type": "Person",
    "@id": personId,
    name: fm.name.canonical,
    alternateName: [
      ...(fm.name.full && fm.name.full !== fm.name.canonical
        ? [fm.name.full]
        : []),
      ...(fm.name.also_known_as ?? []),
    ],
    birthDate: fm.birth_year != null ? String(fm.birth_year) : undefined,
    deathDate: fm.death_year != null ? String(fm.death_year) : undefined,
    nationality:
      fm.nationality === "india"
        ? { "@type": "Country", name: "India" }
        : fm.nationality
          ? { "@type": "Country", name: pretty(fm.nationality) }
          : undefined,
    jobTitle: (fm.vocations ?? []).map(pretty).join(", "),
    image: portrait ? abs(portrait) : undefined,
    url: abs(pagePath),
    knowsAbout: (fm.themes ?? []).map((t) => t.replace(/-/g, " ")),
    mainEntityOfPage: abs(pagePath),
  });
  const profilePage = {
    "@type": "ProfilePage",
    "@id": abs(pagePath),
    mainEntity: { "@id": personId },
    isPartOf: { "@id": WEBSITE_ID },
  };
  return [person, profilePage];
}

/** Musing / opinion / mirrored-column detail page. */
export function articleNode(opts: {
  pagePath: string;
  headline: string;
  datePublished?: Date;
  authorName?: string;
  authorPath?: string;
  aboutName?: string;
  aboutPath?: string;
  image?: string;
  description?: string;
  themes?: string[];
  inLanguage?: string;
}): Node {
  return compact({
    "@type": "Article",
    "@id": abs(opts.pagePath),
    headline: opts.headline,
    datePublished: opts.datePublished?.toISOString().slice(0, 10),
    author: opts.authorName
      ? compact({
          "@type": "Person",
          name: opts.authorName,
          url: opts.authorPath ? abs(opts.authorPath) : undefined,
        })
      : undefined,
    about:
      opts.aboutName && opts.aboutPath
        ? {
            "@type": "Person",
            name: opts.aboutName,
            url: abs(opts.aboutPath),
          }
        : undefined,
    image: opts.image ? abs(opts.image) : undefined,
    description: clip(opts.description),
    keywords: (opts.themes ?? []).map((t) => t.replace(/-/g, " ")).join(", "),
    inLanguage: opts.inLanguage ?? "en",
    publisher: { "@id": ORG_ID },
    url: abs(opts.pagePath),
    mainEntityOfPage: abs(opts.pagePath),
    isAccessibleForFree: true,
    isPartOf: { "@id": WEBSITE_ID },
  });
}

/** Organisation detail page. */
export function organisationDetailNode(
  entry: CollectionEntry<"organisations">,
  pagePath: string,
): Node {
  const fm = entry.data;
  return compact({
    "@type": "Organization",
    "@id": abs(pagePath),
    name: fm.name.canonical,
    alternateName: [
      ...(fm.name.full && fm.name.full !== fm.name.canonical
        ? [fm.name.full]
        : []),
      ...(fm.name.also_known_as ?? []),
    ],
    foundingDate:
      fm.founded_year != null ? String(fm.founded_year) : undefined,
    dissolutionDate:
      fm.dissolved_year != null ? String(fm.dissolved_year) : undefined,
    description: fm.description,
    logo: fm.logo ? abs(fm.logo) : undefined,
    url: abs(pagePath),
    mainEntityOfPage: abs(pagePath),
  });
}

/** Index/landing pages. */
export function collectionPageNode(opts: {
  pagePath: string;
  name: string;
  description?: string;
}): Node {
  return compact({
    "@type": "CollectionPage",
    "@id": abs(opts.pagePath),
    name: opts.name,
    description: opts.description,
    url: abs(opts.pagePath),
    isPartOf: { "@id": WEBSITE_ID },
  });
}
