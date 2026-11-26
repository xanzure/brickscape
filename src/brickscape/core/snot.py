"""Exact SNOT placement: put a part so one of its anti-studs sits on a given stud.

stud(b, x, z, y, face) -> world stud base (LDU) and its outward direction, for a side stud on
  `face` (N/E/S/W) of a 1-cell brick whose bottom is at height y plates (side studs sit 14 LDU
  above a brick's bottom), or face 'U' = the top stud of a cell at height y (top surface).
attach(b, part, col, S, out, fwd, anti=(0, 0)): the part's bottom faces -out (its studs point
  along `out`), its local +z points along `fwd`, and its anti-stud at local (x, z) = anti sits
  on stud S.
"""
from brickscape.core.brick import info

V = {"N": (0, 0, -1), "S": (0, 0, 1), "E": (1, 0, 0), "W": (-1, 0, 0), "U": (0, -1, 0), "D": (0, 1, 0)}


def stud(b, x, z, y, face, along=0.0):
    cx, cz = b.X(x) + 10, b.Z(z) + 10
    if face == "U":
        return (cx, -8 * y, cz)
    d = V[face]
    return (cx + 10 * d[0], -8 * y - 14, cz + 10 * d[2])


def cross(a, c):
    return (a[1] * c[2] - a[2] * c[1], a[2] * c[0] - a[0] * c[2], a[0] * c[1] - a[1] * c[0])


def attach(b, part, col, S, out, fwd, anti=(0, 0), lift=0):
    o = V[out] if isinstance(out, str) else out
    f = V[fwd] if isinstance(fwd, str) else fwd
    ey = tuple(-v for v in o)          # local +y (down, into the part) = -out
    ez = f
    ex = cross(ey, ez)
    R = ((ex[0], ey[0], ez[0]), (ex[1], ey[1], ez[1]), (ex[2], ey[2], ez[2]))
    hb = info(part)["bottom"][0]
    a = (anti[0], hb + lift, anti[1])
    org = tuple(S[i] - sum(R[i][k] * a[k] for k in range(3)) for i in range(3))
    M = (*org, R[0][0], R[0][1], R[0][2], R[1][0], R[1][1], R[1][2], R[2][0], R[2][1], R[2][2])
    p = b.raw(part, col, M)
    p.soft = p.free = True
    return p


def studs_of(p):
    """World (position, direction) of the studs of placed piece p."""
    from brickscape.core.brick import _apply, _dir
    return [(_apply(p.M, s), _dir(p.M, d)) for s, d in info(p.part)["studs"]]


def on_stud(b, part, col, p, k, fwd, anti=(0, 0)):
    """attach() onto stud k of placed piece p (its direction = out)."""
    S, d = studs_of(p)[k]
    return attach(b, part, col, S, tuple(round(v) for v in d), fwd, anti)
