/**
 * Three ways to turn a document into an entry, all landing in the same place.
 *
 * Not everyone has an API key, and nobody should need one. So the same job can
 * be done by copying a prompt into whatever AI the editor already uses, by
 * letting the CMS call a model with the editor's own key, or by typing the
 * details in. The three paths produce identical JSON and go through identical
 * validation, which is the point: the AI is a convenience, never a separate
 * class of record.
 *
 * Where a key is involved it stays in the editor's browser. The CMS never
 * receives it, never stores it, and the request goes straight from their
 * machine to their provider so the bill and the data are both theirs.
 */

import type { CollectionDef, Field } from './collections';

// ── The prompt ───────────────────────────────────────────────────────────

function describeField(field: Field, indent = ''): string[] {
  const lines: string[] = [];
  const required = field.required ? 'required' : 'optional';
  let type: string = field.kind;
  if (field.options?.length) type = `one of: ${field.options.join(' | ')}`;
  if (field.kind === 'reference') type = `a ${field.collection} id`;
  if (field.kind === 'reference-list') type = `a list of ${field.collection} ids`;
  if (field.kind === 'string-list') type = 'a list of short strings';

  lines.push(`${indent}- ${field.name} (${required}, ${type})${field.hint ? `: ${field.hint}` : ''}`);
  for (const child of field.fields ?? []) lines.push(...describeField(child, `${indent}  `));
  return lines;
}

export interface PromptOptions {
  collection: CollectionDef;
  /** Only ask for what an editor actually needs, unless they want everything. */
  everything?: boolean;
  /** Slugs already in the archive, so the model reuses them instead of inventing. */
  knownThinkers?: string[];
  knownOrganisations?: string[];
}

/**
 * Build the prompt an editor pastes into their own AI along with the document.
 *
 * It is written to be pasted whole. Anything the model needs to know about the
 * archive's conventions is in here, because the editor should not have to
 * explain the house style to it themselves.
 */
export function buildPrompt(options: PromptOptions): string {
  const { collection, everything = false } = options;
  const fields = collection.fields.filter(
    (f) => everything || f.group === 'essential' || f.required,
  );

  const lines: string[] = [];
  lines.push(
    `You are helping catalogue a document for the Indian Liberals archive, a collection of works from the Indian liberal tradition maintained by the Centre for Civil Society.`,
    ``,
    `Read the attached document and describe it as JSON. This will become a "${collection.singular}" record.`,
    ``,
    `## What to produce`,
    ``,
    `A single JSON object. No prose before or after it, no markdown fence, just the object.`,
    ``,
    `Fields:`,
    ``,
  );

  for (const field of fields) lines.push(...describeField(field));

  if (collection.hasBody) {
    lines.push(
      ``,
      `Plus one more key, "body", holding markdown that goes below the record:`,
      ``,
      `  ## Summary`,
      `  One dense paragraph covering the whole document: what it argues, who wrote it, what it covers.`,
      ``,
      `  ## Key points`,
      `  Six to ten bullets, each a complete sentence naming the person and the claim.`,
    );
    lines.push(
      ``,
      `  ## Essays`,
      `  Only if the document contains several separate articles, as a periodical issue does.`,
      `  For each one:`,
      ``,
      `    ### Title exactly as printed`,
      `    *By Author exactly as printed*`,
      ``,
      `    A paragraph of summary that OPENS BY NAMING ITS OWN AUTHOR OR TITLE, like`,
      `    "T. H. Chowdary's cover feature argues that...". This matters: a repair tool`,
      `    re-pairs headings to prose using exactly that self identification, and a`,
      `    summary that does not name itself cannot be checked.`,
      ``,
      `    Then two to five bullets of specifics from that article.`,
    );
  }

  if (options.knownThinkers?.length) {
    lines.push(
      ``,
      `## People already in the archive`,
      ``,
      `Use these ids exactly when the document names one of them. Do not invent a new id for someone already listed.`,
      ``,
      options.knownThinkers.slice(0, 400).join(', '),
    );
  }

  lines.push(
    ``,
    `## Rules`,
    ``,
    `1. Only write what the document actually shows. If it does not say, leave the field out. Do not infer a year, a publisher or an author from the title.`,
    `2. Titles and names exactly as printed, including obvious typographical errors. This is an archive: the record should match the page.`,
    `3. No em dashes or en dashes anywhere. Use commas, colons or full stops.`,
    `4. British spelling.`,
    `5. If a page is illegible, say less rather than guessing.`,
    `6. Dates as they appear. If only a year is legible, give the year.`,
  );

  return lines.join('\n');
}

