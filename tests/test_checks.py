import pytest
from brickscape.core.brick import Build
from brickscape.core import geom, snaps
from brickscape.validate import validate

W = lambda p: geom.world_boxes(p.part, p.M)
needs_snaps = pytest.mark.skipif(not snaps.available(), reason="connection data not installed")


def board():
    b = Build("t", 8, 8)
    b.put("41539", 2, 0, -1, 0)         # 8x8 plate as the base, top at y = 0
    b.roots.add(0)
    return b


def test_stacked_bricks_do_not_collide():
    b = board()
    a, c = b.put("3001", 4, 0, 0, 0), b.put("3001", 1, 0, 3, 0)
    assert not geom.collide(W(a), W(c))


def test_overlapping_bricks_collide():
    b = board()
    a, c = b.put("3001", 4, 0, 0, 0), b.put("3001", 1, 1, 0, 0)
    assert geom.collide(W(a), W(c))


def test_half_stud_offset_plate_collides_with_studs():
    b = board()
    a, c = b.put("3001", 4, 3, 0, 3), b.put("3022", 1, 3.5, 3, 3)
    assert geom.collide(W(a), W(c))


def test_plate_in_slope_cavity_collides():
    b = board()
    s, p = b.put("3040b", 4, 0, 0, 0), b.put("3024", 1, 0, 0, 0)
    assert geom.collide(W(s), W(p))


@needs_snaps
def test_valid_stack_passes():
    b = board()
    b.put("3001", 4, 0, 0, 0)
    b.put("3020", 1, 1, 3, 0)
    b.put("3040b", 2, 2, 4, 0)
    r = validate(b, source=None)
    assert all(not v for v in r["checks"].values()), r


@needs_snaps
def test_floating_part_is_reported():
    b = board()
    b.put("3001", 4, 0, 0, 0)
    b.put("3005", 1, 5, 4, 5)           # in mid air
    r = validate(b, source=None)
    assert r["checks"]["not_connected"] == ["3005#2"]


@needs_snaps
def test_hinge_pair_connects():
    from brickscape.validate import connections
    b = Build("t", 8, 8)                # matrices from a real model, top tilted ~24 degrees
    b.raw("3937", 72, (50, -64, 40, 0, 0, 1, 0, 1, 0, -1, 0, 0))
    b.raw("6134", 71, (45.96352, -63.14967, 40.00086, 0, 0.403551, -0.914962, 0, 0.914962, 0.403544, 1, 0, 0))
    edges, _ = connections(b)
    assert list(edges.values()) == ["hinge"]
