import { html, isoDate, fmtDate, plural, daysBetween } from '../util.js';
import { catById, colorById, seasonById } from '../constants.js';
import { state, imgURL, wearStats, saveItem, deleteItem, addItemsToDay } from '../store.js';
import { icon, money, itemLabel, actionSheet, confirmDialog, toast, outfitCard, pickDate } from '../ui.js';
import { editItem } from './item-editor.js';
import { goBack } from '../router.js';

export function itemView(root, [id]) {
  const item = state.items.get(id);
  if (!item) {
    root.innerHTML = '<p class="empty">Вещь не найдена</p>';
    return;
  }
  const w = wearStats().items.get(id);
  const wears = w?.count ?? 0;
  const cpw = item.price != null && wears ? item.price / wears : null;
  const outfits = [...state.outfits.values()].filter((o) => o.layers.some((l) => l.itemId === id));
  const upcoming = [...state.plans.values()].filter((p) => p.date > isoDate() && p.itemIds.includes(id)).sort((a, b) => a.date.localeCompare(b.date));
  const row = (k, v) => (v ? html`<div class="kv"><span>${k}</span><b>${v}</b></div>` : '');

  root.innerHTML = String(html`
    <header class="bar">
      <button class="icon-btn" data-act="back" aria-label="Назад">${icon('back')}</button>
      <h2 class="ellipsis">${itemLabel(item)}</h2>
      <div class="bar-actions">
        <button class="icon-btn ${item.favorite ? 'fav-on' : ''}" data-act="fav" aria-label="Избранное">${icon('heart')}</button>
        <button class="icon-btn" data-act="more" aria-label="Ещё">${icon('more')}</button>
      </div>
    </header>
    <div class="detail-hero"><img src="${imgURL(item.image)}" alt=""></div>
    <div class="page">
      <div class="title-block">
        ${item.brand ? html`<p class="eyebrow">${item.brand}</p>` : ''}
        <h1>${itemLabel(item)}</h1>
        <p class="sub">${catById[item.category]?.name}${item.sub && item.name ? ` · ${item.sub}` : ''}${item.archived ? ' · в архиве' : ''}</p>
      </div>
      <div class="stats-row">
        <div class="stat"><b>${wears}</b><span>${plural(wears, 'выход', 'выхода', 'выходов')}</span></div>
        <div class="stat"><b>${cpw != null ? money(Math.round(cpw * 100) / 100) : '—'}</b><span>цена за выход</span></div>
        <div class="stat"><b>${w?.last ? (w.last === isoDate() ? 'сегодня' : `${daysBetween(w.last, isoDate())} дн.`) : '—'}</b><span>${w?.last ? 'с последнего раза' : 'ещё не надевали'}</span></div>
      </div>
      <div class="btn-row">
        <button class="btn primary" data-act="wear">${icon('check')} Надеть сегодня</button>
        <button class="btn" data-act="plan">${icon('calendar')} Запланировать</button>
      </div>
      <a class="btn block" href="#/builder?item=${item.id}">${icon('outfits')} Собрать образ с этой вещью</a>
      <div class="card-box">
        ${row('Цвет', item.colors?.map((c) => colorById[c]?.name).filter(Boolean).join(', '))}
        ${row('Размер', item.size)}
        ${row('Цена', item.price != null ? money(item.price) : '')}
        ${row('Куплено', item.purchased ? fmtDate(item.purchased, { day: 'numeric', month: 'long', year: 'numeric' }) : '')}
        ${row('Сезон', item.seasons?.map((s) => seasonById[s]?.name).join(', '))}
        ${row('Теги', item.tags?.join(', '))}
        ${row('Добавлена', new Date(item.createdAt).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }))}
        ${item.notes ? html`<p class="notes">${item.notes}</p>` : ''}
      </div>
      ${upcoming.length ? html`<h3 class="section-title">Запланировано</h3>
        <div class="card-box">${upcoming.map((p) => html`<a class="kv link" href="#/calendar?d=${p.date}"><span>${fmtDate(p.date, { weekday: 'short', day: 'numeric', month: 'long' })}</span>${icon('chevronR', 'sm')}</a>`)}</div>` : ''}
      <h3 class="section-title">В образах · ${outfits.length}</h3>
      ${outfits.length ? html`<div class="ogrid">${outfits.map((o) => outfitCard(o))}</div>` : html`<p class="muted">Эта вещь пока не участвует ни в одном образе.</p>`}
    </div>`);

  root.addEventListener('click', async (e) => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'back') goBack('/closet');
    else if (act === 'fav') saveItem({ ...item, favorite: !item.favorite });
    else if (act === 'wear') {
      await addItemsToDay(isoDate(), [id]);
      toast('Отмечено в календаре на сегодня');
    } else if (act === 'plan') {
      const d = await pickDate('На какой день?', isoDate());
      if (d) {
        await addItemsToDay(d, [id]);
        toast(`Добавлено на ${fmtDate(d)}`);
      }
    } else if (act === 'more') {
      actionSheet([
        { label: 'Изменить', icon: 'edit', run: () => editItem({ item }) },
        { label: item.archived ? 'Вернуть из архива' : 'В архив', icon: 'archive', run: () => saveItem({ ...item, archived: !item.archived }) },
        {
          label: 'Удалить', icon: 'trash', danger: true,
          run: async () => {
            const msg = outfits.length
              ? `Удалить вещь? Она исчезнет из ${outfits.length} ${plural(outfits.length, 'образа', 'образов', 'образов')}.`
              : 'Удалить вещь?';
            if (await confirmDialog(msg)) {
              await deleteItem(id);
              toast('Вещь удалена');
              goBack('/closet');
            }
          },
        },
      ]);
    }
  });
}
