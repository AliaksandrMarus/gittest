"""Окно программы: вкладки «Остатки», «Продажи», «Накладные», «Рецепты», «Отчёты», «Настройки»."""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from . import core, db, export, inbox, invoice, sales_excel

STATUS_NAMES = {"posted": "Проведена", "review": "Нужна проверка", "error": "Не распознана",
                "duplicate": "Повтор"}
RED, YELLOW, GREEN = QColor("#f8d0cc"), QColor("#fbeec1"), QColor("#d7efd2")
CHECK_INTERVAL_MS = 10_000


def data_root() -> Path:
    """Рабочая папка — рядом с CoffeeStock.exe (или COFFEE_STOCK_HOME)."""
    if env := os.environ.get("COFFEE_STOCK_HOME"):
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd() / "data"


def fmt(value) -> str:
    if isinstance(value, float):
        if abs(value - round(value)) < 1e-9:
            return f"{int(round(value)):,}".replace(",", " ")
        return f"{value:,.2f}".replace(",", " ").replace(".", ",")
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    return "" if value is None else str(value)


def fill_table(table: QTableWidget, header: list[str], rows: list[list]) -> None:
    table.clear()
    table.setColumnCount(len(header))
    table.setHorizontalHeaderLabels(header)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(fmt(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if isinstance(value, (int, float)):
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()


def color_row(table: QTableWidget, row: int, color: QColor) -> None:
    for c in range(table.columnCount()):
        if item := table.item(row, c):
            item.setBackground(QBrush(color))


def make_table() -> QTableWidget:
    t = QTableWidget()
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def qdate(iso: str) -> QDate:
    return QDate.fromString(iso, "yyyy-MM-dd")


def open_path(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


# ---- Фоновая обработка накладных ------------------------------------------

class InboxWorker(QThread):
    """Распознавание идёт в отдельном потоке: запрос к Claude длится секунды."""

    done = Signal(list)

    def __init__(self, db_path: Path, folders: inbox.Folders, settle_seconds: float):
        super().__init__()
        self.db_path, self.folders, self.settle = db_path, folders, settle_seconds

    def run(self) -> None:
        conn = db.connect(self.db_path)
        try:
            api_key = db.get_setting(conn, "api_key").strip()
            model = db.get_setting(conn, "model").strip() or db.DEFAULT_SETTINGS["model"]
            results = inbox.process_incoming(conn, self.folders,
                                             lambda p: invoice.extract(p, api_key, model), self.settle)
        except Exception as e:  # noqa: BLE001
            results = [inbox.Processed("—", "error", f"Сбой обработки папки: {e}")]
        finally:
            conn.close()
        self.done.emit(results)


# ---- Диалоги ---------------------------------------------------------------

class MovementDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, title: str, qty_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        form = QFormLayout(self)
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
        form.addRow(qty_label, self.qty)
        form.addRow("Комментарий", self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[int, str, float, str]:
        return (self.ingredient.currentData(), self.day.date().toString("yyyy-MM-dd"),
                self.qty.value(), self.note.text().strip())


# ---- Вкладки ---------------------------------------------------------------

class StockTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        for text, slot in (("Обновить", self.refresh), ("Приход вручную…", self.manual_receipt),
                           ("Инвентаризация (факт. остаток)…", self.inventory)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.info = QLabel()
        layout.addWidget(self.info)
        self.table = make_table()
        layout.addWidget(self.table, 3)
        layout.addWidget(QLabel("Сколько порций ещё можно приготовить:"))
        self.portions = make_table()
        layout.addWidget(self.portions, 2)

    def refresh(self) -> None:
        conn = self.win.conn
        days = int(db.get_setting(conn, "forecast_days") or 14)
        rows = core.forecast(conn, days)
        fill_table(self.table, ["Ингредиент", "Ед.", "Остаток", "Мин. запас", "Расход в день",
                                "Хватит на дней", "Закончится примерно"],
                   [[r.name, r.unit, r.stock, r.min_stock, round(r.per_day, 2),
                     "—" if r.days_left is None else int(r.days_left),
                     "—" if r.run_out is None else date.fromisoformat(r.run_out).strftime("%d.%m.%Y")]
                    for r in rows])
        for i, r in enumerate(rows):
            if r.low:
                color_row(self.table, i, RED)
            elif r.days_left is not None and r.days_left < 7:
                color_row(self.table, i, YELLOW)
        last = core.last_sales_date(conn)
        self.info.setText(
            f"Прогноз по среднему расходу за {days} дн. "
            + (f"Продажи внесены по {date.fromisoformat(last):%d.%m.%Y}." if last else "Продаж пока нет.")
            + "  Красным — меньше минимального запаса или на 1–2 дня, жёлтым — меньше недели."
        )
        fill_table(self.portions, ["Напиток", "Порций", "Первым закончится"],
                   [list(p) for p in core.portions_left(conn)])

    def manual_receipt(self) -> None:
        dlg = MovementDialog(self.win.conn, "Приход вручную", "Количество", self)
        if dlg.exec():
            ing, day, qty, note = dlg.values()
            if qty > 0:
                with self.win.conn:
                    core.add_movement(self.win.conn, day, ing, qty, "receipt", note or "Приход вручную")
                self.win.refresh_all()

    def inventory(self) -> None:
        dlg = MovementDialog(self.win.conn, "Инвентаризация", "Фактический остаток", self)
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
        layout.addWidget(QLabel(
            f"Файл продаж: {win.folders.sales_file}\n"
            "Каждый день впишите количество проданных напитков и сохраните файл — программа "
            "подхватит изменения сама (или нажмите «Загрузить продажи сейчас»)."))
        buttons = QHBoxLayout()
        for text, slot in (("Открыть файл продаж", self.open_file),
                           ("Загрузить продажи сейчас", lambda: self.win.import_sales(manual=True))):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Продажи за последние 31 день:"))
        self.table = make_table()
        layout.addWidget(self.table)

    def open_file(self) -> None:
        sales_excel.ensure_template(self.win.conn, self.win.folders.sales_file)
        open_path(self.win.folders.sales_file)

    def refresh(self) -> None:
        end = date.today()
        start = date.fromordinal(end.toordinal() - 30)
        header, rows = core.report_sales_by_day(self.win.conn, start.isoformat(), end.isoformat())
        fill_table(self.table, header, list(reversed(rows)))


class InvoicesTab(QWidget):
    IGNORE = -1

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.loading = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Сканируйте накладную в PDF в папку:\n{win.folders.incoming}\n"
            "Программа проверяет папку каждые 10 секунд, распознаёт накладную и добавляет приход к остаткам. "
            "Если в накладной встретится незнакомый товар, укажите один раз, какой это ингредиент, — "
            "программа запомнит."))
        buttons = QHBoxLayout()
        for text, slot in (("Открыть папку входящих", lambda: open_path(win.folders.incoming)),
                           ("Выбрать PDF вручную…", self.pick_pdf),
                           ("Проверить папку сейчас", lambda: win.check_inbox(settle=0))):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch()
        layout.addLayout(buttons)

        splitter = QSplitter(Qt.Vertical)
        self.invoices = make_table()
        self.invoices.setSelectionMode(QAbstractItemView.SingleSelection)
        self.invoices.itemSelectionChanged.connect(self.show_lines)
        splitter.addWidget(self.invoices)

        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        self.lines_title = QLabel("Выберите накладную, чтобы увидеть её строки")
        lower_layout.addWidget(self.lines_title)
        self.lines = make_table()
        lower_layout.addWidget(self.lines)
        actions = QHBoxLayout()
        self.post_btn = QPushButton("Провести")
        self.post_btn.clicked.connect(self.post)
        self.unpost_btn = QPushButton("Отменить проведение")
        self.unpost_btn.clicked.connect(self.unpost)
        self.delete_btn = QPushButton("Удалить накладную")
        self.delete_btn.clicked.connect(self.delete)
        for b in (self.post_btn, self.unpost_btn, self.delete_btn):
            actions.addWidget(b)
        actions.addStretch()
        lower_layout.addLayout(actions)
        splitter.addWidget(lower)
        layout.addWidget(splitter, 3)

        layout.addWidget(QLabel("Журнал:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
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
            "SELECT id, created_at, file_name, doc_number, doc_date, supplier, status, note "
            "FROM invoices ORDER BY id DESC LIMIT 500").fetchall()
        fill_table(self.invoices, ["Загружена", "Файл", "№", "Дата накладной", "Поставщик", "Статус",
                                   "Примечание"],
                   [[r["created_at"], r["file_name"], r["doc_number"],
                     date.fromisoformat(r["doc_date"]).strftime("%d.%m.%Y") if r["doc_date"] else "",
                     r["supplier"], STATUS_NAMES.get(r["status"], r["status"]), r["note"]] for r in rows])
        for i, r in enumerate(rows):
            self.invoices.item(i, 0).setData(Qt.UserRole, r["id"])
            color_row(self.invoices, i, {"posted": GREEN, "review": YELLOW}.get(r["status"], RED))
            if r["id"] == keep:
                self.invoices.selectRow(i)
        self.show_lines()

    def show_lines(self) -> None:
        invoice_id = self.selected_invoice()
        conn = self.win.conn
        self.loading = True
        self.lines.clear()
        self.lines.setRowCount(0)
        for b in (self.post_btn, self.unpost_btn, self.delete_btn):
            b.setEnabled(invoice_id is not None)
        if invoice_id is None:
            self.lines_title.setText("Выберите накладную, чтобы увидеть её строки")
            self.loading = False
            return
        status = conn.execute("SELECT status FROM invoices WHERE id = ?", (invoice_id,)).fetchone()["status"]
        posted = status == "posted"
        self.post_btn.setEnabled(status == "review")
        self.unpost_btn.setEnabled(posted)
        self.lines_title.setText(
            "Строки накладной (проведена — для правки сначала отмените проведение)" if posted else
            "Строки накладной: укажите ингредиент и сколько его единиц в одной единице из накладной, "
            "затем нажмите «Провести»")
        ingredients = conn.execute("SELECT id, name, unit FROM ingredients ORDER BY name").fetchall()
        units = {r["id"]: r["unit"] for r in ingredients}
        lines = conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY id",
                             (invoice_id,)).fetchall()
        self.lines.setColumnCount(6)
        self.lines.setHorizontalHeaderLabels(["Наименование в накладной", "Кол-во", "Ед.", "Ингредиент",
                                              "Коэффициент", "Будет оприходовано"])
        self.lines.setRowCount(len(lines))
        for i, line in enumerate(lines):
            for c, v in enumerate((line["raw_name"], line["raw_qty"], line["raw_unit"])):
                item = QTableWidgetItem(fmt(v))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.lines.setItem(i, c, item)
            combo = QComboBox()
            combo.addItem("— выберите —", None)
            combo.addItem("Не учитывать (не ингредиент)", self.IGNORE)
            for r in ingredients:
                combo.addItem(f"{r['name']} ({r['unit']})", r["id"])
            combo.setCurrentIndex(1 if line["ignored"] else max(0, combo.findData(line["ingredient_id"])))
            combo.setEnabled(not posted)
            spin = QDoubleSpinBox()
            spin.setRange(0, 1_000_000)
            spin.setDecimals(3)
            spin.setValue(line["factor"] or 0)
            spin.setEnabled(not posted and not line["ignored"])
            combo.currentIndexChanged.connect(lambda _=0, lid=line["id"], row=i: self.line_changed(lid, row, True))
            spin.valueChanged.connect(lambda _=0, lid=line["id"], row=i: self.line_changed(lid, row, False))
            self.lines.setCellWidget(i, 3, combo)
            self.lines.setCellWidget(i, 4, spin)
            if line["ignored"]:
                total = "не учитывается"
            elif line["ingredient_id"] and line["factor"]:
                total = f"{fmt(line['raw_qty'] * line['factor'])} {units.get(line['ingredient_id'], '')}"
            else:
                total = "?"
            self.lines.setItem(i, 5, QTableWidgetItem(total))
            if not line["ignored"] and not (line["ingredient_id"] and line["factor"]):
                color_row(self.lines, i, YELLOW)
        self.lines.resizeColumnsToContents()
        self.loading = False

    def line_changed(self, line_id: int, row: int, ingredient_changed: bool) -> None:
        if self.loading:
            return
        conn = self.win.conn
        combo: QComboBox = self.lines.cellWidget(row, 3)
        spin: QDoubleSpinBox = self.lines.cellWidget(row, 4)
        data = combo.currentData()
        ignored = data == self.IGNORE
        ingredient_id = None if ignored or data is None else data
        factor = spin.value() or None
        if ingredient_changed and ingredient_id:
            unit = conn.execute("SELECT unit FROM ingredients WHERE id = ?", (ingredient_id,)).fetchone()["unit"]
            raw_unit = conn.execute("SELECT raw_unit FROM invoice_lines WHERE id = ?", (line_id,)).fetchone()[0]
            factor = invoice.unit_factor(raw_unit, unit) or factor
        invoice.update_line(conn, line_id, ingredient_id, factor, ignored)
        self.show_lines()

    def post(self) -> None:
        invoice_id = self.selected_invoice()
        if invoice_id is None:
            return
        try:
            invoice.post_invoice(self.win.conn, invoice_id)
        except ValueError as e:
            QMessageBox.warning(self, "Накладная", str(e))
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
        left.addWidget(QLabel("Напитки:"))
        self.drinks = QListWidget()
        self.drinks.currentItemChanged.connect(lambda *_: self.show_recipe())
        left.addWidget(self.drinks)
        row = QHBoxLayout()
        for text, slot in (("Добавить", self.add_drink), ("Переименовать", self.rename_drink),
                           ("Удалить", self.delete_drink)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        left.addLayout(row)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        self.recipe_title = QLabel()
        right.addWidget(self.recipe_title)
        self.recipe = make_table()
        self.recipe.itemChanged.connect(self.recipe_edited)
        right.addWidget(self.recipe, 2)
        recompute = QPushButton("Пересчитать расход за все дни по текущим рецептам")
        recompute.clicked.connect(self.recompute)
        right.addWidget(recompute)

        right.addWidget(QLabel("Ингредиенты (двойной щелчок — изменить название, единицу, мин. запас):"))
        self.ingredients = make_table()
        self.ingredients.itemChanged.connect(self.ingredient_edited)
        right.addWidget(self.ingredients, 2)
        row = QHBoxLayout()
        for text, slot in (("Добавить ингредиент", self.add_ingredient),
                           ("Удалить ингредиент", self.delete_ingredient)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        right.addLayout(row)
        layout.addLayout(right, 3)

    def refresh(self) -> None:
        current = self.current_drink()
        self.loading = True
        self.drinks.clear()
        for r in self.win.conn.execute("SELECT id, name FROM drinks ORDER BY name"):
            item = QListWidgetItem(r["name"])
            item.setData(Qt.UserRole, r["id"])
            self.drinks.addItem(item)
            if r["id"] == current:
                self.drinks.setCurrentItem(item)
        if self.drinks.currentItem() is None and self.drinks.count():
            self.drinks.setCurrentRow(0)
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
        self.recipe_title.setText(f"Рецепт «{self.drinks.currentItem().text()}» — расход на одну порцию "
                                  "(0 — ингредиент не используется):")
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
            self.recipe.setItem(i, 2, item)
        self.recipe.resizeColumnsToContents()
        self.loading = was_loading

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
        if ok and name.strip():
            try:
                with self.win.conn:
                    self.win.conn.execute("INSERT INTO drinks(name) VALUES (?)", (name.strip(),))
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Напиток", "Такой напиток уже есть")
            sales_excel.ensure_template(self.win.conn, self.win.folders.sales_file)
            self.win.refresh_all()

    def rename_drink(self) -> None:
        drink_id = self.current_drink()
        if drink_id is None:
            return
        name, ok = QInputDialog.getText(self, "Переименовать", "Новое название:",
                                        text=self.drinks.currentItem().text())
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

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        today = QDate.currentDate()
        self.d1 = QDateEdit(QDate(today.year(), today.month(), 1))
        self.d2 = QDateEdit(today)
        for d in (self.d1, self.d2):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd.MM.yyyy")
        self.kind = QComboBox()
        self.kind.addItems(list(core.REPORTS) + [self.FORECAST])
        show = QPushButton("Показать")
        show.clicked.connect(self.refresh)
        save = QPushButton("Экспорт в Excel…")
        save.clicked.connect(self.export)
        for w in (QLabel("С"), self.d1, QLabel("по"), self.d2, QLabel("Отчёт:"), self.kind, show, save):
            row.addWidget(w)
        row.addStretch()
        layout.addLayout(row)
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
        fill_table(self.table, *self.build(self.kind.currentText()))

    def export(self) -> None:
        d1, d2 = self.period()
        default = str(self.win.folders.root / f"Отчёт {d1} — {d2}.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", default, "Excel (*.xlsx)")
        if not path:
            return
        names = list(core.REPORTS) + [self.FORECAST]
        sheets = [(n.split(":")[0].replace("(", "").replace(")", ""), *self.build(n)) for n in names]
        title = f"Кофейный автомат: период {date.fromisoformat(d1):%d.%m.%Y} — {date.fromisoformat(d2):%d.%m.%Y}"
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
        form = QFormLayout(self)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.model = QLineEdit()
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        save = QPushButton("Сохранить")
        save.clicked.connect(self.save)
        folder = QPushButton(str(win.folders.root))
        folder.clicked.connect(lambda: open_path(win.folders.root))
        form.addRow("Рабочая папка", folder)
        form.addRow("Ключ Claude API", self.api_key)
        form.addRow("", QLabel("Нужен для распознавания сканов (картинок). Получить: console.anthropic.com. "
                               "Без ключа читаются только PDF с текстом."))
        form.addRow("Модель Claude", self.model)
        form.addRow("Прогноз по расходу за, дней", self.days)
        form.addRow(save)

    def refresh(self) -> None:
        conn = self.win.conn
        self.api_key.setText(db.get_setting(conn, "api_key"))
        self.model.setText(db.get_setting(conn, "model"))
        self.days.setValue(int(db.get_setting(conn, "forecast_days") or 14))

    def save(self) -> None:
        conn = self.win.conn
        db.set_setting(conn, "api_key", self.api_key.text().strip())
        db.set_setting(conn, "model", self.model.text().strip() or db.DEFAULT_SETTINGS["model"])
        db.set_setting(conn, "forecast_days", str(self.days.value()))
        self.win.refresh_all()
        self.win.statusBar().showMessage("Настройки сохранены", 5000)


# ---- Главное окно ----------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, root: Path):
        super().__init__()
        self.folders = inbox.Folders(root)
        self.folders.create()
        self.conn = db.connect(self.folders.db_file)
        sales_excel.ensure_template(self.conn, self.folders.sales_file)
        self.worker: InboxWorker | None = None

        self.setWindowTitle("Учёт кофейного автомата")
        self.resize(1100, 720)
        self.tabs = QTabWidget()
        self.stock_tab = StockTab(self)
        self.sales_tab = SalesTab(self)
        self.invoices_tab = InvoicesTab(self)
        self.recipes_tab = RecipesTab(self)
        self.reports_tab = ReportsTab(self)
        self.settings_tab = SettingsTab(self)
        for tab, title in ((self.stock_tab, "Остатки"), (self.sales_tab, "Продажи"),
                           (self.invoices_tab, "Накладные"), (self.recipes_tab, "Рецепты"),
                           (self.reports_tab, "Отчёты"), (self.settings_tab, "Настройки")):
            self.tabs.addTab(tab, title)
        self.setCentralWidget(self.tabs)
        for w in (self.stock_tab.table, self.invoices_tab.invoices):
            w.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        self.refresh_all()
        self.import_sales(manual=False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(CHECK_INTERVAL_MS)
        QTimer.singleShot(500, lambda: self.check_inbox(settle=3))

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
            msg += f" (по {date.fromisoformat(result.days[-1]):%d.%m.%Y})"
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
            box = QMessageBox(QMessageBox.Information, "Накладные требуют внимания", "\n".join(review),
                              QMessageBox.Ok, self)
            box.setModal(False)
            box.setAttribute(Qt.WA_DeleteOnClose)
            box.show()

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            self.worker.wait(30_000)
        self.conn.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Учёт кофейного автомата")
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    win = MainWindow(root)
    win.show()
    return app.exec()
