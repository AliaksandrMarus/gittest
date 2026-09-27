/**
 * Чат-стилист на Claude. Запросы идут прямо из браузера с ключом пользователя
 * (ключ хранится только на этом устройстве). Модели отправляется текстовое
 * описание гардероба — без фотографий, так дешевле.
 */
import { state, saveSettings, wearStats } from './store.js';
import { catById, colorById, seasonById } from './constants.js';
import { isoDate, fmtDate, plural } from './util.js';
import { city, weatherLine } from './weather.js';

// Цены за миллион токенов, $ (вход / выход)
export const AI_CHAT_MODELS = {
  'claude-haiku-4-5': { name: 'Haiku 4.5', note: 'дешевле', input: 1, output: 5 },
  'claude-sonnet-5': { name: 'Sonnet 5', note: 'умнее, примерно вдвое дороже', input: 2, output: 10 },
};
export const chatModel = () => (AI_CHAT_MODELS[state.settings.aiChatModel] ? state.settings.aiChatModel : 'claude-haiku-4-5');

let lib;
const load = async () => (lib ??= await import('../vendor/anthropic-sdk.js'));

const SYSTEM = `Ты — личный стилист владельца гардероба. Отвечай по-русски, коротко и дружелюбно, без канцелярита.

Правила:
- Собирай образы ТОЛЬКО из вещей гардероба ниже; ссылайся на них по id (например, v12). Не выдумывай id.
- Полный образ обычно: верх + низ (или платье) + обувь; при прохладе или осадках — верхняя одежда. Учитывай погоду, сезон вещей, сочетание цветов и повод.
- Предпочитай вещи, которые давно не надевали, если они подходят.
- Если для задачи в гардеробе чего-то не хватает, скажи об этом в reply и посоветуй, что докупить (без id).
- Если вопрос не про одежду, ответь в одну фразу и мягко верни разговор к гардеробу.
- reply — основной ответ (1–5 предложений). outfits — 0–3 образа; для каждого короткое название и почему он подходит (одно предложение).`;

const SCHEMA = {
  type: 'object',
  properties: {
    reply: { type: 'string' },
    outfits: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          item_ids: { type: 'array', items: { type: 'string' } },
          why: { type: 'string' },
        },
        required: ['title', 'item_ids', 'why'],
        additionalProperties: false,
      },
    },
  },
  required: ['reply', 'outfits'],
  additionalProperties: false,
};

/** Короткие id вместо uuid: меньше токенов. Порядок стабилен, пока гардероб не меняется. */
function wardrobe() {
  const items = [...state.items.values()].filter((i) => !i.archived).sort((a, b) => a.createdAt - b.createdAt);
  const wear = wearStats().items;
  const byShort = new Map();
  const lines = items.map((it, n) => {
    const sid = `v${n + 1}`;
    byShort.set(sid, it.id);
    const w = wear.get(it.id);
    const parts = [
      sid,
      catById[it.category]?.name,
      it.sub,
      it.name && it.name !== it.sub ? `«${it.name}»` : '',
      it.colors?.length ? it.colors.map((c) => colorById[c]?.name.toLowerCase()).join('/') : '',
      it.brand,
      it.seasons?.length ? it.seasons.map((s) => seasonById[s]?.name.toLowerCase()).join('/') : 'всесезонная',
      w ? `надевали ${w.count} р., последний ${w.last}` : 'ни разу не надевали',
      it.tags?.length ? `теги: ${it.tags.join(', ')}` : '',
      it.favorite ? 'любимая' : '',
    ];
    return parts.filter(Boolean).join(' | ');
  });
  return { text: `Гардероб (${items.length} ${plural(items.length, 'вещь', 'вещи', 'вещей')}):\n${lines.join('\n')}`, byShort };
}

function context(forecast) {
  const today = isoDate();
  const tomorrow = isoDate(new Date(Date.now() + 864e5));
  const c = city();
  const lines = [`Сегодня ${fmtDate(today, { weekday: 'long', day: 'numeric', month: 'long' })}. Город: ${c.name}.`];
  const d0 = forecast?.days[today], d1 = forecast?.days[tomorrow];
  if (d0) lines.push(`Погода сегодня: ${weatherLine(d0)}, ощущается ${d0.feelsMin}…${d0.feelsMax}°, ветер до ${d0.wind} км/ч.`);
  if (d1) lines.push(`Погода завтра: ${weatherLine(d1)}, ощущается ${d1.feelsMin}…${d1.feelsMax}°.`);
  if (!d0) lines.push('Прогноз погоды недоступен.');
  return lines.join('\n');
}

