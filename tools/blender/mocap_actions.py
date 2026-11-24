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
    # Kairo (D-087, owner: "a different stance more unique to him"): a
    # karate-kickboxing hybrid. Side-on and sunk on a long base, the lead
    # hand open and held out in front at chest height as a knife-hand guard,
    # the rear fist chambered palm-up at the ribs. He was an upright boxer
    # after Steve Fox before, too close to Drakon's boxing.
    "kairo": dict(clip="13_17", frame=840, facing=900, amp=0.45, bob=0.05, bob_beats=1, sway=0.02, life=2.6, heel_bounce=0.02, walk_life=1.0, lead="Left",
                  # his guard: the open lead forearm upright in front of the face, the rear fist under the chin
                  block={"Left": (0.03, 0.27, -0.09), "Right": (0.08, 0.17, -0.19)},
                  # crouch: sat on the rear heel with the back fairly upright and the guard pulled in
                  # D-107 (owner: "while crouching he kinda gets squished"): 0.47 sat him
                  # almost on his heels and the thighs crushed into the calves. A
                  # fighter's crouch: a third less deep, knees spread out, back upright.
                  crouch_pose=dict(drop=0.33, lean=13.0, chin=8.0, rear_heel=0.07,
                              pose=dict(lead_hand=(0.05, 0.31, -0.15), rear_hand=(0.10, 0.22, -0.17), lead_elbow=0.3, rear_elbow=0.3,
                                        knees=0.45)),
                  # D-107 (owner: "part of his arm is inside his body", "face deformed
                  # sideways"): the rear fist was held low at the ribs (karate chamber)
                  # with the chest turned 58 deg side-on, so the rear forearm ran into
                  # the belly and the neck turned 43 deg to face the opponent. Now a
                  # kickboxing guard: chest 38 deg, rear fist up by the chin in front
                  # of the chest, elbow out; neck turn 28 deg.
                  pose=dict(fit=True, hips=(-0.03, 0.0), pelvis_h=0.915, trunk=(3, 0), pelvis=40, shoulders=38, neck=6, chin=4,
                            lead_foot=(0.07, 0.25), rear_foot=(0.12, 0.23), lead_toe=-8, rear_toe=62, rear_heel=0.012,
                            lead_hand=(0.05, 0.43, -0.25), rear_hand=(0.10, 0.26, -0.16),
                            lead_elbow=0.2, rear_elbow=0.3, lead_palm=(-0.5, -0.6, -0.6), rear_palm="auto")),
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
    # hips_x: the pelvis carried sideways, + = toward the lead side (a slip, a weight shift)
    P = shift(P, list(P.keys()), np.array([sway + sgl * ps.get("hips_x", 0.0) * S - P["Hips"][0],
                                           -ps.get("hips", (0.0, 0.0))[0] * S - P["Hips"][1], 0.0]))
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
        if key + "_foot_abs" in ps:
            # a foot in the air (a kick): the ankle at (x, forward, height) in
            # model space, the foot pointed in line with the shin by `point` 0..1
            x, fw, z, point = ps[key + "_foot_abs"]
            # Knee and toes (D-092). The knee used to bend toward one fixed
            # direction: when the leg swung through that direction it flipped
            # (26 cm in a frame at take-off and landing, and half way up the
            # axe kick), and a foot leaving the floor snapped from its turned-out
            # stance angle to straight ahead. Now the knee bends at right
            # angles to the leg in the fore-and-aft plane (forward when the leg
            # hangs, up when it points forward, back when it is overhead), and
            # near the floor both knee and toes go over to the stance's own
            # turn-out, so leaving and landing are continuous.
            hip_j = pos[sd + "UpperLeg"]
            leg_d = _norm(np.array([x, -fw, z]) - hip_j)
            near_floor = 1.0 - min(1.0, max(0.0, (z - rig.foot_h - 0.03) / 0.32))
            yaw = math.radians(ps.get(key + "_toe", 0.0) * sx) * near_floor
            flat = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
            sag = np.array([0.0, leg_d[2], -leg_d[1]])
            hint = (flat + np.array([0.0, 0.0, 0.25])) * near_floor + sag * (1.0 - near_floor)
            d1, d2 = _ik_dirs(hip_j, np.array([x, -fw, z]), blen(sd + "UpperLeg", sd + "LowerLeg"),
                              blen(sd + "LowerLeg", sd + "Foot"), hint)
            l_thigh, l_shin = slen(sd + "UpLeg", sd + "Leg"), slen(sd + "Leg", sd + "Foot")
            toe_keys = [k for k in (sd + "ToeBase", sd + "ToeBase_end") if k in P]
            toe_len = [slen(sd + "Foot", k) for k in toe_keys]
            P[sd + "Leg"] = P[sd + "UpLeg"] + d1 * l_thigh
            P[sd + "Foot"] = P[sd + "Leg"] + d2 * l_shin
            if point >= 0.0:
                toe = _norm(d2 * point + (flat + np.array([0.0, 0.0, -0.15])) * (1.0 - point))
            else:
                # point < 0 (D-097): the ankle pulled back for a kick that lands on
                # the ball of the foot (front kick). -1 = foot about 100 degrees
                # from the shin, toes up; a pointed foot read as a ballet point.
                up = np.array([0.0, 0.0, 1.0]) - d2 * d2[2]
                up = _norm(up) if np.linalg.norm(up) > 1e-6 else flat
                flex = _norm(up - d2 * 0.18)
                base = _norm(flat + np.array([0.0, 0.0, -0.15]))
                toe = _norm(base * (1.0 + point) + flex * (-point))
            for k, n_ in zip(toe_keys, toe_len):
                P[k] = P[sd + "Foot"] + toe * n_
            P.pop(sd + "Sole", None)
            P.pop(sd + "Sole0", None)
    for sd, key, sx in ((lead, "lead", sgl), (rear, "rear", -sgl)):
        if key + "_hand" not in ps and key + "_hand_abs" not in ps:
            continue
        if key + "_hand_abs" in ps:                        # the wrist at (x, forward, height) in model space
            hx, hf, hz = ps[key + "_hand_abs"]
            wrist = np.array([hx, -hf, hz])
        else:
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
        if isinstance(palm, str) and palm == "auto":       # the hand's roll follows the elbow (retarget's rule)
            for k, ln in zip(hand_keys, hand_len):
                P[k] = P[sd + "Hand"] + d2 * ln
            P.pop(sd + "Palm", None)
            P.pop(sd + "Palm0", None)
            continue
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
FIST = {"finger": (88.0, 106.0, 80.0), "thumb": (40.0, 62.0, 84.0)}

