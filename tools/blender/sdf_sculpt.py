"""Signed-distance sculpting engine for hero fighters (Kairo v4+) — FROM SCRATCH.

Why: v1–v3 fused tube/ellipsoid *meshes*, which kept reading as stacked toy
parts. Production fighting-game characters (SF6, Tekken 8) are sculpted as one
continuous anatomical surface: muscle masses that flow into each other, a real
skull/face construction, clothing that sits ON that anatomy. Signed distance
fields give the same behaviour as digital clay: every form is blended with a
smooth union, grooves are carved, cloth is the body dilated and clipped.

    layer = Layer("Body", slot="Skin", voxel=0.0025)
    layer.ell(c, r, bone="Chest", color=SKIN, k=0.02, rot=(rx, ry, rz))
    layer.cone(a, b, ra, rb, bone=..., k=..., squash=(1.0, 0.8))
    layer.groove(a, b, r, depth)            # carve (negative depth = ridge)
    mesh = layer.polygonize()                # dict(verts, tris)

Pure numpy + scikit-image (marching cubes); Blender is only used by the
caller for decimation, rigging and export. No base meshes, no external assets.

Conventions (same as character_builder.py): metres, Z up, the fighter faces
-Y, +X is the fighter's LEFT side.
"""

import math

import numpy as np

try:
    from skimage.measure import marching_cubes
except ImportError:  # pragma: no cover - reported by the caller
    marching_cubes = None


# ----------------------------------------------------------------- helpers --
def rotm(rot):
    """XYZ Euler degrees -> 3x3 (applied X, then Y, then Z)."""
    rx, ry, rz = (math.radians(a) for a in rot)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    X = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Z @ Y @ X


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def _frame(axis, up=None):
    axis = axis / np.linalg.norm(axis)
    ref = np.array(up if up is not None else ((1.0, 0, 0) if abs(axis[0]) < 0.9 else (0, 1.0, 0)), float)
    u = ref - axis * ref.dot(axis)
    u /= np.linalg.norm(u)
    w = np.cross(axis, u)
    return u, w


# -------------------------------------------------------------- primitives --
class Prim:
    """One sculpt operation. op: add (smooth union), sub (smooth carve),
    int (smooth intersect), groove (surface displacement), paint (colour only)."""

    def __init__(self, op, k, bone, color, lo, hi):
        self.op, self.k, self.bone, self.color = op, k, bone, color
        self.lo, self.hi = np.asarray(lo, float), np.asarray(hi, float)   # influence box

    def touches(self, lo, hi, pad):
        return np.all(self.hi + pad >= lo) and np.all(self.lo - pad <= hi)


class Ell(Prim):
    def __init__(self, c, r, rot=(0, 0, 0), frame=None, **kw):
        self.c, self.r = np.asarray(c, float), np.asarray(r, float)
        self.R = rotm(rot) if frame is None else np.asarray(frame, float)
        m = float(self.r.max())
        super().__init__(lo=self.c - m, hi=self.c + m, **kw)

    def d(self, P):
        q = (P - self.c) @ self.R          # into local frame
        k0 = np.linalg.norm(q / self.r, axis=1)
        k1 = np.linalg.norm(q / (self.r * self.r), axis=1)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


class Cone(Prim):
    """Round cone a->b with radii ra, rb. squash=(lateral, depth) scales the
    cross-section into an ellipse (muscled limbs are never round)."""

    def __init__(self, a, b, ra, rb, squash=(1.0, 1.0), up=None, **kw):
        self.a, self.b = np.asarray(a, float), np.asarray(b, float)
        self.ra, self.rb = float(ra), float(rb)
        ax = self.b - self.a
        self.L = float(np.linalg.norm(ax))
        self.ax = ax / self.L
        self.u, self.w = _frame(self.ax, up)
        self.sq = np.asarray(squash, float)
        m = max(ra, rb) * float(self.sq.max())
        super().__init__(lo=np.minimum(self.a, self.b) - m, hi=np.maximum(self.a, self.b) + m, **kw)

    def d(self, P):
        pa = P - self.a
        h = pa @ self.ax
        x = (pa @ self.u) / self.sq[0]
        y = (pa @ self.w) / self.sq[1]
        rad = np.sqrt(x * x + y * y)
        # 2D round cone (IQ) in (rad, h) space.
        r1, r2, L = self.ra, self.rb, self.L
        b = (r1 - r2) / L
        a = math.sqrt(max(1.0 - b * b, 1e-9))
        k = rad * (-b) + h * a       # dot(q, vec2(-b, a))
        d = np.where(k < 0.0, np.sqrt(rad * rad + h * h) - r1,
                     np.where(k > a * L, np.sqrt(rad * rad + (h - L) ** 2) - r2, rad * a + h * b - r1))
        return d * float(self.sq.min())


