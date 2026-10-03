"""Генерация комплекта чертежей дома 9×12 м в SVG (лист А3).

Запуск:  python3 build.py   → ../sheets/*.svg
"""
import math
import os

import house as H
from drawing import Sheet, View, lvl, arc_pts, f

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sheets")

SHEETS = [
    ("ОД", "Общие данные", ""),
    ("ГП", "Схема планировочной организации участка", "1:200"),
    ("АР-1", "План этажа. Экспликация помещений", "1:50"),
    ("АР-2", "План стен. Ведомости проёмов и перемычек", "1:100"),
    ("АР-3", "Разрез 1-1. Составы конструкций. Ведомость отделки", "1:50"),
    ("АР-4", "Фасады. План кровли", "1:100"),
    ("КЖ-1", "Фундаменты. План, сечения, спецификация", "1:100; 1:20"),
    ("ЭО-1", "План электрооборудования и освещения", "1:50"),
    ("ЭО-2", "Однолинейная схема ЩР. Заземление", "—"),
    ("ВК-1", "План сетей водопровода и канализации", "1:50"),
    ("ВК-2", "Схемы водопровода и канализации. Септик", "б/м"),
]
FILES = ["00-OD", "01-GP-uchastok", "02-AR1-plan", "03-AR2-steny", "04-AR3-razrez", "05-AR4-fasady",
         "06-KZh1-fundament", "07-EO1-elektrika-plan", "08-EO2-shema-ShchR",
         "09-VK1-voda-kanalizaciya", "10-VK2-shemy-septik"]

BLUE, RED, BROWN, ORANGE, GREEN = "#1f5fbf", "#d0342c", "#7a4a12", "#c26b00", "#2e7d32"


def new_sheet(i):
    code, title, scale = SHEETS[i]
    return Sheet(code, title, i + 1, len(SHEETS), scale)


# ======================================================================
# Общая основа плана
# ======================================================================
def plan_base(v, mode="ar", fixtures=True):
    sh = v.sh
    eng = mode == "eng"
    col = "#8a8a8a" if eng else "#000"
    sw = 0.3 if eng else 0.55
    fo = "#e4e4e4" if eng else "url(#hBlock)"
    fb = "#e4e4e4" if eng else "url(#hBlock)"
    fp = "#efefef" if eng else "url(#hPart)"
    x0, y0, x1, y1 = H.OUTER
    a0, b0, a1, b1 = H.INNER
    d = (f"M{f(v.X(x0))} {f(v.Y(y0))} H{f(v.X(x1))} V{f(v.Y(y1))} H{f(v.X(x0))} Z "
         f"M{f(v.X(a0))} {f(v.Y(b0))} H{f(v.X(a1))} V{f(v.Y(b1))} H{f(v.X(a0))} Z")
    sh.path(d, sw, col, fo, extra=' fill-rule="evenodd"')
    v.rect(*H.BEARING, sw=sw, c=col, fill=fb)
    for p in H.PARTITIONS.values():
        v.rect(*p, sw=sw * 0.75, c=col, fill=fp)

    pad = 0.45 * v.s
    gap = max(30, 0.35 * v.s)
    for o in H.OPENINGS:
        ax, n0, n1 = H.wall_of(o)
        a, b = o["a"], o["b"]
        if ax == "x":
            v.rect(a, n0 - pad, b, n1 + pad, sw=0, c="none", fill="#fff")
            v.line(a, n0, a, n1, w=sw * 0.75, c=col)
            v.line(b, n0, b, n1, w=sw * 0.75, c=col)
        else:
            v.rect(n0 - pad, a, n1 + pad, b, sw=0, c="none", fill="#fff")
            v.line(n0, a, n1, a, w=sw * 0.75, c=col)
            v.line(n0, b, n1, b, w=sw * 0.75, c=col)
        if o["kind"] == "win":
            m = (n0 + n1) / 2
            for t in (n0, n1, m - gap / 2, m + gap / 2):
                if ax == "x":
                    v.line(a, t, b, t, w=0.18, c=col)
                else:
                    v.line(t, a, t, b, w=0.18, c=col)
        if o["kind"] == "door" and o["wall"] in ("front", "rear", "right", "left"):
            # порог
            if ax == "x":
                v.line(a, n0, b, n0, w=0.15, c=col)
            else:
                v.line(n0, a, n0, b, w=0.15, c=col)
        sw_ = H.DOOR_SWINGS.get((o["mark"], o["a"]))
        if sw_:
            hx, hy = sw_["hinge"]
            cx, cy = sw_["closed"]
            ox, oy = sw_["open"]
            r = math.hypot(ox - hx, oy - hy)
            a0 = math.degrees(math.atan2(cy - hy, cx - hx))
            a1 = math.degrees(math.atan2(oy - hy, ox - hx))
            dlt = (a1 - a0 + 180) % 360 - 180
            v.pline(arc_pts(hx, hy, r, a0, a0 + dlt), w=0.15, c=col)
            v.line(hx, hy, ox, oy, w=0.4 if not eng else 0.25, c=col)

    if fixtures:
        draw_fixtures(v, "#9a9a9a" if eng else "#333")


