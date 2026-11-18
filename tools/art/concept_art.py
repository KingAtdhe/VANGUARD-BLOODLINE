"""Original concept art for the VANGUARD: BLOODLINE roster (design stage).

    python3 tools/art/concept_art.py docs/art      # writes SVG + PNG sheets

Art comes BEFORE modelling: these sheets fix each fighter's silhouette,
proportions, costume and palette; the 3D models are then built to match.
Everything is drawn here from scratch (vector shapes), no traced or external
artwork. Figures are in metres (x right, y up, origin between the feet) so
the same proportions carry straight into the model builders.
"""

import math
import os
import subprocess
import sys

PX = 520.0  # pixels per metre on the big sheets


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(h, k):
    """k < 0 darkens, k > 0 lightens."""
    r, g, b = hex_to_rgb(h)
    if k < 0:
        r, g, b = (int(c * (1 + k)) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * k) for c in (r, g, b))
    return "#%02x%02x%02x" % (r, g, b)


class Canvas:
    def __init__(self, w, h, bg="#15161b"):
        self.w, self.h = w, h
        self.out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            '<defs>'
            '<linearGradient id="form" x1="0" y1="0" x2="1" y2="0.25">'
            '<stop offset="0" stop-color="#fff" stop-opacity="0.20"/>'
            '<stop offset="0.45" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.6" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0.42"/></linearGradient>'
            '<filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="7"/></filter>'
            '<filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>'
            '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#23252d"/>'
            '<stop offset="1" stop-color="#101116"/></linearGradient>'
            '</defs>',
            f'<rect width="{w}" height="{h}" fill="url(#bg)"/>',
        ]

    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, size=28, fill="#e9e9ee", weight="normal", anchor="start", spacing=0):
        s = s.replace("&", "&amp;").replace("<", "&lt;")
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="DejaVu Sans, Arial, sans-serif" font-size="{size}" '
                 f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" letter-spacing="{spacing}">{s}</text>')

    def save(self, path):
        open(path, "w").write("\n".join(self.out + ["</svg>"]))
        subprocess.run(["rsvg-convert", path, "-o", path[:-4] + ".png"], check=True)


def smooth(pts, closed=True):
    """Catmull-Rom spline through pts as an SVG cubic path."""
    n = len(pts)
    if n < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if closed or i > 0 else pts[0]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed or i + 2 < n else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d) + (" Z" if closed else "")


