"""Распознавание текста скана (PDF-картинки) встроенным Tesseract, без интернета.

Tesseract ищется так: путь из настроек → папка tesseract рядом с программой →
системный PATH. В сборке CoffeeStock он лежит в папке tesseract внутри
программы, ставить отдельно ничего не нужно.
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DPI = 300


class OcrUnavailable(Exception):
    pass


def _bundled_dirs() -> list[Path]:
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent / "tesseract")
        if meipass := getattr(sys, "_MEIPASS", None):
            dirs.append(Path(meipass) / "tesseract")
    dirs.append(Path(__file__).resolve().parent.parent / "tesseract")
    return dirs


def find_tesseract(configured: str = "") -> Path | None:
    candidates = []
    if configured:
        p = Path(configured)
        candidates.append(p / "tesseract.exe" if p.is_dir() else p)
    for d in _bundled_dirs():
        candidates += [d / "tesseract.exe", d / "tesseract"]
    for c in candidates:
        if c.is_file():
            return c
    found = shutil.which("tesseract")
    if found:
        return Path(found)
    if os.name == "nt":
        default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if default.is_file():
            return default
    return None


def _run(exe: Path, args: list[str]) -> str:
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW — без мигающей консоли
    env = dict(os.environ)
    tessdata = exe.parent / "tessdata"
    if tessdata.is_dir():
        env["TESSDATA_PREFIX"] = str(tessdata)
    proc = subprocess.run([str(exe), *args], capture_output=True, env=env, timeout=180, **kwargs)
    if proc.returncode != 0:
        raise OcrUnavailable(proc.stderr.decode("utf-8", "replace").strip()[:300] or "ошибка Tesseract")
    return proc.stdout.decode("utf-8", "replace")


def _languages(exe: Path) -> str:
    out = _run(exe, ["--list-langs"])
    langs = {line.strip() for line in out.splitlines()[1:]}
    if "rus" in langs:
        return "rus+eng" if "eng" in langs else "rus"
    raise OcrUnavailable("для Tesseract не установлен русский язык (rus.traineddata)")


def ocr_pdf(path: Path, configured: str = "") -> list[list[dict]]:
    """Слова каждой страницы: [{'text', 'x0', 'x1', 'top', 'bottom'}], координаты в точках PDF."""
    import pypdfium2 as pdfium

    exe = find_tesseract(configured)
    if exe is None:
        raise OcrUnavailable("не найден Tesseract для распознавания сканов")
    lang = _languages(exe)
    scale = DPI / 72
    pages: list[list[dict]] = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for n in range(len(pdf)):
                image = remove_table_lines(pdf[n].render(scale=scale).to_pil().convert("L"))
                png = Path(tmp) / f"p{n}.png"
                image.save(png)
                # psm 11 — «разрозненный текст»: каждое слово отдельно со своими координатами,
                # колонки потом восстанавливаются по шапке таблицы
                tsv = _run(exe, [str(png), "stdout", "-l", lang, "--psm", "11", "tsv"])
                pages.append(_parse_tsv(tsv, scale))
    finally:
        pdf.close()
    return pages


def _long_runs(dark, min_len: int):
    """Маска пикселей, входящих в горизонтальные отрезки длиной не меньше min_len."""
    import numpy as np

    mask = np.zeros_like(dark)
    for i in np.flatnonzero(dark.sum(axis=1) >= min_len):
        edges = np.diff(np.concatenate(([0], dark[i].astype(np.int8), [0])))
        for x0, x1 in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            if x1 - x0 >= min_len:
                mask[i, x0:x1] = True
    return mask


def remove_table_lines(image):
    """Стирает линии таблицы: с ними Tesseract путает буквы и теряет короткие числа."""
    import numpy as np
    from PIL import Image

    pixels = np.array(image)
    dark = pixels < 140
    height, width = dark.shape
    lines = _long_runs(dark, max(width // 15, 40)) | _long_runs(dark.T.copy(), max(height // 40, 40)).T
    pixels[lines] = 255
    return Image.fromarray(pixels)


def _parse_tsv(tsv: str, scale: float) -> list[dict]:
    words = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = (row.get("text") or "").strip()
        if not text or row.get("level") != "5":
            continue
        try:
            if float(row["conf"]) < 0:
                continue
            left, top = int(row["left"]) / scale, int(row["top"]) / scale
            width, height = int(row["width"]) / scale, int(row["height"]) / scale
        except (KeyError, ValueError):
            continue
        words.append({"text": text, "x0": left, "x1": left + width, "top": top, "bottom": top + height})
    return words
