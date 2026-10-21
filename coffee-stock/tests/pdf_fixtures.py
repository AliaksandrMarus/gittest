"""Тестовые накладные: PDF с текстом и PDF-картинка (как со сканера)."""

import os
from pathlib import Path

import pytest

# Любой TTF с кириллицей: на Linux — DejaVu, на Windows (сборка в CI) — Arial
FONT = next((f for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", r"C:\Windows\Fonts\arial.ttf")
             if os.path.exists(f)), "")

HEADER = ["№", "Наименование товара", "Ед. изм.", "Количество", "Цена, руб.", "Стоимость, руб.",
          "Ставка НДС, %", "Сумма НДС, руб.", "Стоимость с НДС, руб."]

ROWS = [
    ["1", "Кофе зерновой Lavazza Crema", "кг", "3", "45,00", "135,00", "20", "27,00", "162,00"],
    ["2", "Стакан бумажный 250 мл", "шт", "1 000", "0,10", "100,00", "20", "20,00", "120,00"],
    ["3", "Сахар-песок", "кг", "5,5", "2,00", "11,00", "20", "2,20", "13,20"],
]


def make_invoice_pdf(path: Path, rows=ROWS, number="ТН 0012345", day="15.10.2026",
                     supplier="ООО Кофетрейд", total=True):
    pytest.importorskip("reportlab")
    if not FONT:
        pytest.skip("нет шрифта с кириллицей")
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(TTFont("DejaVu", FONT))
    text = ParagraphStyle("p", fontName="DejaVu", fontSize=11, leading=14)
    cell = ParagraphStyle("c", fontName="DejaVu", fontSize=10, leading=12)
    data = [[Paragraph(h, cell) for h in HEADER]] + [[Paragraph(c, cell) for c in r] for r in rows]
    if total:
        data.append([Paragraph(c, cell) for c in ["", "Итого", "", "", "", "", "", "", ""]])
    table = Table(data, colWidths=[25, 220, 50, 75, 65, 80, 65, 80, 95])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.7, "black"),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    SimpleDocTemplate(str(path), pagesize=landscape(A4)).build([
        Paragraph(f"ТОВАРНАЯ НАКЛАДНАЯ № {number} от {day}", text),
        Paragraph(f"Поставщик: {supplier}", text), Spacer(1, 12), table,
    ])


def make_scan_pdf(path: Path, **kwargs):
    """PDF, в котором только картинка страницы — без текстового слоя."""
    import pypdfium2 as pdfium

    source = path.with_suffix(".src.pdf")
    make_invoice_pdf(source, **kwargs)
    doc = pdfium.PdfDocument(str(source))
    image = doc[0].render(scale=300 / 72).to_pil().convert("L")
    doc.close()
    image.save(path, "PDF", resolution=300)
    source.unlink()
