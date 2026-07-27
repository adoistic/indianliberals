#!/usr/bin/env node
// Guard against em dashes (— / &mdash;) creeping back into the hard-coded UI
// copy. CCS flagged em dashes as reading "AI-generated"; we removed them from
// the .astro / .ts UI files (round-2 feedback, item #5). This check keeps them
// out of new UI code. It deliberately scans only src/pages, src/components,
// src/layouts (our-voice UI). Content markdown under src/content is NOT scanned
// here: an em dash inside a quoted primary-source passage is legitimate.
//
// Usage: node scripts/lint-no-emdash.mjs   (exit 1 on any hit)

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOTS = ["src/pages", "src/components", "src/layouts"];
// Only the rendered human UI (.astro). The agent-layer text generators
// (AGENTS.md.ts, llms.txt.ts, llms-full.txt.ts) emit machine-facing markdown
// for LLMs where an em dash is a normal separator, not an "AI-tell" in the
// human copy CCS flagged, so .ts endpoint generators are out of scope.
const EXTS = [".astro"];

// Lines matching any of these are allowed to contain an em dash (functional
// code, not copy). Keep this list tiny and justified.
const ALLOW = [
  // periodicals/index.astro: regex that strips a leading "Name — " / "Name: "
  // / "Name - " prefix from imported issue titles. The — is matched data, not UI copy.
  /\[:—-\]/,
  // series/[series].astro: an em dash standing in for a missing year in a card.
  // A placeholder glyph in a data slot is typographic convention, not prose, and
  // spelling it out would not fit the cell.
  /\?\?\s*"—"/,
];

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const s = statSync(p);
    if (s.isDirectory()) walk(p, out);
    else if (EXTS.some((e) => p.endsWith(e))) out.push(p);
  }
  return out;
}

const hits = [];
for (const root of ROOTS) {
  let files;
  try {
    files = walk(root);
  } catch {
    continue; // root may not exist in some checkouts
  }
  for (const file of files) {
    const lines = readFileSync(file, "utf8").split("\n");
    // Comments are not copy. This check exists because CCS reads em dashes in
    // the *rendered* text as AI-generated; an em dash in a note to the next
    // developer is invisible to a reader. Scanning them made the check fail on
    // main, which is worse than not having it: nobody could use it, and real em
    // dashes crept back into visible copy behind the noise.
    let inBlockComment = false;
    lines.forEach((line, i) => {
      const trimmed = line.trim();

      // Track /* … */ and JSX {/* … */} spans across lines.
      const opens = /\/\*|\{\/\*/.test(line);
      const closes = /\*\/\}?/.test(line);
      const wasInBlock = inBlockComment;
      if (opens && !closes) inBlockComment = true;
      else if (closes && inBlockComment) inBlockComment = false;

      const isComment =
        wasInBlock ||
        inBlockComment ||
        trimmed.startsWith("//") ||
        trimmed.startsWith("*") ||
        trimmed.startsWith("/*") ||
        trimmed.startsWith("{/*");

      if (isComment) return;
      if (!/—|&mdash;/.test(line)) return;
      if (ALLOW.some((re) => re.test(line))) return;
      hits.push(`${file}:${i + 1}: ${line.trim()}`);
    });
  }
}

if (hits.length) {
  console.error("Em dashes found in UI copy (use a comma, colon, or full stop instead):\n");
  console.error(hits.join("\n"));
  console.error(`\n${hits.length} occurrence(s). See scripts/lint-no-emdash.mjs.`);
  process.exit(1);
}
console.log("OK: no em dashes in UI copy.");
