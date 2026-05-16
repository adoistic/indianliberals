/**
 * SUPER-ADMINS — hardcoded in source code.
 *
 * THIS FILE IS THE ROOT OF TRUST for CMS authentication.
 *
 * People listed here can:
 *   - Add or remove sub-admins (via the Sveltia CMS interface to data/admins.json)
 *   - Edit any content
 *   - Cannot be removed except by editing this file and redeploying the Worker
 *
 * Editing this file:
 *   1. Open a pull request modifying this array
 *   2. PR must be approved per CODEOWNERS (currently requires existing super-admin)
 *   3. After merge to main, redeploy the Worker: `cd apps/auth && bun run deploy`
 *      (deploy requires Cloudflare account access — separate gate)
 *
 * The two gates (PR review + Cloudflare deploy access) mean no single
 * person can add themselves as a super-admin without leaving a paper trail.
 *
 * Emails must match the user's GitHub primary email exactly (case-insensitive).
 * To find what GitHub considers your primary email:
 *   curl -H "Authorization: token <PAT>" https://api.github.com/user/emails
 */
export const SUPER_ADMINS: ReadonlyArray<string> = Object.freeze([
  "appsadoistic@gmail.com",
  "eacademy@ccs.in",
]);

/**
 * Compare an email against the SUPER_ADMINS list, case- and whitespace-insensitive.
 */
export function isSuperAdmin(email: string | null | undefined): boolean {
  if (!email) return false;
  const needle = email.trim().toLowerCase();
  return SUPER_ADMINS.some((sa) => sa.toLowerCase() === needle);
}
