import { html, pickFiles } from '../util.js';
import { state, saveSettings, exportBackup, importBackup, wipeAll } from '../store.js';
import { icon, toast, confirmDialog, busy } from '../ui.js';
import { goBack } from '../router.js';
import { applyTheme } from '../theme.js';

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
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'back') goBack('/closet');
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
  });
}