def draw_fixtures(v, c):
    w = 0.18
    sm = 1.5 if v.s >= 100 else 1.7
    # санузел: ванна, умывальник, унитаз
    v.rect(2100, 400, 3800, 1150, sw=w, c=c)
    v.rect(2200, 470, 3700, 1080, sw=w, c=c, rx=1.2)
    v.rect(2100, 1900, 2550, 2500, sw=w, c=c)
    v.sh.add(f'<ellipse cx="{f(v.X(2340))}" cy="{f(v.Y(2200))}" rx="{f(v.L(160))}" ry="{f(v.L(210))}" '
             f'stroke="{c}" stroke-width="{w}" fill="none"/>')
    v.rect(3920, 1500, 4100, 1880, sw=w, c=c)
    v.sh.add(f'<ellipse cx="{f(v.X(3710))}" cy="{f(v.Y(1690))}" rx="{f(v.L(230))}" ry="{f(v.L(170))}" '
             f'stroke="{c}" stroke-width="{w}" fill="none"/>')
    # котельная: котёл, бойлер косвенного нагрева, стиральная машина
    v.rect(1550, 400, 2000, 750, sw=w, c=c, fill="#fff")
    v.text(1775, 520, "котёл", sm, anchor="middle", c=c)
    v.circle(1300, 2650, v.L(270), sw=w, c=c)
    v.text(1300, 2600, "БКН", sm, anchor="middle", c=c)
    v.rect(400, 1800, 1000, 2400, sw=w, c=c)
    v.circle(700, 2100, v.L(210), sw=w, c=c)
    # кухня: столешница вдоль перегородки и фасада, мойка, варочная, холодильник
    v.pline([(6300, 400), (8800, 400), (8800, 1000), (6900, 1000), (6900, 2450), (6300, 2450)], w=w, c=c)
    v.rect(7650, 470, 8250, 930, sw=w, c=c, rx=0.6)
    v.rect(6350, 1500, 6850, 2100, sw=w, c=c)
    for (px, py) in ((6475, 1650), (6725, 1650), (6475, 1950), (6725, 1950)):
        v.circle(px, py, v.L(85), sw=w, c=c)
    v.rect(6300, 2450, 7000, 3150, sw=w, c=c)
    v.text(6650, 2730, "Х", 1.8, anchor="middle", c=c)
    v.rect(8250, 420, 8790, 980, sw=w, c=c, dash="0.8 0.6")
    # обеденный стол и диван
    v.sh.add(f'<ellipse cx="{f(v.X(8900))}" cy="{f(v.Y(2650))}" rx="{f(v.L(800))}" ry="{f(v.L(450))}" '
             f'stroke="{c}" stroke-width="{w}" fill="none"/>')
    v.rect(10650, 1100, 11550, 2300, sw=w, c=c)
    v.rect(10650, 1100, 10850, 2300, sw=w, c=c)
    # кровати
    for (bx1, by1, bx2, by2, head) in ((400, 5800, 2400, 7400, "w"), (5300, 5800, 7300, 7400, "e"),
                                         (7400, 5800, 9400, 7400, "w")):
        v.rect(bx1, by1, bx2, by2, sw=w, c=c)
        hx = bx1 + 120 if head == "w" else bx2 - 520
        v.rect(hx, by1 + 150, hx + 400, by1 + 750, sw=w, c=c, rx=0.5)
        v.rect(hx, by2 - 750, hx + 400, by2 - 150, sw=w, c=c, rx=0.5)
    # шкафы
    v.rect(400, 8000, 1800, 8600, sw=w, c=c, dash="1 0.6")
    v.rect(3900, 8000, 5300, 8600, sw=w, c=c, dash="1 0.6")
    v.rect(10200, 4650, 11600, 5250, sw=w, c=c, dash="1 0.6")
    v.rect(5600, 1550, 6200, 3150, sw=w, c=c, dash="1 0.6")
    # вентканалы (утеплённые трубы Ø125 до выхода над кровлей)
    for (vx, vy) in VENTS:
        v.rect(vx - 70, vy - 70, vx + 70, vy + 70, sw=w, c=c)
        v.line(vx - 70, vy - 70, vx + 70, vy + 70, w=w, c=c)


