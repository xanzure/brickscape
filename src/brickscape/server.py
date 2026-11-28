"""brickscape MCP server.

Tools: guide, search_parts, part_info, build, render, compare, study_reference, parts_list,
export, instructions, check.
Builds are saved under BRICKSCAPE_OUT (default ./brickscape-out), one folder per build name.
"""
import json, os, re, tempfile, zipfile
from functools import wraps
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from brickscape import __version__
from typing import Annotated, Literal, Union
from pydantic import Field
from mcp.types import ToolAnnotations
from brickscape.plan import PlanError, compile_plan, op_reference
from brickscape.schema import Plan

INSTRUCTIONS = """BrickScape designs LEGO builds that can really be built. Never write LDraw coordinates
by hand: describe the build as a JSON plan and let `build` place every part on real studs.

Workflow: `guide` once (operations, coordinates, design rules) -> `build` a plan -> `render`
and look at all 4 views -> change the plan and `build` again at least once -> deliver with
`export` (Studio .io), `parts_list` (CSV + BrickLink wanted list) and, if asked,
`instructions` (PDF). With a reference photo use `compare`; with a reference build file use
`study_reference`. `check` validates any model file. `search_parts` / `part_info` look up
parts. Coordinates: studs, z = 0 is the front edge; heights in plates (3 plates = 1 brick).
Part source: "lego" (default) or "gobricks"."""

mcp = MCPServer("brickscape", title="BrickScape", version=__version__, instructions=INSTRUCTIONS,
                website_url="https://github.com/xanzure/brickscape")

Source = Annotated[Literal["lego", "gobricks"], Field(description="Part source: 'lego' (official LEGO parts and colours, default) or 'gobricks' (GoBricks moulds, colours and prices)")]
Name = Annotated[str, Field(description="The build's name, as given in its plan (see build)")]
RO = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

OUT = os.path.abspath(os.path.expanduser(os.environ.get("BRICKSCAPE_OUT", "brickscape-out")))


NEEDS_DATA = {"search_parts", "part_info", "build", "render", "parts_list", "export", "instructions",
              "compare", "study_reference", "check"}


_SETUP = {"thread": None, "error": None}


def _data_present():
    from brickscape.config import LDRAW, DATA
    return (os.path.isdir(os.path.join(LDRAW, "parts"))
            and os.path.exists(os.path.join(DATA, "rebrickable", "elements.csv.gz"))
            and bool(__import__("glob").glob(os.path.join(DATA, "ldcad", "*", "parts"))))


def _auto_setup():
    """First start without part data: download it in the background (LDraw library, LEGO part
    tables, connection data; not Blender). BRICKSCAPE_NO_AUTO_SETUP=1 turns this off."""
    if _data_present() or os.environ.get("BRICKSCAPE_NO_AUTO_SETUP") or _SETUP["thread"]:
        return
    import threading

    def run():
        try:
            from brickscape.__main__ import ldraw_library
            from brickscape.catalog import lego
            from brickscape.core import snaps
            ldraw_library()
            lego.download()
            snaps.download()
        except Exception as e:                      # reported by the next tool call
            _SETUP["error"] = f"{type(e).__name__}: {e}"
    _SETUP["thread"] = threading.Thread(target=run, daemon=True)
    _SETUP["thread"].start()


def _missing_data():
    from brickscape.config import LDRAW
    t = _SETUP["thread"]
    if t is not None and t.is_alive():
        return ("BrickScape is downloading its part data (LDraw library, LEGO part tables, connection "
                "data; about 150 MB, first start only). Try again in a minute.")
    if _data_present():
        return None
    if _SETUP["error"]:
        return f"Downloading the part data failed ({_SETUP['error']}). Run `brickscape setup` and try again."
    return (f"The part data is not installed (LDraw library looked for in {LDRAW}). "
            "Run `brickscape setup` once, or set LDRAW_LIBRARY_PATH.")


def _tool(fn):
    """Surface expected failures to the client as ToolError, with their message."""
    @wraps(fn)
    def run(*a, **k):
        if fn.__name__ in NEEDS_DATA and (msg := _missing_data()):
            raise ToolError(msg)
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


