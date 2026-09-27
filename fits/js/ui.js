import { html, raw, esc, Raw } from './util.js';
import { state, imgURL } from './store.js';
import { catById, CATEGORIES } from './constants.js';

const P = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  filter: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  heart: '<path d="M12 20s-7.5-4.6-9.4-9.3A5 5 0 0 1 12 5.8a5 5 0 0 1 9.4 4.9C19.5 15.4 12 20 12 20z"/>',
  back: '<path d="m15 18-6-6 6-6"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v5M14 11v5"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  hanger: '<path d="M12 8.5V8c0-1.3 2.2-1.6 2.2-3.3a2.2 2.2 0 0 0-4.4 0"/><path d="M12 8.5 2.8 15.6c-.8.6-.4 1.9.6 1.9h17.2c1 0 1.4-1.3.6-1.9z"/>',
  outfits: '<rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/>',
  chart: '<path d="M4 20V11M10 20V5M16 20v-6M3 20h18"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  shuffle: '<path d="M3 7h3c4.5 0 6.5 10 11 10h4M3 17h3c1.6 0 2.8-1.3 3.8-3M14.2 10c1-1.7 2.2-3 3.8-3h3M18 4l3 3-3 3M18 14l3 3-3 3"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  flip: '<path d="M12 3v18M9 7l-5 5 5 5zM15 7l5 5-5 5z"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 17-5-5-9 8"/>',
  wand: '<path d="m4 20 10.5-10.5M13 7l1.5-4 1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5z"/>',
  eraser: '<path d="M16 20H8.5l-4.8-4.8a1 1 0 0 1 0-1.4l9.6-9.6a1 1 0 0 1 1.4 0l5.6 5.6a1 1 0 0 1 0 1.4L12 20M8.5 10.5l6 6"/>',
  brush: '<path d="m14 4 6 6-7.5 7.5-6-6zM6.5 11.5 4 14c-1.5 1.5-.5 4-1 6 2-.5 4.5.5 6-1l2.5-2.5"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  ai: '<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/><path d="m9.5 14.5 1.5-5 1.5 5M10 13h2M14.5 9.5v5"/>',
  sparkle: '<path d="M11 3l1.9 5.1L18 10l-5.1 1.9L11 17l-1.9-5.1L4 10l5.1-1.9zM19 15v5M16.5 17.5h5"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
  upload: '<path d="M12 15V3M7 8l5-5 5 5M4 21h16"/>',
  book: '<path d="M4 4.5h5.5A2.5 2.5 0 0 1 12 7v13a2 2 0 0 0-2-2H4zM20 4.5h-5.5A2.5 2.5 0 0 0 12 7v13a2 2 0 0 1 2-2h6z"/>',
  more: '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
  shirt: '<path d="M8 3 3 6l2 5 3-1v11h8V10l3 1 2-5-5-3a4 4 0 0 1-8 0z"/>',
  chevronR: '<path d="m9 6 6 6-6 6"/>',
  chevronL: '<path d="m15 6-6 6 6 6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  archive: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>',
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.7-.9 1.4-1.9-.3-1 .3-2.1 1.4-2.1H17a4 4 0 0 0 4-4c0-5.5-4-10-9-10z"/><circle cx="7.5" cy="11" r="1.2"/><circle cx="10" cy="7" r="1.2"/><circle cx="15" cy="7.5" r="1.2"/>',
};

export const icon = (name, cls = '') =>
  raw(`<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] ?? ''}</svg>`);

// ─── Нижние шторки ───────────────────────────────────────────────────────────
const openSheets = [];

export function openSheet({ title = '', body = '', className = '', onClose } = {}) {
  const wrap = document.createElement('div');
  wrap.className = 'sheet-wrap';
  wrap.innerHTML = String(html`
    <div class="sheet-backdrop"></div>
    <div class="sheet ${className}" role="dialog" aria-modal="true" aria-label="${title}">
      <div class="sheet-grip"></div>
      ${title ? html`<div class="sheet-head"><h2>${title}</h2><button class="icon-btn" data-close aria-label="Закрыть">${icon('close')}</button></div>` : ''}
      <div class="sheet-body"></div>
    </div>`);
  const bodyEl = wrap.querySelector('.sheet-body');
  if (body instanceof Node) bodyEl.append(body);
  else bodyEl.innerHTML = String(body);
  document.body.append(wrap);
  openSheets.push(wrap);
  requestAnimationFrame(() => requestAnimationFrame(() => wrap.classList.add('open')));

  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    openSheets.splice(openSheets.indexOf(wrap), 1);
    wrap.classList.remove('open');
    setTimeout(() => wrap.remove(), 260);
    onClose?.();
  };
  wrap.querySelector('.sheet-backdrop').addEventListener('click', close);
  wrap.addEventListener('click', (e) => {
    if (e.target.closest('[data-close]')) close();
  });
  wrap._close = close;
  return { el: wrap.querySelector('.sheet'), body: bodyEl, close };
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && openSheets.length) openSheets[openSheets.length - 1]._close();
});

