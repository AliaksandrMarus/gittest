"""Геометрия дома 9×12 м — единый источник для всех листов и подсчёта объёмов.

Система координат модели (мм): X — вдоль длинной стороны (0…12000),
Y — вдоль короткой (0…9000), Y=0 — главный фасад (вход), Z — высота,
Z=0 — уровень чистого пола (±0.000).
"""

L, B = 12000, 9000          # габарит по наружным граням стен
T_OUT = 400                 # наружная стена, газосиликат D400
T_BEAR = 300                # внутренняя несущая стена, газосиликат D500
T_PART = 100                # перегородки, газосиликат D500
Y_BEAR = (4350, 4650)       # несущая стена по оси Б (ось 4500)

# --- высотные отметки, мм ---
Z_GROUND = -600             # планировочная отметка земли
Z_FTOP = -50                # верх фундамента (низ кладки)
Z_FSOLE_OUT = -1800         # подошва наружной ленты (1,2 м от земли)
Z_FSOLE_IN = -1000          # подошва внутренней ленты (в тёплом контуре)
CUSHION = 200               # песчаная подушка под подошвой
Z_WALL_TOP = 2450           # верх кладки (10 рядов по 250 мм)
Z_BELT_TOP = 2700           # верх монолитного армопояса
Z_CEIL = 2800               # чистый потолок (ГКЛ по обрешётке под балками)
Z_HEAD = 2150               # верх оконных и дверных проёмов
ROOF_DEG = 30
EAVE = 500                  # вынос карниза
GABLE = 400                 # вынос фронтонного свеса
Z_MAUER = 2850              # верх мауэрлата и лежня (на них — балки перекрытия)
Z_BEAM_TOP = 3050           # верх балок перекрытия 50×200 (на них опираются стропила)
Z_RIDGE = 5900              # конёк (верх покрытия)
Z_FLOOR_LAYERS = [          # пол по грунту (сверху вниз): (толщина, название)
    (10, "покрытие: ламинат / керамогранит"),
    (60, "стяжка ЦПС М150, армированная сеткой Вр-I Ø4 100×100"),
    (100, "ЭППС 100 мм (λ ≤ 0,034), швы со смещением"),
    (2, "гидроизоляция — плёнка ПЭ 200 мкм, нахлёст 150 мм"),
    (80, "бетонная подготовка C12/15"),
    (300, "песок средней крупности, уплотнение слоями по 150 мм, Kу ≥ 0,95"),
]

# --- стены ---
OUTER = (0, 0, L, B)
INNER = (T_OUT, T_OUT, L - T_OUT, B - T_OUT)
BEARING = (T_OUT, Y_BEAR[0], L - T_OUT, Y_BEAR[1])
PARTITIONS = {
    "P1": (2000, 400, 2100, 3050),    # котельная | санузел
    "P2": (4100, 400, 4200, 3150),    # санузел | прихожая
    "P3": (6200, 400, 6300, 4350),    # прихожая | кухня-гостиная
    "P4": (400, 3050, 4100, 3150),    # котельная, санузел | коридор
    "P5": (3800, 4650, 3900, 8600),   # спальня 1 | спальня 2
    "P6": (7300, 4650, 7400, 8600),   # спальня 2 | спальня 3
}

# --- помещения: номер, название, прямоугольник, тип пола ---
ROOMS = [
    (1, "Прихожая-холл", (4200, 400, 6200, 4350), "плитка"),
    (2, "Санузел", (2100, 400, 4100, 3050), "плитка"),
    (3, "Котельная (газовая)", (400, 400, 2000, 3050), "плитка"),
    (4, "Коридор", (400, 3150, 4200, 4350), "ламинат"),
    (5, "Кухня-гостиная", (6300, 400, 11600, 4350), "ламинат/плитка"),
    (6, "Спальня 1", (400, 4650, 3800, 8600), "ламинат"),
    (7, "Спальня 2", (3900, 4650, 7300, 8600), "ламинат"),
    (8, "Спальня 3", (7400, 4650, 11600, 8600), "ламинат"),
]
LIVING = {5, 6, 7, 8}
BEDROOMS = {6, 7, 8}


