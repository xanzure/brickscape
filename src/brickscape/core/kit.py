"""Landscape kit: rock masses, ground layers, plants, on top of brick.Build.

Cells are (x, z) stud positions; heights are in plates above the baseplate.
"""
import random
from brickscape.core.brick import Build, info

GREEN, BGREEN, DGREEN, OLIVE, LIME = 2, 10, 288, 330, 27
TAN, DTAN, RBROWN, DBROWN = 19, 28, 70, 308
LBG, DBG, BLACK, WHITE = 71, 72, 0, 15
BLUE, TCLEAR, TLBLUE = 1, 47, 43
import os as _os
HIDDEN = int(_os.environ.get("HIDDEN_COLOR", LBG))  # set HIDDEN_COLOR=4 to see hidden parts in red

PLATES = {(1, 1): "3024", (1, 2): "3023", (1, 3): "3623", (1, 4): "3710", (1, 6): "3666",
          (1, 8): "3460", (2, 2): "3022", (2, 3): "3021", (2, 4): "3020", (2, 6): "3795",
          (2, 8): "3034", (2, 10): "3832", (4, 4): "3031", (4, 6): "3032", (4, 8): "3035",
          (6, 6): "3958", (6, 8): "3036", (6, 10): "3033", (8, 8): "41539"}
BRICKS = {(1, 1): "3005", (1, 2): "3004", (1, 3): "3622", (1, 4): "3010", (1, 6): "3009",
          (1, 8): "3008", (2, 2): "3003", (2, 3): "3002", (2, 4): "3001"}
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


def nbr(c, d):
    dx, dz = DIRS[d]
    return (c[0] + dx, c[1] + dz)


def height(part):
    i = info(part)
    return round((i["hi"][1] - i["lo"][1]) / 8)


def pack(cells, table, rng=None, rotate=False, maxsize=None):
    """Greedy rectangle cover of a cell set with sizes from table. -> [(x, z, w, d)]."""
    cells = set(cells)
    sizes = sorted(table, key=lambda s: -s[0] * s[1])
    if maxsize:
        sizes = [s for s in sizes if s[0] * s[1] <= maxsize]
    out = []
    order = sorted(cells, key=lambda c: (c[1], c[0]) if not rotate else (c[0], c[1]))
    for c in order:
        if c not in cells:
            continue
        x, z = c
        for (a, b) in sizes:
            opts = [(b, a), (a, b)] if rotate else [(a, b), (b, a)]
            hit = None
            for (w, d) in opts:
                fp = {(x + i, z + j) for i in range(w) for j in range(d)}
                if fp <= cells:
                    hit = (w, d, fp)
                    break
            if hit:
                w, d, fp = hit
                cells -= fp
                out.append((x, z, w, d))
                break
    return out


def put_rect(b, table, color, x, z, w, d, y, note=""):
    part = table[(min(w, d), max(w, d))]
    p = b.put(part, color, x, y, z, spin="N" if w >= d else "E", note=note)
    if color == HIDDEN and HIDDEN_PASS[0]:
        p.note += " hidden"
    return p


HIDDEN_PASS = [True]   # put_rect marks hidden-colour pieces as hidden


def put_slope(b, part, color, front, d, y, D=2, note=""):
    """D-deep 1-wide slope (or brick) whose low/front cell is `front`, facing d."""
    back = front
    for _ in range(D - 1):
        back = nbr(back, {"N": "S", "S": "N", "E": "W", "W": "E"}[d])
    x, z = min(front[0], back[0]), min(front[1], back[1])
    if part in LONG_X:  # bricks/plates are long along x unrotated, slopes deep along z
        d = "E" if d in "NS" else "N"
    return b.put(part, color, x, y, z, spin=d, note=note)


LONG_X = {"3004", "3023", "3622", "3623", "3010"}
# 1-wide rib piece -> the same profile 2 wide
WIDE = {"4460": "30499", "60481": "3678b", "3040": "3039", "3665": "3660", "3004": "3003",
        "3023": "3022", "4286": "3298", "3622": "3002", "3623": "3021", "4287": "3747b"}
LONG_X_WIDE = {"3002", "3021"}


def put_wide(b, part, color, cells, mate, d, y, note=""):
    """2-wide rib piece over two side-by-side columns (front cells first in each list)."""
    allc = list(cells) + list(mate)
    x, z = min(c[0] for c in allc), min(c[1] for c in allc)
    spin = d
    if part in LONG_X_WIDE:
        spin = "E" if d in "NS" else "N"
    return b.put(part, color, x, y, z, spin=spin, note=note)


def pick(rng, weighted):
    tot = sum(w for _, w in weighted)
    r = rng.random() * tot
    for v, w in weighted:
        r -= w
        if r <= 0:
            return v
    return weighted[-1][0]


# --------------------------------------------------------------------- rock
# (part, height in plates, weight); depth comes from the part's geometry
RIB_PIECES = [("4460", 9, 4), ("60481", 6, 5), ("3040", 3, 2.5), ("3665", 3, 1.2),
              ("3004", 3, 0.6), ("3023", 1, 0.08)]
