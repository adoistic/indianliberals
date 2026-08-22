#!/usr/bin/env node
/**
 * Pack the rendered cover thumbnails into one blob plus an offset index.
 *
 * Same reasoning as the agent surfaces: R2 has no file-count limit, but
 * uploading 6,355 objects through wrangler costs a process start each. One
 * blob and one index upload in seconds, and apps/archive-root serves any
 * `covers/<slug>.webp` out of a byte range, so the public URL is identical to
 * the 1,463 covers that are individual objects.
 *
 *   node scripts/deploy/pack-covers.mjs [--dir build-artifacts/covers]
 */
import { readdir, readFile, writeFile, stat } from "node:fs/promises";
import { createWriteStream } from "node:fs";
import { join } from "node:path";

const arg = (n, d) => { const i = process.argv.indexOf(n); return i > -1 ? process.argv[i + 1] : d; };
const DIR = arg("--dir", "build-artifacts/covers");

const names = (await readdir(DIR)).filter((n) => n.endsWith(".webp") && !n.startsWith("_")).sort();
const packPath = join(DIR, "_pack.webpack");
const idx = {};
let offset = 0;
const sink = createWriteStream(packPath);
for (const name of names) {
  const buf = await readFile(join(DIR, name));
  if (!sink.write(buf)) await new Promise((r) => sink.once("drain", r));
  idx[`covers/${name}`] = [offset, buf.length];
  offset += buf.length;
}
await new Promise((r) => sink.end(r));
await writeFile(join(DIR, "_pack.idx.json"), JSON.stringify(idx));
const { size } = await stat(join(DIR, "_pack.idx.json"));
console.log(`  covers packed : ${names.length.toLocaleString()}`);
console.log(`  pack          : ${(offset / 1e6).toFixed(1)} MB`);
console.log(`  index         : ${(size / 1e6).toFixed(2)} MB`);
