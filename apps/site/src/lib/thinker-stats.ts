// Build-time helper: computes per-thinker {worksAuthored, referencedIn}
// counts by iterating the relevant content collections.
//
// Per spec §5.1 mapping table:
//   primary-works:  worksAuthored ← authors[] (thinker-refs only; org-refs excluded)
//                   referencedIn  ← contributors[].thinker + thinker_mentions[].thinker
//                                   + related_thinkers[]
//   opinions:       worksAuthored ← author
//                   referencedIn  ← subject + thinker_mentions[].thinker
//                                   + related_thinkers[]
//   interviews:     worksAuthored ← (none — interviewee is not author)
//                   referencedIn  ← subject (the only thinker-ref field on schema)
//   musings:        worksAuthored ← author
//                   referencedIn  ← thinker_mentions[].thinker + related_thinkers[]
//   theprint-mirror: worksAuthored ← (none — author_name is a free-text string)
//                   referencedIn  ← thinker_mentions[].thinker + related_thinkers[]
//   periodicals:    worksAuthored ← toc[].author_resolved (one count per TOC entry)
//                   referencedIn  ← related_thinkers[] + thinker_mentions[].thinker
//                                   + toc[].cross_thinker_mentions[].thinker_resolved
//
// Within-entry dedup: if a thinker appears in both authored AND referenced
// fields of the same entry, count as worksAuthored only.
//
// Contract: returned Map contains an entry iff the thinker has at least
// one non-zero count. Page-render code must use:
//   stats.get(id) ?? { worksAuthored: 0, referencedIn: 0 }
//
// See docs/superpowers/specs/2026-05-23-thinkers-classification-design.md §5.

import { getCollection } from "astro:content";

export interface ThinkerStat {
  worksAuthored: number;
  referencedIn: number;
}

type RefLike = { id: string; collection?: string } | string | undefined | null;

function refToId(ref: RefLike): string | null {
  if (!ref) return null;
  if (typeof ref === "string") return ref;
  // Filter to thinker refs only (org-refs from the primary-works authors[]
  // union are excluded).
  if (ref.collection && ref.collection !== "thinkers") return null;
  return ref.id ?? null;
}

export async function getThinkerStats(): Promise<Map<string, ThinkerStat>> {
  const stats = new Map<string, ThinkerStat>();

  const bump = (id: string, key: keyof ThinkerStat) => {
    const cur = stats.get(id) ?? { worksAuthored: 0, referencedIn: 0 };
    cur[key] += 1;
    stats.set(id, cur);
  };

  const applyEntry = (authored: Set<string>, referenced: Set<string>) => {
    // Within-entry dedup: authored wins
    for (const id of authored) referenced.delete(id);
    for (const id of authored) bump(id, "worksAuthored");
    for (const id of referenced) bump(id, "referencedIn");
  };

  // primary-works
  const primaryWorks = await getCollection("primary-works");
  for (const w of primaryWorks) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    for (const a of w.data.authors ?? []) {
      const id = refToId(a as RefLike);
      if (id) authored.add(id);
    }
    for (const c of w.data.contributors ?? []) {
      const id = refToId(c.thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const m of w.data.thinker_mentions ?? []) {
      const id = refToId((m as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of w.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(authored, referenced);
  }

  // opinions
  const opinions = await getCollection("opinions");
  for (const o of opinions) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    const authorId = refToId(o.data.author as RefLike);
    if (authorId) authored.add(authorId);
    const subjectId = refToId(o.data.subject as RefLike);
    if (subjectId) referenced.add(subjectId);
    for (const m of o.data.thinker_mentions ?? []) {
      const id = refToId((m as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of o.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(authored, referenced);
  }

  // interviews — only `subject` is a thinker ref
  const interviews = await getCollection("interviews");
  for (const v of interviews) {
    const referenced = new Set<string>();
    const subjectId = refToId(v.data.subject as RefLike);
    if (subjectId) referenced.add(subjectId);
    applyEntry(new Set(), referenced);
  }

  // musings
  const musings = await getCollection("musings");
  for (const m of musings) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    const authorId = refToId(m.data.author as RefLike);
    if (authorId) authored.add(authorId);
    for (const mn of m.data.thinker_mentions ?? []) {
      const id = refToId((mn as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of m.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(authored, referenced);
  }

  // theprint-mirror — no author ref, only mentions
  const tpm = await getCollection("theprint-mirror");
  for (const p of tpm) {
    const referenced = new Set<string>();
    for (const mn of p.data.thinker_mentions ?? []) {
      const id = refToId((mn as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const r of p.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    applyEntry(new Set(), referenced);
  }

  // periodicals — may be empty today; helper still iterates
  const periodicals = await getCollection("periodicals");
  for (const p of periodicals) {
    const authored = new Set<string>();
    const referenced = new Set<string>();
    for (const r of p.data.related_thinkers ?? []) {
      const id = refToId(r as RefLike);
      if (id) referenced.add(id);
    }
    for (const mn of p.data.thinker_mentions ?? []) {
      const id = refToId((mn as any).thinker as RefLike);
      if (id) referenced.add(id);
    }
    for (const tocEntry of (p.data as any).toc ?? []) {
      const aid = refToId(tocEntry.author_resolved as RefLike);
      if (aid) authored.add(aid);
      for (const ctm of tocEntry.cross_thinker_mentions ?? []) {
        const id = refToId(ctm.thinker_resolved as RefLike);
        if (id) referenced.add(id);
      }
    }
    applyEntry(authored, referenced);
  }

  return stats;
}
