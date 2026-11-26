"""Typed connection points of LDraw parts, from the LDCad shadow library.

The shadow library (https://github.com/RolandMelkert/LDCadShadowLibrary, CC BY-SA 4.0, by
Roland Melkert) adds !LDCAD SNAP_* meta lines to LDraw files: studs and anti-studs, bars and
bar holes, clips, hinge fingers, pins and axles. `brickscape setup` downloads it to
BRICKSCAPE_DATA/ldcad (it is not bundled).

A part's snaps are collected the way LDCad does it: walk the part's sub-file tree, take each
file's shadow metas in that file's frame, let SNAP_CLEAR drop what sub-files contributed and
SNAP_INCL pull in other shadow files. Every snap ends up in the part's own frame.

Parts with no shadow info at all fall back to the stud-grid rule (studs from the stud
primitives, anti-studs under the bottom face); the report says which parts did.
"""
import functools, glob, math, os, re
import numpy as np
from brickscape.config import DATA, LDRAW
from brickscape.core.brick import _find

SHADOW = os.path.join(DATA, "ldcad")
_KV = re.compile(r"\[(\w+)=([^\]]*)\]")


@functools.lru_cache(None)
def _shadow_root():
    hits = glob.glob(os.path.join(SHADOW, "*", "parts"))
    return os.path.dirname(hits[0]) if hits else None


URL = "https://github.com/RolandMelkert/LDCadShadowLibrary/archive/refs/heads/main.zip"


def download(force=False):
    import io, urllib.request, zipfile
    if available() and not force:
        return SHADOW
    os.makedirs(SHADOW, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "brickscape"})
    with urllib.request.urlopen(req, timeout=120) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(SHADOW)
    _shadow_root.cache_clear()
    return SHADOW


def available():
    return _shadow_root() is not None


def _shadow_path(ldraw_path):
    root = _shadow_root()
    if not root or not ldraw_path:
        return None
    rel = os.path.relpath(ldraw_path, LDRAW)
    p = os.path.join(root, rel)
    if os.path.exists(p):
        return p
    low = os.path.join(root, rel.lower())
    return low if os.path.exists(low) else None


def _vec(s, n):
    v = [float(x) for x in s.split()]
    return v if len(v) == n else None


class Snap:
    __slots__ = ("kind", "gender", "pos", "R", "id", "group", "secs", "caps", "center",
                 "radius", "length", "seq", "gofs", "bounding")

    def copy_to(self, M):
        """Snap in a parent frame: M is (R 3x3, t 3)."""
        R, t = M
        s = Snap()
        for k in Snap.__slots__:
            setattr(s, k, getattr(self, k))
        s.pos = R @ self.pos + t
        s.R = R @ self.R
        return s


def _grid(kv):
    g = kv.get("grid")
    if not g:
        return [np.zeros(3)]
    t = g.split()
    vals, i, cnt = [], 0, []
    while len(cnt) < 2:
        c = t[i] == "C"
        if c:
            i += 1
        cnt.append((c, int(float(t[i]))))
        i += 1
    sx, sz = float(t[i]), float(t[i + 1])
    out = []
    for ix in range(cnt[0][1]):
        for iz in range(cnt[1][1]):
            x = ix * sx - ((cnt[0][1] - 1) * sx / 2 if cnt[0][0] else 0)
            z = iz * sz - ((cnt[1][1] - 1) * sz / 2 if cnt[1][0] else 0)
            out.append(np.array([x, 0.0, z]))
    return out


def _parse_meta(kind, kv):
    pos = np.array(_vec(kv.get("pos", "0 0 0"), 3) or [0, 0, 0], float)
    o = _vec(kv.get("ori", "1 0 0 0 1 0 0 0 1"), 9) or [1, 0, 0, 0, 1, 0, 0, 0, 1]
    R = np.array(o, float).reshape(3, 3)
    out = []
    for g in _grid(kv):
        s = Snap()
        s.kind, s.id, s.group = kind, kv.get("id", "").lower(), kv.get("group", "").lower()
        s.pos, s.R = pos + R @ g, R
        s.gender = kv.get("gender", "M").upper()[:1]
        s.center = kv.get("center", "false").lower() == "true"
        s.caps = kv.get("caps", "one").lower()
        s.secs, s.radius, s.length, s.seq, s.gofs, s.bounding = [], 0.0, 0.0, [], "M", ""
        if kind == "cyl":
            t = kv.get("secs", "R 6 4").split()
            for i in range(0, len(t) - 2, 3):
                s.secs.append((t[i].upper(), float(t[i + 1]), float(t[i + 2])))
            s.length = sum(x[2] for x in s.secs)
            s.radius = max((x[1] for x in s.secs if x[0] in ("R", "A", "S")), default=0)
        elif kind == "clp":
            s.gender, s.radius, s.length = "F", float(kv.get("radius", 4)), float(kv.get("length", 8))
        elif kind == "fgr":
            s.seq = [float(x) for x in kv.get("seq", "").split()]
            s.length, s.radius = sum(s.seq), float(kv.get("radius", 4))
            s.gofs = kv.get("genderofs", "M").upper()[:1]
            s.center = True              # finger runs are always centred on pos in the library
        elif kind == "sph":
            s.radius = float(kv.get("radius", 4))
        elif kind == "gen":
            s.bounding = kv.get("bounding", "")
        out.append(s)
    return out


