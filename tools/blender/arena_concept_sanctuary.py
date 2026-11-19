"""Forgotten Temple, "Ryuen's Sanctuary" — 3D concept render, procedural.

    python tools/blender/arena_concept_sanctuary.py <out.png> [samples] [width]

A monastery on floating stone platforms above a sea of clouds, held together
by giant chains. The great gate carries a dormant Origin crystal; gold prayer
banners in Ryuen's blue and gold hang from the chains. Dawn light.
"""
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402  (bpy must load first)
from mathutils import Matrix, Vector

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sanctuary.png"
SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 64
WIDTH = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
rnd = random.Random(11)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
C = sc.collection


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


def stone_mat(name, base, moss=0.0, scale=1.2):
    """Weathered stone: colour variation, cracks, optional moss on top faces."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = scale
    n1.inputs["Detail"].default_value = 10
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (*[c * 0.6 for c in base], 1)
    r.color_ramp.elements[1].color = (*[min(1, c * 1.25) for c in base], 1)
    nt.links.new(n1.outputs["Fac"], r.inputs["Fac"])
    col = r.outputs["Color"]
    if moss > 0:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Normal"], sep.inputs[0])
        n2 = nt.nodes.new("ShaderNodeTexNoise")
        n2.inputs["Scale"].default_value = 3
        nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
        mm = nt.nodes.new("ShaderNodeMath")
        mm.operation = "MULTIPLY"
        nt.links.new(sep.outputs["Z"], mm.inputs[0])
        nt.links.new(n2.outputs["Fac"], mm.inputs[1])
        th = nt.nodes.new("ShaderNodeMapRange")
        th.inputs["From Min"].default_value = 0.45
        th.inputs["From Max"].default_value = 0.6
        nt.links.new(mm.outputs[0], th.inputs["Value"])
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.inputs[7].default_value = (0.13, 0.2, 0.06, 1)
        nt.links.new(th.outputs["Result"], mx.inputs["Factor"])
        nt.links.new(col, mx.inputs[6])
        col = mx.outputs[2]
    # rain-streaked grime running down the faces
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (5.0, 5.0, 0.35)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    gn = nt.nodes.new("ShaderNodeTexNoise")
    gn.inputs["Scale"].default_value = 2.0
    nt.links.new(mp.outputs[0], gn.inputs["Vector"])
    gr = nt.nodes.new("ShaderNodeMapRange")
    gr.inputs["From Min"].default_value = 0.45
    gr.inputs["From Max"].default_value = 0.75
    gr.inputs["To Max"].default_value = 0.75
    nt.links.new(gn.outputs["Fac"], gr.inputs["Value"])
    gm = nt.nodes.new("ShaderNodeMix")
    gm.data_type = "RGBA"
    gm.inputs[7].default_value = (0.02, 0.022, 0.018, 1)
    nt.links.new(gr.outputs["Result"], gm.inputs["Factor"])
    nt.links.new(col, gm.inputs[6])
    nt.links.new(gm.outputs[2], b.inputs["Base Color"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.35
    nt.links.new(vor.outputs["Distance"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.85
    return m


def box(name, loc, size, m, bevel=0.0, rot=(0, 0, 0)):
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


def rock_underside(loc, rx, ry, depth, m, seed):
    """Floating-island underside: a jagged inverted cone of rock."""
    bpy.ops.mesh.primitive_cone_add(vertices=14, radius1=1.0, radius2=0.05, depth=1.0, location=loc,
                                    rotation=(math.pi, 0, 0))
    o = bpy.context.active_object
    o.scale = (rx, ry, depth)
    bpy.ops.object.transform_apply(scale=True)
    o.location.z -= depth / 2
    sub = o.modifiers.new("s", "SUBSURF")
    sub.levels = 3
    sub.render_levels = 3
    for p in o.data.polygons:
        p.use_smooth = True
    tex = bpy.data.textures.new(f"rk{seed}", "CLOUDS")
    tex.noise_scale = 1.2
    d = o.modifiers.new("d", "DISPLACE")
    d.texture, d.strength = tex, 1.6
    o.data.materials.append(m)
    return o


def tube(name, a, b, r, m, verts=10):
    a, b = Vector(a), Vector(b)
    dv = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=dv.length, vertices=verts, location=(a + b) / 2)
    o = bpy.context.active_object
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = dv.to_track_quat("Z", "Y")
    o.data.materials.append(m)
    return o


iron = mat("iron", (0.05, 0.045, 0.04), 0.5, 0.8)


def chain(a, b, sag, link=0.55, r=0.09):
    """Hanging chain of alternating torus links along a catenary-ish curve."""
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    n = max(4, int(L / (link * 0.85)))
    pts = [a.lerp(b, i / n) - Vector((0, 0, sag * 4 * (i / n) * (1 - i / n))) for i in range(n + 1)]
    for i in range(n):
        c = (pts[i] + pts[i + 1]) / 2
        d = (pts[i + 1] - pts[i]).normalized()
        bpy.ops.mesh.primitive_torus_add(major_radius=link * 0.45, minor_radius=r, location=c,
                                         major_segments=12, minor_segments=6)
        t = bpy.context.active_object
        t.scale = (1.0, 0.6, 1.0)
        q = d.to_track_quat("X", "Z")
        if i % 2:
            q = q @ Matrix.Rotation(math.radians(90), 4, "X").to_quaternion()
        t.rotation_mode = "QUATERNION"
        t.rotation_quaternion = q
        t.data.materials.append(iron)


# ---------------------------------------------------------- the platform --
floor_stone = stone_mat("floor_stone", (0.12, 0.115, 0.11), moss=0.6, scale=0.8)
wall_stone = stone_mat("wall_stone", (0.08, 0.085, 0.085), moss=0.8)
ring_stone = stone_mat("ring_stone", (0.055, 0.06, 0.062), moss=0.5, scale=2.0)
dark_rock = stone_mat("rock", (0.09, 0.08, 0.075), scale=0.4)
# tiled fighting floor: individual slabs, slightly uneven, a few missing / cracked
TILE = 0.62
tb = bmesh.new()
for iy in range(-18, 10):                           # running-bond rows of cut slabs
    x = -13.2 + rnd.uniform(0, 0.6)
    while x < 13.2:
        ln = rnd.choice((0.6, 0.75, 0.9, 1.1))
        if rnd.random() < 0.02 and abs(x) > 3:
            x += ln
            continue                                   # a missing slab
        h = rnd.uniform(-0.03, 0.015)
        sink = rnd.uniform(0.0, 0.045)                 # worn: one end sunk
        g = bmesh.ops.create_cube(tb, size=1.0)["verts"]
        for v in g:
            end = v.co.x > 0
            v.co.x = x + (v.co.x + 0.5) * (ln - rnd.uniform(0.03, 0.05))
            v.co.y = v.co.y * (TILE - 0.04) + iy * TILE
            v.co.z = v.co.z * 0.2 - 0.1 + h - (sink if end and v.co.z > -0.1 else 0)
        x += ln
_tme = bpy.data.meshes.new("floor_tiles")
tb.to_mesh(_tme)
tb.free()
_tob = bpy.data.objects.new("floor_tiles", _tme)
C.objects.link(_tob)
_tme.materials.append(floor_stone)
_tbv = _tob.modifiers.new("b", "BEVEL")
_tbv.width, _tbv.segments = 0.018, 2
box("moss_bed", (0, -2.5, -0.17), (27, 18, 0.1), mat("moss", (0.05, 0.08, 0.025), 0.95))
# fallen leaves on the floor
leaf_m = [mat("leaf_a", (0.45, 0.15, 0.03), 0.8), mat("leaf_b", (0.55, 0.32, 0.05), 0.8)]
for i in range(220):
    bpy.ops.mesh.primitive_plane_add(size=rnd.uniform(0.08, 0.16),
                                     location=(rnd.uniform(-12, 12), rnd.uniform(-10, 5.5), 0.005 + rnd.uniform(0, 0.02)),
                                     rotation=(rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), rnd.uniform(0, 6.3)))
    lf = bpy.context.active_object
    lf.scale.y = 0.55
    lf.data.materials.append(rnd.choice(leaf_m))
rock_underside((0, -2.5, -0.25), 15, 9.5, 9, dark_rock, 1)
# ritual circle inlaid in the floor (gold)
gold = mat("gold", (0.85, 0.62, 0.22), 0.3, 1.0)
for r_, w_ in ((3.2, 0.08), (3.6, 0.05)):
    bpy.ops.mesh.primitive_torus_add(major_radius=r_, minor_radius=w_, location=(0, 0, 0.0), major_segments=64)
    t = bpy.context.active_object
    t.scale.z = 0.25
    t.data.materials.append(gold)
# balustrade at the back edge, broken in places
for ix in range(-13, 14, 2):
    if rnd.random() < 0.18:
        continue
    box("post", (ix, 5.7, 0.5), (0.35, 0.35, 1.0), wall_stone, 0.03)
    if rnd.random() < 0.8:
        box("rail", (ix + 1, 5.7, 1.05), (2.0, 0.3, 0.18), wall_stone, 0.03)

# --------------------------------------------------- the great Origin gate --
gx, gy = 0.0, 9.0
RING_R = 5.2
bpy.ops.mesh.primitive_torus_add(major_radius=RING_R, minor_radius=0.85, location=(gx, gy, RING_R + 0.9),
                                 rotation=(math.radians(90), 0, 0), major_segments=72, minor_segments=16)
ring = bpy.context.active_object
ring.scale = (1, 1, 1.6)                       # deep, heavy ring
ring.data.materials.append(ring_stone)
bpy.ops.mesh.primitive_torus_add(major_radius=RING_R, minor_radius=0.22, location=(gx, gy - 1.2, RING_R + 0.9),
                                 rotation=(math.radians(90), 0, 0), major_segments=96, minor_segments=8)
lip = bpy.context.active_object                 # carved front moulding
lip.data.materials.append(ring_stone)
for k in range(48):                             # carved recesses between the inlays
    a_ = 2 * math.pi * (k + 0.5) / 48
    box("ring_carve", (gx + math.cos(a_) * (RING_R + 0.45), gy - 1.05, RING_R + 0.9 + math.sin(a_) * (RING_R + 0.45)),
        (0.12, 0.1, 0.4), mat("carve_shadow", (0.01, 0.01, 0.01), 0.9), rot=(0, -a_, 0))
for k in range(24):                            # carved gold segments set into the ring face
    a_ = 2 * math.pi * k / 24
    if abs(math.sin(a_) - 1) < 0.05:
        continue
    box("ring_inlay", (gx + math.cos(a_) * RING_R, gy - 1.0, RING_R + 0.9 + math.sin(a_) * RING_R),
        (0.32, 0.12, 0.22 if k % 2 else 0.4), gold, rot=(0, -a_, 0))
box("ring_foot", (gx, gy, 0.5), (4.5, 2.6, 1.0), wall_stone, 0.06)
for sx in (-1, 1):                             # buttresses holding the ring
    box("buttress", (gx + sx * (RING_R - 0.4), gy + 0.9, 1.6), (1.2, 2.2, 3.2), wall_stone, 0.06,
        rot=(0, sx * math.radians(12), 0))
# dormant Origin crystal in the lintel: dark crystal, faint inner glow, cracked
bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=1, location=(gx, gy - 0.6, 2 * RING_R + 1.0))
cr = bpy.context.active_object
cr.scale = (1.5, 1.0, 2.5)
cm = bpy.data.materials.new("origin_crystal")
cm.use_nodes = True
cb = cm.node_tree.nodes["Principled BSDF"]
cb.inputs["Base Color"].default_value = (0.18, 0.005, 0.005, 1)
cb.inputs["Roughness"].default_value = 0.05
cb.inputs["Transmission Weight"].default_value = 0.6
cb.inputs["Emission Color"].default_value = (1.0, 0.1, 0.03, 1)
cb.inputs["Emission Strength"].default_value = 0.9
cr.data.materials.append(cm)
ld = bpy.data.lights.new("crystal", "POINT")
ld.energy, ld.color = 700, (1.0, 0.15, 0.05)
lo = bpy.data.objects.new("crystal", ld)
lo.location = (gx, gy - 1.8, 2 * RING_R + 0.6)
C.objects.link(lo)
for k, (dx, dz, sc_) in enumerate(((-1.3, -0.6, 0.6), (1.2, -0.5, 0.7), (-0.8, 1.3, 0.45), (0.9, 1.1, 0.5))):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=1, location=(gx + dx, gy - 0.5, 2 * RING_R + 1.0 + dz))
    cc = bpy.context.active_object
    cc.scale = (0.45 * sc_, 0.4 * sc_, 1.3 * sc_)
    cc.rotation_euler = (0, -dx * 0.5, 0)
    cc.data.materials.append(cm)
# gate island + stairs down to the fighting platform
rock_underside((gx, gy, 0.0), 8, 3.5, 7, dark_rock, 2)
box("gate_floor", (gx, gy, -0.1), (14, 5, 0.2), floor_stone)
for k in range(5):
    box("step", (gx, 6.6 + k * 0.45, -0.3 + k * 0.0), (6, 0.45, 0.2), wall_stone)

# --------------------------------------------- monastery on the far islands --
roof_m = mat("roof", (0.08, 0.14, 0.32), 0.55, 0.2)     # Ryuen blue tiles
wood_m = mat("wood", (0.06, 0.03, 0.02), 0.7)
lamp_m = mat("lamp", (1, 0.75, 0.4), emit=(1.0, 0.6, 0.25), strength=4)


plaster = mat("plaster", (0.62, 0.58, 0.52), 0.8)
lattice_glow = mat("lattice_glow", (1, 0.7, 0.4), emit=(1.0, 0.55, 0.22), strength=2.5)


def hall(x, y, z, w, d, h, tiers=2):
    rock_underside((x, y, z), w * 0.75, d * 0.9, h * 1.6, dark_rock, int(x * 7 + y))
    box("hall_floor", (x, y, z - 0.2), (w * 1.2, d * 1.3, 0.4), wall_stone, 0.05)
    yy = z
    for t in range(tiers):
        ww, dd = w * (1 - 0.22 * t), d * (1 - 0.22 * t)
        box("hall_wall", (x, y, yy + h / 2), (ww * 0.8, dd * 0.8, h), plaster)
        n_bays = max(2, int(ww * 0.8 / 1.2))
        for k in range(n_bays + 1):                    # timber posts across the front
            px = x - ww * 0.4 + k * (ww * 0.8 / n_bays)
            box("post", (px, y - dd * 0.42, yy + h / 2), (0.16, 0.16, h), wood_m)
            if k < n_bays:                             # lattice window in each bay
                cx = px + ww * 0.4 / n_bays
                box("lat_glow", (cx, y - dd * 0.405, yy + h * 0.55), (ww * 0.8 / n_bays * 0.6, 0.03, h * 0.45), lattice_glow)
                for j in range(3):
                    box("lat_v", (cx - 0.25 + j * 0.25, y - dd * 0.415, yy + h * 0.55), (0.04, 0.03, h * 0.45), wood_m)
                box("lat_h", (cx, y - dd * 0.415, yy + h * 0.55), (ww * 0.8 / n_bays * 0.6, 0.03, 0.04), wood_m)
        box("beam", (x, y - dd * 0.42, yy + h), (ww * 0.85, 0.25, 0.25), wood_m)
        box("balcony", (x, y - dd * 0.5, yy + 0.08), (ww * 0.95, 0.5, 0.12), wood_m)
        for k in range(int(ww * 2)):                   # balcony railing
            box("bal_post", (x - ww * 0.47 + k * 0.5, y - dd * 0.72, yy + 0.4), (0.06, 0.06, 0.6), wood_m)
        box("bal_rail", (x, y - dd * 0.72, yy + 0.7), (ww * 0.95, 0.08, 0.08), wood_m)
        # layered roof: deep eaves, lifted corners, gold ridge
        box("roof_lo", (x, y, yy + h + 0.25), (ww * 1.4, dd * 1.45, 0.3), roof_m, 0.08)
        box("roof_hi", (x, y, yy + h + 0.6), (ww * 1.05, dd * 1.0, 0.5), roof_m, 0.1)
        for sx in (-1, 1):
            for sy in (-1, 1):
                box("corner", (x + sx * ww * 0.68, y + sy * dd * 0.7, yy + h + 0.45), (0.9, 0.5, 0.2), roof_m,
                    0.04, rot=(sy * math.radians(10), sx * math.radians(-22), 0))
        box("ridge", (x, y, yy + h + 0.95), (ww * 0.8, 0.3, 0.3), gold)
        yy += h + 0.9


hall(-17, 22, 3.0, 7, 5, 3.0, 3)
hall(15, 26, 6.0, 6, 4.5, 2.6, 2)
hall(-2, 40, 11.0, 9, 6, 3.4, 3)
hall(30, 45, 2.0, 5, 4, 2.4, 2)
hall(-34, 38, 8.0, 5, 4, 2.4, 2)
for (x, y, z, rx) in ((22, 14, -2.0, 2.5), (-24, 12, -1.0, 2.0), (8, 30, 1.0, 1.8), (-12, 55, 6, 3.0)):
    rock_underside((x, y, z), rx, rx * 0.8, rx * 2.5, dark_rock, int(x + y))
    box("isle_top", (x, y, z - 0.1), (rx * 1.6, rx * 1.3, 0.25), floor_stone)

# chains linking the islands (and anchoring the platform)
chain((-13.5, 5.5, -0.3), (-17, 19.5, 2.5), 1.6)
chain((13.5, 5.5, -0.3), (15, 23.5, 5.5), 1.8)
chain((5.5, 9.0, 9.0), (15, 24.5, 9.0), 2.5)
chain((-5.5, 9.0, 9.0), (-17, 20.5, 10.0), 2.2)
chain((-17, 24, 12.0), (-2, 38, 17.0), 3.0)

# --------------------------------------------- gold & blue prayer banners --
def banner(top, length, width, color, seed):
    rr = random.Random(seed)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(top[0], top[1], top[2] - length / 2),
                                     rotation=(math.radians(90), 0, 0))
    o = bpy.context.active_object
    o.scale = (width, length, 1)
    bpy.ops.object.transform_apply(scale=True)
    sub = o.modifiers.new("s", "SUBSURF")
    sub.levels, sub.subdivision_type = 4, "SIMPLE"
    tex = bpy.data.textures.new(f"wave{seed}", "WOOD")
    tex.wood_type, tex.noise_basis_2 = "BANDNOISE", "SIN"
    tex.turbulence = rr.uniform(3, 8)
    d = o.modifiers.new("d", "DISPLACE")
    d.texture, d.strength, d.direction = tex, 0.25, "Y"
    m = mat(f"banner{seed}", color, 0.8)
    m.node_tree.nodes["Principled BSDF"].inputs["Subsurface Weight"].default_value = 0.0
    o.data.materials.append(m)
    box("pole", (top[0], top[1], top[2] + 0.05), (width + 0.3, 0.08, 0.08), wood_m)
    trim_y = top[1] - 0.3                      # in front of the cloth's sway
    for sx in (-1, 1):
        box("trim", (top[0] + sx * width / 2, trim_y, top[2] - length / 2), (0.05, 0.03, length), gold)
    box("trim_hem", (top[0], trim_y, top[2] - length + 0.03), (width, 0.03, 0.06), gold)
    ez = top[2] - length * 0.3
    er = width * 0.32
    bpy.ops.mesh.primitive_torus_add(major_radius=er, minor_radius=er * 0.09, location=(top[0], trim_y, ez),
                                     rotation=(math.radians(90), 0, 0), major_segments=40, minor_segments=6)
    bpy.context.active_object.data.materials.append(gold)
    wb = bmesh.new()                           # the wave crest inside the ring
    pts = []
    for k in range(14):
        t = k / 13
        pts.append((-0.8 + 1.6 * t, -0.35 + 0.45 * math.sin(t * math.pi * 1.4) + (0.3 if k == 9 else 0)))
    up_ = [wb.verts.new((top[0] + x * er, trim_y, ez + y * er)) for x, y in pts]
    lo_ = [wb.verts.new((top[0] + x * er, trim_y, ez + (y - 0.22) * er)) for x, y in pts]
    for k in range(13):
        wb.faces.new((lo_[k], lo_[k + 1], up_[k + 1], up_[k]))
    _wm = bpy.data.meshes.new("wave")
    wb.to_mesh(_wm)
    wb.free()
    _wo = bpy.data.objects.new("wave", _wm)
    C.objects.link(_wo)
    _wm.materials.append(gold)


for i, x in enumerate((-2.6, -1.3, 1.3, 2.6)):        # hanging inside the ring
    banner((x, gy - 0.2, 2 * RING_R - 0.2 - abs(x) * 0.4), rnd.uniform(4.0, 5.5), 0.95,
           (0.5, 0.06, 0.04) if i % 2 == 0 else (0.05, 0.1, 0.32), 50 + i)
for i, (x, y, z) in enumerate(((-12, 12, 5.5), (11, 14, 7.0), (-8, 16, 8.5))):
    banner((x, y, z), 3.0, 0.5, (0.85, 0.6, 0.15), 60 + i)

# ----------------------------------------------------------- sea of clouds --
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 60, -7))
sea = bpy.context.active_object
sea.scale = (400, 160, 1)
bpy.ops.object.transform_apply(scale=True)
sub = sea.modifiers.new("s", "SUBSURF")
sub.levels = sub.render_levels = 5
sub.subdivision_type = "SIMPLE"
tex = bpy.data.textures.new("billows", "CLOUDS")
tex.noise_scale = 9.0
dsp = sea.modifiers.new("d", "DISPLACE")
dsp.texture, dsp.strength = tex, 9.0
sm = bpy.data.materials.new("cloud_sea")
sm.use_nodes = True
snt = sm.node_tree
sb = snt.nodes["Principled BSDF"]
sb.inputs["Base Color"].default_value = (1.0, 0.93, 0.88, 1)
sb.inputs["Roughness"].default_value = 1.0
sb.inputs["Subsurface Weight"].default_value = 0.0
sb.inputs["Emission Color"].default_value = (1.0, 0.62, 0.4, 1)
sb.inputs["Emission Strength"].default_value = 0.25
sea.data.materials.append(sm)
for p in sea.data.polygons:
    p.use_smooth = True
bpy.ops.mesh.primitive_cube_add(location=(0, 40, -3))
haze = bpy.context.active_object
haze.scale = (200, 80, 4)
hm = bpy.data.materials.new("haze")
hm.use_nodes = True
hm.node_tree.nodes.clear()
ho = hm.node_tree.nodes.new("ShaderNodeOutputMaterial")
hv = hm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
hv.inputs["Density"].default_value = 0.01
hv.inputs["Color"].default_value = (1.0, 0.8, 0.65, 1)
hm.node_tree.links.new(hv.outputs[0], ho.inputs["Volume"])
haze.data.materials.append(hm)

for i, (x, y, z, r) in enumerate(((-45, 90, 4, 14), (38, 110, 8, 18), (-10, 140, 10, 22), (70, 80, 2, 12))):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=r, location=(x, y, z))
    cu_ = bpy.context.active_object
    cu_.scale.z = 1.6
    t_ = bpy.data.textures.new(f"cum{i}", "CLOUDS")
    t_.noise_scale = r * 0.35
    dd = cu_.modifiers.new("d", "DISPLACE")
    dd.texture, dd.strength = t_, r * 0.5
    for p in cu_.data.polygons:
        p.use_smooth = True
    cu_.data.materials.append(sm)
# stone lanterns framing the stage
for x in (-12.5, 12.5):
    box("lantern_base", (x, 4.6, 0.3), (0.9, 0.9, 0.6), wall_stone, 0.05)
    box("lantern_post", (x, 4.6, 1.1), (0.35, 0.35, 1.0), wall_stone, 0.03)
    box("lantern_box", (x, 4.6, 1.85), (0.7, 0.7, 0.55), wall_stone, 0.04)
    box("lantern_fire", (x, 4.6, 1.85), (0.45, 0.75, 0.3), lamp_m)
    box("lantern_roof", (x, 4.6, 2.25), (1.1, 1.1, 0.2), roof_m, 0.05)
    ld = bpy.data.lights.new("lantern", "POINT")
    ld.energy, ld.color = 120, (1.0, 0.6, 0.3)
    lo = bpy.data.objects.new("lantern", ld)
    lo.location = (x, 4.2, 1.85)
    C.objects.link(lo)

# ------------------------------------------------------------- dawn light --
w = bpy.data.worlds.new("dawn")
sc.world = w
w.use_nodes = True
sky = w.node_tree.nodes.new("ShaderNodeTexSky")
if hasattr(sky, "sky_type"):
    for t in ("NISHITA", "MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "PREETHAM"):
        try:
            sky.sky_type = t
            break
        except TypeError:
            continue
try:
    sky.sun_elevation = math.radians(4)
    sky.sun_rotation = math.radians(200)
except AttributeError:
    pass
w.node_tree.links.new(sky.outputs[0], w.node_tree.nodes["Background"].inputs[0])
w.node_tree.nodes["Background"].inputs[1].default_value = 0.35
sun = bpy.data.lights.new("sun", "SUN")
sun.energy, sun.color, sun.angle = 2.4, (1.0, 0.68, 0.45), math.radians(1.5)
so = bpy.data.objects.new("sun", sun)
so.rotation_euler = (math.radians(76), 0, math.radians(235))
C.objects.link(so)
fill = bpy.data.lights.new("fill", "AREA")
fill.energy, fill.size, fill.color = 350, 10, (0.55, 0.65, 1.0)
fo = bpy.data.objects.new("fill", fill)
fo.location = (0, -14, 9)
fo.rotation_euler = (math.radians(55), 0, 0)
C.objects.link(fo)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
C.objects.link(cam)
sc.camera = cam
cam.location = (0, -15.0, 2.1)
cam.rotation_euler = (math.radians(89), 0, 0)
cam.data.lens = 24
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.volume_step_rate = 4.0
sc.cycles.max_bounces = 4
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - High Contrast"
sc.view_settings.exposure = -1.4
sc.render.resolution_x = WIDTH
sc.render.resolution_y = int(WIDTH * 9 / 16)
sc.render.filepath = out
if os.environ.get("NORENDER"):
    raise SystemExit
bpy.ops.render.render(write_still=True)
print("saved", out)
