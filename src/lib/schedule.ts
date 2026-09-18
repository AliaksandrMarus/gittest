import { schedule, TZ_OFFSET_HOURS } from '../config/site';

const DAY_NAMES = [
  'воскресенье',
  'понедельник',
  'вторник',
  'среду',
  'четверг',
  'пятницу',
  'субботу',
];

/** Коды дней для openingHoursSpecification в schema.org. */
const SCHEMA_DAYS = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}

/** Текущее время в Минске, независимо от часового пояса сервера сборки. */
function nowInMinsk(now = new Date()) {
  const utc = now.getTime() + now.getTimezoneOffset() * 60_000;
  return new Date(utc + TZ_OFFSET_HOURS * 3_600_000);
}

export type OpenState = {
  open: boolean;
  /** Готовая строка для показа: «Открыто до 19:00» / «Откроется в понедельник в 09:00». */
  label: string;
};

/**
 * Считает, работает ли мойка прямо сейчас.
 * Одна и та же функция используется при сборке и в браузере,
 * поэтому серверная и клиентская строки не разъезжаются.
 */
export function getOpenState(now = new Date()): OpenState {
  const local = nowInMinsk(now);
  const day = local.getDay();
  const mins = local.getHours() * 60 + local.getMinutes();
  const today = schedule[day];

  if (today) {
    const from = toMinutes(today.open);
    const to = toMinutes(today.close);
    if (mins >= from && mins < to) {
      return { open: true, label: `Открыто до ${today.close}` };
    }
    if (mins < from) {
      return { open: false, label: `Откроется сегодня в ${today.open}` };
    }
  }

  // Ищем ближайший рабочий день вперёд.
  for (let i = 1; i <= 7; i++) {
    const idx = (day + i) % 7;
    const next = schedule[idx];
    if (!next) continue;
    const when = i === 1 ? 'завтра' : `в ${DAY_NAMES[idx]}`;
    return { open: false, label: `Откроется ${when} в ${next.open}` };
  }

  return { open: false, label: 'Уточните время по телефону' };
}

/** openingHoursSpecification для JSON-LD: одинаковые дни сводятся в одну запись. */
export function openingHoursSchema() {
  const groups = new Map<string, string[]>();
  schedule.forEach((day, i) => {
    if (!day) return;
    const key = `${day.open}-${day.close}`;
    const list = groups.get(key) ?? [];
    list.push(SCHEMA_DAYS[i]);
    groups.set(key, list);
  });

  return [...groups.entries()].map(([key, days]) => {
    const [opens, closes] = key.split('-');
    return {
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: days,
      opens,
      closes,
    };
  });
}
