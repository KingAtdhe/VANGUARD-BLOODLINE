"""Pose quality control on the real game skeleton (D-075).

Measures a pose (the same bone rotations that are keyed into the action) on
the fighter's own rig and tests it against plain biomechanical limits, so a
stance or a keyed frame that no body could hold is reported by the build
instead of being found by the owner on a phone.

Used two ways:
  * `import_rigged.py` writes `<out>/<fighter>/pose_report.json` on every
    build: the stance blueprint as measured, and every action checked at its
    first, middle and last frame.
  * `python tools/blender/pose_check.py <pose_report.json>` prints it.

The numbers are checks, not proof that a pose looks good: every pose still
has to be rendered and looked at (tools/godot/pose_views.gd).
"""
import json
import math
import sys

import numpy as np

# Share of body mass per segment and where its centre sits along the segment
# (Dempster / Winter anthropometric tables, rounded).
SEGMENTS = [
    ("Head", "Head", "HEADTOP", 0.081, 0.5),
    ("Trunk", "Hips", "Neck", 0.497, 0.5),
    ("LeftUpperArm", "LeftUpperArm", "LeftLowerArm", 0.028, 0.436),
    ("RightUpperArm", "RightUpperArm", "RightLowerArm", 0.028, 0.436),
    ("LeftForearm", "LeftLowerArm", "LeftHand", 0.022, 0.6),
    ("RightForearm", "RightLowerArm", "RightHand", 0.022, 0.6),
    ("LeftThigh", "LeftUpperLeg", "LeftLowerLeg", 0.10, 0.433),
    ("RightThigh", "RightUpperLeg", "RightLowerLeg", 0.10, 0.433),
    ("LeftShank", "LeftLowerLeg", "LeftFoot", 0.0465, 0.433),
    ("RightShank", "RightLowerLeg", "RightFoot", 0.0465, 0.433),
    ("LeftFootSeg", "LeftFoot", "LeftToe", 0.0145, 0.5),
    ("RightFootSeg", "RightFoot", "RightToe", 0.0145, 0.5),
]

LIMITS = dict(
    knee_flex=(0.0, 150.0),        # degrees of bend, 0 = straight leg
    elbow_flex=(0.0, 150.0),
    wrist_bend=60.0,               # hand against forearm
    knee_toe=40.0,                 # knee pointing one way, foot another
    spine_twist=50.0,              # shoulder line against hip line
    neck_turn=65.0,                # where the head faces against the chest
    neck_tilt=20.0,                # head rolled toward a shoulder
    trunk_lean=45.0,
    spine_bend=28.0,               # lower back against chest: more is a broken-looking back
    foot_float=0.03,               # metres a planted foot may be off the floor
    cog_margin=-0.02,              # metres the centre of gravity may fall outside the feet
    hand_body=-0.005,              # metres: a wrist (with half a fist) this far inside the trunk's surface is a fault
    hand_head=-0.005,
    forearm_body=-0.005,           # the same for the forearm
)


