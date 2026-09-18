// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://lighton.by',
  trailingSlash: 'always',
  build: { format: 'directory', inlineStylesheets: 'auto' },
  integrations: [
    sitemap({
      i18n: undefined,
      changefreq: 'weekly',
      lastmod: new Date(),
      filter: (page) => !page.includes('/politika-konfidencialnosti'),
      serialize(item) {
        // Главная и страницы услуг — приоритетнее служебных
        if (item.url === 'https://lighton.by/') item.priority = 1.0;
        else if (item.url.includes('/uslugi/')) item.priority = 0.9;
        else item.priority = 0.7;
        return item;
      },
    }),
  ],
  // Дублирует 301 из .htaccess: страховка для хостингов без mod_rewrite.
  redirects: {
    '/home': '/',
    '/services': '/uslugi/',
    '/details': '/detailing/',
    '/realizations': '/raboty/',
    '/company': '/o-kompanii/',
    '/contact': '/kontakty/',
  },
  image: { responsiveStyles: true },
  prefetch: { prefetchAll: true, defaultStrategy: 'hover' },
});
