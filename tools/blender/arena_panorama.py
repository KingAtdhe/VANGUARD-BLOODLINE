"""Renders an arena's far scenery as a 360-degree panorama for the Godot sky.

    python tools/blender/arena_panorama.py <neon|temple> <out.png> [width] [samples]

Builds the approved concept scene (tools/blender/arena_concept_*.py), removes
everything the game already has as real geometry (the fighting area, the
hero pieces, near props), and renders the rest from the gameplay camera
position with an equirectangular camera. Rendered in Cycles like the
concepts, so the backdrop keeps their detail at almost no cost on a phone.
"""
import math
import os
import runpy
import sys

import bpy

ARENA = sys.argv[1]
OUT = sys.argv[2]
WIDTH = int(sys.argv[3]) if len(sys.argv) > 3 else 2048
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 16
HERE = os.path.dirname(os.path.abspath(__file__))
CONCEPT = {"neon": "arena_concept_neon.py", "temple": "arena_concept_sanctuary.py"}[ARENA]

os.environ["NORENDER"] = "1"
sys.argv = [CONCEPT, "/tmp/unused.png", str(SAMPLES), "64"]
try:
    runpy.run_path(os.path.join(HERE, CONCEPT), run_name="__main__")
except SystemExit:
    pass


def mats(o):
    return {m.name.split(".")[0] for m in getattr(o.data, "materials", []) if m}


def min_y(o):
    return min((o.matrix_world @ __import__("mathutils").Vector(c)).y for c in o.bound_box)


drop = []
for o in bpy.data.objects:
    if o.type != "MESH":
        continue
    ms = mats(o)
    if ARENA == "neon":
        hero = ms & {"casing", "rib", "origin_core", "origin_glow", "steam", "street_mist"}
        if hero or ms & {"haze", "wanted", "wanted_bar"} or min_y(o) < 13.0 \
                or o.name.lower().startswith(("bill", "wanted", "poster")):
            drop.append(o)
    else:
        if not (ms & {"cloud_sea", "haze"}):
            drop.append(o)
for o in drop:
    bpy.data.objects.remove(o, do_unlink=True)
if ARENA == "neon":
    # The concept city only fills the view ahead; ring the camera with it.
    from mathutils import Matrix
    pivot = Matrix.Translation((0.0, -10.0, 0.0))
    city = [o for o in bpy.data.objects if o.type == "MESH"]
    for ang in (95, 180, 265):
        R = pivot @ Matrix.Rotation(math.radians(ang), 4, "Z") @ pivot.inverted()
        for o in city:
            c = o.copy()
            c.matrix_world = R @ Matrix.Translation((0, 6.0, 0)) @ o.matrix_world
            bpy.context.scene.collection.objects.link(c)
if ARENA == "temple":
    # The concept only dressed the view in front of the camera; the sky
    # dome needs clouds all the way round, and some far islands for depth.
    import random
    rnd = random.Random(5)
    sea = next(o for o in bpy.data.objects if "cloud_sea" in mats(o) and o.type == "MESH" and o.dimensions.x > 100)
    sea.location = (0, 0, -7)
    sea.scale = (sea.scale.x * 2.2, sea.scale.y * 5.5, sea.scale.z)
    towers = [o for o in bpy.data.objects if "cloud_sea" in mats(o) and o is not sea]
    for i in range(16):
        src = rnd.choice(towers)
        c = src.copy()
        c.data = src.data
        bpy.context.scene.collection.objects.link(c)
        a_ = 2 * math.pi * i / 16 + rnd.uniform(-0.15, 0.15)
        d = rnd.uniform(140, 300)
        c.location = (math.cos(a_) * d, math.sin(a_) * d, rnd.uniform(-2, 10))
        c.scale = [v * rnd.uniform(0.7, 1.6) for v in src.scale]
    rock_m = bpy.data.materials.new("far_rock")
    rock_m.use_nodes = True
    rock_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.1, 0.1, 1)
    for i in range(9):                           # distant floating islands
        a_ = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(90, 200)
        bpy.ops.mesh.primitive_cone_add(vertices=9, radius1=rnd.uniform(4, 9), radius2=0.3, depth=rnd.uniform(10, 18),
                                        location=(math.cos(a_) * d, math.sin(a_) * d, rnd.uniform(6, 20)),
                                        rotation=(math.pi, 0, rnd.uniform(0, 3)))
        r = bpy.context.active_object
        r.data.materials.append(rock_m)
        bpy.ops.mesh.primitive_cylinder_add(vertices=9, radius=r.dimensions.x * 0.5, depth=0.6,
                                            location=(r.location.x, r.location.y, r.location.z + r.dimensions.z / 2))
        bpy.context.active_object.data.materials.append(rock_m)
if os.environ.get("PANO_DEBUG"):
    from collections import Counter
    print("[pano] kept materials", Counter(m for o in bpy.data.objects if o.type == "MESH" for m in mats(o)).most_common(40))
print(f"[pano] removed {len(drop)} near/hero objects, kept {sum(1 for o in bpy.data.objects if o.type == 'MESH')}")

sc = bpy.context.scene
cam = sc.camera
cam.location = (0.0, -10.0, 1.6)          # gameplay camera position (Godot z = 10, y = 1.6)
cam.rotation_euler = (math.radians(90), 0, 0)
cam.data.type = "PANO"
try:
    cam.data.panorama_type = "EQUIRECTANGULAR"
except AttributeError:
    cam.data.cycles.panorama_type = "EQUIRECTANGULAR"
sc.render.resolution_x = WIDTH
sc.render.resolution_y = WIDTH // 2
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("saved", OUT)
