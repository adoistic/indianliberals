#!/usr/bin/env node
/**
 * Put the packed agent surfaces on R2, under `agent/`.
 *
 * Four objects, so `wrangler r2 object put` per file is fine here — the reason
 * the surfaces are packed at all is that 16,833 separate uploads would not be.
 *
 *   node scripts/deploy/upload-agent-surfaces.mjs [--dir build-artifacts/agent]
 */
import { execFileSync } from "node:child_process";
import { stat } from "node:fs/promises";
import { join } from "node:path";

const arg = (n, d) => { const i = process.argv.indexOf(n); return i > -1 ? process.argv[i + 1] : d; };
const DIR = arg("--dir", "build-artifacts/agent");
const BUCKET = "indianliberals-archive";

const files = [
  ["api-works.idx.json", "application/json"],
  ["api-works.pack", "application/octet-stream"],
  ["pages-md.idx.json", "application/json"],
  ["pages-md.pack", "application/octet-stream"],
];

for (const [name, ct] of files) {
  const path = join(DIR, name);
  const { size } = await stat(path);
  process.stdout.write(`  ${name.padEnd(20)} ${(size / 1e6).toFixed(1).padStart(6)} MB  `);
  execFileSync("npx", [
    "wrangler", "r2", "object", "put", `${BUCKET}/agent/${name}`,
    "--file", path, "--content-type", ct, "--remote",
  ], { stdio: ["ignore", "ignore", "inherit"] });
  console.log("uploaded");
}
console.log("\nagent surfaces published to R2.");
