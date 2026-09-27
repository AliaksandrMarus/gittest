import { html, plural, uid, isoDate, fmtDate } from '../util.js';
import { SEASONS, seasonById } from '../constants.js';
import { state, imgURL, wearStats, saveOutfit, deleteOutfit, duplicateOutfit, planOutfit, saveLookbook, deleteLookbook } from '../store.js';
import { icon, outfitCard, emptyState, actionSheet, confirmDialog, promptDialog, toast, pickDate, pickOutfit, itemCard, openSheet } from '../ui.js';
import { outfitItemIds } from '../outfit-tools.js';
import { go, goBack, refresh } from '../router.js';

const ui = { tab: 'outfits', filter: 'all' };

export function outfitsView(root) {
  const outfits = [...state.outfits.values()].sort((a, b) => b.createdAt - a.createdAt);
  const lookbooks = [...state.lookbooks.values()].sort((a, b) => b.createdAt - a.createdAt);
  const list = outfits.filter((o) => ui.filter === 'all' || (ui.filter === 'fav' ? o.favorite : o.seasons?.includes(ui.filter)));

  root.innerHTML = String(html`
    <header class="bar top">
      <div class="bar-title"><h1>Образы</h1>
        <p class="sub">${outfits.length} ${plural(outfits.length, 'образ', 'образа', 'образов')} · ${lookbooks.length} ${plural(lookbooks.length, 'лукбук', 'лукбука', 'лукбуков')}</p></div>
      <div class="bar-actions">
        <a class="icon-btn" href="#/builder?shuffle=1" aria-label="Случайный образ" title="Случайный образ">${icon('shuffle')}</a>
      </div>
    </header>
    <div class="segmented">
      <button class="${ui.tab === 'outfits' ? 'on' : ''}" data-tab="outfits">Образы</button>
      <button class="${ui.tab === 'lookbooks' ? 'on' : ''}" data-tab="lookbooks">Лукбуки</button>
    </div>
    ${ui.tab === 'outfits'
      ? html`
        ${outfits.length ? html`<div class="chips scroll">
          <button class="chip ${ui.filter === 'all' ? 'on' : ''}" data-filter="all">Все</button>
          <button class="chip ${ui.filter === 'fav' ? 'on' : ''}" data-filter="fav">${icon('heart', 'sm')} Избранные</button>
          ${SEASONS.map((s) => html`<button class="chip ${ui.filter === s.id ? 'on' : ''}" data-filter="${s.id}">${s.name}</button>`)}
        </div>` : ''}
        ${list.length
          ? html`<div class="ogrid">${list.map((o) => outfitCard(o))}</div>`
          : outfits.length
            ? emptyState('outfits', 'Нет подходящих образов', 'Попробуйте другой фильтр.')
            : emptyState('outfits', 'Образов пока нет', state.items.size ? 'Соберите образ из своих вещей или доверьтесь случаю.' : 'Сначала добавьте несколько вещей в гардероб.',
                state.items.size ? html`<div class="btn-row center"><a class="btn primary" href="#/builder">${icon('plus')} Собрать</a><a class="btn" href="#/builder?shuffle=1">${icon('shuffle')} Случайный</a></div>` : html`<a class="btn primary" href="#/closet">В гардероб</a>`)}`
      : lookbooks.length
        ? html`<div class="lb-list">${lookbooks.map((lb) => lookbookCard(lb))}</div>`
        : emptyState('book', 'Лукбуков пока нет', 'Лукбук — подборка образов: «Отпуск», «Офис», «Капсула на осень».')}
    <button class="fab" data-act="add" aria-label="${ui.tab === 'outfits' ? 'Новый образ' : 'Новый лукбук'}">${icon('plus')}</button>`);

  root.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-tab],[data-filter],[data-act]');
    if (!t) return;
    if (t.dataset.tab) { ui.tab = t.dataset.tab; refresh(); }
    else if (t.dataset.filter) { ui.filter = t.dataset.filter; refresh(); }
    else if (t.dataset.act === 'add') {
      if (ui.tab === 'outfits') go('/builder');
      else {
        const name = await promptDialog('Новый лукбук', '', { placeholder: 'Например, «Отпуск в Грузии»', ok: 'Создать' });
        if (name) {
          const lb = await saveLookbook({ id: uid(), name, outfitIds: [] });
          go(`/lookbook/${lb.id}`);
        }
      }
    }
  });
}

