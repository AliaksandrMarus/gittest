import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const services = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/services' }),
  schema: z.object({
    order: z.number(),
    category: z.enum(['manipulyator', 'mini-ekskavator']),
    /** H1. */
    title: z.string(),
    /** Короткое имя для карточек и меню. */
    short: z.string(),
    /** <title>, до ~65 символов. */
    seoTitle: z.string(),
    /** meta description, до ~160 символов. */
    description: z.string(),
    lead: z.string(),
    /** Описание для карточки. */
    card: z.string(),
    icon: z.enum(['ring', 'bricks', 'container', 'gear', 'trench', 'septic', 'foundation', 'level', 'truck', 'crane', 'excavator']),
    /** Имя файла фото в src/assets/photos без расширения. */
    photo: z.string(),
    photoAlt: z.string(),
    includes: z.array(z.string()).min(3),
    faq: z.array(z.object({ q: z.string(), a: z.string() })).min(3),
  }),
});

export const collections = { services };
