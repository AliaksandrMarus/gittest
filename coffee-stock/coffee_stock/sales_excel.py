"""Excel-файл продаж: строки — даты, столбцы — напитки."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from . import core

SHEET = "Продажи"


@dataclass
class ImportResult:
    days: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def ensure_template(conn: sqlite3.Connection, path: Path) -> None:
    """Создаёт файл продаж или дописывает в него столбцы для новых напитков."""
    drinks = [r["name"] for r in conn.execute("SELECT name FROM drinks ORDER BY id")]
    if path.exists():
        wb = load_workbook(path)
        ws = wb[SHEET] if SHEET in wb.sheetnames else wb.active
        have = {str(c.value).strip() for c in ws[1] if c.value}
        col = ws.max_column + 1
        for name in drinks:
            if name not in have:
                _header_cell(ws, col, name)
                col += 1
        wb.save(path)
        return

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    _header_cell(ws, 1, "Дата")
    for i, name in enumerate(drinks, start=2):
        _header_cell(ws, i, name)
    # Даты на месяц вперёд, чтобы оставалось только вписывать количество
    start = date.today()
    for i in range(31):
        cell = ws.cell(row=i + 2, column=1, value=start + timedelta(days=i))
        cell.number_format = "DD.MM.YYYY"
    ws.column_dimensions["A"].width = 12
    ws.freeze_panes = "B2"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _header_cell(ws, col: int, value: str) -> None:
    cell = ws.cell(row=1, column=col, value=value)
    cell.font = Font(bold=True)
    cell.fill = PatternFill("solid", fgColor="F3E5D0")
    ws.column_dimensions[cell.column_letter].width = max(12, len(value) + 2)


def _parse_date(value) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date().isoformat()
            except ValueError:
                pass
    return None


def import_file(conn: sqlite3.Connection, path: Path) -> ImportResult:
    """Загружает продажи из Excel. Пустые строки (день ещё не заполнен) пропускаются."""
    result = ImportResult()
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb[SHEET] if SHEET in wb.sheetnames else wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        result.errors.append("Файл пустой")
        return result

    drinks = {r["name"].strip().lower(): r["id"] for r in conn.execute("SELECT id, name FROM drinks")}
    columns: dict[int, int] = {}
    for idx, title in enumerate(header[1:], start=1):
        if title is None or not str(title).strip():
            continue
        drink_id = drinks.get(str(title).strip().lower())
        if drink_id is None:
            result.errors.append(f"Напиток «{title}» не найден в рецептах — столбец пропущен")
        else:
            columns[idx] = drink_id

    parsed: dict[str, dict[int, int]] = {}
    for line_no, row in enumerate(rows, start=2):
        if not row or all(v in (None, "") for v in row[1:]):
            continue
        day = _parse_date(row[0])
        if day is None:
            result.errors.append(f"Строка {line_no}: не понял дату «{row[0]}»")
            continue
        counts: dict[int, int] = {}
        for idx, drink_id in columns.items():
            value = row[idx] if idx < len(row) else None
            if value in (None, ""):
                continue
            try:
                n = int(round(float(str(value).replace(",", "."))))
            except ValueError:
                result.errors.append(f"Строка {line_no}: «{value}» — не число")
                continue
            if n < 0:
                result.errors.append(f"Строка {line_no}: отрицательное количество {n}")
                continue
            counts[drink_id] = counts.get(drink_id, 0) + n
        parsed[day] = counts
    wb.close()

    with conn:
        for day, counts in sorted(parsed.items()):
            core.set_sales_for_date(conn, day, counts)
            result.days.append(day)
    return result
