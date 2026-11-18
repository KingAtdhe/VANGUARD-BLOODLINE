"""Builds VANGUARD: BLOODLINE fighters FROM SCRATCH and exports GLB files.

    python tools/blender/character_builder.py --all --moves /tmp/kairo_moves.json --out assets/characters
    python tools/blender/character_builder.py --fighter kairo ...

No base meshes, scans or external assets: every shape is generated here from
lofted cross-sections, ellipsoids and bevelled boxes. One parametric body
(proportions, outfit pieces, hair, palette) per fighter, a shared humanoid
skeleton (Godot SkeletonProfileHumanoid names) and a shared, data-timed
animation set (attack poses placed by IK at the move hitboxes).

Stylized "action figure" construction: each body part is rigidly bound to
one bone (no joint deformation), with overlapping shapes hiding the seams.
Conventions: metres, faces -Y, Z up, origin between the feet, in-place
animation, 60 fps. See docs/BLENDER_PIPELINE.md and docs/ART_BIBLE.md.
"""

import argparse
import json
import math
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

FPS = 60
REF_HEIGHT = 1.8

# ---------------------------------------------------------------- fighters --
# Palettes: (r, g, b) linear-ish; accent is emissive Origin energy.
FIGHTERS = {
    "kairo": dict(
        display="Kairo", height=1.80, shoulder=0.21, hip=0.105, build=1.0,
        chest=(0.205, 0.125), waist=(0.155, 0.105), pelvis=(0.17, 0.11),
        arm=(0.058, 0.05), leg=(0.088, 0.062), head=0.105,
        palette=dict(skin=(0.56, 0.37, 0.27), cloth=(0.05, 0.055, 0.07), cloth2=(0.14, 0.15, 0.19),
                     accent=(1.0, 0.07, 0.05), hair=(0.025, 0.02, 0.02), gear=(0.06, 0.055, 0.06)),
        outfit=["fitted_top", "sleeveless_vest", "wraps", "belt", "headband", "pants", "boots", "chest_line"],
        hair="spiky"),
    "drakon": dict(
        display="Drakon", height=1.98, shoulder=0.27, hip=0.13, build=1.35,
        chest=(0.27, 0.17), waist=(0.21, 0.15), pelvis=(0.21, 0.14),
        arm=(0.082, 0.072), leg=(0.11, 0.08), head=0.11,
        palette=dict(skin=(0.42, 0.26, 0.18), cloth=(0.12, 0.08, 0.05), cloth2=(0.22, 0.2, 0.18),
                     accent=(1.0, 0.42, 0.05), hair=(0.03, 0.02, 0.015), gear=(0.18, 0.17, 0.16)),
        outfit=["armor_shoulders", "gauntlets", "chest_plate", "belt", "pants", "boots", "heavy_boots"],
        hair="buzz_beard"),
    "seraphina": dict(
        display="Seraphina", height=1.72, shoulder=0.18, hip=0.11, build=0.85,
        chest=(0.17, 0.11), waist=(0.13, 0.09), pelvis=(0.165, 0.105),
        arm=(0.046, 0.04), leg=(0.078, 0.055), head=0.1,
        palette=dict(skin=(0.75, 0.55, 0.45), cloth=(0.82, 0.86, 0.95), cloth2=(0.2, 0.28, 0.45),
                     accent=(0.35, 0.75, 1.0), hair=(0.85, 0.85, 0.92), gear=(0.55, 0.6, 0.7)),
        outfit=["fitted_top", "scarf", "tassets", "pants", "boots", "wraps"],
        hair="long_tail"),
    "nox": dict(
        display="Nox", height=1.70, shoulder=0.19, hip=0.1, build=0.9,
        chest=(0.18, 0.115), waist=(0.14, 0.095), pelvis=(0.155, 0.1),
        arm=(0.05, 0.043), leg=(0.08, 0.057), head=0.1,
        palette=dict(skin=(0.5, 0.38, 0.33), cloth=(0.04, 0.035, 0.06), cloth2=(0.12, 0.08, 0.18),
                     accent=(0.62, 0.2, 1.0), hair=(0.03, 0.02, 0.05), gear=(0.08, 0.07, 0.1)),
        outfit=["fitted_top", "hood", "mask", "wraps", "belt", "pants", "boots", "tassets"],
        hair="none"),
    "vexa": dict(
        display="Vexa", height=1.76, shoulder=0.195, hip=0.11, build=0.95,
        chest=(0.19, 0.12), waist=(0.14, 0.1), pelvis=(0.16, 0.105),
        arm=(0.052, 0.046), leg=(0.082, 0.058), head=0.1,
        palette=dict(skin=(0.7, 0.52, 0.42), cloth=(0.85, 0.85, 0.88), cloth2=(0.12, 0.12, 0.14),
                     accent=(1.0, 0.12, 0.15), hair=(0.6, 0.05, 0.06), gear=(0.35, 0.36, 0.4)),
        outfit=["fitted_top", "cyber_arm", "visor", "chest_plate", "belt", "pants", "boots"],
        hair="bob"),
    "ryuen": dict(
        display="Ryuen", height=1.78, shoulder=0.2, hip=0.11, build=1.0,
        chest=(0.2, 0.125), waist=(0.16, 0.11), pelvis=(0.17, 0.115),
        arm=(0.055, 0.048), leg=(0.085, 0.06), head=0.105,
        palette=dict(skin=(0.6, 0.45, 0.32), cloth=(0.55, 0.12, 0.08), cloth2=(0.88, 0.82, 0.7),
                     accent=(1.0, 0.75, 0.15), hair=(0.75, 0.75, 0.72), gear=(0.2, 0.15, 0.1)),
        outfit=["robe", "sash", "wraps", "pants", "sandals", "beard"],
        hair="topknot"),
    # Story/arcade opponent until the M8 roster is playable: an Ascendant
    # "Origin Sentinel" — a faceless trial construct (same frame as Kairo).
    "sentinel": dict(
        display="Origin Sentinel", height=1.82, shoulder=0.215, hip=0.11, build=1.05,
        chest=(0.21, 0.13), waist=(0.15, 0.105), pelvis=(0.17, 0.11),
        arm=(0.058, 0.05), leg=(0.088, 0.062), head=0.105,
        palette=dict(skin=(0.15, 0.15, 0.18), cloth=(0.22, 0.23, 0.27), cloth2=(0.6, 0.6, 0.65),
                     accent=(0.2, 0.9, 1.0), hair=(0.1, 0.1, 0.12), gear=(0.45, 0.46, 0.5)),
        outfit=["fitted_top", "chest_plate", "armor_shoulders", "visor", "faceless", "belt", "pants", "boots"],
        hair="none"),
    # Story/Arcade final boss: the Origin Warden, an elder Sentinel.
    "warden": dict(
        display="Origin Warden", height=1.96, shoulder=0.245, hip=0.12, build=1.25,
        chest=(0.25, 0.155), waist=(0.18, 0.13), pelvis=(0.19, 0.13),
        arm=(0.07, 0.062), leg=(0.1, 0.072), head=0.108,
        palette=dict(skin=(0.08, 0.07, 0.07), cloth=(0.1, 0.09, 0.09), cloth2=(0.55, 0.42, 0.2),
                     accent=(1.0, 0.72, 0.2), hair=(0.05, 0.04, 0.04), gear=(0.62, 0.48, 0.22)),
        outfit=["chest_plate", "armor_shoulders", "gauntlets", "faceless", "tassets", "belt", "pants",
                "heavy_boots", "scarf"],
        hair="none"),
}

