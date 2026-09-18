/**
 * Проверка Яндекс.Метрики без доступа к самому Яндексу.
 *
 * Загрузчик Метрики создаёт window.ym как функцию-заглушку, которая копит
 * аргументы в массиве window.ym.a до тех пор, пока не подгрузится tag.js.
 * Значит инициализацию и цели можно проверить полностью, даже когда домен
 * mc.yandex.ru недоступен: смотрим, что попало в очередь.
 *
 * Запуск: npm run preview, затем node scripts/check-metrika.mjs
 */

import { chromium } from 'playwright';
import { analytics } from '../src/config/site.ts';

const BASE = process.env.BASE ?? 'http://127.0.0.1:4321';
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const ID = Number(analytics.yandexMetrika);

const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ru-BY' });
const page = await ctx.newPage();

const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push(e.message));

// Сам tag.js из этой среды не загрузится, поэтому отвечаем на него пустышкой:
// заглушка ym к этому моменту уже создана, и очередь работает.
await page.route('**/mc.yandex.ru/**', (route) =>
  route.fulfill({ status: 200, contentType: 'application/javascript', body: '' }),
);

// Заявку никуда не отправляем — подменяем ответ обработчика успехом.
await page.route('**/api/lead.php', (route) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }),
);

const queue = () =>
  page.evaluate(() => {
    const ym = window.ym;
    if (typeof ym !== 'function') return null;
    return (ym.a ?? []).map((args) => Array.from(args));
  });

const ok = [];
const bad = [];
const check = (cond, good, err) => (cond ? ok : bad).push(cond ? good : err);

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
// requestIdleCallback с запасом: счётчик стартует в простое браузера.
await page.waitForTimeout(1500);

const afterLoad = await queue();
check(afterLoad !== null, 'window.ym создан загрузчиком', 'window.ym не появился — счётчик не стартовал');

const init = afterLoad?.find((a) => a[1] === 'init');
check(
  Boolean(init) && init[0] === ID,
  `init вызван с номером ${ID}`,
  `init не вызван или номер не тот: ${JSON.stringify(init)}`,
);
check(
  Boolean(init?.[2]?.webvisor),
  'вебвизор включён в настройках init',
  'вебвизор не включён',
);

// ─── Цель на отправке формы ───────────────────────────────────────────────
await page.locator('#form-hero input[name="name"]').fill('Иван');
const phone = page.locator('#form-hero input[name="phone"]');
await phone.fill('');
await phone.type('291234567', { delay: 5 });
await page.locator('#form-hero input[name="consent"]').check();
// В форме стоит защита от ботов: сабмит раньше трёх секунд отбрасывается.
await page.waitForTimeout(3200);
await page.locator('#form-hero button[type="submit"]').click();
await page.waitForTimeout(600);

const status = (await page.locator('#form-hero [data-form-status]').textContent())?.trim();
check(Boolean(status), `форма ответила: «${status}»`, 'форма не показала статус отправки');

const afterSubmit = await queue();
const leadGoal = afterSubmit?.find((a) => a[1] === 'reachGoal' && a[2] === 'lead_sent');
check(
  Boolean(leadGoal) && leadGoal[0] === ID,
  'цель lead_sent ушла с верным номером счётчика',
  `цель lead_sent не зарегистрирована: ${JSON.stringify(leadGoal)}`,
);

// ─── Цель на клике по телефону ────────────────────────────────────────────
await page.locator('a[href^="tel:"]').first().click();
await page.waitForTimeout(300);

const afterCall = await queue();
const callGoal = afterCall?.find((a) => a[1] === 'reachGoal' && a[2] === 'phone_click');
check(
  Boolean(callGoal) && callGoal[0] === ID,
  'цель phone_click ушла с верным номером счётчика',
  `цель phone_click не зарегистрирована: ${JSON.stringify(callGoal)}`,
);

check(errors.length === 0, 'консоль браузера чистая', `ошибки в консоли: ${errors.join(' | ')}`);

await browser.close();

for (const line of ok) console.log('✓', line);
for (const line of bad) console.log('✗', line);

console.log(`\nОчередь вызовов ym: ${JSON.stringify(afterCall)}`);

if (bad.length) process.exit(1);
console.log('\n✓ Метрика подключена корректно');
