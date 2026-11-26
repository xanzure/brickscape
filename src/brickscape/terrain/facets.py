"""Facet rock: faces built as chains of slopes that lean back 1 stud per slope (learned from
recreating wjwa's cliff: almost every visible surface there is a sloped facet; bricks are hidden).

T = {cell: height in plates at that cell's FRONT edge}. Every cell c picks a downhill neighbour f
(steepest drop of the smooth envelope). One slope bridges them: its sloped front part sits over
f (from T(f) up) and its back part fills c up to T(c). Its top stud (on c) is covered by the next
slope up (c, its back neighbour), so on a face the slopes chain into one leaning plane:
75 deg slopes (drop 9 plates) give a steep plane, 65 (6) and 45 (3) gentler ones.
Below each slope the cell is plain hidden bricks. A cell can be the front of only one slope;
conflicts fall back to a stack of slopes or bricks.
"""
import random, collections
from brickscape.core.kit import BRICKS, PLATES, pack, put_rect, pick, nbr, put_slope, DBG
from brickscape.terrain.pillars import TILES

OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
SLOPES = {9: "4460b", 6: "60481a", 3: "3040b"}


def facet_rock(b, T, low=lambda c: 0, board=None, colour=DBG, seed=0, hidden=None, tile_tops=True, no_front=(), max_drop=9, floor=None,
               form=None, light=None, ridge=1.5, pinnacles=0.0, leaves=0.0, leaf_colour=288, lintel=None, inside=None, blocked=None, top_plants=None):
    """no_front: cells a slope may not lean out over (e.g. a path or a cave mouth).
    colour: a colour, or a function cell -> colour (e.g. dark in recesses, light on faces).
    floor: {cell: plates} where a cell's rock starts above a void (cave roof); default 0.
    form: the smooth envelope {cell: plates}; light: ridge colour. Cells on convex ground (higher
      than the mean around them by > ridge plates) get `light`, the rest `colour`: light ridges,
      dark gullies, so the colour expresses the form.
    pinnacles: chance per top-rim cell of a tall slope standing up on the rim (65/75 deg, resting
      fully on the rim cell and the cell behind it, sloped face out): a jagged top edge.
    leaves: chance per uncovered top in a gully (concave) of a leaf plate instead of a tile.
    lintel: set of cells (cave roof + 1 ring) where 3 plate layers span the void at
      min(floor) (the floor must be a whole brick); inside(cell) -> colour of the cave interior."""
    floor = floor or {}
    blocked = blocked or (lambda c, n: False)     # blocked(c, n): c may not lean out over n
    base_col = colour if callable(colour) else (lambda c, _k=colour: _k)
    F = form or T
    def curv(c):
        ns = [F[(c[0] + dx, c[1] + dz)] for dx in (-2, -1, 0, 1, 2) for dz in (-2, -1, 0, 1, 2)
              if (dx or dz) and (c[0] + dx, c[1] + dz) in F]
        return (F.get(c, 0) - sum(ns) / len(ns)) if ns else 0
    def curv1(c):     # radius 1 on the ACTUAL (textured) heights: narrow ridges = streaks
        ns = [T[n] if n in T else low(n) for n in (nbr(c, q) for q in "NESW")
              if board is None or n in board]
        return (T[c] - sum(ns) / len(ns)) if ns else 0
    K = {c: 0.6 * curv(c) + curv1(c) for c in T}
    def col(c):
        if inside and floor.get(c, 0) and c in (lintel or ()):
            return base_col(c)
        if light is not None and K.get(c, 0) > ridge:
            return light
        return base_col(c)
    no_front = set(no_front)
    rng = random.Random(seed)
    hidden = (colour if not callable(colour) else None) if hidden is None else hidden
    T = {c: v - v % 3 for c, v in T.items() if v >= 3}       # whole bricks: slopes fit exactly
    H = lambda c: T[c] if c in T else low(c)
    # no drop bigger than one slope (9 plates) toward any neighbour a slope could lean over:
    # otherwise slopes would have to stack on each other's sloped faces = hanging bottoms
    # (style rule: overhangs only as inverted slopes). Path / board edge sides stay as walls.
    changed = True
    while changed:
        changed = False
        for c in sorted(T):
            lim = T[c]
            for d in "NESW":
                n = nbr(c, d)
                if (board is not None and n not in board) or n in no_front or blocked(c, n):
                    continue
                base = max(H(n), floor[c]) if c in floor else H(n)   # a roof cell's drop starts at its floor
                lim = min(lim, base + max_drop)
            if c in floor:
                lim = max(lim, floor[c] + 3)     # a cave roof never drops below its lintel
            if lim < T[c]:
                T[c] = lim - lim % 3
                changed = True
        T = {c: v for c, v in T.items() if v >= 3}

    # 1. each cell's downhill direction and the slope that bridges it to its front cell
    slope_of = {}            # back cell c -> (front cell f, direction d, drop)
    front_used = set()
    order = sorted(T, key=lambda c: (-T[c], rng.random()))
    for c in order:
        best = None
        for d in "NESW":
            f = nbr(c, d)
            if (board is not None and f not in board) or f in no_front or blocked(c, f):
                continue
            drop = T[c] - H(f)
            if c in floor:
                drop = min(drop, T[c] - floor[c] - 3)
            if drop >= 3 and (best is None or drop > best[2]):
                best = (f, d, drop)
        if best and best[0] not in front_used:
            slope_of[c] = best
            front_used.add(best[0])
    # 2. hidden bricks: each cell up to the bottom of what stands on it
    brick_top = {}
    for c in T:
        if c in slope_of:
            f, d, drop = slope_of[c]
            brick_top[c] = max(0, T[c] - drop)
        else:
            brick_top[c] = T[c]
    top = max(brick_top.values(), default=0)
    LF = min(floor[c] for c in lintel if c in floor) if lintel else None
    if lintel:
        from brickscape.terrain.ground import BIG_PLATES
        from brickscape.core.kit import PLATES
        L = {c for c in lintel if c in T and brick_top[c] >= LF + 3}
        for j in range(3):
            tab = BIG_PLATES if j == 0 else PLATES
            for (x, z, w, dd) in pack(L, tab, rotate=j % 2 == 1):
                cc = (x, z)
                put_rect(b, tab, inside(cc) if (inside and j == 0) else col(cc), x, z, w, dd, LF + j)
    y, k = 0, 0
    while y < top:
        course = {c for c, s in brick_top.items() if s >= y + 3 and floor.get(c, 0) <= y
                  and not (lintel and c in lintel and LF <= y < LF + 3)}
        groups = collections.defaultdict(set)
        for c in course:
            vis = any(nbr(c, q) not in T for q in "NESW") or floor.get(c, 0) > 0
            groups[col(c) if vis else (hidden if not callable(colour) else col(c))].add(c)
        for kc, g in groups.items():
            for (x, z, w, dd) in pack(g, BRICKS, rotate=k % 2 == 1):
                put_rect(b, BRICKS, kc, x, z, w, dd, y)
        y += 3; k += 1
    b.step()
    # 3. the slopes: fill from brick_top to T[c] with slopes facing d (the front part over f)
    n_slopes = 0
    for c, (f, d, drop) in sorted(slope_of.items()):
        y = brick_top[c]
        # the slope's front part sits over f: f must not stand higher than y
        while y < T[c]:
            left = T[c] - y
            hh = 9 if left >= 9 else (6 if left >= 6 else 3)
            put_slope(b, SLOPES[hh], col(c), f, d, y, 2)
            y += hh
            n_slopes += 1
    # 4. tile every cell top that nothing covers (no slope from behind sits on it)
    if tile_tops:
        covered = {f for c, (f, d, drop) in slope_of.items()}
        done = set()
        def downhill(c):      # cheese faces the lowest neighbour (ties: random)
            ds = [(H(nbr(c, q)) if (board is None or nbr(c, q) in board) else 10 ** 6, rng.random(), q) for q in "NESW"]
            return min(ds)[2]
        if pinnacles:
            for c in sorted(T, key=lambda c: rng.random()):
                if c in covered or c in done or rng.random() > pinnacles:
                    continue
                # rim: a neighbour (out) at least 6 lower; the cell behind (opposite) same height, free
                for d in "NESW":
                    o = nbr(c, d); bk = nbr(c, OPP[d])
                    if H(o) <= T[c] - 6 and T.get(bk) == T[c] and bk not in covered and bk not in done:
                        part = rng.choice(("60481a", "4460b", "4460b"))
                        put_slope(b, part, col(c), c, d, T[c], 2)
                        h = 6 if part == "60481a" else 9
                        b.put("54200", col(c), bk[0], T[c] + h, bk[1], spin=d)   # cheese, not a tile
                        done |= {c, bk}
                        break
        for c in T:
            if c in covered or c in done:
                continue
            if top_plants and c in top_plants:
                part, pc = top_plants[c]
                b.attach(part, pc, c[0] + .5, c[1] + .5, T[c], spin=rng.choice("NESW"))
            elif leaves and K.get(c, 0) < -ridge and rng.random() < leaves:
                b.attach("32607", leaf_colour, c[0] + .5, c[1] + .5, T[c], spin=rng.choice("NESW"))
            else:
                b.put("54200", col(c), c[0], T[c], c[1], spin=downhill(c))   # cheese, never a flat tile
    b.step()
    return slope_of
