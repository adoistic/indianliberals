#!/usr/bin/env node
/**
 * A list must still be a list after the CMS has opened the file and saved it.
 *
 * This test exists because it was not. YAML flow style writes a list as
 * `[philosopher, writer, activist]` and does not quote the items, which is how
 * 390 thinker files record `vocations`. The reader handed that to JSON.parse,
 * which rejects unquoted scalars, and on failure kept the raw text. The list
 * became a string. The writer then quoted the string correctly on the way out,
 * the site's schema refused an array field holding a string, and every
 * Cloudflare Pages build failed from that commit onward. Six days of editors'
 * work sat in the repo and never reached the site, and nothing anywhere said
 * so.
 *
 * So: parse the shapes this archive actually contains, and prove that what
 * comes back out of the writer can be read again as the same thing.
 *
 * Run: node scripts/test-yaml-flow.mjs
 */

import { scalar } from '../src/lib/yaml-scalar.ts';
import { toMarkdownFile } from '../src/lib/ingest.ts';

let failures = 0;

function check(label, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (!ok) failures += 1;
  console.log(
    `${ok ? 'ok  ' : 'FAIL'}  ${label.padEnd(52)} ${ok ? '' : `\n        expected ${JSON.stringify(expected)}\n        got      ${JSON.stringify(actual)}`}`,
  );
}

// ── Reading flow style ──────────────────────────────────────────────────
// The first case is the exact text that took the site down.
check('bare flow sequence', scalar('[philosopher, writer, activist]'), [
  'philosopher',
  'writer',
  'activist',
]);
check('single item', scalar('[economist]'), ['economist']);
check('empty sequence', scalar('[]'), []);
check('empty mapping', scalar('{}'), {});
check('padded items', scalar('[ a ,  b ]'), ['a', 'b']);
check('trailing comma', scalar('[a, b,]'), ['a', 'b']);
check('double quoted items', scalar('["a, still one", "b"]'), ['a, still one', 'b']);
check('single quoted items', scalar("['it''s one', 'b']"), ["it's one", 'b']);
check('numbers and booleans keep their type', scalar('[1, 2.5, true, null]'), [1, 2.5, true, null]);
check('nested sequence', scalar('[a, [b, c]]'), ['a', ['b', 'c']]);
check('flow mapping', scalar('{scale: national, places: []}'), { scale: 'national', places: [] });
check('mapping with quoted key', scalar('{"a b": 1}'), { 'a b': 1 });
check('nested mapping in sequence', scalar('[{a: 1}, {b: 2}]'), [{ a: 1 }, { b: 2 }]);
// Devanagari and Bengali appear in also_known_as across the thinker files.
check('non-latin items', scalar('[एम. एन. रॉय, এম. এন. রায়]'), ['एम. एन. रॉय', 'এম. এন. রায়']);

// ── The rule the reader is built on ─────────────────────────────────────
// Anything it cannot understand comes back exactly as it was found, so a save
// can never quietly drop or mangle it.
check('unterminated bracket stays text', scalar('[a, b'), '[a, b');
check('trailing junk stays text', scalar('[a, b] and more'), '[a, b] and more');
check('unterminated quote stays text', scalar('["a]'), '["a]');
check('mapping without a colon stays text', scalar('{a 1}'), '{a 1}');
check('a title in brackets stays text', scalar('[Reprinted 1957'), '[Reprinted 1957');

// ── Round trip: what the writer emits must read back the same ───────────
// This is the assertion that would have caught the outage. Parse the flow
// text, hand the value to the real writer, and confirm the field is still a
// list and not a string wearing quotes.
const roundTrips = [
  ['vocations', '[philosopher, writer, activist]'],
  ['themes', '[liberalism, free-trade]'],
  ['affiliations', '[swatantra-party]'],
  ['related_thinkers', '[minoo-masani, a-d-shroff]'],
  ['ideology', '[classical-liberal]'],
];
for (const [field, text] of roundTrips) {
  const value = scalar(text);
  const file = toMarkdownFile({ id: 'x', [field]: value });
  const emitted = file.slice(file.indexOf(`${field}:`), file.indexOf('\n---', 4));
  const quotedString = emitted.includes(`${field}: "[`);
  check(`${field} survives the writer as a list`, Array.isArray(value) && !quotedString, true);
}

// The writer's own output, read back through the reader, must be unchanged.
// toMarkdownFile writes lists in block style, which the block reader in
// edit.astro handles; what matters here is that no field is ever emitted as a
// bracketed string, because that is what the site's schema rejects.
const all = toMarkdownFile({
  id: 'm-n-roy',
  vocations: scalar('[philosopher, writer, activist]'),
  themes: scalar('[]'),
  geographic_scope: scalar('{scale: national, places: []}'),
});
check('no field emitted as a bracketed string', /: "\[/.test(all), false);
check('list emitted in block style', /vocations:\s*\n- philosopher\n- writer\n- activist/.test(all), true);

console.log(failures ? `\n${failures} failures` : '\nall cases behave');
process.exit(failures ? 1 : 0);
