"""Fighter animations from real motion capture (CMU Graphics Lab Motion
Capture Database, BVH conversion; free for all uses — see LICENSES.md).

build(rig, moves, fid, height, clip_dir) keys every game action on the
shared 18-bone fighter skeleton and replaces the old procedural key poses.

How it works
------------
* Source clips are read with tools/mocap/bvh.py and scaled to the fighter's
  height. Each source frame becomes joint POSITIONS.
* Retarget by directions: every game bone is turned so it points the way the
  real limb points (minimal swing from its parent, so limbs don't twist);
  hips, spine, chest, neck and head also take the real side-to-side axis
  (hip line, shoulder line), so the torso keeps its real turn and lean.
  Proportions don't matter, only directions; the hips height is scaled.
* Strikes are retimed to the move's frame data: guard -> full extension ->
  guard is warped so the extension lands in the move's active frames (the
  hitbox test checks the striking limb against the hitbox). The limb is
  also guided onto the hitbox centre with two-bone IK during the strike, so
  every fighter's punches land where the game says they do.
* Moves that have no good capture (hit reactions, block, power-up,
  victory, knockdown, get-up, defeat, walks) are built from captured poses:
  the boxer's own guard with layered body reactions, real lying / sitting /
  kneeling poses blended with gravity-like timing, and generated footwork
  matched to the game's walk speed (the captured footwork is ~5x slower).
"""
import math
import os
import sys

import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mocap"))
from bvh import BVH  # noqa: E402

FPS_SRC = 120
FPS_OUT = 60

# game bone -> (source head joint, source tail joint) for the direction it points
LIMB = {
    "LeftUpperArm": ("LeftArm", "LeftForeArm"), "LeftLowerArm": ("LeftForeArm", "LeftHand"),
    "LeftHand": ("LeftHand", "LeftHandIndex1"), "RightUpperArm": ("RightArm", "RightForeArm"),
    "RightLowerArm": ("RightForeArm", "RightHand"), "RightHand": ("RightHand", "RightHandIndex1"),
    "LeftUpperLeg": ("LeftUpLeg", "LeftLeg"), "LeftLowerLeg": ("LeftLeg", "LeftFoot"),
    "LeftFoot": ("LeftFoot", "LeftToeBase"), "RightUpperLeg": ("RightUpLeg", "RightLeg"),
    "RightLowerLeg": ("RightLeg", "RightFoot"), "RightFoot": ("RightFoot", "RightToeBase"),
}
# torso bone -> (up from, up to, side axis)
TORSO = {
    "Hips": ("Hips", "Spine", "hips"), "Spine": ("Spine", "Spine1", "mid"),
    # (in the CMU skeleton Neck sits exactly on Spine1, so the chest runs to Neck1)
    "Chest": ("Spine1", "Neck1", "shoulders"), "Neck": ("Neck1", "Head", "shoulders"),
    "Head": ("Head", "Head_end", "shoulders"),
}


# --------------------------------------------------------------------------- clips

class Clip:
    """Joint positions of one capture, scaled to the fighter (Blender axes)."""
    _cache = {}

    def __init__(self, path, height):
        key = (path, round(height, 3))
        if key not in Clip._cache:
            P, _ = BVH(path).positions(height)
            Clip._cache[key] = P
        self.P = {k: v.copy() for k, v in Clip._cache[key].items()}
        self.n = len(self.P["Hips"])
        # standing hips height (the T-pose calibration frame 0)
        self.stand_hips = float(self.P["Hips"][0, 2] - min(self.P["LeftToeBase"][0, 2], self.P["RightToeBase"][0, 2]))

    def at(self, f):
        """Positions at fractional source frame f (linear between frames)."""
        f = min(max(f, 0.0), self.n - 1.001)
        i, t = int(f), f - int(f)
        return {k: v[i] * (1 - t) + v[i + 1] * t for k, v in self.P.items()}

    def opponent_dir(self, frame, window=400):
        """Horizontal direction the fighter faces: from the strikes nearest
        to `frame` (where the fists go), else the hip-line normal."""
        dirs = []
        for side in ("Left", "Right"):
            sh, hd = self.P[side + "Arm"], self.P[side + "Hand"]
            reach = np.linalg.norm(hd - sh, axis=1)
            lo, hi = max(0, frame - window), min(self.n, frame + window)
            for i in range(lo + 1, hi - 1):
                if reach[i] > 0.9 * reach[lo:hi].max() and reach[i] >= reach[i - 1] and reach[i] >= reach[i + 1]:
                    d = hd[i] - sh[i]
                    d[2] = 0
                    dirs.append(d / max(1e-6, np.linalg.norm(d)))
        if dirs:
            d = np.mean(dirs, 0)
        else:
            lr = self.P["LeftUpLeg"][frame] - self.P["RightUpLeg"][frame]
            d = np.cross(lr, [0, 0, 1.0])
        d[2] = 0
        return d / max(1e-6, np.linalg.norm(d))


