"""Greenery library: flowers, tufts, bushes, hedges, small trees, from real building techniques.


Everything is placed through FRAMES: a frame is an LDraw 12-tuple (x, y, z, 3x3 rotation) whose
origin is the base of a stud and whose local -y is the way that stud points. `on(b, F, part)`
puts a part on that stud and returns the frame of the part's top stud. Side studs (4733, 87087,
47905) give frames pointing sideways (SNOT), and flower stems (3741a, 19119, 24855) give angled
'slot' frames taken from the official LDraw composites (3741ac03, 19119c02, 24855c01).

All pieces are marked free (the stud checker can't judge angled parts); they really connect.
"""
import functools, math
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


OPEN = "85861"      # 1x1 round plate with OPEN stud: bar-ended stems need the hollow stud
FIT = True          # decorative parts that clash are turned about their stud, or left out


def decorative(part):
    d = info(part)["desc"].lower()
    return any(w in d for w in ("plant", "leaf", "leaves", "flower", "grass", "vine", "stem", "bush"))


def put(b, part, colour, F):
    """Place a part at frame F. A part that clashes with its neighbours is left out (returns
    None); a decorative one is first tried at 7 more turns about its own axis."""
    if F is None:
        return None
    turns = (0, 45, 90, 135, 180, 225, 270, 315) if FIT and decorative(part) else (0,)
    from brickscape.core.space import fits
    for t in turns:
        p = b.raw(part, colour, M(F, Ry(t)) if t else F)
        if not FIT or fits(b, len(b.pieces) - 1):
            return p
        b.pop()
    return None


@functools.lru_cache(None)
def bar_down(part):
    """True if the part plugs in with a bar pointing down (flower stems, plumes, palm tops)."""
    from brickscape.core.snaps import part_snaps
    S, _ = part_snaps(part)
    return any(s.kind == "cyl" and s.gender == "M" and s.radius < 5.5 and -s.R[1, 1] > 0.99
               and abs(s.pos[0]) < 1 and abs(s.pos[2]) < 1 for s in S)


def seat(b, part, colour, F, turns=None):
    """Slide a bar-ended part down the stud axis of F to the deepest spot where its bar is held
    (a real connection to a neighbour) and nothing clashes. Tries turns for decorative parts."""
    from brickscape.core.space import fits, joined
    if turns is None:
        turns = (0, 45, 90, 135, 180, 225, 270, 315) if FIT and decorative(part) else (0,)
    for t in turns:
        R = M(F, Ry(t)) if t else F
        for dy in range(16, -40, -1):
            p = b.raw(part, colour, M(R, T(0, dy, 0)))
            i = len(b.pieces) - 1
            held = any(joined(p, b.pieces[j]) for j in b.near(i))
            if held and (not FIT or fits(b, i)):
                return p
            b.pop()
    return None


def on(b, F, part, colour, turn=0):
    """Part on the stud of frame F (turned `turn` degrees about the stud). -> frame of its top stud
    (for bricks/plates) or of its origin (bar parts)."""
    if F is None:
        return None
    F = M(F, Ry(turn))
    if bar_down(part):
        p = seat(b, part, colour, F)
        return p.M if p is not None else None
    h = info(part)["bottom"][0]
    G = M(F, T(0, -h, 0))
    p = put(b, part, colour, G)
    return p.M if p is not None else None


def side(F, part, k, roll=0):
    if F is None:
        return None
    """Frame of side stud k (0..3) of a SNOT brick whose top-stud frame is F (4733 / 47905 / 87087).
    roll turns the next part about that stud."""
    studs = [s for s in info(part)["studs"] if abs(s[1][1]) < 0.5]
    pos, d = studs[k % len(studs)]
    h = info(part)["bottom"][0]
    # the brick was placed with origin = F (its top); studs listed relative to its origin
    return M(F, T(*pos), TO[tuple(int(round(v)) for v in d)], Ry(roll))


def slots(F, stem):
    if F is None:
        return []
    return [M(F, s) for s in SLOTS[stem]]


