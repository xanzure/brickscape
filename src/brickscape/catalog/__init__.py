"""Part sources: which parts and colours exist and can be bought.

  lego      official LEGO (default): part/colour pairs LEGO has actually produced, from
            Rebrickable's free CSV downloads (elements.csv), cached in BRICKSCAPE_DATA.
  gobricks  GoBricks / Brickwith moulds, colours and prices.

get(name) -> Source with: resolve(part) -> catalog id or None, colours(part) -> set of LDraw
colour codes (None = unknown), price(part) -> USD or None, substitute(part) -> part or None.
"""
from brickscape.config import SOURCE

# LDraw files that are the same mould under another number (suffix variants)
ALIASES = {"3040": "3040b", "3023": "3023b", "6141": "4073", "4073": "6141", "3062": "3062b",
           "3665": "3665a", "4460": "4460b", "3794": "15573", "3794b": "15573", "3069": "3069b",
           "3068": "3068b", "3070": "3070b", "2654": "2654a", "4032": "4032a", "3741": "3741a",
           "4287": "4287a", "4460a": "4460b", "3678a": "3678b", "3684": "3684c", "3684a": "3684c",
           "3040a": "3040b"}


def candidates(part):
    p = part.lower()
    out = [p, ALIASES.get(p, ""), p.rstrip("abcd"), p + "b", p + "a"]
    seen = []
    for c in out:
        if c and c not in seen:
            seen.append(c)
    return seen


class Source:
    name = "base"

    def resolve(self, part):                 # pragma: no cover - interface
        raise NotImplementedError

    def colours(self, part):
        return None

    def price(self, part):
        return None

    def substitute(self, part):
        return None

    def check(self, counts):
        """counts: {(part, colour): n}. -> report dict used by validate and parts lists."""
        rep = {"source": self.name, "pieces": 0, "missing": {}, "bad_colour": {}, "substitutes": {},
               "cost_usd": None}
        cost, priced = 0.0, True
        for (p, c), n in counts.items():
            rep["pieces"] += n
            r = self.resolve(p)
            if not r:
                s = self.substitute(p)
                if s and self.resolve(s):
                    rep["substitutes"][p] = s
                    r = self.resolve(s)
                else:
                    rep["missing"][p] = rep["missing"].get(p, 0) + n
                    continue
            cols = self.colours(r)
            if cols is not None and int(c) not in cols:
                rep["bad_colour"][f"{p}/{c}"] = n
            pr = self.price(r)
            if pr is None:
                priced = False
            else:
                cost += pr * n
        rep["cost_usd"] = round(cost, 2) if priced else None
        return rep


_cache = {}


def get(name=None):
    name = (name or SOURCE).lower()
    if name not in _cache:
        if name == "lego":
            from brickscape.catalog.lego import Lego
            _cache[name] = Lego()
        elif name == "gobricks":
            from brickscape.catalog.gobricks import GoBricks
            _cache[name] = GoBricks()
        else:
            raise ValueError(f"unknown part source {name!r} (use 'lego' or 'gobricks')")
    return _cache[name]
