"""Ground v2: brick terraces with grass treads, and paths set INTO the ground.

Terraces (for shallow hills; shallow ground is bricks, slopes only for steep rock):
  each course = 1 brick riser ring + a plate floor over the whole course footprint.
  Exposed floor = grass tread (ragged lip overhanging the riser in places); the next
  ring sits on the floor. Inside is hollow apart from 2x2 columns on a grid.
  Pitch is 4 plates per course.

Paths (Market-style): dark tan bed plate on the baseplate, cobble tiles on top, and the
grass verge either side raised 1-2 plates, so the path is flush with or below the ground.
"""
import random, math, collections
from brickscape.core.kit import (PLATES, BRICKS, pack, put_rect, pick, nbr, DIRS, value_noise, HIDDEN, tuft,
                 GREEN, DGREEN, BGREEN, DTAN, TAN, RBROWN, LBG, DBG)
from brickscape.terrain.rock2 import ring
from brickscape.core.kit import OPP

BIG_PLATES = dict(PLATES)
BIG_PLATES.update({(6, 12): "3028", (8, 16): "92438", (16, 16): "91405", (6, 16): "3027"})


class Terraces:
    """Brick terraces with texture.

    Risers are 1 brick + the floor plate (4 plates). Visible riser cells are varied:
    undercuts (inverted slope under the grass lip), round bricks, stones sticking out at
    the foot, lighter stone patches. Treads get a ragged overhanging lip, raised grass
    patches and plants at the foot of the next riser. `reserved` cells (e.g. rock
    outcrops built later) are left plain."""

    def __init__(self, b, H, base_y=0, seed=0, riser_fn=None, grass=((GREEN, 1),), lip=0.3,
                 forbid=(), solid_fn=None, hidden=None, edge_cheese=0.08, col_step=5, tread_fn=None,
                 no_cheese=(), reserved=(), board=None, recess=0.14, rounds=0.10, protrude=0.12,
                 patches=0.30, foot_plants=0.22, accent=LBG, accent_amt=0.18):
        self.b, self.H, self.y0 = b, dict(H), base_y
        self.rng = random.Random(seed)
        self.seed = seed
        self.n = max(H.values()) if H else 0
        self.L = [{c for c, h in H.items() if h > k} for k in range(self.n)] + [set()]
        self.riser_fn = riser_fn or (lambda c, k: DTAN)
        self.grass, self.lip, self.forbid = grass, lip, set(forbid)
        self.solid = solid_fn or (lambda c, y: False)
        self.hidden = HIDDEN if hidden is None else hidden
        self.edge_cheese, self.col_step = edge_cheese, col_step
        self.tread_fn = tread_fn or (lambda c: None)      # colour override for a tread cell
        self.no_cheese = set(no_cheese)
        self.reserved = set(reserved)
        self.board = board
        self.p_recess, self.p_round, self.p_protrude = recess, rounds, protrude
        self.p_patch, self.p_foot = patches, foot_plants
        self.accent, self.accent_amt = accent, accent_amt
        self.surface = {}
        self.blocked = set(self.reserved)

    def Y(self, k):
        return self.y0 + 4 * k

    def top(self, c):
        return self.Y(self.H[c]) if c in self.H else None

    def _colour(self, c, k, an):
        colr = self.riser_fn(c, k)
        if colr == DBG and self.accent is not None and an(c[0] + 5 * k, c[1]) < self.accent_amt:
            return self.accent
        return colr

    def _open(self, c, d, k, y):
        o = nbr(c, d)
        return o not in self.L[k] and not self.solid(o, y + 2)

    def build(self):
        rng, b = self.rng, self.b
        an = value_noise(self.seed * 3 + 11, 3.0)
        lips = {}
        for k in range(self.n):
            Lk, Lu = self.L[k], self.L[k + 1]
            y = self.Y(k)
            r1 = ring(Lk, 1)
            tread = Lk - Lu
            inner = Lk - r1
            # ---- lip (decided first so nothing else claims those cells)
            lip = set()
            for c in tread & r1:
                for d in DIRS:
                    o = nbr(c, d)
                    if o not in Lk and o not in self.forbid and o not in self.blocked and \
                            not self.solid(o, y + 3) and rng.random() < self.lip / 2 and \
                            all(o not in self.L[j] for j in range(k)):
                        lip.add(o)
            lip -= {q for q in lip if sum(1 for d in DIRS if nbr(q, d) in tread) == 0}
            lips[k] = lip
            # ---- columns
            support = set(r1)
            cols = set()
            for (x, z) in sorted(inner):
                fp = {(x, z), (x + 1, z), (x, z + 1), (x + 1, z + 1)}
                if x % self.col_step == 2 and z % self.col_step == 2 and fp <= inner:
                    b.put("3003", self.hidden, x, y, z, note=" column hidden")
                    support |= fp
                    cols |= fp
            # ---- riser treatments
            vis = {c for c in r1 if any(self._open(c, d, k, y) for d in DIRS)}
            recess, rounds, protrude = {}, set(), []
            for c in sorted(vis):
                if c in self.reserved:
                    continue
                outs = [d for d in DIRS if self._open(c, d, k, y)]
                if len(outs) != 1:
                    continue
                d = outs[0]
                back = nbr(c, OPP[d])
                r = rng.random()
                if r < self.p_recess and back in inner and back not in cols and \
                        back not in recess.values() and nbr(c, d) not in lip:
                    recess[c] = back
                elif r < self.p_recess + self.p_round:
                    rounds.add(c)
                elif r < self.p_recess + self.p_round + self.p_protrude:
                    o = nbr(c, d)
                    ok = o not in lip and o not in self.blocked and o not in self.forbid and \
                        not self.solid(o, y) and (self.board is None or o in self.board)
                    if k > 0:
                        ok = ok and o in self.L[k - 1]
                    if ok:
                        protrude.append((o, d, c))
            used = set(recess) | set(recess.values()) | rounds
            support -= set(recess)            # an undercut's front cell has no stud on top
            groups = collections.defaultdict(set)
            for c in r1 - used:
                groups[self._colour(c, k, an) if c in vis else self.hidden].add(c)
            for colr, g in groups.items():
                for (x, z, w, d) in pack(g, BRICKS, rotate=k % 2 == 1):
                    put_rect(b, BRICKS, colr, x, z, w, d, y)
            for c, back in recess.items():
                d = [d for d in DIRS if nbr(c, d) not in Lk][0]
                b.put("3665", self._colour(c, k, an), min(c[0], back[0]), y, min(c[1], back[1]), spin=d,
                      note=" undercut")
                support.add(back)
            for c in rounds:
                b.put("3062b", self._colour(c, k, an), c[0], y, c[1])
            for (o, d, c) in protrude:
                colr = self._colour(c, k, an)
                kind = rng.choice(["tall", "mid", "low", "round"])
                if kind == "tall":
                    b.put("3005", colr, o[0], y, o[1]); b.put("54200", colr, o[0], y + 3, o[1], spin=d)
                elif kind == "mid":
                    b.put("3024", colr, o[0], y, o[1]); b.put("3024", colr, o[0], y + 1, o[1])
                    b.put("54200", colr, o[0], y + 2, o[1], spin=d)
                elif kind == "low":
                    b.put("3024", colr, o[0], y, o[1]); b.put("54200", colr, o[0], y + 1, o[1], spin=d)
                else:
                    b.put("3062b", colr, o[0], y, o[1])
                self.blocked.add(o)
            b.step()
            # ---- floor: whole course footprint plus the lip; green where exposed
            floor = Lk | lip
            special = {c for c in tread if self.tread_fn(c) is not None}
            packs = []
            for colr in sorted({self.tread_fn(c) for c in special}):
                packs += [(r, colr) for r in pack({c for c in special if self.tread_fn(c) == colr},
                                                 PLATES, maxsize=12)]
            packs += [(r, None) for r in pack(floor - special, BIG_PLATES, rotate=k % 2 == 0)]
            covered = set()
            for (x, z, w, d), forced in packs:
                fp = {(x + i, z + j) for i in range(w) for j in range(d)}
                if not fp & support:
                    inside = sorted(fp & (inner - cols), key=lambda c: abs(c[0] - x - w / 2) + abs(c[1] - z - d / 2))
                    if not inside:
                        continue
                    c = inside[0]
                    b.put("3005", self.hidden, c[0], y, c[1], note=" prop hidden")
                    support.add(c)
                seen = fp & (tread | lip)
                colr = forced if forced is not None else (pick(rng, self.grass) if seen else self.hidden)
                put_rect(b, BIG_PLATES, colr, x, z, w, d, y + 3)
                covered |= fp
            for c in (tread | lip) & covered:
                self.surface[c] = y + 4
            b.step()
        self._dress(lips)
        return self.surface

    def _dress(self, lips):
        """Raised grass patches, foot plants and edge cheese on the treads."""
        rng, b = self.rng, self.b
        for c in self.blocked:
            if c in self.surface:
                self.surface[c] = None
        pn = value_noise(self.seed * 3 + 12, 3.5)
        all_lips = set().union(*lips.values()) if lips else set()
        for k in range(self.n):
            Lk, Lu = self.L[k], self.L[k + 1]
            h = self.Y(k) + 4
            tread = {c for c in Lk - Lu if c not in self.blocked and self.tread_fn(c) is None}
            front = {c for c in tread if any(nbr(c, d) not in Lk for d in DIRS)}
            patch = {c for c in tread - front if pn(c[0] + 9 * k, c[1]) > 1 - self.p_patch}
            patch = {c for c in patch if sum(1 for d in DIRS if nbr(c, d) in patch) >= 1}
            edge = {c for c in patch if any(nbr(c, d) not in patch for d in DIRS)}
            rnd = {c for c in edge if rng.random() < 0.3}
            for (x, z, w, d) in pack(patch - rnd, PLATES, maxsize=6):
                put_rect(b, PLATES, pick(rng, self.grass), x, z, w, d, h)
            for c in rnd:
                b.put("6141", pick(rng, self.grass), c[0], h, c[1])
            for c in patch:
                self.surface[c] = h + 1
            # plants gather at the foot of the next riser and in the patches
            for c in sorted(tread):
                at_foot = any(nbr(c, d) in Lu for d in DIRS)
                p = self.p_foot if at_foot else (0.06 if c in patch else 0.0)
                if self.surface.get(c) and rng.random() < p:
                    tuft(b, rng, c[0], c[1], self.surface[c],
                         pick(rng, [("leaf", 4), ("fern", 2), ("big", 2), ("grass", 1.5), ("tabs", 1)]))
                    self.surface[c] = None
            # the odd green cheese slope on the front edge
            for c in sorted(front):
                if c in self.no_cheese or not self.surface.get(c):
                    continue
                outs = [d for d in DIRS if nbr(c, d) not in Lk and not self.solid(nbr(c, d), h)]
                if outs and rng.random() < self.edge_cheese:
                    b.put("54200", GREEN, c[0], h, c[1], spin=rng.choice(outs))
                    self.surface[c] = None
        b.step()


