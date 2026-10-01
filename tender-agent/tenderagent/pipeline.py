"""Основная логика: мониторинг → разбор тендера → сверка с прайсом → пакет документов."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import textnorm
from .config import Settings, tenders_dir
from .db import (DB, STATUS_ERROR, STATUS_EXPIRED, STATUS_FIT, STATUS_NOFIT,
                 STATUS_READY)
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


def tender_folder(t: Tender, existing: str = "") -> Path:
    if existing and Path(existing).exists():
        return Path(existing)
    short = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", t.title)[:60].strip(" .")
    num = re.sub(r"[^\w\-]+", "_", t.number or t.ext_id)[:30]
    f = tenders_dir() / f"{datetime.now():%Y-%m-%d} {t.site} {num} {short}".strip()
    f.mkdir(parents=True, exist_ok=True)
    return f


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
                self.log(f"Не открылась карточка {t.url}: {e}")
                self.db.save_tender(t, STATUS_ERROR)
                continue
            if is_expired(t):
                self.db.save_tender(t, STATUS_EXPIRED)
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
        dest = folder / "Документация"
        dest.mkdir(parents=True, exist_ok=True)
        for d in t.documents:
            if d.local_path and Path(d.local_path).exists():
                continue
            try:
                p = self.http.download(d.url, dest, d.name)
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
        doc_dir = folder / "Документация"
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
        return a

    def match(self, t: Tender, overrides: dict | None = None) -> list[Match]:
        s = self.settings
        matches = match_positions(t.positions, self.index, s.terms, s.monitor.min_item_score, self.db.mappings())
        for k, ov in (overrides or {}).items():
            i = int(k)
            if i >= len(matches):
                continue
            m = matches[i]
            if "item" in ov:
                item = self.index.find(ov["item"]) if ov["item"] else None
                m.item, m.manual = item, True
                m.score = 100 if item else 0
                m.price = unit_price(item, s.terms) if item else None
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
        doc_dir = folder / "Документация"
        if t.documents and not any(d.local_path for d in t.documents):
            self.download_docs(t, folder)
        if not a.infos and doc_dir.exists():
            a.infos = extract.analyze_folder(doc_dir, self.log)
            a.required = extract.required_documents(a.infos)
            a.conditions = extract.key_conditions(a.infos)

        out = folder / "Для подачи"
        check = folder / "Для проверки"
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
            dst = out / f"{info.path.stem} (заполнено){info.path.suffix}"
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
            dst = out / f"{info.path.stem} (заполнено){info.path.suffix}"
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

        generate.comparison_xlsx(check / "Сравнение с прайсом.xlsx", a.matches)
        generate.checklist(check / "ЧЕК-ЛИСТ перед подачей.docx", t, a.matches, a.required,
                           a.conditions, filled, notes)
        self.db.save_tender(t, STATUS_READY, folder=str(folder), match_percent=a.summary.percent,
                            our_sum=a.summary.our_sum)
        self.log(f"Пакет готов: {folder}")
        return folder
