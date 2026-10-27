// Рендер ролика-вакансии: node render.mjs <видео-визитка.mp4> [папка_для_кадров]
// 1) монтирует вертикальную подложку из фрагментов визитки, 2) покадрово снимает
// графику scene.html с прозрачным фоном, 3) накладывает одно на другое через ffmpeg
// и кладёт звуком песню pesnya.m4a (если её нет — тихая дорожка).
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// playwright предустановлен глобально — ESM-импорт его не видит, берём через require
const { chromium } = createRequire(import.meta.url)('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const [src, framesArg] = process.argv.slice(2);
const framesDir = framesArg || join(here, '.frames');
const FPS = 30;
if (!src) throw new Error('Укажите путь к видео-визитке');

// [начало в исходнике, длительность] — фрагмент визитки; ['foto/…', длительность] — фото на весь экран,
// ['foto/…', длительность, 'fit'] — фото целиком по ширине на размытом фоне.
// По порядку монтажа; суммарно = DURATION в scene.html
const CLIPS = [
  [13.0, 3.0],          // команда идёт на камеру — хук
  [4.6, 1.6],           // вывеска «Диагностическая станция №152»
  [73.1, 0.8],          // нашивка «Инженер-диагност»
  [112.5, 1.6],         // осмотр из смотровой ямы — образование
  ['foto/4.jpg', 1.4],  // прибор проверки фар — опыт
  ['foto/5.jpg', 1.4],  // «Лазерная апертура» — опыт
  ['foto/2.jpg', 2.4],  // сотрудник с метлой и лопатой — бонус «многозадачность»
  ['foto/komanda.jpg', 1.8, 'fit'], // команда с тачкой — «территория в порядке» (целиком, чтобы никого не обрезать)
  [68.1, 0.9],          // экран диагностики — ПК
  [71.9, 0.9],          // клавиатура — ПК
  [70.1, 0.8],          // сотрудник за компьютером — ПК
  ['foto/zal.jpg', 1.8], // зал с линией техосмотра — целеустремлённость («только вперёд»)
  [133.0, 2.2],         // сотрудник поправляет кепку — стрессоустойчивость
  ['foto/zal.jpg', 6.8], // фон плашки «Требования к кандидату»
  ['foto/5.jpg', 6.8],  // фон плашки «Основные обязанности»
  [74.1, 2.7],          // сотрудник машет рукой — условия («…станция твоя!»)
  [130.9, 1.9],         // сотрудник у рабочего места — условия
  [136.8, 2.0],         // станция с высоты — «Гоголя, 181 — ждём тебя!»
  ['foto/stanciya.jpg', 2.2], // фасад станции с вывеской
  ['foto/kot.jpg', 5.5], // кот на рабочем столе — «дружный коллектив, и даже кот»
  [13.8, 3.2],          // команда — финал («Звони скорей…»)
  ['foto/komanda.jpg', 2.05, 'fit'], // команда с тачкой — финал
  [4.5, 1.65],          // вывеска — финал
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

// Каждый видеофрагмент: размытый растянутый фон + чёткое видео 1080 по ширине с медленным наездом
const isPhoto = ([s]) => typeof s === 'string';
const inputs = CLIPS.flatMap((c) => isPhoto(c)
  // +0.5 с запаса: zoompan съедает пару кадров, а точную длину всё равно задаёт trim
  ? ['-loop', '1', '-framerate', String(FPS), '-t', String(c[1] + 0.5), '-i', join(here, c[0])]
  : ['-ss', String(c[0]), '-t', String(c[1]), '-i', src]);
const parts = CLIPS.map(([, d, mode], i) => mode === 'fit' ? [
  `[${i}:v]fps=${FPS},setsar=1,split[a${i}][b${i}]`,
  `[a${i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:2,eq=brightness=-0.22[bg${i}]`,
  `[b${i}]scale=1080:-2[fg${i}]`,
  `[bg${i}][fg${i}]overlay=0:(H-h)/2,trim=duration=${d},setpts=PTS-STARTPTS,setsar=1[v${i}]`,
].join(';') : isPhoto(CLIPS[i]) ? [
  // Фото — на весь экран 9:16 с медленным наездом
  // (масштаб ×2 перед zoompan — чтобы наезд шёл плавно, без дрожания)
  `[${i}:v]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,setsar=1,` +
    `zoompan=z='1+0.1*on/${Math.round(d * FPS)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=${FPS},` +
    `eq=saturation=1.08,trim=duration=${d},setpts=PTS-STARTPTS,setsar=1[v${i}]`,
].join(';') : [
  `[${i}:v]fps=${FPS},setsar=1,split[a${i}][b${i}]`,
  `[a${i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:2,eq=brightness=-0.22:saturation=1.2[bg${i}]`,
  `[b${i}]scale=1188:-2,crop=1080:608:'(iw-1080)*t/${d}':'(ih-608)/2',eq=contrast=1.06:saturation=1.12,unsharp=5:5:0.8[fg${i}]`,
  `[bg${i}][fg${i}]overlay=0:640,trim=duration=${d},setpts=PTS-STARTPTS,setsar=1[v${i}]`,
].join(';'));
const n = CLIPS.length;
const filter = [
  ...parts,
  `${CLIPS.map((_, i) => `[v${i}]`).join('')}concat=n=${n}:v=1:a=0[base]`,
  `[${n}:v]format=rgba[gfx]`,
  `[base][gfx]overlay=0:0:format=auto,format=yuv420p[out]`,
].join(';');

// Песня из Suno: обрезаем по длине ролика, плавно гасим в конце, громкость — под соцсети (−14 LUFS).
// Без песни — тихая дорожка: некоторые площадки капризничают с видео без аудио
const song = join(here, 'pesnya.m4a');
const audioIn = existsSync(song) ? ['-i', song] : ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'];
// apad — песня чуть короче ролика (54,8 с), добиваем тишиной, чтобы -shortest не резал видео
const audioFilter = `[${n + 1}:a]apad,atrim=0:${duration},asetpts=PTS-STARTPTS,` +
  `afade=t=out:st=${duration - 1.5}:d=1.5,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aud]`;

const ffArgs = ['-y', '-loglevel', 'error', ...inputs, '-framerate', String(FPS), '-i', join(framesDir, '%04d.png'),
  ...audioIn,
  '-filter_complex', `${filter};${audioFilter}`, '-map', '[out]', '-map', '[aud]',
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-r', String(FPS),
  '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
  join(here, 'ds152-vakansiya.mp4')];
execFileSync('ffmpeg', ffArgs, { stdio: 'inherit' });
console.log('Готово');
