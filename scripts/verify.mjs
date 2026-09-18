/**
 * Проверки собранного сайта: SEO-мета, JSON-LD, ссылки и — главное —
 * сверка цен на страницах с эталонным прайсом из карточки Яндекс.Карт.
 *
 * Запуск: node scripts/verify.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const DIST = 'dist';

/**
 * Эталон. Взят из карточки организации на Яндекс.Картах (прайс обновлён
 * 8 сентября, источник — представитель организации). Если цена на сайте
 * разойдётся с этой таблицей, сборку нужно считать сломанной.
 */
const PRICE_TRUTH = {
  avtomoyka: '15–25 руб.',
  'moyka-motora': '35–45 руб.',
  'moyka-dnishcha': '45 руб.',
  'antigraviynaya-plenka': '100 руб.',
  'antikorroziynaya-obrabotka': '800 руб.',
  tonirovka: '300 руб.',
  'polirovka-far': '100 руб.',
  'himchistka-salona': '300 руб.',
  'restavraciya-far': 'По запросу',
};

const problems = [];
const notes = [];
const fail = (msg) => problems.push(msg);

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

const pages = walk(DIST).filter((f) => f.endsWith('.html'));
const docs = pages.map((file) => ({
  file,
  url: '/' + relative(DIST, file).replace(/index\.html$/, '').replace(/\\/g, '/'),
  html: readFileSync(file, 'utf8'),
}));

const pick = (html, re) => html.match(re)?.[1]?.trim() ?? '';

// ─── 1. Мета-теги ─────────────────────────────────────────────────────────
const titles = new Map();
const descriptions = new Map();

/** Astro отдаёт 301-редиректы как страницы-заглушки с meta refresh. */
const isStub = (html) => /<meta http-equiv="refresh"/i.test(html);

for (const { url, html } of docs) {
  if (isStub(html)) continue;

  const title = pick(html, /<title>([^<]*)<\/title>/);
  const desc = pick(html, /<meta name="description" content="([^"]*)"/);
  const canonical = pick(html, /<link rel="canonical" href="([^"]*)"/);
  const ogTitle = pick(html, /<meta property="og:title" content="([^"]*)"/);
  const ogImage = pick(html, /<meta property="og:image" content="([^"]*)"/);

  if (!title) fail(`${url}: пустой <title>`);
  if (title.length > 65) notes.push(`${url}: title ${title.length} символов — Яндекс обрежет`);
  if (!desc) fail(`${url}: нет meta description`);
  if (desc.length > 160) fail(`${url}: description ${desc.length} символов, лимит 160`);
  if (!canonical) fail(`${url}: нет canonical`);
  if (!ogTitle || !ogImage) fail(`${url}: неполная Open Graph разметка`);

  // Редиректы Astro отдают служебные заглушки — их дубли ожидаемы.
  const isRedirectStub = /<meta http-equiv="refresh"/i.test(html);
  if (!isRedirectStub) {
    if (titles.has(title)) fail(`Дубль title: ${url} и ${titles.get(title)}`);
    else titles.set(title, url);

    if (descriptions.has(desc)) fail(`Дубль description: ${url} и ${descriptions.get(desc)}`);
    else descriptions.set(desc, url);
  }
}

// ─── 2. JSON-LD ───────────────────────────────────────────────────────────
const seenTypes = new Set();

for (const { url, html } of docs) {
  if (/<meta http-equiv="refresh"/i.test(html)) continue;

  const blocks = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
  if (!blocks.length) {
    fail(`${url}: нет ни одного блока JSON-LD`);
    continue;
  }

  for (const [, raw] of blocks) {
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      fail(`${url}: JSON-LD не парсится — ${e.message}`);
      continue;
    }

    for (const node of [parsed].flat()) {
      const type = [node['@type']].flat().join('+');
      seenTypes.add(type);

      if (type.includes('AutoWash')) {
        for (const field of ['name', 'telephone', 'address', 'geo', 'openingHoursSpecification']) {
          if (!node[field]) fail(`${url}: в AutoWash нет поля ${field}`);
        }
        if (node.address?.addressLocality !== 'Бобруйск') {
          fail(`${url}: в адресе не Бобруйск`);
        }
      }

      if (type === 'Service' && !node.offers) fail(`${url}: Service без offers`);
      if (type === 'FAQPage' && !(node.mainEntity?.length >= 3)) {
        fail(`${url}: FAQPage меньше трёх вопросов`);
      }

      // Чужие оценки с Яндекс.Карт не должны попадать в разметку —
      // это прямое нарушение правил Google.
      if (JSON.stringify(node).includes('AggregateRating')) {
        fail(`${url}: в разметке появился AggregateRating`);
      }
    }
  }
}

