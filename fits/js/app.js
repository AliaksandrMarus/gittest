import { initStore, onChange, state } from './store.js';
import { route, startRouter, refresh } from './router.js';
import { applyTheme } from './theme.js';
import { closetView } from './views/closet.js';
import { itemView } from './views/item.js';
import { outfitsView, outfitView, lookbookView } from './views/outfits.js';
import { builderView } from './views/builder.js';
import { calendarView } from './views/calendar.js';
import { statsView } from './views/stats.js';
import { settingsView } from './views/settings.js';

route(/^\/closet$/, closetView, { tab: 'closet' });
route(/^\/item\/([^/]+)$/, itemView);
route(/^\/outfits$/, outfitsView, { tab: 'outfits' });
route(/^\/outfit\/([^/]+)$/, outfitView);
route(/^\/lookbook\/([^/]+)$/, lookbookView);
route(/^\/builder(?:\/([^/]+))?$/, builderView, { keep: true });
route(/^\/calendar$/, calendarView, { tab: 'calendar' });
route(/^\/stats$/, statsView, { tab: 'stats' });
route(/^\/settings$/, settingsView);

async function main() {
  try {
    await initStore();
  } catch (e) {
    document.getElementById('view').innerHTML =
      '<div class="empty"><h3>Хранилище недоступно</h3><p>Браузер не даёт сохранять данные (например, в режиме инкогнито). Откройте приложение в обычном окне.</p></div>';
    console.error(e);
    return;
  }
  applyTheme(state.settings.theme);
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => applyTheme(state.settings.theme));
  onChange(refresh);
  startRouter();

  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    navigator.serviceWorker.register('sw.js').catch((e) => console.warn('SW:', e));
  }
}

main();
