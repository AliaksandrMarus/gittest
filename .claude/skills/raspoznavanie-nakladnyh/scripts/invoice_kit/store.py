"""Учёт по накладным: товары, накладные, запомненные сопоставления, движение остатков (SQLite).

Названия из накладной сопоставляются с товарами справочника. Однажды подтверждённое
сопоставление (и коэффициент пересчёта, например «1 упаковка = 250 шт» или
«1 кг = 1000 г») запоминается в aliases и дальше применяется автоматически,
в том числе к чуть иначе распознанному названию (нечёткое сравнение ≥ 0.85).

Остаток товара = сумма движений: initial (начальный), receipt (приход по накладной),
sale/writeoff (расход, с минусом), adjust (инвентаризация).

    conn = store.connect("учёт.db")
    invoice_id, status = store.save_extracted(conn, "файл.pdf", store.file_hash(path), ex)
    # status: posted — все строки сопоставлены и приход проведён; review — нужна проверка
"""

from __future__ import annotations

import difflib
import hashlib
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .recognize import Extracted, Line, normalize, unit_factor, unit_key

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    unit      TEXT NOT NULL,              -- единица учёта: г, мл, шт…
    min_stock REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invoices (
    id         INTEGER PRIMARY KEY,
    file_name  TEXT NOT NULL,
    file_hash  TEXT NOT NULL UNIQUE,
    doc_number TEXT,
    doc_date   TEXT,
    supplier   TEXT,
    -- posted — проведена, review — ждёт проверки, error — не распознана
    status     TEXT NOT NULL,
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id         INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    raw_name   TEXT NOT NULL,
    raw_qty    REAL NOT NULL,
    raw_unit   TEXT,
    price      REAL,
    vat        REAL,  -- сумма НДС
    total      REAL,  -- стоимость с НДС
    item_id    INTEGER REFERENCES items(id),
    factor     REAL,  -- сколько единиц учёта в одной единице накладной
    ignored    INTEGER NOT NULL DEFAULT 0  -- услуги, тара и т.п. — не идут в остатки
);

-- Запомненные сопоставления «название в накладной → товар»
CREATE TABLE IF NOT EXISTS aliases (
    raw_name TEXT PRIMARY KEY,  -- normalize(name)|unit_key(unit)
    raw_unit TEXT NOT NULL DEFAULT '',
    item_id  INTEGER REFERENCES items(id) ON DELETE CASCADE,
    factor   REAL NOT NULL DEFAULT 1,
    ignored  INTEGER NOT NULL DEFAULT 0
);

-- kind: initial, receipt, sale, writeoff, adjust. Расход хранится с минусом.
CREATE TABLE IF NOT EXISTS movements (
    id         INTEGER PRIMARY KEY,
    date       TEXT NOT NULL,
    item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    qty        REAL NOT NULL,
    kind       TEXT NOT NULL,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
    note       TEXT
);
CREATE INDEX IF NOT EXISTS movements_item_date ON movements(item_id, date);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def today() -> str:
    return date.today().isoformat()


def add_movement(conn: sqlite3.Connection, day: str, item_id: int, qty: float, kind: str,
                 note: str | None = None, invoice_id: int | None = None) -> None:
    conn.execute("INSERT INTO movements(date, item_id, qty, kind, invoice_id, note) VALUES (?, ?, ?, ?, ?, ?)",
                 (day, item_id, qty, kind, invoice_id, note))


def stock(conn: sqlite3.Connection, as_of: str | None = None) -> dict[int, float]:
    """Остаток каждого товара на конец дня as_of (по умолчанию — всё время)."""
    sql = "SELECT i.id, COALESCE(SUM(m.qty), 0) AS qty FROM items i LEFT JOIN movements m ON m.item_id = i.id"
    params: tuple = ()
    if as_of:
        sql += " AND m.date <= ?"
        params = (as_of,)
    return {r["id"]: r["qty"] for r in conn.execute(sql + " GROUP BY i.id", params)}


# ---- Сопоставление строк накладной с товарами --------------------------------

def _stems(text: str) -> set[str]:
    return {w[:4] for w in normalize(text).split() if len(w) > 3 and not w[0].isdigit()}


