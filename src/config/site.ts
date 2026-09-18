/**
 * Единственная точка правки контактных данных, графика и интеграций.
 * Всё остальное — шапка, подвал, формы, JSON-LD, кнопки быстрого вызова —
 * читает значения отсюда, поэтому расхождений между страницами быть не может.
 *
 * Данные сверены с карточкой Яндекс.Карт (организация 85057471321).
 */

export const site = {
  name: 'Лайт Он',
  legalName: 'ООО «Лайт ОН»',
  tagline: 'Автомойка и детейлинг в Бобруйске',
  slogan: 'От грязи до идеала. За один визит.',
  /** На превью подменяется переменной SITE_URL; по умолчанию боевой домен. */
  url: import.meta.env.SITE?.replace(/\/$/, '') ?? 'https://lighton.by',
  /** TODO: уточнить УНП — обязателен в подвале для юрлица РБ. */
  unp: '',
} as const;

export const contacts = {
  /** Как показываем человеку. */
  phoneHuman: '+375 25 987-10-10',
  /** Как уходит в tel: и в JSON-LD. */
  phoneRaw: '+375259871010',
  email: 'lighton9871010@mail.ru',
  telegram: 'https://t.me/+375259871010',
  viber: 'https://viber.click/+375259871010',
  /** Формулировка адреса совпадает с карточкой Яндекса — важно для локального SEO. */
  address: {
    street: 'Минская ул., 123, корп. 8',
    city: 'Бобруйск',
    region: 'Могилёвская область',
    country: 'BY',
    postalCode: '213800',
    full: 'г. Бобруйск, Минская ул., 123, корп. 8',
  },
  geo: { lat: 53.163518, lon: 29.207766 },
  yandexMaps: 'https://yandex.by/maps/org/layt_on/85057471321/',
  yandexOrgId: '85057471321',
  /** Рейтинг показываем визуально со ссылкой на источник, но НЕ размечаем
   *  как AggregateRating: разметка чужих отзывов нарушает правила Google. */
  rating: { value: 4.3, count: 5, reviews: 4 },
} as const;

/**
 * График работы. Индекс — день недели по JS (0 = воскресенье).
 * null означает выходной. Пн–Сб 09:00–19:00, воскресенье закрыто.
 */
export const schedule: ReadonlyArray<{ open: string; close: string } | null> = [
  null,
  { open: '09:00', close: '19:00' },
  { open: '09:00', close: '19:00' },
  { open: '09:00', close: '19:00' },
  { open: '09:00', close: '19:00' },
  { open: '09:00', close: '19:00' },
  { open: '09:00', close: '19:00' },
];

export const scheduleHuman = 'Пн–Сб 09:00–19:00, Вс — выходной';

/** Часовой пояс Минска, без перехода на летнее время. */
export const TZ_OFFSET_HOURS = 3;

/**
 * Куда уходят заявки с форм.
 *
 *  - '/api/lead.php'            — обработчик из public/api для хостинга с PHP;
 *  - 'https://api.web3forms.com/submit' и ключ в FORM_ACCESS_KEY — без бэкенда;
 *  - ''                         — форма не притворяется рабочей и показывает
 *                                 телефон, почту и мессенджеры.
 *
 * Переопределяется переменной PUBLIC_FORM_ENDPOINT на время сборки. На превью
 * в GitHub Pages workflow передаёт пустую строку: PHP там нет, и форма честно
 * показывает телефон с мессенджерами вместо отправки в никуда.
 *
 * Именно import.meta.env, а не process.env: этот файл попадает и в клиентский
 * бандл через скрипт форм, а в браузере process не существует.
 */
export const FORM_ENDPOINT = import.meta.env.PUBLIC_FORM_ENDPOINT ?? '/api/lead.php';
export const FORM_ACCESS_KEY = '';

/** Пустая строка = счётчик не подключается вовсе. */
export const analytics = {
  yandexMetrika: '102469598',
  ga4: '', // TODO: идентификатор потока GA4
} as const;

export const nav = [
  { href: '/', label: 'Главная' },
  { href: '/uslugi/', label: 'Услуги' },
  { href: '/detailing/', label: 'Детейлинг' },
  { href: '/raboty/', label: 'Наши работы' },
  { href: '/o-kompanii/', label: 'О нас' },
  { href: '/kontakty/', label: 'Контакты' },
] as const;

/** Коды белорусских мобильных операторов — используется в валидации форм. */
export const OPERATOR_CODES = ['25', '29', '33', '44'] as const;
