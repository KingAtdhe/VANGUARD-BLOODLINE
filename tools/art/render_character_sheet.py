"""3D concept renders of a fighter (run with Blender's Python / bpy).

    python tools/art/render_character_sheet.py <model.glb> <FIGHTER_ID> <out_dir>

Same method as the Aurelia Island building sheets: the real model is posed,
lit and rendered (Cycles), then composed into a presentation sheet by
compose_character_sheet.py. Rendered in the cel style of the approved 2D
art: toon shading, a rim light and inked outlines (Freestyle).
"""

import math
import sys

import bpy
from mathutils import Matrix, Vector

path, FID, out = sys.argv[-3], sys.argv[-2].upper(), sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = 60   # the game's tick rate, so frame numbers match move frames
bpy.ops.import_scene.gltf(filepath=path)
sc = bpy.context.scene
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]

# ------------------------------------------------------------ materials --
GLOSS = {"Skin": 0.03, "Cloth": 0.0, "Cloth2": 0.06, "Hair": 0.1, "Gear": 0.2, "Accent": 0.0}
meshes = [o for o in meshes if len(o.data.polygons) > 500]
print("[sheet] meshes", [(o.name, [c.name for c in o.data.color_attributes], [a.name for a in o.data.attributes if a.data_type in ("FLOAT_COLOR", "BYTE_COLOR")]) for o in meshes])
COLOR_LAYER = next((c.name for o in meshes for c in o.data.color_attributes), "Color")
print("[sheet] colour layer", COLOR_LAYER)
for m in bpy.data.materials:
    slot = m.name.split("_")[-1].split(".")[0]
    if slot not in GLOSS:
        continue
    nt = m.node_tree
    old_bsdf = nt.nodes.get("Principled BSDF")
    accent = (1.0, 0.07, 0.05, 1.0)
    if old_bsdf:
        e = tuple(old_bsdf.inputs["Emission Color"].default_value)
        bcol = tuple(old_bsdf.inputs["Base Color"].default_value)
        accent = e if sum(e[:3]) > 0.05 else bcol
    nt.nodes.clear()
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    if slot == "Accent":
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = accent
        em.inputs["Strength"].default_value = 3.5
        nt.links.new(em.outputs[0], outn.inputs["Surface"])
        continue
    col = nt.nodes.new("ShaderNodeVertexColor")
    col.layer_name = COLOR_LAYER
    lift = nt.nodes.new("ShaderNodeMixRGB")          # keep darks readable under cel shading
    lift.blend_type = "ADD"
    lift.inputs["Fac"].default_value = 1.0
    lift.inputs["Color2"].default_value = (0.004, 0.004, 0.008, 1)
    dark = nt.nodes.new("ShaderNodeMixRGB")      # cloth reads near-black, as in the 2D art
    dark.blend_type = "MULTIPLY"
    dark.inputs["Fac"].default_value = 1.0
    k = 0.5 if slot in ("Cloth2", "Hair") else 1.0
    dark.inputs["Color2"].default_value = (k, k, k * 1.08, 1)
    nt.links.new(col.outputs["Color"], dark.inputs["Color1"])
    nt.links.new(dark.outputs[0], lift.inputs["Color1"])
    toon = nt.nodes.new("ShaderNodeBsdfToon")
    toon.component = "DIFFUSE"
    toon.inputs["Size"].default_value = 0.62
    toon.inputs["Smooth"].default_value = 0.06
    nt.links.new(lift.outputs[0], toon.inputs["Color"])
    spec = nt.nodes.new("ShaderNodeBsdfToon")
    spec.component = "GLOSSY"
    spec.inputs["Size"].default_value = 0.2
    spec.inputs["Smooth"].default_value = 0.08
    spec.inputs["Color"].default_value = (1, 1, 1, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = GLOSS[slot]
    nt.links.new(toon.outputs[0], mix.inputs[1])
    nt.links.new(spec.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], outn.inputs["Surface"])

for o in meshes:
    for p in o.data.polygons:
        p.use_smooth = True