def ground(b, x, z, y=0, yaw=0):
    """Frame of the stud at board cell (x, z), top at height y plates."""
    return M(T(b.X(x) + 10, -8 * y, b.Z(z) + 10), Ry(yaw))


# ----------------------------------------------------------------- small plants (one stud)
def tuft(b, rng, x, z, y=0, kind="grass", colour=DGREEN, base=DGREEN):
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), OPEN, base)
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
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), OPEN, DGREEN)
    F = on(b, F, "32607", leaf, rng.uniform(0, 360))
    on(b, F, kind, colour)


def stem_flowers(b, rng, x, z, y=0, colours=(RED,), stem="3741a", stem_colour=GREEN, kind="24866",
                 leaf=None):
    """Flower stem (3 or 6 ends) with a flower plate on every end; optional 3-leaf base."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), OPEN, DGREEN)
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
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), OPEN, core)
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
    for i in range(n):                       # each leaf on the stud of the plate below it
        F = on(b, F, "2423", colour, i * 360 / n + rng.uniform(-15, 15))
        F = on(b, F, OPEN, colour)


def big_leaf_plant(b, rng, x, z, y=0, colour=GREEN, n=3, flowers=()):
    """Big-leaf clump (the video's 'agave' row): 3-large-leaf plants stacked on round plates."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), OPEN, DGREEN)
    for i in range(n):
        F = on(b, F, "6255", colour, i * 47)
    if flowers:
        G = on(b, F, "3741a", GREEN)
        for s in slots(G, "3741a"):
            put(b, "24866", rng.choice(flowers), s)


def sword_plant(b, rng, x, z, y=0, colour=DGREEN):
    """Spiky dark-green plant: palm leaves (6148) splayed round a round brick, drooping."""
    F = on(b, ground(b, x, z, y, 0), "3062b", colour)
    G = on(b, F, OPEN, colour)
    for k in range(5):
        put(b, "6148", colour, M(G, Ry(k * 72 + rng.uniform(-10, 10)), Rz(-25), T(10, -6, 0)))


def bamboo(b, rng, x, z, y=0, n=5, colour=GREEN, leaf=GREEN):
    """Bamboo / spindly young tree: bamboo plant bricks (30176) stacked, each turned."""
    F = ground(b, x, z, y, rng.uniform(0, 360))
    for i in range(n):
        F = on(b, F, "30176", colour if i < n - 1 else leaf, i * 70 + rng.uniform(-15, 15))


def pine(b, rng, x, z, y=0, n=4, colour=DGREEN):
    """Young pine: a brown round trunk with tiers of dark leaves, wide at the bottom and
    narrowing up (6x5 leaves, then 4x3, then 3-leaf plates), a grass sprig on top."""
    F = ground(b, x, z, y, rng.uniform(0, 360))
    F = on(b, F, "3062b", RBROWN)
    for i in range(n):
        part = "2417" if i < n // 2 else "2423" if i < n - 1 else "32607"
        F = on(b, F, "3062b", RBROWN, rng.uniform(0, 360))
        L = on(b, F, part, colour, i * 67 + rng.uniform(-20, 20))
        F = L if L is not None else F
    on(b, F, OPEN, RBROWN)

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
            S = on(b, S, OPEN, WHITE)
            G = on(b, S, "19119", ORANGE if leaf[0] in (YELLOW, ORANGE, BLO) else GREEN)
            for s in slots(G, "19119"):
                if rng.random() < 0.6:
                    put(b, "24866", rng.choice(leaf), M(s, Ry(rng.uniform(0, 360))))
        else:
            F = on(b, F, "3062b", WHITE, rng.uniform(0, 360))
        if rng.random() < 0.45:
            F = on(b, F, OPEN, BLACK)
    for crown in range(2):
        G = on(b, F, "19119", (ORANGE if crown == 0 else YELLOW) if leaf[0] in (YELLOW, ORANGE, BLO) else GREEN, crown * 30)
        for s in slots(G, "19119"):
            put(b, "24866", rng.choice(leaf), M(s, Ry(rng.uniform(0, 360))))
        if crown == 0:
            F = on(b, F, OPEN, WHITE)
            F = on(b, F, "3062b", WHITE)
    on(b, F, "32607", rng.choice(leaf), 0)


def palm(b, rng, x, z, y=0, height=6, leaf=GREEN, trunk=RBROWN):
    """Palm: reddish-brown round trunk with ring plates, a palm top (2566) and 4 small palm
    leaves (6148) slid onto its bars."""
    F = ground(b, x, z, y, rng.uniform(0, 360))
    for i in range(height):
        F = on(b, F, "3062b", trunk)
        F = on(b, F, OPEN, DBROWN if i % 2 else trunk)
    G = on(b, F, "2566", trunk)
    if G is None:
        return
    # one small palm leaf slid down each of the palm top's 4 bars, pointing outwards
    for bx, bz in ((10, 10), (-10, 10), (10, -10), (-10, -10)):
        ang = math.degrees(math.atan2(-bz, bx)) + rng.uniform(-10, 10)
        seat(b, "6148", leaf, M(G, T(bx, 0, bz), Ry(ang), T(10, 0, 0)), turns=(0,))


def cactus(b, rng, x, z, y=0, height=4, colour=OLIVE, arms=((1, 0), (2, 2))):
    """Mojave saguaro: a column of round bricks; each arm = a SNOT brick in the column, a sideways
    round brick, a 1x1 brick with a side stud turned so the stud points up, then round bricks up."""
    F = on(b, ground(b, x, z, y, rng.uniform(0, 360)), OPEN, colour)
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
                on(b, up, OPEN, colour)
        else:
            F = on(b, F, "3062b", colour)
    on(b, F, OPEN, colour)
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


def stud_frames(piece):
    """Frames (stud base, local -y = stud direction) of a placed piece's up-facing studs."""
    from brickscape.core.space import snaps
    out = []
    for s in snaps(piece):
        if s.kind == "cyl" and s.gender == "M" and s.secs and abs(s.secs[-1][1] - 6) < 0.5 \
                and s.secs[-1][2] <= 4.5 and s.R[1, 1] > 0.99:
            d, (u0, u1) = (-s.R[:, 1], (0.0, s.length))
            base = s.pos + d * (u1 - 4)                 # the stud section's base
            out.append((base[0], base[1], base[2], 1, 0, 0, 0, 1, 0, 0, 0, 1))
    return out


RISERS = ((), ("85861",), ("85861", "85861"), ("3062b",), ("3062b", "85861"), ("3062b", "3062b"))
OAK_SIZES = {   # trunk: 1 = 1x1 round bricks, 2 = 2x2 round bricks; h = trunk bricks; tiers of crown
    "small":  dict(w=1, h=3, tiers=2),
    "medium": dict(w=2, h=4, tiers=2),
    "tall":   dict(w=2, h=7, tiers=3),
    "fat":    dict(w=2, h=4, tiers=3, roots=True),
    "big":    dict(w=2, h=6, tiers=4, roots=True),
}


def oak(b, rng, x, z, y=0, size="medium", leaves=(GREEN, GREEN, DGREEN), bark=RBROWN, yaw=None):
    """Broadleaf tree in which every part sits on a real stud.

    Trunk of round bricks (1x1 or 2x2); per crown tier a hub plate (2x2 round for thin trunks,
    4x4 for thick) with 6x5 leaves on its outer studs pointing outwards, then 4x3 leaves and
    3-leaf plates on the leaves' own studs. Tiers are a trunk brick apart and shrink upwards;
    any leaf that would clash with another is turned or left out (see put/FIT).
    (x, z) = trunk cell (min corner of the 2x2 trunk for w=2)."""
    P = OAK_SIZES[size]
    yaw = rng.uniform(0, 360) if yaw is None else yaw
    w = P["w"]
    F = ground(b, x, z, y) if w == 1 else M(T(b.X(x) + 20, -8 * y, b.Z(z) + 20))
    trunk = "3062b" if w == 1 else "3941"
    if P.get("roots"):                              # root flare: cheese slopes round the trunk base
        for dx in range(-1, 3):
            for dz in range(-1, 3):
                if (dx in (0, 1) and dz in (0, 1)) or (dx in (-1, 2) and dz in (-1, 2)) or rng.random() < 0.3:
                    continue
                d = "N" if dz < 0 else "S" if dz > 1 else "W" if dx < 0 else "E"
                b.put("54200", bark, x + dx, y, z + dz, spin=d)
    for lv in range(P["h"]):
        F = on(b, F, trunk, bark if rng.random() < 0.8 else DBROWN, 0 if w == 2 else rng.uniform(0, 360))
    for t in range(P["tiers"]):
        hub_part = "4032a" if (w == 1 or t == P["tiers"] - 1) else "3031"
        hub = put(b, hub_part, rng.choice(leaves), M(F, T(0, -8, 0)))
        if hub is None:
            break
        cx, cz = F[0], F[2]
        nxt = None
        if t < P["tiers"] - 1:                       # trunk continues above the hub (placed first,
            if hub_part == "3031":                   # so the leaves fit round it)
                nxt = on(b, M(F, T(0, -8, 0)), "3941", bark)
                for _ in range(rng.choice((0, 1))):
                    nxt = on(b, nxt, "3941", bark)
            else:
                hs = stud_frames(hub)
                nxt = on(b, rng.choice(hs), "3062b", bark) if hs else None
        frames = stud_frames(hub)
        frames.sort(key=lambda G: -((G[0] - cx) ** 2 + (G[2] - cz) ** 2))
        placed = []
        for G in frames[:8]:
            ang = math.degrees(math.atan2(G[0] - cx, -(G[2] - cz))) if abs(G[0] - cx) + abs(G[2] - cz) > 1 \
                else rng.uniform(0, 360)
            part = "2417" if t < P["tiers"] - 1 else "2423"
            for riser in rng.sample(RISERS, len(RISERS)):     # stagger leaf heights
                n0 = len(b.pieces)
                R = G
                for r in riser:
                    R = on(b, R, r, bark if r == "3062b" else rng.choice(leaves))
                if R is not None and on(b, R, part, rng.choice(leaves), -ang + 180 + rng.uniform(-25, 25)):
                    placed.append(b.pieces[-1])
                    break
                while len(b.pieces) > n0:
                    b.pop()
        for leaf in placed:                          # second layer on the leaves' studs
            fr = stud_frames(leaf)
            for G in rng.sample(fr, min(3, len(fr))):
                on(b, G, rng.choice(("2423", "32607", "32607")), rng.choice(leaves), rng.uniform(0, 360))
        if nxt is None:
            break
        F = nxt


oak2 = oak


# ================================================================= botanical parts (2026-11-25)
# From the Canada First Bricks botanical list + unusual GoBricks parts. All grow from one stud.
def _base(b, rng, x, z, y, part=OPEN, colour=DGREEN):
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
    on(b, F, OPEN, centre)


def plume_grass(b, rng, x, z, y=0, colour=OLIVE, n=1):
    """Tall grass / reeds: triple plume (64647) or feather plume (30126) on a round plate."""
    F = _base(b, rng, x, z, y, OPEN, DGREEN)
    on(b, F, "64647" if rng.random() < .6 else "30126", colour, rng.uniform(0, 360))


def swirl_topiary(b, rng, x, z, y=0, colour=DGREEN, trunk=RBROWN, h=2):
    """Clipped topiary / pine sapling: a round-brick trunk and swirl-top round plates (15470)."""
    F = _base(b, rng, x, z, y, OPEN, trunk)
    for _ in range(h):
        F = on(b, F, "3062b", trunk)
    on(b, F, "15470", colour)


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
    F = _base(b, rng, x, z, y, OPEN, DGREEN)
    put(b, "88704", colour, M(F, Ry(rng.uniform(0, 360))))


def crystal_succulent(b, rng, x, z, y=0, colour=SGREEN, n=3):
    """Succulent cluster: 1x1 5-point crystals (30385) on round plates, in a little clump."""
    for i in range(n):
        F = on(b, ground(b, x + (i % 2), z + (i // 2), y, rng.uniform(0, 360)), OPEN, colour)
        put(b, "30385", colour, F)


def specimen(b, rng, x, z, part, colour, y=0, base=OPEN, base_colour=DGREEN):
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
