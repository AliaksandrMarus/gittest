import { html, uid, clamp, fmtDate, $ } from '../util.js';
import { STAGE_BGS, currentSeason } from '../constants.js';
import { state, imgURL, saveOutfit, planOutfit } from '../store.js';
import { icon, toast, confirmDialog, openSheet, catChips, itemLabel, busy } from '../ui.js';
import { autoLayout, slotLayer, randomOutfit, renderOutfitPreview } from '../outfit-tools.js';
import { go, goBack } from '../router.js';
import { SEASONS } from '../constants.js';

/**
 * Конструктор образа: холст 3:4, вещи — слои, которые можно двигать,
 * масштабировать и вращать (пальцами, колесом мыши или ползунками).
 */
export function builderView(root, [id], query) {
  const existing = id ? state.outfits.get(id) : null;
  if (id && !existing) {
    root.innerHTML = '<p class="empty">Образ не найден</p>';
    return;
  }
  const planDate = query.get('date');
  let layers = existing ? existing.layers.map((l) => ({ ...l })) : [];
  let bg = existing?.bg ?? STAGE_BGS[0];
  let selected = null;
  let dirty = false;
  let pickerCat = 'all';
  let pickerOpen = !existing;

  const activeItems = () => [...state.items.values()].filter((i) => !i.archived);

  if (!existing) {
    const seed = query.get('item');
    const many = (query.get('items') ?? '').split(',').map((x) => state.items.get(x)).filter(Boolean);
    if (many.length) layers = autoLayout(many);
    else if (query.get('shuffle')) layers = autoLayout(randomOutfit(activeItems()));
    else if (seed && state.items.has(seed)) layers = autoLayout([state.items.get(seed)]);
    if (layers.length) dirty = true;
  }

  root.classList.add('builder');
  root.innerHTML = String(html`
    <header class="bar">
      <button class="text-btn" data-act="cancel">Отмена</button>
      <h2>${existing ? 'Изменить образ' : 'Новый образ'}</h2>
      <button class="btn primary sm" data-act="save">Сохранить</button>
    </header>
    <div class="stage-wrap"><div class="stage" style="background:${bg}"></div></div>
    <div class="layer-tools"></div>
    <div class="builder-bar">
      <button class="tool" data-act="picker">${icon('hanger')}<span>Вещи</span></button>
      <button class="tool" data-act="shuffle">${icon('shuffle')}<span>Случайно</span></button>
      <button class="tool" data-act="bg">${icon('palette')}<span>Фон</span></button>
      <button class="tool" data-act="clear">${icon('trash')}<span>Очистить</span></button>
    </div>
    <div class="picker"></div>`);

  const stage = $('.stage', root);
  const tools = $('.layer-tools', root);
  const picker = $('.picker', root);

  // ─── Отрисовка слоёв ─────────────────────────────────────────────────
  const styleOf = (L) =>
    `left:${L.x * 100}%;top:${L.y * 100}%;width:${L.w * 100}%;z-index:${Math.round(L.z)};` +
    `transform:translate(-50%,-50%) rotate(${L.rot}deg) scaleX(${L.flip ? -1 : 1})`;

  function drawStage() {
    const sorted = [...layers].sort((a, b) => a.z - b.z);
    stage.innerHTML = String(html`${sorted.map((L) => {
      const it = state.items.get(L.itemId);
      return it ? html`<img class="layer ${L.id === selected ? 'sel' : ''}" data-id="${L.id}" src="${imgURL(it.image)}" alt="" draggable="false" style="${styleOf(L)}">` : '';
    })}${layers.length ? '' : html`<div class="stage-empty">${icon('hanger', 'big')}<p>Добавьте вещи снизу</p></div>`}`);
    drawTools();
  }

  function updateLayerEl(L) {
    const el = stage.querySelector(`[data-id="${L.id}"]`);
    if (el) el.setAttribute('style', styleOf(L));
  }

  function drawTools() {
    const L = layers.find((l) => l.id === selected);
    if (!L) {
      tools.innerHTML = String(html`<p class="hint">${layers.length ? 'Нажмите на вещь, чтобы двигать её. Двумя пальцами — размер и поворот.' : ''}</p>`);
      return;
    }
    tools.innerHTML = String(html`
      <div class="toolbar compact">
        <button class="tool" data-lt="up" title="Выше">${icon('up')}</button>
        <button class="tool" data-lt="down" title="Ниже">${icon('down')}</button>
        <button class="tool" data-lt="flip" title="Отразить">${icon('flip')}</button>
        <button class="tool" data-lt="dup" title="Копия">${icon('copy')}</button>
        <button class="tool danger" data-lt="del" title="Убрать">${icon('trash')}</button>
      </div>
      <div class="sliders">
        <label class="slider"><span>Размер</span><input type="range" min="5" max="130" value="${Math.round(L.w * 100)}" data-ls="w"></label>
        <label class="slider"><span>Поворот</span><input type="range" min="-180" max="180" value="${Math.round(L.rot)}" data-ls="rot"></label>
      </div>`);
  }

  function select(lid) {
    selected = lid;
    stage.querySelectorAll('.layer').forEach((el) => el.classList.toggle('sel', el.dataset.id === lid));
    drawTools();
  }

  const change = () => { dirty = true; };

  // ─── Панель вещей ────────────────────────────────────────────────────
  function drawPicker() {
    picker.classList.toggle('open', pickerOpen);
    if (!pickerOpen) { picker.innerHTML = ''; return; }
    const items = activeItems().sort((a, b) => b.createdAt - a.createdAt);
    const counts = { all: items.length };
    items.forEach((i) => (counts[i.category] = (counts[i.category] ?? 0) + 1));
    if (pickerCat !== 'all' && !counts[pickerCat]) pickerCat = 'all';
    const list = pickerCat === 'all' ? items : items.filter((i) => i.category === pickerCat);
    const used = new Set(layers.map((l) => l.itemId));
    picker.innerHTML = String(html`
      ${catChips(pickerCat, counts)}
      <div class="picker-row">${list.length
        ? list.map((i) => html`<button class="pick ${used.has(i.id) ? 'used' : ''}" data-add="${i.id}" title="${itemLabel(i)}"><img src="${imgURL(i.thumb || i.image)}" alt="" loading="lazy"></button>`)
        : html`<p class="hint">В гардеробе пока пусто — <a href="#/closet">добавьте вещи</a>.</p>`}</div>`);
  }

  function addItem(itemId) {
    const it = state.items.get(itemId);
    const same = layers.filter((l) => state.items.get(l.itemId)?.category === it.category).length;
    const z = layers.reduce((m, l) => Math.max(m, l.z), 0) + 1;
    const L = slotLayer(it, same, Math.max(z, slotLayer(it).z));
    layers.push(L);
    selected = L.id;
    change();
    drawStage();
    drawPicker();
  }

  // ─── Жесты ───────────────────────────────────────────────────────────
  const pointers = new Map();
  let gesture = null;

  const startGesture = () => {
    const L = layers.find((l) => l.id === selected);
    if (!L) { gesture = null; return; }
    gesture = { L0: { ...L }, pts0: [...pointers.values()].map((p) => ({ ...p })), rect: stage.getBoundingClientRect() };
  };

  stage.addEventListener('pointerdown', (e) => {
    const el = e.target.closest('.layer');
    if (!pointers.size) select(el ? el.dataset.id : null);
    if (!selected) return;
    e.preventDefault();
    stage.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    startGesture();
  });

  stage.addEventListener('pointermove', (e) => {
    if (!pointers.has(e.pointerId) || !gesture) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const L = layers.find((l) => l.id === selected);
    if (!L) return;
    const { L0, pts0, rect } = gesture;
    const pts = [...pointers.values()];
    if (pts.length === 1 || pts0.length === 1) {
      L.x = clamp(L0.x + (pts[0].x - pts0[0].x) / rect.width, -0.2, 1.2);
      L.y = clamp(L0.y + (pts[0].y - pts0[0].y) / rect.height, -0.2, 1.2);
    } else {
      const [a0, b0] = pts0, [a, b] = pts;
      const mid0 = { x: (a0.x + b0.x) / 2, y: (a0.y + b0.y) / 2 }, mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const d0 = Math.hypot(b0.x - a0.x, b0.y - a0.y) || 1, d = Math.hypot(b.x - a.x, b.y - a.y);
      const ang0 = Math.atan2(b0.y - a0.y, b0.x - a0.x), ang = Math.atan2(b.y - a.y, b.x - a.x);
      L.x = clamp(L0.x + (mid.x - mid0.x) / rect.width, -0.2, 1.2);
      L.y = clamp(L0.y + (mid.y - mid0.y) / rect.height, -0.2, 1.2);
      L.w = clamp((L0.w * d) / d0, 0.05, 1.3);
      L.rot = normAngle(L0.rot + ((ang - ang0) * 180) / Math.PI);
    }
    updateLayerEl(L);
    change();
  });

  const endPointer = (e) => {
    if (!pointers.delete(e.pointerId)) return;
    if (pointers.size) startGesture();
    else { gesture = null; drawTools(); }
  };
  stage.addEventListener('pointerup', endPointer);
  stage.addEventListener('pointercancel', endPointer);

  stage.addEventListener('wheel', (e) => {
    const L = layers.find((l) => l.id === selected);
    if (!L) return;
    e.preventDefault();
    if (e.shiftKey || e.altKey) L.rot = normAngle(L.rot + e.deltaY * 0.15);
    else L.w = clamp(L.w * Math.exp(-e.deltaY * 0.0015), 0.05, 1.3);
    updateLayerEl(L);
    change();
    clearTimeout(stage._t);
    stage._t = setTimeout(drawTools, 150);
  }, { passive: false });

  const onKey = (e) => {
    if (!selected || e.target.matches('input, textarea')) return;
    const L = layers.find((l) => l.id === selected);
    const step = e.shiftKey ? 0.05 : 0.01;
    const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (e.key === 'Delete' || e.key === 'Backspace') layerTool('del');
    else if (moves[e.key]) {
      L.x += moves[e.key][0];
      L.y += moves[e.key][1];
      updateLayerEl(L);
      change();
    } else return;
    e.preventDefault();
  };
  document.addEventListener('keydown', onKey);

  // ─── Действия со слоем ──────────────────────────────────────────────
  function layerTool(t) {
    const L = layers.find((l) => l.id === selected);
    if (!L) return;
    const zs = layers.map((l) => l.z);
    if (t === 'up') L.z = Math.max(...zs) + 1;
    else if (t === 'down') L.z = Math.min(...zs) - 1;
    else if (t === 'flip') L.flip = !L.flip;
    else if (t === 'dup') {
      const c = { ...L, id: uid(), x: L.x + 0.04, y: L.y + 0.04, z: Math.max(...zs) + 1 };
      layers.push(c);
      selected = c.id;
    } else if (t === 'del') {
      layers = layers.filter((l) => l !== L);
      selected = null;
      drawPicker();
    }
    change();
    drawStage();
  }

  tools.addEventListener('click', (e) => {
    const t = e.target.closest('[data-lt]')?.dataset.lt;
    if (t) layerTool(t);
  });
  tools.addEventListener('input', (e) => {
    const k = e.target.dataset.ls;
    const L = layers.find((l) => l.id === selected);
    if (!k || !L) return;
    if (k === 'w') L.w = +e.target.value / 100;
    else L.rot = +e.target.value;
    updateLayerEl(L);
    change();
  });

  picker.addEventListener('click', (e) => {
    const chip = e.target.closest('[data-cat]');
    if (chip) { pickerCat = chip.dataset.cat; drawPicker(); return; }
    const add = e.target.closest('[data-add]');
    if (add) addItem(add.dataset.add);
  });

  // ─── Верхняя и нижняя панели ────────────────────────────────────────
  root.addEventListener('click', async (e) => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    if (act === 'cancel') {
      if (!dirty || (await confirmDialog('Выйти без сохранения?', { ok: 'Выйти' }))) goBack(existing ? `/outfit/${existing.id}` : '/outfits');
    } else if (act === 'save') save();
    else if (act === 'picker') { pickerOpen = !pickerOpen; drawPicker(); }
    else if (act === 'shuffle') {
      const items = randomOutfit(activeItems());
      if (!items.length) return toast('Добавьте вещи в гардероб — будет из чего выбирать');
      layers = autoLayout(items);
      selected = null;
      change();
      drawStage();
      drawPicker();
    } else if (act === 'bg') chooseBg();
    else if (act === 'clear') {
      if (layers.length && (await confirmDialog('Убрать все вещи с холста?', { ok: 'Очистить' }))) {
        layers = [];
        selected = null;
        change();
        drawStage();
        drawPicker();
      }
    }
  });

  function chooseBg() {
    const s = openSheet({
      title: 'Фон',
      className: 'compact',
      body: html`<div class="swatches big">${STAGE_BGS.map((c) => html`<button class="swatch ${c === bg ? 'on' : ''}" data-bg="${c}" style="background:${c}" aria-label="${c}"></button>`)}</div>`,
    });
    s.body.addEventListener('click', (e) => {
      const b = e.target.closest('[data-bg]');
      if (!b) return;
      bg = b.dataset.bg;
      stage.style.background = bg;
      change();
      s.close();
    });
  }

  async function save() {
    if (!layers.length) return toast('Добавьте на холст хотя бы одну вещь');
    let name = existing?.name ?? '';
    let seasons = existing?.seasons ?? (query.get('shuffle') ? [currentSeason()] : []);
    if (!existing) {
      const res = await askMeta(name, seasons);
      if (!res) return;
      ({ name, seasons } = res);
    }
    const outfit = {
      ...(existing ?? { id: uid(), favorite: false }),
      name, seasons, bg,
      layers: layers.map(({ id: lid, itemId, x, y, w, rot, flip, z }) => ({ id: lid, itemId, x, y, w, rot, flip, z })),
    };
    outfit.preview = await busy('Сохраняю образ…', () => renderOutfitPreview(outfit, state.items));
    await saveOutfit(outfit);
    if (planDate) {
      await planOutfit(planDate, outfit.id);
      toast(`Образ сохранён и запланирован на ${fmtDate(planDate)}`);
    } else toast('Образ сохранён');
    dirty = false;
    if (planDate) location.replace(`#/calendar?d=${planDate}`);
    else location.replace(`#/outfit/${outfit.id}`);
  }

  drawStage();
  drawPicker();

  return () => document.removeEventListener('keydown', onKey);
}

