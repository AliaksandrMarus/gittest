export const CATEGORIES = [
  { id: 'tops', name: 'Верх', sub: ['Футболка', 'Майка', 'Топ', 'Рубашка', 'Блузка', 'Поло', 'Лонгслив', 'Свитер', 'Водолазка', 'Кардиган', 'Худи', 'Свитшот', 'Жилет'] },
  { id: 'bottoms', name: 'Низ', sub: ['Джинсы', 'Брюки', 'Чиносы', 'Шорты', 'Юбка', 'Леггинсы', 'Спортивные штаны'] },
  { id: 'dresses', name: 'Платья', sub: ['Платье', 'Сарафан', 'Комбинезон', 'Костюм'] },
  { id: 'outerwear', name: 'Верхняя одежда', sub: ['Куртка', 'Пальто', 'Пуховик', 'Парка', 'Тренч', 'Ветровка', 'Бомбер', 'Косуха', 'Пиджак', 'Жакет'] },
  { id: 'shoes', name: 'Обувь', sub: ['Кроссовки', 'Кеды', 'Ботинки', 'Сапоги', 'Туфли', 'Лоферы', 'Мокасины', 'Босоножки', 'Сандалии', 'Шлёпанцы'] },
  { id: 'bags', name: 'Сумки', sub: ['Сумка', 'Рюкзак', 'Шоппер', 'Клатч', 'Поясная сумка', 'Портфель'] },
  { id: 'accessories', name: 'Аксессуары', sub: ['Кепка', 'Шапка', 'Шарф', 'Платок', 'Ремень', 'Очки', 'Часы', 'Перчатки', 'Галстук', 'Носки'] },
  { id: 'jewelry', name: 'Украшения', sub: ['Кольцо', 'Серьги', 'Цепочка', 'Браслет', 'Колье', 'Брошь'] },
  { id: 'other', name: 'Другое', sub: ['Бельё', 'Купальник', 'Пижама', 'Спортивная форма'] },
];

export const catById = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));

export const COLORS = [
  { id: 'black', name: 'Чёрный', hex: '#151515' },
  { id: 'white', name: 'Белый', hex: '#f7f7f5' },
  { id: 'grey', name: 'Серый', hex: '#8f8f8f' },
  { id: 'beige', name: 'Бежевый', hex: '#d8c6a5' },
  { id: 'brown', name: 'Коричневый', hex: '#7a4e2d' },
  { id: 'khaki', name: 'Хаки', hex: '#7f7d4f' },
  { id: 'green', name: 'Зелёный', hex: '#3f8f4f' },
  { id: 'lightblue', name: 'Голубой', hex: '#8ec5ef' },
  { id: 'blue', name: 'Синий', hex: '#2c4f9e' },
  { id: 'navy', name: 'Тёмно-синий', hex: '#1f2a44' },
  { id: 'purple', name: 'Фиолетовый', hex: '#7d4fa0' },
  { id: 'pink', name: 'Розовый', hex: '#f0a3bd' },
  { id: 'red', name: 'Красный', hex: '#cf3030' },
  { id: 'burgundy', name: 'Бордовый', hex: '#76202f' },
  { id: 'orange', name: 'Оранжевый', hex: '#ef8a2b' },
  { id: 'yellow', name: 'Жёлтый', hex: '#f2cf40' },
  { id: 'silver', name: 'Серебристый', hex: '#c3c4ca' },
  { id: 'gold', name: 'Золотой', hex: '#c9a24a' },
  { id: 'multi', name: 'Разноцветный', hex: 'conic-gradient(#cf3030,#f2cf40,#3f8f4f,#2c4f9e,#7d4fa0,#cf3030)' },
];

export const colorById = Object.fromEntries(COLORS.map((c) => [c.id, c]));

export const SEASONS = [
  { id: 'spring', name: 'Весна' },
  { id: 'summer', name: 'Лето' },
  { id: 'autumn', name: 'Осень' },
  { id: 'winter', name: 'Зима' },
];

export const seasonById = Object.fromEntries(SEASONS.map((s) => [s.id, s]));

/** Сезон по месяцу: декабрь–февраль зима и так далее. */
export function currentSeason(date = new Date()) {
  const m = date.getMonth();
  if (m === 11 || m <= 1) return 'winter';
  if (m <= 4) return 'spring';
  if (m <= 7) return 'summer';
  return 'autumn';
}

/** Фоны холста для образов. */
export const STAGE_BGS = ['#ffffff', '#f1efeb', '#e9e3d8', '#dfe6ea', '#f3e1e1', '#1c1c1c'];
