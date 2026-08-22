#!/usr/bin/env node
/**
 * Move the per-work agent surfaces out of dist/ and into two packed blobs.
 *
 * Cloudflare Pages allows 20,000 files per deployment. This build emits 35,841,
 * and 16,835 of them are the machine-readable siblings of pages that are
 * already there: one `.md` per page and one `api/works/<id>.json` per work.
 *
 * They cannot simply be dropped. apps/mcp fetches `/api/works/<id>.json`
 * (tools.ts:226, :457) and public/SKILL.md publishes both families as a
 * contract to outside agents. So the URLs have to keep working byte for byte;
 * only the storage moves.
 *
 * Each family becomes two objects: a `.pack` holding every file's bytes
 * concatenated, and a `.idx.json` mapping URL path -> [offset, length]. R2
 * serves byte ranges (apps/archive-root/src/index.js forwards Range), so a
 * Pages Function can return one record without reading the blob.
 *
 * Raw bytes, not NDJSON: a markdown body may contain any byte sequence,
 * including newlines, and byte parity with today's build is the whole point.
 *
 *   node scripts/deploy/pack-agent-surfaces.mjs [--dist DIR] [--out DIR] [--keep]
 */
import { readdir, readFile, writeFile, mkdir, rm, stat } from "node:fs/promises";
import { createWriteStream } from "node:fs";
import { join, relative, sep } from "node:path";
import { argv } from "node:process";

const arg = (name, dflt) => {
  const i = argv.indexOf(name);
  return i > -1 ? argv[i + 1] : dflt;
};
const DIST = arg("--dist", "apps/site/dist");
const OUT = arg("--out", "build-artifacts/agent");
const KEEP = argv.includes("--keep");   // leave dist untouched (for parity runs)

async function* walk(dir) {
  let entries;
  try { entries = await readdir(dir, { withFileTypes: true }); }
  catch { return; }
  for (const e of entries) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else yield p;
  }
}

/** Files whose URL is the dist path minus the leading dist dir. */
async function collect(pred) {
  const out = [];
  for await (const p of walk(DIST)) {
    const url = "/" + relative(DIST, p).split(sep).join("/");
    if (pred(url)) out.push({ path: p, url });
  }
  out.sort((a, b) => (a.url < b.url ? -1 : a.url > b.url ? 1 : 0));
  return out;
}

async function pack(name, files) {
  await mkdir(OUT, { recursive: true });
  const packPath = join(OUT, `${name}.pack`);
  const idx = {};
  let offset = 0;
  const sink = createWriteStream(packPath);
  for (const f of files) {
    const buf = await readFile(f.path);
    if (!sink.write(buf)) await new Promise((r) => sink.once("drain", r));
    idx[f.url] = [offset, buf.length];
    offset += buf.length;
  }
  await new Promise((r) => sink.end(r));
  await writeFile(join(OUT, `${name}.idx.json`), JSON.stringify(idx));
  return { count: files.length, bytes: offset };
}

const families = [
  // `/api/works/<id>.json` only — the aggregates (works.json, search-index.json
  // …) are six files and stay in dist, where the MCP server and the site's own
  // code expect them.
  { name: "api-works", pred: (u) => u.startsWith("/api/works/") && u.endsWith(".json") },
  // Every per-page `.md` sibling, but NOT the two root documents. /AGENTS.md
  // and /SKILL.md are how an agent discovers everything else; making the entry
  // point depend on the same storage it describes is a bad failure mode, and
  // two files cost nothing against the cap.
  { name: "pages-md", pred: (u) => u.endsWith(".md") && u.lastIndexOf("/") > 0 },
];

let removed = 0;
for (const fam of families) {
  const files = await collect(fam.pred);
  const { count, bytes } = await pack(fam.name, files);
  console.log(`  ${fam.name.padEnd(10)} ${String(count).padStart(6)} files  ${(bytes / 1e6).toFixed(1)} MB`);
  if (!KEEP) {
    for (const f of files) { await rm(f.path); removed++; }
  }
}
const left = [];
for await (const p of walk(DIST)) left.push(p);
console.log(`\n  removed from dist : ${removed}`);
console.log(`  files now in dist : ${left.length}  (Pages limit 20,000)`);
if (left.length >= 20000) {
  console.error("  STILL OVER THE LIMIT");
  process.exitCode = 1;
}