MAT_SLOTS = ["Skin", "Cloth", "Cloth2", "Accent", "Hair", "Gear"]


def make_materials(fid, pal):
    mats = {}
    for slot in MAT_SLOTS:
        m = bpy.data.materials.new(f"{fid.upper()}_{slot}")
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        key = {"Skin": "skin", "Cloth": "cloth", "Cloth2": "cloth2", "Accent": "accent",
               "Hair": "hair", "Gear": "gear"}[slot]
        b.inputs["Base Color"].default_value = (*pal[key], 1.0)
        b.inputs["Roughness"].default_value = {"Skin": 0.55, "Cloth": 0.85, "Cloth2": 0.75,
                                               "Accent": 0.35, "Hair": 0.6, "Gear": 0.35}[slot]
        b.inputs["Metallic"].default_value = 0.6 if slot == "Gear" else 0.0
        if slot == "Accent":
            b.inputs["Emission Color"].default_value = (*pal["accent"], 1.0)
            b.inputs["Emission Strength"].default_value = 3.0
        mats[slot] = m
    return mats


# ---------------------------------------------------------------- skeleton --
def skeleton(cfg):
    s = cfg["height"] / REF_HEIGHT
    sh, hp = cfg["shoulder"], cfg["hip"]

    def v(x, y, z):
        return (x, y * s, z * s)

    bones = {
        "Root": (v(0, 0, 0), v(0, 0, 0.15), None, False),
        "Hips": (v(0, 0, 1.0), v(0, 0, 1.12), "Root", False),
        "Spine": (v(0, 0, 1.12), v(0, 0, 1.28), "Hips", True),
        "Chest": (v(0, 0, 1.28), v(0, 0, 1.45), "Spine", True),
        "Neck": (v(0, 0, 1.45), v(0, 0, 1.56), "Chest", True),
        "Head": (v(0, 0, 1.56), v(0, 0, 1.80), "Neck", True),
    }
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        bones.update({
            f"{side}UpperArm": (v(sh * sx, 0, 1.42), v((sh + 0.035) * sx, 0.04, 1.14), "Chest", False),
            f"{side}LowerArm": (v((sh + 0.035) * sx, 0.04, 1.14), v((sh + 0.05) * sx, -0.02, 0.88), f"{side}UpperArm", True),
            f"{side}Hand": (v((sh + 0.05) * sx, -0.02, 0.88), v((sh + 0.055) * sx, -0.04, 0.78), f"{side}LowerArm", True),
            f"{side}UpperLeg": (v(hp * sx, 0, 0.98), v((hp + 0.01) * sx, -0.04, 0.54), "Hips", False),
            f"{side}LowerLeg": (v((hp + 0.01) * sx, -0.04, 0.54), v((hp + 0.01) * sx, 0.0, 0.09), f"{side}UpperLeg", True),
            f"{side}Foot": (v((hp + 0.01) * sx, 0.0, 0.09), v((hp + 0.01) * sx, -0.16, 0.03), f"{side}LowerLeg", True),
        })
    return bones


