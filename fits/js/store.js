import * as db from './db.js';
import { isoDate, uid, blobToDataURL, dataURLToBlob } from './util.js';
import { outfitItemIds, renderOutfitPreview } from './outfit-tools.js';

export const state = {
  items: new Map(),
  outfits: new Map(),
  plans: new Map(),
  lookbooks: new Map(),
  settings: { currency: 'руб.', theme: 'auto', aiBg: false, aiModel: 'small', aiSource: null, aiReady: null },
};

const listeners = new Set();
export const onChange = (fn) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

let queued = false;
let wearCache = null;
function emit() {
  wearCache = null;
  if (queued) return;
  queued = true;
  queueMicrotask(() => {
    queued = false;
    listeners.forEach((fn) => fn());
  });
}

export async function initStore() {
  const [items, outfits, plans, lookbooks, meta] = await Promise.all(db.STORES.map((s) => db.getAll(s)));
  items.forEach((x) => state.items.set(x.id, x));
  outfits.forEach((x) => state.outfits.set(x.id, x));
  plans.forEach((x) => state.plans.set(x.date, x));
  lookbooks.forEach((x) => state.lookbooks.set(x.id, x));
  const s = meta.find((m) => m.key === 'settings');
  if (s) Object.assign(state.settings, s.value);
}

export async function saveSettings(patch) {
  Object.assign(state.settings, patch);
  await db.put('meta', { key: 'settings', value: { ...state.settings } });
  emit();
}

// ─── Картинки ────────────────────────────────────────────────────────────────
const urls = new WeakMap();
/** Постоянный object URL для Blob — чтобы не плодить новые при каждой перерисовке. */
export function imgURL(blob) {
  if (!blob) return '';
  let u = urls.get(blob);
  if (!u) {
    u = URL.createObjectURL(blob);
    urls.set(blob, u);
  }
  return u;
}

// ─── Вещи ────────────────────────────────────────────────────────────────────
export async function saveItem(item) {
  item.updatedAt = Date.now();
  item.createdAt ??= item.updatedAt;
  await db.put('items', item);
  state.items.set(item.id, item);
  emit();
  navigator.storage?.persist?.().catch(() => {});
  return item;
}

export async function deleteItem(id) {
  const ops = [{ store: 'items', del: id }];
  const touchedOutfits = [];
  for (const o of state.outfits.values()) {
    if (o.layers.some((l) => l.itemId === id)) {
      touchedOutfits.push({ ...o, layers: o.layers.filter((l) => l.itemId !== id) });
    }
  }
  const touchedPlans = [];
  for (const p of state.plans.values()) {
    if (p.itemIds.includes(id)) touchedPlans.push({ ...p, itemIds: p.itemIds.filter((x) => x !== id) });
  }
  state.items.delete(id);
  for (const o of touchedOutfits) {
    o.preview = await renderOutfitPreview(o, state.items);
    ops.push({ store: 'outfits', put: o });
    state.outfits.set(o.id, o);
  }
  for (const p of touchedPlans) {
    if (!p.itemIds.length && !p.outfitId && !p.note) {
      ops.push({ store: 'plans', del: p.date });
      state.plans.delete(p.date);
    } else {
      ops.push({ store: 'plans', put: p });
      state.plans.set(p.date, p);
    }
  }
  await db.batch(ops);
  emit();
}

// ─── Образы ──────────────────────────────────────────────────────────────────
export async function saveOutfit(outfit) {
  outfit.updatedAt = Date.now();
  outfit.createdAt ??= outfit.updatedAt;
  await db.put('outfits', outfit);
  state.outfits.set(outfit.id, outfit);
  emit();
  return outfit;
}

export async function deleteOutfit(id) {
  const ops = [{ store: 'outfits', del: id }];
  state.outfits.delete(id);
  for (const p of state.plans.values()) {
    if (p.outfitId === id) {
      const np = { ...p, outfitId: null };
      ops.push({ store: 'plans', put: np });
      state.plans.set(p.date, np);
    }
  }
  for (const lb of state.lookbooks.values()) {
    if (lb.outfitIds.includes(id)) {
      const nl = { ...lb, outfitIds: lb.outfitIds.filter((x) => x !== id) };
      ops.push({ store: 'lookbooks', put: nl });
      state.lookbooks.set(lb.id, nl);
    }
  }
  await db.batch(ops);
  emit();
}

export async function duplicateOutfit(id) {
  const o = state.outfits.get(id);
  const copy = {
    ...o,
    id: uid(),
    name: o.name ? `${o.name} (копия)` : '',
    layers: o.layers.map((l) => ({ ...l, id: uid() })),
    favorite: false,
    createdAt: undefined,
  };
  return saveOutfit(copy);
}