# ---------------------------------------------------------------------- paths
COBBLE_1 = [("98138", 4), ("24246", 2), ("25269", 1.5), ("3070b", 0.6)]   # 1x1 tiles
COBBLE_COL = ((LBG, 5), (DBG, 3), (TAN, 0.5))


def sunken_path(b, rng, cells, style="cobble", y=0, verge=(2.0, 4.5), board=None, avoid=(),
                seed=0, raise2=0.55, grass=((GREEN, 1),)):
    """Path laid into the ground. Returns (occupied cells, surface {cell: height})."""
    cells = set(cells)
    avoid = set(avoid)
    surf = {}
    # bed
    for (x, z, w, d) in pack(cells, PLATES, maxsize=16):
        put_rect(b, PLATES, DTAN, x, z, w, d, y)
    for c in cells:
        surf[c] = y + 1
    # surface: cobbles (tight, gaps show the dark tan bed as gravel) or dirt with a few stones
    free = set(cells)
    order = sorted(cells)
    rng.shuffle(order)
    if style == "cobble":
        for (x, z) in order:
            fp = {(x, z), (x + 1, z), (x, z + 1), (x + 1, z + 1)}
            if fp <= free and rng.random() < 0.3:
                b.put(rng.choice(["14769", "14769", "3068b"]) if False else "14769", pick(rng, COBBLE_COL), x, y + 1, z)
                free -= fp
                for q in fp:
                    surf[q] = y + 2
        for (x, z) in sorted(free):
            fp2 = {(x, z), (x + 1, z)}
            r = rng.random()
            if r < 0.12 and fp2 <= free:
                b.put("1748", pick(rng, COBBLE_COL), x, y + 1, z, spin=rng.choice("NS"))
                free -= fp2
                for q in fp2:
                    surf[q] = y + 2
            elif r < 0.78 and (x, z) in free:
                b.put(pick(rng, COBBLE_1), pick(rng, COBBLE_COL), x, y + 1, z, spin=rng.choice("NESW"))
                free.discard((x, z))
                surf[(x, z)] = y + 2
    elif style == "rough":
        rough_stones(b, rng, cells, lambda c: y + 1, seed=seed, surf=surf)
    else:  # dirt
        for (x, z) in order:
            r = rng.random()
            if r < 0.06:
                b.put(rng.choice(["98138", "6141"]), pick(rng, ((LBG, 3), (DBG, 2))), x, y + 1, z)
            elif r < 0.12:
                b.put(rng.choice(["3070b", "98138"]), TAN, x, y + 1, z)
    b.step()
    # verge: green plates either side; a second plate close to the path
    n1 = value_noise(seed * 7 + 1, 5.0)
    n2 = value_noise(seed * 7 + 2, 3.0)
    dist = {c: 0 for c in cells}
    frontier = set(cells)
    for i in range(1, int(verge[1]) + 2):
        frontier = {nbr(c, d) for c in frontier for d in DIRS} - set(dist)
        for c in frontier:
            dist[c] = i
    lay1, lay2 = set(), set()
    for c, dd in dist.items():
        if dd == 0 or c in avoid or (board is not None and c not in board):
            continue
        w = verge[0] + (verge[1] - verge[0]) * n1(*c)
        if dd <= w:
            lay1.add(c)
            if dd <= 1 + 1.5 * n2(*c) and rng.random() < 0.95 and n2(*c) > 1 - raise2:
                lay2.add(c)
    lay1 = {c for c in lay1 if sum(1 for d in DIRS if nbr(c, d) in lay1 | cells) >= 2}
    lay2 &= lay1
    lay2 = {c for c in lay2 if sum(1 for d in DIRS if nbr(c, d) in lay2 | cells) >= 2}
    # ragged outer edge: some edge cells become round 1x1 plates
    edge1 = {c for c in lay1 if any(nbr(c, d) not in lay1 | cells for d in DIRS)}
    rounds = {c for c in edge1 if rng.random() < 0.35 and c not in lay2}
    for (x, z, w, d) in pack(lay1 - rounds, PLATES, maxsize=12):
        put_rect(b, PLATES, pick(rng, grass), x, z, w, d, y)
    for c in rounds:
        b.put("6141", pick(rng, grass), c[0], y, c[1])
    for c in lay1:
        surf[c] = y + 1
    for (x, z, w, d) in pack(lay2, PLATES, maxsize=8, rotate=True):
        put_rect(b, PLATES, pick(rng, grass), x, z, w, d, y + 1)
    for c in lay2:
        surf[c] = y + 2
    b.step()
    return cells | lay1, surf