def area(r):
    x1, y1, x2, y2 = r
    return (x2 - x1) * (y2 - y1) / 1e6


# --- проёмы ---
# wall: front (Y=0), rear (Y=9000), right (X=12000), left (X=0), bear (несущая), P1..P6
# a, b — границы проёма вдоль стены; sill — низ проёма; mark — марка
OPENINGS = [
    # главный фасад
    dict(mark="ОК3", wall="front", a=900, b=1500, sill=1250, kind="win"),
    dict(mark="ОК3", wall="front", a=2800, b=3400, sill=1250, kind="win"),
    dict(mark="Д1", wall="front", a=4700, b=5700, sill=0, kind="door"),
    dict(mark="ОК1", wall="front", a=7200, b=8700, sill=750, kind="win"),
    dict(mark="ОК1", wall="front", a=9700, b=11200, sill=750, kind="win"),
    # правый торец
    dict(mark="ОК2", wall="right", a=1100, b=2300, sill=750, kind="win"),
    dict(mark="Д2", wall="right", a=2900, b=3800, sill=0, kind="door"),
    dict(mark="ОК1", wall="right", a=5875, b=7375, sill=750, kind="win"),   # спальня 3 — в торец
    # дворовый фасад
    dict(mark="ОК1", wall="rear", a=1350, b=2850, sill=750, kind="win"),
    dict(mark="ОК1", wall="rear", a=4850, b=6350, sill=750, kind="win"),
    # несущая стена — двери в спальни
    dict(mark="ДГ1", wall="bear", a=2800, b=3700, sill=0, kind="door", head=2100),
    dict(mark="ДГ1", wall="bear", a=4400, b=5300, sill=0, kind="door", head=2100),
    dict(mark="ДГ1", wall="bear", a=7600, b=8500, sill=0, kind="door", head=2100),
    # перегородки
    dict(mark="ДГ2", wall="P4", a=2300, b=3100, sill=0, kind="door", head=2100),
    dict(mark="ДГ3", wall="P4", a=700, b=1600, sill=0, kind="door", head=2100),
    dict(mark="ДГ4", wall="P3", a=3250, b=4250, sill=0, kind="door", head=2100),
]

OPENING_TYPES = {
    "ОК1": dict(w=1500, h=1400, name="Окно ПВХ, двухкамерный стеклопакет, Rт ≥ 1,0", note="поворотно-откидная + глухая створки"),
    "ОК2": dict(w=1200, h=1400, name="Окно ПВХ, двухкамерный стеклопакет, Rт ≥ 1,0", note="две створки, одна поворотно-откидная"),
    "ОК3": dict(w=600, h=900, name="Окно ПВХ, двухкамерный стеклопакет, Rт ≥ 1,0", note="поворотно-откидное, санузел — матовое стекло"),
    "Д1": dict(w=1000, h=2150, name="Дверь входная утеплённая металлическая, Rт ≥ 0,9", note="терморазрыв, 2 контура уплотнения"),
    "Д2": dict(w=900, h=2150, name="Дверь балконная ПВХ остеклённая", note="выход на террасу из кухни-гостиной"),
    "ДГ1": dict(w=900, h=2100, name="Дверь межкомнатная 800×2000", note="спальни"),
    "ДГ2": dict(w=800, h=2100, name="Дверь межкомнатная 700×2000", note="санузел, с защёлкой"),
    "ДГ3": dict(w=900, h=2100, name="Дверь 800×2000, EI 15", note="котельная; решётка в низу полотна для притока"),
    "ДГ4": dict(w=1000, h=2100, name="Дверь остеклённая 900×2000", note="прихожая — кухня-гостиная"),
}


def wall_of(o):
    """Возвращает (ось: 'x'|'y', координата нормали from, to) для стены проёма."""
    w = o["wall"]
    if w == "front":
        return "x", 0, T_OUT
    if w == "rear":
        return "x", B - T_OUT, B
    if w == "right":
        return "y", L - T_OUT, L
    if w == "left":
        return "y", 0, T_OUT
    if w == "bear":
        return "x", Y_BEAR[0], Y_BEAR[1]
    x1, y1, x2, y2 = PARTITIONS[w]
    if (x2 - x1) > (y2 - y1):
        return "x", y1, y2
    return "y", x1, x2


