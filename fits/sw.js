/**
 * Офлайн-режим: оболочка приложения кэшируется при установке,
 * дальше отдаётся из кэша и тихо обновляется в фоне (stale-while-revalidate).
 * Данные пользователя живут в IndexedDB и сюда не попадают.
 */
const CACHE = 'fits-v2';
// Модель нейросети — отдельный кэш: он не чистится при обновлении приложения.
const AI_CACHE = 'ai-models-1.4.5';
const SHELL = [
  './',
  'index.html',
  'manifest.webmanifest',
  'css/app.css',
  'icons/icon.svg',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/apple-touch-icon.png',
  'js/ai-bg.js',
  'js/app.js',
  'js/constants.js',
  'js/db.js',
  'js/image-tools.js',
  'js/outfit-tools.js',
  'js/router.js',
  'js/store.js',
  'js/theme.js',
  'js/ui.js',
  'js/util.js',
  'js/views/builder.js',
  'js/views/calendar.js',
  'js/views/closet.js',
  'js/views/item-editor.js',
  'js/views/item.js',
  'js/views/outfits.js',
  'js/views/settings.js',
  'js/views/stats.js',
  'vendor/bg-removal.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('fits-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

const isModelFile = (url) => url.pathname.includes('/background-removal-data') && /(^|\.)(staticimgly\.com|unpkg\.com)$/.test(url.hostname);

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (isModelFile(url)) {
    // Файлы модели неизменны для версии: из кэша, а при первом разе — из сети с сохранением.
    e.respondWith(
      caches.open(AI_CACHE).then(async (cache) => {
        const hit = await cache.match(req);
        if (hit) return hit;
        const res = await fetch(req);
        if (res.ok) cache.put(req, res.clone());
        return res;
      }),
    );
    return;
  }
  if (url.origin !== location.origin) return;
  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(req, { ignoreSearch: true });
      const fresh = fetch(req)
        .then((res) => {
          if (res.ok) cache.put(req, res.clone());
          return res;
        })
        .catch(() => null);
      if (cached) {
        e.waitUntil(fresh);
        return cached;
      }
      return (await fresh) ?? (req.mode === 'navigate' ? cache.match('index.html') : Response.error());
    }),
  );
});
