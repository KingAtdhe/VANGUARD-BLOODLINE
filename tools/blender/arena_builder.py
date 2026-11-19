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

    def export(self, path):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        mesh = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
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
        print(f"[arena] {self.name}: tris={tris} materials={len(self.mats)}")
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True, export_apply=False,
                                  export_materials="EXPORT", export_animations=False)


def M(name, rgb, rough=0.8, metal=0.0, emit=None, strength=0.0):
    return (name, rgb, rough, metal, emit or rgb, strength)


# ------------------------------------------------------------ Ascendant --
def ascendant():
    """Premium tournament arena: octagon stage, light rig, stands, screens."""
    rnd = random.Random(7)
    k = Kit("AscendantArena", [
        M("ASC_Floor", (0.05, 0.055, 0.075), 0.25, 0.3),
        M("ASC_FloorInlay", (0.12, 0.13, 0.17), 0.35, 0.5),
        M("ASC_Gold", (0.9, 0.62, 0.22), 0.3, 1.0),
        M("ASC_GlowGold", (1.0, 0.7, 0.25), 0.4, 0.0, (1.0, 0.62, 0.18), 6.0),
        M("ASC_GlowBlue", (0.2, 0.5, 1.0), 0.4, 0.0, (0.15, 0.45, 1.0), 6.0),
        M("ASC_Structure", (0.07, 0.075, 0.09), 0.6, 0.6),
        M("ASC_Crowd", (0.03, 0.03, 0.04), 0.9),
        M("ASC_Screen", (0.05, 0.1, 0.25), 0.3, 0.0, (0.12, 0.3, 0.9), 2.2),
    ])
    # Arena bowl floor and the raised octagonal stage.
    k.box((0, 6, -0.6), (70, 50, 1.0), "ASC_Structure")
    k.cyl((0, 0, -0.25), 9.5, 0.5, "ASC_Floor", segs=8, rot=(0, 0, 22.5))
    k.ring((0, 0, 0), 9.5, 9.75, "ASC_GlowGold", sides=8, z0=-0.5, z1=0.03)
    k.ring((0, 0, 0), 7.6, 7.75, "ASC_GlowBlue", sides=8, z0=0.0, z1=0.006)
    k.ring((0, 0, 0), 2.2, 2.32, "ASC_FloorInlay", segs=40, z0=0.0, z1=0.004)
    k.ring((0, 0, 0), 1.2, 1.26, "ASC_GlowGold", segs=40, z0=0.0, z1=0.005)
    for a in range(8):  # spokes in the floor
        ang = math.radians(a * 45 + 22.5)
        k.box((math.cos(ang) * 5.0, math.sin(ang) * 5.0, 0.002), (5.0, 0.06, 0.004), "ASC_FloorInlay",
              rot=(0, 0, math.degrees(ang)))
    for a in range(8):  # corner posts with glowing caps
        ang = math.radians(a * 45)
        p = (math.cos(ang) * 9.25, math.sin(ang) * 9.25, 0.6)
        k.box(p, (0.35, 0.35, 1.2), "ASC_Gold", bevel=0.04)
        k.box((p[0], p[1], 1.25), (0.38, 0.38, 0.1), "ASC_GlowBlue")
    # Stands: tiers rising behind the stage, with a crowd silhouette.
    for t in range(9):
        y = 13 + t * 1.6
        z = 0.4 + t * 1.05
        k.box((0, y, z - 0.5), (64, 1.6, 1.0 + 0.0), "ASC_Structure")
        k.box((0, y - 0.79, z - 0.02), (64, 0.04, 0.05), "ASC_GlowBlue" if t % 3 == 0 else "ASC_Structure")
        x = -30.0
        while x < 30.0:
            if rnd.random() < 0.82:
                h = rnd.uniform(0.55, 0.75)
                k.box((x, y + 0.1, z + h / 2), (0.42, 0.3, h), "ASC_Crowd")
                k.sphere((x, y + 0.1, z + h + 0.14), 0.13, "ASC_Crowd", segs=6, rings=4)
            x += rnd.uniform(0.55, 0.85)
    # Giant screens and the hanging light rig.
    for sx in (-1, 1):
        k.box((sx * 12, 24, 10), (9.6, 0.4, 5.6), "ASC_Structure")
        k.quad((sx * 12, 23.78, 10), 9.0, 5.0, "ASC_Screen")
        k.box((sx * 12, 23.76, 7.35), (9.6, 0.05, 0.08), "ASC_GlowGold")
    k.box((0, 24, 13.5), (11, 0.4, 3.4), "ASC_Structure")
    k.quad((0, 23.78, 13.5), 10.4, 2.8, "ASC_Screen")
    for r_, z in ((11.0, 12.0), (7.5, 12.6)):
        k.ring((0, 2, 0), r_, r_ + 0.25, "ASC_Structure", sides=8, z0=z, z1=z + 0.35)
        k.ring((0, 2, 0), r_ + 0.02, r_ + 0.23, "ASC_GlowBlue", sides=8, z0=z - 0.03, z1=z)
    for a in range(16):  # spot cans on the rig
        ang = math.radians(a * 22.5)
        k.cyl((math.cos(ang) * 11.1, 2 + math.sin(ang) * 11.1, 11.75), 0.22, 0.45, "ASC_Gold", segs=8)
        k.disc((math.cos(ang) * 11.1, 2 + math.sin(ang) * 11.1, 11.52), 0.18, "ASC_GlowGold", sides=8)
    for sx in (-1, 1):  # pylons with banners
        for y in (6, 16):
            k.box((sx * 17, y, 7), (0.6, 0.6, 14), "ASC_Structure")
            k.box((sx * 17 - sx * 0.31, y, 7), (0.02, 0.4, 13), "ASC_GlowGold")
        k.box((sx * 15.5, 10, 7), (0.1, 3.0, 8.0), "ASC_FloorInlay")
        k.box((sx * 15.44, 10, 7), (0.02, 2.6, 7.4), "ASC_GlowBlue")
    return k


