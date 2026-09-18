/**
 * Выгрузка фотографий компании в src/assets/.
 *
 * Запускать НА СВОЁЙ МАШИНЕ — скрипту нужен обычный доступ в интернет.
 *
 *   node scripts/fetch-photos.mjs          — снимки из карточки Яндекс.Карт
 *   node scripts/fetch-photos.mjs --wp     — вся медиабиблиотека старого сайта
 *   node scripts/fetch-photos.mjs --all    — и то, и другое
 *
 * Скачанное складывается в src/assets/yandex/ и src/assets/wp/. Уже имеющиеся
 * файлы пропускаются, так что скрипт можно запускать повторно.
 *
 * Дальше остаётся выбрать лучшие кадры, переименовать по списку из ASSETS.md
 * и положить в src/assets/ — компонент Photo подхватит их сам.
 */

import { mkdir, writeFile, access } from 'node:fs/promises';
import { join, extname } from 'node:path';

/**
 * Снимки из карточки организации на Яндекс.Картах (oid 85057471321).
 * Адреса извлечены из сохранённой страницы карточки. Суффикс orig отдаёт
 * оригинал; при желании его можно заменить на XXL, L_height и подобные.
 */
const YANDEX = [
  'https://avatars.mds.yandex.net/get-altay/14093322/2a00000192a47477679896256cbcdda62abe/orig',
  'https://avatars.mds.yandex.net/get-altay/14312158/2a0000019348a53c23785781a2fe6986678a/orig',
  'https://avatars.mds.yandex.net/get-altay/14733519/2a00000197641accb629269e268446601d51/orig',
  'https://avatars.mds.yandex.net/get-altay/15223195/2a000001976304e9e9719e283bbbc186cd62/orig',
  'https://avatars.mds.yandex.net/get-altay/15417312/2a00000196a0f3c9b165c88289db5998749f/orig',
  'https://avatars.mds.yandex.net/get-altay/15417312/2a00000197b54fbe5df974eeadc29535a5fa/orig',
  'https://avatars.mds.yandex.net/get-altay/15487932/2a0000019782115423167b8b978a3b45df41/orig',
  'https://avatars.mds.yandex.net/get-altay/16134335/2a00000198d22d93b83b14920ba381a60fee/orig',
  'https://avatars.mds.yandex.net/get-altay/16386092/2a0000019bdfc20c175cc9ab3558da3c0a41/orig',
  'https://avatars.mds.yandex.net/get-altay/16399547/2a0000019a53fba7a0e558c2b364021f104a/orig',
  'https://avatars.mds.yandex.net/get-altay/16482798/2a0000019a5cfb6d84de19849e1a3d72a302/orig',
  'https://avatars.mds.yandex.net/get-altay/16792294/2a00000198d5de562f30e58e53c21c9a0cac/orig',
  'https://avatars.mds.yandex.net/get-altay/18132699/2a0000019be5b4befae871e46513eccfe3ce/orig',
  'https://avatars.mds.yandex.net/get-altay/19689422/2a0000019d9a381a198eafec734ca2acd685/orig',
  'https://avatars.mds.yandex.net/get-altay/4824927/2a0000018064d3207c0a85186652ad1a16cb/orig',
  'https://avatars.mds.yandex.net/get-sprav-posts/21054513/2a000001a07c166391b49917e7511f444c46/orig',
];

/**
 * Медиабиблиотека старого сайта на WordPress. Берём через публичный REST —
 * авторизация не нужна, в отличие от /wp-admin/, где к тому же нет массовой
 * выгрузки. Если эндпоинт закрыт, остаётся скачать wp-content/uploads/
 * файловым менеджером хостинга.
 */
const WP_API = 'https://lighton.by/wp-json/wp/v2/media';

const EXT_BY_TYPE = {
  'image/jpeg': '.jpg',
  'image/png': '.png',
  'image/webp': '.webp',
  'image/avif': '.avif',
  'image/gif': '.gif',
};

const exists = (p) => access(p).then(() => true, () => false);

async function download(url, dir, name) {
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (fetch-photos; lighton.by)' },
    redirect: 'follow',
  });

  if (!res.ok) return { url, status: 'ошибка', detail: `HTTP ${res.status}` };

  const type = (res.headers.get('content-type') ?? '').split(';')[0].trim();
  const ext = EXT_BY_TYPE[type];
  if (!ext) return { url, status: 'пропущен', detail: `не картинка (${type || 'без типа'})` };

  const file = join(dir, name.endsWith(ext) ? name : name + ext);
  if (await exists(file)) return { url, status: 'уже есть', detail: file };

  const bytes = Buffer.from(await res.arrayBuffer());
  if (bytes.length < 1024) return { url, status: 'пропущен', detail: 'подозрительно маленький файл' };

  await writeFile(file, bytes);
  return { url, status: 'скачан', detail: `${file} · ${Math.round(bytes.length / 1024)} КБ` };
}

async function fromYandex() {
  const dir = 'src/assets/yandex';
  await mkdir(dir, { recursive: true });
  console.log(`\nКарточка Яндекс.Карт: ${YANDEX.length} снимков → ${dir}`);

  const out = [];
  for (const [i, url] of YANDEX.entries()) {
    // Имя формируем из идентификатора картинки: он уникален и стабилен.
    const id = url.split('/').slice(-2, -1)[0].slice(0, 12);
    out.push(await download(url, dir, `yandex-${String(i + 1).padStart(2, '0')}-${id}`));
  }
  return out;
}

async function fromWordpress() {
  const dir = 'src/assets/wp';
  await mkdir(dir, { recursive: true });
  console.log(`\nМедиабиблиотека WordPress → ${dir}`);

  const items = [];
  for (let page = 1; page <= 20; page++) {
    const res = await fetch(`${WP_API}?per_page=100&page=${page}&_fields=id,source_url,alt_text`);
    if (res.status === 400) break; // страницы кончились
    if (!res.ok) {
      console.log(`  Эндпоинт ответил HTTP ${res.status}.`);
      console.log('  Если он закрыт, скачайте wp-content/uploads/ файловым менеджером хостинга.');
      return [];
    }
    const batch = await res.json();
    if (!Array.isArray(batch) || batch.length === 0) break;
    items.push(...batch);
    if (batch.length < 100) break;
  }

  console.log(`  Найдено файлов: ${items.length}`);

  const out = [];
  for (const item of items) {
    if (!item.source_url) continue;
    // Имя оригинала сохраняем — по нему понятно, что на снимке.
    const base = decodeURIComponent(item.source_url.split('/').pop() ?? `wp-${item.id}`);
    const name = base.replace(extname(base), '').replace(/[^\wЀ-ӿ-]+/g, '-').slice(0, 80);
    out.push(await download(item.source_url, dir, `${name}`));
  }
  return out;
}

const args = process.argv.slice(2);
const wantWp = args.includes('--wp') || args.includes('--all');
const wantYandex = args.includes('--all') || !wantWp;

const results = [
  ...(wantYandex ? await fromYandex() : []),
  ...(wantWp ? await fromWordpress() : []),
];

console.log('');
for (const r of results) {
  const mark = { скачан: '✓', 'уже есть': '·', пропущен: '–', ошибка: '✗' }[r.status];
  console.log(`  ${mark} ${r.status.padEnd(9)} ${r.detail}`);
}

const saved = results.filter((r) => r.status === 'скачан').length;
const failed = results.filter((r) => r.status === 'ошибка').length;

console.log(`\nСкачано: ${saved}, ошибок: ${failed}, всего обработано: ${results.length}`);
console.log('Дальше: выберите лучшие кадры и разложите по именам из ASSETS.md.');
