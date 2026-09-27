import { html, uid, isoDate, blobToImage, scaledCanvas, makeCanvas, encodeCanvas, clamp, pickFiles, $ } from '../util.js';
import { CATEGORIES, catById, COLORS, SEASONS, currentSeason } from '../constants.js';
import { state, saveItem, imgURL } from '../store.js';
import { icon, toast, confirmDialog, busy } from '../ui.js';
import { autoBackgroundMask, floodRegion, opaqueBounds, suggestColors, feather } from '../image-tools.js';

const WORK_MAX = 1024;
const SAVE_MAX = 900;
const THUMB_MAX = 360;

/** Вырезание вещи из фото: маска прозрачности + инструменты. */
class Cutout {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', { willReadFrequently: true });
    this.undo = [];
  }

  async load(blob) {
    const img = await blobToImage(blob);
    const c = scaledCanvas(img, WORK_MAX);
    this.setImage(c.getContext('2d').getImageData(0, 0, c.width, c.height));
  }

  setImage(imageData) {
    this.W = imageData.width;
    this.H = imageData.height;
    this.orig = imageData;
    this.mask = new Uint8ClampedArray(this.W * this.H);
    for (let p = 0; p < this.mask.length; p++) this.mask[p] = imageData.data[p * 4 + 3];
    this.initial = this.mask.slice();
    this.beforeAuto = null;
    this.out = new ImageData(new Uint8ClampedArray(imageData.data), this.W, this.H);
    this.canvas.width = this.W;
    this.canvas.height = this.H;
    this.render();
  }

  render(x0 = 0, y0 = 0, x1 = this.W, y1 = this.H) {
    x0 = clamp(Math.floor(x0), 0, this.W); x1 = clamp(Math.ceil(x1), 0, this.W);
    y0 = clamp(Math.floor(y0), 0, this.H); y1 = clamp(Math.ceil(y1), 0, this.H);
    if (x1 <= x0 || y1 <= y0) return;
    const od = this.out.data, m = this.mask;
    for (let y = y0; y < y1; y++) {
      for (let x = x0; x < x1; x++) {
        const p = y * this.W + x;
        od[p * 4 + 3] = m[p];
      }
    }
    this.ctx.putImageData(this.out, 0, 0, x0, y0, x1 - x0, y1 - y0);
  }

  pushUndo() {
    this.undo.push(this.mask.slice());
    if (this.undo.length > 15) this.undo.shift();
  }

  popUndo() {
    const m = this.undo.pop();
    if (!m) return false;
    this.mask = m;
    this.beforeAuto = null;
    this.render();
    return true;
  }

  auto(tol, fresh = true) {
    if (fresh || !this.beforeAuto) {
      this.pushUndo();
      this.beforeAuto = this.mask.slice();
    }
    const m = autoBackgroundMask(this.orig, tol);
    if (!m) {
      this.mask = this.beforeAuto.slice();
      this.render();
      return false;
    }
    const base = this.beforeAuto;
    for (let p = 0; p < m.length; p++) this.mask[p] = Math.min(base[p], m[p]);
    this.render();
    return true;
  }

  wand(x, y, tol) {
    const p = Math.floor(y) * this.W + Math.floor(x);
    const i = p * 4, d = this.orig.data;
    this.pushUndo();
    this.beforeAuto = null;
    const region = floodRegion(this.orig, [p], [d[i], d[i + 1], d[i + 2]], tol);
    // область плюс пиксель вокруг: иначе по контуру остаётся полупрозрачная кайма
    const { W, H } = this;
    for (let q = 0; q < region.length; q++) {
      if (!region[q]) continue;
      const x = q % W;
      this.mask[q] = 0;
      if (x > 0) this.mask[q - 1] = 0;
      if (x < W - 1) this.mask[q + 1] = 0;
      if (q >= W) this.mask[q - W] = 0;
      if (q < W * (H - 1)) this.mask[q + W] = 0;
    }
    this.mask = feather(this.mask, W, H);
    this.render();
  }

  stroke(x0, y0, x1, y1, r, value) {
    const len = Math.hypot(x1 - x0, y1 - y0);
    const steps = Math.max(1, Math.ceil(len / Math.max(1, r / 3)));
    for (let s = 0; s <= steps; s++) {
      const cx = x0 + ((x1 - x0) * s) / steps, cy = y0 + ((y1 - y0) * s) / steps;
      const xa = Math.max(0, Math.floor(cx - r)), xb = Math.min(this.W - 1, Math.ceil(cx + r));
      const ya = Math.max(0, Math.floor(cy - r)), yb = Math.min(this.H - 1, Math.ceil(cy + r));
      for (let y = ya; y <= yb; y++) {
        for (let x = xa; x <= xb; x++) {
          const dd = Math.hypot(x - cx, y - cy);
          if (dd > r) continue;
          const p = y * this.W + x;
          // мягкий край кисти в последнем пикселе
          const k = clamp(r - dd, 0, 1);
          this.mask[p] = value ? Math.max(this.mask[p], 255 * k) : Math.min(this.mask[p], 255 * (1 - k));
        }
      }
    }
    this.render(Math.min(x0, x1) - r - 1, Math.min(y0, y1) - r - 1, Math.max(x0, x1) + r + 2, Math.max(y0, y1) + r + 2);
  }

  reset() {
    this.pushUndo();
    this.beforeAuto = null;
    this.mask = this.initial.slice();
    this.render();
  }

  rotate() {
    const { W, H } = this;
    const src = this.orig.data;
    const rot = new ImageData(H, W);
    const m = new Uint8ClampedArray(W * H);
    const init = new Uint8ClampedArray(W * H);
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        // по часовой: (x, y) → (H-1-y, x)
        const p = y * W + x, q = x * H + (H - 1 - y);
        rot.data.set(src.subarray(p * 4, p * 4 + 4), q * 4);
        m[q] = this.mask[p];
        init[q] = this.initial[p];
      }
    }
    this.setImage(rot);
    this.mask = m;
    this.initial = init;
    this.undo = [];
    this.render();
  }

  hasTransparency() {
    for (let p = 0; p < this.mask.length; p++) if (this.mask[p] < 250) return true;
    return false;
  }

  async export() {
    const transparent = this.hasTransparency();
    let box = { x: 0, y: 0, w: this.W, h: this.H };
    if (transparent) {
      let solid = 0;
      for (let p = 0; p < this.mask.length; p++) if (this.mask[p] > 128) solid++;
      box = solid > this.mask.length * 0.002 ? opaqueBounds(this.mask, this.W, this.H, 128) : null;
      if (!box) throw new Error('Вы стёрли всю картинку — верните часть кистью');
      const padX = Math.round(box.w * 0.03), padY = Math.round(box.h * 0.03);
      box = {
        x: Math.max(0, box.x - padX), y: Math.max(0, box.y - padY),
        w: Math.min(this.W, box.x + box.w + padX) - Math.max(0, box.x - padX),
        h: Math.min(this.H, box.y + box.h + padY) - Math.max(0, box.y - padY),
      };
    }
    const full = makeCanvas(this.W, this.H);
    full.getContext('2d').putImageData(this.out, 0, 0);
    const k = Math.min(1, SAVE_MAX / Math.max(box.w, box.h));
    const c = makeCanvas(box.w * k, box.h * k);
    const ctx = c.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(full, box.x, box.y, box.w, box.h, 0, 0, c.width, c.height);
    const kt = Math.min(1, THUMB_MAX / Math.max(c.width, c.height));
    const t = makeCanvas(c.width * kt, c.height * kt);
    const tctx = t.getContext('2d');
    tctx.imageSmoothingQuality = 'high';
    tctx.drawImage(c, 0, 0, t.width, t.height);
    const [image, thumb] = await Promise.all([encodeCanvas(c, transparent), encodeCanvas(t, transparent)]);
    return { image, thumb, ar: c.height / c.width, colors: suggestColors(this.out, this.mask) };
  }
}

