"""Пути, настройки и реквизиты компании.

Всё хранится в папке «Документы\\ТендерАгент», чтобы пользователь видел
свои файлы и мог их забрать: настройки, база, скачанные тендеры, готовые
предложения.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

APP_NAME = "ТендерАгент"
APP_VERSION = "1.0.0"


def _documents_dir() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5 — «Мои документы», даже если папка перенесена.
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
            if buf.value:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def data_dir() -> Path:
    override = os.environ.get("TENDERAGENT_HOME")
    base = Path(override) if override else _documents_dir() / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def tenders_dir() -> Path:
    d = data_dir() / "Тендеры"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resource_path(rel: str) -> Path:
    """Путь к файлу внутри программы (работает и из .exe PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


@dataclass
class Requisites:
    """Реквизиты участника. Вносятся один раз и подставляются во все документы."""

    full_name: str = ""          # Общество с ограниченной ответственностью «…»
    short_name: str = ""         # ООО «…»
    unp: str = ""
    okpo: str = ""
    legal_address: str = ""
    postal_address: str = ""
    bank_account: str = ""       # IBAN BY..
    bank_name: str = ""
    bank_bic: str = ""
    bank_address: str = ""
    director_position: str = "Директор"
    director_name: str = ""      # Иванов Иван Иванович
    director_short: str = ""     # И.И. Иванов
    acts_on: str = "Устава"      # действует на основании …
    contact_person: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    registration_info: str = ""  # Свидетельство о гос. регистрации №…, дата, орган
    vat_payer: bool = True
    is_resident: bool = True
    is_producer: bool = False    # производитель / дилер / посредник
    country_of_origin: str = "Республика Беларусь"


@dataclass
class OfferTerms:
    """Условия предложения по умолчанию (можно поменять в карточке тендера)."""

    vat_rate: float = 20.0
    prices_include_vat: bool = False   # цены в прайсе указаны с НДС?
    markup_percent: float = 0.0        # наценка (+) или скидка (−) к прайсу
    delivery_term: str = "в течение 10 календарных дней с даты получения заявки"
    delivery_terms_place: str = "доставка на склад заказчика за счёт поставщика"
    payment_terms: str = "оплата в течение 30 календарных дней после поставки"
    offer_validity_days: int = 60
    warranty: str = "согласно гарантии производителя"


@dataclass
class MonitorSettings:
    keywords: list[str] = field(default_factory=list)
    okrb_codes: list[str] = field(default_factory=list)
    stop_words: list[str] = field(default_factory=list)
    sites: dict[str, bool] = field(
        default_factory=lambda: {"icetrade": True, "goszakupki": True, "butb": True}
    )
    interval_minutes: int = 60
    pages_per_query: int = 2
    min_match_percent: int = 60        # доля позиций тендера, найденных в прайсе
    min_item_score: int = 70           # порог похожести названия (0–100)
    require_price_below_estimate: bool = True
    auto_download_docs: bool = True    # качать документы для анализа сразу
    auto_prepare: bool = False         # готовить пакет без нажатия кнопки
    start_monitoring_on_launch: bool = False
    minimize_to_tray: bool = True


@dataclass
class PriceListSettings:
    path: str = ""
    sheet: str = ""
    header_row: int = 0                # 0 — определить автоматически
    columns: dict[str, str] = field(default_factory=dict)  # роль -> заголовок


@dataclass
class Settings:
    requisites: Requisites = field(default_factory=Requisites)
    terms: OfferTerms = field(default_factory=OfferTerms)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    pricelist: PriceListSettings = field(default_factory=PriceListSettings)

    # --- сохранение -------------------------------------------------------
    @staticmethod
    def path() -> Path:
        return data_dir() / "settings.json"

    def save(self) -> None:
        p = self.path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(p)

    @classmethod
    def load(cls) -> "Settings":
        p = cls.path()
        if not p.exists():
            return cls()
        try:
            raw = json.loads(p.read_text("utf-8"))
        except Exception:
            return cls()
        return cls(
            requisites=_from_dict(Requisites, raw.get("requisites")),
            terms=_from_dict(OfferTerms, raw.get("terms")),
            monitor=_from_dict(MonitorSettings, raw.get("monitor")),
            pricelist=_from_dict(PriceListSettings, raw.get("pricelist")),
        )


def _from_dict(klass, data):
    obj = klass()
    if not isinstance(data, dict):
        return obj
    names = {f.name for f in fields(klass)}
    for k, v in data.items():
        if k in names:
            setattr(obj, k, v)
    return obj