// ── Reading a model's answer back ────────────────────────────────────────

export interface ParseResult {
  ok: boolean;
  data?: Record<string, unknown>;
  body?: string;
  problems: string[];
}

/**
 * Take whatever the editor pasted back and find the JSON in it.
 *
 * Models wrap objects in fences, add a sentence of preamble, or both, and an
 * editor should not have to tidy that up by hand before it will work.
 */
export function parseModelOutput(text: string, collection: CollectionDef): ParseResult {
  const problems: string[] = [];
  let raw = text.trim();

  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenced) raw = fenced[1].trim();

  if (!raw.startsWith('{')) {
    const start = raw.indexOf('{');
    const end = raw.lastIndexOf('}');
    if (start === -1 || end <= start) {
      return { ok: false, problems: ['No JSON object found in that. Paste the whole reply.'] };
    }
    raw = raw.slice(start, end + 1);
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    return {
      ok: false,
      problems: [`That is not valid JSON: ${(error as Error).message}`],
    };
  }

  const body = typeof parsed.body === 'string' ? parsed.body : undefined;
  delete parsed.body;

  for (const field of collection.fields) {
    if (field.required && !(field.name in parsed) && !field.name.includes('.')) {
      problems.push(`Missing ${field.label}, which every ${collection.singular.toLowerCase()} needs.`);
    }
  }

  // The house rule the model is most likely to break, and the easiest to catch.
  const serialised = JSON.stringify(parsed) + (body ?? '');
  if (/[—–]/.test(serialised)) {
    problems.push('The reply contains em or en dashes. They will be replaced with commas.');
  }

  return { ok: problems.length === 0, data: parsed, body, problems };
}

/** Strip the dashes the house style bans, everywhere, before anything is saved. */
export function stripDashes<T>(value: T): T {
  if (typeof value === 'string') {
    return value.replace(/\s*—\s*/g, ', ').replace(/\s*–\s*/g, ', ') as unknown as T;
  }
  if (Array.isArray(value)) return value.map(stripDashes) as unknown as T;
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = stripDashes(v);
    return out as T;
  }
  return value;
}

// ── Calling a model directly, with the editor's key ──────────────────────

export type Provider = 'anthropic' | 'openrouter';

export interface DirectCall {
  provider: Provider;
  apiKey: string;
  model: string;
  prompt: string;
  /** Base64 PDF, when the editor uploaded one. */
  pdfBase64?: string;
  signal?: AbortSignal;
}

export const MODELS: Record<Provider, { id: string; label: string; note: string }[]> = {
  anthropic: [
    { id: 'claude-sonnet-5', label: 'Claude Sonnet 5', note: 'Reads PDFs directly. A good default.' },
    { id: 'claude-opus-5', label: 'Claude Opus 5', note: 'Slower and dearer, for difficult scans.' },
  ],
  openrouter: [
    { id: 'anthropic/claude-sonnet-5', label: 'Claude Sonnet 5', note: 'Reads PDFs directly.' },
    { id: 'google/gemini-2.5-pro', label: 'Gemini 2.5 Pro', note: 'Handles long documents well.' },
    { id: 'openai/gpt-5', label: 'GPT-5', note: 'A capable alternative.' },
  ],
};

/**
 * Send the prompt and the document straight from the editor's browser to their
 * provider. Their key, their bill, their data, and nothing about the exchange
 * touches our servers.
 *
 * No max_tokens is set anywhere here. Reasoning models spend an explicit budget
 * on hidden reasoning first and then return an empty or truncated answer, which
 * looks like a bug in the CMS rather than a setting.
 */
