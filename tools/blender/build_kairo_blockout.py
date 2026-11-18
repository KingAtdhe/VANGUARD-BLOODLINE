"""Builds the Kairo BLOCKOUT character from scratch and exports it as GLB.

Run (Blender 5.x, as a Python module or inside Blender):
    python tools/blender/build_kairo_blockout.py --output assets/characters/kairo/kairo_blockout.glb
    blender -b -P tools/blender/build_kairo_blockout.py -- --output ...

This script IS the source asset (reproducible, reviewable in Git). It builds:
  * a stylized blockout mesh from primitives (no external or base meshes),
  * a humanoid skeleton using Godot SkeletonProfileHumanoid bone names,
  * rigid skinning (every vertex 100 % on one bone -> no joint deformation),
  * 17 actions named FIGHTER_ACTION_VARIANT, keyed at 60 fps so animation
    frame N == combat tick N of the move (attack poses hit the hitboxes on
    their active frames; IK targets come straight from the move data).

PLACEHOLDER: this is not final art. The final Kairo model must keep the same
bone names, rest scale/orientation and action names (docs/BLENDER_PIPELINE.md).
Conventions: metres, character faces -Y, Z up, origin between the feet,
animations in place (the simulation owns movement).
"""

import argparse
import math
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

FPS = 60

# ---------------------------------------------------------------- skeleton --
# name: (head, tail, parent, connected)
BONES = {
    "Root": ((0, 0, 0), (0, 0, 0.15), None, False),
    "Hips": ((0, 0, 1.0), (0, 0, 1.12), "Root", False),
    "Spine": ((0, 0, 1.12), (0, 0, 1.28), "Hips", True),
    "Chest": ((0, 0, 1.28), (0, 0, 1.45), "Spine", True),
    "Neck": ((0, 0, 1.45), (0, 0, 1.56), "Chest", True),
    "Head": ((0, 0, 1.56), (0, 0, 1.80), "Neck", True),
}
for side, sx in (("Left", 1.0), ("Right", -1.0)):
    BONES.update({
        f"{side}UpperArm": ((0.20 * sx, 0, 1.42), (0.24 * sx, 0.04, 1.14), "Chest", False),
        f"{side}LowerArm": ((0.24 * sx, 0.04, 1.14), (0.26 * sx, -0.02, 0.88), f"{side}UpperArm", True),
        f"{side}Hand": ((0.26 * sx, -0.02, 0.88), (0.265 * sx, -0.04, 0.78), f"{side}LowerArm", True),
        f"{side}UpperLeg": ((0.10 * sx, 0, 0.98), (0.11 * sx, -0.04, 0.54), "Hips", False),
        f"{side}LowerLeg": ((0.11 * sx, -0.04, 0.54), (0.11 * sx, 0.0, 0.09), f"{side}UpperLeg", True),
        f"{side}Foot": ((0.11 * sx, 0.0, 0.09), (0.11 * sx, -0.16, 0.03), f"{side}LowerLeg", True),
    })

# ---------------------------------------------------------------- materials --
MATERIALS = {
    "BLOCKOUT_Cloth": ((0.07, 0.075, 0.09), 0.85, None),
    "BLOCKOUT_ClothLight": ((0.15, 0.16, 0.2), 0.8, None),
    "BLOCKOUT_Skin": ((0.55, 0.36, 0.27), 0.6, None),
    "BLOCKOUT_Boots": ((0.03, 0.03, 0.035), 0.5, None),
    "BLOCKOUT_Hair": ((0.02, 0.02, 0.025), 0.7, None),
    "BLOCKOUT_OriginRed": ((0.75, 0.05, 0.06), 0.4, ((1.0, 0.08, 0.06), 2.5)),
}