ONE_PIECES = [("3005", 3, 3), ("3062b", 3, 1), ("3024", 1, 0.15)]
SLANTED_TOP = {"4460", "60481", "3040", "54200", "4286", "3298", "3039", "30499", "3678b"}
FLAT_TOP = {"3004", "3023", "3622", "3623", "3005", "3024", "3062b"}

STYLES = {
    "rock": {"pieces": RIB_PIECES + [("4286", 3, 0.6), ("4287", 3, 0.3), ("3622", 3, 0.2)],
             "one": ONE_PIECES, "palette": ((DBG, 6), (LBG, 4)), "streak": 0.8},
    "earth": {"pieces": [("3040", 3, 3), ("4286", 3, 2), ("3665", 3, 0.7), ("3004", 3, 0.5),
                         ("3023", 1, 0.3), ("60481", 6, 1)],
              "one": [("3005", 3, 1), ("3024", 1, 0.5)],
              "palette": ((DTAN, 5), (RBROWN, 2), (DBROWN, 1)), "streak": 0.5},
    "grass": {"pieces": [("3040", 3, 3), ("4286", 3, 3), ("3023", 1, 0.2)],
              "one": [("3005", 3, 1), ("3024", 1, 0.5)],
              "palette": ((GREEN, 6), (DGREEN, 1)), "streak": 0.9},
}


def depth(part):
    i = info(part)
    if part in LONG_X:
        return round((i["hi"][0] - i["lo"][0]) / 20)
    return round((i["hi"][2] - i["lo"][2]) / 20)


def rib_sequence(rng, hb, pieces):
    seq, left = [], hb
    H = {p: h for p, h, _ in pieces}
    while left > 0:
        opts = [(p, w) for (p, h, w) in pieces if h <= left]
        if not opts:
            return None
        p = pick(rng, opts)
        seq.append(p)
        left -= H[p]
    return seq


OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}


