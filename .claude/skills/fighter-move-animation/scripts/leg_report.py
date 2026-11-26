#!/usr/bin/env python3
"""Validate a kick on the game model: the kicking leg's path, the knee, the
supporting foot, and a side-view drawing of the trajectory.

    python3 leg_report.py <fighter> <CLIP_SUFFIX> <Right|Left> [--plot out.png] [--csv keep.csv]
    python3 leg_report.py kairo SPECIAL_RIFT_BREAK Right --plot /root/work/rift_path.png

Runs tools/godot/leg_check.gd (the clip as Godot plays it) and prints what
can be measured about the kick, each line marked OK or CHECK:

  KNEE      never bends the wrong way; no sudden change in the part of its
            rotation that is not flexion (a thigh rolling over: D-129 found
            the knee of a raised leg bending backwards on the mesh while every
            joint position looked right); bend at the peak and at the contact.
  PATH      how high the foot goes against the head; how near vertical the
            leg is at the peak; how far the foot strays sideways (a kick in
            one plane stays within a few centimetres); how steep the strike
            comes down; whether it speeds up into the contact.
  FEET      the supporting foot against the floor IN THE WORLD (model space
            plus the game's travel): slide while planted; no foot under the
            floor.
  FLOW      the largest one-frame move of the ankle and of the head; first and
            last frame the same pose.

--plot draws the hip, knee and ankle paths from the side (forward against
height) and from the front (sideways against height), with the leg drawn at
the frames that matter, so the trajectory can be looked at, not only read.

OK means the number is inside the mark, not that the kick looks right: look
at the strip too (frame_strip.py). Needs godot; Pillow for --plot."""
import argparse
import csv
import math
import os
import subprocess
import sys


