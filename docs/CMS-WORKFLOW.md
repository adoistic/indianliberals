# How the CMS works — for CCS editorial staff

Plain-language guide to editing indianliberals.in via the Sveltia CMS.

## Who can edit

Two tiers. You don't need to memorise the difference — it just affects who can add or remove editors.

**Super-admins**
- Adnan (`appsadoistic@gmail.com`)
- CCS Editorial Academy account (`eacademy@ccs.in`)
- Anyone else added in code by editing `apps/auth/src/super-admins.ts` and redeploying.

Super-admins can do everything a regular editor can do, *plus* add and remove sub-admins via the CMS.

**Sub-admins (regular editors)**
- The CCS staff who actually update content on the site.
- Added and removed by super-admins.
- Cannot promote themselves; cannot remove super-admins.

If you're reading this, you're probably a sub-admin. Welcome.

## How to log in

1. Open <https://indianliberals.in/admin/>
2. Click **Sign in with GitHub**.
3. A popup will ask you to authorise the "Indian Liberals CMS" GitHub app.
4. If your GitHub primary email is in the allowlist, you'll land in the CMS dashboard.
5. If not, you'll see an "Access denied" page with your email shown. Ask a super-admin to add you.

**Important:** the system checks your *GitHub primary verified email*, not whatever email you typed somewhere else. If your CCS work email is `you@ccs.in` but your GitHub account uses `you@gmail.com`, only the GitHub one counts.

To check what GitHub thinks your primary email is: open <https://github.com/settings/emails> and look for the address tagged "Primary".

## How to add a new editor (super-admins only)

1. In the CMS sidebar, scroll to **Sub-admins**.
2. Click the existing entry to edit, or **+ New** to add.
3. Add their GitHub primary email to the list.
4. Click **Publish**.
5. Within 60 seconds, the new editor can log in.

That's it. No code change, no deploys, no asking Thothica.

## How to remove an editor (super-admins only)

Same place. Open Sub-admins, remove the line, Publish. They lose access on the next refresh.

## What sub-admins can and cannot edit

**Can edit:**
- All eight content kinds (Thinkers, Primary works, Periodicals, Musings, Opinions, Interviews, Organisations, ThePrint mirror)
- All languages
- Media uploads

**Cannot edit (rejected by GitHub if attempted):**
- The sub-admin list itself (`data/admins.json`) — only super-admins
- The super-admin list itself (`apps/auth/src/super-admins.ts`) — code change + deploy
- The CMS config (`apps/site/public/admin/config.yml`) — code change
- Branch protection, CODEOWNERS, infrastructure files

If you try to edit something you're not allowed to, the CMS will let you make the change in the editor, but the save will fail with a "permission denied" message from GitHub. Nothing breaks; you just can't save it.

## Why this design

The repo is public. Anyone with a GitHub account can attempt to log in. The auth proxy is the only thing keeping unauthorised people out.

We make the allowlist visible (in `data/admins.json`) because transparency is the right default for a project about classical liberalism. If you don't want your email visible there, use a GitHub-specific email address with email privacy enabled.

The two-tier model exists so:
- One person can't lock everyone else out (you need to edit code AND deploy to change the super-admin list)
- No editor can secretly promote themselves (only super-admins can edit `data/admins.json`)
- Removing a malicious editor is a 30-second job for any super-admin

## If something breaks

- "Access denied" but you should have access → ask a super-admin to verify your email is in `data/admins.json` and that it matches your GitHub primary email exactly
- CMS shows an error after save → check the GitHub Pull Requests page; the change may have been blocked by branch protection
- Site shows old content after editing → Cloudflare Pages deploys take 1-2 minutes; refresh after a moment
- Worse than that → contact Adnan at appsadoistic@gmail.com
