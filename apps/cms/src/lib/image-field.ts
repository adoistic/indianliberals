/**
 * The picture field: drop an image, see it, done.
 *
 * Nobody should type a path or paste a URL to put a picture on a page. This
 * widget shows what is there now, accepts a drop or a chosen file, and works
 * out where the picture belongs from the field's own definition:
 *
 *   - r2 fields (work covers) upload to the archive bucket at once and the
 *     field holds the returned address, exactly as covers always have.
 *   - repo fields (portraits, logos, hero images) upload to a staging area
 *     in the bucket, the field holds the site path it will live at, and the
 *     save commits the picture beside the entry, one commit, one build.
 *
 * The same widget serves the add form and the edit form, which build their
 * pages differently; both hand it a place in the DOM and callbacks for
 * reading and writing the field.
 */

import type { Field } from './collections';
import { sendFile } from './upload';
import { captureFirstPage } from './pdf-cover';

/** A picture waiting in staging for the save to commit it. */
export interface StagedImage {
  /** Where in the repository the save will write it. */
  repoPath: string;
  /** Where it waits in the bucket meanwhile. */
  stagingKey: string;
  /** A viewable address for the preview. */
  url: string;
}

export interface ImageFieldOptions {
  field: Field;
  /** The field's dotted path, used as the key in the staged map. */
  path: string;
  value: () => string;
  setValue: (value: string) => void;
  /** The entry's slug, for naming the file. May be empty early on. */
  slug: () => string;
  /** The entry's PDF address, when there is one, for cover capture. */
  pdfUrl?: () => string;
  token: () => Promise<string>;
  /** Shared across the whole form; the save reads it. */
  staged: Map<string, StagedImage>;
  /** Origin that serves committed site pictures, for previews. */
  siteOrigin?: string;
}

const SITE_ORIGIN = 'https://indianliberals.in';
const ACCEPT = 'image/jpeg,image/png,image/webp,image/svg+xml';

const EXT: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
  'image/svg+xml': 'svg',
};

function tidyStem(name: string): string {
  return (
    name
      .replace(/\.[a-z0-9]+$/i, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 80) || 'picture'
  );
}

function make<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className = '',
  text = '',
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

/** Build the widget and return its root element. */
export function imageField(options: ImageFieldOptions): HTMLElement {
  const { field, path, staged } = options;
  const origin = options.siteOrigin ?? SITE_ORIGIN;

  const root = make('div', 'imgfield');
  const zone = make('div', 'imgzone');
  const shown = make('img', 'imgshown') as HTMLImageElement;
  shown.alt = '';
  const empty = make('p', 'imgempty', 'No picture yet. Drop one here, or');
  const line = make('p', 'imgline');
  const row = make('div', 'imgrow');

  const pick = make('button', 'btn btn-quiet tiny', 'Choose a picture');
  pick.type = 'button';
  const remove = make('button', 'btn btn-quiet tiny', 'Remove');
  remove.type = 'button';
  const capture = make('button', 'btn btn-quiet tiny', 'Capture the first page of the PDF');
  capture.type = 'button';

  const file = make('input') as HTMLInputElement;
  file.type = 'file';
  file.accept = ACCEPT;
  file.hidden = true;

  row.append(pick, capture, remove, file);
  zone.append(shown, empty);
  root.append(zone, row, line);

  function say(text: string, bad = false): void {
    line.textContent = text;
    line.style.fontWeight = bad ? '700' : '';
  }

  function previewUrl(): string {
    const held = staged.get(path);
    if (held) return held.url;
    const value = options.value();
    if (!value) return '';
    if (/^https?:\/\//.test(value)) return value;
    return `${origin}${value.startsWith('/') ? '' : '/'}${value}`;
  }

  function draw(): void {
    const url = previewUrl();
    shown.src = url;
    shown.hidden = !url;
    empty.hidden = Boolean(url);
    remove.hidden = !url;
    const canCapture =
      field.name === 'cover_image' && Boolean(options.pdfUrl && options.pdfUrl());
    capture.hidden = !canCapture;
  }

  async function place(blob: Blob, filename: string): Promise<void> {
    const type = blob.type;
    const ext = EXT[type];
    if (!ext) {
      say('That is not a picture we can use. JPEG, PNG, WebP or SVG.', true);
      return;
    }
    const stem = options.slug() || tidyStem(filename);
    const named = new File([blob], `${stem}.${ext}`, { type });
    const token = await options.token();

    if (field.image?.store === 'r2') {
      say('Sending the picture to the archive server.');
      const done = await sendFile(named, 'cover', token, () => {}, true);
      if (!done.ok || !done.url) {
        say(done.error ?? 'The upload did not work.', true);
        return;
      }
      staged.delete(path);
      options.setValue(done.url);
      say('Done. The picture is on the archive server.');
    } else {
      say('Holding the picture until you save.');
      const done = await sendFile(named, 'staging', token, () => {});
      if (!done.ok || !done.url || !done.key) {
        say(done.error ?? 'The upload did not work.', true);
        return;
      }
      const dir = field.image?.dir ?? '/images';
      const sitePath = `${dir}/${stem}.${ext}`;
      staged.set(path, {
        repoPath: `apps/site/public${sitePath}`,
        stagingKey: done.key,
        url: done.url,
      });
      options.setValue(sitePath);
      say('Ready. It is saved with the entry when you press save.');
    }
    draw();
  }

  pick.addEventListener('click', () => file.click());
  file.addEventListener('change', () => {
    const chosen = file.files?.[0];
    if (chosen) void place(chosen, chosen.name);
    file.value = '';
  });

  zone.addEventListener('dragover', (event) => {
    event.preventDefault();
    zone.classList.add('over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', (event) => {
    event.preventDefault();
    zone.classList.remove('over');
    const dropped = event.dataTransfer?.files?.[0];
    if (dropped) void place(dropped, dropped.name);
  });

  remove.addEventListener('click', () => {
    staged.delete(path);
    options.setValue('');
    say('');
    draw();
  });

  capture.addEventListener('click', async () => {
    const url = options.pdfUrl?.();
    if (!url) return;
    capture.disabled = true;
    say('Reading the first page of the PDF.');
    try {
      const cover = await captureFirstPage(url);
      await place(cover.blob, `cover.${cover.ext}`);
    } catch (error) {
      say(`Could not capture the page: ${(error as Error).message}`, true);
    } finally {
      capture.disabled = false;
    }
  });

  draw();
  return root;
}

/** What the save endpoint wants for everything still staged. */
export function stagedForSave(
  staged: Map<string, StagedImage>,
): { path: string; stagingKey: string }[] {
  return [...staged.values()].map((held) => ({
    path: held.repoPath,
    stagingKey: held.stagingKey,
  }));
}

/** The widget's styles, injected once per page that uses it. */
export function imageFieldStyles(): string {
  return `
    .imgfield { margin: .2rem 0 .3rem; }
    .imgzone { border: 2px dashed var(--ink, #000); border-radius: 0; padding: .9rem; text-align: center; background: var(--paper, #fff); }
    .imgzone.over { border-style: solid; }
    .imgshown { max-width: 200px; max-height: 260px; display: inline-block; border: 1px solid var(--ink, #000); }
    .imgempty { margin: .4rem 0; font-size: .85rem; color: var(--ink, #000); }
    .imgrow { display: flex; gap: .5rem; flex-wrap: wrap; margin-top: .5rem; }
    .imgline { font-size: .82rem; margin: .35rem 0 0; color: var(--ink, #000); }
  `;
}
