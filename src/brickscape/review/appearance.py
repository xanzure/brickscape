"""Appearance metrics that numbers CAN catch (the art-director review does the rest).

- hidden_visible: parts in the hidden colour that can be seen from outside (should be 0)
- plant_density: plants per stud overall, and on water / path cells (keep plants off
  water, crossings and path edges)
- marker: magenta (planning marker) parts present (fine in layouts, never in terrain)
- efficiency: parts per covered stud, share of 1x1 parts
- colours: distinct colours, and the share of the top 3
"""
import collections
from brickscape.core.brick import from_ldr, info
MARKER = 26  # magenta: planning marker colour

PLANT_WORDS = ("plant", "leaves", "leaf", "flower", "grass", "vine", "stem", "bush")
WATER = {1, 33, 41, 43, 47, 322}           # blue, trans blues/clear, medium azure
PATH = {28, 19}                            # dark tan, tan


def metrics(path_or_build, hidden=71):
    b = from_ldr(path_or_build) if isinstance(path_or_build, str) else path_or_build
    plants, top, cells = [], {}, set()
    colours = collections.Counter()
    ones = 0
    n = 0
    marker = 0
    for i, p in enumerate(b.pieces):
        if i in b.roots:
            continue
        n += 1
        d = info(p.part)["desc"].lower()
        colours[p.color] += 1
        if p.color == MARKER:
            marker += 1
        x = int(((p.lo[0] + p.hi[0]) / 2 + b.W * 10) // 20)
        z = int(((p.lo[2] + p.hi[2]) / 2 + b.D * 10) // 20)
        if any(w in d for w in PLANT_WORDS):
            plants.append((x, z))
            continue
        if " 1 x  1" in d or "1 x 1" in d:
            ones += 1
        x0 = int(round((p.lo[0] + b.W * 10) / 20)); x1 = int(round((p.hi[0] + b.W * 10) / 20))
        z0 = int(round((p.lo[2] + b.D * 10) / 20)); z1 = int(round((p.hi[2] + b.D * 10) / 20))
        y = -p.lo[1]
        for cx in range(x0, x1):
            for cz in range(z0, z1):
                cells.add((cx, cz))
                if y >= top.get((cx, cz), (-1, None))[0]:
                    top[(cx, cz)] = (y, p.color)
    water = {c for c, (y, col) in top.items() if col in WATER}
    path = {c for c, (y, col) in top.items() if col in PATH}
    near = lambda c, S: any((c[0] + dx, c[1] + dz) in S for dx in (-1, 0, 1) for dz in (-1, 0, 1))
    on_water = sum(1 for c in plants if near(c, water))
    on_path = sum(1 for c in plants if c in path)
    tot = sum(colours.values()) or 1
    return {
        "parts": n, "covered_studs": len(cells), "parts_per_stud": round(n / max(1, len(cells)), 2),
        "share_1x1": round(ones / max(1, n), 2),
        "plants": len(plants), "plants_per_100_studs": round(100 * len(plants) / max(1, b.W * b.D), 1),
        "plants_on_or_by_water": on_water, "plants_on_paths": on_path,
        "marker_parts": marker, "colours": len(colours),
        "top3_colour_share": round(sum(v for _, v in colours.most_common(3)) / tot, 2),
    }


def flags(m):
    out = []
    if m["plants"] and m["plants_on_or_by_water"] > 0.3 * m["plants"]:
        out.append(f"{m['plants_on_or_by_water']} of {m['plants']} plants sit on/next to water: thin them so the water reads")
    if m["plants_on_paths"]:
        out.append(f"{m['plants_on_paths']} plants stand on path cells")
    if m["plants_per_100_studs"] > 6:
        out.append(f"plant density {m['plants_per_100_studs']}/100 studs is high (subject may be hidden)")
    if m.get("hanging_pieces"):
        out.append(f"{m['hanging_pieces']} pieces hang their bottom over air: overhangs must be inverted slopes (hard rule)")
    if m["share_1x1"] > 0.45:
        out.append(f"{int(m['share_1x1'] * 100)}% of parts are 1x1: consider larger parts where hidden (cost/part count)")
    return out


def hanging(path_or_build):
    """Pieces whose bottom hangs over air (style rule: overhangs only as INVERTED slopes).
    A bottom cell is supported if the cell directly below is occupied up to this piece's bottom.
    The sloped (stud-less) cells of a normal slope only count as occupied up to their lowest
    plate, so a piece resting on a slope's sloped face counts as hanging. Exempt: inverted slopes,
    plants / soft parts, pieces on the baseplate. -> [(index, part, hanging cells)]"""
    from brickscape.core.brick import _apply
    b = from_ldr(path_or_build) if isinstance(path_or_build, str) else path_or_build
    top = {}                       # (x, z) cell -> sorted list of (bottom plate, top plate) solids
    occ = collections.defaultdict(list)
    cell = lambda v, n: int(round((v + n * 10) / 20))
    for i, p in enumerate(b.pieces):
        if i in b.roots or p.soft or p.free:
            continue
        d = info(p.part)["desc"].lower()
        x0, x1 = cell(p.lo[0], b.W), cell(p.hi[0], b.W)
        z0, z1 = cell(p.lo[2], b.D), cell(p.hi[2], b.D)
        y0, y1 = int(round(-p.hi[1] / 8)), int(round(-p.lo[1] / 8))
        stud_cells = set()
        for s, _ in b._studs(p):
            stud_cells.add((int((s[0] + b.W * 10) // 20), int((s[2] + b.D * 10) // 20)))
        sloped = "slope" in d and "inverted" not in d
        for x in range(x0, x1):
            for z in range(z0, z1):
                hi = y1 if (not sloped or (x, z) in stud_cells) else y0 + 1
                occ[(x, z)].append((y0, hi))
    out = []
    for i, p in enumerate(b.pieces):
        if i in b.roots or p.soft or p.free:
            continue
        d = info(p.part)["desc"].lower()
        if "inverted" in d:
            continue
        y0 = int(round(-p.hi[1] / 8))
        if y0 <= 0:
            continue
        x0, x1 = cell(p.lo[0], b.W), cell(p.hi[0], b.W)
        z0, z1 = cell(p.lo[2], b.D), cell(p.hi[2], b.D)
        bad = [(x, z) for x in range(x0, x1) for z in range(z0, z1)
               if not any(a < y0 <= h for a, h in occ.get((x, z), ()))]
        if bad:
            out.append((i, p.part, bad))
    return out
