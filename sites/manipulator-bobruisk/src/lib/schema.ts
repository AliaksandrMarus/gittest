import { site, contacts, hours } from '../config/site';
import { absolute } from './url';

const orgId = () => `${site.url}/#organization`;

/** Организация: один и тот же объект на всех страницах. */
export function businessSchema(image: string) {
  return {
    '@context': 'https://schema.org',
    '@type': ['LocalBusiness', 'HomeAndConstructionBusiness'],
    '@id': orgId(),
    name: site.name,
    legalName: site.legalName,
    taxID: site.unp,
    description: `${site.tagline}. Грузоперевозки с краном-манипулятором 5 т и земляные работы мини-экскаватором. ${hours.human}.`,
    url: site.url,
    telephone: contacts.phoneRaw,
    ...(contacts.email ? { email: contacts.email } : {}),
    image,
    currenciesAccepted: 'BYN',
    priceRange: 'от 60 BYN/час',
    paymentAccepted: 'Наличные, безналичный расчёт',
    address: {
      '@type': 'PostalAddress',
      addressLocality: contacts.city,
      addressRegion: contacts.region,
      addressCountry: contacts.country,
    },
    geo: { '@type': 'GeoCoordinates', latitude: contacts.geo.lat, longitude: contacts.geo.lon },
    openingHoursSpecification: [
      {
        '@type': 'OpeningHoursSpecification',
        dayOfWeek: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        opens: '00:00',
        closes: '23:59',
      },
    ],
    areaServed: contacts.areaServed.map((name) => ({ '@type': 'Place', name })),
  };
}

export function websiteSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': `${site.url}/#website`,
    url: site.url,
    name: site.name,
    inLanguage: 'ru-BY',
    publisher: { '@id': orgId() },
  };
}

/** BreadcrumbList. Первый элемент — всегда главная. */
export function breadcrumbSchema(items: { href?: string; label: string }[]) {
  const all = [{ href: '/', label: 'Главная' }, ...items];
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: all.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.label,
      ...(item.href ? { item: absolute(item.href) } : {}),
    })),
  };
}

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

/** Service без выдуманных цен: Offer появляется, только когда цена задана. */
export function serviceSchema(s: { title: string; description: string; path: string; type: string; price?: number | null }) {
  const url = absolute(s.path);
  return {
    '@context': 'https://schema.org',
    '@type': 'Service',
    name: s.title,
    description: s.description,
    url,
    serviceType: s.type,
    provider: { '@id': orgId() },
    areaServed: contacts.areaServed.map((name) => ({ '@type': 'Place', name })),
    ...(s.price
      ? { offers: { '@type': 'Offer', url, priceCurrency: 'BYN', price: s.price, availability: 'https://schema.org/InStock' } }
      : {}),
  };
}
