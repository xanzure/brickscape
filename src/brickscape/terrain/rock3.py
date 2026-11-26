"""Rockwork v3: cliffs built the way experienced terrain builders build them.

Structure:
  - inside: hidden 2-wide walls of staggered 2x4 bricks every ~10 studs, big plates
    (6x10) spanning between them as the deck;
  - behind the face: a backing wall 2 studs deep of 2x4 / 2x2 bricks, full height;
  - the face: a SKIN 1-2 studs deep in front of the backing wall, built column by column.
    Each column is an independent stack of small steps (1x2 / 1x1 bricks and plates),
    65/45/75 deg slopes and cheese slopes. Because plates are mixed in, slopes start at
    any plate height (60 % are off the brick grid), so the face is jagged at plate scale
    instead of showing brick-high bands. Dark green 1x1 plates sit on the little ledges.
  - on top: grass plates over the deck, overhanging the skin in places.

Rock3(b, H, ...) with H = {cell: height in plates} (a plateau, or several). Faces are
built along every boundary edge whose outside is lower (a skin column per edge cell).
"""
import random, collections
from brickscape.core.kit import (PLATES, BRICKS, pack, put_rect, pick, nbr, DIRS, OPP, value_noise, HIDDEN, tuft,
                 GREEN, DGREEN, BGREEN, OLIVE, LBG, DBG, put_slope)
from brickscape.terrain.rock2 import ring
from brickscape.terrain.ground import BIG_PLATES

# skin vocabulary: (name, part, height in plates, depth after, weight)
TWO_DEEP = [("brick", "3004", 3, 2, 0.7), ("plate", "3023", 1, 2, 0.5),
            ("s45", "3040b", 3, 1, 3.0), ("s65", "60481", 6, 1, 3.0), ("s75", "4460b", 9, 1, 0.7)]
ONE_DEEP = [("b1", "3005", 3, 1, 1.6), ("p1", "3024", 1, 1, 0.7), ("r1", "3062b", 3, 1, 0.2),
            ("inv", "3665", 3, 2, 1.2),            # undercut: back cell only below, both above
            ("ledge", "3023", 1, 2, 0.0)]          # ledge plate DISABLED: its front half hung over air (style rule: overhangs only as inverted slopes)
# mix measured on the Rock-Face reference: slopes ~31 % of the rock parts (cheese 36 %,
# 45 2x1 23 %, 65 2x1x2 19 %, 65 2x2x2 10 %, inverted 45 6 %), plates ~15 %