# -------------------------------------------------------------------- mesh --
class Mesh:
    def __init__(self):
        self.bm = bmesh.new()
        self.deform = self.bm.verts.layers.deform.verify()
        self.groups = {}
        self.parts = 0

    def _bind(self, verts, bone, slot):
        gi = self.groups.setdefault(bone, len(self.groups))
        faces = set()
        for v in verts:
            v[self.deform][gi] = 1.0
            faces.update(v.link_faces)
        for f in faces:
            f.material_index = MAT_SLOTS.index(slot)
            f.smooth = True
        self.parts += 1

    @staticmethod
    def _frame(axis):
        axis = axis.normalized()
        ref = Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 1, 0))
        u = (ref - axis * ref.dot(axis)).normalized()   # lateral
        w = axis.cross(u).normalized()                     # depth
        return u, w

    def loft(self, a, b, profile, bone, slot, segs=16, offset=(0.0, 0.0), caps=True):
        """Lofted tube from a to b. profile: [(t, rx, ry), ...] with t in 0..1;
        rx is the lateral radius, ry the depth radius. offset shifts rings
        (lateral, depth) — e.g. to push a chest forward."""
        a, b = Vector(a), Vector(b)
        u, w = self._frame(b - a)
        rings = []
        for t, rx, ry in profile:
            c = a.lerp(b, t) + u * offset[0] + w * offset[1]
            ring = []
            for k in range(segs):
                ang = 2 * math.pi * k / segs
                ring.append(self.bm.verts.new(c + u * (math.cos(ang) * rx) + w * (math.sin(ang) * ry)))
            rings.append(ring)
        new = [v for r in rings for v in r]
        for r0, r1 in zip(rings, rings[1:]):
            for k in range(segs):
                self.bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
        if caps:
            for ring, rev in ((rings[0], True), (rings[-1], False)):
                c = sum((v.co for v in ring), Vector()) / len(ring)
                cv = self.bm.verts.new(c)
                new.append(cv)
                for k in range(segs):
                    q = (ring[(k + 1) % segs], ring[k], cv) if rev else (ring[k], ring[(k + 1) % segs], cv)
                    self.bm.faces.new(q)
        self._bind(new, bone, slot)

    def ellipsoid(self, c, r, bone, slot, segs=16, rings=10):
        ret = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=1.0)
        bmesh.ops.scale(self.bm, vec=r, verts=ret["verts"])
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=ret["verts"])
        self._bind(ret["verts"], bone, slot)

    def block(self, c, size, bone, slot, bevel=0.015, rot=(0, 0, 0)):
        ret = bmesh.ops.create_cube(self.bm, size=1.0)
        verts = ret["verts"]
        bmesh.ops.scale(self.bm, vec=size, verts=verts)
        edges = list({e for v in verts for e in v.link_edges})
        if bevel > 0:
            res = bmesh.ops.bevel(self.bm, geom=verts + edges, offset=bevel, segments=2,
                                  profile=0.5, affect="EDGES", clamp_overlap=True)
            verts = list({v for f in res["faces"] for v in f.verts} | set(v for v in verts if v.is_valid))
        mat = (Matrix.Rotation(math.radians(rot[2]), 3, "Z") @ Matrix.Rotation(math.radians(rot[1]), 3, "Y")
               @ Matrix.Rotation(math.radians(rot[0]), 3, "X"))
        verts = [v for v in verts if v.is_valid]
        bmesh.ops.rotate(self.bm, verts=verts, cent=(0, 0, 0), matrix=mat)
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=verts)
        self._bind(verts, bone, slot)

    def spike(self, base, tip, r, bone, slot):
        self.loft(base, tip, [(0, r, r * 0.8), (0.6, r * 0.55, r * 0.45), (1.0, 0.004, 0.004)], bone, slot, segs=7)