def make_materials():
    mats = {}
    for name, (color, rough, emission) in MATERIALS.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        if emission:
            bsdf.inputs["Emission Color"].default_value = (*emission[0], 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission[1]
        mats[name] = m
    return mats


# -------------------------------------------------------------------- mesh --
class Builder:
    """Accumulates primitive parts into one bmesh with per-bone vertex groups."""

    def __init__(self, mat_names):
        self.bm = bmesh.new()
        self.mat_index = {n: i for i, n in enumerate(mat_names)}
        self.deform = self.bm.verts.layers.deform.verify()
        self.bone_index = {}
        self.parts = 0

    def _group(self, bone):
        if bone not in self.bone_index:
            self.bone_index[bone] = len(self.bone_index)
        return self.bone_index[bone]

    def _finish(self, geom, bone, mat):
        verts = [g for g in geom if isinstance(g, bmesh.types.BMVert)]
        faces = {f for v in verts for f in v.link_faces}
        gi = self._group(bone)
        for v in verts:
            v[self.deform][gi] = 1.0
        for f in faces:
            f.material_index = self.mat_index[mat]
        self.parts += 1

    def tube(self, a, b, r1, r2, bone, mat, segments=10, squash=1.0):
        """Tapered cylinder from point a to b (squash scales its depth)."""
        a, b = Vector(a), Vector(b)
        length = (b - a).length
        ret = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segments,
                                    radius1=r1, radius2=r2, depth=length)
        verts = ret["verts"]
        bmesh.ops.scale(self.bm, vec=(1.0, squash, 1.0), verts=verts)
        rot = (b - a).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
        bmesh.ops.transform(self.bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=verts)
        self._finish(verts, bone, mat)

    def ball(self, c, r, bone, mat, scale=(1, 1, 1), segs=12, rings=8):
        ret = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=r)
        verts = ret["verts"]
        bmesh.ops.scale(self.bm, vec=scale, verts=verts)
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=verts)
        self._finish(verts, bone, mat)

    def box(self, c, size, bone, mat, rot_x=0.0):
        ret = bmesh.ops.create_cube(self.bm, size=1.0)
        verts = ret["verts"]
        bmesh.ops.scale(self.bm, vec=size, verts=verts)
        if rot_x:
            bmesh.ops.rotate(self.bm, verts=verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(rot_x), 3, "X"))
        bmesh.ops.translate(self.bm, vec=Vector(c), verts=verts)
        self._finish(verts, bone, mat)

    def cone(self, a, b, r, bone, mat):
        self.tube(a, b, r, 0.0, bone, mat, segments=6)


def build_mesh(mat_names):
    m = Builder(mat_names)
    # Torso
    m.box((0, 0.0, 0.99), (0.34, 0.22, 0.17), "Hips", "BLOCKOUT_Cloth")
    m.tube((0, 0, 1.04), (0, 0, 1.08), 0.178, 0.178, "Hips", "BLOCKOUT_OriginRed", 14, 0.72)  # belt
    m.tube((0, 0, 1.07), (0, 0, 1.29), 0.15, 0.175, "Spine", "BLOCKOUT_Cloth", 12, 0.72)
    m.tube((0, 0, 1.28), (0, 0, 1.47), 0.19, 0.215, "Chest", "BLOCKOUT_ClothLight", 12, 0.68)
    m.tube((0, 0, 1.355), (0, 0, 1.375), 0.198, 0.2, "Chest", "BLOCKOUT_OriginRed", 12, 0.7)  # chest stripe
    m.tube((0, 0, 1.44), (0, 0, 1.58), 0.05, 0.048, "Neck", "BLOCKOUT_Skin", 8)
    # Head, headband, spiky hair (silhouette)
    m.ball((0, -0.01, 1.68), 0.105, "Head", "BLOCKOUT_Skin", (0.95, 1.05, 1.18))
    m.tube((0, 0, 1.70), (0, 0, 1.725), 0.112, 0.112, "Head", "BLOCKOUT_OriginRed", 14, 1.07)
    for (dx, dy, dz, tx, ty, tz) in [(0, 0.02, 1.76, 0, 0.12, 1.86), (0.06, 0.03, 1.75, 0.11, 0.14, 1.83),
                                     (-0.06, 0.03, 1.75, -0.11, 0.14, 1.83), (0, 0.07, 1.72, 0, 0.2, 1.74),
                                     (0.04, -0.04, 1.77, 0.05, -0.08, 1.86)]:
        m.cone((dx, dy, dz), (tx, ty, tz), 0.05, "Head", "BLOCKOUT_Hair")
    # Arms and legs
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        sh, el, wr, hd = (Vector(BONES[f"{side}UpperArm"][0]), Vector(BONES[f"{side}LowerArm"][0]),
                          Vector(BONES[f"{side}Hand"][0]), Vector(BONES[f"{side}Hand"][1]))
        m.ball(sh, 0.075, f"{side}UpperArm", "BLOCKOUT_ClothLight")
        m.tube(sh, el, 0.058, 0.05, f"{side}UpperArm", "BLOCKOUT_Cloth", 10)
        m.ball(el, 0.05, f"{side}LowerArm", "BLOCKOUT_Skin", segs=10, rings=6)
        m.tube(el, wr, 0.047, 0.04, f"{side}LowerArm", "BLOCKOUT_Skin", 10)
        m.tube(el.lerp(wr, 0.6), wr, 0.05, 0.046, f"{side}LowerArm", "BLOCKOUT_OriginRed", 10)  # wraps
        m.box(wr.lerp(hd, 0.55), (0.085, 0.1, 0.11), f"{side}Hand", "BLOCKOUT_Skin")
        hip, knee, ankle, toe = (Vector(BONES[f"{side}UpperLeg"][0]), Vector(BONES[f"{side}LowerLeg"][0]),
                                 Vector(BONES[f"{side}Foot"][0]), Vector(BONES[f"{side}Foot"][1]))
        m.tube(hip, knee, 0.09, 0.068, f"{side}UpperLeg", "BLOCKOUT_Cloth", 10)
        m.ball(knee, 0.064, f"{side}LowerLeg", "BLOCKOUT_Cloth", segs=10, rings=6)
        m.tube(knee, ankle + Vector((0, 0, 0.06)), 0.062, 0.05, f"{side}LowerLeg", "BLOCKOUT_Cloth", 10)
        m.box((ankle.x, -0.05, 0.06), (0.1, 0.25, 0.12), f"{side}Foot", "BLOCKOUT_Boots")
    return m


