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
        self.n = 0
        self.out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            '<defs>'
            '<linearGradient id="form" x1="0" y1="0" x2="1" y2="0.25">'
            '<stop offset="0" stop-color="#fff" stop-opacity="0.10"/>'
            '<stop offset="0.45" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.6" stop-color="#000" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0.22"/></linearGradient>'
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

    def __init__(self, cv, ox, ground, scale=PX, sil=False, ink=False):
        # ink=True draws only a heavy contour; run it before the colour pass
        # so the figure gets a bold outer line and thin inner lines.
        self.cv, self.ox, self.gy, self.S, self.sil, self.ink = cv, ox, ground, scale, sil, ink

    def P(self, p):
        return (self.ox + p[0] * self.S, self.gy - p[1] * self.S)

    def _emit(self, d, fill, stroke=None, sw=2.4, form=True, opacity=1.0, cel=1.0, box=None):
        if self.sil:
            self.cv.add(f'<path d="{d}" fill="#0b0b0e" stroke="#0b0b0e" stroke-width="2"/>')
            return
        k = self.S / PX
        if self.ink:
            self.cv.add(f'<path d="{d}" fill="#08080b" stroke="#08080b" stroke-width="{9 * k:.2f}" stroke-linejoin="round"/>')
            return
        stroke = stroke or shade(fill, -0.62)
        op = f' opacity="{opacity}"' if opacity < 1 else ""
        self.cv.n += 1
        i = self.cv.n
        self.cv.add(f'<defs><path id="p{i}" d="{d}"/></defs><use xlink:href="#p{i}" fill="{fill}"{op}/>')
        if form and cel > 0 and box:
            # Cel shading: light from the upper left. A shadow crescent on the
            # lower-right edge and a thin highlight on the upper-left edge.
            x0, y0, x1, y1 = box
            pad = 30 * k
            rect = f'x="{x0 - pad:.0f}" y="{y0 - pad:.0f}" width="{x1 - x0 + 2 * pad:.0f}" height="{y1 - y0 + 2 * pad:.0f}"'
            size = min(x1 - x0, y1 - y0)
            sx, sy = min(11 * k, size * 0.2) * cel, min(7 * k, size * 0.13) * cel
            hx, hy = min(4.5 * k, size * 0.08) * cel, min(3.5 * k, size * 0.06) * cel
            sr, sg, sb = hex_to_rgb(shade(fill, -0.42))
            shadow = "#%02x%02x%02x" % (int(sr * 0.86 + 5), int(sg * 0.84 + 3), int(sb * 0.9 + 14))
            self.cv.add(f'<mask id="s{i}" maskUnits="userSpaceOnUse" {rect}><rect {rect} fill="#fff"/>'
                        f'<use xlink:href="#p{i}" transform="translate({-sx:.1f},{-sy:.1f})" fill="#000"/></mask>'
                        f'<use xlink:href="#p{i}" fill="{shadow}" mask="url(#s{i})"{op}/>')
            self.cv.add(f'<mask id="h{i}" maskUnits="userSpaceOnUse" {rect}><rect {rect} fill="#fff"/>'
                        f'<use xlink:href="#p{i}" transform="translate({hx:.1f},{hy:.1f})" fill="#000"/></mask>'
                        f'<use xlink:href="#p{i}" fill="{shade(fill, 0.3)}" mask="url(#h{i})"{op}/>')
            self.cv.add(f'<use xlink:href="#p{i}" fill="url(#form)"{op}/>')
        self.cv.add(f'<use xlink:href="#p{i}" fill="none" stroke="{stroke}" stroke-width="{sw * k:.2f}" stroke-linejoin="round"{op}/>')

    def shape(self, pts, fill, sharp=False, **kw):
        q = [self.P(p) for p in pts]
        d = ("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in q) + " Z") if sharp else smooth(q)
        xs, ys = [x for x, _ in q], [y for _, y in q]
        self._emit(d, fill, box=(min(xs), min(ys), max(xs), max(ys)), **kw)

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
        if self.sil or self.ink:
            return
        q = [self.P(p) for p in pts]
        d = smooth(q, closed=False) if sm and len(q) > 2 else "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in q)
        self.cv.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w * self.S / PX:.2f}" '
                    f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"/>')

    def glow(self, pts, color, w=4.0, closed=False):
        """Origin-energy accent: bright core over a soft halo."""
        if self.sil or self.ink:
            return
        q = [self.P(p) for p in pts]
        d = smooth(q, closed=closed) if len(q) > 2 else "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in q)
        k = self.S / PX
        self.cv.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w * 2.6 * k:.2f}" stroke-linecap="round" '
                    f'filter="url(#glow)" opacity="0.85"/>')
        self.cv.add(f'<path d="{d}" fill="none" stroke="{shade(color, 0.55)}" stroke-width="{w * k:.2f}" stroke-linecap="round"/>')

    # ------------------------------------------------------------ body ----
    def body(self, b, col):
        """Legs, pelvis, neck and torso (arms are drawn later by arms(), so a
        raised guard sits in front of the costume). b: proportions and pose,
        col: colour per body part. Returns the joints for costume overlays.
        Pose: b["armL"/"armR"] = (elbow x, elbow y, wrist x, wrist y) relative
        to the shoulder, x outward; b["legL"/"legR"] = (knee x out from the
        hip, knee height, ankle x out from the hip)."""
        k = b["h"] / 1.8
        sw, cw, ww, hw = b["sw"], b["cw"], b["ww"], b["hw"]
        J = {"k": k}
        for s, side in ((1, "L"), (-1, "R")):   # the figure's left is on the viewer's right
            ex, ey, wx, wy = b.get("arm" + side, (0.08, -0.3, 0.115, -0.56))
            sh = (s * sw, 1.455 * k)
            J["sh" + side] = sh
            J["el" + side] = (sh[0] + s * ex * k, sh[1] + ey * k)
            J["wr" + side] = (sh[0] + s * wx * k, sh[1] + wy * k)
            kx, ky, ax = b.get("leg" + side, (0.05, 0.52, 0.1))
            hx = s * hw * 0.56
            J["hip" + side] = (hx, 0.95 * k)
            J["kn" + side] = (hx + s * kx, ky * k)
            J["an" + side] = (hx + s * ax, 0.09 * k)
        J["head"] = (b.get("tilt", 0.0), 1.69 * k)
        th, cf = b["thigh"], b["calf"]
        fs = b.get("foot", 1.2)
        for s, side in ((1, "L"), (-1, "R")):
            hip, kn, an = J["hip" + side], J["kn" + side], J["an" + side]
            self.limb(hip, kn, [(0, th * 1.02), (0.22, th * 1.16, th * 1.08) if s > 0 else (0.22, th * 1.08, th * 1.16),
                                (0.55, th * 1.0), (0.82, th * 0.74), (1, th * 0.66)], col["thigh"])
            dk = shade(col["thigh"], -0.55)
            self.line([(hip[0] + s * th * 0.2, hip[1] - 0.1), ((hip[0] + kn[0]) / 2 + s * th * 0.3, (hip[1] + kn[1]) / 2), (kn[0] + s * th * 0.2, kn[1] + 0.09)], dk, 2.2, 0.45)
            self.limb(kn, an, [(0, cf * 0.98), (0.26, cf * (1.3 if s > 0 else 1.05), cf * (1.05 if s > 0 else 1.3)),
                               (0.7, cf * 0.72), (1, cf * 0.58)], col["shin"])
            self.ell(kn, th * 0.6, th * 0.62, col["thigh"], cel=0.7, sw=1.4)
            ax, o = an[0], s * 0.06 * fs
            self.shape([(ax - 0.05 * fs, 0.115 * k), (ax + 0.05 * fs, 0.115 * k), (ax + 0.066 * fs + o, 0.04), (ax + 0.06 * fs + o, 0.0),
                        (ax - 0.05 * fs + o * 0.6, 0.0), (ax - 0.064 * fs + o * 0.3, 0.035)], col["foot"])
            self.line([(ax - 0.05 * fs + o * 0.5, 0.022), (ax + 0.06 * fs + o, 0.022)], shade(col["foot"], -0.7), 2.4, 0.8, sm=False)
        self.shape([(ww, 1.07 * k), (hw, 0.97 * k), (hw * 1.0, 0.89 * k), (hw * 0.45, 0.83 * k), (0, 0.815 * k),
                    (-hw * 0.45, 0.83 * k), (-hw, 0.89 * k), (-hw, 0.97 * k), (-ww, 1.07 * k), (0, 1.09 * k)], col["pelvis"])
        nw = b["neck"]
        self.shape([(nw, 1.6 * k), (nw * 1.1, 1.53 * k), (sw * 0.8, 1.478 * k), (-sw * 0.8, 1.478 * k),
                    (-nw * 1.1, 1.53 * k), (-nw, 1.6 * k)], col["neck"])
        self.shape([(nw * 0.95, 1.6 * k), (nw * 0.2, 1.555 * k), (-nw * 0.95, 1.6 * k), (-nw * 0.6, 1.565 * k), (0, 1.535 * k), (nw * 0.6, 1.565 * k)],
                   shade(col["neck"], -0.45), sw=0.1, form=False)   # shadow under the jaw
        self.shape([(nw * 1.3, 1.5 * k), (sw * 0.96, 1.47 * k), (sw * 1.0, 1.4 * k), (cw, 1.31 * k), (cw * 0.95, 1.2 * k),
                    (ww, 1.08 * k), (ww * 1.03, 1.02 * k), (0, 1.0 * k), (-ww * 1.03, 1.02 * k), (-ww, 1.08 * k),
                    (-cw * 0.95, 1.2 * k), (-cw, 1.31 * k), (-sw, 1.4 * k), (-sw * 0.96, 1.47 * k), (-nw * 1.3, 1.5 * k),
                    (0, 1.49 * k)], col["torso"])
        return J

    def muscles(self, J, b, skin):
        """Chest, abdominal and serratus drawing for a bare torso."""
        k, cw = J["k"], b["cw"]
        d = shade(skin, -0.5)
        for s in (1, -1):
            self.shape([(s * 0.012, 1.45 * k), (s * cw * 0.6, 1.455 * k), (s * cw * 0.98, 1.37 * k), (s * cw * 0.86, 1.28 * k),
                        (s * cw * 0.4, 1.262 * k), (s * 0.012, 1.285 * k)], shade(skin, 0.06), sw=1.8, cel=1.3)   # pectoral
            for i, y in enumerate((1.225, 1.16, 1.095)):
                wdt = cw * (0.38 - i * 0.025)
                self.shape([(s * 0.01, (y + 0.026) * k), (s * wdt, (y + 0.03) * k), (s * wdt * 1.02, (y - 0.024) * k), (s * 0.01, (y - 0.028) * k)],
                           shade(skin, 0.03), sw=1.3, cel=0.9)
            for i in range(3):
                y = 1.25 - i * 0.045
                self.line([(s * cw * 0.9, y * k), (s * cw * 0.62, (y - 0.03) * k)], d, 2.0, 0.5, sm=False)
            self.line([(s * b["ww"] * 0.95, 1.08 * k), (s * b["ww"] * 0.55, 1.03 * k)], d, 2.2, 0.5, sm=False)

    def arms(self, J, b, col):
        k, ua, fa = J["k"], b["arm"], b["fore"]
        for s, side in ((1, "L"), (-1, "R")):
            sh, el, wr = J["sh" + side], J["el" + side], J["wr" + side]
            c = col.get("arm" + side, col["arm"])
            f = col.get("fore" + side, col["fore"])
            hc = col.get("hand" + side, col["hand"])
            self.limb(sh, el, [(0, ua * 1.2), (0.3, ua * 1.12), (0.55, ua * 1.2, ua * 1.02) if s < 0 else (0.55, ua * 1.02, ua * 1.2),
                               (1, ua * 0.8)], c, cap=0.9)
            self.ell((sh[0] + s * ua * 0.25, sh[1] - ua * 0.25), ua * 1.42, ua * 1.5, c, sw=1.6)         # deltoid
            dk = shade(c, -0.55)
            self.line([(sh[0] - s * ua * 0.5, sh[1] - ua * 1.6), ((sh[0] + el[0]) / 2, (sh[1] + el[1]) / 2 - ua * 0.2)], dk, 2.0, 0.5, sm=False)
            self.limb(el, wr, [(0, fa * 1.0), (0.22, fa * 1.28, fa * 1.12) if s > 0 else (0.22, fa * 1.12, fa * 1.28),
                               (0.75, fa * 0.74), (1, fa * 0.62)], f)
            self.ell(el, fa * 0.95, fa * 0.95, f, cel=0.7, sw=1.4)
            # fist along the forearm direction
            dx, dy = wr[0] - el[0], wr[1] - el[1]
            L = math.hypot(dx, dy) or 1e-6
            ux, uy = dx / L, dy / L
            nx, ny = -uy, ux
            hs = 0.052 * b.get("hand", 1.25) * k
            cx, cy = wr[0] + ux * hs * 1.15, wr[1] + uy * hs * 1.15
            Q = lambda a, c2: (cx + ux * a * hs + nx * c2 * hs, cy + uy * a * hs + ny * c2 * hs)   # noqa: E731
            self.shape([Q(-1.0, 0.85), Q(0.35, 1.02), Q(1.0, 0.8), Q(1.1, -0.75), Q(0.4, -1.02), Q(-1.0, -0.85)], hc)
            for i in (-0.45, 0.0, 0.45):
                self.line([Q(1.05, i), Q(0.3, i)], shade(hc, -0.65), 1.8, 0.75, sm=False)
            self.line([Q(0.3, -0.9), Q(0.3, 0.9)], shade(hc, -0.65), 1.6, 0.5, sm=False)
            J["hand" + side] = (cx, cy)

    def head(self, J, b, skin, face=True, brow="#1a1412", eye="#3a2a1c", stern=1.0, jaw=1.0):
        k, hs = J["k"], b["head"]
        cx, cy = J["head"]
        r = lambda x, y: (cx + x * hs * k, cy + y * hs * k)   # noqa: E731
        for s in (1, -1):
            self.ell(r(s * 0.084, -0.004), 0.012 * hs * k, 0.026 * hs * k, shade(skin, -0.12))
        j = jaw
        self.shape([r(0, 0.118), r(0.052, 0.105), r(0.078, 0.05), r(0.079, -0.015), r(0.068 * j, -0.072), r(0.036 * j, -0.11),
                    r(0, -0.12), r(-0.036 * j, -0.11), r(-0.068 * j, -0.072), r(-0.079, -0.015), r(-0.078, 0.05), r(-0.052, 0.105)], skin)
        if not face or self.sil or self.ink:
            return r
        sh1, dk = shade(skin, -0.3), shade(skin, -0.5)
        # planes of the face: eye sockets, cheek hollow on the shadow side, nose, under-lip
        self.shape([r(-0.066, 0.03), r(0.0, 0.022), r(0.066, 0.03), r(0.062, -0.004), r(0.02, -0.008), r(0, 0.0), r(-0.02, -0.008), r(-0.062, -0.004)],
                   sh1, sw=0.1, form=False, opacity=0.55)
        self.shape([r(0.074, 0.0), r(0.05, -0.03), r(0.045, -0.075), r(0.066, -0.07), r(0.078, -0.02)], sh1, sw=0.1, form=False, opacity=0.7)
        self.shape([r(0.002, 0.012), r(0.018, -0.03), r(0.012, -0.043), r(0.0, -0.036)], sh1, sw=0.1, form=False, opacity=0.8)
        self.shape([r(-0.02, -0.084), r(0.02, -0.084), r(0.012, -0.094), r(-0.012, -0.094)], sh1, sw=0.1, form=False, opacity=0.6)
        for s in (1, -1):
            ex = s * 0.034
            self.shape([r(ex - s * 0.024, 0.028 - 0.009 * stern), r(ex - s * 0.005, 0.04), r(ex + s * 0.028, 0.038), r(ex + s * 0.027, 0.03),
                        r(ex - s * 0.004, 0.03), r(ex - s * 0.022, 0.02 - 0.009 * stern)], brow, sw=0.6, form=False)
            self.shape([r(ex - 0.021, 0.006), r(ex - 0.004, 0.0165), r(ex + 0.021, 0.008), r(ex + 0.002, -0.003)], "#efeae0", sw=1.2, form=False)
            self.ell(r(ex + 0.001, 0.007), 0.008 * hs * k, 0.008 * hs * k, eye, sw=1.0, form=False)
            self.ell(r(ex + 0.001, 0.007), 0.0035 * hs * k, 0.0035 * hs * k, "#050505", sw=0.2, form=False)
            self.ell(r(ex - 0.002, 0.0098), 0.0016 * hs * k, 0.0016 * hs * k, "#ffffff", sw=0.1, form=False)
            self.line([r(ex - 0.023, 0.006), r(ex - 0.004, 0.018), r(ex + 0.023, 0.009)], "#0e0a09", 3.2, 1.0)
        self.line([r(-0.011, -0.041), r(0.002, -0.046), r(0.014, -0.04)], dk, 2.2, 0.7)
        self.line([r(-0.026, -0.068), r(-0.008, -0.072), r(0.008, -0.071), r(0.026, -0.067)], shade(skin, -0.68), 3.0, 0.95)
        self.shape([r(-0.016, -0.074), r(0.016, -0.074), r(0.01, -0.082), r(-0.01, -0.082)], shade(skin, -0.14), sw=0.1, form=False, opacity=0.9)
        return r


