#!/usr/bin/env python3
"""What a build log says about a move's motion, frame by frame.

    python3 motion_report.py /root/work/build_kairo.log KICK_LOW_01
    python3 motion_report.py /root/work/build_kairo.log SPECIAL_RIFT_BREAK JUMP_ATTACK
    python3 motion_report.py /root/work/build_kairo.log                 (summary of every keyed clip)
    python3 motion_report.py /root/work/build_kairo.log --diff /root/work/build_kairo.prev.log

Reads the KEYED lines (KEYED_DEBUG=1: wrists, ankles, head, limb extension on
every frame) and GLITCH lines (GLITCH_SCAN=1) that build_fighter.sh always
switches on, and prints per clip:

  * a frame table: how far each wrist and ankle moved since the last frame
    (cm), head height, arm and leg extension (0 = folded, 1 = locked), with
    the move's phase (S startup, A active, R recovery) when the timings are
    known;
  * POP     a joint that jumped on one frame (from GLITCH_SCAN);
  * FAST    a wrist or ankle that covers a long way in a single frame. On
            the frame the strike lands that is right ("arrival", as long as
            the frame before carries a share of it); anywhere else, or when
            the whole strike happens in one frame, it is a snap that wants
            an in-between key (D-096, D-098, D-114);
  * DWELL   a raised foot that barely moves for six or more frames before
            the strike: a leg waiting in the air (Rift Break at D-122);
  * FOLD    a leg folded below 0.33 of its length (0.28 pinched the mesh, D-099);
  * FROZEN  four or more frames in a row on which no wrist, ankle or the head
            moves (the log rounds to 1 cm): a body standing still inside a
            move (D-085). Only checked for moves, not for the stance, crouch
            or jump. The few frames straight after the last active frame are
            the moving hold and are expected to be slow: marked "hold";
  * CONTACT the extension of each limb on the first active frame, and how
            far forward and how high the ankles and wrists are, next to the
            hitbox centre.

--diff: flags (pops and pose-checker faults) that are NEW against an earlier
log, and those that are gone. "No new flag" is the gate.

Limits, so the numbers are not over-trusted: KEYED lines are the build's own
skeleton before the spring pass and the blend into and out of the stance, and
the pelvis and chest are not in them. `legext 1.00` here is NOT proof of a
straight knee in the game: measure with tools/godot/body_angles.gd (D-114).
Frames are 1-based here (as in frame data); the keys in mocap_actions.py are
0-based (key frame k = frame k + 1 here).
A clean report is a move without broken joints, not a move that looks right:
look at every frame (frame_strip.py)."""
import argparse
import json
import math
import os
import re
import sys

NUM = r"(-?\d+\.\d+)"
KEYED = re.compile(r"^KEYED (\S+) (\d+) L=\(%s %s %s\) ext=%s R=\(%s %s %s\) ext=%s F \(%s %s %s\) \(%s %s %s\) head %s legext L=%s R=%s"
                   % ((NUM,) * 17))
GLITCH = re.compile(r"^GLITCH (\S+)\s+f(\d+)\s+(\S+)\s+moved (\d+\.\d+)")
FAULT = re.compile(r"^\s+([A-Z][A-Z0-9_]+)\s+(start|middle|end|any)\s+f(\d+)\s+(.*)$")
FAST_CM = {"hand": 25.0, "foot": 30.0}       # one-frame travel that has read as a snap (the log rounds to 1 cm)
STILL_CM = 0.25                              # below this on every tracked point = not moving


def parse(path):
    clips, pops, faults = {}, [], []
    for line in open(path, errors="replace"):
        m = KEYED.match(line)
        if m:
            v = [float(x) for x in m.groups()[2:]]
            clips.setdefault(m.group(1), []).append(dict(
                f=int(m.group(2)), LH=v[0:3], Lext=v[3], RH=v[4:7], Rext=v[7], LF=v[8:11], RF=v[11:14], head=v[14],
                Llext=v[15], Rlext=v[16]))
            continue
        m = GLITCH.match(line)
        if m:
            pops.append((m.group(1), int(m.group(2)), m.group(3), float(m.group(4))))
            continue
        m = FAULT.match(line)
        if m:
            faults.append((m.group(1), m.group(2), int(m.group(3)), m.group(4).strip()))
    return clips, pops, faults


