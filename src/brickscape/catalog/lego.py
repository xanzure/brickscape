"""Official LEGO parts, from Rebrickable's CSV downloads (https://rebrickable.com/downloads/).

`brickscape setup` downloads parts.csv.gz, colors.csv.gz and elements.csv.gz into
BRICKSCAPE_DATA/rebrickable. A part/colour pair counts as real when LEGO produced an element
for it. Rebrickable colour ids follow LDraw colour codes only for the basic colours (olive
green, the trans blues and others differ), so colours are matched by name against the LDraw
library's LDConfig.ldr.
"""
import csv, gzip, os, re, urllib.request
from brickscape.config import DATA, LDRAW
from brickscape.catalog import Source, candidates

URL = "https://cdn.rebrickable.com/media/downloads/{}.csv.gz"
FILES = ("parts", "colors", "elements")
DIR = os.path.join(DATA, "rebrickable")


def _norm(n):
    n = n.lower().replace("gray", "grey").replace("_", " ").replace("-", " ")
    n = n.replace("lt ", "light ").replace("dk ", "dark ")
    return re.sub(r"[^a-z0-9]", "", n)


def colour_map():
    """Rebrickable colour id -> LDraw colour code (by name; unmatched exotic colours dropped)."""
    ld = {}
    for line in open(os.path.join(LDRAW, "LDConfig.ldr"), errors="ignore"):
        m = re.match(r"0 !COLOUR (\S+)\s+CODE\s+(\d+)", line)
        if m:
            ld[_norm(m.group(1))] = int(m.group(2))
    return {int(r["id"]): ld[_norm(r["name"])] for r in _rows("colors") if _norm(r["name"]) in ld}


def download(force=False):
    os.makedirs(DIR, exist_ok=True)
    for f in FILES:
        out = os.path.join(DIR, f + ".csv.gz")
        if os.path.exists(out) and not force:
            continue
        req = urllib.request.Request(URL.format(f), headers={"User-Agent": "brickscape"})
        with urllib.request.urlopen(req, timeout=120) as r, open(out, "wb") as w:
            w.write(r.read())
    return DIR


def _rows(name):
    path = os.path.join(DIR, name + ".csv.gz")
    if not os.path.exists(path):
        raise RuntimeError(f"official LEGO part data missing ({path}): run `brickscape setup`")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        yield from csv.DictReader(f)


class Lego(Source):
    name = "lego"

    def __init__(self):
        self.parts = {r["part_num"].lower(): r["name"] for r in _rows("parts")}
        self.cols, cmap = {}, colour_map()
        for r in _rows("elements"):
            c = cmap.get(int(r["color_id"]))
            if c is not None:
                self.cols.setdefault(r["part_num"].lower(), set()).add(c)

    def resolve(self, part):
        for c in candidates(part):
            if c in self.parts:
                return c
        return None

    def colours(self, part):
        return self.cols.get(part)
