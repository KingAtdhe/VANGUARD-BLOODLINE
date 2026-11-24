#!/usr/bin/env python3
"""Textures for hit, block and knockdown effects (D-102), white so the game
tints them: an impact star, a shockwave ring, a spark streak, a soft glow,
a smoke puff and debris chunks, plus a white slash arc taken from the
owner's flame sheet (its brightness only). Generated from scratch except the
arc.   python3 tools/art/make_impact_textures.py"""
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

OUT = "assets/vfx/impact/"
rng = np.random.default_rng(7)
N = 256
y, x = np.mgrid[0:N, 0:N]
cx = cy = (N - 1) / 2
dx, dy = x - cx, y - cy
r = np.sqrt(dx * dx + dy * dy) / (N / 2)
ang = np.arctan2(dy, dx)


def save(a, name, rgb=(255, 255, 255)):
    a = np.clip(a, 0, 1)
    img = np.dstack([np.full_like(a, rgb[0]), np.full_like(a, rgb[1]), np.full_like(a, rgb[2]), a * 255]).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(OUT + name)


# impact star: a hot core, a soft glow and 12 uneven rays
core = np.exp(-(r / 0.10) ** 2)
glow = np.exp(-(r / 0.35) ** 2) * 0.55
rays = np.zeros_like(r)
for k in range(12):
    a0 = k * 2 * np.pi / 12 + rng.uniform(-0.15, 0.15)
    length = rng.uniform(0.55, 1.0)
    width = rng.uniform(0.035, 0.07)
    d = np.angle(np.exp(1j * (ang - a0)))
    rays += np.exp(-(d / (width * (1.2 - r))) ** 2) * np.clip(1 - r / length, 0, 1) ** 1.3
save(core + glow + rays * 0.9, "impact_star.png")
# shockwave ring
save(np.exp(-((r - 0.78) / 0.07) ** 2) * (0.7 + 0.3 * np.cos(ang * 9 + rng.uniform(0, 6))) + np.exp(-((r - 0.78) / 0.02) ** 2) * 0.5,
     "shock_ring.png")
# soft glow dot
save(np.exp(-(r / 0.45) ** 2), "glow.png")
# spark streak: 32 x 256, hot head, fading tail
sx, sy = np.mgrid[0:256, 0:32][1], np.mgrid[0:256, 0:32][0]
w = np.exp(-((sx - 15.5) / 5.0) ** 2)
head = np.clip(1 - sy / 255.0, 0, 1) ** 0.6
save(w * head * np.clip(sy / 30.0, 0, 1), "spark.png")
# smoke puff: lumpy noise inside a soft disc
noise = ndimage.gaussian_filter(rng.random((N, N)), 9)
noise = (noise - noise.min()) / (noise.max() - noise.min())
noise2 = ndimage.gaussian_filter(rng.random((N, N)), 3)
noise2 = (noise2 - noise2.min()) / (noise2.max() - noise2.min())
puff = np.clip(1 - r ** 1.6, 0, 1) * (0.45 + 0.55 * noise) * (0.8 + 0.2 * noise2)
save(np.clip(puff * 1.25, 0, 1), "smoke.png")
# debris: four rock chunks in a 2x2 atlas (white; tinted dark in the game)
deb = np.zeros((N, N))
for i in range(4):
    ox, oy = (i % 2) * 128 + 64, (i // 2) * 128 + 64
    pts = 7
    angs = np.sort(rng.uniform(0, 2 * np.pi, pts))
    rad = rng.uniform(28, 52, pts)
    from PIL import ImageDraw
    im = Image.new("L", (N, N))
    ImageDraw.Draw(im).polygon([(ox + rr * np.cos(a), oy + rr * np.sin(a)) for a, rr in zip(angs, rad)], fill=255)
    deb = np.maximum(deb, np.array(im) / 255.0)
deb = ndimage.gaussian_filter(deb, 1.0)
save(deb, "debris.png")
# slash arc from the owner's flame sheet (row 2, first arc): brightness only
sheet = np.array(Image.open("assets/vfx/fire/_source/owner_red_flame_sheet.png").convert("RGB")).astype(float)
arc = sheet[300:510, 20:400].max(2) / 255.0
arc = np.clip(arc - 0.06, 0, 1) ** 1.6
img = Image.fromarray((arc * 255).astype(np.uint8)).resize((384, 212), Image.LANCZOS)
a = np.array(img) / 255.0
save(a, "slash.png")
print("impact textures in", OUT)
