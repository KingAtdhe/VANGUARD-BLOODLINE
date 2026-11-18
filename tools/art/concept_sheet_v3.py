"""Concept sheet v3 — studio-style turnaround (front, back, head, details).

    python3 tools/art/concept_sheet_v3.py docs/art

Style goals taken from professional fighting-game model sheets: the body is
drawn as continuous anatomical contours (no tube limbs or ball joints), flat
colour with inked line work and hatching for shadow, real costume detail
(seams, straps, buckles, folds), and a turnaround layout. Everything is an
original drawing authored here in coordinates (metres, x right, y up).
"""

import math
import os
import random
import subprocess
import sys

INK = "#1b1513"


class Sheet:
    def __init__(self, w, h, bg="#b7b6aa"):
        self.w, self.h, self.n = w, h, 0
        self.o = [
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            '<defs><filter id="hand" x="-5%" y="-5%" width="110%" height="110%">'
            '<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7" result="n"/>'
            '<feDisplacementMap in="SourceGraphic" in2="n" scale="3.2" xChannelSelector="R" yChannelSelector="G"/></filter>'
            '<filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="6"/></filter></defs>',
            f'<rect width="{w}" height="{h}" fill="{bg}"/>',
        ]

    def add(self, s):
        self.o.append(s)

    def text(self, x, y, s, size=26, fill=INK, weight="normal", anchor="start", spacing=0, style=""):
        self.add(f'<text x="{x:.0f}" y="{y:.0f}" font-family="DejaVu Sans, Arial, sans-serif" font-size="{size}" font-weight="{weight}" '
                 f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{spacing}" {style}>{s}</text>')

    def save(self, path):
        open(path, "w").write("\n".join(self.o + ["</svg>"]))
        subprocess.run(["rsvg-convert", path, "-o", path[:-4] + ".png"], check=True)


def spline(q, closed):
    n = len(q)
    d = []
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = q[(i - 1) % n] if closed or i > 0 else q[0]
        p1, p2 = q[i], q[(i + 1) % n]
        p3 = q[(i + 2) % n] if closed or i + 2 < n else q[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return d


def path_d(q, corners, closed=True):
    """Smooth path through q; indices in `corners` are sharp."""
    n = len(q)
    if not corners:
        return f"M{q[0][0]:.1f},{q[0][1]:.1f} " + " ".join(spline(q, closed)) + (" Z" if closed else "")
    cs = sorted(corners)
    out = []
    if closed:
        start = cs[0]
        order = [(start + i) % n for i in range(n + 1)]
    else:
        order = list(range(n))
    out.append(f"M{q[order[0]][0]:.1f},{q[order[0]][1]:.1f}")
    seg = [q[order[0]]]
    for idx in order[1:]:
        seg.append(q[idx])
        if idx in corners or idx == order[-1]:
            if len(seg) == 2:
                out.append(f"L{seg[1][0]:.1f},{seg[1][1]:.1f}")
            else:
                out += spline(seg, False)
            seg = [q[idx]]
    return " ".join(out) + (" Z" if closed else "")


class Pen:
    """Draws in metres at (ox, ground) with `S` px per metre. mirror flips x."""

    def __init__(self, sh, ox, ground, S, mirror=False):
        self.sh, self.ox, self.gy, self.S, self.m = sh, ox, ground, S, -1 if mirror else 1
        self.k = S / 600.0
        self.rnd = random.Random(11)

    def P(self, p):
        return (self.ox + self.m * p[0] * self.S, self.gy - p[1] * self.S)

    def _d(self, pts, closed=True):
        q, corners = [], set()
        for i, p in enumerate(pts):
            q.append(self.P(p))
            if len(p) > 2:
                corners.add(i)
        return path_d(q, corners, closed)

    def part(self, pts, fill, lw=3.0, ink=True):
        """A filled, inked form. Returns its clip id for shadows and details."""
        self.sh.n += 1
        i = self.sh.n
        d = self._d(pts)
        self.sh.add(f'<defs><path id="q{i}" d="{d}"/><clipPath id="c{i}"><use xlink:href="#q{i}"/></clipPath></defs>'
                    f'<use xlink:href="#q{i}" fill="{fill}"/>')
        self._pending = (i, lw) if ink else None
        return i

    def outline(self, i, lw=3.0):
        self.sh.add(f'<use xlink:href="#q{i}" fill="none" stroke="{INK}" stroke-width="{lw * self.k:.2f}" stroke-linejoin="round" filter="url(#hand)"/>')

    def tone(self, clip, pts, fill, opacity=1.0):
        """Flat shadow/colour shape trimmed to a part."""
        self.sh.add(f'<path d="{self._d(pts)}" fill="{fill}" opacity="{opacity}" clip-path="url(#c{clip})"/>')

    def hatch(self, clip, pts, spacing=7.0, angle=-58, lw=1.25, opacity=0.6):
        """Pen hatching inside a region, trimmed to a part."""
        q = [self.P(p) for p in pts]
        xs, ys = [x for x, _ in q], [y for _, y in q]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        self.sh.n += 1
        j = self.sh.n
        a = math.radians(angle)
        dx, dy = math.cos(a), math.sin(a)
        L = math.hypot(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        lines = []
        t = -L / 2
        while t < L / 2:
            ox_, oy_ = cx - dy * t, cy + dx * t
            e0, e1 = self.rnd.uniform(0.55, 1.0), self.rnd.uniform(0.55, 1.0)
            lines.append(f"M{ox_ - dx * L / 2 * e0:.1f},{oy_ - dy * L / 2 * e0:.1f} L{ox_ + dx * L / 2 * e1:.1f},{oy_ + dy * L / 2 * e1:.1f}")
            t += spacing * self.k * self.rnd.uniform(0.8, 1.25)
        self.sh.add(f'<defs><clipPath id="c{j}"><path d="{self._d(pts)}"/></clipPath></defs>'
                    f'<g clip-path="url(#c{clip})"><path d="{" ".join(lines)}" stroke="{INK}" stroke-width="{lw * self.k:.2f}" '
                    f'fill="none" opacity="{opacity}" clip-path="url(#c{j})" stroke-linecap="round"/></g>')

    def line(self, pts, lw=1.8, color=INK, opacity=0.9, clip=None):
        c = f' clip-path="url(#c{clip})"' if clip else ""
        self.sh.add(f'<g{c}><path d="{self._d(pts, closed=False)}" fill="none" stroke="{color}" stroke-width="{lw * self.k:.2f}" '
                    f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}" filter="url(#hand)"/></g>')

    def glow(self, pts, color, lw=2.6):
        d = self._d(pts, closed=False)
        self.sh.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{lw * 2.8 * self.k:.2f}" stroke-linecap="round" filter="url(#glow)" opacity="0.8"/>'
                    f'<path d="{d}" fill="none" stroke="#ffd2c8" stroke-width="{lw * 0.8 * self.k:.2f}" stroke-linecap="round"/>')


def mir(pts):
    return [((-p[0], p[1]) + tuple(p[2:])) for p in pts]


def sym(half):
    """Closed symmetric shape from its x >= 0 half (listed top to bottom)."""
    return half + mir(half)[::-1]


C = (0, 0, "c")   # marker helper: append "c" to a point for a sharp corner

SKIN, SKIN_S = "#c58e6c", "#9d6a4f"
JKT, JKT_S, JKT_L = "#2f3138", "#1c1d22", "#454853"
PANT, PANT_S = "#25262c", "#15161a"
BOOT, BOOT_S = "#3a2f2a", "#231c19"
SASH, SASH_S = "#8c1d17", "#5c110e"
STEEL, STEEL_S = "#6d717c", "#42454e"
HAIR, RED = "#15100e", "#ff3b2a"


def AX(x):
    """Arm bulk: widen everything outside the shoulder joint line."""
    return 0.2 + (x - 0.2) * 1.3 if x > 0.2 else x


def arm(p, s, back, bare_scars):
    """One arm as a single anatomical contour. s = +1 figure's left side."""
    X = lambda x: s * AX(x)   # noqa: E731
    pts = [(X(0.2), 1.492), (X(0.262), 1.47), (X(0.298), 1.41), (X(0.305), 1.335), (X(0.292), 1.265), (X(0.3), 1.2), (X(0.292), 1.115),
           (X(0.31), 1.045), (X(0.308), 0.965), (X(0.287), 0.875), (X(0.283), 0.855), (X(0.297), 0.8), (X(0.29), 0.735), (X(0.262), 0.705),
           (X(0.233), 0.725), (X(0.228), 0.79), (X(0.238), 0.86), (X(0.228), 0.96), (X(0.226), 1.06), (X(0.224), 1.12), (X(0.2), 1.19),
           (X(0.192), 1.28), (X(0.19), 1.36)]
    a = p.part(pts, SKIN)
    # shadow side (light from the viewer's upper left)
    lit = -1 if not p.m < 0 else 1
    edge = 1 if (s * p.m) > 0 else -1
    if edge > 0:   # arm on the viewer's right: shadow on its outer edge
        p.tone(a, [(X(0.27), 1.5), (X(0.33), 1.5), (X(0.33), 0.68), (X(0.272), 0.68), (X(0.283), 0.86), (X(0.288), 1.04), (X(0.272), 1.12), (X(0.28), 1.26), (X(0.275), 1.4)], SKIN_S)
        p.hatch(a, [(X(0.25), 1.36), (X(0.3), 1.36), (X(0.3), 1.24), (X(0.262), 1.25)], angle=-55)
        p.hatch(a, [(X(0.262), 1.1), (X(0.31), 1.1), (X(0.31), 0.9), (X(0.268), 0.9)], angle=-55)
    else:          # arm on the viewer's left: shadow on the inner (torso) side
        p.tone(a, [(X(0.185), 1.4), (X(0.215), 1.38), (X(0.222), 1.2), (X(0.243), 1.11), (X(0.246), 0.96), (X(0.252), 0.86), (X(0.245), 0.7), (X(0.2), 0.7)], SKIN_S)
        p.hatch(a, [(X(0.19), 1.36), (X(0.23), 1.36), (X(0.235), 1.18), (X(0.2), 1.19)], angle=-55)
    p.outline(a, 3.2)
    # anatomy: deltoid, biceps/triceps split, elbow, forearm flexor, wrist, fist
    p.line([(X(0.205), 1.385), (X(0.245), 1.325), (X(0.283), 1.275)], 1.9, clip=a)
    if not back:
        p.line([(X(0.243), 1.325), (X(0.236), 1.25), (X(0.243), 1.17)], 1.5, opacity=0.75, clip=a)
        p.line([(X(0.232), 1.105), (X(0.262), 1.085), (X(0.278), 1.04)], 1.5, opacity=0.8, clip=a)
        p.line([(X(0.268), 1.03), (X(0.262), 0.95), (X(0.266), 0.89)], 1.3, opacity=0.6, clip=a)
    else:
        p.line([(X(0.262), 1.31), (X(0.27), 1.23), (X(0.258), 1.15)], 1.6, opacity=0.8, clip=a)
        p.line([(X(0.235), 1.3), (X(0.228), 1.2)], 1.3, opacity=0.6, clip=a)
        p.line([(X(0.25), 1.115), (X(0.268), 1.095), (X(0.262), 1.07)], 1.8, clip=a)     # elbow point
        p.line([(X(0.255), 1.05), (X(0.262), 0.95)], 1.3, opacity=0.6, clip=a)
    p.line([(X(0.237), 0.865), (X(0.262), 0.853), (X(0.285), 0.862)], 1.6, clip=a)
    for i in range(3):
        x = 0.246 + i * 0.016
        p.line([(X(x), 0.76 - i * 0.004), (X(x + 0.002), 0.718 + (0 if i else 0.004))], 1.4, opacity=0.8, clip=a)
    p.line([(X(0.236), 0.765), (X(0.262), 0.775), (X(0.292), 0.765)], 1.5, opacity=0.8, clip=a)
    if not back:
        p.line([(X(0.232), 0.8), (X(0.243), 0.77), (X(0.24), 0.74)], 1.6, clip=a)                 # thumb
    if bare_scars:
        p.glow([(X(0.262), 1.3), (X(0.252), 1.2), (X(0.268), 1.13), (X(0.262), 1.03), (X(0.272), 0.93), (X(0.262), 0.87)], RED, 2.2)
        p.glow([(X(0.268), 1.13), (X(0.29), 1.1)], RED, 1.6)
        p.glow([(X(0.262), 1.03), (X(0.243), 0.99)], RED, 1.6)
        p.glow([(X(0.262), 0.87), (X(0.257), 0.79)], RED, 1.6)
    else:
        # steel forearm guard with straps + fingerless glove
        g = p.part([(X(0.225), 1.085, "c"), (X(0.262), 1.105), (X(0.318), 1.07, "c"), (X(0.318), 0.985), (X(0.298), 0.885, "c"), (X(0.262), 0.872), (X(0.23), 0.888, "c"), (X(0.22), 0.985)], STEEL)
        p.tone(g, [(X(0.275 if edge > 0 else 0.2), 1.12), (X(0.33 if edge > 0 else 0.243), 1.12), (X(0.33 if edge > 0 else 0.248), 0.86), (X(0.28 if edge > 0 else 0.2), 0.86)], STEEL_S)
        p.outline(g, 2.8)
        p.line([(X(0.262), 1.1), (X(0.266), 0.99), (X(0.262), 0.878)], 1.4, opacity=0.7, clip=g)
        for y in (1.055, 0.925):
            st = p.part([(X(0.216), y + 0.016, "c"), (X(0.322), y + 0.006, "c"), (X(0.322), y - 0.022, "c"), (X(0.216), y - 0.012, "c")], "#17181c")
            p.outline(st, 2.0)
        gl = p.part([(X(0.236), 0.868, "c"), (X(0.288), 0.868, "c"), (X(0.298), 0.8), (X(0.292), 0.765, "c"), (X(0.234), 0.765, "c"), (X(0.228), 0.8)], "#17181c")
        p.outline(gl, 2.4)


def figure(sh, ox, ground, S, back=False):
    p = Pen(sh, ox, ground, S, mirror=back)
    fr = not back

    def sash(front_layer):
        s1 = p.part([(-0.12, 1.03, "c"), (-0.2, 1.0), (-0.3, 0.8), (-0.33, 0.56), (-0.27, 0.42, "c"), (-0.25, 0.56), (-0.21, 0.47, "c"), (-0.19, 0.62), (-0.15, 0.55, "c"), (-0.13, 0.8), (-0.08, 0.98, "c")], SASH)
        p.tone(s1, [(-0.2, 1.05), (-0.1, 1.05), (-0.12, 0.4), (-0.22, 0.4), (-0.2, 0.7)], SASH_S)
        p.hatch(s1, [(-0.2, 0.9), (-0.12, 0.9), (-0.14, 0.5), (-0.22, 0.5)], angle=-70, spacing=8)
        p.outline(s1, 2.8)
        p.line([(-0.17, 0.98), (-0.24, 0.8), (-0.27, 0.58)], 1.5, opacity=0.8, clip=s1)
        p.line([(-0.14, 0.95), (-0.2, 0.75), (-0.21, 0.56)], 1.3, opacity=0.6, clip=s1)

    if fr:
        sash(False)
    # ---- trousers (one continuous shape) -----------------------------------
    half = [(0.0, 1.03), (0.165, 1.03, "c"), (0.2, 0.93), (0.242, 0.78), (0.236, 0.64), (0.218, 0.56), (0.234, 0.44), (0.212, 0.31), (0.2, 0.2, "c"),
            (0.118, 0.2, "c"), (0.108, 0.32), (0.098, 0.44), (0.09, 0.55), (0.062, 0.68), (0.025, 0.8), (0.0, 0.835, "c")]
    t = p.part(sym(half), PANT)
    for s in (1, -1):
        on_right = (s * p.m) > 0
        p.tone(t, [(s * (0.15 if on_right else 0.02), 1.04), (s * (0.24 if on_right else 0.085), 1.04), (s * (0.24 if on_right else 0.13), 0.18), (s * (0.165 if on_right else 0.1), 0.18),
                   (s * (0.172 if on_right else 0.09), 0.5), (s * (0.165 if on_right else 0.055), 0.8)], PANT_S)
        # knee panel, seams, folds
        kp = p.part([(s * 0.1, 0.615, "c"), (s * 0.224, 0.625, "c"), (s * 0.228, 0.5), (s * 0.165, 0.455, "c"), (s * 0.094, 0.5)], JKT_L if fr else PANT)
        if fr:
            p.tone(kp, [(s * 0.16, 0.64), (s * 0.22, 0.64), (s * 0.22, 0.45), (s * 0.165, 0.45)] if on_right else [(s * 0.09, 0.64), (s * 0.13, 0.64), (s * 0.13, 0.45), (s * 0.09, 0.45)], JKT_S)
            p.outline(kp, 2.2)
            p.line([(s * 0.118, 0.585), (s * 0.198, 0.595)], 1.3, opacity=0.7)
        else:
            p.line([(s * 0.115, 0.57), (s * 0.155, 0.555), (s * 0.2, 0.575)], 1.6, opacity=0.8)     # back of knee
            p.line([(s * 0.13, 0.46), (s * 0.158, 0.4), (s * 0.15, 0.3)], 1.4, opacity=0.7)        # calf
        p.line([(s * 0.19, 0.95), (s * 0.225, 0.78), (s * 0.222, 0.64)], 1.3, opacity=0.6, clip=t)  # outer seam
        p.line([(s * 0.03, 0.82), (s * 0.085, 0.85), (s * 0.13, 0.9)], 1.5, opacity=0.8, clip=t)   # crotch folds
        p.line([(s * 0.04, 0.79), (s * 0.1, 0.8)], 1.3, opacity=0.6, clip=t)
        p.line([(s * 0.125, 0.3), (s * 0.165, 0.285), (s * 0.19, 0.3)], 1.4, opacity=0.8, clip=t)  # ankle bunching
        p.line([(s * 0.12, 0.25), (s * 0.16, 0.24), (s * 0.192, 0.255)], 1.4, opacity=0.8, clip=t)
        p.hatch(t, [(s * 0.02, 0.84), (s * 0.075, 0.84), (s * 0.1, 0.6), (s * 0.085, 0.58)], angle=-60, spacing=7)
        # thigh strap with a buckle (figure's left leg only)
        if s > 0:
            st = p.part([(0.04, 0.77, "c"), (0.244, 0.75, "c"), (0.244, 0.715, "c"), (0.045, 0.735, "c")], "#17181c")
            p.outline(st, 2.0)
            if fr:
                bk = p.part([(0.12, 0.775, "c"), (0.155, 0.771, "c"), (0.155, 0.722, "c"), (0.12, 0.726, "c")], STEEL)
                p.outline(bk, 1.8)
    p.outline(t, 3.4)
    # ---- boots ---------------------------------------------------------------
    for s in (1, -1):
        on_right = (s * p.m) > 0
        b = p.part([(s * 0.112, 0.235, "c"), (s * 0.202, 0.235, "c"), (s * 0.208, 0.13), (s * 0.235, 0.06), (s * 0.258, 0.03), (s * 0.255, 0.0, "c"),
                    (s * 0.1, 0.0, "c"), (s * 0.098, 0.05), (s * 0.108, 0.13)] if fr else
                   [(s * 0.112, 0.235, "c"), (s * 0.202, 0.235, "c"), (s * 0.206, 0.12), (s * 0.212, 0.04), (s * 0.208, 0.0, "c"), (s * 0.108, 0.0, "c"), (s * 0.104, 0.05), (s * 0.108, 0.13)], BOOT)
        p.tone(b, [(s * (0.17 if on_right else 0.09), 0.25), (s * (0.27 if on_right else 0.125), 0.25), (s * (0.27 if on_right else 0.125), 0.0), (s * (0.18 if on_right else 0.09), 0.0)], BOOT_S)
        p.outline(b, 3.0)
        p.line([(s * 0.098, 0.028), (s * 0.256, 0.028)] if fr else [(s * 0.105, 0.028), (s * 0.21, 0.028)], 2.0, clip=b)            # sole
        for y in (0.2, 0.155, 0.11):                                                               # straps and buckles
            st = p.part([(s * 0.106, y + 0.014, "c"), (s * 0.208, y + 0.014, "c"), (s * 0.209, y - 0.016, "c"), (s * 0.106, y - 0.016, "c")], "#17181c")
            p.outline(st, 1.8)
            if fr:
                bk = p.part([(s * 0.17, y + 0.018, "c"), (s * 0.196, y + 0.018, "c"), (s * 0.196, y - 0.02, "c"), (s * 0.17, y - 0.02, "c")], STEEL)
                p.outline(bk, 1.5)
        if fr:
            p.line([(s * 0.12, 0.075), (s * 0.165, 0.062), (s * 0.225, 0.07)], 1.4, opacity=0.7, clip=b)
    # ---- neck ----------------------------------------------------------------
    nk = p.part(sym([(0.0, 1.63), (0.058, 1.62), (0.062, 1.54), (0.11, 1.5), (0.0, 1.46)]), SKIN)
    p.tone(nk, [(-0.07, 1.64), (0.07, 1.64), (0.07, 1.585), (0.0, 1.565), (-0.07, 1.585)] if fr else [(0.01, 1.64), (0.08, 1.64), (0.12, 1.48), (0.03, 1.48)], SKIN_S)
    if fr:
        p.hatch(nk, [(0.0, 1.6), (0.07, 1.6), (0.07, 1.5), (0.01, 1.5)], angle=-55, spacing=6)
    p.outline(nk, 2.8)
    # ---- jacket --------------------------------------------------------------
    jh = [(0.0, 1.5), (0.075, 1.515), (0.2, 1.492, "c"), (0.204, 1.42), (0.196, 1.37), (0.222, 1.31), (0.198, 1.2), (0.158, 1.09), (0.168, 1.0), (0.18, 0.9, "c")]
    hem = [(0.1, 0.885), (0.0, 0.9, "c")] if fr else [(0.09, 0.84), (0.012, 0.8, "c"), (0.0, 0.9, "c")]
    j = p.part(sym(jh + hem), JKT)
    side = 1 if not back else -1
    p.tone(j, [(side * 0.09, 1.52), (side * 0.22, 1.52), (side * 0.22, 0.8), (side * 0.11, 0.8), (side * 0.118, 1.05), (side * 0.15, 1.2), (side * 0.13, 1.36)], JKT_S)
    p.hatch(j, [(side * 0.06, 1.3), (side * 0.15, 1.33), (side * 0.13, 1.1), (side * 0.07, 1.08)], angle=-58, spacing=7, opacity=0.5)
    p.hatch(j, [(-side * 0.21, 1.38), (-side * 0.16, 1.38), (-side * 0.13, 1.12), (-side * 0.17, 1.12)], angle=-58, spacing=7, opacity=0.45)
    if fr:
        # lighter overlapping front panel with the diagonal closure
        fp = p.part([(-0.07, 1.515, "c"), (0.012, 1.47), (0.085, 1.3), (0.11, 1.12), (0.095, 0.887, "c"), (0.18, 0.9, "c"), (0.168, 1.0), (0.158, 1.09), (0.198, 1.2), (0.222, 1.31),
                     (0.196, 1.37), (0.204, 1.42), (0.2, 1.492, "c"), (0.075, 1.515)], JKT_L)
        p.tone(fp, [(0.13, 1.52), (0.22, 1.52), (0.22, 0.86), (0.135, 0.86), (0.14, 1.05), (0.165, 1.2), (0.155, 1.36)], JKT)
        p.outline(fp, 2.4)
        p.glow([(0.014, 1.462), (0.087, 1.3), (0.112, 1.12), (0.098, 0.9)], RED, 2.4)
        for y in (1.39, 1.25, 1.11, 0.97):                                                         # closure clasps
            x = 0.012 + (1.47 - y) * 0.2
            x = min(x, 0.112)
            cl = p.part([(x - 0.05, y + 0.012, "c"), (x + 0.012, y + 0.016, "c"), (x + 0.012, y - 0.012, "c"), (x - 0.05, y - 0.016, "c")], "#17181c")
            p.outline(cl, 1.6)
        p.line([(-0.19, 1.36), (-0.13, 1.33), (-0.05, 1.345)], 1.6, opacity=0.8, clip=j)             # chest and waist folds
        p.line([(-0.16, 1.2), (-0.09, 1.215), (-0.03, 1.19)], 1.4, opacity=0.7, clip=j)
        p.line([(-0.15, 1.1), (-0.08, 1.08), (-0.02, 1.1)], 1.5, opacity=0.8, clip=j)
        p.line([(-0.165, 0.99), (-0.1, 0.97), (-0.03, 0.985)], 1.3, opacity=0.6, clip=j)
        pk = p.part([(-0.16, 1.27, "c"), (-0.075, 1.275, "c"), (-0.075, 1.2, "c"), (-0.118, 1.18, "c"), (-0.16, 1.2, "c")], JKT)   # chest pocket
        p.outline(pk, 1.8)
        p.line([(-0.158, 1.25), (-0.077, 1.254)], 1.2, opacity=0.8)
    else:
        p.line([(0.0, 1.5), (0.0, 0.9)], 1.8, clip=j)                                               # centre back seam
        p.line([(-0.19, 1.37), (-0.1, 1.41), (0.0, 1.42), (0.1, 1.41), (0.19, 1.37)], 1.6, clip=j)  # yoke
        for s in (1, -1):
            p.line([(s * 0.1, 1.41), (s * 0.12, 1.2), (s * 0.1, 1.02)], 1.3, opacity=0.7, clip=j)
            p.line([(s * 0.15, 1.1), (s * 0.08, 1.075), (s * 0.02, 1.09)], 1.4, opacity=0.7, clip=j)
        em = p.part([(0.0, 1.345, "c"), (0.07, 1.275, "c"), (0.07, 1.235, "c"), (0.0, 1.3, "c"), (-0.07, 1.235, "c"), (-0.07, 1.275, "c")], SASH)   # chevron emblem
        p.outline(em, 1.8)
        em2 = p.part([(0.0, 1.27, "c"), (0.045, 1.225, "c"), (0.045, 1.195, "c"), (0.0, 1.235, "c"), (-0.045, 1.195, "c"), (-0.045, 1.225, "c")], SASH)
        p.outline(em2, 1.6)
    p.outline(j, 3.4)
    # armhole trim, belt
    for s in (1, -1):
        p.line([(s * 0.196, 1.49), (s * 0.186, 1.42), (s * 0.176, 1.36), (s * 0.19, 1.31)], 1.6, opacity=0.8, clip=j)
    bl = p.part([(-0.166, 1.055, "c"), (0.166, 1.055, "c"), (0.17, 1.0, "c"), (-0.17, 1.0, "c")], "#141417")
    p.outline(bl, 2.6)
    if fr:
        bk = p.part([(-0.04, 1.066, "c"), (0.04, 1.066, "c"), (0.04, 0.99, "c"), (-0.04, 0.99, "c")], STEEL)
        p.tone(bk, [(0.0, 1.07), (0.05, 1.07), (0.05, 0.98), (0.012, 0.98)], STEEL_S)
        p.outline(bk, 2.2)
        p.line([(-0.02, 1.045), (0.02, 1.045), (0.02, 1.01), (-0.02, 1.01), (-0.02, 1.045)], 1.3)
        for x in (-0.12, 0.11):
            lp = p.part([(x - 0.012, 1.064, "c"), (x + 0.012, 1.064, "c"), (x + 0.012, 0.992, "c"), (x - 0.012, 0.992, "c")], JKT_L)
            p.outline(lp, 1.5)
    # ---- arms ----------------------------------------------------------------
    arm(p, -1, back, bare_scars=True)
    arm(p, 1, back, bare_scars=False)
    # torn shoulder cap on the scarred arm
    cp = p.part([(-0.195, 1.5, "c"), (-AX(0.27), 1.478), (-AX(0.305), 1.41), (-AX(0.312), 1.35, "c"), (-AX(0.285), 1.375, "c"), (-AX(0.27), 1.335, "c"), (-AX(0.245), 1.37, "c"), (-AX(0.225), 1.33, "c"), (-0.2, 1.37, "c"), (-0.185, 1.42)], JKT_L)
    p.tone(cp, [(-0.2, 1.5), (-0.24, 1.42), (-0.2, 1.32), (-0.17, 1.36)], JKT_S)
    p.outline(cp, 2.6)
    p.line([(-0.21, 1.47), (-AX(0.27), 1.44), (-AX(0.295), 1.39)], 1.3, opacity=0.7, clip=cp)
    # ---- collar + head --------------------------------------------------------
    col = p.part(sym([(0.0, 1.47, "c"), (0.085, 1.515, "c"), (0.07, 1.6), (0.062, 1.625, "c"), (0.03, 1.565), (0.0, 1.55)] if fr else
                     [(0.0, 1.5, "c"), (0.085, 1.515, "c"), (0.072, 1.6), (0.06, 1.63, "c"), (0.0, 1.635)]), JKT_L)
    p.tone(col, [(0.03, 1.64), (0.1, 1.64), (0.1, 1.46), (0.04, 1.46)] if fr else [(-0.1, 1.64), (-0.02, 1.64), (-0.03, 1.48), (-0.1, 1.48)], JKT_S)
    p.outline(col, 2.6)
    head(p, (0.0, 1.682), 0.95, back)
    if back:
        sash(True)


def head(p, c, hs, back=False):
    cx, cy = c
    r = lambda x, y, *f: (cx + x * hs, cy + y * hs) + tuple(f)   # noqa: E731
    if back:
        h = p.part(sym([r(0.0, 0.125), r(0.055, 0.112), r(0.082, 0.06), r(0.084, 0.0), r(0.07, -0.05), r(0.045, -0.085, "c"), r(0.0, -0.07)]), HAIR)
        p.tone(h, [r(-0.09, 0.0), r(0.09, 0.0), r(0.06, -0.09), r(-0.06, -0.09)], "#3a302b")      # shaved nape
        p.outline(h, 3.0)
        for s in (1, -1):
            e = p.part([r(s * 0.082, 0.02), r(s * 0.096, 0.012), r(s * 0.094, -0.03), r(s * 0.08, -0.04)], SKIN)
            p.outline(e, 2.0)
        for x0 in (-0.05, -0.02, 0.015, 0.045):
            p.line([r(x0, 0.11), r(x0 + 0.02, 0.06), r(x0 + 0.015, 0.01)], 1.3, color="#4a3d36", opacity=0.9, clip=h)
        p.line([r(-0.07, -0.01), r(0.0, -0.022), r(0.07, -0.01)], 1.5, color="#0a0807", clip=h)
        return
    for s in (1, -1):
        e = p.part([r(s * 0.076, 0.016), r(s * 0.094, 0.022), r(s * 0.096, -0.02), r(s * 0.08, -0.045), r(s * 0.074, -0.02)], SKIN)
        p.tone(e, [r(s * 0.078, 0.01), r(s * 0.09, 0.008), r(s * 0.088, -0.03), r(s * 0.078, -0.03)], SKIN_S)
        p.outline(e, 2.0)
    f = p.part(sym([r(0.0, 0.118), r(0.05, 0.108), r(0.075, 0.06), r(0.079, 0.0), r(0.074, -0.045), r(0.06, -0.086, "c"), r(0.032, -0.113), r(0.0, -0.121)]), SKIN)
    # planes of the face in shadow: far cheek, under brow, side of nose, under lip, under jaw
    p.tone(f, [r(0.045, 0.12), r(0.09, 0.12), r(0.09, -0.13), r(0.02, -0.13), r(0.045, -0.09), r(0.058, -0.04), r(0.05, 0.0), r(0.06, 0.03)], SKIN_S)
    p.tone(f, [r(-0.066, 0.03), r(-0.01, 0.022), r(-0.012, 0.004), r(-0.06, 0.0)], SKIN_S, 0.75)
    p.tone(f, [r(0.01, 0.022), r(0.066, 0.03), r(0.06, 0.0), r(0.012, 0.004)], SKIN_S, 0.75)
    p.tone(f, [r(0.003, 0.015), r(0.02, -0.035), r(0.012, -0.046), r(0.0, -0.04)], SKIN_S)
    p.tone(f, [r(-0.02, -0.083), r(0.02, -0.083), r(0.012, -0.095), r(-0.012, -0.095)], SKIN_S, 0.8)
    p.hatch(f, [r(0.05, 0.02), r(0.085, 0.02), r(0.07, -0.09), r(0.04, -0.1)], angle=-60, spacing=5.0, lw=1.0, opacity=0.55)
    p.outline(f, 3.0)
    for s in (1, -1):
        ex = s * 0.034
        br = p.part([r(ex - s * 0.026, 0.02, "c"), r(ex - s * 0.008, 0.038), r(ex + s * 0.03, 0.042, "c"), r(ex + s * 0.028, 0.032), r(ex - s * 0.006, 0.027)], HAIR)
        ew = p.part([r(ex - 0.021, 0.006, "c"), r(ex - 0.002, 0.017), r(ex + 0.021, 0.008, "c"), r(ex + 0.002, -0.003)], "#ece6da")
        p.tone(ew, [r(ex - 0.03, 0.02), r(ex + 0.03, 0.02), r(ex + 0.03, 0.01), r(ex - 0.03, 0.01)], "#b9b0a2")
        ir = p.part([r(ex + 0.002 + 0.0085 * math.cos(a), 0.007 + 0.0085 * math.sin(a)) for a in [i * math.pi / 5 for i in range(10)]], "#4a3423")
        pu = p.part([r(ex + 0.002 + 0.004 * math.cos(a), 0.007 + 0.004 * math.sin(a)) for a in [i * math.pi / 4 for i in range(8)]], "#060505")
        p.sh.add(f'<circle cx="{p.P(r(ex - 0.001, 0.01))[0]:.1f}" cy="{p.P(r(ex - 0.001, 0.01))[1]:.1f}" r="{1.6 * p.k * hs:.1f}" fill="#fff"/>')
        del br, ir, pu
        p.line([r(ex - 0.024, 0.005), r(ex - 0.003, 0.0185), r(ex + 0.024, 0.009)], 2.6)            # upper lid
        p.line([r(ex - 0.016, -0.001), r(ex + 0.004, -0.004), r(ex + 0.02, 0.003)], 1.0, opacity=0.6)
        p.line([r(s * 0.064, -0.01), r(s * 0.056, -0.04), r(s * 0.043, -0.07)], 1.2, opacity=0.55)   # cheek
    p.line([r(0.004, 0.02), r(0.013, -0.02), r(0.016, -0.038), r(0.004, -0.046)], 1.8)                # nose
    p.line([r(-0.013, -0.04), r(-0.004, -0.047), r(0.004, -0.046)], 1.5)
    p.line([r(-0.027, -0.068), r(-0.008, -0.072), r(0.008, -0.071), r(0.027, -0.066)], 2.3)          # mouth
    p.line([r(-0.012, -0.071), r(0.0, -0.068), r(0.012, -0.071)], 1.0, opacity=0.6)
    p.line([r(-0.014, -0.085), r(0.014, -0.085)], 1.3, opacity=0.6)
    p.line([r(-0.02, -0.106), r(0.0, -0.101), r(0.02, -0.106)], 1.2, opacity=0.5)                    # chin
    p.line([r(0.038, -0.008), r(0.05, -0.028), r(0.054, -0.044)], 2.0, color="#7a2a20")              # scar
    # hair: shaved sides, long top swept across to the figure's left, crimson streak
    for s in (1, -1):
        sd = p.part([r(s * 0.079, 0.055, "c"), r(s * 0.062, 0.062, "c"), r(s * 0.066, 0.02), r(s * 0.07, -0.012, "c"), r(s * 0.08, -0.005)], "#3a302b")
        p.outline(sd, 1.4)
    h = p.part([r(-0.083, 0.035, "c"), r(-0.09, 0.09), r(-0.055, 0.15), r(0.01, 0.178), r(0.085, 0.168), r(0.128, 0.115), r(0.132, 0.07, "c"), r(0.1, 0.085), r(0.086, 0.04, "c"),
                r(0.07, 0.085), r(0.025, 0.103), r(-0.03, 0.082), r(-0.066, 0.05)], HAIR)
    stp = p.part([r(-0.03, 0.082, "c"), r(-0.012, 0.15), r(0.035, 0.176, "c"), r(0.055, 0.14), r(0.02, 0.102, "c")], "#b82218")
    del stp
    p.outline(h, 2.8)
    for pts in ([r(-0.07, 0.07), r(-0.035, 0.13), r(0.02, 0.165)], [r(-0.045, 0.085), r(-0.01, 0.14)], [r(0.03, 0.108), r(0.07, 0.14), r(0.115, 0.115)],
                [r(0.05, 0.098), r(0.09, 0.115), r(0.125, 0.085)], [r(0.0, 0.11), r(0.04, 0.16)]):
        p.line(pts, 1.3, color="#6a5a52", opacity=0.9, clip=h)


def callout(sh, x, y, w, h, title):
    sh.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#c6c5ba" stroke="{INK}" stroke-width="2" rx="6"/>')
    sh.text(x + 14, y + 30, title, 19, "#3b3a34", "bold", spacing=2)


def kairo_sheet(out):
    sh = Sheet(2400, 1400)
    # faint emblem behind the figures
    sh.add('<path d="M620,150 L900,430 L900,560 L620,300 L340,560 L340,430 Z M620,430 L900,710 L900,840 L620,580 L340,840 L340,710 Z" fill="#a9a89c"/>')
    sh.add('<path d="M1330,150 L1610,430 L1610,560 L1330,300 L1050,560 L1050,430 Z M1330,430 L1610,710 L1610,840 L1330,580 L1050,840 L1050,710 Z" fill="#a9a89c"/>')
    sh.text(70, 105, "KAIRO", 86, INK, "bold", spacing=8)
    sh.text(74, 150, "THE EXILED", 28, "#a3231b", "bold", spacing=8)
    sh.text(74, 192, "Model sheet v3 — front / back", 20, "#55544c")
    g = 1310
    sh.add(f'<line x1="250" y1="{g}" x2="1720" y2="{g}" stroke="#8d8c80" stroke-width="2"/>')
    figure(sh, 620, g, 640, back=False)
    figure(sh, 1330, g, 640, back=True)
    sh.text(620, g + 46, "FRONT", 22, "#55544c", "bold", "middle", 4)
    sh.text(1330, g + 46, "BACK", 22, "#55544c", "bold", "middle", 4)
    def boxed(x, y, w, h, title, draw):
        callout(sh, x, y, w, h, title)
        sh.n += 1
        sh.add(f'<defs><clipPath id="b{sh.n}"><rect x="{x + 2}" y="{y + 40}" width="{w - 4}" height="{h - 42}"/></clipPath></defs><g clip-path="url(#b{sh.n})">')
        draw()
        sh.add('</g>')

    S = 1450
    boxed(1790, 60, 560, 480, "HEAD", lambda: head(Pen(sh, 2070, 310 + 1.7 * S, S), (0.0, 1.69), 1.0))
    S2 = 640
    boxed(1790, 560, 270, 470, "ORIGIN SCARS", lambda: arm(Pen(sh, 1925 + AX(0.262) * S2, 590 + 1.5 * S2, S2), -1, False, True))
    boxed(2080, 560, 270, 470, "FOREARM GUARD", lambda: arm(Pen(sh, 2215 - AX(0.262) * S2, 590 + 1.5 * S2, S2), 1, False, False))
    callout(sh, 1790, 1050, 560, 290, "PALETTE  +  NOTES")
    for i, c in enumerate((JKT, JKT_L, PANT, SASH, STEEL, SKIN, RED)):
        sh.add(f'<rect x="{1806 + i * 76}" y="1095" width="66" height="56" rx="6" fill="{c}" stroke="{INK}" stroke-width="1.5"/>')
    for i, n in enumerate(("Sleeveless exile jacket, diagonal clasp closure", "One bare arm with glowing Origin scars", "Steel forearm guard + fingerless glove",
                           "Torn crimson sash, chevron emblem on the back", "Undercut, long top swept across, red streak")):
        sh.text(1810, 1190 + i * 29, "•  " + n, 19, "#2c2b26")
    # the clipped arms spill outside their callouts otherwise
    sh.save(f"{out}/kairo_model_sheet_v3.svg")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/art"
    os.makedirs(out, exist_ok=True)
    kairo_sheet(out)
