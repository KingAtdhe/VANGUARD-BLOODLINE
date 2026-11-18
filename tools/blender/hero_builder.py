"""Sculpt-style fighter builder (Milestone 7 quality pass) — FROM SCRATCH.

    python tools/blender/hero_builder.py --fighter kairo --moves /tmp/kairo_moves.json --out assets/characters

Replaces the "action figure" look of character_builder.py for the fighters
listed in HEROES. No base meshes or external assets. Pipeline per layer
("shell": body, top, trousers, boots, hair…):

  1. anatomy as overlapping closed forms (lofted limbs, muscle ellipsoids),
     each tagged with the bone it follows and a paint colour;
  2. voxel-remesh the forms into ONE continuous surface, smooth it so the
     forms blend like clay, decimate to the triangle budget;
  3. skin weights + colours are transferred from the nearest source form and
     smoothed over the surface, so joints bend without seams;
  4. cavity shading is baked into vertex colours.

Layers overlap like real clothing (hem over boot, top over torso). The rig,
conventions and data-timed animations are shared with character_builder.py.
"""

import argparse
import json
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import character_builder as cb  # noqa: E402  (shared rig + animation)

SLOTS = ["Skin", "Cloth", "Cloth2", "Accent", "Hair", "Gear"]
# Surface response per slot; colour comes from vertex paint (Accent excepted).
SLOT_PBR = {"Skin": (0.52, 0.0), "Cloth": (0.9, 0.0), "Cloth2": (0.45, 0.0), "Accent": (0.35, 0.0),
            "Hair": (0.42, 0.0), "Gear": (0.32, 0.85)}


def rot_matrix(rot):
    return (Matrix.Rotation(math.radians(rot[2]), 3, "Z") @ Matrix.Rotation(math.radians(rot[1]), 3, "Y")
            @ Matrix.Rotation(math.radians(rot[0]), 3, "X"))


