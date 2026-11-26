"""Renders for review: any azimuth/elevation, contact sheets, cross-section slices.

Uses the same Blender + ImportLDraw pipeline as the ldraw MCP server (its blender_script.py),
called directly so we can choose the camera elevation (flat side views, top views).

Azimuth convention (renderer): 270 = front view, 180 = left view, 225 = front-left.
"""
import glob, os, subprocess, tempfile
from brickscape.config import LDRAW, blender as _blender, blender_script as _script

VIEWS = {  # name: (azimuth, elevation)
    "front-left": (225, 24), "front": (270, 18), "left": (180, 18),
    "front-flat": (270, 1), "left-flat": (180, 1), "top": (270, 89), "front-left-low": (225, 8),
}
SHEET = ["front-left", "front", "left", "front-flat", "left-flat", "top"]




def render(ldr, out_png, azimuths=(225,), elevation=22, resolution=480, samples=10, timeout=900):
    """Render views (one PNG per azimuth, stitched side by side) at one elevation."""
    with tempfile.TemporaryDirectory() as td:
        prefix = os.path.join(td, "v")
        cmd = [_blender(), "-b", "--factory-startup", "-P", _script(), "--", "--ldr", os.path.abspath(ldr),
               "--out", prefix, "--azimuths=" + ",".join(str(a) for a in azimuths), "--elevation", str(elevation),
               "--samples", str(samples), "--resolution", str(resolution), "--ldraw-dir", LDRAW]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        views = [f"{prefix}_{i}.png" for i in range(len(azimuths))]
        if p.returncode or not all(os.path.exists(v) for v in views):
            raise RuntimeError("render failed:\n" + "\n".join((p.stdout + p.stderr).splitlines()[-12:]))
        from PIL import Image
        ims = [Image.open(v).convert("RGB") for v in views]
        sheet = Image.new("RGB", (sum(i.width for i in ims), max(i.height for i in ims)), (255, 255, 255))
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0)); x += im.width
        sheet.save(out_png)
    return out_png


def render_view(ldr, out_png, cam, target, lens=35, size=(800, 800), samples=12, board=(32, 32), timeout=900):
    """Render from an explicit camera (board coords: x, z studs; h bricks above the baseplate),
    to match a reference photo's viewpoint. See blender_view.py."""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_view.py")
    f = lambda v: ",".join(str(round(q, 3)) for q in v)
    # board coords -> LDraw coords; the script maps LDraw -> Blender through the model's bbox
    from brickscape.core.brick import from_ldr
    m = from_ldr(ldr)
    lo = [min(p.lo[i] for p in m.pieces) for i in range(3)]
    hi = [max(p.hi[i] for p in m.pieces) for i in range(3)]
    W, D = board
    ld = lambda q: (-W * 10 + 20 * q[0], -24 * q[2], -D * 10 + 20 * q[1])
    cmd = [_blender(), "-b", "--factory-startup", "-P", script, "--", "--ldr", os.path.abspath(ldr),
           "--out", os.path.abspath(out_png), "--board", f(board), "--cam=" + f(ld(cam)), "--target=" + f(ld(target)),
           "--ldbox=" + f(lo + hi),
           "--lens", str(lens), "--size", f"{size[0]}x{size[1]}", "--samples", str(samples), "--ldraw-dir", LDRAW]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode or not os.path.exists(out_png):
        raise RuntimeError("render failed:\n" + "\n".join((p.stdout + p.stderr).splitlines()[-12:]))
    return out_png


def contact_sheet(ldr, out_png, views=SHEET, resolution=420, samples=8, title=None):
    """Grid of labelled views (default: front-left, front, left, flat front, flat left, top)."""
    from PIL import Image, ImageDraw
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        by_elev = {}
        for v in views:
            az, el = VIEWS[v]
            by_elev.setdefault(el, []).append((v, az))
        for el, items in by_elev.items():
            png = os.path.join(td, f"e{el}.png")
            render(ldr, png, [az for _, az in items], el, resolution, samples)
            im = Image.open(png)
            w = im.width // len(items)
            for i, (v, _) in enumerate(items):
                tiles.append((v, im.crop((i * w, 0, (i + 1) * w, im.height))))
    order = {v: i for i, v in enumerate(views)}
    tiles.sort(key=lambda t: order[t[0]])
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    W, H = tiles[0][1].size
    top = 28 if title else 0
    sheet = Image.new("RGB", (cols * W, rows * H + top), (235, 235, 235))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((8, 6), title, fill=(0, 0, 0))
    for k, (v, im) in enumerate(tiles):
        x, y = (k % cols) * W, (k // cols) * H + top
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + 120, y + 16], fill=(255, 255, 255))
        d.text((x + 4, y + 3), v, fill=(0, 0, 0))
    sheet.save(out_png)
    return out_png


