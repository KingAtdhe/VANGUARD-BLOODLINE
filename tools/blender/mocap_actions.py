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

# Per-fighter guard (idle stance): source clip and frame of a calm guard,
# share of the captured bounce kept, crouch / extra stance width (x height/1.8),
# upper-body lean (deg, + = back) and hand offset (out, back, up).
STYLES = {
    # Each stance is posed by hand on a captured guard (pose_stance): the base
    # of support, hip height, how the chest is turned and where each hand is
    # held come from the fighter's design; bob / sway / tap are idle habits.
    # Each stance follows a reference the owner approved by name (D-074); they
    # were posed from knowledge of those characters, not traced from footage.
    # Kairo, after Steve Fox: upright boxer on a short springy base, lead
    # shoulder in front, lead fist out at chin height, rear fist on the cheek.
    "kairo": dict(clip="13_17", frame=840, facing=900, amp=0.3, bob=0.022, bob_beats=2, lead="Left",
                  pose=dict(fit=True, hips=(-0.045, 0.0), pelvis_h=0.965, trunk=(7, 0), pelvis=32, shoulders=44, neck=8, chin=6,
                            lead_foot=(0.09, 0.19), rear_foot=(0.11, 0.20), lead_toe=-10, rear_toe=45, rear_heel=0.03,
                            lead_hand=(0.11, 0.33, -0.19), rear_hand=(0.12, 0.07, -0.15),
                            lead_elbow=0.15, rear_elbow=0.12, lead_palm="in", rear_palm="in")),
    # Drakon, after Zangief: wide and square, knees out, chest forward, both
    # arms held open and high at the sides ready to grab.
    "drakon": dict(clip="14_02", frame=4530, amp=0.25, sway=0.035,
                   pose=dict(hips=(0.0, 0.09), lean=1, shoulders=10, chin=0, knees=0.25,
                             lead_foot=(0.30, 0.10), rear_foot=(0.30, 0.10), lead_toe=35, rear_toe=35,
                             lead_hand=(0.40, 0.28, -0.26), rear_hand=(0.40, 0.22, -0.26), lead_elbow=0.7, rear_elbow=0.7)),
    # Seraphina, after Hwoarang: side-on and tall on a narrow base, bouncing,
    # lead arm hanging low in front, rear hand loose at the chest.
    # Fitted to her own skeleton (D-077); blueprint in docs/POSE_BLUEPRINTS.md.
    "seraphina": dict(clip="144_07", frame=1620, amp=0.4, turn=180, bob=0.028, bob_beats=2,
                      pose=dict(fit=True, hips=(-0.02, 0.0), pelvis_h=0.985, trunk=(1, 0), pelvis=52, shoulders=64, neck=5, chin=4,
                                lead_foot=(0.03, 0.155), rear_foot=(0.05, 0.155), lead_toe=-18, rear_toe=78,
                                lead_heel=0.02, rear_heel=0.025,
                                lead_hand=(0.07, 0.26, -0.45), rear_hand=(0.11, 0.21, -0.30),
                                lead_elbow=0.2, rear_elbow=0.45, lead_palm="in", rear_palm="in")),
    # Nox, after Raven: side-on, lead hand reaching out in front below the
    # chin, rear hand held ready in front of the ribs. Upright since D-080
    # (owner: "he needs to stand straight"); he was low and coiled before.
    # Fitted to his own skeleton (D-079); blueprint in docs/POSE_BLUEPRINTS.md.
    "nox": dict(clip="144_20", frame=1590, amp=0.3, sway=0.02,
                pose=dict(fit=True, hips=(-0.02, 0.0), pelvis_h=0.985, trunk=(3, 0), pelvis=38, shoulders=48, neck=4, chin=3,
                          knees=0.0, lead_foot=(0.07, 0.15), rear_foot=(0.10, 0.16), lead_toe=0, rear_toe=45, rear_heel=0.025,
                          lead_hand=(0.05, 0.36, -0.22), rear_hand=(0.20, 0.25, -0.19),
                          lead_elbow=0.25, rear_elbow=0.2, lead_palm="down", rear_palm="in")),
    # Vexa, after Sagat: tall Muay Thai, hips square, both gloves high at the
    # brow with the lead one further out, lead foot light and lifting.
    # Fitted to her own skeleton (D-076); blueprint in docs/POSE_BLUEPRINTS.md.
    "vexa": dict(clip="14_01", frame=2700, amp=0.5, tap=0.05,
                 pose=dict(fit=True, hips=(-0.03, 0.0), pelvis_h=0.99, trunk=(3, 0), pelvis=18, shoulders=24, neck=6, chin=8,
                           lead_foot=(0.08, 0.14), rear_foot=(0.10, 0.15), lead_toe=0, rear_toe=40, lead_heel=0.03,
                           lead_hand=(0.11, 0.30, 0.0), rear_hand=(0.13, 0.10, -0.03),
                           lead_elbow=0.35, rear_elbow=0.3, lead_palm="in", rear_palm="in")),
    # Ryuen, after Leroy Smith: upright Wing Chun, weight on the rear leg, lead
    # hand out on the centre line, rear hand guarding behind the lead elbow.
    "ryuen": dict(clip="144_13", frame=150, amp=0.15,
                  pose=dict(hips=(-0.07, 0.03), lean=1, shoulders=35, lead_foot=(0.05, 0.28), rear_foot=(0.10, 0.14),
                            lead_toe=0, rear_toe=45, lead_heel=0.03, lead_hand=(0.0, 0.50, -0.24),
                            rear_hand=(0.0, 0.26, -0.30), lead_elbow=0.12, rear_elbow=0.2)),
}
FPS_OUT = 60


def idle_motion(P, st, H, u):
    """The character's own idle habit on top of the captured breathing, from
    the design doc (STYLES knobs; u = 0..1 through the one-second loop, and
    every habit is zero at u = 0 so the guard pose is unchanged):
      bob   knees dip this far, bob_beats times per loop (Kairo, Seraphina)
      sway  body rocks this far to each side over planted feet (Drakon, Nox)
      tap   the lead foot lifts this high twice per loop (Vexa)"""
    feet = {sd: P[sd + "Foot"].copy() for sd in ("Left", "Right")}
    knees = st.get("pose", {}).get("knees", 0.0)
    dx = st.get("sway", 0.0) * H * math.sin(2 * math.pi * u)
    dz = -st.get("bob", 0.0) * H * 0.5 * (1 - math.cos(2 * math.pi * u * st.get("bob_beats", 1)))
    if dx != 0.0 or dz != 0.0:
        P = shift(P, list(P.keys()), np.array([dx, 0, dz]))
        for sd in ("Left", "Right"):
            P = move_foot(P, sd, feet[sd], knee_out=knees)
    if st.get("tap"):
        lead = st.get("lead") or ("Left" if feet["Left"][1] < feet["Right"][1] else "Right")
        lift = st["tap"] * H * max(0.0, math.sin(2 * math.pi * u * 2)) ** 2
        P = move_foot(P, lead, feet[lead] + np.array([0, 0, lift]), knee_out=knees)
    return P


def shape_stance(P, st, H):
    """Shapes a captured guard into a fighter's own stance (STYLES knobs, all
    in metres x height/1.8 unless noted):
      crouch  body lower (+) or taller (-); the feet stay put, knees follow
      stride  feet further apart along the fight line (lead forward, rear back)
      width   feet further apart across it
      weight  body carried toward the lead foot (+) or the rear foot (-)
      lean    upper body pitch in degrees (+ = back)
      hands / lead_hand / rear_hand   hand offsets (out to the side, back, up)"""
    feet = {sd: P[sd + "Foot"].copy() for sd in ("Left", "Right")}
    lead = st.get("lead") or ("Left" if feet["Left"][1] < feet["Right"][1] else "Right")
    # the whole figure moves, then the feet are put back with IK: the leg
    # bones keep their length and only the knee angle changes
    moved = list(P.keys())
    P = shift(P, moved, np.array([0, -st.get("weight", 0.0) * H, -st.get("crouch", 0.0) * H]))
    P = lean(P, st.get("lean", 0.0))
    for sd, sg in (("Left", 1), ("Right", -1)):
        along = (-0.5 if sd == lead else 0.5) * st.get("stride", 0.0) * H
        tgt = feet[sd] + np.array([sg * st.get("width", 0.0) * H, along, 0])
        P = move_foot(P, sd, tgt, 1.0)
    for sd, sg in (("Left", 1), ("Right", -1)):
        off = np.array(st.get("hands", (0, 0, 0)), float) \
            + np.array(st.get("lead_hand" if sd == lead else "rear_hand", (0, 0, 0)), float)
        if off.any():
            P = move_hand(P, sd, P[sd + "Hand"] + np.array([sg * off[0], off[1], off[2]]) * H, 1.0,
                          pole_out=st.get("elbows", 0.35))
    st["_lead"] = lead
    return pose_stance(P, st, H, lead) if st.get("pose") else P


def pose_stance(P, st, H, lead):
    """A stance posed by hand on top of the captured guard (D-073): the
    captured pose only supplies natural shoulders, spine and hands; where the
    feet stand, how low the hips sit, how the chest is turned and where each
    hand is held are all set here. `pose` keys (metres x height/1.8):
      hips       (forward, drop): hips over the lead (+) or rear (-) foot, and lowered
      lean, chin upper body pitch (+ back), head pitch (+ = chin down)
      shoulders  how far the chest is turned side-on, in degrees: 0 = square to
                 the opponent, 90 = lead shoulder pointing straight at them
                 (absolute: whatever way the captured performer stood)
      twist      older relative turn about the spine, kept for reference
      knees      knees pushed out to the sides (0 = pointing at the opponent)
      lead_toe, rear_toe   foot turned out, degrees from the fight line
      lead_foot, rear_foot   (across, along): where each foot stands from the
                 point under the hips; along is toward the opponent for the
                 lead foot and away from them for the rear foot
      lead_heel, rear_heel   that heel lifted this high (weight on the ball of the foot)
      pelvis     how far the hips are turned side-on, like `shoulders`
      trunk      (forward, toward the lead side) lean of the spine in degrees, absolute
      spine      how much of the captured back's curve is straightened out (0..1, default 0.85)
      neck, chin, head_turn   neck craned forward, chin dropped (degrees), and the
                 share of the chest turn the head keeps (the eyes stay on the opponent)
      lead_hand, rear_hand   (across, forward, up) from the head joint
      lead_elbow, rear_elbow how far the elbow swings out (0.1 tucked .. 0.7 flared)"""
    ps = st["pose"]
    rear = "Right" if lead == "Left" else "Left"
    sgl = 1 if lead == "Left" else -1                     # +x is the fighter's left
    floor = {sd: P[sd + "Foot"][2] for sd in ("Left", "Right")}
    fwd, drop = ps.get("hips", (0.0, 0.0))
    P = shift(P, list(P.keys()), np.array([-P["Hips"][0], -P["Hips"][1], 0]))        # hips over the origin
    P = shift(P, list(P.keys()), np.array([0, -fwd * H, -drop * H]))
    P = lean(P, ps.get("lean", 0.0))
    if ps.get("twist"):
        o = np.array([P["Hips"][0], P["Hips"][1], 0.0])
        R = np.array(Matrix.Rotation(math.radians(ps["twist"] * sgl), 3, "Z"))
        for k in UPPER:
            if k in P:
                P[k] = R @ (P[k] - o) + o
    if "trunk" in ps:
        # the spine set outright: (forward, toward the lead side) lean in degrees,
        # whatever way the captured performer happened to be leaning
        f, sdl = math.radians(ps["trunk"][0]), math.radians(ps["trunk"][1])
        want = _norm(np.array([math.tan(sdl) * sgl, -math.tan(f), 1.0]))
        R = _swing(P["Neck1"] - P["Hips"], want)
        o = P["Hips"].copy()
        for k in UPPER:
            if k in P:
                P[k] = R @ (P[k] - o) + o
        # ... and its shape (D-081). The captured performer's back keeps its
        # curve when the trunk is stood up: a crouching fighter's rounded
        # back, made vertical, became a pelvis tipped forward under a chest
        # leaning back (Nox: 22 degrees between them). The joints of the
        # back are drawn onto the straight line from pelvis to collar;
        # `spine` (default 0.85) is how much of the curve is taken out.
        k_s = ps.get("spine", 0.85)
        a0, a1 = P["Hips"], P["Neck1"]
        ln = a1 - a0
        for k in ("LowerBack", "Spine", "Spine1", "Neck"):
            if k in P:
                on = a0 + ln * float(np.clip(np.dot(P[k] - a0, ln) / (np.dot(ln, ln) + 1e-12), 0.0, 1.0))
                P[k] = P[k] + (on - P[k]) * k_s
    if "pelvis" in ps:                                     # hips turned side-on, like `shoulders`
        v = P[lead + "UpLeg"] - P[rear + "UpLeg"]
        cur = math.degrees(math.atan2(-v[1], sgl * v[0]))
        o = P["Hips"].copy()
        R = np.array(Matrix.Rotation(math.radians(-(ps["pelvis"] - cur) * sgl), 3, "Z"))
        for k in ("LHipJoint", "RHipJoint", "LeftUpLeg", "RightUpLeg"):
            if k in P:
                P[k] = R @ (P[k] - o) + o
    if "shoulders" in ps:
        v = P[lead + "Arm"] - P[rear + "Arm"]
        cur = math.degrees(math.atan2(-v[1], sgl * v[0]))
        # turned about the spine itself, so a leaning body does not swing sideways
        # (about +Z a positive turn carries +X toward +Y, away from the opponent)
        o, axis = P["Hips"].copy(), Vector(P["Neck1"] - P["Hips"]).normalized()
        R = np.array(Matrix.Rotation(math.radians(-(ps["shoulders"] - cur) * sgl), 3, axis))
        for k in UPPER:
            if k in P:
                P[k] = R @ (P[k] - o) + o
    for sd, key, sign_x, sign_y in ((lead, "lead_foot", sgl, -1), (rear, "rear_foot", -sgl, 1)):
        if key in ps:
            ax, al = ps[key]
            lift = ps.get("lead_heel" if sd == lead else "rear_heel", 0.0) * H
            P = move_foot(P, sd, np.array([sign_x * ax * H, sign_y * al * H, floor[sd] + lift]),
                          knee_out=ps.get("knees", 0.0))
            toe = "lead_toe" if sd == lead else "rear_toe"
            if toe in ps:                                  # foot turned out about the ankle
                a = math.radians(ps[toe]) * sign_x
                for k in ("ToeBase", "ToeBase_end"):
                    if sd + k in P:
                        d = P[sd + k] - P[sd + "Foot"]
                        n = math.hypot(d[0], d[1])
                        P[sd + k] = P[sd + "Foot"] + np.array([math.sin(a) * n, -math.cos(a) * n, d[2]])
            if lift > 0:                                   # toes stay on the floor
                P[sd + "ToeBase"] = P[sd + "ToeBase"] - np.array([0, 0, lift])
    for sd, key, sign_x in ((lead, "lead_hand", sgl), (rear, "rear_hand", -sgl)):
        if key in ps:
            ax, fw, up = ps[key]
            tgt = P["Head"] + np.array([sign_x * ax, -fw, up]) * H
            P = move_hand(P, sd, tgt, 1.0, pole_out=ps.get("lead_elbow" if sd == lead else "rear_elbow", 0.35))
    if "shoulders" in ps:
        # The head is set outright, never inherited from the capture (a head
        # that leaned forward in the capture leans sideways once the chest is
        # turned). The eyes stay on the opponent: the head keeps `head_turn`
        # of the chest turn (default a quarter), the neck cranes `neck`
        # degrees forward and the chin drops `chin` degrees. No sideways tilt.
        a = -math.radians(ps["shoulders"] * ps.get("head_turn", 0.25)) * sgl   # the chest of a left lead faces right
        fwd = np.array([math.sin(a), -math.cos(a), 0.0])
        up = np.array([0.0, 0.0, 1.0])
        nk, ch = math.radians(ps.get("neck", 10.0)), math.radians(ps.get("chin", 0.0))
        l_neck = np.linalg.norm(P["Head"] - P["Neck1"])
        l_head = np.linalg.norm(P["Head_end"] - P["Head"])
        P["Head"] = P["Neck1"] + (fwd * math.sin(nk) + up * math.cos(nk)) * l_neck
        P["Head_end"] = P["Head"] + (fwd * math.sin(ch) + up * math.cos(ch)) * l_head
        P["HeadSide0"] = P["Head"].copy()
        P["HeadSide"] = P["Head"] + np.array([math.cos(a), math.sin(a), 0.0])
    return P


PALMS = {"in": (-1.0, 0.0, 0.0), "out": (1.0, 0.0, 0.0), "down": (0.0, 0.0, -1.0), "up": (0.0, 0.0, 1.0),
         "forward": (0.0, -1.0, 0.0), "back": (0.0, 1.0, 0.0)}


