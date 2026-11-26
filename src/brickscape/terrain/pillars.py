"""Pillar rock: rockwork as many independent vertical prisms.

The technique:
  - the rock is a crowd of PILLARS 1-2 studs wide, each a clean stack of plain bricks (smooth
    vertical faces = brick sides), NOT a skin of small bits;
  - neighbouring pillars end at clearly different heights (2+ plates apart), so there is no
    horizontal seam: the grain is vertical;
  - the face leans back because the pillars further back are taller (rows step up), and a pillar
    can itself step back once with a steep slope (chamfer);
  - each pillar has a cap: a slope facing out (flat-topped pillars), or a ridge / pyramid on the
    free-standing tall ones (pinnacles);
  - two greys by whole pillar; almost no 1x1 bits; no moss.

PillarRock(b, T, ...).build(): T = {cell: rock top height in plates}. Cells not in T are ground
or path (low(c) gives their height). Hidden parts below every pillar's visible part are packed
with big bricks.
"""
import random, collections
from brickscape.core.kit import BRICKS, PLATES, pack, put_rect, pick, nbr, DIRS, put_slope, LBG, DBG, HIDDEN

OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
TILES = {(1, 1): "3070b", (1, 2): "3069b", (2, 2): "3068b"}
# corner (double convex) slopes: spin that makes the two sloped faces look along the given pair
CORNER_SPIN = {frozenset("EN"): "N", frozenset("ES"): "E", frozenset("WS"): "S", frozenset("WN"): "W"}
HIGH_CORNER = {"N": ("W", "S"), "E": ("W", "N"), "S": ("E", "N"), "W": ("E", "S")}


