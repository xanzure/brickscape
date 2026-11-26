"""Blender-side script (runs INSIDE Blender): instruction step renders and part thumbnails.

  blender -b --factory-startup -P blender_steps.py -- --ldr ordered.ldr --steps 5,12,20 \
      --out DIR [--parts parts.txt] [--size 900] [--samples 12]

The model's part lines must be in build order. ImportLDraw names objects 00001_..., 00002_...
in file order, so step k shows objects 1..steps[k]. Every step uses the same camera (framed on
the finished model, front-left, 35 degrees up). --parts: a text file of single-part .ldr paths,
each rendered as a small thumbnail with a transparent background.
Import set-up adapted from ldraw-mcp's blender_script.py (MIT).
"""
import argparse, math, sys
from pathlib import Path
import bpy, mathutils


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--ldr", required=True); p.add_argument("--steps", required=True)
    p.add_argument("--out", required=True); p.add_argument("--parts")
    p.add_argument("--size", type=int, default=900); p.add_argument("--samples", type=int, default=12)
    p.add_argument("--ldraw-dir", default=str(Path.home() / ".ldraw"))
    return p.parse_args(argv)


def enable():
    import addon_utils
    for n in ("io_scene_importldraw", "importldraw"):
        if addon_utils.enable(n, default_set=True) is not None:
            return
    raise RuntimeError("ImportLDraw addon not found")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    enable()
    w = bpy.data.worlds.new("World"); w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    bpy.context.scene.world = w


def load(path, ldraw):
    bpy.ops.import_scene.importldraw(filepath=path, ldrawPath=ldraw, addEnvironment=False, positionCamera=False,
                                     importCameras=False, positionOnGround=True, useLogoStuds=False,
                                     smoothParts=True, addGaps=True, bevelEdges=True, look="normal")


def bounds(objs):
    lo, hi = [1e9] * 3, [-1e9] * 3
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                lo[i], hi[i] = min(lo[i], w[i]), max(hi[i], w[i])
    return lo, hi


def setup(size, samples, transparent=False):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.samples = samples; sc.cycles.device = "CPU"
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.film_transparent = transparent
    if transparent:
        sc.render.image_settings.color_mode = "RGBA"
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", type="SUN"))
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(-40))
    sc.collection.objects.link(sun)
    cd = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
    return sc, cam


def aim(cam, lo, hi, az=225, el=35):
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    span = max(b - a for a, b in zip(lo, hi))
    d = span * 2.0
    a, e = math.radians(az), math.radians(el)
    cam.location = (c[0] + d * math.cos(e) * math.cos(a), c[1] + d * math.cos(e) * math.sin(a), c[2] + d * math.sin(e))
    cam.rotation_euler = (mathutils.Vector(c) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    cam.data.clip_start, cam.data.clip_end = d / 100, d * 100


def main():
    a = args()
    reset(); load(a.ldr, a.ldraw_dir)
    parts = sorted((o for o in bpy.context.scene.objects if o.type == "MESH" and o.name[:5].isdigit()),
                   key=lambda o: o.name)
    sc, cam = setup(a.size, a.samples)
    aim(cam, *bounds(parts))
    for k, n in enumerate(int(v) for v in a.steps.split(",")):
        for i, o in enumerate(parts):
            o.hide_render = i >= n
        sc.render.filepath = f"{a.out}/step_{k + 1:03d}.png"
        bpy.ops.render.render(write_still=True)
        print("RENDERED", sc.render.filepath)
    if a.parts:
        for line in open(a.parts):
            path = line.strip()
            if not path:
                continue
            reset(); load(path, a.ldraw_dir)
            objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
            sc, cam = setup(220, max(6, a.samples // 2), transparent=True)
            aim(cam, *bounds(objs), az=225, el=30)
            cam.data.lens = 40
            sc.render.filepath = path[:-4] + ".png"
            bpy.ops.render.render(write_still=True)
            print("RENDERED", sc.render.filepath)


if __name__ == "__main__":
    main()
