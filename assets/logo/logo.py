"""The brickscape logo as a real build: "BrickScape" in tiled bricks on two green 32x32
baseplates, surrounded by rocks, water and plants.

    python assets/logo/logo.py            # writes assets/logo/logo.ldr
"""
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from brickscape.core.brick import Build
from brickscape.core.kit import pack, put_rect, BRICKS, PLATES, nbr, DIRS
from brickscape.terrain import greenery as G
from brickscape.terrain.water import TILES

W, D = 64, 32
HERE = os.path.dirname(os.path.abspath(__file__))

# pixel font: rows top -> bottom, 7 rows (+2 descender rows for p)
FONT = {
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "r": ["....", "....", "#.##", "##..", "#...", "#...", "#..."],
    "i": ["#", ".", "#", "#", "#", "#", "#"],
    "c": ["....", "....", ".###", "#...", "#...", "#...", ".###"],
    "k": ["#...", "#...", "#..#", "#.#.", "##..", "#.#.", "#..#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "a": ["....", "....", "###.", "...#", ".###", "#..#", ".###"],
    "p": ["....", "....", "###.", "#..#", "#..#", "#..#", "###.", "#...", "#..."],
    "e": ["....", "....", ".##.", "#..#", "####", "#...", ".###"],
}
WORD = "BrickScape"
# letter colours: (body bricks, top tiles)
BRICK_COL = (72, 71)       # dark bluish grey body, light bluish grey tiles
SCAPE_COL = (272, 321)     # dark blue body, dark azure tiles
LAYERS = 3
BASE_Z = 13                # board row of the letters' baseline (row 6 of the glyph)


def letter_cells():
    """{(x, z): word index} for every letter pixel, centred on the board."""
    width = sum(len(FONT[ch][0]) for ch in WORD) + len(WORD) - 1
    x0 = (W - width) // 2
    cells = {}
    for k, ch in enumerate(WORD):
        g = FONT[ch]
        for r, row in enumerate(g):
            for c, v in enumerate(row):
                if v == "#":
                    cells[(x0 + c, BASE_Z + 6 - r)] = k
        x0 += len(g[0]) + 1
    return cells


def letters(b, cells):
    for part, (lo, hi) in (("Brick", (0, 5)), ("Scape", (5, 10))):
        body, top = BRICK_COL if part == "Brick" else SCAPE_COL
        cs = {c for c, k in cells.items() if lo <= k < hi}
        for layer in range(LAYERS):               # brick courses, seams crossed
            for (x, z, w, d) in pack(cs, BRICKS, rotate=layer % 2 == 1):
                put_rect(b, BRICKS, body, x, z, w, d, 3 * layer)
        for (x, z, w, d) in pack(cs, TILES):
            put_rect(b, TILES, top, x, z, w, d, 3 * LAYERS)
    b.step()


def stream(rng):
    """Water cells: a stream from the back-right corner winding to the front edge."""
    pts = [(62, 31), (57, 27), (55, 22), (58, 17), (59, 12), (55, 7), (50, 3), (46, 0)]
    cells = set()
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        n = max(abs(bx - ax), abs(bz - az)) * 2
        for t in range(n + 1):
            x = ax + (bx - ax) * t / n
            z = az + (bz - az) * t / n
            r = 1.6 + 0.6 * rng.random()
            for dx in range(-3, 4):
                for dz in range(-3, 4):
                    if dx * dx + dz * dz <= r * r:
                        c = (round(x + dx), round(z + dz))
                        if 0 <= c[0] < W and 0 <= c[1] < D:
                            cells.add(c)
    return cells


def build(seed=4):
    rng = random.Random(seed)
    b = Build("brickscape logo", W, D)
    b.base(0, 0)
    b.base(32, 0)
    b.step()
    L = letter_cells()
    letters(b, L)
    used = set(L)
    pad = {nbr(c, d) for c in L for d in DIRS} | {(c[0] + dx, c[1] + dz) for c in L
                                                  for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
    # stream, clear of the letters
    water = {c for c in stream(rng) if c not in pad}
    for (x, z, w, d) in pack(water, TILES):
        put_rect(b, TILES, rng.choice((1, 1, 1, 322, 73)), x, z, w, d, 0)
    used |= water
    b.step()

    def free(cells):
        return all(0 <= c[0] < W and 0 <= c[1] < D and c not in used and c not in pad for c in cells)

    def take(cells):
        used.update(cells)

    # trees along the back, behind the letters
    for (x, z, size) in ((5, 27, "medium"), (14, 29, "small"), (24, 28, "small"), (45, 29, "small"),
                         (36, 29, "medium")):
        fp = {(x + dx, z + dz) for dx in range(-2, 3) for dz in range(-2, 3)}
        if free(fp):
            G.oak2(b, rng, x, z, size=size, leaves=(2, 2, 288))
            take(fp)
    b.step()
    # rocks: boulders by the water and in the corners
    for (x, z, s) in ((50, 8, 4), (60, 20, 2), (2, 2, 4), (8, 4, 2), (52, 26, 2), (40, 2, 2),
                      (28, 26, 4), (1, 15, 2), (62, 3, 2)):
        fp = {(x + i, z + j) for i in range(s) for j in range(s)}
        if free(fp):
            from brickscape.core.kit import boulder
            boulder(b, rng, x, z, size=s, pal=((72, 3), (71, 2)))
            take(fp)
    b.step()
    # bushes and ferns
    kinds = [("bush", 4), ("fern", 1), ("leaf", 2), ("sword", 1)]
    cells = [(x, z) for x in range(W) for z in range(D)]
    rng.shuffle(cells)
    for (x, z) in cells:
        fp = {(x + i, z + j) for i in range(2) for j in range(2)}
        front = z < BASE_Z + 1 and 6 < x < W - 12
        if not free(fp) or rng.random() > (0.025 if front else 0.3):
            continue
        if front:
            from brickscape.core.kit import boulder
            boulder(b, rng, x, z, size=2, pal=((72, 3), (71, 2)))
            take(fp)
            continue
        k = rng.choices([k for k, _ in kinds], [w for _, w in kinds])[0]
        if k == "bush":
            G.snot_bush(b, rng, x, z, leaf=(2, 10), levels=1)
        elif k == "fern":
            G.fern_clump(b, rng, x, z, colour=288)
        elif k == "leaf":
            G.big_leaf_plant(b, rng, x, z, colour=2)
        else:
            G.sword_plant(b, rng, x, z, colour=288)
        take(fp | {(x + i, z + j) for i in (-1, 0, 1, 2) for j in (-1, 0, 1, 2)})
    b.step()
    # flat patches of green plates and tiles: calm ground in front of the letters
    for _ in range(60):
        x, z = rng.randrange(0, W - 3), rng.randrange(0, BASE_Z)
        w, d = rng.choice(((2, 2), (2, 3), (3, 2), (2, 4), (1, 3)))
        fp = {(x + i, z + j) for i in range(w) for j in range(d)}
        if free(fp):
            tb = TILES if rng.random() < 0.5 and (min(w, d), max(w, d)) in TILES else PLATES
            put_rect(b, tb, rng.choice((10, 288, 2)), x, z, w, d, 0)
            take(fp)
    b.step()
    # ground cover on what's left: tufts and a few white/blue flowers
    for (x, z) in cells:
        if not free({(x, z)}) or rng.random() > 0.62:
            continue
        r = rng.random()
        if r < 0.25:
            b.put(rng.choice(("3024", "3024", "4073", "3070b")), rng.choice((2, 10, 288)), x, 0, z)
        elif r < 0.37:
            G.flower(b, rng, x, z, colour=rng.choice((15, 15, 1, 322)))
        else:
            G.tuft(b, rng, x, z, kind=rng.choice(("grass", "grass", "leafy", "clover", "spiky")),
                   colour=rng.choice((2, 288, 10)), base=rng.choice((288, 2)))
        take({(x, z)})
    b.step()
    return b


if __name__ == "__main__":
    b = build()
    out = os.path.join(HERE, "logo.ldr")
    b.write(out)
    print(out, len(b.pieces), "parts")