VENTS = [(3980, 2930), (1880, 2930), (7080, 3080)]   # санузел, котельная, кухня
STACK = (4030, 1300)                                 # канализационный стояк Ст К1-1


LABEL_POS = {1: (5200, 2300), 2: (3100, 2600), 3: (1200, 1300), 4: (2400, 3750), 5: (9600, 3500),
             6: (2900, 7900), 7: (4700, 6600), 8: (10300, 7600)}


def room_labels(v, small=False, color="#000"):
    for n, name, r, fl in H.ROOMS:
        cx, cy = LABEL_POS[n]
        if small:
            v.circle(cx, cy, 2.0, sw=0.25, c=color, fill="#fff")
            v.sh.text(v.X(cx), v.Y(cy) + 0.75, str(n), 2.1, anchor="middle", c=color)
        else:
            v.circle(cx, cy, 2.6, sw=0.3, fill="#fff")
            v.sh.text(v.X(cx), v.Y(cy) + 1.0, str(n), 2.8, anchor="middle", weight="bold")
            a = f"{H.area(r):.2f}".replace(".", ",")
            v.sh.text(v.X(cx), v.Y(cy) + 6.3, a, 2.5, anchor="middle")
            v.sh.line(v.X(cx) - 4.5, v.Y(cy) + 7.2, v.X(cx) + 4.5, v.Y(cy) + 7.2, 0.25)


def plan_axes_dims(v, full=True):
    """Оси и размеры плана 1:50 (АР-1, ЭО-1, ВК-1)."""
    top, bot = v.Y(H.B), v.Y(0)
    left, right = v.X(0), v.X(H.L)
    # цепочки сверху: проёмы, оси, габарит
    rear = [0] + sorted(sum(([o["a"], o["b"]] for o in H.OPENINGS if o["wall"] == "rear"), [])) + [H.L]
    if full:
        v.dimh(rear, top - 7, ext=top - 1)
        v.dimh([0, 200, H.L - 200, H.L], top - 13, ext=top - 1)
        v.dimh([0, H.L], top - 19, ext=top - 1)
        front = [0] + sorted(sum(([o["a"], o["b"]] for o in H.OPENINGS if o["wall"] == "front"), [])) + [H.L]
        v.dimh(front, bot + 7, ext=bot + 1)
        v.dimv([0, 400, 4350, 4650, 8600, 9000], left - 7, ext=left - 1)
        v.dimv([0, 200, 4500, 8800, 9000], left - 13, ext=left - 1)
        v.dimv([0, 9000], left - 19, ext=left - 1)
        rgt = [0] + sorted(sum(([o["a"], o["b"]] for o in H.OPENINGS if o["wall"] == "right"), [])) + [H.B]
        v.dimv(rgt, right + 7, ext=right + 1)
        v.dimv([0, 200, 4500, 8800, 9000], right + 13, ext=right + 1)
        v.dimv([0, 9000], right + 19, ext=right + 1)
        ya, yb = top - 23, bot + 9.5
        xa, xb = left - 23, right + 23
    else:
        v.dimh([0, 200, H.L - 200, H.L], top - 8, ext=top - 1)
        v.dimh([0, H.L], top - 14, ext=top - 1)
        v.dimv([0, 200, 4500, 8800, 9000], left - 8, ext=left - 1)
        v.dimv([0, 9000], left - 14, ext=left - 1)
        ya, yb = top - 18, bot + 1
        xa, xb = left - 18, right + 4
    v.axis_x(200, "1", ya, yb, ends=("top", "bottom") if full else ("top",))
    v.axis_x(H.L - 200, "2", ya, yb, ends=("top", "bottom") if full else ("top",))
    for y, lab in ((200, "А"), (4500, "Б"), (8800, "В")):
        v.axis_y(y, lab, xa, xb, ends=("left", "right") if full else ("left",))


