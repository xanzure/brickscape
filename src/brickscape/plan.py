"""Build plans: the JSON an AI client sends instead of raw coordinates.

A plan names a board and a list of operations. The toolkit compiles each operation into real
parts on real studs (the client never does geometry maths), keeps a height map so later
operations land on top of earlier ones, then repairs and validates the result.

    {
      "name": "forest clearing",
      "board": {"width": 32, "depth": 32, "colour": "green"},
      "seed": 1,
      "ops": [
        {"op": "hill", "area": {"ellipse": [16, 20, 10, 7]}, "height": 8, "style": "terraces"},
        {"op": "path", "points": [[0, 4], [16, 10], [31, 6]], "width": 3, "style": "cobble"},
        {"op": "tree", "kind": "oak", "size": "medium", "at": [6, 26]},
        {"op": "scatter", "area": {"rect": [0, 0, 32, 32]}, "kinds": ["tuft", "flower"], "density": 0.1}
      ]
    }

Coordinates are studs: x left to right, z front to back (z = 0 is the front edge, nearest
the viewer), heights in plates (3 plates = 1 brick). See OPS for every operation.
"""
import json, math, os, random, re
from brickscape.config import LDRAW
from brickscape.core.brick import Build, info
from brickscape.core import kit
from brickscape.core.kit import BRICKS, PLATES, pack, put_rect, value_noise, nbr, DIRS
from brickscape.terrain import greenery as G
from brickscape.terrain.water import TILES

# --------------------------------------------------------------------------- colours
_COLOURS = None


def colours():
    """LDraw colour name (lower case, spaces) -> code, from the library's LDConfig.ldr."""
    global _COLOURS
    if _COLOURS is None:
        _COLOURS = {}
        for line in open(os.path.join(LDRAW, "LDConfig.ldr"), errors="ignore"):
            m = re.match(r"0 !COLOUR (\S+)\s+CODE\s+(\d+)", line)
            if m:
                _COLOURS[m.group(1).lower().replace("_", " ")] = int(m.group(2))
        _COLOURS.update({"dark bluish grey": 72, "light bluish grey": 71, "dark grey": 72,
                         "light grey": 71, "grey": 71, "gray": 71, "dark gray": 72, "light gray": 71,
                         "dark bluish gray": 72, "light bluish gray": 71})
    return _COLOURS


def colour(c, default=None):
    if c is None:
        return default
    if isinstance(c, int) or (isinstance(c, str) and c.isdigit()):
        return int(c)
    k = c.lower().replace("_", " ").replace("gray", "grey").strip()
    t = colours()
    if k in t:
        return t[k]
    if k.replace("grey", "gray") in t:
        return t[k.replace("grey", "gray")]
    raise PlanError(f"unknown colour {c!r} (use an LDraw colour name like 'dark bluish grey' or a code)")


class PlanError(ValueError):
    pass


# --------------------------------------------------------------------------- areas
def area_cells(a, board, seed=0):
    """Area spec -> set of cells.
    {"rect": [x0, z0, x1, z1]} (x1/z1 exclusive), {"ellipse": [cx, cz, rx, rz]},
    {"polygon": [[x, z], ...]}, {"cells": [[x, z], ...]}; optional "rough": 0..1 noisy edge."""
    if a is None:
        return set(board)
    rough = float(a.get("rough", 0.0))
    n = value_noise(seed + 77, 4.0)
    out = set()
    if "rect" in a:
        x0, z0, x1, z1 = a["rect"]
        out = {(x, z) for x in range(int(x0), int(x1)) for z in range(int(z0), int(z1))}
    elif "ellipse" in a:
        cx, cz, rx, rz = a["ellipse"]
        for (x, z) in board:
            r = math.hypot((x + .5 - cx) / max(rx, .5), (z + .5 - cz) / max(rz, .5))
            if r < 1 + rough * 0.5 * (n(x, z) - 0.5):
                out.add((x, z))
    elif "polygon" in a:
        P = a["polygon"]
        for (x, z) in board:
            px, pz, inside = x + .5, z + .5, False
            for (ax, az), (bx, bz) in zip(P, P[1:] + P[:1]):
                if (az > pz) != (bz > pz) and px < ax + (pz - az) * (bx - ax) / (bz - az):
                    inside = not inside
            if inside:
                out.add((x, z))
    elif "cells" in a:
        out = {tuple(c) for c in a["cells"]}
    else:
        raise PlanError(f"area needs rect, ellipse, polygon or cells: {a}")
    return out & board