class RBox(Prim):
    def __init__(self, c, half, rad=0.005, rot=(0, 0, 0), frame=None, **kw):
        self.c, self.h, self.rad = np.asarray(c, float), np.asarray(half, float), rad
        self.R = rotm(rot) if frame is None else np.asarray(frame, float)
        m = float(np.linalg.norm(self.h)) + rad
        super().__init__(lo=self.c - m, hi=self.c + m, **kw)

    def d(self, P):
        q = np.abs((P - self.c) @ self.R) - (self.h - self.rad)
        out = np.linalg.norm(np.maximum(q, 0.0), axis=1)
        return out + np.minimum(q.max(axis=1), 0.0) - self.rad


class Sheet(Prim):
    """Hanging cloth panel: a thin sheet with folds, wrap and a torn hem.
    Local frame: u across, v down the cloth, w out of the cloth."""

    def __init__(self, top, down, across, width, length, thick=0.003, folds=((0.045, 0.012, 0.0),),
                 wrap=0.0, tear=0.03, seed=0, **kw):
        self.top = np.asarray(top, float)
        v = np.asarray(down, float)
        self.v = v / np.linalg.norm(v)
        u = np.asarray(across, float)
        u = u - self.v * (u @ self.v)
        self.u = u / np.linalg.norm(u)
        self.w = np.cross(self.u, self.v)
        self.hw, self.L, self.t = width / 2, length, thick
        self.folds, self.wrap, self.tear = folds, wrap, tear
        rng = np.random.default_rng(seed)
        self.teeth = rng.uniform(0.3, 1.0, 9)
        m = max(width, length)
        super().__init__(lo=self.top - m, hi=self.top + m, **kw)

    def d(self, P):
        q = P - self.top
        u, v, w = q @ self.u, q @ self.v, q @ self.w
        g = np.clip(v / self.L, 0, 1)
        h = self.wrap * u * u                                  # wrap around the thigh
        for lam, amp, ph in self.folds:
            h = h + amp * (0.3 + 0.7 * g) * np.sin(2 * np.pi * u / lam + ph + 1.3 * g)
        d_sheet = np.abs(w - h) * 0.7 - self.t
        # torn hem: sawtooth of uneven teeth along u
        x = (u / self.hw + 1) * 0.5 * (len(self.teeth) - 1)
        i = np.clip(np.floor(x).astype(int), 0, len(self.teeth) - 2)
        f = x - i
        tooth = np.abs(f - 0.5) * 2
        hem = self.L - self.tear * (tooth * self.teeth[i] + (1 - tooth) * 0.1)
        d_out = np.maximum.reduce([np.abs(u) - self.hw * (1 - 0.15 * g), -v, v - hem])
        return np.maximum(d_sheet, d_out)


class Plane(Prim):
    """Half-space; inside is the side the normal points AWAY from."""

    def __init__(self, p, n, **kw):
        self.p = np.asarray(p, float)
        self.n = np.asarray(n, float) / np.linalg.norm(n)
        super().__init__(lo=(-9, -9, -9), hi=(9, 9, 9), **kw)

    def d(self, P):
        return (P - self.p) @ self.n


