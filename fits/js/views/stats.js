import { html, isoDate, daysBetween, plural, parseISO } from '../util.js';
import { CATEGORIES, COLORS } from '../constants.js';
import { state, imgURL, wearStats } from '../store.js';
import { icon, money, emptyState, itemLabel } from '../ui.js';

export function statsView(root) {
  const items = [...state.items.values()].filter((i) => !i.archived);
  const wear = wearStats().items;
  const today = isoDate();
  const cnt = (i) => wear.get(i.id)?.count ?? 0;

  if (!items.length) {
    root.innerHTML = String(html`<header class="bar top"><div class="bar-title"><h1>Статистика</h1></div></header>
      ${emptyState('chart', 'Пока нечего считать', 'Добавьте вещи и отмечайте в календаре, что надели.')}`);
    return;
  }

  const value = items.reduce((s, i) => s + (i.price ?? 0), 0);
  const priced = items.filter((i) => i.price != null).length;
  const logged = [...state.plans.values()].filter((p) => p.date <= today);
  const last30 = logged.filter((p) => daysBetween(p.date, today) < 30).length;
  const usedItems = items.filter((i) => cnt(i) > 0).length;

  const byCat = CATEGORIES.map((c) => ({ c, n: items.filter((i) => i.category === c.id).length })).filter((x) => x.n);
  const maxCat = Math.max(...byCat.map((x) => x.n));
  const colorCounts = COLORS.map((c) => ({ c, n: items.filter((i) => i.colors?.includes(c.id)).length })).filter((x) => x.n).sort((a, b) => b.n - a.n);

  const mostWorn = items.filter((i) => cnt(i)).sort((a, b) => cnt(b) - cnt(a)).slice(0, 6);
  const never = items.filter((i) => !cnt(i)).sort((a, b) => a.createdAt - b.createdAt);
  const stale = items
    .filter((i) => wear.get(i.id)?.last && daysBetween(wear.get(i.id).last, today) >= 90)
    .sort((a, b) => wear.get(a.id).last.localeCompare(wear.get(b.id).last));
  const cpw = items.filter((i) => i.price != null && cnt(i)).map((i) => ({ i, v: i.price / cnt(i) })).sort((a, b) => a.v - b.v);

  // Активность за 12 недель: сколько дней в неделю есть запись
  const weeks = [];
  const monday = parseISO(today);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  for (let w = 11; w >= 0; w--) {
    const start = new Date(monday);
    start.setDate(start.getDate() - w * 7);
    let n = 0;
    for (let k = 0; k < 7; k++) {
      const d = new Date(start);
      d.setDate(d.getDate() + k);
      const iso = isoDate(d);
      if (iso <= today && state.plans.has(iso)) n++;
    }
    weeks.push({ start, n });
  }

  const mini = (list, sub) => html`<div class="hscroll">${list.map((x) => {
    const i = x.i ?? x;
    return html`<a class="mini" href="#/item/${i.id}"><div class="mini-img"><img src="${imgURL(i.thumb || i.image)}" alt="" loading="lazy"></div><span>${sub(x)}</span></a>`;
  })}</div>`;

  root.innerHTML = String(html`
    <header class="bar top"><div class="bar-title"><h1>Статистика</h1><p class="sub">Как вы на самом деле пользуетесь гардеробом</p></div></header>
    <div class="page">
      <div class="tiles">
        <div class="tile"><b>${items.length}</b><span>${plural(items.length, 'вещь', 'вещи', 'вещей')}</span></div>
        <div class="tile"><b>${state.outfits.size}</b><span>${plural(state.outfits.size, 'образ', 'образа', 'образов')}</span></div>
        <div class="tile"><b>${money(Math.round(value))}</b><span>стоимость гардероба${priced < items.length ? ` (цена у ${priced})` : ''}</span></div>
        <div class="tile"><b>${Math.round((usedItems / items.length) * 100)}%</b><span>вещей надевали хотя бы раз</span></div>
        <div class="tile"><b>${logged.length}</b><span>${plural(logged.length, 'день', 'дня', 'дней')} в календаре</span></div>
        <div class="tile"><b>${last30}/30</b><span>дней с записью за месяц</span></div>
      </div>

      <h3 class="section-title">Активность за 12 недель</h3>
      <div class="card-box"><div class="weeks">${weeks.map((w) => html`<div class="week" title="${w.start.toLocaleDateString('ru-RU')}: ${w.n} из 7"><i style="height:${(w.n / 7) * 100}%"></i></div>`)}</div>
        <p class="muted small">Каждый столбик — неделя: сколько дней отмечено в календаре.</p></div>

      <h3 class="section-title">По категориям</h3>
      <div class="card-box bars">${byCat.map(({ c, n }) => html`<div class="bar-row"><span>${c.name}</span><div class="bar-track"><i style="width:${(n / maxCat) * 100}%"></i></div><b>${n}</b></div>`)}</div>

      ${colorCounts.length ? html`<h3 class="section-title">Цвета</h3>
        <div class="card-box"><div class="color-strip">${colorCounts.map(({ c, n }) => html`<i style="flex:${n};background:${c.hex}" title="${c.name}: ${n}"></i>`)}</div>
        <div class="color-legend">${colorCounts.slice(0, 8).map(({ c, n }) => html`<span><i style="background:${c.hex}"></i>${c.name} · ${n}</span>`)}</div></div>` : ''}

      ${mostWorn.length ? html`<h3 class="section-title">Любимчики</h3>${mini(mostWorn, (i) => `${cnt(i)} ${plural(cnt(i), 'раз', 'раза', 'раз')}`)}` : ''}

      ${cpw.length ? html`<h3 class="section-title">Лучшая цена за выход</h3>${mini(cpw.slice(0, 8), (x) => money(Math.round(x.v * 100) / 100))}` : ''}

      ${never.length ? html`<h3 class="section-title">Ни разу не надевали · ${never.length}</h3>${mini(never.slice(0, 12), (i) => itemLabel(i))}` : ''}

      ${stale.length ? html`<h3 class="section-title">Не надевали 3+ месяца · ${stale.length}</h3>
        ${mini(stale.slice(0, 12), (i) => `${daysBetween(wear.get(i.id).last, today)} дн.`)}
        <p class="muted small">${icon('archive', 'sm')} Кандидаты, чтобы отдать, продать или вспомнить о них.</p>` : ''}
    </div>`);
}
