"""Общий движок для торговых площадок.

Сайты меняют вёрстку, поэтому разбор сделан «по смыслу», а не по точным
CSS-классам: ищем ссылки на карточки по шаблону адреса, в карточке — пары
«подпись — значение», таблицы с колонками «Наименование/Количество»
и ссылки на файлы. Адреса и шаблоны лежат в sites.json; при поломке их
можно поправить без пересборки программы (файл в папке ТендерАгент).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import requests
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# butb отдаёт XHTML с заголовком <?xml?> — разбираем как HTML, это нормально.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .. import textnorm
from ..config import data_dir, resource_path
from ..models import Document, Position, Tender
from ..pricelist import parse_number

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
DOC_EXT = (".doc", ".docx", ".xls", ".xlsx", ".pdf", ".zip", ".rar", ".7z", ".rtf", ".odt", ".ods", ".txt")
OKRB_RE = re.compile(r"(?<![\d.])\d{2}\.\d{2}\.\d{2}(?:\.\d{3})?(?![\d.])")
DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})(?:\D{1,5}(\d{1,2})[:.](\d{2}))?")


class SiteError(Exception):
    pass


@dataclass
class SiteConfig:
    key: str
    title: str
    base_url: str
    search_urls: list[str]                 # шаблоны с {query} {okrb} {page}
    latest_urls: list[str] = field(default_factory=list)  # ленты без поиска
    detail_link_regex: str = ""
    id_regex: str = r"(\d+)\D*$"
    encoding: str = ""
    page_start: int = 1
    delay_seconds: float = 1.0


def load_site_configs() -> dict[str, SiteConfig]:
    defaults = json.loads(resource_path("tenderagent/sites/sites.json").read_text("utf-8"))
    user_file = data_dir() / "sites.json"
    if user_file.exists():
        try:
            user = json.loads(user_file.read_text("utf-8"))
            for k, v in user.items():
                defaults.setdefault(k, {}).update(v)
        except Exception:
            pass
    return {k: SiteConfig(key=k, **v) for k, v in defaults.items() if not k.startswith("_")}


_system_certs = False


def use_system_certificates() -> None:
    """Проверять сертификаты сайтов через хранилище Windows, как браузер.

    Встроенный в Python список не знает сертификатов, которые Windows
    подгружает сама (промежуточные у белорусских сайтов) или которые
    ставит антивирус, проверяющий HTTPS. Из-за этого были ошибки
    CERTIFICATE_VERIFY_FAILED, хотя в браузере сайты открывались.
    """
    global _system_certs
    if _system_certs:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
        _system_certs = True
    except Exception:  # noqa: BLE001 — без truststore работаем со встроенным списком
        pass


class Http:
    def __init__(self, log=print):
        use_system_certificates()
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9,be;q=0.8"})
        self.log = log
        self.cache: dict[str, str] = {}

    def get(self, url: str, encoding: str = "", retries: int = 3, **kw) -> requests.Response:
        last = None
        for attempt in range(retries):
            try:
                r = self.s.get(url, timeout=40, **kw)
                if r.status_code >= 500:
                    raise SiteError(f"{r.status_code} {url}")
                r.raise_for_status()
                if encoding:
                    r.encoding = encoding
                elif not r.encoding or r.encoding.lower() == "iso-8859-1":
                    r.encoding = r.apparent_encoding
                return r
            except requests.exceptions.SSLError as e:
                raise SiteError(
                    f"Не удалось проверить сертификат сайта {urlparse(url).netloc}. Если сайт открывается "
                    f"в браузере, проверьте дату и время на компьютере и пришлите разработчику эту ошибку: {e}"
                ) from e
            except (requests.RequestException, SiteError) as e:
                last = e
                time.sleep(2 * (attempt + 1))
        raise SiteError(f"Не удалось открыть {url}: {last}")

    def get_text(self, url: str, encoding: str = "") -> str:
        """GET с кэшем на один проход мониторинга (ленты без поиска не качаем дважды)."""
        if url not in self.cache:
            self.cache[url] = self.get(url, encoding).text
        return self.cache[url]

    def download(self, url: str, folder: Path, name_hint: str = "", referer: str = "") -> Path:
        """Скачать файл документации. Проверяет, что пришёл файл, а не веб-страница.

        Некоторые площадки вместо файла отдают HTML (нужна сессия, переадресация,
        проверка браузера). Такой ответ не сохраняем под видом .pdf/.docx — иначе
        дальше «битый PDF» — а кладём в «Диагностика» и сообщаем.
        """
        headers = {"Referer": referer} if referer else {}
        r = self.s.get(url, timeout=120, headers=headers)
        r.raise_for_status()
        data = r.content
        stub = _file_info_stub(data)
        if stub is not None:
            # goszakupki: ссылка отдаёт справку о файле (JSON), сам файл — по той же ссылке с &download=1
            name_hint = stub.get("name") or name_hint
            real = url + ("&" if "?" in url else "?") + "download=1"
            r = self.s.get(real, timeout=180, headers={"Referer": referer or url})
            r.raise_for_status()
            data = r.content
            if _file_info_stub(data) is not None:
                raise SiteError("площадка вернула справку о файле вместо самого файла")
        if _looks_like_html(data):
            # Попробуем пройти по ссылке/переадресации со страницы-заглушки один раз.
            nxt = _next_link_from_html(data, r.url)
            if nxt and nxt != url:
                r2 = self.s.get(nxt, timeout=120, headers={"Referer": r.url})
                if r2.ok and not _looks_like_html(r2.content):
                    r, data = r2, r2.content
        name = _filename_from_response(r) or name_hint or Path(urlparse(url).path).name or "file"
        name = _safe_name(name)
        if _looks_like_html(data):
            diag = data_dir() / "Диагностика"
            diag.mkdir(parents=True, exist_ok=True)
            (diag / f"скачивание_{Path(name).stem[:60]}.html").write_bytes(data)
            raise SiteError("сайт вернул веб-страницу вместо файла (копия в папке «Диагностика»). "
                            "Скачайте файл вручную в папку «Документация» тендера и нажмите «Скачать документы "
                            "и сверить» ещё раз")
        from ..docs.unwrap import SIGNED_DIR, unwrap

        signed = data
        data = unwrap(data)  # документ, подписанный ЭЦП заказчика, — достаём из конверта
        name = _fix_extension(name, data)
        folder.mkdir(parents=True, exist_ok=True)
        if data is not signed and data != signed:
            keep = folder / SIGNED_DIR
            keep.mkdir(exist_ok=True)
            (keep / (name + ".p7s")).write_bytes(signed)
        path = folder / name
        if path.exists():
            old = path.read_bytes()
            if old == data:
                return path
            if is_bad_download(old):
                path.write_bytes(data)  # на месте старой справки/страницы — настоящий файл
                return path
        n = 1
        while path.exists():
            path = folder / f"{Path(name).stem} ({n}){Path(name).suffix}"
            n += 1
        path.write_bytes(data)
        return path


def is_bad_download(data: bytes) -> bool:
    """Вместо файла сохранилась веб-страница или справка о файле (goszakupki)."""
    head = data[:65537]
    return _looks_like_html(head[:8000]) or _file_info_stub(head) is not None


def _file_info_stub(data: bytes) -> dict | None:
    """Ответ вида {"ok":true,"info":{"name":"…docx","size":"24.67Кб",…}} — справка, а не файл."""
    head = data[:4096].lstrip()
    if not head.startswith(b"{") or len(data) > 65536:
        return None
    try:
        import json

        obj = json.loads(data.decode("utf-8", "replace"))
    except ValueError:
        return None
    if isinstance(obj, dict) and isinstance(obj.get("info"), dict) and "ok" in obj:
        return obj["info"]
    return None


def _looks_like_html(data: bytes) -> bool:
    head = data[:1024].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html")) or (head.startswith(b"<") and b"<html" in data[:8000].lower())


def _next_link_from_html(data: bytes, base: str) -> str:
    try:
        soup = BeautifulSoup(data, "lxml")
    except Exception:  # noqa: BLE001
        return ""
    meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    if meta and "url=" in (meta.get("content") or "").lower():
        return urljoin(base, meta["content"].split("=", 1)[1].strip(" '\""))
    for a in soup.find_all("a", href=True):
        h = a["href"].lower()
        if re.search(r"(get-file|download|/file)", h) or h.split("?")[0].endswith(DOC_EXT):
            return urljoin(base, a["href"])
    return ""


_MAGIC = [
    (b"%PDF", ".pdf", (".pdf",)),
    (b"PK\x03\x04", ".zip", (".docx", ".xlsx", ".xlsm", ".zip", ".odt", ".ods", ".pptx")),
    (b"\xd0\xcf\x11\xe0", ".doc", (".doc", ".xls", ".ppt", ".msg")),
    (b"Rar!", ".rar", (".rar",)),
    (b"7z\xbc\xaf", ".7z", (".7z",)),
    (b"{\\rtf", ".rtf", (".rtf", ".doc")),
]


def _fix_extension(name: str, data: bytes) -> str:
    """Расширение по содержимому: «прейскуранту» → «прейскуранту.xls» и т.п."""
    ext = Path(name).suffix.lower()
    for magic, default, allowed in _MAGIC:
        if data.startswith(magic):
            if ext in allowed:
                return name
            if magic.startswith(b"PK"):
                low = data[:4000]
                default = ".docx" if b"word/" in low else ".xlsx" if b"xl/" in low else ".zip"
            elif magic.startswith(b"\xd0"):
                default = ".xls" if b"W\x00o\x00r\x00k\x00b\x00o\x00o\x00k" in data[:200000] else ".doc"
            return name + default if not ext or len(ext) > 5 else Path(name).stem + default
    return name


def _filename_from_response(r: requests.Response) -> str:
    cd = r.headers.get("content-disposition", "")
    m = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", cd)
    if m:
        from urllib.parse import unquote

        return unquote(m.group(1))
    m = re.search(r'filename="?([^";]+)"?', cd)
    if m:
        raw = m.group(1)
        try:
            return raw.encode("latin-1").decode("utf-8")
        except UnicodeError:
            try:
                return raw.encode("latin-1").decode("cp1251")
            except UnicodeError:
                return raw
    return ""


def _safe_name(name: str, limit: int = 70) -> str:
    """Имя файла для Windows: без запрещённых символов и не длиннее limit
    (Word/Excel не открывают файлы с полным путём длиннее 259 символов)."""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip(" .")
    stem, dot, ext = name.rpartition(".")
    if not dot or len(ext) > 5:
        stem, ext = name, ""
    stem = stem[: max(10, limit - len(ext) - 1)].rstrip(" ._")
    return (f"{stem}.{ext}" if ext else stem) or "file"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_date(text: str, end_of_day: bool = False) -> str:
    """ДД.ММ.ГГГГ [ЧЧ:ММ] → ISO. Без времени: 00:00 или 23:59 (для сроков подачи)."""
    m = DATE_RE.search(text or "")
    if not m:
        return ""
    d, mo, y, h, mi = m.groups()
    if h is None and end_of_day:
        h, mi = 23, 59
    try:
        dt = datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0))
    except ValueError:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M")


class GenericSite:
    """Базовый адаптер. Конкретные сайты переопределяют отдельные шаги."""

    def __init__(self, cfg: SiteConfig, http: Http, log=print):
        self.cfg = cfg
        self.http = http
        self.log = log

    # --- поиск ----------------------------------------------------------
    def search(self, query: str = "", okrb: str = "", pages: int = 1) -> list[Tender]:
        found: dict[str, Tender] = {}
        templates = self.cfg.search_urls if (query or okrb) else self.cfg.latest_urls
        for tpl in templates:
            if "{okrb}" in tpl and not okrb:
                continue
            if "{query}" in tpl and not query:
                continue
            for page in range(self.cfg.page_start, self.cfg.page_start + pages):
                url = tpl.format(query=quote_plus(query), okrb=quote_plus(okrb), page=page,
                                 today=datetime.now().strftime("%d.%m.%Y"))
                try:
                    html = self.http.get_text(url, self.cfg.encoding)
                except SiteError as e:
                    self.log(f"{self.cfg.title}: {e}")
                    break
                rows = self.parse_list(html, url)
                new = 0
                trusted = "{query}" in tpl or "{okrb}" in tpl
                for t in rows:
                    if trusted:
                        t.fields["_trusted"] = query or okrb
                    if t.uid not in found:
                        found[t.uid] = t
                        new += 1
                time.sleep(self.cfg.delay_seconds)
                if new == 0:
                    break
        return list(found.values())

    def parse_list(self, html: str, page_url: str) -> list[Tender]:
        soup = BeautifulSoup(html, "lxml")
        rx = re.compile(self.cfg.detail_link_regex)
        result: dict[str, Tender] = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(page_url, a["href"])
            if not rx.search(href):
                continue
            ext_id = self.ext_id(href)
            if not ext_id:
                continue
            row = a.find_parent("tr") or a.find_parent(["li", "article", "div"])
            row_text = clean(row.get_text(" ")) if row else clean(a.get_text(" "))
            title = clean(a.get_text(" "))
            t = result.get(ext_id)
            if t is None:
                t = Tender(site=self.cfg.key, ext_id=ext_id, url=href)
                result[ext_id] = t
            if len(title) > len(t.title) and not re.fullmatch(r"[\d\-/№ ]+", title):
                t.title = title
            t.fields.setdefault("_row", row_text)
            if not t.deadline:
                dates = [parse_date(m.group(0), end_of_day=True) for m in DATE_RE.finditer(row_text)]
                dates = [d for d in dates if d]
                if dates:
                    t.deadline = max(dates)
            if t.estimate is None and row is not None:
                t.estimate = _money_in(row_text)
        for t in result.values():
            if not t.title:
                t.title = t.fields.get("_row", "")[:200]
        return list(result.values())

    def ext_id(self, href: str) -> str:
        m = re.search(self.cfg.id_regex, href)
        return m.group(1) if m else ""

    # --- карточка -------------------------------------------------------
    def fetch_html(self, t: Tender) -> tuple[str, str]:
        r = self.http.get(t.url, self.cfg.encoding)
        return r.text, r.url

    def fetch_details(self, t: Tender) -> Tender:
        html, url = self.fetch_html(t)
        self.parse_details(t, html, url)
        t.page_html = html  # копия страницы сохраняется в папку тендера (не в базу)
        return t

    def parse_details(self, t: Tender, html: str, url: str) -> None:
        soup = BeautifulSoup(html, "lxml")
        for bad in soup(["script", "style", "noscript"]):
            bad.decompose()
        kv = extract_key_values(soup)
        t.fields.update(kv)
        h1 = soup.find(["h1", "h2"])
        title = _pick(kv, ["предмет закупки", "наименование закупки", "краткое описание предмета",
                           "наименование процедуры", "название", "предмет"])
        if title:
            t.title = title
        elif h1 and len(clean(h1.get_text())) > 10 and not t.title:
            t.title = clean(h1.get_text())
        heading_num = None
        for h in soup.find_all(["h1", "h2", "h3", "title"]):
            heading_num = re.search(r"№\s*([A-Za-zА-Яа-я]*\d[\w\-/]*)", h.get_text(" "))
            if heading_num:
                break
        kv_num = _pick(kv, ["номер процедуры", "номер закупки", "номер", "№"])
        # Номер — это код с цифрами (auc0003717571, 2026-1234567), а не ФИО или текст,
        # случайно попавший под подпись «№»/«номер» (например, «номер телефона»).
        if not re.fullmatch(r"[A-Za-zА-Яа-я]{0,6}[\s\-№]*\d[\w\-/.]{2,30}", kv_num or ""):
            kv_num = ""
        t.number = ((heading_num.group(1) if heading_num else "") or kv_num or t.number or t.ext_id)
        t.customer = _pick_customer(kv) or t.customer
        unp = re.search(r"\b\d{9}\b", _pick(kv, ["унп"]) or "")
        t.customer_unp = unp.group(0) if unp else t.customer_unp
        t.procedure = _pick(kv, ["вид процедуры", "вид закупки", "тип процедуры", "способ закупки"]) or t.procedure
        dl = _pick(kv, ["окончания приема", "окончания приёма", "окончания подачи", "окончание приема",
                        "окончание приёма", "окончание подачи", "срок подачи", "предложения принимаются до",
                        "дата и время окончания", "дата окончания"])
        if dl and parse_date(dl):
            t.deadline = parse_date(dl)
            if not re.search(r"\d{1,2}[:.]\d{2}\s*$|\d{4}\D{1,5}\d{1,2}[:.]\d{2}", dl):
                t.deadline = t.deadline[:-5] + "23:59"  # указана только дата — до конца дня
        pub = _pick(kv, ["дата размещения", "дата публикации", "размещено"])
        if pub:
            t.published = parse_date(pub)
        est = _pick(kv, ["ориентировочная стоимость", "общая ориентировочная", "стоимость закупки",
                         "начальная цена", "стоимость"])
        if est:
            t.estimate = _money_in(est) or t.estimate
        page_text = soup.get_text(" ")
        t.fields.update(site_conditions(kv, page_text))
        t.okrb = sorted(set(OKRB_RE.findall(page_text)))
        positions = extract_positions_from_tables(soup.find_all("table"), source="сайт")
        if positions:
            t.positions = positions
        elif not t.positions and t.title:
            t.positions = [Position(name=t.title, source="сайт")]
        t.documents = extract_documents(soup, url)


def _money_in(text: str) -> float | None:
    # (?<![\d.]) — не захватывать год из стоящей рядом даты «05.10.2026 1 620.00 BYN»
    m = re.search(r"(?<![\d.,])(\d{1,3}(?:[ \xa0]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*"
                  r"(?:BYN|бел|руб|Br|р\.)", text or "", re.I)
    if not m:
        m = re.fullmatch(r"\s*(\d[\d\s\xa0]*(?:[.,]\d+)?)\s*", text or "")
    return parse_number(m.group(1)) if m else None


_NOT_CUSTOMER = re.compile(r"(контакт|телефон|лицо|ф\.?и\.?о|адрес|место нахождения|местонахождени|унп|"
                           r"e-?mail|почт|факс|ответственн|должност|срок|дата|время|ответ|запрос)", re.I)


def _pick_customer(kv: dict[str, str]) -> str:
    """Наименование заказчика — не «контактное лицо заказчика», не адрес и не УНП."""
    for want in ("наименование заказчика", "наименование организации", "заказчик", "организатор",
                 "организация"):
        for k, v in kv.items():
            kl = k.lower().replace("ё", "е")
            if want not in kl or not v:
                continue
            # «Наименование заказчика (ФИО — для ИП)» — то, что нужно; «Контактное лицо заказчика»,
            # «Срок размещения заказчиком…», «Адрес заказчика» — нет.
            if kl.startswith("наименование") or not _NOT_CUSTOMER.search(kl):
                return v
    return ""


_CONDITIONS = [
    ("Срок поставки", r"срок\w*\s+(поставки|выполнения|оказания)"),
    ("Условия оплаты", r"(услови\w*|порядок|срок\w*)\s+(оплаты|расчет\w*)"),
    ("Место поставки", r"(место|адрес|пункт)\s+(поставки|доставки)"),
    ("Условия поставки", r"услови\w*\s+(поставки|доставки)"),
    ("Источник финансирования", r"источник\w*\s+финансирования"),
    ("Требования к маркировке", r"маркировк"),
]


def site_conditions(kv: dict[str, str], page_text: str) -> dict[str, str]:
    """Сроки поставки, условия оплаты и т.п. со страницы закупки — для нашего предложения."""
    out: dict[str, str] = {}
    for title, pat in _CONDITIONS:
        for k, v in kv.items():
            if re.search(pat, k, re.I) and v and len(v) < 600:
                out[title] = v
                break
        if title in out:
            continue
        m = re.search(rf"(?:{pat})[^:\n]{{0,40}}:\s*(.{{5,300}}?)(?=\s+(?:Место|Срок|Услови|Порядок|Источник|"
                      rf"Статус|Количество|$))", page_text, re.I | re.S)
        if m:
            out[title] = re.sub(r"\s+", " ", m.group(m.lastindex)).strip(" .;")
    return out


def _pick(kv: dict[str, str], keys: list[str]) -> str:
    low = {k.lower().replace("ё", "е"): v for k, v in kv.items()}
    for want in keys:
        w = want.replace("ё", "е")
        for k, v in low.items():
            if w in k and v:
                return v
    return ""


def extract_key_values(soup) -> dict[str, str]:
    kv: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) == 2:
            k, v = clean(cells[0].get_text(" ")), clean(cells[1].get_text(" "))
            if 2 < len(k) < 150 and v and k not in kv:
                kv[k.rstrip(":")] = v
    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                kv.setdefault(clean(dt.get_text(" ")).rstrip(":"), clean(dd.get_text(" ")))
    # Вёрстка на div: <div class="...label">Подпись</div><div>Значение</div>
    for lab in soup.find_all(class_=re.compile(r"(label|title|caption|name)", re.I)):
        if lab.name in ("tr", "table"):
            continue
        k = clean(lab.get_text(" "))
        nxt = lab.find_next_sibling()
        if nxt and 2 < len(k) < 120 and k not in kv:
            v = clean(nxt.get_text(" "))
            if v and len(v) < 2000:
                kv[k.rstrip(":")] = v
    return kv


_COL_ROLES = {
    "name": [r"наимен", r"предмет", r"товар", r"описание", r"номенклатур"],
    "qty": [r"кол-?во", r"количеств", r"объем", r"объём"],
    "unit": [r"ед\.?\s*изм", r"^ед\b", r"единиц"],
    "okrb": [r"окрб", r"код\s*по"],
    "price": [r"стоимост", r"цена", r"сумма"],
    "lot": [r"^№\s*лота", r"^лот", r"номер лота", r"^№", r"п/п"],
}


def map_columns(headers: list[str]) -> dict[str, int]:
    roles: dict[str, int] = {}
    for j, h in enumerate(headers):
        hl = h.lower().replace("ё", "е")
        for role in ("okrb", "unit", "qty", "price", "lot", "name"):
            if role in roles:
                continue
            if any(re.search(p, hl) for p in _COL_ROLES[role]):
                if role == "name" and re.search(r"заказчик|организац|участник|производител", hl):
                    continue
                roles[role] = j
                break
    return roles


_QTY_CELL = re.compile(r"^\s*(\d[\d\s\xa0]*(?:[.,]\d+)?)\s+([^\d,;][^,;]*?)\s*(?:[,;]\s*(.+))?$")


def positions_from_rows(rows: list[list[str]], source: str) -> list[Position]:
    """rows[0] — шапка (может быть найдена ниже первой строки)."""
    for hi, header in enumerate(rows[:8]):
        cols = map_columns([clean(str(c)) for c in header])
        if "name" in cols and ("qty" in cols or "unit" in cols or "price" in cols):
            break
    else:
        return []
    out = []
    for row in rows[hi + 1 :]:
        cells = [clean(str(c)) if c is not None else "" for c in row]
        if len(cells) <= cols["name"]:
            continue
        name = cells[cols["name"]]
        if not name or len(name) < 3 or re.fullmatch(r"[\d.\s]+", name):
            continue
        if re.match(r"(итого|всего|в том числе|ндс)", name.lower()):
            continue

        def g(role):
            j = cols.get(role)
            return cells[j] if j is not None and j < len(cells) else ""

        okrb = OKRB_RE.search(g("okrb") or "")
        qty, unit, limit = parse_number(g("qty")), g("unit"), parse_number(g("price")) if g("price") else None
        # goszakupki: «150 пачка(пач.), 1 620.00 BYN» — количество, единица и стоимость в одной ячейке
        m = _QTY_CELL.match(g("qty"))
        if m:
            qty = parse_number(m.group(1))
            unit = unit or re.sub(r"\(.*?\)", "", m.group(2)).strip()
            if m.group(3) and limit is None:
                limit = _money_in(m.group(3)) or parse_number(m.group(3))
        out.append(Position(
            name=name,
            qty=qty,
            unit=unit,
            okrb=okrb.group(0) if okrb else "",
            price_limit=limit,
            lot=g("lot") if "lot" in cols and cols["lot"] != cols["name"] else "",
            source=source,
        ))
    return out


def extract_positions_from_tables(tables, source: str) -> list[Position]:
    best: list[Position] = []
    for tb in tables:
        if tb.find("table"):
            continue  # внешняя обёртка вёрстки
        rows = [[c.get_text(" ") for c in tr.find_all(["th", "td"])] for tr in tb.find_all("tr")]
        pos = positions_from_rows(rows, source)
        if len(pos) > len(best):
            best = pos
    return best


_SITE_DOCS = re.compile(r"(reglament|personal_data|регламент|политика обработки|инструкци\w* пользовател|"
                        r"руководств\w* пользовател|/help/|/faq)", re.I)


def extract_documents(soup, base_url: str) -> list[Document]:
    docs: dict[str, Document] = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        text = clean(a.get_text(" ")) or a.get("title", "")
        low_href, low_text = href.lower(), text.lower()
        path = urlparse(low_href).path
        is_doc = (
            path.endswith(DOC_EXT)
            or low_text.endswith(DOC_EXT)
            or re.search(r"(download|/file|get-file|dfile|attach|getfile|document/get)", low_href)
        )
        if not is_doc or href.startswith("mailto:"):
            continue
        if _SITE_DOCS.search(low_href) or _SITE_DOCS.search(low_text):
            continue  # регламент площадки, политика данных и т.п. — не документация закупки
        name = text if low_text.endswith(DOC_EXT) else (text or Path(path).name)
        docs.setdefault(href, Document(name=name[:150], url=href))
    return list(docs.values())


def tender_matches(t: Tender, keywords: list[str], okrb_codes: list[str], stop_words: list[str]) -> str:
    """Возвращает сработавший запрос или пустую строку."""
    text = " ".join([t.title, t.fields.get("_row", "")] + [p.name for p in t.positions])
    for sw in stop_words:
        if sw.strip() and textnorm.contains_keyword(text, sw):
            return ""
    for kw in keywords:
        if kw.strip() and textnorm.contains_keyword(text, kw):
            return kw
    codes = set(t.okrb) | {p.okrb for p in t.positions if p.okrb}
    all_text = text + " " + " ".join(codes)
    for code in okrb_codes:
        c = code.strip()
        if c and (any(x.startswith(c) for x in codes) or c in all_text):
            return c
    return ""