/** Добавить несколько фото подряд: для каждого — вырезание и карточка вещи. */
export async function startAddItems(files, preset = {}) {
  const images = files.filter((f) => f.type.startsWith('image/') || /\.(heic|heif|jpe?g|png|webp|gif|avif)$/i.test(f.name));
  for (let i = 0; i < images.length; i++) {
    const res = await editItem({ file: images[i], index: i, total: images.length, preset });
    if (res === 'cancel') break;
  }
}

/**
 * Полноэкранный редактор вещи.
 * Новая вещь: сначала фото (вырезание фона), потом карточка.
 * Существующая: сразу карточка, фото можно переделать.
 */
export function editItem({ item = null, file = null, index = 0, total = 1, preset = {} }) {
  return new Promise((resolve) => {
    const isNew = !item;
    const draft = item
      ? { ...item, colors: [...(item.colors ?? [])], seasons: [...(item.seasons ?? [])], tags: [...(item.tags ?? [])] }
      : {
          id: uid(), category: preset.category && preset.category !== 'all' ? preset.category : 'tops',
          sub: '', name: '', colors: [], brand: '', size: '', price: null, purchased: '',
          seasons: [], tags: [], notes: '', favorite: false, archived: false,
        };
    let imgResult = null; // { image, thumb, ar, colors } после шага фото
    let step = isNew ? 'image' : 'form';
    let tool = 'auto';
    let tol = 40;
    let brush = 36;
    const counter = total > 1 ? ` · ${index + 1} из ${total}` : '';

    const ov = document.createElement('div');
    ov.className = 'overlay';
    document.body.append(ov);
    document.body.classList.add('no-scroll');
    requestAnimationFrame(() => ov.classList.add('open'));

    const finish = (res) => {
      ov.classList.remove('open');
      document.body.classList.remove('no-scroll');
      setTimeout(() => ov.remove(), 220);
      resolve(res);
    };

    let cut = null;

    // ─── Шаг 1: фото ─────────────────────────────────────────────────────
    async function showImageStep(source) {
      step = 'image';
      ov.innerHTML = String(html`
        <header class="bar">
          <button class="text-btn" data-act="cancel">${isNew ? 'Отмена' : 'Назад'}</button>
          <h2>Фото${counter}</h2>
          <button class="btn primary sm" data-act="next">${isNew ? 'Далее' : 'Готово'}</button>
        </header>
        <div class="cut-area"><div class="checker cut-frame"><canvas class="cut-canvas"></canvas></div></div>
        <div class="cut-tools">
          <div class="toolbar">
            <button class="tool" data-tool="auto">${icon('sparkle')}<span>Авто-фон</span></button>
            <button class="tool" data-tool="wand">${icon('wand')}<span>Палочка</span></button>
            <button class="tool" data-tool="erase">${icon('eraser')}<span>Ластик</span></button>
            <button class="tool" data-tool="restore">${icon('brush')}<span>Вернуть</span></button>
            <button class="tool" data-act="undo">${icon('undo')}<span>Отменить</span></button>
            <button class="tool" data-act="rotate">${icon('reset')}<span>Повернуть</span></button>
            <button class="tool" data-act="reset">${icon('image')}<span>Исходное</span></button>
          </div>
          <div class="tool-opt"></div>
          <p class="hint"></p>
        </div>`);
      const canvas = $('.cut-canvas', ov);
      const prev = cut;
      cut = new Cutout(canvas);
      if (!source && prev) {
        // возврат с карточки: продолжаем с той же маской и историей
        cut.setImage(prev.orig);
        Object.assign(cut, { mask: prev.mask, initial: prev.initial, undo: prev.undo });
        cut.render();
        setTool(tool);
        bindCanvas(canvas);
        return;
      }
      try {
        await busy('Открываю фото…', () => cut.load(source));
      } catch (e) {
        toast(e.message || 'Не удалось открыть фото');
        if (isNew) return finish('skip');
        return showFormStep();
      }
      if (isNew) {
        const ok = await busy('Убираю фон…', async () => cut.auto(tol));
        setHint(ok ? 'Фон убран. Поправьте палочкой или ластиком, если нужно.' : 'Фон не распознан — сфотографируйте вещь на ровном фоне или сотрите его палочкой и ластиком.');
      } else setHint('Выберите инструмент');
      setTool(tool);
      bindCanvas(canvas);
    }

    function setHint(t) {
      const h = $('.hint', ov);
      if (h) h.textContent = t;
    }

    function setTool(t) {
      tool = t;
      ov.querySelectorAll('[data-tool]').forEach((b) => b.classList.toggle('on', b.dataset.tool === t));
      const opt = $('.tool-opt', ov);
      if (t === 'auto' || t === 'wand') {
        opt.innerHTML = String(html`<label class="slider"><span>Чувствительность</span><input type="range" min="5" max="110" value="${tol}" data-opt="tol"></label>`);
      } else {
        opt.innerHTML = String(html`<label class="slider"><span>Размер кисти</span><input type="range" min="6" max="90" value="${brush}" data-opt="brush"></label>`);
      }
      const hints = {
        auto: 'Двигайте ползунок, если фон убран не полностью или задета вещь.',
        wand: 'Нажмите на участок фона, чтобы убрать его.',
        erase: 'Проведите пальцем по тому, что нужно стереть.',
        restore: 'Проведите по стёртому, чтобы вернуть.',
      };
      setHint(hints[t]);
    }

    function bindCanvas(canvas) {
      let last = null;
      const pos = (e) => {
        const r = canvas.getBoundingClientRect();
        return { x: ((e.clientX - r.left) * cut.W) / r.width, y: ((e.clientY - r.top) * cut.H) / r.height, k: cut.W / r.width };
      };
      canvas.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        const p = pos(e);
        if (tool === 'wand') {
          if (p.x >= 0 && p.y >= 0 && p.x < cut.W && p.y < cut.H) cut.wand(p.x, p.y, tol);
          return;
        }
        if (tool === 'erase' || tool === 'restore') {
          canvas.setPointerCapture(e.pointerId);
          cut.pushUndo();
          cut.beforeAuto = null;
          last = p;
          cut.stroke(p.x, p.y, p.x, p.y, (brush / 2) * p.k, tool === 'restore');
        }
      });
      canvas.addEventListener('pointermove', (e) => {
        if (!last) return;
        const p = pos(e);
        cut.stroke(last.x, last.y, p.x, p.y, (brush / 2) * p.k, tool === 'restore');
        last = p;
      });
      const end = () => { last = null; };
      canvas.addEventListener('pointerup', end);
      canvas.addEventListener('pointercancel', end);
    }

    // ─── Шаг 2: карточка ─────────────────────────────────────────────────
    function showFormStep() {
      step = 'form';
      const previewSrc = imgResult ? imgURL(imgResult.image) : imgURL(draft.image);
      ov.innerHTML = String(html`
        <header class="bar">
          <button class="text-btn" data-act="${isNew ? 'back' : 'cancel'}">${isNew ? 'Назад' : 'Отмена'}</button>
          <h2>${isNew ? 'Новая вещь' : 'Изменить вещь'}${counter}</h2>
          <button class="btn primary sm" data-act="save">Сохранить</button>
        </header>
        <form class="form scroll-y" autocomplete="off">
          <div class="form-photo">
            <div class="checker thumb-lg"><img src="${previewSrc}" alt=""></div>
            ${!isNew ? html`<button type="button" class="btn sm" data-act="rephoto">${icon('edit')} Фон</button>
              <button type="button" class="btn sm" data-act="newphoto">${icon('camera')} Другое фото</button>` : ''}
          </div>
          <div class="field"><span class="label">Категория</span>
            <div class="chips wrap" data-group="category">${CATEGORIES.map((c) => html`<button type="button" class="chip ${draft.category === c.id ? 'on' : ''}" data-val="${c.id}">${c.name}</button>`)}</div>
          </div>
          <label class="field"><span class="label">Тип</span>
            <input class="input" name="sub" list="sub-list" value="${draft.sub}" placeholder="Например, ${catById[draft.category].sub[0].toLowerCase()}">
            <datalist id="sub-list"></datalist>
          </label>
          <div class="field"><span class="label">Цвет</span>
            <div class="swatches" data-group="colors">${COLORS.map((c) => html`<button type="button" class="swatch ${draft.colors.includes(c.id) ? 'on' : ''}" data-val="${c.id}" title="${c.name}" aria-label="${c.name}" style="background:${c.hex}"></button>`)}</div>
          </div>
          <label class="field"><span class="label">Название</span><input class="input" name="name" value="${draft.name}" placeholder="Необязательно"></label>
          <div class="grid2">
            <label class="field"><span class="label">Бренд</span><input class="input" name="brand" list="brand-list" value="${draft.brand}">
              <datalist id="brand-list">${[...new Set([...state.items.values()].map((i) => i.brand).filter(Boolean))].sort().map((b) => html`<option value="${b}">`)}</datalist></label>
            <label class="field"><span class="label">Размер</span><input class="input" name="size" value="${draft.size}"></label>
          </div>
          <div class="grid2">
            <label class="field"><span class="label">Цена, ${state.settings.currency}</span><input class="input" name="price" type="number" inputmode="decimal" min="0" step="0.01" value="${draft.price ?? ''}"></label>
            <label class="field"><span class="label">Куплено</span><input class="input" name="purchased" type="date" value="${draft.purchased}" max="${isoDate()}"></label>
          </div>
          <div class="field"><span class="label">Сезон</span>
            <div class="chips wrap" data-group="seasons">${SEASONS.map((s) => html`<button type="button" class="chip ${draft.seasons.includes(s.id) ? 'on' : ''}" data-val="${s.id}">${s.name}</button>`)}</div>
          </div>
          <label class="field"><span class="label">Теги</span><input class="input" name="tags" value="${draft.tags.join(', ')}" placeholder="офис, отпуск, спорт"></label>
          <label class="field"><span class="label">Заметки</span><textarea class="input" name="notes" rows="3">${draft.notes}</textarea></label>
          <label class="switch"><input type="checkbox" name="favorite" ${draft.favorite ? 'checked' : ''}><span>В избранном</span></label>
          <label class="switch"><input type="checkbox" name="archived" ${draft.archived ? 'checked' : ''}><span>В архиве (не показывать в гардеробе и подборе)</span></label>
        </form>`);
      fillSubs();
    }

    function fillSubs() {
      const dl = $('#sub-list', ov);
      if (!dl) return;
      const own = [...state.items.values()].filter((i) => i.category === draft.category).map((i) => i.sub);
      const subs = [...new Set([...catById[draft.category].sub, ...own.filter(Boolean)])];
      dl.innerHTML = subs.map((s) => `<option value="${s.replace(/"/g, '&quot;')}">`).join('');
      const inp = ov.querySelector('[name=sub]');
      if (inp) inp.placeholder = `Например, ${catById[draft.category].sub[0].toLowerCase()}`;
    }

    function readForm() {
      const f = $('form', ov);
      if (!f) return;
      const v = (n) => f.elements[n].value.trim();
      draft.sub = v('sub');
      draft.name = v('name');
      draft.brand = v('brand');
      draft.size = v('size');
      const price = parseFloat(v('price').replace(',', '.'));
      draft.price = Number.isFinite(price) ? price : null;
      draft.purchased = v('purchased');
      draft.tags = v('tags').split(',').map((t) => t.trim()).filter(Boolean);
      draft.notes = f.elements.notes.value.trim();
      draft.favorite = f.elements.favorite.checked;
      draft.archived = f.elements.archived.checked;
    }

    async function toForm() {
      try {
        imgResult = await busy('Сохраняю фото…', () => cut.export());
      } catch (e) {
        toast(e.message);
        return;
      }
      if (isNew && !draft.colors.length) draft.colors = imgResult.colors;
      showFormStep();
    }

    async function save() {
      readForm();
      const out = { ...draft };
      if (imgResult) Object.assign(out, { image: imgResult.image, thumb: imgResult.thumb, ar: imgResult.ar });
      if (!out.image) return toast('Нет фото');
      if (isNew && !out.seasons.length && preset.season) out.seasons = [preset.season];
      await saveItem(out);
      toast(isNew ? 'Вещь добавлена' : 'Сохранено');
      finish('saved');
    }

    ov.addEventListener('click', async (e) => {
      const toolBtn = e.target.closest('[data-tool]');
      if (toolBtn) {
        const t = toolBtn.dataset.tool;
        setTool(t);
        if (t === 'auto') {
          const ok = await busy('Убираю фон…', async () => cut.auto(tol));
          if (!ok) setHint('Фон не распознан. Попробуйте палочку: нажмите на фон.');
        }
        return;
      }
      const chip = e.target.closest('[data-group] [data-val]');
      if (chip) {
        const group = chip.parentElement.dataset.group;
        const val = chip.dataset.val;
        if (group === 'category') {
          draft.category = val;
          chip.parentElement.querySelectorAll('[data-val]').forEach((b) => b.classList.toggle('on', b === chip));
          fillSubs();
        } else {
          const arr = draft[group];
          const i = arr.indexOf(val);
          i >= 0 ? arr.splice(i, 1) : arr.push(val);
          chip.classList.toggle('on', i < 0);
        }
        return;
      }
      const act = e.target.closest('[data-act]')?.dataset.act;
      if (!act) return;
      if (act === 'cancel') {
        if (step === 'image' && !isNew) return showFormStep();
        if (total > 1 && isNew) {
          const all = await confirmDialog(`Пропустить оставшиеся фото (${total - index})?`, { ok: 'Пропустить все', cancel: 'Только это', danger: false });
          return finish(all ? 'cancel' : 'skip');
        }
        return finish('cancel');
      }
      if (act === 'back') { readForm(); return showImageStep(null); }
      if (act === 'next') return toForm();
      if (act === 'save') return save();
      if (act === 'undo') { if (!cut.popUndo()) toast('Нечего отменять'); return; }
      if (act === 'reset') return cut.reset();
      if (act === 'rotate') return cut.rotate();
      if (act === 'rephoto') { readForm(); return showImageStep(imgResult?.image ?? draft.image); }
      if (act === 'newphoto') {
        readForm();
        const [f] = await pickFiles({ multiple: false });
        if (f) {
          file = f;
          await showImageStep(f);
          if (!cut.auto(tol)) setHint('Фон не распознан. Попробуйте палочку: нажмите на фон.');
        }
      }
    });

    ov.addEventListener('input', (e) => {
      const opt = e.target.dataset?.opt;
      if (opt === 'brush') brush = +e.target.value;
      if (opt === 'tol') {
        tol = +e.target.value;
        if (tool === 'auto') {
          clearTimeout(ov._t);
          ov._t = setTimeout(() => {
            const ok = cut.auto(tol, false);
            setHint(ok ? 'Двигайте ползунок, если фон убран не полностью или задета вещь.' : 'При такой чувствительности фон не находится.');
          }, 120);
        }
      }
    });

    if (step === 'image') showImageStep(file);
    else showFormStep();
  });
}
