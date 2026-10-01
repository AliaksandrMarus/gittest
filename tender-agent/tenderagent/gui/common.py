"""Общие элементы интерфейса: фоновые задачи, открытие файлов, стиль."""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str)


class Task(QRunnable):
    """Запуск долгой операции в фоне, чтобы окно не зависало."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()
        self.setAutoDelete(False)

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.signals.failed.emit(f"{e}")
            return
        self.signals.done.emit(res)


_alive: set = set()  # держим ссылки, пока задача работает


def run_task(fn, *args, on_done=None, on_fail=None, **kwargs) -> Task:
    t = Task(fn, *args, **kwargs)
    _alive.add(t)
    t.signals.done.connect(lambda *_: _alive.discard(t))
    t.signals.failed.connect(lambda *_: _alive.discard(t))
    if on_done:
        t.signals.done.connect(on_done)
    if on_fail:
        t.signals.failed.connect(on_fail)
    QThreadPool.globalInstance().start(t)
    return t


class LogBus(QObject):
    """Журнал, в который можно писать из любого потока."""

    message = Signal(str)

    def __call__(self, text: str) -> None:
        self.message.emit(str(text))


def open_path(path: str | Path) -> None:
    path = str(path)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


STYLE = """
QWidget { font-size: 10pt; }
QMainWindow, QDialog { background: #f5f6f8; }
QTabWidget::pane { border: 1px solid #d0d4da; background: white; border-radius: 6px; }
QTabBar::tab { padding: 8px 16px; margin-right: 2px; background: #e6e9ee; border-top-left-radius: 6px;
               border-top-right-radius: 6px; }
QTabBar::tab:selected { background: white; font-weight: bold; }
QPushButton { padding: 6px 14px; border: 1px solid #b9c0ca; border-radius: 5px; background: white; }
QPushButton:hover { background: #eef3fb; }
QPushButton:disabled { color: #9aa1ab; }
QPushButton[primary="true"] { background: #1f6feb; color: white; border-color: #1f6feb; font-weight: bold; }
QPushButton[primary="true"]:hover { background: #1a5fd0; }
QPushButton[danger="true"] { color: #b42318; }
QTableView, QTableWidget { gridline-color: #e3e6ea; selection-background-color: #cfe0fb;
                           selection-color: black; alternate-background-color: #f8f9fb; }
QHeaderView::section { background: #eef0f3; padding: 5px; border: none; border-right: 1px solid #d8dce1;
                       font-weight: bold; }
QGroupBox { font-weight: bold; border: 1px solid #d0d4da; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding: 4px; border: 1px solid #c3c9d1;
                       border-radius: 4px; background: white; }
QLabel[hint="true"] { color: #5b6470; }
"""

STATUS_COLORS = {
    "Новый": "#e8f0fe",
    "Подходит": "#d1f2dc",
    "Не подходит": "#f3f4f6",
    "Пакет готов": "#bfe6ff",
    "Подан": "#e3d7ff",
    "Отклонён": "#f3f4f6",
    "Срок истёк": "#f3f4f6",
    "Ошибка": "#fde2e1",
}
