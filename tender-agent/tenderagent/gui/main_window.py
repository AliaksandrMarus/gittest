"""Главное окно ТендерАгента."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSystemTrayIcon,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from .. import pricelist
from ..config import APP_NAME, APP_VERSION, Settings, data_dir, resource_path
from ..db import DB, STATUSES
from ..docs.fill import money
from ..models import Tender
from ..pipeline import Engine, tender_folder
from ..sites import tender_from_url
from .common import STATUS_COLORS, LogBus, open_path, open_url, run_task
from .tender_dialog import TenderDialog

TENDER_COLS = ["Найден", "Площадка", "№", "Предмет закупки", "Заказчик", "Подача до",
               "Ориентир", "В прайсе", "Наша сумма", "Статус", "Запрос"]


def _lines(text: str) -> list[str]:
    return [x.strip() for x in text.replace(";", "\n").splitlines() if x.strip()]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — тендеры Беларуси  v{APP_VERSION}")
        self.resize(1400, 860)
        icon_path = resource_path("assets/icon.ico")
        self.icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self.setWindowIcon(self.icon)

        self.settings = Settings.load()
        self.db = DB()
        self.log = LogBus()
        self.log.message.connect(self._append_log)
        self.engine = Engine(self.settings, self.db, self.log)
        self.monitor_running = False
        self.scan_in_progress = False
        self.next_run: datetime | None = None
        self._quitting = False

        tabs = QTabWidget()
        self.tabs = tabs
        tabs.addTab(self._build_tenders_tab(), "📋 Тендеры")
        tabs.addTab(self._build_search_tab(), "🔎 Что ищем")
        tabs.addTab(self._build_price_tab(), "💰 Прайс")
        tabs.addTab(self._build_requisites_tab(), "🏢 Реквизиты")
        tabs.addTab(self._build_log_tab(), "📝 Журнал")
        self.setCentralWidget(tabs)

        self.status = self.statusBar()
        self.status_label = QLabel()
        self.status.addPermanentWidget(self.status_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30_000)

        self._setup_tray()
        self._load_price(silent=True)
        self.refresh_tenders()
        self._update_status()
        if self.settings.monitor.start_monitoring_on_launch:
            QTimer.singleShot(1500, self.toggle_monitor)
        if not self.settings.requisites.full_name:
            QTimer.singleShot(400, self._first_run_hint)

    # =================================================================== тендеры
    def _build_tenders_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        self.b_monitor = QPushButton("▶ Запустить мониторинг")
        self.b_monitor.setProperty("primary", True)
        self.b_monitor.clicked.connect(self.toggle_monitor)
        self.b_scan = QPushButton("Проверить сейчас")
        self.b_scan.clicked.connect(self.scan_now)
        b_url = QPushButton("+ По ссылке")
        b_url.setToolTip("Добавить тендер по ссылке с icetrade.by / goszakupki.by / zakupki.butb.by")
        b_url.clicked.connect(self.add_by_url)
        b_folder = QPushButton("+ Из папки с документами")
        b_folder.setToolTip("Если документацию скачали сами — программа сверит её с прайсом и заполнит формы")
        b_folder.clicked.connect(self.add_from_folder)
        for b in (self.b_monitor, self.b_scan, b_url, b_folder):
            top.addWidget(b)
        top.addStretch(1)
        top.addWidget(QLabel("Статус:"))
        self.f_status = QComboBox()
        self.f_status.addItems(["Все активные", "Все"] + STATUSES)
        self.f_status.currentIndexChanged.connect(self.refresh_tenders)
        top.addWidget(self.f_status)
        self.f_text = QLineEdit()
        self.f_text.setPlaceholderText("Фильтр по тексту…")
        self.f_text.textChanged.connect(self.refresh_tenders)
        top.addWidget(self.f_text)
        lay.addLayout(top)

        self.progress = QLabel("")
        self.progress.setProperty("hint", True)
        lay.addWidget(self.progress)

        self.tbl = QTableWidget(0, len(TENDER_COLS))
        self.tbl.setHorizontalHeaderLabels(TENDER_COLS)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSortingEnabled(True)
        self.tbl.verticalHeader().setVisible(False)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl.cellDoubleClicked.connect(lambda r, c: self.open_tender(r))
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._tender_menu)
        lay.addWidget(self.tbl, 1)
        hint = QLabel("Двойной щелчок — карточка тендера: сверка с прайсом и подготовка пакета документов. "
                      "Правая кнопка — дополнительные действия.")
        hint.setProperty("hint", True)
        lay.addWidget(hint)
        return w

    def refresh_tenders(self):
        rows = self.db.all()
        flt = self.f_status.currentText()
        text = self.f_text.text().strip().lower()
        if flt == "Все активные":
            rows = [r for r in rows if r["status"] not in ("Не подходит", "Отклонён", "Срок истёк")]
        elif flt != "Все":
            rows = [r for r in rows if r["status"] == flt]
        if text:
            rows = [r for r in rows if text in (r["tender"].title + r["tender"].customer + r["tender"].number).lower()]
        self.tbl.setSortingEnabled(False)
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t: Tender = r["tender"]
            vals = [
                datetime.fromisoformat(r["found_at"]).strftime("%Y-%m-%d %H:%M"),
                self.engine.sites[t.site].cfg.title if t.site in self.engine.sites else t.site,
                t.number or t.ext_id,
                t.title,
                t.customer,
                datetime.fromisoformat(t.deadline).strftime("%Y-%m-%d %H:%M") if t.deadline else "",
                money(t.estimate) if t.estimate else "",
                f"{r['match_percent']}%" if r["match_percent"] is not None else "",
                money(r["our_sum"]) if r["our_sum"] else "",
                r["status"],
                t.matched_query,
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r["uid"])
                if j == 3:
                    it.setToolTip(f"{t.title}\n\n{r.get('verdict') or ''}")
                bg = STATUS_COLORS.get(r["status"])
                if bg:
                    it.setBackground(QColor(bg))
                if not r["seen"] and r["status"] == "Подходит":
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.tbl.setItem(i, j, it)
        self.tbl.setSortingEnabled(True)
        for j, width in enumerate([118, 110, 125, 0, 210, 118, 90, 70, 90, 100, 110]):
            if width:
                self.tbl.setColumnWidth(j, width)

    def _uid_at(self, row: int) -> str | None:
        it = self.tbl.item(row, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def open_tender(self, row: int):
        uid = self._uid_at(row)
        if not uid:
            return
        if not len(self.engine.index):
            QMessageBox.information(self, "Прайс", "Прайс не загружен — сверка невозможна. Загрузите его на вкладке «Прайс».")
        dlg = TenderDialog(self.engine, uid, self.log, self)
        dlg.exec()
        self.refresh_tenders()

    def _tender_menu(self, pos):
        row = self.tbl.rowAt(pos.y())
        uid = self._uid_at(row)
        if not uid:
            return
        rec = self.db.get(uid)
        m = QMenu(self)
        m.addAction("Открыть карточку", lambda: self.open_tender(row))
        m.addAction("Открыть на сайте", lambda: open_url(rec["tender"].url))
        if rec["folder"] and Path(rec["folder"]).exists():
            m.addAction("Открыть папку", lambda: open_path(rec["folder"]))
        st = m.addMenu("Статус")
        for s in STATUSES:
            st.addAction(s, lambda s=s: (self.db.set_status(uid, s), self.refresh_tenders()))
        m.addSeparator()
        m.addAction("Удалить из списка", lambda: (self.db.delete(uid), self.refresh_tenders()))
        m.exec(self.tbl.viewport().mapToGlobal(pos))

    def add_by_url(self):
        url, ok = QInputDialog.getText(self, "Тендер по ссылке", "Ссылка на страницу процедуры:")
        if not ok or not url.strip():
            return
        t = tender_from_url(url.strip(), self.engine.sites)
        if t.site not in self.engine.sites:
            QMessageBox.warning(self, "Ссылка", "Поддерживаются ссылки icetrade.by, goszakupki.by, zakupki.butb.by")
            return
        self.progress.setText("Открываю страницу тендера…")

        def work():
            self.engine.sites[t.site].fetch_details(t)
            t.matched_query = "вручную"
            self.db.save_tender(t)
            return t.uid

        run_task(work, on_done=self._added, on_fail=lambda e: self._fail("Не удалось открыть ссылку", e))

    def add_from_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка с документацией тендера")
        if not folder:
            return
        title, ok = QInputDialog.getText(self, "Тендер", "Предмет закупки / название:", text=Path(folder).name)
        if not ok:
            return
        num, _ = QInputDialog.getText(self, "Тендер", "Номер процедуры (если известен):")
        cust, _ = QInputDialog.getText(self, "Тендер", "Заказчик (если известен):")
        t = Tender(site="manual", ext_id=datetime.now().strftime("%Y%m%d%H%M%S"), url="",
                   title=title or Path(folder).name, number=num, customer=cust, matched_query="вручную")
        dest = tender_folder(t) / "Документация"
        shutil.copytree(folder, dest, dirs_exist_ok=True)
        self.db.save_tender(t, folder=str(dest.parent))
        self._added(t.uid)

    def _added(self, uid: str):
        self.progress.setText("")
        self.refresh_tenders()
        for r in range(self.tbl.rowCount()):
            if self._uid_at(r) == uid:
                self.tbl.selectRow(r)
                self.open_tender(r)
                break

    def _fail(self, title: str, err: str):
        self.progress.setText("")
        self.log(f"{title}: {err}")
        QMessageBox.warning(self, title, err)

    # ================================================================ мониторинг
    def toggle_monitor(self):
        self.monitor_running = not self.monitor_running
        if self.monitor_running:
            self.b_monitor.setText("■ Остановить мониторинг")
            self.log("Мониторинг запущен.")
            self.scan_now()
        else:
            self.b_monitor.setText("▶ Запустить мониторинг")
            self.engine.stop_requested = True
            self.next_run = None
            self.log("Мониторинг остановлен.")
        self._update_status()

    def _tick(self):
        if self.monitor_running and self.next_run and datetime.now() >= self.next_run:
            self.scan_now()
        self._update_status()

    def scan_now(self):
        if self.scan_in_progress:
            return
        self._save_search()
        if not (self.settings.monitor.keywords or self.settings.monitor.okrb_codes):
            QMessageBox.information(self, "Что ищем", "Укажите ключевые слова или коды ОКРБ на вкладке «Что ищем».")
            self.tabs.setCurrentIndex(1)
            if self.monitor_running:
                self.toggle_monitor()
            return
        if not len(self.engine.index):
            self.log("Внимание: прайс не загружен — тендеры будут найдены, но без сверки цен.")
        self.scan_in_progress = True
        self.b_scan.setEnabled(False)
        self.progress.setText("Идёт проверка площадок…")
        task = run_task(self.engine.run_monitor, progress=self.log.message.emit,
                        on_done=self._scan_done, on_fail=self._scan_failed)
        del task

    def _scan_done(self, good: list[str]):
        self.scan_in_progress = False
        self.b_scan.setEnabled(True)
        self.progress.setText(f"Последняя проверка: {datetime.now():%H:%M}. Новых подходящих: {len(good)}.")
        if self.monitor_running:
            self.next_run = datetime.now() + timedelta(minutes=max(5, self.settings.monitor.interval_minutes))
        self.refresh_tenders()
        self._update_status()
        if good:
            text = f"Найдено подходящих тендеров: {len(good)}"
            if self.tray:
                self.tray.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Information, 15000)

    def _scan_failed(self, err: str):
        self.scan_in_progress = False
        self.b_scan.setEnabled(True)
        self.progress.setText("")
        self.log(f"Ошибка проверки: {err}")
        if self.monitor_running:
            self.next_run = datetime.now() + timedelta(minutes=max(5, self.settings.monitor.interval_minutes))

    def _update_status(self):
        parts = [f"Прайс: {len(self.engine.index)} позиций"]
        if self.monitor_running:
            parts.append("Мониторинг: включён" + (f", следующая проверка в {self.next_run:%H:%M}" if self.next_run else ""))
        else:
            parts.append("Мониторинг: выключен")
        parts.append(f"Папка: {data_dir()}")
        self.status_label.setText("   |   ".join(parts))

    # ================================================================== что ищем
    def _build_search_tab(self) -> QWidget:
        m = self.settings.monitor
        w = QWidget()
        lay = QGridLayout(w)

        g1 = QGroupBox("Ключевые слова (по одному в строке)")
        v1 = QVBoxLayout(g1)
        self.e_keywords = QPlainTextEdit("\n".join(m.keywords))
        self.e_keywords.setPlaceholderText("бумага офисная\nкабель ВВГ\nканцтовары")
        v1.addWidget(self.e_keywords)
        lay.addWidget(g1, 0, 0)

        g2 = QGroupBox("Коды ОКРБ (по одному в строке, можно начало кода)")
        v2 = QVBoxLayout(g2)
        self.e_okrb = QPlainTextEdit("\n".join(m.okrb_codes))
        self.e_okrb.setPlaceholderText("17.12.14\n27.32")
        v2.addWidget(self.e_okrb)
        lay.addWidget(g2, 0, 1)

        g3 = QGroupBox("Исключить, если в названии есть (минус-слова)")
        v3 = QVBoxLayout(g3)
        self.e_stop = QPlainTextEdit("\n".join(m.stop_words))
        self.e_stop.setPlaceholderText("ремонт\nуслуги")
        v3.addWidget(self.e_stop)
        lay.addWidget(g3, 0, 2)

        g4 = QGroupBox("Площадки и расписание")
        f4 = QFormLayout(g4)
        self.c_sites = {}
        for key, site in self.engine.sites.items():
            cb = QCheckBox(site.cfg.title)
            cb.setChecked(m.sites.get(key, True))
            self.c_sites[key] = cb
            f4.addRow(cb)
        self.s_interval = QSpinBox()
        self.s_interval.setRange(5, 24 * 60)
        self.s_interval.setSuffix(" мин")
        self.s_interval.setValue(m.interval_minutes)
        f4.addRow("Проверять каждые:", self.s_interval)
        self.s_pages = QSpinBox()
        self.s_pages.setRange(1, 20)
        self.s_pages.setValue(m.pages_per_query)
        f4.addRow("Страниц результатов на запрос:", self.s_pages)
        self.c_autostart = QCheckBox("Запускать мониторинг при открытии программы")
        self.c_autostart.setChecked(m.start_monitoring_on_launch)
        f4.addRow(self.c_autostart)
        self.c_tray = QCheckBox("При закрытии окна сворачивать в трей (работать в фоне)")
        self.c_tray.setChecked(m.minimize_to_tray)
        f4.addRow(self.c_tray)
        b_test = QPushButton("Проверить доступ к площадкам")
        b_test.clicked.connect(self.test_sites)
        f4.addRow(b_test)
        lay.addWidget(g4, 1, 0)

        g5 = QGroupBox("Когда тендер нам подходит")
        f5 = QFormLayout(g5)
        self.s_minpct = QSpinBox()
        self.s_minpct.setRange(1, 100)
        self.s_minpct.setSuffix(" %")
        self.s_minpct.setValue(m.min_match_percent)
        f5.addRow("Позиций тендера есть в нашем прайсе, не меньше:", self.s_minpct)
        self.s_score = QSpinBox()
        self.s_score.setRange(30, 100)
        self.s_score.setSuffix(" %")
        self.s_score.setValue(m.min_item_score)
        f5.addRow("Похожесть названия товара, не меньше:", self.s_score)
        self.c_below = QCheckBox("Наша цена не выше ориентировочной стоимости заказчика")
        self.c_below.setChecked(m.require_price_below_estimate)
        f5.addRow(self.c_below)
        self.c_autodl = QCheckBox("Сразу скачивать документацию найденных тендеров для сверки")
        self.c_autodl.setChecked(m.auto_download_docs)
        f5.addRow(self.c_autodl)
        self.c_autoprep = QCheckBox("Автоматически готовить пакет документов для подходящих")
        self.c_autoprep.setChecked(m.auto_prepare)
        f5.addRow(self.c_autoprep)
        lay.addWidget(g5, 1, 1, 1, 2)

        b_save = QPushButton("Сохранить")
        b_save.setProperty("primary", True)
        b_save.clicked.connect(lambda: (self._save_search(), self.log("Настройки поиска сохранены.")))
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(b_save)
        lay.addLayout(row, 2, 0, 1, 3)
        lay.setRowStretch(0, 1)
        return w

    def _save_search(self):
        m = self.settings.monitor
        m.keywords = _lines(self.e_keywords.toPlainText())
        m.okrb_codes = _lines(self.e_okrb.toPlainText())
        m.stop_words = _lines(self.e_stop.toPlainText())
        m.sites = {k: cb.isChecked() for k, cb in self.c_sites.items()}
        m.interval_minutes = self.s_interval.value()
        m.pages_per_query = self.s_pages.value()
        m.start_monitoring_on_launch = self.c_autostart.isChecked()
        m.minimize_to_tray = self.c_tray.isChecked()
        m.min_match_percent = self.s_minpct.value()
        m.min_item_score = self.s_score.value()
        m.require_price_below_estimate = self.c_below.isChecked()
        m.auto_download_docs = self.c_autodl.isChecked()
        m.auto_prepare = self.c_autoprep.isChecked()
        self.settings.save()

    def test_sites(self):
        self.log("Проверяю доступ к площадкам…")
        self.tabs.setCurrentIndex(4)

        def work():
            out = []
            snap = data_dir() / "Диагностика"
            snap.mkdir(exist_ok=True)
            for key, site in self.engine.sites.items():
                try:
                    url = (site.cfg.search_urls[0]).format(query="бумага", okrb="", page=site.cfg.page_start,
                                                           today=datetime.now().strftime("%d.%m.%Y"))
                    r = self.engine.http.get(url, site.cfg.encoding, retries=1)
                    (snap / f"{key}_поиск.html").write_text(r.text, "utf-8")
                    found = site.parse_list(r.text, r.url)
                    msg = f"{site.cfg.title}: доступен, на странице найдено тендеров: {len(found)}"
                    if found:
                        t = found[0]
                        try:
                            rr = self.engine.http.get(t.url, site.cfg.encoding, retries=1)
                            (snap / f"{key}_карточка.html").write_text(rr.text, "utf-8")
                            site.parse_details(t, rr.text, rr.url)
                            msg += (f"; карточка: «{t.title[:50]}», позиций {len(t.positions)}, "
                                    f"документов {len(t.documents)}, срок {t.deadline or '?'}")
                        except Exception as e:  # noqa: BLE001
                            msg += f"; карточка не открылась: {e}"
                    else:
                        msg += " — список не распознан (пришлите разработчику файлы из папки «Диагностика»)"
                    out.append(msg)
                except Exception as e:  # noqa: BLE001
                    out.append(f"{site.cfg.title}: НЕДОСТУПЕН — {e}")
            out.append(f"Копии страниц сохранены в {snap}")
            return out

        run_task(work, on_done=lambda res: [self.log(x) for x in res],
                 on_fail=lambda e: self.log(f"Ошибка проверки: {e}"))

    # ===================================================================== прайс
    def _build_price_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        b = QPushButton("Выбрать файл прайса…")
        b.setProperty("primary", True)
        b.clicked.connect(self.choose_price)
        top.addWidget(b)
        self.price_path = QLabel(self.settings.pricelist.path or "Файл не выбран")
        top.addWidget(self.price_path, 1)
        b2 = QPushButton("Перечитать")
        b2.setToolTip("Перечитать файл (если вы обновили прайс)")
        b2.clicked.connect(lambda: self._load_price())
        top.addWidget(b2)
        lay.addLayout(top)
        hint = QLabel("Подходят: Excel (.xlsx, .xls), CSV, выгрузка из 1С в Excel или обмен 1С с сайтом "
                      "(CommerceML: import.xml/offers.xml). Колонки определяются автоматически — проверьте ниже.")
        hint.setWordWrap(True)
        hint.setProperty("hint", True)
        lay.addWidget(hint)

        g = QGroupBox("Колонки прайса")
        grid = QGridLayout(g)
        self.sheet_combo = QComboBox()
        self.header_spin = QSpinBox()
        self.header_spin.setRange(0, 200)
        self.header_spin.setSpecialValueText("авто")
        self.header_spin.setValue(self.settings.pricelist.header_row)
        grid.addWidget(QLabel("Лист:"), 0, 0)
        grid.addWidget(self.sheet_combo, 0, 1)
        grid.addWidget(QLabel("Строка заголовков:"), 0, 2)
        grid.addWidget(self.header_spin, 0, 3)
        self.role_combos: dict[str, QComboBox] = {}
        for i, (role, title) in enumerate(pricelist.ROLES.items()):
            cb = QComboBox()
            self.role_combos[role] = cb
            r, c = 1 + i // 4, (i % 4) * 2
            grid.addWidget(QLabel(title + (" *" if role in ("name", "price") else "") + ":"), r, c)
            grid.addWidget(cb, r, c + 1)
        b_apply = QPushButton("Применить")
        b_apply.clicked.connect(self.apply_price_columns)
        grid.addWidget(b_apply, 3, 7)
        self.sheet_combo.activated.connect(lambda *_: self._load_price(reset_columns=True))
        self.header_spin.editingFinished.connect(lambda: self._load_price(reset_columns=True))
        lay.addWidget(g)

        self.price_info = QLabel()
        lay.addWidget(self.price_info)
        self.price_tbl = QTableWidget(0, 0)
        self.price_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.price_tbl, 1)

        tg = QGroupBox("Проверить поиск по прайсу")
        th = QHBoxLayout(tg)
        self.price_test = QLineEdit()
        self.price_test.setPlaceholderText("Введите наименование, как в тендере, — покажу, что найдётся в прайсе")
        self.price_test_out = QLabel()
        self.price_test_out.setWordWrap(True)
        self.price_test.textChanged.connect(self._price_test)
        th.addWidget(self.price_test, 1)
        th.addWidget(self.price_test_out, 2)
        lay.addWidget(tg)
        return w

    def choose_price(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Прайс", self.settings.pricelist.path or str(Path.home()),
            "Прайс (*.xlsx *.xlsm *.xls *.csv *.txt *.xml);;Все файлы (*.*)")
        if not path:
            return
        self.settings.pricelist.path = path
        self.settings.pricelist.sheet = ""
        self.settings.pricelist.header_row = 0
        self.settings.pricelist.columns = {}
        self.header_spin.setValue(0)
        self._load_price(reset_columns=True)

    def _load_price(self, silent: bool = False, reset_columns: bool = False):
        pl = self.settings.pricelist
        if not pl.path:
            self.price_info.setText("Прайс не загружен.")
            return
        if not Path(pl.path).exists():
            self.price_info.setText(f"Файл не найден: {pl.path}")
            if not silent:
                QMessageBox.warning(self, "Прайс", f"Файл не найден:\n{pl.path}")
            return
        if reset_columns:
            pl.columns = {}
            if self.sheet_combo.count():
                pl.sheet = self.sheet_combo.currentText()
            pl.header_row = self.header_spin.value()
        try:
            items, table = pricelist.load_items(pl.path, pl.sheet, pl.header_row, pl.columns)
        except Exception as e:  # noqa: BLE001
            items, table = [], None
            msg = f"Не удалось прочитать прайс: {e}"
            self.price_info.setText(msg)
            self.log(msg)
            if not silent:
                QMessageBox.warning(self, "Прайс", msg)
            try:
                table = pricelist.read_table(pl.path, pl.sheet, pl.header_row)
            except Exception:  # noqa: BLE001
                table = None
        self.price_path.setText(pl.path)
        self.engine.set_price_items(items)
        if table is not None:
            pl.sheet = table.sheet
            self.sheet_combo.blockSignals(True)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(table.sheets)
            self.sheet_combo.setCurrentText(table.sheet)
            self.sheet_combo.blockSignals(False)
            cols = pl.columns or pricelist.guess_columns(table.headers)
            for role, cb in self.role_combos.items():
                cb.clear()
                cb.addItems(["—"] + table.headers)
                cb.setCurrentText(cols.get(role, "—"))
            self.price_tbl.setColumnCount(len(table.headers))
            self.price_tbl.setHorizontalHeaderLabels(table.headers)
            preview = table.rows[:300]
            self.price_tbl.setRowCount(len(preview))
            for i, row in enumerate(preview):
                for j, v in enumerate(row[: len(table.headers)]):
                    self.price_tbl.setItem(i, j, QTableWidgetItem("" if v is None else str(v)))
            self.price_tbl.resizeColumnsToContents()
        else:
            for cb in self.role_combos.values():
                cb.clear()
            self.price_tbl.setRowCount(0)
        if items:
            self.price_info.setText(f"✅ Загружено позиций с ценой: <b>{len(items)}</b>. "
                                    f"Пример: {items[0].name} — {money(items[0].price)} руб.")
            self.log(f"Прайс загружен: {len(items)} позиций")
        self.settings.save()
        self._update_status()

    def apply_price_columns(self):
        cols = {role: cb.currentText() for role, cb in self.role_combos.items() if cb.currentText() not in ("", "—")}
        self.settings.pricelist.columns = cols
        self.settings.pricelist.sheet = self.sheet_combo.currentText()
        self.settings.pricelist.header_row = self.header_spin.value()
        self._load_price()

    def _price_test(self, text: str):
        if not text.strip() or not len(self.engine.index):
            self.price_test_out.setText("")
            return
        res = self.engine.index.candidates(text, limit=3)
        self.price_test_out.setText("<br>".join(f"<b>{s}%</b> {i.name} — {money(i.price)}" for i, s in res))

    # ================================================================= реквизиты
    def _build_requisites_tab(self) -> QWidget:
        req, terms = self.settings.requisites, self.settings.terms
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        w = QWidget()
        lay = QHBoxLayout(w)

        g1 = QGroupBox("Реквизиты участника — вносятся один раз и подставляются во все документы")
        f1 = QFormLayout(g1)
        self.req_edits: dict[str, QLineEdit] = {}
        fields = [
            ("full_name", "Полное наименование", "Общество с ограниченной ответственностью «…»"),
            ("short_name", "Сокращённое наименование", "ООО «…»"),
            ("unp", "УНП", "9 цифр"),
            ("okpo", "ОКПО", ""),
            ("registration_info", "Гос. регистрация", "Свидетельство № … от …, выдано …"),
            ("legal_address", "Юридический адрес", "индекс, г. …, ул. …"),
            ("postal_address", "Почтовый адрес", "если отличается"),
            ("bank_account", "Расчётный счёт (IBAN)", "BY.."),
            ("bank_name", "Банк", ""),
            ("bank_bic", "BIC банка", ""),
            ("bank_address", "Адрес банка", ""),
            ("director_position", "Должность руководителя", "Директор"),
            ("director_name", "ФИО руководителя", "Иванов Иван Иванович"),
            ("director_short", "Подпись (И.О. Фамилия)", "И.И. Иванов"),
            ("acts_on", "Действует на основании", "Устава"),
            ("contact_person", "Контактное лицо", ""),
            ("phone", "Телефон", "+375 …"),
            ("email", "E-mail", ""),
            ("website", "Сайт", ""),
            ("country_of_origin", "Страна происхождения товара по умолчанию", "Республика Беларусь"),
        ]
        for key, label, ph in fields:
            e = QLineEdit(str(getattr(req, key) or ""))
            e.setPlaceholderText(ph)
            self.req_edits[key] = e
            f1.addRow(label + ":", e)
        self.c_vat_payer = QCheckBox("Плательщик НДС")
        self.c_vat_payer.setChecked(req.vat_payer)
        self.c_resident = QCheckBox("Резидент Республики Беларусь")
        self.c_resident.setChecked(req.is_resident)
        self.c_producer = QCheckBox("Мы производитель товара")
        self.c_producer.setChecked(req.is_producer)
        for c in (self.c_vat_payer, self.c_resident, self.c_producer):
            f1.addRow(c)
        lay.addWidget(g1, 3)

        g2 = QGroupBox("Условия предложения по умолчанию")
        f2 = QFormLayout(g2)
        self.t_vat = QDoubleSpinBox()
        self.t_vat.setRange(0, 50)
        self.t_vat.setSuffix(" %")
        self.t_vat.setValue(terms.vat_rate)
        f2.addRow("Ставка НДС:", self.t_vat)
        self.t_incl = QCheckBox("Цены в прайсе указаны С НДС")
        self.t_incl.setChecked(terms.prices_include_vat)
        f2.addRow(self.t_incl)
        self.t_markup = QDoubleSpinBox()
        self.t_markup.setRange(-90, 500)
        self.t_markup.setSuffix(" %")
        self.t_markup.setValue(terms.markup_percent)
        self.t_markup.setToolTip("Положительное — наценка к прайсу, отрицательное — скидка")
        f2.addRow("Наценка (+) / скидка (−) к прайсу:", self.t_markup)
        self.t_delivery = QLineEdit(terms.delivery_term)
        f2.addRow("Срок поставки:", self.t_delivery)
        self.t_place = QLineEdit(terms.delivery_terms_place)
        f2.addRow("Условия поставки:", self.t_place)
        self.t_payment = QLineEdit(terms.payment_terms)
        f2.addRow("Условия оплаты:", self.t_payment)
        self.t_validity = QSpinBox()
        self.t_validity.setRange(1, 365)
        self.t_validity.setSuffix(" дн.")
        self.t_validity.setValue(terms.offer_validity_days)
        f2.addRow("Срок действия предложения:", self.t_validity)
        self.t_warranty = QLineEdit(terms.warranty)
        f2.addRow("Гарантия:", self.t_warranty)
        b = QPushButton("Сохранить реквизиты и условия")
        b.setProperty("primary", True)
        b.clicked.connect(self.save_requisites)
        f2.addRow(b)
        lay.addWidget(g2, 2)
        outer.setWidget(w)
        return outer

    def save_requisites(self):
        req, terms = self.settings.requisites, self.settings.terms
        for key, e in self.req_edits.items():
            setattr(req, key, e.text().strip())
        req.vat_payer = self.c_vat_payer.isChecked()
        req.is_resident = self.c_resident.isChecked()
        req.is_producer = self.c_producer.isChecked()
        terms.vat_rate = self.t_vat.value()
        terms.prices_include_vat = self.t_incl.isChecked()
        terms.markup_percent = self.t_markup.value()
        terms.delivery_term = self.t_delivery.text().strip()
        terms.delivery_terms_place = self.t_place.text().strip()
        terms.payment_terms = self.t_payment.text().strip()
        terms.offer_validity_days = self.t_validity.value()
        terms.warranty = self.t_warranty.text().strip()
        self.settings.save()
        self.log("Реквизиты и условия сохранены.")
        QMessageBox.information(self, APP_NAME, "Сохранено. Реквизиты будут подставляться во все документы.")

    # ==================================================================== журнал
    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        lay.addWidget(self.log_view)
        row = QHBoxLayout()
        b = QPushButton("Открыть папку программы")
        b.clicked.connect(lambda: open_path(data_dir()))
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        return w

    def _append_log(self, text: str):
        line = f"{datetime.now():%d.%m %H:%M:%S}  {text}"
        self.log_view.appendPlainText(line)
        if self.scan_in_progress:
            self.progress.setText(text)
        try:
            with open(data_dir() / "журнал.txt", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    # ====================================================================== трей
    def _setup_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        act_show = QAction("Открыть", self)
        act_show.triggered.connect(self._show_from_tray)
        act_quit = QAction("Выход", self)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_show)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self._show_from_tray()
                                    if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.messageClicked.connect(self._show_from_tray)
        self.tray.show()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.tabs.setCurrentIndex(0)
        self.refresh_tenders()

    def _quit(self):
        self._quitting = True
        self.close()

    def closeEvent(self, event):
        try:
            self._save_search()
        except Exception:  # noqa: BLE001
            pass
        if (not self._quitting and self.tray and self.monitor_running
                and self.settings.monitor.minimize_to_tray):
            event.ignore()
            self.hide()
            self.tray.showMessage(APP_NAME, "Мониторинг продолжает работать в фоне. "
                                            "Выход — правой кнопкой по значку.",
                                  QSystemTrayIcon.MessageIcon.Information, 5000)
            return
        self.engine.stop_requested = True
        if self.tray:
            self.tray.hide()
        event.accept()
        from PySide6.QtWidgets import QApplication

        QApplication.quit()

    def _first_run_hint(self):
        QMessageBox.information(
            self, f"Добро пожаловать в {APP_NAME}",
            "Три шага перед началом работы:\n\n"
            "1. «Реквизиты» — внесите данные компании (один раз).\n"
            "2. «Прайс» — выберите файл прайса (Excel или выгрузка из 1С).\n"
            "3. «Что ищем» — ключевые слова и/или коды ОКРБ.\n\n"
            "Затем на вкладке «Тендеры» нажмите «Запустить мониторинг».")
        self.tabs.setCurrentIndex(3)
