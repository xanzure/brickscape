"""Rockwork v2, modelled on the reference builds (Rock Face, Mountain House, Lookout Tower).

The rock is a stack of 1-brick layers L[0..n]. Each layer's outline is a little
smaller than the one below in irregular blocky chunks, so the face steps back
1 stud every brick or two. Pieces follow the geometry:
  - face cell where the layer above steps back  -> slope facing out (45 deg; 65/75 deg
    when the face runs straight for 2-3 layers first; 2-wide when the neighbour matches)
  - face cell where the layer above continues   -> brick (flat wall)
  - face cell that overhangs the layer below    -> inverted slope (undercut)
  - ledges (exposed brick tops)                 -> moss 1x1s, cheese slopes, pebbles, bare studs
  - wide tops                                   -> cap plates, grass with rock showing through
Inside is hollow: only a 2-deep skin, walls under the skins of higher layers, and
hidden columns under wide caps.
"""
import random, collections
from brickscape.core.brick import info
from brickscape.core.kit import (PLATES, BRICKS, pack, put_rect, pick, nbr, DIRS, OPP, value_noise, HIDDEN, WHITE,
                 GREEN, DGREEN, BGREEN, OLIVE, LBG, DBG, tuft)

SLOPE1 = {1: "3040", 2: "60481", 3: "4460"}       # 1-wide, by layers spanned
SLOPE2 = {1: "3039", 2: "3678b", 3: "30499"}      # 2-wide
# family -> {width along the face: part}; merged from 1-wide placements
WIDTHS = {("45", 1): {1: "3040", 2: "3039", 3: "3038", 4: "3037"},
          ("45", 2): {1: "60481", 2: "3678b"},
          ("45", 3): {1: "4460", 2: "30499"},
          ("33", 1): {1: "4286", 2: "3298", 4: "3297"}}
INV1, INV2 = "3665", "3660"


def ring(cells, n):
    """Cells of `cells` within n steps of its outside."""
    out, frontier = set(), {c for c in cells if any(nbr(c, d) not in cells for d in DIRS)}
    for _ in range(n):
        out |= frontier
        frontier = {nbr(c, d) for c in frontier for d in DIRS if nbr(c, d) in cells} - out
    return out


def side_dirs(d):
    return ("E", "W") if d in "NS" else ("N", "S")


