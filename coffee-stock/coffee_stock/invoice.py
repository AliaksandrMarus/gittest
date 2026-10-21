"""Распознавание PDF-накладных и оприходование их строк.

Два способа распознавания:
* Claude API — читает и сканы-картинки, и PDF с текстом; нужен ключ API
  и интернет;
* без интернета — таблица из текстового слоя PDF (pdfplumber). Работает
  только для PDF, сохранённых из учётной программы, а не для сканов.

Названия из накладной сопоставляются с ингредиентами. Однажды подтверждённое
сопоставление (и коэффициент пересчёта, например «1 упаковка = 1000 г»)
запоминается и дальше применяется автоматически.
"""

from __future__ import annotations

import base64
import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import core


class RecognitionError(Exception):
    pass


@dataclass
class Line:
    name: str
    qty: float
    unit: str = ""


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


# ---- Распознавание ---------------------------------------------------------

def parse_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[\s ]", "", str(value)).replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", text):
        return None
    return float(text)


def parse_date(text: str) -> str:
    """Дата из накладной в ISO; пустая строка, если не разобрать."""
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def extract_offline(path: Path) -> Extracted:
    import pdfplumber

    result = Extracted()
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
            for table in page.extract_tables():
                result.lines.extend(_lines_from_table(table))
    text = "\n".join(text_parts)
    if m := re.search(r"№\s*([A-ZА-Я0-9\-/]+)", text, re.I):
        result.number = m.group(1)
    if m := re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text):
        result.date = parse_date(m.group(1))
    if m := re.search(r"(?:Поставщик|Грузоотправитель)[:\s]+(.+)", text):
        result.supplier = m.group(1).strip()[:120]
    if not result.lines and not text.strip():
        raise RecognitionError(
            "В PDF нет текста — это скан-картинка. Для сканов укажите ключ Claude API в «Настройках»."
        )
    if not result.lines:
        raise RecognitionError("Не нашёл в PDF таблицу с колонками «Наименование» и «Количество».")
    return result


def _lines_from_table(table: list[list]) -> list[Line]:
    name_col = qty_col = unit_col = None
    lines: list[Line] = []
    for row in table:
        cells = [(c or "").replace("\n", " ").strip() for c in row]
        if name_col is None:
            low = [c.lower() for c in cells]
            for i, c in enumerate(low):
                if name_col is None and ("наимен" in c or "товар" in c):
                    name_col = i
                elif qty_col is None and "кол" in c:
                    qty_col = i
                elif unit_col is None and ("ед" in c and "изм" in c or c in ("ед.", "ед")):
                    unit_col = i
            if name_col is None or qty_col is None:
                name_col = qty_col = unit_col = None
            continue
        if max(name_col, qty_col) >= len(cells):
            continue
        name, qty = cells[name_col], parse_number(cells[qty_col])
        if not name or qty is None or qty <= 0 or name.lower().startswith("итого"):
            continue
        unit = cells[unit_col] if unit_col is not None and unit_col < len(cells) else ""
        lines.append(Line(name, qty, unit))
    return lines


PROMPT = """Это накладная (ТТН/ТН/счёт-фактура) на поставку товаров для кофейного автомата.
Извлеки все товарные строки: наименование ровно как в документе, количество (число) и единицу
измерения (кг, г, л, мл, шт, уп и т.п.) из колонки единиц. Итоговые строки не включай.
Также извлеки номер документа, дату в формате ГГГГ-ММ-ДД и название поставщика.
Если поле не найдено, верни пустую строку."""


def extract_with_claude(path: Path, api_key: str, model: str) -> Extracted:
    import anthropic
    from pydantic import BaseModel

    class Item(BaseModel):
        name: str
        quantity: float
        unit: str

    class Invoice(BaseModel):
        number: str
        date: str
        supplier: str
        items: list[Item]

    data = base64.standard_b64encode(path.read_bytes()).decode()
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=16000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document",
                     "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
                    {"type": "text", "text": PROMPT},
                ],
            }],
            output_format=Invoice,
        )
    except anthropic.AuthenticationError as e:
        raise RecognitionError("Claude API: неверный ключ API") from e
    except anthropic.RateLimitError as e:
        raise RecognitionError("Claude API: превышен лимит запросов, попробуйте позже") from e
    except anthropic.APIConnectionError as e:
        raise RecognitionError("Claude API: нет связи с сервером, проверьте интернет") from e
    except anthropic.APIStatusError as e:
        raise RecognitionError(f"Claude API: ошибка {e.status_code}: {e.message}") from e

    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RecognitionError("Claude не смог разобрать документ")
    inv = response.parsed_output
    return Extracted(
        number=inv.number.strip(),
        date=parse_date(inv.date),
        supplier=inv.supplier.strip(),
        lines=[Line(i.name.strip(), i.quantity, i.unit.strip()) for i in inv.items if i.quantity > 0],
    )


def extract(path: Path, api_key: str, model: str) -> Extracted:
    if api_key:
        return extract_with_claude(path, api_key, model)
    return extract_offline(path)


# ---- Запись в базу ---------------------------------------------------------

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_by_hash(conn: sqlite3.Connection, digest: str):
    return conn.execute("SELECT id, status FROM invoices WHERE file_hash = ?", (digest,)).fetchone()


def find_same_document(conn: sqlite3.Connection, ex: Extracted):
    if not ex.number or not ex.date:
        return None
    return conn.execute(
        "SELECT id, file_name FROM invoices WHERE status != 'error' AND doc_number = ? AND doc_date = ? "
        "AND COALESCE(supplier, '') = ?",
        (ex.number, ex.date, ex.supplier),
    ).fetchone()


def save_error(conn: sqlite3.Connection, file_name: str, digest: str, message: str) -> int:
    with conn:
        return conn.execute(
            "INSERT INTO invoices(file_name, file_hash, status, note) VALUES (?, ?, 'error', ?)",
            (file_name, digest, message),
        ).lastrowid


def save_extracted(conn: sqlite3.Connection, file_name: str, digest: str, ex: Extracted) -> tuple[int, str]:
    """Сохраняет распознанную накладную; если все строки сопоставлены — сразу проводит."""
    with conn:
        invoice_id = conn.execute(
            "INSERT INTO invoices(file_name, file_hash, doc_number, doc_date, supplier, status) "
            "VALUES (?, ?, ?, ?, ?, 'review')",
            (file_name, digest, ex.number, ex.date, ex.supplier),
        ).lastrowid
        for line in ex.lines:
            ingredient_id, factor, ignored = match_line(conn, line.name, line.unit)
            conn.execute(
                "INSERT INTO invoice_lines(invoice_id, raw_name, raw_qty, raw_unit, ingredient_id, factor, ignored) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (invoice_id, line.name, line.qty, line.unit, ingredient_id, factor, int(ignored)),
            )
    if unresolved_lines(conn, invoice_id) == 0 and ex.lines:
        post_invoice(conn, invoice_id)
        return invoice_id, "posted"
    return invoice_id, "review"


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
        conn.execute("UPDATE invoices SET status = 'posted', note = NULL WHERE id = ?", (invoice_id,))


def unpost_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Отменяет проведение (например, чтобы исправить количество) — приход убирается с остатков."""
    with conn:
        conn.execute("DELETE FROM movements WHERE invoice_id = ?", (invoice_id,))
        conn.execute("UPDATE invoices SET status = 'review' WHERE id = ?", (invoice_id,))


def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
