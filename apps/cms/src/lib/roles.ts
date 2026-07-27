/**
 * Who can do what, and the words the interface uses to explain it.
 *
 * Four levels. The wording here is the wording shown in the UI, deliberately:
 * a role model that needs a separate glossary is a role model people get
 * wrong. Each level lists what it can do in plain language, and every screen
 * that gates on a role reads its description from this file so the explanation
 * and the enforcement cannot drift apart.
 *
 * The super admin is pinned by email in the Firestore security rules, not
 * stored as data. That makes it the one role nobody can grant themselves: to
 * change it you have to change the rules, which needs the Firebase console.
 */

export const ROLES = ['super_admin', 'admin', 'sub_admin', 'contributor'] as const;
export type Role = (typeof ROLES)[number];

export interface RoleInfo {
  id: Role;
  label: string;
  /** One line, shown beside the name. */
  summary: string;
  /** What this person can do, in the interface's own words. */
  can: string[];
  /** What they cannot, said plainly so nobody has to infer it. */
  cannot: string[];
}

export const ROLE_INFO: Record<Role, RoleInfo> = {
  super_admin: {
    id: 'super_admin',
    label: 'Super admin',
    summary: 'Runs the system. Only one person, set in the security rules.',
    can: [
      'Everything an admin can do',
      'Add and remove admins',
      'Remove anyone, including other admins',
    ],
    cannot: [
      'Be removed from inside this interface. Changing who holds this role means editing the Firebase security rules.',
    ],
  },
  admin: {
    id: 'admin',
    label: 'Admin',
    summary: 'Full control of the archive and of who else can edit it.',
    can: [
      'Create, edit and publish any kind of content',
      'Upload documents and replace files',
      'Add and remove sub-admins and contributors',
      'Publish work that a contributor has drafted',
    ],
    cannot: ['Add or remove other admins. Ask the super admin for that.'],
  },
  sub_admin: {
    id: 'sub_admin',
    label: 'Sub-admin',
    summary: 'Edits and publishes content. Does not manage people.',
    can: [
      'Create, edit and publish any kind of content',
      'Upload documents and replace files',
      'Publish work that a contributor has drafted',
    ],
    cannot: ['Add or remove anyone.'],
  },
  contributor: {
    id: 'contributor',
    label: 'Contributor',
    summary: 'Prepares work for someone else to publish.',
    can: [
      'Create and edit drafts of any kind of content',
      'Upload documents',
      'See everything in the archive',
    ],
    cannot: [
      'Publish. A sub-admin or admin reviews the draft and publishes it.',
      'Add or remove anyone.',
    ],
  },
};

/** Ordered most powerful first, for menus and tables. */
export const ROLE_ORDER: Role[] = ['super_admin', 'admin', 'sub_admin', 'contributor'];

const RANK: Record<Role, number> = {
  super_admin: 4,
  admin: 3,
  sub_admin: 2,
  contributor: 1,
};

export function atLeast(role: Role | null | undefined, minimum: Role): boolean {
  if (!role) return false;
  return RANK[role] >= RANK[minimum];
}

/** Publishing writes to the repository, so it is the line that matters most. */
export function canPublish(role: Role | null | undefined): boolean {
  return atLeast(role, 'sub_admin');
}

export function canManagePeople(role: Role | null | undefined): boolean {
  return atLeast(role, 'admin');
}

/**
 * Which roles a given person is allowed to hand out. An admin can build a team
 * but cannot mint another admin, which keeps the blast radius of one
 * compromised admin account smaller than the whole system.
 */
export function assignableBy(role: Role | null | undefined): Role[] {
  if (role === 'super_admin') return ['admin', 'sub_admin', 'contributor'];
  if (role === 'admin') return ['sub_admin', 'contributor'];
  return [];
}
