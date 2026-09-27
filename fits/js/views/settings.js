import { html, pickFiles, isoDate } from '../util.js';
import { state, saveSettings, exportBackup, importBackup, wipeAll } from '../store.js';
import { icon, toast, confirmDialog, busy, openSheet } from '../ui.js';
import { goBack } from '../router.js';
import { applyTheme } from '../theme.js';
import { AI_MODELS, aiPreload } from '../ai-bg.js';
import { AI_CHAT_MODELS, chatModel, fmtUsd } from '../ai-stylist.js';
import { city, searchCity, setCity } from '../weather.js';

export async function settingsView(root) {
  const est = await navigator.storage?.estimate?.().catch(() => null);
  const persisted = await navigator.storage?.persisted?.().catch(() => false);
  const mb = (b) => `${(b / 1048576).toFixed(1)} МБ`;
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;

  root.innerHTML = String(html`
    <header class="bar">
      <button class="icon-btn" data-act="back" aria-label="Назад">${icon('back')}</button>
      <h2>Настройки</h2><span class="icon-btn"></span>
    </header>
    <div class="page">
      ${!standalone ? html`<div class="card-box note">
        <b>Установите на телефон</b>
        <p>${isIOS ? 'В Safari нажмите «Поделиться» → «На экран „Домой“».' : 'В меню браузера выберите «Установить приложение» или «Добавить на главный экран».'} Приложение будет открываться как обычное и работать без интернета.</p>
      </div>` : ''}

      <h3 class="section-title">Внешний вид</h3>
      <div class="card-box">
        <div class="segmented" data-group="theme">
          ${[['auto', 'Как в системе'], ['light', 'Светлая'], ['dark', 'Тёмная']].map(([v, n]) => html`<button class="${state.settings.theme === v ? 'on' : ''}" data-theme="${v}">${n}</button>`)}
        </div>
        <label class="field"><span class="label">Валюта</span>
          <input class="input" name="currency" value="${state.settings.currency}" maxlength="8"></label>
      </div>

      <h3 class="section-title">Стилист</h3>
      <div class="card-box">
        <div class="kv link" data-act="city"><span>Город для погоды</span><b>${city().name} ${icon('chevronR', 'sm')}</b></div>
        <label class="field"><span class="label">Ключ API Anthropic для ИИ-стилиста</span>
          <input class="input" name="aiKey" type="password" autocomplete="off" spellcheck="false" placeholder="sk-ant-…" value="${state.settings.aiKey ?? ''}"></label>
        <p class="muted small">Ключ хранится только на этом устройстве и не попадает в резервную копию. Получить: console.anthropic.com → API Keys (нужно пополнить баланс; там же можно поставить месячный лимит). Не давайте никому пользоваться приложением на этом телефоне, если не хотите делиться балансом.</p>
        <span class="label">Модель</span>
        <div class="segmented">${Object.entries(AI_CHAT_MODELS).map(([k, m]) => html`<button class="${chatModel() === k ? 'on' : ''}" data-chat-model="${k}">${m.name}</button>`)}</div>
        <p class="muted small">${AI_CHAT_MODELS[chatModel()].name}: ${AI_CHAT_MODELS[chatModel()].note}.
          ${state.settings.aiSpend?.month === isoDate().slice(0, 7) ? `В этом месяце: ${state.settings.aiSpend.count ?? 0} запр. ≈ ${fmtUsd(state.settings.aiSpend.usd)} (оценка по токенам).` : ''}</p>
        ${state.settings.aiKey ? html`<button class="btn sm danger-text" data-act="ai-key-del">${icon('trash')} Удалить ключ</button>` : ''}
      </div>

      <h3 class="section-title">Удаление фона</h3>
      <div class="card-box">
        <div class="segmented">
          <button class="${!state.settings.aiBg ? 'on' : ''}" data-ai="off">Обычное</button>
          <button class="${state.settings.aiBg ? 'on' : ''}" data-ai="on">Нейросеть</button>
        </div>
        <p class="muted small">${state.settings.aiBg
          ? 'Каждое новое фото обрабатывает нейросеть: вещь вырезается аккуратно даже на пёстром фоне. Считается прямо на телефоне, фото никуда не отправляются. Одно фото — от нескольких секунд до полуминуты.'
          : 'Обычный способ мгновенный, но хорошо работает только на ровном однотонном фоне. Кнопка «Нейросеть» в редакторе доступна всегда.'}</p>
        <span class="label">Модель</span>
        <div class="segmented">${Object.entries(AI_MODELS).map(([k, m]) => html`<button class="${(state.settings.aiModel || 'small') === k ? 'on' : ''}" data-model="${k}">${m.name} · ${m.size}</button>`)}</div>
        ${state.settings.aiReady === (state.settings.aiModel || 'small')
          ? html`<p class="muted small">${icon('check', 'sm')} Модель скачана и работает без интернета.</p>`
          : html`<button class="btn" data-act="ai-preload">${icon('download')} Скачать модель сейчас</button>
            <p class="muted small">Скачивается один раз, лучше по Wi-Fi. Без этого загрузка начнётся при первом использовании.</p>`}
      </div>

      <h3 class="section-title">Данные</h3>
      <div class="card-box">
        <p class="muted">Всё хранится только на этом устройстве, в браузере. Делайте резервную копию — при очистке данных сайта или смене телефона её можно восстановить.</p>
        <div class="btn-row">
          <button class="btn" data-act="export">${icon('download')} Резервная копия</button>
          <button class="btn" data-act="import">${icon('upload')} Восстановить</button>
        </div>
        ${est ? html`<p class="muted small">Занято: ${mb(est.usage ?? 0)}${est.quota ? ` из ${mb(est.quota)}` : ''}. ${persisted ? 'Хранилище защищено от автоочистки.' : 'Браузер может очистить данные при нехватке места.'}</p>` : ''}
        ${!persisted && navigator.storage?.persist ? html`<button class="btn sm" data-act="persist">Защитить от автоочистки</button>` : ''}
      </div>

      <h3 class="section-title">Опасная зона</h3>
      <div class="card-box"><button class="btn danger block" data-act="wipe">${icon('trash')} Удалить все данные</button></div>

      <p class="muted small center">Fits · личный цифровой гардероб · вещей: ${state.items.size}, образов: ${state.outfits.size}</p>
    </div>`);

  root.addEventListener('click', async (e) => {
    const theme = e.target.closest('[data-theme]')?.dataset.theme;
    if (theme) {
      await saveSettings({ theme });
      applyTheme(theme);
      return;
    }
    const cm = e.target.closest('[data-chat-model]')?.dataset.chatModel;
    if (cm) return saveSettings({ aiChatModel: cm });
    const ai = e.target.closest('[data-ai]')?.dataset.ai;
    if (ai) return saveSettings({ aiBg: ai === 'on' });
    const model = e.target.closest('[data-model]')?.dataset.model;
    if (model) return saveSettings({ aiModel: model });
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'back') goBack('/closet');
    else if (act === 'city') chooseCity();
    else if (act === 'ai-key-del') {
      if (await confirmDialog('Удалить ключ API с этого устройства?', { ok: 'Удалить' })) saveSettings({ aiKey: '' });
    }
    else if (act === 'ai-preload') {
      try {
        await busy('Готовлю нейросеть…', (setMsg) => aiPreload(setMsg));
        toast('Нейросеть скачана');
      } catch (err) {
        toast(err.message);
      }
    }
    else if (act === 'export') {
      const data = await busy('Собираю копию…', exportBackup);
      const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
      const name = `fits-backup-${new Date().toISOString().slice(0, 10)}.json`;
      const file = new File([blob], name, { type: 'application/json' });
      if (navigator.canShare?.({ files: [file] }) && /android|iphone|ipad/i.test(navigator.userAgent)) {
        try { await navigator.share({ files: [file], title: name }); return; } catch { /* отмена — просто скачаем */ }
      }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    } else if (act === 'import') {
      const [f] = await pickFiles({ multiple: false, accept: 'application/json,.json' });
      if (!f) return;
      try {
        const res = await busy('Восстанавливаю…', async () => importBackup(JSON.parse(await f.text())));
        toast(`Восстановлено: вещей ${res.items}, образов ${res.outfits}`);
        applyTheme(state.settings.theme);
      } catch (err) {
        toast(err.message || 'Не удалось прочитать файл');
      }
    } else if (act === 'persist') {
      const ok = await navigator.storage.persist();
      toast(ok ? 'Готово: браузер не будет чистить данные сам' : 'Браузер отказал — установите приложение на экран «Домой»');
    } else if (act === 'wipe') {
      if (await confirmDialog('Удалить все вещи, образы, лукбуки и календарь? Отменить нельзя.', { ok: 'Удалить всё' })) {
        await wipeAll();
        toast('Все данные удалены');
      }
    }
  });

  root.addEventListener('change', (e) => {
    if (e.target.name === 'currency') saveSettings({ currency: e.target.value.trim() || 'руб.' });
    if (e.target.name === 'aiKey') {
      const v = e.target.value.trim();
      if (v && !v.startsWith('sk-ant-')) toast('Похоже, это не ключ Anthropic — он начинается с sk-ant-');
      saveSettings({ aiKey: v });
      if (v) toast('Ключ сохранён');
    }
  });
}

