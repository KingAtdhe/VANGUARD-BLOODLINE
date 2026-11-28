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
    "kairo": dict(clip="13_17", frame=840, facing=900, amp=0.45, bob=0.015, bob_beats=2, sway=0.02, life=3.0, weight_shift=0.035, loop=120, walk_life=1.0, lead="Left",   # D-136: heel_bounce 0.02 removed (the rear foot read as sliding)
                  # his guard: the open lead forearm upright in front of the face, the rear fist under the chin
                  # D-136 (owner: "block high looks too much like the stance, raise the guard more clearly"):
                  # lead forearm up in front of the forehead, rear fist at the temple
                  block={"Left": (0.04, 0.215, -0.005), "Right": (0.07, 0.165, -0.025)},
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
                            # D-133 (critique: "arms on parallel planes"): the lead hand further out and lower, the
                            # rear fist higher and tighter with the elbow out, so the two forearms cross at an angle
                            # D-134: 18 deg between the forearms in the side view still read as parallel:
                            # the lead forearm now reaches out nearly level, the rear one stands up by the jaw
                            # D-135 (critique of the D-134 video: "the front arm hangs straight out at chest
                            # height, his guard is open and the jab has no room"): the lead fist comes in
                            # and up to shoulder height, elbow bent, still angled against the upright rear forearm
                            lead_hand=(0.05, 0.36, -0.20), rear_hand=(0.10, 0.20, -0.07),
                            lead_elbow=0.25, rear_elbow=0.3, lead_palm=(-0.5, -0.6, -0.6), rear_palm="auto")),
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
    if ps.get("curl"):
        # `curl` (D-134): the back bends in itself, degrees; + = crunched forward,
        # - = arched back. Until now the trunk was one straight line from pelvis
        # to collar that only leaned: "the upper torso moves as a rigid cylinder".
        # The bend is shared between the waist and the chest about the hip line.
        ax_ = P[lead + "UpLeg"] - P[rear + "UpLeg"]
        ax_ = Vector((float(ax_[0]) * sgl, float(ax_[1]) * sgl, 0.0)).normalized()
        chain = ["Spine", "Spine1", "Neck", "Neck1", "Head", "Head_end"] + [k for k in UPPER if "Shoulder" in k or "Arm" in k or "Hand" in k
                                                                             or "Finger" in k or "Thumb" in k]
        for pivot, share in (("Spine", 0.45), ("Spine1", 0.55)):
            if pivot not in P:
                continue
            o = P[pivot].copy()
            Rc_ = np.array(Matrix.Rotation(math.radians(float(ps["curl"]) * share), 3, ax_))
            for k in chain[chain.index(pivot) + 1:]:
                if k in P:
                    P[k] = Rc_ @ (P[k] - o) + o
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


