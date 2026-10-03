"""Листы ГП, АР-3 (разрез), АР-4 (фасады), КЖ-1 (фундаменты)."""
import math

import house as H
from drawing import View, lvl, f

T30 = math.tan(math.radians(H.ROOF_DEG))
RAFT_V = 200 / math.cos(math.radians(H.ROOF_DEG))     # вертикальная высота стропила 200 мм
COVER_V = 110                                           # контробрешётка + обрешётка + металлочерепица


def zb(u):
    """Низ стропила на расстоянии u от фасада по оси А (переднего ската)."""
    if u <= H.B / 2:
        return H.Z_BEAM_TOP + (u - 150) * T30
    return H.Z_BEAM_TOP + (H.B - 150 - u) * T30


Z_RIDGE_TOP = zb(H.B / 2) + RAFT_V + COVER_V


# ======================================================================
# ГП — схема участка
# ======================================================================
# Контур участка (м) — снят с присланной схемы, масштаб принят ориентировочно 1 пкс = 0,1 м.
PLOT = [(1.5, 0.0), (24.2, 1.0), (24.2, 11.5), (20.0, 11.0), (20.5, 20.5), (22.0, 22.5),
        (20.2, 49.0), (0.0, 47.8), (0.5, 37.0), (2.0, 26.0), (0.8, 14.2)]
OLD_BLD = (4.8, 10.5, 10.5, 19.2)      # существующее строение по схеме (x1, y1, x2, y2)
FENCE_A, FENCE_B = (22.0, 22.5), (20.2, 49.0)
_d = (FENCE_B[0] - FENCE_A[0], FENCE_B[1] - FENCE_A[1])
_n = math.hypot(*_d)
DH = (_d[0] / _n, _d[1] / _n)
EX = (-DH[0], -DH[1])                  # ось X дома (к улице)
EY = (DH[1], -DH[0])                   # ось Y дома (от фасада А к фасаду В, к правому забору)
EY = (-EY[0], -EY[1]) if EY[0] < 0 else EY
_t = 12 + (24.0 - FENCE_A[1] + 12 * EY[1]) / DH[1]
O = (FENCE_A[0] - 12 * EY[0] + _t * DH[0], FENCE_A[1] - 12 * EY[1] + _t * DH[1])


def site(x, y):
    """Локальные координаты дома (мм) → координаты участка (м)."""
    return (O[0] + x / 1000 * EX[0] + y / 1000 * EY[0], O[1] + x / 1000 * EX[1] + y / 1000 * EY[1])


def poly_area(pts):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def dist_pt_line(p, a, b):
    ax, ay = a
    bx, by = b
    return abs((bx - ax) * (ay - p[1]) - (ax - p[0]) * (by - ay)) / math.hypot(bx - ax, by - ay)