def section_mark(v, x, label="1"):
    """Метки разреза у внутренних граней наружных стен, стрелка — направление взгляда."""
    sh = v.sh
    for yy, d in ((H.B - H.T_OUT, 1), (H.T_OUT, -1)):
        Y = v.Y(yy) + 0.8 * d
        Y2 = Y + 4 * d
        sh.line(v.X(x), Y, v.X(x), Y2, 0.9)
        sh.line(v.X(x), Y2, v.X(x) - 4, Y2, 0.35, marker="arr")
        sh.text(v.X(x) - 5.8, Y2 + (3.2 if d > 0 else -0.8), label, 3.2, anchor="middle", weight="bold")


# ======================================================================
# Лист 1. Общие данные
# ======================================================================
def s_od():
    sh = new_sheet(0)
    sh.frame()
    sh.text(25, 16, "Одноэтажный жилой дом 9×12 м с газовой котельной — г. Бобруйск", 5.0, weight="bold")
    sh.text(25, 22.5, "Эскизный проект: архитектура, фундаменты, стены, электроснабжение, водопровод и канализация",
            2.8, c="#333")

    sh.heading(25, 33, "Ведомость листов")
    rows = [["Лист", "Обозначение", "Наименование"]]
    for i, (code, title, sc) in enumerate(SHEETS):
        rows.append([str(i + 1), f"{code}", title])
    y = sh.table(25, 36, [12, 18, 120], rows, rh=5.2, size=2.3, aligns=["middle", "middle", "start"])
    rows = [["Обозначение", "Наименование"],
            ["README.md", "Пояснительная записка: решения, расчёты, ведомости материалов, этапы работ"]]
    sh.heading(25, y + 9, "Прилагаемые документы")
    y = sh.table(25, y + 12, [30, 120], rows, rh=5.2, size=2.3)

    q = H.quantities()
    tot = sum(H.area(r) for _, _, r, _ in H.ROOMS)
    bed = sum(H.area(r) for n, _, r, _ in H.ROOMS if n in H.BEDROOMS)
    sh.heading(25, y + 9, "Технико-экономические показатели")
    rows = [["Показатель", "Ед.", "Значение"],
            ["Габариты в осях / по наружным граням", "м", "11,6×8,6 / 12,0×9,0"],
            ["Площадь застройки", "м²", "108,0"],
            ["Общая площадь", "м²", f"{tot:.1f}".replace(".", ",")],
            ["  в т.ч. спальни (3 шт.)", "м²", f"{bed:.1f}".replace(".", ",")],
            ["  в т.ч. кухня-гостиная", "м²", f"{H.area(H.ROOMS[4][2]):.1f}".replace(".", ",")],
            ["Строительный объём (до верха утеплителя перекрытия)", "м³", f"{108 * 3.1:.0f}"],
            ["Этажность / высота помещений (в чистоте)", "—", "1 / 2,80 м"],
            ["Расчётная электрическая мощность (3 фазы, 380 В)", "кВт", "15"],
            ["Расчётные теплопотери при −24 °C", "кВт", "≈ 7"],
            ["Газовый котёл (одноконтурный, закрытая камера)", "кВт", "12–15"],
            ["Водопотребление (4 чел. × 180 л/сут)", "м³/сут", "0,72"]]
    sh.table(25, y + 12, [100, 14, 36], rows, rh=5.0, size=2.2, aligns=["start", "middle", "middle"])

    x = 190
    sh.heading(x, 33, "Климатические и инженерно-геологические данные (г. Бобруйск)")
    rows = [["Параметр", "Значение"],
            ["Температура наиболее холодной пятидневки (обесп. 0,92)", "≈ −24 °C"],
            ["Продолжительность / ср. температура отопит. периода", "≈ 195 сут / ≈ −1,0 °C"],
            ["Нормативная глубина промерзания: суглинки / супеси / пески", "≈ 0,9 / 1,1 / 1,2 м"],
            ["Снеговая нагрузка (характеристическое значение)", "≈ 1,2 кПа"],
            ["Ветровое давление (базовое)", "≈ 0,23 кПа"],
            ["Требуемое Rт, м²·°С/Вт: стены / перекрытие / окна", "3,2 / 6,0 / 1,0"],
            ["Расчётное сопротивление основания (принято условно)", "R ≥ 150 кПа"],
            ["Уровень грунтовых вод (принято условно)", "ниже −2,5 м от земли"]]
    y2 = sh.table(x, 36, [150, 72], rows, rh=5.0, size=2.2, aligns=["start", "middle"])

    sh.heading(x, y2 + 9, "Общие указания")
    notes = [
        "1. За отметку ±0.000 принят уровень чистого пола, что соответствует абс. отметке по генплану участка "
        "(+0,60 м от планировочной отметки земли). Размеры — в мм, отметки — в м.",
        "2. Проект эскизный. Для строительства в Республике Беларусь необходимы: решение местного исполкома "
        "о предоставлении участка, архитектурно-планировочное задание, технические условия (электросети, газ, "
        "вода), инженерно-геологические изыскания и строительный проект, выполненный аттестованной организацией.",
        "3. Фундаменты рассчитаны на условное основание R ≥ 150 кПа без подземных вод. По результатам изысканий "
        "ширину и глубину ленты уточнить; при пучинистых глинах и высоком УГВ — заменить на утеплённую плиту.",
        "4. Наружные стены — газосиликатные блоки D400 толщиной 400 мм на клею, Rт ≈ 3,5 ≥ 3,2. Перекрытие — "
        "деревянные балки, минвата 300 мм, Rт ≈ 7,0 ≥ 6,0. Кровля двускатная 30°, металлочерепица.",
        "5. Отопление — газовый котёл в отдельной котельной (объём 11,9 м³ ≥ 7,5 м³, окно 0,54 м², приток через "
        "решётку двери и наружный клапан, коаксиальный дымоход через стену). Проект газоснабжения выполняет "
        "газоснабжающая организация по своим ТУ.",
        "6. Электроснабжение — 3 фазы, 380/220 В, 15 кВт, система TN-C-S, повторное заземление ≤ 30 Ом. "
        "Электромонтаж — по ПУЭ и ТКП 339; приёмка с замерами сопротивления изоляции и заземления.",
        "7. Водоснабжение — от городской сети или скважины; канализация — в городскую сеть или в септик "
        "с фильтрующим колодцем (ВК-2). Ввод воды и выпуск канализации разнесены на 1,5 м.",
        "7а. Участок 20×45 м; существующая постройка 5×10 м — по левой границе, 6 м от улицы. Дом (лист ГП): "
        "задний фасад параллельно правой границе на 3,0 м, торец — 19 м от улицы, вход с левой стороны.",
        "8. Применяемые нормы (в действующих редакциях): СН 2.04.01-2020 «Теплотехника», СН 2.04.02-2020 "
        "«Климатология», СН 3.02.01 «Жилые здания», СН 4.01.03 «Водоснабжение и канализация зданий», "
        "СН 4.03.01 «Газоснабжение», ТКП 45-5.01-254 «Основания и фундаменты», ПУЭ, ТКП 339.",
    ]
    yy = y2 + 14
    for n in notes:
        yy = sh.wrap(x, yy, n, 222, size=2.2, lh=3.0) + 1.2
    return sh