def align(pos, facing, anchor_xy):
    """Rotate about Z so `facing` -> -Y, and move anchor_xy to the origin."""
    ang = math.atan2(facing[0], -facing[1])          # angle from -Y to facing
    c, s = math.cos(-ang), math.sin(-ang)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    out = {}
    for k, v in pos.items():
        p = v.copy()
        p[0] -= anchor_xy[0]
        p[1] -= anchor_xy[1]
        out[k] = R @ p
    return out


# --------------------------------------------------------------------------- retarget

def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def _frame(side, up):
    z = _norm(up)
    x = _norm(side - z * np.dot(side, z))
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def _swing(a, b):
    """Minimal rotation (3x3) taking direction a onto b."""
    a, b = _norm(a), _norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.9999:
        axis = _norm(np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]))
        return np.array(Matrix.Rotation(math.pi, 3, Vector(axis)))
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


class Rig:
    """Rest data of the game skeleton (armature at the origin)."""

    def __init__(self, arm_obj):
        self.obj = arm_obj
        self.names = [b.name for b in arm_obj.data.bones]
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm_obj.data.bones}
        self.rest = {b.name: np.array(b.matrix_local) for b in arm_obj.data.bones}
        self.head = {b.name: np.array(b.head_local) for b in arm_obj.data.bones}
        self.tail = {b.name: np.array(b.tail_local) for b in arm_obj.data.bones}
        self.dir = {n: _norm(self.tail[n] - self.head[n]) for n in self.names}
        self.hips_h = float(self.head["Hips"][2])
        self.foot_h = float(min(self.head["LeftFoot"][2], self.head["RightFoot"][2]))


def retarget(rig, P, stand_hips, ground=True):
    """One source pose (aligned positions) -> {bone: delta rotation D (3x3)}
    and the hips head position. World rotation = D @ rest rotation."""
    side = {
        "hips": P["LeftUpLeg"] - P["RightUpLeg"],
        "shoulders": P["LeftArm"] - P["RightArm"],
    }
    side["mid"] = side["hips"] + side["shoulders"]
    D = {"Root": np.eye(3)}
    for name in rig.names:
        if name == "Root":
            continue
        if name in TORSO:
            a, b, s = TORSO[name]
            F = _frame(side[s], P[b] - P[a])
            # rest torso is upright, facing -Y: its frame is the identity
            R0 = _frame(np.array([1.0, 0, 0]), rig.dir[name])
            D[name] = F @ R0.T
        else:
            a, b = LIMB[name]
            par = D[rig.parent[name]]
            carried = par @ rig.dir[name]
            D[name] = _swing(carried, P[b] - P[a]) @ par
    k = (rig.hips_h - rig.foot_h) / max(1e-6, stand_hips)
    hips = np.array([P["Hips"][0], P["Hips"][1], 0.0]) * 1.0
    hips[2] = rig.foot_h + (P["Hips"][2] - min(P["LeftToeBase"][2], P["RightToeBase"][2], P["Hips"][2])) * k \
        if ground else P["Hips"][2] * k
    return D, hips


def fk(rig, D, hips):
    """Joint heads in world space for a pose (D, hips head position)."""
    pos = {"Root": rig.head["Root"]}
    for n in rig.names:
        p = rig.parent[n]
        if p is None:
            continue
        if n == "Hips":
            pos[n] = hips
        else:
            pos[n] = pos[p] + D[p] @ (rig.head[n] - rig.head[p])
    tails = {n: pos[n] + D[n] @ (rig.tail[n] - rig.head[n]) for n in rig.names if n in pos}
    return pos, tails