class Rock3:
    def __init__(self, b, H, seed=0, colour=DBG, accent=LBG, accent_amt=0.06, base_y=0, moss=0.35,
                 moss_colours=((DGREEN, 3), (GREEN, 1)), skin=None, grass=((GREEN, 1),),
                 grass_lip=0.35, hidden=None, wall_step=10, low=None, top_fn=None, board=None,
                 batter=0.8, batter_var=0.45, rock_top=None, overhang=0.24, tread_cover=0.85):
        """H: {cell: top height in plates}. skin(cell) -> True if that edge gets a skin (default
        all). low(cell) -> ground height outside (default 0).
        batter: studs of set-back per brick of height (style rule: faces LEAN BACK as they rise;
        the Rock-Face reference measures ~0.9). The plateau is cut back into a stepped apron of
        rock-topped tiers in front of each face; batter_var varies it per spot (bigger set-backs
        become ledges). None = vertical faces (old behaviour)."""
        self.b, self.H = b, dict(H)
        self.low = low or (lambda c: 0)
        self.board = board
        self.apron = set()
        self.rock_top = rock_top or ((colour, 12), (DGREEN, 1))
        if batter:
            self.H, self.apron = battered(self.H, batter, batter_var, seed, self.low, board)
        self.y0 = base_y
        self.rng = random.Random(seed)
        self.colour, self.accent, self.accent_amt = colour, accent, accent_amt
        self.patch = value_noise(seed * 7 + 3, 5.0)
        self.moss, self.moss_colours = moss, moss_colours
        self.skin_ok = skin or (lambda c: True)
        self.grass, self.grass_lip = grass, grass_lip
        self.hidden = (colour if batter else HIDDEN) if hidden is None else hidden
        self.wall_step = wall_step
        self.top_fn = top_fn
        self.overhang = overhang
        self.tread_cover = tread_cover
        self.ov_noise = value_noise(seed * 17 + 1, 2.5)
        self.surface = {}

    def col(self, c, y):
        if self.accent and self.patch(c[0], c[1]) < self.accent_amt:
            return self.accent
        return self.colour

    # ------------------------------------------------------------------ geometry
    def ground(self, c):
        """Top surface height (plates) of whatever is at c: grass top of a core cell, else low()."""
        return self.H[c] + 1 if c in self.H else self.low(c)

    def plan(self):
        """Skin columns: on every edge where the neighbour is >= 3 plates lower. The column
        stands in the lower cell (on its grass, or on the ground) against the higher cell."""
        self.skin = {}            # back cell -> (wall cell, direction, top height, base height)
        cand = []
        for c in sorted(self.H):
            for d in DIRS:
                bk = nbr(c, d)
                if self.board is not None and bk not in self.board:
                    continue
                if not self.skin_ok(c):
                    continue
                base = self.ground(bk)
                if base <= self.H[c] - 3 + 1:
                    cand.append((self.H[c] - base, bk, c, d, base))
        for drop, bk, c, d, base in sorted(cand, reverse=True):
            if bk not in self.skin:
                self.skin[bk] = (c, d, self.H[c], base)
        return self

    def rim(self):
        """Backing wall: core cells within 2 of a cell >= 3 plates lower (or outside)."""
        core = set(self.H)
        low_edge = {c for c in core if any(self.ground(nbr(c, d)) <= self.H[c] - 2 for d in DIRS)}
        r = set(low_edge)
        for c in low_edge:
            for d in DIRS:
                n = nbr(c, d)
                if n in core and self.H[n] == self.H[c]:
                    r.add(n)
        return r

    # ------------------------------------------------------------------ build
    def _fill(self, cells, y0, top, colour_of, rot=0):
        """Columns from y0 up to top(c) (exclusive). Each course is packed as ONE region
        (long bricks, staggered course to course), then plates finish odd heights."""
        b = self.b
        cells = set(cells)
        y, k = y0, rot
        maxt = max((top(c) for c in cells), default=y0)
        while y < maxt:
            full = {c for c in cells if top(c) - y >= 3}
            part = {c for c in cells if 0 < top(c) - y < 3}
            for colr, g in _groups(full, colour_of).items():
                for (x, z, w, d) in pack(g, BRICKS, rotate=k % 2 == 1):
                    put_rect(b, BRICKS, colr, x, z, w, d, y)
            # cells within 1-2 plates of their top: plates, one layer at a time
            for j in range(min(3, maxt - y)):
                layer = {c for c in part if top(c) - y > j}
                for colr, g in _groups(layer, colour_of).items():
                    for (x, z, w, d) in pack(g, PLATES, rotate=(k + j) % 2 == 1):
                        put_rect(b, PLATES, colr, x, z, w, d, y + j)
            cells -= part
            y += 3; k += 1

    def build(self, talus=0.45):
        b, rng = self.b, self.rng
        core = set(self.H)
        rim = self.rim()
        seen = {c for c in rim if any(self.ground(nbr(c, d)) <= self.H[c] - 2 for d in DIRS)}
        walls = {c for c in core - rim if c[0] % self.wall_step in (0, 1)}
        # 1. frame: backing walls and interior walls, up to one plate below each cell's top
        self._fill(rim | walls, self.y0, lambda c: self.H[c] - 1,
                   lambda c: self.colour if c in seen else self.hidden)
        b.step()
        # 2. deck over the rest, propped where a plate would float
        deck = core - rim - walls
        support = rim | walls
        for h in sorted({self.H[c] for c in deck}):
            cells = {c for c in deck if self.H[c] == h}
            for (x, z, w, d) in pack(cells, BIG_PLATES):
                fp = {(x + i, z + j) for i in range(w) for j in range(d)}
                if not fp & support:
                    cc = sorted(fp)[len(fp) // 2]
                    self._fill({cc}, self.y0, lambda c, h=h: h - 1, lambda c: self.hidden)
                    support.add(cc)
                put_rect(b, BIG_PLATES, self.hidden, x, z, w, d, h - 1)
        for colr, g in _groups(rim | walls, lambda c: self.colour if c in seen else self.hidden).items():
            for h in sorted({self.H[c] for c in g}):
                for (x, z, w, d) in pack({c for c in g if self.H[c] == h}, PLATES):
                    put_rect(b, PLATES, colr, x, z, w, d, h - 1)
        b.step()
        self.plan()
        lip = {c for c in self.skin if self.skin[c][0] not in self.apron and rng.random() < self.grass_lip}
        self._grass(lip)
        b.step()
        self._skin()
        self._treads()
        b.step()
        if talus:
            self.talus(talus)
            b.step()
        return self.surface

    def _treads(self):
        """Apron tier tops that no skin column stands on would show as bare grey stud fields
        (read as terraces): cover most with cheese / 1x1 rock bits; leave a few as mossy ledges."""
        b, rng = self.b, self.rng
        for c in sorted(self.apron):
            if c in self.skin or c in self.occupied:
                continue
            h = self.H[c] + 1
            r = rng.random()
            if r < self.tread_cover * 0.6:
                b.put("54200", self.colour, c[0], h, c[1], spin=rng.choice("NESW"))
            elif r < self.tread_cover:
                b.put("3005", self.colour, c[0], h, c[1]); b.put("54200", self.colour, c[0], h + 3, c[1], spin=rng.choice("NESW"))
            elif r < self.tread_cover + 0.08:
                b.put("3024", pick(rng, self.moss_colours), c[0], h, c[1])
                self.surface[c] = h + 1
            self.surface.pop(c, None) if r < self.tread_cover else None

    def talus(self, amount=0.45, depth=2):
        """Rubble skirt at the foot so the rock grows out of the ground: loose 1x1 stones,
        cheese-topped blocks and the odd 2-high lump, densest right against the face."""
        b, rng = self.b, self.rng
        rock = set(self.H) | set(self.skin) | self.occupied
        taken = set(rock)
        ring_ = rock
        for k in range(depth):
            ring_ = {nbr(c, d) for c in ring_ for d in DIRS} - taken
            if self.board is not None:
                ring_ &= self.board
            for c in sorted(ring_):
                if rng.random() > amount * (1.0 if k == 0 else 0.4):
                    continue
                g = self.low(c)
                colr = self.col(c, g)
                kind = pick(rng, [("pebble", 3), ("block", 3), ("round", 1), ("lump", 1 if k == 0 else 0)])
                if kind == "pebble":
                    b.put("3024", colr, c[0], g, c[1]); b.put("54200", colr, c[0], g + 1, c[1], spin=rng.choice("NESW"))
                elif kind == "block":
                    b.put("3005", colr, c[0], g, c[1]); b.put("54200", colr, c[0], g + 3, c[1], spin=rng.choice("NESW"))
                elif kind == "round":
                    b.put("3062b", colr, c[0], g, c[1])
                else:
                    b.put("3005", colr, c[0], g, c[1]); b.put("3005", colr, c[0], g + 3, c[1])
                    b.put("54200", colr, c[0], g + 6, c[1], spin=rng.choice("NESW"))
                taken.add(c)

    def _skin(self):
        """Each skin cell is a column 1 stud wide, 1 deep: the back half of a 2-deep piece
        sits against the wall cell, i.e. a 2-deep piece uses (skin cell, the cell in front)."""
        b, rng = self.b, self.rng
        H = self.H
        cols = sorted(self.skin.items())
        rng.shuffle(cols)
        occupied = self.occupied = set()
        for bk, (wall, d, top, base) in cols:
            fr = nbr(bk, d)
            two_ok = (self.board is None or fr in self.board) and self.ground(fr) == base and \
                fr not in self.skin and fr not in occupied
            y = max(self.y0, base)
            target = top - rng.choice([0, 0, 0, 0, 1, 2, 3])
            depth = 2 if two_ok else 1
            ffr = nbr(fr, d)
            # occasional small overhang (lean back, with a SLIGHT overhang now and then):
            # top-tier column, inverted slope over the cell in front + a 1x3 grass plate on top.
            # Runs of <= ~5 studs (noise patches). Needs the tier below to be >= 2 bricks lower.
            ov = (self.overhang and two_ok and wall not in self.apron and top - base >= 6
                  and self.ov_noise(bk[0], bk[1]) < self.overhang
                  and (self.board is None or ffr in self.board)
                  and self.ground(ffr) <= top - 7 and ffr not in occupied and ffr not in self.H
                  and (ffr not in self.skin or self.skin[ffr][2] <= top - 6))
            if ov:
                target = top - 3
            # start some columns a plate or two up (plate shims): breaks the brick grid
            while y < target:
                left = target - y
                if depth == 2:
                    opts = [o for o in TWO_DEEP if o[2] <= left]
                    if ov and left <= 6:          # square 2-deep block under the overhang
                        opts = [o for o in opts if o[0] in ("brick", "plate")]
                else:
                    opts = [o for o in ONE_DEEP if o[2] <= left and (o[0] not in ("ledge", "inv") or two_ok)]
                if not opts:
                    break
                name, part, hgt, depth_after, _ = pick(rng, [(o, o[4]) for o in opts])
                colr = self.col(bk, y)
                if depth == 2:
                    if name.startswith("s"):
                        put_slope(b, part, colr, fr, d, y, 2)
                    else:
                        put_slope(b, part, colr, fr, d, y, 2)   # 1x2 brick/plate across the depth
                    occupied.add(fr)
                else:
                    if name in ("ledge", "inv"):
                        put_slope(b, part, colr, fr, d, y, 2)
                        occupied.add(fr)
                        if name == "ledge" and rng.random() < 0.6:   # moss on the little ledge, mid-face
                            b.put("3024", pick(rng, self.moss_colours), fr[0], y + 1, fr[1])
                            depth_after = 1
                            two_ok = False
                            y += hgt
                            depth = depth_after
                            continue
                    else:
                        b.put(part, colr, bk[0], y, bk[1])
                y += hgt
                depth = depth_after
            if ov and y == target and depth == 2:
                colr = self.col(bk, y)
                b.put("3005", colr, bk[0], y, bk[1])
                put_slope(b, "3665", colr, ffr, d, y, 2)
                put_slope(b, "3623", pick(rng, self.grass), ffr, d, top, 3)
                occupied.add(fr); occupied.add(ffr)
                self.overhung = getattr(self, "overhung", set()) | {ffr}
                continue
            # top of the column: grass lip, moss, cheese or nothing
            r = rng.random()
            if y == top and bk in getattr(self, "lip", ()):
                b.put("3024", pick(rng, self.grass), bk[0], y, bk[1])
                self.surface[bk] = y + 1
                continue
            if y < top and r < (self.moss * 0.4 if wall in self.apron else self.moss):
                b.put("3024", pick(rng, self.moss_colours), bk[0], y, bk[1])
                self.surface[bk] = y + 1
            elif y < top - 1 and r < self.moss + 0.55:
                b.put("54200", self.col(bk, y), bk[0], y, bk[1], spin=d)
            elif y <= top:
                self.surface[bk] = y

    def _grass(self, lip):
        b, rng = self.b, self.rng
        core = set(self.H)
        self.lip = lip
        for h in sorted({self.H[c] for c in core}):
            cells = {c for c in core if self.H[c] == h}
            groups = collections.defaultdict(set)
            for c in cells:
                colr = self.top_fn(c) if self.top_fn else None
                if c in self.apron:
                    colr = pick(rng, self.rock_top)
                groups[colr or pick(rng, self.grass)].add(c)
            for colr, g in groups.items():
                for (x, z, w, d) in pack(g, PLATES, maxsize=24):
                    put_rect(b, PLATES, colr, x, z, w, d, h)
            for c in cells:
                if c not in self.skin:
                    self.surface[c] = h + 1


def battered(H, batter=0.8, var=0.45, seed=0, low=lambda c: 0, board=None, step=2):
    """Cut a plateau height map back so faces lean back as they rise: TIERS about `step` studs
    deep and step*3/batter plates tall (default 2 studs per ~2.5 bricks), so each tier's skin is
    tall enough for 65/75 deg slope striations (1-stud tiers looked like busy little cubes).
    Constraint: G[c] <= G[n] + tier(c) for every n within Chebyshev distance step(c); outside
    cells count at their ground height. Tier height and depth vary per spot (blocky noise) so
    the face is not a regular staircase; a deeper tier reads as a ledge.
    Returns (new H, apron cells that were lowered: they get rock tops, not grass)."""
    from brickscape.terrain.rock2 import blocky
    nz = blocky(value_noise(seed * 13 + 5, 3.5), 3)     # 3-5 stud patches: tier breaks at varying heights, no long seam
    nd = blocky(value_noise(seed * 13 + 9, 5.0), 3)
    tier, reach = {}, {}
    for c in H:
        b_ = max(0.2, batter * (1 + var * (2 * nz(c[0], c[1]) - 1)))
        s = step + (1 if nd(c[0], c[1]) > 0.85 else 0)     # occasional deeper set-back = ledge
        reach[c] = s
        tier[c] = max(6, 3 * round(step / b_))    # whole bricks, >= 2 bricks: room for 65/75 slope ribs
    G = dict(H)
    changed = True
    while changed:
        changed = False
        for c in sorted(G):
            best = G[c]
            r = reach[c]
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    n = (c[0] + dx, c[1] + dz)
                    if n == c:
                        continue
                    if n in G:
                        lim = G[n] + tier[c]
                    elif board is None or n in board:
                        lim = low(n) + tier[c]
                    else:
                        continue            # board edge: not a face
                    if lim < best:
                        best = lim
            if best < G[c]:
                G[c] = best
                changed = True
    apron = {c for c in G if G[c] < H[c]}
    return G, apron


def _groups(cells, colour_of):
    out = collections.defaultdict(set)
    for c in cells:
        out[colour_of(c)].add(c)
    return out


# --------------------------------------------------------------------- facet walls
# 87620 "Brick 2x2 Facet": two opposite corners cut, studs on one diagonal. Laid corner to
# corner along a 45 degree line (+-2 studs each way per brick), with alternate courses
# shifted one stud along the line, they build a DIAGONAL wall with a faceted zig-zag face
# (reverse-engineered from the Dirt Valley reference).
FACET_ROT = {(1, 1): (1, 0, 0, 0, 1, 0, 0, 0, 1), (-1, -1): (1, 0, 0, 0, 1, 0, 0, 0, 1),
             (1, -1): (0, 0, 1, 0, 1, 0, -1, 0, 0), (-1, 1): (0, 0, 1, 0, 1, 0, -1, 0, 0)}


def facet_wall(b, x0, z0, dx, dz, n, y0, courses, colour, shift=True, last_short=True):
    """Diagonal wall of facet bricks. (x0, z0): grid point (stud corner) at the centre of the
    first brick; (dx, dz) in {+-1}: direction; n bricks per course; height = courses bricks."""
    R = FACET_ROT[(dx, dz)]
    placed = []
    for k in range(courses):
        off = 1 if (shift and k % 2) else 0
        m = n - (1 if (off and last_short) else 0)
        for i in range(m):
            cx = x0 + dx * (2 * i + off)
            cz = z0 + dz * (2 * i + off)
            M = (b.X(cx), b.Y(y0 + 3 * k) - 24, b.Z(cz), *R)
            placed.append(b.raw("87620", colour, M))
    return placed


def facet_edges(b, core, H, colour, cap=None, board=None, rng=None, cap_colours=((GREEN, 1),)):
    """Clad the 45-degree staircase edges of `core` with facet bricks.

    Candidate brick centres are grid corner points whose 2x2 cells are all outside the core
    and which touch the core on two sides (an inside corner of the staircase). Bricks are
    chained along each diagonal; courses alternate the shift. Returns the cells covered."""
    core = set(core)
    out = set()
    pts = []
    for (x, z) in core:
        for px, pz in ((x, z), (x + 1, z), (x, z + 1), (x + 1, z + 1)):
            pts.append((px, pz))
    cand = set()
    for (px, pz) in set(pts):
        cells = {(px - 1, pz - 1), (px, pz - 1), (px - 1, pz), (px, pz)}
        inside = cells & core
        if len(inside) == 1:                         # outside corner of a 1-stud step
            c = inside.pop()
            # the brick must sit fully outside: shift it diagonally away from the core cell
            sx = 1 if c[0] == px - 1 else -1
            sz = 1 if c[1] == pz - 1 else -1
            q = (px + sx, pz + sz)
            qc = {(q[0] - 1, q[1] - 1), (q[0], q[1] - 1), (q[0] - 1, q[1]), (q[0], q[1])}
            if not qc & core and (board is None or qc <= board):
                # diagonal direction of the wall = perpendicular to (sx, sz)
                cand.add((q, (sx, -sz) if sx * sz > 0 else (sx, -sz)))
    placed = []
    # group the candidate points into diagonal lines; consecutive points are 1 stud apart.
    # Course k uses every other point (parity k), so each brick bridges two below it.
    lines = collections.defaultdict(list)
    for (q, d) in cand:
        key = (d, q[0] + q[1]) if d in ((1, -1), (-1, 1)) else (d, q[0] - q[1])
        lines[key].append(q)
    used = {0: set(), 1: set()}
    for key, pts_ in lines.items():
        d = key[0]
        R = FACET_ROT[d]
        pts_.sort()
        for idx, q in enumerate(pts_):
            qc = {(q[0] - 1, q[1] - 1), (q[0], q[1] - 1), (q[0] - 1, q[1]), (q[0], q[1])}
            nb = [H[c] for c in core if abs(c[0] + .5 - q[0]) <= 1.6 and abs(c[1] + .5 - q[1]) <= 1.6]
            if not nb:
                continue
            top = min(nb)                         # facets rise to the top of the core
            courses = max(1, top // 3)
            par = idx % 2
            if qc & used[par]:
                continue
            used[par] |= qc
            for k in range(par, courses, 2):
                M = (b.X(q[0]), b.Y(3 * k) - 24, b.Z(q[1]), *R)
                placed.append(b.raw("87620", colour, M))
            out |= qc
            if (courses - 1) % 2 == par:
                y = 3 * courses
                for j in range(top - y):              # plate shims to the core's top
                    b.put("3022", colour, q[0] - 1, y + j, q[1] - 1)
                if cap is not None:
                    b.put("3022", pick(rng, cap_colours), q[0] - 1, top, q[1] - 1)
    return out, placed