def slice_ldr(src, out_ldr, axis="x", lo=0, hi=4):
    """Write the parts of a model whose centre lies in a slab (studs, board coordinates) --
    rendered from the side, a slab shows the true profile of a cliff or hill."""
    from brickscape.core.brick import from_ldr, info, _apply
    b = from_ldr(src)
    keep = []
    for i, p in enumerate(b.pieces):
        if i in b.roots:
            continue
        c = ((p.lo[0] + p.hi[0]) / 2 + b.W * 10) / 20 if axis == "x" else ((p.lo[2] + p.hi[2]) / 2 + b.D * 10) / 20
        if lo <= c < hi:
            keep.append(p)
    with open(out_ldr, "w") as f:
        f.write(f"0 slice {axis} {lo}-{hi} of {os.path.basename(src)}\n")
        for p in keep:
            f.write(p.line() + "\n")
    return len(keep)


def profile_strip(src, out_png, axis="x", positions=None, width=4, resolution=360, samples=6):
    """Side renders of several slabs next to each other (axis x: slices viewed from the left,
    showing the FRONT face profile; axis z: slices viewed from the front, showing the LEFT face)."""
    from PIL import Image, ImageDraw
    from brickscape.core.brick import from_ldr
    b = from_ldr(src)
    n = b.W if axis == "x" else b.D
    positions = positions or list(range(width, n - width, max(width, n // 6)))[:6]
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        for pos in positions:
            sl = os.path.join(td, f"s{pos}.ldr")
            if slice_ldr(src, sl, axis, pos, pos + width) == 0:
                continue
            png = os.path.join(td, f"s{pos}.png")
            az = 180 if axis == "x" else 270          # look along the slab
            render(sl, png, [az], 1, resolution, samples)
            tiles.append((pos, Image.open(png).convert("RGB")))
    if not tiles:
        return None
    W, H = tiles[0][1].size
    sheet = Image.new("RGB", (W * len(tiles), H), (235, 235, 235))
    d = ImageDraw.Draw(sheet)
    for k, (pos, im) in enumerate(tiles):
        sheet.paste(im, (k * W, 0))
        d.text((k * W + 4, 4), f"{axis}={pos}..{pos + width}", fill=(0, 0, 0))
    sheet.save(out_png)
    return out_png


def compare(ldr, photo, out_png, azimuth=205, elevation=25, resolution=640, samples=10, label="",
            cam=None, target=None, lens=35, board=(32, 32)):
    """Render `ldr` and put it side by side with the reference photo (same height), for
    recreation work (docs/WORKFLOW.md, recreation mode). With cam/target: render from that exact
    camera at the photo's aspect ratio (match the photo's viewpoint!); else an orbit view, cropped."""
    from PIL import Image, ImageDraw
    import tempfile
    tmp = tempfile.mktemp(suffix=".png")
    a = Image.open(photo).convert("RGB")
    if cam:
        hh = resolution
        render_view(ldr, tmp, cam, target, lens, (int(a.width * hh / a.height), hh), samples, board)
        r = Image.open(tmp).convert("RGB")
        h = resolution
        a = a.resize((int(a.width * h / a.height), h))
        out = Image.new("RGB", (a.width * 2 + 4, h + 24), "white")
        out.paste(a, (0, 24)); out.paste(r.resize(a.size), (a.width + 4, 24))
        d = ImageDraw.Draw(out)
        d.text((6, 6), "reference", fill="black")
        d.text((a.width + 10, 6), f"ours {label} cam {cam} -> {target}, {lens} mm", fill="black")
        out.save(out_png)
        return out_png
    render(ldr, tmp, [azimuth], elevation, int(resolution * 1.4), samples)
    r = Image.open(tmp).convert("RGB")
    # crop to the model (pixels that differ from the background corner), small margin
    bg = r.getpixel((2, 2))
    from PIL import ImageChops
    diff = ImageChops.difference(r, Image.new("RGB", r.size, bg)).convert("L").point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    if box:
        m = 10
        r = r.crop((max(0, box[0] - m), max(0, box[1] - m), min(r.width, box[2] + m), min(r.height, box[3] + m)))
    h = resolution
    a = a.resize((int(a.width * h / a.height), h))
    r = r.resize((int(r.width * h / r.height), h))
    out = Image.new("RGB", (a.width + r.width, h + 24), "white")
    out.paste(a, (0, 24)); out.paste(r, (a.width, 24))
    d = ImageDraw.Draw(out)
    d.text((6, 6), "reference", fill="black")
    d.text((a.width + 6, 6), f"ours {label} (az {azimuth}, elev {elevation})", fill="black")
    out.save(out_png)
    return out_png
