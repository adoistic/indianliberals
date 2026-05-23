// Enforces the invariant that a slug is unique across the union of the
// thinkers/ and organisations/ collections. The primaryWorks.authors[] schema
// is a Zod union over reference('thinkers') | reference('organisations');
// the union resolves by trying each arm in order, so a slug that exists in
// BOTH collections would silently route to thinkers and never to organisations.
// See docs/superpowers/specs/2026-05-23-organisational-authorship-design.md §6.
import { readdirSync } from "node:fs";
import { resolve } from "node:path";

const CONTENT = resolve(import.meta.dirname, "../content");

const slugsOf = (dir: string) =>
  new Set(
    readdirSync(resolve(CONTENT, dir))
      .filter((f) => /\.(md|mdx)$/.test(f))
      .map((f) => f.replace(/\.(md|mdx)$/, "")),
  );

const thinkers = slugsOf("thinkers");
const orgs = slugsOf("organisations");
const overlap = [...thinkers].filter((s) => orgs.has(s));

if (overlap.length) {
  throw new Error(
    `Slug overlap between thinkers/ and organisations/: ${overlap.join(", ")}. ` +
      `A slug must be unique across the union of these collections (see ` +
      `docs/superpowers/specs/2026-05-23-organisational-authorship-design.md §6).`,
  );
}
