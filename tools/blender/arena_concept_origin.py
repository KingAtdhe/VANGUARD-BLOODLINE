"""Boss arena, "The Origin Chamber" — 3D concept render, procedural.

    python tools/blender/arena_concept_origin.py <out.png> [samples] [width]

Inside the Origin core. A floor of black volcanic glass with red light
moving in the fractures beneath it; behind the fighters the Origin heart, a
molten red core caged in slowly turning rings; the chamber walls are a dome
of grown obsidian blades. Frozen in the walls are fragments of the six
bloodline emblems, each caught inside a slab of red-black crystal and lit in
its fighter's colour.
"""
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402  (bpy must load first)
from mathutils import Vector

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/origin.png"
SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 64
WIDTH = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
rnd = random.Random(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
C = sc.collection
HEART = Vector((0, 15, 6.5))


def mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def glass_floor():
    """Black glass: mirror-glossy, with smudged roughness and red fracture
    light (voronoi edges) that seems to sit under the surface."""
    m = bpy.data.materials.new("black_glass")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    b.inputs["Base Color"].default_value = (0.006, 0.005, 0.006, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.7
    sm = node(nt, "ShaderNodeTexNoise", Scale=0.6, Detail=8.0)
    nt.links.new(tc.outputs["Object"], sm.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.03
    rr.inputs["To Max"].default_value = 0.22
    nt.links.new(sm.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    # fractures: distorted voronoi edges, faded out in patches
    warp = node(nt, "ShaderNodeTexNoise", Scale=0.4, Detail=3.0)
    nt.links.new(tc.outputs["Object"], warp.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    nt.links.new(tc.outputs["Object"], add.inputs[0])
    nt.links.new(warp.outputs["Color"], add.inputs[1])
    vor = node(nt, "ShaderNodeTexVoronoi", Scale=0.35)
    vor.feature = "DISTANCE_TO_EDGE"
    nt.links.new(add.outputs[0], vor.inputs["Vector"])
    edge = nt.nodes.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value = 0.035
    edge.inputs["From Max"].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], edge.inputs["Value"])
    fade = node(nt, "ShaderNodeTexNoise", Scale=0.25, Detail=2.0)
    nt.links.new(tc.outputs["Object"], fade.inputs["Vector"])
    fr = nt.nodes.new("ShaderNodeMapRange")
    fr.inputs["From Min"].default_value = 0.5
    fr.inputs["From Max"].default_value = 0.62
    nt.links.new(fade.outputs["Fac"], fr.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(edge.outputs["Result"], mul.inputs[0])
    nt.links.new(fr.outputs["Result"], mul.inputs[1])
    st = nt.nodes.new("ShaderNodeMath")
    st.operation = "MULTIPLY"
    st.inputs[1].default_value = 1.6
    nt.links.new(mul.outputs[0], st.inputs[0])
    b.inputs["Emission Color"].default_value = (1.0, 0.05, 0.02, 1)
    nt.links.new(st.outputs[0], b.inputs["Emission Strength"])
    return m


def obsidian():
    m = bpy.data.materials.new("obsidian")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = node(nt, "ShaderNodeTexNoise", Scale=1.5, Detail=10.0)
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (0.01, 0.008, 0.01, 1)
    r.color_ramp.elements[1].color = (0.06, 0.03, 0.035, 1)
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.08
    rr.inputs["To Max"].default_value = 0.35
    nt.links.new(n.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    return m


FLOOR = glass_floor()
OBS = obsidian()
CRYSTAL = bpy.data.materials.new("red_crystal")
CRYSTAL.use_nodes = True
_cb = CRYSTAL.node_tree.nodes["Principled BSDF"]
_cb.inputs["Base Color"].default_value = (0.25, 0.015, 0.012, 1)
_cb.inputs["Transmission Weight"].default_value = 0.85
_cb.inputs["Roughness"].default_value = 0.22
_cb.inputs["IOR"].default_value = 1.6
_cb.inputs["Emission Color"].default_value = (0.9, 0.05, 0.03, 1)
_cb.inputs["Emission Strength"].default_value = 0.04
CORE = bpy.data.materials.new("core")
CORE.use_nodes = True
_nt = CORE.node_tree
_b = _nt.nodes["Principled BSDF"]
_b.inputs["Base Color"].default_value = (0.03, 0.01, 0.01, 1)
_b.inputs["Roughness"].default_value = 0.4
_tc = _nt.nodes.new("ShaderNodeTexCoord")
_v = node(_nt, "ShaderNodeTexVoronoi", Scale=1.1)
_v.feature = "DISTANCE_TO_EDGE"
_nt.links.new(_tc.outputs["Object"], _v.inputs["Vector"])
_r = _nt.nodes.new("ShaderNodeValToRGB")
_r.color_ramp.elements[0].position = 0.0
_r.color_ramp.elements[0].color = (1.0, 0.55, 0.2, 1)
_r.color_ramp.elements[1].position = 0.09
_r.color_ramp.elements[1].color = (0.12, 0.005, 0.0, 1)
_e = _r.color_ramp.elements.new(0.05)
_e.color = (1.0, 0.1, 0.02, 1)
_nt.links.new(_v.outputs["Distance"], _r.inputs["Fac"])
_nt.links.new(_r.outputs["Color"], _b.inputs["Emission Color"])
_b.inputs["Emission Strength"].default_value = 14.0
CORE_HOT = mat("core_hot", (1, 0.7, 0.4), emit=(1.0, 0.55, 0.25), strength=60.0)
RING = mat("ring_metal", (0.05, 0.03, 0.03), 0.3, 1.0)
RING_GLOW = mat("ring_glow", (0.2, 0, 0), emit=(1.0, 0.1, 0.03), strength=4.0)
TRIM = mat("trim", (0.3, 0.1, 0.06), 0.35, 1.0)

# Bloodline colours for the six frozen emblems.
BLOOD = {
    "kairo": (1.0, 0.25, 0.05),
    "drakon": (0.2, 0.9, 0.3),
    "seraphina": (1.0, 0.85, 0.5),
    "nox": (0.5, 0.25, 1.0),
    "vexa": (1.0, 0.15, 0.55),
    "ryuen": (0.2, 0.5, 1.0),
}


def finish(name, bm, m, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    C.objects.link(o)
    me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return o


def light(kind, loc, energy, color, size=0.3, spot=None):
    d = bpy.data.lights.new(kind, kind)
    d.energy, d.color = energy, color
    if hasattr(d, "shadow_soft_size"):
        d.shadow_soft_size = size
    if kind == "AREA":
        d.size = size
    if spot:
        d.spot_size, d.spot_blend = math.radians(spot), 0.4
    o = bpy.data.objects.new(kind, d)
    o.location = loc
    C.objects.link(o)
    return o


def aim(o, target):
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()


def shard(bm, base, direction, length, width, twist=0.0):
    """A long faceted obsidian blade: a 5-sided prism tapering to a point."""
    base, d = Vector(base), Vector(direction).normalized()
    u = d.orthogonal().normalized()
    v = d.cross(u)
    ring = []
    for i in range(5):
        a = twist + 2 * math.pi * i / 5
        r = width * (0.7 + 0.3 * math.sin(i * 2.1))
        ring.append(bm.verts.new(base + (u * math.cos(a) + v * math.sin(a)) * r))
    mid = []
    for i in range(5):
        a = twist + 0.3 + 2 * math.pi * i / 5
        mid.append(bm.verts.new(base + d * length * 0.6 + (u * math.cos(a) + v * math.sin(a)) * width * 0.55))
    tip = bm.verts.new(base + d * length)
    for i in range(5):
        j = (i + 1) % 5
        bm.faces.new((ring[i], ring[j], mid[j], mid[i]))
        bm.faces.new((mid[i], mid[j], tip))


# ------------------------------------------------------------- floor --
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=34, fill_type="NGON", location=(0, 10, 0))
fl = bpy.context.active_object
fl.data.materials.append(FLOOR)
# fighting stage: a raised disc of the same glass with a trim ring
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=9.0, depth=0.3, location=(0, 3.0, 0.15))
stg = bpy.context.active_object
stg.data.materials.append(FLOOR)
bv = stg.modifiers.new("b", "BEVEL")
bv.width, bv.segments = 0.05, 3
bpy.ops.mesh.primitive_torus_add(major_radius=9.02, minor_radius=0.05, location=(0, 3.0, 0.3))
bpy.context.active_object.data.materials.append(RING_GLOW)

# ---------------------------------------------------- the obsidian dome --
bm = bmesh.new()
for i in range(150):
    a = rnd.uniform(math.radians(-25), math.radians(205))
    r = rnd.uniform(22, 30)
    base = Vector((math.cos(a) * r, 10 + math.sin(a) * r, rnd.uniform(-1, 2)))
    inward = Vector((-math.cos(a), -math.sin(a), 0))
    up = rnd.uniform(1.0, 3.2)
    d = inward * rnd.uniform(0.25, 0.7) + Vector((0, 0, up))
    shard(bm, base, d, rnd.uniform(12, 30), rnd.uniform(0.8, 2.4), rnd.uniform(0, 6))
# second, lower ring of shards leaning outwards to frame the floor edge
for i in range(70):
    a = rnd.uniform(math.radians(-30), math.radians(210))
    r = rnd.uniform(15, 19)
    base = Vector((math.cos(a) * r, 10 + math.sin(a) * r, -0.5))
    out_ = Vector((math.cos(a), math.sin(a), 0))
    shard(bm, base, out_ * rnd.uniform(0.2, 0.9) + Vector((0, 0, 1)), rnd.uniform(2.5, 7), rnd.uniform(0.3, 0.9),
          rnd.uniform(0, 6))
finish("dome_shards", bm, OBS)
# a dark ceiling cap so the dome closes overhead
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=40, location=(0, 10, -6))
cap = bpy.context.active_object
cap.data.materials.append(OBS)
for p in cap.data.polygons:
    p.use_smooth = True

# ---------------------------------------------------------- the heart --
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=2.2, location=HEART)
core = bpy.context.active_object
tex = bpy.data.textures.new("magma", "VORONOI")
tex.noise_scale = 0.5
dsp = core.modifiers.new("d", "DISPLACE")
dsp.texture, dsp.strength = tex, 0.45
core.data.materials.append(CORE)
for p in core.data.polygons:
    p.use_smooth = True
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.2, location=HEART)
bpy.context.active_object.data.materials.append(CORE_HOT)
# the cage: three gyroscope rings at different tilts (they turn in game)
for i, (rx, ry, R) in enumerate(((0.3, 0.0, 3.6), (1.2, 0.5, 4.3), (-0.6, 1.3, 5.0))):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.28, major_segments=96, minor_segments=8,
                                     location=HEART, rotation=(rx, ry, i * 0.7))
    t = bpy.context.active_object
    t.data.materials.append(RING)
    t.scale.z = 0.7          # flattened band, not a round pipe
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.04, major_segments=96, minor_segments=6,
                                     location=HEART, rotation=(rx, ry, i * 0.7))
    g = bpy.context.active_object
    g.data.materials.append(RING_GLOW)