function normAngle(a) {
  a = ((a + 180) % 360 + 360) % 360 - 180;
  return Math.round(a * 10) / 10;
}

function askMeta(name, seasons) {
  return new Promise((resolve) => {
    let result = null;
    const sel = new Set(seasons);
    const s = openSheet({
      title: 'Сохранить образ',
      className: 'compact',
      onClose: () => resolve(result),
      body: html`<form class="prompt-form">
        <input class="input" name="name" value="${name}" placeholder="Название (необязательно)">
        <div class="chips wrap">${SEASONS.map((x) => html`<button type="button" class="chip ${sel.has(x.id) ? 'on' : ''}" data-s="${x.id}">${x.name}</button>`)}</div>
        <div class="btn-row"><button type="button" class="btn" data-close>Отмена</button><button class="btn primary">Сохранить</button></div>
      </form>`,
    });
    s.body.addEventListener('click', (e) => {
      const b = e.target.closest('[data-s]');
      if (b) { sel.has(b.dataset.s) ? sel.delete(b.dataset.s) : sel.add(b.dataset.s); b.classList.toggle('on'); }
    });
    s.body.querySelector('form').onsubmit = (e) => {
      e.preventDefault();
      result = { name: e.target.elements.name.value.trim(), seasons: [...sel] };
      s.close();
    };
  });
}
