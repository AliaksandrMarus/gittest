/**
 * Погода из Open-Meteo (бесплатно, без ключа). Прогноз кэшируется на час;
 * без интернета стилист работает только по сезону.
 */
import { state, saveSettings } from './store.js';
import { isoDate } from './util.js';

export const DEFAULT_CITY = { name: 'Бобруйск', lat: 53.1384, lon: 29.2214 };
export const city = () => state.settings.city ?? DEFAULT_CITY;

const TTL = 60 * 60 * 1000;
let memo = null;

const CODES = [
  [[0], 'ясно'],
  [[1, 2], 'переменная облачность'],
  [[3], 'пасмурно'],
  [[45, 48], 'туман'],
  [[51, 53, 55, 56, 57], 'морось'],
  [[61, 63, 65, 66, 67], 'дождь'],
  [[71, 73, 75, 77], 'снег'],
  [[80, 81, 82], 'ливень'],
  [[85, 86], 'снегопад'],
  [[95, 96, 99], 'гроза'],
];
const RAINY = new Set([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]);
const SNOWY = new Set([71, 73, 75, 77, 85, 86]);

export const describeCode = (code) => CODES.find(([list]) => list.includes(code))?.[1] ?? '';

function readCache() {
  try {
    return JSON.parse(localStorage.getItem('fits-weather') || 'null');
  } catch {
    return null;
  }
}

function writeCache(v) {
  try {
    localStorage.setItem('fits-weather', JSON.stringify(v));
  } catch { /* приватный режим — просто без кэша */ }
}

/** { days: { 'YYYY-MM-DD': {...} } } или null, если прогноз недоступен. */
export async function getForecast() {
  const c = city();
  const key = `${c.lat},${c.lon}`;
  const fresh = (v) => v && v.key === key && Date.now() - v.at < TTL && v.days[isoDate()];
  if (fresh(memo)) return memo;
  const cached = readCache();
  if (fresh(cached)) return (memo = cached);
  const url = 'https://api.open-meteo.com/v1/forecast?' + new URLSearchParams({
    latitude: c.lat, longitude: c.lon, timezone: 'auto', forecast_days: 3,
    daily: 'weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_probability_max,wind_speed_10m_max',
  });
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(res.status);
    const d = (await res.json()).daily;
    const days = {};
    d.time.forEach((date, i) => {
      const code = d.weather_code[i];
      days[date] = {
        date, code,
        text: describeCode(code),
        tmax: Math.round(d.temperature_2m_max[i]),
        tmin: Math.round(d.temperature_2m_min[i]),
        feelsMax: Math.round(d.apparent_temperature_max[i]),
        feelsMin: Math.round(d.apparent_temperature_min[i]),
        rain: d.precipitation_probability_max[i] ?? 0,
        wind: Math.round(d.wind_speed_10m_max[i] ?? 0),
        rainy: RAINY.has(code) || (d.precipitation_probability_max[i] ?? 0) >= 50,
        snowy: SNOWY.has(code),
      };
    });
    memo = { key, at: Date.now(), days };
    writeCache(memo);
    return memo;
  } catch (e) {
    console.warn('Погода недоступна', e);
    // Лучше вчерашний прогноз, чем никакого
    return cached?.key === key ? cached : null;
  }
}

export async function searchCity(q) {
  const url = 'https://geocoding-api.open-meteo.com/v1/search?' + new URLSearchParams({ name: q, count: 6, language: 'ru', format: 'json' });
  const res = await fetch(url);
  if (!res.ok) throw new Error('Поиск города недоступен');
  const data = await res.json();
  return (data.results ?? []).map((r) => ({
    name: r.name, lat: r.latitude, lon: r.longitude,
    region: [r.admin1, r.country].filter(Boolean).join(', '),
  }));
}

export async function setCity(c) {
  memo = null;
  await saveSettings({ city: { name: c.name, lat: c.lat, lon: c.lon } });
}

export const signed = (t) => (t > 0 ? `+${t}` : `${t}`);
export const weatherLine = (w) =>
  `${signed(w.tmin)}…${signed(w.tmax)}°, ${w.text}${w.rain >= 30 ? `, осадки ${w.rain}%` : ''}`;