def _ik_dirs(a, target, l1, l2, hint):
    """Two-bone IK in model space: directions of both bones from root `a` so
    the end reaches `target` (as far as the limb goes), bending toward `hint`."""
    d = np.asarray(target, float) - a
    closest = math.sqrt(l1 * l1 + l2 * l2 - 2 * l1 * l2 * math.cos(math.radians(32.0)))   # folds to 148 degrees at most
    dist = float(np.clip(np.linalg.norm(d), closest, (l1 + l2) * 0.995))
    dn = _norm(d)
    cos_a = np.clip((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1)
    h = np.asarray(hint, float)
    pole = _norm(h - dn * np.dot(h, dn))
    mid = a + dn * cos_a * l1 + pole * math.sqrt(max(0.0, 1 - cos_a * cos_a)) * l1
    end = a + dn * dist
    return _norm(mid - a), _norm(end - mid)


def solve_leg(rig, P, pos, sd, mark, toe_deg, heel=0.0, hop=0.0, knee_out=0.0, toe_up=0.0):
    """One leg solved on the real rig and written back into the source pose:
    the ankle over floor mark `mark` (model x, y), the foot turned `toe_deg`
    (signed, + = toward +X), the heel lifted `heel` with the ball of the
    foot staying on the floor, or the toes lifted `toe_up` with the heel
    staying down, the whole foot `hop` off the floor. The foot pivots on the
    boot's own contact points (Rig.sole), and its sole is set outright: flat
    or tipped, never rolled. pos: model joints of the pose (fk)."""
    blen = lambda a, b: float(np.linalg.norm(rig.head[b] - rig.head[a]))
    slen = lambda a, b: float(np.linalg.norm(P[b] - P[a]))
    sole = rig.sole[sd]
    A0, T0, H0, f0 = rig.head[sd + "Foot"], sole["toe"], sole["heel"], sole["fwd"]
    up = np.array([0.0, 0.0, 1.0])
    lat = np.cross(up, f0)
    length = max(0.05, float(np.dot(T0 - H0, f0)))
    if toe_up > 0:                                         # on the heel, toes up
        phi, pivot = -math.asin(min(0.6, toe_up / length)), H0
    else:                                                  # on the ball of the foot, heel up
        phi, pivot = math.asin(min(0.7, heel / length)), T0
    f1 = f0 * math.cos(phi) - up * math.sin(phi)
    u1 = up * math.cos(phi) + f0 * math.sin(phi)
    Rp = np.outer(f1, f0) + np.outer(u1, up) + np.outer(lat, lat)
    yaw = math.radians(toe_deg)
    flat = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
    yaw0 = math.atan2(f0[0], -f0[1])
    Rz = np.array(Matrix.Rotation(yaw - yaw0, 3, "Z"))     # a turn about +Z carries -Y toward +X, as the yaw is measured
    Df = Rz @ Rp
    ankle = np.array([mark[0], mark[1], pivot[2] + float((Rp @ (A0 - pivot))[2]) + hop])
    # the knee bends over its own toes, pushed out by knee_out
    hint = flat + np.array([knee_out, 0.0, 0.25])
    d1, d2 = _ik_dirs(pos[sd + "UpperLeg"], ankle, blen(sd + "UpperLeg", sd + "LowerLeg"),
                      blen(sd + "LowerLeg", sd + "Foot"), hint)
    toe_keys = [k for k in (sd + "ToeBase", sd + "ToeBase_end") if k in P]
    toe_len = [slen(sd + "Foot", k) for k in toe_keys]
    l_thigh, l_shin = slen(sd + "UpLeg", sd + "Leg"), slen(sd + "Leg", sd + "Foot")
    P = dict(P)
    P["FitMark"] = np.zeros(3)                             # tells move_foot this leg was solved on the rig
    P[sd + "Leg"] = P[sd + "UpLeg"] + d1 * l_thigh
    P[sd + "Foot"] = P[sd + "Leg"] + d2 * l_shin
    toe = _norm(Df @ rig.dir[sd + "Foot"])
    for k, n in zip(toe_keys, toe_len):
        P[k] = P[sd + "Foot"] + toe * n
    P[sd + "Sole0"] = P[sd + "Foot"].copy()                # marker pair read by retarget: where the sole faces
    P[sd + "Sole"] = P[sd + "Foot"] + Df @ up
    return P


def plant_feet(rig, P, st, lead, stand_hips, free=None, step=0.6):
    """A captured pose stood on the fighter's own stance marks (D-075).

    The captured boxer punches from a base twice as wide as Kairo's stance,
    so every punch began with both feet jumping apart and ended with them
    sliding back. Here the capture keeps driving the pelvis, spine and arms,
    and the legs are solved on the real rig with the feet on the stance
    marks: the lead foot steps in with `step` of the body's forward travel,
    the rear foot stays and comes up on its toes when the hips leave it
    behind. `free`: a foot that is in the air (a kick) and is left alone."""
    ps = st["pose"]
    S = rig.hips_h / 0.95
    rear = "Right" if lead == "Left" else "Left"
    sgl = 1 if lead == "Left" else -1
    home_y = -ps.get("hips", (0.0, 0.0))[0] * S
    D, _h = retarget(rig, P, 1.0, ground=False)
    travel = home_y - P["Hips"][1]                         # + = the body has gone forward
    hips = np.array([P["Hips"][0], P["Hips"][1], pelvis_z(rig, P, st, stand_hips)])
    pos, _t = fk(rig, D, hips)
    for sd, key, sx, sy in ((lead, "lead", sgl, -1), (rear, "rear", -sgl, 1)):
        if sd == free:
            continue
        ax, al = ps[key + "_foot"]
        mark = np.array([sx * ax * S, sy * al * S])
        heel = ps.get(key + "_heel", 0.0) * S
        if sd == lead:
            mark[1] -= step * max(0.0, travel)
        else:
            # the rear leg lets its heel up as far as it has to, never more than 9 cm
            reach = float(np.linalg.norm(rig.head[sd + "LowerLeg"] - rig.head[sd + "UpperLeg"])
                          + np.linalg.norm(rig.head[sd + "Foot"] - rig.head[sd + "LowerLeg"])) * 0.99
            a = pos[sd + "UpperLeg"]
            flat_d = float(np.linalg.norm(a[:2] - mark))
            need = a[2] - math.sqrt(max(1e-6, reach * reach - flat_d * flat_d)) - rig.foot_h if flat_d < reach else 0.09
            heel = float(np.clip(max(heel, need), 0.0, 0.09 * S))
        P = solve_leg(rig, P, pos, sd, mark, ps.get(key + "_toe", 0.0) * sx, heel, 0.0, ps.get("knees", 0.0) * sx)
    return P


def steady(P, max_turn=70.0, max_side=18.0, max_forward=32.0, head_level=0.6):
    """Keeps a captured strike inside what reads as a fighter in control
    (D-075): the chest never turns further than `max_turn` from the opponent
    (a captured follow-through spun Kairo's back to them), the trunk leans at
    most `max_side` sideways and `max_forward` forward, and the head is
    brought `head_level` of the way back to upright so the eyes can stay on
    the target. The feet are re-planted afterwards (plant_feet)."""
    P = dict(P)
    o = np.array([P["Hips"][0], P["Hips"][1], 0.0])
    v = P["LeftArm"] - P["RightArm"]
    yaw = math.degrees(math.atan2(v[1], v[0]))
    over = yaw - max(-max_turn, min(max_turn, yaw))
    if abs(over) > 0.5:
        R = np.array(Matrix.Rotation(math.radians(-over), 3, "Z"))
        P = {k: R @ (p - o) + o for k, p in P.items()}
    t = P["Neck1"] - P["Hips"]
    fwd = math.degrees(math.atan2(-t[1], t[2]))
    sid = math.degrees(math.atan2(t[0], t[2]))
    f2, s2 = max(-max_forward, min(max_forward, fwd)), max(-max_side, min(max_side, sid))
    if abs(f2 - fwd) > 0.5 or abs(s2 - sid) > 0.5:
        want = _norm(np.array([math.tan(math.radians(s2)), -math.tan(math.radians(f2)), 1.0]))
        R = _swing(t, want)
        hp = P["Hips"].copy()
        for k in UPPER:
            if k in P:
                P[k] = R @ (P[k] - hp) + hp
    up = np.array([0.0, -0.12, 1.0])                       # upright, chin a touch down
    for a, b in (("Neck1", "Head"), ("Head", "Head_end")):
        d = P[b] - P[a]
        n = np.linalg.norm(d)
        new = _norm(_norm(d) * (1 - head_level) + _norm(up) * head_level) * n
        delta = (P[a] + new) - P[b]
        P[b] = P[b] + delta
        if b == "Head":
            P["Head_end"] = P["Head_end"] + delta
    return P


def eyes_on(P, keep=0.3):
    """The head stays on the opponent while the chest turns into a strike: it
    keeps `keep` of the chest's turn instead of all of it (a captured cross
    turned the face away from the target with the shoulders)."""
    v = P["LeftArm"] - P["RightArm"]
    a = math.atan2(v[1], v[0]) * keep
    P = dict(P)
    P["HeadSide0"] = P["Head"].copy()
    P["HeadSide"] = P["Head"] + np.array([math.cos(a), math.sin(a), 0.0])
    return P


def pelvis_z(rig, P, st, stand_hips):
    """Hip height on the model for a captured pose stood on the stance marks:
    as low as the capture crouches, never taller than the stance itself."""
    low = float(np.clip(P["Hips"][2] / stand_hips, 0.78, 1.0))
    return min(low, st["pose"].get("pelvis_h", 0.95)) * rig.hips_h


def reach_hand(rig, P, sd, wrist, weight, hips_z, elbow_out=0.25, from_head=False):
    """The arm solved on the real rig so the wrist is at `wrist` (model space),
    blended in by `weight`; written back into the source pose like solve_leg.
    The retarget alone leaves a punch short: the fighters' arms are not the
    captured performer's."""
    if weight <= 0:
        return P
    D, hips = retarget(rig, P, 1.0, ground=False)
    pos, _t = fk(rig, D, np.array([P["Hips"][0], P["Hips"][1], hips_z]))
    cur = pos[sd + "Hand"]
    if from_head:                                          # (across, forward, up) from the model's own head joint
        wrist = pos["Head"] + np.array([wrist[0], -wrist[1], wrist[2]], float)
    wrist = np.array([cur[0] * 0.5 if wrist[0] is None else wrist[0], wrist[1], wrist[2]], float)   # None: halfway to the centre line
    tgt = cur + (wrist - cur) * weight
    sx = 1 if sd == "Left" else -1
    l1 = float(np.linalg.norm(rig.head[sd + "LowerArm"] - rig.head[sd + "UpperArm"]))
    l2 = float(np.linalg.norm(rig.head[sd + "Hand"] - rig.head[sd + "LowerArm"]))
    d1, d2 = _ik_dirs(pos[sd + "UpperArm"], tgt, l1, l2, np.array([sx * elbow_out * 2.0, 0.15, -1.0]))
    keys = [k for k in (sd + "HandIndex1", sd + "HandIndex1_end", sd + "FingerBase", sd + "Thumb", sd + "Thumb_end",
                        sd[0] + "Thumb", sd[0] + "Thumb_end") if k in P]
    lens = [float(np.linalg.norm(P[k] - P[sd + "Hand"])) for k in keys]
    l_up = float(np.linalg.norm(P[sd + "ForeArm"] - P[sd + "Arm"]))
    l_fore = float(np.linalg.norm(P[sd + "Hand"] - P[sd + "ForeArm"]))
    old = _norm(P[sd + "Hand"] - P[sd + "ForeArm"])
    P = dict(P)
    P[sd + "ForeArm"] = P[sd + "Arm"] + d1 * l_up
    R = _swing(old, d2)
    hand0 = P[sd + "Hand"]
    P[sd + "Hand"] = P[sd + "ForeArm"] + d2 * l_fore
    for k, ln in zip(keys, lens):                          # knuckles in line with the forearm at full weight
        carried = R @ (P[k] - hand0)
        P[k] = P[sd + "Hand"] + _norm(carried * (1 - weight) + d2 * ln * weight) * ln
    P.pop(sd + "Palm", None)
    P.pop(sd + "Palm0", None)
    return P


def step_feet(rig, P, st, lead, off=None, lift=None, drop=0.0, heel=None, toe_up=None):
    """Both legs solved on the real rig with the feet moved from their stance
    marks (D-076): off[side] metres along the fight line (+ = toward the
    opponent), lift[side] metres off the floor, heel[side] / toe_up[side]
    metres the heel or the toes are rolled up, the pelvis `drop` metres
    below its stance height. Used for walks, dashes and crouching blocks of
    a fitted fighter, whose feet cannot be placed on the source skeleton."""
    ps = st["pose"]
    S = rig.hips_h / 0.95
    rear = "Right" if lead == "Left" else "Left"
    sgl = 1 if lead == "Left" else -1
    off, lift, heel, toe_up = off or {}, lift or {}, heel or {}, toe_up or {}
    D, _h = retarget(rig, P, 1.0, ground=False)
    pos, _t = fk(rig, D, np.array([P["Hips"][0], P["Hips"][1], ps.get("pelvis_h", 0.95) * rig.hips_h - drop]))
    for sd, key, sx, sy in ((lead, "lead", sgl, -1), (rear, "rear", -sgl, 1)):
        ax, al = ps[key + "_foot"]
        mark = np.array([sx * ax * S, sy * al * S - off.get(sd, 0.0)])
        P = solve_leg(rig, P, pos, sd, mark, ps.get(key + "_toe", 0.0) * sx,
                      max(ps.get(key + "_heel", 0.0) * S, heel.get(sd, 0.0)) if toe_up.get(sd, 0.0) <= 0 else 0.0,
                      lift.get(sd, 0.0), ps.get("knees", 0.0) * sx, toe_up=toe_up.get(sd, 0.0))
    return P


def trunk_clearance(rig, D, pos, q, pad=0.0):
    """How far point q (model space) is outside the fighter's trunk, in
    metres (negative = inside), the direction that leads out, and the point
    of the spine it was measured from. The trunk is an ellipse round the
    spine, as wide and as deep as the mesh (Rig.torso_rx / torso_ry), turned
    with the pelvis below and the chest above; `pad` thickens it."""
    best = None
    for a, b, bone, side in ((pos["Hips"], pos["Chest"], "Hips", "hips"), (pos["Chest"], pos["Neck"], "Chest", "shoulders")):
        ab = b - a
        t = float(np.dot(q - a, ab) / (np.dot(ab, ab) + 1e-12))
        if t < -0.15 or t > 1.1:                           # below the pelvis or above the collar: not beside the trunk
            continue
        c = a + ab * float(np.clip(t, 0.0, 1.0))
        o = (q - c) - _norm(ab) * float(np.dot(q - c, _norm(ab)))      # across the spine only
        lat = _norm(D[bone] @ rig.side0[side])
        sag = _norm(np.cross(_norm(ab), lat))
        u, v = float(np.dot(o, lat)), float(np.dot(o, sag))
        k = math.sqrt((u / (rig.torso_rx + pad)) ** 2 + (v / (rig.torso_ry + pad)) ** 2)
        dist = float(np.linalg.norm(o))
        clear = dist * (1.0 - 1.0 / k) if k > 1e-6 else -(rig.torso_ry + pad)
        if best is None or clear < best[0]:
            # outward: straight away from the spine, or to the front if it sits on it
            out = _norm(o) if dist > 1e-4 else -sag
            best = (clear, out, c)
    return best if best is not None else (1.0, np.array([0.0, -1.0, 0.0]), pos["Chest"])


def keep_hands_out(rig, P):
    """A wrist or forearm that has ended up inside the fighter's own trunk
    or head is pushed back out to the surface, on the real rig (D-077,
    D-078, D-080): poses keyed on the captured performer's build folded
    hands into bellies and ran forearms through chests. The body's size is
    the mesh's own (Rig.torso_rx, torso_ry, head_r)."""
    up = P["Neck1"] - P["Hips"]
    if up[2] < 0.6 * np.linalg.norm(up):                   # lying or falling: the floor and the body are meant to touch
        return P
    for _again in range(3):
        D, _h = retarget(rig, P, 1.0, ground=False)
        pos, tails = fk(rig, D, np.array([P["Hips"][0], P["Hips"][1], rig.hips_h]))
        moved = False
        for sd in ("Left", "Right"):
            w, e = pos[sd + "Hand"], pos[sd + "LowerArm"]
            clear, out, _c = trunk_clearance(rig, D, pos, w, pad=0.04)          # half a fist
            if clear < 0:
                P = reach_hand(rig, P, sd, w + _norm(out + np.array([0.0, -0.25, 0.0])) * (-clear + 0.01), 1.0, rig.hips_h)
                moved = True
                continue
            a, b = pos["Head"], tails["Head"]
            ab = b - a
            c = a + ab * float(np.clip(np.dot(w - a, ab) / (np.dot(ab, ab) + 1e-12), 0.0, 1.0))
            d = float(np.linalg.norm(w - c))
            if d < rig.head_r + 0.035:
                P = reach_hand(rig, P, sd, c + _norm((w - c) + np.array([0.0, -0.03, 0.0])) * (rig.head_r + 0.045), 1.0, rig.hips_h)
                moved = True
                continue
            worst = None                                   # the point of the forearm deepest in the trunk
            for f in (0.35, 0.55, 0.75):
                clear, out, _c = trunk_clearance(rig, D, pos, e + (w - e) * f, pad=0.025)   # half a forearm
                if clear < 0 and (worst is None or clear < worst[0]):
                    worst = (clear, out, f)
            if worst:
                clear, out, f = worst
                P = reach_hand(rig, P, sd, w + _norm(out + np.array([0.0, -0.25, 0.0])) * (-clear + 0.01) / f, 1.0, rig.hips_h)
                moved = True
        if not moved:
            break
    return P


def fit_stance(rig, P, st, lead, u=0.0):
    """Fits a posed stance to the fighter's own skeleton (D-075).

    The retarget copies bone directions, and no fighter has the proportions
    of the captured performer, so a foot or a fist placed on the source
    skeleton lands somewhere else on the model (one foot ended up 12 cm off
    the floor). Here the limbs are solved on the real rig instead: the pelvis
    is put at its blueprint height, both ankles on their floor marks, both
    wrists where the blueprint holds them from the model's own head, and the
    bone directions of that solution are written back into the pose. Lengths
    are in the fighter's own scale (x hip height / 0.95 m).

    `pose` keys read here: hips[0] (pelvis forward of the stance centre),
    pelvis_h (hip height as a share of standing), lead_foot / rear_foot,
    lead_toe / rear_toe, lead_heel / rear_heel, knees, lead_hand / rear_hand
    (across, forward, up from the model's head joint), lead_elbow /
    rear_elbow, lead_palm / rear_palm (in, out, down, up, forward, back, or a
    vector; "in" = toward the fighter's own centre line), lead_wrist /
    rear_wrist (degrees the fist is cocked back). Idle habits (STYLES bob,
    sway, tap) are applied here too, so planted feet stay exactly where they are."""
    ps = st["pose"]
    S = rig.hips_h / 0.95
    rear = "Right" if lead == "Left" else "Left"
    sgl = 1 if lead == "Left" else -1
    sway = st.get("sway", 0.0) * S * math.sin(2 * math.pi * u)
    bob = st.get("bob", 0.0) * S * 0.5 * (1 - math.cos(2 * math.pi * u * st.get("bob_beats", 1)))
    tap = st.get("tap", 0.0) * S * max(0.0, math.sin(2 * math.pi * u * 2)) ** 2
    P = shift(P, list(P.keys()), np.array([sway - P["Hips"][0], -ps.get("hips", (0.0, 0.0))[0] * S - P["Hips"][1], 0.0]))
    D, _h = retarget(rig, P, 1.0, ground=False)
    hips = np.array([P["Hips"][0], P["Hips"][1], ps.get("pelvis_h", 0.93) * rig.hips_h - bob])
    pos, _t = fk(rig, D, hips)
    blen = lambda a, b: float(np.linalg.norm(rig.head[b] - rig.head[a]))
    slen = lambda a, b: float(np.linalg.norm(P[b] - P[a]))
    for sd, key, sx, sy in ((lead, "lead", sgl, -1), (rear, "rear", -sgl, 1)):
        ax, al = ps[key + "_foot"]
        lift = ps.get(key + "_heel", 0.0) * S
        hop = tap if sd == lead else 0.0
        P = solve_leg(rig, P, pos, sd, np.array([sx * ax * S, sy * al * S]), ps.get(key + "_toe", 0.0) * sx,
                      lift, hop, ps.get("knees", 0.0) * sx)
    for sd, key, sx in ((lead, "lead", sgl), (rear, "rear", -sgl)):
        if key + "_hand" not in ps:
            continue
        ax, fw, up = ps[key + "_hand"]
        wrist = pos["Head"] + np.array([sx * ax, -fw, up]) * S
        e = ps.get(key + "_elbow", 0.35)
        d1, d2 = _ik_dirs(pos[sd + "UpperArm"], wrist, blen(sd + "UpperArm", sd + "LowerArm"),
                          blen(sd + "LowerArm", sd + "Hand"), np.array([sx * e * 2.0, 0.15, -1.0]))
        hand_keys = [k for k in (sd + "HandIndex1", sd + "HandIndex1_end", sd + "FingerBase", sd + "Thumb",
                                 sd + "Thumb_end", sd[0] + "Thumb", sd[0] + "Thumb_end") if k in P]
        hand_len = [slen(sd + "Hand", k) for k in hand_keys]
        l_up, l_fore = slen(sd + "Arm", sd + "ForeArm"), slen(sd + "ForeArm", sd + "Hand")
        P[sd + "ForeArm"] = P[sd + "Arm"] + d1 * l_up
        P[sd + "Hand"] = P[sd + "ForeArm"] + d2 * l_fore
        palm = ps.get(key + "_palm", "in")
        n = np.array(PALMS[palm] if isinstance(palm, str) else palm, float)
        if isinstance(palm, str) and palm in ("in", "out"):
            n = n * sx                                     # toward / away from the centre line
        n = _norm(n - d2 * np.dot(n, d2))
        cock = math.radians(ps.get(key + "_wrist", 0.0))   # fist cocked back, toward the back of the hand
        fingers = _norm(d2 * math.cos(cock) - n * math.sin(cock))
        n = _norm(n - fingers * np.dot(n, fingers))
        for k, ln in zip(hand_keys, hand_len):
            P[k] = P[sd + "Hand"] + fingers * ln
        P[sd + "Palm0"] = P[sd + "Hand"].copy()
        P[sd + "Palm"] = P[sd + "Hand"] + n
    return P


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
    "Chest": ("Spine1", "Neck1", "shoulders"), "Neck": ("Neck1", "Head", "neck"),
    "Head": ("Head", "Head_end", "head"),
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
        every = [b.name for b in arm_obj.data.bones]
        self.fingers = [n for n in every if any(f"Hand{fg}" in n for fg in FINGERS)]
        self.names = [n for n in every if n not in self.fingers]      # mocap-driven bones
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm_obj.data.bones}
        self.rest = {b.name: np.array(b.matrix_local) for b in arm_obj.data.bones}
        self.head = {b.name: np.array(b.head_local) for b in arm_obj.data.bones}
        self.tail = {b.name: np.array(b.tail_local) for b in arm_obj.data.bones}
        self.dir = {n: _norm(self.tail[n] - self.head[n]) for n in every}
        # Which way the rest shape itself is turned (D-075). The meshes are not
        # all modelled square to the front: Kairo's whole body is turned 35
        # degrees in his rest shape. The torso frames are measured against the
        # rest shape's own hip and shoulder lines, not against "+X is left".
        hp = self.head["LeftUpperLeg"] - self.head["RightUpperLeg"]
        sh = self.head["LeftUpperArm"] - self.head["RightUpperArm"]
        flat = lambda v: _norm(np.array([v[0], v[1], 0.0]))
        self.side0 = {"hips": flat(hp), "shoulders": flat(sh), "mid": flat(flat(hp) + flat(sh)),
                      "head": flat(sh), "neck": flat(sh)}
        self.rest_yaw = math.degrees(math.atan2(sh[1], sh[0]))
        # Which way each palm faces in the rest shape, from the knuckles (the
        # thumb side makes it handed, so it holds for any rest pose).
        self.palm0 = {}
        for side, hand in (("Left", -1.0), ("Right", 1.0)):
            i, q, w = (self.head.get(f"{side}HandIndex1"), self.head.get(f"{side}HandPinky1"), self.head[f"{side}Hand"])
            if i is not None and q is not None:
                self.palm0[side] = _norm(np.cross(i - w, q - w)) * hand
        self.auto_palm = False                 # build() turns it on for fighters with a fitted stance
        # How wide and how deep the trunk really is, and how big the head,
        # from the mesh itself (D-080): a fixed tube round the spine let
        # Seraphina's and Nox's hands sit inside their chest armour without
        # the checker noticing. The trunk is an ellipse round the spine:
        # torso_rx across the shoulders, torso_ry front to back.
        hh = float(self.head["Hips"][2])
        self.torso_rx, self.torso_ry, self.head_r = 0.16 * hh / 0.95, 0.115 * hh / 0.95, 0.10 * hh / 0.95
        try:
            lat = self.side0["shoulders"]
            sag = np.array([-lat[1], lat[0], 0.0])
            def off(p, a, b):
                ab = b - a
                return p - (a + ab * np.clip(np.dot(p - a, ab) / (np.dot(ab, ab) + 1e-12), 0.0, 1.0))
            us, vs, skull = [], [], []
            a0, a1, a2 = self.head["Hips"], self.head["Chest"], self.head["Neck"]
            h0, h1 = self.head["Head"], self.tail["Head"]
            for ob in arm_obj.children:
                if ob.type != "MESH":
                    continue
                gi = {g.index: g.name for g in ob.vertex_groups}
                for v in ob.data.vertices:
                    w = {gi[g.group]: g.weight for g in v.groups if g.group in gi}
                    co = np.array(ob.matrix_world @ v.co)
                    if w.get("Hips", 0) + w.get("Spine", 0) + w.get("Chest", 0) > 0.7 and a0[2] - 0.02 < co[2] < a2[2]:
                        o1, o2 = off(co, a0, a1), off(co, a1, a2)
                        o = o1 if np.linalg.norm(o1) < np.linalg.norm(o2) else o2
                        us.append(abs(float(np.dot(o, lat))))
                        vs.append(abs(float(np.dot(o, sag))))
                    elif w.get("Head", 0) > 0.8:
                        skull.append(float(np.linalg.norm(off(co, h0, h1))))
            if len(us) > 50:
                self.torso_rx, self.torso_ry = float(np.percentile(us, 95)), float(np.percentile(vs, 95))
            if len(skull) > 50:                 # hair and hoods reach far: the middle of the head, capped
                self.head_r = min(float(np.percentile(skull, 60)), 0.125 * hh / 0.95)
        except Exception as exc:                # measuring is a help, never a reason to fail the build
            print("[rig] body thickness not measured:", exc)
        # Where each boot really touches the floor (D-082): the ball of the
        # foot and the heel, from the mesh. The foot bone ends short of the
        # boot's toe, so a foot tipped onto its toes about the bone's end
        # pushed the boot through the floor; the build then lifted the whole
        # fighter until it cleared, and the other foot hung in the air.
        self.sole = {}
        for side in ("Left", "Right"):
            A = self.head[side + "Foot"]
            f = self.tail[side + "Foot"] - A
            f = _norm(np.array([f[0], f[1], 0.0]))
            toe = np.array([self.tail[side + "Foot"][0], self.tail[side + "Foot"][1], 0.0])
            heel = np.array([A[0], A[1], 0.0]) - f * 0.06
            try:
                pts = []
                for ob in arm_obj.children:
                    if ob.type != "MESH" or side + "Foot" not in ob.vertex_groups:
                        continue
                    gidx = ob.vertex_groups[side + "Foot"].index
                    for v in ob.data.vertices:
                        if any(g.group == gidx and g.weight > 0.5 for g in v.groups):
                            pts.append(np.array(ob.matrix_world @ v.co))
                if len(pts) > 30:
                    pts = np.array(pts)
                    along = (pts - A) @ f
                    lo, hi = float(along.min()), float(along.max())
                    floor = float(pts[:, 2].min())
                    front = pts[along > lo + 0.72 * (hi - lo)]
                    back = pts[along < lo + 0.25 * (hi - lo)]
                    front = front[front[:, 2] < front[:, 2].min() + 0.012]
                    back = back[back[:, 2] < back[:, 2].min() + 0.012]
                    toe = np.array([front[:, 0].mean(), front[:, 1].mean(), floor])
                    heel = np.array([back[:, 0].mean(), back[:, 1].mean(), floor])
            except Exception as exc:
                print("[rig] sole not measured:", exc)
            self.sole[side] = {"toe": toe, "heel": heel, "fwd": f}
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
    # a posed stance may say where the head faces (pose_stance); else it follows the chest
    # (a marker pair: both ends are carried along by every shift, so their difference stays the direction)
    side["head"] = P["HeadSide"] - P["HeadSide0"] if "HeadSide" in P else side["shoulders"]
    side["neck"] = side["head"] / np.linalg.norm(side["head"]) + side["shoulders"] / np.linalg.norm(side["shoulders"])
    D = {"Root": np.eye(3)}
    for name in rig.names:
        if name == "Root":
            continue
        if name in TORSO:
            a, b, s = TORSO[name]
            F = _frame(side[s], P[b] - P[a])
            # the rest torso is upright; which way it faces is measured (Rig.side0)
            R0 = _frame(rig.side0[s], rig.dir[name])
            D[name] = F @ R0.T
        elif name.endswith("Foot") and name[:-4] + "Sole" in P:
            # a foot solved on the rig (solve_leg): the sole faces where it was
            # put (flat, or tipped onto the ball of the foot), never rolled
            sd = name[:-4]
            a, b = LIMB[name]
            F = _frame(P[sd + "Sole"] - P[sd + "Sole0"], P[b] - P[a])
            R0 = _frame(np.array([0.0, 0.0, 1.0]), rig.dir[name])
            D[name] = F @ R0.T
        elif name.endswith("Hand") and name[:-4] in rig.palm0 and (name[:-4] + "Palm" in P or rig.auto_palm):
            # The hand's roll is set, not left to chance. A posed hand
            # (fit_stance) says where its palm faces. Otherwise (fitted
            # fighters, D-077) the palm follows the elbow like a relaxed
            # forearm: facing inward while the elbow is bent, turning palm-down
            # as the arm straightens into a punch. Left to the bare swing, the
            # roll differed by up to half a turn between poses and a blend
            # between them folded the wrist (152 degrees in Seraphina's defeat).
            sd = name[:-4]
            a, b = LIMB[name]
            if sd + "Palm" in P:
                n = P[sd + "Palm"] - P[sd + "Palm0"]
            else:
                h = np.cross(_norm(P[sd + "ForeArm"] - P[sd + "Arm"]), _norm(P[sd + "Hand"] - P[sd + "ForeArm"]))
                bend = float(np.linalg.norm(h))               # sine of the elbow's bend
                h = (h / bend if bend > 1e-4 else np.zeros(3)) * (1.0 if sd == "Left" else -1.0)
                w = min(1.0, bend / 0.5)
                n = h * w + np.array([0.0, 0.0, -1.0]) * (1.0 - w)
            F = _frame(n, P[b] - P[a])
            R0 = _frame(rig.palm0[name[:-4]], rig.dir[name])
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
    # an elbow or knee folds to 150 degrees at most (the limb cannot reach closer than that)
    closest = math.sqrt(l1 * l1 + l2 * l2 - 2 * l1 * l2 * math.cos(math.radians(30.0)))
    dist = np.clip(np.linalg.norm(d), closest, (l1 + l2) * 0.999)
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
    Q.pop(side + "Palm", None)                 # a posed palm does not survive the hand being moved
    Q.pop(side + "Palm0", None)
    # The hand goes with its forearm: moved rigidly it kept pointing where it
    # did before, which bent the wrist up to 110 degrees in the blocks (D-075).
    # The more the hand was moved, the straighter the wrist.
    fore = _norm(Q[side + "Hand"] - Q[side + "ForeArm"])
    R = _swing(P[side + "Hand"] - P[side + "ForeArm"], fore)
    for k in (side + "HandIndex1", side + "HandIndex1_end", side + "FingerBase", side + "Thumb", side + "Thumb_end",
              side[0] + "Thumb", side[0] + "Thumb_end"):
        if k in P:
            off = P[k] - cur
            carried = R @ off                                   # the old wrist angle, carried along
            straight = fore * np.linalg.norm(off)
            w = min(1.0, max(0.0, weight)) if k.endswith(("Index1", "Index1_end", "FingerBase")) else 0.0
            Q[k] = Q[side + "Hand"] + _norm(carried * (1 - w) + straight * w) * np.linalg.norm(off)
    return Q