def timings(log_path):
    """{CLIP NAME: (startup, active, recovery, hx, hz)} from moves_<id>.json beside the log."""
    out = {}
    d = os.path.dirname(os.path.abspath(log_path))
    for name in os.listdir(d):
        if name.startswith("moves_") and name.endswith(".json"):
            try:
                data = json.load(open(os.path.join(d, name)))
            except ValueError:
                continue
            for v in data.values():
                if isinstance(v, dict) and v.get("animation"):
                    out[str(v["animation"]).upper()] = (int(v["startup"]), int(v["active"]), int(v["recovery"]),
                                                        float(v["hc"][0]), float(v["hc"][1]))
    return out


def timing_for(clip, tms):
    if clip in tms:
        return tms[clip]
    for k, v in tms.items():                 # JUMP_ATTACK is logged without the fighter's name
        if k.endswith("_" + clip):
            return v
    return None


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3))) * 100.0


def report(clip, rows, pops, tm, table=True):
    rows = sorted(rows, key=lambda r: r["f"])
    n = len(rows)
    s = a = 0
    if tm:
        s, a = tm[0], tm[1]

    def ph(f):
        if not tm:
            return " "
        return "S" if f < s else ("A" if f < s + a else "R")

    sp = [None]
    for i in range(1, n):
        sp.append({k: dist(rows[i][k], rows[i - 1][k]) for k in ("LH", "RH", "LF", "RF")}
                  | {"head": abs(rows[i]["head"] - rows[i - 1]["head"]) * 100.0})
    head = "%s   %d frames" % (clip, n)
    if tm:
        head += "   startup %d / active %d / recovery %d   contact = frame %d   hitbox centre %.2f m forward, %.2f m high" % (
            tm[0], tm[1], tm[2], tm[0], tm[3], tm[4])
    print("\n" + head)
    if table:
        print("  f  ph | cm moved since last frame        | head  | arm ext     | leg ext")
        print("        |  L hand R hand  L foot  R foot   |  m    |  L     R    |  L     R")
        for i, r in enumerate(rows):
            v = sp[i]
            mv = "      -      -       -       -  " if v is None else "%7.1f%7.1f %7.1f %7.1f  " % (v["LH"], v["RH"], v["LF"], v["RF"])
            print(" %3d %s |%s | %.2f  | %.2f  %.2f  | %.2f  %.2f%s" % (
                r["f"], ph(r["f"]), mv, r["head"], r["Lext"], r["Rext"], r["Llext"], r["Rlext"],
                "   <- contact" if tm and r["f"] == s else ""))
    flags = 0
    for c, f, joint, d in pops:
        if c == clip or c.endswith("_" + clip):
            note = "  (the frame the strike fires: allowed if it is the strike itself)" if tm and s - 1 <= f <= s else ""
            print("  POP     f%-3d %-13s moved %.1f cm in one frame%s" % (f, joint, d * 100, note))
            flags += 1
    for i in range(1, n):
        for k, kind, label in (("LH", "hand", "left wrist"), ("RH", "hand", "right wrist"),
                               ("LF", "foot", "left ankle"), ("RF", "foot", "right ankle")):
            d = sp[i][k]
            f = rows[i]["f"]
            before = sp[i - 1][k] if i > 1 else 0.0
            if tm and f == s:
                # the strike landing: fast is right, as long as the frame before carries a share of it
                if max(d, before) <= FAST_CM[kind]:
                    continue
                if before < 0.25 * d:
                    print("  FAST    f%-3d %-11s lands with %.0f cm in one frame and only %.0f cm the frame before: "
                          "the whole strike is one frame. Add an in-between key" % (f, label, d, before))
                    flags += 1
                else:
                    print("  arrival f%d-%d %-11s %.0f cm then %.0f cm into the contact (late and fast: as it should be)"
                          % (f - 1, f, label, before, d))
            elif d > FAST_CM[kind] and not (tm and f == s - 1):
                print("  FAST    f%-3d %-11s travels %.0f cm in this one frame, away from the strike: a snap (wind-up, "
                      "rise or pull-back). Spread it over more frames" % (f, label, d))
                flags += 1
    # a raised foot that waits before the strike: the leg is up and goes nowhere while the move runs on
    # (Rift Break at D-122: vertical on frame 10, strike on frame 22)
    if tm:
        for k, label in (("LF", "left ankle"), ("RF", "right ankle")):
            i = 1
            while i < n:
                j = i
                while (j < n and rows[j]["f"] < s - 1 and rows[j][k][2] > 0.45 and sp[j][k] < 8.0
                       and abs(rows[j][k][2] - rows[i][k][2]) < 0.05):
                    j += 1
                if j - i >= 6:
                    print("  DWELL   f%d-%d %s is raised and keeps its height (within 5 cm) for %d frames before the strike: "
                          "a leg waiting in the air. Give those frames to the rise or the wind-up"
                          % (rows[i]["f"], rows[j - 1]["f"], label, j - i))
                    flags += 1
                i = max(j, i + 1)
        for label, ext in (("left", "Llext"), ("right", "Rlext")):
            low = [r for r in rows if r[ext] < 0.33]
            if low:
                worst = min(low, key=lambda r: r[ext])
                print("  FOLD    %s leg folded to %.2f of its length on f%d (%d frames below 0.33): 0.28 pinched the mesh "
                      "(D-099); look at that frame from the front and run stretch_check.py"
                      % (label, worst[ext], worst["f"], len(low)))
                flags += 1
    still = [i for i in range(1, n) if max(sp[i].values()) < STILL_CM] if tm else []   # only moves: a held crouch or a stance is meant to be still
    groups, cur = [], []
    for i in still:
        if cur and i == cur[-1] + 1:
            cur.append(i)
        else:
            if cur:
                groups.append(cur)
            cur = [i]
    if cur:
        groups.append(cur)
    for g in groups:
        if len(g) < 4:
            continue
        f0, f1 = rows[g[0]]["f"], rows[g[-1]]["f"]
        hold = tm and f0 >= s + a - 1 and f1 <= s + a + 5
        if hold:
            print("  hold    f%d-%d nothing moves more than %.2f cm (the hold after the hit: fine up to ~5 frames)" % (f0, f1, STILL_CM))
        else:
            print("  FROZEN  f%d-%d: %d frames on which no wrist, ankle or the head moves. Wrists, ankles and head only: "
                  "check the strip that the hips and chest are not still too" % (f0, f1, len(g)))
            flags += 1
    if tm and 1 <= s <= n:
        r = rows[s - 1]
        bend = lambda e: 2.0 * math.degrees(math.acos(min(1.0, e)))      # two equal segments: ext 0.96 is already ~32 degrees
        print("  CONTACT f%d: arm ext L %.2f R %.2f (elbow ~%.0f / ~%.0f deg) | leg ext L %.2f R %.2f (knee ~%.0f / ~%.0f deg) "
              "| ankles (forward, height) L (%.2f, %.2f) R (%.2f, %.2f) | wrists L (%.2f, %.2f) R (%.2f, %.2f)" % (
                  s, r["Lext"], r["Rext"], bend(r["Lext"]), bend(r["Rext"]), r["Llext"], r["Rlext"], bend(r["Llext"]),
                  bend(r["Rlext"]), -r["LF"][1], r["LF"][2], -r["RF"][1], r["RF"][2], -r["LH"][1], r["LH"][2], -r["RH"][1], r["RH"][2]))
        print("          (extension hides bend: 0.99 ~16 deg, 0.97 ~28, 0.95 ~36, 0.90 ~52. Exact angles on the game model: "
              "tools/godot/body_angles.gd)")
    if not flags:
        print("  no pops, snaps or frozen stretches reported. That is a move without broken joints, not yet a move that looks right.")
    return flags


