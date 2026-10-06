"""Папки тендеров: Тендеры / <Заказчик> / <дата № номер — предмет> /.

В папке тендера хранится всё по нему:
  1. Документы заказчика           — скачанная документация (ТЗ, формы, проект договора);
  2. Наше предложение (для подачи) — заполненные формы и наши документы;
  3. Для проверки                  — чек-лист, сравнение с прайсом, таблица предложения;
  Сведения о закупке.txt          — номер, заказчик, сроки, ссылка на площадку.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from .config import tenders_dir
from .models import Tender

DOCS = "1. Документы заказчика"
OFFER = "2. Наше предложение (для подачи)"
CHECK = "3. Для проверки"
INFO = "Сведения о закупке.txt"
_OLD_NAMES = {"Документация": DOCS, "Для подачи": OFFER, "Для проверки": CHECK}
NO_CUSTOMER = "Заказчик не указан"

# Длинные организационно-правовые формы → общепринятые сокращения
_ABBR = [
    (r"республиканское\s+унитарное\s+предприятие", "РУП"),
    (r"коммунальное\s+унитарное\s+предприятие", "КУП"),
    (r"коммунальное\s+производственное\s+унитарное\s+предприятие", "КПУП"),
    (r"коммунальное\s+торговое\s+унитарное\s+предприятие", "КТУП"),
    (r"республиканское\s+дочернее\s+торговое\s+унитарное\s+предприятие", "РДТУП"),
    (r"частное\s+производственное\s+унитарное\s+предприятие", "ЧПУП"),
    (r"частное\s+торговое\s+унитарное\s+предприятие", "ЧТУП"),
    (r"частное\s+унитарное\s+предприятие", "ЧУП"),
    (r"унитарное\s+предприятие", "УП"),
    (r"открытое\s+акционерное\s+общество", "ОАО"),
    (r"закрытое\s+акционерное\s+общество", "ЗАО"),
    (r"акционерное\s+общество", "АО"),
    (r"общество\s+с\s+ограниченной\s+ответственностью", "ООО"),
    (r"общество\s+с\s+дополнительной\s+ответственностью", "ОДО"),
    (r"государственное\s+учреждение\s+образования", "ГУО"),
    (r"государственное\s+учреждение\s+здравоохранения", "ГУЗ"),
    (r"учреждение\s+здравоохранения", "УЗ"),
    (r"государственное\s+учреждение", "ГУ"),
    (r"учреждение\s+образования", "УО"),
    (r"районный\s+исполнительный\s+комитет", "райисполком"),
    (r"городской\s+исполнительный\s+комитет", "горисполком"),
    (r"областной\s+исполнительный\s+комитет", "облисполком"),
]


def _safe(text: str, limit: int) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", text or "")
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:limit].rstrip(" .,")


def customer_dir_name(customer: str) -> str:
    """«Республиканское дочернее торговое унитарное предприятие "Медтехника" г.Гомель»
    → «РДТУП Медтехника г.Гомель». Одинаковый заказчик → одна и та же папка."""
    name = (customer or "").strip()
    if not name:
        return NO_CUSTOMER
    name = name.split(",")[0] if len(name) > 90 else name  # «…, УНП 123» и адреса — отрезаем
    for pat, short in _ABBR:
        name = re.sub(pat, short, name, flags=re.I)
    name = re.sub(r"[«»\"“”„']", "", name)
    return _safe(name, 80) or NO_CUSTOMER


def tender_dir_name(t: Tender) -> str:
    date = (t.published or t.deadline or datetime.now().isoformat())[:10]
    num = _safe(t.number or t.ext_id.split("/")[-1], 30)
    title = _safe(t.title, 70)
    return _safe(f"{date} № {num} — {title}", 140)


def _migrate_subfolders(folder: Path) -> None:
    for old, new in _OLD_NAMES.items():
        src, dst = folder / old, folder / new
        if src.exists() and not dst.exists():
            src.rename(dst)
        elif src.exists():
            for p in src.iterdir():
                if not (dst / p.name).exists():
                    shutil.move(str(p), str(dst / p.name))
            shutil.rmtree(src, ignore_errors=True)


def tender_folder(t: Tender, existing: str = "") -> Path:
    """Папка тендера внутри папки заказчика. Старые папки (без заказчика или
    созданные, пока заказчик не был известен) переносятся на новое место."""
    root = tenders_dir()
    cust = customer_dir_name(t.customer)
    if existing and Path(existing).exists():
        cur = Path(existing)
        in_new_layout = cur.parent.parent == root and cur.parent.name != NO_CUSTOMER
        if in_new_layout or (cur.parent.parent == root and cust == NO_CUSTOMER):
            _migrate_subfolders(cur)
            return cur
        target = root / cust / tender_dir_name(t)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.move(str(cur), str(target))
            old_parent = cur.parent
            if old_parent != root and old_parent.exists() and not any(old_parent.iterdir()):
                old_parent.rmdir()  # опустевшая папка «Заказчик не указан»
            _relink_documents(t, cur, target)
            _migrate_subfolders(target)
            return target
        _migrate_subfolders(cur)
        return cur
    target = root / cust / tender_dir_name(t)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _relink_documents(t: Tender, old: Path, new: Path) -> None:
    for d in t.documents:
        if d.local_path and d.local_path.startswith(str(old)):
            rel = Path(d.local_path).relative_to(old)
            parts = list(rel.parts)
            if parts and parts[0] in _OLD_NAMES:
                parts[0] = _OLD_NAMES[parts[0]]
            d.local_path = str(new.joinpath(*parts))


def docs_dir(folder: Path) -> Path:
    return folder / DOCS


def offer_dir(folder: Path) -> Path:
    return folder / OFFER


def check_dir(folder: Path) -> Path:
    return folder / CHECK


def write_info(t: Tender, folder: Path, status: str = "") -> None:
    """Сведения о закупке — чтобы по папке было понятно всё без программы."""
    lines = [
        f"Предмет закупки: {t.title}",
        f"Номер процедуры: {t.number or t.ext_id}",
        f"Вид процедуры: {t.procedure}" if t.procedure else "",
        f"Заказчик: {t.customer}" + (f" (УНП {t.customer_unp})" if t.customer_unp else ""),
        f"Приём предложений до: {t.deadline.replace('T', ' ')}" if t.deadline else "",
        f"Ориентировочная стоимость: {t.estimate:,.2f} {t.currency}".replace(",", " ") if t.estimate else "",
        f"Площадка: {t.site}",
        f"Ссылка: {t.url}" if t.url else "",
        f"Статус: {status}" if status else "",
        "",
    ]
    for k, v in t.fields.items():
        if not k.startswith("_") and v and len(v) < 400:
            lines.append(f"{k}: {v}")
    if t.positions:
        lines += ["", "Позиции:"]
        for i, p in enumerate(t.positions, 1):
            q = f" — {p.qty:g} {p.unit}".rstrip() if p.qty else ""
            lines.append(f"  {i}. {p.name}{q}")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / INFO).write_text("\n".join(x for x in lines if x is not None), "utf-8")
