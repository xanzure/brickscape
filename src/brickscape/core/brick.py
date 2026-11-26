"""Place LDraw parts on a stud grid and check the result.

Units: x/z in studs (20 LDU), y in plates (8 LDU), y measured UP from the
baseplate surface. LDraw itself has -Y up; conversion happens here.

put(part, colour, x, y, z, spin, up) places the part so that the min corner of
its (stud-less) bounding box lands at (x, y, z). `spin` turns the part about
its own vertical axis first (for slopes: the direction the slope faces
N/E/S/W, N = -z = back), then `up` tilts it so its studs point that way
('up', 'N', 'S', 'E', 'W', 'down').

check() reports overlapping pieces and pieces not connected (through studs,
in any direction) to a baseplate.
"""
import os, re, functools, itertools, collections

from brickscape.config import LDRAW as LIB
SEARCH = ["parts", "p", "parts/s", "p/48", "p/8", "parts/textures"]
TOP_STUD = re.compile(r"^(stud|stud2|stud2a|stud6|stud6a|stud10|stud13|stud15|stud17|stud17a|stud26|stud19)\.dat$"
                      r"|^stud-logo\d*\.dat$|^stu2-logo\d*\.dat$")

Mat = tuple  # (x,y,z, a,b,c,d,e,f,g,h,i)
IDENT = (0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1)


def _find(name):
    name = name.replace("\\", "/").lower()
    for d in SEARCH:
        p = os.path.join(LIB, d, name)
        if os.path.exists(p):
            return p
    return None


def _mul(A, B):
    x, y, z, a = A[0], A[1], A[2], A[3:]
    bx, by, bz, b = B[0], B[1], B[2], B[3:]
    return (a[0]*bx + a[1]*by + a[2]*bz + x,
            a[3]*bx + a[4]*by + a[5]*bz + y,
            a[6]*bx + a[7]*by + a[8]*bz + z,
            *[sum(a[r*3+k]*b[k*3+c] for k in range(3)) for r in range(3) for c in range(3)])


def _apply(M, p):
    a = M[3:]
    return (a[0]*p[0] + a[1]*p[1] + a[2]*p[2] + M[0],
            a[3]*p[0] + a[4]*p[1] + a[5]*p[2] + M[1],
            a[6]*p[0] + a[7]*p[1] + a[8]*p[2] + M[2])


def _dir(M, v):
    a = M[3:]
    return (a[0]*v[0] + a[1]*v[1] + a[2]*v[2],
            a[3]*v[0] + a[4]*v[1] + a[5]*v[2],
            a[6]*v[0] + a[7]*v[1] + a[8]*v[2])


@functools.lru_cache(None)
def _geom(name):
    """(points, studs) of a file in its own frame. studs = ((pos), (dir)) tuples."""
    path = _find(name)
    pts, studs = [], []
    if not path:
        return (), ()
    for line in open(path, errors="ignore"):
        t = line.split()
        if not t:
            continue
        if t[0] == "1" and len(t) >= 15:
            sub = t[14].lower().replace("\\", "/")
            M = tuple(map(float, t[2:14]))
            base = os.path.basename(sub)
            if TOP_STUD.match(base):
                studs.append((_apply(M, (0, 0, 0)), _dir(M, (0, -1, 0))))
                continue
            sp, ss = _geom(sub)
            pts += [_apply(M, p) for p in sp]
            studs += [(_apply(M, p), _dir(M, d)) for p, d in ss]
        elif t[0] in ("3", "4"):
            v = list(map(float, t[2:2 + 3 * int(t[0])]))
            pts += [tuple(v[i:i + 3]) for i in range(0, len(v), 3)]
    return tuple(pts), tuple(studs)


