"""Minimal BVH reader: hierarchy, channels and forward kinematics.

positions(frames) -> {joint: (N, 3) array} in Blender axes (Z up), metres,
with the skeleton scaled so the source stands `height` metres tall.
Only numpy; usable inside and outside Blender.
"""
import numpy as np


class Joint:
    def __init__(self, name, parent):
        self.name, self.parent = name, parent
        self.offset = np.zeros(3)
        self.channels = []
        self.children = []
        self.end = None          # end-site offset


def _rot(axis, deg):
    r = np.radians(deg)
    c, s = np.cos(r), np.sin(r)
    n = len(r)
    m = np.zeros((n, 3, 3))
    if axis == "X":
        m[:, 0, 0] = 1; m[:, 1, 1] = c; m[:, 1, 2] = -s; m[:, 2, 1] = s; m[:, 2, 2] = c
    elif axis == "Y":
        m[:, 1, 1] = 1; m[:, 0, 0] = c; m[:, 0, 2] = s; m[:, 2, 0] = -s; m[:, 2, 2] = c
    else:
        m[:, 2, 2] = 1; m[:, 0, 0] = c; m[:, 0, 1] = -s; m[:, 1, 0] = s; m[:, 1, 1] = c
    return m


class BVH:
    def __init__(self, path):
        toks = open(path).read().split()
        self.joints, order = {}, []
        i, stack, cur = 0, [], None
        while toks[i] != "MOTION":
            t = toks[i]
            if t in ("ROOT", "JOINT"):
                j = Joint(toks[i + 1], cur)
                if cur:
                    cur.children.append(j)
                self.joints[j.name] = j
                order.append(j)
                cur = j
                i += 2
            elif t == "End":
                i += 2
                assert toks[i] == "{" and toks[i + 1] == "OFFSET"
                cur.end = np.array([float(x) for x in toks[i + 2:i + 5]])
                i += 6
            elif t == "OFFSET":
                cur.offset = np.array([float(x) for x in toks[i + 1:i + 4]])
                i += 4
            elif t == "CHANNELS":
                n = int(toks[i + 1])
                cur.channels = toks[i + 2:i + 2 + n]
                i += 2 + n
            elif t == "}":
                cur = cur.parent if cur else None
                i += 1
            else:
                i += 1
        self.order = order
        self.frames = int(toks[i + 2])
        self.dt = float(toks[i + 5])
        nch = sum(len(j.channels) for j in order)
        self.data = np.array(toks[i + 6:i + 6 + self.frames * nch], float).reshape(self.frames, nch)

    def world(self):
        """World rotation (N,3,3) and position (N,3) per joint, BVH axes and units."""
        R, P, col = {}, {}, 0
        n = self.frames
        for j in self.order:
            local_r = np.repeat(np.eye(3)[None], n, 0)
            local_t = np.repeat(j.offset[None], n, 0)
            for ch in j.channels:
                v = self.data[:, col]
                col += 1
                if ch.endswith("position"):
                    local_t = local_t.copy()
                    local_t[:, "XYZ".index(ch[0])] = v + (0 if j.parent else 0)
                else:
                    local_r = local_r @ _rot(ch[0], v)
            if j.parent is None:
                R[j.name], P[j.name] = local_r, local_t
            else:
                pr, pp = R[j.parent.name], P[j.parent.name]
                R[j.name] = pr @ local_r
                P[j.name] = pp + np.einsum("nij,nj->ni", pr, local_t)
            if j.end is not None:
                P[j.name + "_end"] = P[j.name] + np.einsum("nij,j->ni", R[j.name], j.end)
        return R, P

    def positions(self, height=1.8):
        """Joint positions in Blender axes (x, -z, y), metres, scaled to `height`."""
        _, P = self.world()
        out = {k: np.stack([v[:, 0], -v[:, 2], v[:, 1]], 1) for k, v in P.items()}
        # stature from the first frame: head top to lowest toe
        top = out["Head_end"][0, 2]
        low = min(out["LeftToeBase"][0, 2], out["RightToeBase"][0, 2])
        s = height / max(1e-6, (top - low) * 1.04)     # head end site sits a little below the crown
        return {k: v * s for k, v in out.items()}, s
