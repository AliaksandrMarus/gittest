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
    (folder / "1. Документы заказчика").mkdir()
    make_offer_form(folder / "1. Документы заказчика" / "Приложение 2 Форма предложения.docx")
    a = eng.analyze(t, download=False)
    assert a.summary.total == 3 and a.summary.found == 2
    s.monitor.min_match_percent = 60
    assert eng.evaluate(t, a.matches).fits
    out = eng.prepare(t, a)
    names = {x.name for x in (out / "2. Наше предложение (для подачи)").iterdir()}
    assert "Приложение 2 Форма предложения (заполнено).docx" in names
    assert {"Сопроводительное письмо.docx", "Опись документов.docx", "Сведения об участнике.docx"} <= names
    assert (out / "3. Для проверки" / "ЧЕК-ЛИСТ перед подачей.docx").exists()
    assert (out / "Сведения о закупке.txt").exists()
    assert db.get(t.uid)["status"] == STATUS_READY


def test_butb_registry():
    """Реестр zakupki.butb.by (JSF): закупки без ссылок, разбираем таблицу."""
    from tenderagent.sites import Http, make_sites

    site = make_sites(Http())["butb"]
    html = (Path(__file__).parent / "fixtures" / "butb_reestr.html").read_text("utf-8")
    ts = site.parse_list(html, "https://zakupki.butb.by/auctions/reestrauctions.html;jsessionid=X")
    assert len(ts) >= 15
    t = ts[0]
    assert t.ext_id == "AU20261001394578"
    assert "Маска кислородная" in t.title
    assert t.estimate == 990.0
    assert t.deadline == "2026-10-13T23:59"
    assert "Медтехника" in t.customer
    assert t.fields["_butb_link"] == "fra:reestrAu:0:_t347"
    assert t.url == "https://zakupki.butb.by/auctions/reestrauctions.html"
    chesnok = [x for x in ts if "Чеснок" in x.title]
    assert chesnok and chesnok[0].estimate is None  # у запроса цен стоимость не указана
    assert chesnok[0].procedure == "заявка о ценах (тарифах)"


def test_goszakupki_real_pages():
    """Настоящие страницы goszakupki.by (сохранены программой в «Диагностика»)."""
    from tenderagent.models import Tender
    from tenderagent.sites import Http, make_sites

    site = make_sites(Http())["goszakupki"]
    fx = Path(__file__).parent / "fixtures"
    ts = site.parse_list((fx / "goszakupki_list.html").read_text("utf-8"), "https://goszakupki.by/tenders/posted")
    assert len(ts) == 20
    first = ts[0]
    assert first.ext_id == "single-source/view/3717571"
    assert first.estimate == 1620.0          # не «20261620» — год из даты не прилипает
    assert first.deadline == "2026-10-05T23:59"

    t = Tender("goszakupki", first.ext_id, "https://goszakupki.by/single-source/view/3717571")
    site.parse_details(t, (fx / "goszakupki_card.html").read_text("utf-8"), t.url)
    assert t.number == "auc0003717571"
    assert t.customer == "Докшицкий районный исполнительный комитет" and t.customer_unp == "300013863"
    assert t.deadline == "2026-10-05T23:59"
    p = t.positions[0]
    assert (p.name, p.qty, p.unit, p.price_limit) == ("Бумага офисная А4", 150.0, "пачка", 1620.0)
    names = [d.name for d in t.documents]
    assert len(names) == 3 and not any("Регламент" in n for n in names)


def test_requisites_from_company_card(tmp_path):
    """Карточка предприятия в свободной форме → поля реквизитов."""
    import docx

    from tenderagent.requisites_import import parse_requisites, read_text

    d = docx.Document()
    for line in [
        "Общество с ограниченной ответственностью «Ромашка»",
        "УНП 190000001",
        "220000, Минская область, г.Минск, ул.Ленина, 1 «а» пом. 2",
        "р/сч  №BY00ALFA30120000000000000000 ЗАО «Альфа-Банк», г.Минск, БИК ALFABY2X",
        "GLN основной 4810000000001 220000, Беларусь, г.Минск, ул. Ленина, д. 1 А",
        "Директор Иванов Иван Иванович",
        "На основании Устава",
        "Электронная почта info@romashka.by",
        "Тел. +375 (17) 123-45-67",
    ]:
        d.add_paragraph(line)
    p = tmp_path / "card.docx"
    d.save(p)
    r = parse_requisites(read_text(p))
    assert r["full_name"] == "Общество с ограниченной ответственностью «Ромашка»"
    assert r["short_name"] == "ООО «Ромашка»"
    assert r["unp"] == "190000001"
    assert r["legal_address"].startswith("220000, Минская область")
    assert r["bank_account"] == "BY00ALFA30120000000000000000"
    assert r["bank_name"] == "ЗАО «Альфа-Банк»" and r["bank_address"] == "г.Минск"
    assert r["bank_bic"] == "ALFABY2X"
    assert (r["director_position"], r["director_name"], r["director_short"]) == (
        "Директор", "Иванов Иван Иванович", "И.И. Иванов")
    assert r["acts_on"] == "Устава"
    assert r["email"] == "info@romashka.by"
    assert r["phone"] == "+375 (17) 123-45-67"  # не кусок номера счёта и не GLN