def s_gp(sh):
    v = View(sh, 50, 272, 200)        # 1:200, модель — мм участка
    M = lambda pts: [(x * 1000, y * 1000) for x, y in pts]
    sh.heading(25, 13, "Схема планировочной организации участка  М 1:200")
    # улица
    sh.rect(22, v.Y(0) + 1.2, 140, 12, sw=0, fill="#eceff2")
    v.line(-1000, -600, 26000, 700, w=0.5, c="#555")
    sh.text(85, v.Y(0) + 9, "УЛИЦА (проезжая часть)", 2.6, anchor="middle", c="#555")
    # участок
    v.pline(M(PLOT), w=0.6, c="#000", close=True, fill="#fbfbf7")
    sh.text(v.X(-1500), v.Y(30000), "соседний участок", 2.0, rot=-90, anchor="middle", c="#777")
    sh.text(v.X(23600), v.Y(40000), "соседний участок", 2.0, rot=-90, anchor="middle", c="#777")
    # существующее строение
    x1, y1, x2, y2 = OLD_BLD
    v.rect(x1 * 1000, y1 * 1000, x2 * 1000, y2 * 1000, sw=0.3, fill="url(#hBlockGray)")
    v.text((x1 + x2) / 2 * 1000, (y1 + y2) / 2 * 1000, "сущ.", 2.0, anchor="middle")
    v.text((x1 + x2) / 2 * 1000, (y1 + y2) / 2 * 1000 - 1100, "строение", 2.0, anchor="middle")
    # подъезд и стоянка, дорожки
    drive = [(1.9, 0.3), (4.5, 0.4), (4.5, 20.5), (8.2, 20.5), (8.2, 27.0), (2.4, 27.0), (2.2, 20.5)]
    v.pline(M(drive), w=0.25, c="#777", close=True, fill="#e9e6df")
    v.text(3200, 9000, "подъезд", 1.9, rot=-90, anchor="middle", c="#555")
    v.text(5300, 24000, "стоянка", 1.9, anchor="middle", c="#555")
    p1 = site(5200, -1800)
    v.pline(M([(p1[0] - 0.7, 27.0), (p1[0] + 0.5, 27.0), (p1[0] + 0.5, p1[1] - 0.6), (p1[0] - 0.7, p1[1] - 0.6)]),
            w=0.2, c="#777", fill="#e9e6df", close=True)
    # терраса
    ter = [site(12000, 1500), site(14500, 1500), site(14500, 6000), site(12000, 6000)]
    v.pline(M(ter), w=0.3, c="#7a5a30", close=True, fill="url(#hWood)")
    # дом
    hp = [site(0, 0), site(H.L, 0), site(H.L, H.B), site(0, H.B)]
    v.pline(M(hp), w=0.7, c="#000", close=True, fill="url(#hBlock)")
    c = site(H.L / 2, H.B / 2)
    sh.rect(v.X(c[0] * 1000) - 9, v.Y(c[1] * 1000) - 7, 18, 13, sw=0.3, fill="#fff")
    sh.mtext(v.X(c[0] * 1000), v.Y(c[1] * 1000) - 3.4, ["Жилой дом", "9×12 м", "1 эт.", "±0.000"], 2.1,
             anchor="middle")
    # крыльцо и вход
    pr = [site(4500, 0), site(5900, 0), site(5900, -1800), site(4500, -1800)]
    v.pline(M(pr), w=0.3, c="#000", close=True, fill="#ddd")
    e = site(5200, -2400)
    e2 = site(5200, -400)
    sh.line(v.X(e[0] * 1000), v.Y(e[1] * 1000), v.X(e2[0] * 1000), v.Y(e2[1] * 1000), 0.5, marker="arr")
    sh.text(v.X(e[0] * 1000) - 1.5, v.Y(e[1] * 1000) - 1.5, "вход", 2.0, anchor="end", weight="bold")
    # сети
    sew = [site(4030, 0), site(4030, -1500)]
    kk1 = sew[1]
    kk2 = (11.8, 20.4)
    sept, filt = (14.6, 15.3), (14.6, 11.4)
    v.pline(M([sew[0], kk1, (kk1[0], 20.4), kk2, (sept[0], sept[1] + 0.9)]), w=0.5, c="#7a4a12", dash="2.4 0.9")
    v.pline(M([(sept[0], sept[1] - 0.9), (filt[0], filt[1] + 0.9)]), w=0.5, c="#7a4a12", dash="2.4 0.9")
    for (px, py), lab in ((kk1, "КК1"), (kk2, "КК2")):
        v.circle(px * 1000, py * 1000, 1.3, sw=0.35, c="#7a4a12", fill="#fff")
        sh.text(v.X(px * 1000) - 2.0, v.Y(py * 1000) - 1.6, lab, 1.9, anchor="end", c="#7a4a12")
    v.circle(sept[0] * 1000, sept[1] * 1000, 3.6, sw=0.4, c="#7a4a12", fill="#f6eadb")
    sh.text(v.X(sept[0] * 1000), v.Y(sept[1] * 1000) + 0.8, "септик", 1.8, anchor="middle", c="#7a4a12")
    v.circle(filt[0] * 1000, filt[1] * 1000, 3.6, sw=0.4, c="#7a4a12", fill="url(#hGravel)")
    sh.text(v.X(filt[0] * 1000) + 4.6, v.Y(filt[1] * 1000) + 0.8, "фильтр. колодец", 1.8, c="#7a4a12")
    wv = site(0, 1000)
    water = [(1.6, 0.35), (1.6, 39.0), (wv[0] - 0.7, 39.0), site(-1300, 1000), wv]
    v.pline(M(water), w=0.5, c="#1f5fbf")
    v.circle(1600, 900, 1.2, sw=0.35, c="#1f5fbf", fill="#fff")
    sh.text(v.X(1600) + 2, v.Y(900) - 1.5, "ВК (кран)", 1.8, c="#1f5fbf")
    el_in = site(4600, 0)
    elec = [(1.0, 0.6), (0.95, 14.2), (1.15, 31.4), (el_in[0], 31.4), el_in]
    v.pline(M(elec), w=0.45, c="#c0392b", dash="1.4 0.7 0.3 0.7")
    sh.rect(v.X(700), v.Y(600) - 1.4, 2.8, 2.8, sw=0.35, c="#c0392b", fill="#fff")
    sh.text(v.X(700) + 3.5, v.Y(600) + 0.6, "ЩУ", 1.9, c="#c0392b")
    gas_in = site(1900, -300)
    gas = [(2.6, 0.4), (2.7, 26.0), (gas_in[0] - 1.2, 33.9), gas_in]
    v.pline(M(gas), w=0.45, c="#d4a106", dash="3 0.8 0.6 0.8")
    # размеры привязки: 3,0 м до правой границы
    for hx, hy in ((H.L, H.B), (0, H.B)):
        p = site(hx, hy)
        q = (p[0] + 3.0 * EY[0], p[1] + 3.0 * EY[1])
        sh.line(v.X(p[0] * 1000), v.Y(p[1] * 1000), v.X(q[0] * 1000), v.Y(q[1] * 1000), 0.25, marker="arr")
        sh.line(v.X(q[0] * 1000), v.Y(q[1] * 1000), v.X(p[0] * 1000), v.Y(p[1] * 1000), 0.25, marker="arr")
        sh.text(v.X((p[0] + q[0]) / 2 * 1000), v.Y((p[1] + q[1]) / 2 * 1000) - 1.2, "3,0", 2.2, anchor="middle",
                weight="bold")
    # расстояния до улицы и левой границы
    pb = site(H.L, 0)
    sh.line(v.X(pb[0] * 1000), v.Y(pb[1] * 1000), v.X(pb[0] * 1000), v.Y(0.45 * 1000), 0.2, dash="1 0.6")
    sh.text(v.X(pb[0] * 1000) + 1.2, v.Y((pb[1] / 2) * 1000), f"≈{pb[1] - 0.4:.1f}".replace(".", ","), 2.1,
            rot=-90, anchor="middle")
    pl = site(H.L / 2, 0)
    pl = site(H.L - 1500, 0)
    sh.line(v.X(pl[0] * 1000), v.Y(pl[1] * 1000), v.X(1.5 * 1000), v.Y(pl[1] * 1000), 0.2, dash="1 0.6")
    sh.text(v.X((pl[0] + 1.5) / 2 * 1000), v.Y(pl[1] * 1000) - 1.0, f"≈{pl[0] - 1.5:.1f}".replace(".", ","),
            2.1, anchor="middle")
    # север
    nx, ny = 150, 30
    sh.circle(nx, ny, 5, 0.3)
    sh.pline([(nx, ny - 5), (nx - 1.8, ny + 3.5), (nx + 1.8, ny + 3.5)], 0.3, fill="#000", close=True)
    sh.text(nx, ny - 6.5, "С", 3, anchor="middle", weight="bold")

    # --- правая колонка ---
    x = 180
    sh.text(x, 24, "Условные обозначения", 2.8, weight="bold")
    leg = [("rect", "url(#hBlock)", "Проектируемый жилой дом"),
           ("rect", "url(#hBlockGray)", "Существующее строение (по схеме; снос/сохранение — уточнить)"),
           ("rect", "url(#hWood)", "Терраса (по желанию), настил по лагам"),
           ("rect", "#e9e6df", "Подъезд, стоянка, дорожки — тротуарная плитка / щебень"),
           ("line", "#1f5fbf", "В1 — водопровод ПЭ100 Ø32, глубина 1,8 м; ввод через торец (ось 1)"),
           ("dash", "#7a4a12", "К1 — канализация ПВХ Ø110, i ≥ 0,02, глубина 0,7–1,2 м, утепление"),
           ("dash", "#c0392b", "Кабель ВБбШв 5×10 от ЩУ в траншее 0,7 м (в трубе ПНД под проездом)"),
           ("dash", "#d4a106", "Г — газопровод (трасса условно, по проекту газоснабжающей организации)")]
    yy = 30
    for kind, col, t in leg:
        if kind == "rect":
            sh.rect(x, yy - 2.6, 9, 3.6, sw=0.3, fill=col)
        else:
            sh.line(x, yy - 0.8, x + 9, yy - 0.8, 0.6, c=col, dash=None if kind == "line" else "2.2 0.8")
        sh.wrap(x + 12, yy, t, 100, size=2.1, lh=2.8)
        yy += 7

    plot_area = poly_area(PLOT)
    ter_area = 2.5 * 4.5
    sh.text(x, yy + 4, "Показатели участка (ориентировочно)", 2.8, weight="bold")
    rows = [["Показатель", "Значение"],
            ["Площадь участка", f"≈ {plot_area:.0f} м² ({plot_area / 10000:.3f} га)".replace(".", ",")],
            ["Площадь застройки дома / с террасой", f"108,0 / {108 + ter_area:.1f} м²".replace(".", ",")],
            ["Процент застройки (с сущ. строением)", f"≈ {(108 + ter_area + 5.7 * 8.7) / plot_area * 100:.0f} %"],
            ["Расстояние от дома до правой границы", "3,0 м (по заданию)"],
            ["До улицы / до левой границы", f"≈ {pb[1] - 0.4:.0f} м / ≈ {site(H.L - 1500, 0)[0] - 1.5:.1f} м"
             .replace(".", ",")],
            ["Септик → дом / граница / питьевой колодец", "≥ 5 м / ≥ 2 м / ≥ 20 м"]]
    yy = sh.table(x, yy + 6, [70, 70], rows, rh=5.0, size=2.1)

    sh.text(x, yy + 7, "Примечания", 2.8, weight="bold")
    yy += 11.5
    for t in [
        "1. Контур участка построен по присланной схеме, масштаб принят ориентировочно (≈ 22×49 м). Перед "
        "строительством получить кадастровый план и топосъёмку М 1:500 с отметками; положение дома уточнить.",
        "2. Дом длинной стороной вдоль участка. Задний фасад (по оси В) — параллельно правой границе на расстоянии "
        "3,0 м; на него выходят окна спален 1 и 2 (лист АР-1). Окна в сторону соседа — по согласованию, если "
        "требуют местные правила застройки.",
        "3. Вход в дом — посередине левого (по участку) фасада по оси А, с подъездом и стоянкой с левой стороны.",
        "4. Кухня-гостиная и терраса обращены к улице (на юг при ориентации схемы «север вверх»), спальни — "
        "на восток. Котельная — в северном углу, ввод воды и газа — со стороны левой границы.",
        "5. Септик — в передней части участка (обслуживание ассенизатором с улицы). При наличии городской "
        "канализации выпуск подключить к ней по ТУ, септик не устраивать.",
        "6. Отвод дождевой воды — по рельефу от дома, уклон планировки 1–2 %, отмостка 1,0 м.",
    ]:
        yy = sh.wrap(x, yy, t, 140, size=2.1, lh=2.85) + 1.2
    # на графике «вход»
    sh.text(v.X(site(4500, -2500)[0] * 1000), 0, "", 1)