light("POINT", HEART + Vector((0, -2.6, 0)), 9000, (1.0, 0.18, 0.06), size=2.2)
light("POINT", HEART + Vector((0, -4, -2)), 2500, (1.0, 0.35, 0.15), size=1.0)
# a pedestal of crystal beneath the heart, as if it grew the chamber
bm = bmesh.new()
for i in range(16):
    a = rnd.uniform(0, 2 * math.pi)
    base = HEART + Vector((math.cos(a) * rnd.uniform(0.5, 3), math.sin(a) * rnd.uniform(0.5, 3), -HEART.z))
    shard(bm, base, Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 1)), rnd.uniform(1.5, 4.5), rnd.uniform(0.3, 0.8))
finish("pedestal", bm, CRYSTAL)


# ------------------------------------------------- the frozen emblems --
def emblem_shape(kind):
    """Each bloodline's emblem as a flat outline (list of 2D points, unit size).
    All six are original marks made for this game."""
    P = []
    if kind == "kairo":            # a rising flame-blade
        P = [(0, 1), (0.25, 0.35), (0.5, 0.55), (0.3, -0.2), (0.45, -1), (0, -0.55), (-0.45, -1), (-0.3, -0.2),
             (-0.5, 0.55), (-0.25, 0.35)]
    elif kind == "drakon":         # three claw slashes joined at the root
        P = [(-0.8, 1), (-0.5, 1), (0.1, -0.6), (0.25, 1), (0.55, 1), (0.6, -0.9), (0.95, 0.9), (1.0, -1),
             (-0.2, -1)]
    elif kind == "seraphina":      # a single swept wing
        P = [(-1, -0.6), (-0.2, 0.0), (0.2, 0.9), (0.4, 0.4), (0.9, 0.7), (0.7, 0.1), (1.0, 0.0), (0.4, -0.4),
             (0.0, -0.3)]
    elif kind == "nox":            # crescent with an eye-slit
        for k in range(17):
            a = math.radians(40 + k * 280 / 16)
            P.append((math.cos(a), math.sin(a)))
        for k in range(17):
            a = math.radians(320 - k * 280 / 16)
            P.append((0.25 + 0.7 * math.cos(a), 0.7 * math.sin(a)))
    elif kind == "vexa":           # a thorned spiral hook
        for k in range(24):
            t = k / 23
            a = t * 4.2
            r = 1.0 - 0.7 * t
            P.append((r * math.cos(a), r * math.sin(a)))
        for k in range(23, -1, -1):
            t = k / 23
            a = t * 4.2
            r = 0.75 - 0.6 * t
            if k % 6 == 0:
                r += 0.25
            P.append((r * math.cos(a), r * math.sin(a)))
    elif kind == "ryuen":          # a wave breaking inside a ring
        for k in range(24):
            a = 2 * math.pi * k / 24
            P.append((math.cos(a), math.sin(a)))
    return P


