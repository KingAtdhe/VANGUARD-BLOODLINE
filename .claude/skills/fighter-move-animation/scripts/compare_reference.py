#!/usr/bin/env python3
"""The owner's reference picture next to the move's contact frame, before and now.

    python3 compare_reference.py --ref owner_picture.png --now /root/work/now_kick_frames --frame 9 \
        [--before /root/work/before_kick_frames] [--ref-flip] [--frames 5,9,13] --out /root/work/compare_kick.png

Top row, large: REFERENCE | BEFORE | NOW at the chosen frame (the contact
frame = the move's startup number). Use it to walk the pose brief line by
line: standing foot, knee, hips, striking limb, trunk, each arm, head, foot.

Bottom row: BEFORE and NOW at about the size the fighter has on a phone
screen. If you cannot tell them apart there, the owner will not see a change
either (D-115, D-116: correct changes that were too small to see).

--frames a,b,c adds a strip of several frames (wind-up, contact, recovery) of
before and now under each other, for the motion around the contact.
--ref-flip mirrors the reference left-right when the pictured fighter faces
left: our fighter faces right. Mirroring swaps nothing in SCREEN terms
(nearer / farther from the camera stays), which is why the brief is written
in screen terms.

--now / --before are frame folders written by frame_strip.py (0001.png ...).
Without --ref it is a plain before/now sheet. Needs Pillow."""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

# In a match the fighter is a little over half the screen height (measured on
# a fight_shot.gd render: ~57 %), which on a phone held sideways is 3.5-4 cm.
# On a review picture that is roughly a fighter this many pixels tall; the
# frames are rendered with the fighter at about half the frame height.
GAME_PX = 150
BIG = 560
BG = (24, 25, 28)


def font(px):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/opentype/inter/Inter-Bold.otf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def frame_of(folder, n):
    names = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
    if not names:
        sys.exit("no frames in " + folder)
    n = min(max(1, n), len(names))
    im = Image.open(os.path.join(folder, names[n - 1])).convert("RGB")
    return im.crop((im.width // 8, 0, im.width - im.width // 8, im.height))


def fit(im, h):
    return im.resize((max(1, int(im.width * h / float(im.height))), h), Image.LANCZOS)


def labelled(im, text, f):
    out = Image.new("RGB", (im.width, im.height + 30), BG)
    out.paste(im, (0, 30))
    ImageDraw.Draw(out).text((6, 5), text, fill=(235, 235, 235), font=f)
    return out


def row(cells, gap=10):
    h = max(c.height for c in cells)
    out = Image.new("RGB", (sum(c.width for c in cells) + gap * (len(cells) - 1), h), BG)
    x = 0
    for c in cells:
        out.paste(c, (x, 0))
        x += c.width + gap
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref")
    ap.add_argument("--ref-flip", action="store_true")
    ap.add_argument("--now", required=True)
    ap.add_argument("--before")
    ap.add_argument("--frame", type=int, required=True, help="1-based frame to compare (contact = startup number)")
    ap.add_argument("--frames", help="extra frames for a motion strip, e.g. 5,9,13")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    f = font(18)
    rows = []

    top = []
    if a.ref:
        ref = Image.open(a.ref).convert("RGB")
        if a.ref_flip:
            ref = ImageOps.mirror(ref)
        top.append(labelled(fit(ref, BIG), "REFERENCE" + (" (mirrored to face right)" if a.ref_flip else ""), f))
    if a.before:
        top.append(labelled(fit(frame_of(a.before, a.frame), BIG), "BEFORE  frame %d" % a.frame, f))
    top.append(labelled(fit(frame_of(a.now, a.frame), BIG), "NOW  frame %d" % a.frame, f))
    rows.append(row(top))

    small = []
    if a.before:
        small.append(labelled(fit(frame_of(a.before, a.frame), GAME_PX * 2), "BEFORE, phone size", f))
    small.append(labelled(fit(frame_of(a.now, a.frame), GAME_PX * 2), "NOW, phone size", f))
    rows.append(row(small))

    if a.frames:
        picks = [int(x) for x in a.frames.split(",") if x.strip()]
        for name, folder in (("BEFORE", a.before), ("NOW", a.now)):
            if folder:
                rows.append(row([labelled(fit(frame_of(folder, n), 300), "%s  %d" % (name, n), f) for n in picks]))

    w = max(r.width for r in rows)
    sheet = Image.new("RGB", (w, sum(r.height for r in rows) + 14 * (len(rows) - 1)), BG)
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 14
    sheet.save(a.out)
    print("wrote %s (%dx%d)" % (a.out, sheet.width, sheet.height))
    print("Now check the brief line by line on the top row, then the phone-size row: is the change visible there?")


if __name__ == "__main__":
    main()
