"""Builds the VANGUARD: BLOODLINE arena geometry FROM SCRATCH and exports GLB.

    python tools/blender/arena_builder.py --out assets/arenas

Every shape is generated here (no kit-bash packs, scans or external assets).
Lighting, fog, glow, particles and in-world text live in the Godot arena
scenes (scenes/arenas/*.tscn) so they can be tuned for mobile without a
rebuild. Conventions: metres, Z up, fighters stand on the X axis at Y = 0,
the camera is at -Y (Godot +Z) looking toward +Y, floor top at Z = 0.
Deterministic: a fixed random seed per arena.
"""

import argparse
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector


class Kit:
    """One mesh, several materials. Every helper tags faces with a material."""

    def __init__(self, name, materials):
        self.name = name
        self.bm = bmesh.new()
        # "Already placed" marker. Not the BMesh tag flag: operators such as
        # bevel use tags as scratch space and would clear them.
        self.done = self.bm.verts.layers.int.new("placed")
        self.mats = list(materials)  # [(name, rgb, rough, metal, emit_rgb, emit_strength)]
        self.idx = {m[0]: i for i, m in enumerate(self.mats)}
        self.custom_uv = {}  # face -> constant UV (data for shaders, e.g. crowd seed/kind)

    def tag_uv(self, verts, uv):
        """Give every face of these verts a constant UV0 (read by a shader).
        Stored V-flipped because the glTF exporter flips V (Godot then reads
        exactly `uv`)."""
        for v in verts:
            for f in v.link_faces:
                self.custom_uv[f] = (uv[0], 1.0 - uv[1])

    def _tag(self, faces, mat):
        for f in faces:
            f.material_index = self.idx[mat]

    @staticmethod
    def _rot(rot):
        return (Matrix.Rotation(math.radians(rot[2]), 3, "Z") @ Matrix.Rotation(math.radians(rot[1]), 3, "Y")
                @ Matrix.Rotation(math.radians(rot[0]), 3, "X"))

    def box(self, c, size, mat, rot=(0, 0, 0), bevel=0.0):
        r = bmesh.ops.create_cube(self.bm, size=1.0)
        bmesh.ops.scale(self.bm, vec=size, verts=r["verts"])
        if bevel > 0:
            verts = [v for v in self.bm.verts if not v[self.done]]
            edges = list({e for v in verts for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bevel, segments=1, affect="EDGES", clamp_overlap=True)
        return self._finish_new(c, rot, mat)

    # Everything not yet marked as placed is the primitive just created.
    def _finish_new(self, c, rot, mat):
        new = [v for v in self.bm.verts if not v[self.done]]
        bmesh.ops.rotate(self.bm, verts=new, cent=(0, 0, 0), matrix=self._rot(rot))
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=new)
        faces = {f for v in new for f in v.link_faces}
        self._tag(faces, mat)
        for v in new:
            v[self.done] = 1
        return new

    def cyl(self, c, r, h, mat, segs=16, r2=None, rot=(0, 0, 0), caps=True):
        bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=segs, radius1=r,
                              radius2=r if r2 is None else r2, depth=h)
        return self._finish_new(c, rot, mat)

    def sphere(self, c, r, mat, segs=10, rings=6, scale=(1, 1, 1)):
        ret = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=r)
        bmesh.ops.scale(self.bm, vec=scale, verts=ret["verts"])
        return self._finish_new(c, (0, 0, 0), mat)

    def quad(self, c, w, h, mat, normal="-Y"):
        """Single-sided panel facing the camera (-Y) by default."""
        x, z = w / 2, h / 2
        if normal == "-Y":
            pts = [(-x, 0, -z), (x, 0, -z), (x, 0, z), (-x, 0, z)]
        elif normal == "+Z":
            pts = [(-x, -z, 0), (x, -z, 0), (x, z, 0), (-x, z, 0)]
        else:  # +X / -X facing
            s = 1 if normal == "+X" else -1
            pts = [(0, -x * s, -z), (0, x * s, -z), (0, x * s, z), (0, -x * s, z)]
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        self.bm.faces.new(vs)
        return self._finish_new(c, (0, 0, 0), mat)

    def ring(self, c, r_in, r_out, mat, segs=48, z0=0.0, z1=0.05, sides=None):
        """Flat annulus band (or polygon with `sides`) — stage trims."""
        n = sides or segs
        rings = []
        for rr, zz in ((r_out, z0), (r_out, z1), (r_in, z1), (r_in, z0)):
            rings.append([self.bm.verts.new(Vector((math.cos(2 * math.pi * k / n + (math.pi / n if sides else 0)) * rr,
                                                    math.sin(2 * math.pi * k / n + (math.pi / n if sides else 0)) * rr,
                                                    zz))) for k in range(n)])
        for a, b in zip(rings, rings[1:] + rings[:1]):
            for k in range(n):
                self.bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
        return self._finish_new(c, (0, 0, 0), mat)

    def disc(self, c, r, mat, sides=8, z=0.0):
        vs = [self.bm.verts.new(Vector((math.cos(2 * math.pi * k / sides + math.pi / sides) * r,
                                        math.sin(2 * math.pi * k / sides + math.pi / sides) * r, z)))
              for k in range(sides)]
        self.bm.faces.new(vs)
        return self._finish_new(c, (0, 0, 0), mat)

    def export(self, path, bake_ao=True, ao_size=2048, ao_samples=48, ao_distance=2.0, materials=True):
        """Write the GLB, its baked ambient-occlusion map and the Godot
        materials that use them.

        UV0 ("UVMap") is a world-space planar projection per face, scaled by
        the material's surface tile size, so the shared tiling textures keep
        a constant texel density. UV1 ("Lightmap") is a unique unwrap; Cycles
        bakes ambient occlusion into it ([id]_ao.png). For every material a
        StandardMaterial3D is written to <arena>/materials/<name>.tres;
        ArenaView swaps them in at runtime (textures + AO on UV2)."""
        bpy.ops.wm.read_factory_settings(use_empty=True)
        out_dir = os.path.dirname(path)
        arena_id = os.path.basename(out_dir)
        uv = self.bm.loops.layers.uv.new("UVMap")
        self.bm.normal_update()
        names = [m[0] for m in self.mats]
        for f in self.bm.faces:
            if f in self.custom_uv:
                for loop in f.loops:
                    loop[uv].uv = self.custom_uv[f]
                continue
            tile = SURFACES.get(names[f.material_index], (None, 2.0))[1]
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            for loop in f.loops:
                co = loop.vert.co
                if ax == 2:
                    u, v = co.x, co.y
                elif ax == 0:
                    u, v = co.y * (1 if n.x > 0 else -1), co.z
                else:
                    u, v = co.x * (-1 if n.y > 0 else 1), co.z
                loop[uv].uv = (u / tile, v / tile)
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
        self.bm.free()
        for name, rgb, rough, metal, emit, strength in self.mats:
            m = bpy.data.materials.new(name)
            m.use_nodes = True
            b = m.node_tree.nodes.get("Principled BSDF")
            b.inputs["Base Color"].default_value = (*rgb, 1)
            b.inputs["Roughness"].default_value = rough
            b.inputs["Metallic"].default_value = metal
            if strength > 0:
                b.inputs["Emission Color"].default_value = (*emit, 1)
                b.inputs["Emission Strength"].default_value = strength
            mesh.materials.append(m)
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        for p in mesh.polygons:
            p.use_smooth = False
        ao_rel, lm_rel = "", ""
        if bake_ao:
            lm = mesh.uv_layers.new(name="Lightmap")
            mesh.uv_layers.active = lm
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003, area_weight=0.0,
                                     scale_to_bounds=True)
            bpy.ops.object.mode_set(mode="OBJECT")
            sc = bpy.context.scene
            sc.render.engine = "CYCLES"
            sc.cycles.device = "CPU"
            sc.cycles.samples = ao_samples
            if sc.world is None:
                sc.world = bpy.data.worlds.new("w")
            sc.world.light_settings.distance = ao_distance
            img = bpy.data.images.new(f"{arena_id}_ao", ao_size, ao_size, alpha=False)
            img.generated_color = (1, 1, 1, 1)
            for m in mesh.materials:
                t = m.node_tree.nodes.new("ShaderNodeTexImage")
                t.image = img
                m.node_tree.nodes.active = t
            sc.render.bake.margin = 8
            bpy.ops.object.bake(type="AO")
            ao_path = os.path.join(out_dir, f"{arena_id}_ao.png")
            img.filepath_raw = ao_path
            img.file_format = "PNG"
            img.save()
            ao_rel = "res://" + os.path.relpath(ao_path, ROOT).replace(os.sep, "/")
            for m in mesh.materials:
                for nd in [nd for nd in m.node_tree.nodes if nd.type == "TEX_IMAGE"]:
                    m.node_tree.nodes.remove(nd)
            lm_rel = "res://" + os.path.relpath(bake_lightmap(obj, arena_id), ROOT).replace(os.sep, "/")
            mesh.uv_layers.active = mesh.uv_layers["UVMap"]
        print(f"[arena] {self.name}: tris={tris} materials={len(self.mats)} ao={'yes' if ao_rel else 'no'}")
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True, export_apply=False,
                                  export_materials="EXPORT", export_animations=False)
        if materials:
            write_godot_materials(out_dir, self.mats, ao_rel, lm_rel)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEX = "res://assets/arenas/textures"
# Material -> (shared tiling texture, tile size in metres). Emissive and
# shader-driven materials are absent: they keep their flat colour.
SURFACES = {
    "SEV_RoofWet": ("concrete_wet", 4.0), "SEV_Concrete": ("stone", 2.0), "SEV_Building": ("facade", 6.0),
    "SEV_Casing": ("paint_grey", 3.0), "SEV_Metal": ("metal_dark", 2.0),
    "SAN_Stone": ("stone", 1.5), "SAN_StoneDark": ("stone", 3.0), "SAN_Moss": ("moss", 1.0),
    "SAN_Gold": ("gold", 1.0), "SAN_Roof": ("roof_tiles", 1.5), "SAN_White": ("plaster", 2.0),
    "SAN_Wood": ("wood", 1.0),
    "PIT_Rock": ("rock_strata", 4.0), "PIT_Gravel": ("gravel", 1.0), "PIT_Dark": ("stone", 3.0),
    "PIT_Paint": ("paint_yellow", 2.0), "PIT_Gold": ("gold", 1.0), "PIT_Steel": ("metal_dark", 1.5),
    "ORI_Obsidian": ("obsidian", 3.0),
}
_TEX_MEAN = {}


def _tex_mean(tex):
    """Average linear albedo of a texture, so the material colour can be kept."""
    if tex not in _TEX_MEAN:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(os.path.join(ROOT, "assets/arenas/textures", f"{tex}_albedo.png")).convert("RGB"),
                       float) / 255.0
        _TEX_MEAN[tex] = (a ** 2.2).reshape(-1, 3).mean(0)
    return _TEX_MEAN[tex]


# Per-material tweaks for the arena surface shader.
FLOW = {"ORI_Origin": 1.0, "PIT_Vein": 0.6, "SEV_Origin": 0.8}
GRIME = {"SAN_Gold": 0.25, "PIT_Gold": 0.25, "SEV_Metal": 0.35, "PIT_Steel": 0.4, "ORI_Obsidian": 0.2,
         "SAN_Roof": 0.45, "SEV_RoofWet": 0.7, "PIT_Rock": 0.5, "SAN_White": 0.5}
# How strongly the baked light is added, per arena (calibrated in-engine).
LIGHT_STRENGTH = {"neon": 1.0, "temple": 0.7, "ascendant": 0.55, "origin": 1.6}


