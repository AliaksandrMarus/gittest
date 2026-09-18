import { site } from '../config/site';

/**
 * Адреса с учётом подпапки, в которой развёрнут сайт.
 *
 * На боевом домене сайт лежит в корне, и обе функции возвращают путь как есть.
 * На превью в GitHub Pages он живёт в /gittest/, и всё написанное руками нужно
 * префиксовать: Astro сам правит только те пути, что генерирует — стили,
 * шрифты, картинки из astro:assets. Ссылки в разметке он не трогает.
 *
 * Поэтому правило простое: любой внутренний адрес проходит через link(),
 * любой абсолютный (canonical, og:image, JSON-LD) — через absolute().
 */

/** Базовый путь без завершающего слеша: '' в корне, '/gittest' в подпапке. */
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** Внутренняя ссылка: link('/uslugi/') → '/gittest/uslugi/'. */
export function link(path: string): string {
  return BASE + path || '/';
}

/** Полный адрес страницы для canonical, Open Graph и разметки. */
export function absolute(path: string): string {
  return new URL(link(path), site.url).href;
}