def terrace(b, T, bands=(9,), base_y=0, seed=1, style=lambda c, k: "rock",
            grass=((GREEN, 1),), grass_cover=0.35,
            overhang=0.2, top_grass=True, ledge_grass=True, hidden=None, bare=None,
            top_color=None, wide=0.5):
    """Banded landform. T: {cell: number of bands}; band k exists where T > k.

    Each band is `bands[k]` plates of skin + core, then one bonding plate.
    Skin columns are slopes stacked to the band height, facing outward, styled
    per column by style(cell, band) -> 'rock' | 'earth' | 'grass'. Exposed
    bonding plates are grass (ledges and tops); bare(cell) -> True leaves that
    exposed cell as bare rock instead. Returns {cell: top height}.
    """
    rng = random.Random(seed)
    hidden = HIDDEN if hidden is None else hidden
    nb = max(T.values())
    bands = list(bands) + [bands[-1]] * (nb - len(bands))
    slanted_prev, floor, col_color = set(), None, {}
    tops = {}
    y0 = base_y
    for k in range(nb):
        hb = bands[k]
        A = {c for c, t in T.items() if t > k}
        if floor is not None:
            A = {c for c in A if c in floor or c in slanted_prev}
        A_next = {c for c, t in T.items() if t > k + 1}
        used, slanted, support = set(), set(), set()
        boundary = [c for c in sorted(A) if any(nbr(c, d) not in A for d in DIRS)]
        if not wide:
            rng.shuffle(boundary)   # (row order lets neighbouring columns pair up)
        for c in boundary:
            if c in used:
                continue
            st = STYLES[style(c, k)]
            dirs = [d for d in DIRS if nbr(c, d) not in A]
            rng.shuffle(dirs)
            placed = False
            for d in dirs:
                seq = None
                for attempt in range(6):
                    cand = rib_sequence(rng, hb, st["pieces"])
                    if not cand:
                        continue
                    D = max(depth(p) for p in cand)
                    if any(depth(p) != D for p in cand):
                        continue
                    cells = [c]
                    for i in range(1, D):
                        cells.append(nbr(cells[-1], OPP[d]))
                    if all(q in A and q not in used and q not in slanted_prev and
                           (floor is None or q in floor) for q in cells[1:]):
                        seq = cand
                        break
                if not seq:
                    continue
                base = col_color.get(c)
                if base is None or base not in dict(st["palette"]) or rng.random() > st["streak"]:
                    base = pick(rng, st["palette"])
                col_color[c] = base
                # try to pair with the next column along the face: one 2-wide column
                mate = None
                if wide and all(p_ in WIDE for p_ in seq) and rng.random() < wide:
                    for side in ({"N": "E", "S": "E", "E": "S", "W": "S"}[d], {"N": "W", "S": "W", "E": "N", "W": "N"}[d]):
                        m0 = nbr(c, side)
                        mc = [m0]
                        for i in range(1, D):
                            mc.append(nbr(mc[-1], OPP[d]))
                        if m0 in A and m0 not in used and nbr(m0, d) not in A and \
                                all(q in A and q not in used and q not in slanted_prev and (floor is None or q in floor)
                                    for q in mc[1:]):
                            mate = mc
                            break
                y = y0
                H = {p: h for p, h, _ in st["pieces"]}
                for part in seq:
                    colr = base if rng.random() < 0.85 else pick(rng, st["palette"])
                    if mate:
                        put_wide(b, WIDE[part], colr, cells, mate, d, y, note=f" rib{c}")
                    else:
                        put_slope(b, part, colr, c, d, y, D, note=f" rib{c}")
                    y += H[part]
                if mate:
                    used |= set(mate)
                    col_color[mate[0]] = base
                    support.add(mate[-1])
                    if seq[-1] in SLANTED_TOP:
                        slanted |= set(mate[:-1])
                    elif seq[-1] in FLAT_TOP:
                        support |= set(mate)
                used |= set(cells)
                support.add(cells[-1])
                if seq[-1] in SLANTED_TOP:
                    slanted |= set(cells[:-1])
                elif seq[-1] in FLAT_TOP:
                    support |= set(cells)
                placed = True
                break
            if not placed and c not in slanted_prev:
                base = col_color.get(c) or pick(rng, st["palette"])
                left, y = hb, y0
                H1 = {p: h for p, h, _ in st["one"]}
                while left > 0:
                    if left == 2:
                        b.put("54200", base, c[0], y, c[1], spin=rng.choice(dirs) if dirs else "N")
                        slanted.add(c)
                        left -= 2
                        y += 2
                        continue
                    part = pick(rng, [(p, w) for p, h, w in st["one"] if h <= left])
                    b.put(part, base, c[0], y, c[1])
                    left -= H1[part]
                    y += H1[part]
                used.add(c)
                if c not in slanted:
                    support.add(c)
        # hidden core: backing right behind the skin, sparse columns deeper in
        interior = A - used - slanted_prev
        backing = {c for c in interior if any((c[0] + i, c[1] + j) in used
                                               for i in (-1, 0, 1) for j in (-1, 0, 1))}
        holes = A - used - interior
        opened = slanted | holes
        seen = {c for c in backing if any(nbr(c, d) not in A or nbr(c, d) in opened for d in DIRS)}

        def face_color(c):
            return col_color.get(c) or STYLES[style(c, k)]["palette"][0][0]
        for colr, group in _group(seen, face_color).items():   # visible: wear the bank's colour
            _fill(b, group, y0, hb, colr)
        support |= seen          # (unseen backing is skipped: the skin's back studs carry the cap)
        deep = interior - seen
        cols = set()
        for (x, z) in sorted(deep):
            fp = {(x, z), (x + 1, z), (x, z + 1), (x + 1, z + 1)}
            if x % 8 == 7 and z % 8 == 7 and fp <= deep:   # 31/32, 63/64 ... straddle seams
                _fill(b, fp, y0, hb, hidden, note=" column")
                cols |= fp
        support |= cols

        def prop(c, deep=deep, cols=cols, y0=y0, hb=hb, support=support):
            if c not in deep or c in cols:
                return False
            for fp in ({c, (c[0] + 1, c[1]), (c[0], c[1] + 1), (c[0] + 1, c[1] + 1)},
                       {c, (c[0] - 1, c[1]), (c[0], c[1] - 1), (c[0] - 1, c[1] - 1)},
                       {c, (c[0] + 1, c[1])}, {c, (c[0], c[1] + 1)}, {c}):
                if fp <= deep and not fp & cols:
                    _fill(b, fp, y0, hb, hidden, note=" prop")
                    cols.update(fp)
                    support.update(fp)
                    return True
            return False
        b.step()
        # bonding / cap layer
        yb = y0 + hb
        layer = A - slanted
        exposed = layer - A_next
        hid = layer & A_next
        if (k == nb - 1 and top_grass) or (k < nb - 1 and ledge_grass):
            extra = {c for c in slanted if c not in A_next and rng.random() < grass_cover}
            lip = set()
            for c in exposed | extra:
                for d in DIRS:
                    o = nbr(c, d)
                    if o not in A and rng.random() < overhang / 2:
                        lip.add(o)
            green = exposed | extra | lip
            rocky = {c for c in exposed if bare and bare(c)}
            green -= rocky
            green -= {c for c in lip | extra if not any(nbr(c, d) in green for d in DIRS)}
            if top_color:
                special = {}
                for c in green:
                    tc = top_color(c)
                    if tc is not None:
                        special.setdefault(tc, set()).add(c)
                for tc, group in special.items():
                    green -= group
                    covered = _plates_supported(b, group, yb, support, rng, ((tc, 1),), prop=prop)
                    for c in covered:
                        tops[c] = yb + 1
            covered = _plates_supported(b, green, yb, support, rng, grass, prop=prop) | \
                {c for c in tops if tops[c] == yb + 1}
            for colr, group in _group(rocky, face_color).items():
                covered |= _plates_supported(b, group, yb, support, rng, ((colr, 1),), prop=prop)
        else:
            covered = _plates_supported(b, exposed, yb, support, rng, STYLES["rock"]["palette"])
        for c in covered:
            if c not in A_next:
                tops[c] = yb + 1
        hid_edge = {c for c in hid if any(nbr(c, d) not in layer for d in DIRS)}

        def hid_colour(fp):
            e = sorted(fp & hid_edge)
            return face_color(e[0]) if e else hidden
        covered |= _plates_supported(b, hid, yb, support, rng, ((hidden, 1),), prop=prop,
                                     colour_fn=hid_colour)
        b.step()
        slanted_prev, floor = slanted, covered
        y0 = yb + 1
    return tops