class Rock:
    def __init__(self, b, H, base_y=0, seed=0, colour=DBG, accent=None, accent_amt=0.0,
                 moss=0.22, moss_colours=((DGREEN, 3), (GREEN, 2)), undercut=0.25,
                 cap_grass=0.7, steep=(5, 3, 1.5), wide=0.5, hidden=None, gentle=0.0,
                 rim_round=0.55, ledge_cheese=0.30, pebble=0.005, colour_fn=None, gentle_fn=None,
                 moss_fn=None, stairs=(), tread=None, slope_fn=None, terrace_fn=None,
                 forbid=(), lip=0.3, grass=((GREEN, 1),), solid_fn=None, cap_fn=None, above=None,
                 snow_from=None, snow=WHITE, keep_clear=()):
        """H: {cell: layers}. colour: main rock colour; accent: second colour in patches."""
        self.b, self.H, self.y0 = b, dict(H), base_y
        self.rng = random.Random(seed)
        self.colour, self.accent, self.accent_amt = colour, accent, accent_amt
        self.patch = value_noise(seed * 13 + 5, 5.0)
        self.moss, self.moss_colours, self.undercut = moss, moss_colours, undercut
        self.cap_grass, self.steep, self.wide = cap_grass, steep, wide
        self.gentle, self.rim_round, self.ledge_cheese, self.pebble = gentle, rim_round, ledge_cheese, pebble
        self.colour_fn, self.gentle_fn, self.moss_fn = colour_fn, gentle_fn, moss_fn
        self.stairs, self.tread = set(stairs), tread
        # terraces: cells where terrace_fn(c) is true get no slopes; their exposed
        # tops become grass treads (with a ragged overhanging lip)
        self.slope_fn, self.terrace_fn = slope_fn, terrace_fn
        self.forbid, self.lip, self.grass = set(forbid), lip, grass
        self.solid = solid_fn or (lambda c, y: False)   # other structures next to this one
        self.cap_fn = cap_fn                             # (cell, layer) -> cap colour override
        self.snow_from, self.snow = snow_from, snow      # layers >= snow_from: snowy ledges/caps
        self.keep_clear = set(keep_clear)                # no ledge dressing here (bridges, buildings)
        self.hidden = HIDDEN if hidden is None else hidden
        self.n = max(H.values()) if H else 0
        self.L = [{c for c, h in H.items() if h > k} for k in range(self.n)] + [set(above or ())]
        self.used = collections.defaultdict(set)     # layer -> cells taken
        self.surface = {}                            # cell -> (height, kind)
        self.fronts = {}                             # layer -> slope front cells (open above)
        self.pending = []                            # slopes waiting to be merged

    # ------------------------------------------------------------------ helpers
    def col(self, c, k):
        if self.colour_fn:
            v = self.colour_fn(c, k)
            if v is not None:
                return v
        if self.accent and self.patch(c[0] + 7 * k, c[1] - 3 * k) < self.accent_amt:
            return self.accent
        return self.colour

    def Y(self, k):
        return self.y0 + 3 * k

    def outward(self, c, k):
        return [d for d in DIRS if nbr(c, d) not in self.L[k] and not self.solid(nbr(c, d), self.Y(k) + 2)]

    def free(self, c, k):
        return c in self.L[k] and c not in self.used[k]

    # ------------------------------------------------------------------ build
    def build(self):
        if not self.n:
            return self.surface
        self._undercuts()
        self._slopes()
        self._place_pending()
        self._walls()
        self.b.step()
        self._tops()
        self.b.step()
        return self.surface

    def _undercuts(self):
        """Grow layer 1 outward by a stud in places; those cells become inverted slopes."""
        if self.n < 2 or not self.undercut:
            return
        L0, L1 = self.L[0], self.L[1]
        for c in sorted(ring(L1, 1) & ring(L0, 1)):
            for d in DIRS:
                o = nbr(c, d)
                if o in L0 or self.rng.random() > self.undercut / 2:
                    continue
                if o in self.forbid or (self.terrace_fn and self.terrace_fn(c)):
                    continue
                if all(o not in self.L[k] for k in range(self.n)) and self._place_inv(o, d, 1):
                    break

    def _place_inv(self, o, d, k):
        back = nbr(o, OPP[d])
        if back not in self.L[k] or back in self.used[k] or back not in self.L[k - 1]:
            return False
        self.L[k].add(o)
        self.b.put(INV1, self.col(o, k), min(o[0], back[0]), self.Y(k), min(o[1], back[1]), spin=d)
        self.used[k] |= {o, back}
        return True

    def _slopes(self):
        """Top-down: every face cell whose layer above steps back gets a slope."""
        rng = self.rng
        for k in range(self.n - 1, -1, -1):
            Lk, Lu = self.L[k], self.L[k + 1]
            cand = [c for c in sorted(Lk) if c not in Lu and c not in self.used[k] and self.outward(c, k)
                    and c not in self.stairs and not (self.terrace_fn and self.terrace_fn(c))]
            for c in cand:
                if c in self.used[k]:
                    continue
                dirs = self.outward(c, k)
                rng.shuffle(dirs)
                dirs.sort(key=lambda d: -self._openness(c, d, k))
                for d in dirs:
                    back = nbr(c, OPP[d])
                    if not self.free(back, k) or back in self.stairs:
                        continue
                    # step-back of 2+ studs: a long 33 degree slope (3 deep)
                    back2 = nbr(back, OPP[d])
                    if back not in Lu and self.free(back2, k) and \
                            rng.random() < (self.gentle_fn(c) if self.gentle_fn else self.gentle):
                        self._put_33(c, back, back2, d, k)
                        break
                    # set-back slope if the layer above sits on the back cell,
                    # or (sometimes) on the top edge to round the rim
                    if back not in Lu and rng.random() > self.rim_round:
                        continue
                    span = self._span(c, back, k, d)
                    mate = None
                    self._put_slope(c, back, d, k, span, mate)
                    break

    def _openness(self, c, d, k):
        """How open the outside is in direction d (prefer facing straight down the hill)."""
        o = nbr(c, d)
        a, b_ = side_dirs(d)
        cells = [o, nbr(o, a), nbr(o, b_), nbr(o, d)]
        return sum(1 for q in cells if q not in self.L[k])

    def _span(self, c, back, k, d):
        """How many layers the slope may cover: the face below must be straight."""
        best, s = 1, 1
        while s < 3 and k - s >= 0:
            kk = k - s
            if not (self.free(c, kk) and self.free(back, kk)) or not self.outward(c, kk):
                break
            if nbr(c, d) in self.L[kk]:      # face below isn't in line
                break
            s += 1
            best = s
        w = {1: 1.0, 2: self.steep[1], 3: self.steep[0]}
        opts = [(n, w[n]) for n in range(1, best + 1)]
        return pick(self.rng, opts)

    def _put_33(self, c, back, back2, d, k):
        self._record("33", 1, d, k, k, [[c, back, back2]], self.col(c, k))

    def _mate(self, c, d, k, span):
        for sd in side_dirs(d):
            m = nbr(c, sd)
            mb = nbr(m, OPP[d])
            if all(self.free(m, kk) and self.free(mb, kk) for kk in range(k - span + 1, k + 1)) and \
                    nbr(m, d) not in self.L[k] and m not in self.L[k + 1] and \
                    (mb in self.L[k + 1]) == (nbr(c, OPP[d]) in self.L[k + 1]) and \
                    all(nbr(m, d) not in self.L[kk] for kk in range(k - span + 1, k + 1)):
                return m, mb
        return None

    def _put_slope(self, c, back, d, k, span, mate):
        k0 = k - span + 1
        rows = [[c, back]] + ([list(mate)] if mate else [])
        self._record("45", span, d, k0, k, rows, self.col(c, k))
        # the slope's back cell has a stud on top: a ledge if nothing sits on it
        for q in ([back] + ([mate[1]] if mate else [])):
            if q not in self.L[k + 1]:
                self.surface[q] = (self.Y(k + 1), "ledge")

    def _record(self, fam, span, d, k0, k, rows, colour):
        for kk in range(k0, k + 1):
            for row in rows:
                self.used[kk] |= set(row)
                self.fronts.setdefault(kk, set()).update(row[:-1])
        for row in rows:
            self.pending.append({"fam": fam, "span": span, "d": d, "k0": k0, "row": row, "colour": colour})

    def _place_pending(self):
        """Merge side-by-side 1-wide slopes of the same kind into wider parts."""
        groups = collections.defaultdict(list)
        for r in self.pending:
            groups[(r["fam"], r["span"], r["d"], r["k0"], r["colour"])].append(r)
        for (fam, span, d, k0, colr), rows in groups.items():
            widths = WIDTHS[(fam, span)]
            along = 0 if d in "NS" else 1          # axis running along the face
            bykey = {}
            for r in rows:
                f = r["row"][0]
                bykey[(f[1 - along], f[along])] = r
            done = set()
            for key in sorted(bykey):
                if key in done:
                    continue
                run = [bykey[key]]
                line, pos = key
                while (line, pos + len(run)) in bykey and (line, pos + len(run)) not in done:
                    run.append(bykey[(line, pos + len(run))])
                i = 0
                while i < len(run):
                    left = len(run) - i
                    opts = [w for w in sorted(widths, reverse=True) if w <= left]
                    w = opts[0] if self.rng.random() < self.wide + 0.3 else opts[-1]
                    if self.rng.random() < 0.25 and len(opts) > 1:
                        w = opts[1]
                    chunk = run[i:i + w]
                    cells = [q for r in chunk for q in r["row"]]
                    x, z = min(q[0] for q in cells), min(q[1] for q in cells)
                    self.b.put(widths[w], colr, x, self.Y(k0), z, spin=d)
                    for r in chunk:
                        f = r["row"][0]
                        done.add((f[1 - along], f[along]))
                    i += w

    def _walls(self):
        """Skin bricks, plus whatever is needed to carry everything built above
        (computed top-down), plus columns under wide tops. The rest stays hollow."""
        need = {}
        above = set()
        for k in range(self.n - 1, -1, -1):
            Lk = self.L[k]
            n_k = (ring(Lk, 2) | (above & Lk)) - self.used[k]
            deep = Lk - ring(Lk, 2) - self.used[k]
            for (x, z) in sorted(deep):
                fp = {(x, z), (x + 1, z), (x, z + 1), (x + 1, z + 1)}
                if x % 4 == 3 and z % 4 == 3 and fp <= deep:
                    n_k |= fp
            need[k] = n_k
            above = n_k | self.used[k]
        for k in range(self.n):
            Lk, Lu = self.L[k], self.L[k + 1]
            fronts = self.fronts.get(k, set())
            vis = {c for c in need[k] if self.outward(c, k) or c not in Lu or
                   any(nbr(c, d) in fronts for d in DIRS)}
            hid = need[k] - vis
            for cells, colour_of in ((vis, lambda c: self.col(c, k)), (hid, lambda c: self.hidden)):
                groups = collections.defaultdict(set)
                for c in cells:
                    groups[colour_of(c)].add(c)
                for colr, g in groups.items():
                    for (x, z, w, d) in pack(g, BRICKS, rotate=k % 2 == 1):
                        put_rect(self.b, BRICKS, colr, x, z, w, d, self.Y(k))
            self.used[k] |= need[k]
            r2 = ring(Lk, 2)
            for c in need[k]:
                if c not in Lu:
                    self.surface[c] = (self.Y(k + 1), "ledge" if c in r2 else "inner")

    def _tops(self):
        """Ledges get moss/pebbles/cheese; hollow tops get cap plates (grass or rock)."""
        rng, b = self.rng, self.b
        # hollow exposed cells: inside a layer, nothing above, never filled
        for k in range(self.n):
            hollow = {c for c in self.L[k] - self.L[k + 1] if c not in self.used[k]}
            if not hollow:
                continue
            top = self.Y(k + 1)
            # cap = hollow cells plus a ragged margin over the surrounding ledge bricks
            margin = {c for c, (h, kind) in self.surface.items() if h == top and kind == "inner"}
            cap = hollow | {c for c in margin if rng.random() < 0.85}
            gn = value_noise(rng.randrange(10 ** 6), 4.0)
            special = {}
            if self.cap_fn:
                for c in cap:
                    v = self.cap_fn(c, k)
                    if v is not None:
                        special.setdefault(v, set()).add(c)
            plain = cap - set().union(*special.values()) if special else cap
            grass = {c for c in plain if gn(*c) < self.cap_grass}
            snowy = self.snow_from is not None and k >= self.snow_from
            groups = [(grass, ((self.snow if snowy else GREEN, 1),), "grass"),
                      (plain - grass, ((self.snow if snowy else self.colour, 1),), "cap")]
            groups += [(cells, ((colr, 1),), "special") for colr, cells in special.items()]
            for cells, pal, kind in groups:
                for (x, z, w, d) in pack(cells, PLATES):
                    fp = {(x + i, z + j) for i in range(w) for j in range(d)}
                    if not fp & set(self.used[k]):
                        self._prop(fp, k)
                    put_rect(b, PLATES, pick(rng, pal), x, z, w, d, top)
                    for c in fp:
                        self.surface[c] = (top + 1, kind)
        # grass treads on terraces (ledge cells of terrace regions), with an overhanging lip
        if self.terrace_fn:
            for k in range(self.n):
                top = self.Y(k + 1)
                cells = {c for c, (h, kind) in self.surface.items()
                         if h == top and kind in ("ledge", "inner") and self.terrace_fn(c)}
                if not cells:
                    continue
                lip = set()
                for c in cells:
                    for d in DIRS:
                        o = nbr(c, d)
                        if o not in self.L[k] and o not in self.forbid and rng.random() < self.lip / 2 \
                                and all(o not in self.L[j] for j in range(k + 1)):
                            lip.add(o)
                lip -= {q for q in lip if not any(nbr(q, d) in cells for d in DIRS)}
                for (x, z, w, d) in pack(cells | lip, PLATES, maxsize=12):
                    fp = {(x + i, z + j) for i in range(w) for j in range(d)}
                    if not fp & cells:
                        continue
                    put_rect(b, PLATES, pick(rng, self.grass), x, z, w, d, top)
                    for q in fp:
                        self.surface[q] = (top + 1, "grass")
        # stair treads
        if self.tread is not None:
            for k in range(self.n):
                cells = {c for c in self.stairs if c in self.L[k] and c not in self.L[k + 1]
                         and c in self.used[k]}
                for (x, z, w, d) in pack(cells, PLATES, maxsize=4):
                    put_rect(b, PLATES, self.tread, x, z, w, d, self.Y(k + 1))
                    for i in range(w):
                        for j in range(d):
                            self.surface[(x + i, z + j)] = (self.Y(k + 1) + 1, "tread")
        # ledge dressing
        for c, (h, kind) in sorted(self.surface.items()):
            if kind not in ("ledge", "inner") or c in self.keep_clear:
                continue
            k = (h - self.y0) // 3 - 1
            r = rng.random()
            outs = []
            if 0 <= k < self.n:   # downhill: toward the face (outside, or a slope front)
                fr = self.fronts.get(k, set())
                outs = [d for d in DIRS if nbr(c, d) not in self.L[k + 1] and
                        (nbr(c, d) not in self.L[k] or nbr(c, d) in fr)]
            moss = self.moss_fn(c) if self.moss_fn else self.moss
            r = r if moss == self.moss else r * (self.moss / max(moss, 1e-6)) if r < self.moss else r
            snowy = self.snow_from is not None and k >= self.snow_from
            if snowy:
                moss = max(moss, 0.45)
            if r < moss:
                b.put("3024", self.snow if snowy else pick(rng, self.moss_colours), c[0], h, c[1])
                self.surface[c] = (h + 1, "moss")
            elif r < self.moss + self.ledge_cheese:
                if not outs:
                    continue                      # inner ledge: leave the studs
                b.put("54200", self.snow if (self.snow_from is not None and k >= self.snow_from
                                             and rng.random() < 0.6) else self.col(c, k),
                      c[0], h, c[1], spin=rng.choice(outs))
                self.surface[c] = (None, "cheese")
            elif self.moss + self.ledge_cheese <= r < self.moss + self.ledge_cheese + self.pebble:
                b.put("6141", LBG if self.colour != LBG else DBG, c[0], h, c[1])
                self.surface[c] = (h + 1, "pebble")

    def _prop(self, fp, k):
        """Hidden 1x1 stack from the nearest support up under one cell of a cap plate."""
        c = sorted(fp)[len(fp) // 2]
        kk = k
        while kk >= 0 and c not in self.used[kk]:
            kk -= 1
        for j in range(kk + 1, k + 1):
            self.b.put("3005", self.hidden, c[0], self.Y(j), c[1], note=" prop hidden")
            self.used[j].add(c)


# ---------------------------------------------------------------------- shapes
def blocky(noise, q=2):
    """Noise sampled on q x q blocks, so outlines step back in chunks, not single studs."""
    return lambda x, z: noise(x // q * q + 0.5, z // q * q + 0.5)


def mound(cells, cx, cz, rx, rz, layers, seed, rough=1.2, q=2, power=1.0, rot=0.0):
    """Height map (layers) of a rounded rock mound with blocky, ragged contours."""
    import math
    n1 = blocky(value_noise(seed, 3.0), q)
    n2 = value_noise(seed + 1, 7.0)
    ca, sa = math.cos(rot), math.sin(rot)
    H = {}
    for (x, z) in cells:
        u, v = x + 0.5 - cx, z + 0.5 - cz
        u, v = u * ca + v * sa, -u * sa + v * ca
        r = math.hypot(u / rx, v / rz)
        h = layers * max(0.0, 1 - r) ** power * (0.8 + 0.4 * n2(x, z)) + rough * (n1(x, z) - 0.5)
        h = int(h)
        if h > 0:
            H[(x, z)] = min(h, layers)
    return H


def dress(b, rng, surface, H, rim=0.5, speck=0.10, board=None, foot=0.45, foot_depth=2, ledge=0.08, ground=0):
    """Plants and texture: dense on the top rim, specks on grass tops, a band at the foot."""
    from brickscape.core.kit import tuft
    rimk = [("leaf", 4), ("fern", 2.5), ("big", 2), ("tabs", 1.5), ("flower", 0.8), ("grass", 1)]
    for c, (h, kind) in sorted(surface.items()):
        if h is None:
            continue
        edge = any(H.get(nbr(c, d), 0) < H.get(c, 0) for d in DIRS)
        if kind == "grass":
            if edge and rng.random() < rim:
                tuft(b, rng, c[0], c[1], h, pick(rng, rimk))
            elif rng.random() < speck:
                tuft(b, rng, c[0], c[1], h, "speck")
            elif rng.random() < 0.03:
                tuft(b, rng, c[0], c[1], h)
        elif kind in ("ledge", "inner", "cap") and rng.random() < ledge:
            tuft(b, rng, c[0], c[1], h, pick(rng, [("leaf", 3), ("tabs", 1), ("fern", 1)]))
    # foot band
    near = set(H)
    band = set()
    for _ in range(foot_depth):
        near = {nbr(c, d) for c in near for d in DIRS} | near
    band = near - set(H)
    if board is not None:
        band &= board
    footk = [("leaf", 4), ("big", 2.5), ("fern", 2), ("tabs", 1.5), ("speck", 2), ("flower", 0.8), ("grass", 1)]
    for c in sorted(band):
        adj = any(nbr(c, d) in H for d in DIRS)
        if rng.random() < (foot if adj else foot * 0.45):
            tuft(b, rng, c[0], c[1], ground(c) if callable(ground) else ground, pick(rng, footk))


def layered(cells, f, n_layers, rate=1.0, amp=1.5, seed=0, q=2, min_w=2):
    """Height map where each layer's outline is jittered independently.

    f(x, z): 'depth inside the rock' in studs (>0 inside the footprint).
    Layer k keeps cells with f - k * rate + jitter_k > 0, nested in layer k-1.
    The jitter is blocky (q-stud chunks), so faces stagger in blocks like the references."""
    from brickscape.core.kit import clean
    layers = []
    prev = set(cells)
    for k in range(n_layers):
        nk = blocky(value_noise(seed * 31 + k, 3.0), q)
        cur = {c for c in prev if f(*c) - k * rate + amp * (nk(*c) - 0.5) > 0}
        # drop slivers thinner than min_w
        T = clean({c: 1 for c in cur}, min_w)
        cur = set(T)
        if not cur:
            break
        layers.append(cur)
        prev = cur
    H = {}
    for k, Lk in enumerate(layers):
        for c in Lk:
            H[c] = k + 1
    return H
