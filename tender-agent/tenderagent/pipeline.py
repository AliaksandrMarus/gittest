"""Основная логика: мониторинг → разбор тендера → сверка с прайсом → пакет документов."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import textnorm
from .config import Settings
from .folders import CHECK, DOCS, OFFER, tender_folder, write_info  # noqa: F401
from .db import (DB, STATUS_ERROR, STATUS_EXPIRED, STATUS_FIT, STATUS_NOFIT,
                 STATUS_READY, STATUS_REJECTED, STATUS_SUBMITTED)
from .docs import extract, generate
from .docs.fill import fill_form, offer_lines, totals
from .matching import MatchSummary, PriceIndex, match_positions, summarize, unit_price
from .models import Match, Tender
from .sites import GenericSite, Http, make_sites, tender_matches


@dataclass
class Analysis:
    matches: list[Match]
    summary: MatchSummary
    infos: list = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    conditions: dict[str, str] = field(default_factory=dict)
    fits: bool = False
    reasons: list[str] = field(default_factory=list)


def is_expired(t: Tender) -> bool:
    if not t.deadline:
        return False
    try:
        return datetime.fromisoformat(t.deadline) < datetime.now()
    except ValueError:
        return False


class Engine:
    def __init__(self, settings: Settings, db: DB, log=print):
        self.settings = settings
        self.db = db
        self.log = log
        self.http = Http(log)
        self.sites: dict[str, GenericSite] = make_sites(self.http, log)
        self.index = PriceIndex([])
        self.stop_requested = False

    def set_price_items(self, items) -> None:
        self.index = PriceIndex(items)

    # --- мониторинг -----------------------------------------------------------
    def relocate_folders(self) -> int:
        """Разложить папки всех тендеров по заказчикам и укоротить длинные имена
        (нужно один раз после обновления программы). Возвращает число перенесённых."""
        moved = 0
        for r in self.db.all():
            cur = r.get("folder") or ""
            if not cur or not Path(cur).exists():
                continue
            t = r["tender"]
            try:
                new = tender_folder(t, cur)
            except OSError as e:
                self.log(f"Папка не перенесена (закройте открытые из неё файлы): {cur} — {e}")
                continue
            if str(new) != cur:
                self.db.save_tender(t, folder=str(new))
                moved += 1
        if moved:
            self.log(f"Папки тендеров разложены по заказчикам и укорочены: {moved}")
        return moved

    def mark_expired(self) -> int:
        """Тендеры, у которых прошёл срок подачи, получают статус «Срок истёк»
        (кроме поданных — по ним ждём итогов)."""
        n = 0
        for r in self.db.all():
            if r["status"] in (STATUS_EXPIRED, STATUS_SUBMITTED):
                continue
            if is_expired(r["tender"]):
                self.db.set_status(r["uid"], STATUS_EXPIRED)
                n += 1
        return n

    def cleanup_candidates(self, include_rejected: bool = True, include_nofit: bool = False) -> list[dict]:
        self.mark_expired()
        statuses = {STATUS_EXPIRED}
        if include_rejected:
            statuses.add(STATUS_REJECTED)
        if include_nofit:
            statuses.add(STATUS_NOFIT)
        return [r for r in self.db.all() if r["status"] in statuses]

    def cleanup(self, rows: list[dict], delete_folders: bool) -> tuple[int, int]:
        """Убрать тендеры из программы (и, по желанию, их папки). Возвращает (тендеров, папок)."""
        import shutil

        from .config import tenders_dir

        root = tenders_dir()
        removed = folders = 0
        for r in rows:
            if r["status"] == STATUS_SUBMITTED:
                continue  # поданные не трогаем
            folder = Path(r["folder"]) if r.get("folder") else None
            if delete_folders and folder and folder.exists() and root in folder.parents:
                try:
                    shutil.rmtree(folder)
                    folders += 1
                    parent = folder.parent
                    if parent != root and parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()  # у заказчика больше нет тендеров
                except OSError as e:
                    self.log(f"Папка не удалена (закройте открытые из неё файлы): {folder} — {e}")
            self.db.forget(r["uid"])
            removed += 1
        self.log(f"Очищено: тендеров {removed}" + (f", папок {folders}" if delete_folders else ""))
        return removed, folders

    def recheck_all(self, progress=None) -> int:
        """Заново сверить с прайсом все найденные и ещё не поданные тендеры
        (после загрузки нового прайса или изменения настроек)."""
        from .db import STATUS_NEW
        self.stop_requested = False
        rows = [r for r in self.db.all()
                if r["status"] in (STATUS_NEW, STATUS_FIT, STATUS_NOFIT, STATUS_ERROR)]
        good = 0
        for i, r in enumerate(rows, 1):
            if self.stop_requested:
                break
            t = r["tender"]
            if progress:
                progress(f"Сверяю {i}/{len(rows)}: {t.title[:60]}")
            if is_expired(t):
                self.db.save_tender(t, STATUS_EXPIRED)
                continue
            try:
                if t.site in self.sites and not any(d.local_path and Path(d.local_path).exists()
                                                    for d in t.documents):
                    try:
                        self.sites[t.site].fetch_details(t)  # свежие ссылки и cookies для скачивания
                    except Exception as e:  # noqa: BLE001
                        self.log(f"{t.number or t.ext_id}: карточка не обновлена ({e})")
                a = self.analyze(t, download=self.settings.monitor.auto_download_docs)
            except Exception as e:  # noqa: BLE001
                self.log(f"Ошибка сверки {t.number or t.ext_id}: {e}")
                continue
            status = STATUS_FIT if a.fits else STATUS_NOFIT
            good += a.fits
            self.db.save_tender(t, status, match_percent=a.summary.percent, our_sum=a.summary.our_sum,
                                verdict="; ".join(a.reasons))
        self.log(f"Пересверка завершена: {len(rows)} тендеров, подходящих {good}.")
        return good

    def run_monitor(self, progress=None) -> list[str]:
        """Один проход по всем площадкам. Возвращает uid новых подходящих тендеров."""
        m = self.settings.monitor
        self.stop_requested = False
        self.http.cache.clear()
        queries = [(kw, "") for kw in m.keywords if kw.strip()] + [("", c) for c in m.okrb_codes if c.strip()]
        if not queries:
            self.log("Добавьте ключевые слова или коды ОКРБ.")
            return []
        candidates: dict[str, Tender] = {}
        for key, site in self.sites.items():
            if not m.sites.get(key, True):
                continue
            for kw, code in queries:
                if self.stop_requested:
                    return []
                if progress:
                    progress(f"{site.cfg.title}: ищу «{kw or code}»…")
                try:
                    found = site.search(query=kw, okrb=code, pages=m.pages_per_query)
                except Exception as e:
                    self.log(f"{site.cfg.title}: ошибка поиска «{kw or code}»: {e}")
                    continue
                n = 0
                for t in found:
                    trusted = t.fields.get("_trusted")
                    hit = tender_matches(t, m.keywords, m.okrb_codes, m.stop_words)
                    if not hit and not trusted:
                        continue
                    if trusted and any(sw.strip() and textnorm.contains_keyword(t.title, sw) for sw in m.stop_words):
                        continue
                    t.matched_query = hit or trusted
                    if t.uid not in candidates and not self.db.has(t.uid):
                        candidates[t.uid] = t
                        n += 1
                self.log(f"{site.cfg.title}: «{kw or code}» — найдено {len(found)}, новых {n}")

        good: list[str] = []
        for i, t in enumerate(candidates.values(), 1):
            if self.stop_requested:
                break
            if progress:
                progress(f"Разбираю {i}/{len(candidates)}: {t.title[:60]}")
            try:
                self.sites[t.site].fetch_details(t)
            except Exception as e:
                if not t.title:
                    self.log(f"Не открылась карточка {t.url}: {e}")
                    self.db.save_tender(t, STATUS_ERROR)
                    continue
                # Данных из списка (название, заказчик, срок, стоимость) достаточно,
                # чтобы показать тендер; документы пользователь скачает с сайта сам.
                self.log(f"{t.number or t.ext_id}: карточка не открылась ({e}), беру данные из реестра")
                if not t.positions:
                    from .models import Position
                    t.positions = [Position(name=t.title, source="реестр")]
            if is_expired(t):
                self.db.forget(t.uid)  # срок уже истёк — в список не добавляем и больше не проверяем
                continue
            try:
                a = self.analyze(t, download=m.auto_download_docs)
            except Exception as e:
                self.log(f"Ошибка анализа {t.number or t.ext_id}: {e}")
                self.db.save_tender(t, STATUS_ERROR)
                continue
            status = STATUS_FIT if a.fits else STATUS_NOFIT
            self.db.save_tender(t, status, match_percent=a.summary.percent, our_sum=a.summary.our_sum,
                                verdict="; ".join(a.reasons))
            if a.fits:
                good.append(t.uid)
                if m.auto_prepare:
                    try:
                        self.prepare(t, a)
                    except Exception as e:
                        self.log(f"Ошибка подготовки пакета {t.number}: {e}")
        self.log(f"Проход завершён: новых {len(candidates)}, подходящих {len(good)}.")
        return good

    # --- анализ одного тендера -----------------------------------------------
    def download_docs(self, t: Tender, folder: Path) -> Path:
        dest = folder / DOCS
        dest.mkdir(parents=True, exist_ok=True)
        from .sites.base import _file_info_stub, _looks_like_html

        for d in t.documents:
            if d.local_path and Path(d.local_path).exists():
                head = Path(d.local_path).read_bytes()[:65537]
                if not (_looks_like_html(head[:8000]) or _file_info_stub(head) is not None):
                    continue
                Path(d.local_path).unlink()  # раньше вместо файла сохранилась справка/страница — качаем заново
                self.log(f"{d.name}: прежняя загрузка была не файлом — скачиваю заново")
            try:
                p = self.http.download(d.url, dest, d.name, referer=t.url)
                d.local_path = str(p)
                self.log(f"Скачан {p.name}")
            except Exception as e:
                self.log(f"Не скачан {d.name}: {e}")
        return dest

    def analyze(self, t: Tender, download: bool = True, overrides: dict | None = None) -> Analysis:
        row = self.db.get(t.uid)
        folder = tender_folder(t, row["folder"] if row else "")
        if row is None or not row["folder"]:
            self.db.save_tender(t, folder=str(folder))
        infos = []
        if download and t.documents:
            self.download_docs(t, folder)
        doc_dir = folder / DOCS
        if doc_dir.exists():
            infos = extract.analyze_folder(doc_dir, self.log)
        positions = extract.best_positions(infos, t.positions)
        if positions and positions is not t.positions:
            t.positions = positions
        matches = self.match(t, overrides or (row["overrides"] if row else {}))
        a = self.evaluate(t, matches)
        a.infos = infos
        a.required = extract.required_documents(infos)
        a.conditions = extract.key_conditions(infos)
        self.db.save_tender(t, folder=str(folder))
        write_info(t, folder, "подходит" if a.fits else "не подходит: " + "; ".join(a.reasons))
        return a

    def terms_for(self, overrides: dict | None = None):
        """Условия для конкретного тендера: наценка может быть своя (поле в карточке)."""
        from dataclasses import replace

        mk = (overrides or {}).get("_markup")
        return replace(self.settings.terms, markup_percent=float(mk)) if mk is not None else self.settings.terms

    def match(self, t: Tender, overrides: dict | None = None) -> list[Match]:
        s = self.settings
        terms = self.terms_for(overrides)
        matches = match_positions(t.positions, self.index, terms, s.monitor.min_item_score, self.db.mappings())
        for k, ov in (overrides or {}).items():
            if not str(k).isdigit():
                continue  # служебные ключи вроде «_markup»
            i = int(k)
            if i >= len(matches):
                continue
            m = matches[i]
            if "item" in ov:
                item = self.index.find(ov["item"]) if ov["item"] else None
                m.item, m.manual = item, True
                m.score = 100 if item else 0
                m.price = unit_price(item, terms) if item else None
            if "include" in ov:
                m.include = bool(ov["include"])
            if ov.get("price") is not None and m.item:
                m.price = float(ov["price"])
            if ov.get("qty") is not None:
                m.position.qty = float(ov["qty"])
        return matches

    def evaluate(self, t: Tender, matches: list[Match]) -> Analysis:
        s = self.settings
        vat_mult = 1 + s.terms.vat_rate / 100 if s.requisites.vat_payer else 1.0
        summ = summarize(matches, t.estimate, vat_mult)
        reasons, fits = [], True
        if not len(self.index):
            fits = False
            reasons.append("прайс не загружен")
        if summ.total == 0:
            fits = False
            reasons.append("не удалось определить позиции")
        elif summ.percent < s.monitor.min_match_percent:
            fits = False
            reasons.append(f"в прайсе {summ.found} из {summ.total} позиций ({summ.percent}%)")
        else:
            reasons.append(f"в прайсе {summ.found} из {summ.total} позиций ({summ.percent}%)")
        if summ.estimate_ok is False and s.monitor.require_price_below_estimate:
            fits = False
            reasons.append(f"наша цена {summ.our_sum * vat_mult:,.2f} выше ориентировочной {summ.limit_sum:,.2f}"
                           .replace(",", " "))
        elif summ.estimate_ok:
            reasons.append("цена ниже ориентировочной")
        if is_expired(t):
            fits = False
            reasons.append("срок подачи истёк")
        return Analysis(matches, summ, fits=fits, reasons=reasons)

    # --- пакет документов ------------------------------------------------------
    def prepare(self, t: Tender, a: Analysis) -> Path:
        s = self.settings
        req, terms = s.requisites, s.terms
        row = self.db.get(t.uid)
        folder = tender_folder(t, row["folder"] if row else "")
        doc_dir = folder / DOCS
        if t.documents and not any(d.local_path for d in t.documents):
            self.download_docs(t, folder)
        if a.infos and not all(i.path.exists() for i in a.infos):
            a.infos = []  # папку перенесли (стал известен заказчик) — перечитаем
        if not a.infos and doc_dir.exists():
            a.infos = extract.analyze_folder(doc_dir, self.log)
            a.required = extract.required_documents(a.infos)
            a.conditions = extract.key_conditions(a.infos)

        out = folder / OFFER
        check = folder / CHECK
        if out.exists():
            shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True, exist_ok=True)
        check.mkdir(parents=True, exist_ok=True)

        lines = offer_lines(a.matches, terms, req)
        notes: list[str] = []
        filled: list[str] = []
        if not lines:
            notes.append("Ни одна позиция не включена в предложение — проверьте сопоставление с прайсом.")

        fillable = [i for i in a.infos if i.path.suffix.lower() in (".docx", ".xlsx", ".xlsm")]
        offer_forms = sorted([i for i in fillable if i.offer_form_score >= 4], key=lambda i: -i.offer_form_score)
        used_form = False
        for info in offer_forms[:3]:
            dst = out / f"{info.path.stem[:50].rstrip(' ._')} (заполнено){info.path.suffix}"
            try:
                st = fill_form(info.path, dst, lines, req, terms, self.log)
            except Exception as e:
                self.log(f"Форма {info.path.name} не заполнена: {e}")
                continue
            if st["offer_table"] and st["rows"]:
                used_form = True
                filled.append(f"{dst.name} — форма заказчика, заполнено строк: {st['rows']}, полей: {st['fields']}")
            elif st["fields"]:
                filled.append(f"{dst.name} — подставлены реквизиты ({st['fields']} полей)")
            else:
                dst.unlink(missing_ok=True)
        # Остальные формы/приложения заказчика: подставляем реквизиты.
        done = {i.path for i in offer_forms[:3]}
        for info in fillable:
            if info.path in done or not re.search(r"(форма|приложени|анкет|сведени|заявлени|декларац)", info.path.stem, re.I):
                continue
            dst = out / f"{info.path.stem[:50].rstrip(' ._')} (заполнено){info.path.suffix}"
            try:
                st = fill_form(info.path, dst, lines, req, terms, self.log)
                if st["fields"] or st["rows"]:
                    filled.append(f"{dst.name} — подставлены реквизиты ({st['fields']} полей)")
                else:
                    dst.unlink(missing_ok=True)
            except Exception as e:
                self.log(f"Форма {info.path.name} не заполнена: {e}")

        own_offer = (out if not used_form else check) / "Ценовое предложение (наша форма).docx"
        generate.offer_docx(own_offer, t, lines, req, terms)
        if not used_form:
            filled.insert(0, f"{own_offer.name} — форма заказчика не найдена, составлено по стандартному образцу")
            notes.append("В документации не найдена заполняемая форма ценового предложения (.docx/.xlsx). "
                         "Если форма есть в .pdf — перенесите цены из нашей формы вручную.")
        generate.offer_xlsx(check / "Ценовое предложение (таблица).xlsx", t, lines, req)
        generate.participant_info(out / "Сведения об участнике.docx", req, terms)
        filled.append("Сведения об участнике.docx")

        attachments = [p.name for p in sorted(out.iterdir())] + ["Сопроводительное письмо.docx"]
        attachments += [r for r in a.required if not any(w in r.lower() for w in ("опись", "сопровод", "анкет"))]
        generate.inventory(out / "Опись документов.docx", t, req, attachments + ["Опись документов.docx"])
        filled.append("Опись документов.docx")
        tt = totals(lines)
        generate.cover_letter(out / "Сопроводительное письмо.docx", t, req,
                              [x for x in attachments if x != "Сопроводительное письмо.docx"],
                              tt["total"] if req.vat_payer else tt["sum"])
        filled.append("Сопроводительное письмо.docx")

        if not req.full_name or not req.unp:
            notes.append("Не заполнены реквизиты компании (вкладка «Реквизиты») — в документах будут пропуски.")
        for i in a.infos:
            if i.path.suffix.lower() == ".pdf" and i.offer_form_score >= 3:
                notes.append(f"Возможно, форма предложения в PDF: {i.path.name} — заполните по нашей таблице.")
        if any(p.suffix.lower() == ".doc" for p in doc_dir.rglob("*")) and not any(
                p.suffix.lower() == ".docx" for p in doc_dir.rglob("*")):
            notes.append("Документация в старом формате .doc — установите MS Word, чтобы программа могла "
                         "заполнять такие формы автоматически.")

        vat_mult = 1 + terms.vat_rate / 100 if req.vat_payer else 1.0
        generate.comparison_xlsx(check / "Сравнение с прайсом.xlsx", a.matches, t.estimate, vat_mult)
        generate.checklist(check / "ЧЕК-ЛИСТ перед подачей.docx", t, a.matches, a.required,
                           a.conditions, filled, notes)
        write_info(t, folder, STATUS_READY)
        self.db.save_tender(t, STATUS_READY, folder=str(folder), match_percent=a.summary.percent,
                            our_sum=a.summary.our_sum)
        self.log(f"Пакет готов: {folder}")
        return folder