def opening_rect(o):
    ax, n0, n1 = wall_of(o)
    if ax == "x":
        return (o["a"], n0, o["b"], n1)
    return (n0, o["a"], n1, o["b"])


# --- двери: петля, направление открывания ---
# hinge — точка петли, open — конец полотна в открытом положении, closed — конец в закрытом
DOOR_SWINGS = {
    ("Д1", 4700): dict(hinge=(5700, 400), closed=(4700, 400), open=(5700, 1400)),
    ("Д2", 2900): dict(hinge=(11600, 3800), closed=(11600, 2900), open=(10700, 3800)),
    ("ДГ1", 2800): dict(hinge=(2800, 4650), closed=(3600, 4650), open=(2800, 5450)),
    ("ДГ1", 4400): dict(hinge=(5300, 4650), closed=(4500, 4650), open=(5300, 5450)),
    ("ДГ1", 7600): dict(hinge=(7600, 4650), closed=(8400, 4650), open=(7600, 5450)),
    ("ДГ2", 2300): dict(hinge=(2350, 3150), closed=(3050, 3150), open=(2350, 3850)),
    ("ДГ3", 700): dict(hinge=(1550, 3150), closed=(750, 3150), open=(1550, 3950)),
    ("ДГ4", 3250): dict(hinge=(6300, 3300), closed=(6300, 4200), open=(7200, 3300)),
}

# --- фундамент ---
F_WIDTH = 400
F_OUT_RING = (0, 0, L, B)                       # наружная лента по контуру стен
F_INNER = (T_OUT, 4300, L - T_OUT, 4700)        # лента под несущей стеной

SLEEVES = [  # гильзы в фундаменте: (обозначение, лента, x, отметка низа трубы, Ø гильзы)
    ("В1", "наружная, ось 1 (торец)", 1000, -1500, 110),
    ("К1-1", "наружная, ось А", 4030, -1300, 160),
]


