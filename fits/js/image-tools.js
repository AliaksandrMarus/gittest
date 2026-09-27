import { COLORS } from './constants.js';

/** Взвешенное расстояние между цветами (глаз чувствительнее к зелёному), 0…255. */
function dist(r1, g1, b1, r2, g2, b2) {
  const dr = r1 - r2, dg = g1 - g2, db = b1 - b2;
  return Math.sqrt(2 * dr * dr + 4 * dg * dg + 3 * db * db) / 3;
}

/**
 * Заливка «волшебной палочкой». Пиксель попадает в область, если он близок
 * к эталонному цвету, либо плавно продолжает соседа (для фонов с градиентом
 * освещения). Возвращает Uint8Array: 1 — в области.
 */
export function floodRegion(img, seeds, ref, tol) {
  const { width: W, height: H, data: d } = img;
  const n = W * H;
  const inRegion = new Uint8Array(n);
  const stack = new Int32Array(n);
  let sp = 0;
  const [rr, rg, rb] = ref;
  const soft = tol * 0.3, far = tol * 1.8;

  const accept = (q, from) => {
    const i = q * 4;
    if (d[i + 3] < 16) return true; // уже прозрачный
    const dRef = dist(d[i], d[i + 1], d[i + 2], rr, rg, rb);
    if (dRef < tol) return true;
    if (dRef > far) return false;
    const j = from * 4;
    return dist(d[i], d[i + 1], d[i + 2], d[j], d[j + 1], d[j + 2]) < soft;
  };

  for (const p of seeds) {
    if (!inRegion[p] && accept(p, p)) {
      inRegion[p] = 1;
      stack[sp++] = p;
    }
  }
  while (sp) {
    const p = stack[--sp];
    const x = p % W;
    if (x > 0 && !inRegion[p - 1] && accept(p - 1, p)) { inRegion[p - 1] = 1; stack[sp++] = p - 1; }
    if (x < W - 1 && !inRegion[p + 1] && accept(p + 1, p)) { inRegion[p + 1] = 1; stack[sp++] = p + 1; }
    if (p >= W && !inRegion[p - W] && accept(p - W, p)) { inRegion[p - W] = 1; stack[sp++] = p - W; }
    if (p < n - W && !inRegion[p + W] && accept(p + W, p)) { inRegion[p + W] = 1; stack[sp++] = p + W; }
  }
  return inRegion;
}

function median(arr) {
  const s = [...arr].sort((a, b) => a - b);
  return s[s.length >> 1] ?? 0;
}

/**
 * Автоудаление однотонного фона: заливка от краёв кадра цветом,
 * близким к медианному цвету рамки. Лучше всего работает, если вещь
 * сфотографирована на ровном фоне (кровать, пол, стена).
 * Возвращает маску прозрачности или null, если фон не нашёлся.
 */
export function autoBackgroundMask(img, tol = 40) {
  const { width: W, height: H, data: d } = img;
  const seeds = [];
  for (let x = 0; x < W; x++) seeds.push(x, (H - 1) * W + x);
  for (let y = 1; y < H - 1; y++) seeds.push(y * W, y * W + W - 1);
  const rs = [], gs = [], bs = [];
  for (const p of seeds) {
    const i = p * 4;
    if (d[i + 3] < 16) continue;
    rs.push(d[i]); gs.push(d[i + 1]); bs.push(d[i + 2]);
  }
  const ref = rs.length ? [median(rs), median(gs), median(bs)] : [255, 255, 255];
  const region = floodRegion(img, seeds, ref, tol);

  let bg = 0;
  for (let p = 0; p < region.length; p++) bg += region[p];
  const share = bg / region.length;
  if (share < 0.02 || share > 0.985) return null;

  const mask = new Uint8ClampedArray(W * H);
  for (let p = 0; p < mask.length; p++) mask[p] = region[p] ? 0 : 255;
  removeSpecks(mask, W, H);
  return feather(mask, W, H);
}

/** Убрать мелкий «мусор» — островки непрозрачных пикселей меньше 0.3% кадра. */
function removeSpecks(mask, W, H) {
  const n = W * H;
  const seen = new Uint8Array(n);
  const stack = new Int32Array(n);
  const minSize = Math.max(30, n * 0.003);
  for (let s = 0; s < n; s++) {
    if (!mask[s] || seen[s]) continue;
    let sp = 0, size = 0;
    const comp = [];
    stack[sp++] = s;
    seen[s] = 1;
    while (sp) {
      const p = stack[--sp];
      size++;
      if (size <= minSize) comp.push(p);
      const x = p % W;
      const nb = [x > 0 ? p - 1 : -1, x < W - 1 ? p + 1 : -1, p - W, p + W];
      for (const q of nb) {
        if (q >= 0 && q < n && mask[q] && !seen[q]) { seen[q] = 1; stack[sp++] = q; }
      }
    }
    if (size < minSize) for (const p of comp) mask[p] = 0;
  }
}

/** Смягчить край маски, чтобы вырезанная вещь не выглядела «лесенкой». */
export function feather(mask, W, H) {
  const out = new Uint8ClampedArray(mask);
  for (let y = 1; y < H - 1; y++) {
    for (let x = 1; x < W - 1; x++) {
      const p = y * W + x;
      const m = mask[p];
      if (m === mask[p - 1] && m === mask[p + 1] && m === mask[p - W] && m === mask[p + W]) continue;
      let s = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) s += mask[p + dy * W + dx];
      out[p] = Math.min(m, s / 9);
    }
  }
  return out;
}

/** Рамка непрозрачной части: {x, y, w, h} или null, если всё прозрачно. */
export function opaqueBounds(mask, W, H, threshold = 12) {
  let minX = W, minY = H, maxX = -1, maxY = -1;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if (mask[y * W + x] > threshold) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  if (maxX < 0) return null;
  return { x: minX, y: minY, w: maxX - minX + 1, h: maxY - minY + 1 };
}

/** Подсказка цвета: самые частые цвета палитры среди непрозрачных пикселей. */
export function suggestColors(img, mask) {
  const { data: d } = img;
  const palette = COLORS.filter((c) => c.id !== 'multi').map((c) => ({
    id: c.id,
    rgb: [1, 3, 5].map((k) => parseInt(c.hex.slice(k, k + 2), 16)),
  }));
  const counts = new Map();
  let total = 0;
  const step = Math.max(1, Math.floor(mask.length / 40000));
  for (let p = 0; p < mask.length; p += step) {
    if (mask[p] < 200) continue;
    const i = p * 4;
    let best = null, bd = Infinity;
    for (const c of palette) {
      const dd = dist(d[i], d[i + 1], d[i + 2], ...c.rgb);
      if (dd < bd) { bd = dd; best = c.id; }
    }
    counts.set(best, (counts.get(best) ?? 0) + 1);
    total++;
  }
  if (!total) return [];
  const sorted = [...counts].sort((a, b) => b[1] - a[1]);
  const res = sorted.filter(([, n]) => n / total > 0.2).slice(0, 2).map(([id]) => id);
  return res.length ? res : [sorted[0][0]];
}
