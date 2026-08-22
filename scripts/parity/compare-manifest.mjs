#!/usr/bin/env node
/**
 * Gate 1: byte parity on everything still in dist.
 *
 * Diffs a fresh manifest of apps/site/dist against the golden manifest taken
 * from the last all-static build. The ONLY differences allowed are the paths
 * deliberately moved to R2. Anything else — a changed hash, a file that
 * vanished, a file that appeared — is a regression in a change that is
 * supposed to be invisible to users.
 *
 *   node scripts/parity/compare-manifest.mjs
 */
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";

const isMoved = (u) =>
  (u.startsWith("/api/works/") && u.endsWith(".json")) ||
  (u.endsWith(".md") && u.lastIndexOf("/") > 0);

const parse = (txt) => {
  const m = new Map();
  for (const line of txt.split("\n")) {
    const g = line.match(/^([0-9a-f]{64})\s+(.+)$/);
    // pagefind fragment names are content-addressed and churn on any content
    // edit; the search gate covers them instead.
    if (g && !g[2].startsWith("pagefind/") && !g[2].startsWith(".wrangler/")) m.set("/" + g[2], g[1]);
  }
  return m;
};

const golden = parse(await readFile("data/parity/golden-manifest.txt", "utf8"));
const current = parse(
  execFileSync("bash", ["-c",
    "cd apps/site/dist && find . -type f ! -path './pagefind/*' -print0 | xargs -0 shasum -a 256 | sed 's|  \\./|  |'",
  ], { maxBuffer: 1 << 28 }).toString(),
);

let movedGone = 0, changed = 0, missing = 0, added = 0;
for (const [url, hash] of golden) {
  if (!current.has(url)) { isMoved(url) ? movedGone++ : (missing++, console.log(`  MISSING  ${url}`)); }
  else if (current.get(url) !== hash) { changed++; console.log(`  CHANGED  ${url}`); }
}
for (const url of current.keys()) if (!golden.has(url)) { added++; console.log(`  ADDED    ${url}`); }

console.log(`\ngolden files            : ${golden.size}`);
console.log(`current files           : ${current.size}`);
console.log(`moved to R2 (expected)  : ${movedGone}`);
console.log(`changed hash            : ${changed}`);
console.log(`missing (unexplained)   : ${missing}`);
console.log(`added (unexplained)     : ${added}`);
process.exitCode = changed || missing || added ? 1 : 0;