def emblem(kind, pos, normal, size):
    color = BLOOD[kind]
    n = Vector(normal).normalized()
    u = Vector((0, 0, 1)).cross(n).normalized()
    v = n.cross(u)
    pos = Vector(pos)
    # the crystal slab it is frozen in
    bm = bmesh.new()
    for i in range(3):
        shard(bm, pos - n * 1.1 + u * rnd.uniform(-0.6, 0.6) - v * size * 1.2,
              v * 1.0 + n * 0.25 + u * rnd.uniform(-0.3, 0.3), size * rnd.uniform(2.6, 3.4), size * 0.8, i * 1.3)
    finish(f"slab_{kind}", bm, CRYSTAL)
    # the emblem fragment: a thick metal outline, broken off on one side
    pts = emblem_shape(kind)
    em = bmesh.new()
    front = pos + n * 0.35                        # proud of the crystal, still caught in it
    vs = [em.verts.new(front + (u * x + v * y) * size) for x, y in pts]
    f = em.faces.new(vs)
    bmesh.ops.triangulate(em, faces=[f])
    cut = rnd.uniform(0.25, 0.55)               # snap a chunk away
    bmesh.ops.bisect_plane(em, geom=em.verts[:] + em.edges[:] + em.faces[:], plane_co=front + u * size * cut,
                           plane_no=u + v * 0.4, clear_outer=True)
    o = finish(f"emblem_{kind}", em, mat(f"emb_{kind}", (0.6, 0.45, 0.25), 0.3, 1.0,
                                           emit=color, strength=3.0))
    s = o.modifiers.new("t", "SOLIDIFY")
    s.thickness = 0.12 * size
    if kind == "ryuen":                          # the wave inside the ring
        wv = bmesh.new()
        ws = []
        for k in range(12):
            t = k / 11
            ws.append(wv.verts.new(front + (u * (-0.7 + 1.4 * t) + v * (0.3 * math.sin(t * 6) - 0.2)) * size + n * 0.05))
        for k in range(11, -1, -1):
            t = k / 11
            ws.append(wv.verts.new(front + (u * (-0.7 + 1.4 * t) + v * (0.3 * math.sin(t * 6) - 0.45)) * size
                                   + n * 0.05))
        f = wv.faces.new(ws)
        finish("ryuen_wave", wv, mat("emb_ryuen_wave", (0.1, 0.2, 0.4), 0.3, 0.5, emit=color, strength=3.0))
    lo = light("POINT", pos - n * 0.4, 120, color, size=1.5)   # glow from inside the slab


