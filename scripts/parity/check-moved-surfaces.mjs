#!/usr/bin/env node
/**
 * Gate 3: the surfaces that moved to R2 must still serve byte-identical bytes.
 *
 * Compares live responses against data/parity/golden-manifest.txt, the SHA-256
 * manifest of the last all-static build. A hash mismatch means an agent or the
 * MCP server would see different content than before the move, which is the
 * one thing this change is not allowed to do.
 *
 *   node scripts/parity/check-moved-surfaces.mjs [--base URL] [--sample N]
 */
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";

const arg = (n, d) => { const i = process.argv.indexOf(n); return i > -1 ? process.argv[i + 1] : d; };
const BASE = arg("--base", "http://127.0.0.1:8788").replace(/\/$/, "");
const SAMPLE = Number(arg("--sample", "300"));

const manifest = new Map();
for (const line of (await readFile("data/parity/golden-manifest.txt", "utf8")).split("\n")) {
  const m = line.match(/^([0-9a-f]{64})\s+(.+)$/);
  if (m) manifest.set("/" + m[2], m[1]);
}

const moved = [...manifest.keys()].filter(
  (u) => (u.startsWith("/api/works/") && u.endsWith(".json")) ||
         (u.endsWith(".md") && u.lastIndexOf("/") > 0),
);

// Deterministic stride rather than random: a failing run must be reproducible.
const stride = Math.max(1, Math.floor(moved.length / SAMPLE));
const picks = moved.filter((_, i) => i % stride === 0).slice(0, SAMPLE);

let ok = 0, bad = 0, err = 0;
for (const url of picks) {
  try {
    const r = await fetch(BASE + url, { headers: { "user-agent": "indianliberals-parity/1.0" } });
    if (!r.ok) { err++; console.log(`  HTTP ${r.status}  ${url}`); continue; }
    const buf = Buffer.from(await r.arrayBuffer());
    const got = createHash("sha256").update(buf).digest("hex");
    if (got === manifest.get(url)) ok++;
    else { bad++; console.log(`  HASH MISMATCH  ${url}`); }
  } catch (e) { err++; console.log(`  ERROR ${e.message}  ${url}`); }
}
console.log(`\nmoved surfaces in manifest : ${moved.length}`);
console.log(`sampled                    : ${picks.length}`);
console.log(`byte-identical             : ${ok}`);
console.log(`mismatched                 : ${bad}`);
console.log(`errored                    : ${err}`);
process.exitCode = bad || err ? 1 : 0;
