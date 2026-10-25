// Рендер ролика: node render.mjs [папка_для_кадров] [--stills]
// Покадрово снимает scene.html в Chromium и собирает MP4 через ffmpeg.
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// playwright предустановлен глобально — ESM-импорт его не видит, берём через require
const { chromium } = createRequire(import.meta.url)('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const framesDir = process.argv[2] || join(here, '.frames');
const stillsOnly = process.argv.includes('--stills');
const FPS = 30;

rmSync(framesDir, { recursive: true, force: true });
mkdirSync(framesDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(join(here, 'scene.html')).href);
await page.evaluate(() => window.ready);
const duration = await page.evaluate(() => window.DURATION);

const times = stillsOnly
  ? [1.6, 5.0, 10.8, 11.6, 15.5, 19.5]
  : Array.from({ length: Math.round(duration * FPS) }, (_, i) => i / FPS);

for (const [i, t] of times.entries()) {
  await page.evaluate((t) => window.render(t), t);
  const name = stillsOnly ? `still-${t.toFixed(1)}.png` : `${String(i).padStart(4, '0')}.png`;
  await page.screenshot({ path: join(framesDir, name) });
}
await browser.close();

if (!stillsOnly) {
  const out = join(here, 'ds152-den-avtomobilista.mp4');
  execFileSync('ffmpeg', [
    '-y', '-loglevel', 'error',
    '-framerate', String(FPS), '-i', join(framesDir, '%04d.png'),
    // Тихая дорожка: некоторые площадки капризничают с видео без аудио
    '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(FPS),
    '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart',
    out,
  ], { stdio: 'inherit' });
  console.log('Готово:', out);
}
