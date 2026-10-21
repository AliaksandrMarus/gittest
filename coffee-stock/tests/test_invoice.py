import os
import time
from pathlib import Path

import pytest

from coffee_stock import core, db, inbox, invoice

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / "t.db")


def make_invoice_pdf(path: Path, rows: list[list[str]], number="123", day="15.10.2026"):
    reportlab = pytest.importorskip("reportlab")  # noqa: F841
    if not os.path.exists(FONT):
        pytest.skip("нет шрифта с кириллицей")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle

    pdfmetrics.registerFont(TTFont("DejaVu", FONT))
    style = ParagraphStyle("p", fontName="DejaVu", fontSize=10)
    table = Table([["№", "Наименование товара", "Ед. изм.", "Количество", "Цена"]] + rows)
    table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
                               ("GRID", (0, 0), (-1, -1), 0.5, "black")]))
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    doc.build([Paragraph(f"Товарная накладная № {number} от {day}", style),
               Paragraph("Поставщик: ООО Кофетрейд", style), table])


def age(path: Path):
    old = time.time() - 60
    os.utime(path, (old, old))


ROWS = [
    ["1", "Кофе зерновой Lavazza Crema", "кг", "3", "45,00"],
    ["2", "Стакан бумажный 250 мл", "шт", "1 000", "0,10"],
    ["3", "Сахар-песок", "кг", "5,5", "2,00"],
]


def test_unit_conversion():
    assert invoice.unit_factor("кг", "г") == 1000
    assert invoice.unit_factor("шт.", "шт") == 1
    assert invoice.unit_factor("уп", "г") is None
    assert invoice.parse_number("1 000,50") == 1000.5


def test_offline_extraction(tmp_path):
    pdf = tmp_path / "n.pdf"
    make_invoice_pdf(pdf, ROWS)
    ex = invoice.extract_offline(pdf)
    assert [(l.name, l.qty, l.unit) for l in ex.lines] == [
        ("Кофе зерновой Lavazza Crema", 3, "кг"),
        ("Стакан бумажный 250 мл", 1000, "шт"),
        ("Сахар-песок", 5.5, "кг"),
    ]
    assert ex.number == "123"
    assert ex.date == "2026-10-15"
    assert "Кофетрейд" in ex.supplier


def test_inbox_posts_recognised_invoice(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    folders.create()
    pdf = folders.incoming / "накладная.pdf"
    make_invoice_pdf(pdf, ROWS)
    age(pdf)
    results = inbox.process_incoming(conn, folders, invoice.extract_offline)
    assert [(r.status) for r in results] == ["posted"]
    assert not pdf.exists() and (folders.done / "накладная.pdf").exists()

    ing = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM ingredients")}
    s = core.stock(conn)
    assert s[ing["Кофе в зёрнах"]] == 3000
    assert s[ing["Стаканчики"]] == 1000
    assert s[ing["Сахар"]] == 5500
    assert conn.execute("SELECT DISTINCT date FROM movements").fetchone()[0] == "2026-10-15"

    # Тот же файл ещё раз — не задваивается
    make_invoice_pdf(pdf, ROWS)
    age(pdf)
    assert [r.status for r in inbox.process_incoming(conn, folders, invoice.extract_offline)] == ["duplicate"]
    assert core.stock(conn)[ing["Кофе в зёрнах"]] == 3000


def test_unknown_line_waits_for_review_and_mapping_is_remembered(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    ing = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM ingredients")}

    def fake_claude(path):
        return invoice.Extracted(path.stem, "2026-10-20", "ИП Иванов", [
            invoice.Line("Мешалки деревянные 140 мм", 2, "уп"),
            invoice.Line("Доставка", 1, "усл"),
        ])

    folders.create()
    pdf = folders.incoming / "скан.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake 1")
    age(pdf)
    [res] = inbox.process_incoming(conn, folders, fake_claude)
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

    # Следующая такая же накладная проводится сама
    pdf2 = folders.incoming / "скан2.pdf"
    pdf2.write_bytes(b"%PDF-1.4 fake 2")
    age(pdf2)
    [res] = inbox.process_incoming(conn, folders, fake_claude)
    assert res.status == "posted"
    assert core.stock(conn)[ing["Палочки для размешивания"]] == 2000

    invoice.unpost_invoice(conn, inv_id)
    assert core.stock(conn)[ing["Палочки для размешивания"]] == 1000


def test_scan_without_text_goes_to_errors(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    folders.create()
    pdf = folders.incoming / "пусто.pdf"
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(pdf))
    c.rect(100, 100, 200, 200)
    c.save()
    age(pdf)
    [res] = inbox.process_incoming(conn, folders, invoice.extract_offline)
    assert res.status == "error" and "ключ Claude API" in res.message
    assert (folders.failed / "пусто.pdf").exists()


def test_fresh_file_is_left_for_later(conn, tmp_path):
    folders = inbox.Folders(tmp_path)
    folders.create()
    (folders.incoming / "пишется.pdf").write_bytes(b"%PDF")
    assert inbox.process_incoming(conn, folders, invoice.extract_offline) == []


def test_claude_extractor_builds_request_and_parses(monkeypatch, tmp_path):
    import anthropic
    from types import SimpleNamespace

    captured = {}

    class FakeMessages:
        def parse(self, **kwargs):
            captured.update(kwargs)
            model = kwargs["output_format"]
            parsed = model(number="45", date="2026-10-19", supplier="ООО Вендинг",
                           items=[{"name": "Шоколад горячий 1 кг", "quantity": 2, "unit": "кг"},
                                  {"name": "Брак", "quantity": 0, "unit": "шт"}])
            return SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)

    class FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 scan")
    ex = invoice.extract(pdf, "sk-test", "claude-opus-5-5")
    assert captured["api_key"] == "sk-test"
    doc = captured["messages"][0]["content"][0]
    assert doc["type"] == "document" and doc["source"]["media_type"] == "application/pdf"
    assert (ex.number, ex.date, ex.supplier) == ("45", "2026-10-19", "ООО Вендинг")
    assert [(l.name, l.qty, l.unit) for l in ex.lines] == [("Шоколад горячий 1 кг", 2, "кг")]