GUIDE = """# BrickScape guide

You design LEGO builds by sending a JSON **build plan** to `build`. The toolkit turns each
operation into real parts on real studs, so you never compute LDraw coordinates. Every result
is repaired (loose or clashing decorations removed, colours moved to ones that really exist)
and strictly validated: real parts and colours, no collisions between solid shapes, every part
held by a real connection (studs, bars, clips, hinges, pins) down to the baseplate.

## Workflow
1. Write a short brief: subject, size, what goes where, palette.
2. `build` with a plan. Read the report: it lists anything removed or still failing.
3. `render` and look at all 4 views. Fix what looks wrong by changing the plan, build again.
   Do at least one improvement round: check the brief's size, part-count and colour limits,
   fill empty areas with detail, and make the main subject stand out.
4. Deliver: `export` (Studio .io), `parts_list`, and `instructions` if asked.

## References
If the user gives you a reference photo or build, use it: it makes a much better result.
- A photo: look at it, plan the same layout (where the rock, water, trees are, their sizes in
  studs), then `compare` your build with the photo from the photo's viewpoint and fix the
  biggest differences first.
- A build file (.io / .ldr): `study_reference` tells you its size, density, colours and parts;
  match its proportions and palette.

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

## Part sources (brick companies)
`source` = "lego" (default: parts and colours LEGO has produced) or "gobricks" (GoBricks
moulds and colours, with prices). Validation, colour repair and part lists follow the source.
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


@mcp.tool(title="Planning guide", annotations=RO)
@_tool
def guide() -> str:
    """How to plan a BrickScape build. Call this first, once per session, before writing a plan.

    Returns Markdown: the workflow (brief, build, render, improve, deliver), the coordinate system
    (studs; z = 0 is the front edge; heights in plates, 3 plates = 1 brick), every plan operation
    with its fields, design rules, how to use reference photos, colour names and an example plan.
    Read-only; needs no installed data."""
    return GUIDE.format(ops=op_reference(), example=json.dumps(EXAMPLE, indent=1))


@mcp.tool(title="Search parts", annotations=RO)
@_tool
def search_parts(query: Annotated[str, Field(description="Words that must all appear in the part description, e.g. 'slope 45 2 x 1' or 'plant leaves'")],
                 source: Source = "lego",
                 limit: Annotated[int, Field(ge=1, le=200, description="Maximum number of parts to list")] = 25) -> str:
    """Find LDraw parts by description, with availability at a part source.

    Use it to pick parts for `brick` / `ldraw` operations, or to check whether a part exists at
    LEGO or GoBricks. Matches parts whose description contains every word of `query` (case
    insensitive), lists available parts first, most colours first. Returns one line per part:
    part number, description, and "N colours" or "NOT AVAILABLE". For one part's details use
    `part_info`. Read-only."""
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


@mcp.tool(title="Part details", annotations=RO)
@_tool
def part_info(part: Annotated[str, Field(description="LDraw part number, e.g. '3001' or '32607'")],
              source: Source = "lego") -> str:
    """Details of one part: size, connection points and real colours.

    Use it before placing a specific part, to know how big it is, how it connects (studs,
    anti-studs, bars, bar holes, clips, hinge fingers, ball joints, from the LDCad connection
    data) and which colours exist for it at the part source. Returns plain text: description,
    size in studs and plates, a count of each connection type, and the colour names with LDraw
    codes. To find a part number first, use `search_parts`. Read-only."""
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
    s = r["source"]
    # unavailable parts and impossible part/colour pairs live in r["source"], not r["checks"]
    ok = not any(c.values()) and not s["missing"] and not s["bad_colour"]
    lines = [f"{'VALID' if ok else 'PROBLEMS'}: {r['pieces']} parts, source {r['source']['source']}"]
    for k, v in c.items():
        if v:
            lines.append(f"- {k}: {len(v)} ({', '.join(v[:8])}{' ...' if len(v) > 8 else ''})")
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


@mcp.tool(title="Build a plan", annotations=WRITES)
@_tool
def build(plan: Annotated[Union[Plan, str], Field(description="The build plan: board size, seed and a list of operations (hill, block, water, path, boulder, tree, plant, scatter, brick, ldraw). An object or a JSON string.")],
          source: Source = "lego") -> str:
    """Compile a build plan into a LEGO model, repair it and validate it strictly.

    This is the main tool. The plan gives a board size and a list of operations (hill, block,
    water, path, boulder, tree, plant, scatter, brick, ldraw); call `guide` for what each does.
    BrickScape places every part on real studs, removes parts that don't fit or stick out past
    the board, swaps colours that don't exist for a part to the nearest real one, then checks for
    intersecting parts, loose parts, unavailable parts and impossible colours.

    Writes `<BRICKSCAPE_OUT>/<plan name>/model.ldr`, `plan.json` and `report.json` (building the
    same name again replaces them). Returns the report: VALID or PROBLEMS, what was removed or
    recoloured, part count, and the saved path. Next: `render` to look at it, then `export`,
    `parts_list` or `instructions`. Invalid plans are rejected with the exact field at fault."""
    from brickscape.validate import validate, repair
    from brickscape.catalog import fix_colours
    from brickscape.schema import parse
    p = parse(plan)
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
    return (_report(r, removed, recol) + f"\nsaved: {os.path.join(d, 'model.ldr')}\n" + "\n".join(comp.log)
            + "\nNext: call render and look at all 4 views; change the plan and build again until it"
              " looks right for the brief (a valid build is not yet a good one).")


@mcp.tool(title="Render 4 views", annotations=WRITES)
@_tool
def render(name: Name,
           resolution: Annotated[int, Field(ge=160, le=2000, description="Pixel size of each of the 4 views")] = 640) -> Image:
    """Render a saved build from the 4 standard camera angles, as one 2x2 image.

    Use after `build` to see the result; look at all four views before changing the plan or
    delivering. Views: front-left, front-right, back-right, back-left, 30 degrees above the board.
    Returns a PNG image and saves the views in `<build>/renders/`. Needs Blender 4.x; takes about
    10-60 seconds depending on size. To compare with a photo from its viewpoint use `compare`."""
    from brickscape.review.views import standard_views
    d = _dir(name)
    out = standard_views(os.path.join(d, "model.ldr"), os.path.join(d, "renders"), resolution=resolution)
    return Image(data=Path(out["sheet"]).read_bytes(), format="png")


@mcp.tool(title="Parts list", annotations=WRITES)
@_tool
def parts_list(name: Name, source: Source = "lego") -> str:
    """Write the parts list of a saved build.

    Use when the user wants to buy or count the parts. Writes `<build>/parts.csv` (part, name,
    colour, LDraw and BrickLink colour ids, quantity, price) and `<build>/bricklink.xml`, a
    BrickLink wanted list ready to upload. Returns a summary: total parts, part/colour lots, the
    file paths, the most used parts, and an estimated cost when `source` is "gobricks". Requires a
    build made with `build` first."""
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


@mcp.tool(title="Export Studio .io", annotations=WRITES)
@_tool
def export(name: Name) -> str:
    """Export a saved build as a BrickLink Studio .io file.

    Use when the user wants to open, edit, price or make instructions for the model in BrickLink
    Studio. Writes `<build>/<name>.io` (with the front-left render as its thumbnail if `render`
    was run) and returns the paths of the .io and the LDraw model.ldr. Requires a build made with
    `build` first; overwrites an earlier export."""
    from brickscape.io.export import write_io
    d = _dir(name)
    thumb = os.path.join(d, "renders", "view_front-left.png")
    out = write_io(os.path.join(d, "model.ldr"), os.path.join(d, _slug(name) + ".io"),
                   thumbnail=thumb if os.path.exists(thumb) else None)
    return f"Studio file: {out}\nLDraw file: {os.path.join(d, 'model.ldr')}"


@mcp.tool(title="Building instructions (PDF)", annotations=WRITES)
@_tool
def instructions(name: Name,
                 parts_per_step: Annotated[int, Field(ge=1, le=60, description="Most parts added in one instruction step")] = 10) -> str:
    """Make step-by-step building instructions as a PDF for a saved build.

    Use when the user asks for instructions. Orders the parts so each one is added only after
    something it connects to, lower parts first, groups them into steps of up to
    `parts_per_step`, renders every step from one camera, and lays out pages with a parts box per
    step. Writes `<build>/instructions/instructions.pdf` and `model_steps.ldr` (with STEP lines for
    Studio's Instruction Maker). Returns the step and page count and paths. Needs Blender; slow
    for big builds (one render per step), so offer it rather than running it unasked."""
    from brickscape.core.brick import from_ldr
    from brickscape.review.instructions import make
    d = _dir(name)
    b = from_ldr(os.path.join(d, "model.ldr"))
    r = make(b, os.path.join(d, "instructions"), per_step=parts_per_step, title=name)
    return f"{r['steps']} steps, {r['pages']} pages: {r['pdf']}\nordered model with STEP lines: {r['ldr']}"


def _ldr_of(path):
    """An .ldr path for .ldr/.mpd/.io input (.io is unpacked to a temp file)."""
    p = os.path.expanduser(path)
    if p.lower().endswith(".io"):
        z = zipfile.ZipFile(p)
        z.setpassword(b"soho0909")
        q = os.path.join(tempfile.mkdtemp(), "model.ldr")
        open(q, "wb").write(z.read("model.ldr"))
        return q
    return p


@mcp.tool(title="Compare with a photo", annotations=WRITES)
@_tool
def compare(name: Name,
            reference: Annotated[str, Field(description="Path to the reference photo (PNG, JPG or WebP)")],
            azimuth: Annotated[float, Field(description="Camera direction in degrees: 270 front, 225 front-left, 180 left, 315 front-right")] = 225,
            elevation: Annotated[float, Field(ge=0, le=90, description="Camera height in degrees above the baseplate")] = 30) -> Image:
    """Render a saved build from a chosen camera next to a reference photo.

    Use when the user gave a reference photo: set `azimuth` / `elevation` to match the photo's
    viewpoint, compare layout, proportions and colours, change the plan, build again. Returns
    one PNG with the photo on the left and the build on the right, also saved as
    `<build>/renders/compare.png`. Needs Blender. For a reference build file use `study_reference`."""
    from brickscape.review.render import compare as cmp
    d = _dir(name)
    out = os.path.join(d, "renders", "compare.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmp(os.path.join(d, "model.ldr"), os.path.expanduser(reference), out, azimuth, elevation, resolution=640)
    return Image(data=Path(out).read_bytes(), format="png")


@mcp.tool(title="Study a reference build", annotations=RO)
@_tool
def study_reference(path: Annotated[str, Field(description="Path to a reference model: .ldr, .mpd or BrickLink Studio .io")]) -> str:
    """Analyse a reference LEGO build file to learn its proportions and techniques.

    Use when the user gives an .ldr, .mpd or BrickLink Studio .io as a reference (not a photo:
    for photos use `compare`). Returns plain text: part count, footprint in studs, height,
    parts per covered stud, how hollow it is, the share of sideways (SNOT) and angled parts, part
    categories, main colours and the 30 most used parts. Read-only: does not change or save the
    file. To check whether that file is buildable use `check`."""
    from brickscape.io.analyze_ref import analyse
    from brickscape.plan import colours
    r = analyse(_ldr_of(path))
    if not r.get("parts"):
        return f"no parts found in {path}"
    names = {v: k for k, v in colours().items()}
    col = lambda L: ", ".join(f"{names.get(int(c), c)} {n}" for c, n in L)
    return "\n".join([
        f"{r['parts']} parts ({r['unique']} different), footprint {r['footprint_studs'][0]} x {r['footprint_studs'][1]} studs, "
        f"{r['height_plates']} plates ({r['height_plates'] / 3:.1f} bricks) tall",
        f"density: {r['parts_per_covered_stud']} parts per covered stud; filled under the surface: "
        f"{round(100 * r['fill_ratio_under_surface'])}% (low = hollow)",
        f"sideways (SNOT) parts: {r['sideways_pct']}%, parts at odd angles: {r['angled_pct']}%",
        "categories: " + ", ".join(f"{k} {n}" for k, n in r["categories"]),
        "colours: " + col(r["colours"]),
        "top surface colours: " + col(r["top_surface_colours"]),
        "most used parts:",
        *[f"  {n:4d}x {p} {d}" for p, n, d in r["top_parts"]],
    ])


@mcp.tool(title="Check any model", annotations=RO)
@_tool
def check(path: Annotated[str, Field(description="Path to a model to validate: .ldr, .mpd or BrickLink Studio .io")],
          source: Source = "lego") -> str:
    """Strictly validate any LEGO model file for buildability.

    Use on any .ldr, .mpd or BrickLink Studio .io, including models not made by BrickScape (for
    BrickScape builds, `build` already reports this). Checks that every part exists in the LDraw
    library and at the part source, every part/colour pair exists, rotations are real (no mirrored
    or scaled parts), no duplicates, no two parts intersect (real part shapes), and every part is
    held by a real connection down to the base. Returns VALID or PROBLEMS with each failing check,
    the parts involved (part#index) and counts by connection type. Read-only: it never changes the
    file. Does not check balance or clutch strength."""
    from brickscape.core.brick import from_ldr
    from brickscape.validate import validate
    b = from_ldr(_ldr_of(path))
    for x in b.pieces:
        x.soft = x.free = False
    return _report(validate(b, source=source), [], {})


# ----------------------------------------------------------------------------- resources
EXAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")


@mcp.resource("brickscape://guide", name="guide", title="Planning guide", mime_type="text/markdown",
              description="The full planning guide: workflow, coordinates, every operation, style rules, example.")
def guide_resource() -> str:
    return guide()


@mcp.resource("brickscape://schema/plan", name="plan-schema", title="Build plan JSON schema",
              mime_type="application/json",
              description="JSON Schema of a build plan: every operation, field, allowed value and limit.")
def plan_schema() -> str:
    return json.dumps(Plan.model_json_schema(), indent=1)


@mcp.resource("brickscape://examples/{example}", name="example-plan", title="Example build plan",
              mime_type="application/json",
              description="A complete example plan: 'forest-clearing', 'garden-20' or 'showcase' (the README cover).")
def example_plan(example: str) -> str:
    f = os.path.join(EXAMPLES, os.path.basename(example) + ".json")
    if not os.path.exists(f):
        raise ValueError(f"no example {example!r}; have: "
                         + ", ".join(sorted(x[:-5] for x in os.listdir(EXAMPLES) if x.endswith(".json"))))
    return open(f).read()


@mcp.resource("brickscape://colours", name="colours", title="LEGO colour names", mime_type="text/plain",
              description="Every LDraw colour name and code accepted in plans (e.g. 'dark bluish grey' = 72).")
def colour_list() -> str:
    from brickscape.plan import colours
    return "\n".join(f"{code:5d}  {name}" for name, code in sorted(colours().items(), key=lambda kv: kv[1]))


# ----------------------------------------------------------------------------- prompts
@mcp.prompt(name="design_scene", title="Design a LEGO scene",
            description="Design a buildable LEGO scene from a short description, then deliver the files.")
def design_scene(description: str, width: int = 32, depth: int = 32, source: str = "lego") -> str:
    return (f"Design a LEGO build with BrickScape: {description}\n"
            f"Board: {width} x {depth} studs. Part source: {source}.\n"
            "Call `guide` first. Write a short brief (what goes where, palette, limits), then `build` a plan, "
            "`render` it and look at all four views, improve the plan and build again at least once. "
            "When it looks right, `export` the Studio .io and run `parts_list`. Report the file paths, "
            "the part count and anything the validator removed.")


@mcp.prompt(name="recreate_photo", title="Recreate a LEGO photo",
            description="Recreate a LEGO diorama from a reference photo as closely as possible.")
def recreate_photo(photo_path: str, width: int = 32, depth: int = 32) -> str:
    return (f"Recreate the LEGO build in the photo {photo_path} with BrickScape, on {width} x {depth} studs.\n"
            "Look at the photo and note what goes where (rock, water, trees, paths), rough sizes in studs and "
            "the colours. Call `guide`, `build` a plan that matches that layout, then use `compare` with the photo "
            "from a camera that matches its viewpoint, fix the biggest differences and build again. Repeat until "
            "the layout, proportions and colours match, then `export` and run `parts_list`.")


@mcp.prompt(name="check_model", title="Check a model is buildable",
            description="Check any LEGO model file for problems and explain how to fix them.")
def check_model(path: str, source: str = "lego") -> str:
    return (f"Use BrickScape's `check` on {path} (part source {source}). Explain each problem it finds "
            "(intersecting parts, loose parts, unavailable parts, impossible colours) in plain words, "
            "say which parts are involved and how a builder could fix each one.")


def main():
    _auto_setup()
    mcp.run()


if __name__ == "__main__":
    main()
