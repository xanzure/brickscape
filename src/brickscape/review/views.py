"""The standard render set: the same four camera angles for every build, so builds can be
compared fairly (the benchmark depends on this).

Views (renderer azimuth, elevation 30 degrees): front-left 225, front-right 315,
back-right 45, back-left 135. Front = the -z edge (z = 0 in plans).
"""
import os, subprocess, tempfile
from brickscape.config import LDRAW, blender, blender_script

VIEWS = (("front-left", 225), ("front-right", 315), ("back-right", 45), ("back-left", 135))
ELEVATION = 30


def standard_views(ldr, out_dir, resolution=640, samples=16, timeout=1800):
    """Render the 4 standard views -> {view name: png path, "sheet": 2x2 sheet path}."""
    from PIL import Image, ImageDraw
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        prefix = os.path.join(td, "v")
        cmd = [blender(), "-b", "--factory-startup", "-P", blender_script(), "--", "--ldr", os.path.abspath(ldr),
               "--out", prefix, "--azimuths=" + ",".join(str(a) for _, a in VIEWS), "--elevation", str(ELEVATION),
               "--samples", str(samples), "--resolution", str(resolution), "--ldraw-dir", LDRAW]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = {}
        for i, (name, _) in enumerate(VIEWS):
            src = f"{prefix}_{i}.png"
            if not os.path.exists(src):
                raise RuntimeError("render failed:\n" + "\n".join((p.stdout + p.stderr).splitlines()[-12:]))
            dst = os.path.join(out_dir, f"view_{name}.png")
            _crop(Image.open(src).convert("RGB")).save(dst)
            out[name] = dst
    ims = [Image.open(out[n]) for n, _ in VIEWS]
    w, h = max(i.width for i in ims), max(i.height for i in ims)
    sheet = Image.new("RGB", (2 * w, 2 * h), ims[0].getpixel((1, 1)))
    d = ImageDraw.Draw(sheet)
    for k, (im, (name, _)) in enumerate(zip(ims, VIEWS)):
        x, y = (k % 2) * w, (k // 2) * h
        sheet.paste(im, (x + (w - im.width) // 2, y + (h - im.height) // 2))
        d.text((x + 10, y + 10), name, fill=(40, 40, 40))
    out["sheet"] = os.path.join(out_dir, "views.png")
    sheet.save(out["sheet"])
    return out


def _crop(im, margin=0.05):
    """Crop a render to the model (plus a margin), keeping the background colour."""
    from PIL import Image, ImageChops
    bg = Image.new("RGB", im.size, im.getpixel((1, 1)))
    box = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 10 else 0).getbbox()
    if not box:
        return im
    m = int(margin * max(box[2] - box[0], box[3] - box[1]))
    return im.crop((max(0, box[0] - m), max(0, box[1] - m), min(im.width, box[2] + m), min(im.height, box[3] + m)))
