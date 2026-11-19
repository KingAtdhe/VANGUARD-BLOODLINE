"""Ryuen's banner texture for the Sanctuary, from scratch.

    python tools/art/make_banner.py [out.png]

Deep blue woven cloth, gold-thread border and hem, and Ryuen's emblem (a wave
breaking inside a ring). RGB = colour; alpha marks gold thread (the banner
shader makes it metallic and glossier).
"""
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/arenas/temple/ryuen_banner.png"
W, H = 256, 1024
rng = np.random.default_rng(3)
yy, xx = np.indices((H, W))
weave = (np.sin(xx * 1.9) * np.sin(yy * 1.9)) * 0.04 + rng.normal(0, 0.025, (H, W))
fade = 1 - 0.25 * (yy / H) ** 2                      # sun-faded / dirtier towards the hem
base = np.array([0.16, 0.24, 0.48])
rgb = np.clip(base[None, None, :] * (1 + weave[..., None]) * fade[..., None], 0, 1)
img = Image.fromarray((rgb * 255).astype(np.uint8), "RGB").convert("RGBA")
gold = Image.new("L", (W, H), 0)
gd = ImageDraw.Draw(gold)
gd.rectangle((10, 0, 22, H), fill=255)
gd.rectangle((W - 23, 0, W - 11, H), fill=255)
gd.rectangle((10, H - 70, W - 11, H - 58), fill=255)
for i in range(0, W - 20, 22):                        # tassel teeth on the hem
    gd.polygon([(10 + i, H - 58), (21 + i, H - 20), (32 + i, H - 58)], fill=255)
cx, cy, R = W // 2, int(H * 0.3), 82                  # emblem: ring + breaking wave
gd.ellipse((cx - R, cy - R, cx + R, cy + R), outline=255, width=13)
# the wave: a thick rising arc that curls over at the crest, with spray
gd.arc((cx - 58, cy - 30, cx + 42, cy + 70), start=180, end=320, fill=255, width=17)
gd.arc((cx + 2, cy - 26, cx + 42, cy + 14), start=200, end=470, fill=255, width=11)
gd.rectangle((cx - 60, cy + 20, cx + 60, cy + 30), fill=255)                  # the sea line
for k, (dx, dy, r) in enumerate(((50, -40, 6), (60, -24, 5), (40, -52, 4))):
    gd.ellipse((cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r), fill=255)
gold = gold.filter(ImageFilter.GaussianBlur(0.8))
g = np.asarray(gold, float)[..., None] / 255
gold_col = np.array([0.86, 0.64, 0.26]) * (0.9 + 0.1 * rng.random((H, W, 1)))
out = np.asarray(img, float)[..., :3] / 255 * (1 - g) + gold_col * g
res = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
res.putalpha(gold)
res.save(OUT)
print("saved", OUT)
