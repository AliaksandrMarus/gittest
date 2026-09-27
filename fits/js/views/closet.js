import { html, plural, pickFiles, $ } from '../util.js';
import { COLORS, SEASONS, catById } from '../constants.js';
import { state, wearStats } from '../store.js';
import { icon, openSheet, itemCard, emptyState, catChips } from '../ui.js';
import { startAddItems } from './item-editor.js';
import { refresh } from '../router.js';

// Состояние экрана живёт между перерисовками
const ui = { cat: 'all', q: '', search: false, colors: new Set(), seasons: new Set(), fav: false, archived: false, sort: 'new' };

const SORTS = {
  new: ['Сначала новые', (a, b) => b.createdAt - a.createdAt],
  old: ['Сначала старые', (a, b) => a.createdAt - b.createdAt],
  most: ['Чаще носимые', null],
  least: ['Реже носимые', null],
  priceHi: ['Дороже', (a, b) => (b.price ?? -1) - (a.price ?? -1)],
  priceLo: ['Дешевле', (a, b) => (a.price ?? Infinity) - (b.price ?? Infinity)],
  brand: ['По бренду', (a, b) => (a.brand || '￿').localeCompare(b.brand || '￿', 'ru')],
};

const filtersActive = () => ui.colors.size || ui.seasons.size || ui.fav || ui.archived || ui.sort !== 'new';

