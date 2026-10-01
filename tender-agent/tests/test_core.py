import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("TENDERAGENT_HOME", str(tmp_path / "home"))
    yield tmp_path


def make_price(path: Path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Прайс-лист ООО «Ромашка» на 01.10.2026"])
    ws.append([])
    ws.append(["Код", "Номенклатура", "Ед. изм.", "Цена, руб.", "Остаток"])
    ws.append(["", "Канцтовары", "", "", ""])  # группа 1С без цены
    ws.append(["1001", "Бумага офисная А4 80 г/м2 500 л. SvetoCopy", "пачка", "12,50", 100])
    ws.append(["1002", "Ручка шариковая синяя BIC", "шт", 0.85, 500])
    ws.append(["1003", "Кабель ВВГнг 3х2,5", "м", 3.2, 1000])
    ws.append(["1004", "Кабель ВВГнг 3х1,5", "м", 2.1, 1000])
    ws.append(["1005", "Степлер №24/6 металлический", "шт", 9.9, 10])
    wb.save(path)


def test_pricelist_autodetect(tmp_path):
    from tenderagent import pricelist

    p = tmp_path / "price.xlsx"
    make_price(p)
    items, table = pricelist.load_items(p)
    assert len(items) == 5
    assert items[0].price == 12.5 and items[0].code == "1001" and items[0].unit == "пачка"


def test_matching_prefers_numbers(tmp_path):
    from tenderagent import pricelist
    from tenderagent.config import OfferTerms
    from tenderagent.matching import PriceIndex, match_positions
    from tenderagent.models import Position

    p = tmp_path / "price.xlsx"
    make_price(p)
    items, _ = pricelist.load_items(p)
    idx = PriceIndex(items)
    pos = [Position("Кабель силовой ВВГнг 3x1.5", qty=200, unit="м"),
           Position("Бумага для офисной техники формат А4, 80 г/м2", qty=50),
           Position("Ноутбук игровой", qty=1)]
    ms = match_positions(pos, idx, OfferTerms(), 60)
    assert ms[0].item.code == "1004"
    assert ms[1].item.code == "1001"
    assert ms[2].item is None


def make_offer_form(path: Path):
    import docx

    d = docx.Document()
    d.add_paragraph("Приложение 2. Форма ценового предложения")
    d.add_paragraph("Наименование участника: ____________________")
    d.add_paragraph("УНП: __________")
    t = d.add_table(rows=1, cols=7)
    for j, h in enumerate(["№ п/п", "Наименование товара", "Ед. изм.", "Количество",
                           "Цена за единицу без НДС, руб.", "Стоимость без НДС, руб.", "Стоимость с НДС, руб."]):
        t.rows[0].cells[j].text = h
    for i, (n, q) in enumerate([("Бумага офисная А4", "50"), ("Ручка шариковая синяя", "100"),
                                ("Маркер текстовыделитель", "10")], 1):
        r = t.add_row().cells
        r[0].text, r[1].text, r[2].text, r[3].text = str(i), n, "шт", q
    r = t.add_row().cells
    r[1].text = "Итого"
    d.add_paragraph("Анкета")
    a = d.add_table(rows=2, cols=2)
    a.rows[0].cells[0].text = "Юридический адрес"
    a.rows[1].cells[0].text = "Банковские реквизиты"
    d.save(path)


def test_fill_customer_form(tmp_path):
    import docx

    from tenderagent import pricelist
    from tenderagent.config import OfferTerms, Requisites
    from tenderagent.docs.fill import fill_docx, offer_lines
    from tenderagent.matching import PriceIndex, match_positions
    from tenderagent.models import Position

    p = tmp_path / "price.xlsx"
    make_price(p)
    items, _ = pricelist.load_items(p)
    req = Requisites(full_name="ООО «Ромашка»", unp="190000001", legal_address="г. Минск, ул. Ленина, 1",
                     bank_account="BY00ALFA30120000000000000000", bank_name="ЗАО «Альфа-Банк»")
    ms = match_positions([Position("Бумага офисная А4", 50), Position("Ручка шариковая синяя", 100),
                          Position("Маркер текстовыделитель", 10)], PriceIndex(items), OfferTerms(), 60)
    lines = offer_lines(ms, OfferTerms(), req)
    src = tmp_path / "form.docx"
    make_offer_form(src)
    dst = tmp_path / "out.docx"
    st = fill_docx(src, dst, lines, req, OfferTerms())
    assert st["offer_table"] and st["rows"] == 2
    d = docx.Document(dst)
    text = "\n".join(p.text for p in d.paragraphs)
    assert "ООО «Ромашка»" in text and "190000001" in text
    rows = [[c.text for c in r.cells] for r in d.tables[0].rows]
    assert rows[1][4] == "12,50" and rows[1][5] == "625,00" and rows[1][6] == "750,00"
    assert rows[2][4] == "0,85"
    assert rows[3][4] == ""  # маркера нет в прайсе
    assert rows[4][5] == "710,00"
    anketa = [[c.text for c in r.cells] for r in d.tables[1].rows]
    assert anketa[0][1] == "г. Минск, ул. Ленина, 1"
    assert "Альфа" in anketa[1][1]


LIST_HTML = """
<html><body><table id="auctions-list">
<tr><th>Название</th><th>Заказчик</th><th>Номер</th><th>Стоимость</th><th>Предложения до</th></tr>
<tr><td><a href="/tenders/all/view/1234567">Поставка бумаги офисной</a></td><td>ОАО «Завод»</td>
<td>auc0001234567</td><td>5 000,00 BYN</td><td>15.10.2099 10:00</td></tr>
<tr><td><a href="/tenders/all/view/1234568">Ремонт кровли</a></td><td>КУП</td>
<td>auc0001234568</td><td>90 000,00 BYN</td><td>16.10.2099</td></tr>
</table></body></html>
"""

DETAIL_HTML = """
<html><body><h1>Процедура закупки</h1>
<table class="details_table">
<tr><td>Номер процедуры</td><td>auc0001234567</td></tr>
<tr><td>Краткое описание предмета закупки</td><td>Поставка бумаги офисной</td></tr>
<tr><td>Наименование организации</td><td>ОАО «Завод», УНП 100000000</td></tr>
<tr><td>Дата и время окончания приема предложений</td><td>15.10.2099 10:00</td></tr>
<tr><td>Общая ориентировочная стоимость закупки</td><td>5 000,00 BYN</td></tr>
</table>
<table><tr><th>№ лота</th><th>Предмет закупки</th><th>Количество</th><th>Ед. изм.</th><th>Код ОКРБ</th></tr>
<tr><td>1</td><td>Бумага офисная А4</td><td>50</td><td>пачка</td><td>17.23.14.500</td></tr>
<tr><td>2</td><td>Ручка шариковая синяя</td><td>100</td><td>шт</td><td>32.99.12.100</td></tr></table>
<a href="/files/12345/Документация.docx">Документация.docx</a>
<a href="https://icetrade.by/info/files/777">Форма предложения.xlsx</a>
</body></html>
"""


def test_site_parsing():
    from tenderagent.models import Tender
    from tenderagent.sites import Http, load_site_configs
    from tenderagent.sites.base import GenericSite, tender_matches

    site = GenericSite(load_site_configs()["icetrade"], Http())
    ts = site.parse_list(LIST_HTML, "https://icetrade.by/search/auctions")
    assert [t.ext_id for t in ts] == ["1234567", "1234568"]
    assert ts[0].title == "Поставка бумаги офисной"
    assert ts[0].deadline == "2099-10-15T10:00"
    assert tender_matches(ts[0], ["бумага"], [], []) == "бумага"
    assert tender_matches(ts[1], ["бумага"], [], []) == ""
    t = Tender("icetrade", "1234567", "https://icetrade.by/tenders/all/view/1234567")
    site.parse_details(t, DETAIL_HTML, t.url)
    assert t.number == "auc0001234567"
    assert t.estimate == 5000.0
    assert t.customer.startswith("ОАО «Завод»")
    assert len(t.positions) == 2 and t.positions[0].qty == 50
    assert "17.23.14.500" in t.okrb
    assert len(t.documents) == 2
    assert tender_matches(t, [], ["17.23"], []) == "17.23"


def test_full_prepare(tmp_path):
    from tenderagent import pricelist
    from tenderagent.config import Requisites, Settings
    from tenderagent.db import DB, STATUS_READY
    from tenderagent.models import Position, Tender
    from tenderagent.pipeline import Engine, tender_folder

    p = tmp_path / "price.xlsx"
    make_price(p)
    s = Settings()
    s.requisites = Requisites(full_name="ООО «Ромашка»", unp="190000001")
    db = DB()
    eng = Engine(s, db, log=lambda *a: None)
    eng.set_price_items(pricelist.load_items(p)[0])
    t = Tender("manual", "x1", "https://example", title="Канцтовары", number="T-1", estimate=2000.0,
               positions=[Position("Канцтовары", 1)])
    folder = tender_folder(t)
    db.save_tender(t, folder=str(folder))
    (folder / "Документация").mkdir()
    make_offer_form(folder / "Документация" / "Приложение 2 Форма предложения.docx")
    a = eng.analyze(t, download=False)
    assert a.summary.total == 3 and a.summary.found == 2
    s.monitor.min_match_percent = 60
    assert eng.evaluate(t, a.matches).fits
    out = eng.prepare(t, a)
    names = {x.name for x in (out / "Для подачи").iterdir()}
    assert "Приложение 2 Форма предложения (заполнено).docx" in names
    assert {"Сопроводительное письмо.docx", "Опись документов.docx", "Сведения об участнике.docx"} <= names
    assert (out / "Для проверки" / "ЧЕК-ЛИСТ перед подачей.docx").exists()
    assert db.get(t.uid)["status"] == STATUS_READY
