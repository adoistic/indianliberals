// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { remarkParagraphIds } from './src/plugins/remark-paragraph-ids.mjs';
import { remarkDemoteH1 } from './src/plugins/remark-demote-h1.mjs';

// Withheld works (`withheld: true` in a primary-works file) keep their pages
// as noindex notices; the sitemap must not advertise them. The sitemap filter
// only sees URLs, so the slugs are read straight off the frontmatter here.
// See src/lib/listable.ts and docs/withheld-works.md.
function withheldSlugs() {
  // fileURLToPath, not .pathname: the repository lives under a path with a
  // space in it, which .pathname leaves percent-encoded.
  const dir = fileURLToPath(new URL('./src/content/primary-works/', import.meta.url));
  const out = new Set();
  for (const name of readdirSync(dir)) {
    if (!name.endsWith('.md')) continue;
    const head = readFileSync(join(dir, name), 'utf8').slice(0, 6000);
    if (/^withheld:\s*true\s*$/m.test(head)) out.add(name.slice(0, -3));
  }
  return out;
}
const WITHHELD = withheldSlugs();
const isWithheldUrl = (page) => {
  const m = /\/primary-works\/([^/]+)\/$/.exec(page);
  return Boolean(m && WITHHELD.has(m[1]));
};

// Cloudflare Pages adapter — uncomment when deploying.
// import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  site: 'https://indianliberals.in',
  // Redirects for slugs removed in the 2026-06 duplicate-content cleanup
  // (WordPress double-imports that surfaced as repeated entries on the
  // Opinions/Musings listings). Static build → emitted as meta-refresh pages.
  redirects: {
    '/opinions/palkhivalas-lost-battle-shapes-the-future-of-indian-online-gaming-2/':
      '/opinions/palkhivalas-lost-battle-shapes-the-future-of-indian-online-gaming/',
    '/opinions/gg-agarkar-modern-indian-liberal-and-reformer-2/':
      '/opinions/gg-agarkar-modern-indian-liberal-and-reformer/',
    '/musings/blueprint-for-eradication-of-poverty-bp-godrej-1980/':
      '/musings/a-blueprint-for-eradication-of-poverty-bp-godrej-1980/',
    '/musings/in-name-of-freedom-the-us-india-alignment-in-cold-war/':
      '/musings/the-us-india-alignment-in-cold-war/',
    '/musings/manifesto-for-india-liberals/': '/musings/manifesto-for-indian-liberals/',
    '/musings/the-tiger-caged-concluding-installment-from-the-economists-survey-of-india/':
      '/musings/the-tiger-caged-part-ii/',
    '/primary-works/khoj-januray-february-2007/': '/primary-works/khoj-january-february-2007/',
  },
  markdown: {
    // Paragraph-stable citation anchors (id="p-xxxxxx") on every rendered
    // paragraph. Same derivation as the .md-sibling annotations — see
    // src/lib/paragraph-id.mjs.
    remarkPlugins: [remarkDemoteH1, remarkParagraphIds],
  },
  integrations: [
    mdx(),
    sitemap({
      // ThePrint mirror detail pages are noindex by design (theprint.in keeps
      // the SEO weight); listing them in the sitemap contradicts that signal
      // and triggers "submitted URL marked noindex" warnings. The section
      // landing page stays.
      filter: (page) =>
        (!page.includes('/theprint-mirror/') || page.endsWith('/theprint-mirror/')) &&
        !isWithheldUrl(page),
      // Emit hreflang alternates per Google's multilingual guidelines.
      // Each URL in the sitemap gets <xhtml:link rel="alternate" hreflang="X">
      // for every available language version. We provide the map directly so
      // sitemap doesn't try to guess from URL structure (slugs differ per lang).
      i18n: {
        defaultLocale: 'en',
        locales: {
          en: 'en-IN',
          hi: 'hi-IN',
          mr: 'mr-IN',
          bn: 'bn-IN',
          gu: 'gu-IN',
        },
      },
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
    build: {
      rollupOptions: {
        // Pagefind's index is emitted to /pagefind/pagefind.js after `astro
        // build` by the `pagefind --site dist` post-step. It does not exist
        // at Vite bundle-time, so externalise it — the browser will fetch
        // the file directly at runtime.
        external: ['/pagefind/pagefind.js'],
      },
    },
  },
  // adapter: cloudflare(),
  build: {
    inlineStylesheets: 'auto',
    // Astro renders pages serially by default. With 7,932 pages — 6,355 of
    // them Swatantra items — that put the Cloudflare Pages build at 36.7
    // minutes and it was terminated for exceeding the build time limit, while
    // the build container's other cores sat idle. The previous production
    // build, at 1,577 works, took 17 minutes, so the ceiling is somewhere
    // between.
    //
    // 4 rather than higher: each worker holds its own render context, and a
    // build that dies on memory is no better than one that dies on time.
    concurrency: 4,
  },
  i18n: {
    defaultLocale: 'en',
    // BCP-47 / ISO 639-1 codes. Subdirectory per language per Google's
    // recommendation; English stays at root via prefixDefaultLocale: false.
    locales: ['en', 'hi', 'gu', 'mr', 'bn'],
    routing: { prefixDefaultLocale: false },
  },
});
