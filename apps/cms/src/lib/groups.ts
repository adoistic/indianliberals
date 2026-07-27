/**
 * What the drawers of a form are called.
 *
 * Both screens fold the same fields into the same six groups, so both screens
 * had better call them the same thing. Somebody who files a pamphlet under
 * "Publication details" on Monday and comes back on Tuesday to correct the
 * publisher should find that drawer where they left it, with the name they
 * remember. This is the one table; neither page keeps its own.
 */

import type { Field } from './collections';

export type GroupId = Field['group'];

export interface GroupInfo {
  id: GroupId;
  /** The name on the drawer. */
  label: string;
  /** A line under it saying what belongs inside. Empty for the open section. */
  note: string;
}

/** In the order the form presents them, essentials first. */
export const GROUPS: GroupInfo[] = [
  {
    id: 'essential',
    label: 'The details that matter',
    note: '',
  },
  {
    id: 'publication',
    label: 'Publication details',
    note: 'Who printed it, where, when, and how long it is.',
  },
  {
    id: 'people',
    label: 'People and contents',
    note: 'Everyone involved, and everything inside it.',
  },
  {
    id: 'classification',
    label: 'Subjects and filing',
    note: 'The tags that decide where this turns up on the site.',
  },
  {
    id: 'files',
    label: 'Files, pictures and rights',
    note: 'The scan, its pictures, and what the archive may do with it.',
  },
  {
    id: 'advanced',
    label: 'Machine records and settings',
    note: 'Written by the extraction scripts. There is rarely a reason to change any of it.',
  },
];

export const GROUP_ORDER: GroupId[] = GROUPS.map((group) => group.id);

const BY_ID = new Map(GROUPS.map((group) => [group.id, group]));

export function groupLabel(id: GroupId): string {
  return BY_ID.get(id)?.label ?? id;
}

export function groupNote(id: GroupId): string {
  return BY_ID.get(id)?.note ?? '';
}
