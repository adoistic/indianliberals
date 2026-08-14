#!/usr/bin/env node
/**
 * Every id in the content must point at something that exists.
 *
 * `astro sync` validates shapes, not targets. Astro's `reference()` records
 * `{ collection, id }` at parse time and does not check that the file is
 * there; the lookup happens later, at render, where a miss returns undefined
 * and the page simply omits whatever it was going to show. Nothing fails, and
 * nothing is logged.
 *
 * That gap has cost real content twice:
 *
 *   - An editor typed "Avanti lele" into a musing's Author field. Musings point
 *     at the thinkers collection and Avanti Lele is a contributor, so there was
 *     no such thinker. The byline silently disappeared. CCS reported it in
 *     round 4 as "the author's name is not displaying correctly", and from the
 *     outside it was indistinguishable from a rendering bug.
 *   - Thirteen works listed an organisation in `authors[]` as a bare string.
 *     A bare string always resolves through the first arm of the
 *     thinkers-or-organisations union, so all thirteen bylines were dropped.
 *     Organisation authorship needs the object form:
 *     `- { collection: organisations, id: forum-of-free-enterprise }`.
 *
 * This script closes both. It runs in CI beside `astro sync`, and it names the
 * file, the field and the value, so a bad save is a one-minute fix rather than
 * an archaeological dig.
 *
 * Usage:  node scripts/check-references.mjs
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const CONTENT = join(ROOT, 'src/content');

/**
 * Which fields carry an id, and what that id must point at.
 *
 * `list` fields hold a YAML sequence; `scalar` fields hold one value. `nested`
 * fields are looked for at any depth, because thinker_mentions and contributors
 * are lists of objects and their ids sit one or two levels down.
 *
 * `union` marks the authors/editors pair: a bare string means a thinker, and an
 * object form names its own collection. Both are checked, and a bare string
 * that names no thinker but does name an organisation is reported with the fix.
 */
const RULES = {
  musings: [
    { field: 'author', kind: 'scalar', target: 'thinkers', severity: 'error' },
    { field: 'related_thinkers', kind: 'list', target: 'thinkers', severity: 'error' },
    { field: 'thinker', kind: 'nested', target: 'thinkers', severity: 'error' },
    { field: 'excerpt_of', kind: 'scalar', target: 'primary-works', severity: 'warn' },
  ],
  opinions: [
    { field: 'author', kind: 'scalar', target: 'contributors', severity: 'error' },
    { field: 'subject', kind: 'scalar', target: 'thinkers', severity: 'error' },
    { field: 'related_thinkers', kind: 'list', target: 'thinkers', severity: 'error' },
    { field: 'thinker', kind: 'nested', target: 'thinkers', severity: 'error' },
    { field: 'related_works', kind: 'list', target: 'primary-works', severity: 'warn' },
  ],
  'primary-works': [
    { field: 'authors', kind: 'union', target: 'thinkers', severity: 'error' },
    { field: 'editors', kind: 'union', target: 'thinkers', severity: 'error' },
    { field: 'related_thinkers', kind: 'list', target: 'thinkers', severity: 'error' },
    { field: 'series_id', kind: 'scalar', target: 'series', severity: 'error' },
    { field: 'thinker', kind: 'nested', target: 'thinkers', severity: 'error' },
    { field: 'author_resolved', kind: 'nested', target: 'thinkers', severity: 'error' },
    { field: 'related_works', kind: 'list', target: 'primary-works', severity: 'warn' },
    { field: 'publisher_id', kind: 'scalar', target: 'organisations', severity: 'warn' },
    { field: 'issuer_id', kind: 'scalar', target: 'organisations', severity: 'warn' },
    { field: 'thinker_id', kind: 'nested', target: 'thinkers', severity: 'warn' },
  ],
  thinkers: [{ field: 'affiliations', kind: 'list', target: 'organisations', severity: 'warn' }],
  series: [
    { field: 'parent_series', kind: 'scalar', target: 'series', severity: 'error' },
    { field: 'publisher_id', kind: 'scalar', target: 'organisations', severity: 'warn' },
    { field: 'issuer_id', kind: 'scalar', target: 'organisations', severity: 'warn' },
  ],
  organisations: [],
  contributors: [],
};

/** Every id present in a collection, from its file names. */
function idsIn(collection) {
  const dir = join(CONTENT, collection);
  if (!existsSync(dir)) return new Set();
  return new Set(
    readdirSync(dir)
      .filter((f) => f.endsWith('.md') || f.endsWith('.mdx') || f.endsWith('.json'))
      .map((f) => f.replace(/\.(md|mdx|json)$/, '')),
  );
}

const KNOWN = Object.fromEntries(
  ['thinkers', 'organisations', 'contributors', 'primary-works', 'musings', 'opinions', 'series'].map(
    (c) => [c, idsIn(c)],
  ),
);

