"""Обновление программы без переустановки.

Каждая сборка выкладывается на GitHub в раздел Releases архивом CoffeeStock.zip
с тегом coffee-stock-v1.0.N. Программа сравнивает свою версию с последним
выпуском, скачивает архив и заменяет свои файлы (CoffeeStock.exe, _internal,
tesseract). Данные — coffee.db, Продажи.xlsx, папка «Накладные» — лежат рядом
и не трогаются; перед обновлением база дополнительно копируется в резерв.

Заменить запущенный exe нельзя, поэтому старая программа распаковывает новую
версию в «_update\\new» и запускает её с ключом --finish-update. Новая версия
ждёт, пока старая закроется, копирует себя на место старой (средствами Python —
русские буквы в пути не мешают), запускает программу из обычной папки и выходит.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
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
EXIT_WAIT = 20  # сколько секунд ждать, пока старая версия закроется сама
FINISH_FLAG = "--finish-update"


def clean_environment() -> dict[str, str]:
    """Окружение без служебных переменных PyInstaller: иначе запущенный из программы
    CoffeeStock.exe принимает их за свои и не стартует."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _spawn(args: list[str], cwd: Path) -> None:
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, cwd=str(cwd), env=clean_environment(), creationflags=flags, close_fds=True)


def install(zip_path: Path, root: Path, db_file: Path, version: str = "") -> None:
    """Распаковывает новую версию и запускает её для замены файлов; после этого программу нужно закрыть."""
    staging = prepare(zip_path, root)
    if db_file.exists():
        shutil.copy2(db_file, db_file.with_name(f"coffee.db.до-обновления-{VERSION}.bak"))
    _spawn([str(staging / "CoffeeStock.exe"), FINISH_FLAG, str(root), str(os.getpid()), version], staging)


def wait_for_exit(pid: int, timeout: float = 60) -> bool:
    """Ждёт, пока процесс завершится (не дольше timeout секунд). True — процесс завершился."""
    deadline = time.monotonic() + timeout
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return True  # процесса уже нет
        try:
            return kernel32.WaitForSingleObject(handle, int(timeout * 1000)) == 0  # WAIT_OBJECT_0
        finally:
            kernel32.CloseHandle(handle)
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.2)
    return not _alive(pid)


def _alive(pid: int) -> bool:
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)  # свой дочерний процесс-«зомби» тоже считается завершённым
        if reaped:
            return False
    except (ChildProcessError, OSError):
        pass
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate(pid: int) -> None:
    """Принудительно закрывает процесс (старая версия программы, которая не закрылась сама)."""
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x0001 | 0x00100000, False, pid)  # PROCESS_TERMINATE | SYNCHRONIZE
        if handle:
            kernel32.TerminateProcess(handle, 1)
            kernel32.CloseHandle(handle)
        return
    import signal

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def _remove(path: Path, attempts: int = 10) -> None:
    """Удаляет файл или папку; файлы могут быть заняты ещё пару секунд после выхода программы."""
    for _ in range(attempts):
        if not path.exists():
            return
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError:
            time.sleep(1)
    if path.exists():
        raise OSError(f"не удалось удалить {path}")


def finish_update(root: Path, staging: Path, pid: int, version: str = "") -> None:
    """Выполняется новой версией из «_update\\new»: заменить файлы программы и запустить её."""
    log = root / LOG_NAME

    def note(text: str) -> None:
        with open(log, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    log.write_text(f"обновление до версии {version}\n", encoding="utf-8")
    try:
        if not wait_for_exit(pid, EXIT_WAIT):
            note("программа не закрылась сама — закрываю её")
            terminate(pid)
            wait_for_exit(pid, 10)
        note("программа закрыта")
        for part in PROGRAM_PARTS:
            _remove(root / part)
        for item in staging.iterdir():
            target = root / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
        note("файлы заменены")
        _spawn([str(root / "CoffeeStock.exe")], root)
        note("готово")
    except Exception as e:  # noqa: BLE001 — всё записать в лог, окна у этого процесса нет
        note(f"ошибка: {e}")


def finish_from_args(argv: list[str]) -> bool:
    """Если программа запущена с --finish-update — завершить обновление и вернуть True (окно не нужно)."""
    if FINISH_FLAG not in argv:
        return False
    i = argv.index(FINISH_FLAG)
    root, pid = Path(argv[i + 1]), int(argv[i + 2])
    version = argv[i + 3] if len(argv) > i + 3 else ""
    finish_update(root, app_dir(), pid, version)
    return True


def cleanup_after_update(root: Path) -> None:
    """Удаляет временную папку обновления (если программа запущена не из неё)."""
    update_dir = root / "_update"
    if update_dir.exists() and update_dir not in app_dir().parents:
        shutil.rmtree(update_dir, ignore_errors=True)


def finished_update(root: Path) -> str | None:
    """Версия, до которой программа только что обновилась (по «Обновление.log»); лог убирается."""
    log = root / LOG_NAME
    if not log.exists():
        return None
    try:
        lines = [l.strip() for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    except OSError:
        return None
    if not lines or lines[-1] != "готово" or VERSION not in lines[0]:
        return None
    log.unlink(missing_ok=True)
    return VERSION


def failed_update(root: Path) -> str | None:
    """Текст «Обновление.log», если обновление закончилось ошибкой (лог убирается)."""
    log = root / LOG_NAME
    if not log.exists():
        return None
    try:
        text = log.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or lines[-1] == "готово" or not any(l.startswith("ошибка") for l in lines):
        return None
    log.unlink(missing_ok=True)
    return text
