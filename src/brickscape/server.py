"""brickscape MCP server.

Tools: guide, search_parts, part_info, build, render, parts_list, export, instructions, check.
Builds are saved under BRICKSCAPE_OUT (default ./brickscape-out), one folder per build name.
"""
import json, os, re, tempfile, zipfile
from functools import wraps
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from brickscape import __version__
from brickscape.plan import PlanError, compile_plan, op_reference

mcp = MCPServer("brickscape", version=__version__)
OUT = os.path.abspath(os.path.expanduser(os.environ.get("BRICKSCAPE_OUT", "brickscape-out")))


def _tool(fn):
    """Surface expected failures to the client as ToolError, with their message."""
    @wraps(fn)
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except (PlanError, ValueError, OSError, RuntimeError, KeyError) as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e
    return run


def _slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "build"


def _dir(name):
    d = os.path.join(OUT, _slug(name))
    if not os.path.isdir(d):
        raise ValueError(f"no build named {name!r} in {OUT} (run build first)")
    return d


GUIDE = """# brickscape guide

You design LEGO builds by sending a JSON **build plan** to `build`. The toolkit turns each
operation into real parts on real studs, so you never compute LDraw coordinates. Every result
is repaired (loose or clashing decorations removed, colours moved to ones that really exist)
and strictly validated: real parts and colours, no collisions between solid shapes, every part
held by a real connection (studs, bars, clips, hinges, pins) down to the baseplate.

## Workflow
1. Write a short brief: subject, size, what goes where, palette.
2. `build` with a plan. Read the report: it lists anything removed or still failing.
3. `render` and look at all 4 views. Fix what looks wrong by changing the plan, build again.
4. Deliver: `export` (Studio .io), `parts_list`, and `instructions` if asked.

## Coordinates
- Board: width x depth studs, multiples of 16 (32 = one baseplate). x = left to right,
  z = front (z = 0, nearest the viewer) to back. Heights in plates (3 plates = 1 brick).
- Later operations sit on top of earlier ones: the toolkit keeps a height map. Terrain ops
  claim their cells, so place terrain first, then paths and water, then trees and scatter.

## Operations
{ops}

## Style that reads well
- Lean cliff faces back as they rise; avoid stair-stepped pyramids and flat shallow slopes.
- Set paths into the ground; raise ground 1-2 plates beside water.
- Mix 2-3 shades in rock (dark + light bluish grey), 2-3 greens in plants. Fewer, better
  plants beat a carpet of them; leave open space.
- Keep large volumes hollow (block does this for you).

## Example
{example}

## Colours
LDraw colour names or codes: green 2, bright green 10, dark green 288, olive green 330, tan 19,
dark tan 28, reddish brown 70, dark brown 308, light bluish grey 71, dark bluish grey 72,
black 0, white 15, blue 1, dark blue 272, medium azure 322, trans light blue 43.

## Part sources
`source` = "lego" (default: parts and colours LEGO has produced) or "gobricks" (GoBricks
moulds and colours, with prices).
"""

EXAMPLE = {
    "name": "forest clearing", "board": {"width": 32, "depth": 32}, "seed": 1,
    "ops": [
        {"op": "hill", "area": {"ellipse": [22, 24, 9, 7], "rough": 0.5}, "height": 8, "style": "terraces"},
        {"op": "hill", "area": {"ellipse": [6, 26, 5, 4]}, "height": 12, "style": "rock"},
        {"op": "path", "points": [[0, 10], [14, 13], [31, 9]], "width": 3, "style": "cobble"},
        {"op": "boulder", "at": [[12, 3, 4], [20, 4, 2]]},
        {"op": "tree", "kind": "oak", "size": "medium", "at": [27, 4]},
        {"op": "scatter", "area": {"rect": [0, 0, 32, 32]}, "kinds": ["tuft", "flower", "bush"], "density": 0.06},
    ]}


@mcp.tool()
@_tool
def guide() -> str:
    """How to plan a brickscape build: workflow, coordinates, every operation, style tips and
    an example plan. Read this first."""
    return GUIDE.format(ops=op_reference(), example=json.dumps(EXAMPLE, indent=1))


