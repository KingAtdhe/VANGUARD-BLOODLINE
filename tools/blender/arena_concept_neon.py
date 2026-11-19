"""Neon District, "The Severed Line" — 3D concept render (stage layout + mood), built procedurally.

    python tools/blender/arena_concept_neon.py <out.png> [samples] [width]

Rooftop fighting floor (wet concrete, puddles), rooftop clutter at the
edges, a layered night skyline with lit windows, original neon signage,
rain streaks and haze. Side-on stage camera like the game's.
"""
import math
import random
import sys

import bpy
from mathutils import Vector

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/neon.png"
SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 64
WIDTH = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
random.seed(4)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
C = sc.collection


def mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
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


def box(name, loc, size, m, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bv = o.modifiers.new("b", "BEVEL")
        bv.width, bv.segments = bevel, 2
    o.data.materials.append(m)
    return o


def light(name, kind, loc, energy, color, size=1.0, rot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy, ld.color = energy, color
    if kind == "AREA":
        ld.size = size
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    if rot:
        o.rotation_euler = rot
    C.objects.link(o)


# ------------------------------------------------------------ rooftop floor --
floor_m = bpy.data.materials.new("wet_concrete")
floor_m.use_nodes = True
nt = floor_m.node_tree
bs = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord")
nz = nt.nodes.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 0.35
nz.inputs["Detail"].default_value = 6
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
ramp = nt.nodes.new("ShaderNodeValToRGB")          # puddles = low roughness
ramp.color_ramp.elements[0].position = 0.40
ramp.color_ramp.elements[0].color = (0.04, 0.04, 0.04, 1)
ramp.color_ramp.elements[1].position = 0.47
ramp.color_ramp.elements[1].color = (0.55, 0.55, 0.55, 1)
nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bs.inputs["Roughness"])
grit = nt.nodes.new("ShaderNodeTexNoise")
grit.inputs["Scale"].default_value = 40
nt.links.new(tc.outputs["Object"], grit.inputs["Vector"])
mixc = nt.nodes.new("ShaderNodeMix")
mixc.data_type = "RGBA"
mixc.inputs[6].default_value = (0.05, 0.05, 0.06, 1)
mixc.inputs[7].default_value = (0.11, 0.11, 0.12, 1)
nt.links.new(grit.outputs["Fac"], mixc.inputs["Factor"])
nt.links.new(mixc.outputs[2], bs.inputs["Base Color"])
bump = nt.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.15
nt.links.new(grit.outputs["Fac"], bump.inputs["Height"])
nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
box("floor", (0, -4.0, -0.1), (30, 20.5, 0.2), floor_m)
# painted stage lines (worn) and expansion joints
line_m = mat("line", (0.6, 0.55, 0.1), 0.6)
for x in (-7.5, 7.5):
    box("edge_line", (x, 0, 0.002), (0.12, 3.0, 0.004), line_m)
joint_m = mat("joint", (0.02, 0.02, 0.02), 0.8)
for x in range(-10, 11, 3):
    box("joint", (x, 2, 0.001), (0.02, 8, 0.003), joint_m)

# --------------------------------------------------------- rooftop clutter --
metal_m = mat("metal", (0.16, 0.17, 0.19), 0.35, 0.8)
dark_m = mat("dark", (0.05, 0.05, 0.06), 0.6, 0.4)
parapet_m = mat("parapet", (0.09, 0.09, 0.1), 0.7)
box("parapet", (0, 6.0, 0.45), (24, 0.3, 0.9), parapet_m, 0.02)
for x in range(-11, 12, 2):                                    # railing
    box("post", (x, 5.85, 1.3), (0.05, 0.05, 0.8), metal_m)
box("rail", (0, 5.85, 1.7), (22, 0.06, 0.06), metal_m)
box("rail2", (0, 5.85, 1.3), (22, 0.04, 0.04), metal_m)
for i, x in enumerate((-9.5, -6.8, 6.5, 9.2)):                # AC units / vents
    box(f"ac{i}", (x, 4.6, 0.55), (1.6, 1.1, 1.1), dark_m, 0.03)
    box(f"fan{i}", (x, 4.6, 1.11), (0.9, 0.9, 0.04), metal_m)
box("tank_leg", (-11.0, 5.0, 1.2), (2.0, 1.6, 2.4), metal_m)
bpy.ops.mesh.primitive_cylinder_add(radius=1.1, depth=2.2, location=(-11.0, 5.0, 3.4), vertices=32)
tank = bpy.context.active_object
tank.data.materials.append(mat("tank", (0.2, 0.12, 0.08), 0.6, 0.3))
for x in (2.5, 3.4):                                           # pipes
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=6, location=(x, 5.4, 0.3),
                                        rotation=(0, math.radians(90), 0))
    bpy.context.active_object.data.materials.append(metal_m)

