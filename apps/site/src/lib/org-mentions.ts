// Build-time reverse index: organisation → content that mentions it in prose.
//
// Most organisation entries exist as institutional context — thinker bios,
// musings, and opinion pieces name them in running text (Brahmo Samaj, Mont
// Pelerin Society, Satyashodhak Samaj…), but nothing structured points back,
// so their pages looked purposeless. The planned Phase-4 graph edges
// (member_of / founded / presided) and thinker `affiliations` were never
// populated; this index recovers the same connective tissue from the prose
// we already have, at build time, with no frontmatter mutation — new content
// is picked up automatically on the next build.
//
// Matching is deliberately conservative: full canonical/full/AKA names only,
// word-boundary anchored; short all-caps acronyms (FFE, NCAER) match
// case-sensitively so ordinary words never trip them.

import { getCollection } from "astro:content";
import { DEFAULT_LOCALE } from "~/lib/i18n";
import { isListed } from "./listable";

export interface OrgMention {
  kind: "thinker" | "opinion" | "musing" | "work";
  id: string;
  title: string;
  href: string;
}

const KIND_ORDER: Record<OrgMention["kind"], number> = {
  thinker: 0,
  opinion: 1,
  musing: 2,
  work: 3,
};

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function patternsFor(names: string[]): RegExp[] {
  const seen = new Set<string>();
  const pats: RegExp[] = [];
  for (const raw of names) {
    const name = (raw ?? "").trim();
    if (!name || seen.has(name.toLowerCase())) continue;
    seen.add(name.toLowerCase());
    const esc = escapeRe(name);
    if (/^[A-Z0-9&.]{3,6}$/.test(name)) {
      // Acronym: exact case, own word.
      pats.push(new RegExp(`\\b${esc}\\b`));
    } else if (name.length >= 5) {
      pats.push(new RegExp(`\\b${esc}\\b`, "i"));
    }
    // Names shorter than 5 chars that aren't acronyms are too ambiguous.
  }
  return pats;
}

let indexPromise: Promise<Map<string, OrgMention[]>> | null = null;

async function buildIndex(): Promise<Map<string, OrgMention[]>> {
  const orgs = await getCollection("organisations", (o) => !o.data.draft);
  const matchers = orgs.map((o) => ({
    id: o.id,
    pats: patternsFor([
      o.data.name.canonical,
      o.data.name.full ?? "",
      ...(o.data.name.also_known_as ?? []),
    ]),
  }));

  const sources: { text: string; mention: OrgMention }[] = [];
  const en = (e: { data: { language?: string } }) =>
    (e.data.language ?? DEFAULT_LOCALE) === DEFAULT_LOCALE;

  for (const t of await getCollection("thinkers", (e) => !e.data.draft && en(e))) {
    sources.push({
      text: t.body ?? "",
      mention: {
        kind: "thinker",
        id: t.id,
        title: t.data.name.canonical,
        href: `/thinkers/${t.id}/`,
      },
    });
  }
  for (const p of await getCollection("opinions", (e) => !e.data.draft && en(e))) {
    sources.push({
      text: p.body ?? "",
      mention: { kind: "opinion", id: p.id, title: p.data.title, href: `/opinions/${p.id}/` },
    });
  }
  for (const m of await getCollection("musings", (e) => !e.data.draft && en(e))) {
    sources.push({
      text: m.body ?? "",
      mention: { kind: "musing", id: m.id, title: m.data.title, href: `/musings/${m.id}/` },
    });
  }
  for (const w of await getCollection("primary-works", (e) => isListed(e) && en(e))) {
    sources.push({
      text: w.body ?? "",
      mention: {
        kind: "work",
        id: w.id,
        title: w.data.title.main,
        href: `/primary-works/${w.id}/`,
      },
    });
  }

  const index = new Map<string, OrgMention[]>(matchers.map((m) => [m.id, []]));
  for (const src of sources) {
    if (!src.text) continue;
    for (const m of matchers) {
      if (m.pats.some((re) => re.test(src.text))) {
        index.get(m.id)!.push(src.mention);
      }
    }
  }
  for (const list of index.values()) {
    list.sort(
      (a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || a.title.localeCompare(b.title),
    );
  }
  return index;
}

/** All prose mentions of an organisation, thinker bios first. Cached across
 *  every org page in a single build. */
export function orgMentions(orgId: string): Promise<OrgMention[]> {
  indexPromise ??= buildIndex();
  return indexPromise.then((m) => m.get(orgId) ?? []);
}
