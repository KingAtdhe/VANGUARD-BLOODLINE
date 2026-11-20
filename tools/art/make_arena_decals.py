"""Decal and backdrop-layer textures for the arenas, generated from scratch.

    python tools/art/make_arena_decals.py [out_dir]   (default assets/arenas/decals)

RGBA PNGs: crack, scorch, stain, leaves, glyph paint (invented script, no real
letters), glowing crack (with a separate emission map), a tileable soft cloud
band and a tileable dust haze for scrolling backdrop layers.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/arenas/decals"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(9)


def fnoise(seed, lo, hi, n=512, m=None):
    r = np.random.default_rng(seed)
    m = m or n
    f = np.fft.fft2(r.standard_normal((m, n)))
    ky = np.fft.fftfreq(m)[:, None] * m
    kx = np.fft.fftfreq(n)[None, :] * n
    rad = np.sqrt(kx ** 2 + ky ** 2)
    mask = ((rad >= lo) & (rad <= hi)).astype(float)
    o = np.real(np.fft.ifft2(f * mask))
    o -= o.min()
    return o / max(1e-9, o.max())


def save(name, rgb, a):
    img = np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)])
    Image.fromarray((img * 255).astype(np.uint8), "RGBA").save(f"{OUT}/{name}.png")
    print("saved", name)


def crack_lines(seed, n=512, branches=7, width=3):
    r = np.random.default_rng(seed)
    im = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(im)
    def grow(x, y, ang, length, w, depth):
        for _ in range(int(length)):
            nx, ny = x + math.cos(ang) * 6, y + math.sin(ang) * 6
            d.line((x, y, nx, ny), fill=255, width=max(1, int(w)))
            x, y = nx, ny
            ang += r.uniform(-0.35, 0.35)
            w *= 0.985
            if depth < 3 and r.random() < 0.05:
                grow(x, y, ang + r.choice((-1, 1)) * r.uniform(0.5, 1.1), length * 0.5, w * 0.7, depth + 1)
            if not (0 < x < n and 0 < y < n):
                break
    for b in range(branches):
        a = 2 * math.pi * b / branches + r.uniform(-0.3, 0.3)
        grow(n / 2, n / 2, a, r.uniform(18, 38), width + 2, 0)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(0.8)), float) / 255


# cracks: dark lines with a faint darker halo
c = crack_lines(1)
halo = np.asarray(Image.fromarray((c * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), float) / 255
save("crack", np.zeros((512, 512, 3)) + 0.02, np.clip(c * 0.95 + halo * 0.35, 0, 1))
# glowing crack: same shape, albedo dark, emission hot core
g = crack_lines(2, width=4)
gh = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(8)), float) / 255
save("crack_glow", np.zeros((512, 512, 3)) + 0.03, np.clip(g + gh * 0.5, 0, 1))
em = np.dstack([np.clip(g * 1.0 + gh * 0.6, 0, 1), np.clip(g * 0.25 + gh * 0.05, 0, 1), np.clip(g * 0.08, 0, 1)])
Image.fromarray((np.clip(em, 0, 1) * 255).astype(np.uint8), "RGB").save(f"{OUT}/crack_glow_emission.png")
# scorch: radial burn, ragged edge
yy, xx = (np.indices((512, 512)) - 256) / 256
rad = np.sqrt(xx ** 2 + yy ** 2)
edge = 0.75 + 0.25 * (fnoise(3, 3, 12) - 0.5) * 2
a = np.clip((edge - rad) / 0.35, 0, 1) ** 1.3 * (0.75 + 0.25 * fnoise(4, 20, 60))
rgb = np.dstack([0.05 + 0.15 * np.clip(rad - 0.5, 0, 1)] * 3) * np.array([1.0, 0.8, 0.6])
save("scorch", rgb, a)
# stain: irregular grime/water stain
blob = fnoise(5, 2, 6)
a = np.clip((blob - 0.55) * 4, 0, 1) * np.clip(1.1 - rad, 0, 1) * (0.6 + 0.4 * fnoise(6, 30, 80))
save("stain", np.zeros((512, 512, 3)) + np.array([0.06, 0.05, 0.035]), a * 0.85)
# leaves: scattered small leaves
im = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
for i in range(70):
    cx, cy = rng.uniform(40, 472), rng.uniform(40, 472)
    if math.hypot(cx - 256, cy - 256) > 230:
        continue
    s, ang = rng.uniform(8, 16), rng.uniform(0, math.pi)
    col = tuple(int(v) for v in rng.choice([(150, 55, 15), (175, 105, 25), (120, 40, 20), (95, 85, 30)])) + (255,)
    pts = [(cx + math.cos(ang + t) * s * (1 if k % 2 == 0 else 0.45), cy + math.sin(ang + t) * s * (1 if k % 2 == 0 else 0.45))
           for k, t in enumerate([0, math.pi / 2, math.pi, 3 * math.pi / 2])]
    d.polygon(pts, fill=col)
im.save(f"{OUT}/leaves.png")
print("saved leaves")
# glyph paint: invented-script strokes, sprayed white with drips
im = Image.new("L", (512, 512), 0)
d = ImageDraw.Draw(im)
x = 60
for k in range(4):
    for s in range(rng.integers(2, 4)):
        if rng.random() < 0.5:
            y = rng.integers(170, 320)
            d.line((x, y, x + rng.integers(30, 70), y), fill=255, width=16)
        else:
            xx0 = x + rng.integers(0, 40)
            d.line((xx0, 160, xx0, 340), fill=255, width=16)
            d.line((xx0, 340, xx0 + rng.integers(-2, 3), 340 + rng.integers(20, 80)), fill=200, width=5)   # drip
    x += 105
gl = np.asarray(im.filter(ImageFilter.GaussianBlur(1.5)), float) / 255 * (0.7 + 0.3 * fnoise(7, 40, 120))
save("glyph_paint", np.zeros((512, 512, 3)) + np.array([0.85, 0.85, 0.8]), gl * 0.9)
# tileable cloud band (wide), alpha soft, for a scrolling layer
cl = fnoise(8, 2, 10, n=1024, m=256) * 0.7 + fnoise(9, 10, 30, n=1024, m=256) * 0.3
v = np.linspace(0, 1, 256)[:, None]
band = np.clip(np.sin(v * math.pi) ** 1.5, 0, 1)
a = np.clip((cl - 0.42) * 2.6, 0, 1) * band
rgb = np.dstack([np.ones((256, 1024)) * 1.0, 0.92 + 0.08 * cl, 0.86 + 0.1 * cl])
save("cloud_band", rgb, a)
# tileable dust haze
hz = fnoise(10, 2, 8, n=512, m=256)
save("dust_haze", np.dstack([np.ones((256, 512))] * 3) * np.array([0.8, 0.65, 0.5]), np.clip((hz - 0.3) * 1.2, 0, 1) * band * 0.6)