def _group(cells, colour_of):
    out = {}
    for c in cells:
        out.setdefault(colour_of(c), set()).add(c)
    return out


def _fill(b, cells, y0, h, color, note=" core"):
    """Fill a cell set from y0 for h plates: bricks then plates, courses staggered."""
    y, course = y0, 0
    while h - (y - y0) >= 3:
        for (x, z, w, d) in pack(cells, BRICKS, rotate=course % 2 == 1):
            put_rect(b, BRICKS, color, x, z, w, d, y, note=note)
        y += 3
        course += 1
    while y < y0 + h:
        for (x, z, w, d) in pack(cells, PLATES, rotate=course % 2 == 1):
            put_rect(b, PLATES, color, x, z, w, d, y, note=note)
        y += 1
        course += 1


def rock_mass(b, T, base_y=0, hb=9, seed=1, **kw):
    return terrace(b, T, bands=(hb,), base_y=base_y, seed=seed, **kw)


def _plates_supported(b, cells, y, support, rng, palette, rotate=False, prop=None, colour_fn=None):
    """Pack plates over cells; a plate with no supported cell under it gets a prop
    (if prop(cell) can make one) or is dropped. Returns the cells actually covered."""
    covered = set()
    for (x, z, w, d) in pack(set(cells), PLATES, rotate=rotate):
        fp = {(x + i, z + j) for i in range(w) for j in range(d)}
        if not fp & support and prop:
            for c in sorted(fp, key=lambda c: (abs(c[0] - x - w / 2) + abs(c[1] - z - d / 2))):
                if prop(c):
                    break
        if fp & support:
            put_rect(b, PLATES, colour_fn(fp) if colour_fn else pick(rng, palette), x, z, w, d, y)
            covered |= fp
        else:
            DROPPED.append((y, sorted(fp)))
    return covered


DROPPED = []


