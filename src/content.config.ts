import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const services = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/services' }),
  schema: z.object({
    /** Порядок вывода в каталоге и в меню. */
    order: z.number(),
    /** H1 страницы. */
    title: z.string(),
    /** Короткое имя для карточек, меню и <select> в формах. */
    short: z.string(),
    /** <title> страницы, до 60 символов. */
    seoTitle: z.string(),
    /** <meta name="description">, до 160 символов. */
    description: z.string(),
    /** Подзаголовок под H1. */
    lead: z.string(),
    /** Цена в BYN. null — «по запросу». */
    price: z.number().nullable(),
    /** Уточнение к цене: «за 2 шт.», «от», «за деталь». */
    priceNote: z.string().optional(),
    /** Верхняя граница вилки, если цена «от и до». */
    priceMax: z.number().nullable().optional(),
    /** Ориентировочная длительность работ. */
    duration: z.string(),
    /** Категория прайса в карточке Яндекс.Карт — для сверки. */
    yandexCategory: z.string().optional(),
    /** Имя иконки из components/Icon.astro. */
    icon: z.enum(['droplet', 'engine', 'shield', 'film', 'headlight', 'sofa', 'sparkle']),
    /** Пункты «что входит». */
    includes: z.array(z.string()).min(3),
    /** Этапы работ. */
    steps: z.array(z.object({ title: z.string(), text: z.string() })).min(3),
    /** Вопросы и ответы — идут в FAQPage JSON-LD. */
    faq: z.array(z.object({ q: z.string(), a: z.string() })).min(3),
    /** Alt-текст главной иллюстрации. */
    imageAlt: z.string(),
    /** Часть детейлинг-направления — попадает в /detailing/. */
    detailing: z.boolean().default(false),
  }),
});

export const collections = { services };
