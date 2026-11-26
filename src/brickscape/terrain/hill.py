"""Castle hill builder: flat plateau, rock cliff on one side, brick terraces on the other,
and a road that climbs the terraces' shelves (cut into the hillside, never a raised ribbon).

castle_hill(b, rng, board, P, cliff_dir, road_pts, ...) -> dict with
  'terraces' {cell: courses}, 'rock' {cell: layers}, 'road' set, 'occupied' set,
  'tsurf'/'rsurf' surfaces (for plants), 'top' plateau height (plates)."""
import math
from brickscape.core.kit import (value_noise, clean, tuft, pick, nbr, DIRS, path_cells, pack, put_rect, PLATES,
                 GREEN, DTAN, RBROWN, DBG, LBG, TAN)
from brickscape.terrain.rock2 import Rock, dress, blocky
from brickscape.terrain.ground import Terraces, sunken_path, rough_stones
from brickscape.terrain.rock2 import layered

TOP_C = 4


def distance_field(P, board, maxd=40):
    dist = {c: 0 for c in P}
    frontier = set(P)
    for i in range(1, maxd):
        frontier = {nbr(c, d) for c in frontier for d in DIRS if nbr(c, d) in board} - set(dist)
        if not frontier:
            break
        for c in frontier:
            dist[c] = i
    return dist


def _along_fn(pts):
    seg = [math.dist(a, e) for a, e in zip(pts, pts[1:])]

    def along(c):
        best, acc, pos = 1e9, 0.0, 0.0
        for (a, e), L in zip(zip(pts, pts[1:]), seg):
            ax, az = a; ex, ez = e
            t = max(0, min(1, ((c[0] + .5 - ax) * (ex - ax) + (c[1] + .5 - az) * (ez - az)) / (L * L)))
            dd = math.hypot(ax + t * (ex - ax) - c[0] - .5, az + t * (ez - az) - c[1] - .5)
            if dd < best:
                best, pos = dd, acc + t * L
            acc += L
        return pos
    return along, seg