@mcp.tool()
@_tool
def search_parts(query: str, source: str = "lego", limit: int = 25) -> str:
    """Find LDraw parts whose description matches all words of `query` (e.g. "slope 45 2 x 1",
    "plant leaves"), with whether the part source has them and in how many colours."""
    from brickscape.catalog import get
    from brickscape.config import LDRAW
    words = query.lower().split()
    src = get(source)
    hits = []
    for f in sorted(os.listdir(os.path.join(LDRAW, "parts"))):
        if not f.endswith(".dat"):
            continue
        with open(os.path.join(LDRAW, "parts", f), errors="ignore") as fh:
            desc = fh.readline()[2:].strip()
        d = desc.lower()
        if desc.startswith("~") or not all(w in d for w in words):
            continue
        pid = f[:-4]
        r = src.resolve(pid)
        cols = src.colours(r) if r else None
        hits.append((0 if r else 1, -(len(cols) if cols else 0), pid, desc, r, cols))
    hits.sort()
    lines = [f"{len(hits)} matches (showing {min(limit, len(hits))}), source {source}:"]
    for _, _, pid, desc, r, cols in hits[:limit]:
        avail = (f"{len(cols)} colours" if cols else "available") if r else "NOT AVAILABLE"
        lines.append(f"- {pid}: {desc} [{avail}]")
    return "\n".join(lines)


@mcp.tool()
@_tool
def part_info(part: str, source: str = "lego") -> str:
    """Size and connection points of one part (studs, anti-studs, bars, clips, hinges, pins)
    and the colours it exists in at the part source."""
    from brickscape.core.brick import info
    from brickscape.core.snaps import part_snaps
    from brickscape.catalog import get
    from brickscape.plan import colours
    i = info(part)
    lo, hi = i["lo"], i["hi"]
    S, had = part_snaps(part)
    kinds = {}
    for s in S:
        if s.kind == "cyl":
            r = s.secs[-1][1] if s.secs else s.radius
            k = ("stud" if s.gender == "M" else "anti-stud") if abs(r - 6) < 0.6 else \
                ("bar" if s.gender == "M" else "bar hole") if r < 5 else ("cylinder " + s.gender)
        else:
            k = {"clp": "clip", "fgr": "hinge fingers", "gen": "special", "sph": "ball joint"}[s.kind]
        kinds[k] = kinds.get(k, 0) + 1
    src = get(source)
    r = src.resolve(part)
    cols = sorted(src.colours(r) or []) if r else []
    names = {v: k for k, v in colours().items()}
    return "\n".join([
        f"{part}: {i['desc']}",
        f"size: {(hi[0] - lo[0]) / 20:g} x {(hi[2] - lo[2]) / 20:g} studs, {(hi[1] - lo[1]) / 8:g} plates high",
        "connections: " + (", ".join(f"{n} {k}" for k, n in kinds.items()) or "none known")
        + ("" if had else " (no detailed connection data: studs and bottom only)"),
        f"{source}: " + ("not available" if not r else f"{len(cols)} colours: "
                         + ", ".join(f"{names.get(c, c)} ({c})" for c in cols[:40])),
    ])


def _report(r, removed, recol):
    c = r["checks"]
    ok = not any(c.values())
    lines = [f"{'VALID' if ok else 'PROBLEMS'}: {r['pieces']} parts, source {r['source']['source']}"]
    for k, v in c.items():
        if v:
            lines.append(f"- {k}: {len(v)} ({', '.join(v[:8])}{' ...' if len(v) > 8 else ''})")
    s = r["source"]
    if s["missing"]:
        lines.append(f"- parts not available at {s['source']}: {s['missing']}")
    if s["bad_colour"]:
        lines.append(f"- colours not available: {s['bad_colour']}")
    if removed:
        from collections import Counter
        lines.append(f"- repair removed {len(removed)} parts that didn't fit: "
                     + ", ".join(f"{n}x {p}" for (p, col), n in Counter(removed).most_common(10)))
    if recol:
        lines.append(f"- recoloured to real colours: {recol}")
    lines.append(f"- connections: {r['connections']}")
    if s.get("cost_usd"):
        lines.append(f"- estimated cost: ${s['cost_usd']}")
    lines.append("Checked: parts, colours, rotations, duplicates, solid-shape collisions, connections. "
                 "Not checked: balance under gravity and clutch strength.")
    return "\n".join(lines)


