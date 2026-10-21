"""Оформление: «кофейная» палитра, стили виджетов и значок программы."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ESPRESSO = "#3E2723"
COFFEE = "#5D4037"
CARAMEL = "#C8873A"
CARAMEL_DARK = "#A86B26"
LATTE = "#EAD7C3"
FOAM = "#FBF6EF"
CREAM = "#F5EBDD"
SELECTION = "#E2C29F"

# Цвета строк по смыслу
RED = "#F6D3CE"
YELLOW = "#FBEDC2"
GREEN = "#D9EDD3"

# Карточки на главной вкладке: (фон, цвет цифры)
CARD_COLORS = {
    "money": ("#FCE9D2", "#8A4B12"),
    "month": ("#E7F0DC", "#3F6B2A"),
    "cups": ("#E3ECF5", "#2F5578"),
    "alert": ("#F8DCD7", "#9B2C1F"),
    "ok": ("#E7F0DC", "#3F6B2A"),
}

QSS = f"""
QMainWindow, QDialog {{ background: {FOAM}; }}
QWidget {{ font-size: 10pt; color: #2B1D16; }}

QTabWidget::pane {{ border: 1px solid {LATTE}; border-radius: 8px; background: white; top: -1px; }}
QTabBar::tab {{
    background: {CREAM}; color: {COFFEE}; padding: 9px 20px; margin-right: 3px;
    border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 600;
}}
QTabBar::tab:selected {{ background: {COFFEE}; color: white; }}
QTabBar::tab:hover:!selected {{ background: {LATTE}; }}

QPushButton {{
    background: {CARAMEL}; color: white; border: none; border-radius: 6px;
    padding: 7px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: {CARAMEL_DARK}; }}
QPushButton:pressed {{ background: {COFFEE}; }}
QPushButton:disabled {{ background: #D9CFC4; color: #F7F2EC; }}
QPushButton[secondary="true"] {{ background: white; color: {COFFEE}; border: 1px solid {CARAMEL}; }}
QPushButton[secondary="true"]:hover {{ background: {CREAM}; }}
QPushButton[danger="true"] {{ background: #B5483A; }}
QPushButton[danger="true"]:hover {{ background: #933629; }}

QLineEdit, QDateEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: white; border: 1px solid #D8C3AC; border-radius: 5px; padding: 4px 6px;
    selection-background-color: {SELECTION};
}}
QLineEdit:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {CARAMEL};
}}

QTableWidget, QListWidget, QTextEdit {{
    background: white; border: 1px solid {LATTE}; border-radius: 6px;
    gridline-color: #EFE4D7; alternate-background-color: #FCF8F3;
    selection-background-color: {SELECTION}; selection-color: #2B1D16;
}}
QHeaderView {{ background: {LATTE}; }}
QHeaderView::section {{
    background: {LATTE}; color: {ESPRESSO}; padding: 6px; border: none;
    border-right: 1px solid #F3E8DB; font-weight: 700;
}}
QListWidget::item {{ padding: 6px; }}
QListWidget::item:selected {{ background: {SELECTION}; color: #2B1D16; }}

QLabel[title="true"] {{ font-size: 13pt; font-weight: 700; color: {COFFEE}; }}
QLabel[hint="true"] {{ color: #7A6656; }}
QFrame[card="true"] {{ border-radius: 10px; }}
QStatusBar {{ background: {COFFEE}; color: white; }}
QStatusBar QLabel {{ color: white; }}
QSplitter::handle {{ background: {FOAM}; }}
"""


def app_icon() -> QIcon:
    """Чашка кофе, нарисованная кодом — без отдельных файлов."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(COFFEE), 4))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(40, 24, 16, 18))  # ручка
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(CARAMEL)))
    cup = QPainterPath()
    cup.moveTo(8, 20)
    cup.lineTo(48, 20)
    cup.lineTo(44, 50)
    cup.quadTo(28, 58, 12, 50)
    cup.closeSubpath()
    p.drawPath(cup)
    p.setBrush(QBrush(QColor(ESPRESSO)))
    p.drawEllipse(QRectF(9, 15, 38, 10))
    p.setPen(QPen(QColor(COFFEE), 3, Qt.SolidLine, Qt.RoundCap))
    for x in (20, 30):
        steam = QPainterPath()
        steam.moveTo(x, 12)
        steam.cubicTo(x - 5, 8, x + 5, 5, x, 1)
        p.drawPath(steam)
    p.end()
    return QIcon(pix)
