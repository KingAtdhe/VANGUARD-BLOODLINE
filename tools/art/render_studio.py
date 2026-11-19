"""Studio renders of a fighter GLB (as imported by the game: textures, normal
maps, rig, animations). Grey cyclorama, soft key, fill and rim lights.

    python tools/art/render_studio.py <model.glb> <out_prefix> [shot,shot,...]
shots: front, back, side, quarter, stance, punch, kick, guard, face, face3q, hands
"""
import math
import os
import sys

import bpy
from mathutils import Vector

path, prefix = sys.argv[1], sys.argv[2]
ONLY = sys.argv[3].split(",") if len(sys.argv) > 3 else None
SCALE = float(os.environ.get("SCALE", "1"))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 60
bpy.ops.import_scene.gltf(filepath=path)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")

# cyclorama
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
bpy.ops.mesh.primitive_cylinder_add(radius=6, depth=12, location=(0, 0, 6), vertices=96, end_fill_type="NOTHING")
cyc = bpy.context.active_object
cyc.scale = (1, 1, 1)
for ob, c in ((floor, (0.16, 0.16, 0.17)), (cyc, (0.2, 0.2, 0.21))):
    m = bpy.data.materials.new(ob.name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = 0.55
    ob.data.materials.append(m)


def area(name, loc, energy, size, color=(1, 1, 1), shape="RECTANGLE", size_y=None, tgt=(0, 0, 1.1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.color, ld.shape = energy, color, shape
    ld.size = size
    ld.size_y = size_y or size
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(o)
    return o


# Photo-studio lighting: big soft key, broad fill, two kicker strips behind,
# a hair light from above and a soft sky so the shadows never go to black.
area("key", (2.0, -2.6, 2.6), 520, 1.4, (1.0, 0.95, 0.88), size_y=2.0, tgt=(0, 0, 1.2))
area("fill", (-2.8, -2.0, 1.4), 140, 2.5, (0.82, 0.88, 1.0), size_y=2.5)
area("kick_l", (-1.6, 1.9, 1.3), 420, 0.35, (0.9, 0.95, 1.0), size_y=2.2, tgt=(0, 0, 1.0))
area("kick_r", (1.7, 1.8, 1.3), 360, 0.35, (1.0, 0.92, 0.85), size_y=2.2, tgt=(0, 0, 1.0))
area("hair", (0.0, 0.6, 3.4), 160, 1.0, (1.0, 0.97, 0.95), tgt=(0, 0, 1.7))
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
bgn = w.node_tree.nodes["Background"]
bgn.inputs[0].default_value = (0.62, 0.64, 0.68, 1)
bgn.inputs[1].default_value = 0.12
# presentation-only shading (Cycles): light through the skin, hair sheen
for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    bs = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bs is None:
        continue
    if m.name.endswith("_Skin"):
        bs.inputs["Subsurface Weight"].default_value = 0.35
        bs.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.18)
        bs.inputs["Subsurface Scale"].default_value = 0.012
        bs.inputs["Roughness"].default_value = 0.55
        bs.inputs["Specular IOR Level"].default_value = 0.4
    if m.name.endswith("_Hair"):
        bs.inputs["Roughness"].default_value = 0.5
        bs.inputs["Specular IOR Level"].default_value = 0.35
    if m.name.endswith(("_Cloth", "_Cloth2")):
        bs.inputs["Sheen Weight"].default_value = 0.35
        bs.inputs["Sheen Roughness"].default_value = 0.35
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = int(os.environ.get("SAMPLES", "48"))
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.exposure = float(os.environ.get("EXPOSURE", "-1.4"))
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def pose(action=None, frame=0):
    arm.animation_data.action = bpy.data.actions.get(action) if action else None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    sc.frame_set(frame)


def shot(name, pos, tgt, lens, res, action=None, frame=0):
    if ONLY and name not in ONLY:
        return
    pose(action, frame)
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    sc.render.resolution_x, sc.render.resolution_y = int(res[0] * SCALE), int(res[1] * SCALE)
    sc.render.filepath = f"{prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("[studio]", name, flush=True)


T = (0, 0, 0.92)
shot("front", (0, -4.4, 1.0), T, 60, (1000, 1400))
shot("back", (0, 5.2, 1.0), T, 50, (1000, 1400))
shot("side", (5.2, 0, 1.0), T, 50, (1000, 1400))
shot("quarter", (3.4, -3.9, 1.1), T, 50, (1000, 1400))
shot("stance", (2.2, -3.3, 1.15), (0, -0.1, 0.95), 60, (1000, 1400), "KAIRO_IDLE_A", 0)
shot("guard", (2.0, -4.4, 1.2), (0, -0.1, 0.95), 50, (1000, 1400), "KAIRO_BLOCK_HIGH", 12)
shot("punch", (3.6, -3.0, 1.1), (0, -0.4, 0.95), 50, (1200, 1200), "KAIRO_ATTACK_HEAVY_01", 12)
shot("kick", (3.8, -2.8, 1.0), (0, -0.4, 0.85), 50, (1200, 1200), "KAIRO_KICK_01", 9)
shot("torso", (0.9, -1.9, 1.35), (0, 0, 1.3), 85, (1000, 1000))
shot("face", (0.0, -1.5, 1.69), (0, 0, 1.68), 105, (900, 900))
shot("face3q", (0.9, -1.25, 1.71), (0, 0, 1.68), 105, (900, 900))
shot("hands", (1.4, -1.6, 0.95), (0.27, -0.03, 0.9), 105, (900, 900))
