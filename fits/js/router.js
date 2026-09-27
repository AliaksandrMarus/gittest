/**
 * Маршрутизация по hash: #/closet, #/item/<id>, #/builder?item=<id> и т.д.
 * Каждый показ экрана получает новый корневой элемент, поэтому обработчики
 * событий не копятся между перерисовками.
 */
import { closeAllSheets } from './ui.js';

const routes = [];
const stack = [];
let current = null;

export function route(pattern, view, { tab = null, keep = false } = {}) {
  routes.push({ pattern, view, tab, keep });
}

export const go = (path) => { location.hash = '#' + path; };

export function goBack(fallback) {
  if (stack.length > 1) history.back();
  else location.replace('#' + fallback);
}

const parse = () => {
  const raw = location.hash.slice(1) || '/closet';
  const [path, query = ''] = raw.split('?');
  return { raw, path, query: new URLSearchParams(query) };
};

async function render({ keepScroll = false } = {}) {
  const { path, query } = parse();
  for (const r of routes) {
    const m = path.match(r.pattern);
    if (!m) continue;
    const scroll = keepScroll ? window.scrollY : 0;
    current?.cleanup?.();
    const host = document.getElementById('view');
    const root = document.createElement('div');
    root.className = 'view';
    host.replaceChildren(root);
    document.body.dataset.tab = r.tab ?? '';
    document.body.classList.toggle('hide-tabs', !r.tab);
    document.querySelectorAll('.tabbar a').forEach((a) => a.classList.toggle('on', a.dataset.tab === r.tab));
    const cleanup = await r.view(root, m.slice(1).map((x) => x && decodeURIComponent(x)), query);
    current = { route: r, cleanup: typeof cleanup === 'function' ? cleanup : null };
    window.scrollTo(0, scroll);
    return;
  }
  location.replace('#/closet');
}

/** Перерисовать текущий экран (после изменения данных), кроме редакторов. */
export function refresh() {
  if (current?.route.keep) return;
  render({ keepScroll: true });
}

export function startRouter() {
  window.addEventListener('hashchange', () => {
    closeAllSheets();
    const { raw } = parse();
    if (stack.length > 1 && stack[stack.length - 2] === raw) stack.pop();
    else stack.push(raw);
    render();
  });
  stack.push(parse().raw);
  render();
}