function chooseCity() {
  const s = openSheet({
    title: 'Город',
    className: 'tall',
    body: html`<form class="prompt-form"><input class="input" type="search" placeholder="Название города" value="${city().name}"><button class="btn primary">Найти</button></form><div class="action-list city-results"></div>`,
  });
  const list = s.body.querySelector('.city-results');
  let found = [];
  s.body.querySelector('form').onsubmit = async (e) => {
    e.preventDefault();
    const q = e.target.querySelector('input').value.trim();
    if (!q) return;
    list.innerHTML = '<p class="hint" style="padding:12px 16px">Ищу…</p>';
    try {
      found = await searchCity(q);
      list.innerHTML = found.length
        ? String(html`${found.map((c, i) => html`<button class="action" data-i="${i}"><span><b>${c.name}</b><br><small class="muted">${c.region}</small></span></button>`)}`)
        : '<p class="hint" style="padding:12px 16px">Ничего не нашлось</p>';
    } catch (err) {
      list.innerHTML = String(html`<p class="hint" style="padding:12px 16px">${err.message}. Нужен интернет.</p>`);
    }
  };
  list.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-i]');
    if (!b) return;
    await setCity(found[+b.dataset.i]);
    s.close();
    toast(`Город: ${found[+b.dataset.i].name}`);
  });
}
