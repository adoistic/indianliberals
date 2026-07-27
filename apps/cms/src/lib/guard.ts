/**
 * The gate every API route goes through.
 *
 * Two questions, in order: is this really the person they claim to be, and are
 * they allowed to do this. The first is answered by verifying the Firebase
 * token signature. The second by reading their role from Firestore, server
 * side, using their own token. We never trust a role the browser sends us,
 * because a browser can send anything.
 */

import { verifyIdToken, type Claims } from './verify';
import type { Role } from './roles';
import { atLeast } from './roles';

export interface Env {
  FIREBASE_PROJECT_ID: string;
  SUPER_ADMIN_EMAIL: string;
  [key: string]: unknown;
}

export interface Actor extends Claims {
  role: Role;
}

export class Refused extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/**
 * Read one document from Firestore over REST, as the signed-in user. The
 * security rules apply exactly as they would in the browser, so a user who
 * cannot read a role document here could not read it there either.
 */
async function roleFromFirestore(
  projectId: string,
  email: string,
  idToken: string,
): Promise<Role | null> {
  const url =
    `https://firestore.googleapis.com/v1/projects/${projectId}` +
    `/databases/(default)/documents/roles/${encodeURIComponent(email)}`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${idToken}` } });
  if (response.status === 404) return null;
  if (!response.ok) throw new Refused(502, 'could not read your role');
  const data = (await response.json()) as { fields?: { role?: { stringValue?: string } } };
  return (data.fields?.role?.stringValue as Role) ?? null;
}

/** Verify the caller and resolve their role, or throw a Refused. */
export async function actorFrom(request: Request, env: Env): Promise<Actor> {
  const header = request.headers.get('Authorization') ?? '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : '';
  if (!token) throw new Refused(401, 'sign in first');

  let claims: Claims;
  try {
    claims = await verifyIdToken(token, env.FIREBASE_PROJECT_ID);
  } catch (error) {
    throw new Refused(401, `your session is not valid: ${(error as Error).message}`);
  }
  if (!claims.email) throw new Refused(401, 'that account has no email address');

  const superAdmin = env.SUPER_ADMIN_EMAIL.toLowerCase();
  const role =
    claims.email === superAdmin
      ? ('super_admin' as Role)
      : await roleFromFirestore(env.FIREBASE_PROJECT_ID, claims.email, token);

  if (!role) throw new Refused(403, 'your account has no role yet, so there is nothing to edit');
  return { ...claims, role };
}

export async function requireRole(request: Request, env: Env, minimum: Role): Promise<Actor> {
  const actor = await actorFrom(request, env);
  if (!atLeast(actor.role, minimum)) {
    throw new Refused(403, `this needs the ${minimum.replace('_', ' ')} level or above`);
  }
  return actor;
}

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });

/** Turn a thrown Refused into an honest response, and anything else into a 500. */
export function refuse(error: unknown): Response {
  if (error instanceof Refused) return json({ error: error.message }, error.status);
  return json({ error: `something went wrong: ${(error as Error).message}` }, 500);
}