def backdrop(cv, x, ground, color, scale=1.0):
    """Brush-stroke energy burst behind a figure."""
    pts = [(-330, -160), (-180, -700), (-40, -980), (120, -760), (300, -1010), (250, -560), (370, -240), (140, -60), (-150, -20)]
    q = [(x + px * scale, ground + py * scale) for px, py in pts]
    cv.add(f'<path d="{smooth(q)}" fill="{color}" opacity="0.16" filter="url(#soft)"/>')
    for i, (dx, w) in enumerate(((-250, 26), (-120, 12), (210, 18), (300, 8))):
        x0, y0 = x + dx * scale, ground - (240 + i * 70) * scale
        cv.add(f'<path d="M{x0:.0f},{y0:.0f} L{x0 + 150 * scale:.0f},{y0 - 520 * scale:.0f} L{x0 + (150 + w) * scale:.0f},{y0 - 500 * scale:.0f} Z" '
               f'fill="{color}" opacity="0.13"/>')


# ---------------------------------------------------------------- roster --
def kairo(f):
    SKIN, JKT, JKT2, PANT, BOOT, RED = "#b98263", "#2a2c34", "#434652", "#1d1e24", "#2e2725", "#ff2a1f"
    # Fighting stance: lead fist out low, rear fist by the jaw, weight on bent legs.
    b = dict(h=1.80, sw=0.235, cw=0.2, ww=0.138, hw=0.165, arm=0.062, fore=0.056, thigh=0.098, calf=0.066, neck=0.058,
             head=0.94, hand=1.35, armL=(0.13, -0.2, 0.2, 0.0), armR=(0.17, -0.2, 0.2, 0.04),
             legL=(0.13, 0.51, 0.27), legR=(0.1, 0.52, 0.2), tilt=0.012)
    col = dict(thigh=PANT, shin=PANT, foot=BOOT, pelvis=PANT, neck=SKIN, torso=JKT, arm=SKIN, armL=JKT, fore=SKIN,
               foreL=JKT2, hand=SKIN, handL="#1b1c21")
    f.shape([(-0.15, 1.02), (-0.24, 0.98), (-0.42, 0.66), (-0.36, 0.5), (-0.3, 0.64), (-0.25, 0.52), (-0.14, 0.9)], "#7d1814")   # exile sash, blown back
    f.shape([(-0.14, 1.0), (-0.2, 0.94), (-0.3, 0.74), (-0.24, 0.7), (-0.12, 0.92)], "#5b100d")
    J = f.body(b, col)
    for side, s in (("L", 1), ("R", -1)):
        kn, an = J["kn" + side], J["an" + side]
        f.shape([(kn[0] - 0.062, kn[1] + 0.085), (kn[0] + 0.062, kn[1] + 0.085), (kn[0] + 0.052, kn[1] - 0.06), (kn[0], kn[1] - 0.09), (kn[0] - 0.052, kn[1] - 0.06)], JKT2)
        for i in range(4):   # bound shins
            t = 0.5 + i * 0.12
            cx, cy = kn[0] + (an[0] - kn[0]) * t, kn[1] + (an[1] - kn[1]) * t
            w = 0.062 - i * 0.004
            f.shape([(cx - w, cy + 0.02), (cx + w, cy + 0.028), (cx + w, cy - 0.008), (cx - w, cy - 0.016)], "#4a4c57", sw=1.4, cel=0.6)
    # jacket: high collar, diagonal closure, long split tail over the hips
    f.shape([(0.0, 1.5), (0.08, 1.52), (0.225, 1.465), (0.215, 1.3), (0.15, 1.1), (0.17, 0.96), (0.08, 0.86), (0.02, 0.95), (-0.07, 0.9),
             (-0.165, 0.99), (-0.15, 1.1), (-0.21, 1.3), (-0.225, 1.43), (-0.08, 1.52)], JKT)
    f.shape([(-0.075, 1.52), (0.02, 1.47), (0.125, 1.2), (0.105, 0.94), (0.17, 0.96), (0.15, 1.1), (0.215, 1.3), (0.225, 1.465), (0.08, 1.52)], JKT2)
    f.line([(-0.19, 1.3), (-0.09, 1.25), (-0.02, 1.27)], "#0e0f12", 2.4, 0.6)             # chest fold
    f.line([(-0.14, 1.12), (-0.06, 1.16), (0.02, 1.13)], "#0e0f12", 2.2, 0.5)
    f.shape([(-0.068, 1.615), (-0.085, 1.52), (0.0, 1.47), (0.085, 1.52), (0.068, 1.615), (0.035, 1.55), (-0.035, 1.55)], JKT2)
    f.glow([(0.022, 1.46), (0.12, 1.2), (0.1, 0.96)], RED, 2.8)
    f.shape([(-0.165, 1.05), (0.17, 1.035), (0.17, 0.985), (-0.165, 1.0)], "#101013", sharp=True)
    f.shape([(-0.035, 1.055), (0.035, 1.052), (0.035, 0.98), (-0.035, 0.983)], "#6a6c75", sharp=True)
    f.arms(J, b, col)
    elL, wrL = J["elL"], J["wrL"]
    f.limb(elL, wrL, [(0.12, 0.07), (0.5, 0.066), (0.92, 0.05)], "#565a66", cap=0.2)        # forearm guard
    f.line([(elL[0] + 0.02, elL[1] + 0.04), (wrL[0] - 0.01, wrL[1] - 0.03)], "#22242a", 2.4, 0.9, sm=False)
    shR, elR, wrR = J["shR"], J["elR"], J["wrR"]
    f.shape([(shR[0] + 0.07, shR[1] + 0.07), (shR[0] - 0.09, shR[1] + 0.05), (shR[0] - 0.1, shR[1] - 0.03), (shR[0] - 0.05, shR[1] - 0.075),
             (shR[0] - 0.015, shR[1] - 0.04), (shR[0] + 0.03, shR[1] - 0.085), (shR[0] + 0.06, shR[1] - 0.03)], JKT2, sharp=True)   # torn shoulder
    f.glow([(shR[0] - 0.03, shR[1] - 0.1), (shR[0] - 0.07, shR[1] - 0.17), (elR[0] + 0.01, elR[1] + 0.05), (elR[0] + 0.03, elR[1] - 0.0)], RED, 2.2)
    f.glow([(elR[0] + 0.03, elR[1] + 0.0), (elR[0] + 0.07, elR[1] + 0.07), (wrR[0] - 0.03, wrR[1] - 0.06)], RED, 2.2)
    f.glow([(elR[0] + 0.07, elR[1] + 0.07), (elR[0] + 0.1, elR[1] + 0.04)], RED, 1.6)
    r = f.head(J, b, SKIN, stern=1.6, jaw=1.06)
    f.shape([r(-0.083, 0.02), r(-0.088, 0.09), r(-0.05, 0.15), r(0.03, 0.175), r(0.1, 0.15), r(0.125, 0.085), r(0.086, 0.03),
             r(0.075, 0.08), r(0.02, 0.1), r(-0.03, 0.08), r(-0.064, 0.045)], "#17120f")
    f.shape([r(-0.03, 0.08), r(-0.005, 0.158), r(0.045, 0.172), r(0.015, 0.1)], "#b31d16", sw=1.2)
    f.line([r(-0.06, 0.1), r(-0.01, 0.15), r(0.06, 0.15)], "#3a2f2a", 2.0, 0.8)
    f.line([r(0.03, 0.105), r(0.075, 0.13), r(0.11, 0.1)], "#3a2f2a", 2.0, 0.8)
    f.line([r(0.04, -0.012), r(0.054, -0.04)], "#6a2a20", 2.6, 0.9)
    return J, b


