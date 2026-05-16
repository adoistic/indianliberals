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
    sitemap(),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
  // adapter: cloudflare(),
  build: {
    inlineStylesheets: 'auto',
  },
  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'hi', 'gu'],
    routing: { prefixDefaultLocale: false },
  },
});