class Shell:
    """One layer of the character, built from tagged closed forms."""

    def __init__(self, name, slot, bones, voxel=0.006, smooth=6, tris=4000, weight_blur=6, cavity=1.0):
        self.name, self.slot = name, slot
        self.bones = bones            # bone name -> index
        self.voxel, self.smooth, self.tris = voxel, smooth, tris
        self.weight_blur, self.cavity = weight_blur, cavity
        self.bm = bmesh.new()
        self.f_bone = self.bm.faces.layers.int.new("bone")
        self.f_col = self.bm.faces.layers.int.new("col")
        self.palette = []

    def _tag(self, faces, bone, color):
        if color not in self.palette:
            self.palette.append(color)
        ci = self.palette.index(color)
        for f in faces:
            f[self.f_bone] = self.bones[bone]
            f[self.f_col] = ci

    def ell(self, c, r, bone, color, rot=(0, 0, 0), segs=20, rings=12):
        ret = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=1.0)
        vs = ret["verts"]
        bmesh.ops.scale(self.bm, vec=r, verts=vs)
        bmesh.ops.rotate(self.bm, verts=vs, cent=(0, 0, 0), matrix=rot_matrix(rot))
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=vs)
        self._tag({f for v in vs for f in v.link_faces}, bone, color)

    def box(self, c, size, bone, color, rot=(0, 0, 0)):
        ret = bmesh.ops.create_cube(self.bm, size=1.0)
        vs = ret["verts"]
        bmesh.ops.scale(self.bm, vec=size, verts=vs)
        bmesh.ops.rotate(self.bm, verts=vs, cent=(0, 0, 0), matrix=rot_matrix(rot))
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=vs)
        self._tag({f for v in vs for f in v.link_faces}, bone, color)

    def loft(self, a, b, profile, bone, color, segs=20, shift=None):
        """Closed tube a→b. profile: [(t, lateral radius, depth radius)].
        shift: optional [(lateral, depth)] offset per ring (muscle bellies)."""
        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        ref = Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 1, 0))
        u = (ref - axis * ref.dot(axis)).normalized()
        w = axis.cross(u).normalized()
        rings = []
        for i, (t, rx, ry) in enumerate(profile):
            c = a.lerp(b, t)
            if shift:
                c += u * shift[i][0] + w * shift[i][1]
            rings.append([self.bm.verts.new(c + u * (math.cos(2 * math.pi * k / segs) * rx)
                                            + w * (math.sin(2 * math.pi * k / segs) * ry)) for k in range(segs)])
        faces = []
        for r0, r1 in zip(rings, rings[1:]):
            for k in range(segs):
                faces.append(self.bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k])))
        faces.append(self.bm.faces.new(list(reversed(rings[0]))))
        faces.append(self.bm.faces.new(rings[-1]))
        self._tag(faces, bone, color)

    # ---------------------------------------------------------------- bake --
    def bake(self):
        """Returns dict(verts Nx3, tris Mx3, weights NxB, colors Nx3)."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.faces.ensure_lookup_table()
        src = bpy.data.meshes.new(self.name + "_src")
        self.bm.to_mesh(src)
        obj = bpy.data.objects.new(self.name + "_src", src)
        bpy.context.scene.collection.objects.link(obj)
        if self.voxel > 0:
            m = obj.modifiers.new("remesh", "REMESH")
            m.mode = "VOXEL"
            m.voxel_size = self.voxel
            m.adaptivity = 0.0
            if self.smooth > 0:
                sm = obj.modifiers.new("smooth", "SMOOTH")
                sm.factor = 0.5
                sm.iterations = self.smooth
            dg = bpy.context.evaluated_depsgraph_get()
            n_tris = sum(len(p.vertices) - 2 for p in obj.evaluated_get(dg).data.polygons)
            if n_tris > self.tris:
                d = obj.modifiers.new("decimate", "DECIMATE")
                d.ratio = self.tris / n_tris
                d.use_collapse_triangulate = True
        tri = obj.modifiers.new("tri", "TRIANGULATE")
        tri.min_vertices = 4
        dg = bpy.context.evaluated_depsgraph_get()
        out = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
        n = len(out.vertices)
        verts = np.zeros(n * 3)
        out.vertices.foreach_get("co", verts)
        verts = verts.reshape(n, 3)
        tris = np.zeros(len(out.polygons) * 3, dtype=np.int64)
        out.polygons.foreach_get("vertices", tris)
        tris = tris.reshape(-1, 3)
        normals = np.zeros(n * 3)
        out.vertices.foreach_get("normal", normals)
        normals = normals.reshape(n, 3)

        # Nearest source form → bone + paint colour.
        bvh = BVHTree.FromBMesh(self.bm)
        weights = np.zeros((n, len(self.bones)))
        colors = np.zeros((n, 3))
        for i in range(n):
            _loc, _nrm, fi, _d = bvh.find_nearest(Vector(verts[i]))
            f = self.bm.faces[fi]
            weights[i, f[self.f_bone]] = 1.0
            colors[i] = self.palette[f[self.f_col]]
        edges = np.unique(np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1), axis=0)
        deg = np.zeros(n)
        np.add.at(deg, edges[:, 0], 1)
        np.add.at(deg, edges[:, 1], 1)
        deg = np.maximum(deg, 1)[:, None]

        def blur(a, iters, keep=0.5):
            for _ in range(iters):
                acc = np.zeros_like(a)
                np.add.at(acc, edges[:, 0], a[edges[:, 1]])
                np.add.at(acc, edges[:, 1], a[edges[:, 0]])
                a = keep * a + (1 - keep) * acc / deg
            return a

        weights = blur(weights, self.weight_blur)
        # Keep the 4 strongest influences (engine limit), renormalise.
        order = np.argsort(-weights, axis=1)
        mask = np.zeros_like(weights, dtype=bool)
        np.put_along_axis(mask, order[:, :4], True, axis=1)
        weights = np.where(mask & (weights > 0.02), weights, 0.0)
        weights /= weights.sum(axis=1, keepdims=True)
        colors = blur(colors, 1)
        # Cavity shading: concave areas darker, ridges slightly lighter.
        if self.cavity > 0 and self.voxel > 0:
            lap = blur(verts, 1, keep=0.0) - verts
            conc = blur((lap * normals).sum(axis=1)[:, None], 2)[:, 0]
            shade = np.clip(1.0 - conc * 55.0 * self.cavity, 0.55, 1.12)
            colors *= shade[:, None]
        bpy.data.objects.remove(obj)
        self.bm.free()
        return dict(verts=verts, tris=tris, weights=weights, colors=np.clip(colors, 0, 1), slot=self.slot,
                    smooth=self.voxel > 0)


# ------------------------------------------------------------------ Kairo --
def kairo_shells(B, bones, construct=None):
    """Kairo, or (construct = palette dict) a faceless Origin construct on the
    same frame: armoured body, smooth helmet with a glowing visor."""
    P = {n: (Vector(h), Vector(t)) for n, (h, t, _p, _c) in B.items()}
    SKIN = (0.50, 0.30, 0.20)
    SKIN_D = (0.40, 0.22, 0.15)
    LIP = (0.38, 0.17, 0.14)
    TOP = (0.045, 0.048, 0.06)
    PANTS = (0.028, 0.03, 0.04)
    RED = (0.62, 0.03, 0.025)
    BOOT = (0.035, 0.03, 0.03)
    HAIR = (0.018, 0.014, 0.014)
    human = construct is None
    if not human:
        SKIN = SKIN_D = LIP = construct["body"]
        TOP, PANTS, BOOT, RED = construct["plate"], construct["under"], construct["plate"], construct["trim"]
    shells = []

    def S(name, slot, **kw):
        s = Shell(name, slot, bones, **kw)
        shells.append(s)
        return s

    # ------------------------------------------------------------ body ----
    b = S("body", "Skin" if human else "Gear", voxel=0.0045, smooth=7, tris=11000 if human else 8000, weight_blur=7)
    # head
    b.ell((0, 0.012, 1.705), (0.078, 0.094, 0.088), "Head", SKIN)                # cranium
    b.ell((0, -0.026, 1.652), (0.069, 0.072, 0.074), "Head", SKIN)               # face mass
    if human:
        b.ell((0, -0.056, 1.584), (0.038, 0.03, 0.024), "Head", SKIN)                 # chin
        b.ell((0, -0.04, 1.607), (0.052, 0.042, 0.03), "Head", SKIN)                  # mouth mass / jaw
        b.ell((0, -0.071, 1.7), (0.06, 0.018, 0.012), "Head", SKIN)                  # brow ridge
        b.ell((0, -0.0805, 1.617), (0.024, 0.008, 0.0042), "Head", LIP)               # upper lip
        b.ell((0, -0.079, 1.6085), (0.02, 0.009, 0.0052), "Head", LIP)               # lower lip
        b.loft((0, -0.079, 1.69), (0, -0.103, 1.649), [(0, 0.006, 0.008), (0.6, 0.0075, 0.009), (1, 0.01, 0.0105)],
               "Head", SKIN, segs=12)                                                # nose bridge
        b.ell((0, -0.103, 1.646), (0.0105, 0.011, 0.0095), "Head", SKIN)            # nose tip
        for sx in (1, -1):
            b.ell((sx * 0.05, -0.048, 1.655), (0.022, 0.024, 0.02), "Head", SKIN)    # cheekbone
            b.ell((sx * 0.0115, -0.094, 1.642), (0.008, 0.0085, 0.007), "Head", SKIN)  # nostril wing
            b.ell((sx * 0.08, 0.008, 1.66), (0.008, 0.019, 0.028), "Head", SKIN_D, rot=(0, sx * 12, sx * 18))  # ear
    else:
        b.ell((0, -0.02, 1.66), (0.082, 0.092, 0.1), "Head", SKIN)                # helmet
    # neck, traps, torso core (the top covers most of it)
    b.loft((0, 0.012, 1.42), (0, -0.002, 1.615), [(0, 0.072, 0.066), (0.5, 0.064, 0.06), (1, 0.058, 0.06)], "Neck", SKIN)
    for sx in (1, -1):
        b.ell((sx * 0.082, 0.024, 1.49), (0.1, 0.06, 0.05), "Chest", SKIN, rot=(0, sx * -26, 0))  # trapezius
        b.loft((sx * 0.03, -0.035, 1.43), (sx * 0.19, -0.02, 1.445), [(0, 0.012, 0.012), (1, 0.014, 0.012)],
               "Chest", SKIN, segs=10)                                           # collarbone
    b.loft((0, 0, 0.98), (0, 0, 1.3), [(0, 0.135, 0.09), (0.4, 0.13, 0.085), (1, 0.15, 0.095)], "Spine", SKIN)
    b.loft((0, 0, 1.26), (0, 0.004, 1.47), [(0, 0.15, 0.095), (0.5, 0.17, 0.1), (1, 0.13, 0.08)], "Chest", SKIN)
    # arms
    for side, sx in (("Left", 1), ("Right", -1)):
        sh, el = P[f"{side}UpperArm"]
        wr, ht = P[f"{side}Hand"]
        ua, la, hd = f"{side}UpperArm", f"{side}LowerArm", f"{side}Hand"
        b.ell(sh + Vector((-sx * 0.004, 0, -0.008)), (0.066, 0.07, 0.08), ua, SKIN)                 # deltoid
        b.loft(sh, el, [(0, 0.06, 0.062), (0.35, 0.062, 0.068), (0.7, 0.052, 0.057), (1, 0.045, 0.047)], ua, SKIN)
        b.ell(sh.lerp(el, 0.5) + Vector((0, -0.022, 0)), (0.042, 0.046, 0.09), ua, SKIN)            # biceps
        b.ell(sh.lerp(el, 0.45) + Vector((sx * 0.006, 0.03, 0)), (0.042, 0.042, 0.1), ua, SKIN)   # triceps
        b.ell(el, (0.04, 0.042, 0.042), la, SKIN)                                                   # elbow
        b.loft(el, wr, [(0, 0.045, 0.043), (0.25, 0.053, 0.048), (0.65, 0.04, 0.035), (1, 0.031, 0.026)], la, SKIN)
        b.ell(el.lerp(wr, 0.25) + Vector((sx * 0.012, -0.005, 0)), (0.03, 0.03, 0.07), la, SKIN)    # forearm belly
        # clenched fist: palm, knuckle row, finger roll, thumb
        d = (ht - wr).normalized()
        pc = wr + d * 0.065
        b.ell(pc, (0.027, 0.046, 0.05), hd, SKIN)
        b.ell(wr + d * 0.03, (0.027, 0.03, 0.03), hd, SKIN)
        for k in range(4):
            off = Vector((0, -0.032 + k * 0.0205, 0))
            b.ell(pc + d * 0.04 + off * 1.1, (0.021, 0.012, 0.014), hd, SKIN)                            # knuckles
            b.ell(pc + d * 0.032 + off * 1.1 + Vector((-sx * 0.019, 0, 0)), (0.013, 0.0115, 0.024), hd, SKIN_D)  # curled fingers
        b.loft(pc + Vector((-sx * 0.01, -0.04, 0.012)), pc + d * 0.03 + Vector((-sx * 0.026, -0.03, 0)),
               [(0, 0.013, 0.013), (1, 0.01, 0.01)], hd, SKIN, segs=10)                             # thumb

    # ------------------------------------------------------------- top ----
    t = S("top", "Cloth2", voxel=0.005, smooth=9, tris=4200, weight_blur=7, cavity=0.8)
    t.loft((0, 0, 1.0), (0, 0, 1.13), [(0, 0.158, 0.106), (1, 0.152, 0.103)], "Hips", TOP)
    t.loft((0, 0, 1.11), (0, 0, 1.3), [(0, 0.152, 0.103), (0.5, 0.16, 0.106), (1, 0.186, 0.12)], "Spine", TOP)
    t.loft((0, -0.005, 1.27), (0, 0.006, 1.525), [(0, 0.186, 0.12), (0.4, 0.206, 0.128), (0.72, 0.196, 0.114),
                                                (0.88, 0.09, 0.08), (1, 0.074, 0.07)], "Chest", TOP)
    for sx in (1, -1):
        t.ell((sx * 0.08, -0.078, 1.385), (0.085, 0.04, 0.05), "Chest", TOP, rot=(0, sx * 6, 0))   # pectoral (subtle)
        t.ell((sx * 0.155, 0.035, 1.27), (0.045, 0.075, 0.11), "Chest", TOP)                        # lat
        t.ell((sx * 0.07, 0.085, 1.37), (0.07, 0.04, 0.085), "Chest", TOP)                          # shoulder blade
        for k, zz in enumerate((1.245, 1.19, 1.135)):                                               # abdominals
            t.ell((sx * 0.036, -0.094 + k * 0.002, zz), (0.034, 0.013, 0.026), "Spine", TOP)
    em = S("emblem", "Accent", voxel=0, tris=0, weight_blur=0)   # Origin mark on the chest
    for sx in (1, -1):   # chevron
        em.box((sx * 0.02, -0.127, 1.4), (0.05, 0.006, 0.012), "Chest", (1, 1, 1), rot=(0, sx * 35, 0))

    # -------------------------------------------------------- trousers ----
    p = S("trousers", "Cloth", voxel=0.0055, smooth=6, tris=5200, weight_blur=7, cavity=1.4)
    p.loft((0, 0, 0.86), (0, 0, 1.06), [(0, 0.15, 0.11), (0.45, 0.172, 0.118), (1, 0.158, 0.108)], "Hips", PANTS)
    p.ell((0, 0.06, 0.95), (0.15, 0.075, 0.09), "Hips", PANTS)                                     # seat
    for side, sx in (("Left", 1), ("Right", -1)):
        hip, knee = P[f"{side}UpperLeg"]
        ankle = P[f"{side}Foot"][0]
        ul, ll = f"{side}UpperLeg", f"{side}LowerLeg"
        p.loft(hip + Vector((0, 0, 0.05)), knee, [(0, 0.102, 0.106), (0.3, 0.106, 0.112), (0.75, 0.08, 0.084),
                                                  (1, 0.066, 0.07)], ul, PANTS)
        p.ell(hip.lerp(knee, 0.4) + Vector((0, -0.03, 0)), (0.06, 0.05, 0.14), ul, PANTS)           # quadriceps
        p.ell(knee + Vector((0, -0.02, 0)), (0.058, 0.056, 0.06), ll, PANTS)                        # knee
        p.loft(knee, ankle + Vector((0, 0.005, 0.2)), [(0, 0.066, 0.07), (0.35, 0.068, 0.074), (1, 0.06, 0.064)], ll, PANTS)
        p.ell(knee.lerp(ankle, 0.3) + Vector((0, 0.03, 0)), (0.05, 0.05, 0.1), ll, PANTS)           # calf
        for k, tt in enumerate((0.18, 0.3, 0.86)):                                                  # cloth folds
            c = hip.lerp(knee, tt)
            p.ell(c + Vector((sx * 0.02, -0.06 if k < 2 else 0.0, 0)), (0.07, 0.03, 0.012), ul, PANTS, rot=(0, sx * 25, 0))
        p.ell(ankle + Vector((0, 0, 0.215)), (0.07, 0.074, 0.022), ll, PANTS)                       # bloused hem
    belt = S("belt", "Gear", voxel=0, tris=0, weight_blur=0)
    belt.loft((0, 0, 1.025), (0, 0, 1.07), [(0, 0.167, 0.117), (0.5, 0.17, 0.12), (1, 0.164, 0.114)], "Hips",
              (0.05, 0.045, 0.04), segs=28)
    buckle = S("buckle", "Accent", voxel=0, tris=0, weight_blur=0)
    buckle.box((0, -0.121, 1.047), (0.06, 0.012, 0.042), "Hips", (1, 1, 1))

    # ----------------------------------------------------------- boots ----
    bt = S("boots", "Cloth2", voxel=0.005, smooth=4, tris=2600, weight_blur=5, cavity=1.2)
    for side, sx in (("Left", 1), ("Right", -1)):
        knee = P[f"{side}LowerLeg"][0]
        ankle = P[f"{side}Foot"][0]
        ll, ft = f"{side}LowerLeg", f"{side}Foot"
        bt.loft(ankle + Vector((0, 0.005, 0.2)), ankle + Vector((0, 0.005, -0.02)),
                [(0, 0.062, 0.066), (0.5, 0.055, 0.06), (1, 0.05, 0.058)], ll, BOOT)
        x = ankle.x
        bt.ell((x, 0.012, 0.055), (0.047, 0.055, 0.055), ft, BOOT)                                  # heel
        bt.ell((x, -0.07, 0.05), (0.05, 0.1, 0.045), ft, BOOT)                                      # instep
        bt.ell((x, -0.145, 0.04), (0.052, 0.055, 0.038), ft, BOOT)                                  # toe cap
        bt.box((x, -0.058, 0.014), (0.1, 0.275, 0.028), ft, (0.012, 0.012, 0.012))                  # sole
        for zz in (0.13, 0.2):
            bt.ell((x, 0.005, 0.09 + zz), (0.066, 0.07, 0.012), ll, (0.02, 0.018, 0.018))           # straps

    # ---------------------------------------------- wraps and headband ----
    w = S("wraps", "Cloth", voxel=0.0045, smooth=2, tris=1800, weight_blur=4, cavity=2.0)
    for side, sx in (("Left", 1), ("Right", -1)):
        el = P[f"{side}LowerArm"][0]
        wr, ht = P[f"{side}Hand"]
        la, hd = f"{side}LowerArm", f"{side}Hand"
        d = (wr - el).normalized()
        for k in range(7):                                                                          # overlapping bands
            c = el.lerp(wr, 0.5 + k * 0.085)
            r = 0.043 - k * 0.0019
            w.loft(c - d * 0.014, c + d * 0.014, [(0, r, r * 0.9), (0.5, r + 0.003, r * 0.9 + 0.003), (1, r, r * 0.9)],
                   la if k < 6 else hd, RED, segs=16)
        dh = (ht - wr).normalized()
        w.ell(wr + dh * 0.062, (0.027, 0.045, 0.036), hd, RED)                                      # palm wrap
    if human:
        hb = S("headband", "Cloth", voxel=0.004, smooth=2, tris=900, weight_blur=0, cavity=1.5)
        hb.loft((0, 0.012, 1.722), (0, 0.012, 1.752), [(0, 0.081, 0.098), (0.5, 0.083, 0.1), (1, 0.08, 0.097)], "Head", RED, segs=28)
        hb.ell((0.03, 0.112, 1.735), (0.016, 0.014, 0.018), "Head", RED)                                # knot
        hb.loft((0.03, 0.115, 1.735), (0.06, 0.2, 1.63), [(0, 0.016, 0.005), (1, 0.02, 0.004)], "Head", RED, segs=10)
        hb.loft((0.03, 0.115, 1.735), (-0.01, 0.19, 1.6), [(0, 0.016, 0.005), (1, 0.019, 0.004)], "Head", RED, segs=10)

        # ------------------------------------------------------------ hair ----
        h = S("hair", "Hair", voxel=0.004, smooth=2, tris=3200, weight_blur=0, cavity=2.2)
        h.ell((0, 0.022, 1.74), (0.082, 0.098, 0.068), "Head", HAIR)
        h.ell((0, 0.06, 1.68), (0.076, 0.06, 0.07), "Head", HAIR)                                       # back of head
        spikes = [((0, -0.05, 1.79), (0, -0.115, 1.865), 0.03), ((0.04, -0.04, 1.79), (0.07, -0.1, 1.86), 0.028),
                  ((-0.04, -0.04, 1.79), (-0.075, -0.095, 1.855), 0.028), ((0, 0.0, 1.8), (0.01, -0.02, 1.9), 0.034),
                  ((0.05, 0.0, 1.79), (0.105, 0.0, 1.875), 0.03), ((-0.05, 0.0, 1.79), (-0.1, 0.01, 1.87), 0.03),
                  ((0.02, 0.05, 1.79), (0.04, 0.09, 1.885), 0.032), ((-0.03, 0.05, 1.79), (-0.05, 0.1, 1.875), 0.03),
                  ((0.06, 0.06, 1.76), (0.12, 0.11, 1.82), 0.028), ((-0.06, 0.06, 1.76), (-0.115, 0.115, 1.815), 0.028),
                  ((0, 0.09, 1.75), (0, 0.17, 1.8), 0.032), ((0.03, 0.1, 1.7), (0.05, 0.165, 1.71), 0.028),
                  ((-0.03, 0.1, 1.7), (-0.055, 0.16, 1.7), 0.028), ((0.065, -0.03, 1.77), (0.115, -0.06, 1.825), 0.024),
                  ((-0.065, -0.03, 1.77), (-0.115, -0.055, 1.82), 0.024)]
        for a, tip, r in spikes:
            h.loft(a, tip, [(0, r, r * 0.8), (0.55, r * 0.6, r * 0.5), (1, 0.003, 0.003)], "Head", HAIR, segs=10)
        for sx in (1, -1):
            h.ell((sx * 0.033, -0.08, 1.7015), (0.022, 0.007, 0.0048), "Head", HAIR, rot=(0, sx * -12, sx * 12))  # eyebrow

        # ------------------------------------------------------------ eyes ----
        e = S("eyes", "Cloth2", voxel=0, tris=0, weight_blur=0)
        for sx in (1, -1):
            e.ell((sx * 0.03, -0.0715, 1.674), (0.0155, 0.0155, 0.0135), "Head", (0.8, 0.78, 0.74), segs=16, rings=12)
            e.ell((sx * 0.0295, -0.0835, 1.6735), (0.0082, 0.0045, 0.0082), "Head", (0.1, 0.05, 0.02), segs=14, rings=8)
            e.ell((sx * 0.0295, -0.0868, 1.6735), (0.0037, 0.0022, 0.0037), "Head", (0.0, 0.0, 0.0), segs=10, rings=6)
        lids = S("lids", "Skin", voxel=0, tris=0, weight_blur=0)
        for sx in (1, -1):
            lids.ell((sx * 0.03, -0.0725, 1.6835), (0.0185, 0.0165, 0.0075), "Head", SKIN_D, rot=(-12, 0, sx * -4), segs=16, rings=8)
            lids.ell((sx * 0.03, -0.072, 1.6635), (0.0175, 0.015, 0.0055), "Head", SKIN, segs=16, rings=8)
    else:
        v = S("visor", "Accent", voxel=0, tris=0, weight_blur=0)
        v.ell((0, -0.07, 1.672), (0.062, 0.03, 0.016), "Head", (1, 1, 1), segs=20, rings=8)
        ar = S("armor", "Gear", voxel=0.005, smooth=3, tris=2600, weight_blur=3, cavity=1.6)
        for side, sx in (("Left", 1), ("Right", -1)):
            sh = P[f"{side}UpperArm"][0]
            knee = P[f"{side}LowerLeg"][0]
            ar.ell(sh + Vector((sx * 0.012, 0, 0.02)), (0.085, 0.085, 0.07), f"{side}UpperArm", construct["trim"])  # pauldron
            ar.ell(knee + Vector((0, -0.05, 0)), (0.05, 0.03, 0.06), f"{side}LowerLeg", construct["trim"])           # knee guard
        ar.ell((0, -0.1, 1.37), (0.15, 0.04, 0.085), "Chest", construct["trim"])                                     # chest plate
        ar.ell((0, 0.02, 1.76), (0.012, 0.09, 0.03), "Head", construct["trim"])                                      # helmet crest
    # Slightly larger head than anatomical: reads better at fight-camera size.
    head, pivot, k = bones["Head"], Vector((0, 0, 1.59)), 1.12
    for sh_ in shells:
        vs = {v for f in sh_.bm.faces if f[sh_.f_bone] == head for v in f.verts}
        for v in vs:
            v.co = pivot + (v.co - pivot) * k + Vector((0, 0, -0.022))
    return shells


SENTINEL = dict(body=(0.1, 0.1, 0.12), plate=(0.3, 0.31, 0.35), under=(0.06, 0.065, 0.08), trim=(0.55, 0.56, 0.6))
WARDEN = dict(body=(0.05, 0.045, 0.045), plate=(0.12, 0.1, 0.09), under=(0.04, 0.035, 0.035), trim=(0.6, 0.44, 0.18))
HEROES = {"kairo": kairo_shells,
          "sentinel": lambda B, bones: kairo_shells(B, bones, SENTINEL),
          "warden": lambda B, bones: kairo_shells(B, bones, WARDEN)}


def build(fid, moves, out_path):
    cfg = cb.FIGHTERS[fid]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = cb.FPS
    B = cb.skeleton(cfg)
    bone_names = list(B.keys())
    bones = {n: i for i, n in enumerate(bone_names)}
    # Forms are authored on Kairo's frame, then scaled to this fighter's.
    shells = HEROES[fid](cb.skeleton(cb.FIGHTERS["kairo"]), bones)
    k = cfg["height"] / cb.REF_HEIGHT
    kx = cfg["shoulder"] / cb.FIGHTERS["kairo"]["shoulder"]
    for sh_ in shells:
        for v in sh_.bm.verts:
            v.co = Vector((v.co.x * kx, v.co.y * (k * kx) ** 0.5, v.co.z * k))
    baked = [s.bake() for s in shells]

    # Assemble one mesh.
    verts, tris, weights, colors, mat_idx, smooth = [], [], [], [], [], []
    base = 0
    for part in baked:
        verts.append(part["verts"])
        tris.append(part["tris"] + base)
        weights.append(part["weights"])
        colors.append(part["colors"])
        mat_idx.append(np.full(len(part["tris"]), SLOTS.index(part["slot"])))
        smooth.append(np.full(len(part["tris"]), part["smooth"]))
        base += len(part["verts"])
    verts, tris = np.concatenate(verts), np.concatenate(tris)
    weights, colors = np.concatenate(weights), np.concatenate(colors)
    mat_idx, smooth = np.concatenate(mat_idx), np.concatenate(smooth)
    mesh = bpy.data.meshes.new(f"{fid.upper()}_Mesh")
    mesh.from_pydata(verts.tolist(), [], tris.tolist())
    mesh.polygons.foreach_set("material_index", mat_idx.astype(np.int32))
    mesh.polygons.foreach_set("use_smooth", np.ones(len(tris), dtype=bool))
    col = mesh.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    loop_v = np.zeros(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", loop_v)
    rgba = np.ones((len(loop_v), 4))
    rgba[:, :3] = colors[loop_v]
    col.data.foreach_set("color", rgba.ravel())
    mesh.color_attributes.active_color = col
    mesh.update()
    for slot in SLOTS:
        m = bpy.data.materials.new(f"{fid.upper()}_{slot}")
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Roughness"].default_value, bsdf.inputs["Metallic"].default_value = SLOT_PBR[slot]
        if slot == "Accent":
            acc = cfg["palette"]["accent"]
            bsdf.inputs["Base Color"].default_value = (*acc, 1)
            bsdf.inputs["Emission Color"].default_value = (*acc, 1)
            bsdf.inputs["Emission Strength"].default_value = 3.0
        else:
            attr = m.node_tree.nodes.new("ShaderNodeVertexColor")
            attr.layer_name = "Col"
            m.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
        mesh.materials.append(m)

    arm_data = bpy.data.armatures.new(f"{fid.upper()}_Skeleton")
    arm_obj = bpy.data.objects.new(f"{fid.upper()}_Rig", arm_data)
    scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent, connect) in B.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail, eb.roll = head, tail, 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
            eb.use_connect = connect
    bpy.ops.object.mode_set(mode="OBJECT")
    obj = bpy.data.objects.new(f"{fid.upper()}_Body", mesh)
    scene.collection.objects.link(obj)
    groups = [obj.vertex_groups.new(name=n) for n in bone_names]
    nz = np.argwhere(weights > 0)
    for vi, bi in nz:
        groups[bi].add([int(vi)], float(weights[vi, bi]), "REPLACE")
    obj.parent = arm_obj
    obj.modifiers.new("Armature", "ARMATURE").object = arm_obj

    arm_obj.animation_data_create()
    targets = cb.setup_ik(arm_obj)
    actions = cb.build_actions(moves, cfg["height"] / cb.REF_HEIGHT, fid)
    for name, keys in actions.items():
        cb.key_action(arm_obj, targets, name, keys)
    for pb in arm_obj.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    for empty, _c in targets.values():
        bpy.data.objects.remove(empty)
    arm_obj.animation_data.action = bpy.data.actions[f"{fid.upper()}_IDLE_A"]
    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    print(f"[hero] {fid}: verts={len(verts)} tris={len(tris)} shells={len(baked)} actions={len(actions)}")
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_step=1,
                              export_skins=True, export_def_bones=False, export_yup=True, export_apply=False,
                              export_materials="EXPORT", export_vertex_color="ACTIVE", export_all_vertex_colors=False,
                              export_active_vertex_color_when_no_material=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--fighter", default="kairo")
    ap.add_argument("--moves", required=True)
    ap.add_argument("--out", default="assets/characters")
    a = ap.parse_args(argv)
    build(a.fighter, json.loads(open(a.moves).read()), f"{a.out}/{a.fighter}/{a.fighter}.glb")


if __name__ == "__main__":
    main()
