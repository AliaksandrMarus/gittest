"""Карточка накладной на PySide6: реквизиты и строки, сопоставление с товаром, «Сохранить и провести».

Необязательная часть пакета (нужен PySide6). Использование:

    dlg = InvoiceEditor(conn, invoice_id, folders, parent=window)   # invoice_id=None — новая вручную
    if dlg.exec():
        refresh()

Строки, где не выбран товар или коэффициент, подсвечиваются жёлтым; «Приход» показывает,
сколько единиц учёта добавится (количество × коэффициент).
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from . import inbox, recognize, store

YELLOW = "#FBEDC2"


def fmt(value, money: bool = False) -> str:
    if value is None:
        return ""
    if money:
        return f"{value:,.2f}".replace(",", " ").replace(".", ",")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).replace(".", ",")


def money(value) -> str:
    return f"{fmt(value, True)} руб."


def button(text: str, slot, kind: str = "primary") -> QPushButton:
    b = QPushButton(text)
    b.setProperty("kind", kind)  # для QSS: QPushButton[kind="secondary"] { … }
    b.clicked.connect(slot)
    return b


def label(text: str, kind: str = "") -> QLabel:
    w = QLabel(text)
    w.setWordWrap(True)
    if kind:
        w.setProperty(kind, True)
    return w


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class InvoiceEditor(QDialog):
    """Карточка накладной: реквизиты и строки, всё можно исправить вручную."""

    COLS = ["Наименование", "Ед.", "Количество", "Цена", "НДС", "С НДС", "Товар", "Коэфф.", "Приход"]
    NAME, UNIT, QTY, PRICE, VAT, TOTAL, ING, FACTOR, RESULT = range(9)
    IGNORE = -1

    def __init__(self, conn: sqlite3.Connection, invoice_id: int | None = None,
                 folders: inbox.Folders | None = None, parent=None):
        super().__init__(parent)
        self.conn, self.invoice_id = conn, invoice_id
        self.setWindowTitle("Новая накладная" if invoice_id is None else "Накладная")
        self.resize(1180, 620)
        self.items = conn.execute("SELECT id, name, unit FROM items ORDER BY name").fetchall()
        self.units = {r["id"]: r["unit"] for r in self.items}
        layout = QVBoxLayout(self)

        head = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone() if invoice_id else None
        form = QHBoxLayout()
        self.day = QDateEdit()
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd.MM.yyyy")
        doc_date = head["doc_date"] if head and head["doc_date"] else store.today()
        self.day.setDate(QDate.fromString(doc_date, "yyyy-MM-dd"))
        self.doc_number = QLineEdit(head["doc_number"] or "" if head else "")
        self.supplier = QLineEdit(head["supplier"] or "" if head else "")
        self.supplier.setMinimumWidth(320)
        for text, w in (("Дата", self.day), ("№", self.doc_number), ("Поставщик", self.supplier)):
            form.addWidget(QLabel(text))
            form.addWidget(w)
        form.addStretch()
        self.pdf_path = folders.stored_pdf(head["file_name"]) if head and folders else None
        if self.pdf_path:
            form.addWidget(button("Открыть PDF", lambda: open_path(self.pdf_path), "secondary"))
        layout.addLayout(form)
        if head and head["note"]:
            layout.addWidget(label(f"Распознавание: {head['note']}", "hint"))
        layout.addWidget(label(
            "Проверьте строки и исправьте, если что-то распознано неверно. «Товар» — что это из вашего "
            "справочника, «Коэфф.» — сколько его единиц в одной единице накладной (1 кг = 1000 г, "
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
        for ing in self.items:
            combo.addItem(f"{ing['name']} ({ing['unit']})", ing["id"])
        spin = QDoubleSpinBox()
        spin.setRange(0, 1_000_000)
        spin.setDecimals(3)
        if line is not None:
            combo.setCurrentIndex(1 if line["ignored"] else max(0, combo.findData(line["item_id"])))
            spin.setValue(line["factor"] or 0)
        combo.currentIndexChanged.connect(lambda _=0, c=combo: self.item_changed_combo(c))
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

    def item_changed_combo(self, combo: QComboBox) -> None:
        r = self.row_of(combo)
        spin: QDoubleSpinBox = self.table.cellWidget(r, self.FACTOR)
        ing = combo.currentData()
        if ing not in (None, self.IGNORE) and spin.value() == 0:
            spin.setValue(recognize.unit_factor(self.text(r, self.UNIT), self.units[ing]) or 0)
        self.update_results()

    def text(self, r: int, c: int) -> str:
        item = self.table.item(r, c)
        return item.text().strip() if item else ""

    def number(self, r: int, c: int) -> float | None:
        return recognize.parse_number(self.text(r, c)) if self.text(r, c) else None

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
                text, ok = "выберите товар и коэффициент", False
            else:
                text = f"{fmt(qty * spin.value())} {self.units[ing]}"
            self.table.item(r, self.RESULT).setText(text)
            for c in range(self.table.columnCount()):
                if item := self.table.item(r, c):
                    item.setBackground(QBrush(QColor("white" if ok else YELLOW)))
        self.totals.setText(f"НДС: {money(vat_sum)}    Итого с НДС: {money(total_sum)}")
        self.loading = False

    def collect(self) -> list[store.EditedLine] | None:
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
            lines.append(store.EditedLine(
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
        self.invoice_id = store.save_invoice(
            self.conn, self.invoice_id, self.doc_number.text().strip(),
            self.day.date().toString("yyyy-MM-dd"), self.supplier.text().strip(), lines, post)
        if post and store.unresolved_lines(self.conn, self.invoice_id):
            QMessageBox.information(self, "Накладная", "Сохранено, но не проведено: не у всех строк выбран "
                                                       "товар и коэффициент (подсвечены жёлтым).")
            return
        self.accept()