def flag_set(pops, faults):
    return ({"POP %s f%d %s" % (c, f, j) for c, f, j, _d in pops}
            | {"POSE %s %s f%d %s" % (c, w, f, re.sub(r"-?\d+(\.\d+)?", "#", t)) for c, w, f, t in faults})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("clips", nargs="*", help="clip names or endings, e.g. KICK_LOW_01 JUMP_ATTACK")
    ap.add_argument("--diff", metavar="OLD_LOG", help="list flags that are new or gone against an earlier build log")
    a = ap.parse_args()
    clips, pops, faults = parse(a.log)
    if not clips:
        sys.exit("no KEYED lines in %s: was it built with KEYED_DEBUG=1 (build_fighter.sh does)?" % a.log)
    tms = timings(a.log)
    if a.diff:
        _c, p0, f0 = parse(a.diff)
        old, new = flag_set(p0, f0), flag_set(pops, faults)
        print("NEW flags (%d):" % len(new - old))
        for x in sorted(new - old):
            print("  + " + x)
        print("gone (%d):" % len(old - new))
        for x in sorted(old - new):
            print("  - " + x)
        print("unchanged: %d" % len(old & new))
        if not a.clips:
            return
    wanted = [c for c in clips if not a.clips or any(c == w.upper() or c.endswith("_" + w.upper()) or c.endswith(w.upper())
                                                     for w in a.clips)]
    if not wanted:
        sys.exit("no such clip. In this log: " + ", ".join(sorted(clips)))
    for c in sorted(wanted):
        report(c, clips[c], pops, timing_for(c, tms), table=bool(a.clips))
    if not a.clips:
        print("\n(summary only: name a clip for its frame table)")


if __name__ == "__main__":
    main()
