"""Ascendant Arena, "The Pit" — 3D concept render, procedural.

    python tools/blender/arena_concept_pit.py <out.png> [samples] [width]

A tournament ring sunk into an abandoned open-pit mine that once dug Origin
ore. The crowd stands on the stepped quarry benches, two old lattice mining
cranes hold the stage-light rigs over the ring, and the floor of bedrock
carries a huge carved crest: a V of two blades inside a circle broken into
six segments (one per bloodline). Red Origin veins still glow in the walls.
Dusk, dust in the air.
"""
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402  (bpy must load first)
from mathutils import Vector

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pit.png"
SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 64
WIDTH = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
rnd = random.Random(23)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
C = sc.collection
PIT = Vector((0, 10, 0))          # centre of the quarry bowl


# ------------------------------------------------------------ materials --
def mat(name, color, rough=0.6, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def rock_mat():
    """Quarry wall: horizontal strata in ochre/rust/grey, plus thin glowing
    red Origin veins that follow the strata."""
    m = bpy.data.materials.new("strata")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = node(nt, "ShaderNodeTexWave", Scale=0.35, Distortion=6.0, Detail=6.0)
    wave.bands_direction = "Z"
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].color, el[1].color = (0.16, 0.1, 0.07, 1), (0.42, 0.3, 0.2, 1)
    e = el.new(0.45)
    e.color = (0.3, 0.16, 0.08, 1)
    e = el.new(0.7)
    e.color = (0.24, 0.23, 0.22, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    noise = node(nt, "ShaderNodeTexNoise", Scale=2.5, Detail=12.0)
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.6
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    nt.links.new(noise.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    # veins: a thin band of a second wave, broken up by noise
    vw = node(nt, "ShaderNodeTexWave", Scale=0.11, Distortion=9.0, Detail=4.0)
    vw.bands_direction = "Z"
    nt.links.new(tc.outputs["Object"], vw.inputs["Vector"])
    band = nt.nodes.new("ShaderNodeMapRange")
    band.inputs["From Min"].default_value = 0.975
    band.inputs["From Max"].default_value = 0.995
    nt.links.new(vw.outputs["Fac"], band.inputs["Value"])
    vn = node(nt, "ShaderNodeTexNoise", Scale=0.8, Detail=2.0)
    nt.links.new(tc.outputs["Object"], vn.inputs["Vector"])
    gate = nt.nodes.new("ShaderNodeMapRange")
    gate.inputs["From Min"].default_value = 0.6
    gate.inputs["From Max"].default_value = 0.64
    nt.links.new(vn.outputs["Fac"], gate.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(band.outputs["Result"], mul.inputs[0])
    nt.links.new(gate.outputs["Result"], mul.inputs[1])
    s = nt.nodes.new("ShaderNodeMath")
    s.operation = "MULTIPLY"
    s.inputs[1].default_value = 3.0
    nt.links.new(mul.outputs[0], s.inputs[0])
    b.inputs["Emission Color"].default_value = (1.0, 0.08, 0.03, 1)
    nt.links.new(s.outputs[0], b.inputs["Emission Strength"])
    bump = node(nt, "ShaderNodeBump", Strength=0.6)
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.92
    return m


def floor_mat():
    """Cut bedrock: dark, scuffed, with tool marks and dust in low spots."""
    m = bpy.data.materials.new("bedrock")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = node(nt, "ShaderNodeTexNoise", Scale=1.6, Detail=14.0, Roughness=0.62)
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (0.05, 0.045, 0.045, 1)
    r.color_ramp.elements[1].color = (0.22, 0.17, 0.13, 1)
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    sc_ = node(nt, "ShaderNodeTexWave", Scale=4.0, Distortion=1.5)
    nt.links.new(tc.outputs["Object"], sc_.inputs["Vector"])      # saw-cut marks
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.35
    rr.inputs["To Max"].default_value = 0.75
    nt.links.new(n.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    bump = node(nt, "ShaderNodeBump", Strength=0.15)
    nt.links.new(sc_.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def rust_mat(name, paint=(0.42, 0.29, 0.07)):
    """Old painted steel, rusted through on edges and in patches."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = node(nt, "ShaderNodeTexNoise", Scale=1.2, Detail=10.0)
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    t = nt.nodes.new("ShaderNodeMapRange")
    t.inputs["From Min"].default_value = 0.58
    t.inputs["From Max"].default_value = 0.66
    nt.links.new(n.outputs["Fac"], t.inputs["Value"])
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.inputs[6].default_value = (*paint, 1)
    mx.inputs[7].default_value = (0.2, 0.07, 0.03, 1)
    nt.links.new(t.outputs["Result"], mx.inputs["Factor"])
    # vertical grime streaks: noise stretched along Z
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (6.0, 6.0, 0.4)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    gn = node(nt, "ShaderNodeTexNoise", Scale=2.0, Detail=6.0)
    nt.links.new(mp.outputs[0], gn.inputs["Vector"])
    gr = nt.nodes.new("ShaderNodeMapRange")
    gr.inputs["From Min"].default_value = 0.45
    gr.inputs["From Max"].default_value = 0.75
    gr.inputs["To Max"].default_value = 0.7
    nt.links.new(gn.outputs["Fac"], gr.inputs["Value"])
    gm = nt.nodes.new("ShaderNodeMix")
    gm.data_type = "RGBA"
    gm.inputs[7].default_value = (0.05, 0.035, 0.025, 1)
    nt.links.new(gr.outputs["Result"], gm.inputs["Factor"])
    nt.links.new(mx.outputs[2], gm.inputs[6])
    nt.links.new(gm.outputs[2], b.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.5
    rr.inputs["To Max"].default_value = 0.9
    nt.links.new(t.outputs["Result"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    b.inputs["Metallic"].default_value = 0.4
    return m


ROCK = rock_mat()
FLOOR = floor_mat()
CRANE = rust_mat("crane_paint")
STEEL = mat("steel", (0.08, 0.08, 0.085), 0.45, 0.9)
HAZARD = rust_mat("hazard", (0.5, 0.33, 0.03))
GRAVEL = mat("gravel", (0.19, 0.14, 0.1), 0.95)
GOLD = mat("crest_gold", (0.75, 0.5, 0.18), 0.3, 1.0)
VEIN = mat("crest_vein", (0.1, 0.0, 0.0), 0.5, emit=(1.0, 0.07, 0.02), strength=5.0)
LAMP = mat("lamp", (1, 1, 1), emit=(1.0, 0.9, 0.75), strength=40.0)
TORCH = mat("torch", (1, 1, 1), emit=(1.0, 0.55, 0.2), strength=25.0)
PHONE = mat("phone", (1, 1, 1), emit=(0.75, 0.85, 1.0), strength=18.0)
CLOTH = [mat(f"crowd{i}", c, 0.85) for i, c in enumerate(
    [(0.05, 0.05, 0.06), (0.12, 0.04, 0.03), (0.08, 0.09, 0.1), (0.15, 0.12, 0.09), (0.03, 0.05, 0.09),
     (0.35, 0.05, 0.02), (0.04, 0.2, 0.06), (0.25, 0.08, 0.3), (0.05, 0.12, 0.35), (0.4, 0.3, 0.12), (0.3, 0.3, 0.3)])]
BANNER = [mat("banner_red", (0.45, 0.03, 0.02), 0.8), mat("banner_black", (0.03, 0.03, 0.03), 0.8)]


# --------------------------------------------------------------- helpers --
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


def box(name, loc, size, m, rot=(0, 0, 0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bv = o.modifiers.new("b", "BEVEL")
        bv.width, bv.segments = bevel, 2
    o.data.materials.append(m)
    return o


def add_beam(bm, p0, p1, r, sides=4):
    """A thin prism from p0 to p1, appended to bm (used for lattice trusses)."""
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    u = ax.orthogonal().normalized()
    v = ax.cross(u)
    ring0, ring1 = [], []
    for i in range(sides):
        a = 2 * math.pi * (i + 0.5) / sides
        off = (u * math.cos(a) + v * math.sin(a)) * r
        ring0.append(bm.verts.new(p0 + off))
        ring1.append(bm.verts.new(p1 + off))
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))


def truss(bm, p0, p1, w, r=0.035, bays=None):
    """Square lattice boom: four chords plus zig-zag lacing on every face."""
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0)
    L = ax.length
    ax.normalize()
    u = Vector((0, 0, 1)).cross(ax)
    if u.length < 1e-3:
        u = Vector((1, 0, 0))
    u.normalize()
    v = ax.cross(u).normalized()
    bays = bays or max(2, int(L / w))
    corners = [(u + v), (u - v), (-u - v), (-u + v)]
    for c in corners:
        add_beam(bm, p0 + c * w / 2, p1 + c * w / 2, r * 1.6)
    for k in range(bays):
        a, b_ = p0 + ax * (L * k / bays), p0 + ax * (L * (k + 1) / bays)
        for i in range(4):
            c0, c1 = corners[i] * w / 2, corners[(i + 1) % 4] * w / 2
            add_beam(bm, a + c0, a + c1, r)
            if k % 2 == 0:
                add_beam(bm, a + c0, b_ + c1, r)
            else:
                add_beam(bm, a + c1, b_ + c0, r)


def light(kind, loc, energy, color, rot=None, size=0.3, spot=None):
    d = bpy.data.lights.new(kind, kind)
    d.energy, d.color = energy, color
    if hasattr(d, "shadow_soft_size"):
        d.shadow_soft_size = size
    if spot:
        d.spot_size, d.spot_blend = math.radians(spot), 0.35
    o = bpy.data.objects.new(kind, d)
    o.location = loc
    if rot:
        o.rotation_euler = rot
    C.objects.link(o)
    return o


def aim(o, target):
    d = Vector(target) - o.location
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------- quarry bench bowl --
# Concentric benches around PIT, only the far 220 degrees (behind the ring).
BENCH_R0, BENCH_STEP, BENCH_H, BENCHES = 14.0, 3.4, 2.2, 7
A0, A1 = math.radians(-38), math.radians(218)
SEG = 160
bm = bmesh.new()
gbm = bmesh.new()
bench_tops = []
for k in range(BENCHES):
    r_in = BENCH_R0 + k * BENCH_STEP
    r_out = r_in + BENCH_STEP
    z0, z1 = k * BENCH_H - 0.4 * (k == 0), (k + 1) * BENCH_H
    lo, hi, top_out = [], [], []
    for i in range(SEG + 1):
        a = A0 + (A1 - A0) * i / SEG
        c, s = math.cos(a), math.sin(a)
        j = rnd.uniform(-0.35, 0.35)
        wall_r = r_in + j
        lo.append(bm.verts.new((PIT.x + c * wall_r, PIT.y + s * wall_r, z0)))
        # wall leans back a little (bench face angle) and is jagged
        hi.append(bm.verts.new((PIT.x + c * (wall_r + 0.9), PIT.y + s * (wall_r + 0.9), z1)))
    for i in range(SEG):
        bm.faces.new((lo[i], lo[i + 1], hi[i + 1], hi[i]))
    # gravel bench top
    t_in, t_out = [], []
    for i in range(SEG + 1):
        a = A0 + (A1 - A0) * i / SEG
        c, s = math.cos(a), math.sin(a)
        t_in.append(gbm.verts.new((PIT.x + c * (r_in + 0.9), PIT.y + s * (r_in + 0.9), z1)))
        t_out.append(gbm.verts.new((PIT.x + c * r_out, PIT.y + s * r_out, z1)))
    for i in range(SEG):
        gbm.faces.new((t_in[i], t_in[i + 1], t_out[i + 1], t_out[i]))
    bench_tops.append((r_in + 0.9, r_out, z1))
walls = finish("bench_walls", bm, ROCK)
sub = walls.modifiers.new("s", "SUBSURF")
sub.subdivision_type, sub.levels, sub.render_levels = "SIMPLE", 2, 3
tx = bpy.data.textures.new("crag", "CLOUDS")
tx.noise_scale = 1.4
dp = walls.modifiers.new("d", "DISPLACE")
dp.texture, dp.strength = tx, 0.8
finish("bench_tops", gbm, GRAVEL)

# pit floor (gravel apron) and the cut bedrock stage
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=BENCH_R0 + 1, fill_type="NGON", location=(PIT.x, PIT.y, -0.4))
apron = bpy.context.active_object
apron.data.materials.append(GRAVEL)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, PIT.y - 18, -0.4))
front = bpy.context.active_object
front.scale = (160, 60, 1)
front.data.materials.append(GRAVEL)

STAGE_R = 8.0
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=STAGE_R, depth=0.6, location=(0, 2.5, -0.1),
                                    rotation=(0, 0, math.pi / 8))
stage = bpy.context.active_object
stage.name = "stage"
stage.data.materials.append(FLOOR)
bv = stage.modifiers.new("b", "BEVEL")
bv.width, bv.segments = 0.04, 2

# hazard-striped steel rim around the octagon, with drill-bit corner pylons
for i in range(8):
    a0 = math.pi / 8 + i * math.pi / 4
    a1 = a0 + math.pi / 4
    p0 = Vector((math.cos(a0) * STAGE_R, 2.5 + math.sin(a0) * STAGE_R, 0.24))
    p1 = Vector((math.cos(a1) * STAGE_R, 2.5 + math.sin(a1) * STAGE_R, 0.24))
    mid, d = (p0 + p1) / 2, (p1 - p0)
    box("rim", mid, (d.length, 0.35, 0.12), HAZARD, rot=(0, 0, math.atan2(d.y, d.x)), bevel=0.02)
    # pylon: a huge spent tri-cone drill bit set on its shank
    base = p0.copy()
    base.z = 0.2
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.28, depth=1.4, location=base + Vector((0, 0, 0.7)))
    sh = bpy.context.active_object
    sh.data.materials.append(STEEL)
    for k in range(3):
        ang = k * 2 * math.pi / 3
        bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.26, radius2=0.04, depth=0.7,
                                        location=base + Vector((math.cos(ang) * 0.22, math.sin(ang) * 0.22, 1.65)),
                                        rotation=(math.cos(ang + 1.57) * 0.5, math.sin(ang + 1.57) * 0.5, 0))
        cn = bpy.context.active_object
        cn.data.materials.append(CRANE)
    lt = light("POINT", base + Vector((0, 0, 1.6)), 40, (1.0, 0.25, 0.1), size=0.2)

# ------------------------------------------------------------- the crest --
# Carved into the bedrock: six arc segments (one per bloodline) and a V of
# two crossed blades. Gold inlay with a red Origin glow in the cut lines.
CY, CR = 2.5, 5.2
for i in range(6):
    a = math.radians(90 + 60 * i + 6)
    seg_bm = bmesh.new()
    n = 24
    outer, inner = [], []
    for k in range(n + 1):
        t = a + math.radians(48) * k / n
        outer.append(seg_bm.verts.new((math.cos(t) * CR, CY + math.sin(t) * CR, 0.205)))
        inner.append(seg_bm.verts.new((math.cos(t) * (CR - 0.35), CY + math.sin(t) * (CR - 0.35), 0.205)))
    for k in range(n):
        seg_bm.faces.new((inner[k], inner[k + 1], outer[k + 1], outer[k]))
    o = finish(f"crest_arc{i}", seg_bm, GOLD)
    so = o.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.02
    # glowing cut just inside each arc
    g_bm = bmesh.new()
    gi, go = [], []
    for k in range(n + 1):
        t = a + math.radians(48) * k / n
        go.append(g_bm.verts.new((math.cos(t) * (CR - 0.42), CY + math.sin(t) * (CR - 0.42), 0.203)))
        gi.append(g_bm.verts.new((math.cos(t) * (CR - 0.5), CY + math.sin(t) * (CR - 0.5), 0.203)))
    for k in range(n):
        g_bm.faces.new((gi[k], gi[k + 1], go[k + 1], go[k]))
    finish(f"crest_cut{i}", g_bm, VEIN)


def blade(hilt, tip, width=0.75):
    """One long blade lying flat from hilt to tip: grip, guard, tapering edge."""
    hilt, tip = Vector(hilt), Vector(tip)
    d = tip - hilt
    length = d.length
    d.normalize()
    angle = math.atan2(-d.x, d.y)                 # local +y -> direction d
    ctr = hilt + d * (length * 0.52)
    bm = bmesh.new()
    pts = [(-0.12, 0), (0.12, 0), (0.12, 0.9), (0.55, 0.95), (0.55, 1.15), (width / 2, 1.2),
           (0.08, length), (-width / 2, 1.2), (-0.55, 1.15), (-0.55, 0.95), (-0.12, 0.9)]
    ca, sa = math.cos(angle), math.sin(angle)
    vs = []
    for x, y in pts:
        y -= length * 0.52
        vs.append(bm.verts.new((ctr.x + x * ca - y * sa, ctr.y + x * sa + y * ca, 0.207)))
    bm.faces.new(vs)
    o = finish("blade", bm, GOLD)
    s = o.modifiers.new("t", "SOLIDIFY")
    s.thickness = 0.02
    gb = bmesh.new()                              # glowing fuller down the middle
    gv = []
    for x, y in [(-0.05, 1.4), (0.05, 1.4), (0.03, length - 0.8), (-0.03, length - 0.8)]:
        y -= length * 0.52
        gv.append(gb.verts.new((ctr.x + x * ca - y * sa, ctr.y + x * sa + y * ca, 0.23)))
    gb.faces.new(gv)
    finish("fuller", gb, VEIN)


# Two blades whose points meet at the bottom of the ring: a V.
blade((-2.6, CY + 3.0), (0.0, CY - 3.4))
blade((2.6, CY + 3.0), (0.0, CY - 3.4))

# chalk-white scuffs and old blood-dark stains on the stage
for i in range(14):
    r, a = rnd.uniform(5.8, STAGE_R - 0.6), rnd.uniform(0, 2 * math.pi)
    bpy.ops.mesh.primitive_circle_add(vertices=10, radius=rnd.uniform(0.15, 0.6), fill_type="NGON",
                                      location=(math.cos(a) * r, 2.5 + math.sin(a) * r, 0.201))
    sp = bpy.context.active_object
    sp.scale.x = rnd.uniform(0.5, 2.0)
    sp.rotation_euler.z = rnd.uniform(0, 3.14)
    sp.data.materials.append(mat(f"stain{i}", (0.05, 0.02, 0.015) if i % 4 else (0.2, 0.18, 0.16), 0.9))

# -------------------------------------------------------------- crowd --
person = bmesh.new()
bmesh.ops.create_cone(person, segments=6, radius1=0.24, radius2=0.18, depth=1.15, cap_ends=True)
for v in person.verts:
    v.co.z += 0.575
head = bmesh.new()
bmesh.ops.create_uvsphere(head, u_segments=8, v_segments=5, radius=0.13)
for v in head.verts:
    v.co.z += 1.32
me_head = bpy.data.meshes.new("head")
head.to_mesh(me_head)
head.free()
me_body = bpy.data.meshes.new("body")
person.to_mesh(me_body)
person.free()
for p in me_body.polygons:
    p.use_smooth = True
me_body.materials.append(CLOTH[0])
me_head.materials.append(mat("skin", (0.3, 0.18, 0.12), 0.7))
crowd_n = 0
for k, (ri, ro, z) in enumerate(bench_tops[:5]):
    rows = 3 if k < 4 else 2
    for row in range(rows):
        r = ri + 0.4 + row * (ro - ri - 0.8) / max(1, rows - 1)
        count = int((A1 - A0 - 0.2) * r / 0.62)
        for i in range(count):
            if rnd.random() < 0.12:
                continue
            a = A0 + 0.1 + (A1 - A0 - 0.2) * (i + rnd.uniform(-0.3, 0.3)) / count
            x, y = PIT.x + math.cos(a) * r, PIT.y + math.sin(a) * r
            s = rnd.uniform(0.9, 1.1)
            bo = bpy.data.objects.new("fan", me_body)
            bo.location = (x, y, z)
            bo.scale = (s, s, s * rnd.uniform(0.9, 1.05))
            bo.rotation_euler = (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), a + math.pi / 2)
            C.objects.link(bo)
            bo.material_slots[0].link = "OBJECT"
            bo.material_slots[0].material = rnd.choice(CLOTH)
            ho = bpy.data.objects.new("fan_head", me_head)
            ho.location = bo.location
            ho.scale = bo.scale
            C.objects.link(ho)
            crowd_n += 1
            # raised arms with phone lights / flares
            roll = rnd.random()
            if roll < 0.10:
                bpy.ops.mesh.primitive_uv_sphere_add(segments=6, ring_count=4, radius=0.05,
                                                     location=(x, y, z + 1.75))
                bpy.context.active_object.data.materials.append(PHONE if roll < 0.07 else TORCH)
print("crowd", crowd_n)

# work-lamp strings along each crowded bench lip, and uplights from the pit
for k, (ri, ro, z) in enumerate(bench_tops[:5]):
    for i in range(14):
        a = A0 + 0.15 + (A1 - A0 - 0.3) * i / 13
        p = Vector((PIT.x + math.cos(a) * (ri - 0.2), PIT.y + math.sin(a) * (ri - 0.2), z + 0.15))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=6, ring_count=4, radius=0.09, location=p)
        bpy.context.active_object.data.materials.append(TORCH)
        if i % 2 == 0:
            light("POINT", p + Vector((0, 0, 0.6)), 60, (1.0, 0.6, 0.3), size=0.3)
for x in (-9, 0, 9):
    up = light("AREA", (x, 9, 0.5), 900, (1.0, 0.7, 0.45), size=4)
    aim(up, (x * 1.6, 30, 8))

# flood-light towers on the bench edges behind the crowd
for a_deg in (25, 70, 110, 155):
    a = math.radians(a_deg)
    ri, ro, z = bench_tops[5]
    base = Vector((PIT.x + math.cos(a) * (ri + 1), PIT.y + math.sin(a) * (ri + 1), z))
    bm = bmesh.new()
    truss(bm, base, base + Vector((0, 0, 9)), 0.8, r=0.03)
    finish("tower", bm, STEEL)
    box("lamp_bank", base + Vector((0, 0, 9.4)), (2.2, 0.4, 1.0), STEEL)
    lp = box("lamp_face", base + Vector((0, 0, 9.4)) - Vector((math.cos(a), math.sin(a), 0)) * 0.22,
             (2.0, 0.05, 0.8), LAMP, rot=(0, 0, a + math.pi / 2))
    sl = light("SPOT", base + Vector((0, 0, 9.4)), 9000, (1.0, 0.85, 0.65), size=0.6, spot=40)
    aim(sl, (0, 2.5, 0))

# ------------------------------------------------ mining cranes + rigs --
def crane(side):
    """Crawler lattice crane: tracks, cab, A-frame, boom reaching over the
    ring with a hanging lighting rig on cables."""
    bx, by = side * 11.5, 14.0
    # tracks and body
    for dy in (-1.3, 1.3):
        box("track", (bx, by + dy, 0.5), (5.0, 0.9, 1.0), STEEL, bevel=0.15)
    box("crane_body", (bx, by, 1.8), (4.2, 3.2, 1.8), CRANE, bevel=0.06)
    box("crane_cab", (bx - side * 1.4, by - 1.0, 3.1), (1.4, 1.2, 1.2), CRANE, bevel=0.04)
    box("cab_glass", (bx - side * 1.4, by - 1.62, 3.15), (1.1, 0.05, 0.7), mat("glass", (0.02, 0.03, 0.03), 0.1))
    box("counterweight", (bx + side * 2.0, by, 2.4), (1.2, 3.0, 1.8), STEEL, bevel=0.05)
    heel = Vector((bx - side * 1.2, by, 2.8))
    tip = Vector((side * 3.6, 3.5, 10.5))
    bm = bmesh.new()
    truss(bm, heel, tip, 1.0, r=0.035)
    truss(bm, Vector((bx + side * 1.5, by, 2.8)), Vector((bx + side * 0.8, by, 6.5)), 0.6, r=0.03, bays=4)
    finish("boom", bm, CRANE)
    # pendant cables
    cb = bmesh.new()
    add_beam(cb, (bx + side * 0.8, by, 6.5), tip, 0.025)
    add_beam(cb, (bx + side * 0.8, by, 6.5), (bx + side * 2.0, by, 3.2), 0.025)
    # lighting rig hanging from the tip
    rig_z = 7.6
    for dx in (-0.6, 0.6):
        add_beam(cb, tip, (tip.x + dx, tip.y, rig_z + 0.4), 0.02)
    finish("cables", cb, STEEL)
    rb = bmesh.new()
    c0 = Vector((tip.x, tip.y, rig_z))
    truss(rb, c0 - Vector((3.2, 0, 0)), c0 + Vector((3.2, 0, 0)), 0.5, r=0.025)
    finish("rig", rb, STEEL)
    for k in range(5):
        p = c0 + Vector((-2.8 + k * 1.4, 0, -0.45))
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.22, depth=0.45, location=p)
        can = bpy.context.active_object
        can.data.materials.append(STEEL)
        bpy.ops.mesh.primitive_circle_add(vertices=12, radius=0.18, fill_type="NGON", location=p - Vector((0, 0, 0.23)))
        bpy.context.active_object.data.materials.append(LAMP)
        sl = light("SPOT", p - Vector((0, 0, 0.3)), 2600, (1.0, 0.92, 0.8), size=0.15, spot=28)
        aim(sl, (side * -0.8 + (k - 2) * 1.6 * 0.6, 2.5, 0))
    # hanging banner of the tournament under the boom
    bpy.ops.mesh.primitive_plane_add(size=1, location=(tip.x + side * 3.5, tip.y + 2, 8.6), rotation=(math.pi / 2, 0, 0))
    bn = bpy.context.active_object
    bn.scale = (1.4, 3.2, 1)
    sub = bn.modifiers.new("s", "SUBSURF")
    sub.subdivision_type, sub.levels, sub.render_levels = "SIMPLE", 4, 4
    tx = bpy.data.textures.new(f"wave{side}", "CLOUDS")
    tx.noise_scale = 1.0
    dp = bn.modifiers.new("d", "DISPLACE")
    dp.texture, dp.strength, dp.direction = tx, 0.3, "Y"
    bn.data.materials.append(BANNER[0])
    # banner emblem: the V-and-ring crest, simplified, in gold
    box("banner_emblem", (tip.x + side * 3.5, tip.y + 1.92, 9.3), (1.3, 0.04, 0.12), GOLD)
    box("banner_emblem_v1", (tip.x + side * 3.5 - 0.25, tip.y + 1.92, 8.7), (0.12, 0.04, 1.1), GOLD, rot=(0, 0.35, 0))
    box("banner_emblem_v2", (tip.x + side * 3.5 + 0.25, tip.y + 1.92, 8.7), (0.12, 0.04, 1.1), GOLD, rot=(0, -0.35, 0))


crane(-1)
crane(1)

# rusting haul truck parked on a bench, an ore skip, rails down the ramp
ri, ro, z = bench_tops[1]
a = math.radians(160)
hx, hy = PIT.x + math.cos(a) * (ri + 1.8), PIT.y + math.sin(a) * (ri + 1.8)
box("truck_bed", (hx, hy, z + 2.4), (6.0, 3.6, 1.8), CRANE, rot=(0, -0.12, a + math.pi / 2), bevel=0.1)
box("truck_cab", (hx + 0.2, hy - 2.6, z + 2.3), (2.4, 1.6, 1.6), CRANE, rot=(0, 0, a + math.pi / 2), bevel=0.06)
for dx, dy in ((-2, -1.6), (2, -1.6), (-2, 1.6), (2, 1.6)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=1.0, depth=0.8,
                                        location=(hx + dx * 0.3, hy + dy * 1.0, z + 1.0), rotation=(0, math.pi / 2, 0))
    bpy.context.active_object.data.materials.append(STEEL)

# fallen rubble and an old ore-cart rail on the apron in front of the ring
for i in range(60):
    x, y = rnd.uniform(-16, 16), rnd.uniform(-9, -5.5) if i % 2 else rnd.uniform(9, 13)
    if abs(x) < 9 and y > 0:
        continue
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rnd.uniform(0.15, 0.6), location=(x, y, -0.3))
    rk = bpy.context.active_object
    rk.scale = (rnd.uniform(0.7, 1.4), rnd.uniform(0.7, 1.4), rnd.uniform(0.4, 0.8))
    rk.rotation_euler = (rnd.uniform(0, 3), rnd.uniform(0, 3), rnd.uniform(0, 3))
    rk.data.materials.append(ROCK)
for x in (-0.55, 0.55):
    box("rail", (x - 13, 0, -0.33), (0.08, 30, 0.1), STEEL, rot=(0, 0, 0.5))
for i in range(22):
    box("sleeper", (-13 + math.sin(0.5) * (i - 11) * -1.3, (i - 11) * 1.3 * math.cos(0.5), -0.38),
        (1.6, 0.22, 0.08), mat("wood", (0.12, 0.08, 0.05), 0.9), rot=(0, 0, 0.5))

# fan flags waved over the crowd, in bloodline colours
FLAG_COLS = [(0.5, 0.06, 0.02), (0.05, 0.3, 0.08), (0.3, 0.08, 0.4), (0.05, 0.15, 0.5), (0.6, 0.45, 0.1)]
for k, (ri, ro, z) in enumerate(bench_tops[:5]):
    for i in range(9):
        a = A0 + 0.3 + (A1 - A0 - 0.6) * (i + rnd.uniform(-0.3, 0.3)) / 8
        r = rnd.uniform(ri + 0.5, ro - 0.5)
        p = Vector((PIT.x + math.cos(a) * r, PIT.y + math.sin(a) * r, z))
        box("flagpole", p + Vector((0, 0, 1.6)), (0.04, 0.04, 2.2), STEEL)
        bpy.ops.mesh.primitive_plane_add(size=1, location=p + Vector((0.55, 0, 2.3)), rotation=(math.pi / 2, 0, a + math.pi / 2))
        fg = bpy.context.active_object
        fg.scale = (1.1, 0.7, 1)
        sb = fg.modifiers.new("s", "SUBSURF")
        sb.subdivision_type, sb.levels, sb.render_levels = "SIMPLE", 3, 3
        tx = bpy.data.textures.new(f"flag{k}{i}", "CLOUDS")
        tx.noise_scale = 0.5
        dpf = fg.modifiers.new("d", "DISPLACE")
        dpf.texture, dpf.strength, dpf.direction = tx, 0.25, "NORMAL"
        fg.data.materials.append(mat(f"flag{k}{i}", rnd.choice(FLAG_COLS), 0.8))

# crane detail: cab glow, hand rails, warning beacons, hazard bands on the tracks
for side in (-1, 1):
    bx, by = side * 11.5, 14.0
    box("cab_light", (bx - side * 1.4, by - 1.6, 3.15), (1.0, 0.02, 0.6), mat("cab_glow", (1, 1, 1), emit=(1.0, 0.7, 0.4), strength=3.0))
    for dz in (2.75, 3.25):
        box("rail", (bx, by - 1.68, dz), (4.0, 0.04, 0.04), STEEL)
    for dx in (-1.9, -0.6, 0.6, 1.9):
        box("rail_post", (bx + dx, by - 1.68, 3.0), (0.04, 0.04, 0.55), STEEL)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=0.12, location=(bx - side * 1.4, by - 1.0, 3.8))
    bpy.context.active_object.data.materials.append(mat("beacon", (1, 0.3, 0), emit=(1.0, 0.35, 0.0), strength=30.0))
    light("POINT", (bx - side * 1.4, by - 1.3, 3.9), 25, (1.0, 0.4, 0.05), size=0.1)
    for k in range(6):
        box("plate", (bx - 1.9 + k * 0.76, by - 1.62, 1.8), (0.7, 0.03, 1.6), CRANE, bevel=0.02)

# foreground: broken conveyor frame, cable runs and a ground work-lamp
bm = bmesh.new()
truss(bm, (-17, -2, 0.4), (-9.5, 2.5, 3.6), 0.9, r=0.03)
truss(bm, (17, -3, 0.2), (12, 6, 2.6), 0.7, r=0.03)
finish("conveyor", bm, CRANE)
for x0 in (-15, 13):
    box("belt", (x0 + 1.5, -0.3, 1.9), (0.9, 5.0, 0.06), mat("rubber", (0.02, 0.02, 0.02), 0.9), rot=(0.6, 0, -0.55 if x0 < 0 else 0.5))
cb = bmesh.new()
for i in range(6):
    x0 = rnd.uniform(-14, 14)
    pts = [Vector((x0 + rnd.uniform(-1, 1), -9 + k * 1.2, -0.36)) for k in range(5)]
    for k in range(4):
        add_beam(cb, pts[k], pts[k + 1] + Vector((rnd.uniform(-0.5, 0.5), 0, 0)), 0.03, sides=5)
finish("cables_ground", cb, mat("cable", (0.02, 0.02, 0.02), 0.6))
for x in (-10.5, 10.5):
    box("worklamp_stand", (x, -6.5, 0.4), (0.06, 0.06, 1.6), STEEL)
    wl = box("worklamp", (x, -6.4, 1.25), (0.6, 0.15, 0.4), LAMP, rot=(0.4, 0, 0))
    l2 = light("SPOT", (x, -6.2, 1.25), 350, (1.0, 0.8, 0.55), size=0.2, spot=70)
    aim(l2, (x * 0.4, -9, -0.4))

# drifting dust in the pit (gives the spotlight beams their shape)
bpy.ops.mesh.primitive_cube_add(location=(0, 8, 4))
haze = bpy.context.active_object
haze.scale = (34, 26, 5)
hm = bpy.data.materials.new("dust")
hm.use_nodes = True
hm.node_tree.nodes.clear()
ho = hm.node_tree.nodes.new("ShaderNodeOutputMaterial")
hv = hm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
hv.inputs["Density"].default_value = 0.01
hv.inputs["Color"].default_value = (0.9, 0.85, 0.8, 1)
hv.inputs["Anisotropy"].default_value = 0.4
hm.node_tree.links.new(hv.outputs[0], ho.inputs["Volume"])
haze.data.materials.append(hm)

# ------------------------------------------------------------ dusk sky --
w = bpy.data.worlds.new("dusk")
sc.world = w
w.use_nodes = True
nt = w.node_tree
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Generated"], sep.inputs[0])
zr = nt.nodes.new("ShaderNodeMapRange")          # horizon (z=0) -> 0, zenith-ish -> 1
zr.inputs["From Min"].default_value = -0.02
zr.inputs["From Max"].default_value = 0.45
nt.links.new(sep.outputs["Z"], zr.inputs["Value"])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.75, 0.22, 0.06, 1)
ramp.color_ramp.elements[1].position = 0.75
ramp.color_ramp.elements[1].color = (0.006, 0.01, 0.035, 1)
e = ramp.color_ramp.elements.new(0.12)
e.color = (0.32, 0.08, 0.12, 1)
e = ramp.color_ramp.elements.new(0.32)
e.color = (0.04, 0.04, 0.12, 1)
nt.links.new(zr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], nt.nodes["Background"].inputs[0])
nt.nodes["Background"].inputs[1].default_value = 0.6
moon = light("SUN", (0, 0, 30), 0.9, (0.5, 0.62, 1.0), rot=(math.radians(50), 0, math.radians(200)))
fill = light("AREA", (0, -12, 6), 160, (0.75, 0.75, 0.9), size=8)
aim(fill, (0, 2.5, 0.8))

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
C.objects.link(cam)
sc.camera = cam
cam.location = (0, -13.0, 3.4)
cam.rotation_euler = (math.radians(84), 0, 0)
cam.data.lens = 22
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.volume_step_rate = 4.0
sc.cycles.max_bounces = 4
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - High Contrast"
sc.view_settings.exposure = float(os.environ.get("EXPOSURE", "-0.6"))
sc.render.resolution_x = WIDTH
sc.render.resolution_y = int(WIDTH * 9 / 16)
sc.render.filepath = out
if os.environ.get("NORENDER"):
    raise SystemExit
bpy.ops.render.render(write_still=True)
print("saved", out)
