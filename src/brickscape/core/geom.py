"""Part solids for collision tests.

Each part's mesh (from the LDraw library) is ray-cast along its own vertical axis on a
1.25 LDU column grid. The hits along each ray are paired into solid runs (enter / exit), so
hollow undersides, tubes and slopes come out right. Neighbouring columns with the same runs
are merged into boxes. A part's solid is then a few dozen boxes in its own frame; two placed
parts collide when some pair of their boxes interpenetrates deeper than PEN.

Studs are part of the solid: a stud inside an anti-stud lands in empty space, a stud pushed
into solid plastic is a collision.
"""
import functools, os, pickle
import numpy as np
from brickscape.config import DATA
from brickscape.core.brick import _find

RES = 1.25         # LDU column spacing
PEN = 0.8          # LDU: two solids clash when they interpenetrate deeper than this (touching is fine;
                   # covers the RES/2 column error round studs and holes)
_DISK = os.path.join(DATA, "solids-%g" % RES)


def _tris(name, M=np.eye(4), out=None, depth=0):
    """All triangles of a file (flattened, in the file's frame) as a list of 3x3 arrays."""
    out = [] if out is None else out
    path = _find(name)
    if not path or depth > 12:
        return out
    for line in open(path, errors="ignore"):
        t = line.split()
        if not t:
            continue
        if t[0] == "1" and len(t) >= 15:
            v = list(map(float, t[2:14]))
            S = np.array([[v[3], v[4], v[5], v[0]], [v[6], v[7], v[8], v[1]],
                          [v[9], v[10], v[11], v[2]], [0, 0, 0, 1]])
            _tris(" ".join(t[14:]), M @ S, out, depth + 1)
        elif t[0] in ("3", "4"):
            n = int(t[0])
            P = np.array(list(map(float, t[2:2 + 3 * n]))).reshape(n, 3)
            P = P @ M[:3, :3].T + M[:3, 3]
            out.append(P[[0, 1, 2]])
            if n == 4:
                out.append(P[[0, 2, 3]])
    return out


def _runs(ys):
    """Sorted ray hits -> solid runs. Odd counts (open meshes) fall back to one min-max run."""
    ys = np.unique(np.round(ys, 2))
    if len(ys) < 2:
        return ()
    if len(ys) % 2:
        return ((float(ys[0]), float(ys[-1])),)
    return tuple((float(ys[i]), float(ys[i + 1])) for i in range(0, len(ys), 2))


FLAT = ("3811", "3867", "6098", "4186", "3857", "3645", "41539", "3036", "3033", "3958", "3035",
        "3032", "3031", "3030", "3029", "3028", "3027", "3026", "92438", "91405")


@functools.lru_cache(None)
def solid(part):
    """Boxes (n x 6 array: x0, y0, z0, x1, y1, z1) in the part's own frame.
    Baseplates and big plates are one box (their body without studs): their mesh is huge and
    nothing nests into them except through studs."""
    if part in FLAT:
        from brickscape.core.brick import info
        i = info(part)
        return np.array([[*i["lo"], *i["hi"]]])
    os.makedirs(_DISK, exist_ok=True)
    cache = os.path.join(_DISK, part + ".pkl")
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    T = _tris(part + ".dat")
    if not T:
        return np.zeros((0, 6))
    T = np.array(T)                                   # n x 3 x 3
    lo, hi = T.min(axis=(0, 1)), T.max(axis=(0, 1))
    xs = np.arange(lo[0] + RES / 2, hi[0], RES)
    zs = np.arange(lo[2] + RES / 2, hi[2], RES)
    # barycentric set-up in the xz plane
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    d = (b[:, 2] - c[:, 2]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 2] - c[:, 2])
    ok = np.abs(d) > 1e-9                              # skip triangles seen edge-on
    a, b, c, d = a[ok], b[ok], c[ok], d[ok]
    tlo, thi = np.minimum(np.minimum(a, b), c), np.maximum(np.maximum(a, b), c)
    cols = {}
    for x in xs:
        sel = (tlo[:, 0] <= x) & (thi[:, 0] >= x)
        if not sel.any():
            continue
        A, B, Cc, D = a[sel], b[sel], c[sel], d[sel]
        zl, zh = tlo[sel, 2], thi[sel, 2]
        for z in zs:
            s2 = (zl <= z) & (zh >= z)
            if not s2.any():
                continue
            a2, b2, c2, d2 = A[s2], B[s2], Cc[s2], D[s2]
            l1 = ((b2[:, 2] - c2[:, 2]) * (x - c2[:, 0]) + (c2[:, 0] - b2[:, 0]) * (z - c2[:, 2])) / d2
            l2 = ((c2[:, 2] - a2[:, 2]) * (x - c2[:, 0]) + (a2[:, 0] - c2[:, 0]) * (z - c2[:, 2])) / d2
            l3 = 1 - l1 - l2
            e = -1e-6
            hit = (l1 >= e) & (l2 >= e) & (l3 >= e)
            if hit.any():
                y = l1[hit] * a2[hit, 1] + l2[hit] * b2[hit, 1] + l3[hit] * c2[hit, 1]
                r = _runs(y)
                if r:
                    cols[(round(x, 3), round(z, 3))] = r
    boxes = _merge(cols)
    pickle.dump(boxes, open(cache, "wb"))
    return boxes


