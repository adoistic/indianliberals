// Test Critical Gap T20 fix: isAdminEdited must be conservative.
// An ambiguous last-commit (no email) is treated as admin-edited (fail closed),
// because the cost of overwriting a real edit is much higher than the cost
// of one missed cron update.

import { describe, it, expect } from 'vitest';
import { isAdminEdited } from '../src/github';

const BOT_EMAIL = 'theprint-ingest@indianliberals.in';

describe('isAdminEdited (T20 guard)', () => {
  it('returns false when there is no commit history (file is new)', () => {
    expect(isAdminEdited(null, BOT_EMAIL)).toBe(false);
  });

  it('returns false when the last commit is by the bot (case-insensitive)', () => {
    expect(isAdminEdited({ email: 'theprint-ingest@indianliberals.in' }, BOT_EMAIL)).toBe(false);
    expect(isAdminEdited({ email: 'ThePrint-Ingest@IndianLiberals.IN' }, BOT_EMAIL)).toBe(false);
  });

  it('returns true when the last commit is by a human admin', () => {
    expect(isAdminEdited({ email: 'arjun@ccs.in', login: 'arjun-ccs' }, BOT_EMAIL)).toBe(true);
    expect(isAdminEdited({ email: 'adnan@thothica.com' }, BOT_EMAIL)).toBe(true);
  });

  it('fails CLOSED when the last commit author email is missing', () => {
    // Unknown author → assume admin-edited rather than risk overwriting.
    expect(isAdminEdited({ name: 'someone' }, BOT_EMAIL)).toBe(true);
  });
});
