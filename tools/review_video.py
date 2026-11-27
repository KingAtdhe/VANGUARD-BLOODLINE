#!/usr/bin/env python3
"""Real-speed review video of a fighter's animations (D-091).

The owner judges motion from video; contact sheets only show poses. This
renders every frame of the chosen clips with tools/godot/clip_frames.gd and
joins them at 60 frames per second, each clip named on screen and separated
by a moment of the stance.

    python3 tools/review_video.py kairo /tmp/kairo_review.mp4
    python3 tools/review_video.py kairo out.mp4 --clips IDLE_A:2 ATTACK_HEAVY_01

A clip is SUFFIX or SUFFIX:repeats (loops). Needs xvfb-run, godot, ffmpeg
and Pillow. Run from the project root."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

DEFAULT = {
    "kairo": ["IDLE_A:3", "WALK_FORWARD:2", "WALK_BACKWARD:2", "DASH_FORWARD", "DASH_BACK", "CROUCH_TRANSITION", "JUMP",
              "JUMP_ATTACK", "BLOCK_HIGH", "BLOCK_LOW", "ATTACK_LIGHT_01", "ATTACK_STRING_CROSS_01", "ATTACK_HEAVY_01", "KICK_LOW_01",
              "ATTACK_BODY_HOOK_01", "ATTACK_RISING_UPPERCUT_01", "KICK_SWEEP_01", "THROW_KNEE_01",
              "SPECIAL_ORIGIN_PALM", "SPECIAL_FIREBALL", "SPECIAL_RIFT_BREAK", "SPECIAL_SLIP_COUNTER",
              "ATTACK_COUNTER_HOOK_01", "ULTIMATE_ORIGIN_BREAK", "HIT_LIGHT", "HIT_BODY", "KNOCKDOWN", "GETUP"],
}
TITLES = {"IDLE_A": "Stance", "CROUCH_TRANSITION": "Crouch (down and up)", "ATTACK_LIGHT_01": "Light", "ATTACK_HEAVY_01": "Heavy", "KICK_LOW_01": "Kick",
          "ATTACK_BODY_HOOK_01": "Down + heavy", "SPECIAL_ORIGIN_PALM": "Special", "SPECIAL_RIFT_BREAK": "Forward + special",
          "SPECIAL_SLIP_COUNTER": "Back + special (counter stance)", "ATTACK_COUNTER_HOOK_01": "Counter strike",
          "ULTIMATE_ORIGIN_BREAK": "Ultimate", "ATTACK_STRING_CROSS_01": "Light, light (one-two)",
          "ATTACK_RISING_UPPERCUT_01": "Down + light (uppercut)", "KICK_SWEEP_01": "Down + kick (sweep)",
          "THROW_KNEE_01": "Light + kick (throw)", "SPECIAL_FIREBALL": "Down + special (fireball)", "JUMP_ATTACK": "Attack in the air"}


def hit_freezes(fighter):
    """{clip suffix: {frame (1-based): frames held}} from data/moves (D-133): on a
    hit the game freezes both fighters for the move's hitstop; a whiff shows none.
    The video shows each strike as it looks when it connects."""
    import glob
    import re
    out = {}
    tok = fighter.upper() + "_"
    for path in glob.glob("data/moves/%s_*.tres" % fighter):
        txt = open(path).read()
        an = re.search(r'animation = &"([^"]+)"', txt)
        if not an or not an.group(1).startswith(tok):
            continue
        def num(key, d=0):
            m = re.search(r"^%s = (-?\d+)" % key, txt, re.M)
            return int(m.group(1)) if m else d
        st, ac, hs = num("startup_frames"), num("active_frames", 1), num("hitstop_frames")
        if st <= 0 or hs <= 0:
            continue
        hits = {st: hs}
        rh, rhs = num("rehit_interval"), num("rehit_hitstop_frames", hs)
        if rh > 0:
            f = st + rh
            while f < st + ac:
                hits[f] = rhs
                f += rh
        out[an.group(1)[len(tok):]] = hits
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fighter")
    ap.add_argument("out")
    ap.add_argument("--clips", nargs="*")
    ap.add_argument("--size", type=int, default=560)
    ap.add_argument("--gap", type=int, default=24, help="stance frames between clips")
    ap.add_argument("--no-hitstop", action="store_true", help="do not hold the contact frames (a whiff)")
    a = ap.parse_args()
    clips = a.clips or DEFAULT.get(a.fighter) or ["IDLE_A:3"]
    pairs = [(c.split(":")[0], int(c.split(":")[1]) if ":" in c else 1) for c in clips]
    names = sorted({n for n, _ in pairs} | {"IDLE_A"})
    freezes = hit_freezes(a.fighter)
    work = tempfile.mkdtemp(prefix="review_")
    try:
        r = subprocess.run(["xvfb-run", "-a", "godot", "--path", ".", "--rendering-driver", "opengl3", "--script",
                            "res://tools/godot/clip_frames.gd", "--", a.fighter, work, ",".join(names), str(a.size)],
                           capture_output=True, text=True)
        got = {n: sorted(os.listdir(os.path.join(work, n))) for n in names if os.path.isdir(os.path.join(work, n))}
        if "IDLE_A" not in got:
            sys.exit("no frames rendered:\n" + r.stdout[-2000:] + r.stderr[-2000:])
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
        seq = os.path.join(work, "seq")
        os.makedirs(seq)
        n_out = 0
        crop = (a.size // 8, 0, a.size - a.size // 8, a.size)

        def put(name, fname, label):
            nonlocal n_out
            im = Image.open(os.path.join(work, name, fname)).convert("RGB").crop(crop)
            ImageDraw.Draw(im).text((12, 10), label, fill=(255, 255, 255), font=font)
            n_out += 1
            im.save(os.path.join(seq, "%05d.png" % n_out))

        for name, reps in pairs:
            if name not in got:
                print("missing", name)
                continue
            label = TITLES.get(name, name.replace("_", " ").title())
            holds = {} if a.no_hitstop else freezes.get(name, {})
            for _ in range(reps):
                for i, f in enumerate(got[name]):
                    put(name, f, label)
                    for _h in range(holds.get(i + 1, 0)):
                        put(name, f, label + "  (hit freeze)")
            if name != "IDLE_A":
                for f in got["IDLE_A"][:a.gap]:
                    put("IDLE_A", f, "")
        w = (crop[2] - crop[0]) // 2 * 2
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "60", "-i", os.path.join(seq, "%05d.png"),
                        "-vf", "crop=%d:%d:0:0" % (w, a.size // 2 * 2), "-pix_fmt", "yuv420p", "-c:v", "libx264",
                        "-crf", "21", a.out], check=True)
        print("wrote %s: %d frames, %.1f s" % (a.out, n_out, n_out / 60.0))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
