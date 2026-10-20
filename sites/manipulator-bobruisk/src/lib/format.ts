import type { PriceRow } from '../config/site';

/** «от 60 руб./час», «по запросу». */
export function formatPrice(row: Pick<PriceRow, 'price' | 'from' | 'unit'>): string {
  if (row.price === null) return 'по запросу';
  return `${row.from ? 'от ' : ''}${row.price} руб./${row.unit}`;
}