def _ik_dirs(a, target, l1, l2, hint, reach=0.995):
    """Two-bone IK in model space: directions of both bones from root `a` so
    the end reaches `target` (as far as the limb goes), bending toward `hint`.
    `reach`: the most the limb opens, as a share of its length. 0.995 still
    bends the joint ~11 degrees (2 acos 0.995); kicking legs use 0.9995 (~3.6
    degrees, D-114: owner, "his leg isn't fully extended")."""
    d = np.asarray(target, float) - a
    closest = math.sqrt(l1 * l1 + l2 * l2 - 2 * l1 * l2 * math.cos(math.radians(32.0)))   # folds to 148 degrees at most
    dist = float(np.clip(np.linalg.norm(d), closest, (l1 + l2) * reach))
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
        hop = (tap if sd == lead else 0.0) + ps.get(key + "_hop", 0.0) * S     # `<key>_hop`: the whole foot off the floor (a step; set by keyed_frames, D-131)
        P = solve_leg(rig, P, pos, sd, np.array([sx * ax * S, sy * al * S]), ps.get(key + "_toe", 0.0) * sx,
                      lift, hop, ps.get("knees", 0.0) * sx)
    for sd, key, sx in ((lead, "lead", sgl), (rear, "rear", -sgl)):
        if key + "_foot_abs" in ps:
            # a foot in the air (a kick): the ankle at (x, forward, height) in
            # model space, the foot pointed in line with the shin by `point` 0..1.
            # `<key>_reach` (D-129): the most this leg opens, as a share of its
            # length (default 0.9995 = locked). With the target beyond reach it
            # sets the knee bend by itself: 0.996 ~10 degrees, 0.985 ~20, 0.95 ~36,
            # 0.6 ~106, so a kick can be keyed as a direction plus an extension.
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
                              blen(sd + "LowerLeg", sd + "Foot"), hint, reach=float(ps.get(key + "_reach", 0.9995)))
            l_thigh, l_shin = slen(sd + "UpLeg", sd + "Leg"), slen(sd + "Leg", sd + "Foot")
            toe_keys = [k for k in (sd + "ToeBase", sd + "ToeBase_end") if k in P]
            toe_len = [slen(sd + "Foot", k) for k in toe_keys]
            P[sd + "Leg"] = P[sd + "UpLeg"] + d1 * l_thigh
            P[sd + "Foot"] = P[sd + "Leg"] + d2 * l_shin
            if ps.get(key + "_hinge"):
                # `<key>_hinge` (D-129): say which way the knee's hinge faces, so the
                # thigh is not rolled by chance. The hinge is square to the plane of
                # the bent leg; a straight leg takes the pelvis' own sideways axis.
                # Without it the thigh is turned by the shortest way from its rest
                # direction, and a leg raised overhead (the opposite of rest) rolled
                # half a turn in one frame: the mesh knee then bent backwards.
                hc = np.cross(d1, d2)
                bend = float(np.linalg.norm(hc))
                lat = _norm(P["LeftUpLeg"] - P["RightUpLeg"])
                w = min(1.0, bend / 0.35)
                hv = _norm((hc / bend if bend > 1e-5 else lat) * w + lat * (1.0 - w))
                # the value is a weight (D-130): 1 = the hinge rules, between 0 and 1
                # the thigh's roll is part way from the stance solver's to the
                # hinge's, so a move can hand the leg over without a one-frame roll
                P[sd + "Hinge0"] = P[sd + "UpLeg"].copy()
                P[sd + "Hinge"] = P[sd + "UpLeg"] + hv * min(1.0, max(0.02, float(ps[key + "_hinge"])))
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
        elif name.endswith("UpperLeg") and name[:-8] + "Hinge" in P:
            # a kicking leg whose knee hinge was set (fit_stance, `_hinge`): the
            # thigh points where it was solved AND its hinge axis faces where the
            # bent leg says, so it never rolls about its own length (D-129)
            sd = name[:-8]
            a, b = LIMB[name]
            hv = P[sd + "Hinge"] - P[sd + "Hinge0"]
            F = _frame(hv, P[b] - P[a])
            R0 = _frame(np.array([1.0, 0.0, 0.0]), rig.dir[name])
            D[name] = F @ R0.T
            hw = float(np.linalg.norm(hv))                 # the hinge's weight (fit_stance)
            if hw < 0.98:
                par = D[rig.parent[name]]
                Dd = _swing(par @ rig.dir[name], P[b] - P[a]) @ par
                ax, ang = Matrix((D[name] @ Dd.T).tolist()).to_quaternion().to_axis_angle()
                D[name] = np.array(Matrix.Rotation(ang * hw, 3, ax)) @ Dd
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
    # the default order in which parts start home (as keyed_move sets it), for moves that set `_hold` themselves
    LAG = (("foot", 0.0), ("heel", 0.0), ("toe", 0.0), ("hips", 0.0), ("pelvis", 0.0), ("trunk", 1.0), ("shoulders", 1.5),
           ("hand", 1.0), ("elbow", 1.0), ("palm", 1.0), ("chin", 3.0), ("neck", 3.0), ("head", 3.0))

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
    hit = (0.02, hx + 0.30, hz)                            # D-135: beyond reach, so the arm locks (0.92 = 46 deg bent at the hit, it read as pulling back)
    # D-145 rebuild (owner: "the fighting mechanics look pale against other fighting
    # games, fully rebuild them"; brief: anticipation -> acceleration -> contact ->
    # follow-through -> recovery, the chain foot -> knee -> hip -> spine -> shoulder ->
    # elbow -> wrist). Frames 1-2: the load (knees dip, hip and lead shoulder cock back,
    # the fist drops and draws in 5 cm). Frame 3: the lead foot drives, the hip fires.
    # Contact: the shoulder and fist arrive last and overshoot 3 cm past the target,
    # then settle back onto it (the arm takes the load), chin tucked behind the
    # shoulder. Recovery: the fist snaps home faster than it went out, past the guard
    # by 4 cm, and settles.
    # the default hold (2) + hand lag (2) left the arm locked out for 7 frames: a jab
    # snaps home. The 3 active frames are the hold; the hand leaves one frame after the hips.
    out["LIGHT"] = dict(_recover=1.35, _hold=0, _lag=LAG, **head(a0, a1, T, 5.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        # D-149 (gameplay audit: the head travelled 18.6 cm in one frame into the contact, a pop):
        # the hips start forward a frame earlier and arrive softer; the fist still arrives last and fast
        "hips": [(0, (hips0, 0)), (2, (hips0 - 0.03, 0), "out"), (a0 - 1, (hips0 + 0.075, 0), "io"), (a0, (hips0 + 0.125, 0), "out"), (a1, (hips0 + 0.12, 0)),
                 (a1 + 4, (hips0 - 0.015, 0), "out"), (T - 2, (hips0, 0))],
        "pelvis": [(0, pel0), (2, pel(-7), "out"), (a0 - 1, pel(12), "in"), (a0, pel(21)), (a1, pel(20)), (a1 + 4, pel(-3), "out"), (T - 2, pel0)],
        "shoulders": [(0, sh0), (2, sho(-9), "out"), (a0 - 1, sho(6), "in"), (a0, sho(26), "in"), (a0 + 1, sho(24)), (a1, sho(23)), (a1 + 4, sho(-4), "out"), (T - 2, sh0)],
        "pelvis_h": [(0, ph0), (2, low(0.022), "out"), (a0 - 1, low(0.008), "in"), (a0, low(0.014)), (a1, low(0.014))] + settle(T, a1 + 5, ph0, 0.008),
        "lead_foot": [(0, lf0), (2, lf0), (a0, (lf0[0], lf0[1] + 0.12), "in"), (a1 + 2, (lf0[0], lf0[1] + 0.12)), (a1 + 5, lf0)],
        "rear_heel": [(0, 0.03), (2, 0.015), (a0, 0.07, "in"), (a1 + 5, 0.03)],
        "curl": [(0, 0.0), (2, -3.0, "out"), (a0, 6.0, "in"), (a1, 5.0), (a1 + 4, -1.5, "out"), (T - 2, 0.0)],
        "trunk": [(0, tr0), (2, lean(-3), "out"), (a0 - 1, lean(3.5), "io"), (a0, lean(6.5), "out"), (a1, lean(6)), (a1 + 4, lean(-1.5), "out"), (T - 2, tr0)],
        "lead_hand_abs": [(0, L), (2, (L[0] + 0.01, L[1] - 0.05, L[2] - 0.02), "out"),
                          (a0 - 1, (hit[0] + 0.03, L[1] + 0.22, hit[2] - 0.01), "in"),
                          (a0, (hit[0], hit[1] + 0.03, hit[2]), "in"), (a0 + 1, hit), (a1, (hit[0], hit[1] + 0.005, hit[2])),
                          (a1 + 1, (hit[0] + 0.01, hx - 0.06, hit[2] - 0.005), "out"),   # back inside reach at once (the target is 30 cm past it, so the arm stays locked until here)
                          (a1 + 2, (L[0] + 0.01, L[1] + 0.06, L[2] + 0.01), "out"), (a1 + 4, (L[0], L[1] - 0.04, L[2] + 0.015), "out"), (a1 + 7, (L[0], L[1] - 0.01, L[2])), (T - 2, L)],
        "lead_elbow": [(0, 0.2), (2, 0.3), (a0, 0.04), (a1 + 2, 0.22), (T - 2, 0.2)],
        # the rear fist tightens to the chin as the jab goes out (the guard does not sleep)
        "rear_hand_abs": [(0, R), (a0, (R[0] + 0.01, R[1] + 0.015, R[2] + 0.025), "in"), (a1 + 3, (R[0] + 0.01, R[1] + 0.015, R[2] + 0.025)), (T - 2, R)],
    })

    # Cross: sit back and load, drive off the rear foot, hip then chest then fist
    a0, a1, T, hx, hz = win(moves["HEAVY"])
    hit = (0.03, hx + 0.30, hz)                            # D-135: beyond reach, the arm locks (it was 59 deg bent at the hit)
    out["HEAVY"] = dict(_recover=1.5, **head(a0, a1, T, 9.0), **{
        "rear_palm": "auto",
        "hips": [(0, (hips0, 0)), (7, (hips0 - 0.10, 0)), (a0, (hips0 + 0.16, 0), "in"), (a1, (hips0 + 0.15, 0)),
                 (a1 + 8, (hips0 - 0.015, 0), "out"), (T - 3, (hips0, 0))],
        "pelvis_h": [(0, ph0), (7, low(0.05)), (a0, low(0.03)), (a1, low(0.03)), (a1 + 6, ph0 + 0.004, "out")] + settle(T, a1 + 11, ph0),
        "pelvis": [(0, pel0), (6, pel(20)), (a0 - 3, pel(14), "io"), (a0 - 1, pel(-40), "io"), (a0, pel(-52)), (a1, pel(-52)), (a1 + 8, pel(5), "out"), (T - 3, pel0)],   # D-133: the hips drive the cross (pelvis 50 deg against the chest 97 read as an arm punch)
        # D-135: the chest stopped at about square to the opponent (it turned 98 deg and showed the camera his back)
        "shoulders": [(0, sh0), (7, sho(34)), (a0 - 2, sho(28), "io"), (a0 - 1, sho(-40), "in"), (a0, sho(-64), "in"), (a0 + 1, sho(-60)), (a1, sho(-59)), (a1 + 8, sho(6), "out"), (T - 3, sh0)],
        "curl": [(0, 0.0), (7, -7.0), (a0, 10.0, "in"), (a1, 9.0), (a1 + 8, -2.0, "out"), (T - 3, 0.0)],   # D-134: the back arches as he loads and closes over the punch
        "trunk": [(0, tr0), (7, lean(-8)), (a0, lean(11), "in"), (a1, lean(10)), (a1 + 8, lean(-1.5), "out"), (T - 3, tr0)],
        "lead_foot": [(0, lf0), (5, lf0), (a0 - 1, (lf0[0], lf0[1] + 0.14), "in"), (a1 + 4, (lf0[0], lf0[1] + 0.14)), (a1 + 7, lf0)],
        # D-145: the chain starts at the floor. The rear heel lifts and turns out from
        # a0-4, before the hip fires (a0-3..a0-1), the chest a frame after it, the fist last.
        "rear_heel": [(0, 0.03), (5, 0.015), (a0 - 5, 0.025), (a0 - 1, 0.10, "io"), (a0, 0.115), (a1, 0.115), (a1 + 8, 0.03)],
        "rear_toe": [(0, base["rear_toe"]), (a0 - 5, base["rear_toe"]), (a0 - 1, -12.0, "io"), (a0, -15.0), (a1, -15.0), (a1 + 8, base["rear_toe"])],   # D-133: the rear heel turns out as the hip drives (the toe was barely turned)
        "rear_hand_abs": [(0, R), (7, (R[0] - 0.10, R[1] - 0.19, R[2] - 0.07)),   # D-130: a wind-up that shows (the fist drew back 11 cm; the chest turned 24)
                          (a0 - 2, (-0.07, R[1] + 0.05, R[2] - 0.03), "in"),
                          (a0, (hit[0], hit[1] + 0.045, hit[2]), "in"), (a0 + 1, hit), (a1, (hit[0], hit[1] + 0.005, hit[2])),
                          (a1 + 4, (R[0] + 0.02, R[1] - 0.03, R[2] + 0.01), "out"), (a1 + 8, (R[0], R[1] + 0.01, R[2])), (T - 3, R)],   # D-145: home fast, past the guard, settle
        "lead_hand_abs": [(0, L), (7, (L[0], L[1] - 0.07, L[2] + 0.03)),      # D-130: the guard sits back with him (it stayed out and the arm straightened for six frames)
                          (a0 - 2, (chin[0], chin[1] + 0.03, chin[2] - 0.03), "io"), (a0, chin), (a1 + 3, chin), (T - 3, L)],     # D-135: to the chin (the hikite point rode up beside his head as the chest turned)
        "lead_palm": "auto",
        "rear_elbow": [(0, 0.1), (a0, 0.06), (a1 + 5, 0.1)],
    })

    # Rising Front Kick (down + heavy). History: D-096/097 a standing front kick
    # to the belly (owner: "extend his leg more", "ball of the foot"); D-130 the
    # leg locked; D-132 hips over the foot. D-136, owner: "he leans back too far
    # and the kick only reaches knee height. Keep the chest upright, chamber the
    # knee, and kick at chest height" and "down + heavy is a standing kick, it
    # should be a crouching attack (or be renamed)". Now it starts from the
    # crouch the down input puts him in: he drives up out of it as the rear
    # knee comes up high to the chest (the chamber), the foot snaps out on a
    # locked leg at chest height off the ball of the foot, the chest stays
    # upright (a few degrees back, not 23), then the knee recoils through the
    # chamber and the foot is set down in the stance. The hitbox moved up to
    # the chest (kairo_body_hook.tres, 1.05 -> 1.25 m: a balance change) and the
    # move is renamed Rising Front Kick.
    a0, a1, T, hx, hz = win(moves["DOWN_HEAVY"])
    cr_h = ph0 - 0.33                                      # the crouch's pelvis height (STYLES crouch_pose drop)
    cr_lean = lean(13.0 / X)                               # the crouch's forward lean
    chamber = (FR[0] * 0.30, 0.26, 0.86, -0.35)            # knee up at the chest, foot tucked under it, toes pulled back
    out_far = (0.0, hx + 0.62, hz + 0.26, -0.95)           # beyond reach along the line of the kick: the leg locks at chest height
    out_hold = (0.0, hx + 0.64, hz + 0.24, -0.95)
    snap = (0.0, hx - 0.25, hz - 0.17, -0.7)               # half way out: the shin swings up and forward
    recoil = (FR[0] * 0.3, 0.28, 0.82, -0.4)
    lh0, rh0 = base["lead_hand"], base["rear_hand"]
    out["DOWN_HEAVY"] = dict(_recover=1.4, _blend_in=0, **head(a0, a1, T, 3.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "rear_hinge": [(0, 0.0), (3, 1.0), (a1 + 6, 1.0), (a1 + 10, 0.0)],
        "curl": [(0, 6.0), (3, 8.0), (a0 - 2, 12.0), (a0, -5.0, "in"), (a1, -4.0), (a1 + 5, 6.0), (T - 3, 0.0)],
        "hips_x": [(0, 0.0), (4, 0.04), (a0, 0.06), (a1, 0.06), (a1 + 7, 0.0)],
        "rear_toe": [(0, base["rear_toe"]), (5, 0.0), (a1 + 7, 0.0), (a1 + 10, base["rear_toe"])],
        # D-144 (audit: the hips were 16 cm behind the standing ankle at the hit)
        "hips": [(0, (hips0 + 0.02, 0)), (3, (hips0 + 0.10, 0), "io"), (a0 - 2, (hips0 + 0.20, 0)), (a0, (hips0 + 0.24, 0), "out"),
                 (a1, (hips0 + 0.13, 0)), (a1 + 4, (hips0 + 0.07, 0), "out"), (T - 3, (hips0, 0))],
        # up out of the crouch: the legs drive him up through the chamber, tall on the standing leg at the kick
        "pelvis_h": [(0, cr_h), (2, cr_h + 0.02, "io"), (5, ph0 - 0.06, "out"), (a0 - 1, ph0 + 0.02), (a0, ph0 + 0.04, "in"), (a1, ph0 + 0.035),
                     (a1 + 4, ph0 + 0.02)] + settle(T, a1 + 9, ph0, 0.018),
        # D-142 ("his upper body does not move with the kick"): the rear hip drives the
        # kick and the chest counter-turns, opens and leans back about 14 deg; the
        # kicking side's arm swings down and back past the hip, the lead fist stays up
        "pelvis": [(0, pel0), (3, pel(-8)), (a0 - 3, pel(-14)), (a0 - 1, pel(-36), "out"), (a0, pel(-40)), (a1, pel(-39)), (a1 + 6, pel(-12), "io"), (T - 3, pel0)],
        "shoulders": [(0, sh0), (3, sho(-2)), (a0 - 2, sho(-4)), (a0, sho(-10), "out"), (a1, sho(-9)), (a1 + 6, sho(-2), "io"), (T - 3, sh0)],
        # the chest stays up: forward over the crouch, upright through the chamber, only a few degrees back at the kick
        "trunk": [(0, cr_lean), (3, lean(6)), (a0 - 2, lean(4)), (a0 - 1, lean(-8, 3), "out"), (a0, lean(-13, 5)), (a1, lean(-13, 5)), (a1 + 2, lean(-15, 5)),
                  (a1 + 5, lean(3), "io"), (a1 + 8, lean(1)), (T - 3, tr0)],
        "lead_heel": [(0, 0.0), (4, 0.02), (a0, 0.05, "in"), (a1, 0.05), (a1 + 6, 0.01), (T - 4, 0.0)],
        "rear_foot_abs": [(0, FR + (0.0,)), (2, (FR[0] * 0.8, FR[1] * 0.6, 0.18, 0.1), "io"), (4, (FR[0] * 0.5, 0.12, 0.52, -0.1)), (a0 - 2, chamber, "out"),
                          (a0 - 1, snap, "in"), (a0, out_far), (a0 + 1, out_hold), (a1, out_hold),
                          (a1 + 1, (0.0, hx + 0.22, hz + 0.04, -0.8)), (a1 + 2, (0.0, hx - 0.15, hz - 0.12, -0.6)), (a1 + 4, recoil), (a1 + 6, (FR[0] * 0.8, FR[1] * 0.6, 0.32, -0.1)),
                          (a1 + 8, (FR[0] * 0.9, FR[1] * 0.85, 0.12, 0.0)), (a1 + 10, FR + (0.0,), "in")],
        # both hands stay a compact guard that rides with the chest (head-relative)
        "lead_hand_abs": [(0, L), (a0, (L[0], L[1] - 0.10, L[2] + 0.04), "in"), (a1 + 4, (L[0], L[1] - 0.10, L[2] + 0.04)), (T - 3, L)],
        "rear_hand_abs": [(0, R), (3, (R[0] - 0.02, R[1] - 0.04, R[2] - 0.12), "io"),
                          (a0, (R[0] - 0.12, -0.14, head_z - 0.52), "in"), (a1, (R[0] - 0.12, -0.15, head_z - 0.53)),
                          (a1 + 5, (R[0] - 0.06, R[1] - 0.08, R[2] - 0.14), "io"), (T - 3, R)],
        "lead_elbow": [(0, 0.25), (a0, 0.3), (T - 3, 0.25)],
    })

    # Counter strike (the Rift Guard's answer). D-135: it was a second copy of
    # the cross (same pose as Heavy and the One-Two). Now the lead hook its data
    # is named after (kairo_counter_hook): out of the parry the lead fist swings
    # round on a flat arc, elbow up at shoulder height, the forearm level; the
    # hips and chest turn in behind it from the lead side, the lead heel pivots
    # out and the rear fist stays at the chin. The silhouette is a bent arm
    # across the face, not a straight one.
    a0, a1, T, hx, hz = win(moves["FOLLOWUP"])
    # D-147 rebuild (owner: "that is not a counter attack"). The hook read as a
    # plain punch thrown from the guard: nothing showed that an attack had been
    # caught. Now it is a parry and a counter in one beat:
    #   f0-2  PARRY + SLIP: the lead hand sweeps out and forward, palm out,
    #         knocking the incoming strike past his head, while he drops 9 cm
    #         and slips his head forward and off the line (side lean);
    #   f3-4  COUNTER: from under the attack he drives up through the legs, the
    #         hips and chest turn in and the rear fist rises as a short
    #         uppercut up the middle to the chin, elbow under the fist;
    #   the parrying hand stays out over the attacker's arm through the hit
    #   (it is still controlling it), then both hands come home.
    # The rear uppercut is distinct from the cross (straight) and the rising
    # uppercut (lead hand, both feet leave the floor). Same frame data.
    # (a parry out to the side is invisible in the game's side view: it goes UP and
    # forward, the forearm deflecting the blow over his head)
    lh_out = (0.14, L[1] + 0.17, head_z + 0.12)            # the parry: up and forward, above his head
    lh_ctl = (0.13, L[1] + 0.06, head_z + 0.08)            # held up over the caught arm, elbow bent, through the counter
    up_hit = (0.0, hx - 0.27, hz + 0.12)                   # the uppercut: fist up at chin height, forearm vertical, inside reach
    out["FOLLOWUP"] = dict(_recover=1.35, _hold=1, _lag=LAG, **head(a0, a1, T, 8.0), **{
        "rear_palm": "auto", "lead_palm": "out",
        "hips": [(0, (hips0 - 0.05, 0)), (2, (hips0 + 0.03, 0), "out"), (a0, (hips0 + 0.10, 0), "in"), (a1, (hips0 + 0.10, 0)),
                 (a1 + 8, (hips0 - 0.01, 0), "out"), (T - 3, (hips0, 0))],
        # down under the attack, then up through it
        "pelvis_h": [(0, low(0.045)), (2, low(0.13), "out"), (a0, low(0.0), "in"), (a1, ph0 + 0.01)] + settle(T, a1 + 9, ph0, 0.015),
        "pelvis": [(0, pel(8)), (2, pel(15), "out"), (a0, pel(-30), "in"), (a1, pel(-33)), (a1 + 8, pel(2), "out"), (T - 3, pel0)],
        "shoulders": [(0, sho(12)), (2, sho(24), "out"), (a0, sho(-36), "in"), (a0 + 1, sho(-34)), (a1, sho(-33)), (a1 + 8, sho(5), "out"), (T - 3, sh0)],
        "curl": [(0, -3.0), (2, 10.0, "out"), (a0, 4.0, "in"), (a1, 3.0), (a1 + 8, -1.0, "out"), (T - 3, 0.0)],
        # the slip: forward and to the side, head off the line; up and back through the hit
        "trunk": [(0, lean(-3)), (2, lean(12, 9), "out"), (a0, lean(2, -3), "in"), (a1, lean(1, -2)), (a1 + 8, lean(-1)), (T - 3, tr0)],
        "rear_heel": [(0, 0.03), (1, 0.02), (a0, 0.10, "io"), (a1, 0.10), (a1 + 8, 0.03)],
        "rear_toe": [(0, base["rear_toe"]), (1, base["rear_toe"]), (a0, -10.0, "io"), (a1, -10.0), (a1 + 8, base["rear_toe"])],
        "lead_hand_abs": [(0, (L[0] - 0.06, L[1] - 0.08, L[2] + 0.06)), (1, (0.14, L[1] + 0.05, L[2] + 0.04), "out"), (2, lh_out, "out"),
                          (a0, lh_ctl), (a1, (lh_ctl[0] - 0.01, lh_ctl[1] - 0.01, lh_ctl[2] - 0.01)),
                          (a1 + 3, (L[0] + 0.06, L[1] + 0.02, L[2] + 0.02), "io"), (a1 + 7, L), (T - 3, L)],
        "lead_elbow": [(0, 0.2), (2, 0.7), (a1, 0.7), (a1 + 5, 0.2)],
        "rear_hand_abs": [(0, R), (2, (R[0] + 0.02, R[1] - 0.02, R[2] - 0.32), "out"),           # loaded low by the dip
                          (a0 - 1, (0.02, R[1] + 0.10, hz - 0.30), "in"), (a0, (up_hit[0], up_hit[1], up_hit[2] - 0.03), "in"), (a0 + 1, up_hit),
                          (a1, (up_hit[0], up_hit[1] - 0.01, up_hit[2] + 0.02)),
                          (a1 + 2, (R[0], R[1] + 0.04, R[2] + 0.10), "out"), (a1 + 5, (R[0], R[1] - 0.02, R[2] + 0.01)), (T - 3, R)],
        "rear_elbow": [(0, 0.1), (2, 0.0), (a1, 0.0), (a1 + 5, 0.1)],
    })

    # Front Kick (Kick). D-138, owner, three times about the Kick button ("leans
    # far back, the foot only reaches knee height, over in a third of a second.
    # Keep his chest upright, lift the knee first, kick at chest height, and
    # hold the extended kick for a moment"). The Kick button was the Low Kick
    # (a low roundhouse to the shin, approved at D-111, lean halved at D-137);
    # it is now a lead-leg front kick (a push kick): the weight settles onto
    # the rear leg, the lead knee comes up to the chest first, the foot drives
    # out at chest height off the ball of the foot on a locked leg and stays
    # out for five frames (`_hold`), then the knee folds back and the foot is
    # set down on its own mark. Chest upright (5 deg back at most). Data:
    # mid, hitbox at 1.25 m (kairo_low_kick.tres keeps its id); his low attack
    # is the Leg Sweep (down + Kick).
    a0, a1, T, hx, hz = win(moves["KICK"])
    lhk, rhk = base["lead_hand"], base["rear_hand"]
    ch_l = (FL[0] * 0.7, 0.30, 0.84, -0.35)                # knee at the chest, foot tucked under it
    snap_l = (FL[0] * 0.4, hx - 0.25, hz - 0.05, -0.7)
    far_l = (FL[0] * 0.2, hx + 0.55, hz + 0.50, -0.95)     # beyond reach along the kick: the leg locks at chest height
    hold_l = (FL[0] * 0.2, hx + 0.57, hz + 0.48, -0.95)
    rec_l = (FL[0] * 0.7, 0.32, 0.80, -0.4)
    out["KICK"] = dict(_recover=1.0, _hold=5, _lag=LAG, _impact=0.4, **head(a0, a1, T, 3.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "lead_hinge": [(0, 0.0), (2, 1.0), (a1 + 6, 1.0), (a1 + 8, 0.0)],
        "lead_toe": [(0, base["lead_toe"]), (3, 0.0), (a1 + 6, 0.0), (a1 + 8, base["lead_toe"])],
        "_feet_abs": (0, T - 1),                           # output frames, not key time: the hold pushes the set-down later
        "lead_foot_abs": [(0, FL + (0.0,)), (2, (FL[0], FL[1] - 0.02, FL[2] + 0.10, 0.1), "io"), (4, (FL[0] * 0.85, 0.20, 0.48, -0.1)), (a0 - 2, ch_l, "out"),
                          (a0 - 1, snap_l, "in"), (a0, far_l), (a0 + 1, hold_l), (a1, hold_l),
                          (a1 + 1, (FL[0] * 0.4, hx - 0.05, hz - 0.08, -0.7)), (a1 + 3, rec_l), (a1 + 5, (FL[0] * 0.85, 0.22, 0.42, -0.1)),
                          (a1 + 7, (FL[0], FL[1] + 0.02, FL[2] + 0.06, 0.0)), (a1 + 8, FL + (0.0,), "in")],   # recovery keys fit the frames _recover can reach
        # weight back over the rear foot, the pelvis riding over it
        # D-144 (audit): the hips sit back over the standing foot through the chamber and
        # THRUST forward into the kick a frame before the foot arrives (they moved back)
        "hips": [(0, (hips0, 0)), (4, (hips0 - 0.12, 0), "io"), (a0 - 2, (hips0 - 0.14, 0)), (a0 - 1, (hips0 - 0.12, 0), "out"), (a0, (hips0 - 0.115, 0)), (a1, (hips0 - 0.12, 0)),
                 (a1 + 5, (hips0 - 0.06, 0)), (a1 + 9, (hips0, 0), "io")],
        "hips_x": [(0, 0.0), (4, -0.04), (a1 + 7, -0.04), (a1 + 11, 0.0)],
        "pelvis_h": [(0, ph0), (3, low(0.03), "io"), (a0 - 2, ph0 + 0.01), (a0, ph0 + 0.025, "in"), (a1, ph0 + 0.02)] + settle(T, a1 + 10, ph0, 0.015),
        # D-142 (owner: "his upper body does not move with the kick, he looks like a
        # mannequin"): the body now works with the leg. Chamber: the chest crunches
        # forward over the rising knee. Kick: the lead hip drives into it, the chest
        # opens and leans back into one line with the leg (about 14 deg, not the 30+
        # she rejected on the old low kick), the kicking side's arm swings down and
        # back past the hip to balance, the rear fist tucks at the chin. Recovery:
        # the chest comes forward again as the leg folds back.
        # D-144 (audit: the hip and chest turned fastest ON the contact frame, after the
        # foot: the leg led the body). Now the hip drives first (fastest a0-2..a0-1),
        # the chest answers a frame later, the foot arrives last.
        "pelvis": [(0, pel0), (4, pel(4)), (a0 - 3, pel(2)), (a0 - 1, pel(18), "out"), (a0, pel(20)), (a1, pel(19)), (a1 + 5, pel(6), "io"), (a1 + 9, pel0)],
        "shoulders": [(0, sh0), (4, sho(8)), (a0 - 2, sho(6)), (a0, sho(-12), "out"), (a1, sho(-11)), (a1 + 5, sho(-2), "io"), (a1 + 9, sh0)],
        # chest upright: a touch forward as the knee comes up, a few degrees back at the kick
        # leaning away from the chest-high leg 16 deg; after the hold the body gives back a
        # little further (the rebound of the contact), then comes forward to the stance
        "trunk": [(0, tr0), (4, lean(5)), (a0 - 2, lean(4)), (a0 - 1, lean(-8, -3), "out"), (a0, lean(-13, -5)), (a1, lean(-13, -5)), (a1 + 2, lean(-15, -5)),
                  (a1 + 5, lean(2), "io"), (a1 + 8, lean(1)), (a1 + 10, tr0)],
        "curl": [(0, 0.0), (4, 9.0), (a0 - 2, 12.0), (a0, -5.0, "in"), (a1, -4.0), (a1 + 4, 6.0), (a1 + 9, 0.0)],
        "rear_heel": [(0, 0.012), (3, 0.0), (a1 + 8, 0.0), (a1 + 11, 0.012)],
        # the guard stays up and rides with the chest; the kicking side's fist drops a little to balance
        "lead_hand_abs": [(0, L), (4, (L[0] + 0.03, L[1] - 0.06, L[2] - 0.12), "io"),
                          (a0, (L[0] + 0.14, -0.10, head_z - 0.52), "in"), (a1, (L[0] + 0.14, -0.12, head_z - 0.53)),
                          (a1 + 4, (L[0] + 0.08, L[1] - 0.10, L[2] - 0.14), "io"), (a1 + 9, L)],
        "lead_elbow": [(0, 0.25), (a0, 0.15), (a1 + 6, 0.25)],
        "rear_hand_abs": [(0, R), (5, (R[0] - 0.01, R[1] + 0.02, R[2] + 0.01), "io"), (a1 + 4, (R[0] - 0.01, R[1] + 0.03, R[2] + 0.01)), (a1 + 9, R)],
    })

    # Spinning Back Kick (forward + heavy, D-142; owner's quality brief: "a new
    # spinning kick with a real heel pivot and momentum"). He turns his back to
    # the opponent by pivoting on the ball of the lead foot (the heel swings
    # out), the shoulders and head leading the hips round, looks over his
    # shoulder, chambers the rear knee tight, then drives the heel straight back
    # into the opponent at chest height on a locked leg, his body leaning away
    # from it in one line. He retracts the leg through the chamber and unwinds
    # into the stance. Pelvis/shoulders are keyed as the turn from side-on.
    if "FORWARD_HEAVY" in moves:
        a0, a1, T, hx, hz = win(moves["FORWARD_HEAVY"])
        def turn_to(deg, base_):
            return base_ + (deg - base_)                   # absolute degrees (not scaled by X)
        sp_back = 160.0                                    # back to the opponent (all but square)
        sp_ch = (FR[0] * 0.2, 0.05, 0.62, -0.5)            # knee up, heel pulled to the seat
        # D-149 (brief: "spinning back-roundhouse ... a powerful horizontal kick", not a thrust):
        # the leg opens out to his left side as the hips come round (the way they turn), then
        # sweeps horizontally across to the opponent at chest height, heel leading, carries a
        # little past the line (follow-through) and folds back in.
        # (heights: the contact lands ~13 cm under a beyond-reach target; the whole arc is
        # kept level at chest height, it does not rise over the head as the first try did)
        sp_open = (0.45, 0.0, hz + 0.12, -0.85)             # opening out to the side
        sp_arc1 = (0.55, hx * 0.45, hz + 0.18, -0.9)        # round the arc, gathering speed
        sp_arc2 = (0.40, hx + 0.15, hz + 0.22, -0.9)
        sp_far = (0.04, hx + 0.55, hz + 0.23, -0.95)        # the contact: beyond reach toward the opponent, the leg locks
        sp_hold = (-0.10, hx + 0.53, hz + 0.22, -0.95)      # carrying through the line
        sp_thru = (-0.24, hx + 0.45, hz + 0.19, -0.9)       # follow-through past the line
        spin_toe = [(0, base["lead_toe"]), (3, base["lead_toe"]), (9, base["lead_toe"] + 150.0, "io"), (a1 + 5, base["lead_toe"] + 145.0),
                    (a1 + 14, base["lead_toe"], "out")]
        # D-149: the marks are multiplied by the stance height (~1.7), so 0.13 put the ankle's
        # correction 23 cm from the ball instead of 13 cm: the over-correction itself slid the
        # ball 22 cm (measured on the game model). 13 cm / 1.7.
        ball_d = 0.076                                      # ankle to the ball of the foot, in stance-mark units

        def ball_kept(yaw):
            y0 = math.radians(base["lead_toe"])
            y1 = math.radians(yaw)
            return (lf0[0] + ball_d * (math.sin(y0) - math.sin(y1)), lf0[1] + ball_d * (math.cos(y0) - math.cos(y1)))
        # sample the toe track every frame and key the matching mark, so both follow one curve
        # D-149: what the ankle mark alone leaves (measured on the game model, ball of the
        # lead foot, metres, x / forward, by OUTPUT frame 1..): the hips' travel and the
        # stance solver carry the foot too. Taken off the mark so the ball stays put.
        drift = {5: (-0.01, 0.0), 6: (-0.01, 0.05), 7: (0.02, 0.10), 8: (0.08, 0.12), 9: (0.13, 0.12)}
        for f_ in range(10, 26):
            drift[f_] = (0.15, 0.105)
        drift.update({26: (0.14, 0.11), 27: (0.11, 0.12), 28: (0.07, 0.12), 29: (0.05, 0.11), 30: (0.03, 0.09),
                      31: (0.01, 0.08), 32: (0.0, 0.06), 33: (0.0, 0.04), 34: (0.0, 0.02), 35: (0.0, 0.01)})
        sp_hold_n, sp_slow = 3, 1.25                         # the `_hold` / `_recover` the drift was MEASURED with (it is a function of key time)

        def out_frame(k):                                    # key time -> the output frame (1-based) that plays it
            if k <= a1:
                return k + 1
            return int(round(a1 + sp_hold_n + (k - a1 - sp_hold_n * 0.125) * sp_slow)) + 1

        def kept(k):
            m_ = ball_kept(curve(k, spin_toe))
            d_ = drift.get(out_frame(k), (0.0, 0.0))
            return (m_[0] - d_[0] / H_MARK, m_[1] - d_[1] / H_MARK)
        H_MARK = 1.0                                         # metres per stance-mark unit for Kairo (H = height / 1.8)
        spin_mark = [(k, kept(k)) for k in range(0, a1 + 15)]
        out["FORWARD_HEAVY"] = dict(_recover=1.25, _hold=1,   # D-149: 3 left the leg frozen out for ~9 frames; the follow-through keys carry it now
             _lag=LAG, _impact=0.5, **head(a0, a1, T, 4.0), **{
            "lead_palm": "auto", "rear_palm": "auto",
            "_feet_abs": (0, T - 1),
            # the spin: shoulders first, hips a few frames behind, held while the leg is out
            # the chest stops short of the hips (135 against 175) so the head can look
            # back over the shoulder within a neck's reach (it was turned 130 deg)
            # D-143 (critique: "the spine snaps on the way out, no deceleration"): the
            # unwind is spread over 14 frames and slows into the stance ("out")
            # D-147 (owner: "his lower body rotates but his upper body stays the same").
            # Measured: the chest turned 95 deg against the pelvis's 121 and stopped at 133,
            # which from the side camera looks the same as the stance (both show the chest
            # three-quarters to the camera). Now the shoulders and head LEAD the spin and go
            # all the way round: a wind-up the other way, then they whip to 175 by frame 9
            # (ahead of the hips), the hips follow to 172; at the kick his back is to the
            # opponent and the camera sees his chest in profile. The arms swing out with the
            # turn (below) so the rotation reads.
            "shoulders": [(0, sh0), (3, sh0 - 14.0, "io"), (6, 95.0, "in"), (9, 172.0, "out"), (a0 - 3, 178.0), (a0, 172.0), (a1, 170.0),
                          (a1 + 5, 160.0), (a1 + 10, 95.0), (a1 + 14, sh0, "out")],
            "pelvis": [(0, pel0), (3, pel0 - 6.0, "io"), (8, 118.0, "in"), (10, 165.0, "out"), (a0 - 2, 172.0), (a1, 172.0), (a1 + 5, 155.0), (a1 + 10, 95.0), (a1 + 14, pel0, "out")],
            # D-143 (critique: "it rotates evenly on both feet, as on a turntable"): the
            # weight goes onto the lead foot first and the rear foot drives off the
            # floor on its ball (heel up, then gone by frame 5), so the turn is one
            # foot's pivot
            "hips_x": [(0, 0.0), (3, 0.06, "io"), (a1 + 6, 0.06), (a1 + 13, 0.0)],
            "rear_heel": [(0, base.get("rear_heel", 0.012)), (2, 0.07, "io"), (4, 0.09), (a1 + 11, 0.05), (a1 + 14, base.get("rear_heel", 0.012))],
            # the lead foot turns on its ball (heel out), stays planted
            "lead_toe": spin_toe,
            # D-144 (audit: the lead foot slid 41 cm while it pivoted): the solver turns the
            # foot about the ankle, so the ball swung round on an arc. The ankle mark now
            # moves against the turn so the ball of the foot stays on its spot.
            "lead_foot": spin_mark,
            # D-149 (owner's brief: "NOT a jumping spin ... grounded, pivot the supporting foot
            # naturally"): the D-147 skip-step is gone; the foot pivots on its ball (ball_d fixed).
            # Head (brief: "the head fails to follow the body and the neck deforms"). Measured:
            # the head kept a quarter of the chest's turn (pose_stance `head_turn` 0.25), so with
            # the chest at 175 the head was turned 134 deg against the chest: that twist is the
            # neck deformation, and the head looked stuck while the body spun. A neck turns about
            # 70-80 deg. Now the head LEADS the spin (the fighter spots the target over his
            # shoulder): it stays within ~60-70 deg ahead of the chest, and comes back to the
            # usual quarter turn as he unwinds into the stance.
            "head_turn": [(0, 0.25), (3, 0.25), (6, 1.12, "io"), (9, 1.26), (a0 - 3, 1.28), (a1, 1.30), (a1 + 5, 1.20),
                          (a1 + 10, 0.70, "io"), (a1 + 14, 0.25, "out")],
            "lead_heel": [(0, 0.0), (3, 0.04), (9, 0.05), (a0, 0.03), (a1 + 6, 0.03), (a1 + 13, 0.0)],
            "hips": [(0, (hips0, 0)), (4, (hips0 + 0.10, 0)), (9, (hips0 + 0.22, 0)), (a0 - 2, (hips0 + 0.36, 0)), (a0, (hips0 + 0.50, 0), "in"), (a1, (hips0 + 0.50, 0)), (a1 + 8, (hips0 + 0.26, 0)), (a1 + 13, (hips0, 0), "io")],   # over the standing (lead) foot, whose ankle the pivot carries 26 cm forward (D-144)
            "pelvis_h": [(0, ph0), (3, low(0.05), "io"), (9, low(0.03)), (a0, ph0 + 0.01, "in"), (a1, ph0 + 0.01)] + settle(T, a1 + 12, ph0, 0.015),
            # leaning away from the kick (body frame: forward, since his back faces the opponent)
            # the trunk channel is measured toward the opponent: negative = away from the kick
            "trunk": [(0, tr0), (3, lean(4)), (9, lean(2)), (a0 - 2, lean(-5)), (a0 - 1, lean(-12)), (a0, lean(-20, 0)), (a1, lean(-19)), (a1 + 6, lean(-6)), (a1 + 12, tr0, "io")],
            "curl": [(0, 0.0), (5, 6.0), (a0 - 2, 10.0), (a0, 2.0, "in"), (a1, 2.0), (a1 + 6, 6.0), (a1 + 12, 0.0)],
            "rear_hinge": [(0, 0.0), (6, 1.0), (a1 + 8, 1.0), (a1 + 12, 0.0)],
            "rear_toe": [(0, base["rear_toe"]), (6, 0.0), (a1 + 8, 0.0), (a1 + 12, base["rear_toe"])],
            "rear_foot_abs": [(0, FR + (0.0,)), (3, FR + (0.0,)), (5, (FR[0] * 0.9, FR[1] * 0.85, FR[2] + 0.08, 0.4), "in"), (8, (FR[0] * 0.6, FR[1] * 0.6, 0.30, 0.0), "io"), (a0 - 5, (FR[0] * 0.35, 0.10, 0.50, -0.3)), (a0 - 4, sp_ch, "out"), (a0 - 3, sp_open, "in"),
                              (a0 - 2, sp_arc1), (a0 - 1, sp_arc2), (a0, sp_far, "in"), (a0 + 1, sp_hold), (a1, sp_thru, "out"),
                              (a1 + 2, (-0.20, hx + 0.20, hz + 0.20, -0.8)), (a1 + 4, (FR[0] * 0.2, hx - 0.15, hz - 0.02, -0.6)), (a1 + 6, (FR[0] * 0.2, 0.30, 0.80, -0.55)), (a1 + 7, sp_ch), (a1 + 8, (FR[0] * 0.7, FR[1] * 0.6, 0.25, 0.0)),
                              (a1 + 11, (FR[0] * 0.95, FR[1] * 0.95, FR[2] + 0.04, 0.0)), (a1 + 12, FR + (0.0,), "in")],
            # guard tight to the body through the spin; the arms stay in
            # D-147: the lead arm swings out with the whip of the turn (it was tucked and still,
            # so nothing above the hips showed the spin), then comes back to the guard for the kick
            "lead_hand": [(0, base["lead_hand"]), (5, (base["lead_hand"][0], base["lead_hand"][1] - 0.10, base["lead_hand"][2] + 0.02)),
                          (8, (base["lead_hand"][0] + 0.16, base["lead_hand"][1] - 0.16, base["lead_hand"][2] - 0.06), "out"),
                          (a0 - 2, (base["lead_hand"][0], base["lead_hand"][1] - 0.10, base["lead_hand"][2] + 0.02), "io"),
                          (a1 + 6, (base["lead_hand"][0], base["lead_hand"][1] - 0.10, base["lead_hand"][2] + 0.02)), (a1 + 12, base["lead_hand"])],
            # the rear fist leaves the chest as he turns (it sank into the armoured trunk
            # with his back to the opponent) and is held out to his side for balance
            "rear_hand_abs": [(0, R), (5, (R[0] - 0.08, R[1] - 0.04, R[2] - 0.02), "io"), (a0 - 3, (-0.30, -0.06, head_z - 0.18)),
                              (a1 + 4, (-0.30, -0.06, head_z - 0.20)), (a1 + 12, R, "io")],
            "rear_elbow": [(0, 0.3), (5, 0.5), (a1 + 6, 0.5), (a1 + 12, 0.3)],
        })

    # Origin Palm: a long load onto the rear leg with the palm chambered at
    # the ribs and the guard hand still up, then a lunging open-hand thrust
    a0, a1, T, hx, hz = win(moves["SPECIAL"])
    # D-135 (critique: "a chest-out flex with the arms spread, it strikes in no
    # direction"): the rear hand no longer goes up over the head in the wind-up
    # and stays out at the hit. Now the rear fist stays at the chin, then pulls
    # back to the hip (hikite) as the lead palm drives out on a locked arm, the
    # lead shoulder leading (side-on, not square): one line from the rear foot
    # through the shoulders to the palm.
    hit = (0.0, hx + 0.25, hz)                             # beyond reach: the arm locks
    hipz_p = head_z - 0.60
    out["SPECIAL"] = dict(_recover=1.5, **head(a0, a1, T, 6.0), **{
        "rear_palm": "auto",
        "lead_palm": [(0, base["lead_palm"]), (8, (0.0, 0.0, 1.0)), (a0 - 3, (0.0, -0.4, 1.0)), (a0, (0.0, -1.0, 0.3), "in"),
                      (a1, (0.0, -1.0, 0.3)), (a1 + 8, base["lead_palm"])],
        "hips": [(0, (hips0, 0)), (8, (hips0 - 0.11, 0)), (a0, (hips0 + 0.22, 0), "in"), (a1, (hips0 + 0.26, 0)),   # D-133: weight onto the stepping foot
                 (a1 + 11, (hips0 - 0.015, 0), "out"), (T - 4, (hips0, 0))],
        "pelvis_h": [(0, ph0), (8, low(0.075)), (a0, low(0.06), "in"), (a1, low(0.06)), (a1 + 9, ph0 + 0.004, "out")] + settle(T, a1 + 15, ph0),
        "pelvis": [(0, pel0), (8, pel(-18)), (a0 - 2, pel(34), "in"), (a1, pel(34)), (a1 + 11, pel(-3), "out"), (T - 4, pel0)],
        "shoulders": [(0, sh0), (8, sho(-28)), (a0, sho(26), "in"), (a1, sho(25)), (a1 + 11, sho(-4), "out"), (T - 4, sh0)],
        "curl": [(0, 0.0), (8, -4.0), (a0, 8.0, "in"), (a1, 9.0), (a1 + 11, -2.0, "out"), (T - 4, 0.0)],
        "trunk": [(0, tr0), (8, lean(-5)), (a0, lean(10), "in"), (a1, lean(9)), (a1 + 11, lean(-1.5), "out"), (T - 4, tr0)],
        "lead_foot": [(0, lf0), (8, (lf0[0], lf0[1] - 0.04)), (a0 - 1, (lf0[0], lf0[1] + 0.23), "in"), (a1 + 4, (lf0[0], lf0[1] + 0.23)), (a1 + 8, lf0)],
        "lead_heel": [(0, 0.0), (8, 0.035), (a0 - 1, 0.0, "in")],
        "rear_heel": [(0, 0.03), (8, 0.0), (a0, 0.09, "in"), (a1, 0.09), (a1 + 10, 0.03)],
        "lead_hand_abs": [(0, L), (8, (0.22, 0.0, hz - 0.20)), (a0 - 3, (0.16, 0.22, hz - 0.12), "in"),
                          (a0, (hit[0], hit[1] - 0.03, hit[2]), "in"), (a1, (hit[0], hit[1] + 0.05, hit[2] + 0.01)),   # D-130: the palm drives on through the five active frames (it stood still)
                          (a1 + 7, (L[0], L[1] + 0.06, L[2] - 0.05), "out"), (T - 4, L)],
        "lead_elbow": [(0, 0.15), (8, 0.35), (a0, 0.05), (a1 + 7, 0.15)],
        # D-136 (owner: "the back arm flies out sideways like a wing, keep it tucked in"):
        # the fist comes back to his own ribs, elbow in against the side
        "rear_hand_abs": [(0, R), (8, (R[0] + 0.02, R[1] + 0.02, R[2] - 0.03)), (a0, (R[0] - 0.01, R[1] - 0.03, R[2] - 0.08), "in"),
                          (a1 + 4, (R[0] - 0.01, R[1] - 0.03, R[2] - 0.08)), (T - 4, R)],   # stays a tight guard under the jaw (a hip chamber put the shoulder far back: the arm stuck out behind)
        "rear_elbow": [(0, 0.1), (8, 0.05), (a0, 0.0), (a1 + 4, 0.0), (T - 4, 0.1)],
    })

    # Fireball (down + special, D-101): both open palms are drawn back to the
    # rear hip as he sinks and coils away, then driven forward together at
    # chest height as the fireball leaves on the first active frame; the
    # palms stay out a moment, then he settles back into the stance.
    a0, a1, T, hx, hz = win(moves["DOWN_SPECIAL"])
    # D-130: the cup sat at chest height in front of him (it did not read as a
    # wind-up), the rear arm arrived bent, and the push stood frozen for ten
    # frames (the release pose was held to a1 + 6 in key time). Now both
    # palms go down and back to the rear hip as he sinks and coils, both arms
    # drive out long, and the recoil starts two frames after the release:
    # hands ride up and back, weight rocks to the rear leg, then the stance.
    hipz = head_z - 0.62
    cup_l = (-0.14, -0.20, hipz + 0.10)                    # lead palm over the rear hip (D-135: further back, the wind-up must read)
    cup_r = (-0.24, -0.24, hipz + 0.00)                    # rear palm under it
    push_l = (0.03, hx + 0.20, hz + 0.03)                  # D-135: beyond reach, both arms lock out (the push never straightened)
    push_r = (-0.05, hx + 0.15, hz - 0.07)
    rec_l = (L[0], L[1] + 0.10, L[2] + 0.03)
    rec_r = (R[0], R[1] + 0.12, R[2] + 0.02)
    out["DOWN_SPECIAL"] = dict(_recover=1.6, **head(a0, a1, T, 5.0), **{
        "lead_palm": [(0, base["lead_palm"]), (a0 - 4, (0.0, 0.3, -1.0)), (a0, (0.0, -1.0, 0.25), "in"), (a1 + 3, (0.0, -1.0, 0.25)),
                      (a1 + 9, base["lead_palm"])],
        "rear_palm": [(0, (0.0, 0.0, 1.0)), (a0 - 4, (0.0, 0.3, 1.0)), (a0, (0.0, -1.0, -0.25), "in"), (a1 + 3, (0.0, -1.0, -0.25)),
                      (a1 + 9, (0.0, 0.0, 1.0))],
        "hips": [(0, (hips0, 0)), (a0 - 4, (hips0 - 0.12, 0), "io"), (a0, (hips0 + 0.15, 0), "in"), (a1 + 1, (hips0 + 0.16, 0)),
                 (a1 + 7, (hips0 - 0.03, 0)), (a1 + 11, (hips0, 0))],
        "pelvis_h": [(0, ph0), (a0 - 4, low(0.11), "io"), (a0, low(0.07), "in"), (a1 + 1, low(0.07)), (a1 + 7, ph0 + 0.008), (a1 + 11, ph0)],
        "pelvis": [(0, pel0), (a0 - 4, pel(24), "io"), (a0, pel(-30), "in"), (a1 + 1, pel(-30)), (a1 + 7, pel(4)), (a1 + 11, pel0)],
        "shoulders": [(0, sh0), (a0 - 4, sho(40), "io"), (a0, sho(-46), "in"), (a1 + 1, sho(-46)), (a1 + 7, sho(5)), (a1 + 11, sh0)],
        "curl": [(0, 0.0), (a0 - 4, -12.0, "io"), (a0, 16.0, "in"), (a1 + 1, 15.0), (a1 + 7, -3.0), (a1 + 11, 0.0)],   # D-134: coiled open over the cup, closed over the release
        "trunk": [(0, tr0), (a0 - 4, lean(-6), "io"), (a0, lean(10), "in"), (a1 + 1, lean(10)), (a1 + 7, lean(-2)), (a1 + 11, tr0)],
        "lead_foot": [(0, lf0), (a0 - 1, (lf0[0], lf0[1] + 0.12), "in"), (a1 + 4, (lf0[0], lf0[1] + 0.12)), (a1 + 7, lf0)],
        "rear_heel": [(0, 0.012), (a0 - 4, 0.0), (a0, 0.08, "in"), (a1 + 1, 0.08), (a1 + 7, 0.012)],
        "lead_hand_abs": [(0, L), (a0 - 4, cup_l, "io"), (a0, (push_l[0], push_l[1] + 0.04, push_l[2]), "in"), (a0 + 1, push_l),
                          (a1 + 1, (push_l[0], push_l[1] - 0.02, push_l[2] + 0.02)), (a1 + 6, rec_l), (a1 + 11, L)],
        "rear_hand_abs": [(0, R), (a0 - 4, cup_r, "io"), (a0, (push_r[0], push_r[1] + 0.04, push_r[2]), "in"), (a0 + 1, push_r),
                          (a1 + 1, (push_r[0], push_r[1] - 0.02, push_r[2] + 0.02)), (a1 + 6, rec_r), (a1 + 11, R)],
        "lead_elbow": [(0, 0.2), (a0 - 4, 0.3), (a0, 0.04), (a1 + 1, 0.04), (a1 + 9, 0.2)],
        "rear_elbow": [(0, 0.05), (a0 - 4, 0.25), (a0, 0.04), (a1 + 1, 0.04), (a1 + 9, 0.05)],
    })

    # D-103: the three moves that filled the gaps in his kit (owner: "yes" to
    # a throw, a sweep and an anti-air).
    # Rising Uppercut (down + light): a quick dip with the rear fist dropped
    # to the hip, then he explodes up onto his toes and the fist drives up
    # past his head, the body turning behind it; a slow landing (punishable).
    a0, a1, T, hx, hz = win(moves["DOWN_LIGHT"])
    u_low = (-0.16, 0.04, R[2] - 0.24)
    u_hit = (0.02, 0.24, head_z - 0.24)                   # D-135: from the head, not the box; D-130: under the chin on the first active frame; the fist then rises through the active frames instead of standing at the top
    # D-135 (critique: "the arm swings straight up past his head with no knee
    # drive"): the fist stops at the top of his own head with the arm bent
    # about 90 (an uppercut, not a raised arm); the dip into the knees is
    # deeper so the legs visibly drive it
    # D-136 (owner: "the fist never rises above the chin; a hip drop, a push up
    # from the legs, and the fist finishing above the head"): the top is above
    # his head, still in front of it with the elbow bent, not a straight arm
    u_top = (0.02, 0.22, head_z + 0.34)
    # D-130 (owner: "check all his skills ... maximum improvement"): the fist
    # stood in the air for 18 frames (frames 9-26) and snapped home in the last
    # four, because the recovery keys sat at T - 4, later than `_recover` ever
    # plays. Now the way down is keyed inside the reachable time: the fist
    # carries on up a little, comes down in front of the face as the heels
    # drop, he lands in a dip leaning forward, and rises into the stance.
    # D-137 (owner: "the arm is right now, but his body stays upright; a small
    # dip in the knees before the punch and a lift up through it"): the dip had
    # three frames and could not be seen. Startup 5 -> 7 (invulnerable 1-7, the
    # travel moved to frames 4-9: a balance change, the anti-air is 2 frames
    # slower): he sinks into his knees over four frames with the chest folding
    # forward, then the legs drive him up onto his toes, higher than before.
    # D-138 (owner, again: "his body still doesn't dip and rise with it"): four
    # frames were still too short to see. Startup 7 -> 9 (invulnerable 1-9,
    # travel 6-11: a balance change), a 30 % sink with the chest folding 20 deg
    # forward over six frames, then up onto the toes, hips 18 % above standing.
    out["DOWN_LIGHT"] = dict(_recover=1.4, _hold=4, _lag=LAG, **{**head(a0, a1, T, -6.0), **{     # D-139: the top is held 3 frames longer so the hit reads
        # D-139 (owner: "a small hop at the top"): both feet leave the floor for a few frames
        # as the fist reaches the top (output frames 10-19 are placed from the keyed hip height)
        "_air": (10, 19),
        "lead_hop": [(0, 0.0), (a1 - 3, 0.0), (a1 - 1, 0.06, "out"), (a1 + 1, 0.05), (a1 + 3, 0.0, "in")],
        "rear_hop": [(0, 0.0), (a1 - 3, 0.0), (a1 - 1, 0.07, "out"), (a1 + 1, 0.06), (a1 + 3, 0.0, "in")],
        "chin": [(0, chin0), (a0, chin0 - 6, "in"), (a1 + 1, chin0 - 6), (a1 + 5, chin0 + 8), (a1 + 12, chin0)],
        "hips": [(0, (hips0, 0)), (5, (hips0 - 0.02, 0), "io"), (a0, (hips0 + 0.10, 0), "in"), (a1, (hips0 + 0.12, 0)),
                 (a1 + 5, (hips0 + 0.05, 0)), (a1 + 12, (hips0, 0))],
        "pelvis_h": [(0, ph0), (1, ph0 - 0.01), (5, low(0.30), "io"), (a0, ph0 + 0.03, "out"), (a1 - 1, ph0 + 0.18), (a1 + 1, ph0 + 0.16),
                     (a1 + 5, low(0.075)), (a1 + 10, ph0 + 0.008), (a1 + 13, ph0)],
        "pelvis": [(0, pel0), (5, pel(16), "io"), (a0, pel(-44), "in"), (a1, pel(-48)), (a1 + 5, pel(-14)), (a1 + 10, pel(3)), (a1 + 13, pel0)],
        "shoulders": [(0, sh0), (5, sho(24), "io"), (a0, sho(-70), "in"), (a1, sho(-76)), (a1 + 5, sho(-24)), (a1 + 10, sho(4)), (a1 + 13, sh0)],
        "curl": [(0, 0.0), (5, 12.0, "io"), (a0, -8.0, "in"), (a1 - 1, -18.0), (a1 + 1, -16.0), (a1 + 5, 10.0), (a1 + 10, -1.0), (a1 + 13, 0.0)],   # D-134: crunched in the dip, the back arches up behind the fist
        "trunk": [(0, tr0), (5, lean(20), "io"), (a0, lean(-6), "in"), (a1, lean(-12)), (a1 + 5, lean(9)), (a1 + 10, lean(-1)), (a1 + 13, tr0)],
        "lead_heel": [(0, 0.0), (5, 0.0), (a0, 0.04, "in"), (a1 - 1, 0.11), (a1 + 1, 0.11), (a1 + 4, 0.0)],
        "rear_heel": [(0, 0.012), (5, 0.0), (a0, 0.07, "in"), (a1 - 1, 0.19), (a1 + 1, 0.19), (a1 + 4, 0.02), (a1 + 9, 0.012)],
        "rear_toe": [(0, base["rear_toe"]), (a0, 10.0, "in"), (a1, 8.0), (a1 + 10, base["rear_toe"])],
        "rear_hand_abs": [(0, R), (5, u_low, "io"), (a0, u_hit, "in"), (a1 - 1, u_top),
                          (a1 + 3, (-0.05, hx - 0.14, hz - 0.14)), (a1 + 7, (R[0], R[1] + 0.06, R[2] - 0.07)),
                          (a1 + 11, (R[0], R[1] - 0.01, R[2] + 0.02)), (a1 + 13, R)],
        "rear_elbow": [(0, 0.05), (5, 0.2), (a0, 0.02), (a1 + 1, 0.02), (a1 + 5, 0.25), (a1 + 12, 0.05)],
        "lead_hand_abs": [(0, L), (5, (L[0] - 0.02, L[1] - 0.06, L[2] - 0.08), "io"), (a0 + 2, hik, "io"), (a1 + 3, hik),
                          (a1 + 6, (0.24, 0.26, R[2] + 0.08)), (a1 + 9, (L[0] + 0.03, L[1], L[2] - 0.05)), (a1 + 12, L)],
    }})

    # Leg Sweep (down + kick): he drops deep with the lead hand near the floor
    # for balance and the rear leg swings round low along the ground into the
    # opponent's ankles, then he draws it back and rises.
    a0, a1, T, hx, hz = win(moves["DOWN_KICK"])
    sw_back = (FR[0] * 1.1, FR[1] - 0.10, 0.10, 0.4)
    # D-130: the sweeping leg was 46 deg bent at the hit and cut straight
    # under his own body; the rear hand stood up behind the head and ended
    # inside the torso; he then sat in the crouch and popped up in the last
    # frames (keys at T - 4 are never played with `_recover`). Now the leg
    # swings round the outside (the camera side) on a locked knee, the rear
    # hand stays a guard at the face (placed from the head), and the way back
    # up is keyed inside the reachable time.
    sw_out = (-0.50, hx * 0.42, 0.12, 0.6)                 # half way round, out on the camera side
    sw_hit = (0.02, hx + 0.30, max(hz, 0.11) - 0.02, 0.6)  # beyond reach: the knee locks
    sw_through = (0.26, hx + 0.20, max(hz, 0.11) - 0.02, 0.6)
    deep = ph0 - 0.40
    rh0s = base["rear_hand"]
    out["DOWN_KICK"] = dict(_recover=1.5, **head(a0, a1, T, 6.0), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "hips": [(0, (hips0, 0)), (4, (hips0 + 0.04, 0), "io"), (a0, (hips0 + 0.08, 0)), (a1 + 4, (hips0 + 0.06, 0)), (a1 + 12, (hips0, 0))],
        "pelvis_h": [(0, ph0), (4, deep, "io"), (a1 + 4, deep + 0.02), (a1 + 9, ph0 - 0.10), (a1 + 12, ph0 + 0.008), (a1 + 13, ph0)],
        "pelvis": [(0, pel0), (4, pel(10), "io"), (a0, pel(-40), "in"), (a1, pel(-52)), (a1 + 6, pel(-18)), (a1 + 12, pel0)],
        "shoulders": [(0, sh0), (4, sho(10), "io"), (a0, sho(-24), "in"), (a1, sho(-30)), (a1 + 6, sho(-10)), (a1 + 12, sh0)],
        "trunk": [(0, tr0), (4, lean(22, 6), "io"), (a0, lean(28, 8)), (a1 + 4, lean(24, 6)), (a1 + 9, lean(10, 2)), (a1 + 12, tr0)],
        "lead_heel": [(0, 0.0), (4, 0.05), (a1 + 5, 0.05), (a1 + 10, 0.0)],
        "rear_hinge": [(0, 0.0), (4, 1.0), (a1 + 6, 1.0), (a1 + 10, 0.0)],   # D-130: as on the Front Kick
        "_feet_abs": (0, T - 1),               # the keyed leg all the way (handing back to the stance solver mid-move jumped)
        "rear_foot_abs": [(0, FR + (0.0,)), (2, FR + (0.0,)), (4, sw_back, "io"), (a0 - 1, sw_out), (a0, sw_hit), (a1, sw_through),
                          (a1 + 3, (0.10, 0.52, 0.11, 0.5)), (a1 + 6, (FR[0] * 0.6, 0.16, 0.10, 0.3)), (a1 + 9, (FR[0], FR[1], FR[2] + 0.035, 0.0)),
                          (a1 + 10, FR + (0.0,))],   # D-133: set down onto its own spot (it landed moving, 10 cm in one frame)
        "lead_hand_abs": [(0, L), (2, (0.20, L[1] - 0.02, (L[2] + 0.42) * 0.5 + 0.10)), (5, (0.26, 0.30, 0.42)), (a1 + 4, (0.26, 0.30, 0.42)),
                          (a1 + 9, (L[0], L[1] - 0.04, L[2] - 0.12)), (a1 + 12, L)],
        "rear_hand": [(0, rh0s), (4, (rh0s[0], rh0s[1] + 0.03, rh0s[2] - 0.02)), (a1 + 6, (rh0s[0], rh0s[1] + 0.03, rh0s[2] - 0.02)), (a1 + 12, rh0s)],
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
    # D-135 (critique: "no reach or grab, hands still in stance"): both arms go
    # out long and high to the back of the neck, the trunk leaning in after them
    # D-143 (critique: "no clear hand placement or hold point"): both hands meet
    # on one spot, the back of the neck, 6 cm apart (they were 20 cm apart)
    grab_l = (0.04, 0.74, hz + 0.30)
    grab_r = (-0.02, 0.72, hz + 0.29)
    # D-130: the knee came up only to the waist, the head was not pulled down
    # onto it, the foot dropped 38 cm in one frame, the "push" was a pose next
    # to the guard, and the last twelve frames stood still. Now: the hands
    # pull down to the rising knee as the trunk crunches over it, the knee
    # drives up to the chest, the foot is set down over four frames, he
    # shoves off the planted rear foot with both arms long, and comes home
    # part by part.
    pull_l = (0.10, 0.44, hz - 0.12)
    pull_r = (-0.06, 0.42, hz - 0.14)
    shove_l = (0.08, hx - 0.08, hz + 0.04)            # a short push as the hands let go: not a second strike (D-103: "a hit and a knee after, why")
    shove_r = (-0.08, hx - 0.10, hz - 0.02)
    kn = a1 + 6                                            # the knee lands
    sh = kn + 8                                            # the hands let go with a push, once the foot is down
    knee_up = (FR[0] * 0.3, 0.33, 0.74, 0.5)
    # no recovery warp: the knee is keyed after the grab's active frames and
    # must play on exactly the frame the throw lands (throw_release_frame)
    out["THROW"] = dict(**{**head(a0, a1, T, 8.0), **{
        "chin": [(0, chin0), (a0, chin0 + 8, "in"), (kn, chin0 + 14), (sh, chin0 + 4), (sh + 8, chin0)],
        "lead_palm": [(0, base["lead_palm"]), (a0, (0.0, 0.4, -1.0), "in"), (kn + 2, (0.0, 0.4, -1.0)), (sh + 9, base["lead_palm"])],
        "rear_palm": [(0, (0.0, 0.0, 1.0)), (a0, (0.0, 0.4, -1.0), "in"), (kn + 2, (0.0, 0.4, -1.0)), (sh + 9, (0.0, 0.0, 1.0))],
        "hips": [(0, (hips0, 0)), (a0, (hips0 + 0.10, 0), "in"), (kn - 3, (hips0 + 0.02, 0)), (kn, (hips0 + 0.12, 0), "in"),
                 (kn + 2, (hips0 + 0.11, 0)), (sh - 2, (hips0 + 0.02, 0)), (sh, (hips0 + 0.12, 0)), (sh + 3, (hips0 + 0.11, 0)), (sh + 8, (hips0 - 0.02, 0)), (sh + 12, (hips0, 0))],
        "pelvis_h": [(0, ph0), (a0, low(0.04), "in"), (kn - 3, low(0.05)), (kn, ph0 + 0.05, "in"), (kn + 2, ph0 + 0.045), (sh - 2, low(0.06)), (sh, low(0.05)),
                     (sh + 3, low(0.05)), (sh + 8, ph0 + 0.008), (sh + 12, ph0)],
        "pelvis": [(0, pel0), (a0, pel(-10), "in"), (kn, pel(-40), "in"), (sh - 2, pel(-6)), (sh, pel(-22)), (sh + 3, pel(-20)), (sh + 8, pel(4)),
                   (sh + 12, pel0)],
        "shoulders": [(0, sh0), (a0, sho(-30), "in"), (kn, sho(-40)), (sh - 2, sho(-16)), (sh, sho(-36)), (sh + 3, sho(-32)), (sh + 9, sho(5)),
                      (sh + 12, sh0)],
        "trunk": [(0, tr0), (a0, lean(16), "in"), (kn, lean(24), "in"), (kn + 2, lean(22)), (sh - 2, lean(4)), (sh, lean(10)), (sh + 3, lean(8)), (sh + 9, lean(-2)),
                  (sh + 12, tr0)],
        "lead_heel": [(0, 0.0), (kn - 2, 0.0), (kn, 0.06, "in"), (kn + 2, 0.05), (kn + 6, 0.0)],
        "rear_heel": [(0, 0.012), (a0, 0.04), (sh, 0.09, "in"), (sh + 3, 0.09), (sh + 8, 0.012)],
        "rear_hinge": [(0, 0.0), (kn - 5, 0.0), (kn - 2, 1.0), (kn + 5, 1.0), (kn + 8, 0.0)],   # D-130
        "rear_toe": [(0, base["rear_toe"]), (kn - 4, base["rear_toe"]), (kn - 1, 0.0), (kn + 4, 0.0), (kn + 8, base["rear_toe"])],
        "_feet_abs": (0, T - 1),
        "rear_foot_abs": [(0, FR + (0.0,)), (kn - 5, FR + (0.0,)), (kn - 3, (FR[0] * 0.7, 0.02, 0.26, 0.2), "io"), (kn - 1, (FR[0] * 0.45, 0.20, 0.56, 0.4)), (kn, knee_up),
                          (kn + 2, (knee_up[0], knee_up[1] - 0.02, knee_up[2] - 0.03, 0.5)), (kn + 4, (FR[0] * 0.5, 0.18, 0.50, 0.3)), (kn + 6, (FR[0] * 0.78, 0.02, 0.26, 0.1)),
                          (kn + 7, (FR[0] * 0.95, FR[1] * 0.85, FR[2] + 0.07, 0.0)), (kn + 8, FR + (0.0,))],
        "lead_hand_abs": [(0, L), (a0, grab_l, "in"), (a1 + 1, grab_l), (kn - 1, (pull_l[0], pull_l[1] + 0.04, pull_l[2] + 0.10)), (kn, pull_l), (kn + 2, pull_l),
                          (sh - 2, (0.12, 0.36, hz + 0.02)), (sh, shove_l), (sh + 3, (shove_l[0], shove_l[1] - 0.04, shove_l[2] + 0.02)), (sh + 8, (L[0], L[1] + 0.05, L[2] - 0.04)), (sh + 12, L)],
        "rear_hand_abs": [(0, R), (a0, grab_r, "in"), (a1 + 1, grab_r), (kn - 1, (pull_r[0], pull_r[1] + 0.04, pull_r[2] + 0.10)), (kn, pull_r), (kn + 2, pull_r),
                          (sh - 2, (-0.10, 0.32, hz - 0.02)), (sh, shove_r), (sh + 3, (shove_r[0], shove_r[1] - 0.04, shove_r[2] + 0.02)), (sh + 8, (R[0], R[1] + 0.06, R[2] - 0.04)), (sh + 12, R)],
        "lead_elbow": [(0, 0.2), (a0, 0.5), (kn, 0.45), (sh, 0.08), (sh + 3, 0.08), (sh + 10, 0.2)],
        "rear_elbow": [(0, 0.05), (a0, 0.5), (kn, 0.45), (sh, 0.08), (sh + 3, 0.08), (sh + 10, 0.05)],
    }})

    # Rift Break: an axe kick with one step in (history and the current design below).
    a0, a1, T, hx, hz = win(moves["FORWARD_SPECIAL"])
    mvf = moves["FORWARD_SPECIAL"]
    m0, m1 = mvf.get("move_start", 4) - 1, mvf.get("move_end", 16) - 1      # animation frames the game moves him on
    v = mvf.get("move_distance", 1.4) / float(m1 - m0 + 1)

    def travel(k):
        return v * min(max(0, k - m0 + 1), m1 - m0 + 1)

    # History of this move, shortest form: D-115 a skip axe kick (hop); D-120 to a
    # taekwondo picture (knee up first); D-121/D-122 the leg nearer the camera (his
    # right, rear leg), locked straight; D-125 the rise re-spaced; D-126 to the owner's
    # written sequence (no chamber, straight leg up and down, heel first, driven to the
    # floor); D-127 the hop replaced by one step in.
    #
    # D-127 (owner chose a step forward over the hop or kicking on the spot): the lead
    # foot steps in while the rear foot pushes on the floor, lands, and the body rolls
    # forward over it as the rear leg swings up; the supporting foot is planted from the
    # landing to the end of the move. Every planted frame moves the foot back in model
    # space exactly as far as the game moves him (travel()), so it holds still on the
    # floor. One step cannot cover the old 1.4 m: with the rear foot still down when the
    # lead foot lands, the feet are (travel + stance length) apart, so the travel is
    # 0.7 m now (kairo_rift_break.tres, frames 4-18): a balance change.
    lf_x, lf_f, lf_h = FL
    fr_x, fr_f, fr_h = FR
    step_k = m0 + 3                                          # the lead foot lands (key frame): a quick step, the frames belong to the kick
    f_end = -0.08                                            # the supporting foot ends just behind the hips: he is driving forward
    w_land = f_end + travel(m1)                              # world spot of the landing (model forward + travel)
    lead_abs = [(0, FL + (0.0,)), (m0 - 1, FL + (0.0,)),
                (m0 + 1, (lf_x, lf_f + 0.05, lf_h + 0.06, 0.2), "out"),
                (step_k - 1, (lf_x, w_land - travel(step_k) - 0.03, lf_h + 0.06, -0.2)),
                (step_k, (lf_x, w_land - travel(step_k), lf_h, 0.0), "in")]
    for k in range(step_k + 1, m1 + 1):                      # planted while the body rolls over it
        lead_abs.append((k, (lf_x, w_land - travel(k), lf_h, 0.0)))
    # D-128: up on the ball of the supporting foot at the peak, the heel drops with the
    # chop. Recovery as the owner wrote it ("retract the leg, lower it naturally and
    # recover"): the kicking leg is drawn back and set down behind him, never planted in
    # front, and then the supporting foot takes ONE step forward into the stance. (It
    # used to plant in front and swap both feet, which left them side by side.)
    # Recovery keys must stay below about a1 + 16: `_recover` plays them slower, later
    # ones are never reached.
    lead_abs += [(a0 - 3, (lf_x, f_end, lf_h, 0.0)),        # D-129: flat on the floor throughout (it rose onto the ball in D-128)
                 (a1 + 10, (lf_x, f_end, lf_h, 0.0)),
                 (a1 + 12, (lf_x, (f_end + lf_f) * 0.5 + 0.02, lf_h + 0.06, 0.2)), (a1 + 15, FL + (0.0,), "in")]
    lh0, rh0 = base["lead_hand"], base["rear_hand"]          # the guard, placed from the head: it rides with the leaning trunk
    hip_z = head_z - 0.60
    arc_r = 1.25                                             # beyond the leg: the knee locks

    def arc(deg, x=FR[0] * 0.6, pt=0.7):
        a = math.radians(deg)
        return (x, arc_r * math.cos(a), hip_z + arc_r * math.sin(a), pt)

    # D-129, to the owner's axe-kick specification (docs/images/references/
    # kairo_rift_break_axe_kick_spec.md), which replaces the D-126 straight-leg swing:
    #   prepare  the foot pushes off through the step and leaves the floor, the KNEE
    #            comes forward and up, the leg bending (a chamber);
    #   lift     the thigh keeps rising toward vertical while the knee extends
    #            progressively; never a rigid straight-leg swing;
    #   peak     near vertical above the head, knee mostly extended (about 10 degrees,
    #            not locked), three frames that keep moving;
    #   strike   down in the fore-aft plane, the knee flexing a little as it starts
    #            and extending into the hit, speeding up;
    #   impact   the heel slows through the active frames into a short impact pose and
    #            rebounds a few degrees;
    #   recover  the leg is drawn back with the knee bending and set down in the stance.
    # The leg is keyed as a DIRECTION (arc(): a target beyond reach at that angle from
    # the hip) plus an EXTENSION (`rear_reach`: how far the leg may open), so the knee
    # bend is set directly: 0.56 ~112 degrees, 0.82 ~70, 0.95 ~36, 0.985 ~20, 0.996 ~10.
    kick = [(0, FR + (0.0,)), (m0 - 1, FR + (0.0,))]
    for k in range(m0, step_k + 1):
        u = (k - m0 + 1) / float(step_k - m0 + 1)
        kick.append((k, (fr_x, fr_f - travel(k), fr_h + 0.05 * u, 0.5 * u)))
    back = fr_f - travel(step_k)
    kick += [(step_k + 1, (fr_x * 0.9, back + 0.10, fr_h + 0.08, 0.4)),
             (step_k + 2, (fr_x * 0.75, back + 0.26, fr_h + 0.13, 0.3)),      # two plain keys carry the foot forward clear of the floor
             (step_k + 3, (fr_x * 0.6, 0.10, fr_h + 0.21, 0.3)), (step_k + 4, arc(-54, pt=0.35)),
             (step_k + 5, arc(-22, pt=0.1)), (step_k + 7, arc(22, pt=-0.6)), (step_k + 9, arc(54, x=FR[0] * 0.7, pt=-0.6)),
             (step_k + 10, arc(70, x=FR[0] * 0.8, pt=-0.65)),
             # peak: near vertical, then the heel is carried forward over the target while
             # the leg is still high, so the strike itself goes down more than forward
             (a0 - 4, arc(84, x=FR[0] * 0.9, pt=-0.65)), (a0 - 3, arc(80, x=FR[0] * 0.9, pt=-0.7)),
             (a0 - 2, arc(72, x=FR[0] * 0.85, pt=-0.75)),
             (a0 - 1, arc(54, x=FR[0] * 0.75, pt=-0.85)), (a0, arc(26, pt=-0.9)),
             (a0 + 1, arc(11, pt=-0.9)), (a0 + 2, arc(1, pt=-0.9)), (a1, arc(-5, pt=-0.9)),
             (a1 + 1, arc(-3, pt=-0.8)),                      # rebound off the hit
             (a1 + 3, (FR[0] * 0.7, 0.72, FR[2] + 0.20, -0.4)),     # the leg comes down and back, the knee bending as it goes
             (a1 + 4, (FR[0] * 0.7, 0.62, FR[2] + 0.18, -0.2)), (a1 + 5, (FR[0] * 0.75, 0.46, FR[2] + 0.17, 0.0)),
             (a1 + 8, (FR[0] * 0.85, 0.02, FR[2] + 0.10, 0.2)), (a1 + 10, FR + (0.0,))]
    kick_reach = [(0, 0.9995), (step_k + 3, 0.9995), (step_k + 4, 0.63),
                  (step_k + 5, 0.56), (step_k + 7, 0.68), (step_k + 9, 0.84), (step_k + 10, 0.93), (a0 - 4, 0.98),
                  (a0 - 3, 0.996), (a0 - 2, 0.996), (a0 - 1, 0.975), (a0, 0.997), (a1, 0.997), (a1 + 1, 0.992),
                  (a1 + 2, 0.975), (a1 + 3, 0.94), (a1 + 6, 0.94), (a1 + 9, 0.9995)]
    out["FORWARD_SPECIAL"] = dict(_recover=1.5, _hold=1, _impact=0.0,    # the heel drives on down to the floor: no hold at hip height
                                  _lag=(("foot", 0.0), ("heel", 0.0), ("toe", 0.0), ("hips", 0.0), ("pelvis", 0.0), ("trunk", 1.0),
                                        ("shoulders", 1.5), ("hand", 1.0), ("elbow", 1.0), ("palm", 1.0), ("chin", 3.0), ("neck", 3.0)), **{
        "lead_palm": "auto", "rear_palm": "auto",
        "chin": [(0, chin0), (m0 - 1, chin0 + 3), (a0 - 2, chin0 + 2), (a1, chin0 + 10), (a1 + 3, chin0 + 10), (a1 + 12, chin0)],
        "hips": [(0, (hips0, 0)), (step_k, (hips0 + 0.03, 0)), (a0 - 2, (hips0 - 0.02, 0)), (a0, (hips0 + 0.005, 0)),
                 (a1, (hips0 + 0.035, 0)), (a1 + 5, (hips0 + 0.01, 0)), (a1 + 10, (hips0 - 0.10, 0)),      # back over the feet while they are close
                 (a1 + 15, (hips0, 0), "out")],
        # D-128 (the upper body was too quiet and he stayed sunk): he sinks into the step,
        # rises as the leg swings through and stands tall on the supporting leg at the
        # peak, then the whole body comes down with the chop: hips drop, chest drives
        # forward, both fists pull down; the weight lands on the front foot
        "pelvis_h": [(0, ph0), (m0 - 1, low(0.015), "io"), (step_k, low(0.05)), (step_k + 3, ph0 + 0.02),
                     (a0 - 2, ph0 + 0.07), (a0 - 1, ph0 + 0.05), (a0, ph0 + 0.005), (a1, low(0.06)), (a1 + 3, low(0.065)), (a1 + 8, low(0.02)),
                     (a1 + 10, low(0.03)), (a1 + 13, low(0.045)), (a1 + 16, ph0, "out")],
        "pelvis": [(0, pel0), (m0, pel(-4)), (step_k, pel(-10)), (a0 - 2, pel(-18)), (a1, pel(-24)),
                   (a1 + 11, pel0, "out")],
        "shoulders": [(0, sh0), (m0, sho(2)), (step_k, sho(-5)), (a0 - 2, sho(-10)), (a1, sho(-18)),
                      (a1 + 11, sh0, "out")],
        "trunk": [(0, tr0), (m0 - 1, lean(2)), (step_k, lean(5)), (a0 - 5, lean(-8)), (a0 - 3, lean(-11)), (a0 - 2, lean(-10)), (a0 - 1, lean(-6)), (a0, lean(-1)),      # the body follows the heel: it finishes its drive on the active frames
                  (a1, lean(10)), (a1 + 1, lean(8)), (a1 + 3, lean(9)), (a1 + 8, lean(5), "out"), (a1 + 13, tr0)],
        "hips_x": [(0, 0.0), (step_k + 3, 0.03), (a0 - 4, 0.07), (a1 + 2, 0.07), (a1 + 10, 0.0)],   # D-134: pelvis sideways over the standing foot (it sat 7 cm off it)
        "lead_foot_abs": lead_abs,
        "rear_foot_abs": kick,
        "rear_reach": kick_reach,
        "rear_hinge": 1.0,
        # the stance's turn-out leaves the leg as it lifts: the knee comes straight forward, not out to the side
        "rear_toe": [(0, base["rear_toe"]), (step_k, base["rear_toe"]), (step_k + 3, 0.0), (a1 + 8, 0.0), (a1 + 10, base["rear_toe"])],
        # the guard stays up and compact, but it lives: the kicking side's fist sinks a
        # little as the leg rises, and both fists drive down with the heel
        "lead_hand": [(0, lh0), (step_k + 4, (lh0[0] + 0.02, lh0[1] + 0.03, lh0[2] - 0.05)), (a0 - 3, (lh0[0] + 0.04, lh0[1] - 0.01, lh0[2] - 0.01)),
                      (a0 - 2, (lh0[0] + 0.03, lh0[1] - 0.03, lh0[2] + 0.01)), (a0, (lh0[0], lh0[1] - 0.08, lh0[2] - 0.05)),
                      (a1, (lh0[0], lh0[1] - 0.13, lh0[2] - 0.10)), (a1 + 1, (lh0[0], lh0[1] - 0.12, lh0[2] - 0.07)), (a1 + 4, (lh0[0], lh0[1] - 0.12, lh0[2] - 0.08)),
                      (a1 + 11, (lh0[0], lh0[1] - 0.03, lh0[2] - 0.02), "out"), (a1 + 16, lh0)],
        "lead_elbow": [(0, 0.2), (a0, 0.4), (a1 + 4, 0.4), (a1 + 12, 0.2)],
        "rear_hand": [(0, rh0), (step_k + 5, (rh0[0], rh0[1] - 0.01, rh0[2] - 0.04)), (a0 - 2, (rh0[0], rh0[1] - 0.02, rh0[2] - 0.10)),
                      (a0, (rh0[0], rh0[1] + 0.04, rh0[2] - 0.24)), (a1, (rh0[0], rh0[1] + 0.06, rh0[2] - 0.28)), (a1 + 1, (rh0[0], rh0[1] + 0.05, rh0[2] - 0.24)),   # D-132: the kicking side's fist drops with the leg (the hands sat level, 2 cm apart)
                      (a1 + 4, (rh0[0], rh0[1] + 0.04, rh0[2] - 0.22)), (a1 + 11, (rh0[0], rh0[1], rh0[2] - 0.03), "out"), (a1 + 16, rh0)],
    })

    # Rift Guard (the counter stance): he sits back onto the rear leg and the
    # open lead hand sweeps across the centre line; the rear fist stays loaded
    mv = moves["BACK_SPECIAL"]
    c0, c1 = mv["counter"]
    T = mv["startup"] + mv["active"] - 1 + mv["recovery"]
    lh0 = base["lead_hand"]
    # D-107 (owner: "his fighting needs improvement"): the guard read as standing
    # still; he now sits clearly back, sinks and slips his head off the line
    # D-130: the stance stood dead still for twelve frames. The open hand now
    # circles across the centre line and back, and the body breathes with it.
    cm = (c0 + c1) // 2
    # D-138 (owner: "he jumps from his normal stance to the counter stance in a single
    # frame"): every channel now eases in over six frames (to c0 + 2, in-out)
    out["BACK_SPECIAL"] = {
        "rear_palm": "auto",
        "lead_palm": [(0, base["lead_palm"]), (c0 + 4, (-0.9, -0.4, 0.0), "io"), (c1, (-0.9, -0.4, 0.0)), (T - 3, base["lead_palm"])],
        # D-135 (critique: "looks almost the same as the stance"): twice as far back and
        # down, chest turned away, the open hand held well out in front at face height
        "hips": [(0, (hips0, 0)), (c0 + 4, (hips0 - 0.20, 0), "io"), (c1, (hips0 - 0.19, 0)), (T - 3, (hips0, 0))],
        "pelvis_h": [(0, ph0), (c0 + 4, low(0.14), "io"), (cm, low(0.12)), (c1, low(0.145))] + settle(T, T - 6, ph0),
        "trunk": [(0, tr0), (c0 + 4, lean(-12, 8), "io"), (cm, lean(-15, 4)), (c1, lean(-11, 9)), (T - 3, tr0)],
        "pelvis": [(0, pel0), (c0 + 4, pel(18), "io"), (c1, pel(18)), (T - 3, pel0)],
        "shoulders": [(0, sh0), (c0 + 4, sho(30), "io"), (cm, sho(22)), (c1, sho(32)), (T - 3, sh0)],
        "chin": [(0, chin0), (c0 + 4, chin0 + 8, "io"), (c1, chin0 + 8), (T - 3, chin0)],
        "lead_heel": [(0, 0.0), (c0 + 4, 0.05, "io"), (c1, 0.05), (T - 3, 0.0)],
        "lead_hand": [(0, lh0), (2, (lh0[0] + 0.10, lh0[1] - 0.06, lh0[2] + 0.02)), (c0 + 4, (-0.02, 0.48, -0.06), "io"),
                      (cm, (0.08, 0.50, 0.0)), (c1, (-0.03, 0.46, -0.08)), (T - 3, lh0)],
        "lead_elbow": [(0, 0.2), (c0 + 4, 0.3), (c1, 0.3), (T - 3, 0.2)],
        # D-131: both hands sat on one level in front of the face (1 cm apart in height); the rear fist is now drawn down to the ribs, loaded
        "rear_hand": [(0, base["rear_hand"]), (c0 + 4, (base["rear_hand"][0] - 0.02, base["rear_hand"][1] - 0.07, base["rear_hand"][2] - 0.20), "io"),
                      (c1, (base["rear_hand"][0] - 0.02, base["rear_hand"][1] - 0.06, base["rear_hand"][2] - 0.22)), (T - 3, base["rear_hand"])],
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
    # D-139 (owner: "after the final strike he pops straight into the next pose;
    # add a 10-15 frame recovery"): the finishing pose is held 4 frames (was 8)
    # and the way home takes the rest (about 14): the arm comes down in front,
    # the feet settle, the guard comes back up.
    out["ULTIMATE"] = {
        "lead_palm": "auto", "rear_palm": "auto",
        "chin": [(0, chin0), (3, chin0 + 10), (a0, chin0 + 6, "in"), (b1, chin0 + 12, "in"), (b2, chin0 + 3), (b3 - 2, chin0 + 10),
                 (b3 + 1, chin0 - 6, "out"), (b3 + 4, chin0 - 5), (T - 4, chin0)],
        "hips": [(0, (hips0, 0)), (3, (hips0 - 0.05, 0), "io"), (a0, (hips0 + 0.09, 0), "in"), (b1, (hips0 + 0.12, 0), "io"),
                 (b2, (hips0 + 0.04, 0), "io"), (b3 - 2, (hips0 + 0.08, 0), "io"), (b3, (hips0 + 0.15, 0), "in"),
                 (b3 + 4, (hips0 + 0.14, 0)), (T - 4, (hips0, 0), "io")],
        "lead_foot": [(0, lf0), (a0 - 1, (lf0[0], lf0[1] + adv), "in"), (b2 + 4, (lf0[0], lf0[1] + adv)),
                      (b3 - 1, (lf0[0], lf0[1] + adv + 0.12), "in"), (b3 + 4, (lf0[0], lf0[1] + adv + 0.12)), (T - 4, lf0, "io")],
        "lead_heel": [(0, 0.0), (b2 - 4, 0.0), (b2, 0.05, "in"), (b2 + 4, 0.0), (b3 - 2, 0.0), (b3, 0.06, "in"), (b3 + 4, 0.055), (T - 5, 0.0)],
        "pelvis_h": [(0, ph0), (3, low(0.06), "io"), (a0, low(0.03), "in"), (b1 - 2, low(0.10), "io"), (b1, low(0.11)),
                     (b2 - 3, ph0 + 0.02, "out"), (b2, ph0 + 0.04), (b2 + 6, low(0.02), "io"),
                     (b3 - 3, low(0.12), "io"), (b3, ph0 + 0.035, "out"), (b3 + 3, ph0 + 0.06), (b3 + 4, ph0 + 0.075)] + settle(T, T - 7, ph0, 0.02),
        "pelvis": [(0, pel0), (3, pel(14), "io"), (a0, pel(8), "in"), (b1 - 3, pel(22), "io"), (b1, pel(28), "in"),
                   (b2 - 3, pel(-30), "io"), (b2, pel(-68), "in"), (b2 + 3, pel(-64)), (b3 - 3, pel(18), "io"),
                   (b3, pel(-46), "in"), (b3 + 4, pel(-44)), (T - 4, pel0, "io")],
        "shoulders": [(0, sh0), (3, sho(22), "io"), (a0, sho(16), "in"), (b1 - 3, sho(-10), "io"), (b1, sho(34), "in"), (b1 + 3, sho(30)),
                      (b2 - 2, sho(-20), "io"), (b2, sho(-40), "in"), (b2 + 3, sho(-36)), (b3 - 3, sho(28), "io"),
                      (b3, sho(-72), "in"), (b3 + 4, sho(-68)), (T - 4, sh0, "io")],
        "trunk": [(0, tr0), (3, lean(6), "io"), (a0, lean(5)), (b1 - 2, lean(12), "io"), (b1, lean(14, -4)), (b2 - 3, lean(0), "io"),
                  (b2, lean(-20, 12), "in"), (b2 + 3, lean(-19, 11)), (b3 - 2, lean(14), "io"), (b3, lean(-7), "in"),
                  (b3 + 4, lean(-13)), (T - 4, tr0, "io")],
        "curl": [(0, 0.0), (3, -5.0), (a0, 6.0, "in"), (b1 - 3, -4.0), (b1, 14.0, "in"), (b2 - 3, 2.0), (b2, 8.0), (b3 - 3, 14.0, "io"), (b3, -8.0, "in"),
                 (b3 + 3, -18.0), (b3 + 4, -20.0), (T - 4, 0.0, "io")],   # D-134: the back works through all four blows; it arches up behind the last uppercut
        "hips_x": [(0, 0.0), (b2 - 4, 0.0), (b2, 0.06, "in"), (b2 + 3, 0.06), (b2 + 8, 0.0)],
        "rear_heel": [(0, 0.012), (a0, 0.04), (b1, 0.06, "in"), (b1 + 3, 0.04), (b3 - 3, 0.03), (b3, 0.08, "io"), (b3 + 3, 0.11), (b3 + 4, 0.10), (T - 4, 0.012)],
        "rear_toe": [(0, base["rear_toe"]), (b1, 20.0, "in"), (b1 + 4, 24.0), (b3 - 4, 20.0), (b3, 8.0, "io"), (b3 + 4, 8.0), (T - 4, base["rear_toe"])],
        "lead_toe": [(0, base["lead_toe"]), (b2 - 4, base["lead_toe"]), (b2, base["lead_toe"] + 60, "in"), (b2 + 3, base["lead_toe"] + 60),
                     (b2 + 7, base["lead_toe"])],
        "rear_hinge": [(0, 0.0), (b2 - 9, 0.0), (b2 - 5, 1.0), (b2 + 5, 1.0), (b2 + 9, 0.0)],   # D-130: the roundhouse chamber bent the mesh knee backwards (-128 deg)
        "_feet_abs": (b2 - 9, b2 + 9),
        "rear_foot_abs": [(b2 - 9, FR + (0.0,)), (b2 - 5, rk_lift, "io"), (b2 - 3, rk_ch), (b2 - 1, rk_mid), (b2, rk), (b2 + 2, rk),
                          (b2 + 3, (-0.08, hx * 0.66, hz - 0.06, 0.7)), (b2 + 5, rk_back), (b2 + 7, (FR[0] * 0.9, FR[1] - 0.04, 0.22, 0.1)), (b2 + 9, FR + (0.0,), "in")],
        "lead_hand_abs": [(0, L), (3, (L[0] + 0.02, L[1] - 0.10, L[2] - 0.03), "io"), (a0, (jab[0], jab[1] + 0.035, jab[2]), "in"),
                          (a0 + 1, jab), (a0 + 3, jab), (b1 - 3, (0.24, 0.10, R[2] - 0.04), "out"),
                          (b1, (body[0], body[1] + 0.03, body[2]), "in"), (b1 + 1, body), (b1 + 3, body),
                          (b2 - 3, chin, "out"), (b2 + 4, chin), (b3, hik, "in"), (b3 + 4, hik), (T - 3, L, "io")],
        "lead_elbow": [(0, 0.2), (a0, 0.05), (b1 - 3, 0.5), (b1, 0.85, "in"), (b1 + 3, 0.8), (b2, 0.2), (T - 3, 0.2)],
        "rear_hand_abs": [(0, R), (3, (R[0] - 0.03, R[1] - 0.04, R[2] + 0.02)), (b2 - 3, (R[0] + 0.02, R[1] + 0.04, R[2] + 0.04)),
                          (b2, (-0.30, -0.06, R[2] - 0.12), "in"), (b2 + 3, (-0.28, -0.04, R[2] - 0.10)),
                          (b3 - 3, upper_low, "io"), (b3, upper, "in"), (b3 + 2, (0.0, hx - 0.30, hz + 0.40)), (b3 + 4, (0.0, hx - 0.33, hz + 0.47)),
                          (b3 + 9, (R[0] - 0.02, R[1] + 0.08, R[2] - 0.04), "io"),   # D-139: the arm comes down in front of him before the guard   # D-130: the finishing uppercut goes on up past the head and keeps rising through the hold (it stood still for seven frames at chin height)
                          (T - 3, R, "io")],
        "rear_elbow": [(0, 0.1), (b2, 0.3), (b3 - 3, 0.15), (b3, 0.02), (b3 + 4, 0.02), (T - 3, 0.1)],
    }

    # One-Two Cross (D-113): the second hit of the jab string. The same cross
    # as the Heavy Punch (hip, then chest, then fist, the jab hand pulled back
    # to the ribs) on the string's faster timing: every key is moved so the
    # wind-up, the active frames and the recovery each scale on their own.
    if "string_cross" in moves and "HEAVY" in out:
        h0, h1, hT = win(moves["HEAVY"])[:3]
        n0, n1, nT = win(moves["string_cross"])[:3]

        def remap(t):
            if h0 - 3 <= t <= h0:                          # the last frames into the hit keep their spacing
                return n0 - (h0 - t)
            if t < h0 - 3:
                return round(t * (n0 - 3) / max(1, h0 - 3))
            if t <= h1:
                return n0 + round((t - h0) * (n1 - n0) / max(1, h1 - h0))
            return n1 + round((t - h1) * (nT - n1) / max(1, hT - h1))

        sc = {}
        for ch, tr in out["HEAVY"].items():
            if isinstance(tr, list) and tr and isinstance(tr[0], tuple) and isinstance(tr[0][0], int):
                keyed, seen = [], set()
                for k in tr:
                    t2 = min(nT - 1, remap(k[0]))
                    if t2 in seen:
                        continue
                    seen.add(t2)
                    keyed.append((t2,) + tuple(k[1:]))
                sc[ch] = keyed
            else:
                sc[ch] = tr
        out["string_cross"] = sc
    return out


# frames after the contact -> how far the body is carried on (+) or thrown back (-); see `_impact`
IMPACT_WAVE = {1: 1.0, 2: 0.6, 3: -0.35, 4: -0.6, 5: -0.3, 6: 0.1}


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

    def mirrored(c):
        """The capture mirrored left for right (D-117: a right-leg recorded kick
        thrown with Kairo's left leg). Joint names swap sides, X flips."""
        import copy as _copy
        import re as _re
        m = _copy.copy(c)

        def swap(k):
            if "Left" in k:
                return k.replace("Left", "Right")
            if "Right" in k:
                return k.replace("Right", "Left")
            if _re.match(r"^L[A-Z]", k):
                return "R" + k[1:]
            if _re.match(r"^R[A-Z]", k):
                return "L" + k[1:]
            return k
        m.P = {swap(k): v * np.array([-1.0, 1.0, 1.0]) for k, v in c.P.items()}
        return m
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
    i0, n_idle = st["frame"], int(st.get("loop", 60))     # D-137: a style may breathe over a longer loop (Kairo: 2 s)
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
    mean = {k: np.mean([r[k] for r in raw[:60]], 0) for k in raw[0]}     # D-137: the first second, as before the 2 s loop (the guard every move starts from stays put)
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
        mix = {k: mean[k] + (r[k] - mean[k]) * amp for k in r}
        P = shape(mix)
        if fitted:                                   # limbs solved on the fighter's own skeleton (D-075)
            life = st.get("life")
            if life:
                # The guard is alive (D-090): with every breath the chest turns a
                # little, the hands float and follow late, the chin moves. All
                # periodic over the loop; the feet stay on their marks.
                ps, ph = dict(st["pose"]), 2 * math.pi * u
                a = float(life)
                # D-137: every wave starts at zero on frame 0, so the first frame of the
                # loop IS the stance the moves start from (no seam into an attack)
                def sn(off, ph=ph):
                    return math.sin(ph - off) - math.sin(-off)
                lh, rh = ps["lead_hand"], ps["rear_hand"]
                ps["lead_hand"] = (lh[0], lh[1] + 0.012 * a * sn(1.3), lh[2] + 0.016 * a * sn(1.0))
                ps["rear_hand"] = (rh[0], rh[1] + 0.006 * a * sn(0.9), rh[2] + 0.009 * a * sn(0.7))
                ps["shoulders"] = ps.get("shoulders", 0.0) + 2.2 * a * sn(0.5)
                ps["pelvis"] = ps.get("pelvis", 0.0) + 0.8 * a * sn(0.0)
                tr = ps.get("trunk", (0.0, 0.0))
                ps["trunk"] = (tr[0] + 1.3 * a * sn(0.3), tr[1] + 0.6 * a * sn(-0.8))
                ps["chin"] = ps.get("chin", 0.0) + 1.2 * a * sn(1.6)
                if st.get("weight_shift"):
                    # D-136 (owner: "it barely moves ... add breathing and a weight shift"):
                    # the hips rock forward onto the lead foot and back once per loop, and
                    # rise and settle with the breath; the feet stay where they are
                    ws = float(st["weight_shift"])
                    hp = ps.get("hips", (0.0, 0.0))
                    ps["hips"] = (hp[0] + ws * sn(0.0), hp[1])
                    ps["hips_x"] = ps.get("hips_x", 0.0) + 1.0 * ws * sn(-1.2)      # and from side to side (D-143: 3.5 cm, was 1.4; the knee bob is halved)
                    ps["pelvis_h"] = ps.get("pelvis_h", 0.93) + 0.9 * ws * (math.cos(ph) - 1.0)      # D-138/139: a deeper breath (0.45, 0.7)
                    ps["curl"] = ps.get("curl", 0.0) + 6.0 * sn(0.4)      # D-139: the chest rises and falls more (was 4)
                    # D-139 (owner: "bounce on the balls of his feet"): both heels come up
                    # at the top of each knee bounce and down as he sinks; the balls stay put
                    hb = 0.014 * (0.5 + 0.5 * math.cos(2 * math.pi * u * st.get("bob_beats", 1)))
                    ps["lead_heel"] = ps.get("lead_heel", 0.0) + hb
                    ps["rear_heel"] = ps.get("rear_heel", 0.0) + hb
                if st.get("heel_bounce"):
                    # D-100: up on the ball of the rear foot at the top of the bounce
                    # (the bob is highest at u = 0), heel down as he sinks
                    ps["rear_heel"] = ps.get("rear_heel", 0.0) + st["heel_bounce"] * 0.5 * (1 + math.cos(ph))
                if mod is not None:
                    mod(ps, u)
                # D-137: the chest, pelvis, trunk, chin and curl channels are applied
                # by the shaping pass, which used to read the fixed stance: only the
                # hands and the hips' height ever moved (measured: chest and pelvis
                # turned 0 deg over the loop). Shape again from the living channels.
                P = shape_stance(mix, dict(st, pose=ps), H)
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
               aim=None, lift=None, foot_last=False, stand=None, hop=None, air_h=None, guide_lead=4):
        """foot_last: aim the kicking foot onto the hitbox once more after the
        feet are re-planted (as the fist is; the recorded karate kicks, D-095).
        aim: horizontal direction of the capture that must point at the
        opponent (kicks thrown sideways from the hips); lift(t): metres the
        whole body is raised on frame t (jumps; those frames are not grounded).
        D-117 (recorded kicks on moves that travel or fly):
        stand(t) -> (side, (x, fwd, height)) or None: that foot is put there
        (model space, fwd = toward the opponent) after the feet are planted, so
        a planted foot can hold still on the floor while the game carries the
        fighter; hop(t): metres the body is raised on frame t after grounding,
        keeping the planted-foot logic (a skip); air_h(t): the hips height on
        an airborne frame (not grounded at all; the jump attacks)."""
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
                # guide_lead: frames before the first active frame the limb starts
                # being pulled onto the hitbox (an axe kick keeps its top: 1)
                g0 = a0 - min(a0, guide_lead)
                w = ease(max(0.0, (t - g0) / max(1.0, mid - g0)))
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
            if fitted and not lift and not air_h:
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
            if stand:
                sp = stand(t)
                if sp is not None:
                    sd2, (sx, sf, sz) = sp
                    P = move_foot(P, sd2, np.array([sx, -sf, sz]), 1.0)
            if air_h:
                P = shift(P, list(P.keys()), np.array([-P["Hips"][0], -P["Hips"][1] + guard_P["Hips"][1], 0.0]))
                pose = pose_of(P, c, ground=False)
                pose = Pose(pose.D, np.array([pose.hips[0], pose.hips[1], air_h(t)]))
            else:
                pose = pose_of(P, c)
            if hop:
                hu = hop(t)
                if hu > 0.002:
                    pose = Pose(pose.D, pose.hips + np.array([0, 0, hu]))
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
        w = ease(min(1, t / 6))                           # D-135: raised over six frames (it was most of the way up in two: a snap)
        P = guard_P
        if fitted:
            # forearms in front of the face, measured from the fighter's own head (D-076)
            P = lean(P, (-10 if fid == "kairo" else -6) * w)       # D-136: Kairo tucks in behind the raised guard
            for side, sg in (("Left", 1), ("Right", -1)):
                bx, bf, bu = st.get("block", {}).get(side, (0.085, 0.19, -0.02))
                if fid == "kairo":                         # D-131: the forearms sat almost level; the lead one is now higher and further out
                    lead_b = side == st.get("_lead", "Left")
                    bf, bu = bf + (0.035 if lead_b else -0.025), bu + (0.035 if lead_b else -0.045)
                P = reach_hand(rig, P, side, (bx * sg * S_fit, bf * S_fit, bu * S_fit), w,
                               st["pose"].get("pelvis_h", 0.95) * rig.hips_h,
                               elbow_out=(0.5 if fid == "kairo" and side != st.get("_lead", "Left") else 0.12), from_head=True)   # D-133: rear forearm across, lead upright
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
        w = ease(min(1, t / 6))
        feet = {sd: guard_P[sd + "Foot"].copy() for sd in ("Left", "Right")}
        drop_b = 0.25 if fid == "kairo" else 0.17           # D-135: Kairo's was a slight dip; now a real low guard
        P = shift(guard_P, UPPER + ["Hips", "LHipJoint", "RHipJoint", "LeftUpLeg", "RightUpLeg"],
                  np.array([0, 0, -drop_b * H * w]))
        for sd in ("Left", "Right"):
            P = move_foot(P, sd, feet[sd])      # feet stay planted, knees bend
        chest = P["Spine2"] if "Spine2" in P else P["Head"] - np.array([0, 0, 0.28 * H])
        if fid == "kairo":
            # lead forearm swept down across the front of the lead knee (a gedan
            # barai), rear fist tight at the chin
            P = move_hand(P, "Left", P["Hips"] + np.array([0.10 * H, -0.30 * H, -0.06 * H]), w, pole_out=0.35)
            P = move_hand(P, "Right", P["Head"] + np.array([-0.05 * H, -0.13 * H, -0.09 * H]), w, pole_out=0.3)
        else:
            P = move_hand(P, "Left", chest + np.array([0.06 * H, -0.22 * H, -0.16 * H]), w, pole_out=0.25)
            P = move_hand(P, "Right", chest + np.array([-0.07 * H, -0.2 * H, 0.0]), w, pole_out=0.25)
        P = lean(P, -8 * w)
        if fitted:                                        # knees bend over the stance's own foot marks
            P = step_feet(rig, P, st, st["_lead"], drop=(0.22 if fid == "kairo" else 0.15) * S_fit * w)
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
            if fid == "kairo":                             # D-131: both boots went back and forth with the body (12 cm on the floor)
                for sd in ("Left", "Right"):
                    P = move_foot(P, sd, guard_P[sd + "Foot"])
            P = lean(P, 24 * amp * k, roll_deg=twist * k)
            if fid == "kairo":
                # D-133: the head lags the chest by a frame and a half on the way back,
                # then whips forward past it as he recovers (it moved rigidly with the chest)
                def kf(tt):
                    uu = tt / (n - 1)
                    return ease(min(1.0, max(0.0, tt) / 2.5), "out") * (1 - ease(max(0.0, (uu - 0.18) / 0.82)))
                kh = kf(t - 1.5) * 1.35 - 0.30 * max(0.0, math.sin(math.pi * min(1.0, max(0.0, (u - 0.28) / 0.35))))
                P = lean(P, 18 * amp * kh, about="Neck1", keys=["Head", "Head_end"])
            else:
                P = lean(P, 18 * amp * k, about="Neck1", keys=["Head", "Head_end"])
            for side, sg in (("Left", 1), ("Right", -1)):         # guard knocked loose
                P = move_hand(P, side, P[side + "Hand"] + np.array([0.05 * sg * H, 0.12 * H, -0.12 * H]) * amp, k * 0.8)
            out.append(pose_of(P, box))
        return out
    A[f"{F}_HIT_LIGHT"] = hit(15, 1.0, 9)                  # D-135: a light hit barely moved him (0.75)
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
        if fid == "kairo":                                 # D-133: the head lags as he folds, then comes up past the chest
            kh = min(1.0, max(0.0, u * 24 / 3.0 - 0.5)) * (1 - ease(max(0.0, (u - 0.3) / 0.7))) * 1.3 \
                - 0.35 * max(0.0, math.sin(math.pi * min(1.0, max(0.0, (u - 0.35) / 0.35))))
            P = lean(P, -14 * kh, about="Neck1", keys=["Head", "Head_end"])
        else:
            P = lean(P, -14 * kk, about="Neck1", keys=["Head", "Head_end"])
        if fid == "kairo":                                 # D-133: the boots turned on the spot as he folded (toes 9.5 cm along the floor)
            for sd in ("Left", "Right"):
                P = move_foot(P, sd, guard_P[sd + "Foot"])
                for tk_ in (sd + "ToeBase", sd + "ToeBase_end"):
                    if tk_ in P and tk_ in guard_P:
                        P[tk_] = guard_P[tk_].copy()
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
    # D-133: the fall had no arc: he dropped from the hit pose straight into lying.
    # Now the blow drives the shoulders back and round first (back arched, chest
    # turned away, arms thrown), the hips follow, and he hits the ground back first.
    arch_P = lean(guard_P, 48, roll_deg=-22)
    arch_P = lean(arch_P, 24, about="Neck1", keys=["Head", "Head_end"])
    arch_P = lean(arch_P, 0.0, roll_deg=-10) if fid == "kairo" else arch_P     # the shoulders, not the feet, turn away
    for sd, sg in (("Left", 1), ("Right", -1)):
        arch_P = move_hand(arch_P, sd, arch_P[sd + "Arm"] + np.array([0.30 * sg * H, 0.10 * H, 0.06 * H]), 0.85, pole_out=0.5)
    arch = pose_of(arch_P, box)
    # D-136 (owner: "he falls like a stiff plank; the knees should buckle first"):
    # the legs give way under him (hips drop over the planted feet, knees out
    # front), and he tips back from that lower point
    LEGS_UP = UPPER + ["Hips", "LHipJoint", "RHipJoint", "LeftUpLeg", "RightUpLeg"]
    def sunk(P0, depth, back=0.0):
        feet_ = {sd: P0[sd + "Foot"].copy() for sd in ("Left", "Right")}
        Pq = shift(P0, [k for k in LEGS_UP if k in P0], np.array([0, back * H, -depth * H]))
        for sd in ("Left", "Right"):
            Pq = move_foot(Pq, sd, feet_[sd], knee_out=0.15)
        return Pq
    buckle = pose_of(lean(sunk(guard_P, 0.30, 0.03), 8), box) if fid == "kairo" else None
    arch_low = pose_of(sunk(arch_P, 0.30, 0.06), box) if fid == "kairo" else None
    kd = []
    # D-135: knockdown_ticks 45 -> 39 and wakeup_ticks 20 -> 26, the same 65
    # ticks on the floor in all (the get-up popped up in a third of a second);
    # the fall takes 16 frames instead of 12
    for t in range(40):
        if t <= 4:
            p = Pose.blend(guard, heavy, ease(t / 4))
        elif fid == "kairo" and t <= 10:                   # the knees give way
            p = Pose.blend(heavy, buckle, ease((t - 4) / 6))
        elif fid == "kairo" and t <= 14:                   # tipping back from the low point
            p = Pose.blend(buckle, arch_low, ease((t - 10) / 4, "in"))
        elif fid == "kairo" and t <= 25:
            u_ = (t - 14) / 11.0
            p = Pose.blend(arch_low, lying, u_ ** 1.5)      # the fall speeds up all the way to the floor
        elif t <= 25:
            p = Pose.blend(heavy, lying, ease((t - 4) / 21, "in"))
        else:
            # D-131: the whole lying pose used to bob up and down as one stiff
            # piece. Now the back hits first and stops; the head, arms and legs
            # are thrown up by the impact a few frames later (part of the way to
            # sitting up) and drop again, once more much smaller, while the body
            # slides the last few centimetres and comes to rest.
            dt_ = t - 25
            flop = math.exp(-dt_ / 4.5) * max(0.0, math.sin(math.pi * dt_ / 7.0)) * 0.26 \
                + math.exp(-dt_ / 6.0) * max(0.0, math.sin(math.pi * (dt_ - 9) / 6.0)) * 0.10
            flop *= min(1.0, dt_ / 3.0)                    # D-135: the legs flew up 18 cm in the first frame on the floor
            p = Pose.blend(lying, sitting, flop) if flop > 1e-4 else Pose(lying.D, lying.hips.copy())
            b = math.exp(-dt_ / 2.5) * abs(math.sin(dt_ / 2.2)) * 0.022 * H
            p.hips = np.array([lying.hips[0], lying.hips[1], lying.hips[2] + b])
            br = 0.006 * H * math.sin(t * 0.25) * min(1.0, dt_ / 12.0)          # breathing, once he lies still
            p.hips = p.hips + np.array([0, 0, br])
        if t > 4:                                          # still sliding as he lands: the last 7 cm are covered on the ground
            p.hips = p.hips - np.array([0, 0.045 * H * math.exp(-max(0.0, t - 21) / 3.5), 0])
        kd.append(p)
    A[f"{F}_KNOCKDOWN"] = kd

    # get-up (26, D-135; was 20 and read as a pop): lying -> sit up -> crouch
    # -> guard, each stage overlapping the next so he never stops on the way
    crouch = Pose.blend(kneel, guard, 0.45)
    gu = []
    for t in range(27):
        if t <= 9:
            p = Pose.blend(lying, sitting, ease(t / 9))
        elif t <= 17:
            p = Pose.blend(sitting, crouch, ease((t - 9) / 8))
        else:
            p = Pose.blend(crouch, guard, ease((t - 17) / 9, "out"))
        gu.append(p)
    A[f"{F}_GETUP"] = gu

    if fid == "kairo":
        # D-141 (owner's quality brief: "a launch into the air with a fall", "getup
        # should have a roll or kip-up variant"). Launched (the game carries him on
        # the arc; the clip poses the body): the blow snaps him back, he folds back
        # over it with the legs swinging up in front, and stays laid out, limbs
        # trailing, until he lands (the knockdown is then entered at its touch-down).
        # D-143 (critique: "the torso leans back in a rigid block, no neck whiplash,
        # no trailing legs, no core compression"): the body first folds round the
        # blow (core compressed, head forward), then snaps back with the head
        # thrown further back a few frames behind the chest (whiplash), and lies
        # out on the arc with the knees bent and the legs trailing.
        comp = pose_of(lean(lean(guard_P, -10), -12, about="Neck1", keys=["Head", "Head_end"]), box)
        whip = pose_of(lean(arch_P, 26, about="Neck1", keys=["Head", "Head_end"]), box)
        trail = Pose.blend(Pose.blend(arch, lying, 0.45), sitting, 0.35)
        la = []
        for t in range(48):
            if t <= 3:
                p = Pose.blend(guard, comp, ease(t / 3, "out"))
            elif t <= 8:
                p = Pose.blend(comp, whip, ease((t - 3) / 5, "out"))
            elif t <= 14:
                p = Pose.blend(whip, arch, ease((t - 8) / 6))         # the head comes back up out of the whip
            elif t <= 24:
                p = Pose.blend(arch, trail, ease((t - 14) / 10))
            else:
                flail = 0.08 * math.sin((t - 24) * 0.4) * math.exp(-(t - 24) / 16.0)
                p = Pose.blend(trail, arch, max(0.0, flail))
            la.append(p)
        A[f"{F}_LAUNCHED"] = la
        # Kip-up (every other wake-up): the knees come up to the chest, then he
        # snaps up off his back onto his feet in one go and settles into the guard.
        # D-143 (critique: "no compression or anticipation, he pops up"): knees to
        # the chest, a rock back onto the shoulders (the load), the snap up, a deep
        # landing squat that absorbs it, then up into the guard.
        tuck = Pose.blend(lying, kneel, 0.32)
        tuck.hips = lying.hips + np.array([0.0, -0.05 * H, 0.04 * H])
        rock = Pose.blend(lying, kneel, 0.42)
        rock.hips = lying.hips + np.array([0.0, 0.05 * H, 0.02 * H])
        squat = Pose.blend(kneel, guard, 0.25)
        squat.hips = crouch.hips + np.array([0.0, 0.0, -0.07 * H])
        kp = []
        for t in range(27):
            if t <= 5:
                p = Pose.blend(lying, tuck, ease(t / 5))
                p.hips = lying.hips + (tuck.hips - lying.hips) * ease(t / 5)
            elif t <= 9:
                u_ = ease((t - 5) / 4)
                p = Pose.blend(tuck, rock, u_)
                p.hips = tuck.hips + (rock.hips - tuck.hips) * u_
            elif t <= 15:
                u_ = ease((t - 9) / 6)
                p = Pose.blend(rock, squat, u_)
                arc = math.sin(math.pi * u_) * 0.12 * H        # off the floor in an arc
                p.hips = rock.hips + (squat.hips - rock.hips) * u_ + np.array([0.0, 0.0, arc])
            elif t <= 19:
                u_ = ease((t - 15) / 4)
                p = Pose.blend(squat, crouch, u_ * 0.4)        # the landing is absorbed low, then he starts up
                p.hips = squat.hips + (crouch.hips - squat.hips) * u_ * 0.4
            else:
                u_ = ease((t - 19) / 7, "out")
                start = Pose.blend(squat, crouch, 0.4)
                start.hips = squat.hips + (crouch.hips - squat.hips) * 0.4
                p = Pose.blend(start, guard, u_)
            kp.append(p)
        A[f"{F}_GETUP_KIPUP"] = kp
        AIRBORNE[f"{F}_GETUP_KIPUP"] = (10, 14)               # the snap up: off the floor, not grounded

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
                        if not forward and fid == "kairo":         # D-134: stepping back the ball lands first and the heel rolls down
                            heel_up[foot] = max(heel_up[foot], 0.035 * S * (1.0 - smooth(q / 0.14)))
                        toe_up[foot] = 0.02 * S * (1.0 - smooth(q / 0.10)) if forward else 0.0
                    else:                                          # swinging
                        v = (q - WALK_PLANT) / (1.0 - WALK_PLANT)
                        o, up = -0.5 + ease(v), 0.065 * S * math.sin(math.pi * v)
                        heel_up[foot] = 0.04 * S * (1.0 - smooth(v / 0.5))
                        if not forward and fid == "kairo":
                            heel_up[foot] = max(heel_up[foot], 0.035 * S * smooth((v - 0.6) / 0.4))
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
                ride = 0.024 if fid == "kairo" else 0.014      # D-131: the pelvis rides further over the standing foot (weight transfer)
                P = shift(base_t, list(base_t.keys()), np.array([sg * ride * S * side_ph, 0.0, 0.0]))
                P = turn(P, -sg * 3.0 * side_ph)                   # pelvis and all: goes with the swinging leg
                hp = P["Hips"].copy()
                Rc = np.array(Matrix.Rotation(math.radians(sg * (5.5 + 2.5 * float(st.get("walk_life", 0.0))) * side_ph), 3, "Z"))
                for k in UPPER:                                    # shoulders against the pelvis
                    if k in P:
                        P[k] = Rc @ (P[k] - hp) + hp
                P = lean(P, (-3 if forward else 2) + 1.2 * math.sin(4 * math.pi * (ph - 0.1)))
                dip = ((0.028 if fid == "kairo" else 0.02) + 0.01 * float(st.get("walk_life", 0.0))) * S * 0.5 * (1.0 + math.cos(4 * math.pi * (ph - 0.06)))
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
            plan = {}                                      # feet of a travelling move: spot on the floor, step in progress
            hop_frames = []                                # frames of a skip: the exporter must not ground them
            handover = {}                                  # foot -> (frame, offset) as a keyed leg takes over from the plan
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
                # Feet in a move the game carries forward (D-133). The ultimate travels
                # 1.3 m and the uppercut 0.25 m while their stance feet stood on body-
                # space marks: in the world they skated the whole distance. Now each
                # stance foot keeps a spot on the floor (body space = spot - travel) and
                # steps to its keyed mark when it falls more than 7 cm behind, one foot
                # at a time, lead first, over five frames on a low arc.
                trv = tracks.get("_travel")
                if trv:
                    dist_, m0_, m1_ = trv
                    n_t = m1_ - m0_ + 1
                    def tv(k, dist_=dist_, m0_=m0_, n_t=n_t):
                        return dist_ / n_t * min(max(0, k - (m0_ - 1) + 1), n_t)
                    fast = dist_ / n_t > 0.04                       # quicker than a run: both feet may go at once (a leap)
                    free, lag = [], {}
                    # floor marks: lead "along" counts forward, rear "along" counts back, both in the
                    # fighter's own scale (fit_stance: mark * S); the plan works in metres forward
                    def fwd_m(fk_, mk):
                        return (1.0 if fk_ == "lead" else -1.0) * float(mk[1]) * S_fit
                    def along_of(fk_, m):
                        return (1.0 if fk_ == "lead" else -1.0) * m / S_fit
                    for fk_ in ("lead", "rear"):
                        if fk_ + "_foot_abs" in ps:
                            # a keyed leg: take its spot again when it lands. Where the plan had it
                            # elsewhere, the keyed leg starts from there and blends onto its keys
                            # over four frames (a 7 cm jump at the ultimate's kick, D-133)
                            old = plan.pop(fk_, None)
                            if old is not None and "body" in old:
                                handover[fk_] = (f, old["body"])
                            if fk_ in handover:
                                f_h, b_h = handover[fk_]
                                ab = ps[fk_ + "_foot_abs"]
                                if f - f_h == 0:
                                    handover[fk_] = (f_h, b_h - float(ab[1]))
                                off_ = handover[fk_][1] * max(0.0, 1.0 - (f - f_h) / 4.0)
                                if off_:
                                    ps[fk_ + "_foot_abs"] = (ab[0], float(ab[1]) + off_, ab[2], ab[3])
                                elif f - f_h >= 4:
                                    handover.pop(fk_, None)
                            continue
                        mk = ps.get(fk_ + "_foot", base_ps[fk_ + "_foot"])
                        st_ = plan.get(fk_)
                        if st_ is None:
                            st_ = plan[fk_] = {"spot": fwd_m(fk_, mk) + tv(f), "from": None}
                        if st_["from"] is not None and (f - st_["t0"]) >= st_["dur"]:
                            st_["spot"], st_["from"] = st_["to"], None
                        free.append(fk_)
                        lag[fk_] = fwd_m(fk_, mk) + tv(f) - st_["spot"]
                    alone = len(free) == 1 and any((k_ + "_foot_abs") in ps for k_ in ("lead", "rear"))
                    stepping = [k_ for k_ in free if plan[k_]["from"] is not None]
                    thresh = 0.12 if alone else (0.04 if fast else 0.07)
                    if f >= total - settle - 8:
                        thresh = 0.012                          # step home onto the marks before the blend into the stance
                    for fk_ in sorted(free, key=lambda k_: -abs(lag[k_])):   # the foot furthest behind goes first
                        st_ = plan[fk_]
                        if st_["from"] is None and abs(lag[fk_]) > thresh and (not stepping or fast):
                            mk = ps.get(fk_ + "_foot", base_ps[fk_ + "_foot"])
                            st_["dur"] = 8.0 if alone else 5.0
                            st_["from"], st_["t0"] = st_["spot"], f
                            st_["to"] = fwd_m(fk_, mk) + tv(f + int(st_["dur"])) + (0.08 if alone else 0.0)
                            stepping.append(fk_)
                    hops = []
                    for fk_ in free:
                        st_ = plan[fk_]
                        mk = ps.get(fk_ + "_foot", base_ps[fk_ + "_foot"])
                        if st_["from"] is not None:
                            u = (f - st_["t0"]) / st_["dur"]
                            along = st_["from"] + (st_["to"] - st_["from"]) * ease(u)
                            st_["body"] = along - tv(f)
                            ps[fk_ + "_foot"] = (float(mk[0]), along_of(fk_, along - tv(f)))
                            ps[fk_ + "_hop"] = 0.05 * math.sin(math.pi * u)
                            hops.append(ps[fk_ + "_hop"])
                        else:
                            st_["body"] = st_["spot"] - tv(f)
                            ps[fk_ + "_foot"] = (float(mk[0]), along_of(fk_, st_["spot"] - tv(f)))
                    if hops and (alone or len(hops) == len(free)):
                        ps["_body_hop"] = min(hops)              # no foot left on the floor: grounding would pull him down
                        hop_frames.append(f)
                    if os.environ.get("PLAN_DEBUG"):
                        print("PLAN", tracks.get("_name"), f + 1, {k_: (round(v_["spot"], 3), v_["from"] is not None) for k_, v_ in plan.items()},
                              {k_: (tuple(round(x, 3) for x in ps[k_ + "_foot"]), round(ps.get(k_ + "_hop", 0.0), 3)) for k_ in free},
                              "tv %.3f" % tv(f), "body_hop %.3f" % ps.get("_body_hop", 0.0))
                # A stance foot whose floor mark is moving is stepping, so it leaves
                # the floor (D-131). The steps of the jab, cross, palm, fireball and
                # ultimate were keyed as a moving mark only: the boot slid along the
                # ground, up to 11.6 cm in one frame on the palm's lunge.
                for fk_ in ("lead", "rear"):
                    trk = tracks.get(fk_ + "_foot")
                    if isinstance(trk, list) and fk_ + "_foot_abs" not in ps and not trv:
                        sp = float(np.linalg.norm(np.asarray(curve(warp(f + 1.5), trk), float)
                                                  - np.asarray(curve(warp(max(0.0, f - 1.5)), trk), float))) / 3.0
                        if sp > 0.004:   # a keyed hop (the spin kick's skip-step, D-146) is kept if it is higher
                            ps[fk_ + "_hop"] = max(float(ps.get(fk_ + "_hop", 0.0)), min(0.05, 0.01 + 0.9 * sp))
                # `_impact` (D-131): the body takes the blow. On the frames after the
                # contact the hips and trunk carry on a little (follow-through), give
                # back (recoil) and settle, while the striking fist or foot stays where
                # it is keyed, so the arm or leg takes the load. Without it every strike
                # reached its pose on the contact frame and stood: measured as "the head
                # goes on 0.0 cm after the contact" on eight of fourteen moves.
                imp = float(tracks.get("_impact", 0.0))
                if imp and tracks.get("_a0") is not None:
                    w = IMPACT_WAVE.get(f - int(tracks["_a0"]), 0.0) * imp
                    if w:
                        h = ps.get("hips", base_ps.get("hips", (0.0, 0.0)))
                        ps["hips"] = (float(h[0]) + 0.024 * w, float(h[1]))
                        tr_ = ps.get("trunk", base_ps.get("trunk", (0.0, 0.0)))
                        ps["trunk"] = (float(tr_[0]) + 2.6 * w, float(tr_[1]))
                        ps["chin"] = float(ps.get("chin", 0.0)) + 3.0 * w
                        ps["pelvis_h"] = float(ps.get("pelvis_h", 0.93)) - 0.006 * abs(w)
                        ps["curl"] = float(ps.get("curl", 0.0)) + 3.5 * w
                # the way home (D-134): the hands do not come back along a straight line.
                # They sink under it as the arm relaxes (the weight of the limb) and
                # rise into the guard at the end; `_lag` already starts them late.
                if imp and a1 is not None and f > a1 + hold:
                    span = float(max(1, total - settle - (a1 + hold)))
                    u_d = min(1.0, (f - a1 - hold) / span)
                    sag = 0.045 * math.sin(math.pi * u_d) ** 1.5
                    for hk in ("lead_hand_abs", "rear_hand_abs", "lead_hand", "rear_hand"):
                        if hk in ps and hk in tracks and isinstance(tracks[hk], list):
                            hv = ps[hk]
                            ps[hk] = (hv[0], hv[1], hv[2] - sag)
                st2 = dict(st, pose=ps, bob=0.0, sway=0.0, tap=0.0)
                P = shape_stance(dict(raw_guard), st2, H)
                P = fit_stance(rig, P, st2, st["_lead"], 0.0)
                aw = tracks.get("_air")                    # (first, last): a hop inside a grounded move (D-115)
                if air or (aw is not None and aw[0] <= f <= aw[1]):
                    if not air:
                        hop_frames.append(f)                 # D-139: the importer must not ground a hop either
                    p = pose_of(P, gclip, ground=False)
                    p = Pose(p.D, np.array([p.hips[0], p.hips[1], ps.get("pelvis_h", 0.93) * rig.hips_h + hips_c]))
                else:
                    p = pose_of(P, gclip)
                    if ps.get("_body_hop"):                       # a skip on the standing foot (D-133)
                        p = Pose(p.D, p.hips + np.array([0.0, 0.0, float(ps["_body_hop"]) * S_fit]))
                poses.append(p)
            if hop_frames and tracks.get("_name"):
                spans, cur = [], [hop_frames[0], hop_frames[0]]
                for hf in hop_frames[1:]:
                    if hf == cur[1] + 1:
                        cur[1] = hf
                    else:
                        spans.append(tuple(cur))
                        cur = [hf, hf]
                spans.append(tuple(cur))
                AIRBORNE[tracks["_name"]] = spans               # action frames count from 0, like the pose list
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
            tr.setdefault("_a0", mv["startup"] - 1)
            if fid == "kairo" and float(mv.get("move_distance", 0.0) or 0.0) > 0.0:
                tr.setdefault("_travel", (float(mv["move_distance"]), int(mv.get("move_start", 1)), int(mv.get("move_end", 1))))
            if "_recover" in tr:
                tr.setdefault("_impact", 1.0)
            if "_recover" in tr and "_hold" not in tr:     # a single strike: hold it, then return in the time left
                rec = mv["recovery"]
                tr["_hold"] = min(4, int(round(rec * 0.16)))
                tr["_recover"] = max(1.0, tr["_recover"] * (rec - tr["_hold"]) / float(rec))
                # who starts home when: hips and legs first, then the chest, the arms, the head last
                tr.setdefault("_lag", (("foot", 0.0), ("heel", 0.0), ("toe", 0.0), ("hips", 0.0), ("pelvis", 0.0),
                                       ("trunk", 1.0), ("curl", 1.5), ("shoulders", 1.5), ("hand", 2.0), ("elbow", 2.0), ("palm", 2.0),
                                       ("chin", 3.0), ("neck", 3.0), ("head", 3.0)))     # D-134: hands two frames behind the body (was one): drag
            # a move that starts from another pose (the crouch: D-136) must not be blended from the stance
            return keyed_frames(total, tr, mv["startup"] + mv["active"] - 2, settle, blend_in=tr.pop("_blend_in", 2))

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
        if fid == "kairo":
            # D-131: the two fists sat on one level in the crouch (2 cm apart in
            # height, 9 forward): the lead hand now leads, the rear fist sits
            # lower and closer, as in the stance.
            for key, d in (("lead_hand", (0.0, 0.05, 0.03)), ("rear_hand", (0.0, -0.05, -0.10))):
                if key in base_ps and not isinstance(ct.get(key), list):
                    h = ct.get(key, base_ps[key])
                    ct[key] = (h[0] + d[0], h[1] + d[1], h[2] + d[2])
        A[f"{F}_CROUCH"] = keyed_frames(n_cr, ct, settle=0, blend_in=0)
        if fid == "kairo":
            # Going down and standing up as clips of their own (D-131). The game
            # cross-faded stance and crouch at an even rate: half a metre in nine
            # equal steps. Down: a small rise first, the drop speeds up, he sinks
            # a little past the crouch and settles, the hands a beat behind the
            # hips. Up: a small dip, the push, a little past the stance, settle.
            n_tr = 12
            low = {k: (curve(0, v) if isinstance(v, list) else v) for k, v in ct.items() if not k.startswith("_")}
            for clip, rev in (("CROUCH_DOWN", False), ("CROUCH_UP", True)):
                tk = {"_name": clip}
                for k, v1 in low.items():
                    v0 = base_ps.get(k)
                    if v0 is None or isinstance(v1, str) or isinstance(v0, str):
                        tk[k] = v1
                        continue
                    a_, b_ = (np.asarray(v1, float), np.asarray(v0, float)) if rev else (np.asarray(v0, float), np.asarray(v1, float))
                    def mix(u, a_=a_, b_=b_):
                        v = a_ + (b_ - a_) * u
                        return tuple(float(x) for x in v) if np.ndim(v) else float(v)
                    late = 2 if ("hand" in k or k in ("chin", "neck")) else 0      # arms and head follow the hips
                    if k == "pelvis_h" and not rev:          # D-133: down: a lift, the drop speeds up, he sinks 10 % past the crouch and comes back up into it
                        tk[k] = [(0, mix(0.0)), (2, mix(-0.05), "io"), (8, mix(1.08), "io"), (10, mix(0.98)), (n_tr - 1, mix(1.0), "io")]   # D-135: eased over 6 frames (the accelerating drop covered most of it in 2)
                    elif k == "pelvis_h":                   # up: he sinks first (compression), drives up, rises a touch past the stance, settles
                        tk[k] = [(0, mix(0.0)), (3, mix(-0.10), "io"), (9, mix(1.04), "io"), (n_tr - 1, mix(1.0), "io")]
                    elif k == "trunk":
                        tk[k] = [(0, mix(0.0)), (2, mix(-0.04), "io"), (8, mix(1.06)), (n_tr - 1, mix(1.0), "io")]
                    elif k in ("lead_heel", "rear_heel"):
                        continue
                    else:
                        tk[k] = [(0, mix(0.0)), (1 + late, mix(0.0)), (8 + late, mix(1.03 if late else 1.0), "io"), (n_tr - 1, mix(1.0))]
                # heel roll (D-133): the heels come up as the weight drops onto the balls of the feet, and back down as it settles
                for hk in ("lead_heel", "rear_heel"):
                    h0_ = float(base_ps.get(hk, 0.0))
                    h1_ = float(low.get(hk, h0_)) if not isinstance(low.get(hk), str) else h0_
                    a_h, b_h = (h1_, h0_) if rev else (h0_, h1_)
                    pk = (5 if not rev else 6)
                    tk[hk] = [(0, a_h), (pk, max(a_h, b_h) + 0.035, "io"), (pk + 4, b_h, "io"), (n_tr - 1, b_h)]
                A[f"{F}_{clip}"] = keyed_frames(n_tr, tk, settle=0, blend_in=0)
        jd = STYLES[fid].get("jump", {})
        tuck = jd.get("tuck", 0.30) * S_fit
        jt = {"_name": "JUMP", "_feet_abs": (t_off, t_down - 1),
              # D-136 (owner: "he lands with straight legs; add a knee bend to absorb it"): the hips
              # are already coming down as the feet touch (they touched at standing height), and the
              # sink goes deeper over the landing frames
              "pelvis_h": [(0, ph0), (t_off - 1, ph0 - 0.16, "out"), (t_off + 3, ph0 + 0.02, "out"), (t_down - 3, ph0 - 0.01),
                           (t_down - 1, ph0 - 0.07, "in"), (t_down + 2, ph0 - 0.24, "out"), (n_jump - 1, ph0 - 0.17)],      # D-131: he lands and sinks through all four landing frames (it dipped and stood up again in two)
              "trunk": [(0, tr0), (t_off - 1, (tr0[0] + 16, tr0[1]), "out"), (t_off + 3, (tr0[0] - 4, tr0[1])),
                        (t_off + 12, (tr0[0] + 10, tr0[1]), "io"), (t_off + 26, (tr0[0] + 9, tr0[1])), (t_down - 2, (tr0[0] + 3, tr0[1])),
                        (t_down + 2, (tr0[0] + 14, tr0[1]), "out"), (n_jump - 1, (tr0[0] + 11, tr0[1]))],
              # D-107 (owner: "jumping does not look like a fighter"): a short
              # push-off with the toes pointed, then BOTH knees drawn up high in
              # front of the chest through the rise and the top (the feet came up
              # 0.3 and the rear leg trailed), held compact, then the legs reach
              # down for the floor over the last frames.
              "lead_foot_abs": [(t_off, hl), (t_off + 3, (hl[0], hl[1] - 0.03 * S_fit, hl[2] - 0.02, 0.9), "out"),
                                (t_off + 10, (hl[0] * 0.9, hl[1] * 0.45, hl[2] + tuck * 1.35, 0.55), "io"),
                                (t_off + 26, (hl[0] * 0.9, hl[1] * 0.40, hl[2] + tuck * 1.45, 0.55)),
                                (t_down - 7, (hl[0], hl[1] * 0.9, hl[2] + 0.12 * S_fit, 0.35), "io"), (t_down - 2, (hl[0], hl[1], hl[2] + 0.07, 0.45)),
                                (t_down - 1, (hl[0], hl[1], hl[2] + 0.035, 0.3))],      # D-134: toes reach down, the ball lands first
              "rear_foot_abs": [(t_off, hr), (t_off + 3, (hr[0], hr[1] - 0.05 * S_fit, hr[2] - 0.02, 0.9), "out"),
                                (t_off + 11, (hr[0] * 0.8, hr[1] * 0.10, hr[2] + tuck * 1.45, 0.6), "io"),
                                (t_off + 26, (hr[0] * 0.8, hr[1] * 0.05, hr[2] + tuck * 1.5, 0.6)),
                                (t_down - 7, (hr[0], hr[1] * 0.9, hr[2] + 0.14 * S_fit, 0.35), "io"), (t_down - 2, (hr[0], hr[1], hr[2] + 0.08, 0.45)),
                                (t_down - 1, (hr[0], hr[1], hr[2] + 0.045, 0.3))],
              # ... and the heels come down after it, over the landing frames
              "lead_heel": [(0, 0.0), (t_off - 1, 0.03), (t_down - 1, 0.05), (t_down, 0.045), (t_down + 2, 0.0)],
              "rear_heel": [(0, base_ps.get("rear_heel", 0.0)), (t_off - 1, 0.05), (t_down - 1, 0.06), (t_down, 0.055),
                            (t_down + 3, base_ps.get("rear_heel", 0.0))]}
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
                           (t_down + 2, off(0.03, -0.06, -0.10), "out"), (n_jump - 1, off(0.03, -0.05, -0.08))]
        jt.update(jd.get("pose", {}))
        A[f"{F}_JUMP"] = keyed_frames(n_jump, jt, settle=0 if fid == "kairo" else 3, air=True)
        AIRBORNE[f"{F}_JUMP"] = (t_off + 1, t_down - 1)
        if fid == "kairo" and "dash_distance" in moves:
            # Dashes (D-131). The first version keyed the feet around the body
            # without regard to how far the game carries him (1.4 m forward in 13
            # ticks, 0.21 m of it on the first): a foot that was "down" travelled
            # with him. Now each dash is a low leap: one foot stays on its spot of
            # the floor while it pushes (in body space it goes back by exactly the
            # distance covered so far, MovementProfile.dash_step), both feet are
            # off the ground while he moves fastest, and each foot lands on the
            # spot where it will stand at the end and stays there.
            for forward, n_d, dist in ((True, int(moves["dash"][0]), float(moves["dash_distance"][0])),
                                       (False, int(moves["dash"][1]), float(moves["dash_distance"][1]))):
                def cov(k, n_d=n_d, dist=dist):                # metres covered when clip frame k is shown
                    k = min(max(k, 0), n_d)
                    return dist * (1.0 - ((n_d - k) / float(n_d)) ** 2)
                end = cov(n_d - 1)
                sg = 1.0 if forward else -1.0
                push, reach = (hr, hl) if forward else (hl, hr)       # the foot that drives, the foot that lands first
                pk, rk = ("rear", "lead") if forward else ("lead", "rear")

                def fixed(home, k, at_end, sg=sg, end=end, cov=cov):
                    """the foot on one spot of the floor: where it stands at the end (at_end) or at the start"""
                    return (home[0], home[1] + sg * ((end if at_end else 0.0) - cov(k)), home[2], 0.0)
                p_off = 1 if forward else 2                    # last frame the driving foot is down
                r_land = 6 if forward else 8                   # the reaching foot lands
                p_land = 9 if forward else 12                  # the driving foot lands again
                pl, rl = fixed(push, p_off, False), fixed(reach, r_land, True)
                pe = fixed(push, p_land, True)
                up = 0.11 * S_fit
                dk = {"_name": "DASH_FORWARD" if forward else "DASH_BACK",
                      pk + "_foot_abs": [(k, fixed(push, k, False)) for k in range(0, p_off + 1)]
                      + [(p_off + 2, (push[0], pl[1] - sg * 0.02, push[2] + up * 1.2, 0.5)),
                         ((p_off + p_land) / 2.0 + 0.5, (push[0], (pl[1] + pe[1]) / 2.0 + sg * 0.04, push[2] + up, 0.3)),
                         (p_land - 1, (push[0], pe[1] + sg * 0.01, push[2] + 0.035, 0.1))]
                      + [(k, fixed(push, k, True)) for k in range(p_land, n_d)],
                      rk + "_foot_abs": [(0, reach), (1, (reach[0], reach[1] + sg * 0.04, reach[2] + 0.05, 0.2)),
                                         ((r_land + 1) / 2.0, (reach[0], (reach[1] + rl[1]) / 2.0 + sg * 0.03, reach[2] + up * 0.9, 0.15)),
                                         (r_land - 1, (reach[0], rl[1] + sg * 0.03, reach[2] + 0.04, -0.2 if forward else 0.4))]
                      + [(k, fixed(reach, k, True)) for k in range(r_land, n_d)],
                      pk + "_heel": [(0, 0.0), (p_off, 0.07), (p_off + 1, 0.0)],
                      "pelvis_h": [(0, ph0), (p_off + 1, ph0 - 0.045), (r_land - 2, ph0 - 0.02), (r_land + 1, ph0 - 0.10, "out"),
                                   (p_land + 1, ph0 - 0.05), (n_d - 1, ph0)],
                      "trunk": [(0, tr0), (p_off + 1, (tr0[0] + sg * 9, tr0[1])), (r_land - 2, (tr0[0] + sg * (15 if forward else 9), tr0[1])),
                                (r_land + 1, (tr0[0] + sg * (10 if forward else 4), tr0[1])), (n_d - 1, tr0)],
                      "chin": [(0, chin0), (r_land - 2, chin0 + (6 if forward else 3)), (n_d - 1, chin0)]}
                for key, kq in (("lead_hand", 1.0), ("rear_hand", 0.7)):
                    if key in base_ps:
                        h0 = base_ps[key]
                        dk[key] = [(0, h0), (p_off, (h0[0], h0[1] - 0.04 * kq, h0[2] - 0.05 * kq)),
                                   (r_land - 2, (h0[0], h0[1] + sg * 0.03 * kq, h0[2] + 0.03 * kq)),
                                   (r_land + 1, (h0[0], h0[1] - 0.02 * kq, h0[2] - 0.07 * kq), "out"), (n_d - 1, h0)]
                A[f"{F}_DASH_FORWARD" if forward else f"{F}_DASH_BACK"] = keyed_frames(n_d, dk, settle=2, air=True, blend_in=1)
                AIRBORNE[f"{F}_DASH_FORWARD" if forward else f"{F}_DASH_BACK"] = (p_off + 1, r_land - 1)
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
                k_chamber = (hl[0] * 0.3, 0.10 * S_fit, hl[2] + 0.60 * S_fit, -0.4)     # knee pulled up to the chest, foot under it (D-116: higher, reads at game distance)
                k_half = (0.02, hx + 0.08, hz + 0.13, -0.85)
                k_out = (0.02, hx + 0.34, hz + 0.08, -0.95)                            # heel first, leg fully straight (D-099)
                k_hold = (0.02, hx + 0.34, hz + 0.08, -0.95)
                # D-118, to the owner's reference (Ryu's flying side kick): the
                # kicking leg straight out, nearly level, a little below the hips,
                # foot edge first; the trunk almost upright, chest toward the
                # camera; the other leg folded tight under him; the front arm
                # straight down along the kicking leg, the back fist at the chest
                k_out = (0.02, hx + 0.36, hz + 0.30, -0.95)
                k_hold = (0.02, hx + 0.36, hz + 0.30, -0.95)
                k_half = (0.02, hx + 0.10, hz + 0.34, -0.85)
                k_back = (0.02, hx * 0.95, hz + 0.10, -0.8)                            # first frames of the pull back
                k_back2 = (hl[0] * 0.15, hx * 0.55, hz + 0.20, -0.6)
                r_tuck = (hr[0] * 0.8, -0.28 * S_fit, hr[2] + 0.30 * S_fit, 0.5)       # rear leg trails behind and below, bent ~0.6 (D-099: tucked to 0.28 it crushed the knee and pinched the thigh)
                # D-115 (owner: "robotic and unnatural"): that trailing leg hung
                # straight down under him like a kneeling man. Now it is tucked up
                # under the hips, knee forward, foot under the seat (bent ~0.45,
                # still clear of the D-099 pinch), and comes down for the landing
                r_tuck = (hr[0] * 0.30, 0.06 * S_fit, hr[2] + 0.44 * S_fit, 0.45)        # folded under, foot below the kicking thigh
                r_tuck2 = (hr[0] * 0.30, 0.04 * S_fit, hr[2] + 0.42 * S_fit, 0.45)
                # D-119 (owner: "his upper body stays straight, that's wrong, also
                # he is using the wrong leg"): the rear (right) leg kicks, the lead
                # leg folds under him; the hips turn the right side to the target
                # and the chest opens to the camera; the trunk leans back and away
                # from the kick and curls into it; the right arm reaches down along
                # the kicking leg, the left fist is pulled to the chest
                kR_tuck = (hr[0], 0.02 * S_fit, hr[2] + tuck, 0.2)
                kR_chamber = (hr[0] * 0.3, 0.10 * S_fit, hr[2] + 0.60 * S_fit, -0.4)
                kR_half = (-0.02, hx + 0.10, hz + 0.34, -0.85)
                kR_out = (-0.02, hx + 0.36, hz + 0.30, -0.95)
                kR_back = (-0.02, hx * 0.95, hz + 0.30, -0.8)
                l_tuck = (hl[0] * 0.30, 0.06 * S_fit, hl[2] + 0.44 * S_fit, 0.45)        # folded under, foot below the kicking thigh
                l_tuck2 = (hl[0] * 0.30, 0.04 * S_fit, hl[2] + 0.42 * S_fit, 0.45)
                at = {"_name": "JUMP_ATTACK", "pelvis_h": ph0,
                      "pelvis": [(0, pel0), (a0 - 3, pel0 - 30, "io"), (a0, pel0 - 88, "io"), (a0 + 5, pel0 - 92), (a1, pel0 - 86), (a1 + 3, pel0 - 50, "io"), (T, pel0 - 8, "io")],
                      "shoulders": [(0, sh0), (a0 - 3, sh0 - 16, "io"), (a0 + 1, sh0 - 44, "io"), (a0 + 6, sh0 - 48), (a1, sh0 - 42), (a1 + 3, sh0 - 22, "io"), (T, sh0 - 4, "io")],
                      "trunk": [(0, (tr0[0] + 4, tr0[1])), (a0 - 3, (tr0[0] + 2, tr0[1] + 3), "io"), (a0 + 1, (tr0[0] - 20, tr0[1] + 12), "io"),
                                (a0 + 5, (tr0[0] - 24, tr0[1] + 14)), (a1, (tr0[0] - 20, tr0[1] + 12)), (a1 + 4, (tr0[0] - 6, tr0[1] + 4), "io"), (T, (tr0[0] + 3, tr0[1]), "io")],
                      "chin": [(0, chin0), (a0, chin0 + 10, "in"), (a1, chin0 + 9), (T, chin0, "io")],
                      "rear_foot_abs": [(0, kR_tuck), (a0 - 3, kR_chamber, "out"), (a0 - 1, kR_half), (a0, kR_out),
                                        (a0 + 4, (kR_out[0], kR_out[1] + 0.05, kR_out[2] + 0.02, kR_out[3])),
                                        (a1 - 3, (kR_out[0], kR_out[1] + 0.01, kR_out[2] - 0.05, kR_out[3])),
                                        (a1, (kR_out[0], kR_out[1] - 0.03, kR_out[2] - 0.09, kR_out[3])), (a1 + 2, kR_back, "io"), (a1 + 4, kR_chamber, "io"),
                                        (T, (hr[0], hr[1] * 0.6, hr[2] + tuck * 0.6, 0.3))],
                      "lead_foot_abs": [(0, (hl[0], hl[1] * 0.45, hl[2] + tuck, 0.5)), (a0 - 3, (hl[0] * 0.8, hl[1] * 0.3, hl[2] + tuck + 0.06 * S_fit, 0.45), "io"),
                                        (a0 + 1, l_tuck, "io"), (a0 + 6, l_tuck2), (a1, (l_tuck[0], l_tuck[1] - 0.04, l_tuck[2] - 0.08, 0.4)),
                                        (T, (hl[0], hl[1] * 0.6, hl[2] + tuck * 0.6, 0.2))],
                      "rear_hand": [(0, rh0), (a0 - 3, (rh0[0], rh0[1] - 0.06, rh0[2] - 0.04)), (a0, (0.06, 0.40, -0.58), "in"),
                                    (a0 + 5, (0.06, 0.43, -0.60)), (a1, (0.06, 0.40, -0.56)),
                                    (a1 + 3, (rh0[0], rh0[1] + 0.04, rh0[2] - 0.16), "io"), (T, rh0, "out")],
                      "lead_hand": [(0, lh0), (a0 - 3, (lh0[0], lh0[1] - 0.04, lh0[2] - 0.04)), (a0, (0.02, 0.14, -0.32), "in"),
                                    (a0 + 6, (0.02, 0.13, -0.33)), (a1, (0.02, 0.14, -0.31)),
                                    (a1 + 3, (lh0[0], lh0[1] - 0.02, lh0[2] - 0.06), "io"), (T, lh0, "out")],
                      "rear_elbow": [(0, 0.1), (a0, 0.04), (a1, 0.05), (T, 0.1)],
                      "lead_elbow": [(0, 0.2), (a0, 0.75), (a1, 0.7), (T, 0.2)]}
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
        if os.environ.get("KAIRO_MOCAP_RIFT"):
            # D-120: Rift Break is keyed again, to the owner's axe-kick reference
            # (a taekwondo axe kick sequence); this recorded version is kept
            # behind KAIRO_MOCAP_RIFT=1
            # D-117 (owner: "look at fighting games and learn how to do them
            # properly"): Street Fighter V/6 build their moves from motion
            # capture of real fighters and then adjust it. Rift Break is now a
            # recorded axe kick (CMU 144_05: the right foot rises straight up in
            # front to head height and drops nearly vertically, frame 2498 at
            # the top; the hit is on the way down, ~2516), timed to the move's
            # frame data, the foot guided onto the hitbox. The move carries him
            # 1.4 m: a recording done on the spot would skate, so the standing
            # foot follows a skip (planted while the travel starts, a hop,
            # planted again as the body rides over it) and the kicking foot is
            # held to the floor until it lifts.
            mv = moves["FORWARD_SPECIAL"]
            axe = clip("144_05")
            m0, m1 = mv.get("move_start", 4) - 1, mv.get("move_end", 16) - 1
            v = mv.get("move_distance", 1.4) / float(m1 - m0 + 1)

            def travel(k):
                return v * min(max(0, k - m0 + 1), m1 - m0 + 1)
            FLk, FRk = tuple(g_foot["Left"]), tuple(g_foot["Right"])
            land_k, f_end = m1 - 3, 0.06
            w_land = f_end + travel(m1)
            hop0, hop1 = m0 + 3, land_k - 1
            lead_path = [(0, FLk), (m0 - 1, FLk)]
            for k in range(m0, m0 + 3):
                lead_path.append((k, (FLk[0], FLk[1] - travel(k), FLk[2])))
            lead_path += [(hop0 + 2, (FLk[0], (FLk[1] - travel(hop0) + w_land - travel(land_k)) * 0.5, FLk[2]), "io"),
                          (land_k, (FLk[0], w_land - travel(land_k), FLk[2]), "in")]
            for k in range(land_k + 1, m1 + 1):
                lead_path.append((k, (FLk[0], w_land - travel(k), FLk[2])))
            a1r = mv["startup"] + mv["active"] - 2
            lead_path += [(a1r + 6, (FLk[0], f_end, FLk[2])), (a1r + 12, FLk, "io")]
            total_r = mv["startup"] + mv["active"] - 1 + mv["recovery"]

            def stand(t):
                return ("Left", tuple(curve(t, lead_path)))

            def hop(t):
                if hop0 < t < land_k:
                    return 0.09 * math.sin(math.pi * (t - hop0) / float(land_k - hop0))
                return 0.0

            def rear_planted(P, t, T):
                # the kicking foot holds its spot on the floor while the travel
                # starts, then lets the recording lift it (weight 1 -> 0)
                if m0 <= t <= m0 + 3:
                    wgt = 1.0 - (t - m0) / 4.0
                    tgt = P["RightFoot"].copy()
                    tgt[1] = -(FRk[1] - travel(t))
                    tgt[2] = min(tgt[2], FRk[2] + 0.02)
                    P = move_foot(P, "Right", tgt, wgt)
                return P
            dk = (axe.at(2498)["RightFoot"] - axe.at(2498)["Hips"])[:2]
            A[F + "_SPECIAL_RIFT_BREAK"] = strike(axe, 2516, "Right", "foot", mv, pre=86, post=62, blend_in=4,
                                                  aim=dk / (np.linalg.norm(dk) + 1e-9), extra=rear_planted,
                                                  stand=stand, hop=hop, foot_last=True, guide_lead=1)
            # The Flying Side Kick from a recorded side kick (CMU 86_08, the
            # right-leg yoko geri at frame 4318: hips turned ~95 degrees, trunk
            # leaning ~38 degrees away, the foot driven 1.06 m straight out at
            # hip height), mirrored onto his lead (left) leg, in the air: the
            # hips stay at jump height and the other leg is tucked under him.
            mv = moves.get("AIR")
            # D-118: the owner's reference (Ryu's flying side kick) is a clear
            # pose, built keyed instead; KAIRO_MOCAP_AIR=1 keeps this version
            if mv and os.environ.get("KAIRO_MOCAP_AIR"):
                yoko = mirrored(clip("86_08"))
                dk = (yoko.at(4318)["LeftFoot"] - yoko.at(4318)["Hips"])[:2]
                air_hips = float(guard.hips[2])

                a0j = mv["startup"] - 1

                def tuck_other(P, t, T):
                    # the standing side kick tipped forward as a whole so the
                    # straight leg points down at the target (it was horizontal,
                    # at hip height) and the trunk comes more upright
                    tip = 22.0 * ease(min(1.0, max(0.0, (t + 1) / float(a0j + 1)))) * (1.0 - ease(min(1.0, max(0.0, (t - (T - 9)) / 9.0))))
                    P = lean(P, -tip, keys=list(P.keys()))
                    hp = P["Hips"]
                    w = min(1.0, (t + 2) / 4.0) * (1.0 - max(0.0, (t - (T - 5)) / 5.0) * 0.6)
                    return move_foot(P, "Right", hp + np.array([-0.10 * H, 0.24 * H, -0.50 * H]), w)
                A[F + "_JUMP_ATTACK"] = strike(yoko, 4322, "Left", "foot", mv, pre=48, post=26, blend_in=2, reach_w=0.0,
                                               aim=dk / (np.linalg.norm(dk) + 1e-9), extra=tuck_other,
                                               air_h=lambda t: air_hips)
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