# ======================================================================
# АР-3 — разрез 1-1 (по оси x = 5400: прихожая, вход Д1, спальня 2)
# ======================================================================
def s_ar3(sh):
    v = View(sh, 88, 140, 50)
    S = sh
    G = H.Z_GROUND
    # грунт
    v.rect(-1900, -2150, 10300, G, sw=0, fill="#f6f2ea")
    for u0, u1 in ((-1900, -1150), (10150, 10300)):
        v.rect(u0, G - 250, u1, G, sw=0, fill="url(#hSoil)")
    v.line(-1900, G, -1050, G, w=0.6)
    v.line(10050, G, 10300, G, w=0.6)
    # подушки и ленты
    for u0 in (0, H.B - 400):
        v.rect(u0 - 200, H.Z_FSOLE_OUT - 200, u0 + 600, H.Z_FSOLE_OUT, sw=0.3, fill="url(#hSand)")
        v.rect(u0, H.Z_FSOLE_OUT, u0 + 400, H.Z_FTOP, sw=0.5, fill="url(#hConcrete)")
    v.rect(4100, H.Z_FSOLE_IN - 200, 4900, H.Z_FSOLE_IN, sw=0.3, fill="url(#hSand)")
    v.rect(4300, H.Z_FSOLE_IN, 4700, H.Z_FTOP, sw=0.5, fill="url(#hConcrete)")
    # утепление цоколя и гидроизоляция
    v.rect(-50, -1100, 0, H.Z_FTOP, sw=0.25, fill="url(#hInsul)")
    v.rect(H.B, -1100, H.B + 50, H.Z_FTOP, sw=0.25, fill="url(#hInsul)")
    v.line(0, H.Z_FSOLE_OUT, 0, H.Z_FTOP, w=0.7, c="#222")
    v.line(H.B, H.Z_FSOLE_OUT, H.B, H.Z_FTOP, w=0.7, c="#222")
    # отмостка (справа) и крыльцо (слева)
    for a, b in ((H.B + 60, H.B + 1050),):
        v.rect(a, -640, b, -580, sw=0.25, fill="#cfcfcf")
        v.rect(a, -690, b, -640, sw=0.2, fill="url(#hSand)")
        v.rect(a, -740, b, -690, sw=0.2, fill="url(#hInsul)")
    porch = [(-60, -20), (-900, -20), (-900, -165), (-1200, -165), (-1200, -310), (-1500, -310),
             (-1500, -455), (-1800, -455), (-1800, -800), (-60, -800)]
    v.pline(porch, w=0.4, fill="url(#hConcrete)", close=True)
    # пол по грунту
    zs = [0]
    for t_, _ in H.Z_FLOOR_LAYERS:
        zs.append(zs[-1] - t_)
    fills = ["#d9d0bf", "#e2e2e2", "url(#hInsul)", "#333", "url(#hConcrete)", "url(#hSand)"]
    for (u0, u1) in ((400, 4300), (4700, 8600)):
        for i, fl in enumerate(fills):
            v.rect(u0, zs[i + 1], u1, zs[i], sw=0.15, fill=fl)
        v.rect(u0, -1000, u1, zs[-1], sw=0, fill="url(#hSand)")
    v.rect(4300, -170, 4700, -50, sw=0.15, fill="#e2e2e2")
    # стены
    Z0, ZT, ZB = H.Z_FTOP, H.Z_WALL_TOP, H.Z_BELT_TOP

    def wall(u0, u1, holes, belt_out):
        z = Z0
        for (h0, h1) in holes:
            v.rect(u0, z, u1, h0, sw=0.5, fill="url(#hBlock)")
            z = h1
        v.rect(u0, z, u1, ZT, sw=0.5, fill="url(#hBlock)")
        if holes:
            v.rect(u0, holes[-1][1], u1, ZT, sw=0.5, fill="url(#hBlock)")
            v.rect(u0 + 60, holes[-1][1] + 20, u1 - 60, ZT - 60, sw=0.2, fill="url(#hConcrete)")
        if belt_out is None:
            v.rect(u0, ZT, u1, ZB, sw=0.5, fill="url(#hConcrete)")
        elif belt_out == "front":
            v.rect(u0, ZT, u0 + 100, ZB, sw=0.4, fill="url(#hBlock)")
            v.rect(u0 + 100, ZT, u0 + 150, ZB, sw=0.2, fill="url(#hInsul)")
            v.rect(u0 + 150, ZT, u1, ZB, sw=0.5, fill="url(#hConcrete)")
        else:
            v.rect(u1 - 100, ZT, u1, ZB, sw=0.4, fill="url(#hBlock)")
            v.rect(u1 - 150, ZT, u1 - 100, ZB, sw=0.2, fill="url(#hInsul)")
            v.rect(u0, ZT, u1 - 150, ZB, sw=0.5, fill="url(#hConcrete)")

    # передняя стена: дверь Д1 (0…2150)
    v.rect(0, ZT, 400, ZB, sw=0.5)
    wall(0, 400, [(Z0, 2150)], "front")
    v.rect(0, Z0, 400, 0, sw=0, fill="#fff")
    v.rect(150, 0, 220, 2150, sw=0.3, fill="#8a6a4a")
    # задняя стена: окно ОК1 750…2150
    wall(H.B - 400, H.B, [(750, 2150)], "rear")
    v.rect(H.B - 230, 750, H.B - 160, 2150, sw=0.3, fill="#fff")
    v.line(H.B - 195, 800, H.B - 195, 2100, w=0.15)
    v.rect(H.B - 460, 730, H.B - 160, 750, sw=0.2, fill="#fff")
    v.pline([(H.B - 160, 740), (H.B + 60, 700)], w=0.3)
    # несущая стена
    wall(4350, 4650, [], None)
    # штукатурка
    for u in (-12, H.B + 12):
        v.line(u, 0, u, ZB, w=0.2, c="#666")
    # мауэрлат, лежень, балки, утеплитель, потолок
    for u0 in (200, H.B - 350, 4425):
        v.rect(u0, ZB, u0 + 150, H.Z_MAUER, sw=0.35, fill="url(#hWood)")
    v.rect(400, H.Z_CEIL, 4350, H.Z_MAUER, sw=0.2, fill="#e6e6e6")
    v.rect(4650, H.Z_CEIL, 8600, H.Z_MAUER, sw=0.2, fill="#e6e6e6")
    v.rect(150, H.Z_MAUER, H.B - 150, H.Z_BEAM_TOP + 100, sw=0.2, fill="url(#hInsul)")
    for (a, b) in ((150, 4600), (4400, H.B - 150)):
        v.rect(a, H.Z_MAUER, b, H.Z_BEAM_TOP, sw=0.3, dash="1.6 0.6")
    v.rect(3200, H.Z_BEAM_TOP + 100, 5800, H.Z_BEAM_TOP + 125, sw=0.25, fill="url(#hWood)")
    # стропила
    for side in (0, 1):
        if side == 0:
            us = (-500, H.B / 2)
        else:
            us = (H.B / 2, H.B + 500)
        a, b = us
        poly = [(a, zb(a)), (b, zb(b)), (b, zb(b) + RAFT_V), (a, zb(a) + RAFT_V)]
        v.pline(poly, w=0.4, fill="url(#hWood)", close=True)
        cov = [(a, zb(a) + RAFT_V), (b, zb(b) + RAFT_V), (b, zb(b) + RAFT_V + COVER_V),
               (a, zb(a) + RAFT_V + COVER_V)]
        v.pline(cov, w=0.35, fill="#7d8389", close=True)
    # прогон, стойка, схватка
    zr = zb(H.B / 2)
    v.rect(4425, zr - 150, 4575, zr, sw=0.35, fill="url(#hWood)")
    v.rect(4450, H.Z_BEAM_TOP, 4550, zr - 150, sw=0.3, fill="url(#hWood)")
    zs_ = 4500
    us_ = 150 + (zs_ - H.Z_BEAM_TOP) / T30
    v.rect(us_, zs_, H.B - us_, zs_ + 150, sw=0.3, fill="url(#hWood)")
    # карниз
    for e in (-500, H.B + 500):
        v.rect(e - (20 if e < 0 else 0), zb(e) - 60, e + (0 if e < 0 else 20), zb(e) + RAFT_V, sw=0.3, fill="#fff")
        v.line(e, zb(e) - 60, 0 if e < 0 else H.B, zb(e) - 60, w=0.3)
        v.circle(e + (-90 if e < 0 else 90), zb(e) + 40, 1.2, sw=0.35, fill="#fff")
    # вентканал за плоскостью разреза
    v.rect(4300, H.Z_BEAM_TOP + 100, 4425, 6400, sw=0.25, dash="1.2 0.6")
    v.text(4200, 6150, "вентканалы и фановый стояк — выше конька на 0,5 м", 1.8, anchor="end")

    # отметки
    xl = v.X(-1900) - 2
    for z, t in ((G, lvl(G)), (H.Z_FSOLE_OUT, lvl(H.Z_FSOLE_OUT)), (ZB, lvl(ZB)), (H.Z_BEAM_TOP, lvl(H.Z_BEAM_TOP)),
                 (Z_RIDGE_TOP, f"{lvl(Z_RIDGE_TOP)} конёк")):
        v.level(xl, z, t, side="left")
    xr = v.X(10300) + 2
    for z in (G, 0, 750, 2150, H.Z_CEIL):
        v.level(xr, z, lvl(z))
    v.level(v.X(4700) + 2, H.Z_FSOLE_IN, lvl(H.Z_FSOLE_IN))
    v.level(v.X(2400), 0, "±0.000")
    v.level(v.X(2400), H.Z_CEIL, lvl(H.Z_CEIL))
    # размеры
    v.dimv([H.Z_FSOLE_OUT, G, 0, 2150, ZT, ZB], v.X(-1900) - 22, ext=v.X(-1850))
    v.dimh([0, 400, 4350, 4650, H.B - 400, H.B], v.Y(-2150) + 5, ext=v.Y(-2150))
    v.dimh([0, 200, 4500, H.B - 200, H.B], v.Y(-2150) + 11, ext=v.Y(-2150))
    for u, lab in ((200, "А"), (4500, "Б"), (H.B - 200, "В")):
        v.axis_x(u, lab, v.Y(-2150) + 13, v.Y(-2150) + 14, r=3, ends=("bottom",))
    sh.heading(25, 13, "Разрез 1-1  М 1:50")
    # выноски составов
    marks = [(1, 1800, zb(1800) + 250), (2, 6200, 3000), (3, 8800, 1600), (4, 6600, -150), (5, 9600, -650),
             (6, 8800, -1300), (7, -1300, -200)]
    for n, u, z in marks:
        X, Y = v.X(u), v.Y(z)
        sh.line(X, Y, X + 4, Y - 4, 0.25)
        sh.circle(X + 6, Y - 6, 2.3, 0.3, fill="#fff")
        sh.text(X + 6, Y - 5.2, str(n), 2.4, anchor="middle", weight="bold")

    # составы конструкций
    x = 318
    sh.text(x, 13, "Составы конструкций", 2.9, weight="bold")
    comp = [
        ("1. Кровля (холодный чердак)", [
            "металлочерепица 0,5 мм с полимерным покрытием",
            "обрешётка 25×100 шаг 350; контробрешётка 50×50",
            "супердиффузионная мембрана",
            "стропила 50×200 шаг 900 (сосна С24, антисептик)",
            "прогон 150×150 на стойках 100×150 шаг ≤ 3 м"]),
        ("2. Чердачное перекрытие, Rт ≈ 7,0", [
            "ходовые доски 25 мм по центру",
            "ветрозащитная мембрана",
            "минвата λ ≤ 0,042: 200 между балками + 100 поверх",
            "балки 50×200 шаг 600 на мауэрлате и лежне",
            "пароизоляция; обрешётка 25×50; ГКЛ 12,5 мм"]),
        ("3. Наружная стена, Rт ≈ 3,5", [
            "фасадная тонкослойная штукатурка 8 мм по сетке",
            "газосиликат D400, 400 мм, на клею",
            "гипсовая штукатурка 15 мм"]),
        ("4. Пол по грунту", [f"{t} мм — {n}" for t, n in H.Z_FLOOR_LAYERS]),
        ("5. Отмостка 1000 мм, уклон 2 %", [
            "тротуарная плитка 60 / ЦПС 30",
            "ЭППС 50 мм / геотекстиль / песок 150"]),
        ("6. Фундамент", [
            "монолитная лента 400×1750, C16/20 F150 W4",
            "песчаная подушка 200 мм; обмазочная гидроизоляция",
            "ЭППС 50 мм по цоколю до −1.100"]),
        ("7. Крыльцо", ["монолит C16/20 на своём фундаменте,", "шов 20 мм от ленты дома"]),
    ]
    yy = 19
    for t, lines in comp:
        sh.text(x, yy, t, 2.2, weight="bold")
        yy = sh.mtext(x + 2, yy + 3.2, lines, 1.95, lh=2.6) + 1.6

    sh.text(x, yy + 3, "Теплотехническая проверка", 2.6, weight="bold")
    rows = [["Конструкция", "Rт расч.", "Rт норм."],
            ["Стена (D400, λ = 0,12)", "3,55", "3,2"],
            ["Чердачное перекрытие", "≈ 7,0", "6,0"],
            ["Окна (2-камерные)", "≥ 1,0", "1,0"],
            ["Пол по грунту (ЭППС 100)", "≈ 3,2", "—"]]
    sh.table(x, yy + 5, [52, 21, 21], rows, rh=4.6, size=1.95, aligns=["start", "middle", "middle"])

    # ведомость отделки
    x, y = 22, 196
    sh.text(x + 2, y - 2, "Ведомость отделки помещений", 2.8, weight="bold")
    rows = [["№", "Помещение", "Потолок", "Стены", "Пол"]]
    fin = {
        1: (["ГКЛ, шпаклёвка,", "водоэмульсионная краска"], ["гипс. штукатурка, шпаклёвка,", "моющаяся краска"],
            ["керамогранит 600×600,", "водяной тёплый пол"]),
        2: (["ГКЛВ, влагостойкая", "краска"], ["цем. штукатурка, обмазочная гидроизол.,", "плитка до потолка"],
            ["гидроизоляция, керамогранит,", "тёплый пол, порог 20 мм"]),
        3: (["ГКЛО (огнестойкий),", "краска"], ["цем. штукатурка,", "плитка / краска"], ["керамогранит, трап Ø50"]),
        4: (["ГКЛ, краска"], ["гипс. штукатурка, краска"], ["ламинат 33 кл. на подложке"]),
        5: (["ГКЛ, краска; над кухней —", "точечные светильники"],
            ["гипс. штукатурка, краска;", "фартук — плитка"], ["кухня — керамогранит,", "гостиная — ламинат 33 кл."]),
        6: (["ГКЛ, краска"], ["гипс. штукатурка, обои"], ["ламинат / инж. доска"]),
    }
    for n, name, r, fl in H.ROOMS:
        k = n if n <= 5 else 6
        cel, wal, flo = fin[k]
        rows.append([str(n), name, cel, wal, flo])
    sh.table(x + 2, y, [6, 30, 44, 60, 50], rows, rh=10.3, size=1.75, aligns=["middle", "start", "start", "start",
                                                                                   "start"],
             rhs=[5.5] + [10.3] * 8)