def move_foot(P, side, target, weight=1.0, knee_out=0.0):
    if weight <= 0:
        return P
    cur = P[side + "Foot"]
    tgt = cur + (np.array(target) - cur) * weight
    # knees point forward (-Y), or out to the fighter's own side by knee_out
    pole = P[side + "Leg"] + np.array([(1 if side == "Left" else -1) * knee_out, -0.4, 0.0])
    if "FitMark" in P:
        # a leg solved on the real rig (solve_leg) keeps bending the way it does:
        # over its own toes, not straight ahead (D-077)
        hip, knee, ank = P[side + "UpLeg"], P[side + "Leg"], P[side + "Foot"]
        line = ank - hip
        off = (knee - hip) - line * float(np.dot(knee - hip, line) / (np.dot(line, line) + 1e-12))
        if np.linalg.norm(off) > 0.02:
            pole = knee + _norm(off) * 0.4
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

    rig = None                        # set by build(): the skeleton being animated

    @staticmethod
    def blend(a, b, t):
        """Blend two poses the way they were built (D-077): torso bones turn
        between their two orientations; every limb bone's *direction* is
        swept between its two directions and the bone is then swung onto it
        from its parent, exactly as retarget() does; a hand turns between its
        two angles against its forearm.
        Blending each bone's world rotation on its own let a forearm and its
        hand take different routes: half way through Kairo's and Seraphina's
        defeat the wrist was folded 120 degrees though neither pose bent it."""
        def turn(Ra, Rb):
            qa, qb = Matrix(Ra.tolist()).to_quaternion(), Matrix(Rb.tolist()).to_quaternion()
            return np.array(qa.slerp(qb, t).to_matrix())
        rig = Pose.rig
        D = {}
        if rig is None:
            for n in a.D:
                D[n] = turn(a.D[n], b.D[n])
            return Pose(D, a.hips * (1 - t) + b.hips * t)
        for n in rig.names:
            if n not in a.D:
                continue
            p = rig.parent.get(n)
            if n in TORSO or p is None or p not in D or n not in LIMB:
                D[n] = turn(a.D[n], b.D[n])
            elif n.endswith("Hand") or n.endswith("Foot"):
                D[n] = D[p] @ turn(a.D[p].T @ a.D[n], b.D[p].T @ b.D[n])
            else:
                da, db = a.D[n] @ rig.dir[n], b.D[n] @ rig.dir[n]
                ang = math.acos(float(np.clip(np.dot(da, db), -1.0, 1.0)))
                if ang < 1e-4:
                    d = da
                else:                                       # great-arc sweep from da to db
                    d = (math.sin((1 - t) * ang) * da + math.sin(t * ang) * db) / math.sin(ang)
                D[n] = _swing(D[p] @ rig.dir[n], d) @ D[p]
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


# --------------------------------------------------------------------------- hands

FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")
# Joint angles (degrees, knuckle -> tip) of a closed fist. The thumb folds
# across the front of the fingers instead of into the palm.
FIST = {"finger": (78.0, 95.0, 62.0), "thumb": (22.0, 26.0, 48.0)}

# Hand shape per fighter (0 = open palm, 1 = fist) as (left, right), and the
# actions that override it. The capture has no finger data, so hands are
# posed per action: boxers keep fists, palm strikers keep open hands.
HANDS = {
    "kairo": (1.0, 1.0), "drakon": (1.0, 1.0), "seraphina": (0.2, 0.9),
    "nox": (0.3, 0.3), "vexa": (0.9, 0.9), "ryuen": (0.08, 0.08),
}
HANDS_BY_ACTION = {
    "SPECIAL_ORIGIN_PALM": (0.05, 0.05),         # open-palm strike
    "KNOCKDOWN": (0.35, 0.35), "GETUP": (0.35, 0.35), "DEFEAT": (0.3, 0.3),
    "SPECIAL_ANVIL_SLAM": (0.45, 0.45),          # grabbing hands
    # Nox: spear hands (straight fingers), a closed fist only for the backfist
    "ATTACK_FANG_JAB_01": (0.03, 0.3), "SPECIAL_THROAT_PIERCE": (0.3, 0.03), "ULTIMATE_ECLIPSE": (0.03, 0.03),
    "ATTACK_RISING_BACKFIST_01": (0.3, 1.0),
    # Vexa: the cyber hand opens to fire; the shield hand is a flat blade
    "SPECIAL_PULSE_SHOT": (0.08, 0.9), "SPECIAL_ARC_GUARD": (0.15, 0.9),
    # Ryuen: open palms throughout, fists only for the chain punches, closing hands for the throw
    "ATTACK_CHAIN_PUNCH_01": (0.95, 0.95), "ULTIMATE_THOUSAND_RIVERS_STRIKE": (0.8, 0.8),
    "SPECIAL_WRIST_THROW": (0.5, 0.5),
}


