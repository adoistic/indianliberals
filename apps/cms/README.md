# Thothica CMS

The editing interface for the Indian Liberals archive, at `cms.indianliberals.in`.

Built for people who have never used a CMS. Editors sign in with Google or an
emailed link, never touch GitHub, and never see YAML unless they ask to.

## How it fits together

```
editor's browser ──► Cloudflare Pages (Astro SSR)
                      │
                      ├─ Firebase Auth      who they are
                      ├─ Firestore          what they may do
                      ├─ R2 (ARCHIVE)       where documents go
                      └─ GitHub App         where content is committed
                                              │
                                              └─► the site rebuilds
```

Content stays in git. That was a deliberate choice: 2,707 markdown files is
nothing for a repository, and the history is what makes a bad edit recoverable.
The CMS is a friendly surface over the GitHub contents API, not a replacement
for it.

## Credentials

One secret, and only one:

| Secret | What it is |
|---|---|
| `GITHUB_APP_ID` | the Thothica CMS app |
| `GITHUB_APP_INSTALLATION_ID` | its installation on adoistic/indianliberals |
| `GITHUB_APP_PRIVATE_KEY` | the PEM it signs with |

There is **no Firebase service account**. The Worker verifies each sign-in
against Google's public certificates and reads roles from Firestore as the user
themselves, so the security rules do the enforcing. One fewer key to leak.

### Setting up the GitHub App

```bash
node scripts/create-github-app.mjs      # opens a browser, one click
# install it on the repo when prompted, then
node scripts/finish-github-app.mjs --set
```

The first script uses GitHub's app manifest flow, so every setting is
pre-filled and the private key comes back over the API rather than being copied
out of a browser.

## Roles

Four levels, defined once in `src/lib/roles.ts` and explained to editors on the
People page using the same words. Super admin is pinned by email in
`firestore.rules`, which is why nobody can grant it to themselves.

| Role | Content | People |
|---|---|---|
| Super admin | everything | everyone, including admins |
| Admin | everything | sub-admins and contributors |
| Sub-admin | create, edit, publish | nobody |
| Contributor | drafts only | nobody |

## Three ways to add something

All three produce the same validated file. The AI paths are a convenience, not
a separate class of record.

1. **Copy a prompt.** The CMS writes the prompt, the editor pastes it into
   whatever AI they already use, then pastes the reply back. Costs nothing.
2. **Bring your own key.** Anthropic or OpenRouter. The key is kept in the
   editor's browser and the request goes straight to the provider, so the bill
   and the document are both theirs. Never sent to us.
3. **Type it in.** Every field, with a hint explaining what belongs there.

## Pop-up notices

`/popups` lists every notice and says which one readers are meeting right now;
"Make a pop-up notice" opens the ordinary entry form with the upload and AI
steps skipped, because a notice is a poster, a sentence and a date.

They are ordinary content files, under `apps/site/src/content/announcements/`,
and the site shows whichever one is live on every page. Two clocks decide that
(`apps/site/src/lib/announcements.ts`): the build leaves out anything finished,
held back or not yet due, and the reader's own browser hides the notice the
moment `ends` passes, so a lecture notice comes down at six on the evening of
the lecture without anybody rebuilding the site. Times are typed plainly,
`2026-09-18T18:00`, and read as Indian Standard Time.

Readers can close a notice, and their browser remembers that against the
notice's `id` for 48 hours, after which a notice that is still running comes
back once. Closing therefore means closed, without meaning lost: somebody who
waves a lecture away on Monday can still be reminded on Wednesday. Renaming a
live notice shows it again to everyone, since the memory is keyed on the id.

## Deploying

```bash
npm run build          # lints for em dashes, then builds
npm run deploy
```

Firestore rules live in `firestore.rules` and deploy separately:

```bash
firebase deploy --only firestore:rules --project thothica-cms-for-ccs
```

## Console settings this depends on

In the Firebase console for `thothica-cms-for-ccs`:

- Authentication, sign-in method: Google enabled
- Authentication, sign-in method: Email link enabled
- Authentication, authorised domains: `cms.indianliberals.in` and `localhost`
- Firestore: created, with the rules in this directory deployed
