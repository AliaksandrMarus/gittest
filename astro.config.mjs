// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

/**
 * Один и тот же код собирается и для боевого домена, и для превью в подпапке.
 * Без переменных получается боевая сборка, поэтому забыть их при деплое
 * на lighton.by нельзя — там просто ничего не задаётся.
 */
const SITE = process.env.SITE_URL ?? 'https://lighton.by';
const BASE = process.env.BASE_PATH ?? '/';

/**
 * Astro сам подставляет базовый путь в адрес, ОТКУДА идёт редирект, но не в тот,
 * КУДА он ведёт. В подпапке из-за этого старые адреса вроде /company/ уводили бы
 * на несуществующий /o-kompanii/ вместо /gittest/o-kompanii/.
 */
function withBase(map) {
  const prefix = BASE.replace(/\/$/, '');
  if (!prefix) return map;
  return Object.fromEntries(Object.entries(map).map(([from, to]) => [from, prefix + to]));
}

export default defineConfig({
  site: SITE,
  base: BASE,
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
        const path = new URL(item.url).pathname.replace(BASE.replace(/\/$/, ''), '');
        if (path === '/') item.priority = 1.0;
        else if (path.startsWith('/uslugi/')) item.priority = 0.9;
        else item.priority = 0.7;
        return item;
      },
    }),
  ],
  // Дублирует 301 из .htaccess: страховка для хостингов без mod_rewrite.
  redirects: withBase({
    '/home': '/',
    '/services': '/uslugi/',
    '/details': '/detailing/',
    '/realizations': '/raboty/',
    '/company': '/o-kompanii/',
    '/contact': '/kontakty/',
  }),
  image: { responsiveStyles: true },
  prefetch: { prefetchAll: true, defaultStrategy: 'hover' },
});