def finger_axes(rig):
    """{finger bone: (curl axis in the bone's rest frame, thumb?)}.
    The palm normal comes from the knuckle positions, so it works for any
    rest pose with the palms facing the floor (T-pose)."""
    out = {}
    for side in ("Left", "Right"):
        mine = [n for n in rig.fingers if n.startswith(side)]
        k1 = {fg: rig.head[f"{side}Hand{fg}1"] for fg in FINGERS if f"{side}Hand{fg}1" in rig.head}
        if len([fg for fg in k1 if fg != "Thumb"]) < 2:
            continue
        wrist = rig.head[f"{side}Hand"]
        order = [fg for fg in FINGERS[1:] if fg in k1]
        palm = _norm(np.cross(k1[order[0]] - wrist, k1[order[-1]] - wrist))
        if palm[2] > 0:
            palm = -palm                         # points out of the palm (down in a T-pose)
        centre = np.mean([k1[fg] for fg in order], 0)
        for n in mine:
            d = rig.dir[n]
            thumb = "Thumb" in n
            toward = _norm(_norm(centre - rig.head[n]) + palm) if thumb else palm
            axis = _norm(np.cross(d, toward))
            out[n] = (rig.rest[n][:3, :3].T @ axis, thumb)
    return out


def key_fingers(rig, act, curls):
    """curls: one (left, right) curl per frame, 0 open .. 1 fist."""
    obj = rig.obj
    obj.animation_data.action = act
    axes = finger_axes(rig)
    last = None
    for f, (cl, cr) in enumerate(curls):
        if last == (cl, cr) and 0 < f < len(curls) - 1:
            continue
        last = (cl, cr)
        for n, (axis, thumb) in axes.items():
            c = cl if n.startswith("Left") else cr
            ang = FIST["thumb" if thumb else "finger"][int(n[-1]) - 1] * c
            pb = obj.pose.bones[n]
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = Quaternion(Vector(axis.tolist()), math.radians(ang))
            pb.keyframe_insert("rotation_quaternion", frame=f)


def hand_curls(fid, action, n):
    """Per-frame hand shape of one action; blends from and back to the
    fighter's own hand shape over 5 frames so cuts between actions match."""
    base = HANDS.get(fid, (1.0, 1.0))
    tgt = HANDS_BY_ACTION.get(action)
    if tgt is None:
        return [base] * n
    out = []
    for f in range(n):
        w = ease(min(f, n - 1 - f) / 5.0)
        out.append(tuple(round(b + (t - b) * w, 3) for b, t in zip(base, tgt)))
    return out


# --------------------------------------------------------------------------- keyed moves

