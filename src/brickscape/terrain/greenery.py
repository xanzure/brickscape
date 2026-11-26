"""Greenery library: flowers, tufts, bushes, hedges, small trees, from real building techniques.


Everything is placed through FRAMES: a frame is an LDraw 12-tuple (x, y, z, 3x3 rotation) whose
origin is the base of a stud and whose local -y is the way that stud points. `on(b, F, part)`
puts a part on that stud and returns the frame of the part's top stud. Side studs (4733, 87087,
47905) give frames pointing sideways (SNOT), and flower stems (3741a, 19119, 24855) give angled
'slot' frames taken from the official LDraw composites (3741ac03, 19119c02, 24855c01).

All pieces are marked free (the stud checker can't judge angled parts); they really connect.
"""
import math
from brickscape.core.brick import info, _mul

GREEN, BGREEN, DGREEN, OLIVE, LIME, SGREEN = 2, 10, 288, 330, 27, 378
RED, DRED, PINK, DPINK, MAGENTA, WHITE, YELLOW, ORANGE, BLO, CORAL = 4, 320, 29, 5, 26, 15, 14, 25, 191, 353   # PINK = Bright Pink (GoBricks has no 13)
RBROWN, DBROWN, TAN, DTAN, LBG, DBG, BLACK = 70, 308, 19, 28, 71, 72, 0
LAV, MLAV = 31, 30

I = (0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1)


def T(x=0, y=0, z=0):
    return (x, y, z, 1, 0, 0, 0, 1, 0, 0, 0, 1)


