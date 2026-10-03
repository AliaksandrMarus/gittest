// Рендер листов браузером: PNG-превью для проверки (node render.mjs png [фрагменты имён]).
// Режим pdf даёт точные штриховки, но файл ~30 МБ; для репозитория — make_pdf.py.
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
const { chromium } = pw;
import fs from 'fs';
import path from 'path';
const dir = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const sheets = path.join(dir, 'sheets');
const mode = process.argv[2] || 'pdf';
const browser = await chromium.launch();
const page = await browser.newPage();
let files = fs.readdirSync(sheets).filter(f => f.endsWith('.svg')).sort();
if (process.argv.length > 3) files = files.filter(f => process.argv.slice(3).some(a => f.includes(a)));
if (mode === 'png') {
  const out = process.env.PNG_DIR || '/tmp';
  await page.setViewportSize({ width: 2100, height: 1485 });
  for (const f of files) {
    const svg = fs.readFileSync(path.join(sheets, f), 'utf8')
      .replace('width="420mm" height="297mm"', 'width="2100" height="1485"');
    await page.setContent(`<html><body style="margin:0">${svg}</body></html>`);
    await page.screenshot({ path: path.join(out, f.replace('.svg', '.png')) });
  }
} else {
  const body = files.map(f => `<div class="p">${fs.readFileSync(path.join(sheets, f), 'utf8')}</div>`).join('');
  await page.setContent(`<html><head><style>@page{size:420mm 297mm;margin:0}body{margin:0}
    .p{width:420mm;height:297mm;page-break-after:always;overflow:hidden}.p svg{display:block}</style></head>
    <body>${body}</body></html>`);
  await page.pdf({ path: path.join(dir, 'Проект_дом_9x12_Бобруйск.pdf'), width: '420mm', height: '297mm', printBackground: true });
}
await browser.close();