def drakon(f):
    SKIN, IRON, IRON2, PANT, ORG, SOOT = "#7b4f38", "#4f4a46", "#77706a", "#2a2623", "#ff7a1a", "#1b1816"
    b = dict(h=1.98, sw=0.31, cw=0.28, ww=0.2, hw=0.2, arm=0.09, fore=0.085, thigh=0.122, calf=0.084, neck=0.08,
             head=0.9, hand=1.75, foot=1.4, armL=(0.19, -0.22, 0.25, -0.5), armR=(0.19, -0.22, 0.25, -0.5),
             legL=(0.12, 0.52, 0.24), legR=(0.12, 0.52, 0.24))
    col = dict(thigh=PANT, shin=IRON, foot=IRON, pelvis=PANT, neck=SKIN, torso=SKIN, arm=SKIN, fore=IRON, hand=IRON2)
    k = b["h"] / 1.8
    J = f.body(b, col)
    f.muscles(J, b, SKIN)
    f.shape([(-0.26, 1.47 * k), (-0.19, 1.5 * k), (0.035, 1.31 * k), (-0.035, 1.26 * k)], SOOT, sharp=True)
    f.shape([(0.26, 1.47 * k), (0.19, 1.5 * k), (-0.035, 1.31 * k), (0.035, 1.26 * k)], SOOT, sharp=True)
    f.shape([(0, 1.375 * k), (0.07, 1.3 * k), (0, 1.21 * k), (-0.07, 1.3 * k)], IRON2, sharp=True)
    f.glow([(0, 1.34 * k), (0.036, 1.3 * k), (0, 1.25 * k), (-0.036, 1.3 * k)], ORG, 4.4, closed=True)
    f.shape([(-0.215, 1.11 * k), (0.215, 1.11 * k), (0.23, 1.0 * k), (-0.23, 1.0 * k)], IRON, sharp=True)
    for x in (-0.165, 0.0, 0.165):
        f.shape([(x - 0.08, 1.0 * k), (x + 0.08, 1.0 * k), (x + 0.066, 0.77 * k), (x, 0.71 * k), (x - 0.066, 0.77 * k)], IRON2 if x == 0 else IRON, sharp=True)
        f.line([(x, 0.98 * k), (x, 0.75 * k)], SOOT, 2.2, 0.6, sm=False)
    f.glow([(-0.055, 1.055 * k), (0.055, 1.055 * k)], ORG, 3.2)
    for side in ("L", "R"):
        kn, an = J["kn" + side], J["an" + side]
        f.shape([(kn[0] - 0.085, kn[1] + 0.1), (kn[0] + 0.085, kn[1] + 0.1), (kn[0] + 0.07, kn[1] - 0.07), (kn[0], kn[1] - 0.13), (kn[0] - 0.07, kn[1] - 0.07)], IRON2, sharp=True)
        f.shape([(an[0] - 0.085, an[1] + 0.2), (an[0] + 0.085, an[1] + 0.2), (an[0] + 0.08, an[1] + 0.13), (an[0] - 0.08, an[1] + 0.13)], SOOT, sharp=True)
    f.arms(J, b, col)
    sh = J["shR"]
    f.shape([(sh[0] + 0.12, sh[1] + 0.11), (sh[0] - 0.02, sh[1] + 0.2), (sh[0] - 0.19, sh[1] + 0.12), (sh[0] - 0.21, sh[1] - 0.07),
             (sh[0] - 0.08, sh[1] - 0.15), (sh[0] + 0.08, sh[1] - 0.07)], IRON2)
    f.shape([(sh[0] + 0.07, sh[1] + 0.045), (sh[0] - 0.03, sh[1] + 0.11), (sh[0] - 0.14, sh[1] + 0.05), (sh[0] - 0.14, sh[1] - 0.05), (sh[0] - 0.03, sh[1] - 0.03)], IRON)
    for dx, dy in ((-0.15, 0.06), (-0.04, 0.15), (0.06, 0.07)):
        f.ell((sh[0] + dx, sh[1] + dy), 0.012, 0.012, SOOT, cel=0)
    for side, s in (("L", 1), ("R", -1)):
        el, wr = J["el" + side], J["wr" + side]
        f.limb(el, wr, [(0.0, 0.108), (0.5, 0.104), (1.0, 0.094)], IRON, cap=0.1)
        f.limb(el, (el[0] + (wr[0] - el[0]) * 0.22, el[1] + (wr[1] - el[1]) * 0.22), [(0, 0.118), (1, 0.118)], IRON2, cap=0.05)
        f.limb((el[0] + (wr[0] - el[0]) * 0.86, el[1] + (wr[1] - el[1]) * 0.86), wr, [(0, 0.104), (1, 0.104)], SOOT, cap=0.05)
        f.glow([(el[0] + s * 0.035, el[1] - 0.09), (wr[0] + s * 0.03, wr[1] + 0.07)], ORG, 3.0)
        f.glow([(el[0] - s * 0.04, el[1] - 0.1), (wr[0] - s * 0.045, wr[1] + 0.1)], ORG, 2.0)
    r = f.head(J, b, SKIN, stern=2.0, brow="#141110", jaw=1.12)
    f.shape([r(-0.08, 0.04), r(-0.072, 0.1), r(0, 0.126), r(0.072, 0.1), r(0.08, 0.04), r(0.05, 0.086), r(0, 0.1), r(-0.05, 0.086)], "#1c1715")
    f.shape([r(-0.076, -0.02), r(-0.052, -0.056), r(-0.026, -0.054), r(0, -0.06), r(0.026, -0.054), r(0.052, -0.056), r(0.076, -0.02),
             r(0.066, -0.1), r(0.034, -0.16), r(0, -0.185), r(-0.034, -0.16), r(-0.066, -0.1)], "#1c1715")
    f.line([r(-0.022, -0.074), r(0.022, -0.074)], "#6b4a3a", 2.6, 0.9, sm=False)
    f.line([r(-0.03, 0.06), r(-0.045, 0.02)], "#5a3628", 2.4, 0.8, sm=False)             # brow scar
    return J, b


