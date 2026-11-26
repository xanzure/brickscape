"""Analyse a reference LDraw model (e.g. model.ldr extracted from a Studio .io).

python3 -I tools/analyze_ref.py path/to/model.ldr [--json out.json]

Flattens MPD sub-models, then reports part/category/colour mix, how much is
built sideways or at an angle, density per stud, hollowness, and what the
visible top surface is made of.
"""
import sys, os, re, collections, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from brickscape.core.brick import info, _mul, _apply, _dir, _find

CATS = [("plant", r"plant|leaves|leaf|flower|grass|vine|bamboo|tree|stem|bush|palm"),
        ("slope-inverted", r"slope.*inverted|inverted.*slope"),
        ("slope-curved", r"slope.*curved|curved.*slope|slope brick curved"),
        ("slope", r"slope"),
        ("wedge", r"wedge|wing"),
        ("tile", r"^tile"),
        ("plate-round", r"^plate.*round|^plate\s+\d+ x\s+\d+ round"),
        ("plate", r"^plate"),
        ("brick-round", r"^brick.*round|cylinder|cone|dish"),
        ("brick-side-studs", r"studs? on (\d+ )?sides?|headlight|stud on 1 side"),
        ("bracket", r"bracket"),
        ("brick", r"^brick"),
        ("hinge/clip/bar", r"hinge|clip|bar |bar$|handle|ball|socket|joint"),
        ("technic", r"technic"),
        ("baseplate", r"baseplate"),
        ("minifig/animal", r"minifig|animal|torso|legs|head|hips"),
        ("rock", r"rock")]


def category(desc):
    d = desc.lower().lstrip("~=_")
    for name, pat in CATS:
        if re.search(pat, d):
            return name
    return "other"


def load(path):
    """-> list of (part, colour, matrix) with sub-models flattened."""
    text = open(path, encoding="utf-8-sig", errors="ignore").read().splitlines()
    files, cur, order = {}, None, []
    for line in text:
        t = line.strip().split()
        if t[:2] == ["0", "FILE"]:
            cur = line.strip()[7:].strip().lower()
            files[cur] = []
            order.append(cur)
            continue
        if cur is None:
            cur = "__main__"
            files[cur] = []
            order.append(cur)
        files[cur].append(line)
    out, missing = [], collections.Counter()

    def walk(name, M, colour, depth):
        for line in files[name]:
            t = line.split()
            if t[:1] != ["1"] or len(t) < 15:
                continue
            c = int(t[1]) if t[1].isdigit() else 16
            c = colour if c == 16 else c
            m = tuple(map(float, t[2:14]))
            ref = " ".join(line.split()[14:]).lower()
            W = _mul(M, m)
            if ref in files and depth < 30:
                walk(ref, W, c, depth + 1)
            else:
                part = ref[:-4] if ref.endswith(".dat") else ref
                if _find(part + ".dat") is None:
                    missing[part] += 1
                    continue
                out.append((part, c, W))
    walk(order[0], (0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1), 16, 0)
    return out, missing


def analyse(path):
    parts, missing = load(path)
    descs = {}
    cat = collections.Counter()
    col = collections.Counter()
    pc = collections.Counter()
    sideways = angled = 0
    boxes = []
    for part, c, M in parts:
        try:
            inf = info(part)
        except Exception:
            missing[part] += 1
            continue
        descs[part] = inf["desc"]
        k = category(inf["desc"])
        if k == "baseplate":
            continue
        cat[k] += 1
        col[c] += 1
        pc[part] += 1
        up = _dir(M, (0, -1, 0))
        if abs(up[1] + 1) > 1e-3:
            sideways += 1
        a = M[3:]
        if any(1e-3 < abs(v) < 0.999 for v in a):
            angled += 1
        lo, hi = inf["lo"], inf["hi"]
        cs = [_apply(M, (x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        boxes.append((part, c, k, [min(p[i] for p in cs) for i in range(3)], [max(p[i] for p in cs) for i in range(3)]))
    n = sum(cat.values())
    if not boxes:
        return {"parts": 0, "missing": dict(missing)}
    X0 = min(b[3][0] for b in boxes); X1 = max(b[4][0] for b in boxes)
    Z0 = min(b[3][2] for b in boxes); Z1 = max(b[4][2] for b in boxes)
    Ytop = min(b[3][1] for b in boxes); Ybot = max(b[4][1] for b in boxes)
    # top surface + volume on a stud x plate grid (bounding boxes, so approximate)
    top = {}
    occ = set()
    for part, c, k, lo, hi in boxes:
        if k in ("plant", "minifig/animal"):
            continue
        for x in range(int((lo[0] - X0) // 20), int(math.ceil((hi[0] - X0) / 20))):
            for z in range(int((lo[2] - Z0) // 20), int(math.ceil((hi[2] - Z0) / 20))):
                cx, cz = X0 + 20 * x + 10, Z0 + 20 * z + 10
                if not (lo[0] <= cx <= hi[0] and lo[2] <= cz <= hi[2]):
                    continue
                if (x, z) not in top or lo[1] < top[(x, z)][0]:
                    top[(x, z)] = (lo[1], k, c)
                for y in range(int(lo[1] // 8), int(math.ceil(hi[1] / 8))):
                    occ.add((x, z, y))
    under = 0
    for (x, z), (yt, k, c) in top.items():
        under += max(0, round((Ybot - yt) / 8))
    topcat = collections.Counter(v[1] for v in top.values())
    topcol = collections.Counter(v[2] for v in top.values())
    area = len(top)
    return {
        "file": path, "parts": n, "unique": len(pc),
        "footprint_studs": [round((X1 - X0) / 20), round((Z1 - Z0) / 20)],
        "height_plates": round((Ybot - Ytop) / 8),
        "covered_cells": area,
        "parts_per_covered_stud": round(n / max(area, 1), 2),
        "fill_ratio_under_surface": round(len(occ) / max(under, 1), 2),
        "sideways_pct": round(100 * sideways / max(n, 1), 1),
        "angled_pct": round(100 * angled / max(n, 1), 1),
        "categories": cat.most_common(),
        "colours": col.most_common(12),
        "top_surface_categories": topcat.most_common(8),
        "top_surface_colours": topcol.most_common(8),
        "top_parts": [(p, k_, descs[p][:40]) for p, k_ in pc.most_common(30)],
        "missing": dict(missing.most_common(15)),
    }


if __name__ == "__main__":
    r = analyse(sys.argv[1])
    if "--json" in sys.argv:
        json.dump(r, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
    for k, v in r.items():
        if isinstance(v, list) and len(v) > 8:
            print(f"{k}:")
            for row in v:
                print("    ", row)
        else:
            print(f"{k}: {v}")