@functools.lru_cache(None)
def info(part):
    pts, studs = _geom(part + ".dat")
    if not pts:
        raise ValueError(f"part {part} not found / empty")
    lo = tuple(min(p[i] for p in pts) for i in range(3))
    hi = tuple(max(p[i] for p in pts) for i in range(3))
    bot = [p for p in pts if abs(p[1] - hi[1]) < 0.01]
    blo = (min(p[0] for p in bot), min(p[2] for p in bot))
    bhi = (max(p[0] for p in bot), max(p[2] for p in bot))
    desc = open(_find(part + ".dat"), errors="ignore").readline()[2:].strip()
    for _ in range(3):   # "~Moved to 3040b" -> description of the target part
        if desc.startswith("~Moved to "):
            tgt = desc[len("~Moved to "):].strip()
            f = _find(tgt + ".dat")
            if not f:
                break
            desc = open(f, errors="ignore").readline()[2:].strip()
        else:
            break
    return {"lo": lo, "hi": hi, "studs": studs, "bottom": (hi[1], blo, bhi), "desc": desc}


def _rot(a, b, c, d, e, f, g, h, i):
    return (0, 0, 0, a, b, c, d, e, f, g, h, i)


SPIN = {"N": _rot(1, 0, 0, 0, 1, 0, 0, 0, 1), "S": _rot(-1, 0, 0, 0, 1, 0, 0, 0, -1),
        "E": _rot(0, 0, -1, 0, 1, 0, 1, 0, 0), "W": _rot(0, 0, 1, 0, 1, 0, -1, 0, 0)}
SPIN.update({0: SPIN["N"], 90: SPIN["E"], 180: SPIN["S"], 270: SPIN["W"]})
UP = {"up": SPIN["N"],
      "N": _rot(1, 0, 0, 0, 0, -1, 0, 1, 0), "S": _rot(1, 0, 0, 0, 0, 1, 0, -1, 0),
      "E": _rot(0, -1, 0, 1, 0, 0, 0, 0, 1), "W": _rot(0, 1, 0, -1, 0, 0, 0, 0, 1),
      "down": _rot(1, 0, 0, 0, -1, 0, 0, 0, -1)}


class Piece:
    __slots__ = ("part", "color", "M", "step", "lo", "hi", "note", "soft", "free", "_boxes", "_snaps")

    def line(self):
        x, y, z = (round(v, 3) for v in self.M[:3])
        m = " ".join(f"{round(v, 6):g}" for v in self.M[3:])
        return f"1 {self.color} {x:g} {y:g} {z:g} {m} {self.part}.dat"