def seraphina(f):
    SKIN, WHT, ICE, NAVY, SIL, BLU = "#e3bfa6", "#eef1f7", "#b9c8e0", "#27324a", "#aab2c2", "#6fd0ff"
    # Poised: lead hand raised open beside the face, rear arm trailing, feet close.
    b = dict(h=1.72, sw=0.178, cw=0.152, ww=0.105, hw=0.16, arm=0.04, fore=0.035, thigh=0.086, calf=0.054, neck=0.04,
             head=0.93, hand=1.0, foot=1.0, armL=(0.14, -0.2, 0.17, 0.06), armR=(0.11, -0.27, 0.24, -0.47),
             legL=(0.02, 0.52, 0.03), legR=(0.07, 0.52, 0.15), tilt=-0.008)
    col = dict(thigh=NAVY, shin=SIL, foot=SIL, pelvis=NAVY, neck=SKIN, torso=NAVY, arm=NAVY, fore=WHT, hand=SKIN)
    k = b["h"] / 1.8
    f.shape([(-0.12, 1.02 * k), (-0.34, 0.66 * k), (-0.5, 0.26 * k), (-0.36, 0.34 * k), (-0.3, 0.14 * k), (-0.14, 0.5 * k), (-0.02, 0.9 * k)], ICE, opacity=0.95)
    f.shape([(0.1, 1.02 * k), (0.26, 0.72 * k), (0.3, 0.4 * k), (0.18, 0.56 * k), (0.06, 0.9 * k)], ICE, opacity=0.95)
    f.shape([(0.04, 1.87 * k), (0.2, 1.84 * k), (0.36, 1.6 * k), (0.47, 1.2 * k), (0.42, 0.88 * k), (0.36, 1.1 * k), (0.3, 1.42 * k), (0.2, 1.62 * k), (0.08, 1.74 * k)], "#f4f5fa")
    f.line([(0.16, 1.78 * k), (0.33, 1.5 * k), (0.41, 1.1 * k)], "#b7bccb", 2.2, 0.8)
    J = f.body(b, col)
    f.shape([(-0.06, 1.5 * k), (0.06, 1.5 * k), (0.152, 1.43 * k), (0.152, 1.3 * k), (0.092, 1.2 * k), (0, 1.165 * k), (-0.092, 1.2 * k), (-0.152, 1.3 * k), (-0.152, 1.43 * k)], WHT)
    f.line([(0, 1.49 * k), (0, 1.185 * k)], SIL, 2.2, 0.8, sm=False)
    f.line([(-0.14, 1.36 * k), (-0.05, 1.31 * k), (0, 1.33 * k), (0.05, 1.31 * k), (0.14, 1.36 * k)], SIL, 2.0, 0.7)
    f.glow([(-0.1, 1.28 * k), (0, 1.225 * k), (0.1, 1.28 * k)], BLU, 2.2)
    f.shape([(-0.11, 1.1 * k), (0.11, 1.1 * k), (0.165, 0.98 * k), (0.05, 0.9 * k), (-0.04, 0.96 * k), (-0.165, 0.97 * k)], ICE)
    f.shape([(-0.165, 0.99 * k), (-0.04, 0.97 * k), (-0.1, 0.66 * k), (-0.24, 0.58 * k)], WHT, opacity=0.97)
    f.line([(-0.13, 0.95 * k), (-0.16, 0.68 * k)], SIL, 2.0, 0.7, sm=False)
    f.glow([(-0.115, 1.045 * k), (0.115, 1.045 * k)], BLU, 2.0)
    for side in ("L", "R"):
        kn, an = J["kn" + side], J["an" + side]
        f.shape([(kn[0] - 0.054, kn[1] + 0.1), (kn[0] + 0.054, kn[1] + 0.1), (kn[0] + 0.042, kn[1] - 0.04), (kn[0], kn[1] - 0.08), (kn[0] - 0.042, kn[1] - 0.04)], WHT)
        f.glow([(kn[0], kn[1] - 0.12), (an[0], an[1] + 0.08)], BLU, 1.4)
    f.arms(J, b, col)
    sh = J["shL"]
    f.shape([(sh[0] - 0.065, sh[1] + 0.065), (sh[0] + 0.03, sh[1] + 0.1), (sh[0] + 0.11, sh[1] + 0.03), (sh[0] + 0.1, sh[1] - 0.08), (sh[0] - 0.02, sh[1] - 0.05)], WHT)
    for side in ("L", "R"):
        el = J["el" + side]
        f.ell(el, 0.042, 0.042, SIL)
    r = f.head(J, b, SKIN, stern=0.9, brow="#aeb2c0", eye="#3f78a8", jaw=0.9)
    f.shape([r(-0.083, -0.03), r(-0.092, 0.07), r(-0.05, 0.145), r(0.02, 0.165), r(0.082, 0.135), r(0.094, 0.06), r(0.084, 0.0),
             r(0.06, 0.07), r(0.02, 0.088), r(-0.02, 0.05), r(-0.064, 0.0), r(-0.074, -0.09)], "#f4f5fa")
    f.line([r(-0.07, 0.07), r(-0.02, 0.12), r(0.05, 0.13)], "#b7bccb", 2.0, 0.8)
    f.line([r(-0.076, -0.06), r(-0.07, 0.02)], "#b7bccb", 1.8, 0.7, sm=False)
    f.ell(r(0.035, 0.168), 0.03, 0.026, "#f4f5fa")
    f.glow([r(-0.005, 0.146), r(0.055, 0.154)], BLU, 1.8)
    return J, b


