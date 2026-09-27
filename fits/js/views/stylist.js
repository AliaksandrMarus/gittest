import { html, isoDate, fmtDate } from '../util.js';
import { state, imgURL, wearStats, setPlan } from '../store.js';
import { icon, emptyState, toast, confirmDialog, itemLabel } from '../ui.js';
import { autoLayout } from '../outfit-tools.js';
import { suggestOutfit } from '../stylist.js';
import { getForecast, city, weatherLine, signed } from '../weather.js';
import { askStylist, fmtUsd, AI_CHAT_MODELS, chatModel } from '../ai-stylist.js';
import { go, refresh } from '../router.js';

// Живёт между перерисовками экрана
const ui = {
  day: 'today',
  suggestion: {}, // дата → { items, reasons, warnings }
  forecast: undefined,
  chat: [], // { role: 'user'|'assistant'|'error', text, outfits, cost }
  history: [], // сообщения для API
  draft: '',
  pending: false,
};

const dayDate = () => (ui.day === 'today' ? isoDate() : isoDate(new Date(Date.now() + 864e5)));
const active = () => [...state.items.values()].filter((i) => !i.archived);

function stage(itemIds, cls = '') {
  const items = itemIds.map((id) => state.items.get(id)).filter(Boolean);
  const layers = autoLayout(items).sort((a, b) => a.z - b.z);
  return html`<div class="stage static ${cls}">${layers.map((L) => {
    const it = state.items.get(L.itemId);
    return html`<img class="layer" src="${imgURL(it.image)}" alt="${itemLabel(it)}" style="left:${L.x * 100}%;top:${L.y * 100}%;width:${L.w * 100}%;z-index:${L.z};transform:translate(-50%,-50%)">`;
  })}</div>`;
}

export function stylistView(root) {
  if (!state.items.size) {
    root.innerHTML = String(html`<header class="bar top"><div class="bar-title"><h1>Стилист</h1></div></header>
      ${emptyState('sparkle', 'Пока не из чего выбирать', 'Добавьте в гардероб хотя бы верх, низ и обувь — и стилист начнёт предлагать образы.', html`<a class="btn primary" href="#/closet">В гардероб</a>`)}`);
    return;
  }
  const ck = `${city().lat},${city().lon}`;
  if (ui.forecastKey !== ck || Date.now() - (ui.forecastAt ?? 0) > 3600e3) {
    ui.forecastKey = ck;
    ui.forecastAt = Date.now();
    ui.forecast = null;
    getForecast().then((f) => { ui.forecast = f; ui.suggestion = {}; refresh(); });
  }
  const date = dayDate();
  const w = ui.forecast?.days[date] ?? null;
  ui.suggestion[date] ??= suggestOutfit(active(), { date, w, wear: wearStats().items });
  const sug = ui.suggestion[date];
  const plan = state.plans.get(date);
  const hasKey = !!state.settings.aiKey;

  root.innerHTML = String(html`
    <header class="bar top">
      <div class="bar-title"><h1>Стилист</h1><p class="sub">${city().name}</p></div>
      <div class="bar-actions"><a class="icon-btn" href="#/settings" aria-label="Настройки">${icon('gear')}</a></div>
    </header>
    <div class="segmented">
      <button class="${ui.day === 'today' ? 'on' : ''}" data-day="today">Сегодня</button>
      <button class="${ui.day === 'tomorrow' ? 'on' : ''}" data-day="tomorrow">Завтра</button>
    </div>
    <div class="page">
      <div class="weather card-box">
        ${w ? html`<div class="w-main"><b>${signed(w.tmax)}°</b><span>${w.text}</span></div>
          <div class="w-meta"><span>${signed(w.tmin)}…${signed(w.tmax)}°, ощущается ${signed(w.feelsMin)}…${signed(w.feelsMax)}°</span>
          <span>Осадки ${w.rain}% · ветер до ${w.wind} км/ч</span></div>`
          : html`<p class="muted">${ui.forecast === null ? 'Загружаю прогноз… Без интернета образ подбирается по сезону.' : 'Прогноз недоступен.'}</p>`}
      </div>

      <h3 class="section-title">Образ ${ui.day === 'today' ? 'дня' : 'на завтра'}</h3>
      ${plan ? html`<a class="card-box note link-row" href="#/calendar?d=${date}">${icon('calendar')} <span>На ${ui.day === 'today' ? 'сегодня' : 'завтра'} уже записан ${plan.outfitId ? 'образ' : 'набор вещей'} — посмотреть</span></a>` : ''}
      ${sug.items.length ? html`
        <div class="suggest">
          ${stage(sug.items.map((i) => i.id))}
          <ul class="reasons">${sug.reasons.map((r) => html`<li>${r}</li>`)}${sug.warnings.map((r) => html`<li class="warn">${r}</li>`)}</ul>
        </div>
        <div class="btn-row">
          <button class="btn" data-act="again">${icon('shuffle')} Ещё вариант</button>
          <button class="btn primary" data-act="wear">${icon('check')} ${ui.day === 'today' ? 'Надеть' : 'Запланировать'}</button>
        </div>
        <button class="btn block" data-act="edit">${icon('edit')} Изменить в конструкторе</button>`
        : html`<ul class="reasons">${sug.warnings.map((r) => html`<li class="warn">${r}</li>`)}</ul>`}

      <h3 class="section-title">Спросить стилиста ${hasKey ? html`<span class="pill">${AI_CHAT_MODELS[chatModel()].name}</span>` : ''}</h3>
      ${hasKey ? chatBlock() : html`<div class="card-box note">
        <b>ИИ-стилист на Claude</b>
        <p>Спросите «что надеть на свадьбу друга» или «собери капсулу в отпуск» — ответит образами из вашего гардероба. Нужен свой ключ API Anthropic; запрос стоит около цента. Фото не отправляются — только описания вещей.</p>
        <a class="btn" href="#/settings">${icon('gear')} Добавить ключ</a>
      </div>`}
    </div>`);

  const input = root.querySelector('.chat-input textarea');
  if (input) {
    input.addEventListener('input', () => { ui.draft = input.value; });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
  }
  root.querySelector('.chat-log')?.lastElementChild?.scrollIntoView({ block: 'nearest' });

  root.addEventListener('click', async (e) => {
    const day = e.target.closest('[data-day]')?.dataset.day;
    if (day) { ui.day = day; refresh(); return; }
    const q = e.target.closest('[data-q]')?.dataset.q;
    if (q) { ui.draft = q; send(); return; }
    const t = e.target.closest('[data-act]');
    if (!t) return;
    const act = t.dataset.act;
    if (act === 'again') {
      ui.suggestion[date] = suggestOutfit(active(), { date, w, wear: wearStats().items });
      refresh();
    } else if (act === 'wear') await wear(date, sug.items.map((i) => i.id));
    else if (act === 'edit') go(`/builder?items=${sug.items.map((i) => i.id).join(',')}&date=${date}`);
    else if (act === 'send') send();
    else if (act === 'reset-chat') { ui.chat = []; ui.history = []; refresh(); }
    else if (act === 'ai-wear') {
      const o = ui.chat[+t.dataset.msg].outfits[+t.dataset.o];
      await wear(date, o.itemIds);
    } else if (act === 'ai-edit') {
      const o = ui.chat[+t.dataset.msg].outfits[+t.dataset.o];
      go(`/builder?items=${o.itemIds.join(',')}&date=${date}`);
    }
  });
}

