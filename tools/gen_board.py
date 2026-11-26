"""All greenery generators side by side on one board, for a visual check.

    python tools/gen_board.py OUT.ldr
"""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
from brickscape.core.brick import Build
from gen_audit import GENS

names = [n for n in GENS if n not in ("tuft", "boulder")]
b = Build("generators", 96, 32)
for i in range(3):
    b.base(32 * i, 0)
cols = 8
for k, n in enumerate(names):
    cx, cz = 6 + (k % cols) * 12, 6 + (k // cols) * 9
    sub = Build("x", 96, 32)
    rng = random.Random(k)
    import types
    # run each generator at its own spot by shifting its default coordinates
    g = GENS[n]
    class Shift:
        def __init__(s, b, dx, dz): s.b, s.dx, s.dz = b, dx, dz
    from brickscape.terrain import greenery as G
    fn = {"oak_small": lambda: G.oak(b, rng, cx, cz, size="small"),
          "oak_medium": lambda: G.oak(b, rng, cx, cz, size="medium"),
          "oak_fat": lambda: G.oak(b, rng, cx, cz, size="fat")}.get(n)
    if fn:
        fn()
    else:
        getattr(G, n)(b, rng, cx, cz)
b.write(sys.argv[1])
print(len(b.pieces), "pieces")