def nox(f):
    DARK, PLUM, MASK, VIO, GLV = "#191622", "#32253f", "#cfcbd8", "#a04bff", "#0e0c13"
    # Low and wide, arms hanging open like a trap.
    b = dict(h=1.68, sw=0.2, cw=0.165, ww=0.122, hw=0.15, arm=0.046, fore=0.042, thigh=0.09, calf=0.058, neck=0.048,
             head=0.98, hand=1.3, armL=(0.17, -0.2, 0.27, -0.44), armR=(0.19, -0.16, 0.3, -0.4),
             legL=(0.17, 0.5, 0.32), legR=(0.15, 0.5, 0.3), tilt=-0.015)
    col = dict(thigh=PLUM, shin=DARK, foot=GLV, pelvis=PLUM, neck=DARK, torso=DARK, arm=DARK, fore=PLUM, hand=GLV)
    k = b["h"] / 1.8
    J = f.body(b, col)
    for side, s in (("L", 1), ("R", -1)):
        hip, kn, an = J["hip" + side], J["kn" + side], J["an" + side]
        t = (an[0] - kn[0], an[1] - kn[1])
        c = (kn[0] + t[0] * 0.5, kn[1] + t[1] * 0.5)
        f.shape([(hip[0] - s * 0.075, hip[1] - 0.07), (hip[0] + s * 0.1, hip[1] + 0.03), (kn[0] + s * 0.15, kn[1] + 0.06), (kn[0] + s * 0.15, kn[1] - 0.14),
                 (c[0] + s * 0.07, c[1]), (c[0] - s * 0.06, c[1] + 0.01), (kn[0] - s * 0.1, kn[1] - 0.06)], PLUM)
        f.line([(hip[0] + s * 0.02, hip[1] - 0.06), (kn[0] + s * 0.04, kn[1] - 0.02), (c[0] + s * 0.02, c[1] + 0.03)], "#150f1c", 2.4, 0.7)
        f.line([(hip[0] + s * 0.08, hip[1] - 0.04), (kn[0] + s * 0.11, kn[1] - 0.06)], "#150f1c", 2.0, 0.5)
        f.glow([(c[0] - s * 0.055, c[1] + 0.012), (c[0] + s * 0.065, c[1] + 0.002)], VIO, 2.2)
    f.shape([(-0.13, 1.1 * k), (0.13, 1.1 * k), (0.155, 1.0 * k), (-0.155, 1.0 * k)], GLV, sharp=True)
    f.arms(J, b, col)
    for side, s in (("L", 1), ("R", -1)):
        el, wr, hd = J["el" + side], J["wr" + side], J["hand" + side]
        f.limb(el, wr, [(0.3, 0.05), (0.9, 0.044)], "#221a2c", cap=0.1)
        f.glow([(hd[0] - 0.035, hd[1] - 0.045), (hd[0] + 0.035, hd[1] - 0.05)], VIO, 2.6)
    f.shape([(-0.08, 1.57 * k), (-0.27, 1.48 * k), (-0.36, 1.27 * k), (-0.27, 1.32 * k), (-0.23, 1.17 * k), (-0.14, 1.29 * k), (-0.07, 1.15 * k),
             (0.0, 1.27 * k), (0.08, 1.13 * k), (0.14, 1.29 * k), (0.24, 1.15 * k), (0.27, 1.32 * k), (0.38, 1.24 * k), (0.27, 1.48 * k), (0.08, 1.57 * k)],
            PLUM, sharp=True)
    f.line([(-0.2, 1.46 * k), (-0.22, 1.3 * k)], "#150f1c", 2.2, 0.6, sm=False)
    f.line([(0.2, 1.46 * k), (0.22, 1.3 * k)], "#150f1c", 2.2, 0.6, sm=False)
    f.glow([(-0.22, 1.4 * k), (0.0, 1.355 * k), (0.22, 1.4 * k)], VIO, 2.2)
    f.shape([(-0.085, 1.52 * k), (-0.11, 1.63 * k), (-0.04, 1.6 * k), (0.0, 1.52 * k), (0.05, 1.63 * k), (0.14, 1.75 * k), (0.11, 1.52 * k)], DARK, sharp=True)
    r = f.head(J, b, MASK, face=False, jaw=0.92)
    f.shape([r(-0.09, 0.01), r(-0.087, 0.1), r(-0.03, 0.142), r(0.04, 0.142), r(0.09, 0.1), r(0.092, 0.01), r(0.06, 0.075), r(0, 0.092), r(-0.06, 0.075)], DARK)
    f.glow([r(-0.054, 0.036), r(0.0, 0.004), r(0.057, -0.032)], VIO, 3.8)
    f.line([r(-0.04, -0.072), r(0, -0.088), r(0.04, -0.072)], "#8f8a9c", 1.8, 0.6)
    f.line([r(0.0, 0.07), r(0.0, 0.02)], "#8f8a9c", 1.4, 0.4, sm=False)
    return J, b