def guess_item(conn: sqlite3.Connection, raw_name: str) -> int | None:
    """Ищет товар, все значимые слова которого встречаются в названии строки."""
    raw = _stems(raw_name)
    hits = [r["id"] for r in conn.execute("SELECT id, name FROM items")
            if (s := _stems(r["name"])) and s <= raw]
    return hits[0] if len(hits) == 1 else None


def alias_key(raw_name: str, raw_unit: str) -> str:
    return f"{normalize(raw_name)}|{unit_key(raw_unit)}"


def match_line(conn: sqlite3.Connection, raw_name: str, raw_unit: str) -> tuple[int | None, float | None, bool]:
    """Возвращает (товар, коэффициент, игнорировать) для строки накладной."""
    alias = conn.execute("SELECT item_id, factor, ignored FROM aliases WHERE raw_name = ?",
                         (alias_key(raw_name, raw_unit),)).fetchone()
    if alias:
        return alias["item_id"], alias["factor"], bool(alias["ignored"])
    # Скан читает название каждый раз чуть по-разному («80мм» / «8Омм») — ищем похожее
    key = alias_key(raw_name, raw_unit)
    name_part, unit_part = key.rsplit("|", 1)
    best, best_ratio = None, 0.0
    for a in conn.execute("SELECT raw_name, item_id, factor, ignored FROM aliases WHERE raw_name LIKE ?",
                          (f"%|{unit_part}",)):
        ratio = difflib.SequenceMatcher(None, name_part, a["raw_name"].rsplit("|", 1)[0]).ratio()
        if ratio > best_ratio:
            best, best_ratio = a, ratio
    if best is not None and best_ratio >= 0.85:
        return best["item_id"], best["factor"], bool(best["ignored"])
    item_id = guess_item(conn, raw_name)
    if item_id is None:
        return None, None, False
    unit = conn.execute("SELECT unit FROM items WHERE id = ?", (item_id,)).fetchone()["unit"]
    return item_id, unit_factor(raw_unit, unit), False



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
        item_id, factor, ignored = match_line(conn, line.name, line.unit)
        conn.execute(
            "INSERT INTO invoice_lines(invoice_id, raw_name, raw_qty, raw_unit, price, vat, total, "
            "item_id, factor, ignored) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (invoice_id, line.name, line.qty, line.unit, line.price, line.vat, line.total,
             item_id, factor, int(ignored)),
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
    item_id: int | None = None
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
                "item_id, factor, ignored) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (invoice_id, line.name, line.qty, line.unit, line.price, line.vat, line.total,
                 None if line.ignored else line.item_id, line.factor, int(line.ignored)),
            )
    if (post or was_posted) and lines and unresolved_lines(conn, invoice_id) == 0:
        post_invoice(conn, invoice_id)
    return invoice_id


def unresolved_lines(conn: sqlite3.Connection, invoice_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM invoice_lines WHERE invoice_id = ? AND ignored = 0 "
        "AND (item_id IS NULL OR factor IS NULL OR factor <= 0)",
        (invoice_id,),
    ).fetchone()[0]


def update_line(conn: sqlite3.Connection, line_id: int, item_id: int | None,
                factor: float | None, ignored: bool) -> None:
    with conn:
        conn.execute("UPDATE invoice_lines SET item_id = ?, factor = ?, ignored = ? WHERE id = ?",
                     (item_id, factor, int(ignored), line_id))


def post_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Проводит накладную: приход на остатки и запоминание сопоставлений."""
    if unresolved_lines(conn, invoice_id):
        raise ValueError("Не все строки накладной сопоставлены с товарами")
    inv = conn.execute("SELECT doc_date, status FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if inv["status"] == "posted":
        return
    day = inv["doc_date"] or today()
    with conn:
        for line in conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (invoice_id,)).fetchall():
            conn.execute(
                "INSERT INTO aliases(raw_name, raw_unit, item_id, factor, ignored) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(raw_name) DO UPDATE SET item_id = excluded.item_id, "
                "factor = excluded.factor, ignored = excluded.ignored",
                (alias_key(line["raw_name"], line["raw_unit"]), unit_key(line["raw_unit"]),
                 line["item_id"], line["factor"] or 1, line["ignored"]),
            )
            if not line["ignored"]:
                add_movement(conn, day, line["item_id"], line["raw_qty"] * line["factor"],
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