ROUGH_COL = ((LBG, 5), (DBG, 3), (TAN, 1.2), (DTAN, 0.8))


def rough_stones(b, rng, cells, height, seed=0, cover=0.42, surf=None):
    """Rough cobble on a dirt bed: stones of mixed sizes, dense in patches, sparse in
    others, so the dark tan shows through. height(c) = top of the bed at cell c."""
    dens = value_noise(seed * 5 + 3, 4.0)
    free = set(cells)
    order = sorted(cells)
    rng.shuffle(order)
    for (x, z) in order:              # a few big flat stones first
        fp = {(x, z), (x + 1, z), (x, z + 1), (x + 1, z + 1)}
        if fp <= free and len({height(c) for c in fp}) == 1 and rng.random() < 0.10 * dens(x, z) * 2:
            b.put(rng.choice(["14769", "14769", "4032a"]), pick(rng, ROUGH_COL), x, height((x, z)), z)
            free -= fp
            if surf is not None:
                for c in fp:
                    surf[c] = height(c) + 1
    for (x, z) in order:
        if (x, z) not in free:
            continue
        p = cover * (0.25 + 1.5 * dens(x, z))
        if rng.random() < p:
            part = pick(rng, [("98138", 4), ("6141", 2.5), ("24246", 1.5), ("25269", 1), ("3024", 0.6)])
            b.put(part, pick(rng, ROUGH_COL), x, height((x, z)), z, spin=rng.choice("NESW"))
            free.discard((x, z))
            if surf is not None:
                surf[(x, z)] = height((x, z)) + 1
