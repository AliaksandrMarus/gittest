"""Хранилище SQLite: справочники, продажи, накладные и движения остатков.

Остаток ингредиента нигде не хранится готовым числом — это сумма всех
движений (начальный остаток, приход, расход по продажам, корректировки).
Так любую цифру можно объяснить и пересчитать.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingredients (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    unit      TEXT NOT NULL,
    min_stock REAL NOT NULL DEFAULT 0,
    in_portions INTEGER NOT NULL DEFAULT 1  -- 0: второстепенный (палочки, крышки) — не ограничивает порции
);

CREATE TABLE IF NOT EXISTS drinks (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    price REAL NOT NULL DEFAULT 0  -- цена порции сейчас
);

-- Норма ингредиента на одну порцию напитка
CREATE TABLE IF NOT EXISTS recipe (
    drink_id      INTEGER NOT NULL REFERENCES drinks(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    qty           REAL NOT NULL,
    PRIMARY KEY (drink_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS sales (
    date     TEXT NOT NULL,
    drink_id INTEGER NOT NULL REFERENCES drinks(id) ON DELETE CASCADE,
    count    INTEGER NOT NULL,
    price    REAL NOT NULL DEFAULT 0,  -- цена порции в этот день
    PRIMARY KEY (date, drink_id)
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
    id            INTEGER PRIMARY KEY,
    invoice_id    INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    raw_name      TEXT NOT NULL,
    raw_qty       REAL NOT NULL,
    raw_unit      TEXT,
    price         REAL,
    vat           REAL,  -- сумма НДС
    total         REAL,  -- стоимость с НДС
    ingredient_id INTEGER REFERENCES ingredients(id),
    factor        REAL,
    ignored       INTEGER NOT NULL DEFAULT 0
);

-- Запомненные сопоставления «название в накладной → ингредиент»
CREATE TABLE IF NOT EXISTS aliases (
    raw_name      TEXT PRIMARY KEY,
    raw_unit      TEXT NOT NULL DEFAULT '',
    ingredient_id INTEGER REFERENCES ingredients(id) ON DELETE CASCADE,
    factor        REAL NOT NULL DEFAULT 1,
    ignored       INTEGER NOT NULL DEFAULT 0
);

-- kind: initial, receipt, sale, adjust. Расход хранится с минусом.
CREATE TABLE IF NOT EXISTS movements (
    id            INTEGER PRIMARY KEY,
    date          TEXT NOT NULL,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    qty           REAL NOT NULL,
    kind          TEXT NOT NULL,
    invoice_id    INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
    note          TEXT
);
CREATE INDEX IF NOT EXISTS movements_ing_date ON movements(ingredient_id, date);
CREATE INDEX IF NOT EXISTS movements_kind_date ON movements(kind, date);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# Пример для первого запуска: всё редактируется на вкладке «Рецепты».
DEFAULT_INGREDIENTS = [
    ("Кофе в зёрнах", "г", 1000),
    ("Молоко сухое", "г", 1000),
    ("Сахар", "г", 1000),
    ("Шоколад", "г", 500),
    ("Стаканчики", "шт", 100),
    ("Палочки для размешивания", "шт", 100),
]

DEFAULT_PRICES = {"Эспрессо": 2.5, "Американо": 2.5, "Капучино": 3.5, "Латте": 3.5, "Горячий шоколад": 3.0}

DEFAULT_RECIPES = {
    "Эспрессо": {"Кофе в зёрнах": 8, "Сахар": 5, "Стаканчики": 1, "Палочки для размешивания": 0.5},
    "Американо": {"Кофе в зёрнах": 8, "Сахар": 5, "Стаканчики": 1, "Палочки для размешивания": 0.5},
    "Капучино": {"Кофе в зёрнах": 8, "Молоко сухое": 10, "Сахар": 5, "Стаканчики": 1,
                 "Палочки для размешивания": 0.5},
    "Латте": {"Кофе в зёрнах": 8, "Молоко сухое": 14, "Сахар": 5, "Стаканчики": 1,
              "Палочки для размешивания": 0.5},
    "Горячий шоколад": {"Шоколад": 25, "Сахар": 3, "Стаканчики": 1, "Палочки для размешивания": 0.5},
}

DEFAULT_SETTINGS = {
    "forecast_days": "14",
    "tesseract_path": "",
    "auto_update": "1",
    "vending_machine": "192.168.1.9:5555",  # кофеавтомат: адрес в сети (порт отладки 5555)
    "vending_mac": "28-2d-06-12-98-5a",  # если IP сменится — найти автомат по MAC
    "vending_minutes": "60",  # опрашивать автомат каждые N минут (0 — только вручную)
    "vending_last": "",
}

# Столбцы, добавленные после первой версии: старая база дополняется при запуске
MIGRATIONS = {
    "ingredients": [("in_portions", "INTEGER NOT NULL DEFAULT 1")],
    "drinks": [("price", "REAL NOT NULL DEFAULT 0")],
    "sales": [("price", "REAL NOT NULL DEFAULT 0")],
    "invoice_lines": [("price", "REAL"), ("vat", "REAL"), ("total", "REAL")],
}


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    if conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
        _seed(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
                if (table, name) == ("ingredients", "in_portions"):
                    mark_secondary(conn)
    conn.commit()


SECONDARY_WORDS = ("палоч", "размешив", "крышк")


def is_secondary(name: str) -> bool:
    return any(w in name.lower() for w in SECONDARY_WORDS)


def mark_secondary(conn: sqlite3.Connection) -> None:
    """Палочки и крышки берут не все — они не должны ограничивать число порций.
    (lower() в SQLite не понимает русские буквы, поэтому проверяем в Python.)"""
    ids = [(r[0],) for r in conn.execute("SELECT id, name FROM ingredients") if is_secondary(r[1])]
    conn.executemany("UPDATE ingredients SET in_portions = 0 WHERE id = ?", ids)


def _seed(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executemany("INSERT INTO settings(key, value) VALUES (?, ?)", DEFAULT_SETTINGS.items())
        conn.executemany(
            "INSERT INTO ingredients(name, unit, min_stock) VALUES (?, ?, ?)", DEFAULT_INGREDIENTS
        )
        mark_secondary(conn)
        ing = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM ingredients")}
        for drink, parts in DEFAULT_RECIPES.items():
            drink_id = conn.execute("INSERT INTO drinks(name, price) VALUES (?, ?)",
                                    (drink, DEFAULT_PRICES.get(drink, 0))).lastrowid
            conn.executemany(
                "INSERT INTO recipe(drink_id, ingredient_id, qty) VALUES (?, ?, ?)",
                [(drink_id, ing[name], qty) for name, qty in parts.items()],
            )


def get_setting(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None or row["value"] is None:
        return DEFAULT_SETTINGS.get(key, "")
    return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