KINDS = {"SNAP_CYL": "cyl", "SNAP_CLP": "clp", "SNAP_FGR": "fgr", "SNAP_GEN": "gen", "SNAP_SPH": "sph"}


def _metas(path):
    """(clears, own snaps, includes) of one shadow file."""
    clears, own, incl = [], [], []
    if not path:
        return clears, own, incl
    for line in open(path, errors="ignore"):
        t = line.split(None, 3)
        if len(t) < 3 or t[0] != "0" or t[1] != "!LDCAD":
            continue
        kv = {k.lower(): v.strip() for k, v in _KV.findall(line)}
        if t[2] == "SNAP_CLEAR":
            clears.append(kv.get("id", "").lower())
        elif t[2] == "SNAP_INCL":
            incl.append(kv)
        elif t[2] in KINDS:
            own += _parse_meta(KINDS[t[2]], kv)
    return clears, own, incl


def _incl(kv):
    ref = kv.get("ref", "").replace("\\", "/")
    path = _shadow_path(_find(ref)) if _find(ref) else None
    if not path:
        root = _shadow_root()
        for d in ("parts", "p", "parts/s"):
            c = os.path.join(root, d, ref)
            if os.path.exists(c):
                path = c
                break
    if not path:
        return []
    _, own, _ = _metas(path)
    pos = np.array(_vec(kv.get("pos", "0 0 0"), 3) or [0, 0, 0], float)
    R = np.array(_vec(kv.get("ori", "1 0 0 0 1 0 0 0 1"), 9) or [1, 0, 0, 0, 1, 0, 0, 0, 1], float).reshape(3, 3)
    out = []
    for g in _grid(kv):
        for s in own:
            c = s.copy_to((R, pos + R @ g))
            if kv.get("id"):
                c.id = kv["id"].lower()
            out.append(c)
    return out


@functools.lru_cache(None)
def _file_snaps(name, depth=0):
    """(snaps, had_shadow_info) of an LDraw file in its own frame."""
    path = _find(name)
    if not path or depth > 12:
        return (), False
    kids, had = [], False
    for line in open(path, errors="ignore"):
        t = line.split()
        if len(t) >= 15 and t[0] == "1":
            v = list(map(float, t[2:14]))
            R = np.array(v[3:12]).reshape(3, 3)
            if abs(np.linalg.det(R)) < 1e-6:
                continue
            sub, h = _file_snaps(" ".join(t[14:]).lower().replace("\\", "/"), depth + 1)
            had |= h
            kids += [s.copy_to((R, np.array(v[:3]))) for s in sub]
    clears, own, incl = _metas(_shadow_path(path))
    if (clears or own or incl) and "/parts/" in path.replace("\\", "/"):
        had = True                       # part-level info (primitives alone don't count)
    for c in clears:
        kids = [] if c == "" else [s for s in kids if s.id != c]
    for kv in incl:
        own += _incl(kv)
    return tuple(kids + own), had


def part_snaps(part):
    return _file_snaps(part.lower() + ".dat")


# ----------------------------------------------------------------------------- matching
def _axis(s):
    """Unit axis (the snap's -Y) and the [a, b] span along it, measured from s.pos."""
    d = -s.R[:, 1]
    n = np.linalg.norm(d)
    d = d / n if n else d
    L = s.length * (n or 1)
    return d, (-L / 2, L / 2) if s.center else (0.0, L)


def _secs_at(s, u0, u1, scale=1.0):
    """Sections of a cylinder (as (shape, r, a, b) along its own axis) overlapping [u0, u1]."""
    out, a = [], (-s.length / 2 if s.center else 0.0)
    for shape, r, ln in s.secs:
        b = a + ln
        if b > u0 and a < u1:
            out.append((shape, r, a, b))
        a = b
    return out


