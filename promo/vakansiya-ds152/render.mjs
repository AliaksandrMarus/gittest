// Рендер ролика-вакансии: node render.mjs <видео-визитка.mp4> [папка_для_кадров]
// 1) монтирует вертикальную подложку из фрагментов визитки, 2) покадрово снимает
// графику scene.html с прозрачным фоном, 3) накладывает одно на другое через ffmpeg.
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// playwright предустановлен глобально — ESM-импорт его не видит, берём через require
const { chromium } = createRequire(import.meta.url)('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const [src, framesArg] = process.argv.slice(2);
const framesDir = framesArg || join(here, '.frames');
const FPS = 30;
if (!src) throw new Error('Укажите путь к видео-визитке');

// [начало в исходнике, длительность] — по порядку монтажа; суммарно = DURATION в scene.html
const CLIPS = [
  [13.0, 3.0],   // команда идёт на камеру — хук
  [4.6, 1.6],    // вывеска «Диагностическая станция №152»
  [73.1, 0.8],   // нашивка «Инженер-диагност»
  [112.5, 2.2],  // осмотр из смотровой ямы — образование
  [61.3, 1.4],   // проверка багажника — опыт
  [65.2, 1.0],   // замер выхлопа — опыт
  [68.1, 0.9],   // экран диагностики — ПК
  [71.9, 0.9],   // клавиатура — ПК
  [70.1, 0.8],   // сотрудник за компьютером — ПК
  [77.7, 1.8],   // автомобиль заезжает на линию — целеустремлённость
  [133.0, 2.2],  // сотрудник поправляет кепку — стрессоустойчивость
  [74.1, 2.0],   // сотрудник машет рукой — условия
  [131.0, 2.0],  // сотрудник у рабочего места — условия
  [13.8, 3.2],   // команда — финал
  [136.8, 2.0],  // станция с высоты — финал
];

rmSync(framesDir, { recursive: true, force: true });
mkdirSync(framesDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(join(here, 'scene.html')).href);
await page.evaluate(() => window.ready);
const duration = await page.evaluate(() => window.DURATION);

for (let i = 0; i < Math.round(duration * FPS); i++) {
  const t = i / FPS;
  await page.evaluate((t) => window.render(t), t);
  await page.screenshot({ path: join(framesDir, `${String(i).padStart(4, '0')}.png`), omitBackground: true });
}
await browser.close();

// Каждый фрагмент: размытый растянутый фон + чёткое видео 1080 по ширине с медленным наездом
const inputs = CLIPS.flatMap(([ss, d]) => ['-ss', String(ss), '-t', String(d), '-i', src]);
const parts = CLIPS.map(([, d], i) => [
  `[${i}:v]fps=${FPS},setsar=1,split[a${i}][b${i}]`,
  `[a${i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:2,eq=brightness=-0.22:saturation=1.2[bg${i}]`,
  `[b${i}]scale=1188:-2,crop=1080:608:'(iw-1080)*t/${d}':'(ih-608)/2',eq=contrast=1.06:saturation=1.12,unsharp=5:5:0.8[fg${i}]`,
  `[bg${i}][fg${i}]overlay=0:640,trim=duration=${d},setpts=PTS-STARTPTS[v${i}]`,
].join(';'));
const n = CLIPS.length;
const filter = [
  ...parts,
  `${CLIPS.map((_, i) => `[v${i}]`).join('')}concat=n=${n}:v=1:a=0[base]`,
  `[${n}:v]format=rgba[gfx]`,
  `[base][gfx]overlay=0:0:format=auto,format=yuv420p[out]`,
].join(';');

const ffArgs = ['-y', '-loglevel', 'error', ...inputs, '-framerate', String(FPS), '-i', join(framesDir, '%04d.png'),
  // Тихая дорожка: некоторые площадки капризничают с видео без аудио
  '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
  '-filter_complex', filter, '-map', '[out]', '-map', `${n + 1}:a`,
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-r', String(FPS),
  '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart',
  join(here, 'ds152-vakansiya.mp4')];
execFileSync('ffmpeg', ffArgs, { stdio: 'inherit' });
console.log('Готово');
