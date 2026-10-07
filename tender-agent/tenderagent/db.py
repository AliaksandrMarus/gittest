"""Локальная база (SQLite): найденные тендеры, их статусы и ручные сопоставления."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

from .config import data_dir
from .models import Tender

STATUS_NEW = "Новый"
STATUS_FIT = "Подходит"
STATUS_NOFIT = "Не подходит"
STATUS_READY = "Пакет готов"
STATUS_SUBMITTED = "Подан"
STATUS_REJECTED = "Отклонён"
STATUS_EXPIRED = "Срок истёк"
STATUS_ERROR = "Ошибка"
STATUSES = [STATUS_NEW, STATUS_FIT, STATUS_NOFIT, STATUS_READY, STATUS_SUBMITTED,
            STATUS_REJECTED, STATUS_EXPIRED, STATUS_ERROR]


class DB:
    def __init__(self, path=None):
        self.path = path or (data_dir() / "tenders.db")
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenders (
                uid TEXT PRIMARY KEY,
                site TEXT, data TEXT, status TEXT,
                found_at TEXT, updated_at TEXT,
                match_percent INTEGER, our_sum REAL, verdict TEXT,
                folder TEXT DEFAULT '', overrides TEXT DEFAULT '{}', seen INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS mappings (key TEXT PRIMARY KEY, item_ref TEXT);
            CREATE TABLE IF NOT EXISTS forgotten (uid TEXT PRIMARY KEY, at TEXT);
            """
        )
        self.conn.commit()

    def has(self, uid: str) -> bool:
        """Тендер уже известен: есть в списке или был удалён как неактуальный."""
        with self._lock:
            return (self.conn.execute("SELECT 1 FROM tenders WHERE uid=?", (uid,)).fetchone() is not None
                    or self.conn.execute("SELECT 1 FROM forgotten WHERE uid=?", (uid,)).fetchone() is not None)

    def forget(self, uid: str) -> None:
        """Удалить из списка и больше не добавлять при мониторинге."""
        with self._lock:
            self.conn.execute("DELETE FROM tenders WHERE uid=?", (uid,))
            self.conn.execute("INSERT OR REPLACE INTO forgotten(uid, at) VALUES (?, ?)",
                              (uid, datetime.now().isoformat(timespec="seconds")))
            self.conn.commit()

    def save_tender(self, t: Tender, status: str | None = None, **extra) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            row = self.conn.execute("SELECT status FROM tenders WHERE uid=?", (t.uid,)).fetchone()
            if row is None:
                self.conn.execute(
                    "INSERT INTO tenders(uid, site, data, status, found_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (t.uid, t.site, json.dumps(t.to_dict(), ensure_ascii=False), status or STATUS_NEW, now, now),
                )
            else:
                self.conn.execute(
                    "UPDATE tenders SET data=?, updated_at=?, status=COALESCE(?, status) WHERE uid=?",
                    (json.dumps(t.to_dict(), ensure_ascii=False), now, status, t.uid),
                )
            for k, v in extra.items():
                if k in ("match_percent", "our_sum", "verdict", "folder", "seen"):
                    self.conn.execute(f"UPDATE tenders SET {k}=? WHERE uid=?", (v, t.uid))
                elif k == "overrides":
                    self.conn.execute("UPDATE tenders SET overrides=? WHERE uid=?",
                                      (json.dumps(v, ensure_ascii=False), t.uid))
            self.conn.commit()

    def set_status(self, uid: str, status: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE tenders SET status=?, updated_at=? WHERE uid=?",
                              (status, datetime.now().isoformat(timespec="seconds"), uid))
            self.conn.commit()

    def mark_seen(self, uid: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE tenders SET seen=1 WHERE uid=?", (uid,))
            self.conn.commit()

    def get(self, uid: str) -> dict | None:
        with self._lock:
            r = self.conn.execute("SELECT * FROM tenders WHERE uid=?", (uid,)).fetchone()
        return _row(r) if r else None

    def all(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM tenders ORDER BY found_at DESC").fetchall()
        return [_row(r) for r in rows]

    def delete(self, uid: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM tenders WHERE uid=?", (uid,))
            self.conn.commit()

    # --- ручные сопоставления «позиция заказчика → товар прайса» ---
    def mappings(self) -> dict[str, str]:
        with self._lock:
            return {r["key"]: r["item_ref"] for r in self.conn.execute("SELECT * FROM mappings")}

    def set_mapping(self, key: str, item_ref: str | None) -> None:
        with self._lock:
            if item_ref is None:
                self.conn.execute("DELETE FROM mappings WHERE key=?", (key,))
            else:
                self.conn.execute("INSERT OR REPLACE INTO mappings(key, item_ref) VALUES (?,?)", (key, item_ref))
            self.conn.commit()


def _row(r) -> dict:
    d = dict(r)
    d["tender"] = Tender.from_dict(json.loads(d.pop("data")))
    d["overrides"] = json.loads(d.get("overrides") or "{}")
    return d
