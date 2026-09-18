import { site } from '../config/site';

/** BreadcrumbList для страницы. Первый элемент — всегда главная. */
export function breadcrumbSchema(items: { href?: string; label: string }[]) {
  const all = [{ href: '/', label: 'Главная' }, ...items];
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: all.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.label,
      ...(item.href ? { item: new URL(item.href, site.url).href } : {}),
    })),
  };
}

/** FAQPage. Отдаём только когда вопросов действительно несколько. */
export function faqSchema(faq: { q: string; a: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  };
}

type ServiceInput = {
  title: string;
  description: string;
  path: string;
  price: number | null;
  priceMax?: number | null;
};

/**
 * Service + Offer. Цена берётся из того же frontmatter, что и видимый прайс,
 * поэтому разметка и текст страницы не могут разойтись.
 */
export function serviceSchema(s: ServiceInput) {
  const url = new URL(s.path, site.url).href;

  const offers =
    s.price === null
      ? {
          '@type': 'Offer',
          url,
          availability: 'https://schema.org/InStock',
          priceCurrency: 'BYN',
          priceSpecification: {
            '@type': 'PriceSpecification',
            priceCurrency: 'BYN',
            valueAddedTaxIncluded: true,
          },
        }
      : {
          '@type': 'Offer',
          url,
          availability: 'https://schema.org/InStock',
          priceCurrency: 'BYN',
          ...(s.priceMax
            ? {
                priceSpecification: {
                  '@type': 'PriceSpecification',
                  minPrice: s.price,
                  maxPrice: s.priceMax,
                  priceCurrency: 'BYN',
                  valueAddedTaxIncluded: true,
                },
              }
            : { price: s.price }),
        };

  return {
    '@context': 'https://schema.org',
    '@type': 'Service',
    name: s.title,
    description: s.description,
    url,
    serviceType: s.title,
    provider: { '@id': `${site.url}/#organization` },
    areaServed: { '@type': 'City', name: 'Бобруйск' },
    offers,
  };
}
