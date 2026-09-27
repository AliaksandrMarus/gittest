/**
 * Бесплатный «Образ дня» без ИИ: правила по погоде, сезону, сочетанию цветов
 * и истории носки. Каждый вызов даёт немного другой вариант.
 */
import { currentSeason, colorById } from './constants.js';
import { isoDate, parseISO, daysBetween, plural } from './util.js';
import { signed } from './weather.js';

// Ключевые слова ищутся в типе и названии вещи
const KW = {
  lightTop: ['футболк', 'майк', 'топ', 'поло'],
  warmTop: ['свитер', 'худи', 'свитшот', 'водолазк', 'кардиган', 'лонгслив', 'джемпер', 'толстовк'],
  shorts: ['шорт'],
  skirt: ['юбк'],
  sundress: ['сарафан'],
  heavyOuter: ['пуховик', 'парк', 'пальто', 'шуб', 'дублёнк', 'дубленк'],
  lightOuter: ['ветровк', 'тренч', 'бомбер', 'косух', 'пиджак', 'жакет', 'джинсовк'],
  jacket: ['куртк'],
  openShoes: ['сандал', 'шлёп', 'шлеп', 'босонож', 'сланц'],
  winterShoes: ['сапог', 'ботин', 'угги'],
  coldAcc: ['шапк', 'перчат', 'шарф', 'варежк', 'снуд'],
  sunAcc: ['очки', 'кепк', 'панам'],
};
const has = (item, key) => {
  const s = `${item.sub ?? ''} ${item.name ?? ''}`.toLowerCase();
  return KW[key].some((k) => s.includes(k));
};

const NEUTRAL = new Set(['black', 'white', 'grey', 'beige', 'navy', 'brown', 'khaki', 'silver', 'gold']);

/** Погодная «полоса» по ощущаемой дневной температуре. */
export function band(w) {
  if (!w) return null;
  const t = w.feelsMax * 0.7 + w.feelsMin * 0.3;
  if (t >= 23) return 'hot';
  if (t >= 17) return 'warm';
  if (t >= 11) return 'mild';
  if (t >= 4) return 'cool';
  return 'cold';
}

// Баллы за соответствие погоде: [hot, warm, mild, cool, cold]
const T = {
  lightTop: [3, 2, 0, -2, -4],
  warmTop: [-5, -2, 2, 3, 3],
  shorts: [3, 1, -3, -6, -6],
  skirt: [1, 1, 0, -1, -2],
  sundress: [3, 1, -2, -5, -5],
  heavyOuter: [-8, -8, -4, 1, 4],
  lightOuter: [-6, -1, 3, 1, -3],
  jacket: [-6, -2, 2, 3, 0],
  openShoes: [3, 1, -4, -8, -8],
  winterShoes: [-6, -3, 0, 2, 3],
  coldAcc: [-6, -6, -3, 1, 3],
  sunAcc: [2, 1, -3, -3, -3],
};
const BANDS = ['hot', 'warm', 'mild', 'cool', 'cold'];

function weatherScore(item, b, w) {
  if (!b) return 0;
  const i = BANDS.indexOf(b);
  let s = 0;
  for (const key of Object.keys(T)) if (has(item, key)) s += T[key][i];
  if (w?.rainy || w?.snowy) {
    if (has(item, 'openShoes')) s -= 4;
    if (has(item, 'winterShoes')) s += 1;
    if (has(item, 'sunAcc')) s -= 3;
  }
  return s;
}

const brights = (item) =>
  (item.colors ?? []).filter((c) => !NEUTRAL.has(c) && !(item.category === 'bottoms' && (c === 'blue' || c === 'lightblue')));

function colorScore(item, picked) {
  const mine = brights(item);
  const have = new Set(picked.flatMap(brights));
  if (!mine.length) return 0.5;
  if (!have.size) return 0.5;
  return mine.every((c) => have.has(c)) ? 1 : -3;
}

function freshScore(item, wear, today) {
  const w = wear.get(item.id);
  if (!w) return daysBetween(isoDate(new Date(item.createdAt)), today) > 3 ? 1.5 : 0.5;
  const d = daysBetween(w.last, today);
  if (d <= 1) return -4;
  if (d <= 3) return -1.5;
  if (d >= 14) return 1;
  return 0;
}

/**
 * items — активные вещи, w — погода на день (или null), wear — Map из wearStats().items.
 * Возвращает { items, reasons, warnings }.
 */
