/**
 * Lighthouse и скриншоты по собранному сайту.
 *
 * Запуск: npm run preview, затем node scripts/audit.mjs
 * Результаты кладутся в .audit/ (каталог не попадает в репозиторий).
 */

import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright';
import lighthouse from 'lighthouse';

const BASE = process.env.BASE ?? 'http://127.0.0.1:4321';
const OUT = '.audit';
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const PAGES = [
  { url: '/', name: 'glavnaya' },
  { url: '/uslugi/polirovka-far/', name: 'usluga' },
  { url: '/kontakty/', name: 'kontakty' },
];

mkdirSync(OUT, { recursive: true });

// ─── Lighthouse ───────────────────────────────────────────────────────────
const browser = await chromium.launch({
  executablePath: CHROME,
  args: ['--remote-debugging-port=9222', '--no-sandbox'],
});

const rows = [];

for (const page of PAGES) {
  const result = await lighthouse(
    BASE + page.url,
    { port: 9222, output: 'json', logLevel: 'error' },
    {
      extends: 'lighthouse:default',
      settings: {
        formFactor: 'mobile',
        screenEmulation: { mobile: true, width: 390, height: 844, deviceScaleFactor: 2 },
        throttling: {
          rttMs: 150,
          throughputKbps: 1638.4,
          cpuSlowdownMultiplier: 4,
          requestLatencyMs: 562.5,
          downloadThroughputKbps: 1474.56,
          uploadThroughputKbps: 675,
        },
      },
    },
  );

  const lhr = result.lhr;
  const score = (id) => Math.round((lhr.categories[id]?.score ?? 0) * 100);

  rows.push({
    page: page.url,
    performance: score('performance'),
    accessibility: score('accessibility'),
    bestPractices: score('best-practices'),
    seo: score('seo'),
    lcp: lhr.audits['largest-contentful-paint']?.displayValue ?? '—',
    cls: lhr.audits['cumulative-layout-shift']?.displayValue ?? '—',
    tbt: lhr.audits['total-blocking-time']?.displayValue ?? '—',
    weight: lhr.audits['total-byte-weight']?.displayValue ?? '—',
  });
}

await browser.close();

console.log('\nLighthouse, мобильный профиль:\n');
console.table(rows);

// ─── Скриншоты и поведенческие проверки ───────────────────────────────────
const shots = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });

for (const [label, viewport] of [
  ['mobile', { width: 390, height: 844 }],
  ['desktop', { width: 1440, height: 900 }],
]) {
  const ctx = await shots.newContext({ viewport, deviceScaleFactor: 2, locale: 'ru-BY' });
  const p = await ctx.newPage();

  for (const page of PAGES) {
    await p.goto(BASE + page.url, { waitUntil: 'networkidle' });
    // Даём CSS-анимациям встать в устойчивое положение, чтобы снимки
    // не отличались от запуска к запуску.
    await p.waitForTimeout(700);
    await p.screenshot({ path: `${OUT}/${page.name}-${label}.png`, fullPage: false });
  }

  // Горизонтальный скролл на узком экране — частая скрытая поломка вёрстки.
  if (label === 'mobile') {
    await p.goto(BASE + '/', { waitUntil: 'networkidle' });
    const overflow = await p.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    console.log(overflow > 0 ? `✗ Горизонтальный скролл: ${overflow}px` : '✓ Горизонтального скролла нет');
  }

  await ctx.close();
}

// ─── Поведение форм и модалки ─────────────────────────────────────────────
const ctx = await shots.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ru-BY' });
const p = await ctx.newPage();
const errors = [];
p.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
p.on('pageerror', (e) => errors.push(e.message));

await p.goto(BASE + '/', { waitUntil: 'networkidle' });

// Маска телефона должна привести любой ввод к единому формату.
const phone = p.locator('#form-hero input[name="phone"]');
await phone.fill('');
await phone.type('291234567', { delay: 10 });
const masked = await phone.inputValue();
console.log(masked === '+375 (29) 123-45-67' ? '✓ Маска телефона работает' : `✗ Маска дала «${masked}»`);

// Неверный код оператора должен отлавливаться до отправки.
await phone.fill('');
await phone.type('211234567', { delay: 10 });
await p.locator('#form-hero input[name="name"]').fill('Иван');
await p.locator('#form-hero input[name="consent"]').check();
await p.locator('#form-hero button[type="submit"]').click();
await p.waitForTimeout(300);
const phoneError = await p.locator('#form-hero [data-error-for="phone"]').textContent();
console.log(phoneError?.trim() ? '✓ Неверный код оператора отклонён' : '✗ Неверный номер прошёл валидацию');

// Модалка обратного звонка.
await p.locator('.quickcall__btn--accent, [data-open-callback]').first().click();
await p.waitForTimeout(300);
const modalOpen = await p.locator('[data-callback-modal]').evaluate((d) => d.open);
await p.keyboard.press('Escape');
await p.waitForTimeout(200);
const modalClosed = await p.locator('[data-callback-modal]').evaluate((d) => !d.open);
console.log(modalOpen && modalClosed ? '✓ Модалка открывается и закрывается по Esc' : '✗ Проблема с модалкой');

await ctx.close();

// ─── prefers-reduced-motion ───────────────────────────────────────────────
const rmCtx = await shots.newContext({
  viewport: { width: 1440, height: 900 },
  reducedMotion: 'reduce',
});
const rmPage = await rmCtx.newPage();
await rmPage.goto(BASE + '/', { waitUntil: 'networkidle' });
await rmPage.waitForTimeout(600);
const canvasOn = await rmPage.locator('.rays__canvas').evaluate((c) => c.classList.contains('is-on'));
console.log(canvasOn ? '✗ Canvas запустился вопреки prefers-reduced-motion' : '✓ Canvas не стартует при reduced-motion');
await rmCtx.close();

await shots.close();

if (errors.length) {
  console.log('\nОшибки в консоли браузера:');
  for (const e of errors) console.log('  ✗', e);
} else {
  console.log('✓ Консоль браузера чистая');
}

console.log(`\nСкриншоты: ${OUT}/`);
