/**
 * Генератор демо-иллюстраций — временная замена реальным фотографиям.
 *
 * Скачать настоящие снимки из этой среды нельзя (сетевая политика блокирует
 * все фотобанки), поэтому вместо заглушек рисуются фирменные иллюстрации:
 * тот же тёмный фон и циановый луч, что у фоновой анимации сайта, с крупной
 * иконкой услуги по центру. Иконки — те же контуры, что в Icon.astro,
 * придуманные для этого сайта, ничего чужого не копируется.
 *
 * Это не имитация фотографии: иллюстрация не претендует быть доказательством
 * реальной работы, поэтому в галерее «Наши работы» и в парах «было/стало»
 * она не обманывает посетителя так, как обманул бы стоковый снимок чужой
 * машины, выданный за результат этой мойки.
 *
 * Файлы кладутся ровно в те имена, что ждёт компонент Photo (см. ASSETS.md).
 * Когда появится реальный кадр — он загружается с тем же именем поверх,
 * без единой правки кода.
 *
 * Запуск: node scripts/gen-demo-visuals.mjs
 */

import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';

const W = 1600;
const H = 1200;

/** Контуры из src/components/Icon.astro — свои, для этого сайта. */
const ICONS = {
  droplet: '<path d="M12 2.7c3.6 4.2 6 7.4 6 10.3a6 6 0 0 1-12 0c0-2.9 2.4-6.1 6-10.3z"/>',
  engine: '<path d="M4 9h2V7h5v2h3l3 3h3v5h-3l-2 2H7l-3-3H2v-4h2V9z"/>',
  shield: '<path d="M12 2.5 20 6v6c0 4.4-3.3 8.4-8 9.5-4.7-1.1-8-5.1-8-9.5V6l8-3.5z"/>',
  film: '<rect x="2.5" y="4.5" width="19" height="15" rx="2.5"/><path d="M7 4.5v15M17 4.5v15" fill="none" stroke="#06080b" stroke-width="1.6"/>',
  headlight:
    '<path d="M3 7.5C3 6 4.2 5 5.7 5H12a7 7 0 0 1 0 14H5.7C4.2 19 3 18 3 16.5v-9z"/><path d="M16 9.5h5M16 12h5M16 14.5h5" fill="none" stroke="#06080b" stroke-width="1.6" stroke-linecap="round"/>',
  sofa: '<path d="M4 11V8a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v3"/><rect x="2" y="11" width="20" height="7" rx="2.5"/><path d="M6 18v2M18 18v2" fill="none" stroke="#0a0c10" stroke-width="2" stroke-linecap="round"/>',
};

/** Одна на icon-файл не хватает деталей: добавляем силуэт кузова фоном. */
const CAR_SILHOUETTE = `
  <path d="M120 640
    C 160 560, 260 500, 380 490
    L 480 420 C 560 380, 720 370, 860 400
    L 980 460 C 1120 470, 1260 520, 1340 600
    L 1420 620 C 1460 630, 1470 660, 1460 690
    L 1440 720 L 140 720 C 110 700, 105 665, 120 640 Z"
    fill="url(#carGrad)" opacity="0.5"/>
  <circle cx="360" cy="720" r="70" fill="#06080b" opacity="0.55"/>
  <circle cx="1220" cy="720" r="70" fill="#06080b" opacity="0.55"/>
`;

/**
 * Сцена: фон в палитре сайта + лучи прожектора + силуэт кузова + иконка
 * услуги в круглой подложке. Вариант меняет насыщенность и яркость свечения —
 * так пары «до/после» получают осмысленный контраст на одной композиции.
 */