# ======================================================================
# Подсчёт объёмов
# ======================================================================
def quantities():
    q = {}
    # фундамент
    perim_axis = 2 * ((L - F_WIDTH) + (B - F_WIDTH)) / 1000          # по оси ленты, м
    inner_len = (L - 2 * T_OUT) / 1000
    h_out = (Z_FTOP - Z_FSOLE_OUT) / 1000
    h_in = (Z_FTOP - Z_FSOLE_IN) / 1000
    v_out = perim_axis * 0.4 * h_out
    v_in = inner_len * 0.4 * h_in
    q["perim_axis"] = perim_axis
    q["inner_len"] = inner_len
    q["concrete_found"] = v_out + v_in
    q["concrete_found_out"] = v_out
    q["concrete_found_in"] = v_in
    # арматура фундамента
    kg = {12: 0.888, 10: 0.617, 8: 0.395, 6: 0.222, 4: 0.099}
    r12 = (4 * perim_axis + 4 * inner_len) * 1.15
    r10 = 2 * perim_axis * 1.15
    n_out = int(perim_axis / 0.4) + 4
    n_in = int(inner_len / 0.4) + 1
    st_out = 2 * (0.3 + (h_out * 1000 - 100) / 1000) + 0.1
    st_in = 2 * (0.3 + (h_in * 1000 - 100) / 1000) + 0.1
    r6 = n_out * st_out + n_in * st_in
    q["rebar_found"] = {12: (r12, r12 * kg[12]), 10: (r10, r10 * kg[10]), 6: (r6, r6 * kg[6])}
    # песчаная подушка и выемка
    q["sand_cushion"] = perim_axis * 0.8 * CUSHION / 1000 + inner_len * 0.8 * CUSHION / 1000
    trench_w = 1.2
    q["excavation"] = perim_axis * trench_w * ((Z_GROUND - Z_FSOLE_OUT + CUSHION) / 1000) \
        + inner_len * 0.8 * (Z_GROUND - Z_FSOLE_IN + CUSHION) / 1000 * 0  # внутр. — в подсыпке
    # гидроизоляция
    q["hydro_vert"] = perim_axis * h_out + inner_len * h_in * 2 * 0  # обмазка снаружи наружной ленты
    q["hydro_hor"] = (perim_axis + inner_len) * 0.4 * 1.1 * 2         # 2 слоя
    # утепление цоколя и отмостки
    q["xps_plinth"] = perim_axis * 1.05 * 0.05 * 1.05                 # от -0.050 до -1.100
    q["otmostka_area"] = (2 * (L + B) / 1000 + 4 * 1.0) * 1.0
    # пол по грунту
    floor_area = (L - 2 * T_OUT) * (B - 2 * T_OUT) / 1e6 - inner_len * 0.3
    q["floor_area"] = floor_area
    q["xps_floor"] = floor_area * 0.1 * 1.05
    q["prep_concrete"] = floor_area * 0.08
    q["screed"] = floor_area * 0.06
    q["sand_floor"] = floor_area * 0.3 * 1.2   # с коэффициентом уплотнения
    q["mesh_floor"] = floor_area * 1.1

    # стены
    wall_h = (Z_WALL_TOP - Z_FTOP) / 1000
    out_axis = 2 * ((L - T_OUT) + (B - T_OUT)) / 1000
    ext_open = sum(OPENING_TYPES[o["mark"]]["w"] * OPENING_TYPES[o["mark"]]["h"] / 1e6
                   for o in OPENINGS if o["wall"] in ("front", "rear", "right", "left"))
    bear_open = sum(OPENING_TYPES[o["mark"]]["w"] * OPENING_TYPES[o["mark"]]["h"] / 1e6
                    for o in OPENINGS if o["wall"] == "bear")
    part_len = sum(max(x2 - x1, y2 - y1) for (x1, y1, x2, y2) in PARTITIONS.values()) / 1000
    part_open = sum(OPENING_TYPES[o["mark"]]["w"] * OPENING_TYPES[o["mark"]]["h"] / 1e6
                    for o in OPENINGS if o["wall"].startswith("P"))
    part_h = (Z_CEIL + 40) / 1000
    q["wall_out_area"] = out_axis * wall_h - ext_open
    q["ext_open_area"] = ext_open
    q["gs_out"] = (out_axis * wall_h - ext_open) * 0.4
    q["gs_bear"] = (inner_len * wall_h - bear_open) * 0.3
    q["gs_part"] = (part_len * part_h - part_open) * 0.1
    q["part_len"] = part_len
    # армопояс 250×250 по наружным и несущей стенам
    belt_len = out_axis + inner_len
    q["belt_len"] = belt_len
    q["concrete_belt"] = belt_len * 0.25 * 0.25
    q["rebar_belt"] = {10: (4 * belt_len * 1.15, 4 * belt_len * 1.15 * kg[10]),
                       6: ((int(belt_len / 0.3) + 1) * 0.9, (int(belt_len / 0.3) + 1) * 0.9 * kg[6])}
    # перемычки (U-блоки, монолит)
    # кровля
    import math
    t = math.tan(math.radians(ROOF_DEG))
    slope_len = ((B / 2 + EAVE) / 1000) / math.cos(math.radians(ROOF_DEG))
    q["roof_area"] = 2 * slope_len * (L + 2 * GABLE) / 1000
    q["slope_len"] = slope_len
    q["ridge_h"] = Z_BEAM_TOP + (B / 2 - 150) * t + 340
    n_raft = int((L + 2 * GABLE) / 900) + 1
    q["rafters"] = 2 * n_raft
    n_beams = int((L - 2 * T_OUT) / 600) + 1
    q["beams"] = 2 * n_beams
    q["attic_area"] = (L - 2 * T_OUT) * (B - 2 * T_OUT) / 1e6
    q["mineral_wool"] = q["attic_area"] * 0.30 * 1.05
    q["wall_plaster_ext"] = (2 * (L + B) / 1000) * (Z_WALL_TOP + 250 - Z_FTOP) / 1000 - ext_open
    return q


if __name__ == "__main__":
    tot = 0
    for n, name, r, fl in ROOMS:
        tot += area(r)
        print(n, name, round(area(r), 2))
    print("итого", round(tot, 2), "жилая", round(sum(area(r) for n, _, r, _ in ROOMS if n in LIVING), 2))
    for k, v in quantities().items():
        print(k, v)