export function suggestOutfit(allItems, { date = isoDate(), w = null, wear = new Map() } = {}) {
  const today = date;
  const season = currentSeason(parseISO(date));
  const b = band(w);
  const picked = [];
  const reasons = [];
  const warnings = [];

  const score = (it) => {
    let s = weatherScore(it, b, w);
    if (it.seasons?.length) s += it.seasons.includes(season) ? 1.5 : -3;
    s += freshScore(it, wear, today);
    s += colorScore(it, picked);
    if (it.favorite) s += 0.5;
    return s + Math.random() * 1.5;
  };

  const pick = (cat, filter = () => true, min = -3) => {
    const pool = allItems.filter((i) => i.category === cat && filter(i) && !picked.includes(i));
    if (!pool.length) return null;
    const ranked = pool.map((i) => ({ i, s: score(i) })).sort((a, b2) => b2.s - a.s);
    const ok = ranked.filter((r) => r.s > min);
    const top = (ok.length ? ok : ranked).slice(0, 3);
    const weights = [3, 2, 1].slice(0, top.length);
    let r = Math.random() * weights.reduce((a, c) => a + c, 0);
    for (let k = 0; k < top.length; k++) {
      r -= weights[k];
      if (r <= 0) { picked.push(top[k].i); return top[k].i; }
    }
    picked.push(top[0].i);
    return top[0].i;
  };
  const count = (cat) => allItems.filter((i) => i.category === cat).length;

  // Основа: платье или верх + низ
  const dressOk = count('dresses') && (!(count('tops') && count('bottoms')) || Math.random() < 0.3);
  if (dressOk) pick('dresses');
  else {
    if (!pick('tops')) warnings.push('Добавьте в гардероб верх — футболки, рубашки, свитеры.');
    if (!pick('bottoms')) warnings.push('Добавьте в гардероб низ — брюки, джинсы, юбки.');
  }

  // Верхняя одежда
  const needOuter = b ? ['mild', 'cool', 'cold'].includes(b) || (b === 'warm' && w?.rainy) : ['autumn', 'winter'].includes(season);
  if (needOuter) {
    const o = pick('outerwear', undefined, -2);
    if (o) {
      if (b === 'cold') reasons.push(`Холодно (ощущается ${signed(w.feelsMin)}…${signed(w.feelsMax)}°) — тёплая верхняя одежда.`);
      else if (w?.rainy) reasons.push(`Осадки ${w.rain}% — возьмите «${o.sub || o.name || 'куртку'}».`);
      else if (b) reasons.push(`Прохладно, до ${signed(w.tmax)}° днём — пригодится верхний слой.`);
    } else if (b && b !== 'warm') warnings.push(`Для ${signed(w.tmax)}° нужна верхняя одежда, а её в гардеробе нет.`);
  }

  // Обувь
  if (!pick('shoes')) warnings.push('Добавьте обувь — образ будет полным.');
  else if (w?.rainy || w?.snowy) reasons.push('Обещают осадки — лучше закрытая обувь.');

  // Аксессуары по погоде и немного случайности
  if (b === 'cold' || (b === 'cool' && w?.wind >= 25)) {
    if (pick('accessories', (i) => has(i, 'coldAcc'), 0)) {
      if (Math.random() < 0.6) pick('accessories', (i) => has(i, 'coldAcc') && !picked.some((p) => p.sub && p.sub === i.sub), 0);
    }
  } else if ((b === 'hot' || b === 'warm') && w && !w.rainy && Math.random() < 0.5) {
    pick('accessories', (i) => has(i, 'sunAcc'), 0);
  } else if (Math.random() < 0.3) {
    pick('accessories', (i) => !has(i, 'coldAcc') && !has(i, 'sunAcc'), 0);
  }
  if (Math.random() < 0.4) pick('bags', undefined, 0);
  if (Math.random() < 0.25) pick('jewelry', undefined, 0);

  // Почему именно эти вещи
  if (!b) reasons.unshift(`Прогноза нет — подобрано по сезону (${{ spring: 'весна', summer: 'лето', autumn: 'осень', winter: 'зима' }[season]}).`);
  else if (b === 'hot') reasons.unshift(`Жарко, до ${signed(w.tmax)}° — лёгкие вещи.`);
  else if (b === 'warm' && !needOuter) reasons.unshift(`Тепло, ${signed(w.tmin)}…${signed(w.tmax)}° — без верхней одежды.`);
  const forgotten = picked
    .map((i) => ({ i, w: wear.get(i.id) }))
    .filter((x) => !x.w || daysBetween(x.w.last, today) >= 14)
    .sort((a, c) => (a.w?.last ?? '0').localeCompare(c.w?.last ?? '0'))[0];
  if (forgotten) {
    const name = (forgotten.i.sub || forgotten.i.name || 'эту вещь').toLowerCase();
    reasons.push(forgotten.w
      ? `${cap(name)} не надевали ${daysBetween(forgotten.w.last, today)} ${plural(daysBetween(forgotten.w.last, today), 'день', 'дня', 'дней')} — пора вспомнить.`
      : `${cap(name)} ещё ни разу не надевали — самое время.`);
  }
  const accent = [...new Set(picked.flatMap(brights))];
  if (accent.length === 1) reasons.push(`Один яркий акцент — ${colorById[accent[0]]?.name.toLowerCase()}, остальное спокойное.`);

  return { items: picked, reasons, warnings };
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
