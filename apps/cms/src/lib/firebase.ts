/**
 * Firebase in the browser: sign in, know who you are, know what you may do.
 *
 * Two ways in, both passwordless. Google for people who have a Google account
 * on the address they were invited at, and an emailed link for everyone else.
 * No passwords to choose, forget, reuse or reset.
 *
 * The config below is public on purpose. A Firebase web key identifies the
 * project, it does not authorise anything: access is decided by the security
 * rules in firestore.rules and by the authorised-domains list in the console.
 */

import { initializeApp, getApps, type FirebaseApp } from 'firebase/app';
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  sendSignInLinkToEmail,
  isSignInWithEmailLink,
  signInWithEmailLink,
  signOut as fbSignOut,
  onAuthStateChanged,
  type User,
} from 'firebase/auth';
import { getFirestore, doc, getDoc, setDoc, deleteDoc, collection, getDocs } from 'firebase/firestore';
import { ROLE_INFO, type Role } from './roles';

export const firebaseConfig = {
  apiKey: 'AIzaSyCmpq8H0izj4JDQWvYltSSn4-sXpBPZnIs',
  authDomain: 'thothica-cms-for-ccs.firebaseapp.com',
  projectId: 'thothica-cms-for-ccs',
  storageBucket: 'thothica-cms-for-ccs.firebasestorage.app',
  messagingSenderId: '306746214193',
  appId: '1:306746214193:web:a8bfe113f4ac994aaa5210',
  measurementId: 'G-7RFHXDSQBG',
};

export const SUPER_ADMIN_EMAIL = 'adnan@thothica.com';

let app: FirebaseApp | undefined;
export function firebase(): FirebaseApp {
  if (!app) app = getApps()[0] ?? initializeApp(firebaseConfig);
  return app;
}

export const auth = () => getAuth(firebase());
export const db = () => getFirestore(firebase());

const EMAIL_KEY = 'thothica-cms:pending-email';

export async function signInWithGoogle(): Promise<User> {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: 'select_account' });
  const result = await signInWithPopup(auth(), provider);
  return result.user;
}

/**
 * Send a sign-in link. The address is remembered locally because Firebase
 * needs it again when the link is opened, and asking twice is the sort of
 * friction that makes people give up on an emailed login.
 */
export async function sendMagicLink(email: string): Promise<void> {
  const address = email.trim().toLowerCase();
  await sendSignInLinkToEmail(auth(), address, {
    url: `${window.location.origin}/finish-signin`,
    handleCodeInApp: true,
  });
  window.localStorage.setItem(EMAIL_KEY, address);
}

export function isMagicLink(url: string = window.location.href): boolean {
  return isSignInWithEmailLink(auth(), url);
}

export async function completeMagicLink(promptForEmail?: () => string | null): Promise<User> {
  let address = window.localStorage.getItem(EMAIL_KEY);
  if (!address && promptForEmail) address = promptForEmail();
  if (!address) throw new Error('This link needs the address it was sent to.');
  const result = await signInWithEmailLink(auth(), address, window.location.href);
  window.localStorage.removeItem(EMAIL_KEY);
  return result.user;
}

export const signOut = () => fbSignOut(auth());

export function watchUser(cb: (user: User | null) => void) {
  return onAuthStateChanged(auth(), cb);
}

// ── Roles ────────────────────────────────────────────────────────────────

export interface Person {
  email: string;
  role: Role;
  name?: string;
  addedBy?: string;
  addedAt?: string;
}

/**
 * The signed-in person's role. The super admin is decided by address rather
 * than by a stored document, matching the security rules exactly: if the two
 * ever disagreed, the interface would offer buttons the database refuses.
 */
export async function roleFor(user: User | null): Promise<Role | null> {
  if (!user?.email) return null;
  const address = user.email.toLowerCase();
  if (address === SUPER_ADMIN_EMAIL) return 'super_admin';
  const snapshot = await getDoc(doc(db(), 'roles', address));
  const role = snapshot.exists() ? (snapshot.data().role as Role) : null;
  return role && role in ROLE_INFO ? role : null;
}

export async function listPeople(): Promise<Person[]> {
  const snapshot = await getDocs(collection(db(), 'roles'));
  const people = snapshot.docs.map((d) => ({ email: d.id, ...(d.data() as Omit<Person, 'email'>) }));
  return people.sort((a, b) => a.email.localeCompare(b.email));
}

export async function setRole(email: string, role: Role, actor: string): Promise<void> {
  const address = email.trim().toLowerCase();
  await setDoc(doc(db(), 'roles', address), {
    role,
    addedBy: actor,
    addedAt: new Date().toISOString(),
  });
}

export async function removePerson(email: string): Promise<void> {
  await deleteDoc(doc(db(), 'roles', email.trim().toLowerCase()));
}
