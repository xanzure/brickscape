"""Placement-time collision checks: does a new piece fit where it was put?

clashes(b, i) uses the same real-shape test and the same joined-pair rule as validate():
parts held together by a bar, clip, pin, hinge or ball may nest into each other, any other
overlap is a clash.
"""
from brickscape.core import geom


def boxes(p):
    if p._boxes is None:
        p._boxes = geom.world_boxes(p.part, p.M)
    return p._boxes


def snaps(p):
    if p._snaps is None:
        from brickscape.validate import _world_snaps
        p._snaps = _world_snaps(p)[0]
    return p._snaps


def joined(p, q):
    """Connection type between two placed pieces, or None."""
    from brickscape.core.snaps import match
    best = None
    for a in snaps(p):
        for c in snaps(q):
            if abs(a.pos[0] - c.pos[0]) > 40 or abs(a.pos[1] - c.pos[1]) > 40 or abs(a.pos[2] - c.pos[2]) > 40:
                continue
            t = match(a, c)
            if t and t != "stud":
                return t
            best = best or t
    return best


def clashes(b, i):
    p = b.pieces[i]
    out = []
    for j in b.near(i):
        q = b.pieces[j]
        if j in b.roots and False:
            continue
        if geom.collide(boxes(p), boxes(q), geom.pen_for(p.part, q.part)) and joined(p, q) in (None, "stud"):
            out.append(j)
    return out


def fits(b, i):
    return not clashes(b, i)
