"""Generates the tileable surface textures shared by all arenas, from scratch.

    python tools/art/make_arena_textures.py [out_dir]   (default assets/arenas/textures)

Everything is procedural (numpy): periodic FFT noise and periodic Voronoi,
so every texture tiles seamlessly. Each surface gets three 512 px maps:
<name>_albedo.png (sRGB, authored around 0.6-0.7 brightness so the arena
material colour can tint it), <name>_normal.png (OpenGL convention, +Y up)
and <name>_rough.png (greyscale roughness). Deterministic per seed.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

N = 512
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/arenas/textures"


def fnoise(seed, lo, hi, n=N):
    """Periodic band-limited noise in 0..1; lo/hi in cycles per tile."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    ky = np.fft.fftfreq(n)[:, None] * n
    kx = np.fft.fftfreq(n)[None, :] * n
    r = np.sqrt(kx ** 2 + ky ** 2)
    mask = np.clip((r - lo) / max(1e-6, lo * 0.3), 0, 1) * np.clip((hi - r) / max(1e-6, hi * 0.3), 0, 1)
    out = np.real(np.fft.ifft2(f * mask))
    out -= out.min()
    return out / max(1e-9, out.max())


def fbm(seed, base=2, octaves=6, n=N):
    acc, amp, tot = np.zeros((n, n)), 1.0, 0.0
    for o in range(octaves):
        f0 = base * 2 ** o
        acc += amp * fnoise(seed + o * 17, f0, f0 * 2, n)
        tot += amp
        amp *= 0.55
    return acc / tot


def voronoi(seed, cells, n=N, jitter=1.0):
    """Periodic Voronoi: returns (F1, F2, cell id) on the unit tile."""
    rng = np.random.default_rng(seed)
    pts = rng.random((cells, 2))
    tree = cKDTree(pts, boxsize=1.0)
    g = (np.indices((n, n)).reshape(2, -1).T + 0.5) / n
    d, i = tree.query(g, k=2)
    return d[:, 0].reshape(n, n), d[:, 1].reshape(n, n), i[:, 0].reshape(n, n)