const clean = (s) => s.trim().replace(/^["']|["']$/g, '').trim();

/** The frontmatter block, as raw lines. */
function frontmatter(text) {
  const m = /^---\n([\s\S]*?)\n---/.exec(text);
  return m ? m[1].split('\n') : [];
}

/**
 * Collect every value written against `field`, wherever it sits.
 *
 * Scalars take the value on the same line. Lists take the `- item` lines that
 * follow at a deeper indent. Nested fields are just scalars found at any depth,
 * which is what makes them work inside object lists.
 */
function valuesFor(lines, field, kind) {
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const m = new RegExp(`^(\\s*)-?\\s*${field}:\\s*(.*)$`).exec(lines[i]);
    if (!m) continue;
    const indent = m[1].length;
    const inline = clean(m[2]);

    if (kind === 'scalar' || kind === 'nested') {
      if (inline && inline !== '~' && inline !== 'null') out.push({ value: inline, line: i + 1 });
      continue;
    }

    // A list: either flow style on the same line, or `- item` lines below.
    if (inline.startsWith('[')) {
      for (const part of inline.slice(1, -1).split(',')) {
        const v = clean(part);
        if (v) out.push({ value: v, line: i + 1 });
      }
      continue;
    }
    for (let j = i + 1; j < lines.length; j++) {
      const item = /^(\s*)-\s+(.*)$/.exec(lines[j]);
      if (!item || item[1].length < indent) break;
      const v = clean(item[2]);
      if (v) out.push({ value: v, line: j + 1 });
      // Stop at the next key at the same or shallower indent.
      const next = lines[j + 1];
      if (next && /^\s*[A-Za-z_]/.test(next) && (next.match(/^\s*/) ?? [''])[0].length <= indent) break;
    }
  }
  return out;
}

const problems = [];

for (const [collection, rules] of Object.entries(RULES)) {
  const dir = join(CONTENT, collection);
  if (!existsSync(dir) || rules.length === 0) continue;

  for (const file of readdirSync(dir).filter((f) => f.endsWith('.md'))) {
    const lines = frontmatter(readFileSync(join(dir, file), 'utf8'));
    if (lines.length === 0) continue;

    for (const rule of rules) {
      for (const { value, line } of valuesFor(lines, rule.field, rule.kind)) {
        // The object form names its own collection: `{ collection: x, id: y }`.
        const obj = /\{\s*collection:\s*([a-z-]+)\s*,\s*id:\s*([^}\s]+)\s*\}/.exec(value);
        if (obj) {
          const [, target, id] = obj;
          if (!KNOWN[target]) {
            problems.push({ severity: rule.severity, collection, file, line, field: rule.field, value, why: `no collection "${target}"` });
          } else if (!KNOWN[target].has(id)) {
            problems.push({ severity: rule.severity, collection, file, line, field: rule.field, value: id, why: `no ${target} with that id` });
          }
          continue;
        }
        // Anything with a space or a slash is prose or a path, not an id.
        if (/[\s/]/.test(value) && rule.kind !== 'scalar') continue;

        const target = KNOWN[rule.target];
        if (!target || target.has(value)) continue;

        // A bare string that names an organisation is the union trap.
        if (rule.kind === 'union' && KNOWN.organisations.has(value)) {
          problems.push({
            severity: 'error', collection, file, line, field: rule.field, value,
            why: `is an organisation, so it needs the object form: - { collection: organisations, id: ${value} }`,
          });
          continue;
        }
        problems.push({ severity: rule.severity, collection, file, line, field: rule.field, value, why: `no ${rule.target} with that id` });
      }
    }
  }
}

const errors = problems.filter((p) => p.severity === 'error');
const warnings = problems.filter((p) => p.severity !== 'error');
const total = Object.values(KNOWN).reduce((n, s) => n + s.size, 0);

function show(list, stream) {
  for (const p of list) {
    stream(`  src/content/${p.collection}/${p.file}:${p.line}`);
    stream(`    ${p.field}: ${p.value}`);
    stream(`    ${p.why}\n`);
  }
}

if (warnings.length > 0) {
  // Loose id fields: publisher and issuer ids double as grouping keys and do
  // not always name an organisation record, and excerpt_of predates the
  // primary-works link. These are worth knowing about and are not a reason to
  // stop a deploy.
  console.log(`${warnings.length} loose id${warnings.length === 1 ? '' : 's'} name nothing in the archive (not fatal):\n`);
  show(warnings.slice(0, 25), (s) => console.log(s));
  if (warnings.length > 25) console.log(`  ... and ${warnings.length - 25} more.\n`);
}

if (errors.length === 0) {
  console.log(`OK: every reference resolves, across ${total} entries.`);
  process.exit(0);
}

console.error(`\n${errors.length} reference${errors.length === 1 ? '' : 's'} point at nothing:\n`);
show(errors, (s) => console.error(s));
console.error(
  'Each of these renders as a silent gap: the byline, the link or the card is\n' +
  'simply left out, with no error anywhere. Fix the id, or create the entry.\n',
);
process.exit(1);