function filtered() {
  const q = ui.q.trim().toLowerCase();
  const wear = wearStats().items;
  let list = [...state.items.values()].filter((i) => {
    if (!!i.archived !== ui.archived) return false;
    if (ui.cat !== 'all' && i.category !== ui.cat) return false;
    if (ui.fav && !i.favorite) return false;
    if (ui.colors.size && !i.colors?.some((c) => ui.colors.has(c))) return false;
    if (ui.seasons.size && i.seasons?.length && !i.seasons.some((s) => ui.seasons.has(s))) return false;
    if (q) {
      const hay = [i.name, i.sub, i.brand, i.size, i.notes, catById[i.category]?.name, ...(i.tags ?? []), ...(i.colors ?? []).map((c) => COLORS.find((x) => x.id === c)?.name)]
        .join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const cnt = (i) => wear.get(i.id)?.count ?? 0;
  if (ui.sort === 'most') list.sort((a, b) => cnt(b) - cnt(a) || b.createdAt - a.createdAt);
  else if (ui.sort === 'least') list.sort((a, b) => cnt(a) - cnt(b) || a.createdAt - b.createdAt);
  else list.sort(SORTS[ui.sort][1]);
  return list;
}

export function closetView(root) {
  const active = [...state.items.values()].filter((i) => !!i.archived === ui.archived);
  const counts = { all: active.length };
  active.forEach((i) => (counts[i.category] = (counts[i.category] ?? 0) + 1));
  if (ui.cat !== 'all' && !counts[ui.cat]) ui.cat = 'all';
  const total = state.items.size;

  root.innerHTML = String(html`
    <header class="bar top">
      <div class="bar-title"><h1>${ui.archived ? 'Архив' : 'Гардероб'}</h1>
        <p class="sub">${active.length} ${plural(active.length, 'вещь', 'вещи', 'вещей')}</p></div>
      <div class="bar-actions">
        <button class="icon-btn ${ui.search ? 'on' : ''}" data-act="search" aria-label="Поиск">${icon('search')}</button>
        <button class="icon-btn ${filtersActive() ? 'dot' : ''}" data-act="filter" aria-label="Фильтры">${icon('filter')}</button>
        <a class="icon-btn" href="#/settings" aria-label="Настройки">${icon('gear')}</a>
      </div>
    </header>
    ${ui.search ? html`<div class="search-row"><input class="input" type="search" placeholder="Бренд, тип, цвет, тег…" value="${ui.q}" enterkeyhint="search"></div>` : ''}
    ${total ? catChips(ui.cat, counts) : ''}
    <div class="closet-grid"></div>
    <button class="fab" data-act="add" aria-label="Добавить вещь">${icon('plus')}</button>`);

  const gridEl = $('.closet-grid', root);
  const drawGrid = () => {
    const list = filtered();
    if (!total) {
      gridEl.innerHTML = String(emptyState('hanger', 'Гардероб пуст', 'Сфотографируйте вещь на ровном фоне — фон уберётся автоматически.',
        html`<button class="btn primary" data-act="add">${icon('plus')} Добавить вещь</button>`));
    } else if (!list.length) {
      gridEl.innerHTML = String(emptyState('search', 'Ничего не нашлось', 'Измените поиск или фильтры.'));
    } else {
      gridEl.innerHTML = String(html`<div class="grid">${list.map((i) => itemCard(i))}</div>`);
    }
  };
  drawGrid();

  const search = $('.search-row input', root);
  if (search) {
    search.addEventListener('input', () => { ui.q = search.value; drawGrid(); });
    if (!ui.q) search.focus();
  }

  root.addEventListener('click', (e) => {
    const chip = e.target.closest('[data-cat]');
    if (chip) {
      ui.cat = chip.dataset.cat;
      root.querySelectorAll('.chips [data-cat]').forEach((c) => c.classList.toggle('on', c === chip));
      drawGrid();
      return;
    }
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'search') {
      ui.search = !ui.search;
      if (!ui.search) ui.q = '';
      refresh();
    } else if (act === 'filter') openFilters();
    else if (act === 'add') openAddSheet();
  });

  // Перетаскивание фото на страницу (на компьютере)
  root.addEventListener('dragover', (e) => { e.preventDefault(); root.classList.add('drop'); });
  root.addEventListener('dragleave', () => root.classList.remove('drop'));
  root.addEventListener('drop', (e) => {
    e.preventDefault();
    root.classList.remove('drop');
    const files = [...(e.dataTransfer?.files ?? [])];
    if (files.length) startAddItems(files, { category: ui.cat });
  });
}

export function openAddSheet(preset = {}) {
  const s = openSheet({
    title: 'Добавить вещь',
    className: 'compact',
    body: html`<div class="action-list">
      <button class="action" data-src="camera">${icon('camera')}<span>Сфотографировать</span></button>
      <button class="action" data-src="gallery">${icon('image')}<span>Выбрать из галереи</span></button>
    </div>
    <p class="hint">Совет: разложите вещь на однотонной поверхности, контрастной по цвету, и снимайте сверху при хорошем свете — так фон уберётся чище.</p>`,
  });
  s.body.addEventListener('click', async (e) => {
    const src = e.target.closest('[data-src]')?.dataset.src;
    if (!src) return;
    const pending = pickFiles({ capture: src === 'camera', multiple: src === 'gallery' });
    s.close();
    const files = await pending;
    if (files.length) startAddItems(files, { category: ui.cat, ...preset });
  });
}

function openFilters() {
  const s = openSheet({ title: 'Фильтры и сортировка', className: 'tall' });
  const draw = () => {
    s.body.innerHTML = String(html`
      <div class="field"><span class="label">Цвет</span>
        <div class="swatches">${COLORS.map((c) => html`<button class="swatch ${ui.colors.has(c.id) ? 'on' : ''}" data-color="${c.id}" title="${c.name}" aria-label="${c.name}" style="background:${c.hex}"></button>`)}</div></div>
      <div class="field"><span class="label">Сезон</span>
        <div class="chips wrap">${SEASONS.map((x) => html`<button class="chip ${ui.seasons.has(x.id) ? 'on' : ''}" data-season="${x.id}">${x.name}</button>`)}</div></div>
      <div class="field"><span class="label">Показать</span>
        <div class="chips wrap">
          <button class="chip ${ui.fav ? 'on' : ''}" data-toggle="fav">${icon('heart', 'sm')} Только избранное</button>
          <button class="chip ${ui.archived ? 'on' : ''}" data-toggle="archived">${icon('archive', 'sm')} Архив</button>
        </div></div>
      <div class="field"><span class="label">Сортировка</span>
        <div class="chips wrap">${Object.entries(SORTS).map(([k, [name]]) => html`<button class="chip ${ui.sort === k ? 'on' : ''}" data-sort="${k}">${name}</button>`)}</div></div>
      <div class="sheet-footer btn-row">
        <button class="btn" data-reset>Сбросить</button>
        <button class="btn primary" data-close>Показать</button>
      </div>`);
  };
  draw();
  s.body.addEventListener('click', (e) => {
    const t = e.target.closest('button');
    if (!t) return;
    const { color, season, toggle, sort } = t.dataset;
    if (color) ui.colors.has(color) ? ui.colors.delete(color) : ui.colors.add(color);
    else if (season) ui.seasons.has(season) ? ui.seasons.delete(season) : ui.seasons.add(season);
    else if (toggle) ui[toggle] = !ui[toggle];
    else if (sort) ui.sort = sort;
    else if ('reset' in t.dataset) {
      ui.colors.clear(); ui.seasons.clear(); ui.fav = false; ui.archived = false; ui.sort = 'new';
    } else return;
    draw();
    refresh();
  });
}