function scene(iconName, variant = 'normal') {
  const icon = ICONS[iconName];
  if (!icon) throw new Error(`Нет иконки: ${iconName}`);

  const dim = variant === 'before';
  const beamOpacity = dim ? 0.06 : variant === 'after' ? 0.16 : 0.11;
  const carOpacity = dim ? 0.3 : 0.5;
  const glowR = dim ? 260 : variant === 'after' ? 340 : 300;
  const iconColor = dim ? '#7a8695' : '#5ee7ff';
  const badgeFill = dim ? 'rgb(122 134 149 / 0.14)' : 'rgb(94 231 255 / 0.16)';
  const grainOpacity = dim ? 0.5 : 0.32;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#131b26"/>
      <stop offset="1" stop-color="#06080b"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.38" r="${glowR / 1000}">
      <stop offset="0" stop-color="#5ee7ff" stop-opacity="${dim ? 0.16 : 0.32}"/>
      <stop offset="1" stop-color="#5ee7ff" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="carGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#1c2733"/>
      <stop offset="1" stop-color="#232f3d"/>
    </linearGradient>
    <linearGradient id="beam" x1="0.5" y1="0" x2="0.5" y2="1">
      <stop offset="0" stop-color="#5ee7ff" stop-opacity="${beamOpacity}"/>
      <stop offset="1" stop-color="#5ee7ff" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <rect width="${W}" height="${H}" fill="url(#glow)"/>

  <!-- Лучи прожектора, как в фоновой анимации сайта -->
  <g>
    <polygon points="${W * 0.5},-40 ${W * 0.3},${H} ${W * 0.62},${H}" fill="url(#beam)" transform="rotate(-6 ${W * 0.5} 0)"/>
    <polygon points="${W * 0.5},-40 ${W * 0.42},${H} ${W * 0.78},${H}" fill="url(#beam)" opacity="0.7" transform="rotate(9 ${W * 0.5} 0)"/>
    <polygon points="${W * 0.5},-40 ${W * 0.2},${H} ${W * 0.5},${H}" fill="url(#beam)" opacity="0.5" transform="rotate(-16 ${W * 0.5} 0)"/>
  </g>

  <!-- Силуэт кузова -->
  <g opacity="${carOpacity}">${CAR_SILHOUETTE}</g>

  <!-- Подложка и иконка услуги -->
  <circle cx="${W / 2}" cy="${H * 0.42}" r="230" fill="${badgeFill}"/>
  <circle cx="${W / 2}" cy="${H * 0.42}" r="230" fill="none" stroke="${iconColor}" stroke-opacity="0.35" stroke-width="2"/>
  <g transform="translate(${W / 2 - 130}, ${H * 0.42 - 130}) scale(10.8)" fill="${iconColor}">
    ${icon}
  </g>

  <!-- Зерно -->
  <g opacity="${grainOpacity}">
    ${Array.from({ length: 220 }, () => {
      const x = Math.round(Math.random() * W);
      const y = Math.round(Math.random() * H);
      const r = (Math.random() * 1.4 + 0.3).toFixed(1);
      const o = (Math.random() * 0.05 + 0.02).toFixed(3);
      return `<circle cx="${x}" cy="${y}" r="${r}" fill="#ffffff" opacity="${o}"/>`;
    }).join('')}
  </g>
</svg>`;
}

async function render(iconName, variant, outPath) {
  await sharp(Buffer.from(scene(iconName, variant)))
    .jpeg({ quality: 86 })
    .toFile(outPath);
  console.log('  ✓', outPath);
}

async function main() {
  await mkdir('src/assets/uslugi', { recursive: true });
  await mkdir('src/assets/raboty', { recursive: true });

  console.log('Шапки страниц услуг → src/assets/uslugi/');
  const services = [
    ['avtomoyka', 'droplet'],
    ['moyka-motora', 'engine'],
    ['moyka-dnishcha', 'shield'],
    ['antigraviynaya-plenka', 'film'],
    ['antikorroziynaya-obrabotka', 'shield'],
    ['tonirovka', 'film'],
    ['polirovka-far', 'headlight'],
    ['restavraciya-far', 'headlight'],
    ['himchistka-salona', 'sofa'],
  ];
  for (const [slug, icon] of services) {
    await render(icon, 'normal', `src/assets/uslugi/${slug}.jpg`);
  }

  console.log('\nПары «до / после» → src/assets/raboty/');
  const pairs = [
    ['far', 'headlight'],
    ['dnishche', 'shield'],
    ['salon', 'sofa'],
    ['motor', 'engine'],
  ];
  for (const [slug, icon] of pairs) {
    await render(icon, 'before', `src/assets/raboty/${slug}-do.jpg`);
    await render(icon, 'after', `src/assets/raboty/${slug}-posle.jpg`);
  }

  console.log('\nГалерея работ → src/assets/raboty/');
  const gallery = [
    ['tonirovka', 'film'],
    ['plenka', 'film'],
    ['moyka-pena', 'droplet'],
    ['antikor', 'shield'],
    ['motor', 'engine'],
    ['salon', 'sofa'],
  ];
  for (const [slug, icon] of gallery) {
    await render(icon, 'normal', `src/assets/raboty/${slug}.jpg`);
  }

  console.log('\nГотово: 23 файла.');
}

main();