for (const required of ['AutoWash+LocalBusiness', 'WebSite', 'Service', 'FAQPage', 'BreadcrumbList']) {
  if (!seenTypes.has(required)) fail(`Ни на одной странице нет схемы ${required}`);
}

// ─── 3. Цены ──────────────────────────────────────────────────────────────
for (const [slug, expected] of Object.entries(PRICE_TRUTH)) {
  const doc = docs.find((d) => d.url === `/uslugi/${slug}/`);
  if (!doc) {
    fail(`Нет страницы услуги /uslugi/${slug}/`);
    continue;
  }

  // В HTML неразрывные пробелы и сущности — нормализуем перед сравнением.
  const text = doc.html.replace(/&#\d+;|&nbsp;/g, ' ').replace(/\s+/g, ' ');
  if (!text.includes(expected)) {
    fail(`/uslugi/${slug}/: на странице нет цены «${expected}» из прайса Яндекса`);
  }
}

const priceList = docs.find((d) => d.url === '/uslugi/');
for (const [slug, expected] of Object.entries(PRICE_TRUTH)) {
  const text = priceList.html.replace(/&#\d+;|&nbsp;/g, ' ').replace(/\s+/g, ' ');
  if (!text.includes(expected)) fail(`/uslugi/: в сводном прайсе нет «${expected}» (${slug})`);
}

// ─── 4. Внутренние ссылки ─────────────────────────────────────────────────
const known = new Set(docs.map((d) => d.url));
known.add('/404/');

for (const { url, html } of docs) {
  const hrefs = [...html.matchAll(/href="(\/[^"#?]*)"/g)].map((m) => m[1]);
  for (const href of new Set(hrefs)) {
    if (/\.(css|js|png|jpg|svg|woff2|xml|txt|webmanifest|php|ico)$/.test(href)) continue;
    const normalized = href.endsWith('/') ? href : `${href}/`;
    if (!known.has(normalized)) fail(`${url}: битая внутренняя ссылка ${href}`);
  }
}

// ─── 5. Контакты и доступность ────────────────────────────────────────────
for (const { url, html } of docs) {
  if (/<meta http-equiv="refresh"/i.test(html)) continue;

  if (!html.includes('tel:+375259871010')) fail(`${url}: нет кликабельного телефона`);
  if (!html.includes('lang="ru-BY"')) fail(`${url}: не указан язык страницы`);
  if (!html.includes('class="skip-link"')) fail(`${url}: нет ссылки «к содержимому»`);

  const h1 = [...html.matchAll(/<h1[\s>]/g)].length;
  if (h1 !== 1) fail(`${url}: заголовков H1 на странице ${h1}, должен быть ровно один`);

  for (const [, tag] of html.matchAll(/<img\b([^>]*)>/g)) {
    if (!/\balt=/.test(tag)) fail(`${url}: <img> без alt`);
  }
}

// ─── 6. Редиректы ─────────────────────────────────────────────────────────
const htaccess = readFileSync(join(DIST, '.htaccess'), 'utf8');
const netlify = readFileSync(join(DIST, '_redirects'), 'utf8');

for (const [from, to] of [
  ['services', '/uslugi/'],
  ['details', '/detailing/'],
  ['realizations', '/raboty/'],
  ['company', '/o-kompanii/'],
  ['contact', '/kontakty/'],
  ['home', '/'],
]) {
  if (!htaccess.includes(from)) fail(`.htaccess: нет правила для /${from}/`);
  if (!netlify.includes(`/${from}`)) fail(`_redirects: нет правила для /${from}`);
  if (!htaccess.includes(to)) fail(`.htaccess: нет цели ${to}`);
}

// ─── Итог ─────────────────────────────────────────────────────────────────
console.log(`Страниц проверено: ${docs.length}`);
console.log(`Схем JSON-LD найдено: ${[...seenTypes].sort().join(', ')}`);

if (notes.length) {
  console.log('\nЗамечания:');
  for (const n of notes) console.log('  ·', n);
}

if (problems.length) {
  console.log(`\nОШИБКИ (${problems.length}):`);
  for (const p of problems) console.log('  ✗', p);
  process.exit(1);
}

console.log('\n✓ Все проверки пройдены');
