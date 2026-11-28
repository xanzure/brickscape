import json, os, zipfile
import pytest
from brickscape.core import snaps

pytestmark = pytest.mark.skipif(not snaps.available(), reason="connection data not installed")


def build(plan):
    from brickscape.plan import compile_plan
    from brickscape.validate import validate, repair
    b, c = compile_plan(plan)
    repair(b)
    return b, validate(b, source=None)


def test_small_plan_is_valid():
    b, r = build({"name": "t", "board": {"width": 16, "depth": 16}, "ops": [
        {"op": "block", "area": {"rect": [2, 2, 8, 7]}, "height": 4},
        {"op": "boulder", "at": [[10, 3, 4]]},
        {"op": "tree", "kind": "oak", "size": "small", "at": [11, 11]}]})
    assert r["pieces"] > 20
    assert not any(r["checks"].values()), r["checks"]


def test_odd_board_gets_plate_floor():
    b, r = build({"name": "t", "board": {"width": 20, "depth": 20}, "ops": []})
    assert len(b.roots) > 1 and r["pieces"] > 0          # bottom layer = ground, top layer locks it
    assert not any(r["checks"].values()), r["checks"]


def test_unknown_op_names_the_op():
    from brickscape.plan import compile_plan, PlanError
    with pytest.raises(PlanError, match=r"ops\.0.*does not match"):
        compile_plan({"ops": [{"op": "castle"}]})


def test_io_roundtrip(tmp_path):
    from brickscape.io.export import write_io
    ldr = tmp_path / "m.ldr"
    ldr.write_text("0 m\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
    out = write_io(str(ldr), str(tmp_path / "m.io"))
    z = zipfile.ZipFile(out)
    z.setpassword(b"soho0909")
    assert b"3001.dat" in z.read("model.ldr")
    assert json.loads(z.read(".info"))["total_parts"] == 1


def test_schema_rejects_bad_fields_with_location():
    from brickscape.plan import compile_plan, PlanError
    with pytest.raises(PlanError, match=r"ops\.0\.tree\.size"):
        compile_plan({"ops": [{"op": "tree", "at": [3, 3], "size": "huge"}]})
    with pytest.raises(PlanError, match="exactly one of"):
        compile_plan({"ops": [{"op": "block", "area": {"rect": [0, 0, 4, 4], "ellipse": [1, 1, 1, 1]}}]})
    with pytest.raises(PlanError, match="Extra inputs"):
        compile_plan({"ops": [{"op": "hill", "area": {"rect": [0, 0, 4, 4]}, "heigth": 4}]})


def test_examples_validate():
    import glob
    from brickscape.schema import parse
    for f in glob.glob(os.path.join(os.path.dirname(__file__), "..", "src", "brickscape", "examples", "*.json")):
        parse(open(f).read())


def test_nothing_sticks_out_past_the_board():
    from brickscape.validate import outside
    b, r = build({"name": "edge", "board": {"width": 16, "depth": 16}, "ops": [
        {"op": "tree", "kind": "oak", "size": "medium", "at": [1, 1]},
        {"op": "hill", "area": {"rect": [0, 8, 16, 16]}, "height": 12, "style": "rock"}]})
    assert not outside(b)
    assert not any(r["checks"].values()), r["checks"]


def test_waterfall_against_a_vertical_cliff():
    b, r = build({"name": "wf", "board": {"width": 16, "depth": 16}, "seed": 3, "ops": [
        {"op": "hill", "area": {"rect": [0, 4, 7, 16]}, "height": 24, "style": "rock", "falloff": 2, "lean": 0},
        {"op": "waterfall", "at": [9, 8], "width": 2, "depth": 2, "height": 18},
        {"op": "water", "points": [[10, 7], [11, 0]], "width": 3}]})
    assert not any(r["checks"].values()), r["checks"]
    trans = [p for p in b.pieces if p.color in (33, 43) and p.part in ("3004", "3005")]
    assert len(trans) >= 6                       # the column survived repair, in real trans colours
    assert min(-p.hi[1] for p in trans) < 1      # and it stands on the ground, not floating


def test_ops_claim_their_footprint():
    from brickscape.plan import Compiler
    from brickscape.schema import parse
    c = Compiler(parse({"board": {"width": 16, "depth": 16}, "ops": []}))
    s = len(c.b.pieces)
    c.op_block({"op": "block", "area": {"rect": [2, 2, 6, 6]}, "height": 3})
    assert {(3, 3), (5, 5)} <= c.footprint(s)