function friendlyError(e, A) {
  if (e instanceof A.AuthenticationError) return 'Ключ не подошёл — проверьте его в настройках.';
  if (e instanceof A.PermissionDeniedError) return 'У ключа нет доступа к этой модели.';
  if (e instanceof A.RateLimitError) return 'Слишком много запросов подряд — подождите минуту.';
  if (e instanceof A.BadRequestError) {
    return /credit balance/i.test(e.message) ? 'На балансе Anthropic закончились деньги — пополните его в консоли.' : `Запрос отклонён: ${e.message}`;
  }
  if (e instanceof A.InternalServerError) return 'У Anthropic временные проблемы — попробуйте позже.';
  if (e instanceof A.APIConnectionError) return 'Нет связи с Anthropic — проверьте интернет.';
  if (e instanceof A.APIError) return `Ошибка API ${e.status ?? ''}: ${e.message}`;
  return e?.message || 'Не удалось получить ответ';
}

/**
 * history — массив {role, content} (content у ассистента — его JSON-ответ).
 * Возвращает { reply, outfits: [{title, itemIds, why}], costUsd, raw }.
 */
export async function askStylist(history, question, forecast) {
  const key = state.settings.aiKey;
  if (!key) throw new Error('Добавьте ключ API в настройках');
  const { Anthropic, jsonSchemaOutputFormat } = await load();
  const client = new Anthropic({ apiKey: key, dangerouslyAllowBrowser: true, maxRetries: 1 });
  const { text: wardrobeText, byShort } = wardrobe();
  const model = chatModel();
  const first = !history.length;
  const messages = [
    ...history,
    { role: 'user', content: first ? `${context(forecast)}\n\n${question}` : question },
  ];

  let res;
  try {
    res = await client.messages.parse({
      model,
      max_tokens: 2000,
      system: [
        { type: 'text', text: SYSTEM },
        { type: 'text', text: wardrobeText, cache_control: { type: 'ephemeral' } },
      ],
      messages,
      output_config: {
        format: jsonSchemaOutputFormat(SCHEMA),
        ...(model === 'claude-sonnet-5' ? { effort: 'low' } : {}),
      },
    });
  } catch (e) {
    console.error(e);
    throw new Error(friendlyError(e, Anthropic));
  }

  const costUsd = cost(model, res.usage);
  await trackSpend(costUsd);

  if (res.stop_reason === 'refusal') throw new Error('Стилист отказался отвечать на этот вопрос.');
  if (res.stop_reason === 'max_tokens') throw new Error('Ответ получился слишком длинным — спросите короче.');
  const raw = res.content.filter((b) => b.type === 'text').map((b) => b.text).join('');
  const out = res.parsed_output;
  if (!out) return { reply: raw || 'Пустой ответ', outfits: [], costUsd, raw, messages };
  const outfits = (out.outfits ?? [])
    .map((o) => ({ title: o.title, why: o.why, itemIds: o.item_ids.map((s) => byShort.get(s)).filter((id) => id && state.items.has(id)) }))
    .filter((o) => o.itemIds.length);
  return { reply: out.reply, outfits, costUsd, raw, messages };
}

function cost(model, u) {
  const p = AI_CHAT_MODELS[model];
  if (!u || !p) return 0;
  const input = (u.input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0) * 1.25 + (u.cache_read_input_tokens ?? 0) * 0.1;
  return (input * p.input + (u.output_tokens ?? 0) * p.output) / 1e6;
}

async function trackSpend(usd) {
  const month = isoDate().slice(0, 7);
  const prev = state.settings.aiSpend;
  const total = (prev?.month === month ? prev.usd : 0) + usd;
  await saveSettings({ aiSpend: { month, usd: total, count: (prev?.month === month ? prev.count ?? 0 : 0) + 1 } });
}

export const fmtUsd = (v) => (v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`);