# ------------------------------------------------------------- lighting --
def sun(direction, energy, color, angle=2.0):
    l = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    l.data.energy, l.data.color, l.data.angle = energy, color, math.radians(angle)
    l.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(l)
    return l


key = sun((0.55, 0.75, -0.55), 3.6, (1.0, 0.97, 0.93))
rim = sun((-0.5, -0.9, -0.15), 2.4, (1.0, 0.45, 0.4), 6.0)
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.44, 0.56, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.85

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 40
sc.cycles.use_denoising = False
sc.render.film_transparent = True
sc.view_settings.view_transform = "Standard"
sc.render.use_freestyle = True
sc.render.line_thickness = 2.1
vl = bpy.context.view_layer
vl.use_freestyle = True
fs = vl.freestyle_settings
fs.crease_angle = math.radians(128)
ls = fs.linesets[0] if fs.linesets else fs.linesets.new("ink")
ls.select_silhouette = ls.select_border = ls.select_crease = True
ls.select_material_boundary = True
if ls.linestyle is None:
    ls.linestyle = bpy.data.linestyles.new("ink")
ls.linestyle.color = (0.04, 0.03, 0.04)
ls.linestyle.thickness = 2.1

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def look(pos, tgt, lens=None, ortho=None):
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type, cam.data.ortho_scale = "ORTHO", ortho
    else:
        cam.data.type, cam.data.lens = "PERSP", lens


def pose(action=None, frame=0, arms_out=0.0):
    arm.animation_data.action = bpy.data.actions.get(f"{FID}_{action}") if action else None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    sc.frame_set(frame)
    if arms_out and not action:
        bpy.context.view_layer.update()
        for name, sgn in (("LeftUpperArm", 1), ("RightUpperArm", -1)):
            pb = arm.pose.bones[name]
            head = pb.head.copy()
            rot = Matrix.Translation(head) @ Matrix.Rotation(-math.radians(arms_out) * sgn, 4, "Y") @ Matrix.Translation(-head)
            pb.matrix = rot @ pb.matrix
            bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def shot(name, res):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = f"{out}/{FID.lower()}_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("[sheet] rendered", name)


H = 1.8

pose(arms_out=16)
look((0, -8, 0.93), (0, 0, 0.93), ortho=2.06)
shot("front", (900, 1500))
key.rotation_euler = Vector((-0.55, -0.75, -0.55)).to_track_quat("-Z", "Y").to_euler()
rim.rotation_euler = Vector((0.5, 0.9, -0.15)).to_track_quat("-Z", "Y").to_euler()
look((0, 8, 0.93), (0, 0, 0.93), ortho=2.06)
shot("back", (900, 1500))
key.rotation_euler = Vector((0.55, 0.75, -0.55)).to_track_quat("-Z", "Y").to_euler()
rim.rotation_euler = Vector((-0.5, -0.9, -0.15)).to_track_quat("-Z", "Y").to_euler()
look((0.25, -1.45, 1.72), (0, 0, 1.69), lens=85)
shot("face", (1000, 1000))
look((0.5, -1.9, 1.38), (0, 0, 1.3), lens=70)
shot("torso", (1000, 1000))
look((-0.9, -1.5, 0.95), (-0.26, -0.05, 0.9), lens=85)
shot("gauntlet", (800, 800))
look((-0.9, -1.9, 0.55), (-0.1, -0.05, 0.42), lens=70)
shot("legs", (800, 1000))
# action poses from the game's own animations
pose("IDLE_A", 0)
look((2.2, -4.0, 1.25), (0, -0.05, 0.93), lens=85)
shot("stance", (1100, 1500))
pose("ATTACK_HEAVY_01", 12)
look((3.4, -2.9, 1.2), (0, -0.45, 0.95), lens=85)
shot("punch", (1500, 1500))
pose("KICK_01", 9)
look((3.4, -2.7, 1.1), (0, -0.5, 0.9), lens=80)
shot("kick", (1500, 1500))
