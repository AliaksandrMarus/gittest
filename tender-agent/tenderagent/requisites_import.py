"""Чтение реквизитов из карточки предприятия (.docx/.pdf/.xlsx/.txt).

Карточки пишут как угодно: строками «УНП 123456789», таблицей «УНП | 123456789»,
одной строкой «р/сч № BY.. ОАО «Банк», г.Минск, БИК XXXX». Поэтому склеиваем
всё в текст по строкам и ищем каждое значение своим правилом.
"""
from __future__ import annotations

import re
from pathlib import Path

_FORMS = (
    ("общество с ограниченной ответственностью", "ООО"),
    ("общество с дополнительной ответственностью", "ОДО"),
    ("закрытое акционерное общество", "ЗАО"),
    ("открытое акционерное общество", "ОАО"),
    ("акционерное общество", "АО"),
    ("частное производственное унитарное предприятие", "ЧПУП"),
    ("частное торговое унитарное предприятие", "ЧТУП"),
    ("частное унитарное предприятие", "ЧУП"),
    ("частное предприятие", "ЧП"),
    ("унитарное предприятие", "УП"),
    ("индивидуальный предприниматель", "ИП"),
)
_SHORT_FORM = r"(ООО|ОДО|ЗАО|ОАО|АО|ЧПУП|ЧТУП|ЧУП|УП|ЧП|ИП)"
_IBAN = re.compile(r"\bBY\s?\d{2}\s?[A-Z]{4}(?:\s?[0-9A-Z]{4}){5}\b")
_POSITIONS = r"(Генеральный директор|Директор|Управляющий|Руководитель|Председатель правления|Индивидуальный предприниматель)"


def read_text(path: str | Path) -> str:
    from .docs.extract import read_any

    path = Path(path)
    text, tables = read_any(path)
    rows = [" ".join(c for c in r if c) for t in tables for r in t]
    return "\n".join([text] + rows)


def _initials(fio: str) -> str:
    parts = fio.split()
    if len(parts) >= 3:
        return f"{parts[1][0]}.{parts[2][0]}. {parts[0]}"
    if len(parts) == 2:
        return f"{parts[1][0]}. {parts[0]}"
    return fio


def _value_after(label: str, text: str) -> str:
    m = re.search(rf"{label}\s*[:\-–]?\s*(.+)", text, re.I)
    return m.group(1).strip(" .;,") if m else ""


def parse_requisites(text: str) -> dict[str, str]:
    """Возвращает только найденные поля (ключи как у config.Requisites)."""
    out: dict[str, str] = {}
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    flat = "\n".join(lines)
    low = flat.lower()

    # Наименование
    for full, short in _FORMS:
        i = low.find(full)
        if i >= 0:
            line = next(ln for ln in lines if full in ln.lower())
            name = line[line.lower().find(full):]
            name = re.split(r"\s*(?:,\s*)?(?:УНП|ИНН|адрес)\b", name, flags=re.I)[0].strip(" ,.;")
            out["full_name"] = name
            q = re.search(r"[«\"“](.+?)[»\"”]", name)
            if q:
                out["short_name"] = f"{short} «{q.group(1)}»"
            break
    if "full_name" not in out:
        m = re.search(rf"\b{_SHORT_FORM}\s*[«\"“][^»\"”]+[»\"”]", flat)
        if m:
            out["short_name"] = m.group(0)

    m = re.search(r"(?:УНП|учетный номер плательщика)\D{0,5}(\d{9})\b", flat, re.I)
    if m:
        out["unp"] = m.group(1)
    m = re.search(r"ОКПО\D{0,5}(\d{8,12})", flat, re.I)
    if m:
        out["okpo"] = m.group(1)

    # Адреса: подписанные или строка, начинающаяся с почтового индекса
    legal = _value_after(r"(?:юридический адрес|место нахождения|адрес)", flat) if re.search(
        r"юридический адрес|место нахождения", flat, re.I) else ""
    if not legal:
        legal = next((ln for ln in lines if re.match(r"^\d{6}\s*,", ln)), "")
    if legal:
        out["legal_address"] = legal.split("\n")[0]
    postal = _value_after(r"почтовый адрес", flat) if re.search(r"почтовый адрес", flat, re.I) else ""
    if postal:
        out["postal_address"] = postal

    # Банк
    m = _IBAN.search(flat.upper())
    if m:
        out["bank_account"] = m.group(0).replace(" ", "")
        line = next((ln for ln in lines if out["bank_account"] in ln.replace(" ", "").upper()), "")
        tail = line[line.upper().replace(" ", "").find(out["bank_account"]):] if line else ""
        # всё, что после номера счёта и до «БИК/BIC», — банк и его адрес
        after = re.split(re.escape(m.group(0)), line, flags=re.I)
        rest = after[-1] if len(after) > 1 else tail
        rest = re.split(r"\b(?:БИК|BIC|SWIFT)\b", rest, flags=re.I)[0]
        rest = re.sub(r"^\s*(в|в банке)\s+", "", rest.strip(" ,.;:"), flags=re.I)
        if rest:
            bank = re.match(r"(.+?[»\"”])\s*,?\s*(.*)$", rest)
            if bank:
                out["bank_name"] = bank.group(1).strip(" ,")
                if bank.group(2):
                    out["bank_address"] = bank.group(2).strip(" ,.")
            else:
                out["bank_name"] = rest
    m = re.search(r"\b(?:БИК|BIC|SWIFT)\s*[:\-]?\s*([A-Z0-9]{8,11})\b", flat, re.I)
    if m:
        out["bank_bic"] = m.group(1).upper()
    if "bank_name" not in out:
        v = _value_after(r"(?:наименование банка|банк)", flat) if re.search(r"банк\s*:", flat, re.I) else ""
        if v:
            out["bank_name"] = v

    # Руководитель: «Директор Иванов Иван Иванович»
    m = re.search(rf"{_POSITIONS}\s*[:\-–]?\s*([А-ЯЁ][а-яё\-]+\s+[А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)?)", flat)
    if m:
        out["director_position"] = m.group(1)
        out["director_name"] = m.group(2)
        out["director_short"] = _initials(m.group(2))
    m = re.search(r"на основании\s+([А-ЯЁа-яё][^,\n.]+)", flat, re.I)
    if m:
        out["acts_on"] = m.group(1).strip()

    m = re.search(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+", flat)
    if m:
        out["email"] = m.group(0).rstrip(".")
    # Телефон не должен быть куском номера счёта или GLN: вокруг — не цифры и не буквы.
    m = re.search(r"(?<![\w+])(\+?375(?:[\s\-()]*\d){9}|8[\s\-]?\(?0(?:[\s\-()]*\d){8,9})(?![\w])", flat)
    if m:
        out["phone"] = m.group(1).strip()
    m = re.search(r"\b((?:https?://)?(?:www\.)?[a-z0-9\-]+\.(?:by|ru|com|net|org)(?:/\S*)?)\b", flat, re.I)
    if m and "@" not in flat[max(0, m.start() - 1):m.start()]:
        out["website"] = m.group(1)
    m = re.search(r"(свидетельств\w*\s+о\s+(?:государственной\s+)?регистрации[^\n]*)", flat, re.I)
    if m:
        out["registration_info"] = m.group(1).strip()
    return out
