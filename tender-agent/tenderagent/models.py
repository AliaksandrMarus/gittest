"""Общие структуры данных."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


@dataclass
class PriceItem:
    name: str
    price: float
    code: str = ""
    unit: str = ""
    vat_rate: float | None = None
    stock: float | None = None
    producer: str = ""
    country: str = ""
    row: int = 0


@dataclass
class Position:
    """Позиция, которую закупает заказчик (из лота или из спецификации)."""

    name: str
    qty: float | None = None
    unit: str = ""
    okrb: str = ""
    price_limit: float | None = None   # ориентировочная/предельная стоимость
    lot: str = ""
    source: str = ""                   # «сайт» или имя файла


@dataclass
class Match:
    position: Position
    item: PriceItem | None
    score: int
    manual: bool = False
    include: bool = True
    price: float | None = None          # цена за единицу без НДС для предложения

    @property
    def found(self) -> bool:
        return self.item is not None

    @property
    def qty(self) -> float:
        return self.position.qty if self.position.qty else 1.0


@dataclass
class Document:
    name: str
    url: str
    local_path: str = ""


@dataclass
class Tender:
    site: str
    ext_id: str
    url: str
    title: str = ""
    number: str = ""
    customer: str = ""
    customer_unp: str = ""
    deadline: str = ""          # ISO «2026-10-15T10:00»
    published: str = ""
    estimate: float | None = None
    currency: str = "BYN"
    okrb: list[str] = field(default_factory=list)
    procedure: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    positions: list[Position] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    matched_query: str = ""
    page_html: str = field(default="", repr=False, compare=False)

    @property
    def uid(self) -> str:
        return f"{self.site}:{self.ext_id}"

    @property
    def num(self) -> str:
        """Номер процедуры для документов. Старые версии иногда сохраняли сюда ФИО
        или телефон контактного лица — такое не используем, берём номер из ссылки."""
        n = (self.number or "").strip()
        if re.fullmatch(r"[A-Za-zА-Яа-я]{0,6}[\s\-№]*\d[\w\-/.]{2,30}", n):
            return n
        return self.ext_id.split("/")[-1]

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("page_html", None)  # страница хранится файлом в папке тендера, не в базе
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Tender":
        d = dict(d)
        d["positions"] = [Position(**p) for p in d.get("positions", [])]
        d["documents"] = [Document(**x) for x in d.get("documents", [])]
        return cls(**d)