def Ry(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (0, 0, 0, c, 0, s, 0, 1, 0, -s, 0, c)


def Rx(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (0, 0, 0, 1, 0, 0, 0, c, -s, 0, s, c)


def Rz(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (0, 0, 0, c, -s, 0, s, c, 0, 0, 0, 1)


def M(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = _mul(out, m)
    return out


# rotation taking local -y (a stud's direction) to an axis direction
TO = {(0, -1, 0): I, (0, 1, 0): Rx(180), (1, 0, 0): Rz(90), (-1, 0, 0): Rz(-90),
      (0, 0, -1): Rx(90), (0, 0, 1): Rx(-90)}

# angled slots on flower stems: (translation, rotation) of a 1x1 round plate on each stem end
def _slot(*v):
    return tuple(v)
SLOTS = {
    "3741a": [_slot(0, -17.628, 14.973, 1, 0, 0, 0, 0.96592, 0.25882, 0, -0.258825, 0.965919),
              _slot(-14.089, -22.458, -8.134, -0.5, 0.22415, -0.8365, 0, 0.96592, 0.25882, 0.86603, 0.12941, -0.48296),
              _slot(15.209, -27.287, -8.782, -0.5, -0.22415, 0.83651, 0, 0.96592, 0.25882, -0.86603, 0.12941, -0.48296)],
    "19119": [_slot(-16.5, -27.383, 0, 0.866025, 0.5, 0, -0.5, 0.866025, 0, 0, 0, 1),
              _slot(25.372, -12.235, 0, 0.34202, -0.939693, 0, 0.939693, 0.34202, 0, 0, 0, 1),
              _slot(8.25, -27.383, 14.289, -0.433013, -0.25, 0.866025, -0.5, 0.866025, 0, -0.75, -0.433013, -0.5),
              _slot(-12.686, -12.235, -21.973, -0.17101, 0.469846, 0.866025, 0.939693, 0.34202, 0, -0.296198, 0.813798, -0.5),
              _slot(8.25, -27.383, -14.289, -0.433013, -0.25, -0.866025, -0.5, 0.866025, 0, 0.75, 0.433013, -0.5),
              _slot(-12.686, -12.235, 21.973, -0.17101, 0.469846, -0.866025, 0.939693, 0.34202, 0, 0.296198, -0.813798, -0.5)],
    "24855": [_slot(0, -14.6829, 19.0279, 1, 0, 0, 0, 0.81915, 0.57358, 0, -0.57358, 0.81915),
              _slot(19.7074, -20.0073, -11.3781, -0.5, -0.49673, 0.70941, 0, 0.81915, 0.57358, -0.86603, 0.28679, -0.40958),
              _slot(-22.191, -24.1031, -12.812, -0.5, 0.49673, -0.70941, 0, 0.81915, 0.57358, 0.86603, 0.28679, -0.40958)],
}
# stems that plug a bar into a hollow stud: how far the origin sits above the stud base
BAR_UP = {"19119": -6, "24855": -16, "37695": 0, "15279": 0, "33183": 0, "99249": 0,
          "2566": -36, "1747": 0, "55236": 0, "28870": -6}


def put(b, part, colour, F):
    p = b.raw(part, colour, F)
    p.soft, p.free = True, True
    return p


def on(b, F, part, colour, turn=0):
    """Part on the stud of frame F (turned `turn` degrees about the stud). -> frame of its top stud
    (for bricks/plates) or of its origin (bar parts)."""
    F = M(F, Ry(turn))
    if part in BAR_UP:
        G = M(F, T(0, BAR_UP[part], 0))
        put(b, part, colour, G)
        return G
    h = info(part)["bottom"][0]
    G = M(F, T(0, -h, 0))
    put(b, part, colour, G)
    return G


def side(F, part, k, roll=0):
    """Frame of side stud k (0..3) of a SNOT brick whose top-stud frame is F (4733 / 47905 / 87087).
    roll turns the next part about that stud."""
    studs = [s for s in info(part)["studs"] if abs(s[1][1]) < 0.5]
    pos, d = studs[k % len(studs)]
    h = info(part)["bottom"][0]
    # the brick was placed with origin = F (its top); studs listed relative to its origin
    return M(F, T(*pos), TO[tuple(int(round(v)) for v in d)], Ry(roll))


def slots(F, stem):
    return [M(F, s) for s in SLOTS[stem]]


def ground(b, x, z, y=0, yaw=0):
    """Frame of the stud at board cell (x, z), top at height y plates."""
    return M(T(b.X(x) + 10, -8 * y, b.Z(z) + 10), Ry(yaw))


# ----------------------------------------------------------------- small plants (one stud)
def tuft(b, rng, x, z, y=0, kind="grass", colour=DGREEN, base=DGREEN):
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "4073", base)
    if kind == "grass":
        on(b, F, "15279", colour)
    elif kind == "twig":
        on(b, F, "33183", RBROWN)
    elif kind == "spiky":                    # bare 3-stem flower stem: a spiky tuft
        on(b, F, "3741a", colour)
    elif kind == "star":                     # bare 6-stem: a star-shaped tuft
        on(b, F, "19119", colour)
    elif kind == "fern":
        on(b, F, "2423", colour)
    elif kind == "leafy":
        on(b, F, "37695", colour)
    elif kind == "clover":
        on(b, F, "32607", colour)
    elif kind == "bigleaf":
        on(b, F, "6255", colour)


def flower(b, rng, x, z, y=0, colour=RED, leaf=BGREEN, kind="24866"):
    """A single flower on leaves: 1x1 round plate, 3-leaf plate, flower plate."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "4073", DGREEN)
    F = on(b, F, "32607", leaf, rng.uniform(0, 360))
    on(b, F, kind, colour)


def stem_flowers(b, rng, x, z, y=0, colours=(RED,), stem="3741a", stem_colour=GREEN, kind="24866",
                 leaf=None):
    """Flower stem (3 or 6 ends) with a flower plate on every end; optional 3-leaf base."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "4073", DGREEN)
    if leaf is not None:
        F = on(b, F, "32607", leaf, rng.uniform(0, 360))
    G = on(b, F, stem, stem_colour)
    for s in slots(G, stem):
        put(b, kind, rng.choice(colours), s)


def flower_clump(b, rng, x, z, y=0, colours=(RED, PINK), leaf=BGREEN, n=2):
    """Leafy flower clump (the video's 3rd/4th rows): stacked 3-leaf plates at different turns with
    a flower stem in the middle and flower plates on the leaf studs."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "3062b", DGREEN)
    for i in range(n):
        F = on(b, F, "32607", leaf, rng.uniform(60, 180))
    G = on(b, F, "3741a", GREEN, rng.uniform(0, 360))
    for s in slots(G, "3741a"):
        L = M(s, T(0, -8, 0))          # a leaf plate under each flower makes it bushier
        put(b, "32607", leaf, M(s, Ry(rng.uniform(0, 360))))
        put(b, "24866", rng.choice(colours), M(L, T(0, 0, 0)))


# ----------------------------------------------------------------- bushes (SNOT cores)
def snot_bush(b, rng, x, z, y=0, levels=2, leaf=(GREEN, BGREEN), flowers=(), flower_p=0.4,
              top=True, leaf_part="32607", core=DGREEN):
    """Round bush: a column of 1x1 bricks with studs on 4 sides (4733), a 3-leaf plate on every side
    stud (leaves droop out), more on top. flowers: colours for flower plates on some leaf studs."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "4073", core)
    leaves = []
    for lv in range(levels):
        C = F
        F = on(b, F, "4733", core)
        for k in range(4):
            S = side(F, "4733", k, rng.uniform(-40, 40))
            leaves.append(on(b, S, leaf_part, rng.choice(leaf), rng.uniform(0, 360)))
    if top:
        F = on(b, F, "32607", rng.choice(leaf), rng.uniform(0, 360))
        F = on(b, F, "32607", rng.choice(leaf), rng.uniform(100, 200))
        leaves.append(F)
    for L in leaves:
        if flowers and rng.random() < flower_p:
            on(b, L, "24866", rng.choice(flowers))   # 33291: no GoBricks colour data
    return F


def wide_bush(b, rng, x, z, y=0, w=3, d=2, levels=2, leaf=(GREEN, BGREEN), flowers=(), flower_p=0.35):
    """A bigger mound / hedge piece: several SNOT columns packed together, centre ones taller."""
    for i in range(w):
        for j in range(d):
            lv = levels + (1 if (0 < i < w - 1 and 0 < j < d - 1) or (w <= 2 and rng.random() < .5) else 0) \
                 - (1 if rng.random() < 0.3 else 0)
            snot_bush(b, rng, x + 2 * i, z + 2 * j, y, max(1, lv), leaf, flowers, flower_p)


def cypress(b, rng, x, z, y=0, levels=5, leaf=(DGREEN,), trunk=RBROWN):
    """Tall narrow column tree: brown trunk, a stack of SNOT cores with dark leaves, tapering."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "3062b", trunk)
    for lv in range(levels):
        F = on(b, F, "4733", DGREEN)
        n = 4 if lv < levels - 1 else 2
        for k in range(n):
            on(b, side(F, "4733", k + lv, rng.uniform(-30, 30)), "32607", rng.choice(leaf), rng.uniform(0, 360))
    F = on(b, F, "32607", rng.choice(leaf), 0)
    on(b, F, "32607", rng.choice(leaf), 120)


def fern_clump(b, rng, x, z, y=0, colour=DGREEN, n=3):
    """Fern / hosta: 4x3 leaves stacked on a round 1x1 core, each turned ~120 degrees."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "3062b", colour)
    for i in range(n):
        on(b, F, "2423", colour, i * 360 / n + rng.uniform(-15, 15))
        F = on(b, F, "4073", colour)


def big_leaf_plant(b, rng, x, z, y=0, colour=GREEN, n=3, flowers=()):
    """Big-leaf clump (the video's 'agave' row): 3-large-leaf plants stacked on round plates."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "4073", DGREEN)
    for i in range(n):
        F = on(b, F, "6255", colour, i * 47)
    if flowers:
        G = on(b, F, "3741a", GREEN)
        for s in slots(G, "3741a"):
            put(b, "24866", rng.choice(flowers), s)


def sword_plant(b, rng, x, z, y=0, colour=DGREEN):
    """Spiky dark-green plant: palm leaves (6148) splayed round a round brick, drooping."""
    F = on(b, ground(b, x, z, y, 0), "3062b", colour)
    G = on(b, F, "4073", colour)
    for k in range(5):
        put(b, "6148", colour, M(G, Ry(k * 72 + rng.uniform(-10, 10)), Rz(-25), T(10, -6, 0)))


def bamboo(b, rng, x, z, y=0, n=5, colour=GREEN, leaf=GREEN):
    """Bamboo / spindly young tree: bamboo plant bricks (30176) stacked, each turned."""
    F = ground(b, x, z, y, rng.uniform(0, 360))
    for i in range(n):
        F = on(b, F, "30176", colour if i < n - 1 else leaf, i * 70 + rng.uniform(-15, 15))


def pine(b, rng, x, z, y=0, n=4, colour=DGREEN):
    """Spiky young pine (video, back right): a brown round trunk with bare 6-stem whorls."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "3062b", RBROWN)
    for i in range(n):
        F = on(b, F, "3062b", RBROWN)
        on(b, F, "19119", colour, i * 37)
        F = on(b, F, "4073", RBROWN)
    on(b, F, "15279", colour)


# ----------------------------------------------------------------- trees from the references
def birch(b, rng, x, z, y=0, leaf=(YELLOW, ORANGE, BLO), height=9, arms=2):
    """Birch: white 1x1 round bricks with black 1x1 round plates between (the bark
    bands), side arms out of 1x1 bricks with a side stud, and flat star crowns (6-stem flower
    stems) with leaf plates on every end. leaf colours: autumn by default (as in the ref)."""
    F = ground(b, x, z, y, rng.uniform(0, 360))
    arm_at = sorted(rng.sample(range(3, height - 1), arms))
    for i in range(height):
        if i in arm_at:
            F = on(b, F, "87087", WHITE)
            S = side(F, "87087", 0, 0)
            S = on(b, S, "4073", WHITE)
            S = M(S, Rx(-55))                   # the arm leans upward
            G = on(b, S, "19119", ORANGE if leaf[0] in (YELLOW, ORANGE, BLO) else GREEN)
            for s in slots(G, "19119"):
                if rng.random() < 0.6:
                    put(b, "32607", rng.choice(leaf), M(s, Ry(rng.uniform(0, 360))))
        else:
            F = on(b, F, "3062b", WHITE, rng.uniform(0, 360))
        if rng.random() < 0.45:
            F = on(b, F, "4073", BLACK)
    for crown in range(2):
        G = on(b, F, "19119", (ORANGE if crown == 0 else YELLOW) if leaf[0] in (YELLOW, ORANGE, BLO) else GREEN, crown * 30)
        for s in slots(G, "19119"):
            put(b, "32607", rng.choice(leaf), M(s, Ry(rng.uniform(0, 360))))
        if crown == 0:
            F = on(b, F, "4073", WHITE)
            F = on(b, F, "3062b", WHITE)
    on(b, F, "32607", rng.choice(leaf), 0)


def palm(b, rng, x, z, y=0, height=6, lean=6, leaf=GREEN, trunk=RBROWN):
    """Oasis palm: reddish-brown round trunk with ring plates, a palm top (2566) and drooping
    small palm leaves (6148) round it; a slight lean by offsetting ring plates."""
    F = ground(b, x, z, y, rng.uniform(0, 360))
    for i in range(height):
        F = on(b, F, "3062b", trunk)
        F = on(b, F, "4073", DBROWN if i % 2 else trunk)
        F = M(F, Rz(lean / height))
    G = on(b, F, "2566", trunk)
    for k in range(5):
        put(b, "6148", leaf, M(G, T(0, -30, 0), Ry(k * 72 + rng.uniform(-12, 12)), Rz(-20), T(10, 0, 0)))


def cactus(b, rng, x, z, y=0, height=4, colour=OLIVE, arms=((1, 0), (2, 2))):
    """Mojave saguaro: a column of round bricks; each arm = a SNOT brick in the column, a sideways
    round brick, a 1x1 brick with a side stud turned so the stud points up, then round bricks up."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), "4073", colour)
    for i in range(height):
        arm = [k for (lv, k) in arms if lv == i]
        if arm:
            F = on(b, F, "4733", colour)
            for k in arm:
                S = side(F, "4733", k)
                S = on(b, S, "3062b", colour)
                E = on(b, S, "87087", colour, 90)    # turned so its side stud points up
                # 87087's side stud: make it point up (world -y)
                U = side(E, "87087", 0)
                up = U
                for j in range(1 + (i % 2)):
                    up = on(b, up, "3062b", colour)
                on(b, up, "4073", colour)
        else:
            F = on(b, F, "3062b", colour)
    on(b, F, "4073", colour)
    on(b, ground(b, x + 1, z, y), "32607", OLIVE)


def hanging_vine(b, rng, x, z, y_top, n=4, colour=BGREEN, face="N"):
    """Curtain of leaves hanging down a face: a hidden column of 1x1 bricks with a side stud, a 4x3
    leaf on each side stud turned so the leaf hangs down (waterfall photo, left)."""
    F = ground(b, x, z, y_top - 3 * n, 0)
    k = {"E": 0, "N": 1, "W": 2, "S": 3}[face]     # 4733 side studs: +x, -z, -x, +z
    for i in range(n):
        F = on(b, F, "4733", DGREEN)
        S = side(F, "4733", k, rng.uniform(-20, 20))   # roll 0: the leaf hangs DOWN
        on(b, S, "2423", rng.choice((colour, colour, GREEN)), 0)


# ================================================================= trees v2 (2026-11-25)
def _pos(F):
    return F[:3]


def flat(F, yaw=0):
    """Level frame at F's position (drop its tilt), turned yaw degrees."""
    return M(T(*_pos(F)), Ry(yaw))


def short_limb(b, F_brick, colour, yaw=0, droop=False):
    """Short curved arm: a Tail End Section (40379) with its bar end in a 6541's hole. -> tip."""
    F = M(F_brick, Ry(yaw), T(0, 10, -10), Ry(180), Rx(-40 if droop else 0))
    put(b, "40379", colour, M(F, T(0, 0, 7.5)))
    return M(F, T(0, -60, 78))


def tail_limb(b, F_brick, colour, yaw=0, end=True, droop=False):
    """Curved limb out of a 1x1 Technic brick with a hole (6541) whose origin frame is F_brick:
    a Tail Middle Section (40378) pinned into the hole, curving out ~6 studs and up; optionally a
    Tail End Section (40379) on its tip. -> tip frame (level)."""
    F = M(F_brick, Ry(yaw), T(0, 10, -10), Ry(180))     # pin into the hole from the -z face
    if droop:
        F = M(F, Rx(-35))                                 # branch dips, then the tip hangs
    put(b, "40378", colour, F)
    tip = M(F, T(0, -36, 120), Rx(45))
    if end:
        put(b, "40379", colour, tip)
        tip = M(tip, T(0, -50, 60))
    return tip


def _spray(b, rng, F, leaves, fill=0.35, fill_part="32607"):
    """A 6x5 leaf branch (2417) on frame F with some leaf plates on its studs for fullness."""
    C = on(b, F, "2417", rng.choice(leaves), rng.uniform(0, 360))
    for st, _d in info("2417")["studs"]:
        if rng.random() < fill:
            put(b, fill_part, rng.choice(leaves), M(C, T(*st), T(0, -8, 0), Ry(rng.uniform(0, 360))))
    return C


OAK_SIZES = {   # trunk width (1 round / 2 round / 3 log pinwheel), trunk bricks, limbs, crown tiers, crown radius
    "small":  dict(w=1, h=3, limbs=1, tiers=2, r=1.2, n=4),
    "medium": dict(w=2, h=4, limbs=2, tiers=2, r=2.0, n=6),
    "tall":   dict(w=2, h=8, limbs=3, tiers=3, r=1.8, n=6),
    "fat":    dict(w=3, h=4, limbs=3, tiers=3, r=3.2, n=8),
    "big":    dict(w=3, h=6, limbs=4, tiers=3, r=3.0, n=8),
}


def oak2(b, rng, x, z, y=0, size="medium", leaves=(GREEN, GREEN, DGREEN), bark=RBROWN, yaw=None):
    """Oak: flared root base (cheese slopes and
    log bricks), a trunk (round bricks, or log bricks pinwheeled round a 1x1 core when fat),
    curved tail-section limbs out of Technic bricks carrying flat 6x5 leaf sprays, and a crown of
    overlapping 6x5 sprays in rings, one plate apart so they stack on each other.
    (x, z) = the trunk's centre cell (for w=3 the pinwheel's core)."""
    P = OAK_SIZES[size]
    yaw = rng.uniform(0, 360) if yaw is None else yaw
    w, H = P["w"], P["h"] + rng.choice((0, 0, 1))
    # roots: cheese slopes round the base, a few 2x1 45s pointing out on fat trunks
    rad = {1: 1, 2: 1, 3: 2}[w]
    for dx in range(-rad, rad + 1 + (w == 2)):
        for dz in range(-rad, rad + 1 + (w == 2)):
            inside = (w == 1 and (dx, dz) == (0, 0)) or (w == 2 and dx in (0, 1) and dz in (0, 1)) or \
                     (w == 3 and abs(dx) <= 1 and abs(dz) <= 1)
            if inside:
                continue
            ring = max(abs(dx - (0.5 if w == 2 else 0)), abs(dz - (0.5 if w == 2 else 0)))
            if ring <= rad + 0.5 and rng.random() < (0.75 if w > 1 else 0.5):
                d = "N" if abs(dz) >= abs(dx) and dz < 0 else "S" if abs(dz) >= abs(dx) else "W" if dx < 0 else "E"
                p = b.put("54200", bark, x + dx, 0 + y, z + dz, spin={"N": "N", "S": "S", "E": "E", "W": "W"}[d])
                p.soft = p.free = True   # (on a rise edge a root may overhang a plate)
    # trunk
    core = ground(b, x, z, y, 0) if w != 2 else M(T(b.X(x) + 20, -8 * y, b.Z(z) + 20), Ry(0))
    F = core
    limb_at = sorted(rng.sample(range(1, H), min(P["limbs"], H - 1)))
    for lv in range(H):
        if w == 1:
            if lv in limb_at:
                F = on(b, F, "6541", bark, rng.uniform(0, 360))
                tip = tail_limb(b, F, bark, rng.uniform(0, 360), end=False)
                _spray(b, rng, flat(tip), leaves)
            else:
                F = on(b, F, "3062b", bark)
        elif w == 2:
            F = on(b, F, "3941", bark if rng.random() < 0.75 else DBROWN, rng.choice((0, 45)))
            if rng.random() < 0.35:                       # bark ring
                F = on(b, F, "4032a", DBROWN if rng.random() < .5 else bark, rng.uniform(0, 90))
            if lv in limb_at:            # limb from a 6541 against the trunk side (on a side plate)
                ang = rng.uniform(0, 360)
                G = M(F, Ry(ang), T(0, 24, -30))
                put(b, "6541", bark, M(G, T(0, -24, 0)))
                tip = tail_limb(b, M(G, T(0, -24, 0)), bark, 0, end=rng.random() < 0.4)
                _spray(b, rng, flat(tip), leaves)
        else:                            # log pinwheel round a 1x1 core
            Fc = M(core, T(0, -24 * lv, 0))
            for k in range(4):
                put(b, "30136", bark if rng.random() < 0.8 else DBROWN, M(Fc, Ry(90 * k), T(-10, -24, -20)))
            if lv in limb_at:
                put(b, "6541", bark, M(Fc, T(0, -24, 0)))
                tip = tail_limb(b, M(Fc, T(0, -24, 0)), bark, rng.uniform(0, 360), end=rng.random() < 0.6)
                _spray(b, rng, flat(tip), leaves)
            else:
                put(b, "3005", bark, M(Fc, T(0, -24, 0)))
            F = M(core, T(0, -24 * (lv + 1), 0))
    # crown: rings of 6x5 sprays, one plate apart, getting smaller towards the top
    top = F
    for t in range(P["tiers"]):
        n = max(3, P["n"] - 2 * t)
        r = P["r"] * (1 - 0.3 * t)
        base = M(top, T(0, -8 * (2 * t + 1), 0))
        for k in range(n):
            a = math.radians(360 * k / n + yaw + t * 23 + rng.uniform(-15, 15))
            rr = r * 20 * rng.uniform(0.8, 1.15)
            S = M(base, T(rr * math.cos(a), -8 * (k % 2), rr * math.sin(a)))
            _spray(b, rng, flat(S), leaves, fill=0.45 if t == 0 else 0.6)
        put(b, "4073", bark, M(base, T(0, 8, 0)))   # stem plate between tiers
    _spray(b, rng, flat(M(top, T(0, -8 * (2 * P["tiers"] + 1), 0))), leaves, fill=0.6)


# ================================================================= botanical parts (2026-11-25)
# From the Canada First Bricks botanical list + unusual GoBricks parts. All grow from one stud.
def _base(b, rng, x, z, y, part="4073", colour=DGREEN):
    return on(b, ground(b, x, z, y, rng.uniform(0, 360)), part, colour)


def tooth_rosette(b, rng, x, z, y=0, colour=GREEN, levels=4, centre=None):
    """Agave / spiky rosette: 1x1 plates with an in-line tooth (49668) stacked on one stud, each
    turned ~90-110 degrees, so the teeth fan out like leaves. centre: a flower plate on top."""
    F = _base(b, rng, x, z, y, "3062b", DGREEN)
    for i in range(levels):
        F = on(b, F, "49668", colour, 95 * i + rng.uniform(-15, 15))
    if centre is not None:
        on(b, F, "24866", centre)


def tooth_flower(b, rng, x, z, y=0, petal=WHITE, centre=YELLOW, stem=GREEN):
    """Daisy: perpendicular-tooth plates (15070, teeth pointing up) can't fan, so use in-line tooth
    plates (49668) in the petal colour, 4 levels, on a green stem brick; flower plate centre."""
    F = _base(b, rng, x, z, y, "3062b", stem)
    F = on(b, F, "32607", stem, rng.uniform(0, 360))
    for i in range(4):
        F = on(b, F, "49668", petal, 90 * i + 45 * (i % 2) + rng.uniform(-8, 8))
    on(b, F, "4073", centre)


def frond_fern(b, rng, x, z, y=0, colour=GREEN, n=3):
    """Big fern: feathered wings (11100) as fronds round a round brick, leaning out."""
    F = _base(b, rng, x, z, y, "3062b", DGREEN)
    G = on(b, F, "4073", DGREEN)
    for k in range(n):
        put(b, "11100", colour, M(G, Ry(360 * k / n + rng.uniform(-20, 20)), Rx(-25), T(0, -10, 0)))


def plume_grass(b, rng, x, z, y=0, colour=OLIVE, n=1):
    """Tall grass / reeds: triple plume (64647) or feather plume (30126) on a round plate."""
    F = _base(b, rng, x, z, y, "4073", DGREEN)
    on(b, F, "64647" if rng.random() < .6 else "30126", colour, rng.uniform(0, 360))


def swirl_topiary(b, rng, x, z, y=0, colour=DGREEN, trunk=RBROWN, h=2):
    """Clipped topiary / pine sapling: a round-brick trunk and swirl-top round plates (15470)."""
    F = _base(b, rng, x, z, y, "4073", trunk)
    for _ in range(h):
        F = on(b, F, "3062b", trunk)
    on(b, F, "15470", colour)


def beehive_conifer(b, rng, x, z, y=0, colour=DGREEN, trunk=RBROWN, tiers=2):
    """Small conifer: brown round brick, stacked beehive cones (35574, ridged 2x2), a 1x1 cone tip."""
    F = M(T(b.X(x) + 20, -8 * y, b.Z(z) + 20), Ry(rng.uniform(0, 360)))
    F = on(b, F, "3941", trunk)
    for _ in range(tiers):
        F = on(b, F, "35574", colour, rng.uniform(0, 90))
    on(b, F, "59900", colour)


def spine_fern(b, rng, x, z, y=0, colour=DGREEN, n=3):
    """Spiky fronds: Barraki spines / spiked vine (55236) radiating from a round plate."""
    F = _base(b, rng, x, z, y, "3062b", colour)
    for k in range(n):
        put(b, "55236", colour, M(F, Ry(360 * k / n + rng.uniform(-15, 15)), Rz(25)))


def coral_bush(b, rng, x, z, y=0, colour=OLIVE, leaf=None):
    """Bare / dead bush or small tree: the thallus (49577) on a round brick; leaf plates on its
    side studs if leaf is given (a sparse shrub)."""
    F = _base(b, rng, x, z, y, "3062b", RBROWN)
    G = on(b, F, "49577", colour)
    if leaf:
        for st, d in info("49577")["studs"]:
            put(b, "32607", rng.choice(leaf), M(G, T(*st), TO[tuple(int(round(v)) for v in d)], T(0, -8, 0), Ry(rng.uniform(0, 360))))


def curl_vine(b, rng, x, z, y=0, colour=GREEN):
    """Curly tendril / fiddlehead: the bent flexible whip (88704) on a round plate."""
    F = _base(b, rng, x, z, y, "4073", DGREEN)
    put(b, "88704", colour, M(F, Ry(rng.uniform(0, 360))))


def crystal_succulent(b, rng, x, z, y=0, colour=SGREEN, n=3):
    """Succulent cluster: 1x1 5-point crystals (30385) on round plates, in a little clump."""
    for i in range(n):
        F = on(b, ground(b, x + (i % 2), z + (i // 2), y, rng.uniform(0, 360)), "4073", colour)
        put(b, "30385", colour, F)


def sword_clump(b, rng, x, z, y=0, colour=DGREEN):
    """Swordleaf (10884) clipped on a 3L bar in a round brick: a big arching leaf plant (hosta)."""
    F = _base(b, rng, x, z, y, "3062b", DGREEN)
    for k in range(2):
        put(b, "10884", colour, M(F, T(0, -8 - 10 * k, 0), Ry(90 * k + rng.uniform(-20, 20)), Rx(-20), T(0, -30, 0)))


def specimen(b, rng, x, z, part, colour, y=0, base="4073", base_colour=DGREEN):
    """One plant part on its own round plate (for the parts catalogue rows)."""
    F = _base(b, rng, x, z, y, base, base_colour)
    if part in ("3565", "15469", "4727", "4728", "2682a", "35473"):
        return on(b, F, part, colour)
    if part in SLOTS:
        G = on(b, F, part, colour)
        for s in slots(G, part):
            put(b, "3742", rng.choice((WHITE, YELLOW)), s)
        return G
    return on(b, F, part, colour)