class Fig:
    """Draws one fighter. All coordinates in metres; mirror=True flips x."""

    def __init__(self, cv, ox, ground, scale=PX, sil=False):
        self.cv, self.ox, self.gy, self.S, self.sil = cv, ox, ground, scale, sil

    def P(self, p):
        return (self.ox + p[0] * self.S, self.gy - p[1] * self.S)

    def _emit(self, d, fill, stroke=None, sw=2.4, form=True, opacity=1.0):
        if self.sil:
            self.cv.add(f'<path d="{d}" fill="#0b0b0e" stroke="#0b0b0e" stroke-width="2"/>')
            return
        stroke = stroke or shade(fill, -0.55)
        k = self.S / PX
        op = f' opacity="{opacity}"' if opacity < 1 else ""
        self.cv.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw * k:.2f}" stroke-linejoin="round"{op}/>')
        if form:
            self.cv.add(f'<path d="{d}" fill="url(#form)"{op}/>')

    def shape(self, pts, fill, sharp=False, **kw):
        q = [self.P(p) for p in pts]
        d = ("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in q) + " Z") if sharp else smooth(q)
        self._emit(d, fill, **kw)

    def pair(self, pts, fill, **kw):
        self.shape(pts, fill, **kw)
        self.shape([(-x, y) for x, y in pts], fill, **kw)

    def limb(self, a, b, prof, fill, cap=0.6, **kw):
        """Tapered limb a→b. prof: [(t, half-width) or (t, left, right)]."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1e-6
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        left, right = [], []
        for item in prof:
            t, wl = item[0], item[1]
            wr = item[2] if len(item) > 2 else wl
            cx, cy = a[0] + dx * t, a[1] + dy * t
            left.append((cx + nx * wl, cy + ny * wl))
            right.append((cx - nx * wr, cy - ny * wr))
        w0, w1 = prof[0][1], prof[-1][1]
        pts = left + [(b[0] + ux * w1 * cap, b[1] + uy * w1 * cap)] + right[::-1] + [(a[0] - ux * w0 * cap, a[1] - uy * w0 * cap)]
        self.shape(pts, fill, **kw)

    def ell(self, c, rx, ry, fill, **kw):
        pts = [(c[0] + math.cos(a) * rx, c[1] + math.sin(a) * ry) for a in [i * math.pi / 6 for i in range(12)]]
        self.shape(pts, fill, **kw)

    def line(self, pts, color, w=2.0, opacity=0.55, sm=True):
        if self.sil:
            return
        q = [self.P(p) for p in pts]
        d = smooth(q, closed=False) if sm and len(q) > 2 else "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in q)
        self.cv.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w * self.S / PX:.2f}" '
                    f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"/>')

    def glow(self, pts, color, w=4.0, closed=False):
        """Origin-energy accent: bright core over a soft halo."""
        if self.sil:
            return
        q = [self.P(p) for p in pts]
        d = smooth(q, closed=closed) if len(q) > 2 else "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in q)
        k = self.S / PX
        self.cv.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w * 2.6 * k:.2f}" stroke-linecap="round" '
                    f'filter="url(#glow)" opacity="0.85"/>')
        self.cv.add(f'<path d="{d}" fill="none" stroke="{shade(color, 0.55)}" stroke-width="{w * k:.2f}" stroke-linecap="round"/>')

    # ------------------------------------------------------------ body ----
    def body(self, b, col):
        """Draws the base figure. b: proportions, col: colour per body part.
        Returns the joint positions for costume overlays."""
        k = b["h"] / 1.8
        sw, cw, ww, hw = b["sw"], b["cw"], b["ww"], b["hw"]
        J = {}
        for s, side in ((1, "L"), (-1, "R")):   # figure's left is drawn on the viewer's right
            sp = b["arms"][0 if s > 0 else 1]
            J["sh" + side] = (s * sw, 1.455 * k)
            J["el" + side] = (s * (sw + sp[0]), (1.455 - 0.3 * sp[2]) * k)
            J["wr" + side] = (s * (sw + sp[1]), (1.455 - (0.3 + 0.26) * sp[2] + sp[3]) * k)
            J["hip" + side] = (s * hw * 0.56, 0.95 * k)
            J["kn" + side] = (s * (hw * 0.56 + b["stance"] * 0.45), 0.52 * k)
            J["an" + side] = (s * (hw * 0.56 + b["stance"]), 0.085 * k)
        J["head"] = (0.0, 1.69 * k)
        J["k"] = k
        th, cf, ua, fa = b["thigh"], b["calf"], b["arm"], b["fore"]

        # legs + feet
        for s, side in ((1, "L"), (-1, "R")):
            hip, kn, an = J["hip" + side], J["kn" + side], J["an" + side]
            self.limb(hip, kn, [(0, th * 1.0, th * 1.0), (0.25, th * 1.12, th * 1.05), (0.75, th * 0.74, th * 0.72),
                                (1, th * 0.62)], col["thigh"])
            self.limb(kn, an, [(0, cf * 0.92), (0.28, cf * (1.18 if s > 0 else 1.0), cf * (1.0 if s > 0 else 1.18)),
                               (0.75, cf * 0.68), (1, cf * 0.55)], col["shin"])
            ax, o = an[0], s * 0.045
            self.shape([(ax - 0.05, 0.105 * k), (ax + 0.05, 0.105 * k), (ax + 0.062 + o, 0.03), (ax + 0.05 + o, 0.0),
                        (ax - 0.05 + o, 0.0), (ax - 0.062 + o * 0.4, 0.03)], col["foot"])
        # pelvis
        self.shape([(ww, 1.07 * k), (hw, 0.97 * k), (hw * 1.0, 0.89 * k), (hw * 0.45, 0.83 * k), (0, 0.815 * k),
                    (-hw * 0.45, 0.83 * k), (-hw, 0.89 * k), (-hw, 0.97 * k), (-ww, 1.07 * k), (0, 1.09 * k)], col["pelvis"])
        # neck + trapezius
        nw = b["neck"]
        self.shape([(nw, 1.6 * k), (nw * 1.08, 1.52 * k), (sw * 0.78, 1.475 * k), (-sw * 0.78, 1.475 * k),
                    (-nw * 1.08, 1.52 * k), (-nw, 1.6 * k)], col["neck"])
        # torso
        self.shape([(nw * 1.3, 1.5 * k), (sw * 0.96, 1.47 * k), (sw * 1.0, 1.4 * k), (cw, 1.31 * k), (cw * 0.95, 1.2 * k),
                    (ww, 1.08 * k), (ww * 1.03, 1.02 * k), (0, 1.0 * k), (-ww * 1.03, 1.02 * k), (-ww, 1.08 * k),
                    (-cw * 0.95, 1.2 * k), (-cw, 1.31 * k), (-sw, 1.4 * k), (-sw * 0.96, 1.47 * k), (-nw * 1.3, 1.5 * k),
                    (0, 1.49 * k)], col["torso"])
        # arms
        for s, side in ((1, "L"), (-1, "R")):
            sh, el, wr = J["sh" + side], J["el" + side], J["wr" + side]
            c = col.get("arm" + side, col["arm"])
            f = col.get("fore" + side, col["fore"])
            self.limb(sh, el, [(0, ua * 1.3), (0.2, ua * 1.25, ua * 1.2) if s < 0 else (0.2, ua * 1.2, ua * 1.25),
                               (0.55, ua * 1.05), (1, ua * 0.76)], c, cap=0.9)
            self.limb(el, wr, [(0, fa * 0.95), (0.25, fa * 1.15), (0.8, fa * 0.68), (1, fa * 0.58)], f)
            hx, hy = wr[0] + s * 0.006, wr[1] - 0.062 * k
            hs = b.get("hand", 1.0) * k
            self.shape([(hx - 0.04 * hs, hy + 0.045 * hs), (hx + 0.04 * hs, hy + 0.045 * hs), (hx + 0.046 * hs, hy - 0.01 * hs),
                        (hx + 0.036 * hs, hy - 0.05 * hs), (hx - 0.036 * hs, hy - 0.05 * hs), (hx - 0.046 * hs, hy - 0.01 * hs)],
                       col.get("hand" + side, col["hand"]))
            for i in (-1, 0, 1):
                self.line([(hx + i * 0.02 * hs, hy - 0.048 * hs), (hx + i * 0.02 * hs, hy - 0.015 * hs)],
                          shade(col.get("hand" + side, col["hand"]), -0.6), 1.6, 0.6, sm=False)
            J["hand" + side] = (hx, hy)
        return J

    def head(self, J, b, skin, face=True, brow="#1a1412", eye="#3a2a1c", stern=1.0):
        k, hs = J["k"], b["head"]
        cx, cy = J["head"]
        r = lambda x, y: (cx + x * hs * k, cy + y * hs * k)   # noqa: E731
        for s in (1, -1):
            self.ell(r(s * 0.084, -0.004), 0.012 * hs * k, 0.026 * hs * k, shade(skin, -0.12))
        self.shape([r(0, 0.118), r(0.052, 0.105), r(0.078, 0.05), r(0.079, -0.015), r(0.066, -0.07), r(0.034, -0.108),
                    r(0, -0.118), r(-0.034, -0.108), r(-0.066, -0.07), r(-0.079, -0.015), r(-0.078, 0.05), r(-0.052, 0.105)], skin)
        if not face or self.sil:
            return r
        dk = shade(skin, -0.45)
        for s in (1, -1):
            ex = s * 0.034
            self.line([r(ex - s * 0.022, 0.03 - 0.007 * stern), r(ex, 0.034), r(ex + s * 0.025, 0.033)], brow, 5.0, 1.0)
            self.shape([r(ex - 0.02, 0.006), r(ex, 0.016), r(ex + 0.02, 0.006), r(ex, -0.003)], "#ece8df", sw=1.2, form=False)
            self.ell(r(ex, 0.0065), 0.0075 * hs * k, 0.0075 * hs * k, eye, sw=1.0, form=False)
            self.line([r(ex - 0.021, 0.008), r(ex, 0.0175), r(ex + 0.021, 0.008)], "#120e0c", 2.6, 0.95)
            self.line([r(s * 0.06, -0.02), r(s * 0.05, -0.062)], dk, 2.0, 0.28)       # cheek plane
        self.line([r(0.006, 0.002), r(0.011, -0.03), r(0.002, -0.04)], dk, 2.2, 0.6)  # nose
        self.line([r(-0.012, -0.041), r(0.0, -0.045), r(0.013, -0.041)], dk, 2.0, 0.5)
        self.line([r(-0.024, -0.07), r(0, -0.073), r(0.024, -0.069)], shade(skin, -0.6), 2.6, 0.9)   # mouth
        self.line([r(-0.012, -0.084), r(0.012, -0.084)], dk, 1.8, 0.35)
        return r


# ---------------------------------------------------------------- roster --
def kairo(f):
    SKIN, JKT, JKT2, PANT, BOOT, RED = "#b98263", "#26282f", "#3a3d47", "#1c1d22", "#2b2523", "#ff2a1f"
    b = dict(h=1.80, sw=0.215, cw=0.185, ww=0.14, hw=0.165, arm=0.05, fore=0.044, thigh=0.086, calf=0.058, neck=0.052,
             head=1.0, stance=0.085, arms=[(0.07, 0.105, 1.0, 0.0), (0.07, 0.105, 1.0, 0.0)])
    col = dict(thigh=PANT, shin=PANT, foot=BOOT, pelvis=PANT, neck=SKIN, torso=JKT, arm=SKIN, armL=JKT, fore=SKIN,
               foreL=JKT2, hand=SKIN, handL="#191a1e")
    k = 1.0
    # exile sash hanging behind the hip (drawn first, behind the legs)
    f.shape([(-0.15, 1.0), (-0.2, 0.98), (-0.27, 0.62), (-0.2, 0.5), (-0.17, 0.66), (-0.12, 0.56), (-0.1, 0.9)], "#6d1512")
    J = f.body(b, col)
    # trousers: knee panels + bound shins, boots
    for s in (1, -1):
        kn, an = J["kn" + ("L" if s > 0 else "R")], J["an" + ("L" if s > 0 else "R")]
        f.shape([(kn[0] - 0.05, kn[1] + 0.07), (kn[0] + 0.05, kn[1] + 0.07), (kn[0] + 0.044, kn[1] - 0.06), (kn[0] - 0.044, kn[1] - 0.06)], JKT2)
        for i in range(4):
            y = an[1] + 0.07 + i * 0.045
            f.line([(an[0] - 0.045 - i * 0.004, y), (an[0] + 0.045 + i * 0.004, y + 0.012 * s)], "#4a4c57", 5.5, 0.9, sm=False)
    # jacket: sleeveless on his right, sleeved on his left, diagonal closure, high collar
    f.shape([(0.0, 1.5), (0.07, 1.515), (0.2, 1.46), (0.19, 1.3), (0.15, 1.1), (0.16, 0.98), (0.06, 0.93), (-0.06, 0.95),
             (-0.155, 1.0), (-0.15, 1.1), (-0.185, 1.3), (-0.2, 1.42), (-0.07, 1.515)], JKT)
    f.shape([(-0.07, 1.515), (0.02, 1.47), (0.12, 1.2), (0.1, 0.96), (0.16, 0.98), (0.15, 1.1), (0.19, 1.3), (0.2, 1.46), (0.07, 1.515)],
            JKT2, sharp=False)
    f.shape([(-0.062, 1.6), (-0.075, 1.52), (0.0, 1.475), (0.075, 1.52), (0.062, 1.6), (0.03, 1.545), (-0.03, 1.545)], JKT2)   # collar
    f.glow([(0.022, 1.46), (0.115, 1.2), (0.098, 0.985)], RED, 2.6)                    # closure seam
    f.shape([(-0.16, 1.045), (0.165, 1.03), (0.165, 0.985), (-0.16, 1.0)], "#111114", sharp=True)   # belt
    f.shape([(-0.03, 1.05), (0.03, 1.047), (0.03, 0.985), (-0.03, 0.988)], "#55575f", sharp=True)
    # left arm: armoured forearm; right arm: bare, Origin scar-lines
    elL, wrL = J["elL"], J["wrL"]
    f.shape([(elL[0] - 0.05, elL[1] - 0.03), (elL[0] + 0.052, elL[1] - 0.02), (wrL[0] + 0.036, wrL[1] + 0.03), (wrL[0] - 0.034, wrL[1] + 0.02)], "#4a4d58")
    shR, elR, wrR = J["shR"], J["elR"], J["wrR"]
    f.shape([(shR[0] + 0.06, shR[1] + 0.05), (shR[0] - 0.075, shR[1] + 0.03), (shR[0] - 0.07, shR[1] - 0.05), (shR[0] + 0.05, shR[1] - 0.07)], JKT2)  # torn shoulder cap
    f.glow([(shR[0] - 0.01, shR[1] - 0.1), (elR[0] + 0.012, elR[1] + 0.06), (elR[0] - 0.012, elR[1] - 0.04), (wrR[0] + 0.01, wrR[1] + 0.08)], RED, 2.2)
    f.glow([(elR[0] - 0.012, elR[1] - 0.04), (elR[0] - 0.03, elR[1] - 0.1)], RED, 1.8)
    f.glow([(wrR[0] + 0.01, wrR[1] + 0.08), (J["handR"][0], J["handR"][1] + 0.03)], RED, 1.8)
    r = f.head(J, b, SKIN, stern=1.4)
    # hair: undercut, swept back and to his left, one crimson streak
    f.shape([r(-0.082, 0.03), r(-0.086, 0.09), r(-0.05, 0.145), r(0.02, 0.165), r(0.085, 0.135), r(0.1, 0.07), r(0.082, 0.03),
             r(0.07, 0.075), r(0.02, 0.1), r(-0.03, 0.082), r(-0.062, 0.05)], "#17120f")
    f.shape([r(-0.03, 0.082), r(0.0, 0.158), r(0.035, 0.16), r(0.012, 0.1)], "#a31a14", sw=1.2)
    f.line([r(0.04, 0.012), r(0.052, -0.02)], "#5a2a20", 2.4, 0.8)                      # scar under the eye
    return J, b


def drakon(f):
    SKIN, IRON, IRON2, PANT, ORG, SOOT = "#7b4f38", "#4a4541", "#6b6560", "#2a2623", "#ff7a1a", "#1b1816"
    b = dict(h=1.98, sw=0.285, cw=0.255, ww=0.2, hw=0.2, arm=0.074, fore=0.07, thigh=0.108, calf=0.074, neck=0.07,
             head=0.98, stance=0.12, hand=1.3, arms=[(0.11, 0.15, 1.0, 0.0), (0.11, 0.15, 1.0, 0.0)])
    col = dict(thigh=PANT, shin=IRON, foot=IRON, pelvis=PANT, neck=SKIN, torso=SKIN, arm=SKIN, fore=IRON, hand=IRON2)
    k = b["h"] / 1.8
    J = f.body(b, col)
    # bare chest: pecs, abdominals
    D = shade(SKIN, -0.5)
    for s in (1, -1):
        f.line([(s * 0.02, 1.44 * k), (s * 0.13, 1.42 * k), (s * 0.23, 1.33 * k), (s * 0.13, 1.27 * k), (s * 0.015, 1.29 * k)], D, 2.6, 0.5)
        for y in (1.22, 1.15, 1.08):
            f.line([(s * 0.012, y * k), (s * 0.085, (y + 0.006) * k)], D, 2.0, 0.35)
    f.line([(0, 1.44 * k), (0, 1.03 * k)], D, 2.0, 0.4, sm=False)
    # harness with furnace core
    f.shape([(-0.23, 1.47 * k), (-0.17, 1.5 * k), (0.03, 1.31 * k), (-0.03, 1.27 * k)], SOOT, sharp=True)
    f.shape([(0.23, 1.47 * k), (0.17, 1.5 * k), (-0.03, 1.31 * k), (0.03, 1.27 * k)], SOOT, sharp=True)
    f.shape([(0, 1.36 * k), (0.06, 1.3 * k), (0, 1.22 * k), (-0.06, 1.3 * k)], IRON2, sharp=True)
    f.glow([(0, 1.335 * k), (0.032, 1.3 * k), (0, 1.255 * k), (-0.032, 1.3 * k)], ORG, 4.0, closed=True)
    # heavy belt + armoured kilt plates
    f.shape([(-0.215, 1.1 * k), (0.215, 1.1 * k), (0.225, 1.0 * k), (-0.225, 1.0 * k)], IRON, sharp=True)
    for x in (-0.16, 0.0, 0.16):
        f.shape([(x - 0.075, 1.0 * k), (x + 0.075, 1.0 * k), (x + 0.06, 0.78 * k), (x, 0.73 * k), (x - 0.06, 0.78 * k)], IRON2 if x == 0 else IRON, sharp=True)
    f.glow([(-0.05, 1.05 * k), (0.05, 1.05 * k)], ORG, 3.0)
    # asymmetric pauldron (his right), piston gauntlets, plated boots
    sh = J["shR"]
    f.shape([(sh[0] + 0.1, sh[1] + 0.1), (sh[0] - 0.02, sh[1] + 0.16), (sh[0] - 0.15, sh[1] + 0.09), (sh[0] - 0.165, sh[1] - 0.06),
             (sh[0] - 0.06, sh[1] - 0.12), (sh[0] + 0.07, sh[1] - 0.05)], IRON2)
    f.shape([(sh[0] + 0.06, sh[1] + 0.035), (sh[0] - 0.03, sh[1] + 0.085), (sh[0] - 0.12, sh[1] + 0.03), (sh[0] - 0.11, sh[1] - 0.04), (sh[0] - 0.02, sh[1] - 0.02)], IRON)
    for side, s in (("L", 1), ("R", -1)):
        el, wr = J["el" + side], J["wr" + side]
        f.shape([(el[0] - 0.085, el[1] - 0.0), (el[0] + 0.085, el[1] + 0.01), (wr[0] + 0.075, wr[1] + 0.0), (wr[0] - 0.075, wr[1] - 0.0)], IRON)
        f.shape([(el[0] - 0.095, el[1] + 0.02), (el[0] + 0.095, el[1] + 0.03), (el[0] + 0.09, el[1] - 0.04), (el[0] - 0.09, el[1] - 0.05)], IRON2, sharp=True)
        f.glow([(el[0] + s * 0.03, el[1] - 0.09), (wr[0] + s * 0.03, wr[1] + 0.06)], ORG, 2.6)
        f.shape([(wr[0] - 0.085, wr[1] + 0.04), (wr[0] + 0.085, wr[1] + 0.04), (wr[0] + 0.08, wr[1] - 0.005), (wr[0] - 0.08, wr[1] - 0.005)], SOOT, sharp=True)
        kn, an = J["kn" + side], J["an" + side]
        f.shape([(kn[0] - 0.07, kn[1] + 0.08), (kn[0] + 0.07, kn[1] + 0.08), (kn[0] + 0.06, kn[1] - 0.07), (kn[0], kn[1] - 0.11), (kn[0] - 0.06, kn[1] - 0.07)], IRON2)
        f.line([(an[0] - 0.06, an[1] + 0.16), (an[0] + 0.06, an[1] + 0.16)], SOOT, 5, 0.9, sm=False)
    r = f.head(J, b, SKIN, stern=1.8, brow="#141110")
    f.shape([r(-0.08, 0.04), r(-0.07, 0.1), r(0, 0.125), r(0.07, 0.1), r(0.08, 0.04), r(0.05, 0.085), r(0, 0.098), r(-0.05, 0.085)], "#1c1715")   # cropped hair
    f.shape([r(-0.072, -0.03), r(-0.05, -0.058), r(-0.025, -0.055), r(0, -0.06), r(0.025, -0.055), r(0.05, -0.058), r(0.072, -0.03),
             r(0.06, -0.1), r(0.03, -0.15), r(0, -0.17), r(-0.03, -0.15), r(-0.06, -0.1)], "#1c1715")   # beard
    f.line([r(-0.02, -0.074), r(0.02, -0.074)], "#6b4a3a", 2.4, 0.9, sm=False)
    return J, b


def seraphina(f):
    SKIN, WHT, ICE, NAVY, SIL, BLU = "#e3bfa6", "#e8ecf4", "#b9c8e0", "#27324a", "#aab2c2", "#6fd0ff"
    b = dict(h=1.72, sw=0.175, cw=0.15, ww=0.11, hw=0.155, arm=0.036, fore=0.032, thigh=0.08, calf=0.05, neck=0.04,
             head=0.96, stance=0.05, hand=0.85, arms=[(0.06, 0.1, 1.0, 0.0), (0.05, 0.02, 0.9, 0.06)])
    col = dict(thigh=NAVY, shin=SIL, foot=SIL, pelvis=NAVY, neck=SKIN, torso=NAVY, arm=NAVY, fore=WHT, hand=SKIN)
    k = b["h"] / 1.8
    # long back panels of the half-coat + ponytail (behind the body)
    f.shape([(-0.12, 1.02 * k), (-0.3, 0.6 * k), (-0.36, 0.2 * k), (-0.24, 0.3 * k), (-0.2, 0.12 * k), (-0.12, 0.5 * k), (-0.02, 0.9 * k)], ICE, opacity=0.92)
    f.shape([(0.1, 1.02 * k), (0.22, 0.72 * k), (0.2, 0.45 * k), (0.13, 0.6 * k), (0.06, 0.9 * k)], ICE, opacity=0.92)
    f.shape([(0.05, 1.86 * k), (0.2, 1.8 * k), (0.3, 1.5 * k), (0.34, 1.1 * k), (0.27, 0.95 * k), (0.25, 1.25 * k), (0.2, 1.5 * k), (0.1, 1.7 * k)], "#f4f5fa")
    J = f.body(b, col)
    # chest armour, one shoulder guard (her left), waist wrap
    f.shape([(-0.06, 1.5 * k), (0.06, 1.5 * k), (0.15, 1.43 * k), (0.15, 1.3 * k), (0.09, 1.2 * k), (0, 1.17 * k), (-0.09, 1.2 * k), (-0.15, 1.3 * k), (-0.15, 1.43 * k)], WHT)
    f.line([(0, 1.49 * k), (0, 1.19 * k)], SIL, 2.2, 0.8, sm=False)
    f.glow([(-0.1, 1.33 * k), (0, 1.27 * k), (0.1, 1.33 * k)], BLU, 2.2)
    sh = J["shL"]
    f.shape([(sh[0] - 0.06, sh[1] + 0.06), (sh[0] + 0.03, sh[1] + 0.09), (sh[0] + 0.1, sh[1] + 0.02), (sh[0] + 0.09, sh[1] - 0.08), (sh[0] - 0.02, sh[1] - 0.05)], WHT)
    f.shape([(-0.115, 1.1 * k), (0.115, 1.1 * k), (0.16, 0.98 * k), (0.05, 0.9 * k), (-0.04, 0.96 * k), (-0.16, 0.97 * k)], ICE)
    f.shape([(-0.16, 0.99 * k), (-0.04, 0.97 * k), (-0.1, 0.68 * k), (-0.2, 0.62 * k)], WHT, opacity=0.95)       # asymmetric front panel
    f.glow([(-0.12, 1.045 * k), (0.12, 1.045 * k)], BLU, 2.0)
    for side in ("L", "R"):
        kn, an, el, wr = J["kn" + side], J["an" + side], J["el" + side], J["wr" + side]
        f.shape([(kn[0] - 0.05, kn[1] + 0.09), (kn[0] + 0.05, kn[1] + 0.09), (kn[0] + 0.04, kn[1] - 0.04), (kn[0], kn[1] - 0.07), (kn[0] - 0.04, kn[1] - 0.04)], WHT)
        f.line([(an[0], an[1] + 0.3), (an[0], an[1] + 0.06)], BLU, 1.6, 0.8, sm=False)
        f.shape([(el[0] - 0.036, el[1] + 0.02), (el[0] + 0.036, el[1] + 0.02), (el[0] + 0.03, el[1] - 0.04), (el[0] - 0.03, el[1] - 0.04)], SIL)
    r = f.head(J, b, SKIN, stern=0.6, brow="#b9bcc8", eye="#3f78a8")
    f.shape([r(-0.083, -0.02), r(-0.09, 0.07), r(-0.05, 0.14), r(0.02, 0.16), r(0.08, 0.13), r(0.092, 0.06), r(0.083, 0.0),
             r(0.06, 0.07), r(0.02, 0.085), r(-0.02, 0.05), r(-0.066, 0.0), r(-0.075, -0.07)], "#f4f5fa")       # side-swept fringe
    f.ell(r(0.03, 0.165), 0.03, 0.026, "#f4f5fa")
    f.glow([r(-0.01, 0.142), r(0.05, 0.15)], BLU, 1.6)
    return J, b


def nox(f):
    DARK, PLUM, MASK, VIO, GLV = "#16131d", "#2b2038", "#c9c5d2", "#a04bff", "#0e0c13"
    b = dict(h=1.68, sw=0.19, cw=0.16, ww=0.125, hw=0.15, arm=0.042, fore=0.038, thigh=0.084, calf=0.054, neck=0.046,
             head=1.0, stance=0.1, arms=[(0.09, 0.16, 0.95, 0.0), (0.09, 0.16, 0.95, 0.0)])
    col = dict(thigh=PLUM, shin=DARK, foot=GLV, pelvis=PLUM, neck=DARK, torso=DARK, arm=DARK, fore=PLUM, hand=GLV)
    k = b["h"] / 1.8
    J = f.body(b, col)
    # wide trousers gathered at the calf
    for side, s in (("L", 1), ("R", -1)):
        hip, kn, an = J["hip" + side], J["kn" + side], J["an" + side]
        f.shape([(hip[0] - s * 0.07, hip[1] - 0.06), (hip[0] + s * 0.1, hip[1] + 0.03), (kn[0] + s * 0.13, kn[1] + 0.05), (kn[0] + s * 0.105, kn[1] - 0.2),
                 (an[0] + s * 0.05, an[1] + 0.2), (an[0] - s * 0.05, an[1] + 0.2), (kn[0] - s * 0.075, kn[1] - 0.12)], PLUM)
        f.line([(an[0] - 0.05, an[1] + 0.19), (an[0] + 0.05, an[1] + 0.19)], VIO, 2.2, 0.9, sm=False)
        f.line([(hip[0] + s * 0.03, hip[1] - 0.05), (kn[0] + s * 0.05, kn[1] - 0.12)], shade(PLUM, -0.5), 2, 0.5)
    # cropped mantle with a jagged hem and a raised asymmetric collar
    f.shape([(-0.075, 1.56 * k), (-0.25, 1.47 * k), (-0.29, 1.3 * k), (-0.22, 1.33 * k), (-0.19, 1.22 * k), (-0.12, 1.3 * k), (-0.06, 1.2 * k),
             (0.0, 1.29 * k), (0.07, 1.18 * k), (0.12, 1.3 * k), (0.2, 1.2 * k), (0.22, 1.33 * k), (0.3, 1.28 * k), (0.25, 1.47 * k), (0.075, 1.56 * k)],
            PLUM, sharp=True)
    f.shape([(-0.08, 1.52 * k), (-0.1, 1.62 * k), (-0.04, 1.6 * k), (0.0, 1.52 * k), (0.05, 1.63 * k), (0.12, 1.72 * k), (0.1, 1.52 * k)], DARK, sharp=True)
    f.glow([(-0.2, 1.4 * k), (0.0, 1.36 * k), (0.2, 1.4 * k)], VIO, 2.0)
    f.shape([(-0.13, 1.1 * k), (0.13, 1.1 * k), (0.15, 1.0 * k), (-0.15, 1.0 * k)], GLV, sharp=True)
    for side in ("L", "R"):
        hd = J["hand" + side]
        f.glow([(hd[0] - 0.03, hd[1] - 0.05), (hd[0] + 0.03, hd[1] - 0.05)], VIO, 2.4)
    # blank faceplate with one diagonal slit
    r = f.head(J, b, MASK, face=False)
    f.shape([r(-0.09, 0.02), r(-0.085, 0.1), r(-0.03, 0.14), r(0.04, 0.14), r(0.088, 0.1), r(0.09, 0.02), r(0.06, 0.075), r(0, 0.092), r(-0.06, 0.075)], DARK)   # cowl
    f.glow([r(-0.052, 0.035), r(0.0, 0.005), r(0.055, -0.03)], VIO, 3.4)
    f.line([r(-0.04, -0.07), r(0, -0.085), r(0.04, -0.07)], "#8f8a9c", 1.6, 0.6)
    return J, b


def vexa(f):
    SKIN, WHT, GRA, RED, HAIR, DRK = "#d9ad91", "#e6e7ea", "#3a3c44", "#ff2440", "#b3122a", "#1b1c21"
    b = dict(h=1.76, sw=0.19, cw=0.16, ww=0.118, hw=0.158, arm=0.04, fore=0.036, thigh=0.083, calf=0.054, neck=0.042,
             head=0.97, stance=0.07, hand=0.9, arms=[(0.07, 0.1, 1.0, 0.0), (0.075, 0.11, 1.0, 0.0)])
    col = dict(thigh=DRK, shin=WHT, foot=WHT, pelvis=DRK, neck=SKIN, torso=DRK, arm=SKIN, armR=GRA, fore=SKIN, foreR=WHT,
               hand=SKIN, handR=GRA)
    k = b["h"] / 1.8
    J = f.body(b, col)
    # cropped tech jacket, exposed midriff plating, hip units
    f.shape([(-0.07, 1.52 * k), (0.07, 1.52 * k), (0.19, 1.46 * k), (0.175, 1.3 * k), (0.15, 1.2 * k), (0.03, 1.16 * k), (-0.03, 1.16 * k),
             (-0.15, 1.2 * k), (-0.175, 1.3 * k), (-0.19, 1.46 * k)], WHT)
    f.shape([(-0.03, 1.52 * k), (0.03, 1.52 * k), (0.03, 1.17 * k), (-0.03, 1.17 * k)], GRA, sharp=True)
    f.glow([(0, 1.47 * k), (0, 1.2 * k)], RED, 2.2)
    f.glow([(-0.16, 1.33 * k), (-0.05, 1.3 * k)], RED, 1.8)
    f.glow([(0.16, 1.33 * k), (0.05, 1.3 * k)], RED, 1.8)
    for y in (1.13, 1.085, 1.04):
        f.line([(-0.1, y * k), (0.1, y * k)], "#5a5c66", 3.5, 0.9, sm=False)
    for s in (1, -1):
        f.shape([(s * 0.12, 1.02 * k), (s * 0.19, 1.0 * k), (s * 0.2, 0.88 * k), (s * 0.13, 0.86 * k)], WHT, sharp=True)
        f.glow([(s * 0.15, 0.97 * k), (s * 0.17, 0.9 * k)], RED, 1.6)
    # mechanical right arm: big forearm emitter; mechanical lower legs
    sh, el, wr = J["shR"], J["elR"], J["wrR"]
    f.shape([(sh[0] + 0.05, sh[1] + 0.06), (sh[0] - 0.06, sh[1] + 0.07), (sh[0] - 0.085, sh[1] - 0.03), (sh[0] - 0.03, sh[1] - 0.09), (sh[0] + 0.05, sh[1] - 0.05)], WHT, sharp=True)
    f.shape([(el[0] - 0.07, el[1] + 0.02), (el[0] + 0.06, el[1] + 0.03), (wr[0] + 0.05, wr[1] + 0.02), (wr[0] - 0.075, wr[1] + 0.0), (wr[0] - 0.095, wr[1] + 0.12)], WHT, sharp=True)
    f.glow([(el[0] - 0.045, el[1] - 0.04), (wr[0] - 0.05, wr[1] + 0.06)], RED, 2.6)
    f.ell((wr[0] - 0.005, wr[1] + 0.1), 0.018, 0.018, DRK)
    for side in ("L", "R"):
        kn, an = J["kn" + side], J["an" + side]
        f.shape([(kn[0] - 0.055, kn[1] + 0.07), (kn[0] + 0.055, kn[1] + 0.07), (kn[0] + 0.035, kn[1] - 0.03), (kn[0] - 0.035, kn[1] - 0.03)], GRA, sharp=True)
        f.glow([(kn[0], kn[1] - 0.06), (an[0], an[1] + 0.08)], RED, 1.8)
        f.line([(an[0] - 0.045, an[1] + 0.05), (an[0] + 0.045, an[1] + 0.05)], GRA, 5, 1, sm=False)
    r = f.head(J, b, SKIN, stern=0.9, brow="#7a1020", eye="#40444c")
    f.shape([r(-0.09, -0.07), r(-0.095, 0.06), r(-0.05, 0.14), r(0.03, 0.155), r(0.09, 0.11), r(0.095, 0.0), r(0.11, -0.1), r(0.078, -0.03),
             r(0.07, 0.06), r(0.0, 0.09), r(-0.05, 0.04), r(-0.072, -0.02)], HAIR)                                # asymmetric bob
    f.shape([r(0.012, 0.022), r(0.062, 0.022), r(0.066, -0.006), r(0.016, -0.006)], "#2a0a10", sharp=True, sw=1.4, form=False)   # monocle visor
    f.glow([r(0.02, 0.008), r(0.058, 0.008)], RED, 2.0)
    return J, b


def ryuen(f):
    SKIN, IND, CRM, GOLD, GREY, SASH = "#c49a74", "#22304a", "#e6dcc6", "#ffc94a", "#c9c9c4", "#7a5a1e"
    b = dict(h=1.75, sw=0.2, cw=0.17, ww=0.145, hw=0.16, arm=0.04, fore=0.038, thigh=0.082, calf=0.052, neck=0.046,
             head=1.0, stance=0.075, arms=[(0.065, 0.085, 1.0, 0.0), (0.065, 0.085, 1.0, 0.0)])
    col = dict(thigh=CRM, shin=CRM, foot="#3a2c22", pelvis=CRM, neck=SKIN, torso=CRM, arm=CRM, fore=CRM, hand=SKIN)
    k = b["h"] / 1.8
    J = f.body(b, col)
    # wide trousers bound at the ankle
    for side, s in (("L", 1), ("R", -1)):
        hip, kn, an = J["hip" + side], J["kn" + side], J["an" + side]
        f.shape([(hip[0] - s * 0.075, hip[1] - 0.08), (hip[0] + s * 0.1, hip[1]), (kn[0] + s * 0.11, kn[1]), (an[0] + s * 0.085, an[1] + 0.13),
                 (an[0] + s * 0.04, an[1] + 0.06), (an[0] - s * 0.045, an[1] + 0.06), (an[0] - s * 0.07, an[1] + 0.16), (kn[0] - s * 0.08, kn[1])], CRM)
        f.line([(an[0] - 0.05, an[1] + 0.07), (an[0] + 0.05, an[1] + 0.07)], GOLD, 3, 0.95, sm=False)
        # wide inner sleeves
        el, wr = J["el" + side], J["wr" + side]
        f.shape([(el[0] - s * 0.045, el[1] + 0.05), (el[0] + s * 0.06, el[1] + 0.04), (wr[0] + s * 0.1, wr[1] + 0.02), (wr[0] + s * 0.07, wr[1] - 0.05),
                 (wr[0] - s * 0.06, wr[1] + 0.01)], CRM)
        f.line([(wr[0] + s * 0.09, wr[1] + 0.012), (wr[0] - s * 0.05, wr[1] + 0.02)], GOLD, 2.4, 0.9, sm=False)
    # long sleeveless outer robe, open at the front, to the shin
    for s in (1, -1):
        f.shape([(s * 0.03, 1.52 * k), (s * 0.215, 1.47 * k), (s * 0.2, 1.3 * k), (s * 0.17, 1.08 * k), (s * 0.22, 0.6 * k), (s * 0.2, 0.3 * k),
                 (s * 0.09, 0.27 * k), (s * 0.075, 0.9 * k), (s * 0.05, 1.1 * k)], IND)
        f.line([(s * 0.035, 1.5 * k), (s * 0.055, 1.1 * k), (s * 0.082, 0.9 * k), (s * 0.095, 0.29 * k)], GOLD, 2.6, 0.95)
    f.shape([(-0.175, 1.11 * k), (0.175, 1.11 * k), (0.18, 0.99 * k), (-0.18, 0.99 * k)], SASH, sharp=True)        # broad sash
    f.glow([(-0.17, 1.05 * k), (0.17, 1.05 * k)], GOLD, 1.8)
    f.shape([(0.05, 0.99 * k), (0.1, 0.99 * k), (0.12, 0.72 * k), (0.07, 0.7 * k)], SASH, sharp=True)
    r = f.head(J, b, SKIN, stern=0.9, brow=GREY, eye="#2a2018")
    f.shape([r(-0.08, 0.035), r(-0.078, 0.095), r(-0.03, 0.135), r(0.03, 0.135), r(0.078, 0.095), r(0.08, 0.035), r(0.04, 0.09), r(-0.04, 0.09)], GREY)   # receding hair
    f.ell(r(0, 0.155), 0.024, 0.028, GREY)                                                                  # knot
    f.line([r(-0.02, 0.13), r(0.02, 0.13)], GOLD, 3, 0.95, sm=False)
    f.shape([r(-0.045, -0.06), r(-0.02, -0.052), r(0, -0.058), r(0.02, -0.052), r(0.045, -0.06), r(0.035, -0.12), r(0.012, -0.2),
             r(0, -0.23), r(-0.012, -0.2), r(-0.035, -0.12)], GREY)                                          # long narrow beard
    f.line([r(-0.018, -0.07), r(0.018, -0.07)], "#7a5a48", 2.2, 0.9, sm=False)
    for s in (1, -1):
        f.line([r(s * 0.045, -0.012), r(s * 0.062, -0.004)], "#7a5a48", 1.4, 0.5, sm=False)                # crow's feet
    return J, b


ROSTER = [
    ("kairo", "KAIRO", "The Exiled", kairo, ["#26282f", "#3a3d47", "#6d1512", "#b98263", "#ff2a1f"],
     ["Shape: upright triangle — balanced, athletic V-taper, 1.80 m",
      "Asymmetry: one bare arm with glowing Origin scar-lines, one sleeved arm with a forearm guard",
      "High-collar exile jacket with a diagonal closure; torn sash at the hip",
      "Undercut hair swept to one side with a single crimson streak; scar under the eye",
      "Red is used sparingly: seam, scars, streak"]),
    ("drakon", "DRAKON", "The Destroyer", drakon, ["#4a4541", "#6b6560", "#2a2623", "#7b4f38", "#ff7a1a"],
     ["Shape: heavy inverted trapezoid — the widest, tallest fighter, 1.98 m",
      "Bare chest under a crossed harness with a furnace core at the sternum",
      "One oversized pauldron; piston gauntlets twice the size of his hands",
      "Plated kilt and boots — weight sits low, small head sells the scale",
      "Orange glow only in the core and gauntlet vents"]),
    ("seraphina", "SERAPHINA", "The Ghost", seraphina, ["#e8ecf4", "#b9c8e0", "#27324a", "#e3bfa6", "#6fd0ff"],
     ["Shape: tall narrow diamond — slim, long-legged, 1.72 m",
      "Layered half-coat: long trailing panels that follow her movement",
      "Light chest armour and a single shoulder guard; silver greaves",
      "White hair with a side-swept fringe and long ponytail — a second moving silhouette",
      "Blue-white glow in thin lines only"]),
    ("nox", "NOX", "The Shadow", nox, ["#16131d", "#2b2038", "#c9c5d2", "#0e0c13", "#a04bff"],
     ["Shape: compact and low, wide stance, 1.68 m — the smallest fighter",
      "Blank pale faceplate with one diagonal violet slit: no eyes, no mouth",
      "Cropped mantle with a jagged hem and a lopsided raised collar",
      "Wide trousers gathered at the calf; arms held away from the body",
      "Violet glow on the slit, mantle seam and fingertips"]),
    ("vexa", "VEXA", "The Machine", vexa, ["#e6e7ea", "#3a3c44", "#1b1c21", "#b3122a", "#ff2440"],
     ["Shape: clean human silhouette with hard mechanical edges, 1.76 m",
      "Mechanical right arm with an oversized forearm emitter",
      "Cropped white tech jacket, plated midriff, hip units, mechanical lower legs",
      "Asymmetric red bob; a visor over one eye",
      "Red light traces every mechanical part"]),
    ("ryuen", "RYUEN", "The Ancient", ryuen, ["#22304a", "#e6dcc6", "#7a5a1e", "#c9c9c4", "#ffc94a"],
     ["Shape: long calm column — robe hem widens the base, 1.75 m",
      "Sleeveless indigo outer robe over cream wide-sleeved tunic",
      "Broad sash with a hanging end; trousers bound at the ankle",
      "Grey hair in a small knot, long narrow beard",
      "Gold only as trim: robe edge, cuffs, sash line"]),
]


def sheet(out, entry):
    fid, name, title, fn, palette, notes = entry
    cv = Canvas(1800, 1300)
    cv.add('<ellipse cx="560" cy="1190" rx="330" ry="34" fill="#000" opacity="0.45" filter="url(#soft)"/>')
    cv.add('<line x1="120" y1="1190" x2="1000" y2="1190" stroke="#3a3c46" stroke-width="2"/>')
    fig = Fig(cv, 560, 1190, PX)
    _J, b = fn(fig)
    # height ruler
    for m in (0.5, 1.0, 1.5, 2.0):
        y = 1190 - m * PX
        cv.add(f'<line x1="120" y1="{y}" x2="150" y2="{y}" stroke="#5a5c66" stroke-width="2"/>')
        cv.text(160, y + 7, f"{m:.1f} m", 20, "#7c7e88")
    cv.text(1060, 130, name, 92, "#ffffff", "bold", spacing=6)
    cv.text(1064, 180, title.upper(), 30, palette[-1], "bold", spacing=8)
    cv.text(1064, 228, f"Height {b['h']:.2f} m   ·   concept v1 — for approval", 22, "#8d8f99")
    y = 300
    cv.text(1064, y, "DESIGN NOTES", 22, "#8d8f99", "bold", spacing=3)
    for n in notes:
        y += 44
        cv.add(f'<circle cx="1072" cy="{y - 8}" r="4" fill="{palette[-1]}"/>')
        # wrap at ~52 chars
        words, line, lines = n.split(), "", []
        for w in words:
            if len(line) + len(w) > 50:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        lines.append(line)
        for i, ln in enumerate(lines):
            cv.text(1092, y + i * 30, ln, 23, "#dcdde3")
        y += (len(lines) - 1) * 30
    cv.text(1064, 700, "PALETTE", 22, "#8d8f99", "bold", spacing=3)
    for i, c in enumerate(palette):
        cv.add(f'<rect x="{1064 + i * 118}" y="722" width="104" height="70" rx="8" fill="{c}" stroke="#00000055"/>')
    cv.text(1064, 870, "SILHOUETTE TEST", 22, "#8d8f99", "bold", spacing=3)
    cv.add('<rect x="1064" y="890" width="660" height="350" rx="12" fill="#d9dae0"/>')
    fn(Fig(cv, 1394, 1225, 158, sil=True))
    cv.save(f"{out}/concept_{fid}.svg")


def lineup(out):
    cv = Canvas(2600, 1420)
    cv.text(70, 90, "VANGUARD: BLOODLINE", 54, "#ffffff", "bold", spacing=5)
    cv.text(72, 132, "ROSTER CONCEPT LINE-UP  ·  v1 for approval  ·  heights to scale", 24, "#8d8f99", spacing=2)
    g = 1010
    cv.add(f'<line x1="60" y1="{g}" x2="2540" y2="{g}" stroke="#3a3c46" stroke-width="2"/>')
    S = 415
    for i, (fid, name, title, fn, palette, _n) in enumerate(ROSTER):
        x = 250 + i * 420
        cv.add(f'<ellipse cx="{x}" cy="{g}" rx="150" ry="16" fill="#000" opacity="0.5" filter="url(#soft)"/>')
        _J, b = fn(Fig(cv, x, g, S))
        cv.text(x, g + 56, name, 34, "#ffffff", "bold", "middle", 3)
        cv.text(x, g + 88, f"{title}  ·  {b['h']:.2f} m", 20, palette[-1], "normal", "middle")
    cv.add('<rect x="60" y="1120" width="2480" height="280" rx="12" fill="#d9dae0"/>')
    cv.text(84, 1152, "SILHOUETTE TEST", 18, "#5a5c66", "bold", spacing=3)
    for i, (_fid, _name, _title, fn, _p, _n) in enumerate(ROSTER):
        fn(Fig(cv, 250 + i * 420, 1390, 128, sil=True))
    cv.save(f"{out}/concept_lineup.svg")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/art"
    os.makedirs(out, exist_ok=True)
    only = sys.argv[2] if len(sys.argv) > 2 else ""
    for e in ROSTER:
        if not only or only == e[0]:
            sheet(out, e)
    if not only or only == "lineup":
        lineup(out)


if __name__ == "__main__":
    main()
