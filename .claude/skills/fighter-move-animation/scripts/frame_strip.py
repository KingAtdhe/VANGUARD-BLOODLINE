#!/usr/bin/env python3
"""Every frame of one clip, in the game's side view, as one picture to read.

    python3 frame_strip.py <fighter> <CLIP_SUFFIX> <out.png>
    python3 frame_strip.py kairo KICK_LOW_01 /root/work/now_kick.png
    python3 frame_strip.py kairo SPECIAL_RIFT_BREAK out.png --from 14 --to 30 --cell 420
    python3 frame_strip.py kairo KICK_LOW_01 out.png --frames-dir /root/work/before_kick_frames   (no render: tile kept frames)

Renders the clip with tools/godot/clip_frames.gd (the same frames the review
video is made of: P1 facing right, camera at the side) and tiles them in
reading order. Each cell carries its frame number (1-based, as in the move's
frame data) and a coloured bar: grey = startup, red = active (the hitbox is
out), blue = recovery. The first active frame is the contact pose.

The single frames are kept in <out>_frames/ (0001.png ...), for
compare_reference.py and for a later before/now comparison: render the strip
BEFORE you rebuild and the frames of the old move stay there.

Why every frame: six sampled frames hid invisible wind-ups, an eleven-frame
standstill and a soft jab (D-085, D-086). Why the side view: it is what the
player sees; a three-quarter view flatters (D-109).

Needs xvfb-run, godot, Pillow. Run from inside the repository. Phases come
from $WORK/moves_<fighter>.json when it exists (build_fighter.sh writes it);
without it the strip is unmarked."""
import argparse
import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

PHASE = {"startup": (150, 150, 150), "active": (230, 60, 50), "recovery": (70, 130, 230), "": (90, 90, 90)}


def font(px):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/opentype/inter/Inter-Bold.otf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def timing(fighter, suffix):
    """(startup, active, recovery) of the move that plays this clip, or None."""
    path = os.path.join(os.environ.get("WORK", "/root/work"), "moves_%s.json" % fighter)
    if not os.path.exists(path):
        return None
    for v in json.load(open(path)).values():
        if isinstance(v, dict) and str(v.get("animation", "")).upper().endswith("_" + suffix.upper()):
            return int(v["startup"]), int(v["active"]), int(v["recovery"])
    return None


def phase_of(frame, tm):
    if not tm:
        return ""
    s, a, _r = tm
    return "startup" if frame < s else ("active" if frame < s + a else "recovery")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fighter")
    ap.add_argument("clip")
    ap.add_argument("out")
    ap.add_argument("--frames-dir", help="tile frames that are already rendered (0001.png ...) instead of rendering")
    ap.add_argument("--from", dest="first", type=int, default=1)
    ap.add_argument("--to", dest="last", type=int, default=0)
    ap.add_argument("--cell", type=int, default=300, help="cell height in pixels")
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--render", type=int, default=560, help="render size of each frame")
    a = ap.parse_args()

    frames_dir = a.frames_dir or os.path.splitext(a.out)[0] + "_frames"
    if not a.frames_dir:
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
        tmp = frames_dir + "_tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        r = subprocess.run(["xvfb-run", "-a", "godot", "--path", root, "--rendering-driver", "opengl3", "--script",
                            "res://tools/godot/clip_frames.gd", "--", a.fighter, tmp, a.clip, str(a.render)],
                           capture_output=True, text=True)
        got = os.path.join(tmp, a.clip)
        if not os.path.isdir(got) or not os.listdir(got):
            sys.exit("no frames rendered for %s %s. Is the clip name right (suffix after the fighter's name, e.g. "
                     "KICK_LOW_01, SPECIAL_RIFT_BREAK, JUMP_ATTACK) and the project imported?\n%s"
                     % (a.fighter, a.clip, (r.stdout + r.stderr)[-1500:]))
        shutil.rmtree(frames_dir, ignore_errors=True)
        shutil.move(got, frames_dir)
        shutil.rmtree(tmp, ignore_errors=True)

    names = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    if not names:
        sys.exit("no frames in " + frames_dir)
    last = a.last or len(names)
    picked = [(i + 1, n) for i, n in enumerate(names) if a.first <= i + 1 <= last]
    tm = timing(a.fighter, a.clip)

    sample = Image.open(os.path.join(frames_dir, picked[0][1]))
    crop = (sample.width // 8, 0, sample.width - sample.width // 8, sample.height)   # the fighter stays inside this
    cw = int(a.cell * (crop[2] - crop[0]) / float(crop[3] - crop[1]))
    cols = min(a.cols, len(picked))
    rows = (len(picked) + cols - 1) // cols
    bar, head = 10, 34
    sheet = Image.new("RGB", (cols * cw, head + rows * (a.cell + bar)), (24, 25, 28))
    d = ImageDraw.Draw(sheet)
    f_num, f_head = font(max(16, a.cell // 14)), font(18)
    title = "%s %s   frames %d-%d of %d" % (a.fighter, a.clip, picked[0][0], picked[-1][0], len(names))
    if tm:
        title += "   startup %d / active %d / recovery %d   contact = frame %d   grey startup, red active, blue recovery" % (
            tm[0], tm[1], tm[2], tm[0])
    d.text((8, 7), title, fill=(235, 235, 235), font=f_head)
    for k, (frame, name) in enumerate(picked):
        im = Image.open(os.path.join(frames_dir, name)).convert("RGB").crop(crop).resize((cw, a.cell), Image.LANCZOS)
        x, y = (k % cols) * cw, head + (k // cols) * (a.cell + bar)
        sheet.paste(im, (x, y))
        ph = phase_of(frame, tm)
        d.rectangle([x, y + a.cell, x + cw - 2, y + a.cell + bar - 2], fill=PHASE[ph])
        label = str(frame) + ("  CONTACT" if tm and frame == tm[0] else "")
        d.text((x + 7, y + 5), label, fill=(255, 235, 120) if ph == "active" else (255, 255, 255), font=f_num,
               stroke_width=2, stroke_fill=(0, 0, 0))
    sheet.save(a.out)
    print("wrote %s  (%d frames, %dx%d). Single frames kept in %s" % (a.out, len(picked), sheet.width, sheet.height, frames_dir))
    if sheet.height > 2400:
        print("tall sheet: read it in parts with --from/--to (e.g. the startup, then active+recovery) so each cell stays large")


if __name__ == "__main__":
    main()