def castle_hill(b, rng, board, P, centre, cliff_dir, road_pts=None, seed=0, cliff_width=0.58,
                reach=12, tread=(0.8, 6.5), road_style="rough", outcrops=6, rock_colour=DBG, grade=0.5,
                plants=True, avoid=(), plant_board=None):
    avoid = set(avoid)
    board = set(board) - avoid
    P = set(P) & board
    dist = distance_field(P, board)
    cx, cz = centre

    def side(x, z):
        a = math.atan2(z + 0.5 - cz, x + 0.5 - cx)
        return 0.5 + 0.5 * math.cos(a - math.radians(cliff_dir))

    cliff_side = lambda c: side(*c) > cliff_width
    nt = value_noise(seed + 2, 9.0)
    nj = blocky(value_noise(seed + 6, 3.5), 2)
    nk = blocky(value_noise(seed + 3, 3.0), 2)
    # each tread has its own width field, so treads wander independently: wide shelves
    # in places, and where a tread pinches out two risers merge into one taller step
    wn = [value_noise(seed + 20 + j, 8.0) for j in range(TOP_C)]
    nf = value_noise(seed + 30, 1.6)             # fine 1-stud wobble so edges aren't 2-stud blocks
    C = {c: TOP_C for c in P}
    for c, d in dist.items():
        if d == 0 or cliff_side(c):
            continue
        dj = d + 2.0 * (nj(*c) - 0.5) + 1.3 * (nf(*c) - 0.5)
        bound, k = 0.0, TOP_C
        for j in range(TOP_C - 1, 0, -1):
            bound += tread[0] + tread[1] * wn[j](*c) ** 1.3
            if dj > bound:
                k = j - 1 if j > 1 else 0
            else:
                k = j
                break
        if d > reach + 3 * (nj(c[0] * 0.7, c[1] * 0.7) - 0.5):
            k = 0
        if k > 0:
            C[c] = k
    R = {}
    for c, d in dist.items():
        if d == 0 or not cliff_side(c):
            continue
        L = 5 - math.floor((d - 1) * 1.1 + 1.8 * (nk(*c) - 0.5))
        if L > 0:
            R[c] = min(5, L)
    # ------------------------------------------------ road
    road, RH = set(), {}
    if road_pts:
        road = path_cells(road_pts, 3, 3.5, seed=seed + 4, board=board) - P
        along, seg = _along_fn(road_pts)
        total = sum(seg)
        samples, acc = [], 0.0
        for (a, e), L in zip(zip(road_pts, road_pts[1:]), seg):
            for i in range(int(L * 2)):
                t = i / (L * 2)
                q = (int(a[0] + t * (e[0] - a[0])), int(a[1] + t * (e[1] - a[1])))
                samples.append((acc + t * L, 4 * C.get(q, 0)))
            acc += L
        samples.append((total, 4 * TOP_C))
        best, prof = 0, []
        for sv, h in samples:
            best = max(best, h)
            prof.append((sv, best))

        def road_h(sv):
            out, m = 0, 99
            for s0, h in prof:
                if s0 > sv:
                    break
                out = h
            for s0, h in prof:
                if s0 > sv:
                    break
                if h < out:
                    m = min(m, h + grade * (sv - s0))
            return int(min(out, m)) if m < 99 else out
        RH = {c: road_h(along(c)) for c in road}
        for c in road:
            R.pop(c, None)
            C.pop(c, None)
        for c in sorted(road):
            rc = RH[c] // 4
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    n = (c[0] + dx, c[1] + dz)
                    if n in board and n not in road and n not in R and n not in P and abs(dx) + abs(dz) <= 3:
                        if rc > C.get(n, 0):
                            C[n] = rc
    road_course = {c: h // 4 for c, h in RH.items() if h >= 4}
    road_extra = {c: h % 4 for c, h in RH.items() if h % 4}
    C.update(road_course)
    HT, prev = {}, set(board)
    for k in range(1, TOP_C + 1):
        cur = {c for c in prev if C.get(c, 0) >= k}
        keep = set(clean({c: 1 for c in cur - set(road_course)}, 3)) | \
            {c for c in cur if road_course.get(c, 0) >= k}
        for c in keep:
            HT[c] = k
        prev = keep

    # ------------------------------------------------ rock outcrops poking out of the terraces
    near_road = {(c[0] + i, c[1] + j) for c in road for i in range(-3, 4) for j in range(-3, 4)}
    sites = []
    cand = [c for c in sorted(board) if c not in near_road and c not in R and c not in P and
            any(HT.get(nbr(c, d), 0) > HT.get(c, 0) for d in DIRS) and HT.get(c, 0) < TOP_C]
    rng.shuffle(cand)
    for c in cand:
        if len(sites) >= outcrops:
            break
        if all(math.dist(c, s_) > 11 for s_ in sites):
            sites.append(c)
    OUT = []
    taken_out = set()
    for i, (sx, sz) in enumerate(sites):
        lvl = HT.get((sx, sz), 0)
        rx = 1.6 + 1.4 * rng.random()
        area = {c for c in board if HT.get(c, 0) == lvl and c not in near_road and c not in R
                and c not in taken_out and math.dist(c, (sx, sz)) < rx + 1.5}
        f = lambda x, z, sx=sx, sz=sz, rx=rx: 2.6 * (1 - math.dist((x + .5, z + .5), (sx + .5, sz + .5)) / rx) + 0.8
        Ho = layered(area, f, 2, rate=1.0, amp=1.4, seed=seed + 40 + i, q=1)
        if len(Ho) < 3:
            continue
        OUT.append((lvl, Ho))
        taken_out |= {(c[0] + a, c[1] + b_) for c in Ho for a in (-1, 0, 1) for b_ in (-1, 0, 1)}

    def rock_h(c):
        return 3 * R[c] + (1 if R[c] == 5 else 0) if c in R else 0

    solid_for_rock = lambda c, y: (c in HT and y < 4 * HT[c]) or (c in RH and y < RH[c])
    solid_for_terr = lambda c, y: (c in R and y < rock_h(c)) or (c in road_extra and y < RH[c])
    en = value_noise(seed + 5, 11.0)

    def riser(c, k):
        v = en(c[0] + 3 * k, c[1] - 2 * k)
        return RBROWN if v > 0.72 else (DTAN if v < 0.3 else DBG)

    terr = Terraces(b, HT, seed=seed + 7, riser_fn=riser, forbid=road | set(R), solid_fn=solid_for_terr,
                    lip=0.35, edge_cheese=0.08, tread_fn=lambda c: DTAN if c in road else None,
                    no_cheese=road, reserved=taken_out,
                    board=(board - {(c[0] + i, c[1] + j) for c in road for i in range(-5, 6)
                                    for j in range(-5, 6)}) | set(HT))
    tsurf = terr.build()
    osurfs = []
    for i, (lvl, Ho) in enumerate(OUT):
        y0 = 4 * lvl
        solid_o = lambda c, y, Ho=Ho: (c in HT and y < 4 * HT[c] and c not in Ho)
        ro = Rock(b, Ho, base_y=y0, seed=seed + 60 + i, colour=rock_colour, accent=LBG, accent_amt=0.15,
                  moss=0.2, cap_grass=0.4, undercut=0, rim_round=0.95, ledge_cheese=0.5, gentle=0.3,
                  solid_fn=solid_o, forbid=board - set(Ho))
        osurfs.append((ro.build(), Ho, y0))
    cliff = Rock(b, R, seed=seed + 8, colour=rock_colour, moss=0.18, cap_grass=0.95, rim_round=0.9,
                 ledge_cheese=0.45, forbid=road | set(HT), solid_fn=solid_for_rock)
    rsurf = cliff.build()
    for course in range(TOP_C + 1):
        for j in range(1, 4):
            layer = {c for c, e in road_extra.items() if e >= j and road_course.get(c, 0) == course}
            for (x, z, w, d) in pack(layer, PLATES, maxsize=8):
                put_rect(b, PLATES, DTAN, x, z, w, d, 4 * course + j - 1)
    hill_road = {c for c, h in RH.items() if h >= 1}
    if road_style == "rough":
        rough_stones(b, rng, hill_road, lambda c: RH[c], seed=seed + 11)
    else:
        for c in sorted(hill_road):
            if rng.random() < 0.07:
                b.put(rng.choice(["6141", "98138", "3070b"]), pick(rng, ((LBG, 2), (DBG, 1), (TAN, 1.5))), c[0], RH[c], c[1])
    b.step()
    flat = {c for c in road if RH.get(c, 0) == 0}
    occ, psurf = set(), {}
    if flat:
        occ, psurf = sunken_path(b, rng, flat, road_style, board=board - set(HT) - set(R) - road, seed=seed + 9)
    occupied = set(HT) | set(R) | road | occ | taken_out
    pb = board if plant_board is None else (set(plant_board) & board)
    if plants:
        dress(b, rng, rsurf, R, board=pb - road - set(HT) - occ, foot=0.3, ledge=0.05, speck=0.01, rim=0.3)
        for so, Ho, y0 in osurfs:
            dress(b, rng, so, Ho, board=set(), foot=0, ledge=0.06, speck=0.02, rim=0.4)
        for c, h in sorted(tsurf.items()):
            if h is None or c in road or c in taken_out:
                continue
            edge = any(HT.get(nbr(c, d), 0) < HT.get(c, 0) for d in DIRS)
            near_road = any((c[0] + i, c[1] + j) in road for i in (-1, 0, 1) for j in (-1, 0, 1))
            if edge and not near_road and rng.random() < 0.18:
                tuft(b, rng, c[0], c[1], h, pick(rng, [("leaf", 4), ("tabs", 2), ("big", 1.5), ("flower", 1)]))
            elif rng.random() < 0.01:
                tuft(b, rng, c[0], c[1], h, "speck")
        foot = ({nbr(c, d) for c in HT for d in DIRS} - occupied) & pb
        for c in sorted(foot):
            if rng.random() < 0.2:
                tuft(b, rng, c[0], c[1], 0)
    return {"terraces": HT, "rock": R, "road": road, "road_h": RH, "occupied": occupied,
            "tsurf": tsurf, "rsurf": rsurf, "top": 4 * TOP_C, "verge": occ - road}
