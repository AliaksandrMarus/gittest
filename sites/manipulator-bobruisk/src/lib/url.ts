import { site } from '../config/site';

/** Базовый путь без завершающего слеша: '' в корне, '/preview' в подпапке. */
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** Внутренняя ссылка с учётом подпапки превью. */
export function link(path: string): string {
  return BASE + path || '/';
}

/** Полный адрес для canonical, Open Graph и разметки. */
export function absolute(path: string): string {
  return new URL(link(path), site.url).href;
}
