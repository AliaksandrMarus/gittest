"""Мини-библиотека для чертежей в SVG: лист А3 с рамкой и штампом,
вид модели в масштабе, размерные цепочки, оси, отметки уровней, таблицы.

Все координаты листа — в миллиметрах. Координаты модели — в миллиметрах
натуры, ось Y модели направлена вверх (на листе — вниз).
"""
import math
from html import escape

FONT = "DejaVu Sans, Arial, sans-serif"

PROJECT = "ДОМ-9х12"
OBJECT_NAME = ["Одноэтажный жилой дом 9×12 м", "г. Бобруйск, Могилёвская обл."]
STAGE = "ЭП"


def f(v):
    """Короткая запись числа для SVG."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


DEFS = """
<defs>
 <pattern id="hBlock" width="1.6" height="1.6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <line x1="0" y1="0" x2="0" y2="1.6" stroke="#000" stroke-width="0.13"/></pattern>
 <pattern id="hBlockGray" width="1.6" height="1.6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <line x1="0" y1="0" x2="0" y2="1.6" stroke="#9a9a9a" stroke-width="0.13"/></pattern>
 <pattern id="hPart" width="1.2" height="1.2" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
  <line x1="0" y1="0" x2="0" y2="1.2" stroke="#000" stroke-width="0.1"/></pattern>
 <pattern id="hConcrete" width="4" height="4" patternUnits="userSpaceOnUse">
  <rect width="4" height="4" fill="#f2f2f2"/>
  <circle cx="0.8" cy="0.9" r="0.22" fill="#000"/><circle cx="2.9" cy="2.6" r="0.18" fill="#000"/>
  <path d="M2.2 0.6 l0.7 0.2 l-0.5 0.5 z" fill="none" stroke="#000" stroke-width="0.12"/>
  <path d="M0.6 2.8 l0.8 0.1 l-0.4 0.6 z" fill="none" stroke="#000" stroke-width="0.12"/></pattern>
 <pattern id="hSand" width="2" height="2" patternUnits="userSpaceOnUse">
  <circle cx="0.5" cy="0.5" r="0.14" fill="#555"/><circle cx="1.5" cy="1.4" r="0.12" fill="#555"/></pattern>
 <pattern id="hSoil" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <line x1="0" y1="0" x2="0" y2="3" stroke="#000" stroke-width="0.15"/>
  <line x1="1" y1="0" x2="1" y2="3" stroke="#000" stroke-width="0.15"/></pattern>
 <pattern id="hInsul" width="2.4" height="2.4" patternUnits="userSpaceOnUse">
  <rect width="2.4" height="2.4" fill="#fff8d6"/>
  <path d="M0 2.0 L0.6 0.4 L1.2 2.0 L1.8 0.4 L2.4 2.0" fill="none" stroke="#8a7a2a" stroke-width="0.12"/></pattern>
 <pattern id="hWood" width="2" height="2" patternUnits="userSpaceOnUse">
  <rect width="2" height="2" fill="#f3e2c3"/>
  <path d="M0 1 Q0.5 0.5 1 1 T2 1" fill="none" stroke="#9b7a46" stroke-width="0.12"/></pattern>
 <pattern id="hGravel" width="3" height="3" patternUnits="userSpaceOnUse">
  <rect width="3" height="3" fill="#ececec"/>
  <circle cx="0.8" cy="0.8" r="0.5" fill="none" stroke="#333" stroke-width="0.12"/>
  <circle cx="2.2" cy="2.1" r="0.6" fill="none" stroke="#333" stroke-width="0.12"/></pattern>
 <pattern id="hPlaster" width="1" height="1" patternUnits="userSpaceOnUse">
  <rect width="1" height="1" fill="#e9e9e9"/><circle cx="0.5" cy="0.5" r="0.1" fill="#777"/></pattern>
 <pattern id="hRoof" width="1.4" height="1.4" patternUnits="userSpaceOnUse" patternTransform="rotate(90)">
  <line x1="0" y1="0" x2="0" y2="1.4" stroke="#7b3b30" stroke-width="0.12"/></pattern>
 <pattern id="hBoard" width="1.6" height="10" patternUnits="userSpaceOnUse">
  <rect width="1.6" height="10" fill="#f6efe2"/>
  <line x1="0" y1="0" x2="0" y2="10" stroke="#a08560" stroke-width="0.12"/></pattern>
 <pattern id="hTile" width="3" height="1.6" patternUnits="userSpaceOnUse">
  <rect width="3" height="1.6" fill="#c9cdd2"/>
  <path d="M0 1.6 L3 1.6 M0 0 L0 1.6" stroke="#6c737b" stroke-width="0.12"/></pattern>
 <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
  <path d="M0 0 L10 5 L0 10 z" fill="#000"/></marker>
 <marker id="arrB" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
  <path d="M0 0 L10 5 L0 10 z" fill="#1f5fbf"/></marker>
 <marker id="arrK" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
  <path d="M0 0 L10 5 L0 10 z" fill="#7a4a12"/></marker>