def build_body(cfg, B):
    """Generates the fighter's mesh around skeleton B (rest pose)."""
    m = Mesh()
    s = cfg["height"] / REF_HEIGHT
    k = cfg["build"]
    out = set(cfg["outfit"])
    P = {n: (Vector(h), Vector(t)) for n, (h, t, _p, _c) in B.items()}

    def z(v):
        return v * s

    # --- torso: pelvis, waist, chest as lofted sections ---------------------
    px, py = cfg["pelvis"]
    wx, wy = cfg["waist"]
    cx, cy = cfg["chest"]
    m.loft((0, 0, z(0.9)), (0, 0, z(1.12)), [(0, px * 0.9, py * 0.95), (0.35, px, py), (0.8, wx * 1.05, wy),
                                           (1, wx, wy * 0.98)], "Hips", "Cloth" if "pants" in out else "Skin", 18)
    top_slot = "Cloth2" if "fitted_top" in out else "Skin"
    if "robe" in out:
        top_slot = "Cloth"
    m.loft((0, 0, z(1.1)), (0, 0, z(1.3)), [(0, wx, wy), (0.5, wx * 1.04, wy * 1.02), (1, cx * 0.92, cy * 0.95)],
           "Spine", top_slot, 18)
    m.loft((0, 0, z(1.27)), (0, 0, z(1.5)), [(0, cx * 0.92, cy * 0.95), (0.35, cx, cy * 1.08), (0.75, cx * 1.02, cy),
                                            (1, cx * 0.62, cy * 0.7)], "Chest", top_slot, 18, offset=(0, -0.01))
    # neck + head
    nr = 0.05 * (1.15 if k > 1.2 else 1.0)
    m.loft(z(Vector((0, 0, 1.44))), z(Vector((0, 0, 1.6))), [(0, nr * 1.1, nr), (1, nr, nr * 0.95)], "Neck", "Skin", 12)
    hr = cfg["head"]
    hc = Vector((0, -0.005, z(1.665)))
    faceless = "faceless" in out
    m.ellipsoid(hc, (hr * 0.92, hr * 1.02, hr * 1.18), "Head", "Gear" if faceless else "Skin")
    if not faceless:
        m.ellipsoid(hc + Vector((0, -hr * 0.55, -hr * 0.62)), (hr * 0.62, hr * 0.5, hr * 0.42), "Head", "Skin", 12, 8)  # jaw
        m.ellipsoid(hc + Vector((0, -hr * 0.96, -hr * 0.12)), (hr * 0.13, hr * 0.15, hr * 0.22), "Head", "Skin", 8, 6)  # nose
        for sx in (1, -1):
            m.ellipsoid(hc + Vector((sx * hr * 0.92, 0.0, -hr * 0.05)), (hr * 0.1, hr * 0.17, hr * 0.24), "Head", "Skin", 8, 6)  # ears
            if "mask" not in out and "visor" not in out:
                m.ellipsoid(hc + Vector((sx * hr * 0.36, -hr * 0.84, hr * 0.12)), (hr * 0.2, hr * 0.07, hr * 0.12),
                            "Head", "Hair", 8, 6)  # eyes
            m.block(hc + Vector((sx * hr * 0.36, -hr * 0.88, hr * 0.3)), (hr * 0.38, hr * 0.12, hr * 0.08), "Head",
                    "Hair", bevel=0.004, rot=(0, -sx * 8, 0))  # brows
    # --- hair / head gear ------------------------------------------------------
    hair = cfg["hair"]
    top = hc + Vector((0, 0, hr * 0.9))
    if hair == "spiky":
        m.ellipsoid(hc + Vector((0, hr * 0.12, hr * 0.38)), (hr * 1.0, hr * 1.04, hr * 0.85), "Head", "Hair")
        for (dx, dy, dz, tx, ty, tz) in [(0, 0.0, 0.9, 0, 0.25, 1.65), (0.45, 0.1, 0.8, 0.85, 0.45, 1.35),
                                         (-0.45, 0.1, 0.8, -0.85, 0.45, 1.35), (0.0, 0.5, 0.65, 0.0, 1.35, 0.95),
                                         (0.3, -0.5, 0.85, 0.45, -0.95, 1.25), (-0.3, -0.5, 0.85, -0.4, -1.05, 1.15),
                                         (0.55, 0.45, 0.55, 1.05, 1.0, 0.8), (-0.55, 0.45, 0.55, -1.05, 1.0, 0.8)]:
            m.spike(hc + Vector((dx, dy, dz)) * hr, hc + Vector((tx, ty, tz)) * hr, hr * 0.32, "Head", "Hair")
    elif hair == "long_tail":
        m.ellipsoid(hc + Vector((0, hr * 0.1, hr * 0.32)), (hr * 1.02, hr * 1.06, hr * 0.9), "Head", "Hair")
        pts = [hc + Vector((0, hr * 0.85, hr * 0.5)), hc + Vector((0, hr * 1.45, -hr * 0.3)),
               hc + Vector((0, hr * 1.7, -hr * 1.8)), hc + Vector((0, hr * 1.85, -hr * 3.4))]
        for a, b2, r0, r1 in zip(pts, pts[1:], (0.3, 0.26, 0.2), (0.26, 0.2, 0.08)):
            m.loft(a, b2, [(0, hr * r0, hr * r0), (1, hr * r1, hr * r1)], "Head", "Hair", 10)
        for sx in (1, -1):
            m.loft(hc + Vector((sx * hr * 0.85, -hr * 0.4, hr * 0.4)), hc + Vector((sx * hr * 0.95, -hr * 0.55, -hr * 0.9)),
                   [(0, hr * 0.18, hr * 0.12), (1, hr * 0.08, hr * 0.06)], "Head", "Hair", 8)
    elif hair == "bob":
        m.ellipsoid(hc + Vector((0, hr * 0.12, hr * 0.1)), (hr * 1.12, hr * 1.12, hr * 1.08), "Head", "Hair")
        m.block(hc + Vector((0, -hr * 0.75, hr * 0.55)), (hr * 1.7, hr * 0.5, hr * 0.5), "Head", "Hair", bevel=0.02, rot=(-15, 0, 0))
    elif hair == "topknot":
        m.ellipsoid(hc + Vector((0, hr * 0.15, hr * 0.42)), (hr * 0.98, hr * 1.0, hr * 0.78), "Head", "Hair")
        m.ellipsoid(top + Vector((0, hr * 0.2, hr * 0.3)), (hr * 0.32, hr * 0.32, hr * 0.38), "Head", "Hair")
        m.loft(top + Vector((0, hr * 0.2, hr * 0.15)), top + Vector((0, hr * 0.2, hr * 0.3)),
               [(0, hr * 0.2, hr * 0.2), (1, hr * 0.2, hr * 0.2)], "Head", "Accent", 10)
    elif hair == "buzz_beard":
        m.ellipsoid(hc + Vector((0, hr * 0.12, hr * 0.32)), (hr * 0.97, hr * 1.02, hr * 0.82), "Head", "Hair")
    if "beard" in out or hair == "buzz_beard":
        m.ellipsoid(hc + Vector((0, -hr * 0.62, -hr * 0.78)), (hr * 0.6, hr * 0.45, hr * 0.5), "Head", "Hair", 12, 8)
    if "headband" in out:
        m.loft(hc + Vector((0, 0, hr * 0.5)), hc + Vector((0, 0, hr * 0.66)),
               [(0, hr * 0.99, hr * 1.05), (1, hr * 0.95, hr * 1.0)], "Head", "Accent", 18, caps=False)
        m.loft(hc + Vector((0, hr * 1.0, hr * 0.58)), hc + Vector((hr * 0.2, hr * 2.0, -hr * 0.3)),
               [(0, hr * 0.12, hr * 0.03), (1, hr * 0.1, hr * 0.02)], "Head", "Accent", 6)  # tail
    if "hood" in out:
        m.ellipsoid(hc + Vector((0, hr * 0.15, hr * 0.12)), (hr * 1.25, hr * 1.3, hr * 1.35), "Head", "Cloth")
        m.ellipsoid(hc + Vector((0, hr * 0.45, -hr * 0.9)), (hr * 1.3, hr * 1.1, hr * 0.7), "Chest", "Cloth")
    if "mask" in out:
        m.ellipsoid(hc + Vector((0, -hr * 0.45, -hr * 0.35)), (hr * 0.95, hr * 0.7, hr * 0.62), "Head", "Gear")
        for sx in (1, -1):
            m.ellipsoid(hc + Vector((sx * hr * 0.36, -hr * 0.9, hr * 0.12)), (hr * 0.2, hr * 0.06, hr * 0.06),
                        "Head", "Accent", 8, 6)
    if "visor" in out:
        m.loft(hc + Vector((0, 0, hr * 0.0)), hc + Vector((0, 0, hr * 0.28)),
               [(0, hr * 1.0, hr * 1.06), (1, hr * 0.98, hr * 1.04)], "Head", "Accent", 18, caps=False)
    if "faceless" in out:
        m.ellipsoid(hc + Vector((0, -hr * 0.78, hr * 0.1)), (hr * 0.55, hr * 0.32, hr * 0.12), "Head", "Accent", 12, 6)
    # --- torso outfit -----------------------------------------------------------
    if "chest_line" in out:
        m.loft((0, 0, z(1.355)), (0, 0, z(1.375)), [(0, cx * 1.02, cy * 1.1), (1, cx * 1.02, cy * 1.1)],
               "Chest", "Accent", 18, offset=(0, -0.01), caps=False)
    if "sleeveless_vest" in out:
        m.loft((0, 0, z(1.12)), (0, 0, z(1.47)), [(0, wx * 1.1, wy * 1.12), (0.55, cx * 1.06, cy * 1.14),
                                                (1, cx * 0.75, cy * 0.82)], "Chest", "Cloth", 18, offset=(0, 0.004))
    if "chest_plate" in out:
        m.block((0, -cy * 0.92, z(1.36)), (cx * 1.55, 0.05, 0.2 * s), "Chest", "Gear", bevel=0.02, rot=(8, 0, 0))
        m.block((0, -cy * 1.0, z(1.33)), (cx * 0.45, 0.03, 0.06), "Chest", "Accent", bevel=0.008)
    if "robe" in out:
        m.loft((0, 0, z(1.0)), (0, 0, z(1.49)), [(0, px * 1.15, py * 1.2), (0.3, wx * 1.18, wy * 1.2),
                                               (0.8, cx * 1.08, cy * 1.12), (1, cx * 0.7, cy * 0.8)], "Chest", "Cloth", 20)
        m.block((cx * 0.25, -cy * 1.12, z(1.3)), (0.06, 0.02, 0.36 * s), "Chest", "Cloth2", bevel=0.006, rot=(0, -25, 0))
        for side, sx in (("Left", 1), ("Right", -1)):  # front/back robe panels follow the legs
            hip = P[f"{side}UpperLeg"][0]
            knee = P[f"{side}LowerLeg"][0]
            m.block(hip.lerp(knee, 0.55) + Vector((0, -0.07, 0)), (0.17 * k, 0.03, (hip - knee).length * 0.95),
                    f"{side}UpperLeg", "Cloth", bevel=0.01)
            m.block(hip.lerp(knee, 0.55) + Vector((0, 0.07, 0)), (0.17 * k, 0.03, (hip - knee).length * 0.95),
                    f"{side}UpperLeg", "Cloth", bevel=0.01)
    if "sash" in out:
        m.loft((0, 0, z(1.05)), (0, 0, z(1.12)), [(0, wx * 1.25, wy * 1.3), (1, wx * 1.22, wy * 1.28)],
               "Hips", "Accent", 18, caps=False)
        m.block((wx * 0.6, -wy * 1.2, z(0.95)), (0.07, 0.02, 0.2), "Hips", "Accent", bevel=0.005, rot=(0, 10, 0))
    if "belt" in out:
        m.loft((0, 0, z(1.03)), (0, 0, z(1.08)), [(0, px * 1.06, py * 1.08), (1, px * 1.05, py * 1.07)],
               "Hips", "Gear", 18, caps=False)
        m.block((0, -py * 1.1, z(1.055)), (0.07, 0.02, 0.055), "Hips", "Accent", bevel=0.006)
    if "scarf" in out:
        m.loft(Vector((0, 0, z(1.46))), Vector((0, 0, z(1.56))), [(0, nr * 2.2, nr * 2.0), (1, nr * 1.9, nr * 1.8)],
               "Neck", "Accent", 14, caps=False)
        m.loft(Vector((0.03, nr * 1.6, z(1.5))), Vector((0.08, 0.32, z(1.18))),
               [(0, 0.06, 0.012), (1, 0.05, 0.008)], "Chest", "Accent", 6)
    if "tassets" in out:
        for sx in (1, -1):
            m.block((sx * px * 0.6, -0.02, z(0.88)), (0.15 * k, 0.17 * k, 0.17), "Hips", "Cloth2", bevel=0.012,
                    rot=(0, sx * 8, 0))
    # --- arms -------------------------------------------------------------------
    ua, fa = cfg["arm"]
    for side, sx in (("Left", 1), ("Right", -1)):
        sh_, el = P[f"{side}UpperArm"]
        wr, ht = P[f"{side}Hand"]
        cyber = "cyber_arm" in out and side == "Right"
        sleeve = "Cloth2" if ("fitted_top" in out and "sleeveless_vest" not in out) or "robe" in out else "Skin"
        if "robe" in out:
            sleeve = "Cloth"
        m.ellipsoid(sh_, (ua * 1.45, ua * 1.35, ua * 1.35), f"{side}UpperArm", "Gear" if cyber else sleeve)
        m.loft(sh_, el, [(0, ua * 1.2, ua * 1.15), (0.35, ua * 1.25, ua * 1.2), (0.85, ua * 0.95, ua * 0.9),
                         (1, ua * 0.85, ua * 0.82)], f"{side}UpperArm", "Gear" if cyber else sleeve, 14)
        m.ellipsoid(el, (fa * 1.05, fa * 1.05, fa * 1.05), f"{side}LowerArm", "Gear" if cyber else "Skin", 10, 6)
        fore_slot = "Gear" if cyber else ("Cloth" if "robe" in out else "Skin")
        m.loft(el, wr, [(0, fa * 1.1, fa * 1.0), (0.3, fa * 1.18, fa * 1.05), (1, fa * 0.78, fa * 0.68)],
               f"{side}LowerArm", fore_slot, 14)
        if cyber:
            for t in (0.3, 0.6):
                m.loft(el.lerp(wr, t), el.lerp(wr, t + 0.06), [(0, fa * 1.25, fa * 1.12), (1, fa * 1.25, fa * 1.12)],
                       f"{side}LowerArm", "Accent", 14, caps=False)
            m.block(sh_ + Vector((sx * 0.02, 0, 0.02)), (0.11, 0.13, 0.1), f"{side}UpperArm", "Gear", bevel=0.02)
        if "wraps" in out and not cyber:
            m.loft(el.lerp(wr, 0.55), wr, [(0, fa * 0.98, fa * 0.9), (1, fa * 0.86, fa * 0.78)],
                   f"{side}LowerArm", "Accent" if cfg.get("accent_wraps", True) else "Cloth2", 14)
        if "gauntlets" in out:
            m.loft(el.lerp(wr, 0.35), wr + (wr - el).normalized() * 0.02,
                   [(0, fa * 1.35, fa * 1.25), (1, fa * 1.3, fa * 1.2)], f"{side}LowerArm", "Gear", 14)
            m.block(el.lerp(wr, 0.7) + Vector((0, -fa * 1.2, 0)), (0.05, 0.02, 0.09), f"{side}LowerArm", "Accent", bevel=0.005)
        if "armor_shoulders" in out:
            m.ellipsoid(sh_ + Vector((sx * 0.02, 0, 0.035)), (ua * 1.6, ua * 1.5, ua * 1.05), f"{side}UpperArm", "Gear")
            m.ellipsoid(sh_ + Vector((sx * 0.03, 0, 0.075)), (ua * 1.0, ua * 0.85, ua * 0.3), f"{side}UpperArm", "Accent", 10, 6)
        # fist: palm block + knuckle row + thumb
        fist_c = wr.lerp(ht, 0.55)
        hs = 0.085 * (1.15 if k > 1.2 else 1.0)
        m.block(fist_c, (hs * 0.95, hs * 1.15, hs * 1.15), f"{side}Hand", "Gear" if (cyber or "gauntlets" in out) else "Skin", bevel=0.018)
        m.block(fist_c + Vector((0, -hs * 0.45, -hs * 0.25)), (hs * 0.9, hs * 0.4, hs * 0.45), f"{side}Hand",
                "Gear" if (cyber or "gauntlets" in out) else "Skin", bevel=0.012)
    # --- legs -------------------------------------------------------------------
    th, sn = cfg["leg"]
    for side, sx in (("Left", 1), ("Right", -1)):
        hip, knee = P[f"{side}UpperLeg"]
        ankle, toe = P[f"{side}Foot"]
        pants = "Cloth" if "pants" in out else "Skin"
        m.loft(hip + Vector((0, 0, 0.04)), knee, [(0, th * 1.1, th * 1.05), (0.3, th * 1.12, th * 1.08),
                                                (0.85, th * 0.82, th * 0.85), (1, th * 0.75, th * 0.78)],
               f"{side}UpperLeg", pants, 14)
        m.ellipsoid(knee, (sn * 1.15, sn * 1.2, sn * 1.15), f"{side}LowerLeg", pants, 10, 6)
        m.loft(knee, ankle + Vector((0, 0, 0.05)), [(0, sn * 1.08, sn * 1.05), (0.3, sn * 1.12, sn * 1.12),
                                                   (1, sn * 0.72, sn * 0.72)], f"{side}LowerLeg", pants, 14)
        if "boots" in out or "heavy_boots" in out:
            bk = 1.25 if "heavy_boots" in out else 1.0
            m.loft(knee.lerp(ankle, 0.45), ankle + Vector((0, 0, 0.02)),
                   [(0, sn * 1.12 * bk, sn * 1.12 * bk), (1, sn * 1.0 * bk, sn * 1.0 * bk)], f"{side}LowerLeg", "Gear", 14)
        foot_slot = "Gear" if ("boots" in out or "heavy_boots" in out) else ("Skin" if "sandals" in out else "Gear")
        fl = 0.26 * s
        m.block((ankle.x, -0.045 * s, 0.05), (0.105 * (1.15 if k > 1.2 else 1.0), fl, 0.1), f"{side}Foot", foot_slot,
                bevel=0.025)
        if "sandals" in out:
            m.block((ankle.x, -0.045 * s, 0.012), (0.11, fl * 1.04, 0.024), f"{side}Foot", "Gear", bevel=0.006)
    return m


