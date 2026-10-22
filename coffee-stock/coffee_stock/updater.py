"""Обновление программы без переустановки.

Каждая сборка выкладывается на GitHub в раздел Releases архивом CoffeeStock.zip
с тегом coffee-stock-v1.0.N. Программа сравнивает свою версию с последним
выпуском, скачивает архив и заменяет свои файлы (CoffeeStock.exe, _internal,
tesseract). Данные — coffee.db, Продажи.xlsx, папка «Накладные» — лежат рядом
и не трогаются; перед обновлением база дополнительно копируется в резерв.

Заменить запущенный exe нельзя, поэтому файлы копирует маленький bat-скрипт:
он ждёт, пока программа закроется, копирует новые файлы и запускает её снова.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ._version import VERSION

REPO = "AliaksandrMarus/gittest"
TAG_PREFIX = "coffee-stock-v"
ASSET = "CoffeeStock.zip"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
# Что принадлежит программе и заменяется при обновлении
PROGRAM_PARTS = ("CoffeeStock.exe", "_internal", "tesseract")


@dataclass
class Release:
    version: str
    url: str
    notes: str
    size: int


def parse_version(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def is_newer(remote: str, local: str = VERSION) -> bool:
    return parse_version(remote) > parse_version(local)


def pick_release(releases: list[dict]) -> Release | None:
    """Самый новый выпуск программы (в репозитории могут быть и другие выпуски)."""
    best: Release | None = None
    for r in releases:
        tag = r.get("tag_name") or ""
        if r.get("draft") or r.get("prerelease") or not tag.startswith(TAG_PREFIX):
            continue
        asset = next((a for a in r.get("assets") or [] if a.get("name") == ASSET), None)
        if asset is None:
            continue
        version = tag[len(TAG_PREFIX):]
        if best is None or parse_version(version) > parse_version(best.version):
            best = Release(version, asset["browser_download_url"], (r.get("body") or "").strip(),
                           int(asset.get("size") or 0))
    return best


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": "CoffeeStock-updater",
                                                "Accept": "application/vnd.github+json"})


def latest_release(timeout: float = 10) -> Release | None:
    with urllib.request.urlopen(_request(API), timeout=timeout) as resp:
        return pick_release(json.load(resp))


def download(release: Release, target: Path, progress: Callable[[int, int], None] | None = None) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(_request(release.url), timeout=60) as resp, open(target, "wb") as out:
        total = int(resp.headers.get("Content-Length") or release.size or 0)
        done = 0
        while chunk := resp.read(256 * 1024):
            out.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if not zipfile.is_zipfile(target):
        raise ValueError("скачанный файл повреждён")
    return target


def app_dir() -> Path:
    return Path(sys.executable).resolve().parent


def can_update() -> bool:
    """Обновляется только собранная программа под Windows, не запуск из исходников."""
    return getattr(sys, "frozen", False) and os.name == "nt"


def prepare(zip_path: Path, root: Path) -> Path:
    """Распаковывает новую версию во временную папку и проверяет, что в ней есть программа."""
    staging = root / "_update" / "new"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(staging)
    # Архив мог быть упакован с папкой CoffeeStock внутри
    if not (staging / "CoffeeStock.exe").exists():
        inner = next((p for p in staging.iterdir() if (p / "CoffeeStock.exe").exists()), None)
        if inner is None:
            raise ValueError("в архиве нет CoffeeStock.exe")
        staging = inner
    return staging


LOG_NAME = "Обновление.log"


def update_script(root: Path, staging: Path, pid: int, version: str = "") -> str:
    """bat-скрипт: дождаться выхода программы, заменить её файлы и запустить её снова.

    Каждый шаг пишется в «Обновление.log» рядом с программой — если что-то пойдёт
    не так, будет видно, на каком шаге.
    """
    log = root / LOG_NAME
    exe = root / "CoffeeStock.exe"
    lines = [
        "@echo off",
        # Новый CoffeeStock.exe не должен принять служебные переменные старого за свои
        "set PYINSTALLER_RESET_ENVIRONMENT=1",
        f'echo обновление до версии {version} > "{log}"',
        "set /a n=0",
        ":wait",
        f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul',
        "if errorlevel 1 goto closed",
        "set /a n+=1",
        "if %n% geq 60 goto closed",
        "ping -n 2 127.0.0.1 >nul",  # пауза 1 с; timeout без консоли не работает
        "goto wait",
        ":closed",
        f'echo программа закрыта >> "{log}"',
    ]
    for i, part in enumerate(PROGRAM_PARTS):
        target = root / part
        remove = f'del /f /q "{target}"' if part.endswith(".exe") else f'rmdir /s /q "{target}"'
        # Файлы могут быть заняты ещё пару секунд после выхода — повторяем до 10 раз
        lines += [
            "set /a r=0",
            f":remove{i}",
            f'if not exist "{target}" goto removed{i}',
            remove,
            f'if not exist "{target}" goto removed{i}',
            "set /a r+=1",
            f"if %r% geq 10 goto removed{i}",
            "ping -n 2 127.0.0.1 >nul",
            f"goto remove{i}",
            f":removed{i}",
        ]
    lines += [
        f'robocopy "{staging}" "{root}" /E /NFL /NDL /NJH /NJS /NP >nul',
        f'if not exist "{exe}" (echo ошибка: после копирования нет CoffeeStock.exe >> "{log}" & goto end)',
        f'echo файлы заменены >> "{log}"',
        f'start "" /D "{root}" "{exe}"',
        f'echo готово >> "{log}"',
        ":end",
        f'rmdir /s /q "{root / "_update"}"',
    ]
    return "\r\n".join(lines) + "\r\n"


def clean_environment() -> dict[str, str]:
    """Окружение для скрипта обновления без служебных переменных PyInstaller."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def finished_update(root: Path) -> str | None:
    """Версия, до которой программа только что обновилась (по «Обновление.log»); лог убирается."""
    log = root / LOG_NAME
    if not log.exists():
        return None
    try:
        lines = [l.strip() for l in log.read_text(encoding="oem" if os.name == "nt" else "utf-8",
                                                    errors="replace").splitlines() if l.strip()]
    except OSError:
        return None
    if not lines or lines[-1] != "готово" or VERSION not in lines[0]:
        return None
    log.unlink(missing_ok=True)
    return VERSION


def install(zip_path: Path, root: Path, db_file: Path, version: str = "") -> None:
    """Готовит замену файлов и запускает скрипт; после этого программу нужно закрыть."""
    staging = prepare(zip_path, root)
    if db_file.exists():
        shutil.copy2(db_file, db_file.with_name(f"coffee.db.до-обновления-{VERSION}.bak"))
    script = root / "_update" / "update.bat"
    # cmd читает bat в OEM-кодировке консоли (cp866) — так пути с русскими буквами не ломаются
    script.write_text(update_script(root, staging, os.getpid(), version),
                      encoding="oem" if os.name == "nt" else "utf-8")
    flags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=flags, close_fds=True, env=clean_environment())