export async function callModel(call: DirectCall): Promise<string> {
  if (call.provider === 'anthropic') {
    const content: unknown[] = [{ type: 'text', text: call.prompt }];
    if (call.pdfBase64) {
      content.unshift({
        type: 'document',
        source: { type: 'base64', media_type: 'application/pdf', data: call.pdfBase64 },
      });
    }
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      signal: call.signal,
      headers: {
        'content-type': 'application/json',
        'x-api-key': call.apiKey,
        'anthropic-version': '2023-06-01',
        // Required for the browser to be allowed to call the API at all.
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: call.model,
        messages: [{ role: 'user', content }],
      }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${(await response.text()).slice(0, 300)}`);
    const data = (await response.json()) as { content: { type: string; text?: string }[] };
    return data.content.filter((c) => c.type === 'text').map((c) => c.text).join('');
  }

  const content: unknown[] = [{ type: 'text', text: call.prompt }];
  if (call.pdfBase64) {
    content.push({
      type: 'file',
      file: { filename: 'document.pdf', file_data: `data:application/pdf;base64,${call.pdfBase64}` },
    });
  }
  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    signal: call.signal,
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${call.apiKey}`,
      'HTTP-Referer': 'https://cms.indianliberals.in',
      'X-Title': 'Thothica CMS',
    },
    body: JSON.stringify({ model: call.model, messages: [{ role: 'user', content }] }),
  });
  if (!response.ok) throw new Error(`${response.status}: ${(await response.text()).slice(0, 300)}`);
  const data = (await response.json()) as { choices: { message: { content: string } }[] };
  return data.choices?.[0]?.message?.content ?? '';
}

// ── Writing the file ─────────────────────────────────────────────────────

function yamlValue(value: unknown, indent: string): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'boolean' || typeof value === 'number') return String(value);
  if (typeof value === 'string') {
    if (value.includes('\n')) {
      return `|\n${value.split('\n').map((l) => `${indent}  ${l}`).join('\n')}`;
    }
    // Quote anything YAML might read as something other than a plain string.
    //
    // The leading class includes both quote characters, which is not obvious
    // and was missing at first. Several works carry a title held inside its own
    // quotation marks, as `'"A Total War on Indian Poverty"'`. Emitted
    // unquoted, YAML reads the outer marks as the string delimiters and the
    // marks vanish from the record on the next save. Silent, and exactly the
    // kind of loss nobody notices until the archive disagrees with the page.
    const risky =
      /^[\s>|&*!%@`{}[\],'"]|:\s|\s#|#\s|^-|^(yes|no|true|false|null|on|off|~)$/i.test(value);
    return risky || value === '' ? JSON.stringify(value) : value;
  }
  if (Array.isArray(value)) {
    if (!value.length) return '[]';
    return `\n${value
      .map((item) =>
        item && typeof item === 'object' && !Array.isArray(item)
          ? `${indent}- ${yamlObject(item as Record<string, unknown>, `${indent}  `).trimStart()}`
          : `${indent}- ${yamlValue(item, `${indent}  `)}`,
      )
      .join('\n')}`;
  }
  return `\n${yamlObject(value as Record<string, unknown>, `${indent}  `)}`;
}

function yamlObject(object: Record<string, unknown>, indent: string): string {
  return Object.entries(object)
    .filter(([, v]) => v !== undefined)
    .map(([key, value]) => `${indent}${key}: ${yamlValue(value, indent)}`)
    .join('\n');
}

/** Assemble the finished file: frontmatter, then the markdown body. */
export function toMarkdownFile(data: Record<string, unknown>, body?: string): string {
  const clean = stripDashes(data);
  const front = yamlObject(clean, '');
  const text = body ? stripDashes(body).trim() : '';
  return `---\n${front}\n---\n\n${text}\n`;
}

/** A filename from a title: lowercase, hyphens, nothing surprising in a URL. */
export function slugify(input: string): string {
  return input
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}
