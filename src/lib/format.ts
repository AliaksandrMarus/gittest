/** Форматирование цен. Валюта одна — белорусский рубль. */

export type PriceLike = {
  price: number | null;
  priceMax?: number | null;
  priceNote?: string;
};

/** «25 руб.», «15–25 руб.», «от 100 руб.», «по запросу». */
export function formatPrice(s: PriceLike): string {
  if (s.price === null) return 'по запросу';
  if (s.priceMax) return `${s.price}–${s.priceMax} руб.`;
  const prefix = s.priceNote?.startsWith('от') ? 'от ' : '';
  return `${prefix}${s.price} руб.`;
}

/** Короткая форма для карточек: число отдельно, подпись отдельно. */
export function priceParts(s: PriceLike): { value: string; note: string } {
  if (s.price === null) return { value: 'По запросу', note: 'рассчитаем за 5 минут' };
  const value = s.priceMax ? `${s.price}–${s.priceMax} руб.` : `${s.price} руб.`;
  return { value, note: s.priceNote ?? '' };
}

/** Нижняя граница по всем услугам — для priceRange в JSON-LD. */
export function priceRange(all: PriceLike[]): string {
  const nums = all.flatMap((s) => (s.price === null ? [] : [s.price, s.priceMax ?? s.price]));
  if (!nums.length) return '$$';
  return `${Math.min(...nums)}–${Math.max(...nums)} BYN`;
}
