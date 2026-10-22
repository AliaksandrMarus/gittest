"""Проверка invoice_kit на синтетических накладных (реальных документов в тестах нет)."""

import os
import time
from pathlib import Path

import pytest

from invoice_kit import inbox, ocr, recognize, store
from invoice_kit.recognize import Extracted, Line, extract
from pdf_fixtures import make_invoice_pdf, make_scan_pdf

EXPECTED = [
    ("Кофе зерновой Lavazza Crema", 3, "кг", 45, 27, 162),
    ("Стакан бумажный 250 мл", 1000, "шт", 0.1, 20, 120),
    ("Сахар-песок", 5.5, "кг", 2, 2.2, 13.2),
]

needs_tesseract = pytest.mark.skipif(ocr.find_tesseract() is None, reason="Tesseract не установлен")


@pytest.fixture
def conn(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    with conn:
        conn.executemany("INSERT INTO items(name, unit) VALUES (?, ?)",
                         [("Кофе зерновой", "г"), ("Стакан бумажный", "шт"), ("Сахар", "г"),
                          ("Размешиватель", "шт")])
    return conn


def items(conn):
    return {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM items")}


def age(path: Path):
    old = time.time() - 60
    os.utime(path, (old, old))


def as_tuples(lines):
    return [(l.name, l.qty, l.unit.lower(), l.price, l.vat, l.total) for l in lines]


def test_text_pdf_extraction(tmp_path):
    pdf = tmp_path / "n.pdf"
    make_invoice_pdf(pdf)
    ex = extract(pdf)
    assert as_tuples(ex.lines) == EXPECTED
    assert (ex.number, ex.date) == ("ТН0012345", "2026-10-15")
    assert "Кофетрейд" in ex.supplier


@needs_tesseract
def test_scanned_pdf_is_recognised_with_ocr(tmp_path):
    pdf = tmp_path / "scan.pdf"
    make_scan_pdf(pdf)
    assert as_tuples(extract(pdf).lines) == EXPECTED


@needs_tesseract
def test_skewed_ttn_scan_with_dotted_rows(tmp_path):
    """Как реальная ТТН: перекос, пунктир, чужие даты/номера в бланке, графы «мест» и «масса»."""
    from pdf_fixtures import TTN_ROWS, make_ttn_scan

    pdf = tmp_path / "ttn.pdf"
    make_ttn_scan(pdf)
    ex = extract(pdf)
    assert (ex.number, ex.date, ex.supplier) == ("1234567", "2026-05-15", 'ООО "КОФЕСНАБ"')
    got = [(l.qty, l.price, l.vat, l.total) for l in ex.lines]
    assert got == [(float(r[3]), float(r[4]), float(r[7]), float(r[8])) for r in TTN_ROWS]


def test_words_parser_handles_wrapped_names_and_totals():
    def w(text, x, y):
        return {"text": text, "x0": x, "x1": x + 6 * len(text), "top": y, "bottom": y + 9}

    words = [w("Наименование", 20, 10), w("Кол-во", 200, 10), w("Цена", 260, 10), w("Сумма", 320, 10),
             w("с", 353, 10), w("НДС", 362, 10),
             w("Шоколад", 20, 30), w("горячий", 70, 30), w("5", 200, 30), w("12,50", 260, 30),
             w("75,00", 320, 30), w("порошок", 20, 42),
             w("Итого", 20, 60), w("75,00", 320, 60)]
    [line] = recognize.lines_from_words(words)
    assert (line.name, line.qty, line.price, line.total) == ("Шоколад горячий порошок", 5, 12.5, 75)


def test_numbers_units_and_ocr_cleanups():
    assert recognize.reconcile(9.9, 2.0, 11.0) == (5.5, 2.0)   # цифра количества прочитана неверно
    assert recognize.reconcile(3, 46.0, 135.0) == (3, 45.0)    # цифра цены прочитана неверно
    assert recognize.reconcile(7, 3.0, 10.0) == (7, 3.0)       # непонятно, что исправлять, — не трогаем
    assert recognize.parse_cell_numbers("1 000,50") == [1000.5]
    assert recognize.parse_cell_numbers("462.00 92.40") == [462.0, 92.4]
    line = recognize._make_line({"name": "Кофе", "qty": "12", "price": "38.50", "amount": "462.00 92.40",
                                 "total": "554.40"})
    assert (line.qty, line.price, line.vat, line.total) == (12, 38.5, 92.4, 554.4)
    assert recognize.unit_factor("lut", "шт") == 1 and recognize.unit_factor("kt", "г") == 1000
    assert recognize.classify_header("№ п/п") == "num"
    assert ocr.fix_lookalikes("3 Caxap-necok") == "3 Сахар-песок"
    assert ocr.fix_lookalikes("Кофе в 3ерНах") == "Кофе в зернах"
    for keep in ("1000х5", "HB80-280V", "0-80мм", "3шт", "6кг", "58002/14"):
        assert ocr.fix_lookalikes(keep) == keep


def test_textual_date_and_supplier_not_receiver():
    ex = Extracted()
    recognize.find_requisites("ТОВАРНАЯ НАКЛАДНАЯ № АБ 123\nДоговор № 5 от 01.01.2019\n"
                              "Грузополучатель ООО «Мы»\nПоставщик: ОДО «Ромашка» г. Минск\n"
                              "Дата 17 июня 2026 г.", ex)
    assert (ex.number, ex.date, ex.supplier) == ("АБ123", "2026-06-17", 'ОДО "Ромашка"')


def test_inbox_posts_recognised_invoice_and_skips_rescan(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    folders.create()
    pdf = folders.incoming / "накладная.pdf"
    make_invoice_pdf(pdf)
    age(pdf)
    assert [r.status for r in inbox.process_incoming(conn, folders)] == ["posted"]
    assert (folders.done / "накладная.pdf").exists()
    it, s = items(conn), store.stock(conn)
    assert (s[it["Кофе зерновой"]], s[it["Стакан бумажный"]], s[it["Сахар"]]) == (3000, 1000, 5500)

    make_invoice_pdf(pdf)  # повторный скан той же бумаги — другой файл, те же реквизиты
    age(pdf)
    assert [r.status for r in inbox.process_incoming(conn, folders)] == ["duplicate"]
    assert store.stock(conn)[it["Кофе зерновой"]] == 3000


def test_unknown_line_waits_for_review_and_mapping_is_remembered(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    folders.create()
    it = items(conn)

    def fake(path):
        return Extracted(path.stem, "2026-10-20", "ИП Иванов", [
            Line("Мешалки деревянные 140 мм", 2, "уп", 3, 1.2, 7.2),
            Line("Доставка", 1, "усл", 10, 2, 12),
        ])

    pdf = folders.incoming / "скан.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake 1")
    age(pdf)
    [res] = inbox.process_incoming(conn, folders, fake)
    assert res.status == "review"
    inv_id = conn.execute("SELECT id FROM invoices").fetchone()[0]
    with pytest.raises(ValueError):
        store.post_invoice(conn, inv_id)
    lines = conn.execute("SELECT id FROM invoice_lines ORDER BY id").fetchall()
    store.update_line(conn, lines[0]["id"], it["Размешиватель"], 500, False)  # 1 уп = 500 шт
    store.update_line(conn, lines[1]["id"], None, None, True)                  # услуга — не в остатки
    store.post_invoice(conn, inv_id)
    assert store.stock(conn)[it["Размешиватель"]] == 1000

    pdf2 = folders.incoming / "скан2.pdf"
    pdf2.write_bytes(b"%PDF-1.4 fake 2")
    age(pdf2)
    assert inbox.process_incoming(conn, folders, fake)[0].status == "posted"  # сопоставление запомнено
    assert store.stock(conn)[it["Размешиватель"]] == 2000
    store.unpost_invoice(conn, inv_id)
    assert store.stock(conn)[it["Размешиватель"]] == 1000


def test_edit_posted_invoice_reposts_and_fuzzy_alias(conn):
    coffee = items(conn)["Кофе зерновой"]
    line = store.EditedLine("Кофе зерновой Jacobs 1 кг 8Омм", 2, "шт", 40, 8, 88, coffee, 1000)
    inv_id = store.save_invoice(conn, None, "77", "2026-10-10", "ООО Зерно", [line], post=True)
    assert store.stock(conn)[coffee] == 2000
    line.qty = 5  # распознали 2, на самом деле 5
    store.save_invoice(conn, inv_id, "77", "2026-10-11", "ООО Зерно", [line])
    assert store.stock(conn)[coffee] == 5000
    # Скан читает название чуть иначе («80мм» / «8Омм») — сопоставление всё равно находится
    assert store.match_line(conn, "Кофе зерновой Jacobs 1 кг 80мм", "шт") == (coffee, 1000, False)


def test_scan_without_ocr_goes_to_errors(conn, tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    monkeypatch.setattr(ocr, "find_tesseract", lambda configured="": None)
    folders = inbox.Folders(tmp_path)
    folders.create()
    pdf = folders.incoming / "пусто.pdf"
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(pdf))
    c.rect(100, 100, 200, 200)
    c.save()
    age(pdf)
    [res] = inbox.process_incoming(conn, folders)
    assert res.status == "error" and "Tesseract" in res.message
    assert (folders.failed / "пусто.pdf").exists()