def write_godot_materials(out_dir, mats, ao_rel, lm_rel=""):
    """One ShaderMaterial (shaders/arena/arena_surface.gdshader) per surface."""
    mdir = os.path.join(out_dir, "materials")
    os.makedirs(mdir, exist_ok=True)
    arena_id = os.path.basename(out_dir)
    for name, rgb, rough, metal, emit, strength in mats:
        res, props = [], []

        def ext(p, typ="Texture2D"):
            res.append(f'[ext_resource type="{typ}" path="{p}" id="{len(res) + 1}"]')
            return f'ExtResource("{len(res)}")'

        shader = ext("res://shaders/arena/arena_surface.gdshader", "Shader")
        surf = SURFACES.get(name)
        P = "shader_parameter/"
        if surf:
            mean = _tex_mean(surf[0])
            tint = [min(1.0, max(0.0, c / max(1e-4, mc))) ** (1 / 2.2) for c, mc in zip(rgb, mean)]
            props += [f"{P}tint = Color({tint[0]:.4f}, {tint[1]:.4f}, {tint[2]:.4f}, 1)",
                      f"{P}use_textures = true",
                      f"{P}albedo_tex = {ext(f'{TEX}/{surf[0]}_albedo.png')}",
                      f"{P}normal_tex = {ext(f'{TEX}/{surf[0]}_normal.png')}",
                      f"{P}rough_tex = {ext(f'{TEX}/{surf[0]}_rough.png')}",
                      f"{P}roughness = {min(1.0, rough * 1.35):.3f}"]
        else:
            c = [x ** (1 / 2.2) for x in rgb]
            props += [f"{P}tint = Color({c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}, 1)", f"{P}use_textures = false",
                      f"{P}roughness = {rough:.3f}"]
        props += [f"{P}metallic = {metal:.3f}", f"{P}macro_tex = {ext(f'{TEX}/macro_noise.png')}",
                  f"{P}macro = {0.0 if strength > 0 else 0.3}", f"{P}grime = {GRIME.get(name, 0.6) if strength <= 0 else 0.0}"]
        if strength > 0:
            e = [x ** (1 / 2.2) for x in emit]
            props += [f"{P}emission_color = Color({e[0]:.4f}, {e[1]:.4f}, {e[2]:.4f}, 1)",
                      f"{P}emission_energy = {strength:.3f}", f"{P}flow = {FLOW.get(name, 0.0)}"]
        else:
            if ao_rel:
                props.append(f"{P}ao_tex = {ext(ao_rel)}")
            if lm_rel:
                props += [f"{P}light_tex = {ext(lm_rel)}", f"{P}light_scale = {LM_SCALE}",
                          f"{P}light_strength = {LIGHT_STRENGTH.get(arena_id, 1.0)}"]
        body = "\n".join([f'[gd_resource type="ShaderMaterial" load_steps={len(res) + 1} format=3]', ""]
                         + res + ["", "[resource]", f'resource_name = "{name}"', f"shader = {shader}"] + props) + "\n"
        with open(os.path.join(mdir, f"{name}.tres"), "w") as fh:
            fh.write(body)


SCENES = {"neon": "scenes/arenas/neon_district.tscn", "temple": "scenes/arenas/forgotten_temple.tscn",
          "ascendant": "scenes/arenas/ascendant_arena.tscn", "origin": "scenes/arenas/origin_chamber.tscn"}


def scene_lights(arena_id):
    """Reads the arena scene's real-time lights and ambient colour so the
    lightmap bake uses the same lighting. Godot (x, y, z) -> Blender (x, -z, y)."""
    import re
    path = os.path.join(ROOT, SCENES.get(arena_id, ""))
    if not os.path.isfile(path):
        return [], (0.3, 0.3, 0.35)
    text = open(path).read()
    amb = (0.3, 0.3, 0.35)
    m = re.search(r"ambient_light_color = Color\(([^)]*)\)", text)
    e = re.search(r"ambient_light_energy = ([\d.]+)", text)
    if m:
        c = [float(x) for x in m.group(1).split(",")[:3]]
        k = float(e.group(1)) if e else 1.0
        amb = tuple(x * k for x in c)
    lights = []
    for blk in re.split(r"\n(?=\[node )", text):
        t = re.match(r'\[node name="([^"]+)" type="(OmniLight3D|SpotLight3D|DirectionalLight3D)"', blk)
        if not t:
            continue
        tr = re.search(r"transform = Transform3D\(([^)]*)\)", blk)
        v = [float(x) for x in tr.group(1).split(",")] if tr else [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        def f(key, d):
            mm = re.search(rf"\n{key} = ([^\n]+)", blk)
            return mm.group(1) if mm else d
        col = [float(x) for x in f("light_color", "Color(1, 1, 1, 1)")[6:-1].split(",")[:3]]
        aim_g = Vector((-v[2], -v[5], -v[8]))             # -Z column (rows are serialised)
        lights.append(dict(name=t.group(1), type=t.group(2), color=col, energy=float(f("light_energy", "1")),
                           range=float(f("omni_range", f("spot_range", "5"))), angle=float(f("spot_angle", "45")),
                           pos=Vector((v[9], -v[11], v[10])), aim=Vector((aim_g.x, -aim_g.z, aim_g.y))))
    return lights, amb


def bake_lightmap(obj, arena_id, size=1024, samples=32):
    """Bakes the light a surface receives that Godot's real-time lights do
    not give it: (1) bounce light from the scene's own lights and sky, and
    (2) light thrown by glowing surfaces (neon, lamps, Origin cracks).
    Returns the image path (sqrt-encoded RGB, value = png^2 * LM_SCALE)."""
    import numpy as np
    sc = bpy.context.scene
    lights, amb = scene_lights(arena_id)
    made = []
    for L in lights:
        if L["type"] == "DirectionalLight3D":
            d = bpy.data.lights.new(L["name"], "SUN")
            d.energy = L["energy"] * 2.5
        elif L["type"] == "SpotLight3D":
            d = bpy.data.lights.new(L["name"], "SPOT")
            d.energy = L["energy"] * 25 * max(1.0, L["range"] / 6)
            d.spot_size = math.radians(min(170.0, L["angle"] * 2))
        else:
            d = bpy.data.lights.new(L["name"], "POINT")
            d.energy = L["energy"] * 25 * max(1.0, L["range"] / 6)
        d.color = L["color"]
        o = bpy.data.objects.new(L["name"], d)
        o.location = L["pos"]
        o.rotation_euler = L["aim"].to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(o)
        made.append(o)
    w = sc.world
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*amb, 1)
    bg.inputs[1].default_value = 1.0
    sc.cycles.samples = samples
    sc.cycles.max_bounces = 4
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = True
    sc.render.bake.use_pass_color = False
    results = []
    for pass_ in ("bounce", "glow"):
        img = bpy.data.images.new(f"{arena_id}_lm_{pass_}", size, size, alpha=False, float_buffer=True)
        for m in obj.data.materials:
            t = m.node_tree.nodes.new("ShaderNodeTexImage")
            t.image = img
            m.node_tree.nodes.active = t
        if pass_ == "glow":                       # light from glowing surfaces only
            for o in made:
                o.hide_render = True
            for m in obj.data.materials:          # Godot's glow makes emitters read brighter than
                b = m.node_tree.nodes.get("Principled BSDF")   # their raw strength: match that here
                b.inputs["Emission Strength"].default_value *= 3.0
            bg.inputs[1].default_value = 0.0
            sc.render.bake.use_pass_direct = True
            sc.render.bake.use_pass_indirect = True
        bpy.ops.object.bake(type="DIFFUSE", margin=8)
        a = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4)[..., :3]
        results.append(a)
        for m in obj.data.materials:
            for nd in [nd for nd in m.node_tree.nodes if nd.type == "TEX_IMAGE"]:
                m.node_tree.nodes.remove(nd)
    lm = results[0] * 0.35 + results[1]          # bounce from Godot-equivalent lights is approximate: keep it gentle
    for _ in range(2):                            # soften sampling noise (light is low-frequency)
        lm = (lm + np.roll(lm, 1, 0) + np.roll(lm, -1, 0) + np.roll(lm, 1, 1) + np.roll(lm, -1, 1)) / 5
    enc = np.sqrt(np.clip(lm / LM_SCALE, 0, 1))
    out = bpy.data.images.new(f"{arena_id}_light", size, size, alpha=False)
    px = np.ones((size, size, 4), np.float32)
    px[..., :3] = enc
    out.pixels = px.ravel()
    path = os.path.join(ROOT, "assets/arenas", arena_id, f"{arena_id}_light.png")
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    for o in made:
        bpy.data.objects.remove(o)
    print(f"[arena] {arena_id}: lightmap mean {lm.mean(axis=(0, 1)).round(3)} max {lm.max():.2f}")
    return path


LM_SCALE = 4.0


def M(name, rgb, rough=0.8, metal=0.0, emit=None, strength=0.0):
    return (name, rgb, rough, metal, emit or rgb, strength)