def track(t, keys):
    """Value at frame t of a keyed track [(frame, value), ...], eased between keys."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if t <= f1:
            w = ease((t - f0) / max(1e-6, f1 - f0))
            return v0 + (v1 - v0) * w
    return keys[-1][1]


BODY = UPPER + ["Hips", "LHipJoint", "RHipJoint", "LeftUpLeg", "RightUpLeg"]


def sink(P, base, depth):
    """Lower the body by `depth`, feet stay where they are in `base` (knees bend)."""
    P = shift(P, BODY, np.array([0, 0, -depth]))
    for sd in ("Left", "Right"):
        P = move_foot(P, sd, base[sd + "Foot"])
    return P


def frames_of(mv):
    total = mv["startup"] + mv["active"] - 1 + mv["recovery"]
    return total, mv["startup"] - 1, mv["startup"] + mv["active"] - 2     # total, first / last active index


def drakon_set(c):
    """Drakon: Ironclad. Heavy boxing and wrestling. Everything except the
    haymaker (a captured wide rear swing) is keyed from his own guard: no
    capture of hammer blows, tackles or grabs exists in the library."""
    H, G, moves, pose_of, box = c["H"], c["guard_P"], c["moves"], c["pose_of"], c["box"]
    v = lambda x, y, z: np.array([x, y, z]) * H          # noqa: E731  body-relative offsets
    gl, gr, head = G["LeftHand"], G["RightHand"], G["Head"]
    lf, rf = G["LeftFoot"], G["RightFoot"]
    out = {}

    def keyed(mv, fn):
        total, a0, a1 = frames_of(mv)
        poses = [pose_of(fn(t, total, a0, a1), box) for t in range(total)]
        for t in range(max(0, total - 6), total):
            poses[t] = Pose.blend(poses[t], c["guard"], ease((t - (total - 6)) / 6))
        return poses

    def hit_point(mv, side_x=0.0, dz=0.0):
        return np.array([side_x * H, -mv["hc"][0], mv["hc"][1] + dz * H])

    # Hammer Fist: lead gauntlet lifts above the head and drops like a hammer
    mv = moves["hammer_fist"]
    def hammer(t, total, a0, a1, mv=mv):
        hand = track(t, [(0, gl), (max(1, a0 - 3), head + v(0.1, 0.02, 0.2)), (a0, hit_point(mv, 0.03)),
                         (a1, hit_point(mv, 0.03, -0.04)), (total - 1, gl)])
        P = sink(G, G, track(t, [(0, 0.0), (a0, 0.05 * H), (a1, 0.05 * H), (total - 1, 0.0)]))
        P = lean(P, track(t, [(0, 0.0), (max(1, a0 - 3), 7.0), (a0, -15.0), (a1, -15.0), (total - 1, 0.0)]))
        return move_hand(P, "Left", hand, 1.0, pole_out=0.5)
    out[c["anim_of"](mv)] = keyed(mv, hammer)

    # Haymaker: the captured wide rear swing, with a long wind-up
    mv = moves["haymaker"]
    out[c["anim_of"](mv)] = c["strike"](box, 2436, "Right", "hand", mv, pre=40, post=50, blend_in=5,
                                        extra=lambda P, t, T: lean(P, -9 * math.sin(math.pi * min(1, t / T))))

    # Shoulder Check: drops behind the lead shoulder and rams it forward
    mv = moves["shoulder_check"]
    def check(t, total, a0, a1):
        w = track(t, [(0, 0.0), (a0, 1.0), (a1, 1.0), (total - 1, 0.0)])
        chest = G["Head"] - v(0, 0, 0.3)
        P = sink(G, G, 0.07 * H * w)
        P = lean(P, track(t, [(0, 0.0), (4, 6.0), (a0, -30.0), (a1, -30.0), (total - 1, 0.0)]), roll_deg=14 * w)
        P = move_hand(P, "Left", gl + (chest + v(0.1, -0.12, -0.02) - gl) * w, 1.0, pole_out=0.5)
        return move_hand(P, "Right", gr + (chest + v(-0.08, -0.08, -0.04) - gr) * w, 1.0, pole_out=0.3)
    out[c["anim_of"](mv)] = keyed(mv, check)

    # Stomp: the knee comes up high, then the boot drives down at shin height
    mv = moves["stomp"]
    def stomp(t, total, a0, a1, mv=mv):
        down = np.array([rf[0], -mv["hc"][0] + 0.08, mv["hc"][1] * 0.5])
        foot = track(t, [(0, rf), (a0 - 5, rf + v(0, -0.14, 0.4)), (a0, down), (a1, down), (a1 + 9, rf), (total - 1, rf)])
        P = lean(G, track(t, [(0, 0.0), (a0 - 5, 7.0), (a0, -12.0), (a1, -12.0), (total - 1, 0.0)]))
        return move_foot(P, "Right", foot)
    out[c["anim_of"](mv)] = keyed(mv, stomp)

    # Forge Charge: head down behind the lead shoulder, driving steps (the
    # game moves him across the floor on frames 5..20)
    mv = moves["forge_charge"]
    def charge(t, total, a0, a1):
        w = track(t, [(0, 0.0), (5, 1.0), (a1, 1.0), (total - 1, 0.0)])
        run = track(t, [(0, 0.0), (5, 1.0), (a1 - 2, 1.0), (a1 + 4, 0.0), (total - 1, 0.0)])
        chest = G["Head"] - v(0, 0, 0.3)
        P = shift(G, BODY, np.array([0, 0, -0.11 * H * w]))
        for sd, ph, base in (("Left", 0.0, lf), ("Right", math.pi, rf)):
            a = 2 * math.pi * t / 12.0 + ph
            P = move_foot(P, sd, base + v(0, -0.13 * math.cos(a), 0.11 * max(0.0, math.sin(a))) * run)
        P = lean(P, -34 * w, roll_deg=10 * w)
        P = move_hand(P, "Left", gl + (chest + v(0.12, -0.16, -0.04) - gl) * w, 1.0, pole_out=0.5)
        return move_hand(P, "Right", gr + (chest + v(-0.1, -0.04, -0.1) - gr) * w, 1.0, pole_out=0.3)
    out[c["anim_of"](mv)] = keyed(mv, charge)

    # Anvil Slam: two-hand collar grab, then the opponent is driven to the floor
    mv = moves["anvil_slam"]
    def slam(t, total, a0, a1, mv=mv):
        d = a1 + 9                                           # the opponent hits the floor
        drive = track(t, [(0, 0.0), (a1, 0.0), (d, 1.0), (d + 9, 1.0), (total - 1, 0.0)])
        P = sink(G, G, 0.17 * H * drive)
        P = lean(P, track(t, [(0, 0.0), (a0, -8.0), (a1, -8.0), (d, -46.0), (d + 9, -46.0), (total - 1, 0.0)]))
        for sd, sg, g in (("Left", 1, gl), ("Right", -1, gr)):
            grab = hit_point(mv, 0.09 * sg, 0.04)
            floor = np.array([0.11 * sg * H, -mv["hc"][0] - 0.1 * H, 0.28 * H])
            hand = track(t, [(0, g), (a0, grab), (a1, grab), (d, floor), (d + 9, floor), (total - 1, g)])
            P = move_hand(P, sd, hand, 1.0, pole_out=0.45)
        return P
    out[c["anim_of"](mv)] = keyed(mv, slam)

    # Quake Stomp: both gauntlets go overhead, then hammer the floor
    mv = moves["quake_stomp"]
    def quake(t, total, a0, a1):
        up = a0 - 7
        P = sink(G, G, track(t, [(0, 0.0), (up, 0.0), (a0, 0.27 * H), (a1 + 6, 0.27 * H), (total - 1, 0.0)]))
        P = lean(P, track(t, [(0, 0.0), (up, 9.0), (a0, -52.0), (a1 + 6, -52.0), (total - 1, 0.0)]))
        for sd, sg, g in (("Left", 1, gl), ("Right", -1, gr)):
            floor = v(0.12 * sg, -0.42, 0.1)
            hand = track(t, [(0, g), (up, head + v(0.1 * sg, -0.02, 0.26)), (a0, floor), (a1 + 6, floor), (total - 1, g)])
            P = move_hand(P, sd, hand, 1.0, pole_out=0.5)
        return P
    out[c["anim_of"](mv)] = keyed(mv, quake)

    # Molten Colossus: grab, slam to the floor, three hammer blows into the
    # fallen opponent, then he straightens up over them
    mv = moves["molten_colossus"]
    def colossus(t, total, a0, a1, mv=mv):
        d = a1 + 8
        blows = [d + 10, d + 20, d + 30]                     # impact frames, alternating hands
        end = blows[-1] + 5
        P = sink(G, G, track(t, [(0, 0.0), (a1, 0.0), (d, 0.19 * H), (end, 0.19 * H), (total - 1, 0.0)]))
        P = lean(P, track(t, [(0, 0.0), (a0, -8.0), (a1, -8.0), (d, -46.0), (end, -46.0), (total - 1, 0.0)]))
        for sd, sg, g in (("Left", 1, gl), ("Right", -1, gr)):
            grab = hit_point(mv, 0.09 * sg, 0.04)
            floor = np.array([0.1 * sg * H, -mv["hc"][0] - 0.08 * H, 0.26 * H])
            high = floor + v(0.04 * sg, 0.12, 0.5)
            keys = [(0, g), (a0, grab), (a1, grab), (d, floor)]
            for k, b in enumerate(blows):
                if (k % 2 == 0) == (sd == "Right"):          # right, left, right
                    keys += [(b - 6, high), (b, floor)]
            keys += [(end, floor), (total - 1, g)]
            P = move_hand(P, sd, track(t, keys), 1.0, pole_out=0.45)
        return P
    out[c["anim_of"](mv)] = keyed(mv, colossus)
    return out


def turn(P, deg):
    """Spin the whole figure about the vertical axis through the hips."""
    R = np.array(Matrix.Rotation(math.radians(deg), 3, "Z"))
    o = np.array([P["Hips"][0], P["Hips"][1], 0.0])
    return {k: R @ (v - o) + o for k, v in P.items()}


def hump(t, t0, t1):
    """0 outside t0..t1, a smooth arc (peak 1) between."""
    if t <= t0 or t >= t1:
        return 0.0
    return math.sin(math.pi * (t - t0) / (t1 - t0))


def seraphina_set(c):
    """Seraphina: Skyblade. Taekwondo / karate kicker. The side kick,
    roundhouse and rising kick are captured kicks (CMU 143_24, 86_08, 135_04),
    aimed so the kicking leg points at the opponent; the knife-hand, sweep,
    dive and the airborne part of the ultimate are keyed from her guard."""
    H, G, moves, pose_of, box = c["H"], c["guard_P"], c["moves"], c["pose_of"], c["box"]
    v = lambda x, y, z: np.array([x, y, z]) * H          # noqa: E731
    gl, gr = G["LeftHand"], G["RightHand"]
    lf, rf = G["LeftFoot"], G["RightFoot"]
    side_c, round_c, rise_c = c["clip"]("143_24"), c["clip"]("86_08"), c["clip"]("135_04")
    out = {}

    def aim(cl, peak, side):
        d = (cl.at(peak)[side + "Foot"] - cl.at(peak)["Hips"])[:2]
        return d / (np.linalg.norm(d) + 1e-9)

    def keyed(mv, fn, lift=None):
        total, a0, a1 = frames_of(mv)
        poses = []
        for t in range(total):
            P = fn(t, total, a0, a1)
            pose = pose_of(P, box)
            up = lift(t) if lift else 0.0
            if up > 0.005:
                pose = Pose(pose.D, pose.hips + np.array([0, 0, up]))
            poses.append(pose)
        for t in range(max(0, total - 6), total):
            poses[t] = Pose.blend(poses[t], c["guard"], ease((t - (total - 6)) / 6))
        return poses

    # Knife-hand: the extended lead hand flicks out and back along one line
    mv = moves["knife_hand"]
    def knife(t, total, a0, a1, mv=mv):
        hit = np.array([0.02 * H, -mv["hc"][0], mv["hc"][1]])
        P = lean(G, track(t, [(0, 0.0), (a0, -5.0), (a1, -5.0), (total - 1, 0.0)]))
        return move_hand(P, "Left", track(t, [(0, gl), (a0, hit), (a1, hit), (total - 1, gl)]), 1.0)
    out[c["anim_of"](mv)] = keyed(mv, knife)

    # Side Kick and Roundhouse: captured, turned so the leg points at the opponent
    mv = moves["side_kick"]
    out[c["anim_of"](mv)] = c["strike"](side_c, 294, "Left", "foot", mv, pre=30, post=40, blend_in=4,
                                        aim=aim(side_c, 294, "Left"))
    mv = moves["roundhouse"]
    out[c["anim_of"](mv)] = c["strike"](round_c, 4061, "Right", "foot", mv, pre=36, post=44, blend_in=4,
                                        aim=aim(round_c, 4061, "Right"))

    # Low Sweep: drops low, the lead leg scythes across the floor
    mv = moves["low_sweep"]
    def sweep(t, total, a0, a1, mv=mv):
        P = sink(G, G, track(t, [(0, 0.0), (a0 - 3, 0.26 * H), (a1 + 3, 0.26 * H), (total - 1, 0.0)]))
        P = lean(P, track(t, [(0, 0.0), (a0, -18.0), (a1, -18.0), (total - 1, 0.0)]))
        foot = track(t, [(0, lf), (a0 - 4, lf + v(0.2, 0.08, 0.03)), (a0, np.array([0.12 * H, -mv["hc"][0], 0.07])),
                         (a1, np.array([-0.16 * H, -mv["hc"][0] + 0.12, 0.07])), (a1 + 8, lf), (total - 1, lf)])
        return move_foot(P, "Left", foot)
    out[c["anim_of"](mv)] = keyed(mv, sweep)

    # Crescent Arc: the captured rising kick, thrown from a jump
    mv = moves["crescent_arc"]
    total, a0, a1 = frames_of(mv)
    name = c["anim_of"](mv)
    out[name] = c["strike"](rise_c, 584, "Left", "foot", mv, pre=30, post=44, blend_in=3,
                            lift=lambda t, a0=a0, a1=a1: 0.26 * H * hump(t, a0 - 4, a1 + 9))
    c["air"](name, a0 - 3, a1 + 8)

    # Halo Step: leans away as she slides back (the game moves her), then the side kick
    mv = moves["halo_step"]
    out[c["anim_of"](mv)] = c["strike"](side_c, 294, "Left", "foot", mv, pre=34, post=40, blend_in=3,
                                        aim=aim(side_c, 294, "Left"),
                                        extra=lambda P, t, T: lean(P, 15 * hump(t, 1, 13)))

    # Seraph Dive: hops forward (the game carries her) and comes down heel first
    mv = moves["seraph_dive"]
    total, a0, a1 = frames_of(mv)
    def dive(t, total, a0, a1, mv=mv):
        heel = np.array([rf[0], -mv["hc"][0] + 0.05, 0.5])
        P = lean(G, track(t, [(0, 0.0), (5, 8.0), (a0, -16.0), (a1, -16.0), (total - 1, 0.0)]))
        P = move_foot(P, "Left", lf + v(0, 0.06, 0.2) * hump(t, 2, a0 + 3))
        return move_foot(P, "Right", track(t, [(0, rf), (7, rf + v(0, -0.06, 0.2)), (a0, heel), (a1, heel),
                                               (a1 + 7, rf), (total - 1, rf)]))
    name = c["anim_of"](mv)
    out[name] = keyed(mv, dive, lift=lambda t, a0=a0: 0.36 * H * hump(t, 2, a0 + 2))
    c["air"](name, 3, a0 + 1)

    # Radiant Ascension: rising kick, two spinning kicks in the air, axe kick down
    mv = moves["radiant_ascension"]
    total, a0, a1 = frames_of(mv)
    first = c["strike"](rise_c, 584, "Left", "foot", mv, pre=26, post=20, blend_in=2)
    up0, land = a1 + 2, total - 9                     # leaves the floor / axe kick lands
    def ascend(t, total, a0, a1):
        u = (t - up0) / max(1, land - 4 - up0)                    # 0..1 over the spins
        spin = 720.0 * ease(min(1.0, max(0.0, u)))
        leg_out = hump(t, up0, land - 3)
        P = move_foot(G, "Right", rf + v(-0.05, -0.36, 0.5) * leg_out)       # kicking leg held out
        P = move_foot(P, "Left", lf + v(0, 0.05, 0.22) * leg_out)            # other leg tucked
        P = turn(P, spin)
        axe = track(t, [(0, 0.0), (land - 6, 0.0), (land - 3, 1.0), (land, 0.0), (total - 1, 0.0)])
        if axe > 0 and t >= land - 6:
            P = move_foot(P, "Left", lf + v(0, -0.3, 0.75) * axe)            # leg whips up, then drops
        return P
    air_pose = keyed(mv, ascend, lift=lambda t: 0.5 * H * hump(t, up0 - 1, land))
    seq = first[:up0] + air_pose[up0:]
    for k in range(3):                                # ease from the captured kick into the air phase
        seq[up0 + k] = Pose.blend(first[min(len(first) - 1, up0 + k)], air_pose[up0 + k], (k + 1) / 4.0)
    name = c["anim_of"](mv)
    out[name] = seq
    c["air"](name, up0, land - 1)
    return out


def nox_set(c):
    """Nox: Umbral Fang. Ninjutsu movement, Silat strikes; low and deceptive.
    Entirely keyed from his own crouched guard: the library has no capture
    of spear hands, sweeps from the floor or spinning backfists."""
    H, G, moves, pose_of, box = c["H"], c["guard_P"], c["moves"], c["pose_of"], c["box"]
    v = lambda x, y, z: np.array([x, y, z]) * H          # noqa: E731
    gl, gr = G["LeftHand"], G["RightHand"]
    lf, rf = G["LeftFoot"], G["RightFoot"]
    hips = G["Hips"]
    out = {}

    def keyed(mv, fn, lift=None):
        total, a0, a1 = frames_of(mv)
        poses = []
        for t in range(total):
            pose = pose_of(fn(t, total, a0, a1), box)
            up = lift(t) if lift else 0.0
            if up > 0.005:
                pose = Pose(pose.D, pose.hips + np.array([0, 0, up]))
            poses.append(pose)
        for t in range(max(0, total - 6), total):
            poses[t] = Pose.blend(poses[t], c["guard"], ease((t - (total - 6)) / 6))
        return poses

    def hit_point(mv, x=0.0, dz=0.0):
        return np.array([x * H, -mv["hc"][0], mv["hc"][1] + dz * H])

    # Fang Jab: a spear-hand flick from the low guard up to the throat
    mv = moves["fang_jab"]
    def jab(t, total, a0, a1, mv=mv):
        tip = hit_point(mv, 0.02, 0.05)
        return move_hand(G, "Left", track(t, [(0, gl), (a0, tip), (a1, tip), (total - 1, gl)]), 1.0, pole_out=0.15)
    out[c["anim_of"](mv)] = keyed(mv, jab)

    # Rising Backfist: coils lower, then uncoils through a full turn into a backfist
    mv = moves["rising_backfist"]
    def backfist(t, total, a0, a1, mv=mv):
        P = sink(G, G, track(t, [(0, 0.0), (3, 0.08 * H), (a0, -0.06 * H), (a1, -0.06 * H), (total - 1, 0.0)]))
        P = turn(P, 360.0 * ease(min(1.0, t / float(a0))))
        fist = hit_point(mv, -0.04, 0.02)
        return move_hand(P, "Right", track(t, [(0, gr), (a0 - 3, P["RightArm"] + v(-0.2, 0.05, 0.0)), (a0, fist),
                                               (a1, fist), (total - 1, gr)]), 1.0 if t >= a0 - 3 else 0.0, pole_out=0.5)
    out[c["anim_of"](mv)] = keyed(mv, backfist)

    # Scythe Sweep: drops onto one hand, the rear leg scythes at ankle height
    def sweep_pose(P, t, s0, s1, mv):
        """Hand on the floor and the sweeping leg, between frames s0 (start) and s1 (end of the arc)."""
        down = track(t, [(s0 - 5, 0.0), (s0, 1.0), (s1 + 3, 1.0), (s1 + 10, 0.0)])
        P = sink(P, G, 0.3 * H * down)
        P = lean(P, -30 * down, roll_deg=18 * down)
        P = move_hand(P, "Left", gl + (np.array([0.26 * H, -0.12 * H, 0.06]) - gl) * down, 1.0, pole_out=0.4)
        arc = track(t, [(s0 - 5, rf), (s0 - 1, rf + v(-0.22, -0.05, 0.02)), (s0, np.array([-0.14 * H, -mv["hc"][0], 0.07])),
                        (s1, np.array([0.18 * H, -mv["hc"][0] + 0.1, 0.07])), (s1 + 9, rf)])
        return move_foot(P, "Right", arc)
    mv = moves["scythe_sweep"]
    out[c["anim_of"](mv)] = keyed(mv, lambda t, total, a0, a1, mv=mv: sweep_pose(G, t, a0, a1, mv))

    # Drop Heel: a small hop, the heel goes up over the head and chops down
    def heel_up(P, t, top, mv, drop=None):
        """Right leg rising to its peak at frame `top`; with `drop`, the chop lands there."""
        peak = np.array([rf[0], -0.42 * H, 0.92 * H])
        keys = [(0, rf), (top, peak)]
        if drop is not None:
            keys += [(drop, np.array([rf[0], -mv["hc"][0] + 0.05, mv["hc"][1] - 0.1])), (drop + 3, np.array(
                [rf[0], -mv["hc"][0] + 0.05, mv["hc"][1] - 0.2])), (drop + 11, rf)]
        return move_foot(lean(P, 10 * hump(t, 0, top + 4)), "Right", track(t, keys))
    mv = moves["drop_heel"]
    total, a0, a1 = frames_of(mv)
    name = c["anim_of"](mv)
    out[name] = keyed(mv, lambda t, total, a0, a1, mv=mv: heel_up(G, t, a0 - 5, mv, drop=a0),
                      lift=lambda t, a0=a0: 0.12 * H * hump(t, 3, a0 + 1))
    c["air"](name, 4, a0)

    # Feint Fang: the same rise as the Drop Heel, abandoned for the sweep
    mv = moves["feint_fang"]
    total, a0, a1 = frames_of(mv)
    def feint(t, total, a0, a1, mv=mv):
        fake = 12                                         # frames of the false overhead
        if t <= fake:
            return heel_up(G, t, fake, mv)
        P = sweep_pose(G, t, a0, a1, mv)
        w = ease(min(1.0, (t - fake) / 5.0))              # the raised leg is pulled back under him
        up = heel_up(G, fake, fake, mv)
        return {k: up[k] * (1 - w) + P[k] * w for k in P}
    out[c["anim_of"](mv)] = keyed(mv, feint)

    # Shade Step: a low glide (the game carries him through the opponent)
    mv = moves["shade_step"]
    def glide(t, total, a0, a1):
        w = track(t, [(0, 0.0), (4, 1.0), (14, 1.0), (total - 1, 0.0)])
        P = shift(G, BODY, np.array([0, 0, -0.14 * H * w]))
        for sd, ph, base in (("Left", 0.0, lf), ("Right", math.pi, rf)):
            a = 2 * math.pi * t / 10.0 + ph
            P = move_foot(P, sd, base + v(0, -0.16 * math.cos(a), 0.05 * max(0.0, math.sin(a))) * w)
        P = lean(P, -42 * w)
        P = move_hand(P, "Left", gl + (hips + v(0.2, 0.22, 0.02) - gl) * w, 1.0, pole_out=0.3)     # arms trail behind
        return move_hand(P, "Right", gr + (hips + v(-0.2, 0.24, 0.0) - gr) * w, 1.0, pole_out=0.3)
    out[c["anim_of"](mv)] = keyed(mv, glide)

    # Throat Pierce: long gliding lunge, rear spear-hand driven out at the end
    mv = moves["throat_pierce"]
    def pierce(t, total, a0, a1, mv=mv):
        w = track(t, [(0, 0.0), (3, 1.0), (a1, 1.0), (total - 1, 0.0)])
        P = sink(G, G, 0.1 * H * w)
        P = move_foot(P, "Left", lf + v(0, -0.2, 0.0) * w)                    # deep front stride
        P = move_foot(P, "Right", rf + v(0, 0.16, 0.0) * w)
        P = lean(P, -30 * w)
        tip = hit_point(mv, -0.02, 0.0)
        P = move_hand(P, "Right", track(t, [(0, gr), (a0 - 4, hips + v(-0.16, 0.05, 0.12)), (a0, tip), (a1, tip),
                                            (total - 1, gr)]), 1.0, pole_out=0.15)
        return move_hand(P, "Left", gl + (hips + v(0.18, 0.2, 0.05) - gl) * w, 1.0, pole_out=0.3)
    out[c["anim_of"](mv)] = keyed(mv, pierce)

    # Eclipse: opening spear-hand, four strikes from alternating sides (half
    # turns), then the final spear-hand
    mv = moves["eclipse"]
    def eclipse(t, total, a0, a1, mv=mv):
        tip = hit_point(mv, 0.0, 0.08)
        beats = [a1 + 7, a1 + 14, a1 + 21, a1 + 28]       # strikes
        final = a1 + 37
        keys_r, keys_l, yaw = [(0, gr), (a0, tip), (a1, tip)], [(0, gl)], [(0, 0.0), (a1, 0.0)]
        for k, b in enumerate(beats):
            hand = keys_l if k % 2 == 0 else keys_r
            other = keys_r if k % 2 == 0 else keys_l
            hand += [(b - 3, (gl if k % 2 == 0 else gr)), (b, tip + v(0.05 * (1 if k % 2 == 0 else -1), 0, -0.05 * k))]
            other.append((b, gr if k % 2 == 0 else gl))
            yaw += [(b - 3, 180.0 * (k + 1))]             # snaps round between strikes
        keys_r += [(final - 4, hips + v(-0.16, 0.05, 0.12)), (final, tip), (final + 3, tip), (total - 1, gr)]
        keys_l += [(final, gl), (total - 1, gl)]
        yaw += [(final - 4, 720.0), (total - 1, 720.0)]
        P = sink(G, G, 0.06 * H * hump(t, a1, final + 4))
        P = move_hand(P, "Right", track(t, keys_r), 1.0, pole_out=0.2)
        P = move_hand(P, "Left", track(t, keys_l), 1.0, pole_out=0.2)
        return turn(P, track(t, yaw))
    out[c["anim_of"](mv)] = keyed(mv, eclipse)
    return out


def mirrored(clip):
    """The same capture as its mirror image (left and right swapped): a kick
    recorded with the right leg becomes a left-leg kick."""
    def other(k):
        if k.startswith("Left"):
            return "Right" + k[4:]
        if k.startswith("Right"):
            return "Left" + k[5:]
        if k[0] in "LR" and k[1:2].isupper():            # LHipJoint, RThumb ...
            return ("R" if k[0] == "L" else "L") + k[1:]
        return k
    m = Clip.__new__(Clip)
    m.P = {other(k): v * np.array([-1.0, 1.0, 1.0]) for k, v in clip.P.items()}
    m.n, m.stand_hips = clip.n, clip.stand_hips
    return m


def bend_to(P, root, mid, end, mid_target, end_target, carry=()):
    """Two-bone IK that puts the MIDDLE joint (elbow, knee) as near as it can
    to mid_target while the end joint goes to end_target. Elbow and knee
    strikes: the joint is the weapon, the hand or foot only follows."""
    cur = P[end]
    Q = ik2(P, root, mid, end, end_target, np.array(mid_target, float))
    for k in carry:
        if k in P:
            Q[k] = P[k] - cur + Q[end]
    return Q


HAND_CARRY = ("HandIndex1", "HandIndex1_end", "FingerBase", "Thumb", "Thumb_end")
FOOT_CARRY = ("ToeBase", "ToeBase_end")


def point_hand(P, side, toward):
    """Turn the hand so its fingers point along `toward` (the capture has no
    hand data: hands otherwise keep the direction they had in the guard)."""
    d = _norm(np.array(toward, float))
    h = P[side + "Hand"]
    P = dict(P)
    for k in [side + k for k in HAND_CARRY] + [side[0] + "Thumb", side[0] + "Thumb_end"]:
        if k in P:
            P[k] = h + d * np.linalg.norm(P[k] - h)
    return P


def vexa_set(c):
    """Vexa: Circuit Striker. Muay Thai with a cybernetic left (lead) arm.
    The Teep is a captured front kick (CMU 144_05, mirrored onto the lead
    leg) and the Cut Kick a captured roundhouse (86_08) kept below hip
    height. Everything else is keyed from her guard: the library has no
    elbows, knees or anything like the arm's piston punches and shots.

    Keyed strikes are aimed in MODEL space: c["joints"](P) gives the game
    skeleton's joints for a source pose, and because the retarget copies limb
    directions, a point the model's wrist, elbow or knee must reach converts
    to a source-space IK target by the ratio of the limb lengths."""
    H, G, moves, pose_of, box = c["H"], c["guard_P"], c["moves"], c["pose_of"], c["box"]
    v = lambda x, y, z: np.array([x, y, z]) * H          # noqa: E731
    gl, gr = G["LeftHand"], G["RightHand"]
    lf, rf = G["LeftFoot"], G["RightFoot"]
    joints = c["joints"]
    teep_c, round_c = mirrored(c["clip"]("144_05")), c["clip"]("86_08")
    out = {}

    g_m = joints(G)[0]
    def length(P, chain):
        return sum(np.linalg.norm(P[b] - P[a]) for a, b in zip(chain, chain[1:]))
    ARM = {sd: length(g_m, [sd + "UpperArm", sd + "LowerArm", sd + "Hand"]) / length(G, [sd + "Arm", sd + "ForeArm", sd + "Hand"])
           for sd in ("Left", "Right")}
    UPPER_ARM = {sd: length(g_m, [sd + "UpperArm", sd + "LowerArm"]) / length(G, [sd + "Arm", sd + "ForeArm"])
                 for sd in ("Left", "Right")}
    THIGH = {sd: length(g_m, [sd + "UpperLeg", sd + "LowerLeg"]) / length(G, [sd + "UpLeg", sd + "Leg"])
             for sd in ("Left", "Right")}
    FIST = 0.07 * H                                       # wrist to the middle of the fist

    def at(x, fwd, z):
        """A point in model space: x to her left, fwd toward the opponent, z above the floor."""
        return np.array([x, -fwd, z])

    def wrist_src(P, side, target_m):
        m = joints(P)[0]
        return P[side + "Arm"] + (np.array(target_m) - m[side + "UpperArm"]) / ARM[side]

    def elbow_src(P, side, target_m):
        m = joints(P)[0]
        return P[side + "Arm"] + (np.array(target_m) - m[side + "UpperArm"]) / UPPER_ARM[side]

    def knee_src(P, side, target_m):
        m = joints(P)[0]
        return P[side + "UpLeg"] + (np.array(target_m) - m[side + "UpperLeg"]) / THIGH[side]

    def blend_P(A, B, w):
        return {k: A[k] * (1 - w) + B[k] * w for k in A}

    def keyed(mv, fn, lift=None, settle=6):
        total, a0, a1 = frames_of(mv)
        poses = []
        for t in range(total):
            pose = pose_of(fn(t, total, a0, a1), box)
            up = lift(t) if lift else 0.0
            if up > 0.005:
                pose = Pose(pose.D, pose.hips + np.array([0, 0, up]))
            poses.append(pose)
        for t in range(max(0, total - settle), total):
            poses[t] = Pose.blend(poses[t], c["guard"], ease((t - (total - settle)) / settle))
        return poses

    def snap(t, keys):
        """A track without easing: the cyber arm moves in hard mechanical
        snaps (linear, full speed from the first frame), unlike her body."""
        if t <= keys[0][0]:
            return keys[0][1]
        for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
            if t <= f1:
                return v0 + (v1 - v0) * ((t - f0) / max(1e-6, f1 - f0))
        return keys[-1][1]

    def aim(cl, peak, side):
        d = (cl.at(peak)[side + "Foot"] - cl.at(peak)["Hips"])[:2]
        return d / (np.linalg.norm(d) + 1e-9)

    def lunge(P, fwd, down=0.0):
        """The body travels toward the opponent over planted feet."""
        Q = shift(P, BODY, np.array([0, -fwd, -down]))
        for sd in ("Left", "Right"):
            Q = move_foot(Q, sd, P[sd + "Foot"])
        return Q

    def twist(P, deg):
        """Turn the shoulders (not the hips) about the spine; + brings the rear (right) shoulder forward."""
        o = np.array([P["Hips"][0], P["Hips"][1], 0.0])
        R = np.array(Matrix.Rotation(math.radians(deg), 3, "Z"))
        Q = dict(P)
        for k in UPPER:
            if k in Q:
                Q[k] = R @ (Q[k] - o) + o
        return Q

    def arm_to(P, side, wrist_m, w=1.0, pole_out=0.2, fingers=None):
        if w <= 0:
            return P
        Q = move_hand(P, side, wrist_src(P, side, wrist_m), w, pole_out=pole_out)
        return point_hand(Q, side, fingers) if fingers is not None and w > 0.5 else Q

    def brace(P, w):
        """Rear hand clamps onto the cyber arm's biceps (steadying it)."""
        if w <= 0:
            return P
        m = joints(P)[0]
        grip = m["LeftUpperArm"] + (m["LeftLowerArm"] - m["LeftUpperArm"]) * 0.6 + np.array([-0.03, 0.0, -0.02])
        return arm_to(P, "Right", grip, w, pole_out=0.35)

    FWD = np.array([0.0, -1.0, 0.0])

    # Piston Jab: cocked for two frames, then fired down one straight line in
    # two; the body slides in behind it but shoulders and hips do not turn
    mv = moves["piston_jab"]
    def jab(t, total, a0, a1, mv=mv):
        go = snap(t, [(0, 0.0), (a0 - 2, 0.0), (a0, 1.0), (a1, 1.0), (a1 + 4, 0.0)])
        P = lunge(G, 0.15 * H * go)
        fist = at(0.05 * H, mv["hc"][0] - 0.04 - FIST, mv["hc"][1] - 0.02)
        cock = joints(P)[0]["LeftHand"] + np.array([0.0, 0.07, -0.03])
        tgt = snap(t, [(0, cock), (a0 - 2, cock), (a0, fist), (a1, fist), (a1 + 4, cock)])
        w = snap(t, [(0, 0.0), (a0 - 2, 1.0), (a1 + 4, 1.0), (total - 1, 0.0)])
        return arm_to(P, "Left", tgt, w, pole_out=0.1, fingers=FWD if go > 0.5 else None)
    out[c["anim_of"](mv)] = keyed(mv, jab, settle=4)

    # Teep: captured front kick on the lead leg, pushed through at hip height
    mv = moves["teep"]
    # (the shared strike helper aims in capture space, where this model's
    # foot ends about 12 cm higher: aim that much lower so it lands in the box)
    low = dict(mv, hc=[mv["hc"][0], mv["hc"][1] - 0.12])
    out[c["anim_of"](mv)] = c["strike"](teep_c, 1639, "Left", "foot", low, pre=44, post=56, blend_in=4,
                                        aim=aim(teep_c, 1639, "Left"))

    # Cut Kick: captured rear-leg roundhouse, reshaped into a low kick. The
    # capture is thrown at the ribs with the body leaning far away, so three
    # things are changed for the whole swing: the foot stays under a ceiling
    # (the hip turn then carries the shin round at thigh height), most of the
    # lean is taken back out, and on the active frames the leg is straightened
    # out to its full length instead of being folded down onto the hitbox
    mv = moves["cut_kick"]
    total, a0, a1 = frames_of(mv)
    ceiling = mv["hc"][1] + 0.1
    def keep_low(P, t, T, a0=a0, a1=a1, mv=mv):
        P = lean(P, -40 * hump(t, 2, T - 7))
        foot = P["RightFoot"]
        if foot[2] > ceiling:
            P = move_foot(P, "Right", np.array([foot[0], foot[1], ceiling]))
        w = track(t, [(0, 0.0), (a0 - 5, 0.0), (a0, 1.0), (a1, 1.0), (a1 + 6, 0.0)])
        if w > 0:
            hip, foot = P["RightUpLeg"], P["RightFoot"]
            leg = 0.97 * (np.linalg.norm(P["RightLeg"] - hip) + np.linalg.norm(foot - P["RightLeg"]))
            drop = hip[2] - (mv["hc"][1] - 0.05)                          # shin through the middle of the box
            out_xy = _norm(np.array([foot[0] - hip[0], foot[1] - hip[1]]))
            flat = math.sqrt(max(0.0, leg * leg - drop * drop))
            P = move_foot(P, "Right", np.array([hip[0] + out_xy[0] * flat, hip[1] + out_xy[1] * flat, hip[2] - drop]), w)
        return P
    out[c["anim_of"](mv)] = c["strike"](round_c, 4325, "Right", "foot", mv, pre=36, post=44, blend_in=4,
                                        aim=aim(round_c, 4325, "Right"), extra=keep_low)

    # Slashing Elbow: steps in (the game carries her), the shoulders turn
    # over and the rear elbow cuts diagonally down through the hitbox, the
    # forearm folded back across her own chest
    mv = moves["slashing_elbow"]
    def elbow(t, total, a0, a1, mv=mv):
        w = track(t, [(0, 0.0), (a0, 1.0), (a1, 1.0), (total - 1, 0.0)])
        P = move_foot(G, "Left", lf + v(0, -0.08, 0.05 * hump(t, 0, a0)) * w)       # the step
        P = lunge(P, 0.12 * H * w, 0.04 * H * w)
        P = twist(P, 62 * w)
        P = lean(P, -5 * w)                                                   # stays behind the elbow: the head must not lead
        m = joints(P)[0]
        sh = m["RightUpperArm"]
        tip0 = at(-0.02 * H, mv["hc"][0] - 0.04, mv["hc"][1] + 0.1)          # enters high ...
        tip1 = at(0.05 * H, mv["hc"][0] - 0.07, mv["hc"][1] - 0.1)           # ... leaves low, across the centre line
        e = track(t, [(0, m["RightLowerArm"]), (a0 - 3, sh + v(-0.1, -0.1, 0.2)), (a0, tip0), (a1, tip1),
                      (a1 + 5, sh + v(0.02, -0.18, -0.1)), (total - 1, m["RightLowerArm"])])
        e_s = elbow_src(P, "Right", e)
        fold = e_s + v(0.2, 0.14, 0.03) / UPPER_ARM["Right"]                 # fist back by her own collarbone
        hand = blend_P({"h": P["RightHand"]}, {"h": fold}, track(t, [(0, 0.0), (a0 - 3, 1.0), (a1 + 2, 1.0),
                                                                     (total - 1, 0.0)]))["h"]
        P = bend_to(P, "RightArm", "RightForeArm", "RightHand", e_s, hand, ["Right" + k for k in HAND_CARRY] + ["RThumb"])
        return move_hand(P, "Left", gl + v(0.0, 0.1, 0.03) * w, 1.0, pole_out=0.2)       # lead hand stays home
    out[c["anim_of"](mv)] = keyed(mv, elbow)

    # Pulse Shot: the arm locks out level, the rear hand clamps it, the whole
    # body rocks back on the shot (frame a0) and settles
    mv = moves["pulse_shot"]
    def shot(t, total, a0, a1, mv=mv):
        w = track(t, [(0, 0.0), (6, 1.0), (a0 + 4, 1.0), (total - 1, 0.0)])
        kick = hump(t, a0 - 1, a0 + 6)                                        # recoil
        P = move_foot(G, "Right", rf + v(-0.02, 0.1, 0.0) * w)                # rear foot braces
        P = lunge(P, (0.05 - 0.07 * kick) * H * w, 0.05 * H * w)
        P = lean(P, -4 * w + 6 * kick)
        P = twist(P, -14 * w)                                                 # squares the cyber shoulder to the target
        muzzle = at(0.07 * H, 0.56 * H - 0.05 * kick, mv["hc"][1])
        cock = joints(P)[0]["LeftHand"] + np.array([0.0, 0.1, -0.05])
        arm_w = snap(t, [(0, 0.0), (3, 1.0), (a0 + 5, 1.0), (total - 1, 0.0)])
        tgt = snap(t, [(0, cock), (4, cock), (7, muzzle), (a0 + 5, muzzle), (total - 1, cock)])
        P = arm_to(P, "Left", tgt, arm_w, pole_out=0.08, fingers=FWD if 6 <= t <= a0 + 6 else None)
        return brace(P, track(t, [(0, 0.0), (6, 0.0), (11, 1.0), (a0 + 4, 1.0), (total - 2, 0.0)]))
    out[c["anim_of"](mv)] = keyed(mv, shot)

    # Overclock Knee: two running strides (the game carries her), then she
    # leaves the floor: the cyber arm reaches out and hauls down while the
    # rear knee drives up through the hitbox
    mv = moves["overclock_knee"]
    total, a0, a1 = frames_of(mv)
    rise = lambda t, a0=a0, a1=a1: 0.16 * H * hump(t, a0 - 4, a1 + 7)       # noqa: E731
    def knee(t, total, a0, a1, mv=mv):
        run = track(t, [(0, 0.0), (2, 1.0), (a0 - 4, 1.0), (a0 - 1, 0.0)])
        fly = track(t, [(0, 0.0), (a0 - 4, 0.0), (a0, 1.0), (a1, 1.0), (a1 + 8, 0.0)])
        P = G
        for sd, ph, base in (("Left", 0.0, lf), ("Right", math.pi, rf)):      # two quick strides
            a = 2 * math.pi * t / 8.0 + ph
            P = move_foot(P, sd, base + v(0, -0.15 * math.cos(a), 0.09 * max(0.0, math.sin(a))) * run)
        P = lean(P, -14 * run + 8 * fly)                                      # runs leaning in, hips thrust through on the knee
        if fly > 0:
            P = shift(P, BODY, np.array([0, -0.1 * H * fly, 0]))              # hips forward over the standing leg
            P = move_foot(P, "Left", lf + v(-0.04, 0.12, 0.0) * fly)          # that leg trails, toes down
            point = at(-0.06 * H, mv["hc"][0] - 0.1, mv["hc"][1] - 0.02 - rise(t))
            k_s = knee_src(P, "Right", point)
            k_now = P["RightLeg"] + (k_s - P["RightLeg"]) * fly
            f_now = P["RightFoot"] + (k_s + v(0.0, 0.3, -0.27) - P["RightFoot"]) * fly    # shin folded back under the thigh
            P = bend_to(P, "RightUpLeg", "RightLeg", "RightFoot", k_now, f_now, ["Right" + k for k in FOOT_CARRY])
        m = joints(P)[0]
        home = m["LeftHand"]
        clinch = at(0.03 * H, 0.52 * H, 1.5 * H - rise(t))                    # behind the opponent's head
        pull = at(0.0, 0.36 * H, 1.24 * H - rise(t))                          # hauled down onto the knee
        tgt = snap(t, [(0, home), (a0 - 6, home), (a0 - 2, clinch), (a0, pull), (a1, pull), (a1 + 8, home)])
        arm_w = snap(t, [(0, 0.0), (a0 - 6, 0.0), (a0 - 4, 1.0), (a1 + 3, 1.0), (a1 + 8, 0.0)])
        P = arm_to(P, "Left", tgt, arm_w, pole_out=0.3)
        return move_hand(P, "Right", P["RightHand"] + v(-0.08, 0.16, -0.14) * fly, 1.0, pole_out=0.3)   # rear arm swings back
    name = c["anim_of"](mv)
    out[name] = keyed(mv, knee, lift=rise)
    c["air"](name, a0 - 3, a1 + 6)

    # Arc Guard: the cyber forearm snaps upright in front of her face as a
    # shield and is held through the parry window, feet rooted
    mv = moves["arc_guard"]
    c0, c1 = mv["counter"]
    def arc(t, total, a0, a1):
        w = snap(t, [(0, 0.0), (max(1, c0 - 1), 1.0), (c1, 1.0), (c1 + 9, 0.0)])
        soft = track(t, [(0, 0.0), (c0, 1.0), (c1, 1.0), (total - 1, 0.0)])
        P = lunge(G, 0.0, 0.05 * H * soft)
        P = lean(P, -5 * soft)
        P = twist(P, -10 * soft)
        m = joints(P)[0]
        head = m["Head"]
        elb = elbow_src(P, "Left", head + v(0.1, -0.3, -0.27))                # forearm upright, held out in front of the face
        wri = wrist_src(P, "Left", head + v(0.03, -0.38, -0.02))
        e_now = P["LeftForeArm"] + (elb - P["LeftForeArm"]) * w
        h_now = P["LeftHand"] + (wri - P["LeftHand"]) * w
        P = bend_to(P, "LeftArm", "LeftForeArm", "LeftHand", e_now, h_now, ["Left" + k for k in HAND_CARRY] + ["LThumb"])
        if w > 0.5:
            P = point_hand(P, "Left", [0.0, -0.15, 1.0])                      # blade hand, fingers up
        return move_hand(P, "Right", gr + v(0.04, 0.03, -0.06) * soft, 1.0, pole_out=0.2)   # rear hand tucks to the ribs
    out[c["anim_of"](mv)] = keyed(mv, arc)

    # System Overdrive: point-blank pulse on the active frames, five piston
    # punches (one every four frames), the arm drawn right back, then the
    # beam held at full extension while the body shudders
    mv = moves["system_overdrive"]
    def overdrive(t, total, a0, a1, mv=mv):
        beats = [a1 + 5 + 4 * k for k in range(5)]
        wind, beam, hold = beats[-1] + 4, beats[-1] + 9, total - 9
        low = track(t, [(0, 0.0), (a0, 1.0), (hold, 1.0), (total - 1, 0.0)])
        charge = track(t, [(0, 0.0), (beats[-1] + 1, 0.0), (wind, 1.0), (beam, 0.0)])
        fire = track(t, [(0, 0.0), (beam - 1, 0.0), (beam + 1, 1.0), (hold, 1.0), (total - 1, 0.0)])
        P = move_foot(G, "Right", rf + v(-0.03, 0.1, 0.0) * low)
        P = lunge(P, (0.07 - 0.12 * charge) * H * low, 0.06 * H * low)
        P = lean(P, -6 * low + 10 * charge - 4 * fire + 1.5 * fire * math.sin(t * 2.2))
        P = twist(P, -12 * fire + 30 * charge)
        m = joints(P)[0]
        sh = m["LeftUpperArm"]
        palm = at(0.05 * H, mv["hc"][0] + 0.14 - FIST, mv["hc"][1] + 0.02)        # arm all but locked out
        cock = sh + v(0.05, -0.02, -0.15)                                     # fist right back at the ribs between punches
        back = sh + v(0.1, 0.16, -0.16)                                       # drawn back past her ribs
        far = at(0.07 * H, 0.95 * H, mv["hc"][1] + 0.06)                      # past her reach: the arm locks straight
        keys = [(0, m["LeftHand"]), (a0 - 3, cock), (a0, palm), (a1, palm)]
        for k, b in enumerate(beats):
            keys += [(b - 2, cock), (b, palm + v(0.0, 0.0, 0.06 - 0.03 * k))]
        keys += [(wind, back), (beam, far), (hold, far), (total - 1, m["LeftHand"])]
        arm_w = snap(t, [(0, 0.0), (a0 - 3, 1.0), (hold, 1.0), (total - 1, 0.0)])
        P = arm_to(P, "Left", snap(t, keys), arm_w, pole_out=0.1, fingers=FWD)
        return brace(P, fire)
    out[c["anim_of"](mv)] = keyed(mv, overdrive, settle=8)
    return out


