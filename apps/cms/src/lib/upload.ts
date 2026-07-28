/**
 * Getting a file into the archive bucket, from the browser.
 *
 * Shared by the single-document screen and the batch screen. They upload the
 * same way for the same reason: the file goes to R2 first, before anything is
 * read or extracted or catalogued, so that whatever happens next the document
 * itself is safe and has a permanent address.
 */

export interface UploadDone {
  ok: boolean;
  url?: string;
  key?: string;
  /** A file of that name is already there and we did not say to replace it. */
  clash?: boolean;
  error?: string;
}

/**
 * Send one file, reporting progress.
 *
 * XMLHttpRequest rather than fetch, because it is still the only way to know
 * how far a 100 MB scan has got, and a bar that does not move is
 * indistinguishable from a hang.
 */
export function sendFile(
  file: File,
  kind: string,
  token: string,
  onProgress: (pct: number) => void,
  overwrite = false,
): Promise<UploadDone> {
  return new Promise((resolve) => {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', kind);
    if (overwrite) form.append('overwrite', 'yes');

    const request = new XMLHttpRequest();
    request.open('POST', '/api/upload');
    // Callers hold a Firebase token; some have already put "Bearer " in front
    // of it and some have not. Getting this wrong fails as "sign in first",
    // which sends you looking in entirely the wrong place.
    request.setRequestHeader(
      'Authorization',
      token.startsWith('Bearer ') ? token : `Bearer ${token}`,
    );

    request.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    });

    request.addEventListener('load', () => {
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(request.responseText) as Record<string, unknown>;
      } catch {
        resolve({ ok: false, error: 'The server said something we could not read.' });
        return;
      }
      if (request.status === 409 && data.needsConfirmation) {
        resolve({ ok: false, clash: true, error: String(data.error ?? '') });
        return;
      }
      if (request.status >= 400) {
        resolve({
          ok: false,
          error: String(data.error ?? `The upload failed with code ${request.status}.`),
        });
        return;
      }
      resolve({ ok: true, url: String(data.url ?? ''), key: String(data.key ?? '') });
    });

    request.addEventListener('error', () => {
      resolve({
        ok: false,
        error: 'The upload could not reach the server. Check the connection and try again.',
      });
    });

    request.send(form);
  });
}

/** The bytes of a file as base64, which is how the model APIs want a PDF. */
export function asBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      const parts = String(reader.result).split(',');
      resolve(parts[1] ?? '');
    });
    reader.addEventListener('error', () => reject(new Error('That file could not be read.')));
    reader.readAsDataURL(file);
  });
}

/** PDFs are documents; everything else we accept is a cover image. */
export function kindOf(file: File): string {
  return file.type === 'application/pdf' ? 'pdf' : 'cover';
}