# Hand shape per fighter (0 = open palm, 1 = fist) as (left, right), and the
# actions that override it. The capture has no finger data, so hands are
# posed per action: boxers keep fists, palm strikers keep open hands.
HANDS = {
    "kairo": (0.1, 1.0), "drakon": (1.0, 1.0), "seraphina": (0.2, 0.9),
    "nox": (0.3, 0.3), "vexa": (0.9, 0.9), "ryuen": (0.08, 0.08),
}
HANDS_BY_ACTION = {
    "SPECIAL_ORIGIN_PALM": (0.05, 0.05),         # open-palm strike
    "SPECIAL_FIREBALL": (0.04, 0.04),
    "THROW_KNEE_01": (0.5, 0.5),                # Kairo: hands closing on the collar (D-103)
    "ATTACK_RISING_UPPERCUT_01": (1.0, 1.0), "KICK_SWEEP_01": (0.6, 1.0),            # Kairo: both palms open to throw the fireball (D-101)
    # Kairo's lead hand is an open guard; it closes to punch
    "ATTACK_LIGHT_01": (1.0, 1.0), "ULTIMATE_ORIGIN_BREAK": (1.0, 1.0),
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

def curve(t, keys):
    """A keyed channel with timing (D-084). keys: (frame, value[, ease]), in
    order; `ease` says how the value ARRIVES at that key from the one before:
      "in"    slow away, then snaps in        (a strike landing)
      "out"   leaves fast, settles slowly     (recovery)
      "io"    slow both ends                  (a full stop at both keys)
      "lin"   even speed; "hold": stays on the previous value until this frame
    A key with no ease is passed THROUGH (D-090): the value follows a smooth
    curve whose speed at the key comes from the keys on either side, so the
    body does not stop dead at every pose. It still stops at a key that
    starts or ends a held value, and at the first and last key.
    Values are numbers or tuples."""
    n = len(keys)
    fr = [float(k[0]) for k in keys]
    val = [np.asarray(k[1], float) for k in keys]
    if t <= fr[0]:
        return val[0]
    if t >= fr[-1]:
        return val[-1]

    def flat(a, b):
        return bool(np.allclose(val[a], val[b], atol=1e-9))

    def slope(i):
        """speed through key i, or 0 where the motion should rest"""
        if i <= 0 or i >= n - 1 or flat(i - 1, i) or flat(i, i + 1):
            return val[i] * 0.0
        if len(keys[i]) > 2 or len(keys[i + 1]) > 2:       # an eased segment on either side: its own timing rules
            return val[i] * 0.0
        return (val[i + 1] - val[i - 1]) / max(1e-6, fr[i + 1] - fr[i - 1])

    for i in range(1, n):
        if t <= fr[i]:
            f0, f1, v0, v1 = fr[i - 1], fr[i], val[i - 1], val[i]
            h = max(1e-6, f1 - f0)
            u = (t - f0) / h
            e = keys[i][2] if len(keys[i]) > 2 else None
            # (2.6 was tried first for in/out: on the frame strips a jab then stood
            # still for four frames and arrived in one, and a recovery was over in two)
            if e == "in":
                u = u ** 1.9
            elif e == "out":
                u = 1.0 - (1.0 - u) ** 1.7
            elif e == "io":
                u = u * u * (3.0 - 2.0 * u)
            elif e == "hold":
                u = 1.0 if t >= f1 else 0.0
            elif e is None:
                if flat(i - 1, i):
                    return v0
                m0, m1 = slope(i - 1) * h, slope(i) * h
                u2, u3 = u * u, u * u * u
                return ((2 * u3 - 3 * u2 + 1) * v0 + (u3 - 2 * u2 + u) * m0
                        + (-2 * u3 + 3 * u2) * v1 + (u3 - u2) * m1)
            return v0 + (v1 - v0) * u
    return val[-1]


def follow_through(rig, poses, a1):
    """Loose parts follow on springs instead of being placed (D-093).

    Every part of a keyed pose is put exactly where its key says, on the
    frame it says: nothing lags, overshoots or settles, which is what reads
    as a robot. Here the head and neck ride a spring through the whole move
    (they nod into a blow and come back late), and after the last active
    frame `a1` the chest and both arms do too, so the return swings a little
    past the guard and settles. Up to `a1` chest and arms are untouched: the
    striking limb stays on its hit box.
    Each bone's world rotation chases its keyed rotation: stiffness from a
    natural frequency, damping below critical."""
    dt = 1.0 / FPS_OUT
    groups = ((("Neck", "Head"), 5.0, 0.5, 0),
              (("Chest", "LeftUpperArm", "LeftLowerArm", "RightUpperArm", "RightLowerArm", "LeftHand", "RightHand"), 5.5, 0.6,
               (a1 or 0) + 1))
    out = [Pose(dict(p.D), p.hips) for p in poses]
    for bones, hz, zeta, start in groups:
        w0 = 2 * math.pi * hz
        for b in bones:
            if b not in poses[0].D or start >= len(poses):
                continue
            q = Matrix(poses[start].D[b].tolist()).to_quaternion()
            vel = Vector((0.0, 0.0, 0.0))
            for f in range(start + 1, len(poses)):
                tgt = Matrix(poses[f].D[b].tolist()).to_quaternion()
                err = tgt @ q.inverted()
                if err.w < 0:
                    err = -err
                axis, ang = err.to_axis_angle()
                e = Vector(axis) * ang
                vel += (e * (w0 * w0) - vel * (2 * zeta * w0)) * dt
                step = vel * dt
                if step.length > 1e-9:
                    q = Quaternion(step.normalized(), step.length) @ q
                out[f].D[b] = np.array(q.to_matrix())
    return out


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


def kairo_keys(moves, base, g, S):
    """Kairo's attacks, pose to pose, on his stance blueprint (D-084, pushed
    further in D-085 after looking at every frame).

    Written from the rules in docs/ANIMATION_RESEARCH.md rather than taken
    from a capture: every strike has a wind-up, the hips turn first, the
    chest follows a frame or two later and the fist arrives last; the hand
    travels on an arc, the contact pose is held through the active frames
    with a small overshoot on the first, and the recovery leaves fast,
    swings a little past the stance and settles. Poses are pushed past real
    boxing (fighting-game exaggeration, one level for the whole set): `X`
    scales every turn, sink and lean. The chin drops into the blow and
    comes back up late.
    Each move returns keyed channels of the stance blueprint (pose keys of
    STYLES, plus *_hand_abs = wrist at (x, forward, height) in model space
    and *_foot_abs for a foot in the air). Kairo stands left side forward:
    lead = left, rear = right, +x is his left.
    Frames are 0-based: a0 = first active frame, a1 = last."""
    X = 1.22                                               # how far past real boxing the poses are pushed
    L, R = g["Left"], g["Right"]                           # wrists in the stance
    hips0, ph0 = base["hips"][0], base["pelvis_h"]
    pel0, sh0 = base["pelvis"], base["shoulders"]
    lf0, rf0 = base["lead_foot"], base["rear_foot"]
    tr0, chin0, neck0 = base["trunk"], base.get("chin", 0.0), base.get("neck", 10.0)
    head_z = g["Head"][2]
    chin = (0.10, 0.19, head_z - 0.17)                     # lead hand pulled in as a guard at the chin (kicks)
    cheek = R                                              # the rear fist stays chambered at the ribs (karate)
    hik = (0.20, 0.13, R[2] + 0.04)                        # hikite: the lead hand pulled back to its own ribs as the rear fist goes out
    FL, FR = g["feet"]["Left"], g["feet"]["Right"]         # ankles in the stance
    out = {}

    def win(mv):
        a0 = mv["startup"] - 1
        a1 = mv["startup"] + mv["active"] - 2
        return a0, a1, mv["startup"] + mv["active"] - 1 + mv["recovery"], mv["hc"][0], mv["hc"][1]

    def pel(d):
        return pel0 + d * X

    def sho(d):
        return sh0 + d * X

    def low(d):                                            # pelvis height, d = sink as a share of standing
        return ph0 - d * X

    def lean(f, sd=0.0):
        return (tr0[0] + f * X, tr0[1] + sd * X)

    def settle(T, back, rest, depth=0.012):
        """the last keys of a pelvis-height track: the weight catches itself (a
        small dip) as the body comes home, instead of stopping dead"""
        return [(back, rest - depth), (T - 2, rest)]

    def head(a0, a1, T, drop=7.0):
        """chin down into the blow, up again a few frames after the body"""
        return {"chin": [(0, chin0), (a0, chin0 + drop, "in"), (a1 + 3, chin0 + drop), (T - 3, chin0)],
                "neck": [(0, neck0), (a0, neck0 + 5, "in"), (a1 + 3, neck0 + 4), (T - 3, neck0)]}

    # Jab: no wind-up to speak of; the lead shoulder and hip go in with the fist
    a0, a1, T, hx, hz = win(moves["LIGHT"])
    hit = (0.02, hx + 0.08, hz)                            # arm all but locked out (0.85 of its length read as a bent-arm push)
    out["LIGHT"] = dict(_recover=1.7, **head(a0, a1, T, 4.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "hips": [(0, (hips0, 0)), (1, (hips0 - 0.015, 0)), (a0, (hips0 + 0.075, 0), "in"), (a1, (hips0 + 0.07, 0)),
                 (a1 + 5, (hips0 - 0.012, 0), "out"), (T - 2, (hips0, 0))],
        "pelvis": [(0, pel0), (a0 - 1, pel(12), "in"), (a1, pel(12)), (a1 + 5, pel(-2), "out"), (T - 2, pel0)],
        "shoulders": [(0, sh0), (1, sho(-4)), (a0, sho(22), "in"), (a1, sho(20)), (a1 + 5, sho(-3), "out"), (T - 2, sh0)],
        "pelvis_h": [(0, ph0), (a0, low(0.012), "in"), (a1, low(0.012))] + settle(T, a1 + 5, ph0, 0.008),
        "lead_foot": [(0, lf0), (a0, (lf0[0], lf0[1] + 0.06), "in"), (a1 + 2, (lf0[0], lf0[1] + 0.06)), (T - 3, lf0)],
        "rear_heel": [(0, 0.03), (a0, 0.06, "in"), (a1 + 5, 0.03)],
        "lead_hand_abs": [(0, L), (1, (L[0] + 0.02, L[1] - 0.12, L[2] - 0.02), "out"),   # the guard hand is already out: it snaps back to punch
                          (a0, (hit[0], hit[1] + 0.035, hit[2]), "in"),
                          (a0 + 1, hit), (a1, hit), (a1 + 4, (L[0], L[1] - 0.02, L[2] + 0.02), "out"), (T - 2, L)],
        "lead_elbow": [(0, 0.2), (a0, 0.05), (a1 + 4, 0.2)],
    })

    # Cross: sit back and load, drive off the rear foot, hip then chest then fist
    a0, a1, T, hx, hz = win(moves["HEAVY"])
    hit = (0.03, hx + 0.02, hz)
    out["HEAVY"] = dict(_recover=1.9, **head(a0, a1, T, 9.0), **{
        "rear_palm": "auto",
        "hips": [(0, (hips0, 0)), (7, (hips0 - 0.075, 0)), (a0, (hips0 + 0.11, 0), "in"), (a1, (hips0 + 0.105, 0)),
                 (a1 + 8, (hips0 - 0.015, 0), "out"), (T - 3, (hips0, 0))],
        "pelvis_h": [(0, ph0), (7, low(0.05)), (a0, low(0.03)), (a1, low(0.03)), (a1 + 6, ph0 + 0.004, "out")] + settle(T, a1 + 11, ph0),
        "pelvis": [(0, pel0), (6, pel(14)), (a0 - 2, pel(-40), "in"), (a1, pel(-42)), (a1 + 8, pel(4), "out"), (T - 3, pel0)],
        "shoulders": [(0, sh0), (7, sho(24)), (a0 - 1, sho(-72), "in"), (a0, sho(-80)), (a1, sho(-76)), (a1 + 8, sho(5), "out"), (T - 3, sh0)],
        "trunk": [(0, tr0), (7, lean(-5)), (a0, lean(9), "in"), (a1, lean(8)), (a1 + 8, lean(-1.5), "out"), (T - 3, tr0)],
        "lead_foot": [(0, lf0), (5, lf0), (a0 - 1, (lf0[0], lf0[1] + 0.09), "in"), (a1 + 4, (lf0[0], lf0[1] + 0.09)), (T - 4, lf0)],
        "rear_heel": [(0, 0.03), (5, 0.015), (a0, 0.095, "in"), (a1, 0.095), (a1 + 8, 0.03)],
        "rear_toe": [(0, base["rear_toe"]), (5, base["rear_toe"]), (a0, 8.0, "in"), (a1, 8.0), (a1 + 8, base["rear_toe"])],
        "rear_hand_abs": [(0, R), (7, (R[0] - 0.08, R[1] - 0.11, R[2] - 0.05)),
                          (a0 - 2, (-0.07, R[1] + 0.05, R[2] - 0.03), "in"),
                          (a0, (hit[0], hit[1] + 0.04, hit[2]), "in"), (a0 + 1, hit), (a1, hit),
                          (a1 + 5, (R[0] + 0.03, R[1] + 0.06, R[2] - 0.02), "out"), (T - 3, R)],
        "lead_hand_abs": [(0, L), (7, (L[0] - 0.02, L[1] + 0.07, L[2] + 0.02)),
                          (a0, hik, "in"), (a1 + 3, hik), (T - 3, L)],
        "lead_palm": [(0, base["lead_palm"]), (7, base["lead_palm"]), (a0, (0.0, 0.0, 1.0), "in"), (a1 + 3, (0.0, 0.0, 1.0)), (T - 3, base["lead_palm"])],
        "rear_elbow": [(0, 0.1), (a0, 0.06), (a1 + 5, 0.1)],
    })

    # Front kick (down + heavy; the old body hook's frame data). D-096, from
    # the owner's look at the side-by-side video ("extend his leg more"): the
    # ankle used to stop at the middle of the hitbox with the hips pushed 10
    # cm forward, so the leg arrived half bent. Now: a small dip onto the lead
    # foot, the rear knee driven up high into the chamber, the foot snaps out
    # to the far part of the box (the leg nearly straight, toes pointed), the
    # trunk leans back to balance it and the standing heel lifts; then the
    # foot comes back fast through the same chamber and is set down.
    a0, a1, T, hx, hz = win(moves["DOWN_HEAVY"])
    # Feet (D-097, owner: "straight like a ballerina, not a kick"): the toes
    # are pulled back from the chamber on and the kick lands on the ball of
    # the foot (point < 0 = ankle flexed, see the *_foot_abs solver).
    chamber = (FR[0] * 0.35, 0.22, 0.70, -0.3)             # knee at the chest, foot tucked under it, toes up
    out_far = (0.0, hx + 0.17, hz - 0.01, -0.95)            # ankle in the far part of the box: leg ~0.95 straight
    out_hold = (0.0, hx + 0.15, hz - 0.02, -0.95)
    snap = (0.0, hx - 0.04, hz - 0.07, -0.7)                 # half way out: the shin swings up and forward
    recoil = (FR[0] * 0.3, 0.26, 0.66, -0.4)
    out["DOWN_HEAVY"] = dict(_recover=1.4, **head(a0, a1, T, 3.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "hips": [(0, (hips0, 0)), (2, (hips0 + 0.03, 0), "io"), (5, (hips0 + 0.05, 0)), (a0, (hips0 - 0.01, 0), "in"),
                 (a1, (hips0 - 0.01, 0)), (a1 + 4, (hips0 + 0.04, 0), "out"), (T - 3, (hips0, 0))],
        "pelvis_h": [(0, ph0), (2, ph0 - 0.02, "io"), (5, ph0 + 0.03, "out"), (a0, ph0 + 0.05, "in"), (a1, ph0 + 0.045),
                     (a1 + 4, ph0 + 0.03)] + settle(T, a1 + 9, ph0, 0.018),
        "pelvis": [(0, pel0), (2, pel(4)), (5, pel(-26)), (a0, pel(-38), "in"), (a1, pel(-37)), (a1 + 6, pel(-12), "out"), (T - 3, pel0)],
        "shoulders": [(0, sh0), (2, sho(6)), (5, sho(-10)), (a0, sho(-16), "in"), (a1, sho(-16)), (a1 + 6, sho(-4), "out"), (T - 3, sh0)],
        "trunk": [(0, tr0), (2, lean(2.5)), (5, lean(-5)), (a0, lean(-19), "in"), (a1, lean(-18)), (a1 + 5, lean(-7), "out"), (T - 3, tr0)],
        "lead_heel": [(0, 0.0), (4, 0.02), (a0, 0.065, "in"), (a1, 0.06), (a1 + 6, 0.01), (T - 4, 0.0)],
        "rear_foot_abs": [(0, FR + (0.0,)), (3, (FR[0] * 0.7, 0.10, 0.34, 0.0), "out"), (a0 - 3, chamber, "out"),
                          (a0 - 1, snap, "in"), (a0, out_far), (a0 + 1, out_hold), (a1, out_hold),
                          (a1 + 3, recoil, "out"), (a1 + 6, (FR[0] * 0.8, FR[1] * 0.6, 0.30, -0.1)), (a1 + 8, (FR[0] * 0.9, FR[1] * 0.85, 0.12, 0.0)), (a1 + 10, FR + (0.0,), "in")],
        "lead_hand_abs": [(0, L), (4, (L[0], L[1] - 0.04, L[2] + 0.03)), (a0, chin, "in"), (a1 + 4, chin), (T - 3, L)],
        "rear_hand_abs": [(0, R), (4, (R[0] - 0.06, R[1] - 0.02, R[2] - 0.03)), (a0, (-0.28, 0.07, R[2] - 0.12), "in"),
                          (a1 + 3, (-0.27, 0.05, R[2] - 0.10)), (T - 3, R)],
    })

    # Counter strike (the Rift Guard's answer): after the open-hand parry the
    # chambered fist goes straight through the face, hips and shoulders behind it
    a0, a1, T, hx, hz = win(moves["FOLLOWUP"])
    hit = (0.03, hx + 0.03, hz)
    out["FOLLOWUP"] = dict(_recover=1.9, **head(a0, a1, T, 8.0), **{
        "rear_palm": "auto", "lead_palm": "auto",
        "hips": [(0, (hips0 - 0.05, 0)), (a0, (hips0 + 0.11, 0), "in"), (a1, (hips0 + 0.10, 0)), (a1 + 8, (hips0 - 0.01, 0), "out"), (T - 3, (hips0, 0))],
        "pelvis_h": [(0, low(0.045)), (a0, low(0.035)), (a1, low(0.035)), (a1 + 6, ph0 + 0.004, "out")] + settle(T, a1 + 10, ph0),
        "pelvis": [(0, pel(8)), (a0 - 1, pel(-40), "in"), (a1, pel(-42)), (a1 + 8, pel(4), "out"), (T - 3, pel0)],
        "shoulders": [(0, sho(12)), (a0, sho(-78), "in"), (a1, sho(-74)), (a1 + 8, sho(5), "out"), (T - 3, sh0)],
        "trunk": [(0, lean(-3)), (a0, lean(9), "in"), (a1, lean(8)), (a1 + 8, lean(-1.5), "out"), (T - 3, tr0)],
        "lead_foot": [(0, lf0), (a0 - 1, (lf0[0], lf0[1] + 0.07), "in"), (a1 + 4, (lf0[0], lf0[1] + 0.07)), (T - 4, lf0)],
        "rear_heel": [(0, 0.012), (a0, 0.095, "in"), (a1, 0.095), (a1 + 8, 0.012)],
        "rear_toe": [(0, base["rear_toe"]), (a0, 8.0, "in"), (a1, 8.0), (a1 + 8, base["rear_toe"])],
        "rear_hand_abs": [(0, (R[0] - 0.04, R[1] - 0.06, R[2])), (a0 - 2, (-0.08, R[1] + 0.08, R[2] + 0.10), "in"),
                          (a0, (hit[0], hit[1] + 0.04, hit[2]), "in"), (a0 + 1, hit), (a1, hit),
                          (a1 + 5, (R[0] + 0.03, R[1] + 0.06, R[2]), "out"), (T - 3, R)],
        "rear_elbow": [(0, 0.1), (a0, 0.06), (a1 + 5, 0.1)],
        "lead_hand_abs": [(0, (L[0] - 0.06, L[1] - 0.08, L[2] + 0.06)), (a0, hik, "in"), (a1 + 3, hik), (T - 3, L)],
    })

    # Low kick: weight onto the lead leg, the rear shin whips round into theirs.
    # D-108 (owner: "his body doesn't turn with the kick, his arm goes
    # sideways"): the chest now turns over with the hips (it stayed back, the
    # body twisted against itself) and the rear arm drops to his own hip
    # instead of flinging 33 cm out to the side. Second pass (owner: "he needs
    # to lean with that kick, check how it's done in Street Fighter"): the
    # fighting-game low roundhouse, the upper body counter-leans back and away
    # from the kicking leg with the head over the bent standing leg, so leg and
    # body make one long line
    a0, a1, T, hx, hz = win(moves["KICK"])
    home = FR
    out["KICK"] = dict(_recover=1.3, **head(a0, a1, T, 3.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "hips": [(0, (hips0, 0)), (4, (hips0 + 0.04, 0)), (a0, (hips0 + 0.06, 0), "in"), (a1, (hips0 + 0.06, 0)), (a1 + 6, (hips0, 0), "out")],
        "pelvis_h": [(0, ph0), (4, low(0.04)), (a0, low(0.055), "in"), (a1, low(0.055))] + settle(T, a1 + 9, ph0, 0.018),
        "pelvis": [(0, pel0), (4, pel(-14)), (a0, pel(-74), "in"), (a1, pel(-72)), (a1 + 4, pel(-40), "out"), (a1 + 10, pel0)],
        "shoulders": [(0, sh0), (4, sho(10)), (a0, sho(-58), "in"), (a1, sho(-56)), (a1 + 4, sho(-30), "out"), (a1 + 10, sh0)],
        "trunk": [(0, tr0), (4, lean(-5, 6)), (a0, lean(-26, 24), "in"), (a1, lean(-25, 23)), (a1 + 4, lean(-11, 10), "out"), (a1 + 10, tr0)],
        "lead_heel": [(0, 0.0), (a0, 0.045, "in"), (a1, 0.045), (a1 + 6, 0.0)],
        "lead_toe": [(0, base["lead_toe"]), (a0, base["lead_toe"] + 60, "in"), (a1, base["lead_toe"] + 60), (a1 + 8, base["lead_toe"])],
        "rear_foot_abs": [(0, home + (0.0,)), (4, (-0.22, 0.02, 0.34, 0.6)), (a0 - 1, (-0.36, hx - 0.36, hz + 0.16, 1.0), "in"),
                          (a0, (0.02, hx + 0.04, hz + 0.09, 1.0), "in"), (a1, (0.12, hx - 0.04, hz + 0.05, 1.0)),
                          (a1 + 3, (-0.14, 0.05, 0.28, 0.6), "lin"), (a1 + 9, home + (0.0,))],
        # the kicking side's arm reaches forward and down along the kick, at
        # chest height (the owner's reference picture; D-110 threw it up and
        # back behind the head: "the hands swing totally wrong"), the other
        # hand stays up at the face
        "rear_hand_abs": [(0, R), (4, (R[0] + 0.01, R[1] - 0.05, R[2] - 0.06)), (a0, (-0.24, 0.36, R[2] - 0.22), "in"),
                          (a1, (-0.25, 0.34, R[2] - 0.24)), (a1 + 5, (-0.15, 0.26, R[2] - 0.10), "out"), (T - 3, R)],
        "rear_elbow": [(0, 0.1), (a0, 0.08), (a1, 0.08), (a1 + 6, 0.1)],
        # the guard hand rides with the leaning chest (a fixed chin point in
        # model space was left behind by the lean and pulled the arm straight)
        "lead_hand": [(0, base["lead_hand"]), (a0, (base["lead_hand"][0] + 0.04, 0.13, base["lead_hand"][2] + 0.07), "in"),
                      (a1 + 3, (base["lead_hand"][0] + 0.04, 0.13, base["lead_hand"][2] + 0.07)), (T - 3, base["lead_hand"])],
        "lead_elbow": [(0, 0.2), (a0, 0.5), (a1 + 3, 0.5), (T - 3, 0.2)],
    })

    # Origin Palm: a long load onto the rear leg with the palm chambered at
    # the ribs and the guard hand still up, then a lunging open-hand thrust
    a0, a1, T, hx, hz = win(moves["SPECIAL"])
    hit = (0.0, hx - 0.08, hz)
    out["SPECIAL"] = dict(_recover=1.8, **head(a0, a1, T, 6.0), **{
        "rear_palm": "auto",
        "lead_palm": [(0, base["lead_palm"]), (8, (0.0, 0.0, 1.0)), (a0 - 3, (0.0, -0.4, 1.0)), (a0, (0.0, -1.0, 0.3), "in"),
                      (a1, (0.0, -1.0, 0.3)), (a1 + 8, base["lead_palm"])],
        "hips": [(0, (hips0, 0)), (8, (hips0 - 0.11, 0)), (a0, (hips0 + 0.19, 0), "in"), (a1, (hips0 + 0.18, 0)),
                 (a1 + 11, (hips0 - 0.015, 0), "out"), (T - 4, (hips0, 0))],
        "pelvis_h": [(0, ph0), (8, low(0.075)), (a0, low(0.06), "in"), (a1, low(0.06)), (a1 + 9, ph0 + 0.004, "out")] + settle(T, a1 + 15, ph0),
        "pelvis": [(0, pel0), (8, pel(-18)), (a0 - 2, pel(26), "in"), (a1, pel(26)), (a1 + 11, pel(-3), "out"), (T - 4, pel0)],
        "shoulders": [(0, sh0), (8, sho(-28)), (a0, sho(24), "in"), (a1, sho(23)), (a1 + 11, sho(-4), "out"), (T - 4, sh0)],
        "trunk": [(0, tr0), (8, lean(-5)), (a0, lean(10), "in"), (a1, lean(9)), (a1 + 11, lean(-1.5), "out"), (T - 4, tr0)],
        "lead_foot": [(0, lf0), (8, (lf0[0], lf0[1] - 0.04)), (a0 - 1, (lf0[0], lf0[1] + 0.23), "in"), (a1 + 4, (lf0[0], lf0[1] + 0.23)), (T - 5, lf0)],
        "lead_heel": [(0, 0.0), (8, 0.035), (a0 - 1, 0.0, "in")],
        "rear_heel": [(0, 0.03), (8, 0.0), (a0, 0.09, "in"), (a1, 0.09), (a1 + 10, 0.03)],
        "lead_hand_abs": [(0, L), (8, (0.22, 0.0, hz - 0.20)), (a0 - 3, (0.16, 0.22, hz - 0.12), "in"),
                          (a0, (hit[0], hit[1] + 0.045, hit[2]), "in"), (a0 + 1, hit), (a1, hit),
                          (a1 + 7, (L[0], L[1] + 0.06, L[2] - 0.05), "out"), (T - 4, L)],
        "lead_elbow": [(0, 0.15), (8, 0.35), (a0, 0.05), (a1 + 7, 0.15)],
        "rear_hand_abs": [(0, R), (8, (-0.10, 0.24, R[2] + 0.20)), (a0, (R[0], R[1] - 0.04, R[2]), "in"), (a1 + 4, (R[0], R[1] - 0.04, R[2])), (T - 4, R)],
    })

    # Fireball (down + special, D-101): both open palms are drawn back to the
    # rear hip as he sinks and coils away, then driven forward together at
    # chest height as the fireball leaves on the first active frame; the
    # palms stay out a moment, then he settles back into the stance.
    a0, a1, T, hx, hz = win(moves["DOWN_SPECIAL"])
    cup_l = (-0.04, -0.02, ph0 * 0.0 + R[2] - 0.20)        # lead palm over the rear hip
    cup_r = (-0.12, -0.06, R[2] - 0.28)                    # rear palm under it
    push_l = (0.03, hx - 0.30, hz + 0.02)
    push_r = (-0.05, hx - 0.33, hz - 0.08)
    out["DOWN_SPECIAL"] = dict(_recover=1.6, **head(a0, a1, T, 5.0), **{
        "lead_palm": [(0, base["lead_palm"]), (a0 - 4, (0.0, 0.3, -1.0)), (a0, (0.0, -1.0, 0.25), "in"), (a1 + 6, (0.0, -1.0, 0.25)),
                      (T - 4, base["lead_palm"])],
        "rear_palm": [(0, (0.0, 0.0, 1.0)), (a0 - 4, (0.0, 0.3, 1.0)), (a0, (0.0, -1.0, -0.25), "in"), (a1 + 6, (0.0, -1.0, -0.25)),
                      (T - 4, (0.0, 0.0, 1.0))],
        "hips": [(0, (hips0, 0)), (a0 - 4, (hips0 - 0.10, 0), "io"), (a0, (hips0 + 0.14, 0), "in"), (a1 + 5, (hips0 + 0.13, 0)),
                 (T - 4, (hips0, 0), "io")],
        "pelvis_h": [(0, ph0), (a0 - 4, low(0.09), "io"), (a0, low(0.06), "in"), (a1 + 5, low(0.06))] + settle(T, T - 8, ph0),
        "pelvis": [(0, pel0), (a0 - 4, pel(22), "io"), (a0, pel(-30), "in"), (a1 + 5, pel(-28)), (T - 4, pel0, "io")],
        "shoulders": [(0, sh0), (a0 - 4, sho(30), "io"), (a0, sho(-46), "in"), (a1 + 5, sho(-44)), (T - 4, sh0, "io")],
        "trunk": [(0, tr0), (a0 - 4, lean(-4), "io"), (a0, lean(9), "in"), (a1 + 5, lean(8)), (T - 4, tr0, "io")],
        "lead_foot": [(0, lf0), (a0 - 1, (lf0[0], lf0[1] + 0.12), "in"), (a1 + 6, (lf0[0], lf0[1] + 0.12)), (T - 4, lf0, "io")],
        "rear_heel": [(0, 0.012), (a0 - 4, 0.0), (a0, 0.08, "in"), (a1 + 5, 0.08), (T - 4, 0.012)],
        "lead_hand_abs": [(0, L), (a0 - 4, cup_l, "io"), (a0, (push_l[0], push_l[1] + 0.04, push_l[2]), "in"), (a0 + 1, push_l),
                          (a1 + 6, push_l), (T - 3, L, "io")],
        "rear_hand_abs": [(0, R), (a0 - 4, cup_r, "io"), (a0, (push_r[0], push_r[1] + 0.04, push_r[2]), "in"), (a0 + 1, push_r),
                          (a1 + 6, push_r), (T - 3, R, "io")],
        "lead_elbow": [(0, 0.2), (a0 - 4, 0.3), (a0, 0.08), (a1 + 6, 0.08), (T - 3, 0.2)],
        "rear_elbow": [(0, 0.05), (a0 - 4, 0.25), (a0, 0.1), (a1 + 6, 0.1), (T - 3, 0.05)],
    })

    # D-103: the three moves that filled the gaps in his kit (owner: "yes" to
    # a throw, a sweep and an anti-air).
    # Rising Uppercut (down + light): a quick dip with the rear fist dropped
    # to the hip, then he explodes up onto his toes and the fist drives up
    # past his head, the body turning behind it; a slow landing (punishable).
    a0, a1, T, hx, hz = win(moves["DOWN_LIGHT"])
    u_low = (-0.16, 0.04, R[2] - 0.24)
    u_hit = (0.02, hx - 0.14, hz + 0.08)
    u_top = (0.0, hx - 0.18, hz + 0.20)
    out["DOWN_LIGHT"] = dict(_recover=1.7, **head(a0, a1, T, -6.0), **{
        "hips": [(0, (hips0, 0)), (2, (hips0 - 0.02, 0), "io"), (a0, (hips0 + 0.10, 0), "in"), (a1, (hips0 + 0.12, 0)), (T - 4, (hips0, 0), "io")],
        "pelvis_h": [(0, ph0), (2, low(0.12), "io"), (a0, ph0 + 0.06, "out"), (a1, ph0 + 0.075)] + settle(T, T - 8, ph0, 0.03),
        "pelvis": [(0, pel0), (2, pel(16), "io"), (a0, pel(-44), "in"), (a1, pel(-48)), (T - 4, pel0, "io")],
        "shoulders": [(0, sh0), (2, sho(24), "io"), (a0, sho(-70), "in"), (a1, sho(-76)), (T - 4, sh0, "io")],
        "trunk": [(0, tr0), (2, lean(12), "io"), (a0, lean(-6), "in"), (a1, lean(-12)), (T - 4, tr0, "io")],
        "lead_heel": [(0, 0.0), (2, 0.0), (a0, 0.07, "in"), (a1, 0.08), (T - 5, 0.0)],
        "rear_heel": [(0, 0.012), (2, 0.0), (a0, 0.12, "in"), (a1, 0.12), (T - 5, 0.012)],
        "rear_toe": [(0, base["rear_toe"]), (a0, 10.0, "in"), (a1, 8.0), (T - 4, base["rear_toe"])],
        "rear_hand_abs": [(0, R), (2, u_low, "io"), (a0, u_hit, "in"), (a1, u_top), (a1 + 6, u_top), (T - 3, R, "io")],
        "rear_elbow": [(0, 0.05), (2, 0.2), (a0, 0.02), (a1 + 6, 0.02), (T - 3, 0.05)],
        "lead_hand_abs": [(0, L), (2, (L[0] - 0.02, L[1] - 0.06, L[2] - 0.08), "io"), (a0 + 2, hik, "io"), (a1 + 6, hik), (T - 3, L, "io")],
    })

    # Leg Sweep (down + kick): he drops deep with the lead hand near the floor
    # for balance and the rear leg swings round low along the ground into the
    # opponent's ankles, then he draws it back and rises.
    a0, a1, T, hx, hz = win(moves["DOWN_KICK"])
    sw_back = (FR[0] * 1.1, FR[1] - 0.10, 0.10, 0.4)
    sw_hit = (0.06, hx - 0.06, max(hz, 0.11), 0.75)
    sw_through = (0.18, hx - 0.16, max(hz, 0.11), 0.75)
    deep = ph0 - 0.40
    out["DOWN_KICK"] = dict(_recover=1.5, **head(a0, a1, T, 6.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "hips": [(0, (hips0, 0)), (4, (hips0 + 0.04, 0), "io"), (a0, (hips0 + 0.08, 0)), (a1 + 6, (hips0 + 0.06, 0)), (T - 4, (hips0, 0), "io")],
        "pelvis_h": [(0, ph0), (4, deep, "io"), (a1 + 6, deep + 0.02), (T - 6, ph0, "io")],
        "pelvis": [(0, pel0), (4, pel(10), "io"), (a0, pel(-40), "in"), (a1, pel(-52)), (a1 + 7, pel(-20), "io"), (T - 4, pel0, "io")],
        "shoulders": [(0, sh0), (4, sho(10), "io"), (a0, sho(-24), "in"), (a1, sho(-30)), (T - 4, sh0, "io")],
        "trunk": [(0, tr0), (4, lean(22, 6), "io"), (a0, lean(28, 8)), (a1 + 6, lean(24, 6)), (T - 4, tr0, "io")],
        "lead_heel": [(0, 0.0), (4, 0.05), (a1 + 6, 0.05), (T - 5, 0.0)],
        "_feet_abs": (0, T - 1),               # the keyed leg all the way (handing back to the stance solver mid-move jumped)
        "rear_foot_abs": [(0, FR + (0.0,)), (2, FR + (0.0,)), (4, sw_back, "io"), (a0, sw_hit, "in"), (a1, sw_through), (a1 + 5, (FR[0] * 0.6, 0.20, 0.10, 0.4), "out"),
                          (a1 + 9, FR + (0.0,), "in")],
        "lead_hand_abs": [(0, L), (4, (0.26, 0.30, 0.42), "io"), (a1 + 6, (0.26, 0.30, 0.42)), (T - 3, L, "io")],
        "rear_hand_abs": [(0, R), (4, (chin[0] - 0.08, chin[1] - 0.02, chin[2] - 0.40), "io"),     # the guard drops with him
                          (a1 + 6, (chin[0] - 0.08, chin[1] - 0.02, chin[2] - 0.38)), (T - 3, R, "io")],
    })

    # Knee Throw (light + kick): both hands seize the collar, he pulls the
    # opponent in onto a rising knee and lets go with a short push. The game
    # holds the opponent from the grab and lands the throw on the knee
    # (MoveData.throw_release_frame = 12 = frame kn + 1); the long shove that
    # followed the knee is gone (owner: "it does a hit and a knee after, why").
    a0, a1, T, hx, hz = win(moves["THROW"])
    # D-104 (owner: "it does not look like he is grabbing"): the hands reach
    # round the back of the opponent's neck (the game draws the opponent in
    # to 0.58 m and tips them forward), then pull the head down onto the knee.
    grab_l = (0.11, 0.62, hz + 0.24)
    grab_r = (-0.07, 0.60, hz + 0.22)
    pull_l = (0.10, 0.50, hz + 0.06)
    pull_r = (-0.06, 0.48, hz + 0.04)
    shove_l = (0.08, hx - 0.14, hz + 0.06)
    shove_r = (-0.08, hx - 0.16, hz + 0.0)
    kn = a1 + 6                                            # the knee lands
    sh = kn + 3                                            # the hands let go with a short push
    knee_up = (FR[0] * 0.4, 0.26, 0.62, 0.35)
    # no recovery warp: the knee is keyed after the grab's active frames and
    # must play on exactly the frame the throw lands (throw_release_frame)
    out["THROW"] = dict(**head(a0, a1, T, 8.0), **{
        "lead_palm": [(0, base["lead_palm"]), (a0, (0.0, 0.4, -1.0), "in"), (kn + 2, (0.0, 0.4, -1.0)), (T - 3, base["lead_palm"])],
        "rear_palm": [(0, (0.0, 0.0, 1.0)), (a0, (0.0, 0.4, -1.0), "in"), (kn + 2, (0.0, 0.4, -1.0)), (T - 3, (0.0, 0.0, 1.0))],
        "hips": [(0, (hips0, 0)), (a0, (hips0 + 0.10, 0), "in"), (kn - 3, (hips0 + 0.02, 0)), (kn, (hips0 + 0.10, 0), "in"),
                 (sh - 2, (hips0 + 0.04, 0)), (sh, (hips0 + 0.16, 0), "in"), (sh + 4, (hips0 + 0.14, 0)), (T - 4, (hips0, 0), "io")],
        "pelvis_h": [(0, ph0), (a0, low(0.04), "in"), (kn, ph0 + 0.04, "in"), (sh, low(0.05), "in")] + settle(T, T - 7, ph0),
        "pelvis": [(0, pel0), (a0, pel(-10), "in"), (kn, pel(-36), "in"), (sh, pel(-20), "in"), (T - 4, pel0, "io")],
        "shoulders": [(0, sh0), (a0, sho(-30), "in"), (kn, sho(-40)), (sh, sho(-46), "in"), (T - 4, sh0, "io")],
        "trunk": [(0, tr0), (a0, lean(8), "in"), (kn, lean(14), "in"), (sh, lean(10), "in"), (T - 4, tr0, "io")],
        "rear_heel": [(0, 0.012), (a0, 0.04), (sh, 0.09, "in"), (T - 4, 0.012)],
        "_feet_abs": (0, T - 1),
        "rear_foot_abs": [(0, FR + (0.0,)), (kn - 5, FR + (0.0,)), (kn - 3, (FR[0] * 0.7, 0.02, 0.26, 0.2), "io"), (kn - 1, (FR[0] * 0.5, 0.16, 0.50, 0.3)), (kn, knee_up),
                          (kn + 2, knee_up), (kn + 5, FR + (0.0,), "in")],
        "lead_hand_abs": [(0, L), (a0, grab_l, "in"), (a1 + 1, grab_l), (kn - 1, pull_l, "io"), (kn + 2, pull_l), (sh, shove_l, "in"),
                          (sh + 4, shove_l), (T - 3, L, "io")],
        "rear_hand_abs": [(0, R), (a0, grab_r, "in"), (a1 + 1, grab_r), (kn - 1, pull_r, "io"), (kn + 2, pull_r), (sh, shove_r, "in"),
                          (sh + 4, shove_r), (T - 3, R, "io")],
        "lead_elbow": [(0, 0.2), (a0, 0.3), (kn, 0.45), (sh, 0.1), (T - 3, 0.2)],
        "rear_elbow": [(0, 0.05), (a0, 0.3), (kn, 0.45), (sh, 0.1), (T - 3, 0.05)],
    })

    # Rift Break: an axe kick. The rear leg swings up past the head as he
    # closes in, then the heel is brought down through the chest
    a0, a1, T, hx, hz = win(moves["FORWARD_SPECIAL"])
    top = (-0.03, 0.46, head_z + 0.06, 0.85)
    out["FORWARD_SPECIAL"] = dict(_recover=1.35, **{
        "lead_palm": "auto", "rear_palm": "auto",
        "chin": [(0, chin0), (a0 - 4, chin0 - 4), (a0, chin0 + 8, "in"), (a1 + 3, chin0 + 8), (T - 3, chin0)],
        "hips": [(0, (hips0, 0)), (6, (hips0 + 0.05, 0)), (a0, (hips0 + 0.10, 0)), (a1, (hips0 + 0.10, 0)),
                 (a1 + 10, (hips0, 0), "out")],
        "pelvis_h": [(0, ph0), (5, low(0.03)), (a0 - 4, ph0 + 0.055, "out"), (a0, ph0 + 0.02, "in"), (a1, ph0 - 0.01)]
                    + settle(T, a1 + 10, ph0, 0.02),
        "pelvis": [(0, pel0), (6, pel(-22)), (a0 - 4, pel(-34)), (a1, pel(-34)), (a1 + 10, pel0, "out")],
        "shoulders": [(0, sh0), (6, sho(-10)), (a0 - 4, sho(-22)), (a1, sho(-26)), (a1 + 10, sh0, "out")],
        "trunk": [(0, tr0), (5, lean(4)), (a0 - 4, lean(-13), "out"), (a0, lean(2), "in"), (a1, lean(7)), (a1 + 10, tr0, "out")],
        "lead_heel": [(0, 0.0), (a0 - 4, 0.05), (a0, 0.02), (a1 + 3, 0.0)],
        "rear_foot_abs": [(0, FR + (0.0,)), (6, (FR[0] * 0.6, 0.10, 0.50, 0.4)), (a0 - 4, top, "out"), (a0 - 2, top),
                          (a0, (0.0, hx - 0.06, hz + 0.20, 0.35), "in"), (a1, (0.0, hx - 0.08, hz - 0.22, 0.25), "lin"),
                          (a1 + 4, (FR[0] * 0.7, 0.30, FR[2] + 0.04, 0.0), "out"), (a1 + 9, FR + (0.0,))],
        "lead_hand_abs": [(0, L), (a0 - 4, chin), (a1 + 4, chin), (T - 4, L)],
        "rear_hand_abs": [(0, R), (a0 - 4, (-0.30, -0.02, R[2] + 0.10)), (a0, (-0.33, 0.10, R[2] - 0.12), "in"),
                          (a1 + 3, (-0.33, 0.10, R[2] - 0.12)), (T - 4, R)],
    })

    # Rift Guard (the counter stance): he sits back onto the rear leg and the
    # open lead hand sweeps across the centre line; the rear fist stays loaded
    mv = moves["BACK_SPECIAL"]
    c0, c1 = mv["counter"]
    T = mv["startup"] + mv["active"] - 1 + mv["recovery"]
    lh0 = base["lead_hand"]
    # D-107 (owner: "his fighting needs improvement"): the guard read as standing
    # still; he now sits clearly back, sinks and slips his head off the line
    out["BACK_SPECIAL"] = {
        "rear_palm": "auto",
        "lead_palm": [(0, base["lead_palm"]), (c0, (-0.9, -0.4, 0.0), "out"), (c1, (-0.9, -0.4, 0.0)), (T - 3, base["lead_palm"])],
        "hips": [(0, (hips0, 0)), (c0, (hips0 - 0.12, 0), "out"), (c1, (hips0 - 0.115, 0)), (T - 3, (hips0, 0))],
        "pelvis_h": [(0, ph0), (c0, low(0.085), "out"), (c0 + 5, low(0.075)), (c1, low(0.08))] + settle(T, T - 6, ph0),
        "trunk": [(0, tr0), (c0, lean(-6, 7), "out"), (c1, lean(-5, 6)), (T - 3, tr0)],
        "pelvis": [(0, pel0), (c0, pel(10), "out"), (c1, pel(10)), (T - 3, pel0)],
        "shoulders": [(0, sh0), (c0, sho(16), "out"), (c1, sho(14)), (T - 3, sh0)],
        "chin": [(0, chin0), (c0, chin0 + 8, "out"), (c1, chin0 + 8), (T - 3, chin0)],
        "lead_heel": [(0, 0.0), (c0, 0.05, "out"), (c1, 0.05), (T - 3, 0.0)],
        "lead_hand": [(0, lh0), (2, (lh0[0] + 0.10, lh0[1] - 0.06, lh0[2] + 0.02)), (c0, (-0.04, 0.34, -0.14), "out"),
                      (c1, (-0.03, 0.33, -0.15)), (T - 3, lh0)],
        "lead_elbow": [(0, 0.2), (c0, 0.45), (c1, 0.45), (T - 3, 0.2)],
    }

    # Origin Break (four hits since D-087, one every ten frames): lead
    # straight, reverse punch, rear-leg roundhouse into the ribs, and a deep
    # lunging lead straight that carries the long freeze
    mv = moves["ULTIMATE"]
    a0 = mv["startup"] - 1
    T = mv["startup"] + mv["active"] - 1 + mv["recovery"]
    hx, hz = mv["hc"]
    step_n = int(mv.get("rehit", 10))
    b1, b2, b3 = a0 + step_n, a0 + 2 * step_n, a0 + 3 * step_n
    jab = (0.02, hx - 0.14, hz + 0.12)
    cross = (0.03, hx - 0.10, hz + 0.06)
    final = (0.02, hx - 0.04, hz + 0.02)
    adv = 0.10
    # D-100 (owner: "his ultimate is boring"): same frame data and hit points,
    # four different strikes at four heights instead of three punches and a
    # mid roundhouse at one height. A coil before the first blow; 1 lunging
    # lead straight (head), 2 dropping lead hook to the body, 3 head-high rear
    # roundhouse leaning away, 4 a deep sink and an explosive rear uppercut up
    # onto the toes, held as the finishing pose before he settles.
    body = (0.16, hx - 0.40, hz - 0.30)                    # lead hook to the ribs, elbow out
    upper_low = (-0.16, 0.02, R[2] - 0.22)                 # the rear fist dropped to the hip before the uppercut
    upper = (0.02, hx - 0.34, hz + 0.10)                    # uppercut: under the chin, arm bent
    upper_top = (0.02, hx - 0.36, hz + 0.16)
    rk_lift = (FR[0] * 0.9, FR[1] - 0.06, 0.24, 0.1)              # heel peels off the floor
    rk_ch = (-0.26, 0.18, 0.64, 0.6)                       # knee up and round in front, foot trailing it                     # roundhouse chamber: knee up and out to the side
    rk_mid = (-0.16, hx * 0.45, hz - 0.04, 0.7)
    rk = (0.02, hx - 0.12, hz + 0.0, 0.7)                   # shin and instep at head height
    rk_back = (-0.24, 0.14, 0.58, 0.55)                    # knee back in front after the kick, as on the way up
    out["ULTIMATE"] = {
        "lead_palm": "auto", "rear_palm": "auto",
        "chin": [(0, chin0), (3, chin0 + 10), (a0, chin0 + 6, "in"), (b1, chin0 + 12, "in"), (b2, chin0 + 3), (b3 - 2, chin0 + 10),
                 (b3 + 1, chin0 - 6, "out"), (b3 + 8, chin0 - 5), (T - 4, chin0)],
        "hips": [(0, (hips0, 0)), (3, (hips0 - 0.05, 0), "io"), (a0, (hips0 + 0.09, 0), "in"), (b1, (hips0 + 0.12, 0), "io"),
                 (b2, (hips0 + 0.04, 0), "io"), (b3 - 2, (hips0 + 0.08, 0), "io"), (b3, (hips0 + 0.15, 0), "in"),
                 (b3 + 8, (hips0 + 0.14, 0)), (T - 4, (hips0, 0), "io")],
        "lead_foot": [(0, lf0), (a0 - 1, (lf0[0], lf0[1] + adv), "in"), (b2 + 4, (lf0[0], lf0[1] + adv)),
                      (b3 - 1, (lf0[0], lf0[1] + adv + 0.12), "in"), (b3 + 8, (lf0[0], lf0[1] + adv + 0.12)), (T - 4, lf0, "io")],
        "lead_heel": [(0, 0.0), (b2 - 4, 0.0), (b2, 0.05, "in"), (b2 + 4, 0.0), (b3 - 2, 0.0), (b3, 0.06, "in"), (b3 + 8, 0.055), (T - 5, 0.0)],
        "pelvis_h": [(0, ph0), (3, low(0.06), "io"), (a0, low(0.03), "in"), (b1 - 2, low(0.10), "io"), (b1, low(0.11)),
                     (b2 - 3, ph0 + 0.02, "out"), (b2, ph0 + 0.04), (b2 + 6, low(0.02), "io"),
                     (b3 - 3, low(0.12), "io"), (b3, ph0 + 0.035, "out"), (b3 + 3, ph0 + 0.06), (b3 + 8, ph0 + 0.055)] + settle(T, T - 7, ph0, 0.02),
        "pelvis": [(0, pel0), (3, pel(14), "io"), (a0, pel(8), "in"), (b1 - 3, pel(22), "io"), (b1, pel(28), "in"),
                   (b2 - 3, pel(-30), "io"), (b2, pel(-68), "in"), (b2 + 3, pel(-64)), (b3 - 3, pel(18), "io"),
                   (b3, pel(-46), "in"), (b3 + 8, pel(-44)), (T - 4, pel0, "io")],
        "shoulders": [(0, sh0), (3, sho(22), "io"), (a0, sho(16), "in"), (b1 - 3, sho(-10), "io"), (b1, sho(34), "in"), (b1 + 3, sho(30)),
                      (b2 - 2, sho(-20), "io"), (b2, sho(-40), "in"), (b2 + 3, sho(-36)), (b3 - 3, sho(28), "io"),
                      (b3, sho(-72), "in"), (b3 + 8, sho(-68)), (T - 4, sh0, "io")],
        "trunk": [(0, tr0), (3, lean(6), "io"), (a0, lean(5)), (b1 - 2, lean(12), "io"), (b1, lean(14, -4)), (b2 - 3, lean(0), "io"),
                  (b2, lean(-20, 12), "in"), (b2 + 3, lean(-19, 11)), (b3 - 2, lean(14), "io"), (b3, lean(-7), "in"),
                  (b3 + 8, lean(-8)), (T - 4, tr0, "io")],
        "rear_heel": [(0, 0.012), (a0, 0.04), (b1, 0.06, "in"), (b1 + 3, 0.04), (b3 - 3, 0.03), (b3, 0.08, "io"), (b3 + 3, 0.11), (b3 + 8, 0.10), (T - 4, 0.012)],
        "rear_toe": [(0, base["rear_toe"]), (b1, 20.0, "in"), (b1 + 4, 24.0), (b3 - 4, 20.0), (b3, 8.0, "io"), (b3 + 8, 8.0), (T - 4, base["rear_toe"])],
        "lead_toe": [(0, base["lead_toe"]), (b2 - 4, base["lead_toe"]), (b2, base["lead_toe"] + 60, "in"), (b2 + 3, base["lead_toe"] + 60),
                     (b2 + 7, base["lead_toe"])],
        "_feet_abs": (b2 - 9, b2 + 9),
        "rear_foot_abs": [(b2 - 9, FR + (0.0,)), (b2 - 5, rk_lift, "io"), (b2 - 3, rk_ch), (b2 - 1, rk_mid), (b2, rk), (b2 + 2, rk),
                          (b2 + 5, rk_back, "out"), (b2 + 7, (FR[0] * 0.9, FR[1] - 0.04, 0.22, 0.1)), (b2 + 9, FR + (0.0,), "in")],
        "lead_hand_abs": [(0, L), (3, (L[0] + 0.02, L[1] - 0.10, L[2] - 0.03), "io"), (a0, (jab[0], jab[1] + 0.035, jab[2]), "in"),
                          (a0 + 1, jab), (a0 + 3, jab), (b1 - 3, (0.24, 0.10, R[2] - 0.04), "out"),
                          (b1, (body[0], body[1] + 0.03, body[2]), "in"), (b1 + 1, body), (b1 + 3, body),
                          (b2 - 3, chin, "out"), (b2 + 4, chin), (b3, hik, "in"), (b3 + 8, hik), (T - 3, L, "io")],
        "lead_elbow": [(0, 0.2), (a0, 0.05), (b1 - 3, 0.5), (b1, 0.85, "in"), (b1 + 3, 0.8), (b2, 0.2), (T - 3, 0.2)],
        "rear_hand_abs": [(0, R), (3, (R[0] - 0.03, R[1] - 0.04, R[2] + 0.02)), (b2 - 3, (R[0] + 0.02, R[1] + 0.04, R[2] + 0.04)),
                          (b2, (-0.30, -0.06, R[2] - 0.12), "in"), (b2 + 3, (-0.28, -0.04, R[2] - 0.10)),
                          (b3 - 3, upper_low, "io"), (b3, upper, "in"), (b3 + 1, upper_top), (b3 + 8, upper_top),
                          (T - 3, R, "io")],
        "rear_elbow": [(0, 0.1), (b2, 0.3), (b3 - 3, 0.15), (b3, 0.02), (b3 + 8, 0.02), (T - 3, 0.1)],
    }
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
    def idle_P(t, mod=None):
        """mod(ps, u): extra changes to the stance channels for this frame
        (the walk uses it to move the guard with the steps, D-100)."""
        r = raw[int(t) % n_idle]
        amp = st.get("amp", 0.35)
        u = (int(t) % n_idle) / float(n_idle)
        P = shape({k: mean[k] + (r[k] - mean[k]) * amp for k in r})
        if fitted:                                   # limbs solved on the fighter's own skeleton (D-075)
            life = st.get("life")
            if life:
                # The guard is alive (D-090): with every breath the chest turns a
                # little, the hands float and follow late, the chin moves. All
                # periodic over the loop; the feet stay on their marks.
                ps, ph = dict(st["pose"]), 2 * math.pi * u
                a = float(life)
                lh, rh = ps["lead_hand"], ps["rear_hand"]
                ps["lead_hand"] = (lh[0], lh[1] + 0.012 * a * math.sin(ph - 1.3), lh[2] + 0.016 * a * math.sin(ph - 1.0))
                ps["rear_hand"] = (rh[0], rh[1] + 0.006 * a * math.sin(ph - 0.9), rh[2] + 0.009 * a * math.sin(ph - 0.7))
                ps["shoulders"] = ps.get("shoulders", 0.0) + 2.2 * a * math.sin(ph - 0.5)
                ps["pelvis"] = ps.get("pelvis", 0.0) + 0.8 * a * math.sin(ph)
                tr = ps.get("trunk", (0.0, 0.0))
                ps["trunk"] = (tr[0] + 1.3 * a * math.sin(ph - 0.3), tr[1] + 0.6 * a * math.sin(ph + 0.8))
                ps["chin"] = ps.get("chin", 0.0) + 1.2 * a * math.sin(ph - 1.6)
                if st.get("heel_bounce"):
                    # D-100: up on the ball of the rear foot at the top of the bounce
                    # (the bob is highest at u = 0), heel down as he sinks
                    ps["rear_heel"] = ps.get("rear_heel", 0.0) + st["heel_bounce"] * 0.5 * (1 + math.cos(ph))
                if mod is not None:
                    mod(ps, u)
                return fit_stance(rig, P, dict(st, pose=ps), st["_lead"], u)
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
               aim=None, lift=None, foot_last=False):
        """foot_last: aim the kicking foot onto the hitbox once more after the
        feet are re-planted (as the fist is; the recorded karate kicks, D-095).
        aim: horizontal direction of the capture that must point at the
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
            if fitted:
                # Timed like a strike, not like a tape played at even speed
                # (D-083, from the animation research in docs/ANIMATION_RESEARCH.md):
                #   startup   slow out of the stance, then the body whips into
                #             the blow: most of the distance in the last frames
                #   active    the contact pose is held so it can be read
                #   recovery  leaves the contact pose fast and settles slowly
                if t <= a0:
                    f = (peak - pre) + pre * (t / max(1.0, float(a0))) ** 2.2
                elif t <= a1:
                    f = peak + 1.5 * (t - a0) / max(1.0, float(a1 - a0))
                else:
                    v = (t - a1) / max(1.0, float(total - 1 - a1))
                    f = peak + 1.5 + (post - 1.5) * (1.0 - (1.0 - v) ** 2.0)
            P = src(c, f, facing_frame=facing or peak, anchor=anchor, fd=aim)
            if fitted and a0 >= 7:
                # anticipation: a short counter-move before a slower strike. The
                # body sinks back and coils away from the target, then goes.
                u = t / float(a0)
                coil = math.sin(math.pi * min(1.0, u / 0.7)) ** 2 if u < 0.7 else 0.0
                if coil > 0.001:
                    P = shift(P, list(P.keys()), np.array([0.0, 0.035 * H * coil, -0.02 * H * coil]))
                    P = lean(P, 3.0 * coil)
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
            if fitted and a0 <= t <= a0 + 1:
                # ... and overshoots: one or two frames past the pose, then back
                P = shift(P, list(P.keys()), np.array([0.0, -0.025 * H, 0.0]))
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
                if limb == "foot" and foot_last:
                    P = move_foot(P, side, np.array([P[side + "Foot"][0], tgt_fwd + 0.08 + guard_P["Hips"][1], tgt_h]), w)
                    if os.environ.get("KEYED_DEBUG") and a0 <= t <= a1:
                        print("FOOT t%d foot %s target fwd %.2f h %.2f hips %s" % (t, np.round(P[side + "Foot"], 2),
                              tgt_fwd + 0.08 + guard_P["Hips"][1], tgt_h, np.round(P["Hips"], 2)))
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
                bx, bf, bu = st.get("block", {}).get(side, (0.085, 0.19, -0.02))
                P = reach_hand(rig, P, side, (bx * sg * S_fit, bf * S_fit, bu * S_fit), w,
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
    # D-108 (owner: "his legs still move too fast"): a foot is planted 55 % of
    # the loop (was 70 %), so each leg swings through in ~11 frames instead of
    # ~6, with a slightly longer step (0.42 m) and a slower loop (25 frames at
    # 1.8 m/s, was 19). Planted travel still equals the ground covered.
    WALK_PLANT, WALK_SHIFT = 0.55, 0.45

    def walk(speed, forward):
        n = 30
        if fitted:
            # D-106 (owner: "his walking looks like sliding on ice"): the loop is
            # timed to the game's walk speed so a planted foot moves back under
            # the body exactly as fast as the game carries him (it was capped at
            # 17 cm a step against 2.6 m/s: ~0.7 m of skating per step). A step
            # of about 0.40 m (Kairo's stance is ~0.48 m long), planted 70 % of
            # the loop: n frames such that speed x 0.7 x n / 60 = the step.
            n = int(min(40, max(14, round(0.42 * S_fit * FPS_OUT / (WALK_PLANT * speed)))))
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
                d = speed * WALK_PLANT * n / float(FPS_OUT)  # planted travel = ground covered: no sliding
                dirn = 1.0 if forward else -1.0
                ph = t / float(n)
                smooth = lambda x: ease(min(1.0, max(0.0, x)))
                off, lift, heel_up, toe_up = {}, {}, {}, {}
                # the second foot follows 0.45 of a loop (WALK_SHIFT) behind the first (not half a
                # loop, a stroll): the stance stretches a little and closes again,
                # and the feet never come together under him (D-092)
                order = ((st["_lead"], 0.0), (rear_fit, WALK_SHIFT)) if forward else ((rear_fit, 0.0), (st["_lead"], WALK_SHIFT))
                for foot, shift_ph in order:
                    q = (ph + shift_ph) % 1.0
                    if q < WALK_PLANT:                             # planted
                        o, up = 0.5 - q / WALK_PLANT, 0.0
                        heel_up[foot] = 0.04 * S * smooth((q - (WALK_PLANT - 0.18)) / 0.18)
                        toe_up[foot] = 0.02 * S * (1.0 - smooth(q / 0.10)) if forward else 0.0
                    else:                                          # swinging
                        v = (q - WALK_PLANT) / (1.0 - WALK_PLANT)
                        o, up = -0.5 + ease(v), 0.065 * S * math.sin(math.pi * v)
                        heel_up[foot] = 0.04 * S * (1.0 - smooth(v / 0.5))
                        toe_up[foot] = 0.02 * S * smooth((v - 0.7) / 0.3) if forward else 0.0
                    off[foot], lift[foot] = dirn * d * o, up
                side_ph = math.sin(2 * math.pi * (ph - 0.06)) * (1.0 if forward else -1.0)
                wl = float(st.get("walk_life", 0.0))
                if wl:
                    # D-100 (owner: motion "needs to be more natural"): the guard
                    # was one frozen frame carried on walking legs. Now the hands
                    # sink a beat after each step lands (two per loop) and swing a
                    # little against the legs, the chin nods with the step.
                    def wmod(ps, _u, ph=ph, wl=wl, fw=(1.0 if forward else -1.0)):
                        beat = 0.5 * (1.0 + math.cos(4 * math.pi * (ph - 0.16)))     # 1 just after a landing
                        for key, k, sw in (("lead_hand", 1.0, 1.0), ("rear_hand", 0.7, -1.0)):
                            h = ps[key]
                            ps[key] = (h[0], h[1] + 0.022 * wl * k * sw * fw * math.sin(2 * math.pi * (ph - 0.1)),
                                       h[2] - 0.022 * wl * k * beat + 0.011 * wl * k)
                        ps["chin"] = ps.get("chin", 0.0) + 2.5 * wl * (beat - 0.5)
                        ps["trunk"] = (ps.get("trunk", (0.0, 0.0))[0] + 1.2 * wl * (beat - 0.5), ps.get("trunk", (0.0, 0.0))[1])
                    base_t = idle_P(0, mod=wmod)
                else:
                    base_t = base
                P = shift(base_t, list(base_t.keys()), np.array([sg * 0.014 * S * side_ph, 0.0, 0.0]))
                P = turn(P, -sg * 3.0 * side_ph)                   # pelvis and all: goes with the swinging leg
                hp = P["Hips"].copy()
                Rc = np.array(Matrix.Rotation(math.radians(sg * (5.5 + 2.5 * float(st.get("walk_life", 0.0))) * side_ph), 3, "Z"))
                for k in UPPER:                                    # shoulders against the pelvis
                    if k in P:
                        P[k] = Rc @ (P[k] - hp) + hp
                P = lean(P, (-3 if forward else 2) + 1.2 * math.sin(4 * math.pi * (ph - 0.1)))
                dip = (0.02 + 0.01 * float(st.get("walk_life", 0.0))) * S * 0.5 * (1.0 + math.cos(4 * math.pi * (ph - 0.06)))
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

    # ---- keyed poses on a fitted stance (D-084; opened to every fitted
    # fighter in D-087 for the crouch, the jump and the jumping attack)
    if fitted:
        raw_guard = {k: mean[k] + (raw[0][k] - mean[k]) * st.get("amp", 0.35) for k in mean}
        gp, _gt = fk(rig, guard.D, guard.hips)
        lift0 = float(min(gp["LeftFoot"][2], gp["RightFoot"][2]) - rig.foot_h)
        g_hand = {sd: (float(gp[sd + "Hand"][0]), float(-gp[sd + "Hand"][1]), float(gp[sd + "Hand"][2] - lift0))
                  for sd in ("Left", "Right")}
        g_hand["Head"] = (float(gp["Head"][0]), float(-gp["Head"][1]), float(gp["Head"][2] - lift0))
        g_foot = {sd: (float(gp[sd + "Foot"][0]), float(-gp[sd + "Foot"][1]), float(gp[sd + "Foot"][2] - lift0))
                  for sd in ("Left", "Right")}
        base_ps = dict(st["pose"])
        hips_c = float(guard.hips[2] - base_ps.get("pelvis_h", 0.93) * rig.hips_h)   # keyed hip height -> built hip height

        def keyed_frames(total, tracks, a1=None, settle=6, air=False, blend_in=2):
            """Poses for `total` frames from channel tracks (see kairo_keys).
            `_recover`: the frames after a1 are played that many times slower.
            `_feet_abs` (first, last): the *_foot_abs channels apply on those
            frames only; outside them the feet stand on their stance marks.
            air=True: the hips are placed from pelvis_h instead of standing the
            lowest foot on the floor (a jump: both feet may be off it)."""
            poses = []
            slow = float(tracks.get("_recover", 1.0))
            hold = int(tracks.get("_hold", 0))
            fa = tracks.get("_feet_abs")
            for f in range(total):
                # the recovery is played `slow` times slower than it was keyed, so
                # the return fills the recovery frames instead of finishing early
                # and standing still (seen on the frame-by-frame strips, D-085)
                # `_hold`: the pose of the last active frame stays for that many
                # frames first. On the phone (D-089) a strike was fully out for
                # 50 ms and gone: too short to read.
                # During the hold the pose is not frozen: it creeps on at an eighth
                # of the speed (a moving hold). `_lag`: in the recovery the chest,
                # the head and the arms start back a few frames after the hips, each
                # in turn, instead of every part leaving on the same frame (D-090).
                def warp(x):
                    if a1 is None or x <= a1:
                        return x
                    if x <= a1 + hold:
                        return a1 + (x - a1) * 0.125
                    return a1 + hold * 0.125 + (x - a1 - hold) / slow
                t = warp(f)
                lag = tracks.get("_lag")
                ps = dict(base_ps)
                for ch, keys in tracks.items():
                    if ch.startswith("_"):
                        continue
                    if ch.endswith("_foot_abs") and fa is not None and not (fa[0] <= f <= fa[1]):
                        continue
                    if isinstance(keys, str):               # a constant, e.g. a palm rule
                        ps[ch] = keys
                        continue
                    tc = t
                    if lag and a1 is not None and f > a1:
                        d = 0.0
                        for part, frames in lag:
                            if part in ch:
                                d = frames
                                break
                        tc = warp(max(float(a1), f - d))
                    v = curve(tc, keys) if isinstance(keys, list) else keys
                    ps[ch] = tuple(float(x) for x in v) if np.ndim(v) else float(v)
                ps.setdefault("lead_palm", "auto")
                st2 = dict(st, pose=ps, bob=0.0, sway=0.0, tap=0.0)
                P = shape_stance(dict(raw_guard), st2, H)
                P = fit_stance(rig, P, st2, st["_lead"], 0.0)
                if air:
                    p = pose_of(P, gclip, ground=False)
                    p = Pose(p.D, np.array([p.hips[0], p.hips[1], ps.get("pelvis_h", 0.93) * rig.hips_h + hips_c]))
                else:
                    p = pose_of(P, gclip)
                poses.append(p)
            if os.environ.get("KEYED_DEBUG"):              # wrist paths per frame, for checking timing
                for i, p in enumerate(poses):
                    J = fk(rig, p.D, p.hips)[0]
                    print("KEYED", tracks.get("_name", "?"), i + 1, " ".join(
                        "%s=(%.2f %.2f %.2f) ext=%.2f" % (n[:1], *J[n + "Hand"], np.linalg.norm(J[n + "Hand"] - J[n + "UpperArm"]) / (
                            np.linalg.norm(rig.head[n + "LowerArm"] - rig.head[n + "UpperArm"]) + np.linalg.norm(rig.head[n + "Hand"] - rig.head[n + "LowerArm"])))
                        for n in ("Left", "Right")), "F " + " ".join("(%.2f %.2f %.2f)" % tuple(J[n + "Foot"]) for n in ("Left", "Right")),
                        "head %.2f" % J["Head"][2], "legext " + " ".join("%s=%.2f" % (n[:1], np.linalg.norm(J[n + "Foot"] - J[n + "UpperLeg"]) / (
                            np.linalg.norm(rig.head[n + "LowerLeg"] - rig.head[n + "UpperLeg"]) + np.linalg.norm(rig.head[n + "Foot"] - rig.head[n + "LowerLeg"])))
                            for n in ("Left", "Right")))
            if tracks.get("_spring", a1 is not None):
                poses = follow_through(rig, poses, a1)
            for t in range(min(blend_in, total)):          # out of the stance without a seam
                poses[t] = Pose.blend(guard, poses[t], (t + 1) / float(blend_in + 1))
            for t in range(max(0, total - settle), total):
                poses[t] = Pose.blend(poses[t], guard, ease((t - (total - settle) + 1) / float(settle)))
            return poses

        def keyed_move(mv, tracks, settle=6):
            total = mv["startup"] + mv["active"] - 1 + mv["recovery"]
            tr = dict(tracks, _name=mv["animation"])
            if "_recover" in tr and "_hold" not in tr:     # a single strike: hold it, then return in the time left
                rec = mv["recovery"]
                tr["_hold"] = min(4, int(round(rec * 0.16)))
                tr["_recover"] = max(1.0, tr["_recover"] * (rec - tr["_hold"]) / float(rec))
                # who starts home when: hips and legs first, then the chest, the arms, the head last
                tr.setdefault("_lag", (("foot", 0.0), ("heel", 0.0), ("toe", 0.0), ("hips", 0.0), ("pelvis", 0.0),
                                       ("trunk", 1.0), ("shoulders", 1.5), ("hand", 1.0), ("elbow", 1.0), ("palm", 1.0),
                                       ("chin", 3.0), ("neck", 3.0), ("head", 3.0)))
            return keyed_frames(total, tr, mv["startup"] + mv["active"] - 2, settle)

    # ---- crouch, jump and jumping attack (D-087). One frame per tick; the
    # game lifts the fighter along the jump arc, so the clips only pose the
    # body: the dip before take-off, legs trailing then tucked, legs reaching
    # for the floor, the landing dip. The jump clip is 4 + 38 + 4 frames
    # (FighterAnimator.JUMP_CLIP_*).
    JUMP_PRE, JUMP_AIR, JUMP_LAND = 4, 38, 4
    n_jump = JUMP_PRE + JUMP_AIR + JUMP_LAND
    t_off, t_down = JUMP_PRE, JUMP_PRE + JUMP_AIR          # first air frame, touch-down frame
    air_mv = moves.get("AIR")
    n_air = (air_mv["startup"] + air_mv["active"] - 1 + air_mv["recovery"]) if air_mv else 0
    lead_sd = st.get("_lead", "Left")
    rear_sd = "Right" if lead_sd == "Left" else "Left"
    if fitted:
        ph0 = base_ps.get("pelvis_h", 0.93)
        tr0 = base_ps.get("trunk", (0.0, 0.0))
        chin0 = base_ps.get("chin", 0.0)
        home = {sd: g_foot[sd] + (0.0,) for sd in ("Left", "Right")}
        hl, hr = home[lead_sd], home[rear_sd]
        kd = STYLES[fid].get("crouch_pose", {})
        # crouch: a deep squat over the stance's own feet, chest forward, eyes up
        cdrop, clean = kd.get("drop", 0.43), kd.get("lean", 26.0)
        n_cr = 97                                              # one slow breath: it was two a second, which read as shaking (D-093)
        ct = {"pelvis_h": [(0, ph0 - cdrop), (n_cr // 2, ph0 - cdrop + 0.012, "io"), (n_cr - 1, ph0 - cdrop, "io")],
              "trunk": [(0, (tr0[0] + clean, tr0[1])), (n_cr // 2, (tr0[0] + clean - 1.4, tr0[1]), "io"),
                        (n_cr - 1, (tr0[0] + clean, tr0[1]), "io")],
              "chin": chin0 - kd.get("chin", 14.0),
              "lead_heel": kd.get("lead_heel", 0.0), "rear_heel": kd.get("rear_heel", 0.07), "_name": "CROUCH"}
        ct.update(kd.get("pose", {}))
        A[f"{F}_CROUCH"] = keyed_frames(n_cr, ct, settle=0, blend_in=0)
        jd = STYLES[fid].get("jump", {})
        tuck = jd.get("tuck", 0.30) * S_fit
        jt = {"_name": "JUMP", "_feet_abs": (t_off, t_down - 1),
              "pelvis_h": [(0, ph0), (t_off - 1, ph0 - 0.16, "out"), (t_off + 3, ph0 + 0.02, "out"), (t_down - 1, ph0),
                           (t_down + 1, ph0 - 0.13, "out"), (n_jump - 1, ph0)],
              "trunk": [(0, tr0), (t_off - 1, (tr0[0] + 16, tr0[1]), "out"), (t_off + 3, (tr0[0] - 4, tr0[1])),
                        (t_off + 12, (tr0[0] + 10, tr0[1]), "io"), (t_off + 26, (tr0[0] + 9, tr0[1])), (t_down - 2, (tr0[0] + 3, tr0[1])),
                        (t_down + 1, (tr0[0] + 12, tr0[1]), "out"), (n_jump - 1, tr0)],
              # D-107 (owner: "jumping does not look like a fighter"): a short
              # push-off with the toes pointed, then BOTH knees drawn up high in
              # front of the chest through the rise and the top (the feet came up
              # 0.3 and the rear leg trailed), held compact, then the legs reach
              # down for the floor over the last frames.
              "lead_foot_abs": [(t_off, hl), (t_off + 3, (hl[0], hl[1] - 0.03 * S_fit, hl[2] - 0.02, 0.9), "out"),
                                (t_off + 10, (hl[0] * 0.9, hl[1] * 0.45, hl[2] + tuck * 1.35, 0.55), "io"),
                                (t_off + 26, (hl[0] * 0.9, hl[1] * 0.40, hl[2] + tuck * 1.45, 0.55)),
                                (t_down - 7, (hl[0], hl[1] * 0.9, hl[2] + 0.12 * S_fit, 0.35), "io"), (t_down - 1, hl)],
              "rear_foot_abs": [(t_off, hr), (t_off + 3, (hr[0], hr[1] - 0.05 * S_fit, hr[2] - 0.02, 0.9), "out"),
                                (t_off + 11, (hr[0] * 0.8, hr[1] * 0.10, hr[2] + tuck * 1.45, 0.6), "io"),
                                (t_off + 26, (hr[0] * 0.8, hr[1] * 0.05, hr[2] + tuck * 1.5, 0.6)),
                                (t_down - 7, (hr[0], hr[1] * 0.9, hr[2] + 0.14 * S_fit, 0.35), "io"), (t_down - 1, hr)]}
        # the arms work with the jump (D-091): they drop as he sinks, come up
        # with the take-off, and drop again to catch the landing
        for key, k in (("lead_hand", 1.0), ("rear_hand", 0.7)):
            if key in base_ps:
                h0 = base_ps[key]
                def off(dx, df, dz, h0=h0, k=k):
                    return (h0[0] + dx * k, h0[1] + df * k, h0[2] + dz * k)
                jt[key] = [(0, h0), (t_off - 1, off(0.04, -0.10, -0.10), "out"), (t_off + 4, off(0.0, -0.02, 0.08)),
                           (t_off + 12, off(-0.01, -0.05, 0.03), "io"), (t_off + 26, off(-0.01, -0.05, 0.03)),   # guard pulled in, compact
                           (t_down - 2, off(0.02, -0.03, 0.05)),
                           (t_down + 1, off(0.03, -0.06, -0.09), "out"), (n_jump - 1, h0)]
        jt.update(jd.get("pose", {}))
        A[f"{F}_JUMP"] = keyed_frames(n_jump, jt, settle=3, air=True)
        AIRBORNE[f"{F}_JUMP"] = (t_off + 1, t_down - 1)
        if air_mv:
            a0, a1 = air_mv["startup"] - 1, air_mv["startup"] + air_mv["active"] - 2
            hx, hz = air_mv["hc"]
            ad = STYLES[fid].get("air_kick", {})
            kick_sd = ad.get("leg", "rear")
            kh, oh = (hr, hl) if kick_sd == "rear" else (hl, hr)
            chamber = (kh[0] * 0.6, 0.12 * S_fit, kh[2] + 0.42 * S_fit, 0.5)
            strike_at = (ad.get("x", 0.02), hx + ad.get("reach", 0.0), hz - 0.04, 0.15)
            tucked = (oh[0], -0.06 * S_fit, oh[2] + 0.36 * S_fit, 0.6)
            at = {"_name": "JUMP_ATTACK", "pelvis_h": ph0,
                  "trunk": [(0, (tr0[0] + 4, tr0[1])), (a0, (tr0[0] - ad.get("lean", 16.0), tr0[1]), "in"),
                            (a1, (tr0[0] - ad.get("lean", 16.0), tr0[1])), (n_air - 1, (tr0[0] + 4, tr0[1]))],
                  kick_sd + "_foot_abs": [(0, (kh[0], kh[1] * 0.45, kh[2] + tuck, 0.6)), (max(1, a0 - 3), chamber),
                                          (a0, strike_at, "in"), (a1, strike_at), (n_air - 1, (kh[0], kh[1] * 0.45, kh[2] + tuck, 0.6))],
                  ("lead" if kick_sd == "rear" else "rear") + "_foot_abs": [(0, (oh[0], oh[1] * 0.6, oh[2] + tuck, 0.5)), (a0, tucked),
                                                                         (a1, tucked), (n_air - 1, (oh[0], oh[1] * 0.6, oh[2] + tuck, 0.5))]}
            at.update(ad.get("pose", {}))
            if fid == "kairo":
                # Kairo's Flying Side Kick (D-098; owner: "the jump kick looks
                # bad" — it sat in the air as on a chair: square to the camera,
                # rear leg bent ~0.78 and pointing steeply down, toes pointed,
                # the other leg hanging, arms frozen). Now a tobi yoko geri: the
                # lead knee comes up across the body, the hips and shoulders turn
                # side-on, the leg shoots out heel first into the far part of the
                # box (0.15-0.95 m forward, below the hips) nearly straight, the
                # trunk leans back away from it, the rear knee is tucked high; on
                # the way down the leg is pulled back in and the feet reach for
                # the floor.
                pel0, sh0 = base_ps.get("pelvis", 48), base_ps.get("shoulders", 58)
                lh0, rh0 = base_ps["lead_hand"], base_ps["rear_hand"]
                T = n_air - 1
                k_tuck = (hl[0], 0.02 * S_fit, hl[2] + tuck, 0.2)
                k_chamber = (hl[0] * 0.3, 0.16 * S_fit, hl[2] + 0.50 * S_fit, -0.4)     # knee high, foot under it
                k_half = (0.02, hx + 0.08, hz + 0.13, -0.85)
                k_out = (0.02, hx + 0.34, hz + 0.08, -0.95)                            # heel first, leg fully straight (D-099)
                k_hold = (0.02, hx + 0.34, hz + 0.08, -0.95)
                k_back = (0.02, hx * 0.95, hz + 0.10, -0.8)                            # first frames of the pull back
                k_back2 = (hl[0] * 0.15, hx * 0.55, hz + 0.20, -0.6)
                r_tuck = (hr[0] * 0.8, -0.28 * S_fit, hr[2] + 0.30 * S_fit, 0.5)       # rear leg trails behind and below, bent ~0.6 (D-099: tucked to 0.28 it crushed the knee and pinched the thigh)
                at = {"_name": "JUMP_ATTACK", "pelvis_h": ph0,
                      "pelvis": [(0, pel0), (a0 - 3, pel0 + 16, "io"), (a0, pel0 + 34, "io"), (a1, pel0 + 32), (a1 + 3, pel0 + 22, "io"), (T, pel0 + 6, "io")],
                      "shoulders": [(0, sh0), (a0 - 3, sh0 + 8, "io"), (a0 + 1, sh0 + 24, "io"), (a1, sh0 + 22), (a1 + 3, sh0 + 14, "io"), (T, sh0 + 4, "io")],
                      "trunk": [(0, (tr0[0] + 4, tr0[1])), (a0 - 3, (tr0[0] + 1, tr0[1]), "io"), (a0 + 1, (tr0[0] - 27, tr0[1]), "io"),
                                (a1, (tr0[0] - 26, tr0[1])), (a1 + 4, (tr0[0] - 10, tr0[1]), "io"), (T, (tr0[0] + 3, tr0[1]), "io")],
                      "lead_foot_abs": [(0, k_tuck), (a0 - 3, k_chamber, "out"), (a0 - 1, k_half), (a0, k_out),
                                        (a0 + 2, k_hold), (a1, k_hold), (a1 + 1, k_back), (a1 + 2, k_back2), (a1 + 4, k_chamber),
                                        (T, (hl[0], hl[1] * 0.6, hl[2] + tuck * 0.6, 0.2))],
                      "rear_foot_abs": [(0, (hr[0], hr[1] * 0.45, hr[2] + tuck, 0.5)), (a0 - 3, (hr[0] * 0.9, hr[1] * 0.3 - 0.08 * S_fit, hr[2] + tuck + 0.06 * S_fit, 0.45), "io"),
                                        (a0 + 1, r_tuck, "io"), (a1, r_tuck),
                                        (T, (hr[0], hr[1] * 0.6, hr[2] + tuck * 0.6, 0.3))],
                      # lead arm drops along the kicking leg as a shield, rear fist up at the chin
                      "lead_hand": [(0, lh0), (a0, (lh0[0] + 0.02, lh0[1] - 0.06, lh0[2] - 0.16), "in"), (a1, (lh0[0] + 0.02, lh0[1] - 0.06, lh0[2] - 0.15)),
                                    (T, lh0, "out")],
                      "rear_hand": [(0, rh0), (a0, (rh0[0] - 0.06, rh0[1] - 0.02, rh0[2] + 0.12), "in"), (a1, (rh0[0] - 0.06, rh0[1] - 0.02, rh0[2] + 0.11)),
                                    (T, rh0, "out")]}
            A[f"{F}_JUMP_ATTACK"] = keyed_frames(n_air, at, settle=0, air=True, blend_in=0)
            AIRBORNE[f"{F}_JUMP_ATTACK"] = (0, n_air)
    else:
        # fighters still on an unfitted stance (Drakon, Ryuen): the same
        # poses made on the captured skeleton
        LEGS_UP = UPPER + ["Hips", "LHipJoint", "RHipJoint", "LeftUpLeg", "RightUpLeg"]
        feet0 = {sd: guard_P[sd + "Foot"].copy() for sd in ("Left", "Right")}
        def squat(drop, pitch, tuck_l=0.0, tuck_r=0.0, kick=None):
            P = shift(guard_P, LEGS_UP, np.array([0, 0, -drop * H]))
            for sd, tk in ((lead_sd, tuck_l), (rear_sd, tuck_r)):
                tgt = feet0[sd] + np.array([0.0, 0.0, tk * H])
                if kick is not None and sd == kick[0]:
                    tgt = kick[1]
                P = move_foot(P, sd, tgt)
            return lean(P, pitch)
        A[f"{F}_CROUCH"] = [pose_of(squat(0.40 + 0.006 * math.sin(2 * math.pi * t / 30.0), -24), box) for t in range(31)]
        jp = []
        for t in range(n_jump):
            if t < t_off:
                P = squat(0.13 * ease((t + 1) / float(t_off), "out"), -12 * ease((t + 1) / float(t_off)))
            elif t < t_down:
                u = (t - t_off) / float(JUMP_AIR - 1)
                k = math.sin(math.pi * u) ** 1.5
                P = squat(0.0, 4 - 8 * k, 0.24 * k, 0.32 * k)
            else:
                w = (t - t_down + 1) / float(JUMP_LAND)
                P = squat(0.11 * math.sin(math.pi * min(1.0, w * 0.9 + 0.1)), -10 * (1 - w))
            jp.append(pose_of(P, box, ground=False))
        A[f"{F}_JUMP"] = jp
        AIRBORNE[f"{F}_JUMP"] = (t_off + 1, t_down - 1)
        if air_mv:
            a0, a1 = air_mv["startup"] - 1, air_mv["startup"] + air_mv["active"] - 2
            hx, hz = air_mv["hc"]
            ja = []
            for t in range(n_air):
                w = ease(t / float(max(1, a0)), "in") if t <= a0 else (1.0 if t <= a1 else 1.0 - ease((t - a1) / float(n_air - 1 - a1)))
                tgt = feet0[rear_sd] * (1 - w) + np.array([feet0[rear_sd][0] * 0.3, -hx, hz - 0.04]) * w
                tgt[2] = max(tgt[2], feet0[rear_sd][2] + 0.25 * H)
                P = squat(0.0, 12 * w, 0.30, 0.0, (rear_sd, tgt))
                ja.append(pose_of(P, box, ground=False))
            A[f"{F}_JUMP_ATTACK"] = ja
            AIRBORNE[f"{F}_JUMP_ATTACK"] = (0, n_air)

    # ---- Kairo: every attack built pose to pose on his stance blueprint
    # (D-084), replacing the research captures above. See kairo_keys().
    if fid == "kairo" and fitted:
        for mv_key, tracks in kairo_keys(moves, base_ps, dict(g_hand, feet=g_foot), S_fit).items():
            mv = moves[mv_key]
            A[F + mv["animation"][mv["animation"].find("_"):]] = keyed_move(mv, tracks)
        if os.environ.get("KAIRO_RECORDED"):
            # Trial (D-095): two of his moves from recorded karate instead of
            # keys, to compare side by side. CMU 135 is a karateka: 135_09
            # oi-zuki (the right punch at frame 762; the step is dropped, his
            # feet stay on his stance), 135_04 front kicks (the rear-leg kick
            # at frame 813). Same frame data and hitboxes as the keyed moves.
            zuki, geri = clip("135_09"), clip("135_04")

            def held_back(mv, root, mid, end, ext):
                """The karateka lunges deeper than Kairo's hitbox allows: his
                shoulder (hip) arrives so close to the box that the arm (leg)
                hits it still folded. Move the whole body back, around the
                active frames, until the limb reaches the box at `ext` of its
                length. Forward is -Y."""
                total, a0, a1 = frames_of(mv)
                tgt_y, tgt_z = -mv["hc"][0], mv["hc"][1]
                def fn(P, t, T):
                    w = track(t, [(0, 0.0), (max(1, a0 - 3), 1.0), (a1 + 2, 1.0), (total - 1, 0.0)])
                    L = np.linalg.norm(P[mid] - P[root]) + np.linalg.norm(P[end] - P[mid])
                    dz = tgt_z - P[root][2]
                    reach = math.sqrt(max(0.0, (ext * L) ** 2 - dz * dz))
                    excess = (tgt_y + reach) - P[root][1]          # > 0: the root is too far forward
                    if excess <= 0.0 or w <= 0.0:
                        return P
                    return shift(P, list(P.keys()), np.array([0.0, excess * w, 0.0]))
                return fn

            mv = moves["HEAVY"]
            A[F + mv["animation"][mv["animation"].find("_"):]] = strike(
                zuki, 762, "Right", "hand", mv, pre=36, post=50, blend_in=4,
                extra=held_back(mv, "RightArm", "RightForeArm", "RightHand", 0.93))
            mv = moves["DOWN_HEAVY"]
            d = (geri.at(813)["RightFoot"] - geri.at(813)["Hips"])[:2]
            A[F + mv["animation"][mv["animation"].find("_"):]] = strike(
                geri, 813, "Right", "foot", mv, pre=30, post=22, blend_in=4,
                aim=d / (np.linalg.norm(d) + 1e-9),
                extra=held_back(mv, "RightUpLeg", "RightLeg", "RightFoot", 0.7), foot_last=True)

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

    if os.environ.get("GLITCH_SCAN"):
        # Pops (D-092): a joint that moves much further on one frame than on the
        # frames either side of it. Printed per action, worst first.
        pts = ("LeftFoot", "RightFoot", "LeftLowerLeg", "RightLowerLeg", "LeftHand", "RightHand", "Head")
        for name, poses in A.items():
            tr = []
            for p in poses:
                pos, tails = fk(rig, p.D, p.hips)
                d = {k: pos[k] for k in pts}
                d["LeftToe"], d["RightToe"] = tails["LeftFoot"] - pos["LeftFoot"], tails["RightFoot"] - pos["RightFoot"]
                tr.append(d)
            found = []
            for k in tr[0]:
                sp = [float(np.linalg.norm(tr[i + 1][k] - tr[i][k])) for i in range(len(tr) - 1)]
                for i, v in enumerate(sp):
                    near = [sp[j] for j in (i - 2, i - 1, i + 1, i + 2) if 0 <= j < len(sp)]
                    lim = 0.035 if k.endswith("Toe") else 0.06
                    if v > lim and near and v > 2.6 * max(near):
                        found.append((v, k, i + 2))
            for v, k, f in sorted(found, reverse=True)[:6]:
                print("GLITCH %-28s f%-3d %-13s moved %.3f in one frame" % (name, f, k, v))
    acts = {}
    for name, poses in A.items():
        acts[name] = key_action(rig, name, poses)
        if rig.fingers:
            key_fingers(rig, acts[name], hand_curls(fid, name[len(F) + 1:], len(poses)))
    LAST_BUILD["rig"], LAST_BUILD["poses"] = rig, A        # for pose_check.report
    return acts