class Groove(Prim):
    """Displace the surface along a polyline: depth>0 carves in, <0 raises."""

    def __init__(self, pts, r, depth, **kw):
        self.pts = np.asarray(pts, float)
        self.r, self.depth = r, depth
        super().__init__(lo=self.pts.min(axis=0) - r, hi=self.pts.max(axis=0) + r, **kw)

    def dist(self, P):
        best = np.full(len(P), 1e9)
        for a, b in zip(self.pts[:-1], self.pts[1:]):
            ab = b - a
            t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
            best = np.minimum(best, np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
        return best

    def apply(self, d, P):
        x = np.clip(self.dist(P) / self.r, 0, 1)
        f = (1 - x * x) ** 2                      # smooth bell
        return d + self.depth * f


# ------------------------------------------------------------------- layer --
class Layer:
    """One surface of the character (skin, top, trousers…)."""

    def __init__(self, name, slot, voxel=0.0025, bounds=None, tris=8000, base=None, base_offset=0.0, color=None):
        self.name, self.slot, self.voxel, self.tris = name, slot, voxel, tris
        self.bounds = bounds          # (lo, hi) or None = from prims
        self.ops = []
        self.base, self.base_offset = base, base_offset   # start from another layer's field
        self.color = color            # colour of the surface inherited from base

    # authoring helpers --------------------------------------------------
    def _add(self, p):
        self.ops.append(p)
        return p

    def ell(self, c, r, bone, color=None, k=0.012, rot=(0, 0, 0), op="add", frame=None):
        return self._add(Ell(c, r, rot, frame, op=op, k=k, bone=bone, color=color))

    def muscle(self, a, b, t, off, r, bone, color=None, k=0.015, op="add", up=None):
        """Ellipsoid aligned to the segment a->b, centred at lerp(a,b,t)+off.
        r = (lateral, depth, along-axis) radii — a muscle belly on a bone."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        ax = (b - a) / np.linalg.norm(b - a)
        u, w = _frame(ax, up)
        c = a + (b - a) * t + np.asarray(off, float)
        return self._add(Ell(c, r, frame=np.stack([u, w, ax], 1), op=op, k=k, bone=bone, color=color))

    def cone(self, a, b, ra, rb, bone, color=None, k=0.012, squash=(1, 1), up=None, op="add"):
        return self._add(Cone(a, b, ra, rb, squash, up, op=op, k=k, bone=bone, color=color))

    def box(self, c, half, bone, color=None, rad=0.004, k=0.006, rot=(0, 0, 0), op="add", frame=None):
        return self._add(RBox(c, half, rad, rot, frame, op=op, k=k, bone=bone, color=color))

    def plate(self, a, b, t, off, half, bone, color=None, rad=0.004, k=0.006, op="add", up=None, twist=0.0):
        """Rounded box aligned to segment a->b (half = lateral, depth, along)."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        ax = (b - a) / np.linalg.norm(b - a)
        u, w = _frame(ax, up)
        if twist:
            c_, s_ = math.cos(math.radians(twist)), math.sin(math.radians(twist))
            u, w = u * c_ + w * s_, -u * s_ + w * c_
        c = a + (b - a) * t + np.asarray(off, float)
        return self._add(RBox(c, half, rad, frame=np.stack([u, w, ax], 1), op=op, k=k, bone=bone, color=color))

    def sheet(self, top, down, across, width, length, bone, color=None, k=0.004, **kw):
        return self._add(Sheet(top, down, across, width, length, op="add", k=k, bone=bone, color=color, **kw))

    def clip(self, p, n, k=0.004):
        """Keep the part of the surface on the side opposite to n."""
        return self._add(Plane(p, n, op="int", k=k, bone=None, color=None))

    def groove(self, pts, r, depth):
        if len(pts) == 1:
            pts = [pts[0], pts[0]]
        return self._add(Groove(pts, r, depth, op="groove", k=0, bone=None, color=None))

    def paint(self, prim_kind, *args, color, soft=0.004, **kw):
        """Colour-only volume, e.g. the glowing Origin line or the hair streak."""
        cls = dict(ell=Ell, cone=Cone, box=RBox)[prim_kind]
        p = cls(*args, op="paint", k=soft, bone=None, color=color, **kw)
        return self._add(p)

    # evaluation ---------------------------------------------------------
    def field(self, P, lo=None, hi=None, pad=0.0):
        """SDF at points P (N,3). lo/hi: region for primitive culling."""
        if self.base is not None:
            d = self.base.field(P, lo, hi, pad) - self.base_offset
        else:
            d = np.full(len(P), 1.0)
        for p in self.ops:
            if p.op == "paint":
                continue
            if lo is not None and p.op in ("add", "sub", "groove") and not p.touches(lo, hi, pad + p.k):
                continue
            if p.op == "groove":
                d = p.apply(d, P)
            elif p.op == "add":
                d = smin(d, p.d(P), p.k)
            elif p.op == "sub":
                d = smax(d, -p.d(P), p.k)
            elif p.op == "int":
                d = smax(d, p.d(P), p.k)
        return d

    def prim_bounds(self):
        adds = [p for p in self.ops if p.op == "add"]
        if self.base is not None and not adds:
            return self.base.prim_bounds()
        lo = np.min([p.lo for p in adds], axis=0)
        hi = np.max([p.hi for p in adds], axis=0)
        if self.base is not None:
            blo, bhi = self.base.prim_bounds()
            lo, hi = np.minimum(lo, blo), np.maximum(hi, bhi)
        return lo, hi

    def polygonize(self, voxel=None, block=16):
        """Sparse narrow-band sampling + marching cubes. Returns verts, tris."""
        h = voxel or self.voxel
        lo, hi = self.bounds if self.bounds else self.prim_bounds()
        lo = np.asarray(lo, float) - 3 * h
        hi = np.asarray(hi, float) + 3 * h
        n = np.ceil((hi - lo) / h).astype(int) + 1
        nb = np.ceil(n / block).astype(int)
        n = nb * block + 1
        vol = np.ones(tuple(n), dtype=np.float32)
        # Coarse pass at block centres decides which blocks straddle the surface.
        bi = np.stack(np.meshgrid(*[np.arange(k) for k in nb], indexing="ij"), -1).reshape(-1, 3)
        centres = lo + (bi + 0.5) * block * h
        dc = self.field(centres)
        half_diag = math.sqrt(3) * block * h * 0.5
        near = np.abs(dc) < half_diag * 1.6 + 0.012
        sign_far = np.sign(dc)
        for (i, j, k), s in zip(bi[~near], sign_far[~near]):
            vol[i * block:(i + 1) * block + 1, j * block:(j + 1) * block + 1, k * block:(k + 1) * block + 1] = s
        ax = np.arange(block + 1) * h
        gx, gy, gz = np.meshgrid(ax, ax, ax, indexing="ij")
        local = np.stack([gx, gy, gz], -1).reshape(-1, 3)
        for i, j, k in bi[near]:
            o = lo + np.array([i, j, k]) * block * h
            P = local + o
            d = self.field(P, o, o + block * h, pad=2 * h)
            vol[i * block:(i + 1) * block + 1, j * block:(j + 1) * block + 1,
                k * block:(k + 1) * block + 1] = d.reshape(block + 1, block + 1, block + 1)
        verts, faces, _n, _v = marching_cubes(vol, level=0.0, spacing=(h, h, h))
        verts += lo
        # skimage winds faces so normals point toward increasing values
        # (outside); flip to standard CCW-outward.
        faces = faces[:, ::-1]
        return verts, faces.astype(np.int64)

    def colors(self, V, chunk=150000):
        """Paint colour only (no weights), chunked — for dense bake sources."""
        out = np.zeros((len(V), 3))
        for i in range(0, len(V), chunk):
            P = V[i:i + chunk]
            own = [p for p in self.ops if p.op == "add" and p.color is not None]
            if own:
                Dc = [p.d(P) for p in own]
                cols = [p.color for p in own]
                if self.base is not None and self.color is not None:
                    Dc.append(self.base.field(P) - self.base_offset)
                    cols.append(self.color)
                Dc = np.stack(Dc, 1)
                Sc = np.exp(-(Dc - Dc.min(axis=1, keepdims=True)) / 0.003)
                C = (Sc[:, :, None] * np.array(cols)[None]).sum(1) / Sc.sum(1, keepdims=True)
            else:
                C = np.tile(np.asarray(self.color or (0.5, 0.5, 0.5), float), (len(P), 1))
            for p in self.ops:
                if p.op != "paint":
                    continue
                t = np.clip(0.5 - p.d(P) / (2 * p.k), 0, 1)[:, None]
                C = C * (1 - t) + np.asarray(p.color)[None] * t
            out[i:i + chunk] = C
        return np.clip(out, 0, 1)

    # attributes -----------------------------------------------------------
    def attributes(self, V, bones, tau=0.012, default_color=(0.5, 0.5, 0.5)):
        """Per-vertex bone weights (soft nearest-form) and paint colour."""
        adds = [p for p in self.ops if p.op == "add" and p.bone is not None]
        src = self
        while src.base is not None:                  # cloth also follows the body it is cut from
            src = src.base
            adds += [p for p in src.ops if p.op == "add" and p.bone is not None]
        D = np.stack([p.d(V) for p in adds], 1)          # (N, P)
        dmin = D.min(axis=1, keepdims=True)
        S = np.exp(-(D - dmin) / tau)
        W = np.zeros((len(V), len(bones)))
        for j, p in enumerate(adds):
            W[:, bones[p.bone]] += S[:, j]
        W /= W.sum(axis=1, keepdims=True)
        # colour from this layer's own coloured forms (sharper falloff)
        own = [p for p in self.ops if p.op == "add" and p.color is not None]
        if own:
            Dc = [p.d(V) for p in own]
            cols = [p.color for p in own]
            if self.base is not None and self.color is not None:
                Dc.append(self.base.field(V) - self.base_offset)
                cols.append(self.color)
            Dc = np.stack(Dc, 1)
            Sc = np.exp(-(Dc - Dc.min(axis=1, keepdims=True)) / 0.003)
            C = (Sc[:, :, None] * np.array(cols)[None]).sum(1) / Sc.sum(1, keepdims=True)
        else:
            C = np.tile(np.asarray(default_color, float), (len(V), 1))
        for p in self.ops:
            if p.op != "paint":
                continue
            t = np.clip(0.5 - p.d(V) / (2 * p.k), 0, 1)[:, None]
            C = C * (1 - t) + np.asarray(p.color)[None] * t
        return W, C
