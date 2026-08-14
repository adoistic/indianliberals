/**
 * Moving an entry from one section to another, and retiring one.
 *
 * Until now the CMS could only write. There was no delete, no rename and no
 * move, so an editor who found a piece filed in the wrong section could create
 * a copy in the right one and then had no way to remove the original: the best
 * they could do was tick "Keep as a draft" and leave a ghost behind. CCS hit
 * exactly this in round 4, asking "whether content can be moved from one
 * section to another. For instance, several pieces currently under Musings are
 * actually Opinion Pieces and should be shifted there." Twelve of them were.
 *
 * Two rules shape what follows.
 *
 * A move is one commit. The new file is written and the old one deleted
 * together, so the entry is never in two sections at once and never in none.
 *
 * A move leaves a forwarding address. The old URL goes into public/_redirects
 * as a 301, because an archive whose links rot is worth less than one that
 * grows slowly. Nothing that was ever published stops resolving.
 */

import type { CollectionDef } from './collections';

/**
 * Fields that mean the same thing under a different name in another section.
 *
 * The one that matters is the byline. A musing's `author` points at the
 * thinkers collection, so on a piece ABOUT a dead thinker it holds the subject,
 * not the writer. An opinion keeps those apart: `subject` is who it is about,
 * `author` is the contributor who wrote it, and `author_name` is what gets
 * printed. Carrying `author` across unchanged is what credited twelve essays to
 * the people they were about.
 */
const RENAMES: Record<string, Record<string, string>> = {
  'musings->opinions': { author: 'subject' },
  'opinions->musings': { subject: 'author' },
};

export interface MovePlan {
  /** Frontmatter for the new file, already filtered to the target's fields. */
  data: Record<string, unknown>;
  /** Fields that could not travel, so the editor is told rather than surprised. */
  dropped: string[];
  /** Required target fields with nothing to fill them: the move needs these. */
  missing: string[];
}

const topLevel = (name: string) => name.split('.')[0];

/**
 * Work out what the entry looks like in its new section.
 *
 * Anything the target collection has no field for is dropped and named. Nothing
 * is invented: a required field with no source stays empty and is reported, so
 * the editor supplies it before the move rather than discovering a broken entry
 * afterwards.
 */
export function planMove(
  data: Record<string, unknown>,
  from: CollectionDef,
  to: CollectionDef,
): MovePlan {
  const renames = RENAMES[`${from.id}->${to.id}`] ?? {};
  const targetFields = new Set(to.fields.map((field) => topLevel(field.name)));

  const out: Record<string, unknown> = {};
  const dropped: string[] = [];

  for (const [key, value] of Object.entries(data)) {
    if (value === undefined || value === null) continue;
    const renamed = renames[key];
    if (renamed && targetFields.has(topLevel(renamed))) {
      out[renamed] = value;
      continue;
    }
    if (targetFields.has(key)) {
      out[key] = value;
      continue;
    }
    // `id` is the file name and always travels, whatever the field list says.
    if (key === 'id') {
      out[key] = value;
      continue;
    }
    dropped.push(key);
  }

  const missing = to.fields
    .filter((field) => field.required && !field.name.includes('.'))
    .filter((field) => {
      const held = out[field.name];
      return held === undefined || held === '' || (Array.isArray(held) && held.length === 0);
    })
    .map((field) => field.label);

  return { data: out, dropped, missing };
}

/**
 * The line that keeps the old address working.
 *
 * Cloudflare Pages reads public/_redirects top to bottom, so appending is
 * enough; a later rule never shadows an earlier one for a different path.
 */
export function redirectLine(fromPath: string, toPath: string): string {
  return `${fromPath}   ${toPath}   301`;
}

export function entryPath(collection: string, slug: string): string {
  return `/${collection}/${slug}/`;
}

/**
 * Add a redirect to the file, unless the same source path is already handled.
 * Re-running a move must not stack duplicate rules.
 */
export function withRedirect(redirects: string, fromPath: string, toPath: string, note: string): string {
  if (new RegExp(`^${fromPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s`, 'm').test(redirects)) {
    return redirects;
  }
  const block = `\n# ${note}\n${redirectLine(fromPath, toPath)}\n`;
  return redirects.replace(/\s*$/, '\n') + block;
}