WALL = [("kairo", -165), ("drakon", -125), ("seraphina", -95), ("nox", 95), ("vexa", 125), ("ryuen", 165)]
for kind, deg in WALL:
    a = math.radians(deg / 2 + 90)              # spread around the back half
    r = 15.5
    pos = (math.cos(a) * r, 10 + math.sin(a) * r * 0.75, 4.5 + abs(deg) * 0.012)
    normal = (-math.cos(a), -math.sin(a) * 0.6 - 0.4, -0.15)
    emblem(kind, pos, normal, 2.3)

# floating debris, frozen mid-air
bm = bmesh.new()
for i in range(60):
    p = Vector((rnd.uniform(-16, 16), rnd.uniform(6, 22), rnd.uniform(3, 14)))
    if (p - HEART).length < 6:
        continue
    d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
    shard(bm, p, d, rnd.uniform(0.3, 1.4), rnd.uniform(0.08, 0.3), rnd.uniform(0, 6))
finish("debris", bm, OBS)
for i in range(120):                            # embers
    p = Vector((rnd.uniform(-14, 14), rnd.uniform(0, 20), rnd.uniform(0.5, 12)))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rnd.uniform(0.015, 0.04), location=p)
    bpy.context.active_object.data.materials.append(CORE_HOT)

# red haze around the heart
bpy.ops.mesh.primitive_cube_add(location=(0, 10, 7))
hz = bpy.context.active_object
hz.scale = (26, 18, 8)
hm = bpy.data.materials.new("haze")
hm.use_nodes = True
hm.node_tree.nodes.clear()
ho = hm.node_tree.nodes.new("ShaderNodeOutputMaterial")
hv = hm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
hv.inputs["Density"].default_value = 0.006
hv.inputs["Color"].default_value = (1.0, 0.75, 0.7, 1)
hm.node_tree.links.new(hv.outputs[0], ho.inputs["Volume"])
hz.data.materials.append(hm)