# ------------------------------------------------------- Forgotten Temple --
def temple():
    """Ancient ruins at dusk: cracked slabs, broken columns, torches, statue."""
    rnd = random.Random(11)
    k = Kit("ForgottenTemple", [
        M("TMP_Stone", (0.42, 0.37, 0.31), 0.95),
        M("TMP_StoneDark", (0.22, 0.2, 0.18), 0.95),
        M("TMP_Moss", (0.16, 0.26, 0.1), 1.0),
        M("TMP_Bronze", (0.45, 0.3, 0.14), 0.45, 0.8),
        M("TMP_Fire", (1.0, 0.55, 0.12), 0.5, 0.0, (1.0, 0.45, 0.08), 8.0),
        M("TMP_Rune", (0.3, 0.75, 0.7), 0.5, 0.0, (0.2, 0.9, 0.8), 1.4),
        M("TMP_Mountain", (0.18, 0.15, 0.2), 1.0),
    ])
    # Courtyard of irregular slabs.
    for ix in range(-9, 10):
        for iy in range(-3, 7):
            w, d = 1.9 + rnd.uniform(-0.05, 0.05), 1.9 + rnd.uniform(-0.05, 0.05)
            z = rnd.uniform(-0.03, 0.0) - 0.15
            mat = "TMP_StoneDark" if rnd.random() < 0.18 else "TMP_Stone"
            k.box((ix * 2.0, iy * 2.0, z), (w, d, 0.3), mat, rot=(0, 0, rnd.uniform(-1.5, 1.5)), bevel=0.04)
            if rnd.random() < 0.12:
                k.box((ix * 2.0 + rnd.uniform(-0.5, 0.5), iy * 2.0 + rnd.uniform(-0.5, 0.5), 0.005),
                      (rnd.uniform(0.4, 1.0), rnd.uniform(0.3, 0.8), 0.02), "TMP_Moss")
    k.box((0, 0, 0.003), (0.08, 3.0, 0.006), "TMP_Rune")  # centre line rune
    k.ring((0, 0, 0), 1.6, 1.7, "TMP_Rune", segs=36, z0=0.0, z1=0.006)
    # Stairs up to the inner sanctum, flanked by columns.
    for s in range(6):
        k.box((0, 13 + s * 0.6, 0.15 + s * 0.3), (16 - s * 0.6, 0.6, 0.3), "TMP_Stone", bevel=0.03)
    k.box((0, 19.5, 1.0), (24, 6, 2.0), "TMP_StoneDark", bevel=0.05)
    k.box((0, 20, 6.5), (10, 3, 9.0), "TMP_Stone", bevel=0.08)       # sanctum wall
    k.box((0, 18.45, 4.6), (3.2, 0.2, 5.0), "TMP_StoneDark")          # doorway
    k.quad((0, 18.33, 4.6), 2.8, 4.6, "TMP_Rune")
    k.box((0, 18.4, 11.5), (12, 3.6, 0.8), "TMP_Stone", bevel=0.05)   # lintel
    # Guardian statue head carved above the door.
    k.sphere((0, 18.6, 13.6), 1.9, "TMP_Stone", segs=14, rings=10, scale=(0.9, 0.85, 1.1))
    k.box((0, 17.0, 13.3), (0.45, 0.6, 0.9), "TMP_Stone")
    for sx in (-1, 1):
        k.box((sx * 0.62, 17.05, 14.0), (0.55, 0.2, 0.16), "TMP_Rune")
    k.box((0, 18.0, 15.35), (3.6, 1.8, 0.35), "TMP_Bronze")           # crown band
    # Columns: some intact, some broken; with a few fallen drums.
    for i, x in enumerate((-13, -9.5, -6, 6, 9.5, 13)):
        y = 9.0 + (i % 2) * 0.8
        h = [9.0, 4.2, 7.5, 9.0, 3.1, 6.4][i]
        k.box((x, y, 0.3), (1.6, 1.6, 0.6), "TMP_StoneDark", bevel=0.05)
        k.cyl((x, y, 0.6 + h / 2), 0.55, h, "TMP_Stone", segs=12)
        for f in range(12):  # flutes
            a = 2 * math.pi * f / 12
            k.box((x + math.cos(a) * 0.55, y + math.sin(a) * 0.55, 0.6 + h / 2), (0.08, 0.08, h * 0.97),
                  "TMP_StoneDark", rot=(0, 0, math.degrees(a)))
        if h > 8:
            k.box((x, y, 0.6 + h + 0.25), (1.5, 1.5, 0.5), "TMP_Stone", bevel=0.05)
        else:
            k.cyl((x + 0.9, y - 1.2, 0.5), 0.5, 1.2, "TMP_Stone", segs=12, rot=(90, 0, rnd.uniform(0, 90)))
        k.box((x, y - 0.56, 0.6 + h * 0.4), (0.9, 0.04, h * 0.5), "TMP_Moss")
    k.box((-11.25, 9.4, 9.85), (5.0, 1.2, 0.7), "TMP_Stone", bevel=0.05)  # surviving architrave
    # Torches on bronze stands.
    for x in (-7.8, 7.8):
        k.cyl((x, 6.5, 0.9), 0.08, 1.8, "TMP_Bronze", segs=8)
        k.cyl((x, 6.5, 1.85), 0.28, 0.25, "TMP_Bronze", segs=10, r2=0.4)
        k.cyl((x, 6.5, 2.15), 0.22, 0.5, "TMP_Fire", segs=8, r2=0.02)
    for x in (-3.6, 3.6):
        k.cyl((x, 17.0, 2.5), 0.3, 1.0, "TMP_Bronze", segs=10, r2=0.45)
        k.cyl((x, 17.0, 3.25), 0.3, 0.6, "TMP_Fire", segs=8, r2=0.02)
    # Hanging vines from the architrave and ruined walls at the sides.
    for i in range(14):
        x = -13.5 + i * 0.4 + rnd.uniform(-0.1, 0.1)
        L = rnd.uniform(1.5, 4.5)
        k.box((x, 8.8, 9.6 - L / 2), (0.05, 0.05, L), "TMP_Moss")
    for sx in (-1, 1):
        for j in range(5):
            h = rnd.uniform(2.0, 5.5)
            k.box((sx * (18 + j * 0.2), 4 + j * 3.5, h / 2), (1.2, 3.4, h), "TMP_StoneDark", bevel=0.06)
    # Distant mountains and a sky band.
    for i in range(14):
        x = -60 + i * 9 + rnd.uniform(-3, 3)
        h = rnd.uniform(14, 30)
        k.cyl((x, 70 + rnd.uniform(-5, 10), h / 2 - 2), rnd.uniform(9, 15), h, "TMP_Mountain", segs=6, r2=0.5,
              rot=(0, 0, rnd.uniform(0, 60)))
    return k


# ---------------------------------------------------------- Neon District --
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

    for row, (y0, hmin, hmax, wp) in enumerate(((16, 4, 22, 0.32), (34, 18, 45, 0.24), (60, 35, 75, 0.16))):
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
            t += rnd.uniform(4.0, 6.5)
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


ARENAS = {"ascendant": ascendant, "temple": temple, "neon": neon}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/arenas")
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    for name, fn in ARENAS.items():
        if a.only and a.only != name:
            continue
        fn().export(f"{a.out}/{name}/{name}_arena.glb")


if __name__ == "__main__":
    main()