function lookbookCard(lb) {
  const covers = lb.outfitIds.map((id) => state.outfits.get(id)).filter(Boolean).slice(0, 4);
  return html`<a class="lb-card" href="#/lookbook/${lb.id}">
    <div class="lb-cover n${covers.length}">${covers.map((o) => html`<img src="${imgURL(o.preview)}" alt="" loading="lazy">`)}${covers.length ? '' : icon('book', 'big')}</div>
    <div class="lb-meta"><b>${lb.name}</b><span>${lb.outfitIds.length} ${plural(lb.outfitIds.length, 'образ', 'образа', 'образов')}</span></div>
  </a>`;
}

// ─── Страница образа ─────────────────────────────────────────────────────────
export function outfitView(root, [id]) {
  const o = state.outfits.get(id);
  if (!o) {
    root.innerHTML = String(emptyState('outfits', 'Образ не найден', ''));
    return;
  }
  const items = outfitItemIds(o).map((i) => state.items.get(i)).filter(Boolean);
  const w = wearStats().outfits.get(id);
  const upcoming = [...state.plans.values()].filter((p) => p.outfitId === id && p.date > isoDate()).sort((a, b) => a.date.localeCompare(b.date));
  const inBooks = [...state.lookbooks.values()].filter((lb) => lb.outfitIds.includes(id));

  root.innerHTML = String(html`
    <header class="bar">
      <button class="icon-btn" data-act="back" aria-label="Назад">${icon('back')}</button>
      <h2 class="ellipsis">${o.name || 'Образ'}</h2>
      <div class="bar-actions">
        <button class="icon-btn ${o.favorite ? 'fav-on' : ''}" data-act="fav" aria-label="Избранное">${icon('heart')}</button>
        <button class="icon-btn" data-act="more" aria-label="Ещё">${icon('more')}</button>
      </div>
    </header>
    <div class="outfit-hero"><img src="${imgURL(o.preview)}" alt=""></div>
    <div class="page">
      <div class="stats-row">
        <div class="stat"><b>${items.length}</b><span>${plural(items.length, 'вещь', 'вещи', 'вещей')}</span></div>
        <div class="stat"><b>${w?.count ?? 0}</b><span>${plural(w?.count ?? 0, 'выход', 'выхода', 'выходов')}</span></div>
        <div class="stat"><b>${w?.last ? fmtDate(w.last, { day: 'numeric', month: 'short' }) : '—'}</b><span>последний раз</span></div>
      </div>
      <div class="btn-row">
        <button class="btn primary" data-act="wear">${icon('check')} Надеть сегодня</button>
        <button class="btn" data-act="plan">${icon('calendar')} Запланировать</button>
      </div>
      <div class="btn-row">
        <a class="btn" href="#/builder/${o.id}">${icon('edit')} Изменить</a>
        <button class="btn" data-act="lookbook">${icon('book')} В лукбук</button>
      </div>
      ${o.seasons?.length || inBooks.length ? html`<div class="chips wrap static">
        ${(o.seasons ?? []).map((s) => html`<span class="chip">${seasonById[s]?.name}</span>`)}
        ${inBooks.map((lb) => html`<a class="chip" href="#/lookbook/${lb.id}">${icon('book', 'sm')} ${lb.name}</a>`)}
      </div>` : ''}
      ${upcoming.length ? html`<p class="muted">Запланирован: ${upcoming.map((p) => fmtDate(p.date)).join(', ')}</p>` : ''}
      <h3 class="section-title">Вещи в образе</h3>
      <div class="grid">${items.map((i) => itemCard(i))}</div>
    </div>`);

  root.addEventListener('click', async (e) => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'back') goBack('/outfits');
    else if (act === 'fav') saveOutfit({ ...o, favorite: !o.favorite });
    else if (act === 'wear') { await planOutfit(isoDate(), id); toast('Записано в календарь на сегодня'); }
    else if (act === 'plan') {
      const d = await pickDate('На какой день?', isoDate());
      if (d) { await planOutfit(d, id); toast(`Запланировано на ${fmtDate(d)}`); }
    } else if (act === 'lookbook') addToLookbook(id);
    else if (act === 'more') {
      actionSheet([
        { label: 'Переименовать', icon: 'edit', run: async () => {
          const name = await promptDialog('Название образа', o.name, { placeholder: 'Например, «Пятница в офисе»' });
          if (name != null) saveOutfit({ ...o, name });
        } },
        { label: 'Сезоны', icon: 'sun', run: () => editSeasons(o) },
        { label: 'Дублировать', icon: 'copy', run: async () => { const c = await duplicateOutfit(id); go(`/outfit/${c.id}`); } },
        { label: 'Сохранить картинку', icon: 'download', run: () => shareImage(o) },
        { label: 'Удалить', icon: 'trash', danger: true, run: async () => {
          if (await confirmDialog('Удалить образ? Записи в календаре сохранятся как набор вещей.')) {
            await deleteOutfit(id);
            toast('Образ удалён');
            goBack('/outfits');
          }
        } },
      ]);
    }
  });
}