# ======================================================================
# АР-4 — фасады и план кровли
# ======================================================================
def facade_long(v, ops, porch=None, vents=(), mirror=False):
    sh = v.sh
    L_ = H.L
    mx = (lambda x: L_ - x) if mirror else (lambda x: x)
    v.line(-1500, H.Z_GROUND, L_ + 1500, H.Z_GROUND, w=0.7)
    v.rect(-60, H.Z_GROUND, L_ + 60, H.Z_FTOP, sw=0.4, fill="#8d9196")
    v.rect(0, H.Z_FTOP, L_, 2650, sw=0.5, fill="#f5f2ec")
    # кровля
    ze = zb(-500)
    v.rect(-H.GABLE, ze + RAFT_V + COVER_V, L_ + H.GABLE, Z_RIDGE_TOP, sw=0.45, fill="#6d737a")
    z = ze + RAFT_V + COVER_V + 350
    while z < Z_RIDGE_TOP - 100:
        v.line(-H.GABLE, z, L_ + H.GABLE, z, w=0.12, c="#b9bec4")
        z += 350
    v.rect(-H.GABLE, 2650, L_ + H.GABLE, ze + RAFT_V + COVER_V, sw=0.35, fill="#fff")
    v.line(-H.GABLE, ze + RAFT_V + 300, L_ + H.GABLE, ze + RAFT_V + 300, w=0.3, c="#ddd")
    v.rect(-H.GABLE - 50, 2560, L_ + H.GABLE + 50, 2650, sw=0.3, fill="#6d737a")
    for dx in (-150, L_ + 150):
        v.rect(dx - 50, -450, dx + 50, 2560, sw=0.25, fill="#6d737a")
    for vx, top in vents:
        X = mx(vx)
        v.rect(X - 70, 4000, X + 70, top, sw=0.3, fill="#ccc")
    for o in ops:
        a, b = sorted((mx(o["a"]), mx(o["b"])))
        t = H.OPENING_TYPES[o["mark"]]
        z0 = o["sill"]
        z1 = z0 + t["h"] if o["kind"] == "win" else 2150
        if o["kind"] == "win":
            v.rect(a, z0, b, z1, sw=0.4, fill="#fff")
            v.rect(a - 40, z0 - 60, b + 40, z0, sw=0.3, fill="#6d737a")
            n = 2 if (b - a) >= 1200 else 1
            w = (b - a) / n
            for i in range(n):
                v.rect(a + i * w + 60, z0 + 60, a + (i + 1) * w - 60, z1 - 60, sw=0.2, fill="#cfe0ee")
            if n == 2:
                v.pline([(a + 60, z1 - 60), (a + w - 60, (z0 + z1) / 2), (a + 60, z0 + 60)], w=0.12, c="#777",
                        dash="0.8 0.5")
        else:
            glass = o["mark"] == "Д2"
            v.rect(a, 0, b, z1, sw=0.4, fill="#cfe0ee" if glass else "#6b4f3a")
            if glass:
                v.rect(a + 60, 60, b - 60, z1 - 60, sw=0.2)
            else:
                v.rect(a + 120, 200, b - 120, z1 - 200, sw=0.2, c="#3d2c1e")
                v.circle(a + 150 if not mirror else b - 150, 1050, 0.5, sw=0.2, fill="#ddd")
    if porch:
        a, b = porch
        for i, z in enumerate((-20, -165, -310, -455)):
            v.rect(a - i * 0, z - 145, b, z, sw=0.3, fill="#c9c9c9")


