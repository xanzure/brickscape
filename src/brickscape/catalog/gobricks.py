"""GoBricks (brickwith.com) catalog: what we can actually buy.

Files (catalog/):
  gobricks_parts.csv/.json : every GoBricks part (1721): GDS code, LDraw id, name, category,
                             number of colours, min/max price (USD), popularity
  gobricks_colours.json    : GoBricks colour id -> LDraw colour id, name, hex
  gobricks_part_colours.json: cache {ldraw part: [LDraw colour ids available]} (fetched per part)

Usage:
  python3 -I tools/catalog.py check model.ldr   # what's buyable, cost estimate, substitutes
  python3 -I tools/catalog.py fetch 3024 3005   # fill the colour cache for parts (1 s apart)
"""
import os, sys, json, re, time, subprocess, collections
from brickscape.config import DATA
from brickscape.catalog import Source, candidates
CAT = os.path.join(DATA, "gobricks")
BASE = "https://www.brickwith.com/en/parts/x/{}"

# LDraw parts that are the same mould under another number (old/new suffixes, variants)
ALIASES = {"3040": "3040b", "3023": "3023b", "6141": "4073", "4073": "6141", "3062": "3062b",
           "3665": "3665a", "60481": "60481", "4460": "4460b", "3794": "15573", "3794b": "15573",
           "3069": "3069b", "3068": "3068b", "3070": "3070b", "2654": "2654a", "4032": "4032a",
           "3741": "3741a", "4287": "4287a", "4460a": "4460b", "3678a": "3678b", "3684": "3684c",
           "3684a": "3684c", "3040a": "3040b", "60481a": "60481a"}
# not sold: nearest GoBricks part with the same look/role (used by check() as a suggestion)
SUBSTITUTE = {"2339": "76768",      # Arch 1x5x4 -> Arch 1x5x4 irregular bow
              "4589": "59900",      # Cone 1x1 -> Cone 1x1 with top groove
              "92947": "3941",      # Round 2x2 with grille -> Round 2x2 with axle hole
              "87620": None,        # Brick 2x2 facet: not sold (use 2x2 corner bricks / slopes)
              "4150": "14769", "85861": "4073", "26601": "2450", "11212": "3031"}


def _load(name, default):
    p = os.path.join(CAT, name)
    return json.load(open(p)) if os.path.exists(p) else default


def parts():
    rows = _load("gobricks_parts.json", [])
    by = {}
    for r in rows:
        if r["ldraw"]:
            by.setdefault(r["ldraw"].lower(), r)
    return by


def lookup(part, table=None):
    table = table or parts()
    p = part.lower()
    for cand in (p, ALIASES.get(p, ""), p.rstrip("abcd"), p + "b", p + "a"):
        if cand and cand in table:
            return table[cand]
    return None


def fetch_colours(ldraw_ids, delay=1.0):
    """Fetch the available colours of parts (one polite request per part) into the cache."""
    cache = _load("gobricks_part_colours.json", {})
    cols = _load("gobricks_colours.json", {})
    table = parts()
    for pid in ldraw_ids:
        r = lookup(pid, table)
        if not r or r["ldraw"] in cache:
            continue
        out = subprocess.run(["curl", "-s", "-H", "RSC: 1", BASE.format(r["ldraw"])],
                             capture_output=True, text=True).stdout
        for m in re.finditer(r'\{"color_id":"(\d+)","color_hex_value":"([^"]*)","ldraw_color_id":"([^"]*)"'
                             r'[^{}]*?"color_name":"([^"]*)"', out):
            cols[m.group(1)] = {"ldraw": m.group(3), "hex": m.group(2), "name": m.group(4)}
        skus = set(re.findall(r'"sku_code":"%s-(\d+)"' % re.escape(r["gobricks"]), out))
        cache[r["ldraw"]] = sorted({cols[c]["ldraw"] for c in skus if c in cols and cols[c]["ldraw"]},
                                   key=lambda v: int(v) if v.isdigit() else 0)
        print(f"  {r['ldraw']:8s} {len(cache[r['ldraw']])} colours", flush=True)
        json.dump(cache, open(os.path.join(CAT, "gobricks_part_colours.json"), "w"))   # save as we go
        json.dump(cols, open(os.path.join(CAT, "gobricks_colours.json"), "w"), indent=0)
        time.sleep(delay)
    json.dump(cache, open(os.path.join(CAT, "gobricks_part_colours.json"), "w"))
    json.dump(cols, open(os.path.join(CAT, "gobricks_colours.json"), "w"), indent=0)
    return cache


def check(ldr):
    """Part list of a model against the catalog: buyable?, colour available?, estimated cost."""
    table = parts()
    cache = _load("gobricks_part_colours.json", {})
    cnt = collections.Counter()
    for l in open(ldr):
        t = l.split()
        if t[:1] == ["1"]:
            cnt[(t[-1][:-4], t[1])] += 1
    total, missing, badcol, cost, subs = 0, collections.Counter(), collections.Counter(), 0.0, {}
    for (p, c), n in cnt.items():
        if p.lower() in ("3811",):
            continue
        total += n
        r = lookup(p, table)
        if not r and SUBSTITUTE.get(p):
            r = lookup(SUBSTITUTE[p], table)
            subs[p] = SUBSTITUTE[p]
        if not r:
            missing[p] += n
            continue
        cost += n * r["min_price"]
        avail = cache.get(r["ldraw"])
        if avail is not None and c not in avail:
            badcol[(p, c)] += n
    return {"pieces": total, "cost_usd": round(cost, 2), "not_sold": missing.most_common(),
            "colour_not_sold": badcol.most_common(), "lots": len(cnt), "substituted": subs}


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch_colours(sys.argv[2:])
    elif sys.argv[1] == "check":
        r = check(sys.argv[2])
        print(f"{r['pieces']} pieces, {r['lots']} part/colour lots, est. ${r['cost_usd']} at GoBricks min prices")
        print("not sold by GoBricks:", r["not_sold"][:30])
        print("substituted:", r["substituted"])
        print("colour not sold (only for parts in the colour cache):", r["colour_not_sold"][:30])


class GoBricks(Source):
    name = "gobricks"

    def __init__(self):
        self.table = parts()
        if not self.table:
            raise RuntimeError(f"GoBricks catalog missing ({CAT}/gobricks_parts.json)")
        self.cache = _load("gobricks_part_colours.json", {})

    def resolve(self, part):
        for c in candidates(part):
            if c in self.table:
                return self.table[c]["ldraw"]
        return None

    def colours(self, part):
        v = self.cache.get(part)
        return None if v is None else {int(c) for c in v}

    def price(self, part):
        r = self.table.get(part.lower())
        return r and r["min_price"]

    def substitute(self, part):
        return SUBSTITUTE.get(part)