function editSeasons(o) {
  const sel = new Set(o.seasons ?? []);
  const s = openSheet({
    title: 'Сезоны образа',
    className: 'compact',
    body: html`<div class="chips wrap">${SEASONS.map((x) => html`<button class="chip ${sel.has(x.id) ? 'on' : ''}" data-s="${x.id}">${x.name}</button>`)}</div>
      <div class="sheet-footer"><button class="btn primary block" data-done>Сохранить</button></div>`,
  });
  s.body.addEventListener('click', (e) => {
    const b = e.target.closest('[data-s]');
    if (b) { sel.has(b.dataset.s) ? sel.delete(b.dataset.s) : sel.add(b.dataset.s); b.classList.toggle('on'); }
    if (e.target.closest('[data-done]')) { saveOutfit({ ...o, seasons: [...sel] }); s.close(); }
  });
}

async function shareImage(o) {
  const ext = o.preview.type.split('/')[1] || 'jpg';
  const file = new File([o.preview], `${o.name || 'образ'}.${ext}`, { type: o.preview.type });
  if (navigator.canShare?.({ files: [file] })) {
    try { await navigator.share({ files: [file] }); } catch { /* пользователь закрыл меню */ }
    return;
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(file);
  a.download = file.name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

function addToLookbook(outfitId) {
  const books = [...state.lookbooks.values()];
  actionSheet([
    ...books.map((lb) => ({
      label: lb.outfitIds.includes(outfitId) ? `${lb.name} ✓` : lb.name,
      icon: 'book',
      run: async () => {
        if (lb.outfitIds.includes(outfitId)) return toast('Уже в этом лукбуке');
        await saveLookbook({ ...lb, outfitIds: [...lb.outfitIds, outfitId] });
        toast(`Добавлено в «${lb.name}»`);
      },
    })),
    { label: 'Новый лукбук…', icon: 'plus', run: async () => {
      const name = await promptDialog('Новый лукбук', '', { ok: 'Создать' });
      if (name) { await saveLookbook({ id: uid(), name, outfitIds: [outfitId] }); toast(`Добавлено в «${name}»`); }
    } },
  ], 'Добавить в лукбук');
}

// ─── Лукбук ──────────────────────────────────────────────────────────────────
export function lookbookView(root, [id]) {
  const lb = state.lookbooks.get(id);
  if (!lb) {
    root.innerHTML = String(emptyState('book', 'Лукбук не найден', ''));
    return;
  }
  const outfits = lb.outfitIds.map((x) => state.outfits.get(x)).filter(Boolean);
  root.innerHTML = String(html`
    <header class="bar">
      <button class="icon-btn" data-act="back" aria-label="Назад">${icon('back')}</button>
      <h2 class="ellipsis">${lb.name}</h2>
      <div class="bar-actions"><button class="icon-btn" data-act="more" aria-label="Ещё">${icon('more')}</button></div>
    </header>
    <div class="page">
      <p class="sub">${outfits.length} ${plural(outfits.length, 'образ', 'образа', 'образов')}</p>
      ${outfits.length
        ? html`<div class="ogrid">${outfits.map((o) => outfitCard(o, { extra: html`<button class="card-remove" data-remove="${o.id}" aria-label="Убрать из лукбука">${icon('close')}</button>` }))}</div>`
        : emptyState('book', 'Пусто', 'Добавьте сюда образы.')}
    </div>
    <button class="fab" data-act="add" aria-label="Добавить образы">${icon('plus')}</button>`);

  root.addEventListener('click', async (e) => {
    const rm = e.target.closest('[data-remove]');
    if (rm) {
      e.preventDefault();
      await saveLookbook({ ...lb, outfitIds: lb.outfitIds.filter((x) => x !== rm.dataset.remove) });
      return;
    }
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'back') goBack('/outfits');
    else if (act === 'add') {
      const ids = await pickOutfit({ title: 'Добавить образы', multiple: true, exclude: lb.outfitIds });
      if (ids?.length) saveLookbook({ ...lb, outfitIds: [...lb.outfitIds, ...ids] });
    } else if (act === 'more') {
      actionSheet([
        { label: 'Переименовать', icon: 'edit', run: async () => {
          const name = await promptDialog('Название лукбука', lb.name);
          if (name) saveLookbook({ ...lb, name });
        } },
        { label: 'Удалить лукбук', icon: 'trash', danger: true, run: async () => {
          if (await confirmDialog('Удалить лукбук? Сами образы останутся.')) { await deleteLookbook(id); goBack('/outfits'); }
        } },
      ]);
    }
  });
}
