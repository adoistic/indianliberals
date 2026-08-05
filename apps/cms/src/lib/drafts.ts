/**
 * The shelf: work that is started but not finished.
 *
 * Two things put an entry here. Somebody begins a document, hits a question
 * they cannot answer, such as who wrote it or what year, and puts it down; or
 * drops fifty scans at once and the machine reads them one after another. Both
 * end in the same place, because they are the same thing: an entry that exists
 * but is not ready for readers.
 *
 * Drafts live in Firestore rather than the repository for one concrete reason.
 * The site takes about twenty-five minutes to build and Cloudflare builds one
 * at a time, so a draft that committed on every save would spend the archive's
 * whole build capacity on work nobody can read yet. Nothing here is public,
 * nothing here triggers a build, and the commit happens once, at the end, when
 * a person says it is ready.
 *
 * The PDF is never in here. It goes to R2 the moment it is chosen, so a draft
 * holds a URL and the file itself is safe even if everything downstream fails.
 *
 * Access is decided entirely by firestore.rules: a person may read the shelf,
 * write their own drafts, and publish only if their role allows it. This module
 * holds no permission logic of its own, because a rule in a client file is a
 * suggestion.
 */

import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  serverTimestamp,
  setDoc,
  updateDoc,
} from 'firebase/firestore';
import { db } from './firebase';

export type DraftStatus = 'needs_work' | 'ready';

export interface Draft {
  id: string;
  /** Which kind of entry this will become. */
  collection: string;
  /** The filename it will take. May be empty on a very early draft. */
  slug: string;
  /** Frontmatter, as an object, exactly as the form holds it. */
  data: Record<string, unknown>;
  /** The markdown body below the frontmatter. */
  body: string;
  /** Whose it is. The rules key off this, so it is not decorative. */
  author: string;
  status: DraftStatus;
  /** What still has to be filled in before it can be published. */
  missing: string[];
  /** Set when the draft came from a batch, so the shelf can group them. */
  batchId?: string | null;
  /** The original filename, which is often the only clue to what a scan is. */
  filename?: string | null;
  /** Already in R2. Present even when extraction failed. */
  pdfUrl?: string | null;
  /** Why the machine could not read it, when that is what happened. */
  error?: string | null;
  /**
   * Pictures dropped on the form, waiting in the bucket's staging area.
   * Keyed by field path; each holds where the picture will be committed
   * and where it sits meanwhile, so reopening the draft finds them again.
   */
  stagedImages?: Record<
    string,
    { repoPath: string; stagingKey: string; url: string }
  > | null;
  createdAt?: unknown;
  updatedAt?: unknown;
}

/** What a caller supplies. Everything else is filled in here. */
export type DraftInput = Omit<Draft, 'id' | 'createdAt' | 'updatedAt'>;

const shelf = () => collection(db(), 'drafts');

/**
 * Ids are made here rather than by Firestore so that a batch can name its
 * drafts before it writes them, and a retry overwrites the same document
 * instead of leaving a second copy behind.
 */
export function draftId(batchId: string | null, filename: string): string {
  const stem = filename
    .toLowerCase()
    .replace(/\.[a-z0-9]+$/, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  return batchId ? `${batchId}--${stem || 'document'}` : `${stem || 'document'}-${stamp()}`;
}

/** A short, sortable, collision-resistant suffix. */
function stamp(): string {
  return `${Date.now().toString(36)}${Math.floor(Math.random() * 1296).toString(36).padStart(2, '0')}`;
}

export function newBatchId(): string {
  return `b${stamp()}`;
}

export async function saveDraft(id: string, input: DraftInput): Promise<void> {
  const existing = await getDoc(doc(shelf(), id));
  await setDoc(
    doc(shelf(), id),
    {
      ...input,
      batchId: input.batchId ?? null,
      filename: input.filename ?? null,
      pdfUrl: input.pdfUrl ?? null,
      error: input.error ?? null,
      stagedImages: input.stagedImages ?? null,
      ...(existing.exists() ? {} : { createdAt: serverTimestamp() }),
      updatedAt: serverTimestamp(),
    },
    { merge: true },
  );
}

export async function getDraft(id: string): Promise<Draft | null> {
  const snapshot = await getDoc(doc(shelf(), id));
  return snapshot.exists() ? ({ id: snapshot.id, ...(snapshot.data() as Omit<Draft, 'id'>) }) : null;
}

export async function deleteDraft(id: string): Promise<void> {
  await deleteDoc(doc(shelf(), id));
}

export async function markStatus(id: string, status: DraftStatus): Promise<void> {
  await updateDoc(doc(shelf(), id), { status, updatedAt: serverTimestamp() });
}

/**
 * Everything on the shelf, newest first.
 *
 * Read whole rather than queried. The shelf is work in progress for a team of
 * a handful of people; if it ever holds enough to need pagination, something
 * has gone wrong that pagination would only hide.
 */
export async function listDrafts(): Promise<Draft[]> {
  const snapshot = await getDocs(shelf());
  const drafts = snapshot.docs.map((d) => ({ id: d.id, ...(d.data() as Omit<Draft, 'id'>) }));
  return drafts.sort((a, b) => millis(b.updatedAt) - millis(a.updatedAt));
}

function millis(value: unknown): number {
  if (value && typeof value === 'object' && 'toMillis' in value) {
    return (value as { toMillis(): number }).toMillis();
  }
  return 0;
}

/** Drafts grouped into the batches they arrived in, loose ones under null. */
export function byBatch(drafts: Draft[]): Map<string | null, Draft[]> {
  const groups = new Map<string | null, Draft[]>();
  for (const draft of drafts) {
    const key = draft.batchId ?? null;
    const group = groups.get(key);
    if (group) group.push(draft);
    else groups.set(key, [draft]);
  }
  return groups;
}