def _compat(m, f):
    """Male section shape/radius m fits female section f."""
    ms, mr = m
    fs, fr = f
    if ms in ("_L", "L_") or fs in ("_L", "L_"):
        return True
    if abs(mr - fr) > 0.75:
        return False
    if fs == "R":
        return ms in ("R", "A")
    if fs == "S":
        return ms in ("R", "S")
    if fs == "A":
        return ms == "A"
    return False


def _coaxial(a, b, tol=1.25):
    da, _ = _axis(a)
    db, _ = _axis(b)
    if abs(float(da @ db)) < 0.999:
        return None
    w = b.pos - a.pos
    perp = w - (w @ da) * da
    if np.linalg.norm(perp) > tol:
        return None
    return da, db, float(w @ da)


def match(a, b):
    """Connection type between two snaps of different parts, or None."""
    k = {a.kind, b.kind}
    if k == {"cyl"}:
        m, f = (a, b) if a.gender == "M" else (b, a)
        if m.gender != "M" or f.gender != "F":
            return None
        c = _coaxial(m, f)
        if not c:
            return None
        dm, df, off = c
        same = float(dm @ df) > 0
        _, (m0, m1) = _axis(m)
        _, (f0, f1) = _axis(f)
        # f's span in m's axis coordinates
        if same:
            g0, g1 = off + f0, off + f1
        else:
            g0, g1 = off - f1, off - f0
        lo, hi = max(m0, g0), min(m1, g1)
        if hi - lo < 0.5:
            return None
        if m.caps in ("one", "a", "two") and f.caps in ("one", "b", "two") and not same:
            return None
        kind = None
        for ms, mr, ma, mb in _secs_at(m, lo, hi):
            for fs, fr, fa, fb in _secs_at(f, *(sorted(((lo - off) if same else (off - hi),
                                                        (hi - off) if same else (off - lo))))):
                if ms in ("R", "A", "S") and fs in ("R", "A", "S") and mr > fr + 0.75:
                    return None                    # male thicker than the hole: interference
                if _compat((ms, mr), (fs, fr)) and kind != "stud":
                    if abs(mr - 6) < 0.75:         # stud into anti-stud, or a pin in a Technic hole
                        kind = "pin" if f.caps == "none" and m.caps == "none" else "stud"
                    elif mr < 5.5:
                        kind = "bar"
                    else:
                        kind = "round"             # e.g. a round plate's body nested in a round hole
        return kind
    if k == {"clp", "cyl"}:
        c_, y = (a, b) if a.kind == "clp" else (b, a)
        if y.gender != "M" or abs(c_.radius - y.radius) > 0.75 and not any(
                abs(c_.radius - r) <= 0.75 for _, r, _ in y.secs):
            return None
        co = _coaxial(c_, y)
        if not co:
            return None
        dc, dy, off = co
        _, (c0, c1) = _axis(c_)
        _, (y0, y1) = _axis(y)
        g0, g1 = (off + y0, off + y1) if float(dc @ dy) > 0 else (off - y1, off - y0)
        return "clip" if min(c1, g1) - max(c0, g0) > 0.5 else None
    if k == {"fgr"}:
        if a.group != b.group or abs(a.radius - b.radius) > 0.75:
            return None
        co = _coaxial(a, b)
        if not co:
            return None
        da, db, off = co
        same = float(da @ db) > 0
        fa, fb = _fingers(a), _fingers(b)
        fb = [(off + x0, off + x1, g) if same else (off - x1, off - x0, g) for x0, x1, g in fb]
        for x0, x1, _ in fa:
            for y0, y1, _ in fb:
                if min(x1, y1) - max(x0, y0) > 0.75:
                    return None                    # two fingers in the same slot
        ea = (min(x[0] for x in fa), max(x[1] for x in fa)) if fa else (0, 0)
        eb = (min(x[0] for x in fb), max(x[1] for x in fb)) if fb else (0, 0)
        return "hinge" if min(ea[1], eb[1]) - max(ea[0], eb[0]) > 0.75 else None
    if k == {"gen"}:
        if a.group != b.group or a.gender == b.gender:
            return None
        if np.linalg.norm(a.pos - b.pos) > 1.0 or abs(float(a.R[:, 1] @ b.R[:, 1])) < 0.99:
            return None
        return "generic"
    if k == {"sph"}:
        if a.gender == b.gender or abs(a.radius - b.radius) > 0.75:
            return None
        return "ball" if np.linalg.norm(a.pos - b.pos) < 1.0 else None
    return None


def _fingers(s):
    """Finger intervals along the axis as (a, b, gender); gaps count as the other gender."""
    out, x, g = [], (-s.length / 2 if s.center else 0.0), s.gofs
    for w in s.seq:
        out.append((x, x + w, g))
        x += w
        g = "F" if g == "M" else "M"
    return [o for o in out if o[2] == "M"]
