// Shared interviews grouping used by /interviews/ (the index of shelves) and
// /interviews/[shelf]/ (one figure's recordings or one themed collection).
//
// Interviews live inside the primary-works collection with
// work_type: "interview". The index is a periodical-style wall of openable
// cards, mirroring /periodicals/: you pick a *figure* (an interviewee whose
// oral history spans several sittings) or a *collection* (historic lectures,
// topical talks, IL Explainers, or the ungrouped conversations) and open it to
// see the recordings inside (Adnan, 2026-07).
//
// The figure vs collection split reuses the editorial grouping the old flat
// page already curated. Only genuine sit-down oral histories are grouped by
// person; animated explainers and profile videos are NOT promoted into figure
// cards (a video *about* Tagore or Gokhale is not an interview *with* them).

import { getCollection } from "astro:content";
import type { CollectionEntry } from "astro:content";
import { DEFAULT_LOCALE } from "~/lib/i18n";

export type Entry = CollectionEntry<"primary-works">;

export function videoIdFor(w: Entry): string {
  const u = w.data.youtube_url ?? "";
  const m =
    u.match(/[?&]v=([a-zA-Z0-9_-]{6,15})/) ??
    u.match(/youtu\.be\/([a-zA-Z0-9_-]{6,15})/) ??
    u.match(/youtube\.com\/embed\/([a-zA-Z0-9_-]{6,15})/);
  return m ? m[1] : "";
}

export function thumbFor(w: Entry): string {
  const id = videoIdFor(w);
  return id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : "";
}

// Duration is baked into the transcript body header ("Duration: 1536.4s").
export function durationFor(w: Entry): string {
  const m = (w.body ?? "").match(/^Duration: (\d+)/m);
  if (!m) return "";
  const mins = Math.round(Number(m[1]) / 60);
  return mins < 1 ? "1 min" : `${mins} min`;
}

export function workHref(w: Entry): string {
  return w.data.language && w.data.language !== DEFAULT_LOCALE
    ? `/${w.data.language}/primary-works/${w.id}/`
    : `/primary-works/${w.id}/`;
}

