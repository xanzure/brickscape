"""Cliff / slope profile check (style rule: rock faces LEAN BACK as they rise; overhangs are rare
and small).

Each slice is split into separate faces where the line jumps back more than MAX_STEP studs
(a flat top between, e.g. a peak standing behind a plateau); every face is judged on its own.
For every slice along the face, find the face position at each brick level (the front-most
solid cell at that height). Real rock and good reference builds step back as they rise
(the top is behind the foot): 'batter'. We report per slice:
  batter     studs of set-back per brick of height (top vs bottom)
  overhang   largest amount a level sticks out in front of the level directly below (studs)
  zigzag     sum of forward moves going up (studs), i.e. how much the face goes back and forth
and flag slices that are vertical (batter < MIN_BATTER), overhang > MAX_OVERHANG, or zigzag
heavily. Faces checked: 'front' (viewer looks along +z) and 'left' (viewer looks along +x).
"""
import collections
from brickscape.core.brick import from_ldr

MIN_BATTER = 0.4          # studs per brick: below this the face reads as a vertical wall
GOOD_BATTER = (0.5, 1.2)  # Rock-Face reference cliff measures 0.89
MAX_BATTER = 1.6         # studs per brick: above this a face reads as a stepped hill, not a cliff
MAX_OVERHANG = 1          # studs
MAX_OVERHANG_SHARE = 0.2      # the Rock-Face reference: ~19 % of slices, all <= 1 stud
MAX_STEP = 3              # a set-back bigger than this is a flat top between two faces (e.g. a peak behind a plateau)
MIN_FACE_BRICKS = 2       # only faces at least this tall are judged
ROCK_COLOURS = {71, 72, 0, 8, 28, 19, 70, 378, 308}   # greys, black, sandstone/earth tones


def _grid(b, colours=None):
    """occ[(x, z)] = set of brick levels (y // 3) that hold solid rock-coloured parts."""
    occ = collections.defaultdict(set)
    for i, p in enumerate(b.pieces):
        if i in b.roots or p.soft or p.free:
            continue
        if colours and p.color not in colours:
            continue
        x0 = int(round((p.lo[0] + b.W * 10) / 20)); x1 = int(round((p.hi[0] + b.W * 10) / 20))
        z0 = int(round((p.lo[2] + b.D * 10) / 20)); z1 = int(round((p.hi[2] + b.D * 10) / 20))
        y0 = int(round(-p.hi[1] / 8)); y1 = int(round(-p.lo[1] / 8))
        for x in range(x0, x1):
            for z in range(z0, z1):
                for y in range(max(0, y0), y1):
                    occ[(x, z)].add(y // 3)
    return occ


def face_profiles(b, face="front", colours=ROCK_COLOURS):
    """{slice index: [face position per brick level, bottom -> top]} (None where empty)."""
    occ = _grid(b, colours)
    if not occ:
        return {}
    top = max(max(v) for v in occ.values())
    prof = {}
    n_slices = b.W if face == "front" else b.D
    depth = b.D if face == "front" else b.W
    for s in range(n_slices):
        col = []
        for lvl in range(top + 1):
            pos = None
            for d in range(depth):
                cell = (s, d) if face == "front" else (d, s)
                if lvl in occ.get(cell, ()):
                    pos = d
                    break
            col.append(pos)
        while col and col[-1] is None:
            col.pop()
        prof[s] = col
    return prof


def analyse(path_or_build, faces=("front", "left"), colours=ROCK_COLOURS):
    b = from_ldr(path_or_build) if isinstance(path_or_build, str) else path_or_build
    report = {}
    for face in faces:
        rows = []
        for s, col in face_profiles(b, face, colours).items():
            levels = [(l, p) for l, p in enumerate(col) if p is not None]
            # split into separate faces where the line jumps back more than MAX_STEP studs
            segs, cur = [], levels[:1]
            for a_, b_ in zip(levels, levels[1:]):
                if b_[1] - a_[1] > MAX_STEP or b_[0] - a_[0] > 1:
                    segs.append(cur); cur = []
                cur.append(b_)
            segs.append(cur)
            for k, seg in enumerate(segs):
                if len(seg) < MIN_FACE_BRICKS + 1:
                    continue
                (l0, p0), (l1, p1) = seg[0], seg[-1]
                span = l1 - l0
                over = zig = 0
                for (la, pa), (lb, pb) in zip(seg, seg[1:]):
                    if pb < pa:
                        zig += pa - pb
                    over = max(over, pa - pb)      # sticks out past the level directly below
                rows.append({"slice": s, "face": k, "from_level": l0, "height_bricks": span + 1, "foot": p0,
                             "top": p1, "batter": round((p1 - p0) / span, 2), "overhang": over, "zigzag": zig})
        if not rows:
            report[face] = {"slices": 0}
            continue
        vertical = [r for r in rows if r["batter"] < MIN_BATTER]
        overhung = [r for r in rows if r["overhang"] > MAX_OVERHANG]
        any_over = [r for r in rows if r["overhang"] > 0]
        zigzag = [r for r in rows if r["zigzag"] > r["height_bricks"] * 0.5]
        mean = sum(r["batter"] for r in rows) / len(rows)
        flags = []
        if len(vertical) > 0.3 * len(rows):
            flags.append(f"{len(vertical)}/{len(rows)} slices are near-vertical (batter < {MIN_BATTER} stud/brick): "
                         f"make the face step back as it rises (target {GOOD_BATTER[0]}-{GOOD_BATTER[1]})")
        if mean > MAX_BATTER:
            flags.append(f"mean batter {mean:.2f} > {MAX_BATTER}: reads as a stepped hill; make tiers taller or shallower")
        if overhung:
            flags.append(f"{len(overhung)} slices overhang by more than {MAX_OVERHANG} stud: "
                         f"slices {[r['slice'] for r in overhung][:12]}")
        if len(any_over) > MAX_OVERHANG_SHARE * len(rows):
            flags.append(f"{len(any_over)}/{len(rows)} slices overhang at all (max {int(MAX_OVERHANG_SHARE * 100)}%)")
        if len(zigzag) > 0.25 * len(rows):
            flags.append(f"{len(zigzag)}/{len(rows)} slices zig-zag in and out: keep the face moving one way (back)")
        report[face] = {"slices": len(rows), "mean_batter": round(mean, 2), "vertical": len(vertical),
                        "overhanging": len(any_over), "big_overhang": len(overhung), "zigzag": len(zigzag),
                        "flags": flags, "rows": rows}
    return report


def summary(report):
    out = []
    for face, r in report.items():
        if not r.get("slices"):
            out.append(f"{face}: no rock face tall enough to judge")
            continue
        out.append(f"{face}: {r['slices']} slices, mean batter {r['mean_batter']} stud/brick, "
                   f"{r['vertical']} vertical, {r['overhanging']} overhanging ({r['big_overhang']} > {MAX_OVERHANG}), "
                   f"{r['zigzag']} zig-zag")
        out += ["  ! " + f for f in r["flags"]] or ["  ok"]
    return "\n".join(out)
