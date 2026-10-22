"""Распознавание текста скана (PDF-картинки) встроенным Tesseract, без интернета.

Tesseract ищется так: путь из настроек → папка tesseract рядом с программой →
системный PATH. В сборке CoffeeStock он лежит в папке tesseract внутри
программы, ставить отдельно ничего не нужно.
"""

from __future__ import annotations

import csv
import re
import io
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DPI = 400


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


@dataclass
class OcrPage:
    words: list[dict]  # {'text', 'x0', 'x1', 'top', 'bottom'} в точках PDF
    vlines: list[tuple[float, float, float]]  # вертикальные линии таблицы: (x, верх, низ)


def ocr_pdf(path: Path, configured: str = "") -> list[OcrPage]:
    """Распознаёт каждую страницу скана: слова с координатами и вертикальные линии таблицы."""
    import pypdfium2 as pdfium

    exe = find_tesseract(configured)
    if exe is None:
        raise OcrUnavailable("не найден Tesseract для распознавания сканов")
    lang = _languages(exe)
    scale = DPI / 72
    pages: list[OcrPage] = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for n in range(len(pdf)):
                image, vlines = remove_table_lines(deskew(pdf[n].render(scale=scale).to_pil().convert("L")))
                png = Path(tmp) / f"p{n}.png"
                image.save(png)
                # psm 11 — «разрозненный текст»: каждое слово отдельно со своими координатами,
                # колонки потом восстанавливаются по линиям и шапке таблицы
                tsv = _run(exe, [str(png), "stdout", "-l", lang, "--psm", "11", "tsv"])
                pages.append(OcrPage(_parse_tsv(tsv, scale),
                                     [(x / scale, y0 / scale, y1 / scale) for x, y0, y1 in vlines]))
    finally:
        pdf.close()
    return pages


def skew_angle(image) -> float:
    """Угол перекоса скана в градусах: при верном повороте строки дают самые резкие пики яркости."""
    import numpy as np

    small = image.copy()
    small.thumbnail((1200, 1200))
    best_angle, best_score = 0.0, -1.0
    for angle in np.arange(-3, 3.01, 0.1):
        rotated = np.array(small.rotate(angle, fillcolor=255)) < 160
        profile = rotated.sum(axis=1).astype(float)
        score = float(np.sum(np.diff(profile) ** 2))
        if score > best_score:
            best_angle, best_score = float(angle), score
    # Уточнение шагом 0,02° вокруг лучшего
    for angle in np.arange(best_angle - 0.1, best_angle + 0.101, 0.02):
        rotated = np.array(small.rotate(angle, fillcolor=255)) < 160
        profile = rotated.sum(axis=1).astype(float)
        score = float(np.sum(np.diff(profile) ** 2))
        if score > best_score:
            best_angle, best_score = float(angle), score
    return best_angle


def deskew(image):
    """Выравнивает перекошенный скан, иначе линии таблицы и строки идут наискосок."""
    from PIL import Image

    angle = skew_angle(image)
    if abs(angle) < 0.05:
        return image
    return image.rotate(angle, resample=Image.BICUBIC, fillcolor=255)


