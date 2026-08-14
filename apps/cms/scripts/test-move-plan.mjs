// What a move does to a record, checked rather than assumed.
//
// The case that matters is a musing becoming an opinion, which is what CCS
// asked for. Two things have to happen and neither is obvious: the author has
// to become the subject, because a musing's author field points at thinkers and
// on a profile it holds the person the piece is ABOUT; and `kind` has to be
// dropped, because the two collections share the field name and share none of
// its values.
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync, rmSync, mkdirSync } from 'node:fs';

mkdirSync('/tmp/movecheck', { recursive: true });
for (const f of ['collections.ts', 'move.ts']) {
  writeFileSync(`/tmp/movecheck/${f}`, readFileSync(`src/lib/${f}`, 'utf8'));
}
execSync('npx tsc /tmp/movecheck/collections.ts /tmp/movecheck/move.ts --target es2022 --module es2022 --moduleResolution bundler --outDir /tmp/movecheck/out', { stdio: 'pipe' });

const { COLLECTIONS } = await import('/tmp/movecheck/out/collections.js');
const { planMove } = await import('/tmp/movecheck/out/move.js');

const musings = COLLECTIONS.find((c) => c.id === 'musings');
const opinions = COLLECTIONS.find((c) => c.id === 'opinions');

const musing = {
  id: 'acharya-n-g-ranga',
  title: 'Acharya N G Ranga',
  pubDate: '2023-11-15T12:24:03Z',
  author: 'n-g-ranga',              // the SUBJECT, mislabelled by the schema
  kind: 'periodical-article',       // not a value an opinion may hold
  excerpt_of: 'some-work',          // opinions have no such field
  hero_image: '/musings/covers/x.webp',
  themes: ['agriculture'],
  thinker_mentions: [{ thinker: 'jawaharlal-nehru', role: 'mention' }],
};

const plan = planMove(musing, musings, opinions);
let bad = 0;
const check = (label, ok, detail) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${label}${detail ? `  (${detail})` : ''}`);
  if (!ok) bad++;
};

check('author becomes subject', plan.data.subject === 'n-g-ranga', `subject=${plan.data.subject}`);
check('author itself does not survive', plan.data.author === undefined);
check('kind is dropped, not carried', plan.data.kind === undefined, `kind=${plan.data.kind}`);
check('the drop is reported', plan.dropped.some((d) => d.startsWith('kind')), plan.dropped.join(', '));
check('excerpt_of is dropped', plan.data.excerpt_of === undefined);
check('title, date, themes, mentions survive',
  plan.data.title && plan.data.pubDate && plan.data.themes?.length === 1 && plan.data.thinker_mentions?.length === 1);
check('the missing byline is reported', plan.missing.includes('Byline'), plan.missing.join(', '));

// And the other direction, so the rename table is not one-way by accident.
const back = planMove({ id: 'x', title: 'T', pubDate: 'd', subject: 'n-g-ranga', kind: 'profile' }, opinions, musings);
check('subject becomes author going back', back.data.author === 'n-g-ranga');
check('an opinion kind is dropped going back', back.data.kind === undefined);

rmSync('/tmp/movecheck', { recursive: true, force: true });
console.log(bad === 0 ? '\nall cases behave' : `\n${bad} failed`);
process.exit(bad === 0 ? 0 : 1);