# stairwell hut, cable runs, vent stacks (all at the edges; the fighting lane stays clear)
hut = box("hut", (10.5, 5.0, 1.4), (3.2, 2.4, 2.8), parapet_m, 0.03)
box("hut_roof", (10.5, 5.0, 2.9), (3.6, 2.8, 0.2), dark_m)
box("door", (10.5, 3.79, 1.1), (1.0, 0.04, 2.0), mat("door", (0.02, 0.02, 0.02), 0.4))
box("door_lamp", (10.5, 3.7, 2.35), (0.35, 0.12, 0.12), mat("lamp", (1, 0.85, 0.6), emit=(1, 0.8, 0.5), strength=25))
light("door_light", "AREA", (10.5, 3.4, 2.2), 120, (1.0, 0.8, 0.55), 0.6, (math.radians(150), 0, 0))
for i, x in enumerate((-12.5, -12.0, 12.6)):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=2.6, location=(x, 4.4 + i * 0.3, 1.3), vertices=12)
    bpy.context.active_object.data.materials.append(metal_m)
for k in range(3):
    tube_pts = [(-13, 5.6, 0.15 + k * 0.08), (13, 5.6, 0.15 + k * 0.08)]
    box("cable_run", (0, 5.6 - k * 0.1, 0.12 + k * 0.08), (26, 0.06, 0.06), dark_m)