def s_ar4(sh):
    sh.heading(25, 13, "Фасады  М 1:100")
    front_ops = [o for o in H.OPENINGS if o["wall"] == "front"]
    rear_ops = [o for o in H.OPENINGS if o["wall"] == "rear"]
    side_ops = [o for o in H.OPENINGS if o["wall"] == "right"]
    vent_tops = [(4030, 4560)] + [(x, 6400) for x, _ in ((3980, 0), (1880, 0), (7080, 0))]

    v = View(sh, 40, 86, 100)
    facade_long(v, front_ops, porch=(4500, 5900), vents=vent_tops)
    v.circle(1775, 2050, 0.9, sw=0.3, fill="#ddd")
    v.text(1775, 2350, "дымоход", 1.5, anchor="middle")
    v.rect(5150, 2250, 5250, 2400, sw=0.25, fill="#333")
    v.text(H.L / 2, -1500, "Фасад А-А (главный, вход)", 2.6, anchor="middle", weight="bold")
    for z in (H.Z_GROUND, 0, 2150, Z_RIDGE_TOP):
        v.level(v.X(H.L + 900), z, lvl(z), shelf=10)
    v.axis_x(0, "1", v.Y(-1000), v.Y(-1000) + 0.1, r=2.4, ends=("bottom",))
    v.axis_x(H.L, "2", v.Y(-1000), v.Y(-1000) + 0.1, r=2.4, ends=("bottom",))

    v2 = View(sh, 222, 86, 100)
    facade_long(v2, rear_ops, vents=vent_tops, mirror=True)
    v2.text(H.L / 2, -1500, "Фасад В-В (к правой границе участка)", 2.6, anchor="middle", weight="bold")
    v2.axis_x(0, "2", v2.Y(-1000), v2.Y(-1000) + 0.1, r=2.4, ends=("bottom",))
    v2.axis_x(H.L, "1", v2.Y(-1000), v2.Y(-1000) + 0.1, r=2.4, ends=("bottom",))

    # торец по оси 2 (к улице): горизонталь — y дома
    v3 = View(sh, 45, 190, 100)
    B_ = H.B
    v3.line(-1500, H.Z_GROUND, B_ + 1500, H.Z_GROUND, w=0.7)
    v3.rect(-60, H.Z_GROUND, B_ + 60, H.Z_FTOP, sw=0.4, fill="#8d9196")
    v3.rect(0, H.Z_FTOP, B_, 2700, sw=0.5, fill="#f5f2ec")
    gable = [(0, 2700), (0, zb(0)), (B_ / 2, zb(B_ / 2)), (B_, zb(B_)), (B_, 2700)]
    v3.pline(gable, w=0.5, fill="url(#hBoard)", close=True)
    edge = [(-500, zb(-500)), (B_ / 2, zb(B_ / 2)), (B_ + 500, zb(B_ + 500)),
            (B_ + 500, zb(B_ + 500) + RAFT_V + COVER_V), (B_ / 2, Z_RIDGE_TOP), (-500, zb(-500) + RAFT_V + COVER_V)]
    v3.pline(edge, w=0.45, fill="#6d737a", close=True)
    v3.rect(B_ / 2 - 300, 4300, B_ / 2 + 300, 4700, sw=0.3, fill="#fff")
    for z in range(4350, 4700, 80):
        v3.line(B_ / 2 - 260, z, B_ / 2 + 260, z, w=0.15)
    # терраса перед Д2
    v3.rect(1500, H.Z_GROUND, 6000, -150, sw=0.35, fill="url(#hWood)")
    for u in (1500, 3000, 4500, 6000):
        v3.rect(u - 40, -150, u + 40, 850, sw=0.25, fill="#8a6a4a")
    v3.line(1500, 850, 6000, 850, w=0.5, c="#8a6a4a")
    for o in side_ops:
        t = H.OPENING_TYPES[o["mark"]]
        a, b = o["a"], o["b"]
        if o["kind"] == "win":
            z0, z1 = o["sill"], o["sill"] + t["h"]
            v3.rect(a, z0, b, z1, sw=0.4, fill="#fff")
            v3.rect(a - 40, z0 - 60, b + 40, z0, sw=0.3, fill="#6d737a")
            n = 2 if (b - a) >= 1200 else 1
            w = (b - a) / n
            for i in range(n):
                v3.rect(a + i * w + 60, z0 + 60, a + (i + 1) * w - 60, z1 - 60, sw=0.2, fill="#cfe0ee")
        else:
            v3.rect(a, 0, b, 2150, sw=0.4, fill="#cfe0ee")
            v3.rect(a + 60, 60, b - 60, 2090, sw=0.2)
    v3.rect(3350 - 60, 2250, 3350 + 60, 2400, sw=0.25, fill="#333")
    v3.text(B_ / 2, -1500, "Фасад 2 (торец к улице, терраса)", 2.6, anchor="middle", weight="bold")
    v3.axis_x(0, "А", v3.Y(-1000), v3.Y(-1000) + 0.1, r=2.4, ends=("bottom",))
    v3.axis_x(B_, "В", v3.Y(-1000), v3.Y(-1000) + 0.1, r=2.4, ends=("bottom",))
    for z in (H.Z_GROUND, 0, 2700, Z_RIDGE_TOP):
        v3.level(v3.X(B_ + 1700), z, lvl(z), shelf=10)

    # план кровли
    v4 = View(sh, 222, 214, 100)
    sh.heading(222, 113, "План кровли  М 1:100", size=3.0)
    v4.rect(-H.GABLE, -H.EAVE, H.L + H.GABLE, H.B + H.EAVE, sw=0.5, fill="#e7e9ec")
    v4.line(-H.GABLE, H.B / 2, H.L + H.GABLE, H.B / 2, w=0.6)
    for yy in (200, H.B - 200):
        v4.line(-H.GABLE + 200, yy, H.L + H.GABLE - 200, yy, w=0.3, dash="2 0.8")
    for (x, y) in ((-200, -300), (H.L + 200, -300), (-200, H.B + 300), (H.L + 200, H.B + 300)):
        v4.circle(x, y, 1.2, sw=0.3, fill="#fff")
    for x, y in [(4030, 1300)] + [(vx, vy) for vx, vy in ((3980, 2930), (1880, 2930), (7080, 3080))]:
        v4.circle(x, y, 0.9, sw=0.3, fill="#999")
    for yy, d in ((2300, -1), (6700, 1)):
        v4.line(6000, yy, 6000, yy + 1500 * d, w=0.3, marker="arr")
        v4.text(6300, yy + 700 * d, "i = 30°", 2.0)
    v4.text(H.L / 2, H.B / 2 + 250, "конёк, аэратор", 1.8, anchor="middle")
    v4.text(9500, 1000, "снегозадержатели", 1.7, anchor="middle")
    v4.dimh([-H.GABLE, 0, H.L, H.L + H.GABLE], v4.Y(H.B + H.EAVE) - 4, ext=v4.Y(H.B + H.EAVE), size=1.8)
    v4.dimv([-H.EAVE, 0, H.B / 2, H.B, H.B + H.EAVE], v4.X(H.L + H.GABLE) + 5, ext=v4.X(H.L + H.GABLE), size=1.8)

    # отделка фасадов
    x = 372
    sh.text(x, 14, "Отделка фасадов", 2.6, weight="bold")
    items = [
        ("#f5f2ec", "Стены — минеральная штукатурка «короед» 2 мм по армирующему слою, силиконовая краска, "
                    "светлый беж"),
        ("#8d9196", "Цоколь — мозаичная штукатурка по ЭППС, графит"),
        ("#6d737a", "Кровля, водосток, отливы — металл RAL 7024"),
        ("url(#hBoard)", "Фронтоны — каркас, ветрозащита, планкен / имитация бруса"),
        ("#cfe0ee", "Окна, двери — ПВХ, ламинация «антрацит» снаружи"),
        ("#fff", "Подшивка карниза — софиты ПВХ с перфорацией"),
    ]
    yy = 20
    for col, t in items:
        sh.rect(x, yy - 2.6, 6, 3.6, sw=0.3, fill=col)
        yy = sh.wrap(x + 8, yy, t, 32, size=1.9, lh=2.55) + 2.5
    yy += 2
    sh.text(x, yy, "Примечания", 2.6, weight="bold")
    yy += 4
    for t in ["1. Фасад к правому забору (В-В) — окна спален 1 и 2.",
              "2. Фасад по оси 1 (север) — глухой, с фронтоном и вентрешёткой.",
              "3. Вентканалы и стояк — выше конька на 0,5 м.",
              "4. Водосток Ø125/90, по углам здания."]:
        yy = sh.wrap(x, yy, t, 38, size=1.9, lh=2.55) + 1.2


