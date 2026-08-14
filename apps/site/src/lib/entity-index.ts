// Thinkers and organisations, indexed by id, built once for the whole build.
//
// Both collections are read on almost every detail page: the byline resolver
// wants them for authors and editors, PeopleInPiece wants thinkers for the
// names at the foot of a piece. Each of those used to call getCollection and
// build its own Map every time it ran, which is 725 thinkers plus 106
// organisations re-indexed roughly four thousand times a build.
//
// That was affordable until it wasn't. Adding a second byline resolution per
// work page, so an edited volume could be credited to its editors, pushed the
// Cloudflare Pages build past its time limit and the deploy was terminated
// after roughly twice the twenty-three minutes the previous one took. Building
// the tables once removes the whole class of problem and leaves the build
// quicker than it was before that call was added.
//
// A module-level promise is the right shape here rather than a plain object:
// pages render concurrently, and the promise means the second caller waits for
// the first build rather than starting its own. Nothing is mutated after
// construction, so sharing the Maps between pages is safe.

import { getCollection } from "astro:content";
import type { CollectionEntry } from "astro:content";

export interface EntityIndex {
  thinkersById: Map<string, CollectionEntry<"thinkers">>;
  orgsById: Map<string, CollectionEntry<"organisations">>;
}

let cached: Promise<EntityIndex> | null = null;

export function entityIndex(): Promise<EntityIndex> {
  if (!cached) {
    cached = (async () => {
      const [thinkers, orgs] = await Promise.all([
        getCollection("thinkers"),
        getCollection("organisations"),
      ]);
      return {
        thinkersById: new Map(thinkers.map((t) => [t.id, t])),
        orgsById: new Map(orgs.map((o) => [o.id, o])),
      };
    })();
  }
  return cached;
}
