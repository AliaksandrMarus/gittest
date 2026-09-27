import { blobToImage, makeCanvas, encodeCanvas, uid, pickRandom } from './util.js';
import { currentSeason } from './constants.js';

/** Холст образа всегда 3:4. Координаты слоёв — доли ширины (x, w) и высоты (y). */
export const STAGE_RATIO = 4 / 3;

/**
 * Где по умолчанию лежит вещь каждой категории — как в раскладке flat lay:
 * верх над низом, обувь внизу, аксессуары по краям.
 */
const SLOTS = {
  outerwear: { x: 0.68, y: 0.28, w: 0.46, maxH: 0.42, z: 1 },
  bags: { x: 0.79, y: 0.66, w: 0.32, maxH: 0.26, z: 2 },
  bottoms: { x: 0.38, y: 0.62, w: 0.42, maxH: 0.42, z: 3 },
  dresses: { x: 0.40, y: 0.42, w: 0.52, maxH: 0.66, z: 3 },
  tops: { x: 0.36, y: 0.24, w: 0.48, maxH: 0.36, z: 4 },
  shoes: { x: 0.40, y: 0.89, w: 0.34, maxH: 0.17, z: 5 },
  accessories: { x: 0.84, y: 0.09, w: 0.22, maxH: 0.15, z: 6, dy: 0.15 },
  jewelry: { x: 0.14, y: 0.08, w: 0.16, maxH: 0.12, z: 7, dy: 0.12 },
  other: { x: 0.16, y: 0.86, w: 0.26, maxH: 0.2, z: 2, dy: -0.2 },
};

export function slotLayer(item, sameCount = 0, z) {
  const s = SLOTS[item.category] ?? SLOTS.other;
  const ar = item.ar || 1;
  let w = s.w;
  // высота слоя в долях высоты холста = w * ar / STAGE_RATIO
  if ((w * ar) / STAGE_RATIO > s.maxH) w = (s.maxH * STAGE_RATIO) / ar;
  const shift = sameCount * (s.dy ?? 0.05);
  return {
    id: uid(),
    itemId: item.id,
    x: s.dy ? s.x : s.x + shift,
    y: s.dy ? s.y + shift : s.y + shift,
    w,
    rot: 0,
    flip: false,
    z: z ?? s.z * 10 + sameCount,
  };
}

export function autoLayout(items) {
  const seen = {};
  return items.map((it) => {
    const n = seen[it.category] ?? 0;
    seen[it.category] = n + 1;
    return slotLayer(it, n);
  });
}

/**
 * Случайный образ из гардероба: платье или верх+низ, обувь,
 * иногда верхняя одежда, сумка и аксессуар. Предпочитает вещи текущего сезона.
 */
export function randomOutfit(allItems, season = currentSeason()) {
  const active = allItems.filter((i) => !i.archived);
  const inSeason = (i) => !i.seasons?.length || i.seasons.includes(season);
  const by = (cat) => {
    const all = active.filter((i) => i.category === cat);
    const seasonal = all.filter(inSeason);
    return seasonal.length ? seasonal : all;
  };
  const res = [];
  const tops = by('tops'), bottoms = by('bottoms'), dresses = by('dresses');
  const useDress = dresses.length && (!(tops.length && bottoms.length) || Math.random() < 0.35);
  if (useDress) res.push(pickRandom(dresses));
  else {
    if (tops.length) res.push(pickRandom(tops));
    if (bottoms.length) res.push(pickRandom(bottoms));
  }
  const maybe = (cat, p) => {
    const list = by(cat);
    if (list.length && Math.random() < p) res.push(pickRandom(list));
  };
  maybe('shoes', 1);
  maybe('outerwear', season === 'winter' || season === 'autumn' ? 0.85 : 0.35);
  maybe('bags', 0.45);
  maybe('accessories', 0.4);
  maybe('jewelry', 0.25);
  return res;
}

export const outfitItemIds = (outfit) => [...new Set(outfit.layers.map((l) => l.itemId))];

/** Картинка-превью образа (то же, что видно на холсте конструктора). */
export async function renderOutfitPreview(outfit, itemsMap, W = 720) {
  const H = Math.round(W * STAGE_RATIO);
  const c = makeCanvas(W, H);
  const ctx = c.getContext('2d');
  ctx.fillStyle = outfit.bg || '#ffffff';
  ctx.fillRect(0, 0, W, H);
  ctx.imageSmoothingQuality = 'high';
  const layers = [...outfit.layers].sort((a, b) => a.z - b.z);
  for (const L of layers) {
    const item = itemsMap.get(L.itemId);
    if (!item) continue;
    let img;
    try {
      img = await blobToImage(item.image);
    } catch {
      continue;
    }
    const w = L.w * W;
    const h = (w * img.naturalHeight) / img.naturalWidth;
    ctx.save();
    ctx.translate(L.x * W, L.y * H);
    ctx.rotate((L.rot * Math.PI) / 180);
    ctx.scale(L.flip ? -1 : 1, 1);
    ctx.drawImage(img, -w / 2, -h / 2, w, h);
    ctx.restore();
  }
  return encodeCanvas(c, false);
}