def ground_fix(rig, D, hips, floor=None):
    """Lift/drop the hips so the lowest foot rests on the floor."""
    pos, tails = fk(rig, D, hips)
    low = min(pos["LeftFoot"][2], pos["RightFoot"][2], tails["LeftFoot"][2] + 0.03, tails["RightFoot"][2] + 0.03)
    target = rig.foot_h if floor is None else floor
    hips = hips.copy()
    hips[2] += target - low
    return hips


# --------------------------------------------------------------------------- source-space edits

def ik2(P, a, b, c, target, pole):
    """Two-bone IK on source positions: joints a (root), b (mid), c (end)
    reach `target`; the mid joint bends toward `pole`."""
    A = P[a]
    l1 = np.linalg.norm(P[b] - A)
    l2 = np.linalg.norm(P[c] - P[b])
    t = np.array(target, float)
    d = t - A
    dist = np.clip(np.linalg.norm(d), 1e-4, (l1 + l2) * 0.999)
    dn = _norm(d)
    cos_a = np.clip((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1)
    pole_dir = _norm((pole - A) - dn * np.dot(pole - A, dn))
    B = A + dn * cos_a * l1 + pole_dir * math.sqrt(max(0.0, 1 - cos_a * cos_a)) * l1
    C = A + dn * dist
    P = dict(P)
    P[b], P[c] = B, C
    return P


def move_hand(P, side, target, weight=1.0, pole_out=0.35):
    if weight <= 0:
        return P
    cur = P[side + "Hand"]
    tgt = cur + (np.array(target) - cur) * weight
    sgn = 1 if side == "Left" else -1
    pole = P[side + "ForeArm"] + np.array([0.15 * sgn, 0.05, -0.25]) * pole_out / 0.35
    Q = ik2(P, side + "Arm", side + "ForeArm", side + "Hand", tgt, pole)
    for k in ("HandIndex1", "HandIndex1_end", "FingerBase", "Thumb", "Thumb_end"):
        if side + k in P:
            Q[side + k] = P[side + k] - cur + Q[side + "Hand"]
    if side[0] + "Thumb" in P:
        Q[side[0] + "Thumb"] = P[side[0] + "Thumb"] - cur + Q[side + "Hand"]
    return Q


def move_foot(P, side, target, weight=1.0):
    if weight <= 0:
        return P
    cur = P[side + "Foot"]
    tgt = cur + (np.array(target) - cur) * weight
    pole = P[side + "Leg"] + np.array([0, -0.4, 0.0])        # knees point forward (-Y)
    Q = ik2(P, side + "UpLeg", side + "Leg", side + "Foot", tgt, pole)
    for k in ("ToeBase", "ToeBase_end"):
        if side + k in P:
            Q[side + k] = P[side + k] - cur + Q[side + "Foot"]
    return Q


def shift(P, keys, delta):
    P = dict(P)
    for k in keys:
        if k in P:
            P[k] = P[k] + delta
    return P


UPPER = ["LowerBack", "Spine", "Spine1", "Neck", "Neck1", "Head", "Head_end", "LeftShoulder", "LeftArm",
         "LeftForeArm", "LeftHand", "LeftFingerBase", "LeftHandIndex1", "LeftHandIndex1_end", "LThumb",
         "LThumb_end", "RightShoulder", "RightArm", "RightForeArm", "RightHand", "RightFingerBase",
         "RightHandIndex1", "RightHandIndex1_end", "RThumb", "RThumb_end"]


def lean(P, pitch_deg, about="Hips", roll_deg=0.0, keys=None):
    """Rotate the upper body about the hips: +pitch leans back (away from -Y)."""
    keys = keys or UPPER
    o = P[about]
    Rx = np.array(Matrix.Rotation(math.radians(-pitch_deg), 3, "X"))
    Ry = np.array(Matrix.Rotation(math.radians(roll_deg), 3, "Y"))
    R = Ry @ Rx
    P = dict(P)
    for k in keys:
        if k in P:
            P[k] = o + R @ (P[k] - o)
    return P


# --------------------------------------------------------------------------- poses and keying

class Pose:
    def __init__(self, D, hips):
        self.D, self.hips = D, hips

    @staticmethod
    def blend(a, b, t):
        D = {}
        for n in a.D:
            qa = Matrix(a.D[n].tolist()).to_quaternion()
            qb = Matrix(b.D[n].tolist()).to_quaternion()
            D[n] = np.array(qa.slerp(qb, t).to_matrix())
        return Pose(D, a.hips * (1 - t) + b.hips * t)


def ease(t, kind="inout"):
    t = min(max(t, 0.0), 1.0)
    if kind == "in":
        return t * t
    if kind == "out":
        return 1 - (1 - t) * (1 - t)
    if kind == "back":            # slight overshoot
        s = 1.4
        t -= 1
        return t * t * ((s + 1) * t + s) + 1
    return t * t * (3 - 2 * t)


def key_action(rig, name, poses):
    """poses: list of Pose, one per output frame (60 fps)."""
    import bpy
    obj = rig.obj
    act = bpy.data.actions.new(name)
    obj.animation_data.action = act
    rest = rig.rest
    for f, pose in enumerate(poses):
        for n in rig.names:
            pb = obj.pose.bones[n]
            pb.rotation_mode = "QUATERNION"
            if n == "Root":
                pb.rotation_quaternion = Quaternion()
                pb.location = Vector()
            else:
                p = rig.parent[n]
                Wp = pose.D[p] @ rest[p][:3, :3]
                W = pose.D[n] @ rest[n][:3, :3]
                basis = rest[n][:3, :3].T @ rest[p][:3, :3] @ Wp.T @ W
                pb.rotation_quaternion = Matrix(basis.tolist()).to_quaternion()
                if n == "Hips":
                    # translation of the head in the bone's rest frame
                    pb.location = Vector((rest[n][:3, :3].T @ (pose.hips - rest[n][:3, 3])).tolist())
                pb.keyframe_insert("rotation_quaternion", frame=f)
            if n in ("Root", "Hips"):
                pb.keyframe_insert("location", frame=f)
    return act


# --------------------------------------------------------------------------- the actions

def build(rig_obj, moves, fid, height, clip_dir):
    rig = Rig(rig_obj)
    F = fid.upper()
    clip = lambda name: Clip(os.path.join(clip_dir, name + ".bvh"), height)  # noqa: E731
    box = clip("13_17")          # boxer: guard, jab, cross, combos
    art = clip("144_13")         # martial artist: straight lead punches
    art_r = clip("144_20")       # martial artist: straight rear punches
    kick = clip("144_05")        # front kicks
    lay = clip("113_08")         # lie down / get up (on the back)
    H = height / 1.8

    def src(c, f, facing_frame=None, anchor=None):
        P = c.at(f)
        fd = c.opponent_dir(int(facing_frame if facing_frame is not None else f))
        a = anchor if anchor is not None else P["Hips"][:2]
        return align(P, fd, a)

    def pose_of(P, c, ground=True):
        D, hips = retarget(rig, P, c.stand_hips, ground)
        if ground:
            hips = ground_fix(rig, D, hips)
        return Pose(D, hips)

    A = {}

    # ---- idle: the boxer's guard bounce, 1 s, looped with a cross-fade
    i0, n_idle = 840, 60
    anchor_idle = box.at(i0)["Hips"][:2]
    def raw_idle_P(t):      # t in output frames (60 fps), loops
        f = i0 + (t % n_idle) * 2
        P = src(box, f, facing_frame=900, anchor=anchor_idle)
        # keep the hips over the origin (no drift in a loop)
        P = shift(P, list(P.keys()), np.array([-P["Hips"][0], -P["Hips"][1], 0]))
        return P
    # The captured boxer bounces and shifts constantly (shadow boxing), which
    # reads as dancing on a select screen: keep a steady guard with ~35% of
    # the captured motion around the average pose (breathing, small bob).
    raw = [raw_idle_P(t) for t in range(n_idle)]
    mean = {k: np.mean([r[k] for r in raw], 0) for k in raw[0]}
    def idle_P(t):
        r = raw[int(t) % n_idle]
        return {k: mean[k] + (r[k] - mean[k]) * 0.35 for k in r}
    idle_poses = []
    fade = 14
    for t in range(n_idle + 1):
        p = pose_of(idle_P(t), box)
        if t > n_idle - fade:       # blend the tail into the head for a seamless loop
            w = ease((t - (n_idle - fade)) / fade)
            p = Pose.blend(p, pose_of(idle_P(t - n_idle), box), w)
        idle_poses.append(p)
    A[f"{F}_IDLE_A"] = idle_poses
    guard_P = idle_P(0)
    guard = idle_poses[0]

    # ---- strikes retimed to frame data, limb guided onto the hitbox
    def strike(c, peak, side, limb, mv, pre=24, post=34, facing=None, reach_w=1.0, extra=None):
        start, total = mv["startup"], mv["startup"] + mv["active"] - 1 + mv["recovery"]
        a0, a1 = mv["startup"] - 1, mv["startup"] + mv["active"] - 2
        mid = (a0 + a1) / 2
        hc = mv["hc"]
        tgt_fwd, tgt_h = -hc[0], hc[1]
        anchor = c.at(peak - pre)["Hips"][:2]
        poses = []
        for t in range(total):
            # piecewise-linear time warp: 0 -> peak-pre, mid -> peak, end -> peak+post
            if t <= mid:
                f = (peak - pre) + (t / max(1e-6, mid)) * pre
            else:
                f = peak + (t - mid) / max(1e-6, total - 1 - mid) * post
            P = src(c, f, facing_frame=facing or peak, anchor=anchor)
            # body stays near the game position: keep 40% of the lunge
            dx = np.array([-P["Hips"][0], -P["Hips"][1] * 0.6, 0])
            P = shift(P, list(P.keys()), dx)
            # guide the striking limb onto the hitbox around the active frames
            w = 0.0
            if t <= mid:
                w = ease(max(0.0, (t - (a0 - min(a0, 4))) / max(1.0, mid - (a0 - min(a0, 4)))))
            else:
                w = 1.0 - ease(min(1.0, (t - a1) / 7.0)) if t > a1 else 1.0
            w *= reach_w
            if limb == "hand":
                cur = P[side + "Hand"]
                P = move_hand(P, side, np.array([cur[0] * 0.5, tgt_fwd + 0.02, tgt_h]), w)
            else:
                cur = P[side + "Foot"]
                P = move_foot(P, side, np.array([cur[0], tgt_fwd + 0.08, tgt_h]), w)
            if extra:
                P = extra(P, t, total)
            poses.append(pose_of(P, c))
        # settle into the guard over the last frames so the next move blends cleanly
        n = len(poses)
        for t in range(max(0, n - 8), n):
            poses[t] = Pose.blend(poses[t], guard, ease((t - (n - 8)) / 8))
        return poses

    A[f"{F}_ATTACK_LIGHT_01"] = strike(box, 1214, "Left", "hand", moves["LIGHT"], pre=20, post=30)
    A[f"{F}_ATTACK_HEAVY_01"] = strike(box, 3368, "Right", "hand", moves["HEAVY"], pre=28, post=40)
    A[f"{F}_KICK_01"] = strike(kick, 1240, "Right", "foot", moves["KICK"], pre=40, post=60)
    A[f"{F}_SPECIAL_ORIGIN_PALM"] = strike(art, 439, "Left", "hand", moves["SPECIAL"], pre=34, post=46)
    A[f"{F}_SPECIAL_RIFT_BREAK"] = strike(art_r, 645, "Right", "hand", moves["FORWARD_SPECIAL"], pre=36, post=50,
                                          extra=lambda P, t, T: lean(P, -10 * math.sin(math.pi * min(1, t / T))))

    # ultimate: the one-two lands on the active frames, then a flurry in recovery
    mv = moves["ULTIMATE"]
    total = mv["startup"] + mv["active"] - 1 + mv["recovery"]
    first = strike(box, 366, "Left", "hand", mv, pre=16, post=16)
    flurry_src = [(391, 22), (1214, 26), (1238, 26), (3368, 30)]   # cross, jab, cross, finishing cross
    tail = []
    for pk, span in flurry_src:
        anchor = box.at(pk - span)["Hips"][:2]
        for k in range(span):
            P = src(box, pk - span + 2 * k, facing_frame=pk, anchor=anchor)
            P = shift(P, list(P.keys()), np.array([-P["Hips"][0], -P["Hips"][1] * 0.6, 0]))
            tail.append(pose_of(P, box))
    a1 = mv["startup"] + mv["active"] - 2
    seq = first[:a1 + 3]
    need = total - len(seq)
    # resample the flurry to fill the recovery, ending in the guard
    for t in range(need):
        u = t / max(1, need - 1)
        idx = u * (len(tail) - 1)
        p = Pose.blend(tail[int(idx)], tail[min(len(tail) - 1, int(idx) + 1)], idx - int(idx))
        if t > need - 10:
            p = Pose.blend(p, guard, ease((t - (need - 10)) / 10))
        seq.append(p)
    A[f"{F}_ULTIMATE_ORIGIN_BREAK"] = seq

    # ---- surge: sink and draw the fists to the hips, then explode open
    mv = moves["SURGE"]
    total = mv["startup"] + mv["active"] - 1 + mv["recovery"]
    surge = []
    for t in range(total):
        P = guard_P
        u = t / (total - 1)
        charge = ease(min(1, u / 0.55))
        burst = ease(max(0, (u - 0.55) / 0.2), "back") if u > 0.55 else 0
        settle = ease(max(0, (u - 0.8) / 0.2))
        P = shift(P, UPPER + ["Hips"], np.array([0, 0, -0.2 * H * charge * (1 - burst * 0.8)]))
        for side, sg in (("Left", 1), ("Right", -1)):
            hip_pt = P["Hips"] + np.array([0.24 * sg * H, 0.05 * H, -0.02 * H])
            wide = P[side + "Arm"] + np.array([0.6 * sg * H, -0.1 * H, 0.05 * H])
            tgt = hip_pt * (1 - burst) + wide * burst
            P = move_hand(P, side, tgt, charge * (1 - settle), pole_out=0.6)
        P = lean(P, 20 * burst * (1 - settle) - 14 * charge * (1 - burst))
        surge.append(pose_of(P, box))
    A[f"{F}_SURGE_ACTIVATE"] = surge

    # ---- block: both forearms up in front of the face, held
    head = guard_P["Head"]
    blk = []
    for t in range(13):
        w = ease(min(1, t / 5), "out")
        P = guard_P
        for side, sg in (("Left", 1), ("Right", -1)):
            P = move_hand(P, side, head + np.array([0.07 * sg * H, -0.2 * H, 0.05 * H]), w, pole_out=0.2)
        P = lean(P, -6 * w)
        blk.append(pose_of(P, box))
    A[f"{F}_BLOCK_HIGH"] = blk

    # ---- hit reactions: head and chest snap back, then recover (spring)
    def hit(n, amp, twist):
        # snap back within 2-3 frames, then a damped recovery to the guard
        out = []
        for t in range(n):
            u = t / (n - 1)
            k = ease(min(1.0, t / 2.5), "out") * (1 - ease(max(0.0, (u - 0.18) / 0.82)))
            k += 0.12 * math.sin(math.pi * u * 3) * (1 - u)        # a little wobble on the way back
            P = shift(guard_P, list(guard_P.keys()), np.array([0, 0.09 * H * amp * k, -0.04 * H * amp * k]))
            P = lean(P, 24 * amp * k, roll_deg=twist * k)
            P = lean(P, 18 * amp * k, about="Neck1", keys=["Head", "Head_end"])
            for side, sg in (("Left", 1), ("Right", -1)):         # guard knocked loose
                P = move_hand(P, side, P[side + "Hand"] + np.array([0.05 * sg * H, 0.12 * H, -0.12 * H]) * amp, k * 0.8)
            out.append(pose_of(P, box))
        return out
    A[f"{F}_HIT_LIGHT"] = hit(15, 0.75, 6)
    A[f"{F}_HIT_HEAVY"] = hit(25, 1.4, -14)

    # ---- lying / sitting / kneeling poses from the capture (on the back)
    def lay_pose(f, head_back=True):
        P = lay.at(f)
        # orient: head toward +Y (fell away from the opponent), centred
        d = P["Head"] - P["Hips"]
        d[2] = 0
        d = d / max(1e-6, np.linalg.norm(d))
        Pa = align(P, -d if head_back else d, P["Hips"][:2])
        return Pa
    lying_P = lay_pose(820)
    sit_P = lay_pose(1450, head_back=True)
    kneel_P = lay_pose(300, head_back=True)
    lying = pose_of(lying_P, lay, ground=True)
    sitting = pose_of(sit_P, lay, ground=True)
    kneel = pose_of(kneel_P, lay, ground=True)
    lying.hips = lying.hips + np.array([0, 0.55 * H, 0])

    # knockdown (45): heavy snap, fall backward with gravity, small bounce, lie
    heavy = A[f"{F}_HIT_HEAVY"][4]
    kd = []
    for t in range(46):
        if t <= 4:
            p = Pose.blend(guard, heavy, ease(t / 4))
        elif t <= 20:
            p = Pose.blend(heavy, lying, ease((t - 4) / 16, "in"))
        else:
            p = Pose(lying.D, lying.hips.copy())
            b = math.exp(-(t - 20) / 4.0) * abs(math.sin((t - 20) / 3.0)) * 0.05 * H
            p.hips = p.hips + np.array([0, 0, b])
            br = 0.006 * H * math.sin(t * 0.25)          # breathing
            p.hips = p.hips + np.array([0, 0, br])
        kd.append(p)
    A[f"{F}_KNOCKDOWN"] = kd

    # get-up (20): lying -> sit up -> crouch -> guard, quick and powerful
    crouch = Pose.blend(kneel, guard, 0.45)
    gu = []
    for t in range(21):
        if t <= 7:
            p = Pose.blend(lying, sitting, ease(t / 7, "out"))
        elif t <= 13:
            p = Pose.blend(sitting, crouch, ease((t - 7) / 6))
        else:
            p = Pose.blend(crouch, guard, ease((t - 13) / 7, "out"))
        gu.append(p)
    A[f"{F}_GETUP"] = gu

    # defeat (40): stagger, drop to the knees, slump
    df = []
    for t in range(41):
        if t <= 6:
            p = Pose.blend(guard, heavy, ease(t / 6))
        elif t <= 24:
            p = Pose.blend(heavy, kneel, ease((t - 6) / 18, "in"))
        else:
            P = lean(kneel_P, -14 * ease((t - 24) / 16))
            p = Pose.blend(kneel, pose_of(P, lay), ease((t - 24) / 16))
        df.append(p)
    A[f"{F}_DEFEAT"] = df

    # victory (60): rear fist raised overhead, chest up, a breath
    vc = []
    for t in range(61):
        w = ease(min(1, t / 16), "back")
        P = guard_P
        top = P["Head"] + np.array([-0.08 * H, 0.0, 0.42 * H])
        P = move_hand(P, "Right", top, min(1.0, w), pole_out=0.5)
        P = move_hand(P, "Left", P["Hips"] + np.array([0.2 * H, -0.12 * H, 0.15 * H]), min(1.0, w) * 0.8)
        P = lean(P, 5 * min(1.0, w) + 1.5 * math.sin(t * 0.18))
        vc.append(pose_of(P, box))
    A[f"{F}_VICTORY"] = vc

    # ---- walks: the boxer's upper body over generated footwork
    def walk(speed, forward):
        n = 36
        cyc = n / 2.0                 # two shuffle steps per loop
        out = []
        base = idle_P(0)
        lf, rf = base["LeftFoot"].copy(), base["RightFoot"].copy()
        lead = "Left" if lf[1] < rf[1] else "Right"       # lead foot is further toward -Y
        rear = "Right" if lead == "Left" else "Left"
        stride = speed * (cyc / FPS_OUT) * 0.55           # partly planted, partly slide
        for t in range(n + 1):
            P = idle_P(t)
            ph = (t % cyc) / cyc
            first, second = (lead, rear) if forward else (rear, lead)
            sgn = -1 if forward else 1                    # travel along -Y (forward) or +Y
            for foot, (s0, s1) in ((first, (0.0, 0.5)), (second, (0.35, 0.85))):
                u = min(1, max(0, (ph - s0) / (s1 - s0)))
                swing = math.sin(math.pi * u)
                home = base[foot + "Foot"]
                off = sgn * stride * (ease(u) - 0.5)
                tgt = home + np.array([0, off, 0.07 * H * swing])
                P = move_foot(P, foot, tgt, 1.0)
            # body bob and a lean into the direction of travel
            bob = 0.015 * H * math.sin(2 * math.pi * ph * 2)
            P = shift(P, UPPER + ["Hips"], np.array([0, 0, -abs(bob)]))
            P = lean(P, (-4 if forward else 3))
            out.append(pose_of(P, box, ground=False))
        # same loop seam handling as the idle
        return out
    A[f"{F}_WALK_FORWARD"] = walk(2.6, True)
    A[f"{F}_WALK_BACKWARD"] = walk(2.0, False)

    acts = {}
    for name, poses in A.items():
        acts[name] = key_action(rig, name, poses)
    return acts
