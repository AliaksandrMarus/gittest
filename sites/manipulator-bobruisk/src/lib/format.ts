import type { PriceRow } from '../config/site';

const num = (n: number) => n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });

/** «от 60 руб./час», «по запросу». */
export function formatPrice(row: Pick<PriceRow, 'price' | 'from' | 'unit'>): string {
  if (row.price === null) return 'по запросу';
  return `${row.from ? 'от ' : ''}${num(row.price)} руб./${row.unit}`;
}