# -------------------------------------------------------------- animation --
STANCE = {
    "hips": (0.0, -0.06, 0.0, 0.0),            # (forward, height delta, pitch, yaw)
    "spine": (4.0, -12.0), "chest": (4.0, -10.0), "head": (-6.0, 15.0),   # (pitch, yaw) degrees
    "LeftHand": (0.16, 0.30, 1.36), "RightHand": (-0.10, 0.18, 1.28),     # (lateral, forward, height)
    "LeftFoot": (0.13, 0.24, 0.09), "RightFoot": (-0.13, -0.22, 0.09),
}


def pose(**over):
    p = {k: v for k, v in STANCE.items()}
    p.update(over)
    return p


def build_actions(moves):
    """Key poses per action: list of (frame, pose). Attack timing from moves."""
    def active_idx(m):
        return m["startup"] - 1, m["startup"] + m["active"] - 2  # 0-based anim frames

    def total(m):
        return m["startup"] + m["active"] - 1 + m["recovery"]

    acts = {}
    acts["KAIRO_IDLE_A"] = [(0, pose()), (30, pose(hips=(0, -0.08, 0, 0), LeftHand=(0.16, 0.3, 1.33),
                                                      RightHand=(-0.1, 0.18, 1.25))), (60, pose())]
    acts["KAIRO_WALK_FORWARD"] = [
        (0, pose()),
        (9, pose(hips=(0.0, -0.04, 0, 0), LeftFoot=(0.13, 0.32, 0.16), RightFoot=(-0.13, -0.12, 0.09))),
        (18, pose(LeftFoot=(0.13, 0.30, 0.09), RightFoot=(-0.13, -0.18, 0.09))),
        (27, pose(hips=(0.0, -0.04, 0, 0), LeftFoot=(0.13, 0.20, 0.09), RightFoot=(-0.13, -0.10, 0.16))),
        (36, pose())]
    acts["KAIRO_WALK_BACKWARD"] = [
        (0, pose()),
        (10, pose(hips=(0.0, -0.04, 0, 0), RightFoot=(-0.13, -0.32, 0.16), LeftFoot=(0.13, 0.14, 0.09))),
        (20, pose(RightFoot=(-0.13, -0.28, 0.09), LeftFoot=(0.13, 0.18, 0.09))),
        (30, pose(hips=(0.0, -0.04, 0, 0), RightFoot=(-0.13, -0.18, 0.09), LeftFoot=(0.13, 0.26, 0.16))),
        (40, pose())]
    guard = pose(chest=(10.0, -20.0), head=(8.0, 10.0), LeftHand=(0.06, 0.32, 1.48), RightHand=(-0.04, 0.26, 1.42))
    acts["KAIRO_BLOCK_HIGH"] = [(0, pose()), (5, guard), (12, guard)]
    lean = pose(hips=(-0.08, -0.06, -8.0, 0), spine=(-10.0, -12.0), chest=(-12.0, -10.0), head=(-20.0, 15.0))
    acts["KAIRO_HIT_LIGHT"] = [(0, pose()), (3, lean), (14, pose())]
    big_lean = pose(hips=(-0.14, -0.1, -14.0, 0), spine=(-16.0, -10.0), chest=(-18.0, -8.0), head=(-28.0, 10.0),
                    LeftHand=(0.25, 0.1, 1.2), RightHand=(-0.25, 0.05, 1.15))
    acts["KAIRO_HIT_HEAVY"] = [(0, pose()), (4, big_lean), (24, pose())]
    down = pose(hips=(-0.55, -0.82, -82.0, 0), spine=(-4.0, 0.0), chest=(-4.0, 0.0), head=(10.0, 0.0),
                LeftHand=(0.35, -0.75, 0.12), RightHand=(-0.35, -0.7, 0.12),
                LeftFoot=(0.18, 0.55, 0.12), RightFoot=(-0.16, 0.45, 0.12))
    fall_mid = pose(hips=(-0.35, -0.45, -45.0, 0), spine=(-14.0, 0.0), chest=(-14.0, 0.0), head=(-10.0, 0.0),
                    LeftHand=(0.35, -0.2, 0.9), RightHand=(-0.35, -0.25, 0.85),
                    LeftFoot=(0.15, 0.45, 0.25), RightFoot=(-0.15, 0.2, 0.09))
    acts["KAIRO_KNOCKDOWN"] = [(0, big_lean), (10, fall_mid), (20, down), (45, down)]
    kneel = pose(hips=(-0.05, -0.45, 10.0, 0), spine=(10.0, 0.0), chest=(10.0, 0.0), head=(-5.0, 0.0),
                 LeftFoot=(0.15, 0.35, 0.09), RightFoot=(-0.15, -0.25, 0.12),
                 LeftHand=(0.25, 0.3, 0.75), RightHand=(-0.2, 0.15, 0.45))
    acts["KAIRO_GETUP"] = [(0, down), (8, kneel), (20, pose())]
    acts["KAIRO_DEFEAT"] = [(0, pose()), (20, kneel), (40, kneel)]
    win = pose(chest=(-6.0, 0.0), head=(-12.0, 0.0), hips=(0, -0.02, 0, 0),
               RightHand=(-0.2, 0.05, 1.95), LeftHand=(0.25, 0.1, 1.05),
               LeftFoot=(0.14, 0.12, 0.09), RightFoot=(-0.14, -0.1, 0.09))
    acts["KAIRO_VICTORY"] = [(0, pose()), (20, win), (60, win)]

    # --- attacks: active frames put the striking limb at the hitbox centre.
    def strike(m, limb, lateral, extra_wind, extra_hit, wind_at=None):
        a0, a1 = active_idx(m)
        tgt = (lateral, m["hc"][0] - (0.04 if "Hand" in limb else 0.0), m["hc"][1])
        hit = pose(**{limb: tgt}, **extra_hit)
        keys = [(0, pose())]
        w = wind_at if wind_at is not None else max(1, a0 // 2)
        if w < a0:
            keys.append((w, pose(**extra_wind)))
        keys += [(a0, hit), (a1, hit), (total(m) - 1, pose())]
        return keys

    L, H, K = moves["LIGHT"], moves["HEAVY"], moves["KICK"]
    acts["KAIRO_ATTACK_LIGHT_01"] = strike(L, "LeftHand", 0.06,
        {"LeftHand": (0.14, 0.2, 1.38)}, {"chest": (6.0, -24.0), "spine": (4.0, -16.0)})
    acts["KAIRO_ATTACK_HEAVY_01"] = strike(H, "RightHand", -0.02,
        {"RightHand": (-0.18, -0.15, 1.3), "chest": (2.0, 20.0), "hips": (0.0, -0.08, 0.0, 10.0)},
        {"chest": (14.0, -35.0), "spine": (8.0, -25.0), "hips": (0.24, -0.1, 8.0, -15.0),
         "RightFoot": (-0.13, -0.05, 0.09)})
    acts["KAIRO_KICK_01"] = strike(K, "RightFoot", -0.08,
        {"RightFoot": (-0.1, 0.3, 0.55), "hips": (0.0, -0.04, -6.0, 0.0)},
        {"hips": (-0.12, -0.02, -14.0, 20.0), "spine": (-8.0, 0.0), "chest": (-6.0, 5.0),
         "LeftFoot": (0.1, 0.05, 0.09)})
    P = moves["SPECIAL"]
    gather = {"LeftHand": (0.18, -0.1, 1.05), "RightHand": (-0.18, -0.12, 1.02),
              "hips": (0.0, -0.14, 0.0, 0.0), "chest": (0.0, 0.0)}
    acts["KAIRO_SPECIAL_ORIGIN_PALM"] = [
        (0, pose()), (8, pose(**gather)),
        (active_idx(P)[0], pose(LeftHand=(0.08, P["hc"][0] - 0.02, P["hc"][1] + 0.05),
                                RightHand=(-0.06, P["hc"][0] - 0.05, P["hc"][1] - 0.06),
                                hips=(0.22, -0.12, 8.0, 0.0), chest=(10.0, 0.0), spine=(6.0, 0.0),
                                LeftFoot=(0.13, 0.45, 0.09), RightFoot=(-0.13, -0.3, 0.09))),
        (active_idx(P)[1], pose(LeftHand=(0.08, P["hc"][0] - 0.02, P["hc"][1] + 0.05),
                                RightHand=(-0.06, P["hc"][0] - 0.05, P["hc"][1] - 0.06),
                                hips=(0.22, -0.12, 8.0, 0.0), chest=(10.0, 0.0), spine=(6.0, 0.0),
                                LeftFoot=(0.13, 0.45, 0.09), RightFoot=(-0.13, -0.3, 0.09))),
        (total(P) - 1, pose())]
    R = moves["FORWARD_SPECIAL"]
    lunge = pose(RightHand=(-0.02, R["hc"][0] - 0.04, R["hc"][1]), LeftHand=(0.15, 0.1, 1.3),
                 hips=(0.3, -0.18, 16.0, -20.0), chest=(16.0, -30.0), spine=(10.0, -20.0),
                 LeftFoot=(0.13, 0.55, 0.09), RightFoot=(-0.13, -0.2, 0.12))
    acts["KAIRO_SPECIAL_RIFT_BREAK"] = [(0, pose()), (3, pose(hips=(0.0, -0.18, 10.0, 0.0))),
                                        (active_idx(R)[0], lunge), (active_idx(R)[1], lunge), (total(R) - 1, pose())]
    S = moves["SURGE"]
    roar = pose(LeftHand=(0.55, 0.05, 1.25), RightHand=(-0.55, 0.0, 1.25), chest=(-10.0, 0.0),
                head=(-15.0, 0.0), hips=(0.0, -0.1, 0.0, 0.0))
    acts["KAIRO_SURGE_ACTIVATE"] = [(0, pose()), (10, pose(**gather)), (20, roar), (total(S) - 1, pose())]
    U = moves["ULTIMATE"]
    a0, a1 = active_idx(U)
    ult_hit = pose(LeftHand=(0.06, U["hc"][0] - 0.02, U["hc"][1] + 0.04),
                   RightHand=(-0.04, U["hc"][0] - 0.06, U["hc"][1] - 0.05),
                   hips=(0.25, -0.16, 10.0, 0.0), chest=(12.0, 0.0), spine=(8.0, 0.0),
                   LeftFoot=(0.13, 0.5, 0.09), RightFoot=(-0.13, -0.35, 0.09))
    acts["KAIRO_ULTIMATE_ORIGIN_BREAK"] = [(0, pose()), (3, pose(**gather)), (a0, ult_hit), (a1, ult_hit),
                                           (30, pose(**gather)), (total(U) - 1, pose())]
    return acts


def setup_rig(arm_obj):
    """IK chains (targets are empties) used only while posing; muted otherwise."""
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
    # Hips bone local axes: Y up the spine. Location in bone space: (x, y=up, z=?)
    # Easier: set via pose-space matrix.
    rest = arm_obj.data.bones["Hips"].matrix_local
    m = Matrix.Translation((0, -fwd, dz)) @ rest @ \
        Matrix.Rotation(math.radians(pitch), 4, "X") @ Matrix.Rotation(math.radians(yaw), 4, "Y")
    pb["Hips"].matrix = m
    bpy.context.view_layer.update()
    for bone, key in (("Spine", "spine"), ("Chest", "chest"), ("Head", "head")):
        pitch_b, yaw_b = p[key]
        pb[bone].rotation_quaternion = (Matrix.Rotation(math.radians(pitch_b), 3, "X") @
                                        Matrix.Rotation(math.radians(yaw_b), 3, "Y")).to_quaternion()
    for limb, (empty, c) in targets.items():
        lat, f, h = p[limb]
        empty.location = (lat, -f, h)
        c.mute = False
    bpy.context.view_layer.update()
    # Capture the visual (constraint-solved) pose as plain local transforms.
    captured = {}
    for b in pb:
        captured[b.name] = arm_obj.convert_space(pose_bone=b, matrix=b.matrix, from_space="POSE", to_space="LOCAL")
    for _limb, (_e, c) in targets.items():
        c.mute = True
    return captured


def key_action(arm_obj, targets, name, keys):
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    arm_obj.animation_data.action = action
    for frame, p in keys:
        captured = apply_pose(arm_obj, targets, p)
        # Apply captured local matrices parent-first so children stay correct.
        for b in arm_obj.pose.bones:
            b.matrix_basis = captured[b.name]
        for b in arm_obj.pose.bones:
            b.keyframe_insert("rotation_quaternion", frame=frame, group=b.name)
            b.keyframe_insert("location", frame=frame, group=b.name)
    return action


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--moves", default="")  # JSON from tools/blender/export_move_timing.gd
    args = ap.parse_args(argv)

    import json
    moves = json.loads(open(args.moves).read()) if args.moves else DEFAULT_MOVES

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS

    mats = make_materials()
    names = list(MATERIALS.keys())

    arm_data = bpy.data.armatures.new("KAIRO_BLOCKOUT_Skeleton")
    arm_obj = bpy.data.objects.new("KAIRO_BLOCKOUT_Rig", arm_data)
    scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, parent, connect) in BONES.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail = head, tail
        eb.roll = 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
            eb.use_connect = connect
    bpy.ops.object.mode_set(mode="OBJECT")

    builder = build_mesh(names)
    mesh = bpy.data.meshes.new("KAIRO_BLOCKOUT_Mesh")
    builder.bm.to_mesh(mesh)
    builder.bm.free()
    for n in names:
        mesh.materials.append(mats[n])
    body = bpy.data.objects.new("KAIRO_BLOCKOUT_Body", mesh)
    scene.collection.objects.link(body)
    for bone, gi in sorted(builder.bone_index.items(), key=lambda kv: kv[1]):
        body.vertex_groups.new(name=bone)
    body.parent = arm_obj
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    for poly in mesh.polygons:
        poly.use_smooth = True

    arm_obj.animation_data_create()
    targets = setup_rig(arm_obj)
    actions = build_actions(moves)
    for name, keys in actions.items():
        key_action(arm_obj, targets, name, keys)
    # Remove posing helpers before export.
    for pb in arm_obj.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    for empty, _c in targets.values():
        bpy.data.objects.remove(empty)
    arm_obj.animation_data.action = bpy.data.actions["KAIRO_IDLE_A"]
    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)

    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    print(f"[blockout] parts={builder.parts} verts={len(mesh.vertices)} tris={tris} "
          f"bones={len(arm_data.bones)} actions={len(actions)}")

    bpy.ops.export_scene.gltf(filepath=args.output, export_format="GLB", export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True,
                              export_frame_step=1, export_skins=True, export_def_bones=False,
                              export_yup=True, export_apply=False, export_materials="EXPORT")
    print(f"[blockout] exported {args.output}")


# Fallback timings if no move JSON is given (kept in sync by the Godot exporter).
DEFAULT_MOVES = {
    "LIGHT": {"startup": 5, "active": 3, "recovery": 10, "hc": [0.6, 1.45]},
    "HEAVY": {"startup": 12, "active": 3, "recovery": 19, "hc": [0.7, 1.35]},
    "KICK": {"startup": 9, "active": 4, "recovery": 15, "hc": [0.8, 0.9]},
    "SPECIAL": {"startup": 14, "active": 5, "recovery": 24, "hc": [0.95, 1.3]},
    "FORWARD_SPECIAL": {"startup": 16, "active": 4, "recovery": 22, "hc": [0.8, 1.1]},
    "SURGE": {"startup": 20, "active": 1, "recovery": 10, "hc": [0.0, 1.0]},
    "ULTIMATE": {"startup": 7, "active": 4, "recovery": 45, "hc": [0.9, 1.3]},
}

if __name__ == "__main__":
    main()
