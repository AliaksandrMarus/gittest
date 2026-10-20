// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

/**
 * Без переменных получается боевая сборка для manipulator-bobruisk.by.
 * Для превью в подпапке задаются SITE_URL и BASE_PATH.
 */
const SITE = process.env.SITE_URL ?? 'https://manipulator-bobruisk.by';
const BASE = process.env.BASE_PATH ?? '/';

export default defineConfig({
  site: SITE,
  base: BASE,
  trailingSlash: 'always',
  build: { format: 'directory', inlineStylesheets: 'auto' },
  integrations: [
    sitemap({
      changefreq: 'weekly',
      lastmod: new Date(),
      filter: (page) => !page.includes('/politika-konfidencialnosti'),
    }),
  ],
});
