// Shared helper for resolving a primary-work's authors[] array into
// renderable entries. Used by both the English and the lang-prefixed
// primary-work detail templates.
//
// The schema for authors[] is a union over the thinkers and organisations
// collections. This helper:
//   1. Discriminates each ref by its .collection field.
//   2. Looks up the entry in the matching collection.
//   3. Returns a flat AuthorEntry[] with just the fields the byline JSX
//      needs (kind / id / name).
//   4. Emits a console.warn at build time if any ref fails to resolve —
//      surfaces typo-or-missing-file regressions that Zod can't catch
//      (Zod's union accepts any string as a thinker id; file existence
//      isn't validated at parse time). Without this warning, an
//      unresolved ref would silently disappear from the byline.
//
// See docs/superpowers/specs/2026-05-23-organisational-authorship-design.md §5.2
// and SESSION-SUMMARY-org-authorship.md (deferred items 1 + 2).

import { getCollection } from "astro:content";

export type AuthorEntry =
  | { kind: "thinker"; id: string; name: string }
  | { kind: "organisation"; id: string; name: string };

// Loose structural type that matches what Astro emits for a
// z.union([reference('thinkers'), reference('organisations')]) field.
type AuthorsRef = { id: string; collection: string };

/**
 * Resolve a primary-work's authors[] refs against the live thinkers
 * and organisations collections.
 *
 * @param authors   The fm.authors array (or undefined for works with none).
 * @param workId    The primary-work's id, used in build-time warnings
 *                  so unresolved refs name the file they came from.
 */
export async function resolveAuthorEntries(
  authors: readonly AuthorsRef[] | undefined,
  workId: string,
): Promise<AuthorEntry[]> {
  const allThinkers = await getCollection("thinkers");
  const allOrgs = await getCollection("organisations");
  const thinkersById = new Map(allThinkers.map((t) => [t.id, t]));
  const orgsById = new Map(allOrgs.map((o) => [o.id, o]));

  const resolved: AuthorEntry[] = [];

  for (const ref of authors ?? []) {
    const id = ref.id;
    if (ref.collection === "organisations") {
      const o = orgsById.get(id);
      if (o) {
        resolved.push({ kind: "organisation", id, name: o.data.name.canonical });
      } else {
        console.warn(
          `[resolve-author-entries] primary-works/${workId}: authors[] references organisation '${id}' which does not exist in apps/site/src/content/organisations/. Entry dropped from byline.`,
        );
      }
    } else {
      const t = thinkersById.get(id);
      if (t) {
        resolved.push({ kind: "thinker", id, name: t.data.name.canonical });
      } else {
        console.warn(
          `[resolve-author-entries] primary-works/${workId}: authors[] references thinker '${id}' which does not exist in apps/site/src/content/thinkers/. Entry dropped from byline.`,
        );
      }
    }
  }

  return resolved;
}