@mcp.tool()
@_tool
def build(plan: str, source: str = "lego") -> str:
    """Compile a JSON build plan (see guide) into a model, repair it, check it strictly, and
    save it as <name>/model.ldr. Returns the validation report."""
    from brickscape.validate import validate, repair
    from brickscape.catalog import fix_colours
    p = json.loads(plan) if isinstance(plan, str) else plan
    b, comp = compile_plan(p)
    removed = repair(b)
    recol = fix_colours(b, source)
    r = validate(b, source=source)
    d = os.path.join(OUT, _slug(p.get("name", "build")))
    os.makedirs(d, exist_ok=True)
    b.write(os.path.join(d, "model.ldr"))
    json.dump(p, open(os.path.join(d, "plan.json"), "w"), indent=1)
    json.dump({"checks": r["checks"], "connections": r["connections"], "removed": len(removed),
               "recoloured": recol, "source": r["source"], "log": comp.log},
              open(os.path.join(d, "report.json"), "w"), indent=1, default=str)
    return _report(r, removed, recol) + f"\nsaved: {os.path.join(d, 'model.ldr')}\n" + "\n".join(comp.log)


@mcp.tool()
@_tool
def render(name: str, resolution: int = 640) -> Image:
    """Render a saved build from the 4 standard views (front-left, front-right, back-right,
    back-left, 30 degrees up) as one 2x2 image. Look at every view before delivering."""
    from brickscape.review.views import standard_views
    d = _dir(name)
    out = standard_views(os.path.join(d, "model.ldr"), os.path.join(d, "renders"), resolution=resolution)
    return Image(data=Path(out["sheet"]).read_bytes(), format="png")


@mcp.tool()
@_tool
def parts_list(name: str, source: str = "lego") -> str:
    """Write the part list of a saved build: parts.csv and a BrickLink wanted list
    (bricklink.xml). Returns a summary."""
    from brickscape.io.export import parts_list as pl
    d = _dir(name)
    r = pl(os.path.join(d, "model.ldr"), d, source=source)
    lines = [f"{r['pieces']} parts in {r['lots']} part/colour lots", f"csv: {r['csv']}", f"bricklink: {r['bricklink_xml']}"]
    if r["estimated_cost_usd"]:
        lines.append(f"estimated cost (GoBricks): ${r['estimated_cost_usd']}")
    if r["no_bricklink_colour"]:
        lines.append(f"no BrickLink colour id for: {r['no_bricklink_colour']}")
    lines += [f"  {q:4d}x {p} {c} - {desc}" for q, p, c, desc in r["top"]]
    return "\n".join(lines)


@mcp.tool()
@_tool
def export(name: str) -> str:
    """Export a saved build as a BrickLink Studio .io file (with a thumbnail if rendered)."""
    from brickscape.io.export import write_io
    d = _dir(name)
    thumb = os.path.join(d, "renders", "view_front-left.png")
    out = write_io(os.path.join(d, "model.ldr"), os.path.join(d, _slug(name) + ".io"),
                   thumbnail=thumb if os.path.exists(thumb) else None)
    return f"Studio file: {out}\nLDraw file: {os.path.join(d, 'model.ldr')}"


@mcp.tool()
@_tool
def instructions(name: str, parts_per_step: int = 10) -> str:
    """Make step-by-step building instructions (PDF) for a saved build. Slow for big builds
    (one render per step)."""
    from brickscape.core.brick import from_ldr
    from brickscape.review.instructions import make
    d = _dir(name)
    b = from_ldr(os.path.join(d, "model.ldr"))
    r = make(b, os.path.join(d, "instructions"), per_step=parts_per_step, title=name)
    return f"{r['steps']} steps, {r['pages']} pages: {r['pdf']}\nordered model with STEP lines: {r['ldr']}"


@mcp.tool()
@_tool
def check(path: str, source: str = "lego") -> str:
    """Strictly validate any .ldr / .mpd / Studio .io file."""
    from brickscape.core.brick import from_ldr
    from brickscape.validate import validate
    p = os.path.expanduser(path)
    if p.endswith(".io"):
        z = zipfile.ZipFile(p)
        z.setpassword(b"soho0909")
        td = tempfile.mkdtemp()
        q = os.path.join(td, "model.ldr")
        open(q, "wb").write(z.read("model.ldr"))
        p = q
    b = from_ldr(p)
    for x in b.pieces:
        x.soft = x.free = False
    return _report(validate(b, source=source), [], {})


def main():
    mcp.run()


if __name__ == "__main__":
    main()
