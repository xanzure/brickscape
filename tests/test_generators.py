import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from brickscape.core import snaps

pytestmark = pytest.mark.skipif(not snaps.available(), reason="connection data not installed")


def names():
    from gen_audit import GENS
    return list(GENS)


@pytest.mark.parametrize("name", names())
def test_generator_is_buildable(name):
    from gen_audit import audit
    a = audit(name)
    assert not a["coll"] and not a["loose"], a
    assert a["pieces"] >= 1
