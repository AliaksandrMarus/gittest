"""Начальные данные кофейного автомата ДС №152 (Бобруйск, ул. Гоголя, 181).

Программа сама переносит их в пустую базу: при первом запуске или при обновлении,
если в базе ещё нет ни накладных, ни продаж (только пример из первой версии).

Источники:
* ТТН серии ИД № 4692066 от 17.06.2026, ООО «ПРОКСИМАВЕСТ» — остаток на 01.07.2026;
* рецептура и цены — файл «coffee_sales_report.xlsx», лист «Рецептура»
  (стакан и палочка — 1 шт на любой напиток, крышки берут не все — в рецепт не входят);
* продажи: июль — итог месяца («ДС №152 отчёт за июль 2026», записан на 31.07),
  август–21 октября — по дням из «Отчёта по реализации товаров на ДС №152»;
* инвентаризация 21.10.2026: палочек по расчёту −84 шт. — фактически закончились, остаток 0.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from . import core, db, invoice

SETTING = "seed_ds152"

INGREDIENTS = [  # название, единица, минимальный запас
    ("Кофе в зёрнах", "г", 2000),
    ("Сухое молоко (сливки)", "г", 2000),
    ("Шоколад (сухая смесь)", "г", 1000),
    ("Сахар", "г", 1000),
    ("Палочки для размешивания", "шт", 150),
    ("Стаканчики", "шт", 150),
    ("Крышки", "шт", 50),
]

DRINKS = {"Эспрессо": 2.5, "Американо": 3.0, "Капучино": 3.5, "Латте": 3.5,
          "Горячий шоколад": 3.0, "Молочный шоколад": 3.0}

RECIPE_COLUMNS = ("Кофе в зёрнах", "Сухое молоко (сливки)", "Шоколад (сухая смесь)", "Сахар",
                  "Палочки для размешивания", "Стаканчики")
RECIPES = {  # на 1 порцию: кофе г, молоко г, шоколад г, сахар г, палочка шт, стакан шт
    "Капучино": (12, 18, 0, 5, 1, 1),
    "Латте": (10, 24, 0, 5, 1, 1),
    "Молочный шоколад": (0, 12, 16, 5, 1, 1),
    "Эспрессо": (10, 0, 0, 5, 1, 1),
    "Американо": (12, 0, 0, 5, 1, 1),
    "Горячий шоколад": (0, 0, 28, 5, 1, 1),
}

INVOICE = {"number": "ИД 4692066", "date": "2026-06-17", "supplier": 'ООО "ПРОКСИМАВЕСТ"',
           "file": "ТТН ИД 4692066 от 17.06.2026.pdf"}
INVOICE_LINES = [  # наименование, кол-во, ед., цена, НДС, с НДС, ингредиент, коэффициент
    ('Кофе в зернах Grano Milano FRESH CLASSIC 1кг 56002 (РФ)', 15, "шт", 43.91, 131.73, 790.38,
     "Кофе в зёрнах", 1000),
    ('Смесь сухая растворимая для приготовления напитка "Венда Кремер" 1кг 5800/53 (РБ)', 25, "шт", 11.40, 57.00,
     342.00, "Сухое молоко (сливки)", 1000),
    ('Смесь сухая растворимая со вкусом "Дубайский шоколад" 1кг 58002/14 (РБ)', 3, "шт", 14.60, 8.76, 52.56,
     "Шоколад (сухая смесь)", 1000),
    ('Сахар "Мир эспрессо" 1300х5 гр. 001/8', 1, "шт", 40.34, 4.03, 44.37, "Сахар", 6500),
    ('Размешиватель дерев. 140*6*1,5 мм в индивидуальной упаковке 250 шт 10/14', 3, "упак", 5.65, 3.39, 20.34,
     "Палочки для размешивания", 250),
    ('Стакан бумажный одноразовый для вендинга 250 мл Крема 50/туба 1400/кор (HB80-280V) 08/53 (РФ)', 22, "упак",
     3.62, 15.93, 95.57, "Стаканчики", 50),
    ('Крышка черная для стакана D-80мм с открытым питейником 100/1000 21/9', 3, "шт", 5.00, 3.00, 18.00,
     "Крышки", 100),
    ('CAFEDEM G31 табл.5 Алкадем для очистки кофемашин 5табл. 16093/2 (РФ)', 1, "шт", 3.13, 0.63, 3.76,
     None, None),
]

SALES_DRINKS = ('Капучино', 'Латте', 'Американо', 'Эспрессо', 'Горячий шоколад', 'Молочный шоколад')
SALES = {  # дата: продано по SALES_DRINKS
    "2026-07-31": (57, 32, 49, 5, 7, 3),
    "2026-08-01": (6, 3, 2, 0, 0, 0),
    "2026-08-04": (6, 1, 0, 0, 1, 0),
    "2026-08-05": (1, 1, 3, 0, 0, 0),
    "2026-08-06": (0, 2, 0, 0, 0, 0),
    "2026-08-07": (6, 3, 1, 0, 0, 1),
    "2026-08-08": (8, 1, 0, 1, 0, 0),
    "2026-08-10": (2, 0, 0, 0, 0, 0),
    "2026-08-11": (5, 2, 1, 0, 1, 0),
    "2026-08-12": (7, 3, 3, 0, 0, 0),
    "2026-08-13": (0, 1, 0, 0, 0, 1),
    "2026-08-14": (7, 1, 1, 0, 0, 0),
    "2026-08-15": (5, 2, 1, 0, 2, 0),
    "2026-08-18": (1, 3, 2, 0, 1, 1),
    "2026-08-19": (2, 1, 1, 0, 0, 0),
    "2026-08-20": (5, 0, 0, 0, 0, 0),
    "2026-08-21": (4, 3, 1, 0, 0, 1),
    "2026-08-22": (8, 3, 0, 1, 1, 0),
    "2026-08-25": (2, 3, 1, 0, 0, 0),
    "2026-08-26": (11, 1, 3, 0, 1, 0),
    "2026-08-27": (7, 2, 1, 0, 0, 0),
    "2026-08-28": (5, 3, 0, 0, 1, 0),
    "2026-08-29": (4, 4, 1, 0, 1, 1),
    "2026-09-01": (7, 3, 0, 0, 1, 0),
    "2026-09-02": (9, 0, 1, 0, 1, 1),
    "2026-09-03": (7, 3, 0, 1, 0, 0),
    "2026-09-04": (14, 0, 1, 0, 0, 0),
    "2026-09-05": (2, 0, 1, 0, 0, 0),
    "2026-09-08": (13, 0, 2, 0, 1, 0),
    "2026-09-09": (8, 0, 4, 0, 0, 0),
    "2026-09-10": (5, 2, 6, 0, 0, 0),
    "2026-09-11": (1, 4, 3, 1, 0, 0),
    "2026-09-12": (12, 0, 5, 1, 1, 1),
    "2026-09-15": (11, 1, 5, 0, 0, 0),
    "2026-09-16": (6, 1, 3, 0, 0, 0),
    "2026-09-17": (9, 0, 4, 0, 0, 1),
    "2026-09-18": (4, 0, 2, 0, 2, 1),
    "2026-09-19": (11, 4, 6, 0, 0, 0),
    "2026-09-22": (12, 1, 6, 0, 0, 0),
    "2026-09-23": (5, 0, 1, 1, 0, 0),
    "2026-09-24": (6, 2, 3, 2, 0, 2),
    "2026-09-25": (11, 0, 4, 0, 0, 0),
    "2026-09-26": (16, 4, 4, 0, 0, 0),
    "2026-09-29": (8, 2, 4, 0, 1, 1),
    "2026-09-30": (15, 3, 1, 0, 0, 0),
    "2026-10-01": (16, 0, 5, 1, 1, 1),
    "2026-10-02": (21, 2, 2, 0, 0, 0),
    "2026-10-03": (8, 1, 3, 0, 1, 1),
    "2026-10-06": (8, 2, 4, 1, 0, 1),
    "2026-10-07": (6, 1, 2, 0, 0, 0),
    "2026-10-08": (2, 2, 2, 0, 1, 1),
    "2026-10-09": (8, 2, 3, 0, 0, 1),
    "2026-10-10": (9, 0, 1, 0, 0, 0),
    "2026-10-13": (9, 3, 2, 1, 0, 1),
    "2026-10-14": (5, 1, 4, 1, 0, 0),
    "2026-10-15": (6, 1, 2, 0, 1, 1),
    "2026-10-16": (8, 2, 1, 1, 1, 1),
    "2026-10-17": (4, 1, 1, 0, 0, 1),
    "2026-10-21": (3, 3, 4, 1, 0, 0),
}

INVENTORY_DATE = "2026-10-21"
INVENTORY = {"Палочки для размешивания": 0}  # фактический остаток; остальное — по расчёту


def needed(conn: sqlite3.Connection) -> bool:
    """База пустая (только пример первой версии) и начальные данные ещё не переносились."""
    if db.get_setting(conn, SETTING) == "1":
        return False
    busy = conn.execute("SELECT (SELECT COUNT(*) FROM invoices) + (SELECT COUNT(*) FROM sales)").fetchone()[0]
    return busy == 0


def apply(conn: sqlite3.Connection, sales_file: Path | None = None) -> None:
    with conn:
        for table in ("recipe", "movements", "invoice_lines", "invoices", "aliases", "drinks", "ingredients"):
            conn.execute(f"DELETE FROM {table}")
        conn.executemany("INSERT INTO ingredients(name, unit, min_stock) VALUES (?, ?, ?)", INGREDIENTS)
        ing = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM ingredients")}
        for name, price in DRINKS.items():
            drink_id = conn.execute("INSERT INTO drinks(name, price) VALUES (?, ?)", (name, price)).lastrowid
            for ing_name, qty in zip(RECIPE_COLUMNS, RECIPES[name]):
                if qty:
                    conn.execute("INSERT INTO recipe VALUES (?, ?, ?)", (drink_id, ing[ing_name], qty))

    lines = [invoice.EditedLine(n, q, u, p, v, t, ing[i] if i else None, f, i is None)
             for n, q, u, p, v, t, i, f in INVOICE_LINES]
    invoice_id = invoice.save_invoice(conn, None, INVOICE["number"], INVOICE["date"], INVOICE["supplier"],
                                      lines, post=True)
    with conn:
        conn.execute("UPDATE invoices SET file_name = ? WHERE id = ?", (INVOICE["file"], invoice_id))
        drinks = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM drinks")}
        for day, counts in SALES.items():
            core.set_sales_for_date(conn, day, {drinks[n]: c for n, c in zip(SALES_DRINKS, counts) if c})
        for name, actual in INVENTORY.items():
            core.adjust_to_actual(conn, INVENTORY_DATE, ing[name], actual,
                                  "Инвентаризация 21.10.2026: по расчёту палочки закончились")
    db.set_setting(conn, SETTING, "1")
    if sales_file is not None:
        write_sales_file(sales_file)
        db.set_setting(conn, "sales_mtime", str(sales_file.stat().st_mtime))


def write_sales_file(path: Path) -> None:
    """Файл продаж с уже внесёнными днями и пустыми датами до конца следующего месяца."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    if path.exists():
        path.replace(path.with_name(path.stem + " (до переноса данных).xlsx"))
    wb = Workbook()
    ws = wb.active
    ws.title = "Продажи"
    names = list(DRINKS)
    ws.append(["Дата"] + names)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="F3E5D0")
    for day, counts in SALES.items():
        by_name = dict(zip(SALES_DRINKS, counts))
        ws.append([date.fromisoformat(day)] + [by_name.get(n) or None for n in names])
    last = date.fromisoformat(max(SALES))
    end = (last.replace(day=1) + timedelta(days=62)).replace(day=1) - timedelta(days=1)
    day = last + timedelta(days=1)
    while day <= end:
        if day.weekday() < 5:  # станция работает по будням
            ws.append([day])
        day += timedelta(days=1)
    for row in ws.iter_rows(min_row=2, max_col=1):
        row[0].number_format = "DD.MM.YYYY"
    ws.column_dimensions["A"].width = 12
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 17
    ws.freeze_panes = "B2"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
