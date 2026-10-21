"""Папка входящих накладных: всё, что туда положили, распознаётся и разносится.

Накладные/Входящие     — сюда сканер (или вы) кладёт PDF
Накладные/Обработанные — распознанные файлы (проведённые и ждущие проверки)
Накладные/Ошибки       — файлы, которые не удалось распознать
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import invoice

Extractor = Callable[[Path], invoice.Extracted]


@dataclass
class Folders:
    root: Path

    @property
    def incoming(self) -> Path:
        return self.root / "Накладные" / "Входящие"

    @property
    def done(self) -> Path:
        return self.root / "Накладные" / "Обработанные"

    @property
    def failed(self) -> Path:
        return self.root / "Накладные" / "Ошибки"

    @property
    def sales_file(self) -> Path:
        return self.root / "Продажи.xlsx"

    @property
    def db_file(self) -> Path:
        return self.root / "coffee.db"

    def create(self) -> None:
        for p in (self.incoming, self.done, self.failed):
            p.mkdir(parents=True, exist_ok=True)


@dataclass
class Processed:
    file_name: str
    status: str  # posted, review, error, duplicate
    message: str = ""


def _move(src: Path, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / src.name
    n = 1
    while target.exists():
        target = folder / f"{src.stem} ({n}){src.suffix}"
        n += 1
    shutil.move(str(src), target)
    return target


def _is_ready(path: Path, settle_seconds: float) -> bool:
    """Сканер мог ещё не дописать файл — берём только «успокоившиеся» файлы."""
    try:
        return time.time() - path.stat().st_mtime >= settle_seconds
    except FileNotFoundError:
        return False


def process_file(conn: sqlite3.Connection, path: Path, folders: Folders, extractor: Extractor) -> Processed:
    digest = invoice.file_hash(path)
    existing = invoice.find_by_hash(conn, digest)
    if existing and existing["status"] != "error":
        _move(path, folders.done)
        return Processed(path.name, "duplicate", "Эта накладная уже загружалась")
    if existing:
        # Повторная попытка для ранее не распознанного файла
        invoice.delete_invoice(conn, existing["id"])
    try:
        extracted = extractor(path)
    except invoice.RecognitionError as e:
        invoice.save_error(conn, path.name, digest, str(e))
        _move(path, folders.failed)
        return Processed(path.name, "error", str(e))
    except Exception as e:  # noqa: BLE001 — любой сбой разбора не должен ронять программу
        message = f"Ошибка при чтении файла: {e}"
        invoice.save_error(conn, path.name, digest, message)
        _move(path, folders.failed)
        return Processed(path.name, "error", message)
    # Повторный скан той же бумаги даёт другой файл, поэтому сверяем ещё и реквизиты
    same = invoice.find_same_document(conn, extracted)
    if same:
        _move(path, folders.done)
        return Processed(path.name, "duplicate", f"Накладная № {extracted.number} от {extracted.date} "
                                                 f"уже загружена (файл «{same['file_name']}»)")
    _, status = invoice.save_extracted(conn, path.name, digest, extracted)
    _move(path, folders.done)
    return Processed(path.name, status)


def process_incoming(conn: sqlite3.Connection, folders: Folders, extractor: Extractor,
                     settle_seconds: float = 3) -> list[Processed]:
    folders.create()
    results = []
    for path in sorted(folders.incoming.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf" and _is_ready(path, settle_seconds):
            results.append(process_file(conn, path, folders, extractor))
    return results
