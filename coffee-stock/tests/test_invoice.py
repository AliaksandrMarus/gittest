import os
import sqlite3
import time
from pathlib import Path

import pytest

from coffee_stock import core, db, inbox, invoice, ocr
from pdf_fixtures import make_invoice_pdf, make_scan_pdf

EXPECTED = [
    ("Кофе зерновой Lavazza Crema", 3, "кг", 45, 27, 162),
    ("Стакан бумажный 250 мл", 1000, "шт", 0.1, 20, 120),
    ("Сахар-песок", 5.5, "кг", 2, 2.2, 13.2),
]

needs_tesseract = pytest.mark.skipif(ocr.find_tesseract() is None, reason="Tesseract не установлен")


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / "t.db")


def ingredients(conn):
    return {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM ingredients")}


def age(path: Path):
    old = time.time() - 60
    os.utime(path, (old, old))


def as_tuples(lines):
    return [(l.name, l.qty, l.unit.lower(), l.price, l.vat, l.total) for l in lines]


def test_unit_conversion_and_numbers():
    assert invoice.unit_factor("кг", "г") == 1000
    assert invoice.unit_factor("шт.", "шт") == 1
    assert invoice.unit_factor("Kr", "г") == 1000  # «кг», прочитанный сканом латиницей
    assert invoice.unit_factor("уп", "г") is None
    assert invoice.parse_number("1 000,50") == 1000.5
    assert invoice.parse_number("1.000.50") == 1000.5


def test_header_classification():
    kinds = [invoice.classify_header(h) for h in
             ["Наименование товара", "Ед. изм.", "Количество", "Цена, руб.", "Стоимость, руб.",
              "Ставка НДС, %", "Сумма НДС, руб.", "Стоимость с НДС, руб.", "Всего"]]
    assert kinds == ["name", "unit", "qty", "price", "amount", "rate", "vat", "total", "total"]


def test_text_pdf_extraction(tmp_path):
    pdf = tmp_path / "n.pdf"
    make_invoice_pdf(pdf)
    ex = invoice.extract(pdf)
    assert as_tuples(ex.lines) == EXPECTED
    assert (ex.number, ex.date) == ("ТН0012345", "2026-10-15")
    assert "Кофетрейд" in ex.supplier


@needs_tesseract
def test_scanned_pdf_is_recognised_with_ocr(tmp_path):
    pdf = tmp_path / "scan.pdf"
    make_scan_pdf(pdf)
    ex = invoice.extract(pdf)
    assert as_tuples(ex.lines) == EXPECTED
    assert ex.date == "2026-10-15"


def test_scan_without_ocr_goes_to_errors(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(ocr, "find_tesseract", lambda configured="": None)
    folders = inbox.Folders(tmp_path)
    folders.create()
    pdf = folders.incoming / "пусто.pdf"
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(pdf))
    c.rect(100, 100, 200, 200)
    c.save()
    age(pdf)
    [res] = inbox.process_incoming(conn, folders, invoice.extract)
    assert res.status == "error" and "Tesseract" in res.message
    assert (folders.failed / "пусто.pdf").exists()


def test_words_parser_handles_wrapped_names_and_totals():
    def w(text, x, y):
        return {"text": text, "x0": x, "x1": x + 6 * len(text), "top": y, "bottom": y + 9}

    words = [w("Наименование", 20, 10), w("Кол-во", 200, 10), w("Цена", 260, 10), w("Сумма", 320, 10),
             w("с", 360, 10), w("НДС", 370, 10),
             w("Шоколад", 20, 30), w("горячий", 70, 30), w("5", 200, 30), w("12,50", 260, 30),
             w("75,00", 320, 30),
             w("порошок", 20, 42),
             w("Итого", 20, 60), w("75,00", 320, 60)]
    [line] = invoice.lines_from_words(words)
    assert (line.name, line.qty, line.price, line.total) == ("Шоколад горячий порошок", 5, 12.5, 75)


def test_inbox_posts_recognised_invoice(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    folders.create()
    pdf = folders.incoming / "накладная.pdf"
    make_invoice_pdf(pdf)
    age(pdf)
    results = inbox.process_incoming(conn, folders, invoice.extract)
    assert [r.status for r in results] == ["posted"]
    assert not pdf.exists() and (folders.done / "накладная.pdf").exists()

    ing = ingredients(conn)
    s = core.stock(conn)
    assert s[ing["Кофе в зёрнах"]] == 3000
    assert s[ing["Стаканчики"]] == 1000
    assert s[ing["Сахар"]] == 5500
    assert conn.execute("SELECT DISTINCT date FROM movements").fetchone()[0] == "2026-10-15"

    header, rows = core.report_receipts(conn, "2026-10-01", "2026-10-31")
    assert rows[0][:3] == ["2026-10-15", "ТН0012345", "ООО Кофетрейд"]
    assert rows[-1][0] == "Итого" and rows[-1][7:9] == [49.2, 295.2]

    # Повторный скан той же накладной (другой файл, те же реквизиты) — не задваивается
    make_invoice_pdf(pdf)
    age(pdf)
    assert [r.status for r in inbox.process_incoming(conn, folders, invoice.extract)] == ["duplicate"]
    assert core.stock(conn)[ing["Кофе в зёрнах"]] == 3000


def test_unknown_line_waits_for_review_and_mapping_is_remembered(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    ing = ingredients(conn)

    def fake(path):
        return invoice.Extracted(path.stem, "2026-10-20", "ИП Иванов", [
            invoice.Line("Мешалки деревянные 140 мм", 2, "уп", 3, 1.2, 7.2),
            invoice.Line("Доставка", 1, "усл", 10, 2, 12),
        ])

    folders.create()
    pdf = folders.incoming / "скан.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake 1")
    age(pdf)
    [res] = inbox.process_incoming(conn, folders, fake)
    assert res.status == "review"
    inv_id = conn.execute("SELECT id FROM invoices").fetchone()[0]
    assert invoice.unresolved_lines(conn, inv_id) == 2
    with pytest.raises(ValueError):
        invoice.post_invoice(conn, inv_id)

    lines = conn.execute("SELECT id FROM invoice_lines ORDER BY id").fetchall()
    invoice.update_line(conn, lines[0]["id"], ing["Палочки для размешивания"], 500, False)
    invoice.update_line(conn, lines[1]["id"], None, None, True)
    invoice.post_invoice(conn, inv_id)
    assert core.stock(conn)[ing["Палочки для размешивания"]] == 1000

    pdf2 = folders.incoming / "скан2.pdf"
    pdf2.write_bytes(b"%PDF-1.4 fake 2")
    age(pdf2)
    [res] = inbox.process_incoming(conn, folders, fake)
    assert res.status == "posted"
    assert core.stock(conn)[ing["Палочки для размешивания"]] == 2000

    invoice.unpost_invoice(conn, inv_id)
    assert core.stock(conn)[ing["Палочки для размешивания"]] == 1000


def test_manual_invoice_and_editing_posted_invoice_reposts(conn):
    ing = ingredients(conn)
    coffee = ing["Кофе в зёрнах"]
    line = invoice.EditedLine("Кофе Jacobs 1 кг", 2, "шт", 40, 8, 88, coffee, 1000)
    inv_id = invoice.save_invoice(conn, None, "77", "2026-10-10", "ООО Зерно", [line], post=True)
    assert conn.execute("SELECT status FROM invoices WHERE id = ?", (inv_id,)).fetchone()[0] == "posted"
    assert core.stock(conn)[coffee] == 2000

    # Распознали 2, на самом деле 5 — исправляем проведённую накладную
    line.qty, line.total = 5, 220
    invoice.save_invoice(conn, inv_id, "77", "2026-10-11", "ООО Зерно", [line])
    assert core.stock(conn)[coffee] == 5000
    assert conn.execute("SELECT DISTINCT date FROM movements WHERE invoice_id = ?", (inv_id,)).fetchone()[0] \
        == "2026-10-11"

    # Новая строка без ингредиента — накладная уходит на проверку, приход снимается
    invoice.save_invoice(conn, inv_id, "77", "2026-10-11", "ООО Зерно",
                         [line, invoice.EditedLine("Что-то новое", 1, "шт")])
    assert conn.execute("SELECT status FROM invoices WHERE id = ?", (inv_id,)).fetchone()[0] == "review"
    assert core.stock(conn)[coffee] == 0


def test_old_database_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE drinks (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE sales (date TEXT NOT NULL, drink_id INTEGER NOT NULL, count INTEGER NOT NULL,
                            PRIMARY KEY (date, drink_id));
        CREATE TABLE invoice_lines (id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, raw_name TEXT NOT NULL,
                                    raw_qty REAL NOT NULL, raw_unit TEXT, ingredient_id INTEGER, factor REAL,
                                    ignored INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO settings VALUES ('forecast_days', '14');
        INSERT INTO drinks(name) VALUES ('Капучино');
    """)
    old.commit()
    old.close()
    conn = db.connect(path)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(invoice_lines)")}
    assert {"price", "vat", "total"} <= cols
    assert conn.execute("SELECT price FROM drinks").fetchone()[0] == 0


def test_fresh_file_is_left_for_later(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    folders.create()
    (folders.incoming / "пишется.pdf").write_bytes(b"%PDF")
    assert inbox.process_incoming(conn, folders, invoice.extract) == []


def test_ocr_cleanups():
    assert ocr.fix_lookalikes("3 Caxap-necok") == "3 Сахар-песок"
    assert ocr.fix_lookalikes("Lavazza Crema") == "Lavazza Crema"
    assert invoice.classify_header("№ п/п") == "num"
    assert invoice.unit_factor("lut", "шт") == 1 and invoice.unit_factor("kt", "г") == 1000
    line = invoice._make_line({"name": "2 Стакан бумажный 250 мл", "qty": "10"})
    assert line.name == "Стакан бумажный 250 мл"
