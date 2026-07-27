#!/usr/bin/env node
/**
 * The quoting rule in ingest.ts decides whether a value is written to YAML
 * plain or wrapped in quotes. Getting it wrong loses data quietly: a title held
 * inside its own quotation marks, written plain, comes back without them, and
 * nobody notices until the archive disagrees with the page.
 *
 * Keep this list in step with the regex in ingest.ts. Run: node scripts/test-yaml-quoting.mjs
 */

const risky = (value) =>
  /^[\s>|&*!%@`{}[\],'"]|:\s|\s#|#\s|^-|^(yes|no|true|false|null|on|off|~)$/i.test(value);

const cases = [
  ['"A Total War on Indian Poverty"', 'title held inside its own quotation marks'],
  ["'Vigilant'", 'single quoted pen name'],
  ['yes', 'reads as a boolean'],
  ['no', 'reads as a boolean'],
  ['null', 'reads as nothing at all'],
  ['~', 'also reads as nothing'],
  ['- leading hyphen', 'reads as a list item'],
  ['key: value', 'reads as a mapping'],
  ['# not a comment', 'reads as a comment'],
  ['a # trailing', 'truncates at the hash'],
  ['[bracketed]', 'reads as a flow sequence'],
  ['{braced}', 'reads as a flow mapping'],
  ['*anchor', 'reads as an alias'],
  ['&anchor', 'reads as an anchor'],
  ['plain title', 'safe, should stay unquoted'],
  ['A. D. Shroff', 'safe, should stay unquoted'],
  ['1957', 'safe as a string here'],
];

let bad = 0;
for (const [value, why] of cases) {
  const quoted = risky(value);
  const shouldQuote = !['plain title', 'A. D. Shroff', '1957'].includes(value);
  const ok = quoted === shouldQuote;
  if (!ok) bad++;
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${quoted ? 'quoted  ' : 'plain   '} ${JSON.stringify(value).padEnd(36)} ${why}`);
}
console.log(bad ? `\n${bad} failures` : '\nall cases behave');
process.exit(bad ? 1 : 0);
