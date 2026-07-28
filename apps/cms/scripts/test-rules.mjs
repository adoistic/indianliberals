#!/usr/bin/env node
/**
 * The security rules are the root of trust, so they get tested.
 *
 * There is no Firebase service account anywhere in this project. Nothing
 * server-side can bypass a rule, which is the point, and which also means that
 * if a rule is wrong the CMS is either broken or unsafe with nothing in
 * between. Everything below runs against the real firestore.rules in the
 * emulator, with mock tokens, so no real account and no real data is involved.
 *
 * Run with:  npm run test:rules
 * Needs Java, which the Firestore emulator requires.
 */

import {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds,
} from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, deleteDoc, collection, getDocs } from 'firebase/firestore';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

const env = await initializeTestEnvironment({
  projectId: 'thothica-cms-rules-test',
  firestore: {
    rules: readFileSync(join(here, '../firestore.rules'), 'utf8'),
    host: '127.0.0.1',
    port: 8080,
  },
});

let failures = 0;
const check = async (name, promise) => {
  try {
    await promise;
    console.log(`ok    ${name}`);
  } catch (error) {
    failures++;
    console.log(`FAIL  ${name}\n        ${String(error.message).slice(0, 160)}`);
  }
};

/** A signed-in, verified user at this address. */
const as = (email) =>
  env.authenticatedContext(email, { email, email_verified: true }).firestore();

const SUPER = 'adnan@thothica.com';
const ADMIN = 'kumar@ccs.in';
const SUB = 'arjun@ccs.in';
const CONTRIB = 'intern@ccs.in';
const OUTSIDER = 'nobody@example.com';

// Roles are set up with the rules disabled, the way they would be by an admin
// who already has the right to do it. What is under test is the drafts model.
await env.withSecurityRulesDisabled(async (ctx) => {
  const db = ctx.firestore();
  await setDoc(doc(db, 'roles', ADMIN), { role: 'admin' });
  await setDoc(doc(db, 'roles', SUB), { role: 'sub_admin' });
  await setDoc(doc(db, 'roles', CONTRIB), { role: 'contributor' });
});

const draft = (author) => ({
  collection: 'primary-works',
  slug: 'a-scanned-pamphlet',
  data: { id: 'a-scanned-pamphlet' },
  body: '',
  author,
  status: 'needs_work',
  missing: ['Title'],
});

console.log('\n── Putting work on the shelf ─────────────────────────────\n');

await check(
  'a contributor may shelve their own draft',
  assertSucceeds(setDoc(doc(as(CONTRIB), 'drafts', 'd1'), draft(CONTRIB))),
);

await check(
  'a sub-admin may shelve their own draft',
  assertSucceeds(setDoc(doc(as(SUB), 'drafts', 'd2'), draft(SUB))),
);

// This is the one the lowercasing fix was for. Firebase hands back whatever
// case the address was typed in; the rules compare against the lowered form.
await check(
  'a draft filed under somebody else\'s name is refused',
  assertFails(setDoc(doc(as(CONTRIB), 'drafts', 'd3'), draft(ADMIN))),
);

await check(
  'a signed-out visitor may not shelve anything',
  assertFails(setDoc(doc(env.unauthenticatedContext().firestore(), 'drafts', 'd4'), draft(CONTRIB))),
);

// Anyone at all can sign in with a Google account. Having signed in is not
// the same as belonging here, and the shelf holds unpublished work, so a
// stranger must not be able to fill it or read it.
await check(
  'a signed-in stranger with no role cannot write to the shelf',
  assertFails(setDoc(doc(as(OUTSIDER), 'drafts', 'd5'), draft(OUTSIDER))),
);

await check(
  'a signed-in stranger cannot read the shelf either',
  assertFails(getDocs(collection(as(OUTSIDER), 'drafts'))),
);

console.log('\n── Reading the shelf ─────────────────────────────────────\n');

await check(
  'a contributor can read the whole shelf',
  assertSucceeds(getDocs(collection(as(CONTRIB), 'drafts'))),
);

await check(
  'a signed-out visitor cannot read the shelf',
  assertFails(getDocs(collection(env.unauthenticatedContext().firestore(), 'drafts'))),
);

console.log('\n── Changing and discarding ───────────────────────────────\n');

await check(
  'the author may change their own draft',
  assertSucceeds(setDoc(doc(as(CONTRIB), 'drafts', 'd1'), draft(CONTRIB), { merge: true })),
);

await check(
  'a sub-admin may change somebody else\'s draft (they publish it)',
  assertSucceeds(setDoc(doc(as(SUB), 'drafts', 'd1'), draft(CONTRIB), { merge: true })),
);

await check(
  'a contributor may not change a colleague\'s draft',
  assertFails(setDoc(doc(as(CONTRIB), 'drafts', 'd2'), draft(SUB), { merge: true })),
);

// Each of these needs a draft that actually exists and is owned by somebody
// specific. Asserting that a delete fails against a document already deleted
// passes for the wrong reason and proves nothing.
await env.withSecurityRulesDisabled(async (ctx) => {
  await setDoc(doc(ctx.firestore(), 'drafts', 'owned-by-sub'), draft(SUB));
  await setDoc(doc(ctx.firestore(), 'drafts', 'owned-by-contrib'), draft(CONTRIB));
});

await check(
  'a contributor may not discard a colleague\'s draft',
  assertFails(deleteDoc(doc(as(CONTRIB), 'drafts', 'owned-by-sub'))),
);

await check(
  'the author may discard their own draft',
  assertSucceeds(deleteDoc(doc(as(CONTRIB), 'drafts', 'owned-by-contrib'))),
);

// The shelf is cleared after a successful publish, so whoever publishes has to
// be able to delete somebody else's.
await check(
  'an admin may discard anybody\'s draft',
  assertSucceeds(deleteDoc(doc(as(ADMIN), 'drafts', 'owned-by-sub'))),
);

console.log('\n── The role model still holds ────────────────────────────\n');

await check(
  'nobody can promote themselves',
  assertFails(setDoc(doc(as(CONTRIB), 'roles', CONTRIB), { role: 'admin' })),
);

await check(
  'an admin cannot mint another admin',
  assertFails(setDoc(doc(as(ADMIN), 'roles', 'newperson@ccs.in'), { role: 'admin' })),
);

await check(
  'an admin may add a contributor',
  assertSucceeds(setDoc(doc(as(ADMIN), 'roles', 'newperson@ccs.in'), { role: 'contributor' })),
);

await check(
  'the super admin may mint an admin',
  assertSucceeds(setDoc(doc(as(SUPER), 'roles', 'another@ccs.in'), { role: 'admin' })),
);

console.log('\n── Nothing else is reachable ─────────────────────────────\n');

await check(
  'a collection the rules do not mention is closed',
  assertFails(setDoc(doc(as(SUPER), 'secrets', 'x'), { a: 1 })),
);

await env.cleanup();
console.log(failures ? `\n${failures} failed` : '\nall cases behave');
process.exit(failures ? 1 : 0);
