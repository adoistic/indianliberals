#!/usr/bin/env node
/**
 * Put `/llms-full.txt` on R2 and take it out of the deployment.
 *
 * The build writes the whole-corpus dump into dist/. It was 29 MB when it
 * was first moved to R2 and is past 35 MB now, and Cloudflare Pages refuses
 * any single file over 25 MiB: leave it in dist and the deploy is rejected
 * outright, after the upload has already run for a minute. So the file goes
 * to the bucket and `functions/llms-full.txt.js` streams it from there,
 * range requests and all, at the same URL it has always had.
 *
 * Run it after the pack step and before `wrangler pages deploy`. Running it
 * twice is harmless: with the file already gone from dist there is nothing
 * to do and it says so.
 *
 *   node scripts/deploy/publish-llms-full.mjs [--dist apps/site/dist]
 */
import { execFileSync } from "node:child_process";
import { stat, rm } from "node:fs/promises";
import { join } from "node:path";

const arg = (n, d) => { const i = process.argv.indexOf(n); return i > -1 ? process.argv[i + 1] : d; };
const DIST = arg("--dist", "apps/site/dist");
const BUCKET = "indianliberals-archive";
const KEY = "agent/llms-full.txt";
const PATH = join(DIST, "llms-full.txt");

// Below this the file is not the corpus dump but a truncated build. Publishing
// it would replace a good copy on R2 with a broken one, and the site would
// serve the broken one at a URL that is published in SKILL.md.
const FLOOR_MB = 10;

let size;
try {
  ({ size } = await stat(PATH));
} catch {
  console.log(`${PATH} is not there. Already published, or this dist was built without it.`);
  process.exit(0);
}

const mb = size / 1e6;
if (mb < FLOOR_MB) {
  console.error(`llms-full.txt is only ${mb.toFixed(1)} MB, which is too small to be the corpus.`);
  console.error("Refusing to overwrite the copy on R2. Check the build before deploying.");
  process.exit(1);
}

process.stdout.write(`  llms-full.txt ${mb.toFixed(1)} MB  `);
execFileSync("npx", [
  "wrangler", "r2", "object", "put", `${BUCKET}/${KEY}`,
  "--file", PATH, "--content-type", "text/plain; charset=utf-8", "--remote",
], { stdio: ["ignore", "ignore", "inherit"] });
console.log("uploaded");

await rm(PATH);
console.log(`removed from ${DIST}, which is what lets the deploy through.`);
