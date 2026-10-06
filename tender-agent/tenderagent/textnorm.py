"""Нормализация русских наименований товаров для сравнения без интернета."""
from __future__ import annotations

import re

_ENDINGS = sorted(
    """
    ями ями ами ов ев ей ий ый ой ая яя ое ее ые ие ых их ым им ую юю ого его ому ему
    ом ем ам ям ах ях ию ия ья ье ьи ью а я о е ы и у ю ь й
    """.split(),
    key=len,
    reverse=True,
)

_STOP = {
    "и", "в", "во", "на", "для", "с", "со", "из", "по", "к", "от", "до", "или", "не",
    "шт", "штука", "штук", "упак", "уп", "компл", "комплект", "ед", "изм",
    "тип", "марка", "модель", "артикул", "арт", "гост", "ту", "стб", "либо",
    "эквивалент", "аналог", "аналогичный", "аналогичн", "товар", "поставка", "закупка",
}

_SHORT_WORDS = [
    (r"\bа/шин", "автошин"),
    (r"\bа/покрышк", "автошин"),          # покрышка = шина для сравнения
    (r"\bа/камер", "автокамер"),
    (r"\bа/м\b", "автомобиль"),
    (r"\bа/мобил", "автомобил"),
    (r"\bэ/ламп", "электролампа"),
    (r"\bэл\.\s?", "электро"),
    (r"\bхоз\.\s?", "хозяйственн"),
    (r"\bканц\.\s?", "канцелярск"),
    (r"\bпокрышк", "шин"),
]

_TRANSLIT = str.maketrans({"ё": "е", "Ё": "е"})
_LAT2CYR = str.maketrans("aceopxyk", "асеорхук")  # похожие латинские буквы в марках
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_TOKEN_RE = re.compile(r"[a-zа-я0-9]+(?:[.,]\d+)?", re.I)


def stem(word: str) -> str:
    if len(word) <= 3 or word.isdigit():
        return word
    for e in _ENDINGS:
        if word.endswith(e) and len(word) - len(e) >= 3:
            return word[: -len(e)]
    return word


def normalize(text: str) -> str:
    text = (text or "").translate(_TRANSLIT).lower()
    # «3х2,5», «3x2.5», «3*2,5» → «3 x 2.5»
    text = re.sub(r"(\d)\s*[хx*×]\s*(\d)", r"\1 x \2", text)
    # Сокращения из прайсов 1С: «А/ШИНА», «А/М», «Э/ЛАМПА»…
    for short, full in _SHORT_WORDS:
        text = re.sub(short, full, text)
    # «R16C»/«R16С» — грузовое (C, cargo) исполнение шины: отдельная метка, а не предлог «с»
    text = re.sub(r"(?<=\d)[сc]\b", " cargo", text)
    # «75R16C» → «75 r 16 c»: размер шин, марки кабеля и т.п. сравниваются по частям
    text = re.sub(r"(?<=\d)(?=[a-zа-я])|(?<=[a-zа-я])(?=\d)", " ", text)
    text = re.sub(r"(\d),(\d)", r"\1.\2", text)
    return text


def tokens(text: str) -> list[str]:
    out = []
    for t in _TOKEN_RE.findall(normalize(text)):
        t = t.replace(",", ".")
        if t in _STOP:
            continue
        if re.fullmatch(r"[a-z]+", t) and len(t) <= 4:
            # Марки вроде «ВВГ» латиницей пишут вперемешку с кириллицей.
            t = t.translate(_LAT2CYR)
        st = stem(t)
        if st in _STOP:
            continue
        out.append(st)
    return out


def numbers(text: str) -> set[str]:
    return {n.replace(",", ".").rstrip("0").rstrip(".") or "0" for n in _NUM_RE.findall(normalize(text))}


def key(text: str) -> str:
    """Короткий ключ для запоминания ручных сопоставлений."""
    return " ".join(tokens(text))


_ABBR = {
    "канцтовар": ["канцелярские товары", "канцелярские принадлежности"],
    "хозтовар": ["хозяйственные товары"],
    "стройматериал": ["строительные материалы"],
    "спецодежд": ["специальная одежда"],
    "электротовар": ["электротехническая продукция", "электротехнические товары"],
    "оргтехник": ["организационная техника"],
    "сантехник": ["санитарно-техническ"],
}


def contains_keyword(text: str, keyword: str) -> bool:
    """Все слова ключевой фразы встречаются в тексте (с учётом окончаний и сокращений)."""
    if _contains(text, keyword):
        return True
    low = normalize(keyword)
    for abbr, full in _ABBR.items():
        if abbr in low:
            if any(_contains(text, low.replace(m, f) if (m := next(
                    (w for w in low.split() if w.startswith(abbr)), "")) else f) for f in full):
                return True
    return False


def _contains(text: str, keyword: str) -> bool:
    kw = tokens(keyword)
    if not kw:
        return False
    tt = tokens(text)
    for k in kw:
        if not any(t.startswith(k) or k.startswith(t) and len(t) >= 4
                   or len(k) >= 3 and t.endswith(k) for t in tt):  # «шины» ⊂ «автошины»
            return False
    return True


# Типоразмер шины: 215/75R16, 215/75 R16C, 185/65 R15, 10.00R20, 11.2-20, 12,5/80-15,3
_TYRE = re.compile(r"(?<![\d.,/])(\d{2,4}(?:[.,]\d{1,2})?)\s*/\s*(\d{2})\s*(?:z?r|р|-)?\s*(\d{2}(?:[.,]\d)?)"
                   r"|(?<![\d.,/])(\d{1,2}[.,]\d{1,2})\s*(?:r|р|-)\s*(\d{2}(?:[.,]\d)?)(?![\d])", re.I)


def tyre_size(text: str) -> str:
    """Нормализованный типоразмер шины («215/75/16») или пустая строка."""
    m = _TYRE.search((text or "").replace("Р", "R"))
    if not m:
        return ""
    if m.group(1):
        parts = [m.group(1), m.group(2), m.group(3)]
    else:
        parts = [m.group(4), m.group(5)]
    return "/".join(p.replace(",", ".").rstrip("0").rstrip(".") if "." in p.replace(",", ".") else p
                    for p in parts)