steam_m = bpy.data.materials.new("steam")
steam_m.use_nodes = True
steam_m.node_tree.nodes.clear()
_so = steam_m.node_tree.nodes.new("ShaderNodeOutputMaterial")
_sv = steam_m.node_tree.nodes.new("ShaderNodeVolumePrincipled")
_sv.inputs["Color"].default_value = (0.85, 0.85, 0.9, 1)
# Wisps, not a blob: thresholded noise, faded towards the volume's edge and
# thinning as it rises (object Z), so it reads as steam leaving a vent.
_stc = steam_m.node_tree.nodes.new("ShaderNodeTexCoord")
_sn = steam_m.node_tree.nodes.new("ShaderNodeTexNoise")
_sn.inputs["Scale"].default_value = 3.5
_sn.inputs["Detail"].default_value = 8.0
_sn.inputs["Distortion"].default_value = 1.2
steam_m.node_tree.links.new(_stc.outputs["Object"], _sn.inputs["Vector"])
_th = steam_m.node_tree.nodes.new("ShaderNodeMapRange")
_th.inputs["From Min"].default_value = 0.5
_th.inputs["From Max"].default_value = 0.72
steam_m.node_tree.links.new(_sn.outputs["Fac"], _th.inputs["Value"])
_len = steam_m.node_tree.nodes.new("ShaderNodeVectorMath")
_len.operation = "LENGTH"
steam_m.node_tree.links.new(_stc.outputs["Object"], _len.inputs[0])
_fo = steam_m.node_tree.nodes.new("ShaderNodeMapRange")
_fo.inputs["From Min"].default_value = 1.0
_fo.inputs["From Max"].default_value = 0.3
steam_m.node_tree.links.new(_len.outputs["Value"], _fo.inputs["Value"])
_sep = steam_m.node_tree.nodes.new("ShaderNodeSeparateXYZ")
steam_m.node_tree.links.new(_stc.outputs["Object"], _sep.inputs[0])
_up = steam_m.node_tree.nodes.new("ShaderNodeMapRange")
_up.inputs["From Min"].default_value = 1.0
_up.inputs["From Max"].default_value = -1.0
_up.inputs["To Min"].default_value = 0.15
steam_m.node_tree.links.new(_sep.outputs["Z"], _up.inputs["Value"])
_m1 = steam_m.node_tree.nodes.new("ShaderNodeMath")
_m1.operation = "MULTIPLY"
steam_m.node_tree.links.new(_th.outputs["Result"], _m1.inputs[0])
steam_m.node_tree.links.new(_fo.outputs["Result"], _m1.inputs[1])
_m2 = steam_m.node_tree.nodes.new("ShaderNodeMath")
_m2.operation = "MULTIPLY"
steam_m.node_tree.links.new(_m1.outputs[0], _m2.inputs[0])
steam_m.node_tree.links.new(_up.outputs["Result"], _m2.inputs[1])
_mul = steam_m.node_tree.nodes.new("ShaderNodeMath")
_mul.operation = "MULTIPLY"
_mul.inputs[1].default_value = 2.2
steam_m.node_tree.links.new(_m2.outputs[0], _mul.inputs[0])
steam_m.node_tree.links.new(_mul.outputs[0], _sv.inputs["Density"])
steam_m.node_tree.links.new(_sv.outputs[0], _so.inputs["Volume"])
for x, y in ((-12.5, 4.4), (12.6, 5.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(x, y, 3.6))
    st_ = bpy.context.active_object
    st_.scale = (0.9, 0.9, 1.8)
    st_.data.materials.append(steam_m)
bpy.ops.mesh.primitive_cube_add(location=(0, 16, -6))           # mist pooling in the street gap
mist = bpy.context.active_object
mist.scale = (60, 10, 5)
mm = bpy.data.materials.new("street_mist")
mm.use_nodes = True
mm.node_tree.nodes.clear()
_mo = mm.node_tree.nodes.new("ShaderNodeOutputMaterial")
_mv = mm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
_mv.inputs["Density"].default_value = 0.05
_mv.inputs["Color"].default_value = (0.6, 0.6, 0.7, 1)
mm.node_tree.links.new(_mv.outputs[0], _mo.inputs["Volume"])
mist.data.materials.append(mm)

# ---------------------------------------------------------------- skyline --
def window_material(name, base, lit, cw=1.3, ch=2.4):
    """Facade with a regular window grid; each window randomly lit."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = 0.45
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])

    def M(op, a, b_=None, v=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        nt.links.new(a, n.inputs[0])
        if b_ is not None:
            nt.links.new(b_, n.inputs[1])
        elif v is not None:
            n.inputs[1].default_value = v
        return n.outputs[0]
    u = M("ADD", sep.outputs["X"], None) if False else M("ADD", sep.outputs["X"], sep.outputs["Y"])
    cu = M("DIVIDE", u, v=cw)
    cz = M("DIVIDE", sep.outputs["Z"], v=ch)
    inx = M("LESS_THAN", M("FRACT", cu), v=0.42)
    inz = M("LESS_THAN", M("FRACT", cz), v=0.42)
    win = M("MULTIPLY", inx, inz)
    cell = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(M("FLOOR", cu), cell.inputs[0])
    nt.links.new(M("FLOOR", cz), cell.inputs[1])
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    nt.links.new(cell.outputs[0], wn.inputs["Vector"])
    on = M("GREATER_THAN", wn.outputs["Value"], v=0.62)
    lit_ = M("MULTIPLY", win, on)
    b.inputs["Emission Color"].default_value = (*lit, 1)
    nt.links.new(M("MULTIPLY", lit_, v=1.1), b.inputs["Emission Strength"])
    return m


wins = [window_material("w_cool", (0.02, 0.025, 0.035), (0.45, 0.7, 1.0)),
        window_material("w_teal", (0.02, 0.03, 0.035), (0.35, 0.9, 0.85)),
        window_material("w_warm", (0.025, 0.022, 0.03), (1.0, 0.8, 0.55))]
GROUND = -32.0    # street level far below the rooftop: we fight high above the city
for layer, (y, hmin, hmax, n) in enumerate(((16, 18, 29, 14), (34, 28, 46, 16), (60, 40, 78, 18))):
    x = -70
    while x < 70:
        w = random.uniform(3.5, 7.0) * (1 + layer * 0.3)
        h = random.uniform(hmin, hmax)
        yb, db = y + random.uniform(-2, 2), random.uniform(5, 9)
        b = box("bld", (x + w / 2, yb, GROUND + h / 2), (w, db, h), random.choice(wins))
        if layer < 2:                                              # facade detail
            bx, by, d = x + w / 2, yb, db
            top = GROUND + h
            for zz in range(int(GROUND + 6), int(top), random.choice((7, 9, 12))):   # floor ledges
                box("ledge", (bx, by - d / 2 - 0.15, zz), (w + 0.3, 0.35, 0.25), dark_m)
            if random.random() < 0.6:                                 # setback crown
                box("crown", (bx, by + 0.5, top + 1.5), (w * 0.7, d * 0.7, 3.0), random.choice(wins))
            for k in range(random.randint(1, 3)):                     # downpipes
                box("pipe", (x + random.uniform(0.3, w - 0.3), by - d / 2 - 0.25, GROUND + h / 2), (0.15, 0.15, h), metal_m)
            for k in range(random.randint(2, 6)):                     # AC units on the facade
                box("acf", (x + random.uniform(0.6, w - 0.6), by - d / 2 - 0.35, random.uniform(GROUND + 10, top - 2)),
                    (0.8, 0.5, 0.55), dark_m)
            if random.random() < 0.5:                                 # rooftop water tank
                bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.2, location=(bx + w * 0.2, by, top + 1.3), vertices=16)
                bpy.context.active_object.data.materials.append(dark_m)
        if random.random() < 0.35:                               # rooftop antenna / spire
            box("ant", (x + w / 2, y, GROUND + h + 2.5), (0.15, 0.15, 5), dark_m)
            box("ant_light", (x + w / 2, y, GROUND + h + 5.0), (0.3, 0.3, 0.3),
                mat("red", (1, 0, 0), emit=(1, 0.05, 0.03), strength=30))
        x += w + random.uniform(0.3, 2.0)

# ----------------------------------------------- THE SEVERED LINE: conduit --
# A colossal Origin power conduit that broke and crashed through the district.
casing_m = bpy.data.materials.new("casing")
casing_m.use_nodes = True
_n = casing_m.node_tree
_b = _n.nodes["Principled BSDF"]
_tc = _n.nodes.new("ShaderNodeTexCoord")
_rust = _n.nodes.new("ShaderNodeTexNoise")
_rust.inputs["Scale"].default_value = 0.8
_rust.inputs["Detail"].default_value = 10
_n.links.new(_tc.outputs["Object"], _rust.inputs["Vector"])
_rr = _n.nodes.new("ShaderNodeValToRGB")
_rr.color_ramp.elements[0].position = 0.5
_rr.color_ramp.elements[0].color = (0.09, 0.1, 0.11, 1)
_rr.color_ramp.elements[1].position = 0.68
_rr.color_ramp.elements[1].color = (0.11, 0.045, 0.02, 1)
_n.links.new(_rust.outputs["Fac"], _rr.inputs["Fac"])
_gm = _n.nodes.new("ShaderNodeMapping")
_gm.inputs["Scale"].default_value = (4.0, 4.0, 0.3)
_n.links.new(_tc.outputs["Object"], _gm.inputs["Vector"])
_gn = _n.nodes.new("ShaderNodeTexNoise")
_gn.inputs["Scale"].default_value = 1.5
_n.links.new(_gm.outputs[0], _gn.inputs["Vector"])
_gr = _n.nodes.new("ShaderNodeMapRange")
_gr.inputs["From Min"].default_value = 0.4
_gr.inputs["From Max"].default_value = 0.75
_gr.inputs["To Max"].default_value = 0.8
_n.links.new(_gn.outputs["Fac"], _gr.inputs["Value"])
_gx = _n.nodes.new("ShaderNodeMix")
_gx.data_type = "RGBA"
_gx.inputs[7].default_value = (0.015, 0.012, 0.01, 1)
_n.links.new(_gr.outputs["Result"], _gx.inputs["Factor"])
_n.links.new(_rr.outputs["Color"], _gx.inputs[6])
_n.links.new(_gx.outputs[2], _b.inputs["Base Color"])
_sc = _n.nodes.new("ShaderNodeTexNoise")
_sc.inputs["Scale"].default_value = 60
_sc.inputs["Detail"].default_value = 12
_n.links.new(_tc.outputs["Object"], _sc.inputs["Vector"])
_rg = _n.nodes.new("ShaderNodeMapRange")
_rg.inputs["To Min"].default_value = 0.62
_rg.inputs["To Max"].default_value = 0.95
_n.links.new(_sc.outputs["Fac"], _rg.inputs["Value"])
_n.links.new(_rg.outputs["Result"], _b.inputs["Roughness"])
_b.inputs["Metallic"].default_value = 0.15
_bp = _n.nodes.new("ShaderNodeBump")
_bp.inputs["Strength"].default_value = 0.4
_n.links.new(_sc.outputs["Fac"], _bp.inputs["Height"])
_n.links.new(_bp.outputs["Normal"], _b.inputs["Normal"])
rib_m = mat("rib", (0.05, 0.045, 0.04), 0.75, 0.3)
core_m = mat("origin_core", (0.3, 0.01, 0.005), 0.3, emit=(1.0, 0.015, 0.0), strength=1.3)
crack_m = mat("origin_glow", (1.0, 0.2, 0.05), 0.3, emit=(1.0, 0.2, 0.04), strength=9)


def tube(name, a, b, r, m, verts=24):
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, vertices=verts, location=(a + b) / 2)
    o = bpy.context.active_object
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    o.name = name
    o.data.materials.append(m)
    return o


def conduit(p0, p1, r=2.6, seed=0, broken_end=False):
    rnd = random.Random(seed)
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    ax = (p1 - p0).normalized()
    tube("core", p0, p1, r * 0.55, core_m)
    up = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    u = ax.cross(up).normalized()
    w = ax.cross(u).normalized()
    n_plates = 10
    for k in range(n_plates):                        # armour plates, some torn away
        ang = 2 * math.pi * k / n_plates
        dirv = u * math.cos(ang) + w * math.sin(ang)
        t0 = 0.0
        while t0 < L:
            seg = rnd.uniform(3.0, 6.0)
            t1 = min(L, t0 + seg)
            if rnd.random() > (0.12 if not broken_end else 0.12 + 0.55 * (t1 / L) ** 3):
                c = p0 + ax * ((t0 + t1) / 2) + dirv * r * 0.92
                bpy.ops.mesh.primitive_cube_add(location=c)
                pl = bpy.context.active_object
                pl.rotation_mode = "QUATERNION"
                pl.rotation_quaternion = ax.to_track_quat("Z", "Y") @ \
                    (Vector((0, 0, 1)).rotation_difference(Vector((0, 0, 1))))
                pl.scale = (r * 0.62 / 2, r * 0.62 / 2, (t1 - t0) / 2 - 0.08)
                pl.rotation_quaternion = (dirv.to_track_quat("Z", "Y").to_matrix() @
                                          dirv.to_track_quat("Z", "Y").to_matrix().transposed()).to_quaternion() @ \
                    ax.to_track_quat("Z", "Y")
                pl.scale = (0.18, r * 0.66, (t1 - t0) / 2 - 0.08)
                look = ax.to_track_quat("Z", "Y").to_matrix()
                # orient: local Z along the conduit, local X along the radius
                xv, yv, zv = dirv, ax.cross(dirv), ax
                from mathutils import Matrix
                pl.rotation_quaternion = Matrix((xv, yv, zv)).transposed().to_quaternion()
                pl.data.materials.append(casing_m)
            t0 = t1
    t = 1.5
    while t < L - 1.0:                                # structural ribs
        if not broken_end or t < L * 0.8:
            bpy.ops.mesh.primitive_torus_add(major_radius=r * 1.02, minor_radius=0.22,
                                             location=p0 + ax * t, major_segments=40, minor_segments=8)
            ring = bpy.context.active_object
            ring.rotation_mode = "QUATERNION"
            ring.rotation_quaternion = ax.to_track_quat("Z", "Y")
            ring.data.materials.append(rib_m)
        t += rnd.uniform(4.0, 6.5)
    if broken_end:                                    # jagged break + spilling energy
        for k in range(14):
            ang = rnd.uniform(0, 2 * math.pi)
            dirv = u * math.cos(ang) + w * math.sin(ang)
            base = p1 + dirv * r * 0.85
            tube("shard", base, base + ax * rnd.uniform(0.6, 2.4) + dirv * rnd.uniform(0.2, 0.9),
                 rnd.uniform(0.15, 0.4), casing_m, verts=5)
        bpy.ops.mesh.primitive_ico_sphere_add(radius=r * 0.42, subdivisions=2, location=p1 - ax * 0.4)
        g = bpy.context.active_object
        g.data.materials.append(crack_m)
        for k in range(70):                           # energy leaking out and falling
            t_ = rnd.random()
            sp = p1 + Vector((rnd.uniform(-1.5, 1.5) * (1 + t_), rnd.uniform(-1.5, 1.5), -t_ * 22 + rnd.uniform(-1, 1)))
            bpy.ops.mesh.primitive_ico_sphere_add(radius=rnd.uniform(0.03, 0.09), subdivisions=1, location=sp)
            bpy.context.active_object.data.materials.append(crack_m)
        for k in range(5):                            # severed cables hanging from the break
            a0 = p1 + Vector((rnd.uniform(-1.5, 1.5), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
            pts_ = [a0]
            for j in range(6):
                pts_.append(pts_[-1] + Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.3, 0.3), -rnd.uniform(1.2, 2.2))))
            for q0, q1 in zip(pts_[:-1], pts_[1:]):
                tube("cable", q0, q1, 0.09, rib_m, verts=6)
        ld = bpy.data.lights.new("break_glow", "POINT")
        ld.energy, ld.color, ld.shadow_soft_size = 3500, (1.0, 0.12, 0.04), 3
        lo = bpy.data.objects.new("break_glow", ld)
        lo.location = p1 - ax * 1.5
        C.objects.link(lo)
    for f in (0.2, 0.5, 0.8):                         # red light along the core
        ld = bpy.data.lights.new("core_glow", "POINT")
        ld.energy, ld.color, ld.shadow_soft_size = 1500, (1.0, 0.1, 0.03), 4
        lo = bpy.data.objects.new("core_glow", ld)
        lo.location = p0 + (p1 - p0) * f
        C.objects.link(lo)


# upper run: comes in from high on the left, still intact-ish
conduit((-75, 95, 52), (-16, 40, 20), r=3.0, seed=1)
# lower run: severed — its torn end hangs over the street behind the rooftop
conduit((-16, 40, 20), (4, 22, 5.5), r=3.0, seed=2, broken_end=True)
# far piece that fell into the street on the right, half buried
# cold moon/sky light catching the top of the conduit armour so it reads as a
# dark plated tube against the city instead of melting into it
for tgt in ((-30, 55, 30), (-6, 31, 13)):
    _rl = bpy.data.lights.new("conduit_rim", "AREA")
    _rl.energy, _rl.size, _rl.color = 18000, 10, (0.55, 0.65, 1.0)
    _ro = bpy.data.objects.new("conduit_rim", _rl)
    _ro.location = Vector(tgt) + Vector((6, 6, 16))
    _ro.rotation_euler = (Vector(tgt) - _ro.location).to_track_quat("-Z", "Y").to_euler()
    C.objects.link(_ro)
conduit((12, 24, -20), (30, 44, -6), r=2.8, seed=3, broken_end=True)

# ------------------------------------------- invented VANGUARD script signs --
def glyph(cx, y, cz, s, seed, m):
    """One glyph of an invented script: strokes on a 3x5 grid, always with a spine."""
    g = random.Random(seed)
    pts = [(gx, gz) for gx in range(3) for gz in range(5)]
    box("spine", (cx, y, cz), (0.12 * s, 0.05, 2.2 * s), m)
    for _ in range(g.randint(2, 4)):
        (x0, z0) = g.choice(pts)
        horiz = g.random() < 0.6
        L = g.choice((1, 2)) * 0.5 * s
        if horiz:
            box("st", (cx + (x0 - 1) * 0.45 * s, y, cz + (z0 - 2) * 0.5 * s), (L, 0.05, 0.12 * s), m)
        else:
            box("st", (cx + (x0 - 1) * 0.5 * s, y, cz + (z0 - 2) * 0.45 * s), (0.12 * s, 0.05, L), m)
    if g.random() < 0.4:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.28 * s, minor_radius=0.05 * s,
                                         location=(cx + 0.35 * s, y, cz + 0.6 * s), rotation=(math.radians(90), 0, 0))
        bpy.context.active_object.data.materials.append(m)


SIGN_COLS = [((0.25, 0.95, 1.0), 30), ((1.0, 0.75, 0.3), 25), ((0.9, 0.95, 1.0), 22)]
for i, (x, y, z, n) in enumerate(((-24, 29.4, 2, 5), (-8, 29.4, 6, 4), (20, 29.4, 4, 5),
                                   (31, 29.4, 9, 3), (-36, 55.4, 18, 6), (40, 55.4, 22, 5))):
    col, st = SIGN_COLS[i % 3]
    m = mat(f"sign{i}", col, emit=col, strength=st)
    s_ = 1.1 if y < 40 else 1.8
    box(f"panel{i}", (x, y + 0.08, z + (n - 1) * 0.65 * s_), (1.4 * s_, 0.08, n * 1.35 * s_ + 0.4), dark_m)
    for k in range(n):
        glyph(x, y - 0.02, z + k * 1.3 * s_, s_, seed=i * 10 + k, m=m)

# --------------------------------------- the WANTED billboard (Kairo, torn) --
bb = bpy.data.materials.new("wanted")
bb.use_nodes = True
ntb = bb.node_tree
ntb.nodes.clear()
o_ = ntb.nodes.new("ShaderNodeOutputMaterial")
em = ntb.nodes.new("ShaderNodeEmission")
tx = ntb.nodes.new("ShaderNodeTexImage")
tx.image = bpy.data.images.load("/home/claude/proj/face_x4.png")
tint = ntb.nodes.new("ShaderNodeMix")
tint.data_type = "RGBA"
tint.blend_type = "MULTIPLY"
tint.inputs["Factor"].default_value = 0.6
tint.inputs[7].default_value = (0.7, 0.85, 1.0, 1)
ntb.links.new(tx.outputs["Color"], tint.inputs[6])
ntb.links.new(tint.outputs[2], em.inputs["Color"])
em.inputs["Strength"].default_value = 1.6
tr = ntb.nodes.new("ShaderNodeBsdfTransparent")
mixs = ntb.nodes.new("ShaderNodeMixShader")
tcb = ntb.nodes.new("ShaderNodeTexCoord")
tear = ntb.nodes.new("ShaderNodeTexNoise")
tear.inputs["Scale"].default_value = 4.0
tear.inputs["Detail"].default_value = 8
ntb.links.new(tcb.outputs["Generated"], tear.inputs["Vector"])
grad = ntb.nodes.new("ShaderNodeTexGradient")
ntb.links.new(tcb.outputs["Generated"], grad.inputs["Vector"])
add = ntb.nodes.new("ShaderNodeMath")
add.operation = "ADD"
ntb.links.new(tear.outputs["Fac"], add.inputs[0])
ntb.links.new(grad.outputs["Fac"], add.inputs[1])
gt = ntb.nodes.new("ShaderNodeMath")
gt.operation = "GREATER_THAN"
gt.inputs[1].default_value = 1.12                 # tear away the right / lower-right corner
ntb.links.new(add.outputs[0], gt.inputs[0])
ntb.links.new(gt.outputs[0], mixs.inputs["Fac"])
ntb.links.new(em.outputs[0], mixs.inputs[1])
ntb.links.new(tr.outputs[0], mixs.inputs[2])
ntb.links.new(mixs.outputs[0], o_.inputs["Surface"])
bpy.ops.mesh.primitive_plane_add(size=1, location=(16.0, 29.2, 11.0), rotation=(math.radians(90), 0, 0))
bill = bpy.context.active_object
bill.scale = (9.3, 10.5, 1)
bpy.ops.object.transform_apply(scale=True)
bill.data.materials.append(bb)
box("bill_frame_t", (16.0, 29.25, 16.3), (9.8, 0.3, 0.3), metal_m)
box("bill_frame_b", (16.0, 29.25, 5.7), (9.8, 0.3, 0.3), metal_m)
for x in (11.2, 20.8):
    box("bill_post", (x, 29.3, -5.0), (0.3, 0.3, 42), metal_m)
redm = mat("wanted_bar", (1.0, 0.1, 0.05), emit=(1.0, 0.1, 0.05), strength=18)
for k in range(4):                                  # "WANTED" in the invented script
    glyph(13.2 + k * 1.9, 29.1, 17.6, 0.8, seed=900 + k, m=redm)

# -------------------------------------------------------- rain + atmosphere --
rain_m = mat("rain", (0.7, 0.8, 1.0), 0.0, emit=(0.6, 0.7, 1.0), strength=0.6)
rain_m.blend_method = "BLEND" if hasattr(rain_m, "blend_method") else None
for _ in range(900):
    x, y, z = random.uniform(-12, 12), random.uniform(-2, 9), random.uniform(0, 8)
    box("drop", (x, y, z), (0.006, 0.006, random.uniform(0.25, 0.5)), rain_m)
bpy.ops.mesh.primitive_cube_add(location=(0, 20, 12))
fog = bpy.context.active_object
fog.scale = (60, 30, 20)
fm = bpy.data.materials.new("haze")
fm.use_nodes = True
fm.node_tree.nodes.clear()
vo = fm.node_tree.nodes.new("ShaderNodeOutputMaterial")
vs = fm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
vs.inputs["Density"].default_value = 0.0035
vs.inputs["Color"].default_value = (0.45, 0.55, 0.7, 1)
fm.node_tree.links.new(vs.outputs[0], vo.inputs["Volume"])
fog.data.materials.append(fm)

# ----------------------------------------------------------------- lights --
w = bpy.data.worlds.new("night")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.01, 0.02, 0.04, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
wn_ = w.node_tree
tcw = wn_.nodes.new("ShaderNodeTexCoord")
sepw = wn_.nodes.new("ShaderNodeSeparateXYZ")
wn_.links.new(tcw.outputs["Generated"], sepw.inputs[0])
rampw = wn_.nodes.new("ShaderNodeValToRGB")
rampw.color_ramp.elements[0].position = 0.5
rampw.color_ramp.elements[0].color = (0.05, 0.06, 0.1, 1)
rampw.color_ramp.elements[1].position = 0.62
rampw.color_ramp.elements[1].color = (0.004, 0.006, 0.015, 1)
wn_.links.new(sepw.outputs["Z"], rampw.inputs["Fac"])
wn_.links.new(rampw.outputs["Color"], wn_.nodes["Background"].inputs[0])


def light(name, kind, loc, energy, color, size=1.0, rot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy, ld.color = energy, color
    if kind == "AREA":
        ld.size = size
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    if rot:
        o.rotation_euler = rot
    C.objects.link(o)


light("red_wash", "AREA", (-8, 6, 6), 900, (1.0, 0.15, 0.08), 6, (math.radians(-60), 0, math.radians(20)))
light("cyan_wash", "AREA", (8, 6, 6), 1200, (0.2, 0.8, 1.0), 6, (math.radians(-60), 0, math.radians(-20)))
light("key", "AREA", (2, -6, 7), 900, (0.8, 0.85, 1.0), 5, (math.radians(50), 0, math.radians(10)))
light("tank_lamp", "POINT", (-11.0, 4.2, 2.6), 150, (1.0, 0.6, 0.3))

# ---------------------------------------------------------- stage camera --
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
C.objects.link(cam)
sc.camera = cam
cam.location = (0, -13.5, 2.4)
cam.rotation_euler = (math.radians(88.5), 0, 0)
cam.data.lens = 22
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.volume_step_rate = 4.0
sc.cycles.max_bounces = 4
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.resolution_x = WIDTH
sc.render.resolution_y = int(WIDTH * 9 / 16)
sc.render.filepath = out
import os
if os.environ.get("NORENDER"):
    from mathutils import Vector as _V
    for o in bpy.data.objects:
        if o.type == "MESH":
            bb = [o.matrix_world @ _V(c) for c in o.bound_box]
            lo = [min(p[i] for p in bb) for i in range(3)]; hi = [max(p[i] for p in bb) for i in range(3)]
            if hi[2] - lo[2] > 6 and hi[1] < 14 and lo[2] < 2 and hi[2] > 4: print("BIG", o.name, [round(v,1) for v in lo], [round(v,1) for v in hi])
    raise SystemExit
bpy.ops.render.render(write_still=True)
print("saved", out)
