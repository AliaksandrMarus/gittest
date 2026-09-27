import { html, isoDate, parseISO, fmtDate, plural } from '../util.js';
import { state, imgURL, setPlan, deletePlan, planOutfit } from '../store.js';
import { icon, pickItems, pickOutfit, itemCard, confirmDialog, toast } from '../ui.js';
import { go, refresh } from '../router.js';

const ui = { month: null, selected: null };
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

function planThumb(plan) {
  const o = plan.outfitId && state.outfits.get(plan.outfitId);
  if (o) return imgURL(o.preview);
  const it = plan.itemIds.map((id) => state.items.get(id)).find(Boolean);
  return it ? imgURL(it.thumb || it.image) : '';
}

export function calendarView(root, _params, query) {
  const today = isoDate();
  const d = query.get('d');
  if (d) {
    ui.selected = d;
    ui.month = parseISO(d);
  }
  ui.selected ??= today;
  const base = ui.month ?? new Date();
  const y = base.getFullYear(), m = base.getMonth();
  const first = new Date(y, m, 1);
  const offset = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const cells = Math.ceil((offset + daysInMonth) / 7) * 7;

  const days = [];
  for (let i = 0; i < cells; i++) {
    const date = new Date(y, m, i - offset + 1);
    const iso = isoDate(date);
    const plan = state.plans.get(iso);
    const thumb = plan ? planThumb(plan) : '';
    days.push(html`<button class="day ${date.getMonth() !== m ? 'out' : ''} ${iso === today ? 'today' : ''} ${iso === ui.selected ? 'sel' : ''} ${plan ? (iso > today ? 'planned' : 'worn') : ''}" data-date="${iso}">
      <span class="num">${date.getDate()}</span>
      ${thumb ? html`<img src="${thumb}" alt="" loading="lazy">` : plan ? html`<i class="dot"></i>` : ''}
    </button>`);
  }

  const monthPlans = [...state.plans.values()].filter((p) => p.date.startsWith(`${y}-${String(m + 1).padStart(2, '0')}`) && p.date <= today);
  const title = first.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });

  root.innerHTML = String(html`
    <header class="bar top">
      <div class="bar-title"><h1>Календарь</h1>
        <p class="sub">${monthPlans.length ? `${monthPlans.length} ${plural(monthPlans.length, 'день', 'дня', 'дней')} с записью в этом месяце` : 'Отмечайте, что надели, и планируйте образы'}</p></div>
      <div class="bar-actions"><button class="btn sm" data-act="today">Сегодня</button></div>
    </header>
    <div class="cal">
      <div class="cal-head">
        <button class="icon-btn" data-act="prev" aria-label="Предыдущий месяц">${icon('chevronL')}</button>
        <b class="cap">${title}</b>
        <button class="icon-btn" data-act="next" aria-label="Следующий месяц">${icon('chevronR')}</button>
      </div>
      <div class="cal-grid">${WEEKDAYS.map((w) => html`<span class="wd">${w}</span>`)}${days}</div>
    </div>
    <section class="day-panel"></section>`);

  drawDay(root.querySelector('.day-panel'));

  root.addEventListener('click', async (e) => {
    const day = e.target.closest('[data-date]');
    if (day) {
      ui.selected = day.dataset.date;
      if (parseISO(ui.selected).getMonth() !== m) ui.month = parseISO(ui.selected);
      if (query.get('d')) history.replaceState(null, '', '#/calendar');
      refresh();
      return;
    }
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'prev' || act === 'next') {
      ui.month = new Date(y, m + (act === 'next' ? 1 : -1), 1);
      if (query.get('d')) history.replaceState(null, '', '#/calendar');
      refresh();
    } else if (act === 'today') {
      ui.month = null;
      ui.selected = today;
      if (query.get('d')) history.replaceState(null, '', '#/calendar');
      refresh();
    } else handleDayAction(act);
  });

  root.addEventListener('change', (e) => {
    if (e.target.name === 'note') setPlan(ui.selected, { note: e.target.value.trim() });
  });
}

function drawDay(panel) {
  const date = ui.selected;
  const today = isoDate();
  const plan = state.plans.get(date);
  const outfit = plan?.outfitId && state.outfits.get(plan.outfitId);
  const items = (plan?.itemIds ?? []).map((id) => state.items.get(id)).filter(Boolean);
  const label = date === today ? 'Сегодня' : fmtDate(date, { weekday: 'long', day: 'numeric', month: 'long' });
  const status = !plan ? '' : date > today ? 'Запланировано' : 'Надето';

  panel.innerHTML = String(html`
    <div class="day-head"><h2 class="cap">${label}</h2>${status ? html`<span class="badge ${date > today ? 'planned' : 'worn'}">${status}</span>` : ''}</div>
    ${outfit ? html`<a class="day-outfit" href="#/outfit/${outfit.id}"><img src="${imgURL(outfit.preview)}" alt=""><span>${outfit.name || 'Образ'}</span></a>` : ''}
    ${items.length ? html`<div class="grid small">${items.map((i) => itemCard(i))}</div>` : ''}
    ${!plan ? html`<p class="muted">${date > today ? 'Спланируйте, что наденете.' : 'Отметьте, что было надето — так посчитается статистика носки.'}</p>` : ''}
    <div class="btn-row wrap">
      <button class="btn" data-act="choose-outfit">${icon('outfits')} ${outfit ? 'Другой образ' : 'Выбрать образ'}</button>
      <button class="btn" data-act="choose-items">${icon('hanger')} ${items.length ? 'Изменить вещи' : 'Выбрать вещи'}</button>
      <button class="btn" data-act="new-outfit">${icon('plus')} Собрать образ</button>
      ${plan ? html`<button class="btn danger-text" data-act="clear-day">${icon('trash')} Очистить день</button>` : ''}
    </div>
    ${plan || state.items.size ? html`<label class="field"><span class="label">Заметка</span><textarea class="input" name="note" rows="2" placeholder="Куда шли, погода, впечатления…">${plan?.note ?? ''}</textarea></label>` : ''}`);
}

async function handleDayAction(act) {
  const date = ui.selected;
  const plan = state.plans.get(date);
  if (act === 'choose-outfit') {
    const id = await pickOutfit();
    if (id) await planOutfit(date, id);
  } else if (act === 'choose-items') {
    const ids = await pickItems({ selected: plan?.itemIds ?? [] });
    if (ids) await setPlan(date, { itemIds: ids, outfitId: ids.length ? plan?.outfitId ?? null : null });
  } else if (act === 'new-outfit') go(`/builder?date=${date}`);
  else if (act === 'clear-day') {
    if (await confirmDialog('Очистить запись этого дня?', { ok: 'Очистить' })) {
      await deletePlan(date);
      toast('Запись удалена');
    }
  }
}