class PillarRock:
    def __init__(self, b, T, seed=0, colours=((LBG, 7), (DBG, 3)), low=None, board=None,
                 sizes=(((2, 2), 9), ((1, 2), 2)), jitter=(0, 0, 1, 2),
                 chamfer=0.9, spire=0.12, hidden=None, tile_tops=1.0, along=0.65, mass_amp=6, flow=False, min_diff=2, style="bricks", flat=(), flat_colour=None):
        """flat: cells built as a plain flat top (plateau for a building), not as pillars."""
        self.b, self.T = b, dict(T)
        self.rng = random.Random(seed)
        self.colours = colours
        self.low = low or (lambda c: 0)
        self.board = board
        self.sizes, self.jitter = sizes, jitter
        self.chamfer, self.spire, self.tile_tops, self.along = chamfer, spire, tile_tops, along
        self.mass_amp = mass_amp
        self.style = style        # "slopes": visible pillars are stacks of slopes (the reference look)
        self.flow = flow          # caps point DOWNHILL on the (smooth) envelope, so they line up
        self.min_diff = min_diff if not flow else 0
        self.hidden = hidden if hidden is not None else HIDDEN
        self.flat = set(flat) & set(T)
        self.flat_colour = flat_colour or colours[0][0]

    def height(self, c):
        return self.T[c] if c in self.T else self.low(c)

    # ---------------------------------------------------------------- pillars
    def partition(self):
        """Random 1x1 / 1x2 / 2x2 footprints; 1x2 lies along the local downhill direction
        (so a slope cap can face out)."""
        rng = self.rng
        free = set(self.T) - self.flat
        pillars = []
        for c in sorted(free, key=lambda c: (rng.random())):
            if c not in free:
                continue
            out = self.outward(c)
            for _ in range(6):
                (w, d) = pick(rng, self.sizes)
                if (w, d) == (1, 2):
                    # mostly ACROSS the face (a 2-wide face, not a 1-wide finger)
                    across = {"N": "E", "S": "E", "E": "N", "W": "N"}
                    along = (across[out] if rng.random() < 0.65 else out) if out else rng.choice("NESW")
                    cells = {c, nbr(c, along)} if rng.random() < 0.5 else {c, nbr(c, OPP[along])}
                elif (w, d) == (2, 2):
                    dx, dz = rng.choice([(0, 0), (-1, 0), (0, -1), (-1, -1)])
                    x0, z0 = c[0] + dx, c[1] + dz
                    cells = {(x0, z0), (x0 + 1, z0), (x0, z0 + 1), (x0 + 1, z0 + 1)}
                else:
                    cells = {c}
                # a pillar should not span a big height change
                if cells <= free and max(self.T[q] for q in cells) - min(self.T[q] for q in cells) <= 8:
                    break
            else:
                # fallback: any 1x2 that fits, only then a 1x1
                cells = {c}
                for dd in "NESW":
                    n = nbr(c, dd)
                    if n in free and abs(self.T[n] - self.T[c]) <= 6:
                        cells = {c, n}
                        break
            free -= cells
            pillars.append(cells)
        return pillars

    def outward(self, c):
        """Direction of the lowest neighbour (where the face looks), or None if none is lower."""
        best, bd = self.T.get(c, 0), None
        for d in "NESW":
            n = nbr(c, d)
            if self.board is not None and n not in self.board:
                continue
            h = self.height(n)
            if h < best - 1:
                best, bd = h, d
        return bd

    def build(self):
        b, rng = self.b, self.rng
        self.pillars = self.partition()
        # pillar heights: the envelope + jitter, so neighbours differ; a few spires stand proud
        H, col, cap = {}, {}, {}
        from brickscape.core.kit import value_noise
        mass = value_noise(rng.randint(0, 10 ** 6), 4.0)      # low-frequency: pillars cluster into masses
        for i, P in enumerate(self.pillars):
            c0 = min(P)
            h = max(self.T[c] for c in P) - rng.choice(self.jitter) - round(self.mass_amp * mass(c0[0], c0[1]))
            if rng.random() < self.spire:
                h += rng.choice((3, 4, 6))
                cap[i] = "spire"
            H[i] = max(h, 2)
            col[i] = pick(rng, self.colours)
        # neighbour difference: if a pillar ends within 1 plate of a neighbour, move it
        owner = {c: i for i, P in enumerate(self.pillars) for c in P}
        for i, P in enumerate(self.pillars):
            nb = {owner[nbr(c, d)] for c in P for d in "NESW" if nbr(c, d) in owner} - {i}
            if any(abs(H[i] - H[j]) < self.min_diff for j in nb):
                H[i] += self.min_diff if rng.random() < 0.5 else -self.min_diff
        self.H, self.owner, self.col = H, owner, col
        cellh = {c: H[owner[c]] for c in owner}
        self.cellh = cellh
        cellh.update({c: self.T[c] for c in self.flat})
        # visible start of each pillar: the lowest neighbouring surface (ground / path / pillar)
        start = {}
        for i, P in enumerate(self.pillars):
            lows = []
            for c in P:
                for d in "NESW":
                    n = nbr(c, d)
                    if n in P:
                        continue
                    if self.board is not None and n not in self.board:
                        continue
                    lows.append(cellh[n] if n in cellh else self.low(n))
            s = min(lows) if lows else H[i]
            s = max(0, min(s, H[i] - 3))
            start[i] = s - s % 3            # whole bricks of hidden core
        # 1. hidden core: per course, pack all cells whose pillar starts above it
        cells_start = {c: start[owner[c]] for c in owner}
        cells_start.update({c: self.T[c] - self.T[c] % 3 for c in self.flat})
        top = max(cells_start.values(), default=0)
        y, k = 0, 0
        while y < top:
            course = {c for c, s in cells_start.items() if s >= y + 3}
            for (x, z, w, d) in pack(course, BRICKS, rotate=k % 2 == 1):
                put_rect(b, BRICKS, self.hidden, x, z, w, d, y)
            y += 3; k += 1
        b.step()
        # flat top: plates from the core up to T
        for h in sorted({self.T[c] for c in self.flat}):
            g = {c for c in self.flat if self.T[c] == h}
            for j in range(h % 3):
                for (x, z, w, d) in pack(g, PLATES, rotate=j % 2 == 1):
                    put_rect(b, PLATES, self.flat_colour, x, z, w, d, h - h % 3 + j)
        # 2. pillars
        for i, P in enumerate(self.pillars):
            if self.style == "slopes":
                self._slope_pillar(i, P, start[i], H[i], col[i], cap.get(i))
            else:
                self._pillar(i, P, start[i], H[i], col[i], cap.get(i))
        b.step()
        return cellh

    def _edge(self, P, d, h):
        """Is this pillar a real edge of the form toward d (its top stands >= 3 plates over the
        surface in front)? Only edges get slope caps in flow mode; the rest end flush (tiles),
        so neighbouring pillars read as one face."""
        hs = []
        for c in P:
            n = nbr(c, d)
            if n in P:
                continue
            hs.append(self.cellh.get(n, self.height(n)) if hasattr(self, "cellh") else self.height(n))
        return bool(hs) and h - max(hs) >= 3

    def _slope_pillar(self, i, P, y0, h, colr, cap):
        """Reference look: the visible part of a pillar is a STACK OF SLOPES (75 / 65 / 45 deg),
        each hiding the studs of the one below, so every visible surface is a sloped facet and
        plain brick sides hardly show. Direction: downhill on the envelope (flow), preferring
        along the face (side profiles draw diagonal edges), else out of the face. Corner pillars
        stack corner slopes. The top slope's studs get tiles."""
        b, rng = self.b, self.rng
        xs = sorted({c[0] for c in P}); zs = sorted({c[1] for c in P})
        x0, z0, w, d = xs[0], zs[0], len(xs), len(zs)
        def deep(q):
            return (w if q in "EW" else d) == 2
        outs = self.outs(P)
        y = y0
        # plate shim so the bottom of the stack fits the height exactly (whole slopes above)
        span = h - y0
        if span < 3:
            for j in range(span):
                put_rect(b, PLATES, colr, x0, z0, w, d, y); y += 1
            put_rect(b, TILES, colr, x0, z0, w, d, y)
            return
        shim = span % 3
        for j in range(shim):
            put_rect(b, PLATES, colr, x0, z0, w, d, y); y += 1
        # corner pillar: stack of corner slopes
        pair = next((frozenset(q) for q in ("EN", "ES", "WS", "WN") if set(q) <= outs), None)
        if len(P) == 4 and pair and rng.random() < 0.6:
            spin = CORNER_SPIN[pair]
            hx, hz = HIGH_CORNER[spin]
            hc = (x0 + (1 if hx == "E" else 0), z0 + (1 if hz == "S" else 0))
            while y < h:
                left = h - y
                if left >= 9 and rng.random() < 0.75:
                    b.put("3685", colr, x0, y, z0, spin=spin); y += 9
                else:
                    b.put("3045", colr, x0, y, z0, spin=spin); y += 3
            b.put("3070b", colr, hc[0], y, hc[1])
            return
        # direction of the slopes
        cand = [q for q in "NESW" if deep(q) and q in outs]
        if self.flow:
            def drop(q):
                ns = [nbr(c, q) for c in P]
                return sum(self.T[c] for c in P) / len(P) - sum(self.height(n) for n in ns) / len(ns)
            cand = [q for q in "NESW" if deep(q) and drop(q) > 0] or cand
            sd = max(cand, key=drop) if cand else None
        else:
            sd = rng.choice(cand) if cand else None
        if sd is None:
            dq = [q for q in "NESW" if deep(q)]
            sd = rng.choice(dq) if dq else None
        if sd is None or len(P) == 1:          # 1x1: brick stack + tile (rare)
            while y < h:
                if h - y >= 9:
                    b.put("14716", colr, x0, y, z0); y += 9
                else:
                    b.put("3005", colr, x0, y, z0); y += 3
            b.put("3070b", colr, x0, y, z0)
            return
        two = len(P) == 4
        def fr_cell():
            k = {"W": lambda c: c[0], "E": lambda c: -c[0], "N": lambda c: c[1], "S": lambda c: -c[1]}[sd]
            m = min(k(c) for c in P)
            return [c for c in P if k(c) == m]
        front = fr_cell()
        back = [c for c in P if c not in front]
        # what stands in front: the cap only needs to cover the drop to the row in front
        hf = max(self.cellh.get(nbr(c, sd), self.height(nbr(c, sd))) for c in front)
        hf = max(y, min(hf, h))
        def slope(hh, yy):
            if two:
                b.put({9: "3684c", 6: "3678b", 3: "3039"}[hh], colr, x0, yy, z0, spin=sd)
            else:
                put_slope(b, {9: "4460b", 6: "60481a", 3: "3040b"}[hh], colr, front[0], sd, yy, 2)
        if cap == "spire" and two and h - y >= 9:
            body = h - 6
        else:
            body = None
        drop = h - hf
        if body is None and drop <= 9:
            # one cap slope covering the drop; plain bricks below are hidden by the row in front
            caph = max([q for q in (9, 6, 3) if q <= max(3, drop)] + [3])
            caph = min(caph, h - y)
            caph -= caph % 3
            body = h - caph
            while y < body:
                if body - y >= 9 and two:
                    b.put("30145", colr, x0, y, z0); y += 9
                elif body - y >= 9:
                    b.put("22886", colr, x0, y, z0, spin="N" if w == 2 else "E"); y += 9
                elif body - y >= 3:
                    put_rect(b, BRICKS, colr, x0, z0, w, d, y); y += 3
                else:
                    put_rect(b, PLATES, colr, x0, z0, w, d, y); y += 1
            if caph:
                slope(caph, y); y += caph
        else:
            # steep: hidden bricks up to the row in front, then a stack of slopes
            target = body if body is not None else h
            lowtop = hf - (hf - y) % 3
            while y < lowtop:
                if lowtop - y >= 9 and two:
                    b.put("30145", colr, x0, y, z0); y += 9
                else:
                    put_rect(b, BRICKS, colr, x0, z0, w, d, y); y += 3
            while y < target:
                left = target - y
                opts = [(hh, wt) for hh, wt in ((9, 4), (6, 3), (3, 1)) if hh <= left]
                if not opts:
                    put_rect(b, PLATES, colr, x0, z0, w, d, y); y += 1
                    continue
                hh = pick(rng, opts)
                slope(hh, y); y += hh
            if body is not None and y == body:
                b.put("3688", colr, x0, y, z0)
                return
        bx = sorted({c[0] for c in back}); bz = sorted({c[1] for c in back})
        put_rect(b, TILES, colr, bx[0], bz[0], len(bx), len(bz), y)

    def outs(self, P):
        """Directions in which this pillar has a lower neighbour (open sides)."""
        res = set()
        for c in P:
            for d in "NESW":
                n = nbr(c, d)
                if n in P or (self.board is not None and n not in self.board):
                    continue
                if self.height(n) < self.T[c] - 1:
                    res.add(d)
        return res

    def _corner(self, P, y0, h, colr, pair):
        """2x2 pillar on a corner: bricks, maybe one 75 deg corner chamfer (3685; above it only
        the high corner cell continues), and a corner cap (3685 75 deg or 3045 45 deg)."""
        b, rng = self.b, self.rng
        x0 = min(c[0] for c in P); z0 = min(c[1] for c in P)
        spin = CORNER_SPIN[pair]
        hx, hz = HIGH_CORNER[spin]
        hc = (x0 + (1 if hx == "E" else 0), z0 + (1 if hz == "S" else 0))
        cap = pick(rng, [("3685", 3), ("3045", 1)])
        caph = 9 if cap == "3685" else 3
        y = y0
        cham = None
        if h - y0 >= 9 + caph + 3 and rng.random() < self.chamfer:
            cham = y0 + 3 * rng.randint(0, (h - y0 - 9 - 3) // 3)
        if cham is not None:
            while y < cham:
                put_rect(b, BRICKS, colr, x0, z0, 2, 2, y); y += 3
            b.put("3685", colr, x0, y, z0, spin=spin); y += 9
            while y < h:                                     # the high corner continues 1x1
                if h - y >= 3:
                    b.put("3005", colr, hc[0], y, hc[1]); y += 3
                else:
                    b.put("3024", colr, hc[0], y, hc[1]); y += 1
            b.put("3070b", colr, hc[0], y, hc[1])
            return
        body = max(y0, h - caph)
        while y < body:
            if body - y >= 9:
                b.put("30145", colr, x0, y, z0); y += 9
            elif body - y >= 3:
                put_rect(b, BRICKS, colr, x0, z0, 2, 2, y); y += 3
            else:
                put_rect(b, PLATES, colr, x0, z0, 2, 2, y); y += 1
        if h - y == caph:
            b.put(cap, colr, x0, y, z0, spin=spin)
        else:
            put_rect(b, TILES, colr, x0, z0, 2, 2, y)

    def _pillar(self, i, P, y0, h, colr, cap):
        """Visible part of one pillar, bottom to top: an optional plate shim (breaks seam lines),
        brick runs, at most one chamfer (75 deg slope across the front row, after which only the
        back row continues), then a cap: a slope facing out (45 / 65 / 75), a pyramid / ridge on
        spires, or a tile."""
        b, rng = self.b, self.rng
        out = None
        for c in sorted(P):
            out = out or self.outward(c)
        def box(cells):
            xs = sorted({c[0] for c in cells}); zs = sorted({c[1] for c in cells})
            return xs[0], zs[0], len(xs), len(zs)
        def front_row(cells, d):
            k = {"W": lambda c: c[0], "E": lambda c: -c[0], "N": lambda c: c[1], "S": lambda c: -c[1]}[d]
            m = min(k(c) for c in cells)
            return {c for c in cells if k(c) == m}
        def deep(cells, d):     # 2 deep along d?
            x0, z0, w, dd = box(cells)
            return (w if d in "EW" else dd) == 2
        # ---- corner pillars (2x2 with two adjacent open sides): diagonal facets, like the
        # reference's faces that look 45 deg off the grid
        cells = set(P)
        outs = self.outs(P)
        pair = next((frozenset(q) for q in ("EN", "ES", "WS", "WN") if set(q) <= outs), None)
        if len(P) == 4 and pair and cap != "spire" and rng.random() < 0.75:
            return self._corner(P, y0, h, colr, pair)
        # ---- slope direction: mostly ALONG the face (left/right), so the face shows the slopes'
        # side profiles as diagonal edges (the reference look); sometimes out of the face
        perp = {"N": "EW", "S": "EW", "E": "NS", "W": "NS"}
        sd = None
        if out and self.flow:
            # downhill on the envelope: compare the mean envelope height one step each way
            def drop(q):
                ns = [nbr(c, q) for c in cells]
                return sum(self.T[c] for c in cells) / len(cells) - sum(self.height(n) for n in ns) / len(ns)
            cand = [q for q in "NESW" if deep(cells, q) and drop(q) > 0]
            if cand:
                along = [q for q in cand if q in perp[out]]
                pool = along if along and rng.random() < self.along else cand
                sd = max(pool, key=drop)
        elif out:
            cand = [q for q in perp[out] if deep(cells, q)]
            if cand and rng.random() < self.along:
                sd = rng.choice(cand)
            elif deep(cells, out):
                sd = out
        # ---- cap plan
        if cap == "spire":
            capk = "pyramid" if len(P) == 4 else ("ridge" if len(P) == 2 else "tile")
        elif sd and (not self.flow or self._edge(P, sd, h)):
            capk = pick(rng, [("s75", 4), ("s65", 3), ("s45", 1)])
        elif not out and len(P) >= 2 and rng.random() < 0.6:
            capk = "pyramid" if len(P) == 4 else "ridge"     # free-standing tops end pointed
        else:
            capk = "tile"
        # ---- chamfer plan (needs 2 deep along the slope direction and room)
        cham = None
        if sd and cap != "spire" and rng.random() < self.chamfer:
            room = h - y0 - 9 - 3
            if room >= 0:
                cham = y0 + 3 * rng.randint(0, room // 3)
        out = sd
        caph = {"pyramid": 6, "ridge": 3, "s75": 9, "s65": 6, "s45": 3, "tile": 0}
        y = y0
        shim = rng.choice((0, 0, 1, 2))
        if h - y0 - shim < 3:
            shim = 0
        for j in range(shim):
            x0, z0, w, d = box(cells)
            put_rect(b, PLATES, colr, x0, z0, w, d, y); y += 1
        if cham is not None:
            cham = max(cham, y)
        while True:
            # after a chamfer the cap must fit the remaining (1-deep) cells
            ck = capk if (deep(cells, out) if out else True) or capk in ("tile",) else "tile"
            if not (out and deep(cells, out)) and ck.startswith("s"):
                ck = "tile"
            body = h - caph[ck]
            if cham is not None and y == cham and body - y >= 9 + 3 and deep(cells, out):
                fr = front_row(cells, out)
                part = "4460b" if len(fr) == 1 else "3684c"
                if len(fr) == 1:
                    put_slope(b, part, colr, next(iter(fr)), out, y, 2)
                else:
                    x0, z0, w, d = box(cells)
                    b.put(part, colr, x0, y, z0, spin=out)
                y += 9
                cells = cells - fr
                cham = None
                continue
            if y >= body:
                break
            x0, z0, w, d = box(cells)
            left = body - y
            if left >= 9 and len(cells) == 4:
                b.put("30145", colr, x0, y, z0); y += 9
            elif left >= 9 and len(cells) == 2:          # 1x2x3: no seams on narrow pillars
                b.put("22886", colr, x0, y, z0, spin="N" if w == 2 else "E"); y += 9
            elif left >= 9 and len(cells) == 1:
                b.put("14716", colr, x0, y, z0); y += 9
            elif left >= 3:
                put_rect(b, BRICKS, colr, x0, z0, w, d, y); y += 3
            else:
                put_rect(b, PLATES, colr, x0, z0, w, d, y); y += 1
        x0, z0, w, d = box(cells)
        if y != body:                     # chamfer overshoot: no room for the cap, end flush
            put_rect(b, TILES, colr, x0, z0, w, d, y)
            return
        if ck == "pyramid":
            b.put("3688", colr, x0, y, z0)
        elif ck == "ridge":
            b.put("3044c", colr, x0, y, z0, spin="E" if w == 2 else "N")
        elif ck.startswith("s"):
            fr = front_row(cells, out)
            back = cells - fr
            if len(fr) == 1:
                part = {"s75": "4460b", "s65": "60481a", "s45": "3040b"}[ck]
                put_slope(b, part, colr, next(iter(fr)), out, y, 2)
            else:
                part = {"s75": "3684c", "s65": "3678b", "s45": "3039"}[ck]
                b.put(part, colr, x0, y, z0, spin=out)
            # tile the slope's top studs: the reference's rock shows smooth tops, no studs
            yt = y + caph[ck]
            bx, bz, bw, bd = box(back)
            put_rect(b, TILES, colr, bx, bz, bw, bd, yt)
        elif rng.random() < self.tile_tops:
            put_rect(b, TILES, colr, x0, z0, w, d, y)
