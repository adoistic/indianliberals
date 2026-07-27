import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';
import react from '@astrojs/react';

// The CMS is entirely behind a login, so there is nothing to prerender and
// every route needs a server: reading a role, minting a GitHub token, signing
// an R2 upload. Server output throughout, on the Cloudflare adapter.
export default defineConfig({
  site: 'https://cms.indianliberals.in',
  output: 'server',
  adapter: cloudflare({ imageService: 'passthrough' }),
  integrations: [react()],
  vite: {
    ssr: { external: ['node:crypto'] },
  },
});