def _merge(cols):
    """Columns with identical runs -> boxes: merge along x into strips, then strips along z."""
    h = RES / 2
    strips = {}                                        # (z, runs) -> list of x
    for (x, z), r in cols.items():
        strips.setdefault((z, r), []).append(x)
    rows = {}                                          # (x0, x1, runs) -> list of z
    for (z, r), xs in strips.items():
        xs.sort()
        s = xs[0]
        for i in range(1, len(xs) + 1):
            if i == len(xs) or xs[i] - xs[i - 1] > RES * 1.01:
                rows.setdefault((s, xs[i - 1], r), []).append(z)
                if i < len(xs):
                    s = xs[i]
    out = []
    for (x0, x1, r), zs in rows.items():
        zs.sort()
        s = zs[0]
        for i in range(1, len(zs) + 1):
            if i == len(zs) or zs[i] - zs[i - 1] > RES * 1.01:
                for y0, y1 in r:
                    out.append((x0 - h, y0, s - h, x1 + h, y1, zs[i - 1] + h))
                if i < len(zs):
                    s = zs[i]
    return np.array(out) if out else np.zeros((0, 6))


def world_boxes(part, M):
    """Oriented boxes of a placed part: (centres n x 3, half sizes n x 3, rotation 3 x 3)."""
    B = solid(part)
    R = np.array(M[3:]).reshape(3, 3)
    t = np.array(M[:3])
    c = (B[:, :3] + B[:, 3:]) / 2
    hs = (B[:, 3:] - B[:, :3]) / 2
    return c @ R.T + t, hs, R


FLEX_PEN = 4.0     # LDU allowed between two flexible plant parts (leaves bend and rest on each other)
FLEX_WORDS = ("leaves", "leaf", "plant", "flower", "grass", "fern", "vine", "stem", "frond")


@functools.lru_cache(None)
def flexible(part):
    from brickscape.core.brick import info
    d = info(part)["desc"].lower()
    return any(w in d for w in FLEX_WORDS)


def pen_for(a, b):
    """Penetration allowed between two parts (by part id)."""
    return FLEX_PEN if flexible(a) and flexible(b) else PEN


def _aabb(c, h, R):
    e = h @ np.abs(R).T
    return c - e, c + e


def _square(R):
    """True if R only permutes / flips axes (no odd angles)."""
    return np.allclose(np.abs(R), np.round(np.abs(R)), atol=1e-6)


def collide(A, B, pen=None):
    """True if some box of placed part A and some box of B interpenetrate deeper than `pen`
    (default PEN) along every separating axis. World-AABB prefilters first; the full
    separating-axis test only for parts at odd angles."""
    pen = PEN if pen is None else pen
    ca, ha, Ra = A
    cb, hb, Rb = B
    if not len(ca) or not len(cb):
        return False
    la, ua = _aabb(ca, ha, Ra)
    lb, ub = _aabb(cb, hb, Rb)
    # keep only boxes that reach into the other part's overall bounds
    ka = ((la < ub.max(0) - pen) & (ua > lb.min(0) + pen)).all(1)
    kb = ((lb < ua.max(0) - pen) & (ub > la.min(0) + pen)).all(1)
    if not ka.any() or not kb.any():
        return False
    ca, ha, la, ua = ca[ka], ha[ka], la[ka], ua[ka]
    cb, hb, lb, ub = cb[kb], hb[kb], lb[kb], ub[kb]
    ov = ((la[:, None, :] < ub[None, :, :] - pen) & (lb[None, :, :] < ua[:, None, :] - pen)).all(2)
    if not ov.any():
        return False
    if _square(Ra) and _square(Rb):
        return True                       # axis-aligned boxes: the AABB test is exact
    ia, ib = np.nonzero(ov)
    D = cb[ib] - ca[ia]
    HA, HB = ha[ia], hb[ib]
    axes = [Ra[:, k] for k in range(3)] + [Rb[:, k] for k in range(3)]
    axes += [np.cross(Ra[:, i], Rb[:, j]) for i in range(3) for j in range(3)]
    sep = np.zeros(len(ia), bool)
    for L in axes:
        n = np.linalg.norm(L)
        if n < 1e-6:
            continue
        L = L / n
        pa = (HA * np.abs(Ra.T @ L)).sum(1)
        pb = (HB * np.abs(Rb.T @ L)).sum(1)
        sep |= np.abs(D @ L) > pa + pb - pen
        if sep.all():
            return False
    return bool((~sep).any())