# ======================================================================
# КЖ-1 — фундаменты
# ======================================================================
def s_kzh(sh):
    q = H.quantities()
    v = View(sh, 45, 122, 100)
    sh.heading(25, 13, "План фундаментов  М 1:100")
    # подушки (пунктир) и ленты
    v.rect(-200, -200, H.L + 200, H.B + 200, sw=0.2, dash="1.5 0.8")
    v.rect(600, 600, H.L - 600, H.B - 600, sw=0.2, dash="1.5 0.8")
    d = (f"M{f(v.X(0))} {f(v.Y(0))} H{f(v.X(H.L))} V{f(v.Y(H.B))} H{f(v.X(0))} Z "
         f"M{f(v.X(400))} {f(v.Y(400))} H{f(v.X(H.L - 400))} V{f(v.Y(H.B - 400))} H{f(v.X(400))} Z")
    sh.path(d, 0.5, "#000", "url(#hConcrete)", extra=' fill-rule="evenodd"')
    v.rect(*H.F_INNER, sw=0.5, fill="url(#hConcrete)")
    v.rect(400, 4100, H.L - 400, 4300, sw=0.2, dash="1.5 0.8")
    v.rect(400, 4700, H.L - 400, 4900, sw=0.2, dash="1.5 0.8")
    # гильзы
    for name, where, pos, z, dia in H.SLEEVES:
        if "торец" in where:
            v.circle(200, pos, 1.1, sw=0.4, c="#1f5fbf", fill="#fff")
            sh.text(v.X(-300), v.Y(pos) + 0.7, f"{name}: гильза Ø{dia}, низ {lvl(z)}", 1.8, anchor="end",
                    c="#1f5fbf")
        else:
            v.circle(pos, 200, 1.1, sw=0.4, c="#7a4a12", fill="#fff")
            sh.text(v.X(pos), v.Y(-700), f"{name}: гильза Ø{dia}, низ {lvl(z)}", 1.8, anchor="middle", c="#7a4a12")
    # сечения
    for (yy, lab) in ((200, "1"), (4500, "2")):
        X = v.X(1500)
        sh.line(X, v.Y(yy) - 4.5, X, v.Y(yy) - 2.5, 0.8)
        sh.line(X, v.Y(yy) + 2.5, X, v.Y(yy) + 4.5, 0.8)
        sh.text(X + 2.5, v.Y(yy) - 3.0, lab, 2.6, weight="bold")
        sh.text(X + 2.5, v.Y(yy) + 5.2, lab, 2.6, weight="bold")
    # размеры и оси
    top, bot, left, right = v.Y(H.B), v.Y(0), v.X(0), v.X(H.L)
    v.dimh([0, 400, H.L - 400, H.L], top - 6, ext=top - 1, size=1.8)
    v.dimh([0, H.L], top - 11, ext=top - 1, size=1.9)
    v.dimv([0, 400, 4300, 4700, H.B - 400, H.B], left - 6, ext=left - 1, size=1.8)
    v.dimv([0, H.B], left - 11, ext=left - 1, size=1.9)
    v.axis_x(200, "1", top - 14, bot + 2, r=2.6, ends=("top",))
    v.axis_x(H.L - 200, "2", top - 14, bot + 2, r=2.6, ends=("top",))
    for y, lab in ((200, "А"), (4500, "Б"), (8800, "В")):
        v.axis_y(y, lab, left - 14, right + 2, r=2.6, ends=("left",))

    # спецификация
    r12, r10, r6 = q["rebar_found"][12], q["rebar_found"][10], q["rebar_found"][6]
    rows = [["Поз.", "Наименование", "Ед.", "Кол-во", "Примечание"],
            ["1", "Бетон C16/20 F150 W4 (СТБ EN 206) — ленты", "м³", f"{q['concrete_found'] * 1.03:.1f}",
             f"нар. {q['concrete_found_out']:.1f} + вн. {q['concrete_found_in']:.1f} + 3%"],
            ["2", "Арматура Ø12 S500 — продольная", "кг", f"{r12[1]:.0f}", f"{r12[0]:.0f} м.п. с нахлёстами"],
            ["3", "Арматура Ø10 S500 — средний ряд наружной ленты", "кг", f"{r10[1]:.0f}", f"{r10[0]:.0f} м.п."],
            ["4", "Арматура Ø6 S240 — хомуты шаг 400", "кг", f"{r6[1]:.0f}", f"{r6[0]:.0f} м.п."],
            ["5", "Песок средней крупности — подушка 200 мм", "м³", f"{q['sand_cushion'] * 1.2:.1f}", "Kупл 1,2"],
            ["6", "Мастика битумная — обмазка 2 слоя", "м²", f"{q['hydro_vert']:.0f}", "≈ 3 кг/м²"],
            ["7", "Наплавляемая гидроизоляция — 2 слоя по верху лент", "м²", f"{q['hydro_hor']:.0f}", ""],
            ["8", "ЭППС 50 мм — цоколь и отмостка", "м³", f"{q['xps_plinth'] + q['otmostka_area'] * 0.05:.1f}", ""],
            ["9", "Щитовая опалубка (аренда)", "м²", f"{2 * (q['perim_axis'] * 1.75 + q['inner_len'] * 0.95):.0f}",
             "2 стороны"],
            ["10", "Разработка траншей 1,2 м / обратная засыпка", "м³", f"{q['excavation']:.0f}", "экскаватор"],
            ["11", "Гильзы ПВХ Ø110 и Ø160, L = 500", "шт", "2", "В1, К1-1"]]
    y = sh.table(22, 170, [9, 86, 9, 16, 82], rows, rh=5.2, size=1.95, aligns=["middle", "start", "middle", "middle",
                                                                                  "start"])
    sh.text(24, 166, "Спецификация материалов фундамента", 2.7, weight="bold")

    # --- сечение 1-1 М 1:20 ---
    s1 = View(sh, 252, 52, 20)
    sh.heading(205, 13, "1-1  М 1:20", size=3.0)
    G = H.Z_GROUND
    s1.rect(-1250, -2100, 1400, G, sw=0, fill="#f6f2ea")
    s1.rect(-1250, G - 200, -1100, G, sw=0, fill="url(#hSoil)")
    s1.rect(-200, -2000, 600, -1800, sw=0.35, fill="url(#hSand)")
    s1.rect(0, -1800, 400, -50, sw=0.6, fill="url(#hConcrete)")
    s1.rect(-50, -1100, 0, -50, sw=0.3, fill="url(#hInsul)")
    s1.line(0, -1800, 0, -50, w=0.9, c="#222")
    s1.rect(0, -50, 400, -40, sw=0.3, fill="#222")
    s1.rect(0, -40, 400, 650, sw=0.6, fill="url(#hBlock)")
    s1.pline([(-30, 650), (430, 650)], w=0.3, dash="2 1")
    s1.rect(-1100, -640, -60, -580, sw=0.3, fill="#cfcfcf")
    s1.rect(-1100, -690, -60, -640, sw=0.2, fill="url(#hSand)")
    s1.rect(-1100, -740, -60, -690, sw=0.2, fill="url(#hInsul)")
    s1.line(-1250, G, -1100, G, w=0.6)
    zs = [0]
    for t_, _ in H.Z_FLOOR_LAYERS:
        zs.append(zs[-1] - t_)
    fills = ["#d9d0bf", "#e2e2e2", "url(#hInsul)", "#333", "url(#hConcrete)", "url(#hSand)"]
    for i, fl in enumerate(fills):
        s1.rect(400, zs[i + 1], 1400, zs[i], sw=0.2, fill=fl)
    s1.rect(400, -1100, 1400, zs[-1], sw=0, fill="url(#hSand)")
    # армирование
    for (u, z, d_) in ((50, -1750, 12), (350, -1750, 12), (50, -100, 12), (350, -100, 12), (50, -925, 10),
                       (350, -925, 10)):
        s1.circle(u, z, 0.55 if d_ == 12 else 0.45, sw=0, fill="#000")
    s1.rect(44, -1756, 356, -94, sw=0.25, c="#b00")
    s1.dimh([-200, 0, 400, 600], s1.Y(-2000) + 5, ext=s1.Y(-2000), size=1.8)
    s1.dimv([-2000, -1800, G, -50, 0], s1.X(-1250) - 3, ext=s1.X(-1150), size=1.8)
    s1.level(s1.X(-1150), G, lvl(G), side="right", shelf=9, size=1.8)
    s1.level(s1.X(900), 0, "±0.000", shelf=9, size=1.8)
    s1.level(s1.X(700), -1800, lvl(-1800), shelf=9, size=1.8)
    calls = [(1, 200, -1300), (2, 200, -1950), (3, 0, -1500), (4, 200, -50), (5, -25, -800), (6, -600, -610),
             (7, 900, -120), (8, 200, 300), (9, 350, -1750)]
    for n, u, z in calls:
        X, Y = s1.X(u), s1.Y(z)
        sh.line(X, Y, X - 5, Y - 3.5, 0.2)
        sh.circle(X - 6.6, Y - 4.6, 1.9, 0.25, fill="#fff")
        sh.text(X - 6.6, Y - 3.9, str(n), 2.0, anchor="middle", weight="bold")

    # --- сечение 2-2 ---
    s2 = View(sh, 150, 42, 20)
    sh.heading(345, 13, "2-2  М 1:20", size=3.0)
    s2.rect(4100, -1200, 4900, -1000, sw=0.35, fill="url(#hSand)")
    s2.rect(4300, -1000, 4700, -50, sw=0.6, fill="url(#hConcrete)")
    s2.rect(4300, -50, 4700, -40, sw=0.3, fill="#222")
    s2.rect(4350, -40, 4650, 450, sw=0.6, fill="url(#hBlock)")
    for (u0, u1) in ((3800, 4300), (4700, 5200)):
        for i, fl in enumerate(fills):
            s2.rect(u0, zs[i + 1], u1, zs[i], sw=0.2, fill=fl)
    for (u, z) in ((4350, -950), (4650, -950), (4350, -100), (4650, -100)):
        s2.circle(u, z, 0.55, sw=0, fill="#000")
    s2.rect(4344, -956, 4656, -94, sw=0.25, c="#b00")
    s2.dimh([4100, 4300, 4700, 4900], s2.Y(-1200) + 5, ext=s2.Y(-1200), size=1.8)
    s2.dimv([-1200, -1000, -50], s2.X(5200) + 4, ext=s2.X(4950), size=1.8)
    s2.level(s2.X(4900), -1000, lvl(-1000), shelf=9, size=1.8)

    # экспликация выносок и указания
    x, y = 232, 166
    sh.text(x, y, "Обозначения к сечениям", 2.6, weight="bold")
    exp = ["1 — лента монолитная C16/20, 400 мм", "2 — подушка: песок, уплотнение Kу ≥ 0,95",
           "3 — обмазочная битумная гидроизоляция 2 сл.", "4 — горизонтальная гидроизоляция 2 сл.",
           "5 — ЭППС 50 мм (до −1.100)", "6 — утеплённая отмостка 1,0 м",
           "7 — пол по грунту (см. АР-3)", "8 — стена газосиликат D400", "9 — арматура 4Ø12 + 2Ø10, хомуты Ø6/400"]
    sh.mtext(x, y + 4, exp[:5], 1.95, lh=2.65)
    sh.mtext(x + 90, y + 4, exp[5:], 1.95, lh=2.65)
    yy = y + 19
    sh.text(x, yy, "Указания", 2.6, weight="bold")
    yy += 4
    for t in ["1. Основание — по результатам изысканий; принято R ≥ 150 кПа (пески, супеси, суглинки "
              "тугопластичные). Дно траншей не перебирать, не замачивать; при переборе — подсыпка песком с уплотнением.",
              "2. Подошва наружной ленты на 1,2 м ниже планировки (нормативное промерзание 0,9–1,2 м). "
              "Внутренняя лента — в тёплом контуре, подошва −1.000.",
              "3. Бетонировать непрерывно, с вибрированием; защитный слой 50 мм. Углы и примыкания — с Г-образными "
              "стержнями 2Ø12 L = 1200. Обратная засыпка — песком послойно после набора 70 % прочности.",
              "4. Гильзы закладывать до бетонирования, зазор заделать эластичным герметиком."]:
        yy = sh.wrap(x, yy, t, 180, size=1.95, lh=2.6) + 0.8