# ======================================================================
# Лист 2. АР-1 План этажа 1:50
# ======================================================================
def s_ar1():
    sh = new_sheet(2)
    v = View(sh, 55, 218, 50)
    plan_base(v, "ar")
    room_labels(v)
    plan_axes_dims(v)
    section_mark(v, 5400)
    # внутренние размеры
    v.dimh([400, 2000, 2100, 4100, 4200, 6200, 6300, 11600], v.Y(2850), ext=None, size=1.9)
    v.dimh([400, 3800, 3900, 7300, 7400, 11600], v.Y(5250), ext=None, size=1.9)

    x = 330
    sh.heading(x, 14, "План этажа  М 1:50")
    rows = [["№", "Наименование", "S, м²"]]
    for n, name, r, fl in H.ROOMS:
        rows.append([str(n), name, f"{H.area(r):.2f}".replace(".", ",")])
    tot = sum(H.area(r) for _, _, r, _ in H.ROOMS)
    bed = sum(H.area(r) for n, _, r, _ in H.ROOMS if n in H.BEDROOMS)
    rows.append(["", "Общая площадь", f"{tot:.2f}".replace(".", ",")])
    rows.append(["", "в т.ч. спальни", f"{bed:.2f}".replace(".", ",")])
    sh.text(x, 22, "Экспликация помещений", 2.8, weight="bold")
    y = sh.table(x, 24, [7, 53, 22], rows, rh=5.2, size=2.2, aligns=["middle", "start", "middle"],
                 bold_rows=(9,))

    sh.text(x, y + 8, "Условные обозначения", 2.8, weight="bold")
    yy = y + 12
    items = [("url(#hBlock)", "Наружная стена — газосиликат D400, 400 мм; несущая — D500, 300 мм"),
             ("url(#hPart)", "Перегородки — газосиликат D500, 100 мм")]
    for fill, t in items:
        sh.rect(x, yy, 10, 4, sw=0.4, fill=fill)
        sh.wrap(x + 13, yy + 2.6, t, 68, size=2.1, lh=2.8)
        yy += 9
    sh.rect(x + 2, yy, 6, 6, sw=0.25)
    sh.line(x + 2, yy, x + 8, yy + 6, 0.25)
    sh.wrap(x + 13, yy + 2.6, "Вентканал — утеплённая труба Ø125 с выводом выше кровли (санузел, котельная, кухня)",
            68, size=2.1, lh=2.8)
    yy += 12
    sh.text(x, yy, "Примечания", 2.8, weight="bold")
    yy += 4.5
    for n in ["1. Высота помещений в чистоте — 2,80 м.",
              "2. Котельная — газовый котёл с закрытой камерой сгорания; дверь EI 15 с решёткой в низу полотна; "
              "в наружной стене — приточный клапан.",
              "3. Двери в санузел и котельную открываются наружу (в коридор). Вход — посередине "
              "фасада по оси А, обращённого к левой (широкой) части участка.",
              "4. Расстановка мебели показана условно.",
              "5. Выход на террасу Д2 — из кухни-гостиной (терраса по желанию, см. АР-4)."]:
        yy = sh.wrap(x, yy, n, 80, size=2.1, lh=2.9) + 1
    # стрелка «север» (по схеме участка север — вверх; торец по оси 1 обращён на север)
    nx, ny = 345, 222
    sh.circle(nx, ny, 4.5, 0.3)
    sh.pline([(nx - 4.5, ny), (nx + 3.5, ny - 1.6), (nx + 3.5, ny + 1.6)], 0.3, fill="#000", close=True)
    sh.text(nx - 7.5, ny + 1.1, "С", 3, anchor="middle", weight="bold")
    sh.frame()
    return sh


