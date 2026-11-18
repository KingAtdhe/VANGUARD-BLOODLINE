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

    def cyl(self, c, r, h, mat, segs=16, r2=None, rot=(0, 0, 0)):
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r,
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
    """Rain-soaked street at night: buildings, neon signs, steam, skyline."""
    rnd = random.Random(23)
    k = Kit("NeonDistrict", [
        M("NEO_Asphalt", (0.035, 0.035, 0.045), 0.12, 0.2),
        M("NEO_Concrete", (0.11, 0.11, 0.13), 0.85),
        M("NEO_Building", (0.05, 0.05, 0.07), 0.6, 0.3),
        M("NEO_Window", (0.22, 0.17, 0.12), 0.4, 0.0, (1.0, 0.68, 0.35), 0.3),
        M("NEO_Magenta", (1.0, 0.1, 0.6), 0.4, 0.0, (1.0, 0.08, 0.55), 7.0),
        M("NEO_Cyan", (0.1, 0.9, 1.0), 0.4, 0.0, (0.05, 0.85, 1.0), 7.0),
        M("NEO_Metal", (0.25, 0.26, 0.28), 0.35, 0.9),
        M("NEO_Line", (0.8, 0.75, 0.3), 0.6),
    ])
    k.box((0, 6, -0.25), (80, 40, 0.5), "NEO_Asphalt")
    for x in range(-14, 15, 4):  # road markings
        k.box((x, 3.2, 0.002), (2.0, 0.12, 0.004), "NEO_Line")
    for y in (-2.6, 7.5):
        k.box((0, y, 0.002), (40, 0.1, 0.004), "NEO_Line")
    k.box((0, 10.5, 0.1), (80, 5.0, 0.2), "NEO_Concrete")  # sidewalk
    k.box((0, 8.05, 0.1), (80, 0.1, 0.2), "NEO_Metal")
    for i in range(10):  # puddles (mirror-like patches)
        k.box((rnd.uniform(-12, 12), rnd.uniform(-2, 5), 0.003), (rnd.uniform(1, 3), rnd.uniform(0.6, 1.5), 0.004),
              "NEO_Metal", rot=(0, 0, rnd.uniform(0, 180)))
    # Building facades with windows, storefronts, neon trims.
    x = -34.0
    bi = 0
    while x < 34.0:
        w = rnd.uniform(6.0, 10.0)
        h = rnd.uniform(14.0, 34.0)
        y = 15.5 + rnd.uniform(-0.5, 2.0)
        cx = x + w / 2
        k.box((cx, y, h / 2), (w - 0.3, 6.0, h), "NEO_Building")
        front = y - 3.02
        for fx in range(int((w - 1.0) / 1.1)):
            for fz in range(int((h - 5.0) / 1.6)):
                if rnd.random() < 0.55:
                    k.quad((x + 0.9 + fx * 1.1, front, 5.0 + fz * 1.6), 0.6, 0.85, "NEO_Window")
        k.quad((cx, front - 0.01, 1.6), w - 1.6, 2.4, "NEO_Building")
        for d in range(int((w - 2.0) / 1.4)):   # shop window panes, dimmer than signs
            k.quad((x + 1.4 + d * 1.4, front - 0.02, 1.7), 1.1, 1.6, "NEO_Window")
        neon_mat = "NEO_Magenta" if bi % 2 == 0 else "NEO_Cyan"
        k.box((cx, front - 0.08, 3.1), (w - 1.0, 0.08, 0.1), neon_mat)
        k.box((cx, front - 0.6, 3.0), (w - 1.0, 1.2, 0.12), "NEO_Metal")  # awning
        if bi % 3 == 1:  # vertical sign blade
            k.box((x + 0.8, front - 0.9, 9), (0.25, 1.4, 7.0), "NEO_Building")
            k.box((x + 0.8, front - 1.62, 9), (0.18, 0.04, 6.6), neon_mat)
        x += w
        bi += 1
    # Overhead cables, street lamps, vents, crates, a parked hover-bike shape.
    for xx in (-15, -5, 5, 15):
        k.cyl((xx, 8.4, 3.0), 0.09, 6.0, "NEO_Metal", segs=8)
        k.box((xx, 7.7, 5.95), (0.18, 1.5, 0.12), "NEO_Metal")
        k.box((xx, 7.05, 5.85), (0.4, 0.4, 0.06), "NEO_Cyan")
    for i in range(6):
        k.box((rnd.uniform(-30, 30), 6, 9 + i * 0.6), (60, 0.03, 0.03), "NEO_Metal", rot=(0, rnd.uniform(-2, 2), 0))
    for vx in (-10.5, 11.0):
        k.box((vx, 9.0, 0.15), (1.2, 1.2, 0.3), "NEO_Metal")
        for g in range(5):
            k.box((vx, 8.6 + g * 0.2, 0.31), (1.0, 0.06, 0.02), "NEO_Building")
    for cx, cy in ((-13, 10.5), (-12.3, 11.0), (13.5, 10.8)):
        k.box((cx, cy, 0.6), (1.0, 1.0, 1.0), "NEO_Concrete", rot=(0, 0, rnd.uniform(-20, 20)), bevel=0.04)
        k.box((cx, cy, 1.205), (1.02, 1.02, 0.03), "NEO_Magenta")
    # Distant skyline.
    for i in range(26):
        h = rnd.uniform(30, 80)
        sx = -90 + i * 7.2
        k.box((sx, 60 + rnd.uniform(0, 20), h / 2), (rnd.uniform(4, 7), 6, h), "NEO_Building")
        k.box((sx, 56.9, h - 1), (2.0, 0.1, 0.3), "NEO_Magenta" if i % 2 else "NEO_Cyan")
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