def vexa(f):
    SKIN, WHT, GRA, RED, HAIR, DRK = "#d9ad91", "#eceded", "#3d4048", "#ff2440", "#b3122a", "#1b1c21"
    # Emitter arm raised and aimed, other fist at the hip.
    b = dict(h=1.76, sw=0.195, cw=0.165, ww=0.115, hw=0.162, arm=0.044, fore=0.04, thigh=0.09, calf=0.058, neck=0.044,
             head=0.93, hand=1.05, foot=1.05, armL=(0.1, -0.27, 0.07, -0.5), armR=(0.19, -0.14, 0.3, 0.1),
             legL=(0.08, 0.52, 0.17), legR=(0.1, 0.52, 0.22))
    col = dict(thigh=DRK, shin=WHT, foot=WHT, pelvis=DRK, neck=SKIN, torso=DRK, arm=SKIN, armR=GRA, fore=SKIN, foreR=WHT,
               hand=SKIN, handR=GRA)
    k = b["h"] / 1.8
    J = f.body(b, col)
    f.shape([(-0.075, 1.52 * k), (0.075, 1.52 * k), (0.2, 1.46 * k), (0.185, 1.3 * k), (0.155, 1.2 * k), (0.03, 1.16 * k), (-0.03, 1.16 * k),
             (-0.155, 1.2 * k), (-0.185, 1.3 * k), (-0.2, 1.46 * k)], WHT)
    f.shape([(-0.032, 1.52 * k), (0.032, 1.52 * k), (0.032, 1.17 * k), (-0.032, 1.17 * k)], GRA, sharp=True)
    f.glow([(0, 1.47 * k), (0, 1.2 * k)], RED, 2.4)
    for s in (1, -1):
        f.glow([(s * 0.17, 1.34 * k), (s * 0.06, 1.305 * k)], RED, 1.8)
        f.line([(s * 0.16, 1.42 * k), (s * 0.06, 1.4 * k)], "#a9abb3", 2.0, 0.8, sm=False)
        f.shape([(s * 0.12, 1.03 * k), (s * 0.2, 1.0 * k), (s * 0.215, 0.86 * k), (s * 0.135, 0.84 * k)], WHT, sharp=True)
        f.glow([(s * 0.155, 0.97 * k), (s * 0.175, 0.89 * k)], RED, 1.6)
    for y in (1.13, 1.085, 1.04):
        f.shape([(-0.1, (y + 0.016) * k), (0.1, (y + 0.016) * k), (0.094, (y - 0.014) * k), (-0.094, (y - 0.014) * k)], "#555862", sharp=True, sw=1.2, cel=0.5)
    for side in ("L", "R"):
        kn, an = J["kn" + side], J["an" + side]
        f.shape([(kn[0] - 0.062, kn[1] + 0.08), (kn[0] + 0.062, kn[1] + 0.08), (kn[0] + 0.04, kn[1] - 0.04), (kn[0] - 0.04, kn[1] - 0.04)], GRA, sharp=True)
        f.glow([(kn[0], kn[1] - 0.07), (an[0], an[1] + 0.09)], RED, 1.8)
        f.shape([(an[0] - 0.052, an[1] + 0.07), (an[0] + 0.052, an[1] + 0.07), (an[0] + 0.05, an[1] + 0.035), (an[0] - 0.05, an[1] + 0.035)], GRA, sharp=True)
    f.arms(J, b, col)
    sh, el, wr = J["shR"], J["elR"], J["wrR"]
    f.shape([(sh[0] + 0.06, sh[1] + 0.07), (sh[0] - 0.07, sh[1] + 0.085), (sh[0] - 0.1, sh[1] - 0.03), (sh[0] - 0.035, sh[1] - 0.1), (sh[0] + 0.06, sh[1] - 0.05)], WHT, sharp=True)
    f.limb(el, wr, [(0.05, 0.085, 0.06), (0.6, 0.095, 0.06), (1.0, 0.075, 0.05)], WHT, cap=0.15)
    f.glow([(el[0] - 0.03, el[1] + 0.06), (wr[0] - 0.03, wr[1] - 0.04)], RED, 2.8)
    f.ell((wr[0] - 0.062, wr[1] + 0.0), 0.022, 0.022, DRK, cel=0)
    f.glow([(wr[0] - 0.062, wr[1] + 0.012), (wr[0] - 0.062, wr[1] - 0.012)], RED, 2.2)
    r = f.head(J, b, SKIN, stern=1.2, brow="#7a1020", eye="#40444c", jaw=0.92)
    f.shape([r(-0.09, -0.08), r(-0.096, 0.06), r(-0.05, 0.142), r(0.03, 0.158), r(0.092, 0.11), r(0.097, 0.0), r(0.12, -0.12), r(0.08, -0.04),
             r(0.07, 0.06), r(0.0, 0.09), r(-0.05, 0.04), r(-0.072, -0.03)], HAIR)
    f.line([r(-0.07, 0.08), r(-0.01, 0.125), r(0.06, 0.11)], "#e0364d", 2.0, 0.8)
    f.line([r(0.092, 0.04), r(0.1, -0.07)], "#e0364d", 1.8, 0.7, sm=False)
    f.shape([r(0.01, 0.024), r(0.064, 0.024), r(0.068, -0.006), r(0.014, -0.006)], "#2a0a10", sharp=True, sw=1.4, form=False)
    f.glow([r(0.02, 0.009), r(0.058, 0.009)], RED, 2.2)
    return J, b