# ======================================================================
# Лист 3. АР-2 План стен 1:100, ведомости проёмов и перемычек
# ======================================================================
LINTELS = [
    ("ПР-1", "ОК1", 1500, "стена 400", "U-блок 400, монолит C16/20, 4Ø10 S500, хомуты Ø6 шаг 200", 2000),
    ("ПР-2", "ОК2", 1200, "стена 400", "то же", 1700),
    ("ПР-3", "ОК3", 600, "стена 400", "U-блок 400, монолит, 2Ø10 S500", 1100),
    ("ПР-4", "Д1", 1000, "стена 400", "U-блок 400, монолит, 4Ø10 S500", 1500),
    ("ПР-5", "Д2", 900, "стена 400", "то же", 1400),
    ("ПР-6", "ДГ1", 900, "стена 300", "U-блок 300, монолит, 4Ø10 S500", 1400),
    ("ПР-7", "ДГ2–ДГ4", 1000, "перегородка 100", "2Ø8 S500 в шве кладки (на клей-растворе) / уголок 63×5", 1500),
]


def s_ar2():
    sh = new_sheet(3)
    v = View(sh, 45, 130, 100)
    plan_base(v, "ar", fixtures=False)
    # марки проёмов
    for o in H.OPENINGS:
        ax, n0, n1 = H.wall_of(o)
        m = (o["a"] + o["b"]) / 2
        if o["wall"] == "front":
            v.text(m, -350, o["mark"], 1.9, anchor="middle")
        elif o["wall"] == "rear":
            v.text(m, B_ + 150, o["mark"], 1.9, anchor="middle")
        elif o["wall"] == "right":
            sh.text(v.X(H.L) + 1.2, v.Y(m) + 0.7, o["mark"], 1.9)
        elif o["wall"] == "bear":
            v.text(m, 4000, o["mark"], 1.7, anchor="middle")
        else:
            v.text(m, 2700, o["mark"], 1.7, anchor="middle")
    top, bot, left, right = v.Y(H.B), v.Y(0), v.X(0), v.X(H.L)
    rear = [0] + sorted(sum(([o["a"], o["b"]] for o in H.OPENINGS if o["wall"] == "rear"), [])) + [H.L]
    front = [0] + sorted(sum(([o["a"], o["b"]] for o in H.OPENINGS if o["wall"] == "front"), [])) + [H.L]
    rgt = [0] + sorted(sum(([o["a"], o["b"]] for o in H.OPENINGS if o["wall"] == "right"), [])) + [H.B]
    v.dimh(rear, top - 6, ext=top - 1, size=1.7)
    v.dimh([0, H.L], top - 11, ext=top - 1, size=1.9)
    v.dimh(front, bot + 8, ext=bot + 4, size=1.7)
    v.dimv(rgt, right + 8, ext=right + 4, size=1.7)
    v.dimv([0, 400, 4350, 4650, 8600, 9000], left - 6, ext=left - 1, size=1.7)
    v.dimv([0, 9000], left - 11, ext=left - 1, size=1.9)
    v.axis_x(200, "1", top - 14, bot + 11, r=2.6, ends=("top",))
    v.axis_x(H.L - 200, "2", top - 14, bot + 11, r=2.6, ends=("top",))
    for y, lab in ((200, "А"), (4500, "Б"), (8800, "В")):
        v.axis_y(y, lab, left - 14, right + 2, r=2.6, ends=("left",))
    sh.heading(45, 14, "План стен на отм. +1.000  М 1:100")

    # указания по кладке
    x, y = 25, 152
    sh.text(x, y, "Указания по кладке", 2.8, weight="bold")
    y += 4.5
    for n in [
        "1. Первый ряд блоков — на выравнивающий слой ЦПР М100 толщиной 10–30 мм по горизонтальной "
        "гидроизоляции (2 слоя наплавляемого материала). Последующие ряды — на клей для ячеистого бетона, шов 2–3 мм.",
        "2. Армирование кладки наружных и несущей стен — 2Ø8 S500 в штрабах в 1-м, 5-м и 9-м рядах и в ряду "
        "под оконными проёмами с заведением за откосы на 500 мм.",
        "3. Перевязка блоков — со смещением не менее 0,4 высоты блока (100 мм). Пересечения стен — с перевязкой "
        "через ряд; перегородки крепить к стенам гибкими связями (нерж. полоса) через ряд.",
        "4. Над проёмами — перемычки по ведомости, опирание не менее 250 мм. По верху наружных и несущей стен — "
        "монолитный армопояс 250×250 мм (C16/20, 4Ø10 S500, хомуты Ø6 шаг 300), снаружи 100 мм газосиликата "
        "и 50 мм ЭППС.",
        "5. В армопоясе — анкеры М12 шаг 1000 мм для крепления мауэрлата.",
        "6. Кладку в мороз (ниже +5 °C) вести на зимнем клее; в дождь укрывать. Отклонение рядов по "
        "горизонтали — не более 10 мм на 10 м.",
    ]:
        y = sh.wrap(x, y, n, 152, size=2.1, lh=2.85) + 1

    x = 185
    sh.text(x, 14, "Ведомость заполнения проёмов", 2.8, weight="bold")
    from collections import Counter
    cnt = Counter(o["mark"] for o in H.OPENINGS)
    rows = [["Марка", "Проём, мм", "Наименование", "Кол.", "Примечание"]]
    for m in ["ОК1", "ОК2", "ОК3", "Д1", "Д2", "ДГ1", "ДГ2", "ДГ3", "ДГ4"]:
        t = H.OPENING_TYPES[m]
        rows.append([m, f"{t['w']}×{t['h']}", t["name"], str(cnt[m]), t["note"]])
    y = sh.table(x, 16, [12, 20, 92, 9, 94], rows, rh=5.0, size=1.95,
                 aligns=["middle", "middle", "start", "middle", "start"])

    sh.text(x, y + 7, "Ведомость перемычек", 2.8, weight="bold")
    rows = [["Марка", "Над проёмом", "Стена", "Конструкция", "L, мм", "Кол."]]
    lcount = {"ОК1": cnt["ОК1"], "ОК2": cnt["ОК2"], "ОК3": cnt["ОК3"], "Д1": cnt["Д1"], "Д2": cnt["Д2"],
              "ДГ1": cnt["ДГ1"], "ДГ2–ДГ4": cnt["ДГ2"] + cnt["ДГ3"] + cnt["ДГ4"]}
    for mk, op, w, wall, constr, ln in LINTELS:
        rows.append([mk, f"{op} ({w})", wall, constr, str(ln), str(lcount[op])])
    y = sh.table(x, y + 9, [12, 24, 26, 128, 26, 11], rows, rh=5.0, size=1.95,
                 aligns=["middle", "start", "start", "start", "middle", "middle"])

    q = H.quantities()
    sh.text(x, y + 7, "Спецификация стеновых материалов", 2.8, weight="bold")
    rows = [["Наименование", "Ед.", "Кол-во", "Примечание"],
            ["Блоки газосиликатные D400, 625×250×400 мм (СТБ 1117)", "м³", f"{q['gs_out'] * 1.05:.1f}",
             "наружные стены, запас 5%"],
            ["Блоки газосиликатные D500, 625×250×300 мм", "м³", f"{q['gs_bear'] * 1.05:.1f}", "несущая стена по оси Б"],
            ["Блоки газосиликатные D500, 625×250×100 мм", "м³", f"{q['gs_part'] * 1.05:.1f}", "перегородки"],
            ["Блоки U-образные 400 / 300 и доборные 100 мм (армопояс)", "м.п.",
             f"{q['belt_len'] + 16:.0f}", "армопояс и перемычки"],
            ["Клей для ячеистого бетона", "т", f"{(q['gs_out'] + q['gs_bear'] + q['gs_part']) * 1.05 * 0.028:.1f}",
             "≈ 28 кг/м³ кладки"],
            ["Арматура Ø8 S500 (армирование кладки)", "кг", "125", "≈ 320 м.п."],
            ["Бетон C16/20 (армопояс, перемычки)", "м³", f"{q['concrete_belt'] + 0.8:.1f}", ""],
            ["Арматура Ø10 S500 / Ø6 S240 (армопояс, перемычки)", "кг",
             f"{q['rebar_belt'][10][1] + 25:.0f} / {q['rebar_belt'][6][1] + 6:.0f}", ""]]
    sh.table(x, y + 9, [112, 10, 20, 85], rows, rh=5.0, size=1.95, aligns=["start", "middle", "middle", "start"])
    sh.frame()
    return sh


