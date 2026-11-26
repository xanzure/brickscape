"""Run each generator alone on a small board through the strict checker.

    python tools/gen_audit.py [name ...]
"""
import os, random, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from brickscape.core.brick import Build
from brickscape.terrain import greenery as G
from brickscape.core import kit
from brickscape.validate import validate, connections, collisions, components

GENS = {
    "tuft": lambda b, r: [G.tuft(b, r, 2 + 3 * i, 2, kind=k) for i, k in enumerate(("grass", "twig", "spiky", "star", "fern", "leafy", "clover", "bigleaf"))],
    "flower": lambda b, r: G.flower(b, r, 4, 4),
    "stem_flowers": lambda b, r: G.stem_flowers(b, r, 4, 4),
    "flower_clump": lambda b, r: G.flower_clump(b, r, 4, 4),
    "snot_bush": lambda b, r: G.snot_bush(b, r, 6, 6),
    "wide_bush": lambda b, r: G.wide_bush(b, r, 6, 6),
    "cypress": lambda b, r: G.cypress(b, r, 6, 6),
    "fern_clump": lambda b, r: G.fern_clump(b, r, 6, 6),
    "big_leaf_plant": lambda b, r: G.big_leaf_plant(b, r, 6, 6),
    "sword_plant": lambda b, r: G.sword_plant(b, r, 6, 6),
    "bamboo": lambda b, r: G.bamboo(b, r, 6, 6),
    "pine": lambda b, r: G.pine(b, r, 6, 6),
    "birch": lambda b, r: G.birch(b, r, 6, 6),
    "palm": lambda b, r: G.palm(b, r, 6, 6),
    "cactus": lambda b, r: G.cactus(b, r, 6, 6),
    "oak_small": lambda b, r: G.oak2(b, r, 8, 8, size="small"),
    "oak_medium": lambda b, r: G.oak2(b, r, 8, 8, size="medium"),
    "oak_fat": lambda b, r: G.oak2(b, r, 8, 8, size="fat"),
    "tooth_rosette": lambda b, r: G.tooth_rosette(b, r, 6, 6),
    "plume_grass": lambda b, r: G.plume_grass(b, r, 6, 6),
    "swirl_topiary": lambda b, r: G.swirl_topiary(b, r, 6, 6),
    "coral_bush": lambda b, r: G.coral_bush(b, r, 6, 6),
    "curl_vine": lambda b, r: G.curl_vine(b, r, 6, 6),
    "crystal_succulent": lambda b, r: G.crystal_succulent(b, r, 6, 6),
    "boulder": lambda b, r: [kit.boulder(b, r, 1 + 7 * i, 4, size=s) for i, s in enumerate((1, 2, 4))],
}


def audit(name, seed=1, verbose=False):
    b = Build(name, 32, 32)
    b.base(0, 0)
    rng = random.Random(seed)
    GENS[name](b, rng)
    from brickscape.validate import repair
    n0 = len(b.pieces)
    gone = repair(b)
    r = validate(b, source="lego")
    r["removed"] = len(gone)
    c = r["checks"]
    P = b.pieces
    pairs = collections.Counter(tuple(sorted(s.split(" x ")[k].split("#")[0] for k in (0, 1))) for s in c["collisions"])
    loose = collections.Counter(s.split("#")[0] for s in c["not_connected"])
    return {"pieces": r["pieces"], "removed": r["removed"], "coll": dict(pairs.most_common(4)), "loose": dict(loose.most_common(5)),
            "colour": r["source"]["bad_colour"], "missing": r["source"]["missing"]}


if __name__ == "__main__":
    names = sys.argv[1:] or list(GENS)
    for n in names:
        try:
            a = audit(n)
            ok = not a["coll"] and not a["loose"]
            print(f"{'OK  ' if ok else 'FAIL'} {n:18s} {a['pieces']:4d}p -{a['removed']} coll={a['coll']} loose={a['loose']} colour={a['colour']} missing={a['missing']}")
        except Exception as e:
            print(f"ERR  {n:18s} {type(e).__name__}: {e}")
