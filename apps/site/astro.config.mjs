// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// Cloudflare Pages adapter — uncomment when deploying.
// import cloudflare from '@astrojs/cloudflare';

export default defineConfig({
  site: 'https://indianliberals.in',
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
