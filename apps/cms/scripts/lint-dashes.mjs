#!/usr/bin/env node
// Thothica house style bans em and en dashes in anything a reader sees. The
// site has the same guard; this is the CMS copy, wired into `npm run build`
// so it cannot rot the way the site's did.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ROOTS = ['src'];
const EXTS = ['.astro', '.tsx', '.ts', '.css'];

// Lines allowed to contain a dash because they are the code that finds and
// removes them. Keep this list tiny and obvious.
const ALLOW = [
  /\/\[—–\]\//,        // a character class matching the dashes
  /replace\(\/\\s\*[—–]/, // the strip itself
];

const hits = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (EXTS.some((e) => p.endsWith(e))) {
      readFileSync(p, 'utf8').split('\n').forEach((line, i) => {
        if (!/[—–]|&mdash;|&ndash;/.test(line)) return;
        if (ALLOW.some((re) => re.test(line))) return;
        hits.push(`${p}:${i + 1}: ${line.trim().slice(0, 100)}`);
      });
    }
  }
}

for (const root of ROOTS) { try { walk(root); } catch {} }

if (hits.length) {
  console.error('Em or en dashes found (use commas, colons or full stops):\n');
  console.error(hits.join('\n'));
  process.exit(1);
}
console.log('OK: no em or en dashes.');
