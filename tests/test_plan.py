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
    assert len(b.roots) > 1 and r["pieces"] == 0


def test_unknown_op_names_the_op():
    from brickscape.plan import compile_plan, PlanError
    with pytest.raises(PlanError, match="op 0"):
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
