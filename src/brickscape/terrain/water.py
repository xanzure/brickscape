"""Water on green baseplates: rivers, ponds, pools, ripples, banks, fords, bridges.

Water is laid on the baseplate (surface 1 plate up): smooth blue tiles, with
trans-clear / white 1x1 round plates set flush among them as ripples and foam.
The ground beside the water is raised 1-2 plates (earth bank at the water's edge),
so the water always sits lower than the land around it.
"""
import math, random, collections
from brickscape.core.kit import (PLATES, pack, pack_seams, put_rect, pick, nbr, DIRS, value_noise, tuft, clean, path_cells,
                 GREEN, DGREEN, BGREEN, OLIVE, DTAN, TAN, RBROWN, LBG, DBG, BLUE, TCLEAR, WHITE)

TILES = {(1, 1): "3070b", (1, 2): "3069b", (1, 4): "2431", (1, 6): "6636", (1, 8): "4162",
         (2, 2): "3068b", (2, 4): "87079"}
TLBLUE = 43           # trans light blue
MAZURE = 322          # medium azure (shallows)


def bfs_dist(src, cells, maxd=12):
    dist = {c: 0 for c in src}
    fr = set(src)
    for i in range(1, maxd + 1):
        fr = {nbr(c, d) for c in fr for d in DIRS if nbr(c, d) in cells} - set(dist)
        for c in fr:
            dist[c] = i
    return dist


def water_surface(b, rng, water, y=0, deep=BLUE, shallow=None, ripple=0.10, foam=(), foam_p=0.5,
                  seed=0, seams=((), ())):
    """Tiles over `water` at height y; ripples/foam as flush 1x1 round plates."""
    water = set(water)
    edge = {c for c in water if any(nbr(c, d) not in water for d in DIRS)}
    rn = value_noise(seed + 1, 2.5)
    rip = {c for c in water if rng.random() < ripple * (0.4 + 1.2 * rn(*c))}
    fo = {c for c in foam if c in water and rng.random() < foam_p}
    rip -= fo
    for c in sorted(rip):
        b.put("6141", rng.choice([TCLEAR, TCLEAR, TLBLUE]), c[0], y, c[1])
    for c in sorted(fo):
        b.put(rng.choice(["6141", "6141", "98138"]), rng.choice([WHITE, WHITE, TCLEAR]), c[0], y, c[1])
    rest = water - rip - fo
    if shallow:
        sh = rest & edge
        for (x, z, w, d) in pack(sh, TILES):
            put_rect(b, TILES, shallow, x, z, w, d, y)
        rest -= sh
    for (x, z, w, d) in pack_seams(rest, TILES, *seams):
        put_rect(b, TILES, deep, x, z, w, d, y)
    b.step()


