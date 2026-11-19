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
import kairo_v3  # noqa: E402
import kairo_v4  # noqa: E402

# "game" keeps the mobile triangle budget; "concept" is the dense version used
# for presentation renders (finer voxels, more triangles, same forms).
QUALITY = dict(voxel=1.0, tris=1.0)
# --bake: high-detail sculpt -> baked normal / colour / AO textures (Kairo v5)
BAKE = dict(on=False, size=2048, samples=24, voxel_scale=0.5, blend=None)

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
        self.brushes = []   # sculpt strokes applied to the dense surface

    # ------------------------------------------------------------ sculpt --
    def crease(self, a, b, r, depth, head=False):
        """Sculpt stroke from a to b: pushes the surface in by `depth` within
        radius r (negative depth raises a ridge). Applied after the forms are
        fused, so it can cut grooves a union of forms cannot: muscle
        separations, the mouth line, seams, folds."""
        self.brushes.append(dict(a=Vector(a), b=Vector(b), r=r, d=depth, head=head))

    def dent(self, c, r, depth, head=False):
        self.brushes.append(dict(a=Vector(c), b=Vector(c), r=r, d=depth, head=head))

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

    def limb(self, rings, bone, color, segs=24, sq=2.0):
        """Anatomical tube through any number of rings, so a limb can curve and
        bulge on one side only (calf at the back, quadriceps at the front).
        rings: [(centre, r_plus_u, r_minus_u, r_minus_w, r_plus_w)] where u is
        the world-X side of the path and w is world-Y (back), or world-Z (up)
        for a path that runs along Y (feet). `bone` is one name or one per band.
        sq > 2 squares the section off (rib cage, pelvis)."""
        cs = [Vector(r[0]) for r in rings]
        loops = []
        for i, r in enumerate(rings):
            axis = (cs[min(i + 1, len(cs) - 1)] - cs[max(i - 1, 0)]).normalized()
            u = Vector((1, 0, 0))
            u = (u - axis * u.dot(axis)).normalized()
            w = Vector((0, 1, 0)) if abs(axis.y) < 0.8 else Vector((0, 0, 1))
            w = (w - axis * w.dot(axis) - u * w.dot(u)).normalized()
            rup, run, rwn, rwp = r[1], r[2], r[3], r[4]
            loop = []
            for k in range(segs):
                a = 2 * math.pi * k / segs
                ca, sa = math.cos(a), math.sin(a)
                ex = 2.0 / sq
                cu = math.copysign(abs(ca) ** ex, ca) * (rup if ca >= 0 else run)
                cw = math.copysign(abs(sa) ** ex, sa) * (rwp if sa >= 0 else rwn)
                loop.append(self.bm.verts.new(cs[i] + u * cu + w * cw))
            loops.append(loop)
        names = bone if isinstance(bone, (list, tuple)) else [bone] * (len(rings) - 1)
        for i, (r0, r1) in enumerate(zip(loops, loops[1:])):
            band = [self.bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k])) for k in range(segs)]
            self._tag(band, names[i], color)
        self._tag([self.bm.faces.new(list(reversed(loops[0])))], names[0], color)
        self._tag([self.bm.faces.new(loops[-1])], names[-1], color)

    # ---------------------------------------------------------------- bake --
    def bake(self):
        """Returns dict(verts Nx3, tris Mx3, weights NxB, colors Nx3)."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.faces.ensure_lookup_table()
        src = bpy.data.meshes.new(self.name + "_src")
        self.bm.to_mesh(src)
        obj = bpy.data.objects.new(self.name + "_src", src)
        bpy.context.scene.collection.objects.link(obj)
        q = QUALITY
        if self.voxel > 0:
            m = obj.modifiers.new("remesh", "REMESH")
            m.mode = "VOXEL"
            m.voxel_size = self.voxel * q["voxel"]
            m.adaptivity = 0.0
            if self.smooth > 0:
                sm = obj.modifiers.new("smooth", "SMOOTH")
                sm.factor = 0.5
                sm.iterations = int(round(self.smooth / q["voxel"]))
            dg = bpy.context.evaluated_depsgraph_get()
            dense = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
            if self.brushes:
                nd = len(dense.vertices)
                co = np.zeros(nd * 3)
                nr = np.zeros(nd * 3)
                dense.vertices.foreach_get("co", co)
                dense.vertices.foreach_get("normal", nr)
                co, nr = co.reshape(nd, 3), nr.reshape(nd, 3)
                for br in self.brushes:
                    a_, b_ = np.array(br["a"]), np.array(br["b"])
                    ab = b_ - a_
                    L2 = float(ab @ ab)
                    t = np.clip(((co - a_) @ ab) / L2, 0, 1) if L2 > 1e-12 else np.zeros(nd)
                    dist = np.linalg.norm(co - (a_ + t[:, None] * ab), axis=1)
                    w = np.clip(1.0 - (dist / br["r"]) ** 2, 0, 1) ** 2
                    co -= nr * (br["d"] * w)[:, None]
                dense.vertices.foreach_set("co", co.ravel())
                dense.update()
            bpy.data.objects.remove(obj)
            obj = bpy.data.objects.new(self.name + "_dense", dense)
            bpy.context.scene.collection.objects.link(obj)
            n_tris = sum(len(p.vertices) - 2 for p in dense.polygons)
            target = self.tris * q["tris"]
            if n_tris > target:
                d = obj.modifiers.new("decimate", "DECIMATE")
                d.ratio = target / n_tris
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


# ----------------------------------------------- Kairo (approved art sheet) --
def kairo_v2_shells(B, bones):
    """Kairo as drawn on docs/art/reference_roster_sheet.png: heroic muscular
    build, fitted black sleeveless top with a red Origin line, bare upper
    arms, black forearm guards and gloves, belt with pouches, torn red sash at
    his right hip, black trousers with knee guards, armoured boots, short
    spiky black hair with a red streak."""
    P = {n: (Vector(h), Vector(t)) for n, (h, t, _p, _c) in B.items()}
    SKIN, SKIN_D, LIP = (0.52, 0.31, 0.2), (0.4, 0.22, 0.14), (0.3, 0.11, 0.09)
    TOP, TOP_L = (0.04, 0.042, 0.055), (0.1, 0.104, 0.13)
    PANTS, GUARD, BOOT = (0.034, 0.036, 0.048), (0.16, 0.168, 0.2), (0.055, 0.056, 0.07)
    SASH, SASH_D = (0.5, 0.02, 0.018), (0.3, 0.012, 0.012)
    HAIR, STREAK = (0.035, 0.03, 0.035), (0.6, 0.04, 0.03)
    shells = []

    def S(name, slot, **kw):
        s = Shell(name, slot, bones, **kw)
        shells.append(s)
        return s

    # ------------------------------------------------------------ body ----
    b = S("body", "Skin", voxel=0.0042, smooth=6, tris=12500, weight_blur=7, cavity=1.25)
    b.ell((0, 0.012, 1.705), (0.078, 0.094, 0.088), "Head", SKIN)                 # cranium
    b.ell((0, -0.026, 1.652), (0.07, 0.072, 0.074), "Head", SKIN)                 # face mass
    b.ell((0, -0.056, 1.585), (0.03, 0.026, 0.02), "Head", SKIN)                  # chin
    b.ell((0, -0.036, 1.608), (0.05, 0.04, 0.028), "Head", SKIN)                  # jaw
    b.ell((0, -0.071, 1.7), (0.06, 0.018, 0.012), "Head", SKIN)                   # brow
    b.ell((0, -0.078, 1.617), (0.024, 0.008, 0.0042), "Head", LIP)
    b.ell((0, -0.0765, 1.6085), (0.02, 0.009, 0.0052), "Head", LIP)
    b.loft((0, -0.079, 1.69), (0, -0.103, 1.649), [(0, 0.006, 0.008), (0.6, 0.0075, 0.009), (1, 0.01, 0.0105)], "Head", SKIN, segs=12)
    b.ell((0, -0.103, 1.646), (0.0105, 0.011, 0.0095), "Head", SKIN)
    for sx in (1, -1):
        b.ell((sx * 0.052, -0.046, 1.656), (0.022, 0.026, 0.02), "Head", SKIN)    # cheekbone
        b.ell((sx * 0.0115, -0.094, 1.642), (0.008, 0.0085, 0.007), "Head", SKIN)
        b.ell((sx * 0.08, 0.008, 1.66), (0.008, 0.019, 0.028), "Head", SKIN_D, rot=(0, sx * 12, sx * 18))
    # neck, traps, torso core
    b.loft((0, 0.014, 1.42), (0, -0.002, 1.615), [(0, 0.082, 0.072), (0.5, 0.07, 0.064), (1, 0.062, 0.062)], "Neck", SKIN)
    for sx in (1, -1):
        b.ell((sx * 0.1, 0.026, 1.478), (0.115, 0.066, 0.052), "Chest", SKIN, rot=(0, sx * -24, 0))    # trapezius
        b.loft((0, 0.0, 1.5), (sx * 0.035, -0.02, 1.61), [(0, 0.016, 0.02), (1, 0.012, 0.016)], "Neck", SKIN, segs=10)  # neck tendon
    b.loft((0, 0, 0.98), (0, 0, 1.3), [(0, 0.13, 0.09), (0.4, 0.125, 0.085), (1, 0.16, 0.1)], "Spine", SKIN)
    b.loft((0, 0, 1.26), (0, 0.004, 1.47), [(0, 0.16, 0.1), (0.5, 0.185, 0.105), (1, 0.14, 0.085)], "Chest", SKIN)
    for side, sx in (("Left", 1), ("Right", -1)):
        sh, el = P[f"{side}UpperArm"]
        wr, ht = P[f"{side}Hand"]
        ua, la, hd = f"{side}UpperArm", f"{side}LowerArm", f"{side}Hand"
        b.ell(sh + Vector((-sx * 0.002, 0, -0.012)), (0.078, 0.082, 0.092), ua, SKIN)                # deltoid
        b.ell(sh + Vector((sx * 0.02, -0.02, -0.06)), (0.05, 0.05, 0.07), ua, SKIN)                  # front deltoid head
        b.loft(sh, el, [(0, 0.066, 0.068), (0.35, 0.068, 0.076), (0.7, 0.056, 0.062), (1, 0.048, 0.05)], ua, SKIN)
        b.ell(sh.lerp(el, 0.52) + Vector((0, -0.03, 0)), (0.048, 0.05, 0.092), ua, SKIN)             # biceps
        b.ell(sh.lerp(el, 0.45) + Vector((sx * 0.01, 0.036, 0)), (0.048, 0.046, 0.108), ua, SKIN)    # triceps
        b.ell(el, (0.044, 0.046, 0.046), la, SKIN)
        b.loft(el, wr, [(0, 0.05, 0.047), (0.25, 0.06, 0.054), (0.65, 0.044, 0.038), (1, 0.034, 0.028)], la, SKIN)
        b.ell(el.lerp(wr, 0.22) + Vector((sx * 0.016, -0.006, 0)), (0.036, 0.034, 0.075), la, SKIN)  # brachioradialis

    # ------------------------------------------------- fitted top ----------
    t = S("top", "Cloth2", voxel=0.0045, smooth=8, tris=6000, weight_blur=7, cavity=1.5)
    t.loft((0, 0, 1.0), (0, 0, 1.13), [(0, 0.158, 0.108), (1, 0.15, 0.104)], "Hips", TOP)
    t.loft((0, 0, 1.11), (0, 0, 1.3), [(0, 0.15, 0.104), (0.5, 0.165, 0.108), (1, 0.205, 0.124)], "Spine", TOP)
    t.loft((0, -0.005, 1.27), (0, 0.006, 1.53), [(0, 0.205, 0.124), (0.4, 0.228, 0.132), (0.72, 0.214, 0.116),
                                                (0.88, 0.1, 0.086), (1, 0.08, 0.074)], "Chest", TOP)
    for sx in (1, -1):
        t.ell((sx * 0.095, -0.07, 1.39), (0.1, 0.046, 0.06), "Chest", TOP, rot=(6, sx * 6, 0))  # pectoral slab
        t.ell((sx * 0.185, 0.03, 1.29), (0.05, 0.085, 0.13), "Chest", TOP)                           # latissimus
        t.ell((sx * 0.08, 0.095, 1.38), (0.08, 0.042, 0.09), "Chest", TOP)                           # shoulder blade
        t.ell((sx * 0.05, 0.1, 1.18), (0.04, 0.03, 0.12), "Spine", TOP)                              # spinal erector
        for k, zz in enumerate((1.25, 1.192, 1.134, 1.078)):                                         # abdominals
            t.ell((sx * 0.038, -0.094 + k * 0.002, zz), (0.035, 0.015, 0.025), "Spine", TOP)
        for k in range(3):                                                                           # serratus
            t.crease((sx * (0.175 - k * 0.012), -0.075, 1.262 - k * 0.04), (sx * (0.135 - k * 0.01), -0.1, 1.245 - k * 0.04), 0.008, 0.003)
    col = S("collar", "Cloth2", voxel=0.004, smooth=2, tris=700, weight_blur=2, cavity=1.2)
    col.loft((0, 0.01, 1.49), (0, 0.006, 1.53), [(0, 0.088, 0.08), (1, 0.078, 0.073)], "Neck", TOP_L, segs=24)
    line = S("origin_line", "Accent", voxel=0, tris=0, weight_blur=0)
    line.box((0.022, -0.139, 1.39), (0.012, 0.01, 0.2), "Chest", (1, 1, 1), rot=(4, 0, 0))
    line.box((0.03, -0.128, 1.2), (0.011, 0.01, 0.2), "Spine", (1, 1, 1), rot=(-6, 0, 0))
    line.box((0.062, -0.136, 1.44), (0.07, 0.008, 0.01), "Chest", (1, 1, 1), rot=(0, -28, 0))
    # layered shoulder guards
    sg = S("shoulder_guards", "Cloth2", voxel=0.0045, smooth=2, tris=1500, weight_blur=3, cavity=1.6)
    for side, sx in (("Left", 1), ("Right", -1)):
        sh = P[f"{side}UpperArm"][0]
        sg.ell(sh + Vector((sx * 0.012, 0, 0.03)), (0.088, 0.09, 0.05), f"{side}UpperArm", TOP_L, rot=(0, sx * 22, 0))
        sg.box(sh + Vector((sx * 0.062, 0, 0.0)), (0.02, 0.15, 0.07), f"{side}UpperArm", GUARD, rot=(0, sx * 28, 0))

    # ----------------------------------------- forearm guards + gloves ----
    g = S("gauntlets", "Cloth2", voxel=0.0042, smooth=3, tris=3200, weight_blur=4, cavity=1.8)
    gl = S("glove_lines", "Accent", voxel=0, tris=0, weight_blur=0)
    for side, sx in (("Left", 1), ("Right", -1)):
        el = P[f"{side}LowerArm"][0]
        wr, ht = P[f"{side}Hand"]
        la, hd = f"{side}LowerArm", f"{side}Hand"
        g.loft(el.lerp(wr, 0.3), wr, [(0, 0.062, 0.056), (0.4, 0.058, 0.05), (1, 0.04, 0.034)], la, GUARD)
        g.loft(el.lerp(wr, 0.3), el.lerp(wr, 0.38), [(0, 0.066, 0.06), (1, 0.066, 0.06)], la, TOP_L, segs=18)   # cuff
        g.ell(el.lerp(wr, 0.6) + Vector((sx * 0.03, 0, 0)), (0.022, 0.03, 0.09), la, TOP_L)                     # outer plate
        d = (ht - wr).normalized()
        pc = wr + d * 0.07
        g.ell(pc, (0.031, 0.05, 0.054), hd, TOP)                                                               # fist (gloved)
        g.ell(wr + d * 0.03, (0.03, 0.033, 0.033), hd, TOP)
        for k in range(4):
            off = Vector((0, -0.036 + k * 0.023, 0))
            g.ell(pc + d * 0.044 + off, (0.023, 0.0135, 0.016), hd, GUARD)                                     # knuckle guards
            g.ell(pc + d * 0.034 + off + Vector((-sx * 0.021, 0, 0)), (0.014, 0.0125, 0.026), hd, TOP)
        g.loft(pc + Vector((-sx * 0.012, -0.044, 0.014)), pc + d * 0.032 + Vector((-sx * 0.028, -0.034, 0)),
               [(0, 0.015, 0.015), (1, 0.011, 0.011)], hd, TOP, segs=10)
        gl.box(el.lerp(wr, 0.62) + Vector((sx * 0.052, 0, 0)), (0.006, 0.012, 0.13), la, (1, 1, 1))

    # ------------------------------------------------------- trousers ----
    p = S("trousers", "Cloth", voxel=0.005, smooth=6, tris=6000, weight_blur=7, cavity=1.5)
    p.loft((0, 0, 0.86), (0, 0, 1.06), [(0, 0.155, 0.112), (0.45, 0.176, 0.122), (1, 0.158, 0.11)], "Hips", PANTS)
    p.ell((0, 0.065, 0.95), (0.155, 0.08, 0.095), "Hips", PANTS)
    for side, sx in (("Left", 1), ("Right", -1)):
        hip, knee = P[f"{side}UpperLeg"]
        ankle = P[f"{side}Foot"][0]
        ul, ll = f"{side}UpperLeg", f"{side}LowerLeg"
        p.loft(hip + Vector((0, 0, 0.05)), knee, [(0, 0.11, 0.114), (0.3, 0.116, 0.124), (0.75, 0.086, 0.09), (1, 0.07, 0.074)], ul, PANTS)
        p.ell(hip.lerp(knee, 0.42) + Vector((sx * 0.012, -0.04, 0)), (0.066, 0.055, 0.16), ul, PANTS)   # quadriceps
        p.ell(hip.lerp(knee, 0.4) + Vector((0, 0.045, 0)), (0.06, 0.05, 0.15), ul, PANTS)              # hamstring
        p.loft(knee, ankle + Vector((0, 0.005, 0.22)), [(0, 0.07, 0.074), (0.35, 0.074, 0.082), (1, 0.062, 0.066)], ll, PANTS)
        p.ell(knee.lerp(ankle, 0.28) + Vector((0, 0.036, 0)), (0.056, 0.056, 0.11), ll, PANTS)          # calf
        for k, tt in enumerate((0.16, 0.27, 0.9)):
            c = hip.lerp(knee, tt)
            p.ell(c + Vector((sx * 0.02, -0.07 if k < 2 else 0.0, 0)), (0.075, 0.03, 0.012), ul, PANTS, rot=(0, sx * 25, 0))
    kn = S("knee_guards", "Cloth2", voxel=0.0045, smooth=2, tris=1300, weight_blur=2, cavity=1.6)
    for side, sx in (("Left", 1), ("Right", -1)):
        knee = P[f"{side}LowerLeg"][0]
        kn.ell(knee + Vector((0, -0.05, 0.0)), (0.052, 0.03, 0.07), f"{side}LowerLeg", GUARD)
        kn.box(knee + Vector((0, -0.074, 0.005)), (0.05, 0.016, 0.07), f"{side}LowerLeg", TOP_L)
        hip = P[f"{side}UpperLeg"][0]
        kn.loft(hip.lerp(knee, 0.45), hip.lerp(knee, 0.52), [(0, 0.104, 0.11), (1, 0.1, 0.106)], f"{side}UpperLeg", TOP_L, segs=20)  # thigh strap
    belt = S("belt", "Cloth2", voxel=0.0045, smooth=1, tris=1500, weight_blur=0, cavity=1.5)
    belt.loft((0, 0, 1.02), (0, 0, 1.075), [(0, 0.168, 0.12), (0.5, 0.172, 0.124), (1, 0.164, 0.116)], "Hips", TOP_L, segs=28)
    for x, y in ((0.172, 0.0), (0.1, 0.105), (-0.1, 0.105)):                                              # pouches
        belt.ell((x, y, 1.005), (0.036, 0.03, 0.045), "Hips", GUARD)
    buckle = S("buckle", "Accent", voxel=0, tris=0, weight_blur=0)
    buckle.box((0, -0.127, 1.047), (0.05, 0.012, 0.04), "Hips", (1, 1, 1))

    # ------------------------------------------------- torn red sash ------
    sa = S("sash", "Cloth", voxel=0.0045, smooth=3, tris=2400, weight_blur=6, cavity=2.2)
    # Draped from the belt over the front of his right thigh, torn at the knee.
    pts = [((-0.1, -0.128, 1.03), 0.075, "Hips"), ((-0.135, -0.138, 0.9), 0.095, "Hips"), ((-0.16, -0.135, 0.76), 0.105, "RightUpperLeg"),
           ((-0.18, -0.125, 0.62), 0.1, "RightUpperLeg"), ((-0.195, -0.115, 0.5), 0.08, "RightUpperLeg")]
    for (a, wa, bn), (c2, wb, _b) in zip(pts, pts[1:]):
        sa.loft(a, c2, [(0, wa, 0.013), (1, wb, 0.013)], bn, SASH, segs=14)
    for dx, ln, w0 in ((-0.06, 0.13, 0.03), (0.0, 0.2, 0.034), (0.06, 0.11, 0.028)):                   # torn tails
        sa.loft((-0.195 + dx, -0.115, 0.52), (-0.21 + dx, -0.11, 0.52 - ln), [(0, w0, 0.011), (1, 0.006, 0.004)], "RightUpperLeg", SASH_D, segs=10)
    for dx in (-0.045, 0.01, 0.055):                                                                 # hanging folds
        sa.loft((-0.115 + dx, -0.146, 0.98), (-0.185 + dx, -0.132, 0.56), [(0, 0.012, 0.01), (0.5, 0.016, 0.012), (1, 0.01, 0.008)], "RightUpperLeg", SASH, segs=8)
    sa.loft((-0.13, 0.105, 1.03), (-0.19, 0.14, 0.68), [(0, 0.07, 0.012), (0.6, 0.08, 0.012), (1, 0.02, 0.005)], "Hips", SASH_D, segs=12)  # back tail

    # ----------------------------------------------------------- boots ----
    bt = S("boots", "Cloth2", voxel=0.0045, smooth=3, tris=3400, weight_blur=5, cavity=1.6)
    bl = S("boot_lines", "Accent", voxel=0, tris=0, weight_blur=0)
    for side, sx in (("Left", 1), ("Right", -1)):
        ankle = P[f"{side}Foot"][0]
        ll, ft = f"{side}LowerLeg", f"{side}Foot"
        bt.loft(ankle + Vector((0, 0.005, 0.24)), ankle + Vector((0, 0.005, -0.02)), [(0, 0.07, 0.074), (0.5, 0.06, 0.066), (1, 0.054, 0.062)], ll, BOOT)
        bt.ell(ankle + Vector((0, -0.05, 0.15)), (0.05, 0.03, 0.1), ll, GUARD)                         # shin plate
        bt.loft(ankle + Vector((0, 0.005, 0.24)), ankle + Vector((0, 0.005, 0.2)), [(0, 0.076, 0.08), (1, 0.074, 0.078)], ll, TOP_L, segs=18)
        x = ankle.x
        bt.ell((x, 0.014, 0.058), (0.05, 0.058, 0.058), ft, BOOT)
        bt.ell((x, -0.072, 0.054), (0.054, 0.105, 0.05), ft, BOOT)
        bt.ell((x, -0.152, 0.044), (0.056, 0.058, 0.042), ft, GUARD)                                   # armoured toe
        bt.box((x, -0.06, 0.015), (0.108, 0.29, 0.03), ft, (0.008, 0.008, 0.008))
        for zz in (0.1, 0.16):
            bt.ell((x, 0.005, 0.02 + zz), (0.066, 0.072, 0.013), ll, TOP_L)
        bl.box((x + sx * 0.058, 0.005, 0.19), (0.006, 0.012, 0.09), ll, (1, 1, 1))

    # ------------------------------------------------------------ hair ----
    h = S("hair", "Hair", voxel=0.0038, smooth=2, tris=3600, weight_blur=0, cavity=2.4)
    h.ell((0, 0.012, 1.738), (0.084, 0.102, 0.07), "Head", HAIR)
    h.ell((0, 0.062, 1.685), (0.077, 0.06, 0.07), "Head", HAIR)
    spikes = [  # base, tip, radius, colour — short, swept up and slightly forward
        ((0.012, -0.07, 1.765), (0.03, -0.125, 1.725), 0.026, STREAK), ((0.035, -0.055, 1.78), (0.065, -0.13, 1.815), 0.026, HAIR),
        ((-0.02, -0.07, 1.765), (-0.035, -0.118, 1.728), 0.024, HAIR), ((0.0, -0.05, 1.79), (0.01, -0.12, 1.84), 0.028, HAIR),
        ((-0.03, -0.055, 1.78), (-0.065, -0.125, 1.815), 0.028, HAIR), ((0.058, -0.03, 1.775), (0.105, -0.085, 1.815), 0.026, HAIR),
        ((-0.058, -0.03, 1.775), (-0.108, -0.075, 1.8), 0.026, HAIR), ((0.0, -0.01, 1.8), (0.02, -0.05, 1.885), 0.034, HAIR),
        ((0.04, 0.0, 1.795), (0.085, -0.01, 1.87), 0.03, HAIR), ((-0.04, 0.0, 1.795), (-0.085, 0.0, 1.865), 0.03, HAIR),
        ((0.0, 0.045, 1.795), (0.0, 0.08, 1.875), 0.032, HAIR), ((0.05, 0.05, 1.78), (0.1, 0.09, 1.84), 0.028, HAIR),
        ((-0.05, 0.05, 1.78), (-0.1, 0.095, 1.835), 0.028, HAIR), ((0.0, 0.095, 1.75), (0.0, 0.16, 1.785), 0.03, HAIR),
        ((0.045, 0.09, 1.73), (0.085, 0.145, 1.75), 0.026, HAIR), ((-0.045, 0.09, 1.73), (-0.085, 0.15, 1.745), 0.026, HAIR),
        ((0.07, 0.01, 1.76), (0.118, 0.03, 1.8), 0.024, HAIR), ((-0.07, 0.01, 1.76), (-0.118, 0.035, 1.795), 0.024, HAIR)]
    for a, tip, r, c in spikes:
        h.loft(a, tip, [(0, r, r * 0.8), (0.55, r * 0.62, r * 0.5), (1, 0.003, 0.003)], "Head", c, segs=10)
    for sx in (1, -1):
        h.ell((sx * 0.034, -0.087, 1.6985), (0.026, 0.008, 0.0058), "Head", HAIR, rot=(0, sx * -18, sx * 10))   # eyebrow
        h.ell((sx * 0.076, -0.01, 1.71), (0.007, 0.018, 0.026), "Head", HAIR)                                  # sideburn
    e = S("eyes", "Cloth2", voxel=0, tris=0, weight_blur=0)
    lids = S("lids", "Skin", voxel=0, tris=0, weight_blur=0)
    for sx in (1, -1):
        e.ell((sx * 0.03, -0.0715, 1.674), (0.0155, 0.0155, 0.0135), "Head", (0.8, 0.78, 0.74), segs=16, rings=12)
        e.ell((sx * 0.0295, -0.0835, 1.6735), (0.0082, 0.0045, 0.0082), "Head", (0.12, 0.05, 0.02), segs=14, rings=8)
        e.ell((sx * 0.0295, -0.0868, 1.6735), (0.0037, 0.0022, 0.0037), "Head", (0.0, 0.0, 0.0), segs=10, rings=6)
        lids.ell((sx * 0.03, -0.0725, 1.6865), (0.0185, 0.0165, 0.0062), "Head", SKIN_D, rot=(-8, sx * -8, 0), segs=16, rings=8)
    # ------------------------------------------------ sculpted detail ----
    H = dict(head=True)
    b.crease((-0.023, -0.088, 1.6128), (0.023, -0.088, 1.6128), 0.0042, 0.0034, **H)          # mouth line
    b.crease((-0.012, -0.086, 1.5975), (0.012, -0.086, 1.5975), 0.006, 0.0022, **H)           # under the lower lip
    b.crease((0, -0.098, 1.633), (0, -0.092, 1.622), 0.0035, 0.0014, **H)                     # philtrum
    for sx in (1, -1):
        b.dent((sx * 0.03, -0.09, 1.676), 0.021, 0.0075, **H)                                 # eye socket
        b.dent((sx * 0.0085, -0.104, 1.6365), 0.0048, 0.0036, **H)                            # nostril
        b.crease((sx * 0.017, -0.094, 1.642), (sx * 0.03, -0.082, 1.612), 0.005, 0.002, **H)  # nasolabial fold
        b.dent((sx * 0.06, -0.045, 1.628), 0.022, 0.0042, **H)                                # cheek hollow
        b.dent((sx * 0.068, -0.03, 1.69), 0.02, 0.003, **H)                                   # temple
        b.dent((sx * 0.09, 0.004, 1.664), 0.011, 0.0045, **H)                                 # ear bowl
        b.crease((sx * 0.02, -0.03, 1.56), (sx * 0.05, -0.012, 1.585), 0.008, 0.003, **H)     # jaw underside
    b.dent((0, -0.06, 1.468), 0.02, 0.006)                                                    # sternal notch
    for side, sx in (("Left", 1), ("Right", -1)):
        sh, el = P[f"{side}UpperArm"]
        wr = P[f"{side}Hand"][0]
        b.crease(sh + Vector((sx * 0.0, -0.06, -0.085)), sh.lerp(el, 0.42) + Vector((sx * 0.05, -0.025, 0)), 0.012, 0.0045)   # deltoid / biceps
        b.crease(sh + Vector((sx * 0.02, 0.06, -0.09)), sh.lerp(el, 0.4) + Vector((sx * 0.055, 0.02, 0)), 0.012, 0.004)       # deltoid / triceps
        b.crease(sh.lerp(el, 0.4) + Vector((sx * 0.062, 0.004, 0)), el + Vector((sx * 0.045, 0.004, 0.03)), 0.009, 0.0035)    # biceps / triceps
        b.crease(sh.lerp(el, 0.4) + Vector((-sx * 0.05, 0.0, 0)), el + Vector((-sx * 0.035, 0.0, 0.03)), 0.009, 0.003)        # inner arm
        b.dent(el + Vector((0, -0.04, 0.0)), 0.02, 0.004)                                                                     # elbow pit
        b.crease(el + Vector((sx * 0.02, -0.035, -0.04)), el.lerp(wr, 0.5) + Vector((sx * 0.005, -0.035, 0)), 0.008, 0.003)   # forearm flexors
    # torso through the fitted top
    t.crease((0, -0.14, 1.445), (0, -0.128, 1.3), 0.011, 0.005)                                # sternum
    t.crease((0, -0.124, 1.295), (0, -0.112, 1.05), 0.008, 0.0045)                             # linea alba
    t.crease((0, 0.125, 1.46), (0, 0.108, 1.06), 0.016, 0.007)                                 # spine
    for sx in (1, -1):
        t.crease((sx * 0.015, -0.13, 1.325), (sx * 0.1, -0.124, 1.312), 0.012, 0.0055)         # under the pectoral
        t.crease((sx * 0.1, -0.124, 1.312), (sx * 0.185, -0.08, 1.345), 0.012, 0.005)
        t.crease((sx * 0.185, -0.08, 1.345), (sx * 0.2, -0.04, 1.4), 0.011, 0.0045)            # pectoral / deltoid
        for zz in (1.222, 1.163, 1.106):
            t.crease((sx * 0.006, -0.118, zz), (sx * 0.078, -0.108, zz + 0.004), 0.0075, 0.004)   # abdominal rows
        t.crease((sx * 0.082, -0.108, 1.285), (sx * 0.092, -0.098, 1.06), 0.008, 0.004)        # rectus edge
        t.crease((sx * 0.13, -0.075, 1.07), (sx * 0.07, -0.105, 1.03), 0.008, 0.003)           # hip line
        t.crease((sx * 0.06, 0.12, 1.42), (sx * 0.15, 0.09, 1.3), 0.012, 0.004)                # shoulder blade
        t.crease((sx * 0.16, 0.07, 1.28), (sx * 0.1, 0.1, 1.12), 0.011, 0.0035)                # lat edge
        t.crease((sx * 0.212, 0.0, 1.33), (sx * 0.156, 0.0, 1.03), 0.0045, 0.002)              # side seam
    # trousers: seams and folds
    for side, sx in (("Left", 1), ("Right", -1)):
        hip, knee = P[f"{side}UpperLeg"]
        ankle = P[f"{side}Foot"][0]
        p.crease(hip + Vector((sx * 0.108, 0, 0.02)), knee + Vector((sx * 0.07, 0, 0)), 0.0045, 0.0022)       # outer seam
        p.crease(knee + Vector((sx * 0.07, 0, 0)), ankle + Vector((sx * 0.062, 0, 0.24)), 0.0045, 0.002)
        for dz, w in ((0.02, 0.07), (-0.02, 0.085), (-0.06, 0.06)):                                           # folds from the crotch
            p.crease((sx * 0.02, -0.105, 0.86 + dz), (sx * w, -0.115, 0.9 + dz * 0.5), 0.009, 0.004)
        p.crease(knee + Vector((-0.05, 0.065, 0.02)), knee + Vector((0.05, 0.065, 0.02)), 0.009, 0.005)       # behind the knee
        p.crease(knee + Vector((-0.045, 0.06, -0.03)), knee + Vector((0.045, 0.06, -0.03)), 0.008, 0.0035)
        p.crease(hip.lerp(knee, 0.2) + Vector((0, -0.11, 0)), hip.lerp(knee, 0.78) + Vector((0, -0.085, 0)), 0.014, 0.003)  # quadriceps split
    p.crease((0, -0.118, 1.02), (0, -0.105, 0.88), 0.005, 0.0025)                                             # fly
    # gloves: finger separations and a wrist line
    for side, sx in (("Left", 1), ("Right", -1)):
        wr, ht = P[f"{side}Hand"]
        d = (ht - wr).normalized()
        pc = wr + d * 0.07
        for yy in (-0.0245, -0.0015, 0.0215):
            g.crease(pc + d * 0.062 + Vector((sx * 0.01, yy, 0)), pc + d * 0.01 + Vector((-sx * 0.036, yy, 0)), 0.0042, 0.0034)
        g.crease(wr + Vector((sx * 0.04, 0, 0.005)), wr + Vector((-sx * 0.04, 0, 0.005)), 0.006, 0.003)
        g.crease(wr + Vector((0, -0.04, 0.005)), wr + Vector((0, 0.04, 0.005)), 0.006, 0.003)
    # sash: long folds
    for dx, dd in ((-0.03, 0.004), (0.02, 0.005), (0.06, 0.004)):
        sa.crease((-0.125 + dx, -0.152, 0.98), (-0.2 + dx, -0.13, 0.52), 0.011, dd)
    # boots: panel lines
    for side, sx in (("Left", 1), ("Right", -1)):
        x = P[f"{side}Foot"][0].x
        bt.crease((x - 0.06, -0.11, 0.07), (x + 0.06, -0.11, 0.07), 0.005, 0.003)                             # toe-cap seam
        bt.crease((x - 0.06, -0.02, 0.1), (x + 0.06, -0.02, 0.1), 0.005, 0.0025)                              # ankle flex
        bt.crease((x, -0.085, 0.24), (x, -0.07, 0.07), 0.004, 0.002)                                          # shin plate centre
    head, pivot, k = bones["Head"], Vector((0, 0, 1.59)), 1.08
    for sh_ in shells:
        for v in {v for f in sh_.bm.faces if f[sh_.f_bone] == head for v in f.verts}:
            v.co = pivot + (v.co - pivot) * k + Vector((0, 0, 0.004))
        for br in sh_.brushes:   # head strokes follow the head
            if br["head"]:
                br["a"] = pivot + (br["a"] - pivot) * k + Vector((0, 0, 0.004))
                br["b"] = pivot + (br["b"] - pivot) * k + Vector((0, 0, 0.004))
                br["r"] *= k
                br["d"] *= k
    return shells


class SdfShell:
    """Adapter: an sdf_sculpt.Layer baked like a Shell (Kairo v4+).
    Dense SDF surface -> hidden-skin culling -> decimate -> soft bone
    weights from the tagged forms -> vertex paint + cavity shading."""

    def __init__(self, layer, bones, cover=(), weight_blur=4, cavity=1.0):
        self.layer, self.bones, self.cover = layer, bones, cover
        self.slot, self.name = layer.slot, layer.name
        self.weight_blur, self.cavity = weight_blur, cavity
        self.bm = bmesh.new()   # empty: build()'s per-fighter rescale loop is a no-op

    def bake(self):
        L = self.layer
        V, F = L.polygonize(L.voxel * QUALITY["voxel"])
        if self.cover:
            # Drop skin that is buried under clothing: saves budget and stops
            # it poking through when joints bend.
            inside = np.zeros(len(V), dtype=bool)
            for c in self.cover:
                inside |= c.field(V) < -0.0015
            F = F[~inside[F].all(axis=1)]
            used = np.unique(F)
            remap = -np.ones(len(V), dtype=np.int64)
            remap[used] = np.arange(len(used))
            V, F = V[used], remap[F]
        me = bpy.data.meshes.new(L.name + "_dense")
        me.from_pydata(V.tolist(), [], F.tolist())
        obj = bpy.data.objects.new(L.name + "_dense", me)
        bpy.context.scene.collection.objects.link(obj)
        target = L.tris * QUALITY["tris"]
        if len(F) > target:
            d = obj.modifiers.new("decimate", "DECIMATE")
            d.ratio = target / len(F)
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
        weights, colors = L.attributes(verts, self.bones, tau=0.003)
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
        order = np.argsort(-weights, axis=1)
        mask = np.zeros_like(weights, dtype=bool)
        np.put_along_axis(mask, order[:, :4], True, axis=1)
        weights = np.where(mask & (weights > 0.03), weights, 0.0)
        weights /= weights.sum(axis=1, keepdims=True)
        if self.cavity > 0:
            lap = blur(verts, 1, keep=0.0) - verts
            conc = blur((lap * normals).sum(axis=1)[:, None], 2)[:, 0]
            shade = np.clip(1.0 - conc * 45.0 * self.cavity, 0.6, 1.1)
            colors = colors * shade[:, None]
        bpy.data.objects.remove(obj)
        print(f"[sdf] {L.name}: {len(tris)} tris", flush=True)
        return dict(verts=verts, tris=tris, weights=weights, colors=np.clip(colors, 0, 1), slot=self.slot,
                    smooth=True)


def kairo_v4_shells(B, bones):  # rejected SDF experiment (D-047 follow-up); not in HEROES
    layers = kairo_v4.all_layers(B)
    by = {L.name: L for L in layers}
    cover = [by[n] for n in ("Top", "Trousers", "Boots", "Gloves")]
    shells = []
    for L in layers:
        if L.name == "Body":
            shells.append(SdfShell(L, bones, cover=cover))
        elif L.name in ("Eyes", "Origin"):
            shells.append(SdfShell(L, bones, cavity=0.0))
        else:
            shells.append(SdfShell(L, bones))
    return shells


SENTINEL = dict(body=(0.1, 0.1, 0.12), plate=(0.3, 0.31, 0.35), under=(0.06, 0.065, 0.08), trim=(0.55, 0.56, 0.6))
WARDEN = dict(body=(0.05, 0.045, 0.045), plate=(0.12, 0.1, 0.09), under=(0.04, 0.035, 0.035), trim=(0.6, 0.44, 0.18))
HEROES = {"kairo": lambda B, bones: kairo_v3.shells(B, bones, Shell),
          "kairo_v3": lambda B, bones: kairo_v3.shells(B, bones, Shell),
          "kairo_v2": kairo_v2_shells,
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
    base = dict(cb.FIGHTERS["kairo"], shoulder=0.21) if fid != "kairo" else cb.FIGHTERS["kairo"]
    shells = HEROES[fid](cb.skeleton(base), bones)
    k = cfg["height"] / cb.REF_HEIGHT
    kx = cfg["shoulder"] / base["shoulder"]
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
    layer_ids = np.concatenate([np.full(len(p["tris"]), i) for i, p in enumerate(baked)])
    lay = mesh.attributes.new("layer", "INT", "FACE")
    lay.data.foreach_set("value", layer_ids.astype(np.int32))
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

    if BAKE["on"] and all(isinstance(s_, SdfShell) for s_ in shells):
        import hero_bake
        highs = [hero_bake.high_object(s_.layer, BAKE["voxel_scale"]) for s_ in shells]   # same order as layer ids
        prefix = f"{os.path.dirname(out_path)}/{fid}"
        albedo, normal = hero_bake.bake_maps(obj, highs, size=BAKE["size"], samples=BAKE["samples"],
                                             out_prefix=BAKE.get("tmp", "/tmp/") + fid)
        hero_bake.game_materials(obj, albedo, normal, cfg["palette"]["accent"])
        for o in highs:
            bpy.data.objects.remove(o)
        obj.data.color_attributes.remove(obj.data.color_attributes["Col"])

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
                              export_materials="EXPORT", export_vertex_color="NONE" if BAKE["on"] else "ACTIVE",
                              export_all_vertex_colors=False,
                              export_active_vertex_color_when_no_material=not BAKE["on"])
    if BAKE.get("blend"):
        bpy.ops.wm.save_as_mainfile(filepath=BAKE["blend"], compress=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--fighter", default="kairo")
    ap.add_argument("--moves", required=True)
    ap.add_argument("--out", default="assets/characters")
    ap.add_argument("--quality", default="game", choices=["game", "concept"])
    ap.add_argument("--bake", action="store_true", help="bake normal/colour/AO maps from a dense sculpt")
    ap.add_argument("--bake-size", type=int, default=2048)
    ap.add_argument("--bake-samples", type=int, default=24)
    ap.add_argument("--blend", default=None, help="also save the .blend source here")
    a = ap.parse_args(argv)
    BAKE.update(on=a.bake, size=a.bake_size, samples=a.bake_samples, blend=a.blend)
    if a.quality == "concept":
        QUALITY.update(voxel=0.62, tris=3.2)
    build(a.fighter, json.loads(open(a.moves).read()), f"{a.out}/{a.fighter}/{a.fighter}.glb")


if __name__ == "__main__":
    main()
