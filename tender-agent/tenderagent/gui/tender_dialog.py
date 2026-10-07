"""Карточка тендера: позиции заказчика против нашего прайса и подготовка пакета."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDoubleSpinBox, QDialogButtonBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from .. import textnorm
from ..db import STATUS_FIT, STATUS_NOFIT, STATUS_REJECTED, STATUS_SUBMITTED
from ..docs.fill import money
from ..matching import customer_unit_price, markup_for_target
from ..folders import DOCS
from ..pipeline import Analysis, Engine
from .common import open_path, open_url, run_task

COLS = ["№", "Позиция заказчика", "Кол-во", "Ед.", "Товар из нашего прайса", "Похожесть",
        "Наша цена\nза ед. без НДС", "Наша цена\nза ед. с НДС", "Цена заказчика\nза ед. (с НДС)",
        "Расхождение", "Сумма\nбез НДС", "В предложение"]
C_QTY, C_ITEM, C_PRICE, C_OURVAT, C_CUST, C_DIFF, C_SUM, C_INC = 2, 4, 6, 7, 8, 9, 10, 11


class ItemPicker(QDialog):
    """Выбор товара из прайса для позиции заказчика."""

    def __init__(self, engine: Engine, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор товара из прайса")
        self.resize(820, 520)
        self.engine = engine
        self.result_ref: str | None = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Позиция заказчика: <b>{text}</b>"))
        self.q = QLineEdit(text)
        self.q.setPlaceholderText("Поиск по прайсу…")
        lay.addWidget(self.q)
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        bb = QDialogButtonBox()
        self.none_btn = bb.addButton("Нет в прайсе (исключить)", QDialogButtonBox.ButtonRole.ResetRole)
        bb.addButton("Выбрать", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton("Отмена", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        self.none_btn.clicked.connect(self._none)
        lay.addWidget(bb)
        self.q.textChanged.connect(self._search)
        self.list.itemDoubleClicked.connect(lambda *_: self._accept())
        self._search()

    def _search(self):
        self.list.clear()
        for item, score in self.engine.index.candidates(self.q.text(), limit=40):
            li = QListWidgetItem(f"{score:3d}%   {item.name}   —   {money(item.price)} руб."
                                 + (f"   [{item.code}]" if item.code else ""))
            li.setData(Qt.ItemDataRole.UserRole, item.code or item.name)
            self.list.addItem(li)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _accept(self):
        it = self.list.currentItem()
        if it:
            self.result_ref = it.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def _none(self):
        self.result_ref = ""
        self.accept()


class TenderDialog(QDialog):
    def __init__(self, engine: Engine, uid: str, log, parent=None):
        super().__init__(parent)
        self.engine, self.uid, self.log = engine, uid, log
        self.setWindowTitle("Карточка тендера")
        self.resize(1250, 780)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.analysis: Analysis | None = None
        self.busy = False

        lay = QVBoxLayout(self)
        self.head = QLabel()
        self.head.setWordWrap(True)
        self.head.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.head)
        self.verdict = QLabel()
        self.verdict.setWordWrap(True)
        self.verdict.setStyleSheet("padding:8px;border-radius:6px;")
        lay.addWidget(self.verdict)

        # --- цена: наценка к прайсу (своя для этого тендера) и подгонка под ориентир ---
        pr = QHBoxLayout()
        pr.addWidget(QLabel("Наценка к прайсу:"))
        self.markup = QDoubleSpinBox()
        self.markup.setRange(-90, 500)
        self.markup.setDecimals(1)
        self.markup.setSingleStep(1)
        self.markup.setSuffix(" %")
        self.markup.setToolTip("Своя наценка для этого тендера: положительная — дороже прайса, "
                               "отрицательная — скидка. Цены пересчитываются сразу.")
        pr.addWidget(self.markup)
        self.incl_vat = QCheckBox("цены в прайсе с НДС")
        self.incl_vat.setToolTip("Отметьте, если в вашем прайсе цены уже включают НДС "
                                 "(розничные прайсы обычно с НДС). Настройка общая для всех тендеров.")
        pr.addWidget(self.incl_vat)
        pr.addSpacing(24)
        pr.addWidget(QLabel("Подогнать — ниже ориентира заказчика на"))
        self.fit_gap = QDoubleSpinBox()
        self.fit_gap.setRange(0, 50)
        self.fit_gap.setDecimals(1)
        self.fit_gap.setValue(1.0)
        self.fit_gap.setSuffix(" %")
        pr.addWidget(self.fit_gap)
        self.b_fit = QPushButton("Подобрать наценку")
        self.b_fit.setToolTip("Рассчитать наценку так, чтобы наше предложение (с НДС) было ниже "
                              "ориентировочной стоимости заказчика на указанный процент")
        pr.addWidget(self.b_fit)
        pr.addStretch(1)
        lay.addLayout(pr)
        self._markup_timer = QTimer(self)
        self._markup_timer.setSingleShot(True)
        self._markup_timer.setInterval(350)
        self._markup_timer.timeout.connect(self._markup_changed)
        self.markup.valueChanged.connect(lambda *_: self._markup_timer.start())
        self.incl_vat.toggled.connect(self._incl_vat_changed)
        self.b_fit.clicked.connect(self._fit_markup)

        split = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._cell_double)
        self.table.itemChanged.connect(self._item_changed)
        split.addWidget(self.table)

        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel()
        self.summary.setStyleSheet("font-size:11pt;")
        bl.addWidget(self.summary)
        bl.addWidget(QLabel("Документы тендера (двойной щелчок — открыть):"))
        self.docs = QListWidget()
        self.docs.itemDoubleClicked.connect(self._open_doc)
        bl.addWidget(self.docs)
        split.addWidget(bottom)
        split.setSizes([480, 200])
        lay.addWidget(split, 1)

        hint = QLabel("Двойной щелчок по колонке «Товар из нашего прайса» — выбрать другой товар "
                      "(выбор запоминается). Цену и количество можно поправить прямо в таблице.")
        hint.setProperty("hint", True)
        lay.addWidget(hint)

        btns = QHBoxLayout()
        self.b_analyze = QPushButton("Скачать документы и сверить с прайсом")
        self.b_prepare = QPushButton("Подготовить пакет документов")
        self.b_prepare.setProperty("primary", True)
        self.b_folder = QPushButton("Открыть папку")
        self.b_site = QPushButton("Открыть на сайте")
        self.b_submitted = QPushButton("Отметить «Подан»")
        self.b_reject = QPushButton("Не участвуем")
        self.b_reject.setProperty("danger", True)
        for b in (self.b_analyze, self.b_prepare, self.b_folder, self.b_site):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(self.b_submitted)
        btns.addWidget(self.b_reject)
        lay.addLayout(btns)
        self.b_analyze.clicked.connect(lambda: self.reanalyze(download=True))
        self.b_prepare.clicked.connect(self.prepare)
        self.b_folder.clicked.connect(self._open_folder)
        self.b_site.clicked.connect(lambda: open_url(self.row["tender"].url))
        self.b_submitted.clicked.connect(lambda: self._set_status(STATUS_SUBMITTED))
        self.b_reject.clicked.connect(lambda: self._set_status(STATUS_REJECTED))

        self.engine.db.mark_seen(uid)
        self.reload()
        self._sync_price_controls()
        self.reanalyze(download=False)

    # --- данные ---------------------------------------------------------------
    def reload(self):
        self.row = self.engine.db.get(self.uid)
        t = self.row["tender"]
        dl = t.deadline.replace("T", " ") if t.deadline else "не указан"
        est = f"{money(t.estimate)} {t.currency}" if t.estimate else "не указана"
        self.head.setText(
            f"<h3 style='margin:0'>{t.title}</h3>"
            f"<p>№ <b>{t.number or t.ext_id}</b> · {t.site} · {t.procedure}<br>"
            f"Заказчик: <b>{t.customer or '—'}</b> {('УНП ' + t.customer_unp) if t.customer_unp else ''}<br>"
            f"Приём предложений до: <b>{dl}</b> · Ориентировочная стоимость: <b>{est}</b>"
            + (f" · ОКРБ: {', '.join(t.okrb[:6])}" if t.okrb else "")
            + f"<br>Статус: <b>{self.row['status']}</b></p>"
        )
        self.docs.clear()
        for d in t.documents:
            li = QListWidgetItem(("✔ " if d.local_path else "⬇ ") + d.name)
            li.setData(Qt.ItemDataRole.UserRole, d.local_path or d.url)
            self.docs.addItem(li)
        folder = Path(self.row["folder"]) / DOCS if self.row["folder"] else None
        if folder and folder.exists():
            known = {Path(d.local_path).name for d in t.documents if d.local_path}
            for p in sorted(folder.rglob("*")):
                if p.is_file() and p.name not in known:
                    li = QListWidgetItem("📄 " + str(p.relative_to(folder)))
                    li.setData(Qt.ItemDataRole.UserRole, str(p))
                    self.docs.addItem(li)

    def _busy(self, on: bool, text: str = ""):
        self.busy = on
        for b in (self.b_analyze, self.b_prepare):
            b.setEnabled(not on)
        if on:
            self.verdict.setText(f"⏳ {text}")
            self.verdict.setStyleSheet("padding:8px;border-radius:6px;background:#fff7d6;")

    def reanalyze(self, download: bool):
        if self.busy:
            return
        t = self.row["tender"]
        self._busy(True, "Скачиваю документы и сверяю с прайсом…" if download else "Сверяю с прайсом…")

        def work():
            if download and t.site in self.engine.sites:
                try:
                    self.engine.sites[t.site].fetch_details(t)
                except Exception as e:  # noqa: BLE001
                    self.log(f"Карточка на сайте не обновлена: {e}")
            return self.engine.analyze(t, download=download)

        run_task(work, on_done=self._analysis_done, on_fail=self._failed)

    def _failed(self, msg: str):
        self._busy(False)
        self.verdict.setText(f"Ошибка: {msg}")
        self.verdict.setStyleSheet("padding:8px;border-radius:6px;background:#fde2e1;")

    def _analysis_done(self, a: Analysis):
        self._busy(False)
        self.analysis = a
        t = self.row["tender"]
        status = self.row["status"]
        if status in ("Новый", STATUS_FIT, STATUS_NOFIT, "Ошибка"):
            status = STATUS_FIT if a.fits else STATUS_NOFIT
        self.engine.db.save_tender(t, status, match_percent=a.summary.percent, our_sum=a.summary.our_sum,
                                   verdict="; ".join(a.reasons))
        self.reload()
        self._fill_table()
        self._show_verdict()

    def _show_verdict(self):
        a = self.analysis
        bg = "#d1f2dc" if a.fits else "#fde2e1"
        word = "✅ Подходит" if a.fits else "⛔ Не проходит по критериям"
        extra = ""
        if a.required:
            extra = "<br><small>В документации упоминаются: " + "; ".join(a.required) + "</small>"
        self.verdict.setText(f"<b>{word}:</b> " + "; ".join(a.reasons) + extra)
        self.verdict.setStyleSheet(f"padding:8px;border-radius:6px;background:{bg};")
        s = a.summary
        vat = self.engine.settings.requisites.vat_payer
        rate = self.engine.settings.terms.vat_rate
        with_vat = s.our_sum * (1 + rate / 100) if vat else s.our_sum
        lim = ""
        if s.limit_sum:
            d = (with_vat - s.limit_sum) / s.limit_sum * 100
            color = "#1a7f37" if d <= 0 else "#b42318"
            pct = f"{d:+.1f}%".replace(".", ",")
            lim = (f" · Ориентир заказчика: <b>{money(s.limit_sum)}</b>"
                   f" · Расхождение: <b style='color:{color}'>{pct}</b>")
        self.summary.setText(f"В прайсе найдено <b>{s.found} из {s.total}</b> позиций · "
                             f"Наша сумма без НДС: <b>{money(s.our_sum)}</b> · "
                             f"{'с НДС' if vat else 'итого'}: <b>{money(with_vat)}</b>{lim}")

    def _vat_mult(self) -> float:
        st = self.engine.settings
        return 1 + st.terms.vat_rate / 100 if st.requisites.vat_payer else 1.0

    def _fill_table(self):
        self.table.blockSignals(True)
        ms = self.analysis.matches
        t = self.row["tender"]
        vm = self._vat_mult()
        self.table.setRowCount(len(ms))
        for i, m in enumerate(ms):
            ours_vat = round(m.price * vm, 2) if (m.item and m.price is not None) else None
            cust = customer_unit_price(m, len(ms), t.estimate)
            diff = (ours_vat - cust) / cust * 100 if (ours_vat is not None and cust) else None
            vals = [str(i + 1), m.position.name, money(m.position.qty).replace(",00", "") if m.position.qty else "",
                    m.position.unit, (m.item.name if m.item else "— нет в прайсе —"),
                    (f"{m.score}%" + (" (вручную)" if m.manual else "")) if m.item else "",
                    money(m.price) if m.price is not None else "",
                    money(ours_vat) if ours_vat is not None else "",
                    money(cust) if cust else "—",
                    (f"{diff:+.1f}%".replace(".", ",")) if diff is not None else "",
                    money((m.price or 0) * m.qty) if m.item else ""]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j not in (C_QTY, C_PRICE):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 1:
                    it.setToolTip(f"{m.position.name}\nИсточник: {m.position.source}")
                if j == C_ITEM and m.item:
                    it.setToolTip(f"{m.item.name}\nКод: {m.item.code}\nЦена прайса: {m.item.price}")
                if j == C_CUST and cust:
                    it.setToolTip("Ориентировочная (предельная) стоимость позиции / количество")
                if j in (C_PRICE, C_OURVAT, C_CUST, C_DIFF, C_SUM):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, j, it)
            if diff is not None:
                d = self.table.item(i, C_DIFF)
                d.setForeground(QColor("#1a7f37" if diff <= 0 else "#b42318"))
                f = d.font()
                f.setBold(True)
                d.setFont(f)
                d.setToolTip("Наша цена ниже цены заказчика" if diff <= 0 else "Наша цена выше цены заказчика")
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if (m.include and m.found) else Qt.CheckState.Unchecked)
            self.table.setItem(i, C_INC, chk)
            color = None
            if not m.found:
                color = QColor("#fde2e1")
            elif m.score < 85 and not m.manual:
                color = QColor("#fff3cd")
            if color:
                for j in range(len(COLS)):
                    self.table.item(i, j).setBackground(color)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(C_ITEM, QHeaderView.ResizeMode.Stretch)
        self.table.blockSignals(False)

    # --- наценка ------------------------------------------------------------------
    def _sync_price_controls(self):
        for w in (self.markup, self.incl_vat):
            w.blockSignals(True)
        mk = self.row["overrides"].get("_markup")
        self.markup.setValue(float(mk) if mk is not None else self.engine.settings.terms.markup_percent)
        self.incl_vat.setChecked(self.engine.settings.terms.prices_include_vat)
        for w in (self.markup, self.incl_vat):
            w.blockSignals(False)

    def _markup_changed(self):
        if not self.analysis:
            return
        ov = dict(self.row["overrides"])
        ov["_markup"] = round(self.markup.value(), 2)
        self.engine.db.save_tender(self.row["tender"], overrides=ov)
        self.row["overrides"] = ov
        self._recalc()

    def _incl_vat_changed(self, on: bool):
        self.engine.settings.terms.prices_include_vat = on
        self.engine.settings.save()
        if self.analysis:
            self._recalc()

    def _fit_markup(self):
        if not self.analysis:
            return
        t = self.row["tender"]
        ms = self.analysis.matches
        target = self.analysis.summary.limit_sum
        if not target:
            parts = [customer_unit_price(m, len(ms), t.estimate) for m in ms if m.found and m.include]
            if parts and all(parts):
                target = sum(p * m.qty for p, m in zip(parts, [m for m in ms if m.found and m.include]))
        if not target:
            QMessageBox.information(self, "Подбор наценки",
                                    "У заказчика не указана ориентировочная стоимость — подгонять не к чему.")
            return
        target *= 1 - self.fit_gap.value() / 100
        fixed = {int(k): float(v["price"]) for k, v in self.row["overrides"].items()
                 if str(k).isdigit() and isinstance(v, dict) and v.get("price") is not None}
        terms = self.engine.terms_for(self.row["overrides"])
        mk = markup_for_target(ms, terms, self._vat_mult(), target, fixed)
        if mk is None:
            return
        mk = int(mk * 10) / 10  # вниз до 0,1 % — чтобы точно уложиться ниже ориентира
        if mk < -90:
            QMessageBox.warning(self, "Подбор наценки", "Даже со скидкой 90 % не уложиться в ориентир заказчика.")
            return
        if mk < 0:
            QMessageBox.information(self, "Подбор наценки",
                                    f"Чтобы уложиться в ориентир, нужна скидка {abs(mk):.1f} % от прайса. "
                                    "Проверьте, выгодно ли это.".replace(".", ",", 1))
        self.markup.setValue(mk)  # сработает пересчёт

    # --- правки пользователя ----------------------------------------------------
    def _override(self, i: int, **kw):
        ov = dict(self.row["overrides"])
        ov.setdefault(str(i), {}).update(kw)
        self.engine.db.save_tender(self.row["tender"], overrides=ov)
        self.row["overrides"] = ov

    def _recalc(self):
        t = self.row["tender"]
        ms = self.engine.match(t, self.row["overrides"])
        a = self.engine.evaluate(t, ms)
        a.infos, a.required, a.conditions = self.analysis.infos, self.analysis.required, self.analysis.conditions
        self._analysis_done(a)

    def _cell_double(self, r: int, c: int):
        if c != C_ITEM or not self.analysis:
            return
        m = self.analysis.matches[r]
        dlg = ItemPicker(self.engine, m.position.name, self)
        if dlg.exec() and dlg.result_ref is not None:
            ref = dlg.result_ref
            self.engine.db.set_mapping(textnorm.key(m.position.name), ref or "-")
            self._override(r, item=ref, include=bool(ref), price=None)
            self._recalc()

    def _item_changed(self, it: QTableWidgetItem):
        if not self.analysis:
            return
        r, c = it.row(), it.column()
        from ..pricelist import parse_number

        if c == C_INC:
            self._override(r, include=it.checkState() == Qt.CheckState.Checked)
        elif c == C_PRICE:
            v = parse_number(it.text())
            if v is not None:
                self._override(r, price=v)
        elif c == C_QTY:
            v = parse_number(it.text())
            if v is not None:
                self._override(r, qty=v)
        else:
            return
        self._recalc()

    # --- действия ----------------------------------------------------------------
    def prepare(self):
        if not self.analysis or self.busy:
            return
        s = self.engine.settings.requisites
        if not s.full_name or not s.unp:
            QMessageBox.warning(self, "Реквизиты", "Сначала заполните реквизиты компании на вкладке «Реквизиты» — "
                                                    "иначе в документах будут пропуски.")
        if not any(m.found and m.include for m in self.analysis.matches):
            QMessageBox.warning(self, "Нет позиций", "Ни одна позиция не включена в предложение.")
            return
        self._busy(True, "Готовлю пакет документов…")
        run_task(self.engine.prepare, self.row["tender"], self.analysis,
                 on_done=self._prepared, on_fail=self._failed)

    def _prepared(self, folder):
        self._busy(False)
        self.reload()
        self._show_verdict()
        box = QMessageBox(self)
        box.setWindowTitle("Пакет готов")
        box.setText("Документы подготовлены. Всё по тендеру — в одной папке (внутри папки заказчика):\n\n"
                    "«1. Документы заказчика» — документация с площадки.\n"
                    "«2. Наше предложение (для подачи)» — файлы для загрузки на площадку.\n"
                    "«3. Для проверки» — чек-лист и сравнение с прайсом.\n\n"
                    "Проверьте документы, подпишите ЭЦП и подайте на площадке.")
        open_btn = box.addButton("Открыть папку", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Закрыть", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            open_path(folder)

    def _open_folder(self):
        if self.row["folder"] and Path(self.row["folder"]).exists():
            open_path(self.row["folder"])

    def _open_doc(self, li: QListWidgetItem):
        target = li.data(Qt.ItemDataRole.UserRole)
        if target and Path(target).exists():
            open_path(target)
        elif target:
            open_url(target)

    def _set_status(self, status: str):
        self.engine.db.set_status(self.uid, status)
        self.reload()
