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


TTN_ROWS = [
    ("1", 'Кофе в зернах Grano Milano FRESH CLASSIC 1кг', "шт.", "15", "43.91", "658.65", "20", "131.73", "790.38", "2", "15"),
    ("2", 'Смесь сухая растворимая "Венда Кремер" 1кг', "шт.", "25", "11.40", "285.00", "20", "57.00", "342.00", "", "25"),
    ("3", 'Смесь сухая со вкусом "Дубайский шоколад" 1кг', "шт.", "3", "14.60", "43.80", "20", "8.76", "52.56", "", "3"),
    ("4", 'Сахар "Мир эспрессо" 1300х5 гр.', "шт.", "1", "40.34", "40.34", "10", "4.03", "44.37", "", ""),
    ("5", 'Размешиватель дерев. 140 мм, упаковка 250 шт', "упак", "3", "5.65", "16.95", "20", "3.39", "20.34", "", ""),
]


def make_ttn_scan(path: Path, angle: float = 0.4):
    """Скан, похожий на белорусскую ТТН: перекос, пунктир между строками, реквизиты бланка."""
    import pypdfium2 as pdfium
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from PIL import Image

    pytest.importorskip("reportlab")
    if not FONT:
        pytest.skip("нет шрифта с кириллицей")
    pdfmetrics.registerFont(TTFont("DejaVu", FONT))
    source = path.with_suffix(".src.pdf")
    c = canvas.Canvas(str(source), pagesize=A4)
    w, h = A4
    c.setFont("DejaVu", 7)
    c.drawString(400, h - 40, "Форма установлена постановлением Минфина")
    c.drawString(400, h - 50, "Республики Беларусь 30.06.2016 № 58")
    c.setFont("DejaVu", 13)
    c.drawString(120, h - 95, "ТОВАРНО-ТРАНСПОРТНАЯ НАКЛАДНАЯ   4692066")
    c.setFont("DejaVu", 10)
    c.drawString(250, h - 125, "17 июня 2026 г.")
    c.drawString(40, h - 150, 'Грузоотправитель   ООО "ПРОКСИМАВЕСТ" г.Минск, Партизанский пр., 6Д')
    c.drawString(40, h - 168, 'Грузополучатель   УП "БЕЛТЕХОСМОТР" г.Минск')
    c.drawString(40, h - 186, "Основание отпуска   Договор №87853И от 28.05.2026г")
    # Колонки как в ТТН: x-границы и двухстрочные подписи
    xs = [30, 200, 230, 268, 305, 350, 380, 420, 465, 500, 530, 565]
    heads = [("Наименование", "товара"), ("Ед.", "изм."), ("Коли-", "чество"), ("Цена,", "руб.коп."),
             ("Стоимость", "руб.коп."), ("Ставка", "НДС, %"), ("Сумма", "НДС"), ("Стоимость", "с НДС"),
             ("Кол-во", "гр. мест"), ("Масса", "груза"), ("Приме-", "чание")]
    top, head_h = h - 215, 34
    c.setFont("DejaVu", 7)
    c.setLineWidth(0.8)
    c.line(xs[0], top, xs[-1], top)
    c.line(xs[0], top - head_h, xs[-1], top - head_h)
    for (a, b), x0, x1 in zip(heads, xs, xs[1:]):
        c.drawCentredString((x0 + x1) / 2, top - 14, a)
        c.drawCentredString((x0 + x1) / 2, top - 24, b)
    y = top - head_h
    row_h = 26
    for r in TTN_ROWS:
        c.setFont("DejaVu", 8)
        c.drawString(xs[0] + 2, y - 11, r[0])
        name = r[1]
        c.drawString(xs[0] + 12, y - 11, name[:30])
        if len(name) > 30:
            c.drawString(xs[0] + 12, y - 21, name[30:])
        for i, val in enumerate(r[2:], start=1):
            c.drawRightString(xs[i + 1] - 3, y - 11, val)
        y -= row_h
        c.setDash(1, 2)
        c.line(xs[0], y, xs[-1], y)
        c.setDash()
    c.setFont("DejaVu", 8)
    c.drawString(xs[0] + 12, y - 11, "Итого")
    c.line(xs[0], top, xs[0], y)
    for x in xs[1:]:
        c.line(x, top, x, y)
    c.save()

    doc = pdfium.PdfDocument(str(source))
    image = doc[0].render(scale=300 / 72).to_pil().convert("L")
    doc.close()
    image = image.rotate(angle, resample=Image.BICUBIC, fillcolor=255, expand=False)
    image.save(path, "PDF", resolution=300)
    source.unlink()
