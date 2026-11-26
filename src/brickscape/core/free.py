"""Free placement: parts at any rotation (SNOT reliefs, pieces turned on one stud), placed by the
centre of their bounding box. Such parts are marked free (the stud checker does not judge them).

  R = frame(U, N)            local x -> U, studs (local -y) -> N (outward), local z -> U x (-N)
  R = mul(rot_axis(N, deg), R)   turn in the plane around N
  place(b, part, colour, R, centre)
Vectors are LDraw world coordinates (LDU; -Y is up, front is -Z).
"""
import math
from brickscape.core.brick import info


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    l = math.sqrt(sum(v * v for v in a)) or 1
    return tuple(v / l for v in a)


def frame(U, N):
    """Columns: local x -> U, local +y (down, into the part's bottom) -> -N, local z -> U x (-N)."""
    U, N = norm(U), norm(N)
    mN = tuple(-v for v in N)
    W = cross(U, mN)
    return ((U[0], mN[0], W[0]), (U[1], mN[1], W[1]), (U[2], mN[2], W[2]))


def rot_axis(axis, deg):
    x, y, z = norm(axis)
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    C = 1 - c
    return ((c + x * x * C, x * y * C - z * s, x * z * C + y * s),
            (y * x * C + z * s, c + y * y * C, y * z * C - x * s),
            (z * x * C - y * s, z * y * C + x * s, c + z * z * C))


def mul(A, B):
    return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def apply(R, v):
    return tuple(sum(R[i][k] * v[k] for k in range(3)) for i in range(3))


def place(b, part, colour, R, centre, note=""):
    """Put `part` so its local bounding-box centre lands on world point `centre`."""
    inf = info(part)
    cl = tuple((inf["lo"][i] + inf["hi"][i]) / 2 for i in range(3))
    rc = apply(R, cl)
    t = tuple(centre[i] - rc[i] for i in range(3))
    M = (t[0], t[1], t[2], R[0][0], R[0][1], R[0][2], R[1][0], R[1][1], R[1][2], R[2][0], R[2][1], R[2][2])
    p = b.raw(part, colour, M, note)
    p.soft, p.free = True, True
    return p


def size(part):
    """Local bounding box size (x, y, z) in LDU."""
    inf = info(part)
    return tuple(inf["hi"][i] - inf["lo"][i] for i in range(3))
