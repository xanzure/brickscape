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


_RGB = None


def rgb(code):
    """LDraw colour code -> (r, g, b) from LDConfig.ldr."""
    global _RGB
    if _RGB is None:
        import os, re
        from brickscape.config import LDRAW
        _RGB = {}
        for line in open(os.path.join(LDRAW, "LDConfig.ldr"), errors="ignore"):
            m = re.match(r"0 !COLOUR (\S+)\s+CODE\s+(\d+)\s+VALUE\s+#([0-9A-Fa-f]{6})", line)
            if m:
                h = m.group(3)
                _RGB[int(m.group(2))] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), "ALPHA" in line)
    return _RGB.get(int(code))


def _lab(c):
    """sRGB (0-255) -> CIE L*a*b*."""
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in c[:3])
    X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.9505
    Y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.089
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return (116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z)))


def nearest_colour(src, part, code):
    """The colour closest to `code` that the part exists in at this source (same transparency),
    or None if the source knows no colours for the part."""
    r = src.resolve(part)
    cols = src.colours(r) if r else None
    if not cols:
        return None
    if int(code) in cols:
        return int(code)
    c0 = rgb(code)
    if c0 is None:
        return None
    L0 = _lab(c0)
    best, bd = None, 1e9
    for c in cols:
        c1 = rgb(c)
        if c1 is None or c1[3] != c0[3]:
            continue
        L1 = _lab(c1)
        d = sum((a - b) ** 2 for a, b in zip(L0, L1)) ** 0.5
        ch0, ch1 = (L0[1] ** 2 + L0[2] ** 2) ** 0.5, (L1[1] ** 2 + L1[2] ** 2) ** 0.5
        if ch0 > 15 and ch1 < 10:
            d += 40                       # a coloured part should stay coloured, not go grey/black
        if d < bd:
            best, bd = c, d
    return best


def fix_colours(b, source=None):
    """Recolour parts whose colour doesn't exist for them at the source to the nearest one that
    does. -> {"part/old": new}."""
    src = get(source)
    out = {}
    for i, p in enumerate(b.pieces):
        if i in b.roots:
            continue
        n = nearest_colour(src, p.part, p.color)
        if n is not None and n != p.color:
            out[f"{p.part}/{p.color}"] = n
            p.color = n
    return out
