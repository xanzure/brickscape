"""Strict build checks. Every model brickscape outputs goes through validate().

Checks (each reported separately; the report never claims more than what was checked):
  parts       every part exists in the LDraw library
  source      every part and colour exists in the chosen part source (LEGO or GoBricks)
  rotations   every rotation is a proper rotation (no mirror, no scale)
  duplicates  no two identical parts in the same place
  collisions  no two parts' solids overlap (real part shapes, see core/geom.py); leaves may
              rest on each other up to geom.FLEX_PEN, since they bend
  connected   every part is held by a real connection, and all parts connect to the base
"""
import collections, itertools
import numpy as np
from brickscape.core import geom
from brickscape.core.brick import info, _find


def _bbox_pairs(P, pad=1.0):
    """Candidate pairs whose world bounding boxes overlap (spatial hash, 40 LDU cells)."""
    cell = collections.defaultdict(list)
    for i, p in enumerate(P):
        for gx in range(int(p.lo[0] // 40), int(p.hi[0] // 40) + 1):
            for gy in range(int(p.lo[1] // 40), int(p.hi[1] // 40) + 1):
                for gz in range(int(p.lo[2] // 40), int(p.hi[2] // 40) + 1):
                    cell[(gx, gy, gz)].append(i)
    seen = set()
    for ids in cell.values():
        for i, j in itertools.combinations(ids, 2):
            if (i, j) in seen:
                continue
            seen.add((i, j))
            a, b = P[i], P[j]
            if all(a.lo[k] + pad < b.hi[k] and b.lo[k] + pad < a.hi[k] for k in range(3)):
                yield i, j


def collisions(b, joined=()):
    """Overlapping part pairs. Pairs joined by a bar, clip, pin, hinge, ball or generic
    connection are skipped: those parts are meant to nest into each other."""
    P = b.pieces
    boxes, out = {}, []
    for i, j in _bbox_pairs(P):
        if i in b.roots and j in b.roots or (i, j) in joined:
            continue
        for k in (i, j):
            if k not in boxes:
                boxes[k] = geom.world_boxes(P[k].part, P[k].M)
        if geom.collide(boxes[i], boxes[j], geom.pen_for(P[i].part, P[j].part)):
            out.append((i, j))
    return out


def rotations(b):
    bad = []
    for i, p in enumerate(b.pieces):
        R = np.array(p.M[3:]).reshape(3, 3)
        if not (np.allclose(R @ R.T, np.eye(3), atol=1e-3) and abs(np.linalg.det(R) - 1) < 1e-3):
            bad.append(i)
    return bad


def duplicates(b):
    seen, out = {}, []
    for i, p in enumerate(b.pieces):
        k = (p.part, tuple(round(v, 1) for v in p.M))
        if k in seen:
            out.append((seen[k], i))
        else:
            seen[k] = i
    return out


def _world_snaps(p):
    from brickscape.core.snaps import part_snaps, Snap
    S, had = part_snaps(p.part)
    R, t = np.array(p.M[3:]).reshape(3, 3), np.array(p.M[:3])
    if not had:                      # no part-level info: add anti-studs under the bottom face
        S = list(S) + [f for f in _fallback(p.part) if f.gender == "F"]
    return [s.copy_to((R, t)) for s in S], had


def _fallback(part):
    from brickscape.core.snaps import Snap
    from brickscape.core.brick import _grid
    inf = info(part)
    def cyl(pos, up, g):
        s = Snap()
        s.kind, s.gender, s.id, s.group, s.caps, s.center = "cyl", g, "", "", "one", False
        s.secs, s.length, s.radius, s.seq, s.gofs, s.bounding = [("R", 6.0, 4.0)], 4.0, 6.0, [], "M", ""
        s.pos = np.array(pos, float)
        y = -np.array(up, float)                       # snap axis is the snap's -Y
        x = np.cross(y, [0, 0, 1]) if abs(y[2]) < 0.9 else np.cross(y, [1, 0, 0])
        x /= np.linalg.norm(x)
        s.R = np.column_stack([x, y, np.cross(x, y)])
        return s
    for pos, d in inf["studs"]:
        yield cyl(pos, d, "M")
    yb, blo, bhi = inf["bottom"]
    for x in _grid(blo[0], bhi[0]):
        for z in _grid(blo[1], bhi[1]):
            yield cyl((x, yb, z), (0, -1, 0), "F")


def connections(b):
    """-> (edges {(i, j): type}, parts without shadow info)."""
    from brickscape.core.snaps import match, _axis
    P = b.pieces
    cell = collections.defaultdict(list)
    allsnaps, nosh = [], []
    for i, p in enumerate(P):
        S, had = _world_snaps(p)
        if not had:
            nosh.append(p.part)
        for s in S:
            k = len(allsnaps)
            allsnaps.append((i, s))
            d, (u0, u1) = _axis(s)
            n = max(1, int((u1 - u0) / 4))
            for q in range(n + 1):
                pt = s.pos + d * (u0 + (u1 - u0) * q / n)
                cell[tuple((pt // 10).astype(int))].append(k)
    edges, tried = {}, set()
    for c, ks in cell.items():
        near = [k2 for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                for k2 in cell.get((c[0] + dx, c[1] + dy, c[2] + dz), ())]
        for k in ks:
            i, a = allsnaps[k]
            for k2 in near:
                j, s2 = allsnaps[k2]
                if j <= i or (k, k2) in tried:
                    continue
                tried.add((k, k2))
                if i in b.roots and j in b.roots:
                    continue
                t = match(a, s2)
                if t and (edges.get((i, j)) in (None, "stud")):
                    edges[(i, j)] = t
    return edges, sorted(set(nosh))


def components(n, edges, roots):
    adj = collections.defaultdict(set)
    for i, j in edges:
        adj[i].add(j); adj[j].add(i)
    start = set(roots)
    if not start:                    # no baseplate: the biggest group is the base
        best, seen = set(), set()
        for s in range(n):
            if s in seen:
                continue
            grp, todo = {s}, [s]
            while todo:
                for m in adj[todo.pop()]:
                    if m not in grp:
                        grp.add(m); todo.append(m)
            seen |= grp
            if len(grp) > len(best):
                best = grp
        return best
    reach, todo = set(start), list(start)
    while todo:
        for m in adj[todo.pop()]:
            if m not in reach:
                reach.add(m); todo.append(m)
    return reach


def validate(b, source="lego"):
    P = b.pieces
    rep = {"pieces": len(P) - len(b.roots), "checks": {}}
    rep["checks"]["parts"] = sorted({p.part for p in P if not _find(p.part + ".dat")})
    rep["checks"]["rotations"] = [f"{P[i].part}#{i}" for i in rotations(b)]
    rep["checks"]["duplicates"] = [f"{P[i].part}#{i} = #{j}" for i, j in duplicates(b)]
    edges, nosh = connections(b)
    joined = {e for e, t in edges.items() if t != "stud"}
    rep["checks"]["collisions"] = [f"{P[i].part}#{i} x {P[j].part}#{j}" for i, j in collisions(b, joined)]
    reach = components(len(P), edges, b.roots)
    rep["checks"]["not_connected"] = [f"{P[i].part}#{i}" for i in range(len(P)) if i not in reach]
    rep["connections"] = dict(collections.Counter(edges.values()))
    rep["no_connection_data"] = nosh
    if source:
        from brickscape import catalog
        cnt = collections.Counter((p.part, p.color) for i, p in enumerate(P) if i not in b.roots)
        rep["source"] = catalog.get(source).check(cnt)
    return rep


def _removable(k, edges, reach, roots):
    """True if removing piece k leaves everything else still connected to the base."""
    sub = {e: t for e, t in edges.items() if k not in e}
    r2 = components(max(max(e) for e in edges) + 1 if edges else 0, sub, roots)
    return all(i in r2 for i in reach if i != k)


def repair(b, max_rounds=5):
    """Remove parts that make a build unbuildable when removing them costs nothing: loose
    parts, and in each clashing pair the later part if it is decorative (plants, leaves,
    flowers) or holds nothing else up. Anything else stays in the report as a failure.
    -> list of removed (part, colour) for the report."""
    from brickscape.terrain.greenery import decorative
    removed = []
    for _ in range(max_rounds):
        edges, _ = connections(b)
        joined_ = {e for e, t in edges.items() if t != "stud"}
        reach = components(len(b.pieces), edges, b.roots)
        bad = {i for i in range(len(b.pieces)) if i not in reach}
        deg = collections.Counter()
        for (i, j) in edges:
            deg[i] += 1
            deg[j] += 1
        for i, j in collisions(b, joined_):
            for k in (j, i):                   # drop the later decorative one, or a part that
                if k in b.roots:               # holds nothing up (one connection at most)
                    continue
                if decorative(b.pieces[k].part) or deg[k] <= 1 or _removable(k, edges, reach, b.roots):
                    bad.add(k)
                    break
        bad = {i for i in bad if i not in b.roots}
        if not bad:
            break
        removed += [(b.pieces[i].part, b.pieces[i].color) for i in sorted(bad)]
        keep = [p for i, p in enumerate(b.pieces) if i not in bad]
        roots = {keep.index(b.pieces[i]) for i in b.roots}
        b.pieces, b.roots, b._grid = [], roots, {}
        for p in keep:
            b.pieces.append(p)
            b._index(len(b.pieces) - 1)
    return removed