async function wear(date, itemIds) {
  if (state.plans.get(date) && !(await confirmDialog('На этот день уже есть запись. Заменить?', { ok: 'Заменить', danger: false }))) return;
  await setPlan(date, { itemIds, outfitId: null });
  toast(date === isoDate() ? 'Записано в календарь на сегодня' : `Запланировано на ${fmtDate(date)}`);
}

const QUICK = ['Что надеть завтра на работу?', 'Собери образ на свидание', 'Какие вещи мне стоит докупить?'];

function chatBlock() {
  return html`<div class="chat">
    ${ui.chat.length ? html`<div class="chat-log">${ui.chat.map((m, i) => message(m, i))}
      ${ui.pending ? html`<div class="msg bot typing"><span></span><span></span><span></span></div>` : ''}</div>`
      : html`<div class="chips wrap">${QUICK.map((q) => html`<button class="chip" data-q="${q}">${q}</button>`)}</div>`}
    <div class="chat-input">
      <textarea class="input" rows="1" placeholder="Спросите стилиста…" ${ui.pending ? 'disabled' : ''}>${ui.draft}</textarea>
      <button class="icon-btn send" data-act="send" aria-label="Отправить" ${ui.pending ? 'disabled' : ''}>${icon('up')}</button>
    </div>
    ${ui.chat.length ? html`<button class="text-btn small muted" data-act="reset-chat">Начать заново</button>` : ''}
  </div>`;
}

function message(m, i) {
  if (m.role === 'user') return html`<div class="msg me">${m.text}</div>`;
  if (m.role === 'error') return html`<div class="msg err">${m.text}</div>`;
  return html`<div class="msg bot">
    <p>${m.text}</p>
    ${m.outfits.map((o, k) => html`<div class="ai-outfit">
      ${stage(o.itemIds, 'mini')}
      <div class="ai-outfit-body"><b>${o.title}</b><p>${o.why}</p>
        <div class="btn-row"><button class="btn sm" data-act="ai-wear" data-msg="${i}" data-o="${k}">${icon('check')} Надеть</button>
        <button class="btn sm" data-act="ai-edit" data-msg="${i}" data-o="${k}">${icon('edit')} Изменить</button></div></div>
    </div>`)}
    ${m.cost != null ? html`<span class="cost">≈ ${fmtUsd(m.cost)}</span>` : ''}
  </div>`;
}

async function send() {
  const q = ui.draft.trim();
  if (!q || ui.pending) return;
  ui.chat.push({ role: 'user', text: q });
  ui.draft = '';
  ui.pending = true;
  refresh();
  try {
    const res = await askStylist(ui.history, q, ui.forecast);
    ui.history = [...res.messages, { role: 'assistant', content: res.raw }].slice(-12);
    // История должна начинаться с сообщения пользователя
    while (ui.history.length && ui.history[0].role !== 'user') ui.history.shift();
    ui.chat.push({ role: 'assistant', text: res.reply, outfits: res.outfits, cost: res.costUsd });
  } catch (e) {
    ui.chat.push({ role: 'error', text: e.message });
  } finally {
    ui.pending = false;
    refresh();
  }
}