def _ang(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def _flat(v):
    return np.array([v[0], v[1], 0.0])


def _hull(points):
    pts = sorted(set((round(float(p[0]), 5), round(float(p[1]), 5)) for p in points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _inside_margin(hull, p):
    """Signed distance of p to the hull boundary (+ inside)."""
    if len(hull) < 3:
        return -1.0
    d = 1e9
    for i in range(len(hull)):
        a, b = np.array(hull[i]), np.array(hull[(i + 1) % len(hull)])
        e = b - a
        n = np.array([-e[1], e[0]]) / (np.linalg.norm(e) + 1e-12)      # inward for a CCW hull
        d = min(d, float(np.dot(np.array(p) - a, n)))
    return d


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, float(np.dot(p - a, ab) / (np.dot(ab, ab) + 1e-12))))
    return float(np.linalg.norm(p - (a + ab * t)))


def joints(M, rig, pose):
    """Joint positions of a pose on the real rig, plus toe tips, heels and the top of the head."""
    pos, tails = M.fk(rig, pose.D, pose.hips)
    J = {k: np.asarray(v, float) for k, v in pos.items()}
    for sd in ("Left", "Right"):
        J[sd + "Toe"] = np.asarray(tails[sd + "Foot"], float)
        J[sd + "Knuckle"] = np.asarray(tails[sd + "Hand"], float)
        back = _flat(J[sd + "Foot"] - J[sd + "Toe"])
        back = back / (np.linalg.norm(back) + 1e-9)
        J[sd + "Heel"] = np.array([J[sd + "Foot"][0], J[sd + "Foot"][1], 0.0]) + back * 0.06 \
            + np.array([0, 0, max(0.0, J[sd + "Foot"][2] - rig.foot_h)])
    J["HEADTOP"] = np.asarray(tails["Head"], float)
    return J


def measure(M, rig, pose, floor=None):
    """The blueprint of a pose as it really is on the rig (metres, degrees).
    Forward is -Y (toward the opponent), +X is the fighter's left."""
    J = joints(M, rig, pose)
    S = rig.hips_h / 0.95                                   # body scale against a 0.95 m hip height
    if floor is None:
        # the build stands every grounded action on its lowest foot afterwards
        # (import_rigged.ground_actions), so the floor is wherever that foot is
        rest_toe = min(rig.tail["LeftFoot"][2], rig.tail["RightFoot"][2])
        floor = min(min(J[sd + "Foot"][2] - rig.foot_h, J[sd + "Toe"][2] - rest_toe) for sd in ("Left", "Right"))
    J = {k: v - np.array([0.0, 0.0, floor]) for k, v in J.items()}
    floor = 0.0
    m = {"rest_toe_height": round(float(min(rig.tail["LeftFoot"][2], rig.tail["RightFoot"][2])), 3),
         "trunk_half_width": round(float(rig.torso_rx), 3), "trunk_half_depth": round(float(rig.torso_ry), 3),
         "head_radius": round(float(rig.head_r), 3)}
    for sd in ("Left", "Right"):
        k = sd.lower()
        toe = _flat(J[sd + "Toe"] - J[sd + "Foot"])
        m[k + "_foot_xy"] = [round(float(J[sd + "Foot"][0]), 3), round(float(-J[sd + "Foot"][1]), 3)]
        m[k + "_foot_turnout"] = round(math.degrees(math.atan2((1 if sd == "Left" else -1) * toe[0], -toe[1])), 1)
        m[k + "_ankle_above_rest"] = round(float(J[sd + "Foot"][2] - rig.foot_h - floor), 3)
        m[k + "_toe_height"] = round(float(J[sd + "Toe"][2] - m["rest_toe_height"]), 3)
        m[k + "_knee_flex"] = round(180.0 - _ang(J[sd + "UpperLeg"] - J[sd + "LowerLeg"], J[sd + "Foot"] - J[sd + "LowerLeg"]), 1)
        # which way the knee bends: where it sits off the straight hip-to-ankle line
        leg = J[sd + "Foot"] - J[sd + "UpperLeg"]
        off = (J[sd + "LowerLeg"] - J[sd + "UpperLeg"]) - leg * float(np.dot(J[sd + "LowerLeg"] - J[sd + "UpperLeg"], leg) / (np.dot(leg, leg) + 1e-12))
        knee_dir = _flat(off)
        m[k + "_knee_vs_toe"] = round(_ang(knee_dir, toe), 1) if np.linalg.norm(knee_dir) > 0.05 else 0.0
        m[k + "_elbow_flex"] = round(180.0 - _ang(J[sd + "UpperArm"] - J[sd + "LowerArm"], J[sd + "Hand"] - J[sd + "LowerArm"]), 1)
        m[k + "_wrist_bend"] = round(_ang(J[sd + "Hand"] - J[sd + "LowerArm"], J[sd + "Knuckle"] - J[sd + "Hand"]), 1)
        if sd in rig.palm0:
            pn = pose.D[sd + "Hand"] @ rig.palm0[sd]
            m[k + "_palm_faces"] = [round(float(pn[0]), 2), round(float(-pn[1]), 2), round(float(pn[2]), 2)]
        m[k + "_wrist_xyz"] = [round(float(J[sd + "Hand"][0]), 3), round(float(-J[sd + "Hand"][1]), 3), round(float(J[sd + "Hand"][2]), 3)]
        m[k + "_elbow_xyz"] = [round(float(J[sd + "LowerArm"][0]), 3), round(float(-J[sd + "LowerArm"][1]), 3), round(float(J[sd + "LowerArm"][2]), 3)]
        # clearances from the surface of the trunk / head as the mesh has it
        # (metres; negative = inside): the wrist with half a fist, the forearm
        # at three points with half its own thickness
        m[k + "_hand_to_spine"] = round(M.trunk_clearance(rig, pose.D, J, J[sd + "Hand"], pad=0.04)[0], 3)
        fore = [J[sd + "LowerArm"] + (J[sd + "Hand"] - J[sd + "LowerArm"]) * f for f in (0.35, 0.55, 0.75)]
        m[k + "_forearm_to_spine"] = round(min(M.trunk_clearance(rig, pose.D, J, q, pad=0.025)[0] for q in fore), 3)
        m[k + "_hand_to_head"] = round(_seg_dist(J[sd + "Hand"], J["Head"], J["HEADTOP"]) - rig.head_r - 0.035, 3)
    m["feet_apart_along"] = round(abs(float(J["LeftFoot"][1] - J["RightFoot"][1])), 3)
    m["feet_apart_across"] = round(abs(float(J["LeftFoot"][0] - J["RightFoot"][0])), 3)
    yaw = lambda v: math.degrees(math.atan2(v[1], v[0]))    # 0 = square; + = left side back (right side leads)
    hip_yaw = yaw(J["LeftUpperLeg"] - J["RightUpperLeg"])
    sh_yaw = yaw(J["LeftUpperArm"] - J["RightUpperArm"])
    m["pelvis_height"] = round(float(J["Hips"][2] - floor), 3)
    m["pelvis_height_of_standing"] = round(float((J["Hips"][2] - floor) / rig.hips_h), 3)
    m["pelvis_yaw"] = round(hip_yaw, 1)
    m["chest_yaw"] = round(sh_yaw, 1)
    m["spine_twist"] = round(sh_yaw - hip_yaw, 1)
    trunk = J["Neck"] - J["Hips"]
    m["trunk_lean_forward"] = round(math.degrees(math.atan2(-trunk[1], trunk[2])), 1)
    m["trunk_lean_side"] = round(math.degrees(math.atan2(trunk[0], trunk[2])), 1)
    # the spine's own shape: how far the lower back and the chest lean apart
    # (a straight back is 0; + = chest folded forward over the pelvis, - = arched)
    low, high = J["Spine"] - J["Hips"], J["Neck"] - J["Chest"]
    m["pelvis_tilt_forward"] = round(math.degrees(math.atan2(-low[1], low[2])), 1)
    m["chest_tilt_forward"] = round(math.degrees(math.atan2(-high[1], high[2])), 1)
    m["spine_bend"] = round(_ang(low, high), 1)
    # the head: its bone runs up the skull; facing comes from the bone's own rotation
    Dh = pose.D["Head"]
    rest_face = np.array([rig.side0["head"][1], -rig.side0["head"][0], 0.0])
    face = Dh @ rest_face
    up = J["HEADTOP"] - J["Head"]
    m["head_yaw"] = round(math.degrees(math.atan2(face[0], -face[1])), 1)          # 0 = looking at the opponent
    m["head_pitch_down"] = round(math.degrees(math.atan2(-face[2], math.hypot(face[0], face[1]))), 1)
    side = Dh @ np.array([rig.side0["head"][0], rig.side0["head"][1], 0.0])
    m["head_tilt"] = round(math.degrees(math.asin(max(-1.0, min(1.0, float(side[2]))))), 1)
    m["neck_turn"] = round(abs(((m["head_yaw"] - sh_yaw) + 180) % 360 - 180), 1)
    m["head_xyz"] = [round(float(J["Head"][0]), 3), round(float(-J["Head"][1]), 3), round(float(J["Head"][2]), 3)]
    # centre of gravity against the feet
    cog, tot = np.zeros(3), 0.0
    for _n, a, b, w, f in SEGMENTS:
        cog += (J[a] + (J[b] - J[a]) * f) * w
        tot += w
    cog /= tot
    planted = [sd for sd in ("Left", "Right") if J[sd + "Foot"][2] - rig.foot_h - floor < 0.08 or J[sd + "Toe"][2] - m["rest_toe_height"] < 0.03]
    pts = []
    for sd in planted:
        toe, heel = J[sd + "Toe"], J[sd + "Heel"]
        w = np.array([-(toe - heel)[1], (toe - heel)[0]])
        w = w / (np.linalg.norm(w) + 1e-9) * 0.045
        for q in (toe, heel):
            if q is heel and heel[2] > 0.04 + floor:
                continue                                   # a lifted heel carries nothing
            pts += [(q[0] + w[0], q[1] + w[1]), (q[0] - w[0], q[1] - w[1])]
    hull = _hull(pts)
    m["cog_xyz"] = [round(float(cog[0]), 3), round(float(-cog[1]), 3), round(float(cog[2]), 3)]
    m["cog_inside_feet_by"] = round(_inside_margin(hull, (cog[0], cog[1])), 3)
    m["planted_feet"] = planted
    if len(planted) == 2:
        a, b = J["LeftFoot"], J["RightFoot"]
        lead = "Left" if a[1] < b[1] else "Right"
        la, ra = (a, b) if lead == "Left" else (b, a)
        span = la[1] - ra[1]
        m["lead_foot"] = lead
        m["weight_on_lead_foot"] = round(float((cog[1] - ra[1]) / span), 2) if abs(span) > 0.05 else 0.5
    return m


def faults(m, lifted=False, lying=False, reach=0.0):
    """What is wrong with a measured pose. lifted: both feet may be off the
    floor (jumps); lying: the body is on the floor (knockdowns), so balance
    and lean do not apply; reach: metres the centre of gravity may run past
    the feet in the middle of a committed strike or a step (momentum carries it)."""
    L, out = LIMITS, []
    for k in ("left", "right"):
        for key, lim in (("knee_flex", L["knee_flex"]), ("elbow_flex", L["elbow_flex"])):
            v = m["%s_%s" % (k, key)]
            if v < lim[0] - 1 or v > lim[1]:
                out.append("%s %s %.0f outside %s" % (k, key, v, lim))
        if m[k + "_wrist_bend"] > L["wrist_bend"]:
            out.append("%s wrist bent %.0f" % (k, m[k + "_wrist_bend"]))
        if not lying and m[k + "_knee_flex"] > 25 and m[k + "_knee_vs_toe"] > L["knee_toe"] and k.capitalize() in m["planted_feet"]:
            out.append("%s knee points %.0f away from its foot" % (k, m[k + "_knee_vs_toe"]))
        if not lying and m[k + "_hand_to_spine"] < L["hand_body"]:
            out.append("%s hand inside the torso (%.2f m clear)" % (k, m[k + "_hand_to_spine"]))
        if not lying and m[k + "_forearm_to_spine"] < L["forearm_body"]:
            out.append("%s forearm inside the torso (%.2f m clear)" % (k, m[k + "_forearm_to_spine"]))
        if not lying and m[k + "_hand_to_head"] < L["hand_head"]:
            out.append("%s hand inside the head (%.2f m clear)" % (k, m[k + "_hand_to_head"]))
        if m[k + "_toe_height"] < -0.03 or m[k + "_ankle_above_rest"] < -0.04:
            out.append("%s foot below the floor" % k)
    if lying:
        return out
    if abs(m["spine_twist"]) > L["spine_twist"]:
        out.append("spine twisted %.0f" % m["spine_twist"])
    if m["neck_turn"] > L["neck_turn"]:
        out.append("neck turned %.0f" % m["neck_turn"])
    if m["spine_bend"] > (45.0 if reach > 0 else L["spine_bend"]):      # a kick tips the pelvis with the leg
        out.append("back bent %.0f (pelvis %+.0f, chest %+.0f forward)" % (m["spine_bend"], m["pelvis_tilt_forward"], m["chest_tilt_forward"]))
    if abs(m["head_tilt"]) > L["neck_tilt"]:
        out.append("head tilted %.0f to the side" % m["head_tilt"])
    if abs(m["trunk_lean_forward"]) > L["trunk_lean"] or abs(m["trunk_lean_side"]) > (45 if reach > 0 else 30):
        out.append("trunk leans %.0f forward, %.0f sideways" % (m["trunk_lean_forward"], m["trunk_lean_side"]))
    if not lifted:
        if not m["planted_feet"]:
            out.append("no foot on the floor")
        elif m["cog_inside_feet_by"] < L["cog_margin"] - reach:
            out.append("centre of gravity %.2f m outside the feet" % -m["cog_inside_feet_by"])
        for k in ("left", "right"):
            if k.capitalize() in m["planted_feet"] and min(m[k + "_ankle_above_rest"], m[k + "_toe_height"]) > L["foot_float"]:
                out.append("%s foot floats" % k)
    return out


def report(M, rig, actions, fid, moving=()):
    """Blueprint of the stance and a check of every action at its first,
    middle and last frame. `moving`: actions in which the body is thrown,
    jumps or lies down (balance is not expected there)."""
    F = fid.upper()
    idle = actions["%s_IDLE_A" % F]
    out = {"fighter": fid, "rest_shape_yaw": round(rig.rest_yaw, 1), "stance": measure(M, rig, idle[0]),
           "stance_faults": faults(measure(M, rig, idle[0])), "actions": {}}
    # feet through the idle loop: a planted foot must not slide
    slide = {}
    for sd in ("Left", "Right"):
        xs = [joints(M, rig, p)[sd + "Foot"] for p in idle]
        base = min(x[2] for x in xs)
        low = [x for x in xs if x[2] - base < 0.02]
        if len(low) > 1:
            c = np.mean(low, 0)
            slide[sd.lower()] = round(float(max(np.linalg.norm((x - c)[:2]) for x in low)), 3)
    out["idle_foot_slide"] = slide
    for name, poses in sorted(actions.items()):
        short = name[len(F) + 1:]
        free = any(w in short for w in moving)
        rows = {}
        for label, i in (("start", 0), ("middle", len(poses) // 2), ("end", len(poses) - 1)):
            m = measure(M, rig, poses[i])
            dyn = 0.10 if label == "middle" and any(w in short for w in ("ATTACK", "KICK", "SPECIAL", "ULTIMATE", "WALK", "DASH")) else 0.0
            if "WALK" in short or "DASH" in short:
                dyn = 0.12                               # a step: one foot carries the body for a moment
            rows[label] = {"frame": i + 1, "faults": faults(m, lifted=free, lying=free, reach=dyn),
                           "cog_inside_feet_by": m["cog_inside_feet_by"], "pelvis_height": m["pelvis_height"]}
        if not free:
            # arms through the body are looked for on every frame, not three
            worst = None
            for i, pz in enumerate(poses):
                m = measure(M, rig, pz)
                inside = [f for f in faults(m, lifted=True) if "inside" in f]
                if inside and worst is None:
                    worst = {"frame": i + 1, "faults": inside, "cog_inside_feet_by": m["cog_inside_feet_by"],
                             "pelvis_height": m["pelvis_height"]}
            if worst and not any("inside" in f for r in rows.values() for f in r["faults"]):
                rows["any"] = worst
        out["actions"][short] = rows
    return out


def show(rep):
    s = rep["stance"]
    print("%s  (rest shape turned %+.1f deg)" % (rep["fighter"].upper(), rep["rest_shape_yaw"]))
    for k in sorted(s):
        print("  %-28s %s" % (k, s[k]))
    print("  stance faults: %s" % (rep["stance_faults"] or "none"))
    print("  idle foot slide (m): %s" % rep["idle_foot_slide"])
    bad = 0
    for name, rows in rep["actions"].items():
        for label, r in rows.items():
            if r["faults"]:
                bad += 1
                print("  %-22s %-6s f%-3d %s" % (name, label, r["frame"], "; ".join(r["faults"])))
    print("  %d action frames with faults out of %d checked" % (bad, 3 * len(rep["actions"])))


if __name__ == "__main__":
    for path in sys.argv[1:]:
        show(json.load(open(path)))