def ryuen(f):
    SKIN, IND, CRM, GOLD, GREY, SASH = "#c49a74", "#243352", "#e9dfc9", "#ffc94a", "#cfcfca", "#7a5a1e"
    # Still and open: lead palm forward at the chest, rear hand low at the hip.
    b = dict(h=1.75, sw=0.205, cw=0.172, ww=0.142, hw=0.16, arm=0.044, fore=0.042, thigh=0.086, calf=0.054, neck=0.048,
             head=0.96, hand=1.15, armL=(0.12, -0.24, 0.07, -0.02), armR=(0.11, -0.28, 0.08, -0.5),
             legL=(0.1, 0.52, 0.2), legR=(0.06, 0.52, 0.12))
    col = dict(thigh=CRM, shin=CRM, foot="#3a2c22", pelvis=CRM, neck=SKIN, torso=CRM, arm=CRM, fore=CRM, hand=SKIN)
    k = b["h"] / 1.8
    J = f.body(b, col)
    for side, s in (("L", 1), ("R", -1)):
        hip, kn, an = J["hip" + side], J["kn" + side], J["an" + side]
        f.shape([(hip[0] - s * 0.08, hip[1] - 0.08), (hip[0] + s * 0.1, hip[1]), (kn[0] + s * 0.12, kn[1]), (an[0] + s * 0.1, an[1] + 0.13),
                 (an[0] + s * 0.045, an[1] + 0.06), (an[0] - s * 0.05, an[1] + 0.06), (an[0] - s * 0.08, an[1] + 0.17), (kn[0] - s * 0.09, kn[1])], CRM)
        f.line([(hip[0] + s * 0.02, hip[1] - 0.1), (kn[0] + s * 0.03, kn[1] - 0.05), (an[0] + s * 0.02, an[1] + 0.12)], "#8f8468", 2.2, 0.6)
        f.shape([(an[0] - 0.055, an[1] + 0.085), (an[0] + 0.055, an[1] + 0.085), (an[0] + 0.052, an[1] + 0.055), (an[0] - 0.052, an[1] + 0.055)], SASH, sharp=True, sw=1.2, cel=0.5)
    for s in (1, -1):
        f.shape([(s * 0.035, 1.52 * k), (s * 0.225, 1.47 * k), (s * 0.205, 1.3 * k), (s * 0.172, 1.08 * k), (s * 0.3, 0.58 * k), (s * 0.3, 0.26 * k),
                 (s * 0.13, 0.22 * k), (s * 0.08, 0.9 * k), (s * 0.052, 1.1 * k)], IND)
        f.line([(s * 0.04, 1.5 * k), (s * 0.058, 1.1 * k), (s * 0.088, 0.9 * k), (s * 0.136, 0.25 * k)], GOLD, 3.0, 0.95)
        f.line([(s * 0.19, 1.0 * k), (s * 0.24, 0.6 * k), (s * 0.23, 0.3 * k)], "#131c30", 2.4, 0.6)
        f.line([(s * 0.14, 0.95 * k), (s * 0.18, 0.5 * k)], "#131c30", 2.0, 0.5, sm=False)
    f.shape([(-0.178, 1.115 * k), (0.178, 1.115 * k), (0.184, 0.99 * k), (-0.184, 0.99 * k)], SASH, sharp=True)
    f.glow([(-0.172, 1.052 * k), (0.172, 1.052 * k)], GOLD, 1.8)
    f.shape([(0.05, 0.99 * k), (0.105, 0.99 * k), (0.135, 0.68 * k), (0.075, 0.66 * k)], SASH, sharp=True)
    f.arms(J, b, col)
    for side, s in (("L", 1), ("R", -1)):   # wide sleeves hang from the forearm
        el, wr = J["el" + side], J["wr" + side]
        dx, dy = wr[0] - el[0], wr[1] - el[1]
        f.shape([(el[0] + 0.06, el[1] + 0.05), (el[0] - 0.06, el[1] + 0.04), (el[0] - 0.02 + dx * 0.4, el[1] - 0.17 + dy * 0.4),
                 (wr[0] - 0.02, wr[1] - 0.13), (wr[0] + 0.06, wr[1] - 0.05), (wr[0] + 0.05, wr[1] + 0.04)], CRM)
        f.line([(wr[0] - 0.018, wr[1] - 0.12), (wr[0] + 0.055, wr[1] - 0.045)], GOLD, 2.8, 0.95, sm=False)
        f.line([(el[0], el[1] + 0.0), (el[0] + dx * 0.4, el[1] - 0.1 + dy * 0.4)], "#8f8468", 2.0, 0.6, sm=False)
    r = f.head(J, b, SKIN, stern=1.0, brow=GREY, eye="#2a2018", jaw=0.96)
    f.shape([r(-0.08, 0.035), r(-0.078, 0.095), r(-0.03, 0.135), r(0.03, 0.135), r(0.078, 0.095), r(0.08, 0.035), r(0.04, 0.092), r(-0.04, 0.092)], GREY)
    f.ell(r(0, 0.158), 0.026, 0.03, GREY)
    f.line([r(-0.022, 0.132), r(0.022, 0.132)], GOLD, 3.2, 0.95, sm=False)
    f.shape([r(-0.046, -0.058), r(-0.02, -0.05), r(0, -0.057), r(0.02, -0.05), r(0.046, -0.058), r(0.036, -0.13), r(0.014, -0.23),
             r(0, -0.27), r(-0.014, -0.23), r(-0.036, -0.13)], GREY)
    f.line([r(0, -0.09), r(0, -0.24)], "#9a9a94", 1.8, 0.7, sm=False)
    f.line([r(-0.018, -0.07), r(0.018, -0.07)], "#7a5a48", 2.4, 0.9, sm=False)
    for s in (1, -1):
        f.line([r(s * 0.046, -0.012), r(s * 0.064, -0.004)], "#7a5a48", 1.6, 0.6, sm=False)
        f.line([r(s * 0.012, 0.062), r(s * 0.05, 0.066)], "#7a5a48", 1.4, 0.45, sm=False)
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
    backdrop(cv, 560, 1190, palette[-1])
    fn(Fig(cv, 560, 1190, PX, ink=True))
    _J, b = fn(Fig(cv, 560, 1190, PX))
    # height ruler
    for m in (0.5, 1.0, 1.5, 2.0):
        y = 1190 - m * PX
        cv.add(f'<line x1="120" y1="{y}" x2="150" y2="{y}" stroke="#5a5c66" stroke-width="2"/>')
        cv.text(160, y + 7, f"{m:.1f} m", 20, "#7c7e88")
    cv.text(1060, 130, name, 92, "#ffffff", "bold", spacing=6)
    cv.text(1064, 180, title.upper(), 30, palette[-1], "bold", spacing=8)
    cv.text(1064, 228, f"Height {b['h']:.2f} m   ·   concept v2 — for approval", 22, "#8d8f99")
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
    cv = Canvas(3000, 1420)
    cv.text(70, 90, "VANGUARD: BLOODLINE", 54, "#ffffff", "bold", spacing=5)
    cv.text(72, 132, "ROSTER CONCEPT LINE-UP  ·  v2 for approval  ·  heights to scale", 24, "#8d8f99", spacing=2)
    g = 1010
    cv.add(f'<line x1="60" y1="{g}" x2="2940" y2="{g}" stroke="#3a3c46" stroke-width="2"/>')
    S = 415
    for i, (fid, name, title, fn, palette, _n) in enumerate(ROSTER):
        x = 290 + i * 485
        cv.add(f'<ellipse cx="{x}" cy="{g}" rx="150" ry="16" fill="#000" opacity="0.5" filter="url(#soft)"/>')
        backdrop(cv, x, g, palette[-1], S / PX)
        fn(Fig(cv, x, g, S, ink=True))
        _J, b = fn(Fig(cv, x, g, S))
        cv.text(x, g + 56, name, 34, "#ffffff", "bold", "middle", 3)
        cv.text(x, g + 88, f"{title}  ·  {b['h']:.2f} m", 20, palette[-1], "normal", "middle")
    cv.add('<rect x="60" y="1120" width="2880" height="280" rx="12" fill="#d9dae0"/>')
    cv.text(84, 1152, "SILHOUETTE TEST", 18, "#5a5c66", "bold", spacing=3)
    for i, (_fid, _name, _title, fn, _p, _n) in enumerate(ROSTER):
        fn(Fig(cv, 290 + i * 485, 1390, 128, sil=True))
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
