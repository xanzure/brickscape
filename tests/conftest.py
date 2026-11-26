import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from brickscape.config import LDRAW


def pytest_collection_modifyitems(config, items):
    if not os.path.isdir(os.path.join(LDRAW, "parts")):
        skip = pytest.mark.skip(reason="LDraw library not installed (run `brickscape setup`)")
        for it in items:
            it.add_marker(skip)
