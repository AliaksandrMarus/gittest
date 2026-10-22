import json

import pytest

from coffee_stock import core, db, seed

DATA = {
    "ingredients": [{"name": "Кофе", "unit": "г", "min_stock": 100}, {"name": "Стакан", "unit": "шт"}],
    "drinks": [{"name": "Американо", "price": 2.0, "recipe": {"Кофе": 10, "Стакан": 1}}],
    "invoices": [{"number": "1", "date": "2026-01-10", "supplier": 'ООО "Тест"', "file": "тест.pdf", "lines": [
        {"name": "Кофе 1 кг", "qty": 2, "unit": "шт", "price": 10, "vat": 4, "total": 24,
         "ingredient": "Кофе", "factor": 1000},
        {"name": "Стаканы 50 шт", "qty": 2, "unit": "упак", "price": 1, "vat": 0.4, "total": 2.4,
         "ingredient": "Стакан", "factor": 50},
        {"name": "Доставка", "qty": 1, "unit": "усл", "price": 5, "vat": 1, "total": 6, "ingredient": None},
    ]}],
    "sales": {"2026-01-12": {"Американо": 10}, "2026-01-13": {"Американо": 5}, "2026-01-14": {"Американо": 5}},
    "inventory": [{"date": "2026-01-14", "ingredient": "Стакан", "actual": 70, "note": "пересчёт"}],
}


def test_seed_file_is_loaded_into_empty_database_and_renamed(tmp_path):
    conn = db.connect(tmp_path / "coffee.db")
    (tmp_path / seed.FILE_NAME).write_text(json.dumps(DATA, ensure_ascii=False), encoding="utf-8")
    message = seed.apply_from_folder(conn, tmp_path, tmp_path / "Продажи.xlsx")
    assert message
    assert not (tmp_path / seed.FILE_NAME).exists() and (tmp_path / seed.LOADED_NAME).exists()

    stock = {r["name"]: core.stock(conn)[r["id"]] for r in conn.execute("SELECT id, name FROM ingredients")}
    assert stock == {"Кофе": 2000 - 200, "Стакан": 70}  # 100 − 20 продано, инвентаризация → 70
    assert conn.execute("SELECT status FROM invoices").fetchone()[0] == "posted"
    assert core.report_sales_by_drink(conn, "2026-01-01", "2026-01-31")[1][-1][:3] == ["Итого", 20, 40]
    assert (tmp_path / "Продажи.xlsx").exists()
    assert not seed.needed(conn)
    # Второй файл в непустую базу не грузится
    (tmp_path / seed.FILE_NAME).write_text(json.dumps(DATA, ensure_ascii=False), encoding="utf-8")
    assert seed.apply_from_folder(conn, tmp_path, tmp_path / "Продажи.xlsx") == ""


def test_seed_file_validation(tmp_path):
    bad = dict(DATA, sales={"2026-01-12": {"Латте": 1}})
    path = tmp_path / "x.json"
    path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(seed.SeedError, match="Латте"):
        seed.load(path)