# --------------------------------------------------------------------- shapes
def value_noise(seed, scale):
    """Smooth 2D noise in [0, 1): bilinear interpolation of a random lattice."""
    rng = random.Random(seed)
    lat = {}

    def L(i, j):
        if (i, j) not in lat:
            lat[(i, j)] = random.Random(hash((seed, i, j))).random()
        return lat[(i, j)]

    def f(x, z):
        u, v = x / scale, z / scale
        i, j = int(u // 1), int(v // 1)
        fu, fv = u - i, v - j
        fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
        a = L(i, j) * (1 - fu) + L(i + 1, j) * fu
        c = L(i, j + 1) * (1 - fu) + L(i + 1, j + 1) * fu
        return a * (1 - fv) + c * fv
    return f


def levels(cells, field, thresholds):
    """{cell: number of thresholds the field exceeds} for cells with at least one."""
    out = {}
    for c in cells:
        n = sum(1 for t in thresholds if field(*c) > t)
        if n:
            out[c] = n
    return out


def clean(T, min_width=2):
    """Remove cells of each level that are thinner than min_width (no slivers)."""
    T = dict(T)
    for _ in range(3):
        for k in range(max(T.values(), default=0), 0, -1):
            A = {c for c, t in T.items() if t >= k}
            for c in list(A):
                ok = any(all((c[0] + i + a, c[1] + j + bb) in A for a in range(min_width) for bb in range(min_width))
                         for i in range(-min_width + 1, 1) for j in range(-min_width + 1, 1))
                if not ok:
                    T[c] = k - 1
        T = {c: t for c, t in T.items() if t > 0}
    return T


# --------------------------------------------------------------------- plants
def spin_r(rng):
    return rng.choice("NESW")


def tuft(b, rng, x, z, y, kind=None):
    """Something small on one stud at cell (x, z), surface height y."""
    kind = kind or pick(rng, [("leaf", 5), ("tabs", 2.5), ("flower", 1.2), ("big", 1)])
    cx, cz = x + 0.5, z + 0.5
    if kind == "speck":     # flat texture: dark green / olive 1x1 plates in the grass
        b.put(rng.choice(["3024", "3024", "6141"]), pick(rng, [(DGREEN, 4), (OLIVE, 1), (BGREEN, 1)]), x, y, z)
        return kind
    if kind == "fern":
        b.attach("2423", pick(rng, [(GREEN, 3), (DGREEN, 2), (BGREEN, 1)]), cx, cz, y, spin_r(rng))
        return kind
    if kind == "wildflower":   # stem with three flowers (3741 + 3742)
        stem = b.attach("3741a", GREEN, cx, cz, y, spin_r(rng))
        return kind
    if kind == "leaf":
        b.attach("32607", pick(rng, [(GREEN, 4), (BGREEN, 3), (DGREEN, 1), (OLIVE, 1)]), cx, cz, y, spin_r(rng))
    elif kind == "grass":
        b.attach("15279", pick(rng, [(GREEN, 3), (BGREEN, 2), (OLIVE, 2), (DGREEN, 1)]), cx, cz, y, spin_r(rng))
    elif kind == "tabs":
        b.attach("33291", pick(rng, [(GREEN, 2), (BGREEN, 3), (LIME, 1)]), cx, cz, y, spin_r(rng))
    elif kind == "flower":
        b.attach("24866", pick(rng, [(WHITE, 3), (14, 2), (4, 1), (13, 1), (22, 1)]), cx, cz, y, spin_r(rng))
    elif kind == "big":
        b.attach("6255", pick(rng, [(GREEN, 2), (BGREEN, 2), (DGREEN, 1)]), cx, cz, y, spin_r(rng))
    return kind


def fern(b, rng, x, z, y, color=None):
    b.attach("2423", color or pick(rng, [(GREEN, 3), (DGREEN, 2), (BGREEN, 1)]), x + 0.5, z + 0.5, y, spin_r(rng))


def bush(b, rng, x, z, y, size=1):  # noqa
    """Leafy bush on one stud (size 1) or a 2x2 (size 2) at cell (x, z)."""
    greens = [(GREEN, 3), (DGREEN, 2), (BGREEN, 1.5)]
    cx, cz = x + 0.5, z + 0.5
    if size == 1:
        b.attach("3062b", pick(rng, greens), cx, cz, y, soft=False)
        b.attach("2423", pick(rng, greens), cx, cz, y + 3, spin_r(rng))
        b.attach("6255", pick(rng, greens), cx, cz, y + 4, spin_r(rng))
    else:
        b.attach("3941", pick(rng, greens), x + 1, z + 1, y, soft=False)
        s = rng.choice("NESW")
        b.attach("2417", pick(rng, greens), x + 0.5, z + 0.5, y + 3, s)
        b.attach("2423", pick(rng, greens), x + 1.5, z + 1.5, y + 4, spin_r(rng))
        b.attach("32607", pick(rng, [(BGREEN, 1), (GREEN, 1)]), x + 0.5, z + 0.5, y + 4, spin_r(rng))


def tree(b, rng, x, z, y, kind="oak", size=1.0):
    """Tree whose trunk stands on cell (x, z) (oak/pine) or a 2x2 at (x, z) (prefab)."""
    cx, cz = x + 0.5, z + 0.5
    greens = [(GREEN, 3), (BGREEN, 2), (DGREEN, 1.5)]
    S = list("NESW")
    if kind == "prefab":
        b.attach("4032a", RBROWN, x + 1, z + 1, y, soft=False)
        b.attach(rng.choice(["3471", "2435"]), DGREEN, x + 1, z + 1, y + 1)
        return
    if kind == "pine":
        h = y
        for _ in range(3 if size >= 1 else 2):
            b.attach("3062b", RBROWN, cx, cz, h, soft=False)
            h += 3
        # wide skirts at the bottom, smaller toward the top
        tiers = ["2417", "2417", "2423", "2417", "2423", "2423", "32607"]
        if size < 1:
            tiers = ["2417", "2423", "2423", "32607"]
        rot = rng.randrange(4)
        for i, part in enumerate(tiers):
            b.attach(part, DGREEN if rng.random() < 0.8 else GREEN, cx, cz, h, S[(rot + i) % 4])
            h += 1
            if part == "2417" and i % 2 == 1:
                b.attach("3062b", DGREEN, cx, cz, h, soft=False)
                h += 3
        b.attach("4589", DGREEN, cx, cz, h, soft=False)    # cone tip
        return
    # oak: trunk, then a dense layered crown on a core of round bricks
    h = y
    trunk = 4 if size >= 1 else 2
    for _ in range(trunk):
        b.attach("3062b", RBROWN, cx, cz, h, soft=False)
        h += 3
    rot = rng.randrange(4)
    crown = ["2417", "2417", "2417", "2417", "2423", "2423", "2423", "32607"]
    if size < 1:
        crown = ["2417", "2417", "2423", "2423", "32607"]
    for i, part in enumerate(crown):
        if part == "spacer":
            b.attach("3062b", RBROWN, cx, cz, h, soft=False)
            h += 3
            continue
        b.attach(part, pick(rng, greens), cx, cz, h, S[(rot + i) % 4])
        h += 1


# --------------------------------------------------------------------- ground
def limit_steps(H, max_step=2, board=None):
    """Lower cells so no neighbour difference exceeds max_step (keeps peaks sane)."""
    H = dict(H)
    changed = True
    while changed:
        changed = False
        for c in list(H):
            for d in DIRS:
                n = nbr(c, d)
                hn = H.get(n, 0) if (board is None or n in board) else H[c]
                if H[c] - hn > max_step:
                    H[c] = hn + max_step
                    changed = True
    return H


def terrain(b, H, rng, top=((GREEN, 1),), side=None, soften=0.8, pillar=8,
            hidden=None, board=None, exclude=(), top_fn=None, neighbour_h=None):
    """Plate-built ground from a height map {cell: plates}.

    Two-plate shell under every surface, visible sides on steps, hidden 2x2
    pillars on a grid, plus extra props wherever a plate would be unsupported.
    Step edges that drop exactly two plates get a cheese slope on the low cell
    (probability `soften`). Returns {cell: surface height} incl. cheese cells.
    """
    side = side or top
    hidden = HIDDEN if hidden is None else hidden
    exclude = set(exclude)
    Hs = {c: h for c, h in H.items() if h > 0 and c not in exclude}
    board = board or set(Hs)

    def hn(c):
        if c in exclude:
            return neighbour_h.get(c, 99) if neighbour_h else 99
        return Hs.get(c, 0)

    occ = {}  # (x, z, level) -> True
    # cheese-slope softening on low cells at the foot of a 2-plate step
    cheese = {}
    for c, h in Hs.items():
        for d in DIRS:
            n = nbr(c, d)
            if n in exclude or n not in board and n not in Hs:
                continue
            if h - hn(n) == 2 and n not in cheese and rng.random() < soften:
                # facing away from the high cell
                cheese[n] = ({"N": "S", "S": "N", "E": "W", "W": "E"}[d], hn(n))
    # voxels
    vis, hid = {}, {}
    maxh = max(Hs.values(), default=0)
    for c, h in Hs.items():
        low = min([hn(nbr(c, d)) for d in DIRS] + [h])
        for l in range(max(0, h - 2), h):
            vis[(c, l)] = True
        for l in range(max(0, low), max(0, h - 2)):
            vis[(c, l)] = True          # visible side of a step
        if pillar and c[0] % pillar in (pillar - 1, 0) and c[1] % pillar in (pillar - 1, 0):
            for l in range(0, max(0, h - 2)):
                if (c, l) not in vis:
                    hid[(c, l)] = True
    surface = {}
    for l in range(maxh):
        lv = {c for (c, ll) in vis if ll == l}
        lh = {c for (c, ll) in hid if ll == l}
        for cells, palette in ((lv, None), (lh, ((hidden, 1),))):
            if not cells:
                continue
            for (x, z, w, d) in pack(cells, PLATES, rotate=l % 2 == 1):
                fp = [(x + i, z + j) for i in range(w) for j in range(d)]
                if l > 0 and not any((c, l - 1) in occ for c in fp):
                    _prop_down(b, fp, l, occ, hidden)
                if palette is None:
                    topcells = [c for c in fp if Hs[c] - 1 == l]
                    pal = top if len(topcells) * 2 >= len(fp) else side
                    if top_fn and topcells:
                        pal = top_fn(topcells[0]) or pal
                else:
                    pal = palette
                put_rect(b, PLATES, pick(rng, pal), x, z, w, d, l)
                for c in fp:
                    occ[(c, l)] = True
        b.step() if l % 3 == 2 else None
    for c, h in Hs.items():
        surface[c] = h
    for n, (face, h) in cheese.items():
        if n in Hs or h == 0 or (n, h - 1) in occ:
            b.put("54200", pick(rng, top), n[0], h, n[1], spin=face)
            surface[n] = None  # no studs here
    b.step()
    return surface


def _prop_down(b, fp, l, occ, hidden):
    """Hidden column under one cell of fp from the nearest support below up to l."""
    c = fp[len(fp) // 2]
    lo = l - 1
    while lo >= 0 and (c, lo) not in occ:
        lo -= 1
    y = lo + 1
    while l - y >= 3:
        b.put("3005", hidden, c[0], y, c[1], note=" prop hidden")
        occ[(c, y)] = occ[(c, y + 1)] = occ[(c, y + 2)] = True
        y += 3
    while y < l:
        b.put("3024", hidden, c[0], y, c[1], note=" prop hidden")
        occ[(c, y)] = True
        y += 1


def scatter(b, rng, surface, density=0.04, kinds=None, avoid=()):
    """Sprinkle tufts on surface cells (dict cell->height)."""
    avoid = set(avoid)
    for c in sorted(surface):
        if c in avoid or surface[c] is None or rng.random() > density:
            continue
        tuft(b, rng, c[0], c[1], surface[c], kind=pick(rng, kinds) if kinds else None)


def blob(cx, cz, rx, rz, noise, amp=0.35, rot=0.0):
    """Membership test for a noisy ellipse."""
    import math
    ca, sa = math.cos(rot), math.sin(rot)

    def inside(x, z):
        u, v = x + 0.5 - cx, z + 0.5 - cz
        u, v = u * ca + v * sa, -u * sa + v * ca
        r = math.hypot(u / rx, v / rz)
        return r < 1 + amp * (noise(x, z) - 0.5)
    return inside


def fringe(b, rng, tops, T, density=0.25, kinds=(("leaf", 5), ("tabs", 2), ("flower", 1), ("big", 1.5))):
    """Plants along the top edges of terraces (cells whose neighbour is lower)."""
    for c in sorted(tops):
        lower = any(T.get(nbr(c, d), 0) < T.get(c, 0) for d in DIRS)
        if lower and rng.random() < density:
            tuft(b, rng, c[0], c[1], tops[c], kind=pick(rng, list(kinds)))


def ground_fringe(b, rng, T, density=0.2, kinds=(("leaf", 5), ("tabs", 2), ("big", 2), ("flower", 1)),
                  board=None):
    """Plants on the baseplate along the foot of a landform."""
    foot = set()
    for c in T:
        for d in DIRS:
            n = nbr(c, d)
            if n not in T and (board is None or n in board):
                foot.add(n)
    for c in sorted(foot):
        if rng.random() < density:
            tuft(b, rng, c[0], c[1], 0, kind=pick(rng, list(kinds)))


def finish(b, hidden=None, default=DBG):
    """Recolour hidden structure that ended up visible (majority colour of its neighbours)."""
    from brickscape.core.brick import recolor_visible
    import collections
    hidden = HIDDEN if hidden is None else hidden

    def choose(p, near):  # noqa
        near = [c for c in near if c not in (hidden,)]
        if not near:
            return default
        return collections.Counter(near).most_common(1)[0][0]
    return recolor_visible(b, hidden, choose, flag=" hidden")


# --------------------------------------------------------------------- boulders
def _ring(b, rng, x, z, n, y, pal, top_stud=True):
    """Rounded n x n (n even >= 4) ring of slopes, corners 3045. Returns inner cells (studs)."""
    for (cx, cz, name) in ((x, z, "NW"), (x + n - 2, z, "NE"), (x, z + n - 2, "SW"), (x + n - 2, z + n - 2, "SE")):
        b.put("3045", pick(rng, pal), cx, y, cz, spin=CORNER_ROT[name])
    for i in range(2, n - 2, 2):
        for (sx, sz, face) in ((x + i, z, "N"), (x + i, z + n - 2, "S"), (x, z + i, "W"), (x + n - 2, z + i, "E")):
            if rng.random() < 0.5:
                b.put("3039", pick(rng, pal), sx, y, sz, spin=face)
            else:   # two 1-wide slopes, sometimes different
                for k in range(2):
                    fx = sx + (k if face in "NS" else 0)
                    fz = sz + (k if face in "EW" else 0)
                    part = pick(rng, [("3040", 3), ("3665", 0.6)]) if True else "3040"
                    if part == "3665":
                        part = "3040"
                    b.put(part, pick(rng, pal), fx, y, fz, spin=face)
    core = [(x + i, z + j) for i in range(2, n - 2) for j in range(2, n - 2)]
    if core:
        for (cx, cz, w, d) in pack(set(core), BRICKS):
            put_rect(b, BRICKS, HIDDEN, cx, cz, w, d, y)
    return [(x + i, z + j) for i in range(1, n - 1) for j in range(1, n - 1)]


CORNER_ROT = {"NE": "N", "SE": "E", "SW": "S", "NW": "W"}


def boulder(b, rng, x, z, size=4, pal=((DBG, 3), (LBG, 2)), y=0):
    """Rounded boulder with min corner (x, z). size 1, 2, 4 or 6 (studs)."""
    if size == 1:
        b.put("54200", pick(rng, pal), x, y, z, spin=spin_r(rng))
    elif size == 2:
        if rng.random() < 0.5:
            b.put("3045", pick(rng, pal), x, y, z, spin=spin_r(rng))
            # the 3045's single stud is in its inner corner; cap it
        else:
            b.put("3039", pick(rng, pal), x, y, z, spin=spin_r(rng))
    elif size == 4:
        _ring(b, rng, x, z, 4, y, pal)
        cap = rng.choice(["3045", "3039", "3040"])
        if cap == "3040":
            b.put("3040", pick(rng, pal), x + 1, y + 3, z + 1, spin=rng.choice("NS"))
            b.put("54200", pick(rng, pal), x + 2, y + 3, z + 1 + rng.randint(0, 1), spin=spin_r(rng))
        else:
            b.put(cap, pick(rng, pal), x + 1, y + 3, z + 1, spin=spin_r(rng))
    elif size == 6:
        _ring(b, rng, x, z, 6, y, pal)
        _ring(b, rng, x + 1, z + 1, 4, y + 3, pal)
        b.put(rng.choice(["3045", "3039"]), pick(rng, pal), x + 2, y + 6, z + 2, spin=spin_r(rng))


def rock(b, rng, cx, cz, rx, rz, bands=(6,), seed=0, base_y=0, taper=0.7, amp=0.45, rot=None,
         avoid=()):
    """Free-standing rock (boulder / outcrop) from rib bands on a noisy ellipse.
    Each higher band shrinks by `taper`. Top is bare rock, edges rounded with
    cheese / 45 slopes. Returns the cells used."""
    import math
    rot = rng.random() * math.pi if rot is None else rot
    T = {}
    for k in range(len(bands)):
        f = taper ** k
        inside = blob(cx, cz, rx * f, rz * f, value_noise(seed * 7 + k, 2.5), amp, rot)
        for x in range(int(cx - rx - 2), int(cx + rx + 3)):
            for z in range(int(cz - rz - 2), int(cz + rz + 3)):
                if inside(x, z) and (x, z) not in avoid and (k == 0 or T.get((x, z), 0) == k):
                    T[(x, z)] = k + 1
    T = clean(T, 2)
    if not T:
        return set()
    tops = terrace(b, T, bands=bands, base_y=base_y, seed=seed, top_grass=False, ledge_grass=False,
                   overhang=0)
    pal = STYLES["rock"]["palette"]
    done = set()
    for c, h in sorted(tops.items()):
        outs = [d for d in DIRS if T.get(nbr(c, d), 0) < T.get(c, 0)]
        r = rng.random()
        if outs and r < 0.8:
            b.put("54200", pick(rng, pal), c[0], h, c[1], spin=rng.choice(outs))
            done.add(c)
    # inner top cells: the odd 45 slope or round plate to break the flat top
    for c, h in sorted(tops.items()):
        if c in done:
            continue
        outs2 = [d for d in DIRS if nbr(c, d) in done]
        r = rng.random()
        if outs2 and r < 0.35:
            b.put("54200", pick(rng, pal), c[0], h, c[1], spin=rng.choice(outs2))
        elif r < 0.12:
            b.put("6141", pick(rng, pal), c[0], h, c[1])
    return set(T)


# --------------------------------------------------------------------- paths
def path_cells(points, wmin, wmax, seed=0, board=None):
    """Cells of a path along a polyline [(x, z), ...] with noisy width."""
    import math
    n = value_noise(seed, 6.0)
    cells = set()
    for (x0, z0), (x1, z1) in zip(points, points[1:]):
        L = math.hypot(x1 - x0, z1 - z0)
        steps = max(2, int(L * 3))
        for i in range(steps + 1):
            t = i / steps
            px, pz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            r = (wmin + (wmax - wmin) * n(px, pz)) / 2
            for x in range(int(px - r - 1), int(px + r + 2)):
                for z in range(int(pz - r - 1), int(pz + r + 2)):
                    if math.hypot(x + 0.5 - px, z + 0.5 - pz) <= r:
                        cells.add((x, z))
    if board is not None:
        cells &= board
    return cells


def dirt_path(b, rng, cells, y=0, colors=((DTAN, 1),), stones=0.07):
    """1-plate dirt track; loose stones and pale tan specks on top."""
    for (x, z, w, d) in pack(cells, PLATES, maxsize=12):
        put_rect(b, PLATES, pick(rng, colors), x, z, w, d, y)
    for c in sorted(cells):
        r = rng.random()
        if r < stones:
            part = rng.choice(["6141", "98138", "6141"])
            b.put(part, pick(rng, ((LBG, 3), (DBG, 2))), c[0], y + 1, c[1])
        elif r < stones * 2:
            b.put(rng.choice(["3024", "98138"]), TAN, c[0], y + 1, c[1])


def cobble_path(b, rng, cells, y=0, base=DTAN, stones=((LBG, 5), (DBG, 3), (TAN, 1)), cover=0.7):
    """Dark tan bed with round stones (2x2 and 1x1 round tiles), some gaps."""
    for (x, z, w, d) in pack(cells, PLATES, maxsize=12):
        put_rect(b, PLATES, base, x, z, w, d, y)
    free = set(cells)
    order = sorted(cells)
    rng.shuffle(order)
    for (x, z) in order:
        fp = {(x, z), (x + 1, z), (x, z + 1), (x + 1, z + 1)}
        if fp <= free and rng.random() < 0.45 * cover / 0.7:
            b.put("14769", pick(rng, stones), x, y + 1, z)
            free -= fp
    for c in sorted(free):
        if rng.random() < cover * 0.55:
            b.put(rng.choice(["98138", "98138", "6141"]), pick(rng, stones + ((base, 2),)), c[0], y + 1, c[1])


def edge_plants(b, rng, cells, density=0.2, board=None, y=0, avoid=()):
    """Tufts on cells just outside a region (e.g. along a path)."""
    around = {nbr(c, d) for c in cells for d in DIRS} - set(cells) - set(avoid)
    if board is not None:
        around &= board
    for c in sorted(around):
        if rng.random() < density:
            tuft(b, rng, c[0], c[1], y)


def pack_seams(cells, table, seams_x=(), seams_z=(), every=3, maxsize=None, rotate=False):
    """Like pack(), but first lays pieces straddling baseplate seams (every few studs),
    so features also tie the baseplates together."""
    cells = set(cells)
    out = []
    long_ = sorted([s for s in table if s[0] == 1 and s[1] in (4, 6)] + [s for s in table if s == (2, 4)],
                   key=lambda s: -s[0] * s[1])
    for sx in seams_x:
        zs = sorted({z for (x, z) in cells if x == sx - 1 and (sx, z) in cells})
        for z in zs[::every]:
            for (a, l) in long_:
                fp = {(sx - l // 2 + i, z + j) for i in range(l) for j in range(a)}
                if fp <= cells:
                    out.append((sx - l // 2, z, l, a)); cells -= fp; break
    for sz in seams_z:
        xs = sorted({x for (x, z) in cells if z == sz - 1 and (x, sz) in cells})
        for x in xs[::every]:
            for (a, l) in long_:
                fp = {(x + j, sz - l // 2 + i) for i in range(l) for j in range(a)}
                if fp <= cells:
                    out.append((x, sz - l // 2, a, l)); cells -= fp; break
    return out + pack(cells, table, rotate=rotate, maxsize=maxsize)