# cold rim light falling from a crack in the dome, to split the fighters
# from the red background
rim = light("SPOT", (0, 6, 24), 30000, (0.55, 0.7, 1.0), size=1.5, spot=30)
aim(rim, (0, 3, 0))
for x in (-16, 16):                              # cold light grazing the dome blades
    rl = light("AREA", (x * 0.6, 4, 16), 2500, (0.45, 0.55, 1.0), size=6)
    aim(rl, (x * 1.2, 22, 6))
key = light("AREA", (0, -10, 7), 500, (1.0, 0.55, 0.45), size=6)
aim(key, (0, 3, 1))

w = bpy.data.worlds.new("void")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.0, 0.0, 0.0, 1)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
C.objects.link(cam)
sc.camera = cam
cam.location = (0, -12.5, 2.6)
cam.rotation_euler = (math.radians(86), 0, 0)
cam.data.lens = 22
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.volume_step_rate = 4.0
sc.cycles.max_bounces = 6
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - High Contrast"
sc.view_settings.exposure = float(os.environ.get("EXPOSURE", "-0.8"))
sc.render.resolution_x = WIDTH
sc.render.resolution_y = int(WIDTH * 9 / 16)
sc.render.filepath = out
if os.environ.get("NORENDER"):
    raise SystemExit
bpy.ops.render.render(write_still=True)
print("saved", out)
