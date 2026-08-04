#!/usr/bin/env node
// Build the full-text Pagefind index for the archive's PDFs.
//
// Inputs:
//   works_meta.json  — one record per listed work with a pdf_url
//                      (scripts/fulltext/export-works-meta.py)
//   fulltext.jsonl   — {"key", "pages": [...]} per work, extracted with PyMuPDF
// Output:
//   a static Pagefind bundle (pagefind.js + wasm + fragments) that gets
//   uploaded to R2 under search/ and served from archive.indianliberals.in.
//
// The bundle is entirely separate from the site-build Pagefind index that
// powers the header quick search; nothing about that flow changes.
//
// Usage: node scripts/fulltext/build-index.mjs <works_meta.json> <fulltext.jsonl> <outdir>
//   (run with cwd anywhere; resolves pagefind from apps/site/node_modules)

import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import readline from "node:readline";
import fs from "node:fs";

// pagefind ships ESM-only with an exports map and no CJS entry, so resolve
// the site's installed copy by path rather than by bare specifier.
const here = path.dirname(fileURLToPath(import.meta.url));
const pagefind = await import(
  pathToFileURL(
    path.join(here, "..", "..", "apps", "site", "node_modules", "pagefind", "lib", "index.js"),
  ).href
);

const [metaPath, textPath, outDir] = process.argv.slice(2);
if (!outDir) {
  console.error("usage: build-index.mjs <works_meta.json> <fulltext.jsonl> <outdir>");
  process.exit(1);
}

const metas = JSON.parse(readFileSync(metaPath, "utf-8"));

// Pagefind language must match the script of the text so the right
// tokenizer is used; these are the site's five locales.
const PF_LANG = { en: "en", hi: "hi", mr: "mr", bn: "bn", gu: "gu" };

// One index for all five languages. Pagefind normally shards per language and
// the client only searches the shard matching the page's <html lang>, which
// would make Devanagari/Bengali/Gujarati queries silently return nothing from
// this English-routed page. Forcing a single shard keeps every script
// searchable from one box; Indic text is whitespace-tokenized either way
// (Pagefind has no hi/mr/bn/gu stemmers), so nothing is lost.
const { index } = await pagefind.createIndex({ forceLanguage: "en" });

let added = 0, missingMeta = 0, empty = 0;
const seen = new Set();

const rl = readline.createInterface({
  input: fs.createReadStream(textPath),
  crlfDelay: Infinity,
});
for await (const line of rl) {
  if (!line.trim()) continue;
  const { key, pages } = JSON.parse(line);
  if (seen.has(key)) continue; // resumed extractions can duplicate a key
  seen.add(key);
  const meta = metas[key];
  if (!meta) { missingMeta++; continue; }
  const content = pages.join("\n\n").trim();
  if (content.length < 40) { empty++; continue; }

  const filters = {
    type: [meta.work_type],
    language: [meta.language],
    collection: [meta.collection],
  };
  if (meta.decade != null) filters.decade = [`${meta.decade}s`];
  if (meta.themes?.length) filters.theme = meta.themes;

  await index.addCustomRecord({
    url: meta.path,
    content: `${meta.title}${meta.subtitle ? " — " + meta.subtitle : ""}\n\n${content}`,
    language: PF_LANG[meta.language] ?? "en",
    meta: {
      title: meta.title,
      image: meta.cover_image,
      byline: meta.byline,
      year: meta.year == null ? "" : String(meta.year),
      type: meta.work_type,
      pdf: meta.pdf_url,
      pages: String(pages.length),
    },
    filters,
    sort: { year: meta.year == null ? "0000" : String(meta.year).padStart(4, "0") },
  });
  added++;
}

const res = await index.writeFiles({ outputPath: outDir });
console.log(`indexed ${added} works (${missingMeta} without meta, ${empty} empty), errors: ${res.errors?.length ?? 0}`);
await pagefind.close();
