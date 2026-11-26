"""LDD .lxf/.lxfml -> LDraw. LDD units: 0.8 per stud, 0.32 per plate, y up. LDraw: 20 LDU per stud,
-y up. Each part's LDD origin differs from its LDraw origin by a per-part local offset (LDD's
ldraw.xml isn't available here), so offsets are SOLVED: for each design id try candidate local
offsets and keep the one that gives the most stud connections across the whole model.
"""
import itertools, math, zipfile, io, collections
import xml.etree.ElementTree as ET
from brickscape.core.brick import info, _apply

S = 25.0
FLIP = (1, -1, -1)          # LDraw = diag(FLIP) * LDD * 25


def read(path):
    if path.lower().endswith(".lxf"):
        z = zipfile.ZipFile(path)
        name = [n for n in z.namelist() if n.upper().endswith(".LXFML")][0]
        root = ET.fromstring(z.read(name))
    else:
        root = ET.parse(path).getroot()
    out = []
    for bk in root.iter("Brick"):
        for p in bk.findall("Part"):
            bone = p.find("Bone")
            v = [float(x) for x in bone.get("transformation").split(",")]
            mats = [m for m in p.get("materials", "0").split(",") if m != "0"] or ["0"]
            out.append((p.get("designID"), int(mats[0]), v))
    return out


def ldraw_matrix(v, transpose):
    a = v[:9]
    R = [[a[0], a[3], a[6]], [a[1], a[4], a[7]], [a[2], a[5], a[8]]] if transpose else \
        [[a[0], a[1], a[2]], [a[3], a[4], a[5]], [a[6], a[7], a[8]]]
    # conjugate by diag(FLIP)
    R2 = [[R[i][j] * FLIP[i] * FLIP[j] for j in range(3)] for i in range(3)]
    t = [v[9] * S * FLIP[0], v[10] * S * FLIP[1], v[11] * S * FLIP[2]]
    return R2, t


def _rots():
    import itertools
    out = []
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            Mx = [[0] * 3 for _ in range(3)]
            for i in range(3):
                Mx[i][perm[i]] = sg[i]
            det = (Mx[0][0] * (Mx[1][1] * Mx[2][2] - Mx[1][2] * Mx[2][1]) - Mx[0][1] * (Mx[1][0] * Mx[2][2] - Mx[1][2] * Mx[2][0])
                   + Mx[0][2] * (Mx[1][0] * Mx[2][1] - Mx[1][1] * Mx[2][0]))
            if det == 1:
                out.append(Mx)
    return out
ROTS = _rots()
IDENT = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def place(R, t, off, E=None):
    """origin = t + R*off (off in LDraw part-local coords); E = extra local rotation."""
    if E is not None:
        R = [[sum(R[i][k] * E[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    o = [t[i] + sum(R[i][k] * off[k] for k in range(3)) for i in range(3)]
    return (o[0], o[1], o[2], R[0][0], R[0][1], R[0][2], R[1][0], R[1][1], R[1][2], R[2][0], R[2][1], R[2][2])


def candidates(part):
    i = info(part)
    h = i["hi"][1]          # LDraw: origin at top usually, bottom at +h
    xs = sorted({0, 10, -10, 20, -20, 30, -30})
    ys = sorted({-h, 0, -h / 2, h})
    return [(x, y, z) for x in xs for y in ys for z in xs]


def score(pieces):
    """Count stud->bottom alignments: stud tip positions of every part vs the bottom-grid points."""
    studs = collections.Counter()
    for part, M in pieces:
        for s, d in info(part)["studs"]:
            p = _apply(M, s)
            studs[(round(p[0] / 5), round(p[1] / 4), round(p[2] / 5))] += 1
    sc = 0
    for part, M in pieces:
        yb, blo, bhi = info(part)["bottom"]
        for lx in range(int(blo[0]) // 10 * 10 + 10, int(bhi[0]) + 1, 20) if bhi[0] - blo[0] >= 18 else [0]:
            for lz in range(int(blo[1]) // 10 * 10 + 10, int(bhi[1]) + 1, 20) if bhi[1] - blo[1] >= 18 else [0]:
                p = _apply(M, (lx, yb, lz))
                sc += studs.get((round(p[0] / 5), round(p[1] / 4), round(p[2] / 5)), 0)
    return sc


def convert(path, idmap=None, colmap=None, out=None, verbose=True, fixed=None, turn=(), transposes=(False, True)):
    idmap = idmap or {}
    fixed = fixed or {}
    raw = read(path)
    best = None
    for transpose in transposes:
        mats = [(idmap.get(d, d), c, *ldraw_matrix(v, transpose)) for d, c, v in raw]
        def one(p):
            i = info(p); return (i["hi"][0] - i["lo"][0] <= 21 and i["hi"][2] - i["lo"][2] <= 21) or p in fixed
        offs = {p: fixed.get(p, (0, -info(p)["hi"][1], 0)) for p, *_ in mats}
        extra = {}
        for it in range(2):
            for p in sorted(q for q in offs if not one(q)):
                bestp = None
                rots = ROTS if p in turn else [None]
                for E in rots:
                    for off in candidates(p):
                        trial = dict(offs); trial[p] = off
                        tr = dict(extra); tr[p] = E
                        pcs = [(q, place(R, t, trial[q], tr.get(q))) for q, c, R, t in mats]
                        s = score(pcs)
                        if bestp is None or s > bestp[0]:
                            bestp = (s, off, E)
                offs[p] = bestp[1]; extra[p] = bestp[2]
        pcs = [(q, place(R, t, offs[q], extra.get(q))) for q, c, R, t in mats]
        s = score(pcs)
        if verbose:
            print("transpose", transpose, "score", s)
        if best is None or s > best[0]:
            best = (s, transpose, offs, mats, extra)
    s, transpose, offs, mats, extra = best
    lines = ["0 converted from " + path.split("/")[-1]]
    # put the model's lowest point on y = 0 and centre it
    pcs = [(q, c, place(R, t, offs[q], extra.get(q))) for q, c, R, t in mats]
    return pcs, offs