class Kit:
    """Helpers for keyed moves aimed in MODEL space (first used for Vexa,
    D-066; shared from Ryuen on). c["joints"](P) gives the game skeleton's
    joints for a source pose; because the retarget copies limb directions, a
    point the model's wrist, elbow, knee or ankle must reach converts to a
    source-space IK target by the ratio of the limb lengths."""

    FWD = np.array([0.0, -1.0, 0.0])

    def __init__(self, c):
        self.c, self.H, self.G = c, c["H"], c["guard_P"]
        self.joints = c["joints"]
        g_m, G = self.joints(self.G)[0], self.G
        def length(P, chain):
            return sum(np.linalg.norm(P[b] - P[a]) for a, b in zip(chain, chain[1:]))
        sides = ("Left", "Right")
        self.ARM = {sd: length(g_m, [sd + "UpperArm", sd + "LowerArm", sd + "Hand"])
                    / length(G, [sd + "Arm", sd + "ForeArm", sd + "Hand"]) for sd in sides}
        self.UPPER_ARM = {sd: length(g_m, [sd + "UpperArm", sd + "LowerArm"]) / length(G, [sd + "Arm", sd + "ForeArm"])
                          for sd in sides}
        self.LEG = {sd: length(g_m, [sd + "UpperLeg", sd + "LowerLeg", sd + "Foot"])
                    / length(G, [sd + "UpLeg", sd + "Leg", sd + "Foot"]) for sd in sides}
        self.THIGH = {sd: length(g_m, [sd + "UpperLeg", sd + "LowerLeg"]) / length(G, [sd + "UpLeg", sd + "Leg"])
                      for sd in sides}
        self.FIST = 0.07 * self.H                         # wrist to the middle of the fist / palm

    def v(self, x, y, z):
        return np.array([x, y, z]) * self.H

    @staticmethod
    def at(x, fwd, z):
        """A point in model space: x to the fighter's left, fwd toward the opponent, z above the floor."""
        return np.array([x, -fwd, z])

    def model(self, P):
        return self.joints(P)[0]

    def wrist_src(self, P, side, target_m):
        return P[side + "Arm"] + (np.array(target_m) - self.model(P)[side + "UpperArm"]) / self.ARM[side]

    def elbow_src(self, P, side, target_m):
        return P[side + "Arm"] + (np.array(target_m) - self.model(P)[side + "UpperArm"]) / self.UPPER_ARM[side]

    def knee_src(self, P, side, target_m):
        return P[side + "UpLeg"] + (np.array(target_m) - self.model(P)[side + "UpperLeg"]) / self.THIGH[side]

    def ankle_src(self, P, side, target_m):
        return P[side + "UpLeg"] + (np.array(target_m) - self.model(P)[side + "UpperLeg"]) / self.LEG[side]

    def arm_to(self, P, side, wrist_m, w=1.0, pole_out=0.2, fingers=None):
        """Wrist of `side` to a model-space point (weight w); fingers: direction the hand points."""
        if w <= 0:
            return P
        Q = move_hand(P, side, self.wrist_src(P, side, wrist_m), w, pole_out=pole_out)
        return point_hand(Q, side, fingers) if fingers is not None and w > 0.5 else Q

    def elbow_to(self, P, side, elbow_m, fold):
        """Elbow of `side` to a model-space point; the wrist sits `fold` (source metres) from the elbow."""
        e = self.elbow_src(P, side, elbow_m)
        return bend_to(P, side + "Arm", side + "ForeArm", side + "Hand", e, e + np.array(fold),
                       [side + k for k in HAND_CARRY] + [side[0] + "Thumb"])

    def foot_to(self, P, side, ankle_m, w=1.0):
        if w <= 0:
            return P
        return move_foot(P, side, self.ankle_src(P, side, ankle_m), w)

    @staticmethod
    def lunge(P, fwd, down=0.0):
        """The body travels toward the opponent (and sinks) over planted feet."""
        Q = shift(P, list(P.keys()), np.array([0, -fwd, -down]))
        for sd in ("Left", "Right"):
            Q = move_foot(Q, sd, P[sd + "Foot"])
        return Q

    @staticmethod
    def twist(P, deg):
        """Turn the shoulders (not the hips) about the spine; + brings the right shoulder forward."""
        o = np.array([P["Hips"][0], P["Hips"][1], 0.0])
        R = np.array(Matrix.Rotation(math.radians(deg), 3, "Z"))
        Q = dict(P)
        for k in UPPER:
            if k in Q:
                Q[k] = R @ (Q[k] - o) + o
        return Q

    @staticmethod
    def snap(t, keys):
        """A keyed track without easing (linear between keys)."""
        if t <= keys[0][0]:
            return keys[0][1]
        for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
            if t <= f1:
                return v0 + (v1 - v0) * ((t - f0) / max(1e-6, f1 - f0))
        return keys[-1][1]

    def keyed(self, mv, fn, lift=None, settle=6):
        """Poses for every frame of a move from fn(t, total, a0, a1) -> source pose, settling into the guard."""
        c = self.c
        total, a0, a1 = frames_of(mv)
        poses = []
        for t in range(total):
            pose = c["pose_of"](fn(t, total, a0, a1), c["box"])
            up = lift(t) if lift else 0.0
            if up > 0.005:
                pose = Pose(pose.D, pose.hips + np.array([0, 0, up]))
            poses.append(pose)
        for t in range(max(0, total - settle), total):
            poses[t] = Pose.blend(poses[t], c["guard"], ease((t - (total - settle)) / settle))
        return poses


