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


def contains_keyword(text: str, keyword: str) -> bool:
    """Все слова ключевой фразы встречаются в тексте (с учётом окончаний)."""
    kw = tokens(keyword)
    if not kw:
        return False
    tt = tokens(text)
    for k in kw:
        if not any(t.startswith(k) or k.startswith(t) and len(t) >= 4 for t in tt):
            return False
    return True
