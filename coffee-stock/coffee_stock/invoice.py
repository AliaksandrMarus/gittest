"""Распознавание PDF-накладных и оприходование их строк.

Распознавание полностью локальное:
1. PDF с текстом (выгрузка из учётной программы, «PDF с поиском» со сканера) —
   таблица читается из текстового слоя;
2. PDF-картинка (обычный скан) — текст распознаётся встроенным Tesseract.

В обоих случаях ищется шапка таблицы («Наименование», «Количество», «Цена»,
«НДС», «Стоимость с НДС») и по её колонкам разбираются строки. Всё, что
распознано неточно, правится вручную в карточке накладной.

Названия из накладной сопоставляются с ингредиентами. Однажды подтверждённое
сопоставление (и коэффициент пересчёта, например «1 упаковка = 1000 г»)
запоминается и дальше применяется автоматически.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import core, ocr


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
    "kr": "кг", "r": "г", "wt": "шт", "mn": "мл",
}
# Сколько базовых единиц в одной единице накладной
FACTORS = {("кг", "г"): 1000, ("г", "кг"): 0.001, ("л", "мл"): 1000, ("мл", "л"): 0.001}


def unit_key(unit: str | None) -> str:
    word = re.sub(r"[^a-zа-яё]", "", (unit or "").lower().replace("ё", "е"))
    return UNITS.get(word, word)


def unit_factor(raw_unit: str, ingredient_unit: str) -> float | None:
    a, b = unit_key(raw_unit), unit_key(ingredient_unit)
    if a == b and a:
        return 1.0
    return FACTORS.get((a, b))


def _stems(text: str) -> set[str]:
    return {w[:4] for w in normalize(text).split() if len(w) > 3 and not w[0].isdigit()}


def guess_ingredient(conn: sqlite3.Connection, raw_name: str) -> int | None:
    """Ищет ингредиент, все значимые слова которого встречаются в названии строки."""
    raw = _stems(raw_name)
    hits = [r["id"] for r in conn.execute("SELECT id, name FROM ingredients")
            if (s := _stems(r["name"])) and s <= raw]
    return hits[0] if len(hits) == 1 else None


def alias_key(raw_name: str, raw_unit: str) -> str:
    return f"{normalize(raw_name)}|{unit_key(raw_unit)}"


def match_line(conn: sqlite3.Connection, raw_name: str, raw_unit: str) -> tuple[int | None, float | None, bool]:
    """Возвращает (ингредиент, коэффициент, игнорировать) для строки накладной."""
    alias = conn.execute("SELECT ingredient_id, factor, ignored FROM aliases WHERE raw_name = ?",
                         (alias_key(raw_name, raw_unit),)).fetchone()
    if alias:
        return alias["ingredient_id"], alias["factor"], bool(alias["ignored"])
    ingredient_id = guess_ingredient(conn, raw_name)
    if ingredient_id is None:
        return None, None, False
    unit = conn.execute("SELECT unit FROM ingredients WHERE id = ?", (ingredient_id,)).fetchone()["unit"]
    return ingredient_id, unit_factor(raw_unit, unit), False


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


def find_requisites(text: str, result: Extracted) -> None:
    if m := re.search(r"№\s*([A-ZА-Я]{0,4}\s?[0-9][0-9A-ZА-Я\-/]*)", text, re.I):
        result.number = m.group(1).replace(" ", "")
    if m := re.search(r"\b(\d{1,2}[./]\d{1,2}[./]\d{2,4})\b", text):
        result.date = parse_date(m.group(1).replace("/", "."))
    if not result.date and (m := re.search(r"\b(\d{1,2})\s+([а-я]+)\s+(\d{4})", text.lower())):
        for stem, month in MONTHS.items():
            if m.group(2).startswith(stem) and (stem != "ма" or m.group(2) in ("мая", "май")):
                try:
                    result.date = datetime(int(m.group(3)), month, int(m.group(1))).date().isoformat()
                except ValueError:
                    pass
                break
    if m := re.search(r"(?:Поставщик|Грузоотправитель|Продавец)[:\s]+(.+)", text):
        result.supplier = m.group(1).strip()[:120]


# ---- Колонки таблицы --------------------------------------------------------

def classify_header(label: str) -> str | None:
    """По заголовку колонки определяет, что в ней: name, unit, qty, price, vat, total, amount."""
    low = " " + re.sub(r"\s+", " ", label.lower().replace("ё", "е")) + " "
    if "наимен" in low or "товар" in low and "кол" not in low:
        return "name"
    if "кол" in low:
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
    name = (cells.get("name") or "").strip(" |")
    qty = parse_number(cells.get("qty"))
    if not name or qty is None or qty <= 0 or name.lower().startswith(("итого", "всего")):
        return None
    price, vat = parse_number(cells.get("price")), parse_number(cells.get("vat"))
    total, amount = parse_number(cells.get("total")), parse_number(cells.get("amount"))
    if total is None:
        base = amount if amount is not None else (qty * price if price is not None else None)
        if base is not None:
            total = round(base + (vat or 0), 2)
    return Line(name, qty, (cells.get("unit") or "").strip(), price, vat, total)


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


def lines_from_words(words: list[dict]) -> list[Line]:
    """Строки накладной из слов с координатами (текстовый слой без линий или OCR)."""
    rows = _group_rows(words)
    if not rows:
        return []
    heights = sorted(w["bottom"] - w["top"] for w in words)
    line_h = heights[len(heights) // 2]
    for idx, row in enumerate(rows):
        text = " ".join(w["text"] for w in row).lower()
        if "наимен" not in text and "товар" not in text:
            continue
        # Шапка занимает несколько строк: берём соседние строки без чисел
        top = min(w["top"] for w in row)
        header_rows = [r for r in rows[max(0, idx - 2):idx + 4]
                       if abs(min(w["top"] for w in r) - top) <= 3.5 * line_h
                       and not any(parse_number(w["text"]) is not None for w in r)]
        last = max(rows.index(r) for r in header_rows)
        groups = [g for g in _column_groups([w for r in header_rows for w in r], line_h) if g["kind"]]
        if not any(g["kind"] == "qty" for g in groups):
            continue
        return _rows_to_lines(rows[last + 1:], groups)
    return []


def _rows_to_lines(rows: list[list[dict]], groups: list[dict]) -> list[Line]:
    name_group = next((g for g in groups if g["kind"] == "name"), None)
    first_number_x = min((g["x0"] for g in groups if g["kind"] != "name"), default=None)
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
        for words in pages:
            result.lines.extend(lines_from_words(words))
        text = "\n".join(" ".join(w["text"] for w in row) for words in pages for row in _group_rows(words))
    find_requisites(text, result)
    if not result.lines:
        raise RecognitionError("Не нашёл в накладной таблицу с колонками «Наименование» и «Количество». "
                               "Заполните накладную вручную.")
    return result


# ---- Запись в базу ---------------------------------------------------------

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_by_hash(conn: sqlite3.Connection, digest: str):
    return conn.execute("SELECT id, status FROM invoices WHERE file_hash = ?", (digest,)).fetchone()


def find_same_document(conn: sqlite3.Connection, ex: Extracted, exclude_id: int | None = None):
    if not ex.number or not ex.date:
        return None
    return conn.execute(
        "SELECT id, file_name FROM invoices WHERE status != 'error' AND doc_number = ? AND doc_date = ? "
        "AND COALESCE(supplier, '') = ? AND id != ?",
        (ex.number, ex.date, ex.supplier, exclude_id or -1),
    ).fetchone()


def save_error(conn: sqlite3.Connection, file_name: str, digest: str, message: str) -> int:
    with conn:
        return conn.execute(
            "INSERT INTO invoices(file_name, file_hash, status, note) VALUES (?, ?, 'error', ?)",
            (file_name, digest, message),
        ).lastrowid


def _insert_lines(conn: sqlite3.Connection, invoice_id: int, lines: list[Line]) -> None:
    for line in lines:
        ingredient_id, factor, ignored = match_line(conn, line.name, line.unit)
        conn.execute(
            "INSERT INTO invoice_lines(invoice_id, raw_name, raw_qty, raw_unit, price, vat, total, "
            "ingredient_id, factor, ignored) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (invoice_id, line.name, line.qty, line.unit, line.price, line.vat, line.total,
             ingredient_id, factor, int(ignored)),
        )


def save_extracted(conn: sqlite3.Connection, file_name: str, digest: str, ex: Extracted) -> tuple[int, str]:
    """Сохраняет распознанную накладную; если все строки сопоставлены — сразу проводит."""
    with conn:
        invoice_id = conn.execute(
            "INSERT INTO invoices(file_name, file_hash, doc_number, doc_date, supplier, status) "
            "VALUES (?, ?, ?, ?, ?, 'review')",
            (file_name, digest, ex.number, ex.date, ex.supplier),
        ).lastrowid
        _insert_lines(conn, invoice_id, ex.lines)
    if unresolved_lines(conn, invoice_id) == 0 and ex.lines and ex.date:
        post_invoice(conn, invoice_id)
        return invoice_id, "posted"
    return invoice_id, "review"


@dataclass
class EditedLine:
    """Строка из карточки накладной, как её оставил пользователь."""
    name: str
    qty: float
    unit: str = ""
    price: float | None = None
    vat: float | None = None
    total: float | None = None
    ingredient_id: int | None = None
    factor: float | None = None
    ignored: bool = False


def save_invoice(conn: sqlite3.Connection, invoice_id: int | None, number: str, doc_date: str,
                 supplier: str, lines: list[EditedLine], post: bool = False) -> int:
    """Сохраняет накладную из карточки (новую или исправленную).

    Если накладная была проведена, приход пересчитывается: старые движения
    удаляются, и она проводится заново (если все строки сопоставлены).
    """
    was_posted = False
    with conn:
        if invoice_id is None:
            invoice_id = conn.execute(
                "INSERT INTO invoices(file_name, file_hash, doc_number, doc_date, supplier, status) "
                "VALUES ('вручную', ?, ?, ?, ?, 'review')",
                (f"manual-{uuid.uuid4()}", number, doc_date, supplier),
            ).lastrowid
        else:
            was_posted = conn.execute("SELECT status FROM invoices WHERE id = ?",
                                      (invoice_id,)).fetchone()["status"] == "posted"
            conn.execute("DELETE FROM movements WHERE invoice_id = ?", (invoice_id,))
            conn.execute("UPDATE invoices SET doc_number = ?, doc_date = ?, supplier = ?, status = 'review', "
                         "note = NULL WHERE id = ?", (number, doc_date, supplier, invoice_id))
        conn.execute("DELETE FROM invoice_lines WHERE invoice_id = ?", (invoice_id,))
        for line in lines:
            conn.execute(
                "INSERT INTO invoice_lines(invoice_id, raw_name, raw_qty, raw_unit, price, vat, total, "
                "ingredient_id, factor, ignored) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (invoice_id, line.name, line.qty, line.unit, line.price, line.vat, line.total,
                 None if line.ignored else line.ingredient_id, line.factor, int(line.ignored)),
            )
    if (post or was_posted) and lines and unresolved_lines(conn, invoice_id) == 0:
        post_invoice(conn, invoice_id)
    return invoice_id


def unresolved_lines(conn: sqlite3.Connection, invoice_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM invoice_lines WHERE invoice_id = ? AND ignored = 0 "
        "AND (ingredient_id IS NULL OR factor IS NULL OR factor <= 0)",
        (invoice_id,),
    ).fetchone()[0]


def update_line(conn: sqlite3.Connection, line_id: int, ingredient_id: int | None,
                factor: float | None, ignored: bool) -> None:
    with conn:
        conn.execute("UPDATE invoice_lines SET ingredient_id = ?, factor = ?, ignored = ? WHERE id = ?",
                     (ingredient_id, factor, int(ignored), line_id))


def post_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Проводит накладную: приход на остатки и запоминание сопоставлений."""
    if unresolved_lines(conn, invoice_id):
        raise ValueError("Не все строки накладной сопоставлены с ингредиентами")
    inv = conn.execute("SELECT doc_date, status FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if inv["status"] == "posted":
        return
    day = inv["doc_date"] or core.today()
    with conn:
        for line in conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (invoice_id,)).fetchall():
            conn.execute(
                "INSERT INTO aliases(raw_name, raw_unit, ingredient_id, factor, ignored) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(raw_name) DO UPDATE SET ingredient_id = excluded.ingredient_id, "
                "factor = excluded.factor, ignored = excluded.ignored",
                (alias_key(line["raw_name"], line["raw_unit"]), unit_key(line["raw_unit"]),
                 line["ingredient_id"], line["factor"] or 1, line["ignored"]),
            )
            if not line["ignored"]:
                core.add_movement(conn, day, line["ingredient_id"], line["raw_qty"] * line["factor"],
                                  "receipt", line["raw_name"], invoice_id)
        conn.execute("UPDATE invoices SET status = 'posted', note = NULL, doc_date = ? WHERE id = ?",
                     (day, invoice_id))


def unpost_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Отменяет проведение — приход убирается с остатков."""
    with conn:
        conn.execute("DELETE FROM movements WHERE invoice_id = ?", (invoice_id,))
        conn.execute("UPDATE invoices SET status = 'review' WHERE id = ?", (invoice_id,))


def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