class Build:
    def __init__(self, name, W=32, D=32):
        """W x D studs of board; baseplates are added with base()."""
        self.name, self.W, self.D = name, W, D
        self.pieces, self.step_no, self.roots = [], 0, set()

    # world LDU of stud-grid coordinates (board centred on the origin)
    def X(self, x): return -self.W * 10 + 20 * x
    def Z(self, z): return -self.D * 10 + 20 * z
    def Y(self, y): return -8 * y

    def base(self, x, z, color=2, part="3811"):
        p = self.put(part, color, x, -0.5, z)  # baseplate top at y=0
        self.roots.add(len(self.pieces) - 1)
        return p

    def put(self, part, color, x, y, z, spin="N", up="up", note="", soft=False):
        R = _mul(UP[up], SPIN[spin])
        inf = info(part)
        lo, hi = inf["lo"], inf["hi"]
        corners = [_apply(R, (a, b, c)) for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])]
        mn = [min(c[i] for c in corners) for i in range(3)]
        mx = [max(c[i] for c in corners) for i in range(3)]
        tx = self.X(x) - mn[0]
        tz = self.Z(z) - mn[2]
        ty = self.Y(y) - mx[1]          # bottom (max LDraw y) sits at height y
        M = (tx, ty, tz, *R[3:])
        p = Piece()
        p.part, p.color, p.M, p.step, p.note = part, color, M, self.step_no, note
        p.soft, p.free = soft, False
        p.lo = (mn[0] + tx, mn[1] + ty, mn[2] + tz)
        p.hi = (mx[0] + tx, mx[1] + ty, mx[2] + tz)
        self.pieces.append(p)
        self._index(len(self.pieces) - 1)
        return p

    def attach(self, part, color, x, z, y, spin="N", up="up", note="", soft=True, free=False):
        """Place by the part's origin: origin at stud-grid point (x, z) (use .5 for a
        stud centre), bottom face at height y. For plants and other one-stud parts."""
        from brickscape.terrain.greenery import decorative, FIT
        from brickscape.core.space import fits
        deco = FIT and decorative(part)
        spins = [spin] + [s for s in "NESW" if s != spin] if deco else [spin]
        for sp in spins:
            R = _mul(UP[up], SPIN[sp])
            yb = info(part)["bottom"][0]
            off = _dir(R, (0, yb, 0))
            M = (self.X(x) - off[0], self.Y(y) - off[1], self.Z(z) - off[2], *R[3:])
            p = self.raw(part, color, M, note)
            p.soft, p.free = soft, free
            if not deco or fits(self, len(self.pieces) - 1):
                return p
            self.pop()
        return None     # a plant that fits nowhere here is left out

    def raw(self, part, color, M, note=""):
        p = Piece()
        p.part, p.color, p.M, p.step, p.note = part, color, tuple(M), self.step_no, note
        p.soft, p.free = False, False
        inf = info(part)
        cs = [_apply(p.M, (a, b, c)) for a in (inf["lo"][0], inf["hi"][0])
              for b in (inf["lo"][1], inf["hi"][1]) for c in (inf["lo"][2], inf["hi"][2])]
        p.lo = tuple(min(c[i] for c in cs) for i in range(3))
        p.hi = tuple(max(c[i] for c in cs) for i in range(3))
        self.pieces.append(p)
        self._index(len(self.pieces) - 1)
        return p

    # ------------------------------------------------------------- spatial index
    CELL = 40

    def _index(self, i):
        if not hasattr(self, "_grid"):
            self._grid = {}
        p = self.pieces[i]
        p._boxes = p._snaps = None
        C = self.CELL
        for gx in range(int(p.lo[0] // C), int(p.hi[0] // C) + 1):
            for gy in range(int(p.lo[1] // C), int(p.hi[1] // C) + 1):
                for gz in range(int(p.lo[2] // C), int(p.hi[2] // C) + 1):
                    self._grid.setdefault((gx, gy, gz), []).append(i)

    def near(self, i, pad=1.0):
        """Indices of pieces whose bounding boxes overlap piece i's."""
        p, C, out = self.pieces[i], self.CELL, set()
        for gx in range(int(p.lo[0] // C), int(p.hi[0] // C) + 1):
            for gy in range(int(p.lo[1] // C), int(p.hi[1] // C) + 1):
                for gz in range(int(p.lo[2] // C), int(p.hi[2] // C) + 1):
                    for j in self._grid.get((gx, gy, gz), ()):
                        if j != i and j < len(self.pieces) and self.pieces[j] is not None:
                            q = self.pieces[j]
                            if all(p.lo[k] + pad < q.hi[k] and q.lo[k] + pad < p.hi[k] for k in range(3)):
                                out.add(j)
        return out

    def pop(self):
        """Remove the last placed piece."""
        i = len(self.pieces) - 1
        for ids in self._grid.values():
            if ids and ids[-1] == i:
                ids.pop()
        return self.pieces.pop()

    def step(self):
        self.step_no += 1

    # ------------------------------------------------------------------ checks
    def _studs(self, p):
        return [(_apply(p.M, s), _dir(p.M, d)) for s, d in info(p.part)["studs"]]

    def check(self, verbose=True):
        msgs = []
        P = self.pieces
        # overlaps (bounding boxes shrunk a little; slopes count as full boxes)
        cell = collections.defaultdict(list)
        for i, p in enumerate(P):
            for gx in range(int(p.lo[0] // 80), int(p.hi[0] // 80) + 1):
                for gz in range(int(p.lo[2] // 80), int(p.hi[2] // 80) + 1):
                    cell[(gx, gz)].append(i)
        seen = set()
        for ids in cell.values():
            for i, j in itertools.combinations(ids, 2):
                if (i, j) in seen:
                    continue
                seen.add((i, j))
                a, b = P[i], P[j]
                if a.soft or b.soft:
                    continue
                if all(a.lo[k] + 1.5 < b.hi[k] and b.lo[k] + 1.5 < a.hi[k] for k in range(3)):
                    if i in self.roots or j in self.roots:
                        continue
                    msgs.append(f"OVERLAP {a.part}#{i}{a.note} / {b.part}#{j}{b.note}")
        # connectivity through studs
        bots = []
        for p in P:
            yb, blo, bhi = info(p.part)["bottom"]
            bots.append((yb, blo, bhi))
        adj = collections.defaultdict(set)
        index = collections.defaultdict(list)
        for i, p in enumerate(P):
            for s, d in self._studs(p):
                index[(round(s[0] / 10), round(s[1] / 4), round(s[2] / 10))].append((i, d))
        inv = {}
        for j, q in enumerate(P):
            a = q.M[3:]
            # inverse rotation = transpose
            inv[j] = a
        for j, q in enumerate(P):
            yb, blo, bhi = bots[j]
            up = _dir(q.M, (0, -1, 0))
            # candidate stud positions: the bottom face grid of q
            pts = {(lx, lz) for lx in _grid(blo[0], bhi[0]) for lz in _grid(blo[1], bhi[1])}
            # also under the part's own up-facing studs (tubes sit under studs); fixes parts
            # whose bottom outline is skewed by fingers/clips (hinges, brackets)
            pts |= {(round(sp[0], 3), round(sp[2], 3)) for sp, sd in info(q.part)["studs"]
                    if abs(sd[1] + 1) < 1e-3}
            for (lx, lz) in pts:
                if True:
                    w = _apply(q.M, (lx, yb, lz))
                    for (i, d) in index.get((round(w[0] / 10), round(w[1] / 4), round(w[2] / 10)), []):
                        if i != j and all(abs(d[k] - up[k]) < 1e-3 for k in range(3)):
                            adj[i].add(j)
                            adj[j].add(i)
        reach, todo = set(self.roots), list(self.roots)
        while todo:
            for n in adj[todo.pop()]:
                if n not in reach:
                    reach.add(n)
                    todo.append(n)
        loose = [i for i in range(len(P)) if i not in reach and not P[i].free]
        for i in loose:
            msgs.append(f"NOT CONNECTED {P[i].part}#{i}{P[i].note} at y={-P[i].hi[1]/8:.2f}")
        if verbose:
            print(f"{self.name}: {len(P) - len(self.roots)} pieces, "
                  f"{len(msgs)} problems")
            for m in msgs[:40]:
                print("  ", m)
        return msgs

    # ------------------------------------------------------------------ output
    def write(self, path, focus=None):
        """focus: also write <path>-focus.ldr without the baseplates (for close renders)."""
        if focus:
            keep, self_roots = self.pieces, self.roots
            self.pieces = [p for i, p in enumerate(keep) if i not in self_roots]
            self.roots = set()
            self.write(focus)
            self.pieces, self.roots = keep, self_roots
        self._write(path)

    def _write(self, path):
        L = [f"0 {self.name}", f"0 Name: {os.path.basename(path)}", "0 Author: brickscape",
             "0 !LDRAW_ORG Unofficial_Model", ""]
        cur = None
        for p in sorted(self.pieces, key=lambda p: p.step):
            if cur is not None and p.step != cur:
                L.append("0 STEP")
            cur = p.step
            L.append(p.line())
        L.append("0 STEP")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        open(path, "w").write("\n".join(L) + "\n")

    def bom(self):
        c = collections.Counter((p.part, p.color) for i, p in enumerate(self.pieces) if i not in self.roots)
        return c


def _grid(a, b):
    """Stud centres (local LDU) along a bottom face from a to b, centred."""
    n = max(1, round((b - a) / 20))
    c = (a + b) / 2
    return [c + 20 * (k - (n - 1) / 2) for k in range(n)]


def _cells(p, W, D):
    """Stud cells and plate levels a grid-aligned piece's bounding box covers."""
    x0 = round((p.lo[0] + W * 10) / 20); x1 = round((p.hi[0] + W * 10) / 20)
    z0 = round((p.lo[2] + D * 10) / 20); z1 = round((p.hi[2] + D * 10) / 20)
    y0 = round(-p.hi[1] / 8); y1 = round(-p.lo[1] / 8)
    return range(x0, x1), range(z0, z1), range(y0, y1)


def recolor_visible(b, hidden, pick_color, flag=None):
    """Give hidden-coloured pieces that can be seen from outside a real colour.

    Air reachable from outside the model (flood fill) counts as open; sealed
    hollow interiors do not. pick_color(piece, neighbour_colours) -> colour."""
    import collections
    occ = {}
    maxy = 0
    for i, p in enumerate(b.pieces):
        if p.soft or i in b.roots:
            continue
        xs, zs, ys = _cells(p, b.W, b.D)
        maxy = max(maxy, ys[-1] + 1 if len(ys) else 0)
        sloped = "slope" in info(p.part)["desc"].lower()
        studded = set()
        if sloped:
            for s_, d_ in info(p.part)["studs"]:
                w = _apply(p.M, s_)
                studded.add((int((w[0] + b.W * 10) // 20), int((w[2] + b.D * 10) // 20)))
        for x in xs:
            for z in zs:
                # a slope's slanted cells are only solid near the bottom
                yy = ys if not sloped or (x, z) in studded else ys[:max(1, len(ys) // 3)]
                for y in yy:
                    occ[(x, z, y)] = i
    air = set()
    start = (-1, -1, maxy)
    todo = collections.deque([start])
    air.add(start)
    while todo:
        x, z, y = todo.popleft()
        for dx, dz, dy in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + dx, z + dz, y + dy)
            if not (-1 <= q[0] <= b.W and -1 <= q[1] <= b.D and 0 <= q[2] <= maxy):
                continue
            if q in air or q in occ:
                continue
            air.add(q)
            todo.append(q)
    n = 0
    def is_hidden(p):
        return (flag in p.note) if flag else p.color == hidden
    for i, p in enumerate(b.pieces):
        if not is_hidden(p) or p.soft or i in b.roots:
            continue
        xs, zs, ys = _cells(p, b.W, b.D)
        seen, near = False, []
        for x in xs:
            for z in zs:
                for y in ys:
                    for dx, dz, dy in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)):
                        q = (x + dx, z + dz, y + dy)
                        if q in air:
                            seen = True
                        j = occ.get(q)
                        if j is not None and j != i and not is_hidden(b.pieces[j]):
                            near.append(b.pieces[j].color)
        if seen:
            p.color = pick_color(p, near)
            p.note = p.note.replace(flag or "\0", "")
            n += 1
    return n


def write_crop(b, path, x0, z0, x1, z1):
    """Review file: pieces whose centre lies in the stud rectangle, with 8x8 plates
    standing in for the baseplates underneath (same colour, top at y=0)."""
    import copy
    c = Build(b.name + " (crop)", b.W, b.D)
    for i, p in enumerate(b.pieces):
        if i in b.roots:
            continue
        cx = ((p.lo[0] + p.hi[0]) / 2 + b.W * 10) / 20
        cz = ((p.lo[2] + p.hi[2]) / 2 + b.D * 10) / 20
        if x0 <= cx < x1 and z0 <= cz < z1:
            c.pieces.append(p)
    for i in b.roots:
        r = b.pieces[i]
        rx0 = round((r.lo[0] + b.W * 10) / 20); rx1 = round((r.hi[0] + b.W * 10) / 20)
        rz0 = round((r.lo[2] + b.D * 10) / 20); rz1 = round((r.hi[2] + b.D * 10) / 20)
        for x in range(max(x0, rx0) // 8 * 8, min(x1, rx1), 8):
            for z in range(max(z0, rz0) // 8 * 8, min(z1, rz1), 8):
                if rx0 <= x < rx1 and rz0 <= z < rz1:
                    c.put("41539", r.color, x, -1, z)
    c._write(path)


def seam_report(b, cols, rows, size=32):
    """Pieces sitting on the baseplates that span each baseplate seam segment."""
    out = {}
    for i, p in enumerate(b.pieces):
        # any rigid piece low in the build that spans the seam ties the two plates
        if p.soft or i in b.roots or -p.hi[1] / 8 > 8:
            continue
        x0 = (p.lo[0] + b.W * 10) / 20; x1 = (p.hi[0] + b.W * 10) / 20
        z0 = (p.lo[2] + b.D * 10) / 20; z1 = (p.hi[2] + b.D * 10) / 20
        for k in range(1, cols):
            s = k * size
            if x0 < s - 0.5 and x1 > s + 0.5:
                for r in range(rows):
                    if z0 < (r + 1) * size and z1 > r * size:
                        out[("x", s, r)] = out.get(("x", s, r), 0) + 1
        for k in range(1, rows):
            s = k * size
            if z0 < s - 0.5 and z1 > s + 0.5:
                for c in range(cols):
                    if x0 < (c + 1) * size and x1 > c * size:
                        out[("z", s, c)] = out.get(("z", s, c), 0) + 1
    rep = []
    for k in range(1, cols):
        for r in range(rows):
            rep.append((f"x={k*size} row{r}", out.get(("x", k * size, r), 0)))
    for k in range(1, rows):
        for c in range(cols):
            rep.append((f"z={k*size} col{c}", out.get(("z", k * size, c), 0)))
    return rep


PLANT_WORDS = ("plant", "leaves", "leaf", "flower", "grass", "vine", "stem", "bush", "tree")
# parts whose bounding box is a poor stand-in for their shape (curved arches used as branches,
# hinges, tabs): excluded from the overlap test when loading files
BOX_POOR_WORDS = ("arch", "hinge", "with tabs", "wedge", "facet", "corner round", "macaroni")
BASEPLATES = ("3811", "3867", "6098", "4186", "3857", "3645")


def from_ldr(path, name=None):
    """Load an .ldr / .mpd (sub-models flattened) into a Build for checking.

    Board size comes from the baseplates (or the part extents); baseplates become roots;
    plants and parts at non-right angles are 'soft' (excluded from the overlap test, and not
    required to connect, since the checker can't model them)."""
    from brickscape.io.analyze_ref import load
    parts, missing = load(path)
    xs, zs = [], []
    for p, c, M in parts:
        if p in BASEPLATES:
            i = info(p)
            xs += [M[0] + i["lo"][0], M[0] + i["hi"][0]]
            zs += [M[2] + i["lo"][2], M[2] + i["hi"][2]]
    if not xs:
        for p, c, M in parts:
            xs.append(M[0]); zs.append(M[2])
    X0, X1, Z0, Z1 = min(xs), max(xs), min(zs), max(zs)
    W, D = max(1, round((X1 - X0) / 20)), max(1, round((Z1 - Z0) / 20))
    b = Build(name or os.path.basename(path), W, D)
    dx, dz = -W * 10 - X0, -D * 10 - Z0          # move the board's min corner to Build's origin
    for p, c, M in parts:
        q = b.raw(p, c, (M[0] + dx, M[1], M[2] + dz, *M[3:]))
        if p in BASEPLATES:
            b.roots.add(len(b.pieces) - 1)
            continue
        d = info(p)["desc"].lower()
        if any(w in d for w in PLANT_WORDS):
            q.soft, q.free = True, True
        elif any(1e-3 < abs(v) < 0.999 for v in M[3:]):
            q.soft, q.free = True, True
        elif any(w in d for w in BOX_POOR_WORDS):
            q.soft = True
    b.missing = dict(missing)
    return b
