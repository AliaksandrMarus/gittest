/**
 * Единственная точка правки контактов, цен, характеристик техники и интеграций.
 * Шапка, подвал, формы, JSON-LD и кнопки связи читают значения отсюда,
 * поэтому расхождений между страницами быть не может.
 *
 * Данные перенесены со старого сайта manipulator-bobruisk.by.
 */

export const site = {
  name: 'Манипулятор Бобруйск',
  legalName: 'ИП Бобруйко Г. В.',
  unp: '791394491',
  registration: 'Свидетельство о регистрации № 0908740',
  tagline: 'Кран-манипулятор и мини-экскаватор в Бобруйске',
  slogan: 'Загрузим. Завезём. Выгрузим. Выкопаем.',
  /** На превью подменяется переменной SITE_URL; по умолчанию боевой домен. */
  url: import.meta.env.SITE?.replace(/\/$/, '') ?? 'https://manipulator-bobruisk.by',
} as const;

export const contacts = {
  /** Как показываем человеку. */
  phoneHuman: '+375 44 499-82-22',
  /** Как уходит в tel:, мессенджеры и JSON-LD. */
  phoneRaw: '+375444998222',
  /** TODO: почта для заявок и подвала. Пустая строка — не показывается. */
  email: '',
  /** Ссылки по номеру телефона. Проверьте, что Telegram и Viber открываются на этот номер. */
  telegram: 'https://t.me/+375444998222',
  viber: 'viber://chat?number=%2B375444998222',
  city: 'Бобруйск',
  region: 'Могилёвская область',
  country: 'BY',
  /** Центр Бобруйска — для гео-метатегов. Адреса базы на сайте нет: техника выезжает к заказчику. */
  geo: { lat: 53.1384, lon: 29.2214 },
  areaHuman: 'Бобруйск, Бобруйский район, Могилёвская область и вся Беларусь',
  /** Ближайшие города — для текста «где работаем» и разметки. Проверьте, что ездите туда. */
  towns: ['Бобруйск', 'Бобруйский район', 'Кировск', 'Глуск', 'Осиповичи', 'Рогачёв', 'Жлобин', 'Светлогорск', 'Березино', 'Кличев'],
  areaServed: ['Бобруйск', 'Бобруйский район', 'Кировск', 'Глуск', 'Осиповичи', 'Рогачёв', 'Могилёвская область', 'Беларусь'],
} as const;

export const hours = {
  human: 'Круглосуточно, без выходных',
  short: '24/7',
} as const;

/** Техника. Пустая строка — характеристика не выводится. */
export const fleet = {
  manipulator: {
    /** По фото: шасси DAF LF, кран Palfinger PK 8500. */
    model: 'DAF LF · Palfinger PK 8500',
    crane: '5 т',
    boom: '10 м',
    /** TODO: длина и ширина кузова. */
    body: '',
    /** TODO: грузоподъёмность бортовой платформы. */
    payload: '',
  },
  excavator: {
    /** Японский мини-экскаватор Kubota (по фото RX-405E). */
    model: 'Kubota RX-405',
    buckets: '30, 40 и 50 см',
    tracks: 'резиновые',
    /** Kubota RX-405 по открытым данным (allstocker.com, untcs.com). Сверьте с паспортом. */
    weight: '3,5 т',
    depth: 'до 3,2 м',
    reach: 'до 4,8 м',
    bucket: '0,11 м³',
  },
} as const;

/**
 * Прайс. price: null — «по запросу». Цены в белорусских рублях.
 * TODO: впишите свои цены. Пока везде «по запросу».
 */
export type PriceRow = { name: string; unit: string; price: number | null; from?: boolean };
export const prices: { group: string; rows: PriceRow[] }[] = [
  {
    group: 'Кран-манипулятор',
    rows: [
      { name: 'Работа по Бобруйску', unit: 'час', price: null, from: true },
      { name: 'Минимальный заказ', unit: 'заказ', price: null },
      { name: 'Выезд за город', unit: 'км', price: null },
      { name: 'Межгород, перевозка по Беларуси', unit: 'рейс', price: null, from: true },
    ],
  },
  {
    group: 'Мини-экскаватор',
    rows: [
      { name: 'Работа с оператором', unit: 'час', price: null, from: true },
      { name: 'Смена, 8 часов', unit: 'смена', price: null },
      { name: 'Копка траншеи', unit: 'пог. м', price: null, from: true },
      { name: 'Доставка экскаватора на объект', unit: 'рейс', price: null, from: true },
    ],
  },
];

/**
 * Куда уходят заявки с форм.
 *  - '/api/lead.php' — обработчик из public/api для хостинга с PHP;
 *  - ''              — форма не притворяется рабочей и показывает телефон и мессенджеры.
 * На превью без PHP передаётся пустая строка через PUBLIC_FORM_ENDPOINT.
 */
export const FORM_ENDPOINT = import.meta.env.PUBLIC_FORM_ENDPOINT ?? '/api/lead.php';

/** Пустая строка — счётчик не подключается. */
export const analytics = {
  yandexMetrika: '103817808',
  ga4: '',
} as const;

export const nav = [
  { href: '/manipulyator/', label: 'Манипулятор' },
  { href: '/mini-ekskavator/', label: 'Мини-экскаватор' },
  { href: '/ceny/', label: 'Цены' },
  { href: '/kontakty/', label: 'Контакты' },
] as const;

export const OPERATOR_CODES = ['25', '29', '33', '44'] as const;