def normal_from_height(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    nz = np.ones_like(h)
    n = np.stack([-dx, dy, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def lerp(a, b, t):
    return a + (b - a) * t[..., None] if np.ndim(t) == 2 and np.ndim(a) else a + (b - a) * t


def col(c):
    return np.array(c, float)[None, None, :]


def save(name, albedo, height, rough, nstrength=6.0):
    os.makedirs(OUT, exist_ok=True)
    a = np.clip(albedo, 0, 1) ** (1 / 2.2)
    Image.fromarray((a * 255).astype(np.uint8)).save(f"{OUT}/{name}_albedo.png")
    nm = normal_from_height(height, nstrength)
    Image.fromarray((np.clip(nm, 0, 1) * 255).astype(np.uint8)).save(f"{OUT}/{name}_normal.png")
    Image.fromarray((np.clip(rough, 0, 1) * 255).astype(np.uint8), "L").save(f"{OUT}/{name}_rough.png")
    print(f"{name}: mean albedo {np.clip(albedo, 0, 1).reshape(-1, 3).mean(0).round(3)}")


def m(x):
    """Stack a greyscale map into RGB."""
    return np.repeat(x[..., None], 3, -1)


# ----------------------------------------------------------------- surfaces --
def stone():
    """Weathered cut stone: grain, darker stains, hairline cracks, pitting."""
    grain = fbm(1, 8, 5)
    stain = fnoise(2, 1, 3)
    f1, f2, _ = voronoi(3, 9)
    crack = np.clip(1 - (f2 - f1) / 0.006, 0, 1) * (fnoise(4, 2, 5) > 0.55)
    pits = (fnoise(5, 60, 120) > 0.82).astype(float)
    v = 0.62 + 0.18 * (grain - 0.5) - 0.18 * np.clip(stain - 0.55, 0, 1) * 3 - 0.35 * crack - 0.12 * pits
    alb = m(v) * col((1.0, 0.97, 0.93))
    h = grain * 0.6 - crack * 0.8 - pits * 0.3
    save("stone", alb, h, 0.8 + 0.15 * grain - 0.2 * np.clip(stain - 0.6, 0, 1) * 3, 5)


def rock_strata():
    """Quarry face: horizontal sediment bands, warped, with chisel/blast marks."""
    y = np.indices((N, N))[0] / N
    warp = fnoise(10, 1, 3) * 0.08
    bands = np.sin((y + warp) * 2 * np.pi * 7) * 0.5 + 0.5
    fine = np.sin((y + warp * 1.7) * 2 * np.pi * 31) * 0.5 + 0.5
    grain = fbm(11, 6, 5)
    c1, c2, c3 = col((0.6, 0.5, 0.41)), col((0.44, 0.36, 0.29)), col((0.6, 0.59, 0.57))
    alb = c1 + (c2 - c1) * m(bands) + (c3 - c1) * m(np.clip(fine - 0.75, 0, 1) * 2.5)
    alb *= m(0.8 + 0.35 * (grain - 0.5))
    f1, f2, _ = voronoi(12, 30)
    crack = np.clip(1 - (f2 - f1) / 0.005, 0, 1) * (fnoise(13, 2, 6) > 0.5)
    alb *= m(1 - 0.3 * crack)
    h = bands * 0.4 + grain * 0.6 - crack
    save("rock_strata", alb * 0.9, h, 0.9 - 0.05 * grain, 7)


def concrete_wet():
    """Roof concrete in the rain: pores, tar patches, and wet (glossy) pools."""
    grain = fbm(20, 10, 5)
    pores = (fnoise(21, 80, 160) > 0.8).astype(float)
    tar = np.clip((fbm(22, 4, 5) - 0.66) * 8, 0, 1)
    wet = np.clip((fnoise(23, 1, 4) - 0.45) * 4, 0, 1)
    v = 0.6 + 0.15 * (grain - 0.5) - 0.12 * pores - 0.18 * tar - 0.12 * wet
    alb = m(v) * col((0.95, 0.97, 1.0))
    rough = np.clip(0.75 - 0.6 * wet - 0.2 * tar + 0.1 * grain, 0.05, 1)
    save("concrete_wet", alb, grain * 0.5 - pores * 0.3, rough, 4)


def paint_rust(name, paint, seed):
    """Industrial paint over steel: chips, rust bleeding down, grime streaks."""
    chip = fbm(seed, 3, 6)
    rust_mask = np.clip((chip - 0.72) * 6, 0, 1) * 0.85
    y = np.indices((N, N))[0]
    streak = fnoise(seed + 1, 1, 2)[:, :1] * 0  # placeholder for shape
    vert = np.zeros((N, N))
    rng = np.random.default_rng(seed + 2)
    for _ in range(40):                               # rust/grime runs downward (image +y is down)
        x0, y0 = rng.integers(0, N), rng.integers(0, N)
        w, ln = rng.integers(2, 8), rng.integers(40, 220)
        rows = (np.arange(ln) + y0) % N
        fade = np.linspace(1, 0, ln)[:, None]
        cols = (np.arange(w) + x0) % N
        vert[np.ix_(rows, cols)] = np.maximum(vert[np.ix_(rows, cols)], fade * rng.uniform(0.3, 0.8))
    grime = fbm(seed + 3, 3, 5)
    base = col(paint) * m(0.9 + 0.2 * (grime - 0.5))
    rust = col((0.36, 0.14, 0.05)) * m(0.8 + 0.4 * fnoise(seed + 4, 20, 60))
    alb = base + (rust - base) * m(rust_mask)
    alb = alb + (col((0.3, 0.15, 0.07)) - alb) * m(vert * 0.6)
    alb *= m(1 - 0.25 * np.clip(grime - 0.6, 0, 1) * 3)
    h = (1 - rust_mask) * 0.5 + fnoise(seed + 5, 30, 90) * 0.2 * rust_mask
    save(name, alb, h, np.clip(0.55 + 0.4 * rust_mask + 0.1 * grime, 0, 1), 5)
    del streak, y


def metal_dark():
    """Dark steel: brushed direction, scratches, worn edges."""
    brush = fnoise(30, 1, 3)
    x = np.indices((N, N))[1] / N
    lines = fnoise(31, 2, 4)[:1, :].repeat(N, 0) * 0.3 + fnoise(32, 80, 200) * 0.2
    rng = np.random.default_rng(33)
    scr = np.zeros((N, N))
    for _ in range(120):
        x0, y0, ln = rng.integers(0, N), rng.integers(0, N), rng.integers(10, 80)
        ang = rng.uniform(0, np.pi)
        t = np.arange(ln)
        xs = ((x0 + t * np.cos(ang)).astype(int)) % N
        ys = ((y0 + t * np.sin(ang)).astype(int)) % N
        scr[ys, xs] = 1
    v = 0.55 + 0.15 * (brush - 0.5) + 0.1 * lines + 0.25 * scr
    save("metal_dark", m(v) * col((0.95, 0.97, 1.0)), lines * 0.3 - scr * 0.2, np.clip(0.45 + 0.2 * brush - 0.2 * scr, 0, 1), 3)
    del x


def gravel():
    f1, f2, cid = voronoi(40, 900)
    rng = np.random.default_rng(41)
    tint = rng.uniform(0.75, 1.2, cid.max() + 1)[cid]
    stone_h = np.clip(1 - f1 / 0.028, 0, 1)
    gaps = np.clip((f2 - f1) / 0.004, 0, 1)
    v = (0.45 + 0.35 * stone_h) * tint * (0.6 + 0.4 * gaps)
    alb = m(v) * col((1.0, 0.92, 0.82))
    save("gravel", alb * 0.85, stone_h * gaps, 0.9 - 0.1 * stone_h, 3)


def obsidian():
    """Volcanic glass: near-black, conchoidal ripples, faint smoky veins."""
    f1, f2, _ = voronoi(50, 30)
    ripple = (np.sin(f1 * 60 + fnoise(52, 3, 8) * 6) * 0.5 + 0.5) * 0.5
    veins = np.clip(1 - np.abs(fnoise(51, 2, 5) - 0.5) / 0.03, 0, 1)
    v = 0.1 + 0.05 * ripple + 0.12 * veins
    alb = m(v) * col((1.0, 0.9, 0.95))
    save("obsidian", alb, ripple * 0.3 + (f2 - f1) * 4, np.clip(0.05 + 0.15 * veins + 0.05 * ripple, 0, 1), 3)


def plaster():
    grain = fbm(60, 6, 5)
    vert = fnoise(61, 1, 3)[:, :] * 0
    mp = fnoise(62, 2, 6)
    streaks = np.clip(fnoise(63, 3, 8)[:, :1].repeat(N, 1).T - 0.6, 0, 1) * 2.5
    v = 0.72 + 0.1 * (grain - 0.5) - 0.25 * streaks - 0.1 * np.clip(mp - 0.6, 0, 1) * 3
    save("plaster", m(v) * col((1.0, 0.96, 0.9)), grain * 0.4, 0.92 - 0.05 * grain, 3)
    del vert


def roof_tiles():
    """Rows of rounded clay/glazed tiles, staggered."""
    yy, xx = np.indices((N, N)) / N
    rows, cols = 8, 10
    ry = (yy * rows) % 1.0
    off = (np.floor(yy * rows) % 2) * 0.5
    rx = ((xx * cols + off) % 1.0)
    bump = np.sin(rx * np.pi) ** 0.6                  # tile is rounded across
    lap = np.clip(ry * 1.2, 0, 1) ** 0.5             # each row laps the one below
    edge = np.clip((1 - ry) / 0.08, 0, 1)
    h = bump * 0.7 * lap * edge
    tid = (np.floor(yy * rows) * 31 + np.floor(xx * cols + off) * 7).astype(int)
    tint = np.random.default_rng(70).uniform(0.8, 1.15, tid.max() + 1)[tid]
    grime = fbm(71, 4, 4)
    v = (0.45 + 0.4 * h) * tint * (0.85 + 0.25 * (grime - 0.5))
    save("roof_tiles", m(v) * col((0.75, 0.85, 1.0)), h, np.clip(0.35 + 0.3 * grime - 0.15 * h, 0, 1), 6)


def facade():
    """Night-time building skin: panel seams, stains, AC drips."""
    yy, xx = np.indices((N, N)) / N
    seams = ((np.abs(((xx * 4) % 1) - 0.5) > 0.49) | (np.abs(((yy * 6) % 1) - 0.5) > 0.49)).astype(float)
    grime = fbm(80, 2, 5)
    drip = np.clip(fnoise(81, 4, 12)[:1, :].repeat(N, 0) - 0.6, 0, 1) * 2
    v = 0.55 + 0.15 * (grime - 0.5) - 0.25 * seams - 0.2 * drip
    save("facade", m(v) * col((0.92, 0.95, 1.0)), -seams * 0.5 + grime * 0.2, 0.7 - 0.2 * drip, 4)


def wood():
    yy, xx = np.indices((N, N)) / N
    warp = fnoise(90, 1, 3) * 0.3
    ring = np.sin((xx * 9 + warp * 3 + fnoise(91, 2, 6) * 0.2) * 2 * np.pi) * 0.5 + 0.5
    fibre = fnoise(92, 80, 200)
    v = 0.45 + 0.2 * ring + 0.1 * fibre
    save("wood", m(v) * col((1.0, 0.75, 0.55)), ring * 0.3 + fibre * 0.2, 0.75 + 0.1 * fibre, 4)


def moss():
    f = fbm(100, 10, 5)
    v = 0.4 + 0.5 * f
    alb = m(v) * col((0.75, 1.0, 0.5))
    save("moss", alb * 0.8, f, 0.95 + 0 * f, 6)


def gold():
    br = fnoise(110, 2, 4)[:1, :].repeat(N, 0) * 0.5 + fnoise(111, 60, 160) * 0.5
    tarnish = np.clip((fbm(112, 3, 5) - 0.62) * 4, 0, 1)
    v = 0.75 + 0.15 * (br - 0.5) - 0.35 * tarnish
    save("gold", m(v) * col((1.0, 0.86, 0.6)), br * 0.2, np.clip(0.25 + 0.15 * br + 0.35 * tarnish, 0, 1), 2)


def macro_noise():
    """Large-scale brightness variation sampled in world space by the arena
    shader, so repeating textures don't read as a grid."""
    v = fbm(140, 1, 5) * 0.7 + fnoise(141, 3, 8) * 0.3
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((np.clip(v, 0, 1) * 255).astype(np.uint8), "L").save(f"{OUT}/macro_noise.png")


if __name__ == "__main__":
    macro_noise()
    stone()
    rock_strata()
    concrete_wet()
    paint_rust("paint_yellow", (0.78, 0.55, 0.12), 120)
    paint_rust("paint_grey", (0.55, 0.57, 0.6), 130)
    metal_dark()
    gravel()
    obsidian()
    plaster()
    roof_tiles()
    facade()
    wood()
    moss()
    gold()
