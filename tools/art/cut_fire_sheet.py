#!/usr/bin/env python3
"""Cuts the owner's red flame sheet (assets/vfx/fire/_source/
owner_red_flame_sheet.png, supplied 2026-11-24) into the fire textures the
game uses (D-101): a 6-frame flame flipbook (the six flames of the top row,
each on its own bottom-aligned 256 px cell), the fireball, streak, burst,
sparks, pillar and ring, plus a soft ember dot. Alpha comes from brightness
(the sheet is on black; the game also draws them additively).

    python3 tools/art/cut_fire_sheet.py [sheet.png] [out_dir]

Needs numpy, scipy and Pillow."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = sys.argv[1] if len(sys.argv) > 1 else "assets/vfx/fire/_source/owner_red_flame_sheet.png"
OUT = (sys.argv[2] if len(sys.argv) > 2 else "assets/vfx/fire") + "/"

im = np.array(Image.open(SRC).convert("RGB")).astype(float)
lum = im.max(2)
lab, _ = ndimage.label(ndimage.binary_dilation(lum > 40, iterations=12))


def cut(y0, x0, y1, x1, keep_brightest=False):
    sub = im[y0:y1, x0:x1].copy()
    if keep_brightest:                      # only the effect the box is about, not a neighbour's edge
        yy, xx = np.unravel_index(np.argmax(lum[y0:y1, x0:x1]), (y1 - y0, x1 - x0))
        sub *= (lab[y0:y1, x0:x1] == lab[y0 + yy, x0 + xx])[..., None]
    return sub


def fit(sub, size=256, anchor="bottom", pad=6):
    h, w = sub.shape[:2]
    s = min((size - 2 * pad) / w, (size - 2 * pad) / h)
    img = Image.fromarray(sub.clip(0, 255).astype(np.uint8)).resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    cell = Image.new("RGB", (size, size))
    y = size - pad - img.height if anchor == "bottom" else (size - img.height) // 2
    cell.paste(img, ((size - img.width) // 2, y))
    return cell


def rgba(cell, gain=1.3):
    a = np.array(cell).astype(float)
    return Image.fromarray(np.dstack([a, (a.max(2) / 255 * gain).clip(0, 1) * 255]).astype(np.uint8), "RGBA")


# the six flames of the top row (pixel boxes found by connected components)
flames = [(15, 1, 293, 224, True), (14, 211, 292, 419, True), (23, 418, 289, 607, True),
          (26, 596, 291, 857, True), (14, 814, 292, 1083, True), (47, 1075, 292, 1236, False)]
atlas = Image.new("RGBA", (256 * 6, 256))
for i, (y0, x0, y1, x1, k) in enumerate(flames):
    atlas.paste(rgba(fit(cut(y0, x0, y1, x1, k))), (i * 256, 0))
atlas.save(OUT + "flame_flipbook.png")
fb = cut(783, 0, 980, 335)
fb[:, :8] = 0
rgba(fit(fb, anchor="center", pad=4), 1.2).save(OUT + "fireball.png")
rgba(fit(cut(830, 330, 940, 570), anchor="center", pad=4)).save(OUT + "streak.png")
rgba(fit(cut(520, 10, 775, 300), anchor="center", pad=4)).save(OUT + "burst.png")
rgba(fit(cut(798, 1272, 988, 1519), anchor="center", pad=4), 1.6).save(OUT + "sparks.png")
rgba(fit(cut(505, 935, 770, 1145), pad=4)).save(OUT + "pillar.png")
rgba(fit(cut(11, 1240, 294, 1518), anchor="center", pad=4)).save(OUT + "ring.png")
y, x = np.mgrid[0:64, 0:64]
a = np.clip(1 - np.sqrt((x - 31.5) ** 2 + (y - 31.5) ** 2) / 31.5, 0, 1) ** 2
Image.fromarray(np.dstack([np.full((64, 64), 255), 140 * a ** 0.5, 60 * a, a * 255]).astype(np.uint8), "RGBA").save(OUT + "ember.png")
print("fire textures in", OUT)
