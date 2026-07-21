// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';
import { remarkParagraphIds } from './src/plugins/remark-paragraph-ids.mjs';

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
    remarkPlugins: [remarkParagraphIds],
  },
  integrations: [
    mdx(),
    sitemap({
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
  },
  i18n: {
    defaultLocale: 'en',
    // BCP-47 / ISO 639-1 codes. Subdirectory per language per Google's
    // recommendation; English stays at root via prefixDefaultLocale: false.
    locales: ['en', 'hi', 'gu', 'mr', 'bn'],
    routing: { prefixDefaultLocale: false },
  },
});