export const closeAllSheets = () => [...openSheets].forEach((w) => w._close());

export function confirmDialog(message, { ok = 'Удалить', cancel = 'Отмена', danger = true } = {}) {
  return new Promise((resolve) => {
    let result = false;
    const s = openSheet({
      className: 'compact',
      body: html`<p class="confirm-msg">${message}</p>
        <div class="btn-row"><button class="btn" data-close>${cancel}</button>
        <button class="btn ${danger ? 'danger' : 'primary'}" data-ok>${ok}</button></div>`,
      onClose: () => resolve(result),
    });
    s.body.querySelector('[data-ok]').onclick = () => {
      result = true;
      s.close();
    };
  });
}

export function promptDialog(title, value = '', { placeholder = '', ok = 'Сохранить', type = 'text' } = {}) {
  return new Promise((resolve) => {
    let result = null;
    const s = openSheet({
      title,
      className: 'compact',
      body: html`<form class="prompt-form">
        <input class="input" type="${type}" value="${value}" placeholder="${placeholder}">
        <div class="btn-row"><button type="button" class="btn" data-close>Отмена</button>
        <button class="btn primary">${ok}</button></div></form>`,
      onClose: () => resolve(result),
    });
    const input = s.body.querySelector('input');
    setTimeout(() => input.focus(), 50);
    s.body.querySelector('form').onsubmit = (e) => {
      e.preventDefault();
      result = input.value.trim();
      s.close();
    };
  });
}

/** Меню действий: [{ label, icon, danger, run }] */
export function actionSheet(actions, title = '') {
  const s = openSheet({
    title,
    className: 'compact',
    body: html`<div class="action-list">${actions.map(
      (a, i) => html`<button class="action ${a.danger ? 'danger' : ''}" data-i="${i}">${a.icon ? icon(a.icon) : ''}<span>${a.label}</span></button>`,
    )}</div>`,
  });
  s.body.addEventListener('click', (e) => {
    const b = e.target.closest('[data-i]');
    if (!b) return;
    s.close();
    actions[+b.dataset.i].run();
  });
}

let toastTimer;
export function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2400);
}

/** Затемнение со спиннером на время fn; fn(setMessage) может менять подпись. */
export async function busy(msg, fn) {
  const el = document.createElement('div');
  el.className = 'busy';
  el.innerHTML = String(html`<div class="spinner"></div><p>${msg}</p>`);
  document.body.append(el);
  const p = el.querySelector('p');
  const setMessage = (m) => { p.textContent = m; };
  await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 30)));
  try {
    return await fn(setMessage);
  } finally {
    el.remove();
  }
}

// ─── Общие куски разметки ────────────────────────────────────────────────────
export function money(n) {
  if (n == null || n === '' || Number.isNaN(+n)) return '—';
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(n)} ${state.settings.currency}`;
}

export const itemLabel = (item) => item.name || item.sub || catById[item.category]?.name || 'Вещь';

export function itemCard(item, { href = `#/item/${item.id}`, selectable = false, selected = false } = {}) {
  const inner = html`
    <div class="card-img"><img src="${imgURL(item.thumb || item.image)}" alt="" loading="lazy" decoding="async"></div>
    ${item.favorite ? html`<span class="card-fav">${icon('heart')}</span>` : ''}
    ${selectable ? html`<span class="card-check">${icon('check')}</span>` : ''}
    <div class="card-cap">${item.brand ? html`<b>${item.brand}</b> ` : ''}${itemLabel(item)}</div>`;
  return selectable
    ? html`<button type="button" class="card ${selected ? 'selected' : ''}" data-id="${item.id}">${inner}</button>`
    : html`<a class="card" href="${href}">${inner}</a>`;
}

