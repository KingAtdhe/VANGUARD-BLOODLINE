#!/usr/bin/env python3
"""Weight, kinetic chain, recoil and spacing of a clip, in numbers (D-131).

    python3 weight_report.py <fighter> <CLIP_SUFFIX> [<CLIP_SUFFIX> ...] [--csv-dir DIR]

Runs tools/godot/weight_check.gd and prints, per clip:
  CHAIN   (moves) how far the pelvis and the chest turn into the hit, the
          trunk's lean change, and the frame on which each turns fastest
          against the frame the striking limb moves fastest: ground -> hips
          -> chest -> limb means pelvis <= chest <= limb.
  WEIGHT  where the hips sit between the feet (0 = over the rear ankle, 1 =
          over the lead ankle) in the stance and at the hit; on one leg, how
          far the hips are from the standing ankle (forward and sideways).
  RECOIL  (moves) what the hips, chest and head do in the frames after the
          contact: a body that takes the blow moves on, then gives back.
  SPACING (other clips) the head's travel per frame: a linear move has every
          step alike (peak / mean near 1, first and last step near the peak).
  TWIN    how alike the two hands sit at the clip's middle (height, forward).
  FEET    drift of a foot along the floor while it is down (clips without
          travel; walks: tools/godot/foot_slide.gd).
Run from the project root."""
import csv
import io
import math
import subprocess
import sys