B_ = H.B

import sheets_arch as SA  # noqa: E402
import sheets_eng as SE  # noqa: E402


def _mk(i, fn, *a):
    sh = new_sheet(i)
    fn(sh, *a)
    sh.frame()
    return sh


def s_gp():
    return _mk(1, SA.s_gp)


def s_ar3():
    return _mk(4, SA.s_ar3)


def s_ar4():
    return _mk(5, SA.s_ar4)


def s_kzh():
    return _mk(6, SA.s_kzh)


def s_eo1():
    return _mk(7, SE.s_eo1, plan_base, plan_axes_dims, room_labels)


def s_eo2():
    return _mk(8, SE.s_eo2)


def s_vk1():
    return _mk(9, SE.s_vk1, plan_base, plan_axes_dims, room_labels)


def s_vk2():
    return _mk(10, SE.s_vk2)


def main(only=None):
    os.makedirs(OUT, exist_ok=True)
    makers = [s_od, s_gp, s_ar1, s_ar2, s_ar3, s_ar4, s_kzh, s_eo1, s_eo2, s_vk1, s_vk2]
    for i, mk in enumerate(makers):
        if only and FILES[i] not in only:
            continue
        sh = mk()
        with open(os.path.join(OUT, FILES[i] + ".svg"), "w", encoding="utf-8") as fh:
            fh.write(sh.svg())
        print("ok", FILES[i])


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or None)
