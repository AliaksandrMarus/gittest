"""zakupki.butb.by — площадка на JSF/ICEfaces.

У закупок в реестре нет обычных ссылок: карточка открывается отправкой
формы «fra» (кнопка-ссылка с id вида fra:reestrAu:N:_t347) вместе со
служебным полем javax.faces.ViewState. Поэтому реестр разбираем по таблице,
а карточку получаем повторной отправкой формы из той же сессии.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Tender
from .base import GenericSite, _money_in, clean, parse_date

_ROW_LINK = re.compile(r"^fra:reestrAu:(\d+):")
_REG = re.compile(r"\b([A-Z]{2}\d{10,})\b")

# Заголовки колонок реестра → поле
_COLS = [
    ("рег", "reg"),
    ("наименование", "title"),
    ("вид", "procedure"),
    ("дата публикации", "published"),
    ("стоимость", "estimate"),
    ("заказчик", "customer"),
    ("финансирование", "funding"),
    ("срок подачи", "deadline"),
    ("дата и время торгов", "auction"),
    ("состояние", "state"),
]


class ButbSite(GenericSite):
    def search(self, query: str = "", okrb: str = "", pages: int = 1) -> list[Tender]:
        url = self.cfg.latest_urls[0] if self.cfg.latest_urls else self.cfg.search_urls[0]
        url = url.format(query="", okrb="", page=1, today="")
        html = self.http.get_text(url, self.cfg.encoding)
        return self.parse_list(html, url)

    def parse_list(self, html: str, page_url: str) -> list[Tender]:
        soup = BeautifulSoup(html, "lxml")
        links = [a for a in soup.find_all("a", id=True) if _ROW_LINK.match(a["id"])]
        if not links:
            return []
        table = links[0].find_parent("table")
        headers = [clean(th.get_text(" ")).lower() for th in table.find_all("th")] if table else []
        col: dict[str, int] = {}
        for j, h in enumerate(headers):
            for key, name in _COLS:
                if name not in col and key in h:
                    col[name] = j
                    break
        result = []
        for a in links:
            tr = a.find_parent("tr")
            cells = [clean(td.get_text(" ")) for td in tr.find_all("td", recursive=False)]

            def g(name, default=""):
                j = col.get(name)
                return cells[j] if j is not None and j < len(cells) else default

            reg = _REG.search(g("reg") or " ".join(cells))
            if not reg:
                continue
            state = g("state")
            t = Tender(site=self.cfg.key, ext_id=reg.group(1), url=page_url.split(";jsessionid")[0])
            t.number = reg.group(1)
            t.title = clean(a.get_text(" ")) or g("title")
            t.procedure = g("procedure")
            t.customer = g("customer")
            t.estimate = _money_in(g("estimate"))
            dl = parse_date(g("deadline"))
            if dl and dl.endswith("T00:00"):
                dl = dl[:-5] + "23:59"  # в реестре только дата — считаем весь день
            t.deadline = dl
            t.published = parse_date(g("published"))
            gias = re.search(r"/\s*(\d{6,})\s*$", g("reg"))
            t.fields.update({
                "_row": " ".join(cells),
                "_butb_link": a["id"],
                "_butb_page": page_url,
                "Состояние": state,
                "Финансирование": g("funding"),
            })
            if gias:
                t.fields["Номер в ГИАС"] = gias.group(1)
            if state and not re.search(r"подач", state, re.I):
                continue  # приём предложений уже закрыт
            result.append(t)
        return result

    def fetch_html(self, t: Tender) -> tuple[str, str]:
        """Открыть карточку: свежий реестр + отправка формы по ссылке строки."""
        list_url = self.cfg.latest_urls[0].format(query="", okrb="", page=1, today="")
        r = self.http.get(list_url, self.cfg.encoding)
        soup = BeautifulSoup(r.text, "lxml")
        link = None
        for a in soup.find_all("a", id=True):
            if _ROW_LINK.match(a["id"]):
                tr = a.find_parent("tr")
                if tr and t.ext_id in tr.get_text(" "):
                    link = a["id"]
                    break
        if not link:
            raise RuntimeError("закупка уже ушла с первой страницы реестра — откройте её на сайте по номере "
                               f"{t.ext_id}")
        form = soup.find("form", id="fra")
        data = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name:
                continue
            if inp.get("type") in ("checkbox", "radio") and not inp.has_attr("checked"):
                continue
            data[name] = inp.get("value", "")
        data[link] = link
        action = urljoin(r.url, form.get("action") or r.url)
        resp = self.http.s.post(action, data=data, timeout=60,
                                headers={"Referer": r.url, "Origin": self.cfg.base_url.rstrip("/")})
        resp.raise_for_status()
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = "utf-8"
        return resp.text, resp.url

    def parse_details(self, t: Tender, html: str, url: str) -> None:
        keep = dict(number=t.number, title=t.title, customer=t.customer, deadline=t.deadline,
                    estimate=t.estimate, url=t.url)
        super().parse_details(t, html, url)
        # Карточка на JSF: ссылки на файлы часто тоже кнопки формы — оставляем только настоящие.
        t.documents = [d for d in t.documents if d.url.startswith("http") and "#" not in d.url[-2:]]
        for k, v in keep.items():
            if v and (not getattr(t, k) or k in ("number", "url")):
                setattr(t, k, v)
        if t.deadline and t.deadline < datetime.now().strftime("%Y-%m-%d"):
            t.deadline = keep["deadline"] or t.deadline
