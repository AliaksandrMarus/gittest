"""Окно программы: вкладки «Остатки», «Продажи», «Накладные», «Рецепты и цены», «Отчёты», «Настройки»."""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QSpinBox,
    QSplitter, QStyleFactory, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from . import core, db, export, inbox, invoice, ocr, sales_excel, seed, style, updater
from ._version import VERSION

STATUS_NAMES = {"posted": "Проведена", "review": "Нужна проверка", "error": "Не распознана",
                "duplicate": "Повтор"}
STATUS_COLORS = {"posted": style.GREEN, "review": style.YELLOW, "error": style.RED}
RED, YELLOW = QColor(style.RED), QColor(style.YELLOW)
CHECK_INTERVAL_MS = 10_000
MONEY_WORDS = ("руб", "Цена", "цена", "НДС", "Выручка")


def data_root() -> Path:
    """Рабочая папка — рядом с CoffeeStock.exe (или COFFEE_STOCK_HOME)."""
    if env := os.environ.get("COFFEE_STOCK_HOME"):
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd() / "data"


def fmt(value, money: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and money:
        return f"{value:,.2f}".replace(",", " ").replace(".", ",")
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return f"{int(round(value)):,}".replace(",", " ")
        return f"{value:,.3f}".rstrip("0").replace(",", " ").replace(".", ",")
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            return date.fromisoformat(value).strftime("%d.%m.%Y")
        except ValueError:
            pass
    return str(value)


def money(value) -> str:
    return fmt(value or 0.0, money=True) + " руб."


def fill_table(table: QTableWidget, header: list[str], rows: list[list], bold_last: bool = False) -> None:
    money_cols = {i for i, h in enumerate(header) if any(w in h for w in MONEY_WORDS) and "%" not in h}
    table.clear()
    table.setColumnCount(len(header))
    table.setHorizontalHeaderLabels(header)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(fmt(value, c in money_cols))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if isinstance(value, (int, float)):
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r, c, item)
    if bold_last and rows and str(rows[-1][0]).startswith("Итого"):
        font = QFont()
        font.setBold(True)
        for c in range(len(header)):
            if item := table.item(len(rows) - 1, c):
                item.setFont(font)
                item.setBackground(QBrush(QColor(style.CREAM)))
    table.resizeColumnsToContents()


def color_row(table: QTableWidget, row: int, color: QColor | str) -> None:
    brush = QBrush(QColor(color))
    for c in range(table.columnCount()):
        if item := table.item(row, c):
            item.setBackground(brush)


def make_table() -> QTableWidget:
    t = QTableWidget()
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(30)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def button(text: str, slot, kind: str = "") -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setProperty(kind, True)
    b.clicked.connect(slot)
    b.setCursor(Qt.PointingHandCursor)
    return b


def label(text: str, kind: str = "") -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    if kind:
        lab.setProperty(kind, True)
    return lab


def open_path(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class Card(QFrame):
    """Цветная карточка с крупной цифрой."""

    def __init__(self, title: str):
        super().__init__()
        self.setProperty("card", True)
        self.setMinimumHeight(86)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        self.title = QLabel(title)
        self.value = QLabel("—")
        self.note = QLabel("")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.note)

    def show_value(self, value: str, note: str, colors: str) -> None:
        bg, fg = style.CARD_COLORS[colors]
        self.setStyleSheet(f"QFrame[card='true'] {{ background: {bg}; }}"
                           f"QLabel {{ background: transparent; color: {fg}; }}")
        self.title.setStyleSheet(f"font-weight: 600; color: {fg};")
        self.value.setStyleSheet(f"font-size: 19pt; font-weight: 800; color: {fg};")
        self.value.setText(value)
        self.note.setText(note)


# ---- Фоновая обработка накладных ------------------------------------------

class InboxWorker(QThread):
    """Распознавание идёт в отдельном потоке: OCR скана занимает несколько секунд."""

    done = Signal(list)

    def __init__(self, db_path: Path, folders: inbox.Folders, settle_seconds: float):
        super().__init__()
        self.db_path, self.folders, self.settle = db_path, folders, settle_seconds

    def run(self) -> None:
        conn = db.connect(self.db_path)
        try:
            tesseract = db.get_setting(conn, "tesseract_path").strip()
            results = inbox.process_incoming(conn, self.folders,
                                             lambda p: invoice.extract(p, tesseract), self.settle)
        except Exception as e:  # noqa: BLE001
            results = [inbox.Processed("—", "error", f"Сбой обработки папки: {e}")]
        finally:
            conn.close()
        self.done.emit(results)


class UpdateCheckWorker(QThread):
    done = Signal(object, str)  # Release | None, текст ошибки

    def run(self) -> None:
        try:
            self.done.emit(updater.latest_release(), "")
        except Exception as e:  # noqa: BLE001 — нет интернета и т.п.
            self.done.emit(None, str(e))


class DownloadWorker(QThread):
    progress = Signal(int, int)
    done = Signal(str, str)  # путь к архиву, текст ошибки

    def __init__(self, release: "updater.Release", target: Path):
        super().__init__()
        self.release, self.target = release, target

    def run(self) -> None:
        try:
            path = updater.download(self.release, self.target, lambda d, t: self.progress.emit(d, t))
            self.done.emit(str(path), "")
        except Exception as e:  # noqa: BLE001
            self.done.emit("", str(e))


# ---- Диалоги ---------------------------------------------------------------

class InventoryDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Инвентаризация")
        form = QFormLayout(self)
        form.addRow(label("Укажите, сколько ингредиента есть на самом деле — программа поправит остаток.",
                          "hint"))
        self.ingredient = QComboBox()
        for r in conn.execute("SELECT id, name, unit FROM ingredients ORDER BY name"):
            self.ingredient.addItem(f"{r['name']} ({r['unit']})", r["id"])
        self.day = QDateEdit(QDate.currentDate())
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd.MM.yyyy")
        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 10_000_000)
        self.qty.setDecimals(2)
        self.note = QLineEdit()
        form.addRow("Ингредиент", self.ingredient)
        form.addRow("Дата", self.day)
        form.addRow("Фактический остаток", self.qty)
        form.addRow("Комментарий", self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[int, str, float, str]:
        return (self.ingredient.currentData(), self.day.date().toString("yyyy-MM-dd"),
                self.qty.value(), self.note.text().strip())


class InvoiceEditor(QDialog):
    """Карточка накладной: реквизиты и строки, всё можно исправить вручную."""

    COLS = ["Наименование", "Ед.", "Количество", "Цена", "НДС", "С НДС", "Ингредиент", "Коэфф.", "Приход"]
    NAME, UNIT, QTY, PRICE, VAT, TOTAL, ING, FACTOR, RESULT = range(9)
    IGNORE = -1

    def __init__(self, win: "MainWindow", invoice_id: int | None):
        super().__init__(win)
        self.win, self.invoice_id = win, invoice_id
        conn = win.conn
        self.setWindowTitle("Новая накладная" if invoice_id is None else "Накладная")
        self.resize(1180, 620)
        self.ingredients = conn.execute("SELECT id, name, unit FROM ingredients ORDER BY name").fetchall()
        self.units = {r["id"]: r["unit"] for r in self.ingredients}
        layout = QVBoxLayout(self)

        head = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone() if invoice_id else None
        form = QHBoxLayout()
        self.day = QDateEdit()
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd.MM.yyyy")
        doc_date = head["doc_date"] if head and head["doc_date"] else core.today()
        self.day.setDate(QDate.fromString(doc_date, "yyyy-MM-dd"))
        self.doc_number = QLineEdit(head["doc_number"] or "" if head else "")
        self.supplier = QLineEdit(head["supplier"] or "" if head else "")
        self.supplier.setMinimumWidth(320)
        for text, w in (("Дата", self.day), ("№", self.doc_number), ("Поставщик", self.supplier)):
            form.addWidget(QLabel(text))
            form.addWidget(w)
        form.addStretch()
        self.pdf_path = win.folders.stored_pdf(head["file_name"]) if head else None
        if self.pdf_path:
            form.addWidget(button("Открыть PDF", lambda: open_path(self.pdf_path), "secondary"))
        layout.addLayout(form)
        if head and head["note"]:
            layout.addWidget(label(f"Распознавание: {head['note']}", "hint"))
        layout.addWidget(label(
            "Проверьте строки и исправьте, если что-то распознано неверно. «Ингредиент» — что это из ваших "
            "ингредиентов, «Коэфф.» — сколько его единиц в одной единице накладной (1 кг = 1000 г, "
            "1 уп = 100 шт). Услуги и доставку отметьте «Не учитывать».", "hint"))

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setDefaultSectionSize(32)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.NAME, QHeaderView.Stretch)
        for col, width in ((self.UNIT, 50), (self.QTY, 90), (self.PRICE, 80), (self.VAT, 80), (self.TOTAL, 90),
                           (self.ING, 240), (self.FACTOR, 90), (self.RESULT, 130)):
            self.table.setColumnWidth(col, width)
        self.table.itemChanged.connect(self.item_changed)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        row.addWidget(button("Добавить строку", lambda: self.add_row(), "secondary"))
        row.addWidget(button("Удалить строку", self.delete_row, "secondary"))
        row.addWidget(button("Посчитать «С НДС» = кол-во × цена + НДС", self.recalc, "secondary"))
        row.addStretch()
        self.totals = QLabel()
        self.totals.setProperty("title", True)
        row.addWidget(self.totals)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(button("Отмена", self.reject, "secondary"))
        buttons.addWidget(button("Сохранить", lambda: self.save(False), "secondary"))
        buttons.addWidget(button("Сохранить и провести", lambda: self.save(True)))
        layout.addLayout(buttons)

        self.loading = True
        if invoice_id:
            for line in conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY id", (invoice_id,)):
                self.add_row(line)
        if self.table.rowCount() == 0:
            self.add_row()
        self.loading = False
        self.update_results()

    def add_row(self, line=None) -> None:
        was_loading, self.loading = self.loading, True
        r = self.table.rowCount()
        self.table.insertRow(r)
        values = {self.NAME: "", self.UNIT: "", self.QTY: None, self.PRICE: None, self.VAT: None, self.TOTAL: None}
        if line is not None:
            values = {self.NAME: line["raw_name"], self.UNIT: line["raw_unit"] or "", self.QTY: line["raw_qty"],
                      self.PRICE: line["price"], self.VAT: line["vat"], self.TOTAL: line["total"]}
        for c, v in values.items():
            item = QTableWidgetItem(v if isinstance(v, str) else fmt(v, c in (self.PRICE, self.VAT, self.TOTAL)))
            if c >= self.QTY:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, c, item)
        combo = QComboBox()
        combo.addItem("— выберите —", None)
        combo.addItem("Не учитывать (услуга, доставка)", self.IGNORE)
        for ing in self.ingredients:
            combo.addItem(f"{ing['name']} ({ing['unit']})", ing["id"])
        spin = QDoubleSpinBox()
        spin.setRange(0, 1_000_000)
        spin.setDecimals(3)
        if line is not None:
            combo.setCurrentIndex(1 if line["ignored"] else max(0, combo.findData(line["ingredient_id"])))
            spin.setValue(line["factor"] or 0)
        combo.currentIndexChanged.connect(lambda _=0, c=combo: self.ingredient_changed(c))
        spin.valueChanged.connect(lambda _=0: self.update_results())
        self.table.setCellWidget(r, self.ING, combo)
        self.table.setCellWidget(r, self.FACTOR, spin)
        result = QTableWidgetItem("")
        result.setFlags(result.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, self.RESULT, result)
        self.loading = was_loading
        if line is None and not self.loading:
            self.table.setCurrentCell(r, self.NAME)
            self.update_results()

    def delete_row(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()} | {self.table.currentRow()}, reverse=True)
        for r in rows:
            if r >= 0:
                self.table.removeRow(r)
        self.update_results()

    def row_of(self, widget) -> int:
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, self.ING) is widget:
                return r
        return -1

    def ingredient_changed(self, combo: QComboBox) -> None:
        r = self.row_of(combo)
        spin: QDoubleSpinBox = self.table.cellWidget(r, self.FACTOR)
        ing = combo.currentData()
        if ing not in (None, self.IGNORE) and spin.value() == 0:
            spin.setValue(invoice.unit_factor(self.text(r, self.UNIT), self.units[ing]) or 0)
        self.update_results()

    def text(self, r: int, c: int) -> str:
        item = self.table.item(r, c)
        return item.text().strip() if item else ""

    def number(self, r: int, c: int) -> float | None:
        return invoice.parse_number(self.text(r, c)) if self.text(r, c) else None

    def item_changed(self, item: QTableWidgetItem) -> None:
        if not self.loading and item.column() != self.RESULT:
            self.update_results()

    def recalc(self) -> None:
        self.loading = True
        for r in range(self.table.rowCount()):
            qty, price = self.number(r, self.QTY), self.number(r, self.PRICE)
            if qty is not None and price is not None:
                total = round(qty * price + (self.number(r, self.VAT) or 0), 2)
                self.table.item(r, self.TOTAL).setText(fmt(total, money=True))
        self.loading = False
        self.update_results()

    def update_results(self) -> None:
        self.loading = True
        vat_sum = total_sum = 0.0
        for r in range(self.table.rowCount()):
            combo: QComboBox = self.table.cellWidget(r, self.ING)
            spin: QDoubleSpinBox = self.table.cellWidget(r, self.FACTOR)
            ing, qty = combo.currentData(), self.number(r, self.QTY)
            spin.setEnabled(ing != self.IGNORE)
            vat_sum += self.number(r, self.VAT) or 0
            total_sum += self.number(r, self.TOTAL) or 0
            ok = True
            if not self.text(r, self.NAME) or qty is None or qty <= 0:
                text, ok = "заполните название и количество", False
            elif ing == self.IGNORE:
                text = "не учитывается"
            elif ing is None or spin.value() <= 0:
                text, ok = "выберите ингредиент и коэффициент", False
            else:
                text = f"{fmt(qty * spin.value())} {self.units[ing]}"
            self.table.item(r, self.RESULT).setText(text)
            for c in range(self.table.columnCount()):
                if item := self.table.item(r, c):
                    item.setBackground(QBrush(QColor("white" if ok else style.YELLOW)))
        self.totals.setText(f"НДС: {money(vat_sum)}    Итого с НДС: {money(total_sum)}")
        self.loading = False

    def collect(self) -> list[invoice.EditedLine] | None:
        lines = []
        for r in range(self.table.rowCount()):
            name, qty = self.text(r, self.NAME), self.number(r, self.QTY)
            if not name and qty is None:
                continue  # пустая строка
            if not name or qty is None or qty <= 0:
                QMessageBox.warning(self, "Накладная", f"Строка {r + 1}: укажите наименование и количество.")
                return None
            for c in (self.PRICE, self.VAT, self.TOTAL):
                if self.text(r, c) and self.number(r, c) is None:
                    QMessageBox.warning(self, "Накладная", f"Строка {r + 1}: «{self.text(r, c)}» — не число.")
                    return None
            ing = self.table.cellWidget(r, self.ING).currentData()
            factor = self.table.cellWidget(r, self.FACTOR).value() or None
            lines.append(invoice.EditedLine(
                name, qty, self.text(r, self.UNIT), self.number(r, self.PRICE), self.number(r, self.VAT),
                self.number(r, self.TOTAL), None if ing in (None, self.IGNORE) else ing, factor,
                ing == self.IGNORE))
        return lines

    def save(self, post: bool) -> None:
        lines = self.collect()
        if lines is None:
            return
        if not lines:
            QMessageBox.warning(self, "Накладная", "В накладной нет ни одной строки.")
            return
        self.invoice_id = invoice.save_invoice(
            self.win.conn, self.invoice_id, self.doc_number.text().strip(),
            self.day.date().toString("yyyy-MM-dd"), self.supplier.text().strip(), lines, post)
        if post and invoice.unresolved_lines(self.win.conn, self.invoice_id):
            QMessageBox.information(self, "Накладная", "Сохранено, но не проведено: не у всех строк выбран "
                                                       "ингредиент и коэффициент (подсвечены жёлтым).")
            self.win.refresh_all()
            return
        self.accept()


