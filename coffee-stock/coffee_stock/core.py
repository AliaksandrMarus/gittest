"""Расчёты: остатки, списание по рецептам, прогноз и отчёты за период."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

KIND_NAMES = {
    "initial": "Начальный остаток",
    "receipt": "Приход",
    "sale": "Расход (продажи)",
    "adjust": "Корректировка",
}


def today() -> str:
    return date.today().isoformat()


def add_movement(conn: sqlite3.Connection, day: str, ingredient_id: int, qty: float, kind: str,
                 note: str | None = None, invoice_id: int | None = None) -> None:
    conn.execute(
        "INSERT INTO movements(date, ingredient_id, qty, kind, invoice_id, note) VALUES (?, ?, ?, ?, ?, ?)",
        (day, ingredient_id, qty, kind, invoice_id, note),
    )


def stock(conn: sqlite3.Connection, as_of: str | None = None) -> dict[int, float]:
    """Остаток каждого ингредиента на конец дня as_of (по умолчанию — всё время)."""
    sql = "SELECT i.id, COALESCE(SUM(m.qty), 0) AS qty FROM ingredients i " \
          "LEFT JOIN movements m ON m.ingredient_id = i.id"
    params: tuple = ()
    if as_of:
        sql += " AND m.date <= ?"
        params = (as_of,)
    sql += " GROUP BY i.id"
    return {r["id"]: r["qty"] for r in conn.execute(sql, params)}


def set_sales_for_date(conn: sqlite3.Connection, day: str, counts: dict[int, int]) -> None:
    """Заменяет продажи за день и пересчитывает списание ингредиентов за этот день.

    Повторный импорт того же дня ничего не задваивает: старые продажи и
    старое списание за день удаляются и пишутся заново по текущим рецептам.
    """
    # Цена фиксируется в день первой загрузки: файл продаж перечитывается целиком,
    # и после подорожания старые дни не должны переоцениться
    kept = {r["drink_id"]: r["price"] for r in
            conn.execute("SELECT drink_id, price FROM sales WHERE date = ?", (day,))}
    current = {r["id"]: r["price"] for r in conn.execute("SELECT id, price FROM drinks")}
    conn.execute("DELETE FROM sales WHERE date = ?", (day,))
    conn.executemany(
        "INSERT INTO sales(date, drink_id, count, price) VALUES (?, ?, ?, ?)",
        [(day, drink_id, n, kept.get(drink_id, current.get(drink_id, 0)))
         for drink_id, n in counts.items() if n],
    )
    _rewrite_sale_movements(conn, day)


def _rewrite_sale_movements(conn: sqlite3.Connection, day: str) -> None:
    conn.execute("DELETE FROM movements WHERE kind = 'sale' AND date = ?", (day,))
    rows = conn.execute(
        "SELECT r.ingredient_id, SUM(s.count * r.qty) AS used FROM sales s "
        "JOIN recipe r ON r.drink_id = s.drink_id WHERE s.date = ? GROUP BY r.ingredient_id",
        (day,),
    ).fetchall()
    for r in rows:
        if r["used"]:
            add_movement(conn, day, r["ingredient_id"], -r["used"], "sale")


def recompute_all_sales(conn: sqlite3.Connection) -> int:
    """Пересчитывает списание за все дни по текущим рецептам (после исправления рецепта)."""
    days = [r[0] for r in conn.execute("SELECT DISTINCT date FROM sales")]
    conn.execute("DELETE FROM movements WHERE kind = 'sale'")
    for day in days:
        _rewrite_sale_movements(conn, day)
    return len(days)


def adjust_to_actual(conn: sqlite3.Connection, day: str, ingredient_id: int, actual: float,
                     note: str = "Инвентаризация") -> float:
    """Инвентаризация: доводит учётный остаток на дату до фактического. Возвращает разницу."""
    current = stock(conn, day).get(ingredient_id, 0.0)
    diff = actual - current
    if abs(diff) > 1e-9:
        add_movement(conn, day, ingredient_id, diff, "adjust", note)
    return diff


def last_sales_date(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT MAX(date) FROM sales").fetchone()[0]


@dataclass
class ForecastRow:
    ingredient_id: int
    name: str
    unit: str
    stock: float
    min_stock: float
    per_day: float
    days_left: float | None  # None — расхода не было, прогноз невозможен
    run_out: str | None

    @property
    def low(self) -> bool:
        return self.stock <= self.min_stock or (self.days_left is not None and self.days_left < 3)


def forecast(conn: sqlite3.Connection, window_days: int) -> list[ForecastRow]:
    """Средний расход за последние window_days дней с продажами и на сколько хватит остатка.

    Окно отсчитывается от последнего дня, за который внесены продажи, —
    иначе пара дней без импорта занизила бы средний расход.
    """
    window_days = max(1, window_days)
    end = last_sales_date(conn)
    used: dict[int, float] = {}
    if end:
        start = (date.fromisoformat(end) - timedelta(days=window_days - 1)).isoformat()
        first = conn.execute("SELECT MIN(date) FROM sales").fetchone()[0]
        # Если продаж меньше, чем окно, делим на фактическое число дней
        if first > start:
            start = first
        span = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        for r in conn.execute(
            "SELECT ingredient_id, -SUM(qty) AS used FROM movements "
            "WHERE kind = 'sale' AND date BETWEEN ? AND ? GROUP BY ingredient_id",
            (start, end),
        ):
            used[r["ingredient_id"]] = r["used"] / span

    current = stock(conn)
    rows = []
    for ing in conn.execute("SELECT id, name, unit, min_stock FROM ingredients ORDER BY name"):
        qty = current.get(ing["id"], 0.0)
        per_day = used.get(ing["id"], 0.0)
        days_left = run_out = None
        if per_day > 0:
            days_left = max(qty, 0) / per_day
            run_out = (date.today() + timedelta(days=int(days_left))).isoformat()
        rows.append(ForecastRow(ing["id"], ing["name"], ing["unit"], qty, ing["min_stock"],
                                per_day, days_left, run_out))
    return rows


def portions_left(conn: sqlite3.Connection) -> list[tuple[str, int, str]]:
    """Сколько порций каждого напитка ещё можно приготовить и что закончится первым."""
    current = stock(conn)
    result = []
    for d in conn.execute("SELECT id, name FROM drinks ORDER BY name"):
        best: tuple[float, str] | None = None
        for r in conn.execute(
            "SELECT r.ingredient_id, r.qty, i.name FROM recipe r "
            "JOIN ingredients i ON i.id = r.ingredient_id WHERE r.drink_id = ? AND r.qty > 0",
            (d["id"],),
        ):
            n = max(current.get(r["ingredient_id"], 0.0), 0) / r["qty"]
            if best is None or n < best[0]:
                best = (n, r["name"])
        if best is not None:
            result.append((d["name"], int(best[0]), best[1]))
    return result


# ---- Отчёты за период -------------------------------------------------------

def report_sales_by_drink(conn: sqlite3.Connection, d1: str, d2: str) -> tuple[list[str], list[list]]:
    rows = conn.execute(
        "SELECT d.name, SUM(s.count) AS n, SUM(s.count * s.price) AS money FROM sales s "
        "JOIN drinks d ON d.id = s.drink_id WHERE s.date BETWEEN ? AND ? GROUP BY d.id ORDER BY money DESC, n DESC",
        (d1, d2),
    ).fetchall()
    days = (date.fromisoformat(d2) - date.fromisoformat(d1)).days + 1
    total_n = sum(r["n"] for r in rows)
    total_money = sum(r["money"] for r in rows)
    data = [[r["name"], r["n"], round(r["money"], 2), round(r["money"] / r["n"], 2) if r["n"] else 0,
             round(r["n"] / days, 1), f"{r['money'] * 100 / total_money:.1f}%" if total_money else "—"]
            for r in rows]
    if rows:
        data.append(["Итого", total_n, round(total_money, 2),
                     round(total_money / total_n, 2) if total_n else 0, round(total_n / days, 1), "100%"])
    return ["Напиток", "Продано, шт", "Выручка, руб.", "Средняя цена", "Порций в день", "Доля выручки"], data


def report_sales_by_day(conn: sqlite3.Connection, d1: str, d2: str) -> tuple[list[str], list[list]]:
    drinks = conn.execute("SELECT id, name FROM drinks ORDER BY name").fetchall()
    by_day: dict[str, dict[int, int]] = {}
    money: dict[str, float] = {}
    for r in conn.execute("SELECT date, drink_id, count, price FROM sales WHERE date BETWEEN ? AND ? "
                          "ORDER BY date", (d1, d2)):
        by_day.setdefault(r["date"], {})[r["drink_id"]] = r["count"]
        money[r["date"]] = money.get(r["date"], 0) + r["count"] * r["price"]
    header = ["Дата"] + [d["name"] for d in drinks] + ["Всего, шт", "Выручка, руб."]
    data = []
    for day, counts in by_day.items():
        row = [day] + [counts.get(d["id"], 0) for d in drinks]
        data.append(row + [sum(row[1:]), round(money[day], 2)])
    if data:
        data.append(["Итого"] + [sum(r[i] for r in data) for i in range(1, len(header) - 1)]
                    + [round(sum(r[-1] for r in data), 2)])
    return header, data


def report_receipts(conn: sqlite3.Connection, d1: str, d2: str) -> tuple[list[str], list[list]]:
    """Все строки накладных за период — дата, №, поставщик, товар, количество, цена, НДС, с НДС."""
    rows = conn.execute(
        "SELECT v.doc_date, v.doc_number, v.supplier, l.raw_name, l.raw_qty, l.raw_unit, l.price, l.vat, "
        "l.total, CASE v.status WHEN 'posted' THEN 'Проведена' ELSE 'Не проведена' END "
        "FROM invoice_lines l JOIN invoices v ON v.id = l.invoice_id "
        "WHERE v.status != 'error' AND COALESCE(NULLIF(v.doc_date, ''), date(v.created_at)) BETWEEN ? AND ? "
        "ORDER BY v.doc_date, v.id, l.id",
        (d1, d2),
    ).fetchall()
    data = [[r[0] or "", r[1] or "", r[2] or "", r[3], r[4], r[5] or "", r[6], r[7], r[8], r[9]] for r in rows]
    if data:
        data.append(["Итого", "", "", "", "", "", None,
                     round(sum(r[7] or 0 for r in data), 2), round(sum(r[8] or 0 for r in data), 2), ""])
    return (["Дата", "№", "Поставщик", "Наименование", "Количество", "Ед.", "Цена", "НДС", "С НДС", "Статус"],
            data)


@dataclass
class Summary:
    last_day: str | None
    last_day_money: float
    last_day_count: int
    month_money: float
    month_count: int
    low_count: int


def summary(conn: sqlite3.Connection, window_days: int) -> Summary:
    """Цифры для карточек на главной вкладке."""
    last = last_sales_date(conn)
    day_money = day_count = 0
    if last:
        r = conn.execute("SELECT COALESCE(SUM(count * price), 0), COALESCE(SUM(count), 0) FROM sales "
                         "WHERE date = ?", (last,)).fetchone()
        day_money, day_count = r[0], r[1]
    month_start = date.today().replace(day=1).isoformat()
    r = conn.execute("SELECT COALESCE(SUM(count * price), 0), COALESCE(SUM(count), 0) FROM sales "
                     "WHERE date >= ?", (month_start,)).fetchone()
    low = sum(1 for f in forecast(conn, window_days) if f.low)
    return Summary(last, day_money, day_count, r[0], r[1], low)


def report_movement(conn: sqlite3.Connection, d1: str, d2: str) -> tuple[list[str], list[list]]:
    """Оборотная ведомость: остаток на начало, приход, расход, корректировки, остаток на конец."""
    before = (date.fromisoformat(d1) - timedelta(days=1)).isoformat()
    opening = stock(conn, before)
    closing = stock(conn, d2)
    sums: dict[tuple[int, str], float] = {}
    for r in conn.execute(
        "SELECT ingredient_id, kind, SUM(qty) AS q FROM movements WHERE date BETWEEN ? AND ? "
        "GROUP BY ingredient_id, kind",
        (d1, d2),
    ):
        sums[(r["ingredient_id"], r["kind"])] = r["q"]
    data = []
    for ing in conn.execute("SELECT id, name, unit FROM ingredients ORDER BY name"):
        i = ing["id"]
        incoming = sums.get((i, "receipt"), 0) + sums.get((i, "initial"), 0)
        data.append([ing["name"], ing["unit"], opening.get(i, 0), incoming,
                     -sums.get((i, "sale"), 0), sums.get((i, "adjust"), 0), closing.get(i, 0)])
    return ["Ингредиент", "Ед.", "На начало", "Приход", "Расход", "Корректировки", "На конец"], data


def report_forecast(conn: sqlite3.Connection, window_days: int) -> tuple[list[str], list[list]]:
    data = []
    for r in forecast(conn, window_days):
        data.append([r.name, r.unit, r.stock, round(r.per_day, 2),
                     "—" if r.days_left is None else int(r.days_left), r.run_out or "—"])
    return ["Ингредиент", "Ед.", "Остаток", "Расход в день", "Хватит на дней", "Закончится примерно"], data


REPORTS = {
    "Продажи по видам напитков": report_sales_by_drink,
    "Продажи по дням": report_sales_by_day,
    "Накладные (приход)": report_receipts,
    "Движение ингредиентов (оборотка)": report_movement,
}