def _runs(row, min_len: int, gap: int = 0):
    """Отрезки [x0, x1) тёмных пикселей строки длиной ≥ min_len; разрывы до gap склеиваются."""
    import numpy as np

    xs = np.flatnonzero(row)
    if len(xs) < (min_len if gap == 0 else min_len // 4):
        return []
    breaks = np.flatnonzero(np.diff(xs) > gap + 1)
    starts = np.concatenate(([xs[0]], xs[breaks + 1]))
    ends = np.concatenate((xs[breaks], [xs[-1]])) + 1
    return [(a, b) for a, b in zip(starts, ends) if b - a >= min_len]


def _long_runs(dark, min_len: int, gap: int = 0):
    """Маска пикселей, входящих в горизонтальные отрезки длиной не меньше min_len."""
    import numpy as np

    mask = np.zeros_like(dark)
    for i in range(dark.shape[0]):
        for a, b in _runs(dark[i], min_len, gap):
            mask[i, a:b] = True
    return mask


def _thin_bands(mask, max_height: int):
    """Оставляет только тонкие (по высоте) полосы маски — линии, а не строки текста."""
    import numpy as np

    rows = np.flatnonzero(mask.any(axis=1))
    keep = np.zeros_like(mask)
    if len(rows) == 0:
        return keep
    bands = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    for band in bands:
        if len(band) <= max_height:
            keep[band] = mask[band]
    return keep


def remove_table_lines(image):
    """Стирает линии таблицы (сплошные и пунктирные) и возвращает вертикальные линии.

    С линиями Tesseract путает буквы, а пунктир между строками ТТН читает как
    «текст-мусор». Вертикальные линии нужны, чтобы разделить колонки шапки,
    подписи которых стоят вплотную друг к другу.
    """
    import numpy as np
    from PIL import Image

    pixels = np.array(image)
    # Тонкие линии после поворота и сглаживания серые — для их поиска порог мягче, чем для текста
    dark = pixels < 175
    height, width = dark.shape
    horizontal = _long_runs(dark, max(width // 15, 40))
    # Пунктир: точки с промежутками; склеиваем разрывы и берём только тонкие полосы
    dotted = _thin_bands(_long_runs(dark & ~horizontal, max(width // 6, 60), gap=12), max_height=8)
    vertical_t = _long_runs(dark.T.copy(), max(height // 40, 40))
    # Края точек и линий светлее порога — стираем полосу с запасом ±2 пикселя
    erase = _grow(horizontal | dotted, axis=0) | _grow(vertical_t.T, axis=1)
    pixels[erase & (pixels < 235)] = 255
    # Светлый защитный узор бланка (сетка, «гильош») — в белый, текст заметно темнее
    pixels[pixels > 185] = 255

    vlines = []
    for x in np.flatnonzero(vertical_t.any(axis=1)):
        for a, b in _runs(vertical_t[x], max(height // 40, 40)):
            vlines.append((int(x), int(a), int(b)))
    return Image.fromarray(pixels), _merge_vlines(vlines)


def _grow(mask, axis: int, by: int = 2):
    """Расширяет маску на by пикселей вдоль оси (0 — вверх/вниз, 1 — влево/вправо)."""
    import numpy as np

    out = mask.copy()
    for shift in range(1, by + 1):
        out |= np.roll(mask, shift, axis=axis) | np.roll(mask, -shift, axis=axis)
    return out


def _merge_vlines(vlines: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Соседние пиксельные столбцы одной толстой линии — в одну линию."""
    merged: list[list[int]] = []
    for x, a, b in sorted(vlines):
        for m in merged:
            if abs(m[0] - x) <= 6 and a <= m[2] + 10 and b >= m[1] - 10:
                m[1], m[2] = min(m[1], a), max(m[2], b)
                break
        else:
            merged.append([x, a, b])
    return [tuple(m) for m in merged]


# Латинские буквы, неотличимые от русских на скане
LOOKALIKES = str.maketrans("aceknopxyABCEHKMOPTX", "асекпорхуАВСЕНКМОРТХ")
LOOKALIKE_SET = set("aceknopxyABCEHKMOPTX")


def fix_lookalikes(text: str) -> str:
    """«Caxap-necok» → «Сахар-песок»: слово целиком из латинских двойников — русское.

    Слова, где есть буквы без русского двойника (Lavazza, Crema), не трогаем.
    """
    def fix(m: re.Match) -> str:
        word = m.group(0)
        return word.translate(LOOKALIKES) if len(word) >= 3 and set(word) <= LOOKALIKE_SET else word
    return re.sub(r"[A-Za-z]+", fix, text)


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
        words.append({"text": fix_lookalikes(text), "x0": left, "x1": left + width, "top": top, "bottom": top + height})
    return words