def ryuen_set(c):
    """Ryuen: Still Water. Tai Chi, Wing Chun and Aikido; everything returns
    to the same quiet guard. Palm Heel and the palm that follows Returning
    Wave are captured straight strikes (CMU 144_13 lead hand, 144_20 rear
    hand) thrown with an open hand. Everything else is keyed from his guard:
    the library has no chain punches, palm pushes, stamps, elbows, circling
    parries or throws."""
    k = Kit(c)
    H, G, moves, v, at = k.H, k.G, c["moves"], k.v, k.at
    gl, gr = G["LeftHand"], G["RightHand"]
    lf, rf = G["LeftFoot"], G["RightFoot"]
    # He stands right side forward; the captures are left-lead, so they are mirrored.
    LEAD = "Left" if lf[1] < rf[1] else "Right"
    REAR = "Right" if LEAD == "Left" else "Left"
    SG = 1 if REAR == "Right" else -1                     # sign that brings the REAR shoulder forward in twist()
    art, art_r = c["clip"]("144_13"), c["clip"]("144_20")
    if LEAD == "Right":
        art, art_r = mirrored(art), mirrored(art_r)
    FWD, UP = Kit.FWD, np.array([0.0, -0.25, 1.0])
    out = {}
    home = k.model(G)
    hl, hr = home["LeftHand"], home["RightHand"]          # the guard's hands, in model space
    base_of = {"Left": hl, "Right": hr}

    def lowered(mv, by):
        """The shared strike helper aims in capture space; this model's hand ends higher by about `by`."""
        return dict(mv, hc=[mv["hc"][0], mv["hc"][1] - by])

    # Palm Heel: captured lead straight, open hand
    mv = moves["palm_heel"]
    out[c["anim_of"](mv)] = c["strike"](art, 439, LEAD, "hand", lowered(mv, 0.1), pre=30, post=40, blend_in=3)

    # Chain Punch: three vertical fists rolling over each other down the
    # centre line, one per hit (lead, rear, lead); the elbows stay low and in
    mv = moves["chain_punch"]
    def chain(t, total, a0, a1, mv=mv):
        beats = [a0, a0 + 2, a0 + 4]
        go = track(t, [(0, 0.0), (a0, 1.0), (a1, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, 0.15 * H * go, 0.03 * H * go)
        tip = at(0.0, mv["hc"][0] + 0.04 - k.FIST, mv["hc"][1] + 0.03)
        chest = k.model(P)["Chest"] + v(0.0, -0.2, 0.12)                     # fist held back at the sternum
        keys = {"Left": [(0, hl), (a0 - 3, chest)], "Right": [(0, hr), (a0 - 2, chest + v(0, 0.0, -0.05))]}
        for i, b in enumerate(beats):
            sd, other = (LEAD, REAR) if i % 2 == 0 else (REAR, LEAD)
            keys[sd] += [(b, tip + v(0.0, 0.0, -0.03 * i))]
            keys[other] += [(b, chest)]
        for sd, base in (("Left", hl), ("Right", hr)):
            keys[sd] += [(a1 + 3, chest), (total - 1, base)]
        for sd in ("Left", "Right"):
            P = k.arm_to(P, sd, Kit.snap(t, keys[sd]), 1.0 if 0 < t < total - 1 else 0.0, pole_out=0.5, fingers=FWD)
        return P
    out[c["anim_of"](mv)] = k.keyed(mv, chain)

    # Shin Stamp: the lead knee barely lifts, then the heel is driven
    # straight down and forward into the opponent's shin
    mv = moves["shin_stamp"]
    def stamp(t, total, a0, a1, mv=mv):
        w = track(t, [(0, 0.0), (a0 - 3, 1.0), (a1 + 2, 1.0), (total - 1, 0.0)])
        P = lean(G, 5 * w)                                                   # weight settles onto the rear leg
        ankle0 = k.model(P)[LEAD + "Foot"]
        lift = ankle0 + v(0.0, -0.08, 0.22)
        hit = at(ankle0[0], mv["hc"][0] - 0.06, mv["hc"][1] - 0.06)
        tgt = track(t, [(0, ankle0), (a0 - 3, lift), (a0, hit), (a1, hit + v(0, 0, -0.04)), (a1 + 6, ankle0)])
        return k.foot_to(P, LEAD, tgt, 1.0 if 0 < t <= a1 + 6 else 0.0)
    out[c["anim_of"](mv)] = k.keyed(mv, stamp)

    # Sinking Elbow: half a step in (the game carries him), the whole body
    # drops and the rear elbow is driven level into the ribs
    mv = moves["sinking_elbow"]
    def elbow(t, total, a0, a1, mv=mv):
        w = track(t, [(0, 0.0), (a0, 1.0), (a1, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, 0.12 * H * w, 0.11 * H * w)
        P = Kit.twist(P, 58 * SG * w)
        m = k.model(P)
        tip = at(-0.03 * H * SG, mv["hc"][0] - 0.05, mv["hc"][1])
        e = track(t, [(0, m[REAR + "LowerArm"]), (a0 - 4, m[REAR + "UpperArm"] + v(-0.12 * SG, 0.08, -0.12)), (a0, tip),
                      (a1, tip), (total - 1, m[REAR + "LowerArm"])])
        fold = track(t, [(0, 0.0), (a0 - 4, 1.0), (a1 + 2, 1.0), (total - 1, 0.0)])
        if fold > 0:
            wrist_now = P[REAR + "Hand"] - k.elbow_src(P, REAR, m[REAR + "LowerArm"])
            folded = v(0.18 * SG, 0.16, 0.06) / k.UPPER_ARM[REAR]             # forearm folded back against the chest
            P = k.elbow_to(P, REAR, e, wrist_now * (1 - fold) + folded * fold)
        return k.arm_to(P, LEAD, base_of[LEAD] + v(0.0, 0.08, -0.03) * w, 1.0 if w > 0 else 0.0, pole_out=0.3)
    out[c["anim_of"](mv)] = k.keyed(mv, elbow)

    # Mountain Push: both feet rooted, the palms gather at the ribs and the
    # whole body goes through them
    mv = moves["mountain_push"]
    def push(t, total, a0, a1, mv=mv):
        gather = track(t, [(0, 0.0), (a0 - 6, 1.0), (a0 - 2, 1.0), (a0, 0.0)])
        drive = track(t, [(0, 0.0), (a0 - 2, 0.0), (a0, 1.0), (a1 + 4, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, (-0.06 * gather + 0.1 * drive) * H, (0.07 * gather + 0.05 * drive) * H)
        P = lean(P, 5 * gather - 9 * drive)
        m = k.model(P)
        for sd, sg, base in (("Left", 1, hl), ("Right", -1, hr)):
            ribs = m["Chest"] + v(0.16 * sg, -0.12, -0.02)
            far = at(0.11 * H * sg, mv["hc"][0] + 0.12, mv["hc"][1] - 0.06)        # past his reach: the arms lock out
            tgt = track(t, [(0, base), (a0 - 6, ribs), (a0 - 2, ribs), (a0, far), (a1 + 4, far), (total - 1, base)])
            P = k.arm_to(P, sd, tgt, 1.0 if 0 < t < total - 1 else 0.0, pole_out=0.45, fingers=UP)
        return P
    out[c["anim_of"](mv)] = k.keyed(mv, push)

    # Flowing Step: a quarter turn off the line with soft knees, arms
    # trailing round, then back to face the opponent
    mv = moves["flowing_step"]
    def flow(t, total, a0, a1):
        w = track(t, [(0, 0.0), (4, 1.0), (11, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, 0.0, 0.06 * H * w)
        P = turn(P, -80 * w)
        m = k.model(P)
        P = k.arm_to(P, "Left", m["LeftHand"] + v(0.0, 0.0, -0.1) * w, w, pole_out=0.4)
        return k.arm_to(P, "Right", m["RightHand"] + v(0.0, 0.0, -0.06) * w, w, pole_out=0.4)
    out[c["anim_of"](mv)] = k.keyed(mv, flow)

    # Returning Wave: the open palms circle each other in front of the chest
    # (one full, slow turn across the counter window), knees soft
    mv = moves["returning_wave"]
    c0, c1 = mv["counter"]
    def wave(t, total, a0, a1):
        w = track(t, [(0, 0.0), (c0, 1.0), (c1, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, 0.0, 0.05 * H * w)
        m = k.model(P)
        centre = m["Chest"] + v(0.0, -0.36, 0.02)
        ang = 2 * math.pi * (t - c0) / max(1, c1 - c0)
        for sd, ph, base in (("Left", 0.0, m["LeftHand"]), ("Right", math.pi, m["RightHand"])):
            ring = centre + v(0.13 * math.cos(ang + ph), 0.05 * math.sin(ang + ph), 0.15 * math.sin(ang + ph))
            P = k.arm_to(P, sd, base + (ring - base) * w, 1.0 if w > 0 else 0.0, pole_out=0.45, fingers=UP if w > 0.5 else None)
        return P
    out[c["anim_of"](mv)] = k.keyed(mv, wave)

    # ... and its answer: captured rear straight with an open hand, into the back
    mv = moves["wave_palm"]
    out[c["anim_of"](mv)] = c["strike"](art_r, 645, REAR, "hand", lowered(mv, 0.1), pre=30, post=44, blend_in=3)

    # Wrist Throw: both hands take the wrist, the hips turn and the arm is
    # led down and across (the victim only has its normal fall)
    mv = moves["wrist_throw"]
    def throw(t, total, a0, a1, mv=mv):
        reach = track(t, [(0, 0.0), (a0, 1.0), (a1 + 2, 1.0), (a1 + 12, 0.0)])
        lead = track(t, [(0, 0.0), (a1 + 1, 0.0), (a1 + 11, 1.0), (total - 8, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, 0.1 * H * reach, 0.06 * H * (reach + lead))
        P = turn(P, -70 * lead)
        m = k.model(P)
        for sd, sg, base in (("Left", 1, m["LeftHand"]), ("Right", -1, m["RightHand"])):
            grab = at(0.05 * H * sg, mv["hc"][0] - k.FIST, mv["hc"][1] - 0.05)
            down = m["Hips"] + v(0.1 * sg - 0.25, -0.2, -0.25)                # led down past his own hip
            tgt = base + (grab - base) * reach + (down - base) * lead
            P = k.arm_to(P, sd, tgt, 1.0 if (reach + lead) > 0 else 0.0, pole_out=0.4)
        return P
    out[c["anim_of"](mv)] = k.keyed(mv, throw, settle=8)

    # Thousand Rivers: he lowers his hands and stands open through the whole
    # counter window
    mv = moves["thousand_rivers"]
    c0, c1 = mv["counter"]
    def rivers(t, total, a0, a1):
        w = track(t, [(0, 0.0), (c0, 1.0), (c1, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, -0.02 * H * w, -0.02 * H * w)                       # stands a little taller
        P = lean(P, 2 * w)
        m = k.model(P)
        for sd, sg in (("Left", 1), ("Right", -1)):
            rest = m["Hips"] + v(0.24 * sg, -0.06, -0.12 + 0.01 * math.sin(t * 0.25))   # open hands by the hips, breathing
            P = k.arm_to(P, sd, m[sd + "Hand"] + (rest - m[sd + "Hand"]) * w, 1.0 if w > 0 else 0.0, pole_out=0.5,
                         fingers=np.array([0.0, -0.3, -1.0]) if w > 0.5 else None)
        return P
    out[c["anim_of"](mv)] = k.keyed(mv, rivers, settle=8)

    # ... struck: a redirecting palm on the active frames, twelve chain
    # punches (one every three frames), then the one-inch palm
    mv = moves["thousand_rivers_strike"]
    def strike12(t, total, a0, a1, mv=mv):
        beats = [a1 + 3 + 3 * i for i in range(12)]
        inch = beats[-1] + 6
        go = track(t, [(0, 0.0), (a0, 1.0), (inch + 3, 1.0), (total - 1, 0.0)])
        surge = track(t, [(0, 0.0), (inch - 3, 0.0), (inch, 1.0), (inch + 3, 1.0), (total - 1, 0.0)])
        P = Kit.lunge(G, (0.1 * go + 0.08 * surge) * H, 0.05 * H * go)
        P = lean(P, -3 * go - 5 * surge)
        m = k.model(P)
        tip = at(0.0, mv["hc"][0] + 0.02 - k.FIST, mv["hc"][1] + 0.05)
        chest = m["Chest"] + v(0.0, -0.2, 0.12)
        near = at(0.02 * H, mv["hc"][0] - 0.2, mv["hc"][1])                 # the palm rests on the chest ...
        keys = {LEAD: [(0, m[LEAD + "Hand"]), (a0, tip), (a1, tip)], REAR: [(0, m[REAR + "Hand"]), (a1, chest)]}
        for i, b in enumerate(beats):
            sd, other = (REAR, LEAD) if i % 2 == 0 else (LEAD, REAR)
            keys[sd] += [(b, tip + v(0.0, 0.0, 0.05 - 0.012 * i))]
            keys[other] += [(b, chest)]
        keys[REAR] += [(inch - 3, near), (inch, near + v(0.0, -0.12, 0.0)), (inch + 3, near + v(0.0, -0.12, 0.0)),   # ... and goes through it
                       (total - 1, m[REAR + "Hand"])]
        keys[LEAD] += [(inch - 3, chest + v(-0.1 * SG, 0.05, -0.15)), (total - 1, m[LEAD + "Hand"])]
        for sd in ("Left", "Right"):
            P = k.arm_to(P, sd, Kit.snap(t, keys[sd]), 1.0 if 0 < t < total - 1 else 0.0, pole_out=0.5,
                         fingers=UP if (sd == REAR and t >= inch - 3) or t <= a1 else FWD)
        return P
    out[c["anim_of"](mv)] = k.keyed(mv, strike12, settle=8)
    return out


OWN_SETS = {"drakon": drakon_set, "seraphina": seraphina_set, "nox": nox_set, "vexa": vexa_set, "ryuen": ryuen_set}
# {action name: (first, last) airborne frame}; filled by build(), read by the
# importer's grounding pass so jumps are not flattened onto the floor.
AIRBORNE = {}
LAST_BUILD = {}


# --------------------------------------------------------------------------- the actions

def build(rig_obj, moves, fid, height, clip_dir):
    rig = Rig(rig_obj)
    Pose.rig = rig
    F = fid.upper()
    clip = lambda name: Clip(os.path.join(clip_dir, name + ".bvh"), height)  # noqa: E731
    box = clip("13_17")          # boxer: guard, jab, cross, combos
    art = clip("144_13")         # martial artist: straight lead punches
    art_r = clip("144_20")       # martial artist: straight rear punches
    kick = clip("144_05")        # front kicks
    lay = clip("113_08")         # lie down / get up (on the back)
    H = height / 1.8

    def src(c, f, facing_frame=None, anchor=None, fd=None):
        P = c.at(f)
        if fd is None:
            fd = c.opponent_dir(int(facing_frame if facing_frame is not None else f))
        a = anchor if anchor is not None else P["Hips"][:2]
        return align(P, fd, a)

    def pose_of(P, c, ground=True):
        if STYLES.get(fid, {}).get("pose", {}).get("fit"):
            P = keep_hands_out(rig, P)                  # no wrist inside the fighter's own body
        D, hips = retarget(rig, P, c.stand_hips, ground)
        if ground:
            hips = ground_fix(rig, D, hips)
        return Pose(D, hips)

    A = {}

    # ---- idle: each fighter's own guard (different performer / stance),
    # shaped to the character: crouch depth, stance width, lean, and how much
    # of the captured bounce is kept. 1 s loop with a cross-fade.
    st = STYLES.get(fid, STYLES["kairo"])
    gclip = clip(st["clip"])
    i0, n_idle = st["frame"], 60
    anchor_idle = gclip.at(i0)["Hips"][:2]
    def raw_idle_P(t):
        f = i0 + (t % n_idle) * 2
        P = src(gclip, f, facing_frame=st.get("facing", i0), anchor=anchor_idle)
        P = shift(P, list(P.keys()), np.array([-P["Hips"][0], -P["Hips"][1], 0]))
        if st.get("turn"):
            R = np.array(Matrix.Rotation(math.radians(st["turn"]), 3, "Z"))
            P = {k: R @ v for k, v in P.items()}
        return P
    # The captured breathing is made to loop: its last frames cross-fade
    # into the frames just before its first one (D-082). It used to jump
    # from frame 59 back to frame 0, a visible cut once a second.
    seam = min(16, i0 // 2)
    def raw_free(t):
        P = src(gclip, i0 + t * 2, facing_frame=st.get("facing", i0), anchor=anchor_idle)
        P = shift(P, list(P.keys()), np.array([-P["Hips"][0], -P["Hips"][1], 0]))
        if st.get("turn"):
            R = np.array(Matrix.Rotation(math.radians(st["turn"]), 3, "Z"))
            P = {k: R @ v for k, v in P.items()}
        return P
    raw = []
    for t in range(n_idle):
        P = raw_free(t)
        if seam > 0 and t >= n_idle - seam:
            w = ease((t - (n_idle - seam) + 1) / float(seam + 1))
            Q = raw_free(t - n_idle)
            P = {k: P[k] * (1 - w) + Q[k] * w for k in P}
        raw.append(P)
    mean = {k: np.mean([r[k] for r in raw], 0) for k in raw[0]}
    def shape(P):
        return shape_stance(P, st, H)
    fitted = bool(st.get("pose", {}).get("fit"))
    rig.auto_palm = fitted
    S_fit = rig.hips_h / 0.95                             # the fighter's own scale (fit_stance)
    def idle_P(t):
        r = raw[int(t) % n_idle]
        amp = st.get("amp", 0.35)
        u = (int(t) % n_idle) / float(n_idle)
        P = shape({k: mean[k] + (r[k] - mean[k]) * amp for k in r})
        if fitted:                                   # limbs solved on the fighter's own skeleton (D-075)
            return fit_stance(rig, P, st, st["_lead"], u)
        return idle_motion(P, st, H, u)
    idle_poses = []
    fade = 14
    for t in range(n_idle + 1):
        p = pose_of(idle_P(t), gclip)
        if t > n_idle - fade:
            w = ease((t - (n_idle - fade)) / fade)
            p = Pose.blend(p, pose_of(idle_P(t - n_idle), gclip), w)
        idle_poses.append(p)
    A[f"{F}_IDLE_A"] = idle_poses
    guard_P = idle_P(0)
    guard = idle_poses[0]
    if os.environ.get("STANCE_ONLY"):        # quick look at a stance: idle only (not a shippable model)
        LAST_BUILD["rig"], LAST_BUILD["poses"] = rig, A
        quick = {n: key_action(rig, n, p) for n, p in A.items()}
        for n, p in A.items():
            if rig.fingers:
                key_fingers(rig, quick[n], hand_curls(fid, n[len(F) + 1:], len(p)))
        return quick
    box_stand = box.stand_hips

    # ---- strikes retimed to frame data, limb guided onto the hitbox
    def strike(c, peak, side, limb, mv, pre=24, post=34, facing=None, reach_w=1.0, extra=None, blend_in=0,
               aim=None, lift=None):
        """aim: horizontal direction of the capture that must point at the
        opponent (kicks thrown sideways from the hips); lift(t): metres the
        whole body is raised on frame t (jumps; those frames are not grounded)."""
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
            P = src(c, f, facing_frame=facing or peak, anchor=anchor, fd=aim)
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
            if fitted and not lift:
                # over the stance centre, on the stance's own foot marks (plant_feet)
                P = shift(P, list(P.keys()), np.array([0.0, guard_P["Hips"][1], 0.0]))
                # a kick leans the trunk away from the leg to stay over the standing foot
                P = steady(P, max_side=40.0, max_forward=40.0) if limb == "foot" else steady(P)
                P = plant_feet(rig, P, st, st["_lead"], c.stand_hips, free=side if limb == "foot" else None)
                if limb == "hand":
                    # the fist itself (8 cm past the wrist) into the middle of the hitbox, on the real arm
                    P = reach_hand(rig, P, side, (None, -(hc[0] - 0.08), hc[1]), w,
                                   pelvis_z(rig, P, st, c.stand_hips))
                P = eyes_on(P)
            pose = pose_of(P, c)
            up = lift(t) if lift else 0.0
            if up > 0.005:                    # grounded pose first, then raised
                pose = Pose(pose.D, pose.hips + np.array([0, 0, up]))
            poses.append(pose)
        # settle into the guard over the last frames so the next move blends cleanly
        n = len(poses)
        if fitted:                             # a posed stance is never the capture's own guard:
            blend_in = max(blend_in, min(4, max(2, a0 - 1)))      # leave it over a few frames, no snap
        for t in range(min(blend_in, n)):      # captures that do not start in a guard
            poses[t] = Pose.blend(guard, poses[t], ease((t + 1) / (blend_in + 1)))
        for t in range(max(0, n - 8), n):
            poses[t] = Pose.blend(poses[t], guard, ease((t - (n - 8)) / 8))
        return poses

    # The shared set is built only for the slots a fighter has not replaced
    # with a move (and animation) of its own.
    def shared(slot, suffix):
        return slot in moves and moves[slot]["animation"].endswith(suffix)
    if shared("LIGHT", "ATTACK_LIGHT_01"):
        A[f"{F}_ATTACK_LIGHT_01"] = strike(box, 1214, "Left", "hand", moves["LIGHT"], pre=20, post=30)
    if shared("HEAVY", "ATTACK_HEAVY_01"):
        A[f"{F}_ATTACK_HEAVY_01"] = strike(box, 3368, "Right", "hand", moves["HEAVY"], pre=28, post=40)
    # the kick is named by its move (a fighter's own kick replaces the shared one)
    if shared("KICK", "KICK_01") or shared("KICK", "KICK_LOW_01"):
        kick_name = F + moves["KICK"]["animation"][moves["KICK"]["animation"].find("_"):]
        A[kick_name] = strike(kick, 1240, "Right", "foot", moves["KICK"], pre=40, post=60)

    # ---- moves only some fighters have (their own move data, D-062)
    def anim_of(mv):
        return F + mv["animation"][mv["animation"].find("_"):]
    if "body_hook" in moves:        # captured rear hook to the body
        mv = moves["body_hook"]
        A[anim_of(mv)] = strike(box, 2214, "Right", "hand", mv, pre=22, post=34, blend_in=4)
    if "counter_hook" in moves:     # captured lead hook at head height
        mv = moves["counter_hook"]
        A[anim_of(mv)] = strike(box, 3342, "Left", "hand", mv, pre=16, post=30, blend_in=2)
    if "slip_counter" in moves:
        # slip: the head leaves the centre line (outside the opponent's lead
        # hand), knees bend, hands stay home; held for the counter window
        mv = moves["slip_counter"]
        total = mv["startup"] + mv["active"] - 1 + mv["recovery"]
        c0, c1 = mv["counter"]
        feet = {sd: guard_P[sd + "Foot"].copy() for sd in ("Left", "Right")}
        slip = []
        for t in range(total):
            w = ease(min(1.0, (t + 1) / max(1, c0)), "out") if t < c1 else 1.0 - ease((t - c1) / max(1, total - 1 - c1))
            P = shift(guard_P, UPPER + ["Hips", "LHipJoint", "RHipJoint", "LeftUpLeg", "RightUpLeg"],
                      np.array([0, 0, -0.07 * H * w]))
            for sd in ("Left", "Right"):
                P = move_foot(P, sd, feet[sd])
            P = lean(P, 18 * w, roll_deg=-32 * w)
            slip.append(pose_of(P, box))
        A[anim_of(mv)] = slip
    if shared("SPECIAL", "SPECIAL_ORIGIN_PALM"):
        A[f"{F}_SPECIAL_ORIGIN_PALM"] = strike(art, 439, "Left", "hand", moves["SPECIAL"], pre=34, post=46)
    if shared("FORWARD_SPECIAL", "SPECIAL_RIFT_BREAK"):
        A[f"{F}_SPECIAL_RIFT_BREAK"] = strike(art_r, 645, "Right", "hand", moves["FORWARD_SPECIAL"], pre=36, post=50,
                                              extra=lambda P, t, T: lean(P, -10 * math.sin(math.pi * min(1, t / T))))

    # ultimate: the one-two lands on the active frames, then a flurry in recovery
    if shared("ULTIMATE", "ULTIMATE_ORIGIN_BREAK"):
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
        if fitted:
            # forearms in front of the face, measured from the fighter's own head (D-076)
            P = lean(P, -6 * w)
            for side, sg in (("Left", 1), ("Right", -1)):
                P = reach_hand(rig, P, side, (0.085 * sg * S_fit, 0.19 * S_fit, -0.02 * S_fit), w,
                               st["pose"].get("pelvis_h", 0.95) * rig.hips_h, elbow_out=0.12, from_head=True)
            blk.append(pose_of(P, box))
            continue
        for side, sg in (("Left", 1), ("Right", -1)):
            P = move_hand(P, side, head + np.array([0.07 * sg * H, -0.2 * H, 0.05 * H]), w, pole_out=0.2)
        P = lean(P, -6 * w)
        blk.append(pose_of(P, box))
    A[f"{F}_BLOCK_HIGH"] = blk

    # ---- low block: drops onto bent knees, forearms cover the body and the
    # lead thigh, chin tucked behind the lead shoulder
    blk_low = []
    for t in range(13):
        w = ease(min(1, t / 5), "out")
        feet = {sd: guard_P[sd + "Foot"].copy() for sd in ("Left", "Right")}
        P = shift(guard_P, UPPER + ["Hips", "LHipJoint", "RHipJoint", "LeftUpLeg", "RightUpLeg"],
                  np.array([0, 0, -0.17 * H * w]))
        for sd in ("Left", "Right"):
            P = move_foot(P, sd, feet[sd])      # feet stay planted, knees bend
        chest = P["Spine2"] if "Spine2" in P else P["Head"] - np.array([0, 0, 0.28 * H])
        P = move_hand(P, "Left", chest + np.array([0.06 * H, -0.22 * H, -0.16 * H]), w, pole_out=0.25)
        P = move_hand(P, "Right", chest + np.array([-0.07 * H, -0.2 * H, 0.0]), w, pole_out=0.25)
        P = lean(P, -8 * w)
        if fitted:                                        # knees bend over the stance's own foot marks
            P = step_feet(rig, P, st, st["_lead"], drop=0.15 * S_fit * w)
        blk_low.append(pose_of(P, box))
    A[f"{F}_BLOCK_LOW"] = blk_low

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

    # ---- hit to the body: folds forward over the blow, hips driven back,
    # arms drop to cover; hit to the legs: the lead leg is knocked out from
    # under the fighter, who dips and catches the weight on the rear leg (D-069)
    lead_side = "Left" if guard_P["LeftFoot"][1] < guard_P["RightFoot"][1] else "Right"
    def react(n, fn):
        out = []
        for t in range(n):
            u = t / (n - 1)
            kk = ease(min(1.0, t / 3.0), "out") * (1 - ease(max(0.0, (u - 0.3) / 0.7)))
            out.append(pose_of(fn(kk, u), box))
        return out
    def body_hit(kk, u):
        P = shift(guard_P, list(guard_P.keys()), np.array([0, 0.1 * H * kk, -0.06 * H * kk]))
        for sd in ("Left", "Right"):
            P = move_foot(P, sd, guard_P[sd + "Foot"])
        P = lean(P, -34 * kk)
        P = lean(P, -14 * kk, about="Neck1", keys=["Head", "Head_end"])
        belly = P["Hips"] + np.array([0, -0.2 * H, 0.16 * H])
        for sd, sg in (("Left", 1), ("Right", -1)):
            P = move_hand(P, sd, belly + np.array([0.09 * sg * H, 0, 0]), kk * 0.85, pole_out=0.45)
        return P
    def leg_hit(kk, u):
        P = shift(guard_P, list(guard_P.keys()), np.array([0, 0.05 * H * kk, -0.12 * H * kk]))
        rear_side = "Right" if lead_side == "Left" else "Left"
        P = move_foot(P, rear_side, guard_P[rear_side + "Foot"])
        swept = guard_P[lead_side + "Foot"] + np.array([0, 0.2 * H, 0.1 * H]) * kk      # the struck leg is knocked back and up
        P = move_foot(P, lead_side, swept)
        P = lean(P, -16 * kk, roll_deg=(10 if lead_side == "Left" else -10) * kk)
        for sd, sg in (("Left", 1), ("Right", -1)):                                    # arms fly out for balance
            P = move_hand(P, sd, P[sd + "Hand"] + np.array([0.14 * sg * H, 0.02 * H, -0.1 * H]), kk * 0.8)
        return P
    A[f"{F}_HIT_BODY"] = react(25, body_hit)
    A[f"{F}_HIT_LOW"] = react(25, leg_hit)

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
        if fitted:                                        # fist raised beside the head, on the real arm
            P = reach_hand(rig, P, "Right", (-0.2 * S_fit, 0.03 * S_fit, 0.36 * S_fit), min(1.0, w),
                           st["pose"].get("pelvis_h", 0.95) * rig.hips_h, elbow_out=0.4, from_head=True)
        else:
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
            if fitted:
                # A walking step solved on the real legs (D-076, redone in D-082
                # after the owner found it robotic). One step of each foot per
                # loop. A foot is planted for 62% of the loop and drifts back
                # under the body as the game carries it along; near the end it
                # rolls up onto its ball, swings through 6 cm off the floor and
                # lands heel first. The pelvis rides toward the standing foot,
                # dips when both feet are down and turns with the swinging leg;
                # the shoulders turn against it, so the guard moves with the
                # step instead of sitting still on moving legs. Everything is
                # periodic over the loop (the old walk also carried the idle's
                # breathing, which jumped where the loop closed).
                S, sg = S_fit, (1 if st["_lead"] == "Left" else -1)
                rear_fit = "Right" if st["_lead"] == "Left" else "Left"
                d = min(stride * 2.0, 0.22 * S)
                dirn = 1.0 if forward else -1.0
                ph = t / float(n)
                smooth = lambda x: ease(min(1.0, max(0.0, x)))
                off, lift, heel_up, toe_up = {}, {}, {}, {}
                order = ((st["_lead"], 0.0), (rear_fit, 0.5)) if forward else ((rear_fit, 0.0), (st["_lead"], 0.5))
                for foot, shift_ph in order:
                    q = (ph + shift_ph) % 1.0
                    if q < 0.62:                                   # planted
                        o, up = 0.5 - q / 0.62, 0.0
                        heel_up[foot] = 0.04 * S * smooth((q - 0.44) / 0.18)
                        toe_up[foot] = 0.02 * S * (1.0 - smooth(q / 0.10)) if forward else 0.0
                    else:                                          # swinging
                        v = (q - 0.62) / 0.38
                        o, up = -0.5 + ease(v), 0.06 * S * math.sin(math.pi * v)
                        heel_up[foot] = 0.04 * S * (1.0 - smooth(v / 0.5))
                        toe_up[foot] = 0.02 * S * smooth((v - 0.7) / 0.3) if forward else 0.0
                    off[foot], lift[foot] = dirn * d * o, up
                side_ph = math.sin(2 * math.pi * (ph - 0.06)) * (1.0 if forward else -1.0)
                P = shift(base, list(base.keys()), np.array([sg * 0.014 * S * side_ph, 0.0, 0.0]))
                P = turn(P, -sg * 3.0 * side_ph)                   # pelvis and all: goes with the swinging leg
                hp = P["Hips"].copy()
                Rc = np.array(Matrix.Rotation(math.radians(sg * 5.5 * side_ph), 3, "Z"))
                for k in UPPER:                                    # shoulders against the pelvis
                    if k in P:
                        P[k] = Rc @ (P[k] - hp) + hp
                P = lean(P, (-3 if forward else 2))
                dip = 0.014 * S * 0.5 * (1.0 + math.cos(4 * math.pi * (ph - 0.06)))
                P = step_feet(rig, P, st, st["_lead"], off, lift, dip, heel_up, toe_up)
                out.append(pose_of(P, box))
                continue
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
    # ---- dashes (D-071): one driving step. The game moves the fighter (most
    # of the distance early), so the feet are keyed relative to the body:
    # forward, the lead foot shoots out and the body lands on it while the
    # rear foot skims in behind; back, the rear foot reaches and the lead
    # foot is dragged after it. One frame per tick of the dash.
    def dash(n, forward):
        base = idle_P(0)
        lf0, rf0 = base["LeftFoot"].copy(), base["RightFoot"].copy()
        lead = "Left" if lf0[1] < rf0[1] else "Right"
        rear = "Right" if lead == "Left" else "Left"
        first, second = (lead, rear) if forward else (rear, lead)
        sgn = -1.0 if forward else 1.0                    # toward -Y (the opponent) or away
        out = []
        for t in range(n):
            u = t / max(1, n - 1)
            reach = math.sin(math.pi * min(1.0, u / 0.55))            # first foot out and planted again
            follow = math.sin(math.pi * min(1.0, max(0.0, (u - 0.35) / 0.6)))   # second foot skims after it
            low = math.sin(math.pi * u)
            if fitted:                                    # the same step, solved on the real legs
                P = lean(base, (-13 if forward else 9) * low)
                P = step_feet(rig, P, st, st["_lead"],
                              {first: -sgn * 0.2 * S_fit * reach, second: sgn * 0.1 * S_fit * follow},
                              {first: 0.05 * S_fit * reach, second: 0.04 * S_fit * follow}, 0.06 * S_fit * low)
                out.append(pose_of(P, box))
                continue
            P = shift(base, list(base.keys()), np.array([0, 0, -0.06 * H * low]))
            P = move_foot(P, first, base[first + "Foot"] + np.array([0, sgn * 0.2 * H * reach, 0.05 * H * reach]))
            P = move_foot(P, second, base[second + "Foot"] + np.array([0, -sgn * 0.1 * H * follow, 0.04 * H * follow]))
            P = lean(P, (-13 if forward else 9) * low)
            out.append(pose_of(P, box))
        for t in range(max(0, n - 3), n):
            out[t] = Pose.blend(out[t], guard, ease((t - (n - 3) + 1) / 3.0))
        return out
    df, db = moves.get("dash", (14, 18))
    A[f"{F}_DASH_FORWARD"] = dash(int(df), True)
    A[f"{F}_DASH_BACK"] = dash(int(db), False)

    wf, wb = moves.get("walk", (2.6, 2.0))
    A[f"{F}_WALK_FORWARD"] = walk(wf, True)
    A[f"{F}_WALK_BACKWARD"] = walk(wb, False)

    # ---- fighters with their own move sets (docs/FIGHTER_COMBAT_DESIGN.md)
    if fid in OWN_SETS:
        def air(name, first, last):
            AIRBORNE[name] = (int(first), int(last))
        def joints(P, c=box):
            """Game-skeleton joint heads and tails for a source pose (on the floor, before any jump lift)."""
            p = pose_of(P, c)
            return fk(rig, p.D, p.hips)
        ctx = dict(H=H, F=F, moves=moves, guard_P=guard_P, guard=guard, box=box, pose_of=pose_of, strike=strike,
                   clip=clip, air=air, joints=joints,
                   anim_of=lambda mv: F + mv["animation"][mv["animation"].find("_"):])
        A.update(OWN_SETS[fid](ctx))

    acts = {}
    for name, poses in A.items():
        acts[name] = key_action(rig, name, poses)
        if rig.fingers:
            key_fingers(rig, acts[name], hand_curls(fid, name[len(F) + 1:], len(poses)))
    LAST_BUILD["rig"], LAST_BUILD["poses"] = rig, A        # for pose_check.report
    return acts
