"""Blender-side script (runs INSIDE Blender): render an LDraw model from an explicit camera, to
match a reference photo's viewpoint. Import step adapted from ldraw_mcp's blender_script.py (MIT).

  blender -b --factory-startup -P blender_view.py -- --ldr M.ldr --out out.png \
      --board 32,32 --cam x,z,h --target x,z,h --lens 35 --size 1066x1600 --samples 12

Board coordinates: x studs left->right, z studs front->back (z=0 front edge), h in bricks above the
baseplate top. Blender X = board x, Blender Y = board z (LDraw front -Z -> Blender -Y), Z up.
"""
import argparse, math, sys
from pathlib import Path
import bpy, mathutils


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--ldr", required=True); p.add_argument("--out", required=True)
    p.add_argument("--board", default="32,32"); p.add_argument("--cam", required=True)
    p.add_argument("--target", required=True); p.add_argument("--lens", type=float, default=35)
    p.add_argument("--size", default="800x800"); p.add_argument("--samples", type=int, default=12)
    p.add_argument("--ldraw-dir", default=str(Path.home() / ".ldraw"))
    p.add_argument("--ldbox", help="model bbox in LDraw coords lox,loy,loz,hix,hiy,hiz; cam/target are then LDraw coords")
    return p.parse_args(argv)


def enable_addon():
    import addon_utils
    for name in ("io_scene_importldraw", "importldraw"):
        if addon_utils.enable(name, default_set=True) is not None:
            return
    raise RuntimeError("ImportLDraw addon not found")


def bounds():
    lo = [1e9] * 3; hi = [-1e9] * 3
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    return lo, hi


def main():
    a = parse()
    enable_addon()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    enable_addon()
    world = bpy.data.worlds.new("World"); world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    bpy.context.scene.world = world
    bpy.ops.import_scene.importldraw(filepath=a.ldr, ldrawPath=a.ldraw_dir, addEnvironment=False,
                                     positionCamera=False, importCameras=False, positionOnGround=True,
                                     useLogoStuds=False, smoothParts=True, addGaps=True, bevelEdges=True,
                                     look="normal")
    # the baseplate gives the board frame: find the lowest, widest mesh extents
    lo, hi = bounds()
    W, D = (float(v) for v in a.board.split(","))
    # baseplates span the board; plants etc. may overhang a little, so use the baseplate objects
    blo = [1e9] * 3; bhi = [-1e9] * 3
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and ("3811" in o.name or "3867" in o.name or "4186" in o.name):
            for c in o.bound_box:
                w = o.matrix_world @ mathutils.Vector(c)
                for i in range(3):
                    blo[i] = min(blo[i], w[i]); bhi[i] = max(bhi[i], w[i])
    if blo[0] < 1e8:
        lo2, hi2 = blo, bhi
    else:
        lo2, hi2 = lo, hi
    stud = (hi2[0] - lo2[0]) / W
    ground = hi2[2] if blo[0] < 1e8 else lo[2]

    if a.ldbox:
        lb = [float(v) for v in a.ldbox.split(",")]
        s = (hi[0] - lo[0]) / (lb[3] - lb[0])
        def P(q):
            X, Y, Z = (float(v) for v in q.split(","))
            # LDraw x -> Blender X, LDraw z -> Blender Y (front -Z -> -Y), LDraw -y (up) -> Blender Z
            return mathutils.Vector((lo[0] + (X - lb[0]) * s, lo[1] + (Z - lb[2]) * s, lo[2] + (lb[4] - Y) * s))
    else:
        def P(s):
            x, z, h = (float(v) for v in s.split(","))
            return mathutils.Vector((lo2[0] + x * stud, lo2[1] + z * stud, ground + h * stud * 1.2))

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.samples = a.samples; sc.cycles.device = "CPU"
    w, h = (int(v) for v in a.size.split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", type="SUN"))
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(-40))
    sc.collection.objects.link(sun)
    cd = bpy.data.cameras.new("Cam"); cd.lens = a.lens
    cd.sensor_fit = "AUTO"
    span = max(b - c for b, c in zip(hi, lo))
    cd.clip_start = span / 1000; cd.clip_end = span * 100
    cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = P(a.cam)
    cam.rotation_euler = (P(a.target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = a.out
    bpy.ops.render.render(write_still=True)
    print("RENDERED", a.out)


if __name__ == "__main__":
    main()