export function speakerFor(
  w: Entry,
  thinkerById: Map<string, CollectionEntry<"thinkers">>,
): { name: string; thinkerId?: string } | null {
  const a = w.data.authors?.[0];
  if (a && "id" in a && thinkerById.has(a.id)) {
    return { name: thinkerById.get(a.id)!.data.name.canonical, thinkerId: a.id };
  }
  const m = (w.body ?? "").match(/^\*\*(?!Speaker\b|Narrator\b)([^*]+?)\*\* \(/m);
  return m ? { name: m[1].trim() } : null;
}

// ── Editorial group membership (verbatim from the old flat index) ─────────
const EXPLAINER_IDS = new Set([
  "women-liberals-dr-janaki",
  "the-life-legacy-of-lady-abala-bose",
  "mithan-tata-lam-an-indian-lawyer-and-suffragist",
]);
const LECTURE_IDS = new Set([
  "union-budget-1992-1993-by-nani-palkhivala",
  "an-auxiliary-for-historians-the-contribution-of-older-austrians",
  "the-case-against-neo-protectionism",
  "how-i-stopped-worrying-and-learned-to-love-the-trade-deficit-sudha-shenoy",
  "the-new-global-marketplace-sudha-shenoy",
  "the-hayek-keynes-debate-1931-1971-by-sudha-r-shenoy",
  "indian-liberal-tradition-gp-manish",
]);
const ORAL_PREFIXES = ["d-r-pendse-on", "minoo-shroff-on", "sunil-bhandare-on", "s-divakara-on"];
const ORAL_IDS = new Set([
  "minoo-masani-on-nehrus-adoption-of-socialism-in-conversation-with-zareer-masani",
  "minoo-masanis-disenchantment-with-the-soviet-economic-model-in-coversation-with-zareer-masani",
  "jagdish-bhagwati-on-milton-friedman",
  "in-conversation-with-ronald-meinardus-regional-director-fnf-south-asia",
  // Lok Satta founder Jayaprakash Narayan's 2020 conversation series.
  "the-early-years-emergency-era-and-tryst-with-civil-services",
  "the-challenges-for-liberal-grassroots-movements",
  "the-hope-for-a-liberal-political-alternative",
  "the-relationship-between-citizen-and-state",
]);

type GroupId = "oral" | "lectures" | "talks" | "explainers";
function groupFor(w: Entry): GroupId {
  if (w.id.startsWith("il-explainer") || EXPLAINER_IDS.has(w.id)) return "explainers";
  if (LECTURE_IDS.has(w.id)) return "lectures";
  if (ORAL_PREFIXES.some((p) => w.id.startsWith(p)) || ORAL_IDS.has(w.id)) return "oral";
  return "talks";
}

export type ShelfKind = "figure" | "collection";

export interface Shelf {
  slug: string; // URL slug under /interviews/<slug>/
  kind: ShelfKind;
  title: string;
  thinkerId?: string; // figure shelves that resolve to a thinker profile
  portrait?: string; // figure portrait (duotone/caricature/ring)
  blurb: string;
  items: Entry[];
  yearRange: string;
  thumb: string; // representative video thumbnail for the index card
}

// The ungrouped-speaker oral bucket surfaces as its own collection page, per
// Adnan's ask that "conversations" get a separate page.
const CONVERSATIONS_NAME = "Conversations";

const COLLECTION_META: Record<string, { title: string; blurb: string; order: number }> = {
  lectures: {
    title: "Historic lectures & addresses",
    blurb:
      "Recordings of addresses delivered decades before they reached the archive, from Nani Palkhivala's 1992 Union Budget address to Sudha Shenoy's lectures at the Mises Institute.",
    order: 1,
  },
  talks: {
    title: "Talks & monologues",
    blurb:
      "Topical talks from the #IndianLiberals series — Bollywood and liberalisation, forest rights, the farmers' movement, populism, and the state of the liberal project.",
    order: 2,
  },
  explainers: {
    title: "IL Explainers",
    blurb:
      "Short animated explainers on landmark liberal texts and under-told figures — B.R. Shenoy, Begum Rokeya, Tagore's Streer Potro, and the women liberals series.",
    order: 3,
  },
  conversations: {
    title: CONVERSATIONS_NAME,
    blurb:
      "Sit-down conversations and dialogues that aren't a single interviewee's oral history — cross-talks, panel exchanges, and interviews with visiting liberals.",
    order: 4,
  },
};

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function yearRangeOf(items: Entry[]): string {
  const years = items
    .map((w) => w.data.publication?.year)
    .filter((y): y is number => y != null);
  if (years.length === 0) return "";
  const lo = Math.min(...years);
  const hi = Math.max(...years);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

function thumbOf(items: Entry[]): string {
  const withThumb = items.map(thumbFor).find(Boolean);
  return withThumb ?? "";
}

export interface InterviewShelves {
  figures: Shelf[];
  collections: Shelf[];
  total: number;
  yearSpan: string;
}

export async function getInterviewShelves(): Promise<InterviewShelves> {
  const interviews = await getCollection(
    "primary-works",
    (w) => !w.data.draft && w.data.work_type === "interview",
  );
  const thinkers = await getCollection("thinkers");
  const thinkerById = new Map(thinkers.map((t) => [t.id, t]));

  const byGroup: Record<GroupId, Entry[]> = { oral: [], lectures: [], talks: [], explainers: [] };
  for (const w of interviews) byGroup[groupFor(w)].push(w);

  // ── Figures: oral histories sub-grouped by interviewee ──────────────────
  const figureByName = new Map<string, Shelf>();
  const conversations: Entry[] = [];
  for (const w of byGroup.oral) {
    const sp = speakerFor(w, thinkerById);
    // No identifiable single interviewee → the shared "Conversations" page.
    if (!sp) {
      conversations.push(w);
      continue;
    }
    if (!figureByName.has(sp.name)) {
      const t = sp.thinkerId ? thinkerById.get(sp.thinkerId) : undefined;
      const p = t?.data.portrait as
        | { duotone?: string; caricature?: string; ring_portrait?: string; photo?: string }
        | undefined;
      figureByName.set(sp.name, {
        slug: sp.thinkerId ?? slugify(sp.name),
        kind: "figure",
        title: sp.name,
        thinkerId: sp.thinkerId,
        portrait: p?.duotone ?? p?.caricature ?? p?.ring_portrait ?? p?.photo,
        blurb: `Oral-history conversations with ${sp.name} on the licence raj, the 1991 reforms, and the liberal institutions of modern India.`,
        items: [],
        yearRange: "",
        thumb: "",
      });
    }
    figureByName.get(sp.name)!.items.push(w);
  }

  const figures = [...figureByName.values()].sort(
    (a, b) => b.items.length - a.items.length || a.title.localeCompare(b.title),
  );
  // Guarantee unique URLs: figure slugs must not collide with each other or
  // with the reserved collection slugs (Astro getStaticPaths throws on dupes).
  const usedSlugs = new Set<string>(Object.keys(COLLECTION_META));
  for (const shelf of figures) {
    let slug = shelf.slug;
    for (let n = 2; usedSlugs.has(slug); n++) slug = `${shelf.slug}-${n}`;
    shelf.slug = slug;
    usedSlugs.add(slug);
    shelf.items.sort((a, b) => a.data.title.main.localeCompare(b.data.title.main));
    shelf.yearRange = yearRangeOf(shelf.items);
    shelf.thumb = thumbOf(shelf.items);
  }

  // ── Collections: lectures, talks, explainers, conversations ─────────────
  byGroup.lectures.sort(
    (a, b) => (a.data.publication?.year ?? 9999) - (b.data.publication?.year ?? 9999),
  );
  byGroup.talks.sort(
    (a, b) =>
      (b.data.publication?.year ?? 0) - (a.data.publication?.year ?? 0) ||
      a.data.title.main.localeCompare(b.data.title.main),
  );
  byGroup.explainers.sort((a, b) => a.id.localeCompare(b.id));
  conversations.sort((a, b) => a.data.title.main.localeCompare(b.data.title.main));

  const collectionItems: Record<string, Entry[]> = {
    lectures: byGroup.lectures,
    talks: byGroup.talks,
    explainers: byGroup.explainers,
    conversations,
  };
  const collections = Object.entries(collectionItems)
    .filter(([, items]) => items.length > 0)
    .map(([id, items]) => ({
      slug: id,
      kind: "collection" as const,
      title: COLLECTION_META[id].title,
      blurb: COLLECTION_META[id].blurb,
      items,
      yearRange: yearRangeOf(items),
      thumb: thumbOf(items),
    }))
    .sort((a, b) => COLLECTION_META[a.slug].order - COLLECTION_META[b.slug].order);

  const total = interviews.length;
  const yearSpan = yearRangeOf(interviews);
  return { figures, collections, total, yearSpan };
}
