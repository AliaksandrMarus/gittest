"""Обновление программы без переустановки.

Новая версия берётся из Releases репозитория на GitHub (github.com открывается
из Беларуси без VPN). Программа скачивает новый .exe (или архив папочной
версии), закрывается, маленький скрипт PowerShell подменяет файлы и запускает
программу снова. Настройки, база и папки тендеров лежат в «Документы\\ТендерАгент»
и при обновлении не трогаются.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import APP_VERSION

REPO = "AliaksandrMarus/gittest"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
TAG_PREFIX = "ta-v"
EXE_ASSET = "TenderAgent.exe"
ZIP_ASSET = "TenderAgent-folder.zip"


@dataclass
class Release:
    version: str
    notes: str
    exe_url: str
    zip_url: str
    page_url: str


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in nums[:4]) or (0,)


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    return parse_version(remote) > parse_version(local)


def check(timeout: int = 15) -> Release | None:
    """Последний выпуск, если он новее установленного; иначе None."""
    r = requests.get(API_LATEST, timeout=timeout, headers={"Accept": "application/vnd.github+json",
                                                         "User-Agent": "TenderAgent"})
    r.raise_for_status()
    data = r.json()
    tag = data.get("tag_name", "")
    if not tag.startswith(TAG_PREFIX):
        return None  # выпуски старого формата (до встроенного обновления)
    version = tag[len(TAG_PREFIX):]
    if not is_newer(version):
        return None
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    return Release(version=version, notes=(data.get("body") or "").strip(),
                   exe_url=assets.get(EXE_ASSET, ""), zip_url=assets.get(ZIP_ASSET, ""),
                   page_url=data.get("html_url", ""))


def install_kind() -> str:
    """«onefile» — один .exe; «folder» — папочная версия; «source» — запуск из исходников."""
    if not getattr(sys, "frozen", False):
        return "source"
    exe_dir = Path(sys.executable).resolve().parent
    meipass = Path(getattr(sys, "_MEIPASS", exe_dir)).resolve()
    # папочная сборка PyInstaller: файлы рядом с .exe или в его подпапке _internal
    return "folder" if meipass in (exe_dir, exe_dir / "_internal") else "onefile"


def download(url: str, dest: Path, progress=None) -> Path:
    with requests.get(url, stream=True, timeout=60, headers={"User-Agent": "TenderAgent"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(256 * 1024):
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(int(done * 100 / total))
    return dest


def _ps_quote(p: str | Path) -> str:
    return "'" + str(p).replace("'", "''") + "'"


def apply_and_restart(rel: Release, progress=None) -> None:
    """Скачать обновление и запланировать замену файлов после выхода программы.
    После вызова программа должна закрыться (QApplication.quit())."""
    kind = install_kind()
    if kind == "source":
        raise RuntimeError("Программа запущена из исходников — обновите их через git pull.")
    tmp = Path(tempfile.mkdtemp(prefix="TenderAgentUpdate_"))
    exe = Path(sys.executable).resolve()
    pid = os.getpid()
    if kind == "onefile":
        if not rel.exe_url:
            raise RuntimeError("В выпуске нет файла TenderAgent.exe")
        new = download(rel.exe_url, tmp / "new.exe", progress)
        body = f"""
$target = {_ps_quote(exe)}
$new = {_ps_quote(new)}
for ($i = 0; $i -lt 60; $i++) {{
  try {{ Copy-Item -LiteralPath $new -Destination $target -Force -ErrorAction Stop; break }}
  catch {{ Start-Sleep -Milliseconds 500 }}
}}
Start-Process -FilePath $target
"""
    else:
        if not rel.zip_url:
            raise RuntimeError("В выпуске нет архива TenderAgent-folder.zip")
        z = download(rel.zip_url, tmp / "new.zip", progress)
        app_dir = exe.parent
        body = f"""
$dir = {_ps_quote(app_dir)}
$exe = {_ps_quote(exe)}
$tmp = {_ps_quote(tmp / "x")}
Expand-Archive -LiteralPath {_ps_quote(z)} -DestinationPath $tmp -Force
$src = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
if (-not $src) {{ $src = Get-Item -LiteralPath $tmp }}
for ($i = 0; $i -lt 60; $i++) {{
  try {{ Copy-Item -Path (Join-Path $src.FullName '*') -Destination $dir -Recurse -Force -ErrorAction Stop; break }}
  catch {{ Start-Sleep -Milliseconds 500 }}
}}
Start-Process -FilePath $exe
"""
    script = tmp / "update.ps1"
    script.write_text(
        f"$ErrorActionPreference = 'Continue'\n"
        f"Wait-Process -Id {pid} -Timeout 60 -ErrorAction SilentlyContinue\n"
        f"Start-Sleep -Milliseconds 700\n{body}",
        encoding="utf-8-sig",  # BOM — чтобы PowerShell правильно прочитал кириллицу в путях
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
         "-File", str(script)],
        creationflags=flags, close_fds=True,
    )