</defs>
"""


class Sheet:
    W, H = 420, 297

    def __init__(self, code, title, num, total, scale=""):
        self.code, self.title, self.num, self.total, self.scale = code, title, num, total, scale
        self.el = []

    # --- примитивы -----------------------------------------------------
    def add(self, s):
        self.el.append(s)

    @staticmethod
    def _st(w, c, dash=None, fill="none", cap=None, extra=""):
        s = f'stroke="{c}" stroke-width="{f(w)}" fill="{fill}"'
        if dash:
            s += f' stroke-dasharray="{dash}"'
        if cap:
            s += f' stroke-linecap="{cap}"'
        return s + extra

    def line(self, x1, y1, x2, y2, w=0.25, c="#000", dash=None, cap=None, marker=None):
        m = ""
        if marker:
            m = f' marker-end="url(#{marker})"'
        self.add(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" {self._st(w, c, dash, cap=cap)}{m}/>')

    def pline(self, pts, w=0.25, c="#000", dash=None, fill="none", close=False, marker=None, join=None):
        d = " ".join(f"{f(x)},{f(y)}" for x, y in pts)
        tag = "polygon" if close else "polyline"
        m = f' marker-end="url(#{marker})"' if marker else ""
        j = f' stroke-linejoin="{join}"' if join else ""
        self.add(f'<{tag} points="{d}" {self._st(w, c, dash, fill)}{m}{j}/>')

    def path(self, d, w=0.25, c="#000", fill="none", dash=None, extra=""):
        self.add(f'<path d="{d}" {self._st(w, c, dash, fill)}{extra}/>')

    def rect(self, x, y, w, h, sw=0.25, c="#000", fill="none", dash=None, rx=0):
        if w < 0:
            x, w = x + w, -w
        if h < 0:
            y, h = y + h, -h
        r = f' rx="{f(rx)}"' if rx else ""
        self.add(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"{r} {self._st(sw, c, dash, fill)}/>')

    def circle(self, cx, cy, r, sw=0.25, c="#000", fill="none", dash=None):
        self.add(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" {self._st(sw, c, dash, fill)}/>')

    def text(self, x, y, s, size=2.5, anchor="start", weight="normal", c="#000", rot=0, italic=False, bg=False):
        t = f' transform="rotate({f(rot)} {f(x)} {f(y)})"' if rot else ""
        it = ' font-style="italic"' if italic else ""
        if bg:
            # подложка под текст, чтобы надпись читалась поверх линий
            wdt = len(str(s)) * size * 0.58
            bx = {"start": x, "middle": x - wdt / 2, "end": x - wdt}[anchor]
            if not rot:
                self.rect(bx - 0.4, y - size * 0.85, wdt + 0.8, size * 1.1, sw=0, fill="#fff")
        self.add(
            f'<text x="{f(x)}" y="{f(y)}" font-family="{FONT}" font-size="{f(size)}" text-anchor="{anchor}" '
            f'font-weight="{weight}" fill="{c}"{it}{t}>{escape(str(s))}</text>'
        )

    def mtext(self, x, y, lines, size=2.5, lh=None, **kw):
        lh = lh or size * 1.35
        for i, s in enumerate(lines):
            self.text(x, y + i * lh, s, size, **kw)
        return y + len(lines) * lh

    def wrap(self, x, y, s, width, size=2.3, lh=None, **kw):
        """Перенос текста по ширине (оценочно по среднему размеру знака)."""
        per = max(8, int(width / (size * 0.63)))
        out, cur = [], ""
        for word in s.split():
            if len(cur) + len(word) + 1 > per and cur:
                out.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}".strip()
        if cur:
            out.append(cur)
        return self.mtext(x, y, out, size, lh, **kw)

    def table(self, x, y, cols, rows, rh=5.0, size=2.2, header=1, aligns=None, rhs=None, bold_rows=()):
        """Таблица: cols — ширины колонок, rows — списки строк (ячейка может быть списком строк)."""
        tw = sum(cols)
        cy = y
        for ri, row in enumerate(rows):
            h = rhs[ri] if rhs else rh
            self.rect(x, cy, tw, h, sw=0.25 if ri >= header else 0.4)
            cx = x
            for ci, cell in enumerate(row):
                w = cols[ci]
                if ci:
                    self.line(cx, cy, cx, cy + h, 0.25)
                lines = cell if isinstance(cell, list) else [cell]
                al = "middle" if ri < header else (aligns[ci] if aligns else "start")
                tx = {"start": cx + 1.0, "middle": cx + w / 2, "end": cx + w - 1.0}[al]
                n = len(lines)
                lh = size * 1.22
                ty = cy + h / 2 - (n - 1) * lh / 2 + size * 0.36
                wt = "bold" if (ri < header or ri in bold_rows) else "normal"
                for li, s in enumerate(lines):
                    self.text(tx, ty + li * lh, s, size, anchor=al, weight=wt)
                cx += w
            cy += h
        return cy

    def heading(self, x, y, s, size=3.5, underline=True, anchor="start"):
        self.text(x, y, s, size, anchor=anchor, weight="bold")
        if underline:
            wdt = len(s) * size * 0.6
            x0 = {"start": x, "middle": x - wdt / 2, "end": x - wdt}[anchor]
            self.line(x0, y + 1.0, x0 + wdt, y + 1.0, 0.35)

    # --- рамка и штамп ---------------------------------------------------
    def frame(self):
        self.rect(0.2, 0.2, self.W - 0.4, self.H - 0.4, sw=0.15, c="#bbb")
        self.rect(20, 5, self.W - 25, self.H - 10, sw=0.7)
        x0, y0 = 230, 237
        self.rect(x0, y0, 185, 55, sw=0.7, fill="#fff")
        # левая часть: подписи
        cw = [7, 10, 10, 15, 13, 10]
        for i in range(1, 11):
            self.line(x0, y0 + 5 * i, x0 + 65, y0 + 5 * i, 0.25 if i not in (2,) else 0.5)
        cx = x0
        for w in cw[:-1]:
            cx += w
            self.line(cx, y0, cx, y0 + 15, 0.25)
        self.line(x0 + 17, y0 + 15, x0 + 17, y0 + 55, 0.25)
        self.line(x0 + 42, y0 + 15, x0 + 42, y0 + 55, 0.25)
        self.line(x0 + 55, y0 + 15, x0 + 55, y0 + 55, 0.25)
        heads = ["Изм.", "Кол.", "Лист", "№док", "Подп.", "Дата"]
        cx = x0
        for w, h in zip(cw, heads):
            self.text(cx + w / 2, y0 + 13.8, h, 1.8, anchor="middle")
            cx += w
        roles = [("Разраб.", "Claude"), ("Пров.", ""), ("ГИП", ""), ("Н.контр.", ""), ("Утв.", "")]
        for i, (r, n) in enumerate(roles):
            yy = y0 + 18.8 + 5 * i
            self.text(x0 + 1, yy, r, 1.9)
            self.text(x0 + 18, yy, n, 1.9)
            if i == 0:
                self.text(x0 + 55.6, yy, "10.26", 1.7)
        self.line(x0 + 65, y0, x0 + 65, y0 + 55, 0.7)
        # правая часть
        rx = x0 + 65
        self.line(rx, y0 + 15, rx + 120, y0 + 15, 0.7)
        self.line(rx, y0 + 40, rx + 120, y0 + 40, 0.7)
        self.line(rx + 70, y0 + 15, rx + 70, y0 + 55, 0.7)
        self.text(rx + 60, y0 + 9.5, f"{PROJECT}-{self.code.split('-')[0]}", 4.5, anchor="middle", weight="bold")
        self.mtext(rx + 35, y0 + 25, OBJECT_NAME, 2.6, anchor="middle")
        # стадия / лист / листов
        self.line(rx + 70, y0 + 20, rx + 120, y0 + 20, 0.25)
        self.line(rx + 70, y0 + 27, rx + 120, y0 + 27, 0.5)
        self.line(rx + 85, y0 + 15, rx + 85, y0 + 27, 0.25)
        self.line(rx + 102, y0 + 15, rx + 102, y0 + 27, 0.25)
        self.text(rx + 77.5, y0 + 18.6, "Стадия", 1.8, anchor="middle")
        self.text(rx + 93.5, y0 + 18.6, "Лист", 1.8, anchor="middle")
        self.text(rx + 111, y0 + 18.6, "Листов", 1.8, anchor="middle")
        self.text(rx + 77.5, y0 + 25, STAGE, 2.6, anchor="middle")
        self.text(rx + 93.5, y0 + 25, str(self.num), 2.6, anchor="middle")
        self.text(rx + 111, y0 + 25, str(self.total), 2.6, anchor="middle")
        self.mtext(rx + 95, y0 + 31.5, ["Эскизный проект.", "Строительство — после", "привязки и экспертизы"], 1.9,
                   anchor="middle")
        # наименование листа
        tl = self.title_lines()
        self.mtext(rx + 35, y0 + 47.5 - (len(tl) - 1) * 1.6, tl, 2.6, lh=3.3, anchor="middle", weight="bold")
        self.mtext(rx + 95, y0 + 46, [f"Лист {self.code}", f"М {self.scale}" if self.scale else ""], 2.2, anchor="middle")

    def title_lines(self):
        words, out, cur = self.title.split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 32 and cur:
                out.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        out.append(cur)
        return out

    def svg(self):
        body = "\n".join(self.el)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.W}mm" height="{self.H}mm" '
            f'viewBox="0 0 {self.W} {self.H}">\n<title>{escape(self.code)} — {escape(self.title)}</title>'
            f"{DEFS}\n<rect width=\"{self.W}\" height=\"{self.H}\" fill=\"#fff\"/>\n{body}\n</svg>\n"
        )


class View:
    """Вид модели на листе: ox, oy — положение начала координат модели на листе, s — масштаб (50 = 1:50)."""

    def __init__(self, sh, ox, oy, s):
        self.sh, self.ox, self.oy, self.s = sh, ox, oy, s

    def X(self, x):
        return self.ox + x / self.s

    def Y(self, y):
        return self.oy - y / self.s

    def L(self, v):
        return v / self.s

    def P(self, pts):
        return [(self.X(x), self.Y(y)) for x, y in pts]

    def rect(self, x1, y1, x2, y2, **kw):
        a, b = sorted((x1, x2)), sorted((y1, y2))
        self.sh.rect(self.X(a[0]), self.Y(b[1]), self.L(a[1] - a[0]), self.L(b[1] - b[0]), **kw)

    def line(self, x1, y1, x2, y2, **kw):
        self.sh.line(self.X(x1), self.Y(y1), self.X(x2), self.Y(y2), **kw)

    def pline(self, pts, **kw):
        self.sh.pline(self.P(pts), **kw)

    def circle(self, x, y, r_sheet, **kw):
        self.sh.circle(self.X(x), self.Y(y), r_sheet, **kw)

    def text(self, x, y, s, size=2.5, **kw):
        self.sh.text(self.X(x), self.Y(y), s, size, **kw)

    # --- размеры ---------------------------------------------------------
    def _tick(self, x, y):
        self.sh.line(x - 0.9, y + 0.9, x + 0.9, y - 0.9, 0.45)

    def dimh(self, xs, ys, ext=None, size=2.2, prefix=""):
        """Горизонтальная размерная цепочка на высоте ys (лист). ext — y листа, откуда тянуть выносные."""
        sh = self.sh
        pts = [self.X(x) for x in xs]
        sh.line(pts[0] - 1.5, ys, pts[-1] + 1.5, ys, 0.2)
        for x in pts:
            e0 = ext if ext is not None else ys + 1.8
            sh.line(x, e0, x, ys + (1.5 if e0 < ys else -1.5), 0.15)
            self._tick(x, ys)
        for a, b, xa, xb in zip(pts, pts[1:], xs, xs[1:]):
            v = abs(xb - xa)
            lab = f"{prefix}{v:g}"
            room = (b - a) / (len(lab) * 0.62)
            sz = size if room >= size else max(1.4, room)
            sh.text((a + b) / 2, ys - 0.7, lab, sz, anchor="middle")

    def dimv(self, ys, xs, ext=None, size=2.2):
        sh = self.sh
        pts = [self.Y(y) for y in ys]
        top, bot = min(pts), max(pts)
        sh.line(xs, top - 1.5, xs, bot + 1.5, 0.2)
        for y in pts:
            e0 = ext if ext is not None else xs + 1.8
            sh.line(e0, y, xs + (1.5 if e0 < xs else -1.5), y, 0.15)
            self._tick(xs, y)
        for a, b, ya, yb in zip(pts, pts[1:], ys, ys[1:]):
            v = abs(yb - ya)
            lab = f"{v:g}"
            room = abs(b - a) / (len(lab) * 0.62)
            sz = size if room >= size else max(1.4, room)
            sh.text(xs - 0.7, (a + b) / 2, lab, sz, anchor="middle", rot=-90)

    # --- оси -------------------------------------------------------------
    def axis_x(self, x, label, y0s, y1s, r=3.2, ends=("top", "bottom")):
        """Вертикальная координационная ось (по X модели) между y листа y0s..y1s."""
        X = self.X(x)
        self.sh.line(X, y0s, X, y1s, 0.18, dash="6 1.2 1 1.2")
        for e in ends:
            cy = y0s - r if e == "top" else y1s + r
            self.sh.circle(X, cy, r, 0.3, fill="#fff")
            self.sh.text(X, cy + 1.1, label, 3.0, anchor="middle")

    def axis_y(self, y, label, x0s, x1s, r=3.2, ends=("left", "right")):
        Y = self.Y(y)
        self.sh.line(x0s, Y, x1s, Y, 0.18, dash="6 1.2 1 1.2")
        for e in ends:
            cx = x0s - r if e == "left" else x1s + r
            self.sh.circle(cx, Y, r, 0.3, fill="#fff")
            self.sh.text(cx, Y + 1.1, label, 3.0, anchor="middle")

    # --- отметка уровня --------------------------------------------------
    def level(self, xs, y, label, side="right", size=2.2, shelf=13):
        """Отметка: xs — x листа точки, y — уровень модели (мм)."""
        sh = self.sh
        Y = self.Y(y)
        sh.pline([(xs - 1.4, Y - 1.6), (xs, Y), (xs + 1.4, Y - 1.6)], 0.3)
        sh.line(xs - 1.4, Y - 1.6, xs + 1.4, Y - 1.6, 0.3)
        sh.line(xs, Y, xs, Y - 3.8, 0.2)
        x2 = xs + shelf if side == "right" else xs - shelf
        sh.line(xs, Y - 3.8, x2, Y - 3.8, 0.2)
        sh.text((xs + 0.8) if side == "right" else (xs - 0.8), Y - 4.4, label, size,
                anchor="start" if side == "right" else "end")


def lvl(v):
    """Отметка в метрах в формате +2.450 / -0.600 / ±0.000 (v — мм)."""
    if abs(v) < 0.5:
        return "±0.000"
    return f"{'+' if v > 0 else '−'}{abs(v) / 1000:.3f}"


def arc_pts(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