def banks(b, rng, water, board, avoid=(), w2=(1.5, 3.0), w1=(3.5, 6.5), seed=0,
          earth=((DTAN, 5), (RBROWN, 2), (DBG, 1.5)), stones=0.18, plants=0.22, reeds=0.07,
          sand=0.0, keep_clear=(), force2=(), seams=((), ())):
    """Raise the ground 1-2 plates beside water; earth/stone at the water's edge.
    Returns (bank cells, surface heights)."""
    avoid = set(avoid) | set(water)
    cand = set(board) - avoid
    dist = bfs_dist(water, cand | set(water), maxd=int(w1[1]) + 2)
    n1, n2, ne = value_noise(seed + 2, 6.0), value_noise(seed + 3, 5.0), value_noise(seed + 4, 7.0)
    L1, L2 = set(), set()
    for c, d in dist.items():
        if d == 0 or c not in cand:
            continue
        if d <= w2[0] + (w2[1] - w2[0]) * n1(*c):
            L2.add(c)
        if d <= w1[0] + (w1[1] - w1[0]) * n2(*c):
            L1.add(c)
    L2 |= set(force2) & cand
    L1 |= L2
    L1 = set(clean({c: 1 for c in L1}, 2)) | {c for c in L1 if dist.get(c) == 1}
    L2 &= L1
    L2 = set(clean({c: 1 for c in L2}, 2)) | {c for c in L2 if dist.get(c) == 1} | (set(force2) & L1)
    face = {c for c in L1 if dist.get(c) == 1}

    def ecol(c):
        v = ne(*c)
        return earth[0][0] if v < 0.55 else (earth[1][0] if v < 0.8 else earth[2][0])
    for lvl, cells in ((0, L1), (1, L2)):
        groups = collections.defaultdict(set)
        for c in cells:
            groups[ecol(c) if c in face else GREEN].add(c)
        for colr, g in groups.items():
            packer = pack_seams(g, PLATES, *seams, maxsize=24, rotate=lvl == 1) if colr == GREEN else \
                pack(g, PLATES, maxsize=6, rotate=lvl == 1)
            for (x, z, w, d) in packer:
                put_rect(b, PLATES, colr, x, z, w, d, lvl)
    # ragged outer edge of the raised ground
    outer = {c for c in L1 if any(nbr(c, d) not in L1 and nbr(c, d) not in water for d in DIRS)}
    surf = {c: (2 if c in L2 else 1) for c in L1}
    b.step()
    # dressing: stones and plants on the bank face, reeds/pebbles/sand in the water edge
    wedge = {c for c in water if any(nbr(c, d) in face for d in DIRS)}
    from brickscape.terrain.ground import ROUGH_COL
    keep_clear = set(keep_clear)
    for c in sorted(face - keep_clear):
        r = rng.random()
        if r < stones:
            b.put(rng.choice(["6141", "98138", "54200"]), pick(rng, ROUGH_COL[:2]), c[0], surf[c], c[1],
                  spin=rng.choice("NESW"))
            surf[c] = None
        elif r < stones + plants:
            tuft(b, rng, c[0], c[1], surf[c], pick(rng, [("leaf", 3), ("grass", 3), ("big", 1.5), ("fern", 1)]))
            surf[c] = None
    used_w = set()
    for c in sorted(wedge - keep_clear):
        r = rng.random()
        if r < reeds:
            b.attach("15279", pick(rng, ((OLIVE, 2), (GREEN, 1), (DGREEN, 1))), c[0] + .5, c[1] + .5, 0,
                     rng.choice("NESW"))
            used_w.add(c)
        elif r < reeds + 0.06:
            b.put("6141", pick(rng, ((LBG, 2), (DBG, 1), (TAN, 1))), c[0], 0, c[1])
            used_w.add(c)
        elif r < reeds + 0.06 + sand:
            b.put("3024", TAN, c[0], 0, c[1])
            used_w.add(c)
    for c in sorted(L1 - face - keep_clear):
        if surf.get(c) and rng.random() < 0.025:
            tuft(b, rng, c[0], c[1], surf[c])
            surf[c] = None
    b.step()
    return L1, surf, used_w


def river_cells(pts, wmin, wmax, seed=0, board=None):
    return path_cells(pts, wmin, wmax, seed=seed, board=board)


def bridge(b, rng, x0, z0, length, width=3, along="x", y=2, posts=(), colour=RBROWN):
    """Plank bridge: deck of plates at height y (bank top), tiles on top; posts are
    cells under the deck where 2-plate stacks stand on the baseplate."""
    for c in posts:
        b.put("3024", DBG, c[0], 0, c[1])
        b.put("3024", colour, c[0], 1, c[1])
    if along == "x":
        for j in range(width):
            for (x, z, w, d) in pack({(x0 + i, z0 + j) for i in range(length)}, PLATES):
                put_rect(b, PLATES, colour, x, z, w, d, y)
        for i in range(length):
            tiles = {1: "3070b", 2: "3069b", 3: "63864", 4: "2431"}
            b.put(tiles[width], rng.choice([colour, colour, 308, DTAN]), x0 + i, y + 1, z0, spin="E")
    else:
        for i in range(width):
            for (x, z, w, d) in pack({(x0 + i, z0 + j) for j in range(length)}, PLATES):
                put_rect(b, PLATES, colour, x, z, w, d, y)
        tiles = {1: "3070b", 2: "3069b", 3: "63864", 4: "2431"}
        for j in range(length):
            b.put(tiles[width], rng.choice([colour, colour, 308, DTAN]), x0, y + 1, z0 + j)
    b.step()