# ---- Вкладки ---------------------------------------------------------------

class StockTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        layout = QVBoxLayout(self)
        cards = QHBoxLayout()
        self.card_day = Card("Выручка за последний день")
        self.card_month = Card("Выручка за месяц")
        self.card_cups = Card("Продано за месяц")
        self.card_low = Card("Заканчивается")
        for c in (self.card_day, self.card_month, self.card_cups, self.card_low):
            cards.addWidget(c)
        layout.addLayout(cards)

        buttons = QHBoxLayout()
        title = label("Остатки ингредиентов", "title")
        buttons.addWidget(title)
        buttons.addStretch()
        buttons.addWidget(button("Инвентаризация…", self.inventory, "secondary"))
        buttons.addWidget(button("Обновить", self.win_refresh, "secondary"))
        layout.addLayout(buttons)
        self.info = label("", "hint")
        layout.addWidget(self.info)
        self.table = make_table()
        layout.addWidget(self.table, 3)
        layout.addWidget(label("Сколько порций ещё можно приготовить", "title"))
        self.portions = make_table()
        layout.addWidget(self.portions, 2)

    def win_refresh(self) -> None:
        self.win.refresh_all()

    def refresh(self) -> None:
        conn = self.win.conn
        days = int(db.get_setting(conn, "forecast_days") or 14)
        s = core.summary(conn, days)
        self.card_day.show_value(money(s.last_day_money),
                                 f"{fmt(s.last_day)} · {s.last_day_count} порц." if s.last_day else "продаж ещё нет",
                                 "money")
        self.card_month.show_value(money(s.month_money), f"{date.today():%m.%Y}", "month")
        self.card_cups.show_value(f"{s.month_count} порц.", "с начала месяца", "cups")
        self.card_low.show_value(str(s.low_count), "ингредиентов на исходе" if s.low_count else "всё в порядке",
                                 "alert" if s.low_count else "ok")

        rows = core.forecast(conn, days)
        fill_table(self.table, ["Ингредиент", "Ед.", "Остаток", "Мин. запас", "Расход в день",
                                "Хватит на дней", "Закончится примерно"],
                   [[r.name, r.unit, r.stock, r.min_stock, round(r.per_day, 2),
                     "—" if r.days_left is None else int(r.days_left), r.run_out or "—"] for r in rows])
        for i, r in enumerate(rows):
            if r.low:
                color_row(self.table, i, RED)
            elif r.days_left is not None and r.days_left < 7:
                color_row(self.table, i, YELLOW)
        last = core.last_sales_date(conn)
        self.info.setText(
            f"Прогноз по среднему расходу за {days} дн. "
            + (f"Продажи внесены по {fmt(last)}. " if last else "Продаж пока нет. ")
            + "Красным — меньше минимального запаса или на 1–2 дня, жёлтым — меньше чем на неделю.")
        fill_table(self.portions, ["Напиток", "Порций", "Первым закончится"],
                   [list(p) for p in core.portions_left(conn)])

    def inventory(self) -> None:
        dlg = InventoryDialog(self.win.conn, self)
        if dlg.exec():
            ing, day, qty, note = dlg.values()
            with self.win.conn:
                diff = core.adjust_to_actual(self.win.conn, day, ing, qty, note or "Инвентаризация")
            self.win.refresh_all()
            self.win.statusBar().showMessage(f"Остаток исправлен, разница {fmt(diff)}", 8000)


class SalesTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        layout = QVBoxLayout(self)
        layout.addWidget(label("Продажи", "title"))
        layout.addWidget(label(
            f"Файл продаж: {win.folders.sales_file}\n"
            "Каждый день впишите количество проданных напитков и сохраните файл — программа подхватит "
            "изменения сама. Сумма считается по цене напитка на вкладке «Рецепты и цены».", "hint"))
        buttons = QHBoxLayout()
        buttons.addWidget(button("Открыть файл продаж", self.open_file))
        buttons.addWidget(button("Загрузить продажи сейчас", lambda: self.win.import_sales(manual=True),
                                 "secondary"))
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addWidget(label("Последние 31 день", "title"))
        self.table = make_table()
        layout.addWidget(self.table)

    def open_file(self) -> None:
        sales_excel.ensure_template(self.win.conn, self.win.folders.sales_file)
        open_path(self.win.folders.sales_file)

    def refresh(self) -> None:
        end = date.today()
        start = date.fromordinal(end.toordinal() - 30)
        header, rows = core.report_sales_by_day(self.win.conn, start.isoformat(), end.isoformat())
        total = rows[-1:] if rows else []
        fill_table(self.table, header, list(reversed(rows[:-1])) + total, bold_last=True)


class InvoicesTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        layout = QVBoxLayout(self)
        layout.addWidget(label("Накладные", "title"))
        layout.addWidget(label(
            f"Сканируйте накладную в PDF в папку {win.folders.incoming}. Программа проверяет её каждые "
            "10 секунд, распознаёт таблицу (дата, №, поставщик, наименование, количество, цена, НДС, с НДС) "
            "и добавляет приход к остаткам. Если что-то распознано неверно — «Редактировать».", "hint"))
        buttons = QHBoxLayout()
        buttons.addWidget(button("Новая накладная вручную…", self.new_invoice))
        buttons.addWidget(button("Выбрать PDF…", self.pick_pdf, "secondary"))
        buttons.addWidget(button("Открыть папку входящих", lambda: open_path(win.folders.incoming), "secondary"))
        buttons.addWidget(button("Проверить папку сейчас", lambda: win.check_inbox(settle=0), "secondary"))
        buttons.addStretch()
        layout.addLayout(buttons)

        splitter = QSplitter(Qt.Vertical)
        self.invoices = make_table()
        self.invoices.setSelectionMode(QAbstractItemView.SingleSelection)
        self.invoices.itemSelectionChanged.connect(self.show_lines)
        self.invoices.itemDoubleClicked.connect(lambda *_: self.edit(self.selected_invoice()))
        splitter.addWidget(self.invoices)

        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 6, 0, 0)
        self.lines_title = label("Выберите накладную", "title")
        lower_layout.addWidget(self.lines_title)
        self.lines = make_table()
        self.lines.itemDoubleClicked.connect(lambda *_: self.edit(self.selected_invoice()))
        lower_layout.addWidget(self.lines)
        actions = QHBoxLayout()
        self.edit_btn = button("Редактировать…", lambda: self.edit(self.selected_invoice()))
        self.pdf_btn = button("Открыть PDF", self.open_pdf, "secondary")
        self.post_btn = button("Провести", self.post, "secondary")
        self.unpost_btn = button("Отменить проведение", self.unpost, "secondary")
        self.delete_btn = button("Удалить", self.delete, "danger")
        for b in (self.edit_btn, self.pdf_btn, self.post_btn, self.unpost_btn):
            actions.addWidget(b)
        actions.addStretch()
        actions.addWidget(self.delete_btn)
        lower_layout.addLayout(actions)
        splitter.addWidget(lower)
        splitter.setSizes([300, 300])
        layout.addWidget(splitter, 3)

        layout.addWidget(QLabel("Журнал:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        layout.addWidget(self.log)

    def pick_pdf(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Накладные PDF", "", "PDF (*.pdf)")
        for f in files:
            target = self.win.folders.incoming / Path(f).name
            if target.exists():
                target = target.with_name(f"{target.stem}_{date.today():%Y%m%d}{target.suffix}")
            shutil.copy2(f, target)
        if files:
            self.win.check_inbox(settle=0)

    def selected_invoice(self) -> int | None:
        rows = self.invoices.selectionModel().selectedRows()
        if not rows:
            return None
        return self.invoices.item(rows[0].row(), 0).data(Qt.UserRole)

    def refresh(self) -> None:
        keep = self.selected_invoice()
        rows = self.win.conn.execute(
            "SELECT v.*, COUNT(l.id) AS n, SUM(l.vat) AS vat, SUM(l.total) AS total FROM invoices v "
            "LEFT JOIN invoice_lines l ON l.invoice_id = v.id GROUP BY v.id "
            "ORDER BY COALESCE(NULLIF(v.doc_date, ''), date(v.created_at)) DESC, v.id DESC LIMIT 1000").fetchall()
        fill_table(self.invoices, ["Дата", "№", "Поставщик", "Строк", "НДС", "С НДС", "Статус", "Файл",
                                   "Примечание"],
                   [[r["doc_date"] or "", r["doc_number"] or "", r["supplier"] or "", r["n"], r["vat"], r["total"],
                     STATUS_NAMES.get(r["status"], r["status"]), r["file_name"], r["note"] or ""] for r in rows])
        for i, r in enumerate(rows):
            self.invoices.item(i, 0).setData(Qt.UserRole, r["id"])
            color_row(self.invoices, i, STATUS_COLORS.get(r["status"], style.RED))
            if r["id"] == keep:
                self.invoices.selectRow(i)
        self.show_lines()

    def show_lines(self) -> None:
        invoice_id = self.selected_invoice()
        conn = self.win.conn
        for b in (self.edit_btn, self.pdf_btn, self.post_btn, self.unpost_btn, self.delete_btn):
            b.setEnabled(invoice_id is not None)
        if invoice_id is None:
            self.lines_title.setText("Выберите накладную")
            fill_table(self.lines, [], [])
            return
        head = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        self.post_btn.setEnabled(head["status"] == "review")
        self.unpost_btn.setEnabled(head["status"] == "posted")
        self.pdf_btn.setEnabled(self.win.folders.stored_pdf(head["file_name"]) is not None)
        self.lines_title.setText(
            f"Накладная № {head['doc_number'] or '—'} от {fmt(head['doc_date']) or '—'}"
            f" · {head['supplier'] or 'поставщик не указан'} · {STATUS_NAMES.get(head['status'], '')}")
        lines = conn.execute(
            "SELECT l.*, i.name AS ing, i.unit AS ing_unit FROM invoice_lines l "
            "LEFT JOIN ingredients i ON i.id = l.ingredient_id WHERE l.invoice_id = ? ORDER BY l.id",
            (invoice_id,)).fetchall()
        data, bad = [], []
        for i, l in enumerate(lines):
            if l["ignored"]:
                what, result = "не учитывается", ""
            elif l["ing"] and l["factor"]:
                what, result = l["ing"], f"{fmt(l['raw_qty'] * l['factor'])} {l['ing_unit']}"
            else:
                what, result = "не выбран", "?"
                bad.append(i)
            data.append([l["raw_name"], l["raw_unit"] or "", l["raw_qty"], l["price"], l["vat"], l["total"],
                         what, result])
        if data:
            data.append(["Итого", "", None, None, round(sum(l["vat"] or 0 for l in lines), 2),
                         round(sum(l["total"] or 0 for l in lines), 2), "", ""])
        fill_table(self.lines, ["Наименование", "Ед.", "Количество", "Цена", "НДС", "С НДС", "Ингредиент",
                                "Приход"], data, bold_last=True)
        for i in bad:
            color_row(self.lines, i, YELLOW)
        self.lines.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

    def new_invoice(self) -> None:
        self._open_editor(None)

    def edit(self, invoice_id: int | None) -> None:
        if invoice_id is not None:
            self._open_editor(invoice_id)

    def _open_editor(self, invoice_id: int | None) -> None:
        dlg = InvoiceEditor(self.win, invoice_id)
        dlg.exec()
        self.win.refresh_all()
        if dlg.invoice_id is not None:
            for r in range(self.invoices.rowCount()):
                if self.invoices.item(r, 0).data(Qt.UserRole) == dlg.invoice_id:
                    self.invoices.selectRow(r)

    def open_pdf(self) -> None:
        invoice_id = self.selected_invoice()
        if invoice_id is None:
            return
        name = self.win.conn.execute("SELECT file_name FROM invoices WHERE id = ?", (invoice_id,)).fetchone()[0]
        if path := self.win.folders.stored_pdf(name):
            open_path(path)

    def post(self) -> None:
        invoice_id = self.selected_invoice()
        if invoice_id is None:
            return
        try:
            invoice.post_invoice(self.win.conn, invoice_id)
        except ValueError:
            QMessageBox.information(self, "Накладная", "Не у всех строк выбран ингредиент — откроется "
                                                       "карточка накладной.")
            self.edit(invoice_id)
            return
        self.win.refresh_all()

    def unpost(self) -> None:
        invoice_id = self.selected_invoice()
        if invoice_id is not None:
            invoice.unpost_invoice(self.win.conn, invoice_id)
            self.win.refresh_all()

    def delete(self) -> None:
        invoice_id = self.selected_invoice()
        if invoice_id is None:
            return
        if QMessageBox.question(self, "Удалить накладную",
                                "Удалить накладную? Если она проведена, приход уйдёт с остатков.") \
                == QMessageBox.Yes:
            invoice.delete_invoice(self.win.conn, invoice_id)
            self.win.refresh_all()

    def add_log(self, text: str) -> None:
        self.log.append(f"{date.today():%d.%m} {text}")


class RecipesTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.loading = False
        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(label("Напитки и цены", "title"))
        self.drinks = QListWidget()
        self.drinks.currentItemChanged.connect(lambda *_: self.show_recipe())
        left.addWidget(self.drinks)
        price_row = QHBoxLayout()
        price_row.addWidget(QLabel("Цена порции:"))
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 100_000)
        self.price.setDecimals(2)
        self.price.setSuffix(" руб.")
        self.price.editingFinished.connect(self.save_price)
        price_row.addWidget(self.price)
        left.addLayout(price_row)
        row = QHBoxLayout()
        row.addWidget(button("Добавить", self.add_drink))
        row.addWidget(button("Переименовать", self.rename_drink, "secondary"))
        row.addWidget(button("Удалить", self.delete_drink, "danger"))
        left.addLayout(row)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        self.recipe_title = label("", "title")
        right.addWidget(self.recipe_title)
        right.addWidget(label("Расход на одну порцию; 0 — ингредиент не используется. Щёлкните по числу, "
                              "чтобы изменить.", "hint"))
        self.recipe = make_table()
        self.recipe.itemChanged.connect(self.recipe_edited)
        right.addWidget(self.recipe, 2)
        right.addWidget(button("Пересчитать расход за все дни по текущим рецептам", self.recompute, "secondary"))

        right.addWidget(label("Ингредиенты", "title"))
        right.addWidget(label("Двойной щелчок — изменить название, единицу или минимальный запас.", "hint"))
        self.ingredients = make_table()
        self.ingredients.itemChanged.connect(self.ingredient_edited)
        right.addWidget(self.ingredients, 2)
        row = QHBoxLayout()
        row.addWidget(button("Добавить ингредиент", self.add_ingredient))
        row.addWidget(button("Удалить ингредиент", self.delete_ingredient, "danger"))
        row.addStretch()
        right.addLayout(row)
        layout.addLayout(right, 3)

    def refresh(self) -> None:
        current = self.current_drink()
        self.loading = True
        self.drinks.blockSignals(True)
        self.drinks.clear()
        for r in self.win.conn.execute("SELECT id, name, price FROM drinks ORDER BY name"):
            item = QListWidgetItem(f"{r['name']}  —  {money(r['price'])}")
            item.setData(Qt.UserRole, r["id"])
            item.setData(Qt.UserRole + 1, r["name"])
            self.drinks.addItem(item)
            if r["id"] == current:
                self.drinks.setCurrentItem(item)
        if self.drinks.currentItem() is None and self.drinks.count():
            self.drinks.setCurrentRow(0)
        self.drinks.blockSignals(False)
        rows = self.win.conn.execute("SELECT id, name, unit, min_stock FROM ingredients ORDER BY name").fetchall()
        self.ingredients.clear()
        self.ingredients.setColumnCount(3)
        self.ingredients.setHorizontalHeaderLabels(["Название", "Единица (г, мл, шт)", "Мин. запас"])
        self.ingredients.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, v in enumerate((r["name"], r["unit"], fmt(r["min_stock"]))):
                item = QTableWidgetItem(v)
                item.setData(Qt.UserRole, r["id"])
                self.ingredients.setItem(i, c, item)
        self.ingredients.resizeColumnsToContents()
        self.loading = False
        self.show_recipe()

    def current_drink(self) -> int | None:
        item = self.drinks.currentItem()
        return item.data(Qt.UserRole) if item else None

    def show_recipe(self) -> None:
        drink_id = self.current_drink()
        # Вызывается и изнутри refresh(), поэтому флаг восстанавливаем, а не сбрасываем
        was_loading, self.loading = self.loading, True
        self.recipe.clear()
        self.recipe.setRowCount(0)
        if drink_id is None:
            self.loading = was_loading
            return
        drink = self.win.conn.execute("SELECT name, price FROM drinks WHERE id = ?", (drink_id,)).fetchone()
        self.recipe_title.setText(f"Рецепт: {drink['name']}")
        self.price.blockSignals(True)
        self.price.setValue(drink["price"])
        self.price.blockSignals(False)
        rows = self.win.conn.execute(
            "SELECT i.id, i.name, i.unit, COALESCE(r.qty, 0) AS qty FROM ingredients i "
            "LEFT JOIN recipe r ON r.ingredient_id = i.id AND r.drink_id = ? ORDER BY i.name",
            (drink_id,)).fetchall()
        self.recipe.setColumnCount(3)
        self.recipe.setHorizontalHeaderLabels(["Ингредиент", "Ед.", "На порцию"])
        self.recipe.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, v in enumerate((r["name"], r["unit"])):
                item = QTableWidgetItem(v)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.recipe.setItem(i, c, item)
            item = QTableWidgetItem(fmt(r["qty"]))
            item.setData(Qt.UserRole, r["id"])
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if r["qty"]:
                item.setBackground(QBrush(QColor(style.CREAM)))
            self.recipe.setItem(i, 2, item)
        self.recipe.resizeColumnsToContents()
        self.loading = was_loading

    def save_price(self) -> None:
        drink_id = self.current_drink()
        if drink_id is None:
            return
        with self.win.conn:
            self.win.conn.execute("UPDATE drinks SET price = ? WHERE id = ?", (self.price.value(), drink_id))
        self.win.statusBar().showMessage(
            "Цена сохранена. Она применяется к дням продаж, загружаемым с этого момента; прошлые дни "
            "остаются по своей цене.", 10000)
        self.win.refresh_all()

    def recipe_edited(self, item: QTableWidgetItem) -> None:
        if self.loading or item.column() != 2:
            return
        qty = invoice.parse_number(item.text())
        drink_id, ing_id = self.current_drink(), item.data(Qt.UserRole)
        if qty is None or qty < 0:
            QMessageBox.warning(self, "Рецепт", "Введите число, например 8 или 7,5")
            self.show_recipe()
            return
        with self.win.conn:
            if qty == 0:
                self.win.conn.execute("DELETE FROM recipe WHERE drink_id = ? AND ingredient_id = ?",
                                      (drink_id, ing_id))
            else:
                self.win.conn.execute(
                    "INSERT INTO recipe(drink_id, ingredient_id, qty) VALUES (?, ?, ?) "
                    "ON CONFLICT(drink_id, ingredient_id) DO UPDATE SET qty = excluded.qty",
                    (drink_id, ing_id, qty))
        self.win.statusBar().showMessage(
            "Рецепт сохранён. Он применяется к продажам, загружаемым дальше; чтобы пересчитать прошлые "
            "дни, нажмите «Пересчитать расход…».", 10000)

    def recompute(self) -> None:
        if QMessageBox.question(self, "Пересчёт",
                                "Пересчитать списание ингредиентов за все дни по текущим рецептам?") \
                != QMessageBox.Yes:
            return
        with self.win.conn:
            n = core.recompute_all_sales(self.win.conn)
        self.win.refresh_all()
        self.win.statusBar().showMessage(f"Пересчитано дней: {n}", 8000)

    def ingredient_edited(self, item: QTableWidgetItem) -> None:
        if self.loading:
            return
        column = ("name", "unit", "min_stock")[item.column()]
        value: object = item.text().strip()
        if column == "min_stock":
            value = invoice.parse_number(value)
            if value is None:
                QMessageBox.warning(self, "Ингредиент", "Минимальный запас — число")
                self.refresh()
                return
        if not value and column != "min_stock":
            self.refresh()
            return
        try:
            with self.win.conn:
                self.win.conn.execute(f"UPDATE ingredients SET {column} = ? WHERE id = ?",
                                      (value, item.data(Qt.UserRole)))
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Ингредиент", "Такой ингредиент уже есть")
        self.win.refresh_all()

    def add_drink(self) -> None:
        name, ok = QInputDialog.getText(self, "Новый напиток", "Название:")
        if not (ok and name.strip()):
            return
        price, ok = QInputDialog.getDouble(self, "Новый напиток", "Цена порции, руб.:", 0, 0, 100_000, 2)
        if not ok:
            return
        try:
            with self.win.conn:
                self.win.conn.execute("INSERT INTO drinks(name, price) VALUES (?, ?)", (name.strip(), price))
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Напиток", "Такой напиток уже есть")
        sales_excel.ensure_template(self.win.conn, self.win.folders.sales_file)
        self.win.refresh_all()

    def rename_drink(self) -> None:
        drink_id = self.current_drink()
        if drink_id is None:
            return
        name, ok = QInputDialog.getText(self, "Переименовать", "Новое название:",
                                        text=self.drinks.currentItem().data(Qt.UserRole + 1))
        if ok and name.strip():
            try:
                with self.win.conn:
                    self.win.conn.execute("UPDATE drinks SET name = ? WHERE id = ?", (name.strip(), drink_id))
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Напиток", "Такой напиток уже есть")
            QMessageBox.information(self, "Напиток", "Не забудьте переименовать столбец в файле продаж.")
            self.win.refresh_all()

    def delete_drink(self) -> None:
        drink_id = self.current_drink()
        if drink_id is None:
            return
        used = self.win.conn.execute("SELECT COUNT(*) FROM sales WHERE drink_id = ?", (drink_id,)).fetchone()[0]
        if used:
            QMessageBox.warning(self, "Напиток", "По этому напитку уже есть продажи — удалить нельзя.")
            return
        if QMessageBox.question(self, "Удалить", "Удалить напиток и его рецепт?") == QMessageBox.Yes:
            with self.win.conn:
                self.win.conn.execute("DELETE FROM drinks WHERE id = ?", (drink_id,))
            self.win.refresh_all()

    def add_ingredient(self) -> None:
        name, ok = QInputDialog.getText(self, "Новый ингредиент", "Название:")
        if not (ok and name.strip()):
            return
        unit, ok = QInputDialog.getItem(self, "Новый ингредиент", "Единица учёта:", ["г", "мл", "шт"], 0, True)
        if not ok:
            return
        try:
            with self.win.conn:
                self.win.conn.execute("INSERT INTO ingredients(name, unit) VALUES (?, ?)",
                                      (name.strip(), unit.strip() or "шт"))
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Ингредиент", "Такой ингредиент уже есть")
        self.win.refresh_all()

    def delete_ingredient(self) -> None:
        item = self.ingredients.currentItem()
        if item is None:
            return
        ing_id = item.data(Qt.UserRole)
        used = self.win.conn.execute("SELECT COUNT(*) FROM movements WHERE ingredient_id = ?",
                                     (ing_id,)).fetchone()[0]
        if used:
            QMessageBox.warning(self, "Ингредиент", "По ингредиенту уже есть движения — удалить нельзя.")
            return
        if QMessageBox.question(self, "Удалить", "Удалить ингредиент?") == QMessageBox.Yes:
            with self.win.conn:
                self.win.conn.execute("DELETE FROM ingredients WHERE id = ?", (ing_id,))
            self.win.refresh_all()


class ReportsTab(QWidget):
    FORECAST = "Прогноз: на сколько хватит остатков"
    SHEETS = {"Продажи по видам напитков": "Продажи по напиткам", "Продажи по дням": "Продажи по дням",
              "Накладные (приход)": "Накладные", "Движение ингредиентов (оборотка)": "Движение ингредиентов",
              FORECAST: "Прогноз"}

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        layout = QVBoxLayout(self)
        layout.addWidget(label("Отчёты", "title"))
        row = QHBoxLayout()
        today = QDate.currentDate()
        self.d1 = QDateEdit(QDate(today.year(), today.month(), 1))
        self.d2 = QDateEdit(today)
        for d in (self.d1, self.d2):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd.MM.yyyy")
            d.dateChanged.connect(self.refresh)
        self.kind = QComboBox()
        self.kind.addItems(list(core.REPORTS) + [self.FORECAST])
        self.kind.setMinimumWidth(280)
        for w in (QLabel("Период с"), self.d1, QLabel("по"), self.d2, QLabel("   Отчёт:"), self.kind):
            row.addWidget(w)
        row.addStretch()
        row.addWidget(button("Экспорт в Excel…", self.export))
        layout.addLayout(row)
        self.total = label("", "title")
        layout.addWidget(self.total)
        self.table = make_table()
        layout.addWidget(self.table)
        self.kind.currentIndexChanged.connect(self.refresh)

    def period(self) -> tuple[str, str]:
        return self.d1.date().toString("yyyy-MM-dd"), self.d2.date().toString("yyyy-MM-dd")

    def build(self, name: str) -> tuple[list[str], list[list]]:
        if name == self.FORECAST:
            return core.report_forecast(self.win.conn, int(db.get_setting(self.win.conn, "forecast_days") or 14))
        return core.REPORTS[name](self.win.conn, *self.period())

    def refresh(self) -> None:
        name = self.kind.currentText()
        header, rows = self.build(name)
        fill_table(self.table, header, rows, bold_last=True)
        text = ""
        if rows and rows[-1][0] == "Итого":
            if name == "Продажи по видам напитков":
                text = f"Выручка за период: {money(rows[-1][2])} · продано {rows[-1][1]} порц."
            elif name == "Продажи по дням":
                text = f"Выручка за период: {money(rows[-1][-1])}"
            elif name == "Накладные (приход)":
                text = f"Поступило на сумму {money(rows[-1][8])}, в т.ч. НДС {money(rows[-1][7])}"
        self.total.setText(text)
        self.total.setVisible(bool(text))

    def export(self) -> None:
        d1, d2 = self.period()
        default = str(self.win.folders.root / f"Отчёт {fmt(d1)} — {fmt(d2)}.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", default, "Excel (*.xlsx)")
        if not path:
            return
        sheets = [(self.SHEETS[n], *self.build(n)) for n in list(core.REPORTS) + [self.FORECAST]]
        title = f"Кофейный автомат: период {fmt(d1)} — {fmt(d2)}"
        try:
            export.save_reports(Path(path), sheets, title)
        except PermissionError:
            QMessageBox.warning(self, "Экспорт", "Файл открыт в Excel — закройте его и повторите.")
            return
        open_path(Path(path))


class SettingsTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.addWidget(label("Настройки", "title"))
        form = QFormLayout()
        outer.addLayout(form)
        outer.addStretch()
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setSuffix(" дн.")
        self.tesseract = QLineEdit()
        self.tesseract.setPlaceholderText("пусто — использовать встроенный")
        browse = button("Выбрать…", self.browse, "secondary")
        tess_row = QHBoxLayout()
        tess_row.addWidget(self.tesseract)
        tess_row.addWidget(browse)
        self.ocr_status = label("", "hint")
        form.addRow("Рабочая папка", button(str(win.folders.root), lambda: open_path(win.folders.root),
                                            "secondary"))
        form.addRow("Прогноз по расходу за", self.days)
        form.addRow("Распознавание сканов (Tesseract)", tess_row)
        form.addRow("", self.ocr_status)
        self.auto_update = QCheckBox("Проверять обновления при запуске")
        update_row = QHBoxLayout()
        update_row.addWidget(QLabel(f"Версия {VERSION}"))
        update_row.addWidget(button("Проверить обновления", lambda: self.win.check_updates(manual=True),
                                    "secondary"))
        update_row.addStretch()
        form.addRow("Программа", update_row)
        form.addRow("Начальные данные", button("Загрузить начальные данные…", self.load_seed, "secondary"))
        form.addRow("", self.auto_update)
        form.addRow(button("Сохранить", self.save))

    def load_seed(self) -> None:
        if not seed.needed(self.win.conn) and QMessageBox.question(
                self, "Начальные данные",
                "В программе уже есть накладные или продажи. Заменить текущие накладные, продажи и остатки "
                "данными из файла?") != QMessageBox.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Файл начальных данных", "", "Начальные данные (*.json)")
        if not path:
            return
        try:
            data = seed.load(Path(path))
            seed.apply(self.win.conn, data, self.win.folders.sales_file)
        except seed.SeedError as e:
            QMessageBox.warning(self, "Начальные данные", f"Не удалось загрузить: {e}")
            return
        self.win.refresh_all()
        QMessageBox.information(self, "Начальные данные", "Данные загружены: справочники, накладные, продажи.")

    def browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "tesseract.exe", "", "tesseract.exe (tesseract.exe)")
        if path:
            self.tesseract.setText(path)

    def refresh(self) -> None:
        conn = self.win.conn
        self.days.setValue(int(db.get_setting(conn, "forecast_days") or 14))
        self.tesseract.setText(db.get_setting(conn, "tesseract_path"))
        self.auto_update.setChecked(db.get_setting(conn, "auto_update") != "0")
        exe = ocr.find_tesseract(self.tesseract.text().strip())
        self.ocr_status.setText(f"Найден: {exe}" if exe else
                                "Tesseract не найден — сканы-картинки распознаваться не будут, только PDF с текстом.")

    def save(self) -> None:
        conn = self.win.conn
        db.set_setting(conn, "forecast_days", str(self.days.value()))
        db.set_setting(conn, "tesseract_path", self.tesseract.text().strip())
        db.set_setting(conn, "auto_update", "1" if self.auto_update.isChecked() else "0")
        self.win.refresh_all()
        self.win.statusBar().showMessage("Настройки сохранены", 5000)


# ---- Главное окно ----------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, root: Path):
        super().__init__()
        self.folders = inbox.Folders(root)
        self.folders.create()
        self.conn = db.connect(self.folders.db_file)
        seed_message = ""
        try:
            seed_message = seed.apply_from_folder(self.conn, self.folders.root, self.folders.sales_file)
        except seed.SeedError as e:
            seed_message = f"Файл начальных данных не загружен: {e}"
        sales_excel.ensure_template(self.conn, self.folders.sales_file)
        self.worker: InboxWorker | None = None
        self.update_worker: UpdateCheckWorker | None = None
        self.download_worker: DownloadWorker | None = None

        self.setWindowTitle(f"Учёт кофейного автомата — версия {VERSION}")
        self.setWindowIcon(style.app_icon())
        self.resize(1200, 780)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.stock_tab = StockTab(self)
        self.sales_tab = SalesTab(self)
        self.invoices_tab = InvoicesTab(self)
        self.recipes_tab = RecipesTab(self)
        self.reports_tab = ReportsTab(self)
        self.settings_tab = SettingsTab(self)
        for tab, title in ((self.stock_tab, "☕  Остатки"), (self.sales_tab, "Продажи"),
                           (self.invoices_tab, "Накладные"), (self.recipes_tab, "Рецепты и цены"),
                           (self.reports_tab, "Отчёты"), (self.settings_tab, "Настройки")):
            self.tabs.addTab(tab, title)
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(12, 10, 12, 6)
        box.addWidget(self.tabs)
        self.setCentralWidget(container)
        for w in (self.stock_tab.table, self.invoices_tab.invoices):
            w.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        self.refresh_all()
        self.import_sales(manual=False)
        if seed_message:
            self.statusBar().showMessage(seed_message, 20000)
        if seed.needed(self.conn) and not seed_message:
            # Пустая база — сразу предложить загрузить начальные данные, а не искать кнопку
            QTimer.singleShot(800, self.offer_seed)
        if updater.can_update():
            updater.cleanup_after_update(updater.app_dir())
            if not seed_message and (updated := updater.finished_update(updater.app_dir())):
                self.statusBar().showMessage(f"Программа обновлена до версии {updated}", 20000)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(CHECK_INTERVAL_MS)
        QTimer.singleShot(500, lambda: self.check_inbox(settle=3))
        if db.get_setting(self.conn, "auto_update") != "0":
            QTimer.singleShot(3000, lambda: self.check_updates(manual=False))

    def refresh_all(self) -> None:
        for tab in (self.stock_tab, self.sales_tab, self.invoices_tab, self.recipes_tab,
                    self.reports_tab, self.settings_tab):
            tab.refresh()

    def tick(self) -> None:
        self.import_sales(manual=False)
        self.check_inbox(settle=3)

    # -- продажи
    def import_sales(self, manual: bool) -> None:
        path = self.folders.sales_file
        if not path.exists():
            return
        mtime = str(path.stat().st_mtime)
        if not manual and db.get_setting(self.conn, "sales_mtime") == mtime:
            return
        try:
            result = sales_excel.import_file(self.conn, path)
        except PermissionError:
            if manual:
                QMessageBox.warning(self, "Продажи", "Файл занят другой программой, повторите позже.")
            return
        except Exception as e:  # noqa: BLE001 — например, файл сохранён не до конца
            if manual:
                QMessageBox.warning(self, "Продажи", f"Не удалось прочитать файл: {e}")
            return
        db.set_setting(self.conn, "sales_mtime", mtime)
        msg = f"Продажи загружены: дней {len(result.days)}"
        if result.days:
            msg += f" (по {fmt(result.days[-1])})"
        self.statusBar().showMessage(msg, 10000)
        if result.errors:
            text = "\n".join(result.errors[:20])
            if manual:
                QMessageBox.warning(self, "Продажи: замечания", text)
            else:
                self.invoices_tab.add_log("Продажи: " + "; ".join(result.errors[:5]))
        elif manual:
            QMessageBox.information(self, "Продажи", msg)
        self.refresh_all()

    # -- накладные
    def check_inbox(self, settle: float) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        has_pdf = any(p.suffix.lower() == ".pdf" for p in self.folders.incoming.iterdir() if p.is_file())
        if not has_pdf:
            return
        self.statusBar().showMessage("Распознаю накладные…")
        self.worker = InboxWorker(self.folders.db_file, self.folders, settle)
        self.worker.done.connect(self.inbox_done)
        self.worker.start()

    def inbox_done(self, results: list) -> None:
        self.statusBar().clearMessage()
        if not results:
            return
        review = []
        for r in results:
            text = f"{r.file_name}: {STATUS_NAMES.get(r.status, r.status)}"
            if r.message:
                text += f" — {r.message}"
            self.invoices_tab.add_log(text)
            if r.status in ("review", "error"):
                review.append(text)
        self.refresh_all()
        posted = sum(r.status == "posted" for r in results)
        self.statusBar().showMessage(f"Обработано накладных: {len(results)}, проведено: {posted}", 15000)
        if review:
            self.tabs.setCurrentWidget(self.invoices_tab)
            # Немодальное окно: таймер и остальная программа продолжают работать
            box = QMessageBox(QMessageBox.Information, "Накладные требуют внимания",
                              "\n".join(review) + "\n\nОткройте накладную и проверьте строки.",
                              QMessageBox.Ok, self)
            box.setModal(False)
            box.setAttribute(Qt.WA_DeleteOnClose)
            box.show()

    def offer_seed(self) -> None:
        if QMessageBox.question(
                self, "Начальные данные",
                "В программе ещё нет накладных и продаж.\n\nЗагрузить начальные данные из файла "
                "«Начальные данные.json» (накладные, рецептура, продажи, остатки)?") == QMessageBox.Yes:
            self.settings_tab.load_seed()

    # -- обновления
    def check_updates(self, manual: bool) -> None:
        if not updater.can_update():
            if manual:
                QMessageBox.information(self, "Обновления", "Обновление работает только в собранной программе "
                                                           "CoffeeStock.exe под Windows.")
            return
        if self.update_worker is not None and self.update_worker.isRunning():
            return
        self.update_worker = UpdateCheckWorker()
        self.update_worker.done.connect(lambda rel, err: self.update_checked(rel, err, manual))
        self.update_worker.start()

    def update_checked(self, release, error: str, manual: bool) -> None:
        if error:
            if manual:
                QMessageBox.warning(self, "Обновления", f"Не удалось проверить обновления: {error}")
            return
        if release is None or not updater.is_newer(release.version):
            if manual:
                QMessageBox.information(self, "Обновления", f"У вас последняя версия ({VERSION}).")
            return
        text = f"Доступна новая версия {release.version} (у вас {VERSION})."
        if release.notes:
            text += "\n\nЧто нового:\n" + release.notes[:1200]
        text += "\n\nОбновить сейчас? Программа перезапустится, данные и накладные сохранятся."
        if QMessageBox.question(self, "Обновление программы", text) == QMessageBox.Yes:
            self.start_update(release)

    def start_update(self, release) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(60_000)
        dialog = QProgressDialog("Скачиваю обновление…", "Отмена", 0, 100, self)
        dialog.setWindowTitle("Обновление")
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        target = self.folders.root / "_update" / updater.ASSET
        self.download_worker = DownloadWorker(release, target)

        def progress(done: int, total: int) -> None:
            if total:
                dialog.setValue(int(done * 100 / total))
            dialog.setLabelText(f"Скачиваю обновление… {done / 1_048_576:.0f} МБ")

        def finished(path: str, error: str) -> None:
            dialog.close()
            if dialog.wasCanceled():
                return
            if error:
                QMessageBox.warning(self, "Обновление", f"Не удалось скачать обновление: {error}")
                return
            try:
                updater.install(Path(path), updater.app_dir(), self.folders.db_file, release.version)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Обновление", f"Не удалось установить обновление: {e}")
                return
            self.timer.stop()
            QApplication.quit()

        self.download_worker.progress.connect(progress)
        self.download_worker.done.connect(finished)
        self.download_worker.start()
        dialog.show()

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            self.worker.wait(60_000)
        self.conn.close()
        super().closeEvent(event)


def main() -> int:
    if updater.finish_from_args(sys.argv):
        return 0  # это запуск только для замены файлов при обновлении — окно не нужно
    app = QApplication(sys.argv)
    app.setApplicationName("Учёт кофейного автомата")
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(style.QSS)
    app.setWindowIcon(style.app_icon())
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    win = MainWindow(root)
    win.show()
    return app.exec()
