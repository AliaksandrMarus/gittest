"""Документы, подписанные ЭЦП: достаём файл из «конверта» подписи.

Площадки отдают документацию, подписанную ЭЦП заказчика: внутри файла
.docx/.pdf лежит контейнер подписи (CMS/PKCS#7, ASN.1), а сам документ —
внутри него. Word такой файл открывает с ошибкой «обнаружено содержимое,
которое не удалось прочитать», PDF-читалки пишут «No /Root object».
Здесь вынимаем исходный документ, ничего не меняя в его содержимом.
"""
from __future__ import annotations

from pathlib import Path

_MAGICS = (b"%PDF", b"PK\x03\x04", b"\xd0\xcf\x11\xe0", b"Rar!", b"7z\xbc\xaf", b"{\\rtf")


def is_signed_container(data: bytes) -> bool:
    """ASN.1 SEQUENCE в начале файла и документ где-то внутри."""
    if len(data) < 64 or data[0] != 0x30 or data[1] not in (0x80, 0x81, 0x82, 0x83, 0x84):
        return False
    return any(m in data[:4096] or m in data for m in _MAGICS)


def _from_cms(data: bytes) -> bytes | None:
    try:
        from asn1crypto import cms

        info = cms.ContentInfo.load(data)
        if info["content_type"].native not in ("signed_data", "1.2.840.113549.1.7.2"):
            return None
        content = info["content"]["encap_content_info"]["content"]
        raw = content.native if content is not None else None
        if isinstance(raw, bytes) and raw:
            return raw
    except Exception:  # noqa: BLE001 — нестандартный контейнер: попробуем по сигнатурам
        return None
    return None


def _by_magic(data: bytes) -> bytes | None:
    """Запасной путь: найти начало документа по сигнатуре и отрезать хвост подписи."""
    best = None
    for m in _MAGICS:
        i = data.find(m, 1)
        if i > 0 and (best is None or i < best[0]):
            best = (i, m)
    if not best:
        return None
    start, magic = best
    body = data[start:]
    if magic == b"%PDF":
        end = body.rfind(b"%%EOF")
        return body[: end + 5] if end > 0 else body
    if magic == b"PK\x03\x04":
        eocd = body.rfind(b"PK\x05\x06")
        if eocd > 0 and eocd + 22 <= len(body):
            comment_len = int.from_bytes(body[eocd + 20: eocd + 22], "little")
            return body[: eocd + 22 + comment_len]
        return body
    return body


def unwrap(data: bytes) -> bytes:
    """Вернуть исходный документ (или данные без изменений, если конверта нет)."""
    if not is_signed_container(data):
        return data
    inner = _from_cms(data) or _by_magic(data)
    return inner if inner and inner[:4] in {m[:4] for m in _MAGICS} | {b"{\\rt"} else data


def unwrap_file(path: Path) -> bool:
    """Переписать файл без конверта подписи. True — если файл был в конверте."""
    try:
        data = path.read_bytes()
    except OSError:
        return False
    inner = unwrap(data)
    if inner is data or inner == data:
        return False
    # Подписанный оригинал сохраняем отдельно — он может понадобиться (проверка подписи).
    keep = path.parent / SIGNED_DIR
    keep.mkdir(exist_ok=True)
    sig = keep / (path.name + ".p7s")
    if not sig.exists():
        sig.write_bytes(data)
    path.write_bytes(inner)
    return True


SIGNED_DIR = "_подписанные оригиналы"
