"""Распознавание PDF-накладных (ТТН, ТН, счёт-фактура) — без базы данных.

Распознавание полностью локальное:
1. PDF с текстом (выгрузка из учётной программы, «PDF с поиском» со сканера) —
   таблица читается из текстового слоя (pdfplumber);
2. PDF-картинка (обычный скан) — текст распознаётся Tesseract (см. ocr.py).

В обоих случаях ищется шапка таблицы («Наименование», «Количество», «Цена»,
«НДС», «Стоимость с НДС») и по её колонкам разбираются строки; реквизиты
(номер, дата, поставщик) ищутся в тексте документа.

    from invoice_kit.recognize import extract
    ex = extract(Path("накладная.pdf"))   # Extracted(number, date, supplier, lines=[Line…])
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import ocr

class RecognitionError(Exception):
    pass


@dataclass
class Line:
    name: str
    qty: float
    unit: str = ""
    price: float | None = None
    vat: float | None = None
    total: float | None = None


@dataclass
class Extracted:
    number: str = ""
    date: str = ""
    supplier: str = ""
    lines: list[Line] = field(default_factory=list)


# ---- Нормализация названий и единиц ----------------------------------------

def normalize(name: str) -> str:
    name = name.lower().replace("ё", "е")
    return " ".join(re.findall(r"[a-zа-я0-9]+(?:[.,][0-9]+)?", name))


UNITS = {
    "кг": "кг", "kg": "кг", "килограмм": "кг",
    "г": "г", "гр": "г", "g": "г", "грамм": "г",
    "л": "л", "l": "л", "литр": "л",
    "мл": "мл", "ml": "мл",
    "шт": "шт", "штук": "шт", "штука": "шт", "pcs": "шт", "ед": "шт",
    # Латинские двойники, которые выдаёт распознавание сканов
    "kr": "кг", "kt": "кг", "r": "г", "wt": "шт", "ut": "шт", "lut": "шт", "mn": "мл", "mr": "мл",
}
# Сколько базовых единиц в одной единице накладной
FACTORS = {("кг", "г"): 1000, ("г", "кг"): 0.001, ("л", "мл"): 1000, ("мл", "л"): 0.001}


def unit_key(unit: str | None) -> str:
    word = re.sub(r"[^a-zа-яё]", "", (unit or "").lower().replace("ё", "е"))
    return UNITS.get(word, word)


def unit_factor(raw_unit: str, item_unit: str) -> float | None:
    a, b = unit_key(raw_unit), unit_key(item_unit)
    if a == b and a:
        return 1.0
    return FACTORS.get((a, b))


# ---- Числа, даты, реквизиты -------------------------------------------------

def parse_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[\s ]", "", str(value)).replace(",", ".")
    # OCR иногда ставит точку и как разделитель тысяч: 1.000.50 → 1000.50
    if text.count(".") > 1:
        head, _, tail = text.rpartition(".")
        text = head.replace(".", "") + "." + tail
    if not re.fullmatch(r"-?\d+(\.\d+)?", text):
        return None
    return float(text)


MONTHS = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6, "июл": 7, "август": 8,
          "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12}


def parse_date(text: str) -> str:
    """Дата из накладной в ISO; пустая строка, если не разобрать."""
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


ORG = r"(?:ООО|ОАО|ЗАО|ОДО|СООО|ЧУП|ЧТУП|ЧПУП|УП|ИП|000)"
# Строки бланка, где встречаются чужие даты и номера (договор, постановление, путевой лист)
NOT_DOCUMENT = re.compile(r"договор|постановлен|доверенност|путевому|листу|основание", re.I)


def _textual_date(line: str) -> str:
    for d, month_word, year in re.findall(r"\b(\d{1,2})\s+([а-я]+)\s+(\d{4})", line.lower()):
        for stem, month in MONTHS.items():
            if month_word.startswith(stem) and (stem != "ма" or month_word in ("мая", "май")):
                try:
                    return datetime(int(year), month, int(d)).date().isoformat()
                except ValueError:
                    return ""
    return ""


def find_requisites(text: str, result: Extracted) -> None:
    lines = [l for l in text.splitlines() if l.strip()]
    doc_lines = [l for l in lines if not NOT_DOCUMENT.search(l)]

    # Номер: в строке с «накладная» (или следующей) — «№ …» либо номер бланка из 6–8 цифр
    for i, line in enumerate(lines):
        if "накладн" in line.lower():
            for cand in (line, lines[i + 1] if i + 1 < len(lines) else ""):
                if m := re.search(r"№\s*([A-ZА-Я]{0,4}\s?[0-9][0-9A-ZА-Я\-/]*)", cand, re.I):
                    result.number = m.group(1).replace(" ", "")
                elif m := re.search(r"\b(\d{6,8})\b", cand):
                    result.number = m.group(1)
                if result.number:
                    break
        if result.number:
            break
    if not result.number:
        for line in doc_lines:
            if m := re.search(r"№\s*([A-ZА-Я]{0,4}\s?[0-9][0-9A-ZА-Я\-/]*)", line, re.I):
                result.number = m.group(1).replace(" ", "")
                break

    # Дата: «17 июня 2026 г.» надёжнее; числовая — только свежая и не из договора/бланка
    for line in doc_lines:
        if day := _textual_date(line):
            result.date = day
            break
    if not result.date:
        for line in doc_lines:
            for cand in re.findall(r"\b(\d{1,2}[./]\d{1,2}[./]\d{2,4})\b", line):
                day = parse_date(cand.replace("/", "."))
                if day and day >= "2020-01-01":
                    result.date = day
                    break
            if result.date:
                break

    # Поставщик: после «Поставщик/Грузоотправитель/Продавец», если там есть организация;
    # иначе первая организация в кавычках, которая не получатель
    for line in lines:
        if m := re.search(r"(?:Поставщик|Грузоотправитель|Продавец)[:\s]+(.+)", line):
            value = m.group(1).strip()
            if re.search(ORG + r"|[«\"“]", value) and not re.match(r"Грузополуч|Покупател", value):
                if q := re.search(ORG + r"\s*[«\"“]([^»\"”]{2,60})[»\"”]", value):
                    org = re.match(ORG, q.group(0)).group(0).replace("000", "ООО")
                    value = f'{org} "{q.group(1).strip()}"'  # без адреса
                result.supplier = value[:120]
                break
    if not result.supplier:
        for line in lines:
            if re.search(r"получател|плательщик|заказчик|покупател", line, re.I):
                continue
            if m := re.search(ORG + r"\s*[«\"“]([^»\"”]{2,60})[»\"”]", line):
                org = re.match(ORG, m.group(0)).group(0).replace("000", "ООО")
                result.supplier = f'{org} "{m.group(1).strip()}"'
                break


# ---- Колонки таблицы --------------------------------------------------------

def classify_header(label: str) -> str | None:
    """По заголовку колонки определяет, что в ней: name, unit, qty, price, vat, total, amount."""
    low = " " + re.sub(r"\s+", " ", label.lower().replace("ё", "е")) + " "
    low = low.translate(str.maketrans("aceopxyk", "асеорхук"))  # латинские двойники из скана
    low = re.sub(r"\bн[оo]с\b", "ндс", low)  # «НДС», прочитанный как «НОС»
    if "цена" in low:
        return "price"
    if re.search(r"мест|грузов|масс|примеч", low):
        return "skip"  # «Количество грузовых мест», «Масса груза» — не количество товара
    if re.fullmatch(r" (№|n|no|nn)\.?( п/п)? ", low) or "п/п" in low:
        return "num"  # порядковый номер строки — не часть названия
    if "наимен" in low or "товар" in low and "кол" not in low:
        return "name"
    if "кол" in low or "чество" in low:  # «Коли-чество» в шапке часто разорвано переносом
        return "qty"
    if "цена" in low:
        return "price"
    if "ставк" in low or "%" in low:
        return "rate"
    if "ндс" in low and (" с ндс" in low or "всего" in low or "стоим" in low and re.search(r"\bс\b", low)):
        return "total"
    if "всего" in low or "итого" in low:
        return "total"
    if "ндс" in low:
        return "vat"
    if re.search(r"\bед\b|единиц", low) or "изм" in low:
        return "unit"
    if "стоим" in low or "сумма" in low:
        return "amount"
    return None


def _make_line(cells: dict[str, str]) -> Line | None:
    # Порядковый номер, прилипший к названию, если колонку «№» не распознали
    name = re.sub(r"^\d{1,3}[.)]?\s+(?=\D)", "", (cells.get("name") or "").strip(" |"))
    if not name or not re.search(r"[A-Za-zА-Яа-яЁё]{2}", name) or name.lower().startswith(("итого", "всего")):
        return None
    values, merged = _split_numeric_cells(cells)
    qty, price, amount, vat, total = (values.get(k) for k in ("qty", "price", "amount", "vat", "total"))
    if amount is None and total is not None and vat is not None:
        # Без колонки НДС нельзя понять, есть ли он в сумме, — тогда не сверяем
        amount = round(total - vat, 2)
    if qty is None and price and amount:
        # Одиночную цифру количества скан часто теряет — восстанавливаем из «стоимость / цена»
        derived = amount / price
        if derived > 0 and _has_decimals(derived, 3):
            qty = round(derived, 3)
    if qty is None or qty <= 0:
        return None
    if not merged:  # из слипшихся колонок стоимость ненадёжна — количество по ней не правим
        qty, price = reconcile(qty, price, amount)
    if total is None:
        base = amount if amount is not None else (qty * price if price is not None else None)
        if base is not None:
            total = round(base + (vat or 0), 2)
    unit = (cells.get("unit") or "").strip()
    if unit_key(unit) in CANONICAL_UNITS:
        unit = unit_key(unit)  # «kt», «КГ» → «кг»
    return Line(name, qty, unit, price, vat, total)


CANONICAL_UNITS = {"кг", "г", "л", "мл", "шт"}

# Порядок числовых граф в ТТН/ТН слева направо
NUMERIC_ORDER = ("qty", "price", "amount", "rate", "vat", "total")


def parse_cell_numbers(text: str | None) -> list[float]:
    """Все числа ячейки. «1 000,50» — одно число (пробел перед ровно тремя цифрами — разряды),
    «462.00 92.40» — два: так выглядят слипшиеся соседние колонки."""
    if not text:
        return []
    tokens = re.findall(r"\d+(?:[.,]\d+)?", text.replace("\u00a0", " "))
    numbers: list[str] = []
    for token in tokens:
        if numbers and re.fullmatch(r"\d{3}(?:[.,]\d+)?", token) and re.fullmatch(r"\d{1,3}", numbers[-1]) \
                and re.search(re.escape(numbers[-1]) + r"\s" + re.escape(token), text):
            numbers[-1] += token  # «1 000» — разряды одного числа
        else:
            numbers.append(token)
    return [v for v in (parse_number(n) for n in numbers) if v is not None]


def _split_numeric_cells(cells: dict[str, str]) -> tuple[dict[str, float], bool]:
    """Числа по графам. Лишнее число из ячейки уходит в следующую пустую графу справа:
    если на скане не нашлась линия между колонками, «Стоимость» и «Сумма НДС» слипаются."""
    found = {k: parse_cell_numbers(cells.get(k)) for k in NUMERIC_ORDER}
    merged = False
    for i, key in enumerate(NUMERIC_ORDER):
        extra = found[key][1:]
        if not extra:
            continue
        merged = True
        found[key] = found[key][:1]
        for nxt in NUMERIC_ORDER[i + 1:]:
            if not extra:
                break
            if found[nxt]:
                continue
            if nxt == "rate" and not (extra[0] <= 30 and extra[0] == int(extra[0])):
                continue  # ставка НДС — целый процент, а не сумма
            found[nxt] = [extra.pop(0)]
    return {k: v[0] for k, v in found.items() if v}, merged


def _has_decimals(value: float, digits: int) -> bool:
    return abs(value * 10 ** digits - round(value * 10 ** digits)) < 1e-6


def reconcile(qty: float, price: float | None, amount: float | None) -> tuple[float, float | None]:
    """Сверяет «количество × цена = стоимость» и исправляет неверно прочитанную цифру.

    Если произведение расходится со стоимостью, ошибка в количестве или в цене:
    берём тот вариант, который даёт правдоподобное число (количество до 3 знаков,
    цена до 2 знаков после запятой). Иначе оставляем как есть — строку проверит человек.
    """
    if not price or not amount or price <= 0 or amount <= 0:
        return qty, price
    if abs(qty * price - amount) <= max(0.01 * amount, 0.01):
        return qty, price
    new_qty = amount / price
    if _has_decimals(new_qty, 3):
        return round(new_qty, 3), price
    new_price = amount / qty
    if _has_decimals(new_price, 2):
        return qty, round(new_price, 2)
    return qty, price


def lines_from_table(table: list[list]) -> list[Line]:
    """Строки из таблицы с линиями (pdfplumber.extract_tables)."""
    columns: dict[int, str] | None = None
    lines: list[Line] = []
    rows = [[(c or "").replace("\n", " ").strip() if c is not None else None for c in row] for row in table]
    i = 0
    while i < len(rows):
        row = rows[i]
        if columns is None:
            labels = [c or "" for c in row]
            kinds = [classify_header(c) for c in labels]
            if "name" in kinds and "qty" in kinds:
                # Шапка в две строки: «НДС» объединён над «Ставка» и «Сумма»
                if i + 1 < len(rows) and all(parse_number(c) is None for c in rows[i + 1] if c):
                    nxt = rows[i + 1]
                    top = ""
                    merged = []
                    for j, c in enumerate(row):
                        top = c if c is not None else top
                        below = nxt[j] if j < len(nxt) and nxt[j] else ""
                        merged.append(f"{top if c is None or below else c} {below}".strip())
                    kinds = [classify_header(c) for c in merged]
                    i += 1
                columns = {j: k for j, k in enumerate(kinds) if k}
            i += 1
            continue
        cells: dict[str, str] = {}
        for j, kind in columns.items():
            if j < len(row) and row[j] and kind not in cells:
                cells[kind] = row[j]
        if (cells.get("name") or "").lower().startswith(("итого", "всего")):
            break
        if line := _make_line(cells):
            lines.append(line)
        elif lines and cells.get("name") and not cells.get("qty"):
            lines[-1].name += " " + cells["name"]  # перенос названия на вторую строку
        i += 1
    return lines


def _group_rows(words: list[dict]) -> list[list[dict]]:
    if not words:
        return []
    heights = sorted(w["bottom"] - w["top"] for w in words)
    tolerance = max(heights[len(heights) // 2] * 0.6, 2)
    rows: list[list[dict]] = []
    row_mid = 0.0
    for w in sorted(words, key=lambda w: (w["top"] + w["bottom"]) / 2):
        mid = (w["top"] + w["bottom"]) / 2
        if rows and abs(mid - row_mid) <= tolerance:
            rows[-1].append(w)
        else:
            rows.append([w])
            row_mid = mid
    return [sorted(r, key=lambda w: w["x0"]) for r in rows]


def _column_groups(header_words: list[dict], line_h: float) -> list[dict]:
    """Слова шапки (одной или нескольких строк) группируются в колонки по перекрытию по x.

    Пробел между словами в ячейке заметно уже промежутка между колонками.
    """
    groups: list[dict] = []
    for w in sorted(header_words, key=lambda w: w["x0"]):
        if groups and w["x0"] <= groups[-1]["x1"] + 0.8 * line_h:
            g = groups[-1]
            g["x1"] = max(g["x1"], w["x1"])
            g["words"].append(w)
        else:
            groups.append({"x0": w["x0"], "x1": w["x1"], "words": [w]})
    for g in groups:
        g["label"] = " ".join(w["text"] for w in
                              sorted(g["words"], key=lambda w: (round(w["top"] / line_h), w["x0"])))
        g["kind"] = classify_header(g["label"])
    return groups


def _groups_from_vlines(header_words: list[dict], vlines, top: float, bottom: float) -> list[dict]:
    """Колонки по вертикальным линиям таблицы, пересекающим шапку."""
    mid = (top + bottom) / 2
    xs = sorted({round(x) for x, y0, y1 in vlines if y0 - 2 <= mid <= y1 + 2})
    groups = []
    for x0, x1 in zip(xs, xs[1:]):
        if x1 - x0 < 6:
            continue
        words = [w for w in header_words if x0 <= (w["x0"] + w["x1"]) / 2 < x1]
        label = " ".join(w["text"] for w in sorted(words, key=lambda w: (round(w["top"] / 4), w["x0"])))
        groups.append({"x0": x0, "x1": x1, "words": words, "label": label,
                       "kind": classify_header(label) or "skip"})
    return _fix_kinds(groups)


def _fix_kinds(groups: list[dict]) -> list[dict]:
    """Две колонки «Стоимость» без явной «с НДС»: правая — стоимость с НДС (порядок граф ТТН/ТН)."""
    amounts = [g for g in groups if g["kind"] == "amount"]
    if len(amounts) >= 2 and not any(g["kind"] == "total" for g in groups):
        amounts[-1]["kind"] = "total"
    names = [g for g in groups if g["kind"] == "name"]
    for g in names[1:]:
        g["kind"] = "skip"  # наименование одно — самая левая такая колонка
    return groups


def lines_from_words(words: list[dict], vlines=None) -> list[Line]:
    """Строки накладной из слов с координатами (текстовый слой без линий или OCR)."""
    rows = _group_rows(words)
    if not rows:
        return []
    heights = sorted(w["bottom"] - w["top"] for w in words)
    line_h = heights[len(heights) // 2]
    def is_header(text: str, word: str) -> bool:
        # «(наименование, адрес)», «Товарный раздел», «Товарно-транспортная» — подписи бланка, не шапка
        return word in text and not re.search(r"адрес|раздел|транспорт|документ", text)

    texts = [" ".join(w["text"] for w in row).lower() for row in rows]
    candidates = [i for i, t in enumerate(texts) if is_header(t, "наимен")] + \
                 [i for i, t in enumerate(texts) if is_header(t, "товар") and not is_header(t, "наимен")]
    for idx in candidates:
        row = rows[idx]
        # Шапка занимает несколько строк: берём соседние строки без чисел
        top = min(w["top"] for w in row)
        header_rows = [r for r in rows[max(0, idx - 3):idx + 5]
                       if abs(min(w["top"] for w in r) - top) <= 3.5 * line_h
                       and not any(parse_number(w["text"]) is not None for w in r)
                       and not re.search(r"раздел|транспорт", " ".join(w["text"] for w in r).lower())]
        last = max(rows.index(r) for r in header_rows)
        header = [w for r in header_rows for w in r]
        groups = []
        if vlines:
            groups = _groups_from_vlines(header, vlines, min(w["top"] for w in row),
                                         max(w["bottom"] for w in row))
        if not any(g["kind"] == "qty" for g in groups) or not any(g["kind"] == "name" for g in groups):
            groups = [g for g in _column_groups(header, line_h) if g["kind"]]
        if not any(g["kind"] == "qty" for g in groups):
            continue
        return _rows_to_lines(rows[last + 1:], groups)
    return []


def _rows_to_lines(rows: list[list[dict]], groups: list[dict]) -> list[Line]:
    name_group = next((g for g in groups if g["kind"] == "name"), None)
    first_number_x = min((g["x0"] for g in groups if g["kind"] not in ("name", "skip", "num")), default=None)
    lines: list[Line] = []
    for row in rows:
        cells: dict[str, list[str]] = {}
        for w in row:
            center = (w["x0"] + w["x1"]) / 2
            inside = [g for g in groups if g["x0"] - 3 <= center <= g["x1"] + 3]
            if inside:
                g = inside[0]
            elif name_group and first_number_x is not None and center < first_number_x:
                g = name_group  # длинное название вылезает за шапку
            else:
                g = min(groups, key=lambda g: abs((g["x0"] + g["x1"]) / 2 - center))
            if g["kind"] != "skip":
                cells.setdefault(g["kind"], []).append(w["text"])
        joined = {k: " ".join(v) for k, v in cells.items()}
        first = " ".join(w["text"] for w in row[:2]).lower()
        if first.startswith(("итого", "всего")):
            break
        if line := _make_line(joined):
            lines.append(line)
        elif lines and joined.get("name") and "qty" not in joined:
            lines[-1].name += " " + joined["name"]
    return lines


# ---- Распознавание файла ----------------------------------------------------

def extract(path: Path, tesseract_path: str = "") -> Extracted:
    import pdfplumber

    result = Extracted()
    text_parts: list[str] = []
    word_pages: list[list[dict]] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
                word_pages.append(page.extract_words(keep_blank_chars=False, use_text_flow=False))
                for table in page.extract_tables():
                    result.lines.extend(lines_from_table(table))
    except Exception as e:  # noqa: BLE001
        raise RecognitionError(f"Не удалось открыть PDF: {e}") from e

    text = "\n".join(text_parts)
    if not result.lines and text.strip():
        for words in word_pages:
            result.lines.extend(lines_from_words(words))
    if not text.strip():
        # Скан-картинка: распознаём изображение
        try:
            pages = ocr.ocr_pdf(path, tesseract_path)
        except ocr.OcrUnavailable as e:
            raise RecognitionError(f"PDF без текста (скан), а распознать картинку нельзя: {e}") from e
        for page in pages:
            result.lines.extend(lines_from_words(page.words, page.vlines))
        text = "\n".join(" ".join(w["text"] for w in row) for page in pages for row in _group_rows(page.words))
    find_requisites(text, result)
    if not result.lines:
        raise RecognitionError("Не нашёл в накладной таблицу с колонками «Наименование» и «Количество». "
                               "Заполните накладную вручную.")
    return result