# ------------------------------------------------------------ Ascendant --
def beam(k, p0, p1, w, mat, h=None):
    """Square bar from p0 to p1 (truss members, cables, flag poles)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    if L < 1e-4:
        return
    z = d / L
    x = z.orthogonal().normalized()
    y = z.cross(x)
    r = bmesh.ops.create_cube(k.bm, size=1.0)
    bmesh.ops.scale(k.bm, vec=(w, h or w, L), verts=r["verts"])
    bmesh.ops.transform(k.bm, matrix=Matrix((x, y, z)).transposed().to_4x4(), verts=r["verts"])
    k._finish_new((p0 + p1) / 2, (0, 0, 0), mat)


def truss(k, p0, p1, w, mat, r=0.07):
    """Square lattice boom: four chords plus zig-zag lacing on each face."""
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0
    L = ax.length
    ax.normalize()
    u = Vector((0, 0, 1)).cross(ax)
    if u.length < 1e-3:
        u = Vector((1, 0, 0))
    u.normalize()
    v = ax.cross(u).normalized()
    corners = [(u + v) * w / 2, (u - v) * w / 2, (-u - v) * w / 2, (-u + v) * w / 2]
    for c in corners:
        beam(k, p0 + c, p1 + c, r * 1.5, mat)
    bays = max(2, int(L / w))
    for b in range(bays):
        a0, a1 = p0 + ax * (L * b / bays), p0 + ax * (L * (b + 1) / bays)
        for i in range(4):
            c0, c1 = corners[i], corners[(i + 1) % 4]
            beam(k, a0 + c0, a1 + c1, r, mat) if b % 2 == 0 else beam(k, a0 + c1, a1 + c0, r, mat)


def ascendant():
    """The Pit: the Ascendant tournament ring sunk into an abandoned open-pit
    mine that once dug Origin ore. Crowd on the quarry benches, two old
    lattice cranes hold the light rigs, a carved crest in the bedrock floor
    (a V of two blades inside a ring broken into six, one per bloodline),
    red Origin veins in the walls. Dusk. Mobile: one mesh, 8 materials."""
    rnd = random.Random(23)
    k = Kit("ThePit", [
        M("PIT_Rock", (0.075, 0.062, 0.052), 0.92),
        M("PIT_Gravel", (0.2, 0.15, 0.11), 0.95),
        M("PIT_Dark", (0.075, 0.07, 0.07), 0.5, 0.5),             # cut bedrock stage, steel
        M("PIT_Paint", (0.2, 0.125, 0.025), 0.7, 0.3),            # weathered crane yellow
        M("PIT_Gold", (0.75, 0.5, 0.18), 0.3, 1.0),
        M("PIT_Vein", (0.2, 0.0, 0.0), 0.5, 0.0, (1.0, 0.05, 0.02), 1.6),
        M("PIT_Lamp", (1.0, 0.95, 0.85), 0.5, 0.0, (1.0, 0.88, 0.7), 2.5),
        M("PIT_Steel", (0.12, 0.12, 0.13), 0.45, 0.8),
    ])
    crowd = Kit("PitCrowd", [M("PIT_CrowdShader", (0.06, 0.055, 0.06), 0.9)])
    PIT = Vector((0, 7.5, 0))
    R0, STEP, H, N = 14.0, 3.4, 2.2, 7
    A0, A1 = math.radians(-38), math.radians(218)
    SEG = 72

    # ---- quarry benches: rough rock faces, gravel tops ----------------------
    tops = []
    for b in range(N):
        r_in, r_out = R0 + b * STEP, R0 + (b + 1) * STEP
        z0, z1 = b * H - (0.5 if b == 0 else 0.0), (b + 1) * H
        lo, hi, t_in, t_out = [], [], [], []
        for i in range(SEG + 1):
            a = A0 + (A1 - A0) * i / SEG
            c, s = math.cos(a), math.sin(a)
            j = rnd.uniform(-0.35, 0.35)
            lo.append(k.bm.verts.new(Vector((PIT.x + c * (r_in + j), PIT.y + s * (r_in + j), z0))))
            hi.append(k.bm.verts.new(Vector((PIT.x + c * (r_in + j + 0.9), PIT.y + s * (r_in + j + 0.9),
                                             z1 + rnd.uniform(-0.1, 0.1)))))
        for i in range(SEG):                              # faces point into the pit (towards the camera)
            k.bm.faces.new((lo[i], hi[i], hi[i + 1], lo[i + 1]))
        k._finish_new((0, 0, 0), (0, 0, 0), "PIT_Rock")
        for i in range(SEG + 1):
            a = A0 + (A1 - A0) * i / SEG
            c, s = math.cos(a), math.sin(a)
            t_in.append(k.bm.verts.new(Vector((PIT.x + c * (r_in + 0.9), PIT.y + s * (r_in + 0.9), z1))))
            t_out.append(k.bm.verts.new(Vector((PIT.x + c * r_out, PIT.y + s * r_out, z1))))
        for i in range(SEG):                              # bench tops face up
            k.bm.faces.new((t_in[i], t_out[i], t_out[i + 1], t_in[i + 1]))
        k._finish_new((0, 0, 0), (0, 0, 0), "PIT_Gravel")
        tops.append((r_in + 0.9, r_out, z1))
        # thin red Origin veins running along the strata of this face
        for v in range(3):
            a = rnd.uniform(A0 + 0.2, A1 - 0.2)
            span = rnd.uniform(0.08, 0.25)
            zz = z0 + rnd.uniform(0.4, H - 0.4)
            for q in range(6):
                aa = a + span * q / 6
                beam(k, (PIT.x + math.cos(aa) * (r_in + 0.3), PIT.y + math.sin(aa) * (r_in + 0.3), zz + rnd.uniform(-0.1, 0.1)),
                     (PIT.x + math.cos(aa + span / 6) * (r_in + 0.3), PIT.y + math.sin(aa + span / 6) * (r_in + 0.3),
                      zz + rnd.uniform(-0.1, 0.1)), 0.07, "PIT_Vein")

    # ---- pit floor and the cut-bedrock ring --------------------------------
    k.box((0, 2, -0.45), (90, 50, 0.1), "PIT_Gravel")
    STAGE_R = 8.0
    k.cyl((0, 0, -0.1), STAGE_R, 0.6, "PIT_Dark", segs=8, rot=(0, 0, 22.5))
    for i in range(8):                                    # hazard rim + drill-bit corner posts
        a0, a1 = math.radians(22.5 + 45 * i), math.radians(22.5 + 45 * (i + 1))
        p0 = Vector((math.cos(a0) * STAGE_R, math.sin(a0) * STAGE_R, 0.25))
        p1 = Vector((math.cos(a1) * STAGE_R, math.sin(a1) * STAGE_R, 0.25))
        beam(k, p0, p1, 0.22, "PIT_Paint", h=0.1)
        if p0.y < 0:                                      # no posts between the camera and the fight
            continue
        k.cyl((p0.x, p0.y, 0.9), 0.28, 1.4, "PIT_Dark", segs=10)
        for c in range(3):
            ang = c * 2 * math.pi / 3
            k.cyl((p0.x + math.cos(ang) * 0.2, p0.y + math.sin(ang) * 0.2, 1.9), 0.24, 0.6, "PIT_Paint", segs=8,
                  r2=0.04, rot=(math.degrees(math.cos(ang + 1.57) * 0.5), math.degrees(math.sin(ang + 1.57) * 0.5), 0))

    # the crest: six arcs (one per bloodline) and a V of two blades
    CR = 5.2
    for i in range(6):
        a = math.radians(90 + 60 * i + 6)
        n = 12
        for kk, (ri, ro, mat, z) in enumerate(((CR - 0.35, CR, "PIT_Gold", 0.215), (CR - 0.5, CR - 0.42, "PIT_Vein", 0.21))):
            out_, in_ = [], []
            for s_ in range(n + 1):
                t = a + math.radians(48) * s_ / n
                out_.append(k.bm.verts.new(Vector((math.cos(t) * ro, math.sin(t) * ro, z))))
                in_.append(k.bm.verts.new(Vector((math.cos(t) * ri, math.sin(t) * ri, z))))
            for s_ in range(n):
                k.bm.faces.new((in_[s_], in_[s_ + 1], out_[s_ + 1], out_[s_]))
            k._finish_new((0, 0, 0), (0, 0, 0), mat)

    def blade(hilt, tip, width=0.75):
        hilt, tip = Vector(hilt), Vector(tip)
        d = tip - hilt
        L = d.length
        d.normalize()
        sx = Vector((d.y, -d.x, 0))
        pts = [(-0.12, 0), (0.12, 0), (0.12, 0.9), (0.55, 0.95), (0.55, 1.15), (width / 2, 1.2), (0.08, L),
               (-width / 2, 1.2), (-0.55, 1.15), (-0.55, 0.95), (-0.12, 0.9)]
        vs = [k.bm.verts.new(hilt + sx * x + d * y + Vector((0, 0, 0.215))) for x, y in pts]
        k.bm.faces.new(vs)
        k._finish_new((0, 0, 0), (0, 0, 0), "PIT_Gold")
        fl = [(-0.05, 1.4), (0.05, 1.4), (0.03, L - 0.8), (-0.03, L - 0.8)]
        vs = [k.bm.verts.new(hilt + sx * x + d * y + Vector((0, 0, 0.222))) for x, y in fl]
        k.bm.faces.new(vs)
        k._finish_new((0, 0, 0), (0, 0, 0), "PIT_Vein")

    blade((-2.6, 3.0, 0), (0.0, -3.4, 0))
    blade((2.6, 3.0, 0), (0.0, -3.4, 0))

    # ---- crowd on the lower benches: a separate mesh animated by
    # shaders/arena/crowd.gdshader; UV0 = (seed, kind) per spectator --------
    C = "PIT_CrowdShader"
    for b, (ri, ro, z) in enumerate(tops[:4]):
        rows = 3 if b < 3 else 2
        for row in range(rows):
            r = ri + 0.4 + row * (ro - ri - 0.8) / max(1, rows - 1)
            count = int((A1 - A0 - 0.2) * r / 0.75)
            for i in range(count):
                if rnd.random() < 0.15:
                    continue
                a = A0 + 0.1 + (A1 - A0 - 0.2) * (i + rnd.uniform(-0.3, 0.3)) / count
                x, y = PIT.x + math.cos(a) * r, PIT.y + math.sin(a) * r
                s = rnd.uniform(0.9, 1.1)
                seed = rnd.random()
                crowd.tag_uv(crowd.cyl((x, y, z + 0.58 * s), 0.15 * s, 1.15 * s, C, segs=6, r2=0.25 * s, caps=False),
                             (seed, 0.0))
                crowd.tag_uv(crowd.sphere((x, y, z + 1.32 * s), 0.13 * s, C, segs=5, rings=3), (seed, 0.0))
                if rnd.random() < 0.08:                    # phone lights and flares held up
                    crowd.tag_uv(crowd.sphere((x, y, z + 1.78), 0.06, C, segs=4, rings=2), (seed, 2.0))
                elif rnd.random() < 0.035:                 # waved flags
                    crowd.tag_uv(crowd.cyl((x, y, z + 2.2), 0.025, 2.0, C, segs=4), (seed, 3.0))
                    crowd.tag_uv(crowd.box((x + 0.45, y, z + 2.85), (0.9, 0.03, 0.6), C,
                                           rot=(0, 0, math.degrees(a) + 90)), (rnd.random(), 1.0))
        for i in range(12):                                # work lamps along the bench lip
            a = A0 + 0.15 + (A1 - A0 - 0.3) * i / 11
            k.sphere((PIT.x + math.cos(a) * (ri - 0.2), PIT.y + math.sin(a) * (ri - 0.2), z + 0.15), 0.09,
                     "PIT_Lamp", segs=5, rings=3)

    # ---- flood-light towers on the upper bench ------------------------------
    for a_deg in (25, 70, 110, 155):
        a = math.radians(a_deg)
        ri, ro, z = tops[5]
        base = Vector((PIT.x + math.cos(a) * (ri + 1), PIT.y + math.sin(a) * (ri + 1), z))
        truss(k, base, base + Vector((0, 0, 9)), 0.8, "PIT_Dark", r=0.05)
        k.box(base + Vector((0, 0, 9.4)), (2.2, 0.4, 1.0), "PIT_Dark", rot=(0, 0, a_deg + 90))
        k.box(base + Vector((0, 0, 9.4)) - Vector((math.cos(a), math.sin(a), 0)) * 0.22, (2.0, 0.05, 0.8),
              "PIT_Lamp", rot=(0, 0, a_deg + 90))

    # ---- mining cranes holding the stage-light rigs -------------------------
    for side in (-1, 1):
        bx, by = side * 11.5, 11.5
        for dy in (-1.3, 1.3):
            k.box((bx, by + dy, 0.5), (5.0, 0.9, 1.0), "PIT_Dark", bevel=0.12)
        k.box((bx, by, 1.8), (4.2, 3.2, 1.8), "PIT_Paint", bevel=0.06)
        k.box((bx - side * 1.4, by - 1.0, 3.1), (1.4, 1.2, 1.2), "PIT_Paint", bevel=0.04)
        k.box((bx - side * 1.4, by - 1.62, 3.15), (1.0, 0.03, 0.6), "PIT_Lamp")
        k.box((bx + side * 2.0, by, 2.4), (1.2, 3.0, 1.8), "PIT_Dark", bevel=0.05)
        k.sphere((bx - side * 1.4, by - 1.0, 3.8), 0.12, "PIT_Vein", segs=6, rings=4)   # warning beacon
        for dx in (-1.8, -0.6, 0.6, 1.8):                 # track wheels
            for dy in (-1.3, 1.3):
                k.cyl((bx + dx, by + dy - 0.47 * (1 if dy < 0 else -1) * 0, 0.5), 0.36, 0.95, "PIT_Steel", segs=12, rot=(90, 0, 0))
        for j in range(8):                                # ladder up the side of the body
            k.box((bx - side * 2.15, by - 1.62, 0.95 + j * 0.25), (0.5, 0.04, 0.04), "PIT_Steel")
        for dx in (-0.25, 0.25):
            k.box((bx - side * 2.15 + dx, by - 1.62, 1.8), (0.04, 0.04, 1.9), "PIT_Steel")
        k.cyl((bx + side * 0.6, by + 1.2, 3.4), 0.13, 1.4, "PIT_Dark", segs=8)          # exhaust stack
        heel = Vector((bx - side * 1.2, by, 2.8))
        tip = Vector((side * 3.6, 1.0, 10.5))
        truss(k, heel, tip, 1.0, "PIT_Paint", r=0.06)
        truss(k, Vector((bx + side * 1.5, by, 2.8)), Vector((bx + side * 0.8, by, 6.5)), 0.6, "PIT_Paint", r=0.05)
        beam(k, (bx + side * 0.8, by, 6.5), tip, 0.05, "PIT_Dark")
        beam(k, (bx + side * 0.8, by, 6.5), (bx + side * 2.0, by, 3.2), 0.05, "PIT_Dark")
        k.cyl(tip, 0.45, 0.35, "PIT_Steel", segs=14, rot=(90, 0, 0))                    # sheave at the boom tip
        k.cyl((bx + side * 0.8, by, 6.5), 0.35, 0.3, "PIT_Steel", segs=12, rot=(90, 0, 0))
        hook_at = tip + Vector((side * -0.9, 0.6, -5.2))                                   # hook block, hanging free
        beam(k, tip + Vector((side * -0.9, 0.6, 0)), hook_at + Vector((0, 0, 0.5)), 0.04, "PIT_Dark")
        k.box(hook_at + Vector((0, 0, 0.25)), (0.5, 0.3, 0.6), "PIT_Paint", bevel=0.04)
        k.cyl(hook_at - Vector((0, 0, 0.35)), 0.2, 0.08, "PIT_Steel", segs=10, rot=(90, 0, 0))
        k.box(hook_at - Vector((0.12, 0, 0.55)), (0.08, 0.08, 0.35), "PIT_Steel", rot=(0, 25, 0))
        rig_z = 7.6
        for dx in (-0.6, 0.6):
            beam(k, tip, (tip.x + dx, tip.y, rig_z + 0.4), 0.04, "PIT_Dark")
        c0 = Vector((tip.x, tip.y, rig_z))
        truss(k, c0 - Vector((3.2, 0, 0)), c0 + Vector((3.2, 0, 0)), 0.5, "PIT_Dark", r=0.04)
        for i in range(5):
            p = c0 + Vector((-2.8 + i * 1.4, 0, -0.45))
            k.cyl(p, 0.22, 0.45, "PIT_Dark", segs=10)
            k.disc(p - Vector((0, 0, 0.23)), 0.18, "PIT_Lamp", sides=10)
        # tournament banner under the boom: black cloth, gold V-and-ring mark
        bxn = tip.x + side * 3.5
        k.box((bxn, tip.y + 2, 8.0), (2.8, 0.04, 4.4), "PIT_Dark")
        k.box((bxn, tip.y + 1.95, 9.2), (1.3, 0.04, 0.12), "PIT_Gold")
        k.box((bxn - 0.25, tip.y + 1.95, 8.6), (0.12, 0.04, 1.1), "PIT_Gold", rot=(0, 20, 0))
        k.box((bxn + 0.25, tip.y + 1.95, 8.6), (0.12, 0.04, 1.1), "PIT_Gold", rot=(0, -20, 0))

    # ---- rusting haul truck, conveyor wreck, rubble ------------------------
    ri, ro, z = tops[1]
    a = math.radians(160)
    hx, hy = PIT.x + math.cos(a) * (ri + 1.8), PIT.y + math.sin(a) * (ri + 1.8)
    k.box((hx, hy, z + 2.4), (6.0, 3.6, 1.8), "PIT_Paint", rot=(0, -7, 160 + 90), bevel=0.1)
    k.box((hx + 0.2, hy - 2.6, z + 2.3), (2.4, 1.6, 1.6), "PIT_Paint", rot=(0, 0, 250), bevel=0.06)
    for dx, dy in ((-0.6, -1.6), (0.6, -1.6), (-0.6, 1.6), (0.6, 1.6)):
        k.cyl((hx + dx, hy + dy, z + 1.0), 1.0, 0.8, "PIT_Dark", segs=14, rot=(0, 90, 0))
    truss(k, (-17, -2, 0.4), (-9.5, 2.5, 3.6), 0.9, "PIT_Paint", r=0.05)
    truss(k, (17, -3, 0.2), (12, 6, 2.6), 0.7, "PIT_Paint", r=0.05)
    for i in range(50):
        x, y = rnd.uniform(-16, 16), rnd.choice((rnd.uniform(-9, -6), rnd.uniform(9, 13)))
        if abs(x) < 9 and y > 0:
            continue
        k.sphere((x, y, -0.3), rnd.uniform(0.15, 0.6), "PIT_Rock", segs=6, rings=4,
                 scale=(rnd.uniform(0.7, 1.4), rnd.uniform(0.7, 1.4), rnd.uniform(0.4, 0.8)))

    # ---- close detail just behind the ring (what the camera sees most) -----
    for i in range(15):                                   # crowd barrier around the back half
        a0, a1 = math.radians(8 + i * 11), math.radians(8 + (i + 1) * 11)
        p0 = Vector((math.cos(a0) * 10.2, math.sin(a0) * 10.2, -0.4))
        p1 = Vector((math.cos(a1) * 10.2, math.sin(a1) * 10.2, -0.4))
        k.box(p0 + Vector((0, 0, 0.6)), (0.08, 0.08, 1.2), "PIT_Steel")
        for zz in (0.35, 0.75, 1.15):
            beam(k, p0 + Vector((0, 0, zz)), p1 + Vector((0, 0, zz)), 0.05, "PIT_Steel")
        if i % 3 == 1:                                    # hazard plate hung on the barrier
            mid = (p0 + p1) / 2
            k.box(mid + Vector((0, 0, 0.75)) - mid.normalized() * 0.05 * 0, (0.9, 0.03, 0.4), "PIT_Paint",
                  rot=(0, 0, math.degrees(math.atan2(p1.y - p0.y, p1.x - p0.x))))
    for sx in (-1, 1):                                    # sound and broadcast kit by the ring
        base = Vector((sx * 8.6, 6.4, -0.4))
        for j in range(3):                                # speaker stack
            k.box(base + Vector((0, 0, 0.45 + j * 0.9)), (1.1, 0.9, 0.86), "PIT_Dark", bevel=0.03)
            k.box(base + Vector((0, -0.46, 0.45 + j * 0.9)), (0.9, 0.02, 0.7), "PIT_Steel")
            k.cyl(base + Vector((0, -0.48, 0.45 + j * 0.9)), 0.28, 0.03, "PIT_Dark", segs=14, rot=(90, 0, 0))
        for j in range(2):                                # flight cases
            k.box(base + Vector((sx * -1.4, -0.3 + j * 0.1, 0.3 + j * 0.6)), (1.2, 0.7, 0.58), "PIT_Dark", bevel=0.04)
            k.box(base + Vector((sx * -1.4, -0.66 + j * 0.1, 0.3 + j * 0.6)), (1.25, 0.02, 0.06), "PIT_Steel")
        k.cyl(base + Vector((sx * -2.6, 0.2, 0.45)), 0.5, 0.9, "PIT_Paint", segs=14, rot=(90, 0, 0))   # cable drum
        k.cyl(base + Vector((sx * -2.6, 0.2, 0.45)), 0.3, 0.92, "PIT_Dark", segs=14, rot=(90, 0, 0))
        cam = Vector((sx * 5.2, 9.0, -0.4))               # broadcast camera on a tripod
        for t in range(3):
            ang = t * 2 * math.pi / 3
            beam(k, cam + Vector((math.cos(ang) * 0.5, math.sin(ang) * 0.5, 0)), cam + Vector((0, 0, 1.4)), 0.04,
                 "PIT_Steel")
        k.box(cam + Vector((0, 0, 1.6)), (0.35, 0.7, 0.4), "PIT_Dark", bevel=0.03)
        k.cyl(cam + Vector((0, -0.45, 1.6)), 0.12, 0.3, "PIT_Steel", segs=10, rot=(90, 0, 0))
        k.box(cam + Vector((0, 0.1, 1.85)), (0.2, 0.2, 0.1), "PIT_Vein")    # tally light
    return k, [(crowd, "pit_crowd.glb")]


def temple():
    """Ryuen's Sanctuary: a monastery courtyard on floating stone above a sea
    of clouds at dawn, held to its neighbours by giant chains. Behind the
    fighters stands the great ring gate with the dormant Origin crystal as
    its keystone. Mobile: one mesh, 8 materials; gameplay bounds come from
    data/arenas/temple_arena.tres."""
    rnd = random.Random(11)
    k = Kit("RyuenSanctuary", [
        M("SAN_Stone", (0.15, 0.145, 0.14), 0.92),
        M("SAN_StoneDark", (0.06, 0.058, 0.056), 0.85),          # ring, timber, rock
        M("SAN_Moss", (0.06, 0.1, 0.03), 1.0),
        M("SAN_Gold", (0.85, 0.6, 0.22), 0.3, 1.0),
        M("SAN_Roof", (0.06, 0.12, 0.3), 0.55, 0.2),             # Ryuen blue: roofs, banners
        M("SAN_White", (0.78, 0.74, 0.68), 0.95),                # plaster walls, clouds
        M("SAN_Glow", (1.0, 0.7, 0.4), 0.5, 0.0, (1.0, 0.55, 0.22), 2.5),
        M("SAN_Origin", (0.2, 0.0, 0.0), 0.2, 0.0, (0.9, 0.02, 0.02), 1.2),
    ])

    def rock(c, rx, ry, depth):
        """Floating-island underside: a jagged, stepped downward spike."""
        segs = 11
        profile = ((0.0, 1.0), (0.18, 0.86), (0.42, 0.6), (0.7, 0.3), (1.0, 0.04))
        rings = []
        for t, rad in profile:
            ring_ = []
            for i in range(segs):
                a = 2 * math.pi * i / segs
                j = rnd.uniform(0.75, 1.15) if t > 0 else rnd.uniform(0.95, 1.05)
                ring_.append(k.bm.verts.new(Vector((math.cos(a) * rx * rad * j, math.sin(a) * ry * rad * j,
                                                    -t * depth * rnd.uniform(0.9, 1.08) if t > 0 else 0.0))))
            rings.append(ring_)
        k.bm.faces.new(rings[0])
        for r0, r1 in zip(rings, rings[1:]):
            for i in range(segs):
                k.bm.faces.new((r0[(i + 1) % segs], r0[i], r1[i], r1[(i + 1) % segs]))
        k._finish_new(c, (0, 0, 0), "SAN_StoneDark")

    def torus(c, R, r_rad, r_depth, mat, segs=48, sides=8, plane="XZ"):
        vs = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring_ = []
            for j in range(sides):
                b = 2 * math.pi * j / sides
                rr = R + math.cos(b) * r_rad
                if plane == "XZ":
                    ring_.append(k.bm.verts.new(Vector((math.cos(a) * rr, math.sin(b) * r_depth, math.sin(a) * rr))))
                else:
                    ring_.append(k.bm.verts.new(Vector((math.cos(a) * rr, math.sin(a) * rr, math.sin(b) * r_depth))))
            vs.append(ring_)
        for i in range(segs):
            for j in range(sides):
                a, b = vs[i], vs[(i + 1) % segs]
                k.bm.faces.new((a[j], b[j], b[(j + 1) % sides], a[(j + 1) % sides]))
        k._finish_new(c, (0, 0, 0), mat)

    # ---- courtyard: running-bond slabs over a moss bed ---------------------
    TILE = 0.62
    k.box((0, -3.5, -0.17), (28, 20, 0.1), "SAN_Moss")
    for iy in range(-21, 10):
        x = -13.4 + rnd.uniform(0, 0.6)
        while x < 13.4:
            ln = rnd.choice((0.6, 0.75, 0.9, 1.1))
            if not (rnd.random() < 0.02 and abs(x) > 3):
                h = rnd.uniform(-0.03, 0.015)
                k.box((x + ln / 2, iy * TILE, -0.1 + h), (ln - 0.045, TILE - 0.045, 0.2), "SAN_Stone",
                      rot=(0, 0, rnd.uniform(-0.6, 0.6)))
            x += ln
    k.ring((0, 0, 0), 3.15, 3.25, "SAN_Gold", segs=64, z0=0.016, z1=0.028)     # ritual circle inlay
    k.ring((0, 0, 0), 3.55, 3.6, "SAN_Gold", segs=64, z0=0.016, z1=0.028)
    rock((0, -3.5, -0.25), 15, 10, 9)
    for ix in range(-13, 14, 2):                                           # broken balustrade
        if rnd.random() < 0.18:
            continue
        k.box((ix, 5.7, 0.5), (0.35, 0.35, 1.0), "SAN_StoneDark", bevel=0.03)
        if rnd.random() < 0.8:
            k.box((ix + 1, 5.7, 1.05), (2.0, 0.3, 0.18), "SAN_StoneDark", bevel=0.03)

    # ---- the great ring gate ------------------------------------------------
    gx, gy, R = 0.0, 9.0, 5.2
    cz = R + 0.9
    torus((gx, gy, cz), R, 0.85, 1.36, "SAN_StoneDark", segs=56, sides=10)
    torus((gx, gy - 1.2, cz), R, 0.22, 0.22, "SAN_StoneDark", segs=56, sides=6)      # carved front lip
    for i in range(48):                                                    # carved recesses
        a = 2 * math.pi * (i + 0.5) / 48
        k.box((gx + math.cos(a) * (R + 0.45), gy - 1.05, cz + math.sin(a) * (R + 0.45)), (0.12, 0.1, 0.4),
              "SAN_Moss" if i % 7 == 0 else "SAN_Stone", rot=(0, -math.degrees(a), 0))
    for i in range(24):                                                    # gold inlays
        a = 2 * math.pi * i / 24
        if abs(math.sin(a) - 1) < 0.05:
            continue
        k.box((gx + math.cos(a) * R, gy - 1.0, cz + math.sin(a) * R), (0.32, 0.12, 0.22 if i % 2 else 0.4),
              "SAN_Gold", rot=(0, -math.degrees(a), 0))
    torus((gx, gy - 0.4, cz), R + 0.95, 0.12, 0.5, "SAN_StoneDark", segs=56, sides=6)   # outer flange
    for i in range(36):                                   # carved radial ribs on the back face
        a = 2 * math.pi * i / 36
        k.box((gx + math.cos(a) * R, gy + 0.75, cz + math.sin(a) * R), (0.16, 0.2, 1.3), "SAN_StoneDark",
              rot=(0, 90 - math.degrees(a), 0))
    k.box((gx, gy, 0.5), (4.5, 2.6, 1.0), "SAN_StoneDark", bevel=0.06)
    k.box((gx, gy, 1.12), (3.6, 2.0, 0.24), "SAN_Stone", bevel=0.04)                     # stepped plinth
    for sx in (-1, 1):
        k.box((gx + sx * 2.0, gy - 1.32, 0.5), (0.4, 0.04, 0.7), "SAN_Gold")              # carved panels
        for j in range(10):                               # chain hanging inside the ring
            k.box((gx + sx * (R - 1.1), gy - 0.6, cz + R - 0.9 - j * 0.42), (0.1, 0.3, 0.4) if j % 2 else (0.3, 0.1, 0.4),
                  "SAN_StoneDark")
    for sx in (-1, 1):
        k.box((gx + sx * (R - 0.4), gy + 0.9, 1.6), (1.2, 2.2, 3.2), "SAN_StoneDark", rot=(0, sx * 12, 0))
    # dormant Origin crystal cluster as keystone
    for dx, dz, s, tilt in ((0, 0, 1.0, 0), (-1.3, -0.6, 0.6, 25), (1.2, -0.5, 0.7, -25), (-0.8, 1.3, 0.45, 15),
                            (0.9, 1.1, 0.5, -15)):
        k.sphere((gx + dx, gy - 0.5, 2 * R + 1.0 + dz), 1.0, "SAN_Origin", segs=6, rings=4,
                 scale=(1.5 * s * 0.6, 1.0 * s * 0.6, 2.5 * s * 0.6))
    rock((gx, gy, 0.0), 8, 3.5, 7)
    k.box((gx, gy, -0.1), (14, 5, 0.2), "SAN_Stone")
    for i in range(5):
        k.box((gx, 6.6 + i * 0.45, -0.3), (6, 0.45, 0.2), "SAN_StoneDark")

    # ---- monastery halls on the far islands --------------------------------
    def hall(x, y, z, w, d, h, tiers):
        rock((x, y, z - 0.4), w * 0.75, d * 0.9, h * 1.6)
        k.box((x, y, z - 0.2), (w * 1.2, d * 1.3, 0.4), "SAN_StoneDark")
        yy = z
        for t in range(tiers):
            ww, dd = w * (1 - 0.22 * t), d * (1 - 0.22 * t)
            k.box((x, y, yy + h / 2), (ww * 0.8, dd * 0.8, h), "SAN_White")
            n_bays = max(2, int(ww * 0.8 / 1.2))
            for i in range(n_bays + 1):
                px = x - ww * 0.4 + i * (ww * 0.8 / n_bays)
                k.box((px, y - dd * 0.42, yy + h / 2), (0.16, 0.16, h), "SAN_StoneDark")
                if i < n_bays:
                    cx = px + ww * 0.4 / n_bays
                    k.box((cx, y - dd * 0.405, yy + h * 0.55), (ww * 0.8 / n_bays * 0.6, 0.03, h * 0.45), "SAN_Glow")
                    for j in range(3):
                        k.box((cx - 0.25 + j * 0.25, y - dd * 0.415, yy + h * 0.55), (0.04, 0.03, h * 0.45),
                              "SAN_StoneDark")
            k.box((x, y - dd * 0.42, yy + h), (ww * 0.85, 0.25, 0.25), "SAN_StoneDark")
            k.box((x, y - dd * 0.5, yy + 0.08), (ww * 0.95, 0.5, 0.12), "SAN_StoneDark")
            k.box((x, y - dd * 0.72, yy + 0.7), (ww * 0.95, 0.08, 0.08), "SAN_StoneDark")
            k.box((x, y, yy + h + 0.25), (ww * 1.4, dd * 1.45, 0.3), "SAN_Roof", bevel=0.06)
            k.box((x, y, yy + h + 0.6), (ww * 1.05, dd * 1.0, 0.5), "SAN_Roof", bevel=0.08)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    k.box((x + sx * ww * 0.68, y + sy * dd * 0.7, yy + h + 0.45), (0.9, 0.5, 0.2), "SAN_Roof",
                          rot=(sy * 10, sx * -22, 0))
            k.box((x, y, yy + h + 0.95), (ww * 0.8, 0.3, 0.3), "SAN_Gold")
            yy += h + 0.9

    hall(-17, 22, 3.0, 7, 5, 3.0, 3)
    hall(15, 26, 6.0, 6, 4.5, 2.6, 2)
    hall(-2, 40, 11.0, 9, 6, 3.4, 3)
    hall(30, 45, 2.0, 5, 4, 2.4, 2)
    hall(-34, 38, 8.0, 5, 4, 2.4, 2)
    for (x, y, z, rx) in ((22, 14, -2.0, 2.5), (-24, 12, -1.0, 2.0), (8, 30, 1.0, 1.8), (-12, 55, 6, 3.0)):
        rock((x, y, z - 0.2), rx, rx * 0.8, rx * 2.5)
        k.box((x, y, z - 0.1), (rx * 1.6, rx * 1.3, 0.25), "SAN_Stone")

    # ---- chains linking the islands ----------------------------------------
    def chain(p0, p1, sag):
        p0, p1 = Vector(p0), Vector(p1)
        L = (p1 - p0).length
        n = int(L / 0.55)
        for i in range(n):
            t = (i + 0.5) / n
            p = p0.lerp(p1, t) - Vector((0, 0, sag * 4 * t * (1 - t)))
            q = p0.lerp(p1, min(1, t + 0.01)) - Vector((0, 0, sag * 4 * min(1, t + 0.01) * (1 - min(1, t + 0.01))))
            d = (q - p).normalized()
            yaw = math.degrees(math.atan2(d.y, d.x))
            pitch = -math.degrees(math.asin(max(-1, min(1, d.z))))
            roll = 90 if i % 2 else 0
            k.box(p, (0.62, 0.09, 0.3), "SAN_StoneDark", rot=(roll, pitch, yaw))

    chain((-13.5, 5.5, -0.3), (-17, 19.5, 2.5), 1.6)
    chain((13.5, 5.5, -0.3), (15, 23.5, 5.5), 1.8)
    chain((5.5, 9.0, 9.0), (15, 24.5, 9.0), 2.5)
    chain((-5.5, 9.0, 9.0), (-17, 20.5, 10.0), 2.2)
    chain((-17, 24, 12.0), (-2, 38, 17.0), 3.0)

    # ---- banner poles (the cloth is a swaying shader quad in the scene,
    # see BANNERS in scenes/arenas/forgotten_temple.tscn) -------------------
    for x, top, w in ((-2.6, 9.16, 0.95), (-1.3, 9.68, 0.95), (1.3, 9.68, 0.95), (2.6, 9.16, 0.95)):
        k.box((x, gy - 0.2, top + 0.05), (w + 0.3, 0.08, 0.08), "SAN_StoneDark")
        k.box((x, gy - 0.2, top + 0.5), (0.04, 0.04, 0.9), "SAN_StoneDark")
    for x, y, z in ((-12, 12, 5.5), (11, 14, 7.0), (-8, 16, 8.5)):
        k.box((x, y, z + 0.05), (0.9, 0.08, 0.08), "SAN_StoneDark")

    # ---- close detail just behind the fighters -----------------------------
    u = Vector((0, 4.4, 0))                                # bronze incense burner (smoke in the scene)
    for t in range(3):
        ang = t * 2 * math.pi / 3 + 0.5
        beam(k, u + Vector((math.cos(ang) * 0.55, math.sin(ang) * 0.55, 0)), u + Vector((0, 0, 0.9)), 0.07,
             "SAN_Gold")
    k.sphere(u + Vector((0, 0, 1.05)), 0.55, "SAN_Gold", segs=14, rings=7, scale=(1.0, 1.0, 0.55))
    k.cyl(u + Vector((0, 0, 1.35)), 0.42, 0.06, "SAN_StoneDark", segs=14)
    k.sphere(u + Vector((0, 0, 1.4)), 0.3, "SAN_Glow", segs=8, rings=3, scale=(1.0, 1.0, 0.25))
    for x0 in (6.6,):                                      # bell rack
        for dx in (-1.1, 1.1):
            k.box((x0 + dx, 4.5, 1.2), (0.18, 0.18, 2.4), "SAN_StoneDark")
        k.box((x0, 4.5, 2.45), (2.8, 0.22, 0.18), "SAN_StoneDark", bevel=0.03)
        k.box((x0, 4.5, 2.62), (3.1, 0.3, 0.12), "SAN_Roof", bevel=0.03)
        for i, bx in enumerate((-0.6, 0.0, 0.6)):
            k.box((x0 + bx, 4.5, 2.2), (0.02, 0.02, 0.4), "SAN_StoneDark")
            k.cyl((x0 + bx, 4.5, 1.85), 0.2 + 0.04 * i, 0.4 + 0.05 * i, "SAN_Gold", segs=12, r2=0.08)
    g = Vector((-6.8, 4.3, 0))                            # a broken stone guardian (original figure)
    k.box(g + Vector((0, 0, 0.35)), (1.4, 1.1, 0.7), "SAN_StoneDark", bevel=0.05)
    k.box(g + Vector((0, 0, 1.4)), (0.9, 0.7, 1.4), "SAN_Stone", bevel=0.08)          # robed legs
    k.box(g + Vector((0.1, 0.05, 2.45)), (1.0, 0.65, 0.9), "SAN_Stone", rot=(0, -8, 4), bevel=0.08)
    k.box(g + Vector((-0.55, -0.1, 2.2)), (0.28, 0.3, 1.0), "SAN_Stone", rot=(0, 12, 0), bevel=0.04)
    beam(k, g + Vector((0.55, -0.35, 0.8)), g + Vector((0.6, -0.4, 2.9)), 0.12, "SAN_StoneDark")      # staff
    k.sphere(g + Vector((1.2, -0.7, 0.32)), 0.32, "SAN_Stone", segs=10, rings=6)                       # fallen head
    k.box(g + Vector((1.15, -1.0, 0.36)), (0.26, 0.05, 0.08), "SAN_StoneDark")
    for i in range(6):                                    # broken pieces
        k.box(g + Vector((rnd.uniform(-1.4, 1.6), rnd.uniform(-1.2, -0.4), 0.1)),
              (rnd.uniform(0.15, 0.4), rnd.uniform(0.15, 0.35), rnd.uniform(0.1, 0.25)), "SAN_Stone",
              rot=(0, 0, rnd.uniform(0, 90)))
    for c in ((-3.2, 5.0), (3.8, 5.1), (-10.5, 4.6)):       # prayer cairns
        z = 0.0
        for j in range(4):
            r = 0.32 - j * 0.06
            k.sphere((c[0] + rnd.uniform(-0.04, 0.04), c[1], z + r * 0.5), r, "SAN_Stone", segs=8, rings=5,
                     scale=(1.0, 0.85, 0.55))
            z += r * 0.9
    for i in range(18):                                   # fallen roof tiles and moss clumps
        x = rnd.choice((rnd.uniform(-13, -8), rnd.uniform(8, 13)))
        k.box((x, rnd.uniform(3.6, 5.3), 0.04), (0.35, 0.22, 0.05), "SAN_Roof", rot=(rnd.uniform(-8, 8), 0, rnd.uniform(0, 90)))
    for ix in range(-13, 14, 2):
        k.sphere((ix + rnd.uniform(-0.2, 0.2), 5.45, 0.02), rnd.uniform(0.2, 0.4), "SAN_Moss", segs=8, rings=4,
                 scale=(1.6, 1.0, 0.35))

    # ---- stone lanterns framing the stage -----------------------------------
    for x in (-12.5, 12.5):
        k.box((x, 4.6, 0.3), (0.9, 0.9, 0.6), "SAN_StoneDark", bevel=0.05)
        k.box((x, 4.6, 1.1), (0.35, 0.35, 1.0), "SAN_StoneDark")
        k.box((x, 4.6, 1.85), (0.7, 0.7, 0.55), "SAN_StoneDark", bevel=0.04)
        k.box((x, 4.6 - 0.36, 1.85), (0.45, 0.02, 0.3), "SAN_Glow")
        k.box((x, 4.6, 2.25), (1.1, 1.1, 0.2), "SAN_Roof", bevel=0.05)

    # ---- the sea of clouds, cloud towers and far islands are the painted
    # panorama sky (tools/blender/arena_panorama.py -> temple_sky.png).
    return k


def neon():
    """The Severed Line: a wet rooftop above the Neon District at night. A
    colossal Origin power conduit broke and crashed through the district; its
    torn end hangs over the street behind the roof, still leaking red energy.
    Mobile layout: one mesh, 8 materials, everything behind the parapet is
    backdrop only (gameplay bounds come from data/arenas/neon_arena.tres)."""
    rnd = random.Random(31)
    k = Kit("SeveredLine", [
        M("SEV_RoofWet", (0.085, 0.085, 0.095), 0.3, 0.1),
        M("SEV_Concrete", (0.11, 0.11, 0.12), 0.85),
        M("SEV_Building", (0.03, 0.032, 0.045), 0.7, 0.2),
        M("SEV_Window", (0.25, 0.22, 0.18), 0.4, 0.0, (1.0, 0.85, 0.62), 0.45),
        M("SEV_Casing", (0.085, 0.09, 0.1), 0.7, 0.25),
        M("SEV_Origin", (0.15, 0.0, 0.0), 0.4, 0.0, (0.85, 0.0, 0.03), 0.8),
        M("SEV_Neon", (0.1, 0.9, 1.0), 0.4, 0.0, (0.15, 0.9, 1.0), 6.0),
        M("SEV_Metal", (0.09, 0.09, 0.1), 0.04, 0.75),
    ])
    # ---- the roof: fighting area, puddles, painted helipad-style lines ----
    k.box((0, -2, -0.25), (34, 24, 0.5), "SEV_RoofWet")
    for i in range(16):                                  # standing water: glossy patches
        k.box((rnd.uniform(-13, 13), rnd.uniform(-9, 4.5), 0.004),
              (rnd.uniform(0.8, 2.8), rnd.uniform(0.5, 1.4), 0.006), "SEV_Metal", rot=(0, 0, rnd.uniform(0, 180)))
    for x in range(-15, 16, 3):                          # tar-sealed seams between roof slabs
        k.box((x + 0.5, -2, 0.002), (0.07, 23.5, 0.004), "SEV_Building")
    for y in range(-13, 6, 3):
        k.box((0, y, 0.002), (33.5, 0.07, 0.004), "SEV_Building")
    for x, y in ((-4.5, 2.6), (5.0, -3.4), (-10.2, -6.0)):  # drain grates
        k.box((x, y, 0.006), (0.7, 0.7, 0.012), "SEV_Metal")
        for g in range(5):
            k.box((x, y - 0.28 + g * 0.14, 0.014), (0.62, 0.05, 0.006), "SEV_Building")
    for x in (-9.5, 9.5):                                # faded yellow lane marks (concrete tone)
        k.box((x, 1.5, 0.003), (3.2, 0.1, 0.005), "SEV_Concrete", rot=(0, 0, -12 if x < 0 else 12))
    # ---- parapets, railing, roof furniture --------------------------------
    k.box((0, 5.75, 0.45), (34, 0.5, 0.9), "SEV_Concrete", bevel=0.03)
    k.box((0, 5.75, 0.93), (34, 0.62, 0.08), "SEV_Concrete")
    for sx in (-1, 1):
        k.box((sx * 16.75, -2, 0.45), (0.5, 15.5, 0.9), "SEV_Concrete")
    for x in range(-16, 17, 2):                          # railing posts + two rails
        k.box((x, 5.75, 1.45), (0.05, 0.05, 1.0), "SEV_Metal")
    for z in (1.5, 1.95):
        k.box((0, 5.75, z), (32, 0.04, 0.04), "SEV_Metal")
    # stairwell hut (right) with its door lamp
    k.box((12.6, 4.0, 1.5), (3.6, 3.0, 3.0), "SEV_Concrete", bevel=0.04)
    k.box((12.6, 4.0, 3.06), (3.9, 3.3, 0.12), "SEV_Concrete")
    k.box((12.6, 2.49, 1.1), (1.0, 0.04, 2.2), "SEV_Metal")
    k.box((12.6, 2.4, 2.45), (0.5, 0.18, 0.1), "SEV_Window")
    # water tank on stilts (left)
    for dx, dy in ((-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9), (0.9, 0.9)):
        k.box((-12.6 + dx, 4.0 + dy, 1.0), (0.14, 0.14, 2.0), "SEV_Metal")
    k.cyl((-12.6, 4.0, 3.2), 1.3, 2.4, "SEV_Casing", segs=18)
    k.cyl((-12.6, 4.0, 4.5), 1.35, 0.3, "SEV_Casing", segs=18, r2=0.4)
    # AC units / vents along the parapet, cable runs on the floor
    for x in (-9.0, -6.6, 6.8, 9.2):
        k.box((x, 4.7, 0.45), (1.6, 1.0, 0.9), "SEV_Concrete", bevel=0.03)
        k.cyl((x, 4.7, 0.92), 0.36, 0.05, "SEV_Metal", segs=12)
    for i in range(3):
        k.box((0, 5.25 - i * 0.12, 0.05 + i * 0.03), (30, 0.06, 0.06), "SEV_Metal")
    for x in (-11.2, 10.7):                              # steam vents (particles in the scene)
        k.cyl((x, 3.6, 0.35), 0.28, 0.7, "SEV_Metal", segs=10)

    # ---- close detail just behind the fighters -----------------------------
    # A torn armour plate from the conduit, smashed into the roof, still
    # bleeding Origin light through the cracks around it.
    k.box((-4.6, 3.7, 0.55), (3.2, 0.35, 1.9), "SEV_Casing", rot=(62, 8, 14), bevel=0.04)
    k.box((-4.4, 3.45, 0.95), (2.6, 0.06, 0.12), "SEV_Metal", rot=(62, 8, 14))
    for i in range(7):
        a = rnd.uniform(0, 2 * math.pi)
        p0 = Vector((-4.6, 3.7, 0.006))
        p1 = p0 + Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(1.0, 2.4)
        k.box(((p0 + p1) / 2).to_tuple(), ((p1 - p0).length, 0.05, 0.006), "SEV_Origin",
              rot=(0, 0, math.degrees(a)))
    for i in range(14):                                  # concrete rubble thrown out of the impact
        k.box((-4.6 + rnd.uniform(-2.4, 2.4), 3.7 + rnd.uniform(-1.6, 1.2), 0.08),
              (rnd.uniform(0.12, 0.45), rnd.uniform(0.12, 0.4), rnd.uniform(0.08, 0.25)), "SEV_Concrete",
              rot=(rnd.uniform(-20, 20), rnd.uniform(-20, 20), rnd.uniform(0, 90)))
    for j, (dx, dy, dz, s_) in enumerate(((0, 0, 0, 1.0), (1.05, 0.1, 0, 0.9), (0.45, 0.05, 0.95, 0.85))):
        c = Vector((5.6 + dx, 4.3 + dy, 0.5 * s_ + dz))   # crate stack, banded
        k.box(c, (1.0 * s_, 1.0 * s_, 1.0 * s_), "SEV_Casing", bevel=0.03, rot=(0, 0, j * 7))
        for zz in (-0.3, 0.3):
            k.box(c + Vector((0, -0.51 * s_, zz * s_)), (1.02 * s_, 0.02, 0.07), "SEV_Metal", rot=(0, 0, j * 7))
    g = Vector((-8.2, 2.9, 0))                           # generator with exhaust and cables
    k.box(g + Vector((0, 0, 0.55)), (1.8, 1.0, 1.1), "SEV_Casing", bevel=0.04)
    for i in range(6):
        k.box(g + Vector((-0.6 + i * 0.24, -0.51, 0.65)), (0.12, 0.02, 0.6), "SEV_Metal")
    k.cyl(g + Vector((0.6, 0.2, 1.5)), 0.1, 0.9, "SEV_Metal", segs=8)
    k.box(g + Vector((-0.5, -0.52, 0.95)), (0.18, 0.02, 0.08), "SEV_Neon")  # status LED
    for i in range(3):
        beam(k, g + Vector((0.9, 0.1 * i, 0.15)), Vector((-6.6, 4.4 + 0.1 * i, 0.06)), 0.05, "SEV_Metal")
    d = Vector((8.9, 4.7, 0))                            # satellite dish on a tripod
    for t in range(3):
        ang = t * 2 * math.pi / 3
        beam(k, d + Vector((math.cos(ang) * 0.5, math.sin(ang) * 0.5, 0)), d + Vector((0, 0, 1.4)), 0.05, "SEV_Metal")
    k.sphere(d + Vector((0, -0.25, 2.0)), 0.9, "SEV_Casing", segs=12, rings=6, scale=(1.0, 0.25, 1.0))
    beam(k, d + Vector((0, -0.4, 2.0)), d + Vector((0, -1.1, 2.0)), 0.04, "SEV_Metal")
    a_ = Vector((14.6, 4.9, 0))                          # antenna mast with an aircraft warning light
    beam(k, a_, a_ + Vector((0, 0, 9.0)), 0.12, "SEV_Metal")
    for zz in (3.0, 5.5, 7.5):
        beam(k, a_ + Vector((-0.6, 0, zz)), a_ + Vector((0.6, 0, zz)), 0.05, "SEV_Metal")
    k.sphere(a_ + Vector((0, 0, 9.15)), 0.14, "SEV_Origin", segs=6, rings=4)
    for z in (0.3, 0.55):                                # pipe run along the parapet
        k.cyl((0, 5.3, z), 0.07, 30, "SEV_Metal", segs=8, rot=(0, 90, 0))
    for x in range(-14, 15, 3):
        k.box((x, 5.35, 0.42), (0.1, 0.2, 0.5), "SEV_Metal")

    # ---- the district below and the skyline -------------------------------
    GROUND = -32.0

    def building(cx, cy, w, d, h, win_p, crown):
        k.box((cx, cy, (GROUND + h) / 2), (w, d, h - GROUND), "SEV_Building")
        front = cy - d / 2 - 0.02
        cols = max(1, int((w - 1.2) / 1.25))
        rows = max(1, int((h - GROUND - 4) / 1.9))
        for c in range(cols):
            for r in range(rows):
                if rnd.random() < win_p:
                    k.quad((cx - (cols - 1) * 0.625 + c * 1.25, front, GROUND + 3 + r * 1.9), 0.55, 0.85,
                           "SEV_Window")
        for lz in range(int(GROUND + 8), int(h), 9):     # ledges catch the light
            k.box((cx, front - 0.1, lz), (w + 0.2, 0.25, 0.18), "SEV_Concrete")
        if crown:
            k.box((cx, cy, h + 0.8), (w * 0.6, d * 0.6, 1.6), "SEV_Building")
            k.box((cx, cy - d * 0.3 - 0.02, h + 1.3), (w * 0.4, 0.05, 0.12), "SEV_Neon")
        if rnd.random() < 0.5:                           # facade AC boxes and a drainpipe
            for j in range(4):
                k.box((cx + rnd.uniform(-w / 3, w / 3), front - 0.3, rnd.uniform(-10, h - 3)), (0.8, 0.6, 0.55),
                      "SEV_Concrete")
            k.box((cx + w / 2 - 0.3, front - 0.15, (GROUND + h) / 2), (0.16, 0.16, h - GROUND), "SEV_Metal")

    # Only the nearest row is real geometry; the far city is the painted
    # panorama sky (tools/blender/arena_panorama.py -> neon_sky.png).
    for row, (y0, hmin, hmax, wp) in enumerate(((16, 4, 22, 0.32),)):
        x = -70.0 + rnd.uniform(0, 4)
        while x < 70:
            w = rnd.uniform(7, 13) * (1 + row * 0.3)
            if row == 0 and -6 < x + w / 2 < 8:          # keep a gap: the street the conduit fell into
                x += w * 0.6
                continue
            building(x + w / 2, y0 + rnd.uniform(0, 6) + w * 0.2, w - 0.6, rnd.uniform(6, 10),
                     rnd.uniform(hmin, hmax), wp, rnd.random() < 0.35)
            x += w
    # invented-script neon signs: stacks of glyph strokes (no real lettering)
    def glyph(cx, y, cz, s, seed):
        g = random.Random(seed)
        for kk in range(g.randint(2, 4)):
            x0, z0 = g.uniform(-0.4, 0.4) * s, g.uniform(-0.6, 0.6) * s
            if g.random() < 0.5:
                k.box((cx + x0, y, cz + z0), (g.uniform(0.3, 0.9) * s, 0.06, 0.08 * s), "SEV_Neon")
            else:
                k.box((cx + x0, y, cz + z0), (0.08 * s, 0.06, g.uniform(0.3, 1.0) * s), "SEV_Neon")

    for i, (gx, gy, gz) in enumerate(((-17, 13.0, 9), (-4.5, 15.5, 6), (9.5, 14.5, 12), (21, 13.5, 4),
                                       (-28, 31, 22), (26, 32, 25))):
        k.box((gx, gy + 0.08, gz), (0.25, 0.1, 5.4), "SEV_Building")
        for j in range(4):
            glyph(gx, gy - 0.02, gz + 2.0 - j * 1.35, 1.1, 100 + i * 10 + j)

    # ---- THE SEVERED LINE: the broken Origin conduit -----------------------
    def ring(c, axis, r, w, mat, segs=28):
        """A rib: a short thick band around the conduit axis."""
        axis = Vector(axis).normalized()
        u = axis.orthogonal().normalized()
        v = axis.cross(u)
        loops = []
        for (rr, off) in ((r, -w / 2), (r, w / 2), (r * 0.94, w / 2), (r * 0.94, -w / 2)):
            loops.append([k.bm.verts.new(Vector(c) + axis * off + (u * math.cos(2 * math.pi * s / segs)
                                                                    + v * math.sin(2 * math.pi * s / segs)) * rr)
                          for s in range(segs)])
        for a, b in zip(loops, loops[1:] + loops[:1]):
            for s in range(segs):
                k.bm.faces.new((a[s], a[(s + 1) % segs], b[(s + 1) % segs], b[s]))
        k._finish_new((0, 0, 0), (0, 0, 0), mat)

    def obox(c, size, basis, mat):
        """Box oriented by a 3x3 basis (columns = local X, Y, Z)."""
        r = bmesh.ops.create_cube(k.bm, size=1.0)
        bmesh.ops.scale(k.bm, vec=size, verts=r["verts"])
        bmesh.ops.transform(k.bm, matrix=basis.to_4x4(), verts=r["verts"])
        k._finish_new(c, (0, 0, 0), mat)

    def conduit(p0, p1, r, broken):
        p0, p1 = Vector(p0), Vector(p1)
        ax = (p1 - p0)
        L = ax.length
        ax.normalize()
        u = ax.orthogonal().normalized()
        w = ax.cross(u)
        # glowing core (visible where armour is torn away)
        rot = ax.to_track_quat("Z", "Y").to_euler()
        # open-ended so the torn end shows a glowing rim, not a flat disc
        k.cyl(p0 + ax * (L - 1.2) / 2, r * 0.8, L - 1.2, "SEV_Origin", segs=16,
              rot=tuple(math.degrees(a) for a in rot), caps=False)
        n_plates = 10
        for i in range(n_plates):
            ang = 2 * math.pi * i / n_plates
            d = u * math.cos(ang) + w * math.sin(ang)
            t0 = 0.0
            while t0 < L:
                t1 = min(L, t0 + rnd.uniform(3.0, 6.0))
                torn = 0.12 + (0.55 * (t1 / L) ** 3 if broken else 0.0)
                if rnd.random() > torn:
                    basis = Matrix((d, ax.cross(d), ax)).transposed()
                    obox(p0 + ax * ((t0 + t1) / 2) + d * r * 0.92, (0.36, r * 0.82, t1 - t0 - 0.16),
                         basis, "SEV_Casing")
                t0 = t1
        t = 1.5
        while t < L - 1.0:
            if not broken or t < L * 0.8:
                ring(p0 + ax * t, ax, r * 1.08, 0.45, "SEV_Casing")
                ring(p0 + ax * (t + 0.3), ax, r * 1.12, 0.08, "SEV_Metal", segs=24)       # bolted flange
            t += rnd.uniform(4.0, 6.5)
        # service pipes riding along the top, clamped to the ribs
        rot_ax = tuple(math.degrees(a) for a in ax.to_track_quat("Z", "Y").to_euler())
        up_side = (w if w.z > 0 else -w)
        for j, off in enumerate((-0.55, 0.0, 0.55)):
            pc = (p0 + p1) / 2 + up_side * (r * 1.18) + u * off
            k.cyl(pc, 0.16 if j != 1 else 0.24, L * (0.78 if broken else 0.98), "SEV_Metal", segs=10, rot=rot_ax)
        if broken:                                       # exposed Origin coils where the armour is gone
            t = L * 0.72
            while t < L - 0.8:
                ring(p0 + ax * t, ax, r * 0.86, 0.12, "SEV_Origin", segs=20)
                t += 0.7
        if broken:                                       # jagged lip and dangling cables
            for i in range(12):
                ang = rnd.uniform(0, 2 * math.pi)
                d = u * math.cos(ang) + w * math.sin(ang)
                base = p1 + d * r * 0.85
                tip = base + ax * rnd.uniform(0.6, 2.4) + d * rnd.uniform(0.2, 0.9)
                basis = Matrix((d, ax.cross(d), (tip - base).normalized())).transposed()
                obox((base + tip) / 2, (0.3, 0.3, (tip - base).length), basis, "SEV_Casing")
            for i in range(5):
                q = p1 + Vector((rnd.uniform(-1.5, 1.5), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
                for j in range(5):
                    q2 = q + Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.3, 0.3), -rnd.uniform(1.2, 2.2)))
                    k.cyl((q + q2) / 2, 0.08, (q2 - q).length, "SEV_Metal", segs=5,
                          rot=tuple(math.degrees(a) for a in (q2 - q).normalized().to_track_quat("Z", "Y").to_euler()))
                    q = q2

    conduit((-75, 95, 52), (-16, 40, 20), 3.0, False)
    conduit((-16, 40, 20), (4, 22, 5.5), 3.0, True)
    conduit((12, 24, -20), (30, 44, -6), 2.8, True)       # a second piece lying in the street

    # torn billboard frame (the poster itself is a Sprite3D in the scene)
    k.box((8.6, 17.6, 13.0), (6.6, 0.3, 7.6), "SEV_Metal")
    for x in (6.2, 11.0):
        k.box((x, 18.0, 4.0), (0.3, 0.3, 12), "SEV_Metal")
    return k


def torus_mesh(k, c, R, r_rad, r_depth, mat, segs=48, sides=8, rot=(0, 0, 0)):
    """Torus in the local XZ plane (ring faces -Y), then rotated by rot (deg)."""
    vs = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ring_ = []
        for j in range(sides):
            b = 2 * math.pi * j / sides
            rr = R + math.cos(b) * r_rad
            ring_.append(k.bm.verts.new(Vector((math.cos(a) * rr, math.sin(b) * r_depth, math.sin(a) * rr))))
        vs.append(ring_)
    for i in range(segs):
        for j in range(sides):
            a, b = vs[i], vs[(i + 1) % segs]
            k.bm.faces.new((a[j], b[j], b[(j + 1) % sides], a[(j + 1) % sides]))
    k._finish_new(c, rot, mat)


def shard(k, base, direction, length, width, mat, twist=0.0):
    """Faceted crystal blade: 5-sided prism tapering to a point."""
    base, d = Vector(base), Vector(direction).normalized()
    u = d.orthogonal().normalized()
    v = d.cross(u)
    ring_, mid = [], []
    for i in range(5):
        a = twist + 2 * math.pi * i / 5
        ring_.append(k.bm.verts.new(base + (u * math.cos(a) + v * math.sin(a)) * width * (0.7 + 0.3 * math.sin(i * 2.1))))
        a2 = twist + 0.3 + 2 * math.pi * i / 5
        mid.append(k.bm.verts.new(base + d * length * 0.6 + (u * math.cos(a2) + v * math.sin(a2)) * width * 0.55))
    tip = k.bm.verts.new(base + d * length)
    for i in range(5):
        j = (i + 1) % 5
        k.bm.faces.new((ring_[i], ring_[j], mid[j], mid[i]))
        k.bm.faces.new((mid[i], mid[j], tip))
    k._finish_new((0, 0, 0), (0, 0, 0), mat)


# Each bloodline's emblem as a flat outline (unit size). All six are original
# marks made for this game.
def _emblem_points(kind):
    P = []
    if kind == "kairo":            # a rising flame-blade
        P = [(0, 1), (0.25, 0.35), (0.5, 0.55), (0.3, -0.2), (0.45, -1), (0, -0.55), (-0.45, -1), (-0.3, -0.2),
             (-0.5, 0.55), (-0.25, 0.35)]
    elif kind == "drakon":         # three claw slashes joined at the root
        P = [(-0.8, 1), (-0.5, 1), (0.1, -0.6), (0.25, 1), (0.55, 1), (0.6, -0.9), (0.95, 0.9), (1.0, -1), (-0.2, -1)]
    elif kind == "seraphina":      # a single swept wing
        P = [(-1, -0.6), (-0.2, 0.0), (0.2, 0.9), (0.4, 0.4), (0.9, 0.7), (0.7, 0.1), (1.0, 0.0), (0.4, -0.4),
             (0.0, -0.3)]
    elif kind == "nox":            # crescent
        P = [(math.cos(math.radians(40 + i * 17.5)), math.sin(math.radians(40 + i * 17.5))) for i in range(17)]
        P += [(0.25 + 0.7 * math.cos(math.radians(320 - i * 17.5)), 0.7 * math.sin(math.radians(320 - i * 17.5)))
              for i in range(17)]
    elif kind == "vexa":           # a thorned spiral hook
        P = [((1.0 - 0.7 * t) * math.cos(t * 4.2), (1.0 - 0.7 * t) * math.sin(t * 4.2)) for t in [i / 23 for i in range(24)]]
        P += [((0.75 - 0.6 * t + (0.25 if i % 6 == 0 else 0)) * math.cos(t * 4.2),
               (0.75 - 0.6 * t + (0.25 if i % 6 == 0 else 0)) * math.sin(t * 4.2)) for i, t in
              [(i, i / 23) for i in range(23, -1, -1)]]
    return P


def origin():
    """The Origin Chamber (boss arena): inside the Origin core. Black glass
    floor with red light in the fractures, the molten Origin heart in a cage
    of rings, a dome of obsidian blades, and the six bloodline emblems frozen
    in crystal slabs on the walls. Mobile: one mesh, 8 materials (six of them
    are the emblem colours)."""
    rnd = random.Random(7)
    BLOOD = (("kairo", (1.0, 0.3, 0.06)), ("drakon", (0.2, 0.9, 0.3)), ("seraphina", (1.0, 0.85, 0.5)),
             ("nox", (0.55, 0.3, 1.0)), ("vexa", (1.0, 0.15, 0.55)), ("ryuen", (0.25, 0.55, 1.0)))
    k = Kit("OriginChamber", [
        M("ORI_Obsidian", (0.012, 0.01, 0.012), 0.12, 0.0),
        M("ORI_Origin", (0.25, 0.0, 0.0), 0.4, 0.0, (0.9, 0.02, 0.02), 1.0),
    ] + [M(f"ORI_Emblem_{n}", tuple(c * 0.5 for c in col), 0.4, 0.6, col, 0.9) for n, col in BLOOD])
    C0 = Vector((0, 10, 0))
    HEART = Vector((0, 15, 4.9))
    # ---- floor: black glass with red fractures --------------------------------
    k.disc((C0.x, C0.y, -0.02), 34, "ORI_Obsidian", sides=48)
    k.cyl((0, 0, 0.15), 9.0, 0.3, "ORI_Obsidian", segs=48)
    torus_mesh(k, (0, 0, 0.3), 9.02, 0.03, 0.03, "ORI_Origin", segs=64, sides=4, rot=(90, 0, 0))
    for i in range(46):
        p = Vector((rnd.uniform(-20, 20), rnd.uniform(-8, 24), 0))
        on_stage = p.length < 9.0
        z = 0.305 if on_stage else 0.004
        ang = rnd.uniform(0, 2 * math.pi)
        for s_ in range(rnd.randint(3, 7)):
            ang += rnd.uniform(-0.8, 0.8)
            q = p + Vector((math.cos(ang), math.sin(ang), 0)) * rnd.uniform(0.6, 1.6)
            if on_stage and q.length > 8.9:
                break
            beam(k, (p.x, p.y, z), (q.x, q.y, z), rnd.uniform(0.04, 0.09), "ORI_Origin", h=0.006)
            p = q
    # ---- dome of obsidian blades ------------------------------------------------
    for i in range(150):
        a = rnd.uniform(math.radians(-25), math.radians(205))
        r = rnd.uniform(22, 30)
        base = Vector((math.cos(a) * r, C0.y + math.sin(a) * r, rnd.uniform(-1, 2)))
        d = Vector((-math.cos(a), -math.sin(a), 0)) * rnd.uniform(0.25, 0.7) + Vector((0, 0, rnd.uniform(1.0, 3.2)))
        shard(k, base, d, rnd.uniform(12, 30), rnd.uniform(0.8, 2.4), "ORI_Obsidian", rnd.uniform(0, 6))
    for i in range(70):
        a = rnd.uniform(math.radians(-30), math.radians(210))
        r = rnd.uniform(15, 19)
        base = Vector((math.cos(a) * r, C0.y + math.sin(a) * r, -0.5))
        d = Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(0.2, 0.9) + Vector((0, 0, 1))
        shard(k, base, d, rnd.uniform(2.5, 7), rnd.uniform(0.3, 0.9), "ORI_Obsidian", rnd.uniform(0, 6))
    ret = bmesh.ops.create_uvsphere(k.bm, u_segments=32, v_segments=16, radius=40)    # dark vault, seen from inside
    bmesh.ops.reverse_faces(k.bm, faces=list({f for v in ret["verts"] for f in v.link_faces}))
    k._finish_new((C0.x, C0.y, -6), (0, 0, 0), "ORI_Obsidian")
    # ---- the Origin heart -------------------------------------------------------
    k.sphere(HEART, 2.2, "ORI_Origin", segs=18, rings=12)
    for i in range(22):                                   # molten spikes forcing through the crust
        a, b = rnd.uniform(0, 2 * math.pi), math.acos(rnd.uniform(-1, 1))
        n = Vector((math.sin(b) * math.cos(a), math.sin(b) * math.sin(a), math.cos(b)))
        shard(k, HEART + n * 1.9, n, rnd.uniform(0.7, 1.6), rnd.uniform(0.12, 0.25), "ORI_Origin", rnd.uniform(0, 6))
    for i in range(95):                                      # cooled crust plates; light shows in the gaps
        a, b = rnd.uniform(0, 2 * math.pi), math.acos(rnd.uniform(-1, 1))
        n = Vector((math.sin(b) * math.cos(a), math.sin(b) * math.sin(a), math.cos(b)))
        rot = n.to_track_quat("Z", "Y").to_euler()
        k.box(HEART + n * 2.2, (rnd.uniform(0.6, 0.95), rnd.uniform(0.6, 0.95), 0.1), "ORI_Obsidian",
              rot=tuple(math.degrees(x) for x in rot[:2]) + (rnd.uniform(0, 90),))
    # (the cage rings turn, so they are TorusMesh nodes in scenes/arenas/origin_chamber.tscn)
    for i in range(16):                                      # crystal pedestal under the heart
        a = rnd.uniform(0, 2 * math.pi)
        base = HEART + Vector((math.cos(a) * rnd.uniform(0.5, 3), math.sin(a) * rnd.uniform(0.5, 3), -HEART.z))
        shard(k, base, (math.cos(a) * 0.3, math.sin(a) * 0.3, 1), rnd.uniform(1.5, 4.5), rnd.uniform(0.3, 0.8),
              "ORI_Obsidian")
    # ---- the six bloodline emblems frozen in crystal ----------------------------
    for (kind, col), deg in zip(BLOOD, (-165, -125, -95, 95, 125, 165)):
        a = math.radians(deg / 2 + 90)
        pos = Vector((math.cos(a) * 15.5, C0.y + math.sin(a) * 15.5 * 0.75, 4.5 + abs(deg) * 0.012))
        n = (Vector((0, 0, 1.2)) - pos).normalized()
        n.z = -0.15
        n.normalize()
        u = Vector((0, 0, 1)).cross(n).normalized()
        v = n.cross(u)
        size = 2.3
        for j in range(3):
            shard(k, pos - n * 1.1 + u * rnd.uniform(-0.6, 0.6) - v * size * 1.2,
                  v + n * 0.25 + u * rnd.uniform(-0.3, 0.3), size * rnd.uniform(2.6, 3.4), size * 0.8,
                  "ORI_Obsidian", j * 1.3)
        front = pos + n * 0.35
        mat = f"ORI_Emblem_{kind}"
        if kind == "ryuen":                                  # wave breaking inside a ring
            ring_c = front
            outer = [k.bm.verts.new(ring_c + (u * math.cos(t) + v * math.sin(t)) * size)
                     for t in [2 * math.pi * i / 32 for i in range(32)]]
            inner = [k.bm.verts.new(ring_c + (u * math.cos(t) + v * math.sin(t)) * size * 0.8)
                     for t in [2 * math.pi * i / 32 for i in range(32)]]
            for i in range(32):
                k.bm.faces.new((outer[i], outer[(i + 1) % 32], inner[(i + 1) % 32], inner[i]))
            k._finish_new((0, 0, 0), (0, 0, 0), mat)
            top = [k.bm.verts.new(front + (u * (-0.7 + 1.4 * t) + v * (0.3 * math.sin(t * 6) - 0.2)) * size)
                   for t in [i / 11 for i in range(12)]]
            bot = [k.bm.verts.new(front + (u * (-0.7 + 1.4 * t) + v * (0.3 * math.sin(t * 6) - 0.45)) * size)
                   for t in [i / 11 for i in range(12)]]
            for i in range(11):
                k.bm.faces.new((bot[i], bot[i + 1], top[i + 1], top[i]))
            k._finish_new((0, 0, 0), (0, 0, 0), mat)
        else:
            vs = [k.bm.verts.new(front + (u * x + v * y) * size) for x, y in _emblem_points(kind)]
            f = k.bm.faces.new(vs)
            f.normal_update()
            if f.normal.dot(n) < 0:
                f.normal_flip()
            k._finish_new((0, 0, 0), (0, 0, 0), mat)
    # ---- close detail just behind the fighters -----------------------------
    for i in range(9):                                   # crystal clusters along the back of the stage
        a = math.radians(18 + i * 18 + rnd.uniform(-5, 5))
        c = Vector((math.cos(a) * 10.4, math.sin(a) * 10.4, 0))
        for j in range(rnd.randint(3, 5)):
            d = Vector((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.2, 0.5), 1))
            shard(k, c + Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.4, 0.4), -0.1)), d, rnd.uniform(0.8, 2.6),
                  rnd.uniform(0.15, 0.4), "ORI_Origin" if j == 0 and i % 3 == 0 else "ORI_Obsidian", rnd.uniform(0, 6))
    for x in (-7.5, 7.8):                                # broken obsidian pillars flanking the stage
        k.cyl((x, 7.5, 1.4), 0.75, 2.8, "ORI_Obsidian", segs=7)
        shard(k, (x, 7.5, 2.7), (0.3, -0.2, 1), 1.4, 0.65, "ORI_Obsidian", 0.4)
        for j in range(4):
            k.box((x + rnd.uniform(-1.2, 1.2), 7.5 + rnd.uniform(-1.4, 0.4), 0.15),
                  (rnd.uniform(0.3, 0.7), rnd.uniform(0.3, 0.6), 0.3), "ORI_Obsidian", rot=(rnd.uniform(-15, 15), 0, rnd.uniform(0, 90)))
    for i in range(14):                                  # fragments hanging in the air just behind the fight
        p = Vector((rnd.uniform(-8, 8), rnd.uniform(4.5, 9), rnd.uniform(2.6, 5.5)))
        shard(k, p, (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)), rnd.uniform(0.3, 0.8),
              rnd.uniform(0.06, 0.18), "ORI_Obsidian", rnd.uniform(0, 6))
    # floating debris frozen mid-air
    for i in range(60):
        p = Vector((rnd.uniform(-16, 16), rnd.uniform(6, 22), rnd.uniform(3, 14)))
        if (p - HEART).length < 6:
            continue
        shard(k, p, (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)), rnd.uniform(0.3, 1.4),
              rnd.uniform(0.08, 0.3), "ORI_Obsidian", rnd.uniform(0, 6))
    return k


ARENAS = {"ascendant": ascendant, "temple": temple, "neon": neon, "origin": origin}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/arenas")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-bake", action="store_true", help="skip the ambient-occlusion bake (fast preview)")
    ap.add_argument("--materials-only", action="store_true",
                    help="only rewrite the Godot materials (reuses the baked AO/light maps)")
    a = ap.parse_args(argv)
    for name, fn in ARENAS.items():
        if a.only and a.only != name:
            continue
        # A builder returns the arena Kit, or (Kit, [(extra Kit, file name), ...])
        # for separately animated parts such as The Pit's crowd.
        res = fn()
        main_kit, extras = (res if isinstance(res, tuple) else (res, []))
        if a.materials_only:
            d = f"{a.out}/{name}"
            rel = lambda f: "res://" + os.path.relpath(os.path.abspath(f"{d}/{f}"), ROOT).replace(os.sep, "/")
            write_godot_materials(d, main_kit.mats, rel(f"{name}_ao.png") if os.path.exists(f"{d}/{name}_ao.png") else "",
                                  rel(f"{name}_light.png") if os.path.exists(f"{d}/{name}_light.png") else "")
            print(f"[arena] {name}: materials rewritten")
            continue
        main_kit.export(f"{a.out}/{name}/{name}_arena.glb", bake_ao=not a.no_bake)
        for kit, fname in extras:
            kit.export(f"{a.out}/{name}/{fname}", bake_ao=False, materials=False)


if __name__ == "__main__":
    main()