def test_tyre_pricelist_like_belshina(tmp_path):
    """Прайскурант вида «Белшины»: «Номенклатурный номер» — это код, а не наименование;
    «А/ШИНА 215/75R16C» должна находиться по «Автошина 215/75 R16C»."""
    import openpyxl

    from tenderagent import pricelist, textnorm
    from tenderagent.matching import PriceIndex

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ПРЕЙСКУРАНТ № 5"])
    ws.append(["Номенклатурный\nномер", "Код\nбазы ГП", "Наименование продукции", "Дата\nустановления\nцены",
               "Цена,\nBYN", "Штрихкод"])
    ws.append(["ШИНЫ"])
    rows = [("0101", "А/ШИНА 215/75R16C BEL-313 СЕР Л/ГРУЗ", 218.5),
            ("0102", "А/ШИНА 205/55R16 BEL-262 СЕР ЛЕГК Б/К", 163.02),
            ("0103", "А/ШИНА 225/65R17 BEL-295 СЕР ЛЕГК Б/К", 224.84),
            ("0104", "А/ШИНА 185/75R16C BEL-293 СЕР Л/ГР", 180.49)]
    for code, name, price in rows:
        ws.append([code, "K1", name, "01.05.2026", price, 4811644000000])
    p = tmp_path / "price.xlsx"
    wb.save(p)
    items, table = pricelist.load_items(p)
    assert pricelist.guess_columns(table.headers)["name"] == "Наименование продукции"
    assert items[0].name.startswith("А/ШИНА") and items[0].code == "0101"
    idx = PriceIndex(items)
    best = lambda q: idx.candidates(q, 1)[0]  # noqa: E731
    assert best("Автошина 215/75 R16C")[0].code == "0101" and best("Автошина 215/75 R16C")[1] >= 80
    assert best("Шина 205/55 R16 зимняя")[0].code == "0102"
    assert best("Автошины 225/65 R17 (зима)")[0].code == "0103"
    assert best("Закупка зимних автошин 285/65 R16C")[1] < 70   # такого размера нет
    # лишние слова не мешают, если типоразмер совпал
    gaz = best("Автошины на автомобиль ГАЗ 330273, 185/75R16C")
    assert gaz[0].code == "0104" and gaz[1] >= 85
    assert textnorm.contains_keyword("Автошины зимние", "шины")


def test_download_rejects_html_and_fixes_extension(tmp_path):
    from tenderagent.sites.base import _fix_extension, _looks_like_html

    assert _looks_like_html(b"<!DOCTYPE html><html><body>login</body></html>")
    assert not _looks_like_html(b"%PDF-1.7 ...")
    assert _fix_extension("прейскуранту", b"\xd0\xcf\x11\xe0" + b"\x00" * 100) == "прейскуранту.doc"
    assert _fix_extension("tz.pdf", b"%PDF-1.4") == "tz.pdf"
    assert _fix_extension("dogovor", b"PK\x03\x04....word/document.xml") == "dogovor.docx"


def test_folders_by_customer(tmp_path):
    """Тендеры / <Заказчик> / <дата № номер — предмет>; старые папки переносятся."""
    from tenderagent.config import tenders_dir
    from tenderagent.folders import DOCS, OFFER, customer_dir_name, tender_folder
    from tenderagent.models import Document, Tender

    assert customer_dir_name('Республиканское дочернее торговое унитарное предприятие "Медтехника" г.Гомель') \
        == "РДТУП Медтехника г.Гомель"
    assert customer_dir_name("Докшицкий районный исполнительный комитет") == "Докшицкий райисполком"
    assert customer_dir_name("") == "Заказчик не указан"

    t = Tender("goszakupki", "single-source/view/1", "u", title="Бумага офисная А4", number="auc0003717571",
               customer="Докшицкий районный исполнительный комитет", published="2026-10-02T00:00")
    f = tender_folder(t)
    assert f.parent == tenders_dir() / "Докшицкий райисполком"
    assert f.name == "2026-10-02 № auc0003717571 — Бумага офисная А4"
    # второй тендер того же заказчика — в той же папке заказчика
    t2 = Tender("icetrade", "2", "u", title="Ручки", number="auc2", customer=t.customer)
    assert tender_folder(t2).parent == f.parent

    # папка старого формата (1.0.x): Тендеры/<дата площадка номер предмет>/Документация
    old = tenders_dir() / "2026-10-06 goszakupki 123 Шины"
    (old / "Документация").mkdir(parents=True)
    (old / "Документация" / "tz.pdf").write_bytes(b"%PDF")
    (old / "Для подачи").mkdir()
    t3 = Tender("goszakupki", "3", "u", title="Шины", number="123", customer="ОАО «Завод»",
                documents=[Document("tz.pdf", "u", str(old / "Документация" / "tz.pdf"))])
    new = tender_folder(t3, str(old))
    assert not old.exists() and new.parent.name == "ОАО Завод"
    assert (new / DOCS / "tz.pdf").exists() and (new / OFFER).exists()
    assert t3.documents[0].local_path == str(new / DOCS / "tz.pdf")


def test_number_not_taken_from_contact_name():
    from tenderagent.models import Tender
    from tenderagent.sites import Http, make_sites

    html = """<html><body><h1>Процедура закупки</h1><table>
    <tr><td>Номер телефона / контактное лицо №</td><td>Ахрамович Василина Анатольевна</td></tr>
    <tr><td>Предмет закупки</td><td>Закупка автошин</td></tr></table></body></html>"""
    site = make_sites(Http())["goszakupki"]
    t = Tender("goszakupki", "tender/view/3720000", "https://goszakupki.by/tender/view/3720000")
    site.parse_details(t, html, t.url)
    assert "Ахрамович" not in t.number
