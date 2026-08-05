/**
 * The first page of a PDF, as a cover picture.
 *
 * Every listing page on the site shows works as a shelf of covers, and the
 * cover of a scanned document is simply its first page. This renders that
 * page in the browser with pdf.js, so the capture costs nothing, needs no
 * server, and happens the moment a document is uploaded rather than in some
 * later pipeline run. The editor can always drop a different picture on the
 * cover field afterwards; this is the default, not the law.
 */

import * as pdfjs from 'pdfjs-dist';

// The worker ships inside the package; Vite turns this URL into a bundled
// asset. Without a worker pdf.js falls back to the main thread and a large
// scan freezes the tab.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

/** How wide the rendered cover is, in pixels. Matches the archive's covers. */
const COVER_WIDTH = 720;

export interface CapturedCover {
  blob: Blob;
  /** jpg when the browser cannot encode webp (older Safari), webp otherwise. */
  ext: 'webp' | 'jpg';
}

/**
 * Render page one of a PDF (a File from the editor's machine, or a URL on
 * the archive server) to an image blob.
 */
export async function captureFirstPage(source: File | string): Promise<CapturedCover> {
  const data =
    typeof source === 'string'
      ? await (await fetch(source)).arrayBuffer()
      : await source.arrayBuffer();

  const pdf = await pdfjs.getDocument({ data }).promise;
  try {
    const page = await pdf.getPage(1);
    const base = page.getViewport({ scale: 1 });
    const viewport = page.getViewport({ scale: COVER_WIDTH / base.width });

    const canvas = document.createElement('canvas');
    canvas.width = Math.round(viewport.width);
    canvas.height = Math.round(viewport.height);
    const context = canvas.getContext('2d');
    if (!context) throw new Error('This browser would not give us a drawing surface.');

    // Scanned pages are often transparent where the paper should be.
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, canvas.width, canvas.height);

    await page.render({ canvasContext: context, viewport }).promise;

    const webp = await toBlob(canvas, 'image/webp', 0.82);
    if (webp && webp.type === 'image/webp') return { blob: webp, ext: 'webp' };
    const jpg = await toBlob(canvas, 'image/jpeg', 0.85);
    if (jpg) return { blob: jpg, ext: 'jpg' };
    throw new Error('The page rendered but could not be saved as a picture.');
  } finally {
    void pdf.destroy();
  }
}

function toBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}