# --------------------------------------------------------------------------- the compiler
class Compiler:
    def __init__(self, plan):
        self.plan = plan
        bd = plan.get("board", {})
        self.W, self.D = int(bd.get("width", 32)), int(bd.get("depth", 32))
        if not (4 <= self.W <= 192 and 4 <= self.D <= 192):
            raise PlanError("board width/depth must be 4..192 studs")
        self.b = Build(plan.get("name", "brickscape build"), self.W, self.D)
        self.rng = random.Random(plan.get("seed", 1))
        self.seed = int(plan.get("seed", 1))
        bc = colour(bd.get("colour", "green"))
        if self.W % 16 == 0 and self.D % 16 == 0:    # baseplates
            step = 32 if self.W % 32 == 0 and self.D % 32 == 0 else 16
            for x in range(0, self.W, step):
                for z in range(0, self.D, step):
                    self.b.base(x, z, color=bc, part="3811" if step == 32 else "3867")
        else:                                        # any other size: a floor of plates
            cells = {(x, z) for x in range(self.W) for z in range(self.D)}
            for (x, z, w, d) in pack(cells, PLATES):
                put_rect(self.b, PLATES, bc, x, z, w, d, -1)
                self.b.roots.add(len(self.b.pieces) - 1)
        self.b.step()
        self.board = {(x, z) for x in range(self.W) for z in range(self.D)}
        self.surface = {}          # cell -> top height in plates (missing = 0)
        self.used = set()          # cells taken by terrain / water / paths / buildings
        self.named = {}            # op id -> list of piece indices
        self.log = []

    # heights
    def h(self, c):
        return self.surface.get(c, 0)

    def refresh_surface(self, start=0):
        """Raise the height map under every structural piece placed since `start`."""
        for p in self.b.pieces[start:]:
            if p is None or G.decorative(p.part):
                continue
            x0 = math.floor((p.lo[0] + self.W * 10) / 20 + 1e-6)
            x1 = math.ceil((p.hi[0] + self.W * 10) / 20 - 1e-6)
            z0 = math.floor((p.lo[2] + self.D * 10) / 20 + 1e-6)
            z1 = math.ceil((p.hi[2] + self.D * 10) / 20 - 1e-6)
            top = round(-p.lo[1] / 8)
            if top <= 0:
                continue
            for x in range(x0, x1):
                for z in range(z0, z1):
                    if (x, z) in self.board and top > self.surface.get((x, z), 0):
                        self.surface[(x, z)] = top

    def footprint(self, start):
        """Board cells under the structural parts placed since `start`."""
        out = set()
        for p in self.b.pieces[start:]:
            if p is None or G.decorative(p.part) or abs(p.M[4] - 1) > 1e-3:
                continue
            x0 = math.floor((p.lo[0] + self.W * 10) / 20 + 1e-6)
            x1 = math.ceil((p.hi[0] + self.W * 10) / 20 - 1e-6)
            z0 = math.floor((p.lo[2] + self.D * 10) / 20 + 1e-6)
            z1 = math.ceil((p.hi[2] + self.D * 10) / 20 - 1e-6)
            out |= {(x, z) for x in range(x0, x1) for z in range(z0, z1)} & self.board
        return out

    def run(self):
        for k, op in enumerate(self.plan.get("ops", [])):
            name = op.get("op")
            fn = getattr(self, "op_" + str(name).replace(".", "_"), None)
            if fn is None:
                raise PlanError(f"op {k}: unknown op {name!r}; ops: {', '.join(OPS)}")
            start = len(self.b.pieces)
            try:
                fn(op)
            except PlanError as e:
                raise PlanError(f"op {k} ({name}): {e}") from None
            except (KeyError, TypeError, ValueError, IndexError) as e:
                raise PlanError(f"op {k} ({name}): bad parameters ({type(e).__name__}: {e})") from None
            self.refresh_surface(start)
            self.used |= self.footprint(start)
            if op.get("id"):
                self.named[op["id"]] = list(range(start, len(self.b.pieces)))
            self.b.step()
            self.log.append(f"op {k} {name}: {len(self.b.pieces) - start} parts")
        return self.b

    def cells(self, op, key="area"):
        return area_cells(op.get(key), self.board, self.seed + len(self.log))

    def rng_for(self, op):
        return random.Random(op.get("seed", self.seed * 1000 + len(self.log)))

    # ------------------------------------------------------------------ primitives
    def op_brick(self, op):
        """One part on the stud grid: part, colour, at [x, z] (min corner), y (plates, default:
        the surface there), spin N/E/S/W."""
        x, z = op["at"]
        y = op.get("y", max(self.h((int(x), int(z))), 0))
        part = str(op["part"]).replace(".dat", "")
        try:
            info(part)
        except ValueError:
            raise PlanError(f"unknown LDraw part {part!r} (search_parts finds ids)")
        self.b.put(part, colour(op.get("colour"), 71), x, y, z, spin=op.get("spin", "N"))

    def op_block(self, op):
        """A raised area built like real LEGO: a hidden frame of bricks round the edge and
        every few studs inside, plates on top. height in plates; top: 'tiles' (smooth),
        'studs', or 'grass' (green plates). colour: visible side colour; top_colour."""
        cells = self.cells(op) - self.used
        if not cells:
            return
        H = int(op.get("height", 3))
        side = colour(op.get("colour"), 71)
        topc = colour(op.get("top_colour"), side if op.get("top") != "grass" else 2)
        base = max(self.h(c) for c in cells)
        if H < 1:
            raise PlanError("height must be at least 1 plate")
        self._solid(cells, base, H, side, topc, op.get("top", "tiles"), hollow=op.get("hollow", True))
        self.used |= cells

    def _solid(self, cells, y0, H, side, topc, top="tiles", hollow=True):
        """H plates from y0: hollow brick frame (edge + a wall every 4 studs), then full plate
        decks with crossed seams, then the top layer."""
        b = self.b
        edge = {c for c in cells if any(nbr(c, d) not in cells for d in DIRS)}
        frame = edge | {c for c in cells - edge if c[0] % 4 == 0 or c[1] % 4 == 0}
        body = H - 1                                   # plates below the top layer
        bricks = max(0, (body - 1) // 3) if hollow else body // 3
        y = y0
        for layer in range(bricks):
            for (x, z, w, d) in pack(frame if hollow else cells, BRICKS, rotate=layer % 2 == 1):
                put_rect(b, BRICKS, side, x, z, w, d, y)
            y += 3
        layer = bricks
        while y < y0 + body:
            for (x, z, w, d) in pack(cells, PLATES, rotate=layer % 2 == 1):
                put_rect(b, PLATES, side, x, z, w, d, y)
            y += 1
            layer += 1
        table = TILES if top == "tiles" else PLATES
        for (x, z, w, d) in pack(cells, table, rotate=layer % 2 == 1):
            put_rect(b, table, topc, x, z, w, d, y)

    def op_ldraw(self, op):
        """Exact parts: lines of LDraw type-1 text ('1 <colour> x y z a b c d e f g h i part.dat'),
        in LDU with the board centred on the origin and -y up (baseplate top at y = 0)."""
        for line in op["lines"]:
            t = line.split()
            if len(t) < 15 or t[0] != "1":
                raise PlanError(f"not an LDraw part line: {line[:60]!r}")
            self.b.raw(t[14].lower().replace(".dat", ""), int(t[1]), tuple(map(float, t[2:14])))

    # ------------------------------------------------------------------ terrain
    def op_hill(self, op):
        """Raised ground over an area. height: plates at the top (rounded to 4-plate terraces
        for 'terraces'); style: 'terraces' (grass treads, earth/stone risers) or 'rock' (a
        rock outcrop with leaning cliff faces and a grass top); falloff: studs from the edge
        to full height (default about a third of the area's radius)."""
        cells = self.cells(op) - self.used
        if not cells:
            return
        top = int(op.get("height", 8))
        dist = _edge_distance(cells)
        fall = float(op.get("falloff", max(2.0, max(dist.values()) * 0.6)))
        rng = self.rng_for(op)
        n = value_noise(self.seed + len(self.log) * 13, 3.0)
        if op.get("style", "terraces") == "rock":
            from brickscape.terrain.rock3 import Rock3
            H = {c: max(3, min(top, round(top * min(1.0, (d + 1 + 2 * (n(*c) - .5)) / fall))))
                 for c, d in dist.items()}
            r = Rock3(self.b, H, seed=rng.randrange(10 ** 6), colour=colour(op.get("colour"), 72),
                      accent=colour(op.get("accent"), 71), board=self.board)
            r.build(talus=0.3)
        else:
            from brickscape.terrain.ground import Terraces
            courses = max(1, round(top / 4))
            H = {}
            for c, d in dist.items():
                k = math.ceil(courses * min(1.0, (d + 1 + 1.5 * (n(*c) - .5)) / fall))
                if k > 0:
                    H[c] = min(courses, k)
            H = kit.clean(H, 2)
            riser = colour(op.get("colour"), 28)
            Terraces(self.b, H, seed=rng.randrange(10 ** 6), riser_fn=lambda c, k: riser,
                     board=self.board).build()
        self.used |= cells

    def op_boulder(self, op):
        """Boulders: at [[x, z, size], ...] with size 1, 2, 4 or 6 studs; colours = rock
        palette (default dark + light bluish grey)."""
        rng = self.rng_for(op)
        pal = tuple((colour(c), 1) for c in op.get("colours", ["dark bluish grey", "dark bluish grey", "light bluish grey"]))
        for x, z, s in op["at"]:
            fp = {(x + i, z + j) for i in range(s) for j in range(s)}
            if fp & self.used:
                continue
            kit.boulder(self.b, rng, x, z, size=int(s), pal=pal, y=self.h((x, z)))
            self.used |= fp

    def op_path(self, op):
        """A path set into the ground along points [[x, z], ...]; width studs (or [min, max]);
        style 'cobble' or 'dirt'. Built at ground level beside raised verges."""
        from brickscape.terrain.ground import sunken_path
        w = op.get("width", 3)
        wmin, wmax = (w, w + 1) if isinstance(w, (int, float)) else w
        cells = kit.path_cells([tuple(p) for p in op["points"]], wmin, wmax,
                               seed=self.seed + 5, board=self.board) - self.used
        if not cells:
            return
        occ, surf = sunken_path(self.b, self.rng_for(op), cells, style=op.get("style", "cobble"),
                                board=self.board, avoid=self.used)
        self.used |= set(occ) | cells

    def op_water(self, op):
        """Water: a stream along points [[x, z], ...] with width, or a pond over an area. Smooth
        blue tiles with ripples, banks raised 1-2 plates with earth and stones."""
        from brickscape.terrain.water import water_surface, banks, river_cells
        if "points" in op:
            w = op.get("width", 4)
            wmin, wmax = (w, w + 2) if isinstance(w, (int, float)) else w
            cells = river_cells([tuple(p) for p in op["points"]], wmin, wmax, seed=self.seed + 9, board=self.board)
        else:
            cells = self.cells(op)
        cells -= self.used
        if not cells:
            return
        rng = self.rng_for(op)
        bank, bsurf, wused = banks(self.b, rng, cells, self.board, avoid=self.used, seed=self.seed + 11)
        water_surface(self.b, rng, cells - set(wused), deep=colour(op.get("colour"), 1), seed=self.seed + 12)
        self.used |= cells | set(bank)

    # ------------------------------------------------------------------ plants
    TREES = {"oak": "oak", "birch": "birch", "pine": "pine", "palm": "palm", "cypress": "cypress"}

    NEAR = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1),
            (2, 0), (-2, 0), (0, 2), (0, -2)]

    def _nearby(self, op, place, need=3):
        """Run place(x, z) at op['at'] or the nearest spot within 2 studs where it fits."""
        x0, z0 = op["at"]
        for dx, dz in self.NEAR:
            n0 = len(self.b.pieces)
            place(x0 + dx, z0 + dz)
            if len(self.b.pieces) - n0 >= need:
                return
            while len(self.b.pieces) > n0:
                self.b.pop()
        self.log.append(f"  (no room for {op.get('kind', op['op'])} near {op['at']})")

    def op_tree(self, op):
        """A tree at [x, z] (moved up to 2 studs if it doesn't fit there): kind oak (size
        small/medium/tall/fat/big), birch, pine, palm, cypress. leaf / bark colours optional."""
        self._nearby(op, lambda x, z: self._tree(op, x, z), need=4)

    def _tree(self, op, x, z):
        kind = op.get("kind", "oak")
        rng = self.rng_for(op)
        y = self.h((x, z))
        lc = op.get("leaf")
        if kind == "oak":
            leaves = tuple(colour(c) for c in lc) if isinstance(lc, list) else (2, 2, 288) if lc is None else (colour(lc),)
            G.oak(self.b, rng, x, z, y, size=op.get("size", "medium"), leaves=leaves,
                  bark=colour(op.get("bark"), 70))
        elif kind == "birch":
            G.birch(self.b, rng, x, z, y, leaf=(colour(lc),) if lc else (14, 25, 191))
        elif kind == "pine":
            G.pine(self.b, rng, x, z, y, colour=colour(lc, 288))
        elif kind == "palm":
            G.palm(self.b, rng, x, z, y, leaf=colour(lc, 2))
        elif kind == "cypress":
            G.cypress(self.b, rng, x, z, y)
        else:
            raise PlanError(f"tree kind must be one of {', '.join(self.TREES)}")

    PLANTS = {
        "tuft": lambda b, r, x, z, y: G.tuft(b, r, x, z, y, kind=r.choice(("grass", "leafy", "clover", "spiky"))),
        "flower": lambda b, r, x, z, y: G.flower(b, r, x, z, y, colour=r.choice((15, 14, 4, 1))),
        "flowers": lambda b, r, x, z, y: G.stem_flowers(b, r, x, z, y),
        "bush": lambda b, r, x, z, y: G.snot_bush(b, r, x, z, y),
        "big_bush": lambda b, r, x, z, y: G.wide_bush(b, r, x, z, y, w=2, d=2),
        "fern": lambda b, r, x, z, y: G.fern_clump(b, r, x, z, y),
        "leafy": lambda b, r, x, z, y: G.big_leaf_plant(b, r, x, z, y),
        "reeds": lambda b, r, x, z, y: G.plume_grass(b, r, x, z, y),
        "bamboo": lambda b, r, x, z, y: G.bamboo(b, r, x, z, y),
        "cactus": lambda b, r, x, z, y: G.cactus(b, r, x, z, y),
        "succulent": lambda b, r, x, z, y: G.crystal_succulent(b, r, x, z, y),
        "stone": lambda b, r, x, z, y: b.put(r.choice(("54200", "6141", "3024")), r.choice((71, 72)), x, y, z,
                                             spin=r.choice("NESW")),
    }

    def op_plant(self, op):
        """One plant at [x, z]: kind from PLANTS (tuft, flower, flowers, bush, big_bush, fern,
        leafy, reeds, bamboo, cactus, succulent, stone)."""
        kind = op.get("kind", "bush")
        if kind not in self.PLANTS:
            raise PlanError(f"plant kind must be one of {', '.join(self.PLANTS)}")
        rng = self.rng_for(op)
        self._nearby(op, lambda x, z: self.PLANTS[kind](self.b, rng, x, z, self.h((x, z))), need=1)

    def op_scatter(self, op):
        """Plants scattered over an area: kinds [..] (PLANTS names, or 'tree:oak' etc.),
        density (share of free cells, default 0.08), keep_clear [area, ...]."""
        cells = sorted(self.cells(op))
        rng = self.rng_for(op)
        kinds = op.get("kinds", ["tuft", "flower", "bush"])
        dens = float(op.get("density", 0.08))
        clear = set()
        for a in op.get("keep_clear", []):
            clear |= area_cells(a, self.board)
        rng.shuffle(cells)
        taken = set()
        for c in cells:
            if c in clear or c in taken or rng.random() > dens:
                continue
            k = rng.choice(kinds)
            if k.startswith("tree:"):
                fp = {(c[0] + i, c[1] + j) for i in range(-2, 3) for j in range(-2, 3)}
                if fp & taken:
                    continue
                self._tree({"kind": k[5:], "size": rng.choice(("small", "medium"))}, c[0], c[1])
                taken |= fp
            else:
                if k not in self.PLANTS:
                    raise PlanError(f"scatter kind {k!r}: use {', '.join(self.PLANTS)} or tree:<kind>")
                self.PLANTS[k](self.b, rng, c[0], c[1], self.h(c))
                taken |= {(c[0] + i, c[1] + j) for i in (-1, 0, 1) for j in (-1, 0, 1)}


OPS = [n[3:] for n in dir(Compiler) if n.startswith("op_")]


def _edge_distance(cells):
    """Studs from each cell to the area's outside (BFS, 4-connected)."""
    dist, frontier = {}, {c for c in cells if any(nbr(c, d) not in cells for d in DIRS)}
    for c in frontier:
        dist[c] = 0
    k = 0
    while frontier:
        k += 1
        frontier = {nbr(c, d) for c in frontier for d in DIRS if nbr(c, d) in cells} - set(dist)
        for c in frontier:
            dist[c] = k
    return dist


def op_reference():
    """Markdown reference of every op (from the docstrings)."""
    out = []
    for n in OPS:
        doc = (getattr(Compiler, "op_" + n).__doc__ or "").strip()
        out.append(f"- `{n}`: " + " ".join(doc.split()))
    return "\n".join(out)


def compile_plan(plan):
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError as e:
            raise PlanError(f"plan is not valid JSON: {e}") from None
    c = Compiler(plan)
    b = c.run()
    return b, c