def run(fighter, clip, side):
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
    r = subprocess.run(["godot", "--headless", "--path", root, "--script", "res://tools/godot/leg_check.gd", "--",
                        fighter, clip, side], capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l and not l.startswith("Godot")]
    head = next((l for l in lines if l.startswith("LEG ")), None)
    if head is None:
        sys.exit("leg_check.gd gave no data:\n" + (r.stdout + r.stderr)[-1500:])
    i = lines.index(head)
    rows = list(csv.DictReader(lines[i + 1:]))
    meta = dict(x.split("=") for x in head.split()[4:])
    for row in rows:
        for k, v in row.items():
            if k != "phase":
                row[k] = float(v)
    return meta, rows, lines[i:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fighter")
    ap.add_argument("clip")
    ap.add_argument("side", choices=["Right", "Left"])
    ap.add_argument("--plot")
    ap.add_argument("--csv")
    a = ap.parse_args()
    meta, R, raw = run(a.fighter, a.clip, a.side)
    if a.csv:
        open(a.csv, "w").write("\n".join(raw) + "\n")
    s, act = int(meta["startup"]), int(meta["active"])
    n = len(R)
    F = lambda f: R[f - 1]                                  # 1-based frame
    checks = []

    def say(group, ok, text):
        checks.append(ok)
        print("  %-5s %-5s %s" % (group, "OK" if ok else "CHECK", text))

    print("%s %s leg: %d frames, contact = frame %d, active %d, travel %s m on frames %s" % (
        a.clip, a.side.lower(), n, s, act, meta["travel"], meta["travel_frames"]))

    # --- knee
    lo = min(R, key=lambda r: r["knee_flex"])
    say("KNEE", lo["knee_flex"] > -3.0, "smallest bend %.1f deg on frame %d (below 0 = bending the wrong way)" % (lo["knee_flex"], lo["f"]))
    jump = max(range(1, n), key=lambda i: abs(R[i]["knee_other"] - R[i - 1]["knee_other"]))
    dj = abs(R[jump]["knee_other"] - R[jump - 1]["knee_other"])
    say("KNEE", dj < 15.0, "largest one-frame change in non-flexion rotation %.1f deg (frame %d): a jump means the thigh rolled over" % (dj, R[jump]["f"]))
    peak = max(R[:s], key=lambda r: r["ank_u"]) if s else max(R, key=lambda r: r["ank_u"])
    if s:
        say("KNEE", True, "bend at the peak (frame %d) %.0f deg, at the contact (frame %d) %.0f deg, most on the way down %.0f deg" % (
            peak["f"], peak["knee_flex"], s, F(s)["knee_flex"], max(r["knee_flex"] for r in R[int(peak["f"]) - 1:s])))

    # --- path
    over = peak["ank_u"] - peak["head_u"]
    say("PATH", over > 0.0, "foot at %.2f m on frame %d, head at %.2f m: %s the head by %.0f cm" % (
        peak["ank_u"], peak["f"], peak["head_u"], "above" if over > 0 else "BELOW", abs(over) * 100))
    high = [r for r in (R[:s] if s else R) if r["ank_u"] > peak["ank_u"] - 0.12]
    steepest = max(high, key=lambda r: math.atan2(r["ank_u"] - r["hip_u"], abs(r["ank_f"] - r["hip_f"])))
    ang = math.degrees(math.atan2(steepest["ank_u"] - steepest["hip_u"], abs(steepest["ank_f"] - steepest["hip_f"])))
    say("PATH", ang > 70.0, "leg at its steepest near the peak (frame %d) %.0f deg from the floor (90 = vertical), hip to ankle" % (steepest["f"], ang))
    if s:
        seg = R[max(0, s - 12):min(n, s + act - 1)]
        sp = (max(r["ank_s"] for r in seg) - min(r["ank_s"] for r in seg)) * 100
        say("PATH", sp < 10.0, "sideways spread of the foot from the lift to the end of the strike %.1f cm (one plane = a few cm)" % sp)
        end = F(min(n, s + act - 1))
        # the strike = from the last frame the foot is still within 5 cm of its peak height
        hi = max((r["f"] for r in R[int(peak["f"]) - 1:s] if r["ank_u"] > peak["ank_u"] - 0.05), default=peak["f"])
        st = F(int(hi))
        drop, fwd = st["ank_u"] - end["ank_u"], end["ank_f"] - st["ank_f"]
        steep = math.degrees(math.atan2(drop, abs(fwd)))
        say("PATH", steep > 45.0, "strike (frames %d-%d): down %.2f m, forward %.2f m = %.0f deg below level (over 45 = more down than forward)" % (
            st["f"], end["f"], drop, fwd, steep))
        c0, c1 = F(s), end
        d2, f2 = c0["ank_u"] - c1["ank_u"], c1["ank_f"] - c0["ank_f"]
        say("PATH", math.degrees(math.atan2(d2, abs(f2))) > 60.0, "through the hit (frames %d-%d): down %.2f m, forward %.2f m = %.0f deg below level" % (
            s, end["f"], d2, f2, math.degrees(math.atan2(d2, abs(f2)))))
        v = [math.dist((R[i]["ank_f"], R[i]["ank_u"], R[i]["ank_s"]), (R[i - 1]["ank_f"], R[i - 1]["ank_u"], R[i - 1]["ank_s"])) * 100
             for i in range(1, n)]
        v3 = [v[s - 4], v[s - 3], v[s - 2]] if s >= 4 else []
        if v3:
            say("PATH", v3[2] > v3[0], "foot speed into the contact %.0f, %.0f, %.0f cm a frame (should rise)" % tuple(v3))
        toes = F(s)["toes_back"]
        say("PATH", toes > 15.0, "foot at the contact: toes pulled back %.0f deg against the rest pose (heel leading; under 0 = pointed)" % toes)

    # --- feet in the world
    planted = [r for r in R if r["sup_u"] < 0.035]
    runs, cur = [], []
    for r in planted:
        if cur and r["f"] == cur[-1]["f"] + 1 and abs(r["sup_world_f"] - cur[-1]["sup_world_f"]) < 0.02:
            cur.append(r)
        else:
            if len(cur) > 3:
                runs.append(cur)
            cur = [r]
    if len(cur) > 3:
        runs.append(cur)
    if runs:
        longest = max(runs, key=len)
        slide = (max(r["sup_world_f"] for r in longest) - min(r["sup_world_f"] for r in longest)) * 100
        say("FEET", slide < 1.5, "supporting foot planted on frames %d-%d: moves %.1f cm on the floor in the world" % (
            longest[0]["f"], longest[-1]["f"], slide))
    low = min(min(r["ank_u"] for r in R), min(r["sup_u"] for r in R))
    rest_h = min(R[0]["ank_u"], R[0]["sup_u"])
    say("FEET", low > rest_h - 0.04, "lowest ankle %.3f m (the stance ankle is at %.3f): %s" % (
        low, rest_h, "no foot under the floor" if low > rest_h - 0.04 else "a foot goes under the floor"))

    # --- flow
    v = [math.dist((R[i]["ank_f"], R[i]["ank_u"]), (R[i - 1]["ank_f"], R[i - 1]["ank_u"])) * 100 for i in range(1, n)]
    vi = max(range(len(v)), key=lambda i: v[i])
    say("FLOW", v[vi] < 60.0, "largest one-frame move of the kicking ankle %.0f cm (frame %d%s)" % (
        v[vi], R[vi + 1]["f"], ", the hit" if s and abs(R[vi + 1]["f"] - s) <= 1 else ""))
    h = [math.dist((R[i]["head_f"], R[i]["head_u"]), (R[i - 1]["head_f"], R[i - 1]["head_u"])) * 100 for i in range(1, n)]
    hi_ = max(range(len(h)), key=lambda i: h[i])
    say("FLOW", h[hi_] < 12.0, "largest one-frame move of the head %.1f cm (frame %d)" % (h[hi_], R[hi_ + 1]["f"]))
    same = math.dist((R[0]["ank_f"], R[0]["ank_u"], R[0]["head_u"]), (R[-1]["ank_f"], R[-1]["ank_u"], R[-1]["head_u"])) * 100
    say("FLOW", same < 3.0, "first and last frame differ by %.1f cm (ankle and head): starts and ends in the stance" % same)
    print("  %d of %d marks OK. Marks are numbers, not looks: read the strip as well." % (sum(checks), len(checks)))

    if a.plot:
        from PIL import Image, ImageDraw, ImageFont
        W, H, sc = 1500, 760, 380.0
        im = Image.new("RGB", (W, H), (24, 25, 28))
        d = ImageDraw.Draw(im)
        try:
            ft = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
        except OSError:
            ft = ImageFont.load_default()

        def side_xy(f_, u_):
            return 230 + f_ * sc, H - 60 - u_ * sc

        def front_xy(s_, u_):
            return 1210 + s_ * sc, H - 60 - u_ * sc

        d.line([20, H - 60, 960, H - 60], fill=(110, 110, 110), width=2)
        d.line([1040, H - 60, W - 20, H - 60], fill=(110, 110, 110), width=2)
        d.text((20, 10), "%s %s leg from the SIDE (the game's view): forward ->, height up. Opponent to the right." % (a.clip, a.side.lower()), fill=(235, 235, 235), font=ft)
        d.text((1040, 10), "from the FRONT: sideways, height up", fill=(235, 235, 235), font=ft)
        col = lambda r: (150, 150, 150) if r["phase"] == "S" else ((235, 70, 60) if r["phase"] == "A" else (80, 140, 235))
        for key, wd in (("hip", 1), ("knee", 1), ("ank", 3)):
            for i in range(1, n):
                d.line([side_xy(R[i - 1][key + "_f"], R[i - 1][key + "_u"]), side_xy(R[i][key + "_f"], R[i][key + "_u"])], fill=col(R[i]), width=wd)
                d.line([front_xy(R[i - 1][key + "_s"], R[i - 1][key + "_u"]), front_xy(R[i][key + "_s"], R[i][key + "_u"])], fill=col(R[i]), width=wd)
        for r in R:
            x, y = side_xy(r["ank_f"], r["ank_u"])
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=col(r))
        marks = sorted({1, max(1, s - 13), max(1, s - 10), max(1, s - 7), int(peak["f"]), max(1, s - 1), s, min(n, s + act - 1), min(n, s + act + 6)}) if s else [1, n]
        for f_ in marks:
            r = F(f_)
            pts = [side_xy(r["hip_f"], r["hip_u"]), side_xy(r["knee_f"], r["knee_u"]), side_xy(r["ank_f"], r["ank_u"])]
            d.line(pts, fill=(250, 220, 110), width=2)
            d.text((pts[2][0] + 6, pts[2][1] - 8), str(f_), fill=(250, 220, 110), font=ft)
            d.line([side_xy(r["hip_f"], r["hip_u"]), side_xy(r["head_f"], r["head_u"])], fill=(120, 120, 120), width=1)
            pf = [front_xy(r["hip_s"], r["hip_u"]), front_xy(r["knee_s"], r["knee_u"]), front_xy(r["ank_s"], r["ank_u"])]
            d.line(pf, fill=(250, 220, 110), width=2)
        d.text((20, H - 40), "thick line = ankle path (grey startup, red active, blue recovery); yellow = the leg at numbered frames; thin grey = hip to head", fill=(200, 200, 200), font=ft)
        im.save(a.plot)
        print("  plot: " + a.plot)


if __name__ == "__main__":
    main()