# -------------------------------------------------------------- animation --
def stance(s):
    """Default fighting stance, scaled to the fighter's height."""
    return {
        "hips": (0.0, -0.06 * s, 0.0, 0.0),
        "spine": (4.0, -12.0), "chest": (4.0, -10.0), "head": (-6.0, 15.0),
        "LeftHand": (0.16, 0.30 * s, 1.36 * s), "RightHand": (-0.10, 0.18 * s, 1.28 * s),
        "LeftFoot": (0.13, 0.24 * s, 0.09), "RightFoot": (-0.13, -0.22 * s, 0.09),
    }


def build_actions(moves, s, fid):
    base = stance(s)
    F = fid.upper()

    def pose(**over):
        p = dict(base)
        p.update(over)
        return p

    def active_idx(mv):
        return mv["startup"] - 1, mv["startup"] + mv["active"] - 2

    def total(mv):
        return mv["startup"] + mv["active"] - 1 + mv["recovery"]

    def S(x, y, zz):
        return (x, y * s, zz * s)

    A = {}
    A[f"{F}_IDLE_A"] = [(0, pose()), (30, pose(hips=(0, -0.08 * s, 0, 0), LeftHand=S(0.16, 0.3, 1.33),
                                                RightHand=S(-0.1, 0.18, 1.25))), (60, pose())]
    A[f"{F}_WALK_FORWARD"] = [
        (0, pose()), (9, pose(hips=(0.0, -0.04 * s, 0, 0), LeftFoot=S(0.13, 0.32, 0.16), RightFoot=S(-0.13, -0.12, 0.09))),
        (18, pose(LeftFoot=S(0.13, 0.30, 0.09), RightFoot=S(-0.13, -0.18, 0.09))),
        (27, pose(hips=(0.0, -0.04 * s, 0, 0), LeftFoot=S(0.13, 0.20, 0.09), RightFoot=S(-0.13, -0.10, 0.16))),
        (36, pose())]
    A[f"{F}_WALK_BACKWARD"] = [
        (0, pose()), (10, pose(hips=(0.0, -0.04 * s, 0, 0), RightFoot=S(-0.13, -0.32, 0.16), LeftFoot=S(0.13, 0.14, 0.09))),
        (20, pose(RightFoot=S(-0.13, -0.28, 0.09), LeftFoot=S(0.13, 0.18, 0.09))),
        (30, pose(hips=(0.0, -0.04 * s, 0, 0), RightFoot=S(-0.13, -0.18, 0.09), LeftFoot=S(0.13, 0.26, 0.16))),
        (40, pose())]
    guard = pose(chest=(10.0, -20.0), head=(8.0, 10.0), LeftHand=S(0.06, 0.32, 1.48), RightHand=S(-0.04, 0.26, 1.42))
    A[f"{F}_BLOCK_HIGH"] = [(0, pose()), (5, guard), (12, guard)]
    lean = pose(hips=(-0.08, -0.06 * s, -8.0, 0), spine=(-10.0, -12.0), chest=(-12.0, -10.0), head=(-20.0, 15.0))
    A[f"{F}_HIT_LIGHT"] = [(0, pose()), (3, lean), (14, pose())]
    big = pose(hips=(-0.14, -0.1 * s, -14.0, 0), spine=(-16.0, -10.0), chest=(-18.0, -8.0), head=(-28.0, 10.0),
               LeftHand=S(0.25, 0.1, 1.2), RightHand=S(-0.25, 0.05, 1.15))
    A[f"{F}_HIT_HEAVY"] = [(0, pose()), (4, big), (24, pose())]
    down = pose(hips=(-0.55 * s, -0.82 * s, -82.0, 0), spine=(-4.0, 0.0), chest=(-4.0, 0.0), head=(10.0, 0.0),
                LeftHand=(0.35, -0.75 * s, 0.12), RightHand=(-0.35, -0.7 * s, 0.12),
                LeftFoot=(0.18, 0.55 * s, 0.12), RightFoot=(-0.16, 0.45 * s, 0.12))
    mid = pose(hips=(-0.35 * s, -0.45 * s, -45.0, 0), spine=(-14.0, 0.0), chest=(-14.0, 0.0), head=(-10.0, 0.0),
               LeftHand=S(0.35, -0.2, 0.9), RightHand=S(-0.35, -0.25, 0.85),
               LeftFoot=S(0.15, 0.45, 0.25), RightFoot=(-0.15, 0.2 * s, 0.09))
    A[f"{F}_KNOCKDOWN"] = [(0, big), (10, mid), (20, down), (45, down)]
    kneel = pose(hips=(-0.05, -0.45 * s, 10.0, 0), spine=(10.0, 0.0), chest=(10.0, 0.0), head=(-5.0, 0.0),
                 LeftFoot=(0.15, 0.35 * s, 0.09), RightFoot=(-0.15, -0.25 * s, 0.12),
                 LeftHand=S(0.25, 0.3, 0.75), RightHand=S(-0.2, 0.15, 0.45))
    A[f"{F}_GETUP"] = [(0, down), (8, kneel), (20, pose())]
    A[f"{F}_DEFEAT"] = [(0, pose()), (20, kneel), (40, kneel)]
    win = pose(chest=(-6.0, 0.0), head=(-12.0, 0.0), hips=(0, -0.02 * s, 0, 0),
               RightHand=S(-0.2, 0.05, 1.95), LeftHand=S(0.25, 0.1, 1.05),
               LeftFoot=S(0.14, 0.12, 0.09), RightFoot=S(-0.14, -0.1, 0.09))
    A[f"{F}_VICTORY"] = [(0, pose()), (20, win), (60, win)]

    def strike(mv, limb, lateral, wind, hit):
        a0, a1 = active_idx(mv)
        tgt = (lateral, mv["hc"][0] - (0.04 if "Hand" in limb else 0.0), mv["hc"][1])
        h = pose(**{limb: tgt}, **hit)
        keys = [(0, pose())]
        w = max(1, a0 // 2)
        if w < a0:
            keys.append((w, pose(**wind)))
        return keys + [(a0, h), (a1, h), (total(mv) - 1, pose())]

    L, H, K = moves["LIGHT"], moves["HEAVY"], moves["KICK"]
    A[f"{F}_ATTACK_LIGHT_01"] = strike(L, "LeftHand", 0.06, {"LeftHand": S(0.14, 0.2, 1.38)},
                                       {"chest": (6.0, -24.0), "spine": (4.0, -16.0)})
    A[f"{F}_ATTACK_HEAVY_01"] = strike(H, "RightHand", -0.02,
        {"RightHand": S(-0.18, -0.15, 1.3), "chest": (2.0, 20.0), "hips": (0.0, -0.08 * s, 0.0, 10.0)},
        {"chest": (14.0, -35.0), "spine": (8.0, -25.0), "hips": (0.24, -0.1 * s, 8.0, -15.0), "RightFoot": S(-0.13, -0.05, 0.09)})
    A[f"{F}_KICK_01"] = strike(K, "RightFoot", -0.08, {"RightFoot": S(-0.1, 0.3, 0.55), "hips": (0.0, -0.04 * s, -6.0, 0.0)},
                               {"hips": (-0.12, -0.02 * s, -14.0, 20.0), "spine": (-8.0, 0.0), "chest": (-6.0, 5.0),
                                "LeftFoot": S(0.1, 0.05, 0.09)})
    P_ = moves["SPECIAL"]
    gather = {"LeftHand": S(0.18, -0.1, 1.05), "RightHand": S(-0.18, -0.12, 1.02), "hips": (0.0, -0.14 * s, 0.0, 0.0),
              "chest": (0.0, 0.0)}
    palm = pose(LeftHand=(0.08, P_["hc"][0] - 0.02, P_["hc"][1] + 0.05), RightHand=(-0.06, P_["hc"][0] - 0.05, P_["hc"][1] - 0.06),
                hips=(0.22, -0.12 * s, 8.0, 0.0), chest=(10.0, 0.0), spine=(6.0, 0.0),
                LeftFoot=S(0.13, 0.45, 0.09), RightFoot=S(-0.13, -0.3, 0.09))
    A[f"{F}_SPECIAL_ORIGIN_PALM"] = [(0, pose()), (8, pose(**gather)), (active_idx(P_)[0], palm),
                                     (active_idx(P_)[1], palm), (total(P_) - 1, pose())]
    R = moves["FORWARD_SPECIAL"]
    lunge = pose(RightHand=(-0.02, R["hc"][0] - 0.04, R["hc"][1]), LeftHand=S(0.15, 0.1, 1.3),
                 hips=(0.3, -0.18 * s, 16.0, -20.0), chest=(16.0, -30.0), spine=(10.0, -20.0),
                 LeftFoot=S(0.13, 0.55, 0.09), RightFoot=S(-0.13, -0.2, 0.12))
    A[f"{F}_SPECIAL_RIFT_BREAK"] = [(0, pose()), (3, pose(hips=(0.0, -0.18 * s, 10.0, 0.0))),
                                    (active_idx(R)[0], lunge), (active_idx(R)[1], lunge), (total(R) - 1, pose())]
    SG = moves["SURGE"]
    roar = pose(LeftHand=S(0.55, 0.05, 1.25), RightHand=S(-0.55, 0.0, 1.25), chest=(-10.0, 0.0), head=(-15.0, 0.0),
                hips=(0.0, -0.1 * s, 0.0, 0.0))
    A[f"{F}_SURGE_ACTIVATE"] = [(0, pose()), (10, pose(**gather)), (20, roar), (total(SG) - 1, pose())]
    U = moves["ULTIMATE"]
    a0, a1 = active_idx(U)
    ult = pose(LeftHand=(0.06, U["hc"][0] - 0.02, U["hc"][1] + 0.04), RightHand=(-0.04, U["hc"][0] - 0.06, U["hc"][1] - 0.05),
               hips=(0.25, -0.16 * s, 10.0, 0.0), chest=(12.0, 0.0), spine=(8.0, 0.0),
               LeftFoot=S(0.13, 0.5, 0.09), RightFoot=S(-0.13, -0.35, 0.09))
    A[f"{F}_ULTIMATE_ORIGIN_BREAK"] = [(0, pose()), (3, pose(**gather)), (a0, ult), (a1, ult), (30, pose(**gather)),
                                       (total(U) - 1, pose())]
    return A


def setup_ik(arm_obj):
    targets = {}
    for limb, chain_end in (("LeftHand", "LeftLowerArm"), ("RightHand", "RightLowerArm"),
                            ("LeftFoot", "LeftLowerLeg"), ("RightFoot", "RightLowerLeg")):
        empty = bpy.data.objects.new(f"IK_{limb}", None)
        bpy.context.scene.collection.objects.link(empty)
        c = arm_obj.pose.bones[chain_end].constraints.new("IK")
        c.target = empty
        c.chain_count = 2
        c.use_tail = True
        c.mute = True
        targets[limb] = (empty, c)
    return targets


def apply_pose(arm_obj, targets, p):
    pb = arm_obj.pose.bones
    for b in pb:
        b.rotation_mode = "QUATERNION"
        b.matrix_basis = Matrix.Identity(4)
    fwd, dz, pitch, yaw = p["hips"]
    rest = arm_obj.data.bones["Hips"].matrix_local
    pb["Hips"].matrix = (Matrix.Translation((0, -fwd, dz)) @ rest @ Matrix.Rotation(math.radians(pitch), 4, "X")
                         @ Matrix.Rotation(math.radians(yaw), 4, "Y"))
    bpy.context.view_layer.update()
    for bone, key in (("Spine", "spine"), ("Chest", "chest"), ("Head", "head")):
        a, b = p[key]
        pb[bone].rotation_quaternion = (Matrix.Rotation(math.radians(a), 3, "X") @ Matrix.Rotation(math.radians(b), 3, "Y")).to_quaternion()
    for limb, (empty, c) in targets.items():
        lat, f, h = p[limb]
        empty.location = (lat, -f, h)
        c.mute = False
    bpy.context.view_layer.update()
    captured = {b.name: arm_obj.convert_space(pose_bone=b, matrix=b.matrix, from_space="POSE", to_space="LOCAL") for b in pb}
    for _l, (_e, c) in targets.items():
        c.mute = True
    return captured


def key_action(arm_obj, targets, name, keys):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm_obj.animation_data.action = act
    for frame, p in keys:
        cap = apply_pose(arm_obj, targets, p)
        for b in arm_obj.pose.bones:
            b.matrix_basis = cap[b.name]
        for b in arm_obj.pose.bones:
            b.keyframe_insert("rotation_quaternion", frame=frame, group=b.name)
            b.keyframe_insert("location", frame=frame, group=b.name)


def build_fighter(fid, moves, out_path):
    cfg = FIGHTERS[fid]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    mats = make_materials(fid, cfg["palette"])
    B = skeleton(cfg)
    arm_data = bpy.data.armatures.new(f"{fid.upper()}_Skeleton")
    arm_obj = bpy.data.objects.new(f"{fid.upper()}_Rig", arm_data)
    scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent, connect) in B.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail = head, tail
        eb.roll = 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
            eb.use_connect = connect
    bpy.ops.object.mode_set(mode="OBJECT")

    body = build_body(cfg, B)
    mesh = bpy.data.meshes.new(f"{fid.upper()}_Mesh")
    body.bm.normal_update()
    body.bm.to_mesh(mesh)
    body.bm.free()
    for slot in MAT_SLOTS:
        mesh.materials.append(mats[slot])
    obj = bpy.data.objects.new(f"{fid.upper()}_Body", mesh)
    scene.collection.objects.link(obj)
    for bone, _gi in sorted(body.groups.items(), key=lambda kv: kv[1]):
        obj.vertex_groups.new(name=bone)
    obj.parent = arm_obj
    obj.modifiers.new("Armature", "ARMATURE").object = arm_obj
    # Smooth shading with hard edges kept by angle (bevelled blocks stay crisp).
    for poly in mesh.polygons:
        poly.use_smooth = True

    arm_obj.animation_data_create()
    targets = setup_ik(arm_obj)
    actions = build_actions(moves, cfg["height"] / REF_HEIGHT, fid)
    for name, keys in actions.items():
        key_action(arm_obj, targets, name, keys)
    for pb in arm_obj.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    for empty, _c in targets.values():
        bpy.data.objects.remove(empty)
    arm_obj.animation_data.action = bpy.data.actions[f"{fid.upper()}_IDLE_A"]
    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    print(f"[character] {fid}: parts={body.parts} verts={len(mesh.vertices)} tris={tris} "
          f"bones={len(arm_data.bones)} actions={len(actions)}")
    bpy.ops.export_scene.gltf(filepath=out_path, export_format="GLB", export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_step=1,
                              export_skins=True, export_def_bones=False, export_yup=True, export_apply=False,
                              export_materials="EXPORT")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--fighter", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--moves", required=True, help="JSON from tools/blender/export_move_timing.gd")
    ap.add_argument("--out", default="assets/characters")
    a = ap.parse_args(argv)
    moves = json.loads(open(a.moves).read())
    ids = list(FIGHTERS) if a.all else [a.fighter]
    for fid in ids:
        build_fighter(fid, moves, f"{a.out}/{fid}/{fid}.glb")


if __name__ == "__main__":
    main()
