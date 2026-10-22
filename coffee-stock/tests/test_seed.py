from coffee_stock import core, db, sales_excel, seed_ds152


def test_ds152_data_is_applied_once(tmp_path):
    conn = db.connect(tmp_path / "coffee.db")
    sales = tmp_path / "Продажи.xlsx"
    sales_excel.ensure_template(conn, sales)  # шаблон первой версии
    assert seed_ds152.needed(conn)
    seed_ds152.apply(conn, sales)
    assert not seed_ds152.needed(conn)
    assert (tmp_path / "Продажи (до переноса данных).xlsx").exists()

    stock = {r["name"]: core.stock(conn)[r["id"]] for r in conn.execute("SELECT id, name FROM ingredients")}
    assert stock == {"Кофе в зёрнах": 5906, "Сухое молоко (сливки)": 13336, "Шоколад (сухая смесь)": 1832,
                     "Сахар": 2330, "Палочки для размешивания": 0, "Стаканчики": 266, "Крышки": 300}
    assert core.stock(conn, "2026-07-01")[conn.execute(
        "SELECT id FROM ingredients WHERE name = 'Стаканчики'").fetchone()[0]] == 1100
    header, rows = core.report_sales_by_drink(conn, "2026-07-01", "2026-10-31")
    assert rows[-1][:3] == ["Итого", 834, 2787.5]
    total = conn.execute("SELECT SUM(total) FROM invoice_lines").fetchone()[0]
    assert round(total, 2) == 1366.98

    # Файл продаж совпадает с базой: повторный импорт ничего не меняет
    result = sales_excel.import_file(conn, sales)
    assert not result.errors
    assert core.report_sales_by_drink(conn, "2026-07-01", "2026-10-31")[1][-1][:3] == ["Итого", 834, 2787.5]


def test_seed_skips_database_in_use(tmp_path):
    conn = db.connect(tmp_path / "coffee.db")
    drink = conn.execute("SELECT id FROM drinks").fetchone()[0]
    with conn:
        core.set_sales_for_date(conn, "2026-10-01", {drink: 1})
    assert not seed_ds152.needed(conn)