export function outfitCard(o, { href = `#/outfit/${o.id}`, button = false, extra = '' } = {}) {
  const inner = html`<div class="ocard-img"><img src="${imgURL(o.preview)}" alt="" loading="lazy" decoding="async"></div>
    ${o.favorite ? html`<span class="card-fav">${icon('heart')}</span>` : ''}
    ${o.name ? html`<div class="card-cap">${o.name}</div>` : ''}${raw(String(extra))}`;
  return button
    ? html`<button type="button" class="ocard" data-id="${o.id}">${inner}</button>`
    : html`<a class="ocard" href="${href}">${inner}</a>`;
}

export function emptyState(ic, title, text, action = '') {
  return html`<div class="empty">${icon(ic, 'big')}<h3>${title}</h3><p>${text}</p>${action}</div>`;
}

export function catChips(active, counts, { all = true } = {}) {
  const chips = [];
  if (all) chips.push(html`<button class="chip ${active === 'all' ? 'on' : ''}" data-cat="all">Все${counts ? html` <i>${counts.all ?? 0}</i>` : ''}</button>`);
  for (const c of CATEGORIES) {
    if (counts && !counts[c.id] && active !== c.id) continue;
    chips.push(html`<button class="chip ${active === c.id ? 'on' : ''}" data-cat="${c.id}">${c.name}${counts ? html` <i>${counts[c.id] ?? 0}</i>` : ''}</button>`);
  }
  return html`<div class="chips scroll">${chips}</div>`;
}

// ─── Выбор вещей и образов ───────────────────────────────────────────────────
export function pickItems({ title = 'Выберите вещи', selected = [] } = {}) {
  return new Promise((resolve) => {
    const sel = new Set(selected);
    let cat = 'all';
    let result = null;
    const s = openSheet({ title, className: 'tall', onClose: () => resolve(result) });
    const items = [...state.items.values()].filter((i) => !i.archived).sort((a, b) => b.createdAt - a.createdAt);
    const counts = { all: items.length };
    items.forEach((i) => (counts[i.category] = (counts[i.category] ?? 0) + 1));
    const draw = () => {
      const list = cat === 'all' ? items : items.filter((i) => i.category === cat);
      s.body.innerHTML = String(html`
        ${catChips(cat, counts)}
        ${list.length ? html`<div class="grid">${list.map((i) => itemCard(i, { selectable: true, selected: sel.has(i.id) }))}</div>` : emptyState('hanger', 'Пусто', 'Сначала добавьте вещи в гардероб')}
        <div class="sheet-footer"><button class="btn primary block" data-done>Готово${sel.size ? ` (${sel.size})` : ''}</button></div>`);
    };
    s.body.addEventListener('click', (e) => {
      const chip = e.target.closest('[data-cat]');
      if (chip) { cat = chip.dataset.cat; draw(); return; }
      const card = e.target.closest('.card[data-id]');
      if (card) {
        const id = card.dataset.id;
        sel.has(id) ? sel.delete(id) : sel.add(id);
        card.classList.toggle('selected', sel.has(id));
        s.body.querySelector('[data-done]').textContent = `Готово${sel.size ? ` (${sel.size})` : ''}`;
        return;
      }
      if (e.target.closest('[data-done]')) { result = [...sel]; s.close(); }
    });
    draw();
  });
}

export function pickOutfit({ title = 'Выберите образ', multiple = false, exclude = [] } = {}) {
  return new Promise((resolve) => {
    let result = null;
    const sel = new Set();
    const list = [...state.outfits.values()].filter((o) => !exclude.includes(o.id)).sort((a, b) => b.createdAt - a.createdAt);
    const s = openSheet({
      title,
      className: 'tall',
      onClose: () => resolve(result),
      body: list.length
        ? html`<div class="ogrid">${list.map((o) => outfitCard(o, { button: true, extra: multiple ? html`<span class="card-check">${icon('check')}</span>` : '' }))}</div>
          ${multiple ? html`<div class="sheet-footer"><button class="btn primary block" data-done>Готово</button></div>` : ''}`
        : emptyState('outfits', 'Образов пока нет', 'Соберите первый образ во вкладке «Образы»'),
    });
    s.body.addEventListener('click', (e) => {
      const card = e.target.closest('.ocard[data-id]');
      if (card) {
        if (!multiple) { result = card.dataset.id; s.close(); return; }
        const id = card.dataset.id;
        sel.has(id) ? sel.delete(id) : sel.add(id);
        card.classList.toggle('selected', sel.has(id));
        return;
      }
      if (e.target.closest('[data-done]')) { result = [...sel]; s.close(); }
    });
  });
}

export function pickDate(title = 'Выберите дату', value) {
  return promptDialog(title, value, { type: 'date', ok: 'Готово' }).then((v) => v || null);
}
