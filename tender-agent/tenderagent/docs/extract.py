"""Чтение тендерной документации: распаковка архивов, текст и таблицы
из .docx/.xlsx/.xls/.pdf, поиск спецификации, формы предложения и
перечня требуемых документов.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ..models import Position
from ..sites.base import positions_from_rows

TEXT_EXT = {".docx", ".xlsx", ".xlsm", ".xls", ".pdf", ".txt", ".rtf"}


@dataclass
class DocInfo:
    path: Path
    text: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    offer_form_score: int = 0


# --- архивы и старые форматы -------------------------------------------------

def _fix_zip_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if info.flag_bits & 0x800:
        return name
    try:
        return name.encode("cp437").decode("cp866")
    except UnicodeError:
        return name


def unpack_archives(folder: Path, log=print) -> None:
    """Распаковывает .zip (и .rar/.7z, если установлен 7-Zip) рядом с архивом."""
    for _ in range(3):  # архивы внутри архивов
        changed = False
        for arc in list(folder.rglob("*")):
            ext = arc.suffix.lower()
            target = arc.with_name(arc.stem + "_файлы")
            if ext not in (".zip", ".rar", ".7z") or target.exists():
                continue
            try:
                if ext == ".zip":
                    with zipfile.ZipFile(arc) as z:
                        for info in z.infolist():
                            if info.is_dir():
                                continue
                            name = _fix_zip_name(info)
                            dest = target / Path(*[p for p in Path(name).parts if p not in ("..", "/")])
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(info) as src, open(dest, "wb") as out:
                                shutil.copyfileobj(src, out)
                else:
                    seven = _find_7zip()
                    if not seven:
                        log(f"Не распакован {arc.name}: установите 7-Zip (7-zip.org) для .rar/.7z")
                        continue
                    target.mkdir(parents=True, exist_ok=True)
                    subprocess.run([seven, "x", "-y", f"-o{target}", str(arc)], capture_output=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                changed = True
            except Exception as e:
                log(f"Ошибка распаковки {arc.name}: {e}")
        if not changed:
            break


def _find_7zip() -> str:
    for p in (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if Path(p).exists():
            return p
    return shutil.which("7z") or ""


def convert_legacy(folder: Path, log=print) -> None:
    """.doc/.rtf/.xls → .docx/.xlsx через установленный MS Word/Excel (если есть)."""
    if sys.platform != "win32":
        return
    olds = [p for p in folder.rglob("*") if p.suffix.lower() in (".doc", ".rtf", ".odt")
            and not p.with_suffix(".docx").exists()]
    if not olds:
        return
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
    except Exception:
        log("Файлы .doc не преобразованы: не найден Microsoft Word. Их можно открыть и заполнить вручную.")
        return
    try:
        for p in olds:
            try:
                doc = word.Documents.Open(str(p.resolve()), ReadOnly=True, AddToRecentFiles=False)
                doc.SaveAs2(str(p.with_suffix(".docx").resolve()), FileFormat=16)
                doc.Close(False)
            except Exception as e:
                log(f"Не удалось преобразовать {p.name}: {e}")
    finally:
        word.Quit()


# --- чтение ------------------------------------------------------------------

def read_docx(path: Path) -> tuple[str, list[list[list[str]]]]:
    import docx

    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs]
    tables = []
    for t in d.tables:
        rows = []
        for r in t.rows:
            try:
                rows.append([c.text.strip() for c in r.cells])
            except Exception:
                continue
        tables.append(rows)
        parts.extend(" ".join(r) for r in rows)
    return "\n".join(parts), tables


def read_xlsx(path: Path) -> tuple[str, list[list[list[str]]]]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    tables, parts = [], []
    for ws in wb.worksheets:
        rows = [["" if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(c.strip() for c in r)]
        tables.append(rows)
        parts.extend(" ".join(r) for r in rows)
    wb.close()
    return "\n".join(parts), tables


def read_xls(path: Path) -> tuple[str, list[list[list[str]]]]:
    import xlrd

    book = xlrd.open_workbook(str(path))
    tables, parts = [], []
    for sh in book.sheets():
        rows = [[str(v) for v in sh.row_values(i)] for i in range(sh.nrows)]
        tables.append(rows)
        parts.extend(" ".join(r) for r in rows)
    return "\n".join(parts), tables


def read_pdf(path: Path) -> tuple[str, list[list[list[str]]]]:
    import pdfplumber

    parts, tables = [], []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages[:60]:
            parts.append(page.extract_text() or "")
            for t in page.extract_tables() or []:
                tables.append([[c or "" for c in r] for r in t])
    return "\n".join(parts), tables


def read_any(path: Path) -> tuple[str, list[list[list[str]]]]:
    ext = path.suffix.lower()
    if ext == ".docx":
        return read_docx(path)
    if ext in (".xlsx", ".xlsm"):
        return read_xlsx(path)
    if ext == ".xls":
        return read_xls(path)
    if ext == ".pdf":
        return read_pdf(path)
    if ext in (".txt", ".rtf"):
        raw = path.read_bytes()
        for enc in ("utf-8", "cp1251"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if ext == ".rtf":
            text = re.sub(r"\\[a-z]+-?\d* ?|[{}]", " ", text)
        return text, []
    return "", []


_OFFER_NAME = re.compile(r"(предложени|форма|ценов|прайс|коммерческ|спецификац|приложени)", re.I)
_OFFER_TEXT = re.compile(r"(ценовое предложение|предложение участника|коммерческое предложение|"
                         r"форма предложения|предложение на участие|конкурсное предложение)", re.I)


def analyze_folder(folder: Path, log=print) -> list[DocInfo]:
    unpack_archives(folder, log)
    convert_legacy(folder, log)
    infos = []
    for p in sorted(folder.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXT or p.name.startswith("~$"):
            continue
        if p.suffix.lower() == ".doc":
            continue
        try:
            text, tables = read_any(p)
        except Exception as e:
            log(f"Не прочитан {p.name}: {e}")
            continue
        info = DocInfo(p, text, tables)
        for tb in tables:
            pos = positions_from_rows(tb, source=p.name)
            if len(pos) > len(info.positions):
                info.positions = pos
        score = 0
        if _OFFER_NAME.search(p.stem):
            score += 2
        if _OFFER_TEXT.search(text[:4000]):
            score += 3
        if re.search(r"цена", " ".join(" ".join(r) for tb in tables for r in tb[:3]), re.I):
            score += 2
        if p.suffix.lower() in (".docx", ".xlsx", ".xlsm"):
            score += 1  # такие умеем заполнять
        if p.suffix.lower() == ".pdf":
            score -= 3
        info.offer_form_score = score
        infos.append(info)
    return infos


def best_positions(infos: list[DocInfo], site_positions: list[Position]) -> list[Position]:
    """Самая подробная спецификация: из документов, если там больше строк, чем на сайте."""
    best = list(site_positions)
    for info in infos:
        if len(info.positions) > len(best) or (
            len(best) <= 1 and info.positions and not any(p.qty for p in best)
        ):
            best = info.positions
    return best


REQUIRED_DOCS = [
    (r"свидетельств\w* о (государственной )?регистрации", "Копия свидетельства о государственной регистрации"),
    (r"устав", "Копия устава (учредительных документов)"),
    (r"выписк\w* из (торгового|единого государственного) реестр", "Выписка из торгового реестра / ЕГР"),
    (r"(сертификат\w* соответствия|декларац\w* о соответствии)", "Сертификаты соответствия / декларации о соответствии"),
    (r"(сертификат\w* продукции собственного производства|ст-1|сертификат\w* происхождения)",
     "Сертификат продукции собственного производства / СТ-1"),
    (r"дилерск\w*|официальн\w* (представител|дистрибьютор)", "Дилерский договор / письмо производителя"),
    (r"(доверенност)", "Доверенность на подписание предложения"),
    (r"(гарантийн\w* письм|гаранти\w* исполнени)", "Гарантийное письмо / обеспечение исполнения"),
    (r"(справк\w* об отсутствии задолженност|налогов\w* задолженност)", "Справка об отсутствии задолженности"),
    (r"(бухгалтерск\w* баланс|финансов\w* отчетност)", "Бухгалтерский баланс / финансовая отчётность"),
    (r"(отзыв\w*|рекомендательн\w* письм)", "Отзывы / рекомендательные письма"),
    (r"(анкет\w* участник|сведения об участник)", "Анкета (сведения) участника"),
    (r"(протокол\w* испытан|паспорт\w* (изделия|качества)|удостоверени\w* качества)",
     "Паспорт качества / протоколы испытаний"),
    (r"(образ\w* продукции|образц\w*)", "Образцы продукции (если требуются)"),
    (r"(лицензи\w*)", "Лицензия (если вид деятельности лицензируется)"),
    (r"(сопроводительн\w* письм)", "Сопроводительное письмо"),
    (r"(перечень|опись) (представленных|прилагаемых)? ?документ", "Опись документов"),
]


def required_documents(infos: list[DocInfo]) -> list[str]:
    text = " ".join(i.text.lower() for i in infos).replace("ё", "е")
    found = []
    for pat, title in REQUIRED_DOCS:
        if re.search(pat, text):
            found.append(title)
    return found


def key_conditions(infos: list[DocInfo]) -> dict[str, str]:
    """Вытаскивает из документации фразы о сроках, оплате, валюте и т.п."""
    text = "\n".join(i.text for i in infos)
    sentences = re.split(r"(?<=[.;])\s+|\n", text)
    wanted = {
        "Срок поставки": r"срок\w* поставки",
        "Условия оплаты": r"(условия оплаты|порядок оплаты|оплат\w* (производится|осуществляется))",
        "Срок действия предложения": r"срок\w* действия (предложения|конкурсного)",
        "Валюта": r"валют\w* (предложения|цены)",
        "Место поставки": r"(место|адрес) поставки",
        "Обеспечение": r"обеспечени\w* (предложения|исполнения)",
        "Преференциальная поправка": r"преференциальн\w* поправк",
    }
    out = {}
    for title, pat in wanted.items():
        for s in sentences:
            if re.search(pat, s, re.I) and 15 < len(s) < 500:
                out[title] = re.sub(r"\s+", " ", s).strip()
                break
    return out