def load(fighter, clip):
    out = subprocess.run(["godot", "--headless", "--path", ".", "--script", "res://tools/godot/weight_check.gd", "--", fighter, clip],
                         capture_output=True, text=True).stdout
    head, body = None, []
    for line in out.splitlines():
        if line.startswith("#CLIP"):
            head = line.split()
        elif head and (line.startswith("f,") or (line[:1].isdigit() and "," in line)):
            body.append(line)
    if not head:
        return None, None, out
    rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(io.StringIO("\n".join(body)))]
    return {"name": head[1], "startup": int(head[5]), "active": int(head[7])}, rows, "\n".join(body)


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def report(fighter, clip, csv_dir=None):
    info, R, raw = load(fighter, clip)
    if info is None:
        print("%s: no data\n%s" % (clip, raw[-300:]))
        return
    if csv_dir:
        open("%s/%s.csv" % (csv_dir, clip), "w").write(raw)
    n, a0 = len(R), info["startup"] - 1
    a1 = a0 + info["active"] - 1
    move = info["startup"] > 0
    print("%s  %d frames%s" % (info["name"], n, "  contact = frame %d" % (a0 + 1) if move else ""))

    def d(key, i):
        return R[i][key] - R[i - 1][key]

    def speed(keys, i):
        return math.sqrt(sum(d(k, i) ** 2 for k in keys))

    lead_is_left = R[0]["la_f"] > R[0]["ra_f"]
    lead, rear = ("la", "ra") if lead_is_left else ("ra", "la")

    def share(i):
        span = R[i][lead + "_f"] - R[i][rear + "_f"]
        return (R[i]["hips_f"] - R[i][rear + "_f"]) / span if abs(span) > 0.05 else float("nan")

    if move:
        pel = wrap(R[a0]["pel"] - R[0]["pel"])
        che = wrap(R[a0]["chest"] - R[0]["chest"])
        back_pel = max(abs(wrap(R[i]["pel"] - R[0]["pel"])) for i in range(0, a0 + 1)) if a0 else 0.0
        lo = max(1, a0 - 12)
        fp = max(range(lo, a0 + 1), key=lambda i: abs(wrap(d("pel", i))))
        fc = max(range(lo, a0 + 1), key=lambda i: abs(wrap(d("chest", i))))
        limbs = {"left wrist": ("lw_f", "lw_x", "lw_h"), "right wrist": ("rw_f", "rw_x", "rw_h"),
                 "left ankle": ("la_f", "la_x", "la_h"), "right ankle": ("ra_f", "ra_x", "ra_h")}
        best = max(limbs, key=lambda k: max(speed(limbs[k], i) for i in range(lo, a0 + 1)))
        fl = max(range(lo, a0 + 1), key=lambda i: speed(limbs[best], i))
        order = "OK   " if fp <= fc <= fl else "CHECK"
        print("  CHAIN  %s pelvis turns %+.0f, chest %+.0f into the hit; trunk lean %+.0f fwd %+.0f side; hips travel %+.0f cm forward, %+.0f cm up/down"
              % ("OK   " if max(abs(pel), abs(che)) >= 20 or abs(R[a0]["lean_f"] - R[0]["lean_f"]) >= 12 else "CHECK", pel, che,
                 R[a0]["lean_f"] - R[0]["lean_f"], R[a0]["lean_s"] - R[0]["lean_s"],
                 (R[a0]["hips_f"] - R[0]["hips_f"]) * 100, (R[a0]["hips_h"] - R[0]["hips_h"]) * 100))
        print("  CHAIN  %s fastest frame: pelvis f%d (%.0f deg), chest f%d (%.0f deg), %s f%d (%.0f cm)   [hips -> chest -> limb]"
              % (order, fp + 1, abs(wrap(d("pel", fp))), fc + 1, abs(wrap(d("chest", fc))), best, fl + 1, speed(limbs[best], fl) * 100))
        wind = min(range(0, a0 + 1), key=lambda i: R[i]["hips_f"])
        print("  CHAIN  info  wind-up: hips furthest back on f%d (%+.0f cm), lowest f%d (%+.0f cm)"
              % (wind + 1, (R[wind]["hips_f"] - R[0]["hips_f"]) * 100,
                 min(range(0, a0 + 1), key=lambda i: R[i]["hips_h"]) + 1, (min(r["hips_h"] for r in R[:a0 + 1]) - R[0]["hips_h"]) * 100))
        # weight
        up = [k for k in ("la", "ra") if R[a0][k + "_h"] - R[0][k + "_h"] > 0.12]
        if len(up) == 1:
            st = "ra" if up[0] == "la" else "la"
            print("  WEIGHT %s on one leg at the hit: hips %+.0f cm forward of the standing ankle, %+.0f cm to the side (over it = near 0)"
                  % ("OK   " if abs(R[a0]["hips_f"] - R[a0][st + "_f"]) <= 0.12 else "CHECK",
                     (R[a0]["hips_f"] - R[a0][st + "_f"]) * 100, (R[a0]["hips_x"] - R[a0][st + "_x"]) * 100))
        else:
            s0, s1 = share(0), share(a0)
            print("  WEIGHT %s hips between the feet: stance %.2f -> hit %.2f (0 = over the rear ankle, 1 = over the lead)"
                  % ("OK   " if abs(s1 - s0) >= 0.12 else "CHECK", s0, s1))
        # recoil
        end = min(n - 1, a1 + 8)
        if end > a0 + 1:
            hf = [R[i]["head_f"] for i in range(a0, end + 1)]
            pk = max(range(len(hf)), key=lambda i: hf[i])
            giveback = (hf[pk] - min(hf[pk:])) * 100
            cf = [wrap(R[i]["chest"] - R[a0]["chest"]) for i in range(a0, end + 1)]
            print("  RECOIL %s after the contact the head goes on %.1f cm (to f%d), then gives back %.1f cm by f%d; chest turns on %.0f deg"
                  % ("OK   " if (hf[pk] - hf[0]) * 100 >= 1.0 and giveback >= 2.0 else "CHECK", (hf[pk] - hf[0]) * 100, a0 + pk + 1,
                     giveback, end + 1, max(abs(c) for c in cf)))
    else:
        steps = [speed(("head_f", "head_x", "head_h"), i) * 100 for i in range(1, n)]
        if max(steps) > 0.3:
            mv = [s for s in steps if s > 0.15 * max(steps)]
            print("  SPACING %s head: peak step %.1f cm, mean of the moving frames %.1f cm (peak / mean %.1f; 1 = linear), first step %.1f, last %.1f"
                  % ("OK   " if max(steps) / (sum(mv) / len(mv)) >= 1.5 else "CHECK", max(steps), sum(mv) / len(mv),
                     max(steps) / (sum(mv) / len(mv)), steps[0], steps[-1]))
            big = [i + 2 for i in range(1, len(steps)) if abs(steps[i] - steps[i - 1]) > 0.45 * max(steps)]
            if big:
                print("  SPACING CHECK step size jumps by over 45 %% of the peak on frames %s (a start or stop without easing)" % big[:8])
        hh = [r["hips_h"] for r in R]
        print("  SPACING info  hips lowest f%d (%.2f m), highest f%d (%.2f m)" % (hh.index(min(hh)) + 1, min(hh), hh.index(max(hh)) + 1, max(hh)))
    m = R[a0] if move else R[n // 2]
    print("  TWIN   %s hands at %s: height apart %.0f cm, forward apart %.0f cm, sideways apart %.0f cm"
          % ("OK   " if abs(m["lw_h"] - m["rw_h"]) >= 0.08 or abs(m["lw_f"] - m["rw_f"]) >= 0.12 else "CHECK",
             "the hit" if move else "the middle", abs(m["lw_h"] - m["rw_h"]) * 100, abs(m["lw_f"] - m["rw_f"]) * 100, abs(m["lw_x"] - m["rw_x"]) * 100))
    for k, nm in (("la", "left"), ("ra", "right")):
        low = min(r[k + "_h"] for r in R)
        tot, cnt, worst = 0.0, 0, 0.0
        for i in range(1, n):
            if R[i][k + "_h"] - low < 0.015 and R[i - 1][k + "_h"] - low < 0.015:
                s = math.hypot(d(k + "_f", i), d(k + "_x", i)) * 100
                tot, cnt, worst = tot + s, cnt + 1, max(worst, s)
        if cnt:
            print("  FEET   %s %s foot down on %d frames: drifts %.1f cm in all, %.1f cm at most in one frame (body space)"
                  % ("OK   " if worst <= 1.5 else "CHECK", nm, cnt, tot, worst))
    print()


def main():
    args = [a for a in sys.argv[1:]]
    csv_dir = None
    if "--csv-dir" in args:
        i = args.index("--csv-dir")
        csv_dir = args[i + 1]
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__)
        return 2
    for clip in args[1:]:
        report(args[0], clip, csv_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