// ─── Календарь ───────────────────────────────────────────────────────────────
/** plan: { date, outfitId|null, itemIds: [...все вещи дня], note } */
export async function setPlan(date, patch) {
  const prev = state.plans.get(date) ?? { date, outfitId: null, itemIds: [], note: '' };
  const plan = { ...prev, ...patch, date };
  if (!plan.outfitId && !plan.itemIds.length && !plan.note) return deletePlan(date);
  await db.put('plans', plan);
  state.plans.set(date, plan);
  emit();
  return plan;
}

export async function deletePlan(date) {
  await db.del('plans', date);
  state.plans.delete(date);
  emit();
}

export function planOutfit(date, outfitId) {
  const o = state.outfits.get(outfitId);
  return setPlan(date, { outfitId, itemIds: outfitItemIds(o) });
}

/** Добавить вещи к записи дня (например, «надеть сегодня» со страницы вещи). */
export function addItemsToDay(date, ids) {
  const prev = state.plans.get(date);
  const itemIds = [...new Set([...(prev?.itemIds ?? []), ...ids])];
  return setPlan(date, { itemIds });
}

/**
 * Сколько раз и когда последний раз надевали каждую вещь и образ.
 * Надетым считается всё, что записано в календарь на сегодня и раньше.
 */
export function wearStats() {
  if (wearCache) return wearCache;
  const today = isoDate();
  const items = new Map();
  const outfits = new Map();
  const bump = (map, id, date) => {
    const s = map.get(id) ?? { count: 0, last: null };
    s.count++;
    if (!s.last || date > s.last) s.last = date;
    map.set(id, s);
  };
  for (const p of state.plans.values()) {
    if (p.date > today) continue;
    p.itemIds.forEach((id) => bump(items, id, p.date));
    if (p.outfitId) bump(outfits, p.outfitId, p.date);
  }
  wearCache = { items, outfits };
  return wearCache;
}

// ─── Лукбуки ─────────────────────────────────────────────────────────────────
export async function saveLookbook(lb) {
  lb.createdAt ??= Date.now();
  await db.put('lookbooks', lb);
  state.lookbooks.set(lb.id, lb);
  emit();
  return lb;
}

export async function deleteLookbook(id) {
  await db.del('lookbooks', id);
  state.lookbooks.delete(id);
  emit();
}

// ─── Резервная копия ─────────────────────────────────────────────────────────
export async function exportBackup() {
  const conv = async (obj, keys) => {
    const out = { ...obj };
    for (const k of keys) if (obj[k] instanceof Blob) out[k] = await blobToDataURL(obj[k]);
    return out;
  };
  const items = [];
  for (const i of state.items.values()) items.push(await conv(i, ['image', 'thumb']));
  const outfits = [];
  for (const o of state.outfits.values()) outfits.push(await conv(o, ['preview']));
  return {
    app: 'fits-clone',
    version: 1,
    exportedAt: new Date().toISOString(),
    settings: state.settings,
    items,
    outfits,
    plans: [...state.plans.values()],
    lookbooks: [...state.lookbooks.values()],
  };
}

export async function importBackup(data) {
  if (data?.app !== 'fits-clone') throw new Error('Это не резервная копия Fits');
  const back = async (obj, keys) => {
    const out = { ...obj };
    for (const k of keys) if (typeof obj[k] === 'string' && obj[k].startsWith('data:')) out[k] = await dataURLToBlob(obj[k]);
    return out;
  };
  const ops = [];
  for (const i of data.items ?? []) ops.push({ store: 'items', put: await back(i, ['image', 'thumb']) });
  for (const o of data.outfits ?? []) ops.push({ store: 'outfits', put: await back(o, ['preview']) });
  for (const p of data.plans ?? []) ops.push({ store: 'plans', put: p });
  for (const l of data.lookbooks ?? []) ops.push({ store: 'lookbooks', put: l });
  if (data.settings) ops.push({ store: 'meta', put: { key: 'settings', value: { ...state.settings, ...data.settings } } });
  await db.batch(ops);
  for (const o of ops) {
    if (o.store === 'items') state.items.set(o.put.id, o.put);
    else if (o.store === 'outfits') state.outfits.set(o.put.id, o.put);
    else if (o.store === 'plans') state.plans.set(o.put.date, o.put);
    else if (o.store === 'lookbooks') state.lookbooks.set(o.put.id, o.put);
    else if (o.store === 'meta') Object.assign(state.settings, o.put.value);
  }
  emit();
  return { items: data.items?.length ?? 0, outfits: data.outfits?.length ?? 0 };
}

export async function wipeAll() {
  await db.clearAll();
  state.items.clear();
  state.outfits.clear();
  state.plans.clear();
  state.lookbooks.clear();
  emit();
}
